"""
Система анкет знайомств Lumena
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Користувач заповнює анкету в особистих →
Карточка летить у чат МОДЕРАЦІЇ (з кнопками) →
Після схвалення — публікується в чат ПУБЛІКАЦІЙ
Статуси: none → pending → approved / rejected
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
     "👤 *Як тебе звати?*\n_(ім'я або нікнейм)_"),
    ("age",
     "🎂 *Скільки тобі років?*"),
    ("district",
     "🏙 *Твій район?*\n_(район або мікрорайон міста)_"),
    ("goal",
     "🎯 *Мета знайомства*\n_(спілкування, дружба, відносини, без різниці)_"),
    ("looking_for",
     "💖 *Кого шукаєш?*\n_(дівчину, хлопця, не важливо)_"),
    ("smoking",
     "🚬 *Куріння*\n_(Курю / Не курю / Іноді)_"),
    ("kids",
     "👶 *Діти*\n_(Є / Немає / Хочу в майбутньому)_"),
    ("about",
     "📝 *Про себе*\n_(декілька речень: характер, інтереси, хто ти)_"),
]
QUESTION_KEYS = [k for k, _ in QUESTIONS]

# Фото-крок іде ПІСЛЯ всіх текстових питань
PHOTO_STEP_IDX = len(QUESTIONS)
PHOTO_STEP_TEXT = (
    "📸 *Фото та відео*\n\n"
    "Надішли від *1 до 10* фото або відео будь-якої тривалості.\n"
    "Коли закінчиш — натисни *«✅ Готово»*.\n\n"
    "Або напиши *«без фото»* щоб пропустити цей крок."
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
QUESTIONS_UK = QUESTIONS  # псевдонім — українська (оригінал)

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

PHOTO_STEP_TEXT_RU = (
    "📸 *Фото и видео*\n\n"
    "Отправь от *1 до 10* фото или видео любой длины.\n"
    "Когда закончишь — нажми *«✅ Готово»*.\n\n"
    "Или напиши *«без фото»* чтобы пропустить этот шаг."
)


def _lang_questions(lang: str) -> list[tuple[str, str]]:
    return QUESTIONS_RU if lang == "ru" else QUESTIONS_UK


def _lang_photo_text(lang: str) -> str:
    return PHOTO_STEP_TEXT_RU if lang == "ru" else PHOTO_STEP_TEXT


def _media_done_kb(uid: int) -> InlineKeyboardMarkup:
    """Кнопки під підтвердженням кожного медіа-файлу."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Готово",       callback_data=f"ank_media_done:{uid}"),
        InlineKeyboardButton(text="⏭ Без медіа",   callback_data=f"ank_media_skip:{uid}"),
    ]])


