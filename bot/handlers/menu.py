# -*- coding: utf-8 -*-
"""Главное меню, профиль, настройки."""

from telegram import Update
from telegram.ext import ContextTypes

import config
import storage
import config
from keyboards import (
    main_menu_kb,
    city_kb,
    company_kb,
    objects_kb,
    profile_kb,
    admin_main_kb,
    my_ads_kb,
    my_ad_actions_kb,
    settings_kb,
    my_responses_kb,
    my_response_detail_kb,
)


async def back_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "back:main":
        return
    await query.answer()
    context.user_data.pop("pending_replacement", None)
    await query.edit_message_text("Главное меню:", reply_markup=main_menu_kb())


async def menu_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "menu:profile":
        return
    await query.answer()
    uid = query.from_user.id if query.from_user else 0
    user = storage.get_user(uid) or {}
    replaced = user.get("replaced_count", 0)
    was_replaced = user.get("was_replaced_count", 0)
    text = (
        f"👤 Профиль\n\n"
        f"Город: {user.get('city', '—')}\n"
        f"Компания: {user.get('company', '—')}\n"
        f"Объект: {user.get('object', '—')}\n\n"
        f"🔄 Вас заменили: {was_replaced} раз\n"
        f"🔍 Вы заменили: {replaced} раз"
    )
    await query.edit_message_text(text, reply_markup=profile_kb())


async def menu_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "menu:admin":
        return
    uid = query.from_user.id if query.from_user else 0
    if uid != config.ADMIN_TELEGRAM_ID:
        await query.answer("Нет доступа.", show_alert=True)
        return
    await query.answer()
    await query.edit_message_text("🔐 Админ-панель", reply_markup=admin_main_kb())


async def menu_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "menu:settings":
        return
    await query.answer()
    uid = query.from_user.id if query.from_user else 0
    user = storage.get_user(uid) or {}
    notify_enabled = bool(user.get("notify_digest", 1))
    await query.edit_message_text(
        "Настройки:\n\n• Редактировать профиль — город, компания, объект.\n• Уведомления — рассылка в 12:00 и 18:00 о количестве замен в списке.",
        reply_markup=settings_kb(notify_enabled),
    )


async def settings_edit_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "settings:edit_profile":
        return
    await query.answer()
    await query.edit_message_text("Выберите город:", reply_markup=city_kb())
    context.user_data["settings_flow"] = True


async def settings_toggle_notify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "settings:toggle_notify":
        return
    await query.answer()
    uid = query.from_user.id if query.from_user else 0
    user = storage.get_user(uid) or {}
    current = bool(user.get("notify_digest", 1))
    user["notify_digest"] = not current
    storage.save_user(uid, user)
    status = "включены" if user["notify_digest"] else "отключены"
    await query.edit_message_text(
        f"Уведомления о заменах {status}.",
        reply_markup=settings_kb(user["notify_digest"]),
    )


async def menu_my_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "menu:my_ads":
        return
    await query.answer()
    uid = query.from_user.id if query.from_user else 0
    ads = storage.get_my_replacements(uid, active_only=True)
    if not ads:
        await query.edit_message_text("У вас пока нет объявлений.", reply_markup=profile_kb())
        return
    context.user_data["my_ads_page"] = 0
    await query.edit_message_text(
        "Ваши объявления:",
        reply_markup=my_ads_kb(ads, page=0),
    )


async def menu_my_ads_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("myads:"):
        return
    await query.answer()
    try:
        page = int(query.data.replace("myads:", "", 1))
    except ValueError:
        return
    uid = query.from_user.id if query.from_user else 0
    ads = storage.get_my_replacements(uid, active_only=True)
    context.user_data["my_ads_page"] = page
    await query.edit_message_text(
        "Ваши объявления:",
        reply_markup=my_ads_kb(ads, page=page),
    )


async def my_ad_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("myad:"):
        return
    await query.answer()
    rid = query.data.replace("myad:", "", 1)
    r = storage.get_replacement_by_id(rid)
    if not r:
        await query.answer("Объявление не найдено.", show_alert=True)
        return
    uid = query.from_user.id if query.from_user else 0
    if str(r.get("author_id")) != str(uid):
        return
    status = "Активно" if r.get("active", True) and not r.get("confirmed") else ("Подтверждено" if r.get("confirmed") else "Снято")
    text = (
        f"📋 {r.get('shift', '')} | {r.get('position', '')}\n"
        f"Дата: {r.get('date_text', '')}\n"
        f"Статус: {status}"
    )
    await query.edit_message_text(
        text,
        reply_markup=my_ad_actions_kb(rid, active=r.get("active", True) and not r.get("confirmed")),
    )


async def deactivate_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("deactivate:"):
        return
    await query.answer()
    rid = query.data.replace("deactivate:", "", 1)
    r = storage.get_replacement_by_id(rid)
    if not r:
        return
    uid = query.from_user.id if query.from_user else 0
    if str(r.get("author_id")) != str(uid):
        return
    r["active"] = False
    storage.save_replacement(r)
    await query.edit_message_text("Объявление снято с публикации.")
    await query.message.reply_text("Главное меню:", reply_markup=main_menu_kb())


# --- Мои отклики ---


async def menu_my_responses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "menu:my_responses":
        return
    await query.answer()
    uid = query.from_user.id if query.from_user else 0
    responses = storage.get_my_responses(uid)
    if not responses:
        await query.edit_message_text(
            "У вас пока нет откликов на замены.",
            reply_markup=profile_kb(),
        )
        return
    context.user_data["my_responses_page"] = 0
    await query.edit_message_text(
        "Ваши отклики (⏳ ожидание, ✅ согласовано):",
        reply_markup=my_responses_kb(responses, page=0),
    )


async def my_responses_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("myrespp:"):
        return
    await query.answer()
    try:
        page = int(query.data.replace("myrespp:", "", 1))
    except ValueError:
        return
    uid = query.from_user.id if query.from_user else 0
    responses = storage.get_my_responses(uid)
    context.user_data["my_responses_page"] = page
    await query.edit_message_text(
        "Ваши отклики:",
        reply_markup=my_responses_kb(responses, page=page),
    )


async def my_response_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("myresp:"):
        return
    await query.answer()
    rid = query.data.replace("myresp:", "", 1)
    r = storage.get_replacement_by_id(rid)
    if not r:
        await query.answer("Замена не найдена.", show_alert=True)
        return
    uid = query.from_user.id if query.from_user else 0
    taker_id = r.get("requested_by_id") or r.get("taken_by_id")
    if str(taker_id) != str(uid):
        return
    status = "Согласовано" if r.get("confirmed") else "Ожидает решения автора"
    text = (
        f"📋 {r.get('position', '')} | {r.get('shift', '')}\n"
        f"Дата: {r.get('date_text', '')}\n"
        f"Объект: {r.get('object', '')}\n"
        f"Статус: {status}"
    )
    can_refuse = True  # можно отозвать заявку или отказаться от согласованной
    await query.edit_message_text(
        text,
        reply_markup=my_response_detail_kb(rid, can_refuse),
    )
