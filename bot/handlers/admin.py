# -*- coding: utf-8 -*-
"""Админ-панель: тикеты, ответы, закрытие, справочники."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

import config
import storage
from keyboards import (
    admin_main_kb,
    admin_tickets_kb,
    ticket_list_kb,
    ticket_actions_kb,
    admin_catalog_cities_kb,
    admin_catalog_city_menu_kb,
    admin_catalog_list_kb,
    admin_catalog_select_company_kb,
    admin_catalog_select_object_kb,
    admin_banned_kb,
    admin_shiftcfg_cities_kb,
    admin_shiftcfg_companies_kb,
    admin_shiftcfg_objects_kb,
    admin_shiftcfg_object_kb,
    admin_supervisors_kb,
    admin_reset_users_kb,
    admin_reset_users_confirm_kb,
    admin_users_nav_kb,
    admin_users_list_kb,
    admin_user_profile_kb,
    admin_unreg_confirm_kb,
    admin_userban_cancel_kb,
    admin_users_filter_cities_kb,
    admin_users_filter_companies_kb,
    admin_users_filter_objects_kb,
    objaccess_cities_kb,
    objaccess_companies_kb,
    objaccess_objects_kb,
    objaccess_object_kb,
    shiftreport_cities_kb,
    shiftreport_companies_kb,
    shiftreport_objects_kb,
    shiftreport_shift_kb,
    shiftreport_nav_kb,
    admin_calendar_kb,
    main_menu_kb,
    admin_reviews_list_kb,
    admin_review_detail_kb,
    admin_replacements_list_kb,
    admin_offers_list_kb,
    admin_replacement_detail_kb,
    admin_offer_detail_kb,
)

from bot.utils.access import check_object_access

from datetime import date

logger = logging.getLogger(__name__)


async def _answer_first(query, text=None):
    """Сразу снимает индикатор загрузки с кнопки."""
    try:
        await query.answer(text=text)
    except Exception as e:
        logger.warning("query.answer: %s", e)


def _is_admin(uid: int) -> bool:
    return uid == config.ADMIN_TELEGRAM_ID


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /admin — вход в админ-панель."""
    if not update.message or not update.effective_user:
        return
    chat = update.effective_chat
    # Админ-панель только в личных сообщениях, в группах не открываем.
    if chat and chat.type != "private":
        return
    uid = update.effective_user.id
    if not _is_admin(uid):
        await update.message.reply_text("Нет доступа к админ-панели.")
        return
    await update.message.reply_text("🔐 Админ-панель", reply_markup=admin_main_kb())


async def admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "admin:back":
        return
    await _answer_first(query)
    try:
        await query.edit_message_text("🔐 Админ-панель", reply_markup=admin_main_kb())
    except Exception as e:
        logger.warning("admin_back: %s", e)


async def admin_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "admin:tickets":
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        await query.answer("Нет доступа.", show_alert=True)
        return
    await query.answer()
    await query.edit_message_text("Тикеты:", reply_markup=admin_tickets_kb())


async def admin_tickets_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:tickets:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    closed = query.data == "admin:tickets:closed"
    tickets = storage.get_tickets(closed=closed)
    context.user_data["admin_tickets_closed"] = closed
    context.user_data["admin_ticket_page"] = 0
    label = "Закрытые" if closed else "Открытые"
    if not tickets:
        await query.edit_message_text(f"{label} тикеты пусты.", reply_markup=admin_tickets_kb())
        return
    await query.edit_message_text(
        f"{label} тикеты:",
        reply_markup=ticket_list_kb(tickets, page=0, prefix="admin:t"),
    )


async def admin_ticket_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:tlist:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    try:
        page = int(query.data.replace("admin:tlist:", "", 1))
    except ValueError:
        return
    closed = context.user_data.get("admin_tickets_closed", False)
    tickets = storage.get_tickets(closed=closed)
    context.user_data["admin_ticket_page"] = page
    label = "Закрытые" if closed else "Открытые"
    await query.edit_message_text(
        f"{label} тикеты:",
        reply_markup=ticket_list_kb(tickets, page=page, prefix="admin:t"),
    )


async def admin_ticket_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:t:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    tid = query.data.replace("admin:t:", "", 1)
    t = storage.get_ticket_by_id(tid)
    if not t:
        await query.answer("Тикет не найден.", show_alert=True)
        return
    lines = [f"Тикет #{tid} | Закрыт: {'да' if t.get('closed') else 'нет'}", f"User: {t.get('user_id')}"]
    for m in t.get("messages", []):
        who = "Пользователь" if m.get("from") == "user" else "Поддержка"
        lines.append(f"\n[{who}]: {m.get('text', '')}")
    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=ticket_actions_kb(tid) if not t.get("closed") else admin_tickets_kb(),
    )


async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:reply:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    tid = query.data.replace("admin:reply:", "", 1)
    context.user_data["admin_replying_tid"] = tid
    await query.edit_message_text(f"Напишите ответ на тикет #{tid}:")


async def admin_reply_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    tid = context.user_data.get("admin_replying_tid")
    if not tid:
        return
    context.user_data.pop("admin_replying_tid", None)
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Ответ не получен.")
        return
    t = storage.get_ticket_by_id(tid)
    if not t:
        await update.message.reply_text("Тикет не найден.", reply_markup=admin_main_kb())
        return
    t.setdefault("messages", []).append({"from": "support", "text": text})
    storage.save_ticket(t)
    await update.message.reply_text("Ответ отправлен.", reply_markup=admin_main_kb())
    # Пользователю — полная история переписки и кнопка «Ответить на тикет»
    history = []
    for m in t.get("messages", []):
        who = "Вы" if m.get("from") == "user" else "Поддержка"
        history.append(f"[{who}]: {m.get('text', '')}")
    from keyboards import support_reply_ticket_kb
    try:
        await update.get_bot().send_message(
            chat_id=t.get("user_id"),
            text=f"💬 Ответ по тикету #{tid}:\n\n" + "\n\n".join(history),
            reply_markup=support_reply_ticket_kb(tid),
        )
    except Exception:
        pass


async def admin_close_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:close:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    tid = query.data.replace("admin:close:", "", 1)
    t = storage.get_ticket_by_id(tid)
    if not t:
        return
    t["closed"] = True
    storage.save_ticket(t)
    await query.edit_message_text(f"Тикет #{tid} закрыт.", reply_markup=admin_tickets_kb())
    try:
        await context.bot.send_message(
            chat_id=t.get("user_id"),
            text=f"✅ Тикет #{tid} закрыт. Спасибо за обращение!",
        )
    except Exception:
        pass


async def admin_delete_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:del:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    tid = query.data.replace("admin:del:", "", 1)
    storage.delete_ticket(tid)
    await query.edit_message_text("Тикет удалён.", reply_markup=admin_tickets_kb())


async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "admin:users":
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        await query.answer("Нет доступа.", show_alert=True)
        return
    await query.answer()
    context.user_data["admin_users_page"] = 0
    f = context.user_data.get("admin_users_filter_obj") or {}
    users_all = list(storage.get_all_users().values())
    # Фильтр по объекту, если задан.
    city_f, company_f, obj_f = f.get("city"), f.get("company"), f.get("object")
    if city_f or company_f or obj_f:
        users_all = [
            u
            for u in users_all
            if (not city_f or u.get("city") == city_f)
            and (not company_f or u.get("company") == company_f)
            and (not obj_f or u.get("object") == obj_f)
        ]
    # Полностью зарегистрированные пользователи первыми.
    def _is_registered(u: dict) -> bool:
        return bool(u.get("city") and u.get("company") and u.get("object") and u.get("full_name") and u.get("supervisor_id"))

    users_all.sort(key=lambda u: (not _is_registered(u), u.get("telegram_id") or 0))
    total = len(users_all)
    registered_total = sum(1 for u in users_all if _is_registered(u))
    per_page = 10
    users_page = users_all[:per_page]
    await query.edit_message_text(
        f"Пользователей: {total} (полностью зарегистрированы: {registered_total})\nНажмите, чтобы забанить/разбанить:",
        reply_markup=admin_users_list_kb(users_page, 0, total, per_page=10),
    )


async def admin_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "admin:reviews":
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    total = storage.get_reviews_count()
    reviews = storage.get_reviews(order="recent", limit=1000, offset=0)
    context.user_data["admin_reviews_page"] = 0
    await query.edit_message_text(
        f"Отзывы: {total}",
        reply_markup=admin_reviews_list_kb(reviews, page=0, total=total, per_page=5),
    )


async def admin_reviews_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:reviewsp:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    try:
        page = int(query.data.replace("admin:reviewsp:", "", 1))
    except ValueError:
        return
    total = storage.get_reviews_count()
    reviews = storage.get_reviews(order="recent", limit=1000, offset=0)
    context.user_data["admin_reviews_page"] = page
    await query.edit_message_text(
        f"Отзывы: {total} (стр. {page+1})",
        reply_markup=admin_reviews_list_kb(reviews, page=page, total=total, per_page=5),
    )


