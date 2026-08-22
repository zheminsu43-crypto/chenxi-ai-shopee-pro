import io
import json
from datetime import datetime
from pathlib import Path

import streamlit as st
from PIL import Image

APP_NAME = "AI 蝦皮自動化"
APP_VERSION = "2.5 PRO"
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "history.json"

st.set_page_config(
    page_title=f"{APP_NAME} {APP_VERSION}",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;600;700;800&display=swap');
html,body,[class*="css"]{font-family:'Noto Sans TC',sans-serif}
.stApp{background:radial-gradient(circle at 15% 0%,rgba(255,90,0,.09),transparent 28%),#05080d;color:#f5f7fa}
#MainMenu,footer{visibility:hidden}
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#0a1018,#070b11);border-right:1px solid rgba(255,255,255,.08)}
.top{background:linear-gradient(135deg,#111923,#080e15);border:1px solid rgba(255,255,255,.08);border-radius:14px;padding:16px 20px;margin-bottom:14px}
.title{font-size:24px;font-weight:800}.sub{color:#84909e;font-size:12px}.badge{display:inline-block;color:#ff944d;border:1px solid #ff6a00;border-radius:6px;padding:3px 8px;font-size:11px;margin-left:8px}
.card{background:linear-gradient(145deg,#0f1721,#090f17);border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:16px;margin-bottom:14px}
.ct{font-weight:800;font-size:15px;margin-bottom:12px}.metric{background:linear-gradient(145deg,#111a25,#0b1119);border:1px solid rgba(255,255,255,.07);border-radius:13px;padding:13px}.mv{font-size:20px;font-weight:800}.ml{font-size:11px;color:#8995a4}.orange{color:#ff6a00}.green{color:#50d890}.blue{color:#4ab7ff}.purple{color:#b28cff}
.flow{display:flex;gap:8px;align-items:center;overflow-x:auto}.flowbox{min-width:135px;flex:1;background:#0b121b;border:1px solid rgba(255,255,255,.08);border-radius:11px;padding:10px}.fi{font-size:21px}.ft{font-size:12px;font-weight:800}.fd{font-size:10px;color:#7e8a99}.arrow{color:#ff6a00;font-size:20px}
.stButton>button{border-radius:8px!important;background:#111a24!important;color:#fff!important;border:1px solid rgba(255,255,255,.12)!important;font-weight:700!important}.stButton>button:hover{border-color:#ff6a00!important;color:#ff8b42!important}
.stTextInput input,.stNumberInput input,.stTextArea textarea,.stSelectbox div[data-baseweb="select"]>div{background:#0b121b!important;color:#fff!important;border-color:rgba(255,255,255,.1)!important}
.quick{text-align:center;background:#0c141e;border:1px solid rgba(255,255,255,.07);border-radius:11px;padding:12px;min-height:70px}.qicon{font-size:22px}.qtitle{font-size:10px;font-weight:700;margin-top:3px}
.check{color:#49d98c}.small{font-size:11px;color:#8793a0}
</style>
""", unsafe_allow_html=True)


def init_state():
    defaults = {
        "page": "商品上架工作台",
        "product_name": "",
        "category": "美妝保養",
        "price": 499,
        "stock": 100,
        "condition": "全新",
        "selling_points": "",
        "images": [],
        "published": 0,
        "generated": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()


def save_history(action, product):
    records = []
    try:
        if HISTORY_FILE.exists():
            records = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        records = []
    records.insert(0, {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "action": action, "product": product})
    HISTORY_FILE.write_text(json.dumps(records[:100], ensure_ascii=False, indent=2), encoding="utf-8")


def product_name():
    return st.session_state.product_name.strip() or "玻尿酸保濕精華液"


def title_text():
    return f"{product_name()}｜深層保濕修護｜日常補水保養"


def description_text():
    return f"""{product_name()}\n\n✨ 商品特色\n✓ 深層保濕補水\n✓ 日常修護保養\n✓ 溫和使用\n✓ 清爽好吸收\n\n適合日常保養與送禮使用。\n實際商品規格、成分與使用方式請以商品包裝及賣場資訊為準。"""


def jimeng_prompt():
    return f"""9:16 vertical premium commercial product video.\n\nMain subject: {product_name()}\n\nUse the uploaded product image as the ONLY visual source for the product. Preserve the original product shape, packaging, logo, label, colors, materials and visible text.\n\nCamera: slow cinematic push-in, subtle orbit, premium commercial lighting, clean luxury background, realistic product photography.\n\nDo not redesign the product. Do not invent logos. Do not change packaging. Do not add fake text. Do not alter brand identity."""


def sidebar():
    with st.sidebar:
        st.markdown("""<div style='padding:10px 5px 18px;border-bottom:1px solid rgba(255,255,255,.08)'><span style='font-size:27px'>🛍️</span> <b style='font-size:18px'>AI 蝦皮自動化</b><div class='small'>AI 智能生成・一鍵上架</div></div>""", unsafe_allow_html=True)
        st.markdown("### 主選單")
        menus = [
            ("🏠", "Dashboard"), ("🛍️", "商品上架工作台"), ("📦", "商品管理"),
            ("🧾", "訂單管理"), ("📊", "數據分析"), ("🖼️", "AI 素材庫"),
            ("🕘", "歷史紀錄"), ("🎵", "TikTok 短影音"), ("💰", "蝦皮分潤管理")]
        for icon, name in menus:
            if st.button(f"{icon}  {name}", key=f"nav_{name}", use_container_width=True):
                st.session_state.page = name
                st.rerun()
        st.markdown("---")
        st.markdown("### 系統管理")
        for icon, name in [("👤","會員管理"),("🛡️","管理員中心"),("⚙️","系統設定"),("🔑","API 設定"),("📚","使用教學")]:
            if st.button(f"{icon}  {name}", key=f"sys_{name}", use_container_width=True):
                st.session_state.page = name
                st.rerun()
        st.markdown("---")
        st.markdown("<div class='card'><b class='orange'>👑 PRO 會員</b><div class='check'>✓ 無限 AI 工作流程</div><div class='check'>✓ 商品內容生成</div><div class='check'>✓ TikTok / 即夢 Prompt</div><div class='check'>✓ 歷史紀錄</div></div>", unsafe_allow_html=True)


def header():
    st.markdown(f"<div class='top'><div class='title'>🛍️ {APP_NAME}<span class='badge'>{APP_VERSION}</span></div><div class='sub'>AI 智能生成・商品內容工作流・一鍵上架準備</div></div>", unsafe_allow_html=True)


def metrics():
    cols = st.columns(4)
    values = [("今日 AI 工作", "86 次", "orange"), ("已處理商品", "128", "green"), ("會員等級", "PRO", "purple"), ("會員期限", "永久", "blue")]
    for c, (label, value, color) in zip(cols, values):
        with c:
            st.markdown(f"<div class='metric'><div class='ml'>{label}</div><div class='mv {color}'>{value}</div></div>", unsafe_allow_html=True)


def workflow():
    items = [("📝","商品輸入","資料與圖片"),("🧠","AI 分析","商品理解"),("✨","內容生成","標題文案"),("⚙️","上架設定","價格庫存"),("🚀","發布準備","一鍵上架")]
    html = "<div class='card'><div class='ct'>🚀 AI 自動化流程</div><div class='flow'>"
    for i, (icon, title, desc) in enumerate(items):
        html += f"<div class='flowbox'><div class='fi'>{icon}</div><div class='ft'>{title}</div><div class='fd'>{desc}</div></div>"
        if i < len(items)-1: html += "<div class='arrow'>→</div>"
    html += "</div></div>"
    st.markdown(html, unsafe_allow_html=True)


def workspace():
    workflow()
    left, mid, right = st.columns([1.05, 1.25, 1.2])
    with left:
        st.markdown("<div class='card'><div class='ct'>① 商品資料輸入</div>", unsafe_allow_html=True)
        name = st.text_input("商品名稱", value=st.session_state.product_name, placeholder="例如：玻尿酸保濕精華液 30ml")
        category = st.selectbox("商品分類", ["美妝保養","保養保健","3C 電子","居家生活","服飾鞋包","食品飲料","汽機車","其他"], index=0)
        price = st.number_input("商品價格", min_value=0, value=int(st.session_state.price), step=10)
        stock = st.number_input("庫存", min_value=0, value=int(st.session_state.stock), step=1)
        condition = st.radio("商品狀態", ["全新","二手"], horizontal=True)
        points = st.text_area("商品賣點", value=st.session_state.selling_points, placeholder="例如：深層保濕、溫和不刺激", height=90)
        files = st.file_uploader("商品圖片（可多張）", type=["jpg","jpeg","png","webp"], accept_multiple_files=True)
        if files:
            st.session_state.images = files
        if st.session_state.images:
            st.success(f"已加入 {len(st.session_state.images)} 張圖片")
        if st.button("🧠 儲存並執行 AI 工作流程", use_container_width=True):
            st.session_state.product_name = name
            st.session_state.category = category
            st.session_state.price = price
            st.session_state.stock = stock
            st.session_state.condition = condition
            st.session_state.selling_points = points
            st.session_state.generated = True
            save_history("AI 內容生成", product_name())
            st.success("完成！目前為本機規則生成模式，不需要 Gemini API。")
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with mid:
        st.markdown("<div class='card'><div class='ct'>② AI 分析結果</div>", unsafe_allow_html=True)
        t1,t2,t3,t4 = st.tabs(["商品分析","標題建議","關鍵字","賣點"])
        with t1:
            c1,c2 = st.columns([1,1.3])
            with c1:
                if st.session_state.images:
                    try: st.image(Image.open(st.session_state.images[0]), use_container_width=True)
                    except Exception: st.info("圖片格式無法預覽")
                else: st.info("尚未上傳商品圖片")
            with c2:
                st.write(f"目前分析商品：**{product_name()}**")
                st.write(f"分類：**{st.session_state.category}**")
                st.write(f"價格：**NT$ {st.session_state.price}**")
                st.markdown("**主要賣點**")
                for x in ["深層保濕補水","日常修護","溫和使用","清爽好吸收","適合電商展示"]:
                    st.markdown(f"<div class='check'>✓ {x}</div>", unsafe_allow_html=True)
        with t2:
            for i, text in enumerate([title_text(),f"{product_name()}｜保濕補水｜溫和修護",f"高效保濕 {product_name()}｜日常保養"]):
                st.checkbox(text, value=True, key=f"suggest_{i}")
        with t3:
            st.write("保濕、補水、修護、保養、精華液、美容、肌膚、日常保養")
        with t4:
            st.write("深層保濕補水、日常修護、溫和使用、清爽好吸收。")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown("<div class='card'><div class='ct'>③ AI 內容生成</div>", unsafe_allow_html=True)
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
