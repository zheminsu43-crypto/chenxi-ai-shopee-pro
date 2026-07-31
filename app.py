import io
from datetime import datetime

import streamlit as st
from google import genai
from PIL import Image, ImageOps


# ==================================================
# 網頁設定
# ==================================================
st.set_page_config(
    page_title="辰曦 AI 蝦皮半自動化 PRO",
    page_icon="🛒",
    layout="wide",
)

st.title("辰曦 AI 蝦皮半自動化 PRO")
st.caption(
    "網頁版 V1｜商品辨識・AI 選品・蝦皮文案・TikTok 文案・"
    "即夢指令・分潤合規檢查"
)


# ==================================================
# 系統設定
# ==================================================
MODEL_CANDIDATES = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
]

MAX_IMAGE_SIZE = 1600


# ==================================================
# 讀取 Gemini API 金鑰
# ==================================================
def get_api_key():
    try:
        api_key = str(st.secrets["GEMINI_API_KEY"]).strip()
        return api_key if api_key else None
    except Exception:
        return None


# ==================================================
# 處理商品圖片
# ==================================================
def prepare_image(uploaded_file):
    uploaded_file.seek(0)
    image = Image.open(uploaded_file)
    image = ImageOps.exif_transpose(image)

    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")

    image.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE))

    if image.mode == "RGBA":
        background = Image.new("RGB", image.size, "white")
        background.paste(image, mask=image.getchannel("A"))
        image = background

    return image


# ==================================================
# 建立辰曦 PRO 分析指令
# ==================================================
def build_prompt(data, selected_items):
    selected_text = "、".join(selected_items)

    return f"""
你現在是「辰曦 AI 蝦皮半自動化 PRO」專業電商營運助手。

請根據使用者上傳的商品圖片及提供的資料，以繁體中文完成分析。
輸出應專業、清楚、可直接複製使用，並遵守蝦皮分潤與廣告合規原則。

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

【商品資訊保護規則】
1. 僅能根據圖片與使用者提供的資料判斷。
2. 無法確認的品牌、容量、產地、成分、價格、香味、功效、
   保存期限、認證、組合數或贈品，必須標示「待確認」。
3. 不可自行虛構商品資訊。
4. 若圖片中有多個主體，選擇最大、最清楚、品牌辨識度最高的商品。
5. 若商品為單瓶、整組或隨機款無法確認，必須提醒人工確認。
6. 不可把圖片中僅供展示的物品宣稱為贈品。
7. 圖片、影片、文案與綁定的分潤商品必須一致。

【文案與合規規則】
1. 不得使用第一、最強、最好、100%、保證有效、永久、無敵、
   醫療級、治療、根治、神效、速效等誇大或無法證明的詞語。
2. 不得宣稱醫療療效、疾病治療或無法證實的效果。
3. 不得虛構價格、折扣、贈品、認證、容量與商品來源。
4. 商品資訊不足時，使用安全、中性的描述。
5. 正式發布前必須提醒人工核對價格、庫存、規格及分潤資格。

【即夢指令規則】
1. 即夢指令使用英文。
2. 海報內需要出現的文字使用繁體中文。
3. 必須鎖定商品原本品牌、包裝、形狀、顏色、比例、印刷文字與細節。
4. 不得改變品牌、重新設計包裝、添加錯誤商品或重複商品。
5. 不要人物、手部、主持人、代言人、浮水印、錯誤價格或假贈品。
6. 影片中商品不可變形、融化、閃爍、文字漂移或變成其他商品。

【輸出規則】
只輸出使用者選擇的功能。
若選擇「完整流程」，請依照下列全部區塊輸出。

一、商品辨識
- 品牌
- 商品名稱
- 商品類型
- 包裝與外觀特徵
- 圖片可確認資訊
- 待人工確認資訊

二、AI 選品分析
- 市場需求
- 商品吸引力
- 競爭程度
- 內容製作難度
- 合規風險
- 推薦分數：0～100
- 推薦等級：高潛力／可測試／暫不推薦
- 評分依據
若缺少月銷、價格、成本或分潤資料，必須註明為暫定內容潛力評分。

三、蝦皮上架文案
- 商品標題三組
- 商品短描述
- 完整商品描述
- 商品特色
- 使用方式
- 保存方式
- 注意事項
- 搜尋關鍵字
- 商品規格欄位
- 待確認資料

四、TikTok 文案
- 影片開場句
- 15 秒口播稿
- 30 秒口播稿
- 貼文文案
- Hashtag
- 行動引導文案

五、即夢生圖指令
- 1:1 蝦皮商品主圖英文指令
- 9:16 TikTok 商品海報英文指令
- 商品介紹圖英文指令
每段指令必須完整且可以直接複製使用。

六、即夢影片指令
- 9:16 直式商品展示影片英文指令
- 開場商品全景
- 中段包裝及材質特寫
- 緩慢推近或輕微環繞運鏡
- 結尾商品置中定格
- 商品全程保持原貌

七、蝦皮分潤合規檢查
- 商品與圖片是否一致
- 影片及文案是否與綁定商品一致
- 是否疑似禁止推廣商品
- 是否可能無法取得分潤
- 是否含療效或誇大宣稱
- 是否存在規格誤判
- 是否存在錯誤價格或假贈品
- 是否使用未確認資訊
- 適合發布／修改後發布／禁止發布
- 必須人工確認的項目

八、最終人工確認清單
- 可直接使用內容
- 必須修改內容
- 缺少的商品資料
- 發布前最後檢查事項
"""


