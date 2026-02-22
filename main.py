import asyncio
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Set, Optional, List, Tuple
import json
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, ChatMemberUpdated
from aiogram.utils.keyboard import InlineKeyboardBuilder


# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в переменных окружения (Railway Variables).")

# username подтянем автоматически при старте
BOT_USERNAME: str = ""

MAX_PLAYERS = 10
MIN_PLAYERS = 2

ROUND_VOTE_SECONDS = 15
EXTEND_SECONDS = 15

LOBBY_CLOSE_SEC = 5 * 60
SESSION_CLOSE_SEC = 10 * 60

NEXT_COOLDOWN_SEC = 1.0

# =========================
# REMINDERS + META STORE
# =========================
CHATS_STORE_PATH = "chats.json"
REMIND_EVERY_SEC = 3 * 24 * 60 * 60
REMIND_CHECK_SEC = 60 * 60


# =========================
# QUESTIONS
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

    since_last_spicy: int = 0
    next_spicy_at: int = field(default_factory=lambda: random.randint(3, 4))

    since_last_secret: int = 0
    next_secret_at: int = field(default_factory=lambda: random.randint(4, 5))

    current_question: Optional[str] = None
    current_is_spicy: bool = False
    current_has_secret: bool = False

    round_targets: List[int] = field(default_factory=list)
    round_voters: Set[int] = field(default_factory=set)

    votes_by_target: Dict[int, int] = field(default_factory=dict)
    voted_users: Set[int] = field(default_factory=set)
    total_votes: int = 0

    extended_once: bool = False
    extend_used: bool = False
    awaiting_next: bool = False
    pause_gate: bool = False

    extend_prompt_msg_id: Optional[int] = None

    last_activity: datetime = field(default_factory=datetime.utcnow)
    watchdog_task: Optional[asyncio.Task] = None
    round_timer_task: Optional[asyncio.Task] = None

    last_next_press_ts: Dict[int, float] = field(default_factory=dict)


GAMES: Dict[int, GameState] = {}


# =========================
# STORE helpers (chats.json)
# =========================
def _load_chats_store() -> Dict[str, Dict]:
    p = Path(CHATS_STORE_PATH)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_chats_store(data: Dict[str, Dict]) -> None:
    p = Path(CHATS_STORE_PATH)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def mark_chat_started(chat_id: int) -> None:
    data = _load_chats_store()
    key = str(chat_id)
    now = int(time.time())
    meta = data.get(key, {})
    meta["last_started_ts"] = now
    meta.setdefault("last_reminded_ts", 0)
    data[key] = meta
    _save_chats_store(data)


def mark_group_welcome_sent(chat_id: int) -> None:
    data = _load_chats_store()
    key = str(chat_id)
    now = int(time.time())
    meta = data.get(key, {})
    meta["welcome_sent_ts"] = now
    data[key] = meta
    _save_chats_store(data)


def was_group_welcome_sent(chat_id: int) -> bool:
    data = _load_chats_store()
    meta = data.get(str(chat_id), {})
    return int(meta.get("welcome_sent_ts", 0)) > 0


# =========================
# TEXTS
# =========================
def dm_welcome_text() -> str:
    return (
        "Привет 😏\n\n"
        "Я — *«Между нами 🤫»*.\n"
        "Игра для компаний: вопрос → голосование → итог → следующий.\n\n"
        "Как запустить:\n"
        "1) Добавь меня в группу\n"
        "2) В группе напиши: *Начать игру* 😈\n\n"
        "/help — правила\n"
        "Я не осуждаю.\n"
        "Я запоминаю 😈"
    )


def group_welcome_text() -> str:
    return (
        "Я тут 😏\n"
        "Это *«Между нами 🤫»*.\n\n"
        "Чтобы начать — напишите:\n"
        "*Начать игру* 😈\n\n"
        "/help — правила"
    )


def already_voted_phrase() -> str:
    return random.choice([
        "Ты уже сделал выбор 😏",
        "Один раз и всё 🤫",
        "Поздно менять сторону 😈",
        "Решил — живи с этим.",
        "Без переигровок 😏",
    ])


