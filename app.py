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
# OpenClaw 龍蝦 + 多 Provider 自動切換版
#
# Streamlit 手機優化完整版本
#
# 功能：
# 1. 會員註冊 / 登入
# 2. 永久會員
# 3. 管理員
# 4. 商品圖片上傳
# 5. 商品資料
# 6. 蝦皮 / TikTok / 兩者
# 7. 商品分析
# 8. 蝦皮上架文案
# 9. TikTok 文案
# 10. 即夢 AI 2.5 生圖 Prompt
# 11. 即夢 AI 2.5 影片 Prompt
# 12. 真生成影片中心
# 13. OpenClaw Gateway
# 14. OpenClaw video_generate
# 15. Provider 自動切換
# 16. MP4 / MOV / WEBM
# 17. 影片上傳與播放
# 18. 手機優化
# 19. 標題頂部防遮蔽
# 20. Session 防止重複處理
#
# 注意：
# OpenClaw 是控制層，不代表本身提供免費無限影片生成額度。
# 真正影片生成仍須有可用的影片 Provider。
# =========================================================


# =========================================================
# 頁面設定
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


# =========================================================
# 基本設定
# =========================================================

MAX_IMAGE_SIZE = 1600
MAX_IMAGE_MB = 20
MAX_VIDEO_MB = 300

PERMANENT_MEMBER = True

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
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }

    .main-title {
        text-align: center;
        font-size: 38px;
        font-weight: 900;
        margin-top: 10px !important;
        margin-bottom: 12px !important;
        line-height: 1.25;
        word-break: break-word;
    }

    .main-subtitle {
        text-align: center;
        font-size: 17px;
        opacity: 0.75;
        margin-bottom: 30px;
        line-height: 1.5;
        word-break: break-word;
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
        line-height: 1.3;
    }

    .small-note {
        opacity: .75;
        font-size: 14px;
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
            padding-top: 3.5rem !important;
            padding-bottom: 2rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }

        .main-title {
            font-size: 28px;
            margin-top: 5px !important;
            margin-bottom: 10px !important;
            line-height: 1.3;
        }

        .main-subtitle {
            font-size: 14px;
            margin-bottom: 20px;
            line-height: 1.5;
        }

        .video-title {
            font-size: 23px;
        }

        .result-box {
            padding: 14px;
        }
    }

    @media (max-width: 480px) {

        .block-container {
            padding-top: 3rem !important;
            padding-left: .8rem !important;
            padding-right: .8rem !important;
        }

        .main-title {
            font-size: 25px;
        }

        .main-subtitle {
            font-size: 13px;
        }

        .video-title {
            font-size: 21px;
        }
    }

    </style>
    """,
    unsafe_allow_html=True,
)


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
            salt
            + str(password)
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
# 管理員
# =========================================================

def ensure_admin():

    members = load_members()

    for member in members:

        if (
            member.get("username")
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

    email = (
        str(email)
        .strip()
        .lower()
    )

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

    username = (
        str(username)
        .strip()
        .lower()
    )

    email = (
        str(email)
        .strip()
        .lower()
    )

    if not username:
        return False, "請輸入帳號。"

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
        "name": str(name).strip(),
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

        if (
            member.get("id")
            == member_id
        ):

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
# Session
# =========================================================

DEFAULT_SESSION_VALUES = {

    "logged_in": False,

    "page": "login",

    "username": "",

    "member": {},

    "analysis_result": "",

    "generated_copy": "",

    "tiktok_copy": "",

    "jimeng_image_prompt": "",

    "jimeng_video_prompt": "",

    "openclaw_status": "",

    "openclaw_last_response": "",

    "video_task_id": "",

    "video_status": "",

    "video_url": "",

    "video_bytes": None,

    "video_name": "",

    "video_mime": "video/mp4",

    "video_signature": "",

    "uploaded_video_bytes": None,

    "uploaded_video_name": "",

    "uploaded_video_mime": "video/mp4",

    "uploaded_video_signature": "",

}


for key, value in DEFAULT_SESSION_VALUES.items():

    if key not in st.session_state:

        st.session_state[key] = value


# =========================================================
# 登出
# =========================================================

def logout():

    for key, value in DEFAULT_SESSION_VALUES.items():

        st.session_state[key] = value

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
# Base64
# =========================================================

def image_to_data_url(image_bytes):

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
            "食品",
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
        price_value = float(price or 0)
    except Exception:
        price_value = 0

    try:
        cost_value = float(cost or 0)
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
            float(monthly_sales or 0)
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

    if monthly_sales >= 1000:
        sales_comment = "月銷量具備明顯市場需求。"
    elif monthly_sales >= 100:
        sales_comment = "已有一定市場銷量。"
    elif monthly_sales > 0:
        sales_comment = "目前銷量較低，建議搭配內容測試。"
    else:
        sales_comment = "尚未提供月銷量。"

    if margin >= 30:
        profit_comment = "估算毛利空間相對充足。"
    elif margin >= 15:
        profit_comment = "估算毛利屬中等，可再優化成本。"
    elif margin > 0:
        profit_comment = "估算利潤偏低，需注意廣告及平台成本。"
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

━━━━━━━━━━━━━━

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

━━━━━━━━━━━━━━

【內容方向】

蝦皮：
主打商品特色、規格、使用情境與購買理由。

TikTok：
使用短影音開場吸引注意，再展示商品細節與使用情境。

圖片：
以商品本體作為主要視覺焦點，避免過度複雜背景。

影片：
建議使用 9:16 直式商業商品影片。

━━━━━━━━━━━━━━

【AI 誤判保護】

商品圖片如果模糊、多商品或資訊不足：
以最大、最清楚、品牌最容易辨識的商品作為主體。

無法確認的商品資訊：
標記「待確認」。

禁止自行虛構品牌、規格、價格、認證、
療效或其他商品資訊。

目標平台：
{target_platform}
""".strip()


