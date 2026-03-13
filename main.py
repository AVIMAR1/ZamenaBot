# -*- coding: utf-8 -*-
"""Точка входа: запуск бота и регистрация обработчиков."""

import logging
from datetime import datetime, time, date, timedelta
from zoneinfo import ZoneInfo

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
from keyboards import main_menu_kb, digest_notify_kb, menu_quick_kb
from bot.handlers import start as start_handlers
from bot.handlers import menu as menu_handlers
from bot.handlers import find_replace as find_handlers
from bot.handlers import replace as replace_handlers
from bot.handlers import offers as offers_handlers
from bot.handlers import support as support_handlers
from bot.handlers import admin as admin_handlers
from bot.handlers import reviews as reviews_handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Локальный часовой пояс объекта (Гродно, Беларусь — без сезонных сдвигов).
LOCAL_TZ = ZoneInfo("Europe/Minsk")


def _is_user_banned(user: dict) -> bool:
    """Полный бан: пользователь не может пользоваться ботом."""
    from datetime import date as _date

    until = user.get("banned_until")
    if not until:
        return False


def _is_user_registered(user: dict | None) -> bool:
    if not user:
        return False
    return bool(user.get("city") and user.get("company") and user.get("object") and user.get("full_name") and user.get("supervisor_id"))
    if until == "forever":
        return True
    try:
        d = _date.fromisoformat(until)
        return d >= _date.today()
    except Exception:
        return False


async def noop_callback(update: Update, context):
    query = update.callback_query
    if query:
        # Обновляем username при любом клике.
        try:
            u = query.from_user
            if u:
                user = storage.get_user(u.id) or {"telegram_id": u.id}
                user["username"] = u.username or ""
                user["name"] = (u.first_name or "") + " " + (u.last_name or "")
                storage.save_user(u.id, user)
                if _is_user_banned(user):
                    await query.answer("Доступ к боту заблокирован.", show_alert=True)
                    return
                if query.data != "noop" and not _is_user_registered(user):
                    await query.answer("Сначала пройдите регистрацию (/start).", show_alert=True)
                    return
        except Exception:
            pass
        await query.answer()


async def message_dispatch(update: Update, context):
    """Текстовые сообщения: поддержка, ответ в тикет, отзыв, ответ админа, справочник."""
    # Обновляем username/имя на любом входящем сообщении.
    try:
        u = update.effective_user
        if u:
            user = storage.get_user(u.id) or {"telegram_id": u.id}
            user["username"] = u.username or ""
            user["name"] = (u.first_name or "") + " " + (u.last_name or "")
            storage.save_user(u.id, user)
            if _is_user_banned(user):
                # Забаненным ничего не отвечаем.
                return
    except Exception:
        pass
    # В группах и каналах бот на обычные сообщения не отвечает (вся логика только в личке).
    chat = update.effective_chat
    if chat and chat.type != "private":
        return
    # До регистрации запрещаем любые текстовые команды/сообщения, кроме flow /start (кнопки города/компании/объекта идут callback'ами).
    try:
        u = update.effective_user
        if u:
            user = storage.get_user(u.id) or {}
            txt = (update.message.text or "") if update.message else ""
            if txt.startswith("/") and not txt.startswith("/start") and not _is_user_registered(user):
                return
    except Exception:
        pass
    if context.user_data.get("waiting_support"):
        await support_handlers.support_text(update, context)
        return
    if context.user_data.get("waiting_support_reply_tid"):
        await support_handlers.support_reply_text(update, context)
        return
    if context.user_data.get("waiting_review_text"):
        await reviews_handlers.review_text_message(update, context)
        return
    if context.user_data.get("waiting_full_name"):
        await start_handlers.full_name_text(update, context)
        return
    if context.user_data.get("friends_add_waiting"):
        await menu_handlers.friends_add_text(update, context)
        return
    if context.user_data.get("admin_broadcast_waiting"):
        await admin_handlers.admin_broadcast_text(update, context)
        return
    if context.user_data.get("admin_ban_waiting"):
        await admin_handlers.admin_ban_text(update, context)
        return
    if context.user_data.get("admin_userban_target"):
        await admin_handlers.admin_userban_text(update, context)
        return
    if context.user_data.get("admin_warn_target"):
        await admin_handlers.admin_warn_text(update, context)
        return
    if context.user_data.get("admin_msg_target"):
        await admin_handlers.admin_msg_text(update, context)
        return
    if context.user_data.get("admin_trust_set_target"):
        await admin_handlers.admin_trust_set_text(update, context)
        return
    if context.user_data.get("admin_supervisor_add_waiting"):
        await admin_handlers.admin_supervisor_add_text(update, context)
        return
    if context.user_data.get("objacc_addchat"):
        await admin_handlers.objacc_addchat_text(update, context)
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
    if context.user_data.get("admin_cat_rename"):
        await admin_handlers.catalog_rename_text(update, context)
        return
    if context.user_data.get("replacement_pay_amount_waiting"):
        rid = context.user_data.pop("replacement_pay_amount_waiting", None)
        pending = context.user_data.get("pending_replacement") or {}
        if rid and pending.get("id") == rid and update.message:
            raw = (update.message.text or "").strip().replace(",", ".")
            try:
                amt = float(raw)
            except Exception:
                amt = None
            if amt is not None and amt > 0:
                pending["pay_amount_byn"] = amt
                pending["pay_enabled"] = True
                context.user_data["pending_replacement"] = pending
                await update.message.reply_text("Сумма сохранена. Вернитесь к подтверждению.", reply_markup=menu_quick_kb())
        return
    if context.user_data.get("offer_pay_amount_waiting"):
        oid = context.user_data.pop("offer_pay_amount_waiting", None)
        pending = context.user_data.get("pending_offer") or {}
        if oid and pending.get("id") == oid and update.message:
            raw = (update.message.text or "").strip().replace(",", ".")
            try:
                amt = float(raw)
            except Exception:
                amt = None
            if amt is not None and amt > 0:
                pending["pay_amount_byn"] = amt
                pending["pay_enabled"] = True
                context.user_data["pending_offer"] = pending
                await update.message.reply_text("Сумма сохранена. Вернитесь к подтверждению.", reply_markup=menu_quick_kb())
        return


