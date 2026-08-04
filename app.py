import streamlit as st
import os
import json
import base64
import requests
from PIL import Image
import io

# =========================================================
# 1. 頁面配置與基本設定
# =========================================================
APP_NAME = "AI 電商文案與即夢 2.5 Prompt 生成器"

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化 Session State
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_role" not in st.session_state:
    st.session_state.user_role = "guest"
if "username" not in st.session_state:
    st.session_state.username = ""
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None

# API 金鑰 (請於專案中自行設定環境變數，或在此填入)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# =========================================================
# 2. 輔助 API 呼叫函式
# =========================================================
def gemini_generate_text(prompt, image_bytes=None):
    """呼叫 Gemini API 進行文字生成或圖片分析 (使用 REST API)"""
    if not GEMINI_API_KEY:
        return "⚠️ 請先設定 GEMINI_API_KEY 環境變數。"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    
    parts = [{"text": prompt}]
    if image_bytes:
        encoded_image = base64.b64encode(image_bytes).decode('utf-8')
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": encoded_image
            }
        })
        
    payload = {"contents": [{"parts": parts}]}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        res_json = response.json()
        if "candidates" in res_json and len(res_json["candidates"]) > 0:
            return res_json["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return f"❌ API 回應異常：{res_json}"
    except Exception as e:
        return f"❌ 呼叫失敗：{str(e)}"

# =========================================================
# 3. Gemini 商品圖片與文案生成邏輯 (含完整補全 Prompt)
# =========================================================
def analyze_product_image(image_bytes):
    prompt = """
你是專業電商商品圖片分析 AI。
請仔細分析使用者上傳的商品圖片。

重要規則：
1. 不可以憑空捏造圖片看不到的資訊。
2. 看不清楚的品牌、型號、規格、容量、材質，請寫「待確認」。
3. 商品包裝上的文字只能描述你實際看見的內容。
4. 不可以自行發明價格、療效、認證或品牌。
5. 如果圖片中有多個物品，找出最主要、最清楚的商品。
6. 用繁體中文回答。

請按照以下格式：

【商品辨識】
商品名稱：
品牌：
類別：
主要顏色：
外觀：
材質：
包裝：
可辨識文字：
型號：
規格：

【商品賣點】
1.
2.
3.

【商品使用情境】
1.
2.
3.

【圖片判斷】
圖片清晰度：
主要商品：
是否有多商品：
可能需要人工確認的資訊：

【電商建議】
蝦皮展示重點：
TikTok 展示重點：
即夢 AI 2.5 畫面建議：

最後再次提醒：正式發布前仍需人工確認商品資訊與規格。
"""
    return gemini_generate_text(prompt, image_bytes=image_bytes)

def generate_marketing_copy(product_info, analysis_text):
    prompt = f"""
你是一位頂級電商文案大師。請根據以下【商品資訊】與【圖片分析結果】，生成 4 個平台的專屬銷售文案：
1. 蝦皮 (Shopee) - 著重SEO關鍵字、規格標示、活動促銷
2. TikTok - 著重短影音腳本 hook、痛點引發、口語化
3. Facebook - 著重故事行銷、社群互動、詳細特色說明
4. Instagram - 著重視覺感、精簡俐落、Hashtag 標籤

【商品資訊】：{product_info}
【圖片分析】：{analysis_text}

請用繁體中文輸出，並清楚標示各平台區塊。
"""
    return gemini_generate_text(prompt)

def generate_jimeng_prompts(product_info, analysis_text):
    prompt = f"""
你是一位即夢 AI 2.5 (Jimeng AI) 提詞專家。請根據商品特色生成生圖與生成影片的 Prompt。

格式需求：
---
### 🖼️ 即夢 AI 2.5 生圖 Prompt (Image Generation)
**中文提示詞：**
**English Prompt:**
**Negative Prompt (負向提示詞):** text, watermark, bad quality, distorted, extra limbs, blur, logo drift

---
### 🎥 即夢 AI 2.5 運鏡影片 Prompt (Video Generation)
**中文影片提示詞：** (包含鏡頭運軌描述，如：鏡頭緩慢拉近、環繞商品、特寫質感)
**English Video Prompt:**
**運鏡設定建議:** 鏡頭速度 1.0x, 保持商品主體穩定 (no text drift)

【商品資訊】：{product_info}
【圖片分析】：{analysis_text}
"""
    return gemini_generate_text(prompt)

# =========================================================
# 4. 介面模組 (UI Components)
# =========================================================
def login_page():
    st.subheader("🔐 會員登入")
    col1, col2 = st.columns([1, 2])
    with col1:
        username = st.text_input("帳號 (預設: admin)")
        password = st.text_input("密碼 (預設: 1234)", type="password")
        if st.button("登入", type="primary"):
            if username == "admin" and password == "1234":
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.user_role = "admin"
                st.success("登入成功！")
                st.rerun()
            else:
                st.error("帳號或密碼錯誤")

def sidebar():
    with st.sidebar:
        st.title("🛒 功能選單")
        if st.session_state.logged_in:
            st.write(f"👤 歡迎，**{st.session_state.username}**")
            st.caption(f"權限：{st.session_state.user_role}")
            if st.button("登出"):
                st.session_state.logged_in = False
                st.session_state.username = ""
                st.rerun()
        else:
            st.info("請先於右側登入系統。")

# =========================================================
# 5. 主程式頁面 (Main Logic)
# =========================================================
def main():
    sidebar()

    st.title("🛒 AI 全方位電商文案與即夢 2.5 Prompt 生成器")
    st.caption("結合 Gemini 圖片辨識 + 蝦皮/TikTok/FB/IG 文案 + 即夢 AI 2.5 繪圖影片 Prompt")

    if not st.session_state.logged_in:
        login_page()
        return

    # 主分頁
    tab1, tab2 = st.tabs(["🚀 一鍵 AI 分析與生成", "📋 完整結果中心"])

    with tab1:
        st.subheader("1. 填寫商品資訊與上傳圖片")
        col_a, col_b = st.columns([1, 1])
        
        with col_a:
            product_name = st.text_input("商品名稱", placeholder="例：極致保濕修護精華液")
            product_features = st.text_area("補充特點/優惠（選填）", placeholder="例：買一送一、全素可可用、敏感肌適用")
            uploaded_file = st.file_uploader("上傳商品圖片 (JPG/PNG)", type=["jpg", "jpeg", "png"])
            
        with col_b:
            image_bytes = None
            if uploaded_file is not None:
                image_bytes = uploaded_file.read()
                st.image(image_bytes, caption="上傳的商品預覽", use_container_width=True)

        st.divider()

        if st.button("🔥 開始全自動 AI 分析與生成", type="primary", use_container_width=True):
            if not uploaded_file and not product_name:
                st.warning("請至少輸入「商品名稱」或「上傳商品圖片」！")
            else:
                with st.spinner("🤖 Gemini 正在深度分析圖片與文字..."):
                    product_info_combined = f"名稱：{product_name}\n補充：{product_features}"
                    
                    # 1. 分析圖片
                    img_analysis = "未上傳圖片，跳過圖片辨識。"
                    if image_bytes:
                        img_analysis = analyze_product_image(image_bytes)

                    # 2. 生成文案
                    copywriting = generate_marketing_copy(product_info_combined, img_analysis)

                    # 3. 生成即夢 Prompt
                    jimeng_prompts = generate_jimeng_prompts(product_info_combined, img_analysis)

                    # 儲存結果
                    st.session_state.analysis_results = {
                        "img_analysis": img_analysis,
                        "copywriting": copywriting,
                        "jimeng_prompts": jimeng_prompts
                    }
                    st.success("✅ 生成完成！請前往「完整結果中心」或於下方檢視。")

    with tab2:
        st.subheader("📋 AI 生成結果報告")
        if st.session_state.analysis_results is None:
            st.info("尚無分析資料，請先至第一頁點擊生成。")
        else:
            res = st.session_state.analysis_results
            
            with st.expander("🔍 1. Gemini 商品圖片辨識報告", expanded=True):
                st.markdown(res["img_analysis"])

            with st.expander("📝 2. 四大平台社群文案 (蝦皮 / TikTok / FB / IG)", expanded=True):
                st.markdown(res["copywriting"])

            with st.expander("🎨 3. 即夢 AI 2.5 繪圖與影片 Prompt 提詞", expanded=True):
                st.markdown(res["jimeng_prompts"])

if __name__ == "__main__":
    main()
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

APP_NAME = "AI 蝦皮半自動化 2.5 PRO"

DATA_DIR = "data"
MEMBERS_FILE = os.path.join(DATA_DIR, "members.json")

MAX_IMAGE_SIZE = 1600
MAX_IMAGE_MB = 20

# 影片本身可以較大；真正限制仍受 Streamlit Cloud / 主機設定影響
MAX_VIDEO_MB = 300

DEFAULT_MEMBER_DAYS = 30

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

GEMINI_MODEL_CANDIDATES = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
]

VIDEO_MIME_MAP = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
}

VIDEO_TYPE_MAP = {
    "mp4": "video/mp4",
    "mov": "video/quicktime",
    "webm": "video/webm",
}

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

    .video-title {
        font-size: 28px;
        font-weight: 800;
        margin-top: 10px;
        margin-bottom: 10px;
    }

    .small-note {
        opacity: .75;
        font-size: 14px;
    }

    .upload-success {
        padding: 12px 16px;
        border-radius: 10px;
        border: 1px solid rgba(0, 180, 100, .35);
        margin: 10px 0;
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

def create_member(username, password, name, email):
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

    if not verify_password(password, saved_hash):
        return False, "invalid"

    expires_text = str(
        member.get("expires", "")
    )

    try:
        expires_date = date.fromisoformat(expires_text)
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
    "last_product_name": "",

    # 影片中心
    "last_video_name": "",
    "last_video_bytes": None,
    "last_video_mime": "video/mp4",
    "last_video_ext": ".mp4",
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

    st.session_state.last_product_name = ""
    st.session_state.last_video_name = ""
    st.session_state.last_video_bytes = None
    st.session_state.last_video_mime = "video/mp4"
    st.session_state.last_video_ext = ".mp4"

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

    return genai.Client(api_key=api_key)


# =========================================================
# Gemini 錯誤
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
            "系統會自動嘗試下一個模型。\n\n"
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
            "GEMINI_API_KEY\n\n"
            f"原始錯誤：{text}"
        )

    if "403" in lower:
        return (
            "Gemini API 權限不足。\n\n"
            "請確認 Google AI Studio API Key。\n\n"
            f"原始錯誤：{text}"
        )

    if (
        "429" in lower
        or "quota" in lower
        or "resource exhausted" in lower
    ):
        return (
            "Gemini API 額度或速率限制。\n\n"
            "請稍後再試。\n\n"
            f"原始錯誤：{text}"
        )

    if "400" in lower:
        return (
            "Gemini API 請求格式錯誤。\n\n"
            "請確認 google-genai 套件版本。\n\n"
            f"原始錯誤：{text}"
        )

    return (
        "Gemini API 呼叫失敗。\n\n"
        f"詳細錯誤：{text}"
    )


# =========================================================
# Gemini API
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
            "requirements.txt 請加入：\n"
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

            text = getattr(response, "text", None)

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

            model_error = (
                "404" in lower
                or "not_found" in lower
                or "not found" in lower
                or "no longer available" in lower
            )

            if model_error:
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
        raise ValueError("沒有收到圖片檔案。")

    try:
        raw_bytes = uploaded_file.getvalue()

        if not raw_bytes:
            raise ValueError("圖片檔案內容是空的。")

        file_size_mb = len(raw_bytes) / 1024 / 1024

        if file_size_mb > MAX_IMAGE_MB:
            raise ValueError(
                f"圖片太大，目前為 {file_size_mb:.1f} MB，"
                f"請使用 {MAX_IMAGE_MB} MB 以下圖片。"
            )

        image = Image.open(io.BytesIO(raw_bytes))
        image = ImageOps.exif_transpose(image)
        image.load()

        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")

        image.thumbnail(
            (MAX_IMAGE_SIZE, MAX_IMAGE_SIZE),
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
            "請確認 JPG、JPEG、PNG 或 WEBP。\n\n"
            f"詳細錯誤：{error}"
        )


# =========================================================
# 即夢 2.5 核心規則
# =========================================================

JIMENG_25_CORE_RULES = """
【即夢 AI 2.5 商品一致性核心規則】

使用者上傳的商品圖片是唯一主要商品來源。

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
- 重新設計品牌
- 重新設計包裝
- 改變顏色
- 改變瓶身
- 改變盒身
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
- 假折扣
- 假贈品
- 假認證
- 未確認規格
- 未確認功效
- 未確認成分
- 未確認產地
- 未確認醫療效果

影片全程保持同一商品身份。

推薦：
slow cinematic push-in,
subtle orbit movement,
smooth camera movement,
stable framing,
premium commercial product photography.
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

    selected_text = "、".join(selected_items)

    return f"""
你現在是：
「AI 蝦皮半自動化 2.5 PRO」
的 Gemini AI 商品分析核心。

你會收到：
1. 使用者上傳的商品圖片
2. 使用者填寫的商品資料

請嚴格依照圖片與已提供資料分析。
不要把猜測當成事實。

==================================================
【使用者資料】
==================================================

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

==================================================
【核心規則】
==================================================

1. 圖片中的商品是主要商品來源。

2. 如果圖片與文字資料衝突：
「⚠️ 資料衝突，請人工確認。」

3. 不能自行創造：
價格、折扣、贈品、認證、成分、產地、
容量、功效、醫療效果、官方規格。

4. 圖片看不清楚：
「無法從圖片確認，待人工確認。」

