import os
import io
import re
import json
import uuid
import shutil
import hashlib
import secrets
import zipfile
import subprocess
from pathlib import Path
from datetime import datetime, date, timedelta

import streamlit as st
from PIL import Image, ImageOps

# =========================================================
# AI 蝦皮全自動化 2.5 PRO
# =========================================================
APP_NAME = "AI 蝦皮全自動化 2.5 PRO"

DATA_DIR = Path("data")
HISTORY_DIR = Path("history")
MEDIA_DIR = DATA_DIR / "media"
MEMBERS_FILE = DATA_DIR / "members.json"

DATA_DIR.mkdir(exist_ok=True)
HISTORY_DIR.mkdir(exist_ok=True)
MEDIA_DIR.mkdir(exist_ok=True)

MAX_IMAGE_SIZE = 1600
MAX_IMAGE_MB = 20
MAX_VIDEO_MB = 300

ADMIN_USERNAME = "admin"
DEFAULT_MEMBER_DAYS = 30

GEMINI_MODEL = "gemini-2.5-flash"

VIDEO_MIME_MAP = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
}

# =========================================================
# Streamlit 設定
# =========================================================
st.set_page_config(
    page_title=APP_NAME,
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================================================
# CSS
# =========================================================
st.markdown(
    """
<style>
.main-title {
    font-size: 36px;
    font-weight: 800;
}
.sub-title {
    color: #777;
    margin-bottom: 20px;
}
.card {
    padding: 20px;
    border-radius: 16px;
    border: 1px solid rgba(128,128,128,.25);
    margin-bottom: 15px;
}
.small {
    color: #777;
    font-size: 14px;
}
.success-box {
    padding: 15px;
    border-radius: 12px;
    border: 1px solid #35a66f;
}
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
    "member": {},
    "page": "Dashboard",
    "analysis_result": {},
    "last_product": {},
    "last_image_bytes": None,
    "last_image_name": "",
    "last_video_bytes": None,
    "last_video_name": "",
    "last_video_mime": "video/mp4",
    "last_zip_bytes": None,
    "last_zip_name": "",
    "last_history_id": "",
    "gemini_model": GEMINI_MODEL,
    "gemini_error": "",
    "generated": False,
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# Secrets / API
# =========================================================
def get_secret(name):
    try:
        value = st.secrets.get(name, "")
        if value:
            return str(value)
    except Exception:
        pass

    return os.environ.get(name, "")


GEMINI_KEY = get_secret("GEMINI_KEY") or get_secret("GEMINI_API_KEY")
PEXELS_KEY = get_secret("PEXELS_KEY")


# =========================================================
# 基礎工具
# =========================================================
def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today():
    return date.today()


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def safe_filename(name):
    name = str(name or "file")
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    return name[:100]


def load_json(path, default):
    try:
        if not path.exists():
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")

    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    temp.replace(path)


def load_members():
    members = load_json(MEMBERS_FILE, {})

    if not isinstance(members, dict):
        members = {}

    return members


def save_members(members):
    save_json(MEMBERS_FILE, members)


# =========================================================
# 初始化 Admin
# =========================================================
def ensure_admin():
    members = load_members()

    if ADMIN_USERNAME not in members:
        members[ADMIN_USERNAME] = {
            "username": ADMIN_USERNAME,
            "password_hash": hash_password("admin123"),
            "created_at": now_text(),
            "expire_date": None,
            "permanent": True,
            "role": "admin",
            "status": "active",
        }

        save_members(members)


ensure_admin()


# =========================================================
# 會員
# =========================================================
def member_expiration(member):
    if member.get("permanent"):
        return "永久會員", True

    expire = member.get("expire_date")

    if not expire:
        return "未設定", False

    try:
        expire_date = date.fromisoformat(expire)
    except Exception:
        return "日期錯誤", False

    days = (expire_date - today()).days

    if days < 0:
        return f"已到期 ({abs(days)} 天)", False

    if days <= 7:
        return f"即將到期（剩 {days} 天）", True

    return f"正常（剩 {days} 天）", True


def create_member(username, password, days=30, permanent=False, role="member"):
    username = username.strip()

    if not username or not password:
        return False, "帳號與密碼不能為空。"

    members = load_members()

    if username in members:
        return False, "帳號已存在。"

    expire_date = None

    if not permanent:
        expire_date = (today() + timedelta(days=int(days))).isoformat()

    members[username] = {
        "username": username,
        "password_hash": hash_password(password),
        "created_at": now_text(),
        "expire_date": expire_date,
        "permanent": permanent,
        "role": role,
        "status": "active",
    }

    save_members(members)

    return True, "會員建立成功。"


def authenticate(username, password):
    members = load_members()

    member = members.get(username)

    if not member:
        return None, "帳號不存在。"

    if member.get("status") != "active":
        return None, "此帳號目前已停用。"

    if member.get("password_hash") != hash_password(password):
        return None, "密碼錯誤。"

    status, valid = member_expiration(member)

    if not valid:
        return None, f"會員已無法使用：{status}"

    return member, ""


# =========================================================
# Gemini
# =========================================================
def get_gemini_client():
    if not GEMINI_KEY:
        return None

    try:
        from google import genai

        return genai.Client(api_key=GEMINI_KEY)
    except Exception as e:
        st.session_state.gemini_error = str(e)
        return None


def clean_json_text(text):
    if not text:
        return ""

    text = text.strip()

    text = re.sub(r"^```json", "", text, flags=re.I)
    text = re.sub(r"^```", "", text)
    text = re.sub(r"```$", "", text)

    return text.strip()


def gemini_text(prompt, image_bytes=None, mime_type="image/jpeg"):
    client = get_gemini_client()

    if not client:
        raise RuntimeError(
            "找不到 Gemini API Key。請在 Streamlit Secrets 設定 GEMINI_KEY。"
        )

    try:
        contents = []

        if image_bytes:
            from google.genai import types

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
            raise RuntimeError("Gemini 沒有返回內容。")

        st.session_state.gemini_model = GEMINI_MODEL

        return text

    except Exception as e:
        error = str(e)

        if "404" in error:
            error = "Gemini 模型不存在或目前 API 不支援此模型（404）。"
        elif "401" in error:
            error = "Gemini API Key 無效（401）。"
        elif "403" in error:
            error = "Gemini API 權限不足（403）。"
        elif "429" in error:
            error = "Gemini API 額度或頻率限制（429）。"
        elif "400" in error:
            error = "Gemini 請求格式錯誤（400）。"

        st.session_state.gemini_error = error
        raise RuntimeError(error)


def gemini_json(prompt, image_bytes=None, mime_type="image/jpeg"):
    text = gemini_text(
        prompt,
        image_bytes=image_bytes,
        mime_type=mime_type,
    )

    cleaned = clean_json_text(text)

    try:
        return json.loads(cleaned)
    except Exception:
        # 嘗試找 JSON 區塊
        match = re.search(r"\{.*\}", cleaned, re.S)

        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass

        raise RuntimeError("Gemini 回傳內容不是有效 JSON。")


# =========================================================
# 圖片處理
# =========================================================
def process_image(uploaded_file):
    if not uploaded_file:
        return None, None

    raw = uploaded_file.getvalue()

    if len(raw) > MAX_IMAGE_MB * 1024 * 1024:
        raise ValueError(f"圖片超過 {MAX_IMAGE_MB}MB。")

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
        image.save(output, format="PNG")
        mime = "image/png"
    else:
        image.save(
            output,
            format="JPEG",
            quality=92,
        )
        mime = "image/jpeg"

    return output.getvalue(), mime


# =========================================================
# 商品分類
# =========================================================
def detect_category(text):
    text = (text or "").lower()

    categories = {
        "保養美妝": [
            "洗面",
            "面膜",
            "乳液",
            "精華",
            "保養",
            "化妝",
            "美容",
            "防曬",
        ],
        "3C": [
            "手機",
            "耳機",
            "充電",
            "電腦",
            "鍵盤",
            "滑鼠",
            "3c",
            "平板",
        ],
        "居家生活": [
            "收納",
            "清潔",
            "家居",
            "廚房",
            "杯",
            "居家",
        ],
        "服飾": [
            "衣服",
            "褲",
            "鞋",
            "帽",
            "包",
            "服飾",
        ],
        "食品": [
            "食品",
            "零食",
            "餅乾",
            "飲料",
            "茶",
            "咖啡",
        ],
        "汽機車": [
            "汽車",
            "機車",
            "車用",
            "汽機車",
        ],
    }

    for category, keywords in categories.items():
        if any(keyword in text for keyword in keywords):
            return category

    return "其他"


# =========================================================
# Gemini 完整商品分析
# =========================================================
def run_product_ai(product):
    prompt = f"""
你現在是「AI 蝦皮全自動化 2.5 PRO」電商 AI。

請分析以下商品，並產生完整電商行銷資料。

商品資料：
商品名稱：{product['name']}
分類：{product['category']}
價格：{product['price']}
商品特色：{product['features']}
商品賣點：{product['selling_points']}

重要規則：

1. 如果有商品圖片，圖片是商品外觀的主要依據。
2. 不得虛構圖片中不存在的品牌、Logo、文字、功能、配件。
3. 不得自行修改商品外觀。
4. 不得虛構價格、折扣、贈品。
5. 如果資訊不足，明確標示「未確認」。
6. 所有內容使用繁體中文。
7. 蝦皮標題要自然，不要塞滿無意義關鍵字。
8. TikTok 必須前 3 秒有 Hook。
9. 即夢 Prompt 必須保護商品一致性。
10. 影片預設 9:16。

請只回傳 JSON：

{{
  "product_analysis": {{
    "basic": "",
    "appearance": "",
    "material": "",
    "color": "",
    "packaging": "",
    "logo_text": "",
    "features": []
  }},
  "selling_points": [],
  "target_audience": [],
  "consumer_needs": [],
  "market_positioning": "",
  "purchase_reasons": [],
  "advantages": [],
  "disadvantages": [],
  "risks": [],
  "selection_score": 0,
  "market_attractiveness": 0,
  "visual_attractiveness": 0,
  "short_video_score": 0,
  "tiktok_score": 0,
  "shopee_score": 0,
  "selling_direction": "",
  "shopee": {{
    "title": "",
    "description": "",
    "selling_points": [],
    "keywords": [],
    "long_tail_keywords": []
  }},
  "tiktok": {{
    "title": "",
    "hook": "",
    "copy": "",
    "hashtags": [],
    "script_15": "",
    "script_30": ""
  }},
  "jimeng": {{
    "image_prompt": "",
    "cover_prompt": "",
    "video_prompt_15": "",
    "video_prompt_30": ""
  }}
}}
"""

    return gemini_json(
        prompt,
        image_bytes=product.get("image_bytes"),
        mime_type=product.get("image_mime", "image/jpeg"),
    )


# =========================================================
# 本機 fallback
# =========================================================
def local_fallback(product):
    category = product["category"]

    name = product["name"]

    return {
        "product_analysis": {
            "basic": f"{name}，分類：{category}",
            "appearance": "請以商品原圖為準",
            "material": "未確認",
            "color": "請以商品原圖為準",
            "packaging": "請以商品原圖為準",
            "logo_text": "請以商品原圖為準",
            "features": [product["features"]],
        },
        "selling_points": [product["selling_points"]],
        "target_audience": ["對此類商品有需求的消費者"],
        "consumer_needs": ["便利性", "實用性", "商品特色"],
        "market_positioning": "實用型電商商品",
        "purchase_reasons": ["商品特色", "使用便利"],
        "advantages": ["適合短影音展示"],
        "disadvantages": ["缺少實際市場數據"],
        "risks": ["AI 分析不能取代實際市場測試"],
        "selection_score": 75,
        "market_attractiveness": 75,
        "visual_attractiveness": 75,
        "short_video_score": 80,
        "tiktok_score": 78,
        "shopee_score": 80,
        "selling_direction": "以商品特色、實際使用情境與視覺展示為主要行銷方向。",
        "shopee": {
            "title": f"{name}｜高質感實用好物",
            "description": f"✨ {name}\n\n{product['features']}\n\n推薦給需要此類商品的消費者。",
            "selling_points": [
                product["selling_points"],
                product["features"],
            ],
            "keywords": [name, category],
            "long_tail_keywords": [
                f"{name}推薦",
                f"{category}好物",
            ],
        },
        "tiktok": {
            "title": f"{name}實用好物推薦",
            "hook": f"如果你正在找 {name}，這個一定要看！",
            "copy": f"今天分享一個實用好物：{name}。",
            "hashtags": [
                "#TikTok",
                "#好物推薦",
                "#生活好物",
                "#蝦皮",
            ],
            "script_15": (
                f"前3秒：你還在找好用的{category}嗎？\n"
                f"接著展示{name}。\n"
                f"快速介紹商品特色。\n"
                f"最後：想了解更多可以到賣場看看。"
            ),
            "script_30": (
                f"開場：你還在找實用的{category}嗎？\n"
                f"展示：這款{name}。\n"
                f"特色：{product['features']}。\n"
                f"賣點：{product['selling_points']}。\n"
                f"結尾：如果剛好有需求，可以進一步了解。"
            ),
        },
        "jimeng": {
            "image_prompt": (
                f"使用上傳商品圖片作為唯一商品外觀依據，"
                f"保持{name}原始品牌、Logo、包裝、顏色、"
                f"材質、比例、形狀與文字完全一致。"
                f"高級商業商品攝影，乾淨背景，自然光，"
                f"9:16 電商視覺。禁止修改商品。"
            ),
            "cover_prompt": (
                f"以原商品圖片為唯一商品依據，製作高級電商封面，"
                f"商品外觀完全保持原樣，不修改Logo、文字、顏色、"
                f"包裝與比例，9:16。"
            ),
            "video_prompt_15": (
                f"9:16 直式15秒商品廣告。"
                f"使用原商品圖片作為唯一商品依據。"
                f"商品外觀完全保持一致。"
                f"高級商業攝影、自然光、慢速推鏡、"
                f"商品特寫、輕微環繞。禁止改品牌、Logo、"
                f"包裝、顏色、比例、文字或增加不存在的物件。"
            ),
            "video_prompt_30": (
                f"9:16 直式30秒商品廣告。"
                f"以原商品圖片為唯一依據。"
                f"開場商品特寫，中段展示商品細節與使用情境，"
                f"結尾高級產品英雄鏡頭。"
                f"保持商品外觀、品牌、Logo、包裝、文字、"
                f"顏色、材質與比例完全一致。"
                f"禁止虛構商品資訊。"
            ),
        },
    }


# =========================================================
# Edge TTS
# =========================================================
def edge_tts_available():
    return shutil.which("edge-tts") is not None


def create_tts(text, output_path):
    if not edge_tts_available():
        raise RuntimeError(
            "找不到 edge-tts。請確認 requirements.txt 已安裝 edge-tts。"
        )

    subprocess.run(
        [
            "edge-tts",
            "--text",
            text,
            "--voice",
            "zh-TW-HsiaoChenNeural",
            "--write-media",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


# =========================================================
# Pexels
# =========================================================
def download_pexels_video(keyword, output_path):
    if not PEXELS_KEY:
        raise RuntimeError("未設定 PEXELS_KEY。")

    import requests

    headers = {
        "Authorization": PEXELS_KEY,
    }

    url = "https://api.pexels.com/videos/search"

    params = {
        "query": keyword,
        "orientation": "portrait",
        "per_page": 5,
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    videos = data.get("videos", [])

    if not videos:
        params["query"] = "product commercial"

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=30,
        )

        response.raise_for_status()

        videos = response.json().get("videos", [])

    if not videos:
        raise RuntimeError("Pexels 找不到適合的影片素材。")

    video_files = videos[0].get("video_files", [])

    if not video_files:
        raise RuntimeError("Pexels 影片沒有可下載檔案。")

    # 優先挑直式/高畫質
    video_files = sorted(
        video_files,
        key=lambda x: (
            x.get("width", 0) * x.get("height", 0)
        ),
        reverse=True,
    )

    video_url = video_files[0]["link"]

    video_response = requests.get(
        video_url,
        timeout=120,
    )

    video_response.raise_for_status()

    output_path.write_bytes(video_response.content)

    return output_path


# =========================================================
# FFmpeg
# =========================================================
def ffmpeg_available():
    return shutil.which("ffmpeg") is not None


def create_video(background, audio, output):
    if not ffmpeg_available():
        raise RuntimeError(
            "找不到 FFmpeg。Streamlit Cloud 需要另外設定 FFmpeg。"
        )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(background),
        "-i",
        str(audio),
        "-vf",
        (
            "scale=1080:1920:"
            "force_original_aspect_ratio=increase,"
            "crop=1080:1920"
        ),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-shortest",
        "-movflags",
        "+faststart",
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

    # bytes 不寫進 JSON
    product_copy.pop("image_bytes", None)

    save_json(
        folder / "product.json",
        product_copy,
    )

    save_json(
        folder / "ai_result.json",
        result,
    )

    if st.session_state.get("last_image_bytes"):
        with open(folder / "product_image.jpg", "wb") as f:
            f.write(st.session_state.last_image_bytes)

    st.session_state.last_history_id = history_id

    return history_id


def list_history():
    if not HISTORY_DIR.exists():
        return []

    folders = [
        p for p in HISTORY_DIR.iterdir()
        if p.is_dir()
    ]

    return sorted(
        folders,
        key=lambda p: p.name,
        reverse=True,
    )


# =========================================================
# ZIP
# =========================================================
def create_zip(product, result):
    memory = io.BytesIO()

    with zipfile.ZipFile(
        memory,
        "w",
        zipfile.ZIP_DEFLATED,
    ) as z:

        product_copy = dict(product)
        product_copy.pop("image_bytes", None)

        z.writestr(
            "商品資料.json",
            json.dumps(
                product_copy,
                ensure_ascii=False,
                indent=2,
            ),
        )

        z.writestr(
            "AI分析結果.json",
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            ),
        )

        shopee = result.get("shopee", {})

        shopee_text = f"""
商品標題
{shopee.get('title', '')}

商品描述
{shopee.get('description', '')}

商品賣點
{chr(10).join('- ' + str(x) for x in shopee.get('selling_points', []))}

SEO關鍵字
{', '.join(shopee.get('keywords', []))}

長尾關鍵字
{', '.join(shopee.get('long_tail_keywords', []))}
"""

        z.writestr(
            "蝦皮文案.txt",
            shopee_text.strip(),
        )

        tiktok = result.get("tiktok", {})

        tiktok_text = f"""
TikTok 標題
{tiktok.get('title', '')}

Hook
{tiktok.get('hook', '')}

TikTok 文案
{tiktok.get('copy', '')}

15秒腳本
{tiktok.get('script_15', '')}

30秒腳本
{tiktok.get('script_30', '')}

Hashtag
{' '.join(tiktok.get('hashtags', []))}
"""

        z.writestr(
            "TikTok素材.txt",
            tiktok_text.strip(),
        )

        jimeng = result.get("jimeng", {})

        z.writestr(
            "即夢圖片Prompt.txt",
            jimeng.get("image_prompt", ""),
        )

        z.writestr(
            "即夢影片15秒Prompt.txt",
            jimeng.get("video_prompt_15", ""),
        )

        z.writestr(
            "即夢影片30秒Prompt.txt",
            jimeng.get("video_prompt_30", ""),
        )

        if st.session_state.get("last_image_bytes"):
            z.writestr(
                "商品圖片.jpg",
                st.session_state.last_image_bytes,
            )

        if st.session_state.get("last_video_bytes"):
            z.writestr(
                st.session_state.last_video_name or "短影音.mp4",
                st.session_state.last_video_bytes,
            )

    memory.seek(0)

    return memory.getvalue()


# =========================================================
# Login
# =========================================================
def login_page():
    st.markdown(
        '<div class="main-title">🛒 AI 蝦皮全自動化 2.5 PRO</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="sub-title">AI 電商全自動內容生成中心</div>',
        unsafe_allow_html=True,
    )

    tab1, tab2 = st.tabs(
        ["🔐 登入", "📝 註冊"]
    )

    with tab1:
        username = st.text_input(
            "會員帳號",
            key="login_username",
        )

        password = st.text_input(
            "會員密碼",
            type="password",
            key="login_password",
        )

        if st.button(
            "登入系統",
            type="primary",
            use_container_width=True,
        ):
            member, error = authenticate(
                username,
                password,
            )

            if member:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.member = member
                st.session_state.page = "Dashboard"

                st.success("登入成功。")
                st.rerun()
            else:
                st.error(error)

        st.caption(
            "系統管理員預設帳號：admin / admin123"
        )

    with tab2:
        new_username = st.text_input(
            "建立帳號",
            key="register_username",
        )

        new_password = st.text_input(
            "建立密碼",
            type="password",
            key="register_password",
        )

        confirm_password = st.text_input(
            "確認密碼",
            type="password",
            key="register_confirm",
        )

        if st.button(
            "建立會員",
            use_container_width=True,
        ):
            if new_password != confirm_password:
                st.error("兩次密碼不一致。")
            else:
                ok, msg = create_member(
                    new_username,
                    new_password,
                    days=DEFAULT_MEMBER_DAYS,
                )

                if ok:
                    st.success(
                        "註冊成功，預設為30天會員。"
                    )
                else:
                    st.error(msg)


# =========================================================
# Dashboard
# =========================================================
def dashboard():
    member = st.session_state.member

    status, valid = member_expiration(member)

    st.title("🏠 Dashboard")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "會員",
            member.get("username", ""),
        )

    with c2:
        st.metric(
            "會員狀態",
            "正常" if valid else "到期",
        )

    with c3:
        st.metric(
            "期限",
            status,
        )

    with c4:
        st.metric(
            "AI",
            "Gemini",
        )

    st.divider()

    st.subheader("🚀 全自動電商流程")

    st.markdown(
        """
        **商品圖片＋商品資料**
        
        ↓
        
        🤖 Gemini 商品理解
        
        ↓
        
        📊 AI 選品
        
        ↓
        
        🛒 蝦皮文案
        
        ↓
        
        🎵 TikTok 文案＋腳本
        
        ↓
        
        🎬 即夢 AI 2.5 Prompt
        
        ↓
        
        🎙️ AI 配音＋🎥影片素材＋⚙️ FFmpeg
        
        ↓
        
        📦 完整素材 ZIP
        """
    )

    if st.session_state.get("generated"):
        st.success("目前已有一組生成結果，可以到素材下載查看。")


# =========================================================
# 全自動商品中心
# =========================================================
def product_center():
    st.title("🤖 AI 商品全自動中心")

    st.write(
        "上傳商品圖片並輸入基本資料後，系統會一次產生完整電商素材。"
    )

    col1, col2 = st.columns([1, 1])

    with col1:
        uploaded = st.file_uploader(
            "📷 商品圖片",
            type=["jpg", "jpeg", "png", "webp"],
        )

        if uploaded:
            try:
                image_bytes, image_mime = process_image(
                    uploaded
                )

                st.session_state.last_image_bytes = image_bytes
                st.session_state.last_image_name = uploaded.name

                st.image(
                    image_bytes,
                    caption="商品圖片",
                    use_container_width=True,
                )

            except Exception as e:
                st.error(str(e))

    with col2:
        product_name = st.text_input(
            "商品名稱",
            placeholder="例如：UNO 洗面乳",
        )

        category_input = st.text_input(
            "商品分類",
            placeholder="例如：保養美妝",
        )

        price = st.number_input(
            "商品價格",
            min_value=0.0,
            value=999.0,
            step=1.0,
        )

        features = st.text_area(
            "商品特色",
            placeholder="輸入商品特色",
        )

        selling_points = st.text_area(
            "商品賣點",
            placeholder="輸入你知道的商品賣點",
        )

    if not category_input:
        category_input = detect_category(
            product_name
            + " "
            + features
        )

    st.info(
        f"AI 判斷分類：**{category_input}**"
    )

    if st.button(
        "🚀 一鍵全自動生成",
        type="primary",
        use_container_width=True,
    ):

        if not product_name:
            st.error("請輸入商品名稱。")
            return

        product = {
            "name": product_name,
            "category": category_input,
            "price": price,
            "features": features,
            "selling_points": selling_points,
            "created_at": now_text(),
            "image_bytes": st.session_state.last_image_bytes,
            "image_mime": "image/jpeg",
        }

        progress = st.status(
            "🚀 全自動製作中...",
            expanded=True,
        )

        try:
            # ---------------------------------------------
            # 1. AI 商品分析
            # ---------------------------------------------
            progress.write(
                "🤖 1/8 Gemini 正在分析商品..."
            )

            if GEMINI_KEY:
                result = run_product_ai(product)
            else:
                progress.write(
                    "⚠️ 未設定 Gemini，使用本機備援模式。"
                )
                result = local_fallback(product)

            # ---------------------------------------------
            # 2. 儲存
            # ---------------------------------------------
            progress.write(
                "📊 2/8 完成 AI 選品與市場分析..."
            )

            st.session_state.last_product = product
            st.session_state.analysis_result = result

            # ---------------------------------------------
            # 3. 歷史
            # ---------------------------------------------
            progress.write(
                "📚 3/8 保存歷史紀錄..."
            )

            history_id = save_history(
                product,
                result,
            )

            # ---------------------------------------------
            # 4. TTS
            # ---------------------------------------------
            progress.write(
                "🎙️ 4/8 建立 AI 口播..."
            )

            tiktok = result.get("tiktok", {})

            script = tiktok.get(
                "script_15",
                "",
            )

            work_dir = MEDIA_DIR / history_id
            work_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            audio_path = work_dir / "audio.mp3"

            if edge_tts_available() and script:
                try:
                    create_tts(
                        script,
                        audio_path,
                    )
                except Exception as e:
                    progress.write(
                        f"⚠️ Edge TTS 失敗：{e}"
                    )

            # ---------------------------------------------
            # 5. Pexels
            # ---------------------------------------------
            progress.write(
                "🎥 5/8 搜尋直式影片素材..."
            )

            background_path = work_dir / "background.mp4"

            keyword = (
                category_input
                or "product"
            )

            if PEXELS_KEY and audio_path.exists():
                try:
                    download_pexels_video(
                        keyword,
                        background_path,
                    )
                except Exception as e:
                    progress.write(
                        f"⚠️ Pexels 素材失敗：{e}"
                    )

            # ---------------------------------------------
            # 6. FFmpeg
            # ---------------------------------------------
            progress.write(
                "⚙️ 6/8 FFmpeg 自動合成短影音..."
            )

            output_path = work_dir / "output.mp4"

            if (
                background_path.exists()
                and audio_path.exists()
                and ffmpeg_available()
            ):
                try:
                    create_video(
                        background_path,
                        audio_path,
                        output_path,
                    )

                    video_bytes = output_path.read_bytes()

                    st.session_state.last_video_bytes = (
                        video_bytes
                    )

                    st.session_state.last_video_name = (
                        "AI短影音_9x16.mp4"
                    )

                    st.session_state.last_video_mime = (
                        "video/mp4"
                    )

                except Exception as e:
                    progress.write(
                        f"⚠️ FFmpeg 影片生成失敗：{e}"
                    )

            # ---------------------------------------------
            # 7. ZIP
            # ---------------------------------------------
            progress.write(
                "📦 7/8 整理完整素材包..."
            )

            zip_bytes = create_zip(
                product,
                result,
            )

            st.session_state.last_zip_bytes = zip_bytes

            st.session_state.last_zip_name = (
                f"{safe_filename(product_name)}_完整素材包.zip"
            )

            # ---------------------------------------------
            # 8. 完成
            # ---------------------------------------------
            progress.write(
                "✅ 8/8 全部完成！"
            )

            st.session_state.generated = True

            progress.update(
                label="🎉 全自動生成完成！",
                state="complete",
            )

            st.success(
                "完整電商素材已產生。"
            )

        except Exception as e:
            progress.update(
                label="❌ 生成失敗",
                state="error",
            )

            st.error(
                f"錯誤：{e}"
            )

            if st.session_state.gemini_error:
                st.error(
                    f"Gemini：{st.session_state.gemini_error}"
                )

    if st.session_state.get("analysis_result"):
        show_results()


# =========================================================
# 結果
# =========================================================
def show_results():
    result = st.session_state.analysis_result

    st.divider()

    st.header("🎉 AI 全自動生成結果")

    tabs = st.tabs(
        [
            "📊 商品分析",
            "📈 AI選品",
            "🛒 蝦皮",
            "🎵 TikTok",
            "🎬 即夢2.5",
            "🎥 影片",
            "📦 素材",
        ]
    )

    # 商品分析
    with tabs[0]:
        analysis = result.get(
            "product_analysis",
            {},
        )

        st.subheader("商品基本分析")

        st.write(
            analysis.get("basic", "")
        )

        st.write(
            f"外觀：{analysis.get('appearance', '')}"
        )

        st.write(
            f"材質：{analysis.get('material', '')}"
        )

        st.write(
            f"顏色：{analysis.get('color', '')}"
        )

        st.write(
            f"包裝：{analysis.get('packaging', '')}"
        )

        st.write(
            f"Logo／文字：{analysis.get('logo_text', '')}"
        )

        st.subheader("商品特色")

        for item in analysis.get(
            "features",
            [],
        ):
            st.write(f"- {item}")

        st.subheader("主要賣點")

        for item in result.get(
            "selling_points",
            [],
        ):
            st.write(f"🔥 {item}")

    # 選品
    with tabs[1]:
        scores = {
            "AI選品總分": result.get("selection_score", 0),
            "市場吸引力": result.get("market_attractiveness", 0),
            "視覺吸引力": result.get("visual_attractiveness", 0),
            "短影音": result.get("short_video_score", 0),
            "TikTok": result.get("tiktok_score", 0),
            "蝦皮": result.get("shopee_score", 0),
        }

        cols = st.columns(3)

        for i, (key, value) in enumerate(scores.items()):
            with cols[i % 3]:
                st.metric(
                    key,
                    f"{value}/100",
                )

        st.subheader("目標客群")

        for item in result.get(
            "target_audience",
            [],
        ):
            st.write(f"- {item}")

        st.subheader("消費需求")

        for item in result.get(
            "consumer_needs",
            [],
        ):
            st.write(f"- {item}")

        st.subheader("銷售方向")

        st.info(
            result.get(
                "selling_direction",
                "",
            )
        )

        st.subheader("優勢")

        for item in result.get(
            "advantages",
            [],
        ):
            st.write(f"✅ {item}")

        st.subheader("缺點")

        for item in result.get(
            "disadvantages",
            [],
        ):
            st.write(f"⚠️ {item}")

        st.subheader("風險")

        for item in result.get(
            "risks",
            [],
        ):
            st.write(f"⚠️ {item}")

    # 蝦皮
    with tabs[2]:
        shopee = result.get(
            "shopee",
            {},
        )

        st.subheader("商品標題")

        st.code(
            shopee.get("title", ""),
            language=None,
        )

        st.subheader("商品描述")

        st.text_area(
            "商品描述",
            shopee.get("description", ""),
            height=300,
            key="shopee_description_view",
        )

        st.subheader("商品賣點")

        for item in shopee.get(
            "selling_points",
            [],
        ):
            st.write(f"🔥 {item}")

        st.subheader("SEO")

        st.write(
            ", ".join(
                shopee.get(
                    "keywords",
                    [],
                )
            )
        )

        st.subheader("長尾關鍵字")

        st.write(
            ", ".join(
                shopee.get(
                    "long_tail_keywords",
                    [],
                )
            )
        )

    # TikTok
    with tabs[3]:
        tiktok = result.get(
            "tiktok",
            {},
        )

        st.subheader("TikTok 標題")

        st.code(
            tiktok.get("title", ""),
            language=None,
        )

        st.subheader("前3秒 Hook")

        st.info(
            tiktok.get("hook", "")
        )

        st.subheader("TikTok 文案")

        st.text_area(
            "TikTok文案",
            tiktok.get("copy", ""),
            height=180,
            key="tiktok_copy_view",
        )

        st.subheader("15秒腳本")

        st.text_area(
            "15秒腳本",
            tiktok.get("script_15", ""),
            height=220,
            key="script15_view",
        )

        st.subheader("30秒腳本")

        st.text_area(
            "30秒腳本",
            tiktok.get("script_30", ""),
            height=300,
            key="script30_view",
        )

        st.subheader("Hashtag")

        st.write(
            " ".join(
                tiktok.get(
                    "hashtags",
                    [],
                )
            )
        )

    # 即夢
    with tabs[4]:
        jimeng = result.get(
            "jimeng",
            {},
        )

        st.subheader("🖼️ 商品圖片 Prompt")

        st.text_area(
            "圖片Prompt",
            jimeng.get(
                "image_prompt",
                "",
            ),
            height=250,
            key="jimeng_image_view",
        )

        st.subheader("🎨 TikTok封面 Prompt")

        st.text_area(
            "封面Prompt",
            jimeng.get(
                "cover_prompt",
                "",
            ),
            height=220,
            key="jimeng_cover_view",
        )

        st.subheader("🎬 15秒影片 Prompt")

        st.text_area(
            "15秒影片Prompt",
            jimeng.get(
                "video_prompt_15",
                "",
            ),
            height=300,
            key="jimeng_video15_view",
        )

        st.subheader("🎬 30秒影片 Prompt")

        st.text_area(
            "30秒影片Prompt",
            jimeng.get(
                "video_prompt_30",
                "",
            ),
            height=300,
            key="jimeng_video30_view",
        )

        st.warning(
            "即夢 Prompt 僅負責生成 Prompt；本系統不直接呼叫即夢 API。"
        )

    # 影片
    with tabs[5]:
        if st.session_state.get(
            "last_video_bytes"
        ):
            st.video(
                st.session_state.last_video_bytes
            )

            st.download_button(
                "⬇️ 下載 AI 短影音",
                data=st.session_state.last_video_bytes,
                file_name=st.session_state.last_video_name,
                mime=st.session_state.last_video_mime,
                use_container_width=True,
            )

        else:
            st.info(
                "目前沒有成功生成影片。"
                "請確認 Edge TTS、Pexels、FFmpeg 均已安裝與設定。"
            )

    # 素材
    with tabs[6]:
        if st.session_state.get(
            "last_zip_bytes"
        ):
            st.success(
                "完整素材包已準備完成。"
            )

            st.download_button(
                "📦 下載完整 ZIP 素材包",
                data=st.session_state.last_zip_bytes,
                file_name=st.session_state.last_zip_name,
                mime="application/zip",
                type="primary",
                use_container_width=True,
            )

            st.write(
                """
                ZIP 包含：

                - 商品資料.json
                - AI分析結果.json
                - 蝦皮文案.txt
                - TikTok素材.txt
                - 即夢圖片Prompt.txt
                - 即夢影片15秒Prompt.txt
                - 即夢影片30秒Prompt.txt
                - 商品圖片
                - AI短影音（如果成功生成）
                """
            )
        else:
            st.info(
                "尚未產生素材包。"
            )


# =========================================================
# 影片中心
# =========================================================
def video_center():
    st.title("🎥 影片中心")

    uploaded = st.file_uploader(
        "上傳影片",
        type=["mp4", "mov", "webm"],
    )

    if uploaded:
        data = uploaded.getvalue()

        if len(data) > MAX_VIDEO_MB * 1024 * 1024:
            st.error(
                f"影片超過 {MAX_VIDEO_MB}MB。"
            )
            return

        ext = Path(uploaded.name).suffix.lower()

        st.session_state.last_video_bytes = data
        st.session_state.last_video_name = uploaded.name
        st.session_state.last_video_mime = VIDEO_MIME_MAP.get(
            ext,
            "video/mp4",
        )

        st.video(data)

        st.download_button(
            "⬇️ 下載影片",
            data=data,
            file_name=uploaded.name,
            mime=st.session_state.last_video_mime,
            use_container_width=True,
        )


# =========================================================
# 歷史紀錄
# =========================================================
def history_page():
    st.title("📚 歷史紀錄")

    histories = list_history()

    if not histories:
        st.info("目前沒有歷史紀錄。")
        return

    for folder in histories:
        product = load_json(
            folder / "product.json",
            {},
        )

        name = product.get(
            "name",
            folder.name,
        )

        with st.expander(
            f"🛒 {name}｜{folder.name}"
        ):
            st.json(product)

            result_file = folder / "ai_result.json"

            if result_file.exists():
                result = load_json(
                    result_file,
                    {},
                )

                st.write(
                    "AI選品分數：",
                    result.get(
                        "selection_score",
                        "-",
                    ),
                )

                shopee = result.get(
                    "shopee",
                    {},
                )

                st.write(
                    "蝦皮標題：",
                    shopee.get(
                        "title",
                        "",
                    ),
                )


# =========================================================
# 會員中心
# =========================================================
def member_center():
    st.title("👤 會員中心")

    member = st.session_state.member

    status, valid = member_expiration(member)

    st.write(
        f"帳號：**{member.get('username')}**"
    )

    st.write(
        f"角色：**{member.get('role')}**"
    )

    st.write(
        f"狀態：**{status}**"
    )

    st.write(
        f"建立時間：**{member.get('created_at')}**"
    )

    st.write(
        f"到期日：**{member.get('expire_date') or '永久'}**"
    )


# =========================================================
# Admin
# =========================================================
def admin_page():
    if st.session_state.member.get("role") != "admin":
        st.error("只有管理員可以使用此頁面。")
        return

    st.title("👑 管理員中心")

    members = load_members()

    st.subheader("會員列表")

    for username, member in list(members.items()):

        with st.expander(
            f"{username}｜{member.get('role')}"
        ):

            status, valid = member_expiration(
                member
            )

            st.write(
                f"狀態：{status}"
            )

            st.write(
                f"建立時間：{member.get('created_at')}"
            )

            st.write(
                f"到期時間：{member.get('expire_date') or '永久'}"
            )

            if username != ADMIN_USERNAME:

                c1, c2, c3 = st.columns(3)

                with c1:
                    if st.button(
                        "♾️ 設為永久",
                        key=f"perm_{username}",
                    ):
                        members[username]["permanent"] = True
                        members[username]["expire_date"] = None
                        save_members(members)
                        st.success("已設為永久會員。")
                        st.rerun()

                with c2:
                    if st.button(
                        "30天",
                        key=f"30_{username}",
                    ):
                        members[username]["permanent"] = False
                        members[username]["expire_date"] = (
                            today()
                            + timedelta(days=30)
                        ).isoformat()

                        save_members(members)
                        st.success("已設定30天。")
                        st.rerun()

                with c3:
                    if st.button(
                        "🗑️ 刪除",
                        key=f"delete_{username}",
                    ):
                        del members[username]
                        save_members(members)
                        st.success("會員已刪除。")
                        st.rerun()

    st.divider()

    st.subheader("➕ 新增會員")

    new_username = st.text_input(
        "會員帳號",
        key="admin_new_user",
    )

    new_password = st.text_input(
        "會員密碼",
        type="password",
        key="admin_new_pass",
    )

    member_type = st.selectbox(
        "會員類型",
        [
            "30天",
            "90天",
            "365天",
            "永久",
        ],
    )

    if st.button(
        "建立會員",
        type="primary",
    ):
        mapping = {
            "30天": 30,
            "90天": 90,
            "365天": 365,
        }

        permanent = member_type == "永久"

        days = mapping.get(
            member_type,
            30,
        )

        ok, msg = create_member(
            new_username,
            new_password,
            days=days,
            permanent=permanent,
        )

        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)


# =========================================================
# Sidebar
# =========================================================
def sidebar():
    with st.sidebar:

        st.title("🛒 AI 蝦皮 2.5 PRO")

        st.caption(
            st.session_state.username
        )

        st.divider()

        pages = [
            "Dashboard",
            "AI商品全自動",
            "影片中心",
            "歷史紀錄",
            "會員中心",
        ]

        if st.session_state.member.get(
            "role"
        ) == "admin":
            pages.append(
                "管理員中心"
            )

        selected = st.radio(
            "系統功能",
            pages,
            index=pages.index(
                st.session_state.page
            )
            if st.session_state.page in pages
            else 0,
        )

        st.session_state.page = selected

        st.divider()

        status, valid = member_expiration(
            st.session_state.member
        )

        st.write(
            f"會員：{status}"
        )

        st.write(
            f"Gemini：{GEMINI_MODEL}"
        )

        if st.button(
            "🚪 登出",
            use_container_width=True,
        ):
            for key in [
                "logged_in",
                "username",
                "member",
                "page",
            ]:
                if key in st.session_state:
                    del st.session_state[key]

            st.rerun()


# =========================================================
# Main
# =========================================================
def main():

    if not st.session_state.logged_in:
        login_page()
        return

    sidebar()

    page = st.session_state.page

    if page == "Dashboard":
        dashboard()

    elif page == "AI商品全自動":
        product_center()

    elif page == "影片中心":
        video_center()

    elif page == "歷史紀錄":
        history_page()

    elif page == "會員中心":
        member_center()

    elif page == "管理員中心":
        admin_page()


if __name__ == "__main__":
    main()    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        margin-bottom: 5px;
    }

    .sub-title {
        color: #777;
        margin-bottom: 20px;
    }

    .member-card {
        padding: 15px;
        border-radius: 12px;
        border: 1px solid rgba(128,128,128,.25);
        margin-bottom: 15px;
    }

    .small-note {
        color: #777;
        font-size: 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# Session State
# ============================================================

DEFAULT_SESSION = {
    "logged_in": False,
    "username": "",
    "name": "",
    "role": "",
    "page": "home",
    "result": "",
}


for key, value in DEFAULT_SESSION.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# 密碼處理
# ============================================================

def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        200000,
    ).hex()

    return f"{salt}${digest}"


def verify_password(password, stored_password):
    try:
        salt, saved_digest = stored_password.split("$", 1)

        check_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            200000,
        ).hex()

        return secrets.compare_digest(
            check_digest,
            saved_digest,
        )

    except Exception:
        return False


# ============================================================
# 會員資料
# ============================================================

def load_members():
    if not MEMBERS_FILE.exists():
        return []

    try:
        data = json.loads(
            MEMBERS_FILE.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(data, list):
            return data

    except Exception:
        return []

    return []


def save_members(members):
    temp_file = MEMBERS_FILE.with_suffix(".tmp")

    temp_file.write_text(
        json.dumps(
            members,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    temp_file.replace(MEMBERS_FILE)


def find_member(username):
    username = username.strip()

    for member in load_members():
        if member.get("username") == username:
            return member

    return None


# ============================================================
# 建立預設管理員
# ============================================================

def ensure_admin():
    members = load_members()

    admin = None

    for member in members:
        if member.get("username") == ADMIN_USERNAME:
            admin = member
            break

    if admin is None:

        members.append(
            {
                "username": ADMIN_USERNAME,
                "password_hash": hash_password(
                    DEFAULT_ADMIN_PASSWORD
                ),
                "name": "系統管理員",
                "email": "",
                "role": "admin",
                "status": "active",
                "membership": "永久",
                "created_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
            }
        )

        save_members(members)


# ============================================================
# 建立會員
# ============================================================

def create_member(
    username,
    password,
    name,
    email,
    role="member",
):
    username = username.strip()

    if not username:
        return False, "請輸入會員帳號。"

    if len(username) < 3:
        return False, "帳號至少需要 3 個字元。"

    if len(username) > 32:
        return False, "帳號最多 32 個字元。"

    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"

    for char in username:
        if char not in allowed:
            return (
                False,
                "帳號只能使用英文、數字、底線、點或連字號。",
            )

    if len(password) < 6:
        return False, "密碼至少需要 6 個字元。"

    if find_member(username) is not None:
        return False, "這個帳號已存在。"

    if role not in ["member", "vip", "admin"]:
        role = "member"

    members = load_members()

    members.append(
        {
            "username": username,
            "password_hash": hash_password(password),
            "name": name.strip() or username,
            "email": email.strip(),
            "role": role,
            "status": "active",
            "membership": "永久",
            "created_at": datetime.now().isoformat(
                timespec="seconds"
            ),
        }
    )

    save_members(members)

    return True, "會員建立成功，期限為永久。"


# ============================================================
# 登入 / 登出
# ============================================================

def login_user(username, password):
    member = find_member(username)

    if member is None:
        return False, "帳號或密碼錯誤。"

    if not verify_password(
        password,
        member.get("password_hash", ""),
    ):
        return False, "帳號或密碼錯誤。"

    if member.get("status") != "active":
        return False, "這個會員帳號目前已被停用。"

    st.session_state.logged_in = True
    st.session_state.username = member.get(
        "username",
        "",
    )
    st.session_state.name = member.get(
        "name",
        member.get("username", ""),
    )
    st.session_state.role = member.get(
        "role",
        "member",
    )
    st.session_state.page = "home"

    return True, "登入成功。"


def logout_user():
    for key, value in DEFAULT_SESSION.items():
        st.session_state[key] = value


# ============================================================
# Gemini API Key & Client
# ============================================================

def get_gemini_api_key():
    try:
        key = st.secrets.get(
            "GEMINI_API_KEY",
            "",
        )
        if key:
            return key
    except Exception:
        pass

    key = os.getenv(
        "GEMINI_API_KEY",
        "",
    )
    return key


def get_gemini_client():
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError(
            "找不到 google-genai。"
            "請確認 requirements.txt 已經安裝。"
        ) from exc

    api_key = get_gemini_api_key()

    if not api_key:
        raise RuntimeError(
            "找不到 GEMINI_API_KEY。"
            "請到 Streamlit Cloud → App Settings → Secrets 設定。"
        )

    return genai.Client(api_key=api_key)


# ============================================================
# Gemini 分析與圖片處理
# ============================================================

def ask_gemini(
    prompt,
    image_bytes=None,
    mime_type="image/jpeg",
):
    client = get_gemini_client()

    if image_bytes:
        from google.genai import types

        contents = [
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type,
            ),
            prompt,
        ]
    else:
        contents = prompt

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
    )

    text = getattr(response, "text", None)

    if not text:
        raise RuntimeError("Gemini 沒有回傳內容。")

    return text.strip()


def prepare_image(uploaded_file):
    raw_data = uploaded_file.getvalue()

    try:
        image = Image.open(io.BytesIO(raw_data))
        image = ImageOps.exif_transpose(image)

        if image.mode not in ["RGB", "RGBA"]:
            image = image.convert("RGB")

        max_size = 1600
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            new_width = max(1, int(image.width * ratio))
            new_height = max(1, int(image.height * ratio))
            image = image.resize(
                (new_width, new_height),
                Image.Resampling.LANCZOS,
            )

        output = io.BytesIO()
        if image.mode == "RGBA":
            image.save(output, format="PNG", optimize=True)
            return output.getvalue(), "image/png"

        image.save(output, format="JPEG", quality=92, optimize=True)
        return output.getvalue(), "image/jpeg"

    except Exception as exc:
        raise RuntimeError(f"圖片處理失敗：{exc}") from exc


# ============================================================
# 即夢 AI 2.5 核心規則 & 完整指令
# ============================================================

JIMENG_25_RULES = """
【即夢 AI 2.5 商品原貌鎖定】
1. 使用上傳圖片中的主要商品作為唯一主要商品。
2. 保留商品品牌、包裝、瓶身、盒子與外觀、形狀比例、顏色、材質、Logo、標籤與文字。
3. 不得自行修改品牌、包裝、顏色、形狀，不得捏造不存在的商品資料。
4. 不確定資訊必須標示「待確認」。

【一致性】
5. 整個畫面只能有一個主要商品，不得商品變形、融化、扭曲、漂浮、閃爍或消失。

【人物與商業限制】
6. 不要人物、手、手臂、模特兒，不使用人體拿商品。
7. 不要浮水印、錯誤價格、假贈品、額外商品。商品必須是視覺焦點，適合蝦皮與 TikTok。

【即夢 AI 2.5 生圖與影片】
8. Prompt 主體使用英文，商業畫面文字使用繁體中文，比例 9:16。
9. 影片包含 Opening, Middle, Camera Motion, Lighting, Focus, Detail, Consistency, Ending Freeze 及 Negative Prompt。
"""


def build_master_prompt(product):
    return f"""
你現在是「{APP_NAME}」的核心電商 AI。
請分析使用者提供的商品圖片與商品資料。

==============================
【商品資料】
==============================
商品名稱：{product["name"]}
商品價格：{product["price"]}
商品成本：{product["cost"]}
分潤比例：{product["commission"]}
月銷量：{product["sales"]}
商品評分：{product["rating"]}
商品連結：{product["url"]}
商品規格：{product["specs"]}
目標平台：{product["platform"]}

==============================
【重要資料規則】
==============================
只能根據圖片與使用者提供的資料，不能自行捏造。不知道的資訊請寫「待確認」。

==============================
【輸出任務】
==============================
【第一部分：商品辨識】
【第二部分：AI 選品分析】
【第三部分：蝦皮上架文案】
【第四部分：TikTok 文案】
【第五部分：即夢 AI 2.5 生圖 Prompt】(包含英文 Prompt、Negative Prompt、繁中文字、9:16 構圖)
【第六部分：即夢 AI 2.5 影片 Prompt】
【第七部分：即夢 AI 2.5 爆款帶貨影片腳本】(0-3s, 3-8s, 8-15s, 15-20s, 20-25s)
【第八部分：分潤合規檢查】
【第九部分：最終 AI 檢查】

請遵循即夢 2.5 規範：
{JIMENG_25_RULES}
"""


# ============================================================
# 頁面元件：登入頁
# ============================================================

def render_login_page():
    st.markdown(
        f"""
        <div class="main-title">🛒 {APP_NAME}</div>
        <div class="sub-title">永久會員｜管理員｜Gemini 2.5 Flash｜即夢 AI 2.5</div>
        """,
        unsafe_allow_html=True,
    )

    login_tab, register_tab = st.tabs(["🔐 會員登入", "📝 會員註冊"])

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("會員帳號")
            password = st.text_input("會員密碼", type="password")
            submitted = st.form_submit_button("登入", use_container_width=True)

        if submitted:
            ok, message = login_user(username, password)
            if ok:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

        st.info("預設管理員帳號：admin / 密碼：admin123456")

    with register_tab:
        with st.form("register_form"):
            username = st.text_input("新會員帳號")
            name = st.text_input("姓名 / 暱稱")
            email = st.text_input("Email")
            password = st.text_input("密碼", type="password")
            password2 = st.text_input("再次輸入密碼", type="password")
            submitted = st.form_submit_button("註冊永久會員", use_container_width=True)

        if submitted:
            if password != password2:
                st.error("兩次密碼不一致。")
            else:
                ok, message = create_member(username, password, name, email, "member")
                if ok:
                    st.success(message)
                else:
                    st.error(message)


# ============================================================
# 頁面元件：Sidebar
# ============================================================

def render_sidebar():
    with st.sidebar:
        st.markdown(f"## 🛒 {APP_NAME}")
        st.markdown(
            f"""
            <div class="member-card">
            👤 <b>{st.session_state.name}</b><br>
            帳號：{st.session_state.username}<br>
            權限：{st.session_state.role}<br>
            會員期限：<b>永久</b>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("🏠 AI 自動化", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()

        if st.session_state.role == "admin":
            if st.button("👑 管理員中心", use_container_width=True):
                st.session_state.page = "admin"
                st.rerun()

        st.divider()

        if st.button("🚪 登出", use_container_width=True):
            logout_user()
            st.rerun()


# ============================================================
# 頁面元件：管理員中心
# ============================================================

def render_admin_page():
    st.title("👑 管理員中心")
    st.caption("永久會員制：沒有到期日期，管理員可以手動啟用或停用。")

    members = load_members()
    total_members = len(members)
    active_members = sum(1 for m in members if m.get("status") == "active")
    admin_count = sum(1 for m in members if m.get("role") == "admin")

    col1, col2, col3 = st.columns(3)
    col1.metric("會員總數", total_members)
    col2.metric("啟用會員", active_members)
    col3.metric("管理員", admin_count)

    st.divider()

    st.subheader("➕ 建立永久會員")
    with st.form("admin_create_member"):
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("會員帳號")
            name = st.text_input("姓名 / 暱稱")
        with col2:
            password = st.text_input("會員密碼", type="password")
            email = st.text_input("Email")

        role = st.selectbox(
            "會員等級",
            ["member", "vip", "admin"],
            format_func=lambda v: {"member": "一般會員", "vip": "VIP 會員", "admin": "管理員"}[v],
        )

        submitted = st.form_submit_button("建立永久會員", use_container_width=True)

    if submitted:
        ok, message = create_member(username, password, name, email, role)
        if ok:
            st.success(message)
            st.rerun()
        else:
            st.error(message)

    st.divider()

    st.subheader("👥 會員管理")
    members = load_members()

    if not members:
        st.info("目前沒有會員資料。")
    else:
        for idx, m in enumerate(members):
            with st.expander(f"👤 {m.get('username')} ({m.get('name')}) - {m.get('role').upper()}"):
                st.write(f"**Email:** {m.get('email', '無')}")
                st.write(f"**狀態:** {m.get('status')}")
                st.write(f"**建立時間:** {m.get('created_at')}")

                if m.get("username") != ADMIN_USERNAME:
                    btn_label = "停用帳號" if m.get("status") == "active" else "啟用帳號"
                    if st.button(btn_label, key=f"toggle_{idx}"):
                        m["status"] = "disabled" if m.get("status") == "active" else "active"
                        save_members(members)
                        st.success(f"已更新 {m.get('username')} 的狀態")
                        st.rerun()


# ============================================================
# 頁面元件：AI 自動化主頁
# ============================================================

def render_home_page():
    st.title(f"🛒 {APP_NAME}")
    st.caption("自動化產生蝦皮文案、TikTok 腳本及即夢 AI 2.5 提示詞")

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("1. 上傳商品圖片")
        uploaded_file = st.file_uploader("選擇圖片 (JPG/PNG)", type=["jpg", "jpeg", "png"])

        if uploaded_file:
            st.image(uploaded_file, caption="預覽商品圖片", use_container_width=True)

        st.subheader("2. 填寫商品資料")
        product_name = st.text_input("商品名稱", placeholder="例如：極致保濕修護精華液")
        product_price = st.text_input("商品售價", placeholder="例如：499")
        product_cost = st.text_input("商品成本", placeholder="例如：150")
        product_commission = st.text_input("分潤比例 (%)", placeholder="例如：15")
        product_sales = st.text_input("預估月銷量", placeholder="例如：1000")
        product_rating = st.text_input("商品評分", placeholder="例如：4.9")
        product_url = st.text_input("商品連結", placeholder="例如：https://shopee.tw/...")
        product_specs = st.text_area("商品規格/細節描述", placeholder="例如：容量 30ml，保存期限 3 年...")
        platform = st.selectbox("主要目標平台", ["蝦皮購物 + TikTok", "僅蝦皮購物", "僅 TikTok"])

        generate_btn = st.button("🚀 開始 AI 文案與提示詞生成", type="primary", use_container_width=True)

    with col_right:
        st.subheader("3. AI 分析與生成結果")

        if generate_btn:
            if not uploaded_file:
                st.warning("請先上傳商品圖片。")
            elif not product_name.strip():
                st.warning("請輸入商品名稱。")
            else:
                with st.spinner("AI 正在分析圖片與撰寫文案中..."):
                    try:
                        img_bytes, mime_type = prepare_image(uploaded_file)
                        product_data = {
                            "name": product_name,
                            "price": product_price,
                            "cost": product_cost,
                            "commission": product_commission,
                            "sales": product_sales,
                            "rating": product_rating,
                            "url": product_url,
                            "specs": product_specs,
                            "platform": platform,
                        }
                        prompt = build_master_prompt(product_data)
                        result = ask_gemini(prompt, img_bytes, mime_type)
                        st.session_state.result = result
                    except Exception as e:
                        st.error(f"生成失敗：{e}")

        if st.session_state.result:
            st.markdown(st.session_state.result)
            st.download_button(
                label="📥 下載完整報告 (.txt)",
                data=st.session_state.result,
                file_name=f"{product_name}_AI分析報告.txt",
                mime="text/plain",
                use_container_width=True,
            )


# ============================================================
# 主程式入口 (Main)
# ============================================================

def main():
    ensure_admin()

    if not st.session_state.logged_in:
        render_login_page()
    else:
        render_sidebar()
        if st.session_state.page == "admin" and st.session_state.role == "admin":
            render_admin_page()
        else:
            render_home_page()


if __name__ == "__main__":
    main()         "找不到 GEMINI_API_KEY。請到 Streamlit Cloud → App Settings → Secrets 設定。"
        )

    return genai.Client(
        api_key=api_key
    )


# ============================================================
# Gemini 圖片＋文字分析
# ============================================================

def ask_gemini(
    prompt,
    image_bytes=None,
    mime_type="image/jpeg",
):
    client = get_gemini_client()

    if image_bytes:

        from google.genai import types

        contents = [
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type,
            ),
            prompt,
        ]

    else:

        contents = prompt

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
    )

    text = getattr(
        response,
        "text",
        None,
    )

    if not text:
        raise RuntimeError(
            "Gemini 沒有回傳內容。"
        )

    return text.strip()


