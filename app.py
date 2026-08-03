import io
import os
import re
import json
import base64
import hashlib
import secrets
import time
from datetime import datetime, date, timedelta
from urllib.parse import urlencode

import requests
import streamlit as st
from PIL import Image, ImageOps


# =========================================================
# AI 蝦皮半自動化 2.5 PRO
# Kling 真生成影片版
#
# 功能：
# 1. 商品圖片上傳
# 2. Gemini 圖片辨識
# 3. Gemini 商品分析
# 4. Gemini 蝦皮文案
# 5. Gemini TikTok 文案
# 6. Gemini Kling 影片 Prompt
# 7. Kling 3.0 Turbo Image-to-Video
# 8. 真正送 API 生成影片
# 9. 自動查詢 Kling 任務狀態
# 10. 生成完成後自動播放
# 11. 影片 Session 狀態避免重複顯示
# 12. MP4 / MOV / WEBM 上傳
# 13. 手機播放提示
# 14. 影片下載
# 15. 會員系統
# 16. 管理員
# 17. 會員到期
#
# Kling：
# Image-to-Video
# kling-3.0-turbo
#
# 注意：
# Gemini = 商品圖片分析 / Prompt
# Kling = 真正影片生成
# =========================================================


# =========================================================
# Google Gemini
# =========================================================

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


# =========================================================
# 網頁設定
# =========================================================

st.set_page_config(
    page_title="AI 蝦皮半自動化 2.5 PRO｜Kling",
    page_icon="🛒",
    layout="wide",
)


APP_NAME = "AI 蝦皮半自動化 2.5 PRO"

DATA_DIR = "data"
MEMBERS_FILE = os.path.join(DATA_DIR, "members.json")

MAX_IMAGE_SIZE = 1600
MAX_IMAGE_MB = 20

MAX_VIDEO_MB = 300

DEFAULT_MEMBER_DAYS = 30

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


# =========================================================
# Gemini 模型
# =========================================================

GEMINI_MODEL_CANDIDATES = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
]


# =========================================================
# Kling 設定
# =========================================================

KLING_BASE_URL = "https://api-singapore.klingai.com"

KLING_IMAGE_TO_VIDEO_PATH = (
    "/kling/image-to-video/kling-3.0-turbo"
)

KLING_TASKS_PATH = "/kling/tasks"

KLING_MODEL_NAME = "kling-3.0-turbo"

KLING_DEFAULT_RESOLUTION = "1080p"

KLING_DEFAULT_DURATION = 10

KLING_DEFAULT_ASPECT_RATIO = "9:16"

KLING_POLL_SECONDS = 5

KLING_MAX_WAIT_SECONDS = 600


# =========================================================
# 影片 MIME
# =========================================================

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
        (salt + password).encode("utf-8")
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
            (salt + password).encode("utf-8")
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

        "password_hash":
            hash_password(
                ADMIN_PASSWORD
            ),

        "name": "系統管理員",

        "email": "",

        "role": "admin",

        "status": "active",

        "expires":
            (
                date.today()
                + timedelta(days=3650)
            ).isoformat(),

        "created_at":
            datetime.now().isoformat(),

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

        "password_hash":
            hash_password(password),

        "name":
            str(name).strip(),

        "email": email,

        "role": "member",

        "status": "active",

        "expires": expires,

        "created_at":
            datetime.now().isoformat(),

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

    saved_hash = str(
        member.get(
            "password_hash",
            "",
        )
    )

    if not saved_hash:
        return False, "invalid"

    if not verify_password(
        password,
        saved_hash,
    ):

        return False, "invalid"

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

        return False, "invalid_date"

    if date.today() > expires_date:

        return False, "expired"

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

    "analysis_mode": "",

    "gemini_model": "",

    "gemini_error": "",

    "last_product_name": "",

    # Kling
    "kling_task_id": "",

    "kling_external_task_id": "",

    "kling_status": "",

    "kling_prompt": "",

    "kling_video_url": "",

    "kling_video_bytes": None,

    "kling_video_name": "",

    "kling_video_mime": "video/mp4",

    # 上傳影片
    "uploaded_video_bytes": None,

    "uploaded_video_name": "",

    "uploaded_video_mime": "video/mp4",

    "uploaded_video_ext": ".mp4",

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
# Secrets
# =========================================================

def get_secret(name):

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


def get_gemini_api_key():

    return get_secret(
        "GEMINI_API_KEY"
    )


def get_kling_api_key():

    return get_secret(
        "KLING_API_KEY"
    )


# =========================================================
# Gemini Client
# =========================================================

@st.cache_resource
def get_gemini_client(api_key):

    if not api_key:
        return None

    if genai is None:
        return None

    return genai.Client(
        api_key=api_key
    )


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
    ):

        return (
            "Gemini 模型無法使用。\n\n"
            f"原始錯誤：{text}"
        )

    if (
        "401" in lower
        or "invalid" in lower
        and "api key" in lower
    ):

        return (
            "Gemini API Key 無效。\n\n"
            f"原始錯誤：{text}"
        )

    if "403" in lower:

        return (
            "Gemini API 權限不足。\n\n"
            f"原始錯誤：{text}"
        )

    if (
        "429" in lower
        or "quota" in lower
    ):

        return (
            "Gemini API 額度或速率限制。\n\n"
            f"原始錯誤：{text}"
        )

    return (
        "Gemini API 呼叫失敗。\n\n"
        f"{text}"
    )