5. 圖片有多個商品：
選擇最大、最清楚、品牌辨識度最高的商品作為主商品，
並說明判斷理由。

6. 不能假裝知道官方商品資料。

7. 不得誇大商品效果。

8. 即夢 Prompt 必須維持：
原商品外觀一致、原包裝一致、原 Logo 一致、
原文字一致、原顏色一致、原比例一致。

9. 預設禁止：
人物、手、模特兒、主持人、代言人。

10. 正式發布前必須人工確認。

==================================================
【輸出】
==================================================

# 🛒 AI 蝦皮半自動化 2.5 PRO

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

未知資訊：「待人工確認」

## 2｜AI 選品分析
分析：
- 商品吸引力
- 電商展示潛力
- 短影音展示潛力
- 內容製作潛力
- 競爭程度
- 內容製作難度
- 合規風險
- 推薦分數 0～100
- 推薦等級
- 原因

不要假裝擁有即時市場數據。

## 3｜蝦皮上架文案
### 商品標題 3 組
### 短描述
### 完整商品描述
### 商品特色
### 使用方式
### 保存方式
### 注意事項
### 搜尋關鍵字

所有未知資訊不得自行補充。

## 4｜TikTok 文案
### 3 秒開場
### 15 秒口播
### 30 秒口播
### TikTok 貼文
### Hashtag
### 行動引導

## 5｜即夢 AI 2.5 生圖 Prompt
### A｜1:1 蝦皮商品主圖
輸出完整 English Prompt。
要求：
- 原商品一致
- 原包裝一致
- 原 Logo 一致
- 原文字一致
- 原顏色一致
- 原比例一致
- premium commercial product photography
- realistic
- sharp product details
- clean background
- studio lighting
- no people

### Negative Prompt

### B｜9:16 TikTok 商品海報
輸出完整 English Prompt。
要求：
- 9:16
- vertical
- premium commercial advertising
- product centered
- original product appearance
- original packaging
- original logo
- original label
- no people
- no hands
- no influencer
- no watermark

### Negative Prompt

### C｜商品細節展示圖
輸出完整 English Prompt。

### Negative Prompt

## 6｜即夢 AI 2.5 影片 Prompt
輸出完整 English Prompt。

規格：
9:16 vertical video
15 seconds
commercial product video

Scene 1：
0–3 seconds
Opening

Scene 2：
3–7 seconds
Product detail

Scene 3：
7–12 seconds
Camera movement + product showcase

Scene 4：
12–15 seconds
Ending

鏡頭：
slow cinematic push-in,
subtle orbit movement,
smooth camera movement,
stable framing.

商品全程：
same product identity,
same packaging,
same color,
same logo,
same label,
same proportions.

## 7｜15 秒爆款帶貨影片 Prompt
輸出完整 English Prompt。

0–3 seconds：
強開場

3–7 seconds：
商品細節

7–12 seconds：
鏡頭運動＋產品展示

12–15 seconds：
商品穩定收尾

禁止：
- 商品變形
- 商品消失
- 新增第二商品
- 人物
- 手
- 假價格
- 假贈品
- 假優惠
- 假認證

## 8｜分潤合規檢查
逐項檢查：
- 商品與圖片一致
- 影片與商品一致
- 文案與商品一致
- 商品連結是否存在
- 價格是否已確認
- 規格是否已確認
- 品牌是否已確認
- 功效是否存在誇大
- 是否存在假贈品
- 是否存在假認證
- 是否存在錯誤規格
- 是否存在品牌誤判

使用：
✅ 通過
⚠️ 需確認
❌ 有問題

## 9｜最終發布建議
給出：
- 是否建議製作
- 推薦影片方向
- 推薦主圖方向
- 人工確認事項
- 最後檢查清單

最後一定輸出：
「正式發布前仍需人工確認商品、
價格、規格、品牌、庫存、
商品頁與分潤資格。」

==================================================
【即夢核心規則】
==================================================
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
# ====================================      min_value=0.0,
            value=0.0,
            step=1.0,
        )

    with c2:

        commission = st.number_input(
            "分潤比例 (%)",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=0.5,
        )

        sales = st.number_input(
            "月銷量",
            min_value=0,
            value=0,
            step=1,
        )

        rating = st.number_input(
            "商品評分",
            min_value=0.0,
            max_value=5.0,
            value=0.0,
            step=0.1,
        )

        link = st.text_input(
            "商品連結",
            placeholder="選填",
        )

    specs = st.text_area(
        "商品規格 / 已知資訊",
        placeholder=(
            "輸入尺寸、材質、顏色、"
            "容量、功能等已知資料。"
        ),
    )

    return {
        "name": name,
        "category": category,
        "price": price,
        "cost": cost,
        "commission": commission,
        "sales": sales,
        "rating": rating,
        "link": link,
        "specs": specs,
    }


def product_text(info):
    return (
        f"商品名稱：{info.get('name') or '待確認'}\n"
        f"商品類別：{info.get('category') or '待確認'}\n"
        f"售價：{info.get('price', 0)}\n"
        f"成本：{info.get('cost', 0)}\n"
        f"分潤比例：{info.get('commission', 0)}%\n"
        f"月銷量：{info.get('sales', 0)}\n"
        f"商品評分：{info.get('rating', 0)}\n"
        f"商品連結：{info.get('link') or '未提供'}\n"
        f"商品規格：{info.get('specs') or '待確認'}"
    )


# =========================================================
# IMAGE UPLOAD
# =========================================================

def upload_product():
    st.subheader("📷 商品圖片")

    uploaded = st.file_uploader(
        "上傳商品圖片",
        type=[
            "jpg",
            "jpeg",
            "png",
            "webp",
        ],
        key="main_product_upload",
    )

    if uploaded is not None:

        image_bytes, mime = process_image(
            uploaded
        )

        if image_bytes:

            st.session_state.image_bytes = (
                image_bytes
            )

            st.session_state.image_mime = (
                mime
            )

    if st.session_state.image_bytes:

        st.image(
            st.session_state.image_bytes,
            caption="目前商品圖片",
            use_container_width=True,
        )

        if st.button(
            "🗑️ 清除商品圖片",
            use_container_width=True,
        ):
            st.session_state.image_bytes = None
            st.session_state.image_mime = None
            st.rerun()


# =========================================================
# CORE RULES
# =========================================================

CORE_RULES = """
你是台灣電商 AI 半自動化助手。

最高規則：

1. 不可虛構商品資訊。
2. 不可虛構品牌。
3. 不可虛構型號。
4. 不可虛構規格。
5. 不可虛構容量。
6. 不可虛構材質。
7. 不可虛構成分。
8. 不可虛構認證。
9. 不可捏造價格。
10. 不可捏造折扣。
11. 不可捏造贈品。
12. 不可捏造銷量。
13. 看不清楚的資料寫「待確認」。
14. 不可誇大。
15. 不可保證效果。
16. 不可做醫療療效保證。
17. 使用繁體中文。
18. 適合台灣電商。

商品圖片規則：

1. 商品原貌必須保持一致。
2. 不可任意改變品牌。
3. 不可任意改變包裝。
4. 不可任意改變商品形狀。
5. 不可任意改變比例。
6. 不可任意改變顏色。
7. 不可任意改變材質。
8. 不可任意改變 Logo。
9. 不可任意改變商品文字。
10. 不可產生第二個商品。
11. 不可讓商品融化、變形或漂浮。
12. 不可讓 Logo 扭曲。
13. 不可讓包裝文字漂移。
14. 不可產生水印。
15. 不可產生虛假商品。
""".strip()


# =========================================================
# FEATURE OPTIONS
# =========================================================

FEATURES = [
    "商品辨識",
    "AI 選品分析",
    "蝦皮文案",
    "TikTok 文案",
    "Facebook 文案",
    "Instagram 文案",
    "即夢 AI 2.5 生圖 Prompt",
    "即夢 AI 2.5 影片 Prompt",
    "爆款帶貨影片",
    "利潤 / 分潤分析",
    "合規檢查",
]


def feature_selector():

    st.subheader("🤖 AI 自動生成項目")

    select_all = st.checkbox(
        "☑️ 全部自動勾選",
        value=True,
        key="feature_select_all",
    )

    selected = []

    cols = st.columns(3)

    for index, feature in enumerate(FEATURES):

        with cols[index % 3]:

            checked = st.checkbox(
                feature,
                value=select_all,
                key=f"feature_checkbox_{index}",
            )

            if checked:
                selected.append(feature)

    return selected


# =========================================================
# FULL PROMPT
# =========================================================

def build_full_prompt(
    info,
    selected,
):
    selected_text = "\n".join(
        f"- {item}"
        for item in selected
    )

    return f"""
{CORE_RULES}

你現在是「AI 蝦皮半自動化 2.5 PRO」。

請分析使用者提供的商品圖片與商品資料。

==================================================
【商品資料】

{product_text(info)}

==================================================
【本次需要生成】

{selected_text}

==================================================
【重要要求】

只能根據圖片與使用者提供的資料判斷。

如果圖片看不清楚，請寫「待確認」。

絕對不要猜測品牌、型號、規格、容量、材質、成分、認證、功效或其他商品資訊。

==================================================
【一、商品辨識】

請輸出：

商品類型：
商品名稱：
品牌：
型號：
顏色：
材質：
規格：
包裝：
圖片可確認資訊：
待確認資訊：

==================================================
【二、AI 選品分析】

請輸出：

適合客群：
使用情境：
核心賣點：
購買理由：
視覺賣點：
主圖建議：
短影音方向：
市場切入方向：

==================================================
【三、蝦皮文案】

請生成：

1. 三個商品標題
2. 五個商品賣點
3. 完整商品描述
4. 商品特色
5. 使用情境
6. 購買提醒
7. 搜尋關鍵字
8. CTA

不可虛構資訊。

==================================================
【四、TikTok 文案】

請生成：

1. 五個前三秒 Hook
2. 15～30 秒短影音文案
3. 畫面建議
4. 字幕
5. CTA
6. Hashtag

==================================================
【五、Facebook 文案】

請生成：

1. FB 貼文標題
2. FB 完整貼文
3. FB 短版貼文
4. CTA
5. Hashtag

風格自然，不要過度廣告感。

==================================================
【六、Instagram 文案】

請生成：

1. IG 第一行 Hook
2. IG Caption
3. 完整貼文
4. CTA
5. Hashtag

==================================================
【七、即夢 AI 2.5 生圖 Prompt】

請建立英文 Prompt。

要求：

- 9:16 vertical
- premium commercial photography
- photorealistic
- product as the only main visual focus
- preserve exact product identity
- preserve original packaging
- preserve original logo
- preserve original label
- preserve original colors
- preserve original materials
- preserve original proportions
- no people
- no hands
- no presenter
- no spokesperson
- no extra products
- no duplicate products
- no fake products
- no watermark
- no distorted logo
- no distorted packaging
- no wrong text
- no deformed object

輸出：

【ENGLISH IMAGE PROMPT】

【NEGATIVE PROMPT】

如果需要海報文字，使用繁體中文。

==================================================
【八、即夢 AI 2.5 影片 Prompt】

建立約 15 秒英文影片 Prompt。

比例：

9:16 vertical

Opening：

完整商品展示。
商品置中。
商品清楚可見。

Middle：

slow push-in。

展示：

包裝細節。
材質。
Logo。
商品細節。

Camera：

自然、高級商業廣告運鏡。

Ending：

商品回到中央。
畫面穩定。
最後 freeze frame。

全程：

不要人物。
不要手。
不要主持人。
不要額外商品。
不要商品變形。
不要 Logo 扭曲。
不要文字漂移。
不要水印。

輸出：

【ENGLISH VIDEO PROMPT】

【NEGATIVE PROMPT】

==================================================
【九、爆款帶貨影片】

製作約 20 秒短影音腳本。

0～3 秒：

畫面：
字幕：
旁白：

3～8 秒：

畫面：
字幕：
旁白：

8～14 秒：

畫面：
字幕：
旁白：

14～18 秒：

畫面：
字幕：
旁白：

18～20 秒：

畫面：
字幕：
旁白：
CTA：

另外提供：

三個影片標題。
三個封面文字。
五個 Hook。

==================================================
【十、利潤 / 分潤分析】

已知：

售價：{info.get("price", 0)}
成本：{info.get("cost", 0)}
分潤比例：{info.get("commission", 0)}%

請計算：

分潤金額：
預估利潤：
利潤率：

計算方式：

分潤金額 = 售價 × 分潤比例

預估利潤 = 售價 - 成本 - 分潤金額

利潤率 = 預估利潤 ÷ 售價 × 100%

如果售價或成本不足，請標示「待確認」。

==================================================
【十一、合規檢查】

檢查：

- 誇大
- 醫療宣稱
- 虛假保證
- 虛構折扣
- 虛構贈品
- 虛構規格
- 虛構品牌
- 虛構功能
- 虛構認證
- 虛構價格

最後提供：

【合規檢查結果】

==================================================

請使用清楚的繁體中文。

不要省略任何被勾選的項目。
""".strip()


# =========================================================
# RUN ANALYSIS
# =========================================================

