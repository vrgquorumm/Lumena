"""Authoritative AURELIA state on the existing bot_store.bot_data JSONB row.

No startup migrations, defaults written on boot, or fallback copies. Unknown legacy
fields are retained verbatim for other consumers; only AURELIA fields are changed.
"""
import asyncio
import copy
import json
import os
import secrets
import ssl
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo

import asyncpg

CAP = 7_000_000_000_000
KYIV = ZoneInfo("Europe/Kyiv")
FIELDS = ("aurelia_accounts", "known_users", "lmn_balances", "user_xp",
          "daily_cooldown", "tasks_bonus_cd", "referrals", "referral_counts",
          "daily_msg_cnt", "user_achievements", "profiles", "bank_balances",
          "bank_term_deposits", "streaks", "verified_users", "auction_state")


class StateError(RuntimeError):
    pass


def _make_ssl(url):
    """Encrypted TLS; Railway's proxy uses a self-signed certificate."""
    parsed = urlparse(url)
    if any(value.lower() == "disable" for value in parse_qs(parsed.query).get("sslmode", [])):
        raise StateError("Plaintext PostgreSQL connections are not allowed")
    context = ssl.create_default_context()
    host = (parsed.hostname or "").lower()
    if (host == "railway.internal" or host.endswith(".railway.internal") or
            host.endswith(".proxy.rlwy.net")):
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


def _holdings(d, uid):
    """Aggregate wallet, bank, term deposit and refundable legacy auction escrow."""
    key = str(uid)
    wallet = max(0, int(d.get("lmn_balances", {}).get(key, 0) or 0))
    bank = max(0, int(d.get("bank_balances", {}).get(key, 0) or 0))
    term = d.get("bank_term_deposits", {}).get(key) or {}
    if not isinstance(term, dict):
        raise StateError("Malformed term deposit")
    principal = max(0, int(term.get("principal", 0) or 0))
    auction = d.get("auction_state") or {}
    if not isinstance(auction, dict):
        raise StateError("Malformed auction state")
    active = auction.get("active") or {}
    if not isinstance(active, dict):
        raise StateError("Malformed auction escrow")
    participants = active.get("participants") or {}
    if not isinstance(participants, dict):
        raise StateError("Malformed auction participants")
    entry = participants.get(key) or {}
    if not isinstance(entry, dict):
        raise StateError("Malformed auction bid")
    escrow = max(0, int(entry.get("bid", 0) or 0))
    return wallet + bank + principal + escrow


def _credit(d, uid, requested):
    key = str(uid)
    balances = d.setdefault("lmn_balances", {})
    wallet = max(0, int(balances.get(key, 0) or 0))
    amount = min(requested, max(0, CAP - _holdings(d, uid)))
    balances[key] = wallet + amount
    return amount


