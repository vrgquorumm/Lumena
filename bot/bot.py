        return False, False, "чат не настроен"
    perms = _ROLE_PERMISSIONS.get(role, {})
    try:
        await bot.promote_chat_member(chat_id, user_id, **perms)
    except Exception as e:
        err = str(e)
        print(f"⚠️ promote_chat_member({user_id}, {role}, chat={chat_id}): {err}")
        return False, False, err
    # Кастомный тег — название роли (максимум 16 символов по ограничению Telegram)
    custom_title = _ROLE_CHAT_TITLE_OVERRIDES.get(
        user_id,
        _ROLE_CHAT_TITLES.get(role, ROLE_NAMES.get(role, role)[:16]),
    )
    try:
        await bot.set_chat_administrator_custom_title(chat_id, user_id, custom_title)
        title_ok = True
        title_err = ""
    except Exception as e:
        title_err = str(e)
        title_ok = False
        print(f"⚠️ set_custom_title({user_id}, '{custom_title}', chat={chat_id}): {title_err}")
    return True, title_ok, title_err


async def _demote_in_chat(user_id: int, chat_id: int | None = None) -> tuple[bool, str]:
    """Снимает все права администратора в чате."""
    if chat_id is None:
        chat_id = MAIN_CHAT_ID
    if not chat_id or user_id is None:
        return False, "чат не настроен"
    try:
        await bot.promote_chat_member(
            chat_id, user_id,
            can_manage_chat=False, can_delete_messages=False,
            can_manage_video_chats=False, can_restrict_members=False,
            can_promote_members=False, can_change_info=False,
            can_invite_users=False, can_pin_messages=False,
        )
        return True, ""
    except Exception as e:
        err = str(e)
        print(f"⚠️ _demote_in_chat({user_id}, chat={chat_id}): {err}")
        return False, err


