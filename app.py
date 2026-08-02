import hashlib
import secrets
from datetime import datetime, date, timedelta

import streamlit as st
from google import genai
from PIL import Image, ImageOps


# =========================================================
# AI 蝦皮半自動化 2.5 PRO
# 會員註冊｜會員登入｜會員期限｜管理員｜AI 商品分析
# =========================================================

st.set_page_config(
    page_title="AI 蝦皮半自動化 2.5 PRO",
    page_icon="🛒",
    layout="wide",
)


# =========================================================
# 系統設定
# =========================================================

MODEL_CANDIDATES = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]

MAX_IMAGE_SIZE = 1600

DEFAULT_MEMBER_DAYS = 30


# =========================================================
# 🔐 密碼工具
# =========================================================

def hash_password(password):
    """
    使用 SHA-256 + 隨機 salt
    """

    salt = secrets.token_hex(16)

    password_hash = hashlib.sha256(
        (salt + password).encode("utf-8")
    ).hexdigest()

    return f"{salt}${password_hash}"


def verify_password(password, saved_value):
    """
    驗證 salt$password_hash
    """

    try:

        salt, saved_hash = saved_value.split("$", 1)

        input_hash = hashlib.sha256(
            (salt + password).encode("utf-8")
        ).hexdigest()

        return secrets.compare_digest(
            input_hash,
            saved_hash,
        )

    except Exception:

        return False


# =========================================================
# Supabase 設定
# =========================================================

def get_supabase_config():

    try:

        url = str(
            st.secrets["SUPABASE_URL"]
        ).strip()

        key = str(
            st.secrets["SUPABASE_ANON_KEY"]
        ).strip()

        if not url or not key:

            return None, None

        return url.rstrip("/"), key

    except Exception:

        return None, None


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
            "尚未設定 SUPABASE_URL 或 SUPABASE_ANON_KEY。"
        )

    headers = {

        "apikey": key,

        "Authorization": f"Bearer {key}",

        "Content-Type": "application/json",

    }

    if headers_extra:

        headers.update(
            headers_extra
        )

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
# 會員資料庫
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

    if rows:

        return rows[0]

    return None


def find_member_by_id(member_id):

    rows = supabase_request(

        "GET",

        "members",

        params={
            "id": f"eq.{member_id}",
            "select": "*",
            "limit": "1",
        },

    )

    if rows:

        return rows[0]

    return None