# =========================================================
# Gemini
# =========================================================

def call_gemini(
    prompt,
    image_bytes=None,
    mime_type="image/jpeg",
):

    api_key = get_gemini_api_key()

    if not api_key:

        raise RuntimeError(
            "找不到 GEMINI_API_KEY。"
        )

    if genai is None:

        raise RuntimeError(
            "尚未安裝 google-genai。\n\n"
            "requirements.txt 請加入：\n"
            "google-genai"
        )

    client = get_gemini_client(
        api_key
    )

    if client is None:

        raise RuntimeError(
            "Gemini Client 建立失敗。"
        )

    errors = []

    for model_name in GEMINI_MODEL_CANDIDATES:

        try:

            contents = []

            if image_bytes:

                image_part = (
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type=mime_type,
                    )
                )

                contents.append(
                    image_part
                )

            contents.append(prompt)

            response = (
                client
                .models
                .generate_content(
                    model=model_name,
                    contents=contents,
                )
            )

            text = getattr(
                response,
                "text",
                None,
            )

            if not text:

                raise RuntimeError(
                    "Gemini 回傳成功，但沒有文字內容。"
                )

            st.session_state.gemini_model = (
                model_name
            )

            return str(text)

        except Exception as error:

            error_text = str(error)

            errors.append(
                f"{model_name}: {error_text}"
            )

            lower = error_text.lower()

            model_error = (
                "404" in lower
                or "not_found" in lower
                or "not found" in lower
            )

            if model_error:
                continue

            raise RuntimeError(
                explain_gemini_error(error)
            )

    raise RuntimeError(
        "Gemini 模型全部失敗。\n\n"
        + "\n\n".join(errors)
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
            mask=image.getchannel(
                "A"
            ),
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
# Kling 商品影片核心規則
# =========================================================

KLING_PRODUCT_RULES = """

PRODUCT IDENTITY LOCK:

Use the uploaded product image as the ONLY main product reference.

Preserve exactly:

- original brand
- original packaging
- original shape
- original proportions
- original colors
- original material
- original logo
- original label
- original printed text
- original package structure

The product must remain visually identical
throughout the entire video.

Do NOT:

- redesign the package
- change the brand
- change the logo
- change label text
- change product color
- change product shape
- change product proportions
- create a second product
- duplicate the product
- morph the product
- melt the product
- distort the package
- make the product disappear
- add fake claims
- add fake prices
- add fake discounts
- add fake gifts
- add fake certifications

Default scene:

No people.
No hands.
No influencer.
No presenter.
No model.
No spokesperson.

Premium commercial product photography.
Photorealistic.
Stable product identity.
Smooth cinematic camera motion.
No flicker.
No warping.
No text drift.
No watermark.
"""


# =========================================================
# Kling Prompt
# =========================================================

def build_kling_prompt(
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
        else "unknown specifications"
    )

    return f"""
Create a premium commercial vertical product video.

MAIN PRODUCT:
{product_name}

KNOWN SPECIFICATION:
{product_spec}

TARGET PLATFORM:
{target_platform}

VIDEO:
9:16 vertical.
10 seconds.
1080p.
Photorealistic premium commercial product advertising.

SCENE 1 — 0 to 3 seconds:
Show the uploaded product clearly and centered.
Use the uploaded product image as the exact first-frame reference.
The original product must be immediately recognizable.
Clean premium studio environment.
Stable framing.

SCENE 2 — 3 to 6 seconds:
Slow cinematic push-in toward the product.
Reveal packaging, material, surface details, logo and label.
Keep the exact original product identity.
Do not redesign or alter any printed information.

SCENE 3 — 6 to 8 seconds:
Very subtle cinematic orbit movement around the product.
The product remains stable and centered.
Maintain exact proportions and packaging.
No duplicate products.

SCENE 4 — 8 to 10 seconds:
Smooth camera movement returns to a clean centered hero shot.
Hold the product stable.
Premium commercial ending.

CAMERA:
slow cinematic push-in,
subtle orbit movement,
smooth camera motion,
stable framing,
controlled depth of field,
professional commercial photography.

LIGHTING:
premium studio lighting,
soft realistic highlights,
natural shadows,
clean background,
high-end product advertising.

STRICT PRODUCT CONSISTENCY:
same product identity,
same packaging,
same color,
same shape,
same proportions,
same logo,
same label,
same printed text,
same material.

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
low quality,
cartoon,
illustration,
3D render,
unrealistic product.

{KLING_PRODUCT_RULES}
"""


# =========================================================
# 自動勾選
# =========================================================

def auto_select_features():

    return [
        "商品辨識",
        "AI 選品分析",
        "蝦皮上架文案",
        "TikTok 文案",
        "Kling AI 3.0 真生成影片",
        "分潤合規檢查",
        "完整流程",
    ]


# =========================================================
# Kling 圖片 Base64
# =========================================================

def image_bytes_to_base64(
    image_bytes,
):

    return base64.b64encode(
        image_bytes
    ).decode("utf-8")


# =========================================================
# Kling Headers
# =========================================================

def kling_headers():

    api_key = get_kling_api_key()

    if not api_key:

        raise RuntimeError(
            "找不到 KLING_API_KEY。\n\n"
            "請在 Streamlit Secrets 設定：\n"
            'KLING_API_KEY = "你的 Kling API Key"'
        )

    return {
        "Content-Type":
            "application/json",

        "Authorization":
            f"Bearer {api_key}",
    }


# =========================================================
# Kling 建立任務
# =========================================================

def kling_create_image_to_video(
    image_bytes,
    prompt,
    resolution="1080p",
    duration=10,
    aspect_ratio="9:16",
    watermark=False,
):

    if not image_bytes:

        raise RuntimeError(
            "Kling 沒有收到商品圖片。"
        )

    if not prompt:

        raise RuntimeError(
            "Kling Prompt 是空的。"
        )

    if duration not in range(
        3,
        16,
    ):

        duration = 10

    image_base64 = image_bytes_to_base64(
        image_bytes
    )

    # =====================================================
    # Kling 首幀
    #
    # 這裡使用 Base64，
    # 不需要另外架圖片網址。
    # =====================================================

    payload = {

        "contents": [

            {
                "type": "prompt",
                "text": prompt,
            },

            {
                "type": "first_frame",
                "url": image_base64,
            },

        ],

        "settings": {

            "resolution": resolution,

            "aspect_ratio":
                aspect_ratio,

            "duration":
                duration,

        },

        "options": {

            "external_task_id":
                (
                    "shopee_"
                    + secrets.token_hex(12)
                ),

            "watermark_info": {

                "enabled":
                    watermark,

            },

        },

    }

    url = (
        KLING_BASE_URL
        + KLING_IMAGE_TO_VIDEO_PATH
    )

    response = requests.post(
        url,
        headers=kling_headers(),
        json=payload,
        timeout=120,
    )

    if response.status_code >= 400:

        raise RuntimeError(
            "Kling 建立影片任務失敗。\n\n"
            f"HTTP：{response.status_code}\n\n"
            f"{response.text}"
        )

    try:

        data = response.json()

    except Exception:

        raise RuntimeError(
            "Kling 回傳不是有效 JSON：\n\n"
            + response.text
        )

    if not isinstance(data, dict):

        raise RuntimeError(
            "Kling 回傳資料格式錯誤。"
        )

    data_block = data.get(
        "data",
        data,
    )

    task_id = (
        data_block.get("id")
        or data_block.get("task_id")
        or data_block.get("taskId")
    )

    external_task_id = (
        data_block.get(
            "external_task_id"
        )
        or data_block.get(
            "externalTaskId"
        )
        or payload["options"][
            "external_task_id"
        ]
    )

    if not task_id:

        raise RuntimeError(
            "Kling 沒有回傳 task ID。\n\n"
            + json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            )
        )

    st.session_state.kling_task_id = (
        str(task_id)
    )

    st.session_state.kling_external_task_id = (
        str(external_task_id)
    )

    st.session_state.kling_status = (
        str(
            data_block.get(
                "status",
                data_block.get(
                    "task_status",
                    "submitted",
                ),
            )
        )
    )

    return (
        str(task_id),
        str(external_task_id),
        data,
    )


