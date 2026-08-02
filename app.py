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
# Gemini / ChatGPT 說明：兩者不是可直接拿來當第三方註冊的通用 OAuth
# =========================================================

st.set_page_config(
    page_title="AI 蝦皮半自動化 2.5 PRO",
    page_icon="🛒",
    layout="wide",
)

MODEL_CANDIDATES = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]

MAX_IMAGE_SIZE = 1600
DEFAULT_MEMBER_DAYS = 30


# =========================================================
# Secrets 工具
# =========================================================

def secret(name, default=""):
    try:
        value = st.secrets.get(name, default)
        return str(value).strip()
    except Exception:
        return default


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
        return secrets.compare_digest(digest, saved_hash)
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
            f"Supabase 錯誤 {response.status_code}: {response.text}"
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


def find_member_by_provider(provider, provider_user_id):
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

    if provider != "password" and provider_user_id:
        if find_member_by_provider(provider, provider_user_id):
            return False, "此第三方帳號已註冊。"

    expires = (
        date.today()
        + timedelta(days=DEFAULT_MEMBER_DAYS)
    ).isoformat()

    data = {
        "username": username,
        "password_hash": hash_password(password) if password else "",
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
        headers_extra={"Prefer": "return=representation"},
    )

    if rows:
        return True, rows[0]

    return False, "會員建立失敗。"


def create_social_member(
    provider,
    provider_user_id,
    name,
    email,
):
    # 第三方註冊不需要讓使用者再設定網站密碼。
    safe_base = re.sub(
        r"[^a-z0-9_]",
        "",
        (email.split("@")[0] if email else name).lower(),
    )[:20]

    if not safe_base:
        safe_base = f"{provider}_member"

    username = f"{safe_base}_{secrets.token_hex(3)}"

    return create_member(
        username=username,
        password="",
        name=name or f"{provider} 會員",
        email=email,
        provider=provider,
        provider_user_id=provider_user_id,
    )


def update_member(member_id, updates):
    return supabase_request(
        "PATCH",
        "members",
        params={"id": f"eq.{member_id}"},
        json_data=updates,
        headers_extra={"Prefer": "return=representation"},
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

    if str(member.get("status", "active")).lower() != "active":
        return False, "disabled"

    saved_hash = str(member.get("password_hash", ""))

    if not saved_hash or not verify_password(password, saved_hash):
        return False, "invalid"

    expires_text = str(member.get("expires", ""))

    try:
        expires_date = date.fromisoformat(expires_text)
    except Exception:
        return False, "invalid_date"

    if date.today() > expires_date:
        return False, "expired"

    return True, member


# =========================================================
# OAuth / 第三方入口
# =========================================================

def oauth_url(provider):
    """
    使用 Supabase Auth 的標準 authorize endpoint。
    Google 可直接使用內建 provider。
    LINE / WeChat 請在 Supabase Custom OAuth/OIDC Provider
    建立 custom:line / custom:wechat 後，把 provider 名稱放入 Secrets。
    """
    supabase_url, anon_key = get_supabase_config()

    if not supabase_url or not anon_key:
        return None

    app_url = get_app_url()
    if not app_url:
        return None

    provider_map = {
        "google": secret("SUPABASE_GOOGLE_PROVIDER", "google"),
        "line": secret("SUPABASE_LINE_PROVIDER", "custom:line"),
        "wechat": secret("SUPABASE_WECHAT_PROVIDER", "custom:wechat"),
    }

    provider_id = provider_map.get(provider)
    if not provider_id:
        return None

    # OAuth callback 由 Supabase Auth 處理。
    # 最終需將使用者導回 APP_URL。
    return (
        f"{supabase_url}/auth/v1/authorize"
        f"?provider={provider_id}"
        f"&redirect_to={app_url}"
    )


def social_buttons():
    st.markdown("### 🌐 第三方註冊 / 登入")

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
        "ChatGPT / Gemini 不能直接當成一般網站的第三方會員登入按鈕；"
        "Gemini 使用 Google 帳號登入，ChatGPT 帳號則不等同於可供你的網站使用的通用 OAuth 登入。"
    )