async def _notify_role_assigned(user_id: int, role: str, assigner_name: str) -> None:
    """Отправляет DM юзеру о назначении роли с ссылкой на чат."""
    # Ролевое приглашение ведёт именно в закрытый админский чат, а не в
    # главный чат.
    chat_link = OBSERVER_CHAT_INVITE_LINK
    role_icon = _ROLE_ICON.get(role, "🔹")
    role_name = ROLE_NAMES.get(role, role)
    try:
        await bot.send_message(
            user_id,
            f"{brand.hdr()}\n\n"
            f"{role_icon} <b>Тебе назначена роль!</b>\n\n"
            f"🏷 Роль: <b>{role_name}</b>\n"
            f"👤 Назначил: <b>{html.escape(assigner_name)}</b>\n\n"
            f"Ты получил права администратора в чате сообщества.\n\n"
            f"🔗 <a href=\"{chat_link}\">Перейти в чат</a>\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        print(f"⚠️ _notify_role_assigned DM to {user_id}: {e}")


async def _notify_role_removed(user_id: int, role: str) -> None:
    """Отправляет DM юзеру о снятии роли."""
    role_name = ROLE_NAMES.get(role, role)
    try:
        await bot.send_message(
            user_id,
            f"{brand.hdr()}\n\n"
            f"🔕 <b>Роль снята</b>\n\n"
            f"🏷 Была роль: <b>{role_name}</b>\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )
    except Exception:
        pass


async def _notify_access_revoked(
    user_id: int, comment: str, assigner_name: str
) -> None:
    """Уведомляет пользователя об отзыве founder-equivalent доступа."""
    try:
        await bot.send_message(
            user_id,
            f"{brand.hdr()}\n\n"
            "⛔ <b>Права разработчика отозваны</b>\n\n"
            f"👤 Решение: <b>{html.escape(assigner_name)}</b>\n"
            f"📝 Комментарий: <i>{html.escape(comment)}</i>\n\n"
            "Founder-доступ, роли и права администратора сняты.\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )
    except Exception:
        pass


@dp.message(Command("снятьправа", "отозватьправа", "revokeaccess"))
async def cmd_revoke_access(msg: Message, command: CommandObject = None):
    """Основной фаундер отзывает весь доступ сотрудника с обязательной причиной."""
    if msg.from_user.id != OWNER_ID:
        return await msg.reply("⛔ Отозвать права может только основной фаундер.")

    raw_args = ((command.args if command else "") or "").strip()
    target = msg.reply_to_message.from_user if msg.reply_to_message else None
    comment = raw_args

    if target is None:
        parts = raw_args.split(maxsplit=1)
        if not parts or not parts[0].lstrip("@").isdigit():
            return await msg.reply(
                "Ответь на сообщение сотрудника и укажи комментарий:\n"
                "<code>/снятьправа причина отзыва</code>\n\n"
                "Или укажи username:\n"
                "<code>/снятьправа 8318351777 причина отзыва</code>",
                parse_mode="HTML",
            )
        target_id = int(parts[0].lstrip("@"))
        comment = parts[1].strip() if len(parts) > 1 else ""
        target_name = str(target_id)
    else:
        target_id = target.id
        target_name = target.full_name

    if target_id == OWNER_ID:
        return await msg.reply("⛔ Нельзя отозвать права у основного фаундера.")
    if len(comment) < 3:
        return await msg.reply(
            "📝 Нужен обязательный комментарий к отзыву прав.",
            parse_mode="HTML",
        )

    old_role = get_role(target_id)
    username = (getattr(target, "username", "") or "").lower().lstrip("@")
    REVOKED_FOUNDER_ACCESS_IDS.add(target_id)
    FOUNDER_ACCESS_REVOCATIONS[target_id] = {
        "comment": comment[:1000],
        "revoked_by": msg.from_user.id,
        "revoked_at": now_kyiv().strftime("%Y-%m-%d %H:%M"),
    }
    remove_role(target_id, username)
    for role_chat_id in _role_sync_chat_ids(msg.chat.id):
        await _demote_in_chat(target_id, role_chat_id)
    save_data()
    await _notify_access_revoked(target_id, comment, msg.from_user.full_name)

    role_text = f"\nБыла роль: {_fmt_role(old_role)}" if old_role else ""
    await msg.reply(
        f"{brand.hdr()}\n\n"
        "✅ <b>Доступ отозван</b>\n\n"
        f"👤 {html.escape(target_name)}\n"
        f"📝 Комментарий: <i>{html.escape(comment)}</i>"
        f"{role_text}\n\n"
        "Сняты founder-права, роль и права администратора в связанных чатах."
        f"\n{brand.div()}",
        parse_mode="HTML",
    )


@dp.message(Command("setrole"))
async def cmd_set_role_slash(msg: Message, command: CommandObject):
    await cmd_set_role(msg, command)


@dp.message(Command("removerole"))
async def cmd_remove_role_slash(msg: Message, command: CommandObject):
    await cmd_remove_role(msg, command)


@dp.message(Command("roles"))
async def cmd_roles_slash(msg: Message):
    await cmd_roles(msg)


async def cmd_set_role(msg: Message, command=None):
    """Назначить роль.
    Фаундер — любую. Lead/co_admin — только admin и moderator.
    Работает: роль @username lead_admin  ИЛИ ответ на сообщение + роль admin"""
    uid = msg.from_user.id
    if not (is_owner(msg) or has_role(
        uid, "founder_deputy", "lead_admin", "co_admin"
    )):
        return await msg.reply("⛔ Только фаундер или главный админ")

    # Получаем сырые аргументы — из CommandObject или из текста сообщения
    if command is not None:
        raw_args = (command.args or "").strip()
    else:
        # Текстовая команда: "роль @username admin"
        parts = (msg.text or "").strip().split(maxsplit=1)
        raw_args = parts[1] if len(parts) > 1 else ""

    args = raw_args.split()
    target = None
    role_raw = ""

    if msg.reply_to_message:
        target = msg.reply_to_message.from_user
        # Пропускаем @упоминания в аргументах — берём первое не-mention слово как роль
        role_raw = next(
            (a.lower() for a in args if not a.startswith("@")), ""
        )
    elif len(args) >= 2:
        username = args[0].lstrip("@")
        role_raw = args[1].lower()
        # Ищем ID по username или имени в chat_members
        found_uid = next(
            (uid for cid_m in chat_members.values()
             for uid in cid_m
             if any(n.lower() == username.lower() for n in [str(uid),
                    next((v for k, v in cid_m.items() if k == uid), "")])),
            None,
        )
        # Упрощённый поиск: ищем по username в _ROLE_USERNAMES или просто сохраняем
        target_id   = found_uid
        target_name = f"@{username}"
    elif len(args) == 1:
        role_raw = args[0].lower()
        if not msg.reply_to_message:
            return await msg.reply(
                "ℹ️ Чтобы назначить роль — ответь на сообщение нужного человека:\n"
                "<code>роль lead_admin</code> (в ответ на его сообщение)\n\n"
                "Или укажи username: <code>роль @username admin</code>",
                parse_mode="HTML",
            )
    else:
        return await msg.reply(
            "👥 <b>Назначение роли</b>\n\n"
            "Ответь на сообщение человека и напиши:\n"
            "<code>роль lead_admin</code>\n"
            "<code>роль co_admin</code>\n"
            "<code>роль admin</code>\n"
            "<code>роль moderator</code>\n\n"
            "Или без reply:\n"
            "<code>роль @username admin</code>",
            parse_mode="HTML",
        )

    role = _ROLE_ALIASES.get(role_raw)
    if not role:
        valid = "  ".join(f"<code>{k}</code>" for k in ROLE_NAMES)
        return await msg.reply(
            f"❓ Неизвестная роль: <code>{html.escape(role_raw)}</code>\n\n"
            f"Доступные:\n{valid}",
            parse_mode="HTML",
        )

    # Проверяем что у вызывающего достаточно прав для этой конкретной роли
    if not _can_manage_role(msg, role):
        allowed = _ROLE_CAN_ASSIGN.get(ROLES.get(msg.from_user.id), set())
        readable = " / ".join(f"<code>{r}</code>" for r in sorted(allowed)) or "—"
        return await msg.reply(
            f"⛔ Ты можешь назначать только: {readable}",
            parse_mode="HTML",
        )

    if msg.reply_to_message:
        u     = msg.reply_to_message.from_user
        uname = (u.username or "").lower().lstrip("@")
        set_role(u.id, role, uname)
        mention = f"@{uname}" if uname else html.escape(u.full_name)
    elif "target_id" in dir():
        uname = username.lower().lstrip("@")
        if target_id:
            set_role(target_id, role, uname)
        else:
            _ROLE_USERNAMES[uname] = role
        mention = f"@{uname}"
    else:
        return

    save_data()

    # Промоут в чате + DM-уведомление
    promoted_uid = None
    if msg.reply_to_message:
        promoted_uid = msg.reply_to_message.from_user.id
    elif "target_id" in dir() and target_id:
        promoted_uid = target_id

    chat_ok = False
    title_ok = False
    chat_err = ""
    if promoted_uid:
        # Одинаковые права в текущем, главном и закрытом админском чатах.
        for role_chat_id in _role_sync_chat_ids(msg.chat.id):
            ok, title, err = await _promote_in_chat(
                promoted_uid, role, role_chat_id
            )
            chat_ok = chat_ok or ok
            title_ok = title_ok or title
            if not ok:
                chat_err = err or chat_err
        assigner = msg.from_user.full_name
        await _notify_role_assigned(promoted_uid, role, assigner)

    if not promoted_uid:
        chat_note = "\n<i>⚠️ ID неизвестен — права выдам автоматически при первом сообщении</i>"
    elif not chat_ok:
        chat_note = f"\n<i>⚠️ Права не выданы: {html.escape(chat_err)}</i>"
    elif not title_ok:
        chat_note = f"\n<i>⚠️ Права выданы, тег не установлен: {html.escape(chat_err)}</i>"
    else:
        chat_note = ""

    tag_display = ROLE_NAMES.get(role, role)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"{_fmt_role(role)} <b>назначена</b>\n\n"
        f"👤 {mention}\n"
        f"🏷 Роль: <b>{tag_display}</b>\n"
        f"💬 Тег в чате: {'<b>' + tag_display + '</b> ✅' if title_ok else '—'}{chat_note}\n"
        f"📩 Уведомление: {'отправлено в ЛС' if promoted_uid else 'отправлю при первом контакте'}\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )


def _normalize_promote_args(raw_args: str, has_reply: bool) -> str:
    """Приводит разговорный формат «до лид админа» к формату /роль."""
    parts = raw_args.strip().split()
    if has_reply:
        target_part = ""
        role_parts = parts
    else:
        if len(parts) < 2:
            return ""
        target_part = parts[0]
        role_parts = parts[1:]

    if role_parts and role_parts[0].casefold() in {"до", "to"}:
        role_parts = role_parts[1:]
    if not role_parts:
        return ""

    role_text = " ".join(role_parts).casefold()
    role_aliases = {
        "лид админ": "lead_admin",
        "лид админа": "lead_admin",
        "лид администратора": "lead_admin",
        "главный админ": "lead_admin",
        "главного админа": "lead_admin",
        "главного администратора": "lead_admin",
        "lead admin": "lead_admin",
        "заместитель фаундера": "founder_deputy",
        "заместителя фаундера": "founder_deputy",
        "заместительфаундера": "founder_deputy",
        "замфау": "founder_deputy",
        "ко админ": "co_admin",
        "ко админа": "co_admin",
        "ко-админ": "co_admin",
        "ко-админа": "co_admin",
        "зам админ": "co_admin",
        "зам админа": "co_admin",
        "заместитель админа": "co_admin",
        "co admin": "co_admin",
        "администратор": "admin",
        "админа": "admin",
        "администраторa": "admin",
        "администратору": "admin",
        "модератора": "moderator",
        "модер": "moderator",
    }
    role = role_aliases.get(role_text) or _ROLE_ALIASES.get(role_text)
    if not role:
        compact_role = "".join(role_parts).casefold()
        role = role_aliases.get(compact_role) or _ROLE_ALIASES.get(compact_role, compact_role)
    return f"{target_part} {role}".strip() if target_part else role


@dp.message(Command("повысить", "повыситьдо", "promote"))
async def cmd_promote(msg: Message, command: CommandObject = None):
    """Разговорный алиас для назначения роли: «повысить до ...»."""
    raw_args = ((command.args if command else "") or "").strip()
    normalized = _normalize_promote_args(
        raw_args,
        bool(getattr(msg, "reply_to_message", None)),
    )
    if not normalized:
        return await msg.reply(
            "👥 <b>Повышение роли</b>\n\n"
            "Ответь на сообщение пользователя:\n"
            "<code>/повысить до лид админа</code>\n"
            "<code>/повысить до админа</code>\n"
            "<code>/повысить до модератора</code>\n\n"
            "Или укажи username:\n"
            "<code>/повысить @username до лид админа</code>",
            parse_mode="HTML",
        )

    class PromoteCommand:
        args = normalized

    await cmd_set_role(msg, PromoteCommand())


async def cmd_remove_role(msg: Message, command=None):
    """Снять роль. Фаундер — любую. Lead/co_admin — только admin и moderator."""
    uid = msg.from_user.id
    if not (is_owner(msg) or has_role(
        uid, "founder_deputy", "lead_admin", "co_admin"
    )):
        return await msg.reply("⛔ Только фаундер или главный админ")

    if command is not None:
        raw_args = (command.args or "").strip().lstrip("@")
    else:
        parts = (msg.text or "").strip().split(maxsplit=1)
        raw_args = parts[1].lstrip("@") if len(parts) > 1 else ""

    if msg.reply_to_message:
        u     = msg.reply_to_message.from_user
        uname = (u.username or "").lower().lstrip("@")
        old   = get_role(u.id)
        if u.id in FIXED_LEAD_ADMIN_IDS:
            return await msg.reply(
                "⛔ Роль Ники закреплена по ID и не может быть снята этой командой."
            )
        # Проверяем что у вызывающего есть право снять эту роль
        if old and not _can_manage_role(msg, old):
            return await msg.reply(f"⛔ Ты не можешь снять роль {_fmt_role(old)}")
        remove_role(u.id, uname)
        save_data()
        for role_chat_id in _role_sync_chat_ids(msg.chat.id):
            await _demote_in_chat(u.id, role_chat_id)
        if old:
            await _notify_role_removed(u.id, old)
        mention = f"@{uname}" if uname else html.escape(u.full_name)
        old_str = f" (была {_fmt_role(old)})" if old else ""
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            f"✅ Роль снята{old_str}\n\n"
            f"👤 {mention}\n"
            f"📩 Пользователь уведомлён в ЛС\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )

    if not raw_args:
        return await msg.reply(
            "Ответь на сообщение или укажи:\n<code>убратьроль @username</code>",
            parse_mode="HTML",
        )

    uname = raw_args.lower()
    found_uid = next(
        (uid for uid, r in ROLES.items()
         if _ROLE_USERNAMES.get(uname) == r and uid in
            {u for cm in chat_members.values() for u in cm}),
        None,
    )
    old = _ROLE_USERNAMES.get(uname)
    _ROLE_USERNAMES.pop(uname, None)
    if found_uid:
        ROLES.pop(found_uid, None)
        for role_chat_id in _role_sync_chat_ids(msg.chat.id):
            await _demote_in_chat(found_uid, role_chat_id)
        if old:
            await _notify_role_removed(found_uid, old)
    save_data()
    old_str = f" (была {_fmt_role(old)})" if old else ""
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"✅ Роль снята{old_str}\n\n"
        f"👤 @{html.escape(uname)}\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )


async def cmd_roles(msg: Message, command=None):
    """Список всех назначенных ролей — фаундер и главные админы."""
    uid = msg.from_user.id
    if not (is_owner(msg) or has_role(
        uid, "founder_deputy", "lead_admin", "co_admin"
    )):
        return await msg.reply("⛔ Только фаундер или главный админ")

    lines = ["👥 <b>Назначенные роли</b>\n"]
    by_role: dict[str, list[str]] = {r: [] for r in ROLE_HIERARCHY}

    seen_unames: set[str] = set()
    for uid, role in ROLES.items():
        if role not in by_role:
            by_role.setdefault(role, [])
        # Имя: ищем в chat_members
        display = "Пользователь"
        for cid_m in chat_members.values():
            if uid in cid_m:
                display = cid_m[uid]
                break
        # Ищем @username
        for uname, r in _ROLE_USERNAMES.items():
            if r == role:
                display = f"@{uname}"
                seen_unames.add(uname)
                break
        by_role[role].append(display)

    # Постоянные роли по ID показываем даже если они не записывались через
    # пользовательскую команду назначения роли.
    for fixed_uid, fixed_role in _fixed_staff_roles():
        if any(str(fixed_uid) in str(item) for item in by_role.get(fixed_role, [])):
            continue
        fixed_name = "Ника" if fixed_uid in FIXED_LEAD_ADMIN_IDS else "Пользователь"
        by_role.setdefault(fixed_role, []).append(
            fixed_name
        )

    # Username-only записи (без ID)
    for uname, role in _ROLE_USERNAMES.items():
        if uname not in seen_unames and role in by_role:
            by_role[role].append(f"@{uname}")

    total = 0
    for role in ROLE_HIERARCHY:
        members = by_role.get(role, [])
        if not members:
            continue
        lines.append(f"\n{_fmt_role(role)}")
        for m in members:
            lines.append(f"  • {html.escape(str(m))}")
            total += 1

    if total == 0:
        lines.append(
            "Нет назначенных ролей.\n\n"
            "<i>Чтобы назначить — ответь на сообщение и напиши:</i>\n"
            "<code>роль lead_admin</code>"
        )
    lines.append(f"\n<i>Фаундер @{OWNER_USERNAME} — всегда активен</i>")
    await msg.reply("\n".join(lines), parse_mode="HTML")


@dp.message(Command("mute"))
async def cmd_mute(msg: Message, command: CommandObject):
    _caller_is_custom = is_custom_muter(msg)
    if not await is_admin(msg) and not _caller_is_custom:
        return await msg.reply("⛔ Только админы")
    chat_id = _command_chat_id(msg)
    if chat_id is None:
        return await msg.reply("❌ Главный чат ещё не связан.")
    user = await get_user(msg, command)
    if not user: return await msg.reply(
        "ℹ️ Ответь на сообщение.\n"
        "Примеры:\n"
        "<code>!мут 30м флуд</code>\n"
        "<code>!мут 2ч спам</code>\n"
        "<code>!мут 7д оскорбления</code>\n"
        "<code>!мут навсегда</code>",
        parse_mode="HTML")
    if user.id == OWNER_ID:
        return await msg.reply("⛔ Нельзя замутить фаундера")
    if user.id in PROTECTED_DEVELOPER_IDS:
        return await msg.reply(
            "🛡️ Нельзя мутить разработчика.",
            parse_mode="HTML",
        )
    if user.id == msg.from_user.id:
        return await msg.reply("⛔ Нельзя замутить себя")
    # Кастомные мутеры могут мутить только своих целей
    if _caller_is_custom and not await is_admin(msg):
        if _username_lower(user) not in _MUTE_TARGETS:
            return await msg.reply("⛔ У тебя нет прав мутить этого пользователя")
    # Снимаем права администратора у цели, если нужно (иначе Telegram вернёт ошибку)
    delta, reason = parse_time_and_reason(command.args or "")
    until = now_kyiv() + delta
    dur_str = _fmt_duration(delta)
    is_perma = delta.days >= 365
    title = f"Мут ♾ навсегда" if is_perma else f"Мут 🔇 на {dur_str}"
    extra = None if is_perma else f"⏰ До {until.strftime('%d.%m.%Y %H:%M')}"
    try:
        muted, soft, mute_error = await _mute_or_soft_mute(chat_id, user.id, until)
        if not muted:
            raise RuntimeError(mute_error)
        if soft:
            title = f"Мягкий мут 🔇 на {dur_str}"
            extra = (
                "Все сообщения администратора будут удаляться автоматически, "
                "включая стикеры, эмодзи, GIF и медиа.\n"
                "🎭 Админ онлайн, но его сообщения отправляются в чёрную дыру."
            )
        _log_mod(chat_id, "soft_mute" if soft else "mute", user.id, msg.from_user.id)
        await msg.reply(
            mod_card(title, user, reason=reason, extra=extra),
            parse_mode="HTML")
    except Exception as e: await msg.reply(f"❌ {e}")


@dp.message(Command("mute1", "мут1"))
async def cmd_mute1(msg: Message, command: CommandObject):
    """Мут на 1 минуту — кастомные мутеры могут применять только к _MUTE_TARGETS."""
    _caller_is_custom = is_custom_muter(msg)
    if not await is_admin(msg) and not _caller_is_custom:
        return await msg.reply("⛔ Только админы")
    chat_id = _command_chat_id(msg)
    if chat_id is None:
        return await msg.reply("❌ Главный чат ещё не связан.")
    user = await get_user(msg, command)
    if not user:
        return await msg.reply(
            "ℹ️ Ответь на сообщение пользователя.\n"
            "Пример: <code>!мут1</code> — мут на 1 минуту",
            parse_mode="HTML")
    if user.id == OWNER_ID:
        return await msg.reply("⛔ Нельзя замутить фаундера")
    if user.id in PROTECTED_DEVELOPER_IDS:
        return await msg.reply(
            "🛡️ Нельзя мутить разработчика.",
            parse_mode="HTML",
        )
    if user.id == msg.from_user.id:
        return await msg.reply("⛔ Нельзя замутить себя")
    if _caller_is_custom and not await is_admin(msg):
        if _username_lower(user) not in _MUTE_TARGETS:
            return await msg.reply("⛔ У тебя нет прав мутить этого пользователя")
    # Снимаем права администратора у цели, если нужно
    delta = timedelta(minutes=1)
    until = now_kyiv() + delta
    _, reason = parse_time_and_reason(command.args or "")
    try:
        muted, soft, mute_error = await _mute_or_soft_mute(chat_id, user.id, until)
        if not muted:
            raise RuntimeError(mute_error)
        _log_mod(chat_id, "soft_mute" if soft else "mute", user.id, msg.from_user.id)
        await msg.reply(
            mod_card(
                "Мягкий мут 🔇 на 1 мин" if soft else "Мут 🔇 на 1 мин",
                user,
                reason=reason,
                extra=(
                    "Все сообщения администратора удаляются автоматически, "
                    "включая стикеры, эмодзи, GIF и медиа.\n"
                    "🎭 Его сообщения отправляются в чёрную дыру."
                    if soft else f"⏰ До {until.strftime('%H:%M')}"
                ),
            ),
            parse_mode="HTML")
    except Exception as e:
        await msg.reply(f"❌ {e}")

@dp.message(Command("unmute"))
async def cmd_unmute(msg: Message, command: CommandObject):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    chat_id = _command_chat_id(msg)
    if chat_id is None: return await msg.reply("❌ Главный чат ещё не связан.")
    user = await get_user(msg, command)
    if not user: return await msg.reply("Ответь на сообщение")
    try:
        if _clear_soft_mute(chat_id, user.id):
            if user.id in admin_mute_snapshots.get(int(chat_id), {}):
                await _restore_admin_mute(chat_id, user.id)
            _log_mod(chat_id, "unmute", user.id, msg.from_user.id)
            return await msg.reply(mod_card("Мягкий мут снят 🔊", user), parse_mode="HTML")
        await bot.restrict_chat_member(
            chat_id,
            user.id,
            permissions=_unmuted_permissions(),
        )
        _log_mod(chat_id, "unmute", user.id, msg.from_user.id)
        await msg.reply(mod_card("Размучен 🔊", user), parse_mode="HTML")
    except Exception as e: await msg.reply(f"❌ {e}")

@dp.message(Command("ban"))
async def cmd_ban(msg: Message, command: CommandObject):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    chat_id = _command_chat_id(msg)
    if chat_id is None: return await msg.reply("❌ Главный чат ещё не связан.")
    user = await get_user(msg, command)
    if not user: return await msg.reply(
        "ℹ️ Ответь на сообщение.\n"
        "Примеры:\n"
        "<code>!бан спам</code>\n"
        "<code>!бан нарушение правил</code>",
        parse_mode="HTML")
    if user.id == OWNER_ID:
        return await msg.reply("⛔ Нельзя забанить фаундера")
    if user.id in PROTECTED_DEVELOPER_IDS:
        return await msg.reply(
            "🛡️ Нельзя банить разработчика.",
            parse_mode="HTML",
        )
    if user.id == msg.from_user.id:
        return await msg.reply("⛔ Нельзя забанить себя")
    if is_super(msg):
        demoted, demote_error = await _demote_if_needed(chat_id, user.id)
        if not demoted:
            return await msg.reply(f"❌ Не удалось снять права администратора: {demote_error}")
    _, reason = parse_time_and_reason(command.args or "")
    try:
        await bot.ban_chat_member(chat_id, user.id)
        _log_mod(chat_id, "ban", user.id, msg.from_user.id)
        await msg.reply(mod_card("Бан 🚫", user, reason=reason), parse_mode="HTML")
    except Exception as e: await msg.reply(f"❌ {e}")

@dp.message(Command("forceban"))
async def cmd_forceban(msg: Message, command: CommandObject):
    if not is_owner(msg): return await msg.reply("⛔ Только @hdrttttttt")
    chat_id = _command_chat_id(msg)
    if chat_id is None: return await msg.reply("❌ Главный чат ещё не связан.")
    user = await get_user(msg, command)
    if not user: return await msg.reply("Ответь на сообщение")
    if user.id in PROTECTED_DEVELOPER_IDS:
        return await msg.reply(
            "🛡️ Нельзя банить разработчика.",
            parse_mode="HTML",
        )
    try:
        await bot.promote_chat_member(chat_id, user.id, can_manage_chat=False,
            can_delete_messages=False, can_manage_video_chats=False,
            can_restrict_members=False, can_promote_members=False,
            can_change_info=False, can_invite_users=False, can_pin_messages=False)
    except: pass
    _, reason = parse_time_and_reason(command.args or "")
    try:
        await bot.ban_chat_member(chat_id, user.id)
        _log_mod(chat_id, "ban", user.id, msg.from_user.id)
        await msg.reply(
            mod_card("Принудительный бан 🔨", user, extra="⚠️ Права сняты", reason=reason),
            parse_mode="HTML")
    except Exception as e: await msg.reply(f"❌ {e}")

@dp.message(Command("forcemute"))
async def cmd_forcemute(msg: Message, command: CommandObject):
    if not is_owner(msg): return await msg.reply("⛔ Только @hdrttttttt")
    chat_id = _command_chat_id(msg)
    if chat_id is None: return await msg.reply("❌ Главный чат ещё не связан.")
    user = await get_user(msg, command)
    if not user: return await msg.reply("Ответь на сообщение")
    if user.id in PROTECTED_DEVELOPER_IDS:
        return await msg.reply(
            "🛡️ Нельзя мутить разработчика.",
            parse_mode="HTML",
        )
    delta, reason = parse_time_and_reason(command.args or "")
    until = now_kyiv() + delta
    dur_str  = _fmt_duration(delta)
    is_perma = delta.days >= 365
    title    = "Принудительный мут ♾ навсегда 🔇" if is_perma else f"Принудительный мут 🔇 на {dur_str}"
    extra2   = None if is_perma else f"До {until.strftime('%d.%m.%Y %H:%M')}"
    try:
        muted, soft, mute_error = await _mute_or_soft_mute(chat_id, user.id, until)
        if not muted:
            raise RuntimeError(mute_error)
        if soft:
            title = "Принудительный мягкий мут 🔇" if is_perma else f"Принудительный мягкий мут 🔇 на {dur_str}"
            extra2 = (
                "Все сообщения администратора удаляются автоматически, "
                "включая стикеры, эмодзи, GIF и медиа."
            )
        _log_mod(chat_id, "soft_mute" if soft else "mute", user.id, msg.from_user.id)
        await msg.reply(
            mod_card(title, user, extra=extra2, reason=reason),
            parse_mode="HTML")
    except Exception as e: await msg.reply(f"❌ {e}")

@dp.message(Command("unban"))
async def cmd_unban(msg: Message, command: CommandObject):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    chat_id = _command_chat_id(msg)
    if chat_id is None: return await msg.reply("❌ Главный чат ещё не связан.")
    user = await get_user(msg, command)
    if not user: return await msg.reply("Укажи ID")
    try:
        await bot.unban_chat_member(chat_id, user.id)
        _log_mod(chat_id, "unban", user.id, msg.from_user.id)
        await msg.reply(mod_card("Разбанен ✅", user), parse_mode="HTML")
    except Exception as e: await msg.reply(f"❌ {e}")

@dp.message(Command("kick"))
async def cmd_kick(msg: Message, command: CommandObject):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    chat_id = _command_chat_id(msg)
    if chat_id is None: return await msg.reply("❌ Главный чат ещё не связан.")
    user = await get_user(msg, command)
    if not user: return await msg.reply("ℹ️ Ответь на сообщение пользователя")
    if user.id == OWNER_ID:
        return await msg.reply("⛔ Нельзя кикнуть фаундера")
    if user.id in PROTECTED_DEVELOPER_IDS:
        return await msg.reply(
            "🛡️ Нельзя кикнуть разработчика.",
            parse_mode="HTML",
        )
    if user.id == msg.from_user.id:
        return await msg.reply("⛔ Нельзя кикнуть себя")
    _, reason = parse_time_and_reason(command.args or "")
    try:
        await bot.ban_chat_member(chat_id, user.id)
        await bot.unban_chat_member(chat_id, user.id)
        _log_mod(chat_id, "kick", user.id, msg.from_user.id)
        await msg.reply(mod_card("Кик 👢", user, reason=reason), parse_mode="HTML")
    except Exception as e: await msg.reply(f"❌ {e}")

@dp.message(Command("warn"))
async def cmd_warn(msg: Message, command: CommandObject):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    chat_id = _command_chat_id(msg)
    if chat_id is None: return await msg.reply("❌ Главный чат ещё не связан.")
    user = await get_user(msg, command)
    if not user: return await msg.reply("Ответь на сообщение")
    if user.id == OWNER_ID:
        return await msg.reply("⛔ Нельзя предупредить фаундера")
    if user.id in PROTECTED_DEVELOPER_IDS:
        return await msg.reply(
            "🛡️ Нельзя выдавать санкции разработчику.",
            parse_mode="HTML",
        )
    if user.id == msg.from_user.id:
        return await msg.reply("⛔ Нельзя предупредить себя")
    chat_id, uid = chat_id, user.id
    warnings_db.setdefault(chat_id, {})
    warnings_db[chat_id][uid] = warnings_db[chat_id].get(uid, 0) + 1
    count = warnings_db[chat_id][uid]
    _, reason = parse_time_and_reason(command.args or "")
    if count >= 3:
        try:
            await bot.ban_chat_member(chat_id, uid)
            _log_mod(chat_id, "ban", uid, msg.from_user.id)
            warnings_db[chat_id][uid] = 0
            await msg.reply(
                mod_card("Бан 🚫 (3 варна)", user, extra="⚠️ Достигнут лимит предупреждений", reason=reason),
                parse_mode="HTML")
        except Exception as e:
            # бан не прошёл — откатываем варн чтобы не было рассинхронизации
            warnings_db[chat_id][uid] = max(0, count - 1)
            await msg.reply(f"❌ Не удалось забанить: {e}")
    else:
        _log_mod(chat_id, "warn", uid, msg.from_user.id)
        await msg.reply(
            mod_card(f"Варн ⚠️ ({count}/3)", user, reason=reason),
            parse_mode="HTML")

@dp.message(Command("unwarn"))
async def cmd_unwarn(msg: Message, command: CommandObject):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    chat_id = _command_chat_id(msg)
    if chat_id is None: return await msg.reply("❌ Главный чат ещё не связан.")
    user = await get_user(msg, command)
    if not user: return await msg.reply("Ответь на сообщение")
    chat_id, uid = chat_id, user.id
    if chat_id in warnings_db and uid in warnings_db[chat_id] and warnings_db[chat_id][uid] > 0:
        warnings_db[chat_id][uid] -= 1
        remaining = warnings_db[chat_id][uid]
        _log_mod(chat_id, "unwarn", uid, msg.from_user.id)
        await msg.reply(
            mod_card("Варн снят ✅", user, extra=f"📊 Осталось предупреждений: {remaining}/3"),
            parse_mode="HTML")
    else:
        await msg.reply(
            mod_card("Снятие варна", user, extra="ℹ️ У пользователя нет варнов"),
            parse_mode="HTML")


# Явные slash-хендлеры для кириллических команд модерации.
# Резервный universal_handler остаётся для клиентов, которые не передают
# кириллическую команду как Telegram MessageEntity bot_command.
@dp.message(Command("мут", "замутить", "замут"))
async def cmd_mute_ru_slash(msg: Message, command: CommandObject):
    return await cmd_mute(msg, command)


@dp.message(Command("бан", "забанить", "забан"))
async def cmd_ban_ru_slash(msg: Message, command: CommandObject):
    return await cmd_ban(msg, command)


@dp.message(Command("форсбан"))
async def cmd_forceban_ru_slash(msg: Message, command: CommandObject):
    return await cmd_forceban(msg, command)


@dp.message(Command("форсмут"))
async def cmd_forcemute_ru_slash(msg: Message, command: CommandObject):
    return await cmd_forcemute(msg, command)


@dp.message(Command("размут"))
async def cmd_unmute_ru_slash(msg: Message, command: CommandObject):
    return await cmd_unmute(msg, command)


@dp.message(Command("разбан"))
async def cmd_unban_ru_slash(msg: Message, command: CommandObject):
    return await cmd_unban(msg, command)


@dp.message(Command("кик"))
async def cmd_kick_ru_slash(msg: Message, command: CommandObject):
    return await cmd_kick(msg, command)


@dp.message(Command("варн"))
async def cmd_warn_ru_slash(msg: Message, command: CommandObject):
    return await cmd_warn(msg, command)


@dp.message(Command("снятьварн"))
async def cmd_unwarn_ru_slash(msg: Message, command: CommandObject):
    return await cmd_unwarn(msg, command)


_MODERATION_SLASH_HANDLERS = {
    "мут": cmd_mute,
    "замутить": cmd_mute,
    "замут": cmd_mute,
    "бан": cmd_ban,
    "забанить": cmd_ban,
    "забан": cmd_ban,
    "форсбан": cmd_forceban,
    "форсмут": cmd_forcemute,
    "размут": cmd_unmute,
    "разбан": cmd_unban,
    "кик": cmd_kick,
    "варн": cmd_warn,
    "снятьварн": cmd_unwarn,
}


def _is_moderation_slash_text(msg: Message) -> bool:
    """Ловит кириллический slash даже без Telegram bot_command entity."""
    text = (msg.text or "").strip()
    if not text.startswith("/"):
        return False
    first = text[1:].split(maxsplit=1)[0].split("@", 1)[0].casefold()
    return first in _MODERATION_SLASH_HANDLERS


@dp.message(F.func(_is_moderation_slash_text))
async def cmd_moderation_slash_fallback(msg: Message):
    """Резервный маршрутизатор модерации для Telegram-клиентов без entity."""
    parts = (msg.text or "").strip()[1:].split(maxsplit=1)
    word = parts[0].split("@", 1)[0].casefold()
    handler = _MODERATION_SLASH_HANDLERS.get(word)
    if not handler:
        return

    class RawSlashCommand:
        args = parts[1] if len(parts) > 1 else ""

    return await handler(msg, RawSlashCommand())


@dp.message(Command("purge"))
async def cmd_purge(msg: Message, command: CommandObject):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    chat_id = _command_chat_id(msg)
    if chat_id is None: return await msg.reply("❌ Главный чат ещё не связан.")
    try: count = min(max(int(command.args or 10), 1), 100)
    except: return await msg.reply("Использование: /purge 20")
    deleted = 0
    async for m in bot.get_chat_history(chat_id, limit=count + 1):
        try: await m.delete(); deleted += 1
        except: pass
    info = await msg.answer(f"🗑 Удалено: {deleted}")
    await asyncio.sleep(3); await info.delete()

@dp.message(Command("ro"))
async def cmd_ro(msg: Message, command: CommandObject):
    if not await is_admin(msg): return await msg.reply("⛔ Только админы")
    chat_id = _command_chat_id(msg)
    if chat_id is None: return await msg.reply("❌ Главный чат ещё не связан.")
    arg = (command.args or "").lower()
    if arg in ("on","1","вкл"):
        perms = ChatPermissions(can_send_messages=False)
        action, icon = "Режим чтения включён", "🔒"
    else:
        perms = ChatPermissions(can_send_messages=True, can_send_media_messages=True,
            can_send_other_messages=True, can_add_web_page_previews=True)
        action, icon = "Режим чтения выключен", "🔓"
    try:
        await bot.set_chat_permissions(chat_id, perms)
        await msg.reply(
            f"{brand.hdr()}\n\n{icon} {action}\n\n{brand.div()}",
    _casino_jackpot_txt = [
        "ТЫ СЛОМАЛ(А) КАЗИНО!! 💎", "это нереально!! x3 🎊🎊🎊",
        "ДЖЕКПОТ! администрация в шоке 👑", "невозможное возможно!! 🎊",
        "легенда чата! джекпот!! 🔥",
    ]
    roll = random.random()
    if roll < 0.45:
        win = bet
        add_balance(uid, win)
        result = f"🟢 ВЫИГРЫШ  +{fmt_lmn(win)} LMN"
        outcome = random.choice(_casino_win_txt)
    elif roll < 0.5:
        win = bet * 3
        add_balance(uid, win)
        result = f"💎 ДЖЕКПОТ  +{fmt_lmn(win)} LMN"
        outcome = random.choice(_casino_jackpot_txt)
    else:
        add_balance(uid, -bet)
        result = f"🔴 ПРОИГРЫШ  -{fmt_lmn(bet)} LMN"
        outcome = random.choice(_casino_loss_txt)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🎰 Казино\n\n"
        f"💰 Ставка: <b>{fmt_lmn(bet)} LMN</b>\n"
        f"🎲 {result}\n\n"
        f"✨ {outcome}\n"
        f"💵 Баланс: <b>{fmt_lmn(get_balance(uid))} LMN</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )
    schedule_state_save("casino")

async def cmd_slots(msg: Message, command: CommandObject):
    if msg.chat.type != "private":
        return await msg.reply(
            f"🎰 Слоты доступны только в личном чате с ботом.\n"
            f"Открой: <a href=\"{CASINO_BOT_URL}\">Lumenora</a>",
            parse_mode="HTML",
        )
    _cur = brand.currency()
    if not command.args: return await msg.reply(brand.get_text("slots_no_bet"), parse_mode="HTML")
    try: bet = int(command.args.split()[0])
    except: return await msg.reply(brand.get_text("slots_invalid_bet"), parse_mode="HTML")
    if bet <= 0: return await msg.reply(brand.get_text("casino_negative_bet"), parse_mode="HTML")
    if get_balance(msg.from_user.id) < bet:
        return await msg.reply(brand.get_text("slots_no_balance", cur=_cur), parse_mode="HTML")
    _slots_jackpot_txt = [
        "ДЖЕКПОТ! ты что, читерил(а)?! 😱", "это невозможно!! 🎊",
        "барабаны в шоке 💎", "три в ряд!! легенда! 🔥",
        "вот это крутануло!! 🎰👑",
    ]
    _slots_pair_txt = [
        "пара есть — уже неплохо 😄", "почти! пара зачтена ✨",
        "два из трёх — уже победа 😊", "пара! монеты твои 💸",
        "неплохо! пара 🍀",
    ]
    _slots_miss_txt = [
        "мимо 😔 барабаны не в настроении", "не сегодня 😅",
        "крути ещё! 🎰", "казино смеётся 😄", "эх, промах...",
        "судьба сказала нет 😔", "барабаны решили иначе 😄",
    ]
    icons = ["🍒","🍋","🍊","🍇","⭐","💎","7️⃣"]
    s = [random.choice(icons) for _ in range(3)]
    line = " | ".join(s)
    uid = msg.from_user.id
    if s[0]==s[1]==s[2]:
        if s[0]=="💎": mult=10
        elif s[0]=="7️⃣": mult=7
        elif s[0]=="⭐": mult=5
        else: mult=3
        win = bet * mult
        add_balance(uid, win)
        result = f"💎 ДЖЕКПОТ x{mult}  +{fmt_lmn(win)} LMN"
        comment = random.choice(_slots_jackpot_txt)
    elif len(set(s))==2:
        win = bet
        add_balance(uid, win)
        result = f"✨ Пара  +{fmt_lmn(win)} LMN"
        comment = random.choice(_slots_pair_txt)
    else:
        add_balance(uid, -bet)
        result = f"😔 Промах  -{fmt_lmn(bet)} LMN"
        comment = random.choice(_slots_miss_txt)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🎰 Слоты\n\n"
        f"┃  {line}  ┃\n\n"
        f"🎲 {result}\n"
        f"💬 {comment}\n"
        f"💵 Баланс: <b>{fmt_lmn(get_balance(uid))} LMN</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

@dp.message(Command("rob"))
async def cmd_rob(msg: Message):
    _cur = brand.currency()
    if not msg.reply_to_message:
        return await msg.reply(brand.get_text("rob_no_reply"), parse_mode="HTML")
    robber = msg.from_user
    victim = msg.reply_to_message.from_user
    if victim.id == robber.id:
        return await msg.reply(brand.get_text("rob_self"), parse_mode="HTML")
    if victim.is_bot:
        return await msg.reply(brand.get_text("rob_bot"), parse_mode="HTML")
    # Перевіряємо баланс гаманця жертви ДО кулдауну — не витрачаємо спробу
    vic_bal  = get_balance(victim.id)
    vic_bank = get_bank(victim.id)
    if vic_bal < 100:
        if vic_bank > 0:
            return await msg.reply(
                f"{brand.hdr()}\n\n"
                f"🏦 <b>{html.escape(victim.full_name)}</b> сохранил(а) монеты в банке!\n\n"
                f"<i>Кошелёк почти пуст, но банк защищён от ограбления.</i>\n\n"
                f"{brand.div()}",
                parse_mode="HTML",
            )
        return await msg.reply(brand.get_text("rob_target_poor"), parse_mode="HTML")
    now = now_kyiv()
    last = rob_cooldown.get(robber.id)
    if last and (now - last).total_seconds() < 7200:
        mins_left = 120 - int((now - last).total_seconds()) // 60
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            f"⏳ Полиция ещё ищет тебя!\n\n"
            f"Следующее ограбление через <b>{mins_left} мин</b>\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )
    rob_cooldown[robber.id] = now
    _rob_win_txt = [
        "тихо, быстро, чисто 🦹", "как в кино 😄 ограбление века",
        "жертва даже не заметила 🤫", "профессионально!",
        "стремительно и без следов 🕶",
        "мастер-класс по карманному делу 😄",
    ]
    _rob_fail_txt = [
        "схватили за руку 🚔", "охрана не спала 😅",
        "план провалился. штраф выписан 😔",
        "камеры везде! попался(лась) 📸",
        "жертва оказалась бывшим полицейским 😬",
        "не повезло. штрафуют 😔",
    ]
    if random.random() < 0.4:
        # Гарантируем корректный диапазон: минимум 50, но не больше трети баланса
        max_steal = max(50, min(vic_bal // 3, 5000))
        stolen = random.randint(1, max_steal)
        add_balance(victim.id, -stolen)
        add_balance(robber.id, stolen)
        comment = random.choice(_rob_win_txt)
        await msg.reply(
            f"{brand.hdr()}\n\n"
            f"🦹 Ограбление удалось!\n\n"
            f"🎯 Жертва: <b>{victim.full_name}</b>\n"
            f"💰 Украдено: <b>{fmt_lmn(stolen)} LMN</b>\n"
            f"💬 {comment}\n\n"
            f"{brand.div()}",
            parse_mode="HTML")
        # Уведомляем жертву
        try:
            await bot.send_message(
                msg.chat.id,
                f"😱 <b>{victim.full_name}</b>, тебя только что обокрал(а) <b>{robber.full_name}</b>!\n"
                f"Пропало: <b>{fmt_lmn(stolen)} LMN</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass
    else:
        robber_bal = get_balance(robber.id)
        fine = random.randint(100, 500)
        actual_fine = min(fine, robber_bal)
        add_balance(robber.id, -actual_fine)
        comment = random.choice(_rob_fail_txt)
        await msg.reply(
            f"{brand.hdr()}\n\n"
            f"👮 Попался!\n\n"
            f"💬 {comment}\n"
            f"💸 Штраф: <b>{fmt_lmn(actual_fine)} LMN</b>\n\n"
            f"{brand.div()}",
            parse_mode="HTML")

# ═══════════════════════════════════════════════════════
# БАНК — захист монет від ограбування
# ═══════════════════════════════════════════════════════
def get_bank(uid: int) -> int:
    return bank_balances.get(uid, 0)


BANK_TERM_APR = 0.10


def _parse_bank_datetime(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=KYIV_TZ)
        return parsed.astimezone(KYIV_TZ)
    except (TypeError, ValueError):
        return None


def _term_interest(uid: int, now: datetime | None = None) -> int:
    record = bank_term_deposits.get(uid)
    if not record:
        return 0
    principal = max(0, int(record.get("principal", 0) or 0))
    started = _parse_bank_datetime(record.get("started_at"))
    if principal <= 0 or not started:
        return 0
    elapsed_seconds = max(0, ((now or now_kyiv()) - started).total_seconds())
    return int(principal * BANK_TERM_APR * elapsed_seconds / (365 * 24 * 3600))


def _bank_keyboard(uid: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="💎 Вклад 10% годовых", callback_data="bank:term:offer"),
            InlineKeyboardButton(text="💰 Сохранить всё", callback_data="bank:save"),
        ],
        [
            InlineKeyboardButton(text="📤 Как снять", callback_data="bank:withdraw:help"),
            InlineKeyboardButton(text="🔄 Обновить", callback_data="bank:card"),
        ],
    ]
    if uid in bank_term_deposits:
        rows.insert(1, [
            InlineKeyboardButton(text="✨ Забрать проценты", callback_data="bank:term:claim"),
            InlineKeyboardButton(text="🔓 Закрыть вклад", callback_data="bank:term:close"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _bank_card_text(uid: int) -> str:
    wallet = get_balance(uid)
    vault = get_bank(uid)
    term = bank_term_deposits.get(uid)
    principal = int(term.get("principal", 0) or 0) if term else 0
    interest = _term_interest(uid) if term else 0
    term_line = (
        f"💎 Вклад: <b>{fmt_lmn(principal)}</b> · "
        f"начислено <b>+{fmt_lmn(interest)}</b>"
        if term else "💎 Вклад: <b>нет</b>"
    )
    return (
        f"{brand.hdr()}\n\n"
        f"🏦 <b>Твой банк</b>\n\n"
        f"💳 Кошелёк: <b>{fmt_lmn(wallet)}</b> {brand.currency()}\n"
        f"🏦 В банке:  <b>{fmt_lmn(vault)}</b> {brand.currency()}\n"
        f"{term_line}\n"
        f"💰 Всего:    <b>{fmt_lmn(wallet + vault + principal)}</b> {brand.currency()}\n\n"
        f"<i>Деньги в обычном банке нельзя украсть через ограбление.</i>\n"
        f"<i>Вклад начисляет 10% годовых пропорционально времени.</i>\n\n"
        f"<code>сохранить</code> — перевести весь кошелёк в обычный банк\n"
        f"<code>снять 1000</code> — вывести из обычного банка\n\n"
        f"{brand.div()}"
    )


async def _bank_card(msg: Message):
    uid = msg.from_user.id
    await msg.reply(
        _bank_card_text(uid),
        parse_mode="HTML",
        reply_markup=_bank_keyboard(uid),
    )


def _move_wallet_to_bank(uid: int) -> int:
    amount = get_balance(uid)
    if amount <= 0:
        return 0
    add_balance(uid, -amount)
    bank_balances[uid] = get_bank(uid) + amount
    return amount


async def _bank_deposit(msg: Message, args_text: str = ""):
    uid = msg.from_user.id
    # «сохранить» всегда кладёт в банк весь доступный баланс.
    # Аргументы игнорируются намеренно — это исключает частичные переводы.
    amount = _move_wallet_to_bank(uid)
    if amount <= 0:
        return await msg.reply(
            "❌ В кошельке нет монет, которые можно сохранить.",
            parse_mode="HTML",
        )
    save_data()
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🏦 <b>Баланс сохранён!</b>\n\n"
        f"➕ В банк переведено: <b>{fmt_lmn(amount)}</b> {brand.currency()}\n"
        f"💳 Кошелёк: <b>{fmt_lmn(get_balance(uid))}</b>\n"
        f"🏦 В банке:  <b>{fmt_lmn(get_bank(uid))}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )

async def _bank_withdraw(msg: Message, args_text: str = ""):
    uid   = msg.from_user.id
    vault = get_bank(uid)
    now   = now_kyiv()
    # Кулдаун 2 часа — чтобы нельзя было мгновенно вывести деньги при ограблении
    last_wd = bank_withdraw_cd.get(uid)
    if last_wd and (now - last_wd).total_seconds() < 7200:
        mins = 120 - int((now - last_wd).total_seconds()) // 60
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            f"⏳ Следующее снятие через <b>{mins} мин</b>\n\n"
            f"<i>Кулдаун защищает от мгновенного вывода при ограблении</i>\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )
    raw = args_text.strip().replace(" ", "").replace(",", "")
    if raw.lower() in ("все", "all", "усе", "max"):
        amount = vault
    elif raw.isdigit():
        amount = int(raw)
    else:
        return await msg.reply(
            f"{brand.hdr()}\n\n🏦 <b>Снятие из банка</b>\n\n"
            f"🏦 В банке: <b>{fmt_lmn(vault)}</b>\n\n"
            f"Укажи сумму: <code>снять 1000</code> или <code>снять всё</code>\n\n"
            f"{brand.div()}",
            parse_mode="HTML",
        )
    if amount <= 0:
        return await msg.reply("❌ Сумма должна быть больше 0.", parse_mode="HTML")
    if amount > vault:
        return await msg.reply(
            f"❌ В банке только <b>{fmt_lmn(vault)}</b> {brand.currency()}",
            parse_mode="HTML",
        )
    bank_balances[uid] = vault - amount
    add_balance(uid, amount)
    bank_withdraw_cd[uid] = now
    save_data()
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🏦 <b>Снятие выполнено!</b>\n\n"
        f"➖ Снято: <b>{fmt_lmn(amount)}</b> {brand.currency()}\n"
        f"💳 Кошелёк: <b>{fmt_lmn(get_balance(uid))}</b>\n"
        f"🏦 В банке:  <b>{fmt_lmn(get_bank(uid))}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )


def _term_offer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Вложить весь кошелёк", callback_data="bank:term:confirm")],
        [InlineKeyboardButton(text="◀️ Назад в банк", callback_data="bank:card")],
    ])


async def _bank_term_confirm(cb: CallbackQuery) -> None:
    uid = cb.from_user.id
    wallet = get_balance(uid)
    if uid in bank_term_deposits:
        return await cb.answer(
            "У тебя уже есть вклад. Сначала забери проценты или закрой его.",
            show_alert=True,
        )
    if wallet <= 0:
        return await cb.answer("В кошельке нет LMN для вклада.", show_alert=True)
    bank_term_deposits[uid] = {
        "principal": wallet,
        "started_at": now_kyiv().isoformat(),
    }
    add_balance(uid, -wallet)
    schedule_state_save("открытие вклада")
    await cb.message.edit_text(
        _bank_card_text(uid) + "\n\n✅ <b>Вклад открыт!</b>",
        parse_mode="HTML",
        reply_markup=_bank_keyboard(uid),
    )
    await cb.answer("Вклад открыт под 10% годовых")


@dp.callback_query(F.data.startswith("bank:"))
async def cb_bank_actions(cb: CallbackQuery):
    parts = (cb.data or "").split(":")
    if len(parts) < 2:
        return await cb.answer("Некорректная кнопка банка", show_alert=True)
    action = parts[1]
    uid = cb.from_user.id

    if action == "card" and len(parts) == 2:
        await cb.message.edit_text(
            _bank_card_text(uid),
            parse_mode="HTML",
            reply_markup=_bank_keyboard(uid),
        )
        return await cb.answer()

    if action == "save" and len(parts) == 2:
        amount = _move_wallet_to_bank(uid)
        if amount <= 0:
            return await cb.answer("В кошельке нет монет для сохранения.", show_alert=True)
        schedule_state_save("сохранение через кнопку банка")
        await cb.message.edit_text(
            _bank_card_text(uid) + f"\n\n✅ В обычный банк переведено <b>{fmt_lmn(amount)} LMN</b>.",
            parse_mode="HTML",
            reply_markup=_bank_keyboard(uid),
        )
        return await cb.answer("Деньги сохранены")

    if action == "withdraw" and len(parts) == 3 and parts[2] == "help":
        return await cb.answer(
            "Для снятия напиши: «снять 1000» или «снять всё». Кулдаун — 2 часа.",
            show_alert=True,
        )

    if action != "term" or len(parts) != 3:
        return await cb.answer("Некорректное действие банка", show_alert=True)

    term_action = parts[2]
    if term_action == "offer":
        wallet = get_balance(uid)
        return await cb.message.edit_text(
            f"{brand.hdr()}\n\n"
            "💎 <b>Срочный вклад Lumenora</b>\n\n"
            "Положи весь кошелёк под <b>10% годовых</b>.\n"
            "Доход считается посекундно и растёт каждый день.\n\n"
            f"💳 Сейчас в кошельке: <b>{fmt_lmn(wallet)} LMN</b>\n"
            "✨ Проценты можно забирать отдельно, не трогая тело вклада.\n"
            "🔓 Закрытие вернёт тело вклада и весь накопленный доход.",
            parse_mode="HTML",
            reply_markup=_term_offer_keyboard(),
        )
    if term_action == "confirm":
        return await _bank_term_confirm(cb)
    if term_action == "claim":
        record = bank_term_deposits.get(uid)
        if not record:
            return await cb.answer("Активного вклада нет.", show_alert=True)
        interest = _term_interest(uid)
        if interest <= 0:
            return await cb.answer("Проценты ещё не накопились.", show_alert=True)
        add_balance(uid, interest)
        record["started_at"] = now_kyiv().isoformat()
        schedule_state_save("получение процентов по вкладу")
        await cb.message.edit_text(
            _bank_card_text(uid) + f"\n\n✨ Получено процентов: <b>+{fmt_lmn(interest)} LMN</b>.",
            parse_mode="HTML",
            reply_markup=_bank_keyboard(uid),
        )
        return await cb.answer(f"+{fmt_lmn(interest)} LMN процентов")
    if term_action == "close":
        record = bank_term_deposits.get(uid)
        if not record:
            return await cb.answer("Активного вклада нет.", show_alert=True)
        principal = max(0, int(record.get("principal", 0) or 0))
        interest = _term_interest(uid)
        bank_term_deposits.pop(uid, None)
        add_balance(uid, principal + interest)
        schedule_state_save("закрытие вклада")
        await cb.message.edit_text(
            _bank_card_text(uid)
            + f"\n\n🔓 Вклад закрыт. Возвращено: <b>{fmt_lmn(principal + interest)} LMN</b>.",
            parse_mode="HTML",
            reply_markup=_bank_keyboard(uid),
        )
        return await cb.answer("Вклад закрыт")
    return await cb.answer("Некорректное действие вклада", show_alert=True)


@dp.message(Command("bank", "банк"))
async def cmd_bank_slash(msg: Message):
    await _bank_card(msg)

@dp.message(Command("save", "сохранить"))
async def cmd_deposit_slash(msg: Message, command: CommandObject = None):
    await _bank_deposit(msg)

@dp.message(Command("withdraw", "снять", "вывести"))
async def cmd_withdraw_slash(msg: Message, command: CommandObject = None):
    await _bank_withdraw(msg, (command.args or "") if command else "")


auction_manager.register(
    dp,
    bot,
    get_funds=_auction_get_funds,
    charge=_auction_charge,
    refund=_auction_refund,
    save=schedule_state_save,
)


@dp.message(Command("richest"))
async def cmd_richest(msg: Message):
    _cur = brand.currency()
    empty_msg = brand.get_text("richest_empty")
    # Объединяем кошельки + банк для полного богатства
    all_uids = set(lmn_balances) | set(bank_balances)
    if not all_uids: return await msg.reply(empty_msg, parse_mode="HTML")
    chat_uids = set(chat_members.get(msg.chat.id, {}))
    if chat_uids:
        all_uids = all_uids & chat_uids
    if not all_uids:
        return await msg.reply(empty_msg, parse_mode="HTML")
    totals = {uid: lmn_balances.get(uid, 0) + bank_balances.get(uid, 0) for uid in all_uids}
    top = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:10]
    medals = ["🥇","🥈","🥉"] + ["4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines = [
        f"{brand.hdr()}\n",
        brand.get_text("richest_header"),
        f"{brand.div()}",
    ]
    for i, (uid, total) in enumerate(top):
        try:
            m = await bot.get_chat_member(msg.chat.id, uid)
            name = html.escape(m.user.full_name)
        except: name = f"ID {uid}"
        wallet = lmn_balances.get(uid, 0)
        bank   = bank_balances.get(uid, 0)
        detail = f" (🏦{fmt_lmn(bank)})" if bank > 0 else ""
        lines.append(f"{medals[i]} <b>{name}</b>  —  {fmt_lmn(wallet)} {_cur}{detail}")
    lines.append(f"\n{brand.div()}")
    lines.append(brand.get_text("richest_total", total=fmt_lmn(sum(totals.values())), cur=_cur))
    await msg.reply("\n".join(lines), parse_mode="HTML")

@dp.message(Command("givetoadmins"))
async def cmd_givetoadmins(msg: Message):
    if not is_super(msg): return await msg.reply("⛔ Только фаундер или суперпользователь")
    try:
        admins = await bot.get_chat_administrators(msg.chat.id)
        lines = []
        for admin in admins:
            if admin.user.is_bot:
                continue
            add_balance(admin.user.id, 2_000_000)
            # Определяем роль
            title = (getattr(admin, "custom_title", None) or "").strip()
            if admin.status == ChatMemberStatus.CREATOR:
                role = "👑 Фаундер"
            elif title:
                role = f"🔰 {title}"
            else:
                role = "🛡 Админ"
            lines.append(f"{role} — {admin.user.full_name}")
        count = len(lines)
        roster = "\n".join(lines) if lines else "—"
        await msg.reply(
            f"💰 <b>Раздача 2 000 000 LMN</b> ({count} чел.):\n\n{roster}",
            parse_mode="HTML"
        )
    except Exception as e: await msg.reply(f"❌ {e}")

def _medal_help() -> str:
    return (
        "🏅 <b>Выдача медали</b>\n\n"
        "Ответом на сообщение пользователя:\n"
        "<code>/медалька Активный участник | За помощь команде</code>\n\n"
        "Или по username:\n"
        "<code>/медалька @username Активный участник | За помощь команде</code>"
    )


async def _resolve_medal_target(msg: Message, target_ref: str = ""):
    """Возвращает (id, имя, username) для медали."""
    replied = getattr(msg, "reply_to_message", None)
    replied_user = getattr(replied, "from_user", None)
    if replied_user and not target_ref:
        return replied_user.id, replied_user.full_name, replied_user.username or ""

    target_ref = target_ref.strip().lstrip("@")
    if not target_ref:
        return None
    if target_ref.isdigit():
        target_id = int(target_ref)
        record = _known_user_records().get(target_id, {})
        return (
            target_id,
            record.get("full_name") or f"ID {target_id}",
            record.get("username", ""),
        )

    target_lower = target_ref.casefold()
    for target_id, record in _known_user_records().items():
        if str(record.get("username", "")).casefold() == target_lower:
            return (
                target_id,
                record.get("full_name") or target_ref,
                record.get("username", target_ref),
            )

    try:
        target = await bot.get_chat(f"@{target_ref}")
        return target.id, target.full_name or target_ref, target.username or target_ref
    except Exception:
        return None


@dp.message(Command("медалька", "медальку", "medal"))
async def cmd_founder_medal(msg: Message, command: CommandObject = None):
    if not is_owner(msg):
        return await msg.reply("⛔ Выдавать медали может только фаундер.")

    raw_args = ((command.args if command else "") or "").strip()
    replied_user = getattr(getattr(msg, "reply_to_message", None), "from_user", None)
    if replied_user:
        target = await _resolve_medal_target(msg)
        medal_text = raw_args
    else:
        parts = raw_args.split(maxsplit=1)
        if len(parts) < 2:
            return await msg.reply(_medal_help(), parse_mode="HTML")
        target = await _resolve_medal_target(msg, parts[0])
        medal_text = parts[1].strip()

    if not target:
        return await msg.reply(
            "❌ Не удалось найти пользователя. Ответь командой на его сообщение "
            "или укажи корректный @username."
        )

    title, separator, description = medal_text.partition("|")
    title = title.strip()[:100]
    description = (
        description.strip()[:300]
        if separator
        else "За вклад в развитие сообщества Lumenora."
    )
    if not title:
        return await msg.reply(
            "❌ Укажи название медали.\n\n" + _medal_help(),
            parse_mode="HTML",
        )

    target_id, target_name, target_username = target
    medal = {
        "title": title,
        "description": description,
        "issuer_id": msg.from_user.id,
        "chat_id": msg.chat.id,
        "created_at": now_kyiv().isoformat(timespec="seconds"),
    }
    founder_medals.setdefault(int(target_id), []).insert(0, medal)
    founder_medals[int(target_id)] = founder_medals[int(target_id)][:50]
    if target_name:
        chat_members.setdefault(msg.chat.id, {})[int(target_id)] = target_name
    schedule_state_save("выдача медали фаундером")

    safe_name = html.escape(target_name or target_username or str(target_id))
    mention = f'<a href="tg://user?id={target_id}">{safe_name}</a>'
    await msg.reply(
        f"🏅 Медаль <b>«{html.escape(title)}»</b> выдана {mention}!\n"
        f"💬 {html.escape(description)}",
        parse_mode="HTML",
    )

    try:
        await bot.send_message(
            int(target_id),
            "🏅 <b>Тебе выдали медаль!</b>\n\n"
            f"🎖 <b>{html.escape(title)}</b>\n"
            f"💬 {html.escape(description)}",
            parse_mode="HTML",
        )
    except Exception:
        # Пользователь мог ещё не открыть личный чат с ботом.
        pass


async def cmd_medals(msg: Message):
    uid = msg.from_user.id
    medals = founder_medals.get(uid, [])
    if not medals:
        return await msg.reply("🏅 У тебя пока нет медалей от фаундера.")

    lines = [
        f"{brand.hdr()}\n\n🏅 <b>Мои медали · "
        f"{html.escape(msg.from_user.first_name or 'участник')}</b>\n\n{brand.div()}"
    ]
    for medal in medals:
        lines.append(
            f"🏅 <b>{html.escape(medal['title'])}</b>\n"
            f"💬 {html.escape(medal.get('description', ''))}"
        )
    lines.append(f"\n{brand.div()}")
    await msg.reply("\n\n".join(lines), parse_mode="HTML")


async def cmd_award(msg: Message, command: CommandObject = None):
    """Фаундер даёт монеты юзеру по @username и пишет сообщение с упоминанием."""
    if not is_owner(msg):
        return await msg.reply("⛔ Только фаундер")
    if not (command and command.args):
        return await msg.reply(
            "Использование: <b>наградить @username [сумма] [текст]</b>\n"
            "Пример: <i>наградить @VladMish11 300000000000000 за лучшую роль клоуна</i>",
            parse_mode="HTML"
        )

    parts = command.args.strip().split(maxsplit=2)
    if len(parts) < 2:
        return await msg.reply("❌ Укажи @username и сумму")

    raw_username = parts[0].lstrip("@")
    try:
        amount = int(parts[1])
    except ValueError:
        return await msg.reply("❌ Сумма должна быть целым числом")
    if amount <= 0:
        return await msg.reply("❌ Сумма должна быть больше нуля")
    custom_text = parts[2] if len(parts) > 2 else ""

    # Ищем юзера — сначала в администраторах чата, затем через Telegram API
    target_id: int | None = None
    target_name: str = raw_username

    try:
        admins = await bot.get_chat_administrators(msg.chat.id)
        for a in admins:
            if (a.user.username or "").lower() == raw_username.lower():
                target_id = a.user.id
                target_name = a.user.full_name
                break
    except Exception:
        pass

    # Если не нашли среди админов — ищем в chat_members
    if target_id is None:
        for uid, name in chat_members.get(msg.chat.id, {}).items():
            # chat_members хранит full_name, username там нет — пробуем через get_chat_member
            pass

    # Попытка через Telegram API по username
    if target_id is None:
        try:
            chat_info = await bot.get_chat(f"@{raw_username}")
            target_id = chat_info.id
            target_name = chat_info.full_name or raw_username
        except Exception:
            pass

    if target_id is None:
        return await msg.reply(
            f"❌ Не удалось найти пользователя <b>@{raw_username}</b>.\n"
            f"Убедись что он писал в чате или что username указан верно.",
            parse_mode="HTML"
        )

    add_balance(target_id, amount)
    # Добавляем в базу участников чата
    chat_members.setdefault(msg.chat.id, {})[target_id] = target_name
    save_data()

    mention = f'<a href="tg://user?id={target_id}">{target_name}</a>'
    text_part = f" {custom_text}" if custom_text else ""
    await msg.answer(
        f"🏆 {mention}{text_part}!\n"
        f"💰 Начислено: <b>{fmt_lmn(amount)} LMN</b>",
        parse_mode="HTML"
    )

async def cmd_give_role(msg: Message, command: CommandObject = None):
    """Фаундер начисляет монеты всем с определённой ролью (custom_title)."""
    if not is_owner(msg):
        return await msg.reply("⛔ Только фаундер")
    if not (command and command.args):
        return await msg.reply(
            "Использование: <b>выдатьроли [роль] [сумма]</b>\n"
            "Пример: <i>выдатьроли модератор 300000000000000</i>",
            parse_mode="HTML"
        )
    parts = command.args.strip().split()
    if len(parts) < 2:
        return await msg.reply("❌ Укажи роль и сумму. Пример: выдатьроли модератор 5000")
    role_query = parts[0].lower()
    try:
        amount = int(parts[1])
    except ValueError:
        return await msg.reply("❌ Сумма должна быть целым числом")
    if amount <= 0:
        return await msg.reply("❌ Сумма должна быть больше нуля")

    try:
        admins = await bot.get_chat_administrators(msg.chat.id)
    except Exception as e:
        return await msg.reply(f"❌ Не удалось получить список администраторов: {e}")

    matched = []
    for a in admins:
        if a.user.is_bot:
            continue
        title = (getattr(a, "custom_title", None) or "").strip().lower()
        if title == role_query:
            add_balance(a.user.id, amount)
            matched.append(a.user.full_name)

    if not matched:
        return await msg.reply(
            f"⚠️ Никого с ролью <b>{parts[0]}</b> не найдено среди администраторов.",
            parse_mode="HTML"
        )

    save_data()
    names = "\n".join(f"• {n}" for n in matched)
    await msg.reply(
        f"💰 <b>Начислено!</b>\n"
        f"Роль: <b>{parts[0]}</b>\n"
        f"Сумма: <b>{fmt_lmn(amount)} LMN</b>\n\n"
        f"Получили:\n{names}",
        parse_mode="HTML"
    )

async def cmd_razdach(msg: Message, command: CommandObject = None):
    """Фаундер раздаёт всем участникам чата одинаковое количество монет."""
    if not is_owner(msg):
        return await msg.reply("⛔ Только фаундер")
    if not (command and command.args):
        return await msg.reply(
            "💰 Использование: <b>раздать [сумма]</b>\n"
            "Пример: <i>раздать 5000</i> — все участники чата получат по 5 000 LMN",
            parse_mode="HTML"
        )

    args = command.args.strip().split()
    # Пропускаем необязательное слово «всем»
    if args and args[0].lower() == "всем":
        args = args[1:]
    if not args:
        return await msg.reply("❌ Укажи сумму. Пример: раздать 5000")
    try:
        amount = int(args[0])
    except ValueError:
        return await msg.reply("❌ Укажи целое число. Пример: раздать 5000")
    if amount <= 0:
        return await msg.reply("❌ Сумма должна быть больше нуля")

    chat_id = msg.chat.id

    # Подтягиваем всех администраторов из Telegram API
    creator_id: int | None = None
    try:
        admins = await bot.get_chat_administrators(chat_id)
        for a in admins:
            if a.user.is_bot:
                continue
            if a.status == ChatMemberStatus.CREATOR:
                creator_id = a.user.id
            # Добавляем в базу участников чата
            chat_members.setdefault(chat_id, {})[a.user.id] = a.user.full_name
    except Exception:
        pass

    # Объединяем: участники из базы (писали сообщения) + только что загруженные админы
    uids_in_chat: dict[int, str] = dict(chat_members.get(chat_id, {}))

    if not uids_in_chat:
        return await msg.reply(
            "⚠️ Пока никто не попал в базу этого чата.\n"
            "Участники добавляются автоматически, когда пишут сообщения."
        )

    # Исключаем создателя чата
    recipients = {uid: name for uid, name in uids_in_chat.items() if uid != creator_id}

    if not recipients:
        return await msg.reply("⚠️ Нет участников для раздачи (кроме создателя)")

    for uid in recipients:
        add_balance(uid, amount)

    save_data()
    names_list = "\n".join(f"• {name}" for name in recipients.values())
    await msg.reply(
        f"🎁 <b>Раздача завершена!</b>\n"
        f"Каждый получил: <b>{fmt_lmn(amount)} LMN</b>\n\n"
        f"<b>Получили ({len(recipients)} чел.):</b>\n{names_list}"
        + (f"\n\n<i>Создатель чата исключён</i>" if creator_id else ""),
        parse_mode="HTML"
    )

# ═══════════════════════════════════════════════════════
# РЕПУТАЦИЯ
# ═══════════════════════════════════════════════════════
@dp.message(Command("aura"))
async def cmd_aura(msg: Message):
    """Показывает ауру пользователя (0–100%)."""
    target = msg.reply_to_message.from_user if msg.reply_to_message else msg.from_user
    pct = get_aura(target.id)
    bar = aura_bar(pct)
    tier = (
        "💫 Светлая" if pct >= 80 else
        "🌟 Высокая"  if pct >= 60 else
        "⭐ Средняя"  if pct >= 40 else
        "🌑 Низкая"   if pct >= 10 else
        "💀 Тёмная"
    )
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"✨ Аура\n\n"
        f"👤 <b>{target.full_name}</b>\n"
        f"{brand.div()}\n"
        f"<code>{bar}</code>\n"
        f"📊 <b>{pct:.2f}%</b>  —  {tier}\n\n"
        f"<i>+0.01% за каждый 👍 на твои сообщения\n"
        f"−1% за агрессию в чате</i>\n"
        f"{brand.div()}",
        parse_mode="HTML",
    )


@dp.message(Command("topaura"))
async def cmd_topaura(msg: Message):
    """Топ-10 пользователей по ауре."""
    if not aura:
        return await msg.reply("Аура ещё никем не набрана 🌑")
    top = sorted(aura.items(), key=lambda x: x[1], reverse=True)[:10]
    medals = ["🥇","🥈","🥉"] + ["4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines = [f"{brand.hdr()}\n", "✨ Топ ауры", f"{brand.div()}"]
    for i, (uid, pct) in enumerate(top):
        try:
            m = await bot.get_chat_member(msg.chat.id, uid)
            name = html.escape(m.user.full_name)
        except Exception:
            name = f"ID {uid}"
        lines.append(f"{medals[i]} <b>{name}</b>  —  {pct:.2f}%")
    lines.append(f"\n{brand.div()}")
    await msg.reply("\n".join(lines), parse_mode="HTML")


async def cmd_rep(msg: Message):
    target = msg.reply_to_message.from_user if msg.reply_to_message else msg.from_user
    r = get_rep(msg.chat.id, target.id)
    emoji = "⭐" if r >= 0 else "💀"
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"{emoji} Репутация\n\n"
        f"👤 <b>{target.full_name}</b>\n"
        f"📊 Рейтинг: <b>{r:+d}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML")

async def cmd_upvote(msg: Message):
    if not msg.reply_to_message: return await msg.reply("Ответь на сообщение")
    target = msg.reply_to_message.from_user
    if target.id == msg.from_user.id: return await msg.reply("Себе нельзя 😄")
    vote_key = (msg.chat.id, msg.from_user.id, target.id)
    prev = rep_votes.get(vote_key)
    if prev == 1:
        return await msg.reply("⚠️ Ты уже поднял репутацию этому пользователю сегодня")
    delta = 2 if prev == -1 else 1   # отменяем старый минус + добавляем плюс
    if prev == -1:
        add_rep(msg.chat.id, target.id, 2)
    else:
        add_rep(msg.chat.id, target.id, 1)
    rep_votes[vote_key] = 1
    total = get_rep(msg.chat.id, target.id)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"⬆️ +1 репутация{' (голос изменён)' if prev == -1 else ''}\n\n"
        f"👤 <b>{html.escape(target.full_name)}</b>\n"
        f"📊 Итого: <b>{total:+d}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML")

async def cmd_downvote(msg: Message):
    if not msg.reply_to_message: return await msg.reply("Ответь на сообщение")
    target = msg.reply_to_message.from_user
    if target.id == msg.from_user.id: return await msg.reply("Себе нельзя 😄")
    vote_key = (msg.chat.id, msg.from_user.id, target.id)
    prev = rep_votes.get(vote_key)
    if prev == -1:
        return await msg.reply("⚠️ Ты уже опустил репутацию этому пользователю сегодня")
    if prev == 1:
        add_rep(msg.chat.id, target.id, -2)
    else:
        add_rep(msg.chat.id, target.id, -1)
    rep_votes[vote_key] = -1
    total = get_rep(msg.chat.id, target.id)
    await msg.reply(


def _anon_ask_user_keyboard(viewer_id: int, page: int = 1) -> tuple[str, InlineKeyboardMarkup]:
    records = _known_user_records()
    ordered = [
        (uid, record)
        for uid, record in records.items()
        if uid != viewer_id
    ]
    ordered.sort(key=lambda item: _known_user_label(*item).lower())
    page_size = 24
    pages = max(1, (len(ordered) + page_size - 1) // page_size)
    page = min(max(1, page), pages)
    start = (page - 1) * page_size
    rows = []
    current_row = []
    for uid, record in ordered[start:start + page_size]:
        label = _known_user_label(uid, record)
        if len(label) > 24:
            label = label[:23] + "…"
        current_row.append(
            InlineKeyboardButton(
                text=label,
                callback_data=f"anon_ask_target:{uid}",
            )
        )
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)

    navigation = []
    if page > 1:
        navigation.append(
            InlineKeyboardButton(text="◀️ Назад", callback_data=f"anon_ask_page:{page - 1}")
        )
    if page < pages:
        navigation.append(
            InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"anon_ask_page:{page + 1}")
        )
    if navigation:
        rows.append(navigation)
    rows.append([
        InlineKeyboardButton(text="✖️ Отмена", callback_data="anon_ask_cancel")
    ])
    text = (
        "🕶 <b>Анонимный вопрос</b>\n\n"
        "Выбери человека из списка. После выбора напиши вопрос следующим сообщением.\n\n"
        f"👥 Пользователей в реестре: <b>{len(ordered)}</b>\n"
        f"📄 Страница {page}/{pages}\n"
        "Можно выбрать любого участника из списка."
    )
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


@dp.message(Command("ask", "спросить", "анонимныйвопрос"))
async def cmd_ask(msg: Message, command: CommandObject = None):
    args = (command.args if command else "") or ""
    args = args.strip()
    target_user = None
    question_text = ""

    if args:
        parts = args.split(maxsplit=1)
        if parts[0].startswith("@"):
            target_user = _find_known_user(parts[0])
            question_text = parts[1] if len(parts) > 1 else ""
        else:
            await msg.reply(
                "Используй формат:\n"
                "<code>/ask @username вопрос</code>",
                parse_mode="HTML",
            )
            return
    elif msg.reply_to_message and msg.reply_to_message.from_user:
        target_id = msg.reply_to_message.from_user.id
        target_user = (target_id, known_users.get(target_id, {
            "full_name": msg.reply_to_message.from_user.full_name,
            "username": msg.reply_to_message.from_user.username or "",
            "private_started": False,
        }))

    if not target_user and not args and not msg.reply_to_message:
        if msg.chat.type != "private":
            return await msg.reply(
                "Открой личный чат с ботом и используй <code>/ask</code> — "
                "там появится список людей с кнопками.",
                parse_mode="HTML",
            )
        ask_text, ask_kb = _anon_ask_user_keyboard(msg.from_user.id)
        await msg.reply(ask_text, parse_mode="HTML", reply_markup=ask_kb)
        return

    if not target_user:
        await msg.reply(
            "Не нашёл пользователя по этому username.\n\n"
            "Используй просто <code>/ask</code> и выбери человека кнопкой "
            "из полного списка.",
            parse_mode="HTML",
        )
        return

    target_id, target_record = target_user
    if not question_text:
        if msg.chat.type != "private":
            await msg.reply(
                "Для анонимности продолжи в личке с ботом:\n"
                f"<code>/ask @{html.escape(str(target_record.get('username', '')).lstrip('@'))}</code>",
                parse_mode="HTML",
            )
            return
        anon_ask_sessions[msg.from_user.id] = target_id
        schedule_state_save("выбор получателя анонимного вопроса")
        await msg.reply(
            "✍️ Напиши вопрос следующим сообщением — он будет отправлен анонимно."
        )
        return
    await _create_anon_question(msg, target_id, target_record, question_text)


@dp.message(Command("answer", "ответить"))
async def cmd_anon_answer(msg: Message, command: CommandObject = None):
    answer = ((command.args if command else "") or "").strip()
    if not answer:
        if (msg.from_user.id in anon_answer_sessions
                or msg.from_user.id in anon_reply_sessions):
            return await msg.reply("Напиши ответ после команды <code>/answer</code>.")
        return await msg.reply("Сейчас нет активного анонимного вопроса.")
    if msg.from_user.id in anon_reply_sessions:
        await _deliver_anon_reply(msg, answer)
    else:
        await _deliver_anon_answer(msg, answer)


@dp.message(Command("users", "пользователи", "юзеры"))
async def cmd_users(msg: Message, command: CommandObject = None):
    allowed = (
        is_owner(msg)
        or has_role(msg.from_user.id, "founder_deputy", "lead_admin", "co_admin", "admin", "moderator")
        or (msg.chat.type != "private" and await is_admin(msg))
    )
    if not allowed:
        return await msg.reply("⛔ Только администрация.")
    records = _known_user_records()
    try:
        page = max(1, int(((command.args if command else "") or "1").strip()))
    except ValueError:
        page = 1
    page_size = 40
    ordered = sorted(records.items(), key=lambda item: _known_user_label(*item).lower())
    pages = max(1, (len(ordered) + page_size - 1) // page_size)
    page = min(page, pages)
    start = (page - 1) * page_size
    lines = []
    for index, (uid, record) in enumerate(ordered[start:start + page_size], start=start + 1):
        status = "✅ ЛС" if record.get("private_started") else "⚠️ без /start"
        lines.append(
            f"{index}. {html.escape(_known_user_label(uid, record))} "
            f"— <code>{uid}</code> · {status}"
        )
    await msg.reply(
        f"👥 <b>Пользователи, известные боту</b>: {len(ordered)}\n"
        f"📄 Страница {page}/{pages}\n\n"
        + ("\n".join(lines) or "Пока нет записей.")
        + "\n\nДля выбора получателя анонимного вопроса: <code>/ask</code>",
        parse_mode="HTML",
    )


@dp.message(Command("updatesave"))
async def cmd_updatesave(msg: Message):
    """Одноразово публикует фаундерское обновление о сохранении данных."""
    global _save_update_sent
    if not (is_owner(msg) or has_role(msg.from_user.id, "founder_deputy", "lead_admin")):
        return await msg.reply("⛔ Эта команда доступна только фаундеру.")
    if _save_update_sent:
        return await msg.reply("ℹ️ Это обновление уже было опубликовано.")

    pub_chat = MAIN_CHAT_ID
    if not pub_chat:
        return await msg.reply("⚠️ Чат для публикации не настроен.")

    update_text = (
        f"{brand.hdr()}\n\n"
        "<b>✨ Обновление Lumenora</b>\n\n"
        "<b>Исправлено сохранение данных бота.</b>\n\n"
        "Теперь надёжно сохраняются:\n"
        "• браки и разводы\n"
        "• стрики и чекины\n"
        "• баланс LMN, банк и экономика\n"
        "• репутация\n"
        "• роли пользователей\n"
        "• настройки чатов\n\n"
        "Данные сохраняются после обновлений и перезапусков бота.\n\n"
        f"{brand.div()}"
    )
    try:
        await bot.send_message(pub_chat, update_text, parse_mode="HTML")
    except Exception as error:
        logging.error("Не удалось отправить обновление о сохранении: %s", error)
        return await msg.reply("❌ Не удалось отправить сообщение в паб-чат. Проверь права бота.")

    _save_update_sent = True
    save_data()
    await msg.reply("✅ Обновление опубликовано в паб-чате. Повторно команда недоступна.")

# ═══════════════════════════════════════════════════════
# LUMENORA AI
# ═══════════════════════════════════════════════════════
LUMENA_NAMES = [
    "lumenora", "люменора", "люменору", "люма",
    "лумена", "lumena", "лум", "лумка",
]
# AI-доступ ограничен только основным founder и заместителем founder.
LUMENA_AI_ALLOWED_IDS = frozenset({
    OWNER_ID,
    *FOUNDER_DEPUTY_IDS,
})


def _is_lumena_ai_allowed(msg: Message) -> bool:
    """Ограничивает AI-диалог только founder и его заместителем."""
    user = getattr(msg, "from_user", None)
    if not user:
        return False
    if user.id == OWNER_ID:
        return True
    return user.id in FOUNDER_DEPUTY_IDS and user.id not in REVOKED_FOUNDER_ACCESS_IDS


def _lumena_command_catalog() -> str:
    """Передаёт AI только фактические команды из текущего маршрутизатора."""
    # Часть slash-команд зарегистрирована напрямую декораторами aiogram и
    # поэтому не попадает в TEXT_COMMANDS.
    direct_commands = {
        "/start", "/help", "/profile", "/helplum",
        "/helpcancel", "/premium", "/premiumstock", "/shop", "/inventory",
        "/exchange", "/withdraw", "/ask", "/answer", "/poll", "/polls",
        "/info", "/level", "/top", "/report", "/settings",
    }
    commands = sorted(direct_commands | {
        f"/{name.lstrip('/')}"
        for name in TEXT_COMMANDS
        if isinstance(name, str) and name.strip()
    })
    return " · ".join(commands)[:3000]


def is_lumena_addressed(msg: Message) -> bool:
    """Lumenora реагирует только если:
    - личный чат
    - ответ на её сообщение
    - @упоминание бота
    - ПЕРВОЕ слово сообщения — её имя
    """
    if msg.chat.type == "private":
        return True
    # Ответ на сообщение бота
    if msg.reply_to_message and msg.reply_to_message.from_user:
        if msg.reply_to_message.from_user.is_bot:
            return True
    # @упоминание бота
    if msg.entities:
        for entity in msg.entities:
            if entity.type == "mention":
                mention = msg.text[entity.offset:entity.offset + entity.length].lower()
                if "lumenora" in mention or "люменор" in mention or "лумен" in mention:
                    return True
    # Только если ПЕРВОЕ слово — имя Lumenora
    text = (msg.text or "").strip().lower()
    first_word = re.split(r"[\s,!?.:]", text)[0]
    return first_word in LUMENA_NAMES

# ═══════════════════════════════════════════════════════
# V6 — XP / УРОВНИ / ДОСТИЖЕНИЯ
# ═══════════════════════════════════════════════════════
async def cmd_level(msg: Message):
    uid  = msg.from_user.id
    name = html.escape(msg.from_user.first_name or "—")
    xp   = user_xp.get(uid, 0)
    lvl, start, end = get_xp_level(xp)
    bar  = xp_bar(xp)
    need = max(0, end - xp)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"⚡ <b>Уровень · {name}</b>\n\n"
        f"{brand.div()}\n"
        f"🏷 Уровень: <b>{lvl}</b>\n"
        f"✨ XP: <b>{xp:,}</b>\n"
        f"📊 {bar}\n"
        + (f"⬆️ До следующего: <b>{need:,} XP</b>\n" if need > 0 and end > start else "🏆 <b>Максимальный уровень!</b>\n")
        + f"\n{brand.div()}",
        parse_mode="HTML"
    )

async def cmd_rank(msg: Message):
    if msg.chat.type == "private":
        return await msg.reply("Команда работает только в групповых чатах")
    cid  = msg.chat.id
    uid  = msg.from_user.id
    name = html.escape(msg.from_user.first_name or "—")
    # Берём всех известных участников + гарантированно добавляем текущего юзера
    members = (
        set(chat_members.get(cid, {}).keys()) |
        set(chat_members.get(econ_cid(cid), {}).keys()) |
        {uid}
    )
    # Если у юзера есть XP, показываем его в глобальном топе
    if user_xp.get(uid, 0) > 0 and msg.chat.type != "private":
        members |= set(user_xp.keys())
    ranked  = sorted(members, key=lambda u: user_xp.get(u, 0), reverse=True)
    pos     = next((i + 1 for i, u in enumerate(ranked) if u == uid), None)
    xp      = user_xp.get(uid, 0)
    lvl     = get_xp_level(xp)[0]
    bar     = xp_bar(xp)
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🏆 <b>Ранг · {name}</b>\n\n"
        f"{brand.div()}\n"
        f"📍 Место: <b>#{pos}</b> из {len(ranked)}\n"
        f"✨ XP: <b>{xp:,}</b>\n"
        f"🏷 Уровень: <b>{lvl}</b>\n"
        f"📊 {bar}\n\n"
        f"{brand.div()}",
        parse_mode="HTML"
    )

@dp.message(Command("top"))
async def _cmd_top_slash(msg: Message):
    await cmd_top_xp(msg)


async def cmd_top_xp(msg: Message):
    if msg.chat.type == "private":
        members = set(user_xp.keys())
        title   = "🌍 Глобальный топ XP"
    else:
        cid     = msg.chat.id
        members = set(chat_members.get(cid, {}).keys()) | set(chat_members.get(econ_cid(cid), {}).keys())
        title   = f"🏆 Топ XP · {html.escape(msg.chat.title or 'чат')}"
    top = sorted(members, key=lambda u: user_xp.get(u, 0), reverse=True)[:10]
    if not top:
        return await msg.reply("📊 Пока нет данных XP")
    medals = ["🥇","🥈","🥉"] + [f"{i}." for i in range(4, 11)]
    lines  = [f"{brand.hdr()}\n\n{title}\n\n{brand.div()}"]
    for i, uid in enumerate(top):
        name = html.escape(
            chat_members.get(msg.chat.id, {}).get(uid) or
            chat_members.get(econ_cid(msg.chat.id), {}).get(uid) or
            next((m.get(uid) for m in chat_members.values() if uid in m), None) or
            f"ID {uid}"
        )
        lvl = get_xp_level(user_xp.get(uid, 0))[0]
        lines.append(f"{medals[i]} <b>{name}</b> — {user_xp.get(uid, 0):,} XP · {lvl}")
    lines.append(f"\n{brand.div()}")
    await msg.reply("\n".join(lines), parse_mode="HTML")

async def cmd_achievements(msg: Message):
    uid    = msg.from_user.id
    name   = html.escape(msg.from_user.first_name or "—")
    _check_achievements(uid)
    earned = set(user_achievements.get(uid, []))
    lines  = [f"{brand.hdr()}\n\n🏆 <b>Достижения · {name}</b>\n\n{brand.div()}"]
    for ach_id, (icon, title_, desc) in ACHIEVEMENT_INFO.items():
        check = "✅" if ach_id in earned else "🔒"
        style = f"<b>{title_}</b>" if ach_id in earned else f"<i>{title_}</i>"
        lines.append(f"{check} {icon} {style} — {desc}")
    medals = founder_medals.get(uid, [])
    if medals:
        lines.append("\n🏅 <b>Медали от фаундера</b>")
        for medal in medals:
            lines.append(
                f"🏅 <b>{html.escape(medal['title'])}</b> — "
                f"{html.escape(medal.get('description', ''))}"
            )
    lines.append(f"\n{brand.div()}\n✅ Получено: <b>{len(earned)}/{len(ACHIEVEMENT_INFO)}</b>")
    await msg.reply("\n".join(lines), parse_mode="HTML")

async def cmd_messages(msg: Message):
    uid   = msg.from_user.id
    name  = html.escape(msg.from_user.first_name or "—")
    total = sum(m.get(uid, 0) for m in user_messages.values())
    xp    = user_xp.get(uid, 0)
    lvl   = get_xp_level(xp)[0]
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"💬 <b>Сообщения · {name}</b>\n\n"
        f"{brand.div()}\n"
        f"📨 Всего сообщений: <b>{total:,}</b>\n"
        f"✨ XP заработано: <b>{xp:,}</b>\n"
        f"🏷 Уровень: <b>{lvl}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML"
    )

async def cmd_activity(msg: Message):
    uid       = msg.from_user.id
    name      = html.escape(msg.from_user.first_name or "—")
    xp        = user_xp.get(uid, 0)
    lvl       = get_xp_level(xp)[0]
    total_msg = sum(m.get(uid, 0) for m in user_messages.values())
    cid_s     = econ_cid(msg.chat.id) if msg.chat.type != "private" else 0
    streak_v  = max((streaks.get(c, {}).get(uid, {}).get("count", 0) for c in streaks), default=0)
    bal       = get_balance(uid) + bank_balances.get(uid, 0)
    ach_cnt   = len(user_achievements.get(uid, []))
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"📊 <b>Активность · {name}</b>\n\n"
        f"{brand.div()}\n"
        f"🏷 Уровень: <b>{lvl}</b>  ✨ XP: <b>{xp:,}</b>\n"
        f"💬 Сообщений: <b>{total_msg:,}</b>\n"
        f"🔥 Стрик: <b>{streak_v} дн.</b>\n"
        f"💰 Баланс (кош.+банк): <b>{fmt_lmn(bal)}</b>\n"
        f"🏆 Достижений: <b>{ach_cnt}/{len(ACHIEVEMENT_INFO)}</b>\n\n"
        f"{brand.div()}",
        parse_mode="HTML"
    )

