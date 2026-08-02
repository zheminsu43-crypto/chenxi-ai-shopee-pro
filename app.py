import io
import os
import re
import json
import hashlib
import secrets
from datetime import datetime, date, timedelta

import streamlit as st
from PIL import Image, ImageOps

# =========================================================
# AI 蝦皮半自動化 2.5 PRO
#
# Gemini API 版本
#
# 使用：
#   Google Gemini API
#   google-genai
#
# 不使用：
#   GPT / ChatGPT API
#   WeChat API
#   LINE API
#   Supabase
#   Google OAuth
#
# 功能：
#   會員註冊
#   會員登入
#   會員期限
#   管理員
#   Gemini 商品圖片分析
#   商品分析
#   蝦皮商品文案
#   即夢 2.5 Prompt
#   商品圖片處理
# =========================================================


# =========================================================
# 網頁設定
# =========================================================

st.set_page_config(
    page_title="AI 蝦皮半自動化 2.5 PRO",
    page_icon="🛒",
    layout="wide",
)


# =========================================================
# 系統設定
# =========================================================

APP_NAME = "AI 蝦皮半自動化 2.5 PRO"

DATA_DIR = "data"
MEMBERS_FILE = os.path.join(DATA_DIR, "members.json")

MAX_IMAGE_SIZE = 1600
MAX_IMAGE_MB = 20

DEFAULT_MEMBER_DAYS = 30

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# Gemini 模型
GEMINI_MODEL = "gemini-2.5-flash"


# =========================================================
# 建立資料夾
# =========================================================

os.makedirs(
    DATA_DIR,
    exist_ok=True
)


# =========================================================
# Gemini API
# =========================================================

def get_gemini_client():

    try:

        from google import genai

    except ImportError:

        return None, (
            "尚未安裝 google-genai。\n\n"
            "請在終端機執行：\n"
            "pip install -U google-genai"
        )

    # 優先從 Streamlit secrets 讀取
    api_key = ""

    try:

        api_key = st.secrets.get(
            "GEMINI_API_KEY",
            ""
        )

    except Exception:
        pass

    # 如果 secrets 沒有，再從環境變數讀取
    if not api_key:

        api_key = os.getenv(
            "GEMINI_API_KEY",
            ""
        )

    # 最後從 Session 暫存的 API Key 讀取
    if not api_key:

        api_key = st.session_state.get(
            "gemini_api_key",
            ""
        )

    if not api_key:

        return None, (
            "尚未設定 Gemini API Key。"
        )

    try:

        client = genai.Client(
            api_key=api_key
        )

        return client, ""

    except Exception as e:

        return None, (
            f"Gemini 初始化失敗：{e}"
        )


def gemini_text(prompt):

    client, error = get_gemini_client()

    if client is None:

        return None, error

    try:

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )

        text = getattr(
            response,
            "text",
            None
        )

        if not text:

            return None, (
                "Gemini 沒有返回文字結果。"
            )

        return text.strip(), ""

    except Exception as e:

        return None, (
            f"Gemini API 執行失敗：{e}"
        )


def gemini_image_analysis(
    image,
    prompt
):

    client, error = get_gemini_client()

    if client is None:

        return None, error

    try:

        from google.genai import types

        buffer = io.BytesIO()

        image.save(
            buffer,
            format="JPEG",
            quality=95
        )

        image_bytes = buffer.getvalue()

        response = client.models.generate_content(

            model=GEMINI_MODEL,

            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type="image/jpeg"
                ),
                prompt
            ]
        )

        text = getattr(
            response,
            "text",
            None
        )

        if not text:

            return None, (
                "Gemini 沒有返回圖片分析結果。"
            )

        return text.strip(), ""

    except Exception as e:

        return None, (
            f"Gemini 圖片分析失敗：{e}"
        )


# =========================================================
# 會員資料庫
# =========================================================

