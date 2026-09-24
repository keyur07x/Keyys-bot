"""
Telegram Quiz Forwarder Bot
----------------------------
No AI, no API cost. You create the quiz poll yourself in Telegram (the
native "Poll" -> "Quiz Mode" feature) and send it to this bot privately.
The bot forwards that exact quiz poll into your group automatically.

SETUP
1. Add this bot to your group and make it an ADMIN.
2. In the group, send any message, then send the command:
     /groupid
   The bot will reply with the group's chat ID (a negative number like
   -1001234567890). Copy it.
3. Set two required env vars:
     TELEGRAM_BOT_TOKEN   = your bot token from BotFather
     TARGET_GROUP_CHAT_ID = the number you copied in step 2
   Optional (only if your group has Topics enabled and you want quizzes
   posted to one specific topic instead of the group's main chat):
     TARGET_TOPIC_THREAD_ID = send /topicid inside that topic to get it
4. pip install python-telegram-bot --break-system-packages
5. Run: python telegram_forward_quiz_bot.py

USAGE
- Open Telegram, tap the attachment/paperclip icon -> Poll.
- Type your question, add options, turn ON "Quiz Mode", mark the correct
  answer, then send it to THIS BOT in a private chat (not the group).
- The bot immediately forwards that same quiz into your group.
"""

import os
import logging

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("quiz-forward-bot")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

_raw_target = os.environ.get("TARGET_GROUP_CHAT_ID", "").strip()
TARGET_GROUP_CHAT_ID = int(_raw_target) if _raw_target else None

_raw_thread = os.environ.get("TARGET_TOPIC_THREAD_ID", "").strip()
TARGET_TOPIC_THREAD_ID = int(_raw_thread) if _raw_thread else None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "Send me a quiz poll (attachment icon -> Poll -> turn on Quiz Mode) "
        "and I'll forward it straight into your group."
    )


async def groupid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(f"This chat's ID is: {update.effective_chat.id}")


async def topicid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    thread_id = msg.message_thread_id
    if thread_id is None:
        await msg.reply_text(
            "This doesn't look like a topic thread — send /topicid inside "
            "the specific topic you want quizzes posted to."
        )
    else:
        await msg.reply_text(f"This topic's thread ID is: {thread_id}")


async def handle_poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    if TARGET_GROUP_CHAT_ID is None:
        await msg.reply_text(
            "I don't know your group yet — set the TARGET_GROUP_CHAT_ID "
            "variable first (use /groupid inside the group to get it)."
        )
        return

    try:
        await context.bot.forward_message(
            chat_id=TARGET_GROUP_CHAT_ID,
            from_chat_id=msg.chat_id,
            message_id=msg.message_id,
            message_thread_id=TARGET_TOPIC_THREAD_ID,
        )
        await msg.reply_text("Quiz posted to your group ✅")
    except Exception as e:
        log.exception("forward failed")
        await msg.reply_text(
            f"Couldn't post it — make sure I'm an admin in the group. ({e})"
        )


def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("groupid", groupid))
    app.add_handler(CommandHandler("topicid", topicid))
    app.add_handler(MessageHandler(filters.POLL, handle_poll))
    log.info("Bot starting…")
    app.run_polling()


if __name__ == "__main__":
    main()