# ============================================================
# 圖片處理
# ============================================================

def prepare_image(uploaded_file):

    raw_data = uploaded_file.getvalue()

    try:

        image = Image.open(
            io.BytesIO(raw_data)
        )

        image = ImageOps.exif_transpose(
            image
        )

        if image.mode not in [
            "RGB",
            "RGBA",
        ]:
            image = image.convert("RGB")

        max_size = 1600

        if max(image.size) > max_size:

            ratio = max_size / max(image.size)

            new_width = max(
                1,
                int(image.width * ratio),
            )

            new_height = max(
                1,
                int(image.height * ratio),
            )

            image = image.resize(
                (
                    new_width,
                    new_height,
                ),
                Image.Resampling.LANCZOS,
            )

        output = io.BytesIO()

        if image.mode == "RGBA":

            image.save(
                output,
                format="PNG",
                optimize=True,
            )

            return (
                output.getvalue(),
                "image/png",
            )

        image.save(
            output,
            format="JPEG",
            quality=92,
            optimize=True,
        )

        return (
            output.getvalue(),
            "image/jpeg",
        )

    except Exception as exc:

        raise RuntimeError(
            f"圖片處理失敗：{exc}"
        ) from exc


# ============================================================
# 即夢 AI 2.5 核心規則
# ============================================================

