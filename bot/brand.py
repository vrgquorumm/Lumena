"""
Брендинг Лумены — Custom Premium emoji из стикер-пака Telegram.
Использует <tg-emoji emoji-id="..."> для HTML-сообщений.
При отсутствии пака — текстовые fallback.
"""
from __future__ import annotations
import os
import re

_pack_ids: list[str] = []
_pack_name: str = ""
_pack_enabled: bool = True
_emoji_map: dict[str, str] = {}

# ── Кастомный стиль ───────────────────────────────────────
_custom_style: dict[str, str] = {}

# Описания редактируемых параметров стиля
STYLE_DEFS: dict[str, dict] = {
    # ── Оформление ────────────────────────────────────────
    "header_text":  {
        "desc":    "Текст заголовка",
        "default": "✨ L U M E N A ✨",
        "hint":    'Показывается в шапке каждого ответа. Пример: «L U M E N A» или «✨ LUMENA ✨»',
        "max":     40,
    },
    "divider_char": {
        "desc":    "Символ разделителя",
        "default": "═",
        "hint":    "Повторяется N раз как горизонтальная черта. Один символ или emoji.",
        "max":     8,
    },
    "divider_count": {
        "desc":    "Длина разделителя",
        "default": "14",
        "hint":    "Сколько символов в разделителе. Число от 3 до 30.",
        "max":     2,
    },
    "bullet_char":  {
        "desc":    "Буллет-поинт",
        "default": "✦",
        "hint":    "Символ в начале пунктов списка. Один символ или emoji.",
        "max":     8,
    },
    "accent_char":  {
        "desc":    "Акцентный символ",
        "default": "◆",
        "hint":    "Используется для выделения важного. Один символ или emoji.",
        "max":     8,
    },
    "bot_display_name": {
        "desc":    "Имя бота в фразах",
        "default": "Lumena",
        "hint":    "Как бот называет себя. Пример: Лумена, Lumena, Lumena Bot",
        "max":     30,
    },
    "community_name": {
        "desc":    "Название сообщества",
        "default": "Lumena",
        "hint":    "Название проекта/сообщества в приветствиях и описаниях.",
        "max":     30,
    },
    # ── Экономика ─────────────────────────────────────────
    "currency_name": {
        "desc":    "Название монеты",
        "default": "LMN",
        "hint":    "Обозначение валюты в экономике. Пример: LMN, COIN, ЛМН",
        "max":     10,
    },
    "currency_emoji": {
        "desc":    "Эмодзи монеты",
        "default": "💎",
        "hint":    "Показывается рядом с балансом. Один символ или emoji.",
        "max":     4,
    },
    "work_emoji": {
        "desc":    "Символ работы",
        "default": "💼",
        "hint":    "Показывается в командах работа/смена.",
        "max":     4,
    },
    "fish_emoji": {
        "desc":    "Символ рыбалки",
        "default": "🎣",
        "hint":    "Показывается в команде рыбалка.",
        "max":     4,
    },
    "casino_emoji": {
        "desc":    "Символ казино",
        "default": "🎰",
        "hint":    "Показывается в команде казино.",
        "max":     4,
    },
    "slots_emoji": {
        "desc":    "Символ слотов",
        "default": "🎲",
        "hint":    "Показывается в команде слоты.",
        "max":     4,
    },
    "rob_emoji": {
        "desc":    "Символ ограбления",
        "default": "🦹",
        "hint":    "Показывается в команде ограбить.",
        "max":     4,
    },
    # ── Социальное ────────────────────────────────────────
    "fire_emoji": {
        "desc":    "Символ огня / стрика",
        "default": "🔥",
        "hint":    "Используется в чекинах и стриках.",
        "max":     4,
    },
    "marry_emoji": {
        "desc":    "Символ брака",
        "default": "💍",
        "hint":    "Показывается в командах брак/замуж/развод.",
        "max":     4,
    },
    "rep_emoji": {
        "desc":    "Символ репутации",
        "default": "⭐",
        "hint":    "Показывается в топе и профиле репутации.",
        "max":     4,
    },
    "aura_emoji": {
        "desc":    "Символ ауры",
        "default": "✨",
        "hint":    "Показывается в команде аура.",
        "max":     4,
    },
    "coin_emoji": {
        "desc":    "Символ монетки (игра)",
        "default": "🪙",
        "hint":    "Показывается в игре «монетка».",
        "max":     4,
    },
    "gift_emoji": {
        "desc":    "Символ подарка",
        "default": "🎁",
        "hint":    "Показывается в социальной команде подарить.",
        "max":     4,
    },
    "vip_emoji": {
        "desc":    "Символ VIP",
        "default": "👑",
        "hint":    "Показывается у VIP-пользователей.",
        "max":     4,
    },
    # ── Модерация ─────────────────────────────────────────
    "mute_emoji": {
        "desc":    "Символ мута",
        "default": "🔇",
        "hint":    "Показывается при выдаче мута.",
        "max":     4,
    },
    "ban_emoji": {
        "desc":    "Символ бана",
        "default": "🚫",
        "hint":    "Показывается при выдаче бана.",
        "max":     4,
    },
    "warn_emoji": {
        "desc":    "Символ варна",
        "default": "⚠️",
        "hint":    "Показывается при выдаче предупреждения.",
        "max":     4,
    },
    "kick_emoji": {
        "desc":    "Символ кика",
        "default": "👢",
        "hint":    "Показывается при кике из чата.",
        "max":     4,
    },
}


def get_style(key: str) -> str:
    """Текущее значение стиля (кастомное или дефолтное)."""
    return _custom_style.get(key) or STYLE_DEFS.get(key, {}).get("default", "")


def em(style_key: str, fallback: str = "") -> str:
    """Эмодзи/символ из настроек стиля (кастомный или fallback)."""
    return _custom_style.get(style_key) or fallback


def currency() -> str:
    """Название монеты из настроек (LMN по умолчанию)."""
    return _custom_style.get("currency_name") or "LMN"


def is_style_customized(key: str) -> bool:
    return key in _custom_style and _custom_style[key] != STYLE_DEFS.get(key, {}).get("default")


def set_style(key: str, value: str) -> None:
    _custom_style[key] = value


def reset_style(key: str) -> None:
    _custom_style.pop(key, None)


def reset_all_styles() -> None:
    """Сбрасывает ВСЕ кастомные стили — возвращает премиальные дефолты из STYLE_DEFS."""
    _custom_style.clear()


def reset_all_buttons() -> None:
    """Сбрасывает ВСЕ кастомные кнопки — возвращает премиальные дефолты из BUTTON_DEFS."""
    _custom_buttons.clear()


def all_custom_styles() -> dict:
    return dict(_custom_style)


def save_custom_style(path: str = "data/custom_style.json") -> None:
    import json, os
    os.makedirs("data", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_custom_style, f, ensure_ascii=False, indent=2)


def load_custom_style(path: str = "data/custom_style.json") -> None:
    import json
    try:
        with open(path, encoding="utf-8") as f:
            _custom_style.update(json.load(f))
    except FileNotFoundError:
        pass
    except Exception as ex:
        print(f"⚠️ load_custom_style: {ex}")


async def push_custom_style_to_github(path: str = "data/custom_style.json") -> bool:
    """Зберігає custom_style в PostgreSQL (і локальний файл)."""
    save_custom_style(path)
    try:
        import db as _db
        await _db.save_kv("custom_style", _custom_style)
        print("✅ custom_style збережено в PostgreSQL")
        return True
    except Exception as ex:
        print(f"⚠️ push_custom_style_to_github (DB): {ex}")
        return False


# Текстовые fallback для каждой роли
_FALLBACK: dict[str, str] = {
    "header":  "🖤",
    "bullet":  "◾",
    "divider": "▬",
    "accent":  "◆",
    "check":   "✔",
    "cross":   "✖",
    "crown":   "👑",
    "star":    "⭐",
    "heart":   "❤️",
    "ok":      "✅",
    "warn":    "⚠️",
    "dot":     "•",
}

# Индекс из пака для каждой роли
_ROLE_IDX: dict[str, int] = {
    "header":  0,
    "bullet":  1,
    "divider": 2,
    "accent":  3,
    "check":   4,
    "cross":   5,
    "crown":   6,
    "star":    7,
    "heart":   8,
    "ok":      9,
    "warn":    10,
    "dot":     11,
}


