from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from services.api_client import get_applications_by_type, confirm_application, refresh_token_log


CHOOSE_FINISHED_APPLICATION, CONFIRM_APPLICATION = range(2)



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
        text="❗️Термін дії вашого сеансу закінчився. Повертаємось до головного меню.",
        reply_markup=START_KEYBOARD
    )


async def start_confirming_finished_applications(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Початок процесу підтвердження завершених заявок."""
    if not context.user_data.get("access_token"):
        await update.message.reply_text("❌ Ви не авторизовані. Спочатку виконайте вхід до системи.")
        return ConversationHandler.END


    access_token = await ensure_valid_token(context)

    try:

        applications = await get_applications_by_type(access_token, application_type="complete", role="beneficiary")
        if not applications:
            await update.message.reply_text("🔍 Наразі немає завершених заявок для підтвердження.")
            return ConversationHandler.END


        keyboard = [
            [InlineKeyboardButton(f"ID: {app['id']} | {app['description']}", callback_data=str(app["id"]))]
            for app in applications
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("📋 Оберіть завершену заявку зі списку для підтвердження:", reply_markup=reply_markup)

        return CHOOSE_FINISHED_APPLICATION


    except PermissionError as e:
        await update.message.reply_text(f"🚫 Помилка доступу: {str(e)}")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Сталася помилка: {str(e)}")
    return ConversationHandler.END

async def choose_finished_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка вибору завершеної заявки користувачем."""
    query = update.callback_query
    await query.answer()
    application_id = query.data


    print(f"Selected application ID: {application_id}")


    context.user_data["selected_application_id"] = application_id

    keyboard = [
        [InlineKeyboardButton("✅ Підтвердити", callback_data="confirm")],
        [InlineKeyboardButton("❌ Скасувати", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=f"📝 Ви вибрали заявку з ID: {application_id}. Підтвердьте її виконання або скасуйте:",
        reply_markup=reply_markup
    )
    return CONFIRM_APPLICATION

async def confirm_finished_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Підтвердження виконання заявки."""
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        await query.edit_message_text("🚫 Підтвердження заявки скасовано.")
        return ConversationHandler.END

    application_id = context.user_data.get("selected_application_id")


    print(f"Retrieved application ID: {application_id}")

    if not application_id:
        await query.edit_message_text("⚠️ Помилка: ID заявки не знайдено. Спробуйте знову.")
        return ConversationHandler.END

    try:

        access_token = await ensure_valid_token(context)
    except Exception as e:
        await query.edit_message_text(f"🚨 Сталася помилка при перевірці токена: {str(e)}")
        return ConversationHandler.END

    try:

        application_id = int(application_id)
        print(f"Confirming application with ID: {application_id}")


        await confirm_application(application_id=application_id, access_token=access_token)
        await query.edit_message_text(f"✅ Заявка з ID {application_id} успішно підтверджена!")
    except ValueError:
        await query.edit_message_text("⚠️ Помилка: ID заявки має бути числовим.")
    except Exception as e:
        await query.edit_message_text(f"⚠️ Сталася помилка: {str(e)}")

    return ConversationHandler.END


async def cancel_confirming_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Скасування підтвердження заявки."""
    await update.message.reply_text("❌ Процес підтвердження заявки скасовано.")
    return ConversationHandler.END


finished_application_confirmation_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^Підтвердити заявку$"), start_confirming_finished_applications)],
    states={
        CHOOSE_FINISHED_APPLICATION: [CallbackQueryHandler(choose_finished_application)],
        CONFIRM_APPLICATION: [CallbackQueryHandler(confirm_finished_application)],
    },
    fallbacks=[CommandHandler("cancel", cancel_confirming_application)],
)
