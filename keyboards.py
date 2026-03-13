# -*- coding: utf-8 -*-
"""Клавиатуры бота — компактные inline-кнопки."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import json

import storage


def chunks(lst, n):
    return [lst[i : i + n] for i in range(0, len(lst), n)]


def city_kb():
    cities = storage.get_cities()
    rows = chunks(
        [InlineKeyboardButton(c, callback_data=f"city:{c}") for c in cities], 2
    )
    return InlineKeyboardMarkup(rows)


def company_kb(city: str):
    companies = storage.get_companies(city)
    rows = chunks(
        [InlineKeyboardButton(c, callback_data=f"company:{city}:{i}") for i, c in enumerate(companies)],
        2,
    )
    return InlineKeyboardMarkup(rows)


def objects_kb(city: str, company: str):
    objs = storage.get_objects(city, company)
    rows = chunks(
        [InlineKeyboardButton(o, callback_data=f"obj:{city}:{company}:{i}") for i, o in enumerate(objs)],
        2,
    )
    return InlineKeyboardMarkup(rows)


def positions_kb(city: str, company: str, object_name: str):
    positions = storage.get_positions(city, company, object_name)
    rows = chunks(
        [InlineKeyboardButton(p, callback_data=f"pos:{i}") for i, p in enumerate(positions)],
        2,
    )
    rows.append([InlineKeyboardButton("« Назад", callback_data="back:main")])
    return InlineKeyboardMarkup(rows)


def main_menu_kb():
    """Главное меню пользователя."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Мне нужна замена", callback_data="act:find")],
        [
            InlineKeyboardButton("👤 Профиль", callback_data="menu:profile"),
            InlineKeyboardButton("⚙️ Настройки", callback_data="menu:settings"),
        ],
        [InlineKeyboardButton("⭐ Отзывы", callback_data="menu:reviews")],
        [InlineKeyboardButton("💬 Поддержка", callback_data="menu:support")],
    ])


def shift_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Дневная", callback_data="shift:day")],
        [InlineKeyboardButton("Ночная", callback_data="shift:night")],
        [InlineKeyboardButton("🙋 Готовы выйти на замену", callback_data="offers:menu")],
        [InlineKeyboardButton("« Назад", callback_data="back:main")],
    ])


def calendar_month_kb(year: int, month: int, shift_key: str, pos_idx: int, single: int, step: int = 0):
    """shift_key: day|night, pos_idx: индекс в POSITIONS, single: 1 день/0 два, step: 0=дата нач, 1=дата конец."""
    import calendar
    from datetime import datetime

    cal = calendar.Calendar(firstweekday=0)
    days = list(cal.itermonthdays(year, month))
    header = [InlineKeyboardButton(f"{year} / {month}", callback_data="noop")]

    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    header_row = [InlineKeyboardButton(d, callback_data="noop") for d in weekdays]
    rows = [header, header_row]

    row = []
    now = datetime.now()
    for d in days:
        if d == 0:
            row.append(InlineKeyboardButton(" ", callback_data="noop"))
        else:
            # В текущем месяце прошлые дни делаем неактивными визуально.
            if year == now.year and month == now.month and d < now.day:
                row.append(InlineKeyboardButton(str(d), callback_data="noop"))
            else:
                cb = f"date:{year}:{month}:{d}:{shift_key}:{pos_idx}:{single}:{step}"
                row.append(InlineKeyboardButton(str(d), callback_data=cb))
        if len(row) == 7:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    nav = []

    # Ограничиваем навигацию календаря: текущий месяц и пара месяцев вперёд.
    now = datetime.now()
    min_year, min_month = now.year, now.month
    # Максимум на 2 месяца вперёд
    if now.month <= 10:
        max_year, max_month = now.year, now.month + 2
    else:
        # Переход через год
        max_year = now.year + 1
        max_month = (now.month + 2) - 12

    if (year, month) > (min_year, min_month):
        prev_year, prev_month = year, month - 1
        if prev_month == 0:
            prev_year -= 1
            prev_month = 12
        nav.append(InlineKeyboardButton("◀", callback_data=f"cal:{prev_year}:{prev_month}:{shift_key}:{pos_idx}:{single}:{step}"))

    nav.append(InlineKeyboardButton("« Назад", callback_data="back:main"))

    if (year, month) < (max_year, max_month):
        next_year, next_month = year, month + 1
        if next_month == 13:
            next_year += 1
            next_month = 1
        nav.append(InlineKeyboardButton("▶", callback_data=f"cal:{next_year}:{next_month}:{shift_key}:{pos_idx}:{single}:{step}"))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def admin_calendar_kb(year: int, month: int, prefix: str = "admincal"):
    """Простой календарь для админских сценариев. prefix задаёт callback."""
    import calendar
    from datetime import datetime

    cal = calendar.Calendar(firstweekday=0)
    days = list(cal.itermonthdays(year, month))
    header = [InlineKeyboardButton(f"{year} / {month}", callback_data="noop")]
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    header_row = [InlineKeyboardButton(d, callback_data="noop") for d in weekdays]
    rows = [header, header_row]

    row = []
    now = datetime.now()
    for d in days:
        if d == 0:
            row.append(InlineKeyboardButton(" ", callback_data="noop"))
        else:
            if year == now.year and month == now.month and d < now.day:
                row.append(InlineKeyboardButton(str(d), callback_data="noop"))
            else:
                iso = f"{year:04d}-{month:02d}-{d:02d}"
                row.append(InlineKeyboardButton(str(d), callback_data=f"{prefix}:date:{iso}"))
        if len(row) == 7:
            rows.append(row)
            row = []
    if row:
        while len(row) < 7:
            row.append(InlineKeyboardButton(" ", callback_data="noop"))
        rows.append(row)

    # nav
    y, m = year, month
    prev_y, prev_m = (y - 1, 12) if m == 1 else (y, m - 1)
    next_y, next_m = (y + 1, 1) if m == 12 else (y, m + 1)
    rows.append([
        InlineKeyboardButton("◀", callback_data=f"{prefix}:nav:{prev_y:04d}-{prev_m:02d}"),
        InlineKeyboardButton("▶", callback_data=f"{prefix}:nav:{next_y:04d}-{next_m:02d}"),
    ])
    rows.append([InlineKeyboardButton("« Назад", callback_data="admin:back")])
    return InlineKeyboardMarkup(rows)