# =========================================================
# Session
# =========================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "page" not in st.session_state:
    st.session_state.page = "login"


def logout():
    st.session_state.logged_in = False
    st.session_state.pop("username", None)
    st.session_state.pop("member", None)
    st.session_state.page = "login"
    st.rerun()


# =========================================================
# CSS
# =========================================================

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
        opacity:.75;
        margin-bottom:30px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# 登入
# =========================================================

def login_page():
    st.markdown(
        '<div class="main-title">🛒 AI 蝦皮半自動化 2.5 PRO</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="main-subtitle">'
        '會員登入｜Google｜LINE｜WeChat｜AI 商品分析｜即夢 AI 2.5'
        '</div>',
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1, 2, 1])

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
                st.error("請輸入會員帳號與密碼。")
            else:
                try:
                    success, result = check_login(
                        username,
                        password,
                    )

                    if success:
                        st.session_state.logged_in = True
                        st.session_state.username = username.strip().lower()
                        st.session_state.member = result
                        st.session_state.page = "main"
                        st.rerun()

                    messages = {
                        "expired": "⛔ 會員資格已到期，請聯絡管理員續期。",
                        "disabled": "⛔ 此會員帳號目前已停權。",
                        "invalid_date": "⛔ 會員到期日資料錯誤。",
                        "invalid": "❌ 帳號或密碼錯誤。",
                    }
                    st.error(messages.get(result, "❌ 登入失敗。"))

                except Exception as error:
                    st.error("會員系統連線失敗。")
                    st.code(str(error))

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
# 註冊
# =========================================================

def register_page():
    st.markdown(
        '<div class="main-title">📝 會員註冊</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="main-subtitle">'
        '建立 AI 蝦皮半自動化 2.5 PRO 會員帳號'
        '</div>',
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1, 2, 1])

    with center:
        st.subheader("👤 建立會員帳號")

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
            username_clean = username.strip().lower()
            email_clean = email.strip().lower()

            if not name.strip():
                st.error("請輸入姓名或暱稱。")
            elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email_clean):
                st.error("請輸入正確 Email。")
            elif not re.fullmatch(r"[a-z0-9_]{3,30}", username_clean):
                st.error("帳號只能使用小寫英數字與底線，長度 3～30。")
            elif len(password) < 6:
                st.error("密碼至少需要 6 個字元。")
            elif password != password_confirm:
                st.error("兩次輸入的密碼不一致。")
            else:
                try:
                    success, result = create_member(
                        username_clean,
                        password,
                        name,
                        email_clean,
                    )

                    if success:
                        st.success("🎉 會員帳號建立成功！")
                        st.info(
                            f"會員資格預設 {DEFAULT_MEMBER_DAYS} 天，請返回登入。"
                        )
                    else:
                        st.error(str(result))
                except Exception as error:
                    st.error("註冊失敗。")
                    st.code(str(error))

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

current_username = st.session_state.get("username", "")
current_member = st.session_state.get("member", {})

try:
    latest_member = find_member(current_username)
    if latest_member:
        current_member = latest_member
        st.session_state.member = latest_member
except Exception:
    pass

member_id = current_member.get("id", "")
member_name = str(current_member.get("name", current_username))
member_email = str(current_member.get("email", ""))
member_role = str(current_member.get("role", "member"))
member_status = str(current_member.get("status", "active"))
member_expires = str(current_member.get("expires", ""))

try:
    expire_date = date.fromisoformat(member_expires)
    remaining_days = (expire_date - date.today()).days
except Exception:
    remaining_days = -999

if member_status.lower() != "active":
    logout()

if remaining_days < 0:
    st.error("⛔ 會員資格已到期。")
    st.info("請聯絡管理員續期後再使用系統。")
    if st.button("🚪 返回登入", type="primary"):
        logout()
    st.stop()


