from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters,
)
from services.api_client import get_applications_by_type, delete_application, refresh_token_log

CHOOSE_ACCESSIBLE_APPLICATION, CONFIRM_DELETE = range(2)

START_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Стати волонтером")],
        [KeyboardButton("Стати бенефіціаром")],
    ],
    resize_keyboard=True, one_time_keyboard=False
)


async def ensure_valid_token(context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    Перевіряє дійсність access_token і оновлює його за потреби.
    """
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


async def start_accessible_application_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Початок процесу видалення заявок з типом `accessible`."""
    if not context.user_data.get("access_token"):
        await update.message.reply_text("Ви не авторизовані. Спочатку виконайте вхід до системи.")
        return ConversationHandler.END

    access_token = await ensure_valid_token(context)

    try:

        applications = await get_applications_by_type(access_token, application_type="accessible", role="beneficiary")
        if not applications:
            await update.message.reply_text("Наразі немає доступних заявок для видалення.")
            return ConversationHandler.END

        keyboard = [
            [InlineKeyboardButton(f"ID: {app['id']} | {app['description']}", callback_data=str(app["id"]))]
            for app in applications
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Оберіть заявку зі списку для видалення:", reply_markup=reply_markup)

        return CHOOSE_ACCESSIBLE_APPLICATION

    except PermissionError as e:
        await update.message.reply_text(f"Помилка доступу: {str(e)}")
    except Exception as e:
        await update.message.reply_text(f"Сталася помилка: {str(e)}")

    return ConversationHandler.END


async def choose_accessible_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка вибору заявки користувачем."""
    query = update.callback_query
    await query.answer()
    application_id = query.data

    context.user_data["application_id"] = application_id

    keyboard = [
        [InlineKeyboardButton("Підтвердити видалення", callback_data="confirm_delete")],
        [InlineKeyboardButton("Скасувати", callback_data="cancel_delete")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=f"Ви вибрали заявку з ID: {application_id}. Ви дійсно хочете її видалити?",
        reply_markup=reply_markup
    )
    return CONFIRM_DELETE


async def confirm_accessible_application_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Підтвердження видалення заявки."""
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_delete":
        await query.edit_message_text("Видалення заявки скасовано.")
        return ConversationHandler.END

    application_id = context.user_data.get("application_id")

    if not application_id:
        await query.edit_message_text("Помилка: ID заявки не знайдено. Спробуйте знову.")
        return ConversationHandler.END

    access_token = await ensure_valid_token(context)

    try:

        await delete_application(application_id=int(application_id), access_token=access_token)
        await query.edit_message_text(f"Заявка з ID {application_id} успішно видалена!")
    except Exception as e:
        await query.edit_message_text(f"Сталася помилка: {str(e)}")

    return ConversationHandler.END


async def cancel_accessible_application_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Скасування видалення заявки."""
    await update.message.reply_text("Процес видалення заявки скасовано.")
    return ConversationHandler.END


accessible_application_deletion_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^Деактивувати заявку$"), start_accessible_application_deletion)],
    states={
        CHOOSE_ACCESSIBLE_APPLICATION: [CallbackQueryHandler(choose_accessible_application)],
        CONFIRM_DELETE: [CallbackQueryHandler(confirm_accessible_application_deletion)],
    },
    fallbacks=[CommandHandler("cancel", cancel_accessible_application_deletion)],
)