def confirm_create_kb(rid: str, is_edit: bool = False):
    if is_edit:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Обновить", callback_data=f"update:{rid}")],
            [InlineKeyboardButton("💰 Доплата", callback_data=f"reppay:toggle:{rid}")],
            [InlineKeyboardButton("« Отмена", callback_data="back:main")],
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Опубликовать", callback_data=f"publish:{rid}")],
        [InlineKeyboardButton("💰 Доплата", callback_data=f"reppay:toggle:{rid}")],
        [InlineKeyboardButton("« Отмена", callback_data="back:main")],
    ])


def replacement_pay_kb(rid: str, enabled: bool, amount: float | None):
    label = "💰 Доплата: включена" if enabled else "💰 Доплата: выключена"
    amount_label = f"Сумма: {amount} BYN" if amount else "Сумма: —"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"reppay:toggle:{rid}")],
        [InlineKeyboardButton(amount_label + " (ввести)", callback_data=f"reppay:set:{rid}")],
        [InlineKeyboardButton("« Назад", callback_data=f"reppay:back:{rid}")],
    ])


def replacements_list_kb(replacements: list, page: int = 0, per_page: int = 5):
    start = page * per_page
    chunk = replacements[start : start + per_page]
    rows = []
    from datetime import date, timedelta

    for r in chunk:
        rid = r.get("id", "")
        # В списке: сначала позиция, потом смена, потом дата.
        date_from = r.get("date_from")
        human_date = r.get("date_text", "")
        d = None
        if date_from:
            try:
                d = date.fromisoformat(date_from)
            except Exception:
                d = None
        if d:
            today = date.today()
            if d == today:
                human_date = "Сегодня"
            elif d == today + timedelta(days=1):
                human_date = "Завтра"
        short = f"{r.get('position', '')} | {r.get('shift', '')} | {human_date}"
        if len(short) > 50:
            short = short[:47] + "..."
        rows.append([InlineKeyboardButton(short, callback_data=f"take:{rid}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀", callback_data=f"replist:{page-1}"))
    nav.append(InlineKeyboardButton("« В меню", callback_data="back:main"))
    if start + per_page < len(replacements):
        nav.append(InlineKeyboardButton("▶", callback_data=f"replist:{page+1}"))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def take_confirm_kb(rid: str):
    """Кто хочет принять — подтвердить заявку."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Хочу заменить", callback_data=f"confirm_take:{rid}")],
        [InlineKeyboardButton("❌ Отмена", callback_data="back:main")],
    ])


def offers_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Список замен", callback_data="replace:list")],
        [InlineKeyboardButton("➕ Предложить выйти на замену", callback_data="offers:create")],
        [InlineKeyboardButton("🙋 Готовы выйти на замену (список)", callback_data="offers:list")],
        [InlineKeyboardButton("📌 Мои предложения", callback_data="offers:mine")],
        [InlineKeyboardButton("« В меню", callback_data="back:main")],
    ])


def offer_shift_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Дневная", callback_data="offer:shift:day")],
        [InlineKeyboardButton("Ночная", callback_data="offer:shift:night")],
        [InlineKeyboardButton("« Назад", callback_data="offers:menu")],
    ])


def offer_calendar_kb(year: int, month: int, shift_key: str, single: int, step: int = 0):
    """Календарь для offers. callback: offerdate:YYYY:MM:DD:shift:single:step"""
    import calendar
    from datetime import datetime

    cal = calendar.Calendar(firstweekday=0)
    days = list(cal.itermonthdays(year, month))
    header = [InlineKeyboardButton(f"{year} / {month}", callback_data="noop")]

    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    header_row = [InlineKeyboardButton(d, callback_data="noop") for d in weekdays]
    rows = [header, header_row]

    row = []
    now = datetime.now()
    for d in days:
        if d == 0:
            row.append(InlineKeyboardButton(" ", callback_data="noop"))
        else:
            if year == now.year and month == now.month and d < now.day:
                row.append(InlineKeyboardButton(str(d), callback_data="noop"))
            else:
                cb = f"offerdate:{year}:{month}:{d}:{shift_key}:{single}:{step}"
                row.append(InlineKeyboardButton(str(d), callback_data=cb))
        if len(row) == 7:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    nav = []
    # текущий месяц и 2 вперёд
    min_year, min_month = now.year, now.month
    if now.month <= 10:
        max_year, max_month = now.year, now.month + 2
    else:
        max_year = now.year + 1
        max_month = (now.month + 2) - 12
    if (year, month) > (min_year, min_month):
        prev_year, prev_month = year, month - 1
        if prev_month == 0:
            prev_year -= 1
            prev_month = 12
        nav.append(InlineKeyboardButton("◀", callback_data=f"offercal:{prev_year}:{prev_month}:{shift_key}:{single}:{step}"))
    nav.append(InlineKeyboardButton("« Назад", callback_data="offers:menu"))
    if (year, month) < (max_year, max_month):
        next_year, next_month = year, month + 1
        if next_month == 13:
            next_year += 1
            next_month = 1
        nav.append(InlineKeyboardButton("▶", callback_data=f"offercal:{next_year}:{next_month}:{shift_key}:{single}:{step}"))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def offers_list_kb(offers: list, page: int = 0, per_page: int = 5):
    start = page * per_page
    chunk = offers[start : start + per_page]
    rows = []
    for o in chunk:
        oid = o.get("id", "")
        date_text = o.get("date_text") or ""
        shift = "Дневная" if o.get("shift_key") == "day" else "Ночная"
        try:
            pos = json.loads(o.get("positions_json") or "[]")
            if not isinstance(pos, list):
                pos = []
        except Exception:
            pos = []
        pos_text = ", ".join(pos[:2]) + ("…" if len(pos) > 2 else "")
        label = f"{shift} | {date_text} | {pos_text or '—'}"
        if len(label) > 55:
            label = label[:52] + "..."
        rows.append([InlineKeyboardButton(label, callback_data=f"noop")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀", callback_data=f"offersp:{page-1}"))
    nav.append(InlineKeyboardButton("« Назад", callback_data="offers:menu"))
    if start + per_page < len(offers):
        nav.append(InlineKeyboardButton("▶", callback_data=f"offersp:{page+1}"))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def offer_positions_kb(pending: dict):
    uid = pending.get("author_id")
    user = storage.get_user(int(uid)) if uid else {}
    positions = storage.get_positions(user.get("city"), user.get("company"), user.get("object")) if user else []
    selected = set(pending.get("positions") or [])
    rows = []
    for i, p in enumerate(positions[:40]):
        mark = "✅" if p in selected else "☑️"
        rows.append([InlineKeyboardButton(f"{mark} {p}", callback_data=f"offerpos:toggle:{i}")])
    rows.append([InlineKeyboardButton("✅ Готово", callback_data="offerpos:done")])
    rows.append([InlineKeyboardButton("❌ Отмена", callback_data="offers:menu")])
    return InlineKeyboardMarkup(rows)


def offer_confirm_kb(oid: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Опубликовать", callback_data=f"offerpub:{oid}")],
        [InlineKeyboardButton("💰 Доплата", callback_data=f"offerpay:toggle:{oid}")],
        [InlineKeyboardButton("❌ Отмена", callback_data="offers:menu")],
    ])


def offer_pay_kb(oid: str, enabled: bool, amount: float | None):
    label = "💰 Доплата: включена" if enabled else "💰 Доплата: выключена"
    amount_label = f"Сумма: {amount} BYN" if amount else "Сумма: —"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"offerpay:toggle:{oid}")],
        [InlineKeyboardButton(amount_label + " (ввести)", callback_data=f"offerpay:set:{oid}")],
        [InlineKeyboardButton("« Назад", callback_data=f"offerpay:back:{oid}")],
    ])


def my_offers_kb(offers: list):
    rows = []
    for o in offers[:20]:
        oid = o.get("id", "")
        date_text = o.get("date_text") or ""
        shift = "Дневная" if o.get("shift_key") == "day" else "Ночная"
        rows.append([InlineKeyboardButton(f"🗑 {shift} | {date_text}", callback_data=f"offer:off:{oid}")])
    rows.append([InlineKeyboardButton("« Назад", callback_data="offers:menu")])
    return InlineKeyboardMarkup(rows)


def creator_decide_kb(rid: str):
    """У автора: принять или отклонить заявку."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Принять", callback_data=f"creator_accept:{rid}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"creator_reject:{rid}")],
    ])


