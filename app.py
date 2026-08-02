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
# Gemini SDK
# =========================================================

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


# =========================================================
# 網頁設定
# =========================================================

st.set_page_config(
    page_title="AI 蝦皮半自動化 2.5 PRO",
    page_icon="🛒",
    layout="wide",
)


# =========================================================
# 系統基本設定
# =========================================================

APP_NAME = "AI 蝦皮半自動化 2.5 PRO"

DATA_DIR = "data"
MEMBERS_FILE = os.path.join(DATA_DIR, "members.json")

MAX_IMAGE_SIZE = 1600
MAX_IMAGE_MB = 20

DEFAULT_MEMBER_DAYS = 30

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


# =========================================================
# Gemini 模型
#
# 目前使用官方穩定模型。
#
# 優先：
# 1. gemini-3.5-flash
# 2. gemini-3.1-flash-lite
# 3. gemini-2.5-flash-lite
#
# 不再使用：
# gemini-2.5-flash
#
# 因為你的 API Key 已經回傳：
# 404 NOT_FOUND / no longer available to new users
# =========================================================

GEMINI_MODEL_CANDIDATES = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
]


# =========================================================
# 建立資料資料夾
# =========================================================

os.makedirs(DATA_DIR, exist_ok=True)


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
    unsafe_allow_html=True,
)


# =========================================================
# 會員資料
# =========================================================

