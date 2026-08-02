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
# Gemini API 完整版
#
# 保留：
# 會員註冊 / 登入 / 期限 / 管理員
# 商品圖片上傳
# Gemini AI 商品圖片分析
# AI 選品
# 蝦皮文案
# TikTok 文案
# 即夢 AI 2.5 生圖 Prompt
# 即夢 AI 2.5 影片 Prompt
# 即夢 AI 2.5 爆款帶貨影片
# 分潤合規檢查
# 完整流程
#
# Gemini API Key：
# Streamlit Secrets:
#
# GEMINI_API_KEY = "你的 Gemini API Key"
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

MEMBERS_FILE = os.path.join(
    DATA_DIR,
    "members.json"
)

MAX_IMAGE_SIZE = 1600
MAX_IMAGE_MB = 20

DEFAULT_MEMBER_DAYS = 30

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# Gemini 文字 / 圖片理解模型
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

        api_key = st.secrets.get(
            "GEMINI_API_KEY",
            ""
        )

    except Exception:

        api_key = ""

    if not api_key:

        return None

    try:

        from google import genai

        return genai.Client(
            api_key=api_key
        )

    except Exception:

        return None


def gemini_available():

    client = get_gemini_client()

    return client is not None


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

    salt = secrets.token_hex(16)

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


if "analysis_mode" not in st.session_state:

    st.session_state.analysis_mode = ""


if "gemini_error" not in st.session_state:

    st.session_state.gemini_error = ""


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

    st.session_state.analysis_mode = ""

    st.session_state.gemini_error = ""

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

    .result-box {
        padding: 20px;
        border-radius: 14px;
        border: 1px solid rgba(128,128,128,.25);
        margin-bottom: 20px;
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
        '會員登入｜Gemini AI｜商品分析｜即夢 AI 2.5'
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
                        username.strip().lower()
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
            "本系統使用本機會員帳號＋密碼登入。"
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


if remaining_days < 0:

    st.error(
        "⛔ 會員資格已到期。"
    )

    if st.button(
        "🚪 返回登入"
    ):

        logout()

    st.stop()


# =========================================================
# 側邊欄
# =========================================================

with st.sidebar:

    st.markdown(
        "## 👤 會員中心"
    )

    st.success(
        f"會員：{member_name}"
    )

    st.write(
        f"帳號：**{current_username}**"
    )

    if member_email:

        st.write(
            f"Email：**{member_email}**"
        )

    st.write(
        f"等級：**{member_role}**"
    )

    st.write(
        "AI：**Gemini API**"
    )

    st.write(
        f"到期日：**{member_expires}**"
    )

    if remaining_days == 0:

        st.warning(
            "⚠️ 今天為最後使用日"
        )

    elif remaining_days <= 7:

        st.warning(
            f"⚠️ 剩餘 {remaining_days} 天"
        )

    else:

        st.info(
            f"⏳ 剩餘 {remaining_days} 天"
        )

    st.divider()

    if st.button(
        "🚪 登出",
        use_container_width=True
    ):

        logout()


# =========================================================
# 管理員中心
# =========================================================

def admin_panel():

    st.header(
        "👑 管理員中心"
    )

    members = load_members()

    st.write(
        f"目前會員數：**{len(members)}**"
    )

    for member in members:

        mid = member.get(
            "id",
            ""
        )

        username = member.get(
            "username",
            ""
        )

        name = member.get(
            "name",
            ""
        )

        email = member.get(
            "email",
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
                f"Email：**{email}**"
            )

            st.write(
                f"身份：**{role}**"
            )

            st.write(
                f"狀態：**{status}**"
            )

            st.write(
                f"到期：**{expires}**"
            )

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
                key=f"status_{mid}"
            )

            roles = [
                "member",
                "vip",
                "admin"
            ]

            new_role = st.selectbox(
                "會員等級",
                roles,
                index=(
                    roles.index(role)
                    if role in roles
                    else 0
                ),
                key=f"role_{mid}"
            )

            try:

                expire_value = date.fromisoformat(
                    expires
                )

            except Exception:

                expire_value = date.today()

            new_expire = st.date_input(
                "會員到期日",
                value=expire_value,
                key=f"expire_{mid}"
            )

            c1, c2, c3 = st.columns(3)

            with c1:

                if st.button(
                    "💾 儲存",
                    key=f"save_{mid}",
                    use_container_width=True
                ):

                    update_member(
                        mid,
                        {
                            "status":
                            new_status,

                            "role":
                            new_role,

                            "expires":
                            new_expire.isoformat()
                        }
                    )

                    st.success(
                        "已更新。"
                    )

                    st.rerun()

            with c2:

                if st.button(
                    "➕ 延長 30 天",
                    key=f"extend_{mid}",
                    use_container_width=True
                ):

                    try:

                        d = date.fromisoformat(
                            expires
                        )

                    except Exception:

                        d = date.today()

                    if d < date.today():

                        d = date.today()

                    new_date = (
                        d
                        + timedelta(
                            days=30
                        )
                    )

                    update_member(
                        mid,
                        {
                            "expires":
                            new_date.isoformat(),

                            "status":
                            "active"
                        }
                    )

                    st.success(
                        "已延長至 "
                        f"{new_date.isoformat()}"
                    )

                    st.rerun()

            with c3:

                if (
                    username
                    != current_username
                ):

                    if st.button(
                        "⛔ 停權",
                        key=f"disable_{mid}",
                        use_container_width=True
                    ):

                        update_member(
                            mid,
                            {
                                "status":
                                "disabled"
                            }
                        )

                        st.warning(
                            "會員已停權。"
                        )

                        st.rerun()