def _lang_kb() -> InlineKeyboardMarkup:
    """Клавіатура вибору мови анкети."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇺🇦 Українська", callback_data="ank_lang:uk"),
        InlineKeyboardButton(text="🇷🇺 Русский",    callback_data="ank_lang:ru"),
    ]])


# ──────────────────────────────────────────
# ЗБЕРІГАННЯ ДАНИХ
# ──────────────────────────────────────────
_sessions: dict[int, dict] = {}
# {user_id: {"step": int, "answers": {}, "username": str, "full_name": str}}

_pending: dict[str, dict] = {}
# {app_id: {...}}

_mod_commenting: dict[int, str] = {}
# {mod_user_id: app_id}

_mod_chat_id: list[int | None] = [None]
_pub_chat_id: list[int | None] = [None]
_chat_link:   list[str | None] = [None]   # посилання на головний чат
_anketa_counter: list[int] = [0]  # глобальний лічильник анкет

# Статуси анкет юзерів
# "pending" | "approved" | "rejected" | відсутній = немає анкети
_user_status: dict[int, str] = {}

# Дані схвалених анкет
# {uid: {"answers": {}, "username": str, "full_name": str, "pub_msg_id": int|None}}
_approved_data: dict[int, dict] = {}

# Реакції в пабліку (in-memory, скидаються при рестарті)
# {owner_uid: {"hearts": {reactor_uid: {"name": str, "username": str}},
#              "dislikes": {reactor_uid: {"name": str, "username": str}}}}
_reactions: dict[int, dict] = {}

ANKETA_DATA_FILE = "data/anketa_settings.json"
ANKETA_USERS_FILE = "data/anketa_users.json"


# ──────────────────────────────────────────
# ЗБЕРЕЖЕННЯ / ЗАВАНТАЖЕННЯ
# ──────────────────────────────────────────
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
            if data:
                with open(local, "w", encoding="utf-8") as f:
                    import json as _j
                    _j.dump(data, f, ensure_ascii=False)
                print(f"✅ {pg_key} відновлено з PostgreSQL")
                continue
            print(f"⚠️ PostgreSQL: {pg_key} порожній")

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
            _anketa_counter[0]  = d.get("anketa_counter", 0)
            _chat_link[0]       = d.get("chat_link")
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
        except Exception:
            pass


def save_anketa_settings():
    """Зберігає anketa дані на диск.
    PostgreSQL/GitHub sync виконується тільки через _save_all_to_db() в bot.py
    (auto_save_loop + shutdown handler) — без race conditions.
    """
    os.makedirs("data", exist_ok=True)
    settings_payload = {
        "mod_chat_id":    _mod_chat_id[0],
        "pub_chat_id":    _pub_chat_id[0],
        "anketa_counter": _anketa_counter[0],
        "chat_link":      _chat_link[0],
    }
    users_payload = {
        "status":   {str(k): v for k, v in _user_status.items()},
        "approved": {str(k): v for k, v in _approved_data.items()},
    }
    with open(ANKETA_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(settings_payload, f, ensure_ascii=False)
    with open(ANKETA_USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users_payload, f, ensure_ascii=False)


def next_anketa_number() -> int:
    """Повертає наступний номер анкети і зберігає лічильник."""
    _anketa_counter[0] += 1
    save_anketa_settings()
    return _anketa_counter[0]


# ──────────────────────────────────────────
# ПУБЛІЧНІ ФУНКЦІЇ СТАТУСІВ
# ──────────────────────────────────────────
def get_mod_chat() -> int | None:
    return _mod_chat_id[0]

def set_mod_chat(chat_id: int):
    _mod_chat_id[0] = chat_id
    save_anketa_settings()

def get_pub_chat() -> int | None:
    return _pub_chat_id[0]

def set_pub_chat(chat_id: int | None):
    _pub_chat_id[0] = chat_id
    save_anketa_settings()

def get_chat_link() -> str | None:
    return _chat_link[0]

def set_chat_link(link: str):
    _chat_link[0] = link
    save_anketa_settings()

def get_user_status(uid: int) -> str | None:
    """none / pending / approved / rejected"""
    return _user_status.get(uid)

def set_pending(uid: int):
    _user_status[uid] = "pending"
    save_anketa_settings()

def set_approved(uid: int, answers: dict, username: str, full_name: str,
                 pub_msg_id: int | None = None, pub_chat_id: int | None = None):
    _user_status[uid] = "approved"
    _approved_data[uid] = {
        "answers":    answers,
        "username":   username,
        "full_name":  full_name,
        "pub_msg_id": pub_msg_id,
        "pub_chat_id": pub_chat_id,
    }
    save_anketa_settings()

def set_rejected(uid: int):
    _user_status[uid] = "rejected"
    _approved_data.pop(uid, None)
    save_anketa_settings()

def revoke_anketa(uid: int) -> dict | None:
    """Розжаловує схвалену анкету. Повертає збережені дані для видалення поста."""
    if _user_status.get(uid) not in ("approved", "pending"):
        return None
    data = _approved_data.pop(uid, None)
    _user_status.pop(uid, None)
    _reactions.pop(uid, None)
    save_anketa_settings()
    return data

def get_uid_by_pub_msg(msg_id: int, chat_id: int | None = None) -> int | None:
    """Знаходить uid власника анкети за msg_id публічного поста."""
    for uid, d in _approved_data.items():
        if d.get("pub_msg_id") == msg_id:
            if chat_id is None or d.get("pub_chat_id") == chat_id:
                return uid
    return None


def delete_user_anketa(uid: int) -> dict | None:
    """Видаляє анкету, повертає дані (pub_msg_id тощо)."""
    _user_status.pop(uid, None)
    data = _approved_data.pop(uid, None)
    save_anketa_settings()
    return data

def get_approved_data(uid: int) -> dict | None:
    return _approved_data.get(uid)


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
        media_icon = " + ".join(parts) + f" ✅ ({len(media_list)} файл(ів))"
    else:
        media_icon = "❌ немає"
    vip_label = " 👑 VIP" if is_premium else ""
    num = anketa_num if anketa_num else "?"
    bul = brand.bul()
    return (
        f"{brand.hdr()}\n\n"
        f"{brand.acc()} <b>Нова анкета #{num}</b>{vip_label} — на модерацію\n\n"
        f"{brand.div()}\n"
        f"👤 <b>Ім'я:</b> {_h(answers.get('name', '—'))}\n"
        f"🎂 <b>Вік:</b> {_h(answers.get('age', '—'))}\n"
        f"🏙 <b>Район:</b> {_h(answers.get('district', '—'))}\n\n"
        f"🎯 <b>Ціль:</b> {_h(answers.get('goal', '—'))}\n"
        f"💖 <b>Шукаю:</b> {_h(answers.get('looking_for', '—'))}\n"
        f"🚬 <b>Куріння:</b> {_h(answers.get('smoking', '—'))}\n"
        f"👶 <b>Діти:</b> {_h(answers.get('kids', '—'))}\n\n"
        f"📝 <b>Про себе:</b>\n{_h(answers.get('about', '—'))}\n\n"
        f"{brand.div()}\n"
        f"🔗 {_h(tag)}  ·  🆔 <code>{user_id}</code>\n"
        f"{bul} Медіа: {_h(media_icon)}"
    )


def fmt_pub_card(answers: dict, username: str = "", full_name: str = "",
                 is_premium: bool = False) -> str:
    """Публічна картка — стиль як на фото."""
    cr   = brand.crown()
    bul  = brand.bul()
    header   = f"{cr} <b>VIP-ANKETA</b>" if is_premium else f"{brand.acc()} <b>Нова анкета</b>"
    vip_note = f"\n\n{cr} <b>VIP-анкета — приоритетная публикация</b>" if is_premium else ""
    tags     = "#анкетазнакомства #VIP" if is_premium else "#анкетазнакомства"
    return (
        f"{header}\n\n"
        f"{bul} <b>Имя:</b> {_h(answers.get('name', '—'))}\n"
        f"{bul} <b>Возраст:</b> {_h(answers.get('age', '—'))}\n"
        f"{bul} <b>Район:</b> {_h(answers.get('district', '—'))}\n\n"
        f"{bul} <b>Цель:</b> {_h(answers.get('goal', '—'))}\n"
        f"{bul} <b>Ищу:</b> {_h(answers.get('looking_for', '—'))}\n"
        f"{bul} <b>Курение:</b> {_h(answers.get('smoking', '—'))}\n"
        f"{bul} <b>Дети:</b> {_h(answers.get('kids', '—'))}\n\n"
        f"{bul} <b>О себе:</b>\n{_h(answers.get('about', '—'))}"
        f"{vip_note}\n\n"
        f"{tags}"
    )


def fmt_my_card(answers: dict, username: str, full_name: str,
                is_premium: bool = False) -> str:
    """Текст картки для перегляду юзером."""
    tag      = f"@{_h(username)}" if username else _h(full_name)
    cr       = brand.crown()
    bul      = brand.bul()
    header   = f"{cr} <b>VIP-ANKETA</b>" if is_premium else f"{brand.acc()} <b>Твоя анкета</b>"
    vip_note = f"\n\n{cr} <b>VIP-анкета — приоритетная публикация</b>" if is_premium else ""
    return (
        f"{brand.hdr()}\n\n"
        f"{header}\n\n"
        f"{brand.div()}\n"
        f"{bul} <b>Имя:</b> {_h(answers.get('name', '—'))}\n"
        f"{bul} <b>Возраст:</b> {_h(answers.get('age', '—'))}\n"
        f"{bul} <b>Район:</b> {_h(answers.get('district', '—'))}\n\n"
        f"{bul} <b>Цель:</b> {_h(answers.get('goal', '—'))}\n"
        f"{bul} <b>Ищу:</b> {_h(answers.get('looking_for', '—'))}\n"
        f"{bul} <b>Курение:</b> {_h(answers.get('smoking', '—'))}\n"
        f"{bul} <b>Дети:</b> {_h(answers.get('kids', '—'))}\n\n"
        f"{bul} <b>О себе:</b>\n{_h(answers.get('about', '—'))}"
        f"{vip_note}\n\n"
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
        return (rtype == "h"), False

    # Видаляємо протилежну реакцію якщо була
    _reactions[owner_uid][other_key].pop(reactor_uid, None)
    _reactions[owner_uid][bucket_key][reactor_uid] = info
    return (rtype == "h"), (rtype == "h")


def get_hearts(owner_uid: int) -> dict[int, dict]:
    """Повертає словник {reactor_uid: info} для ❤️."""
    return _reactions.get(owner_uid, {}).get("hearts", {})


def make_mutual_kb(reactor_uid: int, owner_uid: int) -> InlineKeyboardMarkup:
    """Кнопка 'Ответить взаимностью' — отправляется владельцу анкеты."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="💞 Ответить взаимностью",
            callback_data=f"ank_mutual:{reactor_uid}:{owner_uid}"
        )
    ]])


