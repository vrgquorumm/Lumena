"""Одноразове оголошення про оновлення анкет — надсилається в чат адміністрації при старті."""
import os
import anketa as _ank

FLAG = "data/announce_anketa2.flag"


async def run_announce(bot):
    # Анонс уже был отправлен — отключено
    return
