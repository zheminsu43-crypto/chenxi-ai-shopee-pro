import io
import os
import re
import json
import hashlib
import secrets
import shutil
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime, date, timedelta

import streamlit as st
from PIL import Image, ImageOps

# =========================================================
# AI 蝦皮全自動化 2.5 PRO - 完整修復版
# =========================================================
APP_NAME = "AI 蝦皮全自動化 2.5 PRO"
APP_VERSION = "2.5.2"

DATA_DIR = Path("data")
HISTORY_DIR = Path("history")
MEDIA_DIR = DATA_DIR / "media"
MEMBERS_FILE = DATA_DIR / "members.json"

for folder in (DATA_DIR, HISTORY_DIR, MEDIA_DIR):
    folder.mkdir(parents=True, exist_ok=True)

MAX_IMAGE_SIZE = 1600
MAX_IMAGE_MB = 20
MAX_VIDEO_MB = 300

ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = os.environ.get("DEFAULT_ADMIN_PASSWORD", "admin123456")
GEMINI_MODEL = "gemini-2.5-flash"

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
.main-title{font-size:36px;font-weight:800}
.sub-title{color:#777;margin-bottom:20px}
.member-card{padding:14px;border-radius:14px;border:1px solid rgba(128,128,128,.25);margin:10px 0}
.small{color:#777;font-size:14px}
.result-box{padding:18px;border-radius:16px;border:1px solid rgba(128,128,128,.25)}
</style>
""",
    unsafe_allow_html=True,
)

# =========================================================
# Session State
# =========================================================
DEFAULT_STATE = {
    "logged_in": False,
    "username": "",
    "name": "",
    "role": "",
    "member": {},
    "page": "home",
    "result": "",
    "last_product": {},
    "last_image_bytes": None,
    "last_image_mime": "image/jpeg",
    "last_video_bytes": None,
    "last_video_name": "",
    "last_video_mime": "video/mp4",
    "gemini_model": GEMINI_MODEL,
    "gemini_error": "",
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# Secrets / API
# =========================================================
def get_secret(name, default=""):
    try:
        value = st.secrets.get(name, default)
        if value:
            return str(value)
    except Exception:
        pass
    return os.environ.get(name, default)


GEMINI_KEY = get_secret("GEMINI_KEY") or get_secret("GEMINI_API_KEY")
PEXELS_KEY = get_secret("PEXELS_KEY")


# =========================================================
# 基礎工具
# =========================================================
def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def hash_password(password):
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest()


def safe_filename(name):
    name = re.sub(r'[\\/:*?"<>|]+', "_", str(name or "file"))
    name = re.sub(r"\s+", " ", name).strip()
    return name[:100] or "file"


def load_json(path, default):
    try:
        path = Path(path)
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception:
        return default


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    temp.replace(path)


# =========================================================
# 會員系統
# =========================================================
def load_members():
    members = load_json(MEMBERS_FILE, {})
    return members if isinstance(members, dict) else {}


def save_members(members):
    save_json(MEMBERS_FILE, members)


def ensure_admin():
    members = load_members()
    changed = False
    admin = members.get(ADMIN_USERNAME)

    if not isinstance(admin, dict):
        members[ADMIN_USERNAME] = {
            "username": ADMIN_USERNAME,
            "name": "系統管理員",
            "email": "",
            "password_hash": hash_password(DEFAULT_ADMIN_PASSWORD),
            "created_at": now_text(),
            "expire_date": None,
            "permanent": True,
            "role": "admin",
            "status": "active",
        }
        changed = True
    else:
        defaults = {
            "username": ADMIN_USERNAME,
            "name": "系統管理員",
            "email": "",
            "created_at": now_text(),
            "expire_date": None,
            "permanent": True,
            "role": "admin",
            "status": "active",
        }
        for key, value in defaults.items():
            if key not in admin:
                admin[key] = value
                changed = True
        if admin.get("role") != "admin":
            admin["role"] = "admin"
            changed = True

    if changed:
        save_members(members)


def member_expiration(member):
    if member.get("permanent", True):
        return "永久會員", True

    expire = member.get("expire_date")
    if not expire:
        return "未設定", False

    try:
        expire_date = date.fromisoformat(expire)
    except Exception:
        return "日期錯誤", False

    days = (expire_date - date.today()).days
    if days < 0:
        return f"已到期（{abs(days)} 天）", False

    return f"剩餘 {days} 天", True


def create_member(
    username,
    password,
    name="",
    email="",
    role="member",
    permanent=True,
    days=30,
):
    username = str(username or "").strip()
    password = str(password or "")
    name = str(name or "").strip()
    email = str(email or "").strip()

    if not username or not password:
        return False, "帳號與密碼不能為空。"
    if len(username) < 3:
        return False, "帳號至少 3 個字元。"
    if len(password) < 6:
        return False, "密碼至少 6 個字元。"
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
        return False, "帳號只能使用英數、底線、點或連字號。"

    members = load_members()
    if username in members:
        return False, "帳號已存在。"

    expire_date = None
    if not permanent:
        expire_date = (date.today() + timedelta(days=int(days))).isoformat()

    members[username] = {
        "username": username,
        "name": name or username,
        "email": email,
        "password_hash": hash_password(password),
        "created_at": now_text(),
        "expire_date": expire_date,
        "permanent": bool(permanent),
        "role": role if role in {"member", "vip", "admin"} else "member",
        "status": "active",
    }

    save_members(members)
    return True, "會員建立成功。"


def authenticate(username, password):
    username = str(username or "").strip()
    members = load_members()
    member = members.get(username)

    if not member:
        return None, "帳號不存在。"
    if member.get("status", "active") != "active":
        return None, "此帳號目前已停用。"

    password_hash = hash_password(password)
    if not secrets.compare_digest(
        str(member.get("password_hash", "")),
        password_hash,
    ):
        return None, "密碼錯誤。"

    status, valid = member_expiration(member)
    if not valid:
        return None, f"會員無法使用：{status}"

    return member, ""


def login_user(username, password):
    member, message = authenticate(username, password)
    if not member:
        return False, message

    st.session_state.logged_in = True
    st.session_state.username = member.get("username", "")
    st.session_state.name = member.get("name", member.get("username", ""))
    st.session_state.role = member.get("role", "member")
    st.session_state.member = member
    st.session_state.page = "home"
    return True, "登入成功。"


def logout_user():
    for key, value in DEFAULT_STATE.items():
        st.session_state[key] = value


# =========================================================
# 圖片處理
# =========================================================
def prepare_image(uploaded_file):
    if not uploaded_file:
        raise ValueError("沒有收到圖片。")

    raw = uploaded_file.getvalue()
    if len(raw) > MAX_IMAGE_MB * 1024 * 1024:
        raise ValueError(f"圖片超過 {MAX_IMAGE_MB}MB。")

    try:
        image = Image.open(io.BytesIO(raw))
        image = ImageOps.exif_transpose(image)

        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")

        image.thumbnail(
            (MAX_IMAGE_SIZE, MAX_IMAGE_SIZE),
            Image.Resampling.LANCZOS,
        )

        output = io.BytesIO()

        if image.mode == "RGBA":
            image.save(output, format="PNG", optimize=True)
            mime = "image/png"
        else:
            image.save(output, format="JPEG", quality=92, optimize=True)
            mime = "image/jpeg"

        return output.getvalue(), mime
    except Exception as exc:
        raise ValueError(f"圖片處理失敗：{exc}") from exc


# =========================================================
# Gemini API
# =========================================================
def get_gemini_client():
    if not GEMINI_KEY:
        raise RuntimeError(
            "尚未設定 GEMINI_KEY。請在 Streamlit Secrets 或環境變數中設定。"
        )

    try:
        from google import genai
        return genai.Client(api_key=GEMINI_KEY)
    except ImportError as exc:
        raise RuntimeError(
            "缺少 google-genai，請在 requirements.txt 加入 google-genai。"
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"Gemini 初始化失敗：{exc}") from exc


def ask_gemini(prompt, image_bytes=None, mime_type="image/jpeg"):
    client = get_gemini_client()

    try:
        from google.genai import types

        contents = []

        if image_bytes:
            contents.append(
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type,
                )
            )

        contents.append(prompt)

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
        )

        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("Gemini 沒有返回文字內容。")

        st.session_state.gemini_model = GEMINI_MODEL
        st.session_state.gemini_error = ""
        return text.strip()

    except Exception as exc:
        raw = str(exc)

        if "404" in raw:
            msg = "Gemini 模型不存在或 API 暫不支援（404）。"
        elif "401" in raw:
            msg = "Gemini API Key 無效（401）。"
        elif "403" in raw:
            msg = "Gemini API 權限不足（403）。"
        elif "429" in raw:
            msg = "Gemini API 呼叫頻率過高（429）。"
        elif "400" in raw:
            msg = "Gemini 請求格式錯誤（400）。"
        else:
            msg = f"Gemini 執行失敗：{raw}"

        st.session_state.gemini_error = msg
        raise RuntimeError(msg) from exc


# =========================================================
# Prompt 樣板
# =========================================================
SHOPEE_PROMPT_TEMPLATE = """
請輸出：
1. SEO 商品標題
2. 商品賣點 5 點
3. 完整商品描述
4. 關鍵字
5. 長尾關鍵字
6. FAQ 5 題
不得虛構品牌、規格、認證、效果、折扣或贈品。
"""

TIKTOK_PROMPT_TEMPLATE = """
請輸出：
1. 爆款標題
2. 0~3 秒 Hook
3. 15 秒口播
4. 25 秒口播
5. 貼文文案
6. Hashtags
要求前 3 秒抓住注意力，但不得使用無法證實的誇大承諾。
"""

JIMENG_25_RULES = """
上傳商品圖是商品外觀的唯一主要依據。
必須維持品牌、Logo、包裝、文字、顏色、材質、形狀、比例與細節一致。
不得重新設計包裝、改 Logo、改字、改顏色、增加不存在配件。
可改變的是場景、背景、燈光、鏡頭、景深與商業攝影氛圍。
影片預設 9:16 直式。
"""


def build_master_prompt(product):
    p = {key: str(value or "").strip() for key, value in product.items()}

    return f"""
你是「{APP_NAME}」的核心電商 AI。
請使用繁體中文。
只能根據商品圖片與使用者提供的資料回答；不確定的資訊一律寫「待確認」。

==============================
【商品資料】
==============================
商品名稱：{p.get('name')}
商品分類：{p.get('category')}
售價：{p.get('price')}
成本：{p.get('cost')}
分潤比例：{p.get('commission')}
預估月銷量：{p.get('sales')}
商品評分：{p.get('rating')}
商品連結：{p.get('url')}
商品規格：{p.get('specs')}
目標平台：{p.get('platform')}

==============================
【資料真實性規則】
==============================
1. 不得虛構品牌、Logo、規格、認證、成分、功能、價格、折扣、贈品或效果。
2. 圖片看不清楚的文字請寫「待確認」。
3. 使用者沒有提供的數據，不得自行補數字。
4. 不得把 AI 推測寫成確定事實。
5. 行銷文案可以有吸引力，但不能做無法證實的誇大承諾。

==============================
【任務一：商品辨識與 AI 選品分析】
==============================
請分析：
- 商品名稱與分類
- 圖片可確認資訊
- 待確認資訊
- 外觀、包裝、Logo、文字
- 主要賣點
- 目標客群
- 消費需求
- 市場定位
- 優勢
- 劣勢
- 短影音切入點
- 購買誘因
- 合規提醒
- 選品分數 0~100
- 市場吸引力 0~100
- 視覺吸引力 0~100
- TikTok 潛力 0~100
- 蝦皮潛力 0~100

==============================
【任務二：蝦皮高轉化上架文案】
==============================
{SHOPEE_PROMPT_TEMPLATE}

==============================
【任務三：TikTok 爆款帶貨文案】
==============================
{TIKTOK_PROMPT_TEMPLATE}

==============================
【任務四：即夢 AI 2.5 商業生圖 Prompt】
==============================
{JIMENG_25_RULES}
請輸出：
- 【即夢 AI 2.5 生圖英文 Prompt】
- 【Negative Prompt】
- 【畫面繁體中文文字設計】
- 【9:16 構圖與光影建議】

==============================
【任務五：即夢 AI 2.5 商業影片 Prompt】
==============================
請輸出英文影片 Prompt，必須包含：
Opening、Middle、Camera Motion、Lighting、Product Detail、Ending Freeze。
另外輸出 Negative Prompt。

==============================
【任務六：即夢 AI 2.5 25 秒帶貨分鏡】
==============================
0~3 秒：黃金 Hook
3~8 秒：商品全貌與品質展示
8~15 秒：核心賣點與細節特寫
15~20 秒：使用情境與價值呈現
20~25 秒：CTA 與結尾定格

==============================
【任務七：最終檢查】
==============================
檢查是否有虛構資料、誇大宣稱、錯誤品牌、錯誤規格，
以及是否維持原商品圖片的一致性。

請輸出完整、可直接複製使用的 Markdown 報告。
"""


def detect_category(text):
    text = (text or "").lower()
    groups = {
        "保養美妝": ["洗面", "面膜", "乳液", "精華", "保養", "化妝", "美容", "防曬", "洗髮"],
        "3C": ["手機", "耳機", "充電", "電腦", "鍵盤", "滑鼠", "3c", "平板", "螢幕"],
        "居家生活": ["收納", "清潔", "家居", "廚房", "杯", "居家", "拖把", "用品"],
        "服飾": ["衣服", "褲", "鞋", "帽", "包", "服飾", "外套"],
        "食品": ["食品", "零食", "餅乾", "飲料", "茶", "咖啡", "水果"],
        "汽機車": ["汽車", "機車", "車用", "汽機車", "輪胎"],
    }

    for category, keywords in groups.items():
        if any(keyword in text for keyword in keywords):
            return category

    return "其他"


# =========================================================
# 歷史紀錄
# =========================================================
def save_history(product, result):
    history_id = (
        datetime.now().strftime("%Y%m%d_%H%M%S")
        + "_"
        + secrets.token_hex(3)
    )

    folder = HISTORY_DIR / history_id
    folder.mkdir(parents=True, exist_ok=True)

    product_copy = dict(product)
    product_copy.pop("image_bytes", None)

    save_json(folder / "product.json", product_copy)
    (folder / "result.md").write_text(result, encoding="utf-8")

    return history_id


def list_history(limit=30):
    items = []

    for folder in sorted(HISTORY_DIR.glob("*"), reverse=True):
        if not folder.is_dir():
            continue

        product = load_json(folder / "product.json", {})
        result_file = folder / "result.md"

        items.append(
            {
                "id": folder.name,
                "product": product.get("name", "未命名"),
                "result": result_file.read_text(encoding="utf-8") if result_file.exists() else "",
            }
        )

        if len(items) >= limit:
            break

    return items


# =========================================================
# 短影音工具：Edge TTS / Pexels / FFmpeg
# =========================================================
def tool_available(name):
    return shutil.which(name) is not None


async def _async_tts(text, output_path):
    import edge_tts
    communicate = edge_tts.Communicate(text, "zh-TW-HsiaoChenNeural")
    await communicate.save(str(output_path))


def create_tts(text, output_path):
    """採用 Python 非同步 API 直接生成語音，相容性更高"""
    try:
        asyncio.run(_async_tts(text, output_path))
    except ImportError:
        # 降級方案：嘗試命令列呼叫
        if not tool_available("edge-tts"):
            raise RuntimeError("找不到 edge-tts 套件，請在 requirements.txt 加入 edge-tts。")
        subprocess.run(
            [
                "edge-tts",
                "--text", text,
                "--voice", "zh-TW-HsiaoChenNeural",
                "--write-media", str(output_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )


def download_pexels_video(keyword, output_path):
    if not PEXELS_KEY:
        raise RuntimeError("尚未設定 PEXELS_KEY。")

    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("缺少 requests，請加入 requirements.txt。") from exc

    headers = {
        "Authorization": PEXELS_KEY,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    params = {
        "query": keyword or "product commercial",
        "orientation": "portrait",
        "per_page": 5,
    }

    response = requests.get(
        "https://api.pexels.com/videos/search",
        headers=headers,
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    videos = response.json().get("videos", [])

    if not videos:
        params["query"] = "abstract product"
        response = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        videos = response.json().get("videos", [])

    if not videos:
        raise RuntimeError("Pexels 找不到適合的影片素材。")

    files = videos[0].get("video_files", [])
    if not files:
        raise RuntimeError("Pexels 影片沒有可下載檔案。")

    portrait = [
        item for item in files
        if item.get("height", 0) >= item.get("width", 0)
    ]
    files = portrait or files
    files.sort(
        key=lambda item: item.get("width", 0) * item.get("height", 0),
        reverse=True,
    )

    video_response = requests.get(
        files[0]["link"],
        headers=headers,
        timeout=120,
    )
    video_response.raise_for_status()
    output_path.write_bytes(video_response.content)

    if output_path.stat().st_size > MAX_VIDEO_MB * 1024 * 1024:
        raise RuntimeError(f"影片超過 {MAX_VIDEO_MB}MB。")

    return output_path


def create_video(background, audio, output):
    if not tool_available("ffmpeg"):
        raise RuntimeError(
            "找不到 FFmpeg。若在 Streamlit Cloud 部署，請新增 packages.txt 並寫入 ffmpeg。"
        )

    command = [
        "ffmpeg",
        "-y",
        "-stream_loop", "-1",
        "-i", str(background),
        "-i", str(audio),
        "-vf",
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-shortest",
        "-movflags", "+faststart",
        str(output),
    ]

    subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )

    return output


# =========================================================
# 登入頁
# =========================================================
def render_login_page():
    st.markdown(
        f'<div class="main-title">🛒 {APP_NAME}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sub-title">永久會員｜管理員｜Gemini 2.5 Flash｜TikTok｜即夢 AI 2.5</div>',
        unsafe_allow_html=True,
    )

    login_tab, register_tab = st.tabs(["🔐 會員登入", "📝 會員註冊"])

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("會員帳號", key="login_username")
            password = st.text_input("會員密碼", type="password", key="login_password")
            submitted = st.form_submit_button("登入", use_container_width=True)

        if submitted:
            ok, message = login_user(username, password)
            if ok:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

        st.info(f"預設管理員帳號：admin / 密碼：{DEFAULT_ADMIN_PASSWORD}")

    with register_tab:
        with st.form("register_form"):
            username = st.text_input("新會員帳號", key="reg_username")
            name = st.text_input("姓名 / 暱稱", key="reg_name")
            email = st.text_input("Email", key="reg_email")
            password = st.text_input("設定密碼", type="password", key="reg_password")
    xt", None)
        if not text:
            raise RuntimeError("Gemini 沒有返回文字內容。")

        st.session_state.gemini_model = GEMINI_MODEL
        st.session_state.gemini_error = ""
        return text.strip()

    except Exception as exc:
        raw = str(exc)

        if "404" in raw:
            msg = "Gemini 模型不存在或目前 API 不支援此模型（404）。"
        elif "401" in raw:
            msg = "Gemini API Key 無效（401）。"
        elif "403" in raw:
            msg = "Gemini API 權限不足（403）。"
        elif "429" in raw:
            msg = "Gemini 額度或頻率限制（429）。"
        elif "400" in raw:
            msg = "Gemini 請求格式錯誤（400）。"
        else:
            msg = f"Gemini 執行失敗：{raw}"

        st.session_state.gemini_error = msg
        raise RuntimeError(msg) from exc


# =========================================================
# Prompt
# =========================================================
SHOPEE_PROMPT_TEMPLATE = """
請輸出：
1. SEO 商品標題
2. 商品賣點 5 點
3. 完整商品描述
4. 關鍵字
5. 長尾關鍵字
6. FAQ 5 題
不得虛構品牌、規格、認證、效果、折扣或贈品。
"""

TIKTOK_PROMPT_TEMPLATE = """
請輸出：
1. 爆款標題
2. 0~3 秒 Hook
3. 15 秒口播
4. 25 秒口播
5. 貼文文案
6. Hashtags
要求前 3 秒抓住注意力，但不得使用無法證實的誇大承諾。
"""

JIMENG_25_RULES = """
上傳商品圖是商品外觀的唯一主要依據。
必須維持品牌、Logo、包裝、文字、顏色、材質、形狀、比例與細節一致。
不得重新設計包裝、改 Logo、改字、改顏色、增加不存在配件。
可改變的是場景、背景、燈光、鏡頭、景深與商業攝影氛圍。
影片預設 9:16 直式。
"""


def build_master_prompt(product):
    p = {key: str(value or "").strip() for key, value in product.items()}

    return f"""
你是「{APP_NAME}」的核心電商 AI。
請使用繁體中文。
只能根據商品圖片與使用者提供的資料回答；不確定的資訊一律寫「待確認」。

==============================
【商品資料】
==============================
商品名稱：{p.get('name')}
商品分類：{p.get('category')}
售價：{p.get('price')}
成本：{p.get('cost')}
分潤比例：{p.get('commission')}
預估月銷量：{p.get('sales')}
商品評分：{p.get('rating')}
商品連結：{p.get('url')}
商品規格：{p.get('specs')}
目標平台：{p.get('platform')}

==============================
【資料真實性規則】
==============================
1. 不得虛構品牌、Logo、規格、認證、成分、功能、價格、折扣、贈品或效果。
2. 圖片看不清楚的文字請寫「待確認」。
3. 使用者沒有提供的數據，不得自行補數字。
4. 不得把 AI 推測寫成確定事實。
5. 行銷文案可以有吸引力，但不能做無法證實的誇大承諾。

==============================
【任務一：商品辨識與 AI 選品分析】
==============================
請分析：
- 商品名稱與分類
- 圖片可確認資訊
- 待確認資訊
- 外觀、包裝、Logo、文字
- 主要賣點
- 目標客群
- 消費需求
- 市場定位
- 優勢
- 劣勢
- 短影音切入點
- 購買誘因
- 合規提醒
- 選品分數 0~100
- 市場吸引力 0~100
- 視覺吸引力 0~100
- TikTok 潛力 0~100
- 蝦皮潛力 0~100

==============================
【任務二：蝦皮高轉化上架文案】
==============================
{SHOPEE_PROMPT_TEMPLATE}

==============================
【任務三：TikTok 爆款帶貨文案】
==============================
{TIKTOK_PROMPT_TEMPLATE}

==============================
【任務四：即夢 AI 2.5 商業生圖 Prompt】
==============================
{JIMENG_25_RULES}
請輸出：
- 【即夢 AI 2.5 生圖英文 Prompt】
- 【Negative Prompt】
- 【畫面繁體中文文字設計】
- 【9:16 構圖與光影建議】

==============================
【任務五：即夢 AI 2.5 商業影片 Prompt】
==============================
請輸出英文影片 Prompt，必須包含：
Opening、Middle、Camera Motion、Lighting、Product Detail、Ending Freeze。
另外輸出 Negative Prompt。

==============================
【任務六：即夢 AI 2.5 25 秒帶貨分鏡】
==============================
0~3 秒：黃金 Hook
3~8 秒：商品全貌與品質展示
8~15 秒：核心賣點與細節特寫
15~20 秒：使用情境與價值呈現
20~25 秒：CTA 與結尾定格

==============================
【任務七：最終檢查】
==============================
檢查是否有虛構資料、誇大宣稱、錯誤品牌、錯誤規格，
以及是否維持原商品圖片的一致性。

請輸出完整、可直接複製使用的 Markdown 報告。
"""


def detect_category(text):
    text = (text or "").lower()
    groups = {
        "保養美妝": ["洗面", "面膜", "乳液", "精華", "保養", "化妝", "美容", "防曬", "洗髮"],
        "3C": ["手機", "耳機", "充電", "電腦", "鍵盤", "滑鼠", "3c", "平板", "螢幕"],
        "居家生活": ["收納", "清潔", "家居", "廚房", "杯", "居家", "拖把", "用品"],
        "服飾": ["衣服", "褲", "鞋", "帽", "包", "服飾", "外套"],
        "食品": ["食品", "零食", "餅乾", "飲料", "茶", "咖啡", "水果"],
        "汽機車": ["汽車", "機車", "車用", "汽機車", "輪胎"],
    }

    for category, keywords in groups.items():
        if any(keyword in text for keyword in keywords):
            return category

    return "其他"


# =========================================================
# 歷史紀錄
# =========================================================
def save_history(product, result):
    history_id = (
        datetime.now().strftime("%Y%m%d_%H%M%S")
        + "_"
        + secrets.token_hex(3)
    )

    folder = HISTORY_DIR / history_id
    folder.mkdir(parents=True, exist_ok=True)

    product_copy = dict(product)
    product_copy.pop("image_bytes", None)

    save_json(folder / "product.json", product_copy)
    (folder / "result.md").write_text(result, encoding="utf-8")

    return history_id


def list_history(limit=30):
    items = []

    for folder in sorted(HISTORY_DIR.glob("*"), reverse=True):
        if not folder.is_dir():
            continue

        product = load_json(folder / "product.json", {})
        result_file = folder / "result.md"

        items.append(
            {
                "id": folder.name,
                "product": product.get("name", "未命名"),
                "result": result_file.read_text(encoding="utf-8") if result_file.exists() else "",
            }
        )

        if len(items) >= limit:
            break

    return items


# =========================================================
# 短影音工具：Edge TTS / Pexels / FFmpeg
# =========================================================
def tool_available(name):
    return shutil.which(name) is not None


def create_tts(text, output_path):
    if not tool_available("edge-tts"):
        raise RuntimeError(
            "找不到 edge-tts。請在 requirements.txt 加入 edge-tts。"
        )

    subprocess.run(
        [
            "edge-tts",
            "--text", text,
            "--voice", "zh-TW-HsiaoChenNeural",
            "--write-media", str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def download_pexels_video(keyword, output_path):
    if not PEXELS_KEY:
        raise RuntimeError("尚未設定 PEXELS_KEY。")

    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("缺少 requests，請加入 requirements.txt。") from exc

    headers = {"Authorization": PEXELS_KEY}
    params = {
        "query": keyword or "product commercial",
        "orientation": "portrait",
        "per_page": 5,
    }

    response = requests.get(
        "https://api.pexels.com/videos/search",
        headers=headers,
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    videos = response.json().get("videos", [])

    if not videos:
        params["query"] = "abstract product"
        response = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        videos = response.json().get("videos", [])

    if not videos:
        raise RuntimeError("Pexels 找不到適合的影片素材。")

    files = videos[0].get("video_files", [])
    if not files:
        raise RuntimeError("Pexels 影片沒有可下載檔案。")

    portrait = [
        item for item in files
        if item.get("height", 0) >= item.get("width", 0)
    ]
    files = portrait or files
    files.sort(
        key=lambda item: item.get("width", 0) * item.get("height", 0),
        reverse=True,
    )

    video_response = requests.get(
        files[0]["link"],
        timeout=120,
    )
    video_response.raise_for_status()
    output_path.write_bytes(video_response.content)

    if output_path.stat().st_size > MAX_VIDEO_MB * 1024 * 1024:
        raise RuntimeError(f"影片超過 {MAX_VIDEO_MB}MB。")

    return output_path


def create_video(background, audio, output):
    if not tool_available("ffmpeg"):
        raise RuntimeError(
            "找不到 FFmpeg。Streamlit Cloud 需要額外安裝系統套件。"
        )

    command = [
        "ffmpeg",
        "-y",
        "-stream_loop", "-1",
        "-i", str(background),
        "-i", str(audio),
        "-vf",
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-shortest",
        "-movflags", "+faststart",
        str(output),
    ]

    subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )

    return output


# =========================================================
# 登入頁
# =========================================================
def render_login_page():
    st.markdown(
        f'<div class="main-title">🛒 {APP_NAME}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sub-title">永久會員｜管理員｜Gemini 2.5 Flash｜TikTok｜即夢 AI 2.5</div>',
        unsafe_allow_html=True,
    )

    login_tab, register_tab = st.tabs(["🔐 會員登入", "📝 會員註冊"])

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("會員帳號", key="login_username")
            password = st.text_input("會員密碼", type="password", key="login_password")
            submitted = st.form_submit_button("登入", use_container_width=True)

        if submitted:
            ok, message = login_user(username, password)
            if ok:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

        st.info(f"預設管理員帳號：admin / 密碼：{DEFAULT_ADMIN_PASSWORD}")

    with register_tab:
        with st.form("register_form"):
            username = st.text_input("新會員帳號", key="reg_username")
            name = st.text_input("姓名 / 暱稱", key="reg_name")
            email = st.text_input("Email", key="reg_email")
            password = st.text_input("設定密碼", type="password", key="reg_password")
            password2 = st.text_input("再次輸入密碼", type="password", key="reg_password2")
            submitted = st.form_submit_button("註冊永久會員", use_container_width=True)

        if submitted:
            if password != password2:
                st.error("兩次密碼不一致。")
            else:
                ok, message = create_member(
                    username,
                    password,
                    name,
                    email,
                    "member",
                    True,
                )
                if ok:
                    st.success(message)
                else:
                    st.error(message)


# =========================================================
# Sidebar
# =========================================================
def render_sidebar():
    with st.sidebar:
        st.markdown(f"## 🛒 {APP_NAME}")
        st.markdown(
            f"""
            <div class="member-card">
            👤 <b>{st.session_state.name}</b><br>
            帳號：{st.session_state.username}<br>
            權限：{st.session_state.role.upper()}<br>
            會員期限：<b>永久</b>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("🏠 AI 自動化主頁", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()

        if st.button("🎬 短影音自動製作", use_container_width=True):
            st.session_state.page = "video"
            st.rerun()

        if st.button("🗂️ 歷史紀錄", use_container_width=True):
            st.session_state.page = "history"
            st.rerun()

        if st.session_state.role == "admin":
            if st.button("👑 管理員中心", use_container_width=True):
                st.session_state.page = "admin"
                st.rerun()

        st.divider()

        if st.button("🚪 登出", use_container_width=True):
            logout_user()
            st.rerun()


# =========================================================
# AI 主頁
# =========================================================
def render_home_page():
    st.title(f"🛒 {APP_NAME}")
    st.caption(
        "商品圖片 → AI 商品分析 → 蝦皮文案 → TikTok 腳本 → 即夢 AI 2.5 Prompt"
    )

    left, right = st.columns([1, 1])

    with left:
        st.subheader("📷 商品資料")

        uploaded_file = st.file_uploader(
            "上傳商品主圖",
            type=["jpg", "jpeg", "png", "webp"],
            key="product_image",
        )

        if uploaded_file:
            st.image(
                uploaded_file,
                caption="商品圖片預覽",
                use_container_width=True,
            )

        product_name = st.text_input(
            "商品名稱",
            placeholder="例如：極致保濕修護精華液",
        )
        product_price = st.text_input("商品售價", placeholder="例如：499")
        product_cost = st.text_input("商品成本", placeholder="例如：150")
        product_commission = st.text_input("分潤比例 (%)", placeholder="例如：15")
        product_sales = st.text_input("預估月銷量", placeholder="例如：1000")
        product_rating = st.text_input("商品評分", placeholder="例如：4.9")
        product_url = st.text_input("商品連結")
        product_specs = st.text_area(
            "商品規格 / 已知資訊",
            height=140,
            placeholder="例如：容量 30ml、台灣製造……",
        )
        platform = st.selectbox(
            "主要目標平台",
            ["蝦皮購物 + TikTok", "僅蝦皮購物", "僅 TikTok"],
        )

        generate_btn = st.button(
            "🚀 開始 AI 全套生成",
            type="primary",
            use_container_width=True,
        )

    with right:
        st.subheader("🤖 AI 分析與生成結果")

        if generate_btn:
            if not uploaded_file:
                st.warning("請先上傳商品圖片。")
            elif not product_name.strip():
                st.warning("請輸入商品名稱。")
            elif not GEMINI_KEY:
                st.error("尚未設定 GEMINI_KEY，無法呼叫 Gemini。")
            else:
                try:
                    img_bytes, mime_type = prepare_image(uploaded_file)
                    category = detect_category(
                        product_name + " " + product_specs
                    )

                    product = {
                        "name": product_name.strip(),
                        "price": product_price,
                        "cost": product_cost,
                        "commission": product_commission,
                        "sales": product_sales,
                        "rating": product_rating,
                        "url": product_url,
                        "specs": product_specs,
                        "platform": platform,
                        "category": category,
                        "image_bytes": img_bytes,
                        "image_mime": mime_type,
                    }

                    with st.spinner(
                        "Gemini 2.5 Flash 正在分析商品圖片與資料……"
                    ):
                        result = ask_gemini(
                            build_master_prompt(product),
                            img_bytes,
                            mime_type,
                        )

                    history_id = save_history(product, result)
                    st.session_state.result = result
                    st.session_state.last_product = {
                        key: value
                        for key, value in product.items()
                        if key != "image_bytes"
                    }
                    st.session_state.last_product["history_id"] = history_id
                    st.session_state.last_image_bytes = img_bytes
                    st.session_state.last_image_mime = mime_type

                    st.success("AI 分析完成，已保存到歷史紀錄。")

                except Exception as exc:
                    st.error(f"生成失敗：{exc}")

        if st.session_state.result:
            st.markdown(
                '<div class="result-box">',
                unsafe_allow_html=True,
            )
            st.markdown(st.session_state.result)
            st.markdown("</div>", unsafe_allow_html=True)

            safe_name = safe_filename(
                st.session_state.last_product.get("name", "商品")
            )

            st.download_button(
                "📥 下載完整電商報告",
                data=st.session_state.result,
                file_name=f"{safe_name}_AI電商報告.md",
                mime="text/markdown",
                use_container_width=True,
            )


# =========================================================
# 短影音頁
# =========================================================
def render_video_page():
    st.title("🎬 短影音自動製作")
    st.caption(
        "Gemini 生成口播 → Edge TTS → Pexels 背景 → FFmpeg → 9:16 MP4"
    )

    if not PEXELS_KEY:
        st.warning("尚未設定 PEXELS_KEY，因此 Pexels 背景影片功能目前無法使用。")

    if not tool_available("edge-tts"):
        st.warning("目前環境找不到 edge-tts。請確認 requirements.txt 已安裝。")

    if not tool_available("ffmpeg"):
        st.warning("目前環境找不到 FFmpeg。Streamlit Cloud 需另外安裝系統套件。")

    col1, col2 = st.columns(2)

    with col1:
        default_topic = st.session_state.last_product.get("name", "")
        topic = st.text_input("影片主題 / 商品名稱", value=default_topic)
        script = st.text_area(
            "口播文案（留空＝Gemini 自動生成）",
            height=180,
        )

    with col2:
        duration = st.selectbox("影片版本", ["15 秒", "25 秒"])
        st.info(
            "輸出格式：MP4\n\n"
            "尺寸：1080 × 1920\n\n"
            "比例：9:16\n\n"
            "語音：zh-TW-HsiaoChenNeural"
        )

    if st.button(
        "🎬 開始製作影片",
        type="primary",
        use_container_width=True,
    ):
        if not topic.strip():
            st.error("請輸入影片主題。")
            return

        if not GEMINI_KEY and not script.strip():
            st.error("未設定 GEMINI_KEY，且你沒有手動輸入口播。")
            return

        if not PEXELS_KEY:
            st.error("請先設定 PEXELS_KEY。")
            return

        work = MEDIA_DIR / ("video_" + secrets.token_hex(5))
        work.mkdir(parents=True, exist_ok=True)

        try:
            if not script.strip():
                prompt = f"""
請為商品「{topic}」寫一段繁體中文 {duration} TikTok 短影音口播。
前 3 秒必須有 Hook。
不要虛構價格、功能、效果、品牌或優惠。
只輸出口播內容，不要標題，不要 Markdown。
"""
                with st.spinner("Gemini 正在生成短影音口播……"):
                    script = ask_gemini(prompt)

            st.write("📝 口播文案")
            st.info(script)

            audio_path = work / "audio.mp3"
            background_path = work / "background.mp4"
            output_path = work / "output.mp4"

            with st.status("正在製作影片……", expanded=True) as status:
                status.write("🎙️ 1/3 生成語音")
                create_tts(script, audio_path)

                status.write("🎥 2/3 下載直式背景影片")
                keyword = topic.strip().split()[0] if topic.strip() else "product"
                download_pexels_video(keyword, background_path)

                status.write("⚙️ 3/3 FFmpeg 合成 9:16")
                create_video(background_path, audio_path, output_path)
                status.update(
                    label="🎉 影片完成！",
                    state="complete",
                )

            video_bytes = output_path.read_bytes()
            st.session_state.last_video_bytes = video_bytes
            st.session_state.last_video_name = safe_filename(topic) + ".mp4"
            st.session_state.last_video_mime = "video/mp4"

            st.video(video_bytes)
            st.download_button(
                "⬇️ 下載 MP4",
                data=video_bytes,
                file_name=st.session_state.last_video_name,
                mime="video/mp4",
                use_container_width=True,
            )

        except Exception as exc:
            st.error(f"影片製作失敗：{exc}")


# =========================================================
# 歷史紀錄頁
# =========================================================
def render_history_page():
    st.title("🗂️ 歷史紀錄")
    st.caption("最近 30 筆 AI 商品分析紀錄")

    items = list_history(30)

    if not items:
        st.info("目前沒有歷史紀錄。")
        return

    for item in items:
        with st.expander(
            f"📦 {item['product']}｜{item['id']}"
        ):
            st.markdown(item["result"])
            st.download_button(
                "📥 下載此報告",
                data=item["result"],
                file_name=(
                    f"{safe_filename(item['product'])}_"
                    f"{item['id']}.md"
                ),
                mime="text/markdown",
                key="history_dl_" + item["id"],
            )


# =========================================================
# 管理員中心
# =========================================================
def render_admin_page():
    st.title("👑 管理員中心")
    st.caption("永久會員制：沒有到期日，可手動停用 / 啟用會員。")

    members = load_members()

    total = len(members)
    active = sum(
        1 for member in members.values()
        if member.get("status") == "active"
    )
    admin_count = sum(
        1 for member in members.values()
        if member.get("role") == "admin"
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("會員總數", total)
    col2.metric("啟用會員", active)
    col3.metric("管理員", admin_count)

    st.divider()
    st.subheader("➕ 建立永久會員")

    with st.form("admin_create_member"):
        left, right = st.columns(2)

        with left:
            username = st.text_input("會員帳號")
            name = st.text_input("姓名 / 暱稱")

        with right:
            password = st.text_input("會員密碼", type="password")
            email = st.text_input("Email")

        role = st.selectbox(
            "會員等級",
            ["member", "vip", "admin"],
            format_func=lambda value: {
                "member": "一般會員",
                "vip": "VIP 會員",
                "admin": "管理員",
            }[value],
        )

        submitted = st.form_submit_button(
            "建立永久會員",
            use_container_width=True,
        )

    if submitted:
        ok, message = create_member(
            username,
            password,
            name,
            email,
            role,
            True,
        )

        if ok:
            st.success(message)
            st.rerun()
        else:
            st.error(message)

    st.divider()
    st.subheader("👥 會員清單")

    members = load_members()

    for index, (username, member) in enumerate(members.items()):
        role = member.get("role", "member")
        name = member.get("name", username)

        with st.expander(
            f"👤 {username}｜{name}｜{role.upper()}"
        ):
            st.write(f"Email：{member.get('email', '無')}")
            st.write(f"狀態：{member.get('status', 'active')}")
            st.write(f"建立時間：{member.get('created_at', '')}")
            st.write("會員期限：永久")

            if username != ADMIN_USERNAME:
                is_active = member.get("status") == "active"
                label = "停用帳號" if is_active else "啟用帳號"

                if st.button(
                    label,
                    key=f"toggle_{index}_{username}",
                ):
                    fresh_members = load_members()
                    fresh_members[username]["status"] = (
                        "disabled" if is_active else "active"
                    )
                    save_members(fresh_members)
                    st.success("會員狀態已更新。")
                    st.rerun()


# =========================================================
# Main
# =========================================================
def main():
    ensure_admin()

    if not st.session_state.logged_in:
        render_login_page()
        return

    # 每次重新執行都重新檢查會員狀態。
    current = load_members().get(st.session_state.username)

    if not current or current.get("status") != "active":
        logout_user()
        st.error("帳號目前無法使用，請重新登入。")
        return

    status, valid = member_expiration(current)
    if not valid:
        logout_user()
        st.error(f"會員資格無法使用：{status}")
        return

    st.session_state.member = current
    st.session_state.name = current.get(
        "name",
        current.get("username", ""),
    )
    st.session_state.role = current.get("role", "member")

    render_sidebar()

    if st.session_state.page == "admin" and st.session_state.role == "admin":
        render_admin_page()
    elif st.session_state.page == "video":
        render_video_page()
    elif st.session_state.page == "history":
        render_history_page()
    else:
        render_home_page()


if __name__ == "__main__":
    main()
st.set_page_config(
    page_title=APP_NAME,
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
.main-title{font-size:36px;font-weight:800}
.sub-title{color:#777;margin-bottom:20px}
.member-card{padding:14px;border-radius:14px;border:1px solid rgba(128,128,128,.25);margin:10px 0}
.small{color:#777;font-size:14px}
.result-box{padding:18px;border-radius:16px;border:1px solid rgba(128,128,128,.25)}
</style>
""",
    unsafe_allow_html=True,
)

# =========================================================
# Session State
# =========================================================
DEFAULT_STATE = {
    "logged_in": False,
    "username": "",
    "name": "",
    "role": "",
    "member": {},
    "page": "home",
    "result": "",
    "last_product": {},
    "last_image_bytes": None,
    "last_image_mime": "image/jpeg",
    "last_video_bytes": None,
    "last_video_name": "",
    "last_video_mime": "video/mp4",
    "gemini_model": GEMINI_MODEL,
    "gemini_error": "",
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# Secrets / API
# =========================================================
def get_secret(name, default=""):
    try:
        value = st.secrets.get(name, default)
        if value:
            return str(value)
    except Exception:
        pass
    return os.environ.get(name, default)


GEMINI_KEY = get_secret("GEMINI_KEY") or get_secret("GEMINI_API_KEY")
PEXELS_KEY = get_secret("PEXELS_KEY")


# =========================================================
# 基礎工具
# =========================================================
def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def hash_password(password):
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest()


def safe_filename(name):
    name = re.sub(r'[\\/:*?"<>|]+', "_", str(name or "file"))
    name = re.sub(r"\s+", " ", name).strip()
    return name[:100] or "file"


def load_json(path, default):
    try:
        path = Path(path)
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception:
        return default


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    temp.replace(path)


# =========================================================
# 會員系統
# =========================================================
def load_members():
    members = load_json(MEMBERS_FILE, {})
    return members if isinstance(members, dict) else {}


def save_members(members):
    save_json(MEMBERS_FILE, members)


def ensure_admin():
    members = load_members()
    changed = False
    admin = members.get(ADMIN_USERNAME)

    if not isinstance(admin, dict):
        members[ADMIN_USERNAME] = {
            "username": ADMIN_USERNAME,
            "name": "系統管理員",
            "email": "",
            "password_hash": hash_password(DEFAULT_ADMIN_PASSWORD),
            "created_at": now_text(),
            "expire_date": None,
            "permanent": True,
            "role": "admin",
            "status": "active",
        }
        changed = True
    else:
        defaults = {
            "username": ADMIN_USERNAME,
            "name": "系統管理員",
            "email": "",
            "created_at": now_text(),
            "expire_date": None,
            "permanent": True,
            "role": "admin",
            "status": "active",
        }
        for key, value in defaults.items():
            if key not in admin:
                admin[key] = value
                changed = True
        if admin.get("role") != "admin":
            admin["role"] = "admin"
            changed = True

    if changed:
        save_members(members)


def member_expiration(member):
    if member.get("permanent", True):
        return "永久會員", True

    expire = member.get("expire_date")
    if not expire:
        return "未設定", False

    try:
        expire_date = date.fromisoformat(expire)
    except Exception:
        return "日期錯誤", False

    days = (expire_date - date.today()).days
    if days < 0:
        return f"已到期（{abs(days)} 天）", False

    return f"剩餘 {days} 天", True


def create_member(
    username,
    password,
    name="",
    email="",
    role="member",
    permanent=True,
    days=30,
):
    username = str(username or "").strip()
    password = str(password or "")
    name = str(name or "").strip()
    email = str(email or "").strip()

    if not username or not password:
        return False, "帳號與密碼不能為空。"
    if len(username) < 3:
        return False, "帳號至少 3 個字元。"
    if len(password) < 6:
        return False, "密碼至少 6 個字元。"
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
        return False, "帳號只能使用英數、底線、點或連字號。"

    members = load_members()
    if username in members:
        return False, "帳號已存在。"

    expire_date = None
    if not permanent:
        expire_date = (date.today() + timedelta(days=int(days))).isoformat()

    members[username] = {
        "username": username,
        "name": name or username,
        "email": email,
        "password_hash": hash_password(password),
        "created_at": now_text(),
        "expire_date": expire_date,
        "permanent": bool(permanent),
        "role": role if role in {"member", "vip", "admin"} else "member",
        "status": "active",
    }

    save_members(members)
    return True, "會員建立成功。"


def authenticate(username, password):
    username = str(username or "").strip()
    members = load_members()
    member = members.get(username)

    if not member:
        return None, "帳號不存在。"
    if member.get("status", "active") != "active":
        return None, "此帳號目前已停用。"

    password_hash = hash_password(password)
    if not secrets.compare_digest(
        str(member.get("password_hash", "")),
        password_hash,
    ):
        return None, "密碼錯誤。"

    status, valid = member_expiration(member)
    if not valid:
        return None, f"會員無法使用：{status}"

    return member, ""


def login_user(username, password):
    member, message = authenticate(username, password)
    if not member:
        return False, message

    st.session_state.logged_in = True
    st.session_state.username = member.get("username", "")
    st.session_state.name = member.get("name", member.get("username", ""))
    st.session_state.role = member.get("role", "member")
    st.session_state.member = member
    st.session_state.page = "home"
    return True, "登入成功。"


def logout_user():
    for key, value in DEFAULT_STATE.items():
        st.session_state[key] = value


# =========================================================
# 圖片處理
# =========================================================
def prepare_image(uploaded_file):
    if not uploaded_file:
        raise ValueError("沒有收到圖片。")

    raw = uploaded_file.getvalue()
    if len(raw) > MAX_IMAGE_MB * 1024 * 1024:
        raise ValueError(f"圖片超過 {MAX_IMAGE_MB}MB。")

    try:
        image = Image.open(io.BytesIO(raw))
        image = ImageOps.exif_transpose(image)

        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")

        image.thumbnail(
            (MAX_IMAGE_SIZE, MAX_IMAGE_SIZE),
            Image.Resampling.LANCZOS,
        )

        output = io.BytesIO()

        if image.mode == "RGBA":
            image.save(output, format="PNG", optimize=True)
            mime = "image/png"
        else:
            image.save(output, format="JPEG", quality=92, optimize=True)
            mime = "image/jpeg"

        return output.getvalue(), mime
    except Exception as exc:
        raise ValueError(f"圖片處理失敗：{exc}") from exc


# =========================================================
# Gemini
# =========================================================
def get_gemini_client():
    if not GEMINI_KEY:
        raise RuntimeError(
            "尚未設定 GEMINI_KEY。請在 Streamlit Secrets 加入 GEMINI_KEY。"
        )

    try:
        from google import genai
        return genai.Client(api_key=GEMINI_KEY)
    except ImportError as exc:
        raise RuntimeError(
            "缺少 google-genai，請在 requirements.txt 加入 google-genai。"
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"Gemini 初始化失敗：{exc}") from exc


def ask_gemini(prompt, image_bytes=None, mime_type="image/jpeg"):
    client = get_gemini_client()

    try:
        from google.genai import types

        contents = []

        if image_bytes:
            contents.append(
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type,
                )
            )

        contents.append(prompt)

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
        )

        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("Gemini 沒有返回文字內容。")

        st.session_state.gemini_model = GEMINI_MODEL
        st.session_state.gemini_error = ""
        return text.strip()

    except Exception as exc:
        raw = str(exc)

        if "404" in raw:
            msg = "Gemini 模型不存在或目前 API 不支援此模型（404）。"
        elif "401" in raw:
            msg = "Gemini API Key 無效（401）。"
        elif "403" in raw:
            msg = "Gemini API 權限不足（403）。"
        elif "429" in raw:
            msg = "Gemini 額度或頻率限制（429）。"
        elif "400" in raw:
            msg = "Gemini 請求格式錯誤（400）。"
        else:
            msg = f"Gemini 執行失敗：{raw}"

        st.session_state.gemini_error = msg
        raise RuntimeError(msg) from exc


# =========================================================
# Prompt
# =========================================================
SHOPEE_PROMPT_TEMPLATE = """
請輸出：
1. SEO 商品標題
2. 商品賣點 5 點
3. 完整商品描述
4. 關鍵字
5. 長尾關鍵字
6. FAQ 5 題
不得虛構品牌、規格、認證、效果、折扣或贈品。
"""

TIKTOK_PROMPT_TEMPLATE = """
請輸出：
1. 爆款標題
2. 0~3 秒 Hook
3. 15 秒口播
4. 25 秒口播
5. 貼文文案
6. Hashtags
要求前 3 秒抓住注意力，但不得使用無法證實的誇大承諾。
"""

JIMENG_25_RULES = """
上傳商品圖是商品外觀的唯一主要依據。
必須維持品牌、Logo、包裝、文字、顏色、材質、形狀、比例與細節一致。
不得重新設計包裝、改 Logo、改字、改顏色、增加不存在配件。
可改變的是場景、背景、燈光、鏡頭、景深與商業攝影氛圍。
影片預設 9:16 直式。
"""


def build_master_prompt(product):
    p = {key: str(value or "").strip() for key, value in product.items()}

    return f"""
你是「{APP_NAME}」的核心電商 AI。
請使用繁體中文。
只能根據商品圖片與使用者提供的資料回答；不確定的資訊一律寫「待確認」。

==============================
【商品資料】
==============================
商品名稱：{p.get('name')}
商品分類：{p.get('category')}
售價：{p.get('price')}
成本：{p.get('cost')}
分潤比例：{p.get('commission')}
預估月銷量：{p.get('sales')}
商品評分：{p.get('rating')}
商品連結：{p.get('url')}
商品規格：{p.get('specs')}
目標平台：{p.get('platform')}

==============================
【資料真實性規則】
==============================
1. 不得虛構品牌、Logo、規格、認證、成分、功能、價格、折扣、贈品或效果。
2. 圖片看不清楚的文字請寫「待確認」。
3. 使用者沒有提供的數據，不得自行補數字。
4. 不得把 AI 推測寫成確定事實。
5. 行銷文案可以有吸引力，但不能做無法證實的誇大承諾。

==============================
【任務一：商品辨識與 AI 選品分析】
==============================
請分析：
- 商品名稱與分類
- 圖片可確認資訊
- 待確認資訊
- 外觀、包裝、Logo、文字
- 主要賣點
- 目標客群
- 消費需求
- 市場定位
- 優勢
- 劣勢
- 短影音切入點
- 購買誘因
- 合規提醒
- 選品分數 0~100
- 市場吸引力 0~100
- 視覺吸引力 0~100
- TikTok 潛力 0~100
- 蝦皮潛力 0~100

==============================
【任務二：蝦皮高轉化上架文案】
==============================
{SHOPEE_PROMPT_TEMPLATE}

==============================
【任務三：TikTok 爆款帶貨文案】
==============================
{TIKTOK_PROMPT_TEMPLATE}

==============================
【任務四：即夢 AI 2.5 商業生圖 Prompt】
==============================
{JIMENG_25_RULES}
請輸出：
- 【即夢 AI 2.5 生圖英文 Prompt】
- 【Negative Prompt】
- 【畫面繁體中文文字設計】
- 【9:16 構圖與光影建議】

==============================
【任務五：即夢 AI 2.5 商業影片 Prompt】
==============================
請輸出英文影片 Prompt，必須包含：
Opening、Middle、Camera Motion、Lighting、Product Detail、Ending Freeze。
另外輸出 Negative Prompt。

==============================
【任務六：即夢 AI 2.5 25 秒帶貨分鏡】
==============================
0~3 秒：黃金 Hook
3~8 秒：商品全貌與品質展示
8~15 秒：核心賣點與細節特寫
15~20 秒：使用情境與價值呈現
20~25 秒：CTA 與結尾定格

==============================
【任務七：最終檢查】
==============================
檢查是否有虛構資料、誇大宣稱、錯誤品牌、錯誤規格，
以及是否維持原商品圖片的一致性。

請輸出完整、可直接複製使用的 Markdown 報告。
"""


def detect_category(text):
    text = (text or "").lower()
    groups = {
        "保養美妝": ["洗面", "面膜", "乳液", "精華", "保養", "化妝", "美容", "防曬", "洗髮"],
        "3C": ["手機", "耳機", "充電", "電腦", "鍵盤", "滑鼠", "3c", "平板", "螢幕"],
        "居家生活": ["收納", "清潔", "家居", "廚房", "杯", "居家", "拖把", "用品"],
        "服飾": ["衣服", "褲", "鞋", "帽", "包", "服飾", "外套"],
        "食品": ["食品", "零食", "餅乾", "飲料", "茶", "咖啡", "水果"],
        "汽機車": ["汽車", "機車", "車用", "汽機車", "輪胎"],
    }

    for category, keywords in groups.items():
        if any(keyword in text for keyword in keywords):
            return category

    return "其他"


# =========================================================
# 歷史紀錄
# =========================================================
def save_history(product, result):
    history_id = (
        datetime.now().strftime("%Y%m%d_%H%M%S")
        + "_"
        + secrets.token_hex(3)
    )

    folder = HISTORY_DIR / history_id
    folder.mkdir(parents=True, exist_ok=True)

    product_copy = dict(product)
    product_copy.pop("image_bytes", None)

    save_json(folder / "product.json", product_copy)
    (folder / "result.md").write_text(result, encoding="utf-8")

    return history_id


def list_history(limit=30):
    items = []

    for folder in sorted(HISTORY_DIR.glob("*"), reverse=True):
        if not folder.is_dir():
            continue

        product = load_json(folder / "product.json", {})
        result_file = folder / "result.md"

        items.append(
            {
                "id": folder.name,
                "product": product.get("name", "未命名"),
                "result": result_file.read_text(encoding="utf-8") if result_file.exists() else "",
            }
        )

        if len(items) >= limit:
            break

    return items


# =========================================================
# 短影音工具：Edge TTS / Pexels / FFmpeg
# =========================================================
def tool_available(name):
    return shutil.which(name) is not None


def create_tts(text, output_path):
    if not tool_available("edge-tts"):
        raise RuntimeError(
            "找不到 edge-tts。請在 requirements.txt 加入 edge-tts。"
        )

    subprocess.run(
        [
            "edge-tts",
            "--text", text,
            "--voice", "zh-TW-HsiaoChenNeural",
            "--write-media", str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def download_pexels_video(keyword, output_path):
    if not PEXELS_KEY:
        raise RuntimeError("尚未設定 PEXELS_KEY。")

    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("缺少 requests，請加入 requirements.txt。") from exc

    headers = {"Authorization": PEXELS_KEY}
    params = {
        "query": keyword or "product commercial",
        "orientation": "portrait",
        "per_page": 5,
    }

    response = requests.get(
        "https://api.pexels.com/videos/search",
        headers=headers,
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    videos = response.json().get("videos", [])

    if not videos:
        params["query"] = "abstract product"
        response = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        videos = response.json().get("videos", [])

    if not videos:
        raise RuntimeError("Pexels 找不到適合的影片素材。")

    files = videos[0].get("video_files", [])
    if not files:
        raise RuntimeError("Pexels 影片沒有可下載檔案。")

    portrait = [
        item for item in files
        if item.get("height", 0) >= item.get("width", 0)
    ]
    files = portrait or files
    files.sort(
        key=lambda item: item.get("width", 0) * item.get("height", 0),
        reverse=True,
    )

    video_response = requests.get(
        files[0]["link"],
        timeout=120,
    )
    video_response.raise_for_status()
    output_path.write_bytes(video_response.content)

    if output_path.stat().st_size > MAX_VIDEO_MB * 1024 * 1024:
        raise RuntimeError(f"影片超過 {MAX_VIDEO_MB}MB。")

    return output_path


def create_video(background, audio, output):
    if not tool_available("ffmpeg"):
        raise RuntimeError(
            "找不到 FFmpeg。Streamlit Cloud 需要額外安裝系統套件。"
        )

    command = [
        "ffmpeg",
        "-y",
        "-stream_loop", "-1",
        "-i", str(background),
        "-i", str(audio),
        "-vf",
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-shortest",
        "-movflags", "+faststart",
        str(output),
    ]

    subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )

    return output


# =========================================================
# 登入頁
# =========================================================
def render_login_page():
    st.markdown(
        f'<div class="main-title">🛒 {APP_NAME}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sub-title">永久會員｜管理員｜Gemini 2.5 Flash｜TikTok｜即夢 AI 2.5</div>',
        unsafe_allow_html=True,
    )

    login_tab, register_tab = st.tabs(["🔐 會員登入", "📝 會員註冊"])

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("會員帳號", key="login_username")
            password = st.text_input("會員密碼", type="password", key="login_password")
            submitted = st.form_submit_button("登入", use_container_width=True)

        if submitted:
            ok, message = login_user(username, password)
            if ok:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

        st.info(f"預設管理員帳號：admin / 密碼：{DEFAULT_ADMIN_PASSWORD}")

    with register_tab:
        with st.form("register_form"):
            username = st.text_input("新會員帳號", key="reg_username")
            name = st.text_input("姓名 / 暱稱", key="reg_name")
            email = st.text_input("Email", key="reg_email")
            password = st.text_input("設定密碼", type="password", key="reg_password")
            password2 = st.text_input("再次輸入密碼", type="password", key="reg_password2")
            submitted = st.form_submit_button("註冊永久會員", use_container_width=True)

        if submitted:
            if password != password2:
                st.error("兩次密碼不一致。")
            else:
                ok, message = create_member(
                    username,
                    password,
                    name,
                    email,
                    "member",
                    True,
                )
                if ok:
                    st.success(message)
                else:
                    st.error(message)


# =========================================================
# Sidebar
# =========================================================
def render_sidebar():
    with st.sidebar:
        st.markdown(f"## 🛒 {APP_NAME}")
        st.markdown(
            f"""
            <div class="member-card">
            👤 <b>{st.session_state.name}</b><br>
            帳號：{st.session_state.username}<br>
            權限：{st.session_state.role.upper()}<br>
            會員期限：<b>永久</b>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("🏠 AI 自動化主頁", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()

        if st.button("🎬 短影音自動製作", use_container_width=True):
            st.session_state.page = "video"
            st.rerun()

        if st.button("🗂️ 歷史紀錄", use_container_width=True):
            st.session_state.page = "history"
            st.rerun()

        if st.session_state.role == "admin":
            if st.button("👑 管理員中心", use_container_width=True):
                st.session_state.page = "admin"
                st.rerun()

        st.divider()

        if st.button("🚪 登出", use_container_width=True):
            logout_user()
            st.rerun()


# =========================================================
# AI 主頁
# =========================================================
def render_home_page():
    st.title(f"🛒 {APP_NAME}")
    st.caption(
        "商品圖片 → AI 商品分析 → 蝦皮文案 → TikTok 腳本 → 即夢 AI 2.5 Prompt"
    )

    left, right = st.columns([1, 1])

    with left:
        st.subheader("📷 商品資料")

        uploaded_file = st.file_uploader(
            "上傳商品主圖",
            type=["jpg", "jpeg", "png", "webp"],
            key="product_image",
        )

        if uploaded_file:
            st.image(
                uploaded_file,
                caption="商品圖片預覽",
                use_container_width=True,
            )

        product_name = st.text_input(
            "商品名稱",
            placeholder="例如：極致保濕修護精華液",
        )
        product_price = st.text_input("商品售價", placeholder="例如：499")
        product_cost = st.text_input("商品成本", placeholder="例如：150")
        product_commission = st.text_input("分潤比例 (%)", placeholder="例如：15")
        product_sales = st.text_input("預估月銷量", placeholder="例如：1000")
        product_rating = st.text_input("商品評分", placeholder="例如：4.9")
        product_url = st.text_input("商品連結")
        product_specs = st.text_area(
            "商品規格 / 已知資訊",
            height=140,
            placeholder="例如：容量 30ml、台灣製造……",
        )
        platform = st.selectbox(
            "主要目標平台",
            ["蝦皮購物 + TikTok", "僅蝦皮購物", "僅 TikTok"],
        )

        generate_btn = st.button(
            "🚀 開始 AI 全套生成",
            type="primary",
            use_container_width=True,
        )

    with right:
        st.subheader("🤖 AI 分析與生成結果")

        if generate_btn:
            if not uploaded_file:
                st.warning("請先上傳商品圖片。")
            elif not product_name.strip():
                st.warning("請輸入商品名稱。")
            elif not GEMINI_KEY:
                st.error("尚未設定 GEMINI_KEY，無法呼叫 Gemini。")
            else:
                try:
                    img_bytes, mime_type = prepare_image(uploaded_file)
                    category = detect_category(
                        product_name + " " + product_specs
                    )

                    product = {
                        "name": product_name.strip(),
                        "price": product_price,
                        "cost": product_cost,
                        "commission": product_commission,
                        "sales": product_sales,
                        "rating": product_rating,
                        "url": product_url,
                        "specs": product_specs,
                        "platform": platform,
                        "category": category,
                        "image_bytes": img_bytes,
                        "image_mime": mime_type,
                    }

                    with st.spinner(
                        "Gemini 2.5 Flash 正在分析商品圖片與資料……"
                    ):
                        result = ask_gemini(
                            build_master_prompt(product),
                            img_bytes,
                            mime_type,
                        )

                    history_id = save_history(product, result)
                    st.session_state.result = result
                    st.session_state.last_product = {
                        key: value
                        for key, value in product.items()
                        if key != "image_bytes"
                    }
                    st.session_state.last_product["history_id"] = history_id
                    st.session_state.last_image_bytes = img_bytes
                    st.session_state.last_image_mime = mime_type

                    st.success("AI 分析完成，已保存到歷史紀錄。")

                except Exception as exc:
                    st.error(f"生成失敗：{exc}")

        if st.session_state.result:
            st.markdown(
                '<div class="result-box">',
                unsafe_allow_html=True,
            )
            st.markdown(st.session_state.result)
            st.markdown("</div>", unsafe_allow_html=True)

            safe_name = safe_filename(
                st.session_state.last_product.get("name", "商品")
            )

            st.download_button(
                "📥 下載完整電商報告",
                data=st.session_state.result,
                file_name=f"{safe_name}_AI電商報告.md",
                mime="text/markdown",
                use_container_width=True,
            )


# =========================================================
# 短影音頁
# =========================================================
def render_video_page():
    st.title("🎬 短影音自動製作")
    st.caption(
        "Gemini 生成口播 → Edge TTS → Pexels 背景 → FFmpeg → 9:16 MP4"
    )

    if not PEXELS_KEY:
        st.warning("尚未設定 PEXELS_KEY，因此 Pexels 背景影片功能目前無法使用。")

    if not tool_available("edge-tts"):
        st.warning("目前環境找不到 edge-tts。請確認 requirements.txt 已安裝。")

    if not tool_available("ffmpeg"):
        st.warning("目前環境找不到 FFmpeg。Streamlit Cloud 需另外安裝系統套件。")

    col1, col2 = st.columns(2)

    with col1:
        default_topic = st.session_state.last_product.get("name", "")
        topic = st.text_input("影片主題 / 商品名稱", value=default_topic)
        script = st.text_area(
            "口播文案（留空＝Gemini 自動生成）",
            height=180,
        )

    with col2:
        duration = st.selectbox("影片版本", ["15 秒", "25 秒"])
        st.info(
            "輸出格式：MP4\n\n"
            "尺寸：1080 × 1920\n\n"
            "比例：9:16\n\n"
            "語音：zh-TW-HsiaoChenNeural"
        )

    if st.button(
        "🎬 開始製作影片",
        type="primary",
        use_container_width=True,
    ):
        if not topic.strip():
            st.error("請輸入影片主題。")
            return

        if not GEMINI_KEY and not script.strip():
            st.error("未設定 GEMINI_KEY，且你沒有手動輸入口播。")
            return

        if not PEXELS_KEY:
            st.error("請先設定 PEXELS_KEY。")
            return

        work = MEDIA_DIR / ("video_" + secrets.token_hex(5))
        work.mkdir(parents=True, exist_ok=True)

        try:
            if not script.strip():
                prompt = f"""
請為商品「{topic}」寫一段繁體中文 {duration} TikTok 短影音口播。
前 3 秒必須有 Hook。
不要虛構價格、功能、效果、品牌或優惠。
只輸出口播內容，不要標題，不要 Markdown。
"""
                with st.spinner("Gemini 正在生成短影音口播……"):
                    script = ask_gemini(prompt)

            st.write("📝 口播文案")
            st.info(script)

            audio_path = work / "audio.mp3"
            background_path = work / "background.mp4"
            output_path = work / "output.mp4"

            with st.status("正在製作影片……", expanded=True) as status:
                status.write("🎙️ 1/3 生成語音")
                create_tts(script, audio_path)

                status.write("🎥 2/3 下載直式背景影片")
                keyword = topic.strip().split()[0] if topic.strip() else "product"
                download_pexels_video(keyword, background_path)

                status.write("⚙️ 3/3 FFmpeg 合成 9:16")
                create_video(background_path, audio_path, output_path)
                status.update(
                    label="🎉 影片完成！",
                    state="complete",
                )

            video_bytes = output_path.read_bytes()
            st.session_state.last_video_bytes = video_bytes
            st.session_state.last_video_name = safe_filename(topic) + ".mp4"
            st.session_state.last_video_mime = "video/mp4"

            st.video(video_bytes)
            st.download_button(
                "⬇️ 下載 MP4",
                data=video_bytes,
                file_name=st.session_state.last_video_name,
                mime="video/mp4",
                use_container_width=True,
            )

        except Exception as exc:
            st.error(f"影片製作失敗：{exc}")


# =========================================================
# 歷史紀錄頁
# =========================================================
def render_history_page():
    st.title("🗂️ 歷史紀錄")
    st.caption("最近 30 筆 AI 商品分析紀錄")

    items = list_history(30)

    if not items:
        st.info("目前沒有歷史紀錄。")
        return

    for item in items:
        with st.expander(
            f"📦 {item['product']}｜{item['id']}"
        ):
            st.markdown(item["result"])
            st.download_button(
                "📥 下載此報告",
                data=item["result"],
                file_name=(
                    f"{safe_filename(item['product'])}_"
                    f"{item['id']}.md"
                ),
                mime="text/markdown",
                key="history_dl_" + item["id"],
            )


# =========================================================
# 管理員中心
# =========================================================
def render_admin_page():
    st.title("👑 管理員中心")
    st.caption("永久會員制：沒有到期日，可手動停用 / 啟用會員。")

    members = load_members()

    total = len(members)
    active = sum(
        1 for member in members.values()
        if member.get("status") == "active"
    )
    admin_count = sum(
        1 for member in members.values()
        if member.get("role") == "admin"
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("會員總數", total)
    col2.metric("啟用會員", active)
    col3.metric("管理員", admin_count)

    st.divider()
    st.subheader("➕ 建立永久會員")

    with st.form("admin_create_member"):
        left, right = st.columns(2)

        with left:
            username = st.text_input("會員帳號")
            name = st.text_input("姓名 / 暱稱")

        with right:
            password = st.text_input("會員密碼", type="password")
            email = st.text_input("Email")

        role = st.selectbox(
            "會員等級",
            ["member", "vip", "admin"],
            format_func=lambda value: {
                "member": "一般會員",
                "vip": "VIP 會員",
                "admin": "管理員",
            }[value],
        )

        submitted = st.form_submit_button(
            "建立永久會員",
            use_container_width=True,
        )

    if submitted:
        ok, message = create_member(
            username,
            password,
            name,
            email,
            role,
            True,
        )

        if ok:
            st.success(message)
            st.rerun()
        else:
            st.error(message)

    st.divider()
    st.subheader("👥 會員清單")

    members = load_members()

    for index, (username, member) in enumerate(members.items()):
        role = member.get("role", "member")
        name = member.get("name", username)

        with st.expander(
            f"👤 {username}｜{name}｜{role.upper()}"
        ):
            st.write(f"Email：{member.get('email', '無')}")
            st.write(f"狀態：{member.get('status', 'active')}")
            st.write(f"建立時間：{member.get('created_at', '')}")
            st.write("會員期限：永久")

            if username != ADMIN_USERNAME:
                is_active = member.get("status") == "active"
                label = "停用帳號" if is_active else "啟用帳號"

                if st.button(
                    label,
                    key=f"toggle_{index}_{username}",
                ):
                    fresh_members = load_members()
                    fresh_members[username]["status"] = (
                        "disabled" if is_active else "active"
                    )
                    save_members(fresh_members)
                    st.success("會員狀態已更新。")
                    st.rerun()


# =========================================================
# Main
# =========================================================
def main():
    ensure_admin()

    if not st.session_state.logged_in:
        render_login_page()
        return

    # 每次重新執行都重新檢查會員狀態。
    current = load_members().get(st.session_state.username)

    if not current or current.get("status") != "active":
        logout_user()
        st.error("帳號目前無法使用，請重新登入。")
        return

    status, valid = member_expiration(current)
    if not valid:
        logout_user()
        st.error(f"會員資格無法使用：{status}")
        return

    st.session_state.member = current
    st.session_state.name = current.get(
        "name",
        current.get("username", ""),
    )
    st.session_state.role = current.get("role", "member")

    render_sidebar()

    if st.session_state.page == "admin" and st.session_state.role == "admin":
        render_admin_page()
    elif st.session_state.page == "video":
        render_video_page()
    elif st.session_state.page == "history":
        render_history_page()
    else:
        render_home_page()


if __name__ == "__main__":
    main()
st.set_page_config(
    page_title=APP_NAME,
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
.main-title{font-size:36px;font-weight:800}
.sub-title{color:#777;margin-bottom:20px}
.member-card{padding:14px;border-radius:14px;border:1px solid rgba(128,128,128,.25);margin:10px 0}
.small{color:#777;font-size:14px}
.result-box{padding:18px;border-radius:16px;border:1px solid rgba(128,128,128,.25)}
</style>
""",
    unsafe_allow_html=True,
)

# =========================================================
# Session State
# =========================================================
DEFAULT_STATE = {
    "logged_in": False,
    "username": "",
    "name": "",
    "role": "",
    "member": {},
    "page": "home",
    "result": "",
    "last_product": {},
    "last_image_bytes": None,
    "last_image_mime": "image/jpeg",
    "last_video_bytes": None,
    "last_video_name": "",
    "last_video_mime": "video/mp4",
    "gemini_model": GEMINI_MODEL,
    "gemini_error": "",
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# Secrets / API
# =========================================================
def get_secret(name, default=""):
    try:
        value = st.secrets.get(name, default)
        if value:
            return str(value)
    except Exception:
        pass
    return os.environ.get(name, default)


GEMINI_KEY = get_secret("GEMINI_KEY") or get_secret("GEMINI_API_KEY")
PEXELS_KEY = get_secret("PEXELS_KEY")


# =========================================================
# 基礎工具
# =========================================================
def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def hash_password(password):
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest()


def safe_filename(name):
    name = re.sub(r'[\\/:*?"<>|]+', "_", str(name or "file"))
    name = re.sub(r"\s+", " ", name).strip()
    return name[:100] or "file"


def load_json(path, default):
    try:
        path = Path(path)
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception:
        return default


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    temp.replace(path)


# =========================================================
# 會員系統
# =========================================================
def load_members():
    members = load_json(MEMBERS_FILE, {})
    return members if isinstance(members, dict) else {}


def save_members(members):
    save_json(MEMBERS_FILE, members)


def ensure_admin():
    members = load_members()
    changed = False
    admin = members.get(ADMIN_USERNAME)

    if not isinstance(admin, dict):
        members[ADMIN_USERNAME] = {
            "username": ADMIN_USERNAME,
            "name": "系統管理員",
            "email": "",
            "password_hash": hash_password(DEFAULT_ADMIN_PASSWORD),
            "created_at": now_text(),
            "expire_date": None,
            "permanent": True,
            "role": "admin",
            "status": "active",
        }
        changed = True
    else:
        defaults = {
            "username": ADMIN_USERNAME,
            "name": "系統管理員",
            "email": "",
            "created_at": now_text(),
            "expire_date": None,
            "permanent": True,
            "role": "admin",
            "status": "active",
        }
        for key, value in defaults.items():
            if key not in admin:
                admin[key] = value
                changed = True
        if admin.get("role") != "admin":
            admin["role"] = "admin"
            changed = True

    if changed:
        save_members(members)


def member_expiration(member):
    if member.get("permanent", True):
        return "永久會員", True

    expire = member.get("expire_date")
    if not expire:
        return "未設定", False

    try:
        expire_date = date.fromisoformat(expire)
    except Exception:
        return "日期錯誤", False

    days = (expire_date - date.today()).days
    if days < 0:
        return f"已到期（{abs(days)} 天）", False

    return f"剩餘 {days} 天", True


def create_member(
    username,
    password,
    name="",
    email="",
    role="member",
    permanent=True,
    days=30,
):
    username = str(username or "").strip()
    password = str(password or "")
    name = str(name or "").strip()
    email = str(email or "").strip()

    if not username or not password:
        return False, "帳號與密碼不能為空。"
    if len(username) < 3:
        return False, "帳號至少 3 個字元。"
    if len(password) < 6:
        return False, "密碼至少 6 個字元。"
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
        return False, "帳號只能使用英數、底線、點或連字號。"

    members = load_members()
    if username in members:
        return False, "帳號已存在。"

    expire_date = None
    if not permanent:
        expire_date = (date.today() + timedelta(days=int(days))).isoformat()

    members[username] = {
        "username": username,
        "name": name or username,
        "email": email,
        "password_hash": hash_password(password),
        "created_at": now_text(),
        "expire_date": expire_date,
        "permanent": bool(permanent),
        "role": role if role in {"member", "vip", "admin"} else "member",
        "status": "active",
    }

    save_members(members)
    return True, "會員建立成功。"


def authenticate(username, password):
    username = str(username or "").strip()
    members = load_members()
    member = members.get(username)

    if not member:
        return None, "帳號不存在。"
    if member.get("status", "active") != "active":
        return None, "此帳號目前已停用。"

    password_hash = hash_password(password)
    if not secrets.compare_digest(
        str(member.get("password_hash", "")),
        password_hash,
    ):
        return None, "密碼錯誤。"

    status, valid = member_expiration(member)
    if not valid:
        return None, f"會員無法使用：{status}"

    return member, ""


def login_user(username, password):
    member, message = authenticate(username, password)
    if not member:
        return False, message

    st.session_state.logged_in = True
    st.session_state.username = member.get("username", "")
    st.session_state.name = member.get("name", member.get("username", ""))
    st.session_state.role = member.get("role", "member")
    st.session_state.member = member
    st.session_state.page = "home"
    return True, "登入成功。"


def logout_user():
    for key, value in DEFAULT_STATE.items():
        st.session_state[key] = value


# =========================================================
# 圖片處理
# =========================================================
def prepare_image(uploaded_file):
    if not uploaded_file:
        raise ValueError("沒有收到圖片。")

    raw = uploaded_file.getvalue()
    if len(raw) > MAX_IMAGE_MB * 1024 * 1024:
        raise ValueError(f"圖片超過 {MAX_IMAGE_MB}MB。")

    try:
        image = Image.open(io.BytesIO(raw))
        image = ImageOps.exif_transpose(image)

        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")

        image.thumbnail(
            (MAX_IMAGE_SIZE, MAX_IMAGE_SIZE),
            Image.Resampling.LANCZOS,
        )

        output = io.BytesIO()

        if image.mode == "RGBA":
            image.save(output, format="PNG", optimize=True)
            mime = "image/png"
        else:
            image.save(output, format="JPEG", quality=92, optimize=True)
            mime = "image/jpeg"

        return output.getvalue(), mime
    except Exception as exc:
        raise ValueError(f"圖片處理失敗：{exc}") from exc


# =========================================================
# Gemini
# =========================================================
def get_gemini_client():
    if not GEMINI_KEY:
        raise RuntimeError(
            "尚未設定 GEMINI_KEY。請在 Streamlit Secrets 加入 GEMINI_KEY。"
        )

    try:
        from google import genai
        return genai.Client(api_key=GEMINI_KEY)
    except ImportError as exc:
        raise RuntimeError(
            "缺少 google-genai，請在 requirements.txt 加入 google-genai。"
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"Gemini 初始化失敗：{exc}") from exc


def ask_gemini(prompt, image_bytes=None, mime_type="image/jpeg"):
    client = get_gemini_client()

    try:
        from google.genai import types

        contents = []

        if image_bytes:
            contents.append(
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type,
                )
            )

        contents.append(prompt)

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
        )

        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("Gemini 沒有返回文字內容。")

        st.session_state.gemini_model = GEMINI_MODEL
        st.session_state.gemini_error = ""
        return text.strip()

    except Exception as exc:
        raw = str(exc)

        if "404" in raw:
            msg = "Gemini 模型不存在或目前 API 不支援此模型（404）。"
        elif "401" in raw:
            msg = "Gemini API Key 無效（401）。"
        elif "403" in raw:
            msg = "Gemini API 權限不足（403）。"
        elif "429" in raw:
            msg = "Gemini 額度或頻率限制（429）。"
        elif "400" in raw:
            msg = "Gemini 請求格式錯誤（400）。"
        else:
            msg = f"Gemini 執行失敗：{raw}"

        st.session_state.gemini_error = msg
        raise RuntimeError(msg) from exc


# =========================================================
# Prompt
# =========================================================
SHOPEE_PROMPT_TEMPLATE = """
請輸出：
1. SEO 商品標題
2. 商品賣點 5 點
3. 完整商品描述
4. 關鍵字
5. 長尾關鍵字
6. FAQ 5 題
不得虛構品牌、規格、認證、效果、折扣或贈品。
"""

TIKTOK_PROMPT_TEMPLATE = """
請輸出：
1. 爆款標題
2. 0~3 秒 Hook
3. 15 秒口播
4. 25 秒口播
5. 貼文文案
6. Hashtags
要求前 3 秒抓住注意力，但不得使用無法證實的誇大承諾。
"""

JIMENG_25_RULES = """
上傳商品圖是商品外觀的唯一主要依據。
必須維持品牌、Logo、包裝、文字、顏色、材質、形狀、比例與細節一致。
不得重新設計包裝、改 Logo、改字、改顏色、增加不存在配件。
可改變的是場景、背景、燈光、鏡頭、景深與商業攝影氛圍。
影片預設 9:16 直式。
"""


def build_master_prompt(product):
    p = {key: str(value or "").strip() for key, value in product.items()}

    return f"""
你是「{APP_NAME}」的核心電商 AI。
請使用繁體中文。
只能根據商品圖片與使用者提供的資料回答；不確定的資訊一律寫「待確認」。

==============================
【商品資料】
==============================
商品名稱：{p.get('name')}
商品分類：{p.get('category')}
售價：{p.get('price')}
成本：{p.get('cost')}
分潤比例：{p.get('commission')}
預估月銷量：{p.get('sales')}
商品評分：{p.get('rating')}
商品連結：{p.get('url')}
商品規格：{p.get('specs')}
目標平台：{p.get('platform')}

==============================
【資料真實性規則】
==============================
1. 不得虛構品牌、Logo、規格、認證、成分、功能、價格、折扣、贈品或效果。
2. 圖片看不清楚的文字請寫「待確認」。
3. 使用者沒有提供的數據，不得自行補數字。
4. 不得把 AI 推測寫成確定事實。
5. 行銷文案可以有吸引力，但不能做無法證實的誇大承諾。

==============================
【任務一：商品辨識與 AI 選品分析】
==============================
請分析：
- 商品名稱與分類
- 圖片可確認資訊
- 待確認資訊
- 外觀、包裝、Logo、文字
- 主要賣點
- 目標客群
- 消費需求
- 市場定位
- 優勢
- 劣勢
- 短影音切入點
- 購買誘因
- 合規提醒
- 選品分數 0~100
- 市場吸引力 0~100
- 視覺吸引力 0~100
- TikTok 潛力 0~100
- 蝦皮潛力 0~100

==============================
【任務二：蝦皮高轉化上架文案】
==============================
{SHOPEE_PROMPT_TEMPLATE}

==============================
【任務三：TikTok 爆款帶貨文案】
==============================
{TIKTOK_PROMPT_TEMPLATE}

==============================
【任務四：即夢 AI 2.5 商業生圖 Prompt】
==============================
{JIMENG_25_RULES}
請輸出：
- 【即夢 AI 2.5 生圖英文 Prompt】
- 【Negative Prompt】
- 【畫面繁體中文文字設計】
- 【9:16 構圖與光影建議】

==============================
【任務五：即夢 AI 2.5 商業影片 Prompt】
==============================
請輸出英文影片 Prompt，必須包含：
Opening、Middle、Camera Motion、Lighting、Product Detail、Ending Freeze。
另外輸出 Negative Prompt。

==============================
【任務六：即夢 AI 2.5 25 秒帶貨分鏡】
==============================
0~3 秒：黃金 Hook
3~8 秒：商品全貌與品質展示
8~15 秒：核心賣點與細節特寫
15~20 秒：使用情境與價值呈現
20~25 秒：CTA 與結尾定格

==============================
【任務七：最終檢查】
==============================
檢查是否有虛構資料、誇大宣稱、錯誤品牌、錯誤規格，
以及是否維持原商品圖片的一致性。

請輸出完整、可直接複製使用的 Markdown 報告。
"""


def detect_category(text):
    text = (text or "").lower()
    groups = {
        "保養美妝": ["洗面", "面膜", "乳液", "精華", "保養", "化妝", "美容", "防曬", "洗髮"],
        "3C": ["手機", "耳機", "充電", "電腦", "鍵盤", "滑鼠", "3c", "平板", "螢幕"],
        "居家生活": ["收納", "清潔", "家居", "廚房", "杯", "居家", "拖把", "用品"],
        "服飾": ["衣服", "褲", "鞋", "帽", "包", "服飾", "外套"],
        "食品": ["食品", "零食", "餅乾", "飲料", "茶", "咖啡", "水果"],
        "汽機車": ["汽車", "機車", "車用", "汽機車", "輪胎"],
    }

    for category, keywords in groups.items():
        if any(keyword in text for keyword in keywords):
            return category

    return "其他"


# =========================================================
# 歷史紀錄
# =========================================================
def save_history(product, result):
    history_id = (
        datetime.now().strftime("%Y%m%d_%H%M%S")
        + "_"
        + secrets.token_hex(3)
    )

    folder = HISTORY_DIR / history_id
    folder.mkdir(parents=True, exist_ok=True)

    product_copy = dict(product)
    product_copy.pop("image_bytes", None)

    save_json(folder / "product.json", product_copy)
    (folder / "result.md").write_text(result, encoding="utf-8")

    return history_id


def list_history(limit=30):
    items = []

    for folder in sorted(HISTORY_DIR.glob("*"), reverse=True):
        if not folder.is_dir():
            continue

        product = load_json(folder / "product.json", {})
        result_file = folder / "result.md"

        items.append(
            {
                "id": folder.name,
                "product": product.get("name", "未命名"),
                "result": result_file.read_text(encoding="utf-8") if result_file.exists() else "",
            }
        )

        if len(items) >= limit:
            break

    return items


# =========================================================
# 短影音工具：Edge TTS / Pexels / FFmpeg
# =========================================================
def tool_available(name):
    return shutil.which(name) is not None


def create_tts(text, output_path):
    if not tool_available("edge-tts"):
        raise RuntimeError(
            "找不到 edge-tts。請在 requirements.txt 加入 edge-tts。"
        )

    subprocess.run(
        [
            "edge-tts",
            "--text", text,
            "--voice", "zh-TW-HsiaoChenNeural",
            "--write-media", str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def download_pexels_video(keyword, output_path):
    if not PEXELS_KEY:
        raise RuntimeError("尚未設定 PEXELS_KEY。")

    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("缺少 requests，請加入 requirements.txt。") from exc

    headers = {"Authorization": PEXELS_KEY}
    params = {
        "query": keyword or "product commercial",
        "orientation": "portrait",
        "per_page": 5,
    }

    response = requests.get(
        "https://api.pexels.com/videos/search",
        headers=headers,
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    videos = response.json().get("videos", [])

    if not videos:
        params["query"] = "abstract product"
        response = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        videos = response.json().get("videos", [])

    if not videos:
        raise RuntimeError("Pexels 找不到適合的影片素材。")

    files = videos[0].get("video_files", [])
    if not files:
        raise RuntimeError("Pexels 影片沒有可下載檔案。")

    portrait = [
        item for item in files
        if item.get("height", 0) >= item.get("width", 0)
    ]
    files = portrait or files
    files.sort(
        key=lambda item: item.get("width", 0) * item.get("height", 0),
        reverse=True,
    )

    video_response = requests.get(
        files[0]["link"],
        timeout=120,
    )
    video_response.raise_for_status()
    output_path.write_bytes(video_response.content)

    if output_path.stat().st_size > MAX_VIDEO_MB * 1024 * 1024:
        raise RuntimeError(f"影片超過 {MAX_VIDEO_MB}MB。")

    return output_path


def create_video(background, audio, output):
    if not tool_available("ffmpeg"):
        raise RuntimeError(
            "找不到 FFmpeg。Streamlit Cloud 需要額外安裝系統套件。"
        )

    command = [
        "ffmpeg",
        "-y",
        "-stream_loop", "-1",
        "-i", str(background),
        "-i", str(audio),
        "-vf",
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-shortest",
        "-movflags", "+faststart",
        str(output),
    ]

    subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )

    return output


# =========================================================
# 登入頁
# =========================================================
def render_login_page():
    st.markdown(
        f'<div class="main-title">🛒 {APP_NAME}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sub-title">永久會員｜管理員｜Gemini 2.5 Flash｜TikTok｜即夢 AI 2.5</div>',
        unsafe_allow_html=True,
    )

    login_tab, register_tab = st.tabs(["🔐 會員登入", "📝 會員註冊"])

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("會員帳號", key="login_username")
            password = st.text_input("會員密碼", type="password", key="login_password")
            submitted = st.form_submit_button("登入", use_container_width=True)

        if submitted:
            ok, message = login_user(username, password)
            if ok:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

        st.info(f"預設管理員帳號：admin / 密碼：{DEFAULT_ADMIN_PASSWORD}")

    with register_tab:
        with st.form("register_form"):
            username = st.text_input("新會員帳號", key="reg_username")
            name = st.text_input("姓名 / 暱稱", key="reg_name")
            email = st.text_input("Email", key="reg_email")
            password = st.text_input("設定密碼", type="password", key="reg_password")
            password2 = st.text_input("再次輸入密碼", type="password", key="reg_password2")
            submitted = st.form_submit_button("註冊永久會員", use_container_width=True)

        if submitted:
            if password != password2:
                st.error("兩次密碼不一致。")
            else:
                ok, message = create_member(
                    username,
                    password,
                    name,
                    email,
                    "member",
                    True,
                )
                if ok:
                    st.success(message)
                else:
                    st.error(message)


# =========================================================
# Sidebar
# =========================================================
def render_sidebar():
    with st.sidebar:
        st.markdown(f"## 🛒 {APP_NAME}")
        st.markdown(
            f"""
            <div class="member-card">
            👤 <b>{st.session_state.name}</b><br>
            帳號：{st.session_state.username}<br>
            權限：{st.session_state.role.upper()}<br>
            會員期限：<b>永久</b>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("🏠 AI 自動化主頁", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()

        if st.button("🎬 短影音自動製作", use_container_width=True):
            st.session_state.page = "video"
            st.rerun()

        if st.button("🗂️ 歷史紀錄", use_container_width=True):
            st.session_state.page = "history"
            st.rerun()

        if st.session_state.role == "admin":
            if st.button("👑 管理員中心", use_container_width=True):
                st.session_state.page = "admin"
                st.rerun()

        st.divider()

        if st.button("🚪 登出", use_container_width=True):
            logout_user()
            st.rerun()


# =========================================================
# AI 主頁
# =========================================================
def render_home_page():
    st.title(f"🛒 {APP_NAME}")
    st.caption(
        "商品圖片 → AI 商品分析 → 蝦皮文案 → TikTok 腳本 → 即夢 AI 2.5 Prompt"
    )

    left, right = st.columns([1, 1])

    with left:
        st.subheader("📷 商品資料")

        uploaded_file = st.file_uploader(
            "上傳商品主圖",
            type=["jpg", "jpeg", "png", "webp"],
            key="product_image",
        )

        if uploaded_file:
            st.image(
                uploaded_file,
                caption="商品圖片預覽",
                use_container_width=True,
            )

        product_name = st.text_input(
            "商品名稱",
            placeholder="例如：極致保濕修護精華液",
        )
        product_price = st.text_input("商品售價", placeholder="例如：499")
        product_cost = st.text_input("商品成本", placeholder="例如：150")
        product_commission = st.text_input("分潤比例 (%)", placeholder="例如：15")
        product_sales = st.text_input("預估月銷量", placeholder="例如：1000")
        product_rating = st.text_input("商品評分", placeholder="例如：4.9")
        product_url = st.text_input("商品連結")
        product_specs = st.text_area(
            "商品規格 / 已知資訊",
            height=140,
            placeholder="例如：容量 30ml、台灣製造……",
        )
        platform = st.selectbox(
            "主要目標平台",
            ["蝦皮購物 + TikTok", "僅蝦皮購物", "僅 TikTok"],
        )

        generate_btn = st.button(
            "🚀 開始 AI 全套生成",
            type="primary",
            use_container_width=True,
        )

    with right:
        st.subheader("🤖 AI 分析與生成結果")

        if generate_btn:
            if not uploaded_file:
                st.warning("請先上傳商品圖片。")
            elif not product_name.strip():
                st.warning("請輸入商品名稱。")
            elif not GEMINI_KEY:
                st.error("尚未設定 GEMINI_KEY，無法呼叫 Gemini。")
            else:
                try:
                    img_bytes, mime_type = prepare_image(uploaded_file)
                    category = detect_category(
                        product_name + " " + product_specs
                    )

                    product = {
                        "name": product_name.strip(),
                        "price": product_price,
                        "cost": product_cost,
                        "commission": product_commission,
                        "sales": product_sales,
                        "rating": product_rating,
                        "url": product_url,
                        "specs": product_specs,
                        "platform": platform,
                        "category": category,
                        "image_bytes": img_bytes,
                        "image_mime": mime_type,
                    }

                    with st.spinner(
                        "Gemini 2.5 Flash 正在分析商品圖片與資料……"
                    ):
                        result = ask_gemini(
                            build_master_prompt(product),
                            img_bytes,
                            mime_type,
                        )

                    history_id = save_history(product, result)
                    st.session_state.result = result
                    st.session_state.last_product = {
                        key: value
                        for key, value in product.items()
                        if key != "image_bytes"
                    }
                    st.session_state.last_product["history_id"] = history_id
                    st.session_state.last_image_bytes = img_bytes
                    st.session_state.last_image_mime = mime_type

                    st.success("AI 分析完成，已保存到歷史紀錄。")

                except Exception as exc:
                    st.error(f"生成失敗：{exc}")

        if st.session_state.result:
            st.markdown(
                '<div class="result-box">',
                unsafe_allow_html=True,
            )
            st.markdown(st.session_state.result)
            st.markdown("</div>", unsafe_allow_html=True)

            safe_name = safe_filename(
                st.session_state.last_product.get("name", "商品")
            )

            st.download_button(
                "📥 下載完整電商報告",
                data=st.session_state.result,
                file_name=f"{safe_name}_AI電商報告.md",
                mime="text/markdown",
                use_container_width=True,
            )


# =========================================================
# 短影音頁
# =========================================================
def render_video_page():
    st.title("🎬 短影音自動製作")
    st.caption(
        "Gemini 生成口播 → Edge TTS → Pexels 背景 → FFmpeg → 9:16 MP4"
    )

    if not PEXELS_KEY:
        st.warning("尚未設定 PEXELS_KEY，因此 Pexels 背景影片功能目前無法使用。")

    if not tool_available("edge-tts"):
        st.warning("目前環境找不到 edge-tts。請確認 requirements.txt 已安裝。")

    if not tool_available("ffmpeg"):
        st.warning("目前環境找不到 FFmpeg。Streamlit Cloud 需另外安裝系統套件。")

    col1, col2 = st.columns(2)

    with col1:
        default_topic = st.session_state.last_product.get("name", "")
        topic = st.text_input("影片主題 / 商品名稱", value=default_topic)
        script = st.text_area(
            "口播文案（留空＝Gemini 自動生成）",
            height=180,
        )

    with col2:
        duration = st.selectbox("影片版本", ["15 秒", "25 秒"])
        st.info(
            "輸出格式：MP4\n\n"
            "尺寸：1080 × 1920\n\n"
            "比例：9:16\n\n"
            "語音：zh-TW-HsiaoChenNeural"
        )

    if st.button(
        "🎬 開始製作影片",
        type="primary",
        use_container_width=True,
    ):
        if not topic.strip():
            st.error("請輸入影片主題。")
            return

        if not GEMINI_KEY and not script.strip():
            st.error("未設定 GEMINI_KEY，且你沒有手動輸入口播。")
            return

        if not PEXELS_KEY:
            st.error("請先設定 PEXELS_KEY。")
            return

        work = MEDIA_DIR / ("video_" + secrets.token_hex(5))
        work.mkdir(parents=True, exist_ok=True)

        try:
            if not script.strip():
                prompt = f"""
請為商品「{topic}」寫一段繁體中文 {duration} TikTok 短影音口播。
前 3 秒必須有 Hook。
不要虛構價格、功能、效果、品牌或優惠。
只輸出口播內容，不要標題，不要 Markdown。
"""
                with st.spinner("Gemini 正在生成短影音口播……"):
                    script = ask_gemini(prompt)

            st.write("📝 口播文案")
            st.info(script)

            audio_path = work / "audio.mp3"
            background_path = work / "background.mp4"
            output_path = work / "output.mp4"

            with st.status("正在製作影片……", expanded=True) as status:
                status.write("🎙️ 1/3 生成語音")
                create_tts(script, audio_path)

                status.write("🎥 2/3 下載直式背景影片")
                keyword = topic.strip().split()[0] if topic.strip() else "product"
                download_pexels_video(keyword, background_path)

                status.write("⚙️ 3/3 FFmpeg 合成 9:16")
                create_video(background_path, audio_path, output_path)
                status.update(
                    label="🎉 影片完成！",
                    state="complete",
                )

            video_bytes = output_path.read_bytes()
            st.session_state.last_video_bytes = video_bytes
            st.session_state.last_video_name = safe_filename(topic) + ".mp4"
            st.session_state.last_video_mime = "video/mp4"

            st.video(video_bytes)
            st.download_button(
                "⬇️ 下載 MP4",
                data=video_bytes,
                file_name=st.session_state.last_video_name,
                mime="video/mp4",
                use_container_width=True,
            )

        except Exception as exc:
            st.error(f"影片製作失敗：{exc}")


# =========================================================
# 歷史紀錄頁
# =========================================================
def render_history_page():
    st.title("🗂️ 歷史紀錄")
    st.caption("最近 30 筆 AI 商品分析紀錄")

    items = list_history(30)

    if not items:
        st.info("目前沒有歷史紀錄。")
        return

    for item in items:
        with st.expander(
            f"📦 {item['product']}｜{item['id']}"
        ):
            st.markdown(item["result"])
            st.download_button(
                "📥 下載此報告",
                data=item["result"],
                file_name=(
                    f"{safe_filename(item['product'])}_"
                    f"{item['id']}.md"
                ),
                mime="text/markdown",
                key="history_dl_" + item["id"],
            )


# =========================================================
# 管理員中心
# =========================================================
def render_admin_page():
    st.title("👑 管理員中心")
    st.caption("永久會員制：沒有到期日，可手動停用 / 啟用會員。")

    members = load_members()

    total = len(members)
    active = sum(
        1 for member in members.values()
        if member.get("status") == "active"
    )
    admin_count = sum(
        1 for member in members.values()
        if member.get("role") == "admin"
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("會員總數", total)
    col2.metric("啟用會員", active)
    col3.metric("管理員", admin_count)

    st.divider()
    st.subheader("➕ 建立永久會員")

    with st.form("admin_create_member"):
        left, right = st.columns(2)

        with left:
            username = st.text_input("會員帳號")
            name = st.text_input("姓名 / 暱稱")

        with right:
            password = st.text_input("會員密碼", type="password")
            email = st.text_input("Email")

        role = st.selectbox(
            "會員等級",
            ["member", "vip", "admin"],
            format_func=lambda value: {
                "member": "一般會員",
                "vip": "VIP 會員",
                "admin": "管理員",
            }[value],
        )

        submitted = st.form_submit_button(
            "建立永久會員",
            use_container_width=True,
        )

    if submitted:
        ok, message = create_member(
            username,
            password,
            name,
            email,
            role,
            True,
        )

        if ok:
            st.success(message)
            st.rerun()
        else:
            st.error(message)

    st.divider()
    st.subheader("👥 會員清單")

    members = load_members()

    for index, (username, member) in enumerate(members.items()):
        role = member.get("role", "member")
        name = member.get("name", username)

        with st.expander(
            f"👤 {username}｜{name}｜{role.upper()}"
        ):
            st.write(f"Email：{member.get('email', '無')}")
            st.write(f"狀態：{member.get('status', 'active')}")
            st.write(f"建立時間：{member.get('created_at', '')}")
            st.write("會員期限：永久")

            if username != ADMIN_USERNAME:
                is_active = member.get("status") == "active"
                label = "停用帳號" if is_active else "啟用帳號"

                if st.button(
                    label,
                    key=f"toggle_{index}_{username}",
                ):
                    fresh_members = load_members()
                    fresh_members[username]["status"] = (
                        "disabled" if is_active else "active"
                    )
                    save_members(fresh_members)
                    st.success("會員狀態已更新。")
                    st.rerun()


# =========================================================
# Main
# =========================================================
def main():
    ensure_admin()

    if not st.session_state.logged_in:
        render_login_page()
        return

    # 每次重新執行都重新檢查會員狀態。
    current = load_members().get(st.session_state.username)

    if not current or current.get("status") != "active":
        logout_user()
        st.error("帳號目前無法使用，請重新登入。")
        return

    status, valid = member_expiration(current)
    if not valid:
        logout_user()
        st.error(f"會員資格無法使用：{status}")
        return

    st.session_state.member = current
    st.session_state.name = current.get(
        "name",
        current.get("username", ""),
    )
    st.session_state.role = current.get("role", "member")

    render_sidebar()

    if st.session_state.page == "admin" and st.session_state.role == "admin":
        render_admin_page()
    elif st.session_state.page == "video":
        render_video_page()
    elif st.session_state.page == "history":
        render_history_page()
    else:
        render_home_page()


if __name__ == "__main__":
    main()
