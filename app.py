import io
import os
import json
import hashlib
import secrets
from datetime import datetime, date, timedelta

import streamlit as st
from PIL import Image, ImageOps

# =========================================================
# AI 蝦皮半自動化 2.5 PRO
# 免費 Gemini Flash 版
# =========================================================

# =========================================================
# Google Gemini SDK
# =========================================================
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


# =========================================================
# 頁面設定
# =========================================================
APP_NAME = "AI 蝦皮半自動化 2.5 PRO"
GEMINI_MODEL = "gemini-2.5-flash"

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================================================
# 基本設定
# =========================================================
DATA_DIR = "data"
MEMBERS_FILE = os.path.join(DATA_DIR, "members.json")

MAX_IMAGE_MB = 20
MAX_IMAGE_SIZE = 1600
MAX_VIDEO_MB = 300
DEFAULT_MEMBER_DAYS = 30

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

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
        margin-bottom: 8px;
    }

    .main-subtitle {
        text-align: center;
        opacity: .72;
        margin-bottom: 25px;
    }

    .small-note {
        font-size: 13px;
        opacity: .72;
    }

    .video-title {
        font-size: 26px;
        font-weight: 800;
        margin-top: 10px;
        margin-bottom: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# Session State
# =========================================================
DEFAULT_STATE = {
    "logged_in": False,
    "username": "",
    "user_role": "guest",
    "member": {},
    "api_key": "",
    "analysis_results": None,
    "last_video_name": "",
    "last_video_bytes": None,
    "last_video_mime": "video/mp4",
    "last_video_ext": ".mp4",
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# Gemini API Key
# =========================================================
def get_gemini_api_key():
    key = ""
    try:
        key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        key = ""

    if not key:
        key = os.getenv("GEMINI_API_KEY", "")

    if not key:
        key = st.session_state.get("api_key", "")

    return str(key).strip()


# =========================================================
# Gemini Client
# =========================================================
@st.cache_resource
def create_gemini_client(api_key):
    if not api_key or genai is None:
        return None

    try:
        return genai.Client(api_key=api_key)
    except Exception:
        return None


def reset_gemini_client():
    try:
        create_gemini_client.clear()
    except Exception:
        pass


# =========================================================
# Gemini API
# =========================================================
def gemini_generate_text(prompt, image_bytes=None, image_mime="image/jpeg"):
    api_key = get_gemini_api_key()

    if not api_key:
        return (
            "❌ 尚未設定 GEMINI_API_KEY。\n\n"
            "請在左側 Gemini API 設定輸入 API Key，"
            "或放入 Streamlit Secrets。"
        )

    if genai is None or types is None:
        return (
            "❌ 尚未安裝 google-genai。\n\n"
            "請確認 requirements.txt 包含：\n"
            "google-genai"
        )

    client = create_gemini_client(api_key)

    if client is None:
        return "❌ Gemini Client 建立失敗，請確認 API Key。"

    candidate_models = [GEMINI_MODEL, "gemini-1.5-flash", "gemini-2.0-flash"]
    candidate_models = list(dict.fromkeys(candidate_models))

    contents = []
    if image_bytes:
        contents.append(
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=image_mime,
            )
        )
    contents.append(prompt)

    last_error = ""
    for model_name in candidate_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
            )

            text = getattr(response, "text", None)

            if text:
                return str(text)

        except Exception as e:
            last_error = str(e)
            if "404" in last_error.lower() or "not found" in last_error.lower():
                continue
            else:
                break

    error_text = last_error
    lower = error_text.lower()

    if "api key" in lower or "api_key" in lower:
        return "❌ Gemini API Key 錯誤，請重新建立或確認 Key。"

    if "401" in lower:
        return "❌ Gemini API Key 無效或未授權。"

    if "403" in lower:
        return f"❌ Gemini API 權限不足。\n\n詳細錯誤：{error_text}"

    if "429" in lower or "quota" in lower:
        return (
            "❌ Gemini 免費層級目前遇到額度或速率限制。\n\n"
            "請稍後再試，或確認 Google AI Studio 的用量狀態。"
        )

    if "404" in lower or "not found" in lower:
        return (
            f"❌ 所選的 Gemini 模型目前無法使用。\n\n"
            f"已嘗試模型：{', '.join(candidate_models)}\n\n"
            f"詳細錯誤：{error_text}"
        )

    return f"❌ Gemini 呼叫失敗。\n\n{error_text}"


# =========================================================
# 密碼處理
# =========================================================
def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.sha256(
        (salt + str(password)).encode("utf-8")
    ).hexdigest()
    return f"{salt}${digest}"


def verify_password(password, saved_password):
    try:
        salt, saved_hash = saved_password.split("$", 1)
        digest = hashlib.sha256(
            (salt + str(password)).encode("utf-8")
        ).hexdigest()
        return secrets.compare_digest(digest, saved_hash)
    except Exception:
        return False


