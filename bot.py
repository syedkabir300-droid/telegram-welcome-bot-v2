# Event loop ko Pyrogram import hone se pehle initialize karna (Python 3.14 Fix)
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
from datetime import datetime, timezone
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

# Render URL environment variable (Optional: Render URL auto detect)
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

bot = Client("auto_welcome_master_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

DB_FILE = "master_database.db"

DEFAULT_VIP_POST = (
    "👑 **TELANGANA SURE SHOT VIP CHANNEL** 👑\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "🔥 **Daily 100% Sure Shot WinGo Signals** 🔥\n\n"
    "🎯 **Join VIP Telegram Channel:**\n"
    "👉 https://t.me/+GMTnuLiWcr4wOTQ1\n\n"
    "🎮 **Official Game Register Link:**\n"
    "👉 https://bdglink.com//#/register?invitationCode=1921324032297\n\n"
    "⚠️ **Deposit Min ₹300 to activate VIP Hack Panel & Signals!**\n"
    "━━━━━━━━━━━━━━━━━━━━"
)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS bot_settings (key TEXT PRIMARY KEY, val TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bot_users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT,
        username TEXT,
        joined_date TEXT
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
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id, first_name, username, joined_date FROM bot_users ORDER BY joined_date DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def db_get_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id, first_name, username, joined_date FROM bot_users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

if not db_get_setting("SERVICE_STATUS"):
    db_set_setting("SERVICE_STATUS", "ON")

SYSTEM_STATE = {
    "WAITING_VIP_TEXT": False
}

def is_bot_active():
    return db_get_setting("SERVICE_STATUS", "ON") == "ON"

def get_owner_keyboard():
    status_icon = "🟢 ON (24/7 ACTIVE)" if is_bot_active() else "🔴 OFF (STOPPED)"
    toggle_target = "turn_off" if is_bot_active() else "turn_on"

    vid_status = "✅ ACTIVE" if db_get_setting("WELCOME_VIDEO_ID") else "❌ NOT SET"
    doc_status = "✅ ACTIVE" if db_get_setting("WELCOME_DOC_ID") else "❌ NOT SET"
    voice_status = "✅ ACTIVE" if db_get_setting("WELCOME_VOICE_ID") else "❌ NOT SET"
    total_users = len(db_get_all_users())

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"⚡ BOT STATUS: [{status_icon}]", callback_data=toggle_target)
        ],
        [
            InlineKeyboardButton(f"📹 VIDEO: {vid_status}", callback_data="test_video"),
            InlineKeyboardButton(f"📁 APK: {doc_status}", callback_data="test_doc")
        ],
        [
            InlineKeyboardButton(f"🎙️ VOICE: {voice_status}", callback_data="test_voice"),
            InlineKeyboardButton("📢 VIP POST", callback_data="test_vip")
        ],
        [
            InlineKeyboardButton(f"👥 USERS & LOGOS ({total_users})", callback_data="btn_list_users")
        ],
        [
            InlineKeyboardButton("✏️ SET VIP TEXT & LINKS", callback_data="btn_set_vip_text"),
            InlineKeyboardButton("🚀 TEST FULL PACKAGE", callback_data="btn_test_full")
        ]
    ])

def get_owner_text():
    status_label = "🟢 24/7 NON-STOP CLOUD BACKUP RUNNING" if is_bot_active() else "🔴 STOPPED (OFF)"
    total_users = len(db_get_all_users())
    return (
        "╔════════════════════════════╗\n"
        "  👑 **AUTOMATED WELCOME MASTER BOT** 👑\n"
        "╚════════════════════════════╝\n\n"
        f"⚡ **Cloud Status:** `{status_label}`\n"
        f"🛡️ **Keep-Alive Engine:** `🟢 ACTIVE (Anti-Sleep 24h)`\n"
        f"👥 **Total Started Users:** `{total_users}` Users\n\n"
        "Aapka phone ya PC band hone par bhi yeh cloud me 24 ghante run karta rahega.\n\n"
        "Neeche diye gaye buttons se operate karein:"
    )

