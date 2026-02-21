import asyncio
import os
import random

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatType
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в переменных окружения (Railway Variables).")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# -----------------------------
# MVP: вопросы (потом расширим)
# -----------------------------
QUESTIONS = [
    "Кто из вас мог бы увести чужого партнёра? Отвечайте честно. Это между нами 🤫",
    "Кто чаще всего врёт “по мелочи” — и делает вид, что так и надо?",
    "Кто самый опасный в конфликте: тихий, но мстительный?",
    "Кто способен на поступок, который потом будет стыдно вспоминать?",
    "Кто здесь самый харизматичный манипулятор?",
    "Кто первым сорвётся на “да пошло оно всё” и сделает глупость?",
]

# Память в оперативке (на MVP достаточно)
# chat_id -> {"active": bool, "used": set[int], "round": int}
GAMES: dict[int, dict] = {}


def kb_main() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Начать игру")]],
        resize_keyboard=True,
        selective=False,
    )


def kb_game() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Следующий вопросик")],
            [KeyboardButton(text="Завершить игру")],
        ],
        resize_keyboard=True,
        selective=False,
    )


def pick_question(chat_id: int) -> str:
    st = GAMES.setdefault(chat_id, {"active": False, "used": set(), "round": 0})
    used = st["used"]

    # не повторяемся, пока не закончатся
    if len(used) >= len(QUESTIONS):
        used.clear()

    idx = random.randrange(len(QUESTIONS))
    while idx in used:
        idx = random.randrange(len(QUESTIONS))

    used.add(idx)
    st["round"] += 1
    return QUESTIONS[idx]


async def send_question(message: Message):
    q = pick_question(message.chat.id)
    r = GAMES[message.chat.id]["round"]

    await message.answer(
        f"Раунд {r} 😈\n\n{q}\n\n"
        "Обсудите. А потом жмите «Следующий вопросик».",
        reply_markup=kb_game(),
    )


# -----------------------------
# Команды /start и /help
# -----------------------------
@dp.message(CommandStart())
async def start_cmd(message: Message):
    # Кнопки лучше показывать в ЛС. В группе Telegram иногда “прячет” клавиатуру.
    await message.answer(
        "Между нами 🤫\n\n"
        "Игра для компаний и пар. Будет немного провокационно.\n"
        "Надеюсь, ваши отношения не испортятся (хе-хе-хе).\n\n"
        "Нажми «Начать игру» 👇",
        reply_markup=kb_main(),
    )


@dp.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "Как играть:\n"
        "1) Нажмите «Начать игру»\n"
        "2) Читайте вопрос вслух\n"
        "3) Обсуждайте\n"
        "4) Жмите «Следующий вопросик»\n\n"
        "Чтобы остановиться — «Завершить игру».",
        reply_markup=kb_main(),
    )


# -----------------------------
# Кнопки / сообщения
# -----------------------------
@dp.message(F.text == "Начать игру")
async def start_game(message: Message):
    # В группе реагируем тоже (если privacy выключен — см. ниже)
    GAMES[message.chat.id] = {"active": True, "used": set(), "round": 0}

    await message.answer(
        "Ну что? Погнали? 🔥\n"
        "Только без обид… это между нами 🤫",
        reply_markup=kb_game(),
    )
    await send_question(message)


@dp.message(F.text == "Следующий вопросик")
async def next_question(message: Message):
    st = GAMES.get(message.chat.id)
    if not st or not st.get("active"):
        await message.answer("Игра не запущена. Жми «Начать игру».", reply_markup=kb_main())
        return

    # Каждые 5 вопросов — спросим, продолжать ли (как ты хотел)
    if st["round"] > 0 and st["round"] % 5 == 0:
        await message.answer(
            f"Уже {st['round']} раундов.\n"
            "Продолжим или сделаем паузу?",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Конечно продолжить")],
                    [KeyboardButton(text="Возьмём паузу")],
                ],
                resize_keyboard=True,
            ),
        )
        return

    await send_question(message)


@dp.message(F.text == "Конечно продолжить")
async def continue_game(message: Message):
    st = GAMES.get(message.chat.id)
    if not st or not st.get("active"):
        await message.answer("Игра не запущена. Жми «Начать игру».", reply_markup=kb_main())
        return
    await send_question(message)


@dp.message(F.text == "Возьмём паузу")
async def pause_game(message: Message):
    st = GAMES.get(message.chat.id)
    if st:
        st["active"] = False
    await message.answer(
        "Пауза принята.\n"
        "Как созреете — жмите «Начать игру».",
        reply_markup=kb_main(),
    )


@dp.message(F.text == "Завершить игру")
async def end_game(message: Message):
    if message.chat.id in GAMES:
        GAMES.pop(message.chat.id, None)
    await message.answer(
        "Игра окончена.\n"
        "Надеюсь, никто не обиделся… 🤫",
        reply_markup=kb_main(),
    )


# -----------------------------
# ВАЖНО: в группе бот может не видеть обычные сообщения
# если privacy mode включен у BotFather.
# -----------------------------
@dp.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def group_fallback(message: Message):
    # Чтобы не спамить — молчим.
    # Если хочешь дебаг: раскомментируй строку ниже:
    # await message.answer("Я тут 👀 (вижу сообщения)")
    return


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