# =========================================================
# 會員資料處理
# =========================================================
def load_members():
    if not os.path.exists(MEMBERS_FILE):
        return []

    try:
        with open(MEMBERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data
    except Exception:
        pass

    return []


def save_members(members):
    os.makedirs(DATA_DIR, exist_ok=True)

    with open(MEMBERS_FILE, "w", encoding="utf-8") as f:
        json.dump(
            members,
            f,
            ensure_ascii=False,
            indent=2,
        )


def ensure_admin():
    members = load_members()

    for member in members:
        if str(member.get("username", "")).lower() == ADMIN_USERNAME:
            return

    members.append(
        {
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
    )

    save_members(members)


ensure_admin()


def find_member(username):
    username = str(username).strip().lower()

    for member in load_members():
        if str(member.get("username", "")).lower() == username:
            return member

    return None


def find_member_by_email(email):
    email = str(email).strip().lower()

    if not email:
        return None

    for member in load_members():
        if str(member.get("email", "")).lower() == email:
            return member

    return None


def create_member(username, password, name, email):
    username = str(username).strip().lower()
    password = str(password)
    name = str(name).strip()
    email = str(email).strip().lower()

    if len(username) < 3:
        return False, "帳號至少需要 3 個字元。"

    if len(password) < 6:
        return False, "密碼至少需要 6 個字元。"

    if find_member(username):
        return False, "帳號已存在。"

    if email and find_member_by_email(email):
        return False, "Email 已註冊。"

    expires = (
        date.today() + timedelta(days=DEFAULT_MEMBER_DAYS)
    ).isoformat()

    member = {
        "id": secrets.token_hex(8),
        "username": username,
        "password_hash": hash_password(password),
        "name": name,
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


def update_member(member_id, updates):
    members = load_members()

    for member in members:
        if member.get("id") == member_id:
            member.update(updates)
            save_members(members)
            return True

    return False


def check_login(username, password):
    member = find_member(username)

    if not member:
        return False, "帳號或密碼錯誤。"

    if str(member.get("status", "active")).lower() != "active":
        return False, "此會員帳號已停用。"

    saved_hash = str(member.get("password_hash", ""))

    if not saved_hash or "$" not in saved_hash:
        return False, "會員資料異常。"

    if not verify_password(password, saved_hash):
        return False, "帳號或密碼錯誤。"

    expires_text = str(member.get("expires", ""))

    try:
        expires_date = date.fromisoformat(expires_text)
    except Exception:
        return False, "會員到期日資料異常。"

    if date.today() > expires_date:
        return False, "會員資格已到期。"

    return True, member


def logout():
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.user_role = "guest"
    st.session_state.member = {}
    st.session_state.analysis_results = None
    st.session_state.last_video_name = ""
    st.session_state.last_video_bytes = None
    st.session_state.last_video_mime = "video/mp4"
    st.session_state.last_video_ext = ".mp4"
    st.rerun()


# =========================================================
# 圖片處理
# =========================================================
def prepare_image(uploaded_file):
    if uploaded_file is None:
        return None, None

    raw = uploaded_file.getvalue()

    if not raw:
        raise ValueError("圖片檔案是空的。")

    size_mb = len(raw) / 1024 / 1024

    if size_mb > MAX_IMAGE_MB:
        raise ValueError(
            f"圖片大小為 {size_mb:.1f} MB，"
            f"不可超過 {MAX_IMAGE_MB} MB。"
        )

    try:
        image = Image.open(io.BytesIO(raw))
        image = ImageOps.exif_transpose(image)
        image.load()

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

        image.thumbnail(
            (MAX_IMAGE_SIZE, MAX_IMAGE_SIZE),
            Image.Resampling.LANCZOS,
        )

        output = io.BytesIO()

        image.save(
            output,
            format="JPEG",
            quality=92,
            optimize=True,
        )

        return image, output.getvalue()

    except Exception as e:
        raise ValueError(f"圖片讀取失敗：{e}")


# =========================================================
# 即夢核心規則
# =========================================================
JIMENG_CORE_RULES = """
【商品身份鎖定】
上傳商品圖片是唯一主要商品來源。

必須維持：
- 原品牌、原包裝、原形狀、原比例、原顏色、原材質、原 Logo、原標籤、原印刷文字、原包裝結構

禁止：
- 改品牌、改包裝、改 Logo、改文字、改顏色、商品變形、商品融化、商品漂移、商品閃爍、商品消失、商品變成其他商品、新增第二個商品、重複商品

預設禁止：
- 人物、手、模特兒、主持人、代言人、人物拿商品

禁止：
- 浮水印、假價格、假折扣、假贈品、假認證、假規格、假功效、醫療效果、未確認資訊

影片全程必須維持同一商品身份。

視覺方向：
premium commercial product photography,
realistic product details,
clean composition,
professional studio lighting,
smooth cinematic camera,
stable product identity.
"""


# =========================================================
# 商品分析 Prompt
# =========================================================
def build_product_analysis_prompt(product_data):
    return f"""
你是「AI 蝦皮半自動化 2.5 PRO」的商品分析 AI。

請分析使用者上傳的商品圖片與使用者輸入。

【使用者資料】
商品名稱：{product_data["product_name"] or "待確認"}
商品價格：{product_data["price"] or "待確認"}
商品成本：{product_data["cost"] or "待確認"}
分潤比例：{product_data["commission"] or "待確認"}
月銷量：{product_data["sales"] or "待確認"}
商品評分：{product_data["rating"] or "待確認"}
商品連結：{product_data["url"] or "待確認"}
商品規格：{product_data["spec"] or "待確認"}
補充資訊：{product_data["features"] or "待確認"}
主要平台：{product_data["platform"]}

【嚴格規則】
1. 不得捏造商品資訊。
2. 圖片看不清楚的資料寫「待確認」。
3. 使用繁體中文。

【輸出】
# 1｜商品辨識
商品名稱、品牌、類別、顏色、外觀、材質、包裝、Logo、可辨識文字、型號、規格。

# 2｜商品特色
列出 3～5 個能由圖片或使用者資料確認的特色。

# 3｜AI 選品分析
- 商品視覺吸引力、電商展示潛力、短影音展示潛力、內容製作難度、合規風險、推薦分數 0～100

# 4｜圖片判斷
圖片清晰度、主要商品、是否多商品、需要人工確認事項。

# 5｜蝦皮展示建議
主圖方向、細節圖方向。

# 6｜TikTok 展示建議
前三秒、商品展示、鏡頭、結尾。

# 7｜即夢 AI 2.5 建議
{JIMENG_CORE_RULES}
"""


# =========================================================
# 完整生成 Prompt
# =========================================================
def build_full_generation_prompt(product_data, analysis):
    return f"""
你是「AI 蝦皮半自動化 2.5 PRO」的專業電商 AI。

根據商品資料與商品圖片分析結果，產生完整電商內容。

【商品資料】
商品名稱：{product_data["product_name"] or "待確認"}
價格：{product_data["price"] or "待確認"}
規格：{product_data["spec"] or "待確認"}

【圖片分析】
{analysis}

【生成需求】
1. 蝦皮完整上架文案（標題、SEO關鍵字、完整描述、特色、規格、注意事項）
2. TikTok 帶貨腳本（3秒Hook、15秒腳本、貼文、Hashtag）
3. Facebook / Instagram 貼文
4. 即夢 AI 2.5 英文生圖與影片 Prompt（含 Positive & Negative Prompt）
5. 15 秒影片分鏡表（至少 5 個鏡頭）
6. 合規檢查與發布前確認事項

【即夢核心規則】
{JIMENG_CORE_RULES}
"""


# =========================================================
# 影片上傳
# =========================================================
VIDEO_MIME_MAP = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
}


def get_video_info(uploaded_file):
    if uploaded_file is None:
        return None

    raw = uploaded_file.getvalue()

    if not raw:
        raise ValueError("影片檔案是空的。")

    size_mb = len(raw) / 1024 / 1024

    if size_mb > MAX_VIDEO_MB:
        raise ValueError(
            f"影片大小 {size_mb:.1f} MB，超過 {MAX_VIDEO_MB} MB 上限。"
        )

    filename = uploaded_file.name or "video.mp4"
    ext = os.path.splitext(filename)[1].lower()

    mime = uploaded_file.type or VIDEO_MIME_MAP.get(
        ext,
        "video/mp4",
    )

    return {
        "name": filename,
        "bytes": raw,
        "mime": mime,
        "ext": ext,
        "size_mb": size_mb,
    }


# =========================================================
# 登入 / 註冊頁面
# =========================================================
def auth_page():
    st.markdown(
        '<div class="main-title">🛒 AI 蝦皮半自動化 2.5 PRO</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="main-subtitle">免費 Gemini Flash × 電商 AI × 即夢 AI 2.5</div>',
        unsafe_allow_html=True,
    )

    tab_login, tab_register = st.tabs(["🔐 登入", "📝 註冊"])

    with tab_login:
        st.subheader("🔑 會員登入")

        username = st.text_input(
            "帳號",
            key="login_username",
        )

        password = st.text_input(
            "密碼",
            type="password",
            key="login_password",
        )

        if st.button(
            "登入",
            type="primary",
            use_container_width=True,
        ):
            success, result = check_login(username, password)

            if success:
                st.session_state.logged_in = True
                st.session_state.username = result["username"]
                st.session_state.user_role = result["role"]
                st.session_state.member = result
                st.success("登入成功！")
                st.rerun()
            else:
                st.error(result)

        st.info("預設管理員測試帳號：admin / admin123")

    with tab_register:
        st.subheader("📝 建立會員")

        name = st.text_input(
            "姓名 / 暱稱",
            key="register_name",
        )

        username = st.text_input(
            "帳號",
            key="register_username",
        )

        email = st.text_input(
            "Email",
            key="register_email",
        )

        password = st.text_input(
            "密碼",
            type="password",
            key="register_password",
        )

        confirm = st.text_input(
            "再次輸入密碼",
            type="password",
            key="register_confirm",
        )

        if st.button(
            "建立帳號",
            use_container_width=True,
        ):
            if password != confirm:
                st.error("兩次密碼不一致。")
            else:
                success, result = create_member(
                    username,
                    password,
                    name,
                    email,
                )

                if success:
                    st.success("🎉 註冊成功！請回到登入頁登入。")
                else:
                    st.error(result)


# =========================================================
# Sidebar
# =========================================================
def sidebar():
    with st.sidebar:
        st.title("🛒 功能選單")

        if st.session_state.logged_in:
            member = st.session_state.member

            st.write(f"👤 **{member.get('name') or member.get('username')}**")
            st.caption(f"帳號：{member.get('username')}")
            st.caption(f"身分：{member.get('role')}")
            st.caption(f"到期日：{member.get('expires')}")

            if st.button(
                "🚪 登出",
                use_container_width=True,
            ):
                logout()
        else:
            st.info("請先登入會員。")

        st.divider()

        st.subheader("🤖 Gemini API 設定")

        key = st.text_input(
            "Gemini API Key",
            value=st.session_state.get("api_key", ""),
            type="password",
            help="不要把 API Key 寫進 GitHub 或公開程式碼。",
        )

        if key != st.session_state.get("api_key", ""):
            st.session_state.api_key = key
            reset_gemini_client()

        if get_gemini_api_key():
            st.success("API Key 已設定")
        else:
            st.warning("尚未設定 API Key")

        st.caption(f"預設模型：{GEMINI_MODEL}")


# =========================================================
# 管理員頁面
# =========================================================
def admin_page():
    st.header("👑 管理員中心")

    members = load_members()

    col1, col2 = st.columns(2)

    with col1:
        st.metric("會員總數", len(members))

    with col2:
        active_count = sum(
            1 for m in members if m.get("status") == "active"
        )
        st.metric("啟用會員", active_count)

    st.divider()

    for member in members:
        username = member.get("username", "")

        if username == ADMIN_USERNAME:
            continue

        with st.expander(f"👤 {username}"):
            st.write(f"姓名：{member.get('name', '')}")
            st.write(f"Email：{member.get('email', '')}")
            st.write(f"角色：{member.get('role', 'member')}")
            st.write(f"狀態：{member.get('status', 'active')}")
            st.write(f"到期：{member.get('expires', '')}")

            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("啟用", key=f"enable_{member['id']}"):
                    update_member(member["id"], {"status": "active"})
                    st.rerun()

            with col2:
                if st.button("停用", key=f"disable_{member['id']}"):
        lse, "會員到期日資料異常。"

    if date.today() > expires_date:
        return False, "會員資格已到期。"

    return True, member


def logout():
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.user_role = "guest"
    st.session_state.member = {}
    st.session_state.analysis_results = None
    st.session_state.last_video_name = ""
    st.session_state.last_video_bytes = None
    st.session_state.last_video_mime = "video/mp4"
    st.session_state.last_video_ext = ".mp4"
    st.rerun()


# =========================================================
# 圖片處理
# =========================================================
def prepare_image(uploaded_file):
    if uploaded_file is None:
        return None, None

    raw = uploaded_file.getvalue()

    if not raw:
        raise ValueError("圖片檔案是空的。")

    size_mb = len(raw) / 1024 / 1024

    if size_mb > MAX_IMAGE_MB:
        raise ValueError(
            f"圖片大小為 {size_mb:.1f} MB，"
            f"不可超過 {MAX_IMAGE_MB} MB。"
        )

    try:
        image = Image.open(io.BytesIO(raw))
        image = ImageOps.exif_transpose(image)
        image.load()

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

        image.thumbnail(
            (MAX_IMAGE_SIZE, MAX_IMAGE_SIZE),
            Image.Resampling.LANCZOS,
        )

        output = io.BytesIO()

        image.save(
            output,
            format="JPEG",
            quality=92,
            optimize=True,
        )

        return image, output.getvalue()

    except Exception as e:
        raise ValueError(f"圖片讀取失敗：{e}")


# =========================================================
# 即夢核心規則
# =========================================================
JIMENG_CORE_RULES = """
【商品身份鎖定】
上傳商品圖片是唯一主要商品來源。

必須維持：
- 原品牌、原包裝、原形狀、原比例、原顏色、原材質、原 Logo、原標籤、原印刷文字、原包裝結構

禁止：
- 改品牌、改包裝、改 Logo、改文字、改顏色、商品變形、商品融化、商品漂移、商品閃爍、商品消失、商品變成其他商品、新增第二個商品、重複商品

預設禁止：
- 人物、手、模特兒、主持人、代言人、人物拿商品

禁止：
- 浮水印、假價格、假折扣、假贈品、假認證、假規格、假功效、醫療效果、未確認資訊

影片全程必須維持同一商品身份。

視覺方向：
premium commercial product photography,
realistic product details,
clean composition,
professional studio lighting,
smooth cinematic camera,
stable product identity.
"""


# =========================================================
# 商品分析 Prompt
# =========================================================
def build_product_analysis_prompt(product_data):
    return f"""
你是「AI 蝦皮半自動化 2.5 PRO」的商品分析 AI。

請分析使用者上傳的商品圖片與使用者輸入。

【使用者資料】
商品名稱：{product_data["product_name"] or "待確認"}
商品價格：{product_data["price"] or "待確認"}
商品成本：{product_data["cost"] or "待確認"}
分潤比例：{product_data["commission"] or "待確認"}
月銷量：{product_data["sales"] or "待確認"}
商品評分：{product_data["rating"] or "待確認"}
商品連結：{product_data["url"] or "待確認"}
商品規格：{product_data["spec"] or "待確認"}
補充資訊：{product_data["features"] or "待確認"}
主要平台：{product_data["platform"]}

【嚴格規則】
1. 不得捏造商品資訊。
2. 圖片看不清楚的資料寫「待確認」。
3. 使用繁體中文。

【輸出】
# 1｜商品辨識
商品名稱、品牌、類別、顏色、外觀、材質、包裝、Logo、可辨識文字、型號、規格。

# 2｜商品特色
列出 3～5 個能由圖片或使用者資料確認的特色。

# 3｜AI 選品分析
- 商品視覺吸引力、電商展示潛力、短影音展示潛力、內容製作難度、合規風險、推薦分數 0～100

# 4｜圖片判斷
圖片清晰度、主要商品、是否多商品、需要人工確認事項。

# 5｜蝦皮展示建議
主圖方向、細節圖方向。

# 6｜TikTok 展示建議
前三秒、商品展示、鏡頭、結尾。

# 7｜即夢 AI 2.5 建議
{JIMENG_CORE_RULES}
"""


# =========================================================
# 完整生成 Prompt
# =========================================================
def build_full_generation_prompt(product_data, analysis):
    return f"""
你是「AI 蝦皮半自動化 2.5 PRO」的專業電商 AI。

根據商品資料與商品圖片分析結果，產生完整電商內容。

【商品資料】
商品名稱：{product_data["product_name"] or "待確認"}
價格：{product_data["price"] or "待確認"}
規格：{product_data["spec"] or "待確認"}

【圖片分析】
{analysis}

【生成需求】
1. 蝦皮完整上架文案（標題、SEO關鍵字、完整描述、特色、規格、注意事項）
2. TikTok 帶貨腳本（3秒Hook、15秒腳本、貼文、Hashtag）
3. Facebook / Instagram 貼文
4. 即夢 AI 2.5 英文生圖與影片 Prompt（含 Positive & Negative Prompt）
5. 15 秒影片分鏡表（至少 5 個鏡頭）
6. 合規檢查與發布前確認事項

【即夢核心規則】
{JIMENG_CORE_RULES}
"""


# =========================================================
# 影片上傳
# =========================================================
VIDEO_MIME_MAP = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
}


def get_video_info(uploaded_file):
    if uploaded_file is None:
        return None

    raw = uploaded_file.getvalue()

    if not raw:
        raise ValueError("影片檔案是空的。")

    size_mb = len(raw) / 1024 / 1024

    if size_mb > MAX_VIDEO_MB:
        raise ValueError(
            f"影片大小 {size_mb:.1f} MB，超過 {MAX_VIDEO_MB} MB 上限。"
        )

    filename = uploaded_file.name or "video.mp4"
    ext = os.path.splitext(filename)[1].lower()

    mime = uploaded_file.type or VIDEO_MIME_MAP.get(
        ext,
        "video/mp4",
    )

    return {
        "name": filename,
        "bytes": raw,
        "mime": mime,
        "ext": ext,
        "size_mb": size_mb,
    }


# =========================================================
# 登入 / 註冊
# =========================================================
def auth_page():
    st.markdown(
        '<div class="main-title">🛒 AI 蝦皮半自動化 2.5 PRO</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="main-subtitle">免費 Gemini Flash × 電商 AI × 即夢 AI 2.5</div>',
        unsafe_allow_html=True,
    )

    tab_login, tab_register = st.tabs(["🔐 登入", "📝 註冊"])

    with tab_login:
        st.subheader("🔑 會員登入")

        username = st.text_input(
            "帳號",
            key="login_username",
        )

        password = st.text_input(
            "密碼",
            type="password",
            key="login_password",
        )

        if st.button(
            "登入",
            type="primary",
            use_container_width=True,
        ):
            success, result = check_login(username, password)

            if success:
                st.session_state.logged_in = True
                st.session_state.username = result["username"]
                st.session_state.user_role = result["role"]
                st.session_state.member = result
                st.success("登入成功！")
                st.rerun()
            else:
                st.error(result)

        st.info("預設管理員測試帳號：admin / admin123")

    with tab_register:
        st.subheader("📝 建立會員")

        name = st.text_input(
            "姓名 / 暱稱",
            key="register_name",
        )

        username = st.text_input(
            "帳號",
            key="register_username",
        )

        email = st.text_input(
            "Email",
            key="register_email",
        )

        password = st.text_input(
            "密碼",
            type="password",
            key="register_password",
        )

        confirm = st.text_input(
            "再次輸入密碼",
            type="password",
            key="register_confirm",
        )

        if st.button(
            "建立帳號",
            use_container_width=True,
        ):
            if password != confirm:
                st.error("兩次密碼不一致。")
            else:
                success, result = create_member(
                    username,
                    password,
                    name,
                    email,
                )

                if success:
                    st.success("🎉 註冊成功！請回到登入頁登入。")
                else:
                    st.error(result)


# =========================================================
# Sidebar
# =========================================================
def sidebar():
    with st.sidebar:
        st.title("🛒 功能選單")

        if st.session_state.logged_in:
            member = st.session_state.member

            st.write(f"👤 **{member.get('name') or member.get('username')}**")
            st.caption(f"帳號：{member.get('username')}")
            st.caption(f"身分：{member.get('role')}")
            st.caption(f"到期日：{member.get('expires')}")

            if st.button(
                "🚪 登出",
                use_container_width=True,
            ):
                logout()
        else:
            st.info("請先登入會員。")

        st.divider()

        st.subheader("🤖 Gemini API 設定")

        key = st.text_input(
            "Gemini API Key",
            value=st.session_state.get("api_key", ""),
            type="password",
            help="不要把 API Key 寫進 GitHub 或公開程式碼。",
        )

        if key != st.session_state.get("api_key", ""):
            st.session_state.api_key = key
            reset_gemini_client()

        if get_gemini_api_key():
            st.success("API Key 已設定")
        else:
            st.warning("尚未設定 API Key")

        st.caption(f"預設模型：{GEMINI_MODEL}")


# =========================================================
# 管理員
# =========================================================
def admin_page():
    st.header("👑 管理員中心")

    members = load_members()

    col1, col2 = st.columns(2)

    with col1:
        st.metric("會員總數", len(members))

    with col2:
        active_count = sum(
            1 for m in members if m.get("status") == "active"
        )
        st.metric("啟用會員", active_count)

    st.divider()

    for member in members:
        username = member.get("username", "")

        if username == ADMIN_USERNAME:
            continue

        with st.expander(f"👤 {username}"):
            st.write(f"姓名：{member.get('name', '')}")
            st.write(f"Email：{member.get('email', '')}")
            st.write(f"角色：{member.get('role', 'member')}")
            st.write(f"狀態：{member.get('status', 'active')}")
            st.write(f"到期：{member.get('expires', '')}")

            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("啟用", key=f"enable_{member['id']}"):
                    update_member(member["id"], {"status": "active"})
                    st.rerun()

            with col2:
                if st.button("停用", key=f"disable_{member['id']}"):
              ember.get("status", "active")).lower() != "active":
        return False, "此會員帳號已停用。"

    saved_hash = str(member.get("password_hash", ""))

    if not saved_hash or "$" not in saved_hash:
        return False, "會員資料異常。"

    if not verify_password(password, saved_hash):
        return False, "帳號或密碼錯誤。"

    expires_text = str(member.get("expires", ""))

    try:
        expires_date = date.fromisoformat(expires_text)
    except Exception:
        return False, "會員到期日資料異常。"

    if date.today() > expires_date:
        return False, "會員資格已到期。"

    return True, member


