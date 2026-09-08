import asyncio
from html import escape
import logging
import os
from datetime import datetime, timedelta, timezone

import aiosqlite
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)


BOT_TOKEN = os.environ["DATING_BOT_TOKEN"]
DATA_DIR = os.getenv("DATA_DIR", "data")
DB_PATH = os.path.join(DATA_DIR, "dating.sqlite3")
BRAND_NAME = "Lumenora Dating"
DIVIDER = "────────────"
VIP_PRICE_STARS = 100
VIP_DAYS = 30
VIP_PAYLOAD = "lumenora_vip_30d_100stars"

router = Router()


class ProfileForm(StatesGroup):
    name = State()
    age = State()
    city = State()
    gender = State()
    interested_in = State()
    about = State()
    photo = State()


async def db_execute(query: str, params: tuple = ()) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(query, params)
        await db.commit()


async def db_fetchone(query: str, params: tuple = ()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            return await cursor.fetchone()


async def db_fetchall(query: str, params: tuple = ()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            return await cursor.fetchall()


async def init_db() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS profiles (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                name TEXT NOT NULL,
                age INTEGER NOT NULL CHECK(age >= 18 AND age <= 99),
                city TEXT NOT NULL,
                gender TEXT NOT NULL,
                interested_in TEXT NOT NULL,
                about TEXT NOT NULL,
                photo_file_id TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                vip_until TEXT,
                vip_charge_id TEXT,
                boost_until TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS likes (
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                action TEXT NOT NULL CHECK(action IN ('like', 'skip')),
                created_at TEXT NOT NULL,
                PRIMARY KEY (from_user_id, to_user_id)
            );
            CREATE TABLE IF NOT EXISTS matches (
                user_a INTEGER NOT NULL,
                user_b INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (user_a, user_b)
            );
            """
        )
        existing_columns = set()
        async with db.execute("PRAGMA table_info(profiles)") as cursor:
            existing_columns.update(row[1] for row in await cursor.fetchall())
        for column, definition in (
            ("vip_until", "TEXT"),
            ("vip_charge_id", "TEXT"),
            ("boost_until", "TEXT"),
        ):
            if column not in existing_columns:
                await db.execute(f"ALTER TABLE profiles ADD COLUMN {column} {definition}")
        await db.commit()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def plus_days(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def plus_hours(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def is_vip(profile) -> bool:
    if not profile or not profile["vip_until"]:
        return False
    try:
        return datetime.fromisoformat(profile["vip_until"]) > datetime.now(timezone.utc)
    except ValueError:
        return False


def vip_badge(profile) -> str:
    return "✦ VIP" if is_vip(profile) else ""


def vip_until_label(profile) -> str:
    if not is_vip(profile):
        return ""
    until = datetime.fromisoformat(profile["vip_until"]).astimezone()
    return until.strftime("%d.%m.%Y")


def boost_until_label(profile) -> str:
    if not profile or not profile["boost_until"]:
        return ""
    try:
        until = datetime.fromisoformat(profile["boost_until"])
    except ValueError:
        return ""
    if until <= datetime.now(timezone.utc):
        return ""
    return until.astimezone().strftime("%d.%m.%Y %H:%M")


def vip_keyboard(profile) -> InlineKeyboardMarkup:
    buttons = []
    if is_vip(profile):
        buttons.append(
            [InlineKeyboardButton(text="🚀 Поднять анкету на 24 часа", callback_data="menu:boost")]
        )
    else:
        buttons.append(
            [InlineKeyboardButton(text="⭐ Оформить VIP · 100 Stars", callback_data="vip:buy")]
        )
    buttons.append([InlineKeyboardButton(text="← В меню", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def profile_keyboard(profile_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❤️ Нравится", callback_data=f"discover:like:{profile_id}"
                ),
                InlineKeyboardButton(
                    text="→ Дальше", callback_data=f"discover:skip:{profile_id}"
                ),
            ],
            [InlineKeyboardButton(text="× Закрыть подборку", callback_data="discover:stop")],
        ]
    )


def gender_keyboard(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Парень", callback_data=f"{prefix}:парень"),
                InlineKeyboardButton(text="Девушка", callback_data=f"{prefix}:девушка"),
            ],
            [InlineKeyboardButton(text="Неважно", callback_data=f"{prefix}:неважно")],
        ]
    )


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔎 Подборка", callback_data="menu:discover"),
                InlineKeyboardButton(text="👤 Профиль", callback_data="menu:profile"),
            ],
            [
                InlineKeyboardButton(text="💞 Совпадения", callback_data="menu:matches"),
                InlineKeyboardButton(text="⭐ VIP", callback_data="menu:vip"),
            ],
            [
                InlineKeyboardButton(text="🚀 Поднять анкету", callback_data="menu:boost"),
                InlineKeyboardButton(text="✎ Редактировать", callback_data="menu:edit"),
            ],
        ]
    )


def format_profile(profile) -> str:
    name = escape(str(profile["name"]))
    city = escape(str(profile["city"]))
    about = escape(profile["about"] or "Пока ничего не рассказал(а) о себе.")
    badge = f" · {vip_badge(profile)}" if vip_badge(profile) else ""
    return (
        f"<b>{name}, {profile['age']}</b>{badge}\n"
        f"📍 {city}\n\n"
        f"{about}"
    )


async def get_profile(user_id: int):
    return await db_fetchone("SELECT * FROM profiles WHERE user_id = ?", (user_id,))


async def send_menu(message: Message, text: str = "Выбери действие:") -> None:
    await message.answer(
        f"<b>{BRAND_NAME}</b>\n{DIVIDER}\n{text}",
        reply_markup=main_keyboard(),
    )


async def start_form(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(ProfileForm.name)
    await message.answer(
        "<b>Создаём анкету · 1/7</b>\n"
        f"{DIVIDER}\n\n"
        "Как тебя зовут?\n"
        "<i>Имя или никнейм, от 2 до 40 символов.</i>"
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    profile = await get_profile(message.from_user.id)
    if profile:
        await send_menu(
            message,
            f"С возвращением, <b>{escape(profile['name'])}</b>.\n"
            "Выберите, что сделать дальше.",
        )
        return
    await message.answer(
        f"<b>{BRAND_NAME}</b>\n"
        f"{DIVIDER}\n\n"
        "Знакомства без лишнего шума.\n\n"
        "Создайте анкету, смотрите подходящих людей и получайте уведомление "
        "о взаимной симпатии.\n\n"
        "<i>Только для пользователей 18+.</i>"
    )
    await start_form(message, state)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        f"<b>{BRAND_NAME} · помощь</b>\n{DIVIDER}\n"
        "/start — открыть меню\n"
        "/profile — посмотреть свою анкету\n"
        "/search — смотреть анкеты\n"
        "/matches — взаимные симпатии\n"
        "/vip — статус VIP и оплата\n"
        "/edit — заполнить анкету заново\n"
        "/pause — скрыть анкету из поиска\n"
        "/resume — вернуть анкету в поиск"
    )


@router.message(Command("profile"))
async def cmd_profile(message: Message) -> None:
    profile = await get_profile(message.from_user.id)
    if not profile:
        await message.answer("Сначала заполни анкету командой /start.")
        return
    status = "Виден в подборке" if profile["is_active"] else "Скрыт из подборки"
    text = (
        f"<b>Мой профиль</b>\n{DIVIDER}\n\n"
        f"{format_profile(profile)}\n\n"
        f"<i>{status}</i>"
    )
    if profile["photo_file_id"]:
        await message.answer_photo(profile["photo_file_id"], caption=text, reply_markup=main_keyboard())
    else:
        await message.answer(text, reply_markup=main_keyboard())


@router.message(Command("edit"))
async def cmd_edit(message: Message, state: FSMContext) -> None:
    await start_form(message, state)


@router.message(Command("pause"))
async def cmd_pause(message: Message) -> None:
    await db_execute("UPDATE profiles SET is_active = 0, updated_at = ? WHERE user_id = ?", (now_iso(), message.from_user.id))
    await message.answer(
        f"<b>Профиль скрыт</b>\n{DIVIDER}\n"
        "Вы больше не появляетесь в подборке.\n\n"
        "Вернуть профиль можно командой /resume."
    )


@router.message(Command("resume"))
async def cmd_resume(message: Message) -> None:
    await db_execute("UPDATE profiles SET is_active = 1, updated_at = ? WHERE user_id = ?", (now_iso(), message.from_user.id))
    await message.answer(
        f"<b>Профиль снова активен</b>\n{DIVIDER}\n"
        "Вы снова видны в подборке."
    )


@router.message(Command("search"))
async def cmd_search(message: Message) -> None:
    await show_next_profile(message, message.from_user.id)


@router.message(Command("matches"))
async def cmd_matches(message: Message) -> None:
    await show_matches(message, message.from_user.id)


async def show_vip(message: Message) -> None:
    profile = await get_profile(message.from_user.id)
    if not profile:
        await message.answer("Сначала заполни анкету командой /start.")
        return
    if is_vip(profile):
        boost_status = (
            f"Анкета поднята до {boost_until_label(profile)}."
            if boost_until_label(profile)
            else "Подними анкету, чтобы чаще попадаться в начале подборки."
        )
        text = (
            "<b>VIP активен</b>\n"
            f"{DIVIDER}\n\n"
            f"Действует до <b>{vip_until_label(profile)}</b>.\n\n"
            "Возможности:\n"
            "• отметка VIP в профиле\n"
            "• приоритет в подборке\n"
            "• поднятие анкеты на 24 часа\n\n"
            f"<i>{boost_status}</i>"
        )
    else:
        text = (
            "<b>VIP Lumenora</b>\n"
            f"{DIVIDER}\n\n"
            "Больше заметности и аккуратные преимущества в подборке.\n\n"
            "• VIP на 30 дней\n"
            "• отметка VIP в профиле\n"
            "• приоритет в подборке\n"
            "• поднятие анкеты на 24 часа\n\n"
            "<b>100 Telegram Stars</b> · 30 дней"
        )
    await message.answer(text, reply_markup=vip_keyboard(profile))


@router.message(Command("vip"))
async def cmd_vip(message: Message) -> None:
    await show_vip(message)


async def send_vip_invoice(message: Message) -> None:
    profile = await get_profile(message.from_user.id)
    if not profile:
        await message.answer("Сначала заполни анкету командой /start.")
        return
    if is_vip(profile):
        await show_vip(message)
        return
    await message.answer_invoice(
        title="Lumenora VIP",
        description="VIP-доступ к Lumenora Dating на 30 дней.",
        payload=VIP_PAYLOAD,
        currency="XTR",
        prices=[LabeledPrice(label="VIP · 30 дней", amount=VIP_PRICE_STARS)],
    )


async def boost_profile(message: Message) -> None:
    profile = await get_profile(message.from_user.id)
    if not profile:
        await message.answer("Сначала заполни анкету командой /start.")
        return
    if not is_vip(profile):
        await show_vip(message)
        return

    current_boost_until = None
    if profile["boost_until"]:
        try:
            current_boost_until = datetime.fromisoformat(profile["boost_until"])
        except ValueError:
            current_boost_until = None
    base = max(current_boost_until or datetime.now(timezone.utc), datetime.now(timezone.utc))
    boost_until = base + timedelta(hours=24)
    await db_execute(
        "UPDATE profiles SET boost_until = ?, updated_at = ? WHERE user_id = ?",
        (boost_until.isoformat(), now_iso(), message.from_user.id),
    )
    await message.answer(
        "<b>Анкета поднята</b>\n"
        f"{DIVIDER}\n\n"
        f"Ты будешь выше в подборке до <b>{boost_until.astimezone().strftime('%d.%m.%Y %H:%M')}</b>.\n"
        "Когда кто-то откроет подборку, твоя анкета получит приоритет.",
        reply_markup=main_keyboard(),
    )


@router.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery) -> None:
    if query.invoice_payload != VIP_PAYLOAD or query.currency != "XTR" or query.total_amount != VIP_PRICE_STARS:
        await query.answer(
            ok=False,
            error_message="Платёж не прошёл проверку. Открой VIP и попробуй снова.",
        )
        return
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message) -> None:
    payment = message.successful_payment
    if not payment or payment.invoice_payload != VIP_PAYLOAD:
        return
    if payment.currency != "XTR" or payment.total_amount != VIP_PRICE_STARS:
        logging.error(
            "Unexpected VIP payment terms for user_id=%s: currency=%s amount=%s",
            message.from_user.id,
            payment.currency,
            payment.total_amount,
        )
        return
    profile = await get_profile(message.from_user.id)
    if not profile:
        await message.answer("Платёж получен, но профиль не найден. Напиши /start.")
        logging.error("VIP payment without profile for user_id=%s", message.from_user.id)
        return
    if profile["vip_charge_id"] == payment.telegram_payment_charge_id:
        await show_vip(message)
        return

    current_until = None
    if is_vip(profile):
        try:
            current_until = datetime.fromisoformat(profile["vip_until"])
        except ValueError:
            current_until = None
    vip_until = (current_until or datetime.now(timezone.utc)) + timedelta(days=VIP_DAYS)
    await db_execute(
        "UPDATE profiles SET vip_until = ?, vip_charge_id = ?, updated_at = ? WHERE user_id = ?",
        (vip_until.isoformat(), payment.telegram_payment_charge_id, now_iso(), message.from_user.id),
    )
    await message.answer(
        "<b>VIP активирован</b>\n"
        f"{DIVIDER}\n\n"
        f"Действует до <b>{vip_until.astimezone().strftime('%d.%m.%Y')}</b>.\n"
        "Теперь твоя анкета заметнее в подборке.",
        reply_markup=main_keyboard(),
    )


@router.message(ProfileForm.name)
async def form_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not 2 <= len(name) <= 40:
        await message.answer("Имя должно быть от 2 до 40 символов.")
        return
    await state.update_data(name=name)
    await state.set_state(ProfileForm.age)
    await message.answer(
        f"<b>Создаём анкету · 2/7</b>\n{DIVIDER}\n\n"
        "Сколько тебе лет?\n"
        "<i>Участие доступно только с 18 лет.</i>"
    )


@router.message(ProfileForm.age)
async def form_age(message: Message, state: FSMContext) -> None:
    try:
        age = int((message.text or "").strip())
    except ValueError:
        await message.answer("Напиши возраст числом, например: 24.")
        return
    if age < 18:
        await state.clear()
        await message.answer("Этот бот доступен только пользователям 18+.")
        return
    if age > 99:
        await message.answer("Проверь возраст и напиши число от 18 до 99.")
        return
    await state.update_data(age=age)
    await state.set_state(ProfileForm.city)
    await message.answer(
        f"<b>Создаём анкету · 3/7</b>\n{DIVIDER}\n\n"
        "Из какого ты города?"
    )


@router.message(ProfileForm.city)
async def form_city(message: Message, state: FSMContext) -> None:
    city = (message.text or "").strip()
    if not 2 <= len(city) <= 60:
        await message.answer("Напиши город от 2 до 60 символов.")
        return
    await state.update_data(city=city)
    await state.set_state(ProfileForm.gender)
    await message.answer(
        f"<b>Создаём анкету · 4/7</b>\n{DIVIDER}\n\n"
        "Кто ты?",
        reply_markup=gender_keyboard("form_gender"),
    )


@router.callback_query(ProfileForm.gender, F.data.startswith("form_gender:"))
async def form_gender(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(gender=callback.data.split(":", 1)[1])
    await state.set_state(ProfileForm.interested_in)
    await callback.message.edit_text(
        f"<b>Создаём анкету · 5/7</b>\n{DIVIDER}\n\n"
        "Кого хочешь видеть в подборке?",
        reply_markup=gender_keyboard("form_interest"),
    )
    await callback.answer()


@router.message(ProfileForm.gender)
async def form_gender_text(message: Message) -> None:
    await message.answer("Выбери вариант кнопкой выше.")


@router.callback_query(ProfileForm.interested_in, F.data.startswith("form_interest:"))
async def form_interest(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(interested_in=callback.data.split(":", 1)[1])
    await state.set_state(ProfileForm.about)
    await callback.message.edit_text(
        f"<b>Создаём анкету · 6/7</b>\n{DIVIDER}\n\n"
        "Расскажи о себе в 1–3 предложениях.\n"
        "<i>Это увидят в подборке, от 10 до 500 символов.</i>"
    )
    await callback.answer()


@router.message(ProfileForm.interested_in)
async def form_interest_text(message: Message) -> None:
    await message.answer("Выбери вариант кнопкой выше.")


@router.message(ProfileForm.about)
async def form_about(message: Message, state: FSMContext) -> None:
    about = (message.text or "").strip()
    if not 10 <= len(about) <= 500:
        await message.answer("Напиши от 10 до 500 символов.")
        return
    await state.update_data(about=about)
    await state.set_state(ProfileForm.photo)
    skip = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Пропустить", callback_data="form_photo:skip")]]
    )
    await message.answer(
        f"<b>Создаём анкету · 7/7</b>\n{DIVIDER}\n\n"
        "Добавь фото профиля.\n"
        "<i>Фото необязательно — его можно пропустить.</i>",
        reply_markup=skip,
    )


async def save_profile(
    message: Message,
    state: FSMContext,
    photo_file_id: str | None,
    user_id: int | None = None,
    username: str | None = None,
) -> None:
    data = await state.get_data()
    timestamp = now_iso()
    profile_user_id = user_id or message.from_user.id
    profile_username = username if username is not None else message.from_user.username
    await db_execute(
        """
        INSERT INTO profiles(user_id, username, name, age, city, gender, interested_in,
                             about, photo_file_id, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username, name=excluded.name, age=excluded.age,
            city=excluded.city, gender=excluded.gender, interested_in=excluded.interested_in,
            about=excluded.about, photo_file_id=excluded.photo_file_id,
            is_active=1, updated_at=excluded.updated_at
        """,
        (
            profile_user_id,
            profile_username,
            data["name"],
            data["age"],
            data["city"],
            data["gender"],
            data["interested_in"],
            data["about"],
            photo_file_id,
            timestamp,
            timestamp,
        ),
    )
    await state.clear()
    await message.answer(
        f"<b>Профиль опубликован</b>\n{DIVIDER}\n\n"
        "Теперь вы участвуете в подборке и можете смотреть другие анкеты.",
        reply_markup=main_keyboard(),
    )


@router.callback_query(ProfileForm.photo, F.data == "form_photo:skip")
async def form_photo_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await save_profile(
        callback.message,
        state,
        None,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
    )
    await callback.answer()


@router.message(ProfileForm.photo, F.photo)
async def form_photo(message: Message, state: FSMContext) -> None:
    await save_profile(message, state, message.photo[-1].file_id)


@router.message(ProfileForm.photo)
async def form_photo_invalid(message: Message) -> None:
    await message.answer("Пришли фото или нажми кнопку «Пропустить».")


async def compatible_candidates(user_id: int):
    current = await get_profile(user_id)
    if not current:
        return []
    params: list = [user_id, user_id]
    clauses = ["p.user_id != ?", "p.is_active = 1", "p.user_id NOT IN (SELECT to_user_id FROM likes WHERE from_user_id = ?)"]
    if current["interested_in"] != "неважно":
        clauses.append("p.gender = ?")
        params.append(current["interested_in"])
    if current["gender"] != "неважно":
        clauses.append("(p.interested_in = ? OR p.interested_in = 'неважно')")
        params.append(current["gender"])
    query = (
        f"SELECT p.* FROM profiles p WHERE {' AND '.join(clauses)} "
        "ORDER BY CASE WHEN p.boost_until IS NOT NULL AND p.boost_until > ? "
        "THEN 0 ELSE 1 END, RANDOM() LIMIT 1"
    )
    params.append(now_iso())
    return await db_fetchall(query, tuple(params))


async def show_next_profile(target, user_id: int) -> None:
    profile = await get_profile(user_id)
    if not profile:
        await target.answer(
            f"<b>{BRAND_NAME}</b>\n{DIVIDER}\n\n"
            "Сначала создай профиль командой /start."
        )
        return
    candidates = await compatible_candidates(user_id)
    if not candidates:
        await target.answer(
            f"<b>Подборка</b>\n{DIVIDER}\n\n"
            "Новых подходящих анкет пока нет.\n"
            "<i>Загляни позже — подборка обновляется.</i>",
            reply_markup=main_keyboard(),
        )
        return
    candidate = candidates[0]
    caption = f"<b>Подборка</b>\n{DIVIDER}\n\n{format_profile(candidate)}"
    if candidate["photo_file_id"]:
        await target.answer_photo(
            candidate["photo_file_id"],
            caption=caption,
            reply_markup=profile_keyboard(candidate["user_id"]),
        )
    else:
        await target.answer(caption, reply_markup=profile_keyboard(candidate["user_id"]))


async def show_matches(target, user_id: int) -> None:
    matches = await db_fetchall(
        """
        SELECT p.* FROM profiles p
        JOIN matches m ON (m.user_a = ? AND m.user_b = p.user_id)
                         OR (m.user_b = ? AND m.user_a = p.user_id)
        ORDER BY m.created_at DESC LIMIT 20
        """,
        (user_id, user_id),
    )
    if not matches:
        await target.answer(
            f"<b>Совпадения</b>\n{DIVIDER}\n\n"
            "Взаимных симпатий пока нет.\n"
            "<i>Начни с подборки — всё может измениться.</i>",
            reply_markup=main_keyboard(),
        )
        return
    lines = [f"<b>Совпадения</b>\n{DIVIDER}"]
    for match in matches:
        contact = f"@{escape(match['username'])}" if match["username"] else "контакт скрыт"
        lines.append(f"• <b>{escape(match['name'])}, {match['age']}</b> — {contact}")
    await target.answer("\n".join(lines), reply_markup=main_keyboard())


@router.callback_query(F.data == "discover:stop")
async def discover_stop(callback: CallbackQuery) -> None:
    await callback.message.edit_reply_markup(reply_markup=main_keyboard())
    await callback.answer("Поиск остановлен")


@router.callback_query(F.data.regexp(r"^discover:(like|skip):\d+$"))
async def discover_action(callback: CallbackQuery, bot: Bot) -> None:
    if not callback.message:
        await callback.answer()
        return
    _, action, candidate_raw = callback.data.split(":")
    candidate_id = int(candidate_raw)
    if candidate_id == callback.from_user.id or not await get_profile(candidate_id):
        await callback.answer("Эта анкета уже недоступна.", show_alert=True)
        return

    timestamp = now_iso()
    await db_execute(
        """
        INSERT INTO likes(from_user_id, to_user_id, action, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(from_user_id, to_user_id) DO UPDATE SET
            action=excluded.action, created_at=excluded.created_at
        """,
        (callback.from_user.id, candidate_id, action, timestamp),
    )
    await callback.message.edit_reply_markup(reply_markup=None)

    if action == "like":
        reciprocal = await db_fetchone(
            """
            SELECT 1 FROM likes
            WHERE from_user_id = ? AND to_user_id = ? AND action = 'like'
            """,
            (candidate_id, callback.from_user.id),
        )
        if reciprocal:
            user_a, user_b = sorted((callback.from_user.id, candidate_id))
            await db_execute(
                "INSERT OR IGNORE INTO matches(user_a, user_b, created_at) VALUES (?, ?, ?)",
                (user_a, user_b, timestamp),
            )
            await callback.answer("Взаимная симпатия 💞")
            try:
                await bot.send_message(
                    callback.from_user.id,
                    f"<b>Взаимная симпатия</b>\n{DIVIDER}\n\n"
                    "Вы понравились друг другу 💞\n"
                    "Открой /matches, чтобы увидеть контакт.",
                )
                await bot.send_message(
                    candidate_id,
                    f"<b>Взаимная симпатия</b>\n{DIVIDER}\n\n"
                    "Вы понравились друг другу 💞\n"
                    "Открой /matches, чтобы увидеть контакт.",
                )
            except Exception:
                logging.exception("Не удалось отправить уведомление о совпадении")
        else:
            await callback.answer("Симпатия сохранена ❤️")
    else:
        await callback.answer("Пропущено")
    await show_next_profile(callback.message, callback.from_user.id)


@router.callback_query(F.data == "menu:discover")
async def menu_discover(callback: CallbackQuery) -> None:
    await callback.answer()
    await show_next_profile(callback.message, callback.from_user.id)


@router.callback_query(F.data == "menu:profile")
async def menu_profile(callback: CallbackQuery) -> None:
    await callback.answer()
    profile = await get_profile(callback.from_user.id)
    if not profile:
        await callback.message.answer("Сначала создай анкету через /start.")
        return
    status = "Виден в подборке" if profile["is_active"] else "Скрыт из подборки"
    await callback.message.answer(
        f"<b>Мой профиль</b>\n{DIVIDER}\n\n"
        f"{format_profile(profile)}\n\n"
        f"<i>{status}</i>",
        reply_markup=main_keyboard(),
    )


@router.callback_query(F.data == "menu:matches")
async def menu_matches(callback: CallbackQuery) -> None:
    await callback.answer()
    await show_matches(callback.message, callback.from_user.id)


@router.callback_query(F.data == "menu:home")
async def menu_home(callback: CallbackQuery) -> None:
    await callback.answer()
    await send_menu(callback.message)


@router.callback_query(F.data == "menu:vip")
async def menu_vip(callback: CallbackQuery) -> None:
    await callback.answer()
    await show_vip(callback.message)


@router.callback_query(F.data == "vip:buy")
async def vip_buy(callback: CallbackQuery) -> None:
    await callback.answer()
    await send_vip_invoice(callback.message)


@router.callback_query(F.data == "menu:boost")
async def menu_boost(callback: CallbackQuery) -> None:
    await callback.answer()
    await boost_profile(callback.message)


@router.callback_query(F.data == "menu:edit")
async def menu_edit(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await start_form(callback.message, state)


async def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    await init_db()
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())