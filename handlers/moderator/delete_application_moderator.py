from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from services.api_client import deactivate_application, refresh_moderator_token

# Стани для ConversationHandler
ENTER_APPLICATION_ID = range(1)

MODERATOR_START_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Стати волонтером"), KeyboardButton("Стати бенефіціаром")],
        [KeyboardButton("Авторизація модератора")]
    ],
    resize_keyboard=True, one_time_keyboard=False
)

async def ensure_valid_moderator_token(context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    Перевіряє дійсність access_token для модератора і оновлює його за потреби.
    """
    user_data = context.user_data

    refresh_token = user_data.get("refresh_token")
    if not refresh_token:

        await reset_moderator_to_start_menu(context)
        raise Exception("Refresh token for moderator is missing. Moderator needs to reauthenticate.")

    try:
        tokens = await refresh_moderator_token(refresh_token)
        user_data["access_token"] = tokens["access_token"]
        user_data["refresh_token"] = tokens.get("refresh_token", refresh_token)
        return user_data["access_token"]
    except Exception as e:

        await reset_moderator_to_start_menu(context)
        raise Exception(f"Failed to refresh moderator access token: {e}")

async def reset_moderator_to_start_menu(context: ContextTypes.DEFAULT_TYPE):
    """
    Повертає модератора до початкового меню.
    """
    if "moderator_user_id" in context.user_data:
        del context.user_data["moderator_user_id"]
    if "access_token" in context.user_data:
        del context.user_data["access_token"]
    if "refresh_token" in context.user_data:
        del context.user_data["refresh_token"]

    await context.bot.send_message(
        chat_id=context.user_data.get("chat_id"),
        text="Термін дії вашого сеансу модератора закінчився. Повертаємось до головного меню.",
        reply_markup=MODERATOR_START_KEYBOARD
    )

async def start_deactivate_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Початок процесу деактивації заявки."""

    try:
        access_token = await ensure_valid_moderator_token(context)
    except Exception as e:
        await update.message.reply_text(f"Помилка авторизації: {str(e)}")
        return ConversationHandler.END

    await update.message.reply_text("Будь ласка, введіть ID заявки, яку потрібно деактивувати:")
    return ENTER_APPLICATION_ID

async def handle_application_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка введеного ID заявки та виклик API для деактивації."""

    try:
        access_token = await ensure_valid_moderator_token(context)
    except Exception as e:
        await update.message.reply_text(f"Помилка авторизації: {str(e)}")
        return ConversationHandler.END

    try:
        application_id = int(update.message.text.strip())

        response = await deactivate_application(application_id, access_token)

        await update.message.reply_text(response.get("detail", "Заявка успішно деактивована."))
    except ValueError as e:
        await update.message.reply_text(f"Помилка: {str(e)}")
    except PermissionError as e:
        await update.message.reply_text(f"Доступ заборонено: {str(e)}")
    except Exception as e:
        await update.message.reply_text(f"Сталася помилка: {str(e)}. Спробуйте пізніше.")

    return ConversationHandler.END


async def cancel_deactivation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Скасування процесу деактивації."""
    await update.message.reply_text("Процес деактивації скасовано.")
    return ConversationHandler.END


deactivate_application_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^Видалити заявку$"), start_deactivate_application)],
    states={
        ENTER_APPLICATION_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_application_id)],
    },
    fallbacks=[CommandHandler("cancel", cancel_deactivation)],
)
