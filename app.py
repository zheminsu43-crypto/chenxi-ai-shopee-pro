import io
import os
import re
import json
import hashlib
import secrets
from datetime import datetime, date, timedelta

import streamlit as st
from PIL import Image, ImageOps

# =========================================================
# Gemini SDK
# =========================================================

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


# =========================================================
# AI 蝦皮半自動化 2.5 PRO
#
# Gemini API 正式版本
#
# 特色：
# 1. Gemini API 圖片分析
# 2. 自動尋找 API Key 實際可用模型
# 3. 不再固定使用失效的 gemini-2.5-flash
# 4. 支援商品圖片上傳
# 5. AI 商品辨識
# 6. AI 選品分析
# 7. 蝦皮文案
# 8. TikTok 文案
# 9. 即夢 AI 2.5 生圖 Prompt
# 10. 即夢 AI 2.5 影片 Prompt
# 11. 分潤合規檢查
# 12. 會員登入 / 註冊 / 到期
# 13. 管理員中心
#
# =========================================================


# =========================================================
# Streamlit 設定
# =========================================================

st.set_page_config(
    page_title="AI 蝦皮半自動化 2.5 PRO",
    page_icon="🛒",
    layout="wide",
)


# =========================================================
# 系統設定
# =========================================================

APP_NAME = "AI 蝦皮半自動化 2.5 PRO"

DATA_DIR = "data"

MEMBERS_FILE = os.path.join(
    DATA_DIR,
    "members.json"
)

MAX_IMAGE_SIZE = 1600
MAX_IMAGE_MB = 20

DEFAULT_MEMBER_DAYS = 30

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


# =========================================================
# Gemini 模型優先順序
#
# 注意：
# 不再直接假設所有模型都能用。
# 系統會先呼叫 models.list()，
# 找出這把 API Key 真正可用的 generateContent 模型。
# =========================================================

GEMINI_MODEL_PRIORITY = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
]


# =========================================================
# 建立資料夾
# =========================================================

os.makedirs(
    DATA_DIR,
    exist_ok=True
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

    .gemini-ok {
        padding: 12px;
        border-radius: 10px;
        border: 1px solid rgba(0,180,100,.3);
        margin-bottom: 12px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# 會員資料庫
# =========================================================

def load_members():

    if not os.path.exists(MEMBERS_FILE):
        return []

    try:

        with open(
            MEMBERS_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if isinstance(data, list):
            return data

    except Exception:
        pass

    return []


def save_members(members):

    with open(
        MEMBERS_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            members,
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# 密碼
# =========================================================

def hash_password(password):

    salt = secrets.token_hex(16)

    digest = hashlib.sha256(
        (
            salt + password
        ).encode("utf-8")
    ).hexdigest()

    return f"{salt}${digest}"


def verify_password(
    password,
    saved_value
):

    try:

        salt, saved_hash = saved_value.split(
            "$",
            1
        )

        digest = hashlib.sha256(
            (
                salt + password
            ).encode("utf-8")
        ).hexdigest()

        return secrets.compare_digest(
            digest,
            saved_hash
        )

    except Exception:

        return False


# =========================================================
# 初始化管理員
# =========================================================

def ensure_admin():

    members = load_members()

    for member in members:

        if member.get("username") == ADMIN_USERNAME:
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

        "expires":
        (
            date.today()
            + timedelta(days=3650)
        ).isoformat(),

        "created_at":
        datetime.now().isoformat()

    }

    members.append(admin)

    save_members(members)


ensure_admin()


# =========================================================
# 會員查詢
# =========================================================

def find_member(username):

    username = (
        username
        .strip()
        .lower()
    )

    members = load_members()

    for member in members:

        if (
            member.get(
                "username",
                ""
            ).lower()
            == username
        ):

            return member

    return None


def find_member_by_email(email):

    email = (
        email
        .strip()
        .lower()
    )

    if not email:
        return None

    members = load_members()

    for member in members:

        if (
            member.get(
                "email",
                ""
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
    email
):

    username = (
        username
        .strip()
        .lower()
    )

    email = (
        email
        .strip()
        .lower()
    )

    if find_member(username):

        return (
            False,
            "帳號已存在。"
        )

    if (
        email
        and find_member_by_email(email)
    ):

        return (
            False,
            "Email 已註冊。"
        )

    expires = (
        date.today()
        + timedelta(days=DEFAULT_MEMBER_DAYS)
    ).isoformat()

    member = {

        "id":
        secrets.token_hex(8),

        "username":
        username,

        "password_hash":
        hash_password(password),

        "name":
        name.strip(),

        "email":
        email,

        "role":
        "member",

        "status":
        "active",

        "expires":
        expires,

        "created_at":
        datetime.now().isoformat()

    }

    members = load_members()

    members.append(member)

    save_members(members)

    return (
        True,
        member
    )


# =========================================================
# 更新會員
# =========================================================

def update_member(
    member_id,
    updates
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
    password
):

    member = find_member(username)

    if not member:
        return False, "invalid"

    status = str(
        member.get(
            "status",
            "active"
        )
    ).lower()

    if status != "active":
        return False, "disabled"

    saved_hash = str(
        member.get(
            "password_hash",
            ""
        )
    )

    if (
        not saved_hash
        or not verify_password(
            password,
            saved_hash
        )
    ):

        return False, "invalid"

    expires_text = str(
        member.get(
            "expires",
            ""
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
# Session 初始化
# =========================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "page" not in st.session_state:
    st.session_state.page = "login"

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = ""

if "analysis_mode" not in st.session_state:
    st.session_state.analysis_mode = ""

if "gemini_model" not in st.session_state:
    st.session_state.gemini_model = ""

if "gemini_error" not in st.session_state:
    st.session_state.gemini_error = ""

if "available_models" not in st.session_state:
    st.session_state.available_models = []

if "model_scan_error" not in st.session_state:
    st.session_state.model_scan_error = ""


# =========================================================
# 登出
# =========================================================

def logout():

    st.session_state.logged_in = False

    st.session_state.pop(
        "username",
        None
    )

    st.session_state.pop(
        "member",
        None
    )

    st.session_state.analysis_result = ""

    st.session_state.analysis_mode = ""

    st.session_state.gemini_model = ""

    st.session_state.gemini_error = ""

    st.session_state.available_models = []

    st.session_state.model_scan_error = ""

    st.session_state.page = "login"

    st.rerun()


# =========================================================
# Gemini API Key
# =================================================
