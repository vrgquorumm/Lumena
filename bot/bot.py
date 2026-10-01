"""Standalone AURELIA Telegram worker. No legacy bot imports or boot migrations."""
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.types import (
    BotCommand, BotCommandScopeDefault, BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats, BotCommandScopeChat,
)

from interface import Interface
from state import State
from translations import translate


async def configure_identity(bot, main_chat=None):
    """Replace legacy menus at each formerly configured scope and locale."""
    menu = [BotCommand(command=k, description=v) for k, v in (
        ("start", "✦ AURELIA"), ("home", "⌂ Home"),
        ("profile", "👤 Profile"), ("rewards", "🎁 Rewards"),
        ("social", "🌐 Social"), ("wallet", "💎 Wallet"),
        ("app", "📱 App"), ("help", "✦ Help"))]
    main_chat = main_chat if main_chat is not None else int(os.getenv("MAIN_CHAT_ID", "-1004401287309"))
    scopes = (BotCommandScopeDefault(), BotCommandScopeAllPrivateChats(),
              BotCommandScopeAllGroupChats(), BotCommandScopeChat(chat_id=main_chat))
    for scope in scopes:
        for language in (None, "en", "ru", "sl", "uk"):
            localized = [BotCommand(command=cmd.command,
                                    description=translate(cmd.description, language))
                         for cmd in menu]
            current = await bot.get_my_commands(scope=scope, language_code=language)
            if current != localized:
                await bot.set_my_commands(localized, scope=scope, language_code=language)
    if (await bot.get_my_name()).name != "AURELIA":
        await bot.set_my_name(name="AURELIA")
    for language in (None, "en", "ru", "sl"):
        description = translate("Community, identity and rewards. AI coming soon.", language)
        full = f"✦ AURELIA\n\n{description}"
        short = f"✦ AURELIA — {description}"
        if (await bot.get_my_description(language_code=language)).description != full:
            await bot.set_my_description(description=full, language_code=language)
        if (await bot.get_my_short_description(language_code=language)).short_description != short:
            await bot.set_my_short_description(description=short, language_code=language)


async def configure_identity_safely(bot):
    """Cosmetic API failures must never prevent polling or trigger restart loops."""
    try:
        await configure_identity(bot)
    except Exception:
        logging.exception("Telegram profile/menu sync deferred; command polling continues")


async def main():
    token = os.environ["BOT_TOKEN"]
    state = await State.open()
    bot = Bot(token=token)
    reminder_task = None
    identity_task = None
    try:
        identity = await bot.get_me()
        ui = Interface(state, token, identity.username or "")
        dispatcher = Dispatcher()
        dispatcher.include_router(ui.router)
        identity_task = asyncio.create_task(configure_identity_safely(bot))
        async def reminders():
            while True:
                try:
                    due = await state.due_daily_notices()
                    for uid in due:
                        if await ui.notice(
                                bot, uid, "daily",
                                translate("🎁 Your daily reward is available. Open /daily to claim.",
                                          ui.language(uid))):
                            await state.record_daily_notice(uid, "sent")
                except Exception:
                    logging.exception("Daily reminders unavailable; no unsaved state published")
                await asyncio.sleep(60)
        reminder_task = asyncio.create_task(reminders())
        await dispatcher.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        for task in (reminder_task, identity_task):
            if not task:
                continue
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await bot.session.close()
        await state.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())