def taker_wait_kb(rid: str):
    """У того, кто подал заявку — ждём решения автора, можно отказаться."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("↩️ Отозвать заявку", callback_data=f"taker_refuse:{rid}")],
    ])


def replace_done_kb(rid: str, is_creator: bool):
    """После подтверждения: автор — отменить, принявший — отказаться."""
    if is_creator:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("↩️ Отменить подтверждение", callback_data=f"undo_confirm:{rid}")],
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("↩️ Отказаться от замены", callback_data=f"taker_refuse:{rid}")],
    ])


def profile_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Мои объявления", callback_data="menu:my_ads")],
        [InlineKeyboardButton("📩 Мои отклики", callback_data="menu:my_responses")],
        [InlineKeyboardButton("👥 Друзья", callback_data="menu:friends")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="menu:settings")],
        [InlineKeyboardButton("« В меню", callback_data="back:main")],
    ])


def friends_manage_kb(friends: list):
    rows = []
    for u in friends[:20]:
        uid = u.get("telegram_id")
        fn = u.get("full_name") or u.get("name") or f"ID {uid}"
        short = fn if len(fn) <= 35 else fn[:32] + "..."
        rows.append([InlineKeyboardButton(f"🗑 {short}", callback_data=f"friends:remove:{uid}")])
    rows.append([InlineKeyboardButton("➕ Добавить друга", callback_data="friends:add")])
    rows.append([InlineKeyboardButton("« Назад", callback_data="menu:profile")])
    return InlineKeyboardMarkup(rows)


def settings_kb(notify_enabled: bool):
    """Настройки: редактировать профиль и вкл/выкл уведомления о заменах."""
    label = "🔕 Отключить уведомления" if notify_enabled else "🔔 Включить уведомления"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Редактировать профиль", callback_data="settings:edit_profile")],
        [InlineKeyboardButton(label, callback_data="settings:toggle_notify")],
        [InlineKeyboardButton("🆕 Уведомления о новых заменах", callback_data="settings:notify_new")],
        [InlineKeyboardButton("« Назад", callback_data="back:main")],
    ])


def notify_new_kb(enabled: bool):
    status = "включены" if enabled else "отключены"
    toggle = "🔕 Выключить" if enabled else "🔔 Включить"
    rows = [
        [InlineKeyboardButton(f"Статус: {status}", callback_data="noop")],
        [InlineKeyboardButton(toggle, callback_data="notifynew:toggle")],
    ]
    if enabled:
        rows.append([InlineKeyboardButton("🎯 Позиции", callback_data="notifynew:positions")])
        rows.append([InlineKeyboardButton("🕒 Смены", callback_data="notifynew:shifts")])
    rows.append([InlineKeyboardButton("« Назад", callback_data="menu:settings")])
    return InlineKeyboardMarkup(rows)


def notify_new_positions_kb(positions: list, selected: set[str]):
    rows = []
    for i, p in enumerate(positions[:40]):
        mark = "✅" if p in selected else "☑️"
        rows.append([InlineKeyboardButton(f"{mark} {p}", callback_data=f"notifypos:toggle:{i}")])
    rows.append([InlineKeyboardButton("Очистить (все позиции)", callback_data="notifypos:clear")])
    rows.append([InlineKeyboardButton("« Назад", callback_data="settings:notify_new")])
    return InlineKeyboardMarkup(rows)


def notify_new_shifts_kb(selected: set[str]):
    def row(label: str, key: str):
        mark = "✅" if key in selected else "☑️"
        return [InlineKeyboardButton(f"{mark} {label}", callback_data=f"notifyshift:toggle:{key}")]

    rows = [
        row("Дневная", "day"),
        row("Ночная", "night"),
        [InlineKeyboardButton("Очистить (все смены)", callback_data="notifyshift:clear")],
        [InlineKeyboardButton("« Назад", callback_data="settings:notify_new")],
    ]
    return InlineKeyboardMarkup(rows)


def my_responses_kb(responses: list, page: int = 0, per_page: int = 5):
    start = page * per_page
    chunk = responses[start : start + per_page]
    rows = []
    from datetime import date, timedelta
    for r in chunk:
        rid = r.get("id", "")
        date_from = r.get("date_from")
        human_date = r.get("date_text", "")
        try:
            d = date.fromisoformat(date_from) if date_from else None
        except Exception:
            d = None
        if d:
            today = date.today()
            human_date = "Сегодня" if d == today else ("Завтра" if d == today + timedelta(days=1) else r.get("date_text", ""))
        status = "✅" if r.get("confirmed") else "⏳"
        short = f"{status} {r.get('position', '')} | {human_date}"
        if len(short) > 40:
            short = short[:37] + "..."
        rows.append([InlineKeyboardButton(short, callback_data=f"myresp:{rid}")])
    nav = [InlineKeyboardButton("« К профилю", callback_data="menu:profile")]
    if page > 0:
        nav.insert(0, InlineKeyboardButton("◀", callback_data=f"myrespp:{page-1}"))
    if start + per_page < len(responses):
        nav.append(InlineKeyboardButton("▶", callback_data=f"myrespp:{page+1}"))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def my_response_detail_kb(rid: str, can_refuse: bool):
    """can_refuse: можно отозвать заявку или отказаться от замены."""
    rows = []
    if can_refuse:
        rows.append([InlineKeyboardButton("↩️ Отозвать заявку / Отказаться", callback_data=f"taker_refuse:{rid}")])
    rows.append([InlineKeyboardButton("« К откликам", callback_data="menu:my_responses")])
    return InlineKeyboardMarkup(rows)


def my_ads_kb(ads: list, page: int = 0, per_page: int = 5):
    start = page * per_page
    chunk = ads[start : start + per_page]
    rows = []
    for r in chunk:
        rid = r.get("id", "")
        short = f"{r.get('date_text', '')} | {r.get('position', '')}"
        rows.append([InlineKeyboardButton(short, callback_data=f"myad:{rid}")])
    nav = [InlineKeyboardButton("« Назад", callback_data="menu:profile")]
    if page > 0:
        nav.insert(0, InlineKeyboardButton("◀", callback_data=f"myads:{page-1}"))
    if start + per_page < len(ads):
        nav.append(InlineKeyboardButton("▶", callback_data=f"myads:{page+1}"))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def my_ad_actions_kb(rid: str, active: bool):
    rows = []
    if active:
        rows.append([InlineKeyboardButton("✏️ Редактировать", callback_data=f"editad:{rid}")])
        rows.append([InlineKeyboardButton("🗑 Снять с публикации", callback_data=f"deactivate:{rid}")])
    rows.append([InlineKeyboardButton("« К объявлениям", callback_data="menu:my_ads")])
    return InlineKeyboardMarkup(rows)


def support_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✉️ Написать в поддержку", callback_data="support:new")],
        [InlineKeyboardButton("« Назад", callback_data="back:main")],
    ])


def admin_main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Тикеты", callback_data="admin:tickets")],
        [InlineKeyboardButton("👥 Пользователи", callback_data="admin:users")],
        [InlineKeyboardButton("👨‍💼 Администраторы", callback_data="admin:supervisors")],
        [InlineKeyboardButton("⭐ Отзывы (модерация)", callback_data="admin:reviews")],
        [InlineKeyboardButton("♻️ Сброс пользователей", callback_data="admin:resetusers")],
        [InlineKeyboardButton("✅ Проверка объектов (чаты)", callback_data="admin:objaccess")],
        [InlineKeyboardButton("📨 Дайджест сейчас", callback_data="admin:digestnow")],
        [InlineKeyboardButton("📊 Отчёт по смене", callback_data="admin:shiftreport")],
        [InlineKeyboardButton("📂 Справочники", callback_data="admin:catalog")],
        [InlineKeyboardButton("⏰ Смены объектов", callback_data="admin:shiftcfg")],
        [
            InlineKeyboardButton("📢 Рассылка", callback_data="admin:broadcast"),
            InlineKeyboardButton("🚫 Баны поддержки", callback_data="admin:banned"),
        ],
        [InlineKeyboardButton("🚪 Выйти из админки", callback_data="admin:exit")],
    ])


def admin_reviews_list_kb(reviews: list, page: int, total: int, per_page: int = 5):
    rows = []
    start = page * per_page
    chunk = reviews[start : start + per_page]
    for r in chunk:
        rid = r.get("id")
        rating = r.get("rating", 0)
        uid = r.get("user_id")
        short = (r.get("text") or "").strip().replace("\n", " ")
        if len(short) > 30:
            short = short[:27] + "..."
        label = f"{rating}★ | {uid} | {short or '—'}"
        rows.append([InlineKeyboardButton(label, callback_data=f"admin:review:{rid}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀", callback_data=f"admin:reviewsp:{page-1}"))
    nav.append(InlineKeyboardButton("« Назад", callback_data="admin:back"))
    if start + per_page < total:
        nav.append(InlineKeyboardButton("▶", callback_data=f"admin:reviewsp:{page+1}"))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def admin_review_detail_kb(rid: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 Удалить отзыв", callback_data=f"admin:reviewdel:{rid}")],
        [InlineKeyboardButton("« К списку", callback_data="admin:reviews")],
    ])


def menu_quick_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Меню", callback_data="back:main")]])


def objaccess_cities_kb():
    cities = storage.get_cities()
    rows = [[InlineKeyboardButton(c, callback_data=f"objacc:city:{i}")] for i, c in enumerate(cities)]
    rows.append([InlineKeyboardButton("« Назад", callback_data="admin:back")])
    return InlineKeyboardMarkup(rows)


def objaccess_companies_kb(city_idx: int):
    cities = storage.get_cities()
    if city_idx < 0 or city_idx >= len(cities):
        return InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="admin:objaccess")]])
    companies = storage.get_companies(cities[city_idx])
    rows = [[InlineKeyboardButton(c, callback_data=f"objacc:company:{city_idx}:{i}")] for i, c in enumerate(companies)]
    rows.append([InlineKeyboardButton("« К городам", callback_data="admin:objaccess")])
    return InlineKeyboardMarkup(rows)


def objaccess_objects_kb(city_idx: int, company_idx: int):
    cities = storage.get_cities()
    if city_idx < 0 or city_idx >= len(cities):
        return InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="admin:objaccess")]])
    companies = storage.get_companies(cities[city_idx])
    if company_idx < 0 or company_idx >= len(companies):
        return InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data=f"objacc:city:{city_idx}")]])
    objects = storage.get_objects(cities[city_idx], companies[company_idx])
    rows = [[InlineKeyboardButton(o, callback_data=f"objacc:object:{city_idx}:{company_idx}:{i}")] for i, o in enumerate(objects)]
    rows.append([InlineKeyboardButton("« К компаниям", callback_data=f"objacc:city:{city_idx}")])
    return InlineKeyboardMarkup(rows)


def objaccess_object_kb(city_idx: int, company_idx: int, object_idx: int, require_mode: str, chats: list):
    cities = storage.get_cities()
    companies = storage.get_companies(cities[city_idx]) if 0 <= city_idx < len(cities) else []
    objects = storage.get_objects(cities[city_idx], companies[company_idx]) if 0 <= company_idx < len(companies) else []
    obj = objects[object_idx] if 0 <= object_idx < len(objects) else ""
    mode_label = "Любой" if require_mode == "ANY" else "Все"
    rows = [
        [InlineKeyboardButton(f"Режим: {mode_label} (нажать изменить)", callback_data=f"objacc:mode:{city_idx}:{company_idx}:{object_idx}")],
    ]
    for ch in chats[:20]:
        rows.append([InlineKeyboardButton(f"🗑 {ch}", callback_data=f"objacc:delchat:{city_idx}:{company_idx}:{object_idx}:{ch}")])
    rows.append([InlineKeyboardButton("➕ Добавить чат/канал", callback_data=f"objacc:addchat:{city_idx}:{company_idx}:{object_idx}")])
    rows.append([InlineKeyboardButton("« К объектам", callback_data=f"objacc:company:{city_idx}:{company_idx}")])
    return InlineKeyboardMarkup(rows)


def friends_kb(friends: list, prefix: str = "friends:choose"):
    rows = []
    for u in friends:
        uid = u.get("telegram_id")
        fn = u.get("full_name") or u.get("name") or f"ID {uid}"
        short = fn if len(fn) <= 35 else fn[:32] + "..."
        rows.append([InlineKeyboardButton(short, callback_data=f"{prefix}:{uid}")])
    rows.append([InlineKeyboardButton("« Назад", callback_data="back:main")])
    return InlineKeyboardMarkup(rows)


def friends_choose_kb(friends: list, rid: str):
    rows = []
    for u in friends:
        uid = u.get("telegram_id")
        fn = u.get("full_name") or u.get("name") or f"ID {uid}"
        short = fn if len(fn) <= 35 else fn[:32] + "..."
        rows.append([InlineKeyboardButton(short, callback_data=f"friends:choose:{rid}:{uid}")])
    rows.append([InlineKeyboardButton("❌ Отмена", callback_data=f"friends:cancel:{rid}")])
    return InlineKeyboardMarkup(rows)


def admin_banned_kb(banned: list):
    """Список забаненных: кнопка разбана по uid."""
    rows = []
    for u in banned:
        uid = u.get("telegram_id")
        until = u.get("support_ban_until") or "?"
        label = f"ID {uid} до {until}"
        if len(label) > 35:
            label = label[:32] + "..."
        rows.append([InlineKeyboardButton(f"🔓 {label}", callback_data=f"admin:unban:{uid}")])
    rows.append([InlineKeyboardButton("➕ Забанить по ID", callback_data="admin:ban_prompt")])
    rows.append([InlineKeyboardButton("« Назад", callback_data="admin:back")])
    return InlineKeyboardMarkup(rows)


def admin_catalog_cities_kb():
    cities = storage.get_cities()
    rows = [[InlineKeyboardButton(c, callback_data=f"cat:city:{i}")] for i, c in enumerate(cities)]
    rows.append([InlineKeyboardButton("➕ Добавить город", callback_data="cat:addcity")])
    rows.append([InlineKeyboardButton("« Назад", callback_data="admin:back")])
    return InlineKeyboardMarkup(rows)


def admin_catalog_city_menu_kb(city_idx: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏢 Компании", callback_data=f"cat:companies:{city_idx}")],
        [InlineKeyboardButton("📍 Объекты", callback_data=f"cat:objselect:{city_idx}")],
        [InlineKeyboardButton("👤 Позиции", callback_data=f"cat:posselect:{city_idx}")],
        [InlineKeyboardButton("✏️ Переименовать город", callback_data=f"cat:ren:city:{city_idx}")],
        [InlineKeyboardButton("🗑 Удалить город", callback_data=f"cat:delcity:{city_idx}")],
        [InlineKeyboardButton("« К городам", callback_data="admin:catalog")],
    ])


def admin_catalog_select_company_kb(city_idx: int, prefix: str):
    """prefix: obj или pos — для объектов или позиций."""
    cities = storage.get_cities()
    if city_idx >= len(cities):
        return InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="admin:catalog")]])
    companies = storage.get_companies(cities[city_idx])
    pref = "objectlist" if prefix == "obj" else "posobj"
    rows = [[InlineKeyboardButton(c, callback_data=f"cat:{pref}:{city_idx}:{i}")] for i, c in enumerate(companies)]
    rows.append([InlineKeyboardButton("« Назад", callback_data=f"cat:city:{city_idx}")])
    return InlineKeyboardMarkup(rows)


def admin_catalog_select_object_kb(city_idx: int, company_idx: int):
    cities = storage.get_cities()
    if city_idx >= len(cities):
        return InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="admin:catalog")]])
    companies = storage.get_companies(cities[city_idx])
    if company_idx >= len(companies):
        return InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data=f"cat:posselect:{city_idx}")]])
    objects = storage.get_objects(cities[city_idx], companies[company_idx])
    rows = [[InlineKeyboardButton(o, callback_data=f"cat:positionlist:{city_idx}:{company_idx}:{i}")] for i, o in enumerate(objects)]
    rows.append([InlineKeyboardButton("« Назад", callback_data=f"cat:posselect:{city_idx}")])
    return InlineKeyboardMarkup(rows)


def admin_catalog_list_kb(city_idx: int, kind: str, items: list, company_idx: int = -1, object_idx: int = -1):
    rows = []
    if kind == "companies":
        for i, name in enumerate(items):
            short = name[:25] + "…" if len(name) > 25 else name
            rows.append([
                InlineKeyboardButton(f"✏️ {short}", callback_data=f"cat:ren:company:{city_idx}:{i}"),
                InlineKeyboardButton("🗑", callback_data=f"cat:del:companies:{city_idx}:{i}"),
            ])
        rows.append([InlineKeyboardButton("➕ Добавить", callback_data=f"cat:add:companies:{city_idx}")])
    elif kind == "objects":
        for i, name in enumerate(items):
            short = name[:25] + "…" if len(name) > 25 else name
            rows.append([
                InlineKeyboardButton(f"✏️ {short}", callback_data=f"cat:ren:object:{city_idx}:{company_idx}:{i}"),
                InlineKeyboardButton("🗑", callback_data=f"cat:del:objects:{city_idx}:{company_idx}:{i}"),
            ])
        rows.append([InlineKeyboardButton("➕ Добавить", callback_data=f"cat:add:objects:{city_idx}:{company_idx}")])
    else:
        for i, name in enumerate(items):
            short = name[:25] + "…" if len(name) > 25 else name
            rows.append([
                InlineKeyboardButton(f"✏️ {short}", callback_data=f"cat:ren:pos:{city_idx}:{company_idx}:{object_idx}:{i}"),
                InlineKeyboardButton("🗑", callback_data=f"cat:del:positions:{city_idx}:{company_idx}:{object_idx}:{i}"),
            ])
        rows.append([InlineKeyboardButton("➕ Добавить", callback_data=f"cat:add:positions:{city_idx}:{company_idx}:{object_idx}")])
    rows.append([InlineKeyboardButton("« Назад", callback_data=f"cat:city:{city_idx}")])
    return InlineKeyboardMarkup(rows)


def admin_tickets_kb(closed: bool = False):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Открытые", callback_data="admin:tickets:open")],
        [InlineKeyboardButton("Закрытые", callback_data="admin:tickets:closed")],
        [InlineKeyboardButton("« Назад", callback_data="admin:back")],
    ])


def ticket_list_kb(tickets: list, page: int = 0, per_page: int = 5, prefix: str = "admin:t"):
    start = page * per_page
    chunk = tickets[start : start + per_page]
    rows = []
    for t in chunk:
        tid = t.get("id", "")
        short = f"#{tid[:6]} | {t.get('user_id', '')}"
        rows.append([InlineKeyboardButton(short, callback_data=f"{prefix}:{tid}")])
    nav = [InlineKeyboardButton("« Назад", callback_data="admin:tickets")]
    if page > 0:
        nav.insert(0, InlineKeyboardButton("◀", callback_data=f"{prefix}list:{page-1}"))
    if start + per_page < len(tickets):
        nav.append(InlineKeyboardButton("▶", callback_data=f"{prefix}list:{page+1}"))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def ticket_actions_kb(tid: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Ответить", callback_data=f"admin:reply:{tid}")],
        [InlineKeyboardButton("✅ Закрыть тикет", callback_data=f"admin:close:{tid}")],
        [InlineKeyboardButton("« К тикетам", callback_data="admin:tickets")],
    ])


def back_to_main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("« В главное меню", callback_data="back:main")],
    ])


def admin_quick_reply_ticket_kb(tid: str):
    """Кнопка для администратора: сразу ответить на тикет."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Ответить на тикет", callback_data=f"admin:reply:{tid}")],
    ])


