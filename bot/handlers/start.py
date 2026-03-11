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
    supervisors_kb,
    back_to_main_kb,
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user is None:
        return
    user = update.effective_user
    uid = user.id
    storage.add_user_id(uid)

    existing = storage.get_user(uid)
    if (
        existing
        and existing.get("city")
        and existing.get("company")
        and existing.get("object")
        and existing.get("full_name")
        and existing.get("supervisor_id")
    ):
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

    # Если это настройки — возвращаем старый flow. Иначе запускаем продолжение регистрации:
    if context.user_data.pop("settings_flow", None):
        msg = "Профиль обновлён. Главное меню:"
        await query.edit_message_text(msg, reply_markup=main_menu_kb())
        return

    context.user_data["waiting_full_name"] = True
    await query.edit_message_text(
        "Регистрация почти завершена.\nВведите ваше ФИО (одним сообщением):",
        reply_markup=back_to_main_kb(),
    )


async def full_name_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение ФИО и выбор администратора/куратора."""
    if not update.message or not context.user_data.get("waiting_full_name"):
        return
    context.user_data.pop("waiting_full_name", None)
    uid = update.effective_user.id if update.effective_user else 0
    full_name = (update.message.text or "").strip()
    if len(full_name) < 5:
        context.user_data["waiting_full_name"] = True
        await update.message.reply_text("ФИО слишком короткое. Введите ещё раз:", reply_markup=back_to_main_kb())
        return
    user = storage.get_user(uid) or {}
    user["full_name"] = full_name
    # username/имя обновляем на всякий случай
    if update.effective_user:
        user["username"] = update.effective_user.username or ""
        user["name"] = (update.effective_user.first_name or "") + " " + (update.effective_user.last_name or "")
    storage.save_user(uid, user)

    supervisors = storage.get_supervisors()
    if not supervisors:
        # Если администраторы ещё не настроены — пусть админ добавит их.
        await update.message.reply_text(
            "Администраторы ещё не настроены. Обратитесь к администратору бота.",
            reply_markup=main_menu_kb(),
        )
        return
    await update.message.reply_text(
        "Выберите вашего администратора/куратора:",
        reply_markup=supervisors_kb(supervisors),
    )


async def choose_supervisor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("reg:supervisor:"):
        return
    await query.answer()
    uid = query.from_user.id if query.from_user else 0
    try:
        sid = int(query.data.replace("reg:supervisor:", "", 1))
    except ValueError:
        return
    sup = storage.get_supervisor_by_id(sid)
    if not sup:
        await query.answer("Администратор не найден.", show_alert=True)
        return
    user = storage.get_user(uid) or {}
    user["supervisor_id"] = sid
    # username обновляем на всякий случай
    if query.from_user:
        user["username"] = query.from_user.username or ""
        user["name"] = (query.from_user.first_name or "") + " " + (query.from_user.last_name or "")
    storage.save_user(uid, user)
    await query.edit_message_text("Регистрация завершена. Главное меню:", reply_markup=main_menu_kb())
