from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
from services.api_client import deactivate_beneficiary_profile, refresh_token_log  # Імпортуємо функцію для деактивації

ENTER_DEACTIVATION_CONFIRMATION_VOLUNTEER = range(1)

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Деактивувати профіль волонтера")],
        [KeyboardButton("Подати заявку")],
        [KeyboardButton("Підтвердити заявку")],
        [KeyboardButton("Деактивувати заявку")],
        [KeyboardButton("Переглянути мої заявки")],
        [KeyboardButton("Вихід")],
    ],
    resize_keyboard=True, one_time_keyboard=False,
)

AUTH_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Стати волонтером"), KeyboardButton("Стати бенефіціаром")],
    ],
    resize_keyboard=True, one_time_keyboard=False,
)


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
        reply_markup=AUTH_KEYBOARD
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


async def start_deactivation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запит на деактивацію профілю волонтера."""
    keyboard = [
        [KeyboardButton("✅ Так, деактивувати мій профіль")],
        [KeyboardButton("❌ Ні, скасувати деактивацію")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "⚠️ Ви впевнені, що хочете деактивувати свій профіль бенефіціара? Це незворотна дія.",
        reply_markup=reply_markup,
    )
    return ENTER_DEACTIVATION_CONFIRMATION_VOLUNTEER


async def confirm_deactivation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Підтвердження деактивації профілю волонтера."""
    text = update.message.text.lower()

    if text == "так, деактивувати мій профіль".lower():
        access_token = await ensure_valid_token(context)

        result = await deactivate_beneficiary_profile(access_token)
        if result:
            await update.message.reply_text("✅ Ваш профіль бенефіціара успішно деактивовано.")

            await update.message.reply_text(
                "🔑 Будь ласка, зареєструйтеся або авторизуйтеся для подальшої роботи:",
                reply_markup=AUTH_KEYBOARD,
            )
        else:
            await update.message.reply_text("⚠️ Сталася помилка при деактивації профілю.")

            await update.message.reply_text("🔙 Повертаюсь до головного меню:", reply_markup=MAIN_KEYBOARD)
    elif text == "ні, скасувати деактивацію".lower():
        await update.message.reply_text("❌ Деактивація профілю волонтера скасована.")

        await update.message.reply_text("🔙 Повертаюсь до головного меню:", reply_markup=MAIN_KEYBOARD)
    else:
        await update.message.reply_text("⚠️ Будь ласка, виберіть одну з наданих опцій.")

    return ConversationHandler.END


deactivation_handler_ben = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^Деактивувати профіль бенефіціара"), start_deactivation)],
    states={
        ENTER_DEACTIVATION_CONFIRMATION_VOLUNTEER: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_deactivation)],
    },
    fallbacks=[],
)