# =========================================================
# 蝦皮文案
# =========================================================

def generate_shopee_copy(
    product_name,
    price,
    product_spec,
    category,
):

    product_name = (
        product_name.strip()
        if product_name
        else "商品"
    )

    price_text = (
        f"NT$ {float(price):,.0f}"
        if str(price).strip()
        else "待確認"
    )

    spec = (
        product_spec.strip()
        if product_spec
        else "待確認"
    )

    return f"""
【商品標題】

{product_name}｜高質感商品｜日常實用推薦｜{category}

【商品賣點】

✨ 商品名稱：
{product_name}

✨ 商品分類：
{category}

✨ 商品價格：
{price_text}

✨ 商品規格：
{spec}

【商品介紹】

✔ 商品資訊以實際商品為準
✔ 商品圖片以實際商品為準
✔ 適合電商商品展示
✔ 清楚呈現商品特色與使用情境
✔ 購買前請確認規格

【購買提醒】

下單前請確認商品規格、尺寸、顏色及數量。
不同螢幕可能造成些微色差。
實際商品以收到商品為準。

【搜尋標籤】

#{category.replace(" ", "")}
#蝦皮購物
#網路購物
#熱門商品
#生活好物
#實用好物
#商品推薦
""".strip()


# =========================================================
# TikTok 文案
# =========================================================

def generate_tiktok_copy(
    product_name,
    product_spec,
    category,
):

    product_name = (
        product_name.strip()
        if product_name
        else "這款商品"
    )

    spec = (
        product_spec.strip()
        if product_spec
        else "詳細規格請看商品頁"
    )

    return f"""
【TikTok 爆款帶貨文案】

🔥 最近看到這款 {product_name}！

如果你正在找
{category} 類型的商品，
這款可以直接加入你的選物清單。

✨ 商品：
{product_name}

✨ 規格：
{spec}

影片建議：

0-3 秒：
先用完整商品畫面吸引注意。

3-8 秒：
慢慢推近商品，
展示包裝、材質與細節。

8-12 秒：
切換商品重點細節，
維持乾淨高級的商業畫面。

最後：
商品置中，
停留一個完整商品畫面。

CTA：

想了解更多商品資訊，
可以到商品頁查看完整規格。

#TikTok購物
#好物推薦
#商品推薦
#生活好物
#{category.replace(" ", "")}
""".strip()


