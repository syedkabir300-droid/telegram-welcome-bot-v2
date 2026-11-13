# Event Loop Initialization (Python 3.14 Crash Fix)
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

# Verified Credentials (Updated)
API_ID = int(os.environ.get("API_ID", "36895505"))
API_HASH = os.environ.get("API_HASH", "e699980c3258bc0303a731e3c1594b97")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9267837824:AAEYKspi8C6LEp1SmGaIcq460ZHYalIQlaU")
OWNER_ID = int(os.environ.get("OWNER_ID", "6454597633"))

bot = Client("master_unified_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

DB_FILE = "master_database.db"
VIP_REGISTER_LINK = "https://bdg4.vip//#/register?invitationCode=1921324032297"

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
    "INCLUDE_VIP_LINK": False,
    "WAITING_ADMIN_INPUT": set(),
    "WAITING_DEL_ADMIN": set()
}

def get_dashboard_keyboard(user_id):
    if SYSTEM_STATE["GROUP_PROTECTION"]:
        mode_txt = "🟢 WITH VIP LINK ON" if SYSTEM_STATE["INCLUDE_VIP_LINK"] else "🟢 NORMAL ON"
    else:
        mode_txt = "🔴 OFF"

    buttons = [
        [
            InlineKeyboardButton("🛡️ START (NORMAL)", callback_data="start_prot_normal"),
            InlineKeyboardButton("🔗 START (WITH VIP LINK)", callback_data="start_prot_link")
        ],
        [
            InlineKeyboardButton(f"🛑 STOP PROTECTION [{mode_txt}]", callback_data="stop_protection")
        ],
        [
            InlineKeyboardButton("👤 ADD ADMIN", callback_data="btn_add_admin"),
            InlineKeyboardButton("🗑️ REMOVE ADMIN", callback_data="btn_delete_admin")
        ],
        [
            InlineKeyboardButton("📊 ADMINS & EXPIRY TABLE", callback_data="btn_show_table")
        ],
        [
            InlineKeyboardButton("📦 SEND PROMO KIT (VIDEO + APK + VOICE)", callback_data="btn_send_promo_kit")
        ],
        [
            InlineKeyboardButton("⚙️ SET PROMO MEDIA (VIDEO/APK/VOICE)", callback_data="btn_set_promo_media")
        ]
    ]

    return InlineKeyboardMarkup(buttons)

def get_dashboard_text(user_id):
    has_access, perms, exp_date = check_user_access(user_id)
    groups_count = len(db_get_all_groups())
    sub_admins = len(db_get_all_sub_admins())

    if SYSTEM_STATE["GROUP_PROTECTION"]:
        prot_status = "🟢 Active (VIP Link Mode)" if SYSTEM_STATE["INCLUDE_VIP_LINK"] else "🟢 Active (Normal Clean Mode)"
    else:
        prot_status = "🔴 Stopped"

    return (
        "╔════════════════════════════╗\n"
        "  👑 **TELANGANA MASTER BOT CONTROL** 👑\n"
        "╚════════════════════════════╝\n\n"
        f"👤 **Access Level:** `{'OWNER (Full)' if user_id == OWNER_ID else f'AGENT ({perms})'}`\n"
        f"⏳ **Validity:** `{exp_date if exp_date else 'Lifetime'}`\n"
        f"🏢 **Connected Chats:** `{groups_count}` Groups | 👮 **Sub-Admins:** `{sub_admins}`\n"
        f"🛡️ **Protection Mode:** {prot_status}\n\n"
        "**Neeche diye gaye buttons se operate karein:**"
    )

async def send_promo_kit_to_groups():
    groups = db_get_all_groups()
    vid_id = db_get_setting("PROMO_VIDEO")
    apk_id = db_get_setting("PROMO_APK")
    voice_id = db_get_setting("PROMO_VOICE")

    for cid, title in groups:
        try:
            if vid_id:
                await bot.send_video(
                    cid,
                    video=vid_id,
                    caption="✅ **WATCH ACTIVATION VIDEO** ✅"
                )
                await asyncio.sleep(1)

            apk_caption = "📁 **OFFICIAL APPLICATION / PANEL**"
            if SYSTEM_STATE["INCLUDE_VIP_LINK"]:
                apk_caption += f"\n\n👑 **VIP REGISTER LINK:**\n🔗 {VIP_REGISTER_LINK}"

            if apk_id:
                await bot.send_document(cid, document=apk_id, caption=apk_caption)
                await asyncio.sleep(1)

            if voice_id:
                await bot.send_voice(cid, voice=voice_id, caption="🎙️ **IMPORTANT VOICE NOTE**")

        except Exception as e:
            logger.error(f"Promo kit broadcast error in {title} ({cid}): {e}")

