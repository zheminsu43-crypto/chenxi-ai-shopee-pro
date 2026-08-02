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
# AI 蝦皮半自動化 2.5 PRO
# 本機無 API 版本
#
# 不需要：
# Google API
# LINE API
# WeChat API
# Supabase
# Gemini API
#
# 會員資料：data/members.json
# AI：本機規則 + Prompt 生成模式
# =========================================================


# =========================================================
# 網頁設定
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
# 建立資料夾
# =========================================================

os.makedirs(
    DATA_DIR,
    exist_ok=True
)


# =========================================================
# 會員資料庫
# =========================================================

def load_members():

    if not os.path.exists(
        MEMBERS_FILE
    ):
        return []

    try:

        with open(
            MEMBERS_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if isinstance(
            data,
            list
        ):
            return data

    except Exception:
        pass

    return []


def save_members(
    members
):

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

def hash_password(
    password
):

    salt = secrets.token_hex(16)

    digest = hashlib.sha256(
        (
            salt + password
        ).encode("utf-8")
    ).hexdigest()

    return (
        f"{salt}${digest}"
    )


def verify_password(
    password,
    saved_value
):

    try:

        salt, saved_hash = (
            saved_value.split(
                "$",
                1
            )
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

        if (
            member.get(
                "username"
            )
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

        "expires":
        (
            date.today()
            + timedelta(
                days=3650
            )
        ).isoformat(),

        "created_at":
        datetime.now().isoformat()

    }

    members.append(
        admin
    )

    save_members(
        members
    )


ensure_admin()


# =========================================================
# 會員查詢
# =========================================================

def find_member(
    username
):

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


def find_member_by_email(
    email
):

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

    if find_member(
        username
    ):

        return (
            False,
            "帳號已存在。"
        )

    if (
        email
        and find_member_by_email(
            email
        )
    ):

        return (
            False,
            "Email 已註冊。"
        )

    expires = (
        date.today()
        + timedelta(
            days=DEFAULT_MEMBER_DAYS
        )
    ).isoformat()

    member = {

        "id":
        secrets.token_hex(8),

        "username":
        username,

        "password_hash":
        hash_password(
            password
        ),

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

    members.append(
        member
    )

    save_members(
        members
    )

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

        if (
            member.get(
                "id"
            )
            == member_id
        ):

            member.update(
                updates
            )

            save_members(
                members
            )

            return True

    return False


# =========================================================
# 登入
# =========================================================

def check_login(
    username,
    password
):

    member = find_member(
        username
    )

    if not member:

        return (
            False,
            "invalid"
        )

    status = str(
        member.get(
            "status",
            "active"
        )
    ).lower()

    if status != "active":

        return (
            False,
            "disabled"
        )

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

        return (
            False,
            "invalid"
        )

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

        return (
            False,
            "invalid_date"
        )

    if date.today() > expires_date:

        return (
            False,
            "expired"
        )

    return (
        True,
        member
    )


# =========================================================
# Session
# =========================================================

if "logged_in" not in st.session_state:

    st.session_state.logged_in = False


if "page" not in st.session_state:

    st.session_state.page = "login"


if "analysis_result" not in st.session_state:

    st.session_state.analysis_result = ""


if "analysis_mode" not in st.session_state:

    st.session_state.analysis_mode = ""


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

    st.session_state.page = "login"

    st.rerun()


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

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# 登入頁
# =========================================================

def login_page():

    st.markdown(
        '<div class="main-title">'
        '🛒 AI 蝦皮半自動化 2.5 PRO'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="main-subtitle">'
        '會員登入｜AI 商品分析｜即夢 AI 2.5'
        '</div>',
        unsafe_allow_html=True
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
            placeholder="輸入會員帳號",
            key="login_username"
        )

        password = st.text_input(
            "會員密碼",
            type="password",
            placeholder="輸入會員密碼",
            key="login_password"
        )

        if st.button(
            "🚀 登入系統",
            type="primary",
            use_container_width=True
        ):

            if (
                not username
                or not password
            ):

                st.error(
                    "請輸入會員帳號與密碼。"
                )

            else:

                success, result = check_login(
                    username,
                    password
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

                    messages = {

                        "expired":
                        "⛔ 會員資格已到期，請聯絡管理員續期。",

                        "disabled":
                        "⛔ 此會員帳號目前已停權。",

                        "invalid_date":
                        "⛔ 會員到期日資料錯誤。",

                        "invalid":
                        "❌ 帳號或密碼錯誤。"

                    }

                    st.error(
                        messages.get(
                            result,
                            "❌ 登入失敗。"
                        )
                    )

        st.divider()

        if st.button(
            "📝 還沒有帳號？註冊會員",
            use_container_width=True
        ):

            st.session_state.page = "register"

            st.rerun()

        st.divider()

        st.caption(
            "本系統目前使用本機會員帳號＋密碼登入。"
        )

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
        '📝 會員註冊'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="main-subtitle">'
        '建立 AI 蝦皮半自動化 2.5 PRO 會員帳號'
        '</div>',
        unsafe_allow_html=True
    )

    _, center, _ = st.columns(
        [1, 2, 1]
    )

    with center:

        st.subheader(
            "👤 建立會員帳號"
        )

        name = st.text_input(
            "姓名 / 暱稱",
            placeholder="例如：王小明"
        )

        email = st.text_input(
            "Email",
            placeholder="例如：example@gmail.com"
        )

        username = st.text_input(
            "會員帳號",
            placeholder="3～30 個英數字或底線"
        )

        password = st.text_input(
            "會員密碼",
            type="password",
            placeholder="至少 6 個字元"
        )

        password_confirm = st.text_input(
            "再次輸入密碼",
            type="password"
        )

        if st.button(
            "🚀 建立會員帳號",
            type="primary",
            use_container_width=True
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
                    "請輸入姓名或暱稱。"
                )

            elif not re.fullmatch(
                r"[^@\s]+@[^@\s]+\.[^@\s]+",
                email_clean
            ):

                st.error(
                    "請輸入正確 Email。"
                )

            elif not re.fullmatch(
                r"[a-z0-9_]{3,30}",
                username_clean
            ):

                st.error(
                    "帳號只能使用小寫英數字與底線，長度 3～30。"
                )

            elif len(password) < 6:

                st.error(
                    "密碼至少需要 6 個字元。"
                )

            elif password != password_confirm:

                st.error(
                    "兩次輸入的密碼不一致。"
                )

            else:

                success, result = create_member(
                    username_clean,
                    password,
                    name,
                    email_clean
                )

                if success:

                    st.success(
                        "🎉 會員帳號建立成功！"
                    )

                    st.info(
                        f"會員資格預設 {DEFAULT_MEMBER_DAYS} 天，"
                        "請返回登入。"
                    )

                else:

                    st.error(
                        str(result)
                    )

        st.divider()

        if st.button(
            "⬅️ 返回登入",
            use_container_width=True
        ):

            st.session_state.page = "login"

            st.rerun()


# =========================================================
# 登入判斷
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
# 會員資料
# =========================================================

current_username = st.session_state.get(
    "username",
    ""
)

current_member = st.session_state.get(
    "member",
    {}
)

latest_member = find_member(
    current_username
)

if latest_member:

    current_member = latest_member

    st.session_state.member = (
        latest_member
    )


member_id = current_member.get(
    "id",
    ""
)

member_name = str(
    current_member.get(
        "name",
        current_username
    )
)

member_email = str(
    current_member.get(
        "email",
        ""
    )
)

member_role = str(
    current_member.get(
        "role",
        "member"
    )
)

member_status = str(
    current_member.get(
        "status",
        "active"
    )
)

member_expires = str(
    current_member.get(
        "expires",
        ""
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


if (
    member_status.lower()
    != "active"
):

    st.error(
        "⛔ 此會員帳號目前已停權。"
    )

    if st.button(
        "🚪 返回登入"
