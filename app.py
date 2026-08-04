import streamlit as st
import os
import json
import base64
import requests
from PIL import Image
import io

# =========================================================
# 1. 頁面配置與基本設定
# =========================================================
APP_NAME = "AI 電商文案與即夢 2.5 Prompt 生成器"

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化 Session State
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_role" not in st.session_state:
    st.session_state.user_role = "guest"
if "username" not in st.session_state:
    st.session_state.username = ""
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None
if "api_key" not in st.session_state:
    st.session_state.api_key = os.getenv("GEMINI_API_KEY", "")

# 預設使用者帳密庫 (儲存註冊帳號)
if "users_db" not in st.session_state:
    st.session_state.users_db = {
        "admin": {"password": "123", "role": "admin"}
    }

# =========================================================
# 2. 輔助 API 呼叫函式
# =========================================================
def gemini_generate_text(prompt, image_bytes=None):
    """呼叫 Gemini API 進行文字生成或圖片分析 (使用 REST API)"""
    api_key = st.session_state.api_key
    if not api_key:
        return "⚠️ 請先在左側邊欄輸入或設定 GEMINI_API_KEY！"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    parts = [{"text": prompt}]
    if image_bytes:
        encoded_image = base64.b64encode(image_bytes).decode('utf-8')
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": encoded_image
            }
        })
        
    payload = {"contents": [{"parts": parts}]}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        res_json = response.json()
        if "candidates" in res_json and len(res_json["candidates"]) > 0:
            return res_json["candidates"][0]["content"]["parts"][0]["text"]
        elif "error" in res_json:
            return f"❌ API 錯誤提示：{res_json['error'].get('message', res_json)}"
        else:
            return f"❌ API 回應異常：{res_json}"
    except Exception as e:
        return f"❌ 連線失敗：{str(e)}"

# =========================================================
# 3. Gemini 商品圖片與文案生成邏輯
# =========================================================
def analyze_product_image(image_bytes):
    prompt = """
你是專業電商商品圖片分析 AI。
請仔細分析使用者上傳的商品圖片。

重要規則：
1. 不可以憑空捏造圖片看不到的資訊。
2. 看不清楚的品牌、型號、規格、容量、材質，請寫「待確認」。
3. 商品包裝上的文字只能描述你實際看見的內容。
4. 不可以自行發明價格、療效、認證或品牌。
5. 如果圖片中有多個物品，找出最主要、最清楚的商品。
6. 用繁體中文回答。

請按照以下格式：

【商品辨識】
商品名稱：
品牌：
類別：
主要顏色：
外觀：
材質：
包裝：
可辨識文字：
型號：
規格：

【商品賣點】
1.
2.
3.

【商品使用情境】
1.
2.
3.

【圖片判斷】
圖片清晰度：
主要商品：
是否有多商品：
可能需要人工確認的資訊：

【電商建議】
蝦皮展示重點：
TikTok 展示重點：
即夢 AI 2.5 畫面建議：

最後再次提醒：正式發布前仍需人工確認商品資訊與規格。
"""
    return gemini_generate_text(prompt, image_bytes=image_bytes)

def generate_marketing_copy(product_info, analysis_text):
    prompt = f"""
你是一位頂級電商文案大師。請根據以下【商品資訊】與【圖片分析結果】，生成 4 個平台的專屬銷售文案：
1. 蝦皮 (Shopee) - 著重SEO關鍵字、規格標示、活動促銷
2. TikTok - 著重短影音腳本 hook、痛點引發、口語化
3. Facebook - 著重故事行銷、社群互動、詳細特色說明
4. Instagram - 著重視覺感、精簡俐落、Hashtag 標籤

【商品資訊】：{product_info}
【圖片分析】：{analysis_text}

請用繁體中文輸出，並清楚標示各平台區塊。
"""
    return gemini_generate_text(prompt)

def generate_jimeng_prompts(product_info, analysis_text):
    prompt = f"""
你是一位即夢 AI 2.5 (Jimeng AI) 提詞專家。請根據商品特色生成生圖與生成影片的 Prompt。

格式需求：
---
### 🖼️ 即夢 AI 2.5 生圖 Prompt (Image Generation)
**中文提示詞：**
**English Prompt:**
**Negative Prompt (負向提示詞):** text, watermark, bad quality, distorted, extra limbs, blur, logo drift

---
### 🎥 即夢 AI 2.5 運鏡影片 Prompt (Video Generation)
**中文影片提示詞：** (包含鏡頭運軌描述，如：鏡頭緩慢拉近、環繞商品、特寫質感)
**English Video Prompt:**
**運鏡設定建議:** 鏡頭速度 1.0x, 保持商品主體穩定 (no text drift)

【商品資訊】：{product_info}
【圖片分析】：{analysis_text}
"""
    return gemini_generate_text(prompt)