JIMENG_25_RULES = """
【即夢 AI 2.5 商品原貌鎖定】

1.ode == "RGBA":

            image.save(
                output,
                format="PNG",
                optimize=True,
            )

            return (
                output.getvalue(),
                "image/png",
            )

        image.save(
            output,
            format="JPEG",
            quality=92,
            optimize=True,
        )

        return (
            output.getvalue(),
            "image/jpeg",
        )

    except Exception as exc:

        raise RuntimeError(
            f"圖片處理失敗：{exc}"
        ) from exc


# ============================================================
# 即夢 AI 2.5 核心規則
# ============================================================

JIMENG_25_RULES = """
【即夢 AI 2.5 商品原貌鎖定】

1. 使用上傳圖片中的主要商品作為唯一主要商品。
2. 保留商品品牌。
3. 保留商品包裝。
4. 保留商品瓶身、盒子與外觀。
5. 保留商品形狀與比例。
6. 保留商品顏色。
7. 保留商品材質。
8. 保留 Logo。
9. 保留標籤。
10. 保留包裝上的可見文字。
11. 不得自行改品牌。
12. 不得自行改包裝。
13. 不得自行改顏色。
14. 不得自行改形狀。
15. 不得捏造不存在的商品資料。
16. 不確定資訊必須標示「待確認」。

