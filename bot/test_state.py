"""Offline state migration/integration tests; never contacts PostgreSQL or Telegram."""
import asyncio
import copy
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock

sys.path.insert(0, str(Path(__file__).parent))
from state import State, StateError, KYIV, CAP
from interface import Interface, ROUTES, route_for
from translations import translate


class FakeConnection:
    def __init__(self):
        self.payload = None
        self.fail = False
        self.calls = 0

    async def execute(self, sql, value):
        self.calls += 1
        if self.fail:
            raise ConnectionError("storage unavailable")
        import json
        self.payload = json.loads(value)
        return "UPDATE 1"


def person(uid):
    return SimpleNamespace(id=uid, username=f"user{uid}", full_name=f"User {uid}")


class StateTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.conn = FakeConnection()
        self.legacy = {
            "marriages": {"-100": {"10": 20}},
            "lmn_balance_reset_version": 8,
            "lmn_balances": {"10": 4000, "20": 500},
            "bank_balances": {"20": 99},
            "user_xp": {"10": 1234},
            "known_users": {"10": {"username": "user10", "private_started": True},
                            "20": {"username": "user20", "private_started": True}},
            "referrals": {"20": 10},
            "verified_users": [10, 20],
            "referral_counts": {"10": 1},
            "profiles": {"20": {"bio": "old"}},
            "aurelia_accounts": {"20": {"registered": True, "ledger": [
                {"date": "2025-01-01", "amount": 50, "reason": "Referral"}]}}
        }
        self.s = State(self.conn, copy.deepcopy(self.legacy))

    async def test_preserve_legacy_and_existing_finances(self):
        await self.s.register(person(10), referrer=20)
        self.assertEqual(self.s.balance(10), 4000)
        self.assertEqual(self.s.get("user_xp", 10), 1234)
        self.assertEqual(self.s.table("referrals"), {"20": 10})
        self.assertEqual(self.s.raw["marriages"], self.legacy["marriages"])
        self.assertEqual(self.s.raw["lmn_balance_reset_version"], 8)

    async def test_populated_legacy_json_fixture_is_not_reset_or_reinterpreted(self):
        import json
        fixture = json.loads((Path(__file__).parent / "data" / "bot_data.json").read_text())
        self.assertTrue(fixture["verified_users"])
        original = copy.deepcopy(fixture)
        state = State(FakeConnection(), fixture)
        uid = int(fixture["verified_users"][0])
        self.assertTrue(state.verified(uid))
        old_balance = state.balance(uid)
        old_xp = state.get("user_xp", uid)
        await state.register(person(uid), private=True)
        self.assertEqual(state.balance(uid), old_balance)
        self.assertEqual(state.get("user_xp", uid), old_xp)
        for field in ("streaks", "marriages", "roles", "mod_logs", "games_won",
                      "lmn_balance_reset_version", "verified_users", "referrals"):
            if field in original:
                self.assertEqual(state.raw[field], original[field], field)

    async def test_new_referral_only_once_even_after_deletion(self):
        with self.assertRaises(StateError):
            await self.s.register(person(30), 10, True)
        nonce, x, y = await self.s.challenge(30, 10)
        self.assertEqual(await self.s.verify(30, nonce, x + y, person(30)),
                         ("verified", (10, 1000)))
        await self.s.register(person(30), 10, True)
        await self.s.delete(30)
        await self.s.register(person(30), 10, True)
        self.assertEqual(self.s.balance(10), 5000)
        self.assertEqual(self.s.get("referral_counts", 10), 2)
        self.assertEqual(self.s.get("referrals", 30), 10)
        self.assertTrue(self.s.account(30)["deleted"])
        self.assertEqual(self.s.get("known_users", 30)["username"], "")

    async def test_referral_requires_private_verification_and_replay_is_inert(self):
        nonce, x, y = await self.s.challenge(31, 10)
        self.assertEqual((await self.s.verify(31, nonce, x + y + 1, person(31)))[0], "wrong")
        self.assertFalse(self.s.verified(31))
        self.assertEqual(self.s.balance(10), 4000)
        self.assertEqual((await self.s.verify(31, nonce, x + y, person(31)))[0], "expired")
        nonce, x, y = await self.s.challenge(31, 10)
        # Repeated /start must not erase the pending invite before captcha success.
        nonce, x, y = await self.s.challenge(31)
        self.assertEqual(await self.s.verify(31, nonce, x + y, person(31)),
                         ("verified", (10, 1000)))
        self.assertEqual((await self.s.verify(31, nonce, x + y, person(31)))[0], "expired")
        self.assertEqual(self.s.balance(10), 5000)
        self.assertEqual(self.s.get("referrals", 31), 10)

    async def test_reject_unverified_referrer_and_legacy_member_referral(self):
        nonce, x, y = await self.s.challenge(32, 999)
        self.assertEqual(await self.s.verify(32, nonce, x + y, person(32)), ("verified", None))
        self.assertIsNone(self.s.get("referrals", 32))
        # A legacy account with XP is not a new invite even if it verifies now.
        self.s.raw["verified_users"].remove(10)
        nonce, x, y = await self.s.challenge(10, 20)
        self.assertEqual(await self.s.verify(10, nonce, x + y, person(10)), ("verified", None))
        self.assertEqual(self.s.get("referrals", 10), None)

    async def test_daily_concurrent_and_write_failure(self):
        day = datetime.now(KYIV).date()
        first, second = await asyncio.gather(self.s.claim_daily(10, day), self.s.claim_daily(10, day))
        self.assertIsInstance(first, int)
        self.assertIsNone(second)
        self.assertEqual(self.s.get("user_xp", 10), 1284)
        self.conn.fail = True
        before = copy.deepcopy(self.s.raw)
        with self.assertRaises(StateError):
            await self.s.claim_daily(10, day + timedelta(days=1))
        self.assertEqual(self.s.raw, before)

    async def test_transfer_atomic_replay_and_failure(self):
        nonce = await self.s.prepare_send(10, 20, 200)
        writes_before = self.conn.calls
        self.assertTrue(await self.s.confirm_send(10, nonce))
        self.assertEqual(self.conn.calls, writes_before + 1)
        self.assertEqual(self.conn.payload["lmn_balances"]["10"], 3800)
        self.assertEqual(self.conn.payload["lmn_balances"]["20"], 700)
        self.assertFalse(await self.s.confirm_send(10, nonce))
        self.assertEqual((self.s.balance(10), self.s.balance(20)), (3800, 700))
        nonce = await self.s.prepare_send(10, 20, 100)
        before = copy.deepcopy(self.s.raw)
        self.conn.fail = True
        with self.assertRaises(StateError):
            await self.s.confirm_send(10, nonce)
        self.assertEqual(self.s.raw, before)
        self.conn.fail = False
        with self.assertRaises(StateError):
            await self.s.confirm_send(10, nonce)
        # A new process must restore the authoritative row before retrying.
        restored = State(FakeConnection(), before)
        self.assertTrue(await restored.confirm_send(10, nonce))

    async def test_aggregate_cap_daily_quest_referral_and_transfer(self):
        self.s.raw["lmn_balances"]["10"] = CAP - 50
        self.s.raw["bank_balances"]["10"] = 10
        self.s.raw["bank_term_deposits"] = {"10": {"principal": 20}}
        self.s.raw["auction_state"] = {"active": {"participants": {"10": {"bid": 15}}}}
        self.assertEqual(await self.s.claim_daily(10), 5)
        self.assertEqual(self.s.balance(10), CAP - 45)
        self.assertEqual(self.s.get("user_xp", 10), 1284)
        today = datetime.now(KYIV).date().isoformat()
        await self.s.change(lambda d: (
            d["aurelia_accounts"].setdefault("10", {}).update(streak=3),
            d.setdefault("daily_msg_cnt", {}).update({"10": {"date": today, "count": 10}})))
        self.assertEqual(await self.s.claim_quests(10), 0)
        nonce, x, y = await self.s.challenge(40, 10)
        self.assertEqual(await self.s.verify(40, nonce, x + y, person(40)),
                         ("verified", (10, 0)))
        self.assertEqual(self.s.balance(10), CAP - 45)
        # Dest wallet has room, but bank+term+escrow consume the remaining cap.
        self.s.raw["lmn_balances"]["20"] = CAP - 100
        self.s.raw["bank_balances"]["20"] = 25
        self.s.raw["bank_term_deposits"]["20"] = {"principal": 25}
        self.s.raw["auction_state"]["active"]["participants"]["20"] = {"bid": 25}
        self.assertIsNone(await self.s.prepare_send(10, 20, 30))
        nonce = await self.s.prepare_send(10, 20, 20)
        self.assertTrue(nonce)
        await self.s.change(lambda d: d["auction_state"]["active"]["participants"]["20"].update(bid=31))
        self.assertFalse(await self.s.confirm_send(10, nonce))
        self.assertEqual(self.s.balance(10), CAP - 45)

    async def test_quest_requires_real_events_and_deduplicates_messages(self):
        today = datetime.now(KYIV).date().isoformat()
        await self.s.change(lambda d: d.setdefault("aurelia_accounts", {}).setdefault("10", {}).update(
            streak=2, last_daily=(datetime.now(KYIV).date() - timedelta(days=1)).isoformat()))
        await self.s.claim_daily(10)
        for i in range(10):
            await self.s.record_message(10, -100, i)
        await self.s.record_message(10, -100, 9)
        self.assertEqual(self.s.get("daily_msg_cnt", 10)["count"], 10)
        self.assertEqual(await self.s.claim_quests(10), 1000)
        self.assertIsNone(await self.s.claim_quests(10))

    async def test_empty_authoritative_state(self):
        state = State(FakeConnection(), {})
        nonce, x, y = await state.challenge(1)
        self.assertEqual((await state.verify(1, nonce, x + y, person(1)))[0], "verified")
        await state.register(person(1), private=True)
        self.assertEqual(state.balance(1), 0)
        self.assertIsNone(await state.prepare_send(1, 2, 1))

    async def test_boot_missing_row_and_lock_fail_closed(self):
        connection = SimpleNamespace(fetchval=AsyncMock(return_value=True),
                                     fetchrow=AsyncMock(return_value=None),
                                     close=AsyncMock())
        with patch("state.asyncpg.connect", new=AsyncMock(return_value=connection)):
            with self.assertRaises(StateError):
                await State.open("postgres://offline")
        connection.close.assert_awaited_once()
        connection.fetchrow.assert_awaited_once()
        connection.fetchval.return_value = False
        connection.close.reset_mock()
        connection.fetchrow.reset_mock()
        with patch("state.asyncpg.connect", new=AsyncMock(return_value=connection)):
            with self.assertRaises(StateError):
                await State.open("postgres://offline")
        connection.fetchrow.assert_not_awaited()
        connection.close.assert_awaited_once()

    async def test_tls_verified_elsewhere_railway_self_signed_encrypted(self):
        import ssl
        from state import _make_ssl
        standard = _make_ssl("postgresql://db.example.com/bot")
        self.assertEqual(standard.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(standard.check_hostname)
        for host in ("postgres.railway.internal", "roundhouse.proxy.rlwy.net"):
            railway = _make_ssl(f"postgresql://{host}/bot")
            self.assertEqual(railway.verify_mode, ssl.CERT_NONE)
            self.assertFalse(railway.check_hostname)
            self.assertIsInstance(railway, ssl.SSLContext)
        with self.assertRaises(StateError):
            await State.open("postgresql://db.example.com/bot?sslmode=disable")

    async def test_lock_before_read_and_poison_after_ambiguous_commit(self):
        events = []
        class Connection:
            committed = None
            async def fetchval(self, *_args):
                events.append("lock")
                return True
            async def fetchrow(self, *_args):
                events.append("read")
                return {"value": '{"verified_users":[10],"lmn_balances":{"10":250}}'}
            async def execute(self, _sql, payload):
                events.append("write")
                self.committed = json.loads(payload)
                raise ConnectionError("commit may have completed")
            async def close(self):
                events.append("close")
        import json
        conn = Connection()
        with patch("state.asyncpg.connect", new=AsyncMock(return_value=conn)):
            restored = await State.open("postgresql://db.example.com/bot")
        self.assertEqual(events, ["lock", "read"])
        with self.assertRaises(StateError):
            await restored.claim_daily(10)
        with self.assertRaises(StateError):
            await restored.claim_daily(10)
        self.assertEqual(events, ["lock", "read", "write"])
        self.assertTrue(restored.poisoned)
        # Restarting from the server's actually committed row detects the claim.
        restarted = State(FakeConnection(), conn.committed)
        self.assertIsNone(await restarted.claim_daily(10))
        self.assertEqual(restarted.get("daily_cooldown", 10),
                         datetime.now(KYIV).date().isoformat())
        await restored.close()

    async def test_ambiguous_transfer_commit_never_replays_nonce(self):
        class CommitThenDisconnect(FakeConnection):
            async def execute(self, sql, payload):
                import json
                self.payload = json.loads(payload)
                raise ConnectionError("ack lost after durable commit")
        nonce = await self.s.prepare_send(10, 20, 100)
        self.s.conn = CommitThenDisconnect()
        with self.assertRaises(StateError):
            await self.s.confirm_send(10, nonce)
        self.assertTrue(self.s.poisoned)
        self.assertEqual(self.s.raw["lmn_balances"]["10"], 4000)
        saved = copy.deepcopy(self.s.conn.payload)
        self.assertEqual(saved["lmn_balances"]["10"], 3900)
        self.assertEqual(saved["lmn_balances"]["20"], 600)
        restarted = State(FakeConnection(), saved)
        self.assertFalse(await restarted.confirm_send(10, nonce))
        self.assertEqual(restarted.balance(10), 3900)

    async def test_daily_reminder_opt_in_and_deletion(self):
        await self.s.change(lambda d: d.setdefault("aurelia_accounts", {}).setdefault("10", {}).update(
            notifications={"daily": True}))
        first = await self.s.due_daily_notices()
        self.assertIn(10, first)
        self.assertNotIn(20, first)
        # Reading due work cannot pre-acknowledge undelivered reminders.
        self.assertIn(10, await self.s.due_daily_notices())
        await self.s.record_daily_notice(10, "sent")
        self.assertEqual(await self.s.due_daily_notices(), [])
        await self.s.delete(10)
        self.assertEqual(await self.s.due_daily_notices(datetime.now(KYIV).date() + timedelta(days=1)), [])

    async def test_daily_delivery_transient_retry_blocked_optout_and_ack(self):
        from aiogram.exceptions import TelegramForbiddenError
        from aiogram.methods import SendMessage
        ui = Interface(self.s, "offline-secret")
        await self.s.change(lambda d: d.setdefault("aurelia_accounts", {}).setdefault("10", {}).update(
            notifications={"daily": True}))
        bot = SimpleNamespace(send_message=AsyncMock(side_effect=ConnectionError("offline")))
        with self.assertLogs(level="ERROR"):
            self.assertFalse(await ui.notice(bot, 10, "daily", "due"))
        self.assertEqual(self.s.account(10)["daily_delivery"]["status"], "retry")
        self.assertEqual(await self.s.due_daily_notices(), [])
        # After retry delay, no pre-acknowledgement exists; a crash is also retryable.
        await self.s.change(lambda d: d["aurelia_accounts"]["10"]["daily_delivery"].update(retry_after=0))
        self.assertIn(10, await self.s.due_daily_notices())
        bot.send_message.side_effect = TelegramForbiddenError(
            SendMessage(chat_id=10, text="due"), "bot blocked")
        with self.assertLogs(level="WARNING"):
            self.assertFalse(await ui.notice(bot, 10, "daily", "due"))
        self.assertTrue(self.s.account(10)["daily_notice_blocked"])
        self.assertEqual(await self.s.due_daily_notices(), [])
        await self.s.register(person(10), private=True)
        self.assertIn(10, await self.s.due_daily_notices())
        bot.send_message.side_effect = None
        self.assertTrue(await ui.notice(bot, 10, "daily", "due"))
        # No send can be marked before success; the ack is a distinct durable write.
        self.assertIn(10, await self.s.due_daily_notices())
        await self.s.record_daily_notice(10, "sent")
        self.assertEqual(await self.s.due_daily_notices(), [])
        await self.s.change(lambda d: d["aurelia_accounts"]["10"]["notifications"].update(daily=False))
        self.assertEqual(await self.s.due_daily_notices(datetime.now(KYIV).date() + timedelta(days=1)), [])


class ScreenTests(unittest.TestCase):
    def test_all_routes_and_callback_ownership(self):
        s = State(FakeConnection(), {"known_users": {"10": {"username": "user10"}}})
        ui = Interface(s, "offline-test-secret", "AureliaBot")
        for name in ROUTES:
            self.assertEqual(route_for("/" + name), {"me": "profile", "claim": "daily",
                              "missions": "quests", "portal": "app"}.get(name, name))
            text, keyboard = ui.screen(10, name, person(10))
            self.assertTrue(text)
            for row in keyboard.inline_keyboard:
                for button in row:
                    if button.callback_data:
                        parts = button.callback_data.split(":")
                        self.assertEqual(parts[1], "10")
                        self.assertEqual(parts[3], ui.token(10, parts[2]))
                        self.assertNotEqual(parts[3], ui.token(20, parts[2]))
        self.assertIsNone(route_for("/marry"))
        self.assertIsNone(route_for("/admin"))
        self.assertEqual(route_for("мой баланс"), "balance")

    def test_no_unconfigured_external_urls_or_fake_feeds(self):
        from unittest.mock import patch
        ui = Interface(State(FakeConnection(), {}), "offline-test-secret")
        with patch.dict("os.environ", {}, clear=True):
            for route in ("news", "events", "social", "app", "links"):
                text, markup = ui.screen(10, route, person(10))
                self.assertTrue(any(word in text.lower() for word in ("not", "no verified")))
                self.assertFalse(any(button.url for row in markup.inline_keyboard
                                     for button in row))

    def test_every_route_and_action_localized_for_ru_and_sl(self):
        import re
        state = State(FakeConnection(), {
            "known_users": {"10": {"username": "user10", "private_started": True}},
            "verified_users": [10], "lmn_balances": {"10": 1234},
            "user_achievements": {"10": ["first_message"]},
            "aurelia_accounts": {"10": {"ledger": [
                {"date": "2026-01-01", "amount": 25, "reason": "Daily reward"},
                {"date": "2026-01-01", "amount": -4, "reason": "Send to #20"}],
                "pending_send": {"nonce": "abc", "recipient": 20, "amount": 100,
                                 "expires": 9999999999}}},
        })
        ui = Interface(state, "offline-secret", "AureliaBot")
        routes = ROUTES + ["social_profile", "history_rewards", "history_referrals",
                           "history_quests", "history_purchases", "history_achievements"]
        with patch.dict("os.environ", {}, clear=True):
            for lang in ("ru", "sl"):
                state.raw["aurelia_accounts"]["10"]["language"] = lang
                for route in routes:
                    with self.subTest(lang=lang, route=route):
                        text, markup = ui.screen(10, route, person(10))
                        visible = text + " ".join(
                            button.text for row in markup.inline_keyboard for button in row)
                        # Names, command identifiers, XP/LMN, and brand are invariant.
                        english_ui = (r"\b(?:Welcome|Level|Profile|Wallet|Rewards|Daily|"
                                      r"Streak|Quests|Achievements|Settings|Notifications|"
                                      r"Available|Store|History|Invite|Claim|Send|"
                                      r"Coming soon|No verified|Nothing here|Back|Home)\b")
                        self.assertIsNone(re.search(english_ui, visible))
                        if route == "achievements":
                            self.assertNotIn("first_message", text)
                self.assertEqual(translate("https://example.com/Profile?name=Wallet", lang),
                                 "https://example.com/Profile?name=Wallet")
                for alert in ("Account storage is unavailable. No changes were applied.",
                              "This screen belongs to another user or is invalid.",
                              "Already claimed today.", "Wrong answer. Open /start to try again.",
                              "Transfer rejected. Check recipient, balance, amount and account cap."):
                    self.assertNotEqual(translate(alert, lang), alert)


class MenuTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_former_scopes_and_locales_are_replaced_offline(self):
        from bot import configure_identity
        api = SimpleNamespace(set_my_commands=AsyncMock(), set_my_name=AsyncMock(),
                              set_my_description=AsyncMock(),
                              set_my_short_description=AsyncMock())
        await configure_identity(api, main_chat=-1004401287309)
        self.assertEqual(api.set_my_commands.await_count, 20)
        scopes = {(type(c.kwargs["scope"]).__name__, c.kwargs["language_code"])
                  for c in api.set_my_commands.await_args_list}
        self.assertEqual(len(scopes), 20)
        self.assertIn(("BotCommandScopeChat", "ru"), scopes)
        for call in api.set_my_commands.await_args_list:
            self.assertEqual({cmd.command for cmd in call.args[0]},
                             {"start", "home", "profile", "rewards", "social",
                              "wallet", "app", "help"})
        api.set_my_name.assert_awaited_once_with(name="AURELIA")


class StartupCompatibilityTests(unittest.TestCase):
    def test_site_and_worker_boot_paths_need_no_removed_modules(self):
        import ast
        folder = Path(__file__).parent
        startup = (folder / "start.sh").read_text()
        self.assertIn("python bot.py", startup)
        self.assertIn("python site_server.py", startup)
        self.assertTrue((folder / "site_static" / "index.html").is_file())
        for filename in ("bot.py", "site_server.py", "interface.py", "state.py"):
            tree = ast.parse((folder / filename).read_text())
            imports = {name.name.split(".")[0] for node in ast.walk(tree)
                       if isinstance(node, ast.Import) for name in node.names}
            imports |= {node.module.split(".")[0] for node in ast.walk(tree)
                        if isinstance(node, ast.ImportFrom) and node.module}
            self.assertFalse(imports & {"db", "brand", "lumena", "auction",
                                        "ai_agent", "aurelia", "nlu", "uk_locale"})
        deps = (folder / "requirements.txt").read_text()
        self.assertIn("aiohttp", deps)
        self.assertIn("asyncpg", deps)


class CallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_private_start_verification_then_referral_route(self):
        state = State(FakeConnection(), {"verified_users": [10],
                                         "known_users": {"10": {"private_started": True}},
                                         "lmn_balances": {"10": 250}})
        ui = Interface(state, "offline-test-secret")
        class ChatMessage:
            def __init__(self, text, chat_type="private", uid=30):
                self.text = text
                self.chat = SimpleNamespace(id=uid if chat_type == "private" else -100,
                                            type=chat_type)
                self.from_user = person(uid)
                self.message_id = 1
                self.sent = []
                self.bot = SimpleNamespace(send_message=AsyncMock())
            async def answer(self, text, reply_markup=None):
                result = SimpleNamespace(chat=self.chat, message_id=len(self.sent) + 2,
                                         text=text, reply_markup=reply_markup)
                self.sent.append(result)
                return result
            async def edit_text(self, text, reply_markup=None):
                self.text = text
        group = ChatMessage("/start ref_10", "group")
        await ui.message(group)
        self.assertEqual(state.balance(10), 250)
        self.assertFalse(state.verified(30))
        start = ChatMessage("/start ref_10")
        await ui.message(start)
        self.assertIn("Verify", start.sent[0].text)
        pending = state.account(30)["captcha"]
        action = f"verify_{pending['nonce']}_{pending['answer']}"
        callback = SimpleNamespace(
            from_user=person(30), message=start.sent[0],
            data=f"aur:30:{action}:{ui.token(30, action)}",
            answer=AsyncMock(), bot=start.bot)
        callback.message.edit_text = AsyncMock()
        await ui.callback(callback)
        self.assertIn("Welcome,", callback.message.edit_text.await_args.args[0])
        self.assertTrue(state.verified(30))
        self.assertEqual(state.get("referrals", 30), 10)
        self.assertEqual(state.balance(10), 1250)
        await ui.callback(callback)
        self.assertEqual(state.balance(10), 1250)

    async def test_foreign_callback_and_duplicate_claim(self):
        state = State(FakeConnection(), {"known_users": {"10": {"private_started": True}},
                                         "verified_users": [10]})
        ui = Interface(state, "offline-test-secret")
        class Message:
            text = "AURELIA"
            chat = SimpleNamespace(id=-100)
            message_id = 55
            async def edit_text(self, text, reply_markup=None):
                self.text = text
        class Callback:
            def __init__(self, uid):
                self.from_user = person(uid)
                self.data = f"aur:10:claim_now:{ui.token(10, 'claim_now')}"
                self.message = Message()
                self.answers = []
                self.bot = SimpleNamespace(send_message=self.send_message)
            async def send_message(self, *_args):
                self.answers.append("notice")
            async def answer(self, text=None, **kwargs):
                self.answers.append((text, kwargs))
        foreign = Callback(20)
        await ui.callback(foreign)
        self.assertEqual(state.balance(10), 0)
        self.assertTrue(foreign.answers[0][1]["show_alert"])
        owner = Callback(10)
        await ui.callback(owner)
        balance = state.balance(10)
        self.assertGreaterEqual(balance, 500)
        await ui.callback(owner)
        self.assertEqual(state.balance(10), balance)


class DispatcherIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_feed_update_verification_every_route_and_signed_callbacks(self):
        from aiogram import Bot, Dispatcher
        from aiogram.methods import SendMessage, EditMessageText, AnswerCallbackQuery
        from aiogram.types import Update, Message, Chat, User, CallbackQuery
        class OfflineBot(Bot):
            def __init__(self):
                super().__init__("123456:offline-only-dummy-token")
                self.calls = []
                self.sent = []
            async def __call__(self, method, request_timeout=None):
                self.calls.append(method)
                if isinstance(method, SendMessage):
                    sent = Message(
                        message_id=len(self.sent) + 1000, date=datetime.now(KYIV),
                        chat=Chat(id=method.chat_id,
                                  type="private" if method.chat_id > 0 else "supergroup"),
                        from_user=User(id=123456, is_bot=True, first_name="AURELIA"),
                        text=method.text, reply_markup=method.reply_markup)
                    self.sent.append(sent)
                    return sent
                if isinstance(method, (EditMessageText, AnswerCallbackQuery)):
                    return True
                raise AssertionError(f"Unexpected Telegram API call: {type(method)}")
        offline = OfflineBot()
        state = State(FakeConnection(), {"verified_users": [10],
                                         "known_users": {"10": {"username": "user10",
                                                                "private_started": True}},
                                         "lmn_balances": {"10": 100}})
        ui = Interface(state, "offline-only-dummy-token", "AureliaBot")
        dp = Dispatcher()
        dp.include_router(ui.router)
        next_update = 0
        async def message(uid, text, private=True):
            nonlocal next_update
            next_update += 1
            chat_id = uid if private else -100
            message = Message(
                message_id=next_update, date=datetime.now(KYIV),
                chat=Chat(id=chat_id, type="private" if private else "supergroup"),
                from_user=User(id=uid, is_bot=False, first_name=f"User {uid}",
                               username=f"user{uid}"), text=text)
            await dp.feed_update(offline, Update(update_id=next_update, message=message))
            return offline.sent[-1] if offline.sent else None
        async def callback(uid, screen, target):
            nonlocal next_update
            next_update += 1
            query = CallbackQuery(
                id=f"offline_{next_update}", chat_instance="offline",
                from_user=User(id=uid, is_bot=False, first_name=f"User {uid}",
                               username=f"user{uid}"), message=screen,
                data=f"aur:{uid}:{target}:{ui.token(uid, target)}")
            await dp.feed_update(offline, Update(update_id=next_update, callback_query=query))
        try:
            await message(30, "/daily", private=False)
            self.assertEqual(state.balance(30), 0)
            await message(30, "/start ref_10")
            challenge = state.account(30)["captcha"]
            screen = offline.sent[-1]
            await callback(30, screen, f"verify_{challenge['nonce']}_{challenge['answer']}")
            self.assertTrue(state.verified(30))
            self.assertEqual(state.get("referrals", 30), 10)
            self.assertEqual(state.balance(10), 1100)
            for route in ROUTES:
                with self.subTest(route=route):
                    sent = await message(30, "/" + route, private=False)
                    self.assertIsNotNone(sent)
                    self.assertTrue(sent.text)
            await message(30, "мой баланс")
            self.assertIn("LMN", offline.sent[-1].text)
            sent = await message(30, "/daily")
            claim = next(b for row in sent.reply_markup.inline_keyboard for b in row
                         if b.callback_data and ":claim_now:" in b.callback_data)
            await callback(30, sent, "claim_now")
            amount = state.balance(30)
            self.assertGreaterEqual(amount, 500)
            await callback(30, sent, "claim_now")
            self.assertEqual(state.balance(30), amount)
            language = await message(30, "/language")
            await callback(30, language, "lang_ru")
            self.assertEqual(state.account(30)["language"], "ru")
            notifications = await message(30, "/notify")
            await callback(30, notifications, "toggle_daily")
            self.assertTrue(state.account(30)["notifications"]["daily"])
            await callback(30, notifications, "toggle_daily")
            self.assertFalse(state.account(30)["notifications"]["daily"])
            transfer = await message(30, "/send 10 50")
            nonce = state.account(30)["pending_send"]["nonce"]
            await callback(30, transfer, f"send_confirm_{nonce}")
            self.assertEqual(state.balance(30), amount - 50)
            self.assertEqual(state.balance(10), 1150)
            await callback(30, transfer, f"send_confirm_{nonce}")
            self.assertEqual(state.balance(10), 1150)
            # A foreign user cannot settle another user's signed button.
            next_update += 1
            query = CallbackQuery(
                id=f"offline_{next_update}", chat_instance="offline",
                from_user=User(id=99, is_bot=False, first_name="Other"), message=sent,
                data=claim.callback_data)
            await dp.feed_update(offline, Update(update_id=next_update, callback_query=query))
            self.assertEqual(state.balance(30), amount - 50)
            self.assertTrue(any(isinstance(c, AnswerCallbackQuery) and c.show_alert
                                for c in offline.calls))
            delete = await message(30, "/delete")
            await callback(30, delete, "delete_confirm")
            self.assertTrue(state.account(30)["deleted"])
            self.assertEqual(state.balance(30), amount - 50)
            self.assertEqual(state.get("referrals", 30), 10)
        finally:
            await offline.session.close()


if __name__ == "__main__":
    unittest.main()