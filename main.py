# -*- coding: utf-8 -*-
"""Точка входа: запуск бота и регистрация обработчиков."""

import logging
from datetime import datetime, time, date, timedelta

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from telegram import BotCommand

import config
import database  # инициализация БД при импорте
import storage
from keyboards import main_menu_kb, digest_notify_kb
from bot.handlers import start as start_handlers
from bot.handlers import menu as menu_handlers
from bot.handlers import find_replace as find_handlers
from bot.handlers import replace as replace_handlers
from bot.handlers import support as support_handlers
from bot.handlers import admin as admin_handlers
from bot.handlers import reviews as reviews_handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def noop_callback(update: Update, context):
    query = update.callback_query
    if query:
        await query.answer()


async def message_dispatch(update: Update, context):
    """Текстовые сообщения: поддержка, ответ в тикет, отзыв, ответ админа, справочник."""
    if context.user_data.get("waiting_support"):
        await support_handlers.support_text(update, context)
        return
    if context.user_data.get("waiting_support_reply_tid"):
        await support_handlers.support_reply_text(update, context)
        return
    if context.user_data.get("waiting_review_text"):
        await reviews_handlers.review_text_message(update, context)
        return
    if context.user_data.get("admin_broadcast_waiting"):
        await admin_handlers.admin_broadcast_text(update, context)
        return
    if context.user_data.get("admin_ban_waiting"):
        await admin_handlers.admin_ban_text(update, context)
        return
    if context.user_data.get("admin_shiftcfg_waiting"):
        await admin_handlers.admin_shiftcfg_text(update, context)
        return
    if context.user_data.get("admin_replying_tid"):
        await admin_handlers.admin_reply_text(update, context)
        return
    if context.user_data.get("admin_cat_add") == "city":
        await admin_handlers.catalog_add_city_text(update, context)
        return
    if context.user_data.get("admin_cat_add"):
        await admin_handlers.catalog_add_text(update, context)
        return


async def cmd_menu(update: Update, context):
    """Команда /menu — показать главное меню."""
    if not update.message:
        return
    text = (
        "Главное меню. Доступные команды:\n"
        "/menu — главное меню\n"
        "/help — помощь\n"
        "/admin — режим администратора (для админа)\n"
    )
    await update.message.reply_text(text, reply_markup=main_menu_kb())


async def cmd_help(update: Update, context):
    """Команда /help — краткая справка."""
    if not update.message:
        return
    text = (
        "Команды:\n"
        "/menu — главное меню\n"
        "/help — эта справка\n"
        "/admin — режим администратора (доступен только администратору)\n\n"
        "Основные действия:\n"
        "• «Найти замену» — выложить объявление о замене\n"
        "• «Заменить» — откликнуться на доступные замены\n"
        "• «Профиль» — статистика и ваши объявления\n"
        "• «Настройки» — профиль и уведомления\n"
        "• «Поддержка» — написать в поддержку\n"
    )
    await update.message.reply_text(text, reply_markup=main_menu_kb())


# --- Планировщик задач: дайджесты и старт смен ---


async def digest_job(context):
    """Ежедневные дайджесты в 12:00 и 18:00: сколько сейчас активных замен у пользователя."""
    all_replacements = storage.get_replacements(active_only=True)
    users = storage.get_all_users()
    for uid_str, user in users.items():
        try:
            uid = int(uid_str)
        except (TypeError, ValueError):
            continue
        if not user.get("notify_digest", 1):
            continue
        city = user.get("city")
        company = user.get("company")
        obj = user.get("object")
        if not (city and company and obj):
            continue
        count = 0
        for r in all_replacements:
            if (
                r.get("city") == city
                and r.get("company") == company
                and r.get("object") == obj
                and str(r.get("author_id")) != uid_str
            ):
                count += 1
        if not count:
            continue
        text = (
            f"Сейчас в списке {count} замен(ы) по вашему объекту.\n"
            f"Перейти к списку?"
        )
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=text,
                reply_markup=digest_notify_kb(),
            )
        except Exception:
            continue


