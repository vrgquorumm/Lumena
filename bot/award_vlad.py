"""
Единоразовая выдача монет @VladMish11.
Запускается автоматически при старте бота один раз.
"""
import asyncio
import os

FLAG_FILE = "data/vlad_awarded.flag"
TARGET_USERNAME = "VladMish11"
AMOUNT = 300_000_000_000_000   # 300 триллионов


async def run_award(bot, chat_members, add_balance, fmt_lmn, save_data, ChatMemberStatus):
    """Вызывается из main() один раз после запуска polling."""
    if os.path.exists(FLAG_FILE):
        return  # уже выдавали — не повторяем

    await asyncio.sleep(4)  # ждём пока polling стартует

    awarded = False

    for chat_id in list(chat_members.keys()):
        try:
            admins = await bot.get_chat_administrators(chat_id)
        except Exception:
            continue

        target_id = None
        target_name = TARGET_USERNAME

        for a in admins:
            if (a.user.username or "").lower() == TARGET_USERNAME.lower():
                target_id = a.user.id
                target_name = a.user.full_name
                break

        if not target_id:
            continue

        add_balance(target_id, AMOUNT)
        chat_members.setdefault(chat_id, {})[target_id] = target_name
        save_data()

        mention = f'<a href="tg://user?id={target_id}">{target_name}</a>'
        try:
            await bot.send_message(
                chat_id,
                f"🏆 {mention} — за лучшую роль клоуна!\n"
                f"💰 Начислено: <b>{fmt_lmn(AMOUNT)} LMN</b> 🎉",
                parse_mode="HTML"
            )
            awarded = True
            print(f"✅ Монеты выданы @{TARGET_USERNAME} в чате {chat_id}")
        except Exception as e:
            print(f"⚠️ Не удалось отправить в чат {chat_id}: {e}")

    # Ставим флаг чтобы не повторять при следующих рестартах
    if awarded:
        os.makedirs("data", exist_ok=True)
        with open(FLAG_FILE, "w") as f:
            f.write("done")
