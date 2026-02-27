import asyncio
import os
import logging
from aiohttp import web
from pyrogram import Client, filters, enums, idle
from pyrogram.types import ChatPermissions, Message

# -----------------------------------------------------------
# 🔥 LOGGING SETUP (Render লগে বিস্তারিত দেখার জন্য)
# -----------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------
# ⚙️ কনফিগারেশন
# -----------------------------------------------------------
API_ID = 38892252
API_HASH = "8528a56cef036de8478f09876b5f29ae"
BOT_TOKEN = "8709933046:AAEFxAMKCfB3dx_JElXfGKW4-n2YjL_jgJc"
OWNER_ID = 8253965718 

# Client সেটআপ (in_memory=True জরুরি Render এর জন্য)
app = Client(
    "rose_clone_fixed",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# ডাটাবেস (মেমোরি)
welcome_db = {} 
notes_db = {}
warns_db = {}
served_chats = set()

# -----------------------------------------------------------
# 🌐 WEB SERVER (Render কে সচল রাখার জন্য)
# -----------------------------------------------------------
async def web_handler(request):
    return web.Response(text="Bot is Running Successfully on Render!")

async def start_server():
    server = web.Application()
    server.add_routes([web.get('/', web_handler)])
    runner = web.AppRunner(server)
    await runner.setup()
    # Render এর পোর্ট অথবা ডিফল্ট 8080
    port = int(os.environ.get("PORT", 8080))
    await web.TCPSite(runner, '0.0.0.0', port).start()
    logger.info(f"✅ Web Server Started on Port {port}")

# -----------------------------------------------------------
# 🤖 বট লজিক শুরু
# -----------------------------------------------------------

# এডমিন চেক ফাংশন
async def is_admin(message: Message) -> bool:
    chat_id = message.chat.id
    user = message.from_user
    if message.chat.type == enums.ChatType.PRIVATE: return True
    if message.sender_chat and message.sender_chat.id == chat_id: return True
    if user and user.id == OWNER_ID: return True
    try:
        member = await app.get_chat_member(chat_id, user.id)
        return member.status in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]
    except:
        return False

# গ্রুপ ক্যাপচার (ব্রডকাস্টের জন্য)
@app.on_message(filters.group, group=-1)
async def capture_chats(client, message):
    if message.chat.id not in served_chats:
        served_chats.add(message.chat.id)

# START কমান্ড
@app.on_message(filters.command("start"))
async def start(c, m):
    if m.chat.type == enums.ChatType.PRIVATE:
        await m.reply(f"Hi {m.from_user.mention}! I am a Group Management Bot.\nUse /help for commands.")
    else:
        await m.reply("I am Alive! ✅")

# HELP কমান্ড
@app.on_message(filters.command("help"))
async def help_command(c, m):
    text = """
**🤖 Bot Commands List:**

**👮 Admin Tools:**
/ban, /unban, /mute, /unmute, /kick, /pin, /purge
/lock, /unlock

**⚠️ Warnings:**
/warn, /resetwarn

**📝 Filters & Welcome:**
/save <word>, /setwelcome, /resetwelcome

**📢 Broadcast:**
/broadcast (Owner Only)
"""
    await m.reply(text)

# BROADCAST কমান্ড
@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast_msg(c, m):
    if not m.reply_to_message:
        return await m.reply("❌ **Error:** দয়া করে কোনো মেসেজে রিপ্লাই দিন।")
    
    msg = await m.reply(f"⏳ **Broadcasting to {len(served_chats)} chats...**")
    sent = 0
    failed = 0
    
    for chat_id in served_chats:
        try:
            await m.reply_to_message.copy(chat_id)
            sent += 1
            await asyncio.sleep(0.1)
        except:
            failed += 1
            
    await msg.edit(f"✅ **Broadcast Complete!**\n📢 Sent: `{sent}`\n❌ Failed: `{failed}`")

