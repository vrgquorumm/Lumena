"""
Система анкет знайомств Lumena.

Новые анкеты после заполнения публикуются в основном чате, а просмотр,
реакции и жалобы доступны карточками прямо в личке бота.
"""

import json
import os
import re as _re
from html import escape as _h

import brand
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    InputMediaPhoto, InputMediaVideo,
    MessageEntity as _ME,
)

ANKETA_USERS_FILE = "data/anketa_users.json"
ANKETA_DATA_FILE  = "data/anketa_settings.json"

# ── In-memory стан ──────────────────────────────────────────
_mod_chat_id:   list        = [None]   # [0] — id чату модерації
_pub_chat_id:   list        = [None]   # [0] — id чату публікацій
_observer_chat_id: list     = [None]   # [0] — founder-наблюдательный чат
_anketa_counter:list        = [0]      # [0] — наступний номер анкети
_chat_link:     list        = [None]   # [0] — посилання на чат публікацій
_observer_chat_link: list   = [None]   # [0] — ссылка founder-наблюдательного чата
_user_status:   dict        = {}       # uid → "pending"|"approved"|"rejected"
_approved_data: dict        = {}       # uid → dict з даними анкети
_sessions:      dict        = {}       # uid → незавершена анкета в поточному діалозі
_pending:       dict[str, dict] = {}    # app_id → заявка, що очікує модерації
_reactions:     dict[int, dict] = {}    # uid → реакції під опублікованою анкетою
_mod_commenting: dict[int, str] = {}    # mod_uid → app_id (чекає коментар-правку)
_feed_cursors:  dict[int, int] = {}    # viewer uid → index in the private feed
_feed_seen:     dict[int, set[int]] = {}  # viewer uid → уже обработанные анкеты
DEFAULT_PUBLIC_CHAT_ID = -1004401287309


def _md_to_html(s: str) -> str:
    """Конвертирует базовый Markdown (*bold*, _italic_) в HTML."""
    s = _re.sub(r'\*(.+?)\*', r'<b>\1</b>', s)
    s = _re.sub(r'_(.+?)_',   r'<i>\1</i>', s)
    return s


def _build_ents(ents_data: list[dict]) -> list[_ME]:
    """Восстанавливает MessageEntity из сохранённого JSON."""
    result = []
    for e in (ents_data or []):
        try:
            clean = {k: v for k, v in e.items() if v is not None and k != "user"}
            result.append(_ME(**clean))
        except Exception:
            pass
    return result


async def _send_custom(bot_obj, chat_id: int, key: str, fallback: str,
                       parse_mode: str = "HTML", **kwargs) -> None:
    """Отправляет кастомный текст фаундера (с Premium emoji) или HTML fallback."""
    ct = brand.get_custom_text(key)
    if ct:
        text, ents_data = ct
        ents = _build_ents(ents_data)
        await bot_obj.send_message(chat_id, text, entities=ents or None, **kwargs)
    else:
        await bot_obj.send_message(chat_id, fallback, parse_mode=parse_mode, **kwargs)


async def _answer_custom(msg_obj, key: str, fallback: str,
                         parse_mode: str = "HTML", **kwargs) -> None:
    """Отправляет кастомный текст через msg.answer() или HTML fallback."""
    ct = brand.get_custom_text(key)
    if ct:
        text, ents_data = ct
        ents = _build_ents(ents_data)
        await msg_obj.answer(text, entities=ents or None, **kwargs)
    else:
        await msg_obj.answer(fallback, parse_mode=parse_mode, **kwargs)

# ──────────────────────────────────────────
# ПИТАННЯ АНКЕТИ (знайомства)
# ──────────────────────────────────────────
QUESTIONS: list[tuple[str, str]] = [
    ("name",
     "👤 *Как тебя зовут?*\n_(имя или никнейм)_"),
    ("age",
     "🎂 *Сколько тебе лет?*"),
    ("district",
     "🏙 *Твой район?*\n_(район или микрорайон города)_"),
    ("goal",
     "🎯 *Цель знакомства*\n_(общение, дружба, отношения, не важно)_"),
    ("looking_for",
     "💖 *Кого ищешь?*\n_(девушку, парня, не важно)_"),
    ("smoking",
     "🚬 *Курение*\n_(Курю / Не курю / Иногда)_"),
    ("kids",
     "👶 *Дети*\n_(Есть / Нет / Хочу в будущем)_"),
    ("about",
     "📝 *О себе*\n_(пару предложений: характер, интересы, кто ты)_"),
]
QUESTION_KEYS = [k for k, _ in QUESTIONS]

# Фото-крок іде ПІСЛЯ всіх текстових питань
PHOTO_STEP_IDX = len(QUESTIONS)
PHOTO_STEP_TEXT = (
    "📸 *Фото и видео*\n\n"
    "Отправь от *1 до 10* фото или видео любой длины.\n"
    "Когда закончишь — нажми *«✅ Готово»*.\n\n"
    "Или напиши *«без фото»*, чтобы пропустить этот шаг."
)
_SKIP_MEDIA = {
    "без фото", "без видео", "без медиа", "без", "skip",
    "пропустити", "пропуск", "нет", "no", "-",
}
_SKIP_PHOTO = _SKIP_MEDIA  # обратная совместимость
_DONE_WORDS = {
    "готово", "готов", "всё", "все", "finish", "done",
    "ок", "ok", "всьо", "стоп", "stop",
}

# ──────────────────────────────────────────
# ПИТАННЯ ДВОМА МОВАМИ
# ──────────────────────────────────────────
QUESTIONS_UK = QUESTIONS  # обратная совместимость для старых сессий

QUESTIONS_RU: list[tuple[str, str]] = [
    ("name",
     "👤 *Как тебя зовут?*\n_(имя или никнейм)_"),
    ("age",
     "🎂 *Сколько тебе лет?*"),
    ("district",
     "🏙 *Твой район?*\n_(район или микрорайон города)_"),
    ("goal",
     "🎯 *Цель знакомства*\n_(общение, дружба, отношения, не важно)_"),
    ("looking_for",
     "💖 *Кого ищешь?*\n_(девушку, парня, не важно)_"),
    ("smoking",
     "🚬 *Курение*\n_(Курю / Не курю / Иногда)_"),
    ("kids",
     "👶 *Дети*\n_(Есть / Нет / Хочу в будущем)_"),
    ("about",
     "📝 *О себе*\n_(пару предложений: характер, интересы, кто ты)_"),
]