# =========================================================
# 側邊欄
# =========================================================

with st.sidebar:
    st.markdown("## 👤 會員中心")
    st.success(f"會員：{member_name}")
    st.write(f"帳號：**{current_username}**")

    if member_email:
        st.write(f"Email：**{member_email}**")

    st.write(f"等級：**{member_role}**")
    st.write(f"註冊方式：**{current_member.get('provider', 'password')}**")
    st.write(f"到期日：**{member_expires}**")

    if remaining_days == 0:
        st.warning("⚠️ 今天為最後使用日")
    elif remaining_days <= 7:
        st.warning(f"⚠️ 剩餘 {remaining_days} 天")
    else:
        st.info(f"⏳ 剩餘 {remaining_days} 天")

    st.divider()

    if st.button("🚪 登出", use_container_width=True):
        logout()


# =========================================================
# 管理員
# =========================================================

def admin_panel():
    st.header("👑 管理員中心")

    try:
        members = get_all_members()
    except Exception as error:
        st.error("會員資料庫讀取失敗。")
        st.code(str(error))
        return

    st.write(f"目前會員數：**{len(members)}**")

    for member in members:
        mid = member.get("id", "")
        username = member.get("username", "")
        name = member.get("name", "")
        email = member.get("email", "")
        role = member.get("role", "member")
        status = member.get("status", "active")
        expires = member.get("expires", "")
        provider = member.get("provider", "password")

        with st.expander(f"👤 {name}｜{username}"):
            st.write(f"Email：**{email}**")
            st.write(f"註冊方式：**{provider}**")
            st.write(f"身份：**{role}**")
            st.write(f"狀態：**{status}**")
            st.write(f"到期：**{expires}**")

            new_status = st.selectbox(
                "會員狀態",
                ["active", "disabled"],
                index=0 if status == "active" else 1,
                key=f"status_{mid}",
            )

            roles = ["member", "vip", "admin"]
            new_role = st.selectbox(
                "會員等級",
                roles,
                index=roles.index(role) if role in roles else 0,
                key=f"role_{mid}",
            )

            try:
                expire_value = date.fromisoformat(expires)
            except Exception:
                expire_value = date.today()

            new_expire = st.date_input(
                "會員到期日",
                value=expire_value,
                key=f"expire_{mid}",
            )

            c1, c2, c3 = st.columns(3)

            with c1:
                if st.button("💾 儲存", key=f"save_{mid}", use_container_width=True):
                    update_member(
                        mid,
                        {
                            "status": new_status,
                            "role": new_role,
                            "expires": new_expire.isoformat(),
                        },
                    )
                    st.success("已更新。")
                    st.rerun()

            with c2:
                if st.button("➕ 延長 30 天", key=f"extend_{mid}", use_container_width=True):
                    try:
                        d = date.fromisoformat(expires)
                    except Exception:
                        d = date.today()

                    if d < date.today():
                        d = date.today()

                    new_date = d + timedelta(days=30)

                    update_member(
                        mid,
                        {
                            "expires": new_date.isoformat(),
                            "status": "active",
                        },
                    )
                    st.success(f"已延長至 {new_date.isoformat()}")
                    st.rerun()

            with c3:
                if username != current_username:
                    if st.button("⛔ 停權", key=f"disable_{mid}", use_container_width=True):
                        update_member(mid, {"status": "disabled"})
                        st.warning("會員已停權。")
                        st.rerun()


# =========================================================
# 主標題
# =========================================================

st.markdown(
    '<div class="main-title">🛒 AI 蝦皮半自動化 2.5 PRO</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-subtitle">'
    '商品辨識｜AI 選品｜蝦皮文案｜TikTok｜即夢 AI 2.5｜分潤合規'
    '</div>',
    unsafe_allow_html=True,
)

if member_role.lower() == "admin":
    with st.expander("👑 管理員中心"):
        admin_panel()

    st.divider()


