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
# 無 API 版本
#
# 不需要：
# Google API
# LINE API
# WeChat API
# Supabase
# Gemini API
#
# 會員資料：members.json
# AI：本機規則 + Prompt 生成模式
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


# =========================================================
# 建立資料夾
# =========================================================

os.makedirs(DATA_DIR, exist_ok=True)


# =========================================================
# 本機會員資料庫
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
        salt, saved_hash = (
            saved_value.split("$", 1)
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
        "id": secrets.token_hex(8),
        "username": ADMIN_USERNAME,
        "password_hash": hash_password(
            "admin123"
        ),
        "name": "系統管理員",
        "email": "",
        "role": "admin",
        "status": "active",
        "expires": (
            date.today()
            + timedelta(days=3650)
        ).isoformat(),
        "provider": "local",
        "created_at": datetime.now().isoformat()
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
            member.get("username", "")
            .lower()
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
            member.get("email", "")
            .lower()
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
        "password_hash": hash_password(
            password
        ),
        "name": name.strip(),
        "email": email,
        "role": "member",
        "status": "active",
        "expires": expires,
        "provider": "local",
        "created_at": datetime.now().isoformat()
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
    updates
):

    members = load_members()

    updated = False

    for member in members:

        if member.get("id") == member_id:

            member.update(updates)

            updated = True

            break

    if updated:
        save_members(members)

    return updated


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

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# 第三方登入
# =========================================================

def social_buttons():

    st.markdown(
        "### 🌐 第三方登入"
    )

    st.info(
        "目前尚未設定 Google / LINE / WeChat API。"
        "本版本先使用「一般會員帳號＋密碼」登入，"
        "不需要任何第三方 API。"
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.button(
            "🇬 Google",
            disabled=True,
            use_container_width=True
        )

    with c2:
        st.button(
            "💚 LINE",
            disabled=True,
            use_container_width=True
        )

    with c3:
        st.button(
            "💬 WeChat",
            disabled=True,
            use_container_width=True
        )

    st.caption(
        "等你之後取得第三方 OAuth 設定，再接回 Google / LINE / WeChat。"
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

            if not username or not password:

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
                        "⛔ 會員資格已到期。",

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

        social_buttons()

        st.divider()

        if st.button(
            "📝 還沒有帳號？註冊會員",
            use_container_width=True
        ):

            st.session_state.page = "register"

            st.rerun()

        st.divider()

        st.caption(
            "管理員測試帳號："
        )

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


if member_status.lower() != "active":

    st.error(
        "⛔ 此會員帳號目前已停權。"
    )

    if st.button(
        "🚪 返回登入"
    ):
        logout()

    st.stop()


if remaining_days < 0:

    st.error(
        "⛔ 會員資格已到期。"
    )

    if st.button(
        "🚪 返回登入"
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
        f"登入方式：**本機會員系統**"
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
        use_container_width=True
    ):
        logout()


# =========================================================
# 管理員中心
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
            ""
        )

        username = member.get(
            "username",
            ""
        )

        name = member.get(
            "name",
            ""
        )

        email = member.get(
            "email",
            ""
        )

        role = member.get(
            "role",
            "member"
        )

        status = member.get(
            "status",
            "active"
        )

        expires = member.get(
            "expires",
            ""
        )

        with st.expander(
            f"👤 {name}｜{username}"
        ):

            st.write(
                f"Email：**{email}**"
            )

            st.write(
                "註冊方式：**本機帳號**"
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
                    "disabled"
                ],
                index=(
                    0
                    if status == "active"
                    else 1
                ),
                key=f"status_{mid}"
            )

            roles = [
                "member",
                "vip",
                "admin"
            ]

            new_role = st.selectbox(
                "會員等級",
                roles,
                index=(
                    roles.index(role)
                    if role in roles
                    else 0
                ),
                key=f"role_{mid}"
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
                key=f"expire_{mid}"
            )

            c1, c2, c3 = st.columns(3)

            with c1:

                if st.button(
                    "💾 儲存",
                    key=f"save_{mid}",
                    use_container_width=True
                ):

                    update_member(
                        mid,
                        {
                            "status":
                            new_status,

                            "role":
                            new_role,

                            "expires":
                            new_expire.isoformat()
                        }
                    )

                    st.success(
                        "已更新。"
                    )

                    st.rerun()

            with c2:

                if st.button(
                    "➕ 延長 30 天",
                    key=f"extend_{mid}",
                    use_container_width=True
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
                            "active"
                        }
                    )

                    st.success(
                        "會員期限已延長。"
                    )

                    st.rerun()

            with c3:

                if username != current_username:

                    if st.button(
                        "⛔ 停權",
                        key=f"disable_{mid}",
                        use_container_width=True
                    ):

                        update_member(
                            mid,
                            {
                                "status":
                                "disabled"
                            }
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
    unsafe_allow_html=True
)