def load_members():
    if not os.path.exists(MEMBERS_FILE):
        return []

    try:
        with open(
            MEMBERS_FILE,
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

    except Exception:
        pass

    return []


def save_members(members):
    os.makedirs(DATA_DIR, exist_ok=True)

    with open(
        MEMBERS_FILE,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            members,
            f,
            ensure_ascii=False,
            indent=2,
        )


# =========================================================
# 密碼
# =========================================================

def hash_password(password):
    salt = secrets.token_hex(16)

    digest = hashlib.sha256(
        (salt + password).encode("utf-8")
    ).hexdigest()

    return f"{salt}${digest}"


def verify_password(password, saved_value):
    try:
        salt, saved_hash = saved_value.split("$", 1)

        digest = hashlib.sha256(
            (salt + password).encode("utf-8")
        ).hexdigest()

        return secrets.compare_digest(
            digest,
            saved_hash,
        )

    except Exception:
        return False


# =========================================================
# 管理員初始化
# =========================================================

def ensure_admin():
    members = load_members()

    for member in members:
        if member.get("username") == ADMIN_USERNAME:
            return

    admin = {
        "id": secrets.token_hex(8),
        "username": ADMIN_USERNAME,
        "password_hash": hash_password(ADMIN_PASSWORD),
        "name": "系統管理員",
        "email": "",
        "role": "admin",
        "status": "active",
        "expires": (
            date.today() + timedelta(days=3650)
        ).isoformat(),
        "created_at": datetime.now().isoformat(),
    }

    members.append(admin)
    save_members(members)


ensure_admin()


# =========================================================
# 會員查詢
# =========================================================

def find_member(username):
    username = str(username).strip().lower()

    for member in load_members():
        if (
            str(member.get("username", "")).lower()
            == username
        ):
            return member

    return None


def find_member_by_email(email):
    email = str(email).strip().lower()

    if not email:
        return None

    for member in load_members():
        if (
            str(member.get("email", "")).lower()
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
    email,
):
    username = str(username).strip().lower()
    email = str(email).strip().lower()

    if find_member(username):
        return False, "帳號已存在。"

    if email and find_member_by_email(email):
        return False, "Email 已註冊。"

    expires = (
        date.today()
        + timedelta(days=DEFAULT_MEMBER_DAYS)
    ).isoformat()

    member = {
        "id": secrets.token_hex(8),
        "username": username,
        "password_hash": hash_password(password),
        "name": str(name).strip(),
        "email": email,
        "role": "member",
        "status": "active",
        "expires": expires,
        "created_at": datetime.now().isoformat(),
    }

    members = load_members()
    members.append(member)
    save_members(members)

    return True, member


# =========================================================
# 更新會員
# =========================================================

def update_member(member_id, updates):
    members = load_members()

    for member in members:
        if member.get("id") == member_id:
            member.update(updates)
            save_members(members)
            return True

    return False


# =========================================================
# 登入
# =========================================================

def check_login(username, password):
    member = find_member(username)

    if not member:
        return False, "invalid"

    status = str(
        member.get("status", "active")
    ).lower()

    if status != "active":
        return False, "disabled"

    saved_hash = str(
        member.get("password_hash", "")
    )

    if not saved_hash:
        return False, "invalid"

    if not verify_password(
        password,
        saved_hash,
    ):
        return False, "invalid"

    expires_text = str(
        member.get("expires", "")
    )

    try:
        expires_date = date.fromisoformat(
            expires_text
        )
    except Exception:
        return False, "invalid_date"

    if date.today() > expires_date:
        return False, "expired"

    return True, member


# =========================================================
# Session State
# =========================================================

DEFAULT_SESSION_VALUES = {
    "logged_in": False,
    "page": "login",
    "username": "",
    "member": {},
    "analysis_result": "",
    "analysis_mode": "",
    "gemini_model": "",
    "gemini_error": "",
}


for key, value in DEFAULT_SESSION_VALUES.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# 登出
# =========================================================

def logout():
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.member = {}
    st.session_state.analysis_result = ""
    st.session_state.analysis_mode = ""
    st.session_state.gemini_model = ""
    st.session_state.gemini_error = ""
    st.session_state.page = "login"

    st.rerun()


# =========================================================
# Gemini API Key
# =========================================================

def get_gemini_api_key():
    api_key = ""

    try:
        api_key = st.secrets.get(
            "GEMINI_API_KEY",
            "",
        )
    except Exception:
        api_key = ""

    if not api_key:
        api_key = os.getenv(
            "GEMINI_API_KEY",
            "",
        )

    return str(api_key).strip()


# =========================================================
# Gemini Client
# =========================================================

@st.cache_resource
def get_gemini_client(api_key):
    if not api_key:
        return None

    if genai is None:
        return None

    return genai.Client(
        api_key=api_key
    )


# =========================================================
# Gemini 錯誤處理
# =========================================================

def explain_gemini_error(error):
    text = str(error)
    lower = text.lower()

    if (
        "404" in lower
        or "not_found" in lower
        or "not found" in lower
        or "no longer available" in lower
    ):
        return (
            "Gemini 模型無法使用。\n\n"
            "系統已經不再固定使用 "
            "gemini-2.5-flash。\n\n"
            "目前系統會依序嘗試：\n"
            "1. gemini-3.5-flash\n"
            "2. gemini-3.1-flash-lite\n"
            "3. gemini-2.5-flash-lite\n\n"
            f"原始錯誤：{text}"
        )

    if (
        "401" in lower
        or (
            "api key" in lower
            and "invalid" in lower
        )
    ):
        return (
            "Gemini API Key 無效。\n\n"
            "請檢查 Streamlit Secrets 的：\n"
            "GEMINI_API_KEY\n\n"
            f"原始錯誤：{text}"
        )

    if "403" in lower:
        return (
            "Gemini API 權限不足。\n\n"
            "請確認 API Key、Google AI Studio "
            "專案與 API 權限。\n\n"
            f"原始錯誤：{text}"
        )

    if (
        "429" in lower
        or "quota" in lower
        or "resource exhausted" in lower
    ):
        return (
            "Gemini API 額度或速率限制。\n\n"
            "請稍後再試，或確認 API 帳戶額度。\n\n"
            f"原始錯誤：{text}"
        )

    if "400" in lower:
        return (
            "Gemini API 請求格式錯誤。\n\n"
            "請確認 google-genai 套件版本與圖片格式。\n\n"
            f"原始錯誤：{text}"
        )

    return (
        "Gemini API 呼叫失敗。\n\n"
        f"詳細錯誤：{text}"
    )


# =========================================================
# Gemini 呼叫
# =========================================================

def call_gemini(
    prompt,
    image_bytes=None,
    mime_type="image/jpeg",
):
    api_key = get_gemini_api_key()

    if not api_key:
        raise RuntimeError(
            "找不到 GEMINI_API_KEY。\n\n"
            "請在 Streamlit Secrets 設定：\n"
            'GEMINI_API_KEY = "你的 Gemini API Key"'
        )

    if genai is None:
        raise RuntimeError(
            "尚未安裝 google-genai。\n\n"
            "請在 requirements.txt 加入：\n"
            "google-genai"
        )

    if types is None:
        raise RuntimeError(
            "google.genai.types 無法載入。\n\n"
            "請更新 google-genai。"
        )

    client = get_gemini_client(api_key)

    if client is None:
        raise RuntimeError(
            "Gemini Client 建立失敗。"
        )

    errors = []

    for model_name in GEMINI_MODEL_CANDIDATES:
        try:
            contents = []

            if image_bytes:
                image_part = types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type,
                )

                contents.append(image_part)

            contents.append(prompt)

            response = client.models.generate_content(
                model=model_name,
                contents=contents,
            )

            text = getattr(
                response,
                "text",
                None,
            )

            if not text:
                raise RuntimeError(
                    "Gemini 回傳成功，但沒有文字內容。"
                )

            st.session_state.gemini_model = model_name

            return str(text)

        except Exception as error:
            error_text = str(error)
            lower = error_text.lower()

            errors.append(
                f"{model_name}: {error_text}"
            )

            is_model_error = (
                "404" in lower
                or "not_found" in lower
                or "not found" in lower
                or "no longer available" in lower
            )

            if is_model_error:
                continue

            raise RuntimeError(
                explain_gemini_error(error)
            )

    raise RuntimeError(
        "目前設定的 Gemini 模型都無法使用。\n\n"
        + "\n\n".join(errors)
    )


