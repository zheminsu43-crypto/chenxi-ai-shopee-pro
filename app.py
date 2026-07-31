import streamlit as st
from google import genai
from PIL import Image


st.set_page_config(
    page_title="辰曦 AI 蝦皮半自動化 PRO",
    page_icon="🛒",
    layout="wide",
)

st.title("辰曦 AI 蝦皮半自動化 PRO")
st.caption("網頁版 V1｜商品分析、蝦皮文案、TikTok 文案、即夢指令與合規檢查")


def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return None


def build_prompt(data, selected_items):
    selected_text = "、".join(selected_items)

    return f"""
你現在是「辰曦 AI 蝦皮半自動化 PRO」專業電商營運助手。

請根據使用者上傳的商品圖片與商品資料，使用繁體中文完成分析。

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
需要生成：{selected_text}

【重要規則】
1. 只能根據圖片及使用者提供的資料判斷。
2. 無法確認的品牌、容量、產地、成分、價格、功效與規格，標示「待確認」。
3. 不可虛構價格、贈品、容量、產地、認證、香味、療效或商品效果。
4. 圖片、文案與綁定商品必須一致。
5. 避免第一、最強、100%、保證有效、醫療級、治療、根治、速效等誇大字詞。
6. 即夢指令必須鎖定原商品品牌、包裝、顏色、文字、比例與細節。
7. 即夢指令使用英文，但海報文字使用繁體中文。
8. 所有內容發布前必須提醒人工確認。

【輸出要求】
只輸出使用者選擇的內容。

商品辨識：
- 品牌
- 商品名稱
- 商品類型
- 包裝特徵
- 可確認資訊
- 待確認資訊

AI 選品分析：
- 市場需求
- 商品吸引力
- 競爭程度
- 內容製作難度
- 合規風險
- 推薦分數 0～100
- 推薦等級
- 評分依據

蝦皮上架文案：
- 商品標題三組
- 商品短描述
- 完整商品描述
- 商品特色
- 使用方式
- 注意事項
- 搜尋關鍵字
- 商品規格欄位
- 待確認資料

TikTok 文案：
- 影片開場句
- 15 秒口播稿
- 30 秒口播稿
- 貼文文案
- Hashtag
- 行動引導文案

即夢生圖指令：
- 1:1 蝦皮主圖英文指令
- 9:16 TikTok 海報英文指令
- 商品介紹圖英文指令
每段都要鎖定商品原貌。

即夢影片指令：
- 9:16 商品展示影片英文指令
- 開場全景
- 中段細節特寫
- 結尾商品定格
- 自然流暢運鏡
- 商品不可變形或改包裝

分潤合規檢查：
- 商品與圖片是否一致
- 是否疑似禁止推廣商品
- 是否可能無法取得分潤
- 是否含誇大或療效宣稱
- 是否有規格誤判風險
- 是否有假價格或假贈品
- 是否適合發布
- 必須人工確認項目
- 最終結果：可發布／修改後發布／禁止發布

若選擇「完整流程」，依序輸出：
1. 商品辨識
2. AI 選品分析
3. 蝦皮上架文案
4. TikTok 文案
5. 即夢生圖指令
6. 即夢影片指令
7. 分潤合規檢查
8. 最終人工確認清單
"""


st.subheader("1｜上傳商品圖片")

uploaded_file = st.file_uploader(
    "請上傳商品圖片",
    type=["jpg", "jpeg", "png", "webp"],
)

if uploaded_file:
    st.image(
        uploaded_file,
        caption="已上傳商品圖片",
        use_container_width=True,
    )


st.subheader("2｜填寫商品資料")

col1, col2 = st.columns(2)

with col1:
    product_name = st.text_input("商品名稱")
    product_price = st.text_input("商品價格")
    product_cost = st.text_input("商品成本")
    commission_rate = st.text_input("分潤比例")

with col2:
    monthly_sales = st.text_input("月銷量")
    product_rating = st.text_input("商品評分")
    product_url = st.text_input("商品連結")
    product_spec = st.text_area("商品規格")


st.subheader("3｜選擇目標平台")

target_platform = st.radio(
    "目標平台",
    ["蝦皮", "TikTok", "蝦皮＋TikTok"],
    horizontal=True,
)


st.subheader("4｜選擇生成內容")

generate_options = [
    "商品辨識",
    "AI 選品分析",
    "蝦皮上架文案",
    "TikTok 文案",
    "即夢生圖指令",
    "即夢影片指令",
    "分潤合規檢查",
    "完整流程",
]

selected_items = st.multiselect(
    "請選擇需要的功能",
    generate_options,
    default=["完整流程"],
)


st.subheader("5｜開始分析")

start_button = st.button(
    "啟動辰曦 PRO",
    type="primary",
    use_container_width=True,
)

if start_button:
    if uploaded_file is None:
        st.error("請先上傳商品圖片。")

    elif not selected_items:
        st.error("請至少選擇一個生成內容。")

    elif not get_api_key():
        st.error("尚未設定 GEMINI_API_KEY，請先到 Streamlit Secrets 設定。")

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

        prompt = build_prompt(product_data, selected_items)

        try:
            image = Image.open(uploaded_file)
            client = genai.Client(api_key=get_api_key())

            with st.spinner("辰曦 PRO 正在分析商品，請稍候……"):
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[prompt, image],
                )

            result = response.text

            st.success("分析完成")
            st.subheader("6｜完整結果")
            st.markdown(result)

            st.subheader("7｜複製與下載")

            st.text_area(
                "完整結果文字",
                value=result,
                height=500,
            )

            st.download_button(
                label="下載完整結果",
                data=result,
                file_name="辰曦_PRO_商品分析結果.txt",
                mime="text/plain",
                use_container_width=True,
            )

            st.warning(
                "正式發布前，請人工確認商品價格、容量、產地、成分、"
                "保存期限、貨源、庫存與分潤資格。"
            )

        except Exception as error:
            st.error("分析失敗，請檢查 Gemini API 金鑰、額度或網路狀況。")
            st.code(str(error))
