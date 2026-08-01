import io
from datetime import datetime

import streamlit as st
from google import genai
from PIL import Image, ImageOps


# =========================================================
# 辰曦 AI 蝦皮半自動化2.5 PRO
# 即夢 AI 2.5 優化版
# =========================================================

st.set_page_config(
    page_title="辰曦 AI 蝦皮半自動化 PRO｜即夢 AI 2.5",
    page_icon="🛒",
    layout="wide",
)

st.title("辰曦 AI 蝦皮半自動化 PRO")
st.caption(
    "即夢 AI 2.5 優化版｜商品辨識・AI 選品・蝦皮文案・TikTok 文案・"
    "即夢 2.5 生圖・即夢 2.5 影片・分潤合規檢查"
)


# =========================================================
# 系統設定
# =========================================================

MODEL_CANDIDATES = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
]

MAX_IMAGE_SIZE = 1600


# =========================================================
# API KEY
# =========================================================

def get_api_key():
    try:
        api_key = str(st.secrets["GEMINI_API_KEY"]).strip()
        return api_key if api_key else None
    except Exception:
        return None


# =========================================================
# 商品圖片處理
# =========================================================

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
            mask=image.getchannel("A")
        )
        image = background

    return image


# =========================================================
# 即夢 AI 2.5 核心規則
# =========================================================

JIMENG_25_CORE_RULES = """
【即夢 AI 2.5 核心生成規則】

你現在產生的是「即夢 AI 2.5」專用提示詞。

一、商品原貌鎖定
- 必須以使用者上傳圖片中的實際商品作為唯一商品來源。
- 保持商品原本品牌、包裝、瓶身、盒身、形狀、比例、顏色、材質。
- 保持原本標籤、印刷文字、Logo、圖案與包裝結構。
- 不得重新設計品牌。
- 不得重新設計包裝。
- 不得擅自更改商品顏色。
- 不得增加不存在的配件。
- 不得增加不存在的贈品。
- 不得生成第二個相同商品。
- 不得把商品變成其他商品。

二、商品一致性
- Product identity must remain consistent throughout the entire scene.
- Keep the original product shape and proportions.
- Keep the original packaging design.
- Keep visible printed text and logo placement unchanged.
- No duplicate products unless explicitly requested.
- No product transformation.
- No melting.
- No deformation.
- No flickering.
- No floating packaging.
- No sudden object replacement.
- No warped label.
- No drifting text.
- No changing logo.
- No changing bottle or box shape.

三、人物限制
- 預設不要人物。
- 不要手部。
- 不要主持人。
- 不要代言人。
- 不要模特兒。
- 不要人物拿著商品。
- 不要人物遮擋商品。

四、畫面限制
- 不要浮水印。
- 不要錯誤價格。
- 不要假贈品。
- 不要錯誤品牌。
- 不要虛構產品。
- 不要多餘商品。
- 不要錯誤文字。
- 不要低品質模糊商品。
- 不要過度反光導致包裝文字消失。

五、商業內容
- 畫面必須以商品為視覺主體。
- 商品必須清楚、完整、容易辨識。
- 商品不可被背景或裝飾物搶走視覺焦點。
- 使用高級商業產品攝影質感。
- 適合電商、蝦皮、TikTok 商品行銷內容。

六、圖片指令
- 指令本體使用英文。
- 如果畫面需要出現文字，文字內容使用繁體中文。
- 不要在英文 prompt 中自行創造未確認的商品資訊。
- 未確認資訊不得自行補完。

七、影片指令
影片必須維持同一商品身份。

推薦流程：
Opening：
商品完整出現並置中。

Middle：
慢速推近商品，展示包裝、材質與細節。

Camera：
slow cinematic push-in,
subtle orbit,
smooth camera movement,
stable composition.

Ending：
商品回到置中構圖並穩定定格。

整個影片：
- 商品不可變形。
- 商品不可變色。
- 包裝不可改變。
- Logo 不可改變。
- 文字不可漂移。
- 不可突然增加商品。
- 不可突然減少商品。
- 不可出現人物。
- 不可出現手。
- 不可出現浮水印。
"""