# ═══════════════════════════════════════════════════════
# V6 — ЕЖЕДНЕВНЫЕ НАГРАДЫ
# ═══════════════════════════════════════════════════════
async def cmd_daily(msg: Message):
    uid      = msg.from_user.id
    name     = html.escape(msg.from_user.first_name or "—")
    today    = today_kyiv().isoformat()
    if daily_cooldown.get(uid) == today:
        streak_v = max((streaks.get(c, {}).get(uid, {}).get("count", 0) for c in streaks), default=0)
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            f"⏳ <b>Дейли уже получен!</b>\n\n"
            f"{brand.div()}\n"
            f"🔥 Стрик: <b>{streak_v} дн.</b>\n"
            f"📅 Возвращайся завтра!\n\n"
            f"💡 Пока можешь: <code>задания</code> · <code>гороскоп</code> · <code>предсказание</code>\n\n"
            f"{brand.div()}",
            parse_mode="HTML"
        )
    reward = random.randint(500, 2000)
    reward, combo_bonus = _apply_economy_combo(uid, reward, "daily")
    credited = add_balance(uid, reward)
    _register_earning_challenge(uid, credited, "daily")
    xp_got   = 50
    lvl_up   = award_xp(uid, xp_got)
    daily_cooldown[uid] = today
    save_data()
    schedule_state_save("дейли")
    lvl      = get_xp_level(user_xp.get(uid, 0))[0]
    up_text  = f"\n🆙 <b>Новый уровень: {lvl}!</b>" if lvl_up else ""
    streak_v = max((streaks.get(c, {}).get(uid, {}).get("count", 0) for c in streaks), default=0)
    streak_tip = f"\n🔥 Стрик: <b>{streak_v} дн.</b>" if streak_v > 0 else ""
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🎁 <b>Ежедневная награда · {name}</b>\n\n"
        f"{brand.div()}\n"
        f"💰 +<b>{fmt_lmn(credited)} LMN</b>{_economy_combo_line(combo_bonus)}\n"
        f"✨ +<b>{xp_got} XP</b>{up_text}{streak_tip}\n\n"
        f"📅 Возвращайся завтра!\n"
        f"💡 Не забудь: <code>задания</code> для бонуса за все задания\n\n"
        f"{brand.div()}",
        parse_mode="HTML",
        reply_markup=_earning_actions_keyboard(),
    )