def logout():
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.user_role = "guest"
    st.session_state.member = {}
    st.session_state.analysis_results = None
    st.session_state.last_video_name = ""
    st.session_state.last_video_bytes = None
    st.session_state.last_video_mime = "video/mp4"
    st.session_state.last_video_ext = ".mp4"
    st.rerun()


# =========================================================
# 圖片處理
# =========================================================
def prepare_image(uploaded_file):
    if uploaded_file is None:
        return None, None

    raw = uploaded_file.getvalue()

    if not raw:
        raise ValueError("圖片檔案是空的。")

    size_mb = len(raw) / 1024 / 1024

    if size_mb > MAX_IMAGE_MB:
        raise ValueError(
            f"圖片大小為 {size_mb:.1f} MB，"
            f"不可超過 {MAX_IMAGE_MB} MB。"
        )

    try:
        image = Image.open(io.BytesIO(raw))
        image = ImageOps.exif_transpose(image)
        image.load()

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

        image.thumbnail(
            (MAX_IMAGE_SIZE, MAX_IMAGE_SIZE),
            Image.Resampling.LANCZOS,
        )

        output = io.BytesIO()

        image.save(
            output,
            format="JPEG",
            quality=92,
            optimize=True,
        )

        return image, output.getvalue()

    except Exception as e:
        raise ValueError(f"圖片讀取失敗：{e}")


