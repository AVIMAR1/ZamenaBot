# -*- coding: utf-8 -*-
"""Сценарий «Заменить»: список замен, заявка, принять/отклонить (автор), отказаться (принявший)."""

from telegram import Update
from telegram.ext import ContextTypes

import storage
from keyboards import (
    replacements_list_kb,
    take_confirm_kb,
    creator_decide_kb,
    taker_wait_kb,
    replace_done_kb,
    main_menu_kb,
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

    author = storage.get_user(author_id) or {}
    author["was_replaced_count"] = author.get("was_replaced_count", 0) + 1
    storage.save_user(author_id, author)
    taker = storage.get_user(taker_id) or {}
    taker["replaced_count"] = taker.get("replaced_count", 0) + 1
    storage.save_user(taker_id, taker)

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
        f"Свяжитесь с заменяющим: {contact_taker}\n"
        f"Можно отменить подтверждение."
    )
    msg_taker = (
        f"✅ Автор принял вашу заявку.\n\n"
        f"{base_info}\n"
        f"Свяжитесь с автором: {contact_author}\n"
        f"Можно отказаться от замены."
    )

    await query.edit_message_text(msg_author, reply_markup=replace_done_kb(rid, is_creator=True))
    try:
        await context.bot.send_message(chat_id=taker_id, text=msg_taker, reply_markup=replace_done_kb(rid, is_creator=False))
    except Exception:
        pass


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
    author_id = r.get("author_id")
    if r.get("confirmed"):
        author = storage.get_user(author_id) or {}
        author["was_replaced_count"] = max(0, author.get("was_replaced_count", 0) - 1)
        storage.save_user(author_id, author)
        taker = storage.get_user(uid) or {}
        taker["replaced_count"] = max(0, taker.get("replaced_count", 0) - 1)
        storage.save_user(uid, taker)
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
    author_id = r.get("author_id")
    taker_id = r.get("taken_by_id")
    author = storage.get_user(author_id) or {}
    author["was_replaced_count"] = max(0, author.get("was_replaced_count", 0) - 1)
    storage.save_user(author_id, author)
    taker = storage.get_user(taker_id) or {}
    taker["replaced_count"] = max(0, taker.get("replaced_count", 0) - 1)
    storage.save_user(taker_id, taker)
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
