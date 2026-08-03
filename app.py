import io
import os
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
# OpenClaw 龍蝦整合版
#
# 完整功能：
# 1. 會員註冊
# 2. 會員登入
# 3. 永久會員
# 4. 管理員
# 5. 商品圖片上傳
# 6. 商品資料
# 7. 商品分析
# 8. 蝦皮文案
# 9. TikTok 文案
# 10. 即夢 AI 2.5 生圖 Prompt
# 11. 即夢 AI 2.5 影片 Prompt
# 12. 真生成影片中心
# 13. OpenClaw Gateway
# 14. Provider 自動切換
# 15. MP4 / MOV / WEBM
# 16. 手機優化
# 17. Session 路由
# 18. 重新整理後安全處理
#
# 本版本不需要：
# Gemini API
# Supabase
# LINE API
# WeChat API
#
# 注意：
# OpenClaw 是控制層。
# 真正影片生成仍需要你設定可用的影片 Provider。
# =========================================================


# =========================================================
# Streamlit 頁面設定
# =========================================================

st.set_page_config(
    page_title="AI 蝦皮半自動化 2.5 PRO｜OpenClaw",
    page_icon="🦞",
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
        margin-top: 5px;
        margin-bottom: 10px;
        line-height: 1.3;
        word-break: break-word;
    }

    .main-subtitle {
        text-align: center;
        font-size: 17px;
        opacity: .75;
        margin-bottom: 25px;
        line-height: 1.5;
    }

    .page-title {
        font-size: 30px;
        font-weight: 900;
        margin-bottom: 8px;
        line-height: 1.3;
    }

    .result-box {
        padding: 18px;
        border-radius: 14px;
        border: 1px solid rgba(128,128,128,.25);
        margin-bottom: 18px;
    }

    div.stButton > button {
        min-height: 46px;
        border-radius: 10px;
        font-weight: 700;
    }

    div[data-testid="stDownloadButton"] button {
        min-height: 46px;
        border-radius: 10px;
    }

    @media (max-width: 768px) {

        .block-container {
            padding-top: 3.2rem !important;
            padding-left: .9rem !important;
            padding-right: .9rem !important;
        }

        .main-title {
            font-size: 27px;
        }

        .main-subtitle {
            font-size: 14px;
        }

        .page-title {
            font-size: 24px;
        }
    }

    @media (max-width: 480px) {

        .block-container {
            padding-top: 2.8rem !important;
        }

        .main-title {
            font-size: 24px;
        }

        .main-subtitle {
            font-size: 13px;
        }

        .page-title {
            font-size: 22px;
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
    "page": "login",
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
    "video_target_platform": "TikTok",
    "video_duration": 10,
    "video_image_bytes": None,

    "openclaw_status": "",
    "openclaw_last_response": "",

    "video_task_id": "",
    "video_status": "",
    "video_url": "",

    "video_bytes": None,
    "video_name": "",
    "video_mime": "video/mp4",

    "uploaded_video_bytes": None,
    "uploaded_video_name": "",
    "uploaded_video_mime": "video/mp4",
}


for key, default_value in DEFAULT_SESSION.items():

    if key not in st.session_state:
        st.session_state[key] = default_value


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
        ) as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

    except Exception:
        return []

    return []