【一致性】

17. 整個畫面只能有一個主要商品。
18. 不得出現第二個相同商品。
19. 不得商品變形。
20. 不得商品融化。
21. 不得商品扭曲。
22. 不得商品漂浮。
23. 不得商品閃爍。
24. 不得商品突然消失。
25. 不得 Logo 變形。
26. 不得包裝文字漂移。

【人物限制】

27. 不要人物。
28. 不要手。
29. 不要手臂。
30. 不要模特兒。
31. 不要主持人。
32. 不要代言人。
33. 不要人體拿商品。
34. 不要人物遮擋商品。

【商業限制】

35. 不要浮水印。
36. 不要錯誤價格。
37. 不要假贈品。
38. 不要錯誤品牌。
39. 不要虛構商品。
40. 不要額外商品。
41. 商品必須是視覺焦點。
42. 使用高品質商業攝影。
43. 適合蝦皮與 TikTok 電商。

【內容合規】

44. 不得虛構功效。
45. 不得誇大療效。
46. 不得虛構認證。
47. 不得虛構銷量。
48. 不得虛構價格。
49. 不得使用無依據的保證性宣稱。

【即夢 AI 2.5 生圖】

50. Prompt 主體使用英文。
51. 商業畫面文字使用繁體中文。
52. 使用 9:16。
53. 商品為畫面視覺中心。
54. 必須輸出 Negative Prompt。

