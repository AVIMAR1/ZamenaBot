# -*- coding: utf-8 -*-
"""Сценарий «Найти замену»: смена, кем заменить, календарь, публикация."""

import uuid
from datetime import date, datetime, timedelta, time
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes

import storage
from keyboards import (
    shift_kb,
    positions_kb,
    calendar_month_kb,
    confirm_create_kb,
    main_menu_kb,
    friend_confirm_kb,
)


def _date_text(d: date) -> str:
    return d.strftime("%d.%m.%Y")


LOCAL_TZ = ZoneInfo("Europe/Minsk")


def _shift_already_started(city: str, company: str, obj: str, shift_key: str, d: date) -> bool:
    """Проверяет, началась ли уже смена для выбранной даты (по локальному времени)."""
    now = datetime.now(LOCAL_TZ)
    if d != now.date():
        return False
    shift_info = storage.get_object_shift(city, company, obj, shift_key)
    if shift_info and shift_info.get("start_time"):
        start_str = shift_info["start_time"]
    else:
        start_str = "09:00" if shift_key == "day" else "21:00"
    try:
        h, m = map(int, start_str.split(":", 1))
    except Exception:
        return False
    start_dt = datetime.combine(d, time(h, m, tzinfo=LOCAL_TZ))
    return now >= start_dt


async def _publish_from_pending(query, context: ContextTypes.DEFAULT_TYPE, rid: str, pending: dict):
    """Общая логика публикации объявления из pending_replacement."""
    uid = query.from_user.id if query.from_user else 0
    user = storage.get_user(uid) or {}
    replacement = {
        "id": rid,
        "author_id": uid,
        "author_username": user.get("username") or (query.from_user.username if query.from_user else ""),
        "city": user.get("city"),
        "company": user.get("company"),
        "object": user.get("object"),
        "shift": pending.get("shift"),
        "shift_key": pending.get("shift_key"),
        "position": pending.get("position"),
        "date_from": pending.get("date_from"),
        "date_to": pending.get("date_to"),
        "date_text": pending.get("date_text"),
        "active": True,
        "confirmed": False,
        "taken_by_id": None,
    }
    storage.save_replacement(replacement)
    context.user_data.pop("pending_replacement", None)
    await query.edit_message_text("Объявление опубликовано.")
    await query.message.reply_text("Главное меню:", reply_markup=main_menu_kb())


async def act_find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "act:find":
        return
    await query.answer()
    uid = query.from_user.id if query.from_user else 0
    user = storage.get_user(uid) or {}
    context.user_data["pending_replacement"] = {
        "author_id": uid,
        "city": user.get("city", ""),
        "company": user.get("company", ""),
        "object": user.get("object", ""),
    }
    await query.edit_message_text("Выберите смену:", reply_markup=shift_kb())


async def edit_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("editad:"):
        return
    await query.answer()
    rid = query.data.replace("editad:", "", 1)
    r = storage.get_replacement_by_id(rid)
    if not r:
        await query.answer("Объявление не найдено.", show_alert=True)
        return
    uid = query.from_user.id if query.from_user else 0
    if str(r.get("author_id")) != str(uid):
        return
    user = storage.get_user(uid) or {}
    city = user.get("city", "")
    company = user.get("company", "")
    obj = user.get("object", "")
    positions = storage.get_positions(city, company, obj)
    pos_idx = 0
    if r.get("position") in positions:
        pos_idx = positions.index(r["position"])
    pending = {
        "id": rid,
        "author_id": uid,
        "city": city,
        "shift": r.get("shift"),
        "shift_key": r.get("shift_key", "day" if r.get("shift") == "Дневная" else "night"),
        "position": r.get("position"),
        "pos_idx": pos_idx,
        "date_from": r.get("date_from"),
        "date_to": r.get("date_to"),
        "date_text": r.get("date_text"),
    }
    context.user_data["pending_replacement"] = pending
    await query.edit_message_text("Выберите смену:", reply_markup=shift_kb())


