# -*- coding: utf-8 -*-
"""Уведомления пользователям."""

from __future__ import annotations

import json

import storage
from keyboards import digest_notify_kb


def _loads_list(s: str | None) -> list:
    if not s:
        return []
    try:
        v = json.loads(s)
        return v if isinstance(v, list) else []
    except Exception:
        return []


async def notify_new_replacement(bot, replacement: dict):
    """Разослать уведомления о новой замене по фильтрам пользователей."""
    city = replacement.get("city")
    company = replacement.get("company")
    obj = replacement.get("object")
    position = replacement.get("position")
    shift_key = replacement.get("shift_key")
    shift = replacement.get("shift")
    date_text = replacement.get("date_text")
    author_id = replacement.get("author_id")

    users = storage.get_all_users()
    for uid_str, user in users.items():
        try:
            uid = int(uid_str)
        except Exception:
            continue
        if uid == author_id:
            continue
        if not user.get("notify_new_enabled"):
            continue
        # Только по объекту, на котором работает пользователь.
        if (user.get("city"), user.get("company"), user.get("object")) != (city, company, obj):
            continue

        allowed_positions = _loads_list(user.get("notify_positions"))
        allowed_shifts = _loads_list(user.get("notify_shift_keys"))
        if allowed_positions and position not in allowed_positions:
            continue
        if allowed_shifts and shift_key not in allowed_shifts:
            continue

        text = f"🆕 Новая замена: {position} | {shift}\nДата: {date_text}\n\nПерейти к списку?"
        try:
            await bot.send_message(chat_id=uid, text=text, reply_markup=digest_notify_kb())
        except Exception:
            continue

