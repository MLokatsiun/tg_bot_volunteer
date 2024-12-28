from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from services.api_client import get_applications_by_status, cancel_application, refresh_token_log

CHOOSE_CANCEL_APPLICATION, CONFIRM_CANCEL_APPLICATION = range(2)

PAGE_SIZE = 5

async def ensure_valid_token(context: ContextTypes.DEFAULT_TYPE) -> str:
    user_data = context.user_data

    refresh_token = user_data.get("refresh_token")
    if not refresh_token:
        await reset_to_start_menu(context)
        raise Exception("Refresh token is missing. User needs to reauthenticate.")

    try:
        tokens = await refresh_token_log(refresh_token)
        user_data["access_token"] = tokens["access_token"]
        user_data["refresh_token"] = tokens.get("refresh_token", refresh_token)
        return user_data["access_token"]
    except Exception as e:

        await reset_to_start_menu(context)
        raise Exception(f"Failed to refresh access token: {e}")


async def reset_to_start_menu(context: ContextTypes.DEFAULT_TYPE):
    """
    Повертає користувача до початкового меню.
    """
    if "user_id" in context.user_data:
        del context.user_data["user_id"]
    if "access_token" in context.user_data:
        del context.user_data["access_token"]
    if "refresh_token" in context.user_data:
        del context.user_data["refresh_token"]

    await context.bot.send_message(
        chat_id=context.user_data.get("chat_id"),
        text="Термін дії вашого сеансу закінчився. Повертаємось до головного меню.",
        reply_markup=START_KEYBOARD
    )
START_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Стати волонтером")],
        [KeyboardButton("Стати бенефіціаром")],
    ],
    resize_keyboard=True, one_time_keyboard=False
)

async def start_cancel_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Початок процесу скасування заявки."""
    try:
        access_token = await ensure_valid_token(context)
    except Exception as e:
        await update.message.reply_text(f"❌ Помилка: {str(e)}")
        return ConversationHandler.END

    try:
        applications = await get_applications_by_status(access_token, status="in_progress")
        if not applications:
            await update.message.reply_text("ℹ️ Наразі немає заявок в процесі виконання.")
            return ConversationHandler.END

        context.user_data["applications_list"] = applications
        context.user_data["current_page"] = 0

        await display_application_page(update, context)
        return CHOOSE_CANCEL_APPLICATION

    except PermissionError as e:
        await update.message.reply_text(f"⛔ Помилка доступу: {str(e)}")
    except Exception as e:
        await update.message.reply_text(f"❌ Сталася помилка: {str(e)}")

    return ConversationHandler.END


def get_paginated_keyboard(applications, page, page_size):
    """Створення клавіатури для заявок із пагінацією."""
    start = page * page_size
    end = start + page_size
    current_apps = applications[start:end]

    keyboard = [
        [InlineKeyboardButton(f"🆔 ID: {app['id']} | 📝 {app['description']}", callback_data=f"app_{app['id']}")]
        for app in current_apps
    ]

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data="prev_page"))
    if end < len(applications):
        nav_buttons.append(InlineKeyboardButton("➡️ Вперед", callback_data="next_page"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    return InlineKeyboardMarkup(keyboard)


async def display_application_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Відображення поточної сторінки заявок."""
    applications = context.user_data["applications_list"]
    page = context.user_data["current_page"]
    reply_markup = get_paginated_keyboard(applications, page, PAGE_SIZE)

    if hasattr(update, "callback_query") and update.callback_query:
        await update.callback_query.edit_message_text(
            "📝 Виберіть заявку зі списку для скасування:",
            reply_markup=reply_markup,
        )
    else:
        await update.message.reply_text("📝 Виберіть заявку зі списку для скасування:", reply_markup=reply_markup)


async def navigate_pages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка переходів між сторінками."""
    query = update.callback_query
    await query.answer()

    if query.data == "prev_page":
        context.user_data["current_page"] -= 1
    elif query.data == "next_page":
        context.user_data["current_page"] += 1

    await display_application_page(update, context)
    return CHOOSE_CANCEL_APPLICATION


async def choose_cancel_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка вибору заявки для скасування."""
    query = update.callback_query
    await query.answer()

    if not query.data.startswith("app_"):
        await query.edit_message_text(
            "⚠️ Неправильний вибір. Будь ласка, скористайтеся кнопками для вибору заявки."
        )
        return CHOOSE_CANCEL_APPLICATION

    application_id = query.data.removeprefix("app_")

    context.user_data["selected_application_id"] = application_id

    keyboard = [
        [
            InlineKeyboardButton("✅ Підтвердити", callback_data="confirm_cancel"),
            InlineKeyboardButton("❌ Скасувати", callback_data="cancel_action"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=f"❓ Ви вибрали заявку з ID: {application_id}. Ви дійсно хочете скасувати виконання заявки?",
        reply_markup=reply_markup,
    )
    return CONFIRM_CANCEL_APPLICATION


async def confirm_cancel_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Підтвердження скасування заявки."""
    query = update.callback_query
    await query.answer()

    application_id = context.user_data.get("selected_application_id")
    access_token = context.user_data.get("access_token")

    if not application_id:
        await query.edit_message_text("⚠️ Виберіть заявку перед підтвердженням скасування.")
        return ConversationHandler.END

    try:
        access_token = await ensure_valid_token(context)

        response = await cancel_application(access_token, int(application_id))
        if response.get("status") == "Application cancelled successfully":
            await query.edit_message_text(f"✅ Заявка з ID: {application_id} успішно скасована.")
        else:
            await query.edit_message_text(
                f"❌ Не вдалося скасувати заявку. Повідомлення: {response.get('detail', 'Невідома помилка')}"
            )

    except Exception as e:
        await query.edit_message_text(f"❌ Сталася помилка: {str(e)}")

    return ConversationHandler.END


async def cancel_cancel_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Скасування процесу скасування заявки."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("ℹ️ Скасування заявки було скасовано.")
    return ConversationHandler.END



cancel_application_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^Скасувати заявку$"), start_cancel_application)],
    states={
        CHOOSE_CANCEL_APPLICATION: [
            CallbackQueryHandler(choose_cancel_application, pattern="^app_\\d+$"),
            CallbackQueryHandler(navigate_pages, pattern="^(prev_page|next_page)$"),
        ],
        CONFIRM_CANCEL_APPLICATION: [
            CallbackQueryHandler(confirm_cancel_application, pattern="^confirm_cancel$"),
            CallbackQueryHandler(cancel_cancel_application, pattern="^cancel_action$"),
        ],
    },
    fallbacks=[CallbackQueryHandler(cancel_cancel_application)],
)
