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
from datetime import datetime, timezone, timedelta
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified
from aiohttp import web

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("TelanganaMasterBot")

# Verified New Credentials
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
            conn2 = sqlite3.connect(DB_FILE)
            conn2.cursor().execute("DELETE FROM sub_admins WHERE user_id = ?", (user_id,))
            conn2.commit()
            conn2.close()
            return False, None, None
    except Exception:
        pass
    return True, perms, exp_str

SYSTEM_STATE = {
    "GROUP_PROTECTION": False,
    "WAITING_ADMIN_INPUT": set(),
    "WAITING_DEL_ADMIN": set(),
    "SET_PHOTO_MODE": None,
    "UPLOAD_STATE": {}
}

def get_dashboard_keyboard(user_id):
    prot_st = "🟢 24H ON" if SYSTEM_STATE["GROUP_PROTECTION"] else "🔴 OFF"

    big_st = "✅" if db_get_setting("BIG_PHOTO") else "❌"
    small_st = "✅" if db_get_setting("SMALL_PHOTO") else "❌"
    vid_st = "✅" if db_get_setting("CUSTOM_VIDEO_ID") else "❌"
    doc_st = "✅" if db_get_setting("CUSTOM_DOC_ID") else "❌"

    buttons = [
        [
            InlineKeyboardButton(f"🛡️ ANTI-LINK GUARD [{prot_st}]", callback_data="toggle_guard")
        ],
        [
            InlineKeyboardButton(f"🖼️ SET BANNER 1 [{big_st}]", callback_data="btn_set_big_photo"),
            InlineKeyboardButton(f"🖼️ SET BANNER 2 [{small_st}]", callback_data="btn_set_small_photo")
        ],
        [
            InlineKeyboardButton(f"📹 SET VIDEO [{vid_st}]", callback_data="btn_upload_video"),
            InlineKeyboardButton(f"📁 SET FILE/APK [{doc_st}]", callback_data="btn_upload_doc")
        ],
        [
            InlineKeyboardButton("📦 BROADCAST MEDIA KIT", callback_data="btn_send_media_kit")
        ],
        [
            InlineKeyboardButton("👤 ADD ADMIN", callback_data="btn_add_admin"),
            InlineKeyboardButton("🗑️ REMOVE ADMIN", callback_data="btn_delete_admin")
        ],
        [
            InlineKeyboardButton("📊 ADMINS & EXPIRY TABLE", callback_data="btn_show_table"),
            InlineKeyboardButton("🏢 CONNECTED CHATS", callback_data="list_groups_btn")
        ]
    ]

    return InlineKeyboardMarkup(buttons)

def get_dashboard_text(user_id):
    has_access, perms, exp_date = check_user_access(user_id)
    groups_count = len(db_get_all_groups())
    sub_admins = len(db_get_all_sub_admins())
    prot_status = "🟢 Active (Deleting Forbidden Links)" if SYSTEM_STATE["GROUP_PROTECTION"] else "🔴 Stopped"

    return (
        "╔════════════════════════════╗\n"
        "  👑 **TELANGANA MASTER BOT - CONTROL PANEL** 👑\n"
        "╚════════════════════════════╝\n\n"
        f"👤 **Role:** `{'OWNER (Full)' if user_id == OWNER_ID else f'ADMIN ({perms})'}`\n"
        f"⏳ **Validity:** `{exp_date if exp_date else 'Lifetime'}`\n"
        f"🏢 **Connected Chats:** `{groups_count}` | 👮 **Sub-Admins:** `{sub_admins}`\n"
        f"🛡️ **Anti-Link Guard:** {prot_status}\n\n"
        "Neeche buttons se media upload karein aur settings manage karein:"
    )

async def deliver_custom_bundle(target_chat_id):
    vid = db_get_setting("CUSTOM_VIDEO_ID")
    doc = db_get_setting("CUSTOM_DOC_ID")
    p1 = db_get_setting("BIG_PHOTO")
    p2 = db_get_setting("SMALL_PHOTO")

    sent_any = False
    if p1:
        try:
            await bot.send_photo(target_chat_id, photo=p1, caption="📢 **OFFICIAL ANNOUNCEMENT**")
            sent_any = True
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Send photo error: {e}")

    if vid:
        try:
            await bot.send_video(target_chat_id, video=vid, caption="✅ **ACTIVATION VIDEO**")
            sent_any = True
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Send video error: {e}")

    if doc:
        try:
            await bot.send_document(target_chat_id, document=doc, caption="📁 **OFFICIAL FILE / APPLICATION**")
            sent_any = True
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Send doc error: {e}")

    return sent_any