# =========================================================
# 即夢核心規則
# =========================================================
JIMENG_CORE_RULES = """
【商品身份鎖定】
上傳商品圖片是唯一主要商品來源。

必須維持：
- 原品牌
- 原包裝
- 原形狀
- 原比例
- 原顏色
- 原材質
- 原 Logo
- 原標籤
- 原印刷文字
- 原包裝結構

禁止：
- 改品牌
- 改包裝
- 改 Logo
- 改文字
- 改顏色
- 商品變形
- 商品融化
- 商品漂移
- 商品閃爍
- 商品消失
- 商品變成其他商品
- 新增第二個商品
- 重複商品

預設禁止：
- 人物
- 手
- 模特兒
- 主持人
- 代言人
- 人物拿商品

禁止：
- 浮水印
- 假價格
- 假折扣
- 假贈品
- 假認證
- 假規格
- 假功效
- 醫療效果
- 未確認資訊

影片全程必須維持同一商品身份。

視覺方向：
premium commercial product photography,
realistic product details,
clean composition,
professional studio lighting,
smooth cinematic camera,
stable product identity.
"""


# =========================================================
# 商品分析 Prompt
# =========================================================
def build_product_analysis_prompt(product_data):
    return f"""
你是「AI 蝦皮半自動化 2.5 PRO」的商品分析 AI。

請分析使用者上傳的商品圖片與使用者輸入。

【使用者資料】
商品名稱：{product_data["product_name"] or "待確認"}
商品價格：{product_data["price"] or "待確認"}
商品成本：{product_data["cost"] or "待確認"}
分潤比例：{product_data["commission"] or "待確認"}
月銷量：{product_data["sales"] or "待確認"}
商品評分：{product_data["rating"] or "待確認"}
商品連結：{product_data["url"] or "待確認"}
商品規格：{product_data["spec"] or "待確認"}
補充資訊：{product_data["features"] or "待確認"}
主要平台：{product_data["platform"]}

【嚴格規則】
1. 不得捏造商品資訊。
2. 圖片看不清楚的資料寫「待確認」。
3. 不可自行創造品牌。
4. 不可自行創造價格。
5. 不可自行創造容量。
6. 不可自行創造成分。
7. 不可自行創造產地。
8. 不可自行創造功效。
9. 不可自行創造醫療效果。
10. 不可自行創造認證。
11. 不可自行創造優惠。
12. 不可自行創造贈品。
13. 多個物品時，選擇最大、最清楚、最主要的商品。
14. 使用繁體中文。
15. 不要假裝擁有即時市場資料。
16. 如果資訊不足，直接標記「待確認」。

【輸出】

# 1｜商品辨識
商品名稱：
品牌：
類別：
顏色：
外觀：
材質：
包裝：
Logo：
可辨識文字：
型號：
規格：

# 2｜商品特色
列出 3～5 個能由圖片或使用者資料確認的特色。

# 3｜AI 選品分析
- 商品視覺吸引力
- 電商展示潛力
- 短影音展示潛力
- 文案製作潛力
- 內容製作難度
- 合規風險
- 推薦分數 0～100

# 4｜圖片判斷
圖片清晰度：
主要商品：
是否多商品：
需要人工確認：

# 5｜蝦皮展示建議
主圖方向：
第二張圖片方向：
商品細節圖方向：

# 6｜TikTok 展示建議
前三秒：
商品展示：
鏡頭：
結尾：

# 7｜即夢 AI 2.5 建議
{JIMENG_CORE_RULES}

最後一定提醒：
正式發布前仍需人工確認商品、價格、規格、品牌、庫存、商品頁與分潤資格。
"""