QUESTION_OPTIONS: dict[str, list[tuple[str, str]]] = {
    "goal": [
        ("💬 Общение", "Общение"),
        ("🤝 Дружба", "Дружба"),
        ("❤️ Отношения", "Отношения"),
        ("✨ Не важно", "Не важно"),
    ],
    "looking_for": [
        ("👩 Девушку", "Девушку"),
        ("👨 Парня", "Парня"),
        ("💞 Не важно", "Не важно"),
    ],
    "smoking": [
        ("🚭 Не курю", "Не курю"),
        ("🚬 Курю", "Курю"),
        ("🌫 Иногда", "Иногда"),
    ],
    "kids": [
        ("👶 Есть", "Есть"),
        ("🌱 Нет", "Нет"),
        ("🔮 Хочу в будущем", "Хочу в будущем"),
    ],
}

PHOTO_STEP_TEXT_RU = (
    "📸 *Фото и видео*\n\n"
    "Отправь от *1 до 10* фото или видео любой длины.\n"
    "Когда закончишь — нажми *«✅ Готово»*.\n\n"
    "Или напиши *«без фото»* чтобы пропустить этот шаг."
)


def _lang_questions(lang: str) -> list[tuple[str, str]]:
    return QUESTIONS_RU


def _lang_photo_text(lang: str) -> str:
    return PHOTO_STEP_TEXT_RU


def question_kb(uid: int, key: str) -> InlineKeyboardMarkup | None:
    """Кнопки для вопросов с ограниченным набором вариантов."""
    options = QUESTION_OPTIONS.get(key)
    if not options:
        return None
    rows = []
    row = []
    for index, (label, _value) in enumerate(options):
        row.append(
            InlineKeyboardButton(
                text=label,
                callback_data=f"ank_q:{uid}:{key}:{index}",
            )
        )
        if len(row) == 2 or index == len(options) - 1:
            rows.append(row)
            row = []
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _media_done_kb(uid: int) -> InlineKeyboardMarkup:
    """Кнопки під підтвердженням кожного медіа-файлу."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Готово",       callback_data=f"ank_media_done:{uid}"),
        InlineKeyboardButton(text="⏭ Без медиа",   callback_data=f"ank_media_skip:{uid}"),
    ]])


def _lang_kb() -> InlineKeyboardMarkup:
    """Клавиатура выбора языка анкеты."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="ank_lang:ru"),
    ]])

async def load_anketa_from_db() -> None:
    """При старті завантажує дані анкет з PostgreSQL."""
    import db as _db
    # Завантажуємо налаштування анкет
    settings = await _db.load_kv("anketa_settings")
    if settings:
        _mod_chat_id[0]    = settings.get("mod_chat_id")
        _pub_chat_id[0]    = settings.get("pub_chat_id")
        _observer_chat_id[0] = settings.get("observer_chat_id")
        _anketa_counter[0] = settings.get("anketa_counter", 0)
        _chat_link[0]      = settings.get("chat_link")
        _observer_chat_link[0] = settings.get("observer_chat_link")
        print("✅ anketa_settings завантажено з PostgreSQL")
    else:
        # Fallback: локальний файл
        load_anketa_settings()
        return

    # Завантажуємо дані користувачів анкет
    users = await _db.load_kv("anketa_users")
    if users:
        for k, v in users.get("status", {}).items():
            _user_status[int(k)] = v
        for k, v in users.get("approved", {}).items():
            _approved_data[int(k)] = v
        for k, v in users.get("pending", {}).items():
            _pending[str(k)] = v
        for owner_key, reaction_data in users.get("reactions", {}).items():
            try:
                owner_uid = int(owner_key)
            except (TypeError, ValueError):
                continue
            reaction_data = reaction_data or {}
            _reactions[owner_uid] = {
                "hearts": {
                    int(reactor_uid): dict(info or {})
                    for reactor_uid, info in reaction_data.get("hearts", {}).items()
                },
                "dislikes": {
                    int(reactor_uid): dict(info or {})
                    for reactor_uid, info in reaction_data.get("dislikes", {}).items()
                },
            }
        for viewer_key, seen_uids in users.get("feed_seen", {}).items():
            try:
                _feed_seen[int(viewer_key)] = {
                    int(seen_uid) for seen_uid in (seen_uids or [])
                }
            except (TypeError, ValueError):
                continue
        print("✅ anketa_users завантажено з PostgreSQL")
async def restore_anketa() -> None:
    """При старті відновлює anketa_users і anketa_settings: PostgreSQL → GitHub → локальний файл."""
    import db as _db
    os.makedirs("data", exist_ok=True)

    _targets = [
        (ANKETA_USERS_FILE,  "anketa_users",    "data/anketa_users.json"),
        (ANKETA_DATA_FILE,   "anketa_settings", "data/anketa_settings.json"),
    ]

    for local, pg_key, gh_path in _targets:
        # 1. PostgreSQL
        if _db.has_pg():
            data = await _db.db_get(pg_key)
            if data is not None:  # {} — валідний (очищений стан)
                with open(local, "w", encoding="utf-8") as f:
                    import json as _j
                    _j.dump(data, f, ensure_ascii=False)
                print(f"✅ {pg_key} відновлено з PostgreSQL")
                continue
            print(f"⚠️ PostgreSQL: {pg_key} ще не записано")

        # 2. GitHub fallback
        if os.path.exists(local) and os.path.getsize(local) > 5:
            continue  # локальний файл є
        print(f"📥 {pg_key} не знайдено — спроба відновити з GitHub...")
        raw = await brand.fetch_bot_data_from_github(gh_path)
        if raw:
            with open(local, "wb") as f:
                f.write(raw)
            print(f"✅ {pg_key} відновлено з GitHub")
        else:
            print(f"⚠️ GitHub не повернув {pg_key}")


# Аліас для зворотної сумісності
restore_anketa_from_github = restore_anketa