# =========================================================
# 解析 Kling 回傳
# =========================================================

def recursive_find_video_url(
    obj,
):

    if isinstance(obj, dict):

        # 常見直接欄位
        for key in [
            "video_url",
            "videoUrl",
            "url",
            "download_url",
            "downloadUrl",
        ]:

            value = obj.get(key)

            if (
                isinstance(value, str)
                and value.startswith(
                    "http"
                )
            ):

                if (
                    ".mp4" in value.lower()
                    or "video" in key.lower()
                    or key.lower() == "url"
                ):

                    return value

        # outputs
        outputs = obj.get(
            "outputs"
        )

        if isinstance(
            outputs,
            list,
        ):

            for item in outputs:

                if isinstance(
                    item,
                    dict,
                ):

                    item_type = str(
                        item.get(
                            "type",
                            "",
                        )
                    ).lower()

                    url = item.get(
                        "url"
                    )

                    if (
                        isinstance(
                            url,
                            str,
                        )
                        and url.startswith(
                            "http"
                        )
                    ):

                        if (
                            "video"
                            in item_type
                            or
                            ".mp4"
                            in url.lower()
                        ):

                            return url

        # task_result
        task_result = obj.get(
            "task_result"
        )

        if task_result:

            result = recursive_find_video_url(
                task_result
            )

            if result:
                return result

        # data
        for key, value in obj.items():

            if key in [
                "outputs",
                "task_result",
                "data",
            ]:

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
# Kling 查詢任務
# =========================================================

def kling_query_task(
    task_id=None,
    external_task_id=None,
):

    if not task_id and not external_task_id:

        raise RuntimeError(
            "缺少 Kling task ID。"
        )

    params = {}

    if task_id:

        params["task_ids"] = task_id

    else:

        params[
            "external_task_ids"
        ] = external_task_id

    url = (
        KLING_BASE_URL
        + KLING_TASKS_PATH
    )

    response = requests.get(
        url,
        headers=kling_headers(),
        params=params,
        timeout=60,
    )

    if response.status_code >= 400:

        raise RuntimeError(
            "Kling 查詢任務失敗。\n\n"
            f"HTTP：{response.status_code}\n\n"
            f"{response.text}"
        )

    try:

        return response.json()

    except Exception:

        raise RuntimeError(
            "Kling 查詢回傳不是 JSON。\n\n"
            + response.text
        )


# =========================================================
# 狀態搜尋
# =========================================================

