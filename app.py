import io
import os
import json
import hashlib
import secrets
from datetime import date, datetime, timedelta

import streamlit as st
from PIL import Image, ImageOps


# =========================================================
# AI 蝦皮半自動化 2.5 PRO
# Gemini 免費層版本
#
# 功能：
# 1. 會員登入 / 註冊
# 2. 管理員
# 3. Gemini 圖片辨識
# 4. AI 選品分析
# 5. 蝦皮文案
# 6. TikTok 文案
# 7. Facebook / Instagram 文案
# 8. 即夢 AI 2.5 生圖 Prompt
# 9. 即夢 AI 2.5 影片 Prompt
# 10. AI 龍蝦模式
# 11. 影片上傳與預覽
#
# 注意：
# Gemini API 免費層可以用來做文字 / 圖片分析。
# Gemini API 的 Veo 影片生成目前不是免費層。
# 因此本版本產生「影片 Prompt」，影片本身可另外上傳預覽。
# =========================================================


# =========================================================
# Gemini SDK
# =========================================================

try:
    from google import genai
    from google.genai import types

    HAS_GENAI = True

except ImportError:
    genai = None
    types = None
    HAS_GENAI = False


# =========================================================
# 基本設定
# =========================================================

APP_NAME = "AI 蝦皮半自動化 2.5 PRO"

# 目前優先使用免費層可用的模型
PRIMARY_MODEL = "gemini-2.5-flash-lite"
SECONDARY_MODEL = "gemini-2.5-flash"

DATA_DIR = "data"
MEMBERS_FILE = os.path.join(DATA_DIR, "members.json")

MAX_IMAGE_MB = 20
MAX_IMAGE_SIZE = 1600

MAX_VIDEO_MB = 300

ADMIN_USER = "admin"
ADMIN_PASSWORD = "admin123"

os.makedirs(DATA_DIR, exist_ok=True)


# =========================================================
# Streamlit 設定
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

.main-title {
    text-align: center;
    font-size: 40px;
    font-weight: 800;
    margin-top: 15px;
}

.main-subtitle {
    text-align: center;
    opacity: 0.72;
    margin-bottom: 25px;
}

.ai-box {
    padding: 18px;
    border-radius: 14px;
    border: 1px solid rgba(128,128,128,.25);
    margin-bottom: 15px;
}

</style>
""",
    unsafe_allow_html=True,
)


# =========================================================
# Session State
# =========================================================

DEFAULTS = {
    "logged_in": False,
    "username": "",
    "role": "guest",
    "member": {},
    "api_key": "",
    "result": None,
    "video_bytes": None,
    "video_name": "",
    "video_mime": "video/mp4",
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# API Key
# =========================================================

def get_api_key():
    """
    API Key 優先順序：

    1. Streamlit Secrets
    2. 環境變數
    3. Session State
    """

    secret_key = ""

    try:
        secret_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        secret_key = ""

    key = (
        secret_key
        or os.getenv("GEMINI_API_KEY", "")
        or st.session_state.get("api_key", "")
    )

    return str(key).strip()


# =========================================================
# Gemini Client
# =========================================================

@st.cache_resource(show_spinner=False)
def get_client(key):
    if not HAS_GENAI:
        return None

    if not key:
        return None

    return genai.Client(api_key=key)


# =========================================================
# Gemini 呼叫
# =========================================================

def gemini_generate(prompt, image_bytes=None):
    """
    Gemini 免費層文字 / 圖片分析。

    優先：
    gemini-2.5-flash-lite

    備援：
    gemini-2.5-flash
    """

    key = get_api_key()

    if not key:
        return "❌ 尚未設定 Gemini API Key。"

    if not HAS_GENAI:
        return (
            "❌ 尚未安裝 google-genai。\n\n"
            "請確認 requirements.txt 有：\n"
            "google-genai"
        )

    try:
        ai_client = get_client(key)

        if ai_client is None:
            return "❌ Gemini Client 建立失敗。"

        contents = []

        if image_bytes:
            image_part = types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/jpeg",
            )
            contents.append(image_part)

        contents.append(prompt)

        models = [
            PRIMARY_MODEL,
            SECONDARY_MODEL,
        ]

        errors = []

        for model_name in models:
            try:
                response = ai_client.models.generate_content(
                    model=model_name,
                    contents=contents,
                )

                text = getattr(response, "text", None)

                if text and text.strip():
                    return text.strip()

                errors.append(
                    f"{model_name}: 沒有文字回傳"
                )

            except Exception as exc:
                errors.append(
                    f"{model_name}: {str(exc)}"
                )

        return (
            "❌ Gemini 呼叫失敗。\n\n"
            + "\n".join(errors)
        )

    except Exception as exc:
        return f"❌ Gemini 初始化或呼叫錯誤：{exc}"


# =========================================================
# API 測試
# =========================================================

def test_gemini():
    prompt = """
