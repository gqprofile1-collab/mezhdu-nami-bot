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
# MVP: вопросы
# -----------------------------
NORMAL_QUESTIONS = [
    "Кто чаще всего делает вид, что всё понял — хотя вообще не понял?",
    "Кто из вас умеет “случайно” добиваться своего лучше всех?",
    "Кто первым сдастся в споре, даже если был прав?",
    "Кто чаще всего говорит одно, а делает другое?",
    "Кто самый обаятельный, когда ему что-то нужно?",
    "Кто в компании чаще всего играет роль “хорошего”?",
    "Кто чаще всего исчезает, когда нужно помогать?",
    "Кто из вас больше всего любит внимание?",
    "Кто самый ревнивый, но прячет это?",
    "Кто умеет подколоть так, что ты ещё и виноватым себя почувствуешь?",
    "Кто самый токсичный, когда устал?",
    "Кто чаще всего “случайно” перебивает других?",
    "Кто самый непредсказуемый после пары бокалов?",
    "Кто может держать лицо, даже когда внутри паника?",
    "Кто чаще всего копит обиды молча?",
    "Кто умеет красиво извиняться, но не менять поведение?",
    "Кто самый мастер отмазок?",
    "Кто чаще всего опаздывает — и не считает это проблемой?",
    "Кто в компании самый “серый кардинал”?",
    "Кто из вас самый драматичный, но делает вид, что нет?",
    "Кто легко заводит знакомых где угодно?",
    "Кто чаще всего выбирает “молчать”, чтобы наказать?",
    "Кто умеет очаровать даже тех, кто его не переносил?",
    "Кто чаще всего говорит: “Мне всё равно”, хотя не всё равно?",
    "Кто скорее уйдёт в игнор, чем будет разговаривать?",
    "Кто самый “контролёр” в отношениях/дружбе?",
    "Кто чаще всего делает комплименты — но с подвохом?",
    "Кто умеет “продавить” решение, не повышая голос?",
    "Кто самый хитрый переговорщик?",
    "Кто чаще всего влюбляется не в тех?",
    "Кто из вас может флиртовать просто ради спорта?",
    "Кто чаще всего “проверяет” людей на прочность?",
    "Кто самый злопамятный, но улыбается?",
    "Кто бы смог простить измену быстрее остальных?",
    "Кто чаще всего уходит от ответа, когда неудобно?",
]

SPICY_QUESTIONS = [
    "Кто из вас мог бы увести чужого партнёра?",
    "Кто чаще всего врёт “по мелочи” — и делает вид, что так и надо?",
    "Кто здесь самый харизматичный манипулятор?",
    "Кто самый опасный в конфликте: тихий, но мстительный?",
    "Кто способен на поступок, который потом будет стыдно вспоминать?",
    "Кто в этой компании самый “опасный” для чужих отношений?",
    "Кто способен флиртовать при партнёре — и считать это нормой?",
    "Кто чаще всего играет в “жертву”, когда сам накосячил?",
    "Кто мог бы утаить правду, чтобы не выглядеть виноватым?",
]

QUESTIONS = NORMAL_QUESTIONS + SPICY_QUESTIONS

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


@dp.message(CommandStart())
async def start_cmd(message: Message):
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


@dp.message(F.text == "Начать игру")
async def start_game(message: Message):
    # НЕ сбрасываем прогресс: если игра уже была — продолжаем
    st = GAMES.setdefault(message.chat.id, {"active": False, "used": set(), "round": 0})
    st["active"] = True

    await message.answer(
        "Продолжаем 🔥\n"
        "Только без обид… это между нами 🤫",
        reply_markup=kb_game(),
    )
    await send_question(message)


@dp.message(F.text == "Следующий вопросик")
async def next_question(message: Message):
    st = GAMES.get(message.chat.id)
    if not st or not st.get("active"):
        await message.answer("Игра на паузе. Жми «Начать игру» чтобы продолжить.", reply_markup=kb_main())
        return

    # Каждые 5 вопросов — спросим, продолжать ли
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
    if not st:
        GAMES[message.chat.id] = {"active": True, "used": set(), "round": 0}
    else:
        st["active"] = True

    await send_question(message)


@dp.message(F.text == "Возьмём паузу")
async def pause_game(message: Message):
    st = GAMES.get(message.chat.id)
    if st:
        st["active"] = False  # прогресс НЕ трогаем
    await message.answer(
        "Пауза принята.\n"
        "Чтобы продолжить с того же места — жми «Начать игру».",
        reply_markup=kb_main(),
    )


@dp.message(F.text == "Завершить игру")
async def end_game(message: Message):
    GAMES.pop(message.chat.id, None)  # тут уже полный сброс
    await message.answer(
        "Игра окончена.\n"
        "Надеюсь, никто не обиделся… 🤫",
        reply_markup=kb_main(),
    )


@dp.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def group_fallback(message: Message):
    return


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
