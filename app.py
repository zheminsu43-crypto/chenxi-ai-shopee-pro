import io
import os
import json
import hashlib
import secrets
from datetime import datetime, date, timedelta

import streamlit as st
from PIL import Image, ImageOps

# =========================================================
# AI 蝦皮半自動化 2.5 PRO (圖文識別 + Gemini 2.5 Flash 完整版)
# =========================================================

# SDK 載入
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    genai = None
    types = None
    HAS_GENAI = False

# 頁面設定
APP_NAME = "AI 蝦皮半自動化 2.5 PRO"
GEMINI_MODEL = "gemini-2.5-flash"
MAX_IMAGE_MB = 20
MAX_IMAGE_SIZE = 1600

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 樣式設定
st.markdown("""
    <style>
    .main-title { text-align: center; font-size: 38px; font-weight: 800; margin-top: 15px; }
    .main-subtitle { text-align: center; opacity: .72; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

# Session State 初始化
if "api_key" not in st.session_state:
    st.session_state.api_key = ""

# 圖片處理函式
def process_uploaded_image(uploaded_file):
    if uploaded_file is None:
        return None, None
    raw = uploaded_file.getvalue()
    if len(raw) / (1024 * 1024) > MAX_IMAGE_MB:
        raise ValueError(f"圖片大小超過 {MAX_IMAGE_MB}MB 上限。")
    
    image = Image.open(io.BytesIO(raw))
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")
    image.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE), Image.Resampling.LANCZOS)
    
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=92)
    return image, output.getvalue()

# API Key 讀取
def get_gemini_api_key():
    key = st.secrets.get("GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "") or st.session_state.get("api_key", "")
    return str(key).strip()

# 多模態 Gemini 生成（文字 + 圖片）
def generate_multimodal_content(api_key, prompt, image_bytes=None):
    client = genai.Client(api_key=api_key)
    contents = []
    if image_bytes:
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))
    contents.append(prompt)
    
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents
    )
    return response.text

# 側邊欄
def sidebar():
    with st.sidebar:
        st.title("🛒 功能選單")
        st.subheader("🤖 Gemini API 設定")
        key = st.text_input("Gemini API Key", value=st.session_state.get("api_key", ""), type="password")
        if key != st.session_state.get("api_key", ""):
            st.session_state.api_key = key
        
        if get_gemini_api_key():
            st.success("✅ API Key 已載入")
        else:
            st.warning("⚠️ 尚未設定 API Key")

# 主畫面
def main_app_page():
    st.markdown(f'<div class="main-title">🛒 {APP_NAME}</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-subtitle">AI 蝦皮圖文辨識 ➔ 爆款文案與即夢 2.5 Prompt 全自動生成</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📥 1. 上傳商品圖片（支援 AI 圖文辨識）")
        uploaded_file = st.file_uploader("選擇商品圖片 (JPG/PNG)", type=["jpg", "jpeg", "png"])
        img_obj, img_bytes = None, None
        
        if uploaded_file:
            try:
                img_obj, img_bytes = process_uploaded_image(uploaded_file)
                st.image(img_obj, caption="已上傳商品預覽", use_container_width=True)
            except Exception as e:
                st.error(f"圖片讀取失敗: {e}")

        st.subheader("📝 2. 輸入商品基本資訊")
        p_name = st.text_input("商品名稱", placeholder="例如：波士頓大龍蝦（未填寫時 AI 將自動辨識）")
        p_features = st.text_area("補充特色與規格", placeholder="例如：500g/隻，急速生凍，肉質緊實彈牙")
        p_platform = st.selectbox("銷售平台", ["蝦皮購物", "TikTok 賣場", "全平台整合"])

        start_btn = st.button("🚀 開始全自動圖文分析與生成", type="primary", use_container_width=True)

    with col2:
        st.subheader("📋 3. AI 產出結果")
        if start_btn:
            api_key = get_gemini_api_key()
            if not api_key:
                st.error("❌ 請先在左側欄輸入 Gemini API Key！")
            elif not HAS_GENAI:
                st.error("❌ 尚未安裝 google-genai 套件，請檢查 requirements.txt")
            else:
                with st.spinner("🤖 AI 正在分析圖片並撰寫文案與即夢 Prompt 中..."):
                    try:
                        prompt = f"""
                        你是一個頂級電商視覺與文案專家。
                        
                        請詳細分析【上傳的商品圖片】與以下輸入資料：
                        - 商品名稱：{p_name or "請根據圖片自主辨識"}
                        - 補充資訊：{p_features or "無"}
                        - 主要平台：{p_platform}

                        請輸出完整的電商行銷資料包：

                        # 1｜📸 商品視覺辨識分析
                        - 視覺特徵：外觀細節、顏色、材質、包裝、賣點觀察。

                        # 2｜🛒 蝦皮爆款文案
                        - 蝦皮高轉化標題 (含關鍵字、品牌/規格、高吸引力詞組)
                        - 3 大核心購買賣點 (條列式)
                        - 完整蝦皮商品描述 (含使用情境、注意事項、Emoji視覺排版)

                        # 3｜🎬 TikTok 15秒短影音帶貨腳本
                        - 前 3 秒黃金 Hook (吸睛開場)
                        - 15 秒分鏡畫面與台詞規劃

                        # 4｜🎨 即夢 AI 2.5 英文 Prompt 指南
                        【嚴格規則】保持原商品外觀、顏色與 Logo 一致，預設無人物。
                        - **Positive Prompt (生圖用)**: Commercial product photography of this exact item, studio lighting, ultra-realistic, 8k, photorealistic.
                        - **Negative Prompt**: watermark, blurry, extra objects, modified logo, deformities.
                        - **Video Prompt (生影片用)**: Smooth cinematic camera rotating around the product, studio lighting.
                        """
                        
                        result = generate_multimodal_content(api_key, prompt, img_bytes)
                        st.success("🎉 全自動生成完成！")
                        st.divider()
                        st.markdown(result)
                        
                    except Exception as e:
                        st.error(f"❌ 生成失敗：{e}")

# 主程式入口
def main():
    sidebar()
    main_app_page()

if __name__ == "__main__":
    main()ag）
3. Facebook / Instagram 貼文
4. 即夢 AI 2.5 英文生圖與影片 Prompt（含 Positive & Negative Prompt）
5. 15 秒影片分鏡表（至少 5 個鏡頭）
6. 合規檢查與發布前確認事項

【即夢核心規則】
{JIMENG_CORE_RULES}
"""


# =========================================================
# 影片上傳
# =========================================================
VIDEO_MIME_MAP = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
}