def e(role: str, fallback: str | None = None) -> str:
    """Текстовый символ для HTML-сообщений.
    Если выбран custom emoji-пак, Telegram получает настоящий тег tg-emoji.
    При недоступном Premium автоматически остаётся обычный Unicode fallback."""
    fallback = fallback if fallback is not None else _FALLBACK.get(role, "•")
    custom_id = get_role_id(role)
    if custom_id and _pack_enabled:
        return f'<tg-emoji emoji-id="{custom_id}">{fallback}</tg-emoji>'
    return fallback


def ei(idx: int, fallback: str = "•") -> str:
    """Custom emoji из пака по индексу с безопасным Unicode fallback."""
    custom_id = get_id(idx)
    if custom_id and _pack_enabled:
        return f'<tg-emoji emoji-id="{custom_id}">{fallback}</tg-emoji>'
    return fallback


def get_id(idx: int) -> str | None:
    """ID кастомного emoji из пака по индексу (для entity-подхода, не для HTML)."""
    return _pack_ids[idx] if idx < len(_pack_ids) else None


def get_role_id(role: str) -> str | None:
    """ID кастомного emoji из пака по роли (для entity-подхода, не для HTML)."""
    idx = _ROLE_IDX.get(role)
    return _pack_ids[idx] if idx is not None and idx < len(_pack_ids) else None


def hdr() -> str:
    """Премиальный заголовок — настоящий Rich Message <h1> (Bot API 10.1)."""
    em   = e("header")
    name = get_style("header_text")
    return f"<h1>{em} {name} {em}</h1>"


def div(n: int | None = None) -> str:
    """Премиальный разделитель — настоящий Rich Message <hr> (Bot API 10.1).
    Параметр n сохранён для обратной совместимости вызовов, но больше не влияет
    на вид: длину/толщину разделителя теперь рисует сам Telegram-клиент."""
    return "<hr>"


def bul() -> str:
    """Буллет-поинт."""
    return _custom_style.get("bullet_char") or e("bullet", "◾")


def acc() -> str:
    """Акцентный символ."""
    return _custom_style.get("accent_char") or e("accent", "◆")


def chk() -> str:
    """Галочка / принято."""
    return e("check", "✔")


def crown() -> str:
    """Корона для VIP."""
    return e("crown", "👑")


def quote(text: str, expandable: bool = False) -> str:
    """Премиальная HTML-цитата (Bot API blockquote), опционально сворачиваемая."""
    tag = 'blockquote expandable="true"' if expandable else "blockquote"
    close = "blockquote"
    return f"<{tag}>{text}</{close}>"


def spoiler(text: str) -> str:
    """Скрытый спойлер-текст (Bot API tg-spoiler)."""
    return f"<tg-spoiler>{text}</tg-spoiler>"


def underline(text: str) -> str:
    """Подчёркнутый текст."""
    return f"<u>{text}</u>"


def strike(text: str) -> str:
    """Зачёркнутый текст."""
    return f"<s>{text}</s>"


def code(text: str) -> str:
    """Инлайн-код (моноширинный, для чисел/id/значений)."""
    return f"<code>{text}</code>"


def code_block(text: str, lang: str = "") -> str:
    """Блок кода (Bot API pre + language)."""
    lang_attr = f' class="language-{lang}"' if lang else ""
    return f"<pre{lang_attr}>{text}</pre>"


def set_pack(
    ids: list[str],
    name: str = "",
    emoji_map: dict[str, str] | None = None,
) -> None:
    """Устанавливает emoji-пак и, если доступна, карту Unicode → custom ID."""
    global _pack_ids, _pack_name, _pack_enabled, _emoji_map
    previous_map = dict(_emoji_map)
    _pack_ids = [str(value) for value in ids if str(value).strip()][:100]
    _pack_name = str(name or "")[:128]
    _pack_enabled = bool(_pack_ids)
    if emoji_map is not None:
        allowed = set(_pack_ids)
        _emoji_map = {
            str(emoji): str(custom_id)
            for emoji, custom_id in emoji_map.items()
            if str(emoji) and str(custom_id) in allowed
        }
    else:
        # Сохраняем уже известную карту при ручной смене header ID.
        allowed = set(_pack_ids)
        _emoji_map = {
            emoji: custom_id
            for emoji, custom_id in previous_map.items()
            if custom_id in allowed
        }


def disable_pack_runtime() -> None:
    """Временно отключает custom emoji до следующего успешного set_pack()."""
    global _pack_enabled
    _pack_enabled = False


def pack_name_from_reference(value: str) -> str:
    """Извлекает имя custom emoji-пака из URL или короткого имени.

    Поддерживаются ссылки Telegram вида:
    https://t.me/addemoji/PackName
    https://t.me/addstickers/PackName
    а также обычное имя пака для /setemojipack.
    """
    raw = str(value or "").strip()
    match = re.search(
        r"(?:https?://)?(?:t\.me|telegram\.me)/(?:addemoji|addstickers)/([A-Za-z0-9_]+)",
        raw,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_]{1,128}", raw):
        return raw
    return ""


def get_pack() -> list[str]:
    return list(_pack_ids)


def get_pack_name() -> str:
    return _pack_name


def get_pack_emoji_map() -> dict[str, str]:
    """Возвращает карту fallback-символов пака для сохранения в snapshot."""
    return dict(_emoji_map)


def has_emoji_map() -> bool:
    return bool(_emoji_map)


def has_pack() -> bool:
    return bool(_pack_ids) and _pack_enabled


def preview(n: int = 12) -> str:
    """HTML-строка с превью первых n emoji из пака (использует <tg-emoji> напрямую)."""
    parts = []
    for i in range(min(n, len(_pack_ids))):
        eid = _pack_ids[i]
        parts.append(f'<tg-emoji emoji-id="{eid}">[{i}]</tg-emoji>')
    return "".join(parts) if parts else "(пак не загружен)"


