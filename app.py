import io
import os
import re
import hashlib
import secrets
from datetime import datetime, date, timedelta

import streamlit as st
from google import genai
from PIL import Image, ImageOps


# =========================================================
# AI 蝦皮半自動化 2.5 PRO
# 會員註冊 / 登入 / 期限 / 管理員
# Google / LINE / WeChat OAuth 入口
# Gemini / ChatGPT 說明
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

MODEL_CANDIDATES = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]

MAX_IMAGE_SIZE = 1600
MAX_IMAGE_MB = 20
DEFAULT_MEMBER_DAYS = 30


# =========================================================
# Secrets
# =========================================================

def secret(name, default=""):
    try:
        value = st.secrets.get(name, default)

        if value is None:
            return default

        return str(value).strip()

    except Exception:
        return default


def get_api_key():
    key = secret("GEMINI_API_KEY")

    if key:
        return key

    return None


def get_supabase_config():
    url = secret("SUPABASE_URL")
    key = secret("SUPABASE_ANON_KEY")

    if not url or not key:
        return None, None

    return url.rstrip("/"), key


def get_app_url():
    return secret("APP_URL").rstrip("/")


# =========================================================
# 密碼
# =========================================================

def hash_password(password):
    salt = secrets.token_hex(16)

    digest = hashlib.sha256(
        (salt + password).encode("utf-8")
    ).hexdigest()

    return f"{salt}${digest}"


def verify_password(password, saved_value):
    try:
        salt, saved_hash = saved_value.split("$", 1)

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
# Supabase REST
# =========================================================

def supabase_request(
    method,
    table,
    params=None,
    json_data=None,
    headers_extra=None,
):
    import requests

    url, key = get_supabase_config()

    if not url or not key:
        raise RuntimeError(
            "尚未設定 SUPABASE_URL / SUPABASE_ANON_KEY。"
        )

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    if headers_extra:
        headers.update(headers_extra)

    response = requests.request(
        method=method,
        url=f"{url}/rest/v1/{table}",
        params=params,
        json=json_data,
        headers=headers,
        timeout=20,
    )

    if not response.ok:
        raise RuntimeError(
            f"Supabase 錯誤 {response.status_code}: "
            f"{response.text}"
        )

    if not response.text:
        return []

    try:
        return response.json()

    except Exception:
        return []


# =========================================================
# 會員資料
# =========================================================

def find_member(username):
    username = username.strip().lower()

    rows = supabase_request(
        "GET",
        "members",
        params={
            "username": f"eq.{username}",
            "select": "*",
            "limit": "1",
        },
    )

    return rows[0] if rows else None


def find_member_by_email(email):
    email = email.strip().lower()

    if not email:
        return None

    rows = supabase_request(
        "GET",
        "members",
        params={
            "email": f"eq.{email}",
            "select": "*",
            "limit": "1",
        },
    )

    return rows[0] if rows else None


def find_member_by_provider(
    provider,
    provider_user_id,
):
    if not provider_user_id:
        return None

    rows = supabase_request(
        "GET",
        "members",
        params={
            "provider": f"eq.{provider}",
            "provider_user_id": f"eq.{provider_user_id}",
            "select": "*",
            "limit": "1",
        },
    )

    return rows[0] if rows else None


def create_member(
    username,
    password,
    name,
    email,
    provider="password",
    provider_user_id="",
):
    username = username.strip().lower()
    email = email.strip().lower()

    if find_member(username):
        return False, "帳號已存在。"

    if email and find_member_by_email(email):
        return False, "Email 已註冊。"

    if (
        provider != "password"
        and provider_user_id
        and find_member_by_provider(
            provider,
            provider_user_id,
        )
    ):
        return False, "此第三方帳號已註冊。"

    expires = (
        date.today()
        + timedelta(days=DEFAULT_MEMBER_DAYS)
    ).isoformat()

    data = {
        "username": username,
        "password_hash": (
            hash_password(password)
            if password
            else ""
        ),
        "name": name.strip(),
        "email": email,
        "role": "member",
        "status": "active",
        "expires": expires,
        "provider": provider,
        "provider_user_id": provider_user_id,
    }

    rows = supabase_request(
        "POST",
        "members",
        json_data=data,
        headers_extra={
            "Prefer": "return=representation"
        },
    )

    if rows:
        return True, rows[0]

    return False, "會員建立失敗。"


