# -*- coding: utf-8 -*-
"""Отзывы: оценка 1–5, текст, редактирование, просмотр, лайки/дизлайки."""

from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import storage
from keyboards import (
    main_menu_kb,
    reviews_main_kb,
    review_rating_kb,
    reviews_list_kb,
    review_detail_kb,
    back_to_main_kb,
)


async def menu_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "menu:reviews":
        return
    await query.answer()
    uid = query.from_user.id if query.from_user else 0
    existing = storage.get_review_by_user(uid)
    count = storage.get_reviews_count()
    avg = storage.get_reviews_avg_rating()
    text = f"⭐ Отзывы\n\nСредняя оценка: {avg:.1f} ({count} отзывов)."
    await query.edit_message_text(text, reply_markup=reviews_main_kb(bool(existing)))


async def review_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.data != "review:add":
        return
    await query.answer()
    context.user_data.pop("review_rating", None)
    context.user_data.pop("review_edit_id", None)
    await query.edit_message_text("Поставьте оценку от 1 до 5 звёзд:", reply_markup=review_rating_kb())


async def review_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("review:rate:"):
        return
    await query.answer()
    try:
        rating = int(query.data.replace("review:rate:", "", 1))
    except ValueError:
        return
    if rating < 1 or rating > 5:
        return
    uid = query.from_user.id if query.from_user else 0
    context.user_data["review_rating"] = rating
    existing = storage.get_review_by_user(uid)
    if existing:
        context.user_data["review_edit_id"] = existing["id"]
    context.user_data["waiting_review_text"] = True
    await query.edit_message_text(
        "Напишите текст отзыва (можно будет отредактировать позже):",
        reply_markup=back_to_main_kb(),
    )


async def review_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not context.user_data.get("waiting_review_text"):
        return
    context.user_data.pop("waiting_review_text", None)
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Текст не получен. Попробуйте снова.")
        return
    uid = update.effective_user.id if update.effective_user else 0
    rating = context.user_data.pop("review_rating", 3)
    edit_id = context.user_data.pop("review_edit_id", None)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    user = storage.get_user(uid) or {}
    username = user.get("username") or (update.effective_user.username if update.effective_user else "")
    if edit_id:
        review = storage.get_review_by_id(edit_id)
        if review and str(review.get("user_id")) == str(uid):
            review["rating"] = rating
            review["text"] = text
            review["updated_at"] = now
            storage.save_review(review)
    else:
        review = {
            "user_id": uid,
            "username": username,
            "rating": rating,
            "text": text,
            "admin_reply": None,
            "created_at": now,
            "updated_at": now,
        }
        storage.save_review(review)
    await update.message.reply_text("Спасибо! Отзыв сохранён.", reply_markup=main_menu_kb())


async def review_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return
    data = query.data
    order = context.user_data.get("review_list_order", "recent")
    page = context.user_data.get("review_list_page", 0)
    if data == "review:list":
        page = 0
    elif data.startswith("review:order:"):
        order = data.replace("review:order:", "", 1)
        page = 0
        context.user_data["review_list_order"] = order
    elif data.startswith("review:page:"):
        parts = data.replace("review:page:", "", 1).split(":")
        if len(parts) >= 1:
            try:
                page = int(parts[0])
                if len(parts) >= 2:
                    order = parts[1]
            except ValueError:
                pass
        context.user_data["review_list_page"] = page
    else:
        return
    await query.answer()
    context.user_data["review_list_order"] = order
    context.user_data["review_list_page"] = page
    total = storage.get_reviews_count()
    per_page = 5
    reviews = storage.get_reviews(order=order, limit=per_page, offset=page * per_page)
    if not reviews and total == 0:
        await query.edit_message_text(
            "Пока нет отзывов.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="menu:reviews")]]),
        )
        return
    if not reviews:
        await query.answer("Нет данных на этой странице.", show_alert=True)
        return
    text = f"Отзывы (сортировка: {order}, стр. {page + 1}). Средняя оценка: {storage.get_reviews_avg_rating():.1f}"
    await query.edit_message_text(
        text,
        reply_markup=reviews_list_kb(reviews, order, page, total, per_page),
    )


async def review_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("review:detail:"):
        return
    await query.answer()
    try:
        review_id = int(query.data.replace("review:detail:", "", 1))
    except ValueError:
        return
    rev = storage.get_review_by_id(review_id)
    if not rev:
        await query.answer("Отзыв не найден.", show_alert=True)
        return
    uid = query.from_user.id if query.from_user else 0
    user_like = storage.get_review_reaction(review_id, uid)
    lines = [
        f"⭐ {rev.get('rating', 0)}/5",
        f"{(rev.get('text') or '—')}",
        f"\n👍 Полезно: {rev.get('likes', 0)}  👎 Бесполезно: {rev.get('dislikes', 0)}",
    ]
    if rev.get("admin_reply"):
        lines.append(f"\n💬 Ответ поддержки:\n{rev['admin_reply']}")
    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=review_detail_kb(review_id, user_like),
    )


async def review_like(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("review:like:"):
        return
    await query.answer()
    try:
        review_id = int(query.data.replace("review:like:", "", 1))
    except ValueError:
        return
    uid = query.from_user.id if query.from_user else 0
    current = storage.get_review_reaction(review_id, uid)
    value = 0 if current == 1 else 1
    storage.set_review_reaction(review_id, uid, value)
    rev = storage.get_review_by_id(review_id)
    if not rev:
        return
    user_like = storage.get_review_reaction(review_id, uid)
    lines = [
        f"⭐ {rev.get('rating', 0)}/5",
        f"{(rev.get('text') or '—')}",
        f"\n👍 Полезно: {rev.get('likes', 0)}  👎 Бесполезно: {rev.get('dislikes', 0)}",
    ]
    if rev.get("admin_reply"):
        lines.append(f"\n💬 Ответ поддержки:\n{rev['admin_reply']}")
    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=review_detail_kb(review_id, user_like),
    )


async def review_dislike(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("review:dislike:"):
        return
    await query.answer()
    try:
        review_id = int(query.data.replace("review:dislike:", "", 1))
    except ValueError:
        return
    uid = query.from_user.id if query.from_user else 0
    current = storage.get_review_reaction(review_id, uid)
    value = 0 if current == -1 else -1
    storage.set_review_reaction(review_id, uid, value)
    rev = storage.get_review_by_id(review_id)
    if not rev:
        return
    user_like = storage.get_review_reaction(review_id, uid)
    lines = [
        f"⭐ {rev.get('rating', 0)}/5",
        f"{(rev.get('text') or '—')}",
        f"\n👍 Полезно: {rev.get('likes', 0)}  👎 Бесполезно: {rev.get('dislikes', 0)}",
    ]
    if rev.get("admin_reply"):
        lines.append(f"\n💬 Ответ поддержки:\n{rev['admin_reply']}")
    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=review_detail_kb(review_id, user_like),
    )
