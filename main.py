import asyncio
import html
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

# 20 вопросов “Только пацаны”
BOYS_ONLY_QUESTIONS = [
    "Кто из вас пёрнет и будет до последнего делать вид, что это не он? (выбранный оправдывается как адвокат)",
    "Кто напердит и будет угорать так, будто это стендап? (выбранный объясняет, почему ему это смешно)",
    "Кто устроит газовую атаку и обвинит в этом мебель? (выбранный придумывает легенду)",
    "Кто рыгнёт громче всех? (выбранный либо делает, либо публично признаёт поражение 😏)",
    "Кто быстрее всех напивается и начинает философствовать? (выбранный выдаёт свою любимую «пьяную мудрость»)",
    "Кто чаще всего пишет бывшим после алкоголя? (выбранный рассказывает самую нелепую причину “почему вообще написал”)",
    "Кто чаще всех говорит «я трезвый», а через минуту уже не трезвый? (выбранный вспоминает самый позорный «я норм»)",
    "Кто влипает в самые тупые и неловкие ситуации? (выбранный рассказывает топ-1 историю)",
    "Кто может превратить спокойный вечер в хаос буквально из ничего? (выбранный объясняет, как это у него получается)",
    "Кто несёт уверенную чушь так, что люди почти верят? (выбранный придумывает сейчас “факт”, который звучит правдиво)",
    "Кто больше всех понтуется, а потом ловит жёсткий облом? (выбранный рассказывает самый смешной облом)",
    "Кто первый полезет в конфликт из-за полной фигни? (выбранный называет самый тупой повод, из-за которого бесился)",
    "Кто говорит «по одной» — и исчезает до утра? (выбранный рассказывает, где его потом находили)",
    "Кто чаще всех теряет вещи по пьяни? (выбранный рассказывает, что потерял самое тупое)",
    "Кто устроит кринж на людях и поймёт это только дома? (выбранный рассказывает лучший «стыд на утро»)",
    "Кто вечно делает «ща сделаю» и не делает? (выбранный даёт одно публичное обещание на сегодня)",
    "Кто будет ржать с пердежа дольше всех? (выбранный держит серьёзное лицо 10 секунд)",
    "Кто самый опасный, когда ему скучно? (выбранный рассказывает, какую “идею” он однажды предложил)",
    "Кто устроит эпичный фейл на ровном месте? (выбранный рассказывает свой рекорд)",
    "Кто чаще всего встревает в разговор и делает только хуже? (выбранный признаётся, где он так «помог»)",
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

    mode: str = "all"  # all / boys

    players: Dict[int, Player] = field(default_factory=dict)
    join_order: List[int] = field(default_factory=list)

    round: int = 0
    used_normal: Set[int] = field(default_factory=set)
    used_spicy: Set[int] = field(default_factory=set)
    used_boys: Set[int] = field(default_factory=set)

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
    ended: bool = False

    last_activity: datetime = field(default_factory=datetime.utcnow)
    watchdog_task: Optional[asyncio.Task] = None
    round_timer_task: Optional[asyncio.Task] = None

    last_next_press_ts: Dict[int, float] = field(default_factory=dict)

    # lobby identity
    lobby_msg_id: Optional[int] = None
    lobby_token: int = 0

    # round identity
    round_msg_id: Optional[int] = None
    round_token: int = 0

    current_question: str = ""


GAMES: Dict[int, GameState] = {}


# =========================
# HELPERS
# =========================
def h(text: str) -> str:
    return html.escape(text or "")


def split_question_action(q: str) -> Tuple[str, str]:
    q = (q or "").strip()
    if " (" in q and q.endswith(")"):
        head, tail = q.rsplit(" (", 1)
        action = tail[:-1].strip()
        return head.strip(), action
    return q, ""


def _read_json(path: Path, default):
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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


def pick(arr: List[str]) -> str:
    return random.choice(arr)


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
        cand = f"{base}#{i}"
        if cand not in existing:
            return cand
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
    if gs.host_user_id is not None and gs.host_user_id in gs.players:
        return gs.host_user_id
    for uid in gs.join_order:
        if uid in gs.players:
            gs.host_user_id = uid
            return uid
    return gs.host_user_id


async def safe_clear_markup(chat_id: int, message_id: Optional[int]):
    if not message_id:
        return
    try:
        await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=None)
    except Exception:
        pass


def parse_tail_int(cb_data: str) -> Optional[int]:
    try:
        return int(cb_data.split(":", 1)[1])
    except Exception:
        return None


# =========================
# STYLE / TEXTS
# =========================
DM_WELCOME_VARIANTS = [
    "Этот бот поможет вам *не заскучать*, задавая *колкие вопросы*.\nНадеюсь, вы *не поругаетесь* во время игры 😈",
    "Я тут, чтобы компания *не тухла*.\nВопросы — *острые*. Итоги — *неловкие*.\nНе подеритесь там 😏",
    "Если в чате стало *слишком тихо* — я это исправлю.\nГлавное: *не обижайтесь*. Почти 🤫",
    "Я добавляю *жару* в любой чат.\n*Колкие вопросы* + *быстрые голосования*.\nНадеюсь, вы выживете 😈",
    "Мини-реалити в вашем чате:\n*вопрос → голосование → итог*.\nДа, будет неловко 😏",
]

