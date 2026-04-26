import os
import asyncio
from telethon import TelegramClient, events
from telethon.tl.types import ChannelParticipantsAdmins
from telethon.errors import FloodWaitError

# ---------- ENV VARS ----------
API_ID = int(os.environ.get("APP_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("TOKEN", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise Exception("APP_ID, API_HASH, TOKEN are required.")

# ---------- GLOBALS ----------
cancelled = set()
clones = {}  # for clone feature (optional, as per your earlier request)

# ---------- HELPER: STYLISH TEXT (Small Caps / Fancy) ----------
def small_caps(text: str) -> str:
    """Convert normal text to small caps / stylish (approximate)"""
    mapping = {
        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ғ', 'g': 'ɢ',
        'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ',
        'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 's': 's', 't': 'ᴛ', 'u': 'ᴜ',
        'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ',
        'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 'E': 'ᴇ', 'F': 'ғ', 'G': 'ɢ',
        'H': 'ʜ', 'I': 'ɪ', 'J': 'ᴊ', 'K': 'ᴋ', 'L': 'ʟ', 'M': 'ᴍ', 'N': 'ɴ',
        'O': 'ᴏ', 'P': 'ᴘ', 'Q': 'ǫ', 'R': 'ʀ', 'S': 's', 'T': 'ᴛ', 'U': 'ᴜ',
        'V': 'ᴠ', 'W': 'ᴡ', 'X': 'x', 'Y': 'ʏ', 'Z': 'ᴢ'
    }
    return ''.join(mapping.get(ch, ch) for ch in text)

# ---------- MAIN BOT ----------
bot = TelegramClient("mentionall_bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

@bot.on(events.NewMessage(pattern='/start|/help'))
async def start_help(event):
    await event.reply(
        f"**{small_caps('🤖 MentionAll Bot')}**\n\n"
        f"✅ `{small_caps('/mentionall <message>')}` – {small_caps('mention all members with your message')}\n"
        f"✅ `{small_caps('/mentionadmin <message>')}` – {small_caps('mention only admins with your message')}\n"
        f"✅ `{small_caps('/cancel')}` – {small_caps('stop ongoing mention')}\n"
        f"✅ `{small_caps('/clone <bot_token>')}` – {small_caps('clone this bot (private chat only)')}\n\n"
        f"🔹 {small_caps('send the command in the group where i am admin')}",
        parse_mode='markdown'
    )

@bot.on(events.NewMessage(pattern='/mentionall(?: |$)(.*)'))
async def mention_all(event):
    if not event.is_group:
        await event.reply(small_caps("❌ This command works only in groups."))
        return

    chat = await event.get_chat()
    if not (chat.admin_rights or chat.creator):
        await event.reply(small_caps("❌ Only admins can use this command."))
        return

    # Get the user message
    user_message = event.pattern_match.group(1).strip()
    if not user_message and event.is_reply:
        reply = await event.get_reply_message()
        user_message = reply.text or ""
    if not user_message:
        user_message = "📢 " + small_caps("Attention everyone!")

    # Collect members (non-bot, non-deleted)
    members = []
    async for user in bot.iter_participants(event.chat_id):
        if not user.bot and not user.deleted:
            members.append(user)

    if not members:
        await event.reply(small_caps("❌ No members found."))
        return

    cancelled.discard(event.chat_id)
    await event.reply(f"🔄 {small_caps('Mentioning')} **{len(members)}** {small_caps('members... (send')} /cancel {small_caps('to stop)')}")

    batch_size = 5
    for i in range(0, len(members), batch_size):
        if event.chat_id in cancelled:
            await event.reply(small_caps("⛔ Mention process cancelled."))
            cancelled.discard(event.chat_id)
            return
        
        batch = members[i:i+batch_size]
        mentions = " ".join([f"[{user.first_name or 'User'}](tg://user?id={user.id})" for user in batch])
        
        # First batch includes user_message, subsequent batches only mentions
        if i == 0:
            final_msg = f"{user_message}\n\n{mentions}"
        else:
            final_msg = mentions

        try:
            await bot.send_message(event.chat_id, final_msg, parse_mode='markdown')
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print(f"Error: {e}")
        await asyncio.sleep(1)  # Delay to avoid flood
    
    await bot.send_message(event.chat_id, f"✅ {small_caps('All members have been mentioned.')}")

@bot.on(events.NewMessage(pattern='/mentionadmin(?: |$)(.*)'))
async def mention_admin(event):
    if not event.is_group:
        await event.reply(small_caps("❌ This command works only in groups."))
        return

    chat = await event.get_chat()
    if not (chat.admin_rights or chat.creator):
        await event.reply(small_caps("❌ Only admins can use this command."))
        return

    # Get the user message
    user_message = event.pattern_match.group(1).strip()
    if not user_message and event.is_reply:
        reply = await event.get_reply_message()
        user_message = reply.text or ""
    if not user_message:
        user_message = "🔔 " + small_caps("Notification for admins")

    # Collect only admins
    admins = []
    async for user in bot.iter_participants(event.chat_id, filter=ChannelParticipantsAdmins):
        if not user.bot:
            admins.append(user)

    if not admins:
        await event.reply(small_caps("❌ No admins found in this group."))
        return

    mentions = " ".join([f"[{admin.first_name or 'Admin'}](tg://user?id={admin.id})" for admin in admins])
    final_msg = f"{user_message}\n\n{mentions}"

    await bot.send_message(event.chat_id, final_msg, parse_mode='markdown')
    await event.reply(f"✅ {small_caps('Admins mentioned successfully.')}")

@bot.on(events.NewMessage(pattern='/cancel'))
async def cancel_mention(event):
    if event.chat_id in cancelled:
        await event.reply(small_caps("❌ No ongoing mention to cancel."))
    else:
        cancelled.add(event.chat_id)
        await event.reply(small_caps("🛑 Requested to cancel the mention. Please wait a moment."))

# ---------- CLONE FEATURE (as per your earlier request, kept) ----------
async def run_clone_bot(token: str, owner_id: int):
    client = TelegramClient(f"clone_{owner_id}_{token[:10]}", API_ID, API_HASH).start(bot_token=token)
    try:
        me = await client.get_me()
        print(f"Clone bot @{me.username} started for {owner_id}")

        @client.on(events.NewMessage(pattern='/mentionall(?: |$)(.*)'))
        async def clone_mentionall(e):
            if not e.is_group:
                await e.reply(small_caps("❌ Group only.")); return
            chat = await e.get_chat()
            if not (chat.admin_rights or chat.creator):
                await e.reply(small_caps("❌ Admin only.")); return
            msg = e.pattern_match.group(1).strip()
            if not msg and e.is_reply:
                rep = await e.get_reply_message()
                msg = rep.text or ""
            if not msg:
                msg = "📢 " + small_caps("Attention!")
            members = []
            async for u in client.iter_participants(e.chat_id):
                if not u.bot and not u.deleted:
                    members.append(u)
            if not members:
                await e.reply(small_caps("No members.")); return
            await e.reply(f"🔄 {small_caps('Mentioning')} {len(members)} {small_caps('members')}")
            batch = 5
            for i in range(0, len(members), batch):
                part = members[i:i+batch]
                mentions = " ".join([f"[{u.first_name or 'User'}](tg://user?id={u.id})" for u in part])
                text = f"{msg}\n\n{mentions}" if i == 0 else mentions
                try:
                    await client.send_message(e.chat_id, text, parse_mode='markdown')
                except FloodWaitError as fw:
                    await asyncio.sleep(fw.seconds)
                await asyncio.sleep(1)
            await client.send_message(e.chat_id, f"✅ {small_caps('Done')}")

        @client.on(events.NewMessage(pattern='/mentionadmin(?: |$)(.*)'))
        async def clone_mentionadmin(e):
            if not e.is_group:
                await e.reply(small_caps("Group only.")); return
            chat = await e.get_chat()
            if not (chat.admin_rights or chat.creator):
                await e.reply(small_caps("Admin only.")); return
            msg = e.pattern_match.group(1).strip()
            if not msg and e.is_reply:
                rep = await e.get_reply_message()
                msg = rep.text or ""
            if not msg:
                msg = "🔔 " + small_caps("Admin notification")
            admins = []
            async for u in client.iter_participants(e.chat_id, filter=ChannelParticipantsAdmins):
                if not u.bot:
                    admins.append(u)
            if not admins:
                await e.reply(small_caps("No admins.")); return
            mentions = " ".join([f"[{a.first_name or 'Admin'}](tg://user?id={a.id})" for a in admins])
            await client.send_message(e.chat_id, f"{msg}\n\n{mentions}", parse_mode='markdown')
            await e.reply(small_caps("✅ Admins mentioned"))

        @client.on(events.NewMessage(pattern='/start'))
        async def clone_start(e):
            await e.reply(small_caps("🤖 I am a clone bot. Use /mentionall or /mentionadmin"))

        await client.run_until_disconnected()
    finally:
        await client.disconnect()
        if owner_id in clones:
            clones.pop(owner_id, None)

@bot.on(events.NewMessage(pattern='/clone(?: |$)(.*)'))
async def clone_command(event):
    if event.is_group:
        await event.reply(small_caps("❌ Use /clone in private chat with me."))
        return
    token = event.pattern_match.group(1).strip()
    if not token:
        await event.reply(small_caps("Usage: /clone <bot_token_from_BotFather>"))
        return
    if event.sender_id in clones:
        await event.reply(small_caps("⚠️ You already have a clone running. Restart server to remove."))
        return
    try:
        temp = TelegramClient(f"temp_{event.sender_id}", API_ID, API_HASH).start(bot_token=token)
        me = await temp.get_me()
        await temp.disconnect()
    except Exception as e:
        await event.reply(f"❌ {small_caps('Invalid token')}: {str(e)[:100]}")
        return
    task = asyncio.create_task(run_clone_bot(token, event.sender_id))
    clones[event.sender_id] = task
    await event.reply(f"✅ {small_caps('Clone bot')} @{me.username} {small_caps('started! Add it as admin in your group and use')} /mentionall {small_caps('or')} /mentionadmin")

# ---------- START ----------
async def main():
    await bot.start()
    print("Main bot is running with stylish small-caps replies and fixed mention+message")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
