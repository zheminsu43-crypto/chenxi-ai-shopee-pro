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
# OpenClaw 半自動化版
#
# Streamlit
#   ↓
# OpenClaw Gateway
#   ↓
# OpenClaw 自動管理 Provider
#   ↓
# Video Provider
#
# 本版本：
# 1. 沒有 OpenClaw 也能開網站
# 2. 有 OpenClaw Gateway 才啟用真影片
# 3. 商品圖片可直接從手機上傳
# 4. 自動產生商品分析
# 5. 自動產生蝦皮文案
# 6. 自動產生 TikTok 文案
# 7. 自動產生 OpenClaw 影片 Prompt
# 8. Image-to-Video
# 9. 影片任務查詢
# 10. 影片播放
# 11. 影片下載
# 12. MP4 / MOV / WEBM 上傳
# 13. 永久會員
# 14. 管理員
# 15. 不把 Provider API Key 寫死在程式碼
# =========================================================


# =========================================================
# Streamlit 設定
# =========================================================

st.set_page_config(
    page_title="AI 蝦皮半自動化 2.5 PRO｜OpenClaw",
    page_icon="🦞",
    layout="wide",
    initial_sidebar_state="collapsed",
)


APP_NAME = "AI 蝦皮半自動化 2.5 PRO"


# =========================================================
# 資料
# =========================================================

DATA_DIR = Path("data")
MEMBERS_FILE = DATA_DIR / "members.json"

DATA_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# =========================================================
# 限制
# =========================================================

MAX_IMAGE_SIZE = 1600
MAX_IMAGE_MB = 20
MAX_VIDEO_MB = 300


VIDEO_MIME_MAP = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
}


# =========================================================
# 管理員
# =========================================================

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


# =========================================================
# OpenClaw
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
# CSS
# =========================================================

st.markdown(
    """
<style>

.block-container {
    padding-top: 1rem;
    padding-bottom: 3rem;
    max-width: 1200px;
}

.main-title {
    text-align: center;
    font-size: 38px;
    font-weight: 900;
    margin-top: 10px;
    margin-bottom: 5px;
}

.main-subtitle {
    text-align: center;
    opacity: 0.72;
    font-size: 16px;
    margin-bottom: 25px;
}

.section-title {
    font-size: 25px;
    font-weight: 800;
    margin-top: 20px;
    margin-bottom: 12px;
}

.status-card {
    padding: 18px;
    border-radius: 15px;
    border: 1px solid rgba(128,128,128,.25);
    margin-bottom: 15px;
}

.small-note {
    opacity: .7;
    font-size: 13px;
}

@media (max-width: 768px) {

    .main-title {
        font-size: 27px;
    }

    .main-subtitle {
        font-size: 14px;
    }

    .section-title {
        font-size: 21px;
    }

}

</style>
""",
    unsafe_allow_html=True,
)


# =========================================================
# Session 初始值
# =========================================================

