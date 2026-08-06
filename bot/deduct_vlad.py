"""
Единоразовое снятие монет у @VladMish11 — оставить ровно 50 000 000.
Запускается автоматически при старте бота один раз.
"""
import asyncio
import os

FLAG_FILE = "data/vlad_deducted.flag"
TARGET_USERNAME = "VladMish11"
LEAVE_AMOUNT = 50_000_000   # оставить 50 млн


async def run_deduct(bot, chat_members, lmn_balances, fmt_lmn, save_data, ChatMemberStatus):
    return  # выполнено — отключено

    await asyncio.sleep(4)

    done = False

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

        # Устанавливаем баланс ровно 50 млн
        lmn_balances[target_id] = LEAVE_AMOUNT
        save_data()

        mention = f'<a href="tg://user?id={target_id}">{target_name}</a>'
        try:
            await bot.send_message(
                chat_id,
                f"😏 {mention}, Владосик, не наглей)\n"
                f"💸 Баланс урезан до <b>{fmt_lmn(LEAVE_AMOUNT)} LMN</b>",
                parse_mode="HTML"
            )
            done = True
            print(f"✅ Монеты срезаны у @{TARGET_USERNAME} в чате {chat_id}")
        except Exception as e:
            print(f"⚠️ Не удалось отправить в чат {chat_id}: {e}")

    if done:
        os.makedirs("data", exist_ok=True)
        with open(FLAG_FILE, "w") as f:
            f.write("done")
