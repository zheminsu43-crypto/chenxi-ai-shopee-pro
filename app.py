import io
import os
import json
import hashlib
import secrets
from pathlib import Path
from datetime import datetime

import streamlit as st
from PIL import Image, ImageOps


# ============================================================
# 基本設定
# ============================================================

APP_NAME = "AI 蝦皮半自動化 2.5 PRO"
GEMINI_MODEL = "gemini-2.5-flash"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MEMBERS_FILE = DATA_DIR / "members.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)

# 預設管理員
ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123456"


# ============================================================
# Streamlit 頁面
# ============================================================

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        margin-bottom: 5px;
    }

    .sub-title {
        color: #777;
        margin-bottom: 20px;
    }

    .member-card {
        padding: 15px;
        border-radius: 12px;
        border: 1px solid rgba(128,128,128,.25);
        margin-bottom: 15px;
    }

    .small-note {
        color: #777;
        font-size: 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# Session State
# ============================================================

DEFAULT_SESSION = {
    "logged_in": False,
    "username": "",
    "name": "",
    "role": "",
    "page": "home",
    "result": "",
}


for key, value in DEFAULT_SESSION.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# 密碼處理
# ============================================================

def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        200000,
    ).hex()

    return f"{salt}${digest}"


def verify_password(password, stored_password):
    try:
        salt, saved_digest = stored_password.split("$", 1)

        check_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            200000,
        ).hex()

        return secrets.compare_digest(
            check_digest,
            saved_digest,
        )

    except Exception:
        return False


# ============================================================
# 會員資料
# ============================================================

