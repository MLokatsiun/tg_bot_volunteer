from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CommandHandler, filters, \
    CallbackQueryHandler
from services.api_client import create_or_activate_category, get_categories, refresh_moderator_token

# Константи для станів
ENTER_CATEGORY_NAME, SELECT_PARENT_CATEGORY, CONFIRM_CREATION = range(3)

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


    refresh_token = user_data.get("moderator_refresh_token")
    if not refresh_token:

        await reset_moderator_to_start_menu(context)
        raise Exception("Refresh token for moderator is missing. Moderator needs to reauthenticate.")

    try:

        tokens = await refresh_moderator_token(refresh_token)
        user_data["moderator_access_token"] = tokens["access_token"]
        user_data["moderator_refresh_token"] = tokens.get("refresh_token", refresh_token)  # Оновлюємо, якщо є новий refresh_token
        return user_data["moderator_access_token"]
    except Exception as e:

        await reset_moderator_to_start_menu(context)
        raise Exception(f"Failed to refresh moderator access token: {e}")

async def reset_moderator_to_start_menu(context: ContextTypes.DEFAULT_TYPE):
    """
    Повертає модератора до початкового меню.
    """
    if "moderator_user_id" in context.user_data:
        del context.user_data["moderator_user_id"]
    if "moderator_access_token" in context.user_data:
        del context.user_data["moderator_access_token"]
    if "moderator_refresh_token" in context.user_data:
        del context.user_data["moderator_refresh_token"]

    await context.bot.send_message(
        chat_id=context.user_data.get("chat_id"),
        text="Термін дії вашого сеансу модератора закінчився. Повертаємось до головного меню.",
        reply_markup=MODERATOR_START_KEYBOARD
    )



async def moderator_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Головне меню для модератора."""
    keyboard = [
        [KeyboardButton("Додати категорію")],
        [KeyboardButton("Видалити категорію")],
        [KeyboardButton("Видалити заявку")],
        [KeyboardButton("Перевірити користувача")],
        [KeyboardButton("Вихід")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Головне меню для модератора:", reply_markup=reply_markup)

async def start_category_creation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запуск створення категорії."""
    keyboard = [[KeyboardButton("Скасувати додавання")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text("Введіть назву категорії:", reply_markup=reply_markup)
    return ENTER_CATEGORY_NAME
from decouple import config
async def get_category_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отримання назви категорії."""
    if update.message:
        category_name = update.message.text.strip()
        if category_name.lower() == "скасувати додавання":
            return await cancel_creation(update, context)

        if not category_name:
            await update.message.reply_text("Назва категорії не може бути порожньою. Введіть назву категорії:")
            return ENTER_CATEGORY_NAME

        context.user_data["category_name"] = category_name
    elif update.callback_query:
        category_name = update.callback_query.data.strip()
        if category_name.lower() == "скасувати додавання":
            return await cancel_creation(update, context)

    client = config("CLIENT_NAME")
    password = config("CLIENT_PASSWORD")

    try:
        categories = await get_categories(client, password)
        keyboard = [
            [InlineKeyboardButton(category["name"], callback_data=str(category["id"]))] for category in categories
        ]
        keyboard.append([InlineKeyboardButton("Пропустити", callback_data="skip")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Оберіть батьківську категорію або натисніть 'Пропустити':", reply_markup=reply_markup)
        return SELECT_PARENT_CATEGORY
    except Exception as e:
        await update.message.reply_text(f"Не вдалося завантажити категорії: {str(e)}")
        await moderator_main_menu(update, context)
        return ConversationHandler.END


async def get_parent_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка вибору батьківської категорії."""
    query = update.callback_query
    await query.answer()
    parent_id = None if query.data == "skip" else int(query.data)

    context.user_data["parent_id"] = parent_id

    category_name = context.user_data["category_name"]
    parent_category_text = "Пропущено" if parent_id is None else f"ID: {parent_id}"

    keyboard = [
        [
            InlineKeyboardButton("Підтвердити", callback_data="confirm"),
            InlineKeyboardButton("Скасувати", callback_data="cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"Ви збираєтесь створити категорію з наступними даними:\n"
        f"Назва: {category_name}\n"
        f"Батьківська категорія: {parent_category_text}\n\n"
        f"Підтвердіть або скасуйте операцію.",
        reply_markup=reply_markup
    )
    return CONFIRM_CREATION


async def cancel_creation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Скасування процесу створення категорії."""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("Процес створення категорії скасовано.")
        chat_id = query.message.chat_id
        await context.bot.send_message(chat_id=chat_id, text="Головне меню для модератора:", reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("Додати категорію")],
            [KeyboardButton("Видалити категорію")],
            [KeyboardButton("Видалити заявку")],
            [KeyboardButton("Перевірити користувача")],
            [KeyboardButton("Вихід")]
        ], resize_keyboard=True, one_time_keyboard=False))
    else:
        await update.message.reply_text("Процес створення категорії скасовано.")
        await moderator_main_menu(update, context)

    return ConversationHandler.END

async def confirm_creation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Підтвердження створення категорії."""
    query = update.callback_query
    await query.answer()

    try:
        access_token = await ensure_valid_moderator_token(context)
    except Exception as e:
        await query.edit_message_text(f"Помилка авторизації: {str(e)}")
        return ConversationHandler.END

    category_name = context.user_data["category_name"]
    parent_id = context.user_data.get("parent_id")

    try:

        result = await create_or_activate_category(category_name, parent_id, access_token)
        await query.edit_message_text(
            f"Категорія успішно створена або активована!\n"
            f"ID: {result['id']}\n"
            f"Назва: {result['name']}\n"
            f"Батьківська категорія: {result.get('parent_id', 'Немає')}"
        )
    except ValueError as e:
        await query.edit_message_text(f"Помилка: {str(e)}")
    except Exception as e:
        await query.edit_message_text(f"Невідома помилка: {str(e)}")

    chat_id = query.message.chat_id
    await context.bot.send_message(chat_id=chat_id, text="Головне меню для модератора:", reply_markup=ReplyKeyboardMarkup([
        [KeyboardButton("Додати категорію")],
        [KeyboardButton("Видалити категорію")],
        [KeyboardButton("Видалити заявку")],
        [KeyboardButton("Перевірити користувача")],
        [KeyboardButton("Вихід")]
    ], resize_keyboard=True, one_time_keyboard=False))

    return ConversationHandler.END




category_creation_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^Додати категорію$"), start_category_creation)],
    states={
        ENTER_CATEGORY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_category_name)],
        SELECT_PARENT_CATEGORY: [CallbackQueryHandler(get_parent_id),
                                 MessageHandler(filters.TEXT & ~filters.COMMAND, get_category_name)],
        CONFIRM_CREATION: [CallbackQueryHandler(confirm_creation, pattern="^confirm$"),
                           CallbackQueryHandler(cancel_creation, pattern="^cancel$")],
    },
    fallbacks=[CommandHandler("cancel", cancel_creation)],
)