# =========================================================
# 圖片處理
# =========================================================

def prepare_image(uploaded_file):
    if uploaded_file is None:
        raise ValueError(
            "沒有收到圖片檔案。"
        )

    try:
        raw_bytes = uploaded_file.getvalue()

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
            io.BytesIO(raw_bytes)
        )

        image = ImageOps.exif_transpose(image)
        image.load()

        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")

        image.thumbnail(
            (
                MAX_IMAGE_SIZE,
                MAX_IMAGE_SIZE,
            ),
            Image.Resampling.LANCZOS,
        )

        if image.mode == "RGBA":
            background = Image.new(
                "RGB",
                image.size,
                "white",
            )

            background.paste(
                image,
                mask=image.getchannel("A"),
            )

            image = background
        else:
            image = image.convert("RGB")

        buffer = io.BytesIO()

        image.save(
            buffer,
            format="JPEG",
            quality=92,
            optimize=True,
        )

        return image, buffer.getvalue()

    except Exception as error:
        raise ValueError(
            "無法讀取這張圖片。\n\n"
            "請確認是 JPG、JPEG、PNG 或 WEBP。\n\n"
            f"詳細錯誤：{error}"
        )


# =========================================================
# 即夢核心規則
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
# Gemini Prompt
# =========================================================

def build_gemini_prompt(
    product_data,
    selected_items,
    target_platform,
):
    name = product_data.get("商品名稱") or "待確認"
    price = product_data.get("商品價格") or "待確認"
    cost = product_data.get("商品成本") or "待確認"
    commission = product_data.get("分潤比例") or "待確認"
    sales = product_data.get("月銷量") or "待確認"
    rating = product_data.get("商品評分") or "待確認"
    url = product_data.get("商品連結") or "待確認"
    spec = product_data.get("商品規格") or "待確認"

    selected_text = "、".join(
        selected_items
    )

    return f"""
你現在是「AI 蝦皮半自動化 2.5 PRO」Gemini AI 商品分析核心。

你會看到使用者上傳的一張商品圖片。

請嚴格依照圖片與使用者提供的資料分析。
不要把猜測當成事實。

==============================
【使用者提供資料】
==============================

商品名稱：
{name}

商品價格：
{price}

商品成本：
{cost}

分潤比例：
{commission}

月銷量：
{sales}

商品評分：
{rating}

商品連結：
{url}

商品規格：
{spec}

目標平台：
{target_platform}

使用功能：
{selected_text}

==============================
【最重要規則】
==============================

1. 圖片中的商品是主要商品來源。

2. 必須維持商品：
品牌、包裝、形狀、比例、顏色、材質、
Logo、標籤、印刷文字與包裝結構。

3. 不可以自行創造：
價格、折扣、贈品、認證、成分、產地、
容量、功效、醫療效果、官方規格。

4. 如果圖片看不清楚：
必須寫「無法從圖片確認」。

5. 如果圖片有多個商品：
選擇最大、最清楚、最具品牌辨識度的商品作為主商品，
並明確說明。

6. 不可以假裝知道商品官方資訊。

7. 商品文案必須避免誇大與未確認功效。

8. 即夢 Prompt 必須要求：
原商品外觀一致、包裝一致、Logo 一致、
文字一致、顏色一致、商品不變形。

9. 預設禁止人物、手、模特兒、代言人、
主持人遮擋商品。

10. 正式發布前仍需人工確認。

==============================
【輸出格式】
==============================

# 🛒 AI 蝦皮半自動化 2.5 PRO
Gemini AI 商品分析結果

## 0｜Gemini 分析狀態

- AI：Gemini
- 圖片分析：已執行
- 目標平台：{target_platform}

## 1｜商品辨識

列出：

- 商品名稱
- 商品類型
- 品牌
- 顏色
- 包裝
- 外觀
- 可確認規格
- 無法確認資訊

無法確認資料必須寫：
「待人工確認」。

## 2｜AI 選品分析

分析：

- 商品吸引力
- 內容製作潛力
- 電商展示潛力
- 競爭程度
- 內容製作難度
- 合規風險
- 推薦分數 0～100
- 推薦等級
- 分析原因

不要假裝擁有即時市場數據。

## 3｜蝦皮上架文案

產生：

### 商品標題 3 組

### 短描述

### 完整商品描述

### 商品特色

### 使用方式

### 保存方式

### 注意事項

### 搜尋關鍵字

所有未確認資料不得自行補充。

## 4｜TikTok 文案

產生：

### 3 秒開場

### 15 秒口播

### 30 秒口播

### TikTok 貼文

### Hashtag

### 行動引導

## 5｜即夢 AI 2.5 生圖 Prompt

產生：

### A｜1:1 蝦皮商品主圖

English Prompt

### Negative Prompt

### B｜9:16 TikTok 商品海報

English Prompt

### Negative Prompt

### C｜商品細節展示圖

English Prompt

### Negative Prompt

要求：

- 原商品一致
- 原包裝一致
- 原 Logo 一致
- 原文字一致
- 原顏色一致
- 原商品比例一致
- 高質感商業攝影
- 商品清楚
- 不要人物
- 不要手
- 不要代言人
- 不要浮水印
- 不要假價格
- 不要假贈品

## 6｜即夢 AI 2.5 影片 Prompt

產生 9:16 影片英文 Prompt。

包含：

Scene 1 開場
Scene 2 商品細節
Scene 3 Camera Motion
Scene 4 Ending

要求：

slow cinematic push-in,
subtle orbit movement,
smooth camera movement,
stable framing.

商品全程保持完全一致。

## 7｜即夢 AI 2.5 爆款帶貨影片

產生 15 秒 9:16 英文 Prompt。

包含：

0–3 seconds：
強開場

3–7 seconds：
商品細節

7–12 seconds：
鏡頭運動

12–15 seconds：
商品穩定收尾

不得新增未確認商品資訊。

## 8｜蝦皮分潤合規檢查

檢查：

- 商品與圖片是否一致
- 影片與商品是否一致
- 文案與商品是否一致
- 商品連結是否存在
- 是否存在未確認價格
- 是否存在未確認功效
- 是否存在誇大宣稱
- 是否存在假贈品
- 是否存在假認證
- 是否存在規格誤判
- 是否存在品牌誤判

使用：

✅ 通過
⚠️ 需確認
❌ 有問題

## 9｜最終發布建議

給出：

- 是否建議製作
- 是否建議人工確認
- 最後檢查清單

最後一定提醒：

「正式發布前仍需人工確認商品、價格、
規格、品牌、庫存、商品頁與分潤資格。」

{JIMENG_25_CORE_RULES}
"""