def create_member(
    username,
    password,
    name,
    email,
):

    username = username.strip().lower()

    if find_member(username):

        return False, "帳號已存在。"

    password_hash = hash_password(
        password
    )

    expires = (
        date.today()
        + timedelta(
            days=DEFAULT_MEMBER_DAYS
        )
    ).isoformat()

    data = {

        "username": username,

        "password_hash": password_hash,

        "name": name.strip(),

        "email": email.strip(),

        "role": "member",

        "status": "active",

        "expires": expires,

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


def update_member(
    member_id,
    updates,
):

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
# 登入驗證
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
# Session 初始化
# =========================================================

if "logged_in" not in st.session_state:

    st.session_state.logged_in = False

if "page" not in st.session_state:

    st.session_state.page = "login"


# =========================================================
# 登出
# =========================================================

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

def inject_css():

    st.markdown(
        """
        <style>

        .main-title {
            text-align:center;
            font-size:42px;
            font-weight:800;
            margin-top:20px;
            margin-bottom:10px;
        }

        .main-subtitle {
            text-align:center;
            font-size:17px;
            opacity:0.75;
            margin-bottom:30px;
        }

        .member-card {
            padding:18px;
            border-radius:16px;
            border:1px solid rgba(128,128,128,.25);
            margin-bottom:15px;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


inject_css()


# =========================================================
# 🔐 登入頁
# =========================================================

def login_page():

    st.markdown(
        '<div class="main-title">🛒 AI 蝦皮半自動化 2.5 PRO</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="main-subtitle">'
        '會員登入｜AI 商品分析｜即夢 AI 2.5 Prompt｜蝦皮｜TikTok'
        '</div>',
        unsafe_allow_html=True,
    )

    left, center, right = st.columns(
        [1, 2, 1]
    )

    with center:

        st.subheader(
            "🔐 會員登入"
        )

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

        login_button = st.button(
            "🚀 登入系統",
            type="primary",
            use_container_width=True,
        )

        if login_button:

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

                    elif result == "expired":

                        st.error(
                            "⛔ 會員資格已到期，請聯絡管理員續期。"
                        )

                    elif result == "disabled":

                        st.error(
                            "⛔ 此會員帳號目前已停權。"
                        )

                    elif result == "invalid_date":

                        st.error(
                            "⛔ 會員到期日資料錯誤。"
                        )

                    else:

                        st.error(
                            "❌ 帳號或密碼錯誤。"
                        )

                except Exception as error:

                    st.error(
                        "會員系統連線失敗。"
                    )

                    st.code(
                        str(error)
                    )

        st.divider()

        if st.button(
            "📝 還沒有帳號？註冊會員",
            use_container_width=True,
        ):

            st.session_state.page = "register"

            st.rerun()


# =========================================================
# 📝 註冊頁
# =========================================================

def register_page():

    st.markdown(
        '<div class="main-title">📝 會員註冊</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="main-subtitle">'
        '建立您的 AI 蝦皮半自動化會員帳號'
        '</div>',
        unsafe_allow_html=True,
    )

    left, center, right = st.columns(
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
            "設定會員帳號",
            placeholder="3～30 個英數字或底線",
        )

        password = st.text_input(
            "設定會員密碼",
            type="password",
            placeholder="至少 6 個字元",
        )

        password_confirm = st.text_input(
            "再次輸入密碼",
            type="password",
        )

        register_button = st.button(
            "🚀 建立會員帳號",
            type="primary",
            use_container_width=True,
        )

        if register_button:

            username_clean = (
                username.strip().lower()
            )

            if not name.strip():

                st.error(
                    "請輸入姓名或暱稱。"
                )

            elif "@" not in email:

                st.error(
                    "請輸入正確 Email。"
                )

            elif (
                len(username_clean) < 3
                or len(username_clean) > 30
            ):

                st.error(
                    "會員帳號長度需要 3～30 個字元。"
                )

            elif not username_clean.replace(
                "_",
                "",
            ).isalnum():

                st.error(
                    "帳號只能使用英文字母、數字與底線。"
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

                        username=username_clean,

                        password=password,

                        name=name,

                        email=email,

                    )

                    if success:

                        st.success(
                            "🎉 會員帳號建立成功！"
                        )

                        st.info(
                            "您的會員資格預設為 30 天，"
                            "現在可以直接登入。"
                        )

                        st.session_state.page = "login"

                        st.rerun()

                    else:

                        st.error(
                            str(result)
                        )

                except Exception as error:

                    st.error(
                        "註冊失敗，請檢查會員資料庫設定。"
                    )

                    st.code(
                        str(error)
                    )

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
# 目前會員
# =========================================================

current_username = st.session_state.get(
    "username",
    "",
)

current_member = st.session_state.get(
    "member",
    {},
)


# =========================================================
# 重新取得最新會員資料
# =========================================================

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


# =========================================================
# 會員期限
# =========================================================

try:

    expire_date = date.fromisoformat(
        member_expires
    )

    remaining_days = (
        expire_date - date.today()
    ).days

except Exception:

    remaining_days = -999


if (
    member_status.lower()
    != "active"
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
# 👤 側邊欄
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
# 👑 管理員中心
# =========================================================

def admin_panel():

    st.header(
        "👑 管理員中心"
    )

    st.caption(
        "會員註冊後會自動進入會員資料庫。"
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

    if not members:

        st.info(
            "目前沒有會員資料。"
        )

        return

    st.write(
        f"目前會員數：**{len(members)}**"
    )

    st.divider()

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
            f"👤 {name}｜{username}",
            expanded=False,
        ):

            c1, c2 = st.columns(2)

            with c1:

                st.write(
                    f"帳號：**{username}**"
                )

                st.write(
                    f"姓名：**{name}**"
                )

                st.write(
                    f"Email：**{email}**"
                )

            with c2:

                st.write(
                    f"身份：**{role}**"
                )

                st.write(
                    f"狀態：**{status}**"
                )

                st.write(
                    f"到期：**{expires}**"
                )

            st.divider()

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

            new_role = st.selectbox(

                "會員等級",

                [
                    "member",
                    "vip",
                    "admin",
                ],

                index=(
                    [
                        "member",
                        "vip",
                        "admin",
                    ].index(role)
                    if role
                    in [
                        "member",
                        "vip",
                        "admin",
                    ]
                    else 0
                ),

                key=f"role_{mid}",

            )

            new_expire = st.date_input(

                "會員到期日",

                value=(
                    date.fromisoformat(
                        expires
                    )
                    if expires
                    else date.today()
                ),

                key=f"expire_{mid}",

            )

            b1, b2, b3 = st.columns(3)

            with b1:

                if st.button(
                    "💾 儲存會員",
                    key=f"save_{mid}",
                    use_container_width=True,
                ):

                    try:

                        update_member(

                            mid,

                            {
                                "status": new_status,
                                "role": new_role,
                                "expires": new_expire.isoformat(),
                            },

                        )

                        st.success(
                            "會員資料已更新。"
                        )

                        st.rerun()

                    except Exception as error:

                        st.error(
                            "更新失敗。"
                        )

                        st.code(
                            str(error)
                        )

            with b2:

                if st.button(
                    "➕ 延長 30 天",
                    key=f"extend_{mid}",
                    use_container_width=True,
                ):

                    try:

                        current_expire = date.fromisoformat(
                            expires
                        )

                    except Exception:

                        current_expire = date.today()

                    if current_expire < date.today():

                        current_expire = date.today()

                    new_date = (
                        current_expire
                        + timedelta(days=30)
                    )

                    update_member(

                        mid,

                        {
                            "expires": new_date.isoformat(),
                            "status": "active",
                        },

                    )

                    st.success(
                        f"已延長至 {new_date.isoformat()}"
                    )

                    st.rerun()

            with b3:

                if (
                    username
                    != current_username
                ):

                    if st.button(
                        "⛔ 停權",
                        key=f"disable_{mid}",
                        use_container_width=True,
                    ):

                        update_member(

                            mid,

                            {
                                "status": "disabled"
                            },

                        )

                        st.warning(
                            "會員已停權。"
                        )

                        st.rerun()


# =========================================================
# 主系統
# =========================================================

st.markdown(
    '<div class="main-title">'
    '🛒 AI 蝦皮半自動化 2.5 PRO'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-subtitle">'
    '商品辨識｜AI 選品｜蝦皮文案｜TikTok｜即夢 AI 2.5｜分潤合規'
    '</div>',
    unsafe_allow_html=True,
)


# =========================================================
# 管理員入口
# =========================================================

if member_role.lower() == "admin":

    with st.expander(
        "👑 管理員中心",
        expanded=False,
    ):

        admin_panel()

    st.divider()


# =========================================================
# Gemini API
# =========================================================

def get_api_key():

    try:

        key = str(
            st.secrets["GEMINI_API_KEY"]
        ).strip()

        return key or None

    except Exception:

        return None


# =========================================================
# 圖片處理
# =========================================================

def prepare_image(uploaded_file):

    uploaded_file.seek(0)

    image = Image.open(
        uploaded_file
    )

    image = ImageOps.exif_transpose(
        image
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
        )
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

    return image


# =========================================================
# 即夢 AI 2.5 核心規則
# =========================================================

JIMENG_25_CORE_RULES = """
【即夢 AI 2.5 商品一致性核心規則】

1. 使用者上傳的商品圖片是唯一主要商品來源。

2. 必須維持：
- 商品原本品牌
- 商品原本包裝
- 商品原本形狀
- 商品原本比例
- 商品原本顏色
- 商品原本材質
- 原始 Logo
- 原始標籤
- 原始印刷文字
- 原始包裝結構

3. 禁止：
- 重新設計品牌
- 重新設計包裝
- 改變商品顏色
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

4. 預設禁止：
- 人物
- 手
- 主持人
- 代言人
- 模特兒
- 人物拿商品
- 人物遮擋商品

5. 禁止：
- 浮水印
- 假價格
- 假贈品
- 假優惠
- 假認證
- 未確認規格
- 未確認功效
- 未確認成分
- 未確認產地

6. 畫面：
- 商品為唯一主要視覺焦點
- 高級商業產品攝影
- 清楚
- 真實
- 穩定
- 適合電商

7. 即夢 Prompt 本體使用英文。

8. 不得自行創造未確認商品資訊。

9. 影片必須從開始到結束保持同一商品身份。

10. 影片推薦：
slow cinematic push-in,
subtle orbit movement,
smooth camera movement,
stable framing.
"""


# =========================================================
# Prompt
# =========================================================

def build_prompt(
    data,
    selected_items,
):

    selected_text = "、".join(
        selected_items
    )

    return f"""
你現在是專業電商 AI 營運助手。

請分析使用者上傳的商品圖片以及商品資料。

所有一般說明使用繁體中文。

但是：
「即夢 AI 2.5 生圖 Prompt」
「即夢 AI 2.5 影片 Prompt」
必須使用英文。

=========================================================
商品資料
=========================================================

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


=========================================================
商品辨識保護
=========================================================

只能根據：
1. 商品圖片
2. 使用者提供資料

判斷商品。

無法確認的資訊必須寫：

「待確認」

禁止自行虛構：

- 品牌
- 容量
- 成分
- 產地
- 功效
- 價格
- 贈品
- 認證
- 規格
- 保存期限
- 折扣
- 銷量

如果圖片中有多個商品：

選擇最大、最清楚、品牌辨識度最高的商品作為主要商品。

如果無法確認是單品、組合或套裝：

標示「待人工確認」。


=========================================================
文案合規
=========================================================

不要使用：

第一
最強
最好
100%
保證有效
永久
無敵
神效
速效
治療
根治
醫療級

禁止：

- 疾病治療宣稱
- 醫療療效宣稱
- 虛構折扣
- 虛構價格
- 虛構贈品
- 虛構認證
- 虛構規格


=========================================================
{JIMENG_25_CORE_RULES}
=========================================================


=========================================================
輸出規則
=========================================================

只輸出使用者選擇的功能。

如果選擇「完整流程」：

完整輸出以下內容。


=========================================================
一、商品辨識
=========================================================

品牌：
商品名稱：
商品類型：
包裝與外觀：
圖片可確認資訊：
待人工確認資訊：


=========================================================
二、AI 選品分析
=========================================================

市場需求：
商品吸引力：
競爭程度：
內容製作難度：
合規風險：
推薦分數：0～100
推薦等級：
評分依據：

如果缺少價格、成本、銷量、分潤：

明確標示：
「目前為暫定內容潛力評分。」


=========================================================
三、蝦皮上架文案
=========================================================

商品標題 1：
商品標題 2：
商品標題 3：

短描述：

完整商品描述：

商品特色：

使用方式：

保存方式：

注意事項：

搜尋關鍵字：

商品規格：

待確認資料：


=========================================================
四、TikTok 文案
=========================================================

影片開場：

15 秒口播：

30 秒口播：

TikTok 貼文：

Hashtag：

行動引導：


=========================================================
五、即夢 AI 2.5 生圖
=========================================================

A｜1:1 蝦皮商品主圖

English Prompt：

必須包含：

square 1:1,
premium commercial product photography,
product centered,
clean composition,
realistic materials,
realistic lighting,
original product identity preserved,
original packaging preserved.

Negative Prompt：


B｜9:16 TikTok 商品海報

English Prompt：

必須包含：

vertical 9:16,
product centered,
premium advertising composition,
strong visual hierarchy,
clean background,
original packaging preserved,
original product identity preserved.

Negative Prompt：


C｜商品介紹圖

English Prompt：

必須包含：

product-focused,
premium commercial photography,
close-up product details,
clean premium background,
material details visible,
packaging details visible,
no person,
no hand.

Negative Prompt：


=========================================================
六、即夢 AI 2.5 影片
=========================================================

製作：

9:16 直式商品展示影片。

Video Prompt 必須是完整英文。

Scene 1 — Opening

商品完整出現。
商品置中。
商品清楚可見。

Scene 2 — Product Detail

展示包裝。
展示材質。
展示商品細節。

Scene 3 — Camera Motion

使用：

slow cinematic push-in,
subtle orbit movement,
smooth camera movement,
stable framing.

Scene 4 — Ending

商品重新置中。
穩定定格。
商品保持原貌。

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


=========================================================
七、即夢 AI 2.5 爆款帶貨版本
=========================================================

製作：

9:16 電商帶貨影片。

時間：

0～3 秒：
商品第一視覺。

3～7 秒：
商品細節。

7～12 秒：
商品特色。

12～15 秒：
商品置中結尾。

禁止人物。
禁止手。
禁止主持人。
禁止代言人。

不得自行加入未確認賣點。


=========================================================
八、蝦皮分潤合規檢查
=========================================================

檢查：

商品與圖片是否一致
影片與商品是否一致
文案與商品是否一致
綁定商品是否一致
是否疑似禁止推廣商品
是否可能無法取得分潤
是否含療效宣稱
是否含誇大宣稱
是否存在規格誤判
是否存在錯誤價格
是否存在假贈品
是否使用未確認資訊

最後判斷：

適合發布
或
修改後發布
或
禁止發布

並列出：

必須人工確認項目。


=========================================================
九、最終人工確認清單
=========================================================

可直接使用內容：

必須修改內容：

缺少商品資料：

發布前最後檢查：


=========================================================
最重要
=========================================================

即夢 AI Prompt 必須可以直接複製。

不要輸出：

「你可以」
「建議」
「例如」
「請自行修改」

直接輸出完整 Prompt。

不要把未確認資訊當成事實。

商品圖片中的原始商品永遠是主要參考來源。
"""


# =========================================================
# Gemini
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

            response = client.models.generate_content(

                model=model_name,

                contents=[
                    prompt,
                    image,
                ],

            )

            result = getattr(
                response,
                "text",
                None,
            )

            if result and result.strip():

                return (
                    result.strip(),
                    model_name,
                )

            errors.append(
                f"{model_name}：沒有回傳內容"
            )

        except Exception as error:

            errors.append(
                f"{model_name}：{str(error)}"
            )

    raise RuntimeError(
        "所有 Gemini 模型均無法使用：\n\n"
        + "\n\n".join(errors)
    )


# =========================================================
# 1 商品圖片
# =========================================================

st.subheader(
    "1｜📷 上傳商品圖片"
)

uploaded_file = st.file_uploader(

    "請上傳商品圖片",

    type=[
        "jpg",
        "jpeg",
        "png",
        "webp",
    ],

)


prepared_image = None


if uploaded_file is not None:

    try:

        prepared_image = prepare_image(
            uploaded_file
        )

        st.image(

            prepared_image,

            caption="已上傳商品圖片",

            use_container_width=True,

        )

    except Exception as error:

        st.error(
            "圖片讀取失敗。"
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
        placeholder="不知道可留空",
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
        placeholder="例如：300ml、單瓶、白色",
        height=130,
    )


# =========================================================
# 3 平台
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

)


# =========================================================
# 4 功能
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

    default=[
        "完整流程"
    ],

)


if (
    "完整流程" in selected_items
    and len(selected_items) > 1
):

    st.info(
        "已選擇完整流程，其他選項會自動包含。"
    )


# =========================================================
# 5 啟動
# =========================================================

st.subheader(
    "5｜🚀 開始 AI 分析"
)

start_button = st.button(

    "🚀 啟動 AI 蝦皮半自動化 2.5",

    type="primary",

    use_container_width=True,

)


if start_button:

    api_key = get_api_key()


    if prepared_image is None:

        st.error(
            "請先上傳商品圖片。"
        )


    elif not selected_items:

        st.error(
            "請至少選擇一個 AI 功能。"
        )


    elif not api_key:

        st.error(
            "尚未設定 GEMINI_API_KEY。"
        )


    else:

        product_data = {

            "商品名稱": product_name,

            "商品價格": product_price,

            "商品成本": product_cost,

            "分潤比例": commission_rate,

            "月銷量": monthly_sales,

            "商品評分": product_rating,

            "商品連結": product_url,

            "商品規格": product_spec,

            "目標平台": target_platform,

        }


        if "完整流程" in selected_items:

            effective_items = [
                "完整流程"
            ]

        else:

            effective_items = selected_items


        prompt = build_prompt(

            product_data,

            effective_items,

        )


        try:

            with st.spinner(

                "🤖 AI 正在辨識商品、分析選品並生成即夢 AI 2.5 指令……"

            ):

                result, used_model = (
                    analyze_with_gemini(

                        api_key=api_key,

                        prompt=prompt,

                        image=prepared_image,

                    )
                )


            st.success(
                "🎉 AI 分析完成！"
            )


            st.caption(
                f"本次使用模型：{used_model}"
            )


            st.subheader(
                "6｜📊 AI 分析結果"
            )


            st.markdown(
                result
            )


            st.subheader(
                "7｜📋 複製完整結果"
            )


            st.text_area(

                "完整 AI 結果",

                value=result,

                height=700,

            )


            current_time = (
                datetime.now().strftime(
                    "%Y%m%d_%H%M%S"
                )
            )


            file_name = (

                "AI蝦皮半自動化2.5_"

                f"{product_name or '商品分析'}_"

                f"{current_time}.txt"

            )


            st.download_button(

                "⬇️ 下載完整 AI 結果",

                data=result.encode(
                    "utf-8"
                ),

                file_name=file_name,

                mime="text/plain",

                use_container_width=True,

            )


            st.warning(

                "正式發布前，請人工確認商品名稱、"
                "容量、產地、成分、保存期限、"
                "貨源、售價、庫存、組合數、"
                "商品規格及分潤資格。"

            )


        except Exception as error:

            error_text = str(error)

            st.error(
                "Gemini AI 分析失敗。"
            )

            st.code(
                error_text
            )


            if (
                "401" in error_text
                or "API_KEY"
                in error_text.upper()
            ):

                st.warning(
                    "請檢查 GEMINI_API_KEY。"
                )


            elif (
                "429" in error_text
                or "RESOURCE_EXHAUSTED"
                in error_text
            ):

                st.warning(
                    "API 額度或速率限制，請稍後再試。"
                )


            elif (
                "404" in error_text
                or "NOT_FOUND"
                in error_text
            ):

                st.warning(
                    "目前模型名稱或 API 權限可能不正確。"
                )


# =========================================================
# 頁尾
# =========================================================

st.divider()

st.caption(

    "AI 蝦皮半自動化 2.5 PRO｜"

    "會員系統｜"

    "即夢 AI 2.5｜"

    "AI 內容僅供輔助，正式發布前必須人工確認。"

)
