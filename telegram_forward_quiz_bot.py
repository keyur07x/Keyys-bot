"""

import os
import json
import base64
import logging

from telegram import Update, Poll
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)
from anthropic import Anthropic

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("mcq-quiz-bot")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

EXTRACTION_PROMPT = """You are reading a photo of a multiple-choice question
(it may be in English or Gujarati). Extract it and respond with ONLY a JSON
object, no markdown fences, no extra text, in this exact shape:

{
  "question": "the question text, max 290 characters",
  "options": ["option A", "option B", "..."],
  "correct_index": 0,
  "explanation": "one short sentence, max 195 characters, why that answer is correct"
}

Rules:
- 2 to 10 options, each under 95 characters.
- correct_index is 0-based, pointing to the right option.
- If the photo shows the correct answer marked/underlined/circled, use that.
- If no answer is marked, work out the correct answer yourself.
- If the image has no readable MCQ at all, respond with {"error": "reason"} instead.
"""


def extract_mcq(image_bytes: bytes, media_type: str, caption_hint: str | None) -> dict:
    content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64.b64encode(image_bytes).decode("utf-8"),
            },
        },
        {"type": "text", "text": EXTRACTION_PROMPT + (f"\nHint from sender: {caption_hint}" if caption_hint else "")},
    ]

    resp = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": content}],
    )

    raw = "".join(block.text for block in resp.content if block.type == "text").strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    caption = msg.caption

    photo = msg.photo[-1]  # highest resolution
    tg_file = await context.bot.get_file(photo.file_id)
    image_bytes = bytes(await tg_file.download_as_bytearray())

    await msg.reply_text("Reading the question…")

    try:
        data = extract_mcq(image_bytes, "image/jpeg", caption)
    except Exception as e:
        log.exception("extraction failed")
        await msg.reply_text(f"Couldn't read that image: {e}")
        return

    if "error" in data:
        await msg.reply_text(f"Couldn't find a clear MCQ in that photo: {data['error']}")
        return

    question = data["question"][:295]
    options = [o[:99] for o in data["options"]][:10]
    correct_index = data["correct_index"]
    explanation = (data.get("explanation") or "")[:195]

    if len(options) < 2 or not (0 <= correct_index < len(options)):
        await msg.reply_text("Extracted question didn't have valid options — try a clearer photo.")
        return

    await context.bot.send_poll(
        chat_id=msg.chat_id,
        question=question,
        options=options,
        type=Poll.QUIZ,
        correct_option_id=correct_index,
        explanation=explanation or None,
        is_anonymous=True,
        reply_to_message_id=msg.message_id,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "Send me a photo of an MCQ question (in this chat or a group I'm admin in) "
        "and I'll turn it into a quiz poll here."
    )


def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    log.info("Bot starting…")
    app.run_polling()


if __name__ == "__main__":
    main()
  