async def send_welcome_assets(chat_id):
    vid = db_get_setting("WELCOME_VIDEO_ID")
    doc = db_get_setting("WELCOME_DOC_ID")
    aud = db_get_setting("WELCOME_VOICE_ID")
    vip_post = db_get_setting("VIP_CHANNEL_POST", DEFAULT_VIP_POST)

    sent_count = 0

    if vid:
        try:
            await bot.send_video(
                chat_id,
                video=vid,
                caption="✅ **WATCH ACTIVATION VIDEO** ✅\n\n😍 **300 TO 11000 LIVE PROFIT** 😍"
            )
            sent_count += 1
            await asyncio.sleep(0.8)
        except Exception as e:
            logger.error(f"Error video: {e}")

    if doc:
        try:
            doc_caption = (
                "🃏 ⚡ ⚡ ⚡ ⚡ ⚡ 🃏\n\n"
                "━━━ **ORIGINAL PANEL** ━━━\n\n"
                "⬇️ ⬇️ ⬇️ ⬇️   ⬇️ ⬇️ ⬇️ ⬇️\n\n"
                "🥖 **PREMIUM 🔮 ULTIMATE** 🥖"
            )
            await bot.send_document(
                chat_id,
                document=doc,
                caption=doc_caption
            )
            sent_count += 1
            await asyncio.sleep(0.8)
        except Exception as e:
            logger.error(f"Error doc: {e}")

    if aud:
        try:
            await bot.send_voice(
                chat_id,
                voice=aud,
                caption="**IMPORTANT VOICE** 📣 📣"
            )
            sent_count += 1
            await asyncio.sleep(0.8)
        except Exception as e:
            logger.error(f"Error voice: {e}")

    if vip_post:
        try:
            await bot.send_message(
                chat_id,
                text=vip_post,
                disable_web_page_preview=False
            )
            sent_count += 1
        except Exception as e:
            logger.error(f"Error vip post: {e}")

    return sent_count

@bot.on_message(filters.command("start") & filters.private)
async def handle_start(client, message):
    uid = message.from_user.id
    fname = message.from_user.first_name or "Member"
    uname = message.from_user.username or "No Username"

    db_add_user(uid, fname, uname)

    if uid == OWNER_ID:
        await message.reply_text(get_owner_text(), reply_markup=get_owner_keyboard())
        return

    if not is_bot_active():
        await message.reply_text("⚠️ Bot service is currently offline.")
        return

    sent = await send_welcome_assets(message.chat.id)
    if sent == 0:
        await message.reply_text("👋 Welcome! System updates are in progress.")

@bot.on_message(filters.video & filters.private)
async def auto_catch_video(client, message):
    if message.from_user.id == OWNER_ID:
        db_set_setting("WELCOME_VIDEO_ID", message.video.file_id)
        await message.reply_text("✅ **Activation Video Successfully Saved!**", reply_markup=get_owner_keyboard())

@bot.on_message(filters.document & filters.private)
async def auto_catch_document(client, message):
    if message.from_user.id == OWNER_ID:
        db_set_setting("WELCOME_DOC_ID", message.document.file_id)
        await message.reply_text("✅ **APK / File Successfully Saved!**", reply_markup=get_owner_keyboard())

@bot.on_message((filters.voice | filters.audio) & filters.private)
async def auto_catch_voice(client, message):
    if message.from_user.id == OWNER_ID:
        fid = message.voice.file_id if message.voice else message.audio.file_id
        db_set_setting("WELCOME_VOICE_ID", fid)
        await message.reply_text("✅ **Voice Recording Successfully Saved!**", reply_markup=get_owner_keyboard())

@bot.on_message(filters.text & filters.private & ~filters.command(["start"]))
async def text_input_handler(client, message):
    uid = message.from_user.id
    if uid == OWNER_ID and SYSTEM_STATE["WAITING_VIP_TEXT"]:
        db_set_setting("VIP_CHANNEL_POST", message.text)
        SYSTEM_STATE["WAITING_VIP_TEXT"] = False
        await message.reply_text("✅ **VIP Channel Post Saved!**", reply_markup=get_owner_keyboard())