def _make_mod_kb(app_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Прийняти", callback_data=f"ank_ok:{app_id}"),
            InlineKeyboardButton(text="❌ Відхилити", callback_data=f"ank_no:{app_id}"),
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
        "Виберіть мову / Выберите язык:\n\n"
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
    """Обробляє вибір мови анкети — запускає перше питання."""
    lang = cb.data.split(":", 1)[1]  # "uk" або "ru"
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
        "Отвечай на вопросы по очереди — после заполнения анкета уйдёт на модерацию.\n"
        "Напиши /отмена чтобы отменить.\n\n"
        f"{brand.div()}\n\n"
    )

    try:
        await cb.message.edit_text(
            header + _md_to_html(qs[0][1]),
            parse_mode="HTML",
        )
    except Exception:
        await cb.message.answer(
            header + _md_to_html(qs[0][1]),
            parse_mode="HTML",
        )
    await cb.answer()


def is_on_photo_step(uid: int) -> bool:
    """Чи чекає юзер медіа (фото або відео) — останній крок анкети."""
    session = _sessions.get(uid)
    return session is not None and session["step"] == PHOTO_STEP_IDX

is_on_media_step = is_on_photo_step  # alias


async def _send_media_group_to_chat(bot_obj, chat_id: int, media_items: list) -> None:
    """Відправляє альбом (2–10 медіа) без підпису та кнопок."""
    group = []
    for item in media_items:
        if item["type"] == "photo":
            group.append(InputMediaPhoto(media=item["file_id"]))
        else:
            group.append(InputMediaVideo(media=item["file_id"]))
    await bot_obj.send_media_group(chat_id, media=group)


