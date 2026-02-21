import asyncio
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Set, Optional, Tuple, List

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в переменных окружения (Railway Variables).")

LOBBY_TIMEOUT_SEC = 10 * 60
PAUSE_TIMEOUT_SEC = 10 * 60
SPAM_COOLDOWN_SEC = 1.0  # анти-спам по кнопкам "дальше"

# =========================
# QUESTIONS (44 total)
# =========================
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

ALL_NORMAL = NORMAL_QUESTIONS[:]
ALL_SPICY = SPICY_QUESTIONS[:]

# =========================
# STATE
# =========================
@dataclass
class Player:
    user_id: int
    name: str
    score: int = 0


@dataclass
class GameState:
    chat_id: int
    lobby_open: bool = False
    active: bool = False
    paused: bool = False

    players: Dict[int, Player] = field(default_factory=dict)

    round: int = 0
    used_normal: Set[int] = field(default_factory=set)
    used_spicy: Set[int] = field(default_factory=set)

    current_question: Optional[str] = None
    current_is_spicy: bool = False
    voters_this_round: Set[int] = field(default_factory=set)

    last_activity: datetime = field(default_factory=datetime.utcnow)
    lobby_task: Optional[asyncio.Task] = None
    pause_task: Optional[asyncio.Task] = None

    last_button_press_ts: Dict[int, float] = field(default_factory=dict)


GAMES: Dict[int, GameState] = {}

# =========================
# BOT SETUP
# =========================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# =========================
# HELPERS
# =========================
def touch(gs: GameState):
    gs.last_activity = datetime.utcnow()


def get_display_name(message_or_cb) -> str:
    u = message_or_cb.from_user
    if u.full_name and u.full_name.strip():
        return u.full_name.strip()
    if u.username:
        return f"@{u.username}"
    return str(u.id)


def kb_lobby(gs: GameState):
    b = InlineKeyboardBuilder()
    b.button(text="✅ Я в игре", callback_data="join")
    b.button(text="🚀 Стартуем", callback_data="start")
    b.button(text="❌ Отмена", callback_data="cancel")
    b.adjust(1, 1, 1)
    return b.as_markup()


def kb_pause_choice():
    b = InlineKeyboardBuilder()
    b.button(text="🔥 Конечно продолжить", callback_data="cont")
    b.button(text="🕒 Возьмём паузу", callback_data="pause")
    b.adjust(1, 1)
    return b.as_markup()