class State:
    def __init__(self, conn, raw):
        if not isinstance(raw, dict):
            raise StateError("bot_data is not a JSON object")
        self.conn = conn
        self.raw = raw
        self.lock = asyncio.Lock()
        self.poisoned = False

    @classmethod
    async def open(cls, url=None):
        url = url or os.getenv("DATABASE_URL")
        if not url:
            raise StateError("DATABASE_URL is required; refusing ephemeral financial state")
        conn = await asyncpg.connect(url, ssl=_make_ssl(url))
        try:
            if not await conn.fetchval(
                "SELECT pg_try_advisory_lock(hashtext($1))", "lumena-bot-singleton"
            ):
                raise StateError("Another bot instance owns bot_data")
            # Never CREATE, migrate, or seed authoritative state at boot.
            row = await conn.fetchrow("SELECT value FROM bot_store WHERE key='bot_data'")
            if row is None:
                raise StateError("bot_data is missing; initialize authoritative state explicitly")
            value = row["value"]
            return cls(conn, json.loads(value) if isinstance(value, str) else value)
        except BaseException:
            await conn.close()
            raise

    async def close(self):
        await self.conn.close()

    def table(self, name):
        if self.poisoned:
            raise StateError("Storage outcome is unknown; restart required")
        value = self.raw.get(name, {})
        if not isinstance(value, dict):
            raise StateError(f"Malformed bot_data.{name}")
        return value

    def get(self, name, uid, default=None):
        return self.table(name).get(str(uid), default)

    def balance(self, uid):
        return int(self.get("lmn_balances", uid, 0))

    def account(self, uid):
        return self.get("aurelia_accounts", uid, {}) or {}

    def verified(self, uid):
        users = self.raw.get("verified_users", [])
        if not isinstance(users, list):
            raise StateError("Malformed bot_data.verified_users")
        return uid in users or str(uid) in users

    async def challenge(self, uid, referrer=None):
        """Captcha attempts and referral candidate survive restarts without a payout."""
        def apply(d):
            a = d.setdefault("aurelia_accounts", {}).setdefault(str(uid), {})
            locked = float(a.get("captcha_locked_until", 0))
            now = datetime.now(KYIV).timestamp()
            if locked > now:
                return None
            nonce = secrets.token_hex(4)
            x, y = secrets.randbelow(9) + 1, secrets.randbelow(9) + 1
            candidate = (referrer if isinstance(referrer, int) and referrer > 0 else
                         a.get("captcha", {}).get("referrer") or a.get("pending_referrer"))
            candidate = int(candidate) if (str(candidate).isascii() and
                                           str(candidate).isdecimal() and
                                           len(str(candidate)) <= 19 and int(candidate) > 0) else None
            a["captcha"] = {"nonce": nonce, "answer": x + y, "x": x, "y": y,
                            "expires": now + 300, "attempts": int(a.get("captcha_attempts", 0)),
                            "referrer": candidate}
            return (nonce, x, y)
        return await self.change(apply)

    async def verify(self, uid, nonce, answer, user):
        """Settle attribution and verification together in one durable snapshot."""
        def apply(d):
            a = d.setdefault("aurelia_accounts", {}).setdefault(str(uid), {})
            challenge = a.get("captcha")
            now = datetime.now(KYIV).timestamp()
            if (not challenge or challenge.get("nonce") != nonce or
                    challenge.get("expires", 0) < now or a.get("captcha_locked_until", 0) > now):
                return ("expired", None)
            if answer != challenge["answer"]:
                attempts = int(challenge.get("attempts", 0)) + 1
                a["captcha_attempts"] = attempts
                a.pop("captcha", None)
                if attempts >= 5:
                    a["captcha_locked_until"] = now + 60
                    a["captcha_attempts"] = 0
                return ("wrong", None)
            a.pop("captcha", None)
            a.pop("captcha_attempts", None)
            a.pop("pending_referrer", None)
            a["verified_by_aurelia"] = True
            verified = d.setdefault("verified_users", [])
            if uid in verified or str(uid) in verified:
                return ("expired", None)
            verified.append(uid)
            known = d.setdefault("known_users", {})
            key = str(uid)
            old = known.get(key, {})
            previously_known = (key in known or key in d.get("lmn_balances", {}) or
                                key in d.get("user_xp", {}) or key in d.get("referrals", {}))
            a["registered"] = True
            referrer = challenge.get("referrer")
            awarded = None
            if (not previously_known and referrer and referrer != uid and
                    str(referrer) in known and
                    not known[str(referrer)].get("deleted") and
                    not d["aurelia_accounts"].get(str(referrer), {}).get("deleted") and
                    (referrer in verified or str(referrer) in verified)):
                refs = d.setdefault("referrals", {})
                refs[key] = referrer
                counts = d.setdefault("referral_counts", {})
                counts[str(referrer)] = int(counts.get(str(referrer), 0)) + 1
                amount = _credit(d, referrer, 1000)
                xp = d.setdefault("user_xp", {})
                xp[str(referrer)] = int(xp.get(str(referrer), 0)) + 100
                d["aurelia_accounts"].setdefault(str(referrer), {}).setdefault("ledger", []).append(
                    {"date": datetime.now(KYIV).date().isoformat(), "amount": amount, "reason": "Referral"})
                awarded = (referrer, amount)
            known[key] = {**old, "username": user.username or "",
                          "full_name": user.full_name or "", "private_started": True}
            return ("verified", awarded)
        return await self.change(apply)

    async def change(self, fn):
        """Commit first, publish in-memory copy only on durable success."""
        async with self.lock:
            if self.poisoned:
                raise StateError("Storage outcome is unknown; restart and restore before writing")
            draft = copy.deepcopy(self.raw)
            result = fn(draft)
            try:
                status = await self.conn.execute(
                    "UPDATE bot_store SET value=$1::jsonb, updated_at=NOW() "
                    "WHERE key='bot_data'", json.dumps(draft, ensure_ascii=False)
                )
                if status != "UPDATE 1":
                    raise StateError("bot_data disappeared; change not committed")
            except Exception as exc:
                # The server may have committed just before the connection dropped.
                # Never overwrite that possibly newer snapshot with stale local data.
                self.poisoned = True
                raise StateError("Authoritative bot_data write failed") from exc
            self.raw = draft
            return result

    async def register(self, user, referrer=None, private=False):
        uid = user.id
        if not self.verified(uid):
            raise StateError("Complete private verification before registration")
        def apply(d):
            accounts = d.setdefault("aurelia_accounts", {})
            known = d.setdefault("known_users", {})
            key = str(uid)
            old = known.get(key, {})
            account = accounts.setdefault(key, {})
            previously_known = key in known or key in d.get("lmn_balances", {}) or key in d.get("user_xp", {})
            # Deleted accounts keep their registration marker and attribution forever.
            if not account.get("registered"):
                account["registered"] = True
                ref_key = str(referrer)
                if (not previously_known and private and referrer != uid and ref_key in known
                        and self.verified(referrer)
                        and not old.get("deleted") and not known[ref_key].get("deleted")
                        and not accounts.get(ref_key, {}).get("deleted") and referrer is not None
                        and key not in d.setdefault("referrals", {})):
                    d["referrals"][key] = referrer
                    counts = d.setdefault("referral_counts", {})
                    counts[ref_key] = int(counts.get(ref_key, 0)) + 1
                    amount = _credit(d, referrer, 1000)
                    xp = d.setdefault("user_xp", {})
                    xp[ref_key] = int(xp.get(ref_key, 0)) + 100
                    accounts.setdefault(ref_key, {}).setdefault("ledger", []).append(
                        {"date": datetime.now(KYIV).date().isoformat(), "amount": amount, "reason": "Referral"})
                    referred = referrer
                else:
                    referred = None
            else:
                referred = None
            if not account.get("deleted"):
                known[key] = {**old, "username": user.username or "",
                              "full_name": user.full_name or "",
                              "private_started": bool(private or old.get("private_started"))}
                if private:
                    account.pop("daily_notice_blocked", None)
            return referred
        return await self.change(apply)

    async def record_message(self, uid, chat_id, message_id):
        stamp = datetime.now(KYIV).date().isoformat()
        def apply(d):
            a = d.setdefault("aurelia_accounts", {}).setdefault(str(uid), {})
            seen = a.setdefault("recent_messages", [])
            marker = f"{chat_id}:{message_id}"
            if marker in seen:
                return
            seen.append(marker)
            del seen[:-100]
            counts = d.setdefault("daily_msg_cnt", {})
            entry = counts.get(str(uid), {})
            counts[str(uid)] = {"date": stamp,
                                "count": (int(entry.get("count", 0)) if entry.get("date") == stamp else 0) + 1}
        await self.change(apply)

    async def claim_quests(self, uid):
        today = datetime.now(KYIV).date().isoformat()
        def apply(d):
            key = str(uid)
            a = d.setdefault("aurelia_accounts", {}).setdefault(key, {})
            count = d.get("daily_msg_cnt", {}).get(key, {})
            if (d.setdefault("tasks_bonus_cd", {}).get(key) == today or
                    count.get("date") != today or int(count.get("count", 0)) < 10 or
                    d.get("daily_cooldown", {}).get(key) != today or
                    int(a.get("streak", 0)) < 3):
                return None
            amount = _credit(d, uid, 1000)
            xp = d.setdefault("user_xp", {})
            xp[key] = int(xp.get(key, 0)) + 75
            d["tasks_bonus_cd"][key] = today
            a.setdefault("ledger", []).append({"date": today, "amount": amount,
                                                "reason": "Quest completion"})
            return amount
        return await self.change(apply)

    async def claim_daily(self, uid, day=None):
        today = day or datetime.now(KYIV).date()
        stamp = today.isoformat()
        def apply(d):
            key = str(uid)
            cooldown = d.setdefault("daily_cooldown", {})
            if cooldown.get(key) == stamp:
                return None
            account = d.setdefault("aurelia_accounts", {}).setdefault(key, {})
            streak = int(account.get("streak", 0)) + 1 if account.get("last_daily") == (today - timedelta(days=1)).isoformat() else 1
            # The old reward used a 500..2000 base; do not advertise concept mock 25.
            reward = 500 + secrets.randbelow(1501)
            amount = _credit(d, uid, reward)
            xp = d.setdefault("user_xp", {})
            xp[key] = int(xp.get(key, 0)) + 50
            cooldown[key] = stamp
            account.update(last_daily=stamp, streak=streak,
                           best=max(streak, int(account.get("best", 0))),
                           daily_earned=int(account.get("daily_earned", 0)) + amount)
            account.setdefault("ledger", []).append({"date": stamp, "amount": amount, "reason": "Daily reward"})
            return amount
        return await self.change(apply)

    async def due_daily_notices(self, day=None):
        """Return due users without claiming delivery; only Telegram acknowledgements count."""
        stamp = (day or datetime.now(KYIV).date()).isoformat()
        async with self.lock:
            if self.poisoned:
                raise StateError("Storage outcome is unknown; restart required")
            due = []
            for key, user in self.table("known_users").items():
                if not isinstance(user, dict) or not user.get("private_started"):
                    continue
                account = self.table("aurelia_accounts").get(key, {})
                delivery = account.get("daily_delivery", {})
                if (account.get("deleted") or
                        not account.get("notifications", {}).get("daily", False) or
                        self.table("daily_cooldown").get(key) == stamp or
                        (account.get("daily_notice_day") == stamp and
                         delivery.get("status") == "sent" and delivery.get("day") == stamp) or
                        account.get("daily_notice_blocked") or
                        (delivery.get("day") == stamp and
                         float(delivery.get("retry_after", 0)) > datetime.now(KYIV).timestamp())):
                    continue
                due.append(int(key))
            return due

    async def record_daily_notice(self, uid, status, day=None, error=""):
        """Acknowledge after send; failures retry. Telegram and PG have no joint
        transaction: a crash after Telegram accepts but before this commit may
        cause one duplicate reminder, never a falsely acknowledged unsent one.
        """
        stamp = (day or datetime.now(KYIV).date()).isoformat()
        if status not in ("sent", "retry", "blocked"):
            raise ValueError("Unknown notification delivery status")
        def apply(d):
            account = d.setdefault("aurelia_accounts", {}).setdefault(str(uid), {})
            attempts = int(account.get("daily_delivery", {}).get("attempts", 0)) + 1
            account["daily_delivery"] = {
                "day": stamp, "status": status, "attempts": attempts,
                "error": str(error)[:200],
                "retry_after": datetime.now(KYIV).timestamp() + min(3600, 60 * 2 ** min(attempts, 6))
                if status == "retry" else 0}
            if status == "sent":
                account["daily_notice_day"] = stamp
            if status == "blocked":
                account["daily_notice_blocked"] = True
        await self.change(apply)

    async def prepare_send(self, uid, recipient, amount):
        if uid == recipient or amount <= 0 or recipient not in (
                int(key) for key in self.table("known_users")):
            return None
        nonce = secrets.token_hex(12)
        def apply(d):
            balances = d.setdefault("lmn_balances", {})
            if int(balances.get(str(uid), 0)) < amount or _holdings(d, recipient) + amount > CAP:
                return None
            d.setdefault("aurelia_accounts", {}).setdefault(str(uid), {})["pending_send"] = {
                "nonce": nonce, "recipient": recipient, "amount": amount,
                "expires": datetime.now(KYIV).timestamp() + 300}
            return nonce
        return await self.change(apply)

    async def confirm_send(self, uid, nonce):
        def apply(d):
            account = d.setdefault("aurelia_accounts", {}).setdefault(str(uid), {})
            pending = account.get("pending_send")
            if not pending or pending.get("nonce") != nonce:
                return False
            account.pop("pending_send")
            dest = int(pending["recipient"])
            amount = int(pending["amount"])
            balances = d.setdefault("lmn_balances", {})
            if (datetime.now(KYIV).timestamp() > pending["expires"] or dest == uid or amount <= 0
                    or int(balances.get(str(uid), 0)) < amount or
                    _holdings(d, dest) + amount > CAP):
                return False
            balances[str(uid)] = int(balances.get(str(uid), 0)) - amount
            balances[str(dest)] = int(balances.get(str(dest), 0)) + amount
            stamp = datetime.now(KYIV).date().isoformat()
            account.setdefault("ledger", []).append({"date": stamp, "amount": -amount, "reason": f"Send to #{dest}"})
            d["aurelia_accounts"].setdefault(str(dest), {}).setdefault("ledger", []).append(
                {"date": stamp, "amount": amount, "reason": f"Received from #{uid}"})
            return True
        return await self.change(apply)

    async def delete(self, uid):
        def apply(d):
            key = str(uid)
            a = d.setdefault("aurelia_accounts", {}).setdefault(key, {})
            retained = {k: a[k] for k in ("ledger", "last_daily", "streak", "best", "daily_earned")
                        if k in a}
            d["aurelia_accounts"][key] = {**retained, "registered": True, "deleted": True}
            d.setdefault("known_users", {})[key] = {
                "username": "", "full_name": "", "private_started": True, "deleted": True}
            d.setdefault("profiles", {}).pop(key, None)
            d.setdefault("psych_profiles", {}).pop(key, None)
        await self.change(apply)