def time_up_phrase(missing: int, no_votes: bool) -> str:
    if no_votes:
        return random.choice([
            "Время вышло ⏰\nИ… никто не рискнул 😏",
            "Ноль голосов.\nБоимся? 😈",
            "Тишина.\nПодозрительно 🤫",
        ])
    return random.choice([
        f"Время вышло ⏰\nЕщё {missing} человек молчат…",
        f"{missing} всё ещё думают 😏",
        f"Ещё {missing} и можно делать выводы 😈",
    ])


def next_ack_phrase() -> str:
    return random.choice([
        "Продолжаем 😈",
        "Поехали дальше 😏",
        "Ещё раунд? Люблю это 😈",
    ])


def end_phrase_inactive() -> str:
    return random.choice([
        "10 минут тишины… я понял 🫠\nЗакрываю игру.\nВернётесь — продолжим 😈",
        "Чат ушёл в спячку 😴\nЗакрываю игру. Но я рядом 😏",
    ])


def cancel_phrase() -> str:
    return random.choice([
        "Ок. Отменяем 😏\nИнтрига остаётся.",
        "Передумали? Интересно 🤫",
        "Ладно.\nВ этот раз без разоблачений 😈",
    ])


# =========================
# KEYBOARDS
# =========================
def kb_add_to_group():
    b = InlineKeyboardBuilder()
    # кнопка появится, как только мы узнаем BOT_USERNAME (через get_me)
    if BOT_USERNAME:
        b.button(text="➕ Добавить в группу", url=f"https://t.me/{BOT_USERNAME}?startgroup=1")
    b.button(text="📌 Как играть", callback_data="howto_dm")
    b.adjust(1)
    return b.as_markup()


def kb_lobby(gs: GameState):
    b = InlineKeyboardBuilder()
    b.button(text="✅ Присоединиться", callback_data="join")
    b.button(text="🔥 Ну что? Погнали?", callback_data="start")
    b.button(text="❌ Отмена", callback_data="cancel")
    b.adjust(1, 1, 1)
    return b.as_markup()


def kb_vote(gs: GameState):
    b = InlineKeyboardBuilder()
    targets = [(uid, gs.players[uid]) for uid in gs.round_targets if uid in gs.players]
    targets.sort(key=lambda x: x[1].label.lower())
    for uid, p in targets:
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


def kb_not_all_voted():
    b = InlineKeyboardBuilder()
    b.button(text=f"⏳ +{EXTEND_SECONDS} секунд", callback_data="extend")
    b.button(text="😈 Не ждём опоздавших", callback_data="force_result")
    b.button(text="🛑 Завершить", callback_data="end")
    b.adjust(1, 1, 1)
    return b.as_markup()


# =========================
# HELPERS
# =========================
def touch(gs: GameState):
    gs.last_activity = datetime.utcnow()
    mark_chat_started(gs.chat_id)


def anti_spam_next_ok(gs: GameState, user_id: int) -> bool:
    now = time.time()
    last = gs.last_next_press_ts.get(user_id, 0.0)
    if now - last < NEXT_COOLDOWN_SEC:
        return False
    gs.last_next_press_ts[user_id] = now
    return True


def base_name_from_user(u) -> str:
    base = (u.full_name or "").strip()
    if base:
        return base
    if u.username:
        return f"@{u.username}"
    return str(u.id)


def make_unique_label(gs: GameState, u) -> str:
    base = (u.full_name or "").strip()
    if not base:
        base = f"@{u.username}" if u.username else str(u.id)
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
    return "• " + "\n• ".join([gs.players[uid].label for uid in gs.join_order if uid in gs.players])


def get_host(gs: GameState) -> Optional[int]:
    host = gs.host_user_id
    if host is not None and host not in gs.players and gs.join_order:
        host = gs.join_order[0]
        gs.host_user_id = host
    return host