def _this_week() -> str:
    """ISO year-week string, e.g. '2026-W32'."""
    d   = today_kyiv()
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"

async def cmd_bonus(msg: Message):
    uid      = msg.from_user.id
    name     = html.escape(msg.from_user.first_name or "—")
    week_key = _this_week()
    st = max((streaks.get(c, {}).get(uid, {}).get("count", 0) for c in streaks), default=0)
    bar_filled = min(st, 7)
    bar = "🟩" * bar_filled + "⬜" * (7 - bar_filled)
    if bonus_weekly_cd.get(uid) == week_key:
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            f"✅ <b>Бонус за стрик получен!</b>\n\n"
            f"{brand.div()}\n"
            f"🔥 Стрик: <b>{st} дн.</b>\n"
            f"{bar}\n\n"
            f"📅 Возвращайся на следующей неделе\n\n"
            f"{brand.div()}",
            parse_mode="HTML"
        )
    if st < 7:
        return await msg.reply(
            f"{brand.hdr()}\n\n"
            f"🎯 <b>Недельный бонус за стрик</b>\n\n"
            f"{brand.div()}\n"
            f"🔥 Прогресс: <b>{st}/7 дн.</b>\n"
            f"{bar}\n\n"
            f"Чекинься каждый день — и получишь:\n"
            f"💰 <b>5 000 LMN</b> + ✨ <b>100 XP</b>\n\n"
            f"{brand.div()}",
            parse_mode="HTML"
        )
    reward = 5000
    credited = add_balance(uid, reward)
    _register_earning_challenge(uid, credited, "weekly_bonus")
    award_xp(uid, 100)
    bonus_weekly_cd[uid] = week_key
    save_data()
    schedule_state_save("бонус за стрик")
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🎊 <b>Недельный бонус · {name}</b>\n\n"
        f"{brand.div()}\n"
        f"🔥 Стрик: <b>{st} дн.</b>\n"
        f"{bar}\n\n"
        f"💰 +<b>{fmt_lmn(credited)} LMN</b>\n"
        f"✨ +<b>100 XP</b>\n\n"
        f"{brand.div()}\n"
        f"<i>Продолжай чекиниться каждый день!</i> 🌟",
        parse_mode="HTML",
        reply_markup=_earning_actions_keyboard(),
    )