def recursive_find_status(
    obj,
):

    possible_keys = [
        "status",
        "task_status",
        "taskStatus",
    ]

    if isinstance(obj, dict):

        for key in possible_keys:

            value = obj.get(key)

            if isinstance(
                value,
                str,
            ):

                normalized = (
                    value
                    .strip()
                    .lower()
                )

                if normalized in [
                    "submitted",
                    "processing",
                    "running",
                    "queued",
                    "succeeded",
                    "success",
                    "succeed",
                    "failed",
                    "failure",
                    "cancelled",
                    "canceled",
                ]:

                    return normalized

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
# Kling 等待生成
# =========================================================

def kling_wait_for_video(
    task_id,
    external_task_id,
    max_wait_seconds=KLING_MAX_WAIT_SECONDS,
):

    started = time.time()

    last_status = ""

    while (
        time.time() - started
        < max_wait_seconds
    ):

        result = kling_query_task(
            task_id=task_id,
            external_task_id=None,
        )

        status = recursive_find_status(
            result
        )

        if not status:

            status = "processing"

        if status != last_status:

            st.session_state.kling_status = (
                status
            )

            last_status = status

        # 成功
        if status in [
            "succeeded",
            "success",
            "succeed",
        ]:

            video_url = (
                recursive_find_video_url(
                    result
                )
            )

            if not video_url:

                raise RuntimeError(
                    "Kling 顯示生成成功，"
                    "但沒有找到影片 URL。\n\n"
                    + json.dumps(
                        result,
                        ensure_ascii=False,
                        indent=2,
                    )
                )

            return (
                video_url,
                result,
            )

        # 失敗
        if status in [
            "failed",
            "failure",
            "cancelled",
            "canceled",
        ]:

            raise RuntimeError(
                "Kling 影片生成失敗。\n\n"
                + json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )

        elapsed = int(
            time.time() - started
        )

        remaining = max(
            0,
            max_wait_seconds
            - elapsed,
        )

        st.info(
            f"🎬 Kling 正在生成影片……"
            f"\n\n"
            f"狀態：`{status}`"
            f"\n"
            f"已等待：{elapsed} 秒"
            f"\n"
            f"最多等待：{max_wait_seconds} 秒"
        )

        time.sleep(
            KLING_POLL_SECONDS
        )

    raise RuntimeError(
        "Kling 影片生成等待逾時。\n\n"
        f"Task ID：{task_id}\n"
        "你可以稍後重新查詢任務。"
    )


# =========================================================
# 下載 Kling 影片
# =========================================================

def download_kling_video(
    video_url,
):

    response = requests.get(
        video_url,
        timeout=180,
    )

    if response.status_code >= 400:

        raise RuntimeError(
            "無法下載 Kling 生成影片。\n\n"
            f"HTTP：{response.status_code}"
        )

    raw = response.content

    if not raw:

        raise RuntimeError(
            "Kling 影片下載結果是空的。"
        )

    return raw


# =========================================================
# 自動完整 Kling 生成
# =========================================================

def generate_real_kling_video(
    image_bytes,
    product_name,
    product_spec,
    target_platform,
    resolution,
    duration,
    aspect_ratio,
    watermark,
):

    prompt = build_kling_prompt(
        product_name=product_name,
        product_spec=product_spec,
        target_platform=target_platform,
    )

    st.session_state.kling_prompt = (
        prompt
    )

    with st.spinner(
        "🎬 正在建立 Kling 真影片生成任務……"
    ):

        (
            task_id,
            external_task_id,
            create_response,
        ) = kling_create_image_to_video(
            image_bytes=image_bytes,
            prompt=prompt,
            resolution=resolution,
            duration=duration,
            aspect_ratio=aspect_ratio,
            watermark=watermark,
        )

    st.success(
        "✅ Kling 真影片任務已建立！"
    )

    st.code(
        f"Task ID：{task_id}"
    )

    with st.spinner(
        "🎬 Kling 正在真正生成影片，請稍候……"
    ):

        (
            video_url,
            query_response,
        ) = kling_wait_for_video(
            task_id=task_id,
            external_task_id=external_task_id,
        )

    st.success(
        "🎉 Kling 影片生成完成！"
    )

    with st.spinner(
        "⬇️ 正在取得 Kling 影片……"
    ):

        video_bytes = (
            download_kling_video(
                video_url
            )
        )

    st.session_state.kling_video_url = (
        video_url
    )

    st.session_state.kling_video_bytes = (
        video_bytes
    )

    st.session_state.kling_video_name = (
        "Kling_3.0_Turbo_"
        + datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
        + ".mp4"
    )

    st.session_state.kling_video_mime = (
        "video/mp4"
    )

    st.session_state.kling_status = (
        "succeeded"
    )

    return (
        video_bytes,
        video_url,
    )


# =========================================================
# 影片 MIME
# =========================================================

def detect_video_mime(
    filename,
    browser_mime="",
):

    ext = os.path.splitext(
        str(filename or "")
    )[1].lower()

    if ext in VIDEO_MIME_MAP:

        return (
            VIDEO_MIME_MAP[ext],
            ext,
        )

    if browser_mime in (
        VIDEO_TYPE_MAP.values()
    ):

        for suffix, mime in (
            VIDEO_MIME_MAP.items()
        ):

            if mime == browser_mime:

                return (
                    mime,
                    suffix,
                )

    return (
        "video/mp4",
        ".mp4",
    )