# =========================
# REMINDERS loop
# =========================
async def reminder_loop():
    while True:
        try:
            await asyncio.sleep(REMIND_CHECK_SEC)
            data = _load_chats_store()
            now = int(time.time())

            for key, meta in list(data.items()):
                try:
                    chat_id = int(key)
                except Exception:
                    continue

                last_started = int(meta.get("last_started_ts", 0))
                last_reminded = int(meta.get("last_reminded_ts", 0))

                if last_started <= 0:
                    continue
                if now - last_started < REMIND_EVERY_SEC:
                    continue
                if last_reminded >= last_started:
                    continue

                try:
                    await bot.send_message(
                        chat_id,
                        "Эй 😏\nТри дня тишины…\nМожет, сыграем снова в «Между нами 🤫»?\n\nНапишите: «Начать игру» 👇",
                    )
                    meta["last_reminded_ts"] = now
                    data[key] = meta
                except Exception:
                    continue

            _save_chats_store(data)
        except asyncio.CancelledError:
            return
        except Exception:
            continue


# =========================
# WATCHDOG
# =========================
async def watchdog(chat_id: int):
    while True:
        await asyncio.sleep(10)
        gs = GAMES.get(chat_id)
        if not gs:
            return

        idle_sec = (datetime.utcnow() - gs.last_activity).total_seconds()

        if gs.state != State.IDLE and idle_sec >= SESSION_CLOSE_SEC:
            await end_game(chat_id, reason=end_phrase_inactive())
            return


def ensure_watchdog(gs: GameState):
    if gs.watchdog_task and not gs.watchdog_task.done():
        return
    gs.watchdog_task = asyncio.create_task(watchdog(gs.chat_id))


# =========================
# ROUND FLOW (упрощённо, как у тебя было)
# =========================
async def start_round(chat_id: int):
    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.RUNNING:
        return

    if len(gs.players) < MIN_PLAYERS:
        await bot.send_message(chat_id, "Для игры нужно минимум двое.\nВсе разошлись? Я тоже пойду 😏")
        await end_game(chat_id)
        return

    touch(gs)

    gs.awaiting_next = False
    gs.extended_once = False
    gs.extend_used = False
    gs.extend_prompt_msg_id = None

    gs.round += 1
    gs.votes_by_target.clear()
    gs.voted_users.clear()
    gs.total_votes = 0

    snapshot_ids = [uid for uid in gs.join_order if uid in gs.players]
    gs.round_voters = set(snapshot_ids)
    gs.round_targets = snapshot_ids[:]

    q, is_spicy, has_secret = choose_question(gs)

    q_line = md_bold_caps(q)
    secret_line = "\n\n" + md_italic("Только честно. Это между нами 🤫") if has_secret else ""
    spicy_line = "\n\n" + md_italic("Отвечайте честно. Это между нами 🤫") if is_spicy else ""
    timer_line = "\n\n" + md_italic(f"({ROUND_VOTE_SECONDS} секунд на голосование)")

    text = (
        f"Раунд {gs.round} 😈\n\n"
        f"{q_line}{secret_line}{spicy_line}{timer_line}\n\n"
        f"Голосуйте 👇"
    )

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
    if not gs or gs.state != State.RUNNING or gs.awaiting_next:
        return

    not_all_voted = len(gs.voted_users) < len(gs.round_voters)
    if not gs.extended_once and (not_all_voted or gs.total_votes == 0):
        gs.extended_once = True
        touch(gs)

        missing = len(gs.round_voters) - len(gs.voted_users)
        no_votes = (gs.total_votes == 0)

        m = await bot.send_message(
            chat_id,
            time_up_phrase(missing, no_votes) + f"\n\nДадим ещё {EXTEND_SECONDS} секунд?\nТолько ведущий может продлить 😏",
            reply_markup=kb_not_all_voted(),
        )
        gs.extend_prompt_msg_id = m.message_id
        return

    await show_round_result(chat_id)