async def shifts_start_job(context):
    """Отслеживание начала смен: уведомления по согласованным/несогласованным заменам."""
    now = datetime.now()
    today = date.today()
    today_iso = today.isoformat()
    # Берём все активные замены, включая те, на которые уже есть заявка.
    all_replacements = storage.get_replacements(active_only=True, exclude_requested=False)
    for r in all_replacements:
        if r.get("start_notified"):
            continue
        if r.get("date_from") != today_iso:
            continue
        shift_key = r.get("shift_key") or "day"
        city = r.get("city")
        company = r.get("company")
        obj = r.get("object")
        if not (city and company and obj):
            continue
        # Время начала смены: либо из object_shifts, либо дефолт (09:00/21:00).
        shift_info = storage.get_object_shift(city, company, obj, shift_key)
        if shift_info and shift_info.get("start_time"):
            start_str = shift_info["start_time"]
        else:
            start_str = "09:00" if shift_key == "day" else "21:00"
        try:
            h, m = map(int, start_str.split(":", 1))
        except Exception:
            continue
        start_dt = datetime.combine(today, time(h, m))
        # Считаем, что «начало смены» — окно в 10 минут от старта.
        if not (start_dt <= now <= start_dt + timedelta(minutes=10)):
            continue

        author_id = r.get("author_id")
        taker_id = r.get("taken_by_id")
        position = r.get("position", "")
        date_text = r.get("date_text", "")

        if r.get("confirmed") and taker_id:
            # Согласованная замена.
            try:
                await context.bot.send_message(
                    chat_id=author_id,
                    text=f"Смена началась ({position}, {date_text}). Вас заменяет пользователь ID {taker_id}.",
                )
            except Exception:
                pass
            try:
                await context.bot.send_message(
                    chat_id=taker_id,
                    text=f"Началась согласованная смена ({position}, {date_text}), где вы заменяете автора объявления.",
                )
            except Exception:
                pass
            r["start_notified"] = 1
            storage.save_replacement(r)
            continue

        # Несогласованная замена: никого не нашли, снимаем со списка.
        try:
            await context.bot.send_message(
                chat_id=author_id,
                text=(
                    f"Смена началась ({position}, {date_text}), но замена не была согласована.\n"
                    f"Объявление автоматически снято с публикации."
                ),
            )
        except Exception:
            pass
        r["active"] = False
        r["requested_by_id"] = None
        r["requested_by_username"] = None
        r["start_notified"] = 1
        storage.save_replacement(r)


