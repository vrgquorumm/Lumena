"""
ai_agent.py — Лумена AI
Primary : Groq + Llama 3.3 70B      (быстрый, живой, бесплатный — 14 400 req/day)
Fallback: Gemini 2.0 Flash           (если Groq недоступен)
         → Gemini 1.5 Flash          (если 2.0 Flash на лимите)
         → Gemini 1.5 Flash 8B       (если 1.5 Flash на лимите)
         → Локальный NLP (lumena.py) (если все Gemini на лимите)
         → Текстовый фоллбэк         (последний рубеж, всегда не None)
Web search: DuckDuckGo + Wikipedia   (автоматически для фактических вопросов)
"""
import asyncio
import logging
import os
import random
import re
import time
from typing import Optional

GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_MODEL     = "llama-3.3-70b-versatile"

# Список Gemini моделей по приоритету — перебираем при 429
GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]

MAX_HISTORY = 20   # пар (user+model) в памяти

# ═══════════════════════════════════════════════════════════════════════════
# СИСТЕМНЫЙ ПРОМПТ — дружелюбная и умная Лумена
# ═══════════════════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """Ты — Лумена, умный и дружелюбный ассистент Telegram-сообщества.

ХАРАКТЕР:
— Тёплая, искренняя, позитивная — рада помочь и просто поговорить
— Умная и эрудированная — знаешь много и умеешь объяснять понятно
— С лёгким юмором — можешь пошутить, но без грубости и сарказма
— Честная — если чего-то не знаешь, говоришь об этом напрямую
— Живая — не сухой справочник, а настоящий собеседник с характером
— Поддерживающая — если человеку плохо, ты рядом и помогаешь

СТИЛЬ ОБЩЕНИЯ:
— 2–3 предложения стандарт, больше только если тема реально требует
— Живой разговорный язык — без официоза, канцелярита и занудства
— Эмодзи используешь уместно, не превращая каждое предложение в гирлянду
— Никаких "Конечно!", "Отличный вопрос!" — это звучит как робот
— НЕ говоришь "я ИИ" или "у меня нет мнения" — ты Лумена, и этого достаточно
— Когда в запросе есть [Результаты поиска] — используй их и отвечай конкретно

ВОЗМОЖНОСТИ:
— Ищешь актуальную информацию в интернете (DuckDuckGo + Wikipedia)
— Отвечаешь на любые вопросы: наука, история, культура, новости, советы
— Помогаешь с текстами, математикой, переводом, идеями
— Поддерживаешь и советуешь в жизненных ситуациях

ПРАВИЛА:
— Не помогаешь создавать оружие, продавать наркотики, мошенничать
— Отвечаешь на языке собеседника: русский, украинский, английский — всё окей