_TG_EMOJI_TAG_RE = re.compile(
    r"<tg-emoji\b[^>]*>.*?</tg-emoji>", flags=re.IGNORECASE | re.DOTALL
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_EMOJI_BASE = (
    r"[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF"
    r"\u2300-\u23FF\u2600-\u27BF]"
)
_REGIONAL_BASE = r"[\U0001F1E6-\U0001F1FF]"
_EMOJI_SEQUENCE_RE = re.compile(
    rf"(?:"
    # Два regional-indicator символа — один флаг, а не два отдельных emoji.
    rf"{_REGIONAL_BASE}{_REGIONAL_BASE}"
    rf"|{_EMOJI_BASE}(?:[\ufe0e\ufe0f\U0001F3FB-\U0001F3FF])?"
    rf"|[#*0-9]\ufe0f?\u20e3"
    rf")"
    rf"(?:\u200d{_EMOJI_BASE}(?:[\ufe0e\ufe0f\U0001F3FB-\U0001F3FF])?)*"
)


def _custom_emoji_tag(emoji: str, custom_id: str) -> str:
    return f'<tg-emoji emoji-id="{custom_id}">{emoji}</tg-emoji>'


def replace_emojis_html(text: str | None) -> str | None:
    """Заменяет каждую emoji-последовательность на custom emoji пака.

    Для emoji, у которого нет одноимённого fallback в sticker-set, используется
    первый custom emoji пака. Это гарантирует оформление и для новых/редких
    Unicode-символов, которых не было в метаданных пака.
    """
    if not text or not has_pack():
        return text

    placeholders: list[str] = []

    def protect(match) -> str:
        token = f"__LUMENA_HTML_TAG_{len(placeholders)}__"
        placeholders.append(match.group(0))
        return token

    # Сначала защищаем готовые tg-emoji целиком, чтобы не получить вложенные
    # теги при повторной обработке сообщения.
    safe = _TG_EMOJI_TAG_RE.sub(protect, text)
    safe = _HTML_TAG_RE.sub(protect, safe)

    fallback_id = _pack_ids[0] if _pack_ids else None

    def replace_match(match) -> str:
        emoji = match.group(0)
        custom_id = _emoji_map.get(emoji)
        if custom_id is None:
            # Убираем только variation selector при поиске альтернативной
            # записи — Telegram sticker metadata иногда нормализует его.
            normalized = emoji.replace("\ufe0f", "")
            custom_id = _emoji_map.get(normalized)
        custom_id = custom_id or fallback_id
        return _custom_emoji_tag(emoji, custom_id) if custom_id else emoji

    safe = _EMOJI_SEQUENCE_RE.sub(replace_match, safe)
    for index, original in enumerate(placeholders):
        safe = safe.replace(f"__LUMENA_HTML_TAG_{index}__", original)
    return safe


def first_emoji_id(text: str | None) -> str | None:
    """Находит custom ID первого emoji в подписи кнопки."""
    if not text or not has_pack():
        return None
    matches = []
    for emoji, custom_id in _emoji_map.items():
        position = text.find(emoji)
        if position >= 0:
            matches.append((position, -len(emoji), custom_id))
    if matches:
        return min(matches)[2]
    return _pack_ids[0] if _pack_ids else None


def strip_mapped_emojis(text: str | None) -> str | None:
    """Убирает Unicode emoji из текста кнопки, если их заменит icon-поле."""
    if not text or not has_pack():
        return text
    result = _EMOJI_SEQUENCE_RE.sub("", text)
    return result.strip() or text


def decorate_message_html(text: str | None) -> str | None:
    """Заменяет все emoji в HTML-сообщении и добавляет accent при необходимости."""
    if not text or not has_pack():
        return text
    themed = replace_emojis_html(text)
    if "<tg-emoji" in (themed or "")[:500]:
        return themed
    return f'{e("header", _FALLBACK["header"])} {themed}'


# ── Стили Telegram-кнопок ─────────────────────────────────────
# Bot API поддерживает три официальных цвета: primary (синий),
# success (зелёный) и danger (красный). Произвольные HEX-цвета
# Telegram-клиент для bot-кнопок пока не принимает.
_DANGER_BUTTON_WORDS = (
    "cancel", "отмена", "reset", "сброс", "delete", "удал", "remove",
    "reject", "отказ", "deny", "no", "нет", "close", "закры", "divorce",
    "развод", "ban", "мут", "danger",
)
_SUCCESS_BUTTON_WORDS = (
    "confirm", "подтверд", "accept", "прин", "approve", "одобр", "verify",
    "вериф", "start", "начать", "claim", "забрать", "buy", "купить",
    "deposit", "вклад", "bid", "ставк", "save", "сохран", "yes", "да",
)


def button_style(text: str = "", callback_data: str | None = None,
                 url: str | None = None) -> str:
    """Выбирает безопасный официальный цвет кнопки по её назначению."""
    haystack = " ".join(
        str(value or "").lower() for value in (text, callback_data, url)
    )
    if any(word in haystack for word in _DANGER_BUTTON_WORDS):
        return "danger"
    if any(word in haystack for word in _SUCCESS_BUTTON_WORDS):
        return "success"
    return "primary"


def button_icon_id(text: str = "", callback_data: str | None = None,
                   url: str | None = None) -> str | None:
    """Возвращает custom emoji для иконки кнопки из выбранного пака."""
    if not has_pack():
        return None
    mapped_id = first_emoji_id(text)
    if mapped_id:
        return mapped_id
    style = button_style(text, callback_data, url)
    role = {
        "danger": "cross",
        "success": "ok",
        "primary": "accent",
    }[style]
    return get_role_id(role) or (_pack_ids[0] if _pack_ids else None)


def decorate_reply_markup(markup):
    """Добавляет стили и custom emoji-иконки ко всем типам клавиатур.

    Возвращает копию aiogram-модели, поэтому общие клавиатуры в обработчиках
    не мутируются и могут безопасно переиспользоваться.
    """
    if markup is None or not hasattr(markup, "model_copy"):
        return markup
    rows = getattr(markup, "inline_keyboard", None)
    field_name = "inline_keyboard"
    if rows is None:
        rows = getattr(markup, "keyboard", None)
        field_name = "keyboard"
    if rows is None:
        return markup

    decorated_rows = []
    for row in rows:
        decorated_row = []
        for button in row:
            if not hasattr(button, "model_copy"):
                decorated_row.append(button)
                continue
            text = getattr(button, "text", "") or ""
            callback_data = getattr(button, "callback_data", None)
            url = getattr(button, "url", None)
            updates = {}
            cleaned_text = strip_mapped_emojis(text)
            if cleaned_text and cleaned_text != text:
                updates["text"] = cleaned_text
            if getattr(button, "style", None) is None:
                updates["style"] = button_style(text, callback_data, url)
            icon_id = button_icon_id(text, callback_data, url)
            if icon_id and getattr(button, "icon_custom_emoji_id", None) is None:
                updates["icon_custom_emoji_id"] = icon_id
            decorated_row.append(
                button.model_copy(update=updates) if updates else button
            )
        decorated_rows.append(decorated_row)
    return markup.model_copy(update={field_name: decorated_rows})


# ── Кастомные тексты от фаундера ─────────────────────────
_custom_texts: dict[str, dict] = {}

# ─────────────────────────────────────────────────────────
# DEFAULT_TEXTS — дефолтные строки для всех ответов бота.
# Используются как fallback когда кастом не задан.
# Ключ совпадает с ключом в TEXT_LABELS.
# Поддерживают {format} переменные (подставляются через get_text()).
# ─────────────────────────────────────────────────────────
DEFAULT_TEXTS: dict[str, str] = {
    # ── Главный экран ──────────────────────────────────────
    "start_text":          "🖤 Добро пожаловать, <b>{name}</b>!\n\nВыбери раздел — расскажу всё о командах и возможностях 👇\n\n<i>Команды работают без / — просто напиши нужное слово в чат</i>",
    "start_unverified":    "👋 Привет, <b>{name}</b>!\n\nЧтобы получить доступ ко всем функциям, сначала пройди верификацию 👇",

    # ── Верификация ────────────────────────────────────────
    "verify_prompt":       "🔐 <b>Верификация</b>\n\nПодтверди, что ты не бот — нажми кнопку ниже.",
    "verify_done":         "✅ <b>Верификация пройдена!</b>\n\nДобро пожаловать, <b>{name}</b>! Все функции бота теперь доступны.",

    # ── Приветствие в группе ───────────────────────────────
    "welcome_msg":         "👋 Добро пожаловать в чат, <b>{name}</b>!\n\nНапиши /start в личке боту чтобы узнать всё о командах.",

    # ── Анкета — флоу ─────────────────────────────────────
    "anketa_start":        "📋 <b>Анкета знакомств</b>\n\nВыберите язык:",
    "anketa_cancel":       "❌ <b>Заполнение анкеты отменено.</b>\n\nНачать снова: /анкета",
    "anketa_confirm":      "✅ <b>Анкета отправлена на модерацию!</b>\n\nАдминистраторы рассмотрят её и уведомят тебя.",
    "anketa_duplicate":    "📋 Ты уже заполняешь анкету!\n\nНапиши /отмена чтобы отменить.",
    "anketa_cancel_none":  "У тебя нет активной анкеты.",
    "anketa_private_only": "📋 Анкету можно заполнять только в личке с ботом.",
    "anketa_no_verify":    "🔐 Сначала пройди верификацию — напиши /start боту в личку.",
    "step_accepted":       "✅ <b>Ответ принят!</b> Следующий вопрос 👇",
    "anketa_no_mod":       "✅ Анкета заполнена!\n\n⚠️ Чат модерации ещё не настроен — обратись к администратору.",
    "anketa_media_prompt": "📸 <b>Последний шаг — фото или видео!</b>\n\nОтправь до 10 медиафайлов. После загрузки анкета уйдёт на модерацию.\nМожно пропустить командой /пропустить",
    "anketa_media_added":  "📎 Медиафайл добавлен ({count}/10). Отправь ещё или напиши /готово",
    "anketa_media_done":   "✅ Медиа сохранено! Анкета отправлена на модерацию.",

    # ── Модерация анкет ────────────────────────────────────
    "anketa_approve":      "✅ <b>Твоя анкета одобрена!</b>\n\nДобро пожаловать в сообщество 💙",
    "anketa_reject":       "❌ <b>Твоя анкета отклонена.</b>\n\nПодать заново: /анкета",
    "anketa_delete":       "🗑 Анкета удалена.",
    "mod_comment":         "✏️ <b>Правки от модератора:</b>\n\n{comment}\n\n<i>Исправь и отправь снова: /анкета</i>",
    "revoke_notify":       "🔄 <b>Твоя анкета была отозвана.</b>\n\nПодать заново: /анкета",

    # ── VIP & Поддержка ────────────────────────────────────
    "vip_activated":       "👑 <b>VIP активирован!</b>\n\nТебе открыты премиум-функции сообщества.",
    "support_prompt":      "💬 <b>Поддержка</b>\n\nОпиши свою проблему — администрация ответит в ближайшее время.",
    "support_sent":        "✅ <b>Обращение отправлено!</b>\n\nАдминистрация рассмотрит его в ближайшее время 🙏",

    # ── Экономика ─────────────────────────────────────────
    "balance":             "💰 Кошелёк · <b>{name}</b>\n\n{icon} Баланс: <b>{balance} LMN</b>\n🏷 Статус: <b>{tier}</b>",
    "work":                "💼 Рабочая смена\n\n👷 Должность: <b>{job}</b>\n💵 Зарплата: <b>+{earned} LMN</b>\n\n💰 Баланс: <b>{balance} LMN</b>\n⏳ Следующая смена: <b>через 1 ч</b>",
    "work_cooldown":       "⏳ Следующая работа через <b>{mins} мин</b>",
    "fish":                "🎣 Рыбалка\n\n🐟 Улов: <b>{item}</b>\n💵 Выручка: <b>{result}</b>\n\n💰 Баланс: <b>{balance} LMN</b>\n⏳ Следующая рыбалка: <b>через 30 мин</b>",
    "fish_cooldown":       "⏳ Рыбалка через <b>{mins} мин</b>",
    "give":                "💸 Перевод выполнен!\n\n📤 От: <b>{from_name}</b>\n📥 Кому: <b>{to_name}</b>\n💰 Сумма: <b>{amount} LMN</b>\n\n💵 Остаток: <b>{balance} LMN</b>",
    "give_no_reply":       "ℹ️ Ответь на сообщение получателя и укажи сумму.\nПример: <i>дать 1000</i>",
    "give_no_funds":       "❌ Недостаточно LMN\nУ тебя: <b>{have}</b>, нужно: <b>{need}</b>",
    "casino_win":          "🎰 Казино\n\n🟢 ВЫИГРЫШ  <b>+{amount} LMN</b>\n\n💰 Баланс: <b>{balance} LMN</b>",
    "casino_jackpot":      "🎰 Казино\n\n💎 ДЖЕКПОТ  <b>+{amount} LMN</b>\n\n🎊 Невероятно! Тройной выигрыш!\n💰 Баланс: <b>{balance} LMN</b>",
    "casino_lose":         "🎰 Казино\n\n🔴 ПРОИГРЫШ  <b>-{amount} LMN</b>\n\n😞 Попробуй ещё раз!\n💰 Баланс: <b>{balance} LMN</b>",
    "rob_success":         "🦹 Ограбление удалось!\n\n💰 Украдено: <b>{stolen} LMN</b> у {victim}\n💵 Твой баланс: <b>{balance} LMN</b>",
    "rob_fail":            "👮 Ограбление провалилось!\n\nТебя поймали и оштрафовали на <b>{fine} LMN</b>\n💵 Баланс: <b>{balance} LMN</b>",
    "rob_cooldown":        "⏳ Следующее ограбление через <b>{mins} мин</b>",
    "coin_rain":           "🌧 <b>ДОЖДЬ ИЗ МОНЕТ!</b>\n\n💰 В чате упали монеты LMN!\n\nНапиши <b>подобрать</b> — первым забирает!\n\n🎁 Приз: <b>{amount} LMN</b>",
    "coin_rain_collected": "🎉 <b>{name}</b> подобрал монеты!\n\n💰 <b>+{amount} LMN</b> зачислено на баланс",

    # ── Брак ──────────────────────────────────────────────
    "marry_proposal":      "💍 <b>{from_name}</b> делает предложение <b>{to_name}</b>!\n\n{to_name}, принимаешь? 💕",
    "marry_accept":        "🎉 <b>Совет да любовь!</b>\n\n💍 <b>{name1}</b> и <b>{name2}</b> теперь в браке!",
    "marry_reject":        "💔 <b>{name}</b> отказал(а) в предложении.",
    "marry_self":          "Нельзя жениться на себе 😄",
    "marry_already":       "❌ Ты уже в браке! Сначала разведись: /развод",
    "marry_already_other": "❌ {name} уже в браке.",
    "marry_no_reply":      "💍 Ответь на сообщение человека, которому хочешь сделать предложение.",
    "divorce":             "💔 <b>{name1}</b> и <b>{name2}</b> развелись.",
    "divorce_not_married": "Вы не состоите в браке.",

    # ── Стрики ────────────────────────────────────────────
    "checkin":             "🔥 Чекин выполнен!\n\n👤 {name}\n📅 Дней подряд: <b>{count}</b>\n◆ {fire}",
    "checkin_already":     "🔥 Ты уже отмечался сегодня!",

    # ── Репутация и аура ──────────────────────────────────
    "upvote":              "⬆️ +1 репутация\n\n👤 <b>{name}</b>\n📊 Итого: <b>{total:+d}</b>",
    "downvote":            "⬇️ -1 репутация\n\n👤 <b>{name}</b>\n📊 Итого: <b>{total:+d}</b>",
    "rep":                 "{icon} Репутация\n\n👤 <b>{name}</b>\n📊 Рейтинг: <b>{rep:+d}</b>",
    "aura_show":           "✨ Аура\n\n👤 <b>{name}</b>\n<code>{bar}</code>\n📊 <b>{pct:.2f}%</b>  —  {tier}\n\n<i>+0.01% за каждый 👍 на твои сообщения\n−1% за агрессию в чате</i>",

    # ── Игры ─────────────────────────────────────────────
    "rps_win":             "Ты: {you} | Я: {me}\n✊✌️✋ <b>Ты победил! 🎉</b>\n💰 +{award} LMN",
    "rps_lose":            "Ты: {you} | Я: {me}\n✊✌️✋ <b>Я победил! 😈</b>\n💸 -{fine} LMN",
    "rps_tie":             "Ты: {you} | Я: {me}\n✊✌️✋ <b>Ничья! 🤝</b>",
    "roulette_join":       "🎯 <b>{name}</b> присоединился к рулетке!\nИгроков: <b>{count}</b>\nНапиши <b>рулетка_старт</b> чтобы начать (минимум 2)",
    "roulette_winner":     "🎯 <b>Победитель рулетки — {name}!</b> 🎉",
    "coin":                "🪙 Монетка: <b>{result}</b>",
    "hangman_start":       "🎮 <b>Виселица!</b>\n\nСлово: <code>{mask}</code>\nПопытки: {tries}\n\nНапиши букву для угадывания.",
    "hangman_win":         "🎉 <b>Победа!</b> Слово: <b>{word}</b>",
    "hangman_lose":        "😵 <b>Проигрыш.</b> Слово было: <b>{word}</b>",

    # ── Социальные действия ───────────────────────────────
    "hug":                 "🤗 <b>{from_name}</b> обнял(а) <b>{to_name}</b>! Тепло 💕",
    "kiss":                "😘 <b>{from_name}</b> поцеловал(а) <b>{to_name}</b>! 💋",
    "playful_kill":        "🎭 <b>{from_name}</b> понарошку «убил(а)» <b>{to_name}</b> в театральной сценке! Всё игра 🎬",
    "playful_shoot":       "🔫 <b>{from_name}</b> шуточно «застрелил(а)» <b>{to_name}</b> из водяного пистолета! 💦",
    "playful_stab":        "🔪 <b>{from_name}</b> понарошку «зарезал(а)» <b>{to_name}</b> бутафорским ножом! 🎭",
    "deep_kiss":           "💋 <b>{from_name}</b> поцеловал(а) <b>{to_name}</b> взасос! Только понарошку 😘",
    "confess_love":        "💌 <b>{from_name}</b> признался(ась) в любви к <b>{to_name}</b>! 💖",
    "gift":                "🎁 <b>{from_name}</b> подарил(а) <b>{to_name}</b> подарок! 🎀",
    "slap":                "💢 <b>{from_name}</b> дал(а) пощёчину <b>{to_name}</b>!",
    "pat":                 "✋ <b>{from_name}</b> погладил(а) <b>{to_name}</b>! 🥰",
    "dance":               "💃 <b>{from_name}</b> танцует с <b>{to_name}</b>! 🎶",
    "bite":                "😈 <b>{from_name}</b> укусил(а) <b>{to_name}</b>!",
    "poke":                "👉 <b>{from_name}</b> потыкал(а) <b>{to_name}</b>!",
    "wave":                "👋 <b>{from_name}</b> помахал(а) <b>{to_name}</b>!",
    "highfive":            "🙌 <b>{from_name}</b> дал(а) пять <b>{to_name}</b>!",
    "facepalm":            "🤦 <b>{from_name}</b> делает фейспалм из-за <b>{to_name}</b>!",
    "serenade":            "🎵 <b>{from_name}</b> поёт серенаду для <b>{to_name}</b>! 🌹",

    # ── Профиль ───────────────────────────────────────────
    "profile_no_bio":      "не указано",
    "profile_no_partner":  "—",
    "info_project": (
        "ℹ️ <b>О проекте</b>\n\n"
        "🌟 <b>Lumena</b> — официальный Telegram-бот сообщества\n\n"
        "👑 <b>Основатель:</b> HYDRÆ\n\n"
        "👨‍💻 <b>Разработчики:</b> HYDRÆ · Дмитрий · Евгений\n\n"
        "🛡 <b>Администрация:</b> Диана · Вероника · Владислав · Егор · Алла\n\n"
        "<i>Отредактируй этот текст через /edit → ℹ️ Инфо</i>"
    ),
    "info_founder_badge":  "✨ Создатель проекта Lumena",

    # ── Модерация ─────────────────────────────────────────
    "mute_done":           "🔇 <b>{name}</b> замучен на {duration}.\n📝 Причина: {reason}",
    "ban_done":            "🚫 <b>{name}</b> забанен.\n📝 Причина: {reason}",
    "unban_done":          "✅ <b>{name}</b> разбанен.",
    "unmute_done":         "🔊 <b>{name}</b> размучен.",
    "kick_done":           "👢 <b>{name}</b> кикнут.",
    "warn_done":           "⚠️ <b>{name}</b> получил варн {count}/3.\n📝 Причина: {reason}",
    "warn_ban":            "🚫 <b>{name}</b> — 3 варна. Автобан!",
    "unwarn_done":         "✅ Варн снят с <b>{name}</b>. Осталось: {count}/3",
    "admin_only":          "⛔ Только администраторы",
    "reply_needed":        "↩️ Ответь на сообщение",
    "owner_only":          "⛔ Только @hdrttttttt",

    # ── Предсказания ─────────────────────────────────────
    "fortune_result":      "🔮 <b>Предсказание</b>\n\n{result}",
    "horoscope_result":    "♈ <b>Гороскоп для {sign}</b>\n\n{text}",
    "tarot_result":        "🃏 Твоя карта: <b>{card}</b>\n{meaning}",

    # ── Монетка ───────────────────────────────────────────
    "coin_heads":          "🪙 Орёл 🦅",
    "coin_tails":          "🪙 Решка 🌟",

    # ── Профиль ───────────────────────────────────────────
    "profile_header":      "👤 Профиль · <b>{name}</b>",
    "profile_bio_label":   "📝 Bio:",
    "profile_balance_label": "💰 Баланс:",
    "profile_streak_label":  "🔥 Стрик:",
    "profile_rep_label":     "⭐ Репутация:",
    "profile_marry_label":   "💍 Брак:",
    "profile_id_label":      "🆔 ID:",

    # ── Рейтинги ──────────────────────────────────────────
    "richest_header":      "💰 Топ богачей чата",
    "richest_empty":       "💸 Пока у всех пустые кошельки 😅",
    "richest_total":       "💵 В обороте: <b>{total} {cur}</b>",
    "top_rep_header":      "⭐ Топ репутации",
    "top_checkin_header":  "🔥 Топ по чекинам",

    # ── Казино — ошибки ───────────────────────────────────
    "casino_no_bet":       "🎰 Укажи ставку: <code>казино [сумма]</code>",
    "casino_no_balance":   "❌ Недостаточно {cur} для ставки",
    "casino_invalid_bet":  "❌ Ставка должна быть числом",
    "casino_negative_bet": "❌ Ставка должна быть положительной",

    # ── Слоты — ошибки ────────────────────────────────────
    "slots_no_bet":        "🎲 Укажи ставку: <code>слоты [сумма]</code>",
    "slots_no_balance":    "❌ Недостаточно {cur} для ставки",
    "slots_invalid_bet":   "❌ Ставка должна быть числом",

    # ── Ограбление ────────────────────────────────────────
    "rob_no_reply":        "🦹 Ответь на сообщение жертвы!",
    "rob_self":            "❌ Нельзя грабить самого себя",
    "rob_bot":             "❌ Нельзя грабить бота",
    "rob_target_poor":     "💸 У жертвы нет денег 😅",
    "rob_victim_notify":   "🚨 Тебя ограбили! <b>{thief}</b> украл <b>{stolen} {cur}</b>",

    # ── Перевод ───────────────────────────────────────────
    "give_self":           "❌ Нельзя переводить самому себе",
    "give_zero":           "❌ Сумма должна быть больше нуля",
    "give_bot":            "❌ Нельзя переводить боту",

    # ── Рулетка ───────────────────────────────────────────
    "roulette_already":    "🎯 Ты уже в рулетке! Используй: рулетка_старт",
    "roulette_join_msg":   "🎯 <b>{name}</b> присоединился к рулетке!\nИгроков: <b>{count}</b>\nНапиши <b>рулетка_старт</b> чтобы начать (минимум 2)",
    "roulette_not_enough": "🎯 Нужно минимум 2 игрока для старта!",
    "roulette_result":     "🔫 Барабан крутится...\n💀 Проигравший: <b>{name}</b>!",

    # ── Виселица ──────────────────────────────────────────
    "hangman_no_game":     "🎮 Нет активной игры. Начни: виселица",
    "hangman_letter_used": "🔄 «<b>{letter}</b>» уже было! Попробуй другую букву.",
    "hangman_wrong":       "❌ «<b>{letter}</b>» нет в слове. Попыток осталось: <b>{tries}</b>\n<code>{mask}</code>",
    "hangman_right":       "✅ «<b>{letter}</b>» есть! <code>{mask}</code>",

    # ── Модерация — самодействия ──────────────────────────
    "mute_self":           "❌ Нельзя замутить самого себя",
    "ban_self":            "❌ Нельзя забанить самого себя",
    "kick_self":           "❌ Нельзя кикнуть самого себя",

    # ── Брак — таймаут ────────────────────────────────────
    "marry_timeout":       "⏳ <b>{name}</b> не ответил(а) на предложение. Запрос отменён.",

    # ── Варны ─────────────────────────────────────────────
    "unwarn_no_warns":     "У <b>{name}</b> нет активных варнов.",

    # ── Чекин — майлстоун ─────────────────────────────────
    "checkin_milestone":   "🎉 <b>{name}</b> — {count} дней подряд! Бонус: <b>+{bonus} {cur}</b>",
}

TEXT_LABELS: dict[str, str] = {
    # ── Главный экран ──────────────────────────────────────
    "start_text":          "Главный экран /start (верифицирован)",
    "start_unverified":    "Первый /start — нужна верификация",

    # ── Верификация ────────────────────────────────────────
    "verify_btn":          "Кнопка «Пройти верификацию»",
    "verify_prompt":       "Экран верификации (текст)",
    "verify_confirm_btn":  "Кнопка «Я не бот — подтвердить»",
    "verify_done":         "Верификация пройдена ({name})",

    # ── Приветствие в группе ───────────────────────────────
    "welcome_msg":         "Приветствие нового участника ({name})",
    "welcome_btn":         "Кнопка в приветствии",

    # ── Анкета — флоу ─────────────────────────────────────
    "anketa_start":        "Старт анкеты (выбор языка)",
    "anketa_cancel":       "Анкета отменена",
    "anketa_confirm":      "Анкета отправлена на модерацию",
    "anketa_duplicate":    "Уже заполняешь анкету (повторный старт)",
    "anketa_cancel_none":  "Нет активной анкеты для отмены",
    "anketa_private_only": "Анкета только в ЛС (ответ в группе)",
    "anketa_no_verify":    "Анкета без верификации",
    "step_accepted":       "Ответ принят (каждый шаг анкеты)",
    "anketa_no_mod":       "Анкета заполнена, но чат модерации не настроен",
    "anketa_media_prompt": "Промпт загрузки фото/видео (последний шаг)",
    "anketa_media_added":  "Медиафайл добавлен (счётчик)",
    "anketa_media_done":   "Медиа сохранено, анкета отправлена",

    # ── Модерация анкет ────────────────────────────────────
    "anketa_approve":      "Анкета одобрена ✅ (юзеру)",
    "anketa_reject":       "Анкета отклонена ❌ (юзеру)",
    "anketa_delete":       "Анкета удалена (юзеру)",
    "mod_comment":         "Правки от модератора (юзеру) [{comment}]",
    "revoke_notify":       "Анкета отозвана (юзеру)",

    # ── VIP & Поддержка ────────────────────────────────────
    "vip_activated":       "VIP активирован 👑",
    "support_prompt":      "Начало диалога поддержки",
    "support_sent":        "Обращение отправлено",

    # ── Экономика ──────────────────────────────────────────
    "balance":             "Баланс ({name}, {balance})",
    "work":                "Рабочая смена ({job}, {earned})",
    "work_cooldown":       "Работа: кулдаун ({mins} мин)",
    "fish":                "Рыбалка ({item}, {result})",
    "fish_cooldown":       "Рыбалка: кулдаун ({mins} мин)",
    "give":                "Перевод LMN ({from} → {to}, {amount})",
    "give_no_reply":       "Перевод: нужно ответить на сообщение",
    "give_no_funds":       "Перевод: недостаточно LMN",
    "casino_win":          "Казино: выигрыш",
    "casino_jackpot":      "Казино: джекпот 💎",
    "casino_lose":         "Казино: проигрыш",
    "rob_success":         "Ограбление: успешно ({stolen} LMN)",
    "rob_fail":            "Ограбление: провалилось",
    "rob_cooldown":        "Ограбление: кулдаун",
    "coin_rain":           "Дождь монет: объявление ({amount})",
    "coin_rain_collected": "Дождь монет: монеты подобраны",

    # ── Брак ───────────────────────────────────────────────
    "marry_proposal":      "Предложение руки и сердца 💍",
    "marry_accept":        "Брак принят — Совет да любовь! 💕",
    "marry_reject":        "Отказ от предложения 💔",
    "marry_self":          "Нельзя жениться на себе",
    "marry_already":       "Уже в браке — нужно развестись",
    "marry_already_other": "Цель уже в браке",
    "marry_no_reply":      "Брак: нужно ответить на сообщение",
    "divorce":             "Развод оформлен 💔",
    "divorce_not_married": "Не в браке",

    # ── Стрики ────────────────────────────────────────────
    "checkin":             "Чекин выполнен 🔥 ({count} дней)",
    "checkin_already":     "Уже отмечался сегодня",

    # ── Репутация и аура ──────────────────────────────────
    "upvote":              "Плюс репутации (+1)",
    "downvote":            "Минус репутации (-1)",
    "rep":                 "Репутация пользователя",
    "aura_show":           "Аура пользователя (0–100%)",

    # ── Игры ───────────────────────────────────────────────
    "rps_win":             "КНБ: победа 🎉",
    "rps_lose":            "КНБ: проигрыш 😈",
    "rps_tie":             "КНБ: ничья 🤝",
    "roulette_join":       "Рулетка: игрок вошёл",
    "roulette_winner":     "Рулетка: победитель",
    "coin":                "Монетка (орёл/решка)",
    "hangman_start":       "Виселица: начало игры",
    "hangman_win":         "Виселица: победа",
    "hangman_lose":        "Виселица: проигрыш",

    # ── Социальные ─────────────────────────────────────────
    "hug":                 "🤗 {from_name} обнял(а) {to_name}!",
    "kiss":                "😘 {from_name} поцеловал(а) {to_name}!",
    "playful_kill":        "🎭 {from_name} понарошку «убил(а)» {to_name} в театральной сценке! Всё игра 🎬",
    "playful_shoot":       "🔫 {from_name} шуточно «застрелил(а)» {to_name} из водяного пистолета! 💦",
    "playful_stab":        "🔪 {from_name} понарошку «зарезал(а)» {to_name} бутафорским ножом! 🎭",
    "deep_kiss":           "💋 {from_name} поцеловал(а) {to_name} взасос! Только понарошку 😘",
    "confess_love":        "💌 {from_name} признался(ась) в любви к {to_name}! 💖",
    "gift":                "🎁 {from_name} подарил(а) {item} для {to_name}!",
    "slap":                "👋 {from_name} дал(а) пощёчину {to_name}!",
    "pat":                 "🤚 {from_name} погладил(а) {to_name}!",
    "dance":               "💃 {from_name} танцует с {to_name}! 🎵",
    "bite":                "😬 {from_name} укусил(а) {to_name}!",
    "poke":                "👉 {from_name} ткнул(а) {to_name}!",
    "wave":                "👋 {from_name} помахал(а) рукой {to_name}!",
    "highfive":            "🙌 {from_name} дал(а) пять {to_name}!",
    "facepalm":            "🤦 {from_name} сделал(а) фейспалм из-за {to_name}",
    "serenade":            "🎵 {from_name} поёт серенаду для {to_name}! ♪",

    # ── Профиль ────────────────────────────────────────────
    "profile_no_bio":      "Профиль: нет bio (заглушка)",
    "profile_no_partner":  "Профиль: нет партнёра (заглушка)",
    "info_founder_badge":  "Бейдж создателя в /info",

    # ── Модерация ──────────────────────────────────────────
    "mute_done":           "Мут выдан ({name}, {duration})",
    "ban_done":            "Бан выдан ({name})",
    "unban_done":          "Разбанен ({name})",
    "unmute_done":         "Размучен ({name})",
    "kick_done":           "Кикнут ({name})",
    "warn_done":           "Варн выдан ({name}, {count}/3)",
    "warn_ban":            "3 варна — автобан",
    "unwarn_done":         "Варн снят",
    "admin_only":          "Отказ: только для администраторов",
    "reply_needed":        "Отказ: нужен ответ на сообщение",
    "owner_only":          "Отказ: только для фаундера",

    # ── Предсказания и развлечения ────────────────────────
    "fortune_result":      "Предсказание 🔮",
    "horoscope_result":    "Гороскоп ♈",
    "tarot_result":        "Таро 🃏",
    "fortune_destiny":     "Судьба — результат",
    "fortune_superpower":  "Суперсила — результат",
    "fortune_profession":  "Профессия — результат",
    "fortune_animal":      "Животное дня",
    "fortune_movie":       "Рекомендация фильма",
    "fortune_book":        "Рекомендация книги",
    "fortune_advice":      "Совет дня",
    "fortune_motivation":  "Мотивация",
    "fortune_myth":        "Факт vs Миф",
    "fortune_country":     "Страна дня",
    "fortune_color":       "Цвет настроения",
    "fortune_joke":        "Шутка дня",
    "fortune_compliment":  "Комплимент ({target})",
    "fortune_roast":       "Роаст ({target})",
    "fortune_8ball":       "Магический шар — ответ",
    "fortune_predict":     "Предсказание на запрос",

    # ── Новые игры ─────────────────────────────────────────
    "game_dice":           "Кубик — результат",
    "game_roll":           "Ролл — результат",
    "game_choose":         "Выбор варианта — результат",
    "game_rate":           "Оценка — результат",
    "game_truth":          "Правда или действие — вопрос",
    "game_dare":           "Правда или действие — задание",
    "game_riddle":         "Загадка",
    "game_random":         "Случайное число",

    # ── Магазин / Инвентарь ────────────────────────────────
    "shop_header":         "Магазин — заголовок",
    "shop_coming_soon":    "Магазин — скоро открытие",
    "inventory_header":    "Инвентарь — заголовок",
    "inventory_empty":     "Инвентарь — пуст",

    # ── Банк ──────────────────────────────────────────────
    "bank_header":            "Банк — заголовок карточки",
    "bank_deposit_done":      "Депозит успешен ({amount} LMN)",
    "bank_deposit_no_funds":  "Депозит: недостаточно средств в кошельке",
    "bank_deposit_zero":      "Укажи сумму для депозита",
    "bank_withdraw_done":     "Снятие успешно ({amount} LMN)",
    "bank_withdraw_no_funds": "Снятие: в банке недостаточно средств",
    "bank_withdraw_zero":     "Укажи сумму для снятия",
    "bank_withdraw_cooldown": "Снятие заблокировано ещё на {mins} мин",
    "rob_banked":             "Жертва сохранила монеты в банке — кошелёк защищён",

    # ── Монетка ────────────────────────────────────────────
    "coin_heads":          "Монетка: выпал Орёл 🦅",
    "coin_tails":          "Монетка: выпала Решка 🌟",

    # ── Профиль ────────────────────────────────────────────
    "profile_header":      "Заголовок профиля ({name})",
    "profile_bio_label":   "Профиль: метка Bio",
    "profile_balance_label": "Профиль: метка Баланс",
    "profile_streak_label":  "Профиль: метка Стрик",
    "profile_rep_label":     "Профиль: метка Репутация",
    "profile_marry_label":   "Профиль: метка Брак",
    "profile_id_label":      "Профиль: метка ID",

    # ── Рейтинги ───────────────────────────────────────────
    "richest_header":      "Богатейшие — заголовок",
    "richest_empty":       "Богатейшие — пустой список",
    "richest_total":       "Богатейшие — итого в обороте",
    "top_rep_header":      "Топ репутации — заголовок",
    "top_checkin_header":  "Топ чекинов — заголовок",

    # ── Казино — ошибки ────────────────────────────────────
    "casino_no_bet":       "Казино: не указана ставка",
    "casino_no_balance":   "Казино: недостаточно монет",
    "casino_invalid_bet":  "Казино: ставка не число",
    "casino_negative_bet": "Казино: ставка ≤ 0",

    # ── Слоты — ошибки ─────────────────────────────────────
    "slots_no_bet":        "Слоты: не указана ставка",
    "slots_no_balance":    "Слоты: недостаточно монет",
    "slots_invalid_bet":   "Слоты: ставка не число",

    # ── Ограбление ─────────────────────────────────────────
    "rob_no_reply":        "Ограбление: нет reply",
    "rob_self":            "Ограбление: цель — себя",
    "rob_bot":             "Ограбление: цель — бот",
    "rob_target_poor":     "Ограбление: у жертвы нет денег",
    "rob_victim_notify":   "Ограбление: уведомление жертве",

    # ── Перевод ────────────────────────────────────────────
    "give_self":           "Перевод: попытка перевести себе",
    "give_zero":           "Перевод: сумма ≤ 0",
    "give_bot":            "Перевод: попытка перевести боту",

    # ── Рулетка ────────────────────────────────────────────
    "roulette_already":    "Рулетка: уже участвует",
    "roulette_join_msg":   "Рулетка: игрок вошёл (расширенный)",
    "roulette_not_enough": "Рулетка: мало игроков для старта",
    "roulette_result":     "Рулетка: результат (проигравший)",

    # ── Виселица ───────────────────────────────────────────
    "hangman_no_game":     "Виселица: нет активной игры",
    "hangman_letter_used": "Виселица: буква уже угадана",
    "hangman_wrong":       "Виселица: неверная буква",
    "hangman_right":       "Виселица: верная буква",

    # ── Модерация — самодействия ───────────────────────────
    "mute_self":           "Мут: попытка замутить себя",
    "ban_self":            "Бан: попытка забанить себя",
    "kick_self":           "Кик: попытка кикнуть себя",

    # ── Брак ───────────────────────────────────────────────
    "marry_timeout":       "Брак: таймаут ответа ({name})",

    # ── Варны ──────────────────────────────────────────────
    "unwarn_no_warns":     "Снять варн: варнов нет",

    # ── Чекин — бонус ──────────────────────────────────────
    "checkin_milestone":   "Чекин: бонус за N дней ({count})",
}


def get_text(key: str, fallback: str = "", **fmt) -> str:
    """Возвращает кастомный или дефолтный текст для ключа.
    Поддерживает format-переменные: get_text('work', job='Повар', earned='500').
    """
    ct = get_custom_text(key)
    if ct:
        text = ct[0]
    else:
        text = DEFAULT_TEXTS.get(key, fallback)
    if fmt and text:
        try:
            text = text.format(**fmt)
        except (KeyError, ValueError):
            pass
    return text


def get_current_text(key: str) -> str:
    """Возвращает текущий текст для ключа (кастомный или дефолтный), без форматирования.
    Используется редактором для отображения текущего значения.
    """
    ct = get_custom_text(key)
    if ct:
        return ct[0]
    return DEFAULT_TEXTS.get(key, "")


def substitute_name(text: str, entities: list[dict], name: str) -> tuple[str, list[dict]]:
    """Заменяет {name} в тексте и сдвигает офсеты entities соответственно."""
    placeholder = "{name}"
    if placeholder not in text:
        return text, entities
    pos = text.index(placeholder)
    offset_diff = len(name) - len(placeholder)
    new_text = text[:pos] + name + text[pos + len(placeholder):]
    new_ents = []
    for e in entities:
        ec = dict(e)
        if ec["offset"] >= pos + len(placeholder):
            ec["offset"] += offset_diff
        elif ec["offset"] > pos:
            ec["length"] = max(1, ec["length"] + offset_diff)
        new_ents.append(ec)
    return new_text, new_ents


def set_custom_text(key: str, text: str, entities: list[dict]) -> None:
    _custom_texts[key] = {"text": text, "entities": entities}


def get_custom_text(key: str) -> tuple[str, list[dict]] | None:
    d = _custom_texts.get(key)
    return (d["text"], d.get("entities", [])) if d else None


def del_custom_text(key: str) -> None:
    _custom_texts.pop(key, None)


def all_custom_texts() -> dict:
    return dict(_custom_texts)


def save_custom_texts(path: str = "data/custom_texts.json") -> None:
    import json, os
    os.makedirs("data", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_custom_texts, f, ensure_ascii=False, indent=2)


def load_custom_texts(path: str = "data/custom_texts.json") -> None:
    import json
    try:
        with open(path, encoding="utf-8") as f:
            _custom_texts.update(json.load(f))
    except FileNotFoundError:
        pass
    except Exception as ex:
        print(f"⚠️ load_custom_texts: {ex}")


async def push_custom_texts_to_github(path: str = "data/custom_texts.json") -> bool:
    """Зберігає custom_texts в PostgreSQL (і локальний файл)."""
    save_custom_texts(path)
    try:
        import db as _db
        await _db.save_kv("custom_texts", _custom_texts)
        print("✅ custom_texts збережено в PostgreSQL")
        return True
    except Exception as ex:
        print(f"⚠️ push_custom_texts_to_github (DB): {ex}")
        return False


async def persist_brand_now() -> bool:
    """Зберігає всі налаштування бренду разом, включно з Premium Emoji entities."""
    save_custom_texts()
    save_custom_style()
    save_custom_buttons()
    try:
        import db as _db
        if not _db.has_pg():
            return False
        return await _db.db_set_many([
            ("custom_texts", _custom_texts),
            ("custom_style", _custom_style),
            ("custom_buttons", _custom_buttons),
        ])
    except Exception as ex:
        print(f"⚠️ persist_brand_now: {ex}")
        return False


# ═══════════════════════════════════════════════════════════
# ПЕРСИСТЕНТНОСТЬ bot_data.json → GitHub
# ═══════════════════════════════════════════════════════════

async def push_bot_data_to_github(
    payload_bytes: bytes,
    path: str = "data/bot_data.json",
) -> bool:
    """Залишено для сумісності — більше не використовується (замінено PostgreSQL)."""
    return True

async def restore_brand_from_db() -> None:
    """При старті завантажує custom_texts/style/buttons з PostgreSQL."""
    import db as _db
    mapping = [
        ("custom_texts",   _custom_texts,   "custom_texts"),
        ("custom_style",   _custom_style,   "custom_style"),
        ("custom_buttons", _custom_buttons, "custom_buttons"),
    ]
    for key, store, label in mapping:
        try:
            data = await _db.load_kv(key)
            if data is not None:  # {} — валідний (очищений стан)
                store.update(data)
                print(f"✅ {label} завантажено з PostgreSQL")
        except Exception as ex:
            print(f"⚠️ restore_brand_from_db({label}): {ex}")
async def restore_brand() -> None:
    """При старті відновлює custom_texts/style/buttons: PostgreSQL → GitHub → локальний файл."""
    import os
    try:
        import db as _db
    except ImportError:
        _db = None  # type: ignore

    targets = [
        ("data/custom_texts.json",   "custom_texts",   load_custom_texts),
        ("data/custom_style.json",   "custom_style",   load_custom_style),
        ("data/custom_buttons.json", "custom_buttons", load_custom_buttons),
    ]
    os.makedirs("data", exist_ok=True)

    for local, pg_key, loader in targets:
        # 1. PostgreSQL
        if _db and _db.has_pg():
            data = await _db.db_get(pg_key)
            if data is not None:  # {} — валідний (очищений стан)
                import json as _j
                with open(local, "w", encoding="utf-8") as f:
                    _j.dump(data, f, ensure_ascii=False)
                loader()
                print(f"✅ {pg_key} відновлено з PostgreSQL")
                continue
            print(f"⚠️ PostgreSQL: {pg_key} ще не записано")

        # 2. GitHub fallback
        if os.path.exists(local) and os.path.getsize(local) > 5:
            continue
        print(f"📥 {pg_key} не знайдено — спроба відновити з GitHub...")
        raw = await fetch_bot_data_from_github(local)
        if raw:
            with open(local, "wb") as f:
                f.write(raw)
            loader()
            print(f"✅ {pg_key} відновлено з GitHub")
        else:
            print(f"⚠️ GitHub не повернув {pg_key}")


# Аліас для зворотної сумісності
restore_brand_from_github = restore_brand


async def fetch_bot_data_from_github(path: str = "data/bot_data.json") -> bytes | None:
    """Завантажує файл з GitHub при старті (read-only fallback поки PostgreSQL порожній).
    Повертає raw bytes або None при помилці / відсутності GITHUB_TOKEN.
    """
    import base64
    try:
        import aiohttp
    except ImportError:
        return None

    token = os.getenv("GITHUB_TOKEN", "")
    repo  = os.getenv("GITHUB_REPO", "vrgquorumm/Lumena")

    git_path = f"bot/{path}"
    api_url  = f"https://api.github.com/repos/{repo}/contents/{git_path}"
    headers  = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    # Репозиторий публичный — работает и без токена; если GITHUB_TOKEN задан,
    # используем его (выше лимиты запросов).
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                b64 = data.get("content", "").replace("\n", "")
                return base64.b64decode(b64) if b64 else None
    except Exception as ex:
        print(f"⚠️ fetch_bot_data_from_github: {ex}")
        return None


# ── Кастомные кнопки ──────────────────────────────────────
_custom_buttons: dict[str, dict] = {}

# Все редактируемые кнопки бота: ключ → {label, url|None, desc}
BUTTON_DEFS: dict[str, dict] = {
    "main_chat":      {
        "label": "💬 Чат проекта",
        "url":   "https://t.me/+_K2SJRYIhq9hYjFi",
        "desc":  "Главное меню — кнопка «Чат»",
        "type":  "url",
    },
    "main_channel":   {
        "label": "📢 Канал",
        "url":   "https://t.me/lmnfff",
        "desc":  "Главное меню — кнопка «Канал»",
        "type":  "url",
    },
    "main_help":      {
        "label": "📖 Все команды",
        "url":   None,
        "desc":  "Главное меню — кнопка «Все команды»",
        "type":  "callback",
    },
    "verify_start":   {
        "label": "✨ Пройти верификацию",
        "url":   None,
        "desc":  "Кнопка старта верификации",
        "type":  "callback",
    },
    "verify_confirm": {
        "label": "✨ Я не бот — подтвердить",
        "url":   None,
        "desc":  "Кнопка подтверждения верификации",
        "type":  "callback",
    },
    "welcome_btn":    {
        "label": "✨ Добро пожаловать!",
        "url":   None,
        "desc":  "Кнопка в приветственном сообщении",
        "type":  "callback",
    },
    # ── Новые кнопки ────────────────────────────────────
    "support_link": {
        "label": "💎 Поддержка",
        "url":   "https://t.me/",
        "desc":  "Кнопка поддержки (ссылка)",
        "type":  "url",
    },
    "rules_link": {
        "label": "📜 Правила",
        "url":   "https://t.me/",
        "desc":  "Кнопка правил сообщества (ссылка)",
        "type":  "url",
    },
    "anketa_link": {
        "label": "💌 Анкеты",
        "url":   "https://t.me/",
        "desc":  "Кнопка анкет знакомств (ссылка)",
        "type":  "url",
    },
    "donate_link": {
        "label": "👑 Поддержать проект",
        "url":   "https://t.me/",
        "desc":  "Кнопка донатов / поддержки проекта",
        "type":  "url",
    },
    "news_link": {
        "label": "📰 Новости",
        "url":   "https://t.me/",
        "desc":  "Кнопка новостей / обновлений",
        "type":  "url",
    },
    "social_link": {
        "label": "🌐 Соцсети",
        "url":   "https://t.me/",
        "desc":  "Кнопка соцсетей проекта",
        "type":  "url",
    },
    "partner_link": {
        "label": "🤝 Партнёры",
        "url":   "https://t.me/",
        "desc":  "Кнопка партнёров",
        "type":  "url",
    },
    "store_link": {
        "label": "💎 Магазин",
        "url":   "https://t.me/",
        "desc":  "Кнопка магазина / мерча",
        "type":  "url",
    },
}


def btn_label(key: str) -> str:
    """Текущий label кнопки (кастомный или дефолтный)."""
    cb = _custom_buttons.get(key, {})
    return cb.get("label") or BUTTON_DEFS.get(key, {}).get("label", key)


def btn_url(key: str) -> str | None:
    """Текущий URL кнопки (кастомный или дефолтный). None для callback-кнопок."""
    cb = _custom_buttons.get(key, {})
    if "url" in cb:
        return cb["url"]
    return BUTTON_DEFS.get(key, {}).get("url")


def set_custom_button(key: str, label: str | None = None, url: str | None = None) -> None:
    existing = dict(_custom_buttons.get(key, {}))
    if label is not None:
        existing["label"] = label
    if url is not None:
        existing["url"] = url
    _custom_buttons[key] = existing


def get_custom_button(key: str) -> dict | None:
    return dict(_custom_buttons[key]) if key in _custom_buttons else None


def reset_custom_button(key: str) -> None:
    _custom_buttons.pop(key, None)


def all_custom_buttons() -> dict:
    return dict(_custom_buttons)


def is_btn_customized(key: str) -> bool:
    """True если кнопка была изменена относительно дефолта."""
    cb = _custom_buttons.get(key)
    if not cb:
        return False
    df = BUTTON_DEFS.get(key, {})
    label_changed = "label" in cb and cb["label"] != df.get("label")
    url_changed   = "url"   in cb and cb["url"]   != df.get("url")
    return label_changed or url_changed


def save_custom_buttons(path: str = "data/custom_buttons.json") -> None:
    import json, os
    os.makedirs("data", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_custom_buttons, f, ensure_ascii=False, indent=2)


async def push_custom_buttons_to_github(path: str = "data/custom_buttons.json") -> bool:
    """Зберігає custom_buttons в PostgreSQL (і локальний файл)."""
    save_custom_buttons(path)
    try:
        import db as _db
        await _db.save_kv("custom_buttons", _custom_buttons)
        print("✅ custom_buttons збережено в PostgreSQL")
        return True
    except Exception as ex:
        print(f"⚠️ push_custom_buttons_to_github (DB): {ex}")
        return False


def load_custom_buttons(path: str = "data/custom_buttons.json") -> None:
    import json
    try:
        with open(path, encoding="utf-8") as f:
            _custom_buttons.update(json.load(f))
    except FileNotFoundError:
        pass
    except Exception as ex:
        print(f"⚠️ load_custom_buttons: {ex}")