def run_analysis(
    info,
    selected,
):
    if not selected:
        st.error(
            "至少選擇一個 AI 功能。"
        )
        return

    if not st.session_state.image_bytes:
        st.error(
            "請先上傳商品圖片。"
        )
        return

    prompt = build_full_prompt(
        info,
        selected,
    )

    progress = st.progress(
        0,
        text="準備 Gemini AI 分析...",
    )

    progress.progress(
        20,
        text="正在分析商品圖片...",
    )

    result, error = gemini_generate(
        prompt,
        st.session_state.image_bytes,
        st.session_state.image_mime or "image/jpeg",
    )

    progress.progress(
        100,
        text="AI 分析完成",
    )

    if error:
        st.error(error)
        return

    st.session_state.product_data = info
    st.session_state.selected_features = selected
    st.session_state.full_result = result
    st.session_state.last_run = (
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    st.success(
        "🎉 AI 全部分析完成！"
    )


# =========================================================
# RESULT CENTER
# =========================================================

def result_center():

    result = st.session_state.full_result

    if not result:
        return

    st.divider()

    st.subheader(
        "📋 完整結果中心"
    )

    if st.session_state.last_run:
        st.caption(
            "最後分析時間："
            + st.session_state.last_run
        )

    st.text_area(
        "AI 完整結果",
        value=result,
        height=900,
    )

    c1, c2 = st.columns(2)

    with c1:
        st.download_button(
            "⬇️ 下載完整結果 TXT",
            data=result,
            file_name="AI_蝦皮半自動化_完整結果.txt",
            mime="text/plain",
            use_container_width=True,
        )

    with c2:

        if st.button(
            "🗑️ 清除分析結果",
            use_container_width=True,
        ):
            st.session_state.full_result = ""
            st.session_state.last_run = None
            st.rerun()


# =========================================================
# LOGIN
# =========================================================

def login_page():

    st.markdown(
        '<div class="main-title">🛒 AI 蝦皮半自動化 2.5 PRO</div>',
        unsafe_allow_html=True,
    )

    st.caption(
        "Gemini AI 電商商品分析與內容生成系統"
    )

    st.divider()

    c1, c2, c3 = st.columns(
        [1, 2, 1]
    )

    with c2:

        st.subheader("🔐 會員登入")

        username = st.text_input(
            "帳號",
           min_value=0.0,
            max_value=5.0,
            value=0.0,
            step=0.1,
            key="product_rating",
        )

        link = st.text_input(
            "商品連結",
            placeholder="選填",
            key="product_link",
        )

    specs = st.text_area(
        "商品規格 / 已知資訊",
        placeholder="輸入你知道的規格、尺寸、材質、顏色等；不知道就留空。",
        key="product_specs",
    )

    return {
        "name": name,
        "category": category,
        "price": price,
        "cost": cost,
        "commission": commission,
        "sales": sales,
        "rating": rating,
        "link": link,
        "specs": specs,
    }


def upload_product():
    st.subheader("📷 商品圖片")

    uploaded = st.file_uploader(
        "上傳商品圖片",
        type=["jpg", "jpeg", "png", "webp"],
        key="main_product_upload",
    )

    if uploaded is not None:
        image_bytes, mime = process_image(uploaded)
        if image_bytes:
            st.session_state.image_bytes = image_bytes
            st.session_state.image_mime = mime

    if st.session_state.image_bytes:
        st.image(
            st.session_state.image_bytes,
            caption="目前商品圖片",
            use_container_width=True,
        )

        if st.button("🗑️ 清除目前商品圖片", use_container_width=True):
            st.session_state.image_bytes = None
            st.session_state.image_mime = None
            st.rerun()


ALL_FEATURES = [
    "商品辨識",
    "AI 選品分析",
    "蝦皮文案",
    "TikTok 文案",
    "Facebook 文案",
    "Instagram 文案",
    "即夢 AI 2.5 生圖 Prompt",
    "即夢 AI 2.5 影片 Prompt",
    "爆款帶貨影片",
    "利潤 / 分潤分析",
    "合規檢查",
]


def auto_options():
    st.subheader("☑️ AI 自動生成項目")
    st.caption("預設全部勾選。你可以取消不需要的項目。")

    select_all = st.checkbox(
        "☑️ 全部自動勾選",
        value=True,
        key="select_all_features",
    )

    selected = []
    cols = st.columns(3)

    for index, option in enumerate(ALL_FEATURES):
        key = f"feature_{index}"

        if select_all:
            if key not in st.session_state:
                st.session_state[key] = True
            else:
                st.session_state[key] = True

        with cols[index % 3]:
            checked = st.checkbox(
                option,
                value=st.session_state.get(key, True),
                key=key,
            )

            if checked:
                selected.append(option)

    return selected


def build_full_prompt(info, selected):
    selected_text = "\n".join(f"- {item}" for item in selected)

    return f"""
{CORE_RULES}

請分析使用者提供的商品圖片與商品資料。

【商品資料】
{product_text(info)}

【本次需要生成】
{selected_text}

請嚴格依照以下結構輸出。沒有資料就寫「待確認」，不要猜。

==================================================
【一、商品辨識】
商品類型：
商品名稱：
品牌：
型號：
顏色：
材質：
規格：
包裝：
圖片可確認資訊：
待確認資訊：

==================================================
【二、AI 選品分析】
適合客群：
使用情境：
核心賣點：
購買理由：
視覺賣點：
主圖建議：
短影音方向：
市場切入方向：

==================================================
【三、蝦皮文案】
1. 三個商品標題
2. 五個商品賣點
3. 完整商品描述
4. 商品特色
5. 使用情境
6. 購買提醒
7. 搜尋關鍵字
8. CTA

==================================================
【四、TikTok 文案】
1. 五個前三秒 Hook
2. 15～30 秒短影音文案
3. 畫面建議
4. 字幕
5. CTA
6. Hashtag

==================================================
【五、Facebook 文案】
1. FB 貼文標題
2. FB 完整貼文
3. FB 短版貼文
4. CTA
5. Hashtag

要求自然，不要過度廣告感。

==================================================
【六、Instagram 文案】
1. IG 第一行 Hook
2. IG Caption
3. 完整貼文
4. CTA
5. Hashtag

==================================================
【七、即夢 AI 2.5 生圖 Prompt】
請建立英文 Prompt。

規格：
- 9:16 vertical
- premium commercial photography
- photorealistic
- product as the only main visual focus
- preserve exact product identity
- preserve original packaging
- preserve original logo
- preserve original label
- preserve original colors
- preserve original materials
- preserve original proportions
- no people
- no hands
- no presenter
- no spokesperson
- no extra products
- no fake products
- no watermark
- no distorted logo
- no distorted packaging
- no wrong text
- no deformed object
- no duplicate product

如果需要海報文字，海報文字使用繁體中文。

輸出：
【ENGLISH IMAGE PROMPT】
【NEGATIVE PROMPT】

==================================================
【八、即夢 AI 2.5 影片 Prompt】
建立約 15 秒英文影片 Prompt。

比例：9:16 vertical

Opening：
完整商品展示，商品置中，商品清楚可見。

Middle：
slow push-in，展示包裝細節、材質、Logo、商品細節。

Camera：
自然、高級、穩定的商業廣告運鏡。

Ending：
商品回到中央，畫面穩定，最後 freeze frame。

全程：
不要人物、手、主持人、額外商品、商品變形、Logo 扭曲、文字漂移、水印。

輸出：
【ENGLISH VIDEO PROMPT】
【NEGATIVE PROMPT】

==================================================
【九、爆款帶貨影片】
製作約 20 秒短影音腳本。

0～3 秒：
畫面：
字幕：
旁白：

3～8 秒：
畫面：
字幕：
旁白：

8～14 秒：
畫面：
字幕：
旁白：

14～18 秒：
畫面：
字幕：
旁白：

18～20 秒：
畫面：
字幕：
旁白：
CTA：

另外提供：
三個影片標題
三個封面文字
五個 Hook

==================================================
【十、利潤 / 分潤分析】

售價：{info.get("price", 0)}
成本：{info.get("cost", 0)}
分潤比例：{info.get("commission", 0)}%

請計算：
分潤金額：
預估利潤：
利潤率：

計算方式：
分潤金額 = 售價 × 分潤比例
預估利潤 = 售價 - 成本 - 分潤金額
利潤率 = 預估利潤 ÷ 售價 × 100%

如果售價或成本不足，請標示「待確認」，不要自行猜數字。

==================================================
【十一、合規檢查】

檢查：
- 誇大
- 醫療宣稱
- 虛假保證
- 虛構折扣
- 虛構贈品
- 虛構規格
- 虛構品牌
- 虛構功能
- 不可確認的商品資訊

最後提供：
【合規檢查結果】
風險項目：
修正建議：
整體判定：

==================================================

只輸出清楚、可直接使用的繁體中文結果。
不要省略被勾選的功能。
""".strip()


def run_full_analysis(info, selected):
    if not selected:
        st.error("至少選擇一個 AI 功能。")
        return

    if not st.session_state.image_bytes:
        st.error("請先上傳商品圖片。")
        return

    if not st.session_state.gemini_api_key:
        st.error("請先在左側輸入 Gemini API Key。")
        return

    prompt = build_full_prompt(info, selected)

    with st.spinner("Gemini 正在分析商品圖片與生成內容，請稍候..."):
        result, error = gemini_generate(
            prompt,
            st.session_state.image_bytes,
            st.session_state.image_mime or "image/jpeg",
        )

    if error:
        st.error(error)
        return

    st.session_state.full_result = {
        "商品資料": product_text(info),
        "選擇功能": selected,
        "完整 AI 結果": result,
    }
    st.session_state.product_data = info
    st.session_state.last_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    st.success("🎉 AI 全部分析完成！")


def result_center():
    data = st.session_state.get("full_result", {})

    if not data:
        return

    st.divider()
    st.header("📋 完整結果中心")

    if st.session_state.last_run:
        st.caption(f"最後分析：{st.session_state.last_run}")

    result_text = data.get("完整 AI 結果", "")

    st.text_area(
        "AI 完整結果",
        value=result_text,
        height=900,
        key="final_result_text",
    )

    c1, c2 = st.columns(2)

    with c1:
        st.download_button(
            "⬇️ 下載完整結果 TXT",
            data=result_text,
            file_name="AI_蝦皮半自動化_2.5_PRO_結果.txt",
            mime="text/plain",
            use_container_width=True,
        )

    with c2:
        if st.button("🧹 清除本次結果", use_container_width=True):
            st.session_state.full_result = {}
            st.session_state.last_run = None
            st.rerun()


def login_page():
    st.markdown(
        f'<div class="main-title">🛒 {APP_NAME}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sub-title">Gemini 商品圖片辨識＋電商內容半自動化</div>',
        unsafe_allow_html=True,
    )

    tab1, tab2 = st.tabs(["🔐 會員登入", "📝 註冊永久會員"])

    with tab1:
        username = st.text_input("帳號", key="login_username")
        password = st.text_input("密碼", type="password", key="login_password")

        if st.button("登入", type="primary", use_container_width=True):
            member = find_member(username)

            if not member:
                st.error("帳號或密碼錯誤。")
            elif member.get("status") != "active":
                st.error("此會員帳號目前不是啟用狀態。")
            elif not verify_password(password, member.get("password_hash", "")):
                st.error("帳號或密碼錯誤。")
            elif member_expired(member):
                st.error("會員已到期。")
            else:
                st.session_state.logged_in = True
                st.session_state.username = member["username"]
                st.session_state.member = member
                st.session_state.page = "首頁"
                st.rerun()

        st.info("測試管理員：帳號 admin / 密碼 admin123")

    with tab2:
        name = st.text_input("姓名", key="register_name")
        email = st.text_input("Email", key="register_email")
        username = st.text_input("註冊帳號", key="register_username")
        password = st.text_input(
            "註冊密碼",
            type="password",
            key="register_password",
        )
        password2 = st.text_input(
            "再次輸入密碼",
            type="password",
            key="register_password2",
        )

        if st.button("建立永久會員", use_container_width=True):
            if password != password2:
                st.error("兩次密碼不一致。")
            else:
                ok, message = create_member(username, password, name, email)
                if ok:
                    st.success(message)
                else:
                    st.error(message)


def sidebar():
    with st.sidebar:
        st.markdown(f"## 🛒 {APP_NAME}")

        member = st.session_state.get("member") or {}

        st.success(
            f"登入：{member.get('name') or st.session_state.get('username', '')}"
        )

        st.caption("會員：永久")
        st.caption(f"角色：{member.get('role', 'member')}")

        st.divider()

        st.subheader("🤖 Gemini 設定")

        api_key = st.text_input(
            "Gemini API Key",
            type="password",
            value=st.session_state.get("gemini_api_key", ""),
            placeholder="貼上你的 Gemini API Key",
            help="API Key 只放在目前 Streamlit 工作階段，不寫入 members.json。",
        )
        st.session_state.gemini_api_key = api_key.strip()

        model = st.selectbox(
            "Gemini 模型",
            GEMINI_MODELS,
            index=(
                GEMINI_MODELS.index(st.session_state.gemini_model)
                if st.session_state.gemini_model in GEMINI_MODELS
                else 0
            ),
        )
        st.session_sta

# =========================================================
# APP SETTINGS
# =========================================================

APP_NAME = "AI 蝦皮半自動化 2.5 PRO"

DATA_DIR = Path("data")
MEMBERS_FILE = DATA_DIR / "members.json"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

MAX_IMAGE_SIZE = 1600

GEMINI_MODEL = "gemini-2.5-flash"


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# CSS
# =========================================================

st.markdown(
    """
<style>

html,
body,
[class*="css"] {
    font-family:
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        "Noto Sans TC",
        "Microsoft JhengHei",
        sans-serif;
}

.block-container {
    max-width: 1450px;
    padding-top: 1rem;
    padding-left: 1rem;
    padding-right: 1rem;
    padding-bottom: 4rem;
}

.hero {
    padding: 30px;
    border-radius: 24px;
    background:
        linear-gradient(
            135deg,
            #111111,
            #333333
        );
    color: white;
    margin-bottom: 20px;
    box-shadow:
        0 12px 35px rgba(0, 0, 0, .15);
}

.hero h1 {
    margin-bottom: 8px;
}

.card {
    padding: 20px;
    border-radius: 18px;
    border: 1px solid rgba(120, 120, 120, .20);
    background: rgba(128, 128, 128, .05);
    margin-bottom: 16px;
}

.permanent {
    padding: 16px 20px;
    border-radius: 16px;
    background: rgba(0, 180, 100, .10);
    border: 1px solid rgba(0, 180, 100, .18);
    margin-bottom: 18px;
}

.auto-box {
    padding: 18px;
    border-radius: 16px;
    background: rgba(80, 130, 255, .08);
    border: 1px solid rgba(80, 130, 255, .20);
    margin-bottom: 18px;
}

.result-title {
    font-size: 1.2rem;
    font-weight: 700;
    margin-top: 20px;
}

.small-note {
    color: #777;
    font-size: .9rem;
}

</style>
""",
    unsafe_allow_html=True,
)


# =========================================================
# SESSION STATE
# =========================================================

DEFAULT_STATE = {
    "logged_in": False,
    "username": "",
    "member": None,

    "page": "首頁",

    "gemini_api_key": "",

    "image_bytes": None,
    "image_mime": None,

    "product_data": {},

    "full_result": {},

    "last_run": None,

    "select_all_features": True,

    "feature_0": True,
    "feature_1": True,
    "feature_2": True,
    "feature_3": True,
    "feature_4": True,
    "feature_5": True,
    "feature_6": True,
    "feature_7": True,
    "feature_8": True,
    "feature_9": True,
    "feature_10": True,
}


for key, value in DEFAULT_STATE.items():

    if key not in st.session_state:

        st.session_state[key] = value


# =========================================================
# MEMBER DATABASE
# =========================================================

def ensure_data_dir():

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


def load_members():

    ensure_data_dir()

    if not MEMBERS_FILE.exists():

        data = {
            "members": []
        }

        save_members(data)

        return data

    try:

        with open(
            MEMBERS_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if not isinstance(
            data,
            dict
        ):

            return {
                "members": []
            }

        if not isinstance(
            data.get("members"),
            list
        ):

            data["members"] = []

        return data

    except Exception:

        return {
            "members": []
        }


def save_members(data):

    ensure_data_dir()

    temp_file = MEMBERS_FILE.with_suffix(
        ".tmp"
    )

    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )

    temp_file.replace(
        MEMBERS_FILE
    )


def hash_password(password):

    salt = secrets.token_hex(16)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        str(password).encode("utf-8"),
        salt.encode("utf-8"),
        120000,
    )

    return (
        f"{salt}${digest.hex()}"
    )


