#!/usr/bin/env bash
# ── LUMENA startup script ──────────────────────────────────────────────────
# Railway запускає цей скрипт.
# site_server.py → слухає $PORT (Railway відкриває його як HTTP endpoint).
# bot.py         → long polling, окремий процес у фоні.
# --------------------------------------------------------------------------
set -euo pipefail

echo "🚀 LUMENA: запуск сайту та бота..."

# Бот и сайт работают параллельно. Если любой из них завершится,
# закрываем второй процесс и отдаём ненулевой код Railway.
# Это важно для advisory-lock: при кратком handoff-конфликте Railway
# должен перезапустить контейнер, а не оставить сайт без polling-бота.
python bot.py &
BOT_PID=$!
echo "🤖 Bot PID=$BOT_PID"

python site_server.py &
SITE_PID=$!
echo "🌐 Site PID=$SITE_PID"

cleanup() {
  kill "$BOT_PID" "$SITE_PID" 2>/dev/null || true
}
trap cleanup EXIT TERM INT

set +e
wait -n "$BOT_PID" "$SITE_PID"
EXIT_STATUS=$?
set -e

if ! kill -0 "$BOT_PID" 2>/dev/null; then
  echo "⚠️  bot.py завершился — перезапускаем контейнер..."
  kill "$SITE_PID" 2>/dev/null || true
  exit 1
fi

echo "⚠️  site_server завершился — перезапускаем контейнер..."
kill "$BOT_PID" 2>/dev/null || true
exit "${EXIT_STATUS:-1}"
