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
# AI 蝦皮半自動化 2.5 PRO
#
# Gemini API 正式版本
#
# 功能：
# 會員註冊
# 會員登入
# 會員期限
# 管理員
# 商品圖片上傳
# Gemini 圖片分析
# AI 選品分析
# 蝦皮商品文案
# TikTok 文案
# 即夢 AI 2.5 生圖 Prompt
# 即夢 AI 2.5 影片 Prompt
# 爆款帶貨影片 Prompt
# 分潤合規檢查
#
# Gemini 模型：
# 不再固定使用失效的 gemini-2.5-flash
#
# 系統會：
# 1. 讀取 Gemini API 可用模型
# 2. 找出支援 generateContent 的模型
# 3. 依照優先順序自動選擇
#
# =========================================================


# =========================================================
# Streamlit 網頁設定
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
    "members.json",
)

MAX_IMAGE_SIZE = 1600
MAX_IMAGE_MB = 20

DEFAULT_MEMBER_DAYS = 30

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


# =========================================================
# Gemini 模型優先順序
#
# 重要：
# 不再固定 gemini-2.5-flash。
#
# 系統會先嘗試目前較新的模型，
# 如果你的 API 帳戶沒有該模型，
# 會自動從 models.list() 找真正可用模型。
# =========================================================

GEMINI_MODEL_PREFERENCES = [
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
]


# =========================================================
# 建立資料夾
# =========================================================

os.makedirs(
    DATA_DIR,
    exist_ok=True,
)


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

    .gemini-ok {
        padding: 12px;
        border-radius: 10px;
        border: 1px solid rgba(0,180,100,.3);
        margin-bottom: 12px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# 會員資料庫
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
    os.makedirs(
        DATA_DIR,
        exist_ok=True,
    )

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
        (
            salt + password
        ).encode("utf-8")
    ).hexdigest()

    return f"{salt}${digest}"


def verify_password(
    password,
    saved_value,
):
    try:
        salt, saved_hash = saved_value.split(
            "$",
            1,
        )

        digest = hashlib.sha256(
            (
                salt + password
            ).encode("utf-8")
        ).hexdigest()

        return secrets.compare_digest(
            digest,
            saved_hash,
        )

    except Exception:
        return False


# =========================================================
# 初始化管理員
# =========================================================