def verify_password(
    password,
    stored
):

    try:

        salt, saved_hash = stored.split(
            "$",
            1
        )

        digest = hashlib.pbkdf2_hmac(
            "sha256",
            str(password).encode("utf-8"),
            salt.encode("utf-8"),
            120000,
        )

        return secrets.compare_digest(
            digest.hex(),
            saved_hash
        )

    except Exception:

        return False


def find_member(username):

    username = str(
        username or ""
    ).strip().lower()

    data = load_members()

    for member in data.get(
        "members",
        []
    ):

        saved_username = str(
            member.get(
                "username",
                ""
            )
        ).strip().lower()

        if saved_username == username:

            return member

    return None


def create_default_admin():

    existing = find_member(
        ADMIN_USERNAME
    )

    if existing:

        return

    data = load_members()

    admin = {

        "username": ADMIN_USERNAME,

        "password_hash":
            hash_password(
                ADMIN_PASSWORD
            ),

        "name": "系統管理員",

        "email": "",

        "role": "admin",

        "status": "active",

        "membership": "permanent",

        "expires": None,

        "created_at":
            datetime.now().isoformat(),

        "provider": "local",
    }

    data["members"].append(
        admin
    )

    save_members(data)


def create_member(
    username,
    password,
    name,
    email
):

    username = str(
        username or ""
    ).strip().lower()

    password = str(
        password or ""
    )

    name = str(
        name or ""
    ).strip()

    email = str(
        email or ""
    ).strip()

    if len(username) < 3:

        return (
            False,
            "帳號至少 3 個字元。"
        )

    if len(password) < 6:

        return (
            False,
            "密碼至少 6 個字元。"
        )

    if find_member(username):

        return (
            False,
            "帳號已存在。"
        )

    data = load_members()

    member = {

        "username": username,

        "password_hash":
            hash_password(
                password
            ),

        "name": name,

        "email": email,

        "role": "member",

        "status": "active",

        "membership": "permanent",

        "expires": None,

        "created_at":
            datetime.now().isoformat(),

        "provider": "local",
    }

    data["members"].append(
        member
    )

    save_members(data)

    return (
        True,
        "永久會員建立成功。"
    )


def update_member(
    username,
    **updates
):

    data = load_members()

    found = False

    for member in data.get(
        "members",
        []
    ):

        saved_username = str(
            member.get(
                "username",
                ""
            )
        ).lower()

        if saved_username == str(
            username
        ).lower():

            member.update(
                updates
            )

            found = True

            break

    if found:

        save_members(data)

    return found


# =========================================================
# PERMANENT MEMBERSHIP
# =========================================================

def member_expired(member):

    # =====================================================
    # 永久會員版本
    #
    # 不檢查 expires
    # 不計算日期
    # 不會自動到期
    # =====================================================

    return False


create_default_admin()


# =========================================================
# GEMINI
# =========================================================

def get_gemini_client(api_key):

    api_key = str(
        api_key or ""
    ).strip()

    if not api_key:

        return (
            None,
            "尚未設定 Gemini API Key。"
        )

    try:

        from google import genai

        client = genai.Client(
            api_key=api_key
        )

        return (
            client,
            None
        )

    except ImportError:

        return (
            None,
            "找不到 google-genai。"
            "請確認 requirements.txt 已加入 google-genai。"
        )

    except Exception as error:

        return (
            None,
            f"Gemini 初始化失敗：{error}"
        )


def gemini_generate(
    prompt,
    image_bytes=None,
    mime_type="image/jpeg"
):

    api_key = st.session_state.get(
        "gemini_api_key",
        ""
    )

    client, error = get_gemini_client(
        api_key
    )

    if error:

        return (
            None,
            error
        )

    try:

        from google.genai import types

        contents = []

        if image_bytes:

            contents.append(
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type,
                )
            )

        contents.append(
            prompt
        )

        response = (
            client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
            )
        )

        text = getattr(
            response,
            "text",
            None
        )

        if not text:

            return (
                None,
                "Gemini 沒有回傳內容。"
            )

        return (
            text.strip(),
            None
        )

    except Exception as error:

        return (
            None,
            f"Gemini API 錯誤：{error}"
        )


# =========================================================
# IMAGE PROCESSING
# =========================================================

def process_image(
    uploaded
):

    if uploaded is None:

        return (
            None,
            None
        )

    try:

        image = Image.open(
            uploaded
        )

        image = ImageOps.exif_transpose(
            image
        )

        if image.mode not in (
            "RGB",
            "RGBA"
        ):

            image = image.convert(
                "RGB"
            )

        width, height = image.size

        longest_side = max(
            width,
            height
        )

        if longest_side > MAX_IMAGE_SIZE:

            scale = (
                MAX_IMAGE_SIZE
                / longest_side
            )

            image = image.resize(
                (
                    max(
                        1,
                        int(
                            width * scale
                        )
                    ),
                    max(
                        1,
                        int(
                            height * scale
                        )
                    ),
                ),
                Image.Resampling.LANCZOS
            )

        output = io.BytesIO()

        if image.mode == "RGBA":

            image.save(
                output,
                format="PNG",
                optimize=True
            )

            mime = "image/png"

        else:

            image = image.convert(
                "RGB"
            )

            image.save(
                output,
                format="JPEG",
                quality=92,
                optimize=True
            )

            mime = "image/jpeg"

        return (
            output.getvalue(),
            mime
        )

    except Exception as error:

        st.error(
            f"圖片處理失敗：{error}"
        )

        return (
            None,
            None
        )


# =========================================================
# PRODUCT FORM
# =========================================================

def product_form():

    st.subheader(
        "📦 商品資料"
    )

    c1, c2 = st.columns(2)

    with c1:

        name = st.text_input(
            "商品名稱",
            placeholder="例如：保溫杯"
        )

        category = st.selectbox(
            "商品類別",
            [
                "待確認",
                "保養品",
                "3C",
                "居家",
                "服飾",
                "食品",
                "汽機車",
                "生活用品",
                "其他",
            ]
        )

        price = st.number_input(
            "售價",
            min_value=0.0,
            value=0.0,
            step=1.0
        )

        cost = st.number_input(
            "成本",
            min_value=0.0,
            value=0.0,
            step=1.0
        )

    with c2:

        commission = st.number_input(
            "分潤比例 (%)",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=0.5
        )

        sales = st.number_input(
            "月銷量",
            min_value=0,
            value=0,
            step=1
        )

        rating = st.number_input(
            "商品評分",
            min_value=0.0,
            max_value=5.0,
            value=0.0,
            step=0.1
        )

        link = st.text_input(
            "商品連結",
            placeholder="選填"
        )

    specs = st.text_area(
        "商品規格 / 已知資訊",
        placeholder=(
            "輸入你知道的規格、"
            "尺寸、材質、顏色等..."
        )
    )

    return {

        "name": name,

        "category": category,

        "price": price,

        "cost": cost,

        "commission": commission,

        "sales": sales,

        "rating": rating,

        "link": link,

        "specs": specs,
    }


def product_text(info):

    return f"""
商品名稱：{info.get("name") or "待確認"}
商品類別：{info.get("category") or "待確認"}
售價：{info.get("price", 0)}
成本：{info.get("cost", 0)}
分潤比例：{info.get("commission", 0)}%
月銷量：{info.get("sales", 0)}
商品評分：{info.get("rating", 0)}
商品連結：{info.get("link") or "未提供"}
商品規格：{info.get("specs") or "待確認"}
"""


# =========================================================
# UPLOAD PRODUCT
# =========================================================

def upload_product():

    st.subheader(
        "📷 商品圖片"
    )

    uploaded = st.file_uploader(
        "上傳商品圖片",
        type=[
            "jpg",
            "jpeg",
            "png",
            "webp"
        ],
        key="main_product_upload",
    )

    if uploaded:

        image_bytes, mime = process_image(
            uploaded
        )

        if image_bytes:

            st.session_state.image_bytes = (
                image_bytes
            )

            st.session_state.image_mime = (
                mime
            )

    if st.session_state.image_bytes:

        st.image(
            st.session_state.image_bytes,
            caption="目前商品圖片",
            use_container_width=True
        )

        if st.button(
            "🗑️ 清除目前商品圖片",
            use_container_width=True
        ):

            st.session_state.image_bytes = None
            st.session_state.image_mime = None

            st.rerun()


# =========================================================
# CORE RULES
# =========================================================

CORE_RULES = """
你是台灣電商 AI 半自動化助手。

最高規則：

1. 不可虛構商品資訊。
2. 不可虛構品牌。
3. 不可虛構型號。
4. 不可虛構規格。
5. 不可虛構容量。
6. 不可虛構材質。
7. 不可虛構成分。
8. 不可虛構認證。
9. 不可捏造價格。
10. 不可捏造折扣。
11. 不可捏造贈品。
12. 不可捏造銷量。
13. 看不清楚的資料寫「待確認」。
14. 不可誇大。
15. 不可保證效果。
16. 不可做醫療療效保證。
17. 使用繁體中文。
18. 適合台灣電商。

商品圖片規則：

19. 商品原貌必須保持一致。
20. 不可任意改變品牌。
21. 不可任意改變包裝。
22. 不可任意改變商品形狀。
23. 不可任意改變比例。
24. 不可任意改變顏色。
25. 不可任意改變材質。
26. 不可任意改變 Logo。
27. 不可任意改變商品上的文字。
28. 不可產生第二個商品。
29. 不可讓商品融化、變形或漂浮。
30. 不可讓 Logo 扭曲。
31. 不可讓包裝文字漂移。
32. 不可產生水印。
33. 不可產生虛假商品。
"""


# =========================================================
# FULL PROMPT
# =========================================================

