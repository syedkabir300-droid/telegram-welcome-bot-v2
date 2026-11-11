# Event loop initialization prior to Pyrogram import (Python 3.14 Fix)
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
from aiohttp import web
from pyrogram import Client, filters, idle

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("TelanganaMasterBot")

# Verified Credentials
API_ID = int(os.environ.get("API_ID", "38476624"))
API_HASH = os.environ.get("API_HASH", "6138b409afb06ddb68a735f360092e19")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9174050495:AAGDdZ-Tm6NLxDs0Pqz_l1dmGKschjz55Cs")
OWNER_ID = int(os.environ.get("OWNER_ID", "6454597633"))

bot = Client("master_unified_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

DB_FILE = "master_database.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS groups (chat_id INTEGER PRIMARY KEY, title TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bot_settings (key TEXT PRIMARY KEY, val TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS sub_admins (
        user_id INTEGER PRIMARY KEY,
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

def db_add_group(chat_id, title):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO groups VALUES (?, ?)", (chat_id, title))
    conn.commit()
    conn.close()

def db_remove_group(chat_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM groups WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()

def db_get_all_groups():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT chat_id, title FROM groups")
    rows = c.fetchall()
    conn.close()
    return rows

def db_add_sub_admin(user_id, group_id, perms, expiry_date):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO sub_admins VALUES (?, ?, ?, ?)", (user_id, group_id, perms, expiry_date))
    conn.commit()
    conn.close()

def db_get_all_sub_admins():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id, group_id, permissions, expiry_date FROM sub_admins")
    rows = c.fetchall()
    conn.close()
    return rows

def db_remove_sub_admin(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM sub_admins WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def check_user_access(user_id):
    if user_id == OWNER_ID:
        return True, "ALL", "LIFETIME"
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT group_id, permissions, expiry_date FROM sub_admins WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return False, None, None
    gid, perms, exp_str = row
    try:
        exp_dt = datetime.strptime(exp_str, "%Y-%m-%d")
        if datetime.now(timezone.utc).date() > exp_dt.date():
            db_remove_sub_admin(user_id)
            return False, None, None
    except Exception:
        pass
    return True, perms, exp_str

@bot.on_message(filters.command("start") & filters.private)
async def start_private_cmd(client, message):
    uid = message.from_user.id
    has_access, perms, exp_date = check_user_access(uid)
    if not has_access:
        await message.reply_text("🔒 Access Denied. Contact owner for access.")
        return

    groups_count = len(db_get_all_groups())
    sub_admins_count = len(db_get_all_sub_admins())

    text = (
        "👑 **TELANGANA MASTER BOT** 👑\n\n"
        f"👤 **Access Level:** {'OWNER (Full)' if uid == OWNER_ID else f'AGENT ({perms})'}\n"
        f"⏳ **Validity:** {exp_date if exp_date else 'Lifetime'}\n"
        f"🏢 **Connected Chats:** {groups_count}\n"
        f"👮 **Active Sub-Admins:** {sub_admins_count}\n\n"
        "**Available Commands:**\n"
        "• `/status` - Check system overview\n"
        "• `/groups` - View connected groups list\n"
        "• `/addadmin <UserID> <GroupID> <Perms> <Days>` - Add new admin\n"
        "• `/deladmin <UserID>` - Revoke admin access"
    )
    await message.reply_text(text)

@bot.on_message(filters.command("status") & filters.private)
async def status_cmd(client, message):
    uid = message.from_user.id
    has_access, _, _ = check_user_access(uid)
    if not has_access:
        return
    groups_count = len(db_get_all_groups())
    sub_admins_count = len(db_get_all_sub_admins())
    await message.reply_text(
        f"⚡ **SYSTEM STATUS**\n"
        f"• Status: 24/7 Active Running\n"
        f"• Connected Chats: {groups_count}\n"
        f"• Registered Admins: {sub_admins_count}"
    )

@bot.on_message(filters.command("groups") & filters.private)
async def list_groups_cmd(client, message):
    uid = message.from_user.id
    has_access, _, _ = check_user_access(uid)
    if not has_access:
        return
    groups = db_get_all_groups()
    if not groups:
        await message.reply_text("Koi groups registered nahi hain.")
        return
    txt = "🏢 **CONNECTED GROUPS:**\n\n"
    for cid, title in groups:
        txt += f"• **{title}** (`{cid}`)\n"
    await message.reply_text(txt)

@bot.on_message(filters.command("addadmin") & filters.private)
async def add_admin_cmd(client, message):
    uid = message.from_user.id
    if uid != OWNER_ID:
        await message.reply_text("❌ Sirf owner admin add kar sakta hai.")
        return
    parts = message.command
    if len(parts) < 5:
        await message.reply_text("⚠️ **Format:** `/addadmin <UserID> <GroupID> <Permissions> <Days>`\nEx: `/addadmin 123456 -100123456 ALL 30`")
        return
    try:
        target_uid = int(parts[1])
        target_gid = int(parts[2])
        perms = parts[3].upper()
        days = int(parts[4])
        exp_date = (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")
        db_add_sub_admin(target_uid, target_gid, perms, exp_date)
        db_add_group(target_gid, f"Managed Group ({target_uid})")
        await message.reply_text(f"✅ Admin `{target_uid}` added successfully until `{exp_date}` ({days} Din).")
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

@bot.on_message(filters.command("deladmin") & filters.private)
async def del_admin_cmd(client, message):
    uid = message.from_user.id
    if uid != OWNER_ID:
        await message.reply_text("❌ Sirf owner admin remove kar sakta hai.")
        return
    if len(message.command) < 2:
        await message.reply_text("⚠️ **Format:** `/deladmin <UserID>`")
        return
    try:
        target_uid = int(message.command[1])
        db_remove_sub_admin(target_uid)
        await message.reply_text(f"🗑️ Admin `{target_uid}` removed.")
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

@bot.on_message(filters.command("start") & (filters.group | filters.channel))
async def start_group_cmd(client, message):
    db_add_group(message.chat.id, message.chat.title or "Telegram Chat")
    try:
        ack = await message.reply_text("🛡️ Group registered with Master Bot.")
        await asyncio.sleep(3)
        await ack.delete()
    except Exception:
        pass

@bot.on_message(filters.group | filters.channel)
async def auto_group_guard(client, message):
    if message.chat:
        db_add_group(message.chat.id, message.chat.title or "Telegram Chat")

    if message.chat.type in ["group", "supergroup"]:
        if message.from_user and message.from_user.id == OWNER_ID:
            return
        text = message.text or message.caption or ""
        forbidden = ["t.me/", "telegram.me/", "http://", "https://", "joinchat", "@"]
        if any(w in text.lower() for w in forbidden):
            try:
                await message.delete()
                uname = message.from_user.mention if message.from_user else "Member"
                warn = await message.reply_text(f"🛡️ **Security Alert:** {uname}, external links are not allowed.")
                await asyncio.sleep(4)
                await warn.delete()
            except Exception as e:
                logger.error(f"Auto delete fail: {e}")

async def start_services():
    try:
        await bot.start()
        print("Unified Bot Live with Verified Credentials 🚀", flush=True)

        app = web.Application()
        app.router.add_get('/', lambda r: web.Response(text="Bot 24/7 Running Active"))
        runner = web.AppRunner(app)
        await runner.setup()

        port = int(os.environ.get("PORT", 8080))
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        print(f"Health server listening on {port}", flush=True)

        await idle()
    except Exception as e:
        logger.exception(f"Startup Error: {e}")
        print(f"CRASH: {e}", file=sys.stderr, flush=True)

if __name__ == "__main__":
    loop.run_until_complete(start_services())
