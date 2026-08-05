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
    main()