# =========================================================
# 完整生成 Prompt
# =========================================================
def build_full_generation_prompt(product_data, analysis):
    return f"""
你是「AI 蝦皮半自動化 2.5 PRO」的專業電商 AI。

根據商品資料與商品圖片分析結果，產生完整電商內容。

【商品資料】
商品名稱：{product_data["product_name"] or "待確認"}
價格：{product_data["price"] or "待確認"}
成本：{product_data["cost"] or "待確認"}
分潤比例：{product_data["commission"] or "待確認"}
月銷量：{product_data["sales"] or "待確認"}
商品評分：{product_data["rating"] or "待確認"}
商品連結：{product_data["url"] or "待確認"}
商品規格：{product_data["spec"] or "待確認"}
補充：{product_data["features"] or "待確認"}
主要平台：{product_data["platform"]}

【圖片分析】
{analysis}

【重要規則】
未知資料一律「待確認」。
不得虛構價格、優惠、贈品、認證、成分、容量、產地、功效、醫療效果。
不得誇大。
不得假裝有即時市場資料。

==================================================
【1｜蝦皮完整上架文案】
==================================================
### 商品標題 1
### 商品標題 2
### 商品標題 3
### SEO 關鍵字
### 商品短描述
### 商品完整描述
### 商品特色
### 商品規格
### 使用方式
### 保存方式
### 注意事項
### 購買前提醒

==================================================
【2｜TikTok】
==================================================
### 3 秒 Hook
### 15 秒腳本
### 30 秒腳本
### TikTok 貼文
### Hashtag
### CTA

==================================================
【3｜Facebook】
==================================================
### Facebook 貼文
### 互動問題
### Hashtag

==================================================
【4｜Instagram】
==================================================
### Instagram Caption
### Hashtag

==================================================
【5｜即夢 AI 2.5｜1:1 蝦皮主圖】
==================================================
輸出完整 English Prompt。

要求：
- original product identity
- original packaging
- original logo
- original label
- original visible text
- original color
- original proportions
- realistic
- premium commercial photography
- professional studio lighting
- clean background
- sharp details
- no people
- no hands
- no extra product

### Negative Prompt
必須包含：
text distortion, logo distortion, label distortion,
wrong packaging, wrong product, extra product,
duplicate product, deformed product, watermark,
blur, low quality, people, hands

==================================================
【6｜即夢 AI 2.5｜9:16 商品海報】
==================================================
輸出完整 English Prompt。

要求：
9:16 vertical,
premium advertising,
product centered,
original product identity,
original packaging,
original logo,
original label,
no people,
no hands,
no watermark.

### Negative Prompt

==================================================
【7｜即夢 AI 2.5｜商品細節圖】
==================================================
輸出完整 English Prompt。

要求：
focus on real visible product details,
material texture,
packaging details,
label consistency,
commercial photography,
no invented information.

### Negative Prompt

==================================================
【8｜即夢 AI 2.5｜15 秒影片】
==================================================
輸出完整 English Video Prompt。

格式：

0–3 seconds: Opening
3–7 seconds: Product detail
7–12 seconds: Camera movement + showcase
12–15 seconds: Ending

鏡頭：
slow cinematic push-in,
subtle orbit movement,
smooth camera movement,
stable framing,
premium commercial product video.

商品全程：
same product identity,
same packaging,
same logo,
same label,
same color,
same proportions.

禁止：
people, hands, models, extra products,
duplicate products, product deformation,
product disappearance, logo drift,
text drift, watermark.

### Negative Prompt

==================================================
【9｜15 秒爆款帶貨影片】
==================================================
產生：
- 0–3 秒強視覺 Hook
- 3–7 秒商品細節
- 7–12 秒商品展示＋運鏡
- 12–15 秒穩定收尾

輸出：
### 中文影片腳本
### English Video Prompt
### Negative Prompt
### 建議鏡頭
### 建議節奏
### CTA

注意：
不要虛構商品功效、認證、價格或優惠。

==================================================
【10｜影片分鏡表】
==================================================
輸出至少 5 個鏡頭：

鏡頭 1：
時間：
畫面：
商品位置：
鏡頭：
動作：
音效建議：

鏡頭 2：
時間：
畫面：
商品位置：
鏡頭：
動作：
音效建議：

鏡頭 3：
時間：
畫面：
商品位置：
鏡頭：
動作：
音效建議：

鏡頭 4：
時間：
畫面：
商品位置：
鏡頭：
動作：
音效建議：

鏡頭 5：
時間：
畫面：
商品位置：
鏡頭：
動作：
音效建議：

==================================================
【11｜分潤合規檢查】
==================================================
逐項輸出：
商品與圖片一致：
價格是否確認：
規格是否確認：
品牌是否確認：
商品連結：
是否存在誇大：
是否存在假贈品：
是否存在假認證：
是否存在假價格：
是否存在錯誤規格：
是否存在品牌誤判：

使用：
✅ 通過
⚠️ 需確認
❌ 有問題

==================================================
【12｜發布前檢查】
==================================================
商品：
價格：
規格：
品牌：
庫存：
圖片：
影片：
商品頁：
分潤資格：

最後必須輸出：
「正式發布前仍需人工確認商品、價格、規格、品牌、庫存、商品頁與分潤資格。」

==================================================
【即夢核心規則】
==================================================
{JIMENG_CORE_RULES}
"""


# =========================================================
# 影片上傳
# =========================================================
VIDEO_MIME_MAP = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
}


def get_video_info(uploaded_file):
    if uploaded_file is None:
        return None

    raw = uploaded_file.getvalue()

    if not raw:
        raise ValueError("影片檔案是空的。")

    size_mb = len(raw) / 1024 / 1024

    if size_mb > MAX_VIDEO_MB:
        raise ValueError(
            f"影片大小 {size_mb:.1f} MB，"
            f"超過 {MAX_VIDEO_MB} MB 上限。"
        )

    filename = uploaded_file.name or "video.mp4"
    ext = os.path.splitext(filename)[1].lower()

    mime = uploaded_file.type or VIDEO_MIME_MAP.get(
        ext,
        "video/mp4",
    )

    return {
        "name": filename,
        "bytes": raw,
        "mime": mime,
        "ext": ext,
        "size_mb": size_mb,
    }


