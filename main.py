import asyncio
import json
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    Message,
    PreCheckoutQuery,
    LabeledPrice,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в переменных окружения (Railway Variables).")

ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "").strip()
ADMIN_IDS: Set[int] = set()
if ADMIN_IDS_RAW:
    for x in ADMIN_IDS_RAW.split(","):
        x = x.strip()
        if x.isdigit():
            ADMIN_IDS.add(int(x))

MAX_PLAYERS = 10
MIN_PLAYERS = 2

ROUND_VOTE_SECONDS = 15
EXTEND_SECONDS = 15

LOBBY_CLOSE_SEC = 5 * 60
SESSION_CLOSE_SEC = 10 * 60

NEXT_COOLDOWN_SEC = 1.0

DATA_DIR = Path(".")
CHATS_STORE_PATH = DATA_DIR / "chats.json"
STATS_PATH = DATA_DIR / "stats.json"
SUGGESTIONS_PATH = DATA_DIR / "suggestions.json"

REMIND_EVERY_SEC = 3 * 24 * 60 * 60
REMIND_CHECK_SEC = 60 * 60

BOT_USERNAME: str = ""


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


@dataclass
class Player:
    user_id: int
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

    # spicy каждые 3–4, secret вставка каждые 4–5
    since_last_spicy: int = 0
    next_spicy_at: int = field(default_factory=lambda: random.randint(3, 4))
    since_last_secret: int = 0
    next_secret_at: int = field(default_factory=lambda: random.randint(4, 5))

    round_targets: List[int] = field(default_factory=list)
    round_voters: Set[int] = field(default_factory=set)

    votes_by_target: Dict[int, int] = field(default_factory=dict)
    voted_users: Set[int] = field(default_factory=set)
    total_votes: int = 0

    extended_prompted: bool = False
    extend_used: bool = False
    extend_prompt_msg_id: Optional[int] = None

    awaiting_next: bool = False

    last_activity: datetime = field(default_factory=datetime.utcnow)
    watchdog_task: Optional[asyncio.Task] = None
    round_timer_task: Optional[asyncio.Task] = None

    last_next_press_ts: Dict[int, float] = field(default_factory=dict)


GAMES: Dict[int, GameState] = {}


# =========================
# JSON helpers
# =========================
def _read_json(path: Path, default):
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# =========================
# STATS
# =========================
def stats_init():
    if STATS_PATH.exists():
        return
    _write_json(
        STATS_PATH,
        {
            "users_unique": 0,
            "users_seen": [],
            "chats_unique": 0,
            "chats_seen": [],
            "games_started": 0,
            "rounds_played": 0,
            "votes_cast": 0,
            "donations_stars_total": 0,
            "donations_count": 0,
            "suggestions_count": 0,
            "updated_ts": int(time.time()),
        },
    )


def stats_touch_user(user_id: int):
    s = _read_json(STATS_PATH, {})
    seen = set(s.get("users_seen", []))
    if user_id not in seen:
        seen.add(user_id)
        s["users_seen"] = sorted(list(seen))
        s["users_unique"] = len(seen)
    s["updated_ts"] = int(time.time())
    _write_json(STATS_PATH, s)


def stats_touch_chat(chat_id: int):
    s = _read_json(STATS_PATH, {})
    seen = set(s.get("chats_seen", []))
    if chat_id not in seen:
        seen.add(chat_id)
        s["chats_seen"] = sorted(list(seen))
        s["chats_unique"] = len(seen)
    s["updated_ts"] = int(time.time())
    _write_json(STATS_PATH, s)


def stats_inc(key: str, n: int = 1):
    s = _read_json(STATS_PATH, {})
    s[key] = int(s.get(key, 0)) + n
    s["updated_ts"] = int(time.time())
    _write_json(STATS_PATH, s)