def notify_supervisor_kb(rid: str):
    """Кнопка уведомить своего администратора о замене."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📣 Предупредить администратора", callback_data=f"notify_sup:{rid}")],
        [InlineKeyboardButton("↩️ Отменить подтверждение", callback_data=f"undo_confirm:{rid}")],
    ])


def supervisors_kb(supervisors: list):
    """Выбор администратора/куратора при регистрации."""
    rows = []
    for s in supervisors:
        sid = s.get("id")
        title = s.get("title") or f"Админ #{sid}"
        if len(title) > 40:
            title = title[:37] + "..."
        rows.append([InlineKeyboardButton(title, callback_data=f"reg:supervisor:{sid}")])
    rows.append([InlineKeyboardButton("« В меню", callback_data="back:main")])
    return InlineKeyboardMarkup(rows)


def admin_supervisors_kb(supervisors: list):
    rows = []
    for s in supervisors:
        sid = s.get("id")
        title = s.get("title") or ""
        short = title if len(title) <= 30 else title[:27] + "..."
        rows.append([
            InlineKeyboardButton(f"✏️ {short}", callback_data=f"admin:supervisoredit:{sid}"),
            InlineKeyboardButton("🗑", callback_data=f"admin:supervisordel:{sid}"),
        ])
    rows.append([InlineKeyboardButton("➕ Добавить администратора", callback_data="admin:supervisoradd")])
    rows.append([InlineKeyboardButton("« Назад", callback_data="admin:back")])
    return InlineKeyboardMarkup(rows)


def admin_reset_users_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚠️ Удалить всех пользователей", callback_data="admin:resetusers:confirm")],
        [InlineKeyboardButton("« Назад", callback_data="admin:back")],
    ])


def admin_reset_users_confirm_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да, удалить", callback_data="admin:resetusers:yes"),
            InlineKeyboardButton("❌ Отмена", callback_data="admin:resetusers:no"),
        ],
    ])


def admin_users_nav_kb(page: int, total: int, per_page: int = 10, prefix: str = "admin:usersp"):
    rows = []
    nav = [InlineKeyboardButton("« Назад", callback_data="admin:back")]
    start = page * per_page
    if page > 0:
        nav.insert(0, InlineKeyboardButton("◀", callback_data=f"{prefix}:{page-1}"))
    if start + per_page < total:
        nav.append(InlineKeyboardButton("▶", callback_data=f"{prefix}:{page+1}"))
    rows.append(nav)
    # Дополнительные подсказки для бан/разбан через команды.
    return InlineKeyboardMarkup(rows)


def admin_users_list_kb(users_page: list, page: int, total: int, per_page: int = 10):
    """Список участников с бан/разбан кнопками + навигация."""
    rows = []
    for u in users_page:
        uid = u.get("telegram_id")
        fn = u.get("full_name") or u.get("name") or f"ID {uid}"
        short = fn if len(fn) <= 22 else fn[:19] + "..."
        if u.get("banned_until"):
            rows.append([
                InlineKeyboardButton(f"🔓 {short}", callback_data=f"admin:userunban:{uid}"),
                InlineKeyboardButton("👤 Профиль", callback_data=f"admin:userprofile:{uid}"),
            ])
        else:
            rows.append([
                InlineKeyboardButton(f"🚫 {short}", callback_data=f"admin:userban:{uid}"),
                InlineKeyboardButton("👤 Профиль", callback_data=f"admin:userprofile:{uid}"),
            ])
    # Навигация
    start = page * per_page
    nav = [InlineKeyboardButton("« Назад", callback_data="admin:back")]
    if page > 0:
        nav.insert(0, InlineKeyboardButton("◀", callback_data=f"admin:usersp:{page-1}"))
    if start + per_page < total:
        nav.append(InlineKeyboardButton("▶", callback_data=f"admin:usersp:{page+1}"))
    rows.append(nav)
    rows.append([InlineKeyboardButton("🔎 Фильтр по объекту", callback_data="admin:users:filterobj")])
    return InlineKeyboardMarkup(rows)


def admin_user_profile_kb(uid: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚠ Предупреждение", callback_data=f"admin:warn:{uid}"),
            InlineKeyboardButton("✉ Сообщение", callback_data=f"admin:msg:{uid}"),
        ],
        [
            InlineKeyboardButton("➕ Доверие +5", callback_data=f"admin:trust:+5:{uid}"),
            InlineKeyboardButton("➖ Доверие -5", callback_data=f"admin:trust:-5:{uid}"),
        ],
        [
            InlineKeyboardButton("➕ +1", callback_data=f"admin:trust:+1:{uid}"),
            InlineKeyboardButton("➖ -1", callback_data=f"admin:trust:-1:{uid}"),
            InlineKeyboardButton("✏️ Ввести", callback_data=f"admin:trust:set:{uid}"),
        ],
        [InlineKeyboardButton("« К пользователям", callback_data="admin:users")],
    ])


def admin_userban_cancel_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin:userban_cancel")]])


def admin_users_filter_cities_kb():
    cities = storage.get_cities()
    rows = [[InlineKeyboardButton(c, callback_data=f"usersobj:city:{i}")] for i, c in enumerate(cities)]
    rows.append([InlineKeyboardButton("❌ Сбросить фильтр", callback_data="usersobj:reset")])
    rows.append([InlineKeyboardButton("« Назад", callback_data="admin:users")])
    return InlineKeyboardMarkup(rows)


def admin_users_filter_companies_kb(city_idx: int):
    cities = storage.get_cities()
    if city_idx < 0 or city_idx >= len(cities):
        return InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="admin:users")]])
    companies = storage.get_companies(cities[city_idx])
    rows = [[InlineKeyboardButton(c, callback_data=f"usersobj:company:{city_idx}:{i}")] for i, c in enumerate(companies)]
    rows.append([InlineKeyboardButton("« К городам", callback_data="admin:users:filterobj")])
    return InlineKeyboardMarkup(rows)


def admin_users_filter_objects_kb(city_idx: int, company_idx: int):
    cities = storage.get_cities()
    if city_idx < 0 or city_idx >= len(cities):
        return InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="admin:users")]])
    companies = storage.get_companies(cities[city_idx])
    if company_idx < 0 or company_idx >= len(companies):
        return InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="admin:users:filterobj")]])
    objects = storage.get_objects(cities[city_idx], companies[company_idx])
    rows = [[InlineKeyboardButton(o, callback_data=f"usersobj:set:{city_idx}:{company_idx}:{i}")] for i, o in enumerate(objects)]
    rows.append([InlineKeyboardButton("« К компаниям", callback_data=f"usersobj:city:{city_idx}")])
    return InlineKeyboardMarkup(rows)


def digest_notify_kb():
    """В уведомлении о количестве замен: перейти к списку и отключить уведомления."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 К списку замен", callback_data="act:replace")],
        [InlineKeyboardButton("🏠 Меню", callback_data="back:main")],
        [InlineKeyboardButton("🔕 Отключить уведомления", callback_data="settings:toggle_notify")],
    ])


