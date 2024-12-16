from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from services.api_client import login_user
from decouple import config

ENTER_ROLE, AUTH_COMPLETE = range(2)


CLIENT_NAME = config("CLIENT_NAME")
CLIENT_PASSWORD = config("CLIENT_PASSWORD")



async def start_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Початок авторизації."""

    tg_id = update.effective_user.id
    context.user_data["tg_id"] = tg_id


    keyboard = [
        [KeyboardButton("Бенефіціар"), KeyboardButton("Волонтер")],
        [KeyboardButton("Скасувати авторизацію")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "Виберіть вашу роль:", reply_markup=reply_markup
    )
    return ENTER_ROLE


async def enter_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отримання ролі користувача та виконання авторизації."""
    role_text = update.message.text.lower()
    if role_text == "бенефіціар":
        context.user_data["role_id"] = 1
    elif role_text == "волонтер":
        context.user_data["role_id"] = 2
    else:
        await update.message.reply_text("Некоректний вибір ролі. Оберіть одну з опцій:")
        return ENTER_ROLE


    login_request = {
        "tg_id": str(context.user_data["tg_id"]),
        "role_id": context.user_data["role_id"],
        "client": CLIENT_NAME,
        "password": CLIENT_PASSWORD,
    }

    try:

        response = await login_user(login_request)
        access_token = response["access_token"]
        refresh_token = response["refresh_token"]


        context.user_data["access_token"] = access_token
        context.user_data["refresh_token"] = refresh_token

        await update.message.reply_text("Авторизація успішна! 🎉 Ви тепер можете користуватися ботом.")


        await main_menu(update, context)

        return ConversationHandler.END
    except ValueError as e:
        await update.message.reply_text(f"Помилка даних: {str(e)}. Уточніть ваші дані й спробуйте ще раз.",
                                        reply_markup=ReplyKeyboardMarkup(
                                            keyboard=[[KeyboardButton("Стати волонтером"), KeyboardButton("Стати бенефіціаром")]],
                                            resize_keyboard=True, one_time_keyboard=False
                                        ))
        return ConversationHandler.END
    except PermissionError as e:
        await update.message.reply_text(f"Доступ заборонено: {str(e)}. Зверніться до служби підтримки.",
                                        reply_markup=ReplyKeyboardMarkup(
                                            keyboard=[
                                                [KeyboardButton("Стати волонтером"), KeyboardButton("Стати бенефіціаром")]],
                                            resize_keyboard=True, one_time_keyboard=False
                                        ))

        return ConversationHandler.END
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        await update.message.reply_text(f"Сталася помилка: {str(e)}. Спробуйте пізніше.",
                                        reply_markup=ReplyKeyboardMarkup(
                                            keyboard=[
                                                [KeyboardButton("Стати волонтером"), KeyboardButton("Стати бенефіціаром")]],
                                            resize_keyboard=True, one_time_keyboard=False
                                        ))

        return ConversationHandler.END

async def cancel_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Скасування авторизації."""
    keyboard = [[KeyboardButton("Стати волонтером"), KeyboardButton("Стати бенефіціаром")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text("Авторизацію скасовано.",
                                    reply_markup=reply_markup)
    return ConversationHandler.END

auth_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^Авторизація$"), start_auth)],
    states={
        ENTER_ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^Скасувати авторизацію$"), enter_role)],
    },
    fallbacks=[MessageHandler(filters.Regex("^Скасувати авторизацію$"), cancel_auth)],
)

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Головне меню для користувача після реєстрації."""
    role_id = context.user_data.get("role_id")

    if role_id == 2:
        keyboard = [
            [KeyboardButton("Список завдань")],
            [KeyboardButton("Прийняти заявку в обробку")],
            [KeyboardButton("Закрити заявку")],
            [KeyboardButton("Скасувати заявку")],
            [KeyboardButton("Редагувати профіль")],
            [KeyboardButton("Деактивувати профіль волонтера")],
            [KeyboardButton("Вихід")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Головне меню для волонтера:", reply_markup=reply_markup)

    elif role_id == 1:
        keyboard = [
            [KeyboardButton("Деактивувати профіль бенефіціара")],
            [KeyboardButton("Подати заявку")],
            [KeyboardButton("Підтвердити заявку")],
            [KeyboardButton("Деактивувати заявку")],
            [KeyboardButton("Переглянути мої заявки")],
            [KeyboardButton("Вихід")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Головне меню для бенефіціара:", reply_markup=reply_markup)


async def handle_exit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробка кнопки 'Вийти'. Повертає користувача до сторінки авторизації та реєстрації."""

    context.user_data.clear()


    keyboard = [
        [KeyboardButton("Стати волонтером"), KeyboardButton("Стати бенефіціаром")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


    await update.message.reply_text("Ви вийшли з облікового запису. Будь ласка, оберіть опцію:", reply_markup=reply_markup)