# =========================================================
# 建立辰曦 PRO Prompt
# =========================================================

def build_prompt(data, selected_items):

    selected_text = "、".join(selected_items)

    return f"""
你現在是「辰曦 AI 蝦皮半自動化 PRO」專業電商 AI 營運助手。

你需要根據：
1. 使用者上傳的商品圖片
2. 使用者提供的商品資料

進行商品辨識、選品分析、電商文案以及「即夢 AI 2.5」專用生圖／影片提示詞生成。

請使用繁體中文回答。
但是「即夢 AI 2.5 生圖指令」與「即夢 AI 2.5 影片指令」本體必須使用英文。

=========================================================
【商品資料】
=========================================================

商品名稱：
{data["商品名稱"] or "待確認"}

商品價格：
{data["商品價格"] or "待確認"}

商品成本：
{data["商品成本"] or "待確認"}

分潤比例：
{data["分潤比例"] or "待確認"}

月銷量：
{data["月銷量"] or "待確認"}

商品評分：
{data["商品評分"] or "待確認"}

商品連結：
{data["商品連結"] or "待確認"}

商品規格：
{data["商品規格"] or "待確認"}

目標平台：
{data["目標平台"]}

使用者選擇：
{selected_text}


=========================================================
【AI 商品辨識保護】
=========================================================

1. 僅能根據圖片與使用者提供資料判斷。
2. 無法確認的資訊必須標示「待確認」。
3. 不得自行虛構品牌。
4. 不得自行虛構容量。
5. 不得自行虛構產地。
6. 不得自行虛構成分。
7. 不得自行虛構功效。
8. 不得自行虛構價格。
9. 不得自行虛構贈品。
10. 不得自行虛構認證。
11. 不得自行虛構保存期限。
12. 不得自行虛構規格。
13. 若圖片中有多個商品主體，選擇最大、最清楚、
    品牌辨識度最高的商品作為主要商品。
14. 如果無法確認單瓶、整組、組合或隨機款，
    必須標示「待人工確認」。
15. 圖片中僅供展示的物品不得宣稱為贈品。


=========================================================
【文案合規】
=========================================================

不得使用：
第一、最強、最好、100%、保證有效、永久、無敵、
醫療級、治療、根治、神效、速效等無法證明的誇大詞語。

不得：
- 宣稱疾病治療
- 宣稱醫療療效
- 虛構折扣
- 虛構價格
- 虛構贈品
- 虛構認證
- 虛構容量
- 虛構產地
- 虛構商品來源

資訊不足時：
使用安全、中性的描述。

正式發布前：
提醒人工確認價格、庫存、規格、商品資格與分潤資格。


=========================================================
{JIMENG_25_CORE_RULES}
=========================================================


=========================================================
【輸出規則】
=========================================================

只輸出使用者選擇的功能。

如果使用者選擇「完整流程」，
請完整輸出以下所有內容。


=========================================================
一、商品辨識
=========================================================

- 品牌
- 商品名稱
- 商品類型
- 包裝與外觀特徵
- 圖片可確認資訊
- 待人工確認資訊


=========================================================
二、AI 選品分析
=========================================================

- 市場需求
- 商品吸引力
- 競爭程度
- 內容製作難度
- 合規風險
- 推薦分數：0～100
- 推薦等級：高潛力／可測試／暫不推薦
- 評分依據

如果缺少：
月銷量、價格、成本、分潤資料，
必須明確說明：
「目前為暫定內容潛力評分。」


=========================================================
三、蝦皮上架文案
=========================================================

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


=========================================================
四、TikTok 文案
=========================================================

- 影片開場句
- 15 秒口播稿
- 30 秒口播稿
- 貼文文案
- Hashtag
- 行動引導文案


=========================================================
五、即夢 AI 2.5 生圖指令
=========================================================

請產生：

【A｜1:1 蝦皮商品主圖】

輸出：
- English Prompt
- Negative Prompt

要求：
- square 1:1
- premium commercial product photography
- product centered
- clean composition
- product clearly visible
- realistic materials
- realistic lighting
- original packaging preserved
- original product identity preserved


【B｜9:16 TikTok 商品海報】

輸出：
- English Prompt
- Negative Prompt

要求：
- vertical 9:16
- product centered
- premium advertising composition
- strong visual hierarchy
- suitable for TikTok
- original packaging preserved


【C｜商品介紹圖】

輸出：
- English Prompt
- Negative Prompt

要求：
- product-focused
- clean premium background
- close-up product details
- material and packaging details visible
- no person
- no hand


=========================================================
六、即夢 AI 2.5 影片指令
=========================================================

產生一段：
「9:16 直式商品展示影片」

輸出：

【Video Prompt】
完整英文指令。

必須包含：

Scene 1 — Opening
- 商品完整出現
- 商品置中
- 商品清楚可見

Scene 2 — Product Detail
- 展示包裝
- 展示材質
- 展示商品細節

Scene 3 — Camera Motion
- slow cinematic push-in
- subtle orbit movement
- smooth camera movement
- stable framing

Scene 4 — Ending
- 商品重新置中
- 穩定定格
- 商品保持完整原貌

【Negative Prompt】
必須明確禁止：

- product deformation
- product transformation
- packaging redesign
- logo change
- text distortion
- text drifting
- duplicated product
- extra product
- missing product
- color shift
- shape change
- melting
- flickering
- warped packaging
- floating objects
- human
- hands
- presenter
- spokesperson
- watermark
- fake gift
- fake price


=========================================================
七、即夢 AI 2.5 爆款帶貨版本
=========================================================

另外產生一份「9:16 電商帶貨影片版本」。

必須包含：

- 0～3 秒：商品第一視覺
- 3～7 秒：商品細節
- 7～12 秒：商品特色展示
- 12～15 秒：商品置中結尾

要求：

畫面必須保持高級、乾淨、商業化。

不要人物。
不要手。
不要主持人。
不要代言人。

商品必須全程保持原貌。

不得自行加入未確認商品賣點。


=========================================================
八、蝦皮分潤合規檢查
=========================================================

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

「適合發布」
或
「修改後發布」
或
「禁止發布」

並列出：
「必須人工確認項目」。


=========================================================
九、最終人工確認清單
=========================================================

- 可直接使用內容
- 必須修改內容
- 缺少商品資料
- 發布前最後檢查事項


=========================================================
【最重要輸出要求】
=========================================================

即夢 AI 2.5 Prompt 必須可以直接複製。

不要在 Prompt 中加入：
「你可以」
「建議」
「例如」
「請自行修改」

要直接生成完整指令。

不要把未確認的商品資訊當成事實。

商品圖片中的原始商品永遠是主要參考來源。
"""