# =========================================================
# Gemini 商品分析
# =========================================================

def generate_gemini_ai(
    product_data,
    selected_items,
    image_bytes,
):
    target_platform = product_data.get(
        "目標平台",
        "蝦皮",
    )

    prompt = build_gemini_prompt(
        product_data,
        selected_items,
        target_platform,
    )

    return call_gemini(
        prompt=prompt,
        image_bytes=image_bytes,
        mime_type="image/jpeg",
    )


# =========================================================
# 登入頁
# =========================================================

def login_page():
    st.markdown(
        '<div class="main-title">'
        '🛒 AI 蝦皮半自動化 2.5 PRO'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="main-subtitle">'
        '會員登入｜Gemini AI 商品分析｜即夢 AI 2.5'
        '</div>',
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1, 2, 1])

    with center:
        st.subheader("🔐 會員登入")

        username = st.text_input(
            "會員帳號",
            placeholder="輸入會員帳號",
            key="login_username",
        )

        password = st.text_input(
            "會員密碼",
            type="password",
            placeholder="輸入會員密碼",
            key="login_password",
        )

        if st.button(
            "🚀 登入系統",
            type="primary",
            use_container_width=True,
        ):
            if not username or not password:
                st.error(
                    "請輸入會員帳號與密碼。"
                )
            else:
                success, result = check_login(
                    username,
                    password,
                )

                if success:
                    st.session_state.logged_in = True
                    st.session_state.username = (
                        username.strip().lower()
                    )
                    st.session_state.member = result
                    st.session_state.page = "main"

                    st.rerun()

                messages = {
                    "expired":
                        "⛔ 會員資格已到期，請聯絡管理員續期。",
                    "disabled":
                        "⛔ 此會員帳號目前已停權。",
                    "invalid_date":
                        "⛔ 會員到期日資料錯誤。",
                    "invalid":
                        "❌ 帳號或密碼錯誤。",
                }

                if not success:
                    st.error(
                        messages.get(
                            result,
                            "❌ 登入失敗。",
                        )
                    )

        st.divider()

        if st.button(
            "📝 還沒有帳號？註冊會員",
            use_container_width=True,
        ):
            st.session_state.page = "register"
            st.rerun()

        st.divider()

        st.caption(
            "本系統使用本機會員帳號＋Gemini API。"
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
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="main-subtitle">'
        '建立 AI 蝦皮半自動化 2.5 PRO 會員帳號'
        '</div>',
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1, 2, 1])

    with center:
        st.subheader("👤 建立會員帳號")

        name = st.text_input(
            "姓名 / 暱稱",
            placeholder="例如：王小明",
        )

        email = st.text_input(
            "Email",
            placeholder="例如：example@gmail.com",
        )

        username = st.text_input(
            "會員帳號",
            placeholder="3～30 個英數字或底線",
        )

        password = st.text_input(
            "會員密碼",
            type="password",
            placeholder="至少 6 個字元",
        )

        password_confirm = st.text_input(
            "再次輸入密碼",
            type="password",
        )

        if st.button(
            "🚀 建立會員帳號",
            type="primary",
            use_container_width=True,
        ):
            username_clean = (
                username.strip().lower()
            )

            email_clean = (
                email.strip().lower()
            )

            if not name.strip():
                st.error(
                    "請輸入姓名或暱稱。"
                )

            elif not re.fullmatch(
                r"[^@\s]+@[^@\s]+\.[^@\s]+",
                email_clean,
            ):
                st.error(
                    "請輸入正確 Email。"
                )

            elif not re.fullmatch(
                r"[a-z0-9_]{3,30}",
                username_clean,
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
                    email_clean,
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
                    st.error(str(result))

        st.divider()

        if st.button(
            "⬅️ 返回登入",
            use_container_width=True,
        ):
            st.session_state.page = "login"
            st.rerun()


# =========================================================
# 尚未登入
# =========================================================

if not st.session_state.logged_in:
    if st.session_state.page == "register":
        register_page()
    else:
        login_page()

    st.stop()


# =========================================================
# 目前會員
# =========================================================

current_username = st.session_state.get(
    "username",
    "",
)

current_member = st.session_state.get(
    "member",
    {},
)

latest_member = find_member(
    current_username
)

if latest_member:
    current_member = latest_member
    st.session_state.member = latest_member


member_id = current_member.get(
    "id",
    "",
)

member_name = str(
    current_member.get(
        "name",
        current_username,
    )
)

member_email = str(
    current_member.get(
        "email",
        "",
    )
)

member_role = str(
    current_member.get(
        "role",
        "member",
    )
)

member_status = str(
    current_member.get(
        "status",
        "active",
    )
)

member_expires = str(
    current_member.get(
        "expires",
        "",
    )
)


try:
    expire_date = date.fromisoformat(
        member_expires
    )

    remaining_days = (
        expire_date - date.today()
    ).days

except Exception:
    remaining_days = -999


if member_status.lower() != "active":
    st.error(
        "⛔ 此會員帳號目前已停權。"
    )

    if st.button("🚪 返回登入"):
        logout()

    st.stop()


if remaining_days < 0:
    st.error(
        "⛔ 會員資格已到期。"
    )

    if st.button("🚪 返回登入"):
        logout()

    st.stop()


# =========================================================
# 側邊欄
# =========================================================

with st.sidebar:
    st.markdown("## 👤 會員中心")

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
        "登入方式：**本機會員＋Gemini API**"
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

    if st.session_state.gemini_model:
        st.success("🟢 Gemini 已連線")
        st.caption(
            "模型："
            f"{st.session_state.gemini_model}"
        )
    else:
        st.warning(
            "🟡 Gemini 尚未執行"
        )

    st.divider()

    if st.button(
        "🚪 登出",
        use_container_width=True,
    ):
        logout()


# =========================================================
# 管理員中心
# =========================================================

def admin_panel():
    st.header("👑 管理員中心")

    members = load_members()

    st.write(
        f"目前會員數：**{len(members)}**"
    )

    for member in members:
        mid = member.get("id", "")
        username = member.get("username", "")
        name = member.get("name", "")
        email = member.get("email", "")
        role = member.get("role", "member")
        status = member.get("status", "active")
        expires = member.get("expires", "")

        with st.expander(
            f"👤 {name}｜{username}"
        ):
            st.write(
                f"Email：**{email}**"
            )

            st.write(
                "註冊方式：**本機帳號**"
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
                    "disabled",
                ],
                index=(
                    0
                    if status == "active"
                    else 1
                ),
                key=f"status_{mid}",
            )

            roles = [
                "member",
                "vip",
                "admin",
            ]

            new_role = st.selectbox(
                "會員等級",
                roles,
                index=(
                    roles.index(role)
                    if role in roles
                    else 0
                ),
                key=f"role_{mid}",
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
                key=f"expire_{mid}",
            )

            c1, c2, c3 = st.columns(3)

            with c1:
                if st.button(
                    "💾 儲存",
                    key=f"save_{mid}",
                    use_container_width=True,
                ):
                    update_member(
                        mid,
                        {
                            "status": new_status,
                            "role": new_role,
                            "expires": (
                                new_expire.isoformat()
                            ),
                        },
                    )

                    st.success("已更新。")
                    st.rerun()

            with c2:
                if st.button(
                    "➕ 延長 30 天",
                    key=f"extend_{mid}",
                    use_container_width=True,
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
                        d + timedelta(days=30)
                    )

                    update_member(
                        mid,
                        {
                            "expires":
                                new_date.isoformat(),
                            "status":
                                "active",
                        },
                    )

                    st.success(
                        "已延長至 "
                        f"{new_date.isoformat()}"
                    )

                    st.rerun()

            with c3:
                if username != current_username:
                    if st.button(
                        "⛔ 停權",
                        key=f"disable_{mid}",
                        use_container_width=True,
                    ):
                        update_member(
                            mid,
                            {
                                "status":
                                    "disabled"
                            },
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
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-subtitle">'
    'Gemini 商品辨識｜AI 選品｜蝦皮文案｜'
    'TikTok｜即夢 AI 2.5｜分潤合規'
    '</div>',
    unsafe_allow_html=True,
)