# =========================
# CHATS STORE (reminders + group welcome once)
# =========================
def chats_store_mark_game_started(chat_id: int) -> None:
    data = _read_json(CHATS_STORE_PATH, {})
    key = str(chat_id)
    now = int(time.time())
    meta = data.get(key, {})
    meta["last_started_ts"] = now
    meta.setdefault("last_reminded_ts", 0)
    data[key] = meta
    _write_json(CHATS_STORE_PATH, data)


def chats_store_welcome_sent(chat_id: int) -> bool:
    data = _read_json(CHATS_STORE_PATH, {})
    meta = data.get(str(chat_id), {})
    return int(meta.get("welcome_sent_ts", 0)) > 0


def chats_store_mark_welcome(chat_id: int) -> None:
    data = _read_json(CHATS_STORE_PATH, {})
    key = str(chat_id)
    meta = data.get(key, {})
    meta["welcome_sent_ts"] = int(time.time())
    data[key] = meta
    _write_json(CHATS_STORE_PATH, data)


# =========================
# STYLE
# =========================
def pick(arr: List[str]) -> str:
    return random.choice(arr)


DM_WELCOME_VARIANTS = [
    "Этот бот поможет вам *не заскучать*, задавая *колкие вопросы*.\nНадеюсь, вы *не поругаетесь* во время игры 😈",
    "Я тут, чтобы компания *не тухла*.\nВопросы — *острые*. Итоги — *неловкие*.\nНе подеритесь там 😏",
    "Если в чате стало *слишком тихо* — я это исправлю.\nГлавное: *не обижайтесь*. Почти 🤫",
    "Я добавляю *жару* в любой чат.\n*Колкие вопросы* + *быстрые голосования*.\nНадеюсь, вы выживете 😈",
    "Мини-реалити в вашем чате:\n*вопрос → голосование → итог*.\nДа, будет неловко 😏",
]

ALREADY_VOTED_VARIANTS = [
    "Всё, *выбор сделан* 😏",
    "Один голос — и *живи с этим* 🤫",
    "Поздно *переобуваться* 😈",
    "Голос уже улетел. *Не догоняй*.",
    "Второй попытки *не будет* 😏",
    "Без переигровок. Я *строгий*.",
    "Ты уже отметился 😈",
    "Назад дороги нет 🤫",
    "Переобувка запрещена 😏",
    "Голос засчитан. *Терпи* 😈",
]

NEXT_VARIANTS = [
    "Дальше 😈",
    "Ещё один раунд? *С удовольствием* 😏",
    "Поехали. Сейчас будет *лучше*.",
    "Не тормозим 🤫",
    "Продолжаем — и *не краснеем* 😈",
    "Следующий. *Держитесь*.",
    "Ок, жмём газ 😏",
    "Вперёд. Я только разогрелся 😈",
    "Ещё вопросик — и кто-то *вскроется* 🤫",
    "Погнали. Без лишних слов 😏",
]

END_VARIANTS = [
    "Было *опасно приятно* 😈 Возвращайтесь.",
    "Ну всё, красавчики. Захотите ещё — *зовите* 😏",
    "Игра окончена. *Обиды не хранить*. Почти 🤫",
    "Разошлись красиво. Но я всё *запомнил* 😈",
    "Спасибо за игру. В следующий раз будет *ещё больнее* 😏",
    "Конец. И да — это *между нами* 🤫",
    "Пауза на жизнь. Потом продолжим 😈",
    "Вы держались достойно. *Почти* 😏",
    "Игра закрыта. Кто обиделся — тот проиграл 🤫",
    "До встречи. Я рядом, когда станет скучно 😈",
]

INACTIVE_END_VARIANTS = [
    "*10 минут тишины*… я понял 🫠\nЗакрываю игру. Вернётесь — продолжим 😈",
    "Чат ушёл в спячку 😴\nЗакрываю сессию. Но я рядом 😏",
    "Тишина слишком громкая 🤫\nЗакрываю игру.",
    "Пауза затянулась.\nЗакрываю 😈",
    "Я подождал. Хватит 🤫\nЗакрываю.",
]

