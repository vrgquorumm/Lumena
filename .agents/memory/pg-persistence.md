---
name: PostgreSQL persistence — operational decision
description: Why and how bot data is persisted; what breaks if DATABASE_URL is missing
---

## Decision
Bot data (streaks, marriages, balances, aura, brand customizations, anketa settings) is persisted in Railway PostgreSQL via asyncpg. GitHub API write calls are removed; they caused 409 conflicts and silently lost data on container restarts.

**Why:** Railway kills containers mid-push; GitHub API has race conditions on concurrent writes. PostgreSQL on Railway is durable across restarts.

## Failure mode (no DATABASE_URL)
When `DATABASE_URL` is absent or PostgreSQL is unreachable, the bot starts from the local JSON file (ephemeral container disk) and logs a clear warning that data will be lost on restart. It does **not** silently claim success. This is intentional — task #17 addresses making startup fail explicitly.

## SSL posture
Only verified TLS (system CA, full hostname check) — no plaintext fallback on cert failure. Explicitly disabled only when DATABASE_URL contains `sslmode=disable`.

## Restore semantics
`db_get()` returning `{}` (empty dict) is treated as authoritative data (intentionally cleared state), not as "missing" — uses `is not None` not truthiness checks throughout the restore chain.
