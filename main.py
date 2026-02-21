import asyncio
import os

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatType
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("Переменная окружения BOT_TOKEN не задана")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start_cmd(message: Message):
    # В личке и в группе реагируем одинаково (удобно для теста)
    txt = (
        "Между нами 🤫\n\n"
        "Игра, после которой вы узнаете друг друга чуть лучше.\n"
        "Надеюсь, ваши взаимоотношения не испортятся (хе-хе-хе).\n\n"
        "Добавь меня в чат и нажми «Начать игру»."
    )

    # Если команда в личке — покажем кнопку «Добавить в чат»
    if message.chat.type == ChatType.PRIVATE:
        me = await bot.get_me()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Добавить в чат", url=f"https://t.me/{me.username}?startgroup=1")]
        ])
        await message.answer(txt, reply_markup=kb)
    else:
        await message.answer(txt)


@dp.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def group_text_handler(message: Message):
    # Мини-MVP: если кто-то пишет "начать игру" — отвечаем
    if not message.text:
        return

    if message.text.strip().lower() == "начать игру":
        await message.answer("Окей 😈\nСкоро начнём. (Это тестовый ответ MVP)")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
