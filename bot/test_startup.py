"""Offline regressions for Telegram profile rate limits during worker startup."""
import asyncio
import importlib.util
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent))
spec = importlib.util.spec_from_file_location("aurelia_runtime", Path(__file__).with_name("bot.py"))
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class LanguagePickerTests(unittest.TestCase):
    def test_language_picker_lists_every_supported_native_name(self):
        from interface import Interface
        from translations import LANGUAGES

        state = SimpleNamespace(
            raw={"aurelia_accounts": {}},
            account=lambda uid: {"language": "en"},
            balance=lambda uid: 0,
            get=lambda table, uid, default=0: default,
        )
        ui = Interface(state, "test-token", "AureliaBot")
        _, keyboard = ui.screen(42, "language")
        buttons = [button for row in keyboard.inline_keyboard for button in row]
        choices = [button for button in buttons
                   if button.callback_data.split(":")[2].startswith("lang_")]
        self.assertEqual(
            {button.callback_data.split(":")[2][5:] for button in choices},
            set(LANGUAGES),
        )
        self.assertEqual(
            {button.text.removesuffix(" ✓") for button in choices},
            {f"{flag} {name}" for flag, name in LANGUAGES.values()},
        )


class StartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_unchanged_identity_is_not_written(self):
        bot = SimpleNamespace(
            get_my_commands=AsyncMock(return_value=[]),
            set_my_commands=AsyncMock(),
            get_my_name=AsyncMock(return_value=SimpleNamespace(name="AURELIA")),
            set_my_name=AsyncMock(),
            get_my_description=AsyncMock(),
            get_my_short_description=AsyncMock(),
            set_my_description=AsyncMock(),
            set_my_short_description=AsyncMock(),
        )
        bot.get_my_description.side_effect = lambda **kw: SimpleNamespace(
            description="✦ AURELIA\n\n" + runtime.translate(
                "Community, identity and rewards. AI coming soon.", kw.get("language_code")))
        bot.get_my_short_description.side_effect = lambda **kw: SimpleNamespace(
            short_description="✦ AURELIA — " + runtime.translate(
                "Community, identity and rewards. AI coming soon.", kw.get("language_code")))
        await runtime.configure_identity(bot)
        bot.set_my_name.assert_not_awaited()
        bot.set_my_description.assert_not_awaited()
        bot.set_my_short_description.assert_not_awaited()
        menus = [call.args or call.kwargs for call in bot.set_my_commands.await_args_list]
        self.assertEqual(len(menus), 20)

    async def test_profile_failure_does_not_stop_polling(self):
        from aiogram.exceptions import TelegramRetryAfter
        from aiogram.methods import SetMyName
        from aiogram import Router

        state = SimpleNamespace(close=AsyncMock(), due_daily_notices=AsyncMock(return_value=[]))
        bot = SimpleNamespace(get_me=AsyncMock(return_value=SimpleNamespace(username="AureliaBot")),
                              session=SimpleNamespace(close=AsyncMock()))
        dispatcher = SimpleNamespace(include_router=lambda router: None)
        async def polling(*args, **kwargs):
            await asyncio.sleep(0)
            await asyncio.sleep(0)
        dispatcher.start_polling = AsyncMock(side_effect=polling)
        failure = TelegramRetryAfter(method=SetMyName(name="AURELIA"),
                                     message="Flood control", retry_after=86400)
        with patch.dict("os.environ", {"BOT_TOKEN": "offline"}), \
             patch.object(runtime.State, "open", AsyncMock(return_value=state)), \
             patch.object(runtime, "Bot", return_value=bot), \
             patch.object(runtime, "Interface", return_value=SimpleNamespace(router=Router())), \
             patch.object(runtime, "Dispatcher", return_value=dispatcher), \
             patch.object(runtime, "configure_identity", AsyncMock(side_effect=failure)), \
             self.assertLogs(level="ERROR"):
            await runtime.main()
        dispatcher.start_polling.assert_awaited_once()
        state.close.assert_awaited_once()
        bot.session.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()