TIMEUP_NO_VOTES = [
    "*Время вышло* ⏰\nИ… никто не рискнул 😏",
    "*Ноль голосов*.\nСлишком мило. Подозрительно 🤨",
    "Тишина.\n*Боитесь последствий?* 😈",
    "Никто не нажал.\nНу вы и осторожные 🤫",
    "Ноль.\nЯ даже разочарован 😏",
]

TIMEUP_MISSING = [
    "*Время вышло* ⏰\nЕщё *{missing}* молчат…",
    "*{missing}* всё ещё “думают” 😏",
    "Ещё *{missing}* без голоса.\nТянете драму 🤫",
    "Жду *{missing}*.\nНо недолго 😈",
    "Ещё *{missing}* — и считаем как есть 😏",
]


# =========================
# DM MENU TEXTS
# =========================
def dm_home_text() -> str:
    return (
        "Меню 😏\n\n"
        "— *Добавь меня в группу* и запусти *«Начать игру»*\n"
        "— Предложи свой вопрос (если он злой — я его люблю)\n"
        "— Поддержи проект Stars ⭐\n\n"
        "*Выбирай* 👇"
    )


def dm_howto_text() -> str:
    return (
        "*Как играть* 📌\n\n"
        "1) *Добавь меня в группу*\n"
        "2) В группе: *Начать игру*\n"
        "3) Все жмут: *Присоединиться*\n"
        "4) Ведущий жмёт: *Погнали*\n\n"
        "Дальше: *вопрос → голосование → итог*.\n"
        "*За себя голосовать нельзя* 😈"
    )


def dm_suggest_text() -> str:
    return (
        "*Предложить вопрос* 💡\n\n"
        "Напиши командой:\n"
        "* /suggest Кто из вас…? *\n\n"
        "Я всё соберу.\n"
        "Если вопрос *годный и колкий* — добавим в игру 😈"
    )


def dm_donate_text() -> str:
    return (
        "*Поддержать проект Stars* ⭐\n\n"
        "Донат прилетает *боту (Stars)* и идёт в развитие.\n"
        "Мы это превратим в *ещё более колкие вопросы* 😈\n\n"
        "*Выбирай сумму* 👇"
    )


# =========================
# DM MENU EDIT HELPER
# =========================
async def dm_edit_menu(cb: CallbackQuery, text: str, markup):
    """
    Красивое меню: редактируем текущее сообщение.
    Если редактирование невозможно — мягко шлём новое.
    """
    try:
        await cb.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return
        await bot.send_message(cb.from_user.id, text, reply_markup=markup, parse_mode="Markdown")


# =========================
# KEYBOARDS
# =========================
def kb_dm_home():
    b = InlineKeyboardBuilder()
    if BOT_USERNAME:
        b.button(text="➕ Добавить в группу", url=f"https://t.me/{BOT_USERNAME}?startgroup=1")
    b.button(text="📌 Как играть", callback_data="dm_howto")
    b.button(text="💡 Предложить вопрос", callback_data="dm_suggest")
    b.button(text="⭐ Поддержать Stars", callback_data="dm_donate")
    b.adjust(1, 1, 1, 1)
    return b.as_markup()


def kb_dm_back():
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад", callback_data="dm_back")
    b.adjust(1)
    return b.as_markup()


def kb_dm_donate_amounts():
    b = InlineKeyboardBuilder()
    for amt in [10, 25, 50, 100, 250, 500, 1000]:
        b.button(text=f"⭐ {amt}", callback_data=f"donate:{amt}")
    b.button(text="⬅️ Назад", callback_data="dm_back")
    b.adjust(3, 2, 2, 1)
    return b.as_markup()


def kb_group_lobby():
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
# GAME HELPERS
# =========================
def touch(gs: GameState):
    gs.last_activity = datetime.utcnow()


def anti_spam_next_ok(gs: GameState, user_id: int) -> bool:
    now = time.time()
    last = gs.last_next_press_ts.get(user_id, 0.0)
    if now - last < NEXT_COOLDOWN_SEC:
        return False
    gs.last_next_press_ts[user_id] = now
    return True


