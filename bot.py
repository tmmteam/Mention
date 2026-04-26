import os
import asyncio
import traceback
from telethon import TelegramClient, events
from telethon.tl.types import ChannelParticipantsAdmins
from telethon.errors import FloodWaitError
from telethon.sessions import MemorySession

# ---------- ENVIRONMENT VARIABLES ----------
API_ID = int(os.environ.get("APP_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("TOKEN", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise Exception("APP_ID, API_HASH, TOKEN environment variables are required.")

# ---------- GLOBAL VARIABLES ----------
clones = {}   # {user_id: task}
cancelled = set()

# ---------- CLONE BOT ----------
async def run_clone_bot(token: str, owner_id: int):
    client = TelegramClient(MemorySession(), API_ID, API_HASH)

    try:
        await client.start(bot_token=token)
        me = await client.get_me()
        print(f"Clone bot @{me.username} started for user {owner_id}")

        @client.on(events.NewMessage(pattern=r'/mentionall(?: |$)(.*)'))
        async def clone_mentionall(event):
            if not event.is_group:
                await event.reply("यह कमांड सिर्फ ग्रुप में काम करेगी।")
                return

            if event.pattern_match.group(1):
                mention_text = event.pattern_match.group(1)
            elif event.is_reply:
                reply_msg = await event.get_reply_message()
                mention_text = reply_msg.text or "मेन्शन मैसेज"
            else:
                mention_text = "⚠️ कोई टेक्स्ट नहीं दिया गया!"

            users = []
            async for user in client.iter_participants(event.chat_id):
                if not user.bot and not user.deleted:
                    users.append(user)

            if not users:
                await event.reply("कोई सदस्य नहीं मिला।")
                return

            await event.reply(f"🔄 {len(users)} सदस्यों को मेंशन किया जा रहा है...")

            batch_size = 5
            for i in range(0, len(users), batch_size):
                batch = users[i:i+batch_size]
                mentions = " ".join(
                    [f"[{u.first_name or 'User'}](tg://user?id={u.id})" for u in batch]
                )

                msg = f"{mention_text}\n\n{mentions}" if i == 0 else mentions

                try:
                    await client.send_message(event.chat_id, msg, parse_mode="markdown")
                except FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    print("Error:", e)

                await asyncio.sleep(1)

            await client.send_message(event.chat_id, "✅ सभी को मेंशन कर दिया गया।")

        @client.on(events.NewMessage(pattern=r'/mentionadmin'))
        async def clone_mentionadmin(event):
            if not event.is_group:
                await event.reply("यह कमांड सिर्फ ग्रुप में काम करेगी।")
                return

            admins = []
            async for user in client.iter_participants(
                event.chat_id, filter=ChannelParticipantsAdmins
            ):
                if not user.bot:
                    admins.append(user)

            if not admins:
                await event.reply("कोई एडमिन नहीं मिला।")
                return

            mentions = " ".join(
                [f"[{a.first_name or 'Admin'}](tg://user?id={a.id})" for a in admins]
            )

            await client.send_message(
                event.chat_id,
                f"🔔 एडमिन्स को सूचना:\n{mentions}",
                parse_mode="markdown"
            )

        @client.on(events.NewMessage(pattern=r'/start'))
        async def clone_start(event):
            await event.reply("मैं एक क्लोन बॉट हूँ। /mentionall और /mentionadmin उपयोग करें।")

        await client.run_until_disconnected()

    except Exception as e:
        print("Clone bot crashed:", e)
        traceback.print_exc()

    finally:
        await client.disconnect()
        clones.pop(owner_id, None)

# ---------- MAIN BOT ----------
bot = TelegramClient(MemorySession(), API_ID, API_HASH)

@bot.on(events.NewMessage(pattern=r'/start|/help'))
async def start_help(event):
    await event.reply(
        "**🤖 Mention Bot**\n\n"
        "👉 `/mentionall <msg>` - सभी को टैग करें\n"
        "👉 `/mentionadmin` - एडमिन्स को टैग करें\n"
        "👉 `/clone <bot_token>` - अपना क्लोन बॉट चलाएं\n"
        "👉 `/cancel` - mention रोकें",
        parse_mode="markdown"
    )

@bot.on(events.NewMessage(pattern=r'/mentionall(?: |$)(.*)'))
async def mention_all(event):
    if not event.is_group:
        await event.reply("यह कमांड सिर्फ ग्रुप में काम करेगी।")
        return

    if event.pattern_match.group(1):
        text = event.pattern_match.group(1)
    elif event.is_reply:
        reply = await event.get_reply_message()
        text = reply.text or "मेन्शन मैसेज"
    else:
        text = "📢 सभी सदस्यों को सूचना!"

    users = []
    async for user in bot.iter_participants(event.chat_id):
        if not user.bot and not user.deleted:
            users.append(user)

    if not users:
        await event.reply("कोई सदस्य नहीं मिला।")
        return

    cancelled.discard(event.chat_id)

    await event.reply(f"🔄 {len(users)} लोगों को मेंशन किया जा रहा है...")

    batch_size = 5
    for i in range(0, len(users), batch_size):
        if event.chat_id in cancelled:
            await event.reply("⛔ मेंशन रद्द कर दिया गया।")
            cancelled.discard(event.chat_id)
            return

        batch = users[i:i+batch_size]
        mentions = " ".join(
            [f"[{u.first_name or 'User'}](tg://user?id={u.id})" for u in batch]
        )

        msg = f"{text}\n\n{mentions}" if i == 0 else mentions

        try:
            await bot.send_message(event.chat_id, msg, parse_mode="markdown")
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print("Error:", e)

        await asyncio.sleep(1)

    await bot.send_message(event.chat_id, "✅ सभी को मेंशन कर दिया गया।")

@bot.on(events.NewMessage(pattern=r'/mentionadmin'))
async def mention_admin(event):
    if not event.is_group:
        await event.reply("यह कमांड सिर्फ ग्रुप में काम करेगी।")
        return

    admins = []
    async for user in bot.iter_participants(
        event.chat_id, filter=ChannelParticipantsAdmins
    ):
        if not user.bot:
            admins.append(user)

    if not admins:
        await event.reply("कोई एडमिन नहीं मिला।")
        return

    mentions = " ".join(
        [f"[{a.first_name or 'Admin'}](tg://user?id={a.id})" for a in admins]
    )

    await bot.send_message(
        event.chat_id,
        f"🔔 एडमिन्स को सूचना:\n{mentions}",
        parse_mode="markdown"
    )

@bot.on(events.NewMessage(pattern=r'/cancel'))
async def cancel_mention(event):
    cancelled.add(event.chat_id)
    await event.reply("🛑 cancel request भेज दी गई है।")

@bot.on(events.NewMessage(pattern=r'/clone(?: |$)(.*)'))
async def clone_bot(event):
    if event.is_group:
        await event.reply("❌ यह कमांड private chat में उपयोग करें।")
        return

    token = event.pattern_match.group(1).strip()

    if not token:
        await event.reply("Usage: `/clone BOT_TOKEN`", parse_mode="markdown")
        return

    if event.sender_id in clones:
        await event.reply("⚠️ आपका एक clone पहले से चल रहा है।")
        return

    try:
        temp_client = TelegramClient(MemorySession(), API_ID, API_HASH)
        await temp_client.start(bot_token=token)
        me = await temp_client.get_me()
        await temp_client.disconnect()

    except Exception as e:
        await event.reply(f"❌ Invalid token: {str(e)}")
        return

    task = asyncio.create_task(run_clone_bot(token, event.sender_id))
    clones[event.sender_id] = task

    await event.reply(
        f"✅ Clone bot @{me.username} शुरू हो गया।"
    )

# ---------- START ----------
async def main():
    await bot.start(bot_token=BOT_TOKEN)
    print("Main bot running...")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print("CRASH:", e)
        traceback.print_exc()
