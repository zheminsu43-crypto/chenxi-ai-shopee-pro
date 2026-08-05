import io
import os
import json
import re
import hashlib
import secrets
from datetime import datetime
from pathlib import Path

import streamlit as st
from PIL import Image, ImageOps


# ============================================================
# AI 蝦皮半自動化 2.5 PRO
# ============================================================

APP_NAME = "AI 蝦皮半自動化 2.5 PRO"
GEMINI_MODEL = "gemini-2.5-flash"

DATA_DIR = Path("data")
MEMBERS_FILE = DATA_DIR / "members.json"

DATA_DIR.mkdir(exist_ok=True)


# ============================================================
# 管理員初始設定
# ============================================================

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD",
    "admin123456"
)


# ============================================================
# 即夢 AI 2.5 核心規則
# ============================================================

JIMENG_25_CORE_RULES = """
你是即夢 AI 2.5 商業商品 Prompt 專家。

【商品原貌鎖定】
1. 使用使用者上傳圖片中的主要商品作為唯一主要商品。
2. 保留商品品牌、包裝、瓶身、盒子、形狀、比例、顏色、
   材質、Logo、標籤、印刷文字、結構與視覺識別。
3. 不得自行改變商品品牌。
4. 不得自行改變商品包裝。
5. 不得自行改變商品顏色。
6. 不得自行改變商品形狀。
7. 不得自行創造不存在的商品資訊。
8. 不知道的資訊必須寫「待確認」。
9. 不得產生第二個相同商品。
10. 不得讓商品融化、變形、扭曲、漂浮、閃爍或消失。
11. 不得讓 Logo、標籤、包裝文字變形或漂移。
12. 商品在所有鏡頭中必須維持同一身份與外觀。

【人物限制】
13. 不要人物。
14. 不要手。
15. 不要手臂。
16. 不要主持人。
17. 不要模特兒。
18. 不要代言人。
19. 不要人體拿商品。
20. 不要人物遮擋商品。

【畫面限制】
21. 不要浮水印。
22. 不要錯誤價格。
23. 不要假贈品。
24. 不要錯誤品牌。
25. 不要虛構商品。
26. 不要額外商品。
27. 不要背景搶走商品主體。

【商業內容】
28. 商品必須是畫面視覺焦點。
29. 使用高品質商業攝影。
30. 適合蝦皮與 TikTok 電商內容。
31. 不得誇大療效。
32. 不得虛構功效。
33. 不得虛構認證。
34. 不得虛構銷量。
35. 不得虛構價格。
36. 不得使用沒有依據的保證性宣稱。

【即夢 2.5 生圖】
37. 主要 Prompt 使用英文。
38. 畫面商業文字使用繁體中文。
39. 必須維持 product identity consistency。
40. 必須包含商品、場景、燈光、材質、構圖、鏡頭。
41. 必須提供 Negative Prompt。
42. 以 9:16 商業畫面為主要方向。

【即夢 2.5 影片】
43. 使用 9:16 直式短影片。
44. Opening：完整商品正面展示，商品置中。
45. Middle：slow push-in / dolly-in。
46. 展示包裝、材質、商品細節。
47. Camera Motion 必須平滑。
48. 商品全程保持同一身份。
49. Ending：商品置中並定格。
50. 必須描述 Lighting。
51. 必須描述 Focus。
52. 必須描述 Camera Motion。
53. 必須描述 Product Consistency。
54. 必須提供 Negative Prompt。
"""


# ============================================================
# Streamlit
# ============================================================

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🛒",
    layout="wide",
)


# ============================================================
# Session State
# ============================================================

DEFAULT_STATE = {
    "logged_in": False,
    "username": "",
    "name": "",
    "role": "",
    "page": "home",
    "result": "",
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
    }

    .sub-title {
        color: #777;
        margin-bottom: 20px;
    }

    .member-box {
        padding: 12px;
        border-radius: 12px;
        border: 1px solid rgba(128,128,128,.25);
        margin-bottom: 15px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 密碼
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


def verify_password(password, stored):
    try:
        salt, digest = stored.split("$", 1)
        check = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            200000,
        ).hex()
        return secrets.compare_digest(check, digest)
    except Exception:
        return False


