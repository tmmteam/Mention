import os
import asyncio
import traceback
from telethon import TelegramClient, events
from telethon.tl.types import ChannelParticipantsAdmins
from telethon.errors import FloodWaitError
from telethon.sessions import MemorySession
from telethon.tl.functions.channels import GetParticipantRequest

API_ID = int(os.environ.get("APP_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("TOKEN", "")

OWNER_ID = 5311223486
CLONE_SOURCE = "@Member_tag_bot"

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise Exception("APP_ID, API_HASH, TOKEN are required.")

bot = TelegramClient(MemorySession(), API_ID, API_HASH)

cancelled = {}       # chat_id -> bool
running = {}         # chat_id -> user_id
clones = {}          # user_id -> task
only_admins_mode = {}  # chat_id -> bool


# =========================
# HELPERS
# =========================
async def is_admin(client, chat_id, user_id):
    try:
        participant = await client(GetParticipantRequest(chat_id, user_id))
        return getattr(participant.participant, "admin_rights", None) or getattr(
            participant.participant, "rank", None
        )
    except:
        return False


async def send_mentions(client, chat_id, text, users, starter_id):
    batch_size = 5
    cancelled[chat_id] = False
    running[chat_id] = starter_id

    for i in range(0, len(users), batch_size):
        if cancelled.get(chat_id):
            break

        batch = users[i:i + batch_size]
        mentions = " ".join(
            [f"[{u.first_name or 'User'}](tg://user?id={u.id})" for u in batch]
        )

        msg = f"{text}\n\n{mentions}"

        try:
            await client.send_message(chat_id, msg, parse_mode="markdown")
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
        except:
            pass

        await asyncio.sleep(1)

    running.pop(chat_id, None)
    cancelled.pop(chat_id, None)


def register_handlers(client):
    @client.on(events.NewMessage(pattern=r"^(/mentionall|@all|#all)(?: |$)(.*)"))
    async def mention_all(event):
        if not event.is_group:
            return

        if only_admins_mode.get(event.chat_id, False):
            if not await is_admin(client, event.chat_id, event.sender_id):
                return await event.reply("Only admins can use this command.")

        text = event.pattern_match.group(2).strip() or "Attention everyone!"

        users = []
        async for user in client.iter_participants(event.chat_id):
            if not user.bot and not user.deleted:
                users.append(user)

        await send_mentions(client, event.chat_id, text, users, event.sender_id)

    @client.on(events.NewMessage(pattern=r"^(/mentionadmin)(?: |$)(.*)"))
    async def mention_admin(event):
        if not event.is_group:
            return

        text = event.pattern_match.group(2).strip() or "Attention admins!"

        admins = []
        async for user in client.iter_participants(
            event.chat_id, filter=ChannelParticipantsAdmins
        ):
            if not user.bot:
                admins.append(user)

        await send_mentions(client, event.chat_id, text, admins, event.sender_id)

    @client.on(events.NewMessage(pattern=r"^/stopall$"))
    async def stop_all(event):
        if not event.is_group:
            return

        if event.chat_id not in running:
            return await event.reply("No active mentionall running.")

        starter = running[event.chat_id]

        if event.sender_id != starter and not await is_admin(
            client, event.chat_id, event.sender_id
        ):
            return await event.reply("You are not allowed to stop this.")

        cancelled[event.chat_id] = True
        await event.reply("Stopped mentionall.")

    @client.on(events.NewMessage(pattern=r"^/onlyadmins$"))
    async def only_admins(event):
        if not event.is_group:
            return

        if not await is_admin(client, event.chat_id, event.sender_id):
            return await event.reply("Admins only.")

        only_admins_mode[event.chat_id] = True
        await event.reply("Now only admins can use mentionall.")

    @client.on(events.NewMessage(pattern=r"^/noonlyadmins$"))
    async def no_only_admins(event):
        if not event.is_group:
            return

        if not await is_admin(client, event.chat_id, event.sender_id):
            return await event.reply("Admins only.")

        only_admins_mode[event.chat_id] = False
        await event.reply("Now everyone can use mentionall.")


register_handlers(bot)


# =========================
# CLONE SYSTEM
# =========================
@bot.on(events.NewMessage(pattern=r"/clone(?: |$)(.*)"))
async def clone_bot(event):
    if event.is_group:
        return await event.reply("Use in private.")

    token = event.pattern_match.group(1).strip()

    if not token:
        return await event.reply("Usage: /clone BOT_TOKEN")

    if event.sender_id in clones:
        return await event.reply("You already have a clone running.")

    async def run_clone():
        clone_client = TelegramClient(MemorySession(), API_ID, API_HASH)
        await clone_client.start(bot_token=token)
        register_handlers(clone_client)

        me = await clone_client.get_me()
        owner = await event.get_sender()

        notif = (
            f"#New_Cloned_Bot\n\n"
            f"ʙᴏᴛ:- {me.first_name}\n"
            f"ᴜsᴇʀɴᴀᴍᴇ: @{me.username}\n"
            f"ʙᴏᴛ ɪᴅ : {me.id}\n\n"
            f"ᴏᴡɴᴇʀ : {owner.first_name} ({owner.id})"
        )

        try:
            await bot.send_message(OWNER_ID, notif)
        except:
            pass

        print(f"Clone started @{me.username}")
        await clone_client.run_until_disconnected()

    try:
        task = asyncio.create_task(run_clone())
        clones[event.sender_id] = task
        await event.reply("✅ Clone bot started.")
    except Exception as e:
        await event.reply(f"❌ Error: {e}")


# =========================
# START / HELP
# =========================
@bot.on(events.NewMessage(pattern=r"/start|/help"))
async def start_help(event):
    me = await bot.get_me()

    text = (
        f"Hi and welcome to @{me.username}.\n"
        f"This bot is used to tag all the users in a group.\n\n"
        f"To use it, it's only needed to insert it in a group "
        f"(as standard user) and to start a phrase with @all or #all.\n\n"
        f"Commands (to write in group):\n"
        f"- /stopall - Stops a running @all.\n"
        f"- /onlyadmins - Set the bot to work only for admins.\n"
        f"- /noonlyadmins - Set the bot to work with everyone.\n\n"
        f"I suggest to clone the bot in order to have a better performance.\n"
        f"If you want to do that, just write /clone in a private chat."
    )

    buttons = [
        [
            Button.url('📡 Channel', 'https://t.me/FROZENTOOLS'),
            Button.url('ℹ️ Source', 'https://github.com/TMM-TEAM/mentionall')
        ]
    ]

    await event.respond(text, buttons=buttons)
    if event.client != bot:
        text += f"\n\nYou can clone from here only {CLONE_SOURCE}"

    await event.reply(text)


# =========================
# MAIN
# =========================
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
        traceback.print_exc()    @client.on(events.NewMessage(pattern=r"^/stopall$"))
    async def stop_all(event):
        if not event.is_group:
            return

        if event.chat_id not in running:
            return await event.reply("No active mentionall running.")

        starter = running[event.chat_id]

        if event.sender_id != starter and not await is_admin(
            client, event.chat_id, event.sender_id
        ):
            return await event.reply("You are not allowed to stop this.")

        cancelled[event.chat_id] = True
        await event.reply("Stopped mentionall.")

    @client.on(events.NewMessage(pattern=r"^/onlyadmins$"))
    async def only_admins(event):
        if not event.is_group:
            return

        if not await is_admin(client, event.chat_id, event.sender_id):
            return await event.reply("Admins only.")

        only_admins_mode[event.chat_id] = True
        await event.reply("Now only admins can use mentionall.")

    @client.on(events.NewMessage(pattern=r"^/noonlyadmins$"))
    async def no_only_admins(event):
        if not event.is_group:
            return

        if not await is_admin(client, event.chat_id, event.sender_id):
            return await event.reply("Admins only.")

        only_admins_mode[event.chat_id] = False
        await event.reply("Now everyone can use mentionall.")


register_handlers(bot)


# =========================
# CLONE SYSTEM
# =========================
@bot.on(events.NewMessage(pattern=r"/clone(?: |$)(.*)"))
async def clone_bot(event):
    if event.is_group:
        return await event.reply("Use in private.")

    token = event.pattern_match.group(1).strip()

    if not token:
        return await event.reply("Usage: /clone BOT_TOKEN")

    if event.sender_id in clones:
        return await event.reply("You already have a clone running.")

    async def run_clone():
        clone_client = TelegramClient(MemorySession(), API_ID, API_HASH)
        await clone_client.start(bot_token=token)
        register_handlers(clone_client)

        me = await clone_client.get_me()
        owner = await event.get_sender()

        notif = (
            f"#New_Cloned_Bot\n\n"
            f"ʙᴏᴛ:- {me.first_name}\n"
            f"ᴜsᴇʀɴᴀᴍᴇ: @{me.username}\n"
            f"ʙᴏᴛ ɪᴅ : {me.id}\n\n"
            f"ᴏᴡɴᴇʀ : {owner.first_name} ({owner.id})"
        )

        try:
            await bot.send_message(OWNER_ID, notif)
        except:
            pass

        print(f"Clone started @{me.username}")
        await clone_client.run_until_disconnected()

    try:
        task = asyncio.create_task(run_clone())
        clones[event.sender_id] = task
        await event.reply("✅ Clone bot started.")
    except Exception as e:
        await event.reply(f"❌ Error: {e}")


# =========================
# START / HELP
# =========================
@bot.on(events.NewMessage(pattern=r"/start|/help"))
async def start_help(event):
    me = await bot.get_me()

    text = (
        f"Hi and welcome to @{me.username}.\n"
        f"This bot is used to tag all the users in a group.\n\n"
        f"To use it, it's only needed to insert it in a group "
        f"(as standard user) and to start a phrase with @all or #all.\n\n"
        f"Commands (to write in group):\n"
        f"- /stopall - Stops a running @all.\n"
        f"- /onlyadmins - Set the bot to work only for admins.\n"
        f"- /noonlyadmins - Set the bot to work with everyone.\n\n"
        f"I suggest to clone the bot in order to have a better performance.\n"
        f"If you want to do that, just write /clone in a private chat."
    )

    if event.client != bot:
        text += f"\n\nYou can clone from here only {CLONE_SOURCE}"

    await event.reply(text)


# =========================
# MAIN
# =========================
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
