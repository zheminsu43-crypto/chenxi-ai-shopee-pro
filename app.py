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
import google.generativeai as genai

# ============================================================
# 應用程式設定與常數
# ============================================================

APP_NAME = "AI 蝦皮半自動化 2.5 PRO"
GEMINI_MODEL = "gemini-1.5-flash"  # 使用最具相容性的預設模型

DATA_DIR = Path("data")
MEMBERS_FILE = DATA_DIR / "members.json"

DATA_DIR.mkdir(exist_ok=True)

# ============================================================
# 管理員初始設定
# ============================================================

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123456")

# ============================================================
# 即夢 AI 2.5 核心規則
# ============================================================

JIMENG_25_CORE_RULES = """
你是即夢 AI 2.5 商業商品 Prompt 專家。
【商品原貌鎖定】
1. 使用使用者上傳圖片中的主要商品作為唯一主要商品。
2. 保留商品品牌、包裝、瓶身、盒子、形狀、比例、顏色、材質、Logo、標籤。
3. 不得自行改變商品品牌、包裝、顏色或形狀。
4. 不得自行創造不存在的商品資訊，不知道的寫「待確認」。
5. 商品在所有畫面中必須維持同一身份與外觀。
【畫面限制】
6. 無人物、無手、無模特兒、無代言人。
7. 無浮水印、無錯誤價格、無假贈品。
【生圖與影片】
8. Prompt 主要使用英文，畫面文字使用繁體中文。
9. 必須包含商品、場景、燈光、材質、構圖、鏡頭及 Negative Prompt。
"""

# ============================================================
# Streamlit 頁面配置
# ============================================================

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# Session State 初始化
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
# 密碼加密與驗證
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
# 會員資料處理
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
                "email": "admin@system.local",
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
# 登入與登出
# ============================================================

def do_login(username, password):
    member = find_member(username)
    if member is None or not verify_password(password, member.get("password_hash", "")):
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
# Gemini API 安全呼叫邏輯
# ============================================================

def ask_gemini(prompt, image_obj=None):
    api_key = os.getenv("GEMINI_API_KEY", "")
    try:
        if not api_key and "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

    if not api_key:
        raise RuntimeError("找不到 GEMINI_API_KEY！請至 Streamlit 控制台的 Secrets 中設定。")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(GEMINI_MODEL)

    contents = [prompt]
    if image_obj:
        contents.append(image_obj)

    response = model.generate_content(contents)
    if not response or not response.text:
        raise RuntimeError("Gemini 未能正確回傳分析結果。")

    return response.text.strip()

# ============================================================
# 圖片預處理
# ============================================================

def process_image(uploaded_file):
    try:
        image = Image.open(uploaded_file)
        image = ImageOps.exif_transpose(image)
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")
        return image
    except Exception as exc:
        raise RuntimeError(f"圖片處理失敗：{exc}")

# ============================================================
# Prompt 構建器
# ============================================================

def build_ai_prompt(product):
    return f"""
你現在是「{APP_NAME}」的核心 AI 助手。請分析商品圖片與資料：

【商品資料】
名稱：{product["name"]}
價格：{product["price"]} | 成本：{product["cost"]} | 分潤：{product["commission"]}
銷量：{product["sales"]} | 評分：{product["rating"]} | 平台：{product["platform"]}
規格：{product["specs"]}

請輸出以下 9 大模組內容：
1. 商品辨識
2. AI 選品分析
3. 蝦皮上架文案 (SEO標題、賣點、描述、Hashtag)
4. TikTok 口播文案與 Hook
5. 即夢 AI 2.5 生圖 Prompt (遵循規則：{JIMENG_25_CORE_RULES})
6. 即夢 AI 2.5 影片 Prompt
7. 爆款帶貨影片腳本 (0-25秒)
8. 分潤與合規檢查
9. AI 最終自我檢查
"""

# ============================================================
# 頁面 UI
# ============================================================

def login_page():
    st.title(f"🛒 {APP_NAME}")
    st.caption("永久會員管理系統｜Gemini 驅動｜即夢 AI 2.5 生圖與短影音專家")

    tab1, tab2 = st.tabs(["🔐 會員登入", "📝 會員註冊"])
    with tab1:
        with st.form("login_form"):
            username = st.text_input("會員帳號")
            password = st.text_input("會員密碼", type="password")
            if st.form_submit_button("登入系統", use_container_width=True):
                ok, msg = do_login(username, password)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        st.info(f"💡 預設管理者帳密：`{ADMIN_USERNAME}` / `{ADMIN_PASSWORD}`")

    with tab2:
        with st.form("register_form"):
            username = st.text_input("新會員帳號 (英數)")
            name = st.text_input("顯示名稱")
            email = st.text_input("Email")
            password = st.text_input("密碼", type="password")
            password2 = st.text_input("確認密碼", type="password")
            if st.form_submit_button("註冊永久會員", use_container_width=True):
                if password != password2:
                    st.error("兩次密碼不一致。")
                else:
                    ok, msg = create_member(username, password, name, email)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

def sidebar():
    with st.sidebar:
        st.markdown(f"### 🛒 {APP_NAME}")
        st.markdown(f"👤 **{st.session_state.name}** (`{st.session_state.role.upper()}`)")
        if st.button("🏠 AI 自動化工具", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()
        if st.session_state.role == "admin":
            if st.button("👑 後台管理中心", use_container_width=True):
                st.session_state.page = "admin"
                st.rerun()
        st.divider()
        if st.button("🚪 安全登出", use_container_width=True):
            do_logout()
            st.rerun()

def home_page():
    st.title("🏠 AI 蝦皮/TikTok 一鍵生成")
    col1, col2 = st.columns([1, 1])
    with col1:
        name = st.text_input("商品名稱 *")
        price = st.text_input("銷售價格")
        cost = st.text_input("進貨成本")
        commission = st.text_input("分潤比例")
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
