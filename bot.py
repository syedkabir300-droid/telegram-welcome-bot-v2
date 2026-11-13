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

# Updated Verified Credentials
API_ID = int(os.environ.get("API_ID", "36895505"))
API_HASH = os.environ.get("API_HASH", "e699980c3258bc0303a731e3c1594b97")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9267837824:AAEYKspi8C6LEp1SmGaIcq460ZHYalIQlaU")
OWNER_ID = int(os.environ.get("OWNER_ID", "6454597633"))

RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

bot = Client("master_bot_9267837824", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

DB_FILE = "master_database.db"

DEFAULT_VIP_POST = (
    "👑 **TELANGANA SURE SHOT VIP CHANNEL** 👑\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "🔥 **Welcome to Our Official VIP Community** 🔥\n\n"
    "🎯 **Join VIP Telegram Channel:**\n"
    "👉 https://t.me/+GMTnuLiWcr4wOTQ1\n\n"
    "🔗 **Official Link:**\n"
    "👉 https://bdglink.com//#/register?invitationCode=1921324032297\n"
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
    c.execute('''CREATE TABLE IF NOT EXISTS groups (
        chat_id INTEGER PRIMARY KEY,
        title TEXT
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

def db_add_group(chat_id, title):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO groups VALUES (?, ?)", (chat_id, title))
    conn.commit()
    conn.close()

def db_get_all_groups():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT chat_id, title FROM groups")
    rows = c.fetchall()
    conn.close()
    return rows

def db_add_sub_admin(user_id, username, group_id, perms, expiry_date):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO sub_admins VALUES (?, ?, ?, ?, ?)", (user_id, username, group_id, perms, expiry_date))
    conn.commit()
    conn.close()

def db_get_all_sub_admins():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id, username, group_id, permissions, expiry_date FROM sub_admins")
    rows = c.fetchall()
    conn.close()
    return rows

def db_remove_sub_admin_by_identifier(ident):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    ident = str(ident).replace("@", "").strip()
    if ident.isdigit():
        c.execute("DELETE FROM sub_admins WHERE user_id = ?", (int(ident),))
    else:
        c.execute("DELETE FROM sub_admins WHERE LOWER(username) = LOWER(?)", (ident,))
    conn.commit()
    conn.close()

def check_admin_access(user_id):
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
            conn2 = sqlite3.connect(DB_FILE)
            conn2.cursor().execute("DELETE FROM sub_admins WHERE user_id = ?", (user_id,))
            conn2.commit()
            conn2.close()
            return False, None, None
    except Exception:
        pass
    return True, perms, exp_str

if not db_get_setting("SERVICE_STATUS"):
    db_set_setting("SERVICE_STATUS", "ON")

SYSTEM_STATE = {
    "WAITING_VIP_TEXT": False,
    "WAITING_ADMIN_INPUT": set(),
    "WAITING_DEL_ADMIN": set(),
    "GROUP_PROTECTION": False,
    "INCLUDE_VIP_LINK": False
}

def is_bot_active():
    return db_get_setting("SERVICE_STATUS", "ON") == "ON"

def get_owner_keyboard():
    status_icon = "🟢 ON (24/7 ACTIVE)" if is_bot_active() else "🔴 OFF (STOPPED)"
    toggle_target = "turn_off" if is_bot_active() else "turn_on"

    if SYSTEM_STATE["GROUP_PROTECTION"]:
        prot_label = "🟢 VIP LINK ON" if SYSTEM_STATE["INCLUDE_VIP_LINK"] else "🟢 NORMAL ON"
    else:
        prot_label = "🔴 OFF"

    vid_status = "✅ ACTIVE" if db_get_setting("WELCOME_VIDEO_ID") else "❌ NOT SET"
    doc_status = "✅ ACTIVE" if db_get_setting("WELCOME_DOC_ID") else "❌ NOT SET"
    voice_status = "✅ ACTIVE" if db_get_setting("WELCOME_VOICE_ID") else "❌ NOT SET"
    total_users = len(db_get_all_users())

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"⚡ BOT STATUS: [{status_icon}]", callback_data=toggle_target)
        ],
        [
            InlineKeyboardButton("🛡️ START (NORMAL)", callback_data="start_prot_normal"),
            InlineKeyboardButton("🔗 START (VIP LINK)", callback_data="start_prot_link")
        ],
        [
            InlineKeyboardButton(f"🛑 STOP PROTECTION [{prot_label}]", callback_data="stop_protection")
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
            InlineKeyboardButton("👤 ADD ADMIN", callback_data="btn_add_admin"),
            InlineKeyboardButton("🗑️ REMOVE ADMIN", callback_data="btn_delete_admin")
        ],
        [
            InlineKeyboardButton("📊 ADMINS TABLE", callback_data="btn_show_table"),
            InlineKeyboardButton(f"👥 USERS ({total_users})", callback_data="btn_list_users")
        ],
        [
            InlineKeyboardButton("✏️ SET VIP TEXT & LINKS", callback_data="btn_set_vip_text"),
            InlineKeyboardButton("🚀 TEST FULL PACKAGE", callback_data="btn_test_full")
        ],
        [
            InlineKeyboardButton("📦 BROADCAST TO GROUPS", callback_data="btn_broadcast_groups")
        ]
    ])

def get_owner_text():
    status_label = "🟢 24/7 NON-STOP CLOUD RUNNING" if is_bot_active() else "🔴 STOPPED (OFF)"
    total_users = len(db_get_all_users())
    groups_count = len(db_get_all_groups())
    sub_admins = len(db_get_all_sub_admins())

    if SYSTEM_STATE["GROUP_PROTECTION"]:
        prot_status = "🟢 Active (VIP Link Mode)" if SYSTEM_STATE["INCLUDE_VIP_LINK"] else "🟢 Active (Normal Clean Mode)"
    else:
        prot_status = "🔴 Stopped"

    return (
        "╔════════════════════════════╗\n"
        "  👑 **AUTOMATED WELCOME & GUARD BOT** 👑\n"
        "╚════════════════════════════╝\n\n"
        f"⚡ **Cloud Status:** `{status_label}`\n"
        f"🛡️ **Group Guard:** {prot_status}\n"
        f"🏢 **Groups:** `{groups_count}` | 👮 **Admins:** `{sub_admins}` | 👥 **Users:** `{total_users}`\n\n"
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
                caption="✅ **WATCH ACTIVATION VIDEO** ✅\n\n😍 **LIVE GUIDE & SETUP** 😍"
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
async def handle_start_private(client, message):
    uid = message.from_user.id
    fname = message.from_user.first_name or "Member"
    uname = message.from_user.username or "No Username"

    db_add_user(uid, fname, uname)

    has_access, _, _ = check_admin_access(uid)
    if has_access:
        await message.reply_text(get_owner_text(), reply_markup=get_owner_keyboard())
        return

    if not is_bot_active():
        await message.reply_text("⚠️ Bot service is currently offline.")
        return

    sent = await send_welcome_assets(message.chat.id)
    if sent == 0:
        await message.reply_text("👋 Welcome! System updates are in progress.")

@bot.on_message(filters.command("start") & (filters.group | filters.channel))
async def handle_start_group(client, message):
    db_add_group(message.chat.id, message.chat.title or "Telegram Group")
    try:
        ack = await message.reply_text("✅ **Group Registered & Connected to Master Bot!**")
        await asyncio.sleep(3)
        await ack.delete()
    except Exception as e:
        logger.warning(f"Group start ack error: {e}")

@bot.on_message(filters.group | filters.channel)
async def auto_group_guard(client, message):
    if message.chat:
        db_add_group(message.chat.id, message.chat.title or "Telegram Group")

    if not SYSTEM_STATE["GROUP_PROTECTION"]:
        return

    if message.chat.type in ["group", "supergroup"]:
        if message.from_user and message.from_user.id == OWNER_ID:
            return
        text = message.text or message.caption or ""
        forbidden = ["t.me/", "telegram.me/", "http://", "https://", "joinchat", "@"]
        if any(w in text.lower() for w in forbidden):
            try:
                await message.delete()
                uname = message.from_user.mention if message.from_user else "Member"
                warn_msg = f"🛡️ **Security Alert:** {uname}, external links allow nahi hain!"
                if SYSTEM_STATE["INCLUDE_VIP_LINK"]:
                    vip_text = db_get_setting("VIP_CHANNEL_POST", DEFAULT_VIP_POST)
                    warn_msg += f"\n\n{vip_text}"
                warn = await message.reply_text(warn_msg, disable_web_page_preview=True)
                await asyncio.sleep(5)
                await warn.delete()
            except Exception as e:
                logger.error(f"Auto delete fail: {e}")

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
    txt = message.text.strip()

    if uid == OWNER_ID and SYSTEM_STATE["WAITING_VIP_TEXT"]:
        db_set_setting("VIP_CHANNEL_POST", message.text)
        SYSTEM_STATE["WAITING_VIP_TEXT"] = False
        await message.reply_text("✅ **VIP Channel Post Saved!**", reply_markup=get_owner_keyboard())
        return

    if uid in SYSTEM_STATE["WAITING_ADMIN_INPUT"]:
        SYSTEM_STATE["WAITING_ADMIN_INPUT"].remove(uid)
        parts = txt.split()
        if len(parts) < 4:
            await message.reply_text("❌ Format:\n`<Username/ID> <GroupLink/ID> <Permissions> <Days>`\nEx: `@username @group ALL 30`")
            return

        prog = await message.reply_text("⏳ Verifying...")
        raw_user, raw_group, perms, raw_days = parts[0], parts[1], parts[2].upper(), parts[3]

        target_uid = None
        target_uname = raw_user.replace("@", "").strip()
        try:
            if raw_user.replace("-", "").isdigit():
                target_uid = int(raw_user)
            else:
                u_obj = await bot.get_users(raw_user)
                target_uid = u_obj.id
                target_uname = u_obj.username or u_obj.first_name
        except Exception:
            await prog.edit_text(f"❌ User nahi mila: `{raw_user}`")
            return

        clean_grp = raw_group.replace("https://t.me/", "").replace("t.me/", "")
        try:
            if clean_grp.replace("-", "").isdigit():
                target_gid = int(clean_grp)
                target_gtitle = raw_group
            else:
                g_obj = await bot.get_chat(clean_grp)
                target_gid = g_obj.id
                target_gtitle = g_obj.title
        except Exception:
            target_gid = int(clean_grp) if clean_grp.replace("-", "").isdigit() else 0
            target_gtitle = raw_group

        try:
            days = int(raw_days)
            exp_date = (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")
            db_add_sub_admin(target_uid, target_uname, target_gid, perms, exp_date)
            db_add_group(target_gid, target_gtitle)
            await prog.edit_text(
                f"✅ **Admin Added:** @{target_uname} (`{target_uid}`)\n🏢 **Group:** {target_gtitle}\n📅 **Expiry:** `{exp_date}`",
                reply_markup=get_owner_keyboard()
            )
        except Exception as e:
            await prog.edit_text(f"❌ Error: {e}")
        return

    if uid in SYSTEM_STATE["WAITING_DEL_ADMIN"]:
        SYSTEM_STATE["WAITING_DEL_ADMIN"].remove(uid)
        db_remove_sub_admin_by_identifier(txt)
        await message.reply_text(f"🗑️ Admin `{txt}` removed.", reply_markup=get_owner_keyboard())
        return

@bot.on_callback_query()
async def callback_handler(client, query):
    uid = query.from_user.id
    has_access, _, _ = check_admin_access(uid)
    if not has_access:
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

    elif d == "start_prot_normal":
        SYSTEM_STATE["GROUP_PROTECTION"] = True
        SYSTEM_STATE["INCLUDE_VIP_LINK"] = False
        await query.answer("🛡️ Normal Protection Shuru!", show_alert=True)
        try:
            await query.message.edit_text(get_owner_text(), reply_markup=get_owner_keyboard())
        except MessageNotModified:
            pass

    elif d == "start_prot_link":
        SYSTEM_STATE["GROUP_PROTECTION"] = True
        SYSTEM_STATE["INCLUDE_VIP_LINK"] = True
        await query.answer("🔗 VIP Link Protection Shuru!", show_alert=True)
        try:
            await query.message.edit_text(get_owner_text(), reply_markup=get_owner_keyboard())
        except MessageNotModified:
            pass

    elif d == "stop_protection":
        SYSTEM_STATE["GROUP_PROTECTION"] = False
        await query.answer("🛑 Protection Band kar di gayi!", show_alert=True)
        try:
            await query.message.edit_text(get_owner_text(), reply_markup=get_owner_keyboard())
        except MessageNotModified:
            pass

    elif d == "btn_add_admin":
        if uid != OWNER_ID:
            await query.answer("Sirf Owner admin add kar sakta hai!", show_alert=True)
            return
        SYSTEM_STATE["WAITING_ADMIN_INPUT"].add(uid)
        await query.answer()
        await query.message.reply_text("👤 Format mein bhejein:\n`<@Username> <@GroupLink> <Permissions> <Days>`\nEx: `@Aayan85 @mygroup ALL 30`")

    elif d == "btn_delete_admin":
        if uid != OWNER_ID:
            await query.answer("Sirf Owner remove kar sakta hai!", show_alert=True)
            return
        SYSTEM_STATE["WAITING_DEL_ADMIN"].add(uid)
        await query.answer()
        await query.message.reply_text("🗑️ Jis Admin ko hatana hai uska **@username** ya **User ID** bhejein:")

    elif d == "btn_show_table":
        sub_admins = db_get_all_sub_admins()
        txt = "📊 **ADMINS & EXPIRY TABLE:**\n════════════════════════════\n"
        txt += f"👑 **OWNER:** `{OWNER_ID}` [LIFETIME]\n\n"
        if not sub_admins:
            txt += "_Koi sub-admin active nahi hai._\n"
        else:
            for a_uid, a_uname, a_gid, a_perms, a_exp in sub_admins:
                txt += f"• **Admin:** @{a_uname} (`{a_uid}`)\n  └ Group: `{a_gid}` | Perms: **{a_perms}** | Expiry: `{a_exp}`\n\n"
        await query.message.reply_text(txt)
        await query.answer()

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
            f"👥 **TOTAL USERS LIST ({len(users)} Users):**\nKisi bhi user par tap karein:",
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
        await query.answer("Fetching Details...")
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

    elif d == "btn_broadcast_groups":
        groups = db_get_all_groups()
        if not groups:
            await query.answer("Koi group registered nahi hai! Group me /start likhein.", show_alert=True)
            return
        await query.answer("Broadcasting to all groups...", show_alert=True)
        for cid, title in groups:
            await send_welcome_assets(cid)
        await query.message.reply_text("✅ **Full Package sabhi connected groups me bhej diya gaya hai!**")

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
            except Exception as e:
                logger.debug(f"Keep-alive ping info: {e}")
            await asyncio.sleep(300)

async def start_services():
    try:
        # Clear any old webhook before starting polling
        async with aiohttp.ClientSession() as s:
            await s.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true")

        await bot.start()
        print("Master Bot Live with New Credentials 🚀", flush=True)

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