請只回答：

Gemini API 測試成功。

然後再加一句：

目前可以正常進行 AI 商品分析。
"""

    return gemini_generate(prompt)


# =========================================================
# 密碼
# =========================================================

def hash_password(password):
    salt = secrets.token_hex(16)

    hashed = hashlib.sha256(
        (salt + password).encode("utf-8")
    ).hexdigest()

    return salt + "$" + hashed


def verify_password(password, saved):
    try:
        salt, saved_hash = saved.split("$", 1)

        current_hash = hashlib.sha256(
            (salt + password).encode("utf-8")
        ).hexdigest()

        return secrets.compare_digest(
            current_hash,
            saved_hash,
        )

    except Exception:
        return False


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
        ) as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

        return []

    except Exception:
        return []


def save_members(members):
    with open(
        MEMBERS_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            members,
            file,
            ensure_ascii=False,
            indent=2,
        )


def ensure_admin():
    members = load_members()

    exists = any(
        str(member.get("username", "")).lower()
        == ADMIN_USER.lower()
        for member in members
    )

    if exists:
        return

    admin = {
        "id": secrets.token_hex(8),
        "username": ADMIN_USER,
        "password_hash": hash_password(ADMIN_PASSWORD),
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


def find_member(username):
    username = str(username).strip().lower()

    for member in load_members():
        if (
            str(member.get("username", "")).lower()
            == username
        ):
            return member

    return None


def register_member(
    username,
    password,
    name,
    email,
):
    username = str(username).strip().lower()
    password = str(password)
    name = str(name).strip()
    email = str(email).strip().lower()

    if len(username) < 3:
        return False, "帳號至少 3 個字元。"

    if len(password) < 3:
        return False, "密碼至少 3 個字元。"

    if find_member(username):
        return False, "帳號已存在。"

    members = load_members()

    if email:
        for member in members:
            if (
                str(member.get("email", "")).lower()
                == email
            ):
                return False, "Email 已註冊。"

    member = {
        "id": secrets.token_hex(8),
        "username": username,
        "password_hash": hash_password(password),
        "name": name or username,
        "email": email,
        "role": "member",
        "status": "active",
        "expires": (
            date.today()
            + timedelta(days=30)
        ).isoformat(),
        "created_at": datetime.now().isoformat(),
    }

    members.append(member)
    save_members(members)

    return True, "註冊成功，可以登入。"


def login_member(username, password):
    member = find_member(username)

    if not member:
        return False, "帳號或密碼錯誤。"

    if not verify_password(
        password,
        str(member.get("password_hash", "")),
    ):
        return False, "帳號或密碼錯誤。"

    if member.get("status") != "active":
        return False, "帳號目前已停用。"

    expires = member.get("expires", "")

    try:
        expiry_date = date.fromisoformat(expires)

        if date.today() > expiry_date:
            return False, "會員資格已到期。"

    except Exception:
        return False, "會員到期日資料錯誤。"

    return True, member


# 建立管理員
ensure_admin()


# =========================================================
# 圖片處理
# =========================================================

def process_image(upload):
    if upload is None:
        return None, None

    raw = upload.getvalue()

    if len(raw) > MAX_IMAGE_MB * 1024 * 1024:
        raise ValueError(
            f"圖片不可超過 {MAX_IMAGE_MB} MB。"
        )

    image = Image.open(
        io.BytesIO(raw)
    )

    image = ImageOps.exif_transpose(image)

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


# =========================================================
# 核心規則
# =========================================================

RULES = """
【商品原貌鎖定】

上傳的商品圖片是主要商品來源。

必須盡可能保持：

1. 原品牌
2. 原包裝
3. 原形狀
4. 原比例
5. 原顏色
6. 原材質
7. 原 Logo
8. 原標籤
9. 原印刷文字
10. 原規格

禁止：

- 改品牌
- 改 Logo
- 改包裝
- 改文字
- 商品變形
- 商品融化
- 商品漂移
- 商品閃爍
- 商品消失
- 商品複製
- 新增第二個主要商品
- 假價格
- 假折扣
- 假贈品
- 假認證
- 假規格
- 假功效
- 醫療效果