DEFAULT_SESSION_VALUES = {

    "logged_in": False,

    "page": "login",

    "username": "",

    "member": {},

    "analysis_result": "",

    "shopee_copy": "",

    "tiktok_copy": "",

    "video_prompt": "",

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
            str(
                member.get(
                    "username",
                    "",
                )
            ).lower()
            == ADMIN_USERNAME
        ):

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

    if find_member(username):

        return False, "帳號已存在。"

    if email and find_member_by_email(email):

        return False, "Email 已註冊。"

    member = {

        "id": secrets.token_hex(8),

        "username": username,

        "password_hash": hash_password(
            password
        ),

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
# 登出
# =========================================================

def logout():

    for key, value in DEFAULT_SESSION_VALUES.items():

        st.session_state[key] = value

    st.rerun()


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
            "圖片內容是空的。"
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
# 商品分類
# =========================================================

def detect_product_category(
    product_name,
    product_spec,
):

    text = (
        f"{product_name} "
        f"{product_spec}"
    ).lower()

    categories = {

        "保養品": [
            "保養",
            "精華",
            "乳液",
            "面膜",
            "洗面",
            "化妝水",
            "防曬",
        ],

        "3C": [
            "手機",
            "耳機",
            "充電",
            "鍵盤",
            "滑鼠",
            "電腦",
            "平板",
            "3c",
        ],

        "居家": [
            "家用",
            "收納",
            "清潔",
            "廚房",
            "杯",
            "鍋",
            "居家",
        ],

        "服飾": [
            "衣",
            "褲",
            "鞋",
            "包",
            "外套",
            "帽",
            "服飾",
        ],

        "食品": [
            "食品",
            "零食",
            "餅乾",
            "茶",
            "咖啡",
            "飲料",
        ],

        "汽機車": [
            "汽車",
            "機車",
            "車用",
            "汽機車",
        ],

    }

    for category, words in categories.items():

        for word in words:

            if word.lower() in text:

                return category

    return "其他"


# =========================================================
# 商品分析
# =========================================================

def analyze_product(
    product_name,
    product_price,
    product_cost,
    commission_rate,
    monthly_sales,
    product_rating,
    product_spec,
    target_platform,
):

    category = detect_product_category(
        product_name,
        product_spec,
    )

    name = (
        product_name.strip()
        or "待確認商品"
    )

    price = (
        product_price.strip()
        or "待確認"
    )

    cost = (
        product_cost.strip()
        or "待確認"
    )

    commission = (
        commission_rate.strip()
        or "待確認"
    )

    sales = (
        monthly_sales.strip()
        or "待確認"
    )

    rating = (
        product_rating.strip()
        or "待確認"
    )

    spec = (
        product_spec.strip()
        or "待確認"
    )

    return f"""
【AI 商品分析】

商品名稱：
{name}

商品分類：
{category}

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

商品規格：
{spec}

目標平台：
{target_platform}

【選品分析】

1. 商品定位：
以「{category}」類商品方向進行分析。

2. 商業素材：
建議使用商品原圖作為主要視覺素材，
避免自行改變品牌、包裝、Logo、顏色與產品結構。

3. 影片方向：
以商品本體展示、細節特寫、材質展示、
包裝展示與乾淨商業攝影為主。

4. 蝦皮方向：
標題應包含商品核心名稱與主要用途，
避免沒有依據的誇張宣稱。

5. TikTok方向：
前 2～3 秒先展示商品，
接著展示細節，
最後回到商品完整畫面。

6. 風險提醒：
價格、規格、庫存、優惠、認證、
功效與分潤資訊都必須人工確認。

【AI 保護規則】

不可自行發明：
- 品牌
- 規格
- 價格
- 折扣
- 贈品
- 認證
- 功效
- 材質
- 數據

未知資訊一律標記：
「待確認」。
"""


# =========================================================
# 蝦皮文案
# =========================================================

def generate_shopee_copy(
    product_name,
    product_price,
    product_spec,
    target_platform,
):

    name = (
        product_name.strip()
        or "商品名稱待確認"
    )

    price = (
        product_price.strip()
        or "待確認"
    )

    spec = (
        product_spec.strip()
        or "待確認"
    )

    return f"""
【蝦皮商品標題】

{name}｜實用商品｜日常使用｜品質選物


【商品賣點】

① 商品名稱：
{name}

② 商品資訊：
{spec}

③ 商品價格：
{price}

④ 適用平台：
{target_platform}


【商品介紹】

這款商品適合需要
「{name}」
的消費者。

商品資訊與規格請依實際商品確認。

建議購買前確認：

・商品規格
・尺寸
・顏色
・數量
・庫存
・配送方式


【購買提醒】

實際商品以收到的商品為準。

請確認商品規格與圖片資訊後再下單。


【蝦皮標籤】

#蝦皮購物
#{name}
#生活好物
#實用商品
#熱門商品
"""


# =========================================================
# TikTok 文案
# =========================================================

def generate_tiktok_copy(
    product_name,
    product_spec,
):

    name = (
        product_name.strip()
        or "商品"
    )

    spec = (
        product_spec.strip()
        or "商品規格待確認"
    )

    return f"""
【TikTok 短影音文案】

🎬 前 3 秒：

直接展示「{name}」完整商品。

🔥 中段：

快速展示商品外觀、
材質、包裝與主要細節。

📦 商品資訊：

{name}

{spec}

🎯 結尾：

回到商品完整畫面，
讓觀眾清楚看到商品本體。

⚠️ 注意：

不可自行加入未確認的價格、
折扣、贈品、功效或認證。


【TikTok Hashtags】

#{name}
#TikTok購物
#好物推薦
#商品分享
#購物
#短影音
"""


# =========================================================
# 分潤合規
# =========================================================

def commission_check(
    commission_rate,
    product_url,
):

    commission = (
        commission_rate.strip()
        or "待確認"
    )

    url = (
        product_url.strip()
        or "待確認"
    )

    return f"""
【分潤合規檢查】

分潤比例：
{commission}

商品連結：
{url}

請人工確認：

□ 商品確實存在分潤資格
□ 分潤比例正確
□ 商品連結正確
□ 推廣資格正確
□ 文案沒有誤導消費者
□ 沒有虛構折扣
□ 沒有虛構贈品
□ 沒有虛構認證
□ 沒有誇大效果

結果：

目前僅能做內容檢查，
實際分潤資格仍需以平台資料為準。
"""


# =========================================================
# OpenClaw 影片 Prompt
# =========================================================

PRODUCT_RULES = """
PRODUCT IDENTITY LOCK

Use the supplied product image as the primary
and exact visual reference.

Preserve:

original brand,
original package,
original shape,
original proportions,
original colors,
original materials,
original logo,
original label,
original printed text.

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

No fake claims.
No fake prices.
No fake discounts.
No fake certifications.

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


def build_video_prompt(
    product_name,
    product_spec,
    target_platform,
    duration,
    ratio,
):

    name = (
        product_name.strip()
        or "the uploaded product"
    )

    spec = (
        product_spec.strip()
        or "unknown"
    )

    if ratio == "9:16":
        format_text = (
            "Vertical 9:16 social commerce video."
        )

    elif ratio == "16:9":
        format_text = (
            "Horizontal 16:9 commercial video."
        )

    else:
        format_text = (
            "Square 1:1 commercial video."
        )

    return f"""
Create a premium commercial product advertisement.

PRODUCT:
{name}

SPECIFICATION:
{spec}

TARGET PLATFORM:
{target_platform}

DURATION:
{duration} seconds.

FORMAT:
{format_text}

Use the supplied product image as the
primary visual reference.

SCENE 1 — OPENING

Start with a clean hero shot of the exact
uploaded product.

Keep the product clearly visible.

SCENE 2 — PRODUCT DETAIL

Slowly move the camera closer.

Show realistic:

- packaging
- material
- product surface
- logo
- label
- shape
- proportions

SCENE 3 — CINEMATIC MOVEMENT

Use subtle camera movement.

Slow push-in.

Small cinematic orbit.

Controlled depth of field.

Stable framing.

No aggressive camera shake.

SCENE 4 — ENDING

Return to a clean hero shot.

Keep the exact product centered.

Hold the final frame.

PRODUCT CONSISTENCY:

Same product.
Same packaging.
Same color.
Same shape.
Same proportions.
Same logo.
Same label.
Same material.

NEGATIVE PROMPT:

people,
hands,
human presenter,
influencer,
model,
spokesperson,
second product,
duplicate product,
wrong product,
fake product,
product deformation,
package deformation,
melting,
floating package,
warped logo,
warped text,
changing label,
changing brand,
changing color,
changing shape,
wrong price,
fake discount,
fake gift,
fake certification,
watermark,
text drift,
flicker,
unstable object,
cartoon,
illustration,
low quality,
unrealistic product.

{PRODUCT_RULES}
"""


# =========================================================
# OpenClaw Gateway
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

    try:

        response = requests.post(

            url,

            headers=openclaw_headers(),

            json=payload,

            timeout=timeout,

        )

    except requests.exceptions.Timeout:

        raise RuntimeError(
            "OpenClaw Gateway 連線逾時。"
        )

    except requests.exceptions.ConnectionError:

        raise RuntimeError(
            "無法連接 OpenClaw Gateway。"
        )

    except Exception as error:

        raise RuntimeError(
            f"OpenClaw 連線錯誤：{error}"
        )

    if response.status_code >= 400:

        raise RuntimeError(
            "OpenClaw Gateway 呼叫失敗\n\n"
            f"HTTP：{response.status_code}\n\n"
            f"{response.text[:3000]}"
        )

    try:

        return response.json()

    except Exception:

        return {
            "raw": response.text
        }


# =========================================================
# OpenClaw 影片生成
# =========================================================

def openclaw_generate_video(
    image_bytes,
    prompt,
    duration,
    ratio,
    model="",
):

    if not openclaw_is_configured():

        raise RuntimeError(
            "OpenClaw 尚未設定。"
        )

    image_data_url = image_to_data_url(
        image_bytes
    )

    args = {

        "action": "generate",

        "prompt": prompt,

        "image": image_data_url,

        "imageRoles": [
            "first_frame"
        ],

        "duration": duration,

        "aspect_ratio": ratio,

        "ratio": ratio,

    }

    if model:

        args["model"] = model

    result = openclaw_invoke(

        "video_generate",

        args,

        timeout=60,

    )

    st.session_state.openclaw_last_response = (
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )

    return result


# =========================================================
# 遞迴找 Task ID
# =========================================================

def recursive_find_task_id(obj):

    keys = [

        "task_id",
        "taskId",
        "job_id",
        "jobId",

    ]

    if isinstance(obj, dict):

        for key in keys:

            value = obj.get(key)

            if value is not None:

                text = str(value).strip()

                if text:

                    return text

        for value in obj.values():

            result = recursive_find_task_id(
                value
            )

            if result:

                return result

    elif isinstance(obj, list):

        for item in obj:

            result = recursive_find_task_id(
                item
            )

            if result:

                return result

    return ""


# =========================================================
# 找 URL
# =========================================================

def recursive_find_video_url(obj):

    preferred_keys = [

        "video_url",
        "videoUrl",
        "download_url",
        "downloadUrl",
        "media_url",
        "mediaUrl",
        "url",

    ]

    if isinstance(obj, dict):

        for key in preferred_keys:

            value = obj.get(key)

            if (
                isinstance(value, str)
                and value.startswith("http")
            ):

                lower = value.lower()

                if (
                    "video" in lower
                    or ".mp4" in lower
                    or ".mov" in lower
                    or ".webm" in lower
                    or "download" in lower
                ):

                    return value

        for value in obj.values():

            result = recursive_find_video_url(
                value
            )

            if result:

                return result

    elif isinstance(obj, list):

        for item in obj:

            result = recursive_find_video_url(
                item
            )

            if result:

                return result

    return ""


# =========================================================
# 找狀態
# =========================================================

def recursive_find_status(obj):

    keys = [

        "status",
        "state",
        "task_status",
        "taskStatus",

    ]

    valid = {

        "queued",
        "submitted",
        "processing",
        "running",
        "pending",
        "succeeded",
        "success",
        "completed",
        "complete",
        "failed",
        "failure",
        "cancelled",
        "canceled",

    }

    if isinstance(obj, dict):

        for key in keys:

            value = obj.get(key)

            if isinstance(value, str):

                value = (
                    value.strip().lower()
                )

                if value in valid:

                    return value

        for value in obj.values():

            result = recursive_find_status(
                value
            )

            if result:

                return result

    elif isinstance(obj, list):

        for item in obj:

            result = recursive_find_status(
                item
            )

            if result:

                return result

    return ""


# =========================================================
# 處理 OpenClaw 結果
# =========================================================

def process_openclaw_result(result):

    video_url = recursive_find_video_url(
        result
    )

    task_id = recursive_find_task_id(
        result
    )

    status = recursive_find_status(
        result
    )

    return {

        "video_url": video_url,

        "task_id": task_id,

        "status": (
            status
            or (
                "completed"
                if video_url
                else "submitted"
            )
        ),

        "raw": result,

    }


# =========================================================
# 下載影片
# =========================================================

def download_video(video_url):

    try:

        response = requests.get(
            video_url,
            timeout=180,
        )

    except Exception as error:

        raise RuntimeError(
            f"影片下載錯誤：{error}"
        )

    if response.status_code >= 400:

        raise RuntimeError(
            f"影片下載失敗：HTTP {response.status_code}"
        )

    if not response.content:

        raise RuntimeError(
            "影片內容為空。"
        )

    size_mb = (
        len(response.content)
        / 1024
        / 1024
    )

    if size_mb > MAX_VIDEO_MB:

        raise RuntimeError(
            f"影片 {size_mb:.1f} MB，"
            f"超過系統限制。"
        )

    return response.content


# =========================================================
# 儲存完成影片
# =========================================================

def save_generated_video(
    video_url,
):

    raw = download_video(
        video_url
    )

    signature = hashlib.sha256(
        raw
    ).hexdigest()

    if (
        st.session_state.video_signature
        == signature
    ):

        return False

    st.session_state.video_url = (
        video_url
    )

    st.session_state.video_bytes = (
        raw
    )

    st.session_state.video_signature = (
        signature
    )

    st.session_state.video_name = (
        "OpenClaw_AI_"
        + datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
        + ".mp4"
    )

    st.session_state.video_mime = (
        "video/mp4"
    )

    st.session_state.video_status = (
        "completed"
    )

    return True


# =========================================================
# 查詢影片
# =========================================================

def check_video_status():

    if not openclaw_is_configured():

        raise RuntimeError(
            "OpenClaw 尚未設定。"
        )

    args = {

        "action": "status",

    }

    if st.session_state.video_task_id:

        args["task_id"] = (
            st.session_state.video_task_id
        )

    result = openclaw_invoke(

        "video_generate",

        args,

        timeout=60,

    )

    st.session_state.openclaw_last_response = (
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )

    processed = process_openclaw_result(
        result
    )

    if processed["task_id"]:

        st.session_state.video_task_id = (
            processed["task_id"]
        )

    if processed["video_url"]:

        try:

            save_generated_video(
                processed["video_url"]
            )

            return result

        except Exception as error:

            st.warning(
                "已找到影片，但下載失敗："
                + str(error)
            )

            st.session_state.video_url = (
                processed["video_url"]
            )

    st.session_state.video_status = (
        processed["status"]
    )

    return result


# =========================================================
# 清除影片
# =========================================================

def clear_generated_video():

    st.session_state.video_task_id = ""

    st.session_state.video_status = ""

    st.session_state.video_url = ""

    st.session_state.video_bytes = None

    st.session_state.video_name = ""

    st.session_state.video_mime = "video/mp4"

    st.session_state.video_signature = ""


# =========================================================
# 手動影片
# =========================================================

def detect_video_mime(
    filename,
    browser_mime="",
):

    ext = os.path.splitext(
        str(filename or "")
    )[1].lower()

    if ext in VIDEO_MIME_MAP:

        return VIDEO_MIME_MAP[ext], ext

    for suffix, mime in VIDEO_MIME_MAP.items():

        if mime == browser_mime:

            return mime, suffix

    return "video/mp4", ".mp4"


def save_uploaded_video(video_file):

    raw = video_file.getvalue()

    if not raw:

        raise ValueError(
            "影片檔案內容是空的。"
        )

    size_mb = (
        len(raw)
        / 1024
        / 1024
    )

    if size_mb > MAX_VIDEO_MB:

        raise ValueError(
            f"影片 {size_mb:.1f} MB，"
            f"超過 {MAX_VIDEO_MB} MB。"
        )

    mime, ext = detect_video_mime(
        video_file.name,
        video_file.type or "",
    )

    signature = hashlib.sha256(
        raw
    ).hexdigest()

    if (
        st.session_state.uploaded_video_signature
        != signature
    ):

        st.session_state.uploaded_video_bytes = (
            raw
        )

        st.session_state.uploaded_video_name = (
            video_file.name
        )

        st.session_state.uploaded_video_mime = (
            mime
        )

        st.session_state.uploaded_video_signature = (
            signature
        )

    return raw, mime, ext, size_mb


def clear_uploaded_video():

    st.session_state.uploaded_video_bytes = None

    st.session_state.uploaded_video_name = ""

    st.session_state.uploaded_video_mime = (
        "video/mp4"
    )

    st.session_state.uploaded_video_signature = ""


# =========================================================
# 登入頁
# =========================================================

def login_page():

    st.markdown(
        '<div class="main-title">'
        '🦞 AI 蝦皮半自動化 2.5 PRO'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="main-subtitle">'
        'OpenClaw 半自動化｜商品分析｜影片生成'
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
            key="login_username",
        )

        password = st.text_input(
            "會員密碼",
            type="password",
            key="login_password",
        )

        if st.button(
            "🚀 登入系統",
            type="primary",
            use_container_width=True,
        ):

            if not username or not password:

                st.error(
                    "請輸入帳號與密碼。"
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

                    if result == "disabled":

                        st.error(
                            "⛔ 帳號已停權。"
                        )

                    else:

                        st.error(
                            "❌ 帳號或密碼錯誤。"
                        )

        st.divider()

        if st.button(
            "📝 註冊永久會員",
            use_container_width=True,
        ):

            st.session_state.page = "register"

            st.rerun()

        with st.expander(
            "🔐 管理員測試帳號"
        ):

            st.code(
                "帳號：admin\n"
                "密碼：admin123"
            )


# =========================================================
# 註冊頁
# =========================================================

def register_page():

    st.markdown(
        '<div class="main-title">'
        '📝 永久會員註冊'
        '</div>',
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns(
        [1, 2, 1]
    )

    with center:

        st.success(
            "♾️ 會員期限：永久"
        )

        name = st.text_input(
            "姓名 / 暱稱"
        )

        email = st.text_input(
            "Email"
        )

        username = st.text_input(
            "會員帳號",
            placeholder="3～30 位小寫英數字或底線",
        )

        password = st.text_input(
            "會員密碼",
            type="password",
        )

        password_confirm = st.text_input(
            "再次輸入密碼",
            type="password",
        )

        if st.button(
            "🚀 建立永久會員",
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
                    "請輸入姓名。"
                )

            elif not re.fullmatch(
                r"[^@\s]+@[^@\s]+\.[^@\s]+",
                email_clean,
            ):

                st.error(
                    "Email 格式錯誤。"
                )

            elif not re.fullmatch(
                r"[a-z0-9_]{3,30}",
                username_clean,
            ):

                st.error(
                    "帳號只能使用小寫英數字與底線。"
                )

            elif len(password) < 6:

                st.error(
                    "密碼至少 6 個字元。"
                )

            elif password != password_confirm:

                st.error(
                    "兩次密碼不一致。"
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
                        "🎉 永久會員建立成功！"
                    )

                    st.info(
                        "請返回登入。"
                    )

                else:

                    st.error(
                        str(result)
                    )

        if st.button(
            "⬅️ 返回登入",
            use_container_width=True,
        ):

            st.session_state.page = "login"

            st.rerun()


# =========================================================
# 登入控制
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
# 目前會員
# =========================================================

current_username = (
    st.session_state.username
)

current_member = find_member(
    current_username
)

if not current_member:

    logout()

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

if member_status != "active":

    st.error(
        "⛔ 帳號已停權。"
    )

    if st.button("🚪 登出"):

        logout()

    st.stop()


# =========================================================
# Sidebar
# =========================================================

with st.sidebar:

    st.markdown(
        "## 🦞 OpenClaw 半自動化"
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

    st.success(
        "♾️ 永久會員"
    )

    st.divider()

    if openclaw_is_configured():

        st.success(
            "🟢 OpenClaw 已設定"
        )

    else:

        st.warning(
            "🟡 OpenClaw 尚未設定"
        )

    st.divider()

    if st.button(
        "🚪 登出",
        use_container_width=True,
    ):

        logout()


# =========================================================
# 主標題
# =========================================================

st.markdown(
    '<div class="main-title">'
    '🦞 AI 蝦皮半自動化 2.5 PRO'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-subtitle">'
    'OpenClaw 半自動化｜商品分析｜蝦皮｜TikTok｜'
    'Image-to-Video｜永久會員'
    '</div>',
    unsafe_allow_html=True,
)


# =========================================================
# 1 OpenClaw 狀態
# =========================================================

st.markdown(
    '<div class="section-title">'
    '🦞 1｜OpenClaw 狀態'
    '</div>',
    unsafe_allow_html=True,
)

if openclaw_is_configured():

    st.success(
        "🟢 OpenClaw Gateway 已設定"
    )

    if st.button(
        "🔄 測試 OpenClaw",
        use_container_width=True,
    ):

        try:

            with st.spinner(
                "正在測試 OpenClaw..."
            ):

                result = openclaw_invoke(
                    "video_generate",
                    {
                        "action": "list"
                    },
                    timeout=30,
                )

            st.success(
                "🎉 OpenClaw Gateway 連線成功"
            )

            st.session_state.openclaw_last_response = (
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )

        except Exception as error:

            st.error(
                "❌ OpenClaw 連線失敗"
            )

            st.code(
                str(error)
            )

else:

    st.info(
        "🟡 OpenClaw 尚未設定。\n\n"
        "網站仍然可以使用商品分析、文案與 Prompt 功能。\n\n"
        "設定 Gateway 後才能送出真影片任務。"
    )


# =========================================================
# OpenClaw 設定
# =========================================================

with st.expander(
    "⚙️ OpenClaw 設定"
):

    st.write(
        "不要把 Provider API Key 直接寫進 app.py。"
    )

    st.write(
        "Provider 金鑰應放在 OpenClaw / Secrets 環境。"
    )

    st.code(
        "OPENCLAW_GATEWAY_URL\n"
        "OPENCLAW_GATEWAY_TOKEN"
    )

    if openclaw_is_configured():

        st.success(
            "🟢 Gateway URL + Token 已讀取"
        )

    else:

        st.warning(
            "🟡 尚未設定 Gateway"
        )


# =========================================================
# 2 商品圖片
# =========================================================

st.markdown(
    '<div class="section-title">'
    '📷 2｜商品圖片'
    '</div>',
    unsafe_allow_html=True,
)

uploaded_file = st.file_uploader(

    "從手機選擇商品圖片",

    type=[
        "jpg",
        "jpeg",
        "png",
        "webp",
    ],

    accept_multiple_files=False,

    key="product_image_uploader",

)


prepared_image = None
prepared_image_bytes = None


if uploaded_file:

    try:

        (
            prepared_image,
            prepared_image_bytes,
        ) = prepare_image(
            uploaded_file
        )

        st.success(
            "✅ 商品圖片讀取成功"
        )

        st.image(
            prepared_image,
            caption="OpenClaw Image-to-Video 參考圖",
            use_container_width=True,
        )

    except Exception as error:

        st.error(
            "❌ 圖片處理失敗"
        )

        st.code(
            str(error)
        )


# =========================================================
# 3 商品資料
# =========================================================

st.markdown(
    '<div class="section-title">'
    '📦 3｜商品資料'
    '</div>',
    unsafe_allow_html=True,
)

col1, col2 = st.columns(2)

with col1:

    product_name = st.text_input(
        "商品名稱",
        placeholder="例如：無線藍牙耳機",
    )

    product_price = st.text_input(
        "商品價格",
        placeholder="例如：399",
    )

    product_cost = st.text_input(
        "商品成本",
        placeholder="例如：250",
    )

    commission_rate = st.text_input(
        "分潤比例",
        placeholder="例如：12%",
    )

with col2:

    monthly_sales = st.text_input(
        "月銷量",
        placeholder="例如：1500",
    )

    product_rating = st.text_input(
        "商品評分",
        placeholder="例如：4.8",
    )

    product_url = st.text_input(
        "商品連結",
        placeholder="可留空",
    )

    product_spec = st.text_area(
        "商品規格",
        placeholder="例如：顏色、尺寸、容量、材質",
        height=120,
    )


# =========================================================
# 4 平台
# =========================================================

st.markdown(
    '<div class="section-title">'
    '🎯 4｜目標平台'
    '</div>',
    unsafe_allow_html=True,
)

target_platform = st.radio(

    "選擇平台",

    [
        "蝦皮",
        "TikTok",
        "蝦皮＋TikTok",
    ],

    horizontal=True,

)


# =========================================================
# 5 AI 功能
# =========================================================

st.markdown(
    '<div class="section-title">'
    '🤖 5｜AI 半自動化功能'
    '</div>',
    unsafe_allow_html=True,
)

generate_options = [

    "商品辨識",

    "AI 選品分析",

    "蝦皮上架文案",

    "TikTok 文案",

    "OpenClaw 影片 Prompt",

    "OpenClaw 真生成影片",

    "分潤合規檢查",

]


selected_items = st.multiselect(

    "選擇這次要執行的功能",

    generate_options,

    default=generate_options,

)


# =========================================================
# 6 影片設定
# =========================================================

st.markdown(
    '<div class="section-title">'
    '🎬 6｜影片設定'
    '</div>',
    unsafe_allow_html=True,
)

v1, v2, v3 = st.columns(3)

with v1:

    video_duration = st.selectbox(
        "影片秒數",
        [5, 6, 8, 10, 12],
        index=3,
    )

with v2:

    video_ratio = st.selectbox(
        "影片比例",
        [
            "9:16",
            "16:9",
            "1:1",
        ],
        index=0,
    )

with v3:

    video_model = st.text_input(
        "Provider / Model",
        placeholder="留空＝OpenClaw 自動選",
    )


st.caption(
    "💡 留空時，由 OpenClaw 依你的 Provider / fallback 設定處理。"
)


# =========================================================
# 7 一鍵 AI 半自動化
# =========================================================

st.markdown(
    '<div class="section-title">'
    '🚀 7｜一鍵 AI 半自動化'
    '</div>',
    unsafe_allow_html=True,
)

if st.button(
    "🚀 開始 AI 半自動化分析",
    type="primary",
    use_container_width=True,
):

    if not prepared_image_bytes:

        st.error(
            "❌ 請先上傳商品圖片。"
        )

    else:

        with st.spinner(
            "🤖 AI 正在建立商品內容..."
        ):

            # 商品分析
            if (
                "商品辨識" in selected_items
                or "AI 選品分析" in selected_items
                or "完整流程" in selected_items
            ):

                st.session_state.analysis_result = (
                    analyze_product(
                        product_name,
                        product_price,
                        product_cost,
                        commission_rate,
                        monthly_sales,
                        product_rating,
                        product_spec,
                        target_platform,
                    )
                )

            # 蝦皮
            if (
                "蝦皮上架文案"
                in selected_items
            ):

                st.session_state.shopee_copy = (
                    generate_shopee_copy(
                        product_name,
                        product_price,
                        product_spec,
                        target_platform,
                    )
                )

            # TikTok
            if (
                "TikTok 文案"
                in selected_items
            ):

                st.session_state.tiktok_copy = (
                    generate_tiktok_copy(
                        product_name,
                        product_spec,
                    )
                )

            # 分潤
            commission_result = ""

            if (
                "分潤合規檢查"
                in selected_items
            ):

                commission_result = (
                    commission_check(
                        commission_rate,
                        product_url,
                    )
                )

            # Prompt
            if (
                "OpenClaw 影片 Prompt"
                in selected_items
                or "OpenClaw 真生成影片"
                in selected_items
            ):

                st.session_state.video_prompt = (
                    build_video_prompt(
                        product_name,
                        product_spec,
                        target_platform,
                        video_duration,
                        video_ratio,
                    )
                )

            st.success(
                "🎉 AI 半自動化內容建立完成！"
            )

        # =================================================
        # 顯示結果
        # =================================================

        if st.session_state.analysis_result:

            with st.expander(
                "🔎 商品分析結果",
                expanded=True,
            ):

                st.text_area(
                    "商品分析",
                    value=st.session_state.analysis_result,
                    height=400,
                )

        if st.session_state.shopee_copy:

            with st.expander(
                "🛒 蝦皮文案",
                expanded=True,
            ):

                st.text_area(
                    "蝦皮文案",
                    value=st.session_state.shopee_copy,
                    height=400,
                )

        if st.session_state.tiktok_copy:

            with st.expander(
                "🎵 TikTok 文案",
                expanded=True,
            ):

                st.text_area(
                    "TikTok 文案",
                    value=st.session_state.tiktok_copy,
                    height=400,
                )

        if commission_result:

            with st.expander(
                "💰 分潤合規檢查",
                expanded=True,
            ):

                st.text_area(
                    "分潤檢查",
                    value=commission_result,
                    height=300,
                )

        if st.session_state.video_prompt:

            with st.expander(
                "🎬 OpenClaw 影片 Prompt",
                expanded=True,
            ):

                st.text_area(
                    "影片 Prompt",
                    value=st.session_state.video_prompt,
                    height=500,
                )


# =========================================================
# 8 影片 Prompt
# =========================================================

if not st.session_state.video_prompt:

    st.session_state.video_prompt = (
        build_video_prompt(
            product_name,
            product_spec,
            target_platform,
            video_duration,
            video_ratio,
        )
    )


with st.expander(
    "🎬 查看 / 複製 OpenClaw 影片 Prompt"
):

    st.text_area(
        "OpenClaw Video Prompt",
        value=st.session_state.video_prompt,
        height=500,
    )


# =========================================================
# 9 OpenClaw 真影片
# =========================================================

st.markdown(
    '<div class="section-title">'
    '🦞 9｜OpenClaw 真影片'
    '</div>',
    unsafe_allow_html=True,
)

if not openclaw_is_configured():

    st.warning(
        "🟡 目前尚未設定 OpenClaw Gateway。"
    )

    st.caption(
        "這不影響商品分析、文案與 Prompt。"
        "只有真影片生成需要 Gateway。"
    )

else:

    if st.button(
        "🦞🚀 送出 OpenClaw 真影片任務",
        type="primary",
        use_container_width=True,
        key="generate_real_video",
    ):

        if not prepared_image_bytes:

            st.error(
                "❌ 請先上傳商品圖片。"
            )

        else:

            # 防止重複任務
            if (
                st.session_state.video_status
                in [
                    "submitted",
                    "queued",
                    "processing",
                    "running",
                    "pending",
                ]
            ):

                st.warning(
                    "⚠️ 已經有一個影片任務正在處理。"
                )

            else:

                try:

                    with st.spinner(
                        "🦞 OpenClaw 正在提交影片任務..."
                    ):

                        result = openclaw_generate_video(

                            image_bytes=prepared_image_bytes,

                            prompt=st.session_state.video_prompt,

                            duration=video_duration,

                            ratio=video_ratio,

                            model=video_model.strip(),

                        )

                    processed = (
                        process_openclaw_result(
                            result
                        )
                    )

                    task_id = processed[
                        "task_id"
                    ]

                    status = processed[
                        "status"
                    ]

                    video_url = processed[
                        "video_url"
                    ]

                    st.session_state.video_status = (
                        status
                    )

                    if task_id:

                        st.session_state.video_task_id = (
                            task_id
                        )

                    if video_url:

                        try:

                            save_generated_video(
                                video_url
                            )

                            st.success(
                                "🎉 影片已完成並載入！"
                            )

                            st.rerun()

                        except Exception as error:

                            st.warning(
                                "影片已產生，但下載到 Streamlit 失敗。"
                            )

                            st.code(
                                str(error)
                            )

                    else:

                        st.success(
                            "✅ OpenClaw 影片任務已送出！"
                        )

                        if task_id:

                            st.info(
                                f"Task ID：{task_id}"
                            )

                        st.info(
                            "影片生成通常是非同步的。"
                            "請到下方按「查詢影片狀態」。"
                        )

                except Exception as error:

                    st.error(
                        "❌ OpenClaw 影片任務失敗"
                    )

                    st.code(
                        str(error)
                    )


# =========================================================
# 10 任務狀態
# =========================================================

if (
    st.session_state.video_task_id
    or st.session_state.video_status
):

    st.divider()

    st.markdown(
        '<div class="section-title">'
        '🔄 10｜影片任務狀態'
        '</div>',
        unsafe_allow_html=True,
    )

    status_text = (
        st.session_state.video_status
        or "processing"
    )

    if st.session_state.video_task_id:

        st.write(
            f"Task ID：`{st.session_state.video_task_id}`"
        )

    st.write(
        f"目前狀態：`{status_text}`"
    )

    if st.button(
        "🔄 查詢影片狀態",
        use_container_width=True,
    ):

        if not openclaw_is_configured():

            st.error(
                "OpenClaw 尚未設定。"
            )

        else:

            try:

                with st.spinner(
                    "🦞 OpenClaw 正在查詢..."
                ):

                    result = check_video_status()

                if st.session_state.video_bytes:

                    st.success(
                        "🎉 影片完成！"
                    )

                else:

                    st.info(
                        "目前狀態："
                        + (
                            st.session_state.video_status
                            or "processing"
                        )
                    )

            except Exception as error:

                st.error(
                    "❌ 查詢失敗"
                )

                st.code(
                    str(error)
                )


# =========================================================
# 11 影片播放器
# =========================================================

st.divider()

st.markdown(
    '<div class="section-title">'
    '🎞️ 11｜AI 真生成影片'
    '</div>',
    unsafe_allow_html=True,
)

if st.session_state.video_bytes:

    st.success(
        "🟢 AI 真影片已完成"
    )

    st.video(
        st.session_state.video_bytes,
        format=st.session_state.video_mime,
        start_time=0,
    )

    st.caption(
        "📱 手機建議：MP4 / H.264 / AAC / 9:16"
    )

    st.download_button(
        "⬇️ 下載 AI 真生成影片",
        data=st.session_state.video_bytes,
        file_name=(
            st.session_state.video_name
            or "AI影片.mp4"
        ),
        mime=st.session_state.video_mime,
        use_container_width=True,
        key="download_ai_video",
    )

    if st.button(
        "🗑️ 清除目前 AI 影片",
        use_container_width=True,
    ):

        clear_generated_video()

        st.rerun()

else:

    st.info(
        "目前沒有完成的 AI 影片。"
    )


# =========================================================
# OpenClaw 回應
# =========================================================

if st.session_state.openclaw_last_response:

    with st.expander(
        "🔍 OpenClaw 最後回應（除錯用）"
    ):

        st.code(
            st.session_state.openclaw_last_response,
            language="json",
        )


# =========================================================
# 12 手動影片上傳
# =========================================================

st.divider()

st.markdown(
    '<div class="section-title">'
    '📤 12｜影片上傳 / 預覽'
    '</div>',
    unsafe_allow_html=True,
)

st.caption(
    "支援 MP4 / MOV / WEBM"
)

uploaded_video = st.file_uploader(

    "從手機選擇影片",

    type=[
        "mp4",
        "mov",
        "webm",
    ],

    accept_multiple_files=False,

    key="manual_video_uploader",

)


if uploaded_video:

    try:

        (
            raw,
            mime,
            ext,
            size_mb,
        ) = save_uploaded_video(
            uploaded_video
        )

        st.success(
            "✅ 影片上傳成功"
        )

        st.write(
            f"格式：**{mime}**"
        )

        st.write(
            f"大小：**{size_mb:.2f} MB**"
        )

        st.video(
            raw,
            format=mime,
            start_time=0,
        )

        safe_name = re.sub(
            r'[\\/:*?"<>|]+',
            "_",
            uploaded_video.name,
        )

        st.download_button(
            "⬇️ 下載目前影片",
            data=raw,
            file_name=safe_name,
            mime=mime,
            use_container_width=True,
            key="download_manual_video",
        )

        if ext == ".mp4":

            st.success(
                "🟢 MP4：手機最推薦。"
            )

        elif ext == ".mov":

            st.warning(
                "🟡 MOV：部分手機瀏覽器可能需要轉 MP4。"
            )

        elif ext == ".webm":

            st.warning(
                "🟡 WEBM：部分手機瀏覽器可能需要轉 MP4。"
            )

    except Exception as error:

        st.error(
            "❌ 影片處理失敗"
        )

        st.code(
            str(error)
        )


# =========================================================
# Session 影片
# =========================================================

if st.session_state.uploaded_video_bytes:

    st.divider()

    st.subheader(
        "🎞️ 目前上傳影片"
    )

    st.caption(
        st.session_state.uploaded_video_name
    )

    st.video(
        st.session_state.uploaded_video_bytes,
        format=st.session_state.uploaded_video_mime,
        start_time=0,
    )

    if st.button(
        "🗑️ 清除目前上傳影片",
        use_container_width=True,
    ):

        clear_uploaded_video()

        st.rerun()


# =========================================================
# 13 發布前檢查
# =========================================================

st.divider()

st.markdown(
    '<div class="section-title">'
    '✅ 13｜發布前檢查'
    '</div>',
    unsafe_allow_html=True,
)

check_items = [

    "商品圖片清楚",

    "商品名稱已確認",

    "商品價格已確認",

    "商品規格已確認",

    "商品庫存已確認",

    "商品連結已確認",

    "影片商品與原商品一致",

    "影片沒有第二個商品",

    "影片沒有商品變形",

    "影片沒有錯誤文字",

    "影片沒有假價格",

    "影片沒有假贈品",

    "影片沒有假認證",

    "文案沒有誇大效果",

    "分潤資格已確認",

]


checked = 0

for item in check_items:

    key = (
        "publish_check_"
        + hashlib.md5(
            item.encode("utf-8")
        ).hexdigest()
    )

    if st.checkbox(
        item,
        key=key,
    ):

        checked += 1


progress = (
    checked / len(check_items)
)

st.progress(progress)

st.write(
    f"完成：**{checked}/{len(check_items)}**"
)

if checked == len(check_items):

    st.success(
        "🎉 發布前檢查全部完成。"
    )

else:

    st.warning(
        "⚠️ 還有項目需要人工確認。"
    )


# =========================================================
# 14 管理員
# =========================================================

if member_role.lower() == "admin":

    st.divider()

    with st.expander(
        "👑 14｜管理員中心"
    ):

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

            role = member.get(
                "role",
                "member",
            )

            status = member.get(
                "status",
                "active",
            )

            with st.expander(
                f"👤 {name}｜{username}"
            ):

                st.write(
                    "會員期限：**永久**"
                )

                st.write(
                    f"身份：**{role}**"
                )

                new_status = st.selectbox(

                    "帳號狀態",

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

                if st.button(

                    "💾 儲存會員設定",

                    key=f"save_{mid}",

                    use_container_width=True,

                ):

                    update_member(

                        mid,

                        {
                            "status": new_status,
                            "role": new_role,
                            "permanent": True,
                        },

                    )

                    st.success(
                        "會員資料已更新。"
                    )

                    st.rerun()


# =========================================================
# 15 系統說明
# =========================================================

with st.expander(
    "⚙️ 15｜目前系統架構"
):

    st.markdown(
        """
### 🦞 OpenClaw 半自動化流程

📱 手機

↓

🌐 Streamlit

↓

📷 商品圖片

↓

📦 商品資料

↓

🤖 商品分析

↓

✍️ 蝦皮文案

↓

🎵 TikTok 文案

↓

🎬 OpenClaw Prompt

↓

🦞 OpenClaw Gateway

↓

🔄 Provider / Fallback

↓

🎞️ 真影片生成

↓

📱 Streamlit 播放

↓

⬇️ 手機下載


### 注意

OpenClaw 本身不是「免費無限影片生成額度」。

真正產生影片仍然需要 OpenClaw 後面的
影片 Provider 有可用的服務與額度。

本網站的設計是：

「OpenClaw 負責管理與調度」

而不是：

「OpenClaw 自己憑空提供無限影片額度」。
"""
    )


# =========================================================
# Footer
# =========================================================

st.divider()

st.caption(
    "AI 蝦皮半自動化 2.5 PRO｜"
    "OpenClaw 半自動化｜"
    "Image-to-Video｜"
    "永久會員｜"
    "MP4 / MOV / WEBM"
)