# =========================================================
# 主標題
# =========================================================

st.markdown(
    '<div class="main-title">'
    '🛒 AI 蝦皮半自動化 2.5 PRO'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="main-subtitle">'
    'Gemini AI 商品辨識｜AI 選品｜蝦皮文案｜TikTok｜'
    '即夢 AI 2.5｜分潤合規'
    '</div>',
    unsafe_allow_html=True
)


# =========================================================
# Gemini 狀態
# =========================================================

gemini_client = get_gemini_client()

if gemini_client:

    st.success(
        "🟢 Gemini API 已連線"
    )

else:

    st.warning(
        "🟡 尚未讀取到 GEMINI_API_KEY。"
        "請到 Streamlit Secrets 設定。"
    )


# =========================================================
# 管理員
# =========================================================

if (
    member_role.lower()
    == "admin"
):

    with st.expander(
        "👑 管理員中心"
    ):

        admin_panel()

    st.divider()


# =========================================================
# 圖片處理
# =========================================================

def prepare_image(
    uploaded_file
):

    if uploaded_file is None:

        raise ValueError(
            "沒有收到圖片檔案。"
        )

    try:

        raw_bytes = (
            uploaded_file.getvalue()
        )

        if not raw_bytes:

            raise ValueError(
                "圖片檔案內容是空的。"
            )

        file_size_mb = (
            len(raw_bytes)
            / 1024
            / 1024
        )

        if file_size_mb > MAX_IMAGE_MB:

            raise ValueError(
                f"圖片太大，目前為 "
                f"{file_size_mb:.1f} MB，"
                f"請使用 {MAX_IMAGE_MB} MB 以下圖片。"
            )

        image = Image.open(
            io.BytesIO(
                raw_bytes
            )
        )

        image = ImageOps.exif_transpose(
            image
        )

        image.load()

        if image.mode not in (
            "RGB",
            "RGBA"
        ):

            image = image.convert(
                "RGB"
            )

        image.thumbnail(
            (
                MAX_IMAGE_SIZE,
                MAX_IMAGE_SIZE
            ),
            Image.Resampling.LANCZOS
        )

        if image.mode == "RGBA":

            background = Image.new(
                "RGB",
                image.size,
                "white"
            )

            background.paste(
                image,
                mask=image.getchannel(
                    "A"
                )
            )

            image = background

        else:

            image = image.convert(
                "RGB"
            )

        return image

    except Exception as error:

        raise ValueError(
            "無法讀取這張圖片。"
            "請確認是 JPG、JPEG、PNG 或 WEBP。"
            f"\n\n詳細錯誤：{error}"
        )


# =========================================================
# Gemini 核心規則
# =========================================================