def get_video_info(uploaded_file):
    if uploaded_file is None:
        return None

    raw = uploaded_file.getvalue()

    if not raw:
        raise ValueError("影片檔案是空的。")

    size_mb = len(raw) / 1024 / 1024

    if size_mb > MAX_VIDEO_MB:
        raise ValueError(
            f"影片大小 {size_mb:.1f} MB，超過 {MAX_VIDEO_MB} MB 上限。"
        )

    filename = uploaded_file.name or "video.mp4"
    ext = os.path.splitext(filename)[1].lower()

    mime = uploaded_file.type or VIDEO_MIME_MAP.get(
        ext,
        "video/mp4",
    )

    return {
        "name": filename,
        "bytes": raw,
        "mime": mime,
        "ext": ext,
        "size_mb": size_mb,
    }


# =========================================================
# 登入 / 註冊頁面
# =========================================================
def auth_page():
    st.markdown(
        '<div class="main-title">🛒 AI 蝦皮半自動化 2.5 PRO</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="main-subtitle">免費 Gemini Flash × 電商 AI × 即夢 AI 2.5</div>',
        unsafe_allow_html=True,
    )

    tab_login, tab_register = st.tabs(["🔐 登入", "📝 註冊"])

    with tab_login:
        st.subheader("🔑 會員登入")

        username = st.text_input(
            "帳號",
            key="login_username",
        )

        password = st.text_input(
            "密碼",
            type="password",
            key="login_password",
        )

        if st.button(
            "登入",
            type="primary",
            use_container_width=True,
        ):
            success, result = check_login(username, password)

            if success:
                st.session_state.logged_in = True
                st.session_state.username = result["username"]
                st.session_state.user_role = result["role"]
                st.session_state.member = result
                st.success("登入成功！")
                st.rerun()
            else:
                st.error(result)

        st.info("預設管理員測試帳號：admin / admin123")

    with tab_register:
        st.subheader("📝 建立會員")

        name = st.text_input(
            "姓名 / 暱稱",
            key="register_name",
        )

        username = st.text_input(
            "帳號",
            key="register_username",
        )

        email = st.text_input(
            "Email",
            key="register_email",
        )

        password = st.text_input(
            "密碼",
            type="password",
            key="register_password",
        )

        confirm = st.text_input(
            "再次輸入密碼",
            type="password",
            key="register_confirm",
        )

        if st.button(
            "建立帳號",
            use_container_width=True,
        ):
            if password != confirm:
                st.error("兩次密碼不一致。")
            else:
                success, result = create_member(
                    username,
                    password,
                    name,
                    email,
                )

                if success:
                    st.success("🎉 註冊成功！請回到登入頁登入。")
                else:
                    st.error(result)