預設：

- 不出現人物
- 不出現手
- 不出現模特兒
- 不出現主持人

如果資料無法從圖片確認：

必須寫「待確認」。

絕對禁止自行捏造商品資訊。
"""


# =========================================================
# AI 龍蝦模式
# =========================================================

LOBSTER_RULES = """
【AI 龍蝦模式】

你是一名「AI 龍蝦」電商創意總控。

AI 龍蝦不是亂改商品，而是：

1. 精準辨識商品
2. 保護商品原貌
3. 分析電商賣點
4. 設計高轉換內容
5. 設計短影音
6. 設計商品視覺
7. 設計即夢 AI 2.5 Prompt
8. 保持商業合規
9. 不捏造未知資訊

商品本身永遠優先。
"""


# =========================================================
# 商品分析 Prompt
# =========================================================

def build_analysis_prompt(product):
    return """
你是「AI 蝦皮半自動化 2.5 PRO」的商品分析 AI。

同時啟用：

AI 龍蝦模式。

請分析上傳的商品圖片與以下資料。

【商品資料】

商品名稱：
{name}

價格：
{price}

成本：
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

補充資訊：
{features}

銷售平台：
{platform}


==================================================
# 1 商品辨識
==================================================

商品名稱：
品牌：
類別：
顏色：
形狀：
外觀：
材質：
包裝：
Logo：
圖片可辨識文字：
型號：
規格：

無法確認的資料必須寫：

待確認。


==================================================
# 2 商品特色
==================================================

請列出 3～5 個「圖片或使用者資料可以確認」的特色。

禁止捏造。


==================================================
# 3 AI 選品分析
==================================================

視覺吸引力：
電商展示潛力：
短影音潛力：
社群內容潛力：
內容製作難度：
合規風險：

推薦分數：

0～100。


==================================================
# 4 蝦皮展示策略
==================================================

主圖方向：
第二張圖片：
第三張圖片：
商品細節：
賣點排序：


==================================================
# 5 TikTok 策略
==================================================

前 3 秒 Hook：
15 秒影片方向：
30 秒影片方向：


==================================================
# 6 AI 龍蝦策略
==================================================

請提出：

商品最適合的視覺風格：
商品最適合的影片風格：
商品最適合的場景：
商品最適合的鏡頭語言：
商品最值得強調的視覺賣點：


==================================================
# 核心規則
==================================================

{rules}

{lobster}

最後提醒：

正式發布前仍需要人工確認：

商品名稱、價格、規格、品牌、庫存、圖片、影片、商品頁與分潤資格。
""".format(
        name=product["name"] or "待確認",
        price=product["price"] or "待確認",
        cost=product["cost"] or "待確認",
        commission=product["commission"] or "待確認",
        sales=product["sales"] or "待確認",
        rating=product["rating"] or "待確認",
        url=product["url"] or "待確認",
        spec=product["spec"] or "待確認",
        features=product["features"] or "待確認",
        platform=product["platform"],
        rules=RULES,
        lobster=LOBSTER_RULES,
    )


# =========================================================
# 文案 + 即夢 Prompt
# =========================================================

def build_content_prompt(product, analysis):
    return """
你是「AI 蝦皮半自動化 2.5 PRO」。

請根據：

1. 商品圖片
2. 商品資料
3. AI 商品分析

產生完整電商內容。

【商品】

商品名稱：
{name}

價格：
{price}

規格：
{spec}

補充資訊：
{features}

平台：
{platform}


==================================================
# 1 蝦皮
==================================================

商品標題 1：
商品標題 2：
商品標題 3：

SEO 關鍵字：

短描述：

完整商品描述：

核心特色：

商品規格：

注意事項：


==================================================
# 2 TikTok
==================================================

3 秒 Hook：

15 秒腳本：

30 秒腳本：

TikTok 貼文：

CTA：

Hashtag：


==================================================
# 3 Facebook
==================================================

Facebook 貼文：

互動問題：

Hashtag：


==================================================
# 4 Instagram
==================================================

Instagram Caption：

Hashtag：


==================================================
# 5 即夢 AI 2.5 1:1 商品生圖
==================================================

請使用英文。

English Prompt：

Negative Prompt：


==================================================
# 6 即夢 AI 2.5 9:16 商品海報
==================================================

請使用英文。

English Prompt：

Negative Prompt：


==================================================
# 7 即夢 AI 2.5 商品細節圖
==================================================

請使用英文。

English Prompt：

Negative Prompt：