# =========================================================
# 管理員
# =========================================================

if member_role.lower() == "admin":
    with st.expander("👑 管理員中心"):
        admin_panel()

    st.divider()


# =========================================================
# Gemini API 狀態
# =========================================================

with st.expander(
    "🤖 Gemini API 狀態"
):
    api_key = get_gemini_api_key()

    if genai is None:
        st.error(
            "❌ google-genai 尚未安裝。"
        )

        st.code(
            "google-genai"
        )

    elif not api_key:
        st.error(
            "❌ 找不到 GEMINI_API_KEY。"
        )

        st.info(
            "請在 Streamlit Secrets 設定："
        )

        st.code(
            'GEMINI_API_KEY = "你的 Gemini API Key"'
        )

    else:
        st.success(
            "✅ Gemini API Key 已讀取"
        )

        st.write(
            "模型優先順序："
        )

        for index, model in enumerate(
            GEMINI_MODEL_CANDIDATES,
            start=1,
        ):
            st.write(
                f"{index}. `{model}`"
            )

        st.caption(
            "系統不再固定使用失效的 "
            "gemini-2.5-flash。"
        )


# =========================================================
# 上傳圖片
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
        "webp",
    ],
    accept_multiple_files=False,
    key="product_image_uploader",
    help=(
        "支援 JPG、JPEG、PNG、WEBP。"
        "建議使用清楚的商品正面照片。"
    ),
)

