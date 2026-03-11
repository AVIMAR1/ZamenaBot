# -*- coding: utf-8 -*-
"""Сценарий «Заменить»: список замен, заявка, принять/отклонить (автор), отказаться (принявший)."""

from telegram import Update
from datetime import timedelta
from telegram.ext import ContextTypes

import storage
from bot.utils.access import check_object_access
from keyboards import (
    replacements_list_kb,
    take_confirm_kb,
    creator_decide_kb,
    taker_wait_kb,
    replace_done_kb,
    notify_supervisor_kb,
    main_menu_kb,
    menu_quick_kb,
)


def _filter_for_user(replacements: list, uid: int) -> list:
    user = storage.get_user(uid) or {}
    city = user.get("city")
    company = user.get("company")
    obj = user.get("object")
    return [
        r for r in replacements
        if r.get("city") == city and r.get("company") == company and r.get("object") == obj
        and str(r.get("author_id")) != str(uid)
    ]


async def act_replace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "act:replace":
        return
    await query.answer()
    uid = query.from_user.id if query.from_user else 0
    user = storage.get_user(uid) or {}
    city = user.get("city", "")
    company = user.get("company", "")
    obj = user.get("object", "")
    if city and company and obj:
        ok, reason = await check_object_access(context.bot, uid, city, company, obj)
        if not ok:
            await query.edit_message_text(reason, reply_markup=main_menu_kb())
            return
    all_r = storage.get_replacements(active_only=True)
    replacements = _filter_for_user(all_r, uid)
    if not replacements:
        await query.edit_message_text(
            "Пока нет подходящих замен по вашему городу/компании/объекту.",
            reply_markup=main_menu_kb(),
        )
        return
    context.user_data["replace_list_page"] = 0
    await query.edit_message_text(
        "Доступные замены (выберите):",
        reply_markup=replacements_list_kb(replacements, page=0),
    )


async def replace_list_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("replist:"):
        return
    await query.answer()
    try:
        page = int(query.data.replace("replist:", "", 1))
    except ValueError:
        return
    uid = query.from_user.id if query.from_user else 0
    all_r = storage.get_replacements(active_only=True)
    replacements = _filter_for_user(all_r, uid)
    context.user_data["replace_list_page"] = page
    await query.edit_message_text(
        "Доступные замены:",
        reply_markup=replacements_list_kb(replacements, page=page),
    )


async def take_replacement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("take:"):
        return
    await query.answer()
    uid = query.from_user.id if query.from_user else 0
    user = storage.get_user(uid) or {}
    city = user.get("city", "")
    company = user.get("company", "")
    obj = user.get("object", "")
    if city and company and obj:
        ok, reason = await check_object_access(context.bot, uid, city, company, obj)
        if not ok:
            await query.answer(reason, show_alert=True)
            return
    rid = query.data.replace("take:", "", 1)
    r = storage.get_replacement_by_id(rid)
    if not r or r.get("confirmed") or not r.get("active"):
        await query.answer("Замена уже недоступна.", show_alert=True)
        return
    if r.get("requested_by_id"):
        await query.answer("На эту замену уже подали заявку.", show_alert=True)
        return
    uid = query.from_user.id if query.from_user else 0
    if str(r.get("author_id")) == str(uid):
        await query.answer("Нельзя принять своё объявление.", show_alert=True)
        return
    text = (
        f"📋 {r.get('position')} | {r.get('shift')}\n"
        f"Дата: {r.get('date_text')}\n"
        f"Объект: {r.get('object')}\n\n"
        f"Хотите заменить?"
    )
    context.user_data["take_rid"] = rid
    await query.edit_message_text(text, reply_markup=take_confirm_kb(rid))