st.markdown(
    '<div class="main-subtitle">'
    '商品辨識｜AI 選品｜蝦皮文案｜TikTok｜'
    '即夢 AI 2.5｜無 API 模式'
    '</div>',
    unsafe_allow_html=True
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
# 圖片處理
# =========================================================

def prepare_image(uploaded_file):

    if uploaded_file is None:

        raise ValueError(
            "沒有收到圖片檔案。"
        )

    try:

        raw_bytes = (
            uploaded_file.getvalue()
        )

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

        image.load()

        original_size = image.size

        if image.mode not in (
            "RGB",
            "RGBA"
        ):

            image = image.convert(
                "RGB"
            )

        image.thumbnail(
            (
                MAX_IMAGE_SIZE,
                MAX_IMAGE_SIZE
            ),
            Image.Resampling.LANCZOS
        )

        if image.mode == "RGBA":

            background = Image.new(
                "RGB",
                image.size,
                "white"
            )

            background.paste(
                image,
                mask=image.getchannel("A")
            )

            image = background

        else:

            image = image.convert(
                "RGB"
            )

        return image, original_size

    except Exception as error:

        raise ValueError(
            "無法讀取這張圖片。"
            "請確認是 JPG、JPEG、PNG 或 WEBP。"
            f"\n\n詳細錯誤：{error}"
        )


# =========================================================
# 本機商品分析
# =========================================================

def local_product_analysis(
    image,
    data
):

    width, height = image.size

    name = (
        data["商品名稱"]
        or "待確認"
    )

    platform = data[
        "目標平台"
    ]

    result = f"""
# 🤖 AI 蝦皮半自動化 2.5 PRO

## ⚠️ 目前模式

**本機無 API 模式**

目前沒有使用 Gemini / Google / LINE / WeChat / Supabase API。

因此本次結果主要依據：

- 使用者輸入商品資料
- 上傳圖片基本資訊
- 電商 Prompt 規則
- 即夢 AI 2.5 商品一致性規則

真正的 AI 視覺辨識需要之後接入 Gemini API。

---

# 一、商品辨識

商品名稱：{name}

圖片尺寸：{width} × {height}

目前商品品牌：
**待人工確認**

商品類型：
**待人工確認**

包裝與外觀：
**請以原始商品圖片確認**

圖片可確認資訊：
- 已成功讀取商品圖片
- 圖片可供後續即夢 AI 2.5 Prompt 使用
- 商品原始外觀應保持一致

待人工確認資訊：
- 品牌
- 型號
- 容量
- 規格
- 成分
- 產地
- 功效
- 保存期限
- 價格
- 贈品

---

# 二、AI 選品分析

目前屬於：

**暫定內容潛力分析**

原因：

目前沒有連接即時市場資料 API。

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

推薦分數：
**待人工確認**

---

# 三、蝦皮上架文案

## 商品標題 1

{data["商品名稱"] or "【商品名稱待確認】"}｜質感商品｜日常使用｜熱門推薦

## 商品標題 2

{data["商品名稱"] or "【商品名稱待確認】"}｜實用商品｜高質感設計｜電商推薦

## 商品標題 3

{data["商品名稱"] or "【商品名稱待確認】"}｜商品推薦｜日常使用｜精選商品

### 短描述

{data["商品名稱"] or "本商品"}，
詳細商品資訊請以商品圖片與實際規格為準。

### 商品特色

- 商品外觀以原始圖片為準
- 包裝以原始商品為準
- 不自行增加未確認規格
- 不自行增加未確認功效

### 使用方式

請依商品實際包裝與官方說明使用。

### 注意事項

實際商品規格、內容物、容量、產地與保存方式，
請發布前人工確認。

### 搜尋關鍵字

商品推薦、電商商品、蝦皮商品、熱門商品、
生活用品、商品分享

---

# 四、TikTok 文案

## 影片開場

「這款商品到底有什麼特色？」

## 15 秒口播

「今天快速帶大家看這款商品，
從外觀、包裝到細節都可以近距離確認。
實際規格與商品資訊，請以商品頁面為準。」

## 30 秒口播

「今天來快速介紹這款商品。
先從商品外觀開始，
接著帶大家看包裝與細節。
如果你正在找類似商品，
可以進一步查看商品頁面的實際規格與資訊。」

## TikTok 貼文

商品重點快速展示。
實際商品資訊請以商品頁面為準。

## Hashtag

#商品推薦
#蝦皮
#電商
#TikTok帶貨
#商品分享

## 行動引導

「點擊商品連結查看詳細資訊。」

---

# 五、即夢 AI 2.5 生圖

## A｜1:1 蝦皮商品主圖

English Prompt:

square 1:1,
premium commercial product photography,
product centered,
clean composition,
realistic materials,
realistic lighting,
original product identity preserved,
original packaging preserved,
original logo preserved,
original label preserved,
original colors preserved,
original shape preserved,
studio quality,
high-end e-commerce product photography,
sharp product details,
clean premium background,
no person,
no hand,
no model.

Negative Prompt:

product redesign,
packaging redesign,
logo change,
text distortion,
color shift,
shape change,
fake label,
fake text,
duplicate product,
extra product,
missing product,
human,
hands,
model,
presenter,
spokesperson,
watermark,
fake price,
fake discount,
fake gift.

---

## B｜9:16 TikTok 商品海報

English Prompt:

vertical 9:16,
product centered,
premium advertising composition,
strong visual hierarchy,
clean background,
original packaging preserved,
original product identity preserved,
original logo preserved,
original label preserved,
original colors preserved,
high-end commercial product photography,
dramatic but realistic lighting,
sharp product details,
clean premium composition,
no person,
no hand.

Negative Prompt:

product redesign,
packaging redesign,
logo change,
text distortion,
duplicate product,
extra product,
missing product,
color shift,
shape change,
human,
hands,
model,
presenter,
spokesperson,
watermark,
fake price,
fake discount,
fake gift.

---

## C｜商品介紹圖

English Prompt:

product-focused,
premium commercial photography,
close-up product details,
clean premium background,
material details visible,
packaging details visible,
original product identity preserved,
original packaging preserved,
realistic materials,
realistic lighting,
no person,
no hand,
no model,
high detail,
professional e-commerce advertising photography.

Negative Prompt:

product deformation,
packaging redesign,
logo change,
text distortion,
text drifting,
duplicate product,
extra product,
missing product,
color shift,
shape change,
melting,
flickering,
warped packaging,
human,
hands,
presenter,
spokesperson,
watermark.

---

# 六、即夢 AI 2.5 影片

製作 9:16 直式商品展示影片。

Scene 1 — Opening

商品完整出現、置中、清楚。

Scene 2 — Product Detail

展示包裝、材質、商品細節。

Scene 3 — Camera Motion

slow cinematic push-in,
subtle orbit movement,
smooth camera movement,
stable framing.

Scene 4 — Ending

商品重新置中、
穩定定格、
保持原貌。

Negative Prompt:

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

---

# 七、即夢 AI 2.5 爆款帶貨影片

比例：

9:16

0～3 秒：

商品第一視覺，
商品完整置中。

3～7 秒：

展示商品包裝、
材質與細節。

7～12 秒：

展示已確認的商品特色。

12～15 秒：

商品置中，
穩定定格，
保持原始商品外觀。

禁止：

人物、
手、
主持人、
代言人。

不得自行加入未確認賣點。

---

# 八、蝦皮分潤合規檢查

商品與圖片是否一致：
**待人工確認**

影片與商品是否一致：
**待人工確認**

文案與商品是否一致：
**待人工確認**

綁定商品是否一致：
**發布前確認**

是否疑似禁止推廣商品：
**待人工確認**

是否可能無法取得分潤：
**待人工確認**

是否含療效宣稱：
**目前模板避免使用**

是否含誇大宣稱：
**目前模板避免使用**

是否存在規格誤判：
**待人工確認**

是否存在錯誤價格：
**待人工確認**

是否存在假贈品：
**目前模板避免使用**

是否使用未確認資訊：
**禁止**

最終判斷：

**修改後發布**

---

# 九、最終人工確認清單

## 可直接使用內容

- 即夢 AI 2.5 生圖 Prompt
- 即夢 AI 2.5 影片 Prompt
- TikTok 基礎腳本
- 蝦皮基礎文案模板

## 必須修改內容

- 商品名稱
- 商品規格
- 商品賣點
- 商品價格
- 商品連結
- 商品實際資訊

## 缺少商品資料

- 品牌
- 型號
- 容量
- 成分
- 產地
- 功效
- 保存期限

## 發布前最後檢查

- 商品圖片
- 商品名稱
- 商品規格
- 價格
- 庫存
- 商品連結
- 分潤資格
- 宣稱內容

---

# 🎯 目標平台

{platform}

{JIMENG_25_CORE_RULES}
"""

    return result.strip()


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
        "webp"
    ],
    accept_multiple_files=False,
    key="product_image_uploader",
    help=(
        "支援 JPG、JPEG、PNG、WEBP。"
    )
)


