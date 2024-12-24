import re

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, \
    ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, \
    filters
from urllib3 import request

from handlers.beneficiary.create_application import reverse_geocode
from services.api_client import register_user, login_user

AWAIT_CONFIRMATION, ENTER_PHONE, ENTER_FIRSTNAME, ENTER_LASTNAME, ENTER_PATRONYMIC, CHOOSE_DEVICE, ENTER_LOCATION, CONFIRM_DATA, CONFIRM_OR_EDIT = range(
    9)

from decouple import config

CLIENT_NAME = config("CLIENT_NAME")
CLIENT_PASSWORD = config("CLIENT_PASSWORD")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    deep_link_data = context.args

    if deep_link_data:
        param = deep_link_data[0]
        if param == "volunteer":
            return await start_volunteer_registration(update, context)
        elif param == "beneficiary":
            return await start_beneficiary_registration(update, context)

    keyboard = [
        [KeyboardButton("Стати волонтером"), KeyboardButton("Стати бенефіціаром")],
        [KeyboardButton("Авторизація модератора")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("🎉 Вітаємо!👋 Оберіть одну з опцій нижче, щоб продовжити.", reply_markup=reply_markup)

    return ConversationHandler.END


async def start_volunteer_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Перевірка, чи користувач уже зареєстрований, перед початком процесу реєстрації для волонтера."""
    context.user_data["role_id"] = 2
    return await check_and_start_registration(update, context)


async def start_beneficiary_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Перевірка, чи користувач уже зареєстрований, перед початком процесу реєстрації для бенефіціара."""
    context.user_data["role_id"] = 1
    return await check_and_start_registration(update, context)


async def check_and_start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Перевіряє статус користувача через API.
    Якщо користувач активний, перенаправляє до головного меню.
    Якщо користувач не активний, показує отримані дані для підтвердження або редагування.
    """
    tg_id = update.effective_user.id
    role_id = context.user_data.get("role_id")

    if update.message.text and "❌ Скасувати" in update.message.text:
        return await cancel(update, context)

    login_request = {
        "tg_id": str(tg_id),
        "role_id": role_id,
        "client": CLIENT_NAME,
        "password": CLIENT_PASSWORD,
    }

    try:
        response = await login_user(login_request)

        access_token = response.get("access_token")
        refresh_token = response.get("refresh_token")

        if access_token and refresh_token:
            context.user_data["access_token"] = access_token
            context.user_data["refresh_token"] = refresh_token

            await update.message.reply_text(
                "🎉 Ви вже зареєстровані! Переходимо до головного меню 🏠"
            )
            await main_menu(update, context)
            return ConversationHandler.END

        elif response.get("is_active") is False:
            context.user_data.update(response)

            phone = response.get("phone_num", "Не вказано")
            firstname = response.get("firstname", "Не вказано")
            lastname = response.get("lastname", "")
            patronymic = response.get("patronymic", "")
            role = "Волонтер" if role_id == 2 else "Бенефіціар"

            location = response.get("location", {})
            location_display = ""

            if location:
                if "latitude" in location and "longitude" in location:
                    location_display = f"📍 Широта: {location['latitude']}, Довгота: {location['longitude']}"
                elif "address" in location:
                    location_display = f"🏠 Адреса: {location['address']}"

            confirmation_message = f"Дані, отримані з бази:\n\n"

            if firstname != "Не вказано":
                confirmation_message += f"👤 Ім'я: {firstname}\n"
            if lastname:
                confirmation_message += f"👤 Прізвище: {lastname}\n"
            if patronymic:
                confirmation_message += f"👨‍👩‍👧‍👦 По-батькові: {patronymic}\n"
            if role:
                confirmation_message += f"🎭 Роль: {role}\n"
            if location_display:
                confirmation_message += f"{location_display}\n"

            confirmation_message += f"📞 Телефон: {phone}\n\n"
            confirmation_message += "Якщо дані вірні, натисніть '✅ Підтвердити'. Якщо потрібно внести зміни, натисніть '✏️ Редагувати'."

            keyboard = [
                [KeyboardButton("✅ Підтвердити")],
                [KeyboardButton("✏️ Редагувати")],
                [KeyboardButton("❌ Скасувати")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

            await update.message.reply_text(confirmation_message, reply_markup=reply_markup)
            return CONFIRM_OR_EDIT


    except PermissionError:
        keyboard = [

            [KeyboardButton("🔍 Перевірити статус волонтера")],
            [KeyboardButton("❌ Скасувати")]
        ] if role_id == 2 else [
            [KeyboardButton("🔍 Перевірити статус бенефіціара")],
            [KeyboardButton("❌ Скасувати")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(
            "❗ Доступ заборонено. Зверніться до адміністратора або дочекайтеся підтвердження модератора.",
            reply_markup=reply_markup
        )
        return AWAIT_CONFIRMATION

    except Exception:
        return await start_registration(update, context)


async def handle_confirm_or_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка підтвердження або редагування даних користувача."""
    user_data = context.user_data
    role_id = user_data.get("role_id")
    response_text = "✅ Ваші дані підтверджено!"

    if "✅ Підтвердити" in update.message.text:
        try:
            await register_user(update.message.from_user.id, user_data)

            if role_id == 2:
                keyboard = [
                    [KeyboardButton("🔍 Перевірити статус волонтера")],
                    [KeyboardButton("❌ Скасувати")]
                ]
            else:
                keyboard = [
                    [KeyboardButton("🔍 Перевірити статус бенефіціара")],
                    [KeyboardButton("❌ Скасувати")]
                ]

            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


            await update.message.reply_text(
                f"{response_text} Ви можете перевірити статус або повернутися до меню.",
                reply_markup=reply_markup
            )
            return AWAIT_CONFIRMATION
        except Exception as e:
            await update.message.reply_text(
                f"❌ Сталася помилка при підтвердженні: {str(e)}. Спробуйте пізніше."
            )
            return CONFIRM_DATA

    elif "✏️ Редагувати" in update.message.text:
        return await start_registration(update, context)

    return await cancel(update, context)


async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Початок процесу реєстрації."""
    keyboard = [
        [KeyboardButton("📱 Надіслати номер телефону", request_contact=True)],
        [KeyboardButton("❌ Скасувати")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "📲 Для реєстрації, будь ласка, надішліть свій номер телефону за допомогою кнопки нижче:",
        reply_markup=reply_markup
    )
    return ENTER_PHONE


async def enter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отримання номера телефону або скасування."""
    if update.message.text == "❌ Скасувати":
        return await cancel(update, context)

    if update.message.contact:
        phone = update.message.contact.phone_number

        print("Contact data:", update.message.contact)
        if phone.startswith('+'):
            phone = phone[1:]
        elif phone.startswith('8'):
            phone = '380' + phone[1:]
        elif not phone.startswith('380'):
            await update.message.reply_text("❌ Будь ласка, поділіться коректним номером телефону.")
            return ENTER_PHONE

        print("Extracted phone number:", phone)
        context.user_data["phone_num"] = phone

        keyboard = [[KeyboardButton("❌ Скасувати")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

        await update.message.reply_text(
            "📝 Будь ласка, введіть своє повне ім'я в одному рядку, розділяючи частини пробілами.\n\n"
            "🔹 Наприклад:\n"
            "- Іван Петренко Іванович (ім'я, прізвище, по батькові)\n"
            "- Іван Петренко (тільки ім'я та прізвище)\n"
            "- Іван (лише ім'я)\n\n"
            "Якщо ви введете тільки ім'я, буде збережено лише його.",
            reply_markup=reply_markup
        )

        print("Proceeding to ENTER_FIRSTNAME")
        return ENTER_FIRSTNAME
    else:
        print("No contact data provided.")
        await update.message.reply_text("❌ Будь ласка, скористайтесь кнопкою для передачі номера телефону.")
        return ENTER_PHONE


MAX_NAME_LENGTH = 50
MIN_NAME_LENGTH = 2


async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка введення імені, прізвища і по-батькові одним рядком."""
    if update.message.text == "❌ Скасувати":
        return await cancel(update, context)

    user_input = update.message.text.strip()

    if len(user_input) > MAX_NAME_LENGTH:
        await update.message.reply_text(f"Текст занадто довгий. Максимальна довжина – {MAX_NAME_LENGTH} символів. ❌")
        return ENTER_FIRSTNAME

    name_parts = user_input.split()

    if len(name_parts) == 1:
        context.user_data["firstname"] = name_parts[0]
        context.user_data["lastname"] = ""
        context.user_data["patronymic"] = ""
    elif len(name_parts) == 2:
        context.user_data["lastname"] = name_parts[0]
        context.user_data["firstname"] = name_parts[1]
        context.user_data["patronymic"] = ""
    elif len(name_parts) >= 3:
        context.user_data["lastname"] = name_parts[0]
        context.user_data["firstname"] = name_parts[1]
        context.user_data["patronymic"] = " ".join(name_parts[2:])

    if context.user_data.get("role_id") == 2:
        return await choose_device(update, context)
    else:
        return await confirm_registration(update, context)


async def choose_device(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запитує, чи працює користувач з телефону чи ПК."""
    keyboard = [
        [KeyboardButton("📱 Я на телефоні")],
        [KeyboardButton("💻 Я використовую ПК")],
        [KeyboardButton("❌ Скасувати")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "Вкажіть, будь ласка, чи працюєте ви з телефону чи ПК: 🖥️📱",
        reply_markup=reply_markup
    )
    return ENTER_LOCATION


async def enter_coordinates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка введення координат або отримання адреси через зворотне геокодування."""
    if update.message.text:
        user_response = update.message.text.strip()

        if user_response == "❌ Скасувати":
            return await cancel(update, context)

        if user_response == "📱 Я на телефоні":
            keyboard = [
                [KeyboardButton("📍 Поділитися локацією", request_location=True)],
                [KeyboardButton("❌ Скасувати")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text(
        "🔔 **Інструкція для користувача мобільного телефону:**\n\n"
        "1. **Увімкніть місцезнаходження:**\n"
        "   - Для **Android**: Перейдіть до налаштувань → \"Місцезнаходження\" і увімкніть його.\n"
        "   - Для **iPhone**: Перейдіть до налаштувань → \"Конфіденційність\" → \"Місцезнаходження\" і увімкніть його.\n\n"
        "   - Натисніть кнопку \"📍 Поділитися локацією\".\n"
        "2. **Якщо ви хочете вибрати іншу точку на карті:**\n"
        "   - **Вимкніть місцезнаходження** в налаштуваннях телефону.\n"
        "   - Натисніть кнопку \"📍 Поділитися локацією\".\n"
        "   - З'явиться вікно з картою, де ви зможете вручну вибрати точку або перемістити маркер на правильне місце.\n"
        "   - Після вибору потрібної точки, підтвердіть локацію і надішліть її.",
                reply_markup=reply_markup, parse_mode="Markdown"
            )
            return ENTER_LOCATION

        elif user_response == "💻 Я використовую ПК":
            keyboard = [
                [KeyboardButton("❌ Скасувати")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text(
                "💻 **Як знайти координати за допомогою Google Maps на ПК:**\n\n"
                "1️⃣ Відкрийте [Google Maps](https://www.google.com/maps) у вашому браузері.\n"
                "2️⃣ Знайдіть своє місцезнаходження на карті, натиснувши на потрібну точку лівою кнопкою миші (ЛКМ).\n"
                "3️⃣ Наведіть курсор на крапку, яка з'явилася на карті (ваше місцезнаходження) та натисніть праву кнопку миші (ПКМ).\n"
                "4️⃣ У меню, що з'явиться, клацніть на координати лівою кнопкою миші (ЛКМ).\n"
                "5️⃣ Координати (широта та довгота) автоматично скопіюються в буфер обміну.\n"
                "6️⃣ Поверніться до цього чату і натисніть праву кнопку миші (ПКМ) у текстовому полі чату, а потім виберіть **'Вставити'**.\n"
                "   Також можна використати комбінацію клавіш **Ctrl + V** для вставлення.\n\n"
                "📍 **Приклад координат:** `49.2827, -123.1216`", parse_mode="Markdown", reply_markup=reply_markup
            )
            return ENTER_LOCATION

        coordinates_match = re.match(r"^(-?\d+(\.\d+)?),\s*(-?\d+(\.\d+)?)$", user_response)
        if coordinates_match:
            latitude = float(coordinates_match.group(1))
            longitude = float(coordinates_match.group(3))
            context.user_data["location"] = {
                "latitude": latitude,
                "longitude": longitude
            }

            address = await reverse_geocode(latitude, longitude)
            context.user_data["location"]["address"] = address

            await update.message.reply_text(
                f"Координати отримано. Визначена адреса: {address}.\n"
                "Будь ласка, підтвердіть ваші дані. ✅"
            )
            await confirm_registration(update, context)
            return CONFIRM_DATA


        else:
            context.user_data["location"] = {"address": user_response}
            await update.message.reply_text(
                "Адресу отримано. Будь ласка, підтвердіть ваші дані. ✅"
            )
            await confirm_registration(update, context)
            return CONFIRM_DATA

    elif update.message.location:
        latitude = update.message.location.latitude
        longitude = update.message.location.longitude
        context.user_data["location"] = {
            "latitude": latitude,
            "longitude": longitude
        }

        address = await reverse_geocode(latitude, longitude)
        context.user_data["location"]["address"] = address

        await update.message.reply_text(
            f"Локацію отримано. Визначена адреса: {address}.\n"
            "Будь ласка, підтвердіть ваші дані. ✅"
        )
        await confirm_registration(update, context)
        return CONFIRM_DATA

    else:
        await update.message.reply_text("Будь ласка, надішліть вашу локацію, координати або адресу. 📍")
        return ENTER_LOCATION


async def confirm_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показує дані для підтвердження перед завершенням реєстрації."""
    user_data = context.user_data
    phone = user_data.get("phone_num", "Не вказано")
    firstname = user_data.get("firstname", "Не вказано")
    lastname = user_data.get("lastname", "Не вказано")
    patronymic = user_data.get("patronymic", "Не вказано")
    role = "Волонтер" if user_data.get("role_id") == 2 else "Бенефіціар"

    # Отримуємо локацію, але перевірка її наявності не потрібна для бенефіціарів
    location_display = "Не вказано"
    location = user_data.get("location", None)

    if location and "latitude" in location and "longitude" in location:
        location_display = f"Широта: {location['latitude']}, Довгота: {location['longitude']}"
    elif location and "address" in location:
        location_display = f"Адреса: {location['address']}"

    # Формуємо повідомлення для підтвердження
    confirmation_message = (
        f"Ваші дані для підтвердження:\n\n"
        f"📱 Телефон: {phone}\n"
        f"👤 Ім'я: {firstname}\n"
        f"👥 Прізвище: {lastname}\n"
        f"📝 По-батькові: {patronymic}\n"
        f"🎭 Роль: {role}\n"
        f"{'🌍 Локація: ' + location_display if role == 'Волонтер' else ''}\n\n"
        "Якщо все вірно, натисніть '✅ Підтвердити'. Якщо потрібно виправити, натисніть '✏️ Редагувати'."
    )

    # Кнопки для підтвердження
    keyboard = [
        [KeyboardButton("✅ Підтвердити")],
        [KeyboardButton("❌ Скасувати")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    # Відправляємо повідомлення
    await update.message.reply_text(confirmation_message, reply_markup=reply_markup)
    return CONFIRM_DATA



async def send_to_api(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Надсилання даних до API після підтвердження та повернення до меню."""
    user_data = context.user_data
    user_id = update.message.from_user.id

    try:

        await register_user(user_id, user_data)
        role_id = user_data.get("role_id")

        if role_id == 2:
            keyboard = [
                [KeyboardButton("Перевірити статус волонтера")],
                [KeyboardButton("❌ Скасувати")]
            ]
        else:
            keyboard = [
                [KeyboardButton("Перевірити статус бенефіціара")],
                [KeyboardButton("❌ Скасувати")]
            ]

        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

        await update.message.reply_text(
            "Реєстрація успішна! Ви можете перевірити статус або повернутися до меню.",
            reply_markup=reply_markup
        )

        return AWAIT_CONFIRMATION
    except PermissionError:

        keyboard = [
            [KeyboardButton("🔍 Перевірити статус волонтера")],
            [KeyboardButton("❌ Скасувати")]
        ] if user_data.get("role_id") == 2 else [
            [KeyboardButton("🔍Перевірити статус бенефіціара")],
            [KeyboardButton("❌ Скасувати")]
        ]


        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(
            "Доступ заборонено. Зверніться до адміністратора або дочекайтеся підтвердження модератора.",
            reply_markup=reply_markup
        )

        return AWAIT_CONFIRMATION
    except Exception as e:
        await update.message.reply_text(
            f"Сталася помилка під час реєстрації: {str(e)}. Спробуйте пізніше."
        )
        return CONFIRM_DATA


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Скасування реєстрації та повернення до головного меню."""

    if "❌ Скасувати" in update.message.text:

        await update.message.reply_text(
            "Реєстрацію скасовано. Повертаємось до головного меню.",
            reply_markup=ReplyKeyboardRemove()
        )

        keyboard = [[KeyboardButton("Стати волонтером"), KeyboardButton("Стати бенефіціаром")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

        await update.message.reply_text(
            "Виберіть одну з опцій:",
            reply_markup=reply_markup
        )

        return ConversationHandler.END
    else:

        await update.message.reply_text(
            "Щоб скасувати реєстрацію, напишіть або натисніть 'Скасувати'."
        )
        return AWAIT_CONFIRMATION


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
    else:
        keyboard = [
            [KeyboardButton("Подати заявку")],
            [KeyboardButton("Підтвердити заявку")],
            [KeyboardButton("Деактивувати заявку")],
            [KeyboardButton("Переглянути мої заявки")],
            [KeyboardButton("Деактивувати профіль бенефіціара")],
            [KeyboardButton("Вихід")]
        ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text("Оберіть дію з меню нижче:", reply_markup=reply_markup)


registration_handler = ConversationHandler(
    entry_points=[
        CommandHandler("start", start),
        MessageHandler(filters.Regex("^Стати волонтером$"), start_volunteer_registration),
        MessageHandler(filters.Regex("^Стати бенефіціаром$"), start_beneficiary_registration),
    ],
    states={
        AWAIT_CONFIRMATION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, check_and_start_registration),
        ],
        ENTER_PHONE: [
            MessageHandler(filters.CONTACT | filters.TEXT & ~filters.COMMAND, enter_phone),
        ],
        ENTER_FIRSTNAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name),
        ],
        CHOOSE_DEVICE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, choose_device),
        ],
        ENTER_LOCATION: [
            MessageHandler(filters.LOCATION | filters.TEXT & ~filters.COMMAND, enter_coordinates),
        ],
        CONFIRM_DATA: [
            MessageHandler(filters.Regex("^✅ Підтвердити"), send_to_api),
            MessageHandler(filters.Regex("^❌ Скасувати$"), cancel),
        ],
        CONFIRM_OR_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirm_or_edit)],
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
        MessageHandler(filters.Regex("^❌ Скасувати$"), cancel),
    ],
)