# =========================================================
# Gemini 分析
# =========================================================

def analyze_with_gemini(api_key, prompt, image):

    client = genai.Client(api_key=api_key)

    errors = []

    for model_name in MODEL_CANDIDATES:

        try:

            response = client.models.generate_content(
                model=model_name,
                contents=[
                    prompt,
                    image,
                ],
            )

            result = getattr(response, "text", None)

            if result and result.strip():
                return result.strip(), model_name

            errors.append(
                f"{model_name}：沒有回傳文字內容"
            )

        except Exception as error:

            errors.append(
                f"{model_name}：{str(error)}"
            )

    raise RuntimeError(
        "所有備用模型均無法使用：\n\n"
        + "\n\n".join(errors)
    )


# =========================================================
# 1｜商品圖片
# =========================================================

st.subheader("1｜上傳商品圖片")

uploaded_file = st.file_uploader(
    "請上傳商品圖片",
    type=[
        "jpg",
        "jpeg",
        "png",
        "webp",
    ],
)

prepared_image = None

if uploaded_file is not None:

    try:

        prepared_image = prepare_image(
            uploaded_file
        )

        st.image(
            prepared_image,
            caption="已上傳商品圖片",
            use_container_width=True,
        )

    except Exception as error:

        st.error(
            "圖片讀取失敗，請換一張 JPG 或 PNG 圖片。"
        )

        st.code(str(error))


