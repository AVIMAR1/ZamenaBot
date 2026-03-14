# ZamenaBot — бот для поиска замен

Telegram-бот для публикации и поиска замен (смен).

## Запуск локально

1. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

2. Укажите переменные окружения (Windows PowerShell пример):
   ```powershell
   $env:ZAMENA_BOT_TOKEN="ВАШ_TELEGRAM_BOT_TOKEN"
   $env:ZAMENA_ADMIN_ID="1413959305"
   ```

3. Запустите бота из папки проекта:
   ```bash
   python main.py
   ```

## Переменные окружения

- `ZAMENA_BOT_TOKEN` — токен Telegram-бота (обязателен).
- `ZAMENA_ADMIN_ID` — Telegram ID администратора (по умолчанию 1413959305).

## Публикация на GitHub

1. Инициализируйте git в папке проекта:
   ```bash
   git init
   git add .
   git commit -m "Initial commit of ZamenaBot"
   ```

2. Создайте пустой репозиторий на GitHub (через веб-интерфейс).

3. Привяжите удалённый репозиторий и запушьте:
   ```bash
   git remote add origin https://github.com/<ВАШ_ЛОГИН>/ZamenaBot.git
   git branch -M main
   git push -u origin main
   ```

Токен бота в репозиторий не попадает — он берётся только из переменной окружения.

## Развёртывание на Beget

Вариант для Python-хостинга Beget (SSH/панель):

1. Скопируйте код на Beget (через `git clone` из GitHub или загрузку архива).
2. В каталоге проекта создайте виртуальное окружение и установите зависимости:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Задайте переменные окружения для пользователя/сайта (через панель или в startup-скрипте):
   ```bash
   export ZAMENA_BOT_TOKEN="ВАШ_TELEGRAM_BOT_TOKEN"
   export ZAMENA_ADMIN_ID="1413959305"
   ```

4. Настройте автозапуск бота:
   - Либо через `cron` (перезапуск скрипта при падении),
   - Либо через системный менеджер процессов, доступный на вашем тарифе (например, `supervisord`, если Beget его поддерживает).

   Простейший вариант через `cron` (пример, запуск каждые 5 минут, если процесс не запущен, нужно адаптировать под ваш сервер):
   ```cron
   */5 * * * * cd /home/USER/ZamenaBot && /usr/bin/env -S bash -lc 'source venv/bin/activate && pgrep -f "python main.py" >/dev/null || python main.py >> bot.log 2>&1'
   ```

Убедитесь, что в firewall/настройках сервера нет ограничений по исходящим соединениям к API Telegram.

## Структура проекта

- `main.py` — точка входа
- `config.py` — токен, ID администратора, справочники (города, компании, объекты, должности)
- `storage.py` — работа с данными (пользователи, замены, тикеты)
- `keyboards.py` — inline-клавиатуры
- `data/` — данные бота:
  - `user_ids.txt` — список Telegram ID пользователей
  - `users.json` — профили
  - `replacements.json` — объявления о заменах
  - `tickets.json` — тикеты поддержки
- `bot/handlers/` — обработчики команд и кнопок

## Админ

ID администратора задаётся в `config.py` (`ADMIN_TELEGRAM_ID`). У админа доступна панель: тикеты, ответы, закрытие, просмотр пользователей.

## Настройка справочников

Базовый справочник (город -> компания -> объект -> позиции) задаётся в `config.py` в `DEFAULT_CATALOG` и при первом запуске попадает в SQLite-базу (`data/zamena.db`).
Дальше редактировать города, компании, объекты и позиции удобнее через админ-панель.