async def confirm_take(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принявший нажимает — заявка отправляется автору."""
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("confirm_take:"):
        return
    await query.answer()
    rid = query.data.replace("confirm_take:", "", 1)
    r = storage.get_replacement_by_id(rid)
    if not r or r.get("confirmed"):
        await query.edit_message_text("Замена недоступна.", reply_markup=main_menu_kb())
        return
    uid = query.from_user.id if query.from_user else 0
    author_id = r.get("author_id")
    taker_username = query.from_user.username if query.from_user else ""

    r["requested_by_id"] = uid
    r["requested_by_username"] = taker_username
    storage.save_replacement(r)
    storage.sync_replacement_usernames(r)

    contact = f"@{taker_username}" if taker_username else f"ID: {uid}"
    msg_author = (
        f"📩 Заявка на замену от {contact}\n\n"
        f"Позиция: {r.get('position')}\n"
        f"Смена: {r.get('shift')}\n"
        f"Дата: {r.get('date_text')}\n"
        f"Объект: {r.get('object')}\n\n"
        f"Принять или отклонить?"
    )
    await query.edit_message_text(
        "Заявка отправлена. Ожидайте решения автора. Можно отозвать заявку.",
        reply_markup=taker_wait_kb(rid),
    )
    try:
        await context.bot.send_message(
            chat_id=author_id,
            text=msg_author,
            reply_markup=creator_decide_kb(rid),
        )
    except Exception:
        pass
    context.user_data.pop("take_rid", None)


async def creator_accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Автор принимает заявку."""
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("creator_accept:"):
        return
    await query.answer()
    rid = query.data.replace("creator_accept:", "", 1)
    r = storage.get_replacement_by_id(rid)
    if not r:
        await query.edit_message_text("Замена не найдена.", reply_markup=main_menu_kb())
        return
    uid = query.from_user.id if query.from_user else 0
    if str(r.get("author_id")) != str(uid):
        await query.answer("Только автор может принять.", show_alert=True)
        return
    taker_id = r.get("requested_by_id")
    if not taker_id:
        await query.answer("Заявка уже обработана.", show_alert=True)
        return
    author_id = r.get("author_id")
    author_username = r.get("author_username") or ""
    taker_username = r.get("requested_by_username") or ""

    r["confirmed"] = True
    r["taken_by_id"] = taker_id
    r["taken_by_username"] = taker_username
    r["requested_by_id"] = None
    r["requested_by_username"] = None
    storage.save_replacement(r)
    storage.sync_replacement_usernames(r)

    # Кого заменяют: автора объявления или друга.
    subject_id = r.get("for_friend_id") or author_id
    subject_user = storage.get_user(int(subject_id)) or {}
    # Данные пользователей (ФИО + куратор).
    author_user = storage.get_user(author_id) or {}
    taker_user = storage.get_user(taker_id) or {}
    subject_full = subject_user.get("full_name") or subject_user.get("name") or ""
    taker_full = taker_user.get("full_name") or taker_user.get("name") or ""
    subject_sup = storage.get_supervisor_by_id(subject_user.get("supervisor_id") or 0) or {}
    taker_sup = storage.get_supervisor_by_id(taker_user.get("supervisor_id") or 0) or {}
    subject_sup_name = subject_sup.get("title") or "—"
    taker_sup_name = taker_sup.get("title") or "—"

    contact_taker = f"@{taker_username}" if taker_username else f"ID: {taker_id}"
    contact_author = f"@{author_username}" if author_username else f"ID: {author_id}"
    base_info = (
        f"Позиция: {r.get('position')}\n"
        f"Смена: {r.get('shift')}\n"
        f"Дата: {r.get('date_text')}\n"
        f"Объект: {r.get('object')}\n"
    )
    msg_author = (
        f"✅ Замена согласована.\n\n"
        f"{base_info}\n"
        f"Заменяющий: {taker_full} ({contact_taker})\n"
        f"Куратор заменяющего: {taker_sup_name}\n\n"
        f"Свяжитесь с заменяющим: {contact_taker}\n"
        f"Можно предупредить своего администратора."
    )
    msg_taker = (
        f"✅ Автор принял вашу заявку.\n\n"
        f"{base_info}\n"
        f"Кого заменяете: {subject_full} ({contact_author})\n"
        f"Куратор: {subject_sup_name}\n\n"
        f"Свяжитесь с автором: {contact_author}\n"
        f"Ожидайте начала смены."
    )

    # У автора: вместо обычной кнопки — предложить предупредить администратора.
    await query.edit_message_text(msg_author, reply_markup=notify_supervisor_kb(rid))
    # Заменяющему — всегда.
    try:
        await context.bot.send_message(chat_id=taker_id, text=msg_taker, reply_markup=replace_done_kb(rid, is_creator=False))
    except Exception:
        pass
    # Кого заменяют (если это друг) — отправляем копию.
    if str(subject_id) != str(author_id):
        try:
            await context.bot.send_message(
                chat_id=subject_id,
                text=(
                    f"✅ Вам согласовали замену.\n\n"
                    f"{base_info}\n"
                    f"Заменяющий: {taker_full} ({contact_taker})\n"
                    f"Ожидайте начала смены."
                ),
                reply_markup=menu_quick_kb(),
            )
        except Exception:
            pass


async def notify_supervisor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Автор замены нажимает: предупредить своего администратора/куратора."""
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("notify_sup:"):
        return
    await query.answer()
    rid = query.data.replace("notify_sup:", "", 1)
    r = storage.get_replacement_by_id(rid)
    if not r or not r.get("confirmed"):
        await query.answer("Замена не найдена или не согласована.", show_alert=True)
        return
    if r.get("start_notified"):
        await query.answer("Смена уже началась, уведомление отправлять поздно.", show_alert=True)
        return
    uid = query.from_user.id if query.from_user else 0
    if str(r.get("author_id")) != str(uid):
        return
    author_user = storage.get_user(uid) or {}
    sup_id = author_user.get("supervisor_id")
    if not sup_id:
        await query.answer("У вас не выбран администратор.", show_alert=True)
        return
    sup = storage.get_supervisor_by_id(int(sup_id)) or {}
    sup_tid = sup.get("telegram_id")
    sup_username = (sup.get("username") or "").strip().lstrip("@")
    if not sup_username or not sup_tid:
        await query.answer("У администратора должны быть заданы @username и telegram_id.", show_alert=True)
        return
    # Проверяем, что @username актуален и соответствует telegram_id.
    # Если сменился — обновляем автоматически по telegram_id.
    try:
        chat = await context.bot.get_chat(f"@{sup_username}")
        if not chat or int(chat.id) != int(sup_tid):
            chat_by_id = await context.bot.get_chat(int(sup_tid))
            new_username = (getattr(chat_by_id, "username", None) or "").lstrip("@")
            if not new_username:
                await query.answer("У администратора нет @username. Нужен @username.", show_alert=True)
                return
            storage.update_supervisor_username(int(sup.get("id")), new_username)
            sup_username = new_username
    except Exception:
        try:
            chat_by_id = await context.bot.get_chat(int(sup_tid))
            new_username = (getattr(chat_by_id, "username", None) or "").lstrip("@")
            if new_username:
                storage.update_supervisor_username(int(sup.get("id")), new_username)
                sup_username = new_username
        except Exception:
            await query.answer("Не удалось проверить/обновить @username администратора.", show_alert=True)
            return
    taker_id = r.get("taken_by_id")
    taker_user = storage.get_user(taker_id) or {}
    taker_full = taker_user.get("full_name") or taker_user.get("name") or ""
    taker_username = r.get("taken_by_username") or ""
    taker_contact = f"@{taker_username}" if taker_username else f"ID: {taker_id}"
    # Когда: сегодня / завтра / дата
    from datetime import date as _date
    when = r.get("date_text") or ""
    try:
        d = _date.fromisoformat(r.get("date_from") or "")
        today = _date.today()
        if d == today:
            when = "сегодня"
        elif d == today + timedelta(days=1):
            when = "завтра"
        else:
            when = d.strftime("%d.%m.%Y")
    except Exception:
        pass
    msg = (
        f"Привет! Меня {when} заменит {taker_full} ({taker_contact}).\n\n"
        f"Позиция: {r.get('position')}\n"
        f"Смена: {r.get('shift')}\n"
        f"Объект: {r.get('object')}"
    )

    # 1) Отправляем пользователю текст для копирования
    try:
        await query.message.reply_text(msg)
    except Exception:
        await query.answer("Не удалось показать текст.", show_alert=True)
        return

    # 2) Отдельно — инструкция и кнопка перехода к администратору
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    url = f"https://t.me/{sup_username}"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Перейти к администратору", url=url)]])
    await query.message.reply_text(
        "Скопируйте сообщение выше и нажмите кнопку, чтобы открыть чат с администратором.",
        reply_markup=kb,
    )


async def creator_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Автор отклоняет заявку."""
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("creator_reject:"):
        return
    await query.answer()
    rid = query.data.replace("creator_reject:", "", 1)
    r = storage.get_replacement_by_id(rid)
    if not r:
        return
    uid = query.from_user.id if query.from_user else 0
    if str(r.get("author_id")) != str(uid):
        await query.answer("Только автор может отклонить.", show_alert=True)
        return
    taker_id = r.get("requested_by_id")
    r["requested_by_id"] = None
    r["requested_by_username"] = None
    storage.save_replacement(r)
    await query.edit_message_text(
        "Заявка отклонена. Замена остаётся в общем списке."
    )
    await query.message.reply_text("Главное меню:", reply_markup=main_menu_kb())
    try:
        await context.bot.send_message(chat_id=taker_id, text="Автор отклонил вашу заявку.")
    except Exception:
        pass


async def taker_refuse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принявший отказывается: отзывает заявку или отказывается от уже согласованной замены."""
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("taker_refuse:"):
        return
    await query.answer()
    rid = query.data.replace("taker_refuse:", "", 1)
    r = storage.get_replacement_by_id(rid)
    if not r:
        await query.edit_message_text("Замена не найдена.", reply_markup=main_menu_kb())
        return
    uid = query.from_user.id if query.from_user else 0
    taker_id = r.get("taken_by_id") or r.get("requested_by_id")
    if str(taker_id) != str(uid):
        await query.answer("Только принявший может отказаться.", show_alert=True)
        return
    if r.get("start_notified"):
        await query.answer("Смена уже началась, отказаться от замены нельзя.", show_alert=True)
        return
    author_id = r.get("author_id")
    r["confirmed"] = False
    r["taken_by_id"] = None
    r["taken_by_username"] = None
    r["requested_by_id"] = None
    r["requested_by_username"] = None
    storage.save_replacement(r)
    await query.edit_message_text("Вы отказались. Замена снова в списке.")
    await query.message.reply_text("Главное меню:", reply_markup=main_menu_kb())
    try:
        await context.bot.send_message(chat_id=author_id, text="Принявший отказался. Замена снова доступна.")
    except Exception:
        pass


async def undo_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Только автор отменяет подтверждение."""
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("undo_confirm:"):
        return
    await query.answer()
    rid = query.data.replace("undo_confirm:", "", 1)
    r = storage.get_replacement_by_id(rid)
    if not r or not r.get("confirmed"):
        await query.answer("Уже отменено или не найдено.", show_alert=True)
        return
    uid = query.from_user.id if query.from_user else 0
    if str(r.get("author_id")) != str(uid):
        await query.answer("Только автор может отменить подтверждение.", show_alert=True)
        return
    if r.get("start_notified"):
        await query.answer("Смена уже началась, отменить подтверждение нельзя.", show_alert=True)
        return
    r["confirmed"] = False
    r["taken_by_id"] = None
    r["taken_by_username"] = None
    storage.save_replacement(r)
    await query.edit_message_text("Подтверждение отменено, замена снова в списке.")
    await query.message.reply_text("Главное меню:", reply_markup=main_menu_kb())
    try:
        await context.bot.send_message(chat_id=taker_id, text="Автор отменил подтверждение. Замена снова в списке.")
    except Exception:
        pass