# =========================================================
# 合規檢查
# =========================================================

def compliance_check(
    product_name,
    price,
    product_spec,
):

    text = " ".join(
        [
            str(product_name or ""),
            str(price or ""),
            str(product_spec or ""),
        ]
    )

    risky_words = [
        "100%有效",
        "保證治癒",
        "永久",
        "絕對有效",
        "醫療級",
        "零風險",
        "保證瘦",
        "保證增高",
        "治癌",
        "治療癌症",
    ]

    found = []

    for word in risky_words:

        if word in text:
            found.append(word)

    if found:

        return (
            "⚠️ 發現需要人工確認的高風險宣稱：\n\n"
            + "\n".join(
                f"- {word}"
                for word in found
            )
            + "\n\n建議不要使用未經證實的效果宣稱。"
        )

    return (
        "✅ 基本合規檢查通過。\n\n"
        "未發現預設高風險誇大宣稱。\n"
        "實際上架前仍應依平台規則及商品實際資料確認。"
    )


# =========================================================
# Prompt 組合
# =========================================================

def build_full_workflow(
    product_name,
    product_spec,
    target_platform,
    duration,
):

    image_prompt = build_image_prompt(
        product_name,
        product_spec,
        target_platform,
    )

    video_prompt = build_video_prompt(
        product_name,
        product_spec,
        target_platform,
        duration,
    )

    return (
        image_prompt,
        video_prompt,
    )


# =========================================================
# 影片檔案處理
# =========================================================

def get_video_mime(filename):

    suffix = (
        Path(filename)
        .suffix
        .lower()
    )

    return VIDEO_MIME_MAP.get(
        suffix,
        "video/mp4",
    )


def validate_video_file(uploaded_file):

    if uploaded_file is None:
        raise ValueError(
            "沒有選擇影片。"
        )

    raw = uploaded_file.getvalue()

    if not raw:
        raise ValueError(
            "影片檔案是空的。"
        )

    size_mb = (
        len(raw)
        / 1024
        / 1024
    )

    if size_mb > MAX_VIDEO_MB:

        raise ValueError(
            f"影片大小 {size_mb:.1f} MB，"
            f"超過 {MAX_VIDEO_MB} MB。"
        )

    filename = (
        uploaded_file.name
        or "uploaded_video.mp4"
    )

    mime = get_video_mime(
        filename
    )

    return (
        raw,
        filename,
        mime,
    )


# =========================================================
# Video Response 搜尋
# =========================================================

def recursive_find_value(
    data,
    keys,
):

    if isinstance(data, dict):

        for key in keys:

            if key in data:

                value = data[key]

                if value:
                    return value

        for value in data.values():

            result = recursive_find_value(
                value,
                keys,
            )

            if result:
                return result

    elif isinstance(data, list):

        for item in data:

            result = recursive_find_value(
                item,
                keys,
            )

            if result:
                return result

    return None


# =========================================================
# Base64 影片解碼
# =========================================================

def decode_possible_video(
    value,
):

    if not value:
        return None

    if isinstance(value, bytes):
        return value

    if not isinstance(value, str):
        return None

    text = value.strip()

    if text.startswith(
        "data:video"
    ):

        if "," in text:
            text = text.split(
                ",",
                1,
            )[1]

    try:

        return base64.b64decode(
            text,
            validate=False,
        )

    except Exception:

        return None


# =========================================================
# OpenClaw 影片生成
# =========================================================

def generate_video_with_openclaw(
    image_bytes,
    product_name,
    product_spec,
    target_platform,
    duration,
):

    if not get_openclaw_url():

        raise RuntimeError(
            "尚未設定 OpenClaw Gateway URL。"
        )

    image_data_url = image_to_data_url(
        image_bytes
    )

    prompt = build_video_prompt(
        product_name,
        product_spec,
        target_platform,
        duration,
    )

    args = {

        "action": "generate",

        "prompt": prompt,

        "duration": int(
            duration
        ),

        "aspect_ratio": "9:16",

        "mode": "image_to_video",

        "image": image_data_url,

        "reference_image":
            image_data_url,

        "product_name":
            product_name,

        "target_platform":
            target_platform,

        "provider_strategy":
            "auto",

        "fallback":
            True,

        "output_format":
            "mp4",

    }

    result = openclaw_invoke(
        "video_generate",
        args,
        timeout=600,
    )

    return (
        result,
        prompt,
    )


