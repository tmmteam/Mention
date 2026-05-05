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

clone_owners = {}
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

    @client.on(events.NewMessage(pattern=r"^/start$"))
    async def start_cmd(event):
        me = await event.client.get_me()

        start_text = (
            f"✨ **Welcome to {me.first_name}!** ✨\n\n"
            f"I am a powerful Mention All Bot built to make group management easier and faster.\nWith a single command, I can notify all members or only admins in your group.        
            f"⚡ Fast • Reliable • Easy to Use\n\n"
            f"Use /help to explore my features."
        )

        if event.client == bot:
            buttons = [
                [Button.url("📢 Support", "https://t.me/FROZENTOOLS")],
                [Button.url("👑 Owner", "https://t.me/MOH_MAYA_OFFICIAL")]
            ]
        else:
            me2 = await event.client.get_me()
            owner_id = clone_owners.get(me2.id)

            owner = await bot.get_entity(owner_id)
            owner_username = getattr(owner, "username", None)

            if owner_username:
                owner_link = f"https://t.me/{owner_username}"
            else:
                owner_link = "https://t.me/frozentools"

            buttons = [
                [Button.url("⚡OWNER ⚡", owner_link)]
            ]

        await event.respond(start_text, buttons=buttons)


register_handlers(bot)

# =========================
# HELP COMMAND 
# =========================
client.on(events.NewMessage(pattern=r"^/help$"))
async def help_cmd(event):
    me = await event.client.get_me()

    help_text = (
        f"📘 **{me.first_name} - Help Menu**\n\n"

        f"🤖 This bot helps you tag members quickly in groups.\n\n"

        f"🔹 **Available Commands:**\n"
        f"/mentionall <text> → Mention everyone in the group\n"
        f"@all <text> → Same as mentionall\n"
        f"#all <text> → Alternative trigger\n"
        f"/mentionadmin <text> → Mention only admins\n\n"

        f"⚙️ **Management Commands:**\n"
        f"/stopall → Stop the current mention process\n"
        f"/onlyadmins → Allow only admins to use mentionall\n"
        f"/noonlyadmins → Allow everyone to use mentionall\n\n"

        f"📢 **Broadcast:**\n"
        f"/broadcast <text> → Send announcement"
    )
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
        process = await event.reply("⚡ **Clone Process Started...**\n\n`10%`")

        try:
            await asyncio.sleep(1)
            await process.edit("⚡ **Validating Token...**\n\n`30%`")

            clone_client = TelegramClient(MemorySession(), API_ID, API_HASH)
            await clone_client.start(bot_token=token)

            await asyncio.sleep(1)
            await process.edit("⚡ **Setting Up Clone...**\n\n`60%`")

            me = await clone_client.get_me()
            owner = await event.get_sender()

            register_handlers(clone_client)

            clone_owners[me.id] = event.sender_id
            all_clone_clients.append(clone_client)

            await asyncio.sleep(1)
            await process.edit("⚡ **Finalizing Clone...**\n\n`90%`")

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
                    link = "https://t.me/frozentools"

                await bot.send_message(
                    OWNER_ID,
                    notify_text,
                    buttons=[[Button.url("👑 Clone Owner", link)]]
                )
            except:
                pass

            await process.edit(
                f"✅ **Clone Completed Successfully!**\n\n"
                f"Bot: @{me.username}\n"
                f"`100%`"
            )

            print(f"Clone started @{me.username}")

            await clone_client.run_until_disconnected()

        except Exception as e:
            await process.edit(f"❌ Clone failed:\n`{e}`")

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