prepared_image = None
prepared_image_bytes = None


if uploaded_file is not None:
    try:
        (
            prepared_image,
            prepared_image_bytes,
        ) = prepare_image(
            uploaded_file
        )

        st.success(
            f"✅ 圖片已成功上傳："
            f"{uploaded_file.name}"
        )

        st.image(
            prepared_image,
            caption=(
                "Gemini 將使用這張圖片進行商品分析"
            ),
            use_container_width=True,
        )

    except Exception as error:
        st.error(
            "❌ 圖片讀取失敗。"
        )

        st.code(str(error))


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
        key="product_name",
    )

    product_price = st.text_input(
        "商品價格",
        placeholder="例如：399",
        key="product_price",
    )

    product_cost = st.text_input(
        "商品成本",
        placeholder="例如：250",
        key="product_cost",
    )

    commission_rate = st.text_input(
        "分潤比例",
        placeholder="例如：12%",
        key="commission_rate",
    )


with col2:
    monthly_sales = st.text_input(
        "月銷量",
        placeholder="例如：1500",
        key="monthly_sales",
    )

    product_rating = st.text_input(
        "商品評分",
        placeholder="例如：4.8",
        key="product_rating",
    )

    product_url = st.text_input(
        "商品連結",
        placeholder="可留空",
        key="product_url",
    )

    product_spec = st.text_area(
        "商品規格",
        placeholder="例如：300ml、單瓶、白色",
        height=130,
        key="product_spec",
    )