# =========================================================
# 登入 / 註冊
# =========================================================
def auth_page():
    st.markdown(
        '<div class="member.get("status", "active")).lower() != "active":
        return False, "此會員帳號已停用。"

    saved_hash = str(member.get("password_hash", ""))

    if not saved_hash or "$" not in saved_hash:
        return False, "會員資料異常。"

    if not verify_password(password, saved_hash):
        return False, "帳號或密碼錯誤。"

    expires_text = str(member.get("expires", ""))

    try:
        expires_date = date.fromisoformat(expires_text)
    except Exception:
        return False, "會員到期日資料異常。"

    if date.today() > expires_date:
        return False, "會員資格已到期。"

    return True, member


def logout():
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.user_role = "guest"
    st.session_state.member = {}
    st.session_state.analysis_results = None
    st.session_state.last_video_name = ""
    st.session_state.last_video_bytes = None
    st.session_state.last_video_mime = "video/mp4"
    st.session_state.last_video_ext = ".mp4"
    st.rerun()


# =========================================================
# 圖片處理
# =========================================================
def prepare_image(uploaded_file):
    if uploaded_file is None:
        return None, None

    raw = uploaded_file.getvalue()

    if not raw:
        raise ValueError("圖片檔案是空的。")

    size_mb = len(raw) / 1024 / 1024

    if size_mb > MAX_IMAGE_MB:
        raise ValueError(
            f"圖片大小為 {size_mb:.1f} MB，"
            f"不可超過 {MAX_IMAGE_MB} MB。"
        )

    try:
        image = Image.open(io.BytesIO(raw))
        image = ImageOps.exif_transpose(image)
        image.load()

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

        image.thumbnail(
            (MAX_IMAGE_SIZE, MAX_IMAGE_SIZE),
            Image.Resampling.LANCZOS,
        )

        output = io.BytesIO()

        image.save(
            output,
            format="JPEG",
            quality=92,
            optimize=True,
        )

        return image, output.getvalue()

    except Exception as e:
        raise ValueError(f"圖片讀取失敗：{e}")


# =========================================================
# 即夢核心規則
# =========================================================
JIMENG_CORE_RULES = """
【商品身份鎖定】
上傳商品圖片是唯一主要商品來源。

必須維持：
- 原品牌
- 原包裝
- 原形狀
- 原比例
- 原顏色
- 原材質
- 原 Logo
- 原標籤
- 原印刷文字
- 原包裝結構

禁止：
- 改品牌
- 改包裝
- 改 Logo
- 改文字
- 改顏色
- 商品變形
- 商品融化
- 商品漂移
- 商品閃爍
- 商品消失
- 商品變成其他商品
- 新增第二個商品
- 重複商品

預設禁止：
- 人物
- 手
- 模特兒
- 主持人
- 代言人
- 人物拿商品

禁止：
- 浮水印
- 假價格
- 假折扣
- 假贈品
- 假認證
- 假規格
- 假功效
- 醫療效果
- 未確認資訊

影片全程必須維持同一商品身份。

視覺方向：
premium commercial product photography,
realistic product details,
clean composition,
professional studio lighting,
smooth cinematic camera,
stable product identity.
"""


# =========================================================
# 商品分析 Prompt
# =========================================================
def build_product_analysis_prompt(product_data):
    return f"""
你是「AI 蝦皮半自動化 2.5 PRO」的商品分析 AI。

請分析使用者上傳的商品圖片與使用者輸入。

【使用者資料】
商品名稱：{product_data["product_name"] or "待確認"}
商品價格：{product_data["price"] or "待確認"}
商品成本：{product_data["cost"] or "待確認"}
分潤比例：{product_data["commission"] or "待確認"}
月銷量：{product_data["sales"] or "待確認"}
商品評分：{product_data["rating"] or "待確認"}
商品連結：{product_data["url"] or "待確認"}
商品規格：{product_data["spec"] or "待確認"}
補充資訊：{product_data["features"] or "待確認"}
主要平台：{product_data["platform"]}

【嚴格規則】
1. 不得捏造商品資訊。
2. 圖片看不清楚的資料寫「待確認」。
3. 不可自行創造品牌。
4. 不可自行創造價格。
5. 不可自行創造容量。
6. 不可自行創造成分。
7. 不可自行創造產地。
8. 不可自行創造功效。
9. 不可自行創造醫療效果。
10. 不可自行創造認證。
11. 不可自行創造優惠。
12. 不可自行創造贈品。
13. 多個物品時，選擇最大、最清楚、最主要的商品。
14. 使用繁體中文。
15. 不要假裝擁有即時市場資料。
16. 如果資訊不足，直接標記「待確認」。

【輸出】

# 1｜商品辨識
商品名稱：
品牌：
類別：
顏色：
外觀：
材質：
包裝：
Logo：
可辨識文字：
型號：
規格：

# 2｜商品特色
列出 3～5 個能由圖片或使用者資料確認的特色。

# 3｜AI 選品分析
- 商品視覺吸引力
- 電商展示潛力
- 短影音展示潛力
- 文案製作潛力
- 內容製作難度
- 合規風險
- 推薦分數 0～100

# 4｜圖片判斷
圖片清晰度：
主要商品：
是否多商品：
需要人工確認：

# 5｜蝦皮展示建議
主圖方向：
第二張圖片方向：
商品細節圖方向：

# 6｜TikTok 展示建議
前三秒：
商品展示：
鏡頭：
結尾：

# 7｜即夢 AI 2.5 建議
{JIMENG_CORE_RULES}

最後一定提醒：
正式發布前仍需人工確認商品、價格、規格、品牌、庫存、商品頁與分潤資格。
"""


# =========================================================
# 完整生成 Prompt
# =========================================================
def build_full_generation_prompt(product_data, analysis):
    return f"""
你是「AI 蝦皮半自動化 2.5 PRO」的專業電商 AI。

根據商品資料與商品圖片分析結果，產生完整電商內容。

【商品資料】
商品名稱：{product_data["product_name"] or "待確認"}
價格：{product_data["price"] or "待確認"}
成本：{product_data["cost"] or "待確認"}
分潤比例：{product_data["commission"] or "待確認"}
月銷量：{product_data["sales"] or "待確認"}
商品評分：{product_data["rating"] or "待確認"}
商品連結：{product_data["url"] or "待確認"}
商品規格：{product_data["spec"] or "待確認"}
補充：{product_data["features"] or "待確認"}
主要平台：{product_data["platform"]}

【圖片分析】
{analysis}

【重要規則】
未知資料一律「待確認」。
不得虛構價格、優惠、贈品、認證、成分、容量、產地、功效、醫療效果。
不得誇大。
不得假裝有即時市場資料。

==================================================
【1｜蝦皮完整上架文案】
==================================================
### 商品標題 1
### 商品標題 2
### 商品標題 3
### SEO 關鍵字
### 商品短描述
### 商品完整描述
### 商品特色
### 商品規格
### 使用方式
### 保存方式
### 注意事項
### 購買前提醒

==================================================
【2｜TikTok】
==================================================
### 3 秒 Hook
### 15 秒腳本
### 30 秒腳本
### TikTok 貼文
### Hashtag
### CTA

==================================================
【3｜Facebook】
==================================================
### Facebook 貼文
### 互動問題
### Hashtag

==================================================
【4｜Instagram】
==================================================
### Instagram Caption
### Hashtag

==================================================
【5｜即夢 AI 2.5｜1:1 蝦皮主圖】
==================================================
輸出完整 English Prompt。

要求：
- original product identity
- original packaging
- original logo
- original label
- original visible text
- original color
- original proportions
- realistic
- premium commercial photography
- professional studio lighting
- clean background
- sharp details
- no people
- no hands
- no extra product

### Negative Prompt
必須包含：
text distortion, logo distortion, label distortion,
wrong packaging, wrong product, extra product,
duplicate product, deformed product, watermark,
blur, low quality, people, hands

==================================================
【6｜即夢 AI 2.5｜9:16 商品海報】
==================================================
輸出完整 English Prompt。

要求：
9:16 vertical,
premium advertising,
product centered,
original product identity,
original packaging,
original logo,
original label,
no people,
no hands,
no watermark.

### Negative Prompt

==================================================
【7｜即夢 AI 2.5｜商品細節圖】
==================================================
輸出完整 English Prompt。

要求：
focus on real visible product details,
material texture,
packaging details,
label consistency,
commercial photography,
no invented information.

### Negative Prompt

==================================================
【8｜即夢 AI 2.5｜15 秒影片】
==================================================
輸出完整 English Video Prompt。

格式：

0–3 seconds: Opening
3–7 seconds: Product detail
7–12 seconds: Camera movement + showcase
12–15 seconds: Ending

鏡頭：
slow cinematic push-in,
subtle orbit movement,
smooth camera movement,
stable framing,
premium commercial product video.

商品全程：
same product identity,
same packaging,
same logo,
same label,
same color,
same proportions.

禁止：
people, hands, models, extra products,
duplicate products, product deformation,
product disappearance, logo drift,
text drift, watermark.

### Negative Prompt

==================================================
【9｜15 秒爆款帶貨影片】
==================================================
產生：
- 0–3 秒強視覺 Hook
- 3–7 秒商品細節
- 7–12 秒商品展示＋運鏡
- 12–15 秒穩定收尾

輸出：
### 中文影片腳本
### English Video Prompt
### Negative Prompt
### 建議鏡頭
### 建議節奏
### CTA

注意：
不要虛構商品功效、認證、價格或優惠。

==================================================
【10｜影片分鏡表】
==================================================
輸出至少 5 個鏡頭：

鏡頭 1：
時間：
畫面：
商品位置：
鏡頭：
動作：
音效建議：

鏡頭 2：
時間：
畫面：
商品位置：
鏡頭：
動作：
音效建議：

鏡頭 3：
時間：
畫面：
商品位置：
鏡頭：
動作：
音效建議：

鏡頭 4：
時間：
畫面：
商品位置：
鏡頭：
動作：
音效建議：

鏡頭 5：
時間：
畫面：
商品位置：
鏡頭：
動作：
音效建議：

==================================================
【11｜分潤合規檢查】
==================================================
逐項輸出：
商品與圖片一致：
價格是否確認：
規格是否確認：
品牌是否確認：
商品連結：
是否存在誇大：
是否存在假贈品：
是否存在假認證：
是否存在假價格：
是否存在錯誤規格：
是否存在品牌誤判：

使用：
✅ 通過
⚠️ 需確認
❌ 有問題

==================================================
【12｜發布前檢查】
==================================================
商品：
價格：
規格：
品牌：
庫存：
圖片：
影片：
商品頁：
分潤資格：

最後必須輸出：
「正式發布前仍需人工確認商品、價格、規格、品牌、庫存、商品頁與分潤資格。」

==================================================
【即夢核心規則】
==================================================
{JIMENG_CORE_RULES}
"""


# =========================================================
# 影片上傳
# =========================================================
VIDEO_MIME_MAP = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
}


def get_video_info(uploaded_file):
    if uploaded_file is None:
        return None

    raw = uploaded_file.getvalue()

    if not raw:
        raise ValueError("影片檔案是空的。")

    size_mb = len(raw) / 1024 / 1024

    if size_mb > MAX_VIDEO_MB:
        raise ValueError(
            f"影片大小 {size_mb:.1f} MB，"
            f"超過 {MAX_VIDEO_MB} MB 上限。"
        )

    filename = uploaded_file.name or "video.mp4"
    ext = os.path.splitext(filename)[1].lower()

    mime = uploaded_file.type or VIDEO_MIME_MAP.get(
        ext,
        "video/mp4",
    )

    return {
        "name": filename,
        "bytes": raw,
        "mime": mime,
        "ext": ext,
        "size_mb": size_mb,
    }