@bot.on_message(filters.command("start") & filters.private)
async def start_private_cmd(client, message):
    uid = message.from_user.id
    has_access, _, _ = check_user_access(uid)
    if not has_access:
        await message.reply_text("🔒 **Access Denied:** Aapke paas is bot ka access nahi hai. Owner se contact karein.")
        return
    await message.reply_text(get_dashboard_text(uid), reply_markup=get_dashboard_keyboard(uid))

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
                warn_msg = f"🛡️ **Security Alert:** {uname}, external links allow nahi hain!"
                if SYSTEM_STATE["INCLUDE_VIP_LINK"]:
                    warn_msg += f"\n\n👑 **Official VIP Link:**\n🔗 {VIP_REGISTER_LINK}"
                warn = await message.reply_text(warn_msg, disable_web_page_preview=True)
                await asyncio.sleep(5)
                await warn.delete()
            except Exception as e:
                logger.error(f"Auto delete fail: {e}")

# Media Upload Catchers (Only Video, APK/Doc, and Voice — No Photos)
@bot.on_message(filters.video & filters.private)
async def catch_promo_video(client, message):
    if message.from_user.id == OWNER_ID:
        db_set_setting("PROMO_VIDEO", message.video.file_id)
        await message.reply_text("✅ **Activation Video Saved Successfully!**", reply_markup=get_dashboard_keyboard(message.from_user.id))

@bot.on_message(filters.document & filters.private)
async def catch_promo_apk(client, message):
    if message.from_user.id == OWNER_ID:
        db_set_setting("PROMO_APK", message.document.file_id)
        await message.reply_text("✅ **APK / Document Saved Successfully!**", reply_markup=get_dashboard_keyboard(message.from_user.id))

@bot.on_message((filters.voice | filters.audio) & filters.private)
async def catch_promo_voice(client, message):
    fid = message.voice.file_id if message.voice else message.audio.file_id
    if message.from_user.id == OWNER_ID:
        db_set_setting("PROMO_VOICE", fid)
        await message.reply_text("✅ **Important Voice Note Saved Successfully!**", reply_markup=get_dashboard_keyboard(message.from_user.id))