@bot.on_message(filters.command("start") & filters.private)
async def start_private_cmd(client, message):
    uid = message.from_user.id
    has_access, _, _ = check_user_access(uid)

    if has_access:
        await message.reply_text(get_dashboard_text(uid), reply_markup=get_dashboard_keyboard(uid))
        return

    sent = await deliver_custom_bundle(message.chat.id)
    if not sent:
        await message.reply_text("👋 Welcome! Bot media is currently being initialized.")

@bot.on_message(filters.command("start") & (filters.group | filters.channel))
async def start_group_cmd(client, message):
    db_add_group(message.chat.id, message.chat.title or "Telegram Chat")
    try:
        ack = await message.reply_text("🛡️ **Group registered successfully.**")
        await asyncio.sleep(3)
        await ack.delete()
    except Exception:
        pass

@bot.on_message(filters.group | filters.channel)
async def auto_group_guard(client, message):
    if message.chat:
        db_add_group(message.chat.id, message.chat.title or "Telegram Chat")

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
                warn = await message.reply_text(f"🛡️ **Security Alert:** {uname}, external links allow nahi hain!")
                await asyncio.sleep(4)
                await warn.delete()
            except Exception as e:
                logger.error(f"Auto delete fail: {e}")

@bot.on_message(filters.photo & filters.private)
async def auto_save_photo(client, message):
    uid = message.from_user.id
    fid = message.photo.file_id
    mode = SYSTEM_STATE.get("SET_PHOTO_MODE")
    if mode == "BIG" or uid == OWNER_ID:
        db_set_setting("BIG_PHOTO", fid)
        SYSTEM_STATE["SET_PHOTO_MODE"] = None
        await message.reply_text("✅ **Banner 1 Photo successfully save ho gayi!**", reply_markup=get_dashboard_keyboard(uid))
    elif mode == "SMALL":
        db_set_setting("SMALL_PHOTO", fid)
        SYSTEM_STATE["SET_PHOTO_MODE"] = None
        await message.reply_text("✅ **Banner 2 Photo successfully save ho gayi!**", reply_markup=get_dashboard_keyboard(uid))
    else:
        await message.reply_text("📸 Photo save karne ke liye pehle Dashboard se Banner button click karein.")

@bot.on_message(filters.video & filters.private)
async def catch_video_upload(client, message):
    uid = message.from_user.id
    if SYSTEM_STATE["UPLOAD_STATE"].get(uid) == "VIDEO" or uid == OWNER_ID:
        db_set_setting("CUSTOM_VIDEO_ID", message.video.file_id)
        SYSTEM_STATE["UPLOAD_STATE"].pop(uid, None)
        await message.reply_text("✅ **Video successfully save ho chuki hai!**", reply_markup=get_dashboard_keyboard(uid))

@bot.on_message(filters.document & filters.private)
async def catch_doc_upload(client, message):
    uid = message.from_user.id
    if SYSTEM_STATE["UPLOAD_STATE"].get(uid) == "DOC" or uid == OWNER_ID:
        db_set_setting("CUSTOM_DOC_ID", message.document.file_id)
        SYSTEM_STATE["UPLOAD_STATE"].pop(uid, None)
        await message.reply_text("✅ **Document/File successfully save ho chuki hai!**", reply_markup=get_dashboard_keyboard(uid))

@bot.on_message(filters.text & filters.private & ~filters.command(["start"]))
async def message_dispatcher(client, message):
    uid = message.from_user.id
    txt = message.text.strip()

    if uid in SYSTEM_STATE["WAITING_ADMIN_INPUT"]:
        SYSTEM_STATE["WAITING_ADMIN_INPUT"].remove(uid)
        parts = txt.split()
        if len(parts) < 4:
            await message.reply_text("❌ Format: `<@Username> <@GroupLink> <Permissions> <Days>`\nEx: `@user @mygroup ALL 30`")
            return

        prog = await message.reply_text("⏳ Verifying details...")
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
                g_obj = await bot.get_chat(target_gid)
                target_gtitle = g_obj.title
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
                f"✅ **Admin Added:** @{target_uname}\n🏢 **Group:** {target_gtitle}\n📅 **Expiry:** `{exp_date}` ({days} Din)",
                reply_markup=get_dashboard_keyboard(uid)
            )
        except Exception as ex:
            await prog.edit_text(f"❌ Error: {ex}")
        return

    if uid in SYSTEM_STATE["WAITING_DEL_ADMIN"]:
        SYSTEM_STATE["WAITING_DEL_ADMIN"].remove(uid)
        db_remove_sub_admin_by_identifier(txt)
        await message.reply_text(f"🗑️ Admin `{txt}` access revoked.", reply_markup=get_dashboard_keyboard(uid))
        return

