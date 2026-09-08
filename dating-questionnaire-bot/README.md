# Lumenora Dating Bot

Separate Telegram bot for 18+ dating profiles:

- guided questionnaire with age gate;
- optional profile photo;
- gender and preference filters;
- like/skip discovery;
- mutual matches;
- profile pause, resume, and editing.
- VIP access for 100 Telegram Stars for 30 days;
- VIP profile badge, boosted discovery priority, and a 24-hour profile boost.

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATING_BOT_TOKEN="..."
python bot.py
```

The default database is `data/dating.sqlite3`. On Railway, mount a persistent
volume at `/data`, otherwise the SQLite database will reset on a redeploy.

## VIP and Telegram Stars

Users can open `/vip` or press the `⭐ VIP` button after creating a profile.
The bot sends a native Telegram Stars invoice for **100 XTR**. VIP is activated
only after Telegram sends a confirmed successful payment update and lasts 30
days. Active VIP users can press `🚀 Поднять анкету` to move their profile to
the priority part of discovery for 24 hours.

Telegram Stars payments do not use a provider token or an external payment
processor. Keep the bot token private and use a persistent Railway volume so
VIP status and profiles survive redeploys.

## Railway

Create a Railway service from this repository, add the secret
`DATING_BOT_TOKEN`, and mount a volume at `/data`. The included Dockerfile and
`railway.toml` start the long-running polling worker.