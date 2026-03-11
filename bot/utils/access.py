# -*- coding: utf-8 -*-
"""Проверка доступа к объекту по членству в чатах/каналах."""

from __future__ import annotations

from typing import Tuple

import storage


def _is_active_member(status: str | None) -> bool:
    return status in {"member", "administrator", "creator"}


async def check_object_access(bot, user_id: int, city: str, company: str, obj: str) -> Tuple[bool, str]:
    """
    Возвращает (ok, reason).
    Правила берутся из object_access/object_access_chats.
    """
    acc = storage.get_object_access(city, company, obj) or {}
    chats = acc.get("chats") or []
    require_mode = (acc.get("require_mode") or "ANY").upper()

    if not chats:
        return True, ""

    results = []
    for chat_id in chats:
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            results.append(_is_active_member(getattr(member, "status", None)))
        except Exception:
            results.append(False)

    if require_mode == "ALL":
        ok = all(results)
    else:
        ok = any(results)

    if ok:
        return True, ""
    mode_text = "всех" if require_mode == "ALL" else "хотя бы одного"
    return False, f"Для этого объекта нужно состоять в {mode_text} чате/канале из списка."

