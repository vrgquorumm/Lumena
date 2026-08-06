"""
ai_agent.py — Лумена AI
══════════════════════════════════════════════════════
Использует OpenAI API (OPENAI_API_KEY) если доступен.
Если ключа нет — fallback на локальный NLP (lumena.py).
"""
import asyncio
import os
import random
import re
import time
from typing import Optional

# ── Антиповтор ──────────────────────────────────────────────────────────────
_last_replies: dict[int, list[str]] = {}   # {chat_id: [последние 5 ответов]}
_history:      dict[int, list[dict]] = {}  # {chat_id: [{"role": ..., "content": ...}]}

MAX_RECENT  = 6
MAX_HISTORY = 20   # пар user/assistant

# ── System prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
Ты — Lumena.

Общайся как обычный человек из Telegram.

Правила:
- Естественная разговорная речь.
- Используй сленг когда это уместно.
- Если пользователь матерится — можешь ответить с умеренным матом.
- Не говори шаблонными фразами.
- Не упоминай, что ты ИИ, если тебя не спрашивают напрямую.
- Отвечай эмоционально и разнообразно.
- Иногда шути.
- Иногда отвечай очень коротко.
- Иногда подробно.
- Не повторяй одинаковые конструкции.
- Если не знаешь ответа — честно скажи, что не знаешь.
"""

# ── Fallback-фразы когда нет ключа или ошибка API ───────────────────────────
_FALLBACKS = [
    "Хм, интересный вопрос — напиши чуть подробнее? 🤔",
    "Не совсем поняла — уточни, пожалуйста 😊",
    "Сложно сказать с ходу. Расскажи подробнее 💙",
    "Пока не нашла точного ответа. Попробуй переформулировать!",
    "Честно — не знаю. Но если уточнишь детали, попробую помочь 🔍",
    "Хороший вопрос, но ответа нет прямо сейчас.",
    "Не уверена насчёт этого. Спроси иначе 💙",
]

# ── OpenAI клиент (ленивая инициализация) ───────────────────────────────────
_oai_client = None

def _get_openai_client():
    global _oai_client
    if _oai_client is not None:
        return _oai_client
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return None
    try:
        from openai import AsyncOpenAI
        _oai_client = AsyncOpenAI(api_key=api_key)
        return _oai_client
    except ImportError:
        return None


# ── История ──────────────────────────────────────────────────────────────────
def _get_hist(chat_id: int) -> list[dict]:
    if chat_id not in _history:
        _history[chat_id] = []
    return _history[chat_id]


def _push_hist(chat_id: int, role: str, content: str):
    h = _get_hist(chat_id)
    h.append({"role": role, "content": content[:1000]})
    # Обрезаем до MAX_HISTORY пар
    if len(h) > MAX_HISTORY * 2:
        h[:] = h[-(MAX_HISTORY * 2):]


# ── Антиповтор ───────────────────────────────────────────────────────────────
def _push_recent(chat_id: int, reply: str):
    lst = _last_replies.setdefault(chat_id, [])
    lst.append(reply[:80])
    if len(lst) > MAX_RECENT:
        lst.pop(0)


def _is_recent(chat_id: int, reply: str) -> bool:
    recent = _last_replies.get(chat_id, [])
    return reply.strip() in [r.strip() for r in recent]


# ── OpenAI запрос ────────────────────────────────────────────────────────────
async def _ask_openai(chat_id: int, text: str) -> Optional[str]:
    client = _get_openai_client()
    if not client:
        return None

    history = _get_hist(chat_id)
    messages = [{"role": "system", "content": SYSTEM_PROMPT.strip()}]
    messages.extend(history)
    messages.append({"role": "user", "content": text})

    try:
        resp = await client.chat.completions.create(
            model="gpt-4o",
            temperature=1.15,
            top_p=0.95,
            presence_penalty=0.8,
            frequency_penalty=0.4,
            max_tokens=600,
            messages=messages,
        )
        return resp.choices[0].message.content
    except Exception as e:
        import logging
        logging.warning(f"[AI/OpenAI] error: {e}")
        return None


# ── Локальный NLP fallback ────────────────────────────────────────────────────
async def _ask_local(chat_id: int, text: str, user_name: str) -> Optional[str]:
    try:
        from lumena import get_lumena_response
        return await get_lumena_response(chat_id, text, user_name)
    except Exception as e:
        import logging
        logging.warning(f"[AI/local] lumena error: {e}")
        return None


# ── Публичный интерфейс ──────────────────────────────────────────────────────
async def lumena_reply(chat_id: int, user_name: str, text: str) -> str:
    """
    Возвращает ответ Лумены.
    Порядок: OpenAI API → локальный NLP → случайный fallback.
    """
    _push_hist(chat_id, "user", text)

    reply: Optional[str] = None

    # 1. Пробуем OpenAI
    reply = await _ask_openai(chat_id, text)

    # 2. Fallback: локальный NLP
    if not reply or not reply.strip():
        reply = await _ask_local(chat_id, text, user_name)

    # 3. Крайний fallback
    if not reply or not reply.strip():
        reply = random.choice(_FALLBACKS)

    # Антиповтор
    if _is_recent(chat_id, reply):
        alt = await _ask_openai(chat_id, text)
        if alt and alt.strip() and not _is_recent(chat_id, alt):
            reply = alt
        else:
            reply = random.choice(_FALLBACKS)

    _push_hist(chat_id, "assistant", reply)
    _push_recent(chat_id, reply)

    return reply


def clear_history(chat_id: int):
    """Сбросить историю разговора для данного чата."""
    _history.pop(chat_id, None)
    _last_replies.pop(chat_id, None)


def is_available() -> bool:
    """True если доступен хотя бы локальный NLP."""
    return True