def load_members():
    if not MEMBERS_FILE.exists():
        return []

    try:
        data = json.loads(
            MEMBERS_FILE.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(data, list):
            return data

    except Exception:
        return []

    return []


def save_members(members):
    temp_file = MEMBERS_FILE.with_suffix(".tmp")

    temp_file.write_text(
        json.dumps(
            members,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    temp_file.replace(MEMBERS_FILE)


def find_member(username):
    username = username.strip()

    for member in load_members():
        if member.get("username") == username:
            return member

    return None


# ============================================================
# 建立預設管理員
# ============================================================

def ensure_admin():
    members = load_members()

    admin = None

    for member in members:
        if member.get("username") == ADMIN_USERNAME:
            admin = member
            break

    if admin is None:

        members.append(
            {
                "username": ADMIN_USERNAME,
                "password_hash": hash_password(
                    DEFAULT_ADMIN_PASSWORD
                ),
                "name": "系統管理員",
                "email": "",
                "role": "admin",
                "status": "active",
                "membership": "永久",
                "created_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
            }
        )

        save_members(members)


# ============================================================
# 建立會員
# ============================================================

def create_member(
    username,
    password,
    name,
    email,
    role="member",
):
    username = username.strip()

    if not username:
        return False, "請輸入會員帳號。"

    if len(username) < 3:
        return False, "帳號至少需要 3 個字元。"

    if len(username) > 32:
        return False, "帳號最多 32 個字元。"

    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"

    for char in username:
        if char not in allowed:
            return (
                False,
                "帳號只能使用英文、數字、底線、點或連字號。",
            )

    if len(password) < 6:
        return False, "密碼至少需要 6 個字元。"

    if find_member(username) is not None:
        return False, "這個帳號已存在。"

    if role not in ["member", "vip", "admin"]:
        role = "member"

    members = load_members()

    members.append(
        {
            "username": username,
            "password_hash": hash_password(password),
            "name": name.strip() or username,
            "email": email.strip(),
            "role": role,
            "status": "active",

            # 永久會員
            "membership": "永久",

            "created_at": datetime.now().isoformat(
                timespec="seconds"
            ),
        }
    )

    save_members(members)

    return True, "會員建立成功，期限為永久。"


# ============================================================
# 登入
# ============================================================

def login_user(username, password):
    member = find_member(username)

    if member is None:
        return False, "帳號或密碼錯誤。"

    if not verify_password(
        password,
        member.get("password_hash", ""),
    ):
        return False, "帳號或密碼錯誤。"

    if member.get("status") != "active":
        return False, "這個會員帳號目前已被停用。"

    st.session_state.logged_in = True
    st.session_state.username = member.get(
        "username",
        "",
    )
    st.session_state.name = member.get(
        "name",
        member.get("username", ""),
    )
    st.session_state.role = member.get(
        "role",
        "member",
    )
    st.session_state.page = "home"

    return True, "登入成功。"


# ============================================================
# 登出
# ============================================================

def logout_user():
    for key, value in DEFAULT_SESSION.items():
        st.session_state[key] = value


# ============================================================
# Gemini API Key
# ============================================================

def get_gemini_api_key():

    # Streamlit Cloud Secrets
    try:
        key = st.secrets.get(
            "GEMINI_API_KEY",
            "",
        )

        if key:
            return key

    except Exception:
        pass

    # 本機環境變數
    key = os.getenv(
        "GEMINI_API_KEY",
        "",
    )

    return key


# ============================================================
# Gemini Client
# ============================================================

def get_gemini_client():

    try:
        from google import genai

    except ImportError as exc:
        raise RuntimeError(
            "找不到 google-genai。"
            "請確認 requirements.txt 已經安裝。"
        ) from exc

    api_key = get_gemini_api_key()

    if not api_key:
        raise RuntimeError(
            "找不到 GEMINI_API_KEY。"
            "請到 Streamlit Cloud → App Settings → Secrets 設定。"
        )

    return genai.Client(
        api_key=api_key
    )


# ============================================================
# Gemini 圖片＋文字分析
# ============================================================

def ask_gemini(
    prompt,
    image_bytes=None,
    mime_type="image/jpeg",
):
    client = get_gemini_client()

    if image_bytes:

        from google.genai import types

        contents = [
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type,
            ),
            prompt,
        ]

    else:

        contents = prompt

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
    )

    text = getattr(
        response,
        "text",
        None,
    )

    if not text:
        raise RuntimeError(
            "Gemini 沒有回傳內容。"
        )

    return text.strip()


# ============================================================
# 圖片處理
# ============================================================

def prepare_image(uploaded_file):

    raw_data = uploaded_file.getvalue()

    try:

        image = Image.open(
            io.BytesIO(raw_data)
        )

        image = ImageOps.exif_transpose(
            image
        )

        if image.mode not in [
            "RGB",
            "RGBA",
        ]:
            image = image.convert("RGB")

        max_size = 1600

        if max(image.size) > max_size:

            ratio = max_size / max(image.size)

            new_width = max(
                1,
                int(image.width * ratio),
            )

            new_height = max(
                1,
                int(image.height * ratio),
            )

            image = image.resize(
                (
                    new_width,
                    new_height,
                ),
                Image.Resampling.LANCZOS,
            )

        output = io.BytesIO()

        if image.mode == "RGBA":

            image.save(
                output,
                format="PNG",
                optimize=True,
            )

            return (
                output.getvalue(),
                "image/png",
            )

        image.save(
            output,
            format="JPEG",
            quality=92,
            optimize=True,
        )

        return (
            output.getvalue(),
            "image/jpeg",
        )

    except Exception as exc:

        raise RuntimeError(
            f"圖片處理失敗：{exc}"
        ) from exc


# ============================================================
# 即夢 AI 2.5 核心規則
# ============================================================

JIMENG_25_RULES = """
【即夢 AI 2.5 商品原貌鎖定】

1. 使用上傳圖片中的主要商品作為唯一主要商品。
2. 保留商品品牌。
3. 保留商品包裝。
4. 保留商品瓶身、盒子與外觀。
5. 保留商品形狀與比例。
6. 保留商品顏色。
7. 保留商品材質。
8. 保留 Logo。
9. 保留標籤。
10. 保留包裝上的可見文字。
11. 不得自行改品牌。
12. 不得自行改包裝。
13. 不得自行改顏色。
14. 不得自行改形狀。
15. 不得捏造不存在的商品資料。
16. 不確定資訊必須標示「待確認」。

【一致性】

17. 整個畫面只能有一個主要商品。
18. 不得出現第二個相同商品。
19. 不得商品變形。
20. 不得商品融化。
21. 不得商品扭曲。
22. 不得商品漂浮。
23. 不得商品閃爍。
24. 不得商品突然消失。
25. 不得 Logo 變形。
26. 不得包裝文字漂移。

【人物限制】

27. 不要人物。
28. 不要手。
29. 不要手臂。
30. 不要模特兒。
31. 不要主持人。
32. 不要代言人。
33. 不要人體拿商品。
34. 不要人物遮擋商品。

【商業限制】

35. 不要浮水印。
36. 不要錯誤價格。
37. 不要假贈品。
38. 不要錯誤品牌。
39. 不要虛構商品。
40. 不要額外商品。
41. 商品必須是視覺焦點。
42. 使用高品質商業攝影。
43. 適合蝦皮與 TikTok 電商。

【內容合規】

44. 不得虛構功效。
45. 不得誇大療效。
46. 不得虛構認證。
47. 不得虛構銷量。
48. 不得虛構價格。
49. 不得使用無依據的保證性宣稱。

【即夢 AI 2.5 生圖】

50. Prompt 主體使用英文。
51. 商業畫面文字使用繁體中文。
52. 使用 9:16。
53. 商品為畫面視覺中心。
54. 必須輸出 Negative Prompt。

【即夢 AI 2.5 影片】

55. 使用 9:16 直式影片。
56. Opening：完整商品正面、商品置中。
57. Middle：slow push-in / dolly-in。
58. 展示包裝、材質、細節。
59. Camera Motion 平滑穩定。
60. 商品身份全程一致。
61. Ending：商品置中並 freeze frame。
62. 必須輸出 Negative Prompt。
"""


# ============================================================
# AI 完整指令
# ============================================================

def build_master_prompt(product):

    return f"""
你現在是「{APP_NAME}」的核心電商 AI。

請分析使用者提供的商品圖片與商品資料。

==============================
【商品資料】
==============================

商品名稱：
{product["name"]}

商品價格：
{product["price"]}

商品成本：
{product["cost"]}

分潤比例：
{product["commission"]}

月銷量：
{product["sales"]}

商品評分：
{product["rating"]}

商品連結：
{product["url"]}

商品規格：
{product["specs"]}

目標平台：
{product["platform"]}


==============================
【重要資料規則】
==============================

只能根據圖片與使用者提供的資料。

不能自行捏造：
- 品牌
- 規格
- 成分
- 功效
- 認證
- 價格
- 贈品
- 銷量

不知道的資訊請寫：

「待確認」


==============================
【第一部分：商品辨識】
==============================

請輸出：

商品名稱
商品分類
圖片可確認資訊
待確認資訊
主要賣點
目標客群


==============================
【第二部分：AI 選品分析】
==============================

請輸出：

市場定位
目標客群
商品優勢
商品弱點
短影音內容方向
行銷切入點
購買誘因
合規提醒


==============================
【第三部分：蝦皮上架文案】
==============================

請輸出：

SEO 商品標題
短標題
5 個主要賣點
完整商品描述
商品規格
購買提醒
Hashtag


==============================
【第四部分：TikTok 文案】
==============================

請輸出：

3 秒 Hook
15～30 秒口播
TikTok 貼文
CTA
Hashtag


==============================
【第五部分：即夢 AI 2.5 生圖 Prompt】
==============================

嚴格執行以下規則：

{JIMENG_25_RULES}

輸出：

【即夢 AI 2.5 生圖英文 Prompt】

【Negative Prompt】

【繁體中文畫面文字】

【9:16 商業構圖】


==============================
【第六部分：即夢 AI 2.5 影片 Prompt】
==============================

嚴格執行以下規則：

{JIMENG_25_RULES}

輸出：

【即夢 AI 2.5 影片 Prompt】

必須包含：

Opening
Middle
Camera Motion
Lighting
Focus
Product Detail
Product Consistency
Ending Freeze
Negative Prompt


==============================
【第七部分：即夢 AI 2.5 爆款帶貨影片】
==============================

請產生：

0～3 秒：
Hook

3～8 秒：
商品展示

8～15 秒：
商品細節

15～20 秒：
商品賣點

20～25 秒：
CTA

字幕方向


==============================
【第八部分：分潤合規檢查】
==============================

請檢查：

商品價格
商品成本
分潤比例
可能誇大的內容
需要人工確認的內容


==============================
【第九部分：最終 AI 檢查】
==============================

請逐項確認：

1. 是否捏造商品資料
2. 是否有待確認資訊
3. 是否保持商品原貌
4. 是否禁止人物
5. 是否禁止手
6. 是否禁止第二商品
7. 是否禁止變形
8. 是否有 Negative Prompt
9. 是否為 9:16
10. 是否符合即夢 AI 2.5 規則
"""


# ============================================================
# 登入頁
# ============================================================

def render_login_page():

    st.markdown(
        f"""
        <div class="main-title">
        🛒 {APP_NAME}
        </div>

        <div class="sub-title">
        永久會員｜管理員｜Gemini 2.5 Flash｜即夢 AI 2.5
        </div>
        """,
        unsafe_allow_html=True,
    )

    login_tab, register_tab = st.tabs(
        [
            "🔐 會員登入",
            "📝 會員註冊",
        ]
    )

    # --------------------------
    # 登入
    # --------------------------

    with login_tab:

        with st.form("login_form"):

            username = st.text_input(
                "會員帳號"
            )

            password = st.text_input(
                "會員密碼",
                type="password",
            )

            submitted = st.form_submit_button(
                "登入",
                use_container_width=True,
            )

        if submitted:

            ok, message = login_user(
                username,
                password,
            )

            if ok:

                st.success(message)
                st.rerun()

            else:

                st.error(message)

        st.info(
            "預設管理員帳號：admin"
        )

    # --------------------------
    # 註冊
    # --------------------------

    with register_tab:

        with st.form("register_form"):

            username = st.text_input(
                "新會員帳號"
            )

            name = st.text_input(
                "姓名 / 暱稱"
            )

            email = st.text_input(
                "Email"
            )

            password = st.text_input(
                "密碼",
                type="password",
            )

            password2 = st.text_input(
                "再次輸入密碼",
                type="password",
            )

            submitted = st.form_submit_button(
                "註冊永久會員",
                use_container_width=True,
            )

        if submitted:

            if password != password2:

                st.error(
                    "兩次密碼不一致。"
                )

            else:

                ok, message = create_member(
                    username,
                    password,
                    name,
                    email,
                    "member",
                )

                if ok:

                    st.success(message)

                else:

                    st.error(message)


# ============================================================
# Sidebar
# ============================================================

def render_sidebar():

    with st.sidebar:

        st.markdown(
            f"## 🛒 {APP_NAME}"
        )

        st.markdown(
            f"""
            <div class="member-card">
            👤 <b>{st.session_state.name}</b><br>
            帳號：{st.session_state.username}<br>
            權限：{st.session_state.role}<br>
            會員期限：<b>永久</b>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button(
            "🏠 AI 自動化",
            use_container_width=True,
        ):

            st.session_state.page = "home"
            st.rerun()

        if st.session_state.role == "admin":

            if st.button(
                "👑 管理員中心",
                use_container_width=True,
            ):

                st.session_state.page = "admin"
                st.rerun()

        st.divider()

        if st.button(
            "🚪 登出",
            use_container_width=True,
        ):

            logout_user()
            st.rerun()


# ============================================================
# 管理員中心
# ============================================================

def render_admin_page():

    st.title(
        "👑 管理員中心"
    )

    st.caption(
        "永久會員制：沒有到期日期，管理員可以手動啟用或停用。"
    )

    members = load_members()

    total_members = len(members)

    active_members = sum(
        1
        for member in members
        if member.get("status") == "active"
    )

    admin_count = sum(
        1
        for member in members
        if member.get("role") == "admin"
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "會員總數",
        total_members,
    )

    col2.metric(
        "啟用會員",
        active_members,
    )

    col3.metric(
        "管理員",
        admin_count,
    )

    st.divider()

    # ========================================================
    # 建立會員
    # ========================================================

    st.subheader(
        "➕ 建立永久會員"
    )

    with st.form(
        "admin_create_member"
    ):

        col1, col2 = st.columns(2)

        with col1:

            username = st.text_input(
                "會員帳號"
            )

            name = st.text_input(
                "姓名 / 暱稱"
            )

        with col2:

            password = st.text_input(
                "會員密碼",
                type="password",
            )

            email = st.text_input(
                "Email"
            )

        role = st.selectbox(
            "會員等級",
            [
                "member",
                "vip",
                "admin",
            ],
            format_func=lambda value: {
                "member": "一般會員",
                "vip": "VIP 會員",
                "admin": "管理員",
            }[value],
        )

        submitted = st.form_submit_button(
            "建立永久會員",
            use_container_width=True,
        )

    if submitted:

        ok, message = create_member(
            username,
            password,
            name,
            email,
            role,
        )

        if ok:

            st.success(message)
            st.rerun()

        else:

            st.error(message)

    st.divider()

    # ========================================================
    # 會員列表
    # ========================================================

    st.subheader(
        "👥 會員管理"
    )

    members = load_members()

    if not members:

        st.ision = st.text_input("分潤比例")
        sales = st.text_input("月銷量數據")
        rating = st.text_input("商品評分")
        specs = st.text_area("詳細規格/特點")
        platform = st.selectbox("目標上架平台", ["蝦皮購物", "TikTok 電商", "雙平台通用"])
        uploaded_file = st.file_uploader("上傳商品照片", type=["jpg", "jpeg", "png", "webp"])

    with col2:
        if st.button("🚀 開始全自動分析與文案生成", use_container_width=True, type="primary"):
            if not name:
                st.warning("⚠️ 請輸入商品名稱！")
            else:
                product_info = {
                    "name": name, "price": price or "待確認", "cost": cost or "待確認",
                    "commission": commission or "待確認", "sales": sales or "待確認",
                    "rating": rating or "待確認", "specs": specs or "待確認", "platform": platform,
                }
                img_obj = process_image(uploaded_file) if uploaded_file else None
                with st.spinner("AI 正在分析生成中..."):
                    try:
                        prompt_text = build_ai_prompt(product_info)
                        st.session_state.result = ask_gemini(prompt_text, img_obj)
                        st.success("✅ 生成完畢！")
                    except Exception as e:
                        st.error(f"❌ 生成失敗：{e}")

        if st.session_state.result:
            st.text_area("生成結果", st.session_state.result, height=500)

def admin_page():
    st.title("👑 管理員中心")
    members = load_members()
    st.write(f"目前註冊總人數：{len(members)}")
    for m in members:
        st.write(f"- 帳號: {m['username']} | 權限: {m['role']} | 狀態: {m['status']}")

# ============================================================
# 主入口
# ============================================================

def main():
    ensure_admin()
    if not st.session_state.logged_in:
        login_page()
    else:
        sidebar()
        if st.session_state.page == "admin" and st.session_state.role == "admin":
            admin_page()
        else:
            home_page()

if __name__ == "__main__":
    main()