# ==================================================
# 呼叫 Gemini，並自動嘗試可用模型
# ==================================================
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

            errors.append(f"{model_name}：沒有回傳文字內容")

        except Exception as error:
            errors.append(f"{model_name}：{str(error)}")

    raise RuntimeError(
        "所有備用模型均無法使用：\n\n" + "\n\n".join(errors)
    )


# ==================================================
# 1｜上傳商品圖片
# ==================================================
st.subheader("1｜上傳商品圖片")

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
        st.error("圖片讀取失敗，請換一張 JPG 或 PNG 圖片。")
        st.code(str(error))


# ==================================================
# 2｜填寫商品資料
# ==================================================
st.subheader("2｜填寫商品資料")

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


# ==================================================
# 3｜選擇目標平台
# ==================================================
st.subheader("3｜選擇目標平台")

target_platform = st.radio(
    "目標平台",
    ["蝦皮", "TikTok", "蝦皮＋TikTok"],
    horizontal=True,
)


# ==================================================
# 4｜選擇生成內容
# ==================================================
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
    options=generate_options,
    default=["完整流程"],
)

if "完整流程" in selected_items and len(selected_items) > 1:
    st.info("已選擇「完整流程」，系統會產生全部內容。")


# ==================================================
# 5｜開始分析
# ==================================================
st.subheader("5｜開始分析")

start_button = st.button(
    "啟動辰曦 PRO",
    type="primary",
    use_container_width=True,
)

if start_button:
    api_key = get_api_key()

    if prepared_image is None:
        st.error("請先上傳一張有效的商品圖片。")

    elif not selected_items:
        st.error("請至少選擇一個生成內容。")

    elif not api_key:
        st.error(
            "尚未設定 GEMINI_API_KEY。"
            "請到 Manage app → Settings → Secrets 設定。"
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

        effective_items = selected_items

        if "完整流程" in selected_items:
            effective_items = ["完整流程"]

        prompt = build_prompt(product_data, effective_items)

        try:
            with st.spinner(
                "辰曦 PRO 正在辨識商品並產生內容，請稍候……"
            ):
                result, used_model = analyze_with_gemini(
                    api_key=api_key,
                    prompt=prompt,
                    image=prepared_image,
                )

            st.success("分析完成")
            st.caption(f"本次使用模型：{used_model}")

            st.subheader("6｜完整結果")
            st.markdown(result)

            st.subheader("7｜複製與下載")

            st.text_area(
                "完整結果文字",
                value=result,
                height=600,
            )

            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"辰曦_PRO_商品分析_{current_time}.txt"

            st.download_button(
                label="下載完整結果",
                data=result.encode("utf-8"),
                file_name=file_name,
                mime="text/plain",
                use_container_width=True,
            )

            st.warning(
                "正式發布前，請人工確認商品名稱、容量、產地、成分、"
                "保存期限、貨源、售價、庫存、組合數及分潤資格。"
            )

        except Exception as error:
            error_text = str(error)

            st.error("Gemini 分析失敗。")
            st.code(error_text)

            if "API_KEY" in error_text.upper() or "401" in error_text:
                st.warning(
                    "請檢查 Gemini API 金鑰是否正確，並確認金鑰未被刪除。"
                )

            elif "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
                st.warning(
                    "可能已達免費額度或速率限制，請稍後再試。"
                )

            elif "404" in error_text or "NOT_FOUND" in error_text:
                st.warning(
                    "目前帳戶可能無法使用所列模型。"
                    "程式已自動嘗試多個備用模型，請檢查錯誤內容。"
                )

            else:
                st.warning(
                    "請檢查網路、API 專案權限與 Google AI Studio 狀態。"
                )


# ==================================================
# 頁尾
# ==================================================
st.divider()
st.caption(
    "辰曦 AI 蝦皮半自動化 PRO｜"
    "AI 內容僅供輔助，正式發布前必須人工確認。"
)
