from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ConversationHandler, ContextTypes


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Скасування процесу та повернення до головного меню."""
    # Кнопки для стартового меню
    keyboard = [
        [KeyboardButton("Авторизація"), KeyboardButton("Зареєструватися")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    # Відправляємо повідомлення з меню
    if update.message:
        await update.message.reply_text(
            "Процес скасовано. Ви повернулись до головного меню.",
            reply_markup=reply_markup
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            "Процес скасовано. Ви повернулись до головного меню."
        )
        await update.callback_query.message.reply_text(
            "Оберіть одну з опцій:",
            reply_markup=reply_markup
        )
    return ConversationHandler.END

cancel_handler = CallbackQueryHandler(cancel, pattern="^Скасувати$")