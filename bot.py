import os
import asyncio
import traceback
from telethon import TelegramClient, events
from telethon.tl.types import ChannelParticipantsAdmins
from telethon.errors import FloodWaitError
from telethon.sessions import MemorySession

API_ID = int(os.environ.get("APP_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("TOKEN", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise Exception("APP_ID, API_HASH, TOKEN are required.")

bot = TelegramClient(MemorySession(), API_ID, API_HASH)

cancelled = set()
clones = {}  # user_id -> asyncio task


async def send_mentions(client, chat_id, text, users):
    batch_size = 5
    for i in range(0, len(users), batch_size):
        batch = users[i:i + batch_size]
        mentions = " ".join(
            [f"[{u.first_name or 'User'}](tg://user?id={u.id})" for u in batch]
        )
        msg = f"{text}\n\n{mentions}"

        try:
            await client.send_message(chat_id, msg, parse_mode="markdown")
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)

        await asyncio.sleep(1)


def register_handlers(client):
    @client.on(events.NewMessage(pattern=r"/mentionall(?: |$)(.*)"))
    async def mention_all(event):
        if not event.is_group:
            return await event.reply("ᴏɴʟʏ ɪɴ ɢʀᴏᴜᴘs.")

        text = event.pattern_match.group(1).strip() or "ᴀᴛᴛᴇɴᴛɪᴏɴ ᴇᴠᴇʀʏᴏɴᴇ!"

        users = []
        async for user in client.iter_participants(event.chat_id):
            if not user.bot and not user.deleted:
                users.append(user)

        await send_mentions(client, event.chat_id, text, users)

    @client.on(events.NewMessage(pattern=r"/mentionadmin(?: |$)(.*)"))
    async def mention_admin(event):
        if not event.is_group:
            return await event.reply("ᴏɴʟʏ ɪɴ ɢʀᴏᴜᴘs.")

        text = event.pattern_match.group(1).strip() or "ᴀᴛᴛᴇɴᴛɪᴏɴ ᴀᴅᴍɪɴs!"

        admins = []
        async for user in client.iter_participants(
            event.chat_id, filter=ChannelParticipantsAdmins
        ):
            if not user.bot:
                admins.append(user)

        await send_mentions(client, event.chat_id, text, admins)


register_handlers(bot)


@bot.on(events.NewMessage(pattern=r"/clone(?: |$)(.*)"))
async def clone_bot(event):
    if event.is_group:
        return await event.reply("ᴜsᴇ ɪɴ ᴘʀɪᴠᴀᴛᴇ.")

    token = event.pattern_match.group(1).strip()

    if not token:
        return await event.reply("ᴜsᴀɢᴇ: /clone BOT_TOKEN")

    if event.sender_id in clones:
        return await event.reply("ʏᴏᴜ ᴀʟʀᴇᴀᴅʏ ʜᴀᴠᴇ ᴀ ᴄʟᴏɴᴇ.")

    async def run_clone():
        clone_client = TelegramClient(MemorySession(), API_ID, API_HASH)
        await clone_client.start(bot_token=token)
        register_handlers(clone_client)
        me = await clone_client.get_me()
        print(f"Clone started @{me.username}")
        await clone_client.run_until_disconnected()

    try:
        task = asyncio.create_task(run_clone())
        clones[event.sender_id] = task
        await event.reply("✅ ᴄʟᴏɴᴇ ʙᴏᴛ sᴛᴀʀᴛᴇᴅ.")
    except Exception as e:
        await event.reply(f"❌ ᴇʀʀᴏʀ: {e}")


@bot.on(events.NewMessage(pattern=r"/start|/help"))
async def start_help(event):
    await event.reply(
        "**ᴍᴇɴᴛɪᴏɴ ʙᴏᴛ ⚡**\n\n"
        "/mentionall <msg>\n"
        "/mentionadmin <msg>\n"
        "/clone <bot_token>",
        parse_mode="markdown"
    )


async def main():
    await bot.start(bot_token=BOT_TOKEN)
    me = await bot.get_me()
    print(f"Bot online @{me.username}")
    await bot.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print("CRASH:", e)
        traceback.print_exc()