JIMENG_25_CORE_RULES = """
【即夢 AI 2.5 商品一致性核心規則】

使用者上傳的商品圖片是主要商品來源。

必須維持：

- 商品原本品牌
- 包裝
- 形狀
- 比例
- 顏色
- 材質
- Logo
- 標籤
- 印刷文字
- 包裝結構

禁止：

- 重新設計品牌
- 重新設計包裝
- 改變顏色
- 改變瓶身或盒身
- 改變 Logo
- 改變文字
- 商品變形
- 商品融化
- 商品閃爍
- 商品漂移
- 商品突然變成其他商品
- 多出第二個商品
- 商品消失

預設禁止：

- 人物
- 手
- 主持人
- 代言人
- 模特兒
- 人物拿商品
- 人物遮擋商品

禁止：

- 浮水印
- 假價格
- 假贈品
- 假優惠
- 假認證
- 未確認規格
- 未確認功效
- 未確認成分
- 未確認產地

不得自行創造未確認商品資訊。

影片全程保持同一商品身份。

推薦：

slow cinematic push-in,
subtle orbit movement,
smooth camera movement,
stable framing.
"""


# =========================================================
# Gemini Prompt 建立
# =========================================================

def build_gemini_prompt(
    product_data,
    selected_items
):

    name = (
        product_data["商品名稱"]
        or "待確認商品"
    )

    price = (
        product_data["商品價格"]
        or "待確認"
    )

    cost = (
        product_data["商品成本"]
        or "待確認"
    )

    commission = (
        product_data["分潤比例"]
        or "待確認"
    )

    sales = (
        product_data["月銷量"]
        or "待確認"
    )

    rating = (
        product_data["商品評分"]
        or "待確認"
    )

    url = (
        product_data["商品連結"]
        or "待確認"
    )

    spec = (
        product_data["商品規格"]
        or "待確認"
    )

    platform = (
        product_data["目標平台"]
        or "蝦皮"
    )

    selected_text = "、".join(
        selected_items
    )

    prompt = f"""
你現在是「AI 蝦皮半自動化 2.5 PRO」的核心電商 AI。

你會收到：
1. 一張使用者上傳的商品圖片。
2. 使用者輸入的商品資料。
3. 使用者選擇的 AI 功能。

你的第一任務是分析圖片中真正可確認的商品資訊。

【重要圖片辨識規則】

如果圖片中有多個物件：
- 優先選擇畫面最大、最清楚、最具有品牌辨識度的商品作為主商品。
- 不要把背景物件誤認成商品。
- 如果圖片資訊不足，必須明確寫「待人工確認」。
- 不可以憑空創造品牌、容量、成分、產地、功效、價格、規格。
- 圖片看不到的資料，不准假裝看得到。

【商品資料】

商品名稱：{name}
商品價格：{price}
商品成本：{cost}
分潤比例：{commission}
月銷量：{sales}
商品評分：{rating}
商品連結：{url}
商品規格：{spec}
目標平台：{platform}

【使用者要求功能】

{selected_text}

{JIMENG_25_CORE_RULES}

==================================================
輸出要求
==================================================

請用繁體中文輸出。

不要只給簡短答案。

請依照以下結構完整輸出：

# 🛒 AI 蝦皮半自動化 2.5 PRO

## 一、商品 AI 辨識

請分析：

- 商品名稱
- 商品類型
- 品牌
- 商品外觀
- 包裝
- 顏色
- 材質
- 規格
- 圖片中可讀取文字
- Logo
- 商品主要賣點
- 圖片可以確認的資訊
- 無法確認的資訊

如果不能確認，寫：
「待人工確認」

## 二、AI 選品分析

分析：

- 商品市場吸引力
- 電商內容潛力
- 視覺展示潛力
- 短影音潛力
- 蝦皮銷售內容潛力
- 競爭程度
- 合規風險
- 商品資料完整度
- 推薦分數 0～100
- 推薦等級
- 原因
- 建議

不要假裝有即時市場資料。
沒有提供的資料要標記待確認。

## 三、蝦皮上架文案

請完整產生：

### 商品標題 5 組

### 短描述

### 完整商品描述

### 商品特色

### 使用方式

### 保存方式

### 注意事項

### 搜尋關鍵字

### 賣點整理

### CTA

不得自行創造未確認功效。

## 四、TikTok 文案

請產生：

### 3 秒開場 Hook

### 15 秒腳本

### 30 秒腳本

### 45 秒腳本

### TikTok 貼文

### Hashtag

### CTA

內容以商品實際可確認資訊為主。

## 五、即夢 AI 2.5 生圖指令

請產生：

### A｜1:1 蝦皮商品主圖 Prompt

英文 Prompt。

要求：
- 商品置中
- 高級商業攝影
- 商品原貌保持一致
- 原始包裝保持一致
- 原始 Logo 保持一致
- 原始文字保持一致
- 不重新設計商品
- 不加入人物
- 不加入手
- 不加入代言人
- 不加入浮水印

### B｜9:16 TikTok 商品海報 Prompt

英文 Prompt。

### C｜商品細節展示 Prompt

英文 Prompt。

### Negative Prompt

統一產生完整 Negative Prompt。

## 六、即夢 AI 2.5 影片指令

請產生完整 9:16 英文 Prompt。

需要：

Scene 1 — Opening
Scene 2 — Product Detail
Scene 3 — Camera Motion
Scene 4 — Ending

要求：

- 商品全程一致
- 商品不變形
- 商品包裝不變
- Logo 不變
- 文字不亂變
- 顏色不變
- 不突然增加第二個商品
- 不讓商品消失
- 不加入人物
- 不加入手
- 不加入主持人
- 不加入代言人

推薦：

slow cinematic push-in
subtle orbit movement
smooth camera movement
stable framing

## 七、即夢 AI 2.5 爆款帶貨影片

請產生 15 秒 9:16 爆款帶貨影片 Prompt。

結構：

0–3 秒：
強力第一視覺。

3–7 秒：
商品細節。

7–12 秒：
高級鏡頭運動。

12–15 秒：
商品穩定收尾。

必須維持商品原貌。

再產生：

### Negative Prompt

## 八、蝦皮分潤合規檢查

請檢查：

- 商品與圖片是否一致
- 商品與影片是否一致
- 商品與文案是否一致
- 商品連結是否存在
- 分潤比例是否已確認
- 是否有未確認功效
- 是否有誇大宣稱
- 是否有虛假價格
- 是否有虛假贈品
- 是否有虛假折扣
- 是否有未確認認證
- 是否存在商品資訊不足

最後給：

「可直接使用」
或
「修改後發布」
或
「暫停發布」

並說明原因。

## 九、最終人工確認

列出發布前必須確認：

- 商品名稱
- 品牌
- 價格
- 規格
- 容量
- 成分
- 產地
- 功效
- 保存期限
- 庫存
- 商品連結
- 分潤資格
- 平台規則

==================================================
非常重要
==================================================

你是 AI 分析助手，不要把「推測」當成事實。

看不到就寫：
「待人工確認」。

不要自行捏造商品資料。

商品圖片才是商品外觀的主要依據。

輸出要實際、完整、可以直接拿去整理成電商工作流程。
"""

    return prompt


