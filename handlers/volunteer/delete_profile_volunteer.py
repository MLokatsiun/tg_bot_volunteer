from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler
from services.api_client import deactivate_volunteer_account, refresh_token_log  # Імпортуємо функцію для деактивації


ENTER_DEACTIVATION_CONFIRMATION_PROF = 1


VOLUNTEER_MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Список завдань")],
        [KeyboardButton("Прийняти заявку в обробку")],
        [KeyboardButton("Закрити заявку")],
        [KeyboardButton("Скасувати заявку")],
        [KeyboardButton("Редагувати профіль")],  # Кнопка для редагування профілю
        [KeyboardButton("Деактивувати профіль волонтера")],  # Кнопка для деактивації профілю
        [KeyboardButton("Вихід")]
    ],
    resize_keyboard=True, one_time_keyboard=False,
)
AUTH_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Стати волонтером"), KeyboardButton("Стати бенефіціаром")],
    ],
    resize_keyboard=True, one_time_keyboard=False,
)

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

async def start_deactivation_prof(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запит на деактивацію профілю."""
    try:
        await ensure_valid_token(context)

        keyboard = [
            [KeyboardButton("Так, деактивувати мій профіль")],
            [KeyboardButton("Ні, скасувати деактивацію")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(
            "⚠️ Ви впевнені, що хочете деактивувати свій профіль?",
            reply_markup=reply_markup
        )
        return ENTER_DEACTIVATION_CONFIRMATION_PROF
    except Exception as e:
        await update.message.reply_text(f"Помилка авторизації: {e}. Спробуйте увійти до системи.")
        return ConversationHandler.END



async def confirm_deactivation_prof(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Підтвердження деактивації профілю."""
    text = update.message.text.lower()
    if "деактивувати" in text:
        try:
            access_token = await ensure_valid_token(context)
            result = await deactivate_volunteer_account(access_token)

            if result:

                context.user_data.clear()

                await update.message.reply_text("✅ Ваш профіль успішно деактивовано.")
                await update.message.reply_text(
                    "🔑 Будь ласка, зареєструйтеся або авторизуйтеся для подальшої роботи:",
                    reply_markup=AUTH_KEYBOARD,
                )
            else:
                raise RuntimeError("❌Не вдалося виконати деактивацію профілю.")
        except Exception as e:
            await update.message.reply_text(f"❌Помилка: {e}. Повертаю вас до головного меню.",
                                            reply_markup=VOLUNTEER_MAIN_KEYBOARD)
        return ConversationHandler.END
    elif "скасувати" in text:
        await update.message.reply_text("❌Деактивація профілю скасована.")
        await update.message.reply_text("🔙Повертаю вас до головного меню:", reply_markup=VOLUNTEER_MAIN_KEYBOARD)
        return ConversationHandler.END
    else:
        await update.message.reply_text("⚠️ Будь ласка, виберіть одну з наданих опцій.")
        return ENTER_DEACTIVATION_CONFIRMATION_PROF




async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user cancellation."""
    await update.message.reply_text("Операція скасована.")
    return ConversationHandler.END


deactivation_handler_vol = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^Деактивувати профіль волонтера$"), start_deactivation_prof)],
    states={
        ENTER_DEACTIVATION_CONFIRMATION_PROF: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_deactivation_prof)],
    },
    fallbacks=[MessageHandler(filters.COMMAND, cancel)],
)