# এডমিন টুলস (Ban, Mute, Kick, etc.)
@app.on_message(filters.command(["ban", "unban", "mute", "unmute", "pin", "purge", "kick"]) & filters.group)
async def admin_tools(c, m):
    if not await is_admin(m): return await m.reply("❌ আপনি এডমিন নন।")
    cmd = m.command[0]
    chat_id = m.chat.id
    
    if not m.reply_to_message and cmd != "purge": return await m.reply("❗ রিপ্লাই দিন।")
    target = m.reply_to_message.from_user if m.reply_to_message else None

    try:
        if cmd == "ban":
            await c.ban_chat_member(chat_id, target.id)
            await m.reply(f"🚫 **Banned:** {target.mention}")
        elif cmd == "unban":
            await c.unban_chat_member(chat_id, target.id)
            await m.reply(f"✅ **Unbanned:** {target.mention}")
        elif cmd == "mute":
            await c.restrict_chat_member(chat_id, target.id, ChatPermissions(can_send_messages=False))
            await m.reply(f"🔇 **Muted:** {target.mention}")
        elif cmd == "unmute":
            await c.restrict_chat_member(chat_id, target.id, ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_invite_users=True))
            if chat_id in warns_db and target.id in warns_db[chat_id]: warns_db[chat_id][target.id] = 0
            await m.reply(f"🔊 **Unmuted:** {target.mention}")
        elif cmd == "kick":
            await c.ban_chat_member(chat_id, target.id)
            await c.unban_chat_member(chat_id, target.id)
            await m.reply(f"👞 **Kicked:** {target.mention}")
        elif cmd == "pin":
            await m.reply_to_message.pin(disable_notification=False)
            await m.reply(f"📌 **Pinned!**")
        elif cmd == "purge":
            if not m.reply_to_message: return await m.reply("❗ রিপ্লাই দিন।")
            msg_id = m.reply_to_message.id
            delete_ids = list(range(msg_id, m.id + 1))
            if len(delete_ids) > 100: delete_ids = delete_ids[:100]
            await c.delete_messages(chat_id, delete_ids)
            msg = await m.reply("✅ Purge Complete!")
            await asyncio.sleep(3)
            await msg.delete()
    except Exception as e:
        await m.reply(f"❌ Error: {e}")

# লক সিস্টেম
@app.on_message(filters.command(["lock", "unlock"]) & filters.group)
async def lock_system(c, m):
    if not await is_admin(m): return
    if m.command[0] == "lock":
        await c.set_chat_permissions(m.chat.id, ChatPermissions(can_send_messages=False))
        await m.reply("🔒 **Group Locked!**")
    elif m.command[0] == "unlock":
        await c.set_chat_permissions(m.chat.id, ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_invite_users=True))
        await m.reply("🔓 **Group Unlocked!**")

# ওয়েলকাম সেটআপ
@app.on_message(filters.command(["setwelcome", "resetwelcome"]) & filters.group)
async def set_welcome(c, m):
    if not await is_admin(m): return
    if m.command[0] == "resetwelcome":
        if m.chat.id in welcome_db: del welcome_db[m.chat.id]
        return await m.reply("✅ Welcome Reset.")
    text = ""
    photo = None
    if m.reply_to_message:
        text = m.reply_to_message.caption or m.reply_to_message.text or ""
        if m.reply_to_message.photo: photo = m.reply_to_message.photo.file_id
        if len(m.command) > 1: text = m.text.split(None, 1)[1]
    elif len(m.command) > 1: text = m.text.split(None, 1)[1]
    else: return await m.reply("Usage: /setwelcome <text>")
    welcome_db[m.chat.id] = {'text': text, 'photo': photo}
    await m.reply("✅ Saved!")

@app.on_chat_member_updated()
async def welcome_msg(c, cmu):
    if not cmu.new_chat_member or cmu.new_chat_member.status != enums.ChatMemberStatus.MEMBER: return
    if cmu.new_chat_member.user.is_bot: return
    data = welcome_db.get(cmu.chat.id)
    if data:
        msg = data['text'].replace("{mention}", cmu.new_chat_member.user.mention).replace("{name}", cmu.new_chat_member.user.first_name).replace("{title}", cmu.chat.title)
        if data['photo']: await c.send_photo(cmu.chat.id, data['photo'], caption=msg)
        else: await c.send_message(cmu.chat.id, msg)

# -----------------------------------------------------------
# 🔥 MAIN EXECUTION
# -----------------------------------------------------------
async def main():
    # ওয়েব সার্ভার চালু করা
    await start_server()
    
    # বট কানেক্ট করা
    logger.info("⏳ Connecting to Telegram...")
    try:
        await app.start()
        bot_info = await app.get_me()
        logger.info(f"✅ Bot Started Successfully as {bot_info.first_name} (@{bot_info.username})")
        
        # বট চালু রাখা
        await idle()
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
    finally:
        try:
            if app.is_connected:
                await app.stop()
        except:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"❌ Critical Error: {e}")
