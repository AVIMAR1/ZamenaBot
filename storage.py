# -*- coding: utf-8 -*-
"""Хранение данных — использует SQLite (database) и user_ids.txt."""

import os

import config

# Импортируем всё из database
from database import (
    get_user,
    save_user,
    get_all_users,
    get_users_page,
    reset_all_users,
    get_replacements,
    get_replacement_by_id,
    save_replacement,
    update_replacement_usernames,
    repair_all_replacement_usernames,
    get_my_replacements,
    get_my_responses,
    get_tickets,
    get_ticket_by_id,
    save_ticket,
    get_cities,
    get_companies,
    get_objects,
    get_positions,
    get_all_positions,
    catalog_add_city,
    catalog_rename_city,
    catalog_remove_city,
    catalog_add_company,
    catalog_rename_company,
    catalog_add_object,
    catalog_rename_object,
    catalog_add_position,
    catalog_rename_position,
    catalog_remove_company,
    catalog_remove_object,
    catalog_remove_position,
    get_object_shift,
    set_object_shift,
    get_object_shifts_for_object,
    get_review_by_user,
    save_review,
    get_reviews,
    get_reviews_count,
    get_reviews_avg_rating,
    get_review_by_id,
    delete_review,
    get_review_reaction,
    set_review_reaction,
    get_banned_support_users,
    # Supervisors
    get_supervisors,
    add_supervisor,
    delete_supervisor,
    get_supervisor_by_id,
    update_supervisor_username,
    update_supervisor,
    # Object access
    get_object_access,
    set_object_access_mode,
    add_object_access_chat,
    remove_object_access_chat,
    # Friends
    add_friend,
    remove_friend,
    get_friends,
    # Offers
    save_offer,
    get_offers,
    get_offer_by_id,
    deactivate_offer,
    get_my_offers,
)


def sync_replacement_usernames(replacement: dict):
    """Подтянуть username полей из users для замены и обновить запись."""
    rid = replacement.get("id")
    if not rid:
        return
    author_id = replacement.get("author_id")
    requested_by_id = replacement.get("requested_by_id")
    taken_by_id = replacement.get("taken_by_id")
    author_username = None
    requested_username = None
    taken_username = None
    if author_id:
        u = get_user(int(author_id))
        author_username = (u.get("username") if u else "") or ""
    if requested_by_id:
        u = get_user(int(requested_by_id))
        requested_username = (u.get("username") if u else "") or ""
    if taken_by_id:
        u = get_user(int(taken_by_id))
        taken_username = (u.get("username") if u else "") or ""
    update_replacement_usernames(
        str(rid),
        author_username=author_username,
        requested_by_username=requested_username,
        taken_by_username=taken_username,
    )


def add_user_id(telegram_id: int):
    """Добавить Telegram ID в файл user_ids.txt."""
    os.makedirs(config.DATA_DIR, exist_ok=True)
    path = config.USER_IDS_FILE
    existing = set()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.isdigit():
                    existing.add(int(line))
    if telegram_id in existing:
        return
    existing.add(telegram_id)
    with open(path, "w", encoding="utf-8") as f:
        for uid in sorted(existing):
            f.write(str(uid) + "\n")