ALREADY_VOTED_TOASTS = [
    "Всё, выбор сделан 😏",
    "Один голос — и живи с этим 🤫",
    "Поздно переобуваться 😈",
    "Голос уже улетел. Не догоняй 😏",
    "Второй попытки не будет 😈",
    "Без переигровок. Я строгий 😏",
    "Ты уже отметился 😈",
    "Назад дороги нет 🤫",
    "Переобувка запрещена 😏",
    "Голос засчитан. Терпи 😈",
]

NEXT_TOASTS = ["Дальше 😈", "Поехали 😏", "Газуем 🤫", "Следующий. Держитесь 😈", "Продолжаем 😏"]

END_VARIANTS = [
    "Было <b>опасно приятно</b> 😈 Возвращайтесь.",
    "Ну всё. Захотите ещё — <b>зовите</b> 😏",
    "Игра окончена. <b>Обиды не хранить</b>. Почти 🤫",
    "Разошлись красиво. Но я всё <b>запомнил</b> 😈",
    "Конец. И да — это <b>между нами</b> 🤫",
]

INACTIVE_END_VARIANTS = [
    "<b>10 минут тишины</b>… я понял 🫠\nЗакрываю игру. Вернётесь — продолжим 😈",
    "Чат ушёл в спячку 😴\nЗакрываю сессию. Но я рядом 😏",
    "Пауза затянулась.\nЗакрываю 😈",
]

TIMEUP_NO_VOTES = [
    "<b>Время вышло</b> ⏰\nИ… никто не рискнул 😏",
    "<b>Ноль голосов</b>.\nСлишком мило. Подозрительно 🤨",
    "Тишина.\n<b>Боитесь последствий?</b> 😈",
]

TIMEUP_MISSING = [
    "<b>Время вышло</b> ⏰\nЕщё <b>{missing}</b> молчат…",
    "Ещё <b>{missing}</b> без голоса.\nТянете драму 🤫",
    "Жду <b>{missing}</b>.\nНо недолго 😈",
]


def dm_home_text() -> str:
    return (
        "Меню 😏\n\n"
        "— *Добавь меня в группу* и запусти *«Начать игру»*\n"
        "— Предложи свой вопрос: */suggest ...*\n"
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
        "Если вопрос *годный и колкий* — добавим 😈"
    )


def dm_donate_text() -> str:
    return (
        "*Поддержать проект Stars* ⭐\n\n"
        "Донат идёт в развитие.\n"
        "Мы это превратим в *ещё более колкие вопросы* 😈\n\n"
        "*Выбирай сумму* 👇"
    )


async def dm_edit_menu(cb: CallbackQuery, text: str, markup):
    try:
        await cb.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return
        await bot.send_message(cb.from_user.id, text, reply_markup=markup, parse_mode="Markdown")


# =========================
# COMMENTS
# =========================
def result_comment(question: str, winner_html: str) -> str:
    q = (question or "").lower()
    rules: List[Tuple[List[str], List[str]]] = [
        (["мастер отмазок", "отмаз"], [
            f"{winner_html} — тебя выбрали! Как теперь <b>отмазываться</b> будешь? 😂",
            f"{winner_html} победил(а) в номинации <b>«отмаз года»</b>. Покажи класс 😏",
            f"{winner_html}, у нас тут <b>профессионал</b>. Дай пару уроков 🤫",
        ]),
        (["игнор"], [
            f"{winner_html} — чемпион по <b>игнору</b>. Связь пропала 😏",
            f"{winner_html}: «прочитал(а) и исчез(ла)» — <b>классика</b> 🤫",
            f"{winner_html} в игноре так уверенно, будто это <b>спорт</b> 😈",
        ]),
        (["опаздыва", "опоздал"], [
            f"{winner_html} — ты опять <b>в пути</b>? Уже третий год 😏",
            f"{winner_html}: опоздание — это <b>стиль жизни</b> 🤫",
            f"{winner_html} приходит позже всех, зато с <b>эффектом</b> 😈",
        ]),
        (["внимание"], [
            f"{winner_html} — центр внимания по умолчанию 😏",
            f"{winner_html}: без аплодисментов день не считается? 🤫",
            f"{winner_html} любит внимание так, что оно само <b>приходит</b> 😈",
        ]),
    ]
    for keys, variants in rules:
        if any(k in q for k in keys):
            return pick(variants)
    return pick([
        f"{winner_html} — тебя выбрали. <b>Узнаёшь себя?</b> 😏",
        f"{winner_html}, поздравляю: ты сегодня <b>в центре сюжета</b> 😈",
        f"{winner_html} — большинством голосов. <b>Комментарий будет?</b> 🤫",
    ])