# =========================================================
# Sidebar
# =========================================================
def sidebar():
    with st.sidebar:
        st.title("🛒 功能選單")

        if st.session_state.logged_in:
            member = st.session_state.member

            st.write(f"👤 **{member.get('name') or member.get('username')}**")
            st.caption(f"帳號：{member.get('username')}")
            st.caption(f"身分：{member.get('role')}")
            st.caption(f"到期日：{member.get('expires')}")

            if st.button(
                "🚪 登出",
                use_container_width=True,
            ):
                logout()
        else:
            st.info("請先登入會員。")

        st.divider()

        st.subheader("🤖 Gemini API 設定")

        key = st.text_input(
            "Gemini API Key",
            value=st.session_state.get("api_key", ""),
            type="password",
            help="不要把 API Key 寫進 GitHub 或公開程式碼。",
        )

        if key != st.session_state.get("api_key", ""):
            st.session_state.api_key = key
            reset_gemini_client()

        if get_gemini_api_key():
            st.success("API Key 已設定")
        else:
            st.warning("尚未設定 API Key")

        st.caption(f"預設模型：{GEMINI_MODEL}")


# =========================================================
# 管理員頁面
# =========================================================
def admin_page():
    st.header("👑 管理員中心")

    members = load_members()

    col1, col2 = st.columns(2)

    with col1:
        st.metric("會員總數", len(members))

    with col2:
        active_count = sum(
            1 for m in members if m.get("status") == "active"
        )
        st.metric("啟用會員", active_count)

    st.divider()

    for member in members:
        username = member.get("username", "")

        if username == ADMIN_USERNAME:
            continue

        with st.expander(f"👤 {username}"):
            st.write(f"姓名：{member.get('name', '')}")
            st.write(f"Email：{member.get('email', '')}")
            st.write(f"角色：{member.get('role', 'member')}")
            st.write(f"狀態：{member.get('status', 'active')}")
            st.write(f"到期：{member.get('expires', '')}")

            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("啟用", key=f"enable_{member['id']}"):
                    update_member(member["id"], {"status": "active"})
                    st.rerun()

            with col2:
                if st.button("停用", key=f"disable_{member['id']}"):
                    update_member(member["id"], {"status": "disabled"})
                    st.rerun()

            with col3:
                if st.button("延長 30 天", key=f"extend_{member['id']}"):
                    current = member.get("expires", "")
                    try:
                        old_date = date.fromisoformat(current)
                        base = max(old_date, date.today())
                    except Exception:
                        base = date.today()

                    new_date = (base + timedelta(days=30)).isoformat()
                    update_member(
                        member["id"],
                        {"expires": new_date, "status": "active"},
                    )
                    st.rerun()


# =========================================================
# 商品分析頁面
# =========================================================
def product_page():
    st.header("🚀 AI 商品分析中心")

    col1, col2 = st.columns(2)

    with col1:
        product_name = st.text_input("商品名稱", placeholder="例如：保濕修護精華液")
        price = st.text_input("商品價格", placeholder="例如：399")
        cost = st.text_input("商品成本", placeholder="例如：180")
        commission = st.text_input("分潤比例", placeholder="例如：10%")
        sales = st.text_input("月銷量", placeholder="例如：1000")
        rating = st.text_input("商品評分", placeholder="例如：4.9")

    with col2:
        product_url = st.text_input("商品連結", placeholder="貼上蝦皮商品連結")
        product_spec = st.text_area("商品規格", placeholder="容量、尺寸、顏色等")
        features = st.text_area("補充商品資訊", placeholder="商品特色、優惠等")
        platform = st.selectbox(
            "主要平台",
            ["蝦皮", "TikTok", "蝦皮＋TikTok", "Facebook", "Instagram", "全平台"],
        )

    st.divider()

    uploaded_file = st.file_uploader(
        "📷 上傳商品圖片",
        type=["jpg", "jpeg", "png", "webp"],
        key="product_image_upload",
    )

    pil_image = None
    image_bytes = None

    if uploaded_file:
        try:
            pil_image, image_bytes = prepare_image(uploaded_file)
            st.image(pil_image, caption="商品圖片預覽", use_container_width=True)
        except Exception as e:
            st.error(str(e))

    st.divider()

    start = st.button("🔥 開始 AI 完整分析", type="primary", use_container_width=True)

    if start:
        if not get_gemini_api_key():
            st.error("❌ 請先設定 Gemini API Key。")
            return

        if not product_name and not image_bytes:
            st.warning("請至少輸入商品名稱或上傳商品圖片。")
            return

        product_data = {
            "product_name": product_name,
            "price": price,
            "cost": cost,
            "commission": commission,
            "sales": sales,
            "rating": rating,
            "url": product_url,
            "spec": product_spec,
            "features": features,
            "platform": platform,
        }

        with st.spinner("🤖 Gemini Flash 正在分析商品圖片..."):
            analysis_prompt = build_product_analysis_prompt(product_data)
            analysis = gemini_generate_text(
                analysis_prompt,
                image_bytes=image_bytes,
                image_mime="image/jpeg",
            )

        if analysis.startswith("❌"):
            st.error(analysis)
            return

        with st.spinner("📝 正在產生文案與即夢 Prompt..."):
            full_prompt = build_full_generation_prompt(product_data, analysis)
            generated = gemini_generate_text(full_prompt)

        if generated.startswith("❌"):
            st.error(generated)
            return

        st.session_state.analysis_results = {
            "analysis": analysis,
            "generated": generated,
            "product_data": product_data,
            "created_at": datetime.now().isoformat(),
        }

        st.success("🎉 AI 分析與生成完成！")
        st.rerun()


