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
# 🦞 AI 龍蝦總控版
#
# Gemini 2.5 Flash：
# - 商品圖片辨識
# - 商品分析
# - 蝦皮文案
# - TikTok 文案
# - Facebook 文案
# - Instagram 文案
# - 即夢 AI 2.5 生圖 Prompt
# - 即夢 AI 2.5 影片 Prompt
# - 15 秒爆款影片 Prompt
# - 合規檢查
#
# 影片：
# - MP4
# - MOV
# - WEBM
# - 預覽
# - 下載
#
# 會員：
# - 註冊
# - 登入
# - 30 天會員
# - 管理員
# - members.json
#
# 注意：
# Gemini 2.5 Flash 負責 AI 分析、文案、Prompt。
# Gemini 免費層不在這裡直接產生 MP4。
# 即夢等影片工具負責實際影片生成。
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
# APP 設定
# =========================================================

APP_NAME = "AI 蝦皮半自動化 2.5 PRO"

GEMINI_MODEL = "gemini-2.5-flash"

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
# Streamlit 頁面設定
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
        font-size: 42px;
        font-weight: 800;
        margin-top: 20px;
        margin-bottom: 8px;
    }

    .main-subtitle {
        text-align: center;
        opacity: 0.72;
        margin-bottom: 25px;
    }

    .lobster-box {
        padding: 20px;
        border-radius: 18px;
        border: 1px solid rgba(128,128,128,.25);
        margin: 10px 0 20px 0;
    }

    .result-box {
        padding: 18px;
        border-radius: 14px;
        border: 1px solid rgba(128,128,128,.25);
        margin-bottom: 18px;
    }

    .small-note {
        font-size: 13px;
        opacity: .7;
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

    "last_uploaded_image": None,

    "page": "home",
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# Gemini API Key
# =========================================================

def get_gemini_api_key():
    """
    API Key 優先順序：

    1. Streamlit Secrets
    2. 環境變數
    3. Session State
    """

    key = ""

    try:
        key = st.secrets.get(
            "GEMINI_API_KEY",
            "",
        )
    except Exception:
        key = ""

    if not key:
        key = os.getenv(
            "GEMINI_API_KEY",
            "",
        )

    if not key:
        key = st.session_state.get(
            "api_key",
            "",
        )

    return str(key).strip()


# =========================================================
# Gemini Client
# =========================================================

@st.cache_resource
def create_gemini_client(api_key):
    if not api_key:
        return None

    if not HAS_GENAI:
        return None

    try:
        return genai.Client(
            api_key=api_key
        )
    except Exception:
        return None


# =========================================================
# Gemini API
# =========================================================

def gemini_generate_text(
    prompt,
    image_bytes=None,
    image_mime="image/jpeg",
):
    api_key = get_gemini_api_key()

    if not api_key:
        return (
            "❌ 尚未設定 GEMINI_API_KEY。\n\n"
            "請到左側輸入 Gemini API Key，"
            "或使用 Streamlit Secrets。"
        )

    if not HAS_GENAI:
        return (
            "❌ 尚未安裝 google-genai。\n\n"
            "請確認 requirements.txt 有：\n\n"
            "google-genai"
        )

    client = create_gemini_client(api_key)

    if client is None:
        return "❌ Gemini Client 建立失敗。"

    contents = []

    try:

        if image_bytes:
            image_part = types.Part.from_bytes(
                data=image_bytes,
                mime_type=image_mime,
            )

            contents.append(image_part)

        contents.append(prompt)

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.4,
                max_output_tokens=12000,
            ),
        )

        text = getattr(
            response,
            "text",
            None,
        )

        if text:
            return str(text)

        return "❌ Gemini 沒有回傳文字內容。"

    except Exception as e:

        error_text = str(e)
        lower = error_text.lower()

        if "api key" in lower:
            return (
                "❌ Gemini API Key 錯誤。\n\n"
                "請確認 API Key 是否有效。"
            )

        if "403" in lower:
            return (
                "❌ Gemini API 權限不足。\n\n"
                f"{error_text}"
            )

        if (
            "429" in lower
            or "quota" in lower
            or "resource exhausted" in lower
        ):
            return (
                "❌ Gemini 免費層級目前達到速率／額度限制。\n\n"
                "請稍後再試。\n\n"
                f"詳細資訊：{error_text}"
            )

        if "404" in lower or "not found" in lower:
            return (
                "❌ Gemini 模型目前無法使用。\n\n"
                f"目前模型：{GEMINI_MODEL}\n\n"
                f"{error_text}"
            )

        return (
            "❌ Gemini 呼叫失敗。\n\n"
            f"{error_text}"
        )


