# -*- coding: utf-8 -*-
"""Главное меню, профиль, настройки."""

from telegram import Update
from telegram.ext import ContextTypes

import config
import storage
import config
from bot.utils.access import check_object_access
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
    friends_manage_kb,
    notify_new_kb,
    notify_new_positions_kb,
    notify_new_shifts_kb,
)

import json


def _loads_list(s: str | None) -> list:
    if not s:
        return []
    try:
        v = json.loads(s)
        return v if isinstance(v, list) else []
    except Exception:
        return []


async def back_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "back:main":
        return
    await query.answer()
    context.user_data.pop("pending_replacement", None)
    # Сбрасываем режимы ввода, чтобы не создавались тикеты/действия после выхода в меню.
    context.user_data.pop("waiting_support", None)
    context.user_data.pop("waiting_support_reply_tid", None)
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
    city, company, obj = user.get("city"), user.get("company"), user.get("object")
    verified = "—"
    if city and company and obj:
        ok, _ = await check_object_access(context.bot, uid, city, company, obj)
        verified = "✅ Подтверждён" if ok else "❌ Не подтверждён"
    trust = user.get("trust_score", 50)
    text = (
        f"👤 Профиль\n\n"
        f"Город: {user.get('city', '—')}\n"
        f"Компания: {user.get('company', '—')}\n"
        f"Объект: {user.get('object', '—')}\n"
        f"Статус: {verified}\n"
        f"Доверие: {trust}/100\n\n"
        f"🔄 Вас заменили: {was_replaced} раз\n"
        f"🔍 Вы заменили: {replaced} раз"
    )
    await query.edit_message_text(text, reply_markup=profile_kb())


async def menu_friends(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "menu:friends":
        return
    await query.answer()
    uid = query.from_user.id if query.from_user else 0
    friends = storage.get_friends(uid)
    if not friends:
        await query.edit_message_text(
            "У вас пока нет друзей.\n\nДобавить можно по Telegram ID (человек должен быть зарегистрирован и на том же объекте).",
            reply_markup=friends_manage_kb([]),
        )
        return
    await query.edit_message_text("Ваши друзья:", reply_markup=friends_manage_kb(friends))


async def friends_add_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "friends:add":
        return
    await query.answer()
    context.user_data["friends_add_waiting"] = True
    await query.edit_message_text(
        "Введите Telegram ID друга (число).\n\nВажно: друг должен быть зарегистрирован в боте и быть на том же объекте.",
    )


async def friends_add_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.user_data.pop("friends_add_waiting", None):
        return
    uid = update.effective_user.id if update.effective_user else 0
    raw = (update.message.text or "").strip()
    try:
        fid = int(raw)
    except ValueError:
        await update.message.reply_text("Нужно число (Telegram ID).", reply_markup=profile_kb())
        return
    if fid == uid:
        await update.message.reply_text("Нельзя добавить самого себя.", reply_markup=profile_kb())
        return
    owner = storage.get_user(uid) or {}
    friend = storage.get_user(fid) or {}
    if not friend.get("city") or not friend.get("company") or not friend.get("object"):
        await update.message.reply_text("Друг не зарегистрирован в боте.", reply_markup=profile_kb())
        return
    if (owner.get("city"), owner.get("company"), owner.get("object")) != (friend.get("city"), friend.get("company"), friend.get("object")):
        await update.message.reply_text("Друг должен быть на том же объекте.", reply_markup=profile_kb())
        return
    storage.add_friend(uid, fid)
    friends = storage.get_friends(uid)
    await update.message.reply_text("Друг добавлен.", reply_markup=friends_manage_kb(friends))


async def friends_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("friends:remove:"):
        return
    await query.answer()
    uid = query.from_user.id if query.from_user else 0
    try:
        fid = int(query.data.replace("friends:remove:", "", 1))
    except ValueError:
        return
    storage.remove_friend(uid, fid)
    friends = storage.get_friends(uid)
    await query.edit_message_text("Обновлено.", reply_markup=friends_manage_kb(friends))


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
        "Настройки:\n\n• Редактировать профиль — город, компания, объект.\n• Уведомления — дайджест по количеству замен в списке.",
        reply_markup=settings_kb(notify_enabled),
    )