def build_full_prompt(
    info,
    selected
):

    platform_list = "\n".join(
        [
            f"- {item}"
            for item in selected
        ]
    )

    return f"""
{CORE_RULES}

你現在是「AI 蝦皮半自動化 2.5 PRO」。

請分析使用者提供的商品圖片與商品資料。

==================================================
【商品資料】
==================================================

{product_text(info)}

==================================================
【本次需要生成】
==================================================

{platform_list}

==================================================
【一、商品辨識】
==================================================

請辨識：

商品類型：
商品名稱：
品牌：
型號：
顏色：
材質：
規格：
包裝：
圖片可確認資訊：
待確認資訊：

如果圖片無法確認，
一定寫「待確認」。

不要自行猜測。

==================================================
【二、AI 選品分析】
==================================================

請輸出：

適合客群：
使用情境：
核心賣點：
購買理由：
視覺賣點：
主圖建議：
短影音方向：
市場切入方向：

==================================================
【三、蝦皮文案】
==================================================

生成：

1. 三個商品標題
2. 五個商品賣點
3. 完整商品描述
4. 商品特色
5. 使用情境
6. 購買提醒
7. 搜尋關鍵字
8. CTA

不要虛構商品資訊。

==================================================
【四、TikTok 文案】
==================================================

生成：

1. 五個前三秒 Hook
2. 15～30 秒短影音文案
3. 畫面建議
4. 字幕
5. CTA
6. Hashtag

==================================================
【五、Facebook 文案】
==================================================

生成：

1. FB 貼文標題
2. FB 完整貼文
3. FB 短版貼文
4. CTA
5. Hashtag

風格自然。
避免過度廣告感。

==================================================
【六、Instagram 文案】
==================================================

生成：

1. IG 第一行 Hook
2. IG Caption
3. 完整貼文
4. CTA
5. Hashtag

適合 Instagram 閱讀。

==================================================
【七、即夢 AI 2.5 生圖 Prompt】
==================================================

請建立英文 Prompt。

規格：

- 9:16 vertical
- premium commercial photography
- product as the only main visual focus
- preserve exact product identity
- preserve original packaging
- preserve logo
- preserve label
- preserve colors
- preserve materials
- preserve proportions
- no people
- no hands
- no presenter
- no spokesperson
- no extra products
- no fake products
- no watermark
- no distorted logo
- no distorted packaging
- no wrong text
- no deformed object

需要海報文字時：

海報文字使用繁體中文。

同時輸出：

【ENGLISH IMAGE PROMPT】

【NEGATIVE PROMPT】

==================================================
【八、即夢 AI 2.5 影片 Prompt】
==================================================

建立約 15 秒英文影片 Prompt。

影片比例：

9:16 vertical.

Opening：

完整商品展示。
商品置中。
商品清楚可見。

Middle：

slow push-in。

展示：

包裝細節。
材質。
Logo。
商品細節。

Camera：

使用自然、高級商業廣告運鏡。

Ending：

商品回到中央。
畫面穩定。
最後 freeze frame。

全程：

不要人物。
不要手。
不要主持人。
不要額外商品。
不要商品變形。
不要 Logo 扭曲。
不要文字漂移。
不要水印。

輸出：

【ENGLISH VIDEO PROMPT】

【NEGATIVE PROMPT】

==================================================
【九、爆款帶貨影片】
==================================================

製作約 20 秒短影音腳本。

0～3 秒：

畫面：
字幕：
旁白：

3～8 秒：

畫面：
字幕：
旁白：

8～14 秒：

畫面：
字幕：
旁白：

14～18 秒：

畫面：
字幕：
旁白：

18～20 秒：

畫面：
字幕：
旁白：
CTA：

另外提供：

三個影片標題。

三個封面文字。

五個 Hook。

==================================================
【十、利潤 / 分潤分析】
==================================================

已知：

售價：
{info.get("price", 0)}

成本：
{info.get("cost", 0)}

分潤比例：
{info.get("commission", 0)}%

請計算：

分潤金額：
預估利潤：
利潤率：

如果成本或售價不足，
請標示「待確認」。

不要自行猜數字。

==================================================
【十一e.resize(
                (
                    int(width * scale),
                    int(height * scale)
                ),
                Image.Resampling.LANCZOS
            )

        output = io.BytesIO()

        if image.mode == "RGBA":

            image.save(
                output,
                format="PNG",
                optimize=True
            )

            mime = "image/png"

        else:

            image = image.convert(
                "RGB"
            )

            image.save(
                output,
                format="JPEG",
                quality=92,
                optimize=True
            )

            mime = "image/jpeg"

        return (
            output.getvalue(),
            mime
        )

    except Exception as e:

        st.error(
            f"圖片處理失敗：{e}"
        )

        return None, None


# =========================================================
# PRODUCT FORM
# =========================================================

def product_form():

    st.subheader(
        "📦 商品資料"
    )

    c1, c2 = st.columns(2)

    with c1:

        name = st.text_input(
            "商品名稱",
            placeholder="例如：保溫杯"
        )

        category = st.selectbox(
            "商品類別",
            [
                "待確認",
                "保養品",
                "3C",
                "居家",
                "服飾",
                "食品",
                "汽機車",
                "生活用品",
                "其他",
            ]
        )

        price = st.number_input(
            "售價",
            min_value=0.0,
            value=0.0,
            step=1.0
        )

        cost = st.number_input(
            "成本",
            min_value=0.0,
            value=0.0,
            step=1.0
        )

    with c2:

        commission = st.number_input(
            "分潤比例 (%)",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=0.5
        )

        sales = st.number_input(
            "月銷量",
            min_value=0,
            value=0,
            step=1
        )

        rating = st.number_input(
            "商品評分",
            min_value=0.0,
            max_value=5.0,
            value=0.0,
            step=0.1
        )

        link = st.text_input(
            "商品連結",
            placeholder="選填"
        )

    specs = st.text_area(
        "商品規格 / 已知資訊",
        placeholder="輸入你知道的規格、尺寸、材質、顏色等..."
    )

    return {

        "name": name,

        "category": category,

        "price": price,

        "cost": cost,

        "commission": commission,

        "sales": sales,

        "rating": rating,

        "link": link,

        "specs": specs,
    }


def product_text(info):

    return f"""
商品名稱：{info["name"] or "待確認"}
商品類別：{info["category"]}
售價：{info["price"]}
成本：{info["cost"]}
分潤比例：{info["commission"]}%
月銷量：{info["sales"]}
商品評分：{info["rating"]}
商品連結：{info["link"] or "未提供"}
商品規格：{info["specs"] or "待確認"}
"""


# =========================================================
# UPLOAD
# =========================================================

def upload_product():

    st.subheader(
        "📷 商品圖片"
    )

    uploaded = st.file_uploader(
        "上傳商品圖片",
        type=[
            "jpg",
            "jpeg",
            "png",
            "webp"
        ],
        key="main_product_upload",
    )

    if uploaded:

        image_bytes, mime = process_image(
            uploaded
        )

        if image_bytes:

            st.session_state.image_bytes = (
                image_bytes
            )

            st.session_state.image_mime = (
                mime
            )

    if st.session_state.image_bytes:

        st.image(
            st.session_state.image_bytes,
            caption="目前商品圖片",
            use_container_width=True
        )


# =========================================================
# CORE RULES
# =========================================================

CORE_RULES = """
你是台灣電商 AI 半自動化助手。

最高規則：

1. 不可虛構商品資訊。
2. 不可虛構品牌。
3. 不可虛構型號。
4. 不可虛構規格。
5. 不可虛構容量。
6. 不可虛構材質。
7. 不可虛構成分。
8. 不可虛構認證。
9. 不可捏造價格。
10. 不可捏造折扣。
11. 不可捏造贈品。
12. 不可捏造銷量。
13. 看不清楚的資料寫「待確認」。
14. 不可誇大。
15. 不可保證效果。
16. 不可做醫療療效保證。
17. 使用繁體中文。
18. 適合台灣電商。
"""


# =========================================================
# FULL AUTO PROMPT
# =========================================================

def build_full_prompt(
    info,
    selected
):

    platform_list = "\n".join(
        [
            f"- {x}"
            for x in selected
        ]
    )

    return f"""
{CORE_RULES}

你現在是「AI 蝦皮半自動化 2.5 PRO」。

請分析使用者提供的商品圖片與資料。

商品資料：

{product_text(info)}

本次需要生成：

{platform_list}

==================================================
【商品辨識】
==================================================

請辨識：

商品類型：
商品名稱：
品牌：
型號：
顏色：
材質：
規格：
包裝：
圖片可確認資訊：
待確認資訊：

==================================================
【AI 選品分析】
==================================================

適合客群：
使用情境：
核心賣點：
購買理由：
視覺賣點：
主圖建議：
短影音方向：

==================================================
【蝦皮】
==================================================

生成：

3 個商品標題。

5 個商品賣點。

完整商品描述。

商品特色。

使用情境。

購買提醒。

搜尋關鍵字。

==================================================
【TikTok】
==================================================

生成：

5 個前三秒 Hook。

15～30 秒短影音文案。

字幕。

CTA。

Hashtag。

==================================================
【Facebook】
==================================================

生成：

FB 貼文標題。

FB 完整貼文。

FB 短版貼文。

CTA。

Hashtag。

要求自然、適合 Facebook，不要過度廣告感。

==================================================
【Instagram】
==================================================

生成：

IG Caption。

第一句 Hook。

完整貼文。

CTA。

Hashtag。

適合 Instagram。

==================================================
【即夢 AI 2.5 生圖】
==================================================

建立英文商品生圖 Prompt。

要求：

- 9:16
- 高品質商業攝影
- 商品為唯一主要視覺焦點
- 商品外觀保持一致
- 不要人物
- 不要手
- 不要額外商品
- 不要 Logo 變形
- 不要包裝變形
- 不要文字亂碼

同時提供：

NEGATIVE PROMPT。

如果需要海報文字：

使用繁體中文。

==================================================
【即夢 AI 2.5 影片】
==================================================

建立約 15 秒的英文影片 Prompt。

Opening：
完整商品展示。

Middle：
慢速推近。
展示包裝。
展示材質。
展示細節。

Camera：
自然商業運鏡。

Ending：
商品回到中央並停格。

不要人物。
不要手。
不要主持人。
不要額外商品。
不要變形。
不要 Logo 扭曲。

提供英文 Negative Prompt。

==================================================
【爆款帶貨影片】
==================================================

20 秒左右：

0～3 秒：
畫面：
字幕：
旁白：

3～8 秒：
畫面：
字幕：
旁白：

8～14 秒：
畫面：
字幕：
旁白：

14～18 秒：
畫面：
字幕：
旁白：

18～20 秒：
畫面：
字幕：
CTA：

再提供：

3 個影片標題。

3 個封面文字。

==================================================
【利潤分析】
==================================================

根據：

售價：{info["price"]}
成本：{info["cost"]}
分潤比例：{info["commission"]}%

計算：

分潤金額：
預估利潤：
利潤率：

==================================================
【合規】
==================================================

檢查所有生成內容：

- 誇大
- 醫療宣稱
- 虛假保證
- 虛構折扣
- 虛構贈品
- 虛構規格
- 虛構品牌
- 虛構功能

最後提供：

【合規檢查結果】

==================================================

請用清楚的繁體中文輸出。
不要省略任何被勾選的項目。
"""


# =========================================================
# AUTO CHECK OPTIONS
# =========================================================

def auto_options():

    st.markdown(
        """
<div class="auto-box">

<h3>☑️ AI 自動生成項目</h3>

<p>
系統預設全部自動勾選。
你也可以取消不需要的項目。
</p>

</div>
""",
        unsafe_allow_html=True
    )

    all_options = [
        "商品辨識",
        "AI 選品分析",
        "蝦皮文案",
        "TikTok 文案",
        "Facebook 文案",
        "Instagram 文案",
        "即夢 AI 2.5 生圖",
        "即夢 AI 2.5 影片",
        "爆款帶貨影片",
        "利潤 / 分潤分析",
        "合規檢查",
    ]

    select_all = st.checkbox(
        "☑️ 全部自動勾選",
        value=True,
        key="select_all_features"
    )

    selected = []

    cols = st.columns(3)

    for index, option in enumerate(
        all_options
    ):

        with cols[index % 3]:

            checked = st.checkbox(
                option,
                value=select_all,
                key=f"feature_{index}"
            )

            if checked:
                selected.append(option)

    return selected


# =========================================================
# FULL AUTO ANALYSIS
# =========================================================

def run_full_analysis(
    info,
    selected
):

    if not selected:

        st.error(
            "至少選擇一個 AI 功能。"
        )

        return

    if not st.session_state.image_bytes:

        st.error(
            "請先上傳商品圖片。"
        )

        return

    prompt = build_full_prompt(
        info,
        selected
    )

    progress = st.progress(
        0,
        text="準備 AI 分析..."
    )

    result, error = gemini_generate(
        prompt,
        st.session_state.image_bytes,
        st.session_state.image_mime,
    )

    progress.progress(
        100,
        text="AI 分析完成"
    )

    if error:

        st.error(error)

        return

    st.session_state.full_result = {

        "商品資料":
            product_text(info),

        "選擇功能":
            selected,

        "完整 AI 結果":
            result,
    }

    st.session_state.product_data = info

    st.session_state.last_run = (
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    st.success(
        "🎉 全部分析完成！"
    )


# =========================================================
# RESULT CENTER
# =========================================================

def result_center():

    result_data = (
        st.session_state.full_result
    )

    if not result_data:

        return

    st.divider()

    st.markdown(
        "## 📋 完整結果中心"
    )

    if st.session_state.last_run:

        st.caption(
            "最後分析："
            + st.session_state.last_run
        )

    result_text = result_data.get(
        "完整 AI 結果",
        ""
    )

    st.text_area(
        "AI 完整結果",
        value=result_text,
        height=900,
        key="final_result_text"
    )

    c1, c2 = st.columns(2)

    with c1:

        st.download_button(
            "⬇️ 下載完整結果 TXT",
            data=result_text,
    =======================================
# Secrets / Environment
# =========================================================

def get_setting(name):
    value = ""

    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""

    if not value:
        value = os.getenv(name, "")

    return str(value).strip()


def get_openclaw_url():
    return get_setting(
        "OPENCLAW_GATEWAY_URL"
    ).rstrip("/")


def get_openclaw_token():
    return get_setting(
        "OPENCLAW_GATEWAY_TOKEN"
    )


def openclaw_is_configured():
    return bool(
        get_openclaw_url()
        and get_openclaw_token()
    )


def openclaw_headers():
    headers = {
        "Content-Type": "application/json"
    }

    token = get_openclaw_token()

    if token:
        headers["Authorization"] = (
            f"Bearer {token}"
        )

    return headers


# =========================================================
# OpenClaw
# =========================================================

def openclaw_invoke(
    tool_name,
    args,
    timeout=300,
):
    gateway_url = get_openclaw_url()

    if not gateway_url:
        raise RuntimeError(
            "尚未設定 OPENCLAW_GATEWAY_URL。"
        )

    url = gateway_url + "/tools/invoke"

    payload = {
        "tool": tool_name,
        "args": args,
    }

    try:
        response = requests.post(
            url,
            headers=openclaw_headers(),
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as error:
        raise RuntimeError(
            f"無法連線 OpenClaw Gateway：{error}"
        )

    if response.status_code >= 400:
        raise RuntimeError(
            "OpenClaw Gateway 呼叫失敗。\n\n"
            f"HTTP：{response.status_code}\n\n"
            f"{response.text[:2000]}"
        )

    try:
        return response.json()
    except Exception:
        return {
            "raw": response.text
        }


def check_openclaw():
    if not get_openclaw_url():
        return {
            "available": False,
            "message": "尚未設定 OpenClaw Gateway。",
        }

    try:
        result = openclaw_invoke(
            "video_generate",
            {
                "action": "list"
            },
            timeout=30,
        )

        return {
            "available": True,
            "message": "OpenClaw 已連線。",
            "data": result,
        }

    except Exception as error:
        return {
            "available": False,
            "message": str(error),
        }


# =========================================================
# 圖片
# =========================================================

def prepare_image(uploaded_file):
    if uploaded_file is None:
        raise ValueError("沒有收到圖片。")

    raw_bytes = uploaded_file.getvalue()

    if not raw_bytes:
        raise ValueError("圖片檔案是空的。")

    size_mb = (
        len(raw_bytes)
        / 1024
        / 1024
    )

    if size_mb > MAX_IMAGE_MB:
        raise ValueError(
            f"圖片大小 {size_mb:.1f} MB，"
            f"超過 {MAX_IMAGE_MB} MB。"
        )

    try:
        image = Image.open(
            io.BytesIO(raw_bytes)
        )

        image = ImageOps.exif_transpose(image)
        image.load()

    except Exception as error:
        raise ValueError(
            f"無法讀取圖片：{error}"
        )

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


def image_to_data_url(image_bytes):
    encoded = base64.b64encode(
        image_bytes
    ).decode("utf-8")

    return (
        "data:image/jpeg;base64,"
        + encoded
    )


# =========================================================
# 商品規則
# =========================================================

PRODUCT_RULES = """
PRODUCT IDENTITY LOCK