【即夢 AI 2.5 影片】

55. 使用 9:16 直式影片。
56. Opening：完整商品正面、商品置中。
57. Middle：slow push-in / dolly-in。
58. 展示包裝、材質、細節。
59. Camera Motion 平滑穩定。
60. 商品身份全程一致。
61. Ending：商品置中並 freeze frame。
62. 必須輸出 Negative Prompt。
"""


# ============================================================
# AI 完整指令
# ============================================================

def build_master_prompt(product):

    return f"""
你現在是「{APP_NAME}」的核心電商 AI。

請分析使用者提供的商品圖片與商品資料。

==============================
【商品資料】
==============================

商品名稱：
{product["name"]}

商品價格：
{product["price"]}

商品成本：
{product["cost"]}

分潤比例：
{product["commission"]}

月銷量：
{product["sales"]}

商品評分：
{product["rating"]}

商品連結：
{product["url"]}

商品規格：
{product["specs"]}

目標平台：
{product["platform"]}


==============================
【重要資料規則】
==============================

只能根據圖片與使用者提供的資料。

不能自行捏造：
- 品牌
- 規格
- 成分
- 功效
- 認證
- 價格
- 贈品
- 銷量

不知道的資訊請寫：

「待確認」


==============================
【第一部分：商品辨識】
==============================