async def settings_notify_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "settings:notify_new":
        return
    await query.answer()
    uid = query.from_user.id if query.from_user else 0
    user = storage.get_user(uid) or {}
    enabled = bool(user.get("notify_new_enabled", 0))
    await query.edit_message_text(
        "Уведомления о новых заменах.\n\nМожно включить и выбрать фильтры (позиции/смены).",
        reply_markup=notify_new_kb(enabled),
    )


async def notifynew_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "notifynew:toggle":
        return
    await query.answer()
    uid = query.from_user.id if query.from_user else 0
    user = storage.get_user(uid) or {}
    user["notify_new_enabled"] = not bool(user.get("notify_new_enabled", 0))
    storage.save_user(uid, user)
    enabled = bool(user.get("notify_new_enabled", 0))
    await query.edit_message_text("Обновлено.", reply_markup=notify_new_kb(enabled))


async def notifynew_positions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "notifynew:positions":
        return
    await query.answer()
    uid = query.from_user.id if query.from_user else 0
    user = storage.get_user(uid) or {}
    city, company, obj = user.get("city"), user.get("company"), user.get("object")
    positions = storage.get_positions(city, company, obj) if (city and company and obj) else []
    selected = set(_loads_list(user.get("notify_positions")))
    context.user_data["notify_positions_list"] = positions
    await query.edit_message_text("Выберите позиции (пусто = все):", reply_markup=notify_new_positions_kb(positions, selected))


async def notifypos_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("notifypos:"):
        return
    await query.answer()
    uid = query.from_user.id if query.from_user else 0
    user = storage.get_user(uid) or {}
    positions = context.user_data.get("notify_positions_list") or []
    selected = set(_loads_list(user.get("notify_positions")))
    if query.data == "notifypos:clear":
        user["notify_positions"] = json.dumps([])
        storage.save_user(uid, user)
        await query.edit_message_text("Позиции очищены (все позиции).", reply_markup=notify_new_positions_kb(positions, set()))
        return
    try:
        idx = int(query.data.replace("notifypos:toggle:", "", 1))
    except Exception:
        return
    if 0 <= idx < len(positions):
        p = positions[idx]
        if p in selected:
            selected.remove(p)
        else:
            selected.add(p)
        user["notify_positions"] = json.dumps(sorted(selected))
        storage.save_user(uid, user)
        await query.edit_message_text("Выберите позиции (пусто = все):", reply_markup=notify_new_positions_kb(positions, selected))


async def notifynew_shifts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "notifynew:shifts":
        return
    await query.answer()
    uid = query.from_user.id if query.from_user else 0
    user = storage.get_user(uid) or {}
    selected = set(_loads_list(user.get("notify_shift_keys")))
    await query.edit_message_text("Выберите смены (пусто = все):", reply_markup=notify_new_shifts_kb(selected))


async def notifyshift_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("notifyshift:"):
        return
    await query.answer()
    uid = query.from_user.id if query.from_user else 0
    user = storage.get_user(uid) or {}
    selected = set(_loads_list(user.get("notify_shift_keys")))
    if query.data == "notifyshift:clear":
        user["notify_shift_keys"] = json.dumps([])
        storage.save_user(uid, user)
        await query.edit_message_text("Смены очищены (все смены).", reply_markup=notify_new_shifts_kb(set()))
        return
    key = query.data.replace("notifyshift:toggle:", "", 1)
    if key in {"day", "night"}:
        if key in selected:
            selected.remove(key)
        else:
            selected.add(key)
        user["notify_shift_keys"] = json.dumps(sorted(selected))
        storage.save_user(uid, user)
        await query.edit_message_text("Выберите смены (пусто = все):", reply_markup=notify_new_shifts_kb(selected))


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