# =========================================================
# 使用者上傳影片
# =========================================================

def save_uploaded_video(
    video_file,
):

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

    # 防止同一檔案重複寫入
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

        st.session_state.uploaded_video_ext = (
            ext
        )

        st.session_state.uploaded_video_signature = (
            signature
        )

    return (
        raw,
        mime,
        ext,
        size_mb,
    )


# =========================================================
# 清除使用者影片
# =========================================================

def clear_uploaded_video():

    st.session_state.uploaded_video_bytes = (
        None
    )

    st.session_state.uploaded_video_name = (
        ""
    )

    st.session_state.uploaded_video_mime = (
        "video/mp4"
    )

    st.session_state.uploaded_video_ext = (
        ".mp4"
    )

    st.session_state.uploaded_video_signature = (
        ""
    )


# =========================================================
# 清除 Kling 生成影片
# =========================================================

def clear_kling_video():

    st.session_state.kling_video_url = ""

    st.session_state.kling_video_bytes = (
        None
    )

    st.session_state.kling_video_name = ""

    st.session_state.kling_video_mime = (
        "video/mp4"
    )

    st.session_state.kling_task_id = ""

    st.session_state.kling_external_task_id = ""

    st.session_state.kling_status = ""

    st.session_state.kling_prompt = ""


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
        'Gemini AI｜Kling 真生成影片'
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

                success, result = (
                    check_login(
                        username,
                        password,
                    )
                )

                if success:

                    st.session_state.logged_in = (
                        True
                    )

                    st.session_state.username = (
                        username.strip().lower()
                    )

                    st.session_state.member = (
                        result
                    )

                    st.session_state.page = (
                        "main"
                    )

                    st.rerun()

                messages = {

                    "expired":
                        "⛔ 會員資格已到期。",

                    "disabled":
                        "⛔ 帳號已停權。",

                    "invalid_date":
                        "⛔ 到期日資料錯誤。",

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
            "📝 註冊會員",
            use_container_width=True,
        ):

            st.session_state.page = (
                "register"
            )

            st.rerun()

        with st.expander(
            "🔐 管理員測試帳號"
        ):

            st.code(
                "帳號：admin\n"
                "密碼：admin123"
            )


# =========================================================
# 註冊
# =========================================================