Use the supplied product image as the exact visual reference.

Preserve:
- original brand
- original package
- original shape
- original proportions
- original colors
- original materials
- original logo
- original label
- original printed text

Do not redesign the product.
Do not create another product.
Do not duplicate the product.
Do not change package structure.
Do not change brand.
Do not change logo.
Do not change label.
Do not change product color.
Do not change product proportions.
Do not distort the product.
Do not make the product melt.
Do not make the product disappear.
Do not generate fake claims.
Do not generate fake prices.
Do not generate fake discounts.
Do not generate fake certifications.

Default scene:
No people.
No hands.
No presenter.
No influencer.
No model.
No spokesperson.

Premium commercial product photography.
Photorealistic.
Smooth cinematic movement.
Stable product identity.
No flicker.
No warping.
No text drift.
No watermark.
""".strip()


# =========================================================
# 商品分類
# =========================================================

def detect_product_category(
    product_name,
    product_spec="",
):
    text = (
        f"{product_name} {product_spec}"
    ).lower()

    category_keywords = {
        "保養品": [
            "保養",
            "精華",
            "乳液",
            "面霜",
            "化妝水",
            "洗面",
            "面膜",
            "防曬",
            "serum",
            "cream",
            "lotion",
            "skincare",
        ],
        "3C": [
            "手機",
            "耳機",
            "充電",
            "電腦",
            "鍵盤",
            "滑鼠",
            "螢幕",
            "usb",
            "bluetooth",
            "camera",
            "耳麥",
            "3c",
        ],
        "居家": [
            "家用",
            "收納",
            "清潔",
            "廚房",
            "杯",
            "鍋",
            "床",
            "居家",
            "家具",
            "香氛",
        ],
        "服飾": [
            "衣",
            "褲",
            "鞋",
            "襪",
            "外套",
            "帽",
            "包",
            "服飾",
            "dress",
            "shirt",
            "pants",
            "shoes",
        ],
        "食品": [
            "食品",
            "零食",
            "餅乾",
            "茶",
            "咖啡",
            "飲料",
            "食材",
            "果乾",
        ],
        "汽機車": [
            "汽車",
            "機車",
            "車用",
            "汽配",
            "機油",
            "輪胎",
            "行車記錄器",
            "car",
            "motorcycle",
        ],
    }

    for category, keywords in category_keywords.items():
        for keyword in keywords:
            if keyword in text:
                return category

    return "其他"


# =========================================================
# 商品分析
# =========================================================

def safe_float(value):
    try:
        return float(str(value).strip() or 0)
    except Exception:
        return 0.0


def safe_int(value):
    try:
        return int(float(str(value).strip() or 0))
    except Exception:
        return 0


def analyze_product(
    product_name,
    price,
    cost,
    commission,
    monthly_sales,
    rating,
    product_link,
    product_spec,
    target_platform,
):
    category = detect_product_category(
        product_name,
        product_spec,
    )

    price_value = safe_float(price)
    cost_value = safe_float(cost)
    commission_value = safe_float(commission)
    sales_value = safe_int(monthly_sales)
    rating_value = safe_float(rating)

    gross_profit = (
        price_value - cost_value
    )

    commission_amount = (
        price_value
        * commission_value
        / 100
    )

    estimated_profit = (
        gross_profit
        - commission_amount
    )

    if price_value > 0:
        margin = (
            estimated_profit
            / price_value
            * 100
        )
    else:
        margin = 0

    if rating_value >= 4.8:
        rating_comment = "商品評分表現很好。"
    elif rating_value >= 4.5:
        rating_comment = "商品評分表現不錯。"
    elif rating_value > 0:
        rating_comment = "建議持續觀察商品評價。"
    else:
        rating_comment = "尚未提供商品評分。"

    if sales_value >= 1000:
        sales_comment = "月銷量具備明顯市場需求。"
    elif sales_value >= 100:
        sales_comment = "已有一定市場銷量。"
    elif sales_value > 0:
        sales_comment = "目前銷量較低，建議搭配內容測試。"
    else:
        sales_comment = "尚未提供月銷量。"

    if margin >= 30:
        profit_comment = "估算毛利空間相對充足。"
    elif margin >= 15:
        profit_comment = "估算毛利屬中等，可再優化成本。"
    elif margin > 0:
        profit_comment = "估算利潤偏低，需注意平台及廣告成本。"
    else:
        profit_comment = "目前估算利潤不足，請重新確認售價與成本。"

    return f"""
【AI 商品分析】

商品名稱：
{product_name or "待確認"}

商品分類：
{category}

商品價格：
NT$ {price_value:,.0f}

商品成本：
NT$ {cost_value:,.0f}

分潤比例：
{commission_value:.1f}%

月銷量：
{sales_value:,}

商品評分：
{rating_value:.1f}

商品連結：
{product_link or "待確認"}

商品規格：
{product_spec or "待確認"}

━━━━━━━━━━━━━━━━━━

【市場判斷】

{sales_comment}

{rating_comment}

【利潤估算】

售價：
NT$ {price_value:,.0f}

成本：
NT$ {cost_value:,.0f}

分潤估算：
NT$ {commission_amount:,.0f}

扣除成本與分潤後估算：
NT$ {estimated_profit:,.0f}

估算利潤率：
{margin:.1f}%

{profit_comment}

━━━━━━━━━━━━━━━━━━

【內容方向】

蝦皮：
主打商品特色、規格、使用情境與購買理由。

TikTok：
使用短影音開場吸引注意，再展示商品細節與使用情境。

圖片：
以商品本體作為主要視覺焦點。

影片：
建議使用 9:16 直式商品影片。

━━━━━━━━━━━━━━━━━━

【AI 誤判保護】

圖片模糊、多商品或資訊不足時：
以最大、最清楚、品牌最容易辨識的商品作為主體。

無法確認的商品資訊：
標記「待確認」。

禁止自行虛構：
品牌、規格、價格、認證、療效或其他商品資訊。

目標平台：
{target_platform}
""".strip()


# ============================#
# 功能：
# 1. 會員註冊
# 2. 會員登入
# 3. 永久會員
# 4. 管理員
# 5. 商品圖片上傳
# 6. Gemini 商品圖片辨識
# 7. AI 商品分析
# 8. 蝦皮上架文案
# 9. TikTok 文案
# 10. 即夢 AI 2.5 生圖 Prompt
# 11. 即夢 AI 2.5 影片 Prompt
# 12. 分潤／內容合規檢查
# 13. 完整流程
# 14. 手機版
# 15. 重新整理後安全回首頁
# =========================================================


# =========================================================
# 頁面設定
# =========================================================

st.set_page_config(
    page_title="AI 蝦皮半自動化 2.5 PRO",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="auto",
)


APP_NAME = "AI 蝦皮半自動化 2.5 PRO"

DATA_DIR = Path("data")
MEMBERS_FILE = DATA_DIR / "members.json"

DATA_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# =========================================================
# 基本設定
# =========================================================

MAX_IMAGE_SIZE = 1600
MAX_IMAGE_MB = 20

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]

DEFAULT_MODEL = "gemini-2.5-flash"


# =========================================================
# CSS
# =========================================================

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 4rem !important;
        padding-bottom: 3rem !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
    }

    .main-title {
        text-align: center;
        font-size: 38px;
        font-weight: 900;
        margin-top: 8px !important;
        margin-bottom: 10px !important;
        line-height: 1.3;
        word-break: break-word;
    }

    .main-subtitle {
        text-align: center;
        font-size: 16px;
        opacity: .75;
        margin-bottom: 25px;
        line-height: 1.5;
    }

    .feature-card {
        padding: 18px;
        border-radius: 14px;
        border: 1px solid rgba(128,128,128,.25);
        margin-bottom: 14px;
    }

    .section-title {
        font-size: 27px;
        font-weight: 800;
        margin-top: 10px;
        margin-bottom: 12px;
    }

    div.stButton > button {
        min-height: 44px;
        border-radius: 10px;
    }

    div[data-testid="stDownloadButton"] button {
        min-height: 44px;
        border-radius: 10px;
    }

    @media (max-width: 768px) {

        .block-container {
            padding-top: 3.3rem !important;
            padding-left: .9rem !important;
            padding-right: .9rem !important;
            padding-bottom: 2rem !important;
        }

        .main-title {
            font-size: 27px;
        }

        .main-subtitle {
            font-size: 14px;
        }

        .section-title {
            font-size: 23px;
        }
    }

    @media (max-width: 480px) {

        .block-container {
            padding-top: 3rem !important;
            padding-left: .7rem !important;
            padding-right: .7rem !important;
        }

        .main-title {
            font-size: 24px;
        }

        .main-subtitle {
            font-size: 13px;
        }
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# Session State
# =========================================================

DEFAULT_SESSION = {
    "logged_in": False,
    "page": "home",
    "username": "",
    "member": {},
    "analysis_result": "",
    "image_analysis": "",
    "generated_copy": "",
    "tiktok_copy": "",
    "jimeng_image_prompt": "",
    "jimeng_video_prompt": "",
    "compliance_result": "",
    "last_image_bytes": None,
    "last_product_name": "",
    "last_product_spec": "",
    "last_category": "",
}


for key, value in DEFAULT_SESSION.items():

    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# 會員資料
# =========================================================

def load_members():

    if not MEMBERS_FILE.exists():
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

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_file = DATA_DIR / "members.tmp"

    with open(
        temp_file,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            members,
            f,
            ensure_ascii=False,
            indent=2,
        )

    temp_file.replace(MEMBERS_FILE)


# =========================================================
# 密碼
# =========================================================

def hash_password(password):

    salt = secrets.token_hex(16)

    digest = hashlib.sha256(
        (
            salt
            + str(password)
        ).encode("utf-8")
    ).hexdigest()

    return salt + "$" + digest


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
                salt
                + str(password)
            ).encode("utf-8")
        ).hexdigest()

        return secrets.compare_digest(
            digest,
            saved_hash,
        )

    except Exception:

        return False


# =========================================================
# 建立管理員
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
        "permanent": True,
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

    for member in load_members():

        saved_username = str(
            member.get(
                "username",
                "",
            )
        ).strip().lower()

        if saved_username == username:
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

    for member in load_members():

        saved_email = str(
            member.get(
                "email",
                "",
            )
        ).strip().lower()

        if saved_email == email:
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
        str(username)
        .strip()
        .lower()
    )

    password = str(password)

    name = str(name).strip()

    email = (
        str(email)
        .strip()
        .lower()
    )

    if not username:
        return False, "請輸入會員帳號。"

    if len(username) < 3:
        return False, "帳號至少需要 3 個字元。"

    if not re.match(
        r"^[a-zA-Z0-9_.-]+$",
        username,
    ):
        return False, "帳號只能使用英文、數字、底線、句點或連字號。"

    if not password:
        return False, "請輸入密碼。"

    if len(password) < 4:
        return False, "密碼至少需要 4 個字元。"

    if find_member(username):
        return False, "這個帳號已經存在。"

    if email and find_member_by_email(email):
        return False, "這個 Email 已經註冊。"

    member = {
        "id": secrets.token_hex(8),
        "username": username,
        "password_hash": hash_password(password),
        "name": name,
        "email": email,
        "role": "member",
        "status": "active",
        "permanent": True,
        "created_at": datetime.now().isoformat(),
    }

    members = load_members()

    members.append(member)

    save_members(members)

    return True, member


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
        return False, "invalid"

    if str(
        member.get(
            "status",
            "active",
        )
    ).lower() != "active":

        return False, "disabled"

    if not verify_password(
        password,
        member.get(
            "password_hash",
            "",
        ),
    ):
        return False, "invalid"

    return True, member


# =========================================================
# 登出
# =========================================================

def logout():

    for key, value in DEFAULT_SESSION.items():

        st.session_state[key] = value

    st.session_state.page = "home"

    st.rerun()


# =========================================================
# Gemini API 設定
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


def get_gemini_model():

    try:

        model = st.session_state.get(
            "gemini_model",
            DEFAULT_MODEL,
        )

    except Exception:

        model = DEFAULT_MODEL

    if model not in GEMINI_MODELS:
        model = DEFAULT_MODEL

    return model


def get_gemini_client():

    if genai is None:

        raise RuntimeError(
            "尚未安裝 google-genai。"
            "請在 requirements.txt 加入 google-genai。"
        )

    api_key = get_gemini_api_key()

    if not api_key:

        raise RuntimeError(
            "尚未設定 GEMINI_API_KEY。"
        )

    return genai.Client(
        api_key=api_key
    )


# =========================================================
# Gemini 呼叫
# =========================================================

def gemini_generate_text(
    prompt,
    image_bytes=None,
    mime_type="image/jpeg",
):

    client = get_gemini_client()

    models_to_try = [
        get_gemini_model()
    ]

    for model in GEMINI_MODELS:

        if model not in models_to_try:
            models_to_try.append(model)

    last_error = None

    for model_name in models_to_try:

        try:

            if image_bytes and types is not None:

                image_part = types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type,
                )

                contents = [
                    image_part,
                    prompt,
                ]

            else:

                contents = prompt

            response = client.models.generate_content(
                model=model_name,
                contents=contents,
            )

            text = getattr(
                response,
                "text",
                None,
            )

            if text:

                return text.strip()

            return str(response)

        except Exception as error:

            last_error = error

            continue

    raise RuntimeError(
        "Gemini API 呼叫失敗。\n\n"
        + str(last_error)
    )


# =========================================================
# 圖片處理
# =========================================================

def prepare_image(uploaded_file):

    if uploaded_file is None:
        raise ValueError(
            "沒有收到圖片。"
        )

    raw_bytes = uploaded_file.getvalue()

    if not raw_bytes:
        raise ValueError(
            "圖片檔案是空的。"
        )

    size_mb = (
        len(raw_bytes)
        / 1024
        / 1024
    )

    if size_mb > MAX_IMAGE_MB:

        raise ValueError(
            f"圖片大小 {size_mb:.1f} MB，"
            f"超過 {MAX_IMAGE_MB} MB。"
        )

    try:

        image = Image.open(
            io.BytesIO(raw_bytes)
        )

        image = ImageOps.exif_transpose(
            image
        )

        image.load()

    except Exception as error:

        raise ValueError(
            f"無法讀取圖片：{error}"
        )

    if image.mode not in (
        "RGB",
        "RGBA",
    ):

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

    output = io.BytesIO()

    image.save(
        output,
        format="JPEG",
        quality=92,
        optimize=True,
    )

    return (
        image,
        output.getvalue(),
    )


# =========================================================
# 商品分類
# =========================================================

def detect_product_category(
    product_name,
    product_spec="",
):

    text = (
        str(product_name or "")
        + " "
        + str(product_spec or "")
    ).lower()

    keywords = {

        "保養品": [
            "保養",
            "精華",
            "乳液",
            "面霜",
            "化妝水",
            "洗面",
            "面膜",
            "防曬",
            "serum",
            "cream",
            "lotion",
            "skincare",
        ],

        "3C": [
            "手機",
            "耳機",
            "充電",
            "電腦",
            "鍵盤",
            "滑鼠",
            "螢幕",
            "usb",
            "bluetooth",
            "camera",
            "3c",
        ],

        "居家": [
            "家用",
            "收納",
            "清潔",
            "廚房",
            "杯",
            "鍋",
            "床",
            "居家",
            "家具",
            "香氛",
        ],

        "服飾": [
            "衣",
            "褲",
            "鞋",
            "襪",
            "外套",
            "帽",
            "包",
            "服飾",
            "dress",
            "shirt",
            "pants",
            "shoes",
        ],

        "食品": [
            "食品",
            "零食",
            "餅乾",
            "茶",
            "咖啡",
            "飲料",
            "食材",
            "果乾",
        ],

        "汽機車": [
            "汽車",
            "機車",
            "車用",
            "汽配",
            "機油",
            "輪胎",
            "行車記錄器",
            "car",
            "motorcycle",
        ],
    }

    for category, words in keywords.items():

        for word in words:

            if word in text:
                return category

    return "其他"


# =========================================================
# Gemini 商品圖片辨識
# =========================================================

def analyze_product_image(
    image_bytes,
):

    prompt = """
