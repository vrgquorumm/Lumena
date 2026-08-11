"""
AI Ассистент — FastAPI + Gemini
================================
Умный ИИ-ассистент с естественным общением, стримингом,
историей сессии и настраиваемой личностью.
"""

import os
import uuid
import json
import asyncio
from datetime import datetime
from typing import Optional

from google import genai
from google.genai import types as gtypes
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

# ══════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ
# ══════════════════════════════════════════════════════
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
PORT           = int(os.environ.get("PORT", 5002))
MODEL_NAME     = "gemini-2.0-flash"
MAX_HISTORY    = 50   # максимум сообщений в истории сессии

_client: genai.Client | None = None

def get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client

# ══════════════════════════════════════════════════════
# ЛИЧНОСТИ (системные промпты)
# ══════════════════════════════════════════════════════
PERSONALITIES: dict[str, dict] = {
    "default": {
        "name": "Классический",
        "emoji": "⚡",
        "prompt": """Ты — интеллект высшего порядка. Не просто помощник — собеседник, \
способный видеть суть там, где другие видят лишь поверхность.

ХАРАКТЕР:
- Говоришь уверенно и по существу — без лишних слов и пустых вводных
- Не начинаешь с «Конечно!», «Отличный вопрос!», «Разумеется!» — это удел посредственных ботов
- Простой вопрос — острый точный ответ. Сложная тема — чёткая структура, примеры, глубина
- Можешь быть прямым до резкости — это лучше, чем тёплая вода вместо ответа
- Замечаешь нюансы в вопросе и отвечаешь на то, что действительно спрашивают

ИНТЕЛЛЕКТ:
- Если не знаешь — говоришь об этом прямо, без выдумок
- Различаешь «знаю точно», «предположительно» и «не в курсе»
- Если запрос размыт — задаёшь ровно один вопрос, не анкету
- Ошибся — признаёшь кратко и исправляешь

КОНТЕКСТ:
- Держишь весь разговор в голове и используешь его
- Не спрашиваешь повторно то, что уже было сказано
- Если тема менялась — отслеживаешь это

ФОРМАТ:
- Код — в блоках с языком: ```python ... ```
- Markdown только там, где он действительно помогает структуре
- Короткий ответ на короткий вопрос; развёрнутый — на сложный
- Нумерованные списки вместо хаотичных маркеров в инструкциях""",
    },

    "expert": {
        "name": "Архитектор",
        "emoji": "🏛",
        "prompt": """Ты — старший архитектор знаний. За твоими плечами — глубокая экспертиза \
в технологиях, науке, инженерии и аналитике. Ты не объясняешь очевидное — ты раскрываешь скрытое.

ПОДХОД:
- Отвечаешь с позиции человека, который видел этот вопрос тысячу раз и знает где ловушки
- Называешь вещи своими именами — с правильной терминологией и без лишнего упрощения
- Для сложных тем: сначала суть, потом детали, потом примеры — не наоборот
- Указываешь на подводные камни которые большинство пропускает
- Неточный вопрос — переформулируешь точно, а потом отвечаешь

ЧЕСТНОСТЬ:
- «Знаю», «думаю что», «не уверен» — различаешь строго
- Если вопрос некорректен — говоришь об этом прямо, объясняешь почему
- Рекомендуешь первоисточники когда это важно

ФОРМАТ:
- Структура всегда: от сути к деталям
- Блоки кода с комментариями; команды в `кодовых блоках`
- Примеры — реальные, рабочие, без заглушек""",
    },

    "friendly": {
        "name": "Союзник",
        "emoji": "🤝",
        "prompt": """Ты — умный союзник, который всегда на стороне собеседника. \
Не ассистент-исполнитель, а человек с характером и теплотой.

ОБЩЕНИЕ:
- Говоришь как умный друг — прямо, тепло, без снисхождения
- Слышишь не только слова, но и настроение за ними
- Когда человеку тяжело — сначала принимаешь, потом предлагаешь
- Юмор — уместный и живой, не натужный
- Если представился по имени — используешь его

ПОДДЕРЖКА:
- Не заваливаешь советами когда их не просят
- Сначала слушаешь — потом говоришь
- Признаёшь когда что-то сложно или неоднозначно

СТИЛЬ:
- Живой язык без канцелярии
- Эмодзи — только к месту, не каждое предложение
- Ёмко и по существу — но без холодности""",
    },

    "creative": {
        "name": "Провокатор",
        "emoji": "🔥",
        "prompt": """Ты — нестандартный интеллект с острым взглядом и нетерпимостью к банальности. \
Твоя задача — видеть то, что другие не замечают, и говорить то, что другие не решаются.

МЫШЛЕНИЕ:
- На каждый вопрос ищешь неочевидный угол — очевидный ответ даст кто угодно
- Используешь аналогии, парадоксы и неожиданные связи между идеями
- Задаёшь вопросы которые переворачивают исходную постановку
- Исследуешь тему с нескольких сторон прежде чем выносить суждение

ОБЩЕНИЕ:
- Пишешь ярко, с характером — но не ради эпатажа, а ради точности
- Можешь быть провокационным — когда это помогает думать глубже
- Острый юмор и игра слов приветствуются
- Не боишься сказать «здесь нет правильного ответа — вот почему»

СТИЛЬ:
- «А что если...» вместо «очевидно что...»
- Метафоры как инструмент, не украшение
- Плотный, насыщенный текст — без воды""",
    },
}