def load_members():

    if not os.path.exists(
        MEMBERS_FILE
    ):

        return []

    try:

        with open(
            MEMBERS_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if isinstance(
            data,
            list
        ):

            return data

    except Exception:

        pass

    return []


def save_members(
    members
):

    with open(
        MEMBERS_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            members,
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# 密碼
# =========================================================

def hash_password(
    password
):

    salt = secrets.token_hex(
        16
    )

    digest = hashlib.sha256(
        (
            salt + password
        ).encode("utf-8")
    ).hexdigest()

    return (
        f"{salt}${digest}"
    )


def verify_password(
    password,
    saved_value
):

    try:

        salt, saved_hash = (
            saved_value.split(
                "$",
                1
            )
        )

        digest = hashlib.sha256(
            (
                salt + password
            ).encode("utf-8")
        ).hexdigest()

        return secrets.compare_digest(
            digest,
            saved_hash
        )

    except Exception:

        return False


# =========================================================
# 初始化管理員
# =========================================================

def ensure_admin():

    members = load_members()

    for member in members:

        if (
            member.get(
                "username"
            )
            == ADMIN_USERNAME
        ):

            return

    admin = {

        "id":
        secrets.token_hex(8),

        "username":
        ADMIN_USERNAME,

        "password_hash":
        hash_password(
            ADMIN_PASSWORD
        ),

        "name":
        "系統管理員",

        "email":
        "",

        "role":
        "admin",

        "status":
        "active",

        "expires":
        (
            date.today()
            + timedelta(
                days=3650
            )
        ).isoformat(),

        "created_at":
        datetime.now().isoformat()

    }

    members.append(
        admin
    )

    save_members(
        members
    )


ensure_admin()


# =========================================================
# 會員查詢
# =========================================================

def find_member(
    username
):

    username = (
        username
        .strip()
        .lower()
    )

    members = load_members()

    for member in members:

        if (
            member.get(
                "username",
                ""
            ).lower()
            == username
        ):

            return member

    return None


def find_member_by_email(
    email
):

    email = (
        email
        .strip()
        .lower()
    )

    if not email:

        return None

    members = load_members()

    for member in members:

        if (
            member.get(
                "email",
                ""
            ).lower()
            == email
        ):

            return member

    return None


# =========================================================
# 建立會員
# =========================================================

def create_member(
    username,
    password,
    name,
    email
):

    username = (
        username
        .strip()
        .lower()
    )

    email = (
        email
        .strip()
        .lower()
    )

    if find_member(
        username
    ):

        return (
            False,
            "帳號已存在。"
        )

    if (
        email
        and find_member_by_email(
            email
        )
    ):

        return (
            False,
            "Email 已註冊。"
        )

    expires = (
        date.today()
        + timedelta(
            days=DEFAULT_MEMBER_DAYS
        )
    ).isoformat()

    member = {

        "id":
        secrets.token_hex(8),

        "username":
        username,

        "password_hash":
        hash_password(
            password
        ),

        "name":
        name.strip(),

        "email":
        email,

        "role":
        "member",

        "status":
        "active",

        "expires":
        expires,

        "created_at":
        datetime.now().isoformat()

    }

    members = load_members()

    members.append(
        member
    )

    save_members(
        members
    )

    return (
        True,
        member
    )


# =========================================================
# 更新會員
# =========================================================

def update_member(
    member_id,
    updates
):

    members = load_members()

    for member in members:

        if (
            member.get(
                "id"
            )
            == member_id
        ):

            member.update(
                updates
            )

            save_members(
                members
            )

            return True

    return False


# =========================================================
# 登入
# =========================================================

def check_login(
    username,
    password
):

    member = find_member(
        username
    )

    if not member:

        return (
            False,
            "invalid"
        )

    status = str(
        member.get(
            "status",
            "active"
        )
    ).lower()

    if status != "active":

        return (
            False,
            "disabled"
        )

    saved_hash = str(
        member.get(
            "password_hash",
            ""
        )
    )

    if (
        not saved_hash
        or not verify_password(
            password,
            saved_hash
        )
    ):

        return (
            False,
            "invalid"
        )

    expires_text = str(
        member.get(
            "expires",
            ""
        )
    )

    try:

        expires_date = date.fromisoformat(
            expires_text
        )

    except Exception:

        return (
            False,
            "invalid_date"
        )

    if date.today() > expires_date:

        return (
            False,
            "expired"
        )

    return (
        True,
        member
    )


# =========================================================
# Session
# =========================================================

if "logged_in" not in st.session_state:

    st.session_state.logged_in = False


if "page" not in st.session_state:

    st.session_state.page = "login"


if "analysis_result" not in st.session_state:

    st.session_state.analysis_result = ""


if "generated_prompt" not in st.session_state:

    st.session_state.generated_prompt = ""


if "generated_copy" not in st.session_state:

    st.session_state.generated_copy = ""


if "gemini_analysis" not in st.session_state:

    st.session_state.gemini_analysis = ""


if "gemini_api_key" not in st.session_state:

    st.session_state.gemini_api_key = ""


def logout():

    st.session_state.logged_in = False

    st.session_state.pop(
        "username",
        None
    )

    st.session_state.pop(
        "member",
        None
    )

    st.session_state.analysis_result = ""

    st.session_state.generated_prompt = ""

    st.session_state.generated_copy = ""

    st.session_state.gemini_analysis = ""

    st.session_state.page = "login"

    st.rerun()


# =========================================================
# CSS
# =========================================================

st.markdown(
    """
    <style>

    .main-title {
        text-align: center;
        font-size: 42px;
        font-weight: 800;
        margin-top: 20px;
        margin-bottom: 10px;
    }

    .main-subtitle {
        text-align: center;
        font-size: 17px;
        opacity: 0.75;
        margin-bottom: 30px;
    }

    .card {
        padding: 20px;
        border-radius: 15px;
        border: 1px solid rgba(128,128,128,.25);
        margin-bottom: 15px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# 登入頁
# =========================================================

def login_page():

    st.markdown(
        '<div class="main-title">'
        '🛒 AI 蝦皮半自動化 2.5 PRO'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="main-subtitle">'
        '會員登入｜Gemini AI｜商品分析｜即夢 2.5'
        '</div>',
        unsafe_allow_html=True
    )

    _, center, _ = st.columns(
        [1, 2, 1]
    )

    with center:

        st.subheader(
            "🔐 會員登入"
        )

        username = st.text_input(
            "會員帳號",
            placeholder="輸入會員帳號",
            key="login_username"
        )

        password = st.text_input(
            "會員密碼",
            type="password",
            placeholder="輸入會員密碼",
            key="login_password"
        )

        if st.button(
            "🚀 登入系統",
            type="primary",
            use_container_width=True
        ):

            if (
                not username
                or not password
            ):

                st.error(
                    "請輸入會員帳號與密碼。"
                )

            else:

                success, result = check_login(
                    username,
                    password
                )

                if success:

                    st.session_state.logged_in = True

                    st.session_state.username = (
                        username
                        .strip()
                        .lower()
                    )

                    st.session_state.member = result

                    st.session_state.page = "main"

                    st.rerun()

                else:

                    messages = {

                        "expired":
                        "⛔ 會員資格已到期，請聯絡管理員續期。",

                        "disabled":
                        "⛔ 此會員帳號目前已停權。",

                        "invalid_date":
                        "⛔ 會員到期日資料錯誤。",

                        "invalid":
                        "❌ 帳號或密碼錯誤。"

                    }

                    st.error(
                        messages.get(
                            result,
                            "❌ 登入失敗。"
                        )
                    )

        st.divider()

        if st.button(
            "📝 還沒有帳號？註冊會員",
            use_container_width=True
        ):

            st.session_state.page = "register"

            st.rerun()

        st.divider()

        st.caption(
            "本系統使用會員帳號＋密碼登入。"
        )

        with st.expander(
            "🔐 管理員測試帳號"
        ):

            st.code(
                "帳號：admin\n密碼：admin123"
            )


# =========================================================
# 註冊頁
# =========================================================

def register_page():

    st.markdown(
        '<div class="main-title">'
        '📝 會員註冊'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="main-subtitle">'
        '建立 AI 蝦皮半自動化 2.5 PRO 會員帳號'
        '</div>',
        unsafe_allow_html=True
    )

    _, center, _ = st.columns(
        [1, 2, 1]
    )

    with center:

        st.subheader(
            "👤 建立會員帳號"
        )

        name = st.text_input(
            "姓名 / 暱稱",
            placeholder="例如：王小明"
        )

        email = st.text_input(
            "Email",
            placeholder="例如：example@gmail.com"
        )

        username = st.text_input(
            "會員帳號",
            placeholder="3～30 個英數字或底線"
        )

        password = st.text_input(
            "會員密碼",
            type="password",
            placeholder="至少 6 個字元"
        )

        password_confirm = st.text_input(
            "再次輸入密碼",
            type="password"
        )

        if st.button(
            "🚀 建立會員帳號",
            type="primary",
            use_container_width=True
        ):

            username_clean = (
                username
                .strip()
                .lower()
            )

            email_clean = (
                email
                .strip()
                .lower()
            )

            if not name.strip():

                st.error(
                    "請輸入姓名或暱稱。"
                )

            elif not re.fullmatch(
                r"[^@\s]+@[^@\s]+\.[^@\s]+",
                email_clean
            ):

                st.error(
                    "請輸入正確 Email。"
                )

            elif not re.fullmatch(
                r"[a-z0-9_]{3,30}",
                username_clean
            ):

                st.error(
                    "帳號只能使用小寫英數字與底線，長度 3～30。"
                )

            elif len(password) < 6:

                st.error(
                    "密碼至少需要 6 個字元。"
                )

            elif password != password_confirm:

                st.error(
                    "兩次輸入的密碼不一致。"
                )

            else:

                success, result = create_member(
                    username_clean,
                    password,
                    name,
                    email_clean
                )

                if success:

                    st.success(
                        "🎉 會員帳號建立成功！"
                    )

                    st.info(
                        f"會員資格預設 {DEFAULT_MEMBER_DAYS} 天，"
                        "請返回登入。"
                    )

                else:

                    st.error(
                        str(result)
                    )

        st.divider()

        if st.button(
            "⬅️ 返回登入",
            use_container_width=True
        ):

            st.session_state.page = "login"

            st.rerun()


# =========================================================
# 登入判斷
# =========================================================

if not st.session_state.logged_in:

    if (
        st.session_state.page
        == "register"
    ):

        register_page()

    else:

        login_page()

    st.stop()


# =========================================================
# 會員資料
# =========================================================

current_username = st.session_state.get(
    "username",
    ""
)

current_member = st.session_state.get(
    "member",
    {}
)

latest_member = find_member(
    current_username
)

if latest_member:

    current_member = latest_member

    st.session_state.member = (
        latest_member
    )


member_id = current_member.get(
    "id",
    ""
)

member_name = str(
    current_member.get(
        "name",
        current_username
    )
)

member_email = str(
    current_member.get(
        "email",
        ""
    )
)

member_role = str(
    current_member.get(
        "role",
        "member"
    )
)

member_status = str(
    current_member.get(
        "status",
        "active"
    )
)

member_expires = str(
    current_member.get(
        "expires",
        ""
    )
)


try:

    expire_date = date.fromisoformat(
        member_expires
    )

    remaining_days = (
        expire_date
        - date.today()
    ).days

except Exception:

    remaining_days = -999


if (
    member_status.lower()
    != "active"
):

    st.error(
        "⛔ 此會員帳號目前已停權。"
    )

    if st.button(
        "🚪 返回登入"
    ):

        logout()

    st.stop()


# =========================================================
# 商品分類判斷
# =========================================================

def detect_product_category(
    text
):

    text = text.lower()

    categories = {

        "保養品": [
            "保養",
            "精華",
            "乳液",
            "面霜",
            "面膜",
            "化妝水",
            "洗面",
            "防曬",
            "美容"
        ],

        "3C": [
            "手機",
            "耳機",
            "充電",
            "鍵盤",
            "滑鼠",
            "電腦",
            "平板",
            "喇叭",
            "usb"
        ],

        "居家": [
            "家用",
            "收納",
            "清潔",
            "床",
            "枕頭",
            "棉被",
            "廚房",
            "鍋",
            "居家"
        ],

        "服飾": [
            "衣服",
            "上衣",
            "褲",
            "外套",
            "鞋",
            "襪",
            "包包",
            "帽"
        ],

        "食品": [
            "食品",
            "零食",
            "餅乾",
            "茶",
            "咖啡",
            "飲品",
            "果乾"
        ],

        "汽機車": [
            "汽車",
            "機車",
            "車用",
            "安全帽",
            "手把",
            "雨衣"
        ]

    }

    for category, keywords in categories.items():

        for keyword in keywords:

            if keyword in text:

                return category

    return "其他"


# =========================================================
# 本機商品分析
# =========================================================

def local_product_analysis(
    product_name,
    category,
    price,
    selling_points
):

    detected = detect_product_category(
        product_name
        + " "
        + selling_points
    )

    if category == "自動判斷":

        category = detected

    selling_list = [

        x.strip()

        for x in re.split(
            r"[,，、\n]+",
            selling_points
        )

        if x.strip()

    ]

    if not selling_list:

        selling_list = [
            "高質感設計",
            "實用方便",
            "適合日常使用"
        ]

    price_text = (

        f"NT$ {price:,.0f}"

        if price > 0

        else "價格待補"

    )

    result = f"""
# 📦 商品分析結果

## 商品

{product_name or "未輸入商品名稱"}

## 商品分類

{category}

## 價格

{price_text}

## 核心賣點
"""

    for item in selling_list[:8]:

        result += (
            f"- {item}\n"
        )

    result += f"""
## 🎯 建議銷售定位

此商品可採用「{category}」類型內容進行包裝。

建議強調：

1. 商品外觀與質感
2. 實際使用情境
3. 商品特色
4. 使用便利性
5. 消費者購買理由

## 🛒 蝦皮主圖方向

- 商品置中
- 保持商品原始外觀
- 背景乾淨
- 商品清楚
- 高質感商業攝影
- 避免不必要人物
- 避免浮水印
- 避免多餘品牌修改
"""

    return result.strip()


# =========================================================
# Gemini 商品分析 Prompt
# =========================================================

def build_gemini_product_prompt(
    product_name,
    category,
    price,
    selling_points
):

    return f"""
你是「AI 蝦皮半自動化 2.5 PRO」商品分析助手。

請協助分析以下商品。

商品名稱：
{product_name}

商品分類：
{category}

商品價格：
NT$ {price:,.0f}

使用者提供的賣點：
{selling_points}

請輸出繁體中文。

請依照以下結構：

# 📦 Gemini AI 商品分析

## 1. 商品辨識
判斷商品可能是什麼，以及主要用途。

## 2. 商品分類
如果分類不正確，請提出你判斷的分類。

## 3. 核心賣點
整理最值得銷售的 5～8 個賣點。

## 4. 消費者痛點
列出消費者可能遇到的問題。

## 5. 購買理由
說明為什麼消費者可能購買。

## 6. 蝦皮標題建議
提供 3 個適合蝦皮的商品標題。

## 7. 蝦皮主圖方向
提供適合商品主圖的視覺方向。

## 8. 短影音方向
提供適合 9:16 短影音的拍攝方向。

## 9. 注意事項
不要虛構產品功能、醫療功效、認證、成分或不存在的規格。
"""


# =========================================================
# Gemini 商品圖片分析 Prompt
# =========================================================

def build_image_analysis_prompt():

    return """
你是電商商品圖片分析專家。

請分析這張商品圖片。

請用繁體中文回答。

請依照以下格式：

# 🖼️ Gemini AI 商品圖片分析

## 1. 商品辨識
說明圖片中最主要的商品。

## 2. 商品分類
判斷商品可能屬於：
保養品、3C、居家、服飾、食品、汽機車或其他。

## 3. 商品外觀
描述顏色、形狀、材質、包裝與視覺特色。

## 4. 商品文字
如果圖片上有文字，盡可能辨識。
不確定的文字請標示「可能」。

## 5. 品牌
如果可以辨識品牌，請說明。
如果無法確認，請寫「無法確認」。

## 6. 電商主圖建議
提供蝦皮主圖的構圖、背景、光線與拍攝方向。

## 7. 即夢 2.5 影片方向
提供 9:16 商品短影音方向。

## 8. AI 誤判保護
如果圖片有多個物體，請指出哪一個最適合作為主要商品。

重要：
不要虛構圖片中不存在的品牌、文字、配件、功能或規格。
"""


# =========================================================
# 即夢 2.5 Prompt
# =========================================================

def generate_seedance_prompt(
    product_name,
    category,
    selling_points,
    style,
    duration
):

    if not product_name.strip():

        product_name = "商品"

    if category == "自動判斷":

        category = detect_product_category(
            product_name
            + " "
            + selling_points
        )

    prompt = f"""
【即夢 2.5 商品影片指令】

主體：

以「{product_name}」作為唯一主要商品主體。

商品分類：

{category}

核心要求：

保持商品原始外觀、
原始比例、
原始材質、
原始顏色、
原始包裝、
品牌識別與商品文字。

影片比例：

9:16 垂直短影音。

影片長度：

約 {duration} 秒。

影片風格：

{style}

畫面設計：

高質感商業產品攝影。
商品清楚置中。
鏡頭穩定。
自然高級光線。
背景乾淨。
電商廣告質感。

內容節奏：

第一段：
快速建立商品視覺焦點。

第二段：
展示商品細節、材質、外觀與特色。

第三段：
展示商品使用情境與主要賣點。

第四段：
以商品主體作為結尾畫面。

商品賣點：

{selling_points}

AI 誤判保護：

如果輸入圖片中存在多個物體，
優先選擇最大、
最清楚、
最具品牌識別性的商品
作為主要主體。

禁止：

不要任意修改商品外觀。
不要改變商品品牌。
不要改變商品文字。
不要增加不存在的產品配件。
不要加入無關人物。
不要加入浮水印。
不要加入平台 Logo。
不要加入錯誤文字。
不要讓商品變形。
不要讓商品數量突然增加。

品質：

高細節。
高解析度。
自然光影。
真實材質。
商業廣告質感。
流暢鏡頭。
乾淨構圖。
9:16 直式短影音。
"""

    return prompt.strip()


# =========================================================
# Gemini 生成即夢 Prompt
# =========================================================

def generate_gemini_seedance_prompt(
    product_name,
    category,
    selling_points,
    style,
    duration
):

    prompt = f"""
你是「即夢 2.5 電商短影音 Prompt 專家」。

請根據商品資料，製作一份可以直接複製到即夢使用的繁體中文商品影片指令。

商品名稱：
{product_name}

商品分類：
{category}

商品賣點：
{selling_points}

影片風格：
{style}

影片長度：
{duration} 秒

必須包含：

1. 商品主體
2. 商品原始外觀保護
3. 9:16 垂直短影音
4. 鏡頭運動
5. 光線
6. 場景
7. 商品細節
8. 使用情境
9. 電商廣告節奏
10. AI 誤判保護
11. 禁止商品變形
12. 禁止錯誤文字
13. 禁止增加不存在配件
14. 禁止浮水印
15. 禁止平台 Logo

最重要：

商品必須保持原始外觀、比例、顏色、材質、包裝與品牌識別。

不要虛構商品不存在的功能。

最後只輸出完整 Prompt，不要額外解釋。
"""

    result, error = gemini_text(
        prompt
    )

    if error:

        return (
            generate_seedance_prompt(
                product_name,
                category,
                selling_points,
                style,
                duration
            ),
            "Gemini 暫時不可用，已改用本機 Prompt 模板。"
        )

    return result, ""


# =========================================================
# 蝦皮商品文案
# =========================================================

def generate_shopee_copy_local(
    product_name,
    category,
    selling_points,
    price
):

    points = [

        x.strip()

        for x in re.split(
            r"[,，、\n]+",
            selling_points
        )

        if x.strip()

    ]

    if not points:

        points = [
            "高質感設計",
            "實用方便",
            "適合日常使用"
        ]

    point_text = "\n".join(
        [
            f"✅ {item}"
            for item in points[:6]
        ]
    )

    price_text = (

        f"NT$ {price:,.0f}"

        if price > 0

        else "價格請見賣場"

    )

    copy = f"""
【{product_name}】

✨ 商品分類：
{category}

🔥 商品特色

{point_text}

💰 商品價格

{price_text}

📌 商品介紹

精選「{product_name}」，
以實用性、質感與日常使用體驗為主要訴求。

無論自己使用，
或作為送禮選擇，
都能展現商品本身特色。

🛒 購買前提醒

・下單前請確認商品規格
・不同螢幕可能產生些微色差
・實際商品以收到的商品為準

#蝦皮購物 #{category} #好物推薦 #生活好物 #熱門商品
"""

    return copy.strip()


# =========================================================
# Gemini 蝦皮文案
# =========================================================

def generate_shopee_copy_gemini(
    product_name,
    category,
    selling_points,
    price
):

    prompt = f"""
你是蝦皮電商文案專家。

請為以下商品製作繁體中文蝦皮商品文案。

商品名稱：
{product_name}

商品分類：
{category}

商品價格：
NT$ {price:,.0f}

商品賣點：
{selling_points}

請輸出：

【商品標題】

提供 3 個蝦皮商品標題。

【商品賣點】

整理 5～8 個重點。

【商品介紹】

寫一篇適合蝦皮商品頁的介紹。

【使用情境】

提供 3 個實際使用情境。

【購買理由】

提供 3～5 個購買理由。

【Hashtag】

提供適合的標籤。

規則：

不要虛構商品不存在的功能。
不要虛構醫療功效。
不要虛構認證。
不要虛構規格。
不要做不實保證。

整體語氣：
專業、清楚、有銷售力，但不要過度誇張。
"""

    result, error = gemini_text(
        prompt
    )

    if error:

        return (
            generate_shopee_copy_local(
                product_name,
                category,
                selling_points,
                price
            ),
            "Gemini 暫時不可用，已改用本機文案模板。"
        )

    return result, ""


# =========================================================
# 圖片處理
# =========================================================

def process_image(
    uploaded_file
):

    try:

        image = Image.open(
            uploaded_file
        )

        image = ImageOps.exif_transpose(
            image
        )

        image = image.convert(
            "RGB"
        )

        width, height = image.size

        if max(
            width,
            height
        ) > MAX_IMAGE_SIZE:

            ratio = (
                MAX_IMAGE_SIZE
                / max(
                    width,
                    height
                )
            )

            new_size = (

                int(
                    width * ratio
                ),

                int(
                    height * ratio
                )

            )

            image = image.resize(
                new_size,
                Image.LANCZOS
            )

        return image

    except Exception:

        return None


# =========================================================
# 首頁
# =========================================================

def home_page():

    st.markdown(
        '<div class="main-title">'
        '🛒 AI 蝦皮半自動化 2.5 PRO'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f'<div class="main-subtitle">'
        f'歡迎回來，{member_name}'
        f'</div>',
        unsafe_allow_html=True
    )

    st.divider()

    col1, col2, col3, col4 = st.columns(
        4
    )

    with col1:

        st.metric(
            "會員狀態",
            "正常"
        )

    with col2:

        st.metric(
            "剩餘天數",
            f"{remaining_days} 天"
        )

    with col3:

        st.metric(
            "AI",
            "Gemini"
        )

    with col4:

        st.metric(
            "模型",
            GEMINI_MODEL
        )

    st.divider()

    st.subheader(
        "🚀 系統功能"
    )

    c1, c2 = st.columns(
        2
    )

    with c1:

        st.info(
            """
📦 **商品分析**

使用 Gemini AI 分析商品資訊，
建立商品定位與蝦皮銷售方向。
"""
        )

        st.info(
            """
🖼️ **商品圖片**

上傳商品圖片，
讓 Gemini AI 直接分析圖片中的商品。
"""
        )

    with c2:

        st.info(
            """
🎬 **即夢 2.5**

Gemini AI 協助建立
9:16 商品短影音 Prompt。
"""
        )

        st.info(
            """
✍️ **蝦皮商品文案**

使用 Gemini AI
建立商品標題、賣點與商品介紹。
"""
        )


# =========================================================
# 商品分析頁
# =========================================================

def product_analysis_page():

    st.title(
        "📦 Gemini AI 商品分析"
    )

    st.caption(
        "使用 Gemini API 分析商品資料。"
    )

    product_name = st.text_input(
        "商品名稱",
        placeholder="例如：高級保濕精華液"
    )

    category = st.selectbox(
        "商品分類",
        [
            "自動判斷",
            "保養品",
            "3C",
            "居家",
            "服飾",
            "食品",
            "汽機車",
            "其他"
        ]
    )

    price = st.number_input(
        "商品價格",
        min_value=0,
        value=999,
        step=10
    )

    selling_points = st.text_area(
        "商品賣點",
        placeholder="例如：天然配方、清爽不黏膩、高質感",
        height=120
    )

    if st.button(
        "🤖 Gemini AI 開始分析",
        type="primary",
        use_container_width=True
    ):

        prompt = build_gemini_product_prompt(
            product_name,
            category,
            price,
            selling_points
        )

        with st.spinner(
            "Gemini 正在分析商品..."
        ):

            result, error = gemini_text(
                prompt
            )

        if error:

            st.warning(
                error
            )

            st.info(
                "目前改用本機規則分析。"
            )

            result = local_product_analysis(
                product_name,
                category,
                price,
                selling_points
            )

        st.session_state.analysis_result = (
            result
        )

    if st.session_state.analysis_result:

        st.divider()

        st.markdown(
            st.session_state.analysis_result
        )

        st.download_button(
            "⬇️ 下載商品分析",
            data=st.session_state.analysis_result,
            file_name="Gemini商品分析.txt",
            mime="text/plain",
            use_container_width=True
        )


# =========================================================
# 商品圖片頁
# =========================================================

def image_page():

    st.title(
        "🖼️ Gemini AI 商品圖片分析"
    )

    st.caption(
        "上傳商品圖片後，可以直接交給 Gemini AI 分析。"
    )

    uploaded_file = st.file_uploader(
        "上傳商品圖片",
        type=[
            "jpg",
            "jpeg",
            "png",
            "webp"
        ]
    )

    if not uploaded_file:

        return

    if uploaded_file.size > (
        MAX_IMAGE_MB
        * 1024
        * 1024
    ):

        st.error(
            f"圖片太大，請使用 {MAX_IMAGE_MB}MB 以下圖片。"
        )

        return

    image = process_image(
        uploaded_file
    )

    if image is None:

        st.error(
            "圖片讀取失敗。"
        )

        return

    col1, col2 = st.columns(
        2
    )

    with col1:

        st.image(
            image,
            caption="商品圖片",
            use_container_width=True
        )

    with col2:

        st.subheader(
            "📐 圖片資訊"
        )

        st.write(
            f"尺寸：{image.width} × {image.height}"
        )

        st.success(
            "圖片已成功載入。"
        )

    st.divider()

    if st.button(
        "🤖 Gemini AI 分析這張商品圖片",
        type="primary",
        use_container_width=True
    ):

        with st.spinner(
            "Gemini 正在讀取商品圖片..."
        ):

            result, error = (
                gemini_image_analysis(
                    image,
                    build_image_analysis_prompt()
                )
            )

        if error:

            st.error(
                error
            )

        else:

            st.session_state.gemini_analysis = (
                result
            )

    if st.session_state.gemini_analysis:

        st.divider()

        st.subheader(
            "🤖 Gemini AI 分析結果"
        )

        st.markdown(
            st.session_state.gemini_analysis
        )

        st.download_button(
            "⬇️ 下載圖片分析",
            data=st.session_state.gemini_analysis,
            file_name="Gemini商品圖片分析.txt",
            mime="text/plain",
            use_container_width=True
        )

    st.divider()

    buffer = io.BytesIO()

    image.save(
        buffer,
        format="JPEG",
        quality=95
    )

    st.download_button(
        "⬇️ 下載處理後圖片",
        data=buffer.getvalue(),
        file_name="product_processed.jpg",
        mime="image/jpeg",
        use_container_width=True
    )


# =========================================================
# 即夢 2.5 頁
# =========================================================

def seedance_page():

    st.title(
        "🎬 Gemini AI × 即夢 2.5"
    )

    st.caption(
        "Gemini AI 協助建立 9:16 商品短影音指令。"
    )

    product_name = st.text_input(
        "商品名稱",
        placeholder="例如：高質感保濕精華"
    )

    category = st.selectbox(
        "商品分類",
        [
            "自動判斷",
            "保養品",
            "3C",
            "居家",
            "服飾",
            "食品",
            "汽機車",
            "其他"
        ],
        key="seedance_category"
    )

    selling_points = st.text_area(
        "商品賣點",
        placeholder="例如：天然配方、清爽、高質感",
        height=120,
        key="seedance_points"
    )

    style = st.selectbox(
        "影片風格",
        [
            "高級商業廣告",
            "電商爆款",
            "極簡高級感",
            "科技感",
            "生活情境",
            "電影級產品展示"
        ]
    )

    duration = st.selectbox(
        "影片長度",
        [
            "5",
            "8",
            "10",
            "15"
        ]
    )

    if st.button(
        "🎬 Gemini 生成即夢 2.5 指令",
        type="primary",
        use_container_width=True
    ):

        with st.spinner(
            "Gemini 正在製作即夢 2.5 Prompt..."
        ):

            prompt, notice = (
                generate_gemini_seedance_prompt(
                    product_name,
                    category,
                    selling_points,
                    style,
                    duration
                )
            )

        if notice:

            st.warning(
                notice
            )

        st.session_state.generated_prompt = (
            prompt
        )

    if st.session_state.generated_prompt:

        st.divider()

        st.subheader(
            "📋 即夢 2.5 指令"
        )

        st.code(
            st.session_state.generated_prompt,
            language="text"
        )

        st.download_button(
            "⬇️ 下載即夢 2.5 指令",
            data=st.session_state.generated_prompt,
            file_name="即夢2.5商品影片指令.txt",
            mime="text/plain",
            use_container_width=True
        )


# =========================================================
# 蝦皮文案頁
# =========================================================

def copy_page():

    st.title(
        "✍️ Gemini AI 蝦皮商品文案"
    )

    product_name = st.text_input(
        "商品名稱",
        placeholder="例如：高級保濕精華"
    )

    category = st.selectbox(
        "商品分類",
        [
            "保養品",
            "3C",
            "居家",
            "服飾",
            "食品",
            "汽機車",
            "其他"
        ],
        key="copy_category"
    )

    price = st.number_input(
        "商品價格",
        min_value=0,
        value=999,
        step=10,
        key="copy_price"
    )

    selling_points = st.text_area(
        "商品賣點",
        placeholder="例如：天然配方、清爽不黏、高質感",
        height=120,
        key="copy_points"
    )

    if st.button(
        "🤖 Gemini 生成蝦皮商品文案",
        type="primary",
        use_container_width=True
    ):

        with st.spinner(
            "Gemini 正在生成商品文案..."
        ):

            copy, notice = (
                generate_shopee_copy_gemini(
                    product_name,
                    category,
                    selling_points,
                    price
                )
            )

        if notice:

            st.warning(
                notice
            )

        st.session_state.generated_copy = (
            copy
        )

    if st.session_state.generated_copy:

        st.divider()

        st.subheader(
            "🛒 商品文案"
        )

        st.text_area(
            "可直接複製",
            value=st.session_state.generated_copy,
            height=450
        )

        st.download_button(
            "⬇️ 下載商品文案",
            data=st.session_state.generated_copy,
            file_name="Gemini蝦皮商品文案.txt",
            mime="text/plain",
            use_container_width=True
        )


# =========================================================
# 會員資料頁
# =========================================================

def member_page():

    st.title(
        "👤 我的會員資料"
    )

    col1, col2 = st.columns(
        2
    )

    with col1:

        st.write(
            f"**姓名：** {member_name}"
        )

        st.write(
            f"**帳號：** {current_username}"
        )

        st.write(
            f"**Email：** {member_email or '未設定'}"
        )

    with col2:

        st.write(
            f"**身份：** {member_role}"
        )

        st.write(
            f"**狀態：** {member_status}"
        )

        st.write(
            f"**到期日：** {member_expires}"
        )

        st.write(
            f"**剩餘天數：** {remaining_days}"
        )


# =========================================================
# 管理員中心
# =========================================================

def admin_page():

    if member_role != "admin":

        st.error(
            "⛔ 你沒有管理員權限。"
        )

        return

    st.title(
        "👑 管理員中心"
    )

    members = load_members()

    st.write(
        f"目前會員數：**{len(members)}**"
    )

    st.divider()

    for member in members:

        username = member.get(
            "username",
            ""
        )

        name = member.get(
            "name",
            ""
        )

        role = member.get(
            "role",
            "member"
        )

        status = member.get(
            "status",
            "active"
        )

        expires = member.get(
            "expires",
            ""
        )

        with st.expander(
            f"👤 {name}｜{username}"
        ):

            st.write(
                f"身份：{role}"
            )

            st.write(
                f"狀態：{status}"
            )

            st.write(
                f"到期日：{expires}"
            )

            if role != "admin":

                c1, c2 = st.columns(
                    2
                )

                with c1:

                    new_status = st.selectbox(
                        "會員狀態",
                        [
                            "active",
                            "disabled"
                        ],
                        index=(
                            0
                            if status == "active"
                            else 1
                        ),
                        key=f"status_{username}"
                    )

                with c2:

                    add_days = st.number_input(
                        "增加天數",
                        min_value=0,
                        value=30,
                        step=1,
                        key=f"days_{username}"
                    )

                if st.button(
                    "💾 更新會員",
                    key=f"update_{username}"
                ):

                    updates = {
                        "status":
                        new_status
                    }

                    if add_days > 0:

                        try:

                            current_expire = (
                                date.fromisoformat(
                                    expires
                                )
                            )

                        except Exception:

                            current_expire = (
                                date.today()
                            )

                        if (
                            current_expire
                            < date.today()
                        ):

                            current_expire = (
                                date.today()
                            )

                        new_expire = (
                            current_expire
                            + timedelta(
                                days=int(
                                    add_days
                                )
                            )
                        ).isoformat()

                        updates[
                            "expires"
                        ] = new_expire

                    update_member(
                        member.get(
                            "id"
                        ),
                        updates
                    )

                    st.success(
                        "會員資料已更新。"
                    )

                    st.rerun()


# =========================================================
# Gemini 設定頁
# =========================================================

def gemini_settings_page():

    st.title(
        "🤖 Gemini API 設定"
    )

    st.info(
        """
這裡只設定 Gemini API Key。

本程式沒有 GPT / ChatGPT API、
WeChat、LINE、Supabase 或 Google OAuth。
"""
    )

    st.subheader(
        "🔑 Gemini API Key"
    )

    api_key = st.text_input(
        "輸入 Gemini API Key",
        type="password",
        value=st.session_state.get(
            "gemini_api_key",
            ""
        ),
        placeholder="貼上你的 Gemini API Key"
    )

    if st.button(
        "💾 儲存 Gemini API Key",
        type="primary",
        use_container_width=True
    ):

        if not api_key.strip():

            st.error(
                "請輸入 Gemini API Key。"
            )

        else:

            st.session_state.gemini_api_key = (
                api_key.strip()
            )

            st.success(
                "Gemini API Key 已暫存在目前工作階段。"
            )

            st.info(
                "重新啟動程式後，若沒有放入 secrets / 環境變數，需要再次輸入。"
            )

    st.divider()

    st.write(
        f"目前模型：**{GEMINI_MODEL}**"
    )

    if st.button(
        "🧪 測試 Gemini API",
        use_container_width=True
    ):

        with st.spinner(
            "測試 Gemini..."
        ):

            result, error = gemini_text(
                "請只回答：Gemini API 測試成功。"
            )

        if error:

            st.error(
                error
            )

        else:

            st.success(
                result
            )


# =========================================================
# 側邊欄
# =========================================================

with st.sidebar:

    st.title(
        "🛒 AI 蝦皮 2.5 PRO"
    )

    st.divider()

    st.write(
        f"👤 **{member_name}**"
    )

    st.caption(
        f"帳號：{current_username}"
    )

    if member_role == "admin":

        st.success(
            "👑 管理員"
        )

    else:

        st.info(
            "👤 一般會員"
        )

    st.write(
        f"📅 到期日：{member_expires}"
    )

    st.write(
        f"⏳ 剩餘：{remaining_days} 天"
    )

    st.divider()

    menu_options = [

        "🏠 系統首頁",

        "📦 Gemini 商品分析",

        "🖼️ Gemini 商品圖片分析",

        "🎬 Gemini × 即夢 2.5",

        "✍️ Gemini 蝦皮商品文案",

        "🤖 Gemini API 設定",

        "👤 我的會員資料"

    ]

    if member_role == "admin":

        menu_options.append(
            "👑 管理員中心"
        )

    menu = st.radio(
        "功能選單",
        menu_options
    )

    st.divider()

    if st.button(
        "🚪 登出系統",
        use_container_width=True
    ):

        logout()


# =========================================================
# 主頁路由
# =========================================================

if menu == "🏠 系統首頁":

    home_page()

elif menu == "📦 Gemini 商品分析":

    product_analysis_page()

elif menu == "🖼️ Gemini 商品圖片分析":

    image_page()

elif menu == "🎬 Gemini × 即夢 2.5":

    seedance_page()

elif menu == "✍️ Gemini 蝦皮商品文案":

    copy_page()

elif menu == "🤖 Gemini API 設定":

    gemini_settings_page()

elif menu == "👤 我的會員資料":

    member_page()

elif menu == "👑 管理員中心":

    admin_page()


# =========================================================
# 頁尾
# =========================================================

st.divider()

st.caption(
    "AI 蝦皮半自動化 2.5 PRO｜Gemini API｜會員系統｜即夢 2.5｜蝦皮商品工具"
)