async def cmd_menu(update: Update, context):
    """Команда /menu — показать главное меню."""
    if not update.message:
        return
    chat = update.effective_chat
    if chat and chat.type != "private":
        return
    uid = update.effective_user.id if update.effective_user else 0
    user = storage.get_user(uid) if uid else None
    if not _is_user_registered(user):
        await update.message.reply_text("Сначала пройдите регистрацию через /start.")
        return
    text = (
        "Главное меню. Доступные команды:\n"
        "/menu — главное меню\n"
        "/help — помощь\n"
    )
    await update.message.reply_text(text, reply_markup=main_menu_kb())


async def cmd_help(update: Update, context):
    """Команда /help — краткая справка."""
    if not update.message:
        return
    chat = update.effective_chat
    if chat and chat.type != "private":
        return
    uid = update.effective_user.id if update.effective_user else 0
    user = storage.get_user(uid) if uid else None
    if not _is_user_registered(user):
        await update.message.reply_text("Сначала пройдите регистрацию через /start.")
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


async def cmd_chatid(update: Update, context):
    """Служебная команда: показать chat_id текущего чата."""
    chat = update.effective_chat
    msg = update.effective_message
    if not chat or not msg:
        return
    # В группах/каналах отвечаем только один раз за время работы бота.
    if chat.type != "private":
        data = context.application.bot_data.setdefault("chatid_reported", set())
        try:
            key = int(chat.id)
        except Exception:
            key = chat.id
        if key in data:
            return
        data.add(key)
    await msg.reply_text(f"chat_id: {chat.id}\ntype: {chat.type}")


# --- Планировщик задач: дайджесты и старт смен ---


async def digest_job(context):
    """Ежедневные дайджесты в 12:00 и 18:00: сколько сейчас активных замен у пользователя."""
    all_replacements = storage.get_replacements(active_only=True)
    users = storage.get_all_users()
    sent = 0
    failed = 0
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
        # Удаляем предыдущий дайджест, чтобы не засорять чат.
        try:
            last_id = user.get("last_digest_msg_id")
            if last_id:
                await context.bot.delete_message(chat_id=uid, message_id=int(last_id))
        except Exception:
            pass
        try:
            m = await context.bot.send_message(
                chat_id=uid,
                text=text,
                reply_markup=digest_notify_kb(),
            )
            user["last_digest_msg_id"] = getattr(m, "message_id", None)
            storage.save_user(uid, user)
            sent += 1
        except Exception:
            failed += 1
            continue
    if failed:
        logger.warning("digest_job: sent=%s failed=%s total_users=%s", sent, failed, len(users))


