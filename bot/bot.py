"""
Лумена Бот — полнофункциональный Telegram бот
Версия 6.0
"""
import asyncio
import html
import json
import logging
import math
import os
import random
import re
import string
import uuid
from datetime import datetime, timedelta, date, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc   # используется в restrict_chat_member until_date

KYIV_TZ = ZoneInfo("Europe/Kyiv")

def now_kyiv() -> datetime:
    return datetime.now(KYIV_TZ)

def today_kyiv() -> date:
    return now_kyiv().date()

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    Message, ChatPermissions, MessageReactionUpdated,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    ChatMemberUpdated,
    BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats,
    BotCommandScopeDefault,
    InputMediaPhoto, InputMediaVideo,
    LabeledPrice, MessageEntity,
)
from aiogram.enums import ChatMemberStatus

from lumena import get_lumena_response
import anketa as _ank
import ai_agent
import brand
import db as _db

_edit_sessions:     dict[int, str]  = {}
_btn_edit_sessions: dict[int, dict] = {}
_style_edit_sessions: dict[int, str] = {}
_tracked_bot_msgs:  dict[tuple[int, int], str] = {}

# ═══════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не найден BOT_TOKEN!")

OWNER_USERNAME = "hdrttttttt"
OWNER_ID       = 8655306548
SUPER_IDS      = {OWNER_ID}
BOT_VERSION = "7.0"
DATA_FILE = "data/bot_data.json"

LUMENA_SITE_URL: str = os.environ.get("LUMENA_SITE_URL", "")
CASINO_BOT_URL = "https://t.me/LumenarAi_Bot"
LMN_BALANCE_RESET_TARGET = 7_000_000_000
LMN_BALANCE_RESET_VERSION = 3  # v3: компенсация 7 млрд всем пользователям
LMN_TRANSFER_VERSION = 2  # перевод всех балансов фаундеру

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ═══════════════════════════════════════════════════════
# ХРАНИЛИЩА ДАННЫХ
# ═══════════════════════════════════════════════════════
warnings_db = {}
ru_army_warns = {}
marriages = {}
marriage_proposals = {}
marriage_dates: dict[str, str] = {}  # "min_uid_max_uid" → ISO date свадьбы
streaks = {}
lmn_balances = {}
reputation = {}
work_cooldown = {}
fish_cooldown = {}
rob_cooldown = {}
hunt_cooldown = {}
alchemy_cooldown = {}
# {canonical_chat_id: {"date": "YYYY-MM-DD", "participants": {uid: name},
#                       "completed": bool}}
team_alchemy_runs = {}
bank_balances = {}        # {user_id: int} — гроші в банку (захищені від /rob)
bank_withdraw_cd = {}     # {user_id: datetime} — кулдаун виведення з банку
chat_rules = {}
hangman_games = {}
roulette_players = {}
profiles = {}
chat_members = {}
support_sessions = {}
_active_rain: dict = {}
_last_rain_time: float = 0.0

_link_guard:       dict[int, bool]        = {}
pending_notifications: list[dict] = []  # [{chat_id, text, parse_mode}] — одноразовые сообщения при старте
_link_guard_warns: dict[int, dict]        = {}
_link_whitelist:   dict[int, list[str]]   = {}
_premium_users:  set = set()
_verified_users: set = set()

aura:              dict[int, float] = {}
_aura_credited:    set              = set()
_msg_authors:      dict             = {}

_ECON_CANONICAL: dict[int, int] = {}

ANKETA_PREMIUM_STARS = 300
ROLES: dict[int, str] = {}
ROLE_NAMES: dict[str, str] = {
    "lead_admin":  "Lead Admin",
    "co_admin":    "Co-Admin",
    "admin":       "Admin",
    "moderator":   "Moderator",
    "vip":         "VIP",
}
ROLE_HIERARCHY = ["lead_admin", "co_admin", "admin", "moderator"]
_ROLE_USERNAMES: dict[str, str] = {
    "veroniksssxa": "lead_admin",
}
_PREMIUM_ALWAYS = {"hdrttttttt", "veroniksssxa"}

# ── Кастомные права мута ──────────────────────────────────────
# Эти пользователи могут мутить ТОЛЬКО юзеров из _MUTE_TARGETS
_CUSTOM_MUTERS: set[str] = {"egamaster", "not_persons", "skes1m"}
# Пользователей из этого списка могут мутить _CUSTOM_MUTERS (и, конечно, фаундер + lead_admin)
_MUTE_TARGETS:  set[str] = {"vladmish11", "ne_opoznaii", "zxceblanxa"}

_BOT_ID: int = 0
_BOT_USERNAME: str = ""
_state_save_task: asyncio.Task | None = None
_save_update_sent: bool = False
lmn_balance_reset_version = 0
lmn_transfer_version = 0

# ── V6 хранилища ──────────────────────────────────────
user_xp:           dict[int, int]  = {}   # uid → XP
user_messages:     dict[int, dict] = {}   # chat_id → {uid: count}
daily_cooldown:    dict[int, str]  = {}   # uid → ISO-дата последнего дейли
user_achievements: dict[int, list] = {}   # uid → [achievement_id, ...]
mod_logs:          dict[int, list] = {}   # chat_id → [{action,uid,by,ts}]
reports_db:        dict[int, list] = {}   # chat_id → [{from_uid,target_uid,reason,ts}]
referrals:         dict[int, int]  = {}   # uid → referrer_uid
referral_counts:   dict[int, int]  = {}   # uid → кол-во приглашённых
raid_mode:         dict[int, bool] = {}   # chat_id → bool
antispam_mode:     dict[int, bool] = {}   # chat_id → bool
antispam_tracker:  dict[int, dict] = {}   # chat_id → {uid: {hash,count,ts}}
rep_votes:         dict[tuple, int] = {}  # (chat_id,voter_uid,target_uid) → +1/-1
report_cooldown:   dict[tuple, str] = {}  # (chat_id,from_uid,target_uid) → ISO date
_games_played:     dict[int, int]  = {}   # uid → кол-во игр
_games_won:        dict[int, int]  = {}   # uid → кол-во побед
v6_announced:      bool            = False
bonus_weekly_cd:   dict[int, str]  = {}   # uid → "YYYY-Www" (ISO week claim)
daily_games:       dict[int, str]  = {}   # uid → ISO date последней сыгранной игры
daily_msg_cnt:     dict[int, dict] = {}   # uid → {"date": ISO, "count": int} — сообщения за сегодня
tasks_bonus_cd:    dict[int, str]  = {}   # uid → ISO date: когда получен бонус за все задания
_crash_games:      dict[int, dict] = {}   # uid → crash game state
_bj_games:         dict[int, dict] = {}   # uid → blackjack state
_mines_games:      dict[int, dict] = {}   # uid → mines state

# ── XP / уровни ───────────────────────────────────────
XP_LEVELS = [
    (0,    "🆕 Новичок"),
    (100,  "📗 Участник"),
    (500,  "⚡ Активный"),
    (1500, "🔥 Опытный"),
    (3500, "💎 Ветеран"),
    (7000, "👑 Легенда"),
]

def get_xp_level(xp: int) -> tuple[str, int, int]:
    """(название_уровня, старт_текущего, старт_следующего)."""
    level_name, prev, nxt = XP_LEVELS[0][1], 0, XP_LEVELS[1][0]
    for i, (thr, name) in enumerate(XP_LEVELS):
        if xp >= thr:
            level_name = name
            prev = thr
            nxt = XP_LEVELS[i + 1][0] if i + 1 < len(XP_LEVELS) else thr
    return level_name, prev, nxt

def xp_bar(xp: int) -> str:
    _, start, end = get_xp_level(xp)
    if end <= start:
        return "██████████ MAX"
    pct = min(1.0, (xp - start) / (end - start))
    filled = int(pct * 10)
    return "█" * filled + "░" * (10 - filled) + f" {int(pct*100)}%"

def award_xp(uid: int, amount: int) -> bool:
    """Начисляет XP. Возвращает True если уровень повысился."""
    before_name = get_xp_level(user_xp.get(uid, 0))[0]
    user_xp[uid] = user_xp.get(uid, 0) + amount
    after_name = get_xp_level(user_xp[uid])[0]
    _check_achievements(uid)
    return before_name != after_name

def _check_achievements(uid: int):
    earned = set(user_achievements.get(uid, []))
    xp  = user_xp.get(uid, 0)
    bal = lmn_balances.get(uid, 0) + bank_balances.get(uid, 0)
    played = _games_played.get(uid, 0)
    won    = _games_won.get(uid, 0)
    checks = {
        "first_100xp": xp >= 100,
        "xp_1500":     xp >= 1500,
        "legend":      xp >= 7000,
        "rich_1m":     bal >= 1_000_000,
        "rich_1b":     bal >= 1_000_000_000,
        "gambler":     played >= 1,
        "winner":      won >= 5,
    }
    for ach_id, cond in checks.items():
        if cond:
            earned.add(ach_id)
    user_achievements[uid] = list(earned)

ACHIEVEMENT_INFO: dict[str, tuple[str, str, str]] = {
    "first_message": ("💬", "Первое слово",      "Написал первое сообщение в чате"),
    "first_100xp":   ("⚡", "Искра",             "Набрал 100 XP"),
    "xp_1500":       ("🔥", "Опытный боец",      "Набрал 1500 XP"),
    "legend":        ("👑", "Легенда",            "Достиг 7000 XP — максимальный уровень"),
    "streak_7":      ("🗓", "Неделя подряд",     "Стрик 7 дней"),
    "streak_30":     ("📅", "Месяц подряд",      "Стрик 30 дней"),
    "married":       ("💍", "Женаты!",           "Вступил в брак"),
    "rich_1m":       ("💸", "Миллионер",         "Накопил 1 000 000 LMN"),
    "rich_1b":       ("💎", "Миллиардер",        "Накопил 1 000 000 000 LMN"),
    "gambler":       ("🎰", "Игрок",             "Сыграл первую игру"),
    "winner":        ("🏆", "Победитель",        "Выиграл 5 игр"),
}

def _log_mod(chat_id: int, action: str, uid: int, by: int):
    """Записывает действие модерации в лог чата."""
    mod_logs.setdefault(chat_id, [])
    mod_logs[chat_id].append({
        "action": action, "uid": uid, "by": by,
        "ts": now_kyiv().strftime("%d.%m %H:%M"),
    })
    if len(mod_logs[chat_id]) > 100:
        mod_logs[chat_id] = mod_logs[chat_id][-100:]

# ═══════════════════════════════════════════════════════
# ПЕРСИСТЕНТНОСТЬ ДАННЫХ
# ═══════════════════════════════════════════════════════

def _build_main_payload() -> dict:
    """Будує словник з усіма даними бота для збереження."""
    streaks_serial: dict = {}
    for cid, users in streaks.items():
        streaks_serial[str(cid)] = {}
        for uid, d in users.items():
            streaks_serial[str(cid)][str(uid)] = {
                "count": d.get("count", 0),
                "last": d["last"].isoformat() if d.get("last") else None,
            }
    return {
        "marriages":    {str(c): {str(u): v for u, v in m.items()} for c, m in marriages.items()},
        "streaks":      streaks_serial,
        "lmn_balances": {str(u): b for u, b in lmn_balances.items()},
        "lmn_balance_reset_version": lmn_balance_reset_version,
        "lmn_transfer_version": lmn_transfer_version,
        "reputation":   {str(c): {str(u): v for u, v in r.items()} for c, r in reputation.items()},
        "profiles":     {str(u): v for u, v in profiles.items()},
        "warnings_db":  {str(c): {str(u): v for u, v in w.items()} for c, w in warnings_db.items()},
        "ru_army_warns":{str(c): {str(u): v for u, v in w.items()} for c, w in ru_army_warns.items()},
        "chat_rules":   {str(c): r for c, r in chat_rules.items()},
        "chat_members": {str(c): {str(u): n for u, n in m.items()} for c, m in chat_members.items()},
        "premium_users":  list(_premium_users),
        "verified_users": list(_verified_users),
        "brand_emoji_pack": brand.get_pack(),
        "brand_pack_name":  brand.get_pack_name(),
        "aura":           {str(u): v for u, v in aura.items()},
        "roles":          {str(u): r for u, r in ROLES.items()},
        "role_usernames": dict(_ROLE_USERNAMES),
        "last_rain_time": _last_rain_time,
        "link_guard":       {str(c): v for c, v in _link_guard.items()},
        "link_guard_warns": {str(c): {str(u): v for u, v in w.items()}
                             for c, w in _link_guard_warns.items()},
        "link_whitelist":   {str(c): v for c, v in _link_whitelist.items()},
        "bank_balances":    {str(u): b for u, b in bank_balances.items()},
        "bank_withdraw_cd": {
            str(u): value.isoformat() for u, value in bank_withdraw_cd.items()
        },
        "hunt_cooldown": {
            str(u): value.isoformat() for u, value in hunt_cooldown.items()
        },
        "alchemy_cooldown": {
            str(u): value.isoformat() for u, value in alchemy_cooldown.items()
        },
        "team_alchemy_runs": {
            str(cid): {
                "date": run.get("date"),
                "participants": {
                    str(uid): name for uid, name in run.get("participants", {}).items()
                },
                "completed": bool(run.get("completed", False)),
            }
            for cid, run in team_alchemy_runs.items()
        },
        "save_update_sent": _save_update_sent,
        "pending_notifications": list(pending_notifications),
        "marriage_proposals": [
            {
                "chat_id":      k[0],
                "target_id":    k[1],
                "proposer_id":  v["proposer_id"],
                "proposer_full": v["proposer_full"],
            }
            for k, v in marriage_proposals.items()
        ],
        # V6
        "user_xp":           {str(u): v for u, v in user_xp.items()},
        "user_messages":     {str(c): {str(u): v for u, v in m.items()} for c, m in user_messages.items()},
        "daily_cooldown":    {str(u): v for u, v in daily_cooldown.items()},
        "user_achievements": {str(u): list(v) for u, v in user_achievements.items()},
        "mod_logs":          {str(c): v for c, v in mod_logs.items()},
        "reports_db":        {str(c): v for c, v in reports_db.items()},
        "referrals":         {str(u): v for u, v in referrals.items()},
        "referral_counts":   {str(u): v for u, v in referral_counts.items()},
        "raid_mode":         {str(c): v for c, v in raid_mode.items()},
        "antispam_mode":     {str(c): v for c, v in antispam_mode.items()},
        "games_played":      {str(u): v for u, v in _games_played.items()},
        "games_won":         {str(u): v for u, v in _games_won.items()},
        "v6_announced":      v6_announced,
        "bonus_weekly_cd":   {str(u): v for u, v in bonus_weekly_cd.items()},
        "daily_games":       {str(u): v for u, v in daily_games.items()},
        "daily_msg_cnt":     {str(u): v for u, v in daily_msg_cnt.items()},
        "tasks_bonus_cd":    {str(u): v for u, v in tasks_bonus_cd.items()},
        "marriage_dates":    dict(marriage_dates),
        "work_cooldown":     {str(u): v.isoformat() if hasattr(v, "isoformat") else str(v) for u, v in work_cooldown.items()},
        "fish_cooldown":     {str(u): v.isoformat() if hasattr(v, "isoformat") else str(v) for u, v in fish_cooldown.items()},
        "rob_cooldown":      {str(u): v.isoformat() if hasattr(v, "isoformat") else str(v) for u, v in rob_cooldown.items()},
    }


def save_data():
    """Зберігає всі сховища в локальний JSON-файл (швидкий синхронний кеш на диску).
    PostgreSQL-збереження виконується через _save_all_to_db() (auto_save_loop / shutdown).
    """
    os.makedirs("data", exist_ok=True)
    payload = _build_main_payload()
    try:
        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode()
        with open(DATA_FILE, "wb") as f:
            f.write(raw)
        # Усі команди, що вже викликають save_data(), отримують негайний
        # PostgreSQL sync. Це зберігає стрики, шлюби, економіку й статистику
        # без копіювання викликів у десятки обробників.
        if _db.has_pg():
            try:
                global _state_save_task
                # Не допускаем гонку: несколько быстрых команд раньше могли
                # завершать записи в БД не по порядку и возвращать старый снимок.
                # Каждый новый save_data пишет актуальный snapshot после
                # предыдущего задания.
                previous_task = _state_save_task

                async def _persist_snapshot() -> None:
                    if previous_task:
                        try:
                            await previous_task
                        except Exception:
                            pass
                    ok = await _db.db_set("bot_data", payload)
                    if not ok:
                        logging.warning("💾 PostgreSQL не подтвердил сохранение bot_data")

                _state_save_task = asyncio.get_running_loop().create_task(
                    _persist_snapshot()
                )
            except RuntimeError:
                pass
    except Exception as e:
        print(f"⚠️ save_data error: {e}")


async def save_state_now(reason: str = "оновлення") -> bool:
    """Одразу зберігає весь критичний стан у PostgreSQL.

    Локальний файл оновлюється першим, а недоступна БД не зупиняє обробник
    команди: автозбереження та shutdown лишаються страховкою.
    """
    save_data()
    _ank.save_anketa_settings()
    try:
        await brand.persist_brand_now()
        if not _db.has_pg():
            logging.warning("💾 %s: PostgreSQL недоступний, дані лишилися локально", reason)
            return False
        records = [
            ("bot_data", _build_main_payload()),
            ("anketa_settings", _ank.build_settings_payload()),
            ("anketa_users", _ank.build_users_payload()),
        ]
        ok = await _db.db_set_many(records)
        if not ok:
            logging.warning("💾 %s: PostgreSQL не підтвердив запис", reason)
        return ok
    except Exception as exc:
        logging.warning("💾 %s: негайне збереження не виконалось: %s", reason, exc)
        return False


def schedule_state_save(reason: str = "оновлення") -> None:
    """Планує негайне збереження, не затримуючи відповідь Telegram."""
    try:
        asyncio.get_running_loop().create_task(save_state_now(reason))
    except RuntimeError:
        # Позa event loop лишається синхронний локальний кеш.
        save_data()


async def restore_bot_data() -> None:
    """При старті відновлює bot_data: PostgreSQL → GitHub → локальний файл."""
    os.makedirs("data", exist_ok=True)

    # 1. PostgreSQL (пріоритет)
    if _db.has_pg():
        data = await _db.db_get("bot_data")
        if data is not None:  # {} — валідний (очищений стан), None — ключ відсутній
            with open(DATA_FILE, "w", encoding="utf-8") as _f:
                json.dump(data, _f, ensure_ascii=False)
            print("✅ bot_data відновлено з PostgreSQL")
            return
        print("⚠️ PostgreSQL: bot_data ще не записано — пробую GitHub...")

    # 2. GitHub fallback
    print("📥 Завантажую bot_data.json з GitHub...")
    raw = await brand.fetch_bot_data_from_github()
    if raw and len(raw) > 10:
        with open(DATA_FILE, "wb") as _f:
            _f.write(raw)
        print(f"✅ bot_data відновлено з GitHub ({len(raw)} байт)")
        return

    # 3. Локальний файл (якщо є)
    if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 10:
        print("⚠️ GitHub порожній — використовую локальний файл")
    else:
        print("⚠️ Немає жодного джерела даних — старт з нуля")


def load_data():
    """Загружает данные из JSON-файла при старте."""
    if not os.path.exists(DATA_FILE):
        return
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        _apply_data(data)
        for u, b in data.get("bank_balances", {}).items():
            bank_balances[int(u)] = int(b)
        print(f"✅ Данные загружены: {DATA_FILE}")
    except Exception as e:
        print(f"⚠️ load_data error: {e}")


def normalize_lmn_balances_once() -> bool:
    """Выравнивает LMN-кошельки известных пользователей один раз.

    Список известных пользователей собирается из кошельков, участников чатов,
    профилей и банковских счетов. Маркер сохраняется вместе с bot_data, поэтому
    последующие перезапуски не будут повторно перезаписывать баланс.
    """
    global lmn_balance_reset_version
    if lmn_balance_reset_version >= LMN_BALANCE_RESET_VERSION:
        return False

    known_ids: set[int] = set(lmn_balances)
    known_ids.update(profiles)
    known_ids.update(bank_balances)
    known_ids.update(aura)
    known_ids.update(_premium_users)
    for members in chat_members.values():
        known_ids.update(members)
    for users in reputation.values():
        known_ids.update(users)
    for users in streaks.values():
        known_ids.update(users)
    for users in marriages.values():
        known_ids.update(users)

    for uid in known_ids:
        lmn_balances[int(uid)] = LMN_BALANCE_RESET_TARGET
        # Банк входит в отображаемый общий баланс и тоже содержит LMN.
        bank_balances[int(uid)] = 0
    lmn_balance_reset_version = LMN_BALANCE_RESET_VERSION
    logging.info(
        "LMN balances normalized for %d known users to %s",
        len(known_ids),
        f"{LMN_BALANCE_RESET_TARGET:,}",
    )
    return True


def transfer_all_balances_to_founder() -> bool:
    """Одноразово переводить усі LMN-гаманці та банківські залишки фаундеру.

    Після виконання всі користувачі (крім фаундера) мають нульовий баланс.
    Маркер версії зберігається разом із bot_data, щоб міграція не повторювалась.
    """
    global lmn_transfer_version
    if lmn_transfer_version >= LMN_TRANSFER_VERSION:
        return False

    total = 0
    # Збираємо всі UID, у кого є ненульовий баланс
    all_uids: set[int] = set(lmn_balances) | set(bank_balances)
    for uid in all_uids:
        if uid == OWNER_ID:
            continue
        total += lmn_balances.get(uid, 0)
        total += bank_balances.get(uid, 0)
        lmn_balances[uid] = 0
        bank_balances[uid] = 0

    # Добавляем к фаундеру (его собственный баланс не трогаем, просто прибавляем)
    lmn_balances[OWNER_ID] = lmn_balances.get(OWNER_ID, 0) + total
    bank_balances.setdefault(OWNER_ID, 0)

    lmn_transfer_version = LMN_TRANSFER_VERSION
    logging.info(
        "LMN transfer: %s LMN transferred to founder (uid=%s) from %d users",
        f"{total:,}", OWNER_ID, len(all_uids),
    )
    return True


async def _save_all_to_db() -> None:
    """Зберігає ВСІ дані: PostgreSQL (основний).
    Викликається тільки з auto_save_loop і shutdown handler —
    ЄДИНА точка запису, без race conditions.
    """
    _to_save = [
        (DATA_FILE,               "bot_data",         "data/bot_data.json"),
        (_ank.ANKETA_USERS_FILE,  "anketa_users",     "data/anketa_users.json"),
        (_ank.ANKETA_DATA_FILE,   "anketa_settings",  "data/anketa_settings.json"),
        ("data/custom_texts.json",  "custom_texts",   "data/custom_texts.json"),
        ("data/custom_style.json",  "custom_style",   "data/custom_style.json"),
        ("data/custom_buttons.json","custom_buttons", "data/custom_buttons.json"),
    ]

    if _db.has_pg():
        # ── PostgreSQL шлях — атомарна транзакція ────────
        records: list[tuple[str, dict]] = []
        for local, pg_key, _ in _to_save:
            try:
                if not os.path.exists(local) or os.path.getsize(local) < 2:
                    continue
                with open(local, "r", encoding="utf-8") as _rf:
                    data_dict = json.load(_rf)
                if data_dict is not None:  # {} є валідним (стерті налаштування)
                    records.append((pg_key, data_dict))
            except Exception as _pe:
                print(f"⚠️ PG prepare {pg_key}: {_pe}")
        if records:
            ok = await _db.db_set_many(records)
            status = "✅" if ok else "⚠️"
            print(f"💾 PostgreSQL: {status} {len(records)}/{len(_to_save)} ключів збережено (1 транзакція)")
        else:
            print("⚠️ _save_all_to_db: немає даних для збереження — пропуск")
    else:
        # ── PostgreSQL недоступний — дані тільки на диску ──
        # Запис через GitHub API прибрано; без PostgreSQL надійна персистентність відсутня.
        print(
            "⚠️ _save_all_to_db: PostgreSQL недоступний. "
            "Дані збережено лише на диск контейнера і будуть втрачені при перезапуску. "
            "Налаштуйте DATABASE_URL для надійної персистентності."
        )


async def auto_save_loop():
    """Автозбереження кожні 10 сек.
    save_data() пише лише на диск.
    _save_all_to_db() — єдина точка запису в PostgreSQL / GitHub.
    """
    while True:
        await asyncio.sleep(10)
        save_data()
        try:
            await _save_all_to_db()
        except Exception as _sl_err:
            print(f"⚠️ auto_save_loop: {_sl_err}")

async def coin_rain_loop():
    """Дождь монет LMN строго каждые 6 часов. Перезапуск бота не сбрасывает таймер."""
    global _last_rain_time
    import time
    RAIN_INTERVAL = 6 * 3600  # 6 часов в секундах

    await asyncio.sleep(30)   # небольшая задержка после старта бота

    # Если данные сброшены (редеплой на Railway) — не стреляем сразу,
    # а планируем первый дождь через 6 часов от текущего момента.
    if _last_rain_time == 0.0:
        _last_rain_time = time.time()
        save_data()

    while True:
        now = time.time()
        elapsed = now - _last_rain_time
        if elapsed < RAIN_INTERVAL:
            # ещё не пришло время — ждём оставшееся
            await asyncio.sleep(RAIN_INTERVAL - elapsed)
            continue

        # Время пришло — запускаем дождь
        _last_rain_time = time.time()
        save_data()

        _rain_texts = [
            ("🌧 <b>ДОЖДЬ ИЗ МОНЕТ!</b>", "💰 Монеты LMN посыпались в чат!", "Напиши <b>подобрать</b> — первый забирает!"),
            ("💸 <b>МОНЕТОПАД!</b>", "Кто-то уронил кошелёк!", "Напиши <b>подобрать</b> и монеты твои!"),
            ("🎁 <b>НЕОЖИДАННЫЙ ПОДАРОК!</b>", "LMN монеты упали с неба!", "Первый кто напишет <b>подобрать</b> — забирает всё!"),
            ("⚡ <b>МОЛНИЯ ПРИНЕСЛА МОНЕТЫ!</b>", "Случайная раздача LMN в чате!", "Напиши <b>подобрать</b> и забери приз!"),
            ("🍀 <b>УДАЧА ПРИШЛА В ЧАТ!</b>", "💰 LMN монеты ищут хозяина!", "Напиши <b>подобрать</b> — быстрее всех!"),
        ]

        active_chats = [cid for cid in chat_members.keys() if cid < 0]
        for chat_id in active_chats:
            amount = random.randint(150, 600)
            _active_rain[chat_id] = amount
            title, desc, call = random.choice(_rain_texts)
            try:
                await bot.send_message(
                    chat_id,
                    f"{brand.hdr()}\n\n"
                    f"{title}\n\n"
                    f"{brand.div()}\n"
                    f"{desc}\n\n"
                    f"{call}\n\n"
                    f"🎁 Приз: <b>{fmt_lmn(amount)} LMN</b>\n"
                    f"{brand.div()}",
                    parse_mode="HTML",
                )
            except Exception:
                _active_rain.pop(chat_id, None)

        await asyncio.sleep(RAIN_INTERVAL)

# ═══════════════════════════════════════════════════════
# АВТОМОДЕРАЦИЯ — ПРОПАГАНДА РОССИЙСКОЙ АРМИИ
# ═══════════════════════════════════════════════════════
import re as _re

# Списки фраз (регистр не важен, кириллица — без \b)
_PROP_PHRASES = [
    # Поддержка армии / операции
    "слава российской армии", "слава русской армии", "слава армии рф",
    "слава рф", "слава путину", "слава вдв", "слава фсб",
    "поддерживаю российскую армию", "поддерживаю армию рф",
    "поддерживаю спецоперацию", "поддерживаю сво",
    "поддержим спецоперацию", "за спецоперацию", "за сво",
    "российская армия молодцы", "наши солдаты молодцы",
    "армия рф лучшая", "российские солдаты герои",
    "русские солдаты герои", "солдаты рф герои",
    # Путин
    "путин молодец", "путин прав", "путин красавец",
    "путин герой", "путин спасёт", "путин спасет",
    "путин победит", "путин норм", "путин огонь",
    "я за путина", "поддерживаю путина",
    # Победа России
    "россия победит", "россия победит украину",
    "рф победит", "русские победят",
    "россия права", "россия правы", "рф права",
    "россия права в этой войне", "россия воюет за правду",
    # Денацификация / оправдание
    "денацификация украины", "демилитаризация украины",
    "оправдываю вторжение", "вторжение оправдано",
    "война справедливая", "спецоперация правильная",
    "спецоперация нужна", "спецоперация справедливая",
    "сво нужно", "сво правильное", "сво справедливое",
    # Украина как «нацисты»
    "украина нацисты", "украинцы нацисты",
    "зеленский нацист", "зеленский нацист",
    "украина фашисты", "украинцы фашисты",
    "нацисты в украине", "укронацисты",
    # Лозунги и символика
    "крым наш", "крым всегда был россией",
    "крым навсегда россия", "крым это россия",
    "украины не существует", "нет украины",
    "украина не страна", "украина часть россии",
    "украина это россия",
    # Оскорбительные нарративы
    "укропы", "хохлы должны", "бандеровцы должны",
    "слава zv", "#zv", "zv победа",
    "za rossiyu", "za россию", "вперёд россия zv",
    "смерть украине", "смерть украинцам",
]

def _is_propaganda(text: str) -> bool:
    """Проверяет текст на наличие пропагандистских фраз."""
    tl = text.lower()
    for phrase in _PROP_PHRASES:
        if phrase in tl:
            return True
    # Дополнительные regex-паттерны (без \b, простые поиски)
    _extra = _re.compile(
        r"(слава\s+росси[ия]|за\s+росси[ию]\s+(?:против|воюем)|"
        r"росси[яи]\s+(?:вперёд|форвард)|"
        r"(?:поддержи|поддержу|поддерживаю)\s+(?:россию|рф)\s+(?:в войне|в\s+войне|в\s+боях|против украин)|"
        r"армия\s+(?:рф|российская|русская)\s+(?:лучшая|победит|молодцы|красавцы|сильная)|"
        r"буду\s+(?:за|поддерживать)\s+(?:россию|рф|путина|армию\s+рф))",
        _re.IGNORECASE,
    )
    return bool(_extra.search(tl))

async def auto_moderate_propaganda(msg: Message) -> bool:
    """
    Проверяет сообщение на пропаганду российской армии.
    Работает для ВСЕХ участников: обычные → варн→бан, создатель → только варны.
    Возвращает True если нарушение обнаружено и обработано.
    """
    if not msg.text:
        return False
    if not _is_propaganda(msg.text):
        return False

    user = msg.from_user
    if not user:
        return False
    chat_id = msg.chat.id
    uid = user.id

    # Определяем статус участника
    is_creator = False
    if msg.chat.type != "private":
        try:
            member = await bot.get_chat_member(chat_id, uid)
            # Администраторов НЕ трогаем (только создателя трогаем — но без бана)
            if member.status == ChatMemberStatus.ADMINISTRATOR:
                return False
            if member.status == ChatMemberStatus.CREATOR:
                is_creator = True
        except Exception:
            pass

    # Удаляем сообщение
    try:
        await msg.delete()
    except Exception:
        pass

    # Считаем варны
    ru_army_warns.setdefault(chat_id, {})
    ru_army_warns[chat_id][uid] = ru_army_warns[chat_id].get(uid, 0) + 1
    count = ru_army_warns[chat_id][uid]

    name = user.full_name
    mention = f'<a href="tg://user?id={uid}">{name}</a>'

    if count >= 2 and not is_creator:
        # Второе нарушение — бан (не для создателя)
        try:
            await bot.ban_chat_member(chat_id, uid)
        except Exception:
            pass
        ru_army_warns[chat_id][uid] = 0
        await bot.send_message(
            chat_id,
            f"🚫 {mention} <b>заблокирован</b> за пропаганду российской армии.\n\n"
            f"🇺🇦 Слава Україні! Пропаганді немає місця в цьому чаті.",
            parse_mode="HTML",
        )
    else:
        # Предупреждение (создатель получает только предупреждения)
        ban_note = "" if is_creator else f"\n❗ Це <b>попередження {count}/2</b>. При повторному порушенні — <b>бан</b>."
        await bot.send_message(
            chat_id,
            f"⚠️ {mention}, повідомлення видалено за <b>пропаганду російської армії</b>.{ban_note}\n\n"
            f"🇺🇦 Росія — країна-агресор. Реклама її армії в цьому чаті заборонена.",
            parse_mode="HTML",
        )
    return True


# ═══════════════════════════════════════════════════════
# ПОМОЩНИКИ
# ═══════════════════════════════════════════════════════
# ── Хелперы ролей ─────────────────────────────────────
def get_role(uid: int) -> str | None:
    """Возвращает роль пользователя или None."""
    return ROLES.get(uid)

def get_role_display(uid: int, username: str = "") -> str | None:
    """Красивое название роли для отображения."""
    r = get_role(uid)
    if r:
        return ROLE_NAMES.get(r, r)
    # Проверяем username-кэш
    uname = (username or "").lower().lstrip("@")
    if uname and uname in _ROLE_USERNAMES:
        return ROLE_NAMES.get(_ROLE_USERNAMES[uname], _ROLE_USERNAMES[uname])
    return None

def set_role(uid: int, role: str, username: str = "") -> None:
    """Назначает роль пользователю, обновляет username-кэш."""
    ROLES[uid] = role
    uname = (username or "").lower().lstrip("@")
    if uname:
        _ROLE_USERNAMES[uname] = role

def remove_role(uid: int, username: str = "") -> bool:
    """Снимает роль. Возвращает True если роль была."""
    had = uid in ROLES
    ROLES.pop(uid, None)
    uname = (username or "").lower().lstrip("@")
    if uname:
        _ROLE_USERNAMES.pop(uname, None)
    return had

def has_role(uid: int, *roles: str) -> bool:
    """True если пользователь имеет хотя бы одну из указанных ролей."""
    return ROLES.get(uid) in roles

def role_badge(uid: int, username: str = "") -> str:
    """Возвращает строку-бейдж для роли, или пустую строку."""
    r = get_role(uid)
    if not r:
        uname = (username or "").lower().lstrip("@")
        r = _ROLE_USERNAMES.get(uname)
    if not r:
        return ""
    icons = {
        "lead_admin": "👑",
        "co_admin":   "⭐",
        "admin":      "🔷",
        "moderator":  "🛡",
    }
    return f"{icons.get(r, '🔹')} {ROLE_NAMES.get(r, r)}"


def is_owner(msg) -> bool:
    """Работает и для Message, и для CallbackQuery — проверяет ТОЛЬКО по числовому ID."""
    u = getattr(msg, "from_user", None)
    if u is None:
        return False
    return u.id == OWNER_ID  # username может быть угнан — только ID

# Пользователи, которым разрешено редактировать все тексты/кнопки бота
_EDITOR_USERNAMES = {OWNER_USERNAME.lower(), "veroniksssxa"}

def is_editor(msg) -> bool:
    """True для фаундера и всех, кому разрешено редактировать контент бота."""
    u = getattr(msg, "from_user", None)
    if u is None:
        return False
    if u.id == OWNER_ID:
        return True
    return (u.username or "").lower() in _EDITOR_USERNAMES

def is_super(msg) -> bool:
    return msg.from_user.id in SUPER_IDS or is_owner(msg)

def is_custom_muter(msg) -> bool:
    """True если юзер входит в список кастомных мутеров."""
    u = getattr(msg, "from_user", None)
    if not u: return False
    return (u.username or "").lower().lstrip("@") in _CUSTOM_MUTERS

def _username_lower(user) -> str:
    """Возвращает username пользователя в нижнем регистре без @."""
    return (getattr(user, "username", None) or "").lower().lstrip("@")

def is_verified(uid: int) -> bool:
    """Прошёл ли пользователь верификацию. Фаундер всегда верифицирован."""
    if uid in SUPER_IDS:
        return True
    return uid in _verified_users

# ── Математическая капча ───────────────────────────────────────
_captcha_pending: dict[int, int] = {}   # uid → правильный ответ


def _gen_captcha() -> tuple[str, int]:
    """Генерирует математическое уравнение и возвращает (вопрос, ответ).
    Преимущественно умножение, иногда сложение/вычитание для разнообразия.
    """
    kind = random.choices(
        ["mul", "mul", "mul", "add", "sub"],  # умножение чаще всего
        k=1,
    )[0]
    if kind == "mul":
        a, b = random.randint(2, 12), random.randint(2, 12)
        return f"{a} × {b} = ?", a * b
    elif kind == "add":
        a, b = random.randint(11, 60), random.randint(11, 39)
        return f"{a} + {b} = ?", a + b
    else:  # sub
        a = random.randint(20, 80)
        b = random.randint(5, a - 1)
        return f"{a} − {b} = ?", a - b


def _captcha_keyboard(uid: int, correct: int) -> InlineKeyboardMarkup:
    """4 кнопки с ответами (1 правильный, 3 ложных)."""
    decoys: set[int] = set()
    while len(decoys) < 3:
        delta = random.randint(1, 18)
        sign  = random.choice([-1, 1])
        w = correct + sign * delta
        if w != correct and w > 0:
            decoys.add(w)
    options = list(decoys) + [correct]
    random.shuffle(options)
    btns = [
        InlineKeyboardButton(
            text=str(opt),
            callback_data=f"captcha_ans:{uid}:{opt}",
        )
        for opt in options
    ]
    return InlineKeyboardMarkup(inline_keyboard=[btns[:2], btns[2:]])

def is_anketa_premium(uid: int, username: str = "") -> bool:
    """True якщо юзер має VIP-статус для анкети (куплений або безкоштовний)."""
    if uid in _premium_users:
        return True
    uname = (username or "").lower().lstrip("@")
    return uname in _PREMIUM_ALWAYS

def is_anketa_revoke_allowed(username: str) -> bool:
    """True якщо юзер може розжалувати анкету (фаундер або @veroniksssxa)."""
    uname = (username or "").lower().lstrip("@")
    return uname in {OWNER_USERNAME.lower(), "veroniksssxa"}

async def is_admin(msg: Message) -> bool:
    if msg.chat.type == "private": return True
    if is_super(msg): return True
    # Роль в системе бота — работает даже если TG-промоут не прошёл
    if has_role(msg.from_user.id, "lead_admin", "co_admin", "admin", "moderator"):
        return True
    try:
        member = await bot.get_chat_member(msg.chat.id, msg.from_user.id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR)
    except Exception:
        return False

async def get_user(msg: Message, command: CommandObject = None):
    if msg.reply_to_message:
        return msg.reply_to_message.from_user
    if command and command.args:
        try:
            uid = int(command.args.split()[0])
            member = await bot.get_chat_member(msg.chat.id, uid)
            return member.user
        except: return None
    return None

def parse_time(text: str) -> timedelta:
    if not text: return timedelta(minutes=1)
    t = text.strip().split()[-1].lower()
    t = t.replace("м","m").replace("ч","h").replace("д","d")
    try:
        if t.endswith("m"): return timedelta(minutes=int(t[:-1]))
        if t.endswith("h"): return timedelta(hours=int(t[:-1]))
        if t.endswith("d"): return timedelta(days=int(t[:-1]))
        return timedelta(minutes=int(t))
    except: return timedelta(minutes=1)

def get_balance(uid: int) -> int:
    if uid not in lmn_balances:
        if lmn_transfer_version >= LMN_TRANSFER_VERSION:
            # После перевода балансов фаундеру новые пользователи начинают с 0
            lmn_balances[uid] = 0
        elif lmn_balance_reset_version >= LMN_BALANCE_RESET_VERSION:
            # До перевода — новые пользователи получали стартовый баланс
            lmn_balances[uid] = LMN_BALANCE_RESET_TARGET
        bank_balances.setdefault(uid, 0)
    return lmn_balances.get(uid, 0)

def add_balance(uid: int, amount: int):
    lmn_balances[uid] = lmn_balances.get(uid, 0) + amount

def fmt_lmn(n: int) -> str:
    return f"{n:,}".replace(",", " ")

def econ_cid(cid: int) -> int:
    """Возвращает канонический chat_id для экономики — объединяет связанные чаты."""
    return _ECON_CANONICAL.get(cid, cid)

def get_rep(chat_id: int, uid: int) -> int:
    return reputation.get(econ_cid(chat_id), {}).get(uid, 0)

def add_rep(chat_id: int, uid: int, n: int):
    cid = econ_cid(chat_id)
    reputation.setdefault(cid, {})
    reputation[cid][uid] = reputation[cid].get(uid, 0) + n

def is_married(chat_id: int, uid: int) -> bool:
    return uid in marriages.get(econ_cid(chat_id), {})

def _marriage_days_str(uid1: int, uid2: int | None) -> str:
    """Возвращает строку вида ' · 42 дн. вместе 💑'.
    Если дата не записана — регистрирует сегодня и возвращает 0 дн."""
    if not uid2:
        return ""
    pair_key = f"{min(uid1, uid2)}_{max(uid1, uid2)}"
    if pair_key not in marriage_dates:
        marriage_dates[pair_key] = today_kyiv().isoformat()
        schedule_state_save("инициализация даты брака")
    try:
        days = (today_kyiv() - date.fromisoformat(marriage_dates[pair_key])).days
        return f" · {days} дн. вместе 💑"
    except Exception:
        return ""

def get_partner(chat_id: int, uid: int):
    return marriages.get(econ_cid(chat_id), {}).get(uid)

# ── Аура ─────────────────────────────────────────────────────
def get_aura(uid: int) -> float:
    return aura.get(uid, 0.0)

def add_aura(uid: int, delta: float):
    """Добавляет delta к ауре пользователя, зажимая в [0, 100]."""
    aura[uid] = max(0.0, min(100.0, aura.get(uid, 0.0) + delta))

def aura_bar(pct: float) -> str:
    filled = round(pct / 5)   # 20 делений
    return "█" * filled + "░" * (20 - filled)

# ═══════════════════════════════════════════════════════
# СТРИКИ
# ═══════════════════════════════════════════════════════
async def do_checkin(chat_id: int, user_id: int, reply_msg: Message = None):
    today = today_kyiv()
    cid = econ_cid(chat_id)
    streaks.setdefault(cid, {})
    data = streaks[cid].get(user_id, {"count": 0, "last": None})
    last = data.get("last")
    # Нормализуем last: может быть строкой после загрузки из JSON
    if isinstance(last, str):
        try:
            last = date.fromisoformat(last)
        except Exception:
            last = None
    if last == today:
        if reply_msg:
            cnt = data["count"]
            await reply_msg.reply(
                f"{brand.hdr()}\n\n"
                f"🔥 Уже отмечался сегодня!\n\n"
                f"📅 Текущий стрик: <b>{cnt} дн.</b>\n"
                f"💡 Возвращайся завтра — стрик ждёт\n\n"
                f"{brand.div()}",
                parse_mode="HTML",
            )
        return False
    # Стрик продолжается только если вчера — иначе сброс
    if last is not None and (today - last) == timedelta(days=1):
        data["count"] += 1
    else:
        data["count"] = 1   # пропустил день(и) — стрик сброшен
    data["last"] = today
    streaks[cid][user_id] = data
    cnt = data["count"]
    # Milestone бонусы
    _milestones = {7: 500, 14: 1500, 30: 5000, 60: 15000, 100: 50000}
    bonus = _milestones.get(cnt, 0)
    if bonus:
        add_balance(user_id, bonus)
        save_data()
    if reply_msg:
        if cnt >= 100:   fire, level = "🔥🔥🔥🔥 АБСОЛЮТНАЯ ЛЕГЕНДА!", "👑"
        elif cnt >= 30:  fire, level = "🔥🔥🔥 Легенда чата!",          "💎"
        elif cnt >= 14:  fire, level = "🔥🔥 Горишь не по-детски!",     "🔥"
        elif cnt >= 7:   fire, level = "🔥 Неплохо! Так держать",       "⚡"
        elif cnt >= 3:   fire, level = "✨ Хорошее начало!",             "🌱"
        else:            fire, level = "🆕 Первые шаги",                 "🌱"
        name = reply_msg.from_user.first_name
        bonus_line = f"\n🎁 Milestone-бонус <b>+{fmt_lmn(bonus)} LMN</b>! 🎊" if bonus else ""
        text = (
            f"{brand.hdr()}\n\n"
            f"{level} Чекин выполнен!\n\n"
            f"👤 <b>{html.escape(name)}</b>\n"
            f"📅 Дней подряд: <b>{cnt}</b>\n"
            f"◆ {fire}"
            f"{bonus_line}\n\n"
            f"{brand.div()}"
        )
        await reply_msg.reply(text, parse_mode="HTML")
    return True

# ═══════════════════════════════════════════════════════
# ADMIN КОМАНДЫ
# ═══════════════════════════════════════════════════════
async def _demote_if_needed(chat_id: int, user_id: int):
    """Снимает права если пользователь является администратором (для суперпользователей)."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        if member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
            await bot.promote_chat_member(chat_id, user_id,
                can_manage_chat=False, can_delete_messages=False,
                can_manage_video_chats=False, can_restrict_members=False,
                can_promote_members=False, can_change_info=False,
                can_invite_users=False, can_pin_messages=False)
    except: pass

# ── Премиум-карточки ────────────────────────────────────
_LMN_HDR = "🖤  L U M E N A  🖤"  # plain fallback для legacy-мест
_LMN_DIV = "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"


def mod_card(action: str, user, extra: str = "", reason: str = "") -> str:
    tag = (f"@{user.username}" if getattr(user, "username", None) else user.full_name)
    lines = [brand.hdr(), "", f"{brand.chk()} Действие выполнено",
             "", f"👤 {tag}", f"⚡ {action}"]
    if extra:
        lines.append(extra)
    if reason:
        lines += ["📝 Причина:", reason]
    lines += ["", brand.div()]
    return "\n".join(lines)

def _build_entities(entities_data: list[dict]) -> list[MessageEntity]:
    """Восстанавливает список MessageEntity из сохранённых JSON-данных."""
    result = []
    for e in (entities_data or []):
        try:
            clean = {k: v for k, v in e.items()
                     if v is not None and k != "user"}
            result.append(MessageEntity(**clean))
        except Exception as exc:
            logging.warning("⚠️ Не удалось восстановить entity бренда: %s", exc)
    return result


async def _send_custom(chat_id: int, key: str, fallback_html: str,
                       name: str | None = None, **kwargs):
    """Отправляет кастомный текст фаундера (с Premium emoji) или HTML fallback.
    name — сырое (не HTML-escaped) имя для подстановки {name} в entities-тексте.
    При ошибке entities (напр. custom emoji из личного пака) падает на plain text."""
    ct = brand.get_custom_text(key)
    if ct:
        text, ents_data = ct
        if name is not None:
            text, ents_data = brand.substitute_name(text, ents_data, name)
        ents = _build_entities(ents_data)
        # entities и parse_mode несовместимы — убираем parse_mode из kwargs
        kw = {k: v for k, v in kwargs.items() if k != "parse_mode"}
        try:
            return await bot.send_message(chat_id, text, entities=ents or None, **kw)
        except Exception as _ent_err:
            logging.warning("⚠️ _send_custom entities rejected (%s): %s", key, _ent_err)
            # Fallback: отправить без entities (plain text, без parse_mode)
            try:
                return await bot.send_message(chat_id, text, **kw)
            except Exception:
                pass
    return await bot.send_message(chat_id, fallback_html, parse_mode="HTML", **kwargs)


async def _answer_custom(msg, key: str, fallback_html: str,
                         name: str | None = None, **kwargs):
    """Как _send_custom, но через msg.answer() — не нужен chat_id.
    Автоматически трекает отправленное сообщение для reply-редактора фаундера.
    Приоритет: кастомный текст → DEFAULT_TEXTS → fallback_html."""
    ct = brand.get_custom_text(key)
    sent = None
    if ct:
        text, ents_data = ct
        if name is not None:
            text, ents_data = brand.substitute_name(text, ents_data, name)
        ents = _build_entities(ents_data)
        # entities и parse_mode несовместимы — убираем parse_mode из kwargs
        kw = {k: v for k, v in kwargs.items() if k != "parse_mode"}
        try:
            sent = await msg.answer(text, entities=ents or None, **kw)
        except Exception as _ent_err:
            logging.warning("⚠️ _answer_custom entities rejected (%s): %s", key, _ent_err)
            try:
                sent = await msg.answer(text, **kw)
            except Exception:
                sent = None
    if sent is None and not ct:
        # Используем DEFAULT_TEXTS если есть, иначе fallback_html
        default_text = brand.DEFAULT_TEXTS.get(key)
        if default_text:
            if name is not None:
                default_text = default_text.replace("{name}", name)
            kwargs.setdefault("parse_mode", "HTML")
            sent = await msg.answer(default_text, **kwargs)
        else:
            sent = await msg.answer(fallback_html, parse_mode="HTML", **kwargs)
    # Трекаем для reply-редактора фаундера
    if key in brand.TEXT_LABELS and sent is not None:
        _tracked_bot_msgs[(sent.chat.id, sent.message_id)] = key
        if len(_tracked_bot_msgs) > 2000:
            oldest = next(iter(_tracked_bot_msgs))
            del _tracked_bot_msgs[oldest]
    return sent


async def reply_t(msg: Message, key: str, parse_mode: str = "HTML", **fmt) -> None:
    """Отправляет ответ по ключу текста (кастомный → DEFAULT_TEXTS).
    Поддерживает format-переменные: reply_t(msg, 'work', job='Повар', earned='500').
    """
    ct = brand.get_custom_text(key)
    if ct:
        text, ents_data = ct[0], ct[1]
        # Применяем fmt только если нет entities с custom_emoji:
        # format() меняет длину текста и сдвигает offsets — premium emoji перестают работать
        has_custom_emoji = any(e.get("type") == "custom_emoji" for e in (ents_data or []))
        if fmt and not has_custom_emoji:
            try:
                text = text.format(**fmt)
            except (KeyError, ValueError):
                pass
        ents = _build_entities(ents_data)
        try:
            sent = await msg.reply(text, entities=ents or None)
        except Exception as _ent_err:
            logging.warning("⚠️ reply_t entities rejected (%s): %s", key, _ent_err)
            try:
                sent = await msg.reply(text)
            except Exception:
                sent = None
    else:
        text = brand.DEFAULT_TEXTS.get(key, "")
        if fmt and text:
            try:
                text = text.format(**fmt)
            except (KeyError, ValueError):
                pass
        if text:
            sent = await msg.reply(text, parse_mode=parse_mode)
        else:
            return None
    # Трекаем для reply-редактора
    if key in brand.TEXT_LABELS and sent is not None:
        _tracked_bot_msgs[(sent.chat.id, sent.message_id)] = key
    return sent


async def _edit_custom(message, key: str, fallback_html: str,
                       name: str | None = None, **kwargs):
    """Как _send_custom, но редактирует существующее сообщение (edit_text)."""
    ct = brand.get_custom_text(key)
    if ct:
        text, ents_data = ct
        if name is not None:
            text, ents_data = brand.substitute_name(text, ents_data, name)
        ents = _build_entities(ents_data)
        kw = {k: v for k, v in kwargs.items() if k != "parse_mode"}
        try:
            return await message.edit_text(text, entities=ents or None, **kw)
        except Exception as _ent_err:
            logging.warning("⚠️ _edit_custom entities rejected (%s): %s", key, _ent_err)
            try:
                return await message.edit_text(text, **kw)
            except Exception:
                pass
    return await message.edit_text(fallback_html, parse_mode="HTML", **kwargs)


def _btn_text(key: str, default: str) -> str:
    """Возвращает кастомный текст кнопки или дефолт (без entities — Telegram не поддерживает)."""
    ct = brand.get_custom_text(key)
    return ct[0].strip() if ct else default


def parse_time_and_reason(args: str) -> tuple:
    """Returns (timedelta, reason_str).
    First word parsed as time; rest is reason.
    Supports: 5м 2ч 3д 1нед 2мес навсегда
    Default if no time given: 1 час.
    """
    import re as _re
    if not args:
        return timedelta(hours=1), ""
    parts = args.strip().split(maxsplit=1)
    first = parts[0].lower()
    reason = parts[1].strip() if len(parts) > 1 else ""

    # Навсегда / permanent
    if first in ("навсегда", "perma", "permanent", "∞", "inf", "infinity", "forever"):
        return timedelta(days=366), reason

    # Нормализуем суффиксы (только первое слово — не трогаем reason!)
    t = first
    # Многосимвольные суффиксы сначала
    t = _re.sub(r'(\d+)\s*(нед(?:ел[яьи]|ель)?|week?s?|w)\b', lambda m: str(int(m.group(1)) * 7) + "d", t)
    t = _re.sub(r'(\d+)\s*(мес(?:яц[аов]?)?|month?s?|mo)\b',  lambda m: str(int(m.group(1)) * 30) + "d", t)
    t = _re.sub(r'(\d+)\s*(мин(?:ут[аы]?)?|min(?:ute)?s?)',   lambda m: m.group(1) + "m", t)
    t = _re.sub(r'(\d+)\s*(час(?:[аов]?)?|hour?s?|hr?)',       lambda m: m.group(1) + "h", t)
    t = _re.sub(r'(\d+)\s*(дн(?:ей|я)?|день|day?s?)',          lambda m: m.group(1) + "d", t)
    # Однобуквенные (после многосимвольных чтобы не конфликтовать)
    t = _re.sub(r'(\d+)м$', lambda m: m.group(1) + "m", t)
    t = _re.sub(r'(\d+)ч$', lambda m: m.group(1) + "h", t)
    t = _re.sub(r'(\d+)д$', lambda m: m.group(1) + "d", t)

    try:
        if t.endswith("m"):   delta = timedelta(minutes=max(1, int(t[:-1])))
        elif t.endswith("h"): delta = timedelta(hours=max(1, int(t[:-1])))
        elif t.endswith("d"): delta = timedelta(days=max(1, int(t[:-1])))
        else:                 delta = timedelta(minutes=max(1, int(t)))
        return delta, reason
    except:
        # Время не распознано → весь args = причина, дефолт 1ч
        return timedelta(hours=1), args.strip()


def _fmt_duration(delta: timedelta) -> str:
    """Форматирует timedelta в читаемую строку на русском."""
    total = int(delta.total_seconds())
    if total >= 365 * 24 * 3600:
        return "навсегда ♾"
    days    = total // 86400
    hours   = (total % 86400) // 3600
    minutes = (total % 3600) // 60
    parts = []
    if days:    parts.append(f"{days}д")
    if hours:   parts.append(f"{hours}ч")
    if minutes: parts.append(f"{minutes}м")
    return " ".join(parts) or "1м"

# ═══════════════════════════════════════════════════════
# СИСТЕМА РОЛЕЙ — только фаундер
# /роль @username lead_admin | co_admin | admin | moderator
# /убратьроль @username
# /роли
# ═══════════════════════════════════════════════════════

_ROLE_ALIASES: dict[str, str] = {
    # lead_admin
    "lead_admin":  "lead_admin",
    "lead":        "lead_admin",
    "лид":         "lead_admin",
    "лидадмин":    "lead_admin",
    # co_admin
    "co_admin":    "co_admin",
    "co-admin":    "co_admin",    # через дефис
    "coadmin":     "co_admin",
    "коадмин":     "co_admin",
    "ко-админ":    "co_admin",
    # admin
    "admin":       "admin",
    "адмін":       "admin",
    "админ":       "admin",
    # moderator
    "moderator":   "moderator",
    "mod":         "moderator",
    "модератор":   "moderator",
    "мод":         "moderator",
}

_ROLE_ICON: dict[str, str] = {
    "lead_admin": "👑",
    "co_admin":   "⭐",
    "admin":      "🔷",
    "moderator":  "🛡",
}

# Права в чате для каждой роли
_ROLE_PERMISSIONS: dict[str, dict] = {
    "lead_admin": dict(
        can_manage_chat=True,
        can_delete_messages=True,
        can_manage_video_chats=True,
        can_restrict_members=True,
        can_promote_members=True,   # может сам назначать других
        can_change_info=True,
        can_invite_users=True,
        can_pin_messages=True,
    ),
    "co_admin": dict(
        can_manage_chat=True,
        can_delete_messages=True,
        can_manage_video_chats=True,
        can_restrict_members=True,
        can_promote_members=False,
        can_change_info=True,
        can_invite_users=True,
        can_pin_messages=True,
    ),
    "admin": dict(
        can_manage_chat=True,
        can_delete_messages=True,
        can_manage_video_chats=True,
        can_restrict_members=True,
        can_promote_members=False,
        can_change_info=False,
        can_invite_users=True,
        can_pin_messages=True,
    ),
    "moderator": dict(
        can_manage_chat=True,
        can_delete_messages=True,
        can_manage_video_chats=False,
        can_restrict_members=True,
        can_promote_members=False,
        can_change_info=False,
        can_invite_users=True,
        can_pin_messages=False,
    ),
}


def _fmt_role(role: str) -> str:
    icon = _ROLE_ICON.get(role, "🔹")
    name = ROLE_NAMES.get(role, role)
    return f"{icon} {name}"


# Кто может назначать какие роли
_ROLE_CAN_ASSIGN: dict[str, set] = {
    "lead_admin": {"admin", "moderator"},
    "co_admin":   {"moderator"},
}

def _can_manage_role(msg, target_role: str) -> bool:
    """True если отправитель вправе назначить/снять target_role."""
    if is_owner(msg):
        return True
    user_role = ROLES.get(msg.from_user.id)
    allowed = _ROLE_CAN_ASSIGN.get(user_role, set())
    return target_role in allowed

def _is_lead_or_above(msg) -> bool:
    """True для фаундера и lead_admin."""
    return is_owner(msg) or has_role(msg.from_user.id, "lead_admin")


async def _promote_in_chat(
    user_id: int, role: str, chat_id: int | None = None
) -> tuple[bool, bool, str]:
    """Выдаёт права администратора в чате по роли.
    Возвращает (promote_ok, title_ok, текст_ошибки)."""
    if chat_id is None:
        chat_id = _ank.get_pub_chat()
    if not chat_id or user_id is None:
        return False, False, "чат не настроен"
    perms = _ROLE_PERMISSIONS.get(role, {})
    try:
        await bot.promote_chat_member(chat_id, user_id, **perms)
    except Exception as e:
        err = str(e)
        print(f"⚠️ promote_chat_member({user_id}, {role}, chat={chat_id}): {err}")
        return False, False, err
    # Кастомный тег — название роли (максимум 16 символов по ограничению Telegram)
    custom_title = ROLE_NAMES.get(role, role)[:16]
    try:
        await bot.set_chat_administrator_custom_title(chat_id, user_id, custom_title)
        title_ok = True
        title_err = ""
    except Exception as e:
        title_err = str(e)
        title_ok = False
        print(f"⚠️ set_custom_title({user_id}, '{custom_title}', chat={chat_id}): {title_err}")
    return True, title_ok, title_err


async def _demote_in_chat(user_id: int, chat_id: int | None = None) -> tuple[bool, str]:
    """Снимает все права администратора в чате."""
    if chat_id is None:
        chat_id = _ank.get_pub_chat()
    if not chat_id or user_id is None:
        return False, "чат не настроен"
    try:
        await bot.promote_chat_member(
            chat_id, user_id,
            can_manage_chat=False, can_delete_messages=False,
            can_manage_video_chats=False, can_restrict_members=False,
            can_promote_members=False, can_change_info=False,
            can_invite_users=False, can_pin_messages=False,
        )
        return True, ""
    except Exception as e:
        err = str(e)
        print(f"⚠️ _demote_in_chat({user_id}, chat={chat_id}): {err}")
        return False, err


async def _notify_role_assigned(user_id: int, role: str, assigner_name: str) -> None:
    """Отправляет DM юзеру о назначении роли с ссылкой на чат."""
    chat_link = _ank.get_chat_link() or "https://t.me/+_K2SJRYIhq9hYjFi"
    role_icon = _ROLE_ICON.get(role, "🔹")
    role_name = ROLE_NAMES.get(role, role)
    try:
        await bot.send_message(
            user_id,
            f"{brand.hdr()}\n\n"
            f"{role_icon} <b>Тебе назначена роль!</b>\n\n"
            f"🏷 Роль: <b>{role_name}</b>\n"
            f"👤 Назначил: <b>{html.escape(assigner_name)}</b>\n\n"
            f"Ты получил права администратора в чате сообщества.\n\n"
            f"🔗 <a href=\"{chat_link}\">Перейти в чат</a>\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        print(f"⚠️ _notify_role_assigned DM to {user_id}: {e}")


async def _notify_role_removed(user_id: int, role: str) -> None:
    """Отправляет DM юзеру о снятии роли."""
    role_name = ROLE_NAMES.get(role, role)
    try:
        await bot.send_message(
            user_id,
            f"{brand.hdr()}\n\n"
            f"🔕 <b>Роль снята</b>\n\n"
            f"🏷 Была роль: <b>{role_name}</b>\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )
    except Exception:
        pass


@dp.message(Command("setrole"))
async def cmd_set_role_slash(msg: Message, command: CommandObject):
    await cmd_set_role(msg, command)


@dp.message(Command("removerole"))
async def cmd_remove_role_slash(msg: Message, command: CommandObject):
    await cmd_remove_role(msg, command)


@dp.message(Command("roles"))
async def cmd_roles_slash(msg: Message):
    await cmd_roles(msg)


async def cmd_set_role(msg: Message, command=None):
    """Назначить роль.
    Фаундер — любую. Lead/co_admin — только admin и moderator.
    Работает: роль @username lead_admin  ИЛИ ответ на сообщение + роль admin"""
    uid = msg.from_user.id
    if not (is_owner(msg) or has_role(uid, "lead_admin", "co_admin")):
        return await msg.reply("⛔ Только фаундер или главный админ")

    # Получаем сырые аргументы — из CommandObject или из текста сообщения
    if command is not None:
        raw_args = (command.args or "").strip()
    else:
        # Текстовая команда: "роль @username admin"
        parts = (msg.text or "").strip().split(maxsplit=1)
        raw_args = parts[1] if len(parts) > 1 else ""

    args = raw_args.split()
    target = None
    role_raw = ""

    if msg.reply_to_message:
        target = msg.reply_to_message.from_user
        # Пропускаем @упоминания в аргументах — берём первое не-mention слово как роль
        role_raw = next(
            (a.lower() for a in args if not a.startswith("@")), ""
        )
    elif len(args) >= 2:
        username = args[0].lstrip("@")
        role_raw = args[1].lower()
        # Ищем ID по username или имени в chat_members
        found_uid = next(
            (uid for cid_m in chat_members.values()
             for uid in cid_m
             if any(n.lower() == username.lower() for n in [str(uid),
                    next((v for k, v in cid_m.items() if k == uid), "")])),
            None,
        )
        # Упрощённый поиск: ищем по username в _ROLE_USERNAMES или просто сохраняем
        target_id   = found_uid
        target_name = f"@{username}"
    elif len(args) == 1:
        role_raw = args[0].lower()
        if not msg.reply_to_message:
            return await msg.reply(
                "ℹ️ Чтобы назначить роль — ответь на сообщение нужного человека:\n"
                "<code>роль lead_admin</code> (в ответ на его сообщение)\n\n"
                "Или укажи username: <code>роль @username admin</code>",
                parse_mode="HTML",
            )
    else:
        return await msg.reply(
            "👥 <b>Назначение роли</b>\n\n"
            "Ответь на сообщение человека и напиши:\n"
            "<code>роль lead_admin</code>\n"
            "<code>роль co_admin</code>\n"
            "<code>роль admin</code>\n"
            "<code>роль moderator</code>\n\n"
            "Или без reply:\n"
            "<code>роль @username admin</code>",
            parse_mode="HTML",
        )

    role = _ROLE_ALIASES.get(role_raw)
    if not role:
        valid = "  ".join(f"<code>{k}</code>" for k in ROLE_NAMES)
        return await msg.reply(
            f"❓ Неизвестная роль: <code>{html.escape(role_raw)}</code>\n\n"
            f"Доступные:\n{valid}",
            parse_mode="HTML",
        )

    # Проверяем что у вызывающего достаточно прав для этой конкретной роли
    if not _can_manage_role(msg, role):
        allowed = _ROLE_CAN_ASSIGN.get(ROLES.get(msg.from_user.id), set())
        readable = " / ".join(f"<code>{r}</code>" for r in sorted(allowed)) or "—"
        return await msg.reply(
            f"⛔ Ты можешь назначать только: {readable}",
            parse_mode="HTML",
        )

    if msg.reply_to_message:
        u     = msg.reply_to_message.from_user
        uname = (u.username or "").lower().lstrip("@")
        set_role(u.id, role, uname)
        mention = f"@{uname}" if uname else html.escape(u.full_name)
    elif "target_id" in dir():
        uname = username.lower().lstrip("@")
        if target_id:
            set_role(target_id, role, uname)
        else:
            _ROLE_USERNAMES[uname] = role
        mention = f"@{uname}"
    else:
        return

    save_data()

    # Промоут в чате + DM-уведомление
    promoted_uid = None
    if msg.reply_to_message:
        promoted_uid = msg.reply_to_message.from_user.id
    elif "target_id" in dir() and target_id:
        promoted_uid = target_id

    chat_ok = False
    title_ok = False
    chat_err = ""
    if promoted_uid:
        # Промоут в текущем чате (где выдана команда)
        chat_ok, title_ok, chat_err = await _promote_in_chat(promoted_uid, role, msg.chat.id)
        # Если текущий чат — не pub_chat, промоутим и там
        pub_id = _ank.get_pub_chat()
        if pub_id and pub_id != msg.chat.id:
            ok2, tok2, err2 = await _promote_in_chat(promoted_uid, role, pub_id)
            if ok2:
                chat_ok = True
                if tok2:
                    title_ok = True
                    chat_err = ""
                elif not chat_err:
                    chat_err = err2
            elif not chat_ok:
                chat_err = err2 or chat_err
        assigner = msg.from_user.full_name
        await _notify_role_assigned(promoted_uid, role, assigner)

    if not promoted_uid:
        chat_note = "\n<i>⚠️ ID неизвестен — права выдам автоматически при первом сообщении</i>"
    elif not chat_ok:
        chat_note = f"\n<i>⚠️ Права не выданы: {html.escape(chat_err)}</i>"
    elif not title_ok:
        chat_note = f"\n<i>⚠️ Права выданы, тег не установлен: {html.escape(chat_err)}</i>"
    else:
        chat_note = ""

    tag_display = ROLE_NAMES.get(role, role)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"{_fmt_role(role)} <b>назначена</b>\n\n"
        f"👤 {mention}\n"
        f"🏷 Роль: <b>{tag_display}</b>\n"
        f"💬 Тег в чате: {'<b>' + tag_display + '</b> ✅' if title_ok else '—'}{chat_note}\n"
        f"📩 Уведомление: {'отправлено в ЛС' if promoted_uid else 'отправлю при первом контакте'}\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )


async def cmd_remove_role(msg: Message, command=None):
    """Снять роль. Фаундер — любую. Lead/co_admin — только admin и moderator."""
    uid = msg.from_user.id
    if not (is_owner(msg) or has_role(uid, "lead_admin", "co_admin")):
        return await msg.reply("⛔ Только фаундер или главный админ")

    if command is not None:
        raw_args = (command.args or "").strip().lstrip("@")
    else:
        parts = (msg.text or "").strip().split(maxsplit=1)
        raw_args = parts[1].lstrip("@") if len(parts) > 1 else ""

    if msg.reply_to_message:
        u     = msg.reply_to_message.from_user
        uname = (u.username or "").lower().lstrip("@")
        old   = get_role(u.id)
        # Проверяем что у вызывающего есть право снять эту роль
        if old and not _can_manage_role(msg, old):
            return await msg.reply(f"⛔ Ты не можешь снять роль {_fmt_role(old)}")
        remove_role(u.id, uname)
        save_data()
        await _demote_in_chat(u.id, msg.chat.id)
        pub_id = _ank.get_pub_chat()
        if pub_id and pub_id != msg.chat.id:
            await _demote_in_chat(u.id, pub_id)
        if old:
            await _notify_role_removed(u.id, old)
        mention = f"@{uname}" if uname else html.escape(u.full_name)
        old_str = f" (была {_fmt_role(old)})" if old else ""
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            f"✅ Роль снята{old_str}\n\n"
            f"👤 {mention}\n"
            f"📩 Пользователь уведомлён в ЛС\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )

    if not raw_args:
        return await msg.reply(
            "Ответь на сообщение или укажи:\n<code>убратьроль @username</code>",
            parse_mode="HTML",
        )

    uname = raw_args.lower()
    found_uid = next(
        (uid for uid, r in ROLES.items()
         if _ROLE_USERNAMES.get(uname) == r and uid in
            {u for cm in chat_members.values() for u in cm}),
        None,
    )
    old = _ROLE_USERNAMES.get(uname)
    _ROLE_USERNAMES.pop(uname, None)
    if found_uid:
        ROLES.pop(found_uid, None)
        await _demote_in_chat(found_uid, msg.chat.id)
        pub_id = _ank.get_pub_chat()
        if pub_id and pub_id != msg.chat.id:
            await _demote_in_chat(found_uid, pub_id)
        if old:
            await _notify_role_removed(found_uid, old)
    save_data()
    old_str = f" (была {_fmt_role(old)})" if old else ""
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"✅ Роль снята{old_str}\n\n"
        f"👤 @{html.escape(uname)}\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )


async def cmd_roles(msg: Message, command=None):
    """Список всех назначенных ролей — фаундер и главные админы."""
    uid = msg.from_user.id
    if not (is_owner(msg) or has_role(uid, "lead_admin", "co_admin")):
        return await msg.reply("⛔ Только фаундер или главный админ")

    lines = ["👥 <b>Назначенные роли</b>\n"]
    by_role: dict[str, list[str]] = {r: [] for r in ROLE_HIERARCHY}

    seen_unames: set[str] = set()
    for uid, role in ROLES.items():
        if role not in by_role:
            by_role.setdefault(role, [])
        # Имя: ищем в chat_members
        display = f"ID {uid}"
        for cid_m in chat_members.values():
            if uid in cid_m:
                display = cid_m[uid]
                break
        # Ищем @username
        for uname, r in _ROLE_USERNAMES.items():
            if r == role:
                display = f"@{uname}"
                seen_unames.add(uname)
                break
        by_role[role].append(display)

    # Username-only записи (без ID)
    for uname, role in _ROLE_USERNAMES.items():
        if uname not in seen_unames and role in by_role:
            by_role[role].append(f"@{uname}")

    total = 0
    for role in ROLE_HIERARCHY:
        members = by_role.get(role, [])
        if not members:
            continue
        lines.append(f"\n{_fmt_role(role)}")
        for m in members:
            lines.append(f"  • {html.escape(str(m))}")
            total += 1

    if total == 0:
        lines.append(
            "Нет назначенных ролей.\n\n"
            "<i>Чтобы назначить — ответь на сообщение и напиши:</i>\n"
            "<code>роль lead_admin</code>"
        )
    lines.append(f"\n<i>Фаундер @{OWNER_USERNAME} — всегда активен</i>")
    await msg.reply("\n".join(lines), parse_mode="HTML")


@dp.message(Command("mute"))
async def cmd_mute(msg: Message, command: CommandObject):
    _caller_is_custom = is_custom_muter(msg)
    if not await is_admin(msg) and not _caller_is_custom:
        return await msg.reply("⛔ Только админы")
    user = await get_user(msg, command)
    if not user: return await msg.reply(
        "ℹ️ Ответь на сообщение.\n"
        "Примеры:\n"
        "<code>!мут 30м флуд</code>\n"
        "<code>!мут 2ч спам</code>\n"
        "<code>!мут 7д оскорбления</code>\n"
        "<code>!мут навсегда</code>",
        parse_mode="HTML")
    if user.id == OWNER_ID:
        return await msg.reply("⛔ Нельзя замутить фаундера")
    if user.id == msg.from_user.id:
        return await msg.reply("⛔ Нельзя замутить себя")
    # Кастомные мутеры могут мутить только своих целей
    if _caller_is_custom and not await is_admin(msg):
        if _username_lower(user) not in _MUTE_TARGETS:
            return await msg.reply("⛔ У тебя нет прав мутить этого пользователя")
    # Снимаем права администратора у цели, если нужно (иначе Telegram вернёт ошибку)
    if is_owner(msg) or _username_lower(user) in _MUTE_TARGETS:
        await _demote_if_needed(msg.chat.id, user.id)
    delta, reason = parse_time_and_reason(command.args or "")
    until = now_kyiv() + delta
    dur_str = _fmt_duration(delta)
    is_perma = delta.days >= 365
    title = f"Мут ♾ навсегда" if is_perma else f"Мут 🔇 на {dur_str}"
    extra = None if is_perma else f"⏰ До {until.strftime('%d.%m.%Y %H:%M')}"
    try:
        await bot.restrict_chat_member(msg.chat.id, user.id,
            permissions=ChatPermissions(can_send_messages=False), until_date=until)
        _log_mod(msg.chat.id, "mute", user.id, msg.from_user.id)
        await msg.reply(
            mod_card(title, user, reason=reason, extra=extra),
            parse_mode="HTML")
    except Exception as e: await msg.reply(f"❌ {e}")


@dp.message(Command("mute1", "мут1"))
async def cmd_mute1(msg: Message, command: CommandObject):
    """Мут на 1 минуту — кастомные мутеры могут применять только к _MUTE_TARGETS."""
    _caller_is_custom = is_custom_muter(msg)
    if not await is_admin(msg) and not _caller_is_custom:
        return await msg.reply("⛔ Только админы")
    user = await get_user(msg, command)
    if not user:
        return await msg.reply(
            "ℹ️ Ответь на сообщение пользователя.\n"
            "Пример: <code>!мут1</code> — мут на 1 минуту",
            parse_mode="HTML")
    if user.id == OWNER_ID:
        return await msg.reply("⛔ Нельзя замутить фаундера")
    if user.id == msg.from_user.id:
        return await msg.reply("⛔ Нельзя замутить себя")
    if _caller_is_custom and not await is_admin(msg):
        if _username_lower(user) not in _MUTE_TARGETS:
            return await msg.reply("⛔ У тебя нет прав мутить этого пользователя")
    # Снимаем права администратора у цели, если нужно
    if is_owner(msg) or _username_lower(user) in _MUTE_TARGETS:
        await _demote_if_needed(msg.chat.id, user.id)
    delta = timedelta(minutes=1)
    until = now_kyiv() + delta
    _, reason = parse_time_and_reason(command.args or "")
    try:
        await bot.restrict_chat_member(msg.chat.id, user.id,
            permissions=ChatPermissions(can_send_messages=False), until_date=until)
        _log_mod(msg.chat.id, "mute", user.id, msg.from_user.id)
        await msg.reply(
            mod_card("Мут 🔇 на 1 мин", user, reason=reason,
                     extra=f"⏰ До {until.strftime('%H:%M')}"),
            parse_mode="HTML")
    except Exception as e:
        await msg.reply(f"❌ {e}")

@dp.message(Command("unmute"))
async def cmd_unmute(msg: Message, command: CommandObject):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    user = await get_user(msg, command)
    if not user: return await msg.reply("Ответь на сообщение")
    try:
        await bot.restrict_chat_member(msg.chat.id, user.id,
            permissions=ChatPermissions(can_send_messages=True, can_send_media_messages=True,
                can_send_other_messages=True, can_add_web_page_previews=True))
        _log_mod(msg.chat.id, "unmute", user.id, msg.from_user.id)
        await msg.reply(mod_card("Размучен 🔊", user), parse_mode="HTML")
    except Exception as e: await msg.reply(f"❌ {e}")

@dp.message(Command("ban"))
async def cmd_ban(msg: Message, command: CommandObject):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    user = await get_user(msg, command)
    if not user: return await msg.reply(
        "ℹ️ Ответь на сообщение.\n"
        "Примеры:\n"
        "<code>!бан спам</code>\n"
        "<code>!бан нарушение правил</code>",
        parse_mode="HTML")
    if user.id == OWNER_ID:
        return await msg.reply("⛔ Нельзя забанить фаундера")
    if user.id == msg.from_user.id:
        return await msg.reply("⛔ Нельзя забанить себя")
    if is_super(msg):
        await _demote_if_needed(msg.chat.id, user.id)
    _, reason = parse_time_and_reason(command.args or "")
    try:
        await bot.ban_chat_member(msg.chat.id, user.id)
        _log_mod(msg.chat.id, "ban", user.id, msg.from_user.id)
        await msg.reply(mod_card("Бан 🚫", user, reason=reason), parse_mode="HTML")
    except Exception as e: await msg.reply(f"❌ {e}")

@dp.message(Command("forceban"))
async def cmd_forceban(msg: Message, command: CommandObject):
    if not is_owner(msg): return await msg.reply("⛔ Только @hdrttttttt")
    user = await get_user(msg, command)
    if not user: return await msg.reply("Ответь на сообщение")
    try:
        await bot.promote_chat_member(msg.chat.id, user.id, can_manage_chat=False,
            can_delete_messages=False, can_manage_video_chats=False,
            can_restrict_members=False, can_promote_members=False,
            can_change_info=False, can_invite_users=False, can_pin_messages=False)
    except: pass
    _, reason = parse_time_and_reason(command.args or "")
    try:
        await bot.ban_chat_member(msg.chat.id, user.id)
        _log_mod(msg.chat.id, "ban", user.id, msg.from_user.id)
        await msg.reply(
            mod_card("Принудительный бан 🔨", user, extra="⚠️ Права сняты", reason=reason),
            parse_mode="HTML")
    except Exception as e: await msg.reply(f"❌ {e}")

@dp.message(Command("forcemute"))
async def cmd_forcemute(msg: Message, command: CommandObject):
    if not is_owner(msg): return await msg.reply("⛔ Только @hdrttttttt")
    user = await get_user(msg, command)
    if not user: return await msg.reply("Ответь на сообщение")
    try:
        await bot.promote_chat_member(msg.chat.id, user.id, can_manage_chat=False,
            can_delete_messages=False, can_manage_video_chats=False,
            can_restrict_members=False, can_promote_members=False,
            can_change_info=False, can_invite_users=False, can_pin_messages=False)
    except: pass
    delta, reason = parse_time_and_reason(command.args or "")
    until = now_kyiv() + delta
    dur_str  = _fmt_duration(delta)
    is_perma = delta.days >= 365
    title    = "Принудительный мут ♾ навсегда 🔇" if is_perma else f"Принудительный мут 🔇 на {dur_str}"
    extra2   = "⚠️ Права сняты" if is_perma else f"⚠️ Права сняты · До {until.strftime('%d.%m.%Y %H:%M')}"
    try:
        await bot.restrict_chat_member(msg.chat.id, user.id,
            permissions=ChatPermissions(can_send_messages=False), until_date=until)
        _log_mod(msg.chat.id, "mute", user.id, msg.from_user.id)
        await msg.reply(
            mod_card(title, user, extra=extra2, reason=reason),
            parse_mode="HTML")
    except Exception as e: await msg.reply(f"❌ {e}")

@dp.message(Command("unban"))
async def cmd_unban(msg: Message, command: CommandObject):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    user = await get_user(msg, command)
    if not user: return await msg.reply("Укажи ID")
    try:
        await bot.unban_chat_member(msg.chat.id, user.id)
        _log_mod(msg.chat.id, "unban", user.id, msg.from_user.id)
        await msg.reply(mod_card("Разбанен ✅", user), parse_mode="HTML")
    except Exception as e: await msg.reply(f"❌ {e}")

@dp.message(Command("kick"))
async def cmd_kick(msg: Message, command: CommandObject):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    user = await get_user(msg, command)
    if not user: return await msg.reply("ℹ️ Ответь на сообщение пользователя")
    if user.id == OWNER_ID:
        return await msg.reply("⛔ Нельзя кикнуть фаундера")
    if user.id == msg.from_user.id:
        return await msg.reply("⛔ Нельзя кикнуть себя")
    _, reason = parse_time_and_reason(command.args or "")
    try:
        await bot.ban_chat_member(msg.chat.id, user.id)
        await bot.unban_chat_member(msg.chat.id, user.id)
        _log_mod(msg.chat.id, "kick", user.id, msg.from_user.id)
        await msg.reply(mod_card("Кик 👢", user, reason=reason), parse_mode="HTML")
    except Exception as e: await msg.reply(f"❌ {e}")

@dp.message(Command("warn"))
async def cmd_warn(msg: Message, command: CommandObject):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    user = await get_user(msg, command)
    if not user: return await msg.reply("Ответь на сообщение")
    if user.id == OWNER_ID:
        return await msg.reply("⛔ Нельзя предупредить фаундера")
    if user.id == msg.from_user.id:
        return await msg.reply("⛔ Нельзя предупредить себя")
    chat_id, uid = msg.chat.id, user.id
    warnings_db.setdefault(chat_id, {})
    warnings_db[chat_id][uid] = warnings_db[chat_id].get(uid, 0) + 1
    count = warnings_db[chat_id][uid]
    _, reason = parse_time_and_reason(command.args or "")
    if count >= 3:
        try:
            await bot.ban_chat_member(chat_id, uid)
            _log_mod(chat_id, "ban", uid, msg.from_user.id)
            warnings_db[chat_id][uid] = 0
            await msg.reply(
                mod_card("Бан 🚫 (3 варна)", user, extra="⚠️ Достигнут лимит предупреждений", reason=reason),
                parse_mode="HTML")
        except Exception as e:
            # бан не прошёл — откатываем варн чтобы не было рассинхронизации
            warnings_db[chat_id][uid] = max(0, count - 1)
            await msg.reply(f"❌ Не удалось забанить: {e}")
    else:
        _log_mod(chat_id, "warn", uid, msg.from_user.id)
        await msg.reply(
            mod_card(f"Варн ⚠️ ({count}/3)", user, reason=reason),
            parse_mode="HTML")

@dp.message(Command("unwarn"))
async def cmd_unwarn(msg: Message, command: CommandObject):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    user = await get_user(msg, command)
    if not user: return await msg.reply("Ответь на сообщение")
    chat_id, uid = msg.chat.id, user.id
    if chat_id in warnings_db and uid in warnings_db[chat_id] and warnings_db[chat_id][uid] > 0:
        warnings_db[chat_id][uid] -= 1
        remaining = warnings_db[chat_id][uid]
        _log_mod(chat_id, "unwarn", uid, msg.from_user.id)
        await msg.reply(
            mod_card("Варн снят ✅", user, extra=f"📊 Осталось предупреждений: {remaining}/3"),
            parse_mode="HTML")
    else:
        await msg.reply(
            mod_card("Снятие варна", user, extra="ℹ️ У пользователя нет варнов"),
            parse_mode="HTML")

@dp.message(Command("purge"))
async def cmd_purge(msg: Message, command: CommandObject):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    try: count = min(max(int(command.args or 10), 1), 100)
    except: return await msg.reply("Использование: /purge 20")
    deleted = 0
    async for m in bot.get_chat_history(msg.chat.id, limit=count + 1):
        try: await m.delete(); deleted += 1
        except: pass
    info = await msg.answer(f"🗑 Удалено: {deleted}")
    await asyncio.sleep(3); await info.delete()

@dp.message(Command("ro"))
async def cmd_ro(msg: Message, command: CommandObject):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    arg = (command.args or "").lower()
    if arg in ("on","1","вкл"):
        perms = ChatPermissions(can_send_messages=False)
        action, icon = "Режим чтения включён", "🔒"
    else:
        perms = ChatPermissions(can_send_messages=True, can_send_media_messages=True,
            can_send_other_messages=True, can_add_web_page_previews=True)
        action, icon = "Режим чтения выключен", "🔓"
    try:
        await bot.set_chat_permissions(msg.chat.id, perms)
        await msg.reply(
            f"{brand.hdr()}\n\n{icon} {action}\n\n{brand.div()}",
            parse_mode="HTML")
    except Exception as e: await msg.reply(f"❌ {e}")

@dp.message(Command("pin"))
async def cmd_pin(msg: Message):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    if not msg.reply_to_message: return await msg.reply("Ответь на сообщение")
    try: await bot.pin_chat_message(msg.chat.id, msg.reply_to_message.message_id); await msg.reply("📌 Закреплено")
    except Exception as e: await msg.reply(f"❌ {e}")

@dp.message(Command("unpin"))
async def cmd_unpin(msg: Message):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    try: await bot.unpin_chat_message(msg.chat.id); await msg.reply("📌 Откреплено")
    except Exception as e: await msg.reply(f"❌ {e}")

@dp.message(Command("title"))
async def cmd_title(msg: Message, command: CommandObject):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    if not command.args: return await msg.reply("Использование: /title Новое название")
    try: await bot.set_chat_title(msg.chat.id, command.args); await msg.reply("✅ Название изменено")
    except Exception as e: await msg.reply(f"❌ {e}")

# ═══════════════════════════════════════════════════════
# БРАК — СИСТЕМА С ПРЕДЛОЖЕНИЯМИ
# ═══════════════════════════════════════════════════════
@dp.message(Command("marry"))
async def cmd_marry(msg: Message):
    if not msg.reply_to_message:
        return await msg.reply("Ответь на сообщение человека которому хочешь сделать предложение 💍")
    proposer = msg.from_user
    target = msg.reply_to_message.from_user
    chat_id = msg.chat.id
    if target.id == proposer.id:
        return await msg.reply("Нельзя жениться на себе 😄")
    if target.is_bot:
        return await msg.reply("Бот не может вступить в брак 🤖")
    if is_married(chat_id, proposer.id):
        return await msg.reply("Ты уже в браке! Сначала разведись: развод")
    if is_married(chat_id, target.id):
        return await msg.reply(f"{target.full_name} уже состоит в браке 💔")
    # Блокируем повторное предложение от того же пропоузера
    already_sent = any(
        v["proposer_id"] == proposer.id
        for (cid, _), v in marriage_proposals.items()
        if cid == chat_id
    )
    if already_sent:
        return await msg.reply("Ты уже сделал(а) предложение — дождись ответа 💍")
    # Блокируем повторное предложение тому же таргету
    if (chat_id, target.id) in marriage_proposals:
        existing = marriage_proposals[(chat_id, target.id)]
        return await msg.reply(
            f"У <b>{html.escape(target.full_name)}</b> уже есть ожидающее предложение "
            f"от <b>{html.escape(existing['proposer_full'])}</b> 💔",
            parse_mode="HTML",
        )
    marriage_proposals[(chat_id, target.id)] = {
        "proposer_id": proposer.id,
        "proposer_full": proposer.full_name,
    }
    schedule_state_save("новое предложение брака")
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💍 Принять", callback_data=f"mar_y_{proposer.id}"),
        InlineKeyboardButton(text="❌ Отказать", callback_data=f"mar_n_{proposer.id}"),
    ]])
    await msg.reply(
        f"💍 <b>{html.escape(proposer.full_name)}</b> делает предложение "
        f"<b>{html.escape(target.full_name)}</b>!\n\n"
        f"{html.escape(target.full_name)}, ты принимаешь предложение?",
        parse_mode="HTML", reply_markup=kb
    )


@dp.message(Command("forcemarry"))
async def cmd_forcemarry(msg: Message, command: CommandObject):
    """Фаундер сразу оформляет брак: reply на первого + ID второго участника."""
    if not is_owner(msg):
        return await msg.reply("⛔ Только фаундер может оформить принудительный брак.")
    if msg.chat.type == "private":
        return await msg.reply("💍 Используй команду прямо в групповом чате.")
    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        return await msg.reply(
            "ℹ️ Ответь на сообщение первого человека и напиши:\n"
            "<code>/forcemarry ID_второго</code>",
            parse_mode="HTML",
        )
    try:
        target_id = int((command.args or "").strip().split()[0])
        second_member = await bot.get_chat_member(msg.chat.id, target_id)
        second = second_member.user
    except (IndexError, ValueError):
        return await msg.reply("ℹ️ После команды укажи числовой Telegram ID второго человека.")
    except Exception:
        return await msg.reply("❌ Не удалось найти второго человека в этом чате по ID.")

    first = msg.reply_to_message.from_user
    if first.is_bot or second.is_bot:
        return await msg.reply("🤖 Ботов нельзя оформить в брак.")
    if first.id == second.id:
        return await msg.reply("😄 Нельзя оформить человека в брак с самим собой.")
    if is_married(msg.chat.id, first.id):
        return await msg.reply(f"💔 {first.full_name} уже состоит в браке.")
    if is_married(msg.chat.id, second.id):
        return await msg.reply(f"💔 {second.full_name} уже состоит в браке.")

    cid = econ_cid(msg.chat.id)
    marriages.setdefault(cid, {})
    marriages[cid][first.id] = second.id
    marriages[cid][second.id] = first.id
    # Записываем дату свадьбы
    _pk = f"{min(first.id, second.id)}_{max(first.id, second.id)}"
    marriage_dates[_pk] = today_kyiv().isoformat()
    add_balance(first.id, 500)
    add_balance(second.id, 500)
    save_data()

    marriage_text = (
        f"{brand.hdr()}\n\n"
        "💍 <b>Брак оформлен фаундером!</b>\n\n"
        f"💕 <b>{html.escape(first.full_name)}</b>\n"
        f"❤️ <b>{html.escape(second.full_name)}</b>\n\n"
        "🎊 +500 LMN каждому в подарок!\n\n"
        f"{brand.div()}"
    )
    await msg.reply(marriage_text, parse_mode="HTML")

    pub_chat = _ank.get_pub_chat()
    if pub_chat and pub_chat != msg.chat.id:
        try:
            await bot.send_message(pub_chat, marriage_text, parse_mode="HTML")
        except Exception:
            pass


@dp.callback_query(F.data.startswith("mar_"))
async def marry_callback(cb: CallbackQuery):
    parts = cb.data.split("_")
    action = parts[1]
    proposer_id = int(parts[2])
    chat_id = cb.message.chat.id
    target_id = cb.from_user.id

    # Предложивший не может сам принять/отклонить своё предложение
    if cb.from_user.id == proposer_id:
        await cb.answer("Ты сделал(а) предложение — дождись ответа 💍", show_alert=True)
        return

    proposal = marriage_proposals.get((chat_id, target_id))
    if not proposal or proposal["proposer_id"] != proposer_id:
        await cb.answer("Это предложение не для тебя 😄", show_alert=True)
        return
    del marriage_proposals[(chat_id, target_id)]
    schedule_state_save("ответ на предложение брака")
    _marry_accept = [
        "💍 Совет да любовь!", "❤️ Они вместе!", "🎊 Это случилось!",
        "💕 Новая пара в чате!", "🥂 Совет да любовь!",
    ]
    _marry_reject = [
        "💔 Отказ...", "😬 Нет значит нет", "💔 Сердце разбито",
        "😔 В этот раз не судьба", "🙅 Отказано",
    ]
    if action == "y":
        cid = econ_cid(chat_id)
        # Гонка: проверяем что оба ещё не в браке перед записью
        if is_married(chat_id, proposer_id) or is_married(chat_id, target_id):
            await cb.answer("💔 Один из участников уже состоит в браке", show_alert=True)
            return
        marriages.setdefault(cid, {})
        marriages[cid][proposer_id] = target_id
        marriages[cid][target_id] = proposer_id
        # Записываем дату свадьбы
        pair_key = f"{min(proposer_id, target_id)}_{max(proposer_id, target_id)}"
        marriage_dates[pair_key] = today_kyiv().isoformat()
        add_balance(proposer_id, 500)
        add_balance(target_id, 500)
        await save_state_now("принятие предложения брака")
        header = random.choice(_marry_accept)
        marry_text = (
            f"{brand.hdr()}\n\n"
            f"{header}\n\n"
            f"💕 <b>{html.escape(proposal['proposer_full'])}</b>\n"
            f"❤️ <b>{html.escape(cb.from_user.full_name)}</b>\n\n"
            f"🎊 +500 LMN каждому в подарок!\n\n"
            f"{brand.div()}"
        )
        await cb.message.edit_text(marry_text, parse_mode="HTML")
        # Дублюємо оголошення в основний чат
        pub_chat = _ank.get_pub_chat()
        if pub_chat and pub_chat != chat_id:
            try:
                await bot.send_message(pub_chat, marry_text, parse_mode="HTML")
            except Exception:
                pass
    else:
        header = random.choice(_marry_reject)
        reject_lines = [
            f"<b>{html.escape(cb.from_user.full_name)}</b> отказал(а) <b>{html.escape(proposal['proposer_full'])}</b>",
            f"<b>{html.escape(proposal['proposer_full'])}</b> получил(а) отказ от <b>{html.escape(cb.from_user.full_name)}</b>",
            f"<b>{html.escape(cb.from_user.full_name)}</b> не готов(а)... <b>{html.escape(proposal['proposer_full'])}</b> ждёт",
        ]
        await cb.message.edit_text(
            f"{brand.hdr()}\n\n"
            f"{header}\n\n"
            f"{random.choice(reject_lines)}\n\n"
            f"{brand.div()}",
            parse_mode="HTML"
        )
    await cb.answer()

@dp.message(Command("fordivorce", "развестифаундер"))
async def cmd_fordivorce(msg: Message, command: CommandObject = None):
    """Фаундер разводит двух людей: ответ на сообщение одного + ID второго в аргументе,
    или только ответ — если они женаты между собой."""
    if not is_owner(msg):
        return await msg.reply("⛔ Только фаундер")
    if msg.chat.type == "private":
        return await msg.reply("💔 Команда работает в групповом чате.")
    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        return await msg.reply("ℹ️ Ответь на сообщение одного из участников пары.")

    first = msg.reply_to_message.from_user
    cid = econ_cid(msg.chat.id)

    # Если второй аргумент не указан — ищем партнёра первого
    args_text = (command.args or "").strip() if command else ""
    if args_text:
        try:
            second_id = int(args_text.split()[0])
            second_member = await bot.get_chat_member(msg.chat.id, second_id)
            second = second_member.user
        except Exception:
            return await msg.reply("❌ Не удалось найти второго участника по ID.")
    else:
        partner_id = get_partner(msg.chat.id, first.id)
        if not partner_id:
            return await msg.reply(f"💍 {first.full_name} не состоит в браке.")
        try:
            pm = await bot.get_chat_member(msg.chat.id, partner_id)
            second = pm.user
        except Exception:
            second = None
            second_id = partner_id

    second_id = second.id if second else partner_id
    second_name = second.full_name if second else f"ID {second_id}"

    # Удаляем запись из обоих направлений
    marriages.setdefault(cid, {})
    marriages[cid].pop(first.id, None)
    marriages[cid].pop(second_id, None)
    # Удаляем дату свадьбы
    _pk = f"{min(first.id, second_id)}_{max(first.id, second_id)}"
    marriage_dates.pop(_pk, None)
    save_data()

    divorce_text = (
        f"{brand.hdr()}\n\n"
        f"✂️ <b>Фаундер разрезал ваши узы</b>\n\n"
        f"<b>{html.escape(first.full_name)}</b> и <b>{html.escape(second_name)}</b> "
        f"больше не женаты.\n\n"
        f"<i>Судьба идёт своим путём 🌙</i>\n\n"
        f"{brand.div()}"
    )
    await msg.reply(divorce_text, parse_mode="HTML")

    pub_chat = _ank.get_pub_chat()
    if pub_chat and pub_chat != msg.chat.id:
        try:
            await bot.send_message(pub_chat, divorce_text, parse_mode="HTML")
        except Exception:
            pass


@dp.message(Command("divorce"))
async def cmd_divorce(msg: Message):
    chat_id, uid = msg.chat.id, msg.from_user.id
    if not is_married(chat_id, uid):
        return await msg.reply("💔 Ты не в браке")
    partner_id = get_partner(chat_id, uid)
    partner_name = f"ID {partner_id}"
    try:
        pm = await bot.get_chat_member(chat_id, partner_id)
        partner_name = pm.user.full_name
    except: pass
    cid = econ_cid(chat_id)
    marriages.setdefault(cid, {})
    marriages[cid].pop(uid, None)
    marriages[cid].pop(partner_id, None)
    # Удаляем дату свадьбы
    pair_key = f"{min(uid, partner_id)}_{max(uid, partner_id)}"
    marriage_dates.pop(pair_key, None)
    save_data()
    _divorce_txt = [
        "💔 Развод оформлен", "😔 Всё кончено", "💔 Пути разошлись",
        "😶 Расстались", "💔 История закрыта",
    ]
    _divorce_comment = [
        "Бывает. Жизнь продолжается 🙂",
        "Новая глава начинается",
        "Иногда лучше отпустить",
        "Всему своё время",
        "Не судьба — значит так надо",
    ]
    divorce_text = (
        f"{brand.hdr()}\n\n"
        f"{random.choice(_divorce_txt)}\n\n"
        f"<b>{msg.from_user.full_name}</b> и <b>{partner_name}</b> расстались\n\n"
        f"<i>{random.choice(_divorce_comment)}</i>\n\n"
        f"{brand.div()}"
    )
    await msg.reply(divorce_text, parse_mode="HTML")
    # Дублюємо в основний чат
    pub_chat = _ank.get_pub_chat()
    if pub_chat and pub_chat != msg.chat.id:
        try:
            await bot.send_message(pub_chat, divorce_text, parse_mode="HTML")
        except Exception:
            pass

@dp.message(Command("marriages"))
async def cmd_marriages(msg: Message):
    import html as _html
    cid_raw = msg.chat.id
    cid_can = econ_cid(cid_raw)

    # Мержим браки из обоих ключей (canonical + raw) чтобы не потерять legacy-данные
    merged: dict = {}
    merged.update(marriages.get(cid_can, {}))
    if cid_raw != cid_can:
        merged.update(marriages.get(cid_raw, {}))

    # Уникальные подтверждённые пары (оба направления должны присутствовать)
    seen_pairs: set = set()
    pairs = []
    for u1, u2 in merged.items():
        if merged.get(u2) == u1:          # двустороннее — значит подтверждён
            pair = frozenset([u1, u2])
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                pairs.append((u1, u2))

    # Ожидающие предложения в этом чате
    pending = [
        (v["proposer_id"], tid, v["proposer_full"])
        for (cid, tid), v in marriage_proposals.items()
        if cid == cid_raw
    ]

    if not pairs and not pending:
        return await msg.reply("💍 В этом чате пока нет браков")

    lines = [f"{brand.hdr()}\n"]

    if pairs:
        lines.append(f"💍 Браки чата  ({len(pairs)} пар)")
        lines.append(brand.div())
        for i, (u1, u2) in enumerate(pairs, 1):
            n1, n2 = f"ID {u1}", f"ID {u2}"
            try:
                m1 = await bot.get_chat_member(msg.chat.id, u1)
                n1 = m1.user.full_name
            except: pass
            try:
                m2 = await bot.get_chat_member(msg.chat.id, u2)
                n2 = m2.user.full_name
            except: pass
            pair_key = f"{min(u1, u2)}_{max(u1, u2)}"
            if pair_key not in marriage_dates:
                # Старый брак без даты — регистрируем сегодня, отсчёт начнётся с нуля
                marriage_dates[pair_key] = today_kyiv().isoformat()
                schedule_state_save("инициализация даты брака")
            try:
                wed = date.fromisoformat(marriage_dates[pair_key])
                days_together = (today_kyiv() - wed).days
                days_str = f" · {days_together} дн. вместе 💑"
            except Exception:
                days_str = ""
            lines.append(f"{i}. 💕 <b>{_html.escape(n1)}</b> ❤️ <b>{_html.escape(n2)}</b>{days_str}")

    if pending:
        if pairs:
            lines.append("")
        lines.append("⏳ Ожидают ответа:")
        for prop_id, tgt_id, prop_name in pending:
            tgt_name = f"ID {tgt_id}"
            try:
                tm = await bot.get_chat_member(msg.chat.id, tgt_id)
                tgt_name = tm.user.full_name
            except: pass
            lines.append(
                f"  💌 <b>{_html.escape(prop_name)}</b> → <b>{_html.escape(tgt_name)}</b>"
            )

    lines.append(f"\n{brand.div()}")
    await msg.reply("\n".join(lines), parse_mode="HTML")

# ═══════════════════════════════════════════════════════
# СТРИКИ
# ═══════════════════════════════════════════════════════
@dp.message(Command("checkin"))
async def cmd_checkin(msg: Message):
    await do_checkin(msg.chat.id, msg.from_user.id, msg)

@dp.message(Command("streak"))
async def cmd_streak(msg: Message):
    data = streaks.get(econ_cid(msg.chat.id), {}).get(msg.from_user.id, {"count": 0})
    count = data["count"]
    if count >= 30:   fire = "🔥🔥🔥 Легенда!"
    elif count >= 14: fire = "🔥🔥 Горишь!"
    elif count >= 7:  fire = "🔥 Неплохо!"
    elif count >= 3:  fire = "✨ Начало!"
    else:             fire = "🆕 Старт"
    # Шкала прогресса до следующей вехи (3 → 7 → 14 → 30)
    _milestones = [3, 7, 14, 30]
    _next = next((m for m in _milestones if count < m), None)
    if _next is not None:
        _prev = max([0] + [m for m in _milestones if m <= count])
        pct = (count - _prev) / (_next - _prev) if _next > _prev else 0
        filled = int(pct * 10)
        bar_line = (
            f"📊 {'█' * filled}{'░' * (10 - filled)} {int(pct * 100)}%\n"
            f"🎯 До вехи <b>{_next} дней</b>: осталось <b>{_next - count}</b>\n"
        )
    else:
        bar_line = "📊 ██████████ 100% — максимальная веха! 👑\n"
    name = msg.from_user.first_name
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🔥 Стрик · {name}\n\n"
        f"📅 Дней подряд: <b>{count}</b>\n"
        f"⚡ {fire}\n"
        f"{bar_line}\n"
        f"{brand.div()}",
        parse_mode="HTML"
    )

@dp.message(Command("topstreak"))
async def cmd_topstreak(msg: Message):
    chat_streaks = streaks.get(econ_cid(msg.chat.id), {})
    if not chat_streaks: return await msg.reply("🔥 Пока никто не имеет стрика")
    top = sorted(chat_streaks.items(), key=lambda x: x[1]["count"], reverse=True)[:10]
    medals = ["🥇","🥈","🥉"] + ["4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines = [
        f"{brand.hdr()}\n",
        "🔥 Топ стриков",
        f"{brand.div()}",
    ]
    for i, (uid, data) in enumerate(top):
        try:
            m = await bot.get_chat_member(msg.chat.id, uid)
            name = m.user.full_name
        except: name = f"ID {uid}"
        lines.append(f"{medals[i]} <b>{name}</b>  —  {data['count']} дней 🔥")
    lines.append(f"\n{brand.div()}")
    await msg.reply("\n".join(lines), parse_mode="HTML")

@dp.message(Command("resetstreak"))
async def cmd_resetstreak(msg: Message, command: CommandObject):
    user = await get_user(msg, command) or msg.from_user
    if user.id != msg.from_user.id and not await is_admin(msg):
        return await msg.reply("⛔ Только свой стрик или админ")
    cid = econ_cid(msg.chat.id)
    streaks.get(cid, {}).pop(user.id, None)
    save_data()
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🔄 Стрик сброшен\n\n"
        f"👤 <b>{html.escape(user.full_name)}</b>\n"
        f"📅 Дней подряд: <b>0</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

@dp.message_reaction()
async def on_reaction(event: MessageReactionUpdated):
    """Обрабатывает реакции: 🔥 — стрик, 👍 — аура автора сообщения."""
    if not event.new_reaction:
        return
    user = event.user
    if not user or user.is_bot:
        return

    # ── 🔥 Стрик ────────────────────────────────────────
    if any(getattr(r, "emoji", None) == "🔥" for r in event.new_reaction):
        success = await do_checkin(event.chat.id, user.id)
        if success:
            try:
                await bot.send_message(
                    event.chat.id,
                    f"🔥 {user.first_name} отметился! Стрик растёт.",
                    disable_notification=True,
                )
            except Exception:
                pass

    # ── 👍 Аура ─────────────────────────────────────────
    # Один плюс на сообщение = +0.01% ауры автору, независимо от числа реакций
    if any(getattr(r, "emoji", None) == "👍" for r in event.new_reaction):
        msg_key = (event.chat.id, event.message_id)
        if msg_key not in _aura_credited:
            author_id = _msg_authors.get(msg_key)
            if author_id and author_id != user.id:
                _aura_credited.add(msg_key)
                add_aura(author_id, 0.01)

# ═══════════════════════════════════════════════════════
# LMN ВАЛЮТА
# ═══════════════════════════════════════════════════════
@dp.message(Command("balance"))
async def cmd_balance(msg: Message):
    bal = get_balance(msg.from_user.id)
    name = msg.from_user.first_name
    if bal >= 1_000_000_000:   tier, icon = "Магнат", "💎"
    elif bal >= 1_000_000:     tier, icon = "Богач", "🤑"
    elif bal >= 100_000:       tier, icon = "Зажиточный", "💸"
    elif bal >= 10_000:        tier, icon = "Середняк", "💵"
    else:                      tier, icon = "Новичок", "🪙"
    await reply_t(
        msg,
        "balance",
        name=name,
        icon=icon,
        balance=fmt_lmn(bal),
        tier=tier,
    )

owner_id_cache: int | None = None  # запоминаем ID владельца при первом взаимодействии

def owner_auto_credit(uid: int):
    """Начисляет 500М владельцу если баланс 0 (после рестарта)."""
    if get_balance(uid) == 0:
        add_balance(uid, 500_000_000)

@dp.message(Command("ownerclaim"))
async def cmd_ownerclaim(msg: Message):
    global owner_id_cache
    if not is_owner(msg): return await msg.reply("⛔ Только @hdrttttttt")
    owner_id_cache = msg.from_user.id
    owner_auto_credit(msg.from_user.id)
    bal = get_balance(msg.from_user.id)
    await msg.reply(
        f"👑 <b>HYDRÆ — Фаундер</b>\n"
        f"💰 Баланс: <b>{fmt_lmn(bal)} LMN</b>",
        parse_mode="HTML"
    )

@dp.message(Command("give"))
async def cmd_give(msg: Message, command: CommandObject):
    if not msg.reply_to_message: return await msg.reply(
        "ℹ️ Ответь на сообщение получателя и укажи сумму.\n"
        "Пример: <i>дать 1000</i> (в ответ на сообщение)", parse_mode="HTML")
    target = msg.reply_to_message.from_user
    if target.id == msg.from_user.id:
        return await reply_t(msg, "give_self")
    if target.is_bot:
        return await reply_t(msg, "give_bot")
    if not command.args: return await msg.reply("Укажи сумму: <b>дать [сумма]</b>", parse_mode="HTML")
    try: amount = int(command.args.split()[0])
    except: return await msg.reply("❌ Укажи целое число")
    if amount <= 0:
        return await reply_t(msg, "give_zero")
    sender_bal = get_balance(msg.from_user.id)
    if sender_bal < amount:
        return await msg.reply(
            f"❌ Недостаточно LMN\n"
            f"У тебя: <b>{fmt_lmn(sender_bal)}</b>, нужно: <b>{fmt_lmn(amount)}</b>",
            parse_mode="HTML")
    add_balance(msg.from_user.id, -amount)
    add_balance(target.id, amount)
    schedule_state_save("перевод LMN")
    await reply_t(
        msg,
        "give",
        from_name=msg.from_user.full_name,
        to_name=target.full_name,
        amount=fmt_lmn(amount),
        balance=fmt_lmn(get_balance(msg.from_user.id)),
    )

@dp.message(Command("work"))
async def cmd_work(msg: Message):
    uid = msg.from_user.id
    now = now_kyiv()
    last = work_cooldown.get(uid)
    if last and (now - last).total_seconds() < 3600:
        mins = 60 - int((now - last).total_seconds()) // 60
        return await reply_t(msg, "work_cooldown", mins=mins)
    # Профессии сгруппированы по уровню заработка
    _jobs_tier = [
        # (профессия, мин, макс, эмодзи, фраза результата)
        ("программист",     400, 900,  "💻", "пофиксил баги — получил премию"),
        ("дизайнер",        350, 800,  "🎨", "сдал проект клиенту вовремя"),
        ("врач",            500, 950,  "🧑‍⚕️", "принял пациентов и выписал рецепты"),
        ("юрист",           450, 900,  "⚖️", "выиграл дело в суде"),
        ("архитектор",      400, 850,  "🏗️", "завершил чертежи нового здания"),
        ("пилот",           600,1200,  "✈️", "выполнил рейс без единой задержки"),
        ("астронавт",       700,1500,  "🚀", "провёл эксперименты на орбите"),
        ("стример",         200, 700,  "🎮", "получил донат от зрителей"),
        ("блогер",          150, 600,  "📱", "ролик завирусился — пришли деньги с рекламы"),
        ("повар",           250, 550,  "🧑‍🍳", "шеф-повар оценил твоё блюдо"),
        ("учитель",         200, 500,  "📚", "провёл уроки и получил зарплату"),
        ("водитель",        180, 450,  "🚗", "развёз заказы без пробок"),
        ("музыкант",        100, 800,  "🎵", "сыграл на концерте, зрители аплодировали"),
        ("художник",        100, 600,  "🖼️", "продал картину на аукционе"),
        ("фотограф",        200, 650,  "📸", "фотосессия прошла на ура"),
        ("детектив",        300, 750,  "🕵️", "раскрыл дело и получил гонорар"),
        ("геймдизайнер",    300, 700,  "🎲", "выпустил патч — игроки довольны"),
        ("учёный",          350, 800,  "🔬", "опубликовал статью — гранты прилетели"),
        ("строитель",       200, 500,  "🔨", "сдал объект в срок"),
        ("менеджер",        250, 600,  "💼", "закрыл сделку с клиентом"),
        ("шеф-пекарь",      180, 420,  "🥐", "торты разлетелись ещё до открытия"),
        ("ветеринар",       250, 580,  "🐾", "спас котика — хозяйка щедро заплатила"),
        ("фармацевт",       280, 620,  "💊", "смена прошла спокойно"),
        ("психолог",        320, 700,  "🧠", "сеанс прошёл удачно — клиент вернётся"),
        ("стилист",         220, 550,  "💇", "клиент был в восторге от результата"),
        ("флорист",         150, 400,  "🌸", "огромный букет ушёл с витрины"),
        ("спортсмен",       200, 600,  "⚽", "турнир выигран — призовые в кармане"),
        ("барист",          120, 350,  "☕", "смена без ошибок — чаевые на столе"),
        ("электрик",        250, 580,  "⚡", "ремонт завершён без замыканий"),
        ("сантехник",       200, 500,  "🔧", "труба починена, клиент доволен"),
        ("копирайтер",      180, 500,  "✍️", "текст одобрен с первого раза"),
        ("переводчик",      200, 520,  "🌐", "перевёл документы вовремя"),
        ("бухгалтер",       280, 620,  "🧾", "квартальный отчёт сдан без ошибок"),
        ("иллюзионист",     150, 700,  "🎩", "публика была в восторге от шоу"),
    ]
    work_cooldown[uid] = now
    # У каждой смены есть риск: работа не всегда приносит деньги.
    if random.random() < 0.15:
        fine = min(get_balance(uid), random.randint(30, 150))
        add_balance(uid, -fine)
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            f"💼 <b>Смена не задалась</b>\n\n"
            f"Ты допустил(а) ошибку на работе и оплатил(а) компенсацию.\n"
            f"💸 Потеряно: <b>{fmt_lmn(fine)} LMN</b>\n"
            f"💵 Баланс: <b>{fmt_lmn(get_balance(uid))} LMN</b>\n\n"
            f"⏳ Следующая работа через <b>60 мин</b>\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )
    job_data = random.choice(_jobs_tier)
    job, earn_min, earn_max, job_icon, job_phrase = job_data
    earned = random.randint(earn_min, earn_max)
    add_balance(uid, earned)
    new_bal = get_balance(uid)
    _work_intros = [
        "Вышел на смену и", "Поработал на славу —", "Отличная смена!",
        "Трудовые будни:", "Отчёт за смену:",
    ]
    await reply_t(
        msg,
        "work",
        job=job,
        earned=fmt_lmn(earned),
        balance=fmt_lmn(new_bal),
    )
    schedule_state_save("work")


@dp.message(Command("alchemy", "алхимия"))
async def cmd_alchemy(msg: Message):
    """Личная алхимия: превращает найденные реагенты в LMN с кулдауном."""
    uid = msg.from_user.id
    now = now_kyiv()
    last = alchemy_cooldown.get(uid)
    cooldown_minutes = 120
    if last and (now - last).total_seconds() < cooldown_minutes * 60:
        mins = cooldown_minutes - int((now - last).total_seconds()) // 60
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            f"⚗️ <b>Алхимическая лаборатория ещё работает</b>\n\n"
            f"Следующая варка будет доступна через <b>{max(1, mins)} мин</b>.\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )

    alchemy_cooldown[uid] = now
    recipes = [
        ("🌙", "Лунный эликсир", "собрал(а) росу с ночных цветов", 650, 1150),
        ("🔥", "Искра феникса", "усмирил(а) жаркое пламя в тигле", 800, 1450),
        ("💎", "Кристалл удачи", "очистил(а) редкий кристалл от примесей", 950, 1750),
        ("🌿", "Зелёный катализатор", "вырастил(а) живой катализатор", 500, 1000),
        ("⚡", "Грозовой раствор", "поймал(а) молнию в алхимическую колбу", 1100, 2100),
    ]
    icon, recipe, action, earn_min, earn_max = random.choice(recipes)
    earned = random.randint(earn_min, earn_max)
    add_balance(uid, earned)
    save_data()
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"⚗️ <b>LMN Алхимия</b>\n\n"
        f"{icon} <b>{recipe}</b>\n"
        f"<i>Ты {action} и получил(а) чистый результат.</i>\n\n"
        f"💰 Награда: <b>+{fmt_lmn(earned)} LMN</b>\n"
        f"💵 Баланс: <b>{fmt_lmn(get_balance(uid))} LMN</b>\n\n"
        f"⏳ Следующая варка через <b>2 ч</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )


@dp.message(Command("teamalchemy", "команднаяалхимия", "командаалхимия"))
async def cmd_team_alchemy(msg: Message):
    """Командная алхимия: три разных участника вместе завершают ритуал."""
    if msg.chat.type == "private":
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            "🧪 <b>Команда Алхимия работает только в групповом чате.</b>\n"
            "Позови друзей в общий чат и запусти ритуал там.\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )

    uid = msg.from_user.id
    cid = econ_cid(msg.chat.id)
    today = today_kyiv().isoformat()
    run = team_alchemy_runs.get(cid)
    if not run or run.get("date") != today:
        run = {"date": today, "participants": {}, "completed": False}
        team_alchemy_runs[cid] = run

    participants = run.setdefault("participants", {})
    if run.get("completed"):
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            "🧪 <b>Сегодняшний командный эликсир уже готов!</b>\n\n"
            "Новая команда алхимиков сможет начать ритуал завтра.\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )
    if uid in participants:
        waiting = max(0, 3 - len(participants))
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            "🧪 Ты уже добавил(а) свой ингредиент в общий котёл.\n\n"
            f"Участников: <b>{len(participants)}/3</b>\n"
            f"Нужно ещё: <b>{waiting}</b> разных участника(ов).\n"
            "Пусть следующий алхимик напишет <code>команда алхимия</code>.\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )

    participants[uid] = msg.from_user.full_name
    contribution = random.randint(220, 420)
    add_balance(uid, contribution)
    participant_names = list(participants.values())
    if len(participants) < 3:
        save_data()
        await msg.reply(
            f"{brand.hdr()}\n\n"
            "🧪 <b>Команда Алхимия — ингредиент принят!</b>\n\n"
            f"👤 Алхимиков в ритуале: <b>{len(participants)}/3</b>\n"
            f"💰 За вклад: <b>+{fmt_lmn(contribution)} LMN</b>\n"
            f"💵 Баланс: <b>{fmt_lmn(get_balance(uid))} LMN</b>\n\n"
            "Позови ещё "
            f"<b>{3 - len(participants)}</b> разных участника(ов), чтобы завершить эликсир.\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )

    completion_reward = random.randint(900, 1600)
    run["completed"] = True
    for participant_id in participants:
        add_balance(participant_id, completion_reward)
    save_data()
    names = ", ".join(html.escape(name) for name in participant_names)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        "🧪 <b>Команда Алхимия завершена!</b>\n\n"
        f"✨ {names} объединили ингредиенты и создали общий эликсир.\n\n"
        f"🏆 Командная награда: <b>+{fmt_lmn(completion_reward)} LMN</b> каждому\n"
        f"💰 Твой вклад: <b>+{fmt_lmn(contribution)} LMN</b>\n"
        f"💵 Твой баланс: <b>{fmt_lmn(get_balance(uid))} LMN</b>\n\n"
        "Новый ритуал откроется завтра.\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )


@dp.message(Command("fish"))
async def cmd_fish(msg: Message):
    uid = msg.from_user.id
    now = now_kyiv()
    last = fish_cooldown.get(uid)
    if last and (now - last).total_seconds() < 1800:
        mins = 30 - int((now - last).total_seconds()) // 60
        return await reply_t(msg, "fish_cooldown", mins=mins)
    fish_cooldown[uid] = now
    roll = random.random()
    # (эмодзи, название, мин, макс, комментарий)
    _catches = [
        (0.03, "🏆", "ЛЕГЕНДАРНЫЙ УЛОВ",  3000, 8000, "Такое бывает раз в год! Чат будет говорить об этом неделями"),
        (0.08, "🐋", "Кит на горизонте!", 1500, 3000, "Удача улыбнулась — продал в порту за огромные деньги"),
        (0.15, "🦈", "Акула!",            800,  1500, "Рыбаки из соседней деревни завидуют"),
        (0.30, "🐟", "Большая рыба",       300,  800,  "Отличный улов — рынок доволен"),
        (0.50, "🐠", "Хорошая рыбка",      100,  300,  "Небольшой, но стабильный заработок"),
        (0.68, "🐡", "Малёк",             20,   100,  "Маловато, но лучше, чем ничего"),
        (0.80, "🦀", "Краб",              50,   150,  "Вёрткий попался — почти ушёл!"),
        (0.88, "🐚", "Красивая ракушка",  10,   30,   "Продал туристам как сувенир"),
        (0.94, "🥫", "Консервная банка",  0,    0,    "Кто-то засорил пруд..."),
        (1.00, "👟", "Старый ботинок",    0,    0,    "Классика жанра. Рыбалка не задалась"),
    ]
    r = random.random()
    chosen = _catches[-1]
    for threshold, *rest in _catches:
        if r < threshold:
            chosen = (threshold, *rest)
            break
    _, icon, name, earn_min, earn_max, comment = chosen
    earned = random.randint(earn_min, earn_max) if earn_max > 0 else 0
    add_balance(uid, earned)
    new_bal = get_balance(uid)
    _intros = ["Закинул удочку...", "Рыбалка в разгаре...", "Ждал терпеливо и вот:"]
    result_line = f"<b>+{fmt_lmn(earned)} LMN</b>" if earned else "<i>Ничего не заработал 😔</i>"
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🎣 {random.choice(_intros)}\n\n"
        f"{icon} <b>{name}</b>\n"
        f"<i>{comment}</i>\n\n"
        f"💰 Улов: {result_line}\n"
        f"💵 Баланс: <b>{fmt_lmn(new_bal)} LMN</b>\n\n"
        f"⏳ Следующая рыбалка через <b>30 мин</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )
    schedule_state_save("fish")


@dp.message(Command("hunt", "охота"))
async def cmd_hunt(msg: Message):
    """Охота: рискованная экономическая команда с часовым кулдауном."""
    uid = msg.from_user.id
    now = now_kyiv()
    last = hunt_cooldown.get(uid)
    if last and (now - last).total_seconds() < 3600:
        mins = 60 - int((now - last).total_seconds()) // 60
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            f"🏹 Ты уже был(а) на охоте.\n\n"
            f"⏳ Следующая попытка через <b>{mins} мин</b>\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )

    hunt_cooldown[uid] = now
    roll = random.random()
    if roll < 0.05:
        icon, prey, earned, note = "🐉", "легендарного зверя", random.randint(2500, 5000), "О таком трофее будут говорить весь чат!"
    elif roll < 0.23:
        icon, prey, earned, note = "🦌", "крупную добычу", random.randint(700, 1500), "Отличная охота — трофей дорого оценили."
    elif roll < 0.60:
        icon, prey, earned, note = "🐇", "небольшую добычу", random.randint(180, 600), "Неплохой результат для одного похода."
    elif roll < 0.82:
        fine = min(get_balance(uid), random.randint(50, 220))
        add_balance(uid, -fine)
        schedule_state_save("hunt")
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            f"🏹 <b>Охота не удалась</b>\n\n"
            f"Ты вернулся(лась) без добычи и потратился(лась) на снаряжение.\n"
            f"💸 Потеряно: <b>{fmt_lmn(fine)} LMN</b>\n"
            f"💵 Баланс: <b>{fmt_lmn(get_balance(uid))} LMN</b>\n\n"
            f"⏳ Следующая охота через <b>60 мин</b>\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )
    else:
        schedule_state_save("hunt")
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            f"🏹 <b>Охота без добычи</b>\n\n"
            f"Следов было много, но зверь оказался хитрее. Сегодня без награды.\n\n"
            f"⏳ Следующая охота через <b>60 мин</b>\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )

    add_balance(uid, earned)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🏹 <b>Удачная охота!</b>\n\n"
        f"{icon} Ты добыл(а) <b>{prey}</b>.\n"
        f"💰 Награда: <b>+{fmt_lmn(earned)} LMN</b>\n"
        f"<i>{note}</i>\n"
        f"💵 Баланс: <b>{fmt_lmn(get_balance(uid))} LMN</b>\n\n"
        f"⏳ Следующая охота через <b>60 мин</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )
    schedule_state_save("hunt")


@dp.message(Command("casino"))
async def cmd_casino(msg: Message, command: CommandObject):
    if msg.chat.type != "private":
        return await msg.reply(
            f"🎰 Казино доступно только в личном чате с ботом.\n"
            f"Открой: <a href=\"{CASINO_BOT_URL}\">Lumena</a>",
            parse_mode="HTML",
        )
    _cur = brand.currency()
    if not command.args: return await msg.reply(brand.get_text("casino_no_bet"), parse_mode="HTML")
    try: bet = int(command.args.split()[0])
    except: return await msg.reply(brand.get_text("casino_invalid_bet"), parse_mode="HTML")
    if bet <= 0: return await msg.reply(brand.get_text("casino_negative_bet"), parse_mode="HTML")
    if get_balance(msg.from_user.id) < bet:
        return await msg.reply(brand.get_text("casino_no_balance", cur=_cur), parse_mode="HTML")
    uid = msg.from_user.id
    _casino_win_txt = [
        "удача улыбнулась 🎉", "сегодня твой день 🔥", "вот это повезло!",
        "казино плачет 😄", "фартовый(ая)!", "удача на твоей стороне!",
        "красота! монеты твои 💸", "сегодня везёт 🍀",
    ]
    _casino_loss_txt = [
        "не сегодня 😔", "казино не спит 😄", "бывает...",
        "попробуй ещё раз 🤞", "казино wins 😔", "в следующий раз повезёт",
        "эх, мимо 😅", "риск — благородное дело. но не сегодня",
    ]
    _casino_jackpot_txt = [
        "ТЫ СЛОМАЛ(А) КАЗИНО!! 💎", "это нереально!! x3 🎊🎊🎊",
        "ДЖЕКПОТ! администрация в шоке 👑", "невозможное возможно!! 🎊",
        "легенда чата! джекпот!! 🔥",
    ]
    roll = random.random()
    if roll < 0.45:
        win = bet
        add_balance(uid, win)
        result = f"🟢 ВЫИГРЫШ  +{fmt_lmn(win)} LMN"
        outcome = random.choice(_casino_win_txt)
    elif roll < 0.5:
        win = bet * 3
        add_balance(uid, win)
        result = f"💎 ДЖЕКПОТ  +{fmt_lmn(win)} LMN"
        outcome = random.choice(_casino_jackpot_txt)
    else:
        add_balance(uid, -bet)
        result = f"🔴 ПРОИГРЫШ  -{fmt_lmn(bet)} LMN"
        outcome = random.choice(_casino_loss_txt)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🎰 Казино\n\n"
        f"💰 Ставка: <b>{fmt_lmn(bet)} LMN</b>\n"
        f"🎲 {result}\n\n"
        f"✨ {outcome}\n"
        f"💵 Баланс: <b>{fmt_lmn(get_balance(uid))} LMN</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )
    schedule_state_save("casino")

@dp.message(Command("slots"))
async def cmd_slots(msg: Message, command: CommandObject):
    if msg.chat.type != "private":
        return await msg.reply(
            f"🎰 Слоты доступны только в личном чате с ботом.\n"
            f"Открой: <a href=\"{CASINO_BOT_URL}\">Lumena</a>",
            parse_mode="HTML",
        )
    _cur = brand.currency()
    if not command.args: return await msg.reply(brand.get_text("slots_no_bet"), parse_mode="HTML")
    try: bet = int(command.args.split()[0])
    except: return await msg.reply(brand.get_text("slots_invalid_bet"), parse_mode="HTML")
    if bet <= 0: return await msg.reply(brand.get_text("casino_negative_bet"), parse_mode="HTML")
    if get_balance(msg.from_user.id) < bet:
        return await msg.reply(brand.get_text("slots_no_balance", cur=_cur), parse_mode="HTML")
    _slots_jackpot_txt = [
        "ДЖЕКПОТ! ты что, читерил(а)?! 😱", "это невозможно!! 🎊",
        "барабаны в шоке 💎", "три в ряд!! легенда! 🔥",
        "вот это крутануло!! 🎰👑",
    ]
    _slots_pair_txt = [
        "пара есть — уже неплохо 😄", "почти! пара зачтена ✨",
        "два из трёх — уже победа 😊", "пара! монеты твои 💸",
        "неплохо! пара 🍀",
    ]
    _slots_miss_txt = [
        "мимо 😔 барабаны не в настроении", "не сегодня 😅",
        "крути ещё! 🎰", "казино смеётся 😄", "эх, промах...",
        "судьба сказала нет 😔", "барабаны решили иначе 😄",
    ]
    icons = ["🍒","🍋","🍊","🍇","⭐","💎","7️⃣"]
    s = [random.choice(icons) for _ in range(3)]
    line = " | ".join(s)
    uid = msg.from_user.id
    if s[0]==s[1]==s[2]:
        if s[0]=="💎": mult=10
        elif s[0]=="7️⃣": mult=7
        elif s[0]=="⭐": mult=5
        else: mult=3
        win = bet * mult
        add_balance(uid, win)
        result = f"💎 ДЖЕКПОТ x{mult}  +{fmt_lmn(win)} LMN"
        comment = random.choice(_slots_jackpot_txt)
    elif len(set(s))==2:
        win = bet
        add_balance(uid, win)
        result = f"✨ Пара  +{fmt_lmn(win)} LMN"
        comment = random.choice(_slots_pair_txt)
    else:
        add_balance(uid, -bet)
        result = f"😔 Промах  -{fmt_lmn(bet)} LMN"
        comment = random.choice(_slots_miss_txt)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🎰 Слоты\n\n"
        f"┃  {line}  ┃\n\n"
        f"🎲 {result}\n"
        f"💬 {comment}\n"
        f"💵 Баланс: <b>{fmt_lmn(get_balance(uid))} LMN</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

@dp.message(Command("rob"))
async def cmd_rob(msg: Message):
    _cur = brand.currency()
    if not msg.reply_to_message:
        return await msg.reply(brand.get_text("rob_no_reply"), parse_mode="HTML")
    robber = msg.from_user
    victim = msg.reply_to_message.from_user
    if victim.id == robber.id:
        return await msg.reply(brand.get_text("rob_self"), parse_mode="HTML")
    if victim.is_bot:
        return await msg.reply(brand.get_text("rob_bot"), parse_mode="HTML")
    # Перевіряємо баланс гаманця жертви ДО кулдауну — не витрачаємо спробу
    vic_bal  = get_balance(victim.id)
    vic_bank = get_bank(victim.id)
    if vic_bal < 100:
        if vic_bank > 0:
            return await msg.reply(
                f"{brand.hdr()}\n\n"
                f"🏦 <b>{html.escape(victim.full_name)}</b> зберіг(ла) монети в банку!\n\n"
                f"<i>Гаманець майже порожній, але банк захищений від ограбування.</i>\n\n"
                f"{brand.div()}",
                parse_mode="HTML",
            )
        return await msg.reply(brand.get_text("rob_target_poor"), parse_mode="HTML")
    now = now_kyiv()
    last = rob_cooldown.get(robber.id)
    if last and (now - last).total_seconds() < 7200:
        mins_left = 120 - int((now - last).total_seconds()) // 60
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            f"⏳ Полиция ещё ищет тебя!\n\n"
            f"Следующее ограбление через <b>{mins_left} мин</b>\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )
    rob_cooldown[robber.id] = now
    _rob_win_txt = [
        "тихо, быстро, чисто 🦹", "как в кино 😄 ограбление века",
        "жертва даже не заметила 🤫", "профессионально!",
        "стремительно и без следов 🕶",
        "мастер-класс по карманному делу 😄",
    ]
    _rob_fail_txt = [
        "схватили за руку 🚔", "охрана не спала 😅",
        "план провалился. штраф выписан 😔",
        "камеры везде! попался(лась) 📸",
        "жертва оказалась бывшим полицейским 😬",
        "не повезло. штрафуют 😔",
    ]
    if random.random() < 0.4:
        # Гарантируем корректный диапазон: минимум 50, но не больше трети баланса
        max_steal = max(50, min(vic_bal // 3, 5000))
        stolen = random.randint(1, max_steal)
        add_balance(victim.id, -stolen)
        add_balance(robber.id, stolen)
        comment = random.choice(_rob_win_txt)
        await msg.reply(
            f"{brand.hdr()}\n\n"
            f"🦹 Ограбление удалось!\n\n"
            f"🎯 Жертва: <b>{victim.full_name}</b>\n"
            f"💰 Украдено: <b>{fmt_lmn(stolen)} LMN</b>\n"
            f"💬 {comment}\n\n"
            f"{brand.div()}",
            parse_mode="HTML")
        # Уведомляем жертву
        try:
            await bot.send_message(
                msg.chat.id,
                f"😱 <b>{victim.full_name}</b>, тебя только что обокрал(а) <b>{robber.full_name}</b>!\n"
                f"Пропало: <b>{fmt_lmn(stolen)} LMN</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass
    else:
        robber_bal = get_balance(robber.id)
        fine = random.randint(100, 500)
        actual_fine = min(fine, robber_bal)
        add_balance(robber.id, -actual_fine)
        comment = random.choice(_rob_fail_txt)
        await msg.reply(
            f"{brand.hdr()}\n\n"
            f"👮 Попался!\n\n"
            f"💬 {comment}\n"
            f"💸 Штраф: <b>{fmt_lmn(actual_fine)} LMN</b>\n\n"
            f"{brand.div()}",
            parse_mode="HTML")

# ═══════════════════════════════════════════════════════
# БАНК — захист монет від ограбування
# ═══════════════════════════════════════════════════════
def get_bank(uid: int) -> int:
    return bank_balances.get(uid, 0)

async def _bank_card(msg: Message):
    uid    = msg.from_user.id
    wallet = get_balance(uid)
    vault  = get_bank(uid)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🏦 <b>Твой банк</b>\n\n"
        f"💳 Кошелёк: <b>{fmt_lmn(wallet)}</b> {brand.currency()}\n"
        f"🏦 В банке:  <b>{fmt_lmn(vault)}</b> {brand.currency()}\n"
        f"💰 Всего:    <b>{fmt_lmn(wallet + vault)}</b> {brand.currency()}\n\n"
        f"<i>Деньги в банке <b>нельзя украсть</b> через ограбление</i>\n\n"
        f"<code>сохранить</code> — перевести весь баланс в банк\n"
        f"<code>снять 1000</code> — вывести из банка\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def _bank_deposit(msg: Message, args_text: str = ""):
    uid    = msg.from_user.id
    wallet = get_balance(uid)
    # «сохранить» всегда кладёт в банк весь доступный баланс.
    # Аргументы игнорируются намеренно — это исключает частичные переводы.
    amount = wallet
    if amount <= 0:
        return await msg.reply(
            "❌ В кошельке нет монет, которые можно сохранить.",
            parse_mode="HTML",
        )
    add_balance(uid, -amount)
    bank_balances[uid] = get_bank(uid) + amount
    save_data()
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🏦 <b>Баланс сохранён!</b>\n\n"
        f"➕ В банк переведено: <b>{fmt_lmn(amount)}</b> {brand.currency()}\n"
        f"💳 Кошелёк: <b>{fmt_lmn(get_balance(uid))}</b>\n"
        f"🏦 В банке:  <b>{fmt_lmn(get_bank(uid))}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def _bank_withdraw(msg: Message, args_text: str = ""):
    uid   = msg.from_user.id
    vault = get_bank(uid)
    now   = now_kyiv()
    # Кулдаун 2 часа — чтобы нельзя было мгновенно вывести деньги при ограблении
    last_wd = bank_withdraw_cd.get(uid)
    if last_wd and (now - last_wd).total_seconds() < 7200:
        mins = 120 - int((now - last_wd).total_seconds()) // 60
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            f"⏳ Следующее снятие через <b>{mins} мин</b>\n\n"
            f"<i>Кулдаун защищает от мгновенного вывода при ограблении</i>\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )
    raw = args_text.strip().replace(" ", "").replace(",", "")
    if raw.lower() in ("все", "all", "усе", "max"):
        amount = vault
    elif raw.isdigit():
        amount = int(raw)
    else:
        return await msg.reply(
            f"{brand.hdr()}\n\n🏦 <b>Снятие из банка</b>\n\n"
            f"🏦 В банке: <b>{fmt_lmn(vault)}</b>\n\n"
            f"Укажи сумму: <code>снять 1000</code> или <code>снять всё</code>\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )
    if amount <= 0:
        return await msg.reply("❌ Сумма должна быть больше 0.", parse_mode="HTML")
    if amount > vault:
        return await msg.reply(
            f"❌ В банке только <b>{fmt_lmn(vault)}</b> {brand.currency()}",
            parse_mode="HTML",
        )
    bank_balances[uid] = vault - amount
    add_balance(uid, amount)
    bank_withdraw_cd[uid] = now
    save_data()
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🏦 <b>Снятие выполнено!</b>\n\n"
        f"➖ Снято: <b>{fmt_lmn(amount)}</b> {brand.currency()}\n"
        f"💳 Кошелёк: <b>{fmt_lmn(get_balance(uid))}</b>\n"
        f"🏦 В банке:  <b>{fmt_lmn(get_bank(uid))}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

@dp.message(Command("bank", "банк"))
async def cmd_bank_slash(msg: Message):
    await _bank_card(msg)

@dp.message(Command("save", "сохранить"))
async def cmd_deposit_slash(msg: Message, command: CommandObject = None):
    await _bank_deposit(msg)

@dp.message(Command("withdraw", "снять", "вывести"))
async def cmd_withdraw_slash(msg: Message, command: CommandObject = None):
    await _bank_withdraw(msg, (command.args or "") if command else "")


@dp.message(Command("richest"))
async def cmd_richest(msg: Message):
    _cur = brand.currency()
    empty_msg = brand.get_text("richest_empty")
    # Объединяем кошельки + банк для полного богатства
    all_uids = set(lmn_balances) | set(bank_balances)
    if not all_uids: return await msg.reply(empty_msg, parse_mode="HTML")
    chat_uids = chat_members.get(msg.chat.id, set())
    if chat_uids:
        all_uids = all_uids & chat_uids
    if not all_uids:
        return await msg.reply(empty_msg, parse_mode="HTML")
    totals = {uid: lmn_balances.get(uid, 0) + bank_balances.get(uid, 0) for uid in all_uids}
    top = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:10]
    medals = ["🥇","🥈","🥉"] + ["4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines = [
        f"{brand.hdr()}\n",
        brand.get_text("richest_header"),
        f"{brand.div()}",
    ]
    for i, (uid, total) in enumerate(top):
        try:
            m = await bot.get_chat_member(msg.chat.id, uid)
            name = html.escape(m.user.full_name)
        except: name = f"ID {uid}"
        wallet = lmn_balances.get(uid, 0)
        bank   = bank_balances.get(uid, 0)
        detail = f" (🏦{fmt_lmn(bank)})" if bank > 0 else ""
        lines.append(f"{medals[i]} <b>{name}</b>  —  {fmt_lmn(wallet)} {_cur}{detail}")
    lines.append(f"\n{brand.div()}")
    lines.append(brand.get_text("richest_total", total=fmt_lmn(sum(totals.values())), cur=_cur))
    await msg.reply("\n".join(lines), parse_mode="HTML")

@dp.message(Command("givetoadmins"))
async def cmd_givetoadmins(msg: Message):
    if not is_super(msg): return await msg.reply("⛔ Только фаундер или суперпользователь")
    try:
        admins = await bot.get_chat_administrators(msg.chat.id)
        lines = []
        for admin in admins:
            if admin.user.is_bot:
                continue
            add_balance(admin.user.id, 2_000_000)
            # Определяем роль
            title = (getattr(admin, "custom_title", None) or "").strip()
            if admin.status == ChatMemberStatus.CREATOR:
                role = "👑 Фаундер"
            elif title:
                role = f"🔰 {title}"
            else:
                role = "🛡 Админ"
            lines.append(f"{role} — {admin.user.full_name}")
        count = len(lines)
        roster = "\n".join(lines) if lines else "—"
        await msg.reply(
            f"💰 <b>Раздача 2 000 000 LMN</b> ({count} чел.):\n\n{roster}",
            parse_mode="HTML"
        )
    except Exception as e: await msg.reply(f"❌ {e}")

async def cmd_award(msg: Message, command: CommandObject = None):
    """Фаундер даёт монеты юзеру по @username и пишет сообщение с упоминанием."""
    if not is_owner(msg):
        return await msg.reply("⛔ Только фаундер")
    if not (command and command.args):
        return await msg.reply(
            "Использование: <b>наградить @username [сумма] [текст]</b>\n"
            "Пример: <i>наградить @VladMish11 300000000000000 за лучшую роль клоуна</i>",
            parse_mode="HTML"
        )

    parts = command.args.strip().split(maxsplit=2)
    if len(parts) < 2:
        return await msg.reply("❌ Укажи @username и сумму")

    raw_username = parts[0].lstrip("@")
    try:
        amount = int(parts[1])
    except ValueError:
        return await msg.reply("❌ Сумма должна быть целым числом")
    if amount <= 0:
        return await msg.reply("❌ Сумма должна быть больше нуля")
    custom_text = parts[2] if len(parts) > 2 else ""

    # Ищем юзера — сначала в администраторах чата, затем через Telegram API
    target_id: int | None = None
    target_name: str = raw_username

    try:
        admins = await bot.get_chat_administrators(msg.chat.id)
        for a in admins:
            if (a.user.username or "").lower() == raw_username.lower():
                target_id = a.user.id
                target_name = a.user.full_name
                break
    except Exception:
        pass

    # Если не нашли среди админов — ищем в chat_members
    if target_id is None:
        for uid, name in chat_members.get(msg.chat.id, {}).items():
            # chat_members хранит full_name, username там нет — пробуем через get_chat_member
            pass

    # Попытка через Telegram API по username
    if target_id is None:
        try:
            chat_info = await bot.get_chat(f"@{raw_username}")
            target_id = chat_info.id
            target_name = chat_info.full_name or raw_username
        except Exception:
            pass

    if target_id is None:
        return await msg.reply(
            f"❌ Не удалось найти пользователя <b>@{raw_username}</b>.\n"
            f"Убедись что он писал в чате или что username указан верно.",
            parse_mode="HTML"
        )

    add_balance(target_id, amount)
    # Добавляем в базу участников чата
    chat_members.setdefault(msg.chat.id, {})[target_id] = target_name
    save_data()

    mention = f'<a href="tg://user?id={target_id}">{target_name}</a>'
    text_part = f" {custom_text}" if custom_text else ""
    await msg.answer(
        f"🏆 {mention}{text_part}!\n"
        f"💰 Начислено: <b>{fmt_lmn(amount)} LMN</b>",
        parse_mode="HTML"
    )

async def cmd_give_role(msg: Message, command: CommandObject = None):
    """Фаундер начисляет монеты всем с определённой ролью (custom_title)."""
    if not is_owner(msg):
        return await msg.reply("⛔ Только фаундер")
    if not (command and command.args):
        return await msg.reply(
            "Использование: <b>выдатьроли [роль] [сумма]</b>\n"
            "Пример: <i>выдатьроли модератор 300000000000000</i>",
            parse_mode="HTML"
        )
    parts = command.args.strip().split()
    if len(parts) < 2:
        return await msg.reply("❌ Укажи роль и сумму. Пример: выдатьроли модератор 5000")
    role_query = parts[0].lower()
    try:
        amount = int(parts[1])
    except ValueError:
        return await msg.reply("❌ Сумма должна быть целым числом")
    if amount <= 0:
        return await msg.reply("❌ Сумма должна быть больше нуля")

    try:
        admins = await bot.get_chat_administrators(msg.chat.id)
    except Exception as e:
        return await msg.reply(f"❌ Не удалось получить список администраторов: {e}")

    matched = []
    for a in admins:
        if a.user.is_bot:
            continue
        title = (getattr(a, "custom_title", None) or "").strip().lower()
        if title == role_query:
            add_balance(a.user.id, amount)
            matched.append(a.user.full_name)

    if not matched:
        return await msg.reply(
            f"⚠️ Никого с ролью <b>{parts[0]}</b> не найдено среди администраторов.",
            parse_mode="HTML"
        )

    save_data()
    names = "\n".join(f"• {n}" for n in matched)
    await msg.reply(
        f"💰 <b>Начислено!</b>\n"
        f"Роль: <b>{parts[0]}</b>\n"
        f"Сумма: <b>{fmt_lmn(amount)} LMN</b>\n\n"
        f"Получили:\n{names}",
        parse_mode="HTML"
    )

async def cmd_razdach(msg: Message, command: CommandObject = None):
    """Фаундер раздаёт всем участникам чата одинаковое количество монет."""
    if not is_owner(msg):
        return await msg.reply("⛔ Только фаундер")
    if not (command and command.args):
        return await msg.reply(
            "💰 Использование: <b>раздать [сумма]</b>\n"
            "Пример: <i>раздать 5000</i> — все участники чата получат по 5 000 LMN",
            parse_mode="HTML"
        )

    args = command.args.strip().split()
    # Пропускаем необязательное слово «всем»
    if args and args[0].lower() == "всем":
        args = args[1:]
    if not args:
        return await msg.reply("❌ Укажи сумму. Пример: раздать 5000")
    try:
        amount = int(args[0])
    except ValueError:
        return await msg.reply("❌ Укажи целое число. Пример: раздать 5000")
    if amount <= 0:
        return await msg.reply("❌ Сумма должна быть больше нуля")

    chat_id = msg.chat.id

    # Подтягиваем всех администраторов из Telegram API
    creator_id: int | None = None
    try:
        admins = await bot.get_chat_administrators(chat_id)
        for a in admins:
            if a.user.is_bot:
                continue
            if a.status == ChatMemberStatus.CREATOR:
                creator_id = a.user.id
            # Добавляем в базу участников чата
            chat_members.setdefault(chat_id, {})[a.user.id] = a.user.full_name
    except Exception:
        pass

    # Объединяем: участники из базы (писали сообщения) + только что загруженные админы
    uids_in_chat: dict[int, str] = dict(chat_members.get(chat_id, {}))

    if not uids_in_chat:
        return await msg.reply(
            "⚠️ Пока никто не попал в базу этого чата.\n"
            "Участники добавляются автоматически, когда пишут сообщения."
        )

    # Исключаем создателя чата
    recipients = {uid: name for uid, name in uids_in_chat.items() if uid != creator_id}

    if not recipients:
        return await msg.reply("⚠️ Нет участников для раздачи (кроме создателя)")

    for uid in recipients:
        add_balance(uid, amount)

    save_data()
    names_list = "\n".join(f"• {name}" for name in recipients.values())
    await msg.reply(
        f"🎁 <b>Раздача завершена!</b>\n"
        f"Каждый получил: <b>{fmt_lmn(amount)} LMN</b>\n\n"
        f"<b>Получили ({len(recipients)} чел.):</b>\n{names_list}"
        + (f"\n\n<i>Создатель чата исключён</i>" if creator_id else ""),
        parse_mode="HTML"
    )

# ═══════════════════════════════════════════════════════
# РЕПУТАЦИЯ
# ═══════════════════════════════════════════════════════
@dp.message(Command("aura"))
async def cmd_aura(msg: Message):
    """Показывает ауру пользователя (0–100%)."""
    target = msg.reply_to_message.from_user if msg.reply_to_message else msg.from_user
    pct = get_aura(target.id)
    bar = aura_bar(pct)
    tier = (
        "💫 Светлая" if pct >= 80 else
        "🌟 Высокая"  if pct >= 60 else
        "⭐ Средняя"  if pct >= 40 else
        "🌑 Низкая"   if pct >= 10 else
        "💀 Тёмная"
    )
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"✨ Аура\n\n"
        f"👤 <b>{target.full_name}</b>\n"
        f"{brand.div()}\n"
        f"<code>{bar}</code>\n"
        f"📊 <b>{pct:.2f}%</b>  —  {tier}\n\n"
        f"<i>+0.01% за каждый 👍 на твои сообщения\n"
        f"−1% за агрессию в чате</i>\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )


@dp.message(Command("topaura"))
async def cmd_topaura(msg: Message):
    """Топ-10 пользователей по ауре."""
    if not aura:
        return await msg.reply("Аура ещё никем не набрана 🌑")
    top = sorted(aura.items(), key=lambda x: x[1], reverse=True)[:10]
    medals = ["🥇","🥈","🥉"] + ["4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines = [f"{brand.hdr()}\n", "✨ Топ ауры", f"{brand.div()}"]
    for i, (uid, pct) in enumerate(top):
        try:
            m = await bot.get_chat_member(msg.chat.id, uid)
            name = html.escape(m.user.full_name)
        except Exception:
            name = f"ID {uid}"
        lines.append(f"{medals[i]} <b>{name}</b>  —  {pct:.2f}%")
    lines.append(f"\n{brand.div()}")
    await msg.reply("\n".join(lines), parse_mode="HTML")


@dp.message(Command("rep"))
async def cmd_rep(msg: Message):
    target = msg.reply_to_message.from_user if msg.reply_to_message else msg.from_user
    r = get_rep(msg.chat.id, target.id)
    emoji = "⭐" if r >= 0 else "💀"
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"{emoji} Репутация\n\n"
        f"👤 <b>{target.full_name}</b>\n"
        f"📊 Рейтинг: <b>{r:+d}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML")

@dp.message(Command("upvote"))
async def cmd_upvote(msg: Message):
    if not msg.reply_to_message: return await msg.reply("Ответь на сообщение")
    target = msg.reply_to_message.from_user
    if target.id == msg.from_user.id: return await msg.reply("Себе нельзя 😄")
    vote_key = (msg.chat.id, msg.from_user.id, target.id)
    prev = rep_votes.get(vote_key)
    if prev == 1:
        return await msg.reply("⚠️ Ты уже поднял репутацию этому пользователю сегодня")
    delta = 2 if prev == -1 else 1   # отменяем старый минус + добавляем плюс
    if prev == -1:
        add_rep(msg.chat.id, target.id, 2)
    else:
        add_rep(msg.chat.id, target.id, 1)
    rep_votes[vote_key] = 1
    total = get_rep(msg.chat.id, target.id)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"⬆️ +1 репутация{' (голос изменён)' if prev == -1 else ''}\n\n"
        f"👤 <b>{html.escape(target.full_name)}</b>\n"
        f"📊 Итого: <b>{total:+d}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML")

@dp.message(Command("downvote"))
async def cmd_downvote(msg: Message):
    if not msg.reply_to_message: return await msg.reply("Ответь на сообщение")
    target = msg.reply_to_message.from_user
    if target.id == msg.from_user.id: return await msg.reply("Себе нельзя 😄")
    vote_key = (msg.chat.id, msg.from_user.id, target.id)
    prev = rep_votes.get(vote_key)
    if prev == -1:
        return await msg.reply("⚠️ Ты уже опустил репутацию этому пользователю сегодня")
    if prev == 1:
        add_rep(msg.chat.id, target.id, -2)
    else:
        add_rep(msg.chat.id, target.id, -1)
    rep_votes[vote_key] = -1
    total = get_rep(msg.chat.id, target.id)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"⬇️ -1 репутация{' (голос изменён)' if prev == 1 else ''}\n\n"
        f"👤 <b>{html.escape(target.full_name)}</b>\n"
        f"📊 Итого: <b>{total:+d}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML")

@dp.message(Command("toprep"))
async def cmd_toprep(msg: Message):
    chat_rep = reputation.get(econ_cid(msg.chat.id), {})
    if not chat_rep: return await msg.reply("Репутация ещё не начислена")
    top = sorted(chat_rep.items(), key=lambda x: x[1], reverse=True)[:10]
    medals = ["🥇","🥈","🥉"] + ["4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines = [
        f"{brand.hdr()}\n",
        "⭐ Топ репутации",
        f"{brand.div()}",
    ]
    for i, (uid, r) in enumerate(top):
        try:
            m = await bot.get_chat_member(msg.chat.id, uid)
            name = html.escape(m.user.full_name)
        except: name = f"ID {uid}"
        lines.append(f"{medals[i]} <b>{name}</b>  —  {r:+d}")
    lines.append(f"\n{brand.div()}")
    await msg.reply("\n".join(lines), parse_mode="HTML")

# ═══════════════════════════════════════════════════════
# СОЦИАЛЬНЫЕ ДЕЙСТВИЯ
# ═══════════════════════════════════════════════════════
def social(action: str, emoji: str, variants: list[str]):
    async def handler(msg: Message):
        target = msg.reply_to_message.from_user.first_name if msg.reply_to_message else "всех"
        await msg.reply(f"{emoji} {msg.from_user.first_name} {random.choice(variants)} {target}!")
    return handler

_ACTIONS = {
    "hug": ("🤗", ["обнял(а)", "крепко обнял(а)", "тепло обнял(а)"]),
    "kiss": ("😘", ["поцеловал(а)", "нежно поцеловал(а)"]),
    "pat": ("👋", ["погладил(а)", "потрепал(а) по голове"]),
    "bite": ("😬", ["укусил(а)", "слегка укусил(а)"]),
    "slap": ("👋", ["шлёпнул(а)", "дал(а) пощёчину"]),
    "gift": ("🎁", ["подарил(а) что-то", "подарил(а) подарок"]),
    "throw": ("🎯", ["бросил(а) что-то в", "кинул(а) снежком в"]),
    "dance": ("💃", ["станцевал(а) с", "закружился(ась) в танце с"]),
    "cry": ("😢", ["заплакал(а) рядом с", "расплакался(ась) из-за"]),
    "laugh": ("😂", ["захохотал(а) над", "засмеялся(ась) вместе с"]),
    "poke": ("👉", ["ткнул(а) пальцем", "щёлкнул(а) по носу"]),
    "highfive": ("🙌", ["дал(а) пять", "обменялся(ась) рукопожатием с"]),
    "stare": ("👀", ["уставился(ась) на", "долго смотрел(а) на"]),
    "wave": ("👋", ["помахал(а) рукой", "поприветствовал(а)"]),
    "facepalm": ("🤦", ["сделал(а) фейспалм из-за", "схватился(ась) за голову из-за"]),
}

async def cmd_hug(msg: Message):
    t = msg.reply_to_message.from_user.first_name if msg.reply_to_message else "всех"
    await reply_t(msg, "hug", from_name=msg.from_user.first_name, to_name=t)

async def cmd_kiss(msg: Message):
    if not msg.reply_to_message:
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            f"💋 Поцелуй\n\n"
            f"<i>Ответь на сообщение того, кого хочешь поцеловать</i>\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )
    await reply_t(msg, "kiss",
        from_name=msg.from_user.first_name,
        to_name=msg.reply_to_message.from_user.first_name)

async def cmd_bite(msg: Message):
    t = msg.reply_to_message.from_user.first_name if msg.reply_to_message else "кого-то"
    await reply_t(msg, "bite", from_name=msg.from_user.first_name, to_name=t)

async def cmd_pat(msg: Message):
    t = msg.reply_to_message.from_user.first_name if msg.reply_to_message else "кого-то"
    await reply_t(msg, "pat", from_name=msg.from_user.first_name, to_name=t)

async def cmd_slap(msg: Message):
    t = msg.reply_to_message.from_user.first_name if msg.reply_to_message else "кого-то"
    await reply_t(msg, "slap", from_name=msg.from_user.first_name, to_name=t)

async def cmd_gift(msg: Message):
    gifts = ["🌹 розу","🍫 шоколад","💎 кольцо","🎮 игру","📚 книгу","🎵 плейлист"]
    t = msg.reply_to_message.from_user.first_name if msg.reply_to_message else "кому-то"
    await reply_t(msg, "gift",
        from_name=msg.from_user.first_name,
        to_name=t,
        item=random.choice(gifts))

async def cmd_dance(msg: Message):
    t = msg.reply_to_message.from_user.first_name if msg.reply_to_message else "один(одна)"
    await reply_t(msg, "dance", from_name=msg.from_user.first_name, to_name=t)

async def cmd_poke(msg: Message):
    t = msg.reply_to_message.from_user.first_name if msg.reply_to_message else "кого-то"
    await reply_t(msg, "poke", from_name=msg.from_user.first_name, to_name=t)

async def cmd_highfive(msg: Message):
    t = msg.reply_to_message.from_user.first_name if msg.reply_to_message else "всех"
    await reply_t(msg, "highfive", from_name=msg.from_user.first_name, to_name=t)

async def cmd_wave(msg: Message):
    t = msg.reply_to_message.from_user.first_name if msg.reply_to_message else "всем"
    await reply_t(msg, "wave", from_name=msg.from_user.first_name, to_name=t)

async def cmd_facepalm(msg: Message):
    t = msg.reply_to_message.from_user.first_name if msg.reply_to_message else "из-за всего"
    await reply_t(msg, "facepalm", from_name=msg.from_user.first_name, to_name=t)

# ═══════════════════════════════════════════════════════
# ПРЕДСКАЗАНИЯ / РАЗВЛЕЧЕНИЯ
# ═══════════════════════════════════════════════════════
FORTUNES = [
    "Сегодня тебя ждёт приятный сюрприз 🌟",
    "Будь осторожен с новыми знакомствами — не всё то золото, что блестит",
    "Звёзды говорят: действуй смелее, время на твоей стороне!",
    "Хороший день для нового начала — сделай первый шаг",
    "Кто-то думает о тебе прямо сейчас 💭",
    "Не бойся перемен — они приходят к лучшему ✨",
    "Сегодня лучше молчать и наблюдать — мудрость в паузе",
    "Тебя ждёт маленькая победа, которая придаст сил 🏆",
    "Удача сегодня на твоей стороне — используй момент 🍀",
    "Будь готов к неожиданным новостям — они могут изменить планы",
    "Твои усилия скоро принесут плоды 🌱",
    "Доверяй интуиции — она знает больше, чем кажется 🔮",
    "Сегодня хороший день, чтобы попросить о помощи",
    "Кто-то в твоём окружении нуждается в твоих словах поддержки",
    "Не откладывай важный разговор — время пришло 💬",
    "Успех придёт к тому, кто умеет ждать ⏳",
    "Маленький шаг сегодня — большая победа завтра 🚀",
    "Обрати внимание на знаки — вселенная подсказывает путь",
    "Твоя улыбка сегодня изменит чей-то день ☀️",
    "Отпусти то, что уже не служит тебе — освободи место для нового",
    "День наполнен скрытыми возможностями — будь внимателен 👁",
    "Важное решение лучше принять утром, на свежую голову",
    "Сегодня звёзды благоволят творчеству и вдохновению 🎨",
    "Не сравнивай свой путь с чужим — у каждого свой ритм",
    "Старый друг может преподнести сюрприз 🎁",
    "Береги энергию — впереди более важные дела",
    "Везение приходит к тем, кто готов его встретить 🌠",
    "Твои мысли сейчас особенно сильны — думай о хорошем",
    "Риск сегодня оправдан — смелость города берёт ⚔️",
    "Завтра будет лучше, чем вчера. Обещано звёздами ⭐",
    # --- v7 дополнения ---
    "Сегодняшний день открывает двери, которые долго были закрыты 🚪",
    "Прислушайся к тишине — там скрыты самые важные ответы 🌙",
    "Вселенная расставляет всё на свои места — доверяй процессу",
    "Тот, кто верит в себя, уже на полпути к успеху 💫",
    "Неожиданная встреча сегодня изменит твои планы к лучшему",
    "Сила в тебе уже есть — просто позволь ей проявиться 🦁",
    "Сегодня твои слова несут особую силу — выбирай их мудро 🗣️",
    "Новые горизонты открываются тем, кто не боится двигаться вперёд 🌅",
    "То, что кажется препятствием, на самом деле — трамплин 🎯",
    "Время работает на тебя — терпение и настойчивость победят",
    "Чудеса случаются с теми, кто в них верит ✨",
    "Твой следующий шаг важнее тысячи прошлых мыслей — сделай его",
    "Сегодня — лучший день, чтобы простить и отпустить 🕊️",
    "Вдохновение ищет тебя прямо сейчас — будь открыт к нему",
    "Маленькая радость сегодня — фундамент большого счастья завтра 🌸",
    "Ты ближе к цели, чем кажется — продолжай идти 🚶",
    "Сегодня кто-то скажет тебе именно то, что нужно услышать 💬",
    "Луна благоволит решительным действиям этой ночью 🌙",
    "Твоя интуиция сейчас острее, чем обычно — прислушайся к ней",
    "Забота о себе сегодня — это инвестиция в завтра 💙",
    "Смотри не на проблему, а на решение — и оно найдётся 🔑",
    "Сегодня твои руки создадут что-то, что останется надолго 🎨",
    "Будь мягче к себе — ты делаешь всё, что можешь 🤍",
    "Звёзды выстраиваются в твою пользу — действуй без промедления ⭐",
    "Разговор, которого ты избегал, принесёт освобождение 💬",
    "Природа напомнит тебе сегодня о главном — побудь на воздухе 🌿",
    "Твоё имя произносят с уважением там, где ты этого не ожидаешь",
    "Сегодня — день неожиданных союзников и приятных совпадений",
    "Отдых сегодня — это не слабость, а мудрость 🛌",
    "Что-то, что ты потерял, скоро вернётся в новом обличии 🔄",
    "Твоя уникальность — это твоя главная сила, не скрывай её 🌈",
    "Сегодня благоприятно для финансовых решений — думай наперёд 💰",
    "Смелость быть собой притягивает правильных людей 🧲",
    "Неожиданная новость изменит твои планы — к лучшему, обещаем",
    "Твои прошлые трудности сделали тебя именно тем, кто нужен здесь и сейчас",
    "Сегодня — время завершать начатое, а не откладывать ✅",
    "Кто-то рядом нуждается в твоей поддержке больше, чем показывает",
    "Мир больше, чем твои страхи — выйди за их пределы 🌍",
    "Твоя настойчивость в последние дни скоро окупится сторицей 💎",
]

PREDICTIONS = [
    "Да, и это произойдёт быстрее, чем ты думаешь 🌟",
    "Нет — но не огорчайся, вселенная приготовила кое-что лучше 🌙",
    "Всё указывает на положительный исход — действуй смело ✨",
    "Пока рано — подожди три дня и спроси снова ⏳",
    "Это случится, но только если ты сделаешь первый шаг 🚀",
    "Звёзды молчат — значит, ответ в твоих руках 🤲",
    "Определённо да — но путь будет не прямым 🌀",
    "Сомневайся меньше, действуй больше — и получишь своё 💪",
    "Не сейчас, но желание правильное — береги его 💙",
    "Вселенная говорит «да», но просит немного терпения 🕰️",
    "Это уже начинается — просто незаметно для тебя пока 🌱",
    "Ответ придёт во сне — прислушайся к подсознанию 💭",
    "Да, если ты готов отпустить старое 🕊️",
    "Путь есть, но он требует смелости — решишься? ⚔️",
    "Очень вероятно — судьба уже работает в твою сторону 🎯",
    "Нет прямого пути, но обходной ведёт к тому же результату 🗺️",
    "Звёзды говорят: да, но не торопи события 🌌",
    "Это твоё — просто ещё не время брать 👑",
    "Знак свыше: делай, не думай слишком долго 🔥",
    "Ответ скрыт внутри тебя — медитируй или просто помолчи 🧘",
    "Да, если рядом окажется нужный человек — ищи его 🤝",
    "Вселенная проверяет серьёзность твоих намерений — докажи ей 💎",
    "Всё складывается, как надо — даже то, что кажется помехой 🌈",
    "Твоё желание уже услышано — дай ему воплотиться 🌸",
    "Абсолютно да — это давно предначертано для тебя ⭐",
]

EIGHT_BALL = [
    "Да ✅",
    "Нет ❌",
    "Возможно 🤔",
    "Скорее да 👍",
    "Скорее нет 👎",
    "Спроси позже ⏳",
    "Точно да! 🎯",
    "Даже не думай 🚫",
    "50/50 ⚖️",
    "Всё указывает на да 🌟",
    "Мои источники говорят — нет 🔮",
    "Без сомнений — да! 💯",
    "Очень сомнительно 😬",
    "Лучше не рассчитывай на это 🙅",
    "Знаки указывают на да ✨",
    "Мой ответ — нет, и я твёрд в этом 🗿",
    "Это выглядит хорошо! 🙌",
    "Не могу предсказать сейчас 🌫",
    "Сконцентрируйся и спроси ещё раз 🧘",
    "Определённо нет 🚫",
    "Как ни посмотри — да! 🎉",
    "Мне видится — нет 🌑",
    # --- v7 дополнения ---
    "Вселенная шепчет «да» — прислушайся 🌌",
    "Не в этот раз, но скоро — обязательно 🌠",
    "Всё возможно для того, кто верит 💫",
    "Шары говорят: очень хороший знак! 🎱",
    "Туман неопределённости — подожди ясности 🌫️",
    "Судьба говорит да, но с оговорками ⚠️",
    "Энергия вокруг тебя говорит нет 🌑",
    "Ответ рядом — просто ещё не время его видеть 🕰️",
    "Совпадения говорят: да, иди вперёд! 🔥",
    "Не сейчас — лучший момент ещё впереди ⭐",
    "Интуиция подсказывает: да, без сомнений 🧿",
    "Магия восьмёрки молчит — решай сам 🎱",
    "Путь открыт — действуй! 🚀",
]

TAROT = [
    ("Шут",              "Новые начинания, безрассудная смелость, дух свободы и авантюризма. Самое время рискнуть!"),
    ("Маг",              "Воля и мастерство. У тебя есть всё необходимое для воплощения задуманного — действуй."),
    ("Верховная Жрица",  "Интуиция, тайное знание, внутренний голос. Прислушайся к себе — ответ уже внутри."),
    ("Императрица",      "Плодородие, творчество, изобилие. Время заботиться о себе и создавать что-то прекрасное."),
    ("Император",        "Власть, стабильность, порядок. Возьми ситуацию под контроль — ты справишься."),
    ("Иерофант",         "Традиции, духовное руководство, мудрость наставника. Ищи совета у опытных людей."),
    ("Влюблённые",       "Выбор, союз, гармония. Важное решение в отношениях или ценностях ждёт тебя."),
    ("Колесница",        "Победа через решимость и контроль. Не сдавайся — ты на пути к успеху."),
    ("Сила",             "Внутреннее мужество, терпение, укрощение страстей. Твоя сила — в мягкости и выдержке."),
    ("Отшельник",        "Уединение, поиск истины, внутренняя мудрость. Пора взять паузу и разобраться в себе."),
    ("Колесо Фортуны",   "Цикличность, перемены, удача. Колесо поворачивается — будь готов к сюрпризам судьбы."),
    ("Справедливость",   "Баланс, честность, закономерные последствия. Получишь именно то, что заслужил."),
    ("Повешенный",       "Жертва ради роста, новый взгляд, необходимая пауза. Иногда отступить — мудрее, чем идти вперёд."),
    ("Смерть",           "Трансформация, конец одного и начало другого. Не бойся — это обновление, не потеря."),
    ("Умеренность",      "Баланс, терпение, гармония. Избегай крайностей — золотая середина приведёт к цели."),
    ("Дьявол",           "Искушение, зависимость, скрытые страхи. Пора разглядеть цепи, которые держат тебя."),
    ("Башня",            "Внезапные перемены, крушение иллюзий, очищающее откровение. После шторма — ясность."),
    ("Звезда",           "Надежда, вдохновение, исцеление. Даже в темноте звёзды светят — верь в лучшее."),
    ("Луна",             "Иллюзии, подсознание, неопределённость. Не всё, что видишь — правда. Доверяй инстинктам."),
    ("Солнце",           "Радость, успех, жизненная сила. Прекрасный знак — впереди светлая полоса!"),
    ("Суд",              "Пробуждение, переоценка ценностей, новый этап жизни. Время подвести итоги и двигаться дальше."),
    ("Мир",              "Завершение, целостность, заслуженный триумф. Ты прошёл долгий путь — пора праздновать!"),
]

HOROSCOPES: dict[str, list[str]] = {
    "Овен":      ["Энергия бьёт через край — используй её для начинания новых дел. Конфликтов сегодня лучше избегать.",
                  "День благоприятен для физической активности и спорта. В делах полагайся на собственный опыт.",
                  "Импульсивные решения могут навредить — сделай паузу перед важным шагом. Удача в общении.",
                  "Отличный день для лидерства и инициативы. Люди потянутся к твоей энергии.",
                  "Огонь Овна сегодня особенно ярок — зажги им тех, кто рядом. Удача в новых начинаниях.",
                  "Смелость сегодня вознаграждается. Не жди разрешения — просто действуй! 🔥"],
    "Телец":     ["Финансовые дела складываются благоприятно. Не торопи события — всё придёт в своё время.",
                  "Уют и комфорт важны сегодня. Побалуй себя чем-то приятным — ты заслужил(а).",
                  "Упрямство сегодня ни к чему — попробуй услышать другую точку зрения.",
                  "День для практических дел и планирования. Твой трудолюбивый подход принесёт плоды.",
                  "Красота и природа восстановят твои силы. Выйди на прогулку и вдохни полной грудью 🌿",
                  "Твоя надёжность сегодня будет оценена по достоинству — люди тянутся к стабильности. 💙"],
    "Близнецы":  ["Общение сегодня на высоте — заведи новые знакомства или восстанови старые связи.",
                  "Идеи приходят одна за другой. Запишь — пригодятся. Не распыляйся на всё сразу.",
                  "Любопытство приведёт тебя к интересному открытию. Следуй за ним без колебаний.",
                  "Сегодня легко убедить кого угодно в чём угодно — используй этот дар мудро.",
                  "Двойственность Близнецов — сила: видишь сразу две стороны любой ситуации 🌓",
                  "Слова сегодня особенно точны — пиши, говори, создавай. Твой момент! ✍️"],
    "Рак":       ["Семья и близкие — главный приоритет сегодня. Позаботься о тех, кто рядом.",
                  "Интуиция обострена — прислушайся к внутреннему голосу, особенно в вечерние часы.",
                  "Эмоции могут захлёстывать — дай себе время прийти в равновесие, прежде чем реагировать.",
                  "Уютный вечер дома восстановит силы лучше любого другого отдыха.",
                  "Твоя забота о других сегодня вернётся к тебе теплом и благодарностью 🌙",
                  "Прошлое отпускает тебя — ты готов(а) к новому витку. Доверяй своей чувствительности 💙"],
    "Лев":       ["Ты в центре внимания — и это заслуженно! День для самовыражения и творчества.",
                  "Щедрость сегодня вернётся к тебе сторицей. Не жалей тепла для окружающих.",
                  "Амбиции зовут вперёд — но убедись, что цель реальна, прежде чем рваться к ней.",
                  "Твоя харизма открывает двери. Воспользуйся этим для важного разговора или встречи.",
                  "Корона сегодня сидит прочно — веди с достоинством и другие последуют за тобой 👑",
                  "Твоя искренность и открытость сегодня покоряет сердца. Будь собой! 🦁"],
    "Дева":      ["День для порядка и системности. Разбери завалы — физические и ментальные.",
                  "Внимание к деталям спасёт от ошибки, которую другие не заметят.",
                  "Критика сегодня лучше воспринимается — прими её конструктивно и используй для роста.",
                  "Помощь другим принесёт больше радости, чем ожидаешь. Не отказывай в поддержке.",
                  "Твоя аналитичность сегодня — ключ к решению давней проблемы. Доверяй своему уму 🔍",
                  "Забота о теле сегодня принесёт плоды. Правильное питание и движение — твоя инвестиция 🌿"],
    "Весы":      ["Гармония в отношениях — главная тема дня. Ищи компромисс, а не победу.",
                  "Эстетика и красота вдохновляют — займись тем, что приносит визуальное удовольствие.",
                  "Трудно принять решение? Доверяй чувству справедливости — оно тебя не подведёт.",
                  "Партнёрство и сотрудничество принесут лучшие результаты, чем одиночная работа.",
                  "Твой природный такт сегодня поможет разрешить напряжённую ситуацию ⚖️",
                  "Красота в деталях — замедлись и заметь то, что обычно ускользает 🌸"],
    "Скорпион":  ["Интенсивный день — эмоции глубокие, но управляемые. Трансформация близко.",
                  "Тайна или скрытая информация выйдет на поверхность. Будь готов к открытиям.",
                  "Страсть и решимость — твои главные козыри сегодня. Направь их в созидательное русло.",
                  "Интуиция на пике. Если что-то чувствуется неправильным — так оно и есть.",
                  "Глубина твоей натуры сегодня — сила, а не слабость. Позволь себе чувствовать 🌑",
                  "Трансформация болезненна, но результат превзойдёт ожидания. Держись, Скорпион! 🦂"],
    "Стрелец":   ["Приключения и новые горизонты зовут! День для путешествий, пусть даже мысленных.",
                  "Оптимизм заразителен — поделись им с окружающими. Ты умеешь вдохновлять.",
                  "Честность — твоя сила. Скажи правду, даже если это непросто — потом будешь рад(а).",
                  "Учёба и философские размышления принесут неожиданные инсайты.",
                  "Стрела летит далеко — мечтай масштабно и вселенная поддержит твои амбиции 🏹",
                  "Смех и лёгкость сегодня — лучшее лекарство для тебя и тех, кто рядом 😄"],
    "Козерог":   ["Терпение и труд — всё перетрут. Сегодня пожинаешь плоды вчерашних усилий.",
                  "Карьера и репутация в фокусе. Серьёзный, ответственный подход оценят по достоинству.",
                  "Не бери на себя слишком много — делегируй и доверяй другим.",
                  "Долгосрочное планирование принесёт больше радости, чем сиюминутные решения.",
                  "Гора поддаётся тому, кто идёт методично. Ты почти на вершине — не останавливайся ⛰️",
                  "Отдых — часть стратегии успеха. Сегодня можно замедлиться без вины 🌿"],
    "Водолей":   ["Оригинальные идеи пробивают путь к успеху. Не бойся быть не таким, как все.",
                  "Дружба и командная работа — ключи к сегодняшним достижениям.",
                  "Гуманизм и забота о других наполнят день смыслом. Помоги тому, кто в этом нуждается.",
                  "Технологии и инновации — твоя стихия сегодня. Изучи что-то новое.",
                  "Твоя нестандартная мысль сегодня — это именно то, что ищут другие 💡",
                  "Революционные идеи рождаются в тишине. Позволь себе побыть наедине с разумом 🌌"],
    "Рыбы":      ["Мечты яркие и наполненные — запиши их, они несут послание.",
                  "Творчество и искусство помогут выразить то, что сложно облечь в слова.",
                  "Сострадание привлечёт к тебе людей, которым нужна поддержка. Ты справишься.",
                  "Граница между реальностью и фантазией размыта — это источник вдохновения, а не слабость.",
                  "Вода принимает форму любого сосуда — твоя гибкость сегодня открывает двери 🌊",
                  "Духовный опыт ждёт тебя сегодня — будь открыт(а) к тому, что выходит за рамки логики 🐟"],
}

ZODIAC_SIGNS: tuple[str, ...] = (
    "Овен", "Телец", "Близнецы", "Рак", "Лев", "Дева",
    "Весы", "Скорпион", "Стрелец", "Козерог", "Водолей", "Рыбы",
)
ZODIAC_ALIASES: dict[str, str] = {
    sign.casefold(): sign for sign in ZODIAC_SIGNS
}
SUPERPOWERS = [
    "🦸 Телепатия — ты читаешь мысли людей с первого взгляда",
    "⚡ Молния — твоя воля управляет электричеством и энергией",
    "🔥 Пирокинез — огонь повинуется твоему взгляду и жесту",
    "❄️ Криокинез — ты останавливаешь воду и замораживаешь пространство",
    "🌀 Телепортация — ты мгновенно перемещаешься в любую точку мира",
    "💨 Полёт — небо открыто для тебя в любое время дня и ночи",
    "🛡️ Неуязвимость — ни одно оружие не причинит тебе вреда",
    "🔮 Предвидение — ты видишь будущее на три шага вперёд",
    "👻 Невидимость — ты исчезаешь из поля зрения по желанию",
    "🧲 Управление металлом — любой металл подчиняется твоей воле",
    "⏱️ Остановка времени — ты замораживаешь мир вокруг себя",
    "🌊 Управление водой — океаны слушаются твоей руки",
    "🌿 Связь с природой — животные и растения понимают тебя",
    "💡 Суперинтеллект — твой разум решает любые задачи мгновенно",
    "🔊 Ультразвук — твой голос способен сдвигать горы",
    "🌑 Теневое поглощение — ты растворяешься в тени и путешествуешь сквозь темноту",
    "☀️ Фотокинез — ты управляешь светом, создавая иллюзии",
    "🧬 Регенерация — твоё тело восстанавливается за секунды",
    "🌍 Геокинез — земля и камни движутся по твоей воле",
    "🎭 Мимикрия — ты копируешь суперсилы тех, с кем рядом",
    "🧠 Телекинез — предметы двигаются силой твоей мысли",
    "🌪️ Аэрокинез — ты управляешь ветром и атмосферой",
    "💎 Нерушимость — ничто не может сломить или согнуть тебя",
    "🌺 Биокинез — ты исцеляешь болезни одним прикосновением",
    "🔗 Телепатическая связь — ты соединяешь разумы на расстоянии",
    "🎵 Звуковые волны — твоя музыка способна изменять реальность",
    "🌙 Лунная сила — ночью твои способности удваиваются",
    "🦋 Трансформация — ты меняешь свой облик по желанию",
    "⚗️ Алхимия — ты превращаешь любой материал во что угодно",
    "🌠 Управление гравитацией — ты меняешь силу притяжения вокруг себя",
]
PROFESSIONS = [
    "👨‍💻 Программист — создаёт миры из строк кода",
    "🎨 Художник — превращает мысли в визуальную реальность",
    "🎵 Музыкант — говорит с душой через звук",
    "🧑‍🍳 Шеф-повар — алхимик вкусов и ароматов",
    "✈️ Пилот — властелин небес и горизонтов",
    "🧑‍⚕️ Врач — хранитель жизни и здоровья",
    "🏗️ Архитектор — строит пространство, в котором живут мечты",
    "📸 Фотограф — ловит вечность в один момент",
    "🎭 Актёр — проживает тысячу жизней на одной сцене",
    "📝 Писатель — создаёт миры из слов",
    "🔬 Учёный — разгадывает секреты вселенной",
    "🌿 Фермер — кормит мир и заботится о земле",
    "🧑‍🏫 Учитель — меняет будущее через настоящее",
    "🕵️ Детектив — видит то, что скрыто от других",
    "🚀 Астронавт — первооткрыватель космических границ",
    "🎮 Геймдизайнер — строит игровые вселенные",
    "⚽ Спортсмен — доказывает, что предела нет",
    "🎪 Иллюзионист — превращает невозможное в обычное",
    "🧙 Волшебник — мастер тайного знания",
    "🦁 Дрессировщик — находит общий язык с дикой природой",
    "🌊 Серфер-инструктор — учит покорять волны",
    "🎻 Дирижёр — управляет оркестром с одним жестом",
    "🕌 Историк — хранит память тысячелетий",
    "🌐 Дипломат — строит мосты между народами",
    "🎬 Режиссёр — рассказывает истории, которые остаются навсегда",
    "🧑‍🚀 Исследователь — идёт туда, где никто ещё не бывал",
    "🏛️ Философ — задаёт вопросы, которые меняют мир",
    "🌺 Флорист — создаёт красоту из живой природы",
    "🦅 Орнитолог — знает каждую птицу по голосу",
    "⚙️ Инженер — превращает идеи в реальные конструкции",
    "🧑‍🎤 Певец — дарит эмоции голосом",
    "🎯 Стратег — просчитывает ходы на десять вперёд",
    "🛡️ Рыцарь-защитник — стоит на страже справедливости",
    "🌍 Путешественник — собирает истории со всего света",
    "📡 Астроном — читает язык звёзд",
    "🧘 Инструктор йоги — соединяет тело и разум",
    "🌋 Вулканолог — изучает огонь внутри планеты",
    "🦈 Морской биолог — знает секреты глубин",
    "🎲 Игровой математик — находит закономерности в хаосе",
    "🏺 Реставратор — возвращает прошлое к жизни",
]
ANIMALS = [
    "🦁 Лев — царь зверей, ты рождён(а) вести за собой",
    "🐬 Дельфин — интеллект и радость в каждом движении",
    "🦅 Орёл — видишь дальше всех и паришь над обстоятельствами",
    "🐼 Панда — редкий и особенный, ценишь покой и бамбук",
    "🐺 Волк — сила стаи в тебе, ты верен своим до конца",
    "🦋 Бабочка — рождён(а) для преображения и красоты",
    "🐢 Черепаха — мудрость и долголетие, спешить некуда",
    "🦊 Лиса — хитрость и ум твои главные инструменты",
    "🐧 Пингвин — верен(а) паре и умеешь выживать в любом климате",
    "🐙 Осьминог — мастер адаптации и скрытых талантов",
    "🐻 Медведь — сила, защита и тепло для близких",
    "🦒 Жираф — видишь картину целиком там, где другие упираются в стену",
    "🐘 Слон — память как камень, верность как скала",
    "🦓 Зебра — уникальный узор, нет двух одинаковых",
    "🐆 Гепард — самый быстрый в достижении целей",
    "🦜 Попугай — общительный, яркий, запоминающийся",
    "🐺 Арктический волк — выдерживаешь любые морозы одиночества",
    "🦩 Фламинго — грация и умение выделяться из толпы",
    "🦋 Монарх — путешествуешь далеко от дома, но всегда возвращаешься",
    "🐊 Крокодил — терпение и молниеносная реакция в нужный момент",
    "🦅 Кондор — поднимаешься выше всех на восходящих потоках",
    "🐋 Кит — огромная душа с тихим голосом, который слышат все",
    "🦁 Белый лев — редкость природы, особое предназначение",
    "🐯 Тигр — страсть, сила и независимость в каждом движении",
    "🐍 Питон — терпение, стратегия и умение ждать своего часа",
    "🦎 Хамелеон — адаптируешься к любой ситуации без усилий",
    "🐺 Волк-одиночка — сила без поводка, свобода без границ",
    "🦁 Пума — грация хищника и молчаливая уверенность",
    "🐦 Соловей — голос твой трогает сердца",
    "🦔 Ёж — мягкий внутри, защищённый снаружи",
]
RIDDLES = [("Что идёт, не двигаясь с места?","Время ⏰"),("Чем больше берёшь — тем больше становится. Что это?","Яма 🕳️"),("У меня есть города, но нет домов. Есть леса, но нет деревьев. Есть вода, но нет рыбы. Что я?","Карта 🗺️"),("Чем больше сохнет, тем мокрее становится?","Полотенце 🏊"),("Что можно увидеть с закрытыми глазами?","Сон 😴"),("Какой вопрос нельзя задать?","Ты спишь? (если человек спит — не ответит) 😄")]
ADVICES = ["🌱 Делай каждый день хотя бы одно маленькое дело, которое приближает тебя к мечте","💤 Здоровый сон важнее большинства дел — спи 7-8 часов","🚶 Ходи пешком хотя бы 30 минут в день","📵 Делай цифровые детоксы — хотя бы час без телефона","🙏 Благодари за малое — это меняет восприятие мира","📚 Читай хотя бы 10 страниц в день","💬 Говори людям что ценишь их — это важно","🎯 Ставь маленькие цели — они приводят к большим победам"]
MOTIVATIONS = ["🔥 Ты сильнее, чем думаешь. Продолжай!","⭐ Каждый великий путь начинается с первого шага","💪 Неудача — это не конец, это урок","🌅 Каждое утро — новый шанс стать лучше","🚀 Мечты становятся реальностью когда ты действуешь","💡 Твои идеи имеют значение — воплощай их","🌊 Препятствия делают тебя сильнее","🎯 Верь в себя — ты можешь больше, чем кажется"]
MYTHS = ["❌ Миф: Мы используем только 10% мозга. На самом деле: весь мозг активен всегда","❌ Миф: Стекло — медленно текущая жидкость. Оно твёрдое аморфное тело","❌ Миф: Кровь в жилах синяя. Она всегда красная, просто вены просвечивают синеватым","❌ Миф: Хамелеон меняет цвет для маскировки. На самом деле — для общения","❌ Миф: Сахар делает детей гиперактивными. Это не подтверждено наукой","❌ Миф: Волосы и ногти растут после смерти. Это иллюзия из-за высыхания кожи"]
MOVIES = ["🎬 Побег из Шоушенка (1994)","🎬 Список Шиндлера (1993)","🎬 Тёмный рыцарь (2008)","🎬 Криминальное чтиво (1994)","🎬 Властелин колец (2001-2003)","🎬 Матрица (1999)","🎬 Начало (2010)","🎬 Интерстеллар (2014)","🎬 1+1 (2011)","🎬 Зелёная миля (1999)"]
BOOKS = ["📚 Мастер и Маргарита — Булгаков","📚 Преступление и наказание — Достоевский","📚 1984 — Оруэлл","📚 Маленький принц — Сент-Экзюпери","📚 Гарри Поттер — Роулинг","📚 Война и мир — Толстой","📚 Дюна — Герберт","📚 Автостопом по галактике — Адамс","📚 Три товарища — Ремарк","📚 Атлант расправил плечи — Рэнд"]
JOKES = ["— Почему программисты путают Хэллоуин и Рождество?\n— Oct 31 = Dec 25 😄","— Сколько программистов нужно вкрутить лампочку?\n— Ни одного — аппаратная проблема! 😂","— Что делает программист с яйцом?\n— Exception! 🥚","— Жена программиста: «Купи хлеб, если яйца есть — возьми десяток».\n— Он принёс 10 батонов 😂","— Бармен роботу: «Роботов не обслуживаем».\n— Робот: «Спасибо, со временем стану не роботом» 🤖","— Почему Java-разработчик носит очки?\n— Не может видеть C# 😂","— Баг — это недокументированная фича!","— Как программист считает? 0, 1, 10, 11, 100... 🔢"]
COMPLIMENTS = ["Ты сегодня особенно прекрасно выглядишь! ✨","С тобой очень приятно общаться 💙","У тебя отличное чувство юмора! 😄","Ты умнее, чем думаешь 🧠","Рядом с тобой становится теплее 🌟","У тебя красивая улыбка 😊","Ты настоящий(ая) профессионал своего дела 🏆","Твой позитив заразителен! 🌈"]
ROASTS = ["Ты как Wi-Fi в деревне — иногда есть, но очень слабый 📶","Если бы тупость была спортом — ты был бы олимпийским чемпионом 🥇","Ты не бесполезный. Ты можешь быть плохим примером 😄","Твой код такой же чистый, как носки после трёх дней 🧦","Даже ChatGPT иногда не понимает что ты несёшь 🤖","Ты как пустой холодильник — открываешь и разочаровываешься 🤷"]
COUNTRIES = ["🇯🇵 Япония — в Токио более 37 млн жителей, это крупнейший мегаполис мира","🇧🇷 Бразилия — содержит 60% Амазонского дождевого леса","🇳🇴 Норвегия — 2/3 потребляемой энергии — гидроэлектричество","🇮🇸 Исландия — нет комаров и армии","🇳🇿 Новая Зеландия — на ней живёт больше овец, чем людей","🇧🇭 Бахрейн — единственная страна на острове в Персидском заливе","🇷🇺 Россия — занимает 11% суши планеты"]
COLORS = ["🔴 Красный — страсть, энергия, сила","🔵 Синий — доверие, спокойствие, интеллект","🟢 Зелёный — природа, рост, гармония","🟡 Жёлтый — радость, оптимизм, творчество","🟣 Фиолетовый — роскошь, мудрость, тайна","🟠 Оранжевый — энтузиазм, тепло, общение","⚫ Чёрный — элегантность, сила, загадочность","⚪ Белый — чистота, простота, новое начало"]
EMOJIS_COMBOS = ["🔥💯✨","🎉🎊🎈","😎🤙💪","🌈🦄✨","🌊🏄🌅","🎵🎶🎸","🍕🍔🌮","🚀🌌⭐","🦁👑🌟","💖💫🌸"]

async def cmd_fortune(msg: Message):
    result = random.choice(FORTUNES)
    name   = html.escape(msg.from_user.first_name or "—")
    if not await reply_t(msg, "fortune_result", result=result):
        await msg.reply(
            f"{brand.hdr()}\n\n"
            f"🔮 <b>Предсказание для {name}</b>\n\n"
            f"{brand.div()}\n"
            f"<i>{result}</i>\n\n"
            f"{brand.div()}\n"
            f"<i>Вселенная всегда знает ответ</i> ✨",
            parse_mode="HTML",
        )

async def cmd_8ball(msg: Message, command: CommandObject = None):
    if not (command and command.args):
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            f"🎱 <b>Магический шар</b>\n\n"
            f"Задай вопрос и узнай ответ вселенной:\n"
            f"<code>8ball твой вопрос</code>\n\n"
            f"Например: <i>8ball Всё будет хорошо?</i>\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )
    answer   = random.choice(EIGHT_BALL)
    question = html.escape(command.args.strip())
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🎱 <b>Магический шар отвечает...</b>\n\n"
        f"❓ <i>{question}</i>\n\n"
        f"{brand.div()}\n"
        f"◆ <b>{answer}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def cmd_tarot(msg: Message):
    card, meaning = random.choice(TAROT)
    name = html.escape(msg.from_user.first_name or "—")
    if not await reply_t(msg, "tarot_result", card=card, meaning=meaning):
        await msg.reply(
            f"{brand.hdr()}\n\n"
            f"🃏 <b>Карта Таро для {name}</b>\n\n"
            f"{brand.div()}\n"
            f"✨ <b>{card}</b>\n\n"
            f"<i>{meaning}</i>\n\n"
            f"{brand.div()}\n"
            f"<i>Карты не лгут — прислушайся к посланию</i> 🌙",
            parse_mode="HTML",
        )

async def cmd_horoscope(msg: Message, command: CommandObject = None):
    raw = (command.args if command else "").strip()
    # У текстовій команді аргументи приходять через FakeCmd2, а в slash-команді
    # через CommandObject. Нормалізуємо обидва варіанти однаково і прибираємо
    # пунктуацію, щоб працювали "гороскоп: водолей" та "гороскоп водолей!".
    normalized = re.sub(r"[^\w\s-]", " ", raw.casefold().replace("ё", "е"))
    normalized = re.sub(r"\s+", " ", normalized).strip()
    sign = ZODIAC_ALIASES.get(normalized)
    # Совместимость со старой версией обработчика: она заменяла кириллическую
    # «д» в аргументах на латинскую «d», поэтому Railway мог передать «воdолей».
    if not sign and normalized:
        sign = ZODIAC_ALIASES.get(normalized.replace("d", "д"))
    if not sign and normalized:
        matches = [
            value for key, value in ZODIAC_ALIASES.items()
            if key.startswith(normalized) or key.startswith(normalized.replace("d", "д"))
        ]
        if len(matches) == 1:
            sign = matches[0]
    if not sign:
        if normalized:
            return await msg.reply(
                "Не узнала знак зодиака. Напиши, например: <code>гороскоп водолей</code>.",
                parse_mode="HTML",
            )
        sign = random.choice(ZODIAC_SIGNS)
    text = random.choice(HOROSCOPES[sign])
    if not await reply_t(msg, "horoscope_result", sign=sign, text=text):
        await msg.reply(
            f"{brand.hdr()}\n\n"
            f"🌙 Гороскоп — <b>{sign}</b>\n\n"
            f"<i>{text}</i>\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )

async def cmd_predict(msg: Message, command: CommandObject = None):
    if not (command and command.args):
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            f"🔮 <b>Предсказатель Луменаr</b>\n\n"
            f"Задай любой вопрос и получи ответ от вселенной:\n"
            f"<code>предсказать твой вопрос</code>\n\n"
            f"Например: <i>предсказать Найду ли я работу мечты?</i>\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )
    result   = random.choice(PREDICTIONS)
    question = html.escape(command.args.strip())
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🔮 <b>Вижу будущее...</b>\n\n"
        f"❓ <i>{question}</i>\n\n"
        f"{brand.div()}\n"
        f"◆ {result}\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def cmd_destiny(msg: Message):
    name   = html.escape(msg.from_user.first_name or "—")
    result = random.choice(FORTUNES)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"✨ <b>Судьба для {name}</b>\n\n"
        f"{brand.div()}\n"
        f"<i>{result}</i>\n\n"
        f"{brand.div()}\n"
        f"<i>Звёзды говорят — слушай их</i> 🌌",
        parse_mode="HTML",
    )

async def cmd_superpower(msg: Message):
    name  = html.escape(msg.from_user.first_name or "—")
    power = random.choice(SUPERPOWERS)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🦸 <b>Суперсила {name}</b>\n\n"
        f"{brand.div()}\n"
        f"<b>{power}</b>\n\n"
        f"{brand.div()}\n"
        f"<i>Великая сила требует великой ответственности</i> 💫",
        parse_mode="HTML",
    )

async def cmd_profession(msg: Message):
    name = html.escape(msg.from_user.first_name or "—")
    prof = random.choice(PROFESSIONS)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"💼 <b>Профессия {name} по звёздам</b>\n\n"
        f"{brand.div()}\n"
        f"<b>{prof}</b>\n\n"
        f"{brand.div()}\n"
        f"<i>Карьера написана в звёздах — и она тебе подходит</i> 🌟",
        parse_mode="HTML",
    )

async def cmd_animal(msg: Message):
    animal = random.choice(ANIMALS)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🐾 Животное дня\n\n"
        f"<b>{animal}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def cmd_movie(msg: Message):
    movie = random.choice(MOVIES)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🎬 Рекомендация\n\n"
        f"<b>{movie}</b>\n\n"
        f"<i>Хороший фильм — лучший отдых 🍿</i>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def cmd_book(msg: Message):
    book = random.choice(BOOKS)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"📚 Книга дня\n\n"
        f"<b>{book}</b>\n\n"
        f"<i>Читающий человек живёт несколько жизней ✨</i>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def cmd_advice(msg: Message):
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"💡 Совет дня\n\n"
        f"<i>{random.choice(ADVICES)}</i>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def cmd_motivation(msg: Message):
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🚀 Мотивация\n\n"
        f"<b>{random.choice(MOTIVATIONS)}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def cmd_myth(msg: Message):
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🧐 Интересный факт vs Миф\n\n"
        f"{random.choice(MYTHS)}\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def cmd_country(msg: Message):
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🌍 Страна дня\n\n"
        f"{random.choice(COUNTRIES)}\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def cmd_color(msg: Message):
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🎨 Цвет настроения\n\n"
        f"{random.choice(COLORS)}\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def cmd_emoji_combo(msg: Message):
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"✨ Твой эмодзи-набор дня\n\n"
        f"<b>{random.choice(EMOJIS_COMBOS)}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def cmd_joke(msg: Message):
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"😄 Шутка дня\n\n"
        f"{random.choice(JOKES)}\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def cmd_compliment(msg: Message):
    target = msg.reply_to_message.from_user.first_name if msg.reply_to_message else msg.from_user.first_name
    compliment = random.choice(COMPLIMENTS)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"💖 Комплимент для {html.escape(target)}\n\n"
        f"<i>{compliment}</i>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def cmd_roast(msg: Message):
    target = msg.reply_to_message.from_user.first_name if msg.reply_to_message else msg.from_user.first_name
    roast = random.choice(ROASTS)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🔥 Роаст для {html.escape(target)}\n\n"
        f"<i>{roast}</i>\n\n"
        f"<i>Всё в шутку, не обижайся 😄</i>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

# ═══════════════════════════════════════════════════════
# ИГРЫ
# ═══════════════════════════════════════════════════════
async def cmd_coin(msg: Message):
    side = random.choice(["heads", "tails"])
    text = brand.get_text(f"coin_{side}") or ("🪙 Орёл!" if side == "heads" else "🪙 Решка!")
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🪙 Подбрасываю монету...\n\n"
        f"<b>{text}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def cmd_dice(msg: Message, command: CommandObject = None):
    n = 1
    try: n = min(max(int((command.args or "1").split()[0]), 1), 10)
    except: pass
    results = [random.randint(1, 6) for _ in range(n)]
    faces = ["⚀","⚁","⚂","⚃","⚄","⚅"]
    visual = " ".join(faces[r-1] for r in results)
    total_line = f"  Сумма: <b>{sum(results)}</b>" if n > 1 else ""
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🎲 {'Бросок' if n==1 else f'{n} кубика'}\n\n"
        f"{visual}\n"
        f"<b>{' | '.join(map(str, results))}</b>{total_line}\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def cmd_roll(msg: Message, command: CommandObject = None):
    sides = 20
    try:
        sides = int((command.args or "20").split()[0])
    except Exception:
        pass
    sides = max(2, min(sides, 1_000_000))
    result = random.randint(1, sides)
    is_max = result == sides
    is_min = result == 1
    suffix = " 🎊 МАКСИМУМ!" if is_max else (" 💀 МИНИМУМ!" if is_min else "")
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🎲 Бросок d{sides}\n\n"
        f"Результат: <b>{result}</b>{suffix}\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def cmd_rps(msg: Message, command: CommandObject = None):
    choices = {"камень": "✊", "ножницы": "✌️", "бумага": "✋"}
    # Получаем выбор: из command.args (если /rps) или из текста сообщения (если «кнб камень»)
    if command and command.args:
        user_choice = command.args.strip().lower().split()[0]
    else:
        # Текстовая форма: «кнб камень»
        parts = (msg.text or "").strip().lower().split()
        user_choice = parts[1] if len(parts) >= 2 else ""
    if user_choice not in choices:
        return await msg.reply(
            "✊✌️✋ Выбери: <b>камень</b> | <b>ножницы</b> | <b>бумага</b>\n"
            "Пример: <code>кнб камень</code>",
            parse_mode="HTML",
        )
    bot_choice = random.choice(list(choices.keys()))
    wins = {("камень","ножницы"), ("ножницы","бумага"), ("бумага","камень")}
    if user_choice == bot_choice:
        result = "Ничья! 🤝"
        award = 0
    elif (user_choice, bot_choice) in wins:
        result = "Ты победил! 🎉"
        award = 50
        add_balance(msg.from_user.id, award)
    else:
        result = "Я победил! 😈"
        award = -20
        add_balance(msg.from_user.id, max(award, -get_balance(msg.from_user.id)))
    reward_line = f"💰 {'+' if award > 0 else ''}{award} LMN" if award else ""
    await msg.reply(
        f"Ты: {choices[user_choice]} | Я: {choices[bot_choice]}\n"
        f"{result}" + (f"\n{reward_line}" if reward_line else ""),
        parse_mode="HTML",
    )

async def cmd_random_num(msg: Message, command: CommandObject = None):
    try:
        parts = list(map(int, ((command.args or "1 100") if command else "1 100").split()))
        a, b = (parts[0], parts[1]) if len(parts) == 2 else (1, parts[0])
    except:
        a, b = 1, 100
    result = random.randint(min(a, b), max(a, b))
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🎲 Случайное число\n\n"
        f"Диапазон: <b>{min(a,b)} – {max(a,b)}</b>\n"
        f"◆ Выпало: <b>{result}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def cmd_choose(msg: Message, command: CommandObject = None):
    if not (command and command.args):
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            f"🎯 Выборщик\n\n"
            f"Напиши варианты через пробел:\n"
            f"<code>выбрать пицца суши бургер</code>\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )
    opts = command.args.split()
    chosen = random.choice(opts)
    eliminated = [o for o in opts if o != chosen]
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🎯 Выбор сделан!\n\n"
        f"◆ <b>{html.escape(chosen)}</b>\n\n"
        f"<i>Остальные варианты не подошли: {', '.join(html.escape(e) for e in eliminated[:5])}</i>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def cmd_rate(msg: Message, command: CommandObject = None):
    thing = (command.args if command and command.args else None) or \
            (msg.reply_to_message.text if msg.reply_to_message else "это")
    if len(str(thing)) > 50:
        thing = str(thing)[:50] + "..."
    score = random.randint(0, 10)
    filled = "█" * score
    empty = "░" * (10 - score)
    if score == 10:   verdict = "🏆 Шедевр!"
    elif score >= 8:  verdict = "✨ Очень круто"
    elif score >= 6:  verdict = "👍 Неплохо"
    elif score >= 4:  verdict = "😐 Так себе"
    elif score >= 2:  verdict = "😬 Слабовато"
    else:             verdict = "💀 Ужас"
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"⭐ Оценка\n\n"
        f"«{html.escape(str(thing))}»\n\n"
        f"[{filled}{empty}] <b>{score}/10</b>\n"
        f"◆ {verdict}\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def cmd_truth(msg: Message):
    questions = [
        "Какой твой самый стыдный поступок?",
        "В кого ты сейчас втайне влюблён(а)?",
        "Что никогда никому не рассказывал(а)?",
        "Какую самую большую ложь говорил(а)?",
        "О чём больше всего жалеешь?",
        "Кто твой секретный кумир в чате?",
        "Что первое замечаешь в людях?",
        "Какой твой самый странный страх?",
        "Что думаешь о себе, когда никто не видит?",
        "Когда последний раз плакал(а) и почему?",
    ]
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🗣️ Правда или действие — Правда\n\n"
        f"<b>{random.choice(questions)}</b>\n\n"
        f"<i>Отвечать честно! Все смотрят 👀</i>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def cmd_dare(msg: Message):
    dares = [
        "Напиши бывшему/бывшей «привет» и покажи скрин 👀",
        "Сделай 20 отжиманий прямо сейчас и пришли видео",
        "Спой голосовым сообщением любую песню",
        "Расскажи самый глупый факт о себе в чате",
        "Сделай комплимент трём людям в чате прямо сейчас",
        "Смени статус на «я люблю Lumena» на 30 минут",
        "Напиши «мяу» в трёх разных чатах и пришли скрины",
        "Угадай кто ответит следующим в этом чате",
        "Напиши что-нибудь только заглавными буквами 5 минут",
        "Отправь голосовое сообщение с петушиным криком",
        "Поставь реакцию ❤️ на 5 последних сообщений в чате",
        "Представься в чате как будто ты робот",
    ]
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🔥 Правда или действие — Действие\n\n"
        f"<b>{random.choice(dares)}</b>\n\n"
        f"<i>Отказаться нельзя! Все следят 😈</i>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def cmd_riddle(msg: Message):
    q, a = random.choice(RIDDLES)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🧩 Загадка\n\n"
        f"<b>{q}</b>\n\n"
        f"<tg-spoiler>💡 Ответ: {a}</tg-spoiler>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def cmd_roulette(msg: Message):
    chat_id = msg.chat.id
    uid = msg.from_user.id
    name = msg.from_user.full_name
    roulette_players.setdefault(chat_id, {})
    if uid in roulette_players[chat_id]:
        return await msg.reply(brand.get_text("roulette_already"), parse_mode="HTML")
    roulette_players[chat_id][uid] = name
    await msg.reply(
        brand.get_text("roulette_join_msg",
                       name=html.escape(name),
                       count=len(roulette_players[chat_id])),
        parse_mode="HTML",
    )

async def cmd_roulette_start(msg: Message):
    chat_id = msg.chat.id
    players = roulette_players.get(chat_id, {})
    if len(players) < 2:
        return await msg.reply(brand.get_text("roulette_not_enough"), parse_mode="HTML")
    loser_id, loser_name = random.choice(list(players.items()))
    roulette_players[chat_id] = {}
    await msg.reply(
        brand.get_text("roulette_result", name=html.escape(loser_name)),
        parse_mode="HTML",
    )

async def cmd_hangman(msg: Message):
    words = ["python","телеграм","программист","компьютер","телефон","приключение","музыка","технология"]
    word = random.choice(words)
    chat_id = msg.chat.id
    hangman_games[chat_id] = {"word": word, "guessed": set(), "tries": 0}
    display = " ".join("_" if c not in set() else c for c in word)
    await msg.reply(f"🎮 Виселица началась!\n{display}\n\nОтправь букву для угадывания (виселица_[буква])")

async def cmd_hangman_guess(msg: Message, letter: str):
    chat_id = msg.chat.id
    game = hangman_games.get(chat_id)
    if not game:
        return await msg.reply(brand.get_text("hangman_no_game"), parse_mode="HTML")
    letter = letter.lower()
    if letter in game["guessed"]:
        return await msg.reply(
            brand.get_text("hangman_letter_used", letter=letter), parse_mode="HTML")
    game["guessed"].add(letter)
    word = game["word"]
    if letter not in word:
        game["tries"] += 1
        if game["tries"] >= 6:
            del hangman_games[chat_id]
            return await msg.reply(
                brand.get_text("hangman_lose", word=word), parse_mode="HTML")
        remaining = 6 - game["tries"]
        mask = " ".join(c if c in game["guessed"] else "_" for c in word)
        return await msg.reply(
            brand.get_text("hangman_wrong", letter=letter, tries=remaining, mask=mask),
            parse_mode="HTML")
    mask = " ".join(c if c in game["guessed"] else "_" for c in word)
    if "_" not in mask:
        del hangman_games[chat_id]
        return await msg.reply(
            brand.get_text("hangman_win", word=word), parse_mode="HTML")
    await msg.reply(
        brand.get_text("hangman_right", letter=letter, mask=mask), parse_mode="HTML")

# ═══════════════════════════════════════════════════════
# ОТНОШЕНИЯ
# ═══════════════════════════════════════════════════════
async def cmd_ship(msg: Message):
    if not msg.reply_to_message: return await msg.reply("💘 Ответь на сообщение человека")
    pct = random.randint(0, 100)
    filled = pct // 10
    bar = "💗" * filled + "🖤" * (10 - filled)
    a, b = msg.from_user.first_name, msg.reply_to_message.from_user.first_name
    if pct >= 80:   verdict = "Идеальная пара! 💞"
    elif pct >= 60: verdict = "Есть химия! 🔥"
    elif pct >= 40: verdict = "Неплохие шансы 😊"
    elif pct >= 20: verdict = "Пока просто друзья 🤝"
    else:           verdict = "Совсем не судьба 💀"
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"💘 Совместимость\n\n"
        f"{brand.div()}\n"
        f"💫 <b>{a}</b>  +  <b>{b}</b>\n\n"
        f"{bar}  <b>{pct}%</b>\n\n"
        f"✨ {verdict}\n"
        f"{brand.div()}",
        parse_mode="HTML"
    )

async def cmd_love(msg: Message):
    if not msg.reply_to_message: return await msg.reply("❤️ Ответь на сообщение")
    pct = random.randint(0, 100)
    filled = pct // 10
    hearts = "❤️" * filled + "🖤" * (10 - filled)
    a, b = msg.from_user.first_name, msg.reply_to_message.from_user.first_name
    if pct >= 90:   verdict = "Взаимная любовь 💞"
    elif pct >= 70: verdict = "Сердце точно бьётся 💓"
    elif pct >= 50: verdict = "Симпатия есть 🌸"
    elif pct >= 30: verdict = "Пока только дружба 🤍"
    else:           verdict = "Не судьба 🥀"
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"❤️ Любовь\n\n"
        f"{brand.div()}\n"
        f"💫 <b>{a}</b>  →  <b>{b}</b>\n\n"
        f"{hearts}  <b>{pct}%</b>\n\n"
        f"✨ {verdict}\n"
        f"{brand.div()}",
        parse_mode="HTML"
    )

async def cmd_friend(msg: Message):
    if not msg.reply_to_message: return await msg.reply("🤝 Ответь на сообщение")
    pct = random.randint(0, 100)
    filled = pct // 10
    bar = "💙" * filled + "🖤" * (10 - filled)
    a, b = msg.from_user.first_name, msg.reply_to_message.from_user.first_name
    if pct >= 80:   verdict = "Лучшие друзья! 🏆"
    elif pct >= 60: verdict = "Хорошие друзья 😊"
    elif pct >= 40: verdict = "Приятели 🤝"
    elif pct >= 20: verdict = "Просто знакомые 😐"
    else:           verdict = "Незнакомцы 👽"
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🤝 Дружба\n\n"
        f"{brand.div()}\n"
        f"💫 <b>{a}</b>  &  <b>{b}</b>\n\n"
        f"{bar}  <b>{pct}%</b>\n\n"
        f"✨ {verdict}\n"
        f"{brand.div()}",
        parse_mode="HTML"
    )

async def cmd_couple(msg: Message):
    try:
        admins = await bot.get_chat_administrators(msg.chat.id)
        members = [a.user for a in admins if not a.user.is_bot]
        if len(members) < 2: return await msg.reply("Недостаточно людей")
        u1, u2 = random.sample(members, 2)
        await msg.reply(
            f"{brand.hdr()}\n\n"
            f"💕 Пара дня\n\n"
            f"{brand.div()}\n"
            f"💫 <b>{u1.full_name}</b>\n"
            f"❤️\n"
            f"<b>{u2.full_name}</b>\n"
            f"{brand.div()}",
            parse_mode="HTML"
        )
    except: await msg.reply("Не удалось получить участников")

async def cmd_serenade(msg: Message):
    if not msg.reply_to_message: return await msg.reply("Ответь на сообщение")
    target = msg.reply_to_message.from_user.first_name
    serenades = [f"🎵 {msg.from_user.first_name} поёт для {target}:\n«Ты как звезда в ночи — светла и недосягаема...»",f"🎶 {msg.from_user.first_name} поёт серенаду для {target}:\n«В этом мире нет красивее тебя, и глаза твои — как небо в январе...»"]
    await msg.reply(random.choice(serenades))


async def cmd_compatibility(msg: Message):
    """Совместимость двух людей на основе реальных данных чата.
    1. Ответом на сообщение → проверяет тебя и автора
    2. совместимость @user1 @user2 → проверяет двух упомянутых
    """
    import hashlib

    uid_a: int | None = None
    uid_b: int | None = None
    name_a = name_b = None

    # ── Способ 1: ответ на сообщение ──────────────────────
    if msg.reply_to_message and msg.reply_to_message.from_user:
        uid_a  = msg.from_user.id
        uid_b  = msg.reply_to_message.from_user.id
        name_a = html.escape(msg.from_user.first_name or "Аноним")
        name_b = html.escape(msg.reply_to_message.from_user.first_name or "Аноним")

    # ── Способ 2: упоминания ──────────────────────────────
    else:
        entities = msg.entities or []
        mentioned: list[tuple[int, str]] = []
        for ent in entities:
            if ent.type == "mention":
                uname = (msg.text or "")[ent.offset + 1: ent.offset + ent.length]
                # Ищем uid в user_registry (username → uid) если доступен
                found_uid = user_registry.get(uname.lower()) if "user_registry" in dir() else None
                key = found_uid if found_uid else (abs(hash(uname.lower())) % (10 ** 15))
                mentioned.append((key, html.escape(f"@{uname}")))
            elif ent.type == "text_mention" and ent.user:
                u = ent.user
                mentioned.append((u.id, html.escape(u.first_name or f"ID {u.id}")))

        if len(mentioned) >= 2:
            (uid_a, name_a), (uid_b, name_b) = mentioned[0], mentioned[1]
        elif len(mentioned) == 1:
            uid_a  = msg.from_user.id
            name_a = html.escape(msg.from_user.first_name or "Аноним")
            uid_b, name_b = mentioned[0]
        else:
            return await msg.reply(
                f"💞 <b>Совместимость</b>\n\n"
                f"Как использовать:\n"
                f"• Ответь на сообщение человека\n"
                f"• <code>совместимость @user1 @user2</code>",
                parse_mode="HTML"
            )

    if uid_a == uid_b:
        return await msg.reply("🪞 Ты проверяешь совместимость сам с собой... 100% нарцисс 😄")

    # ── Стабильный seed на базе пары ──────────────────────
    pair_key = "_".join(str(u) for u in sorted([uid_a, uid_b]))
    seed = int(hashlib.md5(pair_key.encode()).hexdigest(), 16)
    rng  = random.Random(seed)

    # ── Вспомогательная функция: схожесть двух числовых значений ──
    def _sim(val_a: float, val_b: float, lo: int = 40, hi: int = 100) -> int:
        """Чем ближе значения — тем выше схожесть (lo..hi%)."""
        mx = max(val_a, val_b, 1)
        ratio = 1.0 - abs(val_a - val_b) / mx          # 0.0 (разные) .. 1.0 (одинаковые)
        base  = round(lo + ratio * (hi - lo))
        # Небольшой хеш-шум ±5 для уникальности
        noise = rng.randint(-5, 5)
        return max(lo, min(hi, base + noise))

    def _bonus(val_a: float, val_b: float, threshold: float = 1) -> int:
        """Бонус если оба выше порога: 0 или +5..+15."""
        if val_a >= threshold and val_b >= threshold:
            return rng.randint(5, 15)
        return 0

    # ── Собираем реальные данные ──────────────────────────
    cid = msg.chat.id; can = econ_cid(cid)

    def _msgs(uid: int) -> int:
        return sum(user_messages.get(c, {}).get(uid, 0) for c in (cid, can))

    msgs_a    = _msgs(uid_a);          msgs_b    = _msgs(uid_b)
    xp_a      = user_xp.get(uid_a, 0); xp_b      = user_xp.get(uid_b, 0)
    streak_a  = (streak_data.get(uid_a) or {}).get("streak", 0)
    streak_b  = (streak_data.get(uid_b) or {}).get("streak", 0)
    lmn_a     = lmn_balances.get(uid_a, 0) + bank_balances.get(uid_a, 0)
    lmn_b     = lmn_balances.get(uid_b, 0) + bank_balances.get(uid_b, 0)
    ach_a     = set(user_achievements.get(uid_a, []))
    ach_b     = set(user_achievements.get(uid_b, []))
    shared_ach = len(ach_a & ach_b)

    # ── Считаем 5 категорий по реальным данным ────────────
    # 💬 Активность: схожесть количества сообщений в чате
    act_score = _sim(msgs_a, msgs_b, lo=35, hi=95)

    # ✨ Уровень: схожесть XP
    xp_score = _sim(xp_a, xp_b, lo=30, hi=95)
    xp_score += _bonus(xp_a, xp_b, threshold=100)       # бонус если оба прокачаны

    # 🔥 Стрик: оба держат стрики → высокая химия
    streak_score = _sim(streak_a, streak_b, lo=30, hi=90)
    streak_score += _bonus(streak_a, streak_b, threshold=3)

    # 💰 Экономика: схожесть богатства
    eco_score = _sim(lmn_a, lmn_b, lo=30, hi=95)

    # 🏆 Достижения: общие достижения → понимание
    if ach_a or ach_b:
        union = len(ach_a | ach_b) or 1
        ach_ratio = shared_ach / union
        ach_score = round(35 + ach_ratio * 60) + rng.randint(-5, 5)
    else:
        ach_score = rng.randint(35, 70)   # нет данных — случайно
    ach_score = max(30, min(100, ach_score))

    # Ограничиваем все значения диапазоном 10..100
    cat_scores = [
        min(100, max(10, act_score)),
        min(100, max(10, xp_score)),
        min(100, max(10, streak_score)),
        min(100, max(10, eco_score)),
        min(100, max(10, ach_score)),
    ]
    cats = [
        ("💬", "Активность"),
        ("✨", "Уровень"),
        ("🔥", "Стрик"),
        ("💰", "Экономика"),
        ("🏆", "Достижения"),
    ]

    total  = round(sum(cat_scores) / len(cat_scores))
    filled = total // 10
    bar    = "💗" * filled + "🖤" * (10 - filled)

    cat_lines = []
    for (icon, label), sc in zip(cats, cat_scores):
        mini = "▓" * (sc // 20) + "░" * (5 - sc // 20)
        cat_lines.append(f"{icon} {label}: {mini} <b>{sc}%</b>")

    if   total >= 90: verdict = "Идеальная пара — судьба! 💞"
    elif total >= 75: verdict = "Очень высокая совместимость 🔥"
    elif total >= 60: verdict = "Хорошая совместимость 💫"
    elif total >= 45: verdict = "Есть потенциал, нужно время 🌱"
    elif total >= 30: verdict = "Противоположности... может притянутся? 🤔"
    else:             verdict = "Очень сложное сочетание 💀"

    # Подсказки на основе данных
    hints = []
    if msgs_a == 0 or msgs_b == 0:
        hints.append("📊 <i>Один из вас ещё не писал в этом чате</i>")
    if streak_a >= 7 and streak_b >= 7:
        hints.append("🔥 <i>Оба держат стрики — это сближает!</i>")
    if shared_ach >= 3:
        hints.append(f"🏆 <i>Общих достижений: {shared_ach}</i>")

    hint_block = ("\n" + "\n".join(hints)) if hints else ""

    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"💞 <b>Совместимость</b>\n\n"
        f"{brand.div()}\n"
        f"👤 <b>{name_a}</b>\n"
        f"💕\n"
        f"👤 <b>{name_b}</b>\n\n"
        f"{bar}  <b>{total}%</b>\n\n"
        f"{chr(10).join(cat_lines)}"
        f"{hint_block}\n\n"
        f"✨ {verdict}\n"
        f"{brand.div()}",
        parse_mode="HTML"
    )

# ═══════════════════════════════════════════════════════
# ИНФОРМАЦИЯ
# ═══════════════════════════════════════════════════════
async def cmd_myid(msg: Message):
    target = msg.reply_to_message.from_user if msg.reply_to_message else msg.from_user
    await msg.reply(f"🆔 ID пользователя <b>{target.full_name}</b>: <code>{target.id}</code>", parse_mode="HTML")

async def cmd_whois(msg: Message):
    """Команда 'кто я' — полная информация о пользователе + интернет-поиск."""
    _reply_user = msg.reply_to_message.from_user if msg.reply_to_message else None
    # Не показываем досье бота — берём инфу о вызвавшем команду
    target = (_reply_user if _reply_user and not _reply_user.is_bot else msg.from_user)
    uid = target.id
    chat_id = msg.chat.id

    # ── Telegram-данные ──────────────────────────────────
    first = target.first_name or ""
    last = target.last_name or ""
    full_name = target.full_name
    username = f"@{target.username}" if target.username else "—"
    is_bot_flag = "🤖 Да" if target.is_bot else "👤 Нет"
    is_premium = "⭐ Да" if getattr(target, "is_premium", False) else "—"
    lang = target.language_code or "—"

    # ── Статус в чате ────────────────────────────────────
    chat_status = "—"
    if msg.chat.type != "private":
        try:
            member = await bot.get_chat_member(chat_id, uid)
            s = member.status
            if s == ChatMemberStatus.CREATOR:
                custom = getattr(member, "custom_title", None)
                chat_status = f"👑 Создатель чата" + (f" ({custom})" if custom else "")
            elif s == ChatMemberStatus.ADMINISTRATOR:
                custom = getattr(member, "custom_title", None)
                if custom:
                    chat_status = f"🛡 {custom}"
                else:
                    chat_status = "🛡 Администратор"
            elif s == ChatMemberStatus.MEMBER:
                chat_status = "👥 Участник"
            elif s == ChatMemberStatus.RESTRICTED:
                chat_status = "🔇 Ограничен"
            elif s == ChatMemberStatus.LEFT:
                chat_status = "🚪 Покинул чат"
            elif s == ChatMemberStatus.KICKED:
                chat_status = "🚫 Забанен"
            else:
                chat_status = str(s)
        except Exception:
            pass

    # ── Статистика чата ──────────────────────────────────
    streak_data = streaks.get(chat_id, {}).get(uid, {"count": 0})
    bal = get_balance(uid)
    rep_val = get_rep(chat_id, uid)
    warns = warnings_db.get(chat_id, {}).get(uid, 0)
    ru_warns = ru_army_warns.get(chat_id, {}).get(uid, 0)

    married = is_married(chat_id, uid)
    partner_name = "—"
    if married:
        partner_id = get_partner(chat_id, uid)
        try:
            pm = await bot.get_chat_member(chat_id, partner_id)
            partner_name = "❤️ " + pm.user.full_name
        except Exception:
            partner_name = "❤️ неизвестно"

    profile_data = profiles.get(uid, {})
    bio = html.escape(profile_data.get("bio", "—"))
    title_str = html.escape(profile_data.get("title", ""))

    # ── Фаундер ──────────────────────────────────────────
    is_founder = (target.username or "").lower() == OWNER_USERNAME.lower()

    # ── Собираем ответ ───────────────────────────────────
    lines = [
        f"{brand.hdr()}\n",
        f"🔎 Досье · {full_name}",
        f"{brand.div()}",
        f"👤 Имя: {first} {last}".strip(),
        f"🔗 Username: {username}",
        f"🆔 ID: <code>{uid}</code>",
        f"🌐 Язык: {lang}",
        f"⭐ Premium: {is_premium}",
    ]

    if title_str:
        lines.append(f"🏷 Звание: {title_str}")
    if bio != "—":
        lines.append(f"📝 Bio: {bio}")

    if msg.chat.type != "private":
        aura_val  = get_aura(uid)
        aura_line = f"{aura_bar(aura_val)} {aura_val:.2f}%"
        lines += [
            f"\n{brand.div()}",
            f"📊 Статус: {chat_status}",
            f"⚠️ Варны: {warns}/3",
            f"🚫 Пропаганда РА: {ru_warns}/2",
            f"🔥 Стрик: <b>{streak_data['count']}</b> дней",
            f"💰 Баланс: <b>{fmt_lmn(bal)} LMN</b>",
            f"⭐ Репутация: <b>{rep_val:+d}</b>",
            f"💍 Партнёр: {partner_name}",
            f"✨ Аура: <b>{aura_line}</b>",
        ]

    if is_founder:
        lines += [f"\n{brand.div()}", "✨ <b>Создатель проекта Lumena</b>"]

    lines.append(f"\n{brand.div()}")
    text = "\n".join(lines)
    await msg.reply(text, parse_mode="HTML")

async def cmd_chatinfo(msg: Message):
    chat = msg.chat
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"ℹ️ Информация о чате\n\n"
        f"🏷 Название: <b>{chat.title or 'Личный чат'}</b>\n"
        f"🆔 ID: <code>{chat.id}</code>\n"
        f"📋 Тип: <b>{chat.type}</b>\n"
        f"🔗 Username: @{chat.username or '—'}\n\n"
        f"{brand.div()}",
        parse_mode="HTML")

async def cmd_profile(msg: Message):
    target = msg.reply_to_message.from_user if msg.reply_to_message else msg.from_user
    uid = target.id
    chat_id = msg.chat.id
    streak_data = streaks.get(econ_cid(chat_id), {}).get(uid, {"count": 0})
    bal = get_balance(uid)
    rep_val = get_rep(chat_id, uid)
    married = is_married(chat_id, uid)
    partner_id = get_partner(chat_id, uid)
    partner_name = ""
    if married and partner_id:
        try:
            pm = await bot.get_chat_member(chat_id, partner_id)
            partner_name = pm.user.full_name
        except: partner_name = "неизвестно"
    profile_data = profiles.get(uid, {})
    bio = html.escape(profile_data.get("bio", brand.get_text("profile_no_bio") or "не указано"))
    title_str = html.escape(profile_data.get("title", ""))
    _cur = brand.currency()
    lines = [
        f"{brand.hdr()}\n",
        brand.get_text("profile_header", name=html.escape(target.full_name)),
    ]
    if title_str:
        lines.append(f"🏷 {title_str}")
    lines += [
        f"{brand.div()}",
        f"{brand.get_text('profile_bio_label')} {bio}",
        f"{brand.get_text('profile_balance_label')} <b>{fmt_lmn(bal)} {_cur}</b>",
        f"{brand.get_text('profile_streak_label')} <b>{streak_data['count']} дней</b>",
        f"{brand.get_text('profile_rep_label')} <b>{rep_val:+d}</b>",
        f"{brand.get_text('profile_marry_label')} {('❤️ ' + html.escape(partner_name) + _marriage_days_str(uid, partner_id)) if married else (brand.get_text('profile_no_partner') or '—')}",
        f"{brand.get_text('profile_id_label')} <code>{uid}</code>",
        f"\n{brand.div()}",
    ]
    await msg.reply("\n".join(lines), parse_mode="HTML")

async def cmd_setbio(msg: Message, command: CommandObject = None):
    if not (command and command.args): return await msg.reply("Использование: сетбио [текст]")
    profiles.setdefault(msg.from_user.id, {})["bio"] = command.args[:100]
    schedule_state_save("обновление bio")
    await msg.reply("✅ Bio обновлено!")

async def cmd_settitle(msg: Message, command: CommandObject = None):
    if not (command and command.args): return await msg.reply("Использование: сетзвание [звание]")
    profiles.setdefault(msg.from_user.id, {})["title"] = command.args[:30]
    schedule_state_save("обновление звания")
    await msg.reply("✅ Звание установлено!")

async def cmd_botstats(msg: Message):
    import html as _html

    def _unique_marriages(*marr_dicts) -> int:
        """Уникальные пары без дублей A↔B / B↔A."""
        pairs: set = set()
        for d in marr_dicts:
            for uid, pid in d.items():
                pairs.add(frozenset([uid, pid]))
        return len(pairs)

    def _best_streaks_per_user(*streak_dicts) -> dict:
        """По каждому uid берём максимальный streak из нескольких чатов."""
        result: dict = {}
        for d in streak_dicts:
            for uid, sd in d.items():
                if uid not in result or sd.get("count", 0) > result[uid].get("count", 0):
                    result[uid] = sd
        return result

    cid      = msg.chat.id
    is_group = msg.chat.type in ("group", "supergroup")

    if is_group:
        # Кількість учасників через Telegram API
        try:
            tg_member_count = await bot.get_chat_member_count(cid)
        except Exception:
            tg_member_count = None

        # Canonical: мод-чат і паблік шерять базу
        canonical = _ECON_CANONICAL.get(cid, cid)

        # Уникальные участники из обоих чатов (без дублей)
        members_cid = chat_members.get(cid, {})
        members_can = chat_members.get(canonical, {}) if canonical != cid else {}
        all_uid_set = set(members_cid) | set(members_can)

        member_display = tg_member_count if tg_member_count is not None else len(all_uid_set)

        # Браки — уникальные пары из обоих чатов, без задвоения
        total_marriages = _unique_marriages(
            marriages.get(cid, {}),
            marriages.get(canonical, {}) if canonical != cid else {},
        )

        # Стрики — по uid берём максимальный (не задваиваем одного человека)
        merged_str  = _best_streaks_per_user(
            streaks.get(canonical, {}) if canonical != cid else {},
            streaks.get(cid, {}),
        )
        total_streaks = sum(1 for d in merged_str.values() if d.get("count", 0) > 0)
        best_streak   = max((d.get("count", 0) for d in merged_str.values()), default=0)

        # Предупреждения — по uid берём максимум из обоих чатов
        warns_merged: dict = {}
        for w in (warnings_db.get(cid, {}),
                  warnings_db.get(canonical, {}) if canonical != cid else {}):
            for uid, cnt in w.items():
                warns_merged[uid] = max(warns_merged.get(uid, 0), cnt)
        total_warns = sum(warns_merged.values())

        # LMN: гаманець + банк для всех участников
        total_balance = sum(
            lmn_balances.get(uid, 0) + bank_balances.get(uid, 0)
            for uid in all_uid_set
        )

        # Топ по сумме (гаманець + банк)
        rich_in_chat = sorted(
            [(lmn_balances.get(uid, 0) + bank_balances.get(uid, 0), uid)
             for uid in all_uid_set],
            reverse=True,
        )
        richest_line = ""
        if rich_in_chat and rich_in_chat[0][0] > 0:
            top_bal, top_uid = rich_in_chat[0]
            top_name = members_cid.get(top_uid) or members_can.get(top_uid) or f"id{top_uid}"
            richest_line = (
                f"\n👑 Топ баланс: <b>{_html.escape(str(top_name))}</b>"
                f" · {fmt_lmn(top_bal)} LMN"
            )

        chat_title = _html.escape(msg.chat.title or "чат")

        await msg.reply(
            f"{brand.hdr()}\n\n"
            f"📊 Статистика · {chat_title}\n\n"
            f"👥 Учасників: <b>{member_display}</b>\n"
            f"💍 Шлюбів: <b>{total_marriages}</b>\n"
            f"🔥 Активних стріків: <b>{total_streaks}</b>\n"
            f"🏆 Рекорд стріку: <b>{best_streak} дн.</b>\n"
            f"⚠️ Попереджень: <b>{total_warns}</b>\n"
            f"💰 LMN в обороті: <b>{fmt_lmn(total_balance)}</b>"
            f" <i>(гаманець + банк)</i>"
            f"{richest_line}\n\n"
            f"{brand.div()}\n"
            f"🤖 v{BOT_VERSION}",
            parse_mode="HTML",
        )

    else:
        # Приватний чат → глобальна статистика

        # Уникальные юзеры по всем чатам
        total_users = len({uid for m in chat_members.values() for uid in m})

        # Браки — уникальные пары без дублей по всем чатам
        total_marriages = _unique_marriages(*marriages.values()) if marriages else 0

        # Стрики — максимальный per-user по всем чатам
        all_streaks   = _best_streaks_per_user(*streaks.values()) if streaks else {}
        total_streaks = sum(1 for d in all_streaks.values() if d.get("count", 0) > 0)
        best_streak   = max((d.get("count", 0) for d in all_streaks.values()), default=0)

        # Предупреждения — максимум по uid
        warns_all: dict = {}
        for w in warnings_db.values():
            for uid, cnt in w.items():
                warns_all[uid] = max(warns_all.get(uid, 0), cnt)
        total_warns = sum(warns_all.values())

        # LMN: гаманець + банк всех известных пользователей
        all_known     = set(lmn_balances) | set(bank_balances)
        total_balance = sum(
            lmn_balances.get(uid, 0) + bank_balances.get(uid, 0)
            for uid in all_known
        )

        await msg.reply(
            f"{brand.hdr()}\n\n"
            f"📊 Загальна статистика\n\n"
            f"👥 Унікальних юзерів: <b>{total_users}</b>\n"
            f"💍 Шлюбів: <b>{total_marriages}</b>\n"
            f"🔥 Активних стріків: <b>{total_streaks}</b>\n"
            f"🏆 Рекорд стріку: <b>{best_streak} дн.</b>\n"
            f"⚠️ Попереджень: <b>{total_warns}</b>\n"
            f"💰 LMN в обороті: <b>{fmt_lmn(total_balance)}</b>"
            f" <i>(гаманець + банк)</i>\n\n"
            f"{brand.div()}\n"
            f"🤖 v{BOT_VERSION}",
            parse_mode="HTML",
        )

async def cmd_ping(msg: Message):
    start = now_kyiv()
    sent = await msg.reply("⏳")
    delta = (now_kyiv() - start).microseconds // 1000
    quality = "🟢 Отличный" if delta < 100 else "🟡 Нормальный" if delta < 300 else "🔴 Высокий"
    await sent.edit_text(
        f"{brand.hdr()}\n\n"
        f"🏓 Понг!\n\n"
        f"⚡ Задержка: <b>{delta} мс</b>\n"
        f"📶 Качество: <b>{quality}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def cmd_version(msg: Message):
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🤖 Лумена Бот\n\n"
        f"📦 Версия: <b>v{BOT_VERSION}</b>\n"
        f"⚡ Функций: <b>100+</b>\n"
        f"🧠 ИИ: <b>Lumena Engine v4</b>\n"
        f"💬 Движок: <b>собственный, без внешних API</b>\n\n"
        f"{brand.div()}\n"
        f"💙 Сделано с душой",
        parse_mode="HTML",
    )

# ═══════════════════════════════════════════════════════
# ІНФО — опис проекту, команда, розробники
# ═══════════════════════════════════════════════════════
@dp.message(Command("info"))
async def cmd_info(msg: Message):
    """Показує опис проекту. Текст редагується через /edit → категорія ℹ️ Інфо.
    Також спрацьовує на текст 'інфо' / 'инфо' через TEXT_COMMANDS.
    """
    text = brand.get_text("info_project")
    await msg.reply(
        f"{brand.hdr()}\n\n{text}\n\n{brand.div()}",
        parse_mode="HTML",
    )


@dp.message(Command("editinfo"), F.chat.type == "private",
            F.func(lambda m: is_owner(m)))
async def cmd_edit_info(msg: Message):
    """Швидке редагування тексту команди /info для фаундера."""
    _edit_sessions[msg.from_user.id] = "info_project"
    current_text = html.escape(brand.get_current_text("info_project"))
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Відміна", callback_data="reply_edit_cancel"),
    ]])
    await msg.answer(
        "✏️ <b>Редагування тексту /info</b>\n\n"
        f"Поточний текст:\n<blockquote>{current_text}</blockquote>\n\n"
        "Надішли новий текст одним повідомленням. Форматування та Premium Emoji "
        "будуть збережені.",
        parse_mode="HTML",
        reply_markup=cancel_kb,
    )

# ═══════════════════════════════════════════════════════
# УТИЛИТЫ
# ═══════════════════════════════════════════════════════
async def cmd_password(msg: Message, command: CommandObject = None):
    try: length = min(max(int((command.args or "12").split()[0]), 6), 32)
    except: length = 12
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    pwd = "".join(random.choice(chars) for _ in range(length))
    await msg.reply(f"🔐 Пароль:\n`{pwd}`", parse_mode="Markdown")

async def cmd_uuid_gen(msg: Message):
    await msg.reply(f"🆔 `{uuid.uuid4()}`", parse_mode="Markdown")

async def cmd_fact(msg: Message):
    facts = [
        "🧠 Осьминоги имеют три сердца и голубую кровь",
        "🧠 Мёд не портится — нашли 3000-летний египетский мёд и он был съедобен",
        "🧠 Банан — ягода. А клубника — нет",
        "🧠 Молния бьёт в Землю около 100 раз в секунду",
        "🧠 У улитки около 14 000 зубов",
        "🧠 Человеческий мозг на 73% состоит из воды",
        "🧠 Первый компьютерный баг был настоящим мотыльком (1947, Гарвард)",
        "🧠 Кофе — вторая по популярности жидкость в мире после воды",
        "🧠 Солнце составляет 99,86% всей массы Солнечной системы",
        "🧠 Египетские пирамиды строили не рабы — есть документы с их зарплатами",
        "🧠 Буква 'е' — самая используемая в большинстве европейских языков",
        "🧠 Акулы существуют дольше деревьев — им около 450 млн лет",
        "🧠 Человек — единственное животное, которое краснеет от стыда",
        "🧠 На Луне нет ветра, поэтому следы Аполлона-11 до сих пор там",
        "🧠 Муравьи никогда не спят — у них есть только короткие фазы отдыха",
        "🧠 Фламинго розовые из-за пигментов в водорослях, которые они едят",
        "🧠 Кошки не чувствуют сладкое — у них нет рецепторов сладкого вкуса",
        "🧠 Сердце кита бьётся всего 2 раза в минуту под водой",
        "🧠 Первый iPhone вышел в 2007 году — ему сейчас почти 20 лет",
        "🧠 Нейронов в мозге больше, чем звёзд в нашей галактике",
        "🧠 Человек в среднем проводит 6 лет жизни во сне",
        "🧠 Слон — единственное животное, которое не умеет прыгать",
        "🧠 Скорость нервного импульса — около 120 м/с",
        "🧠 Морская звезда может вывернуть желудок наружу чтобы переварить добычу",
        "🧠 Дельфины дают друг другу имена и откликаются на них",
        "🧠 Металл галлий тает от тепла руки — его температура плавления 29°C",
        "🧠 Вода не имеет вкуса или запаха — всё что ты чувствуешь, это примеси",
        "🧠 Молоко в холодильнике хранится дольше, если стоит на верхней полке",
        "🧠 Паук может выжить под водой несколько часов внутри воздушного пузыря",
        "🧠 В Монако нет фермеров — это самая маленькая аграрно-нейтральная страна мира",
    ]
    await msg.reply(random.choice(facts))

async def cmd_quote(msg: Message):
    quotes = [
        "Сначала заставь работать, потом — сделай красиво. — Кент Бек",
        "Любой дурак может написать код для компьютера. Хорошие программисты пишут код для людей. — Фаулер",
        "Простота — высшая степень изысканности. — Леонардо да Винчи",
        "Жизнь — это то, что с тобой происходит, пока ты строишь другие планы. — Джон Леннон",
        "Будь собой — остальные роли уже заняты. — Оскар Уайлд",
        "Не важно, как медленно ты идёшь, главное — не останавливаться. — Конфуций",
        "Ты не можешь вернуться и изменить начало. Но ты можешь начать сейчас и изменить конец. — К. С. Льюис",
        "Лучший способ предсказать будущее — создать его. — Питер Друкер",
        "Не считай дни — сделай так, чтобы дни считались. — Мухаммед Али",
        "Люди редко преуспевают, если не получают удовольствия от того, чем занимаются. — Дейл Карнеги",
        "Всё, что ты делаешь, либо приближает тебя к мечте, либо отдаляет. — Стив Харви",
        "Перфекционизм — враг готового. — Рид Хоффман",
        "Единственный способ делать великую работу — любить то, что делаешь. — Стив Джобс",
        "Сила не в том, чтобы никогда не падать. Сила — в том, чтобы подниматься каждый раз. — Нельсон Мандела",
        "Мечты не работают, если не работаешь ты. — Джон Максвелл",
        "Делай что должен — и будь что будет. — Лев Толстой",
        "Жизнь — как вождение велосипеда. Чтобы не упасть, нужно двигаться. — Альберт Эйнштейн",
        "Не бойся медленно двигаться. Бойся стоять на месте. — Китайская пословица",
        "Успех — это идти от неудачи к неудаче, не теряя энтузиазма. — Уинстон Черчилль",
        "Твоё время ограничено. Не трать его на чужую жизнь. — Стив Джобс",
    ]
    await msg.reply(f"💬 {random.choice(quotes)}")

async def cmd_numerology(msg: Message, command: CommandObject = None):
    raw_name = (command.args if command and command.args else None) or msg.from_user.first_name or "—"
    n = sum(ord(c) for c in raw_name.lower() if c.isalpha()) % 9 + 1
    meanings = {
        1: ("👑 Лидер и первопроходец", "Ты рождён(а) вести за собой. Сила воли и независимость — твои главные черты."),
        2: ("🕊️ Дипломат и миротворец", "Ты создан(а) для гармонии. Умеешь слушать и находить компромисс там, где другие видят тупик."),
        3: ("🎨 Творец и коммуникатор", "Твоя жизнь — холст. Творчество, общение и радость — твоё предназначение."),
        4: ("🏗️ Строитель и организатор", "Ты — основа. Надёжность, системность и трудолюбие — твоя суперсила."),
        5: ("🌍 Искатель свободы", "Перемены — твоя стихия. Приключения и новый опыт наполняют тебя жизнью."),
        6: ("💙 Заботливый и ответственный", "Ты — опора для других. Семья, любовь и помощь ближним — смысл твоего пути."),
        7: ("🔭 Мыслитель и исследователь", "Ты ищешь глубину там, где другие видят поверхность. Истина — твоя цель."),
        8: ("💹 Материалист и бизнесмен", "Ты умеешь создавать и управлять ресурсами. Успех и власть — твои естественные спутники."),
        9: ("🌸 Гуманист и альтруист", "Ты живёшь ради других. Мудрость, сострадание и служение — твои высшие ценности."),
    }
    title, desc = meanings[n]
    display_name = html.escape(raw_name)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🔢 <b>Нумерология имени · {display_name}</b>\n\n"
        f"{brand.div()}\n"
        f"Число судьбы: <b>{n}</b>\n"
        f"Архетип: <b>{title}</b>\n\n"
        f"<i>{desc}</i>\n\n"
        f"{brand.div()}",
        parse_mode="HTML"
    )

async def cmd_bmi(msg: Message, command: CommandObject = None):
    if not (command and command.args): return await msg.reply("Использование: бми [вес в кг] [рост в см]\nПример: бми 70 175")
    try:
        parts = command.args.split()
        w, h = float(parts[0]), float(parts[1]) / 100
        bmi = w / (h * h)
        if bmi < 18.5: cat = "недостаточный вес"
        elif bmi < 25: cat = "нормальный вес ✅"
        elif bmi < 30: cat = "избыточный вес"
        else: cat = "ожирение"
        await msg.reply(f"⚖️ ИМТ: <b>{bmi:.1f}</b> — {cat}", parse_mode="HTML")
    except: await msg.reply("Пример: бми 70 175")

async def cmd_age(msg: Message, command: CommandObject = None):
    if not (command and command.args): return await msg.reply("Использование: возраст [год рождения]\nПример: возраст 2000")
    try:
        birth_year = int(command.args.strip())
        age = now_kyiv().year - birth_year
        await msg.reply(f"🎂 Возраст: <b>{age} лет</b>", parse_mode="HTML")
    except: await msg.reply("Пример: возраст 2000")

async def cmd_cat(msg: Message):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.thecatapi.com/v1/images/search") as resp:
                data = await resp.json()
                await msg.answer_photo(data[0]["url"], caption="😺 Котик дня!")
    except: await msg.reply("😿 Не удалось загрузить котика")

async def cmd_dog(msg: Message):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://dog.ceo/api/breeds/image/random") as resp:
                data = await resp.json()
                await msg.answer_photo(data["message"], caption="🐶 Собачка дня!")
    except: await msg.reply("🐶 Не удалось загрузить собачку")

# ═══════════════════════════════════════════════════════
# ПРАВИЛА ЧАТА
# ═══════════════════════════════════════════════════════
DEFAULT_RULES = """🌙 <b>Правила сообщества Lumena</b>

<b>👥 Для участников</b>

• Lumena — украинское сообщество. Чат предназначён для украинской аудитории.
• Вход для пользователей, поддерживающих российскую агрессию, а также аккаунтов для провокаций — запрещён. Администрация вправе ограничить доступ таким пользователям.
• Уважайте каждого участника. Оскорбления, унижения, травля, угрозы, дискриминация и разжигание конфликтов запрещены.
• Запрещены политические споры, пропаганда, оправдание войны, распространение экстремистских идей и материалов.
• Любая реклама без согласования с администрацией запрещена. Это касается Telegram-чатов, каналов, сайтов, услуг, товаров и любых сторонних проектов.
• Запрещён спам, флуд, массовая рассылка сообщений, чрезмерный капс и однотипные сообщения.
• Запрещено распространять личные данные других людей без их согласия.
• Не публикуйте материалы 18+, сцены насилия, шокирующий или запрещённый законом контент.
• Мошенничество, фишинг, вредоносные ссылки и попытки получения чужих данных запрещены.
• Уважайте личные границы. Если человек отказался от общения — не навязывайтесь.
• Использование нескольких аккаунтов для обхода наказаний запрещено.
• Решения администрации обязательны к исполнению. Несогласны — пишите в ЛС администратору.
• Незнание правил не освобождает от ответственности.

⸻

<b>👑 Правила для администрации</b>

• Относитесь ко всем участникам одинаково и беспристрастно.
• Используйте полномочия исключительно в интересах сообщества.
• Перед выдачей наказания по возможности изучайте ситуацию.
• Не злоупотребляйте правами и не используйте их в личных целях.
• Не удаляйте сообщения и не выдавайте наказания без причины.
• Соблюдайте уважительное общение даже при возникновении конфликтов.
• Не разглашайте внутреннюю информацию администрации.
• Важные решения согласовывайте с руководством сообщества.
• Администратор обязан соблюдать все правила наравне с обычными участниками.

⸻

<b>⚖️ Наказания</b>

• Предупреждение
• Мут
• Кик
• Временный бан
• Постоянный бан за грубые или повторные нарушения

⸻

<b>✨ Главный принцип Lumena</b>

Lumena — украинское сообщество для общения и новых знакомств в комфортной атмосфере. Соблюдайте правила, уважайте друг друга и помогайте поддерживать дружелюбное и безопасное пространство для всех. 🇺🇦"""

async def cmd_rules(msg: Message):
    r = chat_rules.get(msg.chat.id, DEFAULT_RULES)
    await msg.reply(f"📋 {r}", parse_mode="HTML")

async def cmd_setrules(msg: Message, command: CommandObject = None):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    if not (command and command.args): return await msg.reply("Укажи текст правил")
    chat_rules[msg.chat.id] = command.args
    await msg.reply("✅ Правила установлены!")

@dp.message(Command("объявление", "announce"))
async def cmd_announce(msg: Message, command: CommandObject = None):
    import re as _re

    # ── Проверка прав ────────────────────────────────────────────
    # В приватном чате is_admin() всегда True → явно проверяем роль
    if msg.chat.type == "private":
        allowed = (
            is_owner(msg)
            or has_role(msg.from_user.id,
                        "lead_admin", "co_admin", "admin", "moderator")
        )
        if not allowed:
            return await msg.reply("⛔ Только администрация")
    else:
        if not await is_admin(msg):
            return await msg.reply("⛔ Только админы")

    # ── Текст: всегда из оригинала msg.text (сохраняем регистр) ──
    raw = (msg.text or msg.caption or "").strip()
    text = _re.sub(r'^[!/]?\s*\S+\s*', '', raw, count=1).strip()

    if not text:
        return await msg.reply(
            "📢 <b>Отправь объявление:</b>\n\n"
            "<code>объявление Сегодня в 20:00 — ивент!</code>\n"
            "или\n"
            "<code>/объявление Текст</code>\n\n"
            "Сообщение уйдёт в паб-чат.",
            parse_mode="HTML"
        )

    # ── Цель ─────────────────────────────────────────────────────
    cid = msg.chat.id
    pub = _ank.get_pub_chat()
    target = pub if pub else cid

    announce_text = (
        f"📢 <b>ОБЪЯВЛЕНИЕ</b>\n"
        f"{brand.div()}\n"
        f"{html.escape(text)}\n"
        f"{brand.div()}"
    )

    try:
        await bot.send_message(target, announce_text, parse_mode="HTML")
        # В приватном чате — подтверждение с указанием куда ушло
        if msg.chat.type == "private":
            chat_name = "паб-чат" if pub else "чат"
            await msg.reply(
                f"✅ <b>Объявление отправлено в {chat_name}!</b>",
                parse_mode="HTML"
            )
        elif target != cid:
            await msg.reply("✅ Объявление отправлено в паб-чат!")
        else:
            await msg.reply("✅ Объявление отправлено!")
    except Exception as e:
        await msg.reply(
            f"❌ Не удалось отправить.\n"
            f"Проверь права бота в паб-чате.\n"
            f"<code>{e}</code>",
            parse_mode="HTML"
        )


@dp.message(Command("updatesave"))
async def cmd_updatesave(msg: Message):
    """Одноразово публикует фаундерское обновление о сохранении данных."""
    global _save_update_sent
    if not (is_owner(msg) or has_role(msg.from_user.id, "lead_admin")):
        return await msg.reply("⛔ Эта команда доступна только фаундеру.")
    if _save_update_sent:
        return await msg.reply("ℹ️ Это обновление уже было опубликовано.")

    pub_chat = _ank.get_pub_chat()
    if not pub_chat:
        return await msg.reply("❌ Паб-чат не настроен. Сначала используй /setpubchat в нужном чате.")

    update_text = (
        f"{brand.hdr()}\n\n"
        "<b>✨ Обновление Lumena</b>\n\n"
        "<b>Исправлено сохранение данных бота.</b>\n\n"
        "Теперь надёжно сохраняются:\n"
        "• браки и разводы\n"
        "• стрики и чекины\n"
        "• баланс LMN, банк и экономика\n"
        "• репутация\n"
        "• роли пользователей\n"
        "• анкеты и настройки чатов\n\n"
        "Данные сохраняются после обновлений и перезапусков бота.\n\n"
        f"{brand.div()}"
    )
    try:
        await bot.send_message(pub_chat, update_text, parse_mode="HTML")
    except Exception as error:
        logging.error("Не удалось отправить обновление о сохранении: %s", error)
        return await msg.reply("❌ Не удалось отправить сообщение в паб-чат. Проверь права бота.")

    _save_update_sent = True
    save_data()
    await msg.reply("✅ Обновление опубликовано в паб-чате. Повторно команда недоступна.")

# ═══════════════════════════════════════════════════════
# ЛУМЕНА АИ
# ═══════════════════════════════════════════════════════
LUMENA_NAMES = ["лумена","lumena","лум","лумка"]

def is_lumena_addressed(msg: Message) -> bool:
    """Лумена реагирует только если:
    - личный чат
    - ответ на её сообщение
    - @упоминание бота
    - ПЕРВОЕ слово сообщения — её имя
    """
    if msg.chat.type == "private":
        return True
    # Ответ на сообщение бота
    if msg.reply_to_message and msg.reply_to_message.from_user:
        if msg.reply_to_message.from_user.is_bot:
            return True
    # @упоминание бота
    if msg.entities:
        for entity in msg.entities:
            if entity.type == "mention":
                mention = msg.text[entity.offset:entity.offset + entity.length].lower()
                if "lumena" in mention or "лумен" in mention:
                    return True
    # Только если ПЕРВОЕ слово — имя Лумены
    text = (msg.text or "").strip().lower()
    first_word = re.split(r"[\s,!?.:]", text)[0]
    return first_word in LUMENA_NAMES

# ═══════════════════════════════════════════════════════
# V6 — XP / УРОВНИ / ДОСТИЖЕНИЯ
# ═══════════════════════════════════════════════════════
async def cmd_level(msg: Message):
    uid  = msg.from_user.id
    name = html.escape(msg.from_user.first_name or "—")
    xp   = user_xp.get(uid, 0)
    lvl, start, end = get_xp_level(xp)
    bar  = xp_bar(xp)
    need = max(0, end - xp)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"⚡ <b>Уровень · {name}</b>\n\n"
        f"{brand.div()}\n"
        f"🏷 Уровень: <b>{lvl}</b>\n"
        f"✨ XP: <b>{xp:,}</b>\n"
        f"📊 {bar}\n"
        + (f"⬆️ До следующего: <b>{need:,} XP</b>\n" if need > 0 and end > start else "🏆 <b>Максимальный уровень!</b>\n")
        + f"\n{brand.div()}",
        parse_mode="HTML"
    )

async def cmd_rank(msg: Message):
    if msg.chat.type == "private":
        return await msg.reply("Команда работает только в групповых чатах")
    cid  = msg.chat.id
    uid  = msg.from_user.id
    name = html.escape(msg.from_user.first_name or "—")
    # Берём всех известных участников + гарантированно добавляем текущего юзера
    members = (
        set(chat_members.get(cid, {}).keys()) |
        set(chat_members.get(econ_cid(cid), {}).keys()) |
        {uid}
    )
    # Если у юзера есть XP, показываем его в глобальном топе
    if user_xp.get(uid, 0) > 0 and msg.chat.type != "private":
        members |= set(user_xp.keys())
    ranked  = sorted(members, key=lambda u: user_xp.get(u, 0), reverse=True)
    pos     = next((i + 1 for i, u in enumerate(ranked) if u == uid), None)
    xp      = user_xp.get(uid, 0)
    lvl     = get_xp_level(xp)[0]
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🏆 <b>Ранг · {name}</b>\n\n"
        f"{brand.div()}\n"
        f"📍 Место: <b>#{pos}</b> из {len(ranked)}\n"
        f"✨ XP: <b>{xp:,}</b>\n"
        f"🏷 Уровень: <b>{lvl}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML"
    )

async def cmd_top_xp(msg: Message):
    if msg.chat.type == "private":
        members = set(user_xp.keys())
        title   = "🌍 Глобальный топ XP"
    else:
        cid     = msg.chat.id
        members = set(chat_members.get(cid, {}).keys()) | set(chat_members.get(econ_cid(cid), {}).keys())
        title   = f"🏆 Топ XP · {html.escape(msg.chat.title or 'чат')}"
    top = sorted(members, key=lambda u: user_xp.get(u, 0), reverse=True)[:10]
    if not top:
        return await msg.reply("📊 Пока нет данных XP")
    medals = ["🥇","🥈","🥉"] + [f"{i}." for i in range(4, 11)]
    lines  = [f"{brand.hdr()}\n\n{title}\n\n{brand.div()}"]
    for i, uid in enumerate(top):
        name = html.escape(
            chat_members.get(msg.chat.id, {}).get(uid) or
            chat_members.get(econ_cid(msg.chat.id), {}).get(uid) or
            next((m.get(uid) for m in chat_members.values() if uid in m), None) or
            f"ID {uid}"
        )
        lvl = get_xp_level(user_xp.get(uid, 0))[0]
        lines.append(f"{medals[i]} <b>{name}</b> — {user_xp.get(uid, 0):,} XP · {lvl}")
    lines.append(f"\n{brand.div()}")
    await msg.reply("\n".join(lines), parse_mode="HTML")

async def cmd_achievements(msg: Message):
    uid    = msg.from_user.id
    name   = html.escape(msg.from_user.first_name or "—")
    _check_achievements(uid)
    earned = set(user_achievements.get(uid, []))
    lines  = [f"{brand.hdr()}\n\n🏆 <b>Достижения · {name}</b>\n\n{brand.div()}"]
    for ach_id, (icon, title_, desc) in ACHIEVEMENT_INFO.items():
        check = "✅" if ach_id in earned else "🔒"
        style = f"<b>{title_}</b>" if ach_id in earned else f"<i>{title_}</i>"
        lines.append(f"{check} {icon} {style} — {desc}")
    lines.append(f"\n{brand.div()}\n✅ Получено: <b>{len(earned)}/{len(ACHIEVEMENT_INFO)}</b>")
    await msg.reply("\n".join(lines), parse_mode="HTML")

async def cmd_messages(msg: Message):
    uid   = msg.from_user.id
    name  = html.escape(msg.from_user.first_name or "—")
    total = sum(m.get(uid, 0) for m in user_messages.values())
    xp    = user_xp.get(uid, 0)
    lvl   = get_xp_level(xp)[0]
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"💬 <b>Сообщения · {name}</b>\n\n"
        f"{brand.div()}\n"
        f"📨 Всего сообщений: <b>{total:,}</b>\n"
        f"✨ XP заработано: <b>{xp:,}</b>\n"
        f"🏷 Уровень: <b>{lvl}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML"
    )

async def cmd_activity(msg: Message):
    uid       = msg.from_user.id
    name      = html.escape(msg.from_user.first_name or "—")
    xp        = user_xp.get(uid, 0)
    lvl       = get_xp_level(xp)[0]
    total_msg = sum(m.get(uid, 0) for m in user_messages.values())
    cid_s     = econ_cid(msg.chat.id) if msg.chat.type != "private" else 0
    streak_v  = max((streaks.get(c, {}).get(uid, {}).get("count", 0) for c in streaks), default=0)
    bal       = get_balance(uid) + bank_balances.get(uid, 0)
    ach_cnt   = len(user_achievements.get(uid, []))
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"📊 <b>Активность · {name}</b>\n\n"
        f"{brand.div()}\n"
        f"🏷 Уровень: <b>{lvl}</b>  ✨ XP: <b>{xp:,}</b>\n"
        f"💬 Сообщений: <b>{total_msg:,}</b>\n"
        f"🔥 Стрик: <b>{streak_v} дн.</b>\n"
        f"💰 Баланс (кош.+банк): <b>{fmt_lmn(bal)}</b>\n"
        f"🏆 Достижений: <b>{ach_cnt}/{len(ACHIEVEMENT_INFO)}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML"
    )

# ═══════════════════════════════════════════════════════
# V6 — ЕЖЕДНЕВНЫЕ НАГРАДЫ
# ═══════════════════════════════════════════════════════
async def cmd_daily(msg: Message):
    uid      = msg.from_user.id
    name     = html.escape(msg.from_user.first_name or "—")
    today    = today_kyiv().isoformat()
    if daily_cooldown.get(uid) == today:
        streak_v = max((streaks.get(c, {}).get(uid, {}).get("count", 0) for c in streaks), default=0)
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            f"⏳ <b>Дейли уже получен!</b>\n\n"
            f"{brand.div()}\n"
            f"🔥 Стрик: <b>{streak_v} дн.</b>\n"
            f"📅 Возвращайся завтра!\n\n"
            f"💡 Пока можешь: <code>задания</code> · <code>гороскоп</code> · <code>предсказание</code>\n\n"
            f"{brand.div()}",
            parse_mode="HTML"
        )
    reward = random.randint(500, 2000)
    add_balance(uid, reward)
    xp_got   = 50
    lvl_up   = award_xp(uid, xp_got)
    daily_cooldown[uid] = today
    save_data()
    schedule_state_save("дейли")
    lvl      = get_xp_level(user_xp.get(uid, 0))[0]
    up_text  = f"\n🆙 <b>Новый уровень: {lvl}!</b>" if lvl_up else ""
    streak_v = max((streaks.get(c, {}).get(uid, {}).get("count", 0) for c in streaks), default=0)
    streak_tip = f"\n🔥 Стрик: <b>{streak_v} дн.</b>" if streak_v > 0 else ""
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🎁 <b>Ежедневная награда · {name}</b>\n\n"
        f"{brand.div()}\n"
        f"💰 +<b>{fmt_lmn(reward)} LMN</b>\n"
        f"✨ +<b>{xp_got} XP</b>{up_text}{streak_tip}\n\n"
        f"📅 Возвращайся завтра!\n"
        f"💡 Не забудь: <code>задания</code> для бонуса за все задания\n\n"
        f"{brand.div()}",
        parse_mode="HTML"
    )

def _this_week() -> str:
    """ISO year-week string, e.g. '2026-W32'."""
    d   = today_kyiv()
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"

async def cmd_bonus(msg: Message):
    uid      = msg.from_user.id
    name     = html.escape(msg.from_user.first_name or "—")
    week_key = _this_week()
    st = max((streaks.get(c, {}).get(uid, {}).get("count", 0) for c in streaks), default=0)
    bar_filled = min(st, 7)
    bar = "🟩" * bar_filled + "⬜" * (7 - bar_filled)
    if bonus_weekly_cd.get(uid) == week_key:
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            f"✅ <b>Бонус за стрик получен!</b>\n\n"
            f"{brand.div()}\n"
            f"🔥 Стрик: <b>{st} дн.</b>\n"
            f"{bar}\n\n"
            f"📅 Возвращайся на следующей неделе\n\n"
            f"{brand.div()}",
            parse_mode="HTML"
        )
    if st < 7:
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            f"🎯 <b>Недельный бонус за стрик</b>\n\n"
            f"{brand.div()}\n"
            f"🔥 Прогресс: <b>{st}/7 дн.</b>\n"
            f"{bar}\n\n"
            f"Чекинься каждый день — и получишь:\n"
            f"💰 <b>5 000 LMN</b> + ✨ <b>100 XP</b>\n\n"
            f"{brand.div()}",
            parse_mode="HTML"
        )
    reward = 5000
    add_balance(uid, reward)
    award_xp(uid, 100)
    bonus_weekly_cd[uid] = week_key
    save_data()
    schedule_state_save("бонус за стрик")
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🎊 <b>Недельный бонус · {name}</b>\n\n"
        f"{brand.div()}\n"
        f"🔥 Стрик: <b>{st} дн.</b>\n"
        f"{bar}\n\n"
        f"💰 +<b>{fmt_lmn(reward)} LMN</b>\n"
        f"✨ +<b>100 XP</b>\n\n"
        f"{brand.div()}\n"
        f"<i>Продолжай чекиниться каждый день!</i> 🌟",
        parse_mode="HTML"
    )

async def cmd_tasks(msg: Message):
    uid       = msg.from_user.id
    name      = html.escape(msg.from_user.first_name or "—")
    today_str = today_kyiv().isoformat()
    did_daily   = daily_cooldown.get(uid) == today_str
    played      = daily_games.get(uid) == today_str
    msgs_today  = (daily_msg_cnt.get(uid) or {}).get("count", 0) \
                  if (daily_msg_cnt.get(uid) or {}).get("date") == today_str else 0
    streak_v  = max((streaks.get(c, {}).get(uid, {}).get("count", 0) for c in streaks), default=0)
    task_list = [
        ("💬", "Написать 10 сообщений",   min(msgs_today, 10), 10, msgs_today >= 10),
        ("📅", "Получить дейли",           1 if did_daily else 0, 1, did_daily),
        ("🎰", "Сыграть в игру",           1 if played else 0, 1, played),
        ("🔥", "Поддержать стрик 3+ дня",  min(streak_v, 3), 3, streak_v >= 3),
    ]
    done      = sum(1 for *_, ok in task_list if ok)
    all_done  = done == len(task_list)
    bonus_got = tasks_bonus_cd.get(uid) == today_str
    lines = [f"{brand.hdr()}\n\n📋 <b>Задания дня · {name}</b>\n\n{brand.div()}"]
    for icon, tname, cur, mx, ok in task_list:
        chk = "✅" if ok else "⬜"
        lines.append(f"{chk} {icon} {tname} ({cur}/{mx})")
    bar_done = "🟩" * done + "⬜" * (len(task_list) - done)
    lines.append(f"\n{brand.div()}\n{bar_done}  <b>{done}/{len(task_list)}</b>")
    if all_done and not bonus_got:
        # Начисляем бонус за все задания
        add_balance(uid, 1000)
        award_xp(uid, 75)
        tasks_bonus_cd[uid] = today_str
        save_data()
        lines.append(
            f"\n🎉 <b>Все задания выполнены!</b>\n"
            f"💰 +<b>1 000 LMN</b> + ✨ +<b>75 XP</b> начислено!"
        )
    elif all_done and bonus_got:
        lines.append(f"\n✅ <b>Бонус за все задания уже получен!</b>")
    else:
        remaining = len(task_list) - done
        lines.append(f"\n💡 Осталось: <b>{remaining}</b> — выполни все и получи <b>+1 000 LMN + 75 XP</b>!")
    lines.append(f"\n{brand.div()}")
    await msg.reply("\n".join(lines), parse_mode="HTML")

async def cmd_rewards(msg: Message):
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🎁 <b>Все источники наград</b>\n\n"
        f"{brand.div()}\n"
        f"📅 <b>Дейли</b> — 500–2 000 LMN + 50 XP\n"
        f"   └ <code>дейли</code> — раз в 24 часа\n\n"
        f"📋 <b>Все задания</b> — 1 000 LMN + 75 XP\n"
        f"   └ <code>задания</code> — выполни все 4 в день\n\n"
        f"🔥 <b>Стрик 7 дней</b> — 5 000 LMN + 100 XP\n"
        f"   └ <code>бонус</code> — за непрерывный чекин 7 дн.\n\n"
        f"💍 <b>Брак</b> — 500 LMN каждому\n"
        f"   └ <code>пожениться @username</code>\n\n"
        f"🌧 <b>Дождь монет</b> — случайный бонус\n"
        f"   └ выдаётся администраторами в чате\n\n"
        f"🔗 <b>Реферал</b> — 1 000 LMN + 100 XP\n"
        f"   └ <code>реферал</code> — за каждого приглашённого\n\n"
        f"{brand.div()}",
        parse_mode="HTML"
    )

async def cmd_leaderboard(msg: Message):
    all_uids = set(user_xp.keys())
    top      = sorted(all_uids, key=lambda u: user_xp.get(u, 0), reverse=True)[:10]
    if not top:
        return await msg.reply("📊 Пока нет данных")
    medals = ["🥇","🥈","🥉"] + [f"{i}." for i in range(4, 11)]
    lines  = [f"{brand.hdr()}\n\n🌍 <b>Глобальный лидерборд XP</b>\n\n{brand.div()}"]
    for i, uid in enumerate(top):
        name = html.escape(
            next((m.get(uid) for m in chat_members.values() if uid in m), None) or f"ID {uid}"
        )
        lines.append(f"{medals[i]} <b>{name}</b> — {user_xp.get(uid, 0):,} XP")
    lines.append(f"\n{brand.div()}")
    await msg.reply("\n".join(lines), parse_mode="HTML")

# ═══════════════════════════════════════════════════════
# V6 — НОВЫЕ ИГРЫ
# ═══════════════════════════════════════════════════════
def _game_result(uid: int, won: bool):
    _games_played[uid] = _games_played.get(uid, 0) + 1
    daily_games[uid]   = today_kyiv().isoformat()   # отмечаем сегодняшнюю игру
    if won:
        _games_won[uid] = _games_won.get(uid, 0) + 1
    _check_achievements(uid)
    save_data()   # синхронный сброс — данные игры не теряются при перезапуске

async def _priv_check(msg: Message) -> bool:
    """Игры работают везде — проверка удалена."""
    return True

@dp.message(Command("орёл", "coinflip"))
async def cmd_coinflip(msg: Message, command: CommandObject = None):
    if not await _priv_check(msg): return
    if not command or not command.args:
        return await msg.reply("Использование: <b>орёл [сумма]</b>", parse_mode="HTML")
    try:
        bet = int(command.args.split()[0])
    except ValueError:
        return await msg.reply("❌ Укажи целое число")
    uid = msg.from_user.id
    if bet <= 0 or get_balance(uid) < bet:
        return await msg.reply("❌ Недостаточно LMN или сумма некорректна")
    won = random.random() < 0.5
    result = "🦅 Орёл" if won else "🪙 Решка"
    _game_result(uid, won)
    if won:
        add_balance(uid, bet)
        award_xp(uid, 10)
        out = f"✅ <b>Победа! +{fmt_lmn(bet)} LMN</b>"
    else:
        add_balance(uid, -bet)
        out = f"❌ <b>Проигрыш! -{fmt_lmn(bet)} LMN</b>"
    schedule_state_save("coinflip")
    await msg.reply(
        f"🪙 <b>Монетка</b> — ставка {fmt_lmn(bet)} LMN\n\n"
        f"Выпало: <b>{result}</b>\n\n{out}",
        parse_mode="HTML"
    )

@dp.message(Command("плинко", "plinko"))
async def cmd_plinko(msg: Message, command: CommandObject = None):
    if not await _priv_check(msg): return
    if not command or not command.args:
        return await msg.reply("Использование: <b>плинко [сумма]</b>", parse_mode="HTML")
    try:
        bet = int(command.args.split()[0])
    except ValueError:
        return await msg.reply("❌ Укажи целое число")
    uid = msg.from_user.id
    if bet <= 0 or get_balance(uid) < bet:
        return await msg.reply("❌ Недостаточно LMN")
    mults   = [0.2, 0.5, 0.5, 1.0, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0]
    weights = [5, 10, 10, 20, 20, 15, 10, 5, 4, 1]
    mult    = random.choices(mults, weights=weights, k=1)[0]
    winnings = max(1, int(bet * mult)) if mult > 0 else 0  # минимум 1 при ненулевом множителе
    diff     = winnings - bet
    add_balance(uid, diff)
    _game_result(uid, winnings > bet)   # победа только если реально больше ставки
    award_xp(uid, random.randint(5, 20))
    schedule_state_save("plinko")
    emoji = "✅" if winnings > bet else ("⚖️" if winnings == bet else "❌")
    sign  = "+" if diff > 0 else ""
    await msg.reply(
        f"🎯 <b>Плинко</b> — ставка {fmt_lmn(bet)} LMN\n\n"
        f"🎰  ● ● ● ● ●\n"
        f"    ● ● ● ● ●\n"
        f"      ● ● ● ●\n\n"
        f"💥 Множитель: <b>{mult}×</b>\n"
        f"{emoji} Результат: <b>{fmt_lmn(winnings)} LMN</b> ({sign}{fmt_lmn(diff)})",
        parse_mode="HTML"
    )

@dp.message(Command("лимбо", "limbo"))
async def cmd_limbo(msg: Message, command: CommandObject = None):
    if not await _priv_check(msg): return
    usage = "Использование: <b>лимбо [сумма] [цель ×]</b>\nПример: лимбо 1000 2.0"
    if not command or not command.args:
        return await msg.reply(usage, parse_mode="HTML")
    parts = command.args.split()
    if len(parts) < 2:
        return await msg.reply(usage, parse_mode="HTML")
    try:
        bet    = int(parts[0])
        target = float(parts[1])
    except ValueError:
        return await msg.reply("❌ Укажи число и дробное цель")
    if not math.isfinite(target):
        return await msg.reply("❌ Цель должна быть обычным числом")
    uid = msg.from_user.id
    if bet <= 0 or get_balance(uid) < bet:
        return await msg.reply("❌ Недостаточно LMN")
    if not 1.01 <= target <= 100:
        return await msg.reply("❌ Цель от 1.01 до 100")
    win_prob = min(0.97 / target, 0.97)
    won      = random.random() < win_prob
    roll     = round(random.uniform(target, target * 2) if won else random.uniform(1.0, target - 0.01), 2)
    if won:
        winnings = int(bet * target)
        add_balance(uid, winnings - bet)
        _game_result(uid, True)
        award_xp(uid, 20)
        result_text = f"✅ <b>Победа! +{fmt_lmn(winnings - bet)} LMN</b>"
    else:
        add_balance(uid, -bet)
        _game_result(uid, False)
        result_text = f"❌ <b>Проигрыш! -{fmt_lmn(bet)} LMN</b>"
    schedule_state_save("limbo")
    await msg.reply(
        f"🚀 <b>Лимбо</b> — ставка {fmt_lmn(bet)} LMN\n\n"
        f"🎯 Цель: <b>{target}×</b>\n"
        f"🎲 Выпало: <b>{roll:.2f}×</b>\n\n"
        f"{result_text}",
        parse_mode="HTML"
    )

@dp.message(Command("краш", "crash"))
async def cmd_crash(msg: Message, command: CommandObject = None):
    if not await _priv_check(msg): return
    if not command or not command.args:
        return await msg.reply("Использование: <b>краш [сумма]</b>", parse_mode="HTML")
    try:
        bet = int(command.args.split()[0])
    except ValueError:
        return await msg.reply("❌ Укажи целое число")
    uid = msg.from_user.id
    if bet <= 0 or get_balance(uid) < bet:
        return await msg.reply("❌ Недостаточно LMN")
    if uid in _crash_games:
        return await msg.reply("⚡ У тебя уже активная игра краш! Нажми Забрать.")
    add_balance(uid, -bet)
    crash_at = round(random.choices(
        [round(random.uniform(1.0, 1.5), 2), round(random.uniform(1.5, 4.0), 2),
         round(random.uniform(4.0, 10.0), 2), round(random.uniform(10.0, 20.0), 2)],
        weights=[40, 35, 20, 5], k=1
    )[0], 2)
    _crash_games[uid] = {"bet": bet, "multiplier": 1.0, "crash_at": crash_at, "active": True}
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💰 Забрать", callback_data=f"crash:out:{uid}:{bet}")
    ]])
    sent = await msg.reply(
        f"🚀 <b>КРАШ</b> — ставка {fmt_lmn(bet)} LMN\n\n"
        f"📈 Множитель: <b>1.00×</b>\n"
        f"⚡ Нажми Забрать пока не поздно!",
        parse_mode="HTML", reply_markup=kb
    )
    _crash_games[uid]["msg_id"]  = sent.message_id
    _crash_games[uid]["chat_id"] = msg.chat.id

    async def crash_tick():
        mult = 1.0
        while True:
            await asyncio.sleep(1.5)
            if uid not in _crash_games or not _crash_games[uid].get("active"):
                break
            mult = round(mult + random.uniform(0.05, 0.25), 2)
            _crash_games[uid]["multiplier"] = mult
            if mult >= crash_at:
                _crash_games.pop(uid, None)
                _game_result(uid, False)
                try:
                    await bot.edit_message_text(
                        f"💥 <b>КРАШ!</b> — ставка {fmt_lmn(bet)} LMN\n\n"
                        f"📉 Упал на <b>{mult:.2f}×</b>\n"
                        f"❌ Ты потерял <b>{fmt_lmn(bet)} LMN</b>",
                        chat_id=msg.chat.id, message_id=sent.message_id, parse_mode="HTML"
                    )
                except Exception:
                    pass
                break
            try:
                await bot.edit_message_text(
                    f"🚀 <b>КРАШ</b> — ставка {fmt_lmn(bet)} LMN\n\n"
                    f"📈 Множитель: <b>{mult:.2f}×</b>\n"
                    f"⚡ Нажми Забрать пока не поздно!",
                    chat_id=msg.chat.id, message_id=sent.message_id,
                    parse_mode="HTML", reply_markup=kb
                )
            except Exception:
                break
    asyncio.create_task(crash_tick())

@dp.callback_query(F.data.startswith("crash:out:"))
async def cb_crash_out(cb: CallbackQuery):
    parts = cb.data.split(":")
    uid   = int(parts[2])
    if cb.from_user.id != uid:
        return await cb.answer("Это не твоя игра!", show_alert=True)
    game = _crash_games.pop(uid, None)
    if not game:
        return await cb.answer("Игра уже закончилась!", show_alert=True)
    game["active"] = False
    mult      = game.get("multiplier", 1.0)
    crash_at  = game.get("crash_at", 1.0)
    real_bet  = game["bet"]   # берём ставку из состояния игры, не из callback
    # если успели нажать после краша — выплаты нет
    if mult >= crash_at:
        _game_result(uid, False)
        schedule_state_save("crash late cashout")
        return await cb.answer("💥 Краш уже произошёл! Ставка потеряна.", show_alert=True)
    winnings = int(real_bet * mult)
    add_balance(uid, winnings)
    _game_result(uid, True)
    award_xp(uid, int(mult * 5))
    schedule_state_save("crash cashout")
    await cb.message.edit_text(
        f"✅ <b>Забрал!</b>\n\n"
        f"📈 Множитель: <b>{mult:.2f}×</b>\n"
        f"💰 +<b>{fmt_lmn(winnings)} LMN</b>\n"
        f"✨ +{int(mult*5)} XP",
        parse_mode="HTML"
    )
    await cb.answer(f"✅ +{fmt_lmn(winnings)} LMN!")

# ── Блэкджек ───────────────────────────────────────────
_BJ_VALUES = [2,3,4,5,6,7,8,9,10,10,10,10,11] * 4

def _bj_val(hand: list) -> int:
    v = sum(hand); a = hand.count(11)
    while v > 21 and a:
        v -= 10; a -= 1
    return v

def _bj_names(hand: list) -> str:
    """Отображает карты. hand — список int (значения карт).
    Масть выбирается один раз по индексу, не случайно — карта не меняет масть."""
    suits = ["♠","♥","♦","♣"]
    nm    = {11:"A",10:"10",9:"9",8:"8",7:"7",6:"6",5:"5",4:"4",3:"3",2:"2"}
    return " ".join(
        f"{nm.get(c,'?')}{suits[i % len(suits)]}"
        for i, c in enumerate(hand)
    )

@dp.message(Command("блэкджек", "blackjack"))
async def cmd_blackjack(msg: Message, command: CommandObject = None):
    if not await _priv_check(msg): return
    if not command or not command.args:
        return await msg.reply("Использование: <b>блэкджек [сумма]</b>", parse_mode="HTML")
    try:
        bet = int(command.args.split()[0])
    except ValueError:
        return await msg.reply("❌ Укажи целое число")
    uid = msg.from_user.id
    if bet <= 0 or get_balance(uid) < bet:
        return await msg.reply("❌ Недостаточно LMN")
    if uid in _bj_games:
        return await msg.reply("⚡ У тебя уже активная игра блэкджек!")
    deck  = _BJ_VALUES.copy(); random.shuffle(deck)
    ph    = [deck.pop(), deck.pop()]
    dh    = [deck.pop(), deck.pop()]
    _bj_games[uid] = {"bet": bet, "player": ph, "dealer": dh, "deck": deck}
    add_balance(uid, -bet)
    pv = _bj_val(ph)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🃏 Взять", callback_data=f"bj:hit:{uid}"),
        InlineKeyboardButton(text="✋ Стоп",  callback_data=f"bj:stand:{uid}"),
    ]])
    if pv == 21:
        _bj_games.pop(uid, None)
        wins = int(bet * 2.5)
        add_balance(uid, wins)
        _game_result(uid, True)
        award_xp(uid, 30)
        schedule_state_save("blackjack")
        return await msg.reply(
            f"🃏 <b>Блэкджек!</b>\n\n"
            f"Твои карты: {_bj_names(ph)} = <b>21</b>\n\n"
            f"✅ <b>БЛЭКДЖЕК! +{fmt_lmn(wins - bet)} LMN</b>",
            parse_mode="HTML"
        )
    await msg.reply(
        f"🃏 <b>Блэкджек</b> — ставка {fmt_lmn(bet)} LMN\n\n"
        f"Твои карты: {_bj_names(ph)} = <b>{pv}</b>\n"
        f"Дилер: {_bj_names([dh[0]])} + 🂠\n\n"
        f"Что делаешь?",
        parse_mode="HTML", reply_markup=kb
    )

@dp.callback_query(F.data.startswith("bj:"))
async def cb_bj(cb: CallbackQuery):
    parts  = cb.data.split(":")
    action = parts[1]; uid = int(parts[2])
    if cb.from_user.id != uid:
        return await cb.answer("Это не твоя игра!", show_alert=True)
    game = _bj_games.get(uid)
    if not game:
        return await cb.answer("Игра не найдена!", show_alert=True)
    bet = game["bet"]; ph = game["player"]; dh = game["dealer"]; deck = game["deck"]
    if action == "hit":
        ph.append(deck.pop() if deck else random.choice(_BJ_VALUES))
        pv = _bj_val(ph)
        if pv > 21:
            _bj_games.pop(uid, None)
            _game_result(uid, False)
            schedule_state_save("blackjack")
            await cb.message.edit_text(
                f"🃏 <b>Блэкджек</b>\n\nТвои: {_bj_names(ph)} = <b>{pv}</b>\n\n"
                f"❌ <b>Перебор! -{fmt_lmn(bet)} LMN</b>", parse_mode="HTML"
            )
            return await cb.answer("❌ Перебор!")
        if pv == 21:
            action = "stand"
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🃏 Взять", callback_data=f"bj:hit:{uid}"),
                InlineKeyboardButton(text="✋ Стоп",  callback_data=f"bj:stand:{uid}"),
            ]])
            await cb.message.edit_text(
                f"🃏 <b>Блэкджек</b>\n\nТвои: {_bj_names(ph)} = <b>{pv}</b>\n"
                f"Дилер: {_bj_names([dh[0]])} + 🂠\n\nЧто делаешь?",
                parse_mode="HTML", reply_markup=kb
            )
            return await cb.answer()
    if action == "stand":
        _bj_games.pop(uid, None)
        pv = _bj_val(ph)
        while _bj_val(dh) < 17:
            dh.append(deck.pop() if deck else random.choice(_BJ_VALUES))
        dv = _bj_val(dh)
        if dv > 21 or pv > dv:
            add_balance(uid, bet * 2); _game_result(uid, True); award_xp(uid, 15)
            res = f"✅ <b>Победа! +{fmt_lmn(bet)} LMN</b>"
        elif pv == dv:
            add_balance(uid, bet); _game_result(uid, False)
            res = "🤝 <b>Ничья! Ставка возвращена</b>"
        else:
            _game_result(uid, False)
            res = f"❌ <b>Проигрыш! -{fmt_lmn(bet)} LMN</b>"
        schedule_state_save("blackjack")
        await cb.message.edit_text(
            f"🃏 <b>Блэкджек</b>\n\nТвои: {_bj_names(ph)} = <b>{pv}</b>\n"
            f"Дилер: {_bj_names(dh)} = <b>{dv}</b>\n\n{res}", parse_mode="HTML"
        )
        await cb.answer()

# ── Мины ───────────────────────────────────────────────
_MINES_SIZE = 5; _MINES_COUNT = 5

def _mines_kb(uid: int, revealed: set) -> InlineKeyboardMarkup:
    rows = []
    for r in range(_MINES_SIZE):
        row = []
        for c in range(_MINES_SIZE):
            idx = r * _MINES_SIZE + c
            txt = "💎" if idx in revealed else "⬜"
            cb_ = "mines:noop" if idx in revealed else f"mines:click:{uid}:{idx}"
            row.append(InlineKeyboardButton(text=txt, callback_data=cb_))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="💰 Забрать", callback_data=f"mines:cashout:{uid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@dp.message(Command("мины", "mines"))
async def cmd_mines(msg: Message, command: CommandObject = None):
    if not await _priv_check(msg): return
    if not command or not command.args:
        return await msg.reply("Использование: <b>мины [сумма]</b>", parse_mode="HTML")
    try:
        bet = int(command.args.split()[0])
    except ValueError:
        return await msg.reply("❌ Укажи целое число")
    uid = msg.from_user.id
    if bet <= 0 or get_balance(uid) < bet:
        return await msg.reply("❌ Недостаточно LMN")
    if uid in _mines_games:
        return await msg.reply("⚡ У тебя уже активная игра мины!")
    total_cells = _MINES_SIZE * _MINES_SIZE
    mines_cells = set(random.sample(range(total_cells), _MINES_COUNT))
    add_balance(uid, -bet)
    _mines_games[uid] = {"bet": bet, "mines": mines_cells, "revealed": set(), "mult": 1.0}
    await msg.reply(
        f"💣 <b>Мины</b> — ставка {fmt_lmn(bet)} LMN\n\n"
        f"Открывай клетки, избегай мин ({_MINES_COUNT} мин)\n"
        f"📈 Множитель: <b>1.00×</b>",
        parse_mode="HTML", reply_markup=_mines_kb(uid, set())
    )

@dp.callback_query(F.data.startswith("mines:"))
async def cb_mines(cb: CallbackQuery):
    parts  = cb.data.split(":")
    action = parts[1]
    if action == "noop":
        return await cb.answer()
    uid = int(parts[2])
    if cb.from_user.id != uid:
        return await cb.answer("Это не твоя игра!", show_alert=True)
    game = _mines_games.get(uid)
    if not game:
        return await cb.answer("Игра не найдена!", show_alert=True)
    bet = game["bet"]; mines = game["mines"]; revealed = game["revealed"]
    if action == "cashout":
        _mines_games.pop(uid, None)
        mult = game["mult"]; winnings = int(bet * mult)
        add_balance(uid, winnings); _game_result(uid, True); award_xp(uid, int(mult * 5))
        schedule_state_save("mines")
        await cb.message.edit_text(
            f"💰 <b>Забрал!</b>\n\n"
            f"💎 Открыто: {len(revealed)} клеток\n"
            f"📈 Множитель: <b>{mult:.2f}×</b>\n"
            f"✅ +<b>{fmt_lmn(winnings)} LMN</b>",
            parse_mode="HTML"
        )
        return await cb.answer(f"+{fmt_lmn(winnings)}!")
    if action == "click":
        idx = int(parts[3])
        total_cells = _MINES_SIZE * _MINES_SIZE
        # защита от невалидного индекса (подделанный callback)
        if not (0 <= idx < total_cells):
            return await cb.answer("Неверная клетка!", show_alert=True)
        # защита от повторного клика по уже открытой клетке
        if idx in revealed:
            return await cb.answer()
        if idx in mines:
            _mines_games.pop(uid, None); _game_result(uid, False)
            schedule_state_save("mines boom")
            show_rows = []
            for r in range(_MINES_SIZE):
                row = []
                for c in range(_MINES_SIZE):
                    i = r * _MINES_SIZE + c
                    txt = "💥" if i == idx else ("💣" if i in mines else ("💎" if i in revealed else "⬜"))
                    row.append(InlineKeyboardButton(text=txt, callback_data="mines:noop"))
                show_rows.append(row)
            await cb.message.edit_text(
                f"💥 <b>МИНА!</b>\n\n❌ Потерял <b>{fmt_lmn(bet)} LMN</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=show_rows)
            )
            return await cb.answer("💥 Бум!")
        revealed.add(idx)
        safe  = len(revealed)
        total_safe = _MINES_SIZE * _MINES_SIZE - _MINES_COUNT
        mult  = round(1.0 + safe * (_MINES_COUNT / max(total_safe - safe + 1, 1) * 0.3), 2)
        game["mult"] = mult
        await cb.message.edit_text(
            f"💣 <b>Мины</b> — ставка {fmt_lmn(bet)} LMN\n\n"
            f"💎 Открыто: {safe} | 📈 Множитель: <b>{mult:.2f}×</b>\n"
            f"Потенциальный выигрыш: {fmt_lmn(int(bet*mult))}",
            parse_mode="HTML", reply_markup=_mines_kb(uid, revealed)
        )
        await cb.answer(f"💎 ×{mult:.2f}")

@dp.message(Command("ставка", "bet"))
async def cmd_bet_game(msg: Message, command: CommandObject = None):
    if not await _priv_check(msg): return
    usage = "Использование: <b>ставка [сумма] [число 0-36]</b>"
    if not command or not command.args: return await msg.reply(usage, parse_mode="HTML")
    parts = command.args.split()
    if len(parts) < 2: return await msg.reply(usage, parse_mode="HTML")
    try:
        bet = int(parts[0]); number = int(parts[1])
    except ValueError:
        return await msg.reply("❌ Укажи целые числа")
    uid = msg.from_user.id
    if not 0 <= number <= 36: return await msg.reply("❌ Число от 0 до 36")
    if bet <= 0 or get_balance(uid) < bet: return await msg.reply("❌ Недостаточно LMN")
    result = random.randint(0, 36)
    add_balance(uid, -bet)
    if result == number:
        wins = bet * 36; add_balance(uid, wins); _game_result(uid, True); award_xp(uid, 50)
        res  = f"✅ <b>ДЖЕКПОТ! +{fmt_lmn(wins)} LMN</b>"
    else:
        _game_result(uid, False); res = f"❌ <b>Проигрыш! -{fmt_lmn(bet)} LMN</b>"
    schedule_state_save("ставка")
    await msg.reply(
        f"🎡 <b>Ставка</b> — {fmt_lmn(bet)} LMN на {number}\n\n"
        f"🎲 Выпало: <b>{result}</b>\n\n{res}",
        parse_mode="HTML"
    )

# ═══════════════════════════════════════════════════════
# V6 — АДМИНИСТРИРОВАНИЕ
# ═══════════════════════════════════════════════════════
async def cmd_mod_logs(msg: Message):
    if msg.chat.type not in ("group", "supergroup"):
        return await msg.reply("Команда работает в групповых чатах")
    if not (is_owner(msg) or has_role(msg.from_user.id, "lead_admin", "co_admin", "admin", "moderator")):
        return await msg.reply("⛔ Только для администраторов")
    cid  = msg.chat.id
    logs = mod_logs.get(cid, [])[-20:]
    if not logs:
        return await msg.reply("📋 Журнал модерации пуст")
    act_ru = {"ban":"🚫 Бан","mute":"🔇 Мут","warn":"⚠️ Варн","kick":"👢 Кик","unban":"✅ Разбан","unmute":"🔊 Размут"}
    lines  = [f"{brand.hdr()}\n\n📋 <b>Журнал модерации</b>\n\n{brand.div()}"]
    for e in reversed(logs):
        a   = act_ru.get(e.get("action",""), e.get("action","?"))
        un  = html.escape(chat_members.get(cid, {}).get(e.get("uid",0)) or f"ID {e.get('uid',0)}")
        bn  = html.escape(chat_members.get(cid, {}).get(e.get("by",0)) or f"ID {e.get('by',0)}")
        lines.append(f"[{e.get('ts','')}] {a}: <b>{un}</b> ← {bn}")
    lines.append(f"\n{brand.div()}")
    await msg.reply("\n".join(lines), parse_mode="HTML")

@dp.message(Command("жалоба", "report"))
async def cmd_report(msg: Message, command: CommandObject = None):
    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        return await msg.reply("Ответь на сообщение: <b>жалоба [причина]</b>", parse_mode="HTML")
    target = msg.reply_to_message.from_user
    # Нельзя жаловаться на себя или бота
    if target.id == msg.from_user.id:
        return await msg.reply("❌ Нельзя пожаловаться на самого себя")
    if target.is_bot:
        return await msg.reply("❌ Нельзя жаловаться на бота")
    if target.id == OWNER_ID:
        return await msg.reply("❌ Нельзя жаловаться на фаундера")
    # Дедупликация: один пользователь → одна жалоба на одну цель в день
    rc_key = (msg.chat.id, msg.from_user.id, target.id)
    today_iso = today_kyiv().isoformat()
    if report_cooldown.get(rc_key) == today_iso:
        return await msg.reply("⚠️ Ты уже жаловался на этого пользователя сегодня")
    report_cooldown[rc_key] = today_iso
    reason = (command.args or "Не указана").strip() if command else "Не указана"
    cid    = msg.chat.id
    reports_db.setdefault(cid, []).append({
        "report_id":   uuid.uuid4().hex,  # полный UUID — нет коллизий
        "from_uid":    msg.from_user.id,
        "target_uid":  target.id,
        "from_name":   msg.from_user.full_name,
        "target_name": target.full_name,
        "reason":      reason,
        "ts":          now_kyiv().strftime("%d.%m %H:%M"),
    })
    if len(reports_db[cid]) > 50:
        reports_db[cid] = reports_db[cid][-50:]
    schedule_state_save("жалоба")
    await msg.reply(
        f"✅ Жалоба на <b>{html.escape(target.full_name)}</b> принята\n"
        f"📝 Причина: {html.escape(reason)}\n\n"
        f"<i>Администрация рассмотрит её в ближайшее время</i>",
        parse_mode="HTML"
    )

async def cmd_reports_list(msg: Message):
    if not (is_owner(msg) or has_role(msg.from_user.id, "lead_admin", "co_admin", "admin", "moderator")):
        return await msg.reply("⛔ Только для администраторов")
    cid      = msg.chat.id
    all_reps = reports_db.get(cid, [])
    # Показываем только открытые жалобы
    open_reps = [r for r in all_reps if r.get("status", "open") == "open"]
    if not open_reps:
        return await msg.reply(
            f"📋 Открытых жалоб нет\n"
            f"<i>Всего в базе: {len(all_reps)}</i>",
            parse_mode="HTML"
        )
    # Отправляем каждую открытую жалобу отдельным сообщением.
    # Кнопки используют неизменяемый report_id — позиция в списке значения не имеет.
    # У старых жалоб без report_id генерируем и сохраняем ID на месте.
    open_reps_with_id = []
    for r in all_reps:
        if r.get("status", "open") != "open":
            continue
        if not r.get("report_id"):
            r["report_id"] = uuid.uuid4().hex[:8]
        open_reps_with_id.append(r)
    total = len(open_reps_with_id)
    for r in open_reps_with_id[-5:]:
        rid = r["report_id"]
        kb  = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Закрыть",  callback_data=f"rep:close:{cid}:{rid}"),
            InlineKeyboardButton(text="🔇 Замутить", callback_data=f"rep:mute:{cid}:{rid}"),
            InlineKeyboardButton(text="🚫 Забанить", callback_data=f"rep:ban:{cid}:{rid}"),
        ]])
        text = (
            f"🔴 <b>Жалоба {rid}</b>\n"
            f"👤 От: <b>{html.escape(r.get('from_name', '?'))}</b>\n"
            f"🎯 На: <b>{html.escape(r.get('target_name', '?'))}</b>\n"
            f"📝 {html.escape(r.get('reason', '—'))}\n"
            f"🕐 {r.get('ts', '—')}"
        )
        await msg.reply(text, parse_mode="HTML", reply_markup=kb)
    if total > 5:
        await msg.reply(f"<i>… и ещё {total - 5} открытых жалоб</i>", parse_mode="HTML")

@dp.callback_query(F.data.startswith("rep:"))
async def cb_report_action(cb: CallbackQuery):
    if not (is_owner(cb) or has_role(cb.from_user.id, "lead_admin", "co_admin", "admin", "moderator")):
        return await cb.answer("⛔ Только для администраторов", show_alert=True)
    parts = cb.data.split(":")
    if len(parts) < 4:
        return await cb.answer("⛔ Некорректный callback", show_alert=True)
    action = parts[1]
    if action not in ("close", "mute", "ban"):
        return await cb.answer("⛔ Неизвестное действие", show_alert=True)
    try:
        cid = int(parts[2])
    except (ValueError, IndexError):
        return await cb.answer("⛔ Некорректный чат", show_alert=True)
    rid = parts[3]  # неизменяемый report_id

    # Верификация: чат колбэка должен совпадать с чатом в данных
    if cb.message.chat.id != cid:
        return await cb.answer("⛔ Чат не совпадает", show_alert=True)

    # Находим жалобу по stable report_id, независимо от позиции в списке
    report = next(
        (r for r in reports_db.get(cid, []) if r.get("report_id") == rid),
        None
    )
    if report is None:
        return await cb.answer("Жалоба не найдена", show_alert=True)
    if report.get("status") == "closed":
        return await cb.answer("Жалоба уже закрыта", show_alert=True)

    # target_uid всегда берётся из жалобы на сервере, а не из колбэка
    target_uid = report.get("target_uid", 0)
    if not target_uid:
        return await cb.answer("⛔ Цель жалобы не найдена", show_alert=True)
    # Нельзя применить действие к фаундеру через жалобу
    if target_uid == OWNER_ID:
        return await cb.answer("⛔ Нельзя применить действие к фаундеру", show_alert=True)

    if action == "close":
        report["status"]    = "closed"
        report["closed_by"] = cb.from_user.id
        report["closed_ts"] = now_kyiv().strftime("%d.%m %H:%M")
        _log_mod(cid, "report_closed", target_uid, cb.from_user.id)
        schedule_state_save("жалоба закрыта")
        await cb.message.edit_reply_markup(reply_markup=None)
        await cb.answer("✅ Жалоба закрыта")
    elif action == "mute":
        try:
            until = datetime.now(UTC) + timedelta(hours=1)
            await bot.restrict_chat_member(
                cid, target_uid,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until,
            )
            # Telegram действие успешно — только теперь закрываем и логируем
            report["status"]    = "closed"
            report["closed_by"] = cb.from_user.id
            report["closed_ts"] = now_kyiv().strftime("%d.%m %H:%M")
            _log_mod(cid, "mute", target_uid, cb.from_user.id)
            schedule_state_save("жалоба: мут")
            await cb.message.edit_reply_markup(reply_markup=None)
            await cb.answer("🔇 Замучен на 1 час")
        except Exception as e:
            # Жалоба остаётся открытой — можно повторить
            await cb.answer(f"❌ {e}", show_alert=True)
    elif action == "ban":
        try:
            await bot.ban_chat_member(cid, target_uid)
            # Telegram действие успешно — только теперь закрываем и логируем
            report["status"]    = "closed"
            report["closed_by"] = cb.from_user.id
            report["closed_ts"] = now_kyiv().strftime("%d.%m %H:%M")
            _log_mod(cid, "ban", target_uid, cb.from_user.id)
            schedule_state_save("жалоба: бан")
            await cb.message.edit_reply_markup(reply_markup=None)
            await cb.answer("🚫 Забанен")
        except Exception as e:
            # Жалоба остаётся открытой — можно повторить
            await cb.answer(f"❌ {e}", show_alert=True)

async def cmd_raid_toggle(msg: Message):
    if not (is_owner(msg) or has_role(msg.from_user.id, "lead_admin", "co_admin", "admin")):
        return await msg.reply("⛔ Только для администраторов")
    cid = msg.chat.id
    raid_mode[cid] = not raid_mode.get(cid, False)
    status = "🟢 ВКЛЮЧЁН" if raid_mode[cid] else "🔴 ВЫКЛЮЧЕН"
    schedule_state_save("рейд")
    await msg.reply(
        f"🛡 <b>Рейд-мод: {status}</b>\n\n"
        + ("⚡ Новые участники мутируются на 10 минут" if raid_mode[cid] else "✅ Защита от рейда выключена"),
        parse_mode="HTML"
    )

async def cmd_antispam_toggle(msg: Message):
    if not (is_owner(msg) or has_role(msg.from_user.id, "lead_admin", "co_admin", "admin")):
        return await msg.reply("⛔ Только для администраторов")
    cid = msg.chat.id
    antispam_mode[cid] = not antispam_mode.get(cid, False)
    status = "🟢 ВКЛЮЧЁН" if antispam_mode[cid] else "🔴 ВЫКЛЮЧЕН"
    schedule_state_save("антиспам")
    await msg.reply(
        f"🤖 <b>Антиспам: {status}</b>\n\n"
        + ("⚡ Повторяющиеся сообщения будут удаляться" if antispam_mode[cid] else "✅ Антиспам выключен"),
        parse_mode="HTML"
    )

async def cmd_filters_list(msg: Message):
    cid = msg.chat.id
    lg  = _link_guard.get(cid, False)
    as_ = antispam_mode.get(cid, False)
    rm  = raid_mode.get(cid, False)
    wl  = _link_whitelist.get(cid, [])
    await msg.reply(
        f"{brand.hdr()}\n\n⚙️ <b>Фильтры чата</b>\n\n{brand.div()}\n"
        f"{'🟢' if lg else '🔴'} Антилинк: {'включён' if lg else 'выключен'}\n"
        f"{'🟢' if as_ else '🔴'} Антиспам: {'включён' if as_ else 'выключен'}\n"
        f"{'🟢' if rm else '🔴'} Рейд-мод: {'включён' if rm else 'выключен'}\n"
        f"🟢 Автомод пропаганды: включён\n"
        + (f"✅ Белый список: {len(wl)} ссылок\n" if wl else "")
        + f"\n{brand.div()}",
        parse_mode="HTML"
    )

# ═══════════════════════════════════════════════════════
# V6 — СТАТИСТИКА ЧАТА
# ═══════════════════════════════════════════════════════
async def cmd_chatstats(msg: Message):
    if msg.chat.type == "private":
        return await msg.reply("📊 Команда работает в групповых чатах")
    import html as _html
    cid = msg.chat.id; can = econ_cid(cid)
    # Объединяем данные из обоих связанных чатов
    all_members = {**chat_members.get(can, {}), **chat_members.get(cid, {})}
    all_msgs: dict[int, int] = {}
    for c in (cid, can):
        for u, cnt in user_messages.get(c, {}).items():
            all_msgs[u] = all_msgs.get(u, 0) + cnt
    try:
        tg_cnt = await bot.get_chat_member_count(cid)
    except Exception:
        tg_cnt = len(all_members)
    msgs_cnt  = sum(all_msgs.values())
    top_act   = sorted(all_msgs.items(), key=lambda x: x[1], reverse=True)[:3]
    marr_cnt  = len({
        frozenset([u, p])
        for c in (cid, can)
        for u, p in marriages.get(c, {}).items()
        if marriages.get(c, {}).get(p) == u
    })
    rich = max(((lmn_balances.get(u, 0) + bank_balances.get(u, 0), u) for u in all_members), default=(0, 0))
    rich_line = ""
    if rich[0] > 0:
        rn = _html.escape(all_members.get(rich[1]) or f"ID {rich[1]}")
        rich_line = f"\n💰 Богатейший: <b>{rn}</b> · {fmt_lmn(rich[0])}"
    top_lines = []
    for uid_t, cnt in top_act:
        nm = _html.escape(all_members.get(uid_t) or f"ID {uid_t}")
        top_lines.append(f"  👤 <b>{nm}</b> — {cnt:,} сообщ.")
    lines = [
        f"{brand.hdr()}\n\n📊 <b>Статистика · {_html.escape(msg.chat.title or 'чат')}</b>\n\n{brand.div()}",
        f"👥 Участников: <b>{tg_cnt:,}</b>",
        f"💬 Сообщений: <b>{msgs_cnt:,}</b>",
        f"✨ XP в чате: <b>{sum(user_xp.get(u, 0) for u in all_members):,}</b>",
        f"💍 Браков: <b>{marr_cnt}</b>",
    ]
    if top_lines:
        lines.append("\n🏆 Топ активных:")
        lines.extend(top_lines)
    if rich_line:
        lines.append(rich_line)
    lines.append(f"\n{brand.div()}")
    await msg.reply("\n".join(lines), parse_mode="HTML")

async def cmd_online(msg: Message):
    if msg.chat.type == "private":
        return await msg.reply("Команда работает в групповых чатах")
    cid = msg.chat.id; can = econ_cid(cid)
    # Объединяем сообщения и участников из обоих чатов
    all_members = {**chat_members.get(can, {}), **chat_members.get(cid, {})}
    all_msgs: dict[int, int] = {}
    for c in (cid, can):
        for u, cnt in user_messages.get(c, {}).items():
            all_msgs[u] = all_msgs.get(u, 0) + cnt
    if not all_msgs:
        return await msg.reply("📊 Нет данных об активности")
    top   = sorted(all_msgs.items(), key=lambda x: x[1], reverse=True)[:15]
    total = sum(all_msgs.values())
    lines = [f"{brand.hdr()}\n\n📊 <b>Топ активных участников</b>\n\n{brand.div()}"]
    medals = ["🥇", "🥈", "🥉"] + ["👤"] * 12
    for i, (uid_t, cnt) in enumerate(top):
        nm  = html.escape(all_members.get(uid_t) or f"ID {uid_t}")
        pct = cnt / total * 100 if total else 0
        bar = "█" * min(int(pct / 5), 10)
        lines.append(f"{medals[i]} <b>{nm}</b> — {cnt:,} ({pct:.0f}%) {bar}")
    lines.append(f"\n{brand.div()}\n💬 Всего сообщений: <b>{total:,}</b>")
    await msg.reply("\n".join(lines), parse_mode="HTML")

async def cmd_analytics(msg: Message):
    if msg.chat.type != "private":
        cid   = msg.chat.id; can = econ_cid(cid)
        title = f"Аналитика · {html.escape(msg.chat.title or 'чат')}"
        all_members = set(chat_members.get(cid, {}).keys()) | set(chat_members.get(can, {}).keys())
        # Только данные чата
        chat_msgs   = sum(user_messages.get(c, {}).get(u, 0) for c in (cid, can) for u in all_members)
        chat_xp     = sum(user_xp.get(u, 0) for u in all_members)
        chat_ach    = sum(len(user_achievements.get(u, [])) for u in all_members)
        chat_lmn    = sum(lmn_balances.get(u, 0) + bank_balances.get(u, 0) for u in all_members)
        await msg.reply(
            f"{brand.hdr()}\n\n📊 <b>{title}</b>\n\n{brand.div()}\n"
            f"👥 Участников в базе: <b>{len(all_members):,}</b>\n"
            f"💬 Сообщений: <b>{chat_msgs:,}</b>\n"
            f"✨ XP участников: <b>{chat_xp:,}</b>\n"
            f"🏆 Достижений: <b>{chat_ach}</b>\n"
            f"💰 LMN участников: <b>{fmt_lmn(chat_lmn)}</b>\n\n"
            f"{brand.div()}",
            parse_mode="HTML"
        )
    else:
        total_msgs = sum(sum(m.values()) for m in user_messages.values())
        total_xp   = sum(user_xp.values())
        total_ach  = sum(len(v) for v in user_achievements.values())
        total_lmn  = sum(lmn_balances.values()) + sum(bank_balances.values())
        total_u    = len({u for m in chat_members.values() for u in m})
        await msg.reply(
            f"{brand.hdr()}\n\n📊 <b>Глобальная аналитика</b>\n\n{brand.div()}\n"
            f"👥 Всего пользователей: <b>{total_u:,}</b>\n"
            f"💬 Всего сообщений: <b>{total_msgs:,}</b>\n"
            f"✨ XP в системе: <b>{total_xp:,}</b>\n"
            f"🏆 Достижений выдано: <b>{total_ach}</b>\n"
            f"💰 LMN в обороте: <b>{fmt_lmn(total_lmn)}</b>\n\n"
            f"{brand.div()}",
            parse_mode="HTML"
        )

async def cmd_growth(msg: Message):
    total_u    = len({uid for m in chat_members.values() for uid in m})
    total_msgs = sum(sum(m.values()) for m in user_messages.values())
    total_xp   = sum(user_xp.values())
    total_games = sum(_games_played.values())
    total_refs  = sum(referral_counts.values())
    total_lmn   = sum(lmn_balances.values()) + sum(bank_balances.values())
    await msg.reply(
        f"{brand.hdr()}\n\n📈 <b>Обзор системы</b>\n\n{brand.div()}\n"
        f"👥 Пользователей: <b>{total_u:,}</b>\n"
        f"💬 Чатов: <b>{len(chat_members)}</b>\n"
        f"📨 Сообщений: <b>{total_msgs:,}</b>\n"
        f"✨ XP в системе: <b>{total_xp:,}</b>\n"
        f"🎮 Игр сыграно: <b>{total_games:,}</b>\n"
        f"🔗 Рефералов: <b>{total_refs:,}</b>\n"
        f"💰 LMN в обороте: <b>{fmt_lmn(total_lmn)}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML"
    )

# ═══════════════════════════════════════════════════════
# V6 — ПАНЕЛЬ ФАУНДЕРА
# ═══════════════════════════════════════════════════════
_OWNER_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👥 Пользователи", callback_data="owner:users"),
     InlineKeyboardButton(text="💰 Экономика",    callback_data="owner:eco")],
    [InlineKeyboardButton(text="📢 Рассылка",     callback_data="owner:broadcast"),
     InlineKeyboardButton(text="📊 Статистика",   callback_data="owner:stats")],
    [InlineKeyboardButton(text="🛠 Редактор",     callback_data="editor:menu")],
])

async def cmd_owner_panel(msg: Message):
    if not is_owner(msg): return await msg.reply("⛔ Только для фаундера")
    total_u   = len({uid for m in chat_members.values() for uid in m})
    total_lmn = sum(lmn_balances.values()) + sum(bank_balances.values())
    total_xp_ = sum(user_xp.values())
    await msg.reply(
        f"{brand.hdr()}\n\n👑 <b>Панель фаундера</b>\n\n{brand.div()}\n"
        f"👥 Пользователей: <b>{total_u}</b>\n"
        f"💰 LMN в системе: <b>{fmt_lmn(total_lmn)}</b>\n"
        f"✨ XP: <b>{total_xp_:,}</b>\n"
        f"💬 Чатов: <b>{len(chat_members)}</b>\n\n{brand.div()}",
        parse_mode="HTML", reply_markup=_OWNER_KB
    )

@dp.callback_query(F.data.startswith("owner:"))
async def cb_owner(cb: CallbackQuery):
    if not is_owner(cb): return await cb.answer("⛔ Только фаундер", show_alert=True)
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="owner:back")]])
    sec = cb.data.split(":", 1)[1]
    if sec == "users":
        total = len({uid for m in chat_members.values() for uid in m})
        vips  = len([uid for uid, r in ROLES.items() if r == "vip"])
        await cb.message.edit_text(
            f"👥 <b>Пользователи</b>\n\nВсего: <b>{total}</b>\nVIP: <b>{vips}</b>\n"
            f"Верифицированных: <b>{len(_verified_users)}</b>\n\n"
            f"Команды: /юзеринфо · /сетвип · /снятьвип",
            parse_mode="HTML", reply_markup=back_kb
        )
    elif sec == "eco":
        total_lmn = sum(lmn_balances.values()) + sum(bank_balances.values())
        await cb.message.edit_text(
            f"💰 <b>Экономика</b>\n\nКошельки: <b>{fmt_lmn(sum(lmn_balances.values()))}</b>\n"
            f"Банки: <b>{fmt_lmn(sum(bank_balances.values()))}</b>\n"
            f"Итого: <b>{fmt_lmn(total_lmn)}</b>\n\nКоманды: /дать · /забрать",
            parse_mode="HTML", reply_markup=back_kb
        )
    elif sec == "broadcast":
        await cb.message.edit_text(
            "📢 <b>Рассылка</b>\n\nИспользуй: <code>/рассылка [текст]</code>\n"
            "Будет отправлено во все активные чаты.",
            parse_mode="HTML", reply_markup=back_kb
        )
    elif sec == "stats":
        total_msgs = sum(sum(m.values()) for m in user_messages.values())
        await cb.message.edit_text(
            f"📊 <b>Статистика</b>\n\nСообщений (сессия): <b>{total_msgs:,}</b>\n"
            f"XP: <b>{sum(user_xp.values()):,}</b>\n"
            f"Достижений: <b>{sum(len(v) for v in user_achievements.values())}</b>\n"
            f"Рефералов: <b>{len(referrals)}</b>",
            parse_mode="HTML", reply_markup=back_kb
        )
    elif sec == "back":
        total_u = len({uid for m in chat_members.values() for uid in m})
        total_lmn = sum(lmn_balances.values()) + sum(bank_balances.values())
        await cb.message.edit_text(
            f"{brand.hdr()}\n\n👑 <b>Панель фаундера</b>\n\n{brand.div()}\n"
            f"👥 Пользователей: <b>{total_u}</b>\n"
            f"💰 LMN: <b>{fmt_lmn(total_lmn)}</b>\n\n{brand.div()}",
            parse_mode="HTML", reply_markup=_OWNER_KB
        )
    await cb.answer()

@dp.message(Command("рассылка", "broadcast"))
async def cmd_broadcast(msg: Message, command: CommandObject = None):
    if not is_owner(msg): return await msg.reply("⛔ Только для фаундера")
    text = (command.args or "").strip() if command else ""
    if not text: return await msg.reply("Использование: <b>рассылка [текст]</b>", parse_mode="HTML")
    active  = [c for c in chat_members if c < 0]
    sent_ok = 0
    for cid in active:
        try:
            await bot.send_message(
                cid,
                f"{brand.hdr()}\n\n📢 <b>Объявление</b>\n\n{brand.div()}\n{html.escape(text)}\n\n{brand.div()}",
                parse_mode="HTML"
            )
            sent_ok += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await msg.reply(f"✅ Рассылка отправлена в <b>{sent_ok}</b> чатов", parse_mode="HTML")

@dp.message(Command("юзеринфо", "userinfo"))
async def cmd_userinfo(msg: Message):
    if not is_owner(msg): return await msg.reply("⛔ Только для фаундера")
    target = msg.reply_to_message.from_user if msg.reply_to_message else msg.from_user
    uid    = target.id
    xp     = user_xp.get(uid, 0); lvl = get_xp_level(xp)[0]
    bal    = get_balance(uid); bank = bank_balances.get(uid, 0)
    role   = get_role_display(uid) or "—"
    warns  = max((warnings_db.get(c, {}).get(uid, 0) for c in warnings_db), default=0)
    stk    = max((streaks.get(c, {}).get(uid, {}).get("count", 0) for c in streaks), default=0)
    ach    = len(user_achievements.get(uid, []))
    msgs_  = sum(m.get(uid, 0) for m in user_messages.values())
    refs   = referral_counts.get(uid, 0)
    await msg.reply(
        f"{brand.hdr()}\n\n🔍 <b>Инфо: {html.escape(target.full_name)}</b>\n\n{brand.div()}\n"
        f"🆔 ID: <code>{uid}</code>\n@{target.username or '—'}\n\n"
        f"💰 Кошелёк: <b>{fmt_lmn(bal)}</b>\n🏦 Банк: <b>{fmt_lmn(bank)}</b>\n"
        f"✨ XP: <b>{xp:,}</b> ({lvl})\n🔥 Стрик: <b>{stk} дн.</b>\n"
        f"⚠️ Варны: <b>{warns}</b>\n🏅 Роль: <b>{role}</b>\n"
        f"🏆 Достижений: <b>{ach}/{len(ACHIEVEMENT_INFO)}</b>\n"
        f"💬 Сообщений: <b>{msgs_:,}</b>\n🔗 Рефералов: <b>{refs}</b>\n\n{brand.div()}",
        parse_mode="HTML"
    )

@dp.message(Command("забрать", "take"))
async def cmd_take(msg: Message, command: CommandObject = None):
    if not is_owner(msg): return await msg.reply("⛔ Только для фаундера")
    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        return await msg.reply("Ответь на сообщение и укажи сумму")
    if not command or not command.args:
        return await msg.reply("Использование: <b>забрать [сумма]</b> (ответом)", parse_mode="HTML")
    try:
        amount = int(command.args.split()[0])
    except ValueError:
        return await msg.reply("❌ Укажи целое число")
    target = msg.reply_to_message.from_user
    actual = min(amount, get_balance(target.id))
    add_balance(target.id, -actual)
    schedule_state_save("забрать")
    await msg.reply(
        f"✅ Забрал <b>{fmt_lmn(actual)} LMN</b> у {html.escape(target.full_name)}\n"
        f"Новый баланс: <b>{fmt_lmn(get_balance(target.id))} LMN</b>",
        parse_mode="HTML"
    )

@dp.message(Command("сетвип", "setvip"))
async def cmd_setvip_v6(msg: Message):
    if not is_owner(msg): return await msg.reply("⛔ Только для фаундера")
    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        return await msg.reply("Ответь на сообщение пользователя")
    target = msg.reply_to_message.from_user
    set_role(target.id, "vip", target.username or "")
    schedule_state_save("setvip")
    await msg.reply(f"⭐ <b>{html.escape(target.full_name)}</b> теперь VIP!", parse_mode="HTML")

@dp.message(Command("снятьвип", "removevip"))
async def cmd_removevip_v6(msg: Message):
    if not is_owner(msg): return await msg.reply("⛔ Только для фаундера")
    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        return await msg.reply("Ответь на сообщение пользователя")
    target = msg.reply_to_message.from_user
    remove_role(target.id, target.username or "")
    schedule_state_save("removevip")
    await msg.reply(f"✅ VIP снят с <b>{html.escape(target.full_name)}</b>", parse_mode="HTML")

@dp.message(Command("сетлевел", "setlevel"))
async def cmd_setlevel(msg: Message, command: CommandObject = None):
    if not is_owner(msg): return await msg.reply("⛔ Только для фаундера")
    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        return await msg.reply("Ответь на сообщение пользователя")
    if not command or not command.args:
        return await msg.reply("Использование: <b>сетлевел [xp]</b> (ответом)", parse_mode="HTML")
    try:
        xp_val = int(command.args.split()[0])
    except ValueError:
        return await msg.reply("❌ Укажи целое число XP")
    target = msg.reply_to_message.from_user
    user_xp[target.id] = max(0, xp_val)
    _check_achievements(target.id)
    schedule_state_save("setlevel")
    lvl = get_xp_level(xp_val)[0]
    await msg.reply(
        f"✅ XP: <b>{xp_val:,}</b> ({lvl}) → {html.escape(target.full_name)}",
        parse_mode="HTML"
    )

@dp.message(Command("разбанвсех", "unbanall"))
async def cmd_unbanall(msg: Message):
    if not is_owner(msg): return await msg.reply("⛔ Только для фаундера")
    if msg.chat.type not in ("group", "supergroup"):
        return await msg.reply("Команда работает в групповых чатах")
    cid   = msg.chat.id
    count = 0
    for uid in list(warnings_db.get(cid, {}).keys()):
        try:
            await bot.unban_chat_member(cid, uid, only_if_banned=True)
            count += 1
        except Exception:
            pass
    schedule_state_save("разбанвсех")
    await msg.reply(f"✅ Попытка разбана для <b>{count}</b> пользователей", parse_mode="HTML")

# ═══════════════════════════════════════════════════════
# V6 — РЕФЕРАЛЫ
# ═══════════════════════════════════════════════════════
async def cmd_invite(msg: Message):
    uid   = msg.from_user.id
    link  = f"https://t.me/LumenarAi_Bot?start=ref_{uid}"
    count = referral_counts.get(uid, 0)
    await msg.reply(
        f"{brand.hdr()}\n\n🔗 <b>Реферальная ссылка</b>\n\n{brand.div()}\n"
        f"<code>{link}</code>\n\n"
        f"👥 Приглашено: <b>{count}</b>\n"
        f"🎁 Бонус за каждого: +1000 LMN + 100 XP\n\n{brand.div()}",
        parse_mode="HTML"
    )

async def cmd_referrals_list(msg: Message):
    uid   = msg.from_user.id
    name  = html.escape(msg.from_user.first_name or "—")
    count = referral_counts.get(uid, 0)
    my_refs = [u for u, ref in referrals.items() if ref == uid]
    lines = [
        f"{brand.hdr()}\n\n🔗 <b>Мои рефералы · {name}</b>\n\n{brand.div()}\n"
        f"👥 Всего приглашено: <b>{count}</b>\n"
    ]
    if my_refs:
        lines.append("\n<b>Список:</b>")
        for ru in my_refs[:20]:
            rn = html.escape(next((m.get(ru) for m in chat_members.values() if ru in m), f"ID {ru}"))
            lines.append(f"  👤 {rn}")
    lines.append(f"\n{brand.div()}")
    await msg.reply("\n".join(lines), parse_mode="HTML")

async def cmd_invites_stats(msg: Message):
    uid   = msg.from_user.id
    name  = html.escape(msg.from_user.first_name or "—")
    count = referral_counts.get(uid, 0)
    await msg.reply(
        f"{brand.hdr()}\n\n📊 <b>Статистика инвайтов · {name}</b>\n\n{brand.div()}\n"
        f"🔗 Приглашено: <b>{count}</b>\n"
        f"💰 Заработано: <b>{fmt_lmn(count * 1000)} LMN</b>\n"
        f"✨ XP за рефералов: <b>{count * 100}</b>\n\n{brand.div()}",
        parse_mode="HTML"
    )

# ── Объявление V7 (фаундер) ────────────────────────────
@dp.message(Command("announce_v7", "объявить_в7"))
async def cmd_announce_v7(msg: Message):
    """Отправляет анонс обновления v7 в паб-чат (только фаундер)."""
    if not is_owner(msg):
        return await msg.reply("⛔ Только фаундер")
    pub_chat = _ank.get_pub_chat()
    if not pub_chat:
        return await msg.reply("❌ pub_chat_id не установлен. Сначала /setpubchat")
    text = (
        "🌟 <b>LUMENA v7 — ПОЛНОЕ ОБНОВЛЕНИЕ!</b> 🌟\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 <b>Задания дня</b>\n"
        "• Выполни все 4 задания → <b>+1 000 LMN + 75 XP</b>!\n"
        "• Прогресс-бар и автоначисление: <code>задания</code>\n\n"
        "🔮 <b>Расширенные предсказания</b>\n"
        "• 98 предсказаний судьбы — <code>предсказание</code>\n"
        "• 25 уникальных ответов вселенной — <code>предсказать</code>\n"
        "• 35 ответов магического шара — <code>8ball</code>\n"
        "• 30 суперсил с описанием — <code>суперсила</code>\n"
        "• 40 профессий с описанием — <code>профессия</code>\n"
        "• 30 животных с описанием — <code>животное</code>\n"
        "• 6 гороскопов на каждый знак — <code>гороскоп</code>\n"
        "• Нумерология с архетипом — <code>нумерология</code>\n\n"
        "💰 <b>Улучшенная экономика</b>\n"
        "• Дейли показывает стрик и подсказки: <code>дейли</code>\n"
        "• Прогресс-бар стрика: <code>бонус</code>\n"
        "• Топ богатейших теперь учитывает банк: <code>богатейшие</code>\n"
        "• Все источники наград: <code>награды</code>\n\n"
        "💍 <b>Браки</b>\n"
        "• Сколько дней вместе теперь видно в <code>браки</code> и профиле!\n\n"
        "🐛 <b>Исправленные баги</b>\n"
        "• Краш: ставка берётся из игры, не из кнопки\n"
        "• Краш: нельзя забрать выигрыш после краша\n"
        "• Мины: повторный клик по открытой клетке заблокирован\n"
        "• Мины: защита от подделанных индексов клеток\n"
        "• Лимбо: защита от NaN/Infinity в цели\n"
        "• Стрик/топ стриков/профиль/репутация: правильно читают данные чата\n"
        "• Перевод LMN: теперь сохраняется сразу после операции\n"
        "• Бонус за стрик: данные сохраняются сразу\n"
        "• Кулдауны работы/рыбалки/ограбления не сбрасываются при рестарте\n"
        "• Мут/бан/кик/варн: нельзя применить к фаундеру или себе\n"
        "• Варн: при неудачном бане откатывает счётчик\n"
        "• Снятие варна теперь пишется в лог модерации\n"
        "• Безопасность фаундера: проверка только по ID, не по username\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "— <b>Команда Lumena</b> 💙\n"
        "#lumena #update #v7"
    )
    try:
        await bot.send_message(pub_chat, text, parse_mode="HTML")
        await msg.reply("✅ Анонс v7 отправлен в паб-чат!")
    except Exception as e:
        await msg.reply(f"❌ Ошибка: {e}")

# ── Объявление V6 (фаундер) ────────────────────────────
@dp.message(Command("объявить_в6", "announce_v6"))
async def cmd_announce_v6(msg: Message):
    if not is_owner(msg): return await msg.reply("⛔ Только фаундер")
    await _send_v6_announcement()
    await msg.reply("✅ V6-объявление отправлено!")

async def _send_v6_announcement():
    global v6_announced
    pub_chat = _ank.get_pub_chat()
    if not pub_chat:
        return
    v6_text = (
        f"{brand.hdr()}\n\n"
        f"🚀 <b>ОБНОВЛЕНИЕ V6</b>\n\n"
        f"{brand.div()}\n"
        f"📋 Что нового:\n"
        f"• ⚡ XP и система уровней (6 уровней)\n"
        f"• 🎮 Новые игры: орёл, плинко, лимбо, краш, блэкджек, мины\n"
        f"• 🎁 Ежедневные награды и задания\n"
        f"• 🏆 Система достижений\n"
        f"• 🔗 Реферальная система\n"
        f"• 🛡 Панель администратора (логи, жалобы, рейд, антиспам)\n"
        f"• 👑 Расширенная панель фаундера\n"
        f"• 📊 Детальная статистика чата\n"
        f"• ✨ Новое оформление анкет\n"
        f"• 📖 Кнопка правил при приветствии\n\n"
        f"{brand.div()}\n"
        f"🤖 v{BOT_VERSION}"
    )
    try:
        await bot.send_message(pub_chat, v6_text, parse_mode="HTML")
        v6_announced = True
        save_data()
    except Exception as e:
        logging.warning("V6 announcement failed: %s", e)

# ═══════════════════════════════════════════════════════
# ПОМОЩЬ
# ═══════════════════════════════════════════════════════
_HELP_MAIN_KB = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="💰 Экономика",      callback_data="help:eco"),
        InlineKeyboardButton(text="🎮 Игры",           callback_data="help:games"),
    ],
    [
        InlineKeyboardButton(text="💑 Отношения",      callback_data="help:social"),
        InlineKeyboardButton(text="🎉 Развлечения",    callback_data="help:fun"),
    ],
    [
        InlineKeyboardButton(text="🔮 Предсказания",   callback_data="help:fortune"),
        InlineKeyboardButton(text="👤 Профиль",        callback_data="help:profile"),
    ],
    [
        InlineKeyboardButton(text="⚡ XP / Уровни",   callback_data="help:xp"),
        InlineKeyboardButton(text="🏆 Достижения",     callback_data="help:ach"),
    ],
    [
        InlineKeyboardButton(text="📊 Статистика",     callback_data="help:stats"),
        InlineKeyboardButton(text="🔗 Рефералы",       callback_data="help:ref"),
    ],
    [
        InlineKeyboardButton(text="✦ 💬 Наш чат ✦",  url="https://t.me/+_K2SJRYIhq9hYjFi"),
        InlineKeyboardButton(text="✦ 📢 Канал ✦",    url="https://t.me/lmnfff"),
    ],
])

async def cmd_help(msg: Message):
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"✦ · · · Справочный центр · · · ✦\n\n"
        f"Выбери раздел — расскажу всё\n"
        f"о командах и возможностях 👇\n\n"
        f"<i>Команды работают без / —\n"
        f"просто напиши нужное слово в чат</i>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
        reply_markup=_HELP_MAIN_KB,
    )


_HELP_BACK_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="help:menu")],
    [
        InlineKeyboardButton(text="💬 Чат проекта", url="https://t.me/+_K2SJRYIhq9hYjFi"),
        InlineKeyboardButton(text="📢 Канал", url="https://t.me/lmnfff"),
    ],
])

_HELP_SECTIONS = {
    "mod": (
        f"{brand.hdr()}\n\n"
        "🔨 Модерация чата\n\n"
        f"{brand.div()}\n"
        "🚫 <b>Ограничения:</b>\n"
        "<code>!мут [время] [причина]</code> — заглушить (5м, 1ч, 7д)\n"
        "<code>!бан [причина]</code> / <code>!разбан</code>\n"
        "<code>!кик [причина]</code> — выгнать из чата\n"
        "<code>!варн [причина]</code> — предупреждение (3 → бан)\n"
        "<code>!снятьварн</code> — убрать варн\n"
        "<code>!очистить [N]</code> — удалить N сообщений\n\n"
        "⚙️ <b>Управление:</b>\n"
        "<code>/ро on/off</code> — режим только для чтения\n"
        "<code>/закрепить</code> / <code>/открепить</code>\n"
        "<code>/название [текст]</code> — звание участнику\n\n"
        f"{brand.div()}\n"
        "<i>Команды с ! работают у администраторов</i>"
    ),
    "eco": (
        f"{brand.hdr()}\n\n"
        "💰 Экономика — валюта LMN\n\n"
        f"{brand.div()}\n"
        "📊 <b>Доход:</b>\n"
        "<code>баланс</code> — кошелёк\n"
        "<code>работа</code> — заработать (кд 1 ч)\n"
        "<code>рыбалка</code> — рыбачить за LMN (кд 30 мин)\n\n"
        "<code>алхимия</code> — сварить личный эликсир (кд 2 ч)\n"
        "<code>команда алхимия</code> — общий ритуал для 3 участников (раз в день)\n\n"
        "🎰 <b>Удача:</b>\n"
        "<code>казино [сумма]</code> — казино (только в личном чате с ботом)\n"
        "<code>слоты [сумма]</code> — игровой автомат (только в личном чате с ботом)\n\n"
        "💸 <b>Переводы:</b>\n"
        "<code>ограбить</code> — ограбить (ответом)\n"
        "<code>дать [сумма]</code> — перевод LMN\n"
        "<code>топ богачей</code> — рейтинг\n\n"
        f"{brand.div()}"
    ),
    "social": (
        f"{brand.hdr()}\n\n"
        "💑 Отношения\n\n"
        f"{brand.div()}\n"
        "💍 <b>Браки:</b>\n"
        "<code>брак</code> — предложение (ответом)\n"
        "<code>развод</code> — расстаться\n"
        "<code>список браков</code> — все пары\n\n"
        "💘 <b>Совместимость:</b>\n"
        "<code>корабль</code> · <code>любовь</code> · <code>дружба</code> · <code>пара</code>\n\n"
        "🤝 <b>Действия (ответом):</b>\n"
        "<code>обнять</code> · <code>поцеловать</code> · <code>укусить</code>\n"
        "<code>погладить</code> · <code>ударить</code> · <code>подарить</code>\n"
        "<code>потыкать</code> · <code>помахать</code> · <code>станцевать</code>\n"
        "<code>фейспалм</code> · <code>серенада</code> · <code>пятёрку</code>\n\n"
        f"{brand.div()}"
    ),
    "games": (
        f"{brand.hdr()}\n\n"
        "🎮 Игры\n\n"
        f"{brand.div()}\n"
        "🎲 <b>Случайность:</b>\n"
        "<code>монетка</code> · <code>кубик</code> · <code>ролл</code>\n"
        "<code>рандом [от] [до]</code>\n\n"
        "🕹 <b>Мини-игры:</b>\n"
        "<code>выбрать [а/б/в]</code> — выбор\n"
        "<code>оценить</code> · <code>загадка</code> · <code>виселица</code>\n\n"
        "⚡ <b>Риск:</b>\n"
        "<code>рулетка</code> · <code>правда</code> · <code>действие</code>\n\n"
        f"{brand.div()}"
    ),
    "fortune": (
        f"{brand.hdr()}\n\n"
        "🔮 Предсказания и магия\n\n"
        f"{brand.div()}\n"
        "🌟 <b>Предсказания:</b>\n"
        "<code>предсказание</code> · <code>судьба</code>\n"
        "<code>8ball [вопрос]</code> — шар ответов\n\n"
        "🌙 <b>Астрология:</b>\n"
        "<code>гороскоп [знак]</code> · <code>таро</code>\n"
        "<code>нумерология [имя]</code>\n\n"
        "✨ <b>Личность:</b>\n"
        "<code>суперсила</code> · <code>профессия</code>\n"
        "<code>животное</code> · <code>страна</code> · <code>цвет</code>\n\n"
        f"{brand.div()}"
    ),
    "fun": (
        f"{brand.hdr()}\n\n"
        "🎉 Развлечения\n\n"
        f"{brand.div()}\n"
        "😄 <b>Контент:</b>\n"
        "<code>шутка</code> · <code>факт</code> · <code>цитата</code>\n"
        "<code>котик</code> · <code>пёс</code>\n"
        "<code>комплимент</code> · <code>роаст</code>\n"
        "<code>фильм</code> · <code>книга</code> · <code>совет</code>\n"
        "<code>мотивация</code> · <code>миф</code> · <code>эмодзи</code>\n\n"
        "⭐ <b>Репутация:</b>\n"
        "<code>+1</code> / <code>-1</code> — ответом\n"
        "<code>репутация</code> · <code>топ репутации</code>\n\n"
        "🔥 <b>Стрики:</b>\n"
        "<code>чекин</code> · <code>стрик</code> · <code>топ стриков</code>\n\n"
        f"{brand.div()}"
    ),
    "profile": (
        f"{brand.hdr()}\n\n"
        "👤 Профиль и статистика\n\n"
        f"{brand.div()}\n"
        "📋 <b>Профиль:</b>\n"
        "<code>профиль</code> — карточка участника\n"
        "<code>досье</code> — полное досье (ответом)\n"
        "<code>айди</code> — Telegram ID\n"
        "<code>инфочат</code> — информация о чате\n"
        "<code>статистика</code> · <code>пинг</code> · <code>версия</code>\n\n"
        "✏️ <b>Настройки:</b>\n"
        "<code>сетбио [текст]</code> — описание профиля\n"
        "<code>сетзвание [текст]</code> — своё звание\n\n"
        "💌 <b>Анкеты знакомств:</b>\n"
        "<code>/анкета</code> — заполнить в личке с ботом\n\n"
        "📩 <b>Поддержка:</b>\n"
        "<code>помощь</code> — обращение администрации\n\n"
        f"{brand.div()}"
    ),
    "ai": (
        f"{brand.hdr()}\n\n"
        "🤖 ИИ Лумена\n\n"
        f"{brand.div()}\n"
        "💬 <b>Как обратиться в группе:</b>\n"
        "• <code>Лумена, вопрос</code>\n"
        "• <code>лумка</code> / <code>лум</code> — коротко\n"
        "• Ответь на любое моё сообщение\n\n"
        "📩 <b>В личных сообщениях:</b>\n"
        "Просто напиши — отвечаю на всё!\n\n"
        "🧠 <b>Умею:</b>\n"
        "💡 Любые вопросы и задачи\n"
        "😈 Острый юмор по запросу\n"
        "✍️ Тексты, стихи, посты\n"
        "🔢 Математика, анализ, код\n"
        "🤝 Помню весь разговор сессии\n\n"
        "⚡ ИИ: <b>Groq Llama 3.3 70B</b> + резерв Gemini\n\n"
        f"{brand.div()}"
    ),
    # ── V6 секции ─────────────────────────────────────
    "xp": (
        f"{brand.hdr()}\n\n"
        "⚡ XP и уровни — V6\n\n"
        f"{brand.div()}\n"
        "📊 <b>Статус:</b>\n"
        "<code>уровень</code> — твой XP и прогресс\n"
        "<code>ранг</code> — место в чате по XP\n"
        "<code>топ</code> — топ-10 по XP\n"
        "<code>активность</code> — сводка по тебе\n"
        "<code>сообщения</code> — счётчик сообщений\n\n"
        "🏅 <b>Уровни:</b>\n"
        "🆕 Новичок (0) → 📗 Участник (100)\n"
        "⚡ Активный (500) → 🔥 Опытный (1500)\n"
        "💎 Ветеран (3500) → 👑 Легенда (7000)\n\n"
        "💡 XP начисляется за каждое сообщение (+1-5)\n\n"
        f"{brand.div()}"
    ),
    "ach": (
        f"{brand.hdr()}\n\n"
        "🏆 Достижения — V6\n\n"
        f"{brand.div()}\n"
        "📋 <b>Просмотр:</b>\n"
        "<code>достижения</code> — все твои достижения\n"
        "<code>лидерборд</code> — глобальный топ XP\n\n"
        "🎁 <b>Ежедневное:</b>\n"
        "<code>дейли</code> — 500-2000 LMN + 50 XP (раз в день)\n"
        "<code>бонус</code> — 5000 LMN за стрик 7 дней\n"
        "<code>задания</code> — ежедневные задачи\n"
        "<code>награды</code> — все доступные бонусы\n\n"
        f"{brand.div()}"
    ),
    "stats": (
        f"{brand.hdr()}\n\n"
        "📊 Статистика чата — V6\n\n"
        f"{brand.div()}\n"
        "<code>статчата</code> — детальная статистика\n"
        "<code>онлайн</code> — активные участники\n"
        "<code>аналитика</code> — данные системы\n"
        "<code>рост</code> — участники по чатам\n\n"
        "🎮 <b>Игры (только в ЛС бота):</b>\n"
        "<code>/орёл [сумма]</code> — монетка\n"
        "<code>/плинко [сумма]</code> — плинко\n"
        "<code>/лимбо [сумма] [цель×]</code> — лимбо\n"
        "<code>/краш [сумма]</code> — краш 🚀\n"
        "<code>/блэкджек [сумма]</code> — блэкджек 🃏\n"
        "<code>/мины [сумма]</code> — мины 💣\n"
        "<code>/ставка [сумма] [0-36]</code> — рулетка\n\n"
        f"{brand.div()}"
    ),
    "ref": (
        f"{brand.hdr()}\n\n"
        "🔗 Рефералы — V6\n\n"
        f"{brand.div()}\n"
        "📨 <b>Команды:</b>\n"
        "<code>инвайт</code> — твоя реферальная ссылка\n"
        "<code>рефералы</code> — список приглашённых\n"
        "<code>инвайты</code> — статистика инвайтов\n\n"
        "🎁 <b>Бонус за реферала:</b>\n"
        "• +1000 LMN тебе\n"
        "• +100 XP тебе\n\n"
        "💡 Поделись ссылкой с друзьями!\n\n"
        f"{brand.div()}"
    ),
}


@dp.callback_query(F.data.startswith("help:"))
async def cb_help_nav(cb: CallbackQuery):
    section = cb.data.split(":", 1)[1]
    if section == "menu":
        await cb.message.edit_text(
            f"{brand.hdr()}\n\n"
            f"✦ · · · Справочный центр · · · ✦\n\n"
            f"Выбери раздел — расскажу всё\n"
            f"о командах и возможностях 👇\n\n"
            f"<i>Команды работают без / —\n"
            f"просто напиши нужное слово в чат</i>\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
            reply_markup=_HELP_MAIN_KB,
        )
    elif section in _HELP_SECTIONS:
        await cb.message.edit_text(
            _HELP_SECTIONS[section],
            parse_mode="HTML",
            reply_markup=_HELP_BACK_KB,
        )
    await cb.answer()

# ═══════════════════════════════════════════════════════
# ПОДДЕРЖКА — ОБРАЩЕНИЕ К АДМИНИСТРАЦИИ
# ═══════════════════════════════════════════════════════
async def cmd_support(msg: Message):
    """Команда /помощь — форма обращения к администрации."""
    uid = msg.from_user.id
    if msg.chat.type != "private":
        await msg.reply(
            "📩 Для отправки обращения напиши боту в личку:\n"
            "👉 @LumenarAi\\_Bot — команда /помощь",
            parse_mode="Markdown"
        )
        return
    mod_chat = _ank.get_mod_chat()
    if not mod_chat:
        await msg.reply(
            "⚠️ Чат администрации ещё не настроен. Обратитесь к владельцу бота."
        )
        return
    support_sessions[uid] = True
    await _answer_custom(
        msg, "support_prompt",
        "📩 <b>Обращение к администрации</b>\n\n"
        "Напиши своё сообщение следующим — оно уйдёт прямо в чат администрации.\n\n"
        "<i>Для отмены напиши /отмена</i>",
    )


async def _farm_soon(msg: Message):
    await msg.reply("🌾 <b>Farm</b>\n\n<i>Coming soon! Stay tuned 🚀</i>", parse_mode="HTML")

@dp.message(Command("ферма", "ferma", "farm"))
async def cmd_farm_slash(msg: Message):
    await _farm_soon(msg)


# ── Магазин (coming soon) ───────────────────────────────
async def _shop_soon(msg: Message):
    await msg.reply(
        brand.get_text("shop_coming_soon") or (
            f"{brand.hdr()}\n\n"
            f"🛒 <b>Магазин LMN</b>\n\n"
            f"⚙️ <i>Скоро відкриється!</i>\n\n"
            f"Тут можна буде витратити зароблені {brand.currency()} на:\n"
            f"• 🎭 Ролі та статуси\n"
            f"• 🛡 Захист від пограбування\n"
            f"• ⚡ Буст заробітку на зміні\n"
            f"• 🔥 Щит для стріку\n"
            f"• 🎁 Унікальні предмети\n\n"
            f"<i>Слідкуй за оновленнями!</i>\n\n"
            f"{brand.div()}"
        ),
        parse_mode="HTML",
    )


async def _inventory_soon(msg: Message):
    await msg.reply(
        brand.get_text("inventory_coming_soon") or (
            f"{brand.hdr()}\n\n"
            f"🎒 <b>Інвентар</b>\n\n"
            f"⚙️ <i>Скоро буде доступний!</i>\n\n"
            f"Тут зберігатимуться всі твої предмети з магазину.\n\n"
            f"<i>Поки що порожньо — зачекай відкриття магазину 🛒</i>\n\n"
            f"{brand.div()}"
        ),
        parse_mode="HTML",
    )


@dp.message(Command("shop", "магазин", "крамниця"))
async def cmd_shop_slash(msg: Message):
    await _shop_soon(msg)


@dp.message(Command("inventory", "інвентар", "инвентарь", "inv"))
async def cmd_inventory_slash(msg: Message):
    await _inventory_soon(msg)

# ═══════════════════════════════════════════════════════
# ТЕКСТОВЫЕ КОМАНДЫ БЕЗ ПРЕФИКСА
# ═══════════════════════════════════════════════════════
# Только admin-команды требуют ! (бан, мут)
TEXT_COMMANDS: dict = {}

def reg(*words):
    """Регистрирует функцию на несколько ключевых слов"""
    def decorator(func):
        for w in words:
            TEXT_COMMANDS[w] = func
        return func
    return decorator

# Регистрируем все команды (без бан и мут — они только через !)
TEXT_COMMANDS.update({
    # Модерация (без бан/мут)
    "размут": cmd_unmute, "разбан": cmd_unban, "кик": cmd_kick,
    "мут1": cmd_mute1, "mute1": cmd_mute1,
    "варн": cmd_warn, "снятьварн": cmd_unwarn, "очистить": cmd_purge,
    "ро": cmd_ro, "закрепить": cmd_pin, "открепить": cmd_unpin,
    # Стрики
    "чекин": cmd_checkin, "стрик": cmd_streak,
    "топстриков": cmd_topstreak, "топ стриков": cmd_topstreak,
    "сбросстрик": cmd_resetstreak,
    # Валюта
    "баланс": cmd_balance, "кошелёк": cmd_balance,
    "работа": cmd_work, "рыбалка": cmd_fish, "охота": cmd_hunt, "hunt": cmd_hunt,
    "казино": cmd_casino, "слоты": cmd_slots, "слот": cmd_slots,
    "ограбить": cmd_rob, "украсть": cmd_rob,
    "банк": _bank_card, "bank": _bank_card,
    "сохранить": _bank_deposit, "save": _bank_deposit,
    "снять": lambda m: _bank_withdraw(m, " ".join((m.text or "").split()[1:])),
    "вывести": lambda m: _bank_withdraw(m, " ".join((m.text or "").split()[1:])),
    "дать": cmd_give, "перевести": cmd_give,
    "топбогачей": cmd_richest, "топ богачей": cmd_richest,
    "выдатьадминам": cmd_givetoadmins,
    "выдатьроли": cmd_give_role,
    "наградить": cmd_award,
    "раздать": cmd_razdach,
    "забрать500м": cmd_ownerclaim, "ownerclaim": cmd_ownerclaim,
    # Репутация
    "репутация": cmd_rep, "реп": cmd_rep,
    "+": cmd_upvote, "плюс": cmd_upvote,
    "-": cmd_downvote, "минус": cmd_downvote,
    "топрепутации": cmd_toprep, "топ репутации": cmd_toprep,
    "аура": cmd_aura, "ауру": cmd_aura, "моя аура": cmd_aura,
    "топауры": cmd_topaura, "топ ауры": cmd_topaura,
    # Брак
    "брак": cmd_marry, "жениться": cmd_marry, "замуж": cmd_marry,
    "развод": cmd_divorce,
    # Роли
    "роль": cmd_set_role, "setrole": cmd_set_role,
    "убратьроль": cmd_remove_role, "снятьроль": cmd_remove_role, "removerole": cmd_remove_role,
    "роли": cmd_roles, "roles": cmd_roles,
    "списокбраков": cmd_marriages, "список браков": cmd_marriages, "браки": cmd_marriages,
    # Отношения
    "корабль": cmd_ship, "шип": cmd_ship,
    "совместимость": cmd_compatibility, "compatibility": cmd_compatibility,
    "любовь": cmd_love, "дружба": cmd_friend,
    "пара": cmd_couple,
    # Социальные
    "обнять": cmd_hug, "обнимашки": cmd_hug,
    "поцеловать": cmd_kiss, "поцелуй": cmd_kiss,
    "укусить": cmd_bite, "погладить": cmd_pat,
    "ударить": cmd_slap, "подарить": cmd_gift,
    "станцевать": cmd_dance, "танцевать": cmd_dance,
    "потыкать": cmd_poke, "пятёрку": cmd_highfive,
    "помахать": cmd_wave, "фейспалм": cmd_facepalm,
    "серенада": cmd_serenade,
    # Предсказания
    "предсказание": cmd_fortune, "гадалка": cmd_fortune,
    "8ball": cmd_8ball, "шар": cmd_8ball, "магический шар": cmd_8ball,
    "гороскоп": cmd_horoscope, "таро": cmd_tarot,
    "предсказать": cmd_predict, "судьба": cmd_destiny,
    "суперсила": cmd_superpower, "профессия": cmd_profession,
    "нумерология": cmd_numerology,
    # Игры
    "монетка": cmd_coin, "кубик": cmd_dice,
    "рандом": cmd_random_num,
    "ролл": cmd_roll, "выбрать": cmd_choose, "выбери": cmd_choose,
    "оценить": cmd_rate, "оценка": cmd_rate,
    "правда": cmd_truth, "действие": cmd_dare,
    "загадка": cmd_riddle, "рулетка": cmd_roulette,
    "рулетка_старт": cmd_roulette_start,
    "виселица": cmd_hangman,
    # Развлечения
    "шутка": cmd_joke, "анекдот": cmd_joke,
    "факт": cmd_fact, "цитата": cmd_quote,
    "котик": cmd_cat, "кот": cmd_cat, "пёс": cmd_dog, "собака": cmd_dog,
    "комплимент": cmd_compliment, "роаст": cmd_roast,
    "животное": cmd_animal, "фильм": cmd_movie, "книга": cmd_book,
    "совет": cmd_advice, "мотивация": cmd_motivation,
    "миф": cmd_myth, "страна": cmd_country, "цвет": cmd_color,
    "эмодзи": cmd_emoji_combo, "смайл": cmd_emoji_combo,
    # Утилиты
    "пароль": cmd_password, "uuid": cmd_uuid_gen,
    "бми": cmd_bmi, "возраст": cmd_age,
    # Профиль
    "кто я": cmd_whois, "кто это": cmd_whois, "whois": cmd_whois, "досье": cmd_whois,
    "профиль": cmd_profile, "айди": cmd_myid, "инфочат": cmd_chatinfo,
    "статистика": cmd_botstats, "пинг": cmd_ping, "версия": cmd_version,
    "інфо": cmd_info, "инфо": cmd_info, "info": cmd_info,
    "сетбио": cmd_setbio, "сетзвание": cmd_settitle,
    "правила": cmd_rules, "сетправила": cmd_setrules,
    "объявление": cmd_announce,
    # Помощь
    "помощь": cmd_support, "команды": cmd_help, "хелп": cmd_help,
    # Фарм (скоро)
    "ферма": _farm_soon, "фарм": _farm_soon, "farm": _farm_soon,
    "магазин": _shop_soon, "крамниця": _shop_soon, "shop": _shop_soon,
    "інвентар": _inventory_soon, "инвентарь": _inventory_soon, "inv": _inventory_soon,
    # Алхимия
    "алхимия": cmd_alchemy,
    "командная алхимия": cmd_team_alchemy,
    "команда алхимия": cmd_team_alchemy,
    "teamalchemy": cmd_team_alchemy,
})

# Slash-команды только для функций БЕЗ @dp.message(Command(...)) декоратора
# (команды с декораторами уже зарегистрированы — дублировать нельзя!)
for slash_name, func in [
    # Социальные действия (без декоратора)
    ("hug", cmd_hug), ("kiss", cmd_kiss), ("bite", cmd_bite),
    ("pat", cmd_pat), ("slap", cmd_slap), ("gift", cmd_gift),
    ("dance", cmd_dance), ("poke", cmd_poke), ("highfive", cmd_highfive),
    ("wave", cmd_wave), ("facepalm", cmd_facepalm), ("serenade", cmd_serenade),
    # Отношения (без декоратора)
    ("ship", cmd_ship), ("love", cmd_love), ("friend", cmd_friend),
    ("couple", cmd_couple),
    # Предсказания (без декоратора)
    ("fortune", cmd_fortune), ("8ball", cmd_8ball), ("horoscope", cmd_horoscope),
    ("tarot", cmd_tarot), ("predict", cmd_predict), ("destiny", cmd_destiny),
    # Игры (без декоратора)
    ("coin", cmd_coin), ("dice", cmd_dice),
    ("random", cmd_random_num), ("choose", cmd_choose), ("rate", cmd_rate),
    ("truth", cmd_truth), ("dare", cmd_dare), ("riddle", cmd_riddle),
    ("roulette", cmd_roulette), ("roulette_start", cmd_roulette_start),
    ("hangman", cmd_hangman), ("roll", cmd_roll),
    # Развлечения (без декоратора)
    ("joke", cmd_joke), ("fact", cmd_fact), ("quote", cmd_quote),
    ("cat", cmd_cat), ("dog", cmd_dog),
    ("compliment", cmd_compliment), ("roast", cmd_roast),
    ("superpower", cmd_superpower), ("profession", cmd_profession),
    ("animal", cmd_animal), ("movie", cmd_movie), ("book", cmd_book),
    ("advice", cmd_advice), ("motivation", cmd_motivation),
    ("myth", cmd_myth), ("country", cmd_country), ("color", cmd_color),
    # Утилиты (без декоратора)
    ("password", cmd_password), ("uuid", cmd_uuid_gen),
    ("bmi", cmd_bmi), ("age", cmd_age), ("numerology", cmd_numerology),
    # Профиль / инфо (без декоратора)
    ("whois", cmd_whois),
    ("profile", cmd_profile), ("myid", cmd_myid), ("chatinfo", cmd_chatinfo),
    ("ping", cmd_ping), ("version", cmd_version), ("botstats", cmd_botstats),
    ("setbio", cmd_setbio), ("settitle", cmd_settitle),
    # Правила (без декоратора)
    ("rules", cmd_rules), ("setrules", cmd_setrules), ("announce", cmd_announce),
    # Помощь (без декоратора)
    ("help", cmd_help),
    # ─── Кириллические слэш-алиасы ───────────────────────
    # Теперь /баланс, /брак, /чекин и др. работают со слешем
    ("брак", cmd_marry), ("развод", cmd_divorce), ("браки", cmd_marriages),
    ("гороскоп", cmd_horoscope),
    ("баланс", cmd_balance), ("работа", cmd_work), ("рыбалка", cmd_fish), ("hunt", cmd_hunt),
     ("алхимия", cmd_alchemy), ("teamalchemy", cmd_team_alchemy),
     ("команднаяалхимия", cmd_team_alchemy), ("командаалхимия", cmd_team_alchemy),
    ("казино", cmd_casino), ("слоты", cmd_slots), ("ограбить", cmd_rob),
    ("дать", cmd_give),
    ("чекин", cmd_checkin), ("стрик", cmd_streak),
    ("топстриков", cmd_topstreak),
    ("репутация", cmd_rep),
    ("профиль", cmd_profile), ("айди", cmd_myid), ("инфочат", cmd_chatinfo),
    ("статистика", cmd_botstats), ("пинг", cmd_ping), ("версия", cmd_version),
    ("інфо", cmd_info), ("инфо", cmd_info), ("info", cmd_info),
    ("правила", cmd_rules), ("команды", cmd_help),
    ("помощь", cmd_support), ("поддержка", cmd_support), ("support", cmd_support),
]:
    dp.message.register(func, Command(slash_name))

# ═══════════════════════════════════════════════════════
# MIDDLEWARE АВТОМОДЕРАЦИИ ПРОПАГАНДЫ
# Перехватывает КАЖДОЕ сообщение до любых хендлеров
# ═══════════════════════════════════════════════════════
from aiogram import BaseMiddleware
from typing import Callable, Any

import re as _re

# ── Антилинк: вспомогательные функции ─────────────────────────
_URL_ENTITY_TYPES = {"url", "text_link"}
_RAW_LINK_RE = _re.compile(
    r"(?:https?://|t\.me/)[^\s<>\"']+",
    _re.IGNORECASE,
)


def _msg_has_links(msg: Message) -> bool:
    """True если в сообщении есть URL-entity или сырая ссылка в тексте."""
    for ents in (msg.entities or [], msg.caption_entities or []):
        for ent in ents:
            if ent.type in _URL_ENTITY_TYPES:
                return True
    text = msg.text or msg.caption or ""
    return bool(_RAW_LINK_RE.search(text))


def _extract_links(msg: Message) -> list[str]:
    """Список всех ссылок из сообщения."""
    links: list[str] = []
    text = msg.text or msg.caption or ""
    for ents in (msg.entities or [], msg.caption_entities or []):
        for ent in ents:
            if ent.type == "url":
                links.append(text[ent.offset: ent.offset + ent.length])
            elif ent.type == "text_link" and ent.url:
                links.append(ent.url)
    if not links:
        links = _RAW_LINK_RE.findall(text)
    return links


def _link_allowed(link: str, chat_id: int) -> bool:
    """True если ссылка разрешена: собственные бренд-ссылки или белый список чата."""
    link_l = link.lower()
    # Все URL из BUTTON_DEFS (собственный бренд)
    for _, df in brand.BUTTON_DEFS.items():
        url = (df.get("url") or "").lower()
        if url and url.rstrip("/") in link_l:
            return True
    # Белый список чата
    for pat in _link_whitelist.get(chat_id, []):
        if pat.lower() in link_l:
            return True
    return False


async def _check_link_guard(msg: Message) -> bool:
    """Автоудаление ссылок. Возвращает True если сообщение удалено."""
    if not _link_guard.get(msg.chat.id, False):
        return False
    if msg.chat.type == "private":
        return False
    if not msg.from_user or msg.from_user.is_bot:
        return False

    # ── Чат администрации — ссылки всегда разрешены ────────────
    mod_chat = _ank.get_mod_chat()
    if mod_chat and msg.chat.id == mod_chat:
        return False

    # ── Администрация в любом чате — разрешены ─────────────────
    uid = msg.from_user.id
    if has_role(uid, "lead_admin", "co_admin", "admin", "moderator") or is_owner(msg):
        return False
    try:
        member = await bot.get_chat_member(msg.chat.id, uid)
        if member.status in ("administrator", "creator"):
            return False
    except Exception:
        pass

    # ── Проверяем наличие ссылок ────────────────────────────────
    if not _msg_has_links(msg):
        # Проверяем форварды из каналов
        fwd_chat = getattr(msg, "forward_from_chat", None)
        if not (fwd_chat and getattr(fwd_chat, "type", None) in ("channel", "supergroup")):
            return False
        # Форвард из канала — проверяем whitelist
        fwd_username = getattr(fwd_chat, "username", None)
        if fwd_username and _link_allowed(f"t.me/{fwd_username}", msg.chat.id):
            return False

    else:
        links = _extract_links(msg)
        # Все ссылки в белом списке — пропускаем
        if links and all(_link_allowed(lnk, msg.chat.id) for lnk in links):
            return False

    # ── Удаляем сообщение ───────────────────────────────────────
    try:
        await msg.delete()
    except Exception:
        pass

    # ── Мут 1 минута сразу ─────────────────────────────────────
    name    = msg.from_user.full_name
    mention = f'<a href="tg://user?id={uid}">{html.escape(name)}</a>'
    until   = int(datetime.now(tz=KYIV_TZ).timestamp()) + 60  # 1 минута

    muted = False
    try:
        await bot.restrict_chat_member(
            msg.chat.id, uid,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until,
        )
        muted = True
    except Exception:
        pass

    mute_text = "🔇 мут <b>1 минута</b>" if muted else "⚠️ ссылки запрещены"
    try:
        warn_msg = await bot.send_message(
            msg.chat.id,
            f"🔗 {mention} — <b>ссылки запрещены!</b>\n"
            f"{mute_text}\n\n"
            f"<i>Сообщение автоматически удалено.</i>",
            parse_mode="HTML",
        )
        # ── Автоудаление уведомления через 30 с ─────────────────
        async def _del_warn():
            await asyncio.sleep(30)
            try:
                await warn_msg.delete()
            except Exception:
                pass
        asyncio.create_task(_del_warn())
    except Exception:
        pass

    save_data()
    return True


# ═══════════════════════════════════════════════════════════════
# MIDDLEWARE АВТОМОДЕРАЦИИ
# ═══════════════════════════════════════════════════════════════
class PropagandaMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable,
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        # Трекинг участников — здесь, чтобы ловить ВСЕХ кто пишет
        if (isinstance(event, Message)
                and event.from_user
                and not event.from_user.is_bot
                and event.chat.type != "private"):
            _uid_mw = event.from_user.id
            _cid_mw = event.chat.id
            chat_members.setdefault(_cid_mw, {})[_uid_mw] = event.from_user.full_name
            # V6: XP + счётчик сообщений
            user_messages.setdefault(_cid_mw, {})
            _new_cnt = user_messages[_cid_mw].get(_uid_mw, 0) + 1
            user_messages[_cid_mw][_uid_mw] = _new_cnt
            # Ежедневный счётчик сообщений (для задания дня)
            _today_mw = today_kyiv().isoformat()
            _dmc = daily_msg_cnt.setdefault(_uid_mw, {"date": _today_mw, "count": 0})
            if _dmc.get("date") != _today_mw:
                _dmc["date"] = _today_mw; _dmc["count"] = 0
            _dmc["count"] += 1
            if _new_cnt % 5 == 0:          # Сохраняем каждые 5 сообщений
                schedule_state_save("повідомлення")
            if "first_message" not in user_achievements.get(_uid_mw, []):
                user_achievements.setdefault(_uid_mw, []).append("first_message")
            award_xp(_uid_mw, random.randint(1, 5))
            # Антиспам
            if antispam_mode.get(_cid_mw) and event.text:
                import time as _t
                import hashlib as _hl
                # Пропускаем команды и пользователей с ролями/админов
                _is_cmd = (event.text or "").startswith("/")
                _has_role = has_role(_uid_mw, "lead_admin", "co_admin", "admin", "moderator")
                if not _is_cmd and not _has_role and _uid_mw != OWNER_ID:
                    # Нормализованный хэш всего текста (не обрезаем — иначе обходится)
                    _norm = " ".join((event.text or "").lower().split())
                    _txt_hash = _hl.md5(_norm.encode()).hexdigest()
                    _asp = antispam_tracker.setdefault(_cid_mw, {})
                    # TTL-cleanup: удаляем записи старше 60 секунд для экономии памяти
                    _now_ts = _t.time()
                    _stale = [u for u, v in _asp.items() if _now_ts - v.get("ts", 0) > 60]
                    for _su in _stale:
                        _asp.pop(_su, None)
                    _usr = _asp.setdefault(_uid_mw, {"hash": "", "count": 0, "ts": 0.0})
                    if _txt_hash == _usr["hash"] and _now_ts - _usr["ts"] < 30:
                        _usr["count"] += 1
                        if _usr["count"] >= 3:
                            _deleted = False
                            try:
                                await event.delete()
                                _deleted = True
                            except Exception:
                                pass
                            if _deleted:
                                # Сбрасываем счётчик только при успешном удалении
                                _asp[_uid_mw] = {"hash": "", "count": 0, "ts": 0.0}
                                return  # Спам удалён — дальше не обрабатываем
                    else:
                        _asp[_uid_mw] = {"hash": _txt_hash, "count": 1, "ts": _now_ts}

        if isinstance(event, Message):
            # Антилинк — до пропаганды, чтобы оба не мешали друг другу
            if await _check_link_guard(event):
                return   # ссылка удалена — дальше не обрабатываем

            if event.text:
                if await auto_moderate_propaganda(event):
                    return   # Пропаганда — прерываем

        return await handler(event, data)

dp.message.middleware(PropagandaMiddleware())

# ═══════════════════════════════════════════════════════
# ГЛАВНЫЙ ОБРАБОТЧИК СООБЩЕНИЙ
# ═══════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════
# АНКЕТИ — CALLBACKS МОДЕРАЦІЇ
# ═══════════════════════════════════════════════════════
@dp.callback_query(F.data.startswith("ank_lang:"))
async def cb_ank_lang(cb: CallbackQuery):
    """Вибір мови анкети."""
    if cb.message.chat.type != "private":
        return await cb.answer()
    await _ank.handle_lang_select(bot, cb)


@dp.callback_query(F.data.startswith("ank_media_done:"))
async def cb_ank_media_done(cb: CallbackQuery):
    """Юзер натиснув «Готово» — завершуємо збір медіа і відправляємо анкету."""
    uid = int(cb.data.split(":", 1)[1])
    if cb.from_user.id != uid:
        return await cb.answer("Это не твоя анкета", show_alert=True)
    session = _ank._sessions.get(uid)
    if not session or session.get("step") != _ank.PHOTO_STEP_IDX:
        return await cb.answer("Анкета не найдена или уже отправлена", show_alert=True)
    session = _ank._sessions.pop(uid)
    await _ank._finish_anketa(bot, uid, session)
    await cb.answer("✅ Отправлено на модерацию!")


@dp.callback_query(F.data.startswith("ank_media_skip:"))
async def cb_ank_media_skip(cb: CallbackQuery):
    """Юзер натиснув «Без медіа» — відправляємо анкету без фото/відео."""
    uid = int(cb.data.split(":", 1)[1])
    if cb.from_user.id != uid:
        return await cb.answer("Это не твоя анкета", show_alert=True)
    session = _ank._sessions.get(uid)
    if not session or session.get("step") != _ank.PHOTO_STEP_IDX:
        return await cb.answer("Анкета не найдена или уже отправлена", show_alert=True)
    session = _ank._sessions.pop(uid)
    session["media_items"] = []
    await _ank._finish_anketa(bot, uid, session)
    await cb.answer("⏭ Пропущено")


@dp.callback_query(F.data.startswith("ank_ok:"))
async def cb_ank_accept(cb: CallbackQuery):
    app_id = cb.data.split(":", 1)[1]
    app = _ank._pending.get(app_id)
    if not app:
        return await cb.answer("Заявка не найдена или уже обработана", show_alert=True)
    mod_name = cb.from_user.full_name
    uid = app["user_id"]

    # 1. Публікуємо в паблік-чат, зберігаємо msg_id
    pub_chat  = _ank.get_pub_chat()
    pub_msg_id       = None
    pub_media_msg_ids: list[int] = []   # IDs альбому (2+ медіа) для видалення
    pub_ok    = False
    media_items = app["answers"].get("media", [])
    # backward compat: old single-media fields
    if not media_items:
        if app["answers"].get("video_id"):
            media_items = [{"type": "video", "file_id": app["answers"]["video_id"]}]
        elif app["answers"].get("photo_id"):
            media_items = [{"type": "photo", "file_id": app["answers"]["photo_id"]}]
    _vip = is_anketa_premium(uid, app.get("username", ""))
    pub_text = _ank.fmt_pub_card(app["answers"], app["username"], app["full_name"],
                                  is_premium=_vip)
    _rkb = _ank.reaction_kb(uid)  # клавіатура реакцій
    if pub_chat:
        try:
            n = len(media_items)
            if n == 0:
                sent_pub = await bot.send_message(
                    pub_chat, pub_text, parse_mode="HTML",
                    reply_markup=_rkb,
                )
            elif n == 1:
                item = media_items[0]
                if item["type"] == "photo":
                    sent_pub = await bot.send_photo(
                        pub_chat, photo=item["file_id"],
                        caption=pub_text, parse_mode="HTML",
                        reply_markup=_rkb,
                    )
                else:
                    sent_pub = await bot.send_video(
                        pub_chat, video=item["file_id"],
                        caption=pub_text, parse_mode="HTML",
                        reply_markup=_rkb,
                    )
            else:
                # 2–10 медіа: альбом, потім текст з реакціями
                _media_ids = await _ank._send_media_group_to_chat(bot, pub_chat, media_items)
                sent_pub = await bot.send_message(
                    pub_chat, pub_text, parse_mode="HTML",
                    reply_markup=_rkb,
                )
                pub_media_msg_ids = _media_ids  # зберігаємо для майбутнього видалення
            pub_msg_id = sent_pub.message_id
            pub_ok = True
            # Публікуємо анкету й одразу закріплюємо саме картку з реакціями.
            # Помилка прав Telegram не повинна скасовувати схвалення анкети:
            # у такому випадку вона лишається опублікованою, а причина потрапляє
            # в лог Railway.
            try:
                await bot.pin_chat_message(
                    pub_chat,
                    pub_msg_id,
                    disable_notification=True,
                )
            except Exception as pin_error:
                print(f"⚠️ Не вдалося закріпити анкету {pub_msg_id} у {pub_chat}: {pin_error}")
        except Exception as e:
            print(f"⚠️ pub_chat send error: {e}")

    # 2. Зберігаємо статус approved (з номером анкети і IDs медіа для видалення)
    _ank.set_approved(uid, app["answers"], app["username"], app["full_name"],
                      pub_msg_id=pub_msg_id, pub_chat_id=pub_chat,
                      anketa_num=app.get("anketa_num"),
                      media_msg_ids=pub_media_msg_ids)

    # 3. Уведомление в мод-чат об одобрении
    anketa_num = app.get("anketa_num", "")
    num_txt    = f" №{anketa_num}" if anketa_num else ""
    mod_chat   = _ank.get_mod_chat()
    mod_tag    = f"@{cb.from_user.username}" if cb.from_user.username else mod_name
    owner_uname = f"@{app['username']}" if app.get("username") else "—"
    if mod_chat:
        try:
            await bot.send_message(
                mod_chat,
                f"{brand.chk()} <b>Анкета принята</b>\n\n"
                f"📋 Номер: <b>№{anketa_num or '—'}</b>\n"
                f"👤 Владелец: <b>{html.escape(app['full_name'])}</b> ({html.escape(owner_uname)})\n"
                f"🆔 ID: <code>{uid}</code>\n"
                f"👮 Принял: {html.escape(mod_tag)}\n"
                + (f"🔗 Опубликовано в паблике\n" if pub_ok else f"{brand.e('warn')} Чат публикаций не настроен\n")
                + f"\n{brand.div()}",
                parse_mode="HTML"
            )
        except Exception:
            pass

    # 4. Повідомляємо автора з новою клавіатурою
    pub_note   = "\n\nТвоя анкета опубликована в чате знакомств! 🎉" if pub_ok else ""
    try:
        await _send_custom(
            uid, "anketa_approve",
            f"{brand.hdr()}\n\n"
            f"{brand.chk()} <b>Твоя анкета{html.escape(num_txt)} одобрена!</b>"
            f"{html.escape(pub_note)}\n\n"
            "Теперь можешь просмотреть или изменить её — нажми кнопку ниже 💌",
            reply_markup=_anketa_kb(uid)
        )
    except Exception:
        pass

    # 5. Обновляем карточку модерации
    try:
        old_text = cb.message.text or cb.message.caption or ""
        new_text = (old_text + f"\n\n{brand.chk()} <b>ПРИНЯТО</b> — {html.escape(mod_name)}"
                    + (" | опубликовано" if pub_ok else f" | {brand.e('warn')} чат публикаций не настроен"))
        if cb.message.photo or cb.message.video:
            await cb.message.edit_caption(new_text, parse_mode="HTML", reply_markup=None)
        else:
            await cb.message.edit_text(new_text, parse_mode="HTML", reply_markup=None)
    except Exception:
        pass

    del _ank._pending[app_id]
    await cb.answer("✅ Принято и опубликовано!" if pub_ok else "✅ Принято", show_alert=True)


@dp.callback_query(F.data.startswith("ank_no:"))
async def cb_ank_reject(cb: CallbackQuery):
    app_id = cb.data.split(":", 1)[1]
    app = _ank._pending.get(app_id)
    if not app:
        return await cb.answer("Заявка не найдена или уже обработана", show_alert=True)
    mod_name = cb.from_user.full_name
    uid = app["user_id"]

    _ank.set_rejected(uid)

    try:
        await _send_custom(
            uid, "anketa_reject",
            f"{brand.hdr()}\n\n"
            f"{brand.e('cross')} <b>К сожалению, твоя анкета отклонена.</b>\n\n"
            "Можешь исправить и подать снова — нажми кнопку ниже.",
            reply_markup=_anketa_kb(uid)
        )
    except Exception:
        pass
    try:
        old_text = cb.message.text or cb.message.caption or ""
        new_text = old_text + f"\n\n❌ <b>ОТКЛОНЕНО</b> — {html.escape(mod_name)}"
        if cb.message.photo or cb.message.video:
            await cb.message.edit_caption(new_text, parse_mode="HTML", reply_markup=None)
        else:
            await cb.message.edit_text(new_text, parse_mode="HTML", reply_markup=None)
    except Exception:
        pass
    del _ank._pending[app_id]
    await cb.answer("❌ Отклонено", show_alert=True)


# ─── Реакції ❤️ / 👎 на публічних анкетах ───
@dp.callback_query(F.data.startswith("ank_r:"))
async def cb_ank_react(cb: CallbackQuery):
    """Обробляє натискання ❤️ або 👎 під анкетою в паблік-чаті."""
    parts = cb.data.split(":")          # ["ank_r", "h"/"d", owner_uid]
    if len(parts) != 3:
        return await cb.answer()
    rtype, owner_uid = parts[1], int(parts[2])

    reactor     = cb.from_user
    reactor_uid = reactor.id

    # Власник не може лайкати сам себе
    if reactor_uid == owner_uid:
        return await cb.answer("Це твоя власна анкета 😊", show_alert=True)

    is_heart, is_new_heart = _ank.record_reaction(
        owner_uid, reactor_uid,
        reactor.full_name, reactor.username or ""
    , rtype)

    # Оновлюємо кнопки під постом
    try:
        await cb.message.edit_reply_markup(reply_markup=_ank.reaction_kb(owner_uid))
    except Exception:
        pass

    # Уведомляем владельца если новый ❤️
    if is_new_heart:
        try:
            await bot.send_message(
                owner_uid,
                "❤️ *Кому-то понравилась твоя анкета!*\n\n"
                "_Нажми кнопку чтобы ответить взаимностью и узнать кто это_ 👇",
                parse_mode="Markdown",
                reply_markup=_ank.make_mutual_kb(reactor_uid, owner_uid)
            )
        except Exception:
            pass
        await cb.answer("❤️ Лайк поставлен!", show_alert=False)
    elif not is_heart:
        await cb.answer("👎", show_alert=False)
    else:
        await cb.answer("Лайк убран", show_alert=False)


# ─── Взаємність: власник хоче дізнатись хто лайкнув ───
@dp.callback_query(F.data.startswith("ank_mutual:"))
async def cb_ank_mutual(cb: CallbackQuery):
    """Власник натискає 'Відповісти взаємністю' — бот розкриває ім'я лайкера."""
    parts = cb.data.split(":")          # ["ank_mutual", reactor_uid, owner_uid]
    if len(parts) != 3:
        return await cb.answer()
    reactor_uid, owner_uid = int(parts[1]), int(parts[2])

    if cb.from_user.id != owner_uid:
        return await cb.answer("Это не твоя анкета", show_alert=True)

    # Проверяем актуален ли лайк
    hearts = _ank.get_hearts(owner_uid)
    info   = hearts.get(reactor_uid)
    if not info:
        await cb.message.edit_reply_markup(reply_markup=None)
        return await cb.answer("Этот человек уже убрал лайк 😔", show_alert=True)

    reactor_name = info["name"]
    reactor_user = info["username"]
    tag = f"@{reactor_user}" if reactor_user else reactor_name

    # Показываем владельцу кто это
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer(
        f"💞 *Взаимная симпатия!*\n\n"
        f"Тебя лайкнул(а): *{reactor_name}*\n"
        f"Telegram: {tag}\n\n"
        "_Напиши первым — возможно это судьба! 🌟_",
        parse_mode="Markdown"
    )

    # Уведомляем лайкера
    owner_data = _ank.get_approved_data(owner_uid)
    owner_name = owner_data["answers"].get("name", "автор анкеты") if owner_data else "автор анкеты"
    try:
        await bot.send_message(
            reactor_uid,
            f"💞 *Взаимная симпатия!*\n\n"
            f"*{owner_name}* ответил(а) на твой лайк — можешь написать им!",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    await cb.answer("💞 Взаимно!", show_alert=True)


@dp.callback_query(F.data.startswith("ank_cm:"))
async def cb_ank_mod_comment(cb: CallbackQuery):
    app_id = cb.data.split(":", 1)[1]
    app = _ank._pending.get(app_id)
    if not app:
        return await cb.answer("Заявка не найдена", show_alert=True)
    _ank._mod_commenting[cb.from_user.id] = app_id
    await cb.answer("Напишите правки следующим сообщением в этом чате", show_alert=True)
    await cb.message.reply(
        f"✏️ {cb.from_user.mention_html()}, напишите правки для "
        f"<b>{app['full_name']}</b> — следующее сообщение уйдёт автору:",
        parse_mode="HTML"
    )


# ─── Кнопки юзера: видалити / редагувати свою анкету ───
@dp.callback_query(F.data.startswith("ank_start:"))
async def cb_ank_start_private(cb: CallbackQuery):
    uid = int(cb.data.split(":", 1)[1])
    if cb.from_user.id != uid:
        return await cb.answer("Это не для тебя", show_alert=True)
    status = _ank.get_user_status(uid)
    if status == "pending":
        return await cb.answer("⏳ Анкета уже на проверке", show_alert=True)
    _ank._sessions[uid] = {
        "step": -1, "answers": {},
        "username": cb.from_user.username or "",
        "full_name": cb.from_user.full_name,
        "lang": None,
    }
    await bot.send_message(
        uid,
        "💌 *Анкета знакомств / Анкета знайомств*\n\nВыберите язык / Виберіть мову:",
        parse_mode="Markdown",
        reply_markup=_ank._lang_kb()
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("ank_mycard:"))
async def cb_ank_mycard_private(cb: CallbackQuery):
    uid = int(cb.data.split(":", 1)[1])
    if cb.from_user.id != uid:
        return await cb.answer("Это не твоя анкета", show_alert=True)
    status = _ank.get_user_status(uid)
    if status == "approved":
        data = _ank.get_approved_data(uid)
        if data:
            _vip2 = is_anketa_premium(uid, data.get("username", ""))
            card_text   = _ank.fmt_my_card(data["answers"], data["username"], data["full_name"],
                                            is_premium=_vip2)
            media_items = data["answers"].get("media", [])
            # backward compat — old single-media fields
            if not media_items:
                if data["answers"].get("video_id"):
                    media_items = [{"type": "video", "file_id": data["answers"]["video_id"]}]
                elif data["answers"].get("photo_id"):
                    media_items = [{"type": "photo", "file_id": data["answers"]["photo_id"]}]
            n = len(media_items)
            if n == 0:
                await bot.send_message(uid, card_text, parse_mode="HTML",
                                       reply_markup=_ank.make_my_anketa_kb(uid))
            elif n == 1:
                item = media_items[0]
                if item["type"] == "photo":
                    await bot.send_photo(uid, photo=item["file_id"], caption=card_text,
                                         parse_mode="HTML", reply_markup=_ank.make_my_anketa_kb(uid))
                else:
                    await bot.send_video(uid, video=item["file_id"], caption=card_text,
                                         parse_mode="HTML", reply_markup=_ank.make_my_anketa_kb(uid))
            else:
                # 2–10 медіа: альбом + текст з кнопками
                await _ank._send_media_group_to_chat(bot, uid, media_items)
                await bot.send_message(uid, card_text, parse_mode="HTML",
                                       reply_markup=_ank.make_my_anketa_kb(uid))
        else:
            await bot.send_message(uid, "Анкета не найдена.", reply_markup=_anketa_kb(uid))
    elif status == "pending":
        await bot.send_message(
            uid,
            "⏳ <b>Твоя анкета сейчас на проверке.</b>\n\n"
            "Если хочешь отменить её и заполнить новую, нажми кнопку ниже.",
            parse_mode="HTML",
            reply_markup=_ank.make_pending_anketa_kb(uid),
        )
        await cb.answer()
        return
    elif status == "rejected":
        await bot.send_message(uid, "❌ Анкета отклонена. Заполни новую 👇",
                               reply_markup=_anketa_kb(uid))
    else:
        await bot.send_message(uid, "У тебя ещё нет анкеты. Заполни! 💌",
                               reply_markup=_anketa_kb(uid))
    await cb.answer()


@dp.callback_query(F.data.startswith("ank_del:"))
async def cb_ank_delete(cb: CallbackQuery):
    uid = int(cb.data.split(":", 1)[1])
    if cb.from_user.id != uid:
        return await cb.answer("Это не твоя анкета", show_alert=True)

    data = _ank.delete_user_anketa(uid)

    # Удаляем карточку из чата модерации, если заявка была ещё pending.
    if data and data.get("mod_chat_id"):
        mod_chat = data["mod_chat_id"]
        if data.get("mod_msg_id"):
            try:
                await bot.delete_message(mod_chat, data["mod_msg_id"])
            except Exception:
                pass
        for _mid in (data.get("media_msg_ids") or []):
            try:
                await bot.delete_message(mod_chat, _mid)
            except Exception:
                pass
    else:
        # Удаляем опубликованную карточку (текст + медиа-альбом).
        pub_chat = data.get("pub_chat_id") if data else None
        pub_chat = pub_chat or _ank.get_pub_chat()
        if pub_chat and data:
            if data.get("pub_msg_id"):
                try:
                    await bot.delete_message(pub_chat, data["pub_msg_id"])
                except Exception:
                    pass
            for _mid in (data.get("media_msg_ids") or []):
                try:
                    await bot.delete_message(pub_chat, _mid)
                except Exception:
                    pass

    await cb.message.edit_reply_markup(reply_markup=None)
    await _send_custom(
        uid, "anketa_delete",
        f"🗑 <b>Твоя анкета удалена.</b>\n\nХочешь подать новую — нажми кнопку ниже.",
        reply_markup=_ank.make_new_anketa_kb(uid)
    )
    await cb.answer("Анкета удалена", show_alert=True)


@dp.callback_query(F.data.startswith("ank_edit:"))
async def cb_ank_user_edit(cb: CallbackQuery):
    uid = int(cb.data.split(":", 1)[1])
    if cb.from_user.id != uid:
        return await cb.answer("Это не твоя анкета", show_alert=True)

    # Удаляем старую публикацию (текст + медіа-альбом)
    data = _ank.delete_user_anketa(uid)
    pub_chat = (data.get("pub_chat_id") if data else None) or _ank.get_pub_chat()
    if pub_chat and data:
        if data.get("pub_msg_id"):
            try:
                await bot.delete_message(pub_chat, data["pub_msg_id"])
            except Exception:
                pass
        for _mid in (data.get("media_msg_ids") or []):
            try:
                await bot.delete_message(pub_chat, _mid)
            except Exception:
                pass

    await cb.message.edit_reply_markup(reply_markup=None)
    _ank._sessions[uid] = {
        "step": -1, "answers": {},
        "username": cb.from_user.username or "",
        "full_name": cb.from_user.full_name,
        "lang": None,
    }
    await bot.send_message(
        uid,
        "💌 *Анкета знакомств / Анкета знайомств*\n\nВыберите язык / Виберіть мову:",
        parse_mode="Markdown",
        reply_markup=_ank._lang_kb()
    )
    await cb.answer()


# ═══════════════════════════════════════════════════════
# АНКЕТИ — КОМАНДИ
# ═══════════════════════════════════════════════════════

def _anketa_kb(uid: int | None = None) -> ReplyKeyboardRemove:
    """Кнопка 'Моя анкета' скрыта — возвращаем пустую клавиатуру."""
    return ReplyKeyboardRemove()


_START_TEXT = (
    "✨ <b>Привет, {name}!</b>\n\n"
    "Я — <b>Лумена</b>, умный Telegram-бот нового поколения.\n\n"
    "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"
    "◆ <b>История создания</b>\n\n"
    "В 2026 году разработчик Hydra запустил проект с простой задачей: "
    "собрать всё нужное для Telegram-сообщества в одном месте — "
    "модерацию, экономику, общение и развлечения. Так появилась Лумена.\n\n"
    "Проект развивается без громких заявлений — просто работает "
    "и становится лучше с каждым обновлением.\n\n"
    "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"
    "🖤 <b>Что умею:</b>\n\n"
    "◾ База знаний 1000+ фактов — отвечаю мгновенно\n"
    "◾ Поиск в интернете и Wikipedia\n"
    "◾ Погода, курсы валют, математика, переводы\n"
    "◾ Браки, отношения, анкеты знакомств\n"
    "◾ Игры, предсказания, мини-развлечения\n"
    "◾ Экономика чата — монеты LMN, работа, казино\n"
    "◾ Полная модерация чата\n\n"
    "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"
    "📋 Анкета знакомств — команда <code>/анкета</code>"
)

def build_main_kb() -> InlineKeyboardMarkup:
    """Главная клавиатура /start — читает кастомные label/url из brand."""
    chat_label = brand.btn_label("main_chat")
    chat_url   = brand.btn_url("main_chat")
    chan_label  = brand.btn_label("main_channel")
    chan_url    = brand.btn_url("main_channel")
    help_label  = brand.btn_label("main_help")
    row1 = []
    if chat_url:
        row1.append(InlineKeyboardButton(text=chat_label, url=chat_url))
    if chan_url:
        row1.append(InlineKeyboardButton(text=chan_label, url=chan_url))
    rows = []
    if row1:
        rows.append(row1)
    rows.append([InlineKeyboardButton(text=help_label, callback_data="help:menu")])
    # Ссылка на сайт
    if LUMENA_SITE_URL:
        rows.append([InlineKeyboardButton(text="🌐 Сайт Лумены", url=LUMENA_SITE_URL)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.message(Command("start"), F.chat.type == "private")
async def cmd_start_private(msg: Message, command: CommandObject = None):
    uid  = msg.from_user.id
    raw_name = msg.from_user.first_name or "друг"
    name     = html.escape(raw_name)

    # V6: обработка реферального кода ?start=ref_UID
    if command and command.args and command.args.startswith("ref_"):
        try:
            referrer_uid = int(command.args[4:])
            if referrer_uid != uid and uid not in referrals:
                referrals[uid] = referrer_uid
                referral_counts[referrer_uid] = referral_counts.get(referrer_uid, 0) + 1
                add_balance(referrer_uid, 1000)
                award_xp(referrer_uid, 100)
                schedule_state_save("реферал")
                try:
                    ref_name_esc = html.escape(msg.from_user.full_name)
                    await bot.send_message(
                        referrer_uid,
                        f"🎉 <b>Новый реферал!</b>\n\n"
                        f"👤 <b>{ref_name_esc}</b> зарегистрировался по твоей ссылке\n"
                        f"💰 +1000 LMN · ✨ +100 XP",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
        except (ValueError, IndexError):
            pass

    if is_verified(uid):
        kb = build_main_kb()
        # Фаундеру добавляем кнопку редактора
        if is_owner(msg):
            kb = InlineKeyboardMarkup(inline_keyboard=
                kb.inline_keyboard +
                [[InlineKeyboardButton(text="🛠 Редактор", callback_data="editor:menu")]]
            )
        await _answer_custom(
            msg, "start_text",
            _START_TEXT.format(name=name),
            name=raw_name,
            reply_markup=kb,
        )
        return

    # Новый пользователь — сначала верификация
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=brand.btn_label("verify_start"),
            callback_data="verify:go",
        )]
    ])
    await _answer_custom(
        msg, "start_unverified",
        f"👋 <b>Привет, {name}!</b>\n\n"
        "Для доступа к боту нужно пройти быструю верификацию.\n"
        "Это займёт несколько секунд 👇",
        name=raw_name,
        reply_markup=kb,
    )


@dp.callback_query(F.data == "verify:go")
async def cb_verify_go(cb: CallbackQuery):
    uid = cb.from_user.id
    if is_verified(uid):
        await cb.answer("Ты уже верифицирован ✅", show_alert=False)
        return
    question, correct = _gen_captcha()
    _captcha_pending[uid] = correct
    kb = _captcha_keyboard(uid, correct)
    await _edit_custom(
        cb.message, "verify_prompt",
        f"🔐 <b>Верификация</b>\n\n"
        f"Реши пример:\n\n"
        f"<b>  {question}</b>\n\n"
        f"<i>Выбери правильный ответ ниже 👇</i>",
        reply_markup=kb,
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("captcha_ans:"))
async def cb_captcha_ans(cb: CallbackQuery):
    uid = cb.from_user.id
    parts = cb.data.split(":")
    if len(parts) != 3:
        return await cb.answer("Ошибка данных", show_alert=True)
    try:
        target_uid = int(parts[1])
        chosen     = int(parts[2])
    except ValueError:
        return await cb.answer("Ошибка данных", show_alert=True)

    # Нельзя нажимать чужую капчу
    if uid != target_uid:
        return await cb.answer("Это не твоя капча 👀", show_alert=True)

    correct = _captcha_pending.get(uid)
    if correct is None:
        # Капча устарела (бот перезапустился)
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔄 Получить новый пример", callback_data="verify:go")
        ]])
        await _edit_custom(
            cb.message, "verify_expired",
            "⏳ <b>Капча устарела.</b>\n\nНажми кнопку, чтобы получить новый пример.",
            reply_markup=kb,
        )
        return await cb.answer()

    if chosen != correct:
        # Неправильный ответ — сразу новый пример
        question, new_correct = _gen_captcha()
        _captcha_pending[uid] = new_correct
        kb = _captcha_keyboard(uid, new_correct)
        await _edit_custom(
            cb.message, "verify_wrong",
            f"❌ <b>Неверно!</b> Попробуй ещё раз.\n\n"
            f"Реши пример:\n\n"
            f"<b>  {question}</b>\n\n"
            f"<i>Выбери правильный ответ 👇</i>",
            reply_markup=kb,
        )
        return await cb.answer("Неверный ответ ❌", show_alert=False)

    # ✅ Правильный ответ
    _captcha_pending.pop(uid, None)
    raw_name = cb.from_user.first_name or "друг"
    name     = html.escape(raw_name)
    _verified_users.add(uid)
    save_data()

    site_line = (f"\n\n🌐 <a href=\"{LUMENA_SITE_URL}\">Офіційний сайт Лумени</a> — всі функції та правила"
                 if LUMENA_SITE_URL else "")
    await _edit_custom(
        cb.message, "verify_done",
        f"✅ <b>Верификация пройдена!</b>\n\n"
        f"Добро пожаловать, {name}! Все функции Лумены теперь доступны.{site_line}",
        name=raw_name,
    )
    await _answer_custom(
        cb.message, "start_text",
        _START_TEXT.format(name=name),
        name=raw_name,
        reply_markup=build_main_kb(),
    )
    await cb.answer("✅ Правильно!", show_alert=False)


@dp.message(Command("анкета", "anketa"))
async def cmd_anketa(msg: Message):
    if msg.chat.type != "private":
        return await _answer_custom(
            msg, "anketa_private_only",
            "💌 Анкету нужно заполнять в личных сообщениях с ботом!\n"
            "👉 Напиши мне в личку: @LumenarAi_Bot",
        )
    if not is_verified(msg.from_user.id):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=_btn_text("verify_btn", "✅ Пройти верификацию"),
                callback_data="verify:go",
            )]
        ])
        return await _answer_custom(
            msg, "anketa_no_verify",
            "🔒 Сначала пройди верификацию — нажми кнопку ниже.",
            reply_markup=kb,
        )
    await _ank.start_anketa(bot, msg, force=True)


@dp.message(Command("premium", "vip", "купить_премиум"))
async def cmd_buy_premium(msg: Message):
    """Покупка VIP-анкеты за 300 Stars."""
    uid = msg.from_user.id
    uname = (msg.from_user.username or "").lower()
    if is_anketa_premium(uid, uname):
        await msg.reply(
            "👑 *У тебя уже есть VIP-статус!*\n\n"
            "Твоя анкета будет опубликована как VIP-ANKETA с приоритетом.",
            parse_mode="Markdown"
        )
        return
    await bot.send_invoice(
        chat_id=uid,
        title="👑 VIP-ANKETA",
        description=(
            "VIP-статус для твоей анкеты:\n"
            "• Оформление 👑 VIP-ANKETA\n"
            "• Приоритетная публикация\n"
            "• Без ограничений по времени"
        ),
        payload="premium_anketa",
        currency="XTR",
        prices=[LabeledPrice(label="VIP-анкета", amount=ANKETA_PREMIUM_STARS)],
    )


@dp.pre_checkout_query()
async def on_pre_checkout(query):
    await query.answer(ok=True)


@dp.message(F.successful_payment)
async def on_successful_payment(msg: Message):
    if msg.successful_payment.invoice_payload == "premium_anketa":
        uid = msg.from_user.id
        _premium_users.add(uid)
        save_data()
        await _send_custom(
            msg.from_user.id, "vip_activated",
            f"{brand.hdr()}\n\n"
            f"{brand.crown()} <b>VIP-статус активирован!</b>\n\n"
            "Твоя следующая анкета будет опубликована как <b>VIP-ANKETA</b> с приоритетом!\n\n"
            f"{brand.div()}"
        )


@dp.message(Command("givepremium", "дать_премиум"))
async def cmd_give_premium(msg: Message, command: CommandObject):
    if not await is_admin(msg):
        return
    target = await get_user(msg, command)
    if not target:
        return await msg.reply("Ответь на сообщение или укажи ID/username.")
    _premium_users.add(target.id)
    save_data()
    tag = f"@{target.username}" if target.username else target.full_name
    await msg.reply(
        f"👑 *VIP выдан!*\n\n{tag} теперь имеет VIP-статус анкеты.",
        parse_mode="Markdown"
    )


@dp.message(Command("відмова", "отмена", "cancel"))
async def cmd_cancel_ank(msg: Message):
    if msg.chat.type == "private":
        uid = msg.from_user.id
        # Если редактор в сессии — сбрасываем
        if uid in _edit_sessions:
            _edit_sessions.pop(uid)
            return await msg.reply("✏️ Редактирование отменено.")
        if uid in _btn_edit_sessions:
            _btn_edit_sessions.pop(uid)
            return await msg.reply("✏️ Редактирование кнопки отменено.")
        if uid in support_sessions:
            del support_sessions[uid]
            await msg.reply("❌ Обращение отменено.")
            return
        await _ank.cancel_anketa(msg)


@dp.message(Command("setmodchat", "setmod"))
async def cmd_setmodchat(msg: Message):
    if not is_owner(msg):
        return await msg.reply("⛔ Тільки фаундер")
    _ank.set_mod_chat(msg.chat.id)
    _ank.save_anketa_settings()
    await msg.reply(
        f"✅ <b>Чат модерації анкет встановлено!</b>\n"
        f"🆔 ID: <code>{msg.chat.id}</code>\n\n"
        f"Сюди надходитимуть анкети на перевірку.",
        parse_mode="HTML"
    )


@dp.message(Command("setpubchat", "setpub"))
async def cmd_setpubchat(msg: Message):
    if not is_owner(msg):
        return await msg.reply("⛔ Тільки фаундер")
    _ank.set_pub_chat(msg.chat.id)
    _ank.save_anketa_settings()
    await msg.reply(
        f"✅ <b>Чат публікацій анкет встановлено!</b>\n"
        f"🆔 ID: <code>{msg.chat.id}</code>\n\n"
        f"Сюди публікуватимуться схвалені анкети.",
        parse_mode="HTML"
    )


@dp.message(Command("resetpubchat"))
async def cmd_resetpubchat(msg: Message):
    """Скидає чат публікацій анкет."""
    if not is_owner(msg):
        return await msg.reply("⛔ Тільки фаундер")
    _ank.set_pub_chat(None)
    _ank.save_anketa_settings()
    await msg.reply(
        "🔄 <b>Чат публікацій анкет скинуто.</b>\n\n"
        "Тепер виконай <code>/setpubchat</code> у потрібному чаті.",
        parse_mode="HTML"
    )


@dp.message(Command("setemoji"))
async def cmd_setemoji(msg: Message):
    """Устанавливает Premium emoji ID для заголовков бота. Только фаундер."""
    if not is_owner(msg):
        return
    parts = (msg.text or "").split(maxsplit=1)
    arg   = parts[1].strip() if len(parts) > 1 else ""
    if not arg:
        pack_name = brand.get_pack_name() or "не задан"
        ids       = brand.get_pack()
        cur_txt   = (
            f"Текущий пак: <code>{html.escape(pack_name)}</code> ({len(ids)} emoji)\n"
            f"Превью: {brand.preview(8)}\n\n"
        ) if ids else "Пак не загружен. Используй /setemojipack.\n\n"
        return await msg.reply(
            f"{cur_txt}"
            "<b>Команды управления паком:</b>\n"
            "<code>/setemojipack adaptiveqp_by_emsetbot</code> — загрузить пак\n"
            "<code>/setemoji reset</code> — сбросить пак\n\n"
            "Чтобы узнать ID отдельного emoji — отправь его мне в личку.",
            parse_mode="HTML"
        )
    if arg == "reset":
        brand.set_pack([], "")
        save_data()
        return await msg.reply(
            "🔄 Emoji пак сброшен. Бот вернулся к стандартным символам 🖤",
            parse_mode="HTML"
        )
    # Одиночный ID — устанавливаем как header emoji (роль 0)
    if arg.isdigit():
        ids = brand.get_pack()
        if ids:
            ids[0] = arg
        else:
            ids = [arg]
        brand.set_pack(ids, brand.get_pack_name())
        save_data()
        return await msg.reply(
            f"✅ Header emoji обновлён!\n\n"
            f"Превью: {brand.hdr()}\n{brand.div()}",
            parse_mode="HTML"
        )
    await msg.reply("❓ Неизвестная команда. Используй /setemojipack для загрузки пака.", parse_mode="HTML")


@dp.message(
    F.chat.type == "private",
    F.entities,
    # пропускаем команды (иначе /edittext и др. не дойдут до своих хендлеров)
    # пропускаем, если фаундер сейчас в сессии редактирования текста
    F.func(lambda m: (
        not any(e.type == "bot_command" for e in (m.entities or []))
        and (m.from_user is None or m.from_user.id not in _edit_sessions)
        and (m.from_user is None or m.from_user.id not in _btn_edit_sessions)
    ))
)
async def handle_emoji_extract(msg: Message):
    """Извлекает ID Premium/custom emoji из сообщения — только для фаундера.
    Один emoji → одразу зберігається як header.
    Кілька → показує список з кнопками для вибору.
    """
    if not is_owner(msg):
        return
    if _ank.is_on_media_step(msg.from_user.id):
        return
    entities = msg.entities or []
    found = [(msg.text[e.offset: e.offset + e.length], e.custom_emoji_id)
             for e in entities if e.type == "custom_emoji" and e.custom_emoji_id]
    if not found:
        return

    if len(found) == 1:
        # ── Один emoji — одразу встановлюємо як header ───────
        char, eid = found[0]
        ids = brand.get_pack()
        if ids:
            ids[0] = eid
        else:
            ids = [eid]
        brand.set_pack(ids, brand.get_pack_name())
        save_data()
        await msg.reply(
            f"✅ <b>Header emoji збережено!</b>\n\n"
            f"Emoji: <tg-emoji emoji-id=\"{eid}\">{html.escape(char)}</tg-emoji>  "
            f"<code>{eid}</code>\n\n"
            f"Превью: {brand.hdr()}\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )
    else:
        # ── Кілька emoji — показуємо список з кнопками ───────
        lines = ["🔍 <b>Знайдені Custom Emoji:</b>\n"]
        buttons = []
        for i, (char, eid) in enumerate(found):
            lines += [
                f"[{i}] <tg-emoji emoji-id=\"{eid}\">{html.escape(char)}</tg-emoji>  "
                f"<code>{eid}</code>",
            ]
            buttons.append([InlineKeyboardButton(
                text=f"[{i}] Встановити як header",
                callback_data=f"setemoji_hdr:{eid}",
            )])
        lines.append("\nНатисни кнопку щоб встановити потрібний як header emoji:")
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await msg.reply("\n".join(lines), parse_mode="HTML", reply_markup=kb)


@dp.callback_query(F.data.startswith("setemoji_hdr:"))
async def cb_setemoji_hdr(cb: CallbackQuery):
    """Встановлює вибраний emoji як header."""
    if not is_owner(cb):
        return await cb.answer("Тільки фаундер", show_alert=True)
    eid = cb.data.split(":", 1)[1]
    ids = brand.get_pack()
    if ids:
        ids[0] = eid
    else:
        ids = [eid]
    brand.set_pack(ids, brand.get_pack_name())
    save_data()
    await cb.message.edit_text(
        f"✅ <b>Header emoji збережено!</b>\n\n"
        f"<code>{eid}</code>\n\n"
        f"Превью: {brand.hdr()}\n"
        f"{brand.div()}",
        parse_mode="HTML",
        reply_markup=None,
    )
    await cb.answer("Збережено ✅")


@dp.message(F.func(lambda m: m.from_user is not None
                   and m.from_user.id in _edit_sessions
                   and not (m.text or "").startswith("/")))
async def handle_founder_edit_text(msg: Message):
    """Сохраняет кастомный текст от фаундера для редактируемого ключа."""
    uid = msg.from_user.id
    key = _edit_sessions.pop(uid, None)
    if not key:
        return

    raw_text = msg.text or msg.caption or ""
    if not raw_text.strip():
        _edit_sessions[uid] = key
        return await msg.reply("❌ Пустое сообщение — отправь текст (с Premium emoji).")

    raw_ents = msg.entities or msg.caption_entities or []
    ents_data = []
    for e in raw_ents:
        d: dict = {"type": e.type, "offset": e.offset, "length": e.length}
        if getattr(e, "url",            None): d["url"]            = e.url
        if getattr(e, "language",       None): d["language"]       = e.language
        if getattr(e, "custom_emoji_id",None): d["custom_emoji_id"]= e.custom_emoji_id
        ents_data.append(d)

    has_custom_emoji_saved = any(d.get("type") == "custom_emoji" for d in ents_data)
    brand.set_custom_text(key, raw_text, ents_data)
    brand_saved = await brand.persist_brand_now()

    label = brand.TEXT_LABELS.get(key, key)
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛠 Открыть редактор", callback_data="editor:menu")]
    ])

    emoji_warning = (
        "\n\n⚠️ <b>Важно про Premium emoji:</b>\n"
        "Боты НЕ могут отправлять анимированные emoji из личных Telegram Premium паков. "
        "Работают только emoji из bot-owned emoji паков (созданных через @Stickers для бота). "
        "Статичный юникод (😊🔥✨) работает всегда.\n"
        if has_custom_emoji_saved else ""
    )

    await msg.reply(
        (
            f"✅ <b>{html.escape(label)}</b> — сохранён!\n\n"
            +
            "Текст та форматування записані в PostgreSQL.\n"
            if brand_saved else
            f"✅ <b>{html.escape(label)}</b> — сохранён!\n\n"
            "Текст збережено локально; PostgreSQL недоступний, автосинхронізація повторить запис.\n"
        )
        + emoji_warning
        + f"\n<code>/resettext {key}</code> — сбросить к дефолту.",
        parse_mode="HTML",
        reply_markup=back_kb,
    )


@dp.message(Command("edittext"))
async def cmd_edittext(msg: Message):
    """Редактор текстов бота — только для фаундера в ЛС."""
    if not is_owner(msg) or msg.chat.type != "private":
        return

    custom = brand.all_custom_texts()
    total  = sum(len(keys) for _, keys in _EDITOR_TEXT_CATEGORIES)
    done   = sum(1 for _, keys in _EDITOR_TEXT_CATEGORIES for k in keys if k in custom)

    await msg.answer(
        f"✏️ <b>Редактор текстов Лумены</b>\n\n"
        f"📊 Изменено: <b>{done}</b> из <b>{total}</b> строк\n"
        f"📂 Категорий: <b>{len(_EDITOR_TEXT_CATEGORIES)}</b>\n\n"
        "Выбери категорию — внутри каждой постраничный список.\n"
        "Тапни строку → отправь новый текст с Premium emoji.\n\n"
        "✅ — кастомный   ⬜ — дефолт\n"
        "<code>/resettext ключ</code> — сбросить одну строку к дефолту",
        parse_mode="HTML",
        reply_markup=_editor_texts_kb(),
    )


@dp.callback_query(F.data.startswith("edittext:"))
async def cb_edittext(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    key = cb.data.split(":", 1)[1]
    if key not in brand.TEXT_LABELS:
        return await cb.answer("Неизвестный ключ", show_alert=True)

    _edit_sessions[cb.from_user.id] = key
    label    = brand.TEXT_LABELS[key]
    ct       = brand.get_custom_text(key)
    cur_text = brand.get_current_text(key)   # кастомный ИЛИ дефолт

    if ct:
        status_line = "📝 <b>Сейчас (кастомный):</b>"
    elif cur_text:
        status_line = "⬜ <b>Сейчас (дефолт):</b>"
    else:
        status_line = "⬜ <i>Текст не задан</i>"

    back_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отмена", callback_data="reply_edit_cancel"),
    ]])

    # Если есть custom_emoji entities — превью нельзя вставить в HTML-строку,
    # отправляем его отдельным сообщением с entities=, чтобы premium emoji были видны
    cts_data = ct  # tuple (text, entities) или None
    has_custom_emoji_preview = (
        cts_data is not None
        and any(e.get("type") == "custom_emoji" for e in (cts_data[1] or []))
    )

    if has_custom_emoji_preview:
        preview_note = "👁 <b>Текущее значение показано выше</b> (с Premium emoji)\n\n"
        try:
            _preview_ents = _build_entities(cts_data[1])
            await cb.message.answer(
                cts_data[0][:300] + ("…" if len(cts_data[0]) > 300 else ""),
                entities=_preview_ents or None,
            )
        except Exception:
            preview_note = f"<blockquote>{html.escape((cur_text or '')[:300])}</blockquote>\n\n"
    else:
        preview_note = (f"<blockquote>{html.escape(cur_text[:300])}</blockquote>\n\n"
                        if cur_text else "\n")

    await cb.message.answer(
        f"✏️ <b>{html.escape(label)}</b>\n\n"
        f"{status_line}\n"
        + preview_note
        + "Отправь новый текст — форматирование и Premium emoji сохранятся.\n"
        "<code>/отмена</code> — выйти без сохранения.",
        parse_mode="HTML",
        reply_markup=back_kb,
    )
    await cb.answer()


@dp.message(Command("resettext"))
async def cmd_resettext(msg: Message):
    """Сброс кастомного текста к дефолту — только для фаундера."""
    if not is_owner(msg) or msg.chat.type != "private":
        return
    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) < 2:
        keys_list = ", ".join(f"<code>{k}</code>" for k in brand.TEXT_LABELS)
        return await msg.reply(
            f"Использование: <code>/resettext ключ</code>\n\nКлючи:\n{keys_list}",
            parse_mode="HTML"
        )
    key = parts[1].strip()
    if key not in brand.TEXT_LABELS:
        return await msg.reply(f"❓ Ключ <code>{html.escape(key)}</code> не найден.", parse_mode="HTML")
    brand.del_custom_text(key)
    saved = await brand.persist_brand_now()
    await msg.reply(
        f"🔄 <b>{html.escape(brand.TEXT_LABELS[key])}</b> — сброшен к дефолту."
        + ("" if saved else "\n\n⚠️ PostgreSQL недоступний: зміна поки є лише локально."),
        parse_mode="HTML"
    )


# ═══════════════════════════════════════════════════════
# КОМАНДА «ИЗМЕНИТЬ» — полный редактор контента бота
# Доступно: фаундеру и @veroniksssxa (только в ЛС)
# ═══════════════════════════════════════════════════════

_EDITOR_TEXT_CATEGORIES = [
    ("🏠 Главный экран",    ["start_text", "start_unverified"]),
    ("✅ Верификация",       ["verify_btn", "verify_prompt", "verify_confirm_btn", "verify_done"]),
    ("👋 Приветствие",       ["welcome_msg", "welcome_btn"]),
    ("📝 Анкета — флоу",    ["anketa_start", "anketa_cancel", "anketa_confirm",
                              "anketa_duplicate", "anketa_cancel_none",
                              "anketa_private_only", "anketa_no_verify", "step_accepted",
                              "anketa_no_mod", "anketa_media_prompt",
                              "anketa_media_added", "anketa_media_done"]),
    ("🛡 Модерация анкет",  ["anketa_approve", "anketa_reject", "anketa_delete",
                              "mod_comment", "revoke_notify"]),
    ("👑 VIP & Поддержка",  ["vip_activated", "support_prompt", "support_sent"]),
    ("💰 Экономика",         ["balance", "work", "work_cooldown",
                              "fish", "fish_cooldown",
                              "give", "give_no_reply", "give_no_funds",
                              "give_self", "give_zero", "give_bot",
                              "casino_win", "casino_jackpot", "casino_lose",
                              "casino_no_bet", "casino_no_balance",
                              "casino_invalid_bet", "casino_negative_bet",
                              "slots_no_bet", "slots_no_balance", "slots_invalid_bet",
                              "rob_success", "rob_fail", "rob_cooldown",
                              "rob_no_reply", "rob_self", "rob_bot",
                              "rob_target_poor", "rob_victim_notify", "rob_banked",
                              "coin_rain", "coin_rain_collected"]),
    ("🏦 Банк",              ["bank_header", "bank_deposit_done", "bank_deposit_no_funds",
                              "bank_deposit_zero", "bank_withdraw_done",
                              "bank_withdraw_no_funds", "bank_withdraw_zero",
                              "bank_withdraw_cooldown"]),
    ("💍 Брак",              ["marry_proposal", "marry_accept", "marry_reject",
                              "marry_self", "marry_already", "marry_already_other",
                              "marry_no_reply", "marry_timeout",
                              "divorce", "divorce_not_married"]),
    ("🔥 Стрики & Аура",    ["checkin", "checkin_already", "checkin_milestone",
                              "upvote", "downvote", "rep", "aura_show"]),
    ("🎮 Игры",              ["rps_win", "rps_lose", "rps_tie",
                              "roulette_join", "roulette_winner",
                              "roulette_already", "roulette_join_msg",
                              "roulette_not_enough", "roulette_result",
                              "coin", "coin_heads", "coin_tails",
                              "hangman_start", "hangman_win", "hangman_lose",
                              "hangman_no_game", "hangman_letter_used",
                              "hangman_wrong", "hangman_right",
                              "game_dice", "game_roll", "game_choose",
                              "game_rate", "game_truth", "game_dare",
                              "game_riddle", "game_random"]),
    ("🤗 Социальные",        ["hug", "kiss", "gift", "slap", "pat",
                              "dance", "bite", "poke", "wave", "highfive",
                              "facepalm", "serenade"]),
    ("🛡 Модерация чата",   ["mute_done", "ban_done", "unban_done", "unmute_done",
                              "kick_done", "warn_done", "warn_ban", "unwarn_done",
                              "unwarn_no_warns",
                              "mute_self", "ban_self", "kick_self",
                              "admin_only", "reply_needed", "owner_only"]),
    ("🔮 Предсказания",     ["fortune_result", "horoscope_result", "tarot_result",
                              "fortune_destiny", "fortune_superpower", "fortune_profession",
                              "fortune_animal", "fortune_movie", "fortune_book",
                              "fortune_advice", "fortune_motivation", "fortune_myth",
                              "fortune_country", "fortune_color", "fortune_joke",
                              "fortune_compliment", "fortune_roast",
                              "fortune_8ball", "fortune_predict"]),
    ("🛒 Магазин & Інвентар", ["shop_header", "shop_coming_soon",
                                "inventory_header", "inventory_empty"]),
    ("ℹ️ Інфо",               ["info_project"]),
    ("👤 Профиль & Рейтинги", ["profile_no_bio", "profile_no_partner", "info_founder_badge",
                                "profile_header", "profile_bio_label",
                                "profile_balance_label", "profile_streak_label",
                                "profile_rep_label", "profile_marry_label", "profile_id_label",
                                "richest_header", "richest_empty", "richest_total",
                                "top_rep_header", "top_checkin_header"]),
]

_PAGE_SIZE = 8  # строк на страницу в категории


def _editor_main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Тексты",     callback_data="editor:texts"),
            InlineKeyboardButton(text="🔘 Кнопки",     callback_data="editor:btns"),
        ],
        [
            InlineKeyboardButton(text="🎨 Оформление", callback_data="editor:style"),
            InlineKeyboardButton(text="ℹ️ О проекте",  callback_data="editor:info_project"),
        ],
    ])


def _editor_style_kb() -> InlineKeyboardMarkup:
    """Список редактируемых параметров оформления."""
    rows = []
    for key, df in brand.STYLE_DEFS.items():
        status = "✅" if brand.is_style_customized(key) else "⬜"
        cur    = brand.get_style(key)
        rows.append([InlineKeyboardButton(
            text=f"{status} {df['desc']}: {cur[:20]}",
            callback_data=f"editor:style_edit:{key}",
        )])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="editor:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _editor_style_detail_kb(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Изменить",  callback_data=f"editor:style_input:{key}"),
            InlineKeyboardButton(text="🔄 Сбросить",  callback_data=f"editor:style_reset:{key}"),
        ],
        [InlineKeyboardButton(text="◀️ К оформлению", callback_data="editor:style")],
    ])


def _editor_texts_kb() -> InlineKeyboardMarkup:
    """Кнопки категорий текстов — 2 в ряд."""
    custom = brand.all_custom_texts()
    rows = []
    for i, (cat_name, cat_keys) in enumerate(_EDITOR_TEXT_CATEGORIES):
        done  = sum(1 for k in cat_keys if k in custom)
        total = len(cat_keys)
        label = f"{cat_name} ({done}/{total})" if done else cat_name
        rows.append([InlineKeyboardButton(text=label, callback_data=f"editor:cat:{i}:0")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="editor:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _editor_cat_kb(cat_idx: int, page: int = 0) -> InlineKeyboardMarkup:
    """Кнопки текстов в категории с пагинацией."""
    _, keys = _EDITOR_TEXT_CATEGORIES[cat_idx]
    valid_keys = [k for k in keys if k in brand.TEXT_LABELS]
    custom = brand.all_custom_texts()

    start  = page * _PAGE_SIZE
    end    = start + _PAGE_SIZE
    page_keys = valid_keys[start:end]
    total_pages = max(1, (len(valid_keys) + _PAGE_SIZE - 1) // _PAGE_SIZE)

    btns = []
    for k in page_keys:
        status = "✅" if k in custom else "⬜"
        short  = brand.TEXT_LABELS[k][:26]
        btns.append(InlineKeyboardButton(
            text=f"{status} {short}",
            callback_data=f"edittext:{k}",
        ))
    rows = [btns[i:i+2] for i in range(0, len(btns), 2)]

    # Навигация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"editor:cat:{cat_idx}:{page-1}"))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"editor:cat:{cat_idx}:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="◀️ Категории", callback_data="editor:texts")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _editor_btns_kb() -> InlineKeyboardMarkup:
    """Кнопки для редактирования кнопок бота."""
    rows = []
    for key, df in brand.BUTTON_DEFS.items():
        status = "✅" if brand.is_btn_customized(key) else "⬜"
        short  = df["desc"][:28]
        rows.append([InlineKeyboardButton(
            text=f"{status} {short}",
            callback_data=f"editor:btn:{key}",
        )])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="editor:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _editor_btn_detail_kb(key: str) -> InlineKeyboardMarkup:
    df = brand.BUTTON_DEFS.get(key, {})
    is_url_btn = df.get("type") == "url"
    btns_row = [InlineKeyboardButton(text="✏️ Изм. название", callback_data=f"editor:btn_label:{key}")]
    if is_url_btn:
        btns_row.append(InlineKeyboardButton(text="🔗 Изм. ссылку", callback_data=f"editor:btn_url:{key}"))
    rows = [
        btns_row,
        [
            InlineKeyboardButton(text="🔄 Сбросить",       callback_data=f"editor:btn_reset:{key}"),
            InlineKeyboardButton(text="◀️ К кнопкам",      callback_data="editor:btns"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _send_editor_menu(msg):
    """Отправляет главное меню редактора (используется из нескольких мест)."""
    await msg.answer(
        f"{brand.hdr()}\n\n"
        "🛠 <b>Настройки Лумены</b>\n\n"
        "Выбери раздел:\n"
        "✏️ <b>Тексты</b> — все фразы и сообщения бота\n"
        "🔘 <b>Кнопки</b> — названия и ссылки кнопок\n"
        "🎨 <b>Оформление</b> — заголовок, разделитель, буллеты",
        parse_mode="HTML",
        reply_markup=_editor_main_menu_kb(),
    )


# ── Reply-редактор: фаундер отвечает на сообщение бота словом «изменить» ──────
# Регистрируется ПЕРВЫМ — более специфичный фильтр (reply + tracked msg)
def _is_reply_edit(m) -> bool:
    """True если: фаундер, слово «изменить»/«edit», ответ на сообщение бота.
    Не требует трекинга — ловит ответ на ЛЮБОЕ сообщение от бота."""
    if not is_owner(m):
        return False
    tl = (m.text or "").strip().lower().lstrip("/")
    if tl not in ("изменить", "edit"):
        return False
    rm = m.reply_to_message
    if not rm or not rm.from_user:
        return False
    # Сообщение должно быть от самого бота
    return rm.from_user.id == _BOT_ID


@dp.message(F.func(_is_reply_edit))
async def cmd_reply_edit(msg: Message):
    """Фаундер ответил на сообщение бота словом «изменить» → начать редактирование."""
    if not is_owner(msg):
        return  # тихо игнорируем
    rm = msg.reply_to_message

    # Пытаемся найти ключ по трекингу (работает только если бот не перезапускался)
    key = _tracked_bot_msgs.get((msg.chat.id, rm.message_id))

    # Если трекинг пуст — пробуем найти ключ по тексту сообщения
    if not key and rm.text:
        rm_text_stripped = rm.text.strip()
        for k, custom in brand.all_custom_texts().items():
            if k in brand.TEXT_LABELS and custom[0].strip() == rm_text_stripped:
                key = k
                break

    is_private = msg.chat.type == "private"

    if key and key in brand.TEXT_LABELS:
        # Ключ найден — открываем редактирование конкретного текста
        _edit_sessions[msg.from_user.id] = key
        label = brand.TEXT_LABELS[key]
        ct    = brand.get_custom_text(key)
        current_note = (
            f"Текущий текст:\n<blockquote>{html.escape(ct[0])}</blockquote>"
            if ct else "Сейчас: <i>встроенный дефолтный текст</i>"
        )
        back_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Отмена", callback_data="reply_edit_cancel"),
        ]])

        if is_private:
            await msg.reply(
                f"✏️ <b>{html.escape(label)}</b>\n\n"
                f"{current_note}\n\n"
                "Отправь новый текст — форматирование сохранится.\n"
                "/отмена или кнопка ниже — выйти без сохранения.",
                parse_mode="HTML",
                reply_markup=back_kb,
            )
        else:
            # В группе — просим зайти в ЛС (сессия уже открыта)
            dm_kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="✏️ Написать новый текст в ЛС",
                    url=f"https://t.me/{_BOT_USERNAME}",
                ),
            ]])
            await msg.reply(
                f"✏️ <b>{html.escape(label)}</b>\n\n"
                f"{current_note}\n\n"
                "Напиши новый текст мне <b>в личку</b> — нажми кнопку.\n"
                "Редактирование уже активировано.",
                parse_mode="HTML",
                reply_markup=dm_kb,
            )
    else:
        # Ключ не определён — открываем общее меню редактора
        await _send_editor_menu(msg)


@dp.callback_query(F.data == "reply_edit_cancel")
async def cb_reply_edit_cancel(cb: CallbackQuery):
    _edit_sessions.pop(cb.from_user.id, None)
    await cb.message.edit_text("❌ Редактирование отменено.", parse_mode="HTML")
    await cb.answer()


# /edit — латиница. is_owner вынесен В ФИЛЬТР и дублируется в теле
# (TEXT_COMMANDS диспетчер викликає без фільтра — потрібна перевірка в тілі)
@dp.message(Command("edit", "настройки", "settings"),
            F.chat.type == "private",
            F.func(lambda m: is_owner(m)))
async def cmd_editor_latin(msg: Message):
    if not is_owner(msg):
        return
    await _send_editor_menu(msg)


# Регистрируем после определения функции
TEXT_COMMANDS.update({
    "настройки": cmd_editor_latin,
    "settings":  cmd_editor_latin,
})


# «изменить» / «/изменить» — кириллица без reply: открываем общее меню.
# is_owner тоже в фильтре.
@dp.message(F.chat.type == "private",
            F.func(lambda m: is_owner(m)
                   and (m.text or "").strip().lower().lstrip("/") in ("изменить", "edit")
                   and not m.reply_to_message))
async def cmd_editor_ru(msg: Message):
    if not is_owner(msg):
        return  # тихо игнорируем — не показываем ошибку
    await _send_editor_menu(msg)


@dp.callback_query(F.data == "editor:menu")
async def cb_editor_menu(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    await cb.message.edit_text(
        f"{brand.hdr()}\n\n"
        "🛠 <b>Настройки Лумены</b>\n\n"
        "Выбери раздел:\n"
        "✏️ <b>Тексты</b> — все фразы и сообщения бота\n"
        "🔘 <b>Кнопки</b> — названия и ссылки кнопок\n"
        "🎨 <b>Оформление</b> — заголовок, разделитель, буллеты",
        parse_mode="HTML",
        reply_markup=_editor_main_menu_kb(),
    )
    await cb.answer()


@dp.callback_query(F.data == "editor:info_project")
async def cb_editor_info_project(cb: CallbackQuery):
    """Прямой переход к редактированию текста «О проекте» из главного меню."""
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    uid = cb.from_user.id
    _edit_sessions[uid] = "info_project"
    ct = brand.get_custom_text("info_project")
    current_note = (
        f"Текущий текст:\n<blockquote>{html.escape(ct[0])}</blockquote>"
        if ct else "Сейчас: <i>стандартный текст /info</i>"
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад в меню", callback_data="editor:menu"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="reply_edit_cancel"),
    ]])
    await cb.message.edit_text(
        "ℹ️ <b>Описание проекта (/info)</b>\n\n"
        f"{current_note}\n\n"
        "Отправь новый текст — форматирование и Premium Emoji сохранятся.\n"
        "Изменение сразу увидят все участники.",
        parse_mode="HTML",
        reply_markup=back_kb,
    )
    await cb.answer()


@dp.callback_query(F.data == "editor:texts")
async def cb_editor_texts(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    custom = brand.all_custom_texts()
    total  = sum(len(keys) for _, keys in _EDITOR_TEXT_CATEGORIES)
    done   = sum(1 for _, keys in _EDITOR_TEXT_CATEGORIES
                 for k in keys if k in custom)
    await cb.message.edit_text(
        f"✏️ <b>Тексты бота</b>\n\n"
        f"Изменено: <b>{done}</b> из <b>{total}</b> строк\n\n"
        "Выбери категорию:",
        parse_mode="HTML",
        reply_markup=_editor_texts_kb(),
    )
    await cb.answer()


@dp.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()


@dp.callback_query(F.data.startswith("editor:cat:"))
async def cb_editor_cat(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    try:
        parts   = cb.data.split(":")
        cat_idx = int(parts[2])
        page    = int(parts[3]) if len(parts) > 3 else 0
    except (ValueError, IndexError):
        return await cb.answer("Ошибка", show_alert=True)
    if cat_idx >= len(_EDITOR_TEXT_CATEGORIES):
        return await cb.answer("Ошибка", show_alert=True)

    cat_name, keys = _EDITOR_TEXT_CATEGORIES[cat_idx]
    valid_keys  = [k for k in keys if k in brand.TEXT_LABELS]
    custom      = brand.all_custom_texts()
    total_pages = max(1, (len(valid_keys) + _PAGE_SIZE - 1) // _PAGE_SIZE)
    page        = max(0, min(page, total_pages - 1))
    start       = page * _PAGE_SIZE
    page_keys   = valid_keys[start:start + _PAGE_SIZE]

    lines = [
        f"✏️ <b>{html.escape(cat_name)}</b>",
        f"<i>Стр. {page+1}/{total_pages} · {len(valid_keys)} строк</i>",
        "✅ кастомный   ⬜ дефолт\n",
    ]
    for k in page_keys:
        status   = "✅" if k in custom else "⬜"
        label    = html.escape(brand.TEXT_LABELS[k])
        cur_text = brand.get_current_text(k)
        preview  = html.escape(cur_text[:60].replace("\n", " ")) + ("…" if len(cur_text) > 60 else "")
        lines.append(f"  {status} <b>{label}</b>")
        if preview:
            lines.append(f"      <i>{preview}</i>")

    await cb.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=_editor_cat_kb(cat_idx, page),
    )
    await cb.answer()


@dp.callback_query(F.data == "editor:btns")
async def cb_editor_btns(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    lines = ["🔘 <b>Кнопки бота</b>\n",
             "✅ — изменена   ⬜ — стандартная\n"]
    for key, df in brand.BUTTON_DEFS.items():
        status     = "✅" if brand.is_btn_customized(key) else "⬜"
        cur_label  = html.escape(brand.btn_label(key))
        lines.append(f"  {status} <b>{html.escape(df['desc'])}</b>: {cur_label}")
    await cb.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=_editor_btns_kb(),
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("editor:btn:"))
async def cb_editor_btn_detail(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    key = cb.data.split(":", 2)[-1]
    if key not in brand.BUTTON_DEFS:
        return await cb.answer("Неизвестная кнопка", show_alert=True)
    df         = brand.BUTTON_DEFS[key]
    cur_label  = html.escape(brand.btn_label(key))
    cur_url    = brand.btn_url(key)
    is_url_btn = df.get("type") == "url"
    lines = [
        f"🔘 <b>{html.escape(df['desc'])}</b>\n",
        f"Название: <b>{cur_label}</b>",
    ]
    if is_url_btn:
        lines.append(f"Ссылка: <code>{html.escape(cur_url or '—')}</code>")
    if brand.is_btn_customized(key):
        lines.append("\n<i>Изменена относительно дефолта.</i>")
    await cb.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=_editor_btn_detail_kb(key),
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("editor:btn_label:"))
async def cb_editor_btn_label(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    key = cb.data.split(":", 2)[-1]
    if key not in brand.BUTTON_DEFS:
        return await cb.answer("Неизвестная кнопка", show_alert=True)
    _btn_edit_sessions[cb.from_user.id] = {"key": key, "step": "label"}
    cur = html.escape(brand.btn_label(key))
    await cb.message.answer(
        f"✏️ <b>Новое название кнопки</b>\n\n"
        f"Сейчас: <b>{cur}</b>\n\n"
        "Отправь новый текст кнопки.\n"
        "/отмена — выйти без сохранения.",
        parse_mode="HTML",
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("editor:btn_url:"))
async def cb_editor_btn_url(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    key = cb.data.split(":", 2)[-1]
    df  = brand.BUTTON_DEFS.get(key, {})
    if df.get("type") != "url":
        return await cb.answer("Эта кнопка без ссылки", show_alert=True)
    _btn_edit_sessions[cb.from_user.id] = {"key": key, "step": "url"}
    cur = html.escape(brand.btn_url(key) or "не задана")
    await cb.message.answer(
        f"🔗 <b>Новая ссылка кнопки</b>\n\n"
        f"Сейчас: <code>{cur}</code>\n\n"
        "Отправь новую ссылку (https://...).\n"
        "/отмена — выйти без сохранения.",
        parse_mode="HTML",
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("editor:btn_reset:"))
async def cb_editor_btn_reset(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    key = cb.data.split(":", 2)[-1]
    if key not in brand.BUTTON_DEFS:
        return await cb.answer("Неизвестная кнопка", show_alert=True)
    brand.reset_custom_button(key)
    saved = await brand.persist_brand_now()
    df = brand.BUTTON_DEFS[key]
    await cb.answer(
        f"🔄 «{df['desc']}» сброшена к дефолту"
        if saved else "⚠️ Зміна локальна: PostgreSQL недоступний",
        show_alert=True,
    )
    # Обновляем сообщение
    lines = ["🔘 <b>Кнопки бота</b>\n",
             "✅ — изменена   ⬜ — стандартная\n"]
    for k, d in brand.BUTTON_DEFS.items():
        status    = "✅" if brand.is_btn_customized(k) else "⬜"
        cur_label = html.escape(brand.btn_label(k))
        lines.append(f"  {status} <b>{html.escape(d['desc'])}</b>: {cur_label}")
    await cb.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=_editor_btns_kb(),
    )


@dp.callback_query(F.data == "editor:style")
async def cb_editor_style(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    lines = ["🎨 <b>Оформление бота</b>\n",
             "✅ — изменено   ⬜ — стандартное\n"]
    for key, df in brand.STYLE_DEFS.items():
        status = "✅" if brand.is_style_customized(key) else "⬜"
        cur    = html.escape(brand.get_style(key))
        lines.append(f"  {status} <b>{html.escape(df['desc'])}</b>: <code>{cur}</code>")
    lines.append(f"\n{brand.div()}")
    lines.append(f"Заголовок: {brand.hdr()}")
    await cb.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=_editor_style_kb(),
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("editor:style_edit:"))
async def cb_editor_style_detail(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    key = cb.data.split(":", 2)[-1]
    if key not in brand.STYLE_DEFS:
        return await cb.answer("Неизвестный параметр", show_alert=True)
    df  = brand.STYLE_DEFS[key]
    cur = html.escape(brand.get_style(key))
    status = "✅ изменено" if brand.is_style_customized(key) else "⬜ стандартное"
    await cb.message.edit_text(
        f"🎨 <b>{html.escape(df['desc'])}</b>\n\n"
        f"Статус: {status}\n"
        f"Сейчас: <code>{cur}</code>\n\n"
        f"<i>{html.escape(df['hint'])}</i>",
        parse_mode="HTML",
        reply_markup=_editor_style_detail_kb(key),
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("editor:style_input:"))
async def cb_editor_style_input(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    key = cb.data.split(":", 2)[-1]
    if key not in brand.STYLE_DEFS:
        return await cb.answer("Неизвестный параметр", show_alert=True)
    df = brand.STYLE_DEFS[key]
    _style_edit_sessions[cb.from_user.id] = key
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"editor:style_edit:{key}"),
    ]])
    await cb.message.answer(
        f"✏️ <b>{html.escape(df['desc'])}</b>\n\n"
        f"Сейчас: <code>{html.escape(brand.get_style(key))}</code>\n\n"
        f"<i>{html.escape(df['hint'])}</i>\n\n"
        "Отправь новое значение:",
        parse_mode="HTML",
        reply_markup=cancel_kb,
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("editor:style_reset:"))
async def cb_editor_style_reset(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    key = cb.data.split(":", 2)[-1]
    if key not in brand.STYLE_DEFS:
        return await cb.answer("Неизвестный параметр", show_alert=True)
    brand.reset_style(key)
    saved = await brand.persist_brand_now()
    df = brand.STYLE_DEFS[key]
    await cb.answer(
        f"🔄 «{df['desc']}» сброшено к дефолту"
        if saved else "⚠️ Зміна локальна: PostgreSQL недоступний",
        show_alert=False,
    )
    # обновить экран детали
    cur = html.escape(brand.get_style(key))
    await cb.message.edit_text(
        f"🎨 <b>{html.escape(df['desc'])}</b>\n\n"
        f"Статус: ⬜ стандартное\n"
        f"Сейчас: <code>{cur}</code>\n\n"
        f"<i>{html.escape(df['hint'])}</i>",
        parse_mode="HTML",
        reply_markup=_editor_style_detail_kb(key),
    )


@dp.message(F.chat.type == "private",
            F.func(lambda m: m.from_user is not None
                   and m.from_user.id in _style_edit_sessions
                   and not (m.text or "").startswith("/")))
async def handle_style_edit_input(msg: Message):
    """Принимает новое значение параметра оформления."""
    uid  = msg.from_user.id
    key  = _style_edit_sessions.pop(uid, None)
    if not key or key not in brand.STYLE_DEFS:
        return
    df   = brand.STYLE_DEFS[key]
    text = (msg.text or "").strip()
    if not text:
        _style_edit_sessions[uid] = key
        return await msg.reply("❌ Пустое сообщение — отправь значение.")
    if len(text) > df["max"]:
        _style_edit_sessions[uid] = key
        return await msg.reply(f"❌ Слишком длинно (максимум {df['max']} символов).")
    brand.set_style(key, text)
    saved = await brand.persist_brand_now()
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 К оформлению", callback_data="editor:style")],
        [InlineKeyboardButton(text="🛠 Главное меню", callback_data="editor:menu")],
    ])
    await msg.reply(
        f"✅ <b>{html.escape(df['desc'])}</b> обновлено!\n\n"
        f"Новое значение: <code>{html.escape(text)}</code>\n\n"
        f"Заголовок теперь: {brand.hdr()}\n"
        f"Разделитель: {brand.div()}"
        + ("" if saved else "\n\n⚠️ PostgreSQL недоступний: зміна поки є лише локально."),
        parse_mode="HTML",
        reply_markup=back_kb,
    )


@dp.message(F.chat.type == "private",
            F.func(lambda m: m.from_user is not None
                   and m.from_user.id in _btn_edit_sessions
                   and not (m.text or "").startswith("/")))
async def handle_btn_edit_input(msg: Message):
    """Принимает ввод для редактирования названия или ссылки кнопки."""
    uid    = msg.from_user.id
    state  = _btn_edit_sessions.pop(uid, None)
    if not state:
        return
    key  = state["key"]
    step = state["step"]
    text = (msg.text or "").strip()
    if not text:
        _btn_edit_sessions[uid] = state  # вернуть состояние
        return await msg.reply("❌ Пустое сообщение — отправь текст.")

    df = brand.BUTTON_DEFS.get(key, {})

    if step == "url":
        if not (text.startswith("http://") or text.startswith("https://") or text.startswith("tg://")):
            _btn_edit_sessions[uid] = state
            return await msg.reply("❌ Ссылка должна начинаться с https:// или tg://")
        brand.set_custom_button(key, url=text)
    else:
        if len(text) > 64:
            _btn_edit_sessions[uid] = state
            return await msg.reply("❌ Название кнопки не может быть длиннее 64 символов.")
        brand.set_custom_button(key, label=text)

    saved = await brand.persist_brand_now()

    what = "Ссылка" if step == "url" else "Название"
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔘 К кнопкам", callback_data="editor:btns")],
        [InlineKeyboardButton(text="🛠 Главное меню", callback_data="editor:menu")],
    ])
    await msg.reply(
        f"✅ {what} кнопки <b>{html.escape(df.get('desc', key))}</b> обновлено!\n\n"
        f"Новое значение: <code>{html.escape(text)}</code>"
        + ("" if saved else "\n\n⚠️ PostgreSQL недоступний: зміна поки є лише локально."),
        parse_mode="HTML",
        reply_markup=back_kb,
    )


@dp.message(Command("setemojipack"))
async def cmd_setemojipack(msg: Message):
    """Загружает стикер-пак из Telegram и использует его emoji в оформлении бота."""
    if not is_owner(msg):
        return
    parts = (msg.text or "").split(maxsplit=1)
    pack_name = parts[1].strip() if len(parts) > 1 else ""
    if not pack_name:
        cur = brand.get_pack_name() or "не задан"
        return await msg.reply(
            f"Текущий пак: <code>{html.escape(cur)}</code>\n\n"
            "Использование:\n"
            "<code>/setemojipack adaptiveqp_by_emsetbot</code>",
            parse_mode="HTML"
        )
    status_msg = await msg.reply(f"⏳ Загружаю пак <code>{html.escape(pack_name)}</code>…", parse_mode="HTML")
    try:
        sticker_set = await bot.get_sticker_set(pack_name)
        ids = [s.custom_emoji_id for s in sticker_set.stickers if getattr(s, "custom_emoji_id", None)]
        if not ids:
            return await status_msg.edit_text(
                f"⚠️ Пак <code>{html.escape(pack_name)}</code> найден, но не содержит custom emoji.\n"
                "Убедись что это пак именно с <b>custom emoji</b>, а не обычными стикерами.",
                parse_mode="HTML"
            )
        brand.set_pack(ids, pack_name)
        save_data()
        await status_msg.edit_text(
            f"✅ <b>Пак загружен!</b>\n\n"
            f"📦 <code>{html.escape(pack_name)}</code> — {len(ids)} emoji\n\n"
            f"Превью первых 12:\n{brand.preview(12)}\n\n"
            f"Заголовок: {brand.hdr()}\n"
            f"Разделитель: {brand.div()}\n\n"
            "Все сообщения бота теперь используют этот пак.",
            parse_mode="HTML"
        )
    except Exception as ex:
        await status_msg.edit_text(
            f"❌ Ошибка загрузки пака <code>{html.escape(pack_name)}</code>:\n"
            f"<code>{html.escape(str(ex))}</code>\n\n"
            "Проверь название пака (часть URL после /addemoji/).",
            parse_mode="HTML"
        )


# ═══════════════════════════════════════════════════════
# АНТИЛИНК — управление фильтром ссылок
# ═══════════════════════════════════════════════════════
@dp.message(Command("antilink", "антилинк"))
async def cmd_antilink(msg: Message, command: CommandObject):
    if not is_owner(msg) and not await is_admin(msg):
        return await msg.reply("⛔ Только администраторы")
    args = (command.args or "").strip().lower()
    cid  = msg.chat.id
    mod_chat = _ank.get_mod_chat()

    if args in ("on", "вкл", "включить", "enable"):
        _link_guard[cid] = True
        save_data()
        mod_note = ""
        if mod_chat:
            mod_note = "\n🛡 В чате администрации ссылки всегда разрешены."
        await msg.reply(
            f"{brand.hdr()}\n\n"
            "🔗 <b>Антилинк включён!</b>\n\n"
            "Все ссылки от обычных участников будут удаляться.\n"
            "Администрация освобождена от фильтра." + mod_note + "\n\n"
            "3 нарушения → автомут на 5 минут.\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )

    elif args in ("off", "выкл", "выключить", "disable"):
        _link_guard[cid] = False
        save_data()
        await msg.reply(
            f"{brand.hdr()}\n\n"
            "🔓 <b>Антилинк выключен.</b>\n\n"
            "Ссылки больше не удаляются автоматически.\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )

    else:
        enabled = _link_guard.get(cid, False)
        status  = "✅ Включён" if enabled else "❌ Выключен"
        wl      = _link_whitelist.get(cid, [])
        wl_text = "\n".join(f"  • <code>{html.escape(p)}</code>" for p in wl) if wl else "  (пусто)"
        mod_note = ""
        if mod_chat:
            mod_note = f"\n🛡 Чат администрации (<code>{mod_chat}</code>) — всегда разрешены.\n"
        await msg.reply(
            f"{brand.hdr()}\n\n"
            f"🔗 <b>Антилинк</b> — {status}\n"
            f"{mod_note}\n"
            f"📋 Белый список ({len(wl)}):\n{wl_text}\n\n"
            "Команды:\n"
            "<code>антилинк вкл</code> — включить\n"
            "<code>антилинк выкл</code> — выключить\n"
            "<code>белый_список [ссылка]</code> — добавить в белый список\n"
            "<code>белый_список удалить [ссылка]</code> — убрать\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )

TEXT_COMMANDS.update({
    "антилинк":  cmd_antilink,
    "antilink":  cmd_antilink,
})


@dp.message(Command("whitelist", "белый_список", "allowlink"))
async def cmd_whitelist(msg: Message, command: CommandObject):
    if not is_owner(msg) and not await is_admin(msg):
        return await msg.reply("⛔ Только администраторы")
    args = (command.args or "").strip()
    cid  = msg.chat.id
    _link_whitelist.setdefault(cid, [])

    if not args:
        wl = _link_whitelist[cid]
        if not wl:
            return await msg.reply(
                "📋 Белый список пуст.\n\n"
                "Добавить: <code>белый_список https://t.me/example</code>",
                parse_mode="HTML",
            )
        lines = [f"  {i+1}. <code>{html.escape(p)}</code>" for i, p in enumerate(wl)]
        return await msg.reply(
            f"📋 <b>Белый список ссылок</b>\n\n" + "\n".join(lines),
            parse_mode="HTML",
        )

    # Удаление
    if args.startswith(("удалить ", "remove ", "del ")):
        pattern = args.split(maxsplit=1)[1] if " " in args else ""
        if pattern in _link_whitelist[cid]:
            _link_whitelist[cid].remove(pattern)
            save_data()
            return await msg.reply(
                f"✅ Убрано из белого списка:\n<code>{html.escape(pattern)}</code>",
                parse_mode="HTML",
            )
        return await msg.reply(
            f"❓ Не найдено:\n<code>{html.escape(pattern)}</code>",
            parse_mode="HTML",
        )

    # Добавление
    if args not in _link_whitelist[cid]:
        _link_whitelist[cid].append(args)
        save_data()
        await msg.reply(
            f"✅ Добавлено в белый список:\n<code>{html.escape(args)}</code>",
            parse_mode="HTML",
        )
    else:
        await msg.reply("⚠️ Уже в белом списке.", parse_mode="HTML")

TEXT_COMMANDS.update({
    "белый_список": cmd_whitelist,
    "allowlink":    cmd_whitelist,
    "whitelist":    cmd_whitelist,
})

# ── V6 команды ─────────────────────────────────────────
TEXT_COMMANDS.update({
    # XP / уровни
    "уровень":       cmd_level,
    "ранг":          cmd_rank,
    "топ":           cmd_top_xp,
    "достижения":    cmd_achievements,
    "сообщения":     cmd_messages,
    "активность":    cmd_activity,
    # Ежедневные
    "дейли":         cmd_daily,
    "бонус":         cmd_bonus,
    "задания":       cmd_tasks,
    "награды":       cmd_rewards,
    "лидерборд":     cmd_leaderboard,
    # Статистика чата
    "статчата":      cmd_chatstats,
    "онлайн":        cmd_online,
    "аналитика":     cmd_analytics,
    "рост":          cmd_growth,
    # Администрирование
    "логи":          cmd_mod_logs,
    "жалобы":        cmd_reports_list,
    "рейд":          cmd_raid_toggle,
    "антиспам":      cmd_antispam_toggle,
    "фильтры":       cmd_filters_list,
    # Фаундер
    "овнер":         cmd_owner_panel,
    # Рефералы
    "инвайт":        cmd_invite,
    "рефералы":      cmd_referrals_list,
    "инвайты":       cmd_invites_stats,
    # VIP / уровни (фаундер)
    "сетвип":        cmd_setvip_v6,    "setvip":       cmd_setvip_v6,
    "снятьвип":      cmd_removevip_v6, "removevip":    cmd_removevip_v6,
    "сетлевел":      cmd_setlevel,     "setlevel":     cmd_setlevel,
    # Юзеринфо
    "юзеринфо":      cmd_userinfo,     "userinfo":     cmd_userinfo,
    # Забрать LMN (фаундер)
    "взять":         cmd_take,         "take":         cmd_take,
    # Настройки чата (фаундер)
    "сетмодчат":     cmd_setmodchat,   "setmodchat":   cmd_setmodchat,
    "сетпубчат":     cmd_setpubchat,   "setpubchat":   cmd_setpubchat,
    "сетэмодзи":     cmd_setemoji,     "setemoji":     cmd_setemoji,
    "сетемодзипак":  cmd_setemojipack, "setemojipack": cmd_setemojipack,
})


@dp.message(Command("sendlaunch"))
async def cmd_sendlaunch(msg: Message):
    """Відправляє алерт про запуск проекту в паб-чат (тільки фаундер)."""
    if not is_owner(msg):
        return await msg.reply("⛔ Тільки фаундер")

    pub_chat = _ank.get_pub_chat()
    if not pub_chat:
        return await msg.reply("❌ pub_chat_id не встановлено. Спочатку запусти /setpubchat")

    # Collect all admins/mods to mention (skip founder)
    mentions: list[str] = []
    team_roles = ("lead_admin", "co_admin", "admin", "moderator")
    # From runtime ROLES dict (uid -> role)
    for uid, role in ROLES.items():
        if role in team_roles:
            uname = next((u for u, r_uid in _ROLE_USERNAMES.items() if False), None)
            # look up by uid in _ROLE_USERNAMES reverse
    # From _ROLE_USERNAMES (username -> role) — simplest source
    for uname, role in _ROLE_USERNAMES.items():
        if role in team_roles:
            mention = f"@{uname}"
            if mention not in mentions:
                mentions.append(mention)

    mention_line = "  ".join(mentions) if mentions else ""
    site_line = f"\n🌐 Офіційний сайт: {LUMENA_SITE_URL}" if LUMENA_SITE_URL else ""

    text = (
        "⚡️ <b>УВАГА КОМАНДІ LUMENA</b> ⚡️\n\n"
        "Адміністратори та модератори — будьте на готові!\n\n"
        "🚀 <b>Запуск проекту о 20:00 за Києвом</b>\n\n"
        "📋 Що потрібно зробити:\n"
        "• Уважно стежте за чатом\n"
        "• Швидко реагуйте на порушення правил\n"
        "• Привітно зустрічайте нових учасників\n"
        "• Перевірте що всі інструменти бота працюють коректно\n"
        "• Антилінк та верифікація — активні"
        f"{site_line}\n"
        "🤖 Бот: @LumenarAi_Bot\n\n"
        "Слава Україні! 🇺🇦\n\n"
        "— <i>Автоматичне повідомлення системи LUMENA</i>"
    )
    if mention_line:
        text += f"\n\n{mention_line}"

    try:
        await bot.send_message(pub_chat, text, parse_mode="HTML")
        await msg.reply("✅ Алерт відправлено в паб-чат!")
    except Exception as e:
        await msg.reply(f"❌ Помилка: {e}")

@dp.message(Command("aistatus"))
async def cmd_aistatus(msg: Message):
    """Статус AI Terra — тільки для власника. Не розкриває секретів."""
    if not is_owner(msg):
        return await msg.reply("⛔ Тільки фаундер")

    mode = ai_agent.terra_mode()
    available = ai_agent.terra_available()

    if mode == "direct_key":
        source = "🔑 Прямий ключ <code>OPENAI_API_KEY</code>"
        status_icon = "✅"
        status_text = "Terra <b>активна</b>"
    elif mode == "replit_proxy":
        source = "🔗 Replit AI Integrations proxy"
        status_icon = "✅"
        status_text = "Terra <b>активна</b> (через Replit проксі)"
    else:
        source = "—"
        status_icon = "❌"
        status_text = "Terra <b>недоступна</b> — використовується локальний AI"

    fallback_ok = "✅ Локальний AI готовий як резерв"

    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"<b>🤖 Статус AI Лумени</b>\n"
        f"{brand.div()}\n"
        f"{status_icon} {status_text}\n"
        f"📡 Джерело: {source}\n"
        f"🛡 {fallback_ok}\n"
        f"🧠 Модель: <code>gpt-5.6-terra</code>\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )
@dp.message(Command("setsiteurl"))
async def cmd_setsiteurl(msg: Message):
    """Встановлює URL офіційного сайту Лумени (відображається в меню та привітаннях)."""
    global LUMENA_SITE_URL
    if not is_owner(msg):
        return await msg.reply("⛔ Тільки фаундер")
    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().startswith("http"):
        current = LUMENA_SITE_URL or "не встановлено"
        return await msg.reply(
            f"ℹ️ Поточний URL сайту:\n<code>{current}</code>\n\n"
            "Оновити:\n<code>/setsiteurl https://...</code>",
            parse_mode="HTML"
        )
    LUMENA_SITE_URL = parts[1].strip()
    await msg.reply(
        f"✅ <b>URL сайту оновлено!</b>\n🌐 <a href=\"{LUMENA_SITE_URL}\">{LUMENA_SITE_URL}</a>\n\n"
        "Кнопка «🌐 Сайт Лумены» тепер веде на нову адресу.",
        parse_mode="HTML"
    )


@dp.message(Command("setchatlink"))
async def cmd_setchatlink(msg: Message):
    """Встановлює посилання на головний чат (для кнопки НАШ ЧАТ в анкетах)."""
    if not is_owner(msg):
        return await msg.reply("⛔ Тільки фаундер")
    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().startswith("http"):
        return await msg.reply(
            "ℹ️ Вкажи посилання на чат:\n"
            "<code>/setchatlink https://t.me/+...</code>",
            parse_mode="HTML"
        )
    link = parts[1].strip()
    _ank.set_chat_link(link)
    _ank.save_anketa_settings()
    await msg.reply(
        f"✅ <b>Посилання на чат збережено!</b>\n"
        f"🔗 {link}\n\n"
        f"Тепер кнопка «⭐ НАШ ЧАТ» з'явиться під кожною анкетою.",
        parse_mode="HTML"
    )


# Регистрируем команды настройки чата (определены после основного блока TEXT_COMMANDS)
TEXT_COMMANDS.update({
    "сетсайтурл": cmd_setsiteurl, "setsiteurl": cmd_setsiteurl,
    "сетчатлинк": cmd_setchatlink, "setchatlink": cmd_setchatlink,
})


@dp.message(F.photo, F.chat.type == "private")
async def handle_photo_in_private(msg: Message):
    """Обробляє фото надіслане в особистих — для медіа-кроку анкети."""
    await _ank.handle_media_step(bot, msg)


@dp.message(F.video, F.chat.type == "private")
async def handle_video_in_private(msg: Message):
    """Обробляє відео надіслане в особистих — для медіа-кроку анкети."""
    await _ank.handle_media_step(bot, msg)


# ── Автомут за оскорбление верхушки ───────────────────────────
_HARD_INSULTS = {
    "иди нахуй","иди нафиг","пошёл нахуй","пошла нахуй","иди на хуй",
    "идите нахуй","идите на хуй","пошли нахуй","нахуй идите",
    "пошёл нафиг","пошла нафиг","иди нафиг","заткнись","заткнитесь",
    "хуйло","пиздуй","сука","мудак","мудаки","уебан","уёбок",
    "дебил","дебилы","идиот","идиоты","ублюдок","тупой","тупая",
    "тупые","уроды","урод","твари","тварь","ёбаный","ёбаная",
    "чёртов","чёртова","нахрен вас","вашу мать","ёб твою",
    "да пошли вы","да пошёл ты","да пошла ты","пошёл в жопу",
    "отстаньте","отвалите","ненавижу вас","ненавижу этот чат",
}
_CHAT_INSULTS = {
    "пидор", "пидоры", "пидорас", "пидорасы", "пидорасина",
    "пидрила", "пидрилы", "гандон", "гандоны", "долбоеб",
    "долбоёб", "долбоебы", "долбоёбы", "уебок", "уёбок",
    "уебки", "уёбки", "еблан", "ебланы", "хуесос", "хуесосы",
    "мразь", "мрази", "ублюдок", "ублюдки", "сука", "суки",
    "мудак", "мудаки", "тварь", "твари", "дебил", "дебилы",
    "идиот", "идиоты",
}
_ADMIN_TARGETS = {
    "админ","адмнн","адмнны","модер","модеры","модератор","владелец",
    "владелка","гидра","hydra","hydræ","создатель","руководство",
    "верхушка","команда","хдр","hdr","hdrttt","начальник","начальники",
    "боты","бот","lumena","лумена","лумена",
}

async def _check_chat_insult(msg: Message) -> bool:
    """Удаляет оскорбление и выдаёт участнику мут на 10 минут."""
    if not msg.text or not msg.from_user or msg.chat.type == "private":
        return False
    uid = msg.from_user.id
    if uid in SUPER_IDS or has_role(uid, "lead_admin", "co_admin", "admin", "moderator"):
        return False
    words = re.findall(r"[а-яёa-z]+", msg.text.lower())
    if not any(word in _CHAT_INSULTS for word in words):
        return False
    try:
        member = await bot.get_chat_member(msg.chat.id, uid)
        if member.status in ("administrator", "creator"):
            return False
    except Exception:
        return False

    try:
        await msg.delete()
        notice = await bot.send_message(
            msg.chat.id,
            f"🚫 <b>{html.escape(msg.from_user.full_name)}</b> — сообщение удалено за нарушение правил.",
            parse_mode="HTML",
        )
        asyncio.create_task(_delete_later(notice, 15))
        return True
    except Exception as error:
        logging.warning("Автомодерация оскорблений не сработала: %s", error)
        return False


async def _check_admin_insult(msg: Message) -> bool:
    """Автомут за оскорбление верхушки. Возвращает True если был применён мут."""
    if not msg.text or not msg.from_user:
        return False
    if msg.chat.type == "private":
        return False
    tl = msg.text.lower()
    has_insult = any(w in tl for w in _HARD_INSULTS)
    has_target = any(w in tl for w in _ADMIN_TARGETS)
    if not (has_insult and has_target):
        return False
    uid = msg.from_user.id
    # Не мутим самих администраторов и владельца
    try:
        member = await bot.get_chat_member(msg.chat.id, uid)
        if member.status in ("administrator", "creator"):
            return False
    except Exception:
        return False
    if uid in SUPER_IDS:
        return False
    name_u = msg.from_user.full_name
    # Штраф ауры за агрессию — без мута
    add_aura(uid, -1.0)
    try:
        await msg.delete()
    except Exception:
        pass
    try:
        notice = await bot.send_message(
            msg.chat.id,
            f"🚫 <b>{html.escape(name_u)}</b> — сообщение удалено за нарушение правил.\n"
            f"🌑 Аура: <b>-1%</b>",
            parse_mode="HTML",
        )
        asyncio.create_task(_delete_later(notice, 15))
        return True
    except Exception:
        return False


# ═══════════════════════════════════════════════════════
# ИИ-АГЕНТ ЛУМЕНА — ХЕЛПЕРЫ
# ═══════════════════════════════════════════════════════

async def _lumena_ai_private(msg: Message):
    """Лумена AI в личке — отвечает на любой свободный текст."""
    name = msg.from_user.first_name or msg.from_user.username or "Участник"
    try:
        await bot.send_chat_action(msg.chat.id, "typing")
    except Exception:
        pass
    reply = await ai_agent.lumena_reply(msg.from_user.id, name, msg.text)
    if reply:
        await msg.reply(reply)


async def _lumena_ai_group(msg: Message):
    """Лумена AI в группе — реагирует только на прямые обращения."""
    tl = (msg.text or "").lower().strip()
    is_addressed = False

    # 1. Ответ на сообщение самого бота
    if (msg.reply_to_message
            and msg.reply_to_message.from_user
            and msg.reply_to_message.from_user.id == _BOT_ID):
        is_addressed = True

    # 2. @mention бота
    if not is_addressed and msg.entities:
        for ent in msg.entities:
            if ent.type.lower() == "mention":
                mention = msg.text[ent.offset: ent.offset + ent.length].lower()
                if _BOT_USERNAME and _BOT_USERNAME.lower() in mention:
                    is_addressed = True
                    break

    # 3. Звернення по імені: «Лумена, ...», «лумка ...», «Lumena ...».
    # Дозволяємо розділовий знак або пробіл після імені, щоб не реагувати
    # на випадкові частини інших слів.
    if not is_addressed:
        is_addressed = bool(re.match(
            r"^(?:лумена|лумену|лумко|лумка|лум|lumena)\b[\s,!.:;—-]",
            tl,
            flags=re.IGNORECASE,
        ))

    if not is_addressed:
        return

    name = msg.from_user.first_name or msg.from_user.username or "Участник"
    try:
        await bot.send_chat_action(msg.chat.id, "typing")
    except Exception:
        pass
    reply = await ai_agent.lumena_reply(msg.chat.id, name, msg.text)
    if reply:
        await msg.reply(reply)


@dp.message(F.text.lower().contains("разжаловать анкету"))
async def cmd_revoke_anketa(msg: Message):
    """@veroniksssxa и фаундер могут отозвать анкету, написав «разжаловать анкету»."""
    sender_uname = (msg.from_user.username or "").lower()
    if not is_anketa_revoke_allowed(sender_uname):
        return  # не авторизован — игнорируем тихо

    # Определяем uid цели
    target_uid = None

    # 1. Из reply — ищем по message_id паблик-поста в approved_data
    if msg.reply_to_message:
        target_uid = _ank.get_uid_by_pub_msg(
            msg.reply_to_message.message_id,
            msg.chat.id,
        )

    # 2. Из текста: цифровой ID или @username
    if not target_uid:
        words = msg.text.split()
        for w in words:
            if w.lstrip("@").isdigit():
                target_uid = int(w.lstrip("@"))
                break
            if w.startswith("@") and len(w) > 1:
                uname_search = w.lstrip("@").lower()
                for uid_key, d in _ank._approved_data.items():
                    if (d.get("username") or "").lower() == uname_search:
                        target_uid = uid_key
                        break
            if target_uid:
                break

    if not target_uid:
        return await msg.reply(
            "❓ Укажи пользователя:\n"
            "• Ответь на пост анкеты\n"
            "• Или добавь @username / ID после команды",
        )

    data = _ank.revoke_anketa(target_uid)
    if not data:
        return await msg.reply("⚠️ Активная анкета у этого пользователя не найдена.")

    # Удаляем пост из паб-чата
    pub_msg  = data.get("pub_msg_id")
    pub_chat = data.get("pub_chat_id") or _ank.get_pub_chat()
    if pub_msg and pub_chat:
        try:
            await bot.delete_message(pub_chat, pub_msg)
        except Exception:
            pass

    # Уведомляем пользователя
    try:
        await _send_custom(
            target_uid, "revoke_notify",
            f"{brand.hdr()}\n\n"
            f"{brand.bul()} <b>Твоя анкета была отозвана администрацией.</b>\n\n"
            "Если считаешь это ошибкой — обратись к модераторам.\n"
            "Создать новую анкету: /анкета\n\n"
            f"{brand.div()}"
        )
    except Exception:
        pass

    name_hint  = data.get("full_name") or data.get("username") or str(target_uid)
    ank_num    = data.get("anketa_num") or "—"
    uname_hint = f"@{data['username']}" if data.get("username") else "—"
    revoker    = f"@{msg.from_user.username}" if msg.from_user.username else msg.from_user.full_name

    await msg.reply(f"✅ Анкета *{name_hint}* отозвана и удалена из паблика.",
                    parse_mode="Markdown")

    # Уведомление в мод-чат
    mod_chat = _ank.get_mod_chat()
    if mod_chat:
        try:
            await bot.send_message(
                mod_chat,
                f"🗑 *Анкета разжалована*\n\n"
                f"📋 Номер анкеты: *№{ank_num}*\n"
                f"👤 Владелец: *{name_hint}* ({uname_hint})\n"
                f"🆔 ID: `{target_uid}`\n"
                f"👮 Разжаловал: {revoker}\n\n"
                f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
                parse_mode="Markdown"
            )
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# /delanket — тільки фаундер: видалити анкету і повідомити автора
# ═══════════════════════════════════════════════════════════════
@dp.message(Command("delanket"))
async def cmd_delanket(msg: Message, command: CommandObject = None):
    """Фаундер видаляє анкету юзера з бази і повідомляє його.

    Синтаксис:
      /delanket               — у відповідь на пост анкети в паб-чаті
      /delanket @username     — за username
      /delanket 123456789     — за Telegram ID
      /delanket @username причина   — з поясненням для юзера
    """
    if not is_owner(msg):
        return  # тихо ігноруємо для всіх крім фаундера

    # ── Розбираємо аргументи ──────────────────────────────────
    args_raw  = (command.args or "").strip() if command else ""
    parts     = args_raw.split(maxsplit=1)
    target_uid: int | None = None
    reason: str = ""
    # Флаг: юзер щось вказав, але пошук не дав результату
    arg_given = bool(msg.reply_to_message) or bool(parts)
    not_found_hint = ""  # пояснення що саме не знайдено

    # 1. З reply — шукаємо uid по message_id паблік-поста
    if msg.reply_to_message:
        target_uid = _ank.get_uid_by_pub_msg(
            msg.reply_to_message.message_id,
            msg.chat.id,
        )
        reason = args_raw
        not_found_hint = "Повідомлення не прив'язане до жодної анкети."

    # 2. З аргументів: числовий ID або @username
    if not target_uid and parts:
        first = parts[0].lstrip("@")
        reason = parts[1] if len(parts) > 1 else ""
        if first.isdigit():
            target_uid = int(first)
        else:
            uname_low = first.lower()
            for uid_key, d in _ank._approved_data.items():
                if (d.get("username") or "").lower() == uname_low:
                    target_uid = uid_key
                    break
            if not target_uid:
                not_found_hint = (
                    f"Юзер <code>@{html.escape(first)}</code> не знайдений в базі анкет.\n"
                    "Перевір username або вкажи Telegram ID."
                )

    if not target_uid:
        if arg_given and not_found_hint:
            return await msg.reply(
                f"{brand.hdr()}\n\n⚠️ {not_found_hint}",
                parse_mode="HTML",
            )
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            "❓ <b>Вкажи юзера:</b>\n\n"
            "• Відповідь на пост анкети в чаті\n"
            "• <code>/delanket @username</code>\n"
            "• <code>/delanket 123456789</code>\n"
            "• <code>/delanket @username причина</code>",
            parse_mode="HTML",
        )

    # ── Видаляємо анкету ──────────────────────────────────────
    data = _ank.revoke_anketa(target_uid)
    if not data:
        # Можливо статус не «approved» — пробуємо hard-delete
        data = _ank.delete_user_anketa(target_uid)
    if not data:
        return await msg.reply("⚠️ Активна анкета у цього юзера не знайдена.")

    # ── Видаляємо пост(и) з паб-чату ────────────────────────
    pub_msg        = data.get("pub_msg_id")
    pub_chat       = data.get("pub_chat_id") or _ank.get_pub_chat()
    media_msg_ids  = data.get("media_msg_ids") or []
    if pub_chat:
        # Видаляємо текстову картку
        if pub_msg:
            try:
                await bot.delete_message(pub_chat, pub_msg)
            except Exception:
                pass
        # Видаляємо медіа-альбом (якщо був)
        for _mid in media_msg_ids:
            try:
                await bot.delete_message(pub_chat, _mid)
            except Exception:
                pass

    # ── Повідомляємо автора анкети ────────────────────────────
    name_hint  = data.get("full_name") or data.get("username") or str(target_uid)
    uname_hint = f"@{data['username']}" if data.get("username") else "—"
    ank_num    = data.get("anketa_num") or "—"
    reason_line = f"\n\n📌 <b>Причина:</b> {html.escape(reason)}" if reason else ""

    try:
        await bot.send_message(
            target_uid,
            f"{brand.hdr()}\n\n"
            f"🗑 <b>Твоя анкета була видалена фаундером.</b>{reason_line}\n\n"
            "Якщо вважаєш це помилкою — звернись до модераторів.\n"
            "Подати нову анкету: /анкета\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
            reply_markup=_anketa_kb(target_uid),
        )
        notified = "✅ Юзер отримав повідомлення"
    except Exception:
        notified = "⚠️ Не вдалось надіслати повідомлення (юзер заблокував бота)"

    # ── Підтвердження фаундеру ────────────────────────────────
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🗑 <b>Анкета видалена</b>\n\n"
        f"👤 {html.escape(name_hint)} ({uname_hint})\n"
        f"🆔 <code>{target_uid}</code>\n"
        f"📋 Номер анкети: <b>№{ank_num}</b>\n"
        f"{reason_line}\n\n"
        f"{notified}\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

    # ── Лог у мод-чат ─────────────────────────────────────────
    mod_chat = _ank.get_mod_chat()
    if mod_chat:
        try:
            await bot.send_message(
                mod_chat,
                f"{brand.hdr()}\n\n"
                f"🗑 <b>Анкета видалена фаундером</b>\n\n"
                f"👤 {html.escape(name_hint)} ({uname_hint})\n"
                f"🆔 <code>{target_uid}</code>\n"
                f"📋 №{ank_num}{reason_line}\n\n"
                f"{brand.div()}",
                parse_mode="HTML",
            )
        except Exception:
            pass


@dp.message(F.text)
async def universal_handler(msg: Message):
    if not msg.text:
        return

    # ── Трекинг авторов для аура-реакций ────────────────
    if msg.from_user and not msg.from_user.is_bot and msg.chat.type != "private":
        _msg_authors[(msg.chat.id, msg.message_id)] = msg.from_user.id
        if len(_msg_authors) > 20_000:
            # удаляем 1000 старых записей
            for k in list(_msg_authors)[:1000]:
                del _msg_authors[k]

    # «изменить»/«edit» — обрабатывается выше специализированными хэндлерами
    # (cmd_reply_edit если это reply на бота, cmd_editor_ru если без reply)
    # Здесь НЕ перехватываем, чтобы не глотать сообщения до нужных хэндлеров

    # Проверка на оскорбление верхушки (до остального)
    if await _check_chat_insult(msg):
        return
    if await _check_admin_insult(msg):
        return

    uid  = msg.from_user.id
    text = msg.text.strip()

    # ── Поддержка: пользователь отправляет обращение администрации
    if msg.chat.type == "private" and uid in support_sessions and not text.startswith("/"):
        mod_chat = _ank.get_mod_chat()
        if mod_chat:
            user = msg.from_user
            tag = f"@{html.escape(user.username)}" if user.username else html.escape(user.full_name)
            safe_text = html.escape(text)
            try:
                await bot.send_message(
                    mod_chat,
                    f"📩 <b>Обращение от участника</b>\n\n"
                    f"👤 {tag} (ID: <code>{user.id}</code>)\n"
                    f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
                    f"{safe_text}",
                    parse_mode="HTML"
                )
                # Удаляем сессию только после успешной отправки
                del support_sessions[uid]
                await _answer_custom(
                    msg, "support_sent",
                    "✅ <b>Обращение отправлено!</b>\n\n"
                    "Администрация рассмотрит его в ближайшее время 🙏",
                )
            except Exception:
                await msg.reply("❌ Не удалось отправить обращение. Попробуй ещё раз.")
        else:
            await msg.reply("⚠️ Чат администрации не настроен. Попробуй позже.")
        return

    # ── Команды администрации из личного чата ────────────────────
    if msg.chat.type == "private":
        _pm_tl  = text.lower().lstrip("/")
        _pm_cmd = _pm_tl.split()[0] if _pm_tl.split() else ""
        if _pm_cmd in ("объявление", "announce"):
            allowed = (
                is_owner(msg)
                or has_role(uid, "lead_admin", "co_admin", "admin", "moderator")
            )
            if not allowed:
                await msg.reply("⛔ Только администрация")
                return
            import re as _re2
            _pm_raw  = (msg.text or "").strip()
            _pm_body = _re2.sub(r'^/?объявление\s*|^/?announce\s*', '', _pm_raw,
                                count=1, flags=_re2.IGNORECASE).strip()
            if not _pm_body:
                await msg.reply(
                    "📢 <b>Укажи текст объявления:</b>\n\n"
                    "<code>объявление Сегодня в 20:00 — ивент!</code>",
                    parse_mode="HTML"
                )
                return
            _pm_pub = _ank.get_pub_chat()
            _pm_tgt = _pm_pub if _pm_pub else None
            if not _pm_tgt:
                await msg.reply("⚠️ Паб-чат не настроен. Используй /сетпубчат.")
                return
            _pm_text = (
                f"📢 <b>ОБЪЯВЛЕНИЕ</b>\n"
                f"{brand.div()}\n"
                f"{html.escape(_pm_body)}\n"
                f"{brand.div()}"
            )
            try:
                await bot.send_message(_pm_tgt, _pm_text, parse_mode="HTML")
                await msg.reply("✅ <b>Объявление отправлено в паб-чат!</b>",
                                parse_mode="HTML")
            except Exception as _e:
                await msg.reply(f"❌ Ошибка: <code>{_e}</code>", parse_mode="HTML")
            return

    # ── Анкета: обробка кнопок клавіатури в особистих
    if msg.chat.type == "private":
        status = _ank.get_user_status(uid)

        if text == "💌 Моя анкета":
            # Немає анкети — починаємо
            await _ank.start_anketa(bot, msg)
            return

        if text == "📋 Моя анкета ✅":
            # Є схвалена анкета — показуємо з кнопками
            data = _ank.get_approved_data(uid)
            if data:
                _vip3 = is_anketa_premium(uid, data.get("username", ""))
                card_text   = _ank.fmt_my_card(data["answers"], data["username"], data["full_name"],
                                                is_premium=_vip3)
                media_items = data["answers"].get("media", [])
                if not media_items:
                    if data["answers"].get("video_id"):
                        media_items = [{"type": "video", "file_id": data["answers"]["video_id"]}]
                    elif data["answers"].get("photo_id"):
                        media_items = [{"type": "photo", "file_id": data["answers"]["photo_id"]}]
                n = len(media_items)
                if n == 0:
                    await msg.answer(card_text, parse_mode="Markdown",
                                     reply_markup=_ank.make_my_anketa_kb(uid))
                elif n == 1:
                    item = media_items[0]
                    if item["type"] == "photo":
                        await msg.answer_photo(photo=item["file_id"], caption=card_text,
                                               parse_mode="Markdown",
                                               reply_markup=_ank.make_my_anketa_kb(uid))
                    else:
                        await msg.answer_video(video=item["file_id"], caption=card_text,
                                               parse_mode="Markdown",
                                               reply_markup=_ank.make_my_anketa_kb(uid))
                else:
                    await _ank._send_media_group_to_chat(bot, uid, media_items)
                    await msg.answer(card_text, parse_mode="Markdown",
                                     reply_markup=_ank.make_my_anketa_kb(uid))
            else:
                await msg.answer("Анкета не найдена. Попробуй подать снова.",
                                 reply_markup=_anketa_kb(uid))
            return

        if text == "✏️ Редагувати анкету":
            # Відхилено — починаємо заново
            await _ank.start_anketa(bot, msg, force=True)
            return

        if text == "⏳ Анкета на перевірці":
            await msg.answer(
                "⏳ *Твоя анкета сейчас рассматривается администраторами.*\n\n"
                "Ожидай — мы уведомим о решении! 🙏",
                parse_mode="Markdown",
                reply_markup=_anketa_kb(uid)
            )
            return

    # ── Анкета: крок заповнення (особисті повідомлення)
    if msg.chat.type == "private" and uid in _ank._sessions:
        handled = await _ank.handle_anketa_step(bot, msg)
        if handled:
            return

    # ── Анкета: модератор надсилає коментар у чаті модерації
    if (msg.chat.id == _ank.get_mod_chat()
            and msg.from_user.id in _ank._mod_commenting
            and not msg.text.startswith("/")):
        handled = await _ank.handle_mod_comment_step(bot, msg)
        if handled:
            return

    # Автоматически восстанавливаем 500М владельцу после рестарта
    if is_owner(msg):
        global owner_id_cache
        owner_id_cache = msg.from_user.id
        owner_auto_credit(msg.from_user.id)

    text = msg.text.strip()
    tl = text.lower()

    # ── Дождь монет: первый кто написал "подобрать" — забирает
    if tl == "подобрать" and msg.chat.id in _active_rain and msg.chat.type != "private":
        amount = _active_rain.pop(msg.chat.id)
        add_balance(msg.from_user.id, amount)
        save_data()
        name = msg.from_user.first_name
        await msg.reply(
            f"{brand.hdr()}\n\n"
            f"🎉 <b>{name}</b> подобрал монеты!\n\n"
            f"{brand.div()}\n"
            f"💰 <b>+{fmt_lmn(amount)}</b> зачислено на баланс\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )
        return

    # ── ! команды для бана/мута (только так!)
    if text.startswith("!"):
        body = text[1:].strip()
        parts = body.split(maxsplit=1)
        if not parts:
            return
        cmd_word = parts[0].lower()
        args_str = parts[1] if len(parts) > 1 else ""

        # Конвертируем русские суффиксы ТОЛЬКО в первом слове (время),
        # чтобы не портить текст причины ("нарушение чата" и т.д.)
        _ac_parts = args_str.split(maxsplit=1)
        _ac_time  = _ac_parts[0].replace("м","m").replace("ч","h").replace("д","d") if _ac_parts else ""
        _ac_rest  = (" " + _ac_parts[1]) if len(_ac_parts) > 1 else ""
        args_converted = _ac_time + _ac_rest

        class FakeCmd:
            args = args_converted

        fake_cmd = FakeCmd()

        # Бан и мут — только через !
        BAN_MUTE = {
            # Мут
            "мут": cmd_mute, "mute": cmd_mute,
            "замутить": cmd_mute, "замут": cmd_mute,
            # Бан
            "бан": cmd_ban, "ban": cmd_ban,
            "забанить": cmd_ban, "забан": cmd_ban,
            # Форс
            "форсбан": cmd_forceban, "forceban": cmd_forceban,
            "форсмут": cmd_forcemute, "forcemute": cmd_forcemute,
            # Мут на 1 минуту
            "мут1": cmd_mute1, "mute1": cmd_mute1,
            # Размут / разбан / кик через ! тоже работают
            "размут": cmd_unmute, "unmute": cmd_unmute,
            "разбан": cmd_unban,  "unban":  cmd_unban,
            "кик":    cmd_kick,   "kick":   cmd_kick,
            # Варн
            "варн": cmd_warn,   "warn": cmd_warn,
            "снятьварн": cmd_unwarn, "unwarn": cmd_unwarn,
        }
        if cmd_word in BAN_MUTE:
            try: await BAN_MUTE[cmd_word](msg, fake_cmd)
            except TypeError: await BAN_MUTE[cmd_word](msg)
            return

        # Остальные ! команды
        if cmd_word in TEXT_COMMANDS:
            try: await TEXT_COMMANDS[cmd_word](msg, fake_cmd)
            except TypeError: await TEXT_COMMANDS[cmd_word](msg)
            return
        return

    # ── Команды без префикса
    if not text.startswith("/"):
        # 🔥 стрик через огонь
        if text.strip() == "🔥" or tl.strip() == "огонь":
            await do_checkin(msg.chat.id, msg.from_user.id, msg)
            return

        # Виселица — угадывание буквы
        if tl.startswith("виселица_") and len(tl) > 9:
            letter = tl.replace("виселица_", "").strip()
            if len(letter) == 1:
                await cmd_hangman_guess(msg, letter)
                return

        # Ищем команду по первому слову (и двум словам)
        parts = tl.split(maxsplit=2)
        two_words = " ".join(parts[:2]) if len(parts) >= 2 else ""
        first_word = parts[0] if parts else ""

        # Сначала пробуем два слова (например "список браков")
        handler = TEXT_COMMANDS.get(two_words) or TEXT_COMMANDS.get(first_word)

        if handler:
            # Аргументы = всё после первого (или двух) слов
            if TEXT_COMMANDS.get(two_words):
                args_str = " ".join(parts[2:]) if len(parts) > 2 else ""
            else:
                args_str = " ".join(parts[1:]) if len(parts) > 1 else ""

            # Не меняем кириллицу в аргументах: например, знак "водолей"
            # содержит букву "д" и раньше превращался в "водолей" с
            # латинской буквой, из-за чего гороскоп не находил знак.
            # parse_time_and_reason сам нормализует суффиксы времени там,
            # где они действительно нужны.
            args_converted = args_str

            class FakeCmd2:
                args = args_converted or None

            try: await handler(msg, FakeCmd2())
            except TypeError: await handler(msg)
            return

        # AI-ассистент отключён: свободные сообщения не обрабатываются.
        return

# ═══════════════════════════════════════════════════════
# АВТОПІДКАЗКА КОЛИ БОТ ВХОДИТЬ У НОВИЙ ЧАТ
# ═══════════════════════════════════════════════════════
_DEFAULT_WELCOME = (
    "👋 *Добро пожаловать, {name}!*\n\n"
    "💫 Рады видеть тебя в нашем чате!\n\n"
    "📋 *Создай анкету знакомства* — это займёт пару минут:\n\n"
    "① Напиши боту в личку:\n"
    "   `/анкета`\n\n"
    "② Заполни: имя, возраст, город, о себе\n\n"
    "③ Добавь фото _(или пропусти)_\n\n"
    "④ Дождись одобрения администрации ✅\n\n"
    "ℹ️ Бот: @LumenarAi\\_Bot"
)


@dp.message(F.new_chat_members)
async def on_new_chat_member(msg: Message):
    """Вітає кожного нового учасника в групових чатах."""
    for user in msg.new_chat_members:
        if user.is_bot:
            continue
        name = user.first_name or user.full_name or "друг"

        # V6: рейд-мод — мутируем новых участников на 10 минут
        if raid_mode.get(msg.chat.id):
            # Не мутируем фаундера и Telegram-администраторов чата
            _skip_raid = user.id == OWNER_ID
            if not _skip_raid:
                try:
                    _cm = await bot.get_chat_member(msg.chat.id, user.id)
                    if _cm.status in ("creator", "administrator"):
                        _skip_raid = True
                except Exception:
                    pass
            if not _skip_raid:
                try:
                    until = datetime.now(UTC) + timedelta(minutes=10)
                    await bot.restrict_chat_member(
                        msg.chat.id, user.id,
                        ChatPermissions(can_send_messages=False),
                        until_date=until,
                    )
                    _log_mod(msg.chat.id, "raid_mute", user.id, 0)
                except Exception as _re:
                    pass

        # ── Текст кнопки (кастомный или дефолтный) ───────
        btn_ct   = brand.get_custom_text("welcome_btn")
        btn_text = btn_ct[0].strip() if btn_ct else "📝 Создать анкету"
        welcome_rows = [[
            InlineKeyboardButton(
                text=btn_text,
                url="https://t.me/LumenarAi_Bot?start=anketa",
            ),
        ]]
        welcome_rows.append([
            InlineKeyboardButton(
                text="📖 Правила чата",
                url="https://teletype.in/@lumenaoff/eoHmmuUNnxP",
            ),
        ])
        if LUMENA_SITE_URL:
            welcome_rows.append([
                InlineKeyboardButton(text="🌐 Сайт Лумены", url=LUMENA_SITE_URL),
            ])
        kb = InlineKeyboardMarkup(inline_keyboard=welcome_rows)

        # ── Текст приветствия ─────────────────────────────
        ct = brand.get_custom_text("welcome_msg")
        try:
            if ct:
                raw_text, ents_data = ct
                # Подставляем {name} и корректируем офсеты entities
                final_text, final_ents_data = brand.substitute_name(raw_text, ents_data, name)
                ents = _build_entities(final_ents_data)
                await msg.answer(final_text, entities=ents or None, reply_markup=kb)
            else:
                await msg.answer(
                    _DEFAULT_WELCOME.format(name=name),
                    parse_mode="Markdown",
                    reply_markup=kb,
                )
        except Exception:
            pass


@dp.my_chat_member()
async def on_bot_added(event: ChatMemberUpdated):
    """Коли бота додають у чат — відразу підказує команди налаштування."""
    new_status = event.new_chat_member.status
    if new_status not in ("member", "administrator"):
        return
    chat_id = event.chat.id
    mod_set = "✅" if _ank.get_mod_chat() == chat_id else "⬜"
    pub_set = "✅" if _ank.get_pub_chat() == chat_id else "⬜"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📖 Всі команди", callback_data="help:menu"),
    ]])
    try:
        await bot.send_message(
            chat_id,
            f"👋 Привіт! Я <b>Лумена</b> — розумний бот для вашого чату 💙\n\n"
            f"<b>Налаштування анкет</b> (тільки фаундер):\n\n"
            f"{mod_set} <code>/setmodchat</code> — чат модерації анкет\n"
            f"{pub_set} <code>/setpubchat</code> — чат публікацій анкет\n\n"
            f"🆔 ID чату: <code>{chat_id}</code>",
            parse_mode="HTML",
            reply_markup=kb,
        )
    except Exception:
        pass

# ═══════════════════════════════════════════════════════
# ЗАПУСК
# ═══════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════
# ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОШИБОК ХЕНДЛЕРОВ
# ═══════════════════════════════════════════════════════
@dp.errors()
async def global_error_handler(event, **kwargs):
    exc = getattr(event, "exception", None) or kwargs.get("exception")
    logging.error(f"⚠️ Необработанная ошибка: {type(exc).__name__}: {exc}")
    return True  # помечаем как обработанное, polling не падает


async def main():
    # 0. Ініціалізація PostgreSQL (якщо DATABASE_URL задано)
    await _db.init_db()

    # 1. Відновлюємо дані: PostgreSQL → GitHub → локальний файл
    await restore_bot_data()
    await _ank.restore_anketa()
    await brand.restore_brand()
    load_data()
    _ank.load_anketa_settings()
    if normalize_lmn_balances_once():
        await save_state_now("одноразовое выравнивание LMN-балансов")
        # Компенсационное объявление отправлено вручную ранее.
        # При редеплое никакие сообщения в чаты не отправляются.
    if transfer_all_balances_to_founder():
        await save_state_now("перевод всех LMN-балансов фаундеру")

    # ── Отложенные уведомления при старте ОТКЛЮЧЕНЫ ──────────────────────────
    # Требование: после редеплоя бот НЕ отправляет никаких сообщений в чаты.
    # Накопившаяся очередь молча очищается.
    if pending_notifications:
        logging.info("🔕 Очищено %d отложенных уведомлений без отправки", len(pending_notifications))
        pending_notifications.clear()
        await save_state_now("очистка отложенных уведомлений без отправки")

    brand.load_custom_texts()
    brand.load_custom_buttons()
    brand.load_custom_style()

    # ── Загружаем emoji пак при старте ───────────────────
    _startup_pack = brand.get_pack_name() or "adaptiveqp_by_emsetbot"
    if not brand.has_pack():
        try:
            _ss = await bot.get_sticker_set(_startup_pack)
            _ids = [s.custom_emoji_id for s in _ss.stickers
                    if getattr(s, "custom_emoji_id", None)]
            if _ids:
                brand.set_pack(_ids, _startup_pack)
                print(f"✅ Emoji пак загружен: {_startup_pack} ({len(_ids)} emoji)")
        except Exception as _ex:
            print(f"⚠️ Не удалось загрузить emoji пак '{_startup_pack}': {_ex}")

    asyncio.create_task(auto_save_loop())
    asyncio.create_task(coin_rain_loop())

    # V6-объявление больше НЕ отправляется автоматически при старте —
    # только вручную через /announce_v6 (иначе каждый редеплой спамил чат).

    # ── Синхронизация экономики связанных чатов ──────────
    # pub_chat и mod_chat используют единую базу (canonical = pub_chat)
    try:
        _pub  = _ank.get_pub_chat()
        _mod  = _ank.get_mod_chat()
        if _pub and _mod and _pub != _mod:
            _ECON_CANONICAL[_mod] = _pub   # mod → pub (canonical)
            print(f"🔗 Связанные чаты: mod={_mod} → pub={_pub}")
    except Exception as _ex:
        print(f"⚠️ linked chats setup: {_ex}")

    # ── Очищаем меню команд Telegram (команды работают без /)
    global _BOT_ID, _BOT_USERNAME
    try:
        me = await bot.get_me()
        _BOT_ID = me.id
        _BOT_USERNAME = me.username or ""
    except Exception as _e:
        logging.warning(f"get_me: {_e}")
    try:
        await bot.delete_my_commands(scope=BotCommandScopeDefault())
        await bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats())
        await bot.delete_my_commands(scope=BotCommandScopeAllGroupChats())
    except Exception as _e:
        logging.warning(f"delete_my_commands: {_e}")

    # Единоразовая выдача @VladMish11
    from award_vlad import run_award
    asyncio.create_task(run_award(
        bot, chat_members, add_balance, fmt_lmn, save_data, ChatMemberStatus
    ))

    # Единоразовое снятие монет у @VladMish11
    from deduct_vlad import run_deduct
    asyncio.create_task(run_deduct(
        bot, chat_members, lmn_balances, fmt_lmn, save_data, ChatMemberStatus
    ))

    # Одноразове оголошення про анкети
    from announce_anketa import run_announce
    asyncio.create_task(run_announce(bot))

    print(f"🤖 Лумена Бот v{BOT_VERSION} запущен!")

    # ── SIGTERM handler (Railway зупиняє контейнер через SIGTERM) ────────
    _shutdown_event = asyncio.Event()

    def _handle_sigterm():
        print("🛑 SIGTERM отримано — збереження і завершення...")
        _shutdown_event.set()

    import signal
    loop_ref = asyncio.get_event_loop()
    loop_ref.add_signal_handler(signal.SIGTERM, _handle_sigterm)
    loop_ref.add_signal_handler(signal.SIGINT,  _handle_sigterm)

    async def _shutdown_watcher():
        await _shutdown_event.wait()
        print("💾 Фінальне збереження ВСІХ файлів перед зупинкою...")
        save_data()
        try:
            await _save_all_to_db()
            print("✅ Всі дані збережено перед зупинкою")
        except Exception as _se:
            print(f"⚠️ Shutdown save error: {_se}")
        await _db.close_db()
        # Зупиняємо polling
        await dp.stop_polling()

    asyncio.create_task(_shutdown_watcher())

    # Сбрасываем webhook и вытесняем любой другой активный polling-инстанс
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        print("✅ Webhook сброшен — polling запускается как единственный инстанс")
    except Exception as _whe:
        logging.warning(f"delete_webhook: {_whe}")

    # Цикл перезапуска polling — при любом сбое сети/API бот сам восстанавливається
    retry_delay = 5
    while True:
        try:
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                polling_timeout=30,
            )
            break  # нормальне завершення (stop_polling викликано)
        except asyncio.CancelledError:
            print("🛑 Polling скасовано")
            break
        except Exception as e:
            if _shutdown_event.is_set():
                break
            logging.error(f"💥 Polling упал: {e}. Перезапуск через {retry_delay}с...")
            save_data()
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)  # экспоненциальный backoff до 60с

def _apply_data(data: dict) -> None:
    """Заповнює in-memory сховища зі словника (з PostgreSQL або JSON-файлу)."""
    for cid, m in data.get("marriages", {}).items():
        marriages[int(cid)] = {int(u): int(v) for u, v in m.items()}
    for cid, users in data.get("streaks", {}).items():
        streaks[int(cid)] = {}
        for uid, d in users.items():
            streaks[int(cid)][int(uid)] = {
                "count": d.get("count", 0),
                "last": date.fromisoformat(d["last"]) if d.get("last") else None,
            }
    for u, b in data.get("lmn_balances", {}).items():
        try:
            lmn_balances[int(u)] = int(b)
        except (TypeError, ValueError):
            lmn_balances[int(u)] = 0
    global lmn_balance_reset_version, lmn_transfer_version
    lmn_balance_reset_version = int(data.get("lmn_balance_reset_version", 0) or 0)
    lmn_transfer_version = int(data.get("lmn_transfer_version", 0) or 0)
    for cid, r in data.get("reputation", {}).items():
        reputation[int(cid)] = {int(u): v for u, v in r.items()}
    for u, v in data.get("profiles", {}).items():
        profiles[int(u)] = v
    for cid, w in data.get("warnings_db", {}).items():
        warnings_db[int(cid)] = {int(u): v for u, v in w.items()}
    for cid, w in data.get("ru_army_warns", {}).items():
        ru_army_warns[int(cid)] = {int(u): v for u, v in w.items()}
    for cid, r in data.get("chat_rules", {}).items():
        chat_rules[int(cid)] = r
    for cid, m in data.get("chat_members", {}).items():
        chat_members[int(cid)] = {int(u): n for u, n in m.items()}
    for u in data.get("premium_users", []):
        _premium_users.add(int(u))
    for u in data.get("verified_users", []):
        _verified_users.add(int(u))
    for u, v in data.get("aura", {}).items():
        aura[int(u)] = float(v)
    for u, r in data.get("roles", {}).items():
        ROLES[int(u)] = r
    for uname, r in data.get("role_usernames", {}).items():
        _ROLE_USERNAMES[uname] = r
    _saved_pack = data.get("brand_emoji_pack", [])
    if _saved_pack:
        brand.set_pack(_saved_pack, data.get("brand_pack_name", ""))
    global _last_rain_time
    _last_rain_time = data.get("last_rain_time", 0)
    for c, v in data.get("link_guard", {}).items():
        _link_guard[int(c)] = bool(v)
    for c, w in data.get("link_guard_warns", {}).items():
        _link_guard_warns[int(c)] = {int(u): v for u, v in w.items()}
    for c, wl in data.get("link_whitelist", {}).items():
        _link_whitelist[int(c)] = list(wl)
    for u, b in data.get("bank_balances", {}).items():
        bank_balances[int(u)] = int(b)
    for u, value in data.get("bank_withdraw_cd", {}).items():
        try:
            _bwcd_dt = datetime.fromisoformat(value)
            # Нормализуем: naive → Kyiv, aware → приводим к Kyiv
            if _bwcd_dt.tzinfo is None:
                _bwcd_dt = _bwcd_dt.replace(tzinfo=KYIV_TZ)
            else:
                _bwcd_dt = _bwcd_dt.astimezone(KYIV_TZ)
            bank_withdraw_cd[int(u)] = _bwcd_dt
        except (TypeError, ValueError):
            logging.warning("⚠️ Некоректний cooldown банку для user=%s пропущено", u)
    for u, value in data.get("hunt_cooldown", {}).items():
        try:
            _dt = datetime.fromisoformat(value)
            hunt_cooldown[int(u)] = _dt if _dt.tzinfo else _dt.replace(tzinfo=KYIV_TZ)
        except (TypeError, ValueError):
            logging.warning("⚠️ Некоректний cooldown охоти для user=%s пропущено", u)
    for u, value in data.get("alchemy_cooldown", {}).items():
        try:
            _dt = datetime.fromisoformat(value)
            alchemy_cooldown[int(u)] = _dt if _dt.tzinfo else _dt.replace(tzinfo=KYIV_TZ)
        except (TypeError, ValueError):
            logging.warning("⚠️ Некоректний cooldown алхимии для user=%s пропущено", u)
    for cid, run in data.get("team_alchemy_runs", {}).items():
        try:
            team_alchemy_runs[int(cid)] = {
                "date": str(run.get("date", "")),
                "participants": {
                    int(uid): str(name)
                    for uid, name in run.get("participants", {}).items()
                },
                "completed": bool(run.get("completed", False)),
            }
        except (AttributeError, TypeError, ValueError):
            logging.warning("⚠️ Некорректный командный ритуал для chat=%s пропущен", cid)
    global _save_update_sent
    _save_update_sent = bool(data.get("save_update_sent", False))
    global pending_notifications
    pending_notifications = list(data.get("pending_notifications", []))
    for _p in data.get("marriage_proposals", []):
        try:
            _key = (int(_p["chat_id"]), int(_p["target_id"]))
            marriage_proposals[_key] = {
                "proposer_id":  int(_p["proposer_id"]),
                "proposer_full": str(_p.get("proposer_full", "")),
            }
        except (KeyError, TypeError, ValueError):
            pass
    # V6
    global v6_announced
    v6_announced = bool(data.get("v6_announced", False))
    for u, v in data.get("user_xp", {}).items():
        user_xp[int(u)] = int(v)
    for c, m in data.get("user_messages", {}).items():
        user_messages[int(c)] = {int(u): int(cnt) for u, cnt in m.items()}
    for u, v in data.get("daily_cooldown", {}).items():
        daily_cooldown[int(u)] = str(v)
    for u, v in data.get("user_achievements", {}).items():
        user_achievements[int(u)] = list(v)
    for c, v in data.get("mod_logs", {}).items():
        mod_logs[int(c)] = list(v)
    for c, v in data.get("reports_db", {}).items():
        reports_db[int(c)] = list(v)
    for u, v in data.get("referrals", {}).items():
        referrals[int(u)] = int(v)
    for u, v in data.get("referral_counts", {}).items():
        referral_counts[int(u)] = int(v)
    for c, v in data.get("raid_mode", {}).items():
        raid_mode[int(c)] = bool(v)
    for c, v in data.get("antispam_mode", {}).items():
        antispam_mode[int(c)] = bool(v)
    for u, v in data.get("games_played", {}).items():
        _games_played[int(u)] = int(v)
    for u, v in data.get("games_won", {}).items():
        _games_won[int(u)] = int(v)
    for u, v in data.get("bonus_weekly_cd", {}).items():
        bonus_weekly_cd[int(u)] = str(v)
    for u, v in data.get("daily_games", {}).items():
        daily_games[int(u)] = str(v)
    for u, v in data.get("daily_msg_cnt", {}).items():
        daily_msg_cnt[int(u)] = dict(v)
    for u, v in data.get("tasks_bonus_cd", {}).items():
        tasks_bonus_cd[int(u)] = str(v)
    for k, v in data.get("marriage_dates", {}).items():
        marriage_dates[str(k)] = str(v)
    # кулдауны работы/рыбалки/ограбления (datetime → сохраняем ISO-строкой)
    _tz = ZoneInfo("Europe/Kyiv")
    for u, v in data.get("work_cooldown", {}).items():
        try:
            work_cooldown[int(u)] = datetime.fromisoformat(str(v)).replace(tzinfo=_tz)
        except Exception:
            pass
    for u, v in data.get("fish_cooldown", {}).items():
        try:
            fish_cooldown[int(u)] = datetime.fromisoformat(str(v)).replace(tzinfo=_tz)
        except Exception:
            pass
    for u, v in data.get("rob_cooldown", {}).items():
        try:
            rob_cooldown[int(u)] = datetime.fromisoformat(str(v)).replace(tzinfo=_tz)
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
