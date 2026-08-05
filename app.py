import io
import os
import json
import hashlib
import secrets
from datetime import date, datetime, timedelta

import streamlit as st
from PIL import Image, ImageOps

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    genai = None
    types = None
    HAS_GENAI = False

APP_NAME = "AI 蝦皮半自動化 2.5 PRO"
MODEL = "gemini-2.0-flash"
FALLBACK_MODEL = "gemini-1.5-flash"
DATA_DIR = "data"
MEMBERS_FILE = os.path.join(DATA_DIR, "members.json")
MAX_IMAGE_MB = 20
MAX_IMAGE_SIZE = 1600
MAX_VIDEO_MB = 300
ADMIN_USER = "admin"
ADMIN_PASSWORD = "admin123"

os.makedirs(DATA_DIR, exist_ok=True)

st.set_page_config(page_title=APP_NAME, page_icon="🛒", layout="wide")

st.markdown("""
<style>
.main-title{text-align:center;font-size:40px;font-weight:800;margin-top:15px}
.main-subtitle{text-align:center;opacity:.7;margin-bottom:25px}
</style>
""", unsafe_allow_html=True)

DEFAULTS = {
    "logged_in": False, "username": "", "role": "guest", "member": {},
    "api_key": "", "result": None, "video_bytes": None,
    "video_name": "", "video_mime": "video/mp4"
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

def api_key():
    try:
        secret = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        secret = ""
    return str(secret or os.getenv("GEMINI_API_KEY", "") or st.session_state.api_key).strip()

@st.cache_resource(show_spinner=False)
def client(key):
    return genai.Client(api_key=key) if HAS_GENAI and key else None

def gemini(prompt, image_bytes=None):
    key = api_key()
    if not key:
        return "❌ 尚未設定 Gemini API Key。"
    if not HAS_GENAI:
        return "❌ 缺少 google-genai，請安裝 requirements.txt。"
    c = client(key)
    parts = []
    if image_bytes:
        parts.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))
    parts.append(prompt)
    errors = []
    for model in (MODEL, FALLBACK_MODEL, "gemini-2.5-flash"):
        try:
            r = c.models.generate_content(model=model, contents=parts)
            if getattr(r, "text", None):
                return r.text
            errors.append(model + ": 無文字回傳")
        except Exception as e:
            errors.append(model + ": " + str(e))
    return "❌ Gemini 呼叫失敗：\n" + "\n".join(errors)

def hash_pw(p):
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + p).encode()).hexdigest()
    return salt + "$" + h

def verify_pw(p, saved):
    try:
        salt, h = saved.split("$", 1)
        return secrets.compare_digest(
            hashlib.sha256((salt + p).encode()).hexdigest(), h
        )
    except Exception:
        return False

def load_members():
    if not os.path.exists(MEMBERS_FILE):
        return []
    try:
        with open(MEMBERS_FILE, encoding="utf-8") as f:
            x = json.load(f)
        return x if isinstance(x, list) else []
    except Exception:
        return []

def save_members(x):
    with open(MEMBERS_FILE, "w", encoding="utf-8") as f:
        json.dump(x, f, ensure_ascii=False, indent=2)

def ensure_admin():
    members = load_members()
    if any(str(x.get("username","")).lower() == ADMIN_USER for x in members):
        return
    members.append({
        "id": secrets.token_hex(8), "username": ADMIN_USER,
        "password_hash": hash_pw(ADMIN_PASSWORD), "name": "系統管理員",
        "email": "", "role": "admin", "status": "active",
        "expires": (date.today() + timedelta(days=3650)).isoformat(),
        "created_at": datetime.now().isoformat()
    })
    save_members(members)

def find_member(username):
    u = str(username).strip().lower()
    return next((x for x in load_members()
                 if str(x.get("username","")).lower() == u), None)

