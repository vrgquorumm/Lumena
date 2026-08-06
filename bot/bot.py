"""
Лумена Бот — полнофункциональный Telegram бот
Версия 5.0
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
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

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

_edit_sessions:     dict[int, str]  = {}  # uid → ключ текста на редактирование (ЛС с фаундером)
_btn_edit_sessions: dict[int, dict] = {}    # uid → {"key": str, "step": "label"|"url"}  (редактор кнопок)
_style_edit_sessions: dict[int, str] = {}  # uid → style_key  (редактор оформления)
# (chat_id, message_id) → text_key — трекинг исходящих сообщений для reply-редактора
_tracked_bot_msgs:  dict[tuple[int, int], str] = {}

# ═══════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не найден BOT_TOKEN!")

OWNER_USERNAME = "hdrttttttt"
OWNER_ID       = 8655306548
SUPER_IDS      = {OWNER_ID}   # могут банить/мутить даже админов
BOT_VERSION = "5.0"
DATA_FILE = "data/bot_data.json"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ═══════════════════════════════════════════════════════
# ХРАНИЛИЩА ДАННЫХ
# ═══════════════════════════════════════════════════════
warnings_db = {}          # {chat_id: {user_id: count}}
ru_army_warns = {}        # {chat_id: {user_id: count}} — варны за пропаганду РА
marriages = {}            # {chat_id: {user_id: partner_id}}
marriage_proposals = {}   # {(chat_id, target_id): {proposer_id, proposer_name, proposer_full}}
streaks = {}              # {chat_id: {user_id: {"count": int, "last": date}}}
lmn_balances = {}         # {user_id: int}
reputation = {}           # {chat_id: {user_id: int}}
work_cooldown = {}        # {user_id: datetime}
fish_cooldown = {}        # {user_id: datetime}
rob_cooldown = {}         # {user_id: datetime}
chat_rules = {}           # {chat_id: str}
hangman_games = {}        # {chat_id: {"word": str, "guessed": set, "tries": int}}
roulette_players = {}     # {chat_id: {user_id: name}}
profiles = {}             # {user_id: {"bio": str, "title": str}}
chat_members = {}         # {chat_id: {user_id: full_name}} — все кто писал в чате
support_sessions = {}    # {user_id: True} — ожидают ввода обращения к администрации
_active_rain: dict = {}  # {chat_id: int} — активный дождь монет LMN
_last_rain_time: float = 0.0  # unix-timestamp последнего дождя
_premium_users:  set = set()  # {user_id} — купили или получили VIP-анкету
_verified_users: set = set()  # {user_id} — прошли верификацию в ЛС

# ── Аура ──────────────────────────────────────────────
aura:              dict[int, float] = {}  # {user_id: float}  0.0–100.0 %
_aura_credited:    set              = set()  # {(chat_id, msg_id)} — плюс уже засчитан
_msg_authors:      dict             = {}     # {(chat_id, msg_id): user_id} — для аура-реакций

# ── Синхронизация чатов ───────────────────────────────
# Оба чата (основной + админ) используют общую экономику.
# Canonical ID = pub_chat; любые обращения к mod_chat → переадресуются на pub_chat.
_ECON_CANONICAL: dict[int, int] = {}   # secondary_cid → primary_cid  (заполняется в main)

ANKETA_PREMIUM_STARS = 300  # стоимость VIP-анкеты в Stars
# Username-ы которые всегда имеют VIP (вечный бесплатный премиум)
# ── Роли ──────────────────────────────────────────────
# Иерархия: founder > lead_admin > co_admin > admin > moderator
ROLES: dict[int, str] = {}          # {user_id: role}
ROLE_NAMES: dict[str, str] = {
    "lead_admin":  "Lead Admin",
    "co_admin":    "Co-Admin",
    "admin":       "Admin",
    "moderator":   "Moderator",
}
ROLE_HIERARCHY = ["lead_admin", "co_admin", "admin", "moderator"]
# Имена пользователей для быстрой связки при первом контакте
_ROLE_USERNAMES: dict[str, str] = {
    "veroniksssxa": "lead_admin",
}

_PREMIUM_ALWAYS = {"hdrttttttt", "veroniksssxa"}

# ── ИИ-агент ──────────────────────────────────────────
_BOT_ID: int = 0          # заполняется в main()
_BOT_USERNAME: str = ""   # заполняется в main()

# ═══════════════════════════════════════════════════════
# ПЕРСИСТЕНТНОСТЬ ДАННЫХ
# ═══════════════════════════════════════════════════════
def save_data():
    """Сохраняет все ключевые хранилища в JSON-файл."""
    os.makedirs("data", exist_ok=True)
    # Стрики: date → str
    streaks_serial = {}
    for cid, users in streaks.items():
        streaks_serial[str(cid)] = {}
        for uid, d in users.items():
            streaks_serial[str(cid)][str(uid)] = {
                "count": d.get("count", 0),
                "last": d["last"].isoformat() if d.get("last") else None,
            }
    payload = {
        "marriages":    {str(c): {str(u): v for u, v in m.items()} for c, m in marriages.items()},
        "streaks":      streaks_serial,
        "lmn_balances": {str(u): b for u, b in lmn_balances.items()},
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
    }
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ save_data error: {e}")

def load_data():
    """Загружает данные из JSON-файла при старте."""
    if not os.path.exists(DATA_FILE):
        return
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
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
            lmn_balances[int(u)] = b
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
        print(f"✅ Данные загружены: {DATA_FILE}")
    except Exception as e:
        print(f"⚠️ load_data error: {e}")

async def auto_save_loop():
    """Автосохранение каждые 60 секунд."""
    while True:
        await asyncio.sleep(60)
        save_data()
        print("💾 Автосохранение выполнено")

async def coin_rain_loop():
    """Дождь монет LMN строго каждые 6 часов. Перезапуск бота не сбрасывает таймер."""
    global _last_rain_time
    RAIN_INTERVAL = 6 * 3600  # 6 часов в секундах

    await asyncio.sleep(30)   # небольшая задержка после старта бота

    while True:
        import time
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
    """Работает и для Message, и для CallbackQuery — проверяет по ID и username."""
    u = getattr(msg, "from_user", None)
    if u is None:
        return False
    return u.id == OWNER_ID or (u.username or "").lower() == OWNER_USERNAME.lower()

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

def is_verified(uid: int) -> bool:
    """Прошёл ли пользователь верификацию. Фаундер всегда верифицирован."""
    if uid in SUPER_IDS:
        return True
    return uid in _verified_users

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
    if data["last"] == today:
        if reply_msg: await reply_msg.reply("🔥 Ты уже отмечался сегодня!")
        return False
    data["count"] += 1
    data["last"] = today
    streaks[cid][user_id] = data
    if reply_msg:
        cnt = data["count"]
        fire = "🔥🔥🔥 Легенда!" if cnt >= 30 else "🔥🔥 Горишь!" if cnt >= 14 else "🔥 Растёт!"
        name = reply_msg.from_user.first_name
        text = (
            f"🖤  L U M E N A  🖤\n\n"
            f"◾ Чекин выполнен!\n\n"
            f"👤 {name}\n"
            f"📅 Дней подряд: <b>{cnt}</b>\n"
            f"◆ {fire}\n\n"
            f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"
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
        except Exception:
            pass
    return result


async def _send_custom(chat_id: int, key: str, fallback_html: str,
                       name: str | None = None, **kwargs):
    """Отправляет кастомный текст фаундера (с Premium emoji) или HTML fallback.
    name — сырое (не HTML-escaped) имя для подстановки {name} в entities-тексте."""
    ct = brand.get_custom_text(key)
    if ct:
        text, ents_data = ct
        if name is not None:
            text, ents_data = brand.substitute_name(text, ents_data, name)
        ents = _build_entities(ents_data)
        return await bot.send_message(chat_id, text, entities=ents or None, **kwargs)
    return await bot.send_message(chat_id, fallback_html, parse_mode="HTML", **kwargs)


async def _answer_custom(msg, key: str, fallback_html: str,
                         name: str | None = None, **kwargs):
    """Как _send_custom, но через msg.answer() — не нужен chat_id.
    Автоматически трекает отправленное сообщение для reply-редактора фаундера.
    Приоритет: кастомный текст → DEFAULT_TEXTS → fallback_html."""
    ct = brand.get_custom_text(key)
    if ct:
        text, ents_data = ct
        if name is not None:
            text, ents_data = brand.substitute_name(text, ents_data, name)
        ents = _build_entities(ents_data)
        sent = await msg.answer(text, entities=ents or None, **kwargs)
    else:
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
        if fmt:
            try:
                text = text.format(**fmt)
            except (KeyError, ValueError):
                pass
        ents = _build_entities(ents_data)
        sent = await msg.reply(text, entities=ents or None)
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
            return
    # Трекаем для reply-редактора
    if key in brand.TEXT_LABELS and sent is not None:
        _tracked_bot_msgs[(sent.chat.id, sent.message_id)] = key


async def _edit_custom(message, key: str, fallback_html: str,
                       name: str | None = None, **kwargs):
    """Как _send_custom, но редактирует существующее сообщение (edit_text)."""
    ct = brand.get_custom_text(key)
    if ct:
        text, ents_data = ct
        if name is not None:
            text, ents_data = brand.substitute_name(text, ents_data, name)
        ents = _build_entities(ents_data)
        return await message.edit_text(text, entities=ents or None, **kwargs)
    return await message.edit_text(fallback_html, parse_mode="HTML", **kwargs)


def _btn_text(key: str, default: str) -> str:
    """Возвращает кастомный текст кнопки или дефолт (без entities — Telegram не поддерживает)."""
    ct = brand.get_custom_text(key)
    return ct[0].strip() if ct else default


def parse_time_and_reason(args: str) -> tuple:
    """Returns (timedelta, reason_str). First word parsed as time; rest is reason."""
    if not args:
        return timedelta(minutes=1), ""
    parts = args.strip().split(maxsplit=1)
    first = parts[0].lower().replace("м","m").replace("ч","h").replace("д","d")
    try:
        if first.endswith("m"):   delta = timedelta(minutes=int(first[:-1]))
        elif first.endswith("h"): delta = timedelta(hours=int(first[:-1]))
        elif first.endswith("d"): delta = timedelta(days=int(first[:-1]))
        else:                     delta = timedelta(minutes=int(first))
        return delta, (parts[1] if len(parts) > 1 else "")
    except:
        return timedelta(minutes=1), args.strip()

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
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    user = await get_user(msg, command)
    if not user: return await msg.reply("Ответь на сообщение. Пример: !мут 5м причина")
    if is_owner(msg):
        await _demote_if_needed(msg.chat.id, user.id)
    delta, reason = parse_time_and_reason(command.args or "")
    until = now_kyiv() + delta
    try:
        await bot.restrict_chat_member(msg.chat.id, user.id,
            permissions=ChatPermissions(can_send_messages=False), until_date=until)
        await msg.reply(
            mod_card(f"Мут до {until.strftime('%d.%m %H:%M')}", user, reason=reason),
            parse_mode="HTML")
    except Exception as e: await msg.reply(f"❌ {e}")

@dp.message(Command("unmute"))
async def cmd_unmute(msg: Message, command: CommandObject):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    user = await get_user(msg, command)
    if not user: return await msg.reply("Ответь на сообщение")
    try:
        await bot.restrict_chat_member(msg.chat.id, user.id,
            permissions=ChatPermissions(can_send_messages=True, can_send_media_messages=True,
                can_send_other_messages=True, can_add_web_page_previews=True))
        await msg.reply(mod_card("Размучен 🔊", user), parse_mode="HTML")
    except Exception as e: await msg.reply(f"❌ {e}")

@dp.message(Command("ban"))
async def cmd_ban(msg: Message, command: CommandObject):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    user = await get_user(msg, command)
    if not user: return await msg.reply("Ответь на сообщение или укажи ID")
    if is_super(msg):
        await _demote_if_needed(msg.chat.id, user.id)
    _, reason = parse_time_and_reason(command.args or "")
    try:
        await bot.ban_chat_member(msg.chat.id, user.id)
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
    try:
        await bot.restrict_chat_member(msg.chat.id, user.id,
            permissions=ChatPermissions(can_send_messages=False), until_date=until)
        await msg.reply(
            mod_card(f"Принудительный мут до {until.strftime('%d.%m %H:%M')} 🔇", user,
                     extra="⚠️ Права сняты", reason=reason),
            parse_mode="HTML")
    except Exception as e: await msg.reply(f"❌ {e}")

@dp.message(Command("unban"))
async def cmd_unban(msg: Message, command: CommandObject):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    user = await get_user(msg, command)
    if not user: return await msg.reply("Укажи ID")
    try:
        await bot.unban_chat_member(msg.chat.id, user.id)
        await msg.reply(mod_card("Разбанен ✅", user), parse_mode="HTML")
    except Exception as e: await msg.reply(f"❌ {e}")

@dp.message(Command("kick"))
async def cmd_kick(msg: Message, command: CommandObject):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    user = await get_user(msg, command)
    if not user: return await msg.reply("Ответь на сообщение")
    _, reason = parse_time_and_reason(command.args or "")
    try:
        await bot.ban_chat_member(msg.chat.id, user.id)
        await bot.unban_chat_member(msg.chat.id, user.id)
        await msg.reply(mod_card("Кик 👢", user, reason=reason), parse_mode="HTML")
    except Exception as e: await msg.reply(f"❌ {e}")

@dp.message(Command("warn"))
async def cmd_warn(msg: Message, command: CommandObject):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    user = await get_user(msg, command)
    if not user: return await msg.reply("Ответь на сообщение")
    chat_id, uid = msg.chat.id, user.id
    warnings_db.setdefault(chat_id, {})
    warnings_db[chat_id][uid] = warnings_db[chat_id].get(uid, 0) + 1
    count = warnings_db[chat_id][uid]
    _, reason = parse_time_and_reason(command.args or "")
    if count >= 3:
        await bot.ban_chat_member(chat_id, uid)
        warnings_db[chat_id][uid] = 0
        await msg.reply(
            mod_card("Бан 🚫 (3 варна)", user, extra="⚠️ Достигнут лимит предупреждений", reason=reason),
            parse_mode="HTML")
    else:
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
    marriage_proposals[(chat_id, target.id)] = {
        "proposer_id": proposer.id,
        "proposer_full": proposer.full_name,
    }
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💍 Принять", callback_data=f"mar_y_{proposer.id}"),
        InlineKeyboardButton(text="❌ Отказать", callback_data=f"mar_n_{proposer.id}"),
    ]])
    await msg.reply(
        f"💍 <b>{proposer.full_name}</b> делает предложение <b>{target.full_name}</b>!\n\n"
        f"{target.full_name}, ты принимаешь предложение?",
        parse_mode="HTML", reply_markup=kb
    )

@dp.callback_query(F.data.startswith("mar_"))
async def marry_callback(cb: CallbackQuery):
    parts = cb.data.split("_")
    action = parts[1]
    proposer_id = int(parts[2])
    chat_id = cb.message.chat.id
    target_id = cb.from_user.id
    proposal = marriage_proposals.get((chat_id, target_id))
    if not proposal or proposal["proposer_id"] != proposer_id:
        await cb.answer("Это предложение не для тебя 😄", show_alert=True)
        return
    del marriage_proposals[(chat_id, target_id)]
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
        marriages.setdefault(cid, {})
        marriages[cid][proposer_id] = target_id
        marriages[cid][target_id] = proposer_id
        add_balance(proposer_id, 500)
        add_balance(target_id, 500)
        save_data()
        header = random.choice(_marry_accept)
        await cb.message.edit_text(
            f"{brand.hdr()}\n\n"
            f"{header}\n\n"
            f"💕 <b>{proposal['proposer_full']}</b>\n"
            f"❤️ <b>{cb.from_user.full_name}</b>\n\n"
            f"🎊 +500 LMN каждому в подарок!\n\n"
            f"{brand.div()}",
            parse_mode="HTML"
        )
    else:
        header = random.choice(_marry_reject)
        reject_lines = [
            f"<b>{cb.from_user.full_name}</b> отказал(а) <b>{proposal['proposer_full']}</b>",
            f"<b>{proposal['proposer_full']}</b> получил(а) отказ от <b>{cb.from_user.full_name}</b>",
            f"<b>{cb.from_user.full_name}</b> не готов(а)... <b>{proposal['proposer_full']}</b> ждёт",
        ]
        await cb.message.edit_text(
            f"{brand.hdr()}\n\n"
            f"{header}\n\n"
            f"{random.choice(reject_lines)}\n\n"
            f"{brand.div()}",
            parse_mode="HTML"
        )
    await cb.answer()

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
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"{random.choice(_divorce_txt)}\n\n"
        f"<b>{msg.from_user.full_name}</b> и <b>{partner_name}</b> расстались\n\n"
        f"<i>{random.choice(_divorce_comment)}</i>\n\n"
        f"{brand.div()}",
        parse_mode="HTML")

@dp.message(Command("marriages"))
async def cmd_marriages(msg: Message):
    chat_marriages = marriages.get(econ_cid(msg.chat.id), {})
    valid = {u: p for u, p in chat_marriages.items() if p in chat_marriages}
    if not valid:
        return await msg.reply("💍 В этом чате пока нет браков")
    seen = set()
    pairs = []
    for u1, u2 in valid.items():
        if u1 in seen or u2 in seen: continue
        seen.add(u1); seen.add(u2)
        pairs.append((u1, u2))
    if not pairs:
        return await msg.reply("💍 В этом чате пока нет браков")
    lines = [
        f"{brand.hdr()}\n",
        f"💍 Браки чата  ({len(pairs)} пар)",
        f"{brand.div()}",
    ]
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
        lines.append(f"{i}. 💕 <b>{n1}</b> ❤️ <b>{n2}</b>")
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
    data = streaks.get(msg.chat.id, {}).get(msg.from_user.id, {"count": 0})
    count = data["count"]
    if count >= 30:   fire = "🔥🔥🔥 Легенда!"
    elif count >= 14: fire = "🔥🔥 Горишь!"
    elif count >= 7:  fire = "🔥 Неплохо!"
    elif count >= 3:  fire = "✨ Начало!"
    else:             fire = "🆕 Старт"
    name = msg.from_user.first_name
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🔥 Стрик · {name}\n\n"
        f"📅 Дней подряд: <b>{count}</b>\n"
        f"⚡ {fire}\n\n"
        f"{brand.div()}",
        parse_mode="HTML"
    )

@dp.message(Command("topstreak"))
async def cmd_topstreak(msg: Message):
    chat_streaks = streaks.get(msg.chat.id, {})
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
    streaks.get(msg.chat.id, {}).pop(user.id, None)
    await msg.reply("Стрик сброшен")

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
    await msg.reply(
        f"{brand.hdr()}\n\n"
        + brand.get_text("balance", name=name, icon=icon, balance=fmt_lmn(bal), tier=tier) +
        f"\n\n{brand.div()}",
        parse_mode="HTML"
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
    if target.id == msg.from_user.id: return await msg.reply("❌ Нельзя переводить себе")
    if target.is_bot: return await msg.reply("❌ Боту нельзя переводить монеты")
    if not command.args: return await msg.reply("Укажи сумму: <b>дать [сумма]</b>", parse_mode="HTML")
    try: amount = int(command.args.split()[0])
    except: return await msg.reply("❌ Укажи целое число")
    if amount <= 0: return await msg.reply("❌ Сумма должна быть больше нуля")
    sender_bal = get_balance(msg.from_user.id)
    if sender_bal < amount:
        return await msg.reply(
            f"❌ Недостаточно LMN\n"
            f"У тебя: <b>{fmt_lmn(sender_bal)}</b>, нужно: <b>{fmt_lmn(amount)}</b>",
            parse_mode="HTML")
    add_balance(msg.from_user.id, -amount)
    add_balance(target.id, amount)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        + brand.get_text("give",
            from_name=msg.from_user.full_name, to_name=target.full_name,
            amount=fmt_lmn(amount), balance=fmt_lmn(get_balance(msg.from_user.id))) +
        f"\n\n{brand.div()}",
        parse_mode="HTML"
    )

@dp.message(Command("work"))
async def cmd_work(msg: Message):
    uid = msg.from_user.id
    now = now_kyiv()
    last = work_cooldown.get(uid)
    if last and (now - last).seconds < 3600:
        mins = 60 - (now - last).seconds // 60
        return await reply_t(msg, "work_cooldown", mins=mins)
    earned = random.randint(100, 800)
    add_balance(uid, earned)
    work_cooldown[uid] = now
    jobs = ["программист","дизайнер","повар","водитель","учитель","врач",
            "строитель","менеджер","стример","блогер","музыкант","художник"]
    job = random.choice(jobs)
    new_bal = get_balance(uid)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        + brand.get_text("work", job=job, earned=fmt_lmn(earned), balance=fmt_lmn(new_bal)) +
        f"\n\n{brand.div()}",
        parse_mode="HTML",
    )

@dp.message(Command("fish"))
async def cmd_fish(msg: Message):
    uid = msg.from_user.id
    now = now_kyiv()
    last = fish_cooldown.get(uid)
    if last and (now - last).seconds < 1800:
        mins = 30 - (now - last).seconds // 60
        return await reply_t(msg, "fish_cooldown", mins=mins)
    fish_cooldown[uid] = now
    roll = random.random()
    if roll < 0.1:
        earned = random.randint(500, 2000)
        item = "🐟 Огромная рыба!"
    elif roll < 0.4:
        earned = random.randint(100, 499)
        item = "🐠 Хорошая рыба"
    elif roll < 0.7:
        earned = random.randint(10, 99)
        item = "🐡 Маленькая рыбка"
    else:
        earned = 0
        item = "👟 Старый ботинок..."
    add_balance(uid, earned)
    new_bal = get_balance(uid)
    result_line = f"+{fmt_lmn(earned)} LMN" if earned else "Ничего не поймал 😔"
    await msg.reply(
        f"{brand.hdr()}\n\n"
        + brand.get_text("fish", item=item, result=result_line, balance=fmt_lmn(new_bal)) +
        f"\n\n{brand.div()}",
        parse_mode="HTML",
    )

@dp.message(Command("casino"))
async def cmd_casino(msg: Message, command: CommandObject):
    if not command.args: return await msg.reply("Укажи ставку: казино [сумма]")
    try: bet = int(command.args.split()[0])
    except: return await msg.reply("Укажи число")
    if bet <= 0: return await msg.reply("Ставка должна быть положительной")
    if get_balance(msg.from_user.id) < bet: return await msg.reply("❌ Недостаточно LMN")
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

@dp.message(Command("slots"))
async def cmd_slots(msg: Message, command: CommandObject):
    if not command.args: return await msg.reply("Укажи ставку: слоты [сумма]")
    try: bet = int(command.args.split()[0])
    except: return await msg.reply("Укажи число")
    if bet <= 0: return await msg.reply("Ставка должна быть положительной")
    if get_balance(msg.from_user.id) < bet: return await msg.reply("❌ Недостаточно LMN")
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
    if not msg.reply_to_message: return await msg.reply("Ответь на сообщение жертвы")
    robber = msg.from_user
    victim = msg.reply_to_message.from_user
    if victim.id == robber.id: return await msg.reply("❌ Нельзя грабить самого себя")
    if victim.is_bot: return await msg.reply("❌ Нельзя грабить бота")
    # Проверяем баланс жертвы ДО кулдауна — не тратим попытку зря
    vic_bal = get_balance(victim.id)
    if vic_bal < 100: return await msg.reply("💸 У жертвы нет денег 😅")
    now = now_kyiv()
    last = rob_cooldown.get(robber.id)
    if last and (now - last).seconds < 7200:
        return await msg.reply("⏳ Следующее ограбление через 2 часа")
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

@dp.message(Command("richest"))
async def cmd_richest(msg: Message):
    if not lmn_balances: return await msg.reply("💸 Пока у всех пустые кошельки 😅")
    # Фильтруем только участников текущего чата
    chat_uids = chat_members.get(msg.chat.id, set())
    if chat_uids:
        filtered = {uid: bal for uid, bal in lmn_balances.items() if uid in chat_uids}
    else:
        filtered = lmn_balances
    if not filtered:
        return await msg.reply("💸 Пока у всех пустые кошельки 😅")
    top = sorted(filtered.items(), key=lambda x: x[1], reverse=True)[:10]
    medals = ["🥇","🥈","🥉"] + ["4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines = [
        f"{brand.hdr()}\n",
        "💰 Топ богачей чата",
        f"{brand.div()}",
    ]
    for i, (uid, bal) in enumerate(top):
        try:
            m = await bot.get_chat_member(msg.chat.id, uid)
            name = m.user.full_name
        except: name = f"ID {uid}"
        lines.append(f"{medals[i]} <b>{name}</b>  —  {fmt_lmn(bal)} LMN")
    lines.append(f"\n{brand.div()}")
    lines.append(f"<i>В чате в обороте: {fmt_lmn(sum(filtered.values()))} LMN</i>")
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
            name = m.user.full_name
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
    add_rep(msg.chat.id, target.id, 1)
    total = get_rep(msg.chat.id, target.id)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"⬆️ +1 репутация\n\n"
        f"👤 <b>{target.full_name}</b>\n"
        f"📊 Итого: <b>{total:+d}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML")

@dp.message(Command("downvote"))
async def cmd_downvote(msg: Message):
    if not msg.reply_to_message: return await msg.reply("Ответь на сообщение")
    target = msg.reply_to_message.from_user
    if target.id == msg.from_user.id: return await msg.reply("Себе нельзя 😄")
    add_rep(msg.chat.id, target.id, -1)
    total = get_rep(msg.chat.id, target.id)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"⬇️ -1 репутация\n\n"
        f"👤 <b>{target.full_name}</b>\n"
        f"📊 Итого: <b>{total:+d}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML")

@dp.message(Command("toprep"))
async def cmd_toprep(msg: Message):
    chat_rep = reputation.get(msg.chat.id, {})
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
            name = m.user.full_name
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
    if not msg.reply_to_message: return await msg.reply("Ответь на сообщение")
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
                  "Отличный день для лидерства и инициативы. Люди потянутся к твоей энергии."],
    "Телец":     ["Финансовые дела складываются благоприятно. Не торопи события — всё придёт в своё время.",
                  "Уют и комфорт важны сегодня. Побалуй себя чем-то приятным — ты заслужил(а).",
                  "Упрямство сегодня ни к чему — попробуй услышать другую точку зрения.",
                  "День для практических дел и планирования. Твой трудолюбивый подход принесёт плоды."],
    "Близнецы":  ["Общение сегодня на высоте — заведи новые знакомства или восстанови старые связи.",
                  "Идеи приходят одна за другой. Запишь — пригодятся. Не распыляйся на всё сразу.",
                  "Любопытство приведёт тебя к интересному открытию. Следуй за ним без колебаний.",
                  "Сегодня легко убедить кого угодно в чём угодно — используй этот дар мудро."],
    "Рак":       ["Семья и близкие — главный приоритет сегодня. Позаботься о тех, кто рядом.",
                  "Интуиция обострена — прислушайся к внутреннему голосу, особенно в вечерние часы.",
                  "Эмоции могут захлёстывать — дай себе время прийти в равновесие, прежде чем реагировать.",
                  "Уютный вечер дома восстановит силы лучше любого другого отдыха."],
    "Лев":       ["Ты в центре внимания — и это заслуженно! День для самовыражения и творчества.",
                  "Щедрость сегодня вернётся к тебе сторицей. Не жалей тепла для окружающих.",
                  "Амбиции зовут вперёд — но убедись, что цель реальна, прежде чем рваться к ней.",
                  "Твоя харизма открывает двери. Воспользуйся этим для важного разговора или встречи."],
    "Дева":      ["День для порядка и системности. Разбери завалы — физические и ментальные.",
                  "Внимание к деталям спасёт от ошибки, которую другие не заметят.",
                  "Критика сегодня лучше воспринимается — прими её конструктивно и используй для роста.",
                  "Помощь другим принесёт больше радости, чем ожидаешь. Не отказывай в поддержке."],
    "Весы":      ["Гармония в отношениях — главная тема дня. Ищи компромисс, а не победу.",
                  "Эстетика и красота вдохновляют — займись тем, что приносит визуальное удовольствие.",
                  "Трудно принять решение? Доверяй чувству справедливости — оно тебя не подведёт.",
                  "Партнёрство и сотрудничество принесут лучшие результаты, чем одиночная работа."],
    "Скорпион":  ["Интенсивный день — эмоции глубокие, но управляемые. Трансформация близко.",
                  "Тайна или скрытая информация выйдет на поверхность. Будь готов к открытиям.",
                  "Страсть и решимость — твои главные козыри сегодня. Направь их в созидательное русло.",
                  "Интуиция на пике. Если что-то чувствуется неправильным — так оно и есть."],
    "Стрелец":   ["Приключения и новые горизонты зовут! День для путешествий, пусть даже мысленных.",
                  "Оптимизм заразителен — поделись им с окружающими. Ты умеешь вдохновлять.",
                  "Честность — твоя сила. Скажи правду, даже если это непросто — потом будешь рад(а).",
                  "Учёба и философские размышления принесут неожиданные инсайты."],
    "Козерог":   ["Терпение и труд — всё перетрут. Сегодня пожинаешь плоды вчерашних усилий.",
                  "Карьера и репутация в фокусе. Серьёзный, ответственный подход оценят по достоинству.",
                  "Не бери на себя слишком много — делегируй и доверяй другим.",
                  "Долгосрочное планирование принесёт больше радости, чем сиюминутные решения."],
    "Водолей":   ["Оригинальные идеи пробивают путь к успеху. Не бойся быть не таким, как все.",
                  "Дружба и командная работа — ключи к сегодняшним достижениям.",
                  "Гуманизм и забота о других наполнят день смыслом. Помоги тому, кто в этом нуждается.",
                  "Технологии и инновации — твоя стихия сегодня. Изучи что-то новое."],
    "Рыбы":      ["Мечты яркие и наполненные — запиши их, они несут послание.",
                  "Творчество и искусство помогут выразить то, что сложно облечь в слова.",
                  "Сострадание привлечёт к тебе людей, которым нужна поддержка. Ты справишься.",
                  "Граница между реальностью и фантазией размыта — это источник вдохновения, а не слабость."],
}
SUPERPOWERS = ["🦸 Телепатия — читать мысли","⚡ Молния — управлять электричеством","🔥 Пирокинез — управлять огнём","❄️ Криокинез — управлять льдом","🌀 Телепортация","💨 Полёт","🛡️ Неуязвимость","🔮 Предвидение будущего","👻 Невидимость","🧲 Управление металлом","⏱️ Остановка времени","🌊 Управление водой"]
PROFESSIONS = ["👨‍💻 Программист","🎨 Художник","🎵 Музыкант","🧑‍🍳 Шеф-повар","✈️ Пилот","🧑‍⚕️ Врач","🏗️ Архитектор","📸 Фотограф","🎭 Актёр","📝 Писатель","🔬 Учёный","🌿 Фермер","🧑‍🏫 Учитель","🕵️ Детектив","🚀 Астронавт","🎮 Геймдизайнер","⚽ Спортсмен","🎪 Иллюзионист"]
ANIMALS = ["🦁 Лев — царь зверей","🐬 Дельфин — интеллект моря","🦅 Орёл — символ свободы","🐼 Панда — редкость природы","🐺 Волк — дух стаи","🦋 Бабочка — символ преображения","🐢 Черепаха — долгожитель","🦊 Лиса — хитрость и ум","🐧 Пингвин — верность паре","🦋 Осьминог — мастер маскировки"]
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
    await reply_t(msg, "fortune_result", result=result)

async def cmd_8ball(msg: Message, command: CommandObject = None):
    if not (command and command.args): return await msg.reply("Задай вопрос: 8ball [вопрос]")
    await msg.reply(f"🎱 {random.choice(EIGHT_BALL)}")

async def cmd_tarot(msg: Message):
    card, meaning = random.choice(TAROT)
    await reply_t(msg, "tarot_result", card=card, meaning=meaning)

async def cmd_horoscope(msg: Message, command: CommandObject = None):
    signs = list(HOROSCOPES.keys())
    raw = (command.args or "").strip()
    # Нечёткий поиск знака зодиака в аргументе
    sign = None
    if raw:
        raw_lower = raw.lower()
        for s in signs:
            if s.lower().startswith(raw_lower[:3]):
                sign = s
                break
    if not sign:
        sign = random.choice(signs)
    text = random.choice(HOROSCOPES[sign])
    await reply_t(msg, "horoscope_result", sign=sign, text=text)
async def cmd_predict(msg: Message, command: CommandObject = None):
    if not (command and command.args): return await msg.reply("Напиши вопрос: предсказать [вопрос]")
    await msg.reply(f"🔮 {random.choice(FORTUNES)}")
async def cmd_destiny(msg: Message): await msg.reply(f"✨ Твоя судьба:\n{random.choice(FORTUNES)}")
async def cmd_superpower(msg: Message): await msg.reply(f"🦸 Твоя суперсила: {random.choice(SUPERPOWERS)}")
async def cmd_profession(msg: Message): await msg.reply(f"💼 Твоя профессия: {random.choice(PROFESSIONS)}")
async def cmd_animal(msg: Message): await msg.reply(f"🐾 Случайное животное: {random.choice(ANIMALS)}")
async def cmd_movie(msg: Message): await msg.reply(f"🎬 Рекомендую посмотреть:\n{random.choice(MOVIES)}")
async def cmd_book(msg: Message): await msg.reply(f"📚 Рекомендую прочитать:\n{random.choice(BOOKS)}")
async def cmd_advice(msg: Message): await msg.reply(random.choice(ADVICES))
async def cmd_motivation(msg: Message): await msg.reply(random.choice(MOTIVATIONS))
async def cmd_myth(msg: Message): await msg.reply(random.choice(MYTHS))
async def cmd_country(msg: Message): await msg.reply(random.choice(COUNTRIES))
async def cmd_color(msg: Message): await msg.reply(random.choice(COLORS))
async def cmd_emoji_combo(msg: Message): await msg.reply(f"✨ Случайный эмодзи-набор: {random.choice(EMOJIS_COMBOS)}")
async def cmd_joke(msg: Message): await msg.reply(random.choice(JOKES))
async def cmd_compliment(msg: Message):
    target = msg.reply_to_message.from_user.first_name if msg.reply_to_message else msg.from_user.first_name
    await msg.reply(f"💖 {target}, {random.choice(COMPLIMENTS).lower()}")
async def cmd_roast(msg: Message):
    target = msg.reply_to_message.from_user.first_name if msg.reply_to_message else msg.from_user.first_name
    await msg.reply(f"🔥 {target}, {random.choice(ROASTS)}")

# ═══════════════════════════════════════════════════════
# ИГРЫ
# ═══════════════════════════════════════════════════════
async def cmd_coin(msg: Message): await msg.reply("🪙 " + random.choice(["Орёл 🦅","Решка 🌟"]))
async def cmd_dice(msg: Message, command: CommandObject = None):
    n = 1
    try: n = min(max(int((command.args or "1").split()[0]), 1), 10)
    except: pass
    results = [random.randint(1,6) for _ in range(n)]
    await msg.reply("🎲 " + " | ".join(map(str, results)) + f" (сумма: {sum(results)})")

async def cmd_roll(msg: Message, command: CommandObject = None):
    sides = 20
    try: sides = int((command.args or "20").split()[0])
    except: pass
    await msg.reply(f"🎲 Бросок d{sides}: <b>{random.randint(1, sides)}</b>", parse_mode="HTML")

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
        a, b = (parts[0], parts[1]) if len(parts)==2 else (1, parts[0])
    except: a, b = 1, 100
    await msg.reply(f"🎲 {random.randint(min(a,b), max(a,b))}")

async def cmd_choose(msg: Message, command: CommandObject = None):
    if not (command and command.args): return await msg.reply("Пример: выбрать пицца суши бургер")
    opts = command.args.split()
    await msg.reply(f"🎯 Я выбираю: <b>{random.choice(opts)}</b>", parse_mode="HTML")

async def cmd_rate(msg: Message, command: CommandObject = None):
    thing = (command.args if command and command.args else None) or \
            (msg.reply_to_message.text if msg.reply_to_message else "это")
    score = random.randint(0, 10)
    bar = "█" * score + "░" * (10-score)
    await msg.reply(f"⭐ Оценка «{thing}»: {score}/10\n[{bar}]")

async def cmd_truth(msg: Message):
    questions = ["Какой твой самый стыдный поступок?","В кого ты сейчас втайне влюблён(а)?","Что никогда никому не рассказывал(а)?","Какую самую большую ложь говорил(а)?","О чём больше всего жалеешь?","Кто твой секретный кумир?","Что первое замечаешь в людях?"]
    await msg.reply(f"🗣️ Правда:\n{random.choice(questions)}")

async def cmd_dare(msg: Message):
    dares = ["Напиши бывшему/бывшей «привет»","Сделай 20 отжиманий прямо сейчас","Спой голосовым сообщением любую песню","Расскажи самый глупый факт о себе","Поменяйся аватаркой на 1 час","Сделай комплимент 3 людям в чате","Поставь лайк всем последним сториз в инстаграм"]
    await msg.reply(f"🔥 Действие:\n{random.choice(dares)}")

async def cmd_riddle(msg: Message):
    q, a = random.choice(RIDDLES)
    await msg.reply(f"🧩 Загадка:\n<b>{q}</b>\n\n<tg-spoiler>Ответ: {a}</tg-spoiler>", parse_mode="HTML")

async def cmd_roulette(msg: Message):
    chat_id = msg.chat.id
    uid = msg.from_user.id
    name = msg.from_user.full_name
    roulette_players.setdefault(chat_id, {})
    if uid in roulette_players[chat_id]:
        return await msg.reply("Ты уже в рулетке! Используй: рулетка_старт")
    roulette_players[chat_id][uid] = name
    await msg.reply(f"🎯 {name} присоединился к рулетке! Игроков: {len(roulette_players[chat_id])}\nНапиши рулетка_старт чтобы начать (минимум 2 игрока)")

async def cmd_roulette_start(msg: Message):
    chat_id = msg.chat.id
    players = roulette_players.get(chat_id, {})
    if len(players) < 2: return await msg.reply("Нужно минимум 2 игрока!")
    loser_id, loser_name = random.choice(list(players.items()))
    roulette_players[chat_id] = {}
    await msg.reply(f"🔫 Барабан крутится...\n💀 Проигравший: <b>{loser_name}</b>!", parse_mode="HTML")

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
    if not game: return await msg.reply("Нет активной игры. Начни: виселица")
    letter = letter.lower()
    if letter in game["guessed"]: return await msg.reply(f"«{letter}» уже было загадано!")
    game["guessed"].add(letter)
    word = game["word"]
    if letter not in word:
        game["tries"] += 1
        if game["tries"] >= 6:
            del hangman_games[chat_id]
            return await msg.reply(f"💀 Проигрыш! Слово было: <b>{word}</b>", parse_mode="HTML")
        remaining = 6 - game["tries"]
        display = " ".join(c if c in game["guessed"] else "_" for c in word)
        return await msg.reply(f"❌ «{letter}» нет! Попыток осталось: {remaining}\n{display}")
    display = " ".join(c if c in game["guessed"] else "_" for c in word)
    if "_" not in display:
        del hangman_games[chat_id]
        return await msg.reply(f"🎉 Победа! Слово: <b>{word}</b>", parse_mode="HTML")
    await msg.reply(f"✅ «{letter}» есть!\n{display}")

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
    streak_data = streaks.get(chat_id, {}).get(uid, {"count": 0})
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
    bio = html.escape(profile_data.get("bio", "не указано"))
    title_str = html.escape(profile_data.get("title", ""))
    lines = [
        f"{brand.hdr()}\n",
        f"👤 Профиль · {html.escape(target.full_name)}",
    ]
    if title_str:
        lines.append(f"🏷 {title_str}")
    lines += [
        f"{brand.div()}",
        f"📝 Bio: {bio}",
        f"💰 Баланс: <b>{fmt_lmn(bal)} LMN</b>",
        f"🔥 Стрик: <b>{streak_data['count']} дней</b>",
        f"⭐ Репутация: <b>{rep_val:+d}</b>",
        f"💍 Брак: {'❤️ ' + partner_name if married else '—'}",
        f"🆔 ID: <code>{uid}</code>",
        f"\n{brand.div()}",
    ]
    await msg.reply("\n".join(lines), parse_mode="HTML")

async def cmd_setbio(msg: Message, command: CommandObject = None):
    if not (command and command.args): return await msg.reply("Использование: сетбио [текст]")
    profiles.setdefault(msg.from_user.id, {})["bio"] = command.args[:100]
    await msg.reply("✅ Bio обновлено!")

async def cmd_settitle(msg: Message, command: CommandObject = None):
    if not (command and command.args): return await msg.reply("Использование: сетзвание [звание]")
    profiles.setdefault(msg.from_user.id, {})["title"] = command.args[:30]
    await msg.reply("✅ Звание установлено!")

async def cmd_botstats(msg: Message):
    total_marriages = sum(len(v)//2 for v in marriages.values())
    total_streaks = sum(len(v) for v in streaks.values())
    total_balance = sum(lmn_balances.values())
    total_warns = sum(sum(v.values()) for v in warnings_db.values())
    total_users = len(lmn_balances)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"📊 Статистика\n\n"
        f"👥 Пользователей: <b>{total_users}</b>\n"
        f"💍 Браков: <b>{total_marriages}</b>\n"
        f"🔥 Активных стриков: <b>{total_streaks}</b>\n"
        f"💰 LMN в обороте: <b>{fmt_lmn(total_balance)}</b>\n"
        f"⚠️ Предупреждений: <b>{total_warns}</b>\n\n"
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
    name = (command.args if command and command.args else None) or msg.from_user.first_name
    n = sum(ord(c) for c in name.lower() if c.isalpha()) % 9 + 1
    meanings = {1:"Лидер и первопроходец",2:"Дипломат и миротворец",3:"Творец и коммуникатор",4:"Строитель и организатор",5:"Искатель свободы",6:"Заботливый и ответственный",7:"Мыслитель и исследователь",8:"Материалист и бизнесмен",9:"Гуманист и альтруист"}
    await msg.reply(f"🔢 Нумерология имени <b>{name}</b>:\nЧисло: {n} — {meanings[n]}", parse_mode="HTML")

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

async def cmd_announce(msg: Message, command: CommandObject = None):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    if not (command and command.args): return await msg.reply("Укажи текст объявления")
    await msg.reply(f"📢 <b>ОБЪЯВЛЕНИЕ</b>\n\n{command.args}", parse_mode="HTML")

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
        "🎰 <b>Удача:</b>\n"
        "<code>казино [сумма]</code> — казино\n"
        "<code>слоты [сумма]</code> — игровой автомат\n\n"
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
        "<code>кнб</code> — камень, ножницы, бумага\n"
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
    "варн": cmd_warn, "снятьварн": cmd_unwarn, "очистить": cmd_purge,
    "ро": cmd_ro, "закрепить": cmd_pin, "открепить": cmd_unpin,
    "название": cmd_title,
    # Стрики
    "чекин": cmd_checkin, "стрик": cmd_streak,
    "топстриков": cmd_topstreak, "топ стриков": cmd_topstreak,
    "сбросстрик": cmd_resetstreak,
    # Валюта
    "баланс": cmd_balance, "кошелёк": cmd_balance,
    "работа": cmd_work, "рыбалка": cmd_fish,
    "казино": cmd_casino, "слоты": cmd_slots, "слот": cmd_slots,
    "ограбить": cmd_rob, "украсть": cmd_rob,
    "дать": cmd_give, "перевести": cmd_give,
    "топбогачей": cmd_richest, "топ богачей": cmd_richest,
    "выдатьадминам": cmd_givetoadmins,
    "выдатьроли": cmd_give_role,
    "наградить": cmd_award,
    "раздать": cmd_razdach,
    "забрать500м": cmd_ownerclaim, "ownerclaim": cmd_ownerclaim,
    # Репутация
    "репутация": cmd_rep, "реп": cmd_rep,
    "+1": cmd_upvote, "плюс": cmd_upvote,
    "-1": cmd_downvote, "минус": cmd_downvote,
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
    "кнб": cmd_rps, "рандом": cmd_random_num,
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
    "сетбио": cmd_setbio, "сетзвание": cmd_settitle,
    "правила": cmd_rules, "сетправила": cmd_setrules,
    "объявление": cmd_announce,
    # Помощь
    "помощь": cmd_support, "команды": cmd_help, "хелп": cmd_help,
    # Фарм (скоро)
    "ферма": _farm_soon, "фарм": _farm_soon, "farm": _farm_soon,
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
    ("coin", cmd_coin), ("dice", cmd_dice), ("rps", cmd_rps),
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
    ("баланс", cmd_balance), ("работа", cmd_work), ("рыбалка", cmd_fish),
    ("казино", cmd_casino), ("слоты", cmd_slots), ("ограбить", cmd_rob),
    ("дать", cmd_give),
    ("чекин", cmd_checkin), ("стрик", cmd_streak),
    ("топстриков", cmd_topstreak),
    ("репутация", cmd_rep),
    ("профиль", cmd_profile), ("айди", cmd_myid), ("инфочат", cmd_chatinfo),
    ("статистика", cmd_botstats), ("пинг", cmd_ping), ("версия", cmd_version),
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
            chat_members.setdefault(event.chat.id, {})[event.from_user.id] = event.from_user.full_name

        if isinstance(event, Message) and event.text:
            handled = await auto_moderate_propaganda(event)
            if handled:
                return   # Пропаганда — цепочку прерываем
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
    pub_msg_id = None
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
                await _ank._send_media_group_to_chat(bot, pub_chat, media_items)
                sent_pub = await bot.send_message(
                    pub_chat, pub_text, parse_mode="HTML",
                    reply_markup=_rkb,
                )
            pub_msg_id = sent_pub.message_id
            pub_ok = True
        except Exception as e:
            print(f"⚠️ pub_chat send error: {e}")

    # 2. Зберігаємо статус approved
    _ank.set_approved(uid, app["answers"], app["username"], app["full_name"],
                      pub_msg_id=pub_msg_id, pub_chat_id=pub_chat)

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
        await cb.answer("⏳ Анкета на проверке — жди решения", show_alert=True)
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

    # Удаляем из паблик-чата если есть
    pub_chat = _ank.get_pub_chat()
    if pub_chat and data and data.get("pub_msg_id"):
        try:
            await bot.delete_message(pub_chat, data["pub_msg_id"])
        except Exception:
            pass

    await cb.message.edit_reply_markup(reply_markup=None)
    await _send_custom(
        uid, "anketa_delete",
        f"🗑 <b>Твоя анкета удалена.</b>\n\nХочешь подать новую — нажми кнопку ниже.",
        reply_markup=_anketa_kb(uid)
    )
    await cb.answer("Анкета удалена", show_alert=True)


@dp.callback_query(F.data.startswith("ank_edit:"))
async def cb_ank_user_edit(cb: CallbackQuery):
    uid = int(cb.data.split(":", 1)[1])
    if cb.from_user.id != uid:
        return await cb.answer("Это не твоя анкета", show_alert=True)

    # Удаляем старую публикацию
    data = _ank.delete_user_anketa(uid)
    pub_chat = _ank.get_pub_chat()
    if pub_chat and data and data.get("pub_msg_id"):
        try:
            await bot.delete_message(pub_chat, data["pub_msg_id"])
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
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.message(Command("start"), F.chat.type == "private")
async def cmd_start_private(msg: Message):
    uid  = msg.from_user.id
    name = html.escape(msg.from_user.first_name or "друг")

    raw_name = msg.from_user.first_name or "друг"
    name     = html.escape(raw_name)

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
    if is_verified(cb.from_user.id):
        await cb.answer("Ты уже верифицирован ✅", show_alert=False)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=brand.btn_label("verify_confirm"),
            callback_data="verify:done",
        )]
    ])
    await _edit_custom(
        cb.message, "verify_prompt",
        "🔐 <b>Верификация</b>\n\n"
        "Нажми кнопку ниже, чтобы подтвердить что ты человек.\n\n"
        "<i>Это разовая проверка — больше не потребуется.</i>",
        reply_markup=kb,
    )
    await cb.answer()


@dp.callback_query(F.data == "verify:done")
async def cb_verify_done(cb: CallbackQuery):
    uid      = cb.from_user.id
    raw_name = cb.from_user.first_name or "друг"
    name     = html.escape(raw_name)
    _verified_users.add(uid)
    save_data()
    await _edit_custom(
        cb.message, "verify_done",
        f"✅ <b>Верификация пройдена!</b>\n\n"
        f"Добро пожаловать, {name}! Все функции Лумены теперь доступны.",
        name=raw_name,
    )
    await _answer_custom(
        cb.message, "start_text",
        _START_TEXT.format(name=name),
        name=raw_name,
        reply_markup=build_main_kb(),
    )
    await cb.answer()


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
    """Извлекает ID Premium/custom emoji из сообщения — только для фаундера."""
    if not is_owner(msg):
        return
    if _ank.is_on_media_step(msg.from_user.id):
        return  # не перехватываем медиа-шаг анкеты
    entities = msg.entities or []
    found = [(msg.text[e.offset: e.offset + e.length], e.custom_emoji_id)
             for e in entities if e.type == "custom_emoji" and e.custom_emoji_id]
    if not found:
        return
    lines = ["🔍 <b>Найдены Custom Emoji ID:</b>\n"]
    for i, (char, eid) in enumerate(found):
        lines += [
            f"[{i}] <tg-emoji emoji-id=\"{eid}\">{html.escape(char)}</tg-emoji>",
            f"ID: <code>{eid}</code>",
            "",
        ]
    await msg.reply("\n".join(lines), parse_mode="HTML")


@dp.message(F.chat.type == "private",
            F.func(lambda m: m.from_user is not None
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

    brand.set_custom_text(key, raw_text, ents_data)
    brand.save_custom_texts()
    asyncio.create_task(brand.push_custom_texts_to_github())

    label = brand.TEXT_LABELS.get(key, key)
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛠 Открыть редактор", callback_data="editor:menu")]
    ])
    await msg.reply(
        f"✅ <b>{html.escape(label)}</b> — сохранён!\n\n"
        "Бот будет использовать твой текст с Premium emoji.\n\n"
        f"<code>/resettext {key}</code> — сбросить к дефолту.",
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

    preview = html.escape(cur_text[:300]) if cur_text else ""
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отмена", callback_data="reply_edit_cancel"),
    ]])
    await cb.message.answer(
        f"✏️ <b>{html.escape(label)}</b>\n\n"
        f"{status_line}\n"
        + (f"<blockquote>{preview}</blockquote>\n\n" if preview else "\n")
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
    brand.save_custom_texts()
    asyncio.create_task(brand.push_custom_texts_to_github())
    await msg.reply(
        f"🔄 <b>{html.escape(brand.TEXT_LABELS[key])}</b> — сброшен к дефолту.",
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
                              "casino_win", "casino_jackpot", "casino_lose",
                              "rob_success", "rob_fail", "rob_cooldown",
                              "coin_rain", "coin_rain_collected"]),
    ("💍 Брак",              ["marry_proposal", "marry_accept", "marry_reject",
                              "marry_self", "marry_already", "marry_already_other",
                              "marry_no_reply", "divorce", "divorce_not_married"]),
    ("🔥 Стрики & Аура",    ["checkin", "checkin_already", "upvote", "downvote",
                              "rep", "aura_show"]),
    ("🎮 Игры",              ["rps_win", "rps_lose", "rps_tie",
                              "roulette_join", "roulette_winner", "coin",
                              "hangman_start", "hangman_win", "hangman_lose"]),
    ("🤗 Социальные",        ["hug", "kiss", "gift", "slap", "pat",
                              "dance", "bite", "poke", "wave", "highfive",
                              "facepalm", "serenade"]),
    ("🛡 Модерация чата",   ["mute_done", "ban_done", "unban_done", "unmute_done",
                              "kick_done", "warn_done", "warn_ban", "unwarn_done",
                              "admin_only", "reply_needed", "owner_only"]),
    ("🔮 Предсказания",     ["fortune_result", "horoscope_result", "tarot_result"]),
    ("👤 Профиль",          ["profile_no_bio", "profile_no_partner", "info_founder_badge"]),
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


# /edit — латиница. is_owner вынесен В ФИЛЬТР: если не совпало — сообщение идёт дальше
@dp.message(Command("edit", "настройки", "settings"),
            F.chat.type == "private",
            F.func(lambda m: is_owner(m)))
async def cmd_editor_latin(msg: Message):
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
    brand.save_custom_buttons()
    df = brand.BUTTON_DEFS[key]
    await cb.answer(f"🔄 «{df['desc']}» сброшена к дефолту", show_alert=True)
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
    brand.save_custom_style()
    asyncio.create_task(brand.push_custom_style_to_github())
    df = brand.STYLE_DEFS[key]
    await cb.answer(f"🔄 «{df['desc']}» сброшено к дефолту", show_alert=False)
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
    brand.save_custom_style()
    asyncio.create_task(brand.push_custom_style_to_github())
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 К оформлению", callback_data="editor:style")],
        [InlineKeyboardButton(text="🛠 Главное меню", callback_data="editor:menu")],
    ])
    await msg.reply(
        f"✅ <b>{html.escape(df['desc'])}</b> обновлено!\n\n"
        f"Новое значение: <code>{html.escape(text)}</code>\n\n"
        f"Заголовок теперь: {brand.hdr()}\n"
        f"Разделитель: {brand.div()}",
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

    brand.save_custom_buttons()

    what = "Ссылка" if step == "url" else "Название"
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔘 К кнопкам", callback_data="editor:btns")],
        [InlineKeyboardButton(text="🛠 Главное меню", callback_data="editor:menu")],
    ])
    await msg.reply(
        f"✅ {what} кнопки <b>{html.escape(df.get('desc', key))}</b> обновлено!\n\n"
        f"Новое значение: <code>{html.escape(text)}</code>",
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
_ADMIN_TARGETS = {
    "админ","адмнн","адмнны","модер","модеры","модератор","владелец",
    "владелка","гидра","hydra","hydræ","создатель","руководство",
    "верхушка","команда","хдр","hdr","hdrttt","начальник","начальники",
    "боты","бот","lumena","лумена","лумена",
}

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
    # Мут на 10 минут
    from datetime import datetime
    until = int(datetime.now(tz=KYIV_TZ).timestamp()) + 600
    try:
        await bot.restrict_chat_member(
            msg.chat.id, uid,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until,
        )
        name_u = msg.from_user.full_name
        # Штраф ауры за агрессию
        add_aura(uid, -1.0)
        await msg.reply(
            f"🔇 <b>{name_u}</b> — мут на 10 минут за оскорбление администрации.\n"
            f"🌑 Аура: <b>-1%</b>",
            parse_mode="HTML",
        )
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

    # 3. Имя бота в начале сообщения
    if not is_addressed:
        for trigger in ("лумена", "лумка", "лум,"):
            if tl.startswith(trigger):
                is_addressed = True
                break

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
    if await _check_admin_insult(msg):
        return

    uid  = msg.from_user.id
    text = msg.text.strip()

    # ── Поддержка: пользователь отправляет обращение администрации
    if msg.chat.type == "private" and uid in support_sessions and not text.startswith("/"):
        del support_sessions[uid]
        mod_chat = _ank.get_mod_chat()
        if mod_chat:
            user = msg.from_user
            tag = f"@{user.username}" if user.username else user.full_name
            try:
                await bot.send_message(
                    mod_chat,
                    f"📩 *Обращение от участника*\n\n"
                    f"👤 {tag} (ID: `{user.id}`)\n"
                    f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
                    f"{text}",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            await _answer_custom(
                msg, "support_sent",
                "✅ <b>Обращение отправлено!</b>\n\n"
                "Администрация рассмотрит его в ближайшее время 🙏",
            )
        else:
            await msg.reply("⚠️ Чат администрации не настроен. Попробуй позже.")
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

        # Конвертируем русские временные суффиксы
        args_converted = args_str.replace("м","m").replace("ч","h").replace("д","d")

        class FakeCmd:
            args = args_converted

        fake_cmd = FakeCmd()

        # Бан и мут — только через !
        BAN_MUTE = {
            "мут": cmd_mute, "бан": cmd_ban,
            "форсбан": cmd_forceban, "форсмут": cmd_forcemute,
            "mute": cmd_mute, "ban": cmd_ban,
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

            # Конвертируем временные суффиксы
            args_converted = args_str.replace("м","m").replace("ч","h").replace("д","d")

            class FakeCmd2:
                args = args_converted or None

            try: await handler(msg, FakeCmd2())
            except TypeError: await handler(msg)
            return

        # ── Лумена ИИ: личка — всегда, группа — при обращении
        if msg.chat.type == "private":
            await _lumena_ai_private(msg)
        else:
            await _lumena_ai_group(msg)

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

        # ── Текст кнопки (кастомный или дефолтный) ───────
        btn_ct   = brand.get_custom_text("welcome_btn")
        btn_text = btn_ct[0].strip() if btn_ct else "📝 Создать анкету"
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=btn_text,
                url="https://t.me/LumenarAi_Bot?start=anketa",
            ),
        ]])

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
    load_data()
    _ank.load_anketa_settings()
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

    # Цикл перезапуска polling — при любом сбое сети/API бот сам восстанавливается
    retry_delay = 5
    while True:
        try:
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                polling_timeout=30,
            )
        except asyncio.CancelledError:
            print("🛑 Бот остановлен вручную")
            save_data()
            break
        except Exception as e:
            logging.error(f"💥 Polling упал: {e}. Перезапуск через {retry_delay}с...")
            save_data()
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)  # экспоненциальный backoff до 60с
        else:
            retry_delay = 5  # сбрасываем задержку при успешном завершении


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Остановлено")
        save_data()
