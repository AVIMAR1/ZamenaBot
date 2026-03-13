# -*- coding: utf-8 -*-
"""Сценарий «Выйду на замену»: пользователь предлагает заменить кого-то."""

import json
import uuid
from datetime import date, timedelta, datetime

from telegram import Update
from telegram.ext import ContextTypes

import storage
from keyboards import (
    main_menu_kb,
    menu_quick_kb,
    offers_menu_kb,
    offers_list_kb,
    offer_positions_kb,
    offer_confirm_kb,
    my_offers_kb,
    offer_shift_kb,
    offer_calendar_kb,
    offer_pay_kb,
)


async def offers_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "offers:menu":
        return
    await query.answer()
    await query.edit_message_text("Выберите действие:", reply_markup=offers_menu_kb())


async def offers_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "offers:list":
        return
    await query.answer()
    uid = query.from_user.id if query.from_user else 0
    user = storage.get_user(uid) or {}
    city, company, obj = user.get("city"), user.get("company"), user.get("object")
    all_offers = storage.get_offers(active_only=True)
    offers = [o for o in all_offers if o.get("city") == city and o.get("company") == company and o.get("object") == obj and str(o.get("author_id")) != str(uid)]
    if not offers:
        await query.edit_message_text("Пока нет предложений выйти на замену по вашему объекту.", reply_markup=main_menu_kb())
        return
    context.user_data["offers_page"] = 0
    await query.edit_message_text("Готовы выйти на замену:", reply_markup=offers_list_kb(offers, page=0))


async def offers_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("offersp:"):
        return
    await query.answer()
    try:
        page = int(query.data.replace("offersp:", "", 1))
    except Exception:
        return
    uid = query.from_user.id if query.from_user else 0
    user = storage.get_user(uid) or {}
    city, company, obj = user.get("city"), user.get("company"), user.get("object")
    all_offers = storage.get_offers(active_only=True)
    offers = [o for o in all_offers if o.get("city") == city and o.get("company") == company and o.get("object") == obj and str(o.get("author_id")) != str(uid)]
    context.user_data["offers_page"] = page
    await query.edit_message_text("Готовы выйти на замену:", reply_markup=offers_list_kb(offers, page=page))


async def my_offers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "offers:mine":
        return
    await query.answer()
    uid = query.from_user.id if query.from_user else 0
    offers = storage.get_my_offers(uid, active_only=True)
    if not offers:
        await query.edit_message_text("У вас пока нет активных предложений.", reply_markup=menu_quick_kb())
        return
    await query.edit_message_text("Ваши предложения:", reply_markup=my_offers_kb(offers))


async def offer_deactivate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("offer:off:"):
        return
    await query.answer()
    oid = query.data.replace("offer:off:", "", 1)
    offer = storage.get_offer_by_id(oid)
    uid = query.from_user.id if query.from_user else 0
    if not offer or str(offer.get("author_id")) != str(uid):
        return
    storage.deactivate_offer(oid)
    await query.edit_message_text("Отключено.", reply_markup=menu_quick_kb())


async def offer_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "offers:create":
        return
    await query.answer()
    uid = query.from_user.id if query.from_user else 0
    user = storage.get_user(uid) or {}
    context.user_data["pending_offer"] = {
        "id": str(uuid.uuid4()),
        "author_id": uid,
        "city": user.get("city"),
        "company": user.get("company"),
        "object": user.get("object"),
    }
    await query.edit_message_text("Выберите смену:", reply_markup=offer_shift_kb())


async def offer_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("offer:shift:"):
        return
    pending = context.user_data.get("pending_offer")
    if not pending:
        return
    await query.answer()
    shift_key = query.data.replace("offer:shift:", "", 1)
    pending["shift_key"] = shift_key
    # дата: день = 1 дата, ночь = 2 даты
    single = 1 if shift_key == "day" else 0
    pending["single"] = single
    pending["step"] = 0
    context.user_data["pending_offer"] = pending
    now = datetime.now()
    await query.edit_message_text("Выберите дату:", reply_markup=offer_calendar_kb(now.year, now.month, shift_key, single, 0))


async def offer_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("offerdate:"):
        return
    pending = context.user_data.get("pending_offer")
    if not pending:
        return
    await query.answer()
    parts = query.data.split(":")
    # offerdate:Y:M:D:shift:single:step
    if len(parts) < 7:
        return
    y, m, d = int(parts[1]), int(parts[2]), int(parts[3])
    shift_key = parts[4]
    single = int(parts[5])
    step = int(parts[6])
    chosen = date(y, m, d)
    if step == 0:
        pending["date_from"] = chosen.isoformat()
        if single:
            pending["date_to"] = chosen.isoformat()
            pending["date_text"] = chosen.strftime("%d.%m.%Y")
            pending["positions"] = []
            context.user_data["pending_offer"] = pending
            await query.edit_message_text("Выберите позиции (можно несколько):", reply_markup=offer_positions_kb(pending))
            return
        # ночь: выбираем конечную дату
        pending["step"] = 1
        context.user_data["pending_offer"] = pending
        await query.edit_message_text("Выберите дату окончания:", reply_markup=offer_calendar_kb(y, m, shift_key, single, 1))
        return
    # step=1
    pending["date_to"] = chosen.isoformat()
    pending["date_text"] = f"{date.fromisoformat(pending['date_from']).strftime('%d.%m.%Y')} → {chosen.strftime('%d.%m.%Y')}"
    pending["positions"] = []
    context.user_data["pending_offer"] = pending
    await query.edit_message_text("Выберите позиции (можно несколько):", reply_markup=offer_positions_kb(pending))