def load_anketa_settings():
    if os.path.exists(ANKETA_DATA_FILE):
        try:
            with open(ANKETA_DATA_FILE, encoding="utf-8") as f:
                d = json.load(f)
            _mod_chat_id[0]     = d.get("mod_chat_id")
            _pub_chat_id[0]     = d.get("pub_chat_id")
            _observer_chat_id[0] = d.get("observer_chat_id")
            _anketa_counter[0]  = d.get("anketa_counter", 0)
            _chat_link[0]       = d.get("chat_link")
            _observer_chat_link[0] = d.get("observer_chat_link")
        except Exception:
            pass
    if os.path.exists(ANKETA_USERS_FILE):
        try:
            with open(ANKETA_USERS_FILE, encoding="utf-8") as f:
                d = json.load(f)
            for k, v in d.get("status", {}).items():
                _user_status[int(k)] = v
            for k, v in d.get("approved", {}).items():
                _approved_data[int(k)] = v
            for k, v in d.get("pending", {}).items():
                _pending[str(k)] = v
            for owner_key, reaction_data in d.get("reactions", {}).items():
                try:
                    owner_uid = int(owner_key)
                except (TypeError, ValueError):
                    continue
                reaction_data = reaction_data or {}
                _reactions[owner_uid] = {
                    "hearts": {
                        int(reactor_uid): dict(info or {})
                        for reactor_uid, info in reaction_data.get("hearts", {}).items()
                    },
                    "dislikes": {
                        int(reactor_uid): dict(info or {})
                        for reactor_uid, info in reaction_data.get("dislikes", {}).items()
                    },
                }
            for viewer_key, seen_uids in d.get("feed_seen", {}).items():
                try:
                    _feed_seen[int(viewer_key)] = {
                        int(seen_uid) for seen_uid in (seen_uids or [])
                    }
                except (TypeError, ValueError):
                    continue
        except Exception:
            pass

def _build_anketa_payloads() -> tuple[dict, dict]:
    """Будує словники для збереження налаштувань і користувачів анкет."""
    settings_payload = {
        "mod_chat_id":    _mod_chat_id[0],
        "pub_chat_id":    _pub_chat_id[0],
        "observer_chat_id": _observer_chat_id[0],
        "anketa_counter": _anketa_counter[0],
        "chat_link":      _chat_link[0],
        "observer_chat_link": _observer_chat_link[0],
    }
    users_payload = {
        "status":   {str(k): v for k, v in _user_status.items()},
        "approved": {str(k): v for k, v in _approved_data.items()},
        "reactions": {
            str(owner_uid): {
                "hearts": {
                    str(reactor_uid): dict(info or {})
                    for reactor_uid, info in reaction_data.get("hearts", {}).items()
                },
                "dislikes": {
                    str(reactor_uid): dict(info or {})
                    for reactor_uid, info in reaction_data.get("dislikes", {}).items()
                },
            }
            for owner_uid, reaction_data in _reactions.items()
        },
        "feed_seen": {
            str(viewer_uid): sorted(seen_uids)
            for viewer_uid, seen_uids in _feed_seen.items()
            if seen_uids
        },
        # Заявки зберігаємо також: після перезапуску користувач повинен
        # мати змогу скасувати pending-анкету, а не отримувати "вічне" очікування.
        "pending":  dict(_pending),
    }
    return settings_payload, users_payload


def build_settings_payload() -> dict:
    """Поточні налаштування анкет у форматі для PostgreSQL."""
    return _build_anketa_payloads()[0]


def build_users_payload() -> dict:
    """Поточні статуси й анкети користувачів у форматі для PostgreSQL."""
    return _build_anketa_payloads()[1]