請輸出：

商品名稱
商品分類
圖片可確認資訊
待確認資訊
主要賣點
目標客群


==============================
【第二部分：AI 選品分析】
==============================

請輸出：

市場定位
目標客群
商品優勢
商品弱點
短影音內容方向
行銷切入點
購買誘因
合規提醒


==============================
【第三部分：蝦皮上架文案】
==============================

請輸出：

SEO 商品標題
短標題
5 個主要賣點
完整商品描述
商品規格
購買提醒
Hashtag


==============================
【第四部分：TikTok 文案】
==============================

請輸出：

3 秒 Hook
15～30 秒口播
TikTok 貼文
CTA
Hashtag


==============================
【第五部分：即夢 AI 2.5 生圖 Prompt】
==============================

嚴格執行以下規則：

{JIMENG_25_RULES}

輸出：

【即夢 AI 2.5 生圖英文 Prompt】

【Negative Prompt】

【繁體中文畫面文字】

【9:16 商業構圖】


==============================
【第六部分：即夢 AI 2.5 影片 Prompt】
==============================

嚴格執行以下規則：

{JIMENG_25_RULES}

輸出：

【即夢 AI 2.5 影片 Prompt】

必須包含：

Opening
Middle
Camera Motion
Lighting
Focus
Product Detail
Product Consistency
Ending Freeze
Negative Prompt


