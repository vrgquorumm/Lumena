"""Тести AI-режимів Lumena: Terra та безпечний локальний fallback.

Запуск:
    python -m unittest test_ai_agent.py
"""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import ai_agent


class TestTerraIntegration(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        ai_agent._mems.clear()

    @patch.dict(os.environ, {}, clear=True)
    async def test_no_key_uses_local_reply(self):
        reply = await ai_agent.lumena_reply(1, "Alice", "Привіт")
        self.assertTrue(reply)
        self.assertIsInstance(reply, str)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True)
    @patch("ai_agent._create_terra_client")
    async def test_terra_response_is_returned(self, mock_client):
        completion = AsyncMock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Відповідь Terra"))]
        ))
        mock_client.return_value.chat.completions.create = completion

        reply = await ai_agent.lumena_reply(2, "Bob", "Поясни щось складне")

        self.assertEqual(reply, "Відповідь Terra")
        self.assertEqual(completion.await_count, 1)
        self.assertEqual(completion.call_args.kwargs["model"], "gpt-5.6-terra")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True)
    @patch("ai_agent._create_terra_client")
    async def test_terra_error_falls_back_to_local_reply(self, mock_client):
        mock_client.return_value.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("provider unavailable")
        )

        reply = await ai_agent.lumena_reply(3, "Carol", "Привіт")

        self.assertTrue(reply)
        self.assertNotIn("provider unavailable", reply)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True)
    @patch("ai_agent._create_terra_client")
    async def test_terra_timeout_falls_back_to_local_reply(self, mock_client):
        async def slow_response(**_kwargs):
            await __import__("asyncio").sleep(0.1)

        mock_client.return_value.chat.completions.create = slow_response
        with patch.object(ai_agent, "_TERRA_TIMEOUT_SECONDS", 0.01):
            reply = await ai_agent.lumena_reply(4, "Dana", "Привіт")

        self.assertTrue(reply)


if __name__ == "__main__":
    unittest.main()