# =========================================================
# Gemini AI 執行
# =========================================================

def run_gemini_analysis(
    product_data,
    selected_items,
    image
):

    client = get_gemini_client()

    if client is None:

        raise RuntimeError(
            "Gemini API 尚未設定。\n\n"
            "請確認 Streamlit Secrets 有：\n\n"
            "GEMINI_API_KEY = \"你的 API Key\""
        )

    prompt = build_gemini_prompt(
        product_data,
        selected_items
    )

    try:

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                prompt,
                image
            ]
        )

        text = getattr(
            response,
            "text",
            None
        )

        if text:

            return text.strip()

        # 某些版本 SDK 如果 text 屬性沒有直接回傳，
        # 嘗試從 candidates 取得
        candidates = getattr(
            response,
            "candidates",
            None
        )

        if candidates:

            parts = []

            for candidate in candidates:

                content = getattr(
                    candidate,
                    "content",
                    None
                )

                if not content:
                    continue

                candidate_parts = getattr(
                    content,
                    "parts",
                    []
                )

                for part in candidate_parts:

                    part_text = getattr(
                        part,
                        "text",
                        None
                    )

                    if part_text:

                        parts.append(
                            part_text
                        )

            if parts:

                return "\n".join(
                    parts
                ).strip()

        raise RuntimeError(
            "Gemini 沒有返回可讀取的文字結果。"
        )

    except Exception as error:

        error_text = str(error)

        raise RuntimeError(
            "Gemini API 呼叫失敗。\n\n"
            f"詳細錯誤：{error_text}"
        )


# =========================================================
# 商品圖片
# =========================================================