# ══════════════════════════════════════════════════════
# СЕССИИ (in-memory хранилище)
# ══════════════════════════════════════════════════════
sessions: dict[str, dict] = {}

def new_session(system_prompt: str) -> dict:
    return {
        "history": [],          # [{role, parts:[{text}]}, ...]
        "system_prompt": system_prompt,
        "created_at": datetime.now().isoformat(),
        "message_count": 0,
    }

# ══════════════════════════════════════════════════════
# МОДЕЛИ ЗАПРОСОВ
# ══════════════════════════════════════════════════════
class CreateSessionReq(BaseModel):
    personality: Optional[str] = "default"
    system_prompt: Optional[str] = None

class ChatReq(BaseModel):
    session_id: str
    message: str

class UpdateSystemReq(BaseModel):
    system_prompt: str

class ClearReq(BaseModel):
    keep_system: bool = True

# ══════════════════════════════════════════════════════
# ПРИЛОЖЕНИЕ
# ══════════════════════════════════════════════════════
app = FastAPI(title="AI Ассистент", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Утилита: синхронный Gemini в отдельном треде ─────
def _gemini_stream(session: dict):
    """
    Запускает стриминг Gemini (синхронный) с полной историей.
    История уже включает последнее сообщение пользователя.
    """
    client = get_client()
    return client.models.generate_content_stream(
        model=MODEL_NAME,
        contents=session["history"],
        config=gtypes.GenerateContentConfig(
            system_instruction=session["system_prompt"],
            max_output_tokens=8192,
            temperature=0.95,
            top_p=0.95,
        ),
    )

# ══════════════════════════════════════════════════════
# API РОУТЫ
# ══════════════════════════════════════════════════════

@app.get("/api/personalities")
async def get_personalities():
    """Список доступных личностей."""
    return {
        key: {"name": val["name"], "emoji": val["emoji"]}
        for key, val in PERSONALITIES.items()
    }

@app.post("/api/sessions")
async def create_session(req: CreateSessionReq):
    """Создать новую сессию."""
    if req.system_prompt:
        system_prompt = req.system_prompt
    elif req.personality and req.personality in PERSONALITIES:
        system_prompt = PERSONALITIES[req.personality]["prompt"]
    else:
        system_prompt = PERSONALITIES["default"]["prompt"]

    session_id = str(uuid.uuid4())
    sessions[session_id] = new_session(system_prompt)
    return {
        "session_id": session_id,
        "personality": req.personality or "default",
    }

@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Получить историю сессии."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    sess = sessions[session_id]
    return {
        "session_id": session_id,
        "message_count": sess["message_count"],
        "created_at": sess["created_at"],
        "history": [
            {
                "role": h["role"],
                "text": h["parts"][0]["text"] if h["parts"] else "",
            }
            for h in sess["history"]
        ],
    }

@app.delete("/api/sessions/{session_id}/history")
async def clear_history(session_id: str):
    """Очистить историю сессии (сохранить системный промпт)."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    sess = sessions[session_id]
    sess["history"] = []
    sess["message_count"] = 0
    return {"ok": True}

@app.put("/api/sessions/{session_id}/system")
async def update_system(session_id: str, req: UpdateSystemReq):
    """Обновить системный промпт сессии."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    sessions[session_id]["system_prompt"] = req.system_prompt
    return {"ok": True}

@app.post("/api/chat")
async def chat(req: ChatReq):
    """Отправить сообщение и получить стримовый ответ (SSE)."""
    if not GEMINI_API_KEY:
        async def no_key():
            yield f'data: {json.dumps({"type":"error","message":"GEMINI_API_KEY не задан. Добавьте ключ в настройках."})}\n\n'
        return StreamingResponse(no_key(), media_type="text/event-stream")

    if req.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    session = sessions[req.session_id]
    user_message = req.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Пустое сообщение")

    # Добавляем сообщение пользователя в историю
    session["history"].append({
        "role": "user",
        "parts": [{"text": user_message}],
    })
    session["message_count"] += 1

    async def generate():
        full_response = ""
        try:
            # Gemini синхронный — запускаем в отдельном треде
            response = await asyncio.to_thread(_gemini_stream, session)

            for chunk in response:
                text = getattr(chunk, "text", None)
                if text:
                    full_response += text
                    payload = json.dumps({"type": "chunk", "text": text})
                    yield f"data: {payload}\n\n"
                    await asyncio.sleep(0)   # отдаём управление event loop-у

            # Сохраняем ответ ассистента
            session["history"].append({
                "role": "model",
                "parts": [{"text": full_response}],
            })
            session["message_count"] += 1

            # Обрезаем историю если слишком длинная
            if len(session["history"]) > MAX_HISTORY:
                session["history"] = session["history"][-MAX_HISTORY:]

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            error_text = str(e)
            # Понятные ошибки для пользователя
            if "API_KEY_INVALID" in error_text or "invalid" in error_text.lower():
                msg = "Неверный GEMINI_API_KEY. Проверьте ключ в настройках."
            elif "quota" in error_text.lower() or "429" in error_text:
                msg = "Превышена квота API. Попробуйте через минуту."
            elif "network" in error_text.lower() or "connection" in error_text.lower():
                msg = "Ошибка сети. Проверьте подключение и попробуйте снова."
            else:
                msg = f"Ошибка Gemini: {error_text[:200]}"

            # Убираем последнее незавершённое сообщение пользователя
            if session["history"] and session["history"][-1]["role"] == "user":
                session["history"].pop()
                session["message_count"] = max(0, session["message_count"] - 1)

            yield f"data: {json.dumps({'type': 'error', 'message': msg})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )

# ══════════════════════════════════════════════════════
# СТАТИКА И HTML
# ══════════════════════════════════════════════════════
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

async def _html_response():
    html_path = os.path.join(static_dir, "index.html")
    with open(html_path, encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/")
@app.get("/ai-chat")
@app.get("/ai-chat/")
async def root():
    return await _html_response()

# ══════════════════════════════════════════════════════
# ЗАПУСК
# ══════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    print(f"🤖 AI Ассистент запускается на порту {PORT}…")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,
        log_level="info",
    )