==============================
【第七部分：即夢 AI 2.5 爆款帶貨影片】
==============================

請產生：

0～3 秒：
Hook

3～8 秒：
商品展示

8～15 秒：
商品細節

15～20 秒：
商品賣點

20～25 秒：
CTA

字幕方向


==============================
【第八部分：分潤合規檢查】
==============================

請檢查：

商品價格
商品成本
分潤比例
可能誇大的內容
需要人工確認的內容


==============================
【第九部分：最終 AI 檢查】
==============================

請逐項確認：

1. 是否捏造商品資料
2. 是否有待確認資訊
3. 是否保持商品原貌
4. 是否禁止人物
5. 是否禁止手
6. 是否禁止第二商品
7. 是否禁止變形
8. 是否有 Negative Prompt
9. 是否為 9:16
10. 是否符合即夢 AI 2.5 規則
"""


# ============================================================
# 登入頁
# ============================================================

def render_login_page():

    st.markdown(
        f"""
        <div class="main-title">
        🛒 {APP_NAME}
        </div>

        <div class="sub-title">
        永久會員｜管理員｜Gemini 2.5 Flash｜即夢 AI 2.5
        </div>
        """,
        unsafe_allow_html=True,
    )

    login_tab, register_tab = st.tabs(
        [
            "🔐 會員登入",
            "📝 會員註冊",
        ]
    )

    # --------------------------
    # 登入
    # --------------------------

    with login_tab:

        with st.form("login_form"):

            username = st.text_input(
                "會員帳號"
            )

            password = st.text_input(
                "會員密碼",
                type="password",
            )

            submitted = st.form_submit_button(
                "登入",
                use_container_width=True,
            )

        if submitted:

            ok, message = login_user(
                username,
                password,
            )

            if ok:

                st.success(message)
                st.rerun()

            else:

                st.error(message)

        st.info(
            "預設管理員帳號：admin"
        )

    # --------------------------
    # 註冊
    # --------------------------

    with register_tab:

        with st.form("register_form"):

            username = st.text_input(
                "新會員帳號"
            )

            name = st.text_input(
                "姓名 / 暱稱"
            )

            email = st.text_input(
                "Email"
            )

            password = st.text_input(
                "密碼",
                type="password",
            )

            password2 = st.text_input(
                "再次輸入密碼",
                type="password",
            )

            submitted = st.form_submit_button(
                "註冊永久會員",
                use_container_width=True,
            )

        if submitted:

            if password != password2:

                st.error(
                    "兩次密碼不一致。"
                )

            else:

                ok, message = create_member(
                    username,
                    password,
                    name,
                    email,
                    "member",
                )

                if ok:

                    st.success(message)

                else:

                    st.error(message)


# ============================================================
# Sidebar
# ============================================================

def render_sidebar():

    with st.sidebar:

        st.markdown(
            f"## 🛒 {APP_NAME}"
        )

        st.markdown(
            f"""
            <div class="member-card">
            👤 <b>{st.session_state.name}</b><br>
            帳號：{st.session_state.username}<br>
            權限：{st.session_state.role}<br>
            會員期限：<b>永久</b>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button(
            "🏠 AI 自動化",
            use_container_width=True,
        ):

            st.session_state.page = "home"
            st.rerun()

        if st.session_state.role == "admin":

            if st.button(
                "👑 管理員中心",
                use_container_width=True,
            ):

                st.session_state.page = "admin"
                st.rerun()

        st.divider()

        if st.button(
            "🚪 登出",
            use_container_width=True,
        ):

            logout_user()
            st.rerun()