async def cmd_tasks(msg: Message):
    uid       = msg.from_user.id
    name      = html.escape(msg.from_user.first_name or "—")
    today_str = today_kyiv().isoformat()
    did_daily   = daily_cooldown.get(uid) == today_str
    played      = daily_games.get(uid) == today_str
    msgs_today  = (daily_msg_cnt.get(uid) or {}).get("count", 0) \
                  if (daily_msg_cnt.get(uid) or {}).get("date") == today_str else 0
    streak_v  = max((streaks.get(c, {}).get(uid, {}).get("count", 0) for c in streaks), default=0)
    task_list = [
        ("💬", "Написать 10 сообщений",   min(msgs_today, 10), 10, msgs_today >= 10),
        ("📅", "Получить дейли",           1 if did_daily else 0, 1, did_daily),
        ("🎰", "Сыграть в игру",           1 if played else 0, 1, played),
        ("🔥", "Поддержать стрик 3+ дня",  min(streak_v, 3), 3, streak_v >= 3),
    ]
    done      = sum(1 for *_, ok in task_list if ok)
    all_done  = done == len(task_list)
    bonus_got = tasks_bonus_cd.get(uid) == today_str
    lines = [f"{brand.hdr()}\n\n📋 <b>Задания дня · {name}</b>\n\n{brand.div()}"]
    for icon, tname, cur, mx, ok in task_list:
        chk = "✅" if ok else "⬜"
        lines.append(f"{chk} {icon} {tname} ({cur}/{mx})")
    bar_done = "🟩" * done + "⬜" * (len(task_list) - done)
    lines.append(f"\n{brand.div()}\n{bar_done}  <b>{done}/{len(task_list)}</b>")
    if all_done and not bonus_got:
        # Начисляем бонус за все задания
        add_balance(uid, 1000)
        award_xp(uid, 75)
        tasks_bonus_cd[uid] = today_str
        save_data()
        lines.append(
            f"\n🎉 <b>Все задания выполнены!</b>\n"
            f"💰 +<b>1 000 LMN</b> + ✨ +<b>75 XP</b> начислено!"
        )
    elif all_done and bonus_got:
        lines.append(f"\n✅ <b>Бонус за все задания уже получен!</b>")
    else:
        remaining = len(task_list) - done
        lines.append(f"\n💡 Осталось: <b>{remaining}</b> — выполни все и получи <b>+1 000 LMN + 75 XP</b>!")
    lines.append(f"\n{brand.div()}")
    await msg.reply("\n".join(lines), parse_mode="HTML")

async def cmd_rewards(msg: Message):
    await msg.reply(
        f"{brand.hdr()}\n\n"
        f"🎁 <b>Все источники наград</b>\n\n"
        f"{brand.div()}\n"
        f"📅 <b>Дейли</b> — 500–2 000 LMN + 50 XP\n"
        f"   └ <code>дейли</code> — раз в 24 часа\n\n"
        f"📋 <b>Все задания</b> — 1 000 LMN + 75 XP\n"
        f"   └ <code>задания</code> — выполни все 4 в день\n\n"
        f"🔥 <b>Стрик 7 дней</b> — 5 000 LMN + 100 XP\n"
        f"   └ <code>бонус</code> — за непрерывный чекин 7 дн.\n\n"
        f"💍 <b>Брак</b> — 500 LMN каждому\n"
        f"   └ <code>пожениться @username</code>\n\n"
        f"🌧 <b>Дождь монет</b> — случайный бонус\n"
        f"   └ выдаётся администраторами в чате\n\n"
        f"🔗 <b>Реферал</b> — 1 000 LMN + 100 XP\n"
        f"   └ <code>реферал</code> — за каждого приглашённого\n\n"
        f"{brand.div()}",
        parse_mode="HTML"
    )

async def cmd_leaderboard(msg: Message):
    all_uids = set(user_xp.keys())
    top      = sorted(all_uids, key=lambda u: user_xp.get(u, 0), reverse=True)[:10]
    if not top:
        return await msg.reply("📊 Пока нет данных")
    medals = ["🥇","🥈","🥉"] + [f"{i}." for i in range(4, 11)]
    lines  = [f"{brand.hdr()}\n\n🌍 <b>Глобальный лидерборд XP</b>\n\n{brand.div()}"]
    for i, uid in enumerate(top):
        name = html.escape(
            next((m.get(uid) for m in chat_members.values() if uid in m), None) or f"ID {uid}"
        )
        lines.append(f"{medals[i]} <b>{name}</b> — {user_xp.get(uid, 0):,} XP")
    lines.append(f"\n{brand.div()}")
    await msg.reply("\n".join(lines), parse_mode="HTML")

# ═══════════════════════════════════════════════════════
# V6 — НОВЫЕ ИГРЫ
# ═══════════════════════════════════════════════════════
def _game_result(uid: int, won: bool):
    _games_played[uid] = _games_played.get(uid, 0) + 1
    daily_games[uid]   = today_kyiv().isoformat()   # отмечаем сегодняшнюю игру
    if won:
        _games_won[uid] = _games_won.get(uid, 0) + 1
    _check_achievements(uid)
    save_data()   # синхронный сброс — данные игры не теряются при перезапуске

async def _priv_check(msg: Message) -> bool:
    """Игры работают везде — проверка удалена."""
    return True

async def cmd_coinflip(msg: Message, command: CommandObject = None):
    if not await _priv_check(msg): return
    if not command or not command.args:
        return await msg.reply("Использование: <b>орёл [сумма]</b>", parse_mode="HTML")
    try:
        bet = int(command.args.split()[0])
    except ValueError:
        return await msg.reply("❌ Укажи целое число")
    uid = msg.from_user.id
    if bet <= 0 or get_balance(uid) < bet:
        return await msg.reply("❌ Недостаточно LMN или сумма некорректна")
    won = random.random() < 0.5
    result = "🦅 Орёл" if won else "🪙 Решка"
    _game_result(uid, won)
    if won:
        add_balance(uid, bet)
        award_xp(uid, 10)
        out = f"✅ <b>Победа! +{fmt_lmn(bet)} LMN</b>"
    else:
        add_balance(uid, -bet)
        out = f"❌ <b>Проигрыш! -{fmt_lmn(bet)} LMN</b>"
    schedule_state_save("coinflip")
    await msg.reply(
        f"🪙 <b>Монетка</b> — ставка {fmt_lmn(bet)} LMN\n\n"
        f"Выпало: <b>{result}</b>\n\n{out}",
        parse_mode="HTML"
    )

async def cmd_plinko(msg: Message, command: CommandObject = None):
    if not await _priv_check(msg): return
    if not command or not command.args:
        return await msg.reply("Использование: <b>плинко [сумма]</b>", parse_mode="HTML")
    try:
        bet = int(command.args.split()[0])
    except ValueError:
        return await msg.reply("❌ Укажи целое число")
    uid = msg.from_user.id
    if bet <= 0 or get_balance(uid) < bet:
        return await msg.reply("❌ Недостаточно LMN")
    mults   = [0.2, 0.5, 0.5, 1.0, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0]
    weights = [5, 10, 10, 20, 20, 15, 10, 5, 4, 1]
    mult    = random.choices(mults, weights=weights, k=1)[0]
    winnings = max(1, int(bet * mult)) if mult > 0 else 0  # минимум 1 при ненулевом множителе
    diff     = winnings - bet
    add_balance(uid, diff)
    _game_result(uid, winnings > bet)   # победа только если реально больше ставки
    award_xp(uid, random.randint(5, 20))
    schedule_state_save("plinko")
    emoji = "✅" if winnings > bet else ("⚖️" if winnings == bet else "❌")
    sign  = "+" if diff > 0 else ""
    await msg.reply(
        f"🎯 <b>Плинко</b> — ставка {fmt_lmn(bet)} LMN\n\n"
        f"🎰  ● ● ● ● ●\n"
        f"    ● ● ● ● ●\n"
        f"      ● ● ● ●\n\n"
        f"💥 Множитель: <b>{mult}×</b>\n"
        f"{emoji} Результат: <b>{fmt_lmn(winnings)} LMN</b> ({sign}{fmt_lmn(diff)})",
        parse_mode="HTML"
    )

async def cmd_limbo(msg: Message, command: CommandObject = None):
    if not await _priv_check(msg): return
    usage = "Использование: <b>лимбо [сумма] [цель ×]</b>\nПример: лимбо 1000 2.0"
    if not command or not command.args:
        return await msg.reply(usage, parse_mode="HTML")
    parts = command.args.split()
    if len(parts) < 2:
        return await msg.reply(usage, parse_mode="HTML")
    try:
        bet    = int(parts[0])
        target = float(parts[1])
    except ValueError:
        return await msg.reply("❌ Укажи число и дробное цель")
    if not math.isfinite(target):
        return await msg.reply("❌ Цель должна быть обычным числом")
    uid = msg.from_user.id
    if bet <= 0 or get_balance(uid) < bet:
        return await msg.reply("❌ Недостаточно LMN")
    if not 1.01 <= target <= 100:
        return await msg.reply("❌ Цель от 1.01 до 100")
    win_prob = min(0.97 / target, 0.97)
    won      = random.random() < win_prob
    roll     = round(random.uniform(target, target * 2) if won else random.uniform(1.0, target - 0.01), 2)
    if won:
        winnings = int(bet * target)
        add_balance(uid, winnings - bet)
        _game_result(uid, True)
        award_xp(uid, 20)
        result_text = f"✅ <b>Победа! +{fmt_lmn(winnings - bet)} LMN</b>"
    else:
        add_balance(uid, -bet)
        _game_result(uid, False)
        result_text = f"❌ <b>Проигрыш! -{fmt_lmn(bet)} LMN</b>"
    schedule_state_save("limbo")
    await msg.reply(
        f"🚀 <b>Лимбо</b> — ставка {fmt_lmn(bet)} LMN\n\n"
        f"🎯 Цель: <b>{target}×</b>\n"
        f"🎲 Выпало: <b>{roll:.2f}×</b>\n\n"
        f"{result_text}",
        parse_mode="HTML"
    )

async def cmd_crash(msg: Message, command: CommandObject = None):
    if not await _priv_check(msg): return
    if not command or not command.args:
        return await msg.reply("Использование: <b>краш [сумма]</b>", parse_mode="HTML")
    try:
        bet = int(command.args.split()[0])
    except ValueError:
        return await msg.reply("❌ Укажи целое число")
    uid = msg.from_user.id
    if bet <= 0 or get_balance(uid) < bet:
        return await msg.reply("❌ Недостаточно LMN")
    if uid in _crash_games:
        return await msg.reply("⚡ У тебя уже активная игра краш! Нажми Забрать.")
    add_balance(uid, -bet)
    crash_at = round(random.choices(
        [round(random.uniform(1.0, 1.5), 2), round(random.uniform(1.5, 4.0), 2),
         round(random.uniform(4.0, 10.0), 2), round(random.uniform(10.0, 20.0), 2)],
        weights=[40, 35, 20, 5], k=1
    )[0], 2)
    _crash_games[uid] = {"bet": bet, "multiplier": 1.0, "crash_at": crash_at, "active": True}
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💰 Забрать", callback_data=f"crash:out:{uid}:{bet}")
    ]])
    sent = await msg.reply(
        f"🚀 <b>КРАШ</b> — ставка {fmt_lmn(bet)} LMN\n\n"
        f"📈 Множитель: <b>1.00×</b>\n"
        f"⚡ Нажми Забрать пока не поздно!",
        parse_mode="HTML", reply_markup=kb
    )
    _crash_games[uid]["msg_id"]  = sent.message_id
    _crash_games[uid]["chat_id"] = msg.chat.id

    async def crash_tick():
        mult = 1.0
        while True:
            await asyncio.sleep(1.5)
            if uid not in _crash_games or not _crash_games[uid].get("active"):
                break
            mult = round(mult + random.uniform(0.05, 0.25), 2)
            _crash_games[uid]["multiplier"] = mult
            if mult >= crash_at:
                _crash_games.pop(uid, None)
                _game_result(uid, False)
                try:
                    await bot.edit_message_text(
                        f"💥 <b>КРАШ!</b> — ставка {fmt_lmn(bet)} LMN\n\n"
                        f"📉 Упал на <b>{mult:.2f}×</b>\n"
                        f"❌ Ты потерял <b>{fmt_lmn(bet)} LMN</b>",
                        chat_id=msg.chat.id, message_id=sent.message_id, parse_mode="HTML"
                    )
                except Exception:
                    pass
                break
            try:
                await bot.edit_message_text(
                    f"🚀 <b>КРАШ</b> — ставка {fmt_lmn(bet)} LMN\n\n"
                    f"📈 Множитель: <b>{mult:.2f}×</b>\n"
                    f"⚡ Нажми Забрать пока не поздно!",
                    chat_id=msg.chat.id, message_id=sent.message_id,
                    parse_mode="HTML", reply_markup=kb
                )
            except Exception:
                break
    asyncio.create_task(crash_tick())

@dp.callback_query(F.data.startswith("crash:out:"))
async def cb_crash_out(cb: CallbackQuery):
    parts = cb.data.split(":")
    if len(parts) != 3 or parts[0] != "crash" or parts[1] != "out":
        return await cb.answer("Некорректная кнопка игры", show_alert=True)
    try:
        uid = int(parts[2])
    except (TypeError, ValueError):
        return await cb.answer("Некорректная кнопка игры", show_alert=True)
    if cb.from_user.id != uid:
        return await cb.answer("Это не твоя игра!", show_alert=True)
    game = _crash_games.pop(uid, None)
    if not game:
        return await cb.answer("Игра уже закончилась!", show_alert=True)
    game["active"] = False
    mult      = game.get("multiplier", 1.0)
    crash_at  = game.get("crash_at", 1.0)
    real_bet  = game["bet"]   # берём ставку из состояния игры, не из callback
    # если успели нажать после краша — выплаты нет
    if mult >= crash_at:
        _game_result(uid, False)
        schedule_state_save("crash late cashout")
        return await cb.answer("💥 Краш уже произошёл! Ставка потеряна.", show_alert=True)
    winnings = int(real_bet * mult)
    add_balance(uid, winnings)
    _game_result(uid, True)
    award_xp(uid, int(mult * 5))
    schedule_state_save("crash cashout")
    await cb.message.edit_text(
        f"✅ <b>Забрал!</b>\n\n"
        f"📈 Множитель: <b>{mult:.2f}×</b>\n"
        f"💰 +<b>{fmt_lmn(winnings)} LMN</b>\n"
        f"✨ +{int(mult*5)} XP",
        parse_mode="HTML"
    )
    await cb.answer(f"✅ +{fmt_lmn(winnings)} LMN!")

# ── Блэкджек ───────────────────────────────────────────
_BJ_VALUES = [2,3,4,5,6,7,8,9,10,10,10,10,11] * 4

def _bj_val(hand: list) -> int:
    v = sum(hand); a = hand.count(11)
    while v > 21 and a:
        v -= 10; a -= 1
    return v

def _bj_names(hand: list) -> str:
    """Отображает карты. hand — список int (значения карт).
    Масть выбирается один раз по индексу, не случайно — карта не меняет масть."""
    suits = ["♠","♥","♦","♣"]
    nm    = {11:"A",10:"10",9:"9",8:"8",7:"7",6:"6",5:"5",4:"4",3:"3",2:"2"}
    return " ".join(
        f"{nm.get(c,'?')}{suits[i % len(suits)]}"
        for i, c in enumerate(hand)
    )

@dp.message(Command("блэкджек", "blackjack"))
async def cmd_blackjack(msg: Message, command: CommandObject = None):
    if not await _priv_check(msg): return
    if not command or not command.args:
        return await msg.reply("Использование: <b>блэкджек [сумма]</b>", parse_mode="HTML")
    try:
        bet = int(command.args.split()[0])
    except ValueError:
        return await msg.reply("❌ Укажи целое число")
    uid = msg.from_user.id
    if bet <= 0 or get_balance(uid) < bet:
        return await msg.reply("❌ Недостаточно LMN")
    if uid in _bj_games:
        return await msg.reply("⚡ У тебя уже активная игра блэкджек!")
    deck  = _BJ_VALUES.copy(); random.shuffle(deck)
    ph    = [deck.pop(), deck.pop()]
    dh    = [deck.pop(), deck.pop()]
    _bj_games[uid] = {"bet": bet, "player": ph, "dealer": dh, "deck": deck}
    add_balance(uid, -bet)
    pv = _bj_val(ph)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🃏 Взять", callback_data=f"bj:hit:{uid}"),
        InlineKeyboardButton(text="✋ Стоп",  callback_data=f"bj:stand:{uid}"),
    ]])
    if pv == 21:
        _bj_games.pop(uid, None)
        wins = int(bet * 2.5)
        add_balance(uid, wins)
        _game_result(uid, True)
        award_xp(uid, 30)
        schedule_state_save("blackjack")
        return await msg.reply(
            f"🃏 <b>Блэкджек!</b>\n\n"
            f"Твои карты: {_bj_names(ph)} = <b>21</b>\n\n"
            f"✅ <b>БЛЭКДЖЕК! +{fmt_lmn(wins - bet)} LMN</b>",
            parse_mode="HTML"
        )
    await msg.reply(
        f"🃏 <b>Блэкджек</b> — ставка {fmt_lmn(bet)} LMN\n\n"
        f"Твои карты: {_bj_names(ph)} = <b>{pv}</b>\n"
        f"Дилер: {_bj_names([dh[0]])} + 🂠\n\n"
        f"Что делаешь?",
        parse_mode="HTML", reply_markup=kb
    )

@dp.callback_query(F.data.startswith("bj:"))
async def cb_bj(cb: CallbackQuery):
    parts  = cb.data.split(":")
    if len(parts) != 3 or parts[1] not in {"hit", "stand"}:
        return await cb.answer("Некорректная кнопка игры", show_alert=True)
    try:
        uid = int(parts[2])
    except (TypeError, ValueError):
        return await cb.answer("Некорректная кнопка игры", show_alert=True)
    action = parts[1]
    if cb.from_user.id != uid:
        return await cb.answer("Это не твоя игра!", show_alert=True)
    game = _bj_games.get(uid)
    if not game:
        return await cb.answer("Игра не найдена!", show_alert=True)
    bet = game["bet"]; ph = game["player"]; dh = game["dealer"]; deck = game["deck"]
    if action == "hit":
        ph.append(deck.pop() if deck else random.choice(_BJ_VALUES))
        pv = _bj_val(ph)
        if pv > 21:
            _bj_games.pop(uid, None)
            _game_result(uid, False)
            schedule_state_save("blackjack")
            await cb.message.edit_text(
                f"🃏 <b>Блэкджек</b>\n\nТвои: {_bj_names(ph)} = <b>{pv}</b>\n\n"
                f"❌ <b>Перебор! -{fmt_lmn(bet)} LMN</b>", parse_mode="HTML"
            )
            return await cb.answer("❌ Перебор!")
        if pv == 21:
            action = "stand"
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🃏 Взять", callback_data=f"bj:hit:{uid}"),
                InlineKeyboardButton(text="✋ Стоп",  callback_data=f"bj:stand:{uid}"),
            ]])
            await cb.message.edit_text(
                f"🃏 <b>Блэкджек</b>\n\nТвои: {_bj_names(ph)} = <b>{pv}</b>\n"
                f"Дилер: {_bj_names([dh[0]])} + 🂠\n\nЧто делаешь?",
                parse_mode="HTML", reply_markup=kb
            )
            return await cb.answer()
    if action == "stand":
        _bj_games.pop(uid, None)
        pv = _bj_val(ph)
        while _bj_val(dh) < 17:
            dh.append(deck.pop() if deck else random.choice(_BJ_VALUES))
        dv = _bj_val(dh)
        if dv > 21 or pv > dv:
            add_balance(uid, bet * 2); _game_result(uid, True); award_xp(uid, 15)
            res = f"✅ <b>Победа! +{fmt_lmn(bet)} LMN</b>"
        elif pv == dv:
            add_balance(uid, bet); _game_result(uid, False)
            res = "🤝 <b>Ничья! Ставка возвращена</b>"
        else:
            _game_result(uid, False)
            res = f"❌ <b>Проигрыш! -{fmt_lmn(bet)} LMN</b>"
        schedule_state_save("blackjack")
        await cb.message.edit_text(
            f"🃏 <b>Блэкджек</b>\n\nТвои: {_bj_names(ph)} = <b>{pv}</b>\n"
            f"Дилер: {_bj_names(dh)} = <b>{dv}</b>\n\n{res}", parse_mode="HTML"
        )
        await cb.answer()

# ── Мины ───────────────────────────────────────────────
_MINES_SIZE = 5; _MINES_COUNT = 5

def _mines_kb(uid: int, revealed: set) -> InlineKeyboardMarkup:
    rows = []
    for r in range(_MINES_SIZE):
        row = []
        for c in range(_MINES_SIZE):
            idx = r * _MINES_SIZE + c
            txt = "💎" if idx in revealed else "⬜"
            cb_ = "mines:noop" if idx in revealed else f"mines:click:{uid}:{idx}"
            row.append(InlineKeyboardButton(text=txt, callback_data=cb_))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="💰 Забрать", callback_data=f"mines:cashout:{uid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@dp.message(Command("мины", "mines"))
async def cmd_mines(msg: Message, command: CommandObject = None):
    if not await _priv_check(msg): return
    if not command or not command.args:
        return await msg.reply("Использование: <b>мины [сумма]</b>", parse_mode="HTML")
    try:
                callback_data=f"setemoji_hdr:{eid}",
            )])
        lines.append("\nНажми кнопку, чтобы установить нужный header emoji:")
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await msg.reply("\n".join(lines), parse_mode="HTML", reply_markup=kb)


@dp.callback_query(F.data.startswith("setemoji_hdr:"))
async def cb_setemoji_hdr(cb: CallbackQuery):
    """Встановлює вибраний emoji як header."""
    if not is_owner(cb):
        return await cb.answer("Только фаундер", show_alert=True)
    eid = cb.data.split(":", 1)[1]
    ids = brand.get_pack()
    if ids:
        ids[0] = eid
    else:
        ids = [eid]
    brand.set_pack(ids, brand.get_pack_name())
    save_data()
    await cb.message.edit_text(
            f"✅ <b>Header emoji сохранено!</b>\n\n"
        f"<code>{eid}</code>\n\n"
        f"Превью: {brand.hdr()}\n"
        f"{brand.div()}",
        parse_mode="HTML",
        reply_markup=None,
    )
    await cb.answer("Збережено ✅")


@dp.message(F.func(lambda m: m.from_user is not None
                   and m.from_user.id in _edit_sessions
                   and not (m.text or "").startswith("/")))
async def handle_founder_edit_text(msg: Message):
    """Сохраняет кастомный текст от фаундера для редактируемого ключа."""
    uid = msg.from_user.id
    key = _edit_sessions.pop(uid, None)
    if not key:
        return

    raw_text = msg.text or msg.caption or ""
    if not raw_text.strip():
        _edit_sessions[uid] = key
        return await msg.reply("❌ Пустое сообщение — отправь текст (с Premium emoji).")

    raw_ents = msg.entities or msg.caption_entities or []
    ents_data = []
    for e in raw_ents:
        d: dict = {"type": e.type, "offset": e.offset, "length": e.length}
        if getattr(e, "url",            None): d["url"]            = e.url
        if getattr(e, "language",       None): d["language"]       = e.language
        if getattr(e, "custom_emoji_id",None): d["custom_emoji_id"]= e.custom_emoji_id
        ents_data.append(d)

    has_custom_emoji_saved = any(d.get("type") == "custom_emoji" for d in ents_data)
    brand.set_custom_text(key, raw_text, ents_data)
    brand_saved = await brand.persist_brand_now()

    label = brand.TEXT_LABELS.get(key, key)
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛠 Открыть редактор", callback_data="editor:menu")]
    ])

    emoji_warning = (
        "\n\n⚠️ <b>Важно про Premium emoji:</b>\n"
        "Боты НЕ могут отправлять анимированные emoji из личных Telegram Premium паков. "
        "Работают только emoji из bot-owned emoji паков (созданных через @Stickers для бота). "
        "Статичный юникод (😊🔥✨) работает всегда.\n"
        if has_custom_emoji_saved else ""
    )

    await msg.reply(
        (
            f"✅ <b>{html.escape(label)}</b> — сохранён!\n\n"
            +
             "Текст и форматирование записаны в PostgreSQL.\n"
            if brand_saved else
            f"✅ <b>{html.escape(label)}</b> — сохранён!\n\n"
             "Текст сохранён локально; PostgreSQL недоступен, автосинхронизация повторит запись.\n"
        )
        + emoji_warning
        + f"\n<code>/resettext {key}</code> — сбросить к дефолту.",
        parse_mode="HTML",
        reply_markup=back_kb,
    )