# =========================================================
# 結果中心
# =========================================================
def results_page():
    st.header("📋 完整結果中心")

    result = st.session_state.analysis_results

    if not result:
        st.info("目前沒有分析結果。請先到「AI 商品分析」開始分析。")
        return

    product_data = result.get("product_data", {})

    st.subheader(f"🛒 {product_data.get('product_name') or '商品分析結果'}")
    st.caption(f"產生時間：{result.get('created_at', '')}")

    with st.expander("🔍 1｜Gemini 商品辨識與選品分析", expanded=True):
        st.markdown(result.get("analysis", ""))

    with st.expander("📝 2｜完整電商文案＋即夢 Prompt＋影片腳本", expanded=True):
        st.markdown(result.get("generated", ""))

    st.divider()

    all_text = result.get("analysis", "") + "\n\n" + result.get("generated", "")

    st.text_area("可直接複製的完整內容", value=all_text, height=500)

    st.download_button(
        "⬇️ 下載完整 AI 報告",
        data=all_text,
        file_name="ai_shopee_report.txt",
        mime="text/plain",
        use_container_width=True,
    )


# =========================================================
# 影片中心
# =========================================================
def video_page():
    st.header("🎬 影片中心")

    uploaded_video = st.file_uploader(
        "🎥 上傳影片",
        type=["mp4", "mov", "webm"],
        key="video_upload",
    )

    if uploaded_video:
        try:
            info = get_video_info(uploaded_video)
            st.session_state.last_video_name = info["name"]
            st.session_state.last_video_bytes = info["bytes"]
            st.session_state.last_video_mime = info["mime"]
            st.session_state.last_video_ext = info["ext"]
            st.success(f"影片已載入：{info['name']}")
        except Exception as e:
            st.error(str(e))

    video_bytes = st.session_state.last_video_bytes

    if video_bytes:
        st.video(video_bytes, format=st.session_state.last_video_mime)

        col1, col2 = st.columns(2)

        with col1:
            st.download_button(
                "⬇️ 下載影片",
                data=video_bytes,
                file_name=st.session_state.last_video_name or "video.mp4",
                mime=st.session_state.last_video_mime,
                use_container_width=True,
            )

        with col2:
            if st.button("🗑️ 清除影片", use_container_width=True):
                st.session_state.last_video_name = ""
                st.session_state.last_video_bytes = None
                st.rerun()


# =========================================================
# 會員中心
# =========================================================
def member_page():
    st.header("👤 會員中心")

    member = st.session_state.member

    if not member:
        st.warning("會員資料不存在。")
        return

    st.write(f"帳號：{member.get('username', '')}")
    st.write(f"姓名：{member.get('name', '')}")
    st.write(f"Email：{member.get('email', '')}")
    st.write(f"身份：{member.get('role', 'member')}")
    st.write(f"狀態：{member.get('status', 'active')}")
    st.write(f"到期日：{member.get('expires', '')}")


# =========================================================
# 首頁
# =========================================================
def home_page():
    st.markdown(
        '<div class="main-title">🛒 AI 蝦皮半自動化 2.5 PRO</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="main-subtitle">免費 Gemini Flash × 商品分析 × 電商文案 × 即夢 AI 2.5</div>',
        unsafe_allow_html=True,
    )

    st.divider()

    st.subheader("🚀 使用流程")
    st.write("1. 使用預設管理員帳號 (admin / admin123) 登入或註冊新帳號")
    st.write("2. 在左側欄設定您的 Gemini API Key")
    st.write("3. 到「AI 商品分析」頁面填寫資料並上傳圖片即可開始！")


# =========================================================
# 主程式
# =========================================================
def main():
    sidebar()

    if not st.session_state.logged_in:
        auth_page()
        return

    tabs = ["🏠 首頁", "🚀 AI 商品分析", "📋 結果中心", "🎬 影片中心", "👤 會員中心"]

    if st.session_state.user_role == "admin":
        tabs.append("👑 管理員")

    menu = st.tabs(tabs)

    with menu[0]:
        home_page()

    with menu[1]:
        product_page()

    with menu[2]:
        results_page()

    with menu[3]:
        video_page()

    with menu[4]:
        member_page()

    if st.session_state.user_role == "admin":
        with menu[5]:
            admin_page()


if __name__ == "__main__":
    main()