def make_label(gs: GameState, u) -> str:
    base = (u.full_name or "").strip() or (f"@{u.username}" if u.username else str(u.id))
    if base.startswith("@"):
        return base
    existing = {p.label for p in gs.players.values()}
    if base not in existing:
        return base
    i = 2
    while True:
        candidate = f"{base}#{i}"
        if candidate not in existing:
            return candidate
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


def get_host(gs: GameState) -> Optional[int]:
    if gs.host_user_id is not None:
        return gs.host_user_id
    if gs.join_order:
        gs.host_user_id = gs.join_order[0]
        return gs.host_user_id
    return None


async def cleanup_game(gs: GameState):
    if gs.round_timer_task and not gs.round_timer_task.done():
        gs.round_timer_task.cancel()
    if gs.watchdog_task and not gs.watchdog_task.done():
        gs.watchdog_task.cancel()
    if gs.extend_prompt_msg_id:
        try:
            await bot.delete_message(gs.chat_id, gs.extend_prompt_msg_id)
        except Exception:
            pass
        gs.extend_prompt_msg_id = None


# =========================
# REMINDER LOOP
# =========================
async def reminder_loop():
    while True:
        try:
            await asyncio.sleep(REMIND_CHECK_SEC)
            data = _read_json(CHATS_STORE_PATH, {})
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
                        "Эй 😏\n"
                        "*Три дня тишины*…\n"
                        "Может, снова сыграем в *«Между нами 🤫»*?\n\n"
                        "Напишите: *«Начать игру»* 👇",
                        parse_mode="Markdown",
                    )
                    meta["last_reminded_ts"] = now
                    data[key] = meta
                except Exception:
                    continue

            _write_json(CHATS_STORE_PATH, data)

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

        if gs.state == State.LOBBY and idle_sec >= LOBBY_CLOSE_SEC:
            await cleanup_game(gs)
            GAMES.pop(chat_id, None)
            try:
                await bot.send_message(
                    chat_id,
                    "Лобби протухло 🫠\n"
                    "*5 минут тишины* — закрываю сбор.\n\n"
                    "Хотите снова — напишите *«Начать игру»* 😏",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
            return

        if gs.state != State.IDLE and idle_sec >= SESSION_CLOSE_SEC:
            await end_game(chat_id, reason=pick(INACTIVE_END_VARIANTS))
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
    if not gs or gs.state != State.RUNNING:
        return

    if len(gs.players) < MIN_PLAYERS:
        await bot.send_message(
            chat_id,
            "Для игры нужно *минимум двое*.\nВсе разошлись? Я тоже 😏",
            parse_mode="Markdown",
        )
        await end_game(chat_id)
        return

    touch(gs)

    gs.awaiting_next = False
    gs.extended_prompted = False
    gs.extend_used = False
    gs.extend_prompt_msg_id = None

    gs.round += 1
    stats_inc("rounds_played", 1)

    gs.votes_by_target.clear()
    gs.voted_users.clear()
    gs.total_votes = 0

    snapshot_ids = [uid for uid in gs.join_order if uid in gs.players]
    gs.round_voters = set(snapshot_ids)
    gs.round_targets = snapshot_ids[:]

    q, is_spicy, has_secret = choose_question(gs)

    extras = []
    if has_secret:
        extras.append("*Только честно* 🤫")
    if is_spicy:
        extras.append("*Отвечайте честно* 😈")
    extras.append(f"*{ROUND_VOTE_SECONDS} сек* на голосование")

    text = (
        f"*Раунд {gs.round}* 😈\n\n"
        f"{q}\n\n"
        f"({', '.join(extras)})\n\n"
        f"*Голосуйте* 👇"
    )

    if gs.round_timer_task and not gs.round_timer_task.done():
        gs.round_timer_task.cancel()

    await bot.send_message(chat_id, text, reply_markup=kb_vote(gs), parse_mode="Markdown")
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

    if not gs.extended_prompted and (not_all_voted or gs.total_votes == 0):
        gs.extended_prompted = True
        touch(gs)

        missing = len(gs.round_voters) - len(gs.voted_users)
        msg = pick(TIMEUP_NO_VOTES) if gs.total_votes == 0 else pick(TIMEUP_MISSING).format(missing=missing)

        m = await bot.send_message(
            chat_id,
            msg + f"\n\nДадим ещё *{EXTEND_SECONDS} секунд*?\n*Только ведущий* может продлить 😏",
            reply_markup=kb_not_all_voted(),
            parse_mode="Markdown",
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

    # убираем “продлить?” если висит
    if gs.extend_prompt_msg_id:
        try:
            await bot.delete_message(chat_id, gs.extend_prompt_msg_id)
        except Exception:
            pass
        gs.extend_prompt_msg_id = None

    if gs.total_votes == 0:
        await bot.send_message(
            chat_id,
            f"*Итог раунда {gs.round}:*\nНикого не выбрали.\nСлишком мирно… подозрительно 🤨",
            reply_markup=kb_result(),
            parse_mode="Markdown",
        )
        return

    items = sorted(gs.votes_by_target.items(), key=lambda x: x[1], reverse=True)
    lines = [f"*Итог раунда {gs.round}:*"]
    for uid, c in items:
        if c <= 0:
            continue
        p = gs.players.get(uid)
        if p:
            lines.append(f"— *{p.label}*: {c}")

    await bot.send_message(chat_id, "\n".join(lines), reply_markup=kb_result(), parse_mode="Markdown")


async def end_game(chat_id: int, reason: str = ""):
    gs = GAMES.get(chat_id)
    if not gs:
        return

    await cleanup_game(gs)
    GAMES.pop(chat_id, None)

    tail = pick(END_VARIANTS)
    text = f"{reason}\n\n{tail}" if reason else tail
    await bot.send_message(chat_id, text, parse_mode="Markdown")


# =========================
# PRIVATE /start
# =========================
@dp.message(CommandStart())
async def cmd_start(message: Message):
    stats_touch_user(message.from_user.id)

    if message.chat.type == "private":
        text = (
            "Привет 😏\n\n"
            f"{pick(DM_WELCOME_VARIANTS)}\n\n"
            "*Как запустить:*\n"
            "1) *Добавь меня в группу*\n"
            "2) В группе напиши: *Начать игру*\n\n"
            "Команды:\n"
            "— /help — правила\n"
            "— /suggest <вопрос> — предложить свой\n"
            "— /donate — поддержать Stars ⭐\n\n"
            "Жми кнопки — будет красиво 👇"
        )
        await message.answer(text, reply_markup=kb_dm_home(), parse_mode="Markdown")
        return

    await message.answer(
        "Я тут 😏\nЧтобы начать — напишите: *Начать игру*\n/help — правила",
        parse_mode="Markdown",
    )


# =========================
# DM MENUS (callbacks) — EDIT MODE
# =========================
@dp.callback_query(F.data == "dm_back")
async def cb_dm_back(cb: CallbackQuery):
    await cb.answer()
    await dm_edit_menu(cb, dm_home_text(), kb_dm_home())


@dp.callback_query(F.data == "dm_howto")
async def cb_dm_howto(cb: CallbackQuery):
    await cb.answer()
    await dm_edit_menu(cb, dm_howto_text(), kb_dm_back())


@dp.callback_query(F.data == "dm_suggest")
async def cb_dm_suggest(cb: CallbackQuery):
    await cb.answer()
    await dm_edit_menu(cb, dm_suggest_text(), kb_dm_back())


@dp.callback_query(F.data == "dm_donate")
async def cb_dm_donate(cb: CallbackQuery):
    await cb.answer()
    await dm_edit_menu(cb, dm_donate_text(), kb_dm_donate_amounts())


# =========================
# /help
# =========================
@dp.message(Command("help"))
async def cmd_help(message: Message):
    stats_touch_user(message.from_user.id)
    await message.answer(
        "*Как играем:*\n"
        "1) В группе: *Начать игру*\n"
        "2) Все: *Присоединиться*\n"
        "3) Ведущий: *Погнали*\n"
        "4) *Вопрос → 15 сек → итог → следующий*\n\n"
        "*Правила:*\n"
        "— За себя нельзя 😈\n"
        "— Продление: *только ведущий*\n"
        "— Лобби тухнет через *5 минут*\n"
        "— Игра закрывается через *10 минут тишины*\n\n"
        "Это между нами 🤫",
        parse_mode="Markdown",
    )


# =========================
# GROUP: “Начать игру”
# =========================
@dp.message(F.text.casefold() == "начать игру")
async def start_lobby(message: Message):
    stats_touch_user(message.from_user.id)
    stats_touch_chat(message.chat.id)

    chat_id = message.chat.id
    gs = GAMES.get(chat_id)

    if gs and gs.state in {State.LOBBY, State.RUNNING}:
        await message.answer("Игра уже идёт 😏\nЖмите кнопки под сообщениями.")
        return

    gs = GameState(chat_id=chat_id, state=State.LOBBY, host_user_id=message.from_user.id)
    GAMES[chat_id] = gs
    touch(gs)
    ensure_watchdog(gs)

    await message.answer(
        "*Между нами* 🤫\n\n"
        "Собираю игроков.\n"
        "Жмите *«Присоединиться»*.\n\n"
        "*Ведущий* — тот, кто начал 😏",
        reply_markup=kb_group_lobby(),
        parse_mode="Markdown",
    )


@dp.callback_query(F.data == "cancel")
async def cb_cancel(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if gs:
        await cleanup_game(gs)
    GAMES.pop(chat_id, None)

    await cb.answer("Ок")
    try:
        await cb.message.edit_text("Отмена 😏\n*Интрига остаётся.*", parse_mode="Markdown")
    except Exception:
        await cb.message.answer("Отмена 😏\n*Интрига остаётся.*", parse_mode="Markdown")


@dp.callback_query(F.data == "join")
async def cb_join(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.LOBBY:
        await cb.answer("Лобби закрыто. Напиши «Начать игру».", show_alert=True)
        return

    stats_touch_user(cb.from_user.id)
    stats_touch_chat(chat_id)

    touch(gs)
    ensure_watchdog(gs)

    uid = cb.from_user.id
    if uid in gs.players:
        await cb.answer("Ты уже в игре 😏")
        return
    if len(gs.players) >= MAX_PLAYERS:
        await cb.answer("Уже 10 игроков. Можешь только смотреть 😈", show_alert=True)
        return

    label = make_label(gs, cb.from_user)
    gs.players[uid] = Player(user_id=uid, label=label)
    gs.join_order.append(uid)

    await cb.answer("Записал ✅")

    try:
        players_text = "\n".join([f"• {gs.players[i].label}" for i in gs.join_order])
        await cb.message.edit_text(
            "*Между нами* 🤫\n\n"
            "Собираю игроков.\n"
            "Жмите *«Присоединиться»*.\n\n"
            "*В игре:*\n" + (players_text or "Пока никого."),
            reply_markup=kb_group_lobby(),
            parse_mode="Markdown",
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
        await cb.answer("Стартует только *ведущий* 😏", show_alert=True)
        return

    if len(gs.players) < MIN_PLAYERS:
        await cb.answer("Нужно минимум *2 игрока*.", show_alert=True)
        return

    gs.state = State.RUNNING
    touch(gs)

    chats_store_mark_game_started(chat_id)
    stats_inc("games_started", 1)

    await cb.answer("Погнали 😈")
    await start_round(chat_id)


@dp.callback_query(F.data.startswith("vote:"))
async def cb_vote(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.RUNNING:
        await cb.answer("Игра не запущена.")
        return

    touch(gs)

    voter_id = cb.from_user.id
    if voter_id not in gs.round_voters:
        await cb.answer("Ты не в этом раунде 😏", show_alert=True)
        return
    if voter_id in gs.voted_users:
        await cb.answer(pick(ALREADY_VOTED_VARIANTS))
        return

    try:
        target_id = int(cb.data.split(":", 1)[1])
    except Exception:
        await cb.answer("Кривой голос 🤨")
        return

    if target_id == voter_id:
        await cb.answer("За себя нельзя 😈", show_alert=True)
        return
    if target_id not in gs.round_targets:
        await cb.answer("Этого игрока нет в текущем раунде.")
        return

    gs.voted_users.add(voter_id)
    gs.votes_by_target[target_id] = gs.votes_by_target.get(target_id, 0) + 1
    gs.total_votes += 1
    stats_inc("votes_cast", 1)

    if target_id in gs.players:
        gs.players[target_id].score += 1

    await cb.answer("Засчитано ✅")

    if len(gs.voted_users) >= len(gs.round_voters):
        if gs.round_timer_task and not gs.round_timer_task.done():
            gs.round_timer_task.cancel()
        await show_round_result(chat_id)


@dp.callback_query(F.data == "extend")
async def cb_extend(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.RUNNING:
        await cb.answer("Неактуально.")
        return

    host = get_host(gs)
    if host is not None and cb.from_user.id != host:
        await cb.answer("Продлить может только *ведущий* 😏", show_alert=True)
        return

    if gs.awaiting_next:
        await cb.answer("Поздно. Уже считаю 😈")
        return

    if gs.extend_used:
        await cb.answer("Уже продлили 😏")
        try:
            await cb.message.delete()
        except Exception:
            pass
        gs.extend_prompt_msg_id = None
        return

    gs.extend_used = True
    touch(gs)
    await cb.answer(f"+{EXTEND_SECONDS} сек 😏")

    if gs.round_timer_task and not gs.round_timer_task.done():
        gs.round_timer_task.cancel()
    gs.round_timer_task = asyncio.create_task(round_timer(chat_id, EXTEND_SECONDS))

    # удаляем служебку “продлить?”
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
        await cb.answer("Неактуально.")
        return

    host = get_host(gs)
    if host is not None and cb.from_user.id != host:
        await cb.answer("Только *ведущий* может не ждать 😏", show_alert=True)
        return

    touch(gs)
    await cb.answer("Ок. Не ждём 😈")

    if gs.round_timer_task and not gs.round_timer_task.done():
        gs.round_timer_task.cancel()

    await show_round_result(chat_id)


@dp.callback_query(F.data == "next")
async def cb_next(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.RUNNING:
        await cb.answer("Игра не запущена.")
        return

    if not anti_spam_next_ok(gs, cb.from_user.id):
        await cb.answer("Тише-тише 😏")
        return

    if not gs.awaiting_next:
        await cb.answer("Сначала итог 😈")
        return

    await cb.answer(pick(NEXT_VARIANTS))
    await start_round(chat_id)


@dp.callback_query(F.data == "end")
async def cb_end(cb: CallbackQuery):
    await cb.answer("Ок")
    await end_game(cb.message.chat.id)


# =========================
# Group welcome only once when BOT added
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

    stats_touch_chat(chat.id)

    if chats_store_welcome_sent(chat.id):
        return

    try:
        await bot.send_message(
            chat.id,
            "Я тут 😏\n"
            "Это *«Между нами 🤫»*.\n\n"
            "Чтобы начать — напишите:\n"
            "*Начать игру* 😈\n\n"
            "/help — правила",
            parse_mode="Markdown",
        )
        chats_store_mark_welcome(chat.id)
    except Exception:
        return


# =========================
# Suggestions: /suggest
# =========================
@dp.message(Command("suggest"))
async def cmd_suggest(message: Message):
    stats_touch_user(message.from_user.id)

    text = (message.text or "").strip()
    parts = text.split(maxsplit=1)
    suggestion = parts[1].strip() if len(parts) > 1 else ""

    if not suggestion or len(suggestion) < 10:
        await message.answer(
            "Коротко слишком 😏\nПример:\n*/suggest Кто из вас чаще всего…?*",
            parse_mode="Markdown",
        )
        return

    data = _read_json(SUGGESTIONS_PATH, [])
    data.append(
        {
            "ts": int(time.time()),
            "user_id": message.from_user.id,
            "username": message.from_user.username,
            "chat_id": message.chat.id,
            "chat_type": message.chat.type,
            "text": suggestion,
        }
    )
    _write_json(SUGGESTIONS_PATH, data)
    stats_inc("suggestions_count", 1)

    await message.answer(
        "Ок 😈 *Записал*.\n"
        "Если вопрос *годный* — добавим и будем палить вас им 🤫",
        parse_mode="Markdown",
    )

    if ADMIN_IDS:
        preview = suggestion if len(suggestion) <= 350 else suggestion[:350] + "…"
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    "💡 *Новый предложенный вопрос:*\n"
                    f"{preview}\n\n"
                    f"От: {message.from_user.id} (@{message.from_user.username})",
                    parse_mode="Markdown",
                )
            except Exception:
                pass


# =========================
# Stats: /stats (admins only)
# =========================
@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    if ADMIN_IDS and message.from_user.id not in ADMIN_IDS:
        await message.answer("Не, это не для тебя 😏")
        return

    stats_init()
    s = _read_json(STATS_PATH, {})
    await message.answer(
        "*📊 Статистика бота:*\n\n"
        f"👤 *Уник. пользователей:* {s.get('users_unique', 0)}\n"
        f"💬 *Уник. чатов:* {s.get('chats_unique', 0)}\n"
        f"🎮 *Игр стартовало:* {s.get('games_started', 0)}\n"
        f"🌀 *Раундов сыграно:* {s.get('rounds_played', 0)}\n"
        f"🗳 *Голосов:* {s.get('votes_cast', 0)}\n"
        f"⭐ *Stars:* {s.get('donations_stars_total', 0)} / {s.get('donations_count', 0)} платежей\n"
        f"💡 *Предложений вопросов:* {s.get('suggestions_count', 0)}",
        parse_mode="Markdown",
    )


# =========================
# Donations: /donate + Stars invoices
# =========================
@dp.message(Command("donate"))
async def cmd_donate(message: Message):
    stats_touch_user(message.from_user.id)
    await message.answer(
        "*Поддержать проект Stars* ⭐\n\n"
        "*Выбирай сумму* 👇",
        reply_markup=kb_dm_donate_amounts(),
        parse_mode="Markdown",
    )


@dp.callback_query(F.data.startswith("donate:"))
async def cb_donate(cb: CallbackQuery):
    await cb.answer()
    try:
        amount = int(cb.data.split(":", 1)[1])
    except Exception:
        await cb.message.answer("Что-то пошло не так 😏")
        return
    if amount <= 0:
        await cb.message.answer("Слишком хитро 😈")
        return

    prices = [LabeledPrice(label="Донат на развитие", amount=amount)]

    await bot.send_invoice(
        chat_id=cb.from_user.id,
        title="Поддержка «Между нами 🤫»",
        description="Добровольный донат Stars на развитие проекта.",
        payload=f"donate_{amount}_{int(time.time())}",
        provider_token="",
        currency="XTR",
        prices=prices,
    )


@dp.pre_checkout_query()
async def pre_checkout(pre: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre.id, ok=True)


@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    sp = message.successful_payment
    stars = int(getattr(sp, "total_amount", 0) or 0)

    stats_inc("donations_count", 1)
    stats_inc("donations_stars_total", stars)

    await message.answer(
        f"*Принято* ⭐ {stars}\n"
        "Спасибо 😏\n"
        "Мы это превратим в *ещё более колкие вопросы* 😈",
        parse_mode="Markdown",
    )


# =========================
# MAIN
# =========================
async def main():
    global BOT_USERNAME

    stats_init()

    me = await bot.get_me()
    BOT_USERNAME = (me.username or "").strip()
    print(f"✅ Started as @{BOT_USERNAME}")

    asyncio.create_task(reminder_loop())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