@dp.message(Command("edittext"))
async def cmd_edittext(msg: Message):
    """Редактор текстов бота — только для фаундера в ЛС."""
    if not is_owner(msg) or msg.chat.type != "private":
        return

    custom = brand.all_custom_texts()
    total  = sum(len(keys) for _, keys in _EDITOR_TEXT_CATEGORIES)
    done   = sum(1 for _, keys in _EDITOR_TEXT_CATEGORIES for k in keys if k in custom)

    await msg.answer(
        f"✏️ <b>Редактор текстов Lumenora</b>\n\n"
        f"📊 Изменено: <b>{done}</b> из <b>{total}</b> строк\n"
        f"📂 Категорий: <b>{len(_EDITOR_TEXT_CATEGORIES)}</b>\n\n"
        "Выбери категорию — внутри каждой постраничный список.\n"
        "Тапни строку → отправь новый текст с Premium emoji.\n\n"
        "✅ — кастомный   ⬜ — дефолт\n"
        "<code>/resettext ключ</code> — сбросить одну строку к дефолту",
        parse_mode="HTML",
        reply_markup=_editor_texts_kb(),
    )


@dp.callback_query(F.data.startswith("edittext:"))
async def cb_edittext(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    key = cb.data.split(":", 1)[1]
    if key not in brand.TEXT_LABELS:
        return await cb.answer("Неизвестный ключ", show_alert=True)

    _edit_sessions[cb.from_user.id] = key
    label    = brand.TEXT_LABELS[key]
    ct       = brand.get_custom_text(key)
    cur_text = brand.get_current_text(key)   # кастомный ИЛИ дефолт

    if ct:
        status_line = "📝 <b>Сейчас (кастомный):</b>"
    elif cur_text:
        status_line = "⬜ <b>Сейчас (дефолт):</b>"
    else:
        status_line = "⬜ <i>Текст не задан</i>"

    back_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отмена", callback_data="reply_edit_cancel"),
    ]])

    # Если есть custom_emoji entities — превью нельзя вставить в HTML-строку,
    # отправляем его отдельным сообщением с entities=, чтобы premium emoji были видны
    cts_data = ct  # tuple (text, entities) или None
    has_custom_emoji_preview = (
        cts_data is not None
        and any(e.get("type") == "custom_emoji" for e in (cts_data[1] or []))
    )

    if has_custom_emoji_preview:
        preview_note = "👁 <b>Текущее значение показано выше</b> (с Premium emoji)\n\n"
        try:
            _preview_ents = _build_entities(cts_data[1])
            await cb.message.answer(
                cts_data[0][:300] + ("…" if len(cts_data[0]) > 300 else ""),
                entities=_preview_ents or None,
            )
        except Exception:
            preview_note = f"<blockquote>{html.escape((cur_text or '')[:300])}</blockquote>\n\n"
    else:
        preview_note = (f"<blockquote>{html.escape(cur_text[:300])}</blockquote>\n\n"
                        if cur_text else "\n")

    await cb.message.answer(
        f"✏️ <b>{html.escape(label)}</b>\n\n"
        f"{status_line}\n"
        + preview_note
        + "Отправь новый текст — форматирование и Premium emoji сохранятся.\n"
        "<code>/отмена</code> — выйти без сохранения.",
        parse_mode="HTML",
        reply_markup=back_kb,
    )
    await cb.answer()


@dp.message(Command("resettext"))
async def cmd_resettext(msg: Message):
    """Сброс кастомного текста к дефолту — только для фаундера."""
    if not is_owner(msg) or msg.chat.type != "private":
        return
    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) < 2:
        keys_list = ", ".join(f"<code>{k}</code>" for k in brand.TEXT_LABELS)
        return await msg.reply(
            f"Использование: <code>/resettext ключ</code>\n\nКлючи:\n{keys_list}",
            parse_mode="HTML"
        )
    key = parts[1].strip()
    if key not in brand.TEXT_LABELS:
        return await msg.reply(f"❓ Ключ <code>{html.escape(key)}</code> не найден.", parse_mode="HTML")
    brand.del_custom_text(key)
    saved = await brand.persist_brand_now()
    await msg.reply(
        f"🔄 <b>{html.escape(brand.TEXT_LABELS[key])}</b> — сброшен к дефолту."
        + ("" if saved else "\n\n⚠️ PostgreSQL недоступен: изменение пока только локальное."),
        parse_mode="HTML"
    )


# ═══════════════════════════════════════════════════════
# КОМАНДА «ИЗМЕНИТЬ» — полный редактор контента бота
# Доступно: фаундеру и @veroniksssxa (только в ЛС)
# ═══════════════════════════════════════════════════════

_EDITOR_TEXT_CATEGORIES = [
    ("🏠 Главный экран",    ["start_text", "start_unverified"]),
    ("✅ Верификация",       ["verify_btn", "verify_prompt", "verify_confirm_btn", "verify_done"]),
    ("👋 Приветствие",       ["welcome_msg", "welcome_btn"]),
    ("👑 VIP & Поддержка",  ["vip_activated", "support_prompt", "support_sent"]),
    ("💰 Экономика",         ["balance", "work", "work_cooldown",
                              "fish", "fish_cooldown",
                              "give", "give_no_reply", "give_no_funds",
                              "give_self", "give_zero", "give_bot",
                              "casino_win", "casino_jackpot", "casino_lose",
                              "casino_no_bet", "casino_no_balance",
                              "casino_invalid_bet", "casino_negative_bet",
                              "slots_no_bet", "slots_no_balance", "slots_invalid_bet",
                              "rob_success", "rob_fail", "rob_cooldown",
                              "rob_no_reply", "rob_self", "rob_bot",
                              "rob_target_poor", "rob_victim_notify", "rob_banked",
                              "coin_rain", "coin_rain_collected"]),
    ("🏦 Банк",              ["bank_header", "bank_deposit_done", "bank_deposit_no_funds",
                              "bank_deposit_zero", "bank_withdraw_done",
                              "bank_withdraw_no_funds", "bank_withdraw_zero",
                              "bank_withdraw_cooldown"]),
    ("💍 Брак",              ["marry_proposal", "marry_accept", "marry_reject",
                              "marry_self", "marry_already", "marry_already_other",
                              "marry_no_reply", "marry_timeout",
                              "divorce", "divorce_not_married"]),
    ("🔥 Стрики & Аура",    ["checkin", "checkin_already", "checkin_milestone",
                              "upvote", "downvote", "rep", "aura_show"]),
    ("🎮 Игры",              ["rps_win", "rps_lose", "rps_tie",
                              "roulette_join", "roulette_winner",
                              "roulette_already", "roulette_join_msg",
                              "roulette_not_enough", "roulette_result",
                              "coin", "coin_heads", "coin_tails",
                              "hangman_start", "hangman_win", "hangman_lose",
                              "hangman_no_game", "hangman_letter_used",
                              "hangman_wrong", "hangman_right",
                              "game_dice", "game_roll", "game_choose",
                              "game_rate", "game_truth", "game_dare",
                              "game_riddle", "game_random"]),
    ("🤗 Социальные",        ["hug", "kiss", "gift", "slap", "pat",
                              "playful_kill", "playful_shoot", "playful_stab",
                              "deep_kiss", "confess_love",
                              "dance", "bite", "poke", "wave", "highfive",
                              "facepalm", "serenade"]),
    ("🛡 Модерация чата",   ["mute_done", "ban_done", "unban_done", "unmute_done",
                              "kick_done", "warn_done", "warn_ban", "unwarn_done",
                              "unwarn_no_warns",
                              "mute_self", "ban_self", "kick_self",
                              "admin_only", "reply_needed", "owner_only"]),
    ("🔮 Предсказания",     ["fortune_result", "horoscope_result", "tarot_result",
                              "fortune_destiny", "fortune_superpower", "fortune_profession",
                              "fortune_animal", "fortune_movie", "fortune_book",
                              "fortune_advice", "fortune_motivation", "fortune_myth",
                              "fortune_country", "fortune_color", "fortune_joke",
                              "fortune_compliment", "fortune_roast",
                              "fortune_8ball", "fortune_predict"]),
    ("🛒 Магазин и инвентарь", ["shop_header", "shop_coming_soon",
                                "inventory_header", "inventory_empty"]),
    ("ℹ️ Инфо",               ["info_project"]),
    ("👤 Профиль & Рейтинги", ["profile_no_bio", "profile_no_partner", "info_founder_badge",
                                "profile_header", "profile_bio_label",
                                "profile_balance_label", "profile_streak_label",
                                "profile_rep_label", "profile_marry_label", "profile_id_label",
                                "richest_header", "richest_empty", "richest_total",
                                "top_rep_header", "top_checkin_header"]),
]

_PAGE_SIZE = 8  # строк на страницу в категории


def _editor_main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Тексты",     callback_data="editor:texts"),
            InlineKeyboardButton(text="🔘 Кнопки",     callback_data="editor:btns"),
        ],
        [
            InlineKeyboardButton(text="🎨 Оформление", callback_data="editor:style"),
            InlineKeyboardButton(text="ℹ️ О проекте",  callback_data="editor:info_project"),
        ],
    ])


async def send_rich_message(chat_id: int, *, html: str | None = None, markdown: str | None = None) -> dict:
    """Отправка Rich Message (Bot API 10.1) — таблицы, чек-листы, заголовки, LaTeX, цитаты.
    aiogram ещё не имеет типизированного метода sendRichMessage, поэтому зовём Bot API напрямую."""
    rich_message: dict = {}
    if html is not None:
        rich_message["html"] = html
    if markdown is not None:
        rich_message["markdown"] = markdown
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendRichMessage"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={"chat_id": chat_id, "rich_message": rich_message}) as resp:
            return await resp.json()


def _editor_style_kb() -> InlineKeyboardMarkup:
    """Список редактируемых параметров оформления."""
    rows = []
    for key, df in brand.STYLE_DEFS.items():
        status = "✅" if brand.is_style_customized(key) else "⬜"
        cur    = brand.get_style(key)
        rows.append([InlineKeyboardButton(
            text=f"{status} {df['desc']}: {cur[:20]}",
            callback_data=f"editor:style_edit:{key}",
        )])
    rows.append([InlineKeyboardButton(text="✨ Сбросить всё к премиуму", callback_data="editor:style_reset_all")])
    rows.append([InlineKeyboardButton(text="📊 Rich-отчёт (таблицы/чек-листы)", callback_data="editor:style_rich_demo")])
    rows.append([InlineKeyboardButton(text="📰 Новости Telegram для ботов", url="https://t.me/BotNews")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="editor:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _editor_style_detail_kb(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Изменить",  callback_data=f"editor:style_input:{key}"),
            InlineKeyboardButton(text="🔄 Сбросить",  callback_data=f"editor:style_reset:{key}"),
        ],
        [InlineKeyboardButton(text="◀️ К оформлению", callback_data="editor:style")],
    ])


def _editor_texts_kb() -> InlineKeyboardMarkup:
    """Кнопки категорий текстов — 2 в ряд."""
    custom = brand.all_custom_texts()
    rows = []
    for i, (cat_name, cat_keys) in enumerate(_EDITOR_TEXT_CATEGORIES):
        done  = sum(1 for k in cat_keys if k in custom)
        total = len(cat_keys)
        label = f"{cat_name} ({done}/{total})" if done else cat_name
        rows.append([InlineKeyboardButton(text=label, callback_data=f"editor:cat:{i}:0")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="editor:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _editor_cat_kb(cat_idx: int, page: int = 0) -> InlineKeyboardMarkup:
    """Кнопки текстов в категории с пагинацией."""
    _, keys = _EDITOR_TEXT_CATEGORIES[cat_idx]
    valid_keys = [k for k in keys if k in brand.TEXT_LABELS]
    custom = brand.all_custom_texts()

    start  = page * _PAGE_SIZE
    end    = start + _PAGE_SIZE
    page_keys = valid_keys[start:end]
    total_pages = max(1, (len(valid_keys) + _PAGE_SIZE - 1) // _PAGE_SIZE)

    btns = []
    for k in page_keys:
        status = "✅" if k in custom else "⬜"
        short  = brand.TEXT_LABELS[k][:26]
        btns.append(InlineKeyboardButton(
            text=f"{status} {short}",
            callback_data=f"edittext:{k}",
        ))
    rows = [btns[i:i+2] for i in range(0, len(btns), 2)]

    # Навигация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"editor:cat:{cat_idx}:{page-1}"))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"editor:cat:{cat_idx}:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="◀️ Категории", callback_data="editor:texts")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _editor_btns_kb() -> InlineKeyboardMarkup:
    """Кнопки для редактирования кнопок бота."""
    rows = []
    for key, df in brand.BUTTON_DEFS.items():
        status = "✅" if brand.is_btn_customized(key) else "⬜"
        short  = df["desc"][:28]
        rows.append([InlineKeyboardButton(
            text=f"{status} {short}",
            callback_data=f"editor:btn:{key}",
        )])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="editor:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _editor_btn_detail_kb(key: str) -> InlineKeyboardMarkup:
    df = brand.BUTTON_DEFS.get(key, {})
    is_url_btn = df.get("type") == "url"
    btns_row = [InlineKeyboardButton(text="✏️ Изм. название", callback_data=f"editor:btn_label:{key}")]
    if is_url_btn:
        btns_row.append(InlineKeyboardButton(text="🔗 Изм. ссылку", callback_data=f"editor:btn_url:{key}"))
    rows = [
        btns_row,
        [
            InlineKeyboardButton(text="🔄 Сбросить",       callback_data=f"editor:btn_reset:{key}"),
            InlineKeyboardButton(text="◀️ К кнопкам",      callback_data="editor:btns"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _send_editor_menu(msg):
    """Отправляет главное меню редактора (используется из нескольких мест)."""
    await msg.answer(
        f"{brand.hdr()}\n\n"
        "🛠 <b>Настройки Lumenora</b>\n\n"
        "Выбери раздел:\n"
        "✏️ <b>Тексты</b> — все фразы и сообщения бота\n"
        "🔘 <b>Кнопки</b> — названия и ссылки кнопок\n"
        "🎨 <b>Оформление</b> — заголовок, разделитель, буллеты",
        parse_mode="HTML",
        reply_markup=_editor_main_menu_kb(),
    )


# ── Reply-редактор: фаундер отвечает на сообщение бота словом «изменить» ──────
# Регистрируется ПЕРВЫМ — более специфичный фильтр (reply + tracked msg)
def _is_reply_edit(m) -> bool:
    """True если: фаундер, слово «изменить»/«edit», ответ на сообщение бота.
    Не требует трекинга — ловит ответ на ЛЮБОЕ сообщение от бота."""
    if not is_owner(m):
        return False
    tl = (m.text or "").strip().lower().lstrip("/")
    if tl not in ("изменить", "edit"):
        return False
    rm = m.reply_to_message
    if not rm or not rm.from_user:
        return False
    # Сообщение должно быть от самого бота
    return rm.from_user.id == _BOT_ID


@dp.message(F.func(_is_reply_edit))
async def cmd_reply_edit(msg: Message):
    """Фаундер ответил на сообщение бота словом «изменить» → начать редактирование."""
    if not is_owner(msg):
        return  # тихо игнорируем
    rm = msg.reply_to_message

    # Пытаемся найти ключ по трекингу (работает только если бот не перезапускался)
    key = _tracked_bot_msgs.get((msg.chat.id, rm.message_id))

    # Если трекинг пуст — пробуем найти ключ по тексту сообщения
    if not key and rm.text:
        rm_text_stripped = rm.text.strip()
        for k, custom in brand.all_custom_texts().items():
            if k in brand.TEXT_LABELS and custom[0].strip() == rm_text_stripped:
                key = k
                break

    is_private = msg.chat.type == "private"

    if key and key in brand.TEXT_LABELS:
        # Ключ найден — открываем редактирование конкретного текста
        _edit_sessions[msg.from_user.id] = key
        label = brand.TEXT_LABELS[key]
        ct    = brand.get_custom_text(key)
        current_note = (
            f"Текущий текст:\n<blockquote>{html.escape(ct[0])}</blockquote>"
            if ct else "Сейчас: <i>встроенный дефолтный текст</i>"
        )
        back_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Отмена", callback_data="reply_edit_cancel"),
        ]])

        if is_private:
            await msg.reply(
                f"✏️ <b>{html.escape(label)}</b>\n\n"
                f"{current_note}\n\n"
                "Отправь новый текст — форматирование сохранится.\n"
                "/отмена или кнопка ниже — выйти без сохранения.",
                parse_mode="HTML",
                reply_markup=back_kb,
            )
        else:
            # В группе — просим зайти в ЛС (сессия уже открыта)
            dm_kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="✏️ Написать новый текст в ЛС",
                    url=f"https://t.me/{_BOT_USERNAME}",
                ),
            ]])
            await msg.reply(
                f"✏️ <b>{html.escape(label)}</b>\n\n"
                f"{current_note}\n\n"
                "Напиши новый текст мне <b>в личку</b> — нажми кнопку.\n"
                "Редактирование уже активировано.",
                parse_mode="HTML",
                reply_markup=dm_kb,
            )
    else:
        # Ключ не определён — открываем общее меню редактора
        await _send_editor_menu(msg)


@dp.callback_query(F.data == "reply_edit_cancel")
async def cb_reply_edit_cancel(cb: CallbackQuery):
    _edit_sessions.pop(cb.from_user.id, None)
    await cb.message.edit_text("❌ Редактирование отменено.", parse_mode="HTML")
    await cb.answer()


# /edit — латиница. is_owner вынесен В ФИЛЬТР и дублируется в теле
# (TEXT_COMMANDS диспетчер викликає без фільтра — потрібна перевірка в тілі)
@dp.message(Command("edit", "настройки", "settings"),
            F.chat.type == "private",
            F.func(lambda m: is_owner(m)))
async def cmd_editor_latin(msg: Message):
    if not is_owner(msg):
        return
    await _send_editor_menu(msg)


# Регистрируем после определения функции
TEXT_COMMANDS.update({
    "настройки": cmd_editor_latin,
    "settings":  cmd_editor_latin,
})


# «изменить» / «/изменить» — кириллица без reply: открываем общее меню.
# is_owner тоже в фильтре.
@dp.message(F.chat.type == "private",
            F.func(lambda m: is_owner(m)
                   and (m.text or "").strip().lower().lstrip("/") in ("изменить", "edit")
                   and not m.reply_to_message))
async def cmd_editor_ru(msg: Message):
    if not is_owner(msg):
        return  # тихо игнорируем — не показываем ошибку
    await _send_editor_menu(msg)


@dp.callback_query(F.data == "editor:menu")
async def cb_editor_menu(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    await cb.message.edit_text(
        f"{brand.hdr()}\n\n"
        "🛠 <b>Настройки Lumenora</b>\n\n"
        "Выбери раздел:\n"
        "✏️ <b>Тексты</b> — все фразы и сообщения бота\n"
        "🔘 <b>Кнопки</b> — названия и ссылки кнопок\n"
        "🎨 <b>Оформление</b> — заголовок, разделитель, буллеты",
        parse_mode="HTML",
        reply_markup=_editor_main_menu_kb(),
    )
    await cb.answer()


@dp.callback_query(F.data == "editor:info_project")
async def cb_editor_info_project(cb: CallbackQuery):
    """Прямой переход к редактированию текста «О проекте» из главного меню."""
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    uid = cb.from_user.id
    _edit_sessions[uid] = "info_project"
    ct = brand.get_custom_text("info_project")
    current_note = (
        f"Текущий текст:\n<blockquote>{html.escape(ct[0])}</blockquote>"
        if ct else "Сейчас: <i>стандартный текст /info</i>"
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад в меню", callback_data="editor:menu"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="reply_edit_cancel"),
    ]])
    await cb.message.edit_text(
        "ℹ️ <b>Описание проекта (/info)</b>\n\n"
        f"{current_note}\n\n"
        "Отправь новый текст — форматирование и Premium Emoji сохранятся.\n"
        "Изменение сразу увидят все участники.",
        parse_mode="HTML",
        reply_markup=back_kb,
    )
    await cb.answer()


