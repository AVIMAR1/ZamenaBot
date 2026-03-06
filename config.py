# -*- coding: utf-8 -*-
"""Конфигурация бота."""

import os

# Telegram Bot API
# Токен обязательно должен быть задан через переменную окружения ZAMENA_BOT_TOKEN.
BOT_TOKEN = os.environ.get("ZAMENA_BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("Не задан токен бота. Установите переменную окружения ZAMENA_BOT_TOKEN.")

# ID администратора (доступ к админке)
ADMIN_TELEGRAM_ID = int(os.environ.get("ZAMENA_ADMIN_ID", "1413959305"))

# Папки данных (относительно корня проекта)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
REPLACEMENTS_FILE = os.path.join(DATA_DIR, "replacements.json")
TICKETS_FILE = os.path.join(DATA_DIR, "tickets.json")
USER_IDS_FILE = os.path.join(DATA_DIR, "user_ids.txt")
CATALOG_FILE = os.path.join(DATA_DIR, "catalog.json")

# Справочники по умолчанию: город → компания → объект → позиции
DEFAULT_CATALOG = {
    "Гродно": {
        "Wildberies": {
            "СЦ Суворова, 298": [
                "Предсортировка", "Сортировка", "Почасовая",
                "Заклейщик коробок", "Маркет", "Переупаковка",
                "КГТ", "Грузчики", "Браки",
            ],
        },
    },
}
SHIFT_TYPES = ["Дневная", "Ночная"]