def ensure_admin():
    members = load_members()

    for member in members:
        if member.get("username") == ADMIN_USERNAME:
            return

    admin = {
        "id": secrets.token_hex(8),
        "username": ADMIN_USERNAME,
        "password_hash": hash_password(
            ADMIN_PASSWORD
        ),
        "name": "系統管理員",
        "email": "",
        "role": "admin",
        "status": "active",
        "expires": (
            date.today()
            + timedelta(days=3650)
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
    username = (
        str(username)
        .strip()
        .lower()
    )

    members = load_members()

    for member in members:
        if (
            str(
                member.get(
                    "username",
                    "",
                )
            ).lower()
            == username
        ):
            return member

    return None


def find_member_by_email(email):
    email = (
        str(email)
        .strip()
        .lower()
    )

    if not email:
        return None

    members = load_members()

    for member in members:
        if (
            str(
                member.get(
                    "email",
                    "",
                )
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
    email,
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

    if find_member(username):
        return (
            False,
            "帳號已存在。",
        )

    if email and find_member_by_email(email):
        return (
            False,
            "Email 已註冊。",
        )

    expires = (
        date.today()
        + timedelta(
            days=DEFAULT_MEMBER_DAYS
        )
    ).isoformat()

    member = {
        "id": secrets.token_hex(8),
        "username": username,
        "password_hash": hash_password(
            password
        ),
        "name": name.strip(),
        "email": email,
        "role": "member",
        "status": "active",
        "expires": expires,
        "created_at": datetime.now().isoformat(),
    }

    members = load_members()

    members.append(member)

    save_members(members)

    return (
        True,
        member,
    )


# =========================================================
# 更新會員
# =========================================================

def update_member(
    member_id,
    updates,
):
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

def check_login(
    username,
    password,
):
    member = find_member(username)

    if not member:
        return (
            False,
            "invalid",
        )

    status = str(
        member.get(
            "status",
            "active",
        )
    ).lower()

    if status != "active":
        return (
            False,
            "disabled",
        )

    saved_hash = str(
        member.get(
            "password_hash",
            "",
        )
    )

    if (
        not saved_hash
        or not verify_password(
            password,
            saved_hash,
        )
    ):
        return (
            False,
            "invalid",
        )

    expires_text = str(
        member.get(
            "expires",
            "",
        )
    )

    try:
        expires_date = date.fromisoformat(
            expires_text
        )

    except Exception:
        return (
            False,
            "invalid_date",
        )

    if date.today() > expires_date:
        return (
            False,
            "expired",
        )

    return (
        True,
        member,
    )


# =========================================================
# Session State
# =========================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "page" not in st.session_state:
    st.session_state.page = "login"

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = ""

if "analysis_mode" not in st.session_state:
    st.session_state.analysis_mode = ""

if "gemini_model" not in st.session_state:
    st.session_state.gemini_model = ""

if "gemini_error" not in st.session_state:
    st.session_state.gemini_error = ""

if "available_gemini_models" not in st.session_state:
    st.session_state.available_gemini_models = []


# =========================================================
# 登出
# =========================================================

def logout():
    st.session_state.logged_in = False

    st.session_state.pop(
        "username",
        None,
    )

    st.session_state.pop(
        "member",
        None,
    )

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
    """
    API Key 優先順序：

    1. Streamlit Secrets
    2. 環境變數

    不把 API Key 寫死。
    """

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

    try:
        return genai.Client(
            api_key=api_key
        )
    except Exception:
        return None


# =========================================================
# 模型名稱整理
# =========================================================

def clean_model_name(model_name):
    """
    Google models.list() 有時回傳：
        models/gemini-xxx

    generate_content 使用：
        gemini-xxx

    因此統一移除 models/。
    """

    name = str(
        model_name or ""
    ).strip()

    if name.startswith("models/"):
        name = name[len("models/"):]

    return name


# =========================================================
# 取得 API 帳號目前真正可用模型
# =========================================================

def list_available_gemini_models(client):
    """
    從 Gemini API 讀取目前帳號可使用的模型。

    只保留支援 generateContent 的模型。
    """

    if client is None:
        return []

    available = []

    try:
        for model in client.models.list():
            name = clean_model_name(
                getattr(
                    model,
                    "name",
                    "",
                )
            )

            if not name:
                continue

            supported_actions = getattr(
                model,
                "supported_actions",
                None,
            )

            supports_generate = False

            if supported_actions:
                try:
                    supports_generate = (
                        "generateContent"
                        in supported_actions
                    )
                except Exception:
                    supports_generate = False

            # 某些 SDK 版本可能沒有正確帶出 supported_actions。
            # 如果名稱是 Gemini 模型，保留給後面的實際呼叫測試。
            if supports_generate:
                available.append(name)

            elif (
                name.startswith("gemini-")
                and "embedding" not in name.lower()
                and "tts" not in name.lower()
                and "live" not in name.lower()
            ):
                available.append(name)

    except Exception:
        return []

    # 去除重複
    result = []

    for item in available:
        if item not in result:
            result.append(item)

    return result


# =========================================================
# 模型排序
# =========================================================

def rank_gemini_models(available_models):
    """
    將 API 實際回傳的模型依照我們的優先順序排序。

    重要：
    只有 API 回傳的模型才會被優先選用。
    """

    available = [
        clean_model_name(x)
        for x in available_models
    ]

    available = list(
        dict.fromkeys(available)
    )

    ranked = []

    # 1. 精準名稱優先
    for preferred in GEMINI_MODEL_PREFERENCES:
        if preferred in available:
            if preferred not in ranked:
                ranked.append(preferred)

    # 2. 再找名稱相近模型
    keywords = [
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
    ]

    for keyword in keywords:
        for model_name in available:
            if model_name == keyword:
                continue

            if keyword in model_name:
                if model_name not in ranked:
                    ranked.append(model_name)

    # 3. 最後才放其他可用 Gemini 模型
    for model_name in available:
        if (
            model_name.startswith("gemini-")
            and model_name not in ranked
            and "embedding" not in model_name.lower()
            and "tts" not in model_name.lower()
            and "live" not in model_name.lower()
        ):
            ranked.append(model_name)

    return ranked


# =========================================================
# Gemini 錯誤分類
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
            "Gemini 模型不存在、已停用，"
            "或目前 API 帳戶無法使用該模型。\n\n"
            "本版本已改成先讀取 Gemini API "
            "目前真正可用的模型，不再固定使用 "
            "gemini-2.5-flash。\n\n"
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
            "請檢查 Streamlit Secrets：\n"
            "GEMINI_API_KEY = \"你的 Gemini API Key\"\n\n"
            f"原始錯誤：{text}"
        )

    if "403" in lower:
        return (
            "Gemini API 權限不足。\n\n"
            "請確認 API Key、Google AI Studio "
            "專案與模型權限。\n\n"
            f"原始錯誤：{text}"
        )

    if (
        "429" in lower
        or "quota" in lower
        or "resource exhausted" in lower
    ):
        return (
            "Gemini API 額度或速率限制。\n\n"
            "請稍後再試，或確認 API 帳戶目前可用額度。\n\n"
            f"原始錯誤：{text}"
        )

    if "400" in lower:
        return (
            "Gemini API 請求格式錯誤。\n\n"
            "請確認圖片格式、Prompt 與 google-genai SDK。\n\n"
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
            "GEMINI_API_KEY = \"你的 Gemini API Key\""
        )

    if genai is None:
        raise RuntimeError(
            "尚未安裝 google-genai。\n\n"
            "請確認 requirements.txt 有：\n"
            "google-genai"
        )

    client = get_gemini_client(
        api_key
    )

    if client is None:
        raise RuntimeError(
            "Gemini Client 建立失敗。\n\n"
            "請確認 GEMINI_API_KEY 是否正確。"
        )

    # -----------------------------------------------------
    # 第一步：直接從 API 取得模型
    # -----------------------------------------------------

    discovered_models = list_available_gemini_models(
        client
    )

    ranked_models = rank_gemini_models(
        discovered_models
    )

    # 保存到 Session
    st.session_state.available_gemini_models = (
        ranked_models
    )

    # -----------------------------------------------------
    # 如果 API 能列出模型
    # 只使用 API 真正回傳的模型。
    # -----------------------------------------------------

    models_to_try = list(ranked_models)

    # -----------------------------------------------------
    # 如果 models.list() 無法使用，
    # 才使用保守 fallback。
    # -----------------------------------------------------

    if not models_to_try:
        models_to_try = list(
            GEMINI_MODEL_PREFERENCES
        )

    errors = []

    # -----------------------------------------------------
    # 建立 Gemini Contents
    # -----------------------------------------------------

    contents = []

    if (
        image_bytes
        and types is not None
    ):
        contents.append(
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type,
            )
        )

    contents.append(prompt)

    # -----------------------------------------------------
    # 逐個模型嘗試
    # -----------------------------------------------------

    for model_name in models_to_try:
        try:
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
                    "Gemini 回傳成功，"
                    "但沒有文字內容。"
                )

            st.session_state.gemini_model = (
                clean_model_name(model_name)
            )

            return text

        except Exception as error:
            error_text = str(error)

            errors.append(
                f"{model_name}: {error_text}"
            )

            lower = error_text.lower()

            # -------------------------------------------------
            # 404 / 模型不存在：
            # 繼續測下一個模型
            # -------------------------------------------------

            is_model_error = (
                "404" in lower
                or "not_found" in lower
                or "not found" in lower
                or "no longer available" in lower
                or (
                    "model" in lower
                    and "not found" in lower
                )
            )

            if is_model_error:
                continue

            # -------------------------------------------------
            # 其他錯誤：
            # 不要無限換模型。
            # 例如 API Key 錯誤、403、429 等，
            # 換模型通常無法解決。
            # -------------------------------------------------

            raise RuntimeError(
                explain_gemini_error(
                    error
                )
            )

    # -----------------------------------------------------
    # 所有模型都失敗
    # -----------------------------------------------------

    raise RuntimeError(
        "目前 Gemini API 找不到可以成功執行的模型。\n\n"
        "系統已嘗試目前 API 可見模型與備援模型。\n\n"
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

        image = ImageOps.exif_transpose(
            image
        )

        image.load()

        if image.mode not in (
            "RGB",
            "RGBA",
        ):
            image = image.convert(
                "RGB"
            )

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
            image = image.convert(
                "RGB"
            )

        buffer = io.BytesIO()

        image.save(
            buffer,
            format="JPEG",
            quality=92,
            optimize=True,
        )

        return (
            image,
            buffer.getvalue(),
        )

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
# Gemini 商品分析 Prompt
# =========================================================

def build_gemini_prompt(
    product_data,
    selected_items,
    target_platform,
):
    name = product_data.get(
        "商品名稱",
        "",
    ) or "待確認"

    price = product_data.get(
        "商品價格",
        "",
    ) or "待確認"

    cost = product_data.get(
        "商品成本",
        "",
    ) or "待確認"

    commission = product_data.get(
        "分潤比例",
        "",
    ) or "待確認"

    sales = product_data.get(
        "月銷量",
        "",
    ) or "待確認"

    rating = product_data.get(
        "商品評分",
        "",
    ) or "待確認"

    url = product_data.get(
        "商品連結",
        "",
    ) or "待確認"

    spec = product_data.get(
        "商品規格",
        "",
    ) or "待確認"

    selected_text = "、".join(
        selected_items
    )

    prompt = f"""
你現在是「AI 蝦皮半自動化 2.5 PRO」的 Gemini 商品分析核心。

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

6. 不可以假裝自己知道商品的官方資訊。

7. 商品文案必須避免誇大與未確認功效。

8. 即夢 Prompt 必須要求：
原商品外觀一致、包裝一致、Logo 一致、
文字一致、顏色一致、商品不變形。

9. 預設禁止人物、手、模特兒、代言人、
主持人遮擋商品。

10. 所有正式發布前仍要人工確認。

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

請列出：

- 商品名稱
- 商品類型
- 品牌
- 顏色
- 包裝
- 外觀
- 可確認規格
- 無法確認資訊

對於無法確認的資料一定寫：
「待人工確認」。

## 2｜AI 選品分析

請分析：

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

請產生：

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

請產生：

### 3 秒開場

### 15 秒口播

### 30 秒口播

### TikTok 貼文

### Hashtag

### 行動引導

## 5｜即夢 AI 2.5 生圖 Prompt

請輸出：

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

請產生 9:16 影片英文 Prompt。

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

請檢查：

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

請用：

✅ 通過
⚠️ 需確認
❌ 有問題

三種標記。

## 9｜最終發布建議

請給：

- 是否建議製作
- 是否建議人工確認
- 最後檢查清單

最後一定提醒：

「正式發布前仍需人工確認商品、價格、
規格、品牌、庫存、商品頁與分潤資格。」

{JIMENG_25_CORE_RULES}
"""

    return prompt


# =========================================================
# Gemini 完整分析
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

    result = call_gemini(
        prompt=prompt,
        image_bytes=image_bytes,
        mime_type="image/jpeg",
    )

    return result


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

                else:
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

    _, center, _ = st.columns(
        [1, 2, 1]
    )

    with center:
        st.subheader(
            "👤 建立會員帳號"
        )

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
                    st.error(
                        str(result)
                    )

        st.divider()

        if st.button(
            "⬅️ 返回登入",
            use_container_width=True,
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
        expire_date
        - date.today()
    ).days

except Exception:
    remaining_days = -999


if member_status.lower() != "active":
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
        st.success(
            "🟢 Gemini 已連線"
        )

        st.caption(
            f"模型：{st.session_state.gemini_model}"
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
            "",
        )

        username = member.get(
            "username",
            "",
        )

        name = member.get(
            "name",
            "",
        )

        email = member.get(
            "email",
            "",
        )

        role = member.get(
            "role",
            "member",
        )

        status = member.get(
            "status",
            "active",
        )

        expires = member.get(
            "expires",
            "",
        )

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
                   