@dp.callback_query(F.data == "editor:texts")
async def cb_editor_texts(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    custom = brand.all_custom_texts()
    total  = sum(len(keys) for _, keys in _EDITOR_TEXT_CATEGORIES)
    done   = sum(1 for _, keys in _EDITOR_TEXT_CATEGORIES
                 for k in keys if k in custom)
    await cb.message.edit_text(
        f"✏️ <b>Тексты бота</b>\n\n"
        f"Изменено: <b>{done}</b> из <b>{total}</b> строк\n\n"
        "Выбери категорию:",
        parse_mode="HTML",
        reply_markup=_editor_texts_kb(),
    )
    await cb.answer()


@dp.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()


@dp.callback_query(F.data.startswith("editor:cat:"))
async def cb_editor_cat(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    try:
        parts   = cb.data.split(":")
        if len(parts) not in (3, 4):
            raise ValueError
        cat_idx = int(parts[2])
        page    = int(parts[3]) if len(parts) > 3 else 0
    except (ValueError, IndexError):
        return await cb.answer("Ошибка", show_alert=True)
    if not (0 <= cat_idx < len(_EDITOR_TEXT_CATEGORIES)):
        return await cb.answer("Ошибка", show_alert=True)

    cat_name, keys = _EDITOR_TEXT_CATEGORIES[cat_idx]
    valid_keys  = [k for k in keys if k in brand.TEXT_LABELS]
    custom      = brand.all_custom_texts()
    total_pages = max(1, (len(valid_keys) + _PAGE_SIZE - 1) // _PAGE_SIZE)
    page        = max(0, min(page, total_pages - 1))
    start       = page * _PAGE_SIZE
    page_keys   = valid_keys[start:start + _PAGE_SIZE]

    lines = [
        f"✏️ <b>{html.escape(cat_name)}</b>",
        f"<i>Стр. {page+1}/{total_pages} · {len(valid_keys)} строк</i>",
        "✅ кастомный   ⬜ дефолт\n",
    ]
    for k in page_keys:
        status   = "✅" if k in custom else "⬜"
        label    = html.escape(brand.TEXT_LABELS[k])
        cur_text = brand.get_current_text(k)
        preview  = html.escape(cur_text[:60].replace("\n", " ")) + ("…" if len(cur_text) > 60 else "")
        lines.append(f"  {status} <b>{label}</b>")
        if preview:
            lines.append(f"      <i>{preview}</i>")

    await cb.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=_editor_cat_kb(cat_idx, page),
    )
    await cb.answer()


@dp.callback_query(F.data == "editor:btns")
async def cb_editor_btns(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    lines = ["🔘 <b>Кнопки бота</b>\n",
             "✅ — изменена   ⬜ — стандартная\n"]
    for key, df in brand.BUTTON_DEFS.items():
        status     = "✅" if brand.is_btn_customized(key) else "⬜"
        cur_label  = html.escape(brand.btn_label(key))
        lines.append(f"  {status} <b>{html.escape(df['desc'])}</b>: {cur_label}")
    await cb.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=_editor_btns_kb(),
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("editor:btn:"))
async def cb_editor_btn_detail(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    key = cb.data.split(":", 2)[-1]
    if key not in brand.BUTTON_DEFS:
        return await cb.answer("Неизвестная кнопка", show_alert=True)
    df         = brand.BUTTON_DEFS[key]
    cur_label  = html.escape(brand.btn_label(key))
    cur_url    = brand.btn_url(key)
    is_url_btn = df.get("type") == "url"
    lines = [
        f"🔘 <b>{html.escape(df['desc'])}</b>\n",
        f"Название: <b>{cur_label}</b>",
    ]
    if is_url_btn:
        lines.append(f"Ссылка: <code>{html.escape(cur_url or '—')}</code>")
    if brand.is_btn_customized(key):
        lines.append("\n<i>Изменена относительно дефолта.</i>")
    await cb.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=_editor_btn_detail_kb(key),
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("editor:btn_label:"))
async def cb_editor_btn_label(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    key = cb.data.split(":", 2)[-1]
    if key not in brand.BUTTON_DEFS:
        return await cb.answer("Неизвестная кнопка", show_alert=True)
    _btn_edit_sessions[cb.from_user.id] = {"key": key, "step": "label"}
    cur = html.escape(brand.btn_label(key))
    await cb.message.answer(
        f"✏️ <b>Новое название кнопки</b>\n\n"
        f"Сейчас: <b>{cur}</b>\n\n"
        "Отправь новый текст кнопки.\n"
        "/отмена — выйти без сохранения.",
        parse_mode="HTML",
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("editor:btn_url:"))
async def cb_editor_btn_url(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    key = cb.data.split(":", 2)[-1]
    df  = brand.BUTTON_DEFS.get(key, {})
    if df.get("type") != "url":
        return await cb.answer("Эта кнопка без ссылки", show_alert=True)
    _btn_edit_sessions[cb.from_user.id] = {"key": key, "step": "url"}
    cur = html.escape(brand.btn_url(key) or "не задана")
    await cb.message.answer(
        f"🔗 <b>Новая ссылка кнопки</b>\n\n"
        f"Сейчас: <code>{cur}</code>\n\n"
        "Отправь новую ссылку (https://...).\n"
        "/отмена — выйти без сохранения.",
        parse_mode="HTML",
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("editor:btn_reset:"))
async def cb_editor_btn_reset(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    key = cb.data.split(":", 2)[-1]
    if key not in brand.BUTTON_DEFS:
        return await cb.answer("Неизвестная кнопка", show_alert=True)
    brand.reset_custom_button(key)
    saved = await brand.persist_brand_now()
    df = brand.BUTTON_DEFS[key]
    await cb.answer(
        f"🔄 «{df['desc']}» сброшена к дефолту"
        if saved else "⚠️ Изменение локальное: PostgreSQL недоступен",
        show_alert=True,
    )
    # Обновляем сообщение
    lines = ["🔘 <b>Кнопки бота</b>\n",
             "✅ — изменена   ⬜ — стандартная\n"]
    for k, d in brand.BUTTON_DEFS.items():
        status    = "✅" if brand.is_btn_customized(k) else "⬜"
        cur_label = html.escape(brand.btn_label(k))
        lines.append(f"  {status} <b>{html.escape(d['desc'])}</b>: {cur_label}")
    await cb.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=_editor_btns_kb(),
    )


@dp.callback_query(F.data == "editor:style")
async def cb_editor_style(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    lines = ["🎨 <b>Оформление бота</b>\n",
             "✅ — изменено   ⬜ — стандартное\n"]
    for key, df in brand.STYLE_DEFS.items():
        status = "✅" if brand.is_style_customized(key) else "⬜"
        cur    = html.escape(brand.get_style(key))
        lines.append(f"  {status} <b>{html.escape(df['desc'])}</b>: <code>{cur}</code>")
    lines.append(f"\n{brand.div()}")
    lines.append(f"Заголовок: {brand.hdr()}")
    await cb.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=_editor_style_kb(),
    )
    await cb.answer()


@dp.callback_query(F.data == "editor:style_reset_all")
async def cb_editor_style_reset_all(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    # Отвечаем сразу, чтобы у кнопки не крутились "часики" пока идёт работа —
    # Telegram отменяет callback, если на него не ответить за ~10 секунд.
    await cb.answer("✨ Сбрасываю к премиуму...")
    try:
        brand.reset_all_styles()
        brand.reset_all_buttons()
        saved = await brand.persist_brand_now()
        lines = ["🎨 <b>Оформление бота</b>\n",
                 "✨ Все стили и кнопки сброшены к премиальным дефолтам\n",
                 "✅ — изменено   ⬜ — стандартное\n"]
        for key, df in brand.STYLE_DEFS.items():
            status = "✅" if brand.is_style_customized(key) else "⬜"
            cur    = html.escape(brand.get_style(key))
            lines.append(f"  {status} <b>{html.escape(df['desc'])}</b>: <code>{cur}</code>")
        lines.append(f"\n{brand.div()}")
        lines.append(f"Заголовок: {brand.hdr()}")
        try:
            await cb.message.edit_text(
                "\n".join(lines),
                parse_mode="HTML",
                reply_markup=_editor_style_kb(),
            )
        except TelegramAPIError as ex:
            if "message is not modified" not in str(ex).lower():
                raise
        if not saved:
            await cb.message.answer("⚠️ Сохранено локально: PostgreSQL недоступен")
    except Exception as ex:
        print(f"⚠️ cb_editor_style_reset_all: {ex}")
        try:
            await cb.message.answer(f"⚠️ Ошибка сброса: {ex}")
        except Exception:
            pass


@dp.callback_query(F.data == "editor:style_rich_demo")
async def cb_editor_style_rich_demo(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    await cb.answer("📊 Собираю rich-отчёт...")
    try:
        total_users     = len(user_xp)
        total_lmn       = sum(lmn_balances.values()) + sum(bank_balances.values())
        total_marriages = sum(len(m) for m in marriages.values()) // 2
        top_uid, top_xp = max(user_xp.items(), key=lambda kv: kv[1], default=(None, 0))
        top_name = f"ID {top_uid}" if top_uid else "—"

        rich_html = (
            "<h1>✨ Lumenora — Rich-отчёт</h1>"
            "<p>Живая сводка по экономике и сообществу, собранная через "
            "<b>Bot API 10.1 Rich Messages</b>.</p>"
            "<hr>"
            "<h2>📊 Ключевые метрики</h2>"
            "<table>"
            "<tr><th>Показатель</th><th>Значение</th></tr>"
            f"<tr><td>Пользователей с XP</td><td>{total_users}</td></tr>"
            f"<tr><td>LMN в обороте</td><td>{total_lmn}</td></tr>"
            f"<tr><td>Пар в браке</td><td>{total_marriages}</td></tr>"
            f"<tr><td>Лидер по XP</td><td>{top_name} ({top_xp} XP)</td></tr>"
            "</table>"
            "<h2>🗺 Дорожная карта оформления</h2>"
            "<ul type=\"checklist\">"
            "<li checked>Премиальный стиль (заголовки, разделители, эмодзи)</li>"
            "<li checked>Меню команд и описание бота в Telegram</li>"
            "<li checked>Rich-форматирование: таблицы, заголовки, чек-листы</li>"
            "<li>Карты и медиаколлажи (нужны координаты/файлы — по запросу)</li>"
            "</ul>"
            "<blockquote>Rich Messages — новый формат Bot API 10.1, "
            "поддерживается напрямую через sendRichMessage.</blockquote>"
        )
        result = await send_rich_message(cb.from_user.id, html=rich_html)
        if not result.get("ok"):
            raise RuntimeError(result.get("description", "unknown error"))
    except Exception as ex:
        print(f"⚠️ cb_editor_style_rich_demo: {ex}")
        try:
            await cb.message.answer(f"⚠️ Rich-отчёт не отправлен: {ex}")
        except Exception:
            pass


@dp.callback_query(F.data.startswith("editor:style_edit:"))
async def cb_editor_style_detail(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    key = cb.data.split(":", 2)[-1]
    if key not in brand.STYLE_DEFS:
        return await cb.answer("Неизвестный параметр", show_alert=True)
    df  = brand.STYLE_DEFS[key]
    cur = html.escape(brand.get_style(key))
    status = "✅ изменено" if brand.is_style_customized(key) else "⬜ стандартное"
    await cb.message.edit_text(
        f"🎨 <b>{html.escape(df['desc'])}</b>\n\n"
        f"Статус: {status}\n"
        f"Сейчас: <code>{cur}</code>\n\n"
        f"<i>{html.escape(df['hint'])}</i>",
        parse_mode="HTML",
        reply_markup=_editor_style_detail_kb(key),
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("editor:style_input:"))
async def cb_editor_style_input(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    key = cb.data.split(":", 2)[-1]
    if key not in brand.STYLE_DEFS:
        return await cb.answer("Неизвестный параметр", show_alert=True)
    df = brand.STYLE_DEFS[key]
    _style_edit_sessions[cb.from_user.id] = key
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"editor:style_edit:{key}"),
    ]])
    await cb.message.answer(
        f"✏️ <b>{html.escape(df['desc'])}</b>\n\n"
        f"Сейчас: <code>{html.escape(brand.get_style(key))}</code>\n\n"
        f"<i>{html.escape(df['hint'])}</i>\n\n"
        "Отправь новое значение:",
        parse_mode="HTML",
        reply_markup=cancel_kb,
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("editor:style_reset:"))
async def cb_editor_style_reset(cb: CallbackQuery):
    if not is_owner(cb):
        return await cb.answer("⛔", show_alert=True)
    key = cb.data.split(":", 2)[-1]
    if key not in brand.STYLE_DEFS:
        return await cb.answer("Неизвестный параметр", show_alert=True)
    brand.reset_style(key)
    saved = await brand.persist_brand_now()
    df = brand.STYLE_DEFS[key]
    await cb.answer(
        f"🔄 «{df['desc']}» сброшено к дефолту"
        if saved else "⚠️ Изменение локальное: PostgreSQL недоступен",
        show_alert=False,
    )
    # обновить экран детали
    cur = html.escape(brand.get_style(key))
    await cb.message.edit_text(
        f"🎨 <b>{html.escape(df['desc'])}</b>\n\n"
        f"Статус: ⬜ стандартное\n"
        f"Сейчас: <code>{cur}</code>\n\n"
        f"<i>{html.escape(df['hint'])}</i>",
        parse_mode="HTML",
        reply_markup=_editor_style_detail_kb(key),
    )


@dp.message(F.chat.type == "private",
            F.func(lambda m: m.from_user is not None
                   and m.from_user.id in _style_edit_sessions
                   and not (m.text or "").startswith("/")))
async def handle_style_edit_input(msg: Message):
    """Принимает новое значение параметра оформления."""
    uid  = msg.from_user.id
    key  = _style_edit_sessions.pop(uid, None)
    if not key or key not in brand.STYLE_DEFS:
        return
    df   = brand.STYLE_DEFS[key]
    text = (msg.text or "").strip()
    if not text:
        _style_edit_sessions[uid] = key
        return await msg.reply("❌ Пустое сообщение — отправь значение.")
    if len(text) > df["max"]:
        _style_edit_sessions[uid] = key
        return await msg.reply(f"❌ Слишком длинно (максимум {df['max']} символов).")
        args_str = parts[1] if len(parts) > 1 else ""

        # Конвертируем русские суффиксы ТОЛЬКО в первом слове (время),
        # чтобы не портить текст причины ("нарушение чата" и т.д.)
        _ac_parts = args_str.split(maxsplit=1)
        _ac_time  = _ac_parts[0].replace("м","m").replace("ч","h").replace("д","d") if _ac_parts else ""
        _ac_rest  = (" " + _ac_parts[1]) if len(_ac_parts) > 1 else ""
        args_converted = _ac_time + _ac_rest

        class FakeCmd:
            args = args_converted

        fake_cmd = FakeCmd()

        # Бан и мут — только через !
        BAN_MUTE = {
            # Мут
            "мут": cmd_mute, "mute": cmd_mute,
            "замутить": cmd_mute, "замут": cmd_mute,
            # Бан
            "бан": cmd_ban, "ban": cmd_ban,
            "забанить": cmd_ban, "забан": cmd_ban,
            # Форс
            "форсбан": cmd_forceban, "forceban": cmd_forceban,
            "форсмут": cmd_forcemute, "forcemute": cmd_forcemute,
            # Мут на 1 минуту
            "мут1": cmd_mute1, "mute1": cmd_mute1,
            # Размут / разбан / кик через ! тоже работают
            "размут": cmd_unmute, "unmute": cmd_unmute,
            "разбан": cmd_unban,  "unban":  cmd_unban,
            "кик":    cmd_kick,   "kick":   cmd_kick,
            # Варн
            "варн": cmd_warn,   "warn": cmd_warn,
            "снятьварн": cmd_unwarn, "unwarn": cmd_unwarn,
        }
        if cmd_word in BAN_MUTE:
            try: await BAN_MUTE[cmd_word](msg, fake_cmd)
            except TypeError: await BAN_MUTE[cmd_word](msg)
            return

        # Остальные ! команды
        if cmd_word in TEXT_COMMANDS:
            try: await TEXT_COMMANDS[cmd_word](msg, fake_cmd)
            except TypeError: await TEXT_COMMANDS[cmd_word](msg)
            return
        return

    # Telegram не всегда передаёт кириллические slash-команды как entity
    # типа bot_command. Разбираем их резервно по обычному тексту.
    if text.startswith("/"):
        slash_parts = text[1:].split(maxsplit=1)
        slash_word = (slash_parts[0] if slash_parts else "").split("@", 1)[0].lower()
        if slash_word in TEXT_COMMANDS:
            class SlashFakeCmd:
                args = slash_parts[1] if len(slash_parts) > 1 else ""

            try:
                await TEXT_COMMANDS[slash_word](msg, SlashFakeCmd())
            except TypeError:
                await TEXT_COMMANDS[slash_word](msg)
        return

    # ── Команды без префикса
    if not text.startswith("/"):
        # Ищем команду по первому слову (и двум словам)
        parts = tl.split(maxsplit=2)
        three_words = " ".join(parts[:3]) if len(parts) >= 3 else ""
        two_words = " ".join(parts[:2]) if len(parts) >= 2 else ""
        first_word = parts[0] if parts else ""

        # Сначала пробуем составные команды (например "признаться в любви"),
        # затем двухсловные и обычные.
        handler = (
            TEXT_COMMANDS.get(three_words)
            or TEXT_COMMANDS.get(two_words)
            or TEXT_COMMANDS.get(first_word)
        )

        if handler:
            # Аргументы = всё после первого (или двух) слов
            if TEXT_COMMANDS.get(three_words):
                args_str = " ".join(parts[3:]) if len(parts) > 3 else ""
            elif TEXT_COMMANDS.get(two_words):
                args_str = " ".join(parts[2:]) if len(parts) > 2 else ""
            else:
                args_str = " ".join(parts[1:]) if len(parts) > 1 else ""

            # Не меняем кириллицу в аргументах: например, знак "водолей"
            # содержит букву "д" и раньше превращался в "водолей" с
            # латинской буквой, из-за чего гороскоп не находил знак.
            # parse_time_and_reason сам нормализует суффиксы времени там,
            # где они действительно нужны.
            args_converted = args_str

            class FakeCmd2:
                args = args_converted or None

            try: await handler(msg, FakeCmd2())
            except TypeError: await handler(msg)
            return

        if _is_nexus_launch_request(msg):
            await msg.reply(NEXUS_LAUNCH_RESPONSE)
            return

        # Свободный AI-диалог разрешён только founder и deputy.
        if _is_lumena_ai_allowed(msg):
            if msg.chat.type == "private":
                await _lumena_ai_private(msg)
                return
            # Групповой хелпер сам проверяет reply/@mention/обращение по имени.
            # Не дублируем здесь адресатор, чтобы условия не расходились.
            await _lumena_ai_group(msg)
            return
        return

# ═══════════════════════════════════════════════════════
@dp.message(F.voice)
async def handle_staff_voice_message(msg: Message):
    """Анализирует присланное voice-сообщение сотрудника.

    Telegram Bot API не передаёт живой Voice Chat, но обычные voice-сообщения
    бот получает как файл. Адресат определяется только по reply, как и для
    текстовой аналитики.
    """
    if msg.chat.type == "private" or not msg.from_user or not _is_staff_uid(msg.from_user.id, msg.chat.id):
        return
    target = _staff_target_from_message(msg)
    cid = msg.chat.id
    stats = staff_voice_stats.setdefault(cid, {}).setdefault(str(msg.from_user.id), {
        "received": 0, "analyzed": 0, "failed": 0,
    })
    stats["received"] = int(stats.get("received", 0)) + 1
    if not target or not _is_staff_uid(target.id, msg.chat.id) or target.id == msg.from_user.id:
        stats["failed"] = int(stats.get("failed", 0)) + 1
        if stats["received"] % 5 == 0:
            schedule_state_save("статистика voice команды")
        return
    try:
        telegram_file = await bot.get_file(msg.voice.file_id)
        audio = io.BytesIO()
        await bot.download(telegram_file, destination=audio)
        transcript = await ai_agent.transcribe_audio(audio.getvalue())
    except Exception:
        transcript = None
    if not transcript:
        stats["failed"] = int(stats.get("failed", 0)) + 1
        schedule_state_save("ошибка расшифровки voice команды")
        return
    stats["analyzed"] = int(stats.get("analyzed", 0)) + 1
    reason = _staff_bad_reason(transcript)
    _record_staff_interaction(
        msg, target, bad=bool(reason), reason=reason, source="voice",
    )
    schedule_state_save("анализ voice команды")


# АВТОПІДКАЗКА КОЛИ БОТ ВХОДИТЬ У НОВИЙ ЧАТ
# ═══════════════════════════════════════════════════════
_DEFAULT_WELCOME = (
    "👋 *Добро пожаловать, {name}!*\n\n"
    "💫 Рады видеть тебя в сообществе Lumenora!\n\n"
    "Здесь есть общение, игры, отношения и своя экономика.\n\n"
    "ℹ️ Бот: @LumenarAi\\_Bot"
)


@dp.message(F.new_chat_members)
async def on_new_chat_member(msg: Message):
    """Вітає кожного нового учасника в групових чатах."""
    for user in msg.new_chat_members:
        if user.is_bot:
            continue
        name = user.first_name or user.full_name or "друг"

        # V6: рейд-мод — мутируем новых участников на 10 минут
        if raid_mode.get(msg.chat.id):
            # Не мутируем фаундера и Telegram-администраторов чата
            _skip_raid = user.id == OWNER_ID
            if not _skip_raid:
                try:
                    _cm = await bot.get_chat_member(msg.chat.id, user.id)
                    if _cm.status in ("creator", "administrator"):
                        _skip_raid = True
                except Exception:
                    pass
            if not _skip_raid:
                try:
                    until = datetime.now(UTC) + timedelta(minutes=10)
                    await bot.restrict_chat_member(
                        msg.chat.id, user.id,
                        ChatPermissions(can_send_messages=False),
                        until_date=until,
                    )
                    _log_mod(msg.chat.id, "raid_mute", user.id, 0)
                except Exception as _re:
                    pass

        # ── Текст кнопки (кастомный или дефолтный) ───────
        welcome_rows = [[
            InlineKeyboardButton(
                text="📖 Правила чата",
                url="https://teletype.in/@lumenaoff/eoHmmuUNnxP",
            ),
        ]]
        if LUMENA_SITE_URL:
            welcome_rows.append([
            InlineKeyboardButton(text="Сайт Lumenora", url=LUMENA_SITE_URL),
            ])
        kb = InlineKeyboardMarkup(inline_keyboard=welcome_rows)

        # ── Текст приветствия ─────────────────────────────
        ct = brand.get_custom_text("welcome_msg")
        try:
            if ct:
                raw_text, ents_data = ct
                # Подставляем {name} и корректируем офсеты entities
                final_text, final_ents_data = brand.substitute_name(raw_text, ents_data, name)
                ents = _build_entities(final_ents_data)
                await msg.answer(final_text, entities=ents or None, reply_markup=kb)
            else:
                await msg.answer(
                    _DEFAULT_WELCOME.format(name=name),
                    parse_mode="Markdown",
                    reply_markup=kb,
                )
        except Exception:
            pass


@dp.my_chat_member()
async def on_bot_added(event: ChatMemberUpdated):
    """Коли бота додають у чат — відразу підказує команди налаштування."""
    new_status = event.new_chat_member.status
    if new_status not in ("member", "administrator"):
        return
    chat_id = event.chat.id
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📖 Все команды", callback_data="help:menu"),
    ]])
    try:
        await bot.send_message(
            chat_id,
             f"👋 Привет! Я <b>Lumenora</b> — умный бот для вашего чата 💙\n\n"
            "",
            parse_mode="HTML",
            reply_markup=kb,
        )
    except Exception:
        pass

# ═══════════════════════════════════════════════════════
# ЗАПУСК
# ═══════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════
# ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОШИБОК ХЕНДЛЕРОВ
# ═══════════════════════════════════════════════════════
@dp.errors()
async def global_error_handler(event, **kwargs):
    exc = getattr(event, "exception", None) or kwargs.get("exception")
    logging.error(f"⚠️ Необработанная ошибка: {type(exc).__name__}: {exc}")
    return True  # помечаем как обработанное, polling не падает


async def main():
    # 0. Ініціалізація PostgreSQL (якщо DATABASE_URL задано)
    await _db.init_db()

    # 1. Відновлюємо дані: PostgreSQL → GitHub → локальний файл
    await restore_bot_data()
    await brand.restore_brand()
    load_data()
    if apply_marriage_date_migrations():
        await save_state_now("миграция даты брака фаундера и заместителя")
    await _restore_night_mode_permissions()
    # ── Захист від повторного спрацювання одноразових LMN-міграцій ──────────
    # Версії міграцій раніше зберігались лише всередині великого bot_data
    # знімку. Якщо його відновлення хоч раз пройде не повністю (гонка,
    # обірваний запис БД тощо), лічильники версій відкочуються на 0 і
    # міграції — обнулення/переказ усіх гаманців — спрацьовують ЗНОВУ,
    # через що монети «зникають» у всіх учасників чату. Тепер версія кожної
    # міграції додатково звіряється й негайно записується в окремий,
    # незалежний ключ БД, ще до будь-якого запису великого знімку.
    global lmn_balance_reset_version, lmn_transfer_version, lmn_global_zero_version, founder_grant_version
    if _db.has_pg():
        migration_state = await _db.db_get("lmn_migrations") or {}
        lmn_balance_reset_version = max(
            lmn_balance_reset_version, int(migration_state.get("reset_version", 0) or 0)
        )
        lmn_transfer_version = max(
            lmn_transfer_version, int(migration_state.get("transfer_version", 0) or 0)
        )
        lmn_global_zero_version = max(
            lmn_global_zero_version, int(migration_state.get("global_zero_version", 0) or 0)
        )
        founder_grant_version = max(
            founder_grant_version, int(migration_state.get("founder_grant_version", 0) or 0)
        )

    if normalize_lmn_balances_once():
        if _db.has_pg():
            await _db.db_set("lmn_migrations", {
                "reset_version": lmn_balance_reset_version,
                "transfer_version": lmn_transfer_version,
            })
        await save_state_now("одноразовое выравнивание LMN-балансов")
        # Компенсационное объявление отправлено вручную ранее.
        # При редеплое никакие сообщения в чаты не отправляются.
    if transfer_all_balances_to_founder():
        if _db.has_pg():
            await _db.db_set("lmn_migrations", {
                "reset_version": lmn_balance_reset_version,
                "transfer_version": lmn_transfer_version,
                "global_zero_version": lmn_global_zero_version,
            })
        await save_state_now("перевод всех LMN-балансов фаундеру")
    if zero_all_lmn_balances_once():
        if _db.has_pg():
            await _db.db_set("lmn_migrations", {
                "reset_version": lmn_balance_reset_version,
                "transfer_version": lmn_transfer_version,
                "global_zero_version": lmn_global_zero_version,
                "founder_grant_version": founder_grant_version,
            })
        await save_state_now("обнуление всех LMN-балансов")
    if grant_founder_amount_once():
        if _db.has_pg():
            await _db.db_set("lmn_migrations", {
                "reset_version": lmn_balance_reset_version,
                "transfer_version": lmn_transfer_version,
                "global_zero_version": lmn_global_zero_version,
                "founder_grant_version": founder_grant_version,
            })
        await save_state_now("начисление суммы фаундеру")

    # ── Отложенные уведомления при старте ОТКЛЮЧЕНЫ ──────────────────────────
    # Требование: после редеплоя бот НЕ отправляет никаких сообщений в чаты.
    # Накопившаяся очередь молча очищается.
    if pending_notifications:
        logging.info("🔕 Очищено %d отложенных уведомлений без отправки", len(pending_notifications))
        pending_notifications.clear()
        await save_state_now("очистка отложенных уведомлений без отправки")

    brand.load_custom_texts()
    brand.load_custom_buttons()
    brand.load_custom_style()

    # ── Загружаем постоянную объединённую emoji-тему ─────
    _desired_emoji_packs = [PRIMARY_EMOJI_PACK, *EXTRA_EMOJI_PACKS]
    _current_emoji_packs = [
        part.strip()
        for part in brand.get_pack_name().split("+")
        if part.strip()
    ]
    _theme_needs_refresh = (
        not brand.has_pack()
        or not brand.has_emoji_map()
        or _current_emoji_packs != _desired_emoji_packs
    )
    _theme_changed = False
    if _theme_needs_refresh:
        try:
            _ids, _emoji_map = await _fetch_emoji_pack(PRIMARY_EMOJI_PACK)
            if _ids:
                brand.set_pack(_ids, PRIMARY_EMOJI_PACK, _emoji_map)
                _theme_changed = True
                print(
                    f"✅ Основной emoji пак загружен: "
                    f"{PRIMARY_EMOJI_PACK} ({len(_ids)} emoji)"
                )
        except Exception as _ex:
            print(
                f"⚠️ Не удалось загрузить основной emoji пак "
                f"'{PRIMARY_EMOJI_PACK}': {_ex}"
            )

    # ── Подмешиваем дополнительные тематические паки ─────
    _extra_pack_changed = False
    for _extra_pack in EXTRA_EMOJI_PACKS:
        if not _theme_changed and _extra_pack in _current_emoji_packs:
            continue
        try:
            _extra_ids, _extra_map = await _fetch_emoji_pack(_extra_pack)
            _before_ids = len(brand.get_pack())
            brand.merge_pack(_extra_ids, _extra_pack, _extra_map)
            if (
                len(brand.get_pack()) != _before_ids
                or _extra_pack not in brand.get_pack_name().split("+")
            ):
                _extra_pack_changed = True
            print(
                f"✅ Emoji пак смешан: {_extra_pack} "
                f"(+{len(brand.get_pack()) - _before_ids}, всего {len(brand.get_pack())})"
            )
        except Exception as _ex:
            print(f"⚠️ Не удалось подмешать emoji пак '{_extra_pack}': {_ex}")
    if _theme_changed or _extra_pack_changed:
        await save_state_now("автоматическое смешивание дополнительных emoji-паков")

    asyncio.create_task(auto_save_loop())
    asyncio.create_task(coin_rain_loop())
    asyncio.create_task(auction_loop())
    asyncio.create_task(admin_mute_restore_loop())

    # V6-объявление больше НЕ отправляется автоматически при старте —
    # только вручную через /announce_v6 (иначе каждый редеплой спамил чат).

    # Автоматически выдаём постоянным сотрудникам их роль в обоих связанных
    # чатах. Ошибка здесь не останавливает polling: чат мог ещё не добавить
    # пользователя или бот мог временно не иметь права промоушена.
    for _fixed_uid, _fixed_role in _fixed_staff_roles():
        for _role_chat_id in _role_sync_chat_ids():
            await _promote_in_chat(_fixed_uid, _fixed_role, _role_chat_id)

    # ── Очищаем меню команд Telegram (команды работают без /)
    global _BOT_ID, _BOT_USERNAME
    try:
        me = await bot.get_me()
        _BOT_ID = me.id
        _BOT_USERNAME = me.username or ""
    except Exception as _e:
        logging.warning(f"get_me: {_e}")
    try:
        await bot.delete_my_commands(scope=BotCommandScopeDefault())
        await bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats())
        await bot.delete_my_commands(scope=BotCommandScopeAllGroupChats())
    except Exception as _e:
        logging.warning(f"delete_my_commands: {_e}")

    await _send_lumena_marriage_proposal()

    # Единоразовая выдача @VladMish11
    from award_vlad import run_award
    asyncio.create_task(run_award(
        bot, chat_members, add_balance, fmt_lmn, save_data, ChatMemberStatus
    ))

    # Единоразовое снятие монет у @VladMish11
    from deduct_vlad import run_deduct
    asyncio.create_task(run_deduct(
        bot, chat_members, lmn_balances, fmt_lmn, save_data, ChatMemberStatus
    ))

    print(f"🤖 Lumenora v{BOT_VERSION} запущен!")

    # ── SIGTERM handler (Railway зупиняє контейнер через SIGTERM) ────────
    _shutdown_event = asyncio.Event()

    def _handle_sigterm():
        print("🛑 SIGTERM отримано — збереження і завершення...")
        _shutdown_event.set()

    import signal
    loop_ref = asyncio.get_event_loop()
    loop_ref.add_signal_handler(signal.SIGTERM, _handle_sigterm)
    loop_ref.add_signal_handler(signal.SIGINT,  _handle_sigterm)

    async def _shutdown_watcher():
        await _shutdown_event.wait()
        print("💾 Фінальне збереження ВСІХ файлів перед зупинкою...")
        save_data()
        try:
            await _save_all_to_db()
            print("✅ Всі дані збережено перед зупинкою")
        except Exception as _se:
            print(f"⚠️ Shutdown save error: {_se}")
        await _db.close_db()
        # Зупиняємо polling
        await dp.stop_polling()

    asyncio.create_task(_shutdown_watcher())

    # Сбрасываем webhook и вытесняем любой другой активный polling-инстанс
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        print("✅ Webhook сброшен — polling запускается как единственный инстанс")
    except Exception as _whe:
        logging.warning(f"delete_webhook: {_whe}")

    # ── Премиальная витрина бота в Telegram ──────────────────────────
    # Меню команд, описание в пустом чате, короткое описание в профиле
    # и кнопка меню — то, что Telegram Bot API официально даёт разработчикам.
    try:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="✨ Открыть Lumenora"),
                BotCommand(command="profile", description="👑 Мой профиль"),
                BotCommand(command="help", description="📖 Все команды"),
                BotCommand(command="settings", description="🎨 Настройки и оформление"),
                BotCommand(command="theme", description="🎨 Установить emoji-пак"),
                BotCommand(command="addtheme", description="➕ Смешать emoji-пак"),
                BotCommand(command="top", description="⭐ Топ участников"),
                BotCommand(command="shop", description="💎 Магазин"),
                BotCommand(command="game", description="🏗 Открыть Котострой"),
                BotCommand(command="date", description="💌 Свидание"),
                BotCommand(command="history", description="📖 Летопись пары"),
                BotCommand(command="wedding", description="💒 Свадьба"),
                BotCommand(command="destiny", description="🔮 Судьба пары"),
                BotCommand(command="contract", description="📜 Брачный контракт"),
                BotCommand(command="helplum", description="📩 Жалобы и вопросы"),
            ],
            scope=BotCommandScopeAllPrivateChats(),
        )
        await bot.set_my_commands(
            [
                BotCommand(command="profile", description="👑 Мой профиль"),
                BotCommand(command="top", description="⭐ Топ участников"),
                BotCommand(command="help", description="📖 Все команды"),
                BotCommand(command="messageschat", description="💬 Статистика сообщений"),
                BotCommand(command="date", description="💌 Свидание"),
                BotCommand(command="history", description="📖 Летопись пары"),
                BotCommand(command="wedding", description="💒 Свадьба"),
                BotCommand(command="destiny", description="🔮 Судьба пары"),
                BotCommand(command="contract", description="📜 Брачный контракт"),
            ],
            scope=BotCommandScopeAllGroupChats(),
        )
        await bot.set_my_description(
            "✨ L U M E N O R A ✨\n\n"
            "Премиальный опыт для твоего сообщества: экономика, роли, магазин, "
            "медали и живая модерация — всё в одном боте."
        )
        await bot.set_my_short_description(
            "✨ Lumenora — премиальный бот для сообществ Telegram"
        )
        print("✅ Премиальная витрина Telegram обновлена (команды, описание)")
    except Exception as _showcase_ex:
        logging.warning(f"premium showcase setup: {_showcase_ex}")

    # Цикл перезапуска polling — при любом сбое сети/API бот сам восстанавливається
    retry_delay = 5
    while True:
        try:
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                polling_timeout=30,
            )
            break  # нормальне завершення (stop_polling викликано)
        except asyncio.CancelledError:
            print("🛑 Polling скасовано")
            break
        except Exception as e:
            if _shutdown_event.is_set():
                break
            logging.error(f"💥 Polling упал: {e}. Перезапуск через {retry_delay}с...")
            save_data()
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)  # экспоненциальный backoff до 60с