async def shifts_start_job(context):
    """Отслеживание начала смен: уведомления по согласованным/несогласованным заменам."""
    # Используем локальный часовой пояс, чтобы отработка не зависела от таймзоны сервера.
    now = datetime.now(LOCAL_TZ)
    today = now.date()
    today_iso = today.isoformat()
    # Берём все активные замены, включая те, на которые уже есть заявка.
    all_replacements = storage.get_replacements(active_only=True, exclude_requested=False)

    # Группируем объявления по смене, чтобы в момент старта снять ВСЕ объявления на эту смену.
    groups = {}
    for r in all_replacements:
        if r.get("start_notified") or r.get("date_from") != today_iso:
            continue
        shift_key = r.get("shift_key") or "day"
        city = r.get("city")
        company = r.get("company")
        obj = r.get("object")
        if not (city and company and obj):
            continue
        groups.setdefault((city, company, obj, shift_key), []).append(r)

    for (city, company, obj, shift_key), items in groups.items():
        shift_info = storage.get_object_shift(city, company, obj, shift_key)
        if shift_info and shift_info.get("start_time"):
            start_str = shift_info["start_time"]
        else:
            start_str = "09:00" if shift_key == "day" else "21:00"
        try:
            h, m = map(int, start_str.split(":", 1))
        except Exception:
            continue
        start_dt = datetime.combine(today, time(h, m, tzinfo=LOCAL_TZ))
        if not (start_dt <= now <= start_dt + timedelta(minutes=10)):
            continue

        # Уведомляем по согласованным заменам.
        for r in items:
            author_id = r.get("author_id")
            subject_id = r.get("for_friend_id") or author_id
            taker_id = r.get("taken_by_id")
            position = r.get("position", "")
            date_text = r.get("date_text", "")
            if r.get("confirmed") and taker_id:
                author = storage.get_user(author_id) or {}
                author["was_replaced_count"] = author.get("was_replaced_count", 0) + 1
                storage.save_user(author_id, author)
                taker = storage.get_user(taker_id) or {}
                taker["replaced_count"] = taker.get("replaced_count", 0) + 1
                # Доверие: повышаем тем, кто реально выходит на замену.
                try:
                    trust = float(taker.get("trust_score", 50) or 50)
                    trust = max(0.0, min(100.0, trust + 2.5))
                    taker["trust_score"] = trust
                except Exception:
                    pass
                storage.save_user(taker_id, taker)
                try:
                    await context.bot.send_message(
                        chat_id=subject_id,
                        text=f"✅ Смена началась: {position} | {date_text}\nЗамена подтверждена.",
                        reply_markup=menu_quick_kb(),
                    )
                except Exception:
                    pass
                if str(subject_id) != str(author_id):
                    try:
                        await context.bot.send_message(
                            chat_id=author_id,
                            text=f"✅ Смена началась: {position} | {date_text}\nДля друга замена подтверждена.",
                            reply_markup=menu_quick_kb(),
                        )
                    except Exception:
                        pass
                try:
                    await context.bot.send_message(
                        chat_id=taker_id,
                        text=f"✅ Смена началась: {position} | {date_text}\nВы выходите на замену.",
                        reply_markup=menu_quick_kb(),
                    )
                except Exception:
                    pass

        # Снимаем с публикации ВСЕ объявления на начавшуюся смену.
        for r in items:
            author_id = r.get("author_id")
            subject_id = r.get("for_friend_id") or author_id
            position = r.get("position", "")
            date_text = r.get("date_text", "")
            if not (r.get("confirmed") and r.get("taken_by_id")):
                try:
                    await context.bot.send_message(
                        chat_id=subject_id,
                        text=(
                            f"❌ Смена началась: {position} | {date_text}\n"
                            f"Замена не согласована — объявление снято."
                        ),
                        reply_markup=menu_quick_kb(),
                    )
                except Exception:
                    pass
                if str(subject_id) != str(author_id):
                    try:
                        await context.bot.send_message(
                            chat_id=author_id,
                            text=f"❌ Смена началась: {position} | {date_text}\nДля друга замена не согласована — объявление снято.",
                            reply_markup=menu_quick_kb(),
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
    app.add_handler(CommandHandler("chatid", cmd_chatid))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_dispatch))

    app.add_handler(CallbackQueryHandler(menu_handlers.back_main, pattern="^back:main$"))
    app.add_handler(CallbackQueryHandler(menu_handlers.menu_profile, pattern="^menu:profile$"))
    app.add_handler(CallbackQueryHandler(menu_handlers.menu_friends, pattern="^menu:friends$"))
    app.add_handler(CallbackQueryHandler(menu_handlers.friends_add_prompt, pattern="^friends:add$"))
    app.add_handler(CallbackQueryHandler(menu_handlers.friends_remove, pattern="^friends:remove:"))
    app.add_handler(CallbackQueryHandler(menu_handlers.menu_admin, pattern="^menu:admin$"))
    app.add_handler(CallbackQueryHandler(menu_handlers.menu_settings, pattern="^menu:settings$"))
    app.add_handler(CallbackQueryHandler(menu_handlers.settings_edit_profile, pattern="^settings:edit_profile$"))
    app.add_handler(CallbackQueryHandler(menu_handlers.settings_toggle_notify, pattern="^settings:toggle_notify$"))
    app.add_handler(CallbackQueryHandler(menu_handlers.settings_notify_new, pattern="^settings:notify_new$"))
    app.add_handler(CallbackQueryHandler(menu_handlers.notifynew_toggle, pattern="^notifynew:toggle$"))
    app.add_handler(CallbackQueryHandler(menu_handlers.notifynew_positions, pattern="^notifynew:positions$"))
    app.add_handler(CallbackQueryHandler(menu_handlers.notifypos_toggle, pattern="^notifypos:"))
    app.add_handler(CallbackQueryHandler(menu_handlers.notifynew_shifts, pattern="^notifynew:shifts$"))
    app.add_handler(CallbackQueryHandler(menu_handlers.notifyshift_toggle, pattern="^notifyshift:"))
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
    app.add_handler(CallbackQueryHandler(start_handlers.choose_supervisor, pattern="^reg:supervisor:"))

    app.add_handler(CallbackQueryHandler(find_handlers.act_find, pattern="^act:find$"))
    app.add_handler(CallbackQueryHandler(find_handlers.edit_ad, pattern="^editad:"))
    app.add_handler(CallbackQueryHandler(find_handlers.callback_shift, pattern="^shift:"))
    app.add_handler(CallbackQueryHandler(find_handlers.callback_position, pattern="^pos:"))
    app.add_handler(CallbackQueryHandler(find_handlers.callback_calendar_nav, pattern="^cal:"))
    app.add_handler(CallbackQueryHandler(find_handlers.callback_date, pattern="^date:"))
    app.add_handler(CallbackQueryHandler(find_handlers.replacement_pay, pattern="^reppay:"))
    app.add_handler(CallbackQueryHandler(find_handlers.callback_publish, pattern="^publish:"))
    app.add_handler(CallbackQueryHandler(find_handlers.friend_confirm, pattern="^friend:(yes|no):"))
    app.add_handler(CallbackQueryHandler(find_handlers.friends_choose, pattern="^friends:choose:"))
    app.add_handler(CallbackQueryHandler(find_handlers.friends_cancel, pattern="^friends:cancel:"))
    app.add_handler(CallbackQueryHandler(find_handlers.callback_update, pattern="^update:"))

    app.add_handler(CallbackQueryHandler(replace_handlers.act_replace, pattern="^act:replace$"))
    app.add_handler(CallbackQueryHandler(replace_handlers.replace_list_open, pattern="^replace:list$"))
    app.add_handler(CallbackQueryHandler(replace_handlers.replace_list_page, pattern="^replist:"))
    app.add_handler(CallbackQueryHandler(offers_handlers.offers_menu, pattern="^offers:menu$"))
    app.add_handler(CallbackQueryHandler(offers_handlers.offers_list, pattern="^offers:list$"))
    app.add_handler(CallbackQueryHandler(offers_handlers.offers_page, pattern="^offersp:"))
    app.add_handler(CallbackQueryHandler(offers_handlers.my_offers, pattern="^offers:mine$"))
    app.add_handler(CallbackQueryHandler(offers_handlers.offer_deactivate, pattern="^offer:off:"))
    app.add_handler(CallbackQueryHandler(offers_handlers.offer_create_start, pattern="^offers:create$"))
    app.add_handler(CallbackQueryHandler(offers_handlers.offer_shift, pattern="^offer:shift:"))
    app.add_handler(CallbackQueryHandler(offers_handlers.offer_date, pattern="^offerdate:"))
    app.add_handler(CallbackQueryHandler(offers_handlers.offer_cal_nav, pattern="^offercal:"))
    app.add_handler(CallbackQueryHandler(offers_handlers.offer_pos_toggle, pattern="^offerpos:"))
    app.add_handler(CallbackQueryHandler(offers_handlers.offer_pay, pattern="^offerpay:"))
    app.add_handler(CallbackQueryHandler(offers_handlers.offer_publish, pattern="^offerpub:"))
    app.add_handler(CallbackQueryHandler(replace_handlers.take_replacement, pattern="^take:"))
    app.add_handler(CallbackQueryHandler(replace_handlers.confirm_take, pattern="^confirm_take:"))
    app.add_handler(CallbackQueryHandler(replace_handlers.creator_accept, pattern="^creator_accept:"))
    app.add_handler(CallbackQueryHandler(replace_handlers.creator_reject, pattern="^creator_reject:"))
    app.add_handler(CallbackQueryHandler(replace_handlers.taker_refuse, pattern="^taker_refuse:"))
    app.add_handler(CallbackQueryHandler(replace_handlers.undo_confirm, pattern="^undo_confirm:"))
    app.add_handler(CallbackQueryHandler(replace_handlers.notify_supervisor, pattern="^notify_sup:"))

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
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_supervisors, pattern="^admin:supervisors$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_supervisor_add, pattern="^admin:supervisoradd$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_supervisor_del, pattern="^admin:supervisordel:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_supervisor_edit, pattern="^admin:supervisoredit:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_reset_users, pattern="^admin:resetusers$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_reset_users_confirm, pattern="^admin:resetusers:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_objaccess, pattern="^admin:objaccess$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.objacc_city, pattern="^objacc:city:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.objacc_company, pattern="^objacc:company:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.objacc_object, pattern="^objacc:object:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.objacc_mode, pattern="^objacc:mode:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.objacc_addchat_prompt, pattern="^objacc:addchat:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.objacc_delchat, pattern="^objacc:delchat:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_digest_now, pattern="^admin:digestnow$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_shiftreport, pattern="^admin:shiftreport$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_reviews, pattern="^admin:reviews$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_reviews_page, pattern="^admin:reviewsp:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_review_detail, pattern="^admin:review:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_review_delete, pattern="^admin:reviewdel:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.shiftrep_city, pattern="^shiftrep:city:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.shiftrep_company, pattern="^shiftrep:company:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.shiftrep_object, pattern="^shiftrep:object:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.shiftrep_shift, pattern="^shiftrep:shift:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.shiftrep_cal_nav, pattern="^shiftrepcal:nav:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.shiftrep_date, pattern="^shiftrepcal:date:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.shiftrep_page, pattern="^shiftrep:page:"))
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
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_users_page, pattern="^admin:usersp:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_users_filterobj, pattern="^admin:users:filterobj$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.usersobj_city, pattern="^usersobj:city:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.usersobj_company, pattern="^usersobj:company:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.usersobj_set, pattern="^usersobj:set:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.usersobj_reset, pattern="^usersobj:reset$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_userban_prompt, pattern="^admin:userban:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_userban_cancel, pattern="^admin:userban_cancel$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_userunban, pattern="^admin:userunban:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_userprofile, pattern="^admin:userprofile:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_warn_prompt, pattern="^admin:warn:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_msg_prompt, pattern="^admin:msg:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.admin_trust_adjust, pattern="^admin:trust:"))

    app.add_handler(CallbackQueryHandler(admin_handlers.admin_catalog, pattern="^admin:catalog$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.catalog_city_menu, pattern="^cat:city:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.catalog_obj_select, pattern="^cat:objselect:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.catalog_pos_select, pattern="^cat:posselect:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.catalog_show_list, pattern="^cat:(companies|objectlist|posobj|positionlist):"))
    app.add_handler(CallbackQueryHandler(admin_handlers.catalog_add_prompt, pattern="^cat:add:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.catalog_rename_prompt, pattern="^cat:ren:"))
    app.add_handler(CallbackQueryHandler(admin_handlers.catalog_del_item, pattern="^cat:del:(companies|objects|positions):"))
    app.add_handler(CallbackQueryHandler(admin_handlers.catalog_add_city_prompt, pattern="^cat:addcity$"))
    app.add_handler(CallbackQueryHandler(admin_handlers.catalog_del_city, pattern="^cat:delcity:"))

    app.add_handler(CallbackQueryHandler(noop_callback, pattern="^noop"))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