# =========================================================
# 登入 / 註冊
# =========================================================
def auth_page():
    st.markdown(
        '<div class="main-title">🛒 AI 蝦皮半自動化 2.5 PRO</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="main-subtitle">免費 Gemini Flash × 電商 AI × 即夢 AI 2.5</div>',
        unsafe_allow_html=True,
    )

    tab_login, tab_register = st.tabs(["🔐 登入", "📝 註冊"])

    with tab_login:
        st.subheader("🔑 會員登入")

        username = st.text_input(
            "帳號",
            key="login_username",
        )

        password = st.text_input(
            "密碼",
            type="password",
            key="login_password",
        )

        if st.button(
            "登入",
            type="primary",
            use_container_width=True,
        ):
            success, result = check_login(username, password)

            if success:
                st.session_state.logged_in = True
                st.session_state.username = result["username"]
                st.session_state.user_role = result["role"]
                st.session_state.member = result
                st.success("登入成功！")
                st.rerun()
            else:
                st.error(result)

        st.info("管理員測試帳號：admin / admin123")

    with tab_register:
        st.subheader("📝 建立會員")

        name = st.text_input(
            "姓名 / 暱稱",
            key="register_name",
        )

        username = st.text_input(
            "帳號",
            key="register_username",
        )

        email = st.text_input(
            "Email",
            key="register_email",
        )

        password = st.text_input(
            "密碼",
            type="password",
            key="register_password",
        )

        confirm = st.text_input(
            "再次輸入密碼",
            type="password",
            key="register_confirm",
        )

        if st.button(
            "建立帳號",
            use_container_width=True,
        ):
            if password != confirm:
                st.error("兩次密碼不一致。")
            else:
                success, result = create_member(
                    username,
                    password,
                    name,
                    email,
                )

                if success:
                    st.success(
                        "🎉 註冊成功！請回到登入頁登入。"
                    )
                else:
                    st.error(result)


# =========================================================
# Sidebar
# =========================================================
def sidebar():
    with st.sidebar:
        st.title("🛒 功能選單")

        if st.session_state.logged_in:
            member = st.session_state.member

            st.write(
                f"👤 **{member.get('name') or member.get('username')}**"
            )
            st.caption(f"帳號：{member.get('username')}")
            st.caption(f"身分：{member.get('role')}")
            st.caption(f"到期日：{member.get('expires')}")

            if st.button(
                "🚪 登出",
                use_container_width=True,
            ):
                logout()
        else:
            st.info("請先登入會員。")

        st.divider()

        st.subheader("🤖 Gemini API 設定")

        key = st.text_input(
            "Gemini API Key",
            value=st.session_state.get("api_key", ""),
            type="password",
            help="不要把 API Key 寫進 GitHub 或公開程式碼。",
        )

        if key != st.session_state.get("api_key", ""):
            st.session_state.api_key = key
            reset_gemini_client()

        if get_gemini_api_key():
            st.success("API Key 已設定")
        else:
            st.warning("尚未設定 API Key")

        st.caption(f"預設模型：{GEMINI_MODEL}")
        st.caption("免費版：Gemini 負責分析、文案、腳本、Prompt")
        st.caption("影片：產生 Prompt 後交給影片工具製作")


# =========================================================
# 管理員
# =========================================================
def admin_page():
    st.header("👑 管理員中心")

    members = load_members()

    col1, col2 = st.columns(2)

    with col1:
        st.metric("會員總數", len(members))

    with col2:
        active_count = sum(
            1
            for m in members
            if m.get("status") == "active"
        )
        st.metric("啟用會員", active_count)

    st.divider()

    for member in members:
        username = member.get("username", "")

        if username == ADMIN_USERNAME:
            continue

        with st.expander(f"👤 {username}"):
            st.write(f"姓名：{member.get('name', '')}")
            st.write(f"Email：{member.get('email', '')}")
            st.write(f"角色：{member.get('role', 'member')}")
            st.write(f"狀態：{member.get('status', 'active')}")
            st.write(f"到期：{member.get('expires', '')}")

            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button(
                    "啟用",
                    key=f"enable_{member['id']}",
                ):
                    update_member(
                        member["id"],
                        {"status": "active"},
                    )
                    st.rerun()

            with col2:
                if st.button(
                    "停用",
                    key=f"disable_{member['id']}",
                ):
                    update_member(
                        member["id"],
                        {"status": "disabled"},
                    )
                    st.rerun()

            with col3:
                if st.button(
                    "延長 30 天",
                    key=f"extend_{member['id']}",
                ):
                    current = member.get("expires", "")

                    try:
                        old_date = date.fromisoformat(current)
                        base = max(old_date, date.today())
                    except Exception:
                        base = date.today()

                    new_date = (
                        base + timedelta(days=30)
                    ).isoformat()

                    update_member(
                        member["id"],
                        {
                            "expires": new_date,
                            "status": "active",
                        },
                    )
                    st.rerun()


# =========================================================
# 商品分析
# =========================================================
def product_page():
    st.header("🚀 AI 商品分析中心")

    st.caption(
        "免費 Gemini Flash：圖片辨識 → 商品分析 → 文案 → "
        "影片腳本 → 即夢 Prompt"
    )

    col1, col2 = st.columns(2)

    with col1:
        product_name = st.text_input(
            "商品名稱",
            placeholder="例如：保濕修護精華液",
        )

        price = st.text_input(
            "商品價格",
            placeholder="例如：399",
        )

        cost = st.text_input(
            "商品成本",
            placeholder="例如：180",
        )

        commission = st.text_input(
            "分潤比例",
            placeholder="例如：10%",
        )

        sales = st.text_input(
            "月銷量",
            placeholder="例如：1000",
        )

        rating = st.text_input(
            "商品評分",
            placeholder="例如：4.9",
        )

    with col2:
        product_url = st.text_input(
            "商品連結",
            placeholder="貼上蝦皮商品連結",
        )

        product_spec = st.text_area(
            "商品規格",
            placeholder="容量、尺寸、顏色、型號等",
        )

        features = st.text_area(
            "補充商品資訊",
            placeholder="商品特色、優惠、注意事項等",
        )

        platform = st.selectbox(
            "主要平台",
            [
                "蝦皮",
                "TikTok",
                "蝦皮＋TikTok",
                "Facebook",
                "Instagram",
                "全平台",
            ],
        )

    st.divider()

    uploaded_file = st.file_uploader(
        "📷 上傳商品圖片",
        type=["jpg", "jpeg", "png", "webp"],
        key="product_image_upload",
    )

    pil_image = None
    image_bytes = None

    if uploaded_file:
        try:
            pil_image, image_bytes = prepare_image(uploaded_file)

            st.image(
                pil_image,
                caption="商品圖片預覽",
                use_container_width=True,
            )
        except Exception as e:
            st.error(str(e))

    st.divider()

    st.subheader("⚙️ 生成項目")

    selected_items = st.multiselect(
        "選擇要生成的內容",
        [
            "商品辨識",
            "AI 選品分析",
            "蝦皮上架文案",
            "TikTok 文案",
            "Facebook 文案",
            "Instagram 文案",
            "即夢 AI 2.5 生圖 Prompt",
            "即夢 AI 2.5 影片 Prompt",
            "15 秒爆款帶貨影片 Prompt",
            "影片分鏡",
            "分潤合規檢查",
            "完整發布檢查",
        ],
        default=[
            "商品辨識",
            "AI 選品分析",
            "蝦皮上架文案",
            "TikTok 文案",
            "即夢 AI 2.5 生圖 Prompt",
            "即夢 AI 2.5 影片 Prompt",
            "15 秒爆款帶貨影片 Prompt",
            "影片分鏡",
            "分潤合規檢查",
        ],
    )

    start = st.button(
        "🔥 開始 AI 完整分析",
        type="primary",
        use_container_width=True,
    )

    if start:
        if not get_gemini_api_key():
            st.error("❌ 請先設定 Gemini API Key。")
            return

        if not product_name and not image_bytes:
            st.warning(
                "請至少輸入商品名稱或上傳商品圖片。"
            )
            return

        if not selected_items:
            st.warning("請至少選擇一個生成項目。")
            return

        product_data = {
            "product_name": product_name,
            "price": price,
            "cost": cost,
            "commission": commission,
            "sales": sales,
            "rating": rating,
            "url": product_url,
            "spec": product_spec,
            "features": features,
            "platform": platform,
            "selected_items": selected_items,
        }

        with st.spinner(
            "🤖 Gemini Flash 正在分析商品圖片..."
        ):
            analysis_prompt = build_product_analysis_prompt(
                product_data
            )

            analysis = gemini_generate_text(
                analysis_prompt,
                image_bytes=image_bytes,
                image_mime="image/jpeg",
            )

        if analysis.startswith("❌"):
            st.error(analysis)
            return

        with st.spinner(
            "📝 正在產生文案、影片腳本、分鏡與即夢 Prompt..."
        ):
            full_prompt = build_full_generation_prompt(
                product_data,
                analysis,
            )

            generated = gemini_generate_text(full_prompt)

        if generated.startswith("❌"):
            st.error(generated)
            return

        st.session_state.analysis_results = {
            "analysis": analysis,
            "generated": generated,
            "product_data": product_data,
            "created_at": datetime.now().isoformat(),
        }

        st.success("🎉 AI 分析與生成完成！")
        st.rerun()


