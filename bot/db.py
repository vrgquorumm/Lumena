"""PostgreSQL persistence layer for Lumena Bot.

Використовує одну key-value таблицю (bot_store) для зберігання всіх даних бота
у вигляді JSONB. Якщо DATABASE_URL не задано — автоматично падає на GitHub-fallback.

Ключі:
  bot_data         — весь стан бота (streaks, marriages, balances, aura…)
  anketa_users     — статуси юзерів анкети
  anketa_settings  — mod_chat_id, pub_chat_id, counter, chat_link
  custom_texts     — кастомні тексти бренду
  custom_style     — кастомний стиль бренду
  custom_buttons   — кастомні кнопки бренду
"""

from __future__ import annotations
import json
import logging
import os
import ssl
from typing import Optional

try:
    import asyncpg  # type: ignore
    _ASYNCPG_OK = True
except ImportError:
    _ASYNCPG_OK = False

_pool: "asyncpg.Pool | None" = None  # type: ignore
_instance_lock_conn = None
_INSTANCE_LOCK_NAME = "lumena-bot-singleton"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS bot_store (
    key        TEXT PRIMARY KEY,
    value      JSONB        NOT NULL,
    updated_at TIMESTAMPTZ  DEFAULT NOW()
)
"""

_UPSERT = """
INSERT INTO bot_store (key, value, updated_at)
VALUES ($1, $2::jsonb, NOW())
ON CONFLICT (key) DO UPDATE
    SET value      = EXCLUDED.value,
        updated_at = NOW()
"""



def _make_ssl(url: str) -> "ssl.SSLContext | bool | None":
    """Повертає SSL-налаштування для asyncpg.

    Railway (як внутрішній railway.internal, так і публічний *.proxy.rlwy.net)
    термінує TLS самопідписаним сертифікатом, тому повна перевірка ланцюжка/
    hostname тут завжди провалюється ("self-signed certificate in certificate
    chain"). З'єднання лишається зашифрованим, просто без перевірки CA.
    """
    if "sslmode=disable" in url:
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


async def init_db() -> bool:
    """Ініціалізує connection pool та схему БД.
    Повертає True якщо PostgreSQL доступний, False — якщо ні.
    """
    global _pool, _instance_lock_conn
    if not _ASYNCPG_OK:
        print("⚠️ asyncpg не встановлено — PostgreSQL вимкнено, використовується GitHub")
        return False

    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        print("ℹ️ DATABASE_URL не задано — PostgreSQL вимкнено, використовується GitHub")
        return False

    ssl_arg = _make_ssl(db_url)
    try:
        pool = await asyncpg.create_pool(
            db_url,
            min_size=1,
            max_size=5,
            command_timeout=15,
            ssl=ssl_arg,
        )
        async with pool.acquire() as conn:
            await conn.execute(_CREATE_TABLE)
        # Не допускаем второй рабочий процесс с тем же DATABASE_URL.
        # Иначе два polling-инстанса читают разные snapshots и последний
        # autosave может вернуть балансы к устаревшему состоянию.
        lock_conn = await pool.acquire()
        locked = await lock_conn.fetchval(
            "SELECT pg_try_advisory_lock(hashtext($1))",
            _INSTANCE_LOCK_NAME,
        )
        if not locked:
            await pool.release(lock_conn)
            await pool.close()
            raise RuntimeError(
                "Другой экземпляр Lumena уже использует PostgreSQL "
                "(advisory lock lumena-bot-singleton)"
            )
        _instance_lock_conn = lock_conn
        _pool = pool
        print("✅ PostgreSQL підключено, таблиця bot_store готова")
        print("🔒 Получена блокировка единственного экземпляра Lumena")
        return True
    except RuntimeError:
        raise
    except Exception as e:
        logging.warning(f"⚠️ Не вдалося підключитись до PostgreSQL: {e}")

    print("⚠️ PostgreSQL недоступний — дані НЕ будуть збережено надійно між перезапусками")
    return False


def has_pg() -> bool:
    """True якщо connection pool активний."""
    return _pool is not None


async def db_get(key: str) -> dict | None:
    """Отримує JSON-об'єкт з БД за ключем.
    Повертає None якщо ключ не знайдено або БД недоступна.
    """
    if not _pool:
        return None
    try:
        async with _pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT value FROM bot_store WHERE key = $1", key
            )
        if not row:
            return None
        val = row["value"]
        return json.loads(val) if isinstance(val, str) else dict(val)
    except Exception as e:
        logging.warning(f"db_get({key!r}): {e}")
        return None


async def db_set(key: str, data: dict) -> bool:
    """Upsert JSON-об'єкта в БД.
    Повертає True при успіху, False при помилці.
    """
    if not _pool:
        return False
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                _UPSERT,
                key,
                json.dumps(data, ensure_ascii=False, default=str),
            )
        return True
    except Exception as e:
        logging.warning(f"db_set({key!r}): {e}")
        return False


async def db_set_raw(key: str, raw_bytes: bytes) -> bool:
    """Зберігає raw JSON bytes (без повторної серіалізації)."""
    if not _pool:
        return False
    try:
        data = json.loads(raw_bytes)
        return await db_set(key, data)
    except Exception as e:
        logging.warning(f"db_set_raw({key!r}): {e}")
        return False


async def db_set_many(records: list[tuple[str, dict]]) -> bool:
    """Зберігає кілька ключів в одній транзакції PostgreSQL.
    records: list of (key, data) pairs.
    Повертає True якщо всі записи збережено, False при будь-якій помилці.
    """
    if not _pool:
        return False
    try:
        async with _pool.acquire() as conn:
            async with conn.transaction():
                for key, data in records:
                    await conn.execute(
                        _UPSERT,
                        key,
                        json.dumps(data, ensure_ascii=False, default=str),
                    )
        return True
    except Exception as e:
        logging.warning(f"db_set_many: {e}")
        return False


async def close_db() -> None:
    """Закриває connection pool."""
    global _pool, _instance_lock_conn
    if _pool:
        if _instance_lock_conn:
            await _pool.release(_instance_lock_conn)
            _instance_lock_conn = None
        await _pool.close()
        _pool = None
        print("🔒 PostgreSQL з'єднання закрито")

# ── Aliases for callers using save_kv / load_kv ──────────────
async def save_kv(key: str, data: dict) -> bool:
    """Alias for db_set — зберігає JSON у bot_store."""
    return await db_set(key, data)

async def load_kv(key: str) -> Optional[dict]:
    """Alias for db_get — завантажує JSON з bot_store."""
    return await db_get(key)
