import os
import asyncio
from telethon import TelegramClient, events, functions, types
from telethon.tl.types import ChannelParticipantsAdmins, ChannelParticipantsSearch
from telethon.errors import FloodWaitError

# ---------- ENVIRONMENT VARIABLES ----------
API_ID = int(os.environ.get("APP_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("TOKEN", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise Exception("APP_ID, API_HASH, TOKEN environment variables are required.")

# ---------- GLOBAL VARIABLES ----------
# Store running clone bots: {user_id: (task, client)}
clones = {}
# To handle cancel operation for mentionall (per chat)
cancelled = set()

# ---------- CLONE BOT HANDLER (दूसरे बॉट के लिए कोर फंक्शन) ----------
async def run_clone_bot(token: str, owner_id: int):
    """एक अलग टेलीग्राम क्लाइंट चलाता है जो सिर्फ mentionall और mentionadmin सपोर्ट करता है"""
    client = TelegramClient(f"clone_{owner_id}_{token[:10]}", API_ID, API_HASH).start(bot_token=token)
    try:
        me = await client.get_me()
        print(f"Clone bot @{me.username} started for user {owner_id}")

        @client.on(events.NewMessage(pattern='/mentionall(?: |$)(.*)'))
        async def clone_mentionall(event):
            if not event.is_group:
                await event.reply("यह कमांड सिर्फ ग्रुप में काम करेगी।")
                return

            # वैकल्पिक रूप से: सिर्फ ऐडमिन को इस्तेमाल की अनुमति दें
            sender = await event.get_sender()
            chat = await event.get_chat()
            if not (chat.admin_rights or chat.creator):
                await event.reply("❌ आपको इस ग्रुप का एडमिन होना चाहिए।")
                return

            # मेंशन टेक्स्ट तैयार करना
            if event.pattern_match.group(1):
                mention_text = event.pattern_match.group(1)
            elif event.is_reply:
                reply_msg = await event.get_reply_message()
                mention_text = reply_msg.text or "मेन्शन मैसेज"
            else:
                mention_text = "⚠️ कोई टेक्स्ट नहीं दिया गया!"

            # सदस्यों को इकट्ठा करना
            users = []
            async for user in client.iter_participants(event.chat_id):
                if not user.bot and not user.deleted:
                    users.append(user)

            if not users:
                await event.reply("कोई सदस्य नहीं मिला।")
                return

            # बैच में मेंशन भेजना (flood wait से बचने के लिए)
            await event.reply(f"🔄 **{len(users)}** सदस्यों को मेंशन किया जा रहा है... कृपया प्रतीक्षा करें।")
            batch_size = 5
            for i in range(0, len(users), batch_size):
                batch = users[i:i+batch_size]
                mentions = " ".join([f"[{u.first_name or 'User'}](tg://user?id={u.id})" for u in batch])
                msg_to_send = f"{mention_text}\n\n{mentions}" if i == 0 else mentions
                try:
                    await client.send_message(event.chat_id, msg_to_send, parse_mode='markdown')
                except FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    print(f"Error: {e}")
                await asyncio.sleep(1)  # छोटा ब्रेक
            await client.send_message(event.chat_id, "✅ सभी सदस्यों को मेंशन कर दिया गया।")

        @client.on(events.NewMessage(pattern='/mentionadmin'))
        async def clone_mentionadmin(event):
            if not event.is_group:
                await event.reply("यह कमांड सिर्फ ग्रुप में काम करेगी।")
                return

            sender = await event.get_sender()
            chat = await event.get_chat()
            if not (chat.admin_rights or chat.creator):
                await event.reply("❌ केवल एडमिन ही इस कमांड का उपयोग कर सकते हैं।")
                return

            # सिर्फ एडमिन्स निकालना
            admins = []
            async for user in client.iter_participants(event.chat_id, filter=ChannelParticipantsAdmins):
                if not user.bot:
                    admins.append(user)

            if not admins:
                await event.reply("इस ग्रुप में कोई एडमिन नहीं मिला।")
                return

            mentions = " ".join([f"[{a.first_name or 'Admin'}](tg://user?id={a.id})" for a in admins])
            text = f"🔔 **एडमिन्स को सूचना:**\n{mentions}"
            await client.send_message(event.chat_id, text, parse_mode='markdown')

        # बेसिक कमांड्स
        @client.on(events.NewMessage(pattern='/start'))
        async def clone_start(event):
            await event.reply(f"मैं एक क्लोन बॉट हूँ। /mentionall और /mentionadmin का उपयोग कर सकते हैं।")

        await client.run_until_disconnected()
    finally:
        await client.disconnect()
        # क्लोन लिस्ट से हटाएँ अगर क्रैश हो जाए
        if owner_id in clones:
            clones.pop(owner_id, None)

# ---------- MAIN BOT ----------
bot = TelegramClient("mentionall_bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

@bot.on(events.NewMessage(pattern='/start|/help'))
async def start_help(event):
    await event.reply(
        "**🤖 मेंशनऑल बॉट**\n\n"
        "👉 `/mentionall <मैसेज>` – सभी सदस्यों को टैग करें\n"
        "👉 `/mentionadmin` – केवल ऐडमिन्स को टैग करें\n"
        "👉 `/clone <बॉट_टोकन>` – अपना खुद का क्लोन बॉट चलाएं\n"
        "👉 `/cancel` – चल रहे मेंशन को रोकें\n\n"
        "बॉट को एडमिन बनाना न भूलें।",
        parse_mode='markdown'
    )

@bot.on(events.NewMessage(pattern='/mentionall(?: |$)(.*)'))
async def mention_all(event):
    if not event.is_group:
        await event.reply("यह कमांड सिर्फ ग्रुप में काम करेगी।")
        return

    chat = await event.get_chat()
    if not (chat.admin_rights or chat.creator):
        await event.reply("❌ केवल एडमिन ही इस कमांड का उपयोग कर सकते हैं।")
        return

    # मेंशन टेक्स्ट
    if event.pattern_match.group(1):
        text = event.pattern_match.group(1)
    elif event.is_reply:
        reply = await event.get_reply_message()
        text = reply.text or "मेन्शन मैसेज"
    else:
        text = "📢 सभी सदस्यों को सूचित किया जाता है!"

    # सदस्य लाना
    users = []
    async for user in bot.iter_participants(event.chat_id):
        if not user.bot and not user.deleted:
            users.append(user)

    if not users:
        await event.reply("कोई सदस्य नहीं मिला।")
        return

    cancelled.discard(event.chat_id)  # पिछला cancel रीसेट
    await event.reply(f"🔄 **{len(users)}** सदस्यों को मेंशन किया जा रहा है... (रोकने के लिए /cancel)")

    batch_size = 5
    for i in range(0, len(users), batch_size):
        if event.chat_id in cancelled:
            await event.reply("⛔ मेंशन प्रोसेस रद्द कर दी गई।")
            cancelled.discard(event.chat_id)
            return
        batch = users[i:i+batch_size]
        mentions = " ".join([f"[{u.first_name or 'User'}](tg://user?id={u.id})" for u in batch])
        msg = f"{text}\n\n{mentions}" if i == 0 else mentions
        try:
            await bot.send_message(event.chat_id, msg, parse_mode='markdown')
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print(f"Error: {e}")
        await asyncio.sleep(1)  # one second gap between batches
    await bot.send_message(event.chat_id, "✅ सभी सदस्यों को मेंशन कर दिया गया।")

@bot.on(events.NewMessage(pattern='/mentionadmin'))
async def mention_admin(event):
    if not event.is_group:
        await event.reply("यह कमांड सिर्फ ग्रुप में काम करेगी।")
        return

    chat = await event.get_chat()
    if not (chat.admin_rights or chat.creator):
        await event.reply("❌ केवल एडमिन ही इस कमांड का उपयोग कर सकते हैं।")
        return

    admins = []
    async for user in bot.iter_participants(event.chat_id, filter=ChannelParticipantsAdmins):
        if not user.bot:
            admins.append(user)

    if not admins:
        await event.reply("कोई एडमिन नहीं मिला।")
        return

    mentions = " ".join([f"[{a.first_name or 'Admin'}](tg://user?id={a.id})" for a in admins])
    await bot.send_message(event.chat_id, f"🔔 **एडमिन्स को सूचना:**\n{mentions}", parse_mode='markdown')

@bot.on(events.NewMessage(pattern='/cancel'))
async def cancel_mention(event):
    if event.chat_id in cancelled:
        await event.reply("❌ पहले से ही कोई मेंशन रद्द करने की प्रक्रिया चल रही है।")
    else:
        cancelled.add(event.chat_id)
        await event.reply("🛑 चल रहे मेंशन को रद्द करने का अनुरोध किया गया है। कृपया कुछ सेकंड प्रतीक्षा करें।")

@bot.on(events.NewMessage(pattern='/clone(?: |$)(.*)'))
async def clone_bot(event):
    # सिर्फ प्राइवेट चैट में क्लोन करने दें (ग्रुप में नहीं)
    if event.is_group:
        await event.reply("❌ यह कमांड सिर्फ मेरे साथ प्राइवेट चैट में उपयोग करें।")
        return

    args = event.pattern_match.group(1).strip()
    if not args:
        await event.reply("सही तरीका: `/clone BOT_TOKEN`\n\nआप @BotFather से टोकन ले सकते हैं।")
        return

    token = args
    # पहले से क्लोन तो नहीं है?
    if event.sender_id in clones:
        await event.reply("⚠️ आप पहले से एक क्लोन बॉट चला रहे हैं। दूसरा चलाने के लिए पहले वाला बंद करें (सर्वर रीस्टार्ट जरूरी)।")
        return

    # टोकन वेरिफाई करें
    try:
        temp_client = TelegramClient(f"temp_{event.sender_id}", API_ID, API_HASH).start(bot_token=token)
        me = await temp_client.get_me()
        await temp_client.disconnect()
    except Exception as e:
        await event.reply(f"❌ टोकन गलत है या बॉट मौजूद नहीं है। एरर: {str(e)[:100]}")
        return

    # नया टास्क शुरू करें
    task = asyncio.create_task(run_clone_bot(token, event.sender_id))
    clones[event.sender_id] = task
    await event.reply(f"✅ **क्लोन बॉट @{me.username} सफलतापूर्वक शुरू हो गया है।**\n\nअब आप उसे अपने ग्रुप में एडमिन बनाकर /mentionall और /mentionadmin का उपयोग कर सकते हैं।")

# ---------- START MAIN BOT ----------
async def main():
    await bot.start()
    print("मुख्य बॉट चल रहा है...")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
