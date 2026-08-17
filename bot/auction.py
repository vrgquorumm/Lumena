"""Живой аукцион коллекционных картин и древних артефактов.

Модуль намеренно не импортирует bot.py: все операции с балансами и
сохранением передаются через register(). Это не даёт аукциону создать
вторую систему хранения или обойти общие лимиты экономики.
"""

from __future__ import annotations

import asyncio
import html
import random
from datetime import datetime, timedelta, timezone
from typing import Callable

from aiogram import F
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)


AUCTION_DURATION = timedelta(minutes=10)
ANTI_SNIPE_WINDOW = timedelta(seconds=60)
ANTI_SNIPE_EXTENSION = timedelta(seconds=60)
MIN_PARTICIPANTS = 3
MAX_EXTENSIONS = 3
MIN_BID_INCREMENT = 1_000
MAX_ITEM_INCOME = 1_000_000


LOT_CATALOG = (
    {
        "kind": "painting",
        "icon": "🖼️",
        "name": "«Лунный сад»",
        "story": "масло на холсте, подпись неизвестного ученика старой школы",
        "rarity": "Редкая картина",
        "start_price": 25_000,
        "income_min": 40_000,
        "income_max": 90_000,
    },
    {
        "kind": "painting",
        "icon": "🎨",
        "name": "«Синий полдень»",
        "story": "спокойный морской пейзаж из закрытой частной коллекции",
        "rarity": "Редкая картина",
        "start_price": 40_000,
        "income_min": 55_000,
        "income_max": 120_000,
    },
    {
        "kind": "painting",
        "icon": "🖌️",
        "name": "«Портрет без имени»",
        "story": "портрет с тайным символом на обороте рамы",
        "rarity": "Эпическая картина",
        "start_price": 80_000,
        "income_min": 90_000,
        "income_max": 220_000,
    },
    {
        "kind": "artifact",
        "icon": "🏺",
        "name": "Амфора из затонувшего порта",
        "story": "древняя керамика, поднятая со дна торгового маршрута",
        "rarity": "Древний артефакт",
        "start_price": 60_000,
        "income_min": 70_000,
        "income_max": 180_000,
    },
    {
        "kind": "artifact",
        "icon": "🗿",
        "name": "Каменная маска жреца",
        "story": "тяжёлая маска с вырезанными знаками неизвестного культа",
        "rarity": "Древний артефакт",
        "start_price": 110_000,
        "income_min": 110_000,
        "income_max": 300_000,
    },
    {
        "kind": "artifact",
        "icon": "⚱️",
        "name": "Печать царского архивариуса",
        "story": "бронзовая печать, которая открыла путь к забытому архиву",
        "rarity": "Легендарный артефакт",
        "start_price": 180_000,
        "income_min": 160_000,
        "income_max": 450_000,
    },
    {
        "kind": "artifact",
        "icon": "🧿",
        "name": "Око пустынного каравана",
        "story": "инкрустированный амулет, переживший несколько империй",
        "rarity": "Легендарный артефакт",
        "start_price": 250_000,
        "income_min": 240_000,
        "income_max": 650_000,
    },
    {
        "kind": "painting",
        "icon": "🧑‍🎨",
        "name": "«Красная комета»",
        "story": "яркая работа художника, исчезнувшего после последней выставки",
        "rarity": "Мифическая картина",
        "start_price": 400_000,
        "income_min": 400_000,
        "income_max": 1_000_000,
    },
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_dt(value: object) -> datetime | None:
    try:
        if not value:
            return None
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


class AuctionManager:
    """Один общий лот, escrow ставок и ежедневный доход коллекции."""

    def __init__(self) -> None:
        self.state: dict = {
            "sequence": 0,
            "active": None,
            "owned_items": {},
        }
        self._lock = asyncio.Lock()
        self._bot = None
        self._get_funds: Callable[[int], int] | None = None
        self._charge: Callable[[int, int], bool] | None = None
        self._refund: Callable[[int, int], None] | None = None
        self._save: Callable[[str], None] | None = None

    def register(
        self,
        dp,
        bot,
        *,
        get_funds: Callable[[int], int],
        charge: Callable[[int, int], bool],
        refund: Callable[[int, int], None],
        save: Callable[[str], None],
    ) -> None:
        self._bot = bot
        self._get_funds = get_funds
        self._charge = charge
        self._refund = refund
        self._save = save

        dp.message.register(self.cmd_auction, Command("auction", "аукцион"))
        dp.message.register(self.cmd_bid, Command("bid", "ставка"))
        dp.message.register(self.cmd_collection, Command("collection", "коллекция", "мояколлекция"))
        dp.callback_query.register(self.cb_auction, F.data.startswith("auction:"))

    def _save_state(self, reason: str) -> None:
        if self._save:
            self._save(reason)

    def export_state(self) -> dict:
        active = self.state.get("active")
        clean_active = None
        if isinstance(active, dict):
            clean_active = dict(active)
            clean_active["participants"] = {
                str(uid): {
                    "name": str(value.get("name", ""))[:120],
                    "bid": max(0, int(value.get("bid", 0) or 0)),
                }
                for uid, value in (active.get("participants") or {}).items()
                if isinstance(value, dict)
            }
        owned = {}
        for uid, items in (self.state.get("owned_items") or {}).items():
            clean_items = []
            for item in items if isinstance(items, list) else []:
                if not isinstance(item, dict):
                    continue
                clean_items.append({
                    "id": str(item.get("id", ""))[:40],
                    "name": str(item.get("name", ""))[:120],
                    "icon": str(item.get("icon", "🏺"))[:8],
                    "rarity": str(item.get("rarity", "Коллекционный предмет"))[:80],
                    "income_daily": max(40_000, min(MAX_ITEM_INCOME, int(item.get("income_daily", 40_000) or 40_000))),
                    "acquired_at": str(item.get("acquired_at", ""))[:50],
                    "next_income_at": str(item.get("next_income_at", ""))[:50],
                    "total_earned": max(0, int(item.get("total_earned", 0) or 0)),
                })
            if clean_items:
                owned[str(uid)] = clean_items[:30]
        return {
            "sequence": max(0, int(self.state.get("sequence", 0) or 0)),
            "active": clean_active,
            "owned_items": owned,
        }

    def load_state(self, data: object) -> None:
        if not isinstance(data, dict):
            return
        self.state["sequence"] = max(0, int(data.get("sequence", 0) or 0))
        active = data.get("active")
        if isinstance(active, dict):
            ends_at = _parse_dt(active.get("ends_at"))
            created_at = _parse_dt(active.get("created_at"))
            if ends_at and created_at and isinstance(active.get("lot"), dict):
                participants = {}
                for uid, value in (active.get("participants") or {}).items():
                    try:
                        if not isinstance(value, dict):
                            continue
                        participants[str(int(uid))] = {
                            "name": str(value.get("name", ""))[:120],
                            "bid": max(0, int(value.get("bid", 0) or 0)),
                        }
                    except (TypeError, ValueError):
                        continue
                self.state["active"] = {
                    "id": str(active.get("id", ""))[:40],
                    "lot": dict(active["lot"]),
                    "created_at": _iso(created_at),
                    "ends_at": _iso(ends_at),
                    "extensions": max(0, min(MAX_EXTENSIONS, int(active.get("extensions", 0) or 0))),
                    "participants": participants,
                    "chat_id": int(active.get("chat_id", 0) or 0),
                    "message_id": int(active.get("message_id", 0) or 0),
                }
        owned = {}
        for uid, items in (data.get("owned_items") or {}).items():
            try:
                uid_s = str(int(uid))
            except (TypeError, ValueError):
                continue
            if not isinstance(items, list):
                continue
            clean = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                try:
                    income = max(40_000, min(MAX_ITEM_INCOME, int(item.get("income_daily", 40_000) or 40_000)))
                except (TypeError, ValueError):
                    income = 40_000
                clean.append({
                    "id": str(item.get("id", ""))[:40],
                    "name": str(item.get("name", ""))[:120],
                    "icon": str(item.get("icon", "🏺"))[:8],
                    "rarity": str(item.get("rarity", "Коллекционный предмет"))[:80],
                    "income_daily": income,
                    "acquired_at": str(item.get("acquired_at", ""))[:50],
                    "next_income_at": str(item.get("next_income_at", ""))[:50],
                    "total_earned": max(0, int(item.get("total_earned", 0) or 0)),
                })
            if clean:
                owned[uid_s] = clean[:30]
        self.state["owned_items"] = owned

    def _keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🚀 +10%", callback_data="auction:raise:10"),
                InlineKeyboardButton(text="🔥 +25%", callback_data="auction:raise:25"),
            ],
            [
                InlineKeyboardButton(text="💰 Как сделать ставку", callback_data="auction:how"),
                InlineKeyboardButton(text="🔄 Обновить", callback_data="auction:refresh"),
            ],
            [InlineKeyboardButton(text="🏛 Моя коллекция", callback_data="auction:collection")],
        ])

    def _lot_card(self, active: dict | None = None) -> str:
        active = active or self.state.get("active")
        if not active:
            return (
                "🏛 <b>Аукционный дом Lumena</b>\n\n"
                "Сейчас активных лотов нет. Напиши <code>аукцион</code>, "
                "чтобы открыть новую торги."
            )
        lot = active["lot"]
        participants = active.get("participants", {})
        highest_uid, highest = self._highest(active)
        ends_at = _parse_dt(active.get("ends_at"))
        remaining = max(0, int((ends_at - _utc_now()).total_seconds())) if ends_at else 0
        minutes, seconds = divmod(remaining, 60)
        current = highest["bid"] if highest else int(lot["start_price"])
        minimum = self._minimum_bid(active)
        leader = html.escape(str(highest.get("name", "—"))) if highest else "пока никто"
        return (
            f"🏛 <b>АУКЦИОННЫЙ ДОМ · ЛОТ {html.escape(str(active['id']))}</b>\n\n"
            f"{lot['icon']} <b>{html.escape(lot['name'])}</b>\n"
            f"<i>{html.escape(lot['rarity'])}: {html.escape(lot['story'])}</i>\n\n"
            f"💰 Текущая ставка: <b>{current:,} LMN</b>\n"
            f"🎯 Следующая ставка: <b>от {minimum:,} LMN</b>\n"
            f"👑 Лидер: <b>{leader}</b>\n"
            f"👥 Участников: <b>{len(participants)}/{MIN_PARTICIPANTS}</b>\n"
            f"⏳ До закрытия: <b>{minutes}м {seconds:02d}с</b>\n\n"
            f"💎 Доход владельцу: <b>{lot['income_daily']:,} LMN/24ч</b>\n"
            "Победитель получает предмет в коллекцию. "
            "Если участников меньше трёх — торги продлятся.\n\n"
            "Ставь через кнопки или команду "
            "<code>ставка 100000</code>."
        )

    @staticmethod
    def _highest(active: dict) -> tuple[str | None, dict | None]:
        participants = active.get("participants", {})
        if not participants:
            return None, None
        uid, value = max(
            participants.items(),
            key=lambda pair: (int(pair[1].get("bid", 0)), int(pair[0])),
        )
        return uid, value

    def _minimum_bid(self, active: dict) -> int:
        _, highest = self._highest(active)
        if not highest:
            return int(active["lot"]["start_price"])
        current = highest["bid"]
        return max(current + MIN_BID_INCREMENT, int(current * 1.10))

    def _new_lot(self) -> dict:
        self.state["sequence"] = int(self.state.get("sequence", 0)) + 1
        template = random.choice(LOT_CATALOG)
        income_daily = random.randint(template["income_min"], template["income_max"])
        return {
            "kind": template["kind"],
            "icon": template["icon"],
            "name": template["name"],
            "story": template["story"],
            "rarity": template["rarity"],
            "start_price": template["start_price"],
            "income_daily": income_daily,
        }

    def _create_active(self, chat_id: int) -> dict:
        now = _utc_now()
        lot = self._new_lot()
        active = {
            "id": f"{self.state['sequence']:04d}",
            "lot": lot,
            "created_at": _iso(now),
            "ends_at": _iso(now + AUCTION_DURATION),
            "extensions": 0,
            "participants": {},
            "chat_id": int(chat_id),
            "message_id": 0,
        }
        self.state["active"] = active
        return active

    async def cmd_auction(self, message: Message) -> None:
        async with self._lock:
            active = self.state.get("active")
            if active and (_parse_dt(active.get("ends_at")) or _utc_now()) <= _utc_now():
                await self._finish_locked()
                active = self.state.get("active")
            if not active:
                active = self._create_active(message.chat.id)
                self._save_state("новый аукционный лот")
            text = self._lot_card(active)
            sent = await message.answer(text, parse_mode="HTML", reply_markup=self._keyboard())
            active["chat_id"] = message.chat.id
            active["message_id"] = sent.message_id
            self._save_state("сохранение карточки аукциона")

    async def cmd_bid(self, message: Message, command: CommandObject | None = None) -> None:
        raw = (
            (command.args or "").strip()
            if command
            else " ".join((message.text or "").split()[1:]).strip()
        )
        if not raw:
            return await message.reply(
                "💰 Укажи ставку: <code>ставка 100000</code>\n"
                "Минимум отображается на карточке аукциона.",
                parse_mode="HTML",
            )
        try:
            amount = int(raw.replace(" ", "").replace(",", ""))
        except (TypeError, ValueError):
            return await message.reply("❌ Ставка должна быть целым числом LMN.")
        result = await self.place_bid(message.from_user.id, message.from_user.full_name, amount)
        await message.reply(result, parse_mode="HTML")

    async def cmd_collection(self, message: Message) -> None:
        await message.reply(self.collection_text(message.from_user.id), parse_mode="HTML")

    async def cb_auction(self, callback: CallbackQuery) -> None:
        parts = (callback.data or "").split(":")
        if len(parts) < 2:
            return await callback.answer("Некорректная кнопка аукциона", show_alert=True)
        action = parts[1]
        if action == "how":
            return await callback.answer(
                "Нажми +10%/+25% или напиши «ставка сумма». Нужны 3 разных участника.",
                show_alert=True,
            )
        if action == "open":
            async with self._lock:
                active = self.state.get("active")
                if active and (_parse_dt(active.get("ends_at")) or _utc_now()) <= _utc_now():
                    await self._finish_locked()
                    active = self.state.get("active")
                if not active:
                    active = self._create_active(callback.message.chat.id)
                    self._save_state("новый лот из меню добычи")
                sent = await callback.message.answer(
                    self._lot_card(active),
                    parse_mode="HTML",
                    reply_markup=self._keyboard(),
                )
                active["chat_id"] = callback.message.chat.id
                active["message_id"] = sent.message_id
                self._save_state("сохранение карточки аукциона")
            return await callback.answer()
        if action == "collection":
            await callback.message.answer(
                self.collection_text(callback.from_user.id),
                parse_mode="HTML",
            )
            return await callback.answer()
        if action == "refresh":
            active = self.state.get("active")
            if not active:
                return await callback.answer("Активного лота нет", show_alert=True)
            try:
                await callback.message.edit_text(
                    self._lot_card(active),
                    parse_mode="HTML",
                    reply_markup=self._keyboard(),
                )
            except Exception:
                pass
            return await callback.answer()
        if action != "raise" or len(parts) != 3 or parts[2] not in {"10", "25"}:
            return await callback.answer("Некорректное действие", show_alert=True)
        active = self.state.get("active")
        if not active:
            return await callback.answer("Аукцион уже завершён", show_alert=True)
        try:
            percent = int(parts[2])
        except ValueError:
            return await callback.answer("Некорректная ставка", show_alert=True)
        current_user_bid = int(
            (active.get("participants", {}).get(str(callback.from_user.id), {}) or {}).get("bid", 0)
        )
        minimum = self._minimum_bid(active)
        amount = max(minimum, int(max(minimum, current_user_bid) * (100 + percent) / 100))
        result = await self.place_bid(
            callback.from_user.id,
            callback.from_user.full_name,
            amount,
        )
        if result.startswith("✅"):
            try:
                await callback.message.edit_text(
                    self._lot_card(self.state.get("active")),
                    parse_mode="HTML",
                    reply_markup=self._keyboard(),
                )
            except Exception:
                pass
        await callback.answer(result.replace("<b>", "").replace("</b>", "")[:180], show_alert=True)

    async def place_bid(self, uid: int, name: str, amount: int) -> str:
        async with self._lock:
            active = self.state.get("active")
            if not active:
                return "❌ Активного аукциона нет. Напиши <code>аукцион</code>."
            if (_parse_dt(active.get("ends_at")) or _utc_now()) <= _utc_now():
                await self._finish_locked()
                return "⏳ Торги уже закрывались. Открой карточку заново командой <code>аукцион</code>."
            if amount <= 0:
                return "❌ Ставка должна быть больше нуля."
            minimum = self._minimum_bid(active)
            previous = int(
                (active.get("participants", {}).get(str(uid), {}) or {}).get("bid", 0)
            )
            if amount < minimum or amount <= previous:
                return f"❌ Минимальная новая ставка: <b>{minimum:,} LMN</b>."
            delta = amount - previous
            if not self._get_funds or not self._charge:
                return "⚠️ Экономика аукциона ещё не подключена."
            if self._get_funds(uid) < delta:
                return (
                    f"❌ Не хватает LMN для повышения на <b>{delta:,}</b>.\n"
                    "Учитываются кошелёк и банк."
                )
            if not self._charge(uid, delta):
                return "❌ Не удалось зарезервировать ставку. Попробуй ещё раз."
            participants = active.setdefault("participants", {})
            participants[str(uid)] = {
                "name": str(name or f"ID {uid}")[:120],
                "bid": amount,
            }
            ends_at = _parse_dt(active["ends_at"]) or _utc_now()
            if ends_at - _utc_now() <= ANTI_SNIPE_WINDOW:
                active["ends_at"] = _iso(_utc_now() + ANTI_SNIPE_EXTENSION)
            self._save_state("ставка на аукционе")
            return (
                f"✅ Ставка принята: <b>{amount:,} LMN</b>\n"
                f"👥 Участников: <b>{len(participants)}/{MIN_PARTICIPANTS}</b>\n"
                "Если тебя перебьют, следующую ставку можно поднять кнопкой."
            )

    async def tick(self) -> None:
        async with self._lock:
            changed = self._pay_due_income_locked()
            active = self.state.get("active")
            if active and (_parse_dt(active.get("ends_at")) or _utc_now()) <= _utc_now():
                await self._finish_locked()
                changed = True
            if changed and self._save:
                self._save("доход коллекции")

    def _pay_due_income_locked(self) -> bool:
        now = _utc_now()
        changed = False
        for uid_s, items in (self.state.get("owned_items") or {}).items():
            try:
                uid = int(uid_s)
            except (TypeError, ValueError):
                continue
            for item in items if isinstance(items, list) else []:
                due = _parse_dt(item.get("next_income_at"))
                if not due or due > now:
                    continue
                base = max(40_000, min(MAX_ITEM_INCOME, int(item.get("income_daily", 40_000))))
                payout = max(40_000, min(MAX_ITEM_INCOME, int(base * random.uniform(0.90, 1.10))))
                if self._refund:
                    self._refund(uid, payout)
                item["total_earned"] = int(item.get("total_earned", 0) or 0) + payout
                item["next_income_at"] = _iso(now + timedelta(days=1))
                changed = True
                if self._bot:
                    try:
                        asyncio.create_task(self._bot.send_message(
                            uid,
                            f"🏛 <b>Доход коллекции</b>\n\n"
                            f"{item.get('icon', '🏺')} <b>{html.escape(item.get('name', 'Предмет'))}</b>\n"
                            f"💰 Начислено: <b>+{payout:,} LMN</b>\n"
                            "Следующий доход — через 24 часа.",
                            parse_mode="HTML",
                        ))
                    except Exception:
                        pass
        return changed

    async def _finish_locked(self) -> None:
        active = self.state.get("active")
        if not active:
            return
        participants = active.get("participants", {})
        if len(participants) < MIN_PARTICIPANTS:
            extensions = int(active.get("extensions", 0) or 0)
            if extensions < MAX_EXTENSIONS:
                active["extensions"] = extensions + 1
                active["ends_at"] = _iso(_utc_now() + timedelta(minutes=3))
                self._save_state("продление аукциона")
                await self._update_card_locked()
                return
            for uid_s, value in participants.items():
                if self._refund:
                    self._refund(int(uid_s), int(value.get("bid", 0) or 0))
            chat_id = active.get("chat_id")
            self.state["active"] = None
            self._save_state("отмена аукциона без участников")
            await self._notify_chat(
                chat_id,
                "🕰 <b>Аукцион закрыт без сделки.</b>\n"
                "Не набралось 3 разных участника — все ставки возвращены.",
            )
            return

        winner_s, winner = self._highest(active)
        if not winner_s or not winner:
            return
        winner_id = int(winner_s)
        now = _utc_now()
        lot = dict(active["lot"])
        owned = self.state.setdefault("owned_items", {}).setdefault(str(winner_id), [])
        owned.append({
            "id": str(active["id"]),
            "name": lot["name"],
            "icon": lot["icon"],
            "rarity": lot["rarity"],
            "income_daily": int(lot["income_daily"]),
            "acquired_at": _iso(now),
            "next_income_at": _iso(now + timedelta(days=1)),
            "total_earned": 0,
        })
        for uid_s, value in participants.items():
            if uid_s != winner_s and self._refund:
                self._refund(int(uid_s), int(value.get("bid", 0) or 0))
        winner_bid = int(winner.get("bid", 0) or 0)
        chat_id = active.get("chat_id")
        self.state["active"] = None
        self._save_state("завершение аукциона")
        await self._notify_chat(
            chat_id,
            f"🏆 <b>Аукцион завершён!</b>\n\n"
            f"{lot['icon']} <b>{html.escape(lot['name'])}</b>\n"
            f"Победитель: <b>{html.escape(str(winner.get('name', winner_id)))}</b>\n"
            f"Финальная ставка: <b>{winner_bid:,} LMN</b>\n"
            f"💎 Доход предмета: <b>{int(lot['income_daily']):,} LMN/24ч</b>",
        )
        if self._bot:
            try:
                await self._bot.send_message(
                    winner_id,
                    f"🏆 <b>Ты выиграл(а) аукцион!</b>\n\n"
                    f"{lot['icon']} <b>{html.escape(lot['name'])}</b>\n"
                    f"Предмет добавлен в <code>коллекция</code>.\n"
                    f"Доход: <b>{int(lot['income_daily']):,} LMN/24ч</b>",
                    parse_mode="HTML",
                )
            except Exception:
                pass

    async def _update_card_locked(self) -> None:
        active = self.state.get("active")
        if not active or not self._bot:
            return
        try:
            await self._bot.edit_message_text(
                self._lot_card(active),
                chat_id=int(active.get("chat_id", 0)),
                message_id=int(active.get("message_id", 0)),
                parse_mode="HTML",
                reply_markup=self._keyboard(),
            )
        except Exception:
            pass

    async def _notify_chat(self, chat_id: object, text: str) -> None:
        if not self._bot or not chat_id:
            return
        try:
            await self._bot.send_message(int(chat_id), text, parse_mode="HTML")
        except Exception:
            pass

    def collection_text(self, uid: int) -> str:
        items = (self.state.get("owned_items") or {}).get(str(uid), [])
        if not items:
            return (
                "🏛 <b>Твоя коллекция пуста</b>\n\n"
                "Участвуй в аукционах: предметы дают от "
                "<b>40 000 до 1 000 000 LMN каждые 24 часа</b>."
            )
        total_income = sum(int(item.get("income_daily", 0) or 0) for item in items)
        lines = [
            "🏛 <b>Твоя коллекция Lumena</b>",
            f"Предметов: <b>{len(items)}</b>",
            f"Потенциальный доход: <b>{total_income:,} LMN/24ч</b>\n",
        ]
        for item in items[:20]:
            lines.append(
                f"{item.get('icon', '🏺')} <b>{html.escape(item.get('name', 'Предмет'))}</b> "
                f"— {int(item.get('income_daily', 0) or 0):,} LMN/24ч"
            )
        if len(items) > 20:
            lines.append(f"\n<i>Ещё предметов: {len(items) - 20}</i>")
        return "\n".join(lines)