def save_anketa_settings():
    """Зберігає anketa дані на диск.
    PostgreSQL sync виконується тільки через _save_all_to_db() в bot.py
    (auto_save_loop + shutdown handler) — без race conditions.
    """
    os.makedirs("data", exist_ok=True)
    settings_payload, users_payload = _build_anketa_payloads()
    with open(ANKETA_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(settings_payload, f, ensure_ascii=False)
    with open(ANKETA_USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users_payload, f, ensure_ascii=False)


def _schedule_anketa_save() -> None:
    """Запускає асинхронне збереження, не затримуючи Telegram-відповідь."""
    try:
        import asyncio
        asyncio.get_running_loop().create_task(async_save_anketa_to_db())
    except RuntimeError:
        pass


async def async_save_anketa_to_db() -> None:
    """Зберігає дані анкет у PostgreSQL одним атомарним записом."""
    import db as _db
    settings_payload, users_payload = _build_anketa_payloads()
    if _db.has_pg():
        await _db.db_set_many([
            ("anketa_settings", settings_payload),
            ("anketa_users", users_payload),
        ])


def next_anketa_number() -> int:
    """Повертає наступний номер анкети і зберігає лічильник."""
    _anketa_counter[0] += 1
    save_anketa_settings()
    _schedule_anketa_save()
    return _anketa_counter[0]


# ──────────────────────────────────────────
# ПУБЛІЧНІ ФУНКЦІЇ СТАТУСІВ
# ──────────────────────────────────────────
def get_mod_chat() -> int | None:
    return _mod_chat_id[0]

def set_mod_chat(chat_id: int):
    _mod_chat_id[0] = chat_id
    save_anketa_settings()
    _schedule_anketa_save()

def get_pub_chat() -> int | None:
    return _pub_chat_id[0]

def set_pub_chat(chat_id: int | None):
    _pub_chat_id[0] = chat_id
    save_anketa_settings()

def get_observer_chat() -> int | None:
    return _observer_chat_id[0]

def set_observer_chat(chat_id: int | None):
    _observer_chat_id[0] = chat_id
    save_anketa_settings()
    _schedule_anketa_save()

def get_chat_link() -> str | None:
    return _chat_link[0]

def set_chat_link(link: str):
    _chat_link[0] = link
    save_anketa_settings()

def get_observer_chat_link() -> str | None:
    return _observer_chat_link[0]

def set_observer_chat_link(link: str):
    _observer_chat_link[0] = link
    save_anketa_settings()
    _schedule_anketa_save()

def get_user_status(uid: int) -> str | None:
    """none / pending / approved / rejected"""
    return _user_status.get(uid)

def set_pending(uid: int):
    _user_status[uid] = "pending"
    save_anketa_settings()
    _schedule_anketa_save()


def save_pending_application(application: dict) -> str:
    """Сохраняет заявку и переводит владельца в статус pending."""
    uid = int(application["user_id"])
    app_id = _app_id(uid)
    _pending[app_id] = application
    _user_status[uid] = "pending"
    save_anketa_settings()
    _schedule_anketa_save()
    return app_id


def set_approved(uid: int, answers: dict, username: str, full_name: str,
                 pub_msg_id: int | None = None, pub_chat_id: int | None = None,
                 anketa_num: int | None = None,
                 media_msg_ids: list[int] | None = None,
                 pub_control_msg_id: int | None = None):
    _user_status[uid] = "approved"
    _approved_data[uid] = {
        "answers":       answers,
        "username":      username,
        "full_name":     full_name,
        "pub_msg_id":    pub_msg_id,
        "pub_chat_id":   pub_chat_id,
        "anketa_num":    anketa_num,
        "media_msg_ids": media_msg_ids or [],  # IDs медіа-повідомлень альбому
        "pub_control_msg_id": pub_control_msg_id,
    }
    save_anketa_settings()
    _schedule_anketa_save()

def set_rejected(uid: int):
    _user_status[uid] = "rejected"
    _approved_data.pop(uid, None)
    save_anketa_settings()
    _schedule_anketa_save()

def revoke_anketa(uid: int) -> dict | None:
    """Розжаловує схвалену анкету. Повертає збережені дані для видалення поста."""
    if _user_status.get(uid) not in ("approved", "pending"):
        return None
    data = _approved_data.pop(uid, None)
    _user_status.pop(uid, None)
    _reactions.pop(uid, None)
    for seen_uids in _feed_seen.values():
        seen_uids.discard(uid)
    save_anketa_settings()
    _schedule_anketa_save()
    return data

def get_uid_by_pub_msg(msg_id: int, chat_id: int | None = None) -> int | None:
    """Знаходить uid власника анкети за msg_id публічного поста."""
    for uid, d in _approved_data.items():
        if (
            d.get("pub_msg_id") == msg_id
            or d.get("pub_control_msg_id") == msg_id
            or msg_id in (d.get("media_msg_ids") or [])
        ):
            if chat_id is None or d.get("pub_chat_id") == chat_id:
                return uid
    return None


def delete_user_anketa(uid: int) -> dict | None:
    """Видаляє анкету або заявку, повертає дані для очищення повідомлень."""
    pending = _pending.pop(_app_id(uid), None)
    old_status = _user_status.pop(uid, None)
    approved = _approved_data.pop(uid, None)
    # Якщо бот був перезапущений до відновлення старого pending-повідомлення,
    # статус усе одно треба видалити. Порожній словник дає виклику змогу
    # коректно завершити видалення без падіння.
    data = approved or pending or ({"user_id": uid} if old_status == "pending" else None)
    _sessions.pop(uid, None)
    _reactions.pop(uid, None)
    for seen_uids in _feed_seen.values():
        seen_uids.discard(uid)
    save_anketa_settings()
    _schedule_anketa_save()
    return data

def get_approved_data(uid: int) -> dict | None:
    return _approved_data.get(uid)


def feed_uids(viewer_uid: int) -> list[int]:
    """Возвращает опубликованные анкеты для личной ленты без своей анкеты."""
    seen = _feed_seen.get(viewer_uid, set())
    candidates = [
        (uid, data)
        for uid, data in _approved_data.items()
        if uid != viewer_uid
        and uid not in seen
        and _user_status.get(uid) == "approved"
    ]
    candidates.sort(
        key=lambda item: (
            int(item[1].get("anketa_num") or 0),
            int(item[0]),
        )
    )
    return [uid for uid, _ in candidates]


def feed_position(viewer_uid: int, owner_uid: int | None = None) -> tuple[int, int] | None:
    """Возвращает (индекс, размер) для карточки в ленте."""
    uids = feed_uids(viewer_uid)
    if not uids:
        return None
    if owner_uid in uids:
        index = uids.index(owner_uid)
    else:
        index = _feed_cursors.get(viewer_uid, 0) % len(uids)
    _feed_cursors[viewer_uid] = index
    return index, len(uids)


def set_feed_cursor(viewer_uid: int, index: int) -> None:
    uids = feed_uids(viewer_uid)
    if uids:
        _feed_cursors[viewer_uid] = index % len(uids)


def mark_feed_seen(viewer_uid: int, owner_uid: int) -> None:
    """Помечает профиль обработанным, чтобы он не повторялся в ленте."""
    if viewer_uid == owner_uid:
        return
    _feed_seen.setdefault(viewer_uid, set()).add(owner_uid)
    _feed_cursors.pop(viewer_uid, None)
    save_anketa_settings()
    _schedule_anketa_save()


def reset_feed_seen(viewer_uid: int) -> None:
    """Начинает ленту заново после просмотра всех доступных анкет."""
    _feed_seen.pop(viewer_uid, None)
    _feed_cursors.pop(viewer_uid, None)
    save_anketa_settings()
    _schedule_anketa_save()


def feed_owner(viewer_uid: int, index: int | None = None) -> int | None:
    """Возвращает владельца карточки по позиции ленты."""
    uids = feed_uids(viewer_uid)
    if not uids:
        return None
    if index is None:
        index = _feed_cursors.get(viewer_uid, 0)
    index %= len(uids)
    _feed_cursors[viewer_uid] = index
    return uids[index]


def feed_kb(owner_uid: int, index: int, total: int) -> InlineKeyboardMarkup:
    """Кнопки интерактивной карточки в личной ленте."""
    reaction_data = _reactions.get(owner_uid, {})
    likes = len(reaction_data.get("hearts", {}))
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"❤️ Лайк{f' · {likes}' if likes else ''}",
                callback_data=f"ank_feed:like:{owner_uid}:{index}",
            ),
            InlineKeyboardButton(
                text="👎 Пропустить",
                callback_data=f"ank_feed:pass:{owner_uid}:{index}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="👤 Подробнее",
                callback_data=f"ank_feed:detail:{owner_uid}:{index}",
            ),
            InlineKeyboardButton(
                text="🚩 Жалоба",
                callback_data=f"ank_feed:report:{owner_uid}:{index}",
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"📋 {index + 1}/{total}",
                callback_data=f"ank_feed:position:{owner_uid}:{index}",
            ),
        ],
    ])


