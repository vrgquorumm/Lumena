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

    # ── Дополнительные кнопки и ответы ────────────────────
    "main_chat_btn":       "Кнопка «Чат проекта»",
    "main_channel_btn":    "Кнопка «Канал»",
    "main_help_btn":       "Кнопка «Все команды»",
    "anketa_lang_uk":      "Кнопка языка «Українська»",
    "anketa_lang_ru":      "Кнопка языка «Русский»",
    "anketa_media_done_btn": "Кнопка «Готово» в медиа-шаге",
    "anketa_media_skip_btn": "Кнопка «Без медиа»",
    "anketa_media_hint_ru": "Подсказка медиа-шагa (русский)",
    "anketa_media_hint_uk": "Подсказка медиа-шагa (украинский)",
    "anketa_media_accepted_ru": "Медиа принято (русский)",
    "anketa_media_accepted_uk": "Медиа принято (украинский)",
    "anketa_media_limit_ru": "Достигнут лимит медиа (русский)",
    "anketa_media_limit_uk": "Достигнут лимит медиа (украинский)",
    "anketa_mod_accept_btn": "Кнопка модерации «Принять»",
    "anketa_mod_reject_btn": "Кнопка модерации «Отклонить»",
    "anketa_mod_comment_btn": "Кнопка модерации «Правки»",
    "anketa_my_delete_btn": "Кнопка «Удалить анкету»",
    "anketa_my_edit_btn": "Кнопка «Редактировать анкету»",
    "anketa_reaction_like_btn": "Кнопка реакции «Нравится»",
    "anketa_reaction_dislike_btn": "Кнопка реакции «Не нравится»",
    "anketa_reaction_chat_btn": "Кнопка «Наш чат»",
    "anketa_reaction_create_btn": "Кнопка «Создать анкету»",
    "verify_already": "Ответ «Уже верифицирован»",
    "media_sent_callback": "Ответ «Отправлено на модерацию»",
    "media_skipped_callback": "Ответ «Медиа пропущено»",
    "anketa_not_mine_callback": "Ответ «Это не твоя анкета»",
}

# Подсказки показываются фаундеру при выборе пункта редактора. Они не
# ограничивают содержимое сообщения, а только объясняют доступные подстановки.
TEXT_PLACEHOLDERS: dict[str, str] = {
    "start_text": "{name}",
    "start_unverified": "{name}",
    "verify_done": "{name}",
    "welcome_msg": "{name}",
    "step_accepted": "{step}, {total}, {question}",
    "anketa_approve": "{name}",
    "anketa_reject": "{name}",
    "mod_comment": "{comment}",
    "revoke_notify": "{name}",
    "vip_activated": "{name}",
    "support_sent": "{name}",
    "anketa_media_hint_ru": "{count}",
    "anketa_media_hint_uk": "{count}",
    "anketa_media_accepted_ru": "{count}",
    "anketa_media_accepted_uk": "{count}",
    "anketa_media_limit_ru": "{count}",
    "anketa_media_limit_uk": "{count}",
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


def substitute_values(
    text: str,
    entities: list[dict],
    values: dict[str, object],
) -> tuple[str, list[dict]]:
    """Заменяет доступные {placeholders}, сохраняя offsets Telegram entities.

    Значения подставляются слева направо. Если значение для placeholder не
    передано, он остаётся в сообщении — это позволяет безопасно хранить текст
    даже при добавлении новых переменных.
    """
    result_text = text
    result_entities = [dict(entity) for entity in entities]
    for key, value in values.items():
        placeholder = "{" + key + "}"
        if placeholder not in result_text:
            continue
        result_text, result_entities = _substitute_once(
            result_text, result_entities, placeholder, str(value)
        )
    return result_text, result_entities


def _substitute_once(
    text: str,
    entities: list[dict],
    placeholder: str,
    replacement: str,
) -> tuple[str, list[dict]]:
    pos = text.find(placeholder)
    if pos < 0:
        return text, entities

    offset_diff = len(replacement) - len(placeholder)
    new_text = text[:pos] + replacement + text[pos + len(placeholder):]
    new_entities = []
    placeholder_end = pos + len(placeholder)
    for entity in entities:
        updated = dict(entity)
        entity_offset = updated.get("offset", 0)
        entity_end = entity_offset + updated.get("length", 0)
        if entity_offset >= placeholder_end:
            updated["offset"] = entity_offset + offset_diff
        elif entity_end <= pos:
            pass
        elif entity_offset >= pos:
            # Entity starts inside the placeholder. Keep it valid but move it
            # to cover the replacement instead of producing invalid offsets.
            updated["offset"] = pos
            updated["length"] = max(1, len(replacement))
        elif entity_end > pos:
            updated["length"] = max(1, updated.get("length", 0) + offset_diff)
        new_entities.append(updated)
    return new_text, new_entities


def set_custom_text(key: str, text: str, entities: list[dict]) -> None:
    _custom_texts[key] = {"text": text, "entities": entities}


def get_custom_text(key: str) -> tuple[str, list[dict]] | None:
    d = _custom_texts.get(key)
    return (d["text"], d.get("entities", [])) if d else None


def plain_text(key: str, default: str) -> str:
    """Возвращает кастомную подпись кнопки или callback без entities."""
    custom = get_custom_text(key)
    return custom[0].strip() if custom and custom[0].strip() else default


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
