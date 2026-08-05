"""
Брендинг Лумены — Custom Premium emoji из стикер-пака Telegram.
Использует <tg-emoji emoji-id="..."> для HTML-сообщений.
При отсутствии пака — текстовые fallback.
"""
from __future__ import annotations

_pack_ids: list[str] = []
_pack_name: str = ""

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
    Боты без Premium-подписки не могут отправлять <tg-emoji> через parse_mode=HTML —
    Telegram возвращает ENTITY_TEXT_INVALID. Используем простые Unicode-символы."""
    return fallback if fallback is not None else _FALLBACK.get(role, "•")


def ei(idx: int, fallback: str = "•") -> str:
    """Текстовый символ для HTML-сообщений (по индексу — возвращает fallback)."""
    return fallback


def get_id(idx: int) -> str | None:
    """ID кастомного emoji из пака по индексу (для entity-подхода, не для HTML)."""
    return _pack_ids[idx] if idx < len(_pack_ids) else None


def get_role_id(role: str) -> str | None:
    """ID кастомного emoji из пака по роли (для entity-подхода, не для HTML)."""
    idx = _ROLE_IDX.get(role)
    return _pack_ids[idx] if idx is not None and idx < len(_pack_ids) else None


def hdr() -> str:
    """Заголовок  EM  L U M E N A  EM  с Premium emoji."""
    em = e("header")
    return f"{em}  L U M E N A  {em}"


def div(n: int = 10) -> str:
    """Разделитель из n кастомных emoji."""
    em = e("divider", "▬")
    return em * n


def bul() -> str:
    """Буллет-поинт."""
    return e("bullet")


def acc() -> str:
    """Акцентный символ."""
    return e("accent")


def chk() -> str:
    """Галочка / принято."""
    return e("check", "✔")


def crown() -> str:
    """Корона для VIP."""
    return e("crown", "👑")


def set_pack(ids: list[str], name: str = "") -> None:
    """Устанавливает emoji пак по списку ID."""
    global _pack_ids, _pack_name
    _pack_ids = list(ids)
    _pack_name = name


def get_pack() -> list[str]:
    return list(_pack_ids)


def get_pack_name() -> str:
    return _pack_name


def has_pack() -> bool:
    return len(_pack_ids) > 0


def preview(n: int = 12) -> str:
    """HTML-строка с превью первых n emoji из пака (использует <tg-emoji> напрямую)."""
    parts = []
    for i in range(min(n, len(_pack_ids))):
        eid = _pack_ids[i]
        parts.append(f'<tg-emoji emoji-id="{eid}">[{i}]</tg-emoji>')
    return "".join(parts) if parts else "(пак не загружен)"


# ── Кастомные тексты от фаундера ─────────────────────────
_custom_texts: dict[str, dict] = {}

TEXT_LABELS: dict[str, str] = {
    # ── Главный экран ──────────────────────────────────────
    "start_text":          "Главный экран /start (верифицирован, {name})",
    "start_unverified":    "Первый /start — нужна верификация ({name})",

    # ── Верификация ────────────────────────────────────────
    "verify_btn":          "Кнопка «Пройти верификацию»",
    "verify_prompt":       "Экран верификации (текст + кнопка)",
    "verify_confirm_btn":  "Кнопка «Я не бот — подтвердить»",
    "verify_done":         "После успешной верификации ({name})",

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

    # ── Модерация анкет ────────────────────────────────────
    "anketa_approve":      "Анкета одобрена ✅",
    "anketa_reject":       "Анкета отклонена ❌",
    "anketa_delete":       "Анкета удалена",
    "mod_comment":         "Правки от модератора (юзеру)",
    "revoke_notify":       "Анкета отозвана (юзеру)",

    # ── VIP & Поддержка ────────────────────────────────────
    "vip_activated":       "VIP активирован 👑",
    "support_prompt":      "Начало диалога поддержки",
    "support_sent":        "Обращение отправлено",
}


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
        "label": "✅ Пройти верификацию",
        "url":   None,
        "desc":  "Кнопка старта верификации",
        "type":  "callback",
    },
    "verify_confirm": {
        "label": "✅ Я не бот — подтвердить",
        "url":   None,
        "desc":  "Кнопка подтверждения верификации",
        "type":  "callback",
    },
    "welcome_btn":    {
        "label": "📌 Добро пожаловать!",
        "url":   None,
        "desc":  "Кнопка в приветственном сообщении",
        "type":  "callback",
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


def load_custom_buttons(path: str = "data/custom_buttons.json") -> None:
    import json
    try:
        with open(path, encoding="utf-8") as f:
            _custom_buttons.update(json.load(f))
    except FileNotFoundError:
        pass
    except Exception as ex:
        print(f"⚠️ load_custom_buttons: {ex}")