你是專業電商商品圖片分析 AI。

請仔細分析使用者上傳的商品圖片。

重要規則：

1. 不可以憑空捏造圖片看不到的資訊。
2. 看不清楚的品牌、型號、規格、容量、材質，請寫「待確認」。
3. 商品包裝上的文字只能描述你實際看見的內容。
4. 不可以自行發明價格。
5. 不可以自行發明療效。
6. 不可以自行發明認證。
7. 不可以自行發明品牌。
8. 如果圖片中有多個物品，找出最主要、最清楚的商品。
9. 用繁體中文回答。

請按照以下格式：

【商品辨識】
商品名稱：
品牌：
類別：
主要顏色：
外觀：
材質：
包裝：
可辨識文字：
型號：
規格：

【商品賣點】
1.
2.
3.

【商品使用情境】
1.
2.
3.

【圖片判斷】
圖片清晰度：
主要商品：
是否有多商品：
可能需要人工確認的資訊：

【電商建議】
蝦皮展示重點：
TikTok 展示重點：
即夢 AI 2.5 畫面建議：

最後再次確認：
任何無法從圖片確認的資訊必須標示「待確認」。
"""

    return gemini_generate_text(
        prompt,
        image_bytes=image_bytes,
        mime_type="image/jpeg",
    )


# =========================================================
# Gemini 完整商品分析
# =========================================================

def generate_ai_product_analysis(
    product_name,
    product_spec,
    price,
    cost,
    commission,
    monthly_sales,
    rating,
    target_platform,
    image_analysis,
):

    prompt = f"""
你是專業電商商品分析 AI。

請根據以下資料進行分析。

【商品名稱】
{product_name or "待確認"}

【商品規格】
{product_spec or "待確認"}

【商品價格】
{price or "待確認"}

【商品成本】
{cost or "待確認"}

【分潤比例】
{commission or "待確認"}

【月銷量】
{monthly_sales or "待確認"}

【商品評分】
{rating or "待確認"}

【目標平台】
{target_platform}

【圖片 AI 辨識】
{image_analysis or "沒有圖片辨識資料"}

規則：

- 不可捏造商品資訊。
- 不可捏造品牌。
- 不可捏造規格。
- 不可捏造價格。
- 不可捏造療效。
- 不可把推測當成事實。
- 不確定資訊標示「待確認」。
- 使用繁體中文。

請輸出：

【AI 商品分析】

【商品定位】

【核心賣點】

【目標客群】

【蝦皮銷售方向】

【TikTok 短影音方向】

【圖片視覺方向】

【影片內容方向】

【購買理由】

【風險與注意事項】

【最值得測試的內容角度】

請務必實用、具體，不要只寫空泛形容詞。
"""

    return gemini_generate_text(
        prompt
    )


# =========================================================
# 蝦皮文案
# =========================================================

def generate_shopee_copy(
    product_name,
    product_spec,
    category,
    price,
    image_analysis,
    product_analysis,
):

    prompt = f"""
你是台灣蝦皮電商文案專家。

請製作一份可以直接修改後上架的商品文案。

商品名稱：
{product_name or "待確認"}

商品分類：
{category}

商品規格：
{product_spec or "待確認"}

價格：
{price or "待確認"}

圖片辨識：
{image_analysis or "待確認"}

商品分析：
{product_analysis or "待確認"}

規則：

- 使用繁體中文。
- 不要虛構品牌。
- 不要虛構規格。
- 不要虛構價格。
- 不要虛構療效。
- 不要使用「百分之百有效」等誇大宣稱。
- 不確定資料標示「待確認」。
- 標題要適合蝦皮搜尋。
- 文案要清楚、容易閱讀。
- 不要過度堆砌 emoji。

請輸出：

【蝦皮商品標題】

【短版賣點】

【商品介紹】

【商品特色】

【規格資訊】

【使用／購買提醒】

【適合族群】

【SEO 關鍵字】

【Hashtag】
"""

    return gemini_generate_text(
        prompt
    )


# =========================================================
# TikTok 文案
# =========================================================

def generate_tiktok_copy(
    product_name,
    product_spec,
    category,
    image_analysis,
    product_analysis,
):

    prompt = f"""
你是台灣 TikTok 電商短影音文案專家。

商品：
{product_name or "待確認"}

分類：
{category}

規格：
{product_spec or "待確認"}

圖片辨識：
{image_analysis or "待確認"}

商品分析：
{product_analysis or "待確認"}

請製作一份適合 10～15 秒商品短影音的文案。

規則：

- 繁體中文。
- 不虛構商品資訊。
- 不誇大功效。
- 不捏造價格。
- 不捏造折扣。
- 不捏造品牌。
- 不捏造認證。
- 開頭 0～3 秒必須吸引注意。
- 中間展示商品。
- 最後有自然 CTA。
- 適合電商帶貨。

請輸出：

【0～3 秒 Hook】

【3～8 秒商品展示】

【8～12 秒商品細節】

【結尾 CTA】

【完整口播文案】

【影片字幕建議】

【Hashtag】
"""

    return gemini_generate_text(
        prompt
    )


# =========================================================
# 即夢 AI 2.5 生圖 Prompt
# =========================================================

def generate_jimeng_image_prompt(
    product_name,
    product_spec,
    target_platform,
    image_analysis,
    product_analysis,
):

    prompt = f"""
你是專業 AI 商業攝影 Prompt 工程師。

請為「即夢 AI 2.5」製作商品生圖指令。

商品：
{product_name or "the uploaded product"}

規格：
{product_spec or "unknown"}

平台：
{target_platform}

圖片辨識：
{image_analysis or "unknown"}

商品分析：
{product_analysis or "unknown"}

最重要規則：

1. 使用上傳商品圖片作為唯一商品外觀參考。
2. 商品品牌必須保持一致。
3. 包裝保持一致。
4. 商品形狀保持一致。
5. 商品比例保持一致。
6. 商品顏色保持一致。
7. Logo 保持一致。
8. 標籤保持一致。
9. 商品上的文字不要自行修改。
10. 不可以新增不存在的商 return True, member


# =========================================================
# 登出
# =========================================================

def logout():

    for key, default_value in DEFAULT_SESSION.items():
        st.session_state[key] = default_value

    st.session_state.page = "login"

    st.rerun()


# =========================================================
# 頁面切換
# =========================================================

def go_page(page_name):

    st.session_state.page = page_name

    st.rerun()


# =========================================================
# Settings / Secrets
# =========================================================

def get_setting(name):

    value = ""

    try:

        value = st.secrets.get(
            name,
            "",
        )

    except Exception:

        value = ""

    if not value:
        value = os.getenv(
            name,
            "",
        )

    return str(value).strip()


def get_openclaw_url():

    return get_setting(
        "OPENCLAW_GATEWAY_URL"
    ).rstrip("/")


def get_openclaw_token():

    return get_setting(
        "OPENCLAW_GATEWAY_TOKEN"
    )


def openclaw_configured():

    return bool(
        get_openclaw_url()
    )


# =========================================================
# OpenClaw Header
# =========================================================

def openclaw_headers():

    headers = {
        "Content-Type": "application/json",
    }

    token = get_openclaw_token()

    if token:

        headers["Authorization"] = (
            "Bearer " + token
        )

    return headers


# =========================================================
# OpenClaw 呼叫
# =========================================================

def openclaw_invoke(
    tool_name,
    args,
    timeout=300,
):

    gateway_url = get_openclaw_url()

    if not gateway_url:

        raise RuntimeError(
            "尚未設定 OPENCLAW_GATEWAY_URL。"
        )

    endpoint = (
        gateway_url
        + "/tools/invoke"
    )

    payload = {
        "tool": tool_name,
        "args": args,
    }

    response = requests.post(
        endpoint,
        headers=openclaw_headers(),
        json=payload,
        timeout=timeout,
    )

    if response.status_code >= 400:

        raise RuntimeError(
            "OpenClaw Gateway 呼叫失敗。\n"
            + "HTTP："
            + str(response.status_code)
            + "\n\n"
            + response.text[:2000]
        )

    try:

        return response.json()

    except Exception:

        return {
            "raw": response.text
        }


# =========================================================
# OpenClaw 狀態
# =========================================================

def check_openclaw():

    if not get_openclaw_url():

        return {
            "available": False,
            "message": "尚未設定 OpenClaw Gateway。",
        }

    try:

        result = openclaw_invoke(
            "video_generate",
            {
                "action": "list"
            },
            timeout=30,
        )

        return {
            "available": True,
            "message": "OpenClaw 已連線。",
            "data": result,
        }

    except Exception as error:

        return {
            "available": False,
            "message": str(error),
        }


# =========================================================
# 圖片處理
# =========================================================

def prepare_image(uploaded_file):

    if uploaded_file is None:

        raise ValueError(
            "沒有收到圖片。"
        )

    raw_bytes = uploaded_file.getvalue()

    if not raw_bytes:

        raise ValueError(
            "圖片檔案是空的。"
        )

    size_mb = (
        len(raw_bytes)
        / 1024
        / 1024
    )

    if size_mb > MAX_IMAGE_MB:

        raise ValueError(
            "圖片大小 "
            + f"{size_mb:.1f} MB，"
            + f"超過 {MAX_IMAGE_MB} MB。"
        )

    try:

        image = Image.open(
            io.BytesIO(raw_bytes)
        )

        image = ImageOps.exif_transpose(
            image
        )

        image.load()

    except Exception as error:

        raise ValueError(
            "無法讀取圖片："
            + str(error)
        )

    if image.mode not in (
        "RGB",
        "RGBA",
    ):

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

    return (
        image,
        buffer.getvalue(),
    )