async def offer_cal_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("offercal:"):
        return
    pending = context.user_data.get("pending_offer")
    if not pending:
        return
    await query.answer()
    parts = query.data.split(":")
    if len(parts) < 6:
        return
    y, m = int(parts[1]), int(parts[2])
    shift_key = parts[3]
    single = int(parts[4])
    step = int(parts[5])
    await query.edit_message_text("Выберите дату:", reply_markup=offer_calendar_kb(y, m, shift_key, single, step))


async def offer_pos_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("offerpos:"):
        return
    pending = context.user_data.get("pending_offer")
    if not pending:
        return
    await query.answer()
    uid = query.from_user.id if query.from_user else 0
    user = storage.get_user(uid) or {}
    positions = storage.get_positions(user.get("city"), user.get("company"), user.get("object"))
    selected = set(pending.get("positions") or [])
    if query.data == "offerpos:done":
        pending["positions"] = sorted(selected)
        context.user_data["pending_offer"] = pending
        await query.edit_message_text("Подтвердите публикацию:", reply_markup=offer_confirm_kb(pending["id"]))
        return
    try:
        idx = int(query.data.replace("offerpos:toggle:", "", 1))
    except Exception:
        return
    if 0 <= idx < len(positions):
        p = positions[idx]
        if p in selected:
            selected.remove(p)
        else:
            selected.add(p)
    pending["positions"] = sorted(selected)
    context.user_data["pending_offer"] = pending
    await query.edit_message_text("Выберите позиции (можно несколько):", reply_markup=offer_positions_kb(pending))


async def offer_publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("offerpub:"):
        return
    pending = context.user_data.get("pending_offer")
    if not pending:
        return
    await query.answer()
    oid = query.data.replace("offerpub:", "", 1)
    if pending.get("id") != oid:
        return
    uid = query.from_user.id if query.from_user else 0
    user = storage.get_user(uid) or {}
    offer = {
        "id": oid,
        "author_id": uid,
        "author_username": user.get("username") or (query.from_user.username if query.from_user else ""),
        "city": user.get("city"),
        "company": user.get("company"),
        "object": user.get("object"),
        "positions_json": json.dumps(pending.get("positions") or [], ensure_ascii=False),
        "shift_key": pending.get("shift_key"),
        "date_from": pending.get("date_from"),
        "date_to": pending.get("date_to"),
        "date_text": pending.get("date_text"),
        "pay_enabled": bool(pending.get("pay_enabled")),
        "pay_amount_byn": pending.get("pay_amount_byn"),
        "active": True,
        "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
    }
    storage.save_offer(offer)
    # Матчинг: ищем объявления "Мне нужна замена" по тому же объекту/дате/смене, где позиция входит в offers.positions_json
    try:
        positions = json.loads(offer.get("positions_json") or "[]")
        if not isinstance(positions, list):
            positions = []
    except Exception:
        positions = []
    matches = []
    try:
        all_r = storage.get_replacements(active_only=True, exclude_requested=True)
        for r in all_r:
            if r.get("city") != offer.get("city") or r.get("company") != offer.get("company") or r.get("object") != offer.get("object"):
                continue
            if r.get("shift_key") != offer.get("shift_key"):
                continue
            if r.get("date_from") != offer.get("date_from"):
                continue
            if r.get("position") not in positions:
                continue
            matches.append(r)
    except Exception:
        matches = []
    if matches:
        # оффер автору — быстрый выбор "подать заявку" (через существующий take-flow)
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton

        rows = []
        for r in matches[:5]:
            rid = r.get("id")
            label = f"{r.get('position')} | {r.get('shift')} | {r.get('date_text')}"
            rows.append([InlineKeyboardButton(label, callback_data=f"take:{rid}")])
        rows.append([InlineKeyboardButton("🏠 Меню", callback_data="back:main")])
        try:
            await context.bot.send_message(
                chat_id=offer["author_id"],
                text="🔔 Нашли совпадения с теми, кому нужна замена. Нажмите, чтобы подать заявку:",
                reply_markup=InlineKeyboardMarkup(rows),
            )
        except Exception:
            pass
        # авто-уведомления авторам объявлений
        for r in matches[:10]:
            try:
                await context.bot.send_message(
                    chat_id=r.get("author_id"),
                    text="🔔 Нашёлся человек, готовый выйти на замену по вашему объявлению. Ожидайте заявки в боте.",
                    reply_markup=menu_quick_kb(),
                )
            except Exception:
                pass
    context.user_data.pop("pending_offer", None)
    await query.edit_message_text("Предложение опубликовано.", reply_markup=menu_quick_kb())


async def offer_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("offerpay:"):
        return
    pending = context.user_data.get("pending_offer")
    if not pending:
        return
    await query.answer()
    parts = query.data.split(":")
    action = parts[1]
    oid = parts[2] if len(parts) > 2 else ""
    if pending.get("id") != oid:
        return
    if action == "toggle":
        pending["pay_enabled"] = not bool(pending.get("pay_enabled"))
        context.user_data["pending_offer"] = pending
        await query.edit_message_text(
            "Доплата за замену (будет показана обеим сторонам):",
            reply_markup=offer_pay_kb(oid, bool(pending.get("pay_enabled")), pending.get("pay_amount_byn")),
        )
        return
    if action == "set":
        context.user_data["offer_pay_amount_waiting"] = oid
        await query.edit_message_text("Введите сумму доплаты в BYN (например: 10 или 10.5):")
        return
    if action == "back":
        await query.edit_message_text("Подтвердите публикацию:", reply_markup=offer_confirm_kb(oid))