def register(username, password, name, email):
    u = str(username).strip().lower()
    if len(u) < 3 or len(password) < 3:
        return False, "帳號與密碼至少 3 個字元。"
    if find_member(u):
        return False, "帳號已存在。"
    members = load_members()
    if email and any(str(x.get("email","")).lower() == email.lower() for x in members):
        return False, "Email 已註冊。"
    members.append({
        "id": secrets.token_hex(8), "username": u,
        "password_hash": hash_pw(password), "name": name.strip(),
        "email": email.strip().lower(), "role": "member", "status": "active",
        "expires": (date.today() + timedelta(days=30)).isoformat(),
        "created_at": datetime.now().isoformat()
    })
    save_members(members)
    return True, "註冊成功。"

def login(username, password):
    m = find_member(username)
    if not m or not verify_pw(password, str(m.get("password_hash",""))):
        return False, "帳號或密碼錯誤。"
    if m.get("status") != "active":
        return False, "帳號已停用。"
    try:
        if date.today() > date.fromisoformat(m.get("expires","")):
            return False, "會員資格已到期。"
    except Exception:
        return False, "會員到期日資料錯誤。"
    return True, m

ensure_admin()

def image_bytes(upload):
    if not upload:
        return None, None
    raw = upload.getvalue()
    if len(raw) > MAX_IMAGE_MB * 1024 * 1024:
        raise ValueError(f"圖片不可超過 {MAX_IMAGE_MB} MB。")
    im = Image.open(io.BytesIO(raw))
    im = ImageOps.exif_transpose(im).convert("RGB")
    im.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    im.save(out, "JPEG", quality=92, optimize=True)
    return im, out.getvalue()

RULES = """
商品一致性鎖定：上傳商品圖片是主要商品來源。
保留原品牌、包裝、形狀、比例、顏色、材質、Logo、標籤、印刷文字。
禁止改品牌、改包裝、改 Logo、改文字、商品變形、融化、漂移、閃爍、消失。
禁止新增第二個商品。預設禁止人物、手、模特兒、主持人。
禁止假價格、假折扣、假贈品、假認證、假規格、假功效、醫療效果。
未知資料必須寫「待確認」。
"""

def analysis_prompt(p):
    return """
你是 AI 蝦皮半自動化 2.5 PRO 商品分析專家。
請分析商品圖片與資料，不可捏造。

商品名稱：{name}
價格：{price}
成本：{cost}
分潤：{commission}
月銷量：{sales}
評分：{rating}
規格：{spec}
補充：{features}
平台：{platform}

輸出：
# 商品辨識
商品名稱：
品牌：
類別：
顏色：
外觀：
材質：
包裝：
Logo：
可辨識文字：
型號：
規格：

# 商品特色
列出 3～5 個可確認特色。

# AI 選品分析
視覺吸引力：
電商展示潛力：
短影音潛力：
內容製作難度：
合規風險：
推薦分數 0～100：

# 蝦皮展示建議
# TikTok 展示建議
# 即夢 AI 2.5 建議

最後提醒：正式發布前仍需人工確認商品、價格、規格、品牌、庫存、商品頁與分潤資格。

核心規則：
{rules}
""".format(
        name=p["name"] or "待確認", price=p["price"] or "待確認",
        cost=p["cost"] or "待確認", commission=p["commission"] or "待確認",
        sales=p["sales"] or "待確認", rating=p["rating"] or "待確認",
        spec=p["spec"] or "待確認", features=p["features"] or "待確認",
        platform=p["platform"], rules=RULES
    )

