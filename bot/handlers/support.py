# -*- coding: utf-8 -*-
"""Поддержка: создание тикета, ответ в тикет, уведомление о закрытии. Баны проверяются здесь."""

import uuid
from datetime import date
from telegram import Update
from telegram.ext import ContextTypes

import config
import storage
from keyboards import support_kb, main_menu_kb, back_to_main_kb, admin_quick_reply_ticket_kb


def _is_support_banned(user: dict) -> tuple[bool, str]:
    """Возвращает (забанен, причина/дата)."""
    until = user.get("support_ban_until")
    if not until:
        return False, ""
    if until == "forever":
        return True, "навсегда"
    try:
        d = date.fromisoformat(until)
        if d >= date.today():
            return True, until
        return False, ""
    except Exception:
        return False, ""


async def menu_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data not in ("menu:support", "support:new"):
        return
    await query.answer()
    uid = query.from_user.id if query.from_user else 0
    user = storage.get_user(uid) or {}
    banned, reason = _is_support_banned(user)
    if banned:
        msg = f"Написание в поддержку для вас заблокировано до {reason}."
        await query.edit_message_text(msg, reply_markup=main_menu_kb())
        return
    await query.edit_message_text(
        "Напишите ваше обращение в поддержку (одним сообщением):",
        reply_markup=back_to_main_kb(),
    )
    context.user_data["waiting_support"] = True


async def support_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not context.user_data.get("waiting_support"):
        return
    context.user_data.pop("waiting_support", None)
    uid = update.effective_user.id if update.effective_user else 0
    user = storage.get_user(uid) or {}
    if _is_support_banned(user)[0]:
        await update.message.reply_text("Написание в поддержку заблокировано.", reply_markup=main_menu_kb())
        return
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Текст не получен. Попробуйте снова.", reply_markup=support_kb())
        return
    tid = str(uuid.uuid4())[:8]
    ticket = {
        "id": tid,
        "user_id": uid,
        "username": update.effective_user.username if update.effective_user else "",
        "messages": [{"from": "user", "text": text}],
        "closed": False,
    }
    storage.save_ticket(ticket)
    await update.message.reply_text(
        f"Обращение #{tid} принято. Ожидайте ответа поддержки.",
        reply_markup=main_menu_kb(),
    )
    try:
        await context.bot.send_message(
            chat_id=config.ADMIN_TELEGRAM_ID,
            text=f"📩 Новый тикет #{tid}\nОт: {uid} (@{ticket.get('username', '')})\n\n{text}",
            reply_markup=admin_quick_reply_ticket_kb(tid),
        )
    except Exception:
        pass


async def support_reply_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пользователь нажал «Ответить на тикет» — запрашиваем текст ответа."""
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("support:reply:"):
        return
    await query.answer()
    tid = query.data.replace("support:reply:", "", 1)
    t = storage.get_ticket_by_id(tid)
    if not t or t.get("closed"):
        await query.answer("Тикет не найден или закрыт.", show_alert=True)
        return
    uid = query.from_user.id if query.from_user else 0
    if t.get("user_id") != uid:
        return
    context.user_data["waiting_support_reply_tid"] = tid
    await query.edit_message_text(
        "Напишите ваш ответ. Он будет добавлен в тикет и отправлен поддержке:",
        reply_markup=back_to_main_kb(),
    )


async def support_reply_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Текст ответа пользователя в тикет — добавляем в тикет и шлём админу с полной историей."""
    if not update.message:
        return
    tid = context.user_data.get("waiting_support_reply_tid")
    if not tid:
        return
    context.user_data.pop("waiting_support_reply_tid", None)
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Текст не получен.")
        return
    t = storage.get_ticket_by_id(tid)
    if not t or t.get("closed"):
        await update.message.reply_text("Тикет закрыт.", reply_markup=main_menu_kb())
        return
    t.setdefault("messages", []).append({"from": "user", "text": text})
    storage.save_ticket(t)
    history = []
    for m in t.get("messages", []):
        who = "Вы" if m.get("from") == "user" else "Поддержка"
        history.append(f"[{who}]: {m.get('text', '')}")
    await update.message.reply_text("Ответ отправлен в поддержку.", reply_markup=main_menu_kb())
    try:
        await context.bot.send_message(
            chat_id=config.ADMIN_TELEGRAM_ID,
            text=f"💬 Ответ по тикету #{tid} (полная переписка):\n\n" + "\n\n".join(history),
        )
    except Exception:
        pass