# =========================================================
# 目標平台
# =========================================================

st.subheader(
    "3｜🎯 目標平台"
)

target_platform = st.radio(
    "目標平台",
    [
        "蝦皮",
        "TikTok",
        "蝦皮＋TikTok",
    ],
    horizontal=True,
    key="target_platform",
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
    "完整流程",
]

selected_items = st.multiselect(
    "選擇需要的功能",
    options=generate_options,
    default=["完整流程"],
    key="selected_ai_features",
)

if (
    "完整流程" in selected_items
    and len(selected_items) > 1
):
    st.info(
        "ℹ️ 已選擇完整流程，"
        "Gemini 會一次產生完整分析。"
    )


# =========================================================
# 啟動 Gemini
# =========================================================

st.subheader(
    "5｜🚀 開始 Gemini AI 分析"
)

if st.button(
    "🚀 啟動 Gemini AI 蝦皮半自動化 2.5",
    type="primary",
    use_container_width=True,
    key="start_ai_analysis",
):
    st.session_state.gemini_error = ""

    if prepared_image_bytes is None:
        st.error(
            "❌ 請先上傳商品圖片。"
        )

    elif not selected_items:
        st.error(
            "❌ 請至少選擇一個 AI 功能。"
        )

    elif not get_gemini_api_key():
        st.error(
            "❌ 找不到 GEMINI_API_KEY。"
        )

        st.code(
            'GEMINI_API_KEY = "你的 Gemini API Key"'
        )

    else:
        product_data = {
            "商品名稱": product_name,
            "商品價格": product_price,
            "商品成本": product_cost,
            "分潤比例": commission_rate,
            "月銷量": monthly_sales,
            "商品評分": product_rating,
            "商品連結": product_url,
            "商品規格": product_spec,
            "目標平台": target_platform,
        }

        effective_items = (
            ["完整流程"]
            if "完整流程" in selected_items
            else selected_items
        )

        with st.spinner(
            "🧠 Gemini 正在讀取商品圖片、"
            "辨識商品並建立完整電商內容……"
        ):
            try:
                result = generate_gemini_ai(
                    product_data,
                    effective_items,
                    prepared_image_bytes,
                )

                st.session_state.analysis_result = result

                st.session_state.analysis_mode = (
                    "Gemini API｜圖片＋文字分析"
                )

                st.success(
                    "🎉 Gemini AI 分析完成！"
                )

                if st.session_state.gemini_model:
                    st.info(
                        "🤖 實際使用模型："
                        f"{st.session_state.gemini_model}"
                    )

            except Exception as error:
                error_message = str(error)

                st.session_state.gemini_error = (
                    error_message
                )

                st.session_state.analysis_result = ""

                st.error(
                    "❌ Gemini API 呼叫失敗。"
                )

                st.code(
                    error_message
                )