def feed_empty_kb() -> InlineKeyboardMarkup:
    """Кнопки пустой ленты: начать просмотр заново или создать анкету."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔄 Смотреть сначала",
                callback_data="ank_feed:reset",
            ),
        ],
        [
            InlineKeyboardButton(
                text="📝 Создать анкету",
                callback_data="ank_feed:create",
            ),
        ],
    ])


def feed_empty_text() -> str:
    return (
        f"{brand.hdr()}\n\n"
        "💌 <b>Анкеты пока закончились</b>\n\n"
        "Ты уже просмотрел(а) все доступные анкеты. "
        "Можно начать сначала или создать свою."
    )


# ──────────────────────────────────────────
# ФОРМАТУВАННЯ КАРТОК
# ──────────────────────────────────────────
def _clean_social(val: str) -> str:
    if val.lower().strip() in ("ні", "нет", "no", "н", "-", "немає", "нема", "не хочу"):
        return "не вказано"
    return val


def fmt_mod_card(answers: dict, user_id: int, username: str, full_name: str,
                 anketa_num: int = 0, is_premium: bool = False) -> str:
    """Картка для чату модерації."""
    tag = f"@{username}" if username else full_name
    media_list = answers.get("media", [])
    if not media_list:
        if answers.get("video_id"):
            media_list = [{"type": "video", "file_id": answers["video_id"]}]
        elif answers.get("photo_id"):
            media_list = [{"type": "photo", "file_id": answers["photo_id"]}]
    if media_list:
        n_photo = sum(1 for m in media_list if m["type"] == "photo")
        n_video = sum(1 for m in media_list if m["type"] == "video")
        parts = []
        if n_photo: parts.append(f"📷 {n_photo}")
        if n_video: parts.append(f"🎬 {n_video}")
        media_icon = " + ".join(parts) + f" ✅ ({len(media_list)} файлов)"
    else:
        media_icon = "❌ нет"
    vip_label = " 👑 VIP" if is_premium else ""
    num = anketa_num if anketa_num else "?"
    bul = brand.bul()
    return (
        f"{brand.hdr()}\n\n"
        f"{brand.acc()} <b>Новая анкета #{num}</b>{vip_label} — на модерацию\n\n"
        f"{brand.div()}\n"
        f"👤 <b>Имя:</b> {_h(answers.get('name', '—'))}\n"
        f"🎂 <b>Возраст:</b> {_h(answers.get('age', '—'))}\n"
        f"🏙 <b>Район:</b> {_h(answers.get('district', '—'))}\n\n"
        f"🎯 <b>Цель:</b> {_h(answers.get('goal', '—'))}\n"
        f"💖 <b>Ищу:</b> {_h(answers.get('looking_for', '—'))}\n"
        f"🚬 <b>Курение:</b> {_h(answers.get('smoking', '—'))}\n"
        f"👶 <b>Дети:</b> {_h(answers.get('kids', '—'))}\n\n"
        f"📝 <b>Про себе:</b>\n{_h(answers.get('about', '—'))}\n\n"
        f"{brand.div()}\n"
        f"🔗 {_h(tag)}  ·  🆔 <code>{user_id}</code>\n"
        f"{bul} Медиа: {_h(media_icon)}"
    )


def fmt_pub_card(answers: dict, username: str = "", full_name: str = "",
                 is_premium: bool = False) -> str:
    """Публічна картка — V6 стиль."""
    vip_badge = "⭐ VIP\n\n" if is_premium else "⭐ New\n\n"
    tags      = "#анкетазнакомства #VIP" if is_premium else "#анкетазнакомства"
    return (
        f"{vip_badge}"
        f"👤 Имя: {_h(answers.get('name', '—'))}\n"
        f"🎂 Возраст: {_h(answers.get('age', '—'))}\n"
        f"📍 Район: {_h(answers.get('district', '—'))}\n\n"
        f"🎯 Цель: {_h(answers.get('goal', '—'))}\n"
        f"💘 Ищу: {_h(answers.get('looking_for', '—'))}\n\n"
        f"🚬 Курение: {_h(answers.get('smoking', '—'))}\n"
        f"👶 Дети: {_h(answers.get('kids', '—'))}\n\n"
        f"📝 О себе:\n{_h(answers.get('about', '—'))}\n\n"
        f"{tags}"
    )


def fmt_my_card(answers: dict, username: str, full_name: str,
                is_premium: bool = False) -> str:
    """Текст картки для перегляду юзером — V6 стиль."""
    tag       = f"@{_h(username)}" if username else _h(full_name)
    vip_badge = "⭐ VIP\n\n" if is_premium else "⭐ New\n\n"
    return (
        f"{brand.hdr()}\n\n"
        f"{brand.div()}\n"
        f"{vip_badge}"
        f"👤 Имя: {_h(answers.get('name', '—'))}\n"
        f"🎂 Возраст: {_h(answers.get('age', '—'))}\n"
        f"📍 Район: {_h(answers.get('district', '—'))}\n\n"
        f"🎯 Цель: {_h(answers.get('goal', '—'))}\n"
        f"💘 Ищу: {_h(answers.get('looking_for', '—'))}\n\n"
        f"🚬 Курение: {_h(answers.get('smoking', '—'))}\n"
        f"👶 Дети: {_h(answers.get('kids', '—'))}\n\n"
        f"📝 О себе:\n{_h(answers.get('about', '—'))}\n\n"
        f"{brand.div()}\n"
        f"🔗 {tag}"
    )


# ──────────────────────────────────────────
# РЕАКЦІЇ (❤️ / 👎) НА ПУБЛІЧНИХ АНКЕТАХ
# ──────────────────────────────────────────
def reaction_kb(owner_uid: int) -> InlineKeyboardMarkup:
    """Клавіатура реакцій + посилання НАШ ЧАТ / СТВОРИТИ АНКЕТУ."""
    r = _reactions.get(owner_uid, {})
    h = len(r.get("hearts",   {}))
    d = len(r.get("dislikes", {}))

    rows = [[
        InlineKeyboardButton(text=f"❤️ {h}" if h else "❤️",
                             callback_data=f"ank_r:h:{owner_uid}"),
        InlineKeyboardButton(text=f"👎🏻 {d}" if d else "👎🏻",
                             callback_data=f"ank_r:d:{owner_uid}"),
    ]]

    # Другий рядок: НАШ ЧАТ | СТВОРИТИ АНКЕТУ
    link_row = []
    chat_url = _chat_link[0]
    if chat_url:
        link_row.append(InlineKeyboardButton(
            text="⭐ НАШ ЧАТ",
            url=chat_url,
        ))
    link_row.append(InlineKeyboardButton(
        text="📝 СТВОРИТИ АНКЕТУ",
        url="https://t.me/LumenarAi_Bot?start=anketa",
    ))
    rows.append(link_row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def record_reaction(owner_uid: int, reactor_uid: int,
                    reactor_name: str, reactor_username: str,
                    rtype: str) -> tuple[bool, bool]:
    """
    Записує або знімає реакцію.
    rtype: "h" (heart) або "d" (dislike)
    Повертає: (is_heart, is_new_heart)
      is_new_heart=True якщо ❤️ новий (не повторний) → треба повідомити власника
    """
    if owner_uid not in _reactions:
        _reactions[owner_uid] = {"hearts": {}, "dislikes": {}}

    bucket_key  = "hearts"  if rtype == "h" else "dislikes"
    other_key   = "dislikes" if rtype == "h" else "hearts"
    info = {"name": reactor_name, "username": reactor_username}

    # Якщо вже є цей тип — знімаємо (toggle)
    if reactor_uid in _reactions[owner_uid][bucket_key]:
        del _reactions[owner_uid][bucket_key][reactor_uid]
        save_anketa_settings()
        _schedule_anketa_save()
        return (rtype == "h"), False

    # Видаляємо протилежну реакцію якщо була
    _reactions[owner_uid][other_key].pop(reactor_uid, None)
    _reactions[owner_uid][bucket_key][reactor_uid] = info
    save_anketa_settings()
    _schedule_anketa_save()
    return (rtype == "h"), (rtype == "h")


def get_hearts(owner_uid: int) -> dict[int, dict]:
    """Повертає словник {reactor_uid: info} для ❤️."""
    return _reactions.get(owner_uid, {}).get("hearts", {})


def make_mutual_kb(reactor_uid: int, owner_uid: int) -> InlineKeyboardMarkup:
    """Кнопки уведомления о лайке."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="💞 Ответить взаимностью",
            callback_data=f"ank_mutual:{reactor_uid}:{owner_uid}",
        ),
    ], [
        InlineKeyboardButton(
            text="👀 Посмотреть, кто лайкнул",
            callback_data=f"ank_likers:{owner_uid}",
        ),
    ]])


