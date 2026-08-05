---
name: Premium message style
description: Design system for all Лумена bot message outputs — constants, helpers, and conventions
---

## Constants (bot.py)
```python
_LMN_HDR = "┏━━━━━━━━━━━━━━━━━━━━━┓\n        L U M E N A\n┗━━━━━━━━━━━━━━━━━━━━━┛"
_LMN_DIV = "━━━━━━━━━━━━━━━━━━━━━━"
```

## mod_card() helper
Generates moderation cards (ban/mute/kick/warn/etc.) with the LUMENA header, action line, optional extra line, optional reason, and divider footer. Signature: `mod_card(action, user, extra="", reason="")`.

## parse_time_and_reason() helper
Splits command args into `(timedelta, reason_str)`. First word is parsed as time (5м/1ч/7д/numeric), rest is reason. Replaces the old `parse_time()` for moderation commands.

## Template pattern
```
{_LMN_HDR}

<section title> · <context name>

<field>: <value>
...

{_LMN_DIV}
```

## Help menu (_HELP_MAIN_KB)
6 section buttons in a 2×3 grid + 2 link buttons. Buttons: 💰 Экономика, 🎮 Игры, 💑 Отношения, 🎉 Развлечения, 🔮 Предсказания, 👤 Профиль, ✦ 💬 Наш чат ✦, ✦ 📢 Канал ✦.
"Модерация" and "ИИ Лумена" buttons intentionally removed by user request.

## Coin rain (дождь монет)
- `_active_rain: dict = {}` — {chat_id: amount} tracks active drops
- `coin_rain_loop()` fires every 8h, sends to all negative-ID chats in `chat_members`
- Random 150–600 LMN per drop
- First user to write "подобрать" wins; handled in `universal_handler` before text commands

## anketa.py
All format functions (fmt_mod_card, fmt_pub_card, fmt_my_card) + all flow messages (start_anketa, cancel_anketa, handle_lang_select header, handle_anketa_step progress, _finish_anketa, handle_mod_comment_step) use the same ┏━━┓ L U M E N A style with ━━━ dividers.

## Commands with premium style
All moderation (mute, unmute, ban, forceban, forcemute, unban, kick, warn, unwarn, ro), economy (balance, give, work, fish, casino, slots, rob, richest), social (marry, divorce, marriages, ship, love, friend, couple), streaks (checkin, streak, topstreak), reputation (rep, upvote, downvote, toprep), profile (profile, whois, chatinfo, botstats, ping, version), help sections.

**Why:** Unified visual identity across all bot outputs, requested by user for full premium redesign.

**How to apply:** Always use `_LMN_HDR` / `_LMN_DIV` constants for new command outputs. Use `mod_card()` for any admin action that affects a specific user. Add new coin rain chats to coverage by ensuring they appear in `chat_members` (all messages go through PropagandaMiddleware which tracks them).
