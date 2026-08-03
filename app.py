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
# Streamlit 手機優化版
#
# 核心：
# 1. 沒有 OpenClaw Key / Token 也能開網站
# 2. 有 OpenClaw Gateway 後自動啟用
# 3. OpenClaw 負責 video_generate
# 4. OpenClaw 自動選影片 Provider
# 5. Provider 失敗可自動 fallback
# 6. 商品圖片作為 Image-to-Video 參考圖
# 7. 會員永久期限
# 8. MP4 / MOV / WEBM
# 9. Session 防止影片重複處理
# 10. 手機播放提示
# 11. Streamlit 重新啟動後頂部標題不被遮住
# 12. 手機版自動縮小標題
#
# 注意：
# OpenClaw 本身不是免費無限影片額度。
# 真生成影片仍須至少有一個可用影片 Provider。
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
# OpenClaw 設定
# =========================================================

OPENCLAW_URL = os.getenv(
    "OPENCLAW_GATEWAY_URL",
    "",
).strip().rstrip("/")

OPENCLAW_TOKEN = os.getenv(
    "OPENCLAW_GATEWAY_TOKEN",
    "",
).strip()


# =========================================================
# 圖片 / 影片限制
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
# 永久會員
# =========================================================

PERMANENT_MEMBER = True

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


# =========================================================
# CSS
# =========================================================
#
# 重要：
# Streamlit 手機 / 重新啟動後，
# 最上方標題有時會因為 block-container 的預設 padding
# 太小而被頂部區域遮住。
#
# 這裡直接增加頂部空間。
# 同時加入手機版 CSS。
# =========================================================