def friend_confirm_kb(rid: str):
    """Подтверждение второй замены на ту же дату."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да", callback_data=f"friend:yes:{rid}"),
            InlineKeyboardButton("❌ Нет", callback_data=f"friend:no:{rid}"),
        ],
        [InlineKeyboardButton("« В меню", callback_data="back:main")],
    ])


def admin_shiftcfg_cities_kb():
    cities = storage.get_cities()
    rows = [[InlineKeyboardButton(c, callback_data=f"shiftcfg:city:{i}")] for i, c in enumerate(cities)]
    rows.append([InlineKeyboardButton("« Назад", callback_data="admin:back")])
    return InlineKeyboardMarkup(rows)


def admin_shiftcfg_companies_kb(city_idx: int):
    cities = storage.get_cities()
    if city_idx < 0 or city_idx >= len(cities):
        return InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="admin:back")]])
    companies = storage.get_companies(cities[city_idx])
    rows = [[InlineKeyboardButton(c, callback_data=f"shiftcfg:company:{city_idx}:{i}")] for i, c in enumerate(companies)]
    rows.append([InlineKeyboardButton("« К городам", callback_data="admin:shiftcfg")])
    return InlineKeyboardMarkup(rows)


def admin_shiftcfg_objects_kb(city_idx: int, company_idx: int):
    cities = storage.get_cities()
    if city_idx < 0 or city_idx >= len(cities):
        return InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="admin:shiftcfg")]])
    companies = storage.get_companies(cities[city_idx])
    if company_idx < 0 or company_idx >= len(companies):
        return InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data=f"shiftcfg:city:{city_idx}")]])
    objects = storage.get_objects(cities[city_idx], companies[company_idx])
    rows = [[InlineKeyboardButton(o, callback_data=f"shiftcfg:object:{city_idx}:{company_idx}:{i}")] for i, o in enumerate(objects)]
    rows.append([InlineKeyboardButton("« К компаниям", callback_data=f"shiftcfg:city:{city_idx}")])
    return InlineKeyboardMarkup(rows)


def shiftreport_cities_kb():
    return admin_shiftcfg_cities_kb()


def shiftreport_companies_kb(city_idx: int):
    return admin_shiftcfg_companies_kb(city_idx)


def shiftreport_objects_kb(city_idx: int, company_idx: int):
    return admin_shiftcfg_objects_kb(city_idx, company_idx)


def shiftreport_shift_kb(city_idx: int, company_idx: int, object_idx: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Дневная", callback_data=f"shiftrep:shift:{city_idx}:{company_idx}:{object_idx}:day")],
        [InlineKeyboardButton("Ночная", callback_data=f"shiftrep:shift:{city_idx}:{company_idx}:{object_idx}:night")],
        [InlineKeyboardButton("« Назад", callback_data=f"shiftrep:company:{city_idx}:{company_idx}")],
    ])


def shiftreport_nav_kb(page: int, total: int, per_page: int = 10):
    nav = [InlineKeyboardButton("« Назад", callback_data="admin:shiftreport")]
    start = page * per_page
    if page > 0:
        nav.insert(0, InlineKeyboardButton("◀", callback_data=f"shiftrep:page:{page-1}"))
    if start + per_page < total:
        nav.append(InlineKeyboardButton("▶", callback_data=f"shiftrep:page:{page+1}"))
    return InlineKeyboardMarkup([nav])

def admin_shiftcfg_object_kb(city_idx: int, company_idx: int, object_idx: int):
    cities = storage.get_cities()
    if city_idx < 0 or city_idx >= len(cities):
        return InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="admin:shiftcfg")]])
    companies = storage.get_companies(cities[city_idx])
    if company_idx < 0 or company_idx >= len(companies):
        return InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data=f"shiftcfg:city:{city_idx}")]])
    objects = storage.get_objects(cities[city_idx], companies[company_idx])
    if object_idx < 0 or object_idx >= len(objects):
        return InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data=f"shiftcfg:company:{city_idx}:{company_idx}")]])
    obj = objects[object_idx]
    city = cities[city_idx]
    company = companies[company_idx]
    day = storage.get_object_shift(city, company, obj, "day") or {}
    night = storage.get_object_shift(city, company, obj, "night") or {}
    day_label = f"Дневная: {day.get('start_time','09:00')}–{day.get('end_time','21:00')}"
    night_label = f"Ночная: {night.get('start_time','21:00')}–{night.get('end_time','09:00')}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✏️ {day_label}", callback_data=f"shiftcfg:edit:{city_idx}:{company_idx}:{object_idx}:day")],
        [InlineKeyboardButton(f"✏️ {night_label}", callback_data=f"shiftcfg:edit:{city_idx}:{company_idx}:{object_idx}:night")],
        [InlineKeyboardButton("« К объектам", callback_data=f"shiftcfg:company:{city_idx}:{company_idx}")],
    ])


def support_reply_ticket_kb(tid: str):
    """Кнопка «Ответить на тикет» под сообщением от поддержки."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Ответить на тикет", callback_data=f"support:reply:{tid}")],
    ])