def content_prompt(p, analysis):
    return """
根據商品資料與圖片分析，產生完整電商內容。

【商品】
名稱：{name}
價格：{price}
規格：{spec}
補充：{features}
平台：{platform}

【分析】
{analysis}

未知資料一律「待確認」，禁止捏造價格、優惠、贈品、認證、成分、產地、功效、醫療效果。

# 1 蝦皮
商品標題 1：
商品標題 2：
商品標題 3：
SEO 關鍵字：
短描述：
完整描述：
特色：
規格：
注意事項：

# 2 TikTok
3 秒 Hook：
15 秒腳本：
30 秒腳本：
貼文：
Hashtag：
CTA：

# 3 Facebook
貼文：
互動問題：
Hashtag：

# 4 Instagram
Caption：
Hashtag：

# 5 即夢 AI 2.5 1:1 生圖
English Prompt：
Negative Prompt：

# 6 即夢 AI 2.5 9:16 海報
English Prompt：
Negative Prompt：

# 7 即夢 AI 2.5 商品細節圖
English Prompt：
Negative Prompt：

# 8 即夢 AI 2.5 15 秒影片
English Video Prompt：
0–3 seconds：商品正面穩定開場。
3–7 seconds：慢速推近展示包裝與材質。
7–12 seconds：平滑環繞商品展示。
12–15 seconds：回到正面英雄鏡頭並定格。
Camera：slow cinematic push-in, subtle orbit, smooth movement, stable framing.
全程保持 same product identity, same packaging, same logo, same label, same color, same proportions.
禁止 people, hands, models, extra products, duplicate products, deformation, disappearance, logo drift, text drift, watermark.

# 9 15 秒爆款帶貨影片
請輸出完整 English Video Prompt，依照 0–3 / 3–7 / 7–12 / 12–15 秒結構。

# 10 分潤合規檢查
商品與圖片一致：
價格：
規格：
品牌：
商品連結：
誇大：
假贈品：
假認證：
假價格：
錯誤規格：
品牌誤判：
使用 ✅ 通過 / ⚠️ 需確認 / ❌ 有問題。

# 11 發布前檢查
商品、價格、規格、品牌、庫存、圖片、影片、商品頁、分潤資格。

核心規則：
{rules}
""".format(
        name=p["name"] or "待確認",
        price=p["price"] or "待確認",
        spec=p["spec"] or "待確認",
        features=p["features"] or "待確認",
        platform=p["platform"],
        analysis=analysis,
        rules=RULES
    )

