"""Telegram screens for the standalone AURELIA bot."""
import html
import hmac
import hashlib
import logging
import os
import re
from datetime import datetime
from urllib.parse import quote, urlparse

from aiogram import Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from state import KYIV, StateError
from translations import translate

ROUTES = ("start home profile me wallet vault balance rewards daily claim streak quests "
          "missions achievements social links community events news ai notify settings "
          "language referral orbit invite history ledger store forge app portal share id "
          "about help privacy delete send").split()
ALIASES = {"me": "profile", "claim": "daily", "missions": "quests", "portal": "app"}
SMART = {"мой баланс": "balance", "мои награды": "rewards", "мои задания": "quests",
         "мой профиль": "profile", "соцсети": "social", "дай ссылку": "links",
         "пригласить друга": "invite", "открой приложение": "app",
         "какие новости": "news"}
NOTICES = ("ai", "daily", "events", "news", "social", "referrals")
PARENTS = {"daily": "rewards", "quests": "rewards", "streak": "rewards",
           "achievements": "rewards", "notify": "settings", "language": "settings",
           "delete": "settings", "privacy": "settings", "ledger": "wallet",
           "history": "wallet", "send": "wallet", "invite": "referral",
           "links": "social", "community": "social", "events": "community",
           "news": "community"}
LINKS = {"Website": "AURELIA_SITE_URL", "Social": "AURELIA_SOCIAL_URL",
         "X": "AURELIA_X_URL", "Instagram": "AURELIA_INSTAGRAM_URL",
         "Threads": "AURELIA_THREADS_URL", "TikTok": "AURELIA_TIKTOK_URL",
         "Telegram": "AURELIA_TELEGRAM_URL", "Official channel": "AURELIA_CHANNEL_URL",
         "Community": "AURELIA_COMMUNITY_URL"}
XP_THRESHOLDS = (0, 100, 500, 1500, 3500, 7000)


def route_for(text):
    text = (text or "").strip()
    if text.startswith("/"):
        name = text.split()[0][1:].split("@")[0].lower()
        return ALIASES.get(name, name) if name in ROUTES else None
    return SMART.get(re.sub(r"[?!.,]+$", "", text.casefold()))


def verified_url(value):
    parsed = urlparse(value or "")
    return value if parsed.scheme == "https" and parsed.netloc else ""