def make_likers_kb(owner_uid: int) -> InlineKeyboardMarkup | None:
    """Кнопки просмотра конкретных лайкнувших и ответа взаимностью."""
    rows = []
    for reactor_uid, info in get_hearts(owner_uid).items():
        name = str((info or {}).get("name") or f"ID {reactor_uid}")
        name = " ".join(name.split())[:28]
        rows.append([
            InlineKeyboardButton(
                text=f"👀 {name}",
                callback_data=f"ank_liker:{reactor_uid}:{owner_uid}",
            ),
            InlineKeyboardButton(
                text="💞",
                callback_data=f"ank_mutual:{reactor_uid}:{owner_uid}",
            ),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def make_liker_view_kb(reactor_uid: int, owner_uid: int) -> InlineKeyboardMarkup:
    """Действия при приватном просмотре анкеты лайкнувшего."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="💞 Ответить взаимностью",
            callback_data=f"ank_mutual:{reactor_uid}:{owner_uid}",
        ),
    ], [
        InlineKeyboardButton(
            text="👀 Все лайки",
            callback_data=f"ank_likers:{owner_uid}",
        ),
    ]])


def _make_mod_kb(app_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"ank_ok:{app_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"ank_no:{app_id}"),
        ],
        [
            InlineKeyboardButton(text="✏️ Правки (написать автору)", callback_data=f"ank_cm:{app_id}"),
        ],
    ])


def make_my_anketa_kb(uid: int) -> InlineKeyboardMarkup:
    """Инлайн-кнопки под просмотром своей анкеты."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🗑 Удалить анкету", callback_data=f"ank_del:{uid}"),
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"ank_edit:{uid}"),
    ]])


def make_pending_anketa_kb(uid: int) -> InlineKeyboardMarkup:
    """Кнопка удаления заявки, пока она ожидает модерации."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🗑 Удалить заявку",
            callback_data=f"ank_del:{uid}",
        ),
    ]])


def make_new_anketa_kb(uid: int) -> InlineKeyboardMarkup:
    """Кнопка запуска новой анкеты после удаления старой."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="📝 Создать новую анкету",
            callback_data=f"ank_start:{uid}",
        ),
    ]])


def _app_id(user_id: int) -> str:
    return f"app_{user_id}"


# ──────────────────────────────────────────
# ОБРОБНИКИ КРОКІВ (викликаються з bot.py)
# ──────────────────────────────────────────
async def start_anketa(bot_obj, msg, force: bool = False) -> None:
    """Починає заповнення анкети — спочатку пропонує вибір мови."""
    uid = msg.from_user.id
    if uid in _sessions:
        await _answer_custom(
            msg, "anketa_duplicate",
            "📋 Ты уже заполняешь анкету!\n"
            "Напиши /отмена чтобы отменить.",
        )
        return
    # Скидаємо попередній статус якщо force (редагування)
    if force:
        _user_status.pop(uid, None)
        _approved_data.pop(uid, None)

    # step = -1 означає «чекаємо вибір мови»
    _sessions[uid] = {
        "step":        -1,
        "answers":     {},
        "username":    msg.from_user.username or "",
        "full_name":   msg.from_user.full_name,
        "lang":        None,
        "media_items": [],   # збираємо сюди фото/відео
    }
    await _answer_custom(
        msg, "anketa_start",
        f"{brand.hdr()}\n\n"
        f"{brand.acc()} <b>Анкета знакомств</b>\n\n"
        "Выберите язык:\n\n"
        f"{brand.div()}",
        reply_markup=_lang_kb()
    )


async def cancel_anketa(msg) -> bool:
    uid = msg.from_user.id
    if uid in _sessions:
        del _sessions[uid]
        await _answer_custom(
            msg, "anketa_cancel",
            f"{brand.hdr()}\n\n"
            f"{brand.bul()} <b>Заполнение анкеты отменено</b>\n\n"
            "Начать снова: /анкета\n\n"
            f"{brand.div()}"
        )
        return True
    await _answer_custom(
        msg, "anketa_cancel_none",
        "У тебя нет активной анкеты.",
    )
    return False


async def handle_lang_select(bot_obj, cb) -> None:
    """Обрабатывает выбор языка анкеты и запускает первый вопрос."""
    lang = "ru"
    uid  = cb.from_user.id

    session = _sessions.get(uid)
    if session is None or session.get("step") != -1:
        await cb.answer()
        return

    session["lang"] = lang
    session["step"] = 0
    qs = _lang_questions(lang)

    header = (
        f"{brand.hdr()}\n\n"
        f"{brand.acc()} <b>Анкета знакомств</b>\n\n"
        "Отвечай на вопросы по очереди — после заполнения анкета будет опубликована автоматически.\n"
        "Напиши /отмена чтобы отменить.\n\n"
        f"{brand.div()}\n\n"
    )

    try:
        await cb.message.edit_text(
            header + _md_to_html(qs[0][1]),
            parse_mode="HTML",
            reply_markup=question_kb(uid, qs[0][0]),
        )
    except Exception:
        await cb.message.answer(
            header + _md_to_html(qs[0][1]),
            parse_mode="HTML",
            reply_markup=question_kb(uid, qs[0][0]),
        )
    await cb.answer()


def is_on_photo_step(uid: int) -> bool:
    """Чи чекає юзер медіа (фото або відео) — останній крок анкети."""
    session = _sessions.get(uid)
    return session is not None and session["step"] == PHOTO_STEP_IDX

