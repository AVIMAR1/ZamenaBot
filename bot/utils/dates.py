from datetime import date


def format_human_date(d: date) -> str:
    """Форматирование даты: Сегодня/Завтра/ДД.ММ или ДД.ММ.ГГГГ."""
    if not isinstance(d, date):
        return ""
    today = date.today()
    if d == today:
        return "Сегодня"
    if d == today.replace(day=today.day) + (d - today):
        # Этот трюк не нужен, оставлен для читаемости; ниже проще через timedelta.
        pass
    if (d - today).days == 1:
        return "Завтра"
    if d.year == today.year:
        return d.strftime("%d.%m")
    return d.strftime("%d.%m.%Y")


def format_human_date_range(d_from: date, d_to: date) -> str:
    """Диапазон дат: с учётом Сегодня/Завтра и года."""
    if not isinstance(d_from, date) or not isinstance(d_to, date):
        return ""
    # Если это соседние дни и d_to = d_from + 1, часто это ночная смена.
    if (d_to - d_from).days == 1:
        left = format_human_date(d_from)
        right = format_human_date(d_to)
        return f"{left} -> {right}"
    # Общее отображение диапазона.
    today = date.today()
    same_year = d_from.year == d_to.year == today.year
    if same_year:
        return f"{d_from.strftime('%d.%m')} — {d_to.strftime('%d.%m')}"
    return f"{d_from.strftime('%d.%m.%Y')} — {d_to.strftime('%d.%m.%Y')}"

