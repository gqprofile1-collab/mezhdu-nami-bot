import asyncio
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Set, Optional, List, Tuple

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder


# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в переменных окружения (Railway Variables).")

MAX_PLAYERS = 10
MIN_PLAYERS = 2

ROUND_VOTE_SECONDS = 15
EXTEND_SECONDS = 15

# TЗ: 5 минут → закрыть лобби, 10 минут → закрыть сессию
LOBBY_CLOSE_SEC = 5 * 60
SESSION_CLOSE_SEC = 10 * 60

NEXT_COOLDOWN_SEC = 1.0


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
# BOT
# =========================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =========================
# STATE
# =========================
class State(str, Enum):
    IDLE = "IDLE"
    LOBBY = "LOBBY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"


@dataclass
class Player:
    user_id: int
    name: str
    label: str
    score: int = 0


@dataclass
class GameState:
    chat_id: int

    state: State = State.IDLE
    host_user_id: Optional[int] = None

    players: Dict[int, Player] = field(default_factory=dict)
    join_order: List[int] = field(default_factory=list)

    round: int = 0

    used_normal: Set[int] = field(default_factory=set)
    used_spicy: Set[int] = field(default_factory=set)

    # TЗ: острые каждые 3–4; фирменная вставка каждые 4–5
    since_last_spicy: int = 0
    next_spicy_at: int = field(default_factory=lambda: random.randint(3, 4))

    since_last_secret: int = 0
    next_secret_at: int = field(default_factory=lambda: random.randint(4, 5))

    current_question: Optional[str] = None
    current_is_spicy: bool = False
    current_has_secret: bool = False

    round_targets: List[int] = field(default_factory=list)  # snapshot целей на раунд
    round_voters: Set[int] = field(default_factory=set)     # snapshot голосующих на раунд
    votes_by_target: Dict[int, int] = field(default_factory=dict)
    voted_users: Set[int] = field(default_factory=set)
    total_votes: int = 0
    extended_once: bool = False

    last_activity: datetime = field(default_factory=datetime.utcnow)
    watchdog_task: Optional[asyncio.Task] = None
    round_timer_task: Optional[asyncio.Task] = None

    last_next_press_ts: Dict[int, float] = field(default_factory=dict)

    awaiting_next: bool = False
    pause_gate: bool = False  # после каждого 5-го раунда блокируем "Следующий" до "Продолжить/Пауза"


GAMES: Dict[int, GameState] = {}


# =========================
# MARKDOWNV2 HELPERS
# =========================
def md_escape(text: str) -> str:
    # escape for MarkdownV2
    for ch in r"_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


def md_bold(text: str) -> str:
    return f"*{md_escape(text)}*"


def md_italic(text: str) -> str:
    return f"_{md_escape(text)}_"


def md_bold_caps(text: str) -> str:
    return md_bold(text.upper())


# =========================
# HELPERS
# =========================
def touch(gs: GameState):
    gs.last_activity = datetime.utcnow()


def base_name_from_user(u) -> str:
    base = (u.full_name or "").strip()
    if base:
        return base
    if u.username:
        return f"@{u.username}"
    return str(u.id)


def make_unique_label(gs: GameState, u) -> str:
    # Требование: Ilya#2 (без пробела) если одинаковые имена
    base = (u.full_name or "").strip()
    if not base:
        base = f"@{u.username}" if u.username else str(u.id)

    # @username и так уникально
    if base.startswith("@"):
        return base

    existing = {p.label for p in gs.players.values()}
    if base not in existing:
        return base

    i = 2
    while True:
        label = f"{base}#{i}"
        if label not in existing:
            return label
        i += 1


def pick_from_pool(used: Set[int], pool: List[str]) -> str:
    if len(used) >= len(pool):
        used.clear()
    idx = random.randrange(len(pool))
    while idx in used:
        idx = random.randrange(len(pool))
    used.add(idx)
    return pool[idx]


def choose_question(gs: GameState) -> Tuple[str, bool, bool]:
    gs.since_last_spicy += 1
    gs.since_last_secret += 1

    is_spicy = False
    has_secret = False

    if gs.since_last_spicy >= gs.next_spicy_at:
        is_spicy = True
        gs.since_last_spicy = 0
        gs.next_spicy_at = random.randint(3, 4)

    if gs.since_last_secret >= gs.next_secret_at:
        has_secret = True
        gs.since_last_secret = 0
        gs.next_secret_at = random.randint(4, 5)

    q = pick_from_pool(gs.used_spicy, ALL_SPICY) if is_spicy else pick_from_pool(gs.used_normal, ALL_NORMAL)
    return q, is_spicy, has_secret