# =========================================================
# 4. 介面模組 (會員登入與註冊)
# =========================================================
def auth_page():
    st.subheader("🔑 會員中心")
    
    tab_login, tab_register = st.tabs(["🔒 帳號登入", "📝 註冊新帳號"])
    
    with tab_login:
        col1, _ = st.columns([1, 1])
        with col1:
            username = st.text_input("帳號", key="login_user")
            password = st.text_input("密碼", type="password", key="login_pwd")
            if st.button("登入", type="primary"):
                db = st.session_state.users_db
                if username in db and db[username]["password"] == password:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.user_role = db[username]["role"]
                    st.success(f"登入成功！歡迎，{username}")
                    st.rerun()
                else:
                    st.error("帳號或密碼錯誤！")

    with tab_register:
        col2, _ = st.columns([1, 1])
        with col2:
            new_user = st.text_input("新帳號名稱", key="reg_user")
            new_pwd = st.text_input("設定密碼", type="password", key="reg_pwd")
            confirm_pwd = st.text_input("再次確認密碼", type="password", key="reg_pwd_confirm")
            
            if st.button("建立帳號"):
                if not new_user or not new_pwd:
                    st.warning("請填寫完整的帳號與密碼！")
                elif new_user in st.session_state.users_db:
                    st.error("此帳號已被註冊，請換一個名字。")
                elif new_pwd != confirm_pwd:
                    st.error("兩次輸入的密碼不一致！")
                else:
                    st.session_state.users_db[new_user] = {
                        "password": new_pwd,
                        "role": "user"
                    }
                    st.success("🎉 註冊成功！請切換到「帳號登入」頁籤進行登入。")

def sidebar():
    with st.sidebar:
        st.title("🛒 功能選單")
        
        st.subheader("🔑 API 設定")
        input_key = st.text_input(
            "Gemini API Key", 
            value=st.session_state.api_key, 
            type="password",
            help="請至 Google AI Studio 免費申請 API Key 並貼於此處"
        )
        if input_key != st.session_state.api_key:
            st.session_state.api_key = input_key
            st.success("API Key 已更新！")

        st.divider()

        if st.session_state.logged_in:
            st.write(f"👤 歡迎，**{st.session_state.username}**")
            st.caption(f"身分：{st.session_state.user_role}")
            if st.button("登出"):
                st.session_state.logged_in = False
                st.session_state.username = ""
                st.rerun()
        else:
            st.info("請先於右側登入或註冊帳號。")

# =========================================================
# 5. 主程式頁面 (Main Logic)
# =========================================================
def main():
    sidebar()

    st.title("🛒 AI 全方位電商文案與即夢 2.5 Prompt 生成器")
    st.caption("結合 Gemini 圖片辨識 + 蝦皮/TikTok/FB/IG 文案 + 即夢 AI 2.5 繪圖影片 Prompt")

    if not st.session_state.logged_in:
        auth_page()
        return

    tab1, tab2 = st.tabs(["🚀 一鍵 AI 分析與生成", "📋 完整結果中心"])

    with tab1:
        st.subheader("1. 填寫商品資訊與上傳圖片")
        col_a, col_b = st.columns([1, 1])
        
        with col_a:
            product_name = st.text_input("商品名稱", placeholder="例：極致保濕修護精華液")
            product_features = st.text_area("補充特點/優惠（選填）", placeholder="例：買一送一、全素可可用、敏感肌適用")
            uploaded_file = st.file_uploader("上傳商品圖片 (JPG/PNG)", type=["jpg", "jpeg", "png"])
            
        with col_b:
            image_bytes = None
            if uploaded_file is not None:
                image_bytes = uploaded_file.read()
                st.image(image_bytes, caption="上傳的商品預覽", use_column_width=True)

        st.divider()

        if st.button("🔥 開始全自動 AI 分析與生成", type="primary", use_container_width=True):
            if not st.session_state.api_key:
                st.error("❌ 請先在左側邊欄輸入你的 Gemini API Key！")
            elif not uploaded_file and not product_name:
                st.warning("⚠️ 請至少輸入「商品名稱」或「上傳商品圖片」！")
            else:
                with st.spinner("🤖 Gemini 正在深度分析圖片與文字..."):
                    product_info_combined = f"名稱：{product_name}\n補充：{product_features}"
                    
                    img_analysis = "未上傳圖片，跳過圖片辨識。"
                    if image_bytes:
                        img_analysis = analyze_product_image(image_bytes)

                    copywriting = generate_marketing_copy(product_info_combined, img_analysis)
                    jimeng_prompts = generate_jimeng_prompts(product_info_combined, img_analysis)

                    st.session_state.analysis_results = {
                        "img_analysis": img_analysis,
                        "copywriting": copywriting,
                        "jimeng_prompts": jimeng_prompts
                    }
                    st.success("✅ 生成完成！請前往「📋 完整結果中心」查看結果，或直接於下方預覽。")

                    st.markdown("---")
                    st.subheader("🎉 生成結果快速預覽")
                    st.markdown(copywriting)

    with tab2:
        st.subheader("📋 AI 生成結果報告")
        if st.session_state.analysis_results is None:
            st.info("尚無分析資料，請先至第一頁點擊生成。")
        else:
            res = st.session_state.analysis_results
            
            with st.expander("🔍 1. Gemini 商品圖片辨識報告", expanded=True):
                st.markdown(res["img_analysis"])

            with st.expander("📝 2. 四大平台社群文案 (蝦皮 / TikTok / FB / IG)", expanded=True):
                st.markdown(res["copywriting"])

            with st.expander("🎨 3. 即夢 AI 2.5 繪圖與影片 Prompt 提詞", expanded=True):
                st.markdown(res["jimeng_prompts"])

if __name__ == "__main__":
    main()
