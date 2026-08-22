from datetime import datetime
import streamlit as st
from PIL import Image
from google import genai

# -------------------- API 金鑰安全讀取 --------------------
GEMINI_KEY = st.secrets.get("GEMINI_KEY", "")

APP_NAME = "AI 蝦皮自動化"
APP_VERSION = "2.5 PRO"

st.set_page_config(
    page_title=f"{APP_NAME} {APP_VERSION}",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 自訂 CSS 樣式
st.markdown("""
<style>
.stApp{background:radial-gradient(circle at 20% 0%,rgba(255,90,0,.08),transparent 25%),#05080d;color:#f5f7fa}
#MainMenu,footer{visibility:hidden}
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#0a1018,#070b11);border-right:1px solid rgba(255,255,255,.08)}
.card{background:linear-gradient(145deg,#101923,#090f17);border:1px solid rgba(255,255,255,.08);border-radius:14px;padding:16px;margin-bottom:14px}
.title{font-size:24px;font-weight:800}.sub{color:#8995a4;font-size:12px}
.section{font-size:17px;font-weight:800;margin:10px 0}
.badge{display:inline-block;margin-left:8px;padding:3px 8px;border-radius:6px;font-size:11px;color:#ff9d52;border:1px solid #ff6a00;background:rgba(255,90,0,.1)}
.metric{background:linear-gradient(145deg,#111a25,#0b1119);border:1px solid rgba(255,255,255,.07);border-radius:13px;padding:13px;min-height:80px}
.metric-label{font-size:11px;color:#8995a4}.metric-value{font-size:21px;font-weight:800;margin-top:4px}.orange{color:#ff6a00}.green{color:#50d890}.blue{color:#4ab7ff}.purple{color:#b28cff}
.workflow{display:flex;gap:8px;align-items:center;background:#0b121b;border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:12px;margin-bottom:14px;overflow-x:auto}
.step{min-width:130px;flex:1;background:#101923;border:1px solid rgba(255,255,255,.08);border-radius:11px;padding:10px}.step-icon{font-size:22px}.step-title{font-size:13px;font-weight:800}.step-desc{font-size:10px;color:#7e8a99}.arrow{color:#ff6a00;font-size:20px;font-weight:bold}
.check{color:#49d98c}.tag{display:inline-block;padding:5px 9px;margin:3px;background:#172331;border:1px solid #293a4b;border-radius:7px;color:#b8c5d2;font-size:11px}
.stButton>button{border-radius:8px!important;background:#111a24!important;color:#fff!important;font-weight:700!important;border:1px solid rgba(255,255,255,.12)!important}
.stButton>button:hover{border-color:#ff6a00!important;color:#ff8b42!important}
.stTextInput input,.stNumberInput input,.stTextArea textarea,.stSelectbox div[data-baseweb="select"]>div{background:#0b121b!important;color:#fff!important;border-radius:8px!important}
</style>
""", unsafe_allow_html=True)

# -------------------- 初始化 Session State --------------------
def init_state():
    defaults = {
        "page": "商品上架工作台",
        "product_name": "",
        "category": "保養保健",
        "price": 499,
        "stock": 100,
        "selling_points": "",
        "condition": "全新",
        "images": [],
        "generated": False,
        "published": 0,
        "history": [],
        "ai_results": {},
        "api_key": GEMINI_KEY,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_state()

# -------------------- 核心邏輯與 Gemini API 調用 --------------------
def current_name():
    return st.session_state.product_name.strip() or "玻尿酸保濕精華液"

def call_gemini_ai():
    api_key = st.session_state.api_key or GEMINI_KEY
    if not api_key:
        st.warning("⚠️ 未檢測到 Gemini API Key，將使用預設內容。請至【🔑 API 設定】輸入金鑰。")
        return False

    try:
        client = genai.Client(api_key=api_key)
        contents = []

        if st.session_state.images:
            img = Image.open(st.session_state.images[0])
            contents.append(img)

        prompt = f"""
        請作為專業的電商爆款文案專家，分析並生成以下商品資訊：
        - 商品名稱：{current_name()}
        - 分類：{st.session_state.category}
        - 產品賣點描述：{st.session_state.selling_points}

        請務必依照下方格式回覆：
        [AI分析]：簡單描述商品外觀與核心價值（100字內）。
        [商品標題]：撰寫具備 SEO 高搜尋量的蝦皮標題。
        [商品描述]：詳細蝦皮文案，含特色、情境、使用方法。
        [關鍵字]：7-10 個熱門標籤，以逗號分隔。
        [TikTok文案]：15-25 秒短影音口播文案。
        [即夢Prompt]：英文撰寫 9:16 商業影片 Prompt。
        """
        contents.append(prompt)

        with st.spinner("🤖 Gemini 正在分析圖片與生成爆款文案..."):
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents
            )
            text = response.text

            results = {}
            current_tag = "analysis"
            for line in text.split("\n"):
                if "[AI分析]" in line: current_tag = "analysis"
                elif "[商品標題]" in line: current_tag = "title"
                elif "[商品描述]" in line: current_tag = "description"
                elif "[關鍵字]" in line: current_tag = "keywords"
                elif "[TikTok文案]" in line: current_tag = "tiktok"
                elif "[即夢Prompt]" in line: current_tag = "jimeng"
                else:
                    results[current_tag] = results.get(current_tag, "") + line + "\n"

            st.session_state.ai_results = results
            return True

    except Exception as e:
        st.error(f"❌ AI 調用失敗：{str(e)}")
        return False

def get_res(key, default_func):
    if st.session_state.ai_results.get(key):
        return st.session_state.ai_results[key].strip()
    return default_func()

def title_text():
    return f"{current_name()}｜深層保濕修護｜日常補水保養"

def description_text():
    return f"{current_name()}\n\n✨ 商品特色\n✓ 深層保濕補水\n✓ 修護日常保養\n✓ 溫和好使用\n✓ 清爽不黏膩"

def keywords_text():
    return "保濕,補水,修護,保養,美妝"

def tiktok_text():
    return f"🔥 {current_name()}\n乾燥缺水怎麼辦？使用簡單日常保養維持水嫩感！"

def jimeng_prompt():
    return f"9:16 vertical commercial video of {current_name()}, luxury cinematic style."

def save_history(action):
    st.session_state.history.insert(0, {
        "時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "商品": current_name(),
        "操作": action,
    })

# -------------------- 側邊欄與頁面 --------------------
def sidebar():
    with st.sidebar:
        st.markdown('<div class="card"><div style="font-size:19px;font-weight:800">🛍️ AI 蝦皮自動化</div></div>', unsafe_allow_html=True)
        menus = [
            ("🏠", "Dashboard"), ("🛍️", "商品上架工作台"), ("📦", "商品管理"),
            ("🧾", "訂單管理"), ("📊", "數據分析"), ("🖼️", "AI 素材庫"),
            ("🕘", "歷史紀錄"), ("🎵", "TikTok 短影音"), ("💰", "蝦皮分潤管理"),
        ]
        for icon, name in menus:
            if st.button(f"{icon}  {name}", key=f"nav_{name}", use_container_width=True):
                st.session_state.page = name
                st.rerun()
        st.markdown("---")
        for icon, name in [("⚙️", "系統設定"), ("🔑", "API 設定"), ("📚", "使用教學")]:
            if st.button(f"{icon}  {name}", key=f"sys_{name}", use_container_width=True):
                st.session_state.page = name
                st.rerun()

def workspace():
    left, middle, right = st.columns([1, 1.2, 1.2])
    with left:
        st.markdown('<div class="card"><b>① 商品資訊輸入</b>', unsafe_allow_html=True)
        name = st.text_input("商品名稱", value=st.session_state.product_name)
        category = st.selectbox("商品分類", ["保養保健", "美妝保養", "3C 電子", "居家生活", "其他"])
        price = st.number_input("商品價格", min_value=0, value=int(st.session_state.price))
        stock = st.number_input("商品庫存", min_value=0, value=int(st.session_state.stock))
        points = st.text_area("商品賣點", value=st.session_state.selling_points)
        files = st.file_uploader("上傳商品圖片", type=["jpg", "png", "webp"], accept_multiple_files=True)
        
        if files:
            st.session_state.images = files
            st.success(f"已選擇 {len(files)} 張圖片")

        if st.button("🚀 執行 AI 工作流", use_container_width=True):
            st.session_state.product_name = name
            st.session_state.category = category
            st.session_state.price = price
            st.session_state.stock = stock
            st.session_state.selling_points = points
            
            if call_gemini_ai():
                st.success("✨ 文案已成功生成！")
            save_history("執行 AI 工作流")
        st.markdown('</div>', unsafe_allow_html=True)

    with middle:
        st.markdown('<div class="card"><b>② AI 分析結果</b>', unsafe_allow_html=True)
        if st.session_state.images:
            try:
                st.image(Image.open(st.session_state.images[0]), use_container_width=True)
            except:
                pass
        st.write(get_res("analysis", lambda: "請點擊左側【執行 AI 工作流】進行分析。"))
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="card"><b>③ AI 內容生成</b>', unsafe_allow_html=True)
        tabs = st.tabs(["標題", "描述", "關鍵字", "TikTok", "即夢 Prompt"])
        with tabs[0]: st.text_area("標題", get_res("title", title_text), height=100)
        with tabs[1]: st.text_area("描述", get_res("description", description_text), height=180)
        with tabs[2]: st.text_area("關鍵字", get_res("keywords", keywords_text), height=80)
        with tabs[3]: st.text_area("TikTok", get_res("tiktok", tiktok_text), height=120)
        with tabs[4]: st.text_area("Prompt", get_res("jimeng", jimeng_prompt), height=120)
        st.markdown('</div>', unsafe_allow_html=True)

# -------------------- 應用程式執行進入點 --------------------
sidebar()
st.markdown(f'<div class="card"><div class="title">🛍️ AI 蝦皮自動化 <span class="badge">2.5 PRO</span></div></div>', unsafe_allow_html=True)

if st.session_state.page == "商品上架工作台":
    workspace()
elif st.session_state.page == "API 設定":
    st.info("請於下方輸入您的 Gemini API Key：")
    key_input = st.text_input("Gemini API Key", value=st.session_state.api_key, type="password")
    if st.button("儲存 API Key"):
        st.session_state.api_key = key_input
        st.success("API Key 已成功儲存！")
else:
    st.markdown(f'<div class="card"><h3>{st.session_state.page} 功能模組展示中</h3></div>', unsafe_allow_html=True)fe_allow_html=True)
        a,b,c,d,e = st.tabs(["標題","描述","關鍵字","TikTok","即夢 Prompt"])
        with a: st.text_area("商品標題", title_text(), height=110, key="out_title")
        with b: st.text_area("商品描述", description_text(), height=220, key="out_desc")
        with c: st.text_area("關鍵字", "保濕,補水,修護,保養,美容,肌膚,日常保養", height=100, key="out_kw")
        with d: st.text_area("TikTok 文案", f"🔥 {product_name()}\n\n乾燥肌日常保養怎麼做？\n簡單介紹商品特色與使用情境。\n\n立即了解商品資訊！", height=170, key="out_tt")
        with e: st.text_area("即夢 AI 2.5 Prompt", jimeng_prompt(), height=270, key="out_jm")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("###")
    c1,c2,c3 = st.columns([1,1.25,1])
    with c1:
        st.markdown("<div class='card'><div class='ct'>④ 蝦皮上架設定</div>", unsafe_allow_html=True)
        st.selectbox("物流", ["蝦皮店到店","7-11 店到店","全家店到店","賣家宅配"])
        st.selectbox("出貨地", ["新北市","台北市","桃園市","其他"])
        st.text_input("商品規格", "30ml")
        st.number_input("上架庫存", min_value=0, value=int(st.session_state.stock))
        st.selectbox("出貨天數", ["1 天內","2 天內","3 天內","7 天內"])
        st.toggle("自動回覆買家問題", value=True)
        st.button("💾 儲存上架設定", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='card'><div class='ct'>⑤ 蝦皮商品預覽</div>", unsafe_allow_html=True)
        if st.session_state.images:
            try: st.image(Image.open(st.session_state.images[0]), use_container_width=True)
            except Exception: pass
        else: st.info("尚未上傳商品圖片")
        st.markdown(f"<div style='background:white;color:#222;border-radius:8px;padding:12px'><b>{product_name()}</b><div style='color:#ee4d2d;font-size:25px;font-weight:800'>NT$ {st.session_state.price}</div><span style='font-size:10px;color:#777'>⭐⭐⭐⭐⭐　已售 268</span></div>", unsafe_allow_html=True)
        if st.button("🚀 一鍵上架蝦皮（目前為模擬）", use_container_width=True):
            st.session_state.published += 1
            save_history("一鍵上架模擬", product_name())
            st.success("上架資料已完成驗證；目前尚未連接蝦皮官方 API，因此不會真的發布商品。")
        st.markdown("</div>", unsafe_allow_html=True)
    with c3:
        st.markdown("<div class='card'><div class='ct'>📡 系統狀態</div><div style='text-align:center;font-size:40px'>🚀</div><div style='text-align:center;font-weight:800'>系統運行正常</div><div class='check' style='text-align:center'>● 本機 AI 工作流在線</div><hr><div class='small'>版本：2.5 PRO</div><div class='small'>AI：規則生成模式</div><div class='small'>已模擬上架：%d 次</div></div>" % st.session_state.published, unsafe_allow_html=True)
    st.markdown("### ⚡ 快速功能")
    q = [("🧠","AI 圖片分析"),("📄","批量生成"),("🎵","TikTok 短影音"),("🎬","即夢 Prompt"),("📁","素材庫"),("🕘","歷史紀錄"),("📊","數據分析")]
    cols=st.columns(7)
    for col,(icon,title) in zip(cols,q):
        with col: st.markdown(f"<div class='quick'><div class='qicon'>{icon}</div><div class='qtitle'>{title}</div></div>", unsafe_allow_html=True)


def dashboard():
    metrics()
    workflow()
    a,b=st.columns([2,1])
    with a:
        st.markdown("<div class='card'><div class='ct'>📈 電商工作概況</div>", unsafe_allow_html=True)
        st.bar_chart({"上架商品":[8,12,10,15,12,18,20],"AI 工作量":[10,16,14,22,20,28,30]})
        st.markdown("</div>", unsafe_allow_html=True)
    with b:
        st.markdown("<div class='card'><div class='ct'>🤖 AI 使用統計</div><div style='font-size:38px;font-weight:800;color:#ff6a00;text-align:center'>24.96%</div><div class='small' style='text-align:center'>本月使用量</div><hr><div class='small'>文案生成　658 次</div><div class='small'>圖片分析　412 次</div><div class='small'>Prompt　178 次</div></div>", unsafe_allow_html=True)


def generic_page(page):
    info={
        "商品管理":("📦","管理商品資料、價格、庫存與狀態"),"訂單管理":("🧾","查看訂單與出貨資料"),"數據分析":("📊","查看銷售與工作流數據"),
        "AI 素材庫":("🖼️","管理圖片、文案、Prompt 與影片素材"),"歷史紀錄":("🕘","查看本機 AI 工作紀錄"),"TikTok 短影音":("🎵","建立 9:16 短影音腳本與 Prompt"),
        "蝦皮分潤管理":("💰","管理分潤資料"),"會員管理":("👤","會員管理介面"),"管理員中心":("🛡️","管理員控制中心"),"系統設定":("⚙️","系統功能設定"),"API 設定":("🔑","未來接入 API 的設定區"),"使用教學":("📚","系統使用說明")}
    icon,desc=info.get(page,("⚙️","系統功能"))
    st.markdown(f"<div class='card'><div style='font-size:28px'>{icon}</div><div style='font-size:22px;font-weight:800'>{page}</div><div class='small'>{desc}</div></div>",unsafe_allow_html=True)
    if page=="商品管理":
        st.dataframe({"商品":["玻尿酸保濕精華液","修護面膜","保濕乳液"],"價格":[499,299,399],"庫存":[100,250,88],"狀態":["上架中","上架中","草稿"]},use_container_width=True,hide_index=True)
    elif page=="訂單管理": st.info("訂單模組目前為介面版，尚未連接蝦皮官方訂單 API。")
    elif page=="數據分析":
        c=st.columns(3); c[0].metric("今日銷售額","NT$28,560","+25%"); c[1].metric("今日訂單","58","+15%"); c[2].metric("瀏覽人次","5,689","+22%"); st.line_chart([18000,21000,19500,26000,24500,28000,28560])
    elif page=="AI 素材庫": st.info("目前可由商品工作台產生並管理素材；雲端儲存可在下一階段加入。")
    elif page=="歷史紀錄":
        try: st.dataframe(json.loads(HISTORY_FILE.read_text(encoding="utf-8")),use_container_width=True,hide_index=True)
        except Exception: st.info("目前沒有歷史紀錄。")
    elif page=="TikTok 短影音": st.text_area("9:16 腳本", "3 秒吸睛開場\n商品特色\n使用情境\nCTA", height=180); st.text_area("即夢 Prompt", jimeng_prompt(), height=220)
    elif page=="蝦皮分潤管理": st.metric("本月分潤","NT$12,580","+18%")
    elif page=="會員管理": st.info("會員管理介面已建立。後續可加入登入、永久會員、期限與權限資料庫。")
    elif page=="管理員中心": st.warning("管理員中心目前是介面版，正式權限驗證可在下一階段加入。")
    elif page=="系統設定": st.toggle("啟用 AI 自動分析",True); st.toggle("自動保存歷史紀錄",True); st.toggle("深色科技介面",True)
    elif page=="API 設定":
        st.info("這個版本不需要 API 就能啟動。API 欄位先保留，避免因缺少金鑰造成部署失敗。")
        st.text_input("Gemini API Key",type="password"); st.text_input("Shopee API Key",type="password")
    elif page=="使用教學": st.markdown("1. 輸入商品資料 → 2. 上傳圖片 → 3. 執行 AI 工作流 → 4. 檢查標題、描述與 Prompt → 5. 確認上架資料。\n\n**注意：目前一鍵上架是模擬功能，不會真的操作蝦皮。**")


sidebar()
header()

if st.session_state.page == "Dashboard":
    dashboard()
elif st.session_state.page == "商品上架工作台":
    metrics(); workspace()
else:
    generic_page(st.session_state.page)

st.markdown("<div style='text-align:center;color:#52606e;font-size:10px;padding:25px 0'>AI 蝦皮自動化 2.5 PRO ・ Streamlit Cloud Ready</div>",unsafe_allow_html=True)