prepared_image = None
original_image_size = None


if uploaded_file is not None:

    try:

        prepared_image, original_image_size = (
            prepare_image(
                uploaded_file
            )
        )

        st.success(
            f"✅ 圖片已成功上傳："
            f"{uploaded_file.name}"
        )

        st.image(
            prepared_image,
            caption=(
                f"已讀取商品圖片｜"
                f"原始尺寸："
                f"{original_image_size[0]} × "
                f"{original_image_size[1]}"
            ),
            use_container_width=True
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
        key="product_name"
    )

    product_price = st.text_input(
        "商品價格",
        placeholder="例如：399",
        key="product_price"
    )

    product_cost = st.text_input(
        "商品成本",
        placeholder="例如：250",
        key="product_cost"
    )

    commission_rate = st.text_input(
        "分潤比例",
        placeholder="例如：12%",
        key="commission_rate"
    )


with col2:

    monthly_sales = st.text_input(
        "月銷量",
        placeholder="例如：1500",
        key="monthly_sales"
    )

    product_rating = st.text_input(
        "商品評分",
        placeholder="例如：4.8",
        key="product_rating"
    )

    product_url = st.text_input(
        "商品連結",
        placeholder="可留空",
        key="product_url"
    )

    product_spec = st.text_area(
        "商品規格",
        placeholder=(
            "例如：300ml、單瓶、白色"
        ),
        height=130,
        key="product_spec"
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
        "蝦皮＋TikTok"
    ],
    horizontal=True,
    key="target_platform"
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
    "完整流程"
]