def boys_result_comment(question: str, winner_html: str) -> str:
    m: Dict[str, List[str]] = {
        BOYS_ONLY_QUESTIONS[0]: [
            f"{winner_html} — ну ты крыса. Навонял и молчишь 😏",
            f"{winner_html} — запах есть, совести нет 😂",
            f"{winner_html} — оправдывайся. Суд присяжных уже тут 😈",
        ],
        BOYS_ONLY_QUESTIONS[1]: [
            f"{winner_html} — тебе смешно, а людям жить дальше 😂",
            f"{winner_html} — ты реально этим гордишься? 😏",
            f"{winner_html} — ещё раз — и тебя выносят вместе с атмосферой 😈",
        ],
        BOYS_ONLY_QUESTIONS[2]: [
            f"{winner_html} — мебель не виновата. Это ты 😏",
            f"{winner_html} — легенда слабая. Запах сильный 😂",
            f"{winner_html} — фальшивый алиби. Признание принимаем 😈",
        ],
        BOYS_ONLY_QUESTIONS[3]: [
            f"{winner_html} — ну всё, концерт. Или трус 😏",
            f"{winner_html} — давай, без монтажа 😂",
            f"{winner_html} — мы верим в тебя. К сожалению 😈",
        ],
        BOYS_ONLY_QUESTIONS[4]: [
            f"{winner_html} — пьяная мудрость активирована. Ждём цитату 😏",
            f"{winner_html} — сейчас будет «а вот жизнь…» 😂",
            f"{winner_html} — говори. Потом мы это тебе припомним 😈",
        ],
        BOYS_ONLY_QUESTIONS[5]: [
            f"{winner_html} — ночные сообщения — твой спорт? 😏",
            f"{winner_html} — главное потом не делай вид, что «это не я» 😂",
            f"{winner_html} — причина? Давай, удиви нас 😈",
        ],
        BOYS_ONLY_QUESTIONS[6]: [
            f"{winner_html} — «я трезвый» звучит как угроза 😏",
            f"{winner_html} — твой режим “нормальный” длится минуту 😂",
            f"{winner_html} — рассказывай позор. Мы готовы 😈",
        ],
        BOYS_ONLY_QUESTIONS[7]: [
            f"{winner_html} — у тебя талант: кринж находить самому 😏",
            f"{winner_html} — давай историю. Мы хотим страдать 😂",
            f"{winner_html} — рассказывай. И не приукрашивай 😈",
        ],
        BOYS_ONLY_QUESTIONS[8]: [
            f"{winner_html} — “просто посидели” с тобой не бывает 😏",
            f"{winner_html} — ты хаос на ножках 😂",
            f"{winner_html} — объясни механику. Наука требует 😈",
        ],
        BOYS_ONLY_QUESTIONS[9]: [
            f"{winner_html} — уверенность есть, фактов нет 😏",
            f"{winner_html} — скажи ещё раз — почти поверили 😂",
            f"{winner_html} — давай свой “факт”. Мы проверять не будем 😈",
        ],
        BOYS_ONLY_QUESTIONS[10]: [
            f"{winner_html} — понты сгорели, пепел остался 😏",
            f"{winner_html} — рассказывай облом. Смакуем 😂",
            f"{winner_html} — это был сильный выход… в никуда 😈",
        ],
        BOYS_ONLY_QUESTIONS[11]: [
            f"{winner_html} — повод тупой, эмоции максимальные 😏",
            f"{winner_html} — назови повод. Мы оценим уровень идиотизма 😂",
            f"{winner_html} — ты реально заводишься от воздуха? 😈",
        ],
        BOYS_ONLY_QUESTIONS[12]: [
            f"{winner_html} — «по одной» и ушёл в легенды 😏",
            f"{winner_html} — ну давай: где тебя нашли? 😂",
            f"{winner_html} — маршрут пропажи в студию 😈",
        ],
        BOYS_ONLY_QUESTIONS[13]: [
            f"{winner_html} — у тебя в карманах портал? 😏",
            f"{winner_html} — что потерял — самое тупое? Давай 😂",
            f"{winner_html} — ты не теряешь вещи. Ты их освобождаешь 😈",
        ],
        BOYS_ONLY_QUESTIONS[14]: [
            f"{winner_html} — кринж на людях, стыд дома. Классика 😏",
            f"{winner_html} — рассказывай. Мы осудим, но любя 😂",
            f"{winner_html} — давай “стыд на утро”. Без цензуры 😈",
        ],
        BOYS_ONLY_QUESTIONS[15]: [
            f"{winner_html} — «ща сделаю» — и исчез 😏",
            f"{winner_html} — одно обещание. И мы следим 😂",
            f"{winner_html} — давай. Сегодня отвечаешь за слова 😈",
        ],
        BOYS_ONLY_QUESTIONS[16]: [
            f"{winner_html} — держи лицо. 10 секунд. Погнали 😏",
            f"{winner_html} — серьёзность включи. Хоть раз 😂",
            f"{winner_html} — выдержишь — мы тебя простим. Почти 😈",
        ],
        BOYS_ONLY_QUESTIONS[17]: [
            f"{winner_html} — когда тебе скучно, всем страшно 😏",
            f"{winner_html} — расскажи “идею”. Мы заранее против 😂",
            f"{winner_html} — давай, что ты придумал тогда? 😈",
        ],
        BOYS_ONLY_QUESTIONS[18]: [
            f"{winner_html} — фейл на ровном месте — твой стиль 😏",
            f"{winner_html} — давай рекорд. Хотим удивиться 😂",
            f"{winner_html} — рассказывай. И не смягчай 😈",
        ],
        BOYS_ONLY_QUESTIONS[19]: [
            f"{winner_html} — влез и стало хуже. Легенда 😏",
            f"{winner_html} — где ты “помог” так, что лучше бы молчал? 😂",
            f"{winner_html} — признавайся. Мы не забываем 😈",
        ],
    }
    if question in m:
        return random.choice(m[question])
    return random.choice([
        f"{winner_html} — ну всё, тебя выбрали. Давай без задней 😏",
        f"{winner_html} — компания решила. И это приговор 😂",
        f"{winner_html} — сегодня ты главный герой. Соболезную 😈",
    ])


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
        b.button(text=f"⭐ {amt}", callback_data=f"donate_amount:{amt}")
    b.button(text="⬅️ Назад", callback_data="dm_back")
    b.adjust(3, 2, 2, 1)
    return b.as_markup()