def register_page():

    st.markdown(
        '<div class="main-title">'
        '📝 會員註冊'
        '</div>',
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns(
        [1, 2, 1]
    )

    with center:

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
            "🚀 建立會員",
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

                success, result = (
                    create_member(
                        username_clean,
                        password,
                        name,
                        email_clean,
                    )
                )

                if success:

                    st.success(
                        "🎉 會員建立成功！"
                    )

                    st.info(
                        f"預設會員期限："
                        f"{DEFAULT_MEMBER_DAYS} 天"
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

            st.session_state.page = (
                "login"
            )

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
# 會員資訊
# =========================================================

current_username = (
    st.session_state.username
)

current_member = (
    st.session_state.member
)

latest_member = find_member(
    current_username
)

if latest_member:

    current_member = (
        latest_member
    )

    st.session_state.member = (
        latest_member
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


if member_status != "active":

    st.error(
        "⛔ 會員帳號已停權。"
    )

    if st.button(
        "🚪 登出"
    ):

        logout()

    st.stop()


if remaining_days < 0:

    st.error(
        "⛔ 會員資格已到期。"
    )

    if st.button(
        "🚪 登出"
    ):

        logout()

    st.stop()


# =========================================================
# Sidebar
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
        f"到期日：**{member_expires}**"
    )

    if remaining_days <= 7:

        st.warning(
            f"⚠️ 剩餘 {remaining_days} 天"
        )

    else:

        st.info(
            f"⏳ 剩餘 {remaining_days} 天"
        )

    st.divider()

    if get_kling_api_key():

        st.success(
            "🟢 Kling API Key 已設定"
        )

    else:

        st.error(
            "🔴 Kling API Key 未設定"
        )

    if get_gemini_api_key():

        st.success(
            "🟢 Gemini API Key 已設定"
        )

    else:

        st.warning(
            "🟡 Gemini API Key 未設定"
        )

    st.divider()

    if st.button(
        "🚪 登出",
        use_container_width=True,
    ):

        logout()


# =========================================================
# 管理員
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
                    "disabled",
                ],
                index=(
                    0
                    if status
                    == "active"
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

            try:

                expire_value = (
                    date.fromisoformat(
                        expires
                    )
                )

            except Exception:

                expire_value = (
                    date.today()
                )

            new_expire = st.date_input(
                "會員到期日",
                value=expire_value,
                key=f"expire_{mid}",
            )

            c1, c2, c3 = st.columns(3)

            with c1:

                if st.button(
                    "💾 儲存",
                    key=f"save_{mid}",
                    use_container_width=True,
                ):

                    update_member(
                        mid,
                        {
                            "status":
                                new_status,

                            "role":
                                new_role,

                            "expires":
                                new_expire.isoformat(),
                        },
                    )

                    st.success(
                        "已更新。"
                    )

                    st.rerun()

            with c2:

                if st.button(
                    "➕ 延長 30 天",
                    key=f"extend_{mid}",
                    use_container_width=True,
                ):

                    try:

                        d = date.fromisoformat(
                            expires
                        )

                    except Exception:

                        d = date.today()

                    if d < date.today():

                        d = date.today()

                    new_date = (
                        d
                        + timedelta(
                            days=30
                        )
                    )

                    update_member(
                        mid,
                        {
                            "expires":
                                new_date.isoformat(),

                            "status":
                                "active",
                        },
                    )

                    st.success(
                        "已延長至 "
                        + new_date.isoformat()
                    )

                    st.rerun()

            with c3:

                if username != current_username:

                    if st.button(
                        "⛔ 停權",
                        key=f"disable_{mid}",
                        use_container_width=True,
                    ):

                        update_member(
                            mid,
                            {
                                "status":
                                    "disabled"
                            },
                        )

                        st.warning(
                            "會員已停權。"
                        )

                        st.rerun()


# =========================================================
# 標題
# =========================================================

st.markdown(
    '<div class="main-title">'
    '🛒 AI 蝦皮半自動化 2.5 PRO'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-subtitle">'
    'Gemini 商品辨識｜AI 選品｜蝦皮文案｜'
    'TikTok｜Kling 3.0 Turbo 真生成影片｜'
    '影片中心｜分潤合規'
    '</div>',
    unsafe_allow_html=True,
)


# =========================================================
# Admin
# =========================================================

if member_role.lower() == "admin":

    with st.expander(
        "👑 管理員中心"
    ):

        admin_panel()

    st.divider()


# =========================================================
# API 狀態
# =========================================================

with st.expander(
    "🔌 AI API 狀態",
    expanded=False,
):

    c1, c2 = st.columns(2)

    with c1:

        st.subheader(
            "🤖 Gemini"
        )

        if genai is None:

            st.error(
                "google-genai 未安裝"
            )

        elif get_gemini_api_key():

            st.success(
                "Gemini API 已設定"
            )

        else:

            st.warning(
                "Gemini API Key 未設定"
            )

    with c2:

        st.subheader(
            "🎬 Kling"
        )

        if get_kling_api_key():

            st.success(
                "Kling API 已設定"
            )

            st.write(
                "模型："
                f"`{KLING_MODEL_NAME}`"
            )

            st.write(
                "解析度："
                f"`{KLING_DEFAULT_RESOLUTION}`"
            )

            st.write(
                "影片："
                f"`{KLING_DEFAULT_DURATION} 秒`"
            )

            st.write(
                "比例："
                f"`{KLING_DEFAULT_ASPECT_RATIO}`"
            )

        else:

            st.error(
                "Kling API Key 未設定"
            )


# =========================================================
# 1 商品圖片
# =========================================================

st.subheader(
    "1｜📷 商品圖片"
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


if uploaded_file:

    try:

        (
            prepared_image,
            prepared_image_bytes,
        ) = prepare_image(
            uploaded_file
        )

        st.success(
            "✅ 商品圖片已讀取"
        )

        st.image(
            prepared_image,
            caption=(
                "這張圖片會直接作為 "
                "Kling 影片首幀商品來源"
            ),
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
# 2 商品資料
# =========================================================

st.subheader(
    "2｜📦 商品資料"
)

col1, col2 = st.columns(2)

with col1:

    product_name = st.text_input(
        "商品名稱",
        placeholder="可留空，AI 會從圖片判斷",
        key="product_name",
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
        height=130,
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

    "Kling AI 3.0 真生成影片",

    "分潤合規檢查",

    "完整流程",

]


selected_items = st.multiselect(

    "AI 功能",
    generate_options,

    default=auto_select_features(),

    key="selected_ai_features",

)


if (
    "完整流程"
    in selected_items
):

    st.success(
        "🤖 完整流程已自動勾選"
    )


# =========================================================
# 5 Kling 設定
# =========================================================

st.subheader(
    "5｜🎬 Kling 真生成影片設定"
)

kcol1, kcol2, kcol3 = st.columns(3)


with kcol1:

    kling_resolution = st.selectbox(
        "解析度",
        [
            "720p",
            "1080p",
        ],
        index=1,
    )


with kcol2:

    kling_duration = st.selectbox(
        "影片秒數",
        list(range(3, 16)),
        index=7,
    )


with kcol3:

    kling_aspect_ratio = st.selectbox(
        "畫面比例",
        [
            "9:16",
            "16:9",
            "1:1",
        ],
        index=0,
    )


kling_watermark = st.checkbox(
    "Kling 生成水印",
    value=False,
)


st.info(
    "📌 商品圖片會自動作為 Kling Image-to-Video 的首幀。"
)


# =========================================================
# 6 啟動 AI
# =========================================================

st.subheader(
    "6｜🚀 開始 AI 分析"
)

if st.button(
    "🚀 啟動 Gemini＋Kling 真生成影片",
    type="primary",
    use_container_width=True,
    key="start_real_ai",
):

    if not prepared_image_bytes:

        st.error(
            "❌ 請先上傳商品圖片。"
        )

    elif not get_kling_api_key():

        st.error(
            "❌ 找不到 KLING_API_KEY。"
        )

        st.code(
            'KLING_API_KEY = "你的 Kling API Key"'
        )

    else:

        # =================================================
        # 自動 AI 分析
        # =================================================

        product_data = {

            "商品名稱":
                product_name,

            "商品價格":
                product_price,

            "商品成本":
                product_cost,

            "分潤比例":
                commission_rate,

            "月銷量":
                monthly_sales,

            "商品評分":
                product_rating,

            "商品連結":
                product_url,

            "商品規格":
                product_spec,

            "目標平台":
                target_platform,

        }


        # =================================================
        # Gemini
        # =================================================

        if get_gemini_api_key():

            gemini_prompt = f"""
你是 AI 蝦皮半自動化 2.5 PRO 商品分析 AI。

請分析使用者提供的商品圖片。

商品名稱：
{product_name or "待辨識"}

商品價格：
{product_price or "待確認"}

商品規格：
{product_spec or "待確認"}

平台：
{target_platform}

請輸出：

1. 商品辨識
2. AI 選品分析
3. 蝦皮商品標題 3 組
4. 蝦皮商品描述
5. TikTok 15 秒文案
6. 商品特色
7. 合規風險
8. Kling 3.0 Turbo 影片 Prompt

禁止虛構：
品牌、規格、價格、成分、產地、
功效、醫療效果、認證、贈品。

如果無法確認：
請寫「待人工確認」。

Kling 影片必須：
9:16
10 seconds
1080p
premium commercial product video
same product identity
same packaging
same logo
same label
same color
same proportions
no people
no hands
no second product
no deformation
no fake claims

{KLING_PRODUCT_RULES}
"""

            with st.spinner(
                "🧠 Gemini 正在分析商品圖片……"
            ):

                try:

                    result = call_gemini(
                        prompt=gemini_prompt,
                        image_bytes=(
                            prepared_image_bytes
                        ),
                        mime_type="image/jpeg",
                    )

                    st.session_state.analysis_result = (
                        result
                    )

                    st.session_state.analysis_mode = (
                        "Gemini｜商品圖片＋文字"
                    )

                    st.success(
                        "✅ Gemini 商品分析完成"
                    )

                except Exception as error:

                    st.warning(
                        "⚠️ Gemini 分析失敗，"
                        "但仍可以直接使用 Kling 生成影片。"
                    )

                    st.code(
                        str(error)
                    )

        else:

            st.info(
                "ℹ️ 未設定 Gemini API，"
                "直接使用 Kling 自動生成影片 Prompt。"
            )


        # =================================================
        # Kling Prompt
        # =================================================

        kling_prompt = build_kling_prompt(
            product_name=product_name,
            product_spec=product_spec,
            target_platform=target_platform,
        )

        st.session_state.kling_prompt = (
            kling_prompt
        )


        # =================================================
        # Kling 真生成
        # =================================================

        try:

            (
                video_bytes,
                video_url,
            ) = generate_real_kling_video(

                image_bytes=
                    prepared_image_bytes,

                product_name=
                    product_name,

                product_spec=
                    product_spec,

                target_platform=
                    target_platform,

                resolution=
                    kling_resolution,

                duration=
                    kling_duration,

                aspect_ratio=
                    kling_aspect_ratio,

                watermark=
                    kling_watermark,

            )

            st.balloons()

            st.success(
                "🎉 Kling 已真正生成影片！"
            )

        except Exception as error:

            st.error(
                "❌ Kling 真影片生成失敗"
            )

            st.code(
                str(error)
            )


# =========================================================
# Gemini 結果
# =========================================================

if st.session_state.analysis_result:

    st.divider()

    st.subheader(
        "📊 Gemini AI 分析結果"
    )

    if st.session_state.gemini_model:

        st.success(
            "Gemini 模型："
            + st.session_state.gemini_model
        )

    st.markdown(
        '<div class="result-box">',
        unsafe_allow_html=True,
    )

    st.markdown(
        st.session_state.analysis_result
    )

    st.markdown(
        "</div>",
        unsafe_allow_html=True,
    )

    st.download_button(
        "⬇️ 下載 Gemini 分析",
        data=(
            st.session_state.analysis_result
            .encode("utf-8")
        ),
        file_name=(
            "Gemini_商品分析.txt"
        ),
        mime="text/plain",
        use_container_width=True,
    )


# =========================================================
# Kling Prompt
# =========================================================

if st.session_state.kling_prompt:

    st.divider()

    st.subheader(
        "🎬 Kling 3.0 Turbo Prompt"
    )

    st.text_area(
        "Kling Prompt",
        value=(
            st.session_state.kling_prompt
        ),
        height=500,
        key="kling_prompt_display",
    )

    st.download_button(
        "⬇️ 下載 Kling Prompt",
        data=(
            st.session_state.kling_prompt
            .encode("utf-8")
        ),
        file_name="Kling_3.0_Turbo_Prompt.txt",
        mime="text/plain",
        use_container_width=True,
    )


# =========================================================
# Kling 真生成影片
# =========================================================

st.divider()

st.markdown(
    '<div class="video-title">'
    '🎬 Kling 3.0 Turbo 真生成影片中心'
    '</div>',
    unsafe_allow_html=True,
)


if st.session_state.kling_task_id:

    st.write(
        "Kling Task ID："
        f"`{st.session_state.kling_task_id}`"
    )

    st.write(
        "目前狀態："
        f"`{st.session_state.kling_status or 'processing'}`"
    )


if st.session_state.kling_video_bytes:

    st.success(
        "🟢 Kling 真影片已生成完成"
    )

    st.video(
        st.session_state.kling_video_bytes,
        format="video/mp4",
        start_time=0,
    )

    st.caption(
        "Kling 生成影片｜MP4"
    )

    st.download_button(
        "⬇️ 下載 Kling 真生成影片",
        data=(
            st.session_state.kling_video_bytes
        ),
        file_name=(
            st.session_state.kling_video_name
            or "Kling影片.mp4"
        ),
        mime="video/mp4",
        use_container_width=True,
        key="download_kling_video",
    )

    if st.button(
        "🗑️ 清除 Kling 影片",
        use_container_width=True,
        key="clear_kling",
    ):

        clear_kling_video()

        st.rerun()

else:

    st.info(
        "目前還沒有 Kling 真生成影片。"
    )


# =========================================================
# 使用者上傳影片
# =========================================================

st.divider()

st.subheader(
    "📤 其他影片上傳 / 預覽"
)

st.caption(
    "建議優先使用 MP4。"
    "如果即夢、Kling 或其他平台下載的是 MOV / WEBM，"
    "可以嘗試上傳；若手機無法播放，"
    "請轉成 MP4（H.264/AAC）。"
)


uploaded_video = st.file_uploader(

    "上傳 MP4 / MOV / WEBM",

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
            f"✅ 影片已上傳："
            f"{uploaded_video.name}"
        )

        st.write(
            f"格式：**{mime}**"
        )

        st.write(
            f"大小：**{size_mb:.2f} MB**"
        )

        st.markdown(
            "### ▶️ 影片預覽"
        )

        st.video(
            raw,
            format=mime,
            start_time=0,
        )

        if ext == ".mp4":

            st.success(
                "🟢 MP4：手機瀏覽器最推薦。"
            )

        elif ext == ".mov":

            st.warning(
                "🟡 MOV："
                "如果手機黑屏，"
                "請轉成 MP4（H.264/AAC）。"
            )

        elif ext == ".webm":

            st.warning(
                "🟡 WEBM："
                "如果手機無法解碼，"
                "請轉成 MP4（H.264/AAC）。"
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

    except Exception as error:

        st.error(
            "❌ 影片處理失敗"
        )

        st.code(
            str(error)
        )


# =========================================================
# Session 目前影片
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
        format=(
            st.session_state.uploaded_video_mime
        ),
        start_time=0,
    )

    if st.button(
        "🗑️ 清除目前上傳影片",
        use_container_width=True,
        key="clear_manual_video",
    ):

        clear_uploaded_video()

        st.rerun()


# =========================================================
# 影片格式說明
# =========================================================

with st.expander(
    "📱 手機播放與影片格式"
):

    st.markdown(
        """
### 最推薦

**MP4**

Video：
**H.264**

Audio：
**AAC**

比例：
**9:16**

建議解析度：
**1080 × 1920**

---

### MOV

MOV 可以上傳。

但手機瀏覽器是否能播放，
取決於 MOV 裡面的實際 Video Codec。

如果：
- 黑屏
- 只有聲音
- 一直轉圈
- 無法播放

請轉成：

**MP4 / H.264 / AAC**

---

### WEBM

WEBM 也可以嘗試上傳。

如果 Android 瀏覽器不支援該影片編碼，
同樣建議轉成：

**MP4 / H.264 / AAC**

---

### Kling

Kling 真生成影片完成後，
本系統會直接取得影片，
並以 MP4 形式提供播放與下載。

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

    "商品品牌已確認",

    "商品名稱已確認",

    "商品價格已確認",

    "商品規格已確認",

    "商品庫存已確認",

    "商品連結已確認",

    "Kling 影片商品與原商品一致",

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


st.progress(
    progress
)


st.write(
    f"完成："
    f"**{checked}/{len(check_items)}**"
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
# 系統狀態
# =========================================================

with st.expander(
    "⚙️ 系統功能"
):

    st.success(
        "✅ 商品圖片上傳"
    )

    st.success(
        "✅ Gemini 商品圖片分析"
    )

    st.success(
        "✅ AI 商品選品"
    )

    st.success(
        "✅ 蝦皮文案"
    )

    st.success(
        "✅ TikTok 文案"
    )

    st.success(
        "✅ Kling 3.0 Turbo"
    )

    st.success(
        "✅ Image-to-Video"
    )

    st.success(
        "✅ 真正 API 生成影片"
    )

    st.success(
        "✅ Kling Task ID"
    )

    st.success(
        "✅ 自動查詢生成狀態"
    )

    st.success(
        "✅ 自動取得生成影片"
    )

    st.success(
        "✅ 自動播放"
    )

    st.success(
        "✅ MP4"
    )

    st.success(
        "✅ MOV"
    )

    st.success(
        "✅ WEBM"
    )

    st.success(
        "✅ 手機播放提示"
    )

    st.success(
        "✅ Session 防止影片重複處理"
    )

    st.success(
        "✅ 會員系統"
    )

    st.success(
        "✅ 管理員"
    )

    st.success(
        "✅ 會員到期"
    )

    st.info(
        "Gemini 負責商品理解與 Prompt；"
        "Kling 負責真正生成影片。"
    )


# =========================================================
# Footer
# =========================================================

st.divider()

st.caption(
    "AI 蝦皮半自動化 2.5 PRO｜"
    "Gemini AI｜"
    "Kling 3.0 Turbo｜"
    "Image-to-Video｜"
    "真生成影片｜"
    "MP4 / MOV / WEBM｜"
    "正式發布前必須人工確認。"
)