# =========================================================
# 圖片 Base64
# =========================================================

def image_to_data_url(image_bytes):

    encoded = base64.b64encode(
        image_bytes
    ).decode("utf-8")

    return (
        "data:image/jpeg;base64,"
        + encoded
    )


# =========================================================
# 商品分類
# =========================================================

def detect_product_category(
    product_name,
    product_spec="",
):

    text = (
        str(product_name)
        + " "
        + str(product_spec)
    ).lower()

    categories = {

        "保養品": [
            "保養",
            "精華",
            "乳液",
            "面霜",
            "化妝水",
            "洗面",
            "面膜",
            "防曬",
            "serum",
            "cream",
            "lotion",
            "skincare",
        ],

        "3C": [
            "手機",
            "耳機",
            "充電",
            "電腦",
            "鍵盤",
            "滑鼠",
            "螢幕",
            "usb",
            "bluetooth",
            "camera",
            "耳麥",
            "3c",
        ],

        "居家": [
            "家用",
            "收納",
            "清潔",
            "廚房",
            "杯",
            "鍋",
            "床",
            "居家",
            "家具",
            "香氛",
        ],

        "服飾": [
            "衣",
            "褲",
            "鞋",
            "襪",
            "外套",
            "帽",
            "包",
            "服飾",
            "dress",
            "shirt",
            "pants",
            "shoes",
        ],

        "食品": [
            "食品",
            "零食",
            "餅乾",
            "茶",
            "咖啡",
            "飲料",
            "食材",
            "果乾",
        ],

        "汽機車": [
            "汽車",
            "機車",
            "車用",
            "汽配",
            "機油",
            "輪胎",
            "行車記錄器",
            "car",
            "motorcycle",
        ],
    }

    for category, keywords in categories.items():

        for keyword in keywords:

            if keyword in text:
                return category

    return "其他"


# =========================================================
# 即夢 / 商品核心規則
# =========================================================

PRODUCT_RULES = """
PRODUCT IDENTITY LOCK

Use the supplied product image as the exact visual reference.

Preserve:
- original brand
- original package
- original shape
- original proportions
- original colors
- original materials
- original logo
- original label
- original printed text

Do not redesign the product.
Do not create another product.
Do not duplicate the product.
Do not change package structure.
Do not change brand.
Do not change logo.
Do not change label.
Do not change product color.
Do not change product proportions.
Do not distort the product.
Do not make the product melt.
Do not make the product disappear.
Do not invent product information.
Do not invent prices.
Do not invent discounts.
Do not invent certifications.
Do not invent medical claims.

DEFAULT SCENE:
No people.
No hands.
No presenter.
No influencer.
No model.
No spokesperson.

STYLE:
Premium commercial product photography.
Photorealistic.
Clean.
Professional.
Stable product identity.
No flicker.
No warping.
No text drift.
No watermark.
"""


# =========================================================
# 即夢圖片 Prompt
# =========================================================

def build_image_prompt(
    product_name,
    product_spec,
    target_platform,
):

    name = (
        str(product_name).strip()
        or "the uploaded product"
    )

    spec = (
        str(product_spec).strip()
        or "unknown"
    )

    platform = (
        str(target_platform).strip()
        or "Shopee and TikTok"
    )

    prompt = f"""
Create a premium commercial product image.

MAIN PRODUCT:
{name}

PRODUCT SPECIFICATION:
{spec}

TARGET PLATFORM:
{platform}

REFERENCE:
Use the uploaded product image as the ONLY exact product reference.

PRESERVE:
Brand, packaging, shape, proportions, color,
material, logo, label and printed text.

COMPOSITION:
The product is the clear visual focus.
Premium commercial photography.
Clean professional background.
Natural realistic lighting.
High-end e-commerce advertising style.
Photorealistic.
Sharp details.
Professional composition.

PEOPLE:
No people.
No hands.
No presenter.
No influencer.
No model.
No spokesperson.

PRODUCT PROTECTION:
Do not redesign the product.
Do not change the brand.
Do not change the package.
Do not change logo.
Do not change label.
Do not change printed text.
Do not invent specifications.
Do not invent claims.
Do not add fake prices.
Do not add fake discounts.
Do not add watermark.

TEXT:
Traditional Chinese only if poster text is necessary.

NEGATIVE PROMPT:
people, hands, fingers, presenter, influencer, model,
duplicate product, extra product, wrong product,
wrong brand, wrong logo, wrong package,
distorted label, wrong text, unreadable text,
text drift,=======================================
# Secrets / Environment
# =========================================================

def get_setting(name):
    value = ""

    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""

    if not value:
        value = os.getenv(name, "")

    return str(value).strip()


def get_openclaw_url():
    return get_setting(
        "OPENCLAW_GATEWAY_URL"
    ).rstrip("/")


def get_openclaw_token():
    return get_setting(
        "OPENCLAW_GATEWAY_TOKEN"
    )


def openclaw_is_configured():
    return bool(
        get_openclaw_url()
        and get_openclaw_token()
    )


def openclaw_headers():
    headers = {
        "Content-Type": "application/json"
    }

    token = get_openclaw_token()

    if token:
        headers["Authorization"] = (
            f"Bearer {token}"
        )

    return headers


# =========================================================
# OpenClaw
# =========================================================

def openclaw_invoke(
    tool_name,
    args,
    timeout=300,
):
    gateway_url = get_openclaw_url()

    if not gateway_url:
        raise RuntimeError(
            "尚未設定 OPENCLAW_GATEWAY_URL。"
        )

    url = gateway_url + "/tools/invoke"

    payload = {
        "tool": tool_name,
        "args": args,
    }

    try:
        response = requests.post(
            url,
            headers=openclaw_headers(),
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as error:
        raise RuntimeError(
            f"無法連線 OpenClaw Gateway：{error}"
        )

    if response.status_code >= 400:
        raise RuntimeError(
            "OpenClaw Gateway 呼叫失敗。\n\n"
            f"HTTP：{response.status_code}\n\n"
            f"{response.text[:2000]}"
        )

    try:
        return response.json()
    except Exception:
        return {
            "raw": response.text
        }


def check_openclaw():
    if not get_openclaw_url():
        return {
            "available": False,
            "message": "尚未設定 OpenClaw Gateway。",
        }

    try:
        result = openclaw_invoke(
            "video_generate",
            {
                "action": "list"
            },
            timeout=30,
        )

        return {
            "available": True,
            "message": "OpenClaw 已連線。",
            "data": result,
        }

    except Exception as error:
        return {
            "available": False,
            "message": str(error),
        }


# =========================================================
# 圖片
# =========================================================

def prepare_image(uploaded_file):
    if uploaded_file is None:
        raise ValueError("沒有收到圖片。")

    raw_bytes = uploaded_file.getvalue()

    if not raw_bytes:
        raise ValueError("圖片檔案是空的。")

    size_mb = (
        len(raw_bytes)
        / 1024
        / 1024
    )

    if size_mb > MAX_IMAGE_MB:
        raise ValueError(
            f"圖片大小 {size_mb:.1f} MB，"
            f"超過 {MAX_IMAGE_MB} MB。"
        )

    try:
        image = Image.open(
            io.BytesIO(raw_bytes)
        )

        image = ImageOps.exif_transpose(image)
        image.load()

    except Exception as error:
        raise ValueError(
            f"無法讀取圖片：{error}"
        )

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


def image_to_data_url(image_bytes):
    encoded = base64.b64encode(
        image_bytes
    ).decode("utf-8")

    return (
        "data:image/jpeg;base64,"
        + encoded
    )


# =========================================================
# 商品規則
# =========================================================

PRODUCT_RULES = """
PRODUCT IDENTITY LOCK

Use the supplied product image as the exact visual reference.

Preserve:
- original brand
- original package
- original shape
- original proportions
- original colors
- original materials
- original logo
- original label
- original printed text

Do not redesign the product.
Do not create another product.
Do not duplicate the product.
Do not change package structure.
Do not change brand.
Do not change logo.
Do not change label.
Do not change product color.
Do not change product proportions.
Do not distort the product.
Do not make the product melt.
Do not make the product disappear.
Do not generate fake claims.
Do not generate fake prices.
Do not generate fake discounts.
Do not generate fake certifications.

Default scene:
No people.
No hands.
No presenter.
No influencer.
No model.
No spokesperson.

Premium commercial product photography.
Photorealistic.
Smooth cinematic movement.
Stable product identity.
No flicker.
No warping.
No text drift.
No watermark.
""".strip()


# =========================================================
# 商品分類
# =========================================================

def detect_product_category(
    product_name,
    product_spec="",
):
    text = (
        f"{product_name} {product_spec}"
    ).lower()

    category_keywords = {
        "保養品": [
            "保養",
            "精華",
            "乳液",
            "面霜",
            "化妝水",
            "洗面",
            "面膜",
            "防曬",
            "serum",
            "cream",
            "lotion",
            "skincare",
        ],
        "3C": [
            "手機",
            "耳機",
            "充電",
            "電腦",
            "鍵盤",
            "滑鼠",
            "螢幕",
            "usb",
            "bluetooth",
            "camera",
            "耳麥",
            "3c",
        ],
        "居家": [
            "家用",
            "收納",
            "清潔",
            "廚房",
            "杯",
            "鍋",
            "床",
            "居家",
            "家具",
            "香氛",
        ],
        "服飾": [
            "衣",
            "褲",
            "鞋",
            "襪",
            "外套",
            "帽",
            "包",
            "服飾",
            "dress",
            "shirt",
            "pants",
            "shoes",
        ],
        "食品": [
            "食品",
            "零食",
            "餅乾",
            "茶",
            "咖啡",
            "飲料",
            "食材",
            "果乾",
        ],
        "汽機車": [
            "汽車",
            "機車",
            "車用",
            "汽配",
            "機油",
            "輪胎",
            "行車記錄器",
            "car",
            "motorcycle",
        ],
    }

    for category, keywords in category_keywords.items():
        for keyword in keywords:
            if keyword in text:
                return category

    return "其他"


# =========================================================
# 商品分析
# =========================================================

def safe_float(value):
    try:
        return float(str(value).strip() or 0)
    except Exception:
        return 0.0


def safe_int(value):
    try:
        return int(float(str(value).strip() or 0))
    except Exception:
        return 0


def analyze_product(
    product_name,
    price,
    cost,
    commission,
    monthly_sales,
    rating,
    product_link,
    product_spec,
    target_platform,
):
    category = detect_product_category(
        product_name,
        product_spec,
    )

    price_value = safe_float(price)
    cost_value = safe_float(cost)
    commission_value = safe_float(commission)
    sales_value = safe_int(monthly_sales)
    rating_value = safe_float(rating)

    gross_profit = (
        price_value - cost_value
    )

    commission_amount = (
        price_value
        * commission_value
        / 100
    )

    estimated_profit = (
        gross_profit
        - commission_amount
    )

    if price_value > 0:
        margin = (
            estimated_profit
            / price_value
            * 100
        )
    else:
        margin = 0

    if rating_value >= 4.8:
        rating_comment = "商品評分表現很好。"
    elif rating_value >= 4.5:
        rating_comment = "商品評分表現不錯。"
    elif rating_value > 0:
        rating_comment = "建議持續觀察商品評價。"
    else:
        rating_comment = "尚未提供商品評分。"

    if sales_value >= 1000:
        sales_comment = "月銷量具備明顯市場需求。"
    elif sales_value >= 100:
        sales_comment = "已有一定市場銷量。"
    elif sales_value > 0:
        sales_comment = "目前銷量較低，建議搭配內容測試。"
    else:
        sales_comment = "尚未提供月銷量。"

    if margin >= 30:
        profit_comment = "估算毛利空間相對充足。"
    elif margin >= 15:
        profit_comment = "估算毛利屬中等，可再優化成本。"
    elif margin > 0:
        profit_comment = "估算利潤偏低，需注意平台及廣告成本。"
    else:
        profit_comment = "目前估算利潤不足，請重新確認售價與成本。"

    return f"""
【AI 商品分析】

商品名稱：
{product_name or "待確認"}

商品分類：
{category}

商品價格：
NT$ {price_value:,.0f}

商品成本：
NT$ {cost_value:,.0f}

分潤比例：
{commission_value:.1f}%

月銷量：
{sales_value:,}

商品評分：
{rating_value:.1f}

商品連結：
{product_link or "待確認"}

商品規格：
{product_spec or "待確認"}

━━━━━━━━━━━━━━━━━━

【市場判斷】

{sales_comment}

{rating_comment}

【利潤估算】

售價：
NT$ {price_value:,.0f}

成本：
NT$ {cost_value:,.0f}

分潤估算：
NT$ {commission_amount:,.0f}

扣除成本與分潤後估算：
NT$ {estimated_profit:,.0f}

估算利潤率：
{margin:.1f}%

{profit_comment}

━━━━━━━━━━━━━━━━━━

【內容方向】

蝦皮：
主打商品特色、規格、使用情境與購買理由。

TikTok：
使用短影音開場吸引注意，再展示商品細節與使用情境。

圖片：
以商品本體作為主要視覺焦點。

影片：
建議使用 9:16 直式商品影片。

━━━━━━━━━━━━━━━━━━

【AI 誤判保護】

圖片模糊、多商品或資訊不足時：
以最大、最清楚、品牌最容易辨識的商品作為主體。

無法確認的商品資訊：
標記「待確認」。

禁止自行虛構：
品牌、規格、價格、認證、療效或其他商品資訊。

目標平台：
{target_platform}
""".strip()


# ============================