st.subheader(
    "1｜📷 上傳商品圖片"
)

uploaded_file = st.file_uploader(
    "請選擇商品圖片",
    type=[
        "jpg",
        "jpeg",
        "png",
        "webp"
    ],
    accept_multiple_files=False,
    key="product_image_uploader",
    help=(
        "支援 JPG、JPEG、PNG、WEBP。"
        "建議使用清楚的商品正面照片。"
    )
)

prepared_image = None

if uploaded_file is not None:

    try:

        prepared_image = prepare_image(
            uploaded_file
        )

        st.success(
            f"✅ 圖片已成功上傳："
            f"{uploaded_file.name}"
        )

        st.image(
            prepared_image,
            caption="已讀取商品圖片",
            use_container_width=True
        )

    except Exception as error:

        st.error(
            "❌ 圖片讀取失敗。"
        )

        st.code(
            str(error)
        )


# =========================================================
# 商品資料
# =========================================================

st.subheader(
    "2｜📦 商品資料"
)

col1, col2 = st.columns(2)

with col1:

    product_name = st.text_input(
        "商品名稱",
        placeholder="不知道可留空",
        key="product_name"
    )

    product_price = st.text_input(
        "商品價格",
        placeholder="例如：399",
        key="product_price"
    )

    product_cost = st.text_input(
        "商品成本",
        placeholder="例如：250",
        key="product_cost"
    )

    commission_rate = st.text_input(
        "分潤比例",
        placeholder="例如：12%",
        key="commission_rate"
    )

with col2:

    monthly_sales = st.text_input(
        "月銷量",
        placeholder="例如：1500",
        key="monthly_sales"
    )

    product_rating = st.text_input(
        "商品評分",
        placeholder="例如：4.8",
        key="product_rating"
    )

    product_url = st.text_input(
        "商品連結",
        placeholder="可留空",
        key="product_url"
    )

    product_spec = st.text_area(
        "商品規格",
        placeholder="例如：300ml、單瓶、白色",
        height=130,
        key="product_spec"
    )


# =========================================================
# 平台
# =========================================================

st.subheader(
    "3｜🎯 目標平台"
)

target_platform = st.radio(
    "目標平台",
    [
        "蝦皮",
        "TikTok",
        "蝦皮＋TikTok"
    ],
    horizontal=True,
    key="target_platform"
)


# =========================================================
# AI 功能
# =========================================================

st.subheader(
    "4｜🤖 Gemini AI 功能"
)

generate_options = [

    "商品辨識",

    "AI 選品分析",

    "蝦皮上架文案",

    "TikTok 文案",

    "即夢 AI 2.5 生圖指令",

    "即夢 AI 2.5 影片指令",

    "即夢 AI 2.5 爆款帶貨影片",

    "分潤合規檢查",

    "完整流程"

]

selected_items = st.multiselect(
    "選擇需要的功能",
    options=generate_options,
    default=["完整流程"],
    key="selected_ai_features"
)

if (
    "完整流程" in selected_items
    and len(selected_items) > 1
):

    st.info(
        "ℹ️ 已選擇完整流程，"
        "Gemini 會依完整工作流程產生結果。"
    )


# =========================================================
# 啟動
# =========================================================

st.subheader(
    "5｜🚀 開始 Gemini AI 分析"
)

if st.button(
    "🚀 啟動 Gemini AI 蝦皮半自動化 2.5",
    type="primary",
    use_container_width=True,
    key="start_ai_analysis"
):

    if prepared_image is None:

        st.error(
            "❌ 請先上傳商品圖片。"
        )

    elif not selected_items:

        st.error(
            "❌ 請至少選擇一個 AI 功能。"
        )

    elif not gemini_available():

        st.error(
            "❌ Gemini API 尚未設定。"
        )

        st.info(
            "請在 Streamlit Secrets 加入："
        )

        st.code(
            'GEMINI_API_KEY = "你的 Gemini API Key"'
        )

    else:

        product_data = {

            "商品名稱":
            product_name,

            "商品價格":
            product_price,

            "商品成本":
            product_cost,

            "分潤比例":
            commission_rate,

            "月銷量":
            monthly_sales,

            "商品評分":
            product_rating,

            "商品連結":
            product_url,

            "商品規格":
            product_spec,

            "目標平台":
            target_platform

        }

        effective_items = (

            ["完整流程"]

            if "完整流程"
            in selected_items

            else selected_items
        )

        with st.spinner(
            "🧠 Gemini 正在讀取商品圖片並建立 "
            "AI 商品分析、選品、蝦皮文案、TikTok、"
            "即夢 AI 2.5 Prompt……"
        ):

            try:

                result = run_gemini_analysis(
                    product_data,
                    effective_items,
                    prepared_image
                )

                st.session_state.analysis_result = (
                    result
                )

                st.session_state.analysis_mode = (
                    f"Gemini API｜{GEMINI_MODEL}"
                )

                st.session_state.gemini_error = ""

                st.success(
                    "🎉 Gemini AI 分析完成！"
                )

            except Exception as error:

                st.session_state.analysis_result = ""

                st.session_state.analysis_mode = ""

                st.session_state.gemini_error = (
                    str(error)
                )

                st.error(
                    "❌ Gemini AI 分析失敗。"
                )

                st.code(
                    str(error)
                )