# ============================================================
# 會員資料
# ============================================================

def load_members():
    if not MEMBERS_FILE.exists():
        return []

    try:
        data = json.loads(MEMBERS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:
        pass

    return []


def save_members(members):
    temp_file = MEMBERS_FILE.with_suffix(".tmp")
    temp_file.write_text(
        json.dumps(members, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_file.replace(MEMBERS_FILE)


def ensure_admin():
    members = load_members()
    admin = next((m for m in members if m.get("username") == ADMIN_USERNAME), None)

    if admin is None:
        members.append(
            {
                "username": ADMIN_USERNAME,
                "password_hash": hash_password(ADMIN_PASSWORD),
                "name": "系統管理員",
                "email": "",
                "role": "admin",
                "status": "active",
                "membership": "永久",
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        save_members(members)


def find_member(username):
    for member in load_members():
        if member.get("username") == username.strip():
            return member
    return None


def create_member(username, password, name, email, role="member"):
    username = username.strip()

    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", username):
        return (False, "帳號必須 3～32 字元，只能使用英文、數字、底線、點或連字號。")

    if len(password) < 6:
        return (False, "密碼至少 6 個字元。")

    if find_member(username):
        return (False, "帳號已存在。")

    if role not in ("member", "vip", "admin"):
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
            "membership": "永久",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    save_members(members)

    return (True, "會員建立成功，期限為永久。")


# ============================================================
# 登入
# ============================================================

def do_login(username, password):
    member = find_member(username)

    if member is None:
        return (False, "帳號或密碼錯誤。")

    if not verify_password(password, member.get("password_hash", "")):
        return (False, "帳號或密碼錯誤。")

    if member.get("status") != "active":
        return (False, "此會員目前已被停用。")

    st.session_state.logged_in = True
    st.session_state.username = member["username"]
    st.session_state.name = member.get("name", member["username"])
    st.session_state.role = member.get("role", "member")
    st.session_state.page = "home"

    return (True, "登入成功。")


def do_logout():
    for key, value in DEFAULT_STATE.items():
        st.session_state[key] = value


# ============================================================
# Gemini
# ============================================================

def get_gemini_client():
    try:
        from google import genai
    except ImportError:
        raise RuntimeError("沒有安裝 google-genai，請先執行 pip install google-genai")

    api_key = ""
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        pass

    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY", "")

    if not api_key:
        raise RuntimeError("找不到 GEMINI_API_KEY，請於 Secrets 或環境變數中設定。")

    return genai.Client(api_key=api_key)


def ask_gemini(prompt, image_bytes=None, mime_type="image/jpeg"):
    client = get_gemini_client()
    contents = [prompt]

    if image_bytes:
        from google.genai import types
        contents.append(
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type,
            )
        )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
    )

    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini 沒有回傳結果。")

    return text.strip()


# ============================================================
# 圖片處理
# ============================================================

def process_image(uploaded_file):
    raw = uploaded_file.getvalue()
    try:
        image = Image.open(io.BytesIO(raw))
        image = ImageOps.exif_transpose(image)

        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")

        max_size = 1600
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            image = image.resize(
                (
                    max(1, int(image.width * ratio)),
                    max(1, int(image.height * ratio)),
                ),
                Image.Resampling.LANCZOS,
            )

        output = io.BytesIO()
        if image.mode == "RGBA":
            image.save(output, format="PNG")
            return (output.getvalue(), "image/png")

        image.save(output, format="JPEG", quality=92)
        return (output.getvalue(), "image/jpeg")

    except Exception as exc:
        raise RuntimeError(f"圖片處理失敗：{exc}")


# ============================================================
# AI 完整自動化
# ============================================================

def build_ai_prompt(product):
    return f"""
你現在是「{APP_NAME}」的核心 AI。

請分析使用者提供的商品圖片與資料。

【商品資料】

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


==================================================
第一部分：商品辨識
==================================================

輸出：

商品名稱
商品分類
圖片可確認資訊
待確認資訊
主要賣點
目標客群


==================================================
第二部分：AI 選品分析
==================================================

輸出：

市場定位
目標族群
商品優勢
商品弱點
內容行銷方向
適合短影音的賣點
合規提醒


==================================================
第三部分：蝦皮上架文案
==================================================

產生：

SEO 商品標題
短標題
5 個主要賣點
完整商品描述
商品規格
購買提醒
Hashtag

不得虛構任何商品資料。


==================================================
第四部分：TikTok 文案
==================================================

產生：

3 秒 Hook
15～30 秒口播
TikTok 貼文
CTA
Hashtag


==================================================
第五部分：即夢 AI 2.5 生圖
==================================================

請嚴格遵守：

{JIMENG_25_CORE_RULES}

輸出：

【即夢 AI 2.5 生圖英文 Prompt】

【Negative Prompt】

【繁體中文畫面文字】

【9:16 商業構圖】


==================================================
第六部分：即夢 AI 2.5 影片
==================================================

請嚴格遵守：

{JIMENG_25_CORE_RULES}

影片必須包含：

Opening
Middle
Camera Motion
Lighting
Focus
Product Detail
Product Consistency
Ending Freeze
Negative Prompt

影片設定：

9:16
商業電商短影音
商品唯一主體
無人物
無手
無第二商品


==================================================
第七部分：爆款帶貨影片腳本
==================================================

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

另外提供字幕方向。


==================================================
第八部分：分潤合規檢查
==================================================

檢查：

價格
成本
分潤比例
可能的誇大宣稱
需要人工確認的內容


==================================================
第九部分：AI 最終檢查
==================================================

請確認：

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

def login_page():
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

    login_tab, register_tab = st.tabs(["🔐 會員登入", "📝 會員註冊"])

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("會員帳號")
            password = st.text_input("會員密碼", type="password")
            submit = st.form_submit_button("登入", use_container_width=True)

        if submit:
            ok, msg = do_login(username, password)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

        st.info(f"測試管理員：{ADMIN_USERNAME} / {ADMIN_PASSWORD}")

    with register_tab:
        with st.form("register_form"):
            username = st.text_input("新會員帳號")
            name = st.text_input("姓名 / 暱稱")
            email = st.text_input("Email")
            password = st.text_input("密碼", type="password")
            password2 = st.text_input("再次輸入密碼", type="password")
            submit = st.form_submit_button("註冊永久會員", use_container_width=True)

        if submit:
            if password != password2:
                st.error("兩次密碼不一致。")
            else:
                ok, msg = create_member(username, password, name, email)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)


# ============================================================
# Sidebar
# ============================================================

def sidebar():
    with st.sidebar:
        st.markdown(f"## 🛒 {APP_NAME}")
        st.markdown(
            f"""
            <div class="member-box">
            👤 <b>{st.session_state.name}</b><br>
            權限：{st.session_state.role}<br>
            會員期限：永久
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("🏠 AI 自動化", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()

        if st.session_state.role == "admin":
            if st.button("👑 管理員中心", use_container_width=True):
                st.session_state.page = "admin"
                st.rerun()

        st.divider()

        if st.button("🚪 登出", use_container_width=True):
            do_logout()
            st.rerun()


# ============================================================
# 主頁 (AI 半自動化操作頁面)
# ============================================================

def home_page():
    st.title("🏠 AI 商品自動化生成")
    st.caption("填寫基本商品資料並上傳圖片，AI 將自動生成上架文案、短影音腳本與即夢 Prompt。")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("1. 填寫商品資料")
        name = st.text_input("商品名稱", placeholder="例如：無塵兩用隨身涼風扇")
        price = st.text_input("商品價格", placeholder="例如：$299")
        cost = st.text_input("商品成本", placeholder="例如：$120")
        commission = st.text_input("分潤比例", placeholder="例如：15%")
        sales = st.text_input("月銷量", placeholder="例如：1200+")
        rating = st.text_input("商品評分", placeholder="例如：4.9")
        url = st.text_input("商品連結", placeholder="https://...")
        specs = st.text_area("商品規格/細節", placeholder="顏色：白色/粉色\n電池容量：2000mAh")
        platform = st.selectbox("目標平台", ["蝦皮購物", "TikTok 電商", "雙平台通用"])

        uploaded_file = st.file_uploader("上傳商品圖片 (選填，強化辨識)", type=["jpg", "jpeg", "png", "webp"])

    with col2:
        st.subheader("2. AI 生成預覽")
        if st.button("🚀 開始全自動分析生成", use_container_width=True, type="primary"):
            if not name:
                st.warning("請至少填寫商品名稱！")
            else:
                product_info = {
                    "name": name,
                    "price": price or "待確認",
                    "cost": cost or "待確認",
                    "commission": commission or "待確認",
                    "sales": sales or "待確認",
                    "rating": rating or "待確認",
                    "url": url or "待確認",
                    "specs": specs or "待確認",
                    "platform": platform,
                }

                img_bytes = None
                mime_type = "image/jpeg"

                if uploaded_file:
                    with st.spinner("正在優化與處理圖片..."):
                        img_bytes, mime_type = process_image(uploaded_file)

                with st.spinner("AI 正在思考並調用 Gemini 2.5 PRO 生成分析內容..."):
                    try:
                        prompt_text = build_ai_prompt(product_info)
                        result = ask_gemini(prompt_text, img_bytes, mime_type)
                        st.session_state.result = result
                        st.success("生成完成！")
                    except Exception as e:
                        st.error(f"生成過程發生錯誤：{e}")

        if st.session_state.result:
            st.text_area("生成結果", st.session_state.result, height=600)
            st.download_button(
                label="📥 下載完整報告 (.txt)",
                data=st.session_state.result,
                file_name=f"{name}_AI生成企劃.txt",
                mime="text/plain",
                use_container_width=True,
            )


# ============================================================
# 管理員中心
# ============================================================

def admin_page():
    st.title("👑 管理員中心")
    st.caption("所有會員期限均為永久，由管理員手動控制會員狀態與權限。")

    members = load_members()

    c1, c2, c3 = st.columns(3)
    c1.metric("會員總數", len(members))
    c2.metric("啟用會員", sum(m.get("status") == "active" for m in members))
    c3.metric("永久會員", len(members))

    st.divider()

    st.subheader("➕ 新增會員")
    with st.form("admin_add"):
        a, b = st.columns(2)
        with a:
            username = st.text_input("帳號")
            name = st.text_input("姓名 / 暱稱")
        with b:
            password = st.text_input("密碼", type="password")
            email = st.text_input("Email")

        role = st.selectbox(
            "會員等級",
            ["member", "vip", "admin"],
            format_func=lambda x: {
                "member": "一般會員",
                "vip": "VIP 會員",
                "admin": "管理員",
            }[x],
        )

        submit = st.form_submit_button("建立永久會員", use_container_width=True)

    if submit:
        ok, msg = create_member(username, password, name, email, role)
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)

    st.divider()

    st.subheader("👥 會員管理")

    for idx, member in enumerate(members):
        username = member.get("username", "")

        with st.expander(
            f"👤 {username} ｜ {member.get('role', 'member')} ｜ 狀態: {member.get('status', 'active')}"
        ):
            c1, c2, c3 = st.columns(3)

            with c1:
                st.write(f"姓名：{member.get('name', '')}")
                st.write(f"Email：{member.get('email', '')}")
                st.write("期限：**永久**")
                st.write(f"建立時間：{member.get('created_at', '')}")

            with c2:
                roles = ["member", "vip", "admin"]
                current_role = member.get("role", "member")
                new_role = st.selectbox(
                    "權限等級",
                    roles,
                    index=roles.index(current_role) if current_role in roles else 0,
                    key=f"role_{username}_{idx}",
                )

                statuses = ["active", "disabled"]
                current_status = member.get("status", "active")
                new_status = st.selectbox(
                    "帳號狀態",
                    statuses,
                    index=statuses.index(current_status) if current_status in statuses else 0,
                    key=f"status_{username}_{idx}",
                )

            with c3:
                st.write("操作")
                if st.button("💾 儲存修改", key=f"save_{username}_{idx}"):
                    member["role"] = new_role
                    member["status"] = new_status
                    save_members(members)
                    st.success(f"已更新 {username} 的設定！")
                    st.rerun()


# ============================================================
# 主程式入口
# ============================================
