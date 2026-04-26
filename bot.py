import os
import asyncio
import traceback
from telethon import TelegramClient, events, Button
from telethon.tl.types import ChannelParticipantsAdmins
from telethon.errors import FloodWaitError
from telethon.sessions import MemorySession
from telethon.tl.functions.channels import GetParticipantRequest

API_ID = int(os.environ.get("APP_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("TOKEN", "")

OWNER_ID = 5311223486
CLONE_SOURCE = "@number_tracker_robot"

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise Exception("APP_ID, API_HASH, TOKEN are required.")

bot = TelegramClient(MemorySession(), API_ID, API_HASH)

cancelled = {}
running = {}
clones = {}
only_admins_mode = {}

clone_owners = {}   # bot_id -> owner_id
all_clone_clients = []


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


# =========================
# HANDLERS
# =========================
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

    @client.on(events.NewMessage(pattern=r"^/cancel$"))
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

    @client.on(events.NewMessage(pattern=r"^/broadcast(?: |$)(.*)"))
    async def broadcast(event):
        msg = event.pattern_match.group(1).strip()

        if not msg:
            return await event.reply("Usage: /broadcast your_message")

        if client == bot and event.sender_id == OWNER_ID:
            for clone_client in all_clone_clients:
                try:
                    await clone_client.send_message("me", msg)
                except:
                    pass

            await event.reply("✅ Broadcast sent to all bots.")

        elif client != bot:
            me = await client.get_me()
            owner_id = clone_owners.get(me.id)

            if event.sender_id != owner_id:
                return await event.reply("You are not allowed.")

            try:
                await client.send_message("me", msg)
                await event.reply("✅ Broadcast sent.")
            except:
                await event.reply("❌ Failed.")

    @client.on(events.NewMessage(pattern=r"^/start$"))
    async def start_cmd(event):
        me = await event.client.get_me()

        start_text = (
            f"✨ **Welcome to {me.first_name}!** ✨\n\n"
            f"I am a powerful **Mention All Bot** built to make group "
            f"management easier and faster.\n\n"
            f"With a single command, I can notify all members "
            f"or only admins in your group.\n\n"
            f"⚡ Fast • Reliable • Easy to Use\n\n"
            f"Use /help to explore my features and commands."
        )

        if event.client == bot:
            buttons = [
                [
                    Button.url("📢 Support", "https://t.me/FROZENTOOLS"),
                    Button.url("💻 Source", "https://github.com/TMM-TEAM/mentionall"),
                ],
                [
                    Button.url("👑 Owner", "https://t.me/MOH_MAYA_OFFICIAL"),
                ]
            ]
            await event.respond(start_text, buttons=buttons)

        else:
            me2 = await event.client.get_me()
            owner_id = clone_owners.get(me2.id)

            if owner_username:
    owner_link = f"https://t.me/{owner_username}"
else:
    owner_link = f"https://t.me/{CLONE_SOURCE.replace('@', '')}"

buttons = [
    [
        Button.url("⚡OWNER ⚡", owner_link)
    ]
]

            await event.respond(start_text, buttons=buttons)

    @client.on(events.NewMessage(pattern=r"^/help$"))
    async def help_cmd(event):
        help_text = (
            "📘 **Bot Features & Commands**\n\n"
            "This bot helps you tag members quickly in groups.\n\n"
            "**Available Commands:**\n\n"
            "🔹 `/mentionall <text>` → Mention everyone in the group\n"
            "🔹 `@all <text>` → Same as mentionall\n"
            "🔹 `#all <text>` → Alternative trigger\n"
            "🔹 `/mentionadmin <text>` → Mention only admins\n\n"
            "⚙️ **Management Commands:**\n"
            "🔸 `/cancel` → Stop the current mention process\n"
            "🔸 `/onlyadmins` → Allow only admins to use mentionall\n"
            "🔸 `/noonlyadmins` → Allow everyone to use mentionall\n\n"
            "📢 **Broadcast:**\n"
            "🔸 `/broadcast <text>` → Send announcement\n"
        )

        await event.respond(help_text, parse_mode="markdown")


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
        try:
            clone_client = TelegramClient(MemorySession(), API_ID, API_HASH)
            await clone_client.start(bot_token=token)

            me = await clone_client.get_me()
            owner = await event.get_sender()

            register_handlers(clone_client)

            clone_owners[me.id] = event.sender_id
            all_clone_clients.append(clone_client)

            # OWNER NOTIFICATION
            try:
                notify_text = (
                    f"#New_Cloned_Bot\n\n"
                    f"Bot: {me.first_name}\n"
                    f"Username: @{me.username}\n"
                    f"Bot ID: {me.id}\n\n"
                    f"Owner: {owner.first_name}"
                )

                owner_username = getattr(owner, "username", None)

if owner_username:
    link = f"https://t.me/{owner_username}"
else:
    link = f"https://t.me/{CLONE_SOURCE.replace('@', '')}"

await bot.send_message(
    OWNER_ID,
    notify_text,
    buttons=[
        [Button.url("👑 Clone Owner", link)]
    ]
)
            except:
                pass

            await event.reply(
                f"✅ Clone bot started successfully.\n\n"
                f"Username: @{me.username}"
            )

            print(f"Clone started @{me.username}")

            await clone_client.run_until_disconnected()

        except Exception as e:
            await event.reply(f"❌ Clone failed: {e}")

    task = asyncio.create_task(run_clone())
    clones[event.sender_id] = task


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