def sidebar():
    with st.sidebar:
        st.title("🛒 功能選單")
        if st.session_state.logged_in:
            m = st.session_state.member
            st.write(f"👤 **{m.get('name') or m.get('username')}**")
            st.caption(f"身份：{m.get('role')}")
            st.caption(f"到期：{m.get('expires')}")
            if st.button("🚪 登出", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.member = {}
                st.session_state.role = "guest"
                st.rerun()

        st.divider()
        st.subheader("🤖 Gemini API")
        k = st.text_input("Gemini API Key", value=st.session_state.api_key, type="password")
        st.session_state.api_key = k
        st.success("API Key 已設定" if api_key() else "尚未設定 API Key")
        st.caption(f"主要：{MODEL}")
        st.caption(f"備援：{FALLBACK_MODEL}")

def auth_page():
    st.markdown(f'<div class="main-title">🛒 {APP_NAME}</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-subtitle">Gemini AI × 電商自動化生成</div>', unsafe_allow_html=True)
    a, b = st.tabs(["🔐 登入", "📝 註冊"])
    with a:
        u = st.text_input("帳號", key="lu")
        p = st.text_input("密碼", type="password", key="lp")
        if st.button("登入", type="primary", use_container_width=True):
            ok, result = login(u, p)
            if ok:
                st.session_state.logged_in = True
                st.session_state.username = result["username"]
                st.session_state.role = result["role"]
                st.session_state.member = result
                st.rerun()
            else:
                st.error(result)
        st.info("管理員測試帳號：admin / admin123")
    with b:
        n = st.text_input("姓名 / 暱稱", key="rn")
        u = st.text_input("帳號", key="ru")
        e = st.text_input("Email", key="re")
        p = st.text_input("密碼", type="password", key="rp")
        q = st.text_input("確認密碼", type="password", key="rq")
        if st.button("建立帳號", use_container_width=True):
            if p != q:
                st.error("兩次密碼不一致。")
            else:
                ok, msg = register(u, p, n, e)
                st.success(msg) if ok else st.error(msg)

def product_page():
    st.header("🚀 AI 商品分析中心")
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("商品名稱")
        price = st.text_input("商品價格")
        cost = st.text_input("商品成本")
        commission = st.text_input("分潤比例")
        sales = st.text_input("月銷量")
        rating = st.text_input("商品評分")
    with c2:
        url = st.text_input("商品連結")
        spec = st.text_area("商品規格")
        features = st.text_area("補充商品資訊")
        platform = st.selectbox("主要平台", ["蝦皮", "TikTok", "蝦皮＋TikTok", "Facebook", "Instagram", "全平台"])

    upload = st.file_uploader("📷 上傳商品圖片", type=["jpg", "jpeg", "png", "webp"])
    im, ib = None, None
    if upload:
        try:
            im, ib = image_bytes(upload)
            st.image(im, caption="商品預覽", use_container_width=True)
        except Exception as e:
            st.error(str(e))

    if st.button("🔥 開始 AI 完整分析", type="primary", use_container_width=True):
        if not api_key():
            st.error("請先輸入 Gemini API Key。")
            return
        if not HAS_GENAI:
            st.error("請安裝 google-genai。")
            return
        if not name and not ib:
            st.warning("請輸入商品名稱或上傳圖片。")
            return

        p = {
            "name": name, "price": price, "cost": cost,
            "commission": commission, "sales": sales,
            "rating": rating, "url": url, "spec": spec,
            "features": features, "platform": platform
        }

        with st.spinner("Gemini 正在分析商品圖片..."):
            analysis = gemini(analysis_prompt(p), ib)
        if analysis.startswith("❌"):
            st.error(analysis)
            return

        with st.spinner("Gemini 正在產生文案與影片 Prompt..."):
            generated = gemini(content_prompt(p, analysis))
        if generated.startswith("❌"):
            st.error(generated)
            return

        st.session_state.result = {
            "product": p, "analysis": analysis,
            "generated": generated,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        st.success("🎉 完成！")
        st.markdown(analysis)
        st.markdown(generated)

def results_page():
    st.header("📋 結果中心")
    r = st.session_state.result
    if not r:
        st.info("尚無結果。")
        return
    st.caption(r["time"])
    st.subheader("🔍 商品分析")
    st.markdown(r["analysis"])
    st.subheader("📝 文案＋即夢 Prompt")
    st.markdown(r["generated"])
    text = r["analysis"] + "\n\n" + r["generated"]
    st.text_area("完整內容", text, height=600)
    st.download_button("⬇️ 下載 TXT", text, "ai_shopee_report.txt", "text/plain", use_container_width=True)

def video_page():
    st.header("🎬 影片中心")
    st.caption("上傳你實際生成的 MP4 / MOV / WEBM 來預覽。")
    v = st.file_uploader("🎥 上傳影片", type=["mp4", "mov", "webm"])
    if v:
        raw = v.getvalue()
        if len(raw) > MAX_VIDEO_MB * 1024 * 1024:
            st.error(f"影片不可超過 {MAX_VIDEO_MB} MB。")
            return
        st.session_state.video_bytes = raw
        st.session_state.video_name = v.name
        st.session_state.video_mime = v.type or "video/mp4"
    if st.session_state.video_bytes:
        st.video(st.session_state.video_bytes, format=st.session_state.video_mime)
        st.download_button("⬇️ 下載影片", st.session_state.video_bytes, st.session_state.video_name, st.session_state.video_mime, use_container_width=True)
        if st.button("🗑️ 清除影片", use_container_width=True):
            st.session_state.video_bytes = None
            st.session_state.video_name = ""
            st.rerun()
    else:
        st.info("尚未上傳影片。")

def member_page():
    st.header("👤 會員中心")
    m = st.session_state.member
    st.write(f"帳號：{m.get('username')}")
    st.write(f"姓名：{m.get('name')}")
    st.write(f"身份：{m.get('role')}")
    st.write(f"到期日：{m.get('expires')}")

def admin_page():
    st.header("👑 管理員")
    members = load_members()
    st.metric("會員總數", len(members))
    for m in members:
        if m.get("username") == ADMIN_USER:
            continue
        with st.expander(m.get("username","")):
            st.write(f"姓名：{m.get('name','')}")
            st.write(f"狀態：{m.get('status','active')}")
            st.write(f"到期：{m.get('expires','')}")
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("啟用", key="en_"+m["id"]):
                    update = load_members()
                    for x in update:
                        if x["id"] == m["id"]: x["status"] = "active"
                    save_members(update); st.rerun()
            with c2:
                if st.button("停用", key="di_"+m["id"]):
                    update = load_members()
                    for x in update:
                        if x["id"] == m["id"]: x["status"] = "disabled"
                    save_members(update); st.rerun()
            with c3:
                if st.button("延長30天", key="ex_"+m["id"]):
                    try: base = max(date.fromisoformat(m["expires"]), date.today())
                    except Exception: base = date.today()
                    update = load_members()
                    for x in update:
                        if x["id"] == m["id"]:
                            x["expires"] = (base + timedelta(days=30)).isoformat()
                            x["status"] = "active"
                    save_members(update); st.rerun()

def main():
    sidebar()
    if not st.session_state.logged_in:
        auth_page()
        return

    st.title(APP_NAME)
    tabs = ["🏠 首頁", "🚀 AI 商品分析", "📋 結果中心", "🎬 影片中心", "👤 會員中心"]
    if st.session_state.role == "admin":
        tabs.append("👑 管理員")
    pages = st.tabs(tabs)

    with pages[0]:
        st.markdown("### 📷 商品圖片 → Gemini 分析")
        st.write("### 📝 蝦皮 / TikTok / Facebook / Instagram 文案")
        st.write("### 🎬 即夢 AI 2.5 生圖與影片 Prompt")
        st.info("免費 Gemini API 層級：本程式產生影片 Prompt，不直接呼叫付費 Veo 影片生成。")
    with pages[1]: product_page()
    with pages[2]: results_page()
    with pages[3]: video_page()
    with pages[4]: member_page()
    if st.session_state.role == "admin":
        with pages[5]: admin_page()

if __name__ == "__main__":
    main()=====================================

def create_member(
    username,
    password,
    name,
    email,
):

    username = str(
        username
    ).strip().lower()

    password = str(password)

    name = str(
        name
    ).strip()

    email = str(
        email
    ).strip().lower()

    if len(username) < 3:
        return False, "帳號至少需要 3 個字元。"

    if len(password) < 3:
        return False, "密碼至少需要 3 個字元。"

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
        "name": name,
        "email": email,
        "role": "member",
        "status": "active",
        "expires": expires,
        "created_at": datetime.now().isoformat(),
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
    updates,
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
    password,
):

    member = find_member(username)

    if not member:
        return False, "帳號或密碼錯誤。"

    if (
        str(
            member.get(
                "status",
                "active",
            )
        ).lower()
        != "active"
    ):
        return False, "此會員帳號已停用。"

    saved_hash = str(
        member.get(
            "password_hash",
            "",
        )
    )

    if not saved_hash:
        return False, "會員資料異常。"

    if not verify_password(
        password,
        saved_hash,
    ):
        return False, "帳號或密碼錯誤。"

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

        return False, "會員到期日資料異常。"

    if date.today() > expires_date:

        return False, "會員資格已到期。"

    return True, member


# =========================================================
# 登出
# =========================================================

def logout():

    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.user_role = "guest"
    st.session_state.member = {}

    st.session_state.analysis_results = None

    st.session_state.last_video_name = ""
    st.session_state.last_video_bytes = None

    st.rerun()


# =========================================================
# 圖片處理
# =========================================================

def process_uploaded_image(
    uploaded_file
):

    if uploaded_file is None:
        return None, None

    raw = uploaded_file.getvalue()

    if not raw:
        raise ValueError(
            "圖片檔案是空的。"
        )

    size_mb = (
        len(raw)
        / 1024
        / 1024
    )

    if size_mb > MAX_IMAGE_MB:

        raise ValueError(
            f"圖片大小 {size_mb:.1f} MB，"
            f"超過 {MAX_IMAGE_MB} MB。"
        )

    try:

        image = Image.open(
            io.BytesIO(raw)
        )

        image = ImageOps.exif_transpose(
            image
        )

        image.load()

        if image.mode == "RGBA":

            background = Image.new(
                "RGB",
                image.size,
                "white",
            )

            background.paste(
                image,
                mask=image.getchannel(
                    "A"
                ),
            )

            image = background

        else:

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

        output = io.BytesIO()

        image.save(
            output,
            format="JPEG",
            quality=92,
            optimize=True,
        )

        return (
            image,
            output.getvalue(),
        )

    except Exception as e:

        raise ValueError(
            f"圖片讀取失敗：{e}"
        )


# =========================================================
# 即夢核心規則
# =========================================================

JIMENG_CORE_RULES = """
【即夢 AI 2.5 商品一致性鎖定】

上傳商品圖片是唯一主要商品來源。

必須保持：
- 原品牌
- 原包裝
- 原形狀
- 原比例
- 原顏色
- 原材質
- 原 Logo
- 原標籤
- 原印刷文字
- 原包裝結構

禁止：
- 改品牌
- 改包裝
- 改 Logo
- 改文字
- 改顏色
- 商品變形
- 商品融化
- 商品漂移
- 商品閃爍
- 商品消失
- 商品變成其他商品
- 新增第二個商品

預設禁止：
- 人物
- 手
- 模特兒
- 主持人
- 代言人
- 人物拿商品

禁止：
- 浮水印
- 假價格
- 假折扣
- 假贈品
- 假認證
- 假規格
- 假功效
- 醫療效果
- 未確認資訊

影片全程必須維持同一商品身份。

視覺方向：

premium commercial product photography,
realistic product details,
clean composition,
professional studio lighting,
smooth cinematic camera,
stable product identity.
"""


# =========================================================
# 商品分析 Prompt
# =========================================================

def build_product_analysis_prompt(
    product_data
):

    return f"""
你是「AI 蝦皮半自動化 2.5 PRO」的
AI 電商商品分析專家。

請仔細分析使用者提供的商品圖片與資料。

【使用者資料】

商品名稱：
{product_data["product_name"] or "待確認"}

價格：
{product_data["price"] or "待確認"}

成本：
{product_data["cost"] or "待確認"}

分潤：
{product_data["commission"] or "待確認"}

月銷量：
{product_data["sales"] or "待確認"}

商品評分：
{product_data["rating"] or "待確認"}

商品連結：
{product_data["url"] or "待確認"}

商品規格：
{product_data["spec"] or "待確認"}

補充：
{product_data["features"] or "待確認"}

【絕對規則】

1. 不得捏造圖片看不到的資訊。
2. 不清楚的資訊必須寫「待確認」。
3. 不得自行創造品牌。
4. 不得自行創造價格。
5. 不得自行創造容量。
6. 不得自行創造成分。
7. 不得自行創造產地。
8. 不得自行創造功效。
9. 不得自行創造醫療效果。
10. 不得自行創造認證。
11. 不得自行創造優惠。
12. 不得自行創造贈品。
13. 如果圖片有多個物品，選擇最主要、最大、
    最清楚、最具品牌辨識度的商品。
14. 全部使用繁體中文。
15. 不要假裝擁有即時市場銷量資料。

【輸出格式】

# 1｜商品辨識

商品名稱：
品牌：
類別：
主要顏色：
外觀：
材質：
包裝：
Logo：
可辨識文字：
型號：
規格：

# 2｜商品特色

列出 3～5 個
「圖片或使用者資料可以確認」
的特色。

# 3｜AI 選品分析

請分析：

- 商品視覺吸引力
- 電商展示潛力
- 短影音展示潛力
- 文案製作潛力
- 內容製作難度
- 合規風險
- 推薦分數 0～100

# 4｜圖片判斷

圖片清晰度：
主要商品：
是否多商品：
需要人工確認：

# 5｜蝦皮展示建議

主圖方向：
第二張圖方向：
商品細節圖：
賣點展示：

# 6｜TikTok 展示建議

前三秒：
商品展示：
鏡頭：
結尾：

# 7｜AI 龍蝦下一步建議

請判斷下一步最適合自動產生：

- 蝦皮文案
- TikTok 文案
- Facebook 文案
- Instagram 文案
- 即夢生圖 Prompt
- 即夢影片 Prompt
- 15 秒爆款影片 Prompt
- 合規檢查

# 8｜即夢 AI 2.5 注意事項

{JIMENG_CORE_RULES}

最後必須提醒：

正式發布前仍需人工確認商品、
價格、規格、品牌、庫存、商品頁
與分潤資格。
"""


# =========================================================
# AI 龍蝦完整生成 Prompt
# =========================================================

def build_lobster_prompt(
    product_data,
    analysis,
):

    return f"""
你現在是「🦞 AI 龍蝦總控」。

你的任務是把一個商品從：
商品圖片
→ 商品資料
→ 商品分析
→ 電商文案
→ 短影音腳本
→ 即夢 Prompt
→ 合規檢查

一次整理完成。

==================================================
【商品資料】
==================================================

商品名稱：
{product_data["product_name"] or "待確認"}

價格：
{product_data["price"] or "待確認"}

成本：
{product_data["cost"] or "待確認"}

分潤：
{product_data["commission"] or "待確認"}

月銷量：
{product_data["sales"] or "待確認"}

商品評分：
{product_data["rating"] or "待確認"}

商品連結：
{product_data["url"] or "待確認"}

商品規格：
{product_data["spec"] or "待確認"}

補充：
{product_data["features"] or "待確認"}

平台：
{product_data["platform"]}

==================================================
【Gemini 商品分析】
==================================================

{analysis}

==================================================
【絕對規則】
==================================================

不得捏造任何商品資訊。

不知道：
→ 寫「待確認」

不得虛構：

- 品牌
- 價格
- 規格
- 容量
- 成分
- 產地
- 功效
- 醫療效果
- 認證
- 優惠
- 贈品
- 銷量
- 評價

不得誇大。

==================================================
【1｜蝦皮完整上架】
==================================================

### 商品標題 1
### 商品標題 2
### 商品標題 3

### SEO 關鍵字

### 商品短描述

### 商品完整描述

### 商品特色

### 商品規格

### 使用方式

### 保存方式

### 注意事項

### 購買前提醒

==================================================
【2｜TikTok】
==================================================

### 3 秒 Hook

### 15 秒腳本

0–3 秒：
3–7 秒：
7–12 秒：
12–15 秒：

### TikTok 貼文

### Hashtag

### CTA

==================================================
【3｜Facebook】
==================================================

### Facebook 貼文

### 互動問題

### Hashtag

==================================================
【4｜Instagram】
==================================================

### Instagram Caption

### Hashtag

==================================================
【5｜即夢 AI 2.5 1:1 蝦皮主圖】
==================================================

請輸出完整 English Prompt。

要求：

- exact original product
- original product identity
- original packaging
- original logo
- original label
- original visible text
- original color
- original proportions
- realistic
- premium commercial photography
- professional studio lighting
- clean composition
- sharp product details
- no people
- no hands

### Negative Prompt

必須包含：

text distortion,
logo distortion,
label distortion,
wrong packaging,
wrong product,
extra product,
duplicate product,
deformed product,
product deformation,
watermark,
blur,
low quality,
people,
hands,
model,
fake text,
fake logo

==================================================
【6｜即夢 AI 2.5 9:16 商品海報】
==================================================

完整 English Prompt。

要求：

9:16 vertical

premium advertising photography

product centered

exact original product identity

original packaging

original logo

original label

original color

original proportions

realistic lighting

professional commercial composition

no people

no hands

no watermark

### Negative Prompt

==================================================
【7｜即夢 AI 2.5 商品細節圖】
============