async def callback_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("shift:"):
        return
    await query.answer()
    shift_key = query.data.replace("shift:", "", 1)
    shift_name = "Дневная" if shift_key == "day" else "Ночная"
    pending = context.user_data.get("pending_replacement") or {}
    pending["shift_key"] = shift_key
    pending["shift"] = shift_name
    context.user_data["pending_replacement"] = pending
    city = pending.get("city", "")
    company = pending.get("company", "")
    obj = pending.get("object", "")
    await query.edit_message_text("Кем заменить?", reply_markup=positions_kb(city, company, obj))


async def callback_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("pos:"):
        return
    await query.answer()
    try:
        pos_idx = int(query.data.replace("pos:", "", 1))
    except ValueError:
        return
    pending = context.user_data.get("pending_replacement") or {}
    city = pending.get("city", "")
    company = pending.get("company", "")
    obj = pending.get("object", "")
    positions = storage.get_positions(city, company, obj)
    if pos_idx < 0 or pos_idx >= len(positions):
        await query.answer("Позиция не найдена.", show_alert=True)
        return
    position = positions[pos_idx]
    pending["position"] = position
    pending["pos_idx"] = pos_idx
    context.user_data["pending_replacement"] = pending
    single = 1 if pending.get("shift_key") == "day" else 0
    from datetime import datetime
    now = datetime.now()
    await query.edit_message_text(
        "Выберите дату:",
        reply_markup=calendar_month_kb(now.year, now.month, pending["shift_key"], pos_idx, single, step=0),
    )


async def callback_calendar_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("cal:"):
        return
    await query.answer()
    parts = query.data.replace("cal:", "", 1).split(":")
    if len(parts) < 6:
        return
    year, month = int(parts[0]), int(parts[1])
    shift_key, pos_idx = parts[2], int(parts[3])
    single, step = int(parts[4]), int(parts[5])
    await query.edit_message_text(
        "Выберите дату:",
        reply_markup=calendar_month_kb(year, month, shift_key, pos_idx, single, step),
    )


async def callback_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("date:"):
        return
    await query.answer()
    parts = query.data.replace("date:", "", 1).split(":")
    if len(parts) < 7:
        return
    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
    shift_key, pos_idx, single, step = parts[3], int(parts[4]), int(parts[5]), int(parts[6])
    pending = context.user_data.get("pending_replacement") or {}
    city = pending.get("city", "")
    company = pending.get("company", "")
    obj = pending.get("object", "")
    positions = storage.get_positions(city, company, obj)
    position = positions[pos_idx] if 0 <= pos_idx < len(positions) else pending.get("position", "")

    today = date.today()

    if single == 1:
        d = date(year, month, day)
        if d < today:
            await query.answer("Нельзя выбрать дату в прошлом.", show_alert=True)
            return
        if _shift_already_started(city, company, obj, shift_key, d):
            await query.answer("Нельзя искать замену на смену, которая уже началась.", show_alert=True)
            return
        pending["date_from"] = d.isoformat()
        pending["date_to"] = d.isoformat()
        pending["date_text"] = _date_text(d)
        pending["position"] = position
        context.user_data["pending_replacement"] = pending
        text = f"Проверьте:\nСмена: {pending.get('shift')}\nКем: {position}\nДата: {pending['date_text']}"
        rid = pending.get("id") or str(uuid.uuid4())[:8]
        pending["id"] = rid
        context.user_data["pending_replacement"] = pending
        is_edit = bool(storage.get_replacement_by_id(rid))
        await query.edit_message_text(text, reply_markup=confirm_create_kb(rid, is_edit=is_edit))
        return

    # Ночная смена: сначала выбираем дату начала, затем дату окончания (должна быть соседним днём).
    if step == 0:
        d_from = date(year, month, day)
        if d_from < today:
            await query.answer("Нельзя выбрать дату в прошлом.", show_alert=True)
            return
        if _shift_already_started(city, company, obj, shift_key, d_from):
            await query.answer("Нельзя искать замену на смену, которая уже началась.", show_alert=True)
            return
        pending["date_from"] = d_from.isoformat()
        pending["position"] = position
        context.user_data["pending_replacement"] = pending
        await query.edit_message_text(
            "Выберите дату окончания (ночная смена):",
            reply_markup=calendar_month_kb(year, month, shift_key, pos_idx, single, step=1),
        )
        return

    d_to = date(year, month, day)
    d_from = date.fromisoformat(pending.get("date_from", ""))
    if d_to < d_from:
        await query.answer("Дата окончания должна быть не раньше начала.", show_alert=True)
        return
    # Для ночной смены запрещаем не соседние дни (например, с 22 на 24).
    if (d_to - d_from).days != 1:
        await query.answer("Ночная смена должна заканчиваться на следующий день.", show_alert=True)
        return
    pending["date_to"] = d_to.isoformat()
    pending["date_text"] = f"{_date_text(d_from)} — {_date_text(d_to)}"
    context.user_data["pending_replacement"] = pending
    text = f"Проверьте:\nСмена: {pending.get('shift')}\nКем: {position}\nДаты: {pending['date_text']}"
    rid = pending.get("id") or str(uuid.uuid4())[:8]
    pending["id"] = rid
    context.user_data["pending_replacement"] = pending
    is_edit = bool(storage.get_replacement_by_id(rid))
    await query.edit_message_text(text, reply_markup=confirm_create_kb(rid, is_edit=is_edit))