def save_members(members):
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

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
        (
            salt + str(password)
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
                salt + str(password)
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

    if not username:
        return None

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

    if not password:
        return False, "請輸入密碼。"

    if len(password) < 4:
        return False, "密碼至少需要 4 個字元。"

    if find_member(username):
        return False, "帳號已存在。"

    if email and find_member_by_email(email):
        return False, "Email 已註冊。"

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

    status = str(
        member.get(
            "status",
            "active",
        )
    ).lower()

    if status != "active":
        return False, "disabled"

    password_hash = str(
        member.get(
            "password_hash",
            "",
        )
    )

    if not verify_password(
        password,
        password_hash,
    ):
        return False, "invalid"

    return True, member


# =========================================================
# 登出
# =========================================================

def logout():

    for key, value in DEFAULT_SESSION.items():
        st.session_state[key] = value

    st.session_state.page = "login"

    st.rerun()


# =========================================================
# Secrets / Environment
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


def openclaw_is_configured():

    return bool(
        get_openclaw_url()
        and get_openclaw_token()
    )


def openclaw_headers():

    headers = {
        "Content-Type": "application/json",
    }

    token = get_openclaw_token()

    if token:
        headers["Authorization"] = (
            f"Bearer {token}"
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

    url = (
        gateway_url
        + "/tools/invoke"
    )

    payload = {
        "tool": tool_name,
        "args": args,
    }

    response = requests.post(
        url,
        headers=openclaw_headers(),
        json=payload,
        timeout=timeout,
    )

    if response.status_code >= 400:

        raise RuntimeError(
            "OpenClaw Gateway 呼叫失敗\n"
            f"HTTP：{response.status_code}\n"
            f"{response.text[:2000]}"
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
                "action": "list",
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
            "圖片檔案內容是空的。"
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
        f"{product_name or ''} "
        f"{product_spec or ''}"
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
# 即夢 AI 2.5 核心規則
# =========================================================

PRODUCT_RULES = """
PRODUCT IDENTITY LOCK

Use the supplied product image as the main and exact
visual reference.

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

DEFAULT SCENE:
No people.
No hands.
No presenter.
No influencer.
No model.
No spokesperson.

PREMIUM COMMERCIAL PRODUCT PHOTOGRAPHY.
Photorealistic.
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

    product_name = (
        str(product_name).strip()
        if product_name
        else "the uploaded product"
    )

    product_spec = (
        str(product_spec).strip()
        if product_spec
        else "unknown"
    )

    target_platform = (
        str(target_platform).strip()
        if target_platform
        else "Shopee and TikTok"
    )

    return f"""
Create a premium commercial product image.

MAIN PRODUCT:
{product_name}

PRODUCT SPECIFICATION:
{product_spec}

TARGET PLATFORM:
{target_platform}

Use the uploaded product image as the ONLY exact
product reference.

PRESERVE:
brand, packaging, shape, proportions, color,
material, logo, label and printed text.

COMPOSITION:
The product is the clear visual focus.
Premium commercial photography.
Clean professional background.
Natural realistic lighting.
High-end e-commerce advertising style.
Photorealistic.
Sharp product details.
Professional composition.

No people.
No hands.
No presenter.
No influencer.
No model.
No spokesperson.

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

Poster text:
Traditional Chinese only if text is needed.

NEGATIVE PROMPT:
people, hands, fingers, presenter, influencer, model,
duplicate product, extra product, wrong product,
wrong brand, wrong logo, wrong package, distorted label,
wrong text, unreadable text, text drift, watermark,
fake price, fake discount, fake claims, deformation,
melting, floating product, low quality, blurry product.
""".strip()


# =========================================================
# 即夢影片 Prompt
# =========================================================

def build_video_prompt(
    product_name,
    product_spec,
    target_platform,
    duration,
):

    product_name = (
        str(product_name).strip()
        i============
# 登出
# =========================================================

def logout():
    for key, value in DEFAULT_SESSION_VALUES.items():
        st.session_state[key] = value

    st.session_state.page = "home"
    st.rerun()


# =========================================================
# Secrets / Environment
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


def openclaw_is_configured():
    return bool(
        get_openclaw_url()
        and get_openclaw_token()
    )


def openclaw_headers():
    headers = {
        "Content-Type": "application/json",
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

    response = requests.post(
        url,
        headers=openclaw_headers(),
        json=payload,
        timeout=timeout,
    )

    if response.status_code >= 400:
        raise RuntimeError(
            "OpenClaw Gateway 呼叫失敗\n\n"
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
            "message": "尚未設定 OpenClaw Gateway",
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
            "message": "OpenClaw 已連線",
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
            "圖片檔案內容是空的。"
        )

    size_mb = (
        len(raw_bytes)
        / 1024
        / 1024
    )

    if size_mb > MAX_IMAGE_MB:
        raise ValueError(
            f"圖片 {size_mb:.1f} MB，"
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

Use the supplied product image as the main and exact
visual reference.

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
"""


# =========================================================
# 即夢 AI 2.5 生圖 Prompt
# =========================================================

def build_image_prompt(
    product_name,
    product_spec,
    target_platform,
):
    product_name = (
        str(product_name).strip()
        if product_name
        else "the uploaded product"
    )

    product_spec = (
        str(product_spec).strip()
        if product_spec
        else "unknown"
    )

    target_platform = (
        str(target_platform).strip()
        if target_platform
        else "Shopee and TikTok"
    )

    return f"""
Create a premium commercial product image.

Main subject:
{product_name}

Product specification:
{product_spec}

Target platform:
{target_platform}

Use the uploaded product image as the ONLY exact product reference.

Preserve:
brand, packaging, shape, proportions, color,
material, logo, label and printed text.

Composition:
The product is the clear visual focus.
Premium commercial photography.
Clean professional background.
Natural realistic lighting.
High-end e-commerce advertising style.
Photorealistic.
Sharp details.
Professional composition.

No people.
No hands.
No presenter.
No influencer.
No model.
No spokesperson.

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

Poster text:
Traditional Chinese only if text is needed.

Negative prompt:
people, hands, fingers, presenter, influencer, model,
duplicate product, extra product, wrong product,
wrong brand, wrong logo, wrong package, distorted label,
wrong text, unreadable text, text drift, watermark,
fake price, fake discount, fake claims, deformation,
melting, floating product, low quality, blurry product.
""".strip()


# =========================================================
# 即夢 AI 2.5 影片 Prompt
# =========================================================

def build_video_prompt(
    product_name,
    product_spec,
    target_platform,
    duration,
):
    product_name = (
        str(product_name).strip()
        if product_name
        else "the uploaded product"
    )

    product_spec = (
        str(product_spec).strip()
        if product_spec
        else "unknown"
    )

    target_platform = (
        str(target_platform).strip()
        if target_platform
        else "Shopee and TikTok"
    )

    return f"""
Create a premium commercial product advertisement
for {target_platform}.

PRODUCT:
{product_name}

PRODUCT SPECIFICATION:
{product_spec}

VIDEO FORMAT:
Vertical 9:16.

TARGET DURATION:
{duration} seconds.

OPENING:
Start with the complete product centered in frame.
Use the supplied product image as the exact visual reference.
Keep the entire product clearly visible.

MIDDLE:
Slow cinematic camera push-in.
Show the product from a clean commercial angle.
Use subtle camera movement.
Show realistic material, package and surface details.
Maintain exact product identity.

CAMERA:
Smooth professional commercial camera movement.
No sudden camera shake.
No rapid cuts.
No unnecessary transitions.

ENDING:
Return to a clean centered product shot.
Keep the product stable.
Hold the final frame briefly.

COMMERCIAL STYLE:
Premium e-commerce advertising.
Photorealistic.
Clean.
Modern.
High-end product photography.
Strong lighting.
Realistic shadows.
Sharp product details.

IMPORTANT:
The uploaded product is the only main product.
Do not invent product details.
Do not invent brand information.
Do not invent prices.
Do not invent claims.

{PRODUCT_RULES}

NEGATIVE PROMPT:
people, person, hands, fingers, presenter, influencer,
model, spokesperson, duplicate product, extra product,
wrong product, wrong brand, wrong logo, wrong packaging,
changed label, changed text, text drift,
warped package, melting product, floating package,
deformed product, flicker, unstable product identity,
fake price, fake discount, fake claim, fake certification,
watermark, low quality, blurry product, CGI-looking product,
unrealistic material, camera shake.
""".strip()


# =========================================================
# 商品分類
# =========================================================

def detect_product_c  if not member:
        return False, "invalid"

    if (
        str(
            member.get(
                "status",
                "active",
            )
        ).lower()
        != "active"
    ):
        return False, "disabled"

    if not verify_password(
        password,
        str(
            member.get(
                "password_hash",
                "",
            )
        ),
    ):
        return False, "invalid"

    return True, member


# =========================================================
# 持久登入 Token
#
# 這裡是本次修正「重新整理後首頁消失」的核心。
#
# Streamlit session_state 重新整理後會重建。
# 因此另外建立一組登入 token：
#
# URL query parameter
#       ↓
# sessions.json
#       ↓
# 找到會員
#       ↓
# 自動恢復登入
#       ↓
# 自動進入首頁
# =========================================================

def create_login_token(member):

    raw_token = secrets.token_urlsafe(32)

    token_hash = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()

    sessions = load_sessions()

    sessions.append(
        {
            "token_hash": token_hash,
            "member_id": member.get("id"),
            "username": member.get("username"),
            "created_at": datetime.now().isoformat(),
        }
    )

    # 最多保留最近 100 個 session
    sessions = sessions[-100:]

    save_sessions(sessions)

    return raw_token


def delete_login_token(raw_token):

    if not raw_token:
        return

    token_hash = hashlib.sha256(
        str(raw_token).encode("utf-8")
    ).hexdigest()

    sessions = load_sessions()

    sessions = [
        item
        for item in sessions
        if item.get("token_hash")
        != token_hash
    ]

    save_sessions(sessions)


def get_member_from_token(raw_token):

    if not raw_token:
        return None

    token_hash = hashlib.sha256(
        str(raw_token).encode("utf-8")
    ).hexdigest()

    sessions = load_sessions()

    for item in sessions:

        if (
            item.get("token_hash")
            == token_hash
        ):

            member_id = item.get(
                "member_id"
            )

            member = find_member_by_id(
                member_id
            )

            if not member:
                return None

            if (
                str(
                    member.get(
                        "status",
                        "active",
                    )
                ).lower()
                != "active"
            ):
                return None

            return member

    return None


# =========================================================
# Session State
# =========================================================

DEFAULT_SESSION_VALUES = {

    "logged_in": False,

    "page": "home",

    "username": "",

    "member": {},

    "login_token": "",

    "analysis_result": "",

    "generated_copy": "",

    "tiktok_copy": "",

    "jimeng_image_prompt": "",

    "jimeng_video_prompt": "",

    "compliance_result": "",

    "openclaw_status": "",

    "openclaw_last_response": "",

    "video_task_id": "",

    "video_status": "",

    "video_url": "",

    "video_bytes": None,

    "video_name": "",

    "video_mime": "video/mp4",

    "uploaded_video_bytes": None,

    "uploaded_video_name": "",

    "uploaded_video_mime": "video/mp4",

    "video_product_name": "",

    "video_product_spec": "",

    "video_target_platform": "TikTok",

    "video_duration": 10,

    "video_image_bytes": None,
}


for key, value in DEFAULT_SESSION_VALUES.items():

    if key not in st.session_state:

        st.session_state[key] = value


# =========================================================
# 重新整理後自動恢復登入
# =========================================================

def restore_login_from_url():

    if st.session_state.logged_in:
        return

    try:

        token = st.query_params.get(
            "session",
            "",
        )

    except Exception:

        token = ""

    if not token:
        return

    member = get_member_from_token(
        token
    )

    if member:

        st.session_state.logged_in = True

        st.session_state.username = (
            member.get(
                "username",
                "",
            )
        )

        st.session_state.member = member

        st.session_state.login_token = token

        # 核心：
        # 重新整理後直接回首頁
        st.session_state.page = "home"


restore_login_from_url()


# =========================================================
# 登入成功
# =========================================================

def login_success(member):

    token = create_login_token(
        member
    )

    st.session_state.logged_in = True

    st.session_state.username = (
        member.get(
            "username",
            "",
        )
    )

    st.session_state.member = member

    st.session_state.login_token = token

    # 登入後一定進首頁
    st.session_state.page = "home"

    try:

        st.query_params["session"] = token

    except Exception:
        pass


# =========================================================
# 登出
# =========================================================

def logout():

    token = st.session_state.get(
        "login_token",
        "",
    )

    delete_login_token(token)

    for key, value in DEFAULT_SESSION_VALUES.items():

        st.session_state[key] = value

    try:

        st.query_params.clear()

    except Exception:
        pass

    st.rerun()


# =========================================================
# 切換頁面
# =========================================================

def go_page(page):

    st.session_state.page = page

    st.rerun()


# =========================================================
# Secrets / Environment
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


def openclaw_is_configured():

    return bool(
        get_openclaw_url()
        and get_openclaw_token()
    )


# =========================================================
# OpenClaw Header
# =========================================================

def openclaw_headers():

    token = get_openclaw_token()

    headers = {
        "Content-Type": "application/json",
    }

    if token:

        headers["Authorization"] = (
            f"Bearer {token}"
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

    url = (
        gateway_url
        + "/tools/invoke"
    )

    payload = {
        "tool": tool_name,
        "args": args,
    }

    response = requests.post(
        url,
        headers=openclaw_headers(),
        json=payload,
        timeout=timeout,
    )

    if response.status_code >= 400:

        raise RuntimeError(
            "OpenClaw Gateway 呼叫失敗\n\n"
            f"HTTP：{response.status_code}\n\n"
            f"{response.text[:2000]}"
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
            "message": "尚未設定 OpenClaw Gateway",
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
            "message": "OpenClaw 已連線",
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
            "圖片檔案內容是空的。"
        )

    size_mb = (
        len(raw_bytes)
        / 1024
        / 1024
    )

    if size_mb > MAX_IMAGE_MB:

        raise ValueError(
            f"圖片 {size_mb:.1f} MB，"
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


# =========================================================
# Base64
# =========================================================

def image_to_data_url(
    image_bytes
):

    encoded = (
        base64.b64encode(
            image_bytes
        )
        .decode("utf-8")
    )

    return (
        "data:image/jpeg;base64,"
        + encoded
    )


# =========================================================
# 商品規則
# =========================================================

PRODUCT_RULES = """

PRODUCT IDENTITY LOCK

Use the supplied product image as the main and exact
visual reference.

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
"""


# =========================================================
# 影片 Prompt
# =========================================================

def build_video_prompt(
    product_name,
    product_spec,
    target_platform,
    duration,
):

    product_name = (
        product_name.strip()
        if product_name
        else "the uploaded product"
    )

    product_spec = (
        product_spec.strip()
        if product_spec
        else "unknown"
    )

    target_platform = (
        target_platform.strip()
        if target_platform
        else "Shopee and TikTok"
    )

    return f"""
Create a premium commercial product advertisement
for {target_platform}.

PRODUCT:
{product_name}

PRODUCT SPECIFICATION:
{product_spec}

VIDEO FORMAT:
Vertical 9:16.

TARGET DURATION:
{duration} seconds.

OPENING:
Start with the complete product centered in frame.
Use the supplied product image as the exact visual reference.
Keep the entire product clearly visible.

MIDDLE:
Slow cinematic camera push-in.
Show the product from a clean commercial angle.
Use subtle camera movement.
Show realistic material, package and surface details.
Maintain exact product identity.

CAMERA:
Smooth professional commercial camera movement.
No sudden camera shake.
No rapid camera cuts.
No unnecessary transitions.

ENDING:
Return to a clean centered product shot.
Keep the product stable.
Hold the final frame briefly.

COMMERCIAL STYLE:
Premium e-commerce advertising.
Photorealistic.
Clean.
Modern.
High-end product photography.
Strong lighting.
Realistic shadows.
Sharp product details.

IMPORTANT:
The uploaded product is the only main product.
Do not invent product details.
Do not invent brand information.
Do not invent prices.
Do not invent claims.

{PRODUCT_RULES}

NEGATIVE PROMPT:
people, person, hands, fingers, presenter, influencer,
model, spokesperson, duplicate product, extra product,
wrong product, wrong brand, wrong logo, wrong packaging,
changed label, changed text, distorted text, text drift,
warped package, melting product, floating package,
deformed product, flicker, unstable product identity,
fake price, fake discount, fake claim, fake certification,
watermark, low quality, blurry product, CGI-looking product,
unrealistic material, camera shake.
""".strip()


# =========================================================
# 即夢圖片 Prompt
# =========================================================

def build_image_prompt(
    product_name,
    product_spec,
    target_platform,
):

    product_name = (
        product_name.strip()
        if product_name
        else "the uploaded product"
    )

    product_spec = (
        product_spec.strip()
        if product_spec
        else "unknown"
    )

    return f"""
Create a premium commercial product image.

Main subject:
{product_name}

Product specification:
{product_spec}

Target platform:
{target_platform}

Use the uploaded product image as the ONLY exact product reference.

Preserve:
brand, packaging, shape, proportions, color,
material, logo, label and printed text.

Composition:
The product is the clear visual focus.
Premium commercial photography.
Clean professional background.
Natural realistic lighting.
High-end e-commerce advertising style.
Photorealistic.
Sharp details.
Professional composition.

No people.
No hands.
No presenter.
No influencer.
No model.
No spokesperson.

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

Poster text:
Traditional Chinese only if text is needed.

Negative prompt:
people, hands, fingers, presenter, influencer, model,
duplicate product, extra product, wrong product,
wrong brand, wrong logo, wrong package, distorted label,
wrong text, unreadable text, text drift, watermark,
fake price, fake discount, fake claims, deformation,
melting, floating product, low quality, blurry product.
""".strip()


# =========================================================
# 商品分類
# =========================================================

def detect_product_category(
    product_name,
    product_spec="",
):

    text = (
        f"{product_name} "
        f"{product_spec}"
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

    try:
        price_value = float(
            price or 0
        )
    except Exception:
        price_value = 0

    try:
        cost_value = float(
            cost or 0
        )
    except Exception:
        cost_value = 0

    try:
        commission_value = float(
            commission or 0
        )
    except Exception:
        commission_value = 0

    try:
        sales_value = int(
            float(
                monthly_sales or 0
            )
        )
    except Exception:
        sales_value = 0

    try:
        rating_value = float(
            rating or 0
        )
    except Exception:
        rating_value = 0

    gross_profit = (
        price_value
        - cost_value
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
           
