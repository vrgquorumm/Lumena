"""
Railway entry point — запускает бот из bot/
"""
import os
import sys

# Переходим в bot/ чтобы все относительные пути (data/, и т.д.) работали
bot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot")
os.chdir(bot_dir)
sys.path.insert(0, bot_dir)

# Запускаем бот
import asyncio
from bot import main

if __name__ == "__main__":
    asyncio.run(main())