is_on_media_step = is_on_photo_step  # alias


async def _send_media_group_to_chat(
    bot_obj,
    chat_id: int,
    media_items: list,
    caption: str | None = None,
    parse_mode: str | None = None,
) -> list[int]:
    """Відправляє альбом (2–10 медіа) з підписом на першому елементі.

    Telegram не дозволяє прикріпити inline-клавіатуру до sendMediaGroup,
    тому кнопки відправляються окремим reply-повідомленням викликаючого коду.
    Повертає список message_id надісланих повідомлень (потрібно для видалення).
    """
    group = []
    for index, item in enumerate(media_items):
        media_kwargs = {}
        if index == 0 and caption:
            media_kwargs["caption"] = caption
            if parse_mode:
                media_kwargs["parse_mode"] = parse_mode
        if item["type"] == "photo":
            group.append(InputMediaPhoto(media=item["file_id"], **media_kwargs))
        else:
            group.append(InputMediaVideo(media=item["file_id"], **media_kwargs))
    sent = await bot_obj.send_media_group(chat_id, media=group)
    return [m.message_id for m in (sent or [])]


async def _delete_sent_anketa_messages(
    bot_obj,
    chat_id: int | None,
    *message_ids,
) -> None:
    """Удаляет частично отправленную заявку после ошибки Telegram API."""
    if not chat_id:
        return
    seen: set[int] = set()
    for raw_id in message_ids:
        try:
            message_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if not message_id or message_id in seen:
            continue
        seen.add(message_id)
        try:
            await bot_obj.delete_message(chat_id, message_id)
        except Exception:
            pass


async def _finish_anketa(bot_obj, uid: int, session: dict) -> None:
    """Завершает заполнение и автоматически публикует анкету."""
    answers = dict(session["answers"])
    media_items = list(session.get("media_items", []))
    answers["media"] = media_items
    answers.pop("photo_id", None)
    answers.pop("video_id", None)
    username = session["username"]
    full_name = session["full_name"]
    pub_chat = get_pub_chat() or DEFAULT_PUBLIC_CHAT_ID
    anketa_num = next_anketa_number()
    pub_msg_id = None
    pub_control_msg_id = None
    pub_media_msg_ids: list[int] = []

    try:
        card = fmt_pub_card(answers, username, full_name)
        reaction_markup = reaction_kb(uid)
        count = len(media_items)

        if count == 0:
            sent = await bot_obj.send_message(
                pub_chat,
                card,
                parse_mode="HTML",
                reply_markup=reaction_markup,
            )
            pub_msg_id = sent.message_id
        elif count == 1:
            item = media_items[0]
            if item["type"] == "photo":
                sent = await bot_obj.send_photo(
                    pub_chat,
                    photo=item["file_id"],
                    caption=card,
                    parse_mode="HTML",
                    reply_markup=reaction_markup,
                )
            else:
                sent = await bot_obj.send_video(
                    pub_chat,
                    video=item["file_id"],
                    caption=card,
                    parse_mode="HTML",
                    reply_markup=reaction_markup,
                )
            pub_msg_id = sent.message_id
        else:
            pub_media_msg_ids = await _send_media_group_to_chat(
                bot_obj,
                pub_chat,
                media_items,
                caption=card,
                parse_mode="HTML",
            )
            control = await bot_obj.send_message(
                pub_chat,
                "💞 <b>Реакции на анкету:</b>",
                parse_mode="HTML",
                reply_markup=reaction_markup,
                reply_to_message_id=(
                    pub_media_msg_ids[0] if pub_media_msg_ids else None
                ),
                allow_sending_without_reply=True,
            )
            pub_control_msg_id = control.message_id
            pub_msg_id = pub_media_msg_ids[0] if pub_media_msg_ids else control.message_id

        set_approved(
            uid,
            answers,
            username,
            full_name,
            pub_msg_id=pub_msg_id,
            pub_chat_id=pub_chat,
            anketa_num=anketa_num,
            media_msg_ids=pub_media_msg_ids,
            pub_control_msg_id=pub_control_msg_id,
        )

        await _send_custom(
            bot_obj,
            uid,
            "anketa_auto_confirm",
            f"{brand.hdr()}\n\n"
            f"{brand.chk()} <b>Анкета №{anketa_num} опубликована!</b>\n\n"
            "Она уже доступна в ленте знакомств. "
            "Ты можешь посмотреть, изменить или удалить её кнопками ниже.\n\n"
            f"{brand.div()}",
            reply_markup=make_my_anketa_kb(uid),
        )
    except Exception as error:
        await _delete_sent_anketa_messages(
            bot_obj,
            pub_chat,
            pub_msg_id,
            pub_control_msg_id,
            *pub_media_msg_ids,
        )
        print(f"⚠️ Ошибка автопубликации анкеты {uid}: {error}")
        await bot_obj.send_message(
            uid,
            "❌ Не удалось автоматически опубликовать анкету. "
            "Попробуй ещё раз через /анкета.",
        )


async def handle_media_step(bot_obj, msg) -> bool:
    """
    Обробляє фото або відео надіслане під час медіа-кроку анкети.
    Збирає до 10 медіа; після 10 — автоматично завершує.
    Повертає True якщо оброблено.
    """
    uid = msg.from_user.id
    if not is_on_photo_step(uid):
        return False

    session = _sessions.get(uid)
    if session is None:
        return False

    if msg.photo:
        file_id    = msg.photo[-1].file_id
        media_type = "photo"
    elif msg.video:
        file_id    = msg.video.file_id
        media_type = "video"
    else:
        return False

    if "media_items" not in session:
        session["media_items"] = []

    session["media_items"].append({"type": media_type, "file_id": file_id})
    count = len(session["media_items"])
    lang  = session.get("lang", "uk")

    if count >= 10:
        # Автозавершення при 10 медіа
        session = _sessions.pop(uid)
        await msg.answer(
            f"{brand.chk()} <b>Добавлено 10 медиа — достигнут максимум!</b>\n\nОтправляем анкету…"
            if lang != "ru" else
            f"{brand.chk()} <b>10 медиа добавлено — максимум достигнут!</b>\n\nОтправляем анкету…",
            parse_mode="HTML",
        )
        await _finish_anketa(bot_obj, uid, session)
        return True

    emoji = "📷" if media_type == "photo" else "🎬"
    if lang == "ru":
        ack = (
            f"{emoji} *Медиа {count}/10 принято!*\n\n"
            f"Отправь ещё фото/видео или нажми *«✅ Готово»*.\n"
            f"_Чтобы пропустить медиа — «⏭ Без медиа»._"
        )
    else:
        ack = (
            f"{emoji} *Медиа {count}/10 принято!*\n\n"
            f"Отправь ещё фото/видео или нажми *«✅ Готово»*.\n"
            f"_Чтобы пропустить — «⏭ Без медиа»._"
        )
    await msg.answer(ack, parse_mode="Markdown", reply_markup=_media_done_kb(uid))
    return True