# ============================================================
# 管理員中心
# ============================================================

def render_admin_page():

    st.title(
        "👑 管理員中心"
    )

    st.caption(
        "永久會員制：沒有到期日期，管理員可以手動啟用或停用。"
    )

    members = load_members()

    total_members = len(members)

    active_members = sum(
        1
        for member in members
        if member.get("status") == "active"
    )

    admin_count = sum(
        1
        for member in members
        if member.get("role") == "admin"
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "會員總數",
        total_members,
    )

    col2.metric(
        "啟用會員",
        active_members,
    )

    col3.metric(
        "管理員",
        admin_count,
    )

    st.divider()

    # ========================================================
    # 建立會員
    # ========================================================

    st.subheader(
        "➕ 建立永久會員"
    )

    with st.form(
        "admin_create_member"
    ):

        col1, col2 = st.columns(2)

        with col1:

            username = st.text_input(
                "會員帳號"
            )

            name = st.text_input(
                "姓名 / 暱稱"
            )

        with col2:

            password = st.text_input(
                "會員密碼",
                type="password",
            )

            email = st.text_input(
                "Email"
            )

        role = st.selectbox(
            "會員等級",
            [
                "member",
                "vip",
                "admin",
            ],
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
        )

        if ok:

            st.success(message)
            st.rerun()

        else:

            st.error(message)

    st.divider()

    # ========================================================
    # 會員列表
    # ========================================================

    st.subheader(
        "👥 會員管理"
    )

    members = load_members()

    if not members:

        st.ision = st.text_input("分潤比例")
        sales = st.text_input("月銷量數據")
        rating = st.text_input("商品評分")
        specs = st.text_area("詳細規格/特點")
        platform = st.selectbox("目標上架平台", ["蝦皮購物", "TikTok 電商", "雙平台通用"])
        uploaded_file = st.file_uploader("上傳商品照片", type=["jpg", "jpeg", "png", "webp"])

    with col2:
        if st.button("🚀 開始全自動分析與文案生成", use_container_width=True, type="primary"):
            if not name:
                st.warning("⚠️ 請輸入商品名稱！")
            else:
                product_info = {
                    "name": name, "price": price or "待確認", "cost": cost or "待確認",
                    "commission": commission or "待確認", "sales": sales or "待確認",
                    "rating": rating or "待確認", "specs": specs or "待確認", "platform": platform,
                }
                img_obj = process_image(uploaded_file) if uploaded_file else None
                with st.spinner("AI 正在分析生成中..."):
                    try:
                        prompt_text = build_ai_prompt(product_info)
                        st.session_state.result = ask_gemini(prompt_text, img_obj)
                        st.success("✅ 生成完畢！")
                    except Exception as e:
                        st.error(f"❌ 生成失敗：{e}")

        if st.session_state.result:
            st.text_area("生成結果", st.session_state.result, height=500)

def admin_page():
    st.title("👑 管理員中心")
    members = load_members()
    st.write(f"目前註冊總人數：{len(members)}")
    for m in members:
        st.write(f"- 帳號: {m['username']} | 權限: {m['role']} | 狀態: {m['status']}")

# ============================================================
# 主入口
# ============================================================

def main():
    ensure_admin()
    if not st.session_state.logged_in:
        login_page()
    else:
        sidebar()
        if st.session_state.page == "admin" and st.session_state.role == "admin":
            admin_page()
        else:
            home_page()

if __name__ == "__main__":
    main()