# =========================================================
# Gemini 錯誤
# =========================================================

if st.session_state.gemini_error:

    st.warning(
        "上一次 Gemini 執行發生錯誤："
    )

    st.code(
        st.session_state.gemini_error
    )


# =========================================================
# AI 結果
# =========================================================

if st.session_state.analysis_result:

    st.divider()

    st.subheader(
        "6｜📊 Gemini AI 分析結果"
    )

    st.caption(
        "模式："
        f"{st.session_state.analysis_mode}"
    )

    st.markdown(
        '<div class="result-box">',
        unsafe_allow_html=True
    )

    st.markdown(
        st.session_state.analysis_result
    )

    st.markdown(
        "</div>",
        unsafe_allow_html=True
    )

    st.subheader(
        "7｜📋 完整結果"
    )

    st.text_area(
        "完整 Gemini AI 結果",
        value=st.session_state.analysis_result,
        height=700,
        key="full_ai_result"
    )

    current_time = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    safe_product_name = (
        product_name.strip()
        if product_name.strip()
        else "商品分析"
    )

    safe_product_name = re.sub(
        r'[\\/:*?"<>|]+',
        "_",
        safe_product_name
    )

    file_name = (
        "AI蝦皮半自動化2.5_Gemini_"
        f"{safe_product_name}_"
        f"{current_time}.txt"
    )

    st.download_button(
        "⬇️ 下載完整 Gemini AI 結果",
        data=(
            st.session_state.analysis_result
            .encode("utf-8")
        ),
        file_name=file_name,
        mime="text/plain",
        use_container_width=True,
        key="download_ai_result"
    )

    st.warning(
        "正式發布前，請人工確認："
        "商品名稱、品牌、容量、產地、"
        "成分、保存期限、貨源、售價、"
        "庫存、組合數、商品規格及分潤資格。"
    )


# =========================================================
# 系統設定狀態
# =========================================================

with st.expander(
    "⚙️ 系統設定"
):

    if gemini_available():

        st.success(
            "🟢 Gemini API 已連線"
        )

    else:

        st.error(
            "🔴 Gemini API 尚未設定"
        )

    st.success(
        "✅ 本機會員系統"
    )

    st.success(
        "✅ members.json"
    )

    st.success(
        "✅ 商品圖片上傳"
    )

    st.success(
        f"✅ Gemini AI：{GEMINI_MODEL}"
    )

    st.success(
        "✅ Gemini 商品圖片理解"
    )

    st.success(
        "✅ AI 選品分析"
    )

    st.success(
        "✅ 蝦皮上架文案"
    )

    st.success(
        "✅ TikTok 文案"
    )

    st.success(
        "✅ 即夢 AI 2.5 Prompt"
    )

    st.success(
        "✅ 分潤合規檢查"
    )

    st.success(
        "✅ 完整流程"
    )

    st.info(
        "本版本 AI 分析會實際呼叫 Gemini API，"
        "不是本機關鍵字規則產生器。"
    )


# =========================================================
# 頁尾
# =========================================================

st.divider()

st.caption(
    "AI 蝦皮半自動化 2.5 PRO｜"
    "Gemini API｜"
    "會員系統｜"
    "商品圖片 AI 分析｜"
    "即夢 AI 2.5 Prompt｜"
    "正式發布前必須人工確認。"
)
