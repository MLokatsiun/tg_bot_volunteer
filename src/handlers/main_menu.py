from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Головне меню для користувача після реєстрації."""
    role_id = context.user_data.get("role_id")

    # Створення клавіатури для волонтера
    if role_id == 2:  # Волонтер
        keyboard = [
            [KeyboardButton("Список задач")],
            [KeyboardButton("Підтвердити виконання задач")],
            [KeyboardButton("Переглянути профіль")],
            [KeyboardButton("Деактивувати профіль")],  # Додаємо кнопку деактивації
            [KeyboardButton("Вийти")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Головне меню для волонтера:", reply_markup=reply_markup)

    # Створення клавіатури для бенефіціара
    elif role_id == 1:  # Бенефіціар
        keyboard = [
            [KeyboardButton("Переглянути волонтерів")],
            [KeyboardButton("Створити новий запит")],
            [KeyboardButton("Переглянути профіль")],
            [KeyboardButton("Вихід")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Головне меню для бенефіціара:", reply_markup=reply_markup)