@bot.on_callback_query()
async def callback_handler(client, query):
    uid = query.from_user.id
    if uid != OWNER_ID:
        await query.answer("Access Restricted.", show_alert=True)
        return

    d = query.data

    if d == "turn_on":
        db_set_setting("SERVICE_STATUS", "ON")
        await query.answer("Bot Lifetime ON!", show_alert=True)
        try:
            await query.message.edit_text(get_owner_text(), reply_markup=get_owner_keyboard())
        except MessageNotModified:
            pass

    elif d == "turn_off":
        db_set_setting("SERVICE_STATUS", "OFF")
        await query.answer("Bot STOPPED (OFF)!", show_alert=True)
        try:
            await query.message.edit_text(get_owner_text(), reply_markup=get_owner_keyboard())
        except MessageNotModified:
            pass

    elif d == "btn_list_users":
        users = db_get_all_users()
        if not users:
            await query.answer("Abhi tak koi user nahi hai.", show_alert=True)
            return

        await query.answer()
        btn_rows = []
        for u_id, fname, uname, jdate in users[:25]:
            u_title = f"👤 {fname} (@{uname})" if uname != "No Username" else f"👤 {fname} ({u_id})"
            btn_rows.append([InlineKeyboardButton(u_title, callback_data=f"view_user_{u_id}")])

        btn_rows.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data="back_to_dash")])

        await query.message.reply_text(
            f"👥 **TOTAL USERS LIST ({len(users)} Users):**\n"
            "Kissi bhi user ka logo dekhne ke liye uske naam par tap karein:",
            reply_markup=InlineKeyboardMarkup(btn_rows)
        )

    elif d.startswith("view_user_"):
        target_uid = int(d.replace("view_user_", ""))
        user_info = db_get_user(target_uid)

        if not user_info:
            await query.answer("User info not found.", show_alert=True)
            return

        u_id, fname, uname, jdate = user_info
        uname_display = f"@{uname}" if uname != "No Username" else "No Username Set"

        caption = (
            "╔════════════════════════════╗\n"
            "  👤 **USER PROFILE DETAILS** 👤\n"
            "╚════════════════════════════╝\n\n"
            f"🏷️ **Name:** {fname}\n"
            f"🔗 **Username:** {uname_display}\n"
            f"🆔 **Telegram ID:** `{u_id}`\n"
            f"📅 **Started Bot At:** `{jdate}`\n"
        )

        await query.answer("Fetching Profile Photo/Logo...")

        photo_sent = False
        try:
            async for photo in bot.get_chat_photos(target_uid, limit=1):
                await bot.send_photo(uid, photo=photo.file_id, caption=caption)
                photo_sent = True
                break
        except Exception as e:
            logger.warning(f"Could not fetch profile photo: {e}")

        if not photo_sent:
            caption += "\nℹ️ _(User has no public profile photo/logo)_"
            await bot.send_message(uid, text=caption)

    elif d == "back_to_dash":
        await query.answer()
        await query.message.reply_text(get_owner_text(), reply_markup=get_owner_keyboard())

    elif d == "test_video":
        vid = db_get_setting("WELCOME_VIDEO_ID")
        if vid:
            await query.answer("Sending Video...")
            await bot.send_video(uid, video=vid, caption="✅ **WATCH ACTIVATION VIDEO**")
        else:
            await query.answer("Video set nahi hai!", show_alert=True)

    elif d == "test_doc":
        doc = db_get_setting("WELCOME_DOC_ID")
        if doc:
            await query.answer("Sending APK...")
            await bot.send_document(uid, document=doc, caption="📁 **SAVED APK FILE**")
        else:
            await query.answer("APK set nahi hai!", show_alert=True)

    elif d == "test_voice":
        aud = db_get_setting("WELCOME_VOICE_ID")
        if aud:
            await query.answer("Sending Voice...")
            await bot.send_voice(uid, voice=aud, caption="🎙️ **SAVED VOICE NOTE**")
        else:
            await query.answer("Voice set nahi hai!", show_alert=True)

    elif d == "test_vip":
        vip = db_get_setting("VIP_CHANNEL_POST", DEFAULT_VIP_POST)
        await query.answer("Sending VIP Post...")
        await bot.send_message(uid, text=vip)

    elif d == "btn_set_vip_text":
        SYSTEM_STATE["WAITING_VIP_TEXT"] = True
        await query.answer()
        await query.message.reply_text("📢 **Apna naya Channel link aur message type karke bhej dein:**")

    elif d == "btn_test_full":
        await query.answer("Testing Full Bundle...")
        await send_welcome_assets(uid)

# 24/7 Anti-Sleep Keep-Alive Engine
async def keep_alive_ping_loop(port):
    await asyncio.sleep(10)
    url_local = f"http://127.0.0.1:{port}/"
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(url_local, timeout=5) as resp:
                    pass

                if RENDER_EXTERNAL_URL:
                    async with session.get(RENDER_EXTERNAL_URL, timeout=10) as resp2:
                        pass
                logger.info("24/7 Anti-Sleep Keep-Alive Ping Executed (Server Awake)")
            except Exception as e:
                logger.debug(f"Keep-alive ping info: {e}")

            await asyncio.sleep(300)

async def start_services():
    try:
        await bot.start()
        print("Master Bot Live and Ready 🚀", flush=True)

        app = web.Application()
        app.router.add_get('/', lambda r: web.Response(text="Bot is 24/7 Running Active"))
        runner = web.AppRunner(app)
        await runner.setup()

        port = int(os.environ.get("PORT", 8080))
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        print(f"Health server on port {port}", flush=True)

        asyncio.create_task(keep_alive_ping_loop(port))

        await idle()
    except Exception as e:
        logger.exception(f"Startup Failure: {e}")
        print(f"CRASH: {e}", file=sys.stderr, flush=True)

if __name__ == "__main__":
    loop.run_until_complete(start_services())