==================================================
# 8 即夢 AI 2.5 15 秒商品影片
==================================================

請使用英文。

English Video Prompt：

0–3 seconds：
商品正面穩定英雄開場。

3–7 seconds：
慢速推近，展示包裝、材質、細節。

7–12 seconds：
平滑環繞商品。

12–15 seconds：
回到正面英雄鏡頭並定格。

Camera：

slow cinematic push-in,
subtle orbit,
smooth movement,
stable framing.

全程：

same product identity,
same packaging,
same logo,
same label,
same color,
same proportions.

禁止：

people,
hands,
models,
extra products,
duplicate products,
deformation,
disappearance,
logo drift,
text drift,
watermark.


==================================================
# 9 AI 龍蝦爆款 15 秒影片
==================================================

請產生完整英文影片 Prompt。

必須包含：

0–3 seconds：
Hook。

3–7 seconds：
商品視覺亮點。

7–12 seconds：
商品細節與核心賣點。

12–15 seconds：
Hero shot + CTA 視覺收尾。


==================================================
# 10 分潤合規檢查
==================================================

商品與圖片一致：
價格：
規格：
品牌：
商品連結：
誇大宣稱：
假贈品：
假認證：
假價格：
錯誤規格：
品牌誤判：

請使用：

✅ 通過
⚠️ 需確認
❌ 有問題


==================================================
# 11 發布前檢查
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


==================================================
# 核心規則
==================================================

{rules}

未知資訊：

一律寫「待確認」。

不要自行發明：

價格、優惠、贈品、認證、成分、產地、功效、醫療效果。
""".format(
        name=product["name"] or "待確認",
        price=product["price"] or "待確認",
        spec=product["spec"] or "待確認",
        features=product["features"] or "待確認",
        platform=product["platform"],
        analysis=analysis,
        rules=RULES,
    )


# =========================================================
# 側邊欄
# =========================================================

def sidebar():

    with st.sidebar:

        st.title("🛒 功能選單")

        if st.session_state.logged_in:

            member = st.session_state.member

            st.write(
                f"👤 **{member.get('name') or member.get('username')}**"
            )

            st.caption(
                f"身份：{member.get('role')}"
            )

            st.caption(
                f"到期：{member.get('expires')}"
            )

            if st.button(
                "🚪 登出",
                use_container_width=True,
            ):
                st.session_state.logged_in = False
                st.session_state.username = ""
                st.session_state.role = "guest"
                st.session_state.member = {}

                st.rerun()

        st.divider()

        st.subheader("🤖 Gemini 免費層")

        key_input = st.text_input(
            "Gemini API Key",
            value=st.session_state.api_key,
            type="password",
            help="建議放在 Streamlit Secrets，不要把 API Key 寫進程式碼。",
        )

        st.session_state.api_key = key_input

        if get_api_key():
            st.success("✅ API Key 已設定")
        else:
            st.warning("⚠️ 尚未設定 API Key")

        st.caption(
            f"主要模型：{PRIMARY_MODEL}"
        )

        st.caption(
            f"備援模型：{SECONDARY_MODEL}"
        )

        if st.button(
            "🔌 測試 Gemini API",
            use_container_width=True,
        ):

            if not get_api_key():
                st.error("請先設定 API Key。")

            elif not HAS_GENAI:
                st.error(
                    "缺少 google-genai 套件。"
                )

            else:
                with st.spinner("測試 Gemini..."):

                    result = test_gemini()

                if result.startswith("❌"):
                    st.error(result)
                else:
                    st.success(result)


# =========================================================
# 登入 / 註冊
# =========================================================

def auth_page():

    st.markdown(
        f"""
<div class="main-title">
🛒 {APP_NAME}
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<div class="main-subtitle">
Gemini AI × AI 龍蝦 × 電商半自動化
</div>
""",
        unsafe_allow_html=True,
    )

    login_tab, register_tab = st.tabs(
        [
            "🔐 登入",
            "📝 註冊",
        ]
    )

    # -----------------------------
    # 登入
    # -----------------------------

    with login_tab:

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

            ok, result = login_member(
                username,
                password,
            )

            if ok:

                st.session_state.logged_in = True
                st.session_state.username = result["username"]
                st.session_state.role = result["role"]
                st.session_state.member = result

                st.rerun()

            else:
                st.error(result)

        st.info(
            "管理員測試帳號：admin / admin123"
        )

    # -----------------------------
    # 註冊
    # -----------------------------

    with register_tab:

        name = st.text_input(
            "姓名 / 暱稱",
            key="register_name",
  