@bot.on_message(filters.text & filters.private & ~filters.command(["start"]))
async def message_dispatcher(client, message):
    uid = message.from_user.id
    txt = message.text.strip()

    if uid in SYSTEM_STATE["WAITING_ADMIN_INPUT"]:
        SYSTEM_STATE["WAITING_ADMIN_INPUT"].remove(uid)
        parts = txt.split()
        if len(parts) < 4:
            await message.reply_text(
                "❌ **Format Galat Hai!**\nAise likh kar bhejein:\n`<Username/UserID> <GroupUsername/Link/ID> <Permissions> <Days>`\n\n"
                "**Example:**\n`@Aayan85 @mygroup ALL 30`"
            )
            return

        prog = await message.reply_text("⏳ **Verifying...**")
        raw_user, raw_group, perms, raw_days = parts[0], parts[1], parts[2].upper(), parts[3]

        target_uid = None
        target_uname = raw_user.replace("@", "").strip()
        try:
            if raw_user.replace("-", "").isdigit():
                target_uid = int(raw_user)
                try:
                    u_obj = await bot.get_users(target_uid)
                    target_uname = u_obj.username or u_obj.first_name
                except Exception:
                    pass
            else:
                u_obj = await bot.get_users(raw_user)
                target_uid = u_obj.id
                target_uname = u_obj.username or u_obj.first_name
        except Exception:
            await prog.edit_text(f"❌ **User nahi mila:** `{raw_user}`.")
            return

        target_gid = None
        target_gtitle = raw_group
        clean_grp = raw_group.replace("https://t.me/", "").replace("t.me/", "")
        try:
            if clean_grp.replace("-", "").isdigit():
                target_gid = int(clean_grp)
                try:
                    g_obj = await bot.get_chat(target_gid)
                    target_gtitle = g_obj.title
                except Exception:
                    pass
            else:
                g_obj = await bot.get_chat(clean_grp)
                target_gid = g_obj.id
                target_gtitle = g_obj.title
        except Exception:
            if clean_grp.replace("-", "").isdigit():
                target_gid = int(clean_grp)
            else:
                await prog.edit_text(f"❌ **Group nahi mila:** `{raw_group}`.")
                return

        try:
            days = int(raw_days)
            exp_date = (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")

            db_add_sub_admin(target_uid, target_uname, target_gid, perms, exp_date)
            db_add_group(target_gid, target_gtitle)

            await prog.edit_text(
                f"✅ **Sub-Admin Successfully Added!**\n\n"
                f"👤 **Admin:** @{target_uname} (`{target_uid}`)\n"
                f"🏢 **Group:** {target_gtitle} (`{target_gid}`)\n"
                f"🛡️ **Permissions:** `{perms}`\n"
                f"📅 **Validity:** `{exp_date}` ({days} Din)",
                reply_markup=get_dashboard_keyboard(uid)
            )
        except Exception as ex:
            await prog.edit_text(f"❌ Error: {ex}")
        return

    if uid in SYSTEM_STATE["WAITING_DEL_ADMIN"]:
        SYSTEM_STATE["WAITING_DEL_ADMIN"].remove(uid)
        db_remove_sub_admin_by_identifier(txt)
        await message.reply_text(f"🗑️ **Admin `{txt}` ka access cancel kar diya gaya hai.**", reply_markup=get_dashboard_keyboard(uid))
        return

@bot.on_callback_query()
async def callback_dispatcher(client, query):
    d = query.data
    uid = query.from_user.id
    has_access, perms, _ = check_user_access(uid)

    if not has_access:
        await query.answer("Access Denied! Contact Owner.", show_alert=True)
        return

    if d == "start_prot_normal":
        SYSTEM_STATE["GROUP_PROTECTION"] = True
        SYSTEM_STATE["INCLUDE_VIP_LINK"] = False
        await query.answer("🛡️ Normal Protection Shuru (Bina Register Link)!", show_alert=True)
        try:
            await query.message.edit_text(get_dashboard_text(uid), reply_markup=get_dashboard_keyboard(uid))
        except MessageNotModified:
            pass
        return

    elif d == "start_prot_link":
        SYSTEM_STATE["GROUP_PROTECTION"] = True
        SYSTEM_STATE["INCLUDE_VIP_LINK"] = True
        await query.answer("🔗 VIP Link Protection Shuru (Register Link Ke Saath)!", show_alert=True)
        try:
            await query.message.edit_text(get_dashboard_text(uid), reply_markup=get_dashboard_keyboard(uid))
        except MessageNotModified:
            pass
        return

    elif d == "stop_protection":
        SYSTEM_STATE["GROUP_PROTECTION"] = False
        await query.answer("🛑 Protection Band kar di gayi!", show_alert=True)
        try:
            await query.message.edit_text(get_dashboard_text(uid), reply_markup=get_dashboard_keyboard(uid))
        except MessageNotModified:
            pass
        return

    elif d == "btn_add_admin":
        if uid != OWNER_ID:
            await query.answer("Sirf Owner Admin add kar sakta hai!", show_alert=True)
            return
        await query.answer()
        await query.message.reply_text(
            "👤 **ADD ADMIN BY USERNAME:**\n\nFormat mein reply karein:\n`<Username> <GroupLink/Username> <Permissions> <Days>`\n\n"
            "**Example:**\n`@Aayan85 @mygroup ALL 30`"
        )
        SYSTEM_STATE["WAITING_ADMIN_INPUT"].add(uid)
        return

    elif d == "btn_delete_admin":
        if uid != OWNER_ID:
            await query.answer("Sirf Owner Admin remove kar sakta hai!", show_alert=True)
            return
        SYSTEM_STATE["WAITING_DEL_ADMIN"].add(uid)
        await query.answer()
        await query.message.reply_text("🗑️ Jis Admin ko nikalna hai uska **@username** ya **User ID** bhejein:")
        return

    elif d == "btn_show_table":
        sub_admins = db_get_all_sub_admins()
        txt = "📊 **ADMINS & EXPIRY TABLE:**\n════════════════════════════\n"
        txt += f"👑 **MAIN OWNER:** `{OWNER_ID}` [LIFETIME]\n\n"
        if not sub_admins:
            txt += "_Abhi koi Sub-Admin active nahi hai._\n"
        else:
            for a_uid, a_uname, a_gid, a_perms, a_exp in sub_admins:
                txt += f"• **Admin:** @{a_uname}\n  └ Group: `{a_gid}` | Access: **{a_perms}** | Expiry: `{a_exp}`\n\n"
        await query.message.reply_text(txt)
        await query.answer()
        return

    elif d == "btn_send_promo_kit":
        await query.answer("📦 Promo Kit (Video + APK + Voice) send ki ja rahi hai...", show_alert=True)
        await send_promo_kit_to_groups()
        await query.message.reply_text("✅ **Promo Kit Successfully Posted in all registered channels/groups!**")
        return

    elif d == "btn_set_promo_media":
        await query.answer()
        await query.message.reply_text(
            "⚙️ **SET PROMO MEDIA FILES:**\n\n"
            "1. Bot ke DM me direct koi bhi **Video** bhej dein, wo Activation Video ban jayegi.\n"
            "2. Bot ke DM me direct koi bhi **APK / Document** bhejein, wo Panel APK ban jayegi.\n"
            "3. Bot ke DM me direct koi bhi **Voice Note** record karke bhejein, wo Important Voice ban jayegi."
        )
        return

async def start_services():
    try:
        await bot.start()
        print("Telangana Master Bot Live 🚀", flush=True)

        app = web.Application()
        app.router.add_get('/', lambda r: web.Response(text="Bot 24/7 Running"))
        runner = web.AppRunner(app)
        await runner.setup()

        port = int(os.environ.get("PORT", 8080))
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        print(f"Health server listening on {port}", flush=True)

        await idle()
    except Exception as e:
        logger.exception(f"Fatal Startup Error: {e}")
        print(f"CRASH OCCURRED: {e}", file=sys.stderr, flush=True)

if __name__ == "__main__":
    loop.run_until_complete(start_services())