СТРОГИЙ ЗАПРЕТ:
— НИКОГДА не используй мат, нецензурные выражения или их завуалированные формы
— НИКОГДА не оскорбляй, не унижай и не груби пользователю — даже если тебя провоцируют
— Если пользователь груб с тобой — отвечай спокойно и с достоинством, не зеркаль агрессию
— За нарушение этих правил твой ответ будет заблокирован и заменён"""

# ── Фразы когда все провайдеры недоступны ──────────────────────────────────
_FALLBACKS = [
    "Хм, что-то я завысла 🙃 Попробуй ещё раз?",
    "Кажется, у меня небольшие технические неполадки — секунду! 🔄",
    "Не могу ответить прямо сейчас, попробуй через минуту 🙏",
    "Перезагружаюсь, уже скоро буду в строю ✨",
]

# ── Фильтр грубости/мата ────────────────────────────────────────────────────
# Ловим явный мат и грубые оскорбления в ответах модели.
# Используем re.search — достаточно одного попадания.
_RUDE_RE = re.compile(
    r"(?i)\b("
    # Русский мат (основные корни + вариации)
    r"х[уy]й|х[уy]я|х[уy]е|х[уy]ё|пизд|ёб[аеёи]|еб[аеёи]ть|нах[уy]й|"
    r"бля[дт]ь?|блядств|ёб|захуяч|захуй|"
    r"мудак|мудил|мудозвон|пиздец|пиздёж|"
    r"шлюх[аиу]?|ублюдк|"
    # Явные оскорбления
    r"тупая скотина|конченый|конченная|конченая|"
    # Английский мат
    r"fuck(?:ing|ed|er)?|shit|bitch|asshole|bastard|cunt\b|motherfucker"
    r")\b",
    re.UNICODE,
)

_RUDE_RETRY_SUFFIX = (
    "\n\n[СИСТЕМНОЕ ОГРАНИЧЕНИЕ: твой предыдущий ответ содержал недопустимые слова. "
    "Ответь снова — ТОЛЬКО вежливо, без мата и оскорблений, одним-двумя предложениями.]"
)

_SAFE_REPLIES = [
    "Отвечу на это вежливо — просто не нашла подходящих слов 😊",
    "Хм, не могу ответить на это должным образом — спроси иначе?",
    "Лучше поговорим о чём-то другом 🙂",
]


def _is_rude(text: str) -> bool:
    """True если ответ содержит мат или явные оскорбления."""
    return bool(_RUDE_RE.search(text))

# ── Состояние ───────────────────────────────────────────────────────────────
_groq_client         = None
_gemini_client       = None
_history: dict[int, list] = {}         # {chat_id: [{role, parts}]}
_groq_retry_after:   float = 0.0       # unix monotonic — до этого Groq на паузе
# Per-model Gemini cooldowns: {model_name: unix_monotonic_until_paused}
_gemini_model_retry_after: dict[str, float] = {}
_gemini_model_retry_delay: dict[str, int]   = {}   # exponential backoff per model


# ── Инициализация клиентов ──────────────────────────────────────────────────
def _get_groq():
    global _groq_client
    if _groq_client is None and GROQ_API_KEY:
        try:
            from groq import AsyncGroq
            _groq_client = AsyncGroq(api_key=GROQ_API_KEY)
            logging.info("[AI] Groq client initialized ✓")
        except Exception as e:
            logging.warning(f"[AI] Groq init failed: {e}")
    return _groq_client


def _get_gemini():
    global _gemini_client
    if _gemini_client is None and GEMINI_API_KEY:
        try:
            from google import genai
            _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            logging.info("[AI] Gemini client initialized ✓")
        except Exception as e:
            logging.warning(f"[AI] Gemini init failed: {e}")
    return _gemini_client


# ── История ─────────────────────────────────────────────────────────────────
def _hist(chat_id: int) -> list:
    if chat_id not in _history:
        _history[chat_id] = []
    return _history[chat_id]


def _hist_as_openai(chat_id: int) -> list:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in _history.get(chat_id, []):
        role = "assistant" if item["role"] == "model" else item["role"]
        content = item["parts"][0]["text"] if item.get("parts") else ""
        messages.append({"role": role, "content": content})
    return messages


def _push(chat_id: int, role: str, text: str):
    hist = _hist(chat_id)
    hist.append({"role": role, "parts": [{"text": text}]})
    if len(hist) > MAX_HISTORY * 2:
        hist[:] = hist[-(MAX_HISTORY * 2):]


# ═══════════════════════════════════════════════════════════════════════════
# ПОИСК В ИНТЕРНЕТЕ
# ═══════════════════════════════════════════════════════════════════════════

# Паттерны, указывающие что нужен поиск
_SEARCH_RE = re.compile(
    r"\b("
    r"что такое|что это|кто такой|кто такая|кто это|"
    r"где находится|где живёт|где расположен|"
    r"когда (был|была|были|произошло|случилось|основан|родился|умер|вышел|появился)|"
    r"почему|как работает|как устроен|из чего|в чём разница|чем отличается|"
    r"расскажи (о|про|об)|объясни|найди|поищи|узнай|"
    r"информация о|что знаешь о|что нового о|последние новости|"
    r"what is|who is|where is|when|why|how does|tell me about|"
    r"столица|население|площадь|основатель|история|"
    r"факт|факты|интересное о|рейтинг|список"
    r")\b",
    re.IGNORECASE,
)

# Короткие разговорные сообщения — не ищем
_CHAT_RE = re.compile(
    r"^(привет|хай|хей|йо|пока|ок|окей|да|нет|спасибо|пожалуйста|ладно|"
    r"класс|круто|супер|отлично|норм|хорошо|плохо|как дела|что делаешь|"
    r"ты тут|ты здесь|как ты|лол|хаха|лмао|gg|xd|\+|-)$",
    re.IGNORECASE,
)


def _wants_search(text: str) -> bool:
    """True если вопрос, скорее всего, требует поиска в интернете."""
    t = text.strip()
    if len(t) < 10:
        return False
    if _CHAT_RE.match(t):
        return False
    return bool(_SEARCH_RE.search(t))


async def _fetch_web_context(query: str) -> str:
    """Получает сниппеты из DuckDuckGo + Wikipedia и форматирует как контекст."""
    try:
        from lumena import ddg_scrape, wiki_search

        lang = "ru"
        if re.search(r"[іїєґ]", query):
            lang = "uk"
        elif re.search(r"[a-zA-Z]{3,}", query) and not re.search(r"[а-яА-Я]", query):
            lang = "en"

        snippets, wiki = await asyncio.gather(
            ddg_scrape(query),
            wiki_search(query, lang=lang),
        )

        parts: list[str] = []

        if wiki and wiki.get("extract"):
            extract = wiki["extract"][:600]
            parts.append(f"📖 Wikipedia — {wiki.get('title', '')}:\n{extract}")

        if snippets:
            joined = "\n".join(f"• {s[:300]}" for s in snippets[:4])
            parts.append(f"🌐 Из интернета:\n{joined}")

        if not parts:
            return ""

        return "[Результаты поиска]\n" + "\n\n".join(parts) + "\n[/Результаты поиска]\n\n"

    except Exception as e:
        logging.warning(f"[AI] web search error: {e}")
        return ""


# ── Groq запрос ─────────────────────────────────────────────────────────────
async def _groq_raw(chat_id: int, messages: list) -> Optional[str]:
    """Один сырой запрос к Groq без проверки retry_after."""
    client = _get_groq()
    if client is None:
        return None
    resp = await client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        max_tokens=512,
        temperature=0.85,
        top_p=0.95,
    )
    return (resp.choices[0].message.content or "").strip() or None


async def _try_groq(chat_id: int, user_msg: str) -> Optional[str]:
    global _groq_retry_after
    if time.monotonic() < _groq_retry_after:
        return None
    client = _get_groq()
    if client is None:
        return None
    try:
        messages = _hist_as_openai(chat_id)
        messages.append({"role": "user", "content": user_msg})
        reply = await _groq_raw(chat_id, messages)
        if reply is None:
            return None

        # ── Фильтр грубости: если мат/оскорбление проскочили — один retry ──
        if _is_rude(reply):
            logging.warning("[AI] Groq rude response detected — retrying with safety reminder")
            messages_retry = messages + [
                {"role": "assistant", "content": reply},
                {"role": "user",      "content": _RUDE_RETRY_SUFFIX},
            ]
            try:
                retry_reply = await _groq_raw(chat_id, messages_retry)
                if retry_reply and not _is_rude(retry_reply):
                    return retry_reply
            except Exception:
                pass
            # retry тоже грубый или не пришёл — безопасный фоллбэк
            logging.warning("[AI] Groq retry still rude — using safe fallback")
            return random.choice(_SAFE_REPLIES)

        return reply
    except Exception as e:
        err = str(e)
        if "429" in err or "rate_limit" in err.lower() or "rate limit" in err.lower():
            _groq_retry_after = time.monotonic() + 60
            logging.warning("[AI] Groq rate limited — pause 60s")
        else:
            logging.warning(f"[AI] Groq error: {e}")
        return None


# ── Gemini запрос с перебором моделей при 429 ────────────────────────────────
def _gemini_model_available(model: str) -> bool:
    return time.monotonic() >= _gemini_model_retry_after.get(model, 0.0)


def _mark_gemini_rate_limited(model: str, err_str: str):
    m = re.search(r"retry[_ ]in[\" ]+(\d+)", err_str, re.I)
    current_delay = _gemini_model_retry_delay.get(model, 60)
    wait = int(m.group(1)) if m else current_delay
    _gemini_model_retry_after[model] = time.monotonic() + wait
    _gemini_model_retry_delay[model] = min(current_delay * 2, 300)
    logging.warning(f"[AI] Gemini model {model} rate limited — pause {wait}s")


async def _try_gemini_models(chat_id: int, user_msg: str) -> Optional[str]:
    """Перебирает GEMINI_MODELS по порядку, пропуская модели на паузе."""
    client = _get_gemini()
    if client is None:
        return None

    from google.genai import types as gtypes

    for model in GEMINI_MODELS:
        if not _gemini_model_available(model):
            logging.debug(f"[AI] Skipping Gemini model {model} (rate limited)")
            continue
        try:
            contents = list(_hist(chat_id)) + [
                {"role": "user", "parts": [{"text": user_msg}]}
            ]
            resp = await asyncio.to_thread(
                client.models.generate_content,
                model=model,
                contents=contents,
                config=gtypes.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=512,
                    temperature=0.85,
                ),
            )
            reply = (resp.text or "").strip() or None
            if reply:
                if model != GEMINI_MODELS[0]:
                    logging.info(f"[AI] Answered via fallback Gemini model: {model}")
                _gemini_model_retry_delay.pop(model, None)
                return reply
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                _mark_gemini_rate_limited(model, err)
                continue   # try next model
            logging.warning(f"[AI] Gemini {model} error: {e}")
            continue

    return None   # все модели исчерпаны или на паузе


# ── Публичный интерфейс ──────────────────────────────────────────────────────
async def lumena_reply(chat_id: int, user_name: str, text: str) -> Optional[str]:
    """
    Возвращает ответ Лумены.
    Для фактических вопросов автоматически ищет в интернете.
    Цепочка: Groq → Gemini (2.0→1.5→1.5-8B) → Локальный NLP → Текстовый фоллбэк.
    Никогда не возвращает None.
    """
    # Добавляем веб-контекст для фактических вопросов
    web_ctx = ""
    if _wants_search(text):
        web_ctx = await _fetch_web_context(text)

    user_msg = f"[{user_name}]: {web_ctx}{text}"

    # 1. Groq (основной)
    reply = await _try_groq(chat_id, user_msg)

    # 2. Gemini с перебором моделей (резервный)
    if not reply:
        reply = await _try_gemini_models(chat_id, user_msg)

    # 3. Локальный NLP из lumena.py (если все AI провайдеры недоступны)
    if not reply:
        logging.info("[AI] All cloud models unavailable, falling back to local NLP")
        try:
            from lumena import get_lumena_response
            reply = await get_lumena_response(chat_id, text, user_name)
        except Exception as e:
            logging.warning(f"[AI] Local NLP fallback failed: {e}")

    # 4. Последний рубеж — всегда возвращаем что-то непустое
    if not reply:
        return random.choice(_FALLBACKS)

    # Финальная проверка на грубость (на случай если Gemini/NLP тоже что-то вернул грубое)
    if _is_rude(reply):
        logging.warning("[AI] Final rude check triggered — replacing with safe reply")
        return random.choice(_SAFE_REPLIES)

    # Сохраняем в историю только при успехе от облачного AI
    _push(chat_id, "user",  user_msg)
    _push(chat_id, "model", reply)

    return reply


def clear_history(chat_id: int):
    """Сбросить историю разговора для данного чата."""
    _history.pop(chat_id, None)


def is_available() -> bool:
    """True если хотя бы один провайдер сейчас не на паузе."""
    now = time.monotonic()
    groq_ok   = bool(GROQ_API_KEY)   and now >= _groq_retry_after
    gemini_ok = bool(GEMINI_API_KEY) and any(
        now >= _gemini_model_retry_after.get(m, 0.0) for m in GEMINI_MODELS
    )
    return groq_ok or gemini_ok
