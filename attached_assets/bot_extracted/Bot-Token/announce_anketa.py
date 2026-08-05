"""Одноразове оголошення про оновлення анкет — надсилається в чат адміністрації при старті."""
import os
import anketa as _ank

FLAG = "data/announce_anketa2.flag"


async def run_announce(bot):
    if os.path.exists(FLAG):
        return

    # Надсилаємо в чат модерації (адміністрації) якщо він налаштований
    mod_chat = _ank.get_mod_chat()
    if not mod_chat:
        return  # Чат ще не налаштовано — пропускаємо

    try:
        await bot.send_message(
            mod_chat,
            "🆕 <b>Апдейт: переработаны анкеты</b>\n\n"
            "Теперь это анкеты знайомств 💌\n\n"
            "• Юзер пише /анкета боту в особисті\n"
            "• Заповнює 7 питань (ім'я, вік, місто, про себе, інтереси, що шукає, соцмережі)\n"
            "• Анкета надходить сюди на модерацію\n"
            "• ✅ Прийняти → публікується в чат знайомств\n"
            "• ❌ Відхилити → автор отримує повідомлення\n"
            "• ✏️ Правки → пишеш наступним повідомленням, воно йде автору\n\n"
            "Не забудь налаштувати чат публікацій: /setpubchat (в потрібному чаті)",
            parse_mode="HTML"
        )
        with open(FLAG, "w") as f:
            f.write("done")
    except Exception as e:
        print(f"announce_anketa: {e}")
