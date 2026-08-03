import io
import os
import re
import json
import base64
import hashlib
import secrets
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st
from PIL import Image, ImageOps


# =========================================================
# AI 蝦皮半自動化 2.5 PRO
# OpenClaw 多 Provider 控制版
#
# 純 Streamlit
# 不需要 Gemini
# 不需要 Supabase
# 不需要 LINE API
# 不需要 WeChat API
#
# 功能：
# 1. 永久會員
# 2. 登入 / 註冊
# 3. 管理員
# 4. 首頁
# 5. 商品圖片上傳
# 6. 商品分析
# 7. 蝦皮文案
# 8. TikTok 文案
# 9. 即夢 AI 2.5 生圖 Prompt
# 10. 即夢 AI 2.5 影片 Prompt
# 11. OpenClaw Gateway
# 12. 真生成影片中心
# 13. 影片上傳 / 播放 / 下載
# 14. 手機版
#
# 重要：
# OpenClaw 是控制層。
# 真正影片生成仍然需要 OpenClaw 後端有可用 Provider。
# =========================================================


# =========================================================
# Streamlit 頁面
# =========================================================

st.set_page_config(
    page_title="AI 蝦皮半自動化 2.5 PRO",
    page_icon="🦞",
    layout="wide",
    initial_sidebar_state="auto",
)


# =========================================================
# 全域設定
# =========================================================

APP_NAME = "AI 蝦皮半自動化 2.5 PRO"

DATA_DIR = Path("data")
MEMBERS_FILE = DATA_DIR / "members.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)

MAX_IMAGE_SIZE = 1600
MAX_IMAGE_MB = 20
MAX_VIDEO_MB = 300

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

VIDEO_MIME_MAP = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
}


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
    line-height: 1.3;
    margin: 10px 0 10px 0;
    word-break: break-word;
}

.main-subtitle {
    text-align: center;
    font-size: 16px;
    opacity: 0.75;
    margin-bottom: 25px;
    line-height: 1.5;
}

.section-title {
    font-size: 28px;
    font-weight: 800;
    margin-top: 10px;
    margin-bottom: 12px;
}

.card {
    border: 1px solid rgba(128,128,128,.25);
    border-radius: 16px;
    padding: 18px;
    margin-bottom: 16px;
}

.small-note {
    opacity: .7;
    font-size: 13px;
}

div.stButton > button {
    min-height: 44px;
    border-radius: 10px;
    font-weight: 600;
}

div[data-testid="stDownloadButton"] button {
    min-height: 44px;
    border-radius: 10px;
}

@media (max-width: 768px) {

    .block-container {
        padding-top: 3.2rem !important;
        padding-left: 0.9rem !important;
        padding-right: 0.9rem !important;
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
        padding-top: 2.8rem !important;
        padding-left: 0.7rem !important;
        padding-right: 0.7rem !important;
    }

    .main-title {
        font-size: 24px;
    }

}

</style>
""",
    unsafe_allow_html=True,
)


# =========================================================
# Session 初始化
# =========================================================

def initialize_session():
    defaults = {
        "logged_in": False,
        "page": "home",
        "username": "",
        "member": {},

        "analysis_result": "",
        "generated_copy": "",
        "tiktok_copy": "",
        "jimeng_image_prompt": "",
        "jimeng_video_prompt": "",
        "compliance_result": "",

        "video_product_name": "",
        "video_product_spec": "",
        "video_target_platform": "蝦皮＋TikTok",
        "video_duration": 10,
        "video_image_bytes": None,

        "video_task_id": "",
        "video_status": "",
        "video_url": "",
        "video_bytes": None,
        "video_name": "",
        "video_mime": "video/mp4",

        "uploaded_video_bytes": None,
        "uploaded_video_name": "",
        "uploaded_video_mime": "video/mp4",

        "openclaw_status": "",
        "openclaw_last_response": "",

        "login_username": "",
        "login_password": "",

        "register_name": "",
        "register_username": "",
        "register_email": "",
        "register_password": "",
        "register_password2": "",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


initialize_session()


# =========================================================
# 會員資料
# =========================================================

def load_members():
    if not MEMBERS_FILE.exists():
        return []

    try:
        with open(MEMBERS_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

    except Exception:
        return []

    return []


def save_members(members):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

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


# =========================================================
# 密碼
# =========================================================

def hash_password(password):
    salt = secrets.token_hex(16)

    digest = hashlib.sha256(
        (salt + str(password)).encode("utf-8")
    ).hexdigest()

    return f"{salt}${digest}"


def verify_password(password, saved_value):
    try:
        salt, saved_hash = saved_value.split("$", 1)

        digest = hashlib.sha256(
            (salt + str(password)).encode("utf-8")
        ).hexdigest()

        return secrets.compare_digest(
            digest,
            saved_hash,
        )

    except Exception:
        return False


# =========================================================
# 管理員
# =========================================================

def ensure_admin():
    members = load_members()

    for member in members:
        if member.get("username") == ADMIN_USERNAME:
            return

    members.append(
        {
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
    )

    save_members(members)


ensure_admin()


# =========================================================
# 會員搜尋
# =========================================================

def find_member(username):
    username = str(username).strip().lower()

    if not username:
        return None

    for member in load_members():
        saved_username = str(
            member.get("username", "")
        ).strip().lower()

        if saved_username == username:
            return member

    return None


def find_member_by_email(email):
    email = str(email).strip().lower()

    if not email:
        return None

    for member in load_members():
        saved_email = str(
            member.get("email", "")
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
    username = str(username).strip().lower()
    password = str(password)
    name = str(name).strip()
    email = str(email).strip().lower()

    if not username:
        return False, "請輸入會員帳號。"

    if len(username) < 3:
        return False, "會員帳號至少 3 個字元。"

    if not re.match(r"^[a-zA-Z0-9_.-]+$", username):
        return False, "帳號只能使用英文、數字、底線、句點或連字號。"

    if not password:
        return False, "請輸入密碼。"

    if len(password) < 4:
        return False, "密碼至少 4 個字元。"

    if find_member(username):
        return False, "帳號已存在。"

    if email and find_member_by_email(email):
        return False, "Email 已經註冊。"

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

    saved_password = str(
        member.get("password_hash", "")
    )

    if not verify_password(
        password,
        saved_password,
    ):
        return False, "invalid"

    return True, member


# =========================================================
# 登出
# =========================================================

def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]

    initialize_session()

    st.rerun()


# =========================================================
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