async def show_round_result(chat_id: int):
    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.RUNNING or gs.awaiting_next:
        return

    touch(gs)
    gs.awaiting_next = True

    if gs.round_timer_task and not gs.round_timer_task.done():
        gs.round_timer_task.cancel()

    if gs.extend_prompt_msg_id:
        try:
            await bot.delete_message(chat_id, gs.extend_prompt_msg_id)
        except Exception:
            pass
        gs.extend_prompt_msg_id = None

    if gs.total_votes == 0:
        await bot.send_message(chat_id, f"Итог раунда {gs.round}:\nНикого не выбрали 😏", reply_markup=kb_result())
        return

    items = sorted(gs.votes_by_target.items(), key=lambda x: x[1], reverse=True)
    lines = [f"Итог раунда {gs.round}:"]
    for uid, c in items:
        p = gs.players.get(uid)
        if p and c > 0:
            lines.append(f"{p.label} — {c}")
    await bot.send_message(chat_id, "\n".join(lines), reply_markup=kb_result())


async def end_game(chat_id: int, reason: str = ""):
    gs = GAMES.get(chat_id)
    if not gs:
        return

    if gs.round_timer_task and not gs.round_timer_task.done():
        gs.round_timer_task.cancel()
    if gs.watchdog_task and not gs.watchdog_task.done():
        gs.watchdog_task.cancel()

    if gs.extend_prompt_msg_id:
        try:
            await bot.delete_message(chat_id, gs.extend_prompt_msg_id)
        except Exception:
            pass

    GAMES.pop(chat_id, None)
    await bot.send_message(chat_id, reason or "Ок. Игра завершена 😏")


# =========================
# DM /start (главное)
# =========================
@dp.message(CommandStart())
async def cmd_start(message: Message):
    if message.chat.type == "private":
        await message.answer(dm_welcome_text(), reply_markup=kb_add_to_group(), parse_mode="Markdown")
        return
    await message.answer("Я тут 😏\nНапишите: «Начать игру»\n\n/help — правила")


@dp.callback_query(F.data == "howto_dm")
async def cb_howto_dm(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "Коротко:\n"
        "1) Добавь меня в группу\n"
        "2) В группе напиши: *Начать игру*\n"
        "3) Жмите «Присоединиться» и погнали 😈",
        parse_mode="Markdown",
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Как играем:\n"
        "1) Напишите: Начать игру\n"
        "2) Все жмут: Присоединиться\n"
        "3) Создатель жмёт: Ну что? Погнали?\n"
        "4) Вопрос → голосование → итог → следующий\n\n"
        "Это между нами 🤫"
    )


@dp.message(F.text.casefold() == "начать игру")
async def start_lobby(message: Message):
    chat_id = message.chat.id
    gs = GAMES.get(chat_id)

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
        "Между нами 🤫\n\nИгра создаётся.\nЖмите «Присоединиться».",
        reply_markup=kb_lobby(gs),
    )