@bot.on_callback_query()
async def callback_dispatcher(client, query):
    d = query.data
    uid = query.from_user.id
    has_access, perms, _ = check_user_access(uid)

    if not has_access:
        await query.answer("Access Denied!", show_alert=True)
        return

    if d == "toggle_guard":
        SYSTEM_STATE["GROUP_PROTECTION"] = not SYSTEM_STATE["GROUP_PROTECTION"]
        st = "ON" if SYSTEM_STATE["GROUP_PROTECTION"] else "OFF"
        await query.answer(f"Anti-Link Guard {st}!", show_alert=True)
        try:
            await query.message.edit_text(get_dashboard_text(uid), reply_markup=get_dashboard_keyboard(uid))
        except MessageNotModified:
            pass
        return

    elif d == "btn_set_big_photo":
        SYSTEM_STATE["SET_PHOTO_MODE"] = "BIG"
        await query.answer()
        await query.message.reply_text("📸 **Chat mein Banner 1 photo bhej kar save karein.**")
        return

    elif d == "btn_set_small_photo":
        SYSTEM_STATE["SET_PHOTO_MODE"] = "SMALL"
        await query.answer()
        await query.message.reply_text("📸 **Chat mein Banner 2 photo bhej kar save karein.**")
        return

    elif d == "btn_upload_video":
        SYSTEM_STATE["UPLOAD_STATE"][uid] = "VIDEO"
        await query.answer()
        await query.message.reply_text("📹 **Chat mein Video bhej dein, bot use save kar lega.**")
        return

    elif d == "btn_upload_doc":
        SYSTEM_STATE["UPLOAD_STATE"][uid] = "DOC"
        await query.answer()
        await query.message.reply_text("📁 **Chat mein koi bhi File / APK bhej dein, bot save kar lega.**")
        return

    elif d == "btn_send_media_kit":
        await query.answer("Broadcast bheja ja raha hai...", show_alert=True)
        groups = db_get_all_groups()
        for cid, title in groups:
            await deliver_custom_bundle(cid)
        await query.message.reply_text("✅ **Media kit registered groups me send ho chuki hai.**")
        return

    elif d == "btn_add_admin":
        if uid != OWNER_ID:
            await query.answer("Sirf Owner admin add kar sakta hai!", show_alert=True)
            return
        SYSTEM_STATE["WAITING_ADMIN_INPUT"].add(uid)
        await query.answer()
        await query.message.reply_text("👤 Format me bhejein:\n`<@Username> <@GroupLink> <Permissions> <Days>`\nEx: `@user @mygroup ALL 30`")
        return

    elif d == "btn_delete_admin":
        if uid != OWNER_ID:
            await query.answer("Sirf Owner remove kar sakta hai!", show_alert=True)
            return
        SYSTEM_STATE["WAITING_DEL_ADMIN"].add(uid)
        await query.answer()
        await query.message.reply_text("🗑️ Jis Admin ko nikalna hai uska **@username** ya ID bhejein:")
        return

    elif d == "btn_show_table":
        sub_admins = db_get_all_sub_admins()
        txt = "📊 **ACTIVE ADMINS & EXPIRY:**\n════════════════════════════\n"
        txt += f"👑 **OWNER:** `{OWNER_ID}` [LIFETIME]\n\n"
        if not sub_admins:
            txt += "_Koi sub-admin active nahi hai._\n"
        else:
            for a_uid, a_uname, a_gid, a_perms, a_exp in sub_admins:
                txt += f"• **Admin:** @{a_uname}\n  └ Group: `{a_gid}` | Access: **{a_perms}** | Expiry: `{a_exp}`\n\n"
        await query.message.reply_text(txt)
        await query.answer()
        return

    elif d == "list_groups_btn":
        groups = db_get_all_groups()
        if not groups:
            await query.answer("Koi group registered nahi hai.", show_alert=True)
            return
        txt = "🏢 **CONNECTED GROUPS:**\n════════════════════════════\n"
        for cid, title in groups:
            txt += f"• **{title}** (`{cid}`)\n"
        await query.message.reply_text(txt)
        await query.answer()
        return

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