def main():
    async def post_init(app_: Application):
        # Команды, чтобы пользователю всегда было куда вернуться (/menu).
        await app_.bot.set_my_commands([
            BotCommand("start", "Запуск / регистрация"),
            BotCommand("menu", "Главное меню"),
            BotCommand("help", "Справка"),
            BotCommand("admin", "Админка (только для админа)"),
        ])

    app = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()

    # Планировщик: дайджесты в 12:00 и 18:00 и отслеживание начала смен.
    job_queue = app.job_queue
    job_queue.run_daily(digest_job, time=time(12, 0))
    job_queue.run_daily(digest_job, time=time(18, 0))
    # Проверка начала смен каждые 5 минут.
    job_queue.run_repeating(shifts_start_job, interval=300, first=60)

    app.add_handler(CommandHandler("start", start_handlers.start))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("admin", admin_handlers.admin_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_dispatch))

    app.add_handler(CallbackQueryHandler(menu_handlers.back_main, pattern="^back:main$"))
    app.add_handler(CallbackQueryHandler(menu_handlers.menu_profile, pattern="^menu:profile$"))
    app.add_handler(CallbackQueryHandler(menu_handlers.menu_admin, pattern="^menu:admin$"))
    app.add_handler(CallbackQueryHandler(menu_handlers.menu_settings, pattern="^menu:settings$"))
    app.add_handler(CallbackQueryHandler(menu_handlers.settings_edit_profile, pattern="^settings:edit_profile$"))
    app.add_handler(CallbackQueryHandler(menu_handlers.settings_toggle_notify, pattern="^settings:toggle_notify$"))
    app.add_handler(CallbackQueryHandler(menu_handlers.menu_my_ads, pattern="^menu:my_ads$"))
    app.add_handler(CallbackQueryHandler(menu_handlers.menu_my_ads_page, pattern="^myads:"))
    app.add_handler(CallbackQueryHandler(menu_handlers.my_ad_detail, pattern="^myad:"))
    app.add_handler(CallbackQueryHandler(menu_handlers.deactivate_ad, pattern="^deactivate:"))
    app.add_handler(CallbackQueryHandler(menu_handlers.menu_my_responses, pattern="^menu:my_responses$"))
    app.add_handler(CallbackQueryHandler(menu_handlers.my_responses_page, pattern="^myrespp:"))
    app.add_handler(CallbackQueryHandler(menu_handlers.my_response_detail, pattern="^myresp:"))

    app.add_handler(CallbackQueryHandler(start_handlers.callback_city, pattern="^city:"))
    app.add_handler(CallbackQueryHandler(start_handlers.callback_company, pattern="^company:"))
    app.add_handler(CallbackQueryHandler(start_handlers.callback_object, pattern="^obj:"))

    app.add_handler(CallbackQueryHandler(find_handlers.act_find, pattern="^act:find$"))
    app.add_handler(CallbackQueryHandler(find_handlers.edit_ad, pattern="^editad:"))
    app.add_handler(CallbackQueryHandler(find_handlers.callback_shift, pattern="^shift:"))
    app.add_handler(CallbackQueryHandler(find_handlers.callback_position, pattern="^pos:"))
    app.add_handler(CallbackQueryHandler(find_handlers.callback_calendar_nav, pattern="^cal:"))
    app.add_handler(CallbackQueryHandler(find_handlers.callback_date, pattern="^date:"))
    app.add_handler(CallbackQueryHandler(find_handlers.callback_publish, pattern="^publish:"))
    app.add_handler(CallbackQueryHandler(find_handlers.friend_confirm, pattern="^friend:(yes|no):"))
    app.add_handler(CallbackQueryHandler(find_handlers.callback_update, pattern="^update:"))

    app.add_handler(CallbackQueryHandler(replace_handlers.act_replace, pattern="^act:replace$"))
    app.add_handler(CallbackQueryHandler(replace_handlers.replace_list_page, pattern="^replist:"))
    app.add_handler(CallbackQueryHandler(replace_handlers.take_replacement, pattern="^take:"))
    app.add_handler(CallbackQueryHandler(replace_handlers.confirm_take, pattern="^confirm_take:"))
    app.add_handler(CallbackQueryHandler(replace_handlers.creator_accept, pattern="^creator_accept:"))
    app.add_handler(CallbackQueryHandler(replace_handlers.creator_reject, pattern="^creator_reject:"))
    app.add_handler(CallbackQueryHandler(replace_handlers.taker_refuse, pattern="^taker_refuse:"))
    app.add_handler(CallbackQueryHandler(replace_handlers.undo_confirm, pattern="^undo_confirm:"))

    app.add_handler(CallbackQueryHandler(support_handlers.menu_support, pattern="^(menu:support|support:new)$"))
    app.add_handler(CallbackQueryHandler(support_handlers.support_reply_start, pattern="^support:reply:"))

    app.add_handler(CallbackQueryHandler(reviews_handlers.menu_reviews, pattern="^menu:reviews$"))
    app.add_handler(CallbackQueryHandler(reviews_handlers.review_add, pattern="^review:add$"))
    app.add_handler(CallbackQueryHandler(reviews_handlers.review_rate, pattern="^review:rate:"))
    app.add_handler(CallbackQueryHandler(reviews_handlers.review_list, pattern="^review:(list|order:|page:)"))
    app.add_handler(CallbackQueryHandler(reviews_handlers.review_detail, pattern="^review:detail:"))
    app.add_handler(CallbackQueryHandler(reviews_handlers.review_like, pattern="^review:like:"))
    app.add_handler(CallbackQueryHandler(reviews_handlers.review_dislike, pattern="^review:dislike:"))

    app.add_handler(CallbackQueryHandler(admin_handlers.admin_back, pattern="^admin:back$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_exit, pattern="^admin:exit$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_broadcast, pattern="^admin:broadcast$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_banned, pattern="^admin:banned$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_unban, pattern="^admin:unban:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_ban_prompt, pattern="^admin:ban_prompt$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_shiftcfg, pattern="^admin:shiftcfg$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_shiftcfg_city, pattern="^shiftcfg:city:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_shiftcfg_company, pattern="^shiftcfg:company:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_shiftcfg_object, pattern="^shiftcfg:object:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_shiftcfg_edit, pattern="^shiftcfg:edit:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_tickets, pattern="^admin:tickets$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_tickets_list, pattern="^admin:tickets:(open|closed)$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_ticket_page, pattern="^admin:tlist:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_ticket_detail, pattern="^admin:t:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_reply, pattern="^admin:reply:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_close_ticket, pattern="^admin:close:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_users, pattern="^admin:users$"))

    app.add_handler(CallbackQueryHandler(admin_handlers.admin_catalog, pattern="^admin:catalog$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.catalog_city_menu, pattern="^cat:city:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.catalog_obj_select, pattern="^cat:objselect:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.catalog_pos_select, pattern="^cat:posselect:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.catalog_show_list, pattern="^cat:(companies|objectlist|posobj|positionlist):"))
    app.add_handler(CallbackQueryHandler(admin_handlers.catalog_add_prompt, pattern="^cat:add:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.catalog_del_item, pattern="^cat:del:(companies|objects|positions):"))
    app.add_handler(CallbackQueryHandler(admin_handlers.catalog_add_city_prompt, pattern="^cat:addcity$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.catalog_del_city, pattern="^cat:delcity:"))

    app.add_handler(CallbackQueryHandler(noop_callback, pattern="^noop"))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