@dp.callback_query(F.data == "cancel")
async def cb_cancel(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    GAMES.pop(chat_id, None)
    await cb.answer("Ок")
    try:
        await cb.message.edit_text(cancel_phrase())
    except Exception:
        await cb.message.answer(cancel_phrase())


@dp.callback_query(F.data == "join")
async def cb_join(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.LOBBY:
        await cb.answer("Лобби закрыто. Напиши «Начать игру».", show_alert=True)
        return

    uid = cb.from_user.id
    if uid in gs.players:
        await cb.answer("Ты уже в игре 😏", show_alert=False)
        return

    if len(gs.players) >= MAX_PLAYERS:
        await cb.answer("Уже 10 игроков. Просто наблюдай 😈", show_alert=True)
        return

    u = cb.from_user
    label = make_unique_label(gs, u)
    gs.players[uid] = Player(user_id=uid, name=base_name_from_user(u), label=label)
    gs.join_order.append(uid)

    await cb.answer("Записал ✅", show_alert=False)
    try:
        await cb.message.edit_text(
            "Между нами 🤫\n\nИгра создаётся.\nНажмите «Присоединиться».\n\nВ игре:\n" + format_players(gs),
            reply_markup=kb_lobby(gs),
        )
    except Exception:
        pass


@dp.callback_query(F.data == "start")
async def cb_start(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.LOBBY:
        await cb.answer("Лобби закрыто. Напиши «Начать игру».", show_alert=True)
        return

    host = get_host(gs)
    if host is not None and cb.from_user.id != host:
        await cb.answer("Стартует только ведущий 😏", show_alert=True)
        return

    if len(gs.players) < MIN_PLAYERS:
        await cb.answer("Нужно минимум 2 игрока.", show_alert=True)
        return

    gs.state = State.RUNNING
    touch(gs)
    mark_chat_started(chat_id)

    await cb.answer("Поехали")
    await start_round(chat_id)


@dp.callback_query(F.data.startswith("vote:"))
async def cb_vote(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.RUNNING:
        await cb.answer("Игра не запущена.", show_alert=False)
        return

    voter_id = cb.from_user.id
    if voter_id in gs.voted_users:
        await cb.answer(already_voted_phrase(), show_alert=False)
        return

    try:
        target_id = int(cb.data.split(":", 1)[1])
    except Exception:
        await cb.answer("Кривой голос 🤨", show_alert=False)
        return

    if target_id == voter_id:
        await cb.answer("За себя нельзя 😈", show_alert=True)
        return

    gs.voted_users.add(voter_id)
    gs.votes_by_target[target_id] = gs.votes_by_target.get(target_id, 0) + 1
    gs.total_votes += 1

    await cb.answer("Засчитано ✅", show_alert=False)

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

    host = get_host(gs)
    if host is not None and cb.from_user.id != host:
        await cb.answer("Продлить может только ведущий 😏", show_alert=True)
        return

    if gs.extend_used:
        await cb.answer("Уже продлили 😏", show_alert=False)
        try:
            await cb.message.delete()
        except Exception:
            pass
        gs.extend_prompt_msg_id = None
        return

    gs.extend_used = True
    await cb.answer(f"+{EXTEND_SECONDS} сек 😏", show_alert=False)

    if gs.round_timer_task and not gs.round_timer_task.done():
        gs.round_timer_task.cancel()
    gs.round_timer_task = asyncio.create_task(round_timer(chat_id, EXTEND_SECONDS))

    try:
        await cb.message.delete()
    except Exception:
        pass
    gs.extend_prompt_msg_id = None


@dp.callback_query(F.data == "force_result")
async def cb_force_result(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.RUNNING:
        await cb.answer("Неактуально.", show_alert=False)
        return

    host = get_host(gs)
    if host is not None and cb.from_user.id != host:
        await cb.answer("Только ведущий может не ждать 😏", show_alert=True)
        return

    await cb.answer("Ок. Не ждём 😈", show_alert=False)
    if gs.round_timer_task and not gs.round_timer_task.done():
        gs.round_timer_task.cancel()
    await show_round_result(chat_id)


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

    if not gs.awaiting_next:
        await cb.answer("Сначала дождёмся результата 😈", show_alert=False)
        return

    await cb.answer(next_ack_phrase(), show_alert=False)
    await start_round(chat_id)


@dp.callback_query(F.data == "end")
async def cb_end(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    await cb.answer("Ок", show_alert=False)
    await end_game(chat_id, reason="Игра закрыта 😏")


# =========================
# Group приветствие 1 раз при добавлении бота
# =========================
@dp.my_chat_member()
async def on_my_chat_member(update: ChatMemberUpdated):
    chat = update.chat
    if chat.type not in ("group", "supergroup"):
        return

    old_status = update.old_chat_member.status
    new_status = update.new_chat_member.status

    added = old_status in ("left", "kicked") and new_status in ("member", "administrator")
    if not added:
        return

    if was_group_welcome_sent(chat.id):
        return

    try:
        await bot.send_message(chat.id, group_welcome_text(), parse_mode="Markdown")
        mark_group_welcome_sent(chat.id)
    except Exception:
        return


# =========================
# MAIN
# =========================
async def main():
    global BOT_USERNAME
    me = await bot.get_me()
    BOT_USERNAME = (me.username or "").strip()
    print(f"✅ Bot started as @{BOT_USERNAME}")

    asyncio.create_task(reminder_loop())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