# =========================================================
# 密碼處理
# =========================================================

def hash_password(password):
    salt = secrets.token_hex(16)

    digest = hashlib.sha256(
        (
            salt
            + str(password)
        ).encode("utf-8")
    ).hexdigest()

    return f"{salt}${digest}"


def verify_password(
    password,
    saved_password,
):
    try:
        salt, saved_hash = saved_password.split(
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
# 建立管理員
# =========================================================

def ensure_admin():

    members = load_members()

    for member in members:

        if (
            str(
                member.get(
                    "username",
                    "",
                )
            ).lower()
            == ADMIN_USERNAME
        ):
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
# 查詢會員
# =========================================================

def find_member(username):

    username = str(
        username
    ).strip().lower()

    for member in load_members():

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

    email = str(
        email
    ).strip().lower()

    if not email:
        return None

    for member in load_members():

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

    username = str(
        username
    ).strip().lower()

    password = str(password)

    name = str(
        name
    ).strip()

    email = str(
        email
    ).strip().lower()

    if len(username) < 3:
        return False, "帳號至少需要 3 個字元。"

    if len(password) < 3:
        return False, "密碼至少需要 3 個字元。"

    if find_member(username):
        return False, "帳號已存在。"

    if email and find_member_by_email(email):
        return False, "Email 已註冊。"

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
        return False, "帳號或密碼錯誤。"

    if (
        str(
            member.get(
                "status",
                "active",
            )
        ).lower()
        != "active"
    ):
        return False, "此會員帳號已停用。"

    saved_hash = str(
        member.get(
            "password_hash",
            "",
        )
    )

    if not saved_hash:
        return False, "會員資料異常。"

    if not verify_password(
        password,
        saved_hash,
    ):
        return False, "帳號或密碼錯誤。"

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

        return False, "會員到期日資料異常。"

    if date.today() > expires_date:

        return False, "會員資格已到期。"

    return True, member


# =========================================================
# 登出
# =========================================================

def logout():

    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.user_role = "guest"
    st.session_state.member = {}

    st.session_state.analysis_results = None

    st.session_state.last_video_name = ""
    st.session_state.last_video_bytes = None

    st.rerun()


# =========================================================
# 圖片處理
# =========================================================

def process_uploaded_image(
    uploaded_file
):

    if uploaded_file is None:
        return None, None

    raw = uploaded_file.getvalue()

    if not raw:
        raise ValueError(
            "圖片檔案是空的。"
        )

    size_mb = (
        len(raw)
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
            io.BytesIO(raw)
        )

        image = ImageOps.exif_transpose(
            image
        )

        image.load()

        if image.mode == "RGBA":

            background = Image.new(
                "RGB",
                image.size,
                "white",
            )

            background.paste(
                image,
                mask=image.getchannel(
                    "A"
                ),
            )

            image = background

        else:

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

    except Exception as e:

        raise ValueError(
            f"圖片讀取失敗：{e}"
        )


# =========================================================
# 即夢核心規則
# =========================================================

JIMENG_CORE_RULES = """
【即夢 AI 2.5 商品一致性鎖定】

上傳商品圖片是唯一主要商品來源。

必須保持：
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

def build_product_analysis_prompt(
    product_data
):

    return f"""
你是「AI 蝦皮半自動化 2.5 PRO」的
AI 電商商品分析專家。

請仔細分析使用者提供的商品圖片與資料。

【使用者資料】

商品名稱：
{product_data["product_name"] or "待確認"}

價格：
{product_data["price"] or "待確認"}

成本：
{product_data["cost"] or "待確認"}

分潤：
{product_data["commission"] or "待確認"}

月銷量：
{product_data["sales"] or "待確認"}

商品評分：
{product_data["rating"] or "待確認"}

商品連結：
{product_data["url"] or "待確認"}

商品規格：
{product_data["spec"] or "待確認"}

補充：
{product_data["features"] or "待確認"}

【絕對規則】

1. 不得捏造圖片看不到的資訊。
2. 不清楚的資訊必須寫「待確認」。
3. 不得自行創造品牌。
4. 不得自行創造價格。
5. 不得自行創造容量。
6. 不得自行創造成分。
7. 不得自行創造產地。
8. 不得自行創造功效。
9. 不得自行創造醫療效果。
10. 不得自行創造認證。
11. 不得自行創造優惠。
12. 不得自行創造贈品。
13. 如果圖片有多個物品，選擇最主要、最大、
    最清楚、最具品牌辨識度的商品。
14. 全部使用繁體中文。
15. 不要假裝擁有即時市場銷量資料。

【輸出格式】

# 1｜商品辨識

商品名稱：
品牌：
類別：
主要顏色：
外觀：
材質：
包裝：
Logo：
可辨識文字：
型號：
規格：

# 2｜商品特色

列出 3～5 個
「圖片或使用者資料可以確認」
的特色。

# 3｜AI 選品分析

請分析：

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
第二張圖方向：
商品細節圖：
賣點展示：

# 6｜TikTok 展示建議

前三秒：
商品展示：
鏡頭：
結尾：

# 7｜AI 龍蝦下一步建議

請判斷下一步最適合自動產生：

- 蝦皮文案
- TikTok 文案
- Facebook 文案
- Instagram 文案
- 即夢生圖 Prompt
- 即夢影片 Prompt
- 15 秒爆款影片 Prompt
- 合規檢查

# 8｜即夢 AI 2.5 注意事項

{JIMENG_CORE_RULES}

最後必須提醒：

正式發布前仍需人工確認商品、
價格、規格、品牌、庫存、商品頁
與分潤資格。
"""


# =========================================================
# AI 龍蝦完整生成 Prompt
# =========================================================

def build_lobster_prompt(
    product_data,
    analysis,
):

    return f"""
你現在是「🦞 AI 龍蝦總控」。

你的任務是把一個商品從：
商品圖片
→ 商品資料
→ 商品分析
→ 電商文案
→ 短影音腳本
→ 即夢 Prompt
→ 合規檢查

一次整理完成。

==================================================
【商品資料】
==================================================

商品名稱：
{product_data["product_name"] or "待確認"}

價格：
{product_data["price"] or "待確認"}

成本：
{product_data["cost"] or "待確認"}

分潤：
{product_data["commission"] or "待確認"}

月銷量：
{product_data["sales"] or "待確認"}

商品評分：
{product_data["rating"] or "待確認"}

商品連結：
{product_data["url"] or "待確認"}

商品規格：
{product_data["spec"] or "待確認"}

補充：
{product_data["features"] or "待確認"}

平台：
{product_data["platform"]}

==================================================
【Gemini 商品分析】
==================================================

{analysis}

==================================================
【絕對規則】
==================================================

不得捏造任何商品資訊。

不知道：
→ 寫「待確認」

不得虛構：

- 品牌
- 價格
- 規格
- 容量
- 成分
- 產地
- 功效
- 醫療效果
- 認證
- 優惠
- 贈品
- 銷量
- 評價

不得誇大。

==================================================
【1｜蝦皮完整上架】
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

0–3 秒：
3–7 秒：
7–12 秒：
12–15 秒：

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
【5｜即夢 AI 2.5 1:1 蝦皮主圖】
==================================================

請輸出完整 English Prompt。

要求：

- exact original product
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
- clean composition
- sharp product details
- no people
- no hands

### Negative Prompt

必須包含：

text distortion,
logo distortion,
label distortion,
wrong packaging,
wrong product,
extra product,
duplicate product,
deformed product,
product deformation,
watermark,
blur,
low quality,
people,
hands,
model,
fake text,
fake logo

==================================================
【6｜即夢 AI 2.5 9:16 商品海報】
==================================================

完整 English Prompt。

要求：

9:16 vertical

premium advertising photography

product centered

exact original product identity

original packaging

original logo

original label

original color

original proportions

realistic lighting

professional commercial composition

no people

no hands

no watermark

### Negative Prompt

==================================================
【7｜即夢 AI 2.5 商品細節圖】
============