def _apply_data(data: dict) -> None:
    """Заповнює in-memory сховища зі словника (з PostgreSQL або JSON-файлу)."""
    for cid, m in data.get("marriages", {}).items():
        marriages[int(cid)] = {int(u): int(v) for u, v in m.items()}
    global marriage_date_migration_version
    marriage_date_migration_version = int(
        data.get("marriage_date_migration_version", 0) or 0
    )
    for cid, users in data.get("streaks", {}).items():
        streaks[int(cid)] = {}
        for uid, d in users.items():
            streaks[int(cid)][int(uid)] = {
                "count": d.get("count", 0),
                "last": date.fromisoformat(d["last"]) if d.get("last") else None,
            }
    for u, b in data.get("lmn_balances", {}).items():
        try:
            lmn_balances[int(u)] = int(b)
        except (TypeError, ValueError):
            lmn_balances[int(u)] = 0
    global lmn_balance_reset_version, lmn_transfer_version, lmn_global_zero_version, founder_grant_version
    lmn_balance_reset_version = int(data.get("lmn_balance_reset_version", 0) or 0)
    lmn_transfer_version = int(data.get("lmn_transfer_version", 0) or 0)
    lmn_global_zero_version = int(data.get("lmn_global_zero_version", 0) or 0)
    founder_grant_version = int(data.get("founder_grant_version", 0) or 0)
    for cid, r in data.get("reputation", {}).items():
        reputation[int(cid)] = {int(u): v for u, v in r.items()}
    for u, v in data.get("profiles", {}).items():
        profiles[int(u)] = v
    for u, value in data.get("user_locations", {}).items():
        if isinstance(value, str) and value.strip():
            user_locations[int(u)] = value.strip()[:80]
    for u, value in data.get("known_users", {}).items():
        try:
            uid = int(u)
            if isinstance(value, dict):
                known_users[uid] = {
                    "full_name": str(value.get("full_name", "") or "")[:160],
                    "username": str(value.get("username", "") or "").lstrip("@")[:64],
                    "private_started": bool(value.get("private_started", False)),
                    "last_seen": str(value.get("last_seen", "") or "")[:40],
                }
        except (TypeError, ValueError):
            pass
    for qid, value in data.get("anon_questions", {}).items():
        try:
            if not isinstance(value, dict):
                continue
            anon_questions[str(qid)] = {
                "sender_id": int(value["sender_id"]),
                "target_id": int(value["target_id"]),
                "question": str(value.get("question", ""))[:1000],
                "status": str(value.get("status", "pending")),
                "answer": str(value.get("answer", ""))[:1000],
                "answers": [
                    {
                        "text": str(item.get("text", ""))[:1000],
                        "created_at": str(item.get("created_at", ""))[:40],
                    }
                    for item in (value.get("answers", []) or [])
                    if isinstance(item, dict)
                ],
                "created_at": str(value.get("created_at", ""))[:40],
                "answered_at": str(value.get("answered_at", ""))[:40],
            }
        except (KeyError, TypeError, ValueError):
            pass
    for u, qid in data.get("anon_answer_sessions", {}).items():
        try:
            if str(qid) in anon_questions:
                anon_answer_sessions[int(u)] = str(qid)
        except (TypeError, ValueError):
            pass
    for u, qid in data.get("anon_reply_sessions", {}).items():
        try:
            if str(qid) in anon_questions:
                anon_reply_sessions[int(u)] = str(qid)
        except (TypeError, ValueError):
            pass
    for u, target in data.get("anon_ask_sessions", {}).items():
        try:
            anon_ask_sessions[int(u)] = int(target)
        except (TypeError, ValueError):
            pass
    for u in data.get("help_sessions", []):
        try:
            help_sessions.add(int(u))
        except (TypeError, ValueError):
            pass
    for message_id, user_id in data.get("help_forward_map", {}).items():
        try:
            help_forward_map[int(message_id)] = int(user_id)
        except (TypeError, ValueError):
            pass
    for owner, items in data.get("shop_reservations", {}).items():
        if not isinstance(items, dict):
            continue
        clean_items: dict[str, int] = {}
        for item, quantity in items.items():
            try:
                amount = int(quantity)
            except (TypeError, ValueError):
                continue
            if amount > 0:
                clean_items[str(item)[:120]] = amount
        if clean_items:
            shop_reservations[str(owner)[:120]] = clean_items
    for poll_id, value in data.get("founder_polls", {}).items():
        if not isinstance(value, dict):
            continue
        try:
            founder_polls[str(poll_id)[:32]] = {
                "founder_id": int(value["founder_id"]),
                "chat_id": int(value["chat_id"]),
                "message_id": int(value.get("message_id", 0) or 0),
                "question": str(value.get("question", ""))[:300],
                "options": [str(option)[:100] for option in value.get("options", [])][:10],
                "created_at": str(value.get("created_at", ""))[:40],
            }
        except (KeyError, TypeError, ValueError):
            pass
    for uid, poll_id in data.get("poll_extra_sessions", {}).items():
        try:
            if str(poll_id) in founder_polls:
                poll_extra_sessions[int(uid)] = str(poll_id)
        except (TypeError, ValueError):
            pass
    for cid, w in data.get("warnings_db", {}).items():
        warnings_db[int(cid)] = {int(u): v for u, v in w.items()}
    for cid, w in data.get("ru_army_warns", {}).items():
        ru_army_warns[int(cid)] = {int(u): v for u, v in w.items()}
    for cid, r in data.get("chat_rules", {}).items():
        chat_rules[int(cid)] = r
    for cid, m in data.get("chat_members", {}).items():
        chat_members[int(cid)] = {int(u): n for u, n in m.items()}
    for u in data.get("premium_users", []):
        _premium_users.add(int(u))
    for u in data.get("verified_users", []):
        _verified_users.add(int(u))
    for u, v in data.get("aura", {}).items():
        aura[int(u)] = float(v)
    for u, r in data.get("roles", {}).items():
        ROLES[int(u)] = r
    for uname, r in data.get("role_usernames", {}).items():
        _ROLE_USERNAMES[uname] = r
    REVOKED_FOUNDER_ACCESS_IDS.update(
        int(uid) for uid in data.get("revoked_founder_access_ids", [])
    )
    for uid, note in data.get("founder_access_revocations", {}).items():
        try:
            if isinstance(note, dict):
                FOUNDER_ACCESS_REVOCATIONS[int(uid)] = {
                    "comment": str(note.get("comment", ""))[:1000],
                    "revoked_by": int(note.get("revoked_by", OWNER_ID)),
                    "revoked_at": str(note.get("revoked_at", ""))[:40],
                }
        except (TypeError, ValueError):
            pass
    _saved_pack = data.get("brand_emoji_pack", [])
    if _saved_pack:
        brand.set_pack(
            _saved_pack,
            data.get("brand_pack_name", ""),
            data.get("brand_emoji_map") or None,
        )
    global _last_rain_time
    _last_rain_time = data.get("last_rain_time", 0)
    for c, v in data.get("link_guard", {}).items():
        _link_guard[int(c)] = bool(v)
    for c, w in data.get("link_guard_warns", {}).items():
        _link_guard_warns[int(c)] = {int(u): v for u, v in w.items()}
    for c, wl in data.get("link_whitelist", {}).items():
        _link_whitelist[int(c)] = list(wl)
    for u, b in data.get("bank_balances", {}).items():
        bank_balances[int(u)] = int(b)
    for u, value in data.get("bank_term_deposits", {}).items():
        try:
            principal = int(value.get("principal", 0) or 0)
            started_at = _parse_bank_datetime(value.get("started_at"))
            if principal > 0 and started_at:
                bank_term_deposits[int(u)] = {
                    "principal": principal,
                    "started_at": started_at.isoformat(),
                }
        except (AttributeError, TypeError, ValueError):
            logging.warning("⚠️ Некорректный вклад для user=%s пропущен", u)
    for u, value in data.get("economy_progress", {}).items():
        try:
            if isinstance(value, dict):
                economy_progress[int(u)] = {
                    "date": str(value.get("date", ""))[:20],
                    "sources": [
                        str(source)[:30]
                        for source in (value.get("sources") or [])
                        if str(source).strip()
                    ][:12],
                }
        except (TypeError, ValueError):
            pass
    auction_manager.load_state(data.get("auction_state", {}))
    for u, value in data.get("bank_withdraw_cd", {}).items():
        try:
            _bwcd_dt = datetime.fromisoformat(value)
            # Нормализуем: naive → Kyiv, aware → приводим к Kyiv
            if _bwcd_dt.tzinfo is None:
                _bwcd_dt = _bwcd_dt.replace(tzinfo=KYIV_TZ)
            else:
                _bwcd_dt = _bwcd_dt.astimezone(KYIV_TZ)
            bank_withdraw_cd[int(u)] = _bwcd_dt
        except (TypeError, ValueError):
            logging.warning("⚠️ Некоректний cooldown банку для user=%s пропущено", u)
    for u, value in data.get("hunt_cooldown", {}).items():
        try:
            _dt = datetime.fromisoformat(value)
            hunt_cooldown[int(u)] = _dt if _dt.tzinfo else _dt.replace(tzinfo=KYIV_TZ)
        except (TypeError, ValueError):
            logging.warning("⚠️ Некоректний cooldown охоти для user=%s пропущено", u)
    for u, value in data.get("alchemy_cooldown", {}).items():
        try:
            _dt = datetime.fromisoformat(value)
            alchemy_cooldown[int(u)] = _dt if _dt.tzinfo else _dt.replace(tzinfo=KYIV_TZ)
        except (TypeError, ValueError):
            logging.warning("⚠️ Некоректний cooldown алхимии для user=%s пропущено", u)
    for cid, run in data.get("team_alchemy_runs", {}).items():
        try:
            team_alchemy_runs[int(cid)] = {
                "date": str(run.get("date", "")),
                "participants": {
                    int(uid): str(name)
                    for uid, name in run.get("participants", {}).items()
                },
                "completed": bool(run.get("completed", False)),
            }
        except (AttributeError, TypeError, ValueError):
            logging.warning("⚠️ Некорректный командный ритуал для chat=%s пропущен", cid)
    global _save_update_sent, _lumena_proposal_sent, _lumena_proposal_version
    _save_update_sent = bool(data.get("save_update_sent", False))
    _lumena_proposal_sent = bool(data.get("lumena_proposal_sent", False))
    _lumena_proposal_version = int(data.get("lumena_proposal_version", 0) or 0)
    global pending_notifications
    pending_notifications = list(data.get("pending_notifications", []))
    for _p in data.get("marriage_proposals", []):
        try:
            _key = (int(_p["chat_id"]), int(_p["target_id"]))
            marriage_proposals[_key] = {
                "proposer_id":  int(_p["proposer_id"]),
                "proposer_full": str(_p.get("proposer_full", "")),
            }
        except (KeyError, TypeError, ValueError):
            pass
    # V6
    global v6_announced
    v6_announced = bool(data.get("v6_announced", False))
    for u, v in data.get("user_xp", {}).items():
        user_xp[int(u)] = int(v)
    for c, m in data.get("user_messages", {}).items():
        user_messages[int(c)] = {int(u): int(cnt) for u, cnt in m.items()}
    for u, v in data.get("daily_cooldown", {}).items():
        daily_cooldown[int(u)] = str(v)
    for u, v in data.get("user_achievements", {}).items():
        user_achievements[int(u)] = list(v)
    for u, medals in data.get("founder_medals", {}).items():
        try:
            clean_medals = []
            for medal in medals[:50]:
                if not isinstance(medal, dict) or not str(medal.get("title", "")).strip():
                    continue
                clean_medals.append({
                    "title": str(medal.get("title", "")).strip()[:100],
                    "description": str(medal.get("description", "")).strip()[:300],
                    "issuer_id": int(medal.get("issuer_id", OWNER_ID)),
                    "chat_id": int(medal.get("chat_id", 0) or 0),
                    "created_at": str(medal.get("created_at", ""))[:40],
                })
            if clean_medals:
                founder_medals[int(u)] = clean_medals
        except (AttributeError, TypeError, ValueError):
            pass
    for c, v in data.get("mod_logs", {}).items():
        mod_logs[int(c)] = list(v)
    for c, users in data.get("soft_mutes", {}).items():
        try:
            clean = {
                int(uid): str(until)
                for uid, until in (users or {}).items()
                if str(until).strip()
            }
            if clean:
                soft_mutes[int(c)] = clean
        except (AttributeError, TypeError, ValueError):
            logging.warning("⚠️ Некорректный soft-mute для chat=%s пропущен", c)
    for c, users in data.get("admin_mute_snapshots", {}).items():
        try:
            clean = {
                int(uid): dict(snapshot)
                for uid, snapshot in (users or {}).items()
                if isinstance(snapshot, dict)
            }
            if clean:
                admin_mute_snapshots[int(c)] = clean
        except (AttributeError, TypeError, ValueError):
            logging.warning("⚠️ Некорректный снимок admin-mute для chat=%s пропущен", c)
    for c, v in data.get("reports_db", {}).items():
        reports_db[int(c)] = list(v)
    for c, pairs in data.get("staff_relations", {}).items():
        try:
            staff_relations[int(c)] = {
                str(pair): {
                    "messages": int(counter.get("messages", 0) or 0),
                    "bad": int(counter.get("bad", 0) or 0),
                    "last": str(counter.get("last", "") or ""),
                    "last_bad": str(counter.get("last_bad", "") or ""),
                    "last_bad_reason": str(counter.get("last_bad_reason", "") or ""),
                }
                for pair, counter in pairs.items()
                if isinstance(counter, dict)
            }
        except (AttributeError, TypeError, ValueError):
            logging.warning("⚠️ Некорректная статистика отношений команды для chat=%s", c)
    for c, targets in data.get("staff_ratings", {}).items():
        try:
            staff_ratings[int(c)] = {
                str(target): {
                    str(rater): {
                        "stars": max(1, min(5, int(rating.get("stars", 0) or 0))),
                        "ts": str(rating.get("ts", "") or ""),
                        "rater_name": str(rating.get("rater_name", "") or ""),
                    }
                    for rater, rating in raters.items()
                    if isinstance(rating, dict) and int(rating.get("stars", 0) or 0) in range(1, 6)
                }
                for target, raters in targets.items()
                if isinstance(raters, dict)
            }
        except (AttributeError, TypeError, ValueError):
            logging.warning("⚠️ Некорректные оценки команды для chat=%s", c)
    for c, users in data.get("staff_voice_stats", {}).items():
        try:
            staff_voice_stats[int(c)] = {
                str(uid): {
                    "received": int(stats.get("received", 0) or 0),
                    "analyzed": int(stats.get("analyzed", 0) or 0),
                    "failed": int(stats.get("failed", 0) or 0),
                }
                for uid, stats in users.items()
                if isinstance(stats, dict)
            }
        except (AttributeError, TypeError, ValueError):
            logging.warning("⚠️ Некорректная статистика voice для chat=%s", c)
    for c in data.get("staff_team_chats", []):
        try:
            staff_team_chats.add(int(c))
        except (TypeError, ValueError):
            pass
    for u, v in data.get("referrals", {}).items():
        referrals[int(u)] = int(v)
    for u, v in data.get("referral_counts", {}).items():
        referral_counts[int(u)] = int(v)
    for c, v in data.get("raid_mode", {}).items():
        raid_mode[int(c)] = bool(v)
    for c, v in data.get("antispam_mode", {}).items():
        antispam_mode[int(c)] = bool(v)
    for c, v in data.get("night_mode", {}).items():
        night_mode[int(c)] = bool(v)
    for u, v in data.get("games_played", {}).items():
        _games_played[int(u)] = int(v)
    for u, v in data.get("games_won", {}).items():
        _games_won[int(u)] = int(v)
    for u, v in data.get("bonus_weekly_cd", {}).items():
        bonus_weekly_cd[int(u)] = str(v)
    for u, v in data.get("daily_games", {}).items():
        daily_games[int(u)] = str(v)
    for u, v in data.get("daily_msg_cnt", {}).items():
        daily_msg_cnt[int(u)] = dict(v)
    for u, v in data.get("tasks_bonus_cd", {}).items():
        tasks_bonus_cd[int(u)] = str(v)
    for k, v in data.get("marriage_dates", {}).items():
        marriage_dates[str(k)] = str(v)
    for key, value in data.get("marriage_rpg_pairs", {}).items():
        if isinstance(value, dict):
            marriage_rpg_pairs[str(key)] = value
    for key, value in data.get("marriage_wedding_sessions", {}).items():
        if isinstance(value, dict):
            if value.get("status") == "pending" and _rpg_expire_wedding_session(str(key), value):
                continue
            marriage_wedding_sessions[str(key)] = value
    # кулдауны работы/рыбалки/ограбления (datetime → сохраняем ISO-строкой)
    _tz = ZoneInfo("Europe/Kyiv")
    for u, v in data.get("work_cooldown", {}).items():
        try:
            work_cooldown[int(u)] = datetime.fromisoformat(str(v)).replace(tzinfo=_tz)
        except Exception:
            pass
    for u, v in data.get("fish_cooldown", {}).items():
        try:
            fish_cooldown[int(u)] = datetime.fromisoformat(str(v)).replace(tzinfo=_tz)
        except Exception:
            pass
    for u, v in data.get("rob_cooldown", {}).items():
        try:
            rob_cooldown[int(u)] = datetime.fromisoformat(str(v)).replace(tzinfo=_tz)
        except Exception:
            pass
    for u, v in data.get("mine_cooldown", {}).items():
        try:
            mine_cooldown[int(u)] = datetime.fromisoformat(str(v)).replace(tzinfo=_tz)
        except Exception:
            pass
    for u, v in data.get("cook_cooldown", {}).items():
        try:
            cook_cooldown[int(u)] = datetime.fromisoformat(str(v)).replace(tzinfo=_tz)
        except Exception:
            pass
    for u, v in data.get("explore_cooldown", {}).items():
        try:
            explore_cooldown[int(u)] = datetime.fromisoformat(str(v)).replace(tzinfo=_tz)
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