def kb_dm_donate_confirm(amount: int):
    b = InlineKeyboardBuilder()
    b.button(text=f"✅ Оплатить ⭐ {amount}", callback_data=f"donate_pay:{amount}")
    b.button(text="⬅️ Назад", callback_data="dm_donate")
    b.adjust(1, 1)
    return b.as_markup()


def kb_group_lobby(gs: GameState):
    t = gs.lobby_token
    b = InlineKeyboardBuilder()

    if gs.mode == "all":
        b.button(text="🔥 Для всех ✓", callback_data=f"mode_all:{t}")
        b.button(text="😈 Только пацаны", callback_data=f"mode_boys:{t}")
    else:
        b.button(text="🔥 Для всех", callback_data=f"mode_all:{t}")
        b.button(text="😈 Только пацаны ✓", callback_data=f"mode_boys:{t}")

    b.button(text="✅ Присоединиться", callback_data=f"join:{t}")
    b.button(text="🔥 Погнали", callback_data=f"start:{t}")
    b.button(text="Отмена", callback_data=f"cancel:{t}")

    b.adjust(2, 1, 1, 1)
    return b.as_markup()


def kb_vote(gs: GameState, token: int):
    b = InlineKeyboardBuilder()
    targets = [(uid, gs.players[uid]) for uid in gs.round_targets if uid in gs.players]
    targets.sort(key=lambda x: x[1].label.lower())

    for uid, p in targets:
        b.button(text=p.label, callback_data=f"vote:{token}:{uid}")

    cols = 2 if len(targets) <= 6 else 3
    if targets:
        b.adjust(*([cols] * ((len(targets) + cols - 1) // cols)))

    b.row()
    b.button(text="Завершить игру", callback_data="end_req")
    b.adjust(1)
    return b.as_markup()


def kb_result(token: int):
    b = InlineKeyboardBuilder()
    b.button(text="👉 Следующий вопросик", callback_data=f"next:{token}")
    b.button(text="Завершить игру", callback_data="end_req")
    b.adjust(1, 1)
    return b.as_markup()


def kb_not_all_voted(token: int):
    b = InlineKeyboardBuilder()
    b.button(text=f"⏳ +{EXTEND_SECONDS} секунд", callback_data=f"extend:{token}")
    b.button(text="😈 Не ждём опоздавших", callback_data=f"force_result:{token}")
    b.button(text="Завершить игру", callback_data="end_req")
    b.adjust(1, 1, 1)
    return b.as_markup()


def kb_end_confirm():
    b = InlineKeyboardBuilder()
    b.button(text="✅ Да, завершить", callback_data="end_yes")
    b.button(text="⬅️ Нет", callback_data="end_no")
    b.adjust(1, 1)
    return b.as_markup()


# =========================
# LOBBY RENDER / UPDATE
# =========================
def lobby_text(gs: GameState) -> str:
    players = [gs.players[uid].label for uid in gs.join_order if uid in gs.players]
    players_block = "\n".join([f"• {h(x)}" for x in players]) if players else "Пока никого."

    if gs.mode == "boys":
        mode_line = "😈 <b>Режим:</b> только пацаны"
        hint = "Нужен другой — жми режим ниже.\nЕсли этот — жми <b>«Присоединиться»</b>."
    else:
        mode_line = "🔥 <b>Режим:</b> для всех"
        hint = "Хочешь другой — жми режим ниже.\nЕсли этот — жми <b>«Присоединиться»</b>."

    return (
        "<b>МЕЖДУ НАМИ</b> 🤫\n\n"
        f"{mode_line}\n"
        f"{hint}\n\n"
        f"<b>В игре:</b>\n{players_block}\n\n"
        "<b>Ведущий</b> — кто начал 😏"
    )


async def lobby_upsert(gs: GameState):
    text = lobby_text(gs)

    if gs.lobby_msg_id:
        try:
            await bot.edit_message_text(
                chat_id=gs.chat_id,
                message_id=gs.lobby_msg_id,
                text=text,
                reply_markup=kb_group_lobby(gs),
                parse_mode="HTML",
            )
            return
        except Exception:
            pass

    old_id = gs.lobby_msg_id
    gs.lobby_token = max(gs.lobby_token + 1, 1)

    m = await bot.send_message(gs.chat_id, text, reply_markup=kb_group_lobby(gs), parse_mode="HTML")
    gs.lobby_msg_id = m.message_id

    if old_id and old_id != gs.lobby_msg_id:
        try:
            await bot.delete_message(gs.chat_id, old_id)
        except Exception:
            pass


async def ensure_lobby_fresh(cb: CallbackQuery, gs: GameState) -> bool:
    tok = parse_tail_int(cb.data or "")
    if tok is None:
        await cb.answer("Криво нажалось 🤨")
        return False
    if tok != gs.lobby_token:
        await cb.answer("Это старое меню 😏 Смотри ниже.", show_alert=False)
        try:
            await cb.message.delete()
        except Exception:
            pass
        await lobby_upsert(gs)
        return False
    return True


async def stale_lobby(cb: CallbackQuery):
    await cb.answer("Это старое меню 😏 Напиши «Начать игру».", show_alert=True)
    try:
        await cb.message.delete()
    except Exception:
        pass


# =========================
# CLEANUP / WATCHDOG / REMINDER
# =========================
async def cleanup_game(gs: GameState):
    gs.ended = True

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

    await safe_clear_markup(gs.chat_id, gs.round_msg_id)
    await safe_clear_markup(gs.chat_id, gs.lobby_msg_id)

    gs.round_msg_id = None


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
                        "Эй 😏\n<b>Три дня тишины</b>…\n"
                        "Может, снова сыграем в <b>«Между нами 🤫»</b>?\n\n"
                        "Напишите: <b>«Начать игру»</b> 👇",
                        parse_mode="HTML",
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


async def watchdog(chat_id: int):
    while True:
        await asyncio.sleep(10)
        gs = GAMES.get(chat_id)
        if not gs or gs.ended:
            return

        idle_sec = (datetime.utcnow() - gs.last_activity).total_seconds()

        if gs.state == State.LOBBY and idle_sec >= LOBBY_CLOSE_SEC:
            await cleanup_game(gs)
            GAMES.pop(chat_id, None)
            try:
                await bot.send_message(
                    chat_id,
                    "Лобби протухло 🫠\n<b>5 минут тишины</b> — закрываю сбор.\n\n"
                    "Хотите снова — напишите <b>«Начать игру»</b> 😏",
                    parse_mode="HTML",
                )
            except Exception:
                pass
            return

        if gs.state != State.IDLE and idle_sec >= SESSION_CLOSE_SEC:
            await end_game(chat_id, reason=random.choice(INACTIVE_END_VARIANTS))
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
    if not gs or gs.state != State.RUNNING or gs.ended:
        return

    if len(gs.players) < MIN_PLAYERS:
        await bot.send_message(
            chat_id,
            "Для игры нужно <b>минимум двое</b>.\nВсе разошлись? Я тоже 😏",
            parse_mode="HTML",
        )
        await end_game(chat_id)
        return

    touch(gs)

    await safe_clear_markup(chat_id, gs.round_msg_id)
    gs.round_msg_id = None

    gs.awaiting_next = False
    gs.extended_prompted = False
    gs.extend_used = False

    if gs.extend_prompt_msg_id:
        try:
            await bot.delete_message(chat_id, gs.extend_prompt_msg_id)
        except Exception:
            pass
        gs.extend_prompt_msg_id = None

    gs.round += 1
    stats_inc("rounds_played", 1)

    gs.votes_by_target.clear()
    gs.voted_users.clear()
    gs.total_votes = 0

    snapshot_ids = [uid for uid in gs.join_order if uid in gs.players]
    gs.round_voters = set(snapshot_ids)
    gs.round_targets = snapshot_ids[:]

    if gs.mode == "boys":
        q = pick_from_pool(gs.used_boys, BOYS_ONLY_QUESTIONS)
        is_spicy = False
        has_secret = False
    else:
        q, is_spicy, has_secret = choose_question(gs)

    gs.current_question = q

    q_head, q_action = split_question_action(q)
    q_head_caps = q_head.upper()
    action_line = f"\n\n<i>{h(q_action)}</i>" if q_action else ""

    tags = []
    if has_secret:
        tags.append("Только честно 🤫")
    if is_spicy:
        tags.append("Отвечайте честно 😈")
    tag_line = f"\n\n<i>{h(' · '.join(tags))}</i>" if tags else ""
    timer_line = f"\n\n<i>({ROUND_VOTE_SECONDS} сек на голосование)</i>"

    mode_line = "😈 <b>ТОЛЬКО ПАЦАНЫ</b>\n\n" if gs.mode == "boys" else ""

    text = (
        f"<b>РАУНД {gs.round} 😈</b>\n\n"
        f"{mode_line}"
        f"<b>{h(q_head_caps)}</b>"
        f"{action_line}"
        f"{tag_line}"
        f"{timer_line}\n\n"
        f"<b>Голосуйте</b> 👇"
    )

    gs.round_token += 1
    token = gs.round_token

    if gs.round_timer_task and not gs.round_timer_task.done():
        gs.round_timer_task.cancel()

    m = await bot.send_message(chat_id, text, reply_markup=kb_vote(gs, token), parse_mode="HTML")
    gs.round_msg_id = m.message_id

    gs.round_timer_task = asyncio.create_task(round_timer(chat_id, ROUND_VOTE_SECONDS, token))


async def round_timer(chat_id: int, seconds: int, token: int):
    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        return

    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.RUNNING or gs.ended:
        return
    if token != gs.round_token or gs.awaiting_next:
        return

    not_all_voted = len(gs.voted_users) < len(gs.round_voters)

    if not gs.extended_prompted and (not_all_voted or gs.total_votes == 0):
        gs.extended_prompted = True
        touch(gs)

        missing = len(gs.round_voters) - len(gs.voted_users)
        msg = random.choice(TIMEUP_NO_VOTES) if gs.total_votes == 0 else random.choice(TIMEUP_MISSING).format(missing=missing)

        m = await bot.send_message(
            chat_id,
            msg + f"\n\nДадим ещё <b>{EXTEND_SECONDS} секунд</b>?\n<b>Только ведущий</b> может продлить 😏",
            reply_markup=kb_not_all_voted(token),
            parse_mode="HTML",
        )
        gs.extend_prompt_msg_id = m.message_id
        return

    await show_round_result(chat_id, token)


async def show_round_result(chat_id: int, token: int):
    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.RUNNING or gs.ended:
        return
    if token != gs.round_token or gs.awaiting_next:
        return

    gs.awaiting_next = True
    touch(gs)

    if gs.round_timer_task and not gs.round_timer_task.done():
        gs.round_timer_task.cancel()

    if gs.extend_prompt_msg_id:
        try:
            await bot.delete_message(chat_id, gs.extend_prompt_msg_id)
        except Exception:
            pass
        gs.extend_prompt_msg_id = None

    await safe_clear_markup(chat_id, gs.round_msg_id)
    gs.round_msg_id = None

    if gs.total_votes == 0:
        await bot.send_message(
            chat_id,
            f"<b>ИТОГ РАУНДА {gs.round}:</b>\nНикого не выбрали.\nСлишком мирно… подозрительно 🤨",
            reply_markup=kb_result(token),
            parse_mode="HTML",
        )
        return

    items = sorted(gs.votes_by_target.items(), key=lambda x: x[1], reverse=True)
    top_uid, top_count = items[0]
    top_all = [uid for uid, c in items if c == top_count]

    lines = [f"<b>ИТОГ РАУНДА {gs.round}:</b>"]
    for uid, c in items:
        if c <= 0:
            continue
        p = gs.players.get(uid)
        if p:
            lines.append(f"— <b>{h(p.label)}</b>: {c}")
    lines.append("")

    if len(top_all) == 1 and top_uid in gs.players:
        winner = gs.players[top_uid].label
        winner_html = f"<b>{h(winner)}</b>"
        lines.append(f"<b>Большинство:</b> {h(winner)}")
        if gs.mode == "boys":
            lines.append(boys_result_comment(gs.current_question, winner_html))
        else:
            lines.append(result_comment(gs.current_question, winner_html))
    else:
        names = ", ".join([gs.players[uid].label for uid in top_all if uid in gs.players])
        lines.append(f"<b>Ничья:</b> {h(names)}")
        lines.append("Красиво разошлись. Но я всё равно <b>запомнил</b> 😏")

    await bot.send_message(chat_id, "\n".join(lines), reply_markup=kb_result(token), parse_mode="HTML")


async def end_game(chat_id: int, reason: str = ""):
    gs = GAMES.get(chat_id)
    if not gs:
        return

    await cleanup_game(gs)
    GAMES.pop(chat_id, None)

    tail = random.choice(END_VARIANTS)
    text = f"{reason}\n\n{tail}" if reason else tail
    await bot.send_message(chat_id, text, parse_mode="HTML")


# =========================
# DM
# =========================
@dp.message(CommandStart())
async def cmd_start(message: Message):
    stats_touch_user(message.from_user.id)

    if message.chat.type == "private":
        text = (
            "Привет 😏\n\n"
            f"{random.choice(DM_WELCOME_VARIANTS)}\n\n"
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
        "Я тут 😏\nЧтобы начать — напишите: <b>Начать игру</b>\n/help — правила",
        parse_mode="HTML",
    )


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
# HELP
# =========================
@dp.message(Command("help"))
async def cmd_help(message: Message):
    stats_touch_user(message.from_user.id)
    await message.answer(
        "<b>Как играем:</b>\n"
        "1) В группе: <b>Начать игру</b>\n"
        "2) Все: <b>Присоединиться</b>\n"
        "3) Ведущий: <b>Погнали</b>\n"
        "4) <b>Вопрос → 15 сек → итог → следующий</b>\n\n"
        "<b>Правила:</b>\n"
        "— За себя нельзя 😈\n"
        "— Продление: <b>только ведущий</b>\n"
        "— Лобби тухнет через <b>5 минут</b>\n"
        "— Игра закрывается через <b>10 минут тишины</b>\n\n"
        "Это между нами 🤫",
        parse_mode="HTML",
    )


# =========================
# GROUP FLOW
# =========================
@dp.message(F.text.casefold() == "начать игру")
async def start_lobby(message: Message):
    stats_touch_user(message.from_user.id)
    stats_touch_chat(message.chat.id)

    chat_id = message.chat.id
    gs = GAMES.get(chat_id)
    if gs and gs.state in {State.LOBBY, State.RUNNING} and not gs.ended:
        await message.answer("Игра уже идёт 😏\nЖмите кнопки под сообщениями.")
        return

    gs = GameState(chat_id=chat_id, state=State.LOBBY, host_user_id=message.from_user.id)
    gs.lobby_token = 1
    GAMES[chat_id] = gs

    touch(gs)
    ensure_watchdog(gs)
    await lobby_upsert(gs)


@dp.callback_query(F.data.startswith("mode_all:"))
async def cb_mode_all(cb: CallbackQuery):
    gs = GAMES.get(cb.message.chat.id)

    # ✅ FIX: после завершения — это старое меню, а не “поздно менять”
    if not gs or gs.ended:
        await stale_lobby(cb)
        return

    if gs.state != State.LOBBY:
        await cb.answer("Режим меняется в лобби 😏", show_alert=True)
        return

    if not await ensure_lobby_fresh(cb, gs):
        return

    if gs.mode == "all":
        await cb.answer("Уже для всех ✓")
        return

    gs.mode = "all"
    touch(gs)
    await cb.answer("Ок 🔥 Для всех")
    await lobby_upsert(gs)


@dp.callback_query(F.data.startswith("mode_boys:"))
async def cb_mode_boys(cb: CallbackQuery):
    gs = GAMES.get(cb.message.chat.id)

    # ✅ FIX: после завершения — это старое меню, а не “поздно менять”
    if not gs or gs.ended:
        await stale_lobby(cb)
        return

    if gs.state != State.LOBBY:
        await cb.answer("Режим меняется в лобби 😏", show_alert=True)
        return

    if not await ensure_lobby_fresh(cb, gs):
        return

    if gs.mode == "boys":
        await cb.answer("Уже только пацаны ✓")
        return

    gs.mode = "boys"
    touch(gs)
    await cb.answer("Ок 😈 Только пацаны")
    await lobby_upsert(gs)


@dp.callback_query(F.data.startswith("cancel:"))
async def cb_cancel(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs:
        await cb.answer("Ок 😏")
        return

    if gs.state == State.LOBBY:
        if not await ensure_lobby_fresh(cb, gs):
            return

    await cleanup_game(gs)
    GAMES.pop(chat_id, None)

    await cb.answer("Ок")
    try:
        await cb.message.edit_text("Отмена 😏\n<b>Интрига остаётся.</b>", parse_mode="HTML")
    except Exception:
        await cb.message.answer("Отмена 😏\n<b>Интрига остаётся.</b>", parse_mode="HTML")


@dp.callback_query(F.data.startswith("join:"))
async def cb_join(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)

    if not gs or gs.ended or gs.state not in (State.LOBBY, State.RUNNING):
        await cb.answer("Сессии нет 😏 Напиши «Начать игру».", show_alert=True)
        return

    if gs.state == State.LOBBY:
        if not await ensure_lobby_fresh(cb, gs):
            return

    stats_touch_user(cb.from_user.id)
    stats_touch_chat(chat_id)
    touch(gs)
    ensure_watchdog(gs)

    uid = cb.from_user.id
    if uid in gs.players:
        await cb.answer("Ты уже в игре 😏")
        if gs.state == State.LOBBY:
            await lobby_upsert(gs)
        return

    if len(gs.players) >= MAX_PLAYERS:
        await cb.answer("Уже 10 игроков 😈", show_alert=True)
        return

    label = make_label(gs, cb.from_user)
    gs.players[uid] = Player(user_id=uid, label=label)
    gs.join_order.append(uid)

    if gs.state == State.RUNNING:
        await cb.answer("Ок ✅ Со следующего раунда ты в деле 😈")
        return

    await cb.answer("Записал ✅")
    await lobby_upsert(gs)


@dp.callback_query(F.data.startswith("start:"))
async def cb_start(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.LOBBY or gs.ended:
        await cb.answer("Это уже не лобби 😏", show_alert=False)
        return

    if not await ensure_lobby_fresh(cb, gs):
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

    chats_store_mark_game_started(chat_id)
    stats_inc("games_started", 1)

    await cb.answer("Погнали 😈")
    await safe_clear_markup(chat_id, gs.lobby_msg_id)
    await start_round(chat_id)


# =========================
# VOTE / EXTEND / FORCE / NEXT
# =========================
@dp.callback_query(F.data.startswith("vote:"))
async def cb_vote(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.RUNNING or gs.ended:
        await cb.answer("Игра уже закрыта 😏", show_alert=True)
        return

    try:
        _, tok_s, uid_s = (cb.data or "").split(":", 2)
        token = int(tok_s)
        target_id = int(uid_s)
    except Exception:
        await cb.answer("Кривой голос 🤨")
        return

    if token != gs.round_token or cb.message.message_id != gs.round_msg_id:
        await cb.answer("Поздно 😏 Это был прошлый раунд.", show_alert=False)
        return

    touch(gs)

    voter_id = cb.from_user.id
    if voter_id not in gs.round_voters:
        await cb.answer("Ты не в этом раунде 😏", show_alert=True)
        return
    if voter_id in gs.voted_users:
        await cb.answer(pick(ALREADY_VOTED_TOASTS))
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
        await show_round_result(chat_id, gs.round_token)


@dp.callback_query(F.data.startswith("extend:"))
async def cb_extend(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.RUNNING or gs.ended:
        await cb.answer("Уже поздно 😏")
        return

    token = parse_tail_int(cb.data or "")
    if token is None:
        await cb.answer("Криво нажалось 🤨")
        return

    if token != gs.round_token or cb.message.message_id != gs.extend_prompt_msg_id:
        await cb.answer("Поздно 😏 Уже другой движ.", show_alert=False)
        return

    host = get_host(gs)
    if host is not None and cb.from_user.id != host:
        await cb.answer("Продлить может только ведущий 😏", show_alert=True)
        return

    if gs.awaiting_next:
        await cb.answer("Поздно. Уже считаю 😈")
        return

    if gs.extend_used:
        await cb.answer("Уже продлили 😏")
        return

    gs.extend_used = True
    touch(gs)
    await cb.answer(f"+{EXTEND_SECONDS} сек 😏")

    if gs.round_timer_task and not gs.round_timer_task.done():
        gs.round_timer_task.cancel()
    gs.round_timer_task = asyncio.create_task(round_timer(chat_id, EXTEND_SECONDS, gs.round_token))

    try:
        await cb.message.delete()
    except Exception:
        pass
    gs.extend_prompt_msg_id = None


@dp.callback_query(F.data.startswith("force_result:"))
async def cb_force_result(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.RUNNING or gs.ended:
        await cb.answer("Уже поздно 😏")
        return

    token = parse_tail_int(cb.data or "")
    if token is None:
        await cb.answer("Криво нажалось 🤨")
        return

    if token != gs.round_token or cb.message.message_id != gs.extend_prompt_msg_id:
        await cb.answer("Поздно 😏 Это было про прошлый раунд.", show_alert=False)
        return

    host = get_host(gs)
    if host is not None and cb.from_user.id != host:
        await cb.answer("Только ведущий может не ждать 😏", show_alert=True)
        return

    touch(gs)
    await cb.answer("Ок. Не ждём 😈")

    if gs.round_timer_task and not gs.round_timer_task.done():
        gs.round_timer_task.cancel()

    try:
        await cb.message.delete()
    except Exception:
        pass
    gs.extend_prompt_msg_id = None

    await show_round_result(chat_id, gs.round_token)


@dp.callback_query(F.data.startswith("next:"))
async def cb_next(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    gs = GAMES.get(chat_id)
    if not gs or gs.state != State.RUNNING or gs.ended:
        await cb.answer("Игра уже закрыта 😏", show_alert=True)
        return

    token = parse_tail_int(cb.data or "")
    if token is None:
        await cb.answer("Криво нажалось 🤨")
        return

    if token != gs.round_token:
        await cb.answer("Поздно 😏 Это был прошлый раунд.", show_alert=False)
        return

    if not anti_spam_next_ok(gs, cb.from_user.id):
        await cb.answer("Тише-тише 😏")
        return

    if not gs.awaiting_next:
        await cb.answer("Сначала итог 😈")
        return

    await cb.answer(pick(NEXT_TOASTS))
    await start_round(chat_id)


# =========================
# END CONFIRM FLOW
# =========================
@dp.callback_query(F.data == "end_req")
async def cb_end_req(cb: CallbackQuery):
    gs = GAMES.get(cb.message.chat.id)
    if not gs or gs.ended:
        await cb.answer("Ок 😏")
        return
    await cb.answer("Точно? 😏")
    await bot.send_message(
        cb.message.chat.id,
        "Точно <b>завершить игру</b>?",
        reply_markup=kb_end_confirm(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "end_no")
async def cb_end_no(cb: CallbackQuery):
    await cb.answer("Ок 😏")
    try:
        await cb.message.delete()
    except Exception:
        pass


@dp.callback_query(F.data == "end_yes")
async def cb_end_yes(cb: CallbackQuery):
    await cb.answer("Ладно.")
    try:
        await cb.message.delete()
    except Exception:
        pass
    await end_game(cb.message.chat.id)


# =========================
# BOT ADDED TO GROUP (once)
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
            "Это <b>«Между нами 🤫»</b>.\n\n"
            "Чтобы начать — напишите:\n"
            "<b>Начать игру</b> 😈\n\n"
            "/help — правила",
            parse_mode="HTML",
        )
        chats_store_mark_welcome(chat.id)
    except Exception:
        return


# =========================
# SUGGESTIONS
# =========================
@dp.message(Command("suggest"))
async def cmd_suggest(message: Message):
    stats_touch_user(message.from_user.id)

    text = (message.text or "").strip()
    parts = text.split(maxsplit=1)
    suggestion = parts[1].strip() if len(parts) > 1 else ""

    if not suggestion or len(suggestion) < 10:
        await message.answer("Коротко слишком 😏\nПример:\n/suggest Кто из вас чаще всего…?")
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
        "Ок 😈 <b>Записал</b>.\nЕсли вопрос <b>годный</b> — добавим и будем палить вас им 🤫",
        parse_mode="HTML",
    )

    if ADMIN_IDS:
        preview = suggestion if len(suggestion) <= 350 else suggestion[:350] + "…"
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    "💡 <b>Новый предложенный вопрос:</b>\n"
                    f"{h(preview)}\n\n"
                    f"От: {message.from_user.id} (@{h(message.from_user.username or '')})",
                    parse_mode="HTML",
                )
            except Exception:
                pass


# =========================
# STATS (admin)
# =========================
@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    if ADMIN_IDS and message.from_user.id not in ADMIN_IDS:
        await message.answer("Не, это не для тебя 😏")
        return

    stats_init()
    s = _read_json(STATS_PATH, {})
    await message.answer(
        "<b>📊 Статистика:</b>\n\n"
        f"👤 <b>Уник. пользователей:</b> {s.get('users_unique', 0)}\n"
        f"💬 <b>Уник. чатов:</b> {s.get('chats_unique', 0)}\n"
        f"🎮 <b>Игр стартовало:</b> {s.get('games_started', 0)}\n"
        f"🌀 <b>Раундов сыграно:</b> {s.get('rounds_played', 0)}\n"
        f"🗳 <b>Голосов:</b> {s.get('votes_cast', 0)}\n"
        f"⭐ <b>Stars:</b> {s.get('donations_stars_total', 0)} / {s.get('donations_count', 0)} платежей\n"
        f"💡 <b>Предложений:</b> {s.get('suggestions_count', 0)}",
        parse_mode="HTML",
    )


# =========================
# DONATE (Stars) — без тупиков
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


@dp.callback_query(F.data.startswith("donate_amount:"))
async def cb_donate_amount(cb: CallbackQuery):
    await cb.answer()
    try:
        amount = int((cb.data or "").split(":", 1)[1])
    except Exception:
        await cb.message.answer("Что-то пошло не так 😏")
        return
    if amount <= 0:
        await cb.message.answer("Слишком хитро 😈")
        return

    text = (
        f"*Поддержка Stars* ⭐\n\n"
        f"Сумма: *⭐ {amount}*\n\n"
        "Нажмёшь оплатить — откроется Telegram-оплата.\n"
        "Передумал? Назад 😏"
    )
    await dm_edit_menu(cb, text, kb_dm_donate_confirm(amount))


@dp.callback_query(F.data.startswith("donate_pay:"))
async def cb_donate_pay(cb: CallbackQuery):
    await cb.answer()
    try:
        amount = int((cb.data or "").split(":", 1)[1])
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
        f"<b>Принято</b> ⭐ {stars}\n"
        "Спасибо 😏\n"
        "Мы это превратим в <b>ещё более колкие вопросы</b> 😈",
        parse_mode="HTML",
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
