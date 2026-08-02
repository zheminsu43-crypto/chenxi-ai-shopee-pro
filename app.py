# =========================================================
# Session
# =========================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "page" not in st.session_state:
    st.session_state.page = "login"

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = ""

if "generated_prompt" not in st.session_state:
    st.session_state.generated_prompt = ""

if "generated_copy" not in st.session_state:
    st.session_state.generated_copy = ""


def logout():

    st.session_state.logged_in = False

    st.session_state.pop("username", None)
    st.session_state.pop("member", None)

    st.session_state.analysis_result = ""
    st.session_state.generated_prompt = ""
    st.session_state.generated_copy = ""

    st.session_state.page = "login"

    st.rerun()


# =========================================================
# CSS
# =========================================================

st.markdown(
    """
    <style>

    .main-title {
        text-align: center;
        font-size: 42px;
        font-weight: 800;
        margin-top: 20px;
        margin-bottom: 10px;
    }

    .main-subtitle {
        text-align: center;
        font-size: 17px;
        opacity: 0.75;
        margin-bottom: 30px;
    }

    .card {
        padding: 20px;
        border-radius: 15px;
        border: 1px solid rgba(128,128,128,.25);
        margin-bottom: 15px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# 登入頁
# =========================================================

def login_page():

    st.markdown(
        '<div class="main-title">'
        '🛒 AI 蝦皮半自動化 2.5 PRO'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="main-subtitle">'
        '會員登入｜商品分析｜圖片處理｜即夢 2.5 指令生成'
        '</div>',
        unsafe_allow_html=True
    )

    _, center, _ = st.columns([1, 2, 1])

    with center:

        st.subheader("🔐 會員登入")

        username = st.text_input(
            "會員帳號",
            placeholder="輸入會員帳號",
            key="login_username"
        )

        password = st.text_input(
            "會員密碼",
            type="password",
            placeholder="輸入會員密碼",
            key="login_password"
        )

        if st.button(
            "🚀 登入系統",
            type="primary",
            use_container_width=True
        ):

            if not username or not password:

                st.error("請輸入會員帳號與密碼。")

            else:

                success, result = check_login(
                    username,
                    password
                )

                if success:

                    st.session_state.logged_in = True

                    st.session_state.username = (
                        username.strip().lower()
                    )

                    st.session_state.member = result

                    st.session_state.page = "main"

                    st.rerun()

                else:

                    messages = {

                        "expired":
                        "⛔ 會員資格已到期，請聯絡管理員續期。",

                        "disabled":
                        "⛔ 此會員帳號目前已停權。",

                        "invalid_date":
                        "⛔ 會員到期日資料錯誤。",

                        "invalid":
                        "❌ 帳號或密碼錯誤。"

                    }

                    st.error(
                        messages.get(
                            result,
                            "❌ 登入失敗。"
                        )
                    )

        st.divider()

        if st.button(
            "📝 還沒有帳號？註冊會員",
            use_container_width=True
        ):

            st.session_state.page = "register"

            st.rerun()

        st.divider()

        st.caption(
            "本系統使用本機會員帳號與密碼。"
        )

        with st.expander("🔐 管理員測試帳號"):

            st.code(
                "帳號：admin\n密碼：admin123"
            )


# =========================================================
# 註冊頁
# =========================================================

def register_page():

    st.markdown(
        '<div class="main-title">'
        '📝 會員註冊'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="main-subtitle">'
        '建立 AI 蝦皮半自動化 2.5 PRO 會員帳號'
        '</div>',
        unsafe_allow_html=True
    )

    _, center, _ = st.columns([1, 2, 1])

    with center:

        st.subheader("👤 建立會員帳號")

        name = st.text_input(
            "姓名 / 暱稱",
            placeholder="例如：王小明"
        )

        email = st.text_input(
            "Email",
            placeholder="例如：example@gmail.com"
        )

        username = st.text_input(
            "會員帳號",
            placeholder="3～30 個英數字或底線"
        )

        password = st.text_input(
            "會員密碼",
            type="password",
            placeholder="至少 6 個字元"
        )

        password_confirm = st.text_input(
            "再次輸入密碼",
            type="password"
        )

        if st.button(
            "🚀 建立會員帳號",
            type="primary",
            use_container_width=True
        ):

            username_clean = username.strip().lower()
            email_clean = email.strip().lower()

            if not name.strip():

                st.error("請輸入姓名或暱稱。")

            elif not re.fullmatch(
                r"[^@\s]+@[^@\s]+\.[^@\s]+",
                email_clean
            ):

                st.error("請輸入正確 Email。")

            elif not re.fullmatch(
                r"[a-z0-9_]{3,30}",
                username_clean
            ):

                st.error(
                    "帳號只能使用小寫英數字與底線，長度 3～30。"
                )

            elif len(password) < 6:

                st.error(
                    "密碼至少需要 6 個字元。"
                )

            elif password != password_confirm:

                st.error(
                    "兩次輸入的密碼不一致。"
                )

            else:

                success, result = create_member(
                    username_clean,
                    password,
                    name,
                    email_clean
                )

                if success:

                    st.success(
                        "🎉 會員帳號建立成功！"
                    )

                    st.info(
                        f"會員資格預設 {DEFAULT_MEMBER_DAYS} 天，"
                        "請返回登入。"
                    )

                else:

                    st.error(str(result))

        st.divider()

        if st.button(
            "⬅️ 返回登入",
            use_container_width=True
        ):

            st.session_state.page = "login"

            st.rerun()


# =========================================================
# 登入判斷
# =========================================================

if not st.session_state.logged_in:

    if st.session_state.page == "register":

        register_page()

    else:

        login_page()

    st.stop()


# =========================================================
# 會員資料
# =========================================================

current_username = st.session_state.get(
    "username",
    ""
)

current_member = st.session_state.get(
    "member",
    {}
)

latest_member = find_member(
    current_username
)

if latest_member:

    current_member = latest_member

    st.session_state.member = latest_member


member_id = current_member.get(
    "id",
    ""
)

member_name = str(
    current_member.get(
        "name",
        current_username
    )
)

member_email = str(
    current_member.get(
        "email",
        ""
    )
)

member_role = str(
    current_member.get(
        "role",
        "member"
    )
)

member_status = str(
    current_member.get(
        "status",
        "active"
    )
)

member_expires = str(
    current_member.get(
        "expires",
        ""
    )
)


try:

    expire_date = date.fromisoformat(
        member_expires
    )

    remaining_days = (
        expire_date
        - date.today()
    ).days

except Exception:

    remaining_days = -999


if member_status.lower() != "active":

    st.error(
        "⛔ 此會員帳號目前已停權。"
    )

    if st.button("🚪 返回登入"):

        logout()

    st.stop()


# =========================================================
# 商品分類判斷
# =========================================================

def detect_product_category(text):

    text = text.lower()

    categories = {

        "保養品": [
            "保養",
            "精華",
            "乳液",
            "面霜",
            "面膜",
            "化妝水",
            "洗面",
            "防曬",
            "美容"
        ],

        "3C": [
            "手機",
            "耳機",
            "充電",
            "鍵盤",
            "滑鼠",
            "電腦",
            "平板",
            "喇叭",
            "usb"
        ],

        "居家": [
            "家用",
            "收納",
            "清潔",
            "床",
            "枕頭",
            "棉被",
            "廚房",
            "鍋",
            "居家"
        ],

        "服飾": [
            "衣服",
            "上衣",
            "褲",
            "外套",
            "鞋",
            "襪",
            "包包",
            "帽"
        ],

        "食品": [
            "食品",
            "零食",
            "餅乾",
            "茶",
            "咖啡",
            "飲品",
            "果乾"
        ],

        "汽機車": [
            "汽車",
            "機車",
            "車用",
            "安全帽",
            "手把",
            "雨衣"
        ]

    }

    for category, keywords in categories.items():

        for keyword in keywords:

            if keyword in text:

                return category

    return "其他"


# =========================================================
# 商品分析
# =========================================================

def analyze_product(
    product_name,
    category,
    price,
    selling_points
):

    detected = detect_product_category(
        product_name + " " + selling_points
    )

    if category == "自動判斷":

        category = detected

    selling_list = [
        x.strip()
        for x in re.split(
            r"[,，、\n]+",
            selling_points
        )
        if x.strip()
    ]

    if not selling_list:

        selling_list = [
            "高質感設計",
            "實用方便",
            "適合日常使用"
        ]

    price_text = (
        f"NT$ {price:,.0f}"
        if price > 0
        else "價格待補"
    )

    result = f"""
# 📦 商品分析結果

## 商品
{product_name or "未輸入商品名稱"}

## 商品分類
{category}

## 價格
{price_text}

## 核心賣點
"""

    for item in selling_list[:8]:

        result += f"- {item}\n"

    result += f"""

## 🎯 建議銷售定位

此商品可採用「{category}」類型內容進行包裝。

建議強調：

1. 商品外觀與質感
2. 實際使用情境
3. 商品特色
4. 使用便利性
5. 消費者購買理由

## 🛒 蝦皮主圖方向

建議：

- 商品置中
- 保持商品原始外觀
- 背景乾淨
- 商品清楚
- 高質感商業攝影
- 避免不必要人物
- 避免浮水印
- 避免多餘品牌修改
"""

    return result.strip()


# =========================================================
# 即夢 2.5 指令生成
# =========================================================

def generate_seedance_prompt(
    product_name,
    category,
    selling_points,
    style,
    duration
):

    if not product_name.strip():

        product_name = "商品"

    if category == "自動判斷":

        category = detect_product_category(
            product_name + " " + selling_points
        )

    prompt = f"""
【即夢 2.5 商品影片指令】

主體：
以「{product_name}」作為唯一主要商品主體。

商品分類：
{category}

核心要求：
保持商品原始外觀、原始比例、原始材質、
原始顏色與品牌識別。

影片比例：
9:16 垂直短影音。

影片長度：
約 {duration} 秒。

影片風格：
{style}

畫面設計：
高質感商業產品攝影。
商品清楚置中。
鏡頭穩定。
自然高級光線。
背景乾淨。
電商廣告質感。

內容節奏：

第一段：
快速建立商品視覺焦點。

第二段：
展示商品細節、材質、外觀與特色。

第三段：
展示商品使用情境與主要賣點。

第四段：
以商品主體作為結尾畫面。

商品賣點：
{selling_points}

AI 誤判保護：
如果輸入圖片中存在多個物體，
優先選擇最大、最清楚、最具品牌識別性的商品
作為主要主體。

禁止：
不要任意修改商品外觀。
不要改變商品品牌。
不要改變商品文字。
不要增加不存在的產品配件。
不要加入無關人物。
不要加入浮水印。
不要加入平台 Logo。
不要加入錯誤文字。
不要讓商品變形。
不要讓商品數量突然增加。

品質：
高細節。
高解析度。
自然光影。
真實材質。
商業廣告質感。
流暢鏡頭。
乾淨構圖。
9:16 直式短影音。
"""

    return prompt.strip()


# =========================================================
# 蝦皮商品文案
# =========================================================

def generate_shopee_copy(
    product_name,
    category,
    selling_points,
    price
):

    points = [
        x.strip()
        for x in re.split(
            r"[,，、\n]+",
            selling_points
        )
        if x.strip()
    ]

    if not points:

        points = [
            "高質感設計",
            "實用方便",
            "適合日常使用"
        ]

    point_text = "\n".join(
        [
            f"✅ {item}"
            for item in points[:6]
        ]
    )

    price_text = (
        f"NT$ {price:,.0f}"
        if price > 0
        else "價格請見賣場"
    )

    copy = f"""
【{product_name}】

✨ 商品分類：{category}

🔥 商品特色

{point_text}

💰 商品價格

{price_text}

📌 商品介紹

精選「{product_name}」，
以實用性、質感與日常使用體驗為主要訴求。

無論自己使用，
或作為送禮選擇，
都能展現商品本身特色。

🛒 購買前提醒

・下單前請確認商品規格
・不同螢幕可能產生些微色差
・實際商品以收到的商品為準

#蝦皮購物
#{category}
#好物推薦
#生活好物
#熱門商品
"""

    return copy.strip()


# =========================================================
# 圖片處理
# =========================================================

def process_image(uploaded_file):

    try:

        image = Image.open(
            uploaded_file
        )

        image = ImageOps.exif_transpose(
            image
        )

        image = image.convert("RGB")

        width, height = image.size

        if max(width, height) > MAX_IMAGE_SIZE:

            ratio = (
                MAX_IMAGE_SIZE
                / max(width, height)
            )

            new_size = (
                int(width * ratio),
                int(height * ratio)
            )

            image = image.resize(
                new_size,
                Image.LANCZOS
            )

        return image

    except Exception:

        return None


# =========================================================
# 首頁
# =========================================================

def home_page():

    st.markdown(
        '<div class="main-title">'
        '🛒 AI 蝦皮半自動化 2.5 PRO'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f'<div class="main-subtitle">'
        f'歡迎回來，{member_name}'
        f'</div>',
        unsafe_allow_html=True
    )

    st.divider()

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "會員狀態",
            "正常"
        )

    with col2:

        st.metric(
            "剩餘天數",
            f"{remaining_days} 天"
        )

    with col3:

        st.metric(
            "AI 模式",
            "本機規則"
        )

    with col4:

        st.metric(
            "外部 API",
            "未使用"
        )

    st.divider()

    st.subheader("🚀 系統功能")

    c1, c2 = st.columns(2)

    with c1:

        st.info(
            """
📦 **商品分析**

輸入商品名稱、分類、價格與賣點，
快速產生蝦皮商品分析。
"""
        )

        st.info(
            """
🖼️ **商品圖片**

上傳商品圖片，
進行圖片預覽與尺寸處理。
"""
        )

    with c2:

        st.info(
            """
🎬 **即夢 2.5 指令生成**

依照商品資訊，
建立 9:16 商品短影音指令。
"""
        )

        st.info(
            """
✍️ **蝦皮商品文案**

快速建立商品介紹、
賣點與標籤內容。
"""
        )


# =========================================================
# 商品分析頁
# =========================================================

def product_analysis_page():

    st.title("📦 商品分析")

    st.caption(
        "本頁使用本機規則進行分析。"
    )

    product_name = st.text_input(
        "商品名稱",
        placeholder="例如：高級保濕精華液"
    )

    category = st.selectbox(
        "商品分類",
        [
            "自動判斷",
            "保養品",
            "3C",
            "居家",
            "服飾",
            "食品",
            "汽機車",
            "其他"
        ]
    )

    price = st.number_input(
        "商品價格",
        min_value=0,
        value=999,
        step=10
    )

    selling_points = st.text_area(
        "商品賣點",
        placeholder="例如：天然配方、清爽不黏膩、高質感",
        height=120
    )

    if st.button(
        "🔎 開始商品分析",
        type="primary",
        use_container_width=True
    ):

        result = analyze_product(
            product_name,
            category,
            price,
            selling_points
        )

        st.session_state.analysis_result = result

    if st.session_state.analysis_result:

        st.divider()

        st.markdown(
            st.session_state.analysis_result
        )

        st.download_button(
            "⬇️ 下載商品分析",
            data=st.session_state.analysis_result,
            file_name="商品分析.txt",
            mime="text/plain",
            use_container_width=True
        )


# =========================================================
# 商品圖片頁
# =========================================================

def image_page():

    st.title("🖼️ 商品圖片")

    st.caption(
        "圖片在目前工作階段處理。"
    )

    uploaded_file = st.file_uploader(
        "上傳商品圖片",
        type=[
            "jpg",
            "jpeg",
            "png",
            "webp"
        ]
    )

    if uploaded_file:

        if uploaded_file.size > MAX_IMAGE_MB * 1024 * 1024:

            st.error(
                f"圖片太大，請使用 {MAX_IMAGE_MB}MB 以下圖片。"
            )

            return

        image = process_image(
            uploaded_file
        )

        if image is None:

            st.error(
                "圖片讀取失敗。"
            )

            return

        col1, col2 = st.columns(2)

        with col1:

            st.image(
                image,
                caption="商品圖片",
                use_container_width=True
            )

        with col2:

            st.subheader("📐 圖片資訊")

            st.write(
                f"尺寸：{image.width} × {image.height}"
            )

            st.success(
                "圖片已成功載入。"
            )

            buffer = io.BytesIO()

            image.save(
                buffer,
                format="JPEG",
                quality=95
            )

            st.download_button(
                "⬇️ 下載處理後圖片",
                data=buffer.getvalue(),
                file_name="product_processed.jpg",
                mime="image/jpeg",
                use_container_width=True
            )


# =========================================================
# 即夢 2.5 頁
# =========================================================

def seedance_page():

    st.title("🎬 即夢 2.5 指令生成")

    st.caption(
        "根據商品資料建立 9:16 商品短影音指令詞。"
    )

    product_name = st.text_input(
        "商品名稱",
        placeholder="例如：高質感保濕精華"
    )

    category = st.selectbox(
        "商品分類",
        [
            "自動判斷",
            "保養品",
            "3C",
            "居家",
            "服飾",
            "食品",
            "汽機車",
            "其他"
        ],
        key="seedance_category"
    )

    selling_points = st.text_area(
        "商品賣點",
        placeholder="例如：天然配方、清爽、高質感",
        height=120,
        key="seedance_points"
    )

    style = st.selectbox(
        "影片風格",
        [
            "高級商業廣告",
            "電商爆款",
            "極簡高級感",
            "科技感",
            "生活情境",
            "電影級產品展示"
        ]
    )

    duration = st.selectbox(
        "影片長度",
        [
            "5",
            "8",
            "10",
            "15"
        ]
    )

    if st.button(
        "🎬 生成即夢 2.5 指令",
        type="primary",
        use_container_width=True
    ):

        prompt = generate_seedance_prompt(
            product_name,
            category,
            selling_points,
            style,
            duration
        )

        st.session_state.generated_prompt = prompt

    if st.session_state.generated_prompt:

        st.divider()

        st.subheader("📋 即夢 2.5 指令")

        st.code(
            st.session_state.generated_prompt,
            language="text"
        )

        st.download_button(
            "⬇️ 下載指令",
            data=st.session_state.generated_prompt,
            file_name="即夢2.5商品影片指令.txt",
            mime="text/plain",
            use_container_width=True
        )


# =========================================================
# 蝦皮文案頁
# =========================================================

def copy_page():

    st.title("✍️ 蝦皮商品文案")

    product_name = st.text_input(
        "商品名稱",
        placeholder="例如：高級保濕精華"
    )

    category = st.selectbox(
        "商品分類",
        [
            "保養品",
            "3C",
            "居家",
            "服飾",
            "食品",
            "汽機車",
            "其他"
        ],
        key="copy_category"
    )

    price = st.number_input(
        "商品價格",
        min_value=0,
        value=999,
        step=10,
        key="copy_price"
    )

    selling_points = st.text_area(
        "商品賣點",
        placeholder="例如：天然配方、清爽不黏、高質感",
        height=120,
        key="copy_points"
    )

    if st.button(
        "✍️ 生成蝦皮商品文案",
        type="primary",
        use_container_width=True
    ):

        copy = generate_shopee_copy(
            product_name,
            category,
            selling_points,
            price
        )

        st.session_state.generated_copy = copy

    if st.session_state.generated_copy:

        st.divider()

        st.subheader("🛒 商品文案")

        st.text_area(
            "可直接複製",
            value=st.session_state.generated_copy,
            height=400
        )

        st.download_button(
            "⬇️ 下載商品文案",
            data=st.session_state.generated_copy,
            file_name="蝦皮商品文案.txt",
            mime="text/plain",
            use_container_width=True
        )


# =========================================================
# 會員資料頁
# =========================================================

def member_page():

    st.title("👤 我的會員資料")

    col1, col2 = st.columns(2)

    with col1:

        st.write(
            f"**姓名：** {member_name}"
        )

        st.write(
            f"**帳號：** {current_username}"
        )

        st.write(
            f"**Email：** {member_email or '未設定'}"
        )

    with col2:

        st.write(
            f"**身份：** {member_role}"
        )

        st.write(
            f"**狀態：** {member_status}"
        )

        st.write(
            f"**到期日：** {member_expires}"
        )

        st.write(
            f"**剩餘天數：** {remaining_days}"
        )


# =========================================================
# 管理員中心
# =========================================================

def admin_page():

    if member_role != "admin":

        st.error(
            "⛔ 你沒有管理員權限。"
        )

        return

    st.title("👑 管理員中心")

    members = load_members()

    st.write(
        f"目前會員數：**{len(members)}**"
    )

    st.divider()

    for member in members:

        username = member.get(
            "username",
            ""
        )

        name = member.get(
            "name",
            ""
        )

        role = member.get(
            "role",
            "member"
        )

        status = member.get(
            "status",
            "active"
        )

        expires = member.get(
            "expires",
            ""
        )

        with st.expander(
            f"👤 {name}｜{username}"
        ):

            st.write(
                f"身份：{role}"
            )

            st.write(
                f"狀態：{status}"
            )

            st.write(
                f"到期日：{expires}"
            )

            if role != "admin":

                c1, c2 = st.columns(2)

                with c1:

                    new_status = st.selectbox(
                        "會員狀態",
                        [
                            "active",
                            "disabled"
                        ],
                        index=(
                            0
                            if status == "active"
                            else 1
                        ),
                        key=f"status_{username}"
                    )

                with c2:

                    add_days = st.number_input(
                        "增加天數",
                        min_value=0,
                        value=30,
                        step=1,
                        key=f"days_{username}"
                    )

                if st.button(
                    "💾 更新會員",
                    key=f"update_{username}"
                ):

                    updates = {
                        "status": new_status
                    }

                    if add_days > 0:

                        try:

                            current_expire = date.fromisoformat(
                                expires
                            )

                        except Exception:

                            current_expire = date.today()

                        if current_expire < date.today():

                            current_expire = date.today()

                        new_expire = (
                            current_expire
                            + timedelta(days=int(add_days))
                        ).isoformat()

                        updates["expires"] = new_expire

                    update_member(
                        member.get("id"),
                        updates
                    )

                    st.success(
                        "會員資料已更新。"
                    )

                    st.rerun()


# =========================================================
# 側邊欄
# =========================================================

with st.sidebar:

    st.title("🛒 AI 蝦皮 2.5 PRO")

    st.divider()

    st.write(
        f"👤 **{member_name}**"
    )

    st.caption(
        f"帳號：{current_username}"
    )

    if member_role == "admin":

        st.success("👑 管理員")

    else:

        st.info("👤 一般會員")

    st.write(
        f"📅 到期日：{member_expires}"
    )

    st.write(
        f"⏳ 剩餘：{remaining_days} 天"
    )

    st.divider()

    menu_options = [
        "🏠 系統首頁",
        "📦 商品分析",
        "🖼️ 商品圖片",
        "🎬 即夢 2.5 指令生成",
        "✍️ 蝦皮商品文案",
        "👤 我的會員資料"
    ]

    if member_role == "admin":

        menu_options.append(
            "👑 管理員中心"
        )

    menu = st.radio(
        "功能選單",
        menu_options
    )

    st.divider()

    if st.button(
        "🚪 登出系統",
        use_container_width=True
    ):

        logout()


# =========================================================
# 主頁路由
# =========================================================

if menu == "🏠 系統首頁":

    home_page()

elif menu == "📦 商品分析":

    product_analysis_page()

elif menu == "🖼️ 商品圖片":

    image_page()

elif menu == "🎬 即夢 2.5 指令生成":

    seedance_page()

elif menu == "✍️ 蝦皮商品文案":

    copy_page()

elif menu == "👤 我的會員資料":

    member_page()

elif menu == "👑 管理員中心":

    admin_page()


# =========================================================
# 頁尾
# =========================================================

st.divider()

st.caption(
    "AI 蝦皮半自動化 2.5 PRO｜純本機規則模式｜無外部 API"
)