# =========================================================
# 從 OpenClaw Response 取得影片
# =========================================================

def extract_video_from_response(
    result,
):

    if not result:
        return None, None

    video_keys = [
        "video",
        "video_data",
        "video_base64",
        "base64",
        "content",
        "data",
    ]

    video_value = recursive_find_value(
        result,
        video_keys,
    )

    video_bytes = decode_possible_video(
        video_value
    )

    if video_bytes:

        return (
            video_bytes,
            "generated_video.mp4",
        )

    video_url = recursive_find_value(
        result,
        [
            "video_url",
            "url",
            "download_url",
            "file_url",
        ],
    )

    if video_url:

        return (
            None,
            str(video_url),
        )

    return (
        None,
        None,
    )


# =========================================================
# 任務 ID
# =========================================================

def extract_task_id(result):

    value = recursive_find_value(
        result,
        [
            "task_id",
            "taskId",
            "job_id",
            "jobId",
            "id",
        ],
    )

    if value:
        return str(value)

    return ""


# =========================================================
# 影片狀態
# =========================================================

def query_video_status(
    task_id,
):

    if not task_id:
        raise ValueError(
            "沒有影片任務 ID。"
        )

    result = openclaw_invoke(
        "video_generate",
        {
            "action": "status",
            "task_id": task_id,
        },
        timeout=60,
    )

    return result


# =========================================================
# 下載影片 URL
# =========================================================

def download_video_url(
    url,
):

    if not url:
        return None

    response = requests.get(
        url,
        timeout=300,
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"影片下載失敗：HTTP {response.status_code}"
        )

    content = response.content

    if not content:
        return None

    if len(content) > (
        MAX_VIDEO_MB
        * 1024
        * 1024
    ):
        raise RuntimeError(
            "下載影片超過大小限制。"
        )

    return content


# =========================================================
# OpenClaw 測試
# =========================================================

def render_openclaw_status():

    st.subheader("🦞 OpenClaw 連線狀態")

    url = get_openclaw_url()

    if not url:

        st.warning(
            "目前尚未設定 OPENCLAW_GATEWAY_URL。"
        )

        st.info(
            "網站仍然可以使用商品分析、文案與 "
            "即夢 AI 2.5 Prompt 功能。"
        )

        return

    result = check_openclaw()

    if result.get("available"):

        st.success(
            "🟢 OpenClaw Gateway 已連線"
        )

    else:

        st.error(
            "🔴 OpenClaw 尚未成功連線"
        )

        st.caption(
            result.get(
                "message",
                "",
            )
        )


# =========================================================
# 登入頁
# =========================================================