async def admin_review_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:review:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    try:
        rid = int(query.data.replace("admin:review:", "", 1))
    except ValueError:
        return
    rev = storage.get_review_by_id(rid)
    if not rev:
        await query.answer("Отзыв не найден.", show_alert=True)
        return
    author = storage.get_user(int(rev.get("user_id") or 0)) or {}
    author_name = author.get("full_name") or author.get("name") or f"ID {rev.get('user_id')}"
    author_un = author.get("username") or rev.get("username") or ""
    contact = f"@{author_un}" if author_un else f"ID {rev.get('user_id')}"
    text = (
        "⭐ Отзыв о боте\n\n"
        f"ID отзыва: {rid}\n"
        f"Автор: {author_name} ({contact})\n"
        f"Оценка: {rev.get('rating')}★\n"
        f"Дата: {rev.get('created_at')}\n\n"
        f"{rev.get('text') or ''}"
    )
    await query.edit_message_text(text, reply_markup=admin_review_detail_kb(rid))


async def admin_review_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:reviewdel:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    try:
        rid = int(query.data.replace("admin:reviewdel:", "", 1))
    except ValueError:
        return
    storage.delete_review(rid)
    await query.edit_message_text("Отзыв удалён.", reply_markup=admin_main_kb())


async def admin_users_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:usersp:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    try:
        page = int(query.data.replace("admin:usersp:", "", 1))
    except ValueError:
        return
    context.user_data["admin_users_page"] = page
    f = context.user_data.get("admin_users_filter_obj") or {}
    users_all = list(storage.get_all_users().values())
    city_f, company_f, obj_f = f.get("city"), f.get("company"), f.get("object")
    if city_f or company_f or obj_f:
        users_all = [
            u
            for u in users_all
            if (not city_f or u.get("city") == city_f)
            and (not company_f or u.get("company") == company_f)
            and (not obj_f or u.get("object") == obj_f)
        ]
    def _is_registered(u: dict) -> bool:
        return bool(u.get("city") and u.get("company") and u.get("object") and u.get("full_name") and u.get("supervisor_id"))

    users_all.sort(key=lambda u: (not _is_registered(u), u.get("telegram_id") or 0))
    total = len(users_all)
    registered_total = sum(1 for u in users_all if _is_registered(u))
    per_page = 10
    start = page * per_page
    users_page = users_all[start : start + per_page]
    await query.edit_message_text(
        f"Пользователей: {total} (стр. {page+1}, полностью зарегистрированы: {registered_total})\nНажмите, чтобы забанить/разбанить:",
        reply_markup=admin_users_list_kb(users_page, page, total, per_page=10),
    )