# =========================================================
# 結果中心
# =========================================================
def results_page():
    st.header("📋 完整結果中心")

    result = st.session_state.analysis_results

    if not result:
        st.info(
            "目前沒有分析結果。請先到「AI 商品分析」開始分析。"
        )
        return

    product_data = result.get("product_data", {})

    st.subheader(
        f"🛒 {product_data.get('product_name') or '商品分析結果'}"
    )

    st.caption(
        f"產生時間：{result.get('created_at', '')}"
    )

    with st.expander(
        "🔍 1｜Gemini 商品辨識與選品分析",
        expanded=True,
    ):
        st.markdown(result.get("analysis", ""))

    with st.expander(
        "📝 2｜完整電商文案＋即夢 Prompt＋影片腳本",
        expanded=True,
    ):
        st.markdown(result.get("generated", ""))

    st.divider()

    all_text = (
        result.get("analysis", "")
        + "\n\n"
        + result.get("generated", "")
    )

    st.subheader("📋 完整結果")

    st.text_area(
        "可直接複製的完整內容",
        value=all_text,
        height=600,
    )

    st.download_button(
        "⬇️ 下載完整 AI 報告",
        data=all_text,
        file_name="ai_shopee_report.txt",
        mime="text/plain",
        use_container_width=True,
    )


# =========================================================
# 影片中心
# =========================================================
def video_page():
    st.header("🎬 影片中心")

    st.caption(
        "將使用即夢或其他影片工具生成的 MP4 / MOV / WEBM "
        "上傳到這裡預覽與下載。"
    )

    st.info(
        "目前免費 Gemini Flash 版負責產生影片腳本、"
        "分鏡與 Prompt，不在本程式直接呼叫付費影片生成 API。"
    )

    uploaded_video = st.file_uploader(
        "🎥 上傳影片",
        type=["mp4", "mov", "webm"],
        key="video_upload",
    )

    if uploaded_video:
        try:
            info = get_video_info(uploaded_video)

            st.session_state.last_video_name = info["name"]
            st.session_state.last_video_bytes = info["bytes"]
            st.session_state.last_video_mime = info["mime"]
            st.session_state.last_video_ext = info["ext"]

            st.success(
                f"影片已載入：{info['name']} "
                f"({info['size_mb']:.1f} MB)"
            )
        except Exception as e:
            st.error(str(e))

    video_bytes = st.session_state.last_video_bytes

    if video_bytes:
        st.markdown(
            '<div class="video-title">🎬 影片預覽</div>',
            unsafe_allow_html=True,
        )

        mime = st.session_state.last_video_mime

        try:
            st.video(video_bytes, format=mime)
        except Exception:
            st.warning(
                "目前瀏覽器可能不支援這個影片格式。"
                "建議轉成 MP4 後重新上傳。"
            )

        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            st.download_button(
                "⬇️ 下載影片",
                data=video_bytes,
                file_name=(
                    st.session_state.last_video_name
                    or "jimeng_video.mp4"
                ),
                mime=mime,
                use_container_width=True,
            )

        with col2:
            if st.button(
                "🗑️ 清除目前影片",
                use_container_width=True,
            ):
                st.session_state.last_video_name = ""
                st.session_state.last_video_bytes = None
                st.session_state.last_video_mime = "video/mp4"
                st.session_state.last_video_ext = ".mp4"
                st.rerun()
    else:
        st.info("尚未上傳影片。")

    st.divider()

    st.subheader("📌 影片格式")

    st.write("MP4：最推薦，瀏覽器相容性最好。")
    st.write("MOV：部分 Android / 瀏覽器可能無法直接播放。")
    st.write("WEBM：部分瀏覽器支援良好，但手機環境可能不同。")

    st.caption(
        "若影片無法預覽，建議使用 MP4（H.264 + AAC）。"
    )


# =========================================================
# 會員中心
# =========================================================
def member_page():
    st.header("👤 會員中心")

    member = st.session_state.member

    if not member:
        st.warning("會員資料不存在。")
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "帳號",
            member.get("username", ""),
        )

    with col2:
        st.metric(
            "身份",
            member.get("role", "member"),
        )

    with col3:
        st.metric(
            "狀態",
            member.get("status", "active"),
        )

    st.divider()

    st.write(f"姓名：{member.get('name', '')}")
    st.write(f"Email：{member.get('email', '')}")
    st.write(f"會員到期日：{member.get('expires', '')}")

    try:
        expire_date = date.fromisoformat(
            member.get("expires", "")
        )

        remaining = (
            expire_date - date.today()
        ).days

        if remaining >= 0:
            st.success(
                f"目前剩餘 {remaining} 天。"
            )
        else:
            st.error("會員資格已到期。")

    except Exception:
        st.warning("無法判斷會員到期日。")


# =========================================================
# 首頁
# =========================================================
def home_page():
    st.markdown(
        '<div class="main-title">🛒 AI 蝦皮半自動化 2.5 PRO</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="main-subtitle">免費 Gemini Flash × 商品分析 × 電商文案 × 影片腳本 × 即夢 AI 2.5</div>',
        unsafe_allow_html=True,
    )

    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("📷 商品圖片分析")
        st.write(
            "上傳商品圖片，Gemini 分析外觀、包裝、"
            "品牌與可辨識資訊。"
        )

    with col2:
        st.subheader("📝 電商內容")
        st.write(
            "一次產生蝦皮、TikTok、Facebook、Instagram "
            "內容。"
        )

    with col3:
        st.subheader("🎬 AI 影片內容")
        st.write(
            "產生 15 秒影片腳本、分鏡、運鏡與即夢影片 Prompt。"
        )

    st.divider()

    st.subheader("🚀 使用流程")

    steps = [
        "1️⃣ 登入會員",
        "2️⃣ 設定 Gemini API Key",
        "3️⃣ 上傳商品圖片",
        "4️⃣ 填寫商品資訊",
        "5️⃣ 開始 AI 分析",
        "6️⃣ 複製即夢 AI 2.5 Prompt",
        "7️⃣ 使用影片工具生成影片",
        "8️⃣ 將 MP4 / MOV / WEBM 上傳到影片中心",
    ]

    for step in steps:
        st.write(step)

    st.divider()

    st.subheader("🆓 免費層級版本的工作方式")

    st.write(
        "Gemini Flash：負責商品圖片分析、文案、"
        "影片腳本、影片分鏡、即夢 Prompt。"
    )

    st.write(
        "影片生成：本程式不偷偷呼叫付費影片 API，"
        "而是把完整影片 Prompt 交給你選擇的影片生成工具。"
    )


# =========================================================
# 主程式
# =========================================================
def main():
    sidebar()

    if not st.session_state.logged_in:
        auth_page()
        return

    st.title("🛒 AI 蝦皮半自動化 2.5 PRO")

    st.caption(
        "免費 Gemini Flash × 商品圖片分析 × 蝦皮 × TikTok × 即夢 AI 2.5"
    )

    tabs = [
        "🏠 首頁",
        "🚀 AI 商品分析",
        "📋 結果中心",
        "🎬 影片中心",
        "👤 會員中心",
    ]

    if st.session_state.user_role == "admin":
        tabs.append("👑 管理員")

    menu = st.tabs(tabs)

    with menu[0]:
        home_page()

    with menu[1]:
        product_page()

    with menu[2]:
        results_page()

    with menu[3]:
        video_page()

    with menu[4]:
        member_page()

    if st.session_state.user_role == "admin":
        with menu[5]:
            admin_page()


if __name__ == "__main__":
    main()
