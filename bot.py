# Event Loop Initialization (Python 3.14 Fix - Must be at the very top)
import asyncio
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

import os
import sys
import sqlite3
import logging
from datetime import datetime, timezone, timedelta
import aiohttp
from aiohttp import web
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AutoWelcomeMasterBot")

API_ID = int(os.environ.get("API_ID", "38476624"))
API_HASH = os.environ.get("API_HASH", "6138b409afb06ddb68a735f360092e19")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9174050495:AAGDdZ-Tm6NLxDs0Pqz_l1dmGKschjz55Cs")
OWNER_ID = int(os.environ.get("OWNER_ID", "6454597633"))
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

bot = Client("auto_welcome_master_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

DB_FILE = "master_database.db"

DEFAULT_VIP_POST = (
    "👑 **TELANGANA SURE SHOT VIP CHANNEL** 👑\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "🔥 **Daily Official Updates & VIP Access** 🔥\n\n"
    "🎯 **Join VIP Telegram Channel:**\n"
    "👉 https://t.me/+GMTnuLiWcr4wOTQ1\n\n"
    "🔗 **Official Registration Link:**\n"
    "👉 https://bdglink.com//#/register?invitationCode=1921324032297\n"
    "━━━━━━━━━━━━━━━━━━━━"
)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS bot_settings (key TEXT PRIMARY KEY, val TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS groups (chat_id INTEGER PRIMARY KEY, title TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bot_users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT,
        username TEXT,
        joined_date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS sub_admins (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        group_id INTEGER,
        permissions TEXT,
        expiry_date TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

def db_set_setting(key, val):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO bot_settings VALUES (?, ?)", (key, val))
    conn.commit()
    conn.close()

def db_get_setting(key, default_val=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT val FROM bot_settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default_val

def db_add_user(user_id, first_name, username):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    c.execute("INSERT OR REPLACE INTO bot_users VALUES (?, ?, ?, ?)", (user_id, first_name, username, date_str))
    conn.commit()
    conn.close()

def db_get_all_users():
    conn = sqlite3.connect(DB