async def _finish_anketa(bot_obj, uid: int, session: dict) -> None:
    """Завершує анкету і надсилає в чат модерації."""
    answers     = session["answers"]
    media_items = session.get("media_items", [])
    answers["media"] = media_items        # список {"type","file_id"}
    answers.pop("photo_id", None)         # прибираємо старі поля
    answers.pop("video_id", None)
    username  = session["username"]
    full_name = session["full_name"]

    mod_chat = get_mod_chat()
    if not mod_chat:
        try:
            await bot_obj.send_message(
                uid,
                "✅ Анкета заполнена!\n\n"
                "⚠️ Чат модерации ещё не настроен — обратитесь к администратору."
            )
        except Exception:
            pass
        return

    anketa_num = next_anketa_number()
    card       = fmt_mod_card(answers, uid, username, full_name, anketa_num=anketa_num)
    app_id     = _app_id(uid)
    _pending.pop(app_id, None)

    try:
        n = len(media_items)
        if n == 0:
            # Без медіа — тільки текст
            sent = await bot_obj.send_message(
                mod_chat, card,
                parse_mode="HTML",
                reply_markup=_make_mod_kb(app_id),
            )
        elif n == 1:
            item = media_items[0]
            if item["type"] == "photo":
                sent = await bot_obj.send_photo(
                    mod_chat, photo=item["file_id"],
                    caption=card, parse_mode="HTML",
                    reply_markup=_make_mod_kb(app_id),
                )
            else:
                sent = await bot_obj.send_video(
                    mod_chat, video=item["file_id"],
                    caption=card, parse_mode="HTML",
                    reply_markup=_make_mod_kb(app_id),
                )
        else:
            # 2–10 медіа: спочатку альбом, потім картка з кнопками
            await _send_media_group_to_chat(bot_obj, mod_chat, media_items)
            sent = await bot_obj.send_message(
                mod_chat, card,
                parse_mode="HTML",
                reply_markup=_make_mod_kb(app_id),
            )

        _pending[app_id] = {
            "user_id":     uid,
            "answers":     answers,
            "username":    username,
            "full_name":   full_name,
            "mod_msg_id":  sent.message_id,
            "mod_chat_id": mod_chat,
            "media_count": n,
            "anketa_num":  anketa_num,
        }
        set_pending(uid)
        await _send_custom(
            bot_obj, uid, "anketa_confirm",
            f"{brand.hdr()}\n\n"
            f"{brand.acc()} <b>Анкета №{anketa_num} отправлена!</b>\n\n"
            "Администраторы рассмотрят её и уведомят тебя.\n\n"
            f"{brand.div()}"
        )
    except Exception as e:
        await bot_obj.send_message(uid, f"❌ Помилка надсилання: {e}")


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
            f"{brand.chk()} <b>10 медіа додано — максимум досягнуто!</b>\n\nВідправляємо анкету…"
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
            f"_Чтобы пропустить медиа — «⏭ Без медіа»._"
        )
    else:
        ack = (
            f"{emoji} *Медіа {count}/10 прийнято!*\n\n"
            f"Надішли ще фото/відео або натисни *«✅ Готово»*.\n"
            f"_Щоб пропустити — «⏭ Без медіа»._"
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
                    f"или <b>«⏭ Без медіа»</b> чтобы пропустить."
                )
            else:
                hint = (
                    f"📸 Надішли фото або відео. Додано: <b>{count}/10</b>.\n"
                    f"Натисни <b>«✅ Готово»</b> щоб завершити, "
                    f"або <b>«⏭ Без медіа»</b> щоб пропустити."
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
            parse_mode="HTML"
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
        await msg.reply(f"❌ Не вдалося надіслати: {e}")
    return True