# =========================================================
# 2｜商品資料
# =========================================================

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


# =========================================================
# 3｜平台
# =========================================================

st.subheader("3｜選擇目標平台")

target_platform = st.radio(
    "目標平台",
    [
        "蝦皮",
        "TikTok",
        "蝦皮＋TikTok",
    ],
    horizontal=True,
)


# =========================================================
# 4｜生成內容
# =========================================================

st.subheader("4｜選擇生成內容")

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
    "請選擇需要的功能",
    options=generate_options,
    default=["完整流程"],
)

if (
    "完整流程" in selected_items
    and len(selected_items) > 1
):

    st.info(
        "已選擇「完整流程」，系統會產生全部內容。"
    )


# =========================================================
# 5｜啟動
# =========================================================

st.subheader("5｜開始分析")

start_button = st.button(
    "🚀 啟動辰曦 PRO｜即夢 AI 2.5",
    type="primary",
    use_container_width=True,
)


if start_button:

    api_key = get_api_key()

    if prepared_image is None:

        st.error(
            "請先上傳一張有效的商品圖片。"
        )

    elif not selected_items:

        st.error(
            "請至少選擇一個生成內容。"
        )

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

        if "完整流程" in selected_items:

            effective_items = [
                "完整流程"
            ]

        else:

            effective_items = selected_items

        prompt = build_prompt(
            product_data,
            effective_items,
        )

        try:

            with st.spinner(
                "辰曦 PRO 正在分析商品並生成即夢 AI 2.5 專用指令……"
            ):

                result, used_model = analyze_with_gemini(
                    api_key=api_key,
                    prompt=prompt,
                    image=prepared_image,
                )

            st.success(
                "分析完成｜即夢 AI 2.5 指令已生成"
            )

            st.caption(
                f"本次使用模型：{used_model}"
            )

            # =================================================
            # 結果
            # =================================================

            st.subheader(
                "6｜辰曦 PRO 完整結果"
            )

            st.markdown(result)

            # =================================================
            # 複製區
            # =================================================

            st.subheader(
                "7｜複製與下載"
            )

            st.text_area(
                "完整結果文字",
                value=result,
                height=700,
            )

            current_time = datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )

            file_name = (
                f"辰曦_PRO_即夢2.5_"
                f"商品分析_{current_time}.txt"
            )

            st.download_button(
                label="⬇️ 下載完整結果",
                data=result.encode("utf-8"),
                file_name=file_name,
                mime="text/plain",
                use_container_width=True,
            )

            # =================================================
            # 最終提醒
            # =================================================

            st.warning(
                "正式發布前，請人工確認商品名稱、容量、產地、"
                "成分、保存期限、貨源、售價、庫存、組合數、"
                "商品規格及分潤資格。"
            )

        except Exception as error:

            error_text = str(error)

            st.error(
                "Gemini 分析失敗。"
            )

            st.code(error_text)

            if (
                "API_KEY" in error_text.upper()
                or "401" in error_text
            ):

                st.warning(
                    "請檢查 Gemini API 金鑰是否正確，"
                    "並確認金鑰未被刪除。"
                )

            elif (
                "429" in error_text
                or "RESOURCE_EXHAUSTED"
                in error_text
            ):

                st.warning(
                    "可能已達免費額度或速率限制，"
                    "請稍後再試。"
                )

            elif (
                "404" in error_text
                or "NOT_FOUND"
                in error_text
            ):

                st.warning(
                    "目前帳戶可能無法使用所列模型。"
                    "程式已自動嘗試多個備用模型，"
                    "請檢查錯誤內容。"
                )

            else:

                st.warning(
                    "請檢查網路、API 專案權限與 "
                    "Google AI Studio 狀態。"
                )


# =========================================================
# 頁尾
# =========================================================

st.divider()

st.caption(
    "辰曦 AI 蝦皮半自動化 PRO｜"
    "即夢 AI 2.5 優化版｜"
    "AI 內容僅供輔助，正式發布前必須人工確認。"
)