selected_items = st.multiselect(
    "選擇需要的功能",
    options=generate_options,
    default=["完整流程"],
    key="selected_ai_features"
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
    key="start_ai_analysis"
):

    if prepared_image is None:

        st.error(
            "❌ 請先上傳商品圖片。"
        )

    elif not selected_items:

        st.error(
            "❌ 請至少選擇一個 AI 功能。"
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
            target_platform
        }

        with st.spinner(
            "🤖 正在產生本機 AI 電商分析與即夢 AI 2.5 Prompt……"
        ):

            result = local_product_analysis(
                prepared_image,
                product_data
            )

        st.session_state.analysis_result = result

        st.session_state.analysis_mode = (
            "本機無 API 模式"
        )

        st.success(
            "🎉 分析完成！"
        )


# =========================================================
# AI 結果
# =========================================================

if st.session_state.analysis_result:

    st.divider()

    st.subheader(
        "6｜📊 AI 分析結果"
    )

    st.caption(
        "本次模式："
        + st.session_state.analysis_mode
    )

    st.markdown(
        st.session_state.analysis_result
    )

    st.subheader(
        "7｜📋 完整結果"
    )

    st.text_area(
        "完整 AI 結果",
        value=(
            st.session_state.analysis_result
        ),
        height=700,
        key="full_ai_result"
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
        safe_product_name
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
        key="download_ai_result"
    )

    st.warning(
        "正式發布前，請人工確認："
        "商品名稱、容量、產地、成分、"
        "保存期限、售價、庫存、"
        "組合數、商品規格及分潤資格。"
    )


# =========================================================
# 系統狀態
# =========================================================

with st.expander(
    "⚙️ 系統設定狀態"
):

    st.success(
        "✅ 本機會員系統：啟用"
    )

    st.success(
        "✅ 本機會員資料：members.json"
    )

    st.success(
        "✅ 圖片上傳：啟用"
    )

    st.success(
        "✅ 即夢 AI 2.5 Prompt 生成：啟用"
    )

    st.info(
        "ℹ️ Gemini API：目前未使用"
    )

    st.info(
        "ℹ️ Google / LINE / WeChat：目前未使用"
    )

    st.info(
        "ℹ️ Supabase：目前未使用"
    )


# =========================================================
# 頁尾
# =========================================================

st.divider()

st.caption(
    "AI 蝦皮半自動化 2.5 PRO｜"
    "本機會員系統｜"
    "即夢 AI 2.5 Prompt｜"
    "無 API 版本｜"
    "正式發布前必須人工確認。"
)
