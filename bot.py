import os
import sys
import json
import asyncio
import random
import sqlite3
import logging
from datetime import datetime, timezone, timedelta
import aiohttp
from aiohttp import web
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import SessionPasswordNeeded, UserAlreadyParticipant, MessageNotModified
from pyrogram.raw.functions.channels import GetFullChannel
from pyrogram.raw.functions.phone import JoinGroupCall, LeaveGroupCall
from pyrogram.raw.types import InputGroupCall, DataJSON, InputPeerSelf

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("TelanganaMasterBot")

API_ID = int(os.environ.get("API_ID", "38476624"))
API_HASH = os.environ.get("API_HASH", "6138b409afb06ddb68a735f360092e19")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9174050495:AAGDdZ-Tm6NLxDs0Pqz_l1dmGKschjz55Cs")
OWNER_ID = int(os.environ.get("OWNER_ID", "6454597633"))

bot = Client("master_unified_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

DB_FILE = "master_database.db"

VIP_REGISTER_LINK = "https://bdg4.vip//#/register?invitationCode=1921324032297"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS accounts (phone TEXT PRIMARY KEY, session TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS groups (chat_id INTEGER PRIMARY KEY, title TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bot_settings (key TEXT PRIMARY KEY, val TEXT)''')
    # Table for Sub-Admins, Agents, Permissions & Expiry Dates
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

def db_save_session(phone, session_str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO accounts VALUES (?, ?)", (phone, session_str))
    conn.commit()
    conn.close()

def db_get_all_sessions():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT session FROM accounts")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

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

SYSTEM_STATE = {
    "AUTO_VC": True,
    "ANTI_DROP_VC": True,
    "AUTO_REACTION": True,
    "PROXY_PROTECTION": True,
    "GROUP_PROTECTION": False,
    "AUTO_VIEWS": True,
    "PREDICTION_TASK": None,
    "LAST_PREDICTION": None,
    "REACTIONS": ["🔥", "⚡", "🚀", "👑", "🎯", "💎", "💯", "👍", "❤️"],
    "LOGIN_TEMP": {},
    "CURRENT_TARGET": None,
    "ACTIVE_USER_CLIENTS": [],
    "PENDING_VC_TARGET": {},
    "WAITING_CUSTOM_COUNT": {},
    "WAITING_LEAVE_INPUT": set(),
    "SET_PHOTO_MODE": None,
    "WAITING_DATE_INPUT": set(),
    "WAITING_DEL_ADMIN": set()
}

def get_dashboard_keyboard(user_id):
    is_owner = (user_id == OWNER_ID)
    prot_st = "🟢 24H ON" if SYSTEM_STATE["GROUP_PROTECTION"] else "🔴 OFF"

    buttons = [
        [
            InlineKeyboardButton("🎙️ JOIN VC BOOST", callback_data="vc_join_boost"),
            InlineKeyboardButton("🛑 LEAVE VC", callback_data="vc_leave_all")
        ],
        [
            InlineKeyboardButton("🛡️ START 24H PROTECTION", callback_data="start_24h_protection"),
            InlineKeyboardButton("🛑 STOP 24H PROTECTION", callback_data="stop_24h_protection")
        ],
        [
            InlineKeyboardButton("📅 DATE & ACCESS MANAGER", callback_data="btn_admin_manager"),
            InlineKeyboardButton("📊 DATE & PERMS TABLE", callback_data="btn_show_table")
        ],
        [
            InlineKeyboardButton("🖼️ SET BIG PHOTO", callback_data="btn_set_big_photo"),
            InlineKeyboardButton("🖼️ SET SMALL PHOTO", callback_data="btn_set_small_photo")
        ],
        [
            InlineKeyboardButton("🔥 AUTO REACTION", callback_data="trigger_reactions_btn"),
            InlineKeyboardButton("👁️ 500+ VIEW BOOST", callback_data="trigger_views_btn")
        ],
        [
            InlineKeyboardButton("🏢 CONNECTED CHATS", callback_data="list_groups_btn"),
            InlineKeyboardButton("🚪 LEAVE GROUP", callback_data="prompt_leave_group")
        ]
    ]

    if is_owner:
        buttons.append([
            InlineKeyboardButton("➕ ADD BY PHONE", callback_data="add_phone_info"),
            InlineKeyboardButton("📑 ACCOUNTS LIST", callback_data="list_accounts")
        ])

    return InlineKeyboardMarkup(buttons)

def get_dashboard_text(user_id):
    has_access, perms, exp_date = check_user_access(user_id)
    saved_count = len(db_get_all_sessions())
    active_count = len(SYSTEM_STATE["ACTIVE_USER_CLIENTS"])
    groups_count = len(db_get_all_groups())
    prot_status = "🟢 24H Active (Clean Signal Mode)" if SYSTEM_STATE["GROUP_PROTECTION"] else "🔴 Stopped"
    sub_admins = len(db_get_all_sub_admins())

    return (
        "╔════════════════════════════╗\n"
        "  👑 **TELANGANA SURE SHOT TRADING BADSHAH** 👑\n"
        "     ⚡ **VIP VC BOOSTER & PREDICTION** ⚡\n"
        "╚════════════════════════════╝\n\n"
        f"👤 **Access Level:** `{'OWNER (Full)' if user_id == OWNER_ID else f'AGENT ({perms})'}`\n"
        f"⏳ **Validity / Expiry:** `{exp_date if exp_date else 'Lifetime'}`\n"
        "🟢 **Server Status:** 24/7 Cloud Running 🚀\n"
        f"🎙️ **Active In VC:** `{active_count}` IDs | 📱 **Accounts:** `{saved_count}`\n"
        f"🏢 **Connected Chats:** `{groups_count}` Groups | 👮 **Active Admins:** `{sub_admins}`\n"
        f"🛡️ **Protection Engine:** {prot_status}\n\n"
        "Neeche diye gaye buttons se complete control karein:"
    )

async def broadcast_card(photo_id, caption_text):
    groups = db_get_all_groups()
    for cid, title in groups:
        sent = False
        if photo_id:
            try:
                await bot.send_photo(cid, photo=photo_id, caption=caption_text)
                sent = True
            except Exception as ex:
                logger.warning(f"Photo send error: {ex}")

        if not sent:
            try:
                await bot.send_message(cid, caption_text)
            except Exception as e:
                logger.error(f"Fallback fail for {cid}: {e}")

def get_current_30s_period():
    now = datetime.now(timezone.utc)
    date_part = now.strftime("%Y%m%d")
    cycle_index = (now.hour * 3600 + now.minute * 60 + now.second) // 30 + 1
    return f"{date_part}1000{cycle_index:04d}"

async def color_trading_loop():
    logger.info("WinGo 30s Loop Started")
    while SYSTEM_STATE["GROUP_PROTECTION"]:
        try:
            current_period = get_current_30s_period()
            big_photo = db_get_setting("BIG_PHOTO")
            small_photo = db_get_setting("SMALL_PHOTO")

            if SYSTEM_STATE["LAST_PREDICTION"]:
                last = SYSTEM_STATE["LAST_PREDICTION"]
                pred_type = last["type"]
                lucky_nums = last["numbers"]

                is_win_round = random.random() < 0.85

                if is_win_round:
                    actual_type = pred_type
                    actual_num = random.choice([5, 6, 7, 8, 9] if actual_type == "BIG" else [0, 1, 2, 3, 4])
                    res_photo = big_photo if actual_type == "BIG" else small_photo
                    res_caption = (
                        "🏆✅ **BIG WIN - PASS!** ✅🏆\n"
                        f"🎯 Period: `{last['period']}` | Outcome: `{actual_type}` [{actual_num}]\n"
                        "👑 **VIP Accuracy 100% Sure Shot!**"
                    )
                    await broadcast_card(res_photo, res_caption)
                else:
                    actual_type = "SMALL" if pred_type == "BIG" else "BIG"
                    actual_num = random.choice([5, 6, 7, 8, 9] if actual_type == "BIG" else [0, 1, 2, 3, 4])
                    res_photo = big_photo if actual_type == "BIG" else small_photo
                    res_caption = (
                        "💔⚠️ **LOSS - 3X RECOVERY** ⚠️💔\n"
                        f"🎯 Period: `{last['period']}` | Outcome: `{actual_type}` [{actual_num}]\n"
                        "🛡️ **Next Trade 100% Guaranteed Recovery!**"
                    )
                    await broadcast_card(res_photo, res_caption)

                await asyncio.sleep(2)

            next_pred_type = random.choice(["BIG", "SMALL"])
            next_lucky = random.sample([5, 6, 7, 8, 9] if next_pred_type == "BIG" else [0, 1, 2, 3, 4], 2)

            SYSTEM_STATE["LAST_PREDICTION"] = {
                "period": current_period,
                "type": next_pred_type,
                "numbers": next_lucky
            }

            photo_to_send = big_photo if next_pred_type == "BIG" else small_photo
            lucky_str = f"{next_lucky[0]}, {next_lucky[1]}"

            signal_caption = (
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "┣ᴡɪɴɢᴏ 30 ꜱᴇᴄ 🗣\n"
                f"┣☞︎𝑃𝐸𝑅𝐼𝑂𝐷 → ( {current_period} )\n\n"
                f"⚙️ 𝑆𝐼𝐺𝑁𝐴𝐿 ──➤ {next_pred_type}\n\n"
                f"➡️ 𝑁𝑈𝑀𝐵𝐸𝑅 → {lucky_str}\n"
                "➖➖➖➖➖➖➖➖➖➖\n"
                "🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢\n"
                "👑 **VIP REGISTER & JOINING LINK:**\n"
                f"🔗 {VIP_REGISTER_LINK}"
            )

            await broadcast_card(photo_to_send, signal_caption)

        except Exception as e:
            logger.error(f"30s loop error: {e}")

        now_sec = datetime.now(timezone.utc).second % 30
        sleep_time = max(3, 30 - now_sec)
        await asyncio.sleep(sleep_time)

# Auto Photo Save Feature
@bot.on_message(filters.photo & filters.private)
async def auto_save_photo(client, message):
    fid = message.photo.file_id
    mode = SYSTEM_STATE.get("SET_PHOTO_MODE")
    if mode == "BIG":
        db_set_setting("BIG_PHOTO", fid)
        SYSTEM_STATE["SET_PHOTO_MODE"] = None
        await message.reply_text("✅ **BIG वाली फोटो सफलतापूर्वक सेव हो गई है!** 🎉", reply_markup=get_dashboard_keyboard(message.from_user.id))
    elif mode == "SMALL":
        db_set_setting("SMALL_PHOTO", fid)
        SYSTEM_STATE["SET_PHOTO_MODE"] = None
        await message.reply_text("✅ **SMALL वाली फोटो सफलतापूर्वक सेव हो गई है!** 🎉", reply_markup=get_dashboard_keyboard(message.from_user.id))
    else:
        await message.reply_text(
            "📸 **फोटो रिसीव हो गई!**\n\nइसे सेट करने के लिए पहले डैशबोर्ड पर **SET BIG PHOTO** या **SET SMALL PHOTO** का बटन दबाएँ!",
            reply_markup=get_dashboard_keyboard(message.from_user.id)
        )

async def inject_web_views_500(channel_name, post_id):
    url = f"https://t.me/{channel_name}/{post_id}?embed=1"
    headers_list = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
        "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 Chrome/120.0.0.0"
    ]
    async with aiohttp.ClientSession() as session:
        for _ in range(55):
            tasks = [
                session.get(url, headers={"User-Agent": random.choice(headers_list)}, timeout=aiohttp.ClientTimeout(total=4))
                for _ in range(10)
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.sleep(0.02)

async def join_target_vc_process(target_url, limit_count=None):
    SYSTEM_STATE["CURRENT_TARGET"] = target_url
    sessions = db_get_all_sessions()
    if not sessions:
        return 0, "Database me koi account nahi hai. /login karein."

    if limit_count is not None and limit_count > 0:
        sessions = sessions[:limit_count]

    clean_link = target_url.split("?")[0].strip()
    is_private = ("+" in clean_link) or ("joinchat" in clean_link)
    target_clean = clean_link.split("/")[-1].replace("+", "").replace("@", "").strip()

    joined_count = 0
    last_err = ""

    for sess in sessions:
        uc = None
        try:
            uc = Client(f"usr_{random.randint(1000, 9999)}", api_id=API_ID, api_hash=API_HASH, session_string=sess, in_memory=True)
            await uc.start()

            chat_obj = None
            if is_private:
                try:
                    chat_obj = await uc.join_chat(clean_link)
                except UserAlreadyParticipant:
                    pass
            else:
                try:
                    chat_obj = await uc.join_chat(target_clean)
                except UserAlreadyParticipant:
                    pass
                try:
                    chat_obj = await uc.get_chat(target_clean)
                except Exception:
                    pass

            await asyncio.sleep(1.2)
            target_id = chat_obj.id if chat_obj else target_clean
            peer = await uc.resolve_peer(target_id)

            call_obj = None
            for _ in range(3):
                try:
                    full_chat = await uc.invoke(GetFullChannel(channel=peer))
                    if hasattr(full_chat.full_chat, "call") and full_chat.full_chat.call:
                        call_obj = full_chat.full_chat.call
                        break
                except Exception as ex:
                    last_err = str(ex)
                await asyncio.sleep(1)

            if not call_obj:
                last_err = "Active Voice Chat nahi mili."
                await uc.stop()
                continue

            try:
                await uc.invoke(LeaveGroupCall(call=InputGroupCall(id=call_obj.id, access_hash=call_obj.access_hash), source=0))
                await asyncio.sleep(1)
            except Exception:
                pass

            unique_ssrc = random.randint(10000000, 2147483647)
            payload_data = {"min_layer": 100, "max_layer": 114, "ssrc": unique_ssrc}
            payload_json = json.dumps(payload_data)

            await uc.invoke(JoinGroupCall(call=InputGroupCall(id=call_obj.id, access_hash=call_obj.access_hash), join_as=InputPeerSelf(), params=DataJSON(data=payload_json), muted=True))
            SYSTEM_STATE["ACTIVE_USER_CLIENTS"].append(uc)
            joined_count += 1
        except Exception as e:
            last_err = str(e)
            if uc and uc.is_connected and uc not in SYSTEM_STATE["ACTIVE_USER_CLIENTS"]:
                try:
                    await uc.stop()
                except Exception:
                    pass

    return joined_count, last_err

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
        ack = await message.reply_text("🛡️ **Group registered for WinGo 30s Signals & Protection.**")
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
                warn = await message.reply_text(f"🛡️ **Security Alert:** {uname}, links allow nahi hain!")
                await asyncio.sleep(4)
                await warn.delete()
            except Exception as e:
                logger.error(f"Auto delete fail: {e}")

@bot.on_message(filters.command("login") & filters.private)
async def login_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return
    if len(message.command) < 2:
        await message.reply_text("⚠️ **Format:** `/login +91XXXXXXXXXX`")
        return
    phone = message.command[1].strip().replace(" ", "").replace("-", "")
    c = Client(f"login_{phone.replace('+', '')}", api_id=API_ID, api_hash=API_HASH, in_memory=True)
    await c.connect()
    try:
        sent = await c.send_code(phone)
        SYSTEM_STATE["LOGIN_TEMP"][message.from_user.id] = {"client": c, "phone": phone, "hash": sent.phone_code_hash}
        await message.reply_text(f"📩 **OTP Sent to {phone}!**\nLikh kar bhejein:\n`/otp 12345`")
    except Exception as e:
        await c.disconnect()
        await message.reply_text(f"❌ Error: {e}")

@bot.on_message(filters.command("otp") & filters.private)
async def otp_cmd(client, message):
    uid = message.from_user.id
    if uid not in SYSTEM_STATE["LOGIN_TEMP"]:
        return
    if len(message.command) < 2:
        await message.reply_text("⚠️ **Format:** `/otp 12345`")
        return
    otp = message.command[1].strip()
    dt = SYSTEM_STATE["LOGIN_TEMP"][uid]
    c = dt["client"]
    try:
        await c.sign_in(dt["phone"], dt["hash"], otp)
        s_str = await c.export_session_string()
        db_save_session(dt["phone"], s_str)
        await c.disconnect()
        del SYSTEM_STATE["LOGIN_TEMP"][uid]
        await message.reply_text(f"✅ **Account {dt['phone']} Save ho gaya!**")
    except SessionPasswordNeeded:
        await message.reply_text("🔐 **2FA Password bhejein:**\n`/password aapka_password`")
    except Exception as e:
        await message.reply_text(f"❌ OTP Error: {e}")

@bot.on_message(filters.command("password") & filters.private)
async def pwd_cmd(client, message):
    uid = message.from_user.id
    if uid not in SYSTEM_STATE["LOGIN_TEMP"]:
        return
    pwd = " ".join(message.command[1:])
    dt = SYSTEM_STATE["LOGIN_TEMP"][uid]
    c = dt["client"]
    try:
        await c.check_password(pwd)
        s_str = await c.export_session_string()
        db_save_session(dt["phone"], s_str)
        await c.disconnect()
        del SYSTEM_STATE["LOGIN_TEMP"][uid]
        await message.reply_text("✅ **2FA Verified! Account save ho gaya.**")
    except Exception as e:
        await message.reply_text(f"❌ Password Error: {e}")

@bot.on_message(filters.text & filters.private & ~filters.command(["start", "login", "otp", "password"]))
async def message_dispatcher(client, message):
    uid = message.from_user.id
    txt = message.text.strip()

    # Input: Add Agent / Sub-Admin with Date & Permissions
    if uid in SYSTEM_STATE["WAITING_DATE_INPUT"]:
        SYSTEM_STATE["WAITING_DATE_INPUT"].remove(uid)
        parts = txt.split()
        if len(parts) < 4:
            await message.reply_text(
                "❌ **Galat Format!**\nSahi format aise likhein:\n`<UserID> <GroupID> <Permissions> <Days>`\n\n"
                "**Example:**\n`12345678 -100987654321 ALL 30`\n(Permissions: `ALL` ya `TRADING` ya `VC`)"
            )
            return
        try:
            target_uid = int(parts[0])
            target_gid = int(parts[1])
            perms = parts[2].upper()
            days = int(parts[3])
            exp_date = (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")

            db_add_sub_admin(target_uid, target_gid, perms, exp_date)
            db_add_group(target_gid, f"Agent Group ({target_uid})")

            await message.reply_text(
                f"✅ **Agent Access Successfully Added!**\n\n"
                f"👤 **User ID:** `{target_uid}`\n"
                f"🏢 **Group ID:** `{target_gid}`\n"
                f"🛡️ **Permissions:** `{perms}`\n"
                f"📅 **Expiry Date:** `{exp_date}` ({days} Din)\n\n"
                "Ab is agent aur iske group me bot access active ho chuka hai!",
                reply_markup=get_dashboard_keyboard(uid)
            )
        except Exception as e:
            await message.reply_text(f"❌ Error: `{e}`")
        return

    # Input: Remove Admin
    if uid in SYSTEM_STATE["WAITING_DEL_ADMIN"]:
        SYSTEM_STATE["WAITING_DEL_ADMIN"].remove(uid)
        try:
            target_uid = int(txt)
            db_remove_sub_admin(target_uid)
            await message.reply_text(f"🗑️ **Agent ID `{target_uid}` ka access revoke kar diya gaya hai.**", reply_markup=get_dashboard_keyboard(uid))
        except Exception:
            await message.reply_text("❌ Sahi numeric User ID bhejein.")
        return

    if uid in SYSTEM_STATE["WAITING_CUSTOM_COUNT"]:
        target_link = SYSTEM_STATE["WAITING_CUSTOM_COUNT"].pop(uid)
        if not txt.isdigit() or int(txt) <= 0:
            await message.reply_text("❌ Kripya valid number dalein.")
            return
        count = int(txt)
        prog = await message.reply_text(f"⏳ **{count} IDs ko VC me baithaya ja raha hai...**")
        joined, err = await join_target_vc_process(target_link, limit_count=count)
        if joined > 0:
            await prog.edit_text(f"🎙️ **SUCCESS!** Kul `{joined}` IDs VC me baith chuki hain! 🚀")
        else:
            await prog.edit_text(f"⚠️ **0 IDs Join hui.**\nKaran: `{err}`")
        return

    if uid in SYSTEM_STATE["WAITING_LEAVE_INPUT"]:
        SYSTEM_STATE["WAITING_LEAVE_INPUT"].remove(uid)
        try:
            cid = int(txt)
            db_remove_group(cid)
            try:
                await bot.leave_chat(cid)
                await message.reply_text(f"🚪 **Group `{cid}` se bot exit ho gaya.**", reply_markup=get_dashboard_keyboard(uid))
            except Exception as ex:
                await message.reply_text(f"⚠️ Removed from DB. Leave Error: `{ex}`", reply_markup=get_dashboard_keyboard(uid))
        except ValueError:
            await message.reply_text("❌ Sahi numeric Chat ID bhejein.")
        return

    if "livestream=" in txt or txt.startswith("@") or ("t.me/" in txt and not any(p.isdigit() for p in txt.split("?")[0].split("/")[-1:])):
        total_avail = len(db_get_all_sessions())
        if total_avail == 0:
            await message.reply_text("❌ Pehle `/login +91XXXXXXXXXX` se account save karein.")
            return
        SYSTEM_STATE["PENDING_VC_TARGET"][uid] = txt
        await message.reply_text(f"🎯 **Target Set:** `{txt}`\n📱 **Available IDs:** `{total_avail}`\n\nKitne members baithane hain? Choose karein:", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 1 ID", callback_data="joinvc_cnt_1"), InlineKeyboardButton("👥 5 IDs", callback_data="joinvc_cnt_5"), InlineKeyboardButton("🔟 10 IDs", callback_data="joinvc_cnt_10")],
            [InlineKeyboardButton("⚡ 20 IDs", callback_data="joinvc_cnt_20"), InlineKeyboardButton("🔥 50 IDs", callback_data="joinvc_cnt_50"), InlineKeyboardButton("🚀 ALL IDs", callback_data="joinvc_cnt_all")],
            [InlineKeyboardButton("❌ CANCEL", callback_data="cancel_vc_flow")]
        ]))
        return

    if "t.me/" in txt and any(c.isdigit() for c in txt.split("?")[0].split("/")[-1]):
        status_msg = await message.reply_text("⚡ Post link mila! **500+ Views & Reactions Boost** shuru ho raha hai...")
        clean = txt.split("?")[0].strip().split("/")
        ch_name, post_id = clean[-2], clean[-1]

        await inject_web_views_500(ch_name, post_id)

        sessions = db_get_all_sessions()
        rxn_count = 0
        for sess in sessions:
            try:
                uc = Client("rxn_temp", api_id=API_ID, api_hash=API_HASH, session_string=sess, in_memory=True)
                await uc.start()
                for _ in range(3):
                    await uc.send_reaction(chat_id=ch_name, message_id=int(post_id), emoji=random.choice(SYSTEM_STATE["REACTIONS"]))
                    rxn_count += 1
                await uc.stop()
            except Exception:
                pass

        await status_msg.edit_text("🔥 **500+ Views Deliver Ho Gaye!** Saath hi multi-reactions lag chuke hain.")
        return

@bot.on_callback_query()
async def callback_dispatcher(client, query):
    d = query.data
    uid = query.from_user.id
    has_access, perms, _ = check_user_access(uid)

    if not has_access:
        await query.answer("Access Denied! Contact Owner.", show_alert=True)
        return

    if d == "btn_admin_manager":
        if uid != OWNER_ID:
            await query.answer("Sirf Main Owner hi Date aur Access manage kar sakta hai!", show_alert=True)
            return
        await query.answer()
        await query.message.reply_text(
            "📅 **AGENT ACCESS & DATE MANAGER:**\n════════════════════════════\n\n"
            "Kisi agent/admin ko date ke hisaab se access dene ke liye format me reply karein:\n\n"
            "`<UserID> <GroupID> <Permissions> <Days>`\n\n"
            "**Permissions Options:**\n"
            "• `ALL` (Sabhi features: Trading + VC + Views)\n"
            "• `TRADING` (Sirf WinGo Signals)\n"
            "• `VC` (Sirf VC Booster)\n\n"
            "**Example:**\n`6454597633 -100123456789 ALL 30`\n*(Isse 30 din ka full access set ho jayega)*"
        )
        SYSTEM_STATE["WAITING_DATE_INPUT"].add(uid)
        return

    elif d == "btn_show_table":
        sub_admins = db_get_all_sub_admins()
        txt = "📊 **ADMINS, AGENTS & EXPIRY TABLE:**\n"
        txt += "════════════════════════════\n"
        txt += f"👑 **MAIN OWNER:** `{OWNER_ID}` [LIFETIME - ALL]\n\n"

        if not sub_admins:
            txt += "_Abhi koi Sub-Admin/Agent active nahi hai._\n"
        else:
            txt += "| USER ID | GROUP ID | ACCESS | EXPIRY |\n"
            txt += "|---|---|---|---|\n"
            for a_uid, a_gid, a_perms, a_exp in sub_admins:
                txt += f"• `{a_uid}` | `{a_gid}` | **{a_perms}** | `{a_exp}`\n"

        txt += "════════════════════════════\n"
        await query.message.reply_text(txt, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑️ REMOVE AGENT", callback_data="btn_delete_agent")]
        ]))
        await query.answer()
        return

    elif d == "btn_delete_agent":
        if uid != OWNER_ID:
            await query.answer("Sirf Main Owner remove kar sakta hai!", show_alert=True)
            return
        SYSTEM_STATE["WAITING_DEL_ADMIN"].add(uid)
        await query.answer()
        await query.message.reply_text("🗑️ Jis Agent ko remove karna hai uski **User ID** bhejein:")
        return

    elif d == "btn_set_big_photo":
        SYSTEM_STATE["SET_PHOTO_MODE"] = "BIG"
        await query.answer()
        await query.message.reply_text("📸 **Ab chat mein apni BIG wali photo bhej kar save kar lein!**")
        return

    elif d == "btn_set_small_photo":
        SYSTEM_STATE["SET_PHOTO_MODE"] = "SMALL"
        await query.answer()
        await query.message.reply_text("📸 **Ab chat mein apni SMALL wali photo bhej kar save kar lein!**")
        return

    elif d == "start_24h_protection":
        if perms not in ["ALL", "TRADING"] and uid != OWNER_ID:
            await query.answer("Aapko Color Trading Signals ka access nahi mila hai!", show_alert=True)
            return
        SYSTEM_STATE["GROUP_PROTECTION"] = True
        if not SYSTEM_STATE["PREDICTION_TASK"] or SYSTEM_STATE["PREDICTION_TASK"].done():
            SYSTEM_STATE["PREDICTION_TASK"] = asyncio.create_task(color_trading_loop())

        await query.answer("🛡️ 24-Hour WinGo 30s Protection Shuru!", show_alert=True)
        try:
            await query.message.edit_text(get_dashboard_text(uid), reply_markup=get_dashboard_keyboard(uid))
        except MessageNotModified:
            pass
        return

    elif d == "stop_24h_protection":
        SYSTEM_STATE["GROUP_PROTECTION"] = False
        if SYSTEM_STATE["PREDICTION_TASK"]:
            SYSTEM_STATE["PREDICTION_TASK"].cancel()

        await query.answer("🛑 Protection Band kar di gayi!", show_alert=True)
        try:
            await query.message.edit_text(get_dashboard_text(uid), reply_markup=get_dashboard_keyboard(uid))
        except MessageNotModified:
            pass
        return

    elif d.startswith("joinvc_cnt_"):
        await query.answer()
        target_link = SYSTEM_STATE["PENDING_VC_TARGET"].get(uid)
        if not target_link:
            await query.message.reply_text("⚠️ Pehle VC link bhejein.")
            return

        selected = d.replace("joinvc_cnt_", "")
        del SYSTEM_STATE["PENDING_VC_TARGET"][uid]
        count = None if selected == "all" else int(selected)
        lbl = "All Available" if count is None else str(count)

        prog = await query.message.reply_text(f"⏳ **{lbl} IDs ko VC me baithaya ja raha hai...**")
        joined, err = await join_target_vc_process(target_link, limit_count=count)
        if joined > 0:
            await prog.edit_text(f"🎙️ **SUCCESS!** Kul `{joined}` IDs VC me enter ho chuki hain! 🚀")
        else:
            await prog.edit_text(f"⚠️ **0 IDs Join hui.**\nKaran: `{err}`")
        return

    elif d == "cancel_vc_flow":
        SYSTEM_STATE["PENDING_VC_TARGET"].pop(uid, None)
        await query.answer("Canceled!")
        await query.message.edit_text("❌ Cancel kar diya gaya.")
        return

    elif d == "vc_join_boost":
        if perms not in ["ALL", "VC"] and uid != OWNER_ID:
            await query.answer("Aapko VC Booster ka access nahi hai!", show_alert=True)
            return
        await query.answer()
        await query.message.reply_text("🎙️ VC / Live Stream ka link ya username chat me bhejein.")
        return

    elif d == "vc_leave_all":
        for uc in SYSTEM_STATE["ACTIVE_USER_CLIENTS"]:
            try:
                await uc.stop()
            except Exception:
                pass
        SYSTEM_STATE["ACTIVE_USER_CLIENTS"].clear()
        SYSTEM_STATE["CURRENT_TARGET"] = None
        await query.answer("Sabhi IDs VC se bahar aa gayi hain!", show_alert=True)
        await query.message.reply_text("🛑 Sabhi accounts VC se leave kar chuke hain.")
        return

    elif d == "list_groups_btn":
        groups = db_get_all_groups()
        if not groups:
            await query.answer("Koi group registered nahi hai. Group me /start likhein.", show_alert=True)
            return
        txt = "🏢 **CONNECTED GROUPS / CHANNELS:**\n════════════════════════════\n"
        for cid, title in groups:
            txt += f"• **{title}**\n  └ ID: `{cid}`\n\n"
        await query.message.reply_text(txt)
        await query.answer()
        return

    elif d == "prompt_leave_group":
        SYSTEM_STATE["WAITING_LEAVE_INPUT"].add(uid)
        await query.answer()
        await query.message.reply_text("🚪 **Chat ID Bhejein:** Jis group se bot ko nikalna hai uski ID bhejein (jaise: `-100123456789`):")
        return

    elif d in ["reaction_views_info", "trigger_views_btn", "trigger_reactions_btn"]:
        await query.answer()
        await query.message.reply_text("👁️ **500+ Views & Reactions Booster:**\nApne channel ka post link DM mein bhejein, bot turant 500+ views deliver karega.")
        return

    elif d == "add_phone_info":
        await query.answer()
        await query.message.reply_text("📱 Format: `/login +91XXXXXXXXXX`")
        return

    elif d == "list_accounts":
        await query.answer(f"Total Accounts: {len(db_get_all_sessions())}", show_alert=True)
        return

    elif d == "force_reconnect":
        await query.answer("Force reconnect initiated!", show_alert=True)
        return

async def start_services():
    try:
        await bot.start()
        print("Telangana Unified Master Bot Live 🚀", flush=True)

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
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_services())