def login_page():

    st.markdown(
        f"""
        <div class="main-title">
            🦞 {APP_NAME}
        </div>

        <div class="main-subtitle">
            OpenClaw 龍蝦｜蝦皮＋TikTok＋即夢 AI 2.5
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_login, tab_register = st.tabs(
        [
            "🔐 登入",
            "📝 註冊會員",
        ]
    )

    with tab_login:

        st.subheader("會員登入")

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
            "🚀 登入系統",
            use_container_width=True,
        ):

            ok, result = check_login(
                username,
                password,
            )

            if ok:

                st.session_state.logged_in = True

                st.session_state.username = (
                    result.get(
                        "username",
                        "",
                    )
                )

                st.session_state.member = result

                st.session_state.page = "home"

                st.success(
                    "登入成功！"
                )

                st.rerun()

            elif result == "disabled":

                st.error(
                    "此會員帳號目前已停用。"
                )

            else:

                st.error(
                    "帳號或密碼錯誤。"
                )

        st.divider()

        st.caption(
            "測試管理員帳號："
            f"{ADMIN_USERNAME}"
        )

        st.caption(
            "測試管理員密碼："
            f"{ADMIN_PASSWORD}"
        )

    with tab_register:

        st.subheader("建立永久會員")

        name = st.text_input(
            "姓名 / 暱稱",
            key="register_name",
        )

        username = st.text_input(
            "會員帳號",
            key="register_username",
        )

        email = st.text_input(
            "Email",
            key="register_email",
        )

        password = st.text_input(
            "會員密碼",
            type="password",
            key="register_password",
        )

        password2 = st.text_input(
            "再次輸入密碼",
            type="password",
            key="register_password2",
        )

        if st.button(
            "✨ 建立永久會員",
            use_container_width=True,
        ):

            if password != password2:

                st.error(
                    "兩次密碼不一致。"
                )

            else:

                ok, result = create_member(
                    username,
                    password,
                    name,
                    email,
                )

                if ok:

                    st.success(
                        "會員建立成功，請回到登入頁登入。"
                    )

                else:

                    st.error(result)


# =========================================================
# Sidebar
# =========================================================

def render_sidebar():

    with st.sidebar:

        st.markdown(
            "## 🦞 AI 蝦皮半自動化"
        )

        st.caption(
            "2.5 PRO｜OpenClaw"
        )

        st.divider()

        member = st.session_state.member

        st.markdown(
            "### 👤 會員中心"
        )

        st.write(
            f"帳號："
            f"{member.get('username', '')}"
        )

        st.write(
            f"名稱："
            f"{member.get('name', '') or '未設定'}"
        )

        st.success(
            "♾️ 永久會員"
        )

        st.divider()

        st.markdown(
            "### 📌 系統功能"
        )

        if st.button(
            "🏠 首頁",
            use_container_width=True,
        ):
            st.session_state.page = "home"
            st.rerun()

        if st.button(
            "🛒 商品分析",
            use_container_width=True,
        ):
            st.session_state.page = "product"
            st.rerun()

        if st.button(
            "🎬 真生成影片中心",
            use_container_width=True,
        ):
            st.session_state.page = "video"
            st.rerun()

        if st.button(
            "🦞 OpenClaw 狀態",
            use_container_width=True,
        ):
            st.session_state.page = "openclaw"
            st.rerun()

        if member.get("role") == "admin":

            if st.button(
                "👑 管理員中心",
                use_container_width=True,
            ):
                st.session_state.page = "admin"
                st.rerun()

        st.divider()

        if st.button(
            "🚪 登出",
            use_container_width=True,
        ):
            logout()


# =========================================================
# 首頁
# =========================================================

def home_page():

    st.markdown(
        f"""
        <div class="main-title">
            🦞 {APP_NAME}
        </div>

        <div class="main-subtitle">
            OpenClaw 龍蝦半自動化電商內容中心
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.success(
        "🟢 系統已啟動"
    )

    st.markdown(
        """
        ### 🚀 主要功能

        **① 商品圖片辨識與分析**

        上傳商品圖片後，建立商品內容製作流程。

        **② 蝦皮商品上架**

        自動整理商品標題、商品介紹、賣點與標籤。

        **③ TikTok 帶貨內容**

        產生短影音開場、內容節奏與 CTA。

        **④ 即夢 AI 2.5**

        產生生圖 Prompt 與影片 Prompt。

        **⑤ 真生成影片中心**

        商品圖片 → OpenClaw → 影片 Provider → 影片。

        **⑥ Provider 自動切換**

        交由 OpenClaw 根據設定處理影片生成。
        """
    )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "🛒 開始商品分析",
            use_container_width=True,
        ):
            st.session_state.page = "product"
            st.rerun()

    with col2:

        if st.button(
            "🎬 開啟真生成影片中心",
            use_container_width=True,
        ):
            st.session_state.page = "video"
            st.rerun()

    st.divider()

    st.info(
        "💡 如果目前還沒有 OpenClaw Gateway，"
        "你仍然可以使用商品分析、蝦皮文案、"
        "TikTok 文案與即夢 AI 2.5 Prompt。"
    )


