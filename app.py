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
# OpenClaw 龍蝦｜半自動化完整版
#
# 功能：
# - 永久會員
# - 管理員
# - 手機版 UI
# - 商品圖片上傳
# - 商品圖片自動處理
# - 商品資料
# - 蝦皮 / TikTok
# - 商品原貌鎖定 Prompt
# - OpenClaw Gateway
# - Image-to-Video
# - 非同步影片任務
# - Task ID
# - 查詢影片狀態
# - MP4 / MOV / WEBM 上傳
# - 影片播放
# - 影片下載
# - 發布前檢查
#
# 注意：
# OpenClaw 只是控制層。
# 真正影片生成仍需要 OpenClaw 後端存在可用 Provider。
# =========================================================


# =========================================================
# 頁面
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


ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


# =========================================================
# CSS
# =========================================================

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 4.5rem !important;
        padding-bottom: 3rem !important;
        padding-left: 1.2rem !important;
        padding-right: 1.2rem !important;
    }

    .main-title {
        text-align: center;
        font-size: 38px;
        font-weight: 900;
        line-height: 1.3;
        margin-top: 10px !important;
        margin-bottom: 10px !important;
        word-break: break-word;
    }

    .main-subtitle {
        text-align: center;
        font-size: 16px;
        opacity: .75;
        line-height: 1.5;
        margin-bottom: 25px;
    }

    .video-title {
        font-size: 28px;
        font-weight: 900;
        margin-top: 10px;
        margin-bottom: 15px;
    }

    div.stButton > button {
        min-height: 46px;
        border-radius: 10px;
        font-weight: 700;
    }

    [data-testid="stFileUploader"] {
        border-radius: 14px;
    }

    @media (max-width: 768px) {

        .block-container {
            padding-top: 3.8rem !important;
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

        .video-title {
            font-size: 23px;
        }
    }

    @media (max-width: 480px) {

        .block-container {
            padding-top: 3.5rem !important;
        }

        .main-title {
            font-size: 24px;
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

        return data if isinstance(data, list) else []

    except Exception:
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
# Session
# =========================================================

SESSION_DEFAULTS = {

    "logged_in": False,

    "page": "login",

    "username": "",

    "member": {},

    "prepared_image_bytes": None,

    "prepared_image_signature": "",

    "prepared_image_name": "",

    "kling_prompt": "",

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

    "uploaded_video_signature": "",

}


for key, default in SESSION_DEFAULTS.items():

    if key not in st.session_state:
        st.session_state[key] = default


# =========================================================
# 登出
# =========================================================

def logout():

    for key, default in SESSION_DEFAULTS.items():
        st.session_state[key] = default

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
            f"{response.text[:3000]}"
        )

    try:
        return response.json()

    except Exception:

        return {
            "raw": response.text
        }


# =========================================================
# OpenClaw 測試
# =========================================================

def check_openclaw():

    if not openclaw_is_configured():

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

    elif image.mode != "RGB":

        image = image.convert("RGB")

    image.thumbnail(
        (
            MAX_IMAGE_SIZE,
            MAX_IMAGE_SIZE,
        ),
        Image.Resampling.LANCZOS,
    )

    buffer = io.BytesIO()

    image.save(
        buffer,
        format="JPEG",
        quality=92,
        optimize=True,
    )

    return image, buffer.getvalue()


# =========================================================
# 圖片 Data URL
# =========================================================

def image_to_data_url(
    image_bytes,
):

    encoded = base64.b64encode(
        image_bytes
    ).decode("utf-8")

    return (
        "data:image/jpeg;base64,"
        + encoded
    )


# =========================================================
# Prompt
# =========================================================

PRODUCT_RULES = """

PRODUCT IDENTITY LOCK

Use the supplied product image as the primary
and exact visual reference.

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

Do not invent:
- price
- discount
- gift
- certification
- medical claim
- performance claim

DEFAULT SCENE:

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
Create a premium commercial product advertisement.

PRODUCT:
{product_name}

SPECIFICATION:
{product_spec}

TARGET PLATFORM:
{target_platform}

DURATION:
{duration} seconds

ASPECT RATIO:
{ratio}

VISUAL REFERENCE:

Use the supplied product image as the primary
visual reference.

The uploaded product must remain the same
throughout the entire video.

OPENING:

Start with a clean hero shot of the exact
uploaded product.

Keep the product clearly visible and centered.

MIDDLE:

Use a slow cinematic push-in.

Reveal realistic material details,
packaging details, logo and label.

Use subtle camera movement.

Do not transform or redesign the product.

ENDING:

Return to a clean stable hero shot.

Keep the exact product centered.

Hold the final shot briefly.

LIGHTING:

Premium studio lighting.
Soft realistic highlights.
Natural shadows.
Clean commercial environment.
High-end advertising photography.

CAMERA:

Smooth slow push-in.
Subtle cinematic orbit.
Stable framing.
Controlled depth of field.
No aggressive shake.

PRODUCT CONSISTENCY:

Same product.
Same package.
Same color.
Same shape.
Same proportions.
Same logo.
Same label.
Same material.

NEGATIVE:

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
# 商品分析
# =========================================================

def build_product_analysis(
    product_name,
    price,
    cost,
    commission,
    sales,
    rating,
    spec,
):

    name = product_name.strip() or "待確認商品"

    return f"""
【AI 商品分析】

商品：
{name}

價格：
{price.strip() or "待確認"}

成本：
{cost.strip() or "待確認"}

分潤：
{commission.strip() or "待確認"}

月銷量：
{sales.strip() or "待確認"}

評分：
{rating.strip() or "待確認"}

規格：
{spec.strip() or "待確認"}

【分析原則】

1. 不自行虛構商品資料。
2. 不自行虛構銷量。
3. 不自行虛構評價。
4. 不自行虛構品牌。
5. 不自行虛構優惠。
6. 未知資料標記「待確認」。
7. 商業內容應以實際商品資訊為準。
"""


def build_shopee_copy(
    product_name,
    price,
    spec,
    platform,
):

    name = product_name.strip() or "商品名稱待確認"

    return f"""
【蝦皮商品文案】

商品名稱：
{name}

平台：
{platform}

價格：
{price.strip() or "待確認"}

商品規格：
{spec.strip() or "待確認"}

【商品賣點】

・以實際商品特色為準
・不虛構商品功能
・不虛構優惠
・不虛構認證
・不誇大效果

【購買提醒】

下單前請確認商品規格、尺寸、顏色及庫存。

【標籤】

#{name.replace(" ", "")}
#蝦皮購物
#好物推薦
"""


def build_tiktok_copy(
    product_name,
    platform,
):

    name = product_name.strip() or "商品名稱待確認"

    return f"""
【TikTok 帶貨文案】

商品：
{name}

開頭：
這款商品如果你正在找實用型好物，可以先看看。

內容：
用實際商品特色呈現商品，
避免誇大、虛構或未確認資訊。

結尾：
喜歡的話可以查看商品資訊。

平台：
{platform}

#TikTok購物
#好物推薦
"""


# =========================================================
# OpenClaw 生成影片
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
            "OpenClaw 尚未設定。\n\n"
            "請先設定 OPENCLAW_GATEWAY_URL。"
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

    }

    if model.strip():
        args["model"] = model.strip()

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
# 遞迴找 ID
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

            if value:

                return str(value)

        for value in obj.values():

            found = recursive_find_task_id(
                value
            )

            if found:
                return found

    elif isinstance(obj, list):

        for item in obj:

            found = recursive_find_task_id(
                item
            )

            if found:
                return found

    return ""


# =========================================================
# 遞迴找影片 URL
# =========================================================

def recursive_find_video_url(obj):

    preferred = [
        "video_url",
        "videoUrl",
        "download_url",
        "downloadUrl",
        "media_url",
        "mediaUrl",
        "output_url",
        "outputUrl",
    ]

    if isinstance(obj, dict):

        for key in preferred:

            value = obj.get(key)

            if (
                isinstance(value, str)
                and value.startswith("http")
            ):
                return value

        for value in obj.values():

            found = recursive_find_video_url(
                value
            )

            if found:
                return found

    elif isinstance(obj, list):

        for item in obj:

            found = recursive_find_video_url(
                item
            )

            if found:
                return found

    return ""


# =========================================================
# 遞迴找狀態
# =========================================================

def recursive_find_status(obj):

    valid = {
        "queued",
        "submitted",
        "pending",
        "processing",
        "running",
        "succeeded",
        "success",
        "completed",
        "complete",
        "failed",
        "failure",
        "cancelled",
        "canceled",
    }

    keys = [
        "status",
        "state",
        "task_status",
        "taskStatus",
    ]

    if isinstance(obj, dict):

        for key in keys:

            value = obj.get(key)

            if isinstance(value, str):

                value = value.strip().lower()

                if value in valid:
                    return value

        for value in obj.values():

            found = recursive_find_status(
                value
            )

            if found:
                return found

    elif isinstance(obj, list):

        for item in obj:

            found = recursive_find_status(
                item
            )

            if found:
                return found

    return ""


# =========================================================
# 下載影片
# =========================================================

def download_video(video_url):

    response = requests.get(
        video_url,
        timeout=180,
    )

    if response.status_code >= 400:

        raise RuntimeError(
            f"影片下載失敗：HTTP {response.status_code}"
        )

    if not response.content:

        raise RuntimeError(
            "影片內容為空。"
        )

    if len(response.content) > (
        MAX_VIDEO_MB * 1024 * 1024
    ):

        raise RuntimeError(
            f"影片超過 {MAX_VIDEO_MB} MB。"
        )

    return response.content


# =========================================================
# 儲存影片
# =========================================================

def store_generated_video(
    video_bytes,
    video_url="",
    mime="video/mp4",
):

    if not video_bytes:
        return

    signature = hashlib.sha256(
        video_bytes
    ).hexdigest()

    if (
        st.session_state.video_signature
        == signature
    ):
        return

    st.session_state.video_bytes = video_bytes

    st.session_state.video_url = video_url

    st.session_state.video_mime = mime

    st.session_state.video_signature = signature

    st.session_state.video_name = (
        "OpenClaw_AI_"
        + datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
        + ".mp4"
    )

    st.session_state.video_status = (
        "completed"
    )


# =========================================================
# 處理生成結果
# =========================================================

def process_video_result(result):

    video_url = recursive_find_video_url(
        result
    )

    task_id = recursive_find_task_id(
        result
    )

    status = recursive_find_status(
        result
    )

    if video_url:

        try:

            raw = download_video(
                video_url
            )

            store_generated_video(
                raw,
                video_url,
                "video/mp4",
            )

            return {
                "completed": True,
                "task_id": task_id,
                "status": "completed",
                "video_url": video_url,
            }

        except Exception as error:

            return {
                "completed": False,
                "task_id": task_id,
                "status": status or "submitted",
                "video_url": video_url,
                "download_error": str(error),
            }

    return {
        "completed": False,
        "task_id": task_id,
        "status": status or "submitted",
    }


# =========================================================
# 查詢影片狀態
# =========================================================

def check_video_status():

    if not openclaw_is_configured():

        raise RuntimeError(
            "OpenClaw 尚未設定。"
        )

    args = {
        "action": "status",
    }

    task_id = (
        st.session_state.video_task_id
    )

    if task_id:
        args["task_id"] = task_id

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

    processed = process_video_result(
        result
    )

    if processed.get("task_id"):

        st.session_state.video_task_id = (
            processed["task_id"]
        )

    st.session_state.video_status = (
        processed.get(
            "status",
            "processing",
        )
    )

    return processed


# =========================================================
# 清除生成影片
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
# 手動影片格式
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


# =========================================================
# 儲存手動影片
# =========================================================

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

        st.session_state.uploaded_video_bytes = raw

        st.session_state.uploaded_video_name = (
            video_file.name
        )

        st.session_state.uploaded_video_mime = mime

        st.session_state.uploaded_video_signature = (
            signature
        )

    return raw, mime, ext, size_mb


def clear_uploaded_video():

    st.session_state.uploaded_video_bytes = None
    st.session_state.uploaded_video_name = ""
    st.session_state.uploaded_video_mime = "video/mp4"
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
        'OpenClaw 龍蝦｜AI 商品分析｜真生成影片'
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
                "帳號：admin\n密碼：admin123"
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
            "會員帳號"
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

                st.error("請輸入姓名。")

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
                        "現在可以返回登入。"
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
# 登入控制
# =========================================================

if not st.session_state.logged_in:

    if st.session_state.page == "register":

        register_page()

    else:

        login_page()

    st.stop()


# =========================================================
# 會員驗證
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
        "## 🦞 OpenClaw AI"
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
        "♾️ 會員期限：永久"
    )

    st.divider()

    if openclaw_is_configured():

        st.success(
            "🟢 OpenClaw Gateway 已設定"
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
    'OpenClaw 龍蝦｜商品分析｜Image-to-Video｜'
    '多 Provider｜永久會員'
    '</div>',
    unsafe_allow_html=True,
)


# =========================================================
# OpenClaw 狀態
# =========================================================

st.subheader(
    "🦞 OpenClaw 龍蝦狀態"
)

if not openclaw_is_configured():

    st.warning(
        "🟡 OpenClaw 尚未設定。"
    )

    st.caption(
        "網站其他功能仍然可以使用；"
        "設定 Gateway 後才能提交真影片生成。"
    )

else:

    c1, c2 = st.columns(2)

    with c1:

        st.success(
            "🟢 OpenClaw Gateway 已設定"
        )

    with c2:

        if st.button(
            "🔄 測試 OpenClaw",
            use_container_width=True,
        ):

            with st.spinner(
                "正在測試 OpenClaw..."
            ):

                result = check_openclaw()

            if result.get("available"):

                st.success(
                    "🎉 OpenClaw 連線成功"
                )

            else:

                st.error(
                    "❌ OpenClaw 連線失敗"
                )

                st.code(
                    str(
                        result.get(
                            "message",
                            "",
                        )
                    )
                )


# =========================================================
# 設定
# =========================================================

with st.expander(
    "⚙️ OpenClaw 設定"
):

    st.write(
        "請將 Gateway 設定放在 Streamlit Secrets 或環境變數。"
    )

    st.code(
        "OPENCLAW_GATEWAY_URL\n"
        "OPENCLAW_GATEWAY_TOKEN"
    )

    if openclaw_is_configured():

        st.success(
            "OpenClaw Gateway URL 已設定。"
        )

        if get_openclaw_token():

            st.success(
                "Gateway Token 已設定。"
            )

        else:

            st.info(
                "目前沒有設定 Token；"
                "如果你的 Gateway 不需要 Token，可以直接使用。"
            )

    else:

        st.info(
            "目前沒有設定 OpenClaw Gateway。"
        )


# =========================================================
# 1 商品圖片
# =========================================================

st.subheader(
    "1｜📷 商品圖片"
)

st.info(
    "📱 手機操作：點「Browse files / 瀏覽檔案」後選擇商品照片。"
)

uploaded_file = st.file_uploader(

    "上傳商品圖片",

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


if uploaded_file is not None:

    try:

        raw_signature = hashlib.sha256(
            uploaded_file.getvalue()
        ).hexdigest()

        if (
            st.session_state.prepared_image_signature
            != raw_signature
        ):

            (
                prepared_image,
                prepared_image_bytes,
            ) = prepare_image(
                uploaded_file
            )

            st.session_state.prepared_image_bytes = (
                prepared_image_bytes
            )

            st.session_state.prepared_image_signature = (
                raw_signature
            )

            st.session_state.prepared_image_name = (
                uploaded_file.name
            )

        else:

            prepared_image_bytes = (
                st.session_state.prepared_image_bytes
            )

            if prepared_image_bytes:

                prepared_image = Image.open(
                    io.BytesIO(
                        prepared_image_bytes
                    )
                )

        if prepared_image is not None:

            st.success(
                "✅ 商品圖片已成功讀取"
            )

            st.image(
                prepared_image,
                caption="商品圖片｜將作為 Image-to-Video 參考圖",
                use_container_width=True,
            )

    except Exception as error:

        st.error(
            "❌ 圖片處理失敗"
        )

        st.code(
            str(error)
        )

else:

    if st.session_state.prepared_image_bytes:

        try:

            prepared_image = Image.open(
                io.BytesIO(
                    st.session_state.prepared_image_bytes
                )
            )

            prepared_image_bytes = (
                st.session_state.prepared_image_bytes
            )

            st.success(
                "✅ 已保留目前商品圖片"
            )

            st.image(
                prepared_image,
                caption="目前商品圖片",
                use_container_width=True,
            )

        except Exception:

            pass


# =========================================================
# 清除商品圖片
# =========================================================

if st.session_state.prepared_image_bytes:

    if st.button(
        "🗑️ 清除商品圖片",
        use_container_width=True,
    ):

        st.session_state.prepared_image_bytes = None
        st.session_state.prepared_image_signature = ""
        st.session_state.prepared_image_name = ""

        st.rerun()


# =========================================================
# 2 商品資料
# =========================================================

st.subheader(
    "2｜📦 商品資料"
)

col1, col2 = st.columns(2)

with col1:

    product_name = st.text_input(
        "商品名稱",
        placeholder="可留空",
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
        placeholder="可留空",
        height=120,
    )


# =========================================================
# 3 平台
# =========================================================

st.subheader(
    "3｜🎯 目標平台"
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
# 4 AI 功能
# =========================================================

st.subheader(
    "4｜🤖 AI 功能"
)

generate_options = [

    "商品辨識",

    "AI 選品分析",

    "蝦皮上架文案",

    "TikTok 文案",

    "OpenClaw 真生成影片",

    "多 Provider 自動切換",

    "分潤合規檢查",

    "完整流程",

]

selected_items = st.multiselect(
    "AI 功能",
    generate_options,
    default=generate_options,
)


# =========================================================
# 5 影片設定
# =========================================================

st.subheader(
    "5｜🎬 真生成影片設定"
)

v1, v2, v3 = st.columns(3)

with v1:

    video_duration = st.selectbox(
        "影片秒數",
        [
            5,
            6,
            8,
            10,
            12,
        ],
        index=3,
    )

with v2:

    video_ratio = st.selectbox(
        "比例",
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
        placeholder="留空＝OpenClaw 自動選擇",
    )

st.caption(
    "💡 Model 留空時，由你的 OpenClaw 後端決定 Provider / fallback。"
)


# =========================================================
# Prompt
# =========================================================

kling_prompt = build_video_prompt(

    product_name=product_name,

    product_spec=product_spec,

    target_platform=target_platform,

    duration=video_duration,

    ratio=video_ratio,

)

st.session_state.kling_prompt = kling_prompt


with st.expander(
    "🎬 查看 / 複製影片 Prompt"
):

    st.text_area(
        "Video Prompt",
        value=kling_prompt,
        height=500,
    )


# =========================================================
# AI 商品分析
# =========================================================

if (
    "商品辨識" in selected_items
    or "AI 選品分析" in selected_items
    or "完整流程" in selected_items
):

    st.divider()

    st.subheader(
        "🔎 AI 商品分析"
    )

    analysis = build_product_analysis(

        product_name,

        product_price,

        product_cost,

        commission_rate,

        monthly_sales,

        product_rating,

        product_spec,

    )

    st.text_area(
        "分析結果",
        value=analysis,
        height=300,
    )


# =========================================================
# 蝦皮文案
# =========================================================

if (
    "蝦皮上架文案" in selected_items
    or "完整流程" in selected_items
):

    st.divider()

    st.subheader(
        "🛒 蝦皮上架文案"
    )

    shopee_copy = build_shopee_copy(

        product_name,

        product_price,

        product_spec,

        target_platform,

    )

    st.text_area(
        "蝦皮文案",
        value=shopee_copy,
        height=280,
    )


# =========================================================
# TikTok
# =========================================================

if (
    "TikTok 文案" in selected_items
    or "完整流程" in selected_items
):

    st.divider()

    st.subheader(
        "🎵 TikTok 文案"
    )

    tiktok_copy = build_tiktok_copy(
        product_name,
        target_platform,
    )

    st.text_area(
        "TikTok 文案",
        value=tiktok_copy,
        height=250,
    )


# =========================================================
# 6 啟動影片
# =========================================================

st.divider()

st.subheader(
    "6｜🦞 啟動 OpenClaw 真生成"
)

if st.button(

    "🦞🚀 啟動 OpenClaw 真生成影片",

    type="primary",

    use_container_width=True,

    key="start_openclaw_video",

):

    if not st.session_state.prepared_image_bytes:

        st.error(
            "❌ 請先上傳商品圖片。"
        )

    elif not openclaw_is_configured():

        st.warning(
            "🟡 OpenClaw Gateway 尚未設定。"
        )

        st.info(
            "圖片與網站本身正常；"
            "目前只是沒有影片生成後端。"
        )

    else:

        clear_generated_video()

        with st.spinner(
            "🦞 正在提交 OpenClaw 真影片任務..."
        ):

            try:

                result = openclaw_generate_video(

                    image_bytes=
                        st.session_state.prepared_image_bytes,

                    prompt=
                        st.session_state.kling_prompt,

                    duration=
                        video_duration,

                    ratio=
                        video_ratio,

                    model=
                        video_model,

                )

                processed = process_video_result(
                    result
                )

                task_id = processed.get(
                    "task_id",
                    "",
                )

                status = processed.get(
                    "status",
                    "submitted",
                )

                if task_id:

                    st.session_state.video_task_id = (
                        task_id
                    )

                st.session_state.video_status = (
                    status
                )

                if processed.get("completed"):

                    st.balloons()

                    st.success(
                        "🎉 真影片已生成完成！"
                    )

                else:

                    st.success(
                        "✅ 已提交 OpenClaw 影片任務！"
                    )

                    if task_id:

                        st.info(
                            f"Task ID：{task_id}"
                        )

                    st.info(
                        "影片正在非同步生成，"
                        "請到下面「影片任務中心」查詢。"
                    )

            except Exception as error:

                st.error(
                    "❌ OpenClaw 影片生成失敗"
                )

                st.code(
                    str(error)
                )


# =========================================================
# 影片任務中心
# =========================================================

st.divider()

st.markdown(
    '<div class="video-title">'
    '🎬 真生成影片中心'
    '</div>',
    unsafe_allow_html=True,
)


if st.session_state.video_task_id:

    st.info(
        "🦞 目前有一個 OpenClaw 影片任務。"
    )

    st.write(
        "Task ID："
    )

    st.code(
        st.session_state.video_task_id
    )

    st.write(
        "目前狀態："
    )

    st.info(
        st.session_state.video_status
        or "processing"
    )

    if st.button(
        "🔄 查詢影片狀態",
        use_container_width=True,
        key="check_openclaw_video",
    ):

        if not openclaw_is_configured():

            st.error(
                "OpenClaw 尚未設定。"
            )

        else:

            with st.spinner(
                "🦞 正在查詢影片..."
            ):

                try:

                    result = check_video_status()

                    if st.session_state.video_bytes:

                        st.success(
                            "🎉 影片已完成！"
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


if st.session_state.video_bytes:

    st.success(
        "🟢 AI 真生成影片已完成"
    )

    st.video(
        st.session_state.video_bytes,
        format=st.session_state.video_mime,
        start_time=0,
    )

    st.caption(
        "📱 手機建議使用 MP4 / H.264 / AAC。"
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

        key="download_generated_video",

    )

    if st.session_state.video_url:

        st.caption(
            "影片來源 URL 已由 OpenClaw 回傳。"
        )

    if st.button(
        "🗑️ 清除 AI 真生成影片",
        use_container_width=True,
        key="clear_generated",
    ):

        clear_generated_video()

        st.rerun()

else:

    if not st.session_state.video_task_id:

        st.info(
            "目前尚未生成影片。"
            "先上傳商品圖片，再啟動 OpenClaw 真生成。"
        )


# =========================================================
# OpenClaw 原始回應
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
# 手動影片上傳
# =========================================================

st.divider()

st.subheader(
    "📤 其他影片上傳 / 預覽"
)

st.caption(
    "支援 MP4 / MOV / WEBM，最大 300 MB。"
)

uploaded_video = st.file_uploader(

    "📱 選擇影片",

    type=[
        "mp4",
        "mov",
        "webm",
    ],

    accept_multiple_files=False,

    key="manual_video_uploader",

)


if uploaded_video is not None:

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
                "🟡 MOV：部分手機可能需要轉成 MP4。"
            )

        elif ext == ".webm":

            st.warning(
                "🟡 WEBM：部分手機瀏覽器可能不支援。"
            )

    except Exception as error:

        st.error(
            "❌ 影片處理失敗"
        )

        st.code(
            str(error)
        )


# =========================================================
# Session 手動影片
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

        format=
            st.session_state.uploaded_video_mime,

        start_time=0,

    )

    if st.button(
        "🗑️ 清除目前上傳影片",
        use_container_width=True,
        key="clear_uploaded_video",
    ):

        clear_uploaded_video()

        st.rerun()


# =========================================================
# 手機格式說明
# =========================================================

with st.expander(
    "📱 手機播放與影片格式"
):

    st.markdown(
        """
### ⭐ 最推薦

**MP4**

Video：

**H.264**

Audio：

**AAC**

社群影片：

**1080 × 1920**

比例：

**9:16**

---

### MOV

可以上傳。

如果手機出現：

- 黑屏
- 只有聲音
- 一直轉圈
- 無法播放

建議轉成：

**MP4 / H.264 / AAC**

---

### WEBM

可以上傳。

如果手機瀏覽器無法播放，

建議轉：

**MP4 / H.264 / AAC**
"""
    )


# =========================================================
# 發布前檢查
# =========================================================

st.divider()

st.subheader(
    "✅ 發布前檢查"
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
    checked
    / len(check_items)
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
# 管理員
# =========================================================

if member_role.lower() == "admin":

    st.divider()

    with st.expander(
        "👑 管理員中心"
    ):

        members = load_members()

        st.write(
            f"會員數：**{len(members)}**"
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

                    "狀態",

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

                    "等級",

                    roles,

                    index=(
                        roles.index(role)
                        if role in roles
                        else 0
                    ),

                    key=f"role_{mid}",

                )

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
                            "permanent": True,
                        },

                    )

                    st.success(
                        "會員資料已更新。"
                    )

                    st.rerun()


# =========================================================
# 系統功能
# =========================================================

with st.expander(
    "⚙️ 系統功能"
):

    features = [

        "✅ Streamlit",

        "✅ 手機版 UI",

        "✅ 商品圖片上傳",

        "✅ JPG / JPEG / PNG / WEBP",

        "✅ 商品圖片自動縮放",

        "✅ OpenClaw Gateway",

        "✅ Image-to-Video",

        "✅ Provider / Model 選擇",

        "✅ OpenClaw 非同步 Task",

        "✅ Task ID",

        "✅ 影片狀態查詢",

        "✅ 真生成影片播放器",

        "✅ MP4",

        "✅ MOV",

        "✅ WEBM",

        "✅ 手動影片上傳",

        "✅ 影片下載",

        "✅ 永久會員",

        "✅ 管理員",

        "✅ 商品分析",

        "✅ 蝦皮文案",

        "✅ TikTok 文案",

        "✅ 商品原貌鎖定",

        "✅ 發布前檢查",

    ]

    for feature in features:

        st.write(feature)


# =========================================================
# Footer
# =========================================================

st.divider()

st.caption(
    "AI 蝦皮半自動化 2.5 PRO｜"
    "OpenClaw 龍蝦｜"
    "Image-to-Video｜"
    "手機優化｜"
    "永久會員｜"
    "MP4 / MOV / WEBM"
)