def kb_in_game(gs: GameState, include_votes: bool = True):
    b = InlineKeyboardBuilder()

    if include_votes and gs.players:
        for uid, p in sorted(gs.players.items(), key=lambda kv: kv[1].name.lower()):
            b.button(text=p.name, callback_data=f"vote:{uid}")
        cols = 2 if len(gs.players) <= 6 else 3
        b.adjust(*([cols] * ((len(gs.players) + cols - 1) // cols)))

    b.row()
    b.button(text="👉 Следующий вопросик", callback_data="next")
    b.button(text="⏸ Пауза", callback_data="pause")
    b.button(text="🛑 Завершить", callback_data="end")
    b.adjust(3)
    return b.as_markup()


def kb_resume():
    b = InlineKeyboardBuilder()
    b.button(text="▶️ Продолжить", callback_data="resume")
    b.button(text="🛑 Завершить", callback_data="end")
    b.adjust(1, 1)
    return b.as_markup()


def format_players(gs: GameState) -> str:
    if not gs.players:
        return "Пока никого."
    names = [p.name for p in gs.players.values()]
    return "• " + "\n• ".join(names)


def pick_from_pool(used: Set[int], pool: List[str]) -> Tuple[int, str]:
    if len(used) >= len(pool):
        used.clear()
    idx = random.randrange(len(pool))
    while idx in used:
        idx = random.randrange(len(pool))
    used.add(idx)
    return idx, pool[idx]


def should_spicy(round_num: int) -> bool:
    if round_num % 5 == 0:
        return True
    if round_num % 5 == 4 and random.random() < 0.5:
        return True
    return False


def anti_spam_ok(gs: GameState, user_id: int) -> bool:
    now = time.time()
    last = gs.last_button_press_ts.get(user_id, 0.0)
    if now - last < SPAM_COOLDOWN_SEC:
        return False
    gs.last_button_press_ts[user_id] = now
    return True


async def lobby_timeout(chat_id: int):
    await asyncio.sleep(LOBBY_TIMEOUT_SEC)
    gs = GAMES.get(chat_id)
    if not gs:
        return
    if gs.lobby_open and not gs.active and (datetime.utcnow() - gs.last_activity).total_seconds() >= LOBBY_TIMEOUT_SEC:
        gs.lobby_open = False
        try:
            await bot.send_message(
                chat_id,
                "Лобби протухло 🫠\n"
                "10 минут тишины — я всё закрыл.\n\n"
                "Если хотите заново: напишите «Начать игру».",
            )
        except Exception:
            pass


async def pause_timeout(chat_id: int):
    await asyncio.sleep(PAUSE_TIMEOUT_SEC)
    gs = GAMES.get(chat_id)
    if not gs:
        return
    if gs.paused and (datetime.utcnow() - gs.last_activity).total_seconds() >= PAUSE_TIMEOUT_SEC:
        GAMES.pop(chat_id, None)
        try:
            await bot.send_message(
                chat_id,
                "Пауза затянулась 😴\n"
                "10 минут тишины — игра закрыта.\n\n"
                "Хотите снова — напишите «Начать игру».",
            )
        except Exception:
            pass


async def send_question(chat_id: int):
    gs = GAMES[chat_id]
    gs.round += 1
    gs.voters_this_round.clear()

    is_spicy = should_spicy(gs.round)
    gs.current_is_spicy = is_spicy

    if is_spicy:
        _, q = pick_from_pool(gs.used_spicy, ALL_SPICY)
    else:
        _, q = pick_from_pool(gs.used_normal, ALL_NORMAL)

    gs.current_question = q

    spicy_tail = "\n\nОтвечайте честно.\nЭто между нами 🤫" if is_spicy else ""
    text = f"Раунд {gs.round} 😈\n\n{q}{spicy_tail}\n\nГолосуйте кнопками ниже 👇"

    await bot.send_message(
        chat_id,
        text,
        reply_markup=kb_in_game(gs, include_votes=True),
    )


def final_stats(gs: GameState) -> str:
    if not gs.players:
        return "Игра окончена. Но вы даже не собрались 🤷‍♂️"

    ranking = sorted(gs.players.values(), key=lambda p: p.score, reverse=True)

    if ranking[0].score == 0:
        return (
            "Игра окончена 🛑\n\n"
            "Вы вообще никого не выбирали…\n"
            "Подозрительно мирная компания 🤨\n\n"
            "Между нами 🤫"
        )

    top3 = ranking[:3]
    medals = ["🥇", "🥈", "🥉"]

    lines = [
        "Игра окончена 🛑\n",
        "🔥 ТОП-3 самых обсуждаемых сегодня:\n",
    ]

    for i, player in enumerate(top3):
        lines.append(f"{medals[i]} {player.name} — {player.score} голос(ов)")

    lines.append("\nВот такие у вас приоритеты 😈")
    lines.append("Это между нами 🤫")
    return "\n".join(lines)

# =========================
# COMMANDS
# =========================
@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Между нами 🤫\n\n"
        "Игра для компаний (2–10 человек).\n"
        "Напишите **«Начать игру»** в чате и собирайтесь.\n\n"
        "Команды:\n"
        "/help — правила\n",
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Как играем:\n"
        "1) Напишите: **Начать игру**\n"
        "2) Все жмут: **Я в игре**\n"
        "3) Жмёте: **Стартуем**\n"
        "4) Читаем вопрос, голосуем по именам\n"
        "5) Каждые 5 вопросов — пауза/продолжить\n\n"
        "Лобби/пауза закрываются через 10 минут тишины.\n"
        "Это между нами 🤫",
    )

# =========================
# TEXT TRIGGER (for groups)
# =========================
@dp.message(F.text.casefold() == "начать игру")
async def text_start_game(message: Message):
    chat_id = message.chat.id
    gs = GAMES.get(chat_id)
    if not gs:
        gs = GameState(chat_id=chat_id)
        GAMES[chat_id] = gs

    touch(gs)

    if gs.paused and not gs.active:
        await message.answer(
            "Игра на паузе.\nПродолжим с того же места?",
            reply_markup=kb_resume(),
        )
        return

    if gs.active:
        await message.answer("Мы уже в игре 😏\nЖмите голосование/«Следующий вопросик».")
        return

    gs.lobby_open = True
    gs.active = False
    gs.paused = False
    touch(gs)

    if gs.lobby_task and not gs.lobby_task.done():
        gs.lobby_task.cancel()
    gs.lobby_task = asyncio.create_task(lobby_timeout(chat_id))

    await message.answer(
        "Собираемся 😈\n"
        "Кто играет — жмите **«Я в игре»**.\n"
        "Нужно минимум **2** человека.\n\n"
        "Игроки сейчас:\n"
        f"{format_players(gs)}",
        reply_markup=kb_lobby(gs),
    )

# =========================
# CALLBACKS
# =========================
@dp.callback_query(F.data == "cancel")
async def cb_cancel(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs:
        await cb.answer("Уже нечего отменять 🤷‍♂️", show_alert=False)
        return

    GAMES.pop(chat_id, None)
    await cb.message.edit_text("Ок, отменил. Это между нами 🤫")
    await cb.answer("Отменено")


@dp.callback_query(F.data == "join")
async def cb_join(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs or not gs.lobby_open:
        await cb.answer("Лобби закрыто. Напиши «Начать игру».", show_alert=True)
        return

    uid = cb.from_user.id
    name = get_display_name(cb)

    touch(gs)

    if uid in gs.players:
        await cb.answer("Ты уже в игре 😏", show_alert=False)
    else:
        if len(gs.players) >= 10:
            await cb.answer("Лимит 10 игроков. Кто-то лишний 😈", show_alert=True)
            return
        gs.players[uid] = Player(user_id=uid, name=name)
        await cb.answer("Записал тебя ✅", show_alert=False)

    await cb.message.edit_text(
        "Собираемся 😈\n"
        "Кто играет — жмите **«Я в игре»**.\n"
        "Нужно минимум **2** человека.\n\n"
        "Игроки сейчас:\n"
        f"{format_players(gs)}",
        reply_markup=kb_lobby(gs),
    )


@dp.callback_query(F.data == "start")
async def cb_start(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs or not gs.lobby_open:
        await cb.answer("Лобби закрыто. Напиши «Начать игру».", show_alert=True)
        return

    touch(gs)

    if len(gs.players) < 2:
        await cb.answer("Нужно минимум 2 игрока.", show_alert=True)
        return

    gs.lobby_open = False
    gs.active = True
    gs.paused = False

    await cb.message.edit_text("Погнали 🔥\nТолько без обид… это между нами 🤫")
    await cb.answer("Старт!")
    await send_question(chat_id)


@dp.callback_query(F.data == "resume")
async def cb_resume(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs or not gs.paused:
        await cb.answer("Тут нечего продолжать 🤨", show_alert=False)
        return

    touch(gs)
    gs.paused = False
    gs.active = True

    await cb.message.edit_text("Продолжаем 🔥\nЭто между нами 🤫")
    await cb.answer("Поехали")
    await send_question(chat_id)


@dp.callback_query(F.data == "pause")
async def cb_pause(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs:
        await cb.answer("Игра не найдена 🤷‍♂️", show_alert=False)
        return

    touch(gs)
    gs.active = False
    gs.paused = True
    gs.lobby_open = False

    if gs.pause_task and not gs.pause_task.done():
        gs.pause_task.cancel()
    gs.pause_task = asyncio.create_task(pause_timeout(chat_id))

    await cb.message.edit_text(
        "Пауза принята 🕒\n\n"
        "Вернуться можно в течение **10 минут**.\n"
        "Это между нами 🤫",
        reply_markup=kb_resume(),
    )
    await cb.answer("Пауза")


@dp.callback_query(F.data == "cont")
async def cb_continue_after_5(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs:
        await cb.answer("Игра не найдена 🤷‍♂️", show_alert=False)
        return

    touch(gs)
    gs.active = True
    gs.paused = False
    await cb.answer("Продолжаем")
    await cb.message.edit_text("Ладно. Продолжаем 😈")
    await send_question(chat_id)


@dp.callback_query(F.data == "next")
async def cb_next(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs or not gs.active:
        await cb.answer("Игра на паузе/не запущена. Напиши «Начать игру».", show_alert=True)
        return

    if not anti_spam_ok(gs, cb.from_user.id):
        await cb.answer("Тише-тише 😏", show_alert=False)
        return

    touch(gs)

    if gs.round > 0 and gs.round % 5 == 0:
        await cb.message.answer(
            f"Уже **{gs.round}** раундов.\nПродолжим или сделаем паузу?",
            reply_markup=kb_pause_choice(),
        )
        await cb.answer("Выбор")
        return

    await cb.answer("Дальше")
    await send_question(chat_id)


@dp.callback_query(F.data == "end")
async def cb_end(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)

    if not gs:
        await cb.answer("Уже всё.", show_alert=False)
        return

    text = final_stats(gs)
    GAMES.pop(chat_id, None)

    try:
        await cb.message.edit_text(text)
    except Exception:
        await cb.message.answer(text)

    await cb.answer("Конец")


@dp.callback_query(F.data.startswith("vote:"))
async def cb_vote(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs or not gs.active:
        await cb.answer("Игра не запущена/на паузе 🤷‍♂️", show_alert=False)
        return

    touch(gs)

    voter_id = cb.from_user.id
    if voter_id not in gs.players:
        await cb.answer("Ты не в игре. В лобби надо было жать «Я в игре».", show_alert=True)
        return

    if voter_id in gs.voters_this_round:
        await cb.answer("Ты уже проголосовал(а) в этом раунде 😏", show_alert=False)
        return

    try:
        target_id = int(cb.data.split(":", 1)[1])
    except Exception:
        await cb.answer("Кривой голос 🤨", show_alert=False)
        return

    if target_id not in gs.players:
        await cb.answer("Игрока уже нет.", show_alert=False)
        return

    if target_id == voter_id:
        await cb.answer("За себя нельзя 😈", show_alert=True)
        return

    gs.players[target_id].score += 1
    gs.voters_this_round.add(voter_id)

    target_name = gs.players[target_id].name
    await cb.answer(f"Засчитано ✅ ({target_name})", show_alert=False)

    if len(gs.voters_this_round) >= len(gs.players):
        await cb.message.answer("Все проголосовали. Жмите «Следующий вопросик» 👉")

# =========================
# MAIN
# =========================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