# =========================================================
# 商品分析頁
# =========================================================

def product_analysis_page():

    st.markdown(
        '<div class="video-title">🛒 AI 商品分析中心</div>',
        unsafe_allow_html=True,
    )

    st.caption(
        "上傳商品圖片 → 填寫資料 → 產生完整電商內容"
    )

    uploaded = st.file_uploader(
        "📷 上傳商品圖片",
        type=[
            "jpg",
            "jpeg",
            "png",
            "webp",
        ],
        key="product_image_upload",
        help="建議使用清楚、完整的商品照片。",
    )

    image_bytes = None

    if uploaded:

        try:

            image, image_bytes = prepare_image(
                uploaded
            )

            st.image(
                image,
                caption="商品圖片",
                use_container_width=True,
            )

        except Exception as error:

            st.error(str(error))

    st.divider()

    col1, col2 = st.columns(2)

    with col1:

        product_name = st.text_input(
            "商品名稱",
            placeholder="例如：無線藍牙耳機",
        )

        price = st.text_input(
            "商品價格",
            placeholder="例如：699",
        )

        cost = st.text_input(
            "商品成本",
            placeholder="例如：350",
        )

        commission = st.text_input(
            "分潤比例 %",
            placeholder="例如：10",
        )

    with col2:

        monthly_sales = st.text_input(
            "月銷量",
            placeholder="例如：500",
        )

        rating = st.text_input(
            "商品評分",
            placeholder="例如：4.8",
        )

        product_link = st.text_input(
            "商品連結",
            placeholder="可留空",
        )

        product_spec = st.text_area(
            "商品規格",
            placeholder="例如：顏色、尺寸、容量、材質...",
            height=100,
        )

    target_platform = st.selectbox(
        "🎯 選擇平台",
        [
            "蝦皮",
            "TikTok",
            "蝦皮＋TikTok",
        ],
    )

    generation_options = st.multiselect(
        "🤖 選擇生成內容",
        [
            "商品辨識",
            "AI 選品分析",
            "蝦皮上架文案",
            "TikTok 文案",
            "即夢 AI 2.5 生圖指令",
            "即夢 AI 2.5 影片指令",
            "即夢 AI 2.5 爆款帶貨影片",
            "分潤合規檢查",
            "完整流程",
        ],
        default=[
            "完整流程"
        ],
    )

    duration = st.selectbox(
        "🎬 影片秒數",
        [
            5,
            8,
            10,
            12,
            15,
        ],
        index=2,
    )

    if st.button(
        "🚀 開始分析",
        use_container_width=True,
    ):

        if not product_name and not image_bytes:

            st.error(
                "請至少上傳商品圖片或輸入商品名稱。"
            )

        else:

            category = detect_product_category(
                product_name,
                product_spec,
            )

            analysis = analyze_product(
                product_name,
                price,
                cost,
                commission,
                monthly_sales,
                rating,
                product_link,
                product_spec,
                target_platform,
            )

            copy = generate_shopee_copy(
                product_name,
                price,
                product_spec,
                category,
            )

            tiktok = generate_tiktok_copy(
                product_name,
                product_spec,
                category,
            )

            image_prompt, video_prompt = (
                build_full_workflow(
                    product_name,
                    product_spec,
                    target_platform,
                    duration,
                )
            )

            compliance = compliance_check(
                product_name,
                price,
                product_spec,
            )

            st.session_state.analysis_result = analysis
            st.session_state.generated_copy = copy
            st.session_state.tiktok_copy = tiktok
            st.session_state.jimeng_image_prompt = image_prompt
            st.session_state.jimeng_video_prompt = video_prompt

            st.success(
                "分析完成！"
            )

    if st.session_state.analysis_result:

        st.divider()

        st.subheader(
            "📊 商品分析"
        )

        st.code(
            st.session_state.analysis_result,
            language="text",
        )

        st.subheader(
            "🛒 蝦皮上架文案"
        )

        st.code(
            st.session_state.generated_copy,
            language="text",
        )

        st.subheader(
            "🎵 TikTok 文案"
        )

        st.code(
            st.session_state.tiktok_copy,
            language="text",
        )

        st.subheader(
            "🖼️ 即夢 AI 2.5 生圖指令"
        )

        st.code(
            st.session_state.jimeng_image_prompt,
            language="text",
        )

        st.subheader(
            "🎬 即夢 AI 2.5 影片指令"
        )

        st.code(
            st.session_state.jimeng_video_prompt,
            language="text",
        )

        st.subheader(
            "🛡️ 分潤／內容合規檢查"
        )

        st.code(
            compliance_check(
                product_name,
                price,
                product_spec,
            ),
            language="text",
        )

        st.divider()

        if st.button(
            "🎬 帶這個商品進入真生成影片中心",
            use_container_width=True,
        ):

            st.session_state.video_product_name = (
                product_name
            )

            st.session_state.video_product_spec = (
                product_spec
            )

            st.session_state.video_target_platform = (
                target_platform
            )

            st.session_state.video_duration = (
                duration
            )

            st.session_state.video_image_bytes = (
                image_bytes
            )

            st.session_state.page = "video"

            st.rerun()