async def callback_publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("publish:"):
        return
    await query.answer()
    rid = query.data.replace("publish:", "", 1)
    pending = context.user_data.get("pending_replacement")
    if not pending or pending.get("id") != rid:
        await query.edit_message_text("Сессия истекла. Создайте объявление заново.", reply_markup=main_menu_kb())
        return
    uid = query.from_user.id if query.from_user else 0

    # Если у пользователя уже есть активная замена на эту же дату и смену — спрашиваем, не для друга ли.
    if not pending.get("friend_confirmed"):
        my_active = storage.get_my_replacements(uid, active_only=True)
        for r0 in my_active:
            if (
                r0.get("id") != rid
                and r0.get("date_from") == pending.get("date_from")
                and r0.get("shift_key") == pending.get("shift_key")
            ):
                await query.edit_message_text(
                    "У вас уже есть объявление на эту дату.\n"
                    "Вы хотите найти замену для друга?",
                    reply_markup=friend_confirm_kb(rid),
                )
                return
    await _publish_from_pending(query, context, rid, pending)


async def friend_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("friend:"):
        return
    await query.answer()
    parts = query.data.split(":")
    if len(parts) < 3:
        return
    action = parts[1]
    rid = parts[2]
    pending = context.user_data.get("pending_replacement")
    if not pending or pending.get("id") != rid:
        await query.edit_message_text("Сессия истекла.", reply_markup=main_menu_kb())
        return
    if action == "no":
        context.user_data.pop("pending_replacement", None)
        await query.edit_message_text("Ок. Публикация отменена.", reply_markup=main_menu_kb())
        return
    if action == "yes":
        pending["friend_confirmed"] = True
        context.user_data["pending_replacement"] = pending
        await _publish_from_pending(query, context, rid, pending)


async def callback_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("update:"):
        return
    await query.answer()
    rid = query.data.replace("update:", "", 1)
    pending = context.user_data.get("pending_replacement")
    if not pending or pending.get("id") != rid:
        await query.edit_message_text("Сессия истекла.", reply_markup=main_menu_kb())
        return
    existing = storage.get_replacement_by_id(rid)
    if not existing:
        await query.edit_message_text("Объявление не найдено.", reply_markup=main_menu_kb())
        return
    uid = query.from_user.id if query.from_user else 0
    if str(existing.get("author_id")) != str(uid):
        return
    user = storage.get_user(uid) or {}
    replacement = {
        **existing,
        "shift": pending.get("shift"),
        "shift_key": pending.get("shift_key"),
        "position": pending.get("position"),
        "date_from": pending.get("date_from"),
        "date_to": pending.get("date_to"),
        "date_text": pending.get("date_text"),
    }
    storage.save_replacement(replacement)
    context.user_data.pop("pending_replacement", None)
    await query.edit_message_text("Объявление обновлено.")
    await query.message.reply_text("Главное меню:", reply_markup=main_menu_kb())