# =========================================================
# Gemini
# =========================================================

def get_api_key():
    key = secret("GEMINI_API_KEY")
    return key or None


def prepare_image(uploaded_file):
    uploaded_file.seek(0)
    image = Image.open(uploaded_file)
    image = ImageOps.exif_transpose(image)

    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")

    image.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE))

    if image.mode == "RGBA":
        background = Image.new("RGB", image.size, "white")
        background.paste(
            image,
            mask=image.getchannel("A"),
        )
        image = background

    return image


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

即夢 Prompt 本體使用英文。

不得自行創造未確認商品資訊。

影片全程保持同一商品身份。

推薦：
slow cinematic push-in,
subtle orbit movement,
smooth camera movement,
stable framing.
"""


def build_prompt(data, selected_items):
    selected_text = "、".join(selected_items)

    return f"""
你是專業電商 AI 營運助手。

請分析使用者上傳的商品圖片及商品資料。

一般說明使用繁體中文。
「即夢 AI 2.5 生圖 Prompt」與「即夢 AI 2.5 影片 Prompt」必須使用英文。

【商品資料】

商品名稱：{data["商品名稱"] or "待確認"}
商品價格：{data["商品價格"] or "待確認"}
商品成本：{data["商品成本"] or "待確認"}
分潤比例：{data["分潤比例"] or "待確認"}
月銷量：{data["月銷量"] or "待確認"}
商品評分：{data["商品評分"] or "待確認"}
商品連結：{data["商品連結"] or "待確認"}
商品規格：{data["商品規格"] or "待確認"}
目標平台：{data["目標平台"]}
使用者選擇：{selected_text}

【商品辨識保護】

只能根據圖片與使用者資料判斷。

無法確認必須寫「待確認」。

禁止虛構：
品牌、容量、成分、產地、功效、價格、贈品、認證、規格、保存期限、折扣、銷量。

圖片中有多個商品時，選擇最大、最清楚、品牌辨識度最高者作主要商品。

無法確認單品、組合或套裝時，標示「待人工確認」。

【文案合規】

不要使用：
第一、最強、最好、100%、保證有效、永久、無敵、神效、速效、治療、根治、醫療級。

禁止疾病治療、醫療療效、虛構折扣、虛構價格、虛構贈品、虛構認證、虛構規格。

{JIMENG_25_CORE_RULES}

【輸出】

只輸出使用者選擇的功能。

若選擇「完整流程」，輸出：

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

若缺少價格、成本、銷量、分潤，標示：
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
商品完整出現、置中、清楚。

Scene 2 — Product Detail
展示包裝、材質、商品細節。

Scene 3 — Camera Motion
slow cinematic push-in,
subtle orbit movement,
smooth camera movement,
stable framing.

Scene 4 — Ending
商品重新置中、穩定定格、保持原貌。

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

0～3 秒：商品第一視覺
3～7 秒：商品細節
7～12 秒：商品特色
12～15 秒：商品置中結尾

禁止人物、手、主持人、代言人。
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
適合發布 / 修改後發布 / 禁止發布

並列出必須人工確認項目。

九、最終人工確認清單
- 可直接使用內容
- 必須修改內容
- 缺少商品資料
- 發布前最後檢查事項