# =========================================================
# 真生成影片中心
# =========================================================

def video_center_page():

    st.markdown(
        '<div class="video-title">🎬 真生成影片中心</div>',
        unsafe_allow_html=True,
    )

    st.caption(
        "商品圖片 → OpenClaw → Provider → 真實影片"
    )

    st.info(
        "📱 手機操作：先上傳商品圖片，再按「開始生成影片」。"
    )

    # -----------------------------------------------------
    # 產品資料
    # -----------------------------------------------------

    product_name = st.text_input(
        "商品名稱",
        value=st.session_state.get(
            "video_product_name",
            "",
        ),
        key="video_product_name_input",
    )

    product_spec = st.text_area(
        "商品規格",
        value=st.session_state.get(
            "video_product_spec",
            "",
        ),
        key="video_product_spec_input",
    )

    target_platform = st.selectbox(
        "目標平台",
        [
            "蝦皮",
            "TikTok",
            "蝦皮＋TikTok",
        ],
        key="video_target_platform_input",
    )

    duration = st.selectbox(
        "影片秒數",
        [
            5,
            8,
            10,
            12,
            15,
        ],
        index=2,
        key="video_duration_input",
    )

    # -----------------------------------------------------
    # 商品圖片
    # -----------------------------------------------------

    uploaded = st.file_uploader(
        "📷 上傳商品圖片",
        type=[
            "jpg",
            "jpeg",
            "png",
            "webp",
        ],
        key="video_image_upload",
    )

    image_bytes = None

    if uploaded:

        try:

            image, image_bytes = prepare_image(
                uploaded
            )

            st.image(
                image,
                caption="影片參考商品圖片",
                use_container_width=True,
            )

        except Exception as error:

            st.error(str(error))

    elif st.session_state.get(
        "video_image_bytes"
    ):

        image_bytes = st.session_state.video_image_bytes

        try:

            image = Image.open(
                io.BytesIO(
                    image_bytes
                )
            )

            st.image(
                image,
                caption="已從商品分析帶入",
                use_container_width=True,
            )

        except Exception:
            pass

    st.divider()

    # -----------------------------------------------------
    # OpenClaw
    # -----------------------------------------------------

    st.subheader(
        "🦞 OpenClaw"
    )

    if get_openclaw_url():

        st.success(
            "已設定 OpenClaw Gateway"
        )

        st.caption(
            get_openclaw_url()
        )

    else:

        st.warning(
            "目前沒有設定 OpenClaw Gateway。"
        )

    st.divider()

    # -----------------------------------------------------
    # Prompt
    # -----------------------------------------------------

    video_prompt = build_video_prompt(
        product_name,
        product_spec,
        target_platform,
        duration,
    )

    with st.expander(
        "👁️ 查看即夢 AI 2.5 影片指令",
        expanded=False,
    ):

        st.code(
            video_prompt,
            language="text",
        )

    # -----------------------------------------------------
    # 真生成
    # -----------------------------------------------------

    if st.button(
        "
