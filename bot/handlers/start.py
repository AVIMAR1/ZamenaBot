# -*- coding: utf-8 -*-
"""Старт и регистрация: город → компания → тип объекта → объект."""

from telegram import Update
from telegram.ext import ContextTypes

import config
import storage
from keyboards import (
    city_kb,
    company_kb,
    objects_kb,
    main_menu_kb,
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user is None:
        return
    user = update.effective_user
    uid = user.id
    storage.add_user_id(uid)

    existing = storage.get_user(uid)
    if existing and existing.get("city") and existing.get("company") and existing.get("object"):
        await update.message.reply_text(
            "Главное меню. Выберите действие:",
            reply_markup=main_menu_kb(),
        )
        return

    context.user_data.pop("pending_replacement", None)
    await update.message.reply_text(
        "Выберите город:",
        reply_markup=city_kb(),
    )


async def callback_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("city:"):
        return
    await query.answer()
    city = query.data.replace("city:", "", 1)
    uid = query.from_user.id if query.from_user else 0
    storage.add_user_id(uid)

    user = storage.get_user(uid) or {}
    user["city"] = city
    user["telegram_id"] = uid
    if query.from_user:
        user["username"] = query.from_user.username or ""
        user["name"] = (query.from_user.first_name or "") + " " + (query.from_user.last_name or "")
    storage.save_user(uid, user)

    await query.edit_message_text("Выберите компанию:", reply_markup=company_kb(city))


async def callback_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("company:"):
        return
    await query.answer()
    # company:Гродно:0
    parts = query.data.replace("company:", "", 1).split(":", 1)
    if len(parts) < 2:
        return
    city = parts[0]
    try:
        idx = int(parts[1])
    except ValueError:
        return
    companies = storage.get_companies(city)
    if idx < 0 or idx >= len(companies):
        return
    company = companies[idx]
    uid = query.from_user.id if query.from_user else 0
    user = storage.get_user(uid) or {}
    user["company"] = company
    storage.save_user(uid, user)
    await query.edit_message_text("Выберите объект:", reply_markup=objects_kb(city, company))


async def callback_object(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("obj:"):
        return
    await query.answer()
    # obj:Гродно:Wildberies:0
    parts = query.data.replace("obj:", "", 1).split(":")
    if len(parts) < 3:
        return
    city = parts[0]
    company = parts[1]
    try:
        idx = int(parts[2])
    except (ValueError, IndexError):
        return
    objects = storage.get_objects(city, company)
    if idx < 0 or idx >= len(objects):
        return
    obj = objects[idx]
    uid = query.from_user.id if query.from_user else 0
    user = storage.get_user(uid) or {}
    user["object"] = obj
    user.setdefault("replaced_count", 0)
    user.setdefault("was_replaced_count", 0)
    storage.save_user(uid, user)

    if context.user_data.pop("settings_flow", None):
        msg = "Профиль обновлён. Главное меню:"
    else:
        msg = "Профиль заполнен. Главное меню:"
    await query.edit_message_text(msg, reply_markup=main_menu_kb())