def format_players(gs: GameState) -> str:
    if not gs.players:
        return "Пока никого."
    lines = []
    for uid in gs.join_order:
        p = gs.players.get(uid)
        if p:
            lines.append(p.label)
    return "• " + "\n• ".join(lines)


def anti_spam_next_ok(gs: GameState, user_id: int) -> bool:
    now = time.time()
    last = gs.last_next_press_ts.get(user_id, 0.0)
    if now - last < NEXT_COOLDOWN_SEC:
        return False
    gs.last_next_press_ts[user_id] = now
    return True


# =========================
# KEYBOARDS
# =========================
def kb_lobby(gs: GameState):
    b = InlineKeyboardBuilder()
    b.button(text="✅ Присоединиться", callback_data="join")
    b.button(text="🔥 Ну что? Погнали?", callback_data="start")  # старт только хост
    b.button(text="❌ Отмена", callback_data="cancel")
    b.adjust(1, 1, 1)
    return b.as_markup()


def kb_vote(gs: GameState):
    # ВАЖНО: во время вопроса НЕ показываем кнопку "добавить"
    b = InlineKeyboardBuilder()

    targets = [(uid, gs.players[uid]) for uid in gs.round_targets if uid in gs.players]
    targets.sort(key=lambda x: x[1].label.lower())

    for uid, p in targets:
        # В кнопках форматирование не работает — оставляем plain text
        b.button(text=p.label, callback_data=f"vote:{uid}")

    cols = 2 if len(targets) <= 6 else 3
    if targets:
        b.adjust(*([cols] * ((len(targets) + cols - 1) // cols)))

    b.row()
    b.button(text="🛑 Завершить", callback_data="end")
    b.adjust(1)
    return b.as_markup()


def kb_result():
    b = InlineKeyboardBuilder()
    b.button(text="👉 Следующий вопросик", callback_data="next")
    b.button(text="🛑 Завершить", callback_data="end")
    b.adjust(1, 1)
    return b.as_markup()


def kb_pause_gate():
    b = InlineKeyboardBuilder()
    b.button(text="😏 Продолжить", callback_data="resume")
    b.button(text="🕒 Возьмём паузу", callback_data="pause")
    b.adjust(1, 1)
    return b.as_markup()


def kb_paused():
    b = InlineKeyboardBuilder()
    b.button(text="😏 Продолжить", callback_data="resume")
    b.button(text="🛑 Завершить", callback_data="end")
    b.adjust(1, 1)
    return b.as_markup()


def kb_no_votes_extend():
    b = InlineKeyboardBuilder()
    b.button(text=f"Дадим ещё шанс (+{EXTEND_SECONDS}с)", callback_data="extend")
    b.button(text="🛑 Завершить", callback_data="end")
    b.adjust(1, 1)
    return b.as_markup()


# =========================
# WATCHDOG (inactivity)
# =========================
async def watchdog(chat_id: int):
    while True:
        await asyncio.sleep(10)
        gs = GAMES.get(chat_id)
        if not gs:
            return

        idle_sec = (datetime.utcnow() - gs.last_activity).total_seconds()

        # 5 минут — закрыть лобби
        if gs.state == State.LOBBY and idle_sec >= LOBBY_CLOSE_SEC:
            gs.state = State.IDLE
            try:
                await bot.send_message(
                    chat_id,
                    "Лобби протухло 🫠\n"
                    "5 минут тишины — закрываю сбор.\n\n"
                    "Если хотите снова — напишите «Начать игру».",
                )
            except Exception:
                pass

        # 10 минут — закрыть сессию
        if gs.state != State.IDLE and idle_sec >= SESSION_CLOSE_SEC:
            GAMES.pop(chat_id, None)
            try:
                await bot.send_message(
                    chat_id,
                    "10 минут тишины 😴\n"
                    "Я закрываю игру.\n\n"
                    "Хотите снова — напишите «Начать игру».",
                )
            except Exception:
                pass
            return


def ensure_watchdog(gs: GameState):
    if gs.watchdog_task and not gs.watchdog_task.done():
        return
    gs.watchdog_task = asyncio.create_task(watchdog(gs.chat_id))


# =========================
# ROUND FLOW
# =========================
async def start_round(chat_id: int):
    gs = GAMES.get(chat_id)
    if not gs:
        return
    if gs.state != State.RUNNING:
        return

    if len(gs.players) < MIN_PLAYERS:
        await bot.send_message(chat_id, "Для игры нужно минимум двое.\nВсе разошлись? Я тоже пойду 😏")
        GAMES.pop(chat_id, None)
        return

    touch(gs)

    gs.awaiting_next = False
    gs.pause_gate = False

    gs.round += 1
    gs.votes_by_target.clear()
    gs.voted_users.clear()
    gs.total_votes = 0
    gs.extended_once = False

    # snapshot voters + targets for this round
    snapshot_ids = [uid for uid in gs.join_order if uid in gs.players]
    gs.round_voters = set(snapshot_ids)
    gs.round_targets = snapshot_ids[:]

    q, is_spicy, has_secret = choose_question(gs)
    gs.current_question = q
    gs.current_is_spicy = is_spicy
    gs.current_has_secret = has_secret

    # формат B:
    # **ВОПРОС КАПС**
    # _Только честно. Это между нами 🤫_
    q_line = md_bold_caps(q)

    secret_line = ""
    if has_secret:
        secret_line = "\n\n" + md_italic("Только честно. Это между нами 🤫")

    spicy_line = ""
    if is_spicy:
        spicy_line = "\n\n" + md_italic("Отвечайте честно. Это между нами 🤫")

    timer_line = "\n\n" + md_italic(f"({ROUND_VOTE_SECONDS} секунд на голосование)")

    text = (
        f"Раунд {gs.round} 😈\n\n"
        f"{q_line}"
        f"{secret_line}"
        f"{spicy_line}"
        f"{timer_line}\n\n"
        f"Голосуйте 👇"
    )

    # cancel previous timer
    if gs.round_timer_task and not gs.round_timer_task.done():
        gs.round_timer_task.cancel()

    await bot.send_message(chat_id, text, reply_markup=kb_vote(gs), parse_mode="MarkdownV2")
    gs.round_timer_task = asyncio.create_task(round_timer(chat_id, ROUND_VOTE_SECONDS))


async def round_timer(chat_id: int, seconds: int):
    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        return

    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.RUNNING:
        return

    if gs.awaiting_next:
        return

    # time up: if no votes and not extended yet -> offer extend
    if gs.total_votes == 0 and not gs.extended_once:
        gs.extended_once = True
        touch(gs)
        await bot.send_message(
            chat_id,
            "Тишина…\nДадим ещё шанс? 😏",
            reply_markup=kb_no_votes_extend(),
        )
        return

    await show_round_result(chat_id)


def reaction_for_result(votes_sorted: List[Tuple[int, int]], total_votes: int) -> str:
    if total_votes == 0:
        return "Никто не рискнул. Слишком мило 🤨"

    top_count = votes_sorted[0][1] if votes_sorted else 0
    second_count = votes_sorted[1][1] if len(votes_sorted) > 1 else 0

    top_all = [uid for uid, c in votes_sorted if c == top_count]
    if len(top_all) > 1:
        return random.choice([
            "Мнения разделились. У вас тут своя дипломатия 😏",
            "Поровну. Никто не захотел быть крайним 🤫",
            "Ничья. Санта-Барбара продолжается 😈",
        ])

    # unanimous = все голоса ушли одному
    if top_count == total_votes and total_votes >= 2:
        return random.choice([
            "Единогласно. Тут даже обсуждать нечего 😈",
            "Ну всё, спалили. Весь чат согласен 🤭",
            "Ого. Хором. Больно, наверное 🤫",
        ])

    # minimal margin
    if top_count - second_count == 1:
        return random.choice([
            "На тоненького. Едва-едва 😏",
            "Разрыв минимальный. Почти ничья 🤫",
            "Ух. С минимальным отрывом 😈",
        ])

    # strong lead
    if top_count >= second_count + 3:
        return random.choice([
            "Похоже, всё очевидно 😈",
            "Сильный перевес. Вы прям уверены 😏",
            "Ну да… вопросов не осталось 🤫",
        ])

    return random.choice([
        "Интересно… 😏",
        "Запомним. 🤫",
        "Окей. Занёс в протокол 😈",
    ])


async def show_round_result(chat_id: int):
    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.RUNNING:
        return
    if gs.awaiting_next:
        return

    touch(gs)
    gs.awaiting_next = True

    if gs.total_votes == 0:
        text = (
            f"Итог раунда {gs.round}:\n"
            "Никого не выбрали.\n"
            "Слишком мирно… подозрительно 🤨"
        )
        await bot.send_message(chat_id, text, reply_markup=kb_result())
    else:
        items = sorted(gs.votes_by_target.items(), key=lambda x: x[1], reverse=True)

        # блок результатов с MarkdownV2: имена жирные
        lines: List[str] = [f"Итог раунда {gs.round}:"]
        for uid, c in items:
            p = gs.players.get(uid)
            if p and c > 0:
                lines.append(f"{md_bold(p.label)} — {c}")

        top_uid, top_count = items[0]
        top_all = [uid for uid, c in items if c == top_count]

        lines.append("")

        if len(top_all) == 1:
            p = gs.players.get(top_uid)
            if p:
                lines.append(f"Большинство: {md_bold(p.label)}")
                lines.append(random.choice([
                    f"{md_escape(p.label)}, есть комментарий? 🙂",
                    f"{md_escape(p.label)}, ну что, узнаёшь себя? 😏",
                    f"{md_escape(p.label)}, держись\\. Это только начало 😈",
                    f"{md_escape(p.label)}, ты сегодня в центре внимания 🤫",
                ]))
        else:
            names = ", ".join([gs.players[uid].label for uid in top_all if uid in gs.players])
            lines.append(f"Ничья: {md_bold(names)}")

        reaction = reaction_for_result(items, gs.total_votes)
        lines.append(md_escape(reaction))

        await bot.send_message(chat_id, "\n".join(lines), reply_markup=kb_result(), parse_mode="MarkdownV2")

    # pause every 5 rounds (TЗ)
    if gs.round % 5 == 0:
        gs.pause_gate = True
        await bot.send_message(
            chat_id,
            "Уже 5 раундов.\n"
            "Пока никто не поссорился… надеюсь.\n"
            "Идём дальше? 😏",
            reply_markup=kb_pause_gate(),
        )


# =========================
# FINAL (Top-3 total)
# =========================
def final_top3_text(gs: GameState) -> str:
    played = gs.round
    if not gs.players:
        return "Игра окончена. Но вы даже не собрались 🤷‍♂️"

    ranking = sorted(gs.players.values(), key=lambda p: p.score, reverse=True)

    if not ranking or ranking[0].score == 0:
        return (
            "Игра окончена 🛑\n\n"
            f"Сыграли: {played} раундов\n"
            "И… вы почти никого не выбирали.\n"
            "Подозрительно мирная компания 🤨\n\n"
            "Если было интересно — добавь меня в другой чат 😉\n"
            "Это между нами 🤫"
        )

    top3 = ranking[:3]
    medals = ["🥇", "🥈", "🥉"]

    lines = [
        "Игра окончена 🛑",
        "",
        f"Сыграли: {played} раундов",
        "Чаще всего выбирали (ТОП-3):",
    ]
    for i, p in enumerate(top3):
        lines.append(f"{medals[i]} {p.label} — {p.score}")

    lines += [
        "",
        "Интересная компания. Очень 😈",
        "",
        "Если зашло — поддержи ❤️",
        "Это между нами 🤫",
        "Если было интересно — добавь меня в другой чат 😉",
    ]
    return "\n".join(lines)


async def end_game(chat_id: int, reason: str = ""):
    gs = GAMES.get(chat_id)
    if not gs:
        return
    text = final_top3_text(gs)
    if reason:
        text = reason + "\n\n" + text
    # стоп таймеров
    if gs.round_timer_task and not gs.round_timer_task.done():
        gs.round_timer_task.cancel()
    if gs.watchdog_task and not gs.watchdog_task.done():
        gs.watchdog_task.cancel()

    GAMES.pop(chat_id, None)
    await bot.send_message(chat_id, text)


# =========================
# COMMANDS
# =========================
@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Между нами 🤫\n\n"
        "Добавь меня в чат — и напиши:\n"
        "«Начать игру»\n\n"
        "/help — правила"
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Как играем:\n"
        "1) Напишите: Начать игру\n"
        "2) Все жмут: Присоединиться\n"
        "3) Создатель жмёт: Ну что? Погнали?\n"
        "4) Вопрос → голосование (15 сек) → результат → следующий\n"
        "5) Каждые 5 раундов — пауза\n\n"
        "Лобби закрывается через 5 минут тишины.\n"
        "Сессия закрывается через 10 минут тишины.\n"
        "Это между нами 🤫"
    )


# =========================
# START LOBBY (text trigger)
# =========================
@dp.message(F.text.casefold() == "начать игру")
async def start_lobby(message: Message):
    chat_id = message.chat.id
    gs = GAMES.get(chat_id)

    # запрет второй игры пока одна активна
    if gs and gs.state in {State.LOBBY, State.RUNNING, State.PAUSED}:
        await message.answer("Игра уже идёт 😏\nЖмите кнопки под сообщениями.")
        return

    gs = GameState(chat_id=chat_id)
    gs.state = State.LOBBY
    gs.host_user_id = message.from_user.id
    touch(gs)
    ensure_watchdog(gs)
    GAMES[chat_id] = gs

    await message.answer(
        "Между нами 🤫\n\n"
        "Игра создаётся.\n"
        "Нажмите «Присоединиться».\n\n"
        "В игре:\n"
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
    if gs:
        if gs.round_timer_task and not gs.round_timer_task.done():
            gs.round_timer_task.cancel()
        if gs.watchdog_task and not gs.watchdog_task.done():
            gs.watchdog_task.cancel()
    GAMES.pop(chat_id, None)

    await cb.answer("Ок")
    try:
        await cb.message.edit_text("Ок, отменил. Это между нами 🤫")
    except Exception:
        await cb.message.answer("Ок, отменил. Это между нами 🤫")


@dp.callback_query(F.data == "join")
async def cb_join(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.LOBBY:
        await cb.answer("Лобби закрыто. Напиши «Начать игру».", show_alert=True)
        return

    touch(gs)
    ensure_watchdog(gs)

    uid = cb.from_user.id
    if uid in gs.players:
        await cb.answer("Ты уже в игре 😏", show_alert=False)
        return

    if len(gs.players) >= MAX_PLAYERS:
        await cb.answer("Уже 10 игроков. Просто наблюдай 😈", show_alert=True)
        return

    u = cb.from_user
    name = base_name_from_user(u)
    label = make_unique_label(gs, u)

    gs.players[uid] = Player(user_id=uid, name=name, label=label)
    gs.join_order.append(uid)

    # если создатель вышел — право старта у первого присоединившегося
    if gs.host_user_id and gs.host_user_id not in gs.players:
        gs.host_user_id = gs.join_order[0] if gs.join_order else uid

    await cb.answer("Записал ✅", show_alert=False)

    try:
        await cb.message.edit_text(
            "Между нами 🤫\n\n"
            "Игра создаётся.\n"
            "Нажмите «Присоединиться».\n\n"
            "В игре:\n"
            f"{format_players(gs)}",
            reply_markup=kb_lobby(gs),
        )
    except Exception:
        await cb.message.answer(
            "В игре:\n"
            f"{format_players(gs)}",
            reply_markup=kb_lobby(gs),
        )


@dp.callback_query(F.data == "start")
async def cb_start(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.LOBBY:
        await cb.answer("Лобби закрыто. Напиши «Начать игру».", show_alert=True)
        return

    touch(gs)
    ensure_watchdog(gs)

    # старт только хост
    host = gs.host_user_id
    if host is not None:
        if host not in gs.players and gs.join_order:
            gs.host_user_id = gs.join_order[0]
            host = gs.host_user_id

    if host is not None and cb.from_user.id != host:
        await cb.answer("Стартует только создатель 😏", show_alert=True)
        return

    if len(gs.players) < MIN_PLAYERS:
        await cb.answer("Нужно минимум 2 игрока.", show_alert=True)
        return

    gs.state = State.RUNNING
    touch(gs)

    try:
        await cb.message.edit_text("Ну что? Погнали? 🔥\nТолько без обид… это между нами 🤫")
    except Exception:
        await cb.message.answer("Ну что? Погнали? 🔥\nТолько без обид… это между нами 🤫")

    await cb.answer("Поехали")
    await start_round(chat_id)


@dp.callback_query(F.data.startswith("vote:"))
async def cb_vote(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.RUNNING:
        await cb.answer("Игра не запущена.", show_alert=False)
        return

    touch(gs)

    voter_id = cb.from_user.id
    if voter_id not in gs.round_voters:
        await cb.answer("Ты не в этом раунде 😏", show_alert=True)
        return

    if voter_id in gs.voted_users:
        await cb.answer("Ты уже проголосовал(а) 😏", show_alert=False)
        return

    try:
        target_id = int(cb.data.split(":", 1)[1])
    except Exception:
        await cb.answer("Кривой голос 🤨", show_alert=False)
        return

    if target_id not in gs.round_targets:
        await cb.answer("Этого игрока нет в текущем раунде.", show_alert=False)
        return

    if target_id == voter_id:
        await cb.answer("За себя нельзя 😈", show_alert=True)
        return

    gs.voted_users.add(voter_id)
    gs.votes_by_target[target_id] = gs.votes_by_target.get(target_id, 0) + 1
    gs.total_votes += 1

    target_label = gs.players.get(target_id).label if target_id in gs.players else "кто-то"
    await cb.answer(f"Засчитано ✅ ({target_label})", show_alert=False)

    # все проголосовали — результат сразу
    if len(gs.voted_users) >= len(gs.round_voters):
        if gs.round_timer_task and not gs.round_timer_task.done():
            gs.round_timer_task.cancel()
        await show_round_result(chat_id)


@dp.callback_query(F.data == "extend")
async def cb_extend(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.RUNNING:
        await cb.answer("Неактуально.", show_alert=False)
        return

    touch(gs)
    await cb.answer("Ок, ещё шанс 😏", show_alert=False)

    if gs.awaiting_next:
        return

    # перезапуск таймера на EXTEND_SECONDS
    if gs.round_timer_task and not gs.round_timer_task.done():
        gs.round_timer_task.cancel()
    gs.round_timer_task = asyncio.create_task(round_timer(chat_id, EXTEND_SECONDS))

    try:
        await cb.message.edit_text(f"Ладно.\nЕщё {EXTEND_SECONDS} секунд. Только без стеснения 😈")
    except Exception:
        await cb.message.answer(f"Ладно.\nЕщё {EXTEND_SECONDS} секунд. Только без стеснения 😈")


@dp.callback_query(F.data == "next")
async def cb_next(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.RUNNING:
        await cb.answer("Игра не запущена.", show_alert=False)
        return

    if not anti_spam_next_ok(gs, cb.from_user.id):
        await cb.answer("Тише-тише 😏", show_alert=False)
        return

    touch(gs)

    # нельзя дальше до результата
    if not gs.awaiting_next:
        await cb.answer("Сначала голосование/результат 😈", show_alert=False)
        return

    # после 5 раундов — только через кнопки паузы
    if gs.pause_gate:
        await cb.answer("После 5 раундов — выбери: продолжить или пауза 😏", show_alert=False)
        return

    await cb.answer("Дальше", show_alert=False)
    await start_round(chat_id)


@dp.callback_query(F.data == "pause")
async def cb_pause(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs:
        await cb.answer("Не найдено.", show_alert=False)
        return

    touch(gs)

    gs.state = State.PAUSED
    if gs.round_timer_task and not gs.round_timer_task.done():
        gs.round_timer_task.cancel()

    await cb.answer("Пауза", show_alert=False)
    try:
        await cb.message.edit_text(
            "Пауза 🕒\n\n"
            "Вернуться можно в течение 10 минут.\n"
            "Это между нами 🤫",
            reply_markup=kb_paused(),
        )
    except Exception:
        await cb.message.answer(
            "Пауза 🕒\n\n"
            "Вернуться можно в течение 10 минут.\n"
            "Это между нами 🤫",
            reply_markup=kb_paused(),
        )


@dp.callback_query(F.data == "resume")
async def cb_resume(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs:
        await cb.answer("Неактуально.", show_alert=False)
        return

    touch(gs)

    gs.state = State.RUNNING
    gs.pause_gate = False  # снимаем блок после 5-го

    await cb.answer("Поехали 😏", show_alert=False)
    try:
        await cb.message.edit_text("Продолжаем 😈\nЭто между нами 🤫")
    except Exception:
        await cb.message.answer("Продолжаем 😈\nЭто между нами 🤫")

    await start_round(chat_id)


@dp.callback_query(F.data == "end")
async def cb_end(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    await cb.answer("Ок", show_alert=False)
    await end_game(chat_id)


# =========================
# MAIN
# =========================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
