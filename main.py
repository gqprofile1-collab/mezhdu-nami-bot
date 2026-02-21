import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")

# Клавиатура
keyboard = ReplyKeyboardMarkup(
    [["Начать игру"]],
    resize_keyboard=True
)

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Между нами 🤫\n\n"
        "Игра, после которой вы узнаете друг друга чуть лучше.\n"
        "Надеюсь, ваши отношения не испортятся 😈\n\n"
        "Нажми кнопку ниже 👇",
        reply_markup=keyboard
    )

# Обработка кнопки
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "Начать игру":
        await update.message.reply_text(
            "Поехали 😈\nПервый вопрос скоро прилетит..."
        )

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
