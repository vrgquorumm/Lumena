"""
test_ai_agent.py — тесты автоматического переключения моделей в lumena_reply().

Запуск:
    python -m pytest test_ai_agent.py -v
"""
import asyncio
import time
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import ai_agent


# ── Вспомогательные фабрики ───────────────────────────────────────────────

def _make_resp(text: str):
    """Фейковый ответ Gemini."""
    r = MagicMock()
    r.text = text
    return r


def _rate_limit_exc(model: str = "gemini-2.0-flash") -> Exception:
    return Exception(f"429 RESOURCE_EXHAUSTED quota for {model}")


# ── Базовый класс с setup/teardown ────────────────────────────────────────

class BaseTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Сброс всего глобального состояния между тестами
        ai_agent._client = None
        ai_agent._history.clear()
        ai_agent._model_retry_after.clear()
        ai_agent._model_retry_delay.clear()


# ── Тест 1: первичная модель отвечает успешно ─────────────────────────────

class TestPrimaryModelSuccess(BaseTest):
    async def test_primary_model_used_on_success(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_resp("Привет")

        with patch("ai_agent._get_client", return_value=mock_client):
            result = await ai_agent.lumena_reply(1, "Alice", "Привет")

        self.assertEqual(result, "Привет")
        # Только один вызов — к первичной модели
        self.assertEqual(mock_client.models.generate_content.call_count, 1)
        call_args = mock_client.models.generate_content.call_args
        self.assertEqual(call_args.kwargs["model"], ai_agent.MODELS[0])


# ── Тест 2: первичная 429 → вторичная отвечает ────────────────────────────

class TestFallbackToSecondModel(BaseTest):
    async def test_429_on_primary_falls_back_to_secondary(self):
        call_count = {"n": 0}

        def side_effect(**kwargs):
            call_count["n"] += 1
            if kwargs["model"] == ai_agent.MODELS[0]:
                raise _rate_limit_exc(ai_agent.MODELS[0])
            return _make_resp("От резервной модели")

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = side_effect

        with patch("ai_agent._get_client", return_value=mock_client):
            result = await ai_agent.lumena_reply(2, "Bob", "Тест")

        self.assertEqual(result, "От резервной модели")
        # Первичная модель теперь на паузе
        self.assertGreater(
            ai_agent._model_retry_after.get(ai_agent.MODELS[0], 0),
            time.monotonic() - 1,
        )


# ── Тест 3: все Gemini модели на 429 → вызывается локальный NLP ──────────

class TestAllModelsRateLimited(BaseTest):
    async def test_all_models_rate_limited_calls_local_nlp(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = _rate_limit_exc

        local_mock = AsyncMock(return_value="Локальный ответ")

        with (
            patch("ai_agent._get_client", return_value=mock_client),
            patch("lumena.get_lumena_response", local_mock),
        ):
            result = await ai_agent.lumena_reply(3, "Carol", "Привет")

        self.assertEqual(result, "Локальный ответ")
        local_mock.assert_awaited_once()


# ── Тест 4: локальный NLP падает → всё равно возвращается непустой fallback

class TestLocalNLPFailureFallback(BaseTest):
    async def test_local_nlp_failure_returns_text_fallback(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = _rate_limit_exc

        failing_local = AsyncMock(side_effect=Exception("local error"))

        with (
            patch("ai_agent._get_client", return_value=mock_client),
            patch("lumena.get_lumena_response", failing_local),
        ):
            result = await ai_agent.lumena_reply(4, "Dave", "Привет")

        # Должен вернуться непустой текстовый фоллбэк, а не None
        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)
        self.assertIn(result, ai_agent._FALLBACKS)


# ── Тест 5: клиент не настроен → сразу локальный NLP ────────────────────

class TestNoClientFallsToLocal(BaseTest):
    async def test_no_client_uses_local_nlp(self):
        local_mock = AsyncMock(return_value="Без Gemini")

        with (
            patch("ai_agent._get_client", return_value=None),
            patch("lumena.get_lumena_response", local_mock),
        ):
            result = await ai_agent.lumena_reply(5, "Eve", "Тест")

        self.assertEqual(result, "Без Gemini")


if __name__ == "__main__":
    unittest.main()
