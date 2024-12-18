import re

import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters

from handlers.beneficiary.create_application import reverse_geocode
from services.api_client import edit_volunteer_location_and_categories, get_categories, refresh_token_log
from decouple import config
CLIENT_NAME = config('CLIENT_NAME')
CLIENT_PASSWORD = config('CLIENT_PASSWORD')

# Константи для станів
ENTER_LOCATION, ENTER_CATEGORIES, CONFIRM_EDIT = range(3)

async def start_edit_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Початок редагування профілю волонтера."""
    if not context.user_data.get("access_token"):
        await update.message.reply_text("Ви не авторизовані. Спочатку виконайте вхід до системи.")
        return ConversationHandler.END


    keyboard = [
        [KeyboardButton("Я на телефоні")],
        [KeyboardButton("Я використовую ПК")],
        [KeyboardButton("Пропустити")],
        [KeyboardButton("Скасувати редагування")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text(
        "Поділіться вашою новою локацією, введіть адресу або оберіть спосіб введення:",
        reply_markup=reply_markup
    )
    return ENTER_LOCATION

async def skip_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пропуск введення локації."""
    await update.message.reply_text("Локація залишиться незмінною.")

    return await enter_location(update, context)

async def enter_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка введення нової локації користувача."""
    if update.message.text:
        user_response = update.message.text.strip().lower()

        if user_response == "скасувати редагування":
            return await cancel_edit(update, context)


        if user_response == "пропустити":
            await update.message.reply_text("Локація залишиться незмінною.")
            return await proceed_to_categories(update, context)

        if user_response == "я на телефоні":
            keyboard = [
                [KeyboardButton("Поділитися локацією", request_location=True)],
                [KeyboardButton("Скасувати редагування")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text(
                "Будь ласка, поділіться вашою локацією за допомогою кнопки нижче:",
                reply_markup=reply_markup
            )
            return ENTER_LOCATION

        elif user_response == "я використовую пк":
            keyboard = [[KeyboardButton("Скасувати редагування")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text(
                "Ви можете знайти вашу адресу чи координати за допомогою Google Maps. Перейдіть за посиланням:\n"
                "[Google Maps](https://www.google.com/maps)\n\n"
                "Скопіюйте адресу чи координати та вставте їх у повідомленні.",
                parse_mode="Markdown", reply_markup=reply_markup
            )
            return ENTER_LOCATION


        coordinates_match = re.match(r"^(-?\d+(\.\d+)?),\s*(-?\d+(\.\d+)?)$", user_response)
        if coordinates_match:
            latitude = float(coordinates_match.group(1))
            longitude = float(coordinates_match.group(3))
            context.user_data["edit_location"] = {
                "latitude": latitude,
                "longitude": longitude
            }


            address = await reverse_geocode(latitude, longitude)
            context.user_data["edit_location"]["address"] = address

            await update.message.reply_text(
                f"Координати отримано. Визначена адреса: {address}."
            )
            return await proceed_to_categories(update, context)


        else:
            context.user_data["edit_location"] = {"address": user_response}
            await update.message.reply_text(
                "Адресу отримано. Переходимо до наступного кроку."
            )
            return await proceed_to_categories(update, context)

    elif update.message.location:
        latitude = update.message.location.latitude
        longitude = update.message.location.longitude
        context.user_data["edit_location"] = {
            "latitude": latitude,
            "longitude": longitude
        }


        address = await reverse_geocode(latitude, longitude)
        context.user_data["edit_location"]["address"] = address

        await update.message.reply_text(
            f"Локацію отримано. Визначена адреса: {address}."
        )
        return await proceed_to_categories(update, context)

    else:
        await update.message.reply_text("Будь ласка, надішліть вашу локацію, координати або адресу.")
        return ENTER_LOCATION

async def proceed_to_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Переходить до вибору категорій після введення локації."""
    try:
        categories = await get_categories(CLIENT_NAME, CLIENT_PASSWORD)

        if not categories:
            await update.message.reply_text("Категорії відсутні. Спробуйте пізніше.")
            return ConversationHandler.END

        parent_categories = [cat for cat in categories if cat["parent_id"] is None]

        if not parent_categories:
            await update.message.reply_text("Категорії верхнього рівня відсутні.")
            return ConversationHandler.END

        keyboard = [
            [InlineKeyboardButton(cat["name"], callback_data=f"parent_{cat['id']}")]
            for cat in parent_categories
        ]
        keyboard.append([InlineKeyboardButton("Завершити вибір", callback_data="finish_selection")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        context.user_data["categories"] = categories
        context.user_data["selected_categories"] = []
        context.user_data["current_parent_id"] = None

        cancel_keyboard = [[KeyboardButton("Скасувати редагування")]]
        cancel_reply_markup = ReplyKeyboardMarkup(cancel_keyboard, resize_keyboard=True, one_time_keyboard=True)

        await update.message.reply_text("Оберіть категорії для редагування:", reply_markup=reply_markup)
        await update.message.reply_text("Натисніть кнопку нижче, щоб скасувати редагування:", reply_markup=cancel_reply_markup)

        return ENTER_CATEGORIES

    except Exception as e:
        await update.message.reply_text(f"Помилка отримання категорій: {e}")
        return ConversationHandler.END


async def select_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка вибору категорії."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data


    if callback_data == "finish_selection":
        selected_categories = context.user_data.get("selected_categories", [])
        if not selected_categories:
            await query.edit_message_text("Ви не обрали жодної категорії.")
            return ENTER_CATEGORIES

        await query.edit_message_text("Категорії обрано.")
        await query.message.reply_text(
            "Підтвердити редагування профілю?",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("Так"), KeyboardButton("Ні")]],
                resize_keyboard=True,
            )
        )
        return CONFIRM_EDIT


    if callback_data == "back_to_parents":
        categories = context.user_data.get("categories", [])
        selected_categories = context.user_data.get("selected_categories", [])
        parent_categories = [cat for cat in categories if cat["parent_id"] is None]

        keyboard = [
            [InlineKeyboardButton(
                f"{cat['name']} {'✅' if cat['id'] in selected_categories else ''}",
                callback_data=f"parent_{cat['id']}"
            )]
            for cat in parent_categories
        ]
        keyboard.append([InlineKeyboardButton("Завершити вибір", callback_data="finish_selection")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Оберіть категорії (✅ позначено обрані):",
            reply_markup=reply_markup,
        )
        context.user_data["current_parent_id"] = None
        return ENTER_CATEGORIES


    category_id = int(callback_data.split("_")[1])
    categories = context.user_data.get("categories", [])
    selected_categories = context.user_data.setdefault("selected_categories", [])


    if category_id in selected_categories:
        selected_categories.remove(category_id)
    else:
        selected_categories.append(category_id)


    subcategories = [cat for cat in categories if cat["parent_id"] == category_id]

    if subcategories:

        context.user_data["current_parent_id"] = category_id


        keyboard = [
            [InlineKeyboardButton(
                f"{cat['name']} {'✅' if cat['id'] in selected_categories else ''}",
                callback_data=f"parent_{cat['id']}"
            )]
            for cat in subcategories
        ]
        keyboard.append([InlineKeyboardButton("Повернутися", callback_data="back_to_parents")])
        keyboard.append([InlineKeyboardButton("Завершити вибір", callback_data="finish_selection")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Оберіть підкатегорії (✅ позначено обрані):",
            reply_markup=reply_markup,
        )
    else:

        current_parent_id = context.user_data.get("current_parent_id")
        subcategories = [cat for cat in categories if cat["parent_id"] == current_parent_id]

        keyboard = [
            [InlineKeyboardButton(
                f"{cat['name']} {'✅' if cat['id'] in selected_categories else ''}",
                callback_data=f"parent_{cat['id']}"
            )]
            for cat in subcategories
        ]

        if current_parent_id:
            keyboard.append([InlineKeyboardButton("Повернутися", callback_data="back_to_parents")])
        keyboard.append([InlineKeyboardButton("Завершити вибір", callback_data="finish_selection")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Оберіть підкатегорії (✅ позначено обрані):",
            reply_markup=reply_markup,
        )

    return ENTER_CATEGORIES

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

async def confirm_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Підтвердження редагування профілю."""
    if update.message.text.lower() == "так":
        access_token = context.user_data.get("access_token")
        location = context.user_data.get("edit_location")
        category_ids = context.user_data.get("selected_categories")


        if location is None:

            location = None


        if category_ids is None:
            category_ids = []

        try:

            access_token = await ensure_valid_token(context)

            await edit_volunteer_location_and_categories(access_token, location, category_ids)


            await update.message.reply_text("Профіль успішно оновлено.")

            main_menu_buttons = [
                [KeyboardButton("Список завдань")],
                [KeyboardButton("Прийняти заявку в обробку")],
                [KeyboardButton("Закрити заявку")],
                [KeyboardButton("Скасувати заявку")],
                [KeyboardButton("Редагувати профіль")],
                [KeyboardButton("Деактивувати профіль волонтера")],
                [KeyboardButton("Вихід")],
            ]
            reply_markup = ReplyKeyboardMarkup(main_menu_buttons, resize_keyboard=True)
            await update.message.reply_text("Головне меню:", reply_markup=reply_markup)

        except ValueError as e:
            await update.message.reply_text(f"Помилка: {str(e)}")
        except Exception as e:
            await update.message.reply_text(f"Сталася помилка: Виберіть категорії в розділі 'Редагувати профіль', щоб отримувати заявки по вибраним категоріям ")
    else:
        await update.message.reply_text("Редагування профілю скасовано.")

        main_menu_buttons = [
            [KeyboardButton("Список завдань")],
            [KeyboardButton("Прийняти заявку в обробку")],
            [KeyboardButton("Закрити заявку")],
            [KeyboardButton("Скасувати заявку")],
            [KeyboardButton("Редагувати профіль")],
            [KeyboardButton("Деактивувати профіль волонтера")],
            [KeyboardButton("Вихід")],
        ]
        reply_markup = ReplyKeyboardMarkup(main_menu_buttons, resize_keyboard=True, one_time_keyboard=False)
        await update.message.reply_text("Головне меню:", reply_markup=reply_markup)

    return ConversationHandler.END

async def cancel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Скасування редагування профілю та повернення до меню."""
    main_menu_buttons = [
        [KeyboardButton("Список завдань")],
        [KeyboardButton("Прийняти заявку в обробку")],
        [KeyboardButton("Закрити заявку")],
        [KeyboardButton("Скасувати заявку")],
        [KeyboardButton("Редагувати профіль")],
        [KeyboardButton("Деактивувати профіль волонтера")],
        [KeyboardButton("Вихід")],
    ]
    reply_markup = ReplyKeyboardMarkup(main_menu_buttons, resize_keyboard=True, one_time_keyboard=False)

    await update.message.reply_text("Редагування профілю скасовано.", reply_markup=reply_markup)
    return ConversationHandler.END



edit_profile_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^Редагувати профіль$"), start_edit_profile)],
    states={
        ENTER_LOCATION: [
            MessageHandler(filters.LOCATION, enter_location),
            MessageHandler(filters.TEXT & ~filters.COMMAND, enter_location),
            MessageHandler(filters.Regex("^Пропустити$"), skip_location),
        ],
        ENTER_CATEGORIES: [
            CallbackQueryHandler(select_category),
        ],
        CONFIRM_EDIT: [
            MessageHandler(filters.Regex("^Так$"), confirm_edit),
            MessageHandler(filters.Regex("^Ні$"), cancel_edit),
        ],
    },
    fallbacks=[MessageHandler(filters.Regex("^Скасувати редагування$"), cancel_edit)],
)
