from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from services.api_client import login_moderator
from decouple import config
ENTER_MODERATOR_CREDENTIALS, MODERATOR_AUTH_COMPLETE = range(2)


CLIENT_NAME = config("CLIENT_NAME")
CLIENT_PASSWORD = config("CLIENT_PASSWORD")


def get_main_menu_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Зареєструватися"), KeyboardButton("Авторизація")],
        [KeyboardButton("Авторизація модератора")]
    ], resize_keyboard=True, one_time_keyboard=True)

async def start_moderator_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Початок авторизації модератора."""
    keyboard = [[KeyboardButton("Скасувати авторизацію")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Введіть ваш номер телефону (модератора) в форматі '380958205750':", reply_markup=reply_markup)
    return ENTER_MODERATOR_CREDENTIALS


async def enter_moderator_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отримання облікових даних модератора та виконання авторизації."""
    if "phone_number" not in context.user_data:
        context.user_data["phone_number"] = update.message.text.strip()
        keyboard = [[KeyboardButton("Скасувати авторизацію")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Введіть ваш пароль:", reply_markup=reply_markup)
        return ENTER_MODERATOR_CREDENTIALS
    else:
        context.user_data["password"] = update.message.text.strip()

    login_request = {
        "phone_number": context.user_data["phone_number"],
        "password": context.user_data["password"],
        "client": CLIENT_NAME,
        "client_password": CLIENT_PASSWORD
    }

    try:
        response = await login_moderator(login_request)
        access_token = response["access_token"]
        refresh_token = response["refresh_token"]

        context.user_data["access_token"] = access_token
        context.user_data["refresh_token"] = refresh_token

        await update.message.reply_text(
            "Авторизація успішна! 🎉 Ви увійшли як модератор.",
        )

        await moderator_main_menu(update, context)

        return ConversationHandler.END
    except ValueError as e:
        await update.message.reply_text(f"Помилка даних: {str(e)}. Спробуйте ще раз.")
        keyboard = [[KeyboardButton("Скасувати авторизацію")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Введіть ваш номер телефону (модератора) в форматі '380958205750':", reply_markup=reply_markup)
        return ENTER_MODERATOR_CREDENTIALS
    except PermissionError as e:
        await update.message.reply_text(f"Доступ заборонено: {str(e)}. Зверніться до адміністратора.")
        await update.message.reply_text("Зверніться до адміністратора для вирішення цієї проблеми.")
        await update.message.reply_text("Головне меню:", reply_markup=get_main_menu_keyboard())
        return ConversationHandler.END
    except Exception as e:
        print(f"Unexpected error: {str(e)}")  # Логування
        await update.message.reply_text(f"Сталася помилка: {str(e)}. Спробуйте пізніше.")
        await update.message.reply_text("Головне меню:", reply_markup=get_main_menu_keyboard())
        return ConversationHandler.END


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



async def cancel_moderator_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Скасування авторизації модератора."""

    if update.message.text == "Скасувати авторизацію":
        await update.message.reply_text("Авторизацію скасовано.")
        await update.message.reply_text("Головне меню:", reply_markup=get_main_menu_keyboard())
        return ConversationHandler.END


moderator_auth_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^Авторизація модератора$"), start_moderator_auth)],
    states={
        ENTER_MODERATOR_CREDENTIALS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^Скасувати авторизацію$"), enter_moderator_credentials),
            MessageHandler(filters.Regex("^Скасувати авторизацію$"), cancel_moderator_auth)
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel_moderator_auth), MessageHandler(filters.Regex("^Скасувати авторизацію$"), cancel_moderator_auth)],
)