st.markdown(
    """
    <style>

    /* =====================================================
       Streamlit 主內容區
       防止重新整理 / 重新啟動後標題貼住最上方
       ===================================================== */

    .block-container {
        padding-top: 4rem !important;
        padding-bottom: 3rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }


    /* =====================================================
       主標題
       ===================================================== */

    .main-title {
        text-align: center;
        font-size: 38px;
        font-weight: 900;

        margin-top: 10px !important;
        margin-bottom: 12px !important;

        line-height: 1.25;

        word-break: break-word;
    }


    /* =====================================================
       副標題
       ===================================================== */

    .main-subtitle {
        text-align: center;

        font-size: 17px;

        opacity: 0.75;

        margin-bottom: 30px;

        line-height: 1.5;

        word-break: break-word;
    }


    /* =====================================================
       結果區
       ===================================================== */

    .result-box {
        padding: 20px;
        border-radius: 14px;

        border: 1px solid rgba(128,128,128,.25);

        margin-bottom: 20px;
    }


    /* =====================================================
       影片標題
       ===================================================== */

    .video-title {
        font-size: 28px;
        font-weight: 800;

        margin-top: 10px;
        margin-bottom: 10px;

        line-height: 1.3;
    }


    /* =====================================================
       小提示
       ===================================================== */

    .small-note {
        opacity: .75;
        font-size: 14px;
    }


    /* =====================================================
       Streamlit 按鈕
       ===================================================== */

    div.stButton > button {
        min-height: 44px;
        border-radius: 10px;
    }


    /* =====================================================
       手機版
       ===================================================== */

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

            line-height: 1.3;

        }


        .result-box {

            padding: 14px;

        }

    }


    /* =====================================================
       更小手機
       ===================================================== */

    @media (max-width: 480px) {

        .block-container {

            padding-top: 3rem !important;

            padding-left: 0.8rem !important;

            padding-right: 0.8rem !important;

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
# 會員
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

        salt, saved_hash = (
            saved_value.split(
                "$",
                1,
            )
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

        "id":
            secrets.token_hex(8),

        "username":
            ADMIN_USERNAME,

        "password_hash":
            hash_password(
                ADMIN_PASSWORD
            ),

        "name":
            "系統管理員",

        "email":
            "",

        "role":
            "admin",

        "status":
            "active",

        "permanent":
            True,

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
# 建立永久會員
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

        return (
            False,
            "帳號已存在。",
        )

    if email and find_member_by_email(
        email
    ):

        return (
            False,
            "Email 已註冊。",
        )

    member = {

        "id":
            secrets.token_hex(8),

        "username":
            username,

        "password_hash":
            hash_password(password),

        "name":
            str(name).strip(),

        "email":
            email,

        "role":
            "member",

        "status":
            "active",

        "permanent":
            True,

        "created_at":
            datetime.now().isoformat(),

    }

    members = load_members()

    members.append(member)

    save_members(members)

    return (
        True,
        member,
    )


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

    member = find_member(
        username
    )

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

    return (
        True,
        member,
    )


# =========================================================
# Session
# =========================================================

DEFAULT_SESSION_VALUES = {

    "logged_in":
        False,

    "page":
        "login",

    "username":
        "",

    "member":
        {},

    "analysis_result":
        "",

    "gemini_error":
        "",

    "kling_prompt":
        "",

    "openclaw_status":
        "",

    "openclaw_last_response":
        "",

    "video_task_id":
        "",

    "video_status":
        "",

    "video_url":
        "",

    "video_bytes":
        None,

    "video_name":
        "",

    "video_mime":
        "video/mp4",

    "video_signature":
        "",

    "uploaded_video_bytes":
        None,

    "uploaded_video_name":
        "",

    "uploaded_video_mime":
        "video/mp4",

    "uploaded_video_signature":
        "",

}


for key, value in (
    DEFAULT_SESSION_VALUES.items()
):

    if key not in st.session_state:

        st.session_state[key] = value


# =========================================================
# 登出
# =========================================================

def logout():

    for key, value in (
        DEFAULT_SESSION_VALUES.items()
    ):

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

    return str(
        value
    ).strip()


def get_openclaw_url():

    return get_setting(
        "OPENCLAW_GATEWAY_URL"
    ).rstrip("/")


def get_openclaw_token():

    return get_setting(
        "OPENCLAW_GATEWAY_TOKEN"
    )


# =========================================================
# OpenClaw 是否可用
# =========================================================

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

    if not token:

        return {
            "Content-Type":
                "application/json"
        }

    return {

        "Content-Type":
            "application/json",

        "Authorization":
            f"Bearer {token}",

    }


# =========================================================
# OpenClaw 工具呼叫
# =========================================================

def openclaw_invoke(
    tool_name,
    args,
    timeout=300,
):

    gateway_url = (
        get_openclaw_url()
    )

    if not gateway_url:

        raise RuntimeError(
            "尚未設定 "
            "OPENCLAW_GATEWAY_URL。"
        )

    url = (
        gateway_url
        + "/tools/invoke"
    )

    payload = {

        "tool":
            tool_name,

        "args":
            args,

    }

    response = requests.post(

        url,

        headers=
            openclaw_headers(),

        json=
            payload,

        timeout=
            timeout,

    )

    if response.status_code >= 400:

        raise RuntimeError(
            "OpenClaw Gateway 呼叫失敗\n\n"
            f"HTTP：{response.status_code}\n\n"
            f"{response.text}"
        )

    try:

        return response.json()

    except Exception:

        return {
            "raw":
                response.text
        }


# =========================================================
# OpenClaw 狀態
# =========================================================

def check_openclaw():

    if not openclaw_is_configured():

        return {
            "available":
                False,

            "message":
                "尚未設定 OpenClaw Gateway",

        }

    try:

        result = openclaw_invoke(
            "video_generate",
            {
                "action":
                    "list"
            },
            timeout=30,
        )

        return {

            "available":
                True,

            "message":
                "OpenClaw 已連線",

            "data":
                result,

        }

    except Exception as error:

        return {

            "available":
                False,

            "message":
                str(error),

        }


# =========================================================
# 圖片處理
# =========================================================

def prepare_image(
    uploaded_file,
):

    if uploaded_file is None:

        raise ValueError(
            "沒有收到圖片。"
        )

    raw_bytes = (
        uploaded_file.getvalue()
    )

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
            io.BytesIO(
                raw_bytes
            )
        )

        image = (
            ImageOps
            .exif_transpose(
                image
            )
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

            mask=
                image.getchannel(
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
# Base64 圖片
# =========================================================

def image_to_data_url(
    image_bytes,
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
# 商品影片 Prompt
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

    return f"""
Create a premium commercial product advertisement.

PRODUCT:
{product_name}

SPECIFICATION:
{product_spec}

TARGET:
{target_platform}

DURATION:
{duration} seconds.

FORMAT:
Vertical 9:16 social commerce video.

Use the supplied product image as the
primary visual reference.

SCENE:

Start with a clean hero shot of the exact
uploaded product.

The camera slowly pushes toward the product.

Reveal realistic material details,
packaging details, logo and label.

Use subtle cinematic camera movement.

Maintain exact product identity throughout.

Finish with a stable premium hero shot.

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
No aggressive camera shake.

PRODUCT CONSISTENCY:

Same product.
Same packaging.
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
# OpenClaw 真影片生成
# =========================================================

def openclaw_generate_video(
    image_bytes,
    prompt,
    duration,
    model="",
):

    if not openclaw_is_configured():

        raise RuntimeError(
            "OpenClaw 尚未設定。\n\n"
            "網站本身仍可正常使用，"
            "但目前無法進行真影片生成。"
        )

    image_data_url = (
        image_to_data_url(
            image_bytes
        )
    )

    args = {

        "action":
            "generate",

        "prompt":
            prompt,

        "image":
            image_data_url,

        "imageRoles":
            [
                "first_frame"
            ],

        "duration":
            duration,

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
# 遞迴尋找 Task ID
# =========================================================

def recursive_find_task_id(
    obj,
):

    keys = [

        "task_id",

        "taskId",

        "id",

        "job_id",

        "jobId",

    ]

    if isinstance(
        obj,
        dict,
    ):

        for key in keys:

            value = obj.get(
                key
            )

            if value is not None:

                text = str(
                    value
                )

                if text:

                    return text

        for value in obj.values():

            result = (
                recursive_find_task_id(
                    value
                )
            )

            if result:

                return result

    elif isinstance(
        obj,
        list,
    ):

        for item in obj:

            result = (
                recursive_find_task_id(
                    item
                )
            )

            if result:

                return result

    return ""


# =========================================================
# 遞迴找影片 URL
# =========================================================

def recursive_find_video_url(
    obj,
):

    if isinstance(
        obj,
        dict,
    ):

        preferred = [

            "video_url",

            "videoUrl",

            "download_url",

            "downloadUrl",

            "media_url",

            "mediaUrl",

        ]

        for key in preferred:

            value = obj.get(
                key
            )

            if (
                isinstance(
                    value,
                    str,
                )
                and value.startswith(
                    "http"
                )
            ):

                return value

        for key, value in (
            obj.items()
        ):

            if (
                isinstance(
                    value,
                    str,
                )
                and value.startswith(
                    "http"
                )
            ):

                lower = (
                    value.lower()
                )

                if (
                    ".mp4" in lower
                    or "video" in lower
                ):

                    return value

        for value in obj.values():

            result = (
                recursive_find_video_url(
                    value
                )
            )

            if result:

                return result

    elif isinstance(
        obj,
        list,
    ):

        for item in obj:

            result = (
                recursive_find_video_url(
                    item
                )
            )

            if result:

                return result

    return ""


# =========================================================
# 遞迴找狀態
# =========================================================

def recursive_find_status(
    obj,
):

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

    if isinstance(
        obj,
        dict,
    ):

        for key in keys:

            value = obj.get(
                key
            )

            if isinstance(
                value,
                str,
            ):

                value = (
                    value
                    .strip()
                    .lower()
                )

                if value in valid:

                    return value

        for value in obj.values():

            result = (
                recursive_find_status(
                    value
                )
            )

            if result:

                return result

    elif isinstance(
        obj,
        list,
    ):

        for item in obj:

            result = (
                recursive_find_status(
                    item
                )
            )

            if result:

                return result

    return ""


# =========================================================
# 從 OpenClaw 回應取得影片
# =========================================================

def process_openclaw_video_result(
    result,
):

    video_url = (
        recursive_find_video_url(
            result
        )
    )

    if video_url:

        return {
            "status":
                "completed",

            "video_url":
                video_url,

            "raw":
                result,
        }

    task_id = (
        recursive_find_task_id(
            result
        )
    )

    status = (
        recursive_find_status(
            result
        )
    )

    return {

        "status":
            status
            or "submitted",

        "task_id":
            task_id,

        "raw":
            result,

    }


# =========================================================
# 下載影片
# =========================================================

def download_video(
    video_url,
):

    response = requests.get(

        video_url,

        timeout=180,

    )

    if response.status_code >= 400:

        raise RuntimeError(

            "影片下載失敗。\n\n"

            f"HTTP：{response.status_code}"

        )

    if not response.content:

        raise RuntimeError(
            "影片內容為空。"
        )

    return response.content


# =========================================================
# 查詢 OpenClaw video_generate 狀態
# =========================================================

def openclaw_video_status():

    result = openclaw_invoke(

        "video_generate",

        {
            "action":
                "status"
        },

        timeout=60,

    )

    return result


# =========================================================
# 嘗試自動取得影片
# =========================================================

def try_get_video_from_result(
    result,
):

    video_url = (
        recursive_find_video_url(
            result
        )
    )

    if not video_url:

        return False

    try:

        raw = download_video(
            video_url
        )

    except Exception as error:

        st.warning(
            f"找到影片 URL，但下載失敗：{error}"
        )

        st.session_state.video_url = (
            video_url
        )

        return False

    st.session_state.video_url = (
        video_url
    )

    st.session_state.video_bytes = (
        raw
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
# 手動查詢影片
# =========================================================

def check_video_status():

    if not openclaw_is_configured():

        raise RuntimeError(
            "OpenClaw 尚未設定。"
        )

    result = (
        openclaw_video_status()
    )

    st.session_state.openclaw_last_response = (
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )

    if try_get_video_from_result(
        result
    ):

        return result

    status = (
        recursive_find_status(
            result
        )
    )

    st.session_state.video_status = (
        status
        or "processing"
    )

    return result


# =========================================================
# 清除生成影片
# =========================================================

def clear_generated_video():

    st.session_state.video_task_id = ""
    st.session_state.video_status = ""
    st.session_state.video_url = ""
    st.session_state.video_bytes = None
    st.session_state.video_name = ""
    st.session_state.video_signature = ""


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
# 儲存手動上傳影片
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

    return (
        raw,
        mime,
        ext,
        size_mb,
    )


# =========================================================
# 清除上傳影片
# =========================================================

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
        'OpenClaw 龍蝦｜多 Provider｜真影片生成'
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

                    st.session_state.logged_in = True

                    st.session_state.username = (
                        username
                        .strip()
                        .lower()
                    )

                    st.session_state.member = result

                    st.session_state.page = "main"

                    st.rerun()

                else:

                    messages = {

                        "disabled":
                            "⛔ 帳號已停權。",

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
            "📝 註冊永久會員",
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
        '📝 永久會員註冊'
        '</div>',
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns(
        [1, 2, 1]
    )

    with center:

        st.success(
            "會員期限：永久"
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
                        "🎉 永久會員建立成功！"
                    )

                    st.info(
                        "會員期限：永久"
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
# 目前會員
# =========================================================

current_username = (
    st.session_state.username
)

current_member = (
    find_member(
        current_username
    )
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
            "🟢 OpenClaw 已設定"
        )

    else:

        st.warning(
            "🟡 OpenClaw 尚未設定"
        )

        st.caption(
            "網站仍可正常使用。"
        )

    st.divider()

    if st.button(
        "🚪 登出",
        use_container_width=True,
    ):

        logout()


# =========================================================
# 標題
# =========================================================

st.markdown(
    '<div class="main-title">'
    '🦞 AI 蝦皮半自動化 2.5 PRO'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-subtitle">'
    'OpenClaw 龍蝦｜AI 商品分析｜'
    '多 Provider 自動切換｜'
    'Image-to-Video｜永久會員'
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

    st.info(
        "🟡 OpenClaw 尚未連接。"
        "\n\n"
        "網站可以正常使用。"
        "\n\n"
        "設定 Gateway URL + Token 後，"
        "即可啟用真影片生成。"
    )

else:

    status_col1, status_col2 = (
        st.columns(2)
    )

    with status_col1:

        st.success(
            "🟢 OpenClaw Gateway 已設定"
        )

    with status_col2:

        if st.button(
            "🔄 測試 OpenClaw",
            use_container_width=True,
        ):

            with st.spinner(
                "正在連接 OpenClaw..."
            ):

                result = (
                    check_openclaw()
                )

            if result.get(
                "available"
            ):

                st.success(
                    "🎉 OpenClaw 連線成功"
                )

            else:

                st.error(
                    "OpenClaw 連線失敗"
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
# API 設定
# =========================================================

with st.expander(
    "⚙️ OpenClaw 設定",
    expanded=False,
):

    st.write(
        "這裡不需要把 Provider API Key 寫死在程式碼。"
    )

    st.write(
        "Provider Key 應該設定在 OpenClaw Gateway 那邊。"
    )

    st.code(
        "OPENCLAW_GATEWAY_URL\n"
        "OPENCLAW_GATEWAY_TOKEN"
    )

    if openclaw_is_configured():

        st.success(
            "OpenClaw Gateway 設定完整。"
        )

    else:

        st.warning(
            "目前沒有 OpenClaw Gateway 設定。"
        )


# =========================================================
# 商品圖片
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

            caption=
                "這張圖片會作為影片生成參考圖",

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
# 商品資料
# =========================================================

st.subheader(
    "2｜📦 商品資料"
)

col1, col2 = st.columns(2)

with col1:

    product_name = st.text_input(
        "商品名稱",
        placeholder=
            "可留空",
    )

    product_price = st.text_input(
        "商品價格",
        placeholder=
            "例如：399",
    )

    product_cost = st.text_input(
        "商品成本",
        placeholder=
            "例如：250",
    )

    commission_rate = st.text_input(
        "分潤比例",
        placeholder=
            "例如：12%",
    )


with col2:

    monthly_sales = st.text_input(
        "月銷量",
        placeholder=
            "例如：1500",
    )

    product_rating = st.text_input(
        "商品評分",
        placeholder=
            "例如：4.8",
    )

    product_url = st.text_input(
        "商品連結",
        placeholder=
            "可留空",
    )

    product_spec = st.text_area(
        "商品規格",
        placeholder=
            "可留空",
        height=130,
    )


# =========================================================
# 平台
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
# AI 功能
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
# 影片設定
# =========================================================

st.subheader(
    "5｜🎬 真生成影片設定"
)

vcol1, vcol2, vcol3 = (
    st.columns(3)
)

with vcol1:

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


with vcol2:

    video_ratio = st.selectbox(

        "比例",

        [
            "9:16",
            "16:9",
            "1:1",
        ],

        index=0,

    )


with vcol3:

    video_model = st.text_input(

        "指定 Provider / Model（可留空）",

        placeholder=
            "留空＝OpenClaw 自動選擇",

    )


st.info(
    "💡 Model 留空時，由 OpenClaw 依照可用 Provider 與 fallback 設定自動選擇。"
)


# =========================================================
# Prompt 預覽
# =========================================================

kling_prompt = build_video_prompt(

    product_name=
        product_name,

    product_spec=
        product_spec,

    target_platform=
        target_platform,

    duration=
        video_duration,

)

st.session_state.kling_prompt = (
    kling_prompt
)


with st.expander(
    "🎬 查看影片 Prompt"
):

    st.text_area(

        "Video Prompt",

        value=
            kling_prompt,

        height=450,

    )


# =========================================================
# 啟動真生成
# =========================================================

st.subheader(
    "6｜🚀 啟動 AI"
)

if st.button(

    "🦞🚀 啟動 OpenClaw 真生成影片",

    type="primary",

    use_container_width=True,

    key="start_openclaw_video",

):

    if not prepared_image_bytes:

        st.error(
            "❌ 請先上傳商品圖片。"
        )

    elif not openclaw_is_configured():

        st.warning(
            "🟡 OpenClaw 尚未設定。"
        )

        st.info(
            "網站本身正常。"
            "\n\n"
            "設定 OpenClaw Gateway 後，"
            "這個按鈕才會真正提交影片生成。"
        )

    else:

        with st.spinner(
            "🦞 OpenClaw 正在提交真影片生成任務..."
        ):

            try:

                result = (
                    openclaw_generate_video(

                        image_bytes=
                            prepared_image_bytes,

                        prompt=
                            kling_prompt,

                        duration=
                            video_duration,

                        model=
                            video_model.strip(),

                    )
                )

                processed = (
                    process_openclaw_video_result(
                        result
                    )
                )

                status = (
                    processed.get(
                        "status",
                        "submitted",
                    )
                )

                st.session_state.video_status = (
                    status
                )

                task_id = (
                    processed.get(
                        "task_id",
                        "",
                    )
                )

                if task_id:

                    st.session_state.video_task_id = (
                        task_id
                    )

                if processed.get(
                    "video_url"
                ):

                    success = (
                        try_get_video_from_result(
                            result
                        )
                    )

                    if success:

                        st.balloons()

                        st.success(
                            "🎉 OpenClaw 真影片生成完成！"
                        )

                else:

                    st.success(
                        "✅ OpenClaw 已提交影片生成任務！"
                    )

                    if task_id:

                        st.info(
                            "Task ID："
                            + task_id
                        )

                    st.info(
                        "影片是非同步生成。"
                        "完成後可以按「查詢影片狀態」。"
                    )

            except Exception as error:

                st.error(
                    "❌ OpenClaw 真影片生成失敗"
                )

                st.code(
                    str(error)
                )


# =========================================================
# 查詢影片
# =========================================================

if (
    st.session_state.video_task_id
    or st.session_state.video_status
):

    st.divider()

    st.subheader(
        "🔄 影片任務"
    )

    c1, c2 = st.columns(2)

    with c1:

        st.write(
            "狀態："
            f"`{st.session_state.video_status or 'processing'}`"
        )

        if st.session_state.video_task_id:

            st.write(
                "Task ID："
                f"`{st.session_state.video_task_id}`"
            )

    with c2:

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
                        "正在查詢..."
                    ):

                        result = (
                            check_video_status()
                        )

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
                        "查詢失敗"
                    )

                    st.code(
                        str(error)
                    )


# =========================================================
# 真生成影片播放器
# =========================================================

st.divider()

st.markdown(

    '<div class="video-title">'
    '🎬 真生成影片中心
