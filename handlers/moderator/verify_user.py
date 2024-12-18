from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from services.api_client import verify_user, get_customers

CHOOSE_ROLE, CHOOSE_USER = range(2)


MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("Додати категорію")],
        [KeyboardButton("Видалити категорію")],
        [KeyboardButton("Видалити заявку")],
        [KeyboardButton("Перевірити користувача")],
        [KeyboardButton("Вихід")],
    ],
    resize_keyboard=True, one_time_keyboard=False
)

async def start_verify_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Початок процесу верифікації користувача."""
    access_token = context.user_data.get("access_token")
    refresh_token = context.user_data.get("refresh_token")

    if not access_token or not refresh_token:
        await update.message.reply_text("Вам потрібно авторизуватись як модератор.", reply_markup=MAIN_MENU_KEYBOARD)
        return ConversationHandler.END

    role_keyboard = ReplyKeyboardMarkup(
        [["Верифікувати волонтерів"], ["Верифікувати бенефіціарів"], ["Скасувати"]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await update.message.reply_text("Оберіть роль, яку потрібно верифікувати:", reply_markup=role_keyboard)
    return CHOOSE_ROLE

async def cancel_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Загальна функція для скасування процесу."""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("Процес верифікації скасовано. Повертаємося до головного меню.")
    else:
        await update.message.reply_text("Процес верифікації скасовано. Повертаємося до головного меню.", reply_markup=MAIN_MENU_KEYBOARD)

    return ConversationHandler.END

async def choose_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка вибору ролі користувача."""
    role_text = update.message.text
    access_token = context.user_data.get("access_token")

    if role_text == "Скасувати":
        return await cancel_process(update, context)

    role_id = 2 if role_text == "Верифікувати волонтерів" else 1 if role_text == "Верифікувати бенефіціарів" else None

    if role_id is None:
        await update.message.reply_text("Невірний вибір. Спробуйте ще раз.")
        return CHOOSE_ROLE

    try:
        users = await get_customers("https://bot.bckwdd.fun")
        filtered_users = [user for user in users if user["role"] == role_id]

        if not filtered_users:
            await update.message.reply_text(f"Немає доступних користувачів із роллю '{role_text}'.", reply_markup=MAIN_MENU_KEYBOARD)
            return ConversationHandler.END

        context.user_data["users"] = filtered_users

        keyboard = [
            [InlineKeyboardButton(f"{user['firstname']} {user['lastname']} (ID: {user['id']})", callback_data=str(user["id"]))]
            for user in filtered_users
        ]
        keyboard.append([InlineKeyboardButton("Скасувати", callback_data="cancel")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("Оберіть користувача зі списку:", reply_markup=reply_markup)
        return CHOOSE_USER

    except Exception as e:
        await update.message.reply_text(f"Сталася помилка: {str(e)}", reply_markup=MAIN_MENU_KEYBOARD)
        return ConversationHandler.END

async def handle_user_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка вибору користувача."""
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        return await cancel_process(update, context)

    user_id = int(query.data)
    users = context.user_data.get("users", [])
    selected_user = next((user for user in users if user["id"] == user_id), None)

    if not selected_user:
        await query.edit_message_text("Обраного користувача не знайдено. Спробуйте ще раз.")
        return CHOOSE_USER

    context.user_data["selected_user"] = selected_user

    await query.edit_message_text(
        f"Ви обрали користувача:\n"
        f"Ім'я: {selected_user['firstname']} {selected_user['lastname']}\n"
        f"Телефон: {selected_user['phone_num']}\n"
        f"Роль: {selected_user['role']}\n\n"
        "Підтвердити верифікацію?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Підтвердити", callback_data="confirm")],
            [InlineKeyboardButton("Скасувати", callback_data="cancel")]
        ])
    )
    return CHOOSE_USER

async def confirm_verification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Підтвердження верифікації користувача."""
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        # Скасування процесу
        await query.edit_message_text(
            "Процес верифікації скасовано. Повертаємося до головного меню."
        )
        await query.message.reply_text("Головне меню:", reply_markup=MAIN_MENU_KEYBOARD)
        return ConversationHandler.END

    selected_user = context.user_data.get("selected_user")
    access_token = context.user_data.get("access_token")
    refresh_token = context.user_data.get("refresh_token")
    refresh_url = "https://bot.bckwdd.fun/moderator/refresh-token/"  # URL для оновлення токенів (змінити, якщо інший)

    try:
        # Спроба верифікації користувача
        response = await verify_user(
            user_id=selected_user["id"],
            is_verified=True,
            access_token=access_token,
            refresh_token=refresh_token,
            refresh_url=refresh_url,
        )
        await query.edit_message_text(
            f"Користувача успішно верифіковано:\n"
            f"ID: {response['id']}\n"
            f"Статус: Підтверджено ✅"
        )
        await query.message.reply_text("Головне меню:", reply_markup=MAIN_MENU_KEYBOARD)
    except Exception as e:
        # Обробка помилки
        await query.edit_message_text(f"Сталася помилка: {str(e)}")
        await query.message.reply_text("Головне меню:", reply_markup=MAIN_MENU_KEYBOARD)

    return ConversationHandler.END




verify_user_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^Перевірити користувача$"), start_verify_user)],
    states={
        CHOOSE_ROLE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, choose_role),
            MessageHandler(filters.Regex("^Скасувати$"), cancel_process),
        ],
        CHOOSE_USER: [
            CallbackQueryHandler(handle_user_selection, pattern="^\d+$"),
            CallbackQueryHandler(confirm_verification, pattern="^confirm$"),
            CallbackQueryHandler(cancel_process, pattern="^cancel$"),
            MessageHandler(filters.Regex("^Скасувати$"), cancel_process),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel_process)],
)