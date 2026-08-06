#!/usr/bin/env bash
# ── LUMENA startup script ──────────────────────────────────────────────────
# Railway запускає цей скрипт.
# site_server.py → слухає $PORT (Railway відкриває його як HTTP endpoint).
# bot.py         → long polling, окремий процес у фоні.
# --------------------------------------------------------------------------
set -euo pipefail

echo "🚀 LUMENA: запуск сайту та бота..."

# Бот у фоні
python bot.py &
BOT_PID=$!
echo "🤖 Bot PID=$BOT_PID"

# Сайт — основний процес (прив'язує $PORT, Railway бачить HTTP)
python site_server.py

# Якщо сайт впав — завершуємо і бот (Railway перезапустить увесь сервіс)
echo "⚠️  site_server завершився — зупиняємо бота..."
kill "$BOT_PID" 2>/dev/null || true
