from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, \
    filters
from services.api_client import deactivate_category, get_categories, refresh_moderator_token


SELECT_CATEGORY, CONFIRM_DEACTIVATION = range(1, 3)

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
        user_data["refresh_token"] = tokens.get("refresh_token",
                                                          refresh_token)
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
from decouple import config
async def start_category_deactivation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запуск процесу деактивації категорії з вибором через кнопки."""
    client = config("CLIENT_NAME")
    password = config("CLIENT_PASSWORD")

    try:

        categories = await get_categories(client, password)

        if not categories:
            await update.message.reply_text("Немає доступних категорій для деактивації.")
            return ConversationHandler.END


        keyboard = [
            [InlineKeyboardButton(f"{category['name']} (Parent ID: {category['parent_id']})",
                                  callback_data=str(category['id']))]
            for category in categories
        ]


        await update.message.reply_text(
            "Виберіть категорію для деактивації:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return SELECT_CATEGORY
    except Exception as e:
        await update.message.reply_text(f"Помилка при отриманні категорій: {str(e)}")
        return ConversationHandler.END


async def category_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка вибору категорії для деактивації через кнопки."""
    query = update.callback_query
    category_id = int(query.data)
    context.user_data['category_id'] = category_id


    client = config("CLIENT_NAME")
    password = config("CLIENT_PASSWORD")
    categories = await get_categories(client, password)

    selected_category = next((category for category in categories if category["id"] == category_id), None)
    if selected_category:
        name = selected_category["name"]
        parent_id = selected_category["parent_id"]


        keyboard = [
            [InlineKeyboardButton("Підтвердити", callback_data="confirm"),
             InlineKeyboardButton("Скасувати", callback_data="cancel")]
        ]
        await query.answer()
        await query.edit_message_text(
            f"Ви дійсно хочете деактивувати категорію: {name} (Parent ID: {parent_id})?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CONFIRM_DEACTIVATION
    else:
        await query.answer()
        await query.edit_message_text("Категорія не знайдена.")
        return ConversationHandler.END


async def confirm_deactivation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Підтвердження деактивації категорії."""
    query = update.callback_query
    action = query.data


    try:
        access_token = await ensure_valid_moderator_token(context)
    except Exception as e:
        await query.answer()
        await query.edit_message_text(f"Помилка авторизації: {str(e)}")
        return ConversationHandler.END

    if action == "confirm":
        category_id = context.user_data.get('category_id')

        try:
            result = await deactivate_category(category_id, access_token)
            await query.answer()
            await query.edit_message_text(result["detail"])
        except ValueError as e:
            await query.answer()
            await query.edit_message_text(f"Помилка: {str(e)}")
        except Exception as e:
            await query.answer()
            await query.edit_message_text(f"Невідома помилка: {str(e)}")
    else:
        await query.answer()
        await query.edit_message_text("Процес деактивації скасовано.")

    return ConversationHandler.END



async def cancel_deactivation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Скасування процесу деактивації категорії."""
    await update.message.reply_text("Процес деактивації категорії скасовано.")
    return ConversationHandler.END


category_deactivation_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^Видалити категорію$"), start_category_deactivation)],
    states={
        SELECT_CATEGORY: [CallbackQueryHandler(category_selection_handler)],  # Handler for selecting category
        CONFIRM_DEACTIVATION: [
            CallbackQueryHandler(confirm_deactivation, pattern="^(confirm|cancel)$")  # Handle confirmation or cancel
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel_deactivation)],
)