class Interface:
    def __init__(self, state, token, username=""):
        self.s = state
        self.secret = token
        self.username = username
        self.router = Router()
        self.router.message.register(self.message)
        self.router.callback_query.register(self.callback)
        self.navigation = {}

    def language(self, uid):
        return self.s.raw.get("aurelia_accounts", {}).get(str(uid), {}).get("language", "en")

    def token(self, uid, target):
        return hmac.new(self.secret.encode(), f"{uid}:{target}".encode(), hashlib.sha256).hexdigest()[:12]

    def button(self, uid, label, target):
        return InlineKeyboardButton(text=label, callback_data=f"aur:{uid}:{target}:{self.token(uid, target)}")

    def screen(self, uid, page, user=None, first_start=False):
        page = ALIASES.get(page, page)
        if page not in ROUTES and page != "social_profile" and not page.startswith("history_"):
            page = "home"
        s = self.s
        a = s.account(uid)
        balance = s.balance(uid)
        xp = int(s.get("user_xp", uid, 0))
        level = max(i + 1 for i, threshold in enumerate(XP_THRESHOLDS) if xp >= threshold)
        current = XP_THRESHOLDS[level - 1]
        next_level = XP_THRESHOLDS[level] if level < len(XP_THRESHOLDS) else current
        fill = min(10, (xp - current) * 10 // (next_level - current)) if next_level > current else 10
        progress = "█" * fill + "░" * (10 - fill)
        today = datetime.now(KYIV).date().isoformat()
        claimed = s.get("daily_cooldown", uid) == today
        streak = int(a.get("streak", 0))
        name = html.escape(("@" + user.username) if user and user.username else
                           (user.full_name if user else s.get("known_users", uid, {}).get("full_name", str(uid))))
        rows, extra = [], []
        if page in ("start", "home"):
            title = "Welcome" if first_start else "Welcome back"
            text = (f"✦ AURELIA\n\n{title}, {name}.\n\n💎 {balance:,} LMN\n"
                    f"◈ Level {level}\n{progress}\n🔥 {streak} day streak\n\n"
                    + ("✓ Daily reward claimed" if claimed else "🎁 Daily reward available"))
            rows = [[("🎁 Daily", "daily"), ("📋 Quests", "quests")],
                    [("🌐 Social", "social"), ("👤 Profile", "profile")],
                    [("💎 Wallet", "wallet"), ("✦ AI", "ai")],
                    [("📱 App", "app"), ("⚙️ Settings", "settings")]]
        elif page == "profile":
            refs = sum(1 for r in s.table("referrals").values() if int(r) == uid)
            text = (f"👤 {name}\n\n◈ Level {level}\n{progress}\n{xp:,} XP\n"
                    f"💎 {balance:,} LMN\n🔥 {streak} day streak\n"
                    f"🏆 {len(s.get('user_achievements', uid, []))} Achievements\n👥 {refs} Referrals")
            rows = [[("🌐 Social Profile", "social_profile"), ("🏆 Achievements", "achievements")],
                    [("🔥 Streak", "streak"), ("📋 Quests", "quests")],
                    [("👥 Referrals", "referral"), ("⚙️ Settings", "settings")]]
        elif page == "social_profile":
            text = "🌐 Social Profile\n\nA verified social profile integration is not connected yet."
            rows = [[("🌐 Links", "links")]]
        elif page in ("balance", "wallet", "vault"):
            text = f"💎 Your balance\n\n{balance:,} LMN"
            if page != "balance":
                text += "\n\nEarn LMN from rewards. Transfers require confirmation."
                if page == "vault":
                    text += (f"\nProtected bank: {int(s.get('bank_balances', uid, 0)):,} LMN"
                             f"\nTerm deposit: {int(s.get('bank_term_deposits', uid, {}).get('principal', 0)):,} LMN")
                rows = [[("➕ Add LMN", "rewards"), ("🎁 Send", "send")],
                        [("📜 History", "history"), ("🛍 Store", "store")]]
        elif page == "send":
            text = "🎁 SEND LMN\n\nUse /send [known Telegram ID or @username] [positive whole amount]."
            p = a.get("pending_send", {})
            if p and p.get("expires", 0) >= datetime.now(KYIV).timestamp():
                text += f"\n\nConfirm: {p['amount']:,} LMN to #{p['recipient']} (expires in 5 minutes)."
                rows = [[("Confirm send", "send_confirm_" + p["nonce"]),
                         ("Cancel", "send_cancel")]]
        elif page == "rewards":
            text = (f"🎁 REWARDS\n\nDaily: 500–2,000 LMN + 50 XP\n"
                    f"Status: {'Claimed today' if claimed else 'Available'}\n🔥 Streak: {streak} days")
            rows = [[("🎁 Daily reward", "daily"), ("🔥 Streak", "streak")],
                    [("📋 Quests", "quests"), ("🏆 Achievements", "achievements")]]
        elif page == "daily":
            text = ("🎁 DAILY REWARD\n\n" + ("✓ Claimed today. Return tomorrow." if claimed
                    else "Available: 500–2,000 LMN + 50 XP (subject to account cap).")
                    + f"\n🔥 Streak: {streak} days")
            if not claimed:
                rows = [[("Claim reward", "claim_now")]]
        elif page == "streak":
            text = (f"🔥 YOUR STREAK\n\nCurrent: {streak} days\nBest: {a.get('best', 0)} days\n"
                    f"Recorded daily rewards: {a.get('daily_earned', 0):,} LMN\n\n"
                    "Claim on consecutive Kyiv calendar days to build your streak.")
            rows = [[("🎁 Daily", "daily")]]
        elif page == "quests":
            count = s.get("daily_msg_cnt", uid, {})
            messages = int(count.get("count", 0)) if count.get("date") == today else 0
            text = (f"📋 QUEST CENTER\n\nCommunity messages: {min(messages, 10)}/10\n"
                    f"Daily reward: {int(claimed)}/1\n3-day daily streak: {min(streak, 3)}/3\n"
                    "Complete all three for 1,000 LMN + 75 XP.")
            rows = [[("🎁 Daily", "daily")]]
            if messages >= 10 and claimed and streak >= 3 and s.get("tasks_bonus_cd", uid) != today:
                rows.append([("Claim quest completion", "quest_claim")])
        elif page == "achievements":
            earned = s.get("user_achievements", uid, [])
            text = (f"🏆 ACHIEVEMENTS\n\nUnlocked: {len(earned)}\n\n"
                    + (", ".join(html.escape(str(x)) for x in earned) if earned else
                       "Nothing here yet. Earn XP and claim daily rewards."))
            rows = [[("📋 Quests", "quests")]]
        elif page in ("social", "links", "community"):
            links = {k: url for k, env in LINKS.items() if (url := verified_url(os.getenv(env)))}
            text = f"🌐 AURELIA {page.upper()}\n\n"
            text += "\n".join(f"{k}: {v}" for k, v in links.items()) if links else "Official links have not been configured."
            rows = [[("🌐 Links", "links"), ("💬 Community", "community")],
                    [("🔥 Events", "events"), ("✦ News", "news")]]
            extra = [[InlineKeyboardButton(text=translate(k, a.get("language", "en")), url=v)]
                     for k, v in links.items()]
        elif page in ("events", "news"):
            text = f"✦ AURELIA {page.upper()}\n\nNo verified project feed is connected yet."
            rows = [[("🌐 Links", "links")]]
        elif page == "ai":
            text = "✦ AURELIA AI\n\nComing soon. AI is currently unavailable."
            rows = [[("🔕 Remove me" if a.get("ai_waitlist") else "🔔 Notify me", "waitlist")]]
        elif page == "notify":
            text = "🔔 Notifications\n\nDaily and referral notices are delivered to users who started a private chat. Other categories await verified event sources."
            rows = [[(f"{key.title()}: {'ON' if a.get('notifications', {}).get(key, False) else 'OFF'}",
                      "toggle_" + key)] for key in NOTICES]
        elif page == "settings":
            text = f"⚙️ SETTINGS\n\nLanguage: {a.get('language', 'en').upper()}"
            rows = [[("🔔 Notifications", "notify"), ("🌐 Language", "language")],
                    [("👤 Privacy", "privacy"), ("💎 Wallet", "wallet")],
                    [("🌐 Social", "social"), ("✦ AI", "ai")],
                    [("❌ Delete account", "delete")]]
        elif page == "language":
            text = f"🌐 Language\n\nSelected: {a.get('language', 'en').upper()}"
            rows = [[("🇷🇺 Русский", "lang_ru"), ("🇬🇧 English", "lang_en")],
                    [("🇸🇮 Slovenščina", "lang_sl")]]
        elif page == "privacy":
            text = "👤 Privacy\n\nDeleting a profile does not erase LMN, XP, financial history or referral attribution."
            rows = [[("❌ Delete account", "delete")]]
        elif page == "delete":
            text = "❌ Delete AURELIA profile?\n\nYour public profile and preferences will be removed. Financial history and attribution remain."
            rows = [[("Confirm deletion", "delete_confirm"), ("Cancel", "settings")]]
        elif page in ("referral", "orbit", "invite"):
            refs = sum(1 for r in s.table("referrals").values() if int(r) == uid)
            valid_name = self.username if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{4,31}", self.username) else ""
            link = f"https://t.me/{valid_name}?start=ref_{uid}" if valid_name else ""
            text = f"👥 YOUR REFERRALS\n\nInvited: {refs}\nHistorical earnings are not itemized."
            text += f"\n\nInvite link: {link}" if link else "\n\nBot username is not configured for invites."
            rows = [[("🔗 Invite friends", "invite"), ("👥 Referral Hub", "orbit")]]
            if link:
                extra = [[InlineKeyboardButton(text=translate("Copy link", a.get("language", "en")),
                                                copy_text=CopyTextButton(text=link)),
                          InlineKeyboardButton(text=translate("Share", a.get("language", "en")),
                                                url=f"https://t.me/share/url?url={quote(link, safe='')}")]]
        elif page in ("history", "ledger") or page.startswith("history_"):
            records = a.get("ledger", [])
            category = page.removeprefix("history_")
            if page.startswith("history_"):
                allowed = {"rewards": "Daily reward", "referrals": "Referral",
                           "quests": "Quest completion"}
                records = [r for r in records if r.get("reason") == allowed.get(category)] if category in allowed else []
            text = f"📜 AURELIA {page.upper()}\n\n"
            text += ("\n".join(f"{r['date']} {int(r['amount']):+,} LMN · {html.escape(str(r['reason']))}"
                               for r in records[-15:][::-1]) if records else
                     "Nothing here yet. Older legacy transactions are not itemized.")
            rows = [[("🎁 Rewards", "history_rewards"), ("💎 LMN", "ledger")],
                    [("📋 Quests", "history_quests"), ("🛍 Purchases", "history_purchases")],
                    [("🏆 Achievements", "history_achievements"), ("👥 Referrals", "history_referrals")]]
        elif page in ("store", "forge"):
            text = "🛍 AURELIA Store\n\nPurchases are currently unavailable. Your LMN is unchanged."
        elif page == "app":
            url = verified_url(os.getenv("AURELIA_APP_URL"))
            text = "📱 AURELIA App\n\n" + (f"Open: {url}" if url else "Mini App is not configured yet.")
            if url:
                extra = [[InlineKeyboardButton(text=translate("Open App", a.get("language", "en")), url=url)]]
        elif page == "share":
            text = "✦ Share AURELIA\n\nInvite friends using your personal link."
            rows = [[("👥 Invite friend", "invite"), ("🌐 Social", "social")]]
        elif page == "id":
            text = f"AURELIA ID\n\n#AUR-{uid}"
        elif page == "about":
            text = "✦ AURELIA\n\nA community and identity experience with rewards. AI is coming soon."
            rows = [[("🌐 Links", "links"), ("💬 Community", "community")]]
        else:
            text = ("✦ AURELIA\n\nCore: /home /profile /wallet /rewards /social /app\n"
                    "Rewards: /daily /streak /quests /achievements\n"
                    "Social: /links /community /events /news /invite\n"
                    "Account: /settings /language /notify /id\nFuture: /ai")
            rows = [[("⌂ Home", "home")]]
        language = a.get("language", "en")
        buttons = [[self.button(uid, translate(label, language), target) for label, target in row] for row in rows]
        buttons.extend(extra)
        if page not in ("home", "start"):
            buttons.append([self.button(uid, translate("← Back", language), "back"),
                            self.button(uid, translate("⌂ Home", language), "home")])
        if name and page in ("start", "home", "profile"):
            text = text.replace(name, "\x00AURELIA_USER\x00", 1)
        return translate(text, language).replace("\x00AURELIA_USER\x00", name), InlineKeyboardMarkup(inline_keyboard=buttons)

    def verification_markup(self, uid, nonce, answer):
        choices = [answer, answer + 1, answer - 1, answer + 2]
        return InlineKeyboardMarkup(inline_keyboard=[
            [self.button(uid, str(choice), f"verify_{nonce}_{choice}") for choice in choices[:2]],
            [self.button(uid, str(choice), f"verify_{nonce}_{choice}") for choice in choices[2:]]])

    async def message(self, msg):
        if not msg.from_user or not msg.text:
            return
        first = msg.text.split()[0]
        if first.startswith("/") and "@" in first and self.username and first.split("@", 1)[1].casefold() != self.username.casefold():
            return
        page = route_for(msg.text)
        uid = msg.from_user.id
        try:
            authorized = self.s.verified(uid)
        except StateError:
            return await msg.answer(translate(
                "Account storage is unavailable. No changes were applied.", self.language(uid)))
        if not authorized:
            if page is None:
                return
            if page != "start" or msg.chat.type != "private":
                return await msg.answer(translate(
                    "Open /start in a private chat with the bot to verify.",
                    self.s.account(uid).get("language", "en")))
            payload = msg.text.split(maxsplit=1)
            ref = re.fullmatch(r"ref_(\d+)", payload[1]) if len(payload) > 1 else None
            try:
                challenge = await self.s.challenge(uid, int(ref.group(1)) if ref else None)
            except StateError:
                return await msg.answer(translate(
                    "Account storage is unavailable. No changes were applied.", self.language(uid)))
            if challenge is None:
                return await msg.answer(translate("Too many attempts. Try again in one minute.",
                                                  self.s.account(uid).get("language", "en")))
            nonce, x, y = challenge
            text = translate(f"✦ AURELIA\n\nVerify your account to continue.\n"
                             f"Solve: {x} + {y} = ?", self.s.account(uid).get("language", "en"))
            return await msg.answer(text, reply_markup=self.verification_markup(uid, nonce, x + y))
        if page is None:
            if msg.chat.type in ("group", "supergroup") and not msg.text.startswith("/"):
                try:
                    await self.s.record_message(msg.from_user.id, msg.chat.id, msg.message_id)
                except StateError:
                    logging.exception("Community activity could not be persisted")
            return
        try:
            first_start = page == "start" and not self.s.account(uid).get("registered") and not self.s.get("known_users", uid)
            if page == "start":
                await self.s.register(msg.from_user, private=msg.chat.type == "private")
            elif page == "send" and len(msg.text.split()) > 1:
                args = msg.text.split()
                target = args[1]
                if target.startswith("@"):
                    matches = [int(k) for k, v in self.s.table("known_users").items()
                               if v.get("username", "").casefold() == target[1:].casefold()]
                    dest = matches[0] if len(matches) == 1 else None
                else:
                    dest = int(target) if target.isascii() and target.isdecimal() and len(target) <= 19 else None
                amount = int(args[2]) if len(args) == 3 and args[2].isascii() and args[2].isdecimal() and len(args[2]) <= 19 else 0
                if dest is None or not await self.s.prepare_send(uid, dest, amount):
                    return await msg.answer(translate(
                        "Transfer rejected. Check recipient, balance, amount and account cap.", self.language(uid)))
            text, markup = self.screen(uid, page, msg.from_user, first_start=first_start)
            sent = await msg.answer(text, reply_markup=markup)
            self.navigation[(msg.chat.id, sent.message_id)] = [page]
        except StateError:
            await msg.answer(translate("Account storage is unavailable. No changes were applied.",
                                       self.language(uid)))

    async def notice(self, bot, uid, category, text):
        account = self.s.account(uid)
        if (not account.get("deleted") and account.get("notifications", {}).get(category, False)
                and self.s.get("known_users", uid, {}).get("private_started")):
            try:
                await bot.send_message(uid, text)
                return True
            except TelegramForbiddenError as exc:
                logging.warning("Notification blocked for user %s (%s): %s", uid, category, exc)
                if category == "daily":
                    await self.s.record_daily_notice(uid, "blocked", error=type(exc).__name__)
            except Exception as exc:
                logging.exception("Notification delivery failed for user %s (%s)", uid, category)
                if category == "daily":
                    await self.s.record_daily_notice(uid, "retry", error=type(exc).__name__)
        return False

    async def callback(self, cb):
        if not cb.from_user:
            return
        parts = (cb.data or "").split(":", 3)
        uid = cb.from_user.id
        def tr(text):
            return translate(text, self.language(uid))
        if (len(parts) != 4 or parts[0] != "aur" or parts[1] != str(uid)
                or not hmac.compare_digest(parts[3], self.token(uid, parts[2]))):
            return await cb.answer(tr("This screen belongs to another user or is invalid."), show_alert=True)
        if not cb.message or not cb.message.text:
            return await cb.answer(tr("This screen is no longer available."), show_alert=True)
        key = (cb.message.chat.id, cb.message.message_id)
        target = parts[2]
        just_verified = False
        try:
            if target.startswith("verify_"):
                if cb.message.chat.type != "private":
                    return await cb.answer(tr(
                        "Open /start in a private chat with the bot to verify.",
                        ), show_alert=True)
                match = re.fullmatch(r"verify_([0-9a-f]{8})_(\d{1,2})", target)
                if not match:
                    return await cb.answer(tr("Invalid action"), show_alert=True)
                status, award = await self.s.verify(uid, match.group(1), int(match.group(2)), cb.from_user)
                if status != "verified":
                    return await cb.answer(tr(
                        "Wrong answer. Open /start to try again." if status == "wrong"
                        else "Verification expired. Open /start to try again."), show_alert=True)
                if award:
                    await self.notice(cb.bot, award[0], "referrals",
                                      translate(f"👥 New referral joined AURELIA. +{award[1]:,} LMN",
                                                self.language(award[0])))
                target = "home"
                just_verified = True
            elif not self.s.verified(uid):
                return await cb.answer(tr("Verify with /start in a private chat first."), show_alert=True)
            elif target == "claim_now":
                amount = await self.s.claim_daily(uid)
                if amount is None:
                    return await cb.answer(tr("Already claimed today."))
                target = "daily"
                await self.notice(cb.bot, uid, "daily", tr(f"🎁 Daily reward claimed: +{amount:,} LMN"))
            elif target.startswith("send_confirm_"):
                if not await self.s.confirm_send(uid, target[13:]):
                    return await cb.answer(tr("Transfer expired, invalid or already confirmed."), show_alert=True)
                target = "wallet"
            elif target == "quest_claim":
                amount = await self.s.claim_quests(uid)
                if amount is None:
                    return await cb.answer(tr("Complete all quests first or already claimed today."), show_alert=True)
                target = "quests"
            elif target == "delete_confirm":
                await self.s.delete(uid)
                target = "home"
            elif target == "send_cancel":
                await self.s.change(lambda d: d.setdefault("aurelia_accounts", {}).setdefault(str(uid), {}).pop("pending_send", None))
                target = "send"
            elif target == "waitlist" or target.startswith("toggle_") or target.startswith("lang_"):
                if target == "waitlist":
                    def change(d):
                        a = d.setdefault("aurelia_accounts", {}).setdefault(str(uid), {})
                        a["ai_waitlist"] = not a.get("ai_waitlist", False)
                        a.setdefault("notifications", {})["ai"] = a["ai_waitlist"]
                    target = "ai"
                elif target.startswith("toggle_") and target[7:] in NOTICES:
                    category = target[7:]
                    def change(d):
                        a = d.setdefault("aurelia_accounts", {}).setdefault(str(uid), {})
                        n = a.setdefault("notifications", {})
                        n[category] = not n.get(category, False)
                        if category == "daily" and n[category]:
                            a.pop("daily_notice_blocked", None)
                        if category == "ai":
                            a["ai_waitlist"] = n[category]
                    target = "notify"
                elif target[5:] in ("ru", "en", "sl"):
                    language = target[5:]
                    def change(d):
                        d.setdefault("aurelia_accounts", {}).setdefault(str(uid), {})["language"] = language
                    target = "language"
                else:
                    return await cb.answer(tr("Invalid action"), show_alert=True)
                await self.s.change(change)
            elif target not in ROUTES and not target.startswith("history_") and target not in ("back", "social_profile"):
                return await cb.answer(tr("This action is unavailable."), show_alert=True)
            stack = self.navigation.setdefault(key, [])
            if target == "back":
                if len(stack) > 1:
                    stack.pop()
                    target = stack[-1]
                else:
                    target = PARENTS.get(stack[-1], "home") if stack else "home"
                    stack[:] = [target]
            elif target == "home":
                stack[:] = ["home"]
            elif not stack or stack[-1] != target:
                stack.append(target)
            text, markup = self.screen(uid, target, cb.from_user, first_start=just_verified)
            await cb.answer()
            try:
                await cb.message.edit_text(text, reply_markup=markup)
            except TelegramBadRequest as exc:
                if "message is not modified" not in str(exc).lower():
                    raise
        except StateError:
            await cb.answer(tr("Account storage is unavailable. No changes were applied."),
                            show_alert=True)