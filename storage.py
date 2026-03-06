# -*- coding: utf-8 -*-
"""Хранение данных — использует SQLite (database) и user_ids.txt."""

import os

import config

# Импортируем всё из database
from database import (
    get_user,
    save_user,
    get_all_users,
    get_replacements,
    get_replacement_by_id,
    save_replacement,
    get_my_replacements,
    get_my_responses,
    get_tickets,
    get_ticket_by_id,
    save_ticket,
    get_cities,
    get_companies,
    get_objects,
    get_positions,
    catalog_add_city,
    catalog_remove_city,
    catalog_add_company,
    catalog_add_object,
    catalog_add_position,
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
    get_review_reaction,
    set_review_reaction,
    get_banned_support_users,
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