# =========================================================
# Gemini 錯誤
# =========================================================

if st.session_state.gemini_error:
    with st.expander(
        "🔎 Gemini 錯誤詳細資訊",
        expanded=True,
    ):
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

    if st.session_state.gemini_model:
        st.success(
            "🤖 Gemini 模型："
            f"{st.session_state.gemini_model}"
        )

    st.markdown(
        '<div class="result-box">',
        unsafe_allow_html=True,
    )

    st.markdown(
        st.session_state.analysis_result
    )

    st.markdown(
        "</div>",
        unsafe_allow_html=True,
    )

    st.subheader(
        "7｜📋 完整結果"
    )

    st.text_area(
        "完整 Gemini AI 結果",
        value=st.session_state.analysis_result,
        height=700,
        key="full_ai_result",
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
        safe_product_name,
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
        key="download_ai_result",
    )

    st.warning(
        "正式發布前，請人工確認："
        "商品名稱、品牌、容量、產地、"
        "成分、保存期限、貨源、售價、"
        "庫存、組合數、商品規格及分潤資格。"
    )


# =========================================================
# 系統設定
# =========================================================

with st.expander(
    "⚙️ 系統設定"
):
    st.success("✅ 本機會員系統")
    st.success("✅ members.json")
    st.success("✅ Gemini API")
    st.success("✅ Gemini 商品圖片辨識")
    st.success("✅ Gemini 商品分析")
    st.success("✅ Gemini 蝦皮文案")
    st.success("✅ Gemini TikTok 文案")
    st.success("✅ Gemini 即夢 AI 2.5 Prompt")
    st.success("✅ Gemini 爆款帶貨影片 Prompt")
    st.success("✅ 即夢 AI 2.5 商品一致性規則")

    st.info(
        "目前系統使用 Gemini API 真正分析商品圖片，"
        "不再使用原本的本機規則假 AI 模式。"
    )

    st.info(
        "目前模型優先順序："
        "gemini-3.5-flash → "
        "gemini-3.1-flash-lite → "
        "gemini-2.5-flash-lite"
    )


# =========================================================
# 頁尾
# =========================================================

st.divider()

st.caption(
    "AI 蝦皮半自動化 2.5 PRO｜"
    "Gemini AI｜"
    "商品圖片辨識｜"
    "即夢 AI 2.5 Prompt｜"
    "正式發布前必須人工確認。"
)