def update_member(member_id, updates):
    return supabase_request(
        "PATCH",
        "members",
        params={
            "id": f"eq.{member_id}"
        },
        json_data=updates,
        headers_extra={
            "Prefer": "return=representation"
        },
    )


def get_all_members():
    return supabase_request(
        "GET",
        "members",
        params={
            "select": "*",
            "order": "created_at.desc",
        },
    )


# =========================================================
# 登入
# =========================================================

def check_login(username, password):
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

    saved_hash = str(
        member.get(
            "password_hash",
            "",
        )
    )

    if (
        not saved_hash
        or not verify_password(
            password,
            saved_hash,
        )
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
# OAuth
# =========================================================

def oauth_url(provider):
    supabase_url, anon_key = get_supabase_config()

    if not supabase_url or not anon_key:
        return None

    app_url = get_app_url()

    if not app_url:
        return None

    provider_map = {
        "google": secret(
            "SUPABASE_GOOGLE_PROVIDER",
            "google",
        ),
        "line": secret(
            "SUPABASE_LINE_PROVIDER",
            "custom:line",
        ),
        "wechat": secret(
            "SUPABASE_WECHAT_PROVIDER",
            "custom:wechat",
        ),
    }

    provider_id = provider_map.get(provider)

    if not provider_id:
        return None

    return (
        f"{supabase_url}/auth/v1/authorize"
        f"?provider={provider_id}"
        f"&redirect_to={app_url}"
    )


def social_buttons():
    st.markdown(
        "### 🌐 第三方註冊 / 登入"
    )

    google_url = oauth_url("google")
    line_url = oauth_url("line")
    wechat_url = oauth_url("wechat")

    c1, c2, c3 = st.columns(3)

    with c1:
        if google_url:
            st.link_button(
                "🇬 Google 註冊 / 登入",
                google_url,
                use_container_width=True,
            )
        else:
            st.button(
                "🇬 Google（尚未設定）",
                disabled=True,
                use_container_width=True,
            )

    with c2:
        if line_url:
            st.link_button(
                "💚 LINE 註冊 / 登入",
                line_url,
                use_container_width=True,
            )
        else:
            st.button(
                "💚 LINE（尚未設定）",
                disabled=True,
                use_container_width=True,
            )

    with c3:
        if wechat_url:
            st.link_button(
                "💬 WeChat 註冊 / 登入",
                wechat_url,
                use_container_width=True,
            )
        else:
            st.button(
                "💬 WeChat（尚未設定）",
                disabled=True,
                use_container_width=True,
            )

    st.caption(
        "Google / LINE / WeChat 為第三方 OAuth 入口；"
        "ChatGPT / Gemini 本身不是直接拿來當你網站會員系統的通用 OAuth 按鈕。"
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

if "analysis_model" not in st.session_state:
    st.session_state.analysis_model = ""


def logout():
    st.session_state.logged_in = False
    st.session_state.pop(
        "username",
        None,
    )
    st.session_state.pop(
        "member",
        None,
    )

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

    .upload-box {
        padding: 12px;
        border-radius: 12px;
        border: 1px solid rgba(128,128,128,.25);
    }

    </style>
    """,
    unsafe_allow_html=True,
)


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
        '會員登入｜Google｜LINE｜WeChat｜'
        'AI 商品分析｜即夢 AI 2.5'
        '</div>',
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns(
        [1, 2, 1]
    )

    with center:

        st.subheader("🔐 會員登入")

        username = st.text_input(
            "會員帳號",
            placeholder="輸入會員帳號",
            key="login_username",
        )

        password = st.text_input(
            "會員密碼",
            type="password",
            placeholder="輸入會員密碼",
            key="login_password",
        )

        if st.button(
            "🚀 登入系統",
            type="primary",
            use_container_width=True,
        ):

            if not username or not password:
                st.error(
                    "請輸入會員帳號與密碼。"
                )

            else:

                try:

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

                    messages = {
                        "expired":
                            "⛔ 會員資格已到期，請聯絡管理員續期。",
                        "disabled":
                            "⛔ 此會員帳號目前已停權。",
                        "invalid_date":
                            "⛔ 會員到期日資料錯誤。",
                        "invalid":
                            "❌ 帳號或密碼錯誤。",
                    }

                    st.error(
                        messages.get(
                            result,
                            "❌ 登入失敗。",
                        )
                    )

                except Exception as error:

                    st.error(
                        "會員系統連線失敗。"
                    )

                    st.code(
                        str(error)
                    )

        st.divider()

        social_buttons()

        st.divider()

        if st.button(
            "📝 還沒有帳號？註冊會員",
            use_container_width=True,
        ):

            st.session_state.page = "register"

            st.rerun()


# =========================================================
# 註冊頁
# =========================================================

def register_page():

    st.markdown(
        '<div class="main-title">'
        '📝 會員註冊'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="main-subtitle">'
        '建立 AI 蝦皮半自動化 2.5 PRO 會員帳號'
        '</div>',
        unsafe_allow_html=True,
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
            placeholder="例如：王小明",
        )

        email = st.text_input(
            "Email",
            placeholder="例如：example@gmail.com",
        )

        username = st.text_input(
            "會員帳號",
            placeholder="3～30 個英數字或底線",
        )

        password = st.text_input(
            "會員密碼",
            type="password",
            placeholder="至少 6 個字元",
        )

        password_confirm = st.text_input(
            "再次輸入密碼",
            type="password",
        )

        if st.button(
            "🚀 建立會員帳號",
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
                    "請輸入姓名或暱稱。"
                )

            elif not re.fullmatch(
                r"[^@\s]+@[^@\s]+\.[^@\s]+",
                email_clean,
            ):

                st.error(
                    "請輸入正確 Email。"
                )

            elif not re.fullmatch(
                r"[a-z0-9_]{3,30}",
                username_clean,
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

                try:

                    success, result = create_member(
                        username_clean,
                        password,
                        name,
                        email_clean,
                    )

                    if success:

                        st.success(
                            "🎉 會員帳號建立成功！"
                        )

                        st.info(
                            f"會員資格預設 "
                            f"{DEFAULT_MEMBER_DAYS} 天，"
                            "請返回登入。"
                        )

                    else:

                        st.error(
                            str(result)
                        )

                except Exception as error:

                    st.error(
                        "註冊失敗。"
                    )

                    st.code(
                        str(error)
                    )

        st.divider()

        social_buttons()

        st.divider()

        if st.button(
            "⬅️ 返回登入",
            use_container_width=True,
        ):

            st.session_state.page = "login"

            st.rerun()


# =========================================================
# 尚未登入
# =========================================================

if not st.session_state.logged_in:

    if st.session_state.page == "register":
        register_page()

    else:
        login_page()

    st.stop()


# =========================================================
# 會員資料
# =========================================================

current_username = st.session_state.get(
    "username",
    "",
)

current_member = st.session_state.get(
    "member",
    {},
)

try:

    latest_member = find_member(
        current_username
    )

    if latest_member:

        current_member = latest_member

        st.session_state.member = (
            latest_member
        )

except Exception:
    pass


member_id = current_member.get(
    "id",
    "",
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
        expire_date - date.today()
    ).days

except Exception:

    remaining_days = -999


if member_status.lower() != "active":

    st.error(
        "⛔ 此會員帳號目前已停權。"
    )

    if st.button(
        "🚪 返回登入",
        type="primary",
    ):
        logout()

    st.stop()


if remaining_days < 0:

    st.error(
        "⛔ 會員資格已到期。"
    )

    st.info(
        "請聯絡管理員續期後再使用系統。"
    )

    if st.button(
        "🚪 返回登入",
        type="primary",
    ):
        logout()

    st.stop()


# =========================================================
# 側邊欄
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
        "註冊方式："
        f"**{current_member.get('provider', 'password')}**"
    )

    st.write(
        f"到期日：**{member_expires}**"
    )

    if remaining_days == 0:

        st.warning(
            "⚠️ 今天為最後使用日"
        )

    elif remaining_days <= 7:

        st.warning(
            f"⚠️ 剩餘 {remaining_days} 天"
        )

    else:

        st.info(
            f"⏳ 剩餘 {remaining_days} 天"
        )

    st.divider()

    if st.button(
        "🚪 登出",
        use_container_width=True,
    ):
        logout()


# =========================================================
# 管理員中心
# =========================================================

def admin_panel():

    st.header(
        "👑 管理員中心"
    )

    try:

        members = get_all_members()

    except Exception as error:

        st.error(
            "會員資料庫讀取失敗。"
        )

        st.code(
            str(error)
        )

        return

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

        provider = member.get(
            "provider",
            "password",
        )

        with st.expander(
            f"👤 {name}｜{username}"
        ):

            st.write(
                f"Email：**{email}**"
            )

            st.write(
                f"註冊方式：**{provider}**"
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

            try:

                expire_value = date.fromisoformat(
                    expires
                )

            except Exception:

                expire_value = date.today()

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
                            "status": new_status,
                            "role": new_role,
                            "expires": (
                                new_expire.isoformat()
                            ),
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
                        + timedelta(days=30)
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
                        f"{new_date.isoformat()}"
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
# 主標題
# =========================================================

st.markdown(
    '<div class="main-title">'
    '🛒 AI 蝦皮半自動化 2.5 PRO'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-subtitle">'
    '商品辨識｜AI 選品｜蝦皮文案｜TikTok｜'
    '即夢 AI 2.5｜分潤合規'
    '</div>',
    unsafe_allow_html=True,
)


# =========================================================
# 管理員
# =========================================================

if member_role.lower() == "admin":

    with st.expander(
        "👑 管理員中心"
    ):
        admin_panel()

    st.divider()


# =========================================================
# Gemini
# =========================================================

def prepare_image(uploaded_file):

    if uploaded_file is None:
        raise ValueError(
            "沒有收到圖片檔案。"
        )

    try:

        # 直接從 UploadedFile 讀取 bytes
        raw_bytes = uploaded_file.getvalue()

        if not raw_bytes:
            raise ValueError(
                "圖片檔案內容是空的。"
            )

        file_size_mb = (
            len(raw_bytes)
            / 1024
            / 1024
        )

        if file_size_mb > MAX_IMAGE_MB:

            raise ValueError(
                f"圖片太大，目前為 "
                f"{file_size_mb:.1f} MB，"
                f"請使用 {MAX_IMAGE_MB} MB 以下圖片。"
            )

        image = Image.open(
            io.BytesIO(raw_bytes)
        )

        image = ImageOps.exif_transpose(
            image
        )

        # 完全解碼圖片
        image.load()

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

        return image

    except Exception as error:

        raise ValueError(
            "無法讀取這張圖片。"
            "請確認是 JPG、JPEG、PNG 或 WEBP。"
            f"\n\n詳細錯誤：{error}"
        )


# =========================================================
# 即夢 AI 2.5 核心規則
# =========================================================

JIMENG_25_CORE_RULES = """

【即夢 AI 2.5 商品一致性核心規則】

使用者上傳的商品圖片是主要商品來源。

必須維持：

- 商品原本品牌
- 包裝
- 形狀
- 比例
- 顏色
- 材質
- Logo
- 標籤
- 印刷文字
- 包裝結構

禁止：

- 重新設計品牌
- 重新設計包裝
- 改變顏色
- 改變瓶身或盒身
- 改變 Logo
- 改變文字
- 商品變形
- 商品融化
- 商品閃爍
- 商品漂移
- 商品突然變成其他商品
- 多出第二個商品
- 商品消失

預設禁止：

- 人物
- 手
- 主持人
- 代言人
- 模特兒
- 人物拿商品
- 人物遮擋商品

禁止：

- 浮水印
- 假價格
- 假贈品
- 假優惠
- 假認證
- 未確認規格
- 未確認功效
- 未確認成分
- 未確認產地

不得自行創造未確認商品資訊。

影片全程保持同一商品身份。

推薦：

slow cinematic push-in,
subtle orbit movement,
smooth camera movement,
stable framing.
"""


# =========================================================
# AI Prompt
# =========================================================

def build_prompt(
    data,
    selected_items,
):

    selected_text = "、".join(
        selected_items
    )

    return f"""

你是專業電商 AI 營運助手。

請分析使用者上傳的商品圖片及商品資料。

一般說明使用繁體中文。

「即夢 AI 2.5 生圖 Prompt」
與
「即夢 AI 2.5 影片 Prompt」
必須使用英文。

【商品資料】

商品名稱：
{data["商品名稱"] or "待確認"}

商品價格：
{data["商品價格"] or "待確認"}

商品成本：
{data["商品成本"] or "待確認"}

分潤比例：
{data["分潤比例"] or "待確認"}

月銷量：
{data["月銷量"] or "待確認"}

商品評分：
{data["商品評分"] or "待確認"}

商品連結：
{data["商品連結"] or "待確認"}

商品規格：
{data["商品規格"] or "待確認"}

目標平台：
{data["目標平台"]}

使用者選擇：
{selected_text}


【商品辨識保護】

只能根據圖片與使用者資料判斷。

無法確認必須寫：
「待確認」。

禁止虛構：

品牌、
容量、
成分、
產地、
功效、
價格、
贈品、
認證、
規格、
保存期限、
折扣、
銷量。

圖片中有多個商品時：

選擇最大、
最清楚、
品牌辨識度最高者作主要商品。

無法確認單品、組合或套裝時：

標示「待人工確認」。


【文案合規】

不要使用：

第一、
最強、
最好、
100%、
保證有效、
永久、
無敵、
神效、
速效、
治療、
根治、
醫療級。

禁止：

疾病治療、
醫療療效、
虛構折扣、
虛構價格、
虛構贈品、
虛構認證、
虛構規格。

{JIMENG_25_CORE_RULES}


【輸出】

只輸出使用者選擇的功能。

如果選擇「完整流程」，
輸出以下全部內容：


一、商品辨識

- 品牌
- 商品名稱
- 商品類型
- 包裝與外觀
- 圖片可確認資訊
- 待人工確認資訊


二、AI 選品分析

- 市場需求
- 商品吸引力
- 競爭程度
- 內容製作難度
- 合規風險
- 推薦分數 0～100
- 推薦等級
- 評分依據

若缺少價格、成本、銷量、分潤：

標示：
「目前為暫定內容潛力評分。」


三、蝦皮上架文案

- 商品標題三組
- 短描述
- 完整商品描述
- 商品特色
- 使用方式
- 保存方式
- 注意事項
- 搜尋關鍵字
- 商品規格
- 待確認資料


四、TikTok 文案

- 影片開場
- 15 秒口播
- 30 秒口播
- TikTok 貼文
- Hashtag
- 行動引導


五、即夢 AI 2.5 生圖


A｜1:1 蝦皮商品主圖

English Prompt

Negative Prompt

必須包含：

square 1:1,
premium commercial product photography,
product centered,
clean composition,
realistic materials,
realistic lighting,
original product identity preserved,
original packaging preserved.


B｜9:16 TikTok 商品海報

English Prompt

Negative Prompt

必須包含：

vertical 9:16,
product centered,
premium advertising composition,
strong visual hierarchy,
clean background,
original packaging preserved,
original product identity preserved.


C｜商品介紹圖

English Prompt

Negative Prompt

必須包含：

product-focused,
premium commercial photography,
close-up product details,
clean premium background,
material details visible,
packaging details visible,
no person,
no hand.


六、即夢 AI 2.5 影片

製作 9:16 直式商品展示影片。

Scene 1 — Opening

商品完整出現、
置中、
清楚。

Scene 2 — Product Detail

展示包裝、
材質、
商品細節。

Scene 3 — Camera Motion

slow cinematic push-in,
subtle orbit movement,
smooth camera movement,
stable framing.

Scene 4 — Ending

商品重新置中、
穩定定格、
保持原貌。

Negative Prompt：

product deformation,
product transformation,
packaging redesign,
logo change,
text distortion,
text drifting,
duplicated product,
extra product,
missing product,
color shift,
shape change,
melting,
flickering,
warped packaging,
floating objects,
human,
hands,
presenter,
spokesperson,
watermark,
fake gift,
fake price.


七、即夢 AI 2.5 爆款帶貨版本

9:16 電商帶貨影片。

0～3 秒：
商品第一視覺。

3～7 秒：
商品細節。

7～12 秒：
商品特色。

12～15 秒：
商品置中結尾。

禁止：

人物、
手、
主持人、
代言人。

不得自行加入未確認賣點。


八、蝦皮分潤合規檢查

- 商品與圖片是否一致
- 影片與商品是否一致
- 文案與商品是否一致
- 綁定商品是否一致
- 是否疑似禁止推廣商品
- 是否可能無法取得分潤
- 是否含療效宣稱
- 是否含誇大宣稱
- 是否存在規格誤判
- 是否存在錯誤價格
- 是否存在假贈品
- 是否使用未確認資訊

最後判斷：

適合發布
/
修改後發布
/
禁止發布

並列出必須人工確認項目。


九、最終人工確認清單

- 可直接使用內容
- 必須修改內容
- 缺少商品資料
- 發布前最後檢查事項


重要：

即夢 Prompt 必須可以直接複製。

不要輸出：

「你可以」
「建議」
「例如」
「請自行修改」

不要把未確認資訊當成事實。

商品圖片中的原始商品永遠是主要參考來源。
"""


# =========================================================
# Gemini 分析
# =========================================================

def analyze_with_gemini(
    api_key,
    prompt,
    image,
):

    client = genai.Client(
        api_key=api_key
    )

    errors = []

    for model_name in MODEL_CANDIDATES:

        try:

            response = (
                client.models.generate_content(
                    model=model_name,
                    contents=[
                        prompt,
                        image,
                    ],
                )
            )

            result = getattr(
                response,
                "text",
                None,
            )

            if (
                result
                and result.strip()
            ):

                return (
                    result.strip(),
                    model_name,
                )

            errors.append(
                f"{model_name}："
                "沒有回傳內容"
            )

        except Exception as error:

            errors.append(
                f"{model_name}："
                f"{str(error)}"
            )

    raise RuntimeError(
        "所有 Gemini 模型均無法使用：\n\n"
        + "\n\n".join(errors)
    )


# =========================================================
# 商品圖片
# =========================================================

st.subheader(
    "1｜📷 上傳商品圖片"
)

uploaded_file = st.file_uploader(
    "請選擇商品圖片",
    type=[
        "jpg",
        "jpeg",
        "png",
        "webp",
    ],
    accept_multiple_files=False,
    key="product_image_uploader",
    help=(
        "支援 JPG、JPEG、PNG、WEBP。"
        "建議使用清楚的商品正面照片。"
    ),
)


prepared_image = None


if uploaded_file is not None:

    try:

        prepared_image = prepare_image(
            uploaded_file
        )

        st.success(
            f"✅ 圖片已成功上傳："
            f"{uploaded_file.name}"
        )

        st.image(
            prepared_image,
            caption="已讀取商品圖片",
            use_container_width=True,
        )

    except Exception as error:

        st.error(
            "❌ 圖片讀取失敗。"
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
        placeholder="不知道可留空",
        key="product_name",
    )

    product_price = st.text_input(
        "商品價格",
        placeholder="例如：399",
        key="product_price",
    )

    product_cost = st.text_input(
        "商品成本",
        placeholder="例如：250",
        key="product_cost",
    )

    commission_rate = st.text_input(
        "分潤比例",
        placeholder="例如：12%",
        key="commission_rate",
    )


with col2:

    monthly_sales = st.text_input(
        "月銷量",
        placeholder="例如：1500",
        key="monthly_sales",
    )

    product_rating = st.text_input(
        "商品評分",
        placeholder="例如：4.8",
        key="product_rating",
    )

    product_url = st.text_input(
        "商品連結",
        placeholder="可留空",
        key="product_url",
    )

    product_spec = st.text_area(
        "商品規格",
        placeholder=(
            "例如：300ml、單瓶、白色"
        ),
        height=130,
        key="product_spec",
    )


# =========================================================
# 平台
# =========================================================

st.subheader(
    "3｜🎯 目標平台"
)

target_platform = st.radio(
    "目標平台",
    [
        "蝦皮",
        "TikTok",
        "蝦皮＋TikTok",
    ],
    horizontal=True,
    key="target_platform",
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
    "即夢 AI 2.5 生圖指令",
    "即夢 AI 2.5 影片指令",
    "即夢 AI 2.5 爆款帶貨影片",
    "分潤合規檢查",
    "完整流程",
]


selected_items = st.multiselect(
    "選擇需要的功能",
    options=generate_options,
    default=["完整流程"],
    key="selected_ai_features",
)


if (
    "完整流程" in selected_items
    and len(selected_items) > 1
):

    st.info(
        "ℹ️ 已選擇完整流程，"
        "系統會自動以完整流程執行。"
    )


# =========================================================
# 啟動
# =========================================================

st.subheader(
    "5｜🚀 開始 AI 分析"
)


if st.button(
    "🚀 啟動 AI 蝦皮半自動化 2.5",
    type="primary",
    use_container_width=True,
    key="start_ai_analysis",
):

    api_key = get_api_key()

    if prepared_image is None:

        st.error(
            "❌ 請先上傳商品圖片。"
        )

    elif not selected_items:

        st.error(
            "❌ 請至少選擇一個 AI 功能。"
        )

    elif not api_key:

        st.error(
            "❌ 尚未設定 GEMINI_API_KEY。"
        )

        st.info(
            "請到 Streamlit Secrets "
            "設定 GEMINI_API_KEY。"
        )

    else:

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


        effective_items = (

            ["完整流程"]

            if "完整流程"
            in selected_items

            else selected_items
        )


        prompt = build_prompt(
            product_data,
            effective_items,
        )


        try:

            with st.spinner(
                "🤖 AI 正在辨識商品、"
                "分析選品並生成即夢 AI 2.5 指令……"
            ):

                result, used_model = (
                    analyze_with_gemini(
                        api_key=api_key,
                        prompt=prompt,
                        image=prepared_image,
                    )
                )


            st.session_state.analysis_result = (
                result
            )

            st.session_state.analysis_model = (
                used_model
            )

            st.success(
                "🎉 AI 分析完成！"
            )


        except Exception as error:

            error_text = str(error)

            st.error(
                "❌ Gemini AI 分析失敗。"
            )

            st.code(
                error_text
            )

            if (
                "401" in error_text
                or "API_KEY"
                in error_text.upper()
                or "UNAUTHENTICATED"
                in error_text.upper()
            ):

                st.warning(
                    "請檢查 GEMINI_API_KEY "
                    "是否正確。"
                )

            elif (
                "429" in error_text
                or "RESOURCE_EXHAUSTED"
                in error_text
            ):

                st.warning(
                    "API 額度或速率限制，"
                    "請稍後再試。"
                )

            elif (
                "404" in error_text
                or "NOT_FOUND"
                in error_text
            ):

                st.warning(
                    "Gemini 模型或 API 權限可能不正確。"
                )


# =========================================================
# AI 結果
# =========================================================

if st.session_state.analysis_result:

    st.divider()

    st.subheader(
        "6｜📊 AI 分析結果"
    )

    if st.session_state.analysis_model:

        st.caption(
            "本次使用模型："
            f"{st.session_state.analysis_model}"
        )

    st.markdown(
        st.session_state.analysis_result
    )

    st.subheader(
        "7｜📋 複製完整結果"
    )

    st.text_area(
        "完整 AI 結果",
        value=st.session_state.analysis_result,
        height=700,
        key="full_ai_result",
    )

    current_time = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    safe_product_name = (
        product_name.strip()
        if product_name.strip()
        else "商品分析"
    )

    safe_product_name = re.sub(
        r'[\\/:*?"<>|]+',
        "_",
        safe_product_name,
    )

    file_name = (
        "AI蝦皮半自動化2.5_"
        f"{safe_product_name}_"
        f"{current_time}.txt"
    )

    st.download_button(
        "⬇️ 下載完整 AI 結果",
        data=(
            st.session_state.analysis_result
            .encode("utf-8")
        ),
        file_name=file_name,
        mime="text/plain",
        use_container_width=True,
        key="download_ai_result",
    )

    st.warning(
        "正式發布前，請人工確認："
        "商品名稱、容量、產地、成分、"
        "保存期限、貨源、售價、庫存、"
        "組合數、商品規格及分潤資格。"
    )


# =========================================================
# 系統設定狀態
# =========================================================

with st.expander(
    "⚙️ 系統設定檢查"
):

    gemini_ok = bool(
        secret("GEMINI_API_KEY")
    )

    supabase_url_ok = bool(
        secret("SUPABASE_URL")
    )

    supabase_key_ok = bool(
        secret("SUPABASE_ANON_KEY")
    )

    app_url_ok = bool(
        secret("APP_URL")
    )

    st.write(
        "Gemini API："
        + ("✅ 已設定"
           if gemini_ok
           else "❌ 未設定")
    )

    st.write(
        "Supabase URL："
        + ("✅ 已設定"
           if supabase_url_ok
           else "❌ 未設定")
    )

    st.write(
        "Supabase Anon Key："
        + ("✅ 已設定"
           if supabase_key_ok
           else "❌ 未設定")
    )

    st.write(
        "APP_URL："
        + ("✅ 已設定"
           if app_url_ok
           else "❌ 未設定")
    )

    st.caption(
        "⚠️ 這裡只顯示是否設定，"
        "不會顯示你的 API Key 或密鑰內容。"
    )


# =========================================================
# 頁尾
# =========================================================

st.divider()

st.caption(
    "AI 蝦皮半自動化 2.5 PRO｜"
    "會員系統｜Google / LINE / WeChat 入口｜"
    "Gemini AI｜即夢 AI 2.5｜"
    "AI 內容僅供輔助，正式發布前必須人工確認。"
)
