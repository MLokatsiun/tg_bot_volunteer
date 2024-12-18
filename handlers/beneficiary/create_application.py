from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from services.api_client import create_application, get_categories, refresh_token_log
from decouple import config
CLIENT_NAME = config("CLIENT_NAME")
CLIENT_PASSWORD = config("CLIENT_PASSWORD")
ENTER_CATEGORY_ID, ENTER_DESCRIPTION, ENTER_LOCATION, ENTER_ACTIVE_TO, CONFIRM_DATA = range(5)

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Деактивувати профіль бенефіціара")],
        [KeyboardButton("Подати заявку")],
        [KeyboardButton("Підтвердити заявку")],
        [KeyboardButton("Деактивувати заявку")],
        [KeyboardButton("Переглянути мої заявки")],
        [KeyboardButton("Вихід")],
    ],
    resize_keyboard=True, one_time_keyboard=False
)


async def start_application_creation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Початок створення заявки."""
    try:
        categories = await get_categories(CLIENT_NAME, CLIENT_PASSWORD)

        if not categories:
            await update.message.reply_text("Категорії відсутні. Спробуйте пізніше.")
            await update.message.reply_text("Повертаюсь до головного меню.", reply_markup=MAIN_KEYBOARD)
            return ConversationHandler.END

        parent_categories = [cat for cat in categories if cat["parent_id"] is None]

        if not parent_categories:
            await update.message.reply_text("Категорії верхнього рівня відсутні.")
            await update.message.reply_text("Повертаюсь до головного меню.", reply_markup=MAIN_KEYBOARD)
            return ConversationHandler.END


        cancel_keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("Скасувати подачу заявки")]], resize_keyboard=True, one_time_keyboard=True
        )
        await update.message.reply_text(
            "Натисніть кнопку нижче для скасування реєстрації, якщо захочете змінити якісь дані:",
            reply_markup=cancel_keyboard)

        keyboard = [
            [InlineKeyboardButton(cat["name"], callback_data=f"parent_{cat['id']}")]
            for cat in parent_categories
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("Оберіть категорію:", reply_markup=reply_markup)

        context.user_data["categories"] = categories
        return ENTER_CATEGORY_ID

    except Exception as e:
        await update.message.reply_text(f"Помилка отримання категорій: {e}")
        await update.message.reply_text("Повертаюсь до головного меню.", reply_markup=MAIN_KEYBOARD)
        return ConversationHandler.END


async def select_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка вибору категорії."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    category_id = int(callback_data.split("_")[1])
    context.user_data["category_id"] = category_id

    categories = context.user_data.get("categories", [])
    subcategories = [cat for cat in categories if cat["parent_id"] == category_id]

    if subcategories:
        keyboard = [
            [InlineKeyboardButton(cat["name"], callback_data=f"parent_{cat['id']}")]
            for cat in subcategories
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text("Оберіть підкатегорію:", reply_markup=reply_markup)
        return ENTER_CATEGORY_ID
    else:
        await query.edit_message_text(f"Вибрано категорію ID {category_id}. Введіть опис вашої заявки:")
        return ENTER_DESCRIPTION



async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отримання опису заявки."""
    description = update.message.text.strip()
    if description.lower() == "скасувати подачу заявки":
        return await cancel_application(update, context)

    if not description:
        await update.message.reply_text("Опис не може бути порожнім. Введіть опис заявки:")
        return ENTER_DESCRIPTION


    if len(description) > 256:
        await update.message.reply_text("Опис не може перевищувати 256 символів. Введіть коротший опис:")
        return ENTER_DESCRIPTION

    context.user_data["description"] = description

    keyboard = [
        [KeyboardButton("Так, я на телефоні")],
        [KeyboardButton("Ні, я використовую ПК")],
        [KeyboardButton("Скасувати подачу заявки")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        "Ви працюєте з телефону чи ПК? Це допоможе нам правильно запросити вашу локацію.",
        reply_markup=reply_markup
    )
    return ENTER_LOCATION


import re


async def get_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка локації залежно від вибору пристрою або введення користувача."""

    if update.message.text:
        user_response = update.message.text.strip().lower()

        if user_response == "скасувати подачу заявки":
            return await cancel_application(update, context)

        elif user_response == "так, я на телефоні":

            keyboard = [[KeyboardButton("Поділитися локацією", request_location=True)],
                        [KeyboardButton("Скасувати подачу заявки")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

            await update.message.reply_text(
                "Надішліть вашу локацію, натиснувши кнопку нижче:",
                reply_markup=reply_markup
            )
            return ENTER_LOCATION

        elif user_response == "ні, я використовую пк":

            await update.message.reply_text(
                "Ви можете знайти вашу адресу чи координати за допомогою Google Maps. Перейдіть за посиланням:\n"
                "[Google Maps](https://www.google.com/maps)\n\n"
                "Скопіюйте адресу чи координати та вставте їх у повідомленні.",
                parse_mode="Markdown"
            )
            return ENTER_LOCATION


        coordinates_match = re.match(r"^(-?\d+(\.\d+)?),\s*(-?\d+(\.\d+)?)$", user_response)
        if coordinates_match:

            latitude = float(coordinates_match.group(1))
            longitude = float(coordinates_match.group(3))
            context.user_data["location"] = {"latitude": latitude, "longitude": longitude}


            address = await reverse_geocode(latitude, longitude)
            context.user_data["location"]["address"] = address

            await update.message.reply_text(
                f"Координати отримано. Визначена адреса: {address}.\n"
                "Введіть дату, до якої заявка буде активною (у форматі ДД.ММ.РРРР 00:00):"
            )
            return ENTER_ACTIVE_TO

        else:

            context.user_data["location"] = {"address": user_response}
            await update.message.reply_text(
                "Адресу отримано. Введіть дату, до якої заявка буде активною (у форматі ДД.ММ.РРРР 00:00):"
            )
            return ENTER_ACTIVE_TO


    elif update.message.location:
        context.user_data["location"] = {
            "latitude": update.message.location.latitude,
            "longitude": update.message.location.longitude,
        }
        await update.message.reply_text(
            "Локацію отримано. Введіть дату, до якої заявка буде активною (у форматі ДД.ММ.РРРР 00:00):"
        )
        return ENTER_ACTIVE_TO


    await update.message.reply_text("Будь ласка, надішліть вашу локацію, координати або введіть адресу вручну.")
    return ENTER_LOCATION


import aiohttp

GOOGLE_GEOCODING_API_KEY = config("GOOGLE_GEOCODING_API_KEY")


async def reverse_geocode(latitude: float, longitude: float) -> str:
    """Перетворює координати в адресу за допомогою Google Maps Geocoding API."""
    url = (
        f"https://maps.googleapis.com/maps/api/geocode/json"
        f"?latlng={latitude},{longitude}&key={GOOGLE_GEOCODING_API_KEY}"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()

                print(f"Geocoding API Response: {data}")
                if data["status"] == "OK" and data["results"]:
                    return data["results"][0]["formatted_address"]
                else:
                    return "Адреса не знайдена"
    except Exception as e:
        return f"Помилка геокодування: {e}"


async def get_active_to(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = context.user_data
    location = user_data.get("location", {})
    location_info = ""

    if "latitude" in location and "longitude" in location:
        address = await reverse_geocode(location["latitude"], location["longitude"])
        location_info = f"Адреса: {address}"
    elif "address" in location:
        location_info = f"Адреса: {location['address']}"
    else:
        location_info = "Локація не вказана"

    active_to = update.message.text.strip()
    context.user_data["active_to"] = active_to

    confirmation_message = (
        f"Перевірте введені дані:\n"
        f"- Категорія ID: {user_data.get('category_id')}\n"
        f"- Опис: {user_data.get('description')}\n"
        f"- {location_info}\n"
        f"- Активна до: {active_to}"
    )

    keyboard = [
        [InlineKeyboardButton("Підтвердити", callback_data="confirm_application")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(confirmation_message, reply_markup=reply_markup)
    cancel_keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("Скасувати подачу заявки")]],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    await update.message.reply_text(
        "Якщо потрібно скасувати заявку, натисніть кнопку нижче:",
        reply_markup=cancel_keyboard
    )
    return CONFIRM_DATA


START_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Стати волонтером")],
        [KeyboardButton("Стати бенефіціаром")],
    ],
    resize_keyboard=True, one_time_keyboard=False
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


async def confirm_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Підтвердження заявки."""
    query = update.callback_query
    await query.answer()

    user_data = context.user_data
    access_token = user_data.get("access_token")

    try:

        result = await create_application(
            description=user_data["description"],
            category_id=user_data.get("category_id"),
            address=user_data["location"].get("address"),
            latitude=user_data["location"].get("latitude"),
            longitude=user_data["location"].get("longitude"),
            active_to=user_data["active_to"],
            access_token=access_token,
        )
        await query.edit_message_text(f"Заявка успішно створена! 🎉\nID: {result['id']}")
    except Exception as e:

        if "401" in str(e):
            try:
                access_token = await ensure_valid_token(context)

                result = await create_application(
                    description=user_data["description"],
                    category_id=user_data.get("category_id"),
                    address=user_data["location"].get("address"),
                    latitude=user_data["location"].get("latitude"),
                    longitude=user_data["location"].get("longitude"),
                    active_to=user_data["active_to"],
                    access_token=access_token,
                )
                await query.edit_message_text(f"Заявка успішно створена! 🎉\nID: {result['id']}")
            except Exception as refresh_error:
                await query.edit_message_text(f"Помилка при оновленні токена: {refresh_error}")
                return ConversationHandler.END
        else:
            await query.edit_message_text(f"Помилка при створенні заявки: {e}")

    await query.message.reply_text("Повертаюсь до головного меню.", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END


async def cancel_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Скасування створення заявки."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("Процес створення заявки скасовано.")
    else:
        await update.message.reply_text("Процес створення заявки скасовано.")

    await update.message.reply_text("Повертаюсь до головного меню.", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END


application_creation_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^Подати заявку$"), start_application_creation)],
    states={
        ENTER_CATEGORY_ID: [
            CallbackQueryHandler(select_category, pattern=r"^parent_\d+$"),
            MessageHandler(filters.TEXT & filters.Regex("^Скасувати подачу заявки$"), cancel_application),
        ],
        ENTER_DESCRIPTION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, get_description),
            MessageHandler(filters.TEXT & filters.Regex("^Скасувати подачу заявки$"), cancel_application),
        ],
        ENTER_LOCATION: [
            MessageHandler(filters.LOCATION, get_location),
            MessageHandler(filters.TEXT & ~filters.COMMAND, get_location),
            MessageHandler(filters.TEXT & filters.Regex("^Скасувати подачу заявки$"), cancel_application),
        ],
        ENTER_ACTIVE_TO: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, get_active_to),
            MessageHandler(filters.TEXT & filters.Regex("^Скасувати подачу заявки$"), cancel_application),
        ],
        CONFIRM_DATA: [
            CallbackQueryHandler(confirm_application, pattern="^confirm_application$"),
            MessageHandler(filters.TEXT & filters.Regex("^Скасувати подачу заявки$"), cancel_application),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel_application)],
)