# backward-compat alias
async def handle_photo_step(bot_obj, msg) -> bool:
    return await handle_media_step(bot_obj, msg)


async def handle_anketa_step(bot_obj, msg) -> bool:
    """
    Обробляє черговий текстовий крок анкети.
    Повертає True якщо повідомлення оброблено.
    """
    uid = msg.from_user.id
    if uid not in _sessions:
        return False
    if not msg.text or msg.text.startswith("/"):
        return False

    session = _sessions[uid]
    step    = session["step"]

    # Ще не обрана мова → тихо ігноруємо (чекаємо натискання кнопки)
    if step == -1:
        return True

    lang = session.get("lang", "uk")
    qs   = _lang_questions(lang)

    # ── Медіа-крок: юзер написав текст замість фото/відео
    if step == PHOTO_STEP_IDX:
        lo = msg.text.strip().lower()
        if lo in _SKIP_MEDIA:
            # Пропустити медіа — відправляємо без фото/відео
            session["media_items"] = []
            session = _sessions.pop(uid)
            await _finish_anketa(bot_obj, uid, session)
        elif lo in _DONE_WORDS:
            # «Готово» — відправляємо з тим що є
            session = _sessions.pop(uid)
            await _finish_anketa(bot_obj, uid, session)
        else:
            count = len(session.get("media_items", []))
            if lang == "ru":
                hint = (
                    f"📸 Отправь фото или видео. Добавлено: <b>{count}/10</b>.\n"
                    f"Нажми <b>«✅ Готово»</b> чтобы завершить, "
                    f"или <b>«⏭ Без медиа»</b>, чтобы пропустить."
                )
            else:
                hint = (
                    f"📸 Отправь фото или видео. Добавлено: <b>{count}/10</b>.\n"
                    f"Нажми <b>«✅ Готово»</b>, чтобы завершить, "
                    f"или <b>«⏭ Без медиа»</b>, чтобы пропустить."
                )
            await msg.answer(hint, parse_mode="HTML",
                             reply_markup=_media_done_kb(uid))
        return True

    # ── Звичайний крок
    key = QUESTION_KEYS[step]
    session["answers"][key] = msg.text.strip()
    session["step"] += 1
    next_step = session["step"]

    if next_step >= len(qs):
        # Всі текстові питання пройдено → переходимо до фото-кроку
        total = len(qs) + 1
        await msg.answer(
            f"{brand.chk()} <b>Принято!</b>\n\n"
            f"{brand.div()}\n"
            f"<i>Шаг {next_step} из {total} — последний!</i>\n\n"
            f"{_md_to_html(_lang_photo_text(lang))}",
            parse_mode="HTML"
        )
    else:
        _, question_text = qs[next_step]
        total = len(qs) + 1
        await msg.answer(
            f"{brand.chk()} <b>Принято!</b>\n\n"
            f"{brand.div()}\n"
            f"<i>Шаг {next_step} из {total}</i>\n\n"
            f"{_md_to_html(question_text)}",
            parse_mode="HTML",
            reply_markup=question_kb(uid, qs[next_step][0]),
        )
    return True


async def handle_question_choice(bot_obj, cb) -> bool:
    """Сохраняет ответ на вопрос-кнопку и показывает следующий шаг."""
    try:
        parts = cb.data.split(":")
        if len(parts) != 4:
            raise ValueError
        uid = int(parts[1])
        key = parts[2]
        option_index = int(parts[3])
    except (TypeError, ValueError):
        await cb.answer("Некорректная кнопка", show_alert=True)
        return True

    if cb.from_user.id != uid:
        await cb.answer("Это не твоя анкета", show_alert=True)
        return True
    session = _sessions.get(uid)
    if not session or session.get("step") < 0:
        await cb.answer("Анкета уже завершена или устарела", show_alert=True)
        return True
    qs = _lang_questions(session.get("lang", "ru"))
    step = int(session.get("step", 0))
    if step >= len(qs) or qs[step][0] != key:
        await cb.answer("Этот вопрос уже закрыт", show_alert=True)
        return True
    options = QUESTION_OPTIONS.get(key, [])
    if option_index < 0 or option_index >= len(options):
        await cb.answer("Вариант недоступен", show_alert=True)
        return True

    session["answers"][key] = options[option_index][1]
    session["step"] = step + 1
    await cb.answer("✅ Сохранено")
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if session["step"] >= len(qs):
        total = len(qs) + 1
        await cb.message.answer(
            f"{brand.chk()} <b>Принято!</b>\n\n"
            f"{brand.div()}\n"
            f"<i>Шаг {session['step']} из {total} — последний!</i>\n\n"
            f"{_md_to_html(_lang_photo_text(session.get('lang', 'ru')))}",
            parse_mode="HTML",
        )
    else:
        next_key, next_text = qs[session["step"]]
        total = len(qs) + 1
        await cb.message.answer(
            f"{brand.chk()} <b>Принято!</b>\n\n"
            f"{brand.div()}\n"
            f"<i>Шаг {session['step']} из {total}</i>\n\n"
            f"{_md_to_html(next_text)}",
            parse_mode="HTML",
            reply_markup=question_kb(uid, next_key),
        )
    return True


async def handle_mod_comment_step(bot_obj, msg) -> bool:
    """Модератор надсилає правки у чаті модерації."""
    mod_id = msg.from_user.id
    if mod_id not in _mod_commenting:
        return False

    app_id = _mod_commenting.pop(mod_id)
    app = _pending.get(app_id)
    if not app:
        return False

    comment_text = msg.text or ""
    user_id  = app["user_id"]
    mod_name = msg.from_user.full_name

    try:
        await _send_custom(
            bot_obj, user_id, "mod_comment",
            f"{brand.hdr()}\n\n"
            f"✏️ <b>Правки от модератора:</b>\n\n"
            f"{_h(comment_text)}\n\n"
            f"{brand.div()}\n"
            "<i>Исправь и отправь снова: /анкета</i>"
        )
        await msg.reply(
            f"✅ Правки отправлены автору <b>{_h(app['full_name'])}</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        await msg.reply(f"❌ Не удалось отправить: {e}")
    return True
