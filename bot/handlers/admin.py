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
    main_menu_kb,
)

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


async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "admin:users":
        return
    uid = query.from_user.id if query.from_user else 0
    if not _is_admin(uid):
        await query.answer("Нет доступа.", show_alert=True)
        return
    await query.answer()
    users = storage.get_all_users()
    text = f"Пользователей: {len(users)}"
    await query.edit_message_text(text, reply_markup=admin_main_kb())


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
        "Введите текст рассылки (одним сообщением). Его получат все пользователи бота:"
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
