import io
import os
import re
import json
import hashlib
import secrets
from datetime import datetime, date, timedelta

import streamlit as st
from PIL import Image, ImageOps


# =========================================================
# AI 蝦皮半自動化 2.5 PRO
# 純本機無 API 版本
#
# 已移除：
# Google
# GPT / ChatGPT
# Gemini
# WeChat
# LINE
# 所有外部 API
#
# 保留：
# 會員註冊
# 會員登入
# 會員期限
# 管理員
# 商品分析
# 圖片上傳
# 即夢 2.5 Prompt 生成
# 蝦皮商品文案
# =========================================================


# =========================================================
# 網頁設定
# =========================================================

st.set_page_config(
    page_title="AI 蝦皮半自動化 2.5 PRO",
    page_icon="🛒",
    layout="wide",
)


# =========================================================
# 系統設定
# =========================================================

APP_NAME = "AI 蝦皮半自動化 2.5 PRO"

DATA_DIR = "data"
MEMBERS_FILE = os.path.join(DATA_DIR, "members.json")

MAX_IMAGE_SIZE = 1600
MAX_IMAGE_MB = 20

DEFAULT_MEMBER_DAYS = 30

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


# =========================================================
# 建立資料夾
# =========================================================

os.makedirs(DATA_DIR, exist_ok=True)


# =========================================================
# 會員資料
# =========================================================

def load_members():

    if not os.path.exists(MEMBERS_FILE):
        return []

    try:

        with open(
            MEMBERS_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if isinstance(data, list):
            return data

    except Exception:
        pass

    return []


def save_members(members):

    with open(
        MEMBERS_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            members,
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# 密碼
# =========================================================

def hash_password(password):

    salt = secrets.token_hex(16)

    digest = hashlib.sha256(
        (
            salt + password
        ).encode("utf-8")
    ).hexdigest()

    return f"{salt}${digest}"


def verify_password(
    password,
    saved_value
):

    try:

        salt, saved_hash = saved_value.split(
            "$",
            1
        )

        digest = hashlib.sha256(
            (
                salt + password
            ).encode("utf-8")
        ).hexdigest()

        return secrets.compare_digest(
            digest,
            saved_hash
        )

    except Exception:

        return False


# =========================================================
# 初始化管理員
# =========================================================

def ensure_admin():

    members = load_members()

    for member in members:

        if member.get("username") == ADMIN_USERNAME:
            return

    admin = {

        "id": secrets.token_hex(8),

        "username": ADMIN_USERNAME,

        "password_hash": hash_password(
            ADMIN_PASSWORD
        ),

        "name": "系統管理員",

        "email": "",

        "role": "admin",

        "status": "active",

        "expires": (
            date.today()
            + timedelta(days=3650)
        ).isoformat(),

        "created_at": datetime.now().isoformat()

    }

    members.append(admin)

    save_members(members)


ensure_admin()


# =========================================================
# 會員查詢
# =========================================================

def find_member(username):

    username = username.strip().lower()

    members = load_members()

    for member in members:

        if (
            member.get(
                "username",
                ""
            ).lower()
            == username
        ):

            return member

    return None


def find_member_by_email(email):

    email = email.strip().lower()

    if not email:
        return None

    members = load_members()

    for member in members:

        if (
            member.get(
                "email",
                ""
            ).lower()
            == email
        ):

            return member

    return None


# =========================================================
# 建立會員
# =========================================================

def create_member(
    username,
    password,
    name,
    email
):

    username = username.strip().lower()
    email = email.strip().lower()

    if find_member(username):

        return False, "帳號已存在。"

    if email and find_member_by_email(email):

        return False, "Email 已註冊。"

    expires = (
        date.today()
        + timedelta(days=DEFAULT_MEMBER_DAYS)
    ).isoformat()

    member = {

        "id": secrets.token_hex(8),

        "username": username,

        "password_hash": hash_password(
            password
        ),

        "name": name.strip(),

        "email": email,

        "role": "member",

        "status": "active",

        "expires": expires,

        "created_at": datetime.now().isoformat()

    }

    members = load_members()

    members.append(member)

    save_members(members)

    return True, member


# =========================================================
# 更新會員
# =========================================================

def update_member(
    member_id,
    updates
):

    members = load_members()

    for member in members:

        if member.get("id") == member_id:

            member.update(updates)

            save_members(members)

            return True

    return False


# =========================================================
# 登入
# =========================================================

def check_login(
    username,
    password
):

    member = find_member(username)

    if not member:

        return False, "invalid"

    status = str(
        member.get(
            "status",
            "active"
        )
    ).lower()

    if status != "active":

        return False, "disabled"

    saved_hash = str(
        member.get(
            "password_hash",
            ""
        )
    )

    if (
        not saved_hash
        or not verify_password(
            password,
            saved_hash
        )
    ):

        return False, "invalid"

    expires_text = str(
        member.get(
            "expires",
            ""
        )
    )

    try:

        expires_date = date.fromisoformat(
            expires_text
        )

    except Exception:

        return False, "invalid_date"

    if date.today() > expires_date:

        return False, "expired"

    return True, member


# =========================================================
# Session
