import asyncio
import re
import os
from aiohttp import web
from pyrogram import Client, filters, enums, idle
from pyrogram.types import ChatPermissions, Message

# -----------------------------------------------------------
# 🔥 RENDER FIX: Event Loop Fix & Web Server Setup
# -----------------------------------------------------------
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# কনফিগারেশন
API_ID = 38892252
API_HASH = "8528a56cef036de8478f09876b5f29ae"
BOT_TOKEN = "8709933046:AAEFxAMKCfB3dx_JElXfGKW4-n2YjL_jgJc"
OWNER_ID = 1162926011 

app = Client("rose_clone_fixed", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ডাটাবেস (মেমোরি)
welcome_db = {} 
notes_db = {}
warns_db = {}
served_chats = set()

# -----------------------------------------------------------
# 🔥 WEB SERVER (Render কে সচল রাখার জন্য)
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
    print(f"✅ Web Server Started on Port {port}")

# -----------------------------------------------------------
# বট লজিক শুরু
# -----------------------------------------------------------

# এডমিন চেক
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

# অটো মডারেশন (Anti-Link & Anti-Forward)
@app.on_message(filters.group & (filters.text | filters.caption | filters.forwarded), group=1)
async def auto_moderation(c, m):
    if await is_admin(m): return # এডমিনদের জন্য মাফ

    chat_id = m.chat.id
    user_id = m.from_user.id
    msg_text = m.text or m.caption or ""
    
    violation = False
    reason = ""
    link_pattern = r"(https?://|www\.|t\.me/|@[a-zA-Z0-9_]+)"
    
    if m.forward_date or m.forward_from or m.forward_from_chat:
        violation = True
        reason = "ফরোয়ার্ড করা নিষিদ্ধ!"
    elif re.search(link_pattern, msg_text):
        violation = True
        reason = "লিংক বা ইউজারনেম নিষিদ্ধ!"

    if violation:
        try: await m.delete()
        except: pass

        if chat_id not in warns_db: warns_db[chat_id] = {}
        current_warn = warns_db[chat_id].get(user_id, 0) + 1
        warns_db[chat_id][user_id] = current_warn

        if current_warn >= 3:
            try:
                # ৩ বারের পর অটো মিউট
                await c.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=False))
                msg = await m.reply(f"🔇 {m.from_user.mention} কে অটোমেটিক মিউট করা হয়েছে!\nকারণ: ৩ বার রুলস ব্রেক।")
                warns_db[chat_id][user_id] = 0 # মিউট হলে ওয়ার্নিং রিসেট
                await asyncio.sleep(10)
                await msg.delete()
            except: pass
        else:
            msg = await m.reply(f"⚠️ {m.from_user.mention}, {reason} ({current_warn}/3)")
            await asyncio.sleep(5)
            try: await msg.delete() 
            except: pass

# এডমিন টুলস
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
            # আনমিউট + ওয়ার্নিং রিসেট
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

# ম্যানুয়াল ওয়ার্নিং
@app.on_message(filters.command(["warn", "resetwarn"]) & filters.group)
async def warn_system(c, m):
    if not await is_admin(m): return
    if m.command[0] == "resetwarn":
        if not m.reply_to_message: return
        t = m.reply_to_message.from_user
        if m.chat.id in warns_db and t.id in warns_db[m.chat.id]: warns_db[m.chat.id][t.id] = 0
        return await m.reply("✅ Warnings reset.")
    
    if not m.reply_to_message: return await m.reply("Reply to warn.")
    target = m.reply_to_message.from_user
    chat_id = m.chat.id
    
    if chat_id not in warns_db: warns_db[chat_id] = {}
    current_warn = warns_db[chat_id].get(target.id, 0) + 1
    warns_db[chat_id][target.id] = current_warn
    
    if current_warn >= 3:
        try:
            await c.ban_chat_member(chat_id, target.id)
            await m.reply(f"🚫 {target.mention} Banned (3/3 Warns)!")
            warns_db[chat_id][target.id] = 0
        except: pass
    else:
        await m.reply(f"⚠️ Warned: {target.mention} ({current_warn}/3)")

# ওয়েলকাম
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
    else:
        await c.send_message(cmu.chat.id, f"Welcome {cmu.new_chat_member.user.mention}!")

# ফিল্টার সেভ
@app.on_message(filters.command(["save", "filter"]) & filters.group)
async def save_filter(c, m):
    if not await is_admin(m): return
    if len(m.command) < 2: return
    word = m.command[1].lower()
    content = ""
    file_id = None
    if m.reply_to_message:
        content = m.reply_to_message.caption or m.reply_to_message.text or ""
        if m.reply_to_message.photo: file_id = m.reply_to_message.photo.file_id
    elif len(m.command) > 2: content = m.text.split(None, 2)[2]
    if m.chat.id not in notes_db: notes_db[m.chat.id] = {}
    notes_db[m.chat.id][word] = {'text': content, 'file': file_id}
    await m.reply(f"✅ Saved: {word}")

@app.on_message(filters.text & filters.group, group=2)
async def check_filter(c, m):
    if m.text.startswith("/"): return
    word = m.text.lower()
    if m.chat.id in notes_db and word in notes_db[m.chat.id]:
        n = notes_db[m.chat.id][word]
        if n['file']: await c.send_photo(m.chat.id, n['file'], caption=n['text'])
        else: await c.send_message(m.chat.id, n['text'])

# স্টার্ট
@app.on_message(filters.command("start"))
async def start(c, m):
    if m.chat.type == enums.ChatType.PRIVATE:
        await m.reply("Hi! I am a Group Management Bot. Use /help for commands.")
    else:
        await m.reply("I am Alive! ✅")

# -----------------------------------------------------------
# MAIN EXECUTION (BOT + WEB SERVER)
# -----------------------------------------------------------
async def main():
    # ওয়েব সার্ভার চালু করা (Render এর জন্য)
    await start_server()
    
    # বট চালু করা
    await app.start()
    print("✅ Bot Started Successfully on Render!")
    
    # বট যেন বন্ধ না হয়
    await idle()
    await app.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())