def reviews_main_kb(has_review: bool):
    label = "✏️ Редактировать отзыв" if has_review else "⭐ Оставить отзыв"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data="review:add")],
        [InlineKeyboardButton("📋 Смотреть отзывы", callback_data="review:list")],
        [InlineKeyboardButton("« Назад", callback_data="back:main")],
    ])


def reviews_list_kb(reviews: list, order: str, page: int, total: int, per_page: int = 5):
    """Кнопки сортировки, по одной кнопке на отзыв, навигация."""
    order_btn = {
        "recent": ("По времени ▼", "review:order:recent"),
        "rating_asc": ("Сначала низкие", "review:order:rating_asc"),
        "rating_desc": ("Сначала высокие", "review:order:rating_desc"),
    }
    rows = []
    row = []
    for k, (label, cb) in order_btn.items():
        prefix = "• " if order == k else ""
        row.append(InlineKeyboardButton(prefix + label, callback_data=cb))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    for rev in reviews:
        short = f"⭐{rev.get('rating', 0)} | {(rev.get('text') or '')[:30]}..."
        if len(short) > 40:
            short = short[:37] + "..."
        rows.append([InlineKeyboardButton(short, callback_data=f"review:detail:{rev['id']}")])
    start = page * per_page
    nav = [InlineKeyboardButton("« Назад", callback_data="menu:reviews")]
    if page > 0:
        nav.insert(0, InlineKeyboardButton("◀", callback_data=f"review:page:{page-1}:{order}"))
    if start + per_page < total:
        nav.append(InlineKeyboardButton("▶", callback_data=f"review:page:{page+1}:{order}"))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def review_detail_kb(review_id: int, user_like: int):
    """user_like: -1, 0, 1 — текущая реакция пользователя."""
    rows = []
    like_label = "👍 Полезно" if user_like != 1 else "👍 Полезно ✓"
    dis_label = "👎 Бесполезно" if user_like != -1 else "👎 Бесполезно ✓"
    rows.append([
        InlineKeyboardButton(like_label, callback_data=f"review:like:{review_id}"),
        InlineKeyboardButton(dis_label, callback_data=f"review:dislike:{review_id}"),
    ])
    rows.append([InlineKeyboardButton("« К отзывам", callback_data="review:list")])
    return InlineKeyboardMarkup(rows)


def review_rating_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("1", callback_data="review:rate:1"),
            InlineKeyboardButton("2", callback_data="review:rate:2"),
            InlineKeyboardButton("3", callback_data="review:rate:3"),
            InlineKeyboardButton("4", callback_data="review:rate:4"),
            InlineKeyboardButton("5", callback_data="review:rate:5"),
        ],
        [InlineKeyboardButton("« Отмена", callback_data="menu:reviews")],
    ])
