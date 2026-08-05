"""
ai_agent.py — Лумена AI (локальный, без внешних API)
══════════════════════════════════════════════════════
Использует только встроенный NLP-движок (lumena.py + nlu.py).
Никаких Groq, Gemini, OpenAI — всё работает автономно.
"""
import asyncio
import random
import re
import time
from typing import Optional

# ── Антиповтор ──────────────────────────────────────────────────────────────
_last_replies: dict[int, list[str]] = {}   # {chat_id: [последние 5 ответов]}
_history:      dict[int, list] = {}        # {chat_id: [(role, text)]}

MAX_RECENT = 6    # сколько последних ответов запоминаем для антиповтора
MAX_HISTORY = 20  # сколько реплик в памяти диалога

# ── Пул «живых» вставок чтобы разнообразить ответ ──────────────────────────
_OPENER_POOL = [
    "", "", "", "",   # чаще без вставки
    "Слушай, ",
    "Кстати, ",
    "Знаешь что? ",
    "Интересно — ",
    "Честно говоря, ",
    "Если подумать, ",
    "Ну вот, ",
    "Ладно, ",
]

_CLOSER_POOL = [
    "", "", "", "",   # чаще без
    " Что думаешь?",
    " Согласен?",
    " Интересно, правда?",
    " А у тебя как?",
    " Вот так вот 😊",
    " Надеюсь, помогло 💙",
    " Если что — спрашивай!",
]

# ── Фразы когда локальный NLP тоже ничего не нашёл ─────────────────────────
_FALLBACKS = [
    "Хм, интересный вопрос — дай подумаю 🤔 Напиши чуть подробнее?",
    "Не совсем поняла — уточни, пожалуйста 😊",
    "Сложно сказать с ходу. Расскажи подробнее — постараюсь помочь 💙",
    "Пока не нашла точного ответа. Попробуй переформулировать!",
    "М-м, надо подумать. Напиши иначе — разберёмся вместе 🙂",
    "Честно — не знаю. Но если уточнишь детали, попробую найти 🔍",
    "Хороший вопрос, но ответа нет прямо сейчас. Может, переформулируешь?",
    "Не уверена насчёт этого. Спроси иначе — помогу чем смогу 💙",
]

# ── Детектор мата/грубости (для фильтра ответа) ────────────────────────────
_RUDE_RE = re.compile(
    r"(?i)\b(х[уy]й|х[уy]я|пизд|ёба|еба|нахуй|бляд|мудак|пиздец|"
    r"шлюх|ублюдк|fuck(?:ing|ed|er)?|shit|bitch|asshole|cunt\b|motherfucker)\b",
    re.UNICODE,
)

_SAFE_REPLIES = [
    "Давай без этого — найдём тему получше 🙂",
    "Ок, сменим тему 😊",
    "Лучше поговорим о чём-то другом 💙",
]


def _is_rude(text: str) -> bool:
    return bool(_RUDE_RE.search(text))


# ── История ──────────────────────────────────────────────────────────────────
def _get_hist(chat_id: int) -> list:
    if chat_id not in _history:
        _history[chat_id] = []
    return _history[chat_id]


def _push_hist(chat_id: int, role: str, text: str):
    h = _get_hist(chat_id)
    h.append((role, text[:500]))
    if len(h) > MAX_HISTORY * 2:
        h[:] = h[-(MAX_HISTORY * 2):]


# ── Антиповтор ───────────────────────────────────────────────────────────────
def _get_recent(chat_id: int) -> list[str]:
    return _last_replies.get(chat_id, [])


def _push_recent(chat_id: int, reply: str):
    lst = _last_replies.setdefault(chat_id, [])
    lst.append(reply[:80])
    if len(lst) > MAX_RECENT:
        lst.pop(0)


def _dedupe(reply: str, chat_id: int) -> str:
    """Если ответ — точная копия одного из последних → берём fallback."""
    recent = _get_recent(chat_id)
    if reply.strip() in [r.strip() for r in recent]:
        return random.choice(_FALLBACKS)
    return reply


# ── Лёгкая постобработка: добавляем живую «интонацию» ───────────────────────
def _humanize(text: str, chat_id: int) -> str:
    """Изредка добавляет живой opener/closer чтобы не звучало как робот."""
    recent = _get_recent(chat_id)
    t = text.strip()
    if not t:
        return t

    # Не добавляем вставки к коротким ответам и к ответам с уже явной эмоцией
    if len(t) < 30 or t[-1] in "?!":
        return t

    # Если подобный opener уже был в последних — пропускаем
    opener = random.choice(_OPENER_POOL)
    closer = random.choice(_CLOSER_POOL)

    # Не добавляем одинаковые закрывалки подряд
    if closer and any(closer.strip() in r for r in recent[-2:]):
        closer = ""

    if opener:
        t = opener + t[0].lower() + t[1:]
    t = t + closer
    return t


# ── Публичный интерфейс ──────────────────────────────────────────────────────
async def lumena_reply(chat_id: int, user_name: str, text: str) -> str:
    """
    Возвращает ответ Лумены на основе встроенного NLP.
    Никогда не возвращает None — всегда есть запасная фраза.
    """
    from lumena import get_lumena_response   # импорт здесь, чтобы избежать циклов

    # Сохраняем сообщение пользователя в историю
    _push_hist(chat_id, "user", text)

    reply: Optional[str] = None

    try:
        # Основной ответ от локального NLP-движка
        reply = await get_lumena_response(chat_id, text, user_name)
    except Exception as e:
        import logging
        logging.warning(f"[AI] lumena error: {e}")
        reply = None

    # Если NLP вернул пустоту — берём случайный fallback
    if not reply or not reply.strip():
        reply = random.choice(_FALLBACKS)

    # Фильтр грубости (на случай если NLP что-то грубое сгенерировал)
    if _is_rude(reply):
        reply = random.choice(_SAFE_REPLIES)

    # Антиповтор
    reply = _dedupe(reply, chat_id)

    # Лёгкая «живость» интонации (не слишком часто)
    if random.random() < 0.25:
        reply = _humanize(reply, chat_id)

    # Запоминаем что сказали
    _push_hist(chat_id, "bot", reply)
    _push_recent(chat_id, reply)

    return reply


def clear_history(chat_id: int):
    """Сбросить историю разговора для данного чата."""
    _history.pop(chat_id, None)
    _last_replies.pop(chat_id, None)


def is_available() -> bool:
    """Локальный AI всегда доступен — не зависит от внешних сервисов."""
    return True