即夢 Prompt 必須可以直接複製。
不要輸出「你可以」「建議」「例如」「請自行修改」。
不要把未確認資訊當成事實。
商品圖片中的原始商品永遠是主要參考來源。
"""


def analyze_with_gemini(api_key, prompt, image):
    client = genai.Client(api_key=api_key)
    errors = []

    for model_name in MODEL_CANDIDATES:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[prompt, image],
            )

            result = getattr(response, "text", None)

            if result and result.strip():
                return result.strip(), model_name

            errors.append(f"{model_name}：沒有回傳內容")

        except Exception as error:
            errors.append(f"{model_name}：{str(error)}")

    raise RuntimeError(
        "所有 Gemini 模型均無法使用：\n\n"
        + "\n\n".join(errors)
    )


# =========================================================
# 商品圖片
# =========================================================

st.subheader("1｜📷 上傳商品圖片")

uploaded_file = st.file_uploader(
    "請上傳商品圖片",
    type=["jpg", "jpeg", "png", "webp"],
)

prepared_image = None

if uploaded_file is not None:
    try:
        prepared_image = prepare_image(uploaded_file)
        st.image(
            prepared_image,
            caption="已上傳商品圖片",
            use_container_width=True,
        )
    except Exception as error:
        st.error("圖片讀取失敗。")
        st.code(str(error))


# =========================================================
# 商品資料
# =========================================================

st.subheader("2｜📦 商品資料")

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
# 平台
# =========================================================

st.subheader("3｜🎯 目標平台")

target_platform = st.radio(
    "目標平台",
    ["蝦皮", "TikTok", "蝦皮＋TikTok"],
    horizontal=True,
)


# =========================================================
# 功能
# =========================================================

st.subheader("4｜🤖 AI 功能")

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
)

if "完整流程" in selected_items and len(selected_items) > 1:
    st.info("已選擇完整流程，系統會自動包含全部內容。")


# =========================================================
# 啟動
# =========================================================

st.subheader("5｜🚀 開始 AI 分析")

if st.button(
    "🚀 啟動 AI 蝦皮半自動化 2.5",
    type="primary",
    use_container_width=True,
):
    api_key = get_api_key()

    if prepared_image is None:
        st.error("請先上傳商品圖片。")

    elif not selected_items:
        st.error("請至少選擇一個 AI 功能。")

    elif not api_key:
        st.error("尚未設定 GEMINI_API_KEY。")

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

        effective_items = (
            ["完整流程"]
            if "完整流程" in selected_items
            else selected_items
        )

        prompt = build_prompt(
            product_data,
            effective_items,
        )

        try:
            with st.spinner(
                "🤖 AI 正在辨識商品、分析選品並生成即夢 AI 2.5 指令……"
            ):
                result, used_model = analyze_with_gemini(
                    api_key=api_key,
                    prompt=prompt,
                    image=prepared_image,
                )

            st.success("🎉 AI 分析完成！")
            st.caption(f"本次使用模型：{used_model}")

            st.subheader("6｜📊 AI 分析結果")
            st.markdown(result)

            st.subheader("7｜📋 複製完整結果")

            st.text_area(
                "完整 AI 結果",
                value=result,
                height=700,
            )

            current_time = datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )

            file_name = (
                f"AI蝦皮半自動化2.5_"
                f"{product_name or '商品分析'}_"
                f"{current_time}.txt"
            )

            st.download_button(
                "⬇️ 下載完整 AI 結果",
                data=result.encode("utf-8"),
                file_name=file_name,
                mime="text/plain",
                use_container_width=True,
            )

            st.warning(
                "正式發布前，請人工確認商品名稱、容量、產地、"
                "成分、保存期限、貨源、售價、庫存、組合數、"
                "商品規格及分潤資格。"
            )

        except Exception as error:
            error_text = str(error)

            st.error("Gemini AI 分析失敗。")
            st.code(error_text)

            if (
                "401" in error_text
                or "API_KEY" in error_text.upper()
            ):
                st.warning("請檢查 GEMINI_API_KEY。")

            elif (
                "429" in error_text
                or "RESOURCE_EXHAUSTED" in error_text
            ):
                st.warning("API 額度或速率限制，請稍後再試。")

            elif (
                "404" in error_text
                or "NOT_FOUND" in error_text
            ):
                st.warning("模型名稱或 API 權限可能不正確。")


# =========================================================
# 頁尾
# =========================================================

st.divider()

st.caption(
    "AI 蝦皮半自動化 2.5 PRO｜會員系統｜"
    "Google / LINE / WeChat 入口｜即夢 AI 2.5｜"
    "AI 內容僅供輔助，正式發布前必須人工確認。"
)