async def admin_users_filterobj(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "admin:users:filterobj":
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    await query.edit_message_text("Фильтр участников: выберите город.", reply_markup=admin_users_filter_cities_kb())


async def usersobj_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("usersobj:city:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    city_idx = int(query.data.replace("usersobj:city:", "", 1))
    await query.edit_message_text("Выберите компанию.", reply_markup=admin_users_filter_companies_kb(city_idx))


async def usersobj_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("usersobj:company:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    parts = query.data.replace("usersobj:company:", "", 1).split(":")
    city_idx, company_idx = int(parts[0]), int(parts[1])
    await query.edit_message_text("Выберите объект.", reply_markup=admin_users_filter_objects_kb(city_idx, company_idx))


async def usersobj_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("usersobj:set:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    parts = query.data.replace("usersobj:set:", "", 1).split(":")
    city_idx, company_idx, object_idx = int(parts[0]), int(parts[1]), int(parts[2])
    cities = storage.get_cities()
    city = cities[city_idx]
    company = storage.get_companies(city)[company_idx]
    obj = storage.get_objects(city, company)[object_idx]
    context.user_data["admin_users_filter_obj"] = {"city": city, "company": company, "object": obj}
    # Переоткрываем список, с сортировкой зарегистрированные->незарегистрированные.
    users_all = list(storage.get_all_users().values())
    users_all = [u for u in users_all if (u.get("city"), u.get("company"), u.get("object")) == (city, company, obj)]
    def _is_registered(u: dict) -> bool:
        return bool(u.get("city") and u.get("company") and u.get("object") and u.get("full_name") and u.get("supervisor_id"))

    users_all.sort(key=lambda u: (not _is_registered(u), u.get("telegram_id") or 0))
    total = len(users_all)
    registered_total = sum(1 for u in users_all if _is_registered(u))
    per_page = 10
    users_page = users_all[:per_page]
    await query.edit_message_text(
        f"Фильтр: {obj}\nПользователей: {total} (полностью зарегистрированы: {registered_total})\nНажмите, чтобы забанить/разбанить:",
        reply_markup=admin_users_list_kb(users_page, 0, total, per_page=10),
    )


async def usersobj_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "usersobj:reset":
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    context.user_data.pop("admin_users_filter_obj", None)
    users_all = list(storage.get_all_users().values())
    def _is_registered(u: dict) -> bool:
        return bool(u.get("city") and u.get("company") and u.get("object") and u.get("full_name") and u.get("supervisor_id"))

    users_all.sort(key=lambda u: (not _is_registered(u), u.get("telegram_id") or 0))
    total = len(users_all)
    registered_total = sum(1 for u in users_all if _is_registered(u))
    per_page = 10
    users_page = users_all[:per_page]
    await query.edit_message_text(
        f"Фильтр сброшен.\nПользователей: {total} (полностью зарегистрированы: {registered_total})\nНажмите, чтобы забанить/разбанить:",
        reply_markup=admin_users_list_kb(users_page, 0, total, per_page=10),
    )


async def admin_userban_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Нажатие 'забанить' на пользователе: просим срок."""
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:userban:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    try:
        target_id = int(query.data.replace("admin:userban:", "", 1))
    except ValueError:
        return
    context.user_data["admin_userban_target"] = target_id
    await query.edit_message_text(
        "Введите срок бана для пользователя (в днях) или 'forever'.\n"
        "Пример: 7  или  forever",
        reply_markup=admin_userban_cancel_kb(),
    )


async def admin_userban_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "admin:userban_cancel":
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    context.user_data.pop("admin_userban_target", None)
    users_all = list(storage.get_all_users().values())
    def _is_registered(u: dict) -> bool:
        return bool(u.get("city") and u.get("company") and u.get("object") and u.get("full_name") and u.get("supervisor_id"))

    users_all.sort(key=lambda u: (not _is_registered(u), u.get("telegram_id") or 0))
    total = len(users_all)
    registered_total = sum(1 for u in users_all if _is_registered(u))
    per_page = 10
    users_page = users_all[:per_page]
    await query.edit_message_text(
        f"Отменено.\nПользователей: {total} (полностью зарегистрированы: {registered_total})\nНажмите, чтобы забанить/разбанить:",
        reply_markup=admin_users_list_kb(users_page, 0, total, per_page=10),
    )


async def admin_userprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:userprofile:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    try:
        target_id = int(query.data.replace("admin:userprofile:", "", 1))
    except ValueError:
        return
    u = storage.get_user(target_id) or {"telegram_id": target_id}
    city, company, obj = u.get("city"), u.get("company"), u.get("object")
    verified = "—"
    if city and company and obj:
        ok, _ = await check_object_access(context.bot, target_id, city, company, obj)
        verified = "✅ Подтверждён" if ok else "❌ Не подтверждён"
    sup = storage.get_supervisor_by_id(u.get("supervisor_id") or 0) or {}
    admin_name = sup.get("title") or "—"
    trust = u.get("trust_score", 50)
    uname = u.get("username") or ""
    username_line = f"@username: @{uname}" if uname else "@username: —"
    text = (
        "👤 Пользователь\n\n"
        f"ID: {target_id}\n"
        f"ФИО: {u.get('full_name') or '—'}\n"
        f"{username_line}"
    )
    text += (
        f"\nГород: {city or '—'}\n"
        f"Компания: {company or '—'}\n"
        f"Объект: {obj or '—'}\n"
        f"Администратор: {admin_name}\n"
        f"Статус: {verified}\n"
        f"Доверие: {trust}/100\n"
        f"Бан: {u.get('banned_until') or '—'}"
    )
    await query.edit_message_text(text, reply_markup=admin_user_profile_kb(target_id))


async def admin_unreg_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:unreg:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    target_id = int(query.data.replace("admin:unreg:", "", 1))
    await query.edit_message_text(
        "Снять регистрацию с пользователя?\n"
        "Он будет вынужден пройти /start заново.",
        reply_markup=admin_unreg_confirm_kb(target_id),
    )


async def admin_unreg_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:unreg_"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    parts = query.data.split(":")
    action = parts[0]  # admin:unreg_yes or admin:unreg_no
    target_id = int(parts[1]) if len(parts) > 1 else 0
    if action == "admin:unreg_no":
        await query.edit_message_text("Отменено.", reply_markup=admin_main_kb())
        return
    if target_id:
        storage.reset_user_registration(int(target_id))
        await query.edit_message_text("Регистрация снята.", reply_markup=admin_main_kb())


async def admin_warn_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:warn:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    target_id = int(query.data.replace("admin:warn:", "", 1))
    context.user_data["admin_warn_target"] = target_id
    await query.edit_message_text("Введите текст предупреждения пользователю (одним сообщением):")


async def admin_msg_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:msg:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    target_id = int(query.data.replace("admin:msg:", "", 1))
    context.user_data["admin_msg_target"] = target_id
    await query.edit_message_text("Введите сообщение пользователю (одним сообщением):")


async def admin_warn_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    target_id = context.user_data.pop("admin_warn_target", None)
    if not target_id:
        return
    uid = update.effective_user.id if update.effective_user else 0
    if not _is_admin(uid):
        return
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Пустое предупреждение. Отмена.", reply_markup=admin_main_kb())
        return
    try:
        await context.bot.send_message(chat_id=int(target_id), text=f"⚠ Предупреждение от администратора:\n\n{text}")
    except Exception:
        pass
    await update.message.reply_text("Отправлено.", reply_markup=admin_main_kb())


async def admin_msg_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    target_id = context.user_data.pop("admin_msg_target", None)
    if not target_id:
        return
    uid = update.effective_user.id if update.effective_user else 0
    if not _is_admin(uid):
        return
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Пустое сообщение. Отмена.", reply_markup=admin_main_kb())
        return
    try:
        await context.bot.send_message(chat_id=int(target_id), text=text)
    except Exception:
        pass
    await update.message.reply_text("Отправлено.", reply_markup=admin_main_kb())


async def admin_trust_set_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    target_id = context.user_data.pop("admin_trust_set_target", None)
    if not target_id:
        return
    uid = update.effective_user.id if update.effective_user else 0
    if not _is_admin(uid):
        return
    raw = (update.message.text or "").strip().replace(",", ".")
    try:
        val = float(raw)
    except Exception:
        await update.message.reply_text("Нужно число 0..100.", reply_markup=admin_main_kb())
        return
    val = max(0.0, min(100.0, val))
    u = storage.get_user(int(target_id)) or {"telegram_id": int(target_id)}
    u["trust_score"] = val
    storage.save_user(int(target_id), u)
    await update.message.reply_text(f"Доверие обновлено: {val}/100.", reply_markup=admin_main_kb())


async def admin_trust_adjust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:trust:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    parts = query.data.split(":")
    # admin:trust:+5:uid | admin:trust:set:uid
    if len(parts) < 4:
        return
    action = parts[2]
    target_id = int(parts[3])
    u = storage.get_user(target_id) or {"telegram_id": target_id}
    if action == "set":
        context.user_data["admin_trust_set_target"] = target_id
        await query.edit_message_text("Введите новое значение доверия (0..100):")
        return
    try:
        delta = float(action)
    except Exception:
        return
    trust = float(u.get("trust_score", 50) or 50)
    trust = max(0.0, min(100.0, trust + delta))
    u["trust_score"] = trust
    storage.save_user(target_id, u)
    await query.answer("Обновлено")
    # вернём в профиль
    fake = update
    fake.callback_query.data = f"admin:userprofile:{target_id}"
    await admin_userprofile(fake, context)


async def admin_userban_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    target = context.user_data.get("admin_userban_target")
    if not target:
        return
    context.user_data.pop("admin_userban_target", None)
    uid = update.effective_user.id if update.effective_user else 0
    if not _is_admin(uid):
        return
    raw = (update.message.text or "").strip().lower()
    from datetime import date, timedelta
    if raw == "forever":
        until = "forever"
    else:
        try:
            days = int(raw)
            until = (date.today() + timedelta(days=days)).isoformat()
        except ValueError:
            await update.message.reply_text("Нужно число дней или 'forever'.", reply_markup=admin_main_kb())
            return
    user = storage.get_user(target) or {"telegram_id": target}
    user["banned_until"] = until
    storage.save_user(target, user)
    await update.message.reply_text(f"Пользователь {target} забанен до {until}.", reply_markup=admin_main_kb())


async def admin_replacement_remove_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приём причины снятия замены с публикации."""
    if not update.message:
        return
    rid = context.user_data.pop("admin_repl_remove_id", None)
    if not rid:
        return
    uid = update.effective_user.id if update.effective_user else 0
    if not _is_admin(uid):
        return
    reason = (update.message.text or "").strip()
    r = storage.get_replacement_by_id(rid)
    if not r:
        await update.message.reply_text("Замена не найдена.", reply_markup=admin_main_kb())
        return
    author_id = r.get("author_id")
    r["active"] = False
    r["requested_by_id"] = None
    r["requested_by_username"] = None
    r["taken_by_id"] = None
    r["taken_by_username"] = None
    r["confirmed"] = False
    storage.save_replacement(r)
    if author_id:
        try:
            text = "Ваша замена снята администратором."
            if reason:
                text += f"\nПричина: {reason}"
            await update.get_bot().send_message(chat_id=author_id, text=text)
        except Exception:
            pass
    await update.message.reply_text("Замена снята с публикации.", reply_markup=admin_main_kb())


async def admin_offer_remove_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приём причины снятия предложения с публикации."""
    if not update.message:
        return
    oid = context.user_data.pop("admin_offer_remove_id", None)
    if not oid:
        return
    uid = update.effective_user.id if update.effective_user else 0
    if not _is_admin(uid):
        return
    reason = (update.message.text or "").strip()
    o = storage.get_offer_by_id(oid)
    if not o:
        await update.message.reply_text("Предложение не найдено.", reply_markup=admin_main_kb())
        return
    author_id = o.get("author_id")
    storage.deactivate_offer(oid)
    if author_id:
        try:
            text = "Ваше предложение выйти на замену снято администратором."
            if reason:
                text += f"\nПричина: {reason}"
            await update.get_bot().send_message(chat_id=author_id, text=text)
        except Exception:
            pass
    await update.message.reply_text("Предложение снято с публикации.", reply_markup=admin_main_kb())


async def admin_userunban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:userunban:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    try:
        target_id = int(query.data.replace("admin:userunban:", "", 1))
    except ValueError:
        return
    user = storage.get_user(target_id) or {"telegram_id": target_id}
    user["banned_until"] = None
    storage.save_user(target_id, user)
    await query.edit_message_text("Разбанено. Откройте список пользователей заново.", reply_markup=admin_main_kb())


async def admin_supervisors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "admin:supervisors":
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    sups = storage.get_supervisors()
    await query.edit_message_text(
        f"Администраторы: {len(sups)}",
        reply_markup=admin_supervisors_kb(sups),
    )


async def admin_supervisor_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "admin:supervisoradd":
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    context.user_data["admin_supervisor_add_waiting"] = True
    await query.edit_message_text(
        "Введите администратора в формате:\n"
        "Название | @username | telegram_id\n"
        "Пример: Иванов И.И. | @boss_admin | 123456789\n"
        "Важно: @username проверяется по telegram_id (должны совпадать).\n"
        "Для отмены введите слово Отмена.",
    )


async def admin_supervisor_add_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.user_data.pop("admin_supervisor_add_waiting", None):
        return
    uid = update.effective_user.id if update.effective_user else 0
    if not _is_admin(uid):
        return
    raw = (update.message.text or "").strip()
    if raw.lower() in {"отмена", "cancel"}:
        await update.message.reply_text("Добавление администратора отменено.", reply_markup=admin_main_kb())
        return
    parts = [p.strip() for p in raw.split("|")]
    title = parts[0] if parts else ""
    username = None
    tid = None
    if len(parts) >= 2 and parts[1]:
        username = parts[1].lstrip("@")
    if len(parts) >= 3 and parts[2]:
        try:
            tid = int(parts[2])
        except ValueError:
            tid = None
    if not title:
        await update.message.reply_text("Пустое название.", reply_markup=admin_main_kb())
        return
    if not username or not tid:
        await update.message.reply_text("Нужно указать и @username, и telegram_id.", reply_markup=admin_main_kb())
        return
    # Проверяем, что username действительно принадлежит этому telegram_id.
    # Идём к Telegram по ID (надёжнее), а username сверяем из ответа.
    try:
        chat = await context.bot.get_chat(tid)
        real_username = (chat.username or "").lstrip("@")
        if real_username.lower() != username.lower():
            await update.message.reply_text(
                "Проверка не пройдена: @username не соответствует telegram_id.\n"
                "Проверьте данные и попробуйте снова.",
                reply_markup=admin_main_kb(),
            )
            return
    except Exception:
        await update.message.reply_text(
            "Не удалось проверить @username (возможно, неверный telegram_id или ограничения Telegram).",
            reply_markup=admin_main_kb(),
        )
        return
    storage.add_supervisor(title, username=username, telegram_id=tid)
    sups = storage.get_supervisors()
    await update.message.reply_text("Администратор добавлен.", reply_markup=admin_supervisors_kb(sups))


async def admin_supervisor_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:supervisordel:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    try:
        sid = int(query.data.replace("admin:supervisordel:", "", 1))
    except ValueError:
        return
    storage.delete_supervisor(sid)
    sups = storage.get_supervisors()
    await query.edit_message_text("Обновлено.", reply_markup=admin_supervisors_kb(sups))


async def admin_supervisor_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования администратора."""
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:supervisoredit:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    try:
        sid = int(query.data.replace("admin:supervisoredit:", "", 1))
    except ValueError:
        return
    sup = storage.get_supervisor_by_id(sid)
    if not sup:
        await query.answer("Администратор не найден.", show_alert=True)
        return
    context.user_data["admin_supervisor_edit_id"] = sid
    username = sup.get("username") or ""
    tid = sup.get("telegram_id") or ""
    await query.edit_message_text(
        "Редактирование администратора.\n"
        "Текущие данные:\n"
        f"Название: {sup.get('title') or '—'}\n"
        f"@username: @{username or '—'}\n"
        f"telegram_id: {tid or '—'}\n\n"
        "Введите НОВЫЕ данные в формате:\n"
        "Название | @username | telegram_id\n"
        "Или введите Отмена для выхода.",
    )


async def admin_supervisor_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приём новых данных администратора."""
    if not update.message:
        return
    sid = context.user_data.pop("admin_supervisor_edit_id", None)
    if not sid:
        return
    uid = update.effective_user.id if update.effective_user else 0
    if not _is_admin(uid):
        return
    raw = (update.message.text or "").strip()
    if raw.lower() in {"отмена", "cancel"}:
        sups = storage.get_supervisors()
        await update.message.reply_text("Редактирование отменено.", reply_markup=admin_supervisors_kb(sups))
        return
    parts = [p.strip() for p in raw.split("|")]
    title = parts[0] if parts else ""
    username = None
    tid = None
    if len(parts) >= 2 and parts[1]:
        username = parts[1].lstrip("@")
    if len(parts) >= 3 and parts[2]:
        try:
            tid = int(parts[2])
        except ValueError:
            tid = None
    if not title:
        sups = storage.get_supervisors()
        await update.message.reply_text("Пустое название. Изменения не сохранены.", reply_markup=admin_supervisors_kb(sups))
        return
    # Если указаны и username, и tid — проверяем соответствие так же, как при добавлении.
    if username and tid:
        try:
            chat = await context.bot.get_chat(tid)
            real_username = (chat.username or "").lstrip("@")
            if real_username.lower() != username.lower():
                sups = storage.get_supervisors()
                await update.message.reply_text(
                    "Проверка не пройдена: @username не соответствует telegram_id.\n"
                    "Проверьте данные и попробуйте снова.",
                    reply_markup=admin_supervisors_kb(sups),
                )
                return
        except Exception:
            sups = storage.get_supervisors()
            await update.message.reply_text(
                "Не удалось проверить @username (возможно, неверный telegram_id или ограничения Telegram).",
                reply_markup=admin_supervisors_kb(sups),
            )
            return
    storage.update_supervisor(int(sid), title, username, tid)
    sups = storage.get_supervisors()
    await update.message.reply_text("Администратор обновлён.", reply_markup=admin_supervisors_kb(sups))


async def admin_reset_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "admin:resetusers":
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    await query.edit_message_text(
        "Сброс пользователей. Это удалит всех пользователей из базы, и им нужно будет зарегистрироваться заново.",
        reply_markup=admin_reset_users_kb(),
    )


async def admin_reset_users_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:resetusers:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    if query.data == "admin:resetusers:confirm":
        await query.edit_message_text(
            "Точно удалить всех пользователей?",
            reply_markup=admin_reset_users_confirm_kb(),
        )
        return
    if query.data == "admin:resetusers:no":
        await query.edit_message_text("Отменено.", reply_markup=admin_main_kb())
        return
    if query.data == "admin:resetusers:yes":
        storage.reset_all_users()
        await query.edit_message_text("Все пользователи удалены. Теперь они пройдут регистрацию заново.", reply_markup=admin_main_kb())


async def admin_objaccess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "admin:objaccess":
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    await query.edit_message_text("Выберите город для настройки доступа по чатам:", reply_markup=objaccess_cities_kb())


async def objacc_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("objacc:city:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    city_idx = int(query.data.replace("objacc:city:", "", 1))
    await query.edit_message_text("Выберите компанию:", reply_markup=objaccess_companies_kb(city_idx))


async def objacc_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("objacc:company:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    parts = query.data.replace("objacc:company:", "", 1).split(":")
    city_idx, company_idx = int(parts[0]), int(parts[1])
    await query.edit_message_text("Выберите объект:", reply_markup=objaccess_objects_kb(city_idx, company_idx))


async def objacc_object(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("objacc:object:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    parts = query.data.replace("objacc:object:", "", 1).split(":")
    city_idx, company_idx, object_idx = int(parts[0]), int(parts[1]), int(parts[2])
    cities = storage.get_cities()
    city = cities[city_idx]
    companies = storage.get_companies(city)
    company = companies[company_idx]
    obj = storage.get_objects(city, company)[object_idx]
    acc = storage.get_object_access(city, company, obj)
    await query.edit_message_text(
        f"Доступ по чатам для объекта:\n{obj}\n\nРежим: {acc.get('require_mode')}\nЧаты:\n" + ("\n".join(acc.get("chats", [])) or "—"),
        reply_markup=objaccess_object_kb(city_idx, company_idx, object_idx, acc.get("require_mode", "ANY"), acc.get("chats", [])),
    )


async def objacc_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("objacc:mode:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    parts = query.data.replace("objacc:mode:", "", 1).split(":")
    city_idx, company_idx, object_idx = int(parts[0]), int(parts[1]), int(parts[2])
    cities = storage.get_cities()
    city = cities[city_idx]
    company = storage.get_companies(city)[company_idx]
    obj = storage.get_objects(city, company)[object_idx]
    acc = storage.get_object_access(city, company, obj)
    new_mode = "ALL" if acc.get("require_mode") == "ANY" else "ANY"
    storage.set_object_access_mode(city, company, obj, new_mode)
    acc = storage.get_object_access(city, company, obj)
    await query.edit_message_text(
        f"Доступ по чатам для объекта:\n{obj}\n\nРежим: {acc.get('require_mode')}\nЧаты:\n" + ("\n".join(acc.get("chats", [])) or "—"),
        reply_markup=objaccess_object_kb(city_idx, company_idx, object_idx, acc.get("require_mode", "ANY"), acc.get("chats", [])),
    )


async def objacc_addchat_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("objacc:addchat:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    parts = query.data.replace("objacc:addchat:", "", 1).split(":")
    context.user_data["objacc_addchat"] = {"city_idx": int(parts[0]), "company_idx": int(parts[1]), "object_idx": int(parts[2])}
    await query.edit_message_text("Введите @канал или chat_id группы/канала:")


async def objacc_addchat_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    state = context.user_data.get("objacc_addchat")
    if not state:
        return
    context.user_data.pop("objacc_addchat", None)
    uid = update.effective_user.id if update.effective_user else 0
    if not _is_admin(uid):
        return
    chat_id = (update.message.text or "").strip()
    cities = storage.get_cities()
    city = cities[state["city_idx"]]
    company = storage.get_companies(city)[state["company_idx"]]
    obj = storage.get_objects(city, company)[state["object_idx"]]
    storage.add_object_access_chat(city, company, obj, chat_id)
    acc = storage.get_object_access(city, company, obj)
    await update.message.reply_text(
        "Добавлено.",
        reply_markup=objaccess_object_kb(state["city_idx"], state["company_idx"], state["object_idx"], acc.get("require_mode", "ANY"), acc.get("chats", [])),
    )


async def objacc_delchat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("objacc:delchat:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    parts = query.data.replace("objacc:delchat:", "", 1).split(":")
    city_idx, company_idx, object_idx = int(parts[0]), int(parts[1]), int(parts[2])
    chat_id = ":".join(parts[3:])  # на случай двоеточий в id
    cities = storage.get_cities()
    city = cities[city_idx]
    company = storage.get_companies(city)[company_idx]
    obj = storage.get_objects(city, company)[object_idx]
    storage.remove_object_access_chat(city, company, obj, chat_id)
    acc = storage.get_object_access(city, company, obj)
    await query.edit_message_text(
        f"Доступ по чатам для объекта:\n{obj}\n\nРежим: {acc.get('require_mode')}\nЧаты:\n" + ("\n".join(acc.get("chats", [])) or "—"),
        reply_markup=objaccess_object_kb(city_idx, company_idx, object_idx, acc.get("require_mode", "ANY"), acc.get("chats", [])),
    )


async def admin_digest_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "admin:digestnow":
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer("Отправляю дайджест...", show_alert=False)
    # Переиспользуем общий job
    from main import digest_job  # локальный импорт, чтобы избежать циклов на старте

    await digest_job(context)
    await query.edit_message_text("Готово: дайджест отправлен всем, у кого он включён.", reply_markup=admin_main_kb())


async def admin_shiftreport(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "admin:shiftreport":
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    await query.edit_message_text("Отчёт по смене: выберите город.", reply_markup=shiftreport_cities_kb())


async def shiftrep_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("shiftrep:city:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    city_idx = int(query.data.replace("shiftrep:city:", "", 1))
    await query.edit_message_text("Выберите компанию.", reply_markup=shiftreport_companies_kb(city_idx))


async def shiftrep_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("shiftrep:company:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    parts = query.data.replace("shiftrep:company:", "", 1).split(":")
    city_idx, company_idx = int(parts[0]), int(parts[1])
    await query.edit_message_text("Выберите объект.", reply_markup=shiftreport_objects_kb(city_idx, company_idx))


async def shiftrep_object(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("shiftrep:object:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    parts = query.data.replace("shiftrep:object:", "", 1).split(":")
    city_idx, company_idx, object_idx = int(parts[0]), int(parts[1]), int(parts[2])
    await query.edit_message_text("Выберите смену.", reply_markup=shiftreport_shift_kb(city_idx, company_idx, object_idx))


async def shiftrep_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("shiftrep:shift:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    parts = query.data.replace("shiftrep:shift:", "", 1).split(":")
    city_idx, company_idx, object_idx = int(parts[0]), int(parts[1]), int(parts[2])
    shift_key = parts[3]
    context.user_data["shiftrep"] = {"city_idx": city_idx, "company_idx": company_idx, "object_idx": object_idx, "shift_key": shift_key, "cal_month": date.today().replace(day=1)}
    m = context.user_data["shiftrep"]["cal_month"]
    await query.edit_message_text("Выберите дату начала смены:", reply_markup=admin_calendar_kb(m.year, m.month, prefix="shiftrepcal"))


async def shiftrep_cal_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("shiftrepcal:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    st = context.user_data.get("shiftrep") or {}
    if not st:
        await query.edit_message_text("Сессия истекла.", reply_markup=admin_main_kb())
        return
    parts = query.data.split(":")
    if len(parts) >= 3 and parts[1] == "nav":
        ym = parts[2]
        y, m = map(int, ym.split("-", 1))
        st["cal_month"] = date(y, m, 1)
        context.user_data["shiftrep"] = st
        await query.edit_message_text("Выберите дату начала смены:", reply_markup=admin_calendar_kb(y, m, prefix="shiftrepcal"))


async def shiftrep_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("shiftrepcal:date:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    d_iso = query.data.replace("shiftrepcal:date:", "", 1)
    st = context.user_data.get("shiftrep") or {}
    if not st:
        await query.edit_message_text("Сессия истекла.", reply_markup=admin_main_kb())
        return
    cities = storage.get_cities()
    city = cities[st["city_idx"]]
    company = storage.get_companies(city)[st["company_idx"]]
    obj = storage.get_objects(city, company)[st["object_idx"]]
    shift_key = st["shift_key"]
    # Берём все записи replacements и фильтруем.
    all_r = storage.get_replacements(active_only=False, exclude_requested=False)
    rows = []
    for r in all_r:
        if not r.get("confirmed"):
            continue
        if r.get("city") != city or r.get("company") != company or r.get("object") != obj:
            continue
        if r.get("shift_key") != shift_key:
            continue
        if r.get("date_from") != d_iso:
            continue
        taker_id = r.get("taken_by_id")
        if not taker_id:
            continue
        subject_id = r.get("for_friend_id") or r.get("author_id")
        subject = storage.get_user(int(subject_id)) or {}
        taker = storage.get_user(int(taker_id)) or {}
        subject_name = subject.get("full_name") or subject.get("name") or f"ID {subject_id}"
        taker_name = taker.get("full_name") or taker.get("name") or f"ID {taker_id}"
        subject_un = subject.get("username") or ""
        taker_un = taker.get("username") or ""
        subject_contact = f"@{subject_un}" if subject_un else f"ID {subject_id}"
        taker_contact = f"@{taker_un}" if taker_un else f"ID {taker_id}"
        subject_sup = storage.get_supervisor_by_id(subject.get("supervisor_id") or 0) or {}
        taker_sup = storage.get_supervisor_by_id(taker.get("supervisor_id") or 0) or {}
        subject_sup_name = subject_sup.get("title") or "—"
        taker_sup_name = taker_sup.get("title") or "—"
        pay = ""
        if r.get("pay_enabled"):
            pay = f"\n💰 Доплата: {r.get('pay_amount_byn') or '—'} BYN"
        taker_link = taker_contact if taker_contact.startswith("@") else f"tg://user?id={taker_id}"
        subject_link = subject_contact if subject_contact.startswith("@") else f"tg://user?id={subject_id}"
        rows.append(
            f"{subject_name} ({subject_contact})\n"
            f"Админ: {subject_sup_name}\n"
            f"{taker_name} ({taker_contact})\n"
            f"Админ: {taker_sup_name}{pay}\n"
            f"Ссылки: {subject_link} -> {taker_link}\n"
            f"Позиция: {r.get('position')}"
        )
    header = f"📊 Отчёт\nОбъект: {obj}\nСмена: {'Дневная' if shift_key=='day' else 'Ночная'}\nДата: {d_iso}\n\n"
    # Пагинация
    per_page = 5
    context.user_data["shiftrep_result"] = {"header": header, "rows": rows, "page": 0, "per_page": per_page}
    await _shiftrep_render(query, context)


async def _shiftrep_render(query, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data.get("shiftrep_result") or {}
    header = data.get("header") or ""
    rows = data.get("rows") or []
    page = int(data.get("page") or 0)
    per_page = int(data.get("per_page") or 5)
    start = page * per_page
    chunk = rows[start : start + per_page]
    if not rows:
        await query.edit_message_text(header + "Нет подтверждённых замен.", reply_markup=admin_main_kb())
        return
    body = "\n\n".join(chunk)
    footer = f"\n\nСтраница {page+1} / {max(1, (len(rows)+per_page-1)//per_page)}"
    await query.edit_message_text(header + body + footer, reply_markup=shiftreport_nav_kb(page, len(rows), per_page=per_page))


async def shiftrep_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("shiftrep:page:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        return
    await query.answer()
    try:
        page = int(query.data.replace("shiftrep:page:", "", 1))
    except Exception:
        return
    st = context.user_data.get("shiftrep_result") or {}
    st["page"] = max(0, page)
    context.user_data["shiftrep_result"] = st
    await _shiftrep_render(query, context)


async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "admin:broadcast":
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    context.user_data["admin_broadcast_waiting"] = True
    await query.edit_message_text(
        "Введите текст рассылки (одним сообщением). Его получат все пользователи бота.\n"
        "Чтобы отменить рассылку, введите Отмена."
    )


async def admin_broadcast_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.user_data.pop("admin_broadcast_waiting", None):
        return
    uid = update.effective_user.id if update.effective_user else 0
    if not _is_admin(uid):
        return
    text = (update.message.text or "").strip()
    if text.lower() in {"отмена", "cancel"}:
        await update.message.reply_text("Рассылка отменена.", reply_markup=admin_main_kb())
        return
    if not text:
        await update.message.reply_text("Пусто. Рассылка отменена.", reply_markup=admin_main_kb())
        return
    users = storage.get_all_users()
    sent, fail = 0, 0
    for chat_id_str in users:
        try:
            await context.bot.send_message(chat_id=int(chat_id_str), text=text)
            sent += 1
        except Exception:
            fail += 1
    await update.message.reply_text(
        f"Рассылка завершена. Доставлено: {sent}, ошибок: {fail}.",
        reply_markup=admin_main_kb(),
    )


async def admin_banned(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "admin:banned":
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    banned = storage.get_banned_support_users()
    if not banned:
        await query.edit_message_text(
            "Нет заблокированных пользователей.",
            reply_markup=admin_banned_kb([]),
        )
        return
    lines = [f"ID {u.get('telegram_id')} — до {u.get('support_ban_until', '?')}" for u in banned]
    await query.edit_message_text(
        "Заблокированные для поддержки:\n\n" + "\n".join(lines),
        reply_markup=admin_banned_kb(banned),
    )


async def admin_replacements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список активных замен для админа."""
    query = update.callback_query
    if not query or query.data != "admin:replacements":
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    repls = storage.get_replacements(active_only=True, exclude_requested=False)
    if not repls:
        await query.edit_message_text("Активных замен нет.", reply_markup=admin_main_kb())
        return
    context.user_data["admin_repl_page"] = 0
    await query.edit_message_text(
        f"Активные замены: {len(repls)}",
        reply_markup=admin_replacements_list_kb(repls, page=0, per_page=10),
    )


async def admin_replacements_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:replp:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    try:
        page = int(query.data.replace("admin:replp:", "", 1))
    except ValueError:
        return
    repls = storage.get_replacements(active_only=True, exclude_requested=False)
    context.user_data["admin_repl_page"] = page
    await query.edit_message_text(
        f"Активные замены: {len(repls)} (стр. {page+1})",
        reply_markup=admin_replacements_list_kb(repls, page=page, per_page=10),
    )


async def admin_replacement_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:repl:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    rid = query.data.replace("admin:repl:", "", 1)
    r = storage.get_replacement_by_id(rid)
    if not r:
        await query.answer("Замена не найдена.", show_alert=True)
        return
    author = storage.get_user(int(r.get("author_id") or 0)) or {}
    author_name = author.get("full_name") or author.get("name") or f"ID {r.get('author_id')}"
    author_un = author.get("username") or ""
    author_contact = f"@{author_un}" if author_un else f"ID {r.get('author_id')}"
    friend = None
    if r.get("for_friend_id"):
        friend = storage.get_user(int(r.get("for_friend_id"))) or {}
    friend_name = friend.get("full_name") or friend.get("name") or f"ID {r.get('for_friend_id')}" if friend else "—"
    status = "Активно"
    if r.get("confirmed"):
        status = "Подтверждено"
    elif not r.get("active"):
        status = "Снято"
    taker = None
    if r.get("taken_by_id"):
        taker = storage.get_user(int(r.get("taken_by_id"))) or {}
    taker_name = taker.get("full_name") or taker.get("name") or f"ID {r.get('taken_by_id')}" if taker else "—"
    text = (
        "📋 Замена\n\n"
        f"ID: {r.get('id')}\n"
        f"Автор: {author_name} ({author_contact})\n"
        f"Для друга: {friend_name}\n"
        f"Город: {r.get('city') or '—'}\n"
        f"Компания: {r.get('company') or '—'}\n"
        f"Объект: {r.get('object') or '—'}\n"
        f"Позиция: {r.get('position') or '—'}\n"
        f"Смена: {r.get('shift') or '—'}\n"
        f"Даты: {r.get('date_text') or '—'}\n"
        f"Статус: {status}\n"
        f"Принявший: {taker_name}\n"
    )
    await query.edit_message_text(text, reply_markup=admin_replacement_detail_kb(rid))


async def admin_offers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список активных предложений выйти на замену для админа."""
    query = update.callback_query
    if not query or query.data != "admin:offers":
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    offers = storage.get_offers(active_only=True)
    if not offers:
        await query.edit_message_text("Активных предложений нет.", reply_markup=admin_main_kb())
        return
    context.user_data["admin_offer_page"] = 0
    await query.edit_message_text(
        f"Активные предложения выйти на замену: {len(offers)}",
        reply_markup=admin_offers_list_kb(offers, page=0, per_page=10),
    )


async def admin_offers_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:offerp:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    try:
        page = int(query.data.replace("admin:offerp:", "", 1))
    except ValueError:
        return
    offers = storage.get_offers(active_only=True)
    context.user_data["admin_offer_page"] = page
    await query.edit_message_text(
        f"Активные предложения: {len(offers)} (стр. {page+1})",
        reply_markup=admin_offers_list_kb(offers, page=page, per_page=10),
    )


async def admin_offer_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:offer:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    oid = query.data.replace("admin:offer:", "", 1)
    o = storage.get_offer_by_id(oid)
    if not o:
        await query.answer("Предложение не найдено.", show_alert=True)
        return
    author = storage.get_user(int(o.get("author_id") or 0)) or {}
    author_name = author.get("full_name") or author.get("name") or f"ID {o.get('author_id')}"
    author_un = author.get("username") or o.get("author_username") or ""
    author_contact = f"@{author_un}" if author_un else f"ID {o.get('author_id')}"
    text = (
        "🙋 Предложение выйти на замену\n\n"
        f"ID: {o.get('id')}\n"
        f"Автор: {author_name} ({author_contact})\n"
        f"Город: {o.get('city') or '—'}\n"
        f"Компания: {o.get('company') or '—'}\n"
        f"Объект: {o.get('object') or '—'}\n"
        f"Смена: {'Дневная' if o.get('shift_key')=='day' else 'Ночная'}\n"
        f"Даты: {o.get('date_text') or '—'}\n"
    )
    await query.edit_message_text(text, reply_markup=admin_offer_detail_kb(oid))


async def admin_replacement_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ нажал снять замену с публикации — спрашиваем причину."""
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:replrm:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    rid = query.data.replace("admin:replrm:", "", 1)
    context.user_data["admin_repl_remove_id"] = rid
    await query.edit_message_text(
        "Введите причину снятия замены (одним сообщением). Она будет отправлена автору.",
        reply_markup=admin_main_kb(),
    )


async def admin_offer_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ нажал снять предложение с публикации — спрашиваем причину."""
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:offerrm:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    oid = query.data.replace("admin:offerrm:", "", 1)
    context.user_data["admin_offer_remove_id"] = oid
    await query.edit_message_text(
        "Введите причину снятия предложения (одним сообщением). Она будет отправлена автору.",
        reply_markup=admin_main_kb(),
    )


async def admin_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("admin:unban:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    try:
        target_id = int(query.data.replace("admin:unban:", "", 1))
    except ValueError:
        return
    user = storage.get_user(target_id) or {}
    user["support_ban_until"] = None
    user["support_ban_reason"] = None
    storage.save_user(target_id, user)
    banned = storage.get_banned_support_users()
    await query.edit_message_text(
        f"Пользователь {target_id} разблокирован.",
        reply_markup=admin_banned_kb(banned),
    )


async def admin_ban_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "admin:ban_prompt":
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    context.user_data["admin_ban_waiting"] = True
    await query.edit_message_text(
        "Введите Telegram ID пользователя и срок блокировки через пробел:\n"
        "• forever — навсегда\n"
        "• 7 — на 7 дней\n"
        "Пример: 123456789 forever  или  123456789 7"
    )


async def admin_ban_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.user_data.pop("admin_ban_waiting", None):
        return
    uid = update.effective_user.id if update.effective_user else 0
    if not _is_admin(uid):
        return
    text = (update.message.text or "").strip().split()
    if len(text) < 2:
        await update.message.reply_text("Нужно: ID и срок (forever или число дней).", reply_markup=admin_main_kb())
        return
    try:
        target_id = int(text[0])
    except ValueError:
        await update.message.reply_text("Неверный ID.", reply_markup=admin_main_kb())
        return
    from datetime import date, timedelta
    term = text[1].lower()
    if term == "forever":
        until = "forever"
    else:
        try:
            days = int(term)
            until = (date.today() + timedelta(days=days)).isoformat()
        except ValueError:
            await update.message.reply_text("Срок: forever или число дней.", reply_markup=admin_main_kb())
            return
    user = storage.get_user(target_id) or {}
    user["telegram_id"] = target_id
    user["support_ban_until"] = until
    user["support_ban_reason"] = "Админ"
    storage.save_user(target_id, user)
    await update.message.reply_text(f"Пользователь {target_id} заблокирован до {until}.", reply_markup=admin_main_kb())


async def admin_exit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выйти из админ-панели в обычное меню."""
    query = update.callback_query
    if not query or query.data != "admin:exit":
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        await query.answer("Нет доступа.", show_alert=True)
        return
    await _answer_first(query)
    await query.edit_message_text("Главное меню:", reply_markup=main_menu_kb())


# --- Смены объектов (настройка времени) ---


async def admin_shiftcfg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "admin:shiftcfg":
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        await query.answer("Нет доступа.", show_alert=True)
        return
    await query.answer()
    await query.edit_message_text(
        "Настройка смен по объектам.\nВыберите город:",
        reply_markup=admin_shiftcfg_cities_kb(),
    )


async def admin_shiftcfg_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("shiftcfg:city:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    try:
        city_idx = int(query.data.replace("shiftcfg:city:", "", 1))
    except ValueError:
        return
    await query.edit_message_text(
        "Выберите компанию:",
        reply_markup=admin_shiftcfg_companies_kb(city_idx),
    )


async def admin_shiftcfg_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("shiftcfg:company:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    parts = query.data.replace("shiftcfg:company:", "", 1).split(":")
    if len(parts) < 2:
        return
    try:
        city_idx = int(parts[0])
        company_idx = int(parts[1])
    except ValueError:
        return
    await query.edit_message_text(
        "Выберите объект:",
        reply_markup=admin_shiftcfg_objects_kb(city_idx, company_idx),
    )


async def admin_shiftcfg_object(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("shiftcfg:object:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    parts = query.data.replace("shiftcfg:object:", "", 1).split(":")
    if len(parts) < 3:
        return
    try:
        city_idx = int(parts[0])
        company_idx = int(parts[1])
        object_idx = int(parts[2])
    except ValueError:
        return
    await query.edit_message_text(
        "Выберите смену для редактирования:",
        reply_markup=admin_shiftcfg_object_kb(city_idx, company_idx, object_idx),
    )


async def admin_shiftcfg_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("shiftcfg:edit:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    parts = query.data.replace("shiftcfg:edit:", "", 1).split(":")
    if len(parts) < 4:
        return
    try:
        city_idx = int(parts[0])
        company_idx = int(parts[1])
        object_idx = int(parts[2])
    except ValueError:
        return
    shift_key = parts[3]
    context.user_data["admin_shiftcfg_waiting"] = {
        "city_idx": city_idx,
        "company_idx": company_idx,
        "object_idx": object_idx,
        "shift_key": shift_key,
    }
    label = "Дневная" if shift_key == "day" else "Ночная"
    await query.edit_message_text(
        f"{label} смена.\nВведите время в формате HH:MM-HH:MM (пример: 09:00-21:00):"
    )


async def admin_shiftcfg_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    state = context.user_data.get("admin_shiftcfg_waiting")
    if not state:
        return
    context.user_data.pop("admin_shiftcfg_waiting", None)
    uid = update.effective_user.id if update.effective_user else 0
    if not _is_admin(uid):
        return
    raw = (update.message.text or "").strip()
    if "-" not in raw:
        await update.message.reply_text("Нужно в формате HH:MM-HH:MM.", reply_markup=admin_main_kb())
        return
    start_str, end_str = [p.strip() for p in raw.split("-", 1)]
    def _ok(t: str) -> bool:
        if len(t) != 5 or t[2] != ":":
            return False
        try:
            h = int(t[:2]); m = int(t[3:])
        except ValueError:
            return False
        return 0 <= h <= 23 and 0 <= m <= 59
    if not (_ok(start_str) and _ok(end_str)):
        await update.message.reply_text("Неверный формат времени. Пример: 09:00-21:00", reply_markup=admin_main_kb())
        return
    cities = storage.get_cities()
    if state["city_idx"] < 0 or state["city_idx"] >= len(cities):
        await update.message.reply_text("Город не найден.", reply_markup=admin_main_kb())
        return
    city = cities[state["city_idx"]]
    companies = storage.get_companies(city)
    if state["company_idx"] < 0 or state["company_idx"] >= len(companies):
        await update.message.reply_text("Компания не найдена.", reply_markup=admin_main_kb())
        return
    company = companies[state["company_idx"]]
    objects = storage.get_objects(city, company)
    if state["object_idx"] < 0 or state["object_idx"] >= len(objects):
        await update.message.reply_text("Объект не найден.", reply_markup=admin_main_kb())
        return
    obj = objects[state["object_idx"]]
    shift_key = state["shift_key"]
    storage.set_object_shift(city, company, obj, shift_key, start_str, end_str)
    await update.message.reply_text(
        f"Сохранено: {obj} ({'день' if shift_key=='day' else 'ночь'}) {start_str}-{end_str}",
        reply_markup=admin_main_kb(),
    )


# --- Справочники (каталог) ---


async def admin_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "admin:catalog":
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        await query.answer("Нет доступа.", show_alert=True)
        return
    await _answer_first(query)
    cities = storage.get_cities()
    if not cities:
        await query.edit_message_text("Справочники пусты. Добавьте город.", reply_markup=admin_catalog_cities_kb())
        return
    await query.edit_message_text("Города. Выберите город для редактирования:", reply_markup=admin_catalog_cities_kb())


async def catalog_city_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("cat:city:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        await query.answer("Нет доступа.", show_alert=True)
        return
    await _answer_first(query)
    try:
        city_idx = int(query.data.replace("cat:city:", "", 1))
    except ValueError:
        return
    cities = storage.get_cities()
    if city_idx < 0 or city_idx >= len(cities):
        return
    city_name = cities[city_idx]
    context.user_data["admin_cat_city_idx"] = city_idx
    await query.edit_message_text(
        f"📂 {city_name}\nВыберите раздел:",
        reply_markup=admin_catalog_city_menu_kb(city_idx),
    )


async def catalog_obj_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("cat:objselect:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        await query.answer("Нет доступа.", show_alert=True)
        return
    await _answer_first(query)
    try:
        city_idx = int(query.data.replace("cat:objselect:", "", 1))
    except ValueError:
        return
    await query.edit_message_text("Выберите компанию (объекты):", reply_markup=admin_catalog_select_company_kb(city_idx, "obj"))


async def catalog_pos_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("cat:posselect:"):
        return
    if not _is_admin(query.from_user.id if query.from_user else 0):
        await query.answer("Нет доступа.", show_alert=True)
        return
    await _answer_first(query)
    try:
        city_idx = int(query.data.replace("cat:posselect:", "", 1))
    except ValueError:
        return
    await query.edit_message_text("Выберите компанию (позиции):", reply_markup=admin_catalog_select_company_kb(city_idx, "pos"))


async def catalog_show_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return
    data = query.data
    if not (data.startswith("cat:companies:") or data.startswith("cat:objectlist:") or data.startswith("cat:posobj:") or data.startswith("cat:positionlist:")):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        await query.answer("Нет доступа.", show_alert=True)
        return
    await _answer_first(query)
    parts = data.replace("cat:", "", 1).split(":")
    cities = storage.get_cities()
    city_idx = int(parts[1]) if len(parts) > 1 else 0
    if city_idx < 0 or city_idx >= len(cities):
        return
    city = cities[city_idx]
    if data.startswith("cat:companies:"):
        items = storage.get_companies(city)
        await query.edit_message_text("Компании:", reply_markup=admin_catalog_list_kb(city_idx, "companies", items))
    elif data.startswith("cat:objectlist:"):
        company_idx = int(parts[2]) if len(parts) > 2 else 0
        companies = storage.get_companies(city)
        if company_idx >= len(companies):
            return
        company = companies[company_idx]
        items = storage.get_objects(city, company)
        await query.edit_message_text(f"Объекты ({company}):", reply_markup=admin_catalog_list_kb(city_idx, "objects", items, company_idx=company_idx))
    elif data.startswith("cat:posobj:"):
        company_idx = int(parts[2]) if len(parts) > 2 else 0
        companies = storage.get_companies(city)
        if company_idx >= len(companies):
            return
        await query.edit_message_text("Выберите объект (позиции):", reply_markup=admin_catalog_select_object_kb(city_idx, company_idx))
    elif data.startswith("cat:positionlist:"):
        company_idx = int(parts[2]) if len(parts) > 2 else 0
        object_idx = int(parts[3]) if len(parts) > 3 else 0
        companies = storage.get_companies(city)
        if company_idx >= len(companies):
            return
        company = companies[company_idx]
        objects = storage.get_objects(city, company)
        if object_idx >= len(objects):
            return
        obj_name = objects[object_idx]
        items = storage.get_positions(city, company, obj_name)
        await query.edit_message_text(f"Позиции ({obj_name}):", reply_markup=admin_catalog_list_kb(city_idx, "positions", items, company_idx=company_idx, object_idx=object_idx))


async def catalog_add_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("cat:add:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    # cat:add:companies:0  |  cat:add:objects:0:0  |  cat:add:positions:0:0:0
    parts = query.data.split(":")
    if len(parts) < 4:
        return
    kind = parts[2]  # companies, objects, positions
    context.user_data["admin_cat_add"] = ":".join(parts[2:])  # companies:0  or  objects:0:0  or  positions:0:0:0
    labels = {"companies": "компанию", "objects": "объект", "positions": "позицию"}
    await query.edit_message_text(f"Введите название {labels.get(kind, kind)}:")


async def catalog_rename_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("cat:ren:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await _answer_first(query)
    # cat:ren:city:0 | cat:ren:company:0:idx | cat:ren:object:0:comp:idx | cat:ren:pos:0:comp:obj:idx
    parts = query.data.split(":")
    if len(parts) < 4:
        return
    kind = parts[2]
    context.user_data["admin_cat_rename"] = query.data
    labels = {"city": "города", "company": "компании", "object": "объекта", "pos": "позиции"}
    await query.edit_message_text(f"Введите новое название для {labels.get(kind, kind)}:")


async def catalog_rename_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    state = context.user_data.get("admin_cat_rename")
    if not state:
        return
    context.user_data.pop("admin_cat_rename", None)
    uid = update.effective_user.id if update.effective_user else 0
    if not _is_admin(uid):
        return
    new_name = (update.message.text or "").strip()
    if not new_name:
        await update.message.reply_text("Пусто. Отмена.", reply_markup=admin_main_kb())
        return
    parts = state.split(":")
    kind = parts[2]
    cities = storage.get_cities()
    try:
        city_idx = int(parts[3])
    except Exception:
        await update.message.reply_text("Ошибка.", reply_markup=admin_main_kb())
        return
    if city_idx < 0 or city_idx >= len(cities):
        await update.message.reply_text("Город не найден.", reply_markup=admin_main_kb())
        return
    city = cities[city_idx]

    ok = False
    if kind == "city":
        ok = storage.catalog_rename_city(city, new_name)
    elif kind == "company":
        companies = storage.get_companies(city)
        company_idx = int(parts[4]) if len(parts) > 4 else -1
        if not (0 <= company_idx < len(companies)):
            await update.message.reply_text("Компания не найдена.", reply_markup=admin_main_kb())
            return
        ok = storage.catalog_rename_company(city, companies[company_idx], new_name)
    elif kind == "object":
        companies = storage.get_companies(city)
        company_idx = int(parts[4]) if len(parts) > 4 else -1
        obj_idx = int(parts[5]) if len(parts) > 5 else -1
        if not (0 <= company_idx < len(companies)):
            await update.message.reply_text("Компания не найдена.", reply_markup=admin_main_kb())
            return
        company = companies[company_idx]
        objects = storage.get_objects(city, company)
        if not (0 <= obj_idx < len(objects)):
            await update.message.reply_text("Объект не найден.", reply_markup=admin_main_kb())
            return
        ok = storage.catalog_rename_object(city, company, objects[obj_idx], new_name)
    elif kind == "pos":
        companies = storage.get_companies(city)
        company_idx = int(parts[4]) if len(parts) > 4 else -1
        obj_idx = int(parts[5]) if len(parts) > 5 else -1
        pos_idx = int(parts[6]) if len(parts) > 6 else -1
        if not (0 <= company_idx < len(companies)):
            await update.message.reply_text("Компания не найдена.", reply_markup=admin_main_kb())
            return
        company = companies[company_idx]
        objects = storage.get_objects(city, company)
        if not (0 <= obj_idx < len(objects)):
            await update.message.reply_text("Объект не найден.", reply_markup=admin_main_kb())
            return
        obj = objects[obj_idx]
        positions = storage.get_positions(city, company, obj)
        if not (0 <= pos_idx < len(positions)):
            await update.message.reply_text("Позиция не найдена.", reply_markup=admin_main_kb())
            return
        ok = storage.catalog_rename_position(city, company, obj, positions[pos_idx], new_name)

    msg = "Переименовано." if ok else "Не удалось переименовать (возможно, такое название уже существует)."
    await update.message.reply_text(msg, reply_markup=admin_main_kb())


async def catalog_add_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    state = context.user_data.get("admin_cat_add")
    if not state:
        return
    context.user_data.pop("admin_cat_add", None)
    uid = update.effective_user.id if update.effective_user else 0
    if not _is_admin(uid):
        return
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Пусто. Отмена.", reply_markup=admin_main_kb())
        return
    parts = state.split(":")
    if len(parts) < 2:
        await update.message.reply_text("Ошибка.", reply_markup=admin_main_kb())
        return
    kind = parts[0]
    cities = storage.get_cities()
    city_idx = int(parts[1])
    if city_idx < 0 or city_idx >= len(cities):
        await update.message.reply_text("Город не найден.", reply_markup=admin_main_kb())
        return
    city = cities[city_idx]
    if kind == "companies":
        storage.catalog_add_company(city, text)
        await update.message.reply_text(f"Компания «{text}» добавлена.", reply_markup=admin_main_kb())
    elif kind == "objects":
        company_idx = int(parts[2]) if len(parts) > 2 else 0
        companies = storage.get_companies(city)
        if company_idx >= len(companies):
            await update.message.reply_text("Компания не найдена.", reply_markup=admin_main_kb())
            return
        storage.catalog_add_object(city, companies[company_idx], text)
        await update.message.reply_text(f"Объект «{text}» добавлен.", reply_markup=admin_main_kb())
    elif kind == "positions":
        company_idx = int(parts[2]) if len(parts) > 2 else 0
        object_idx = int(parts[3]) if len(parts) > 3 else 0
        companies = storage.get_companies(city)
        if company_idx >= len(companies):
            await update.message.reply_text("Компания не найдена.", reply_markup=admin_main_kb())
            return
        company = companies[company_idx]
        objects = storage.get_objects(city, company)
        if object_idx >= len(objects):
            await update.message.reply_text("Объект не найден.", reply_markup=admin_main_kb())
            return
        storage.catalog_add_position(city, company, objects[object_idx], text)
        await update.message.reply_text(f"Позиция «{text}» добавлена.", reply_markup=admin_main_kb())
    else:
        await update.message.reply_text("Ошибка.", reply_markup=admin_main_kb())


async def catalog_del_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("cat:del:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    # cat:del:companies:0:1  |  cat:del:objects:0:0:1  |  cat:del:positions:0:0:0:1
    parts = query.data.split(":")
    if len(parts) < 5 or (parts[2] == "positions" and len(parts) < 7):
        return
    kind = parts[2]
    try:
        city_idx = int(parts[3])
        item_idx = int(parts[-1])
    except ValueError:
        return
    cities = storage.get_cities()
    if city_idx < 0 or city_idx >= len(cities):
        return
    city = cities[city_idx]
    if kind == "companies":
        storage.catalog_remove_company(city, item_idx)
    elif kind == "objects":
        company_idx = int(parts[4])
        companies = storage.get_companies(city)
        if company_idx < len(companies):
            storage.catalog_remove_object(city, companies[company_idx], item_idx)
    elif kind == "positions":
        company_idx = int(parts[4])
        object_idx = int(parts[5])
        companies = storage.get_companies(city)
        if company_idx < len(companies):
            company = companies[company_idx]
            objects = storage.get_objects(city, company)
            if object_idx < len(objects):
                storage.catalog_remove_position(city, company, objects[object_idx], item_idx)
    else:
        return
    if kind == "companies":
        items = storage.get_companies(city)
        await query.edit_message_text("Компании:", reply_markup=admin_catalog_list_kb(city_idx, kind, items))
    elif kind == "objects":
        company_idx = int(parts[4])
        companies = storage.get_companies(city)
        company = companies[company_idx] if company_idx < len(companies) else ""
        items = storage.get_objects(city, company)
        await query.edit_message_text(f"Объекты ({company}):", reply_markup=admin_catalog_list_kb(city_idx, kind, items, company_idx=company_idx))
    else:
        company_idx = int(parts[4])
        object_idx = int(parts[5])
        companies = storage.get_companies(city)
        company = companies[company_idx] if company_idx < len(companies) else ""
        objects = storage.get_objects(city, company)
        obj_name = objects[object_idx] if object_idx < len(objects) else ""
        items = storage.get_positions(city, company, obj_name)
        await query.edit_message_text(f"Позиции ({obj_name}):", reply_markup=admin_catalog_list_kb(city_idx, kind, items, company_idx=company_idx, object_idx=object_idx))


async def catalog_add_city_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "cat:addcity":
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    context.user_data["admin_cat_add"] = "city"
    await query.edit_message_text("Введите название города:")


async def catalog_add_city_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if context.user_data.get("admin_cat_add") != "city":
        return
    context.user_data.pop("admin_cat_add", None)
    uid = update.effective_user.id if update.effective_user else 0
    if not _is_admin(uid):
        return
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Пусто. Отмена.", reply_markup=admin_main_kb())
        return
    if storage.catalog_add_city(text):
        await update.message.reply_text(f"Город «{text}» добавлен.", reply_markup=admin_main_kb())
    else:
        await update.message.reply_text("Такой город уже есть.", reply_markup=admin_main_kb())


async def catalog_del_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("cat:delcity:"):
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        return
    await query.answer()
    try:
        city_idx = int(query.data.replace("cat:delcity:", "", 1))
    except ValueError:
        return
    cities = storage.get_cities()
    if city_idx < 0 or city_idx >= len(cities):
        return
    city = cities[city_idx]
    storage.catalog_remove_city(city)
    await query.edit_message_text("Город удалён.", reply_markup=admin_catalog_cities_kb())
