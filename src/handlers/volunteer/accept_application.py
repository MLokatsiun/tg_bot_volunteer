from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from services.api_client import get_applications_by_status, accept_application, refresh_token_log


CHOOSE_DISTANCE, CHOOSE_APPLICATION, CONFIRM_APPLICATION = range(3)

PAGE_SIZE = 5
DISTANCE_FILTERS = ["до 5 км", "до 10 км", "до 20 км", "до 50 км"]


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

async def start_accept_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the application selection process with distance filter."""

    if not context.user_data.get("access_token"):
        await update.message.reply_text("Ви не авторизовані. Спочатку виконайте вхід до системи.")
        return ConversationHandler.END


    try:
        access_token = await ensure_valid_token(context)
    except Exception as e:
        await update.message.reply_text(f"Сталася помилка при перевірці токена: {str(e)}")
        return ConversationHandler.END

    try:

        applications = await get_applications_by_status(access_token, status="available")

        if 'detail' in applications and applications['detail'] == 'No applications found.':
            await update.message.reply_text("Наразі немає доступних заявок.")
            return ConversationHandler.END

        if not applications:
            await update.message.reply_text("Наразі немає доступних заявок.")
            return ConversationHandler.END


        context.user_data["all_applications"] = applications


        keyboard = [
            [InlineKeyboardButton(distance, callback_data=f"distance_{i}") for i, distance in enumerate(DISTANCE_FILTERS)]
        ]
        keyboard.append([InlineKeyboardButton("Скасувати", callback_data="cancel")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("Оберіть дистанцію для пошуку заявок:", reply_markup=reply_markup)
        return CHOOSE_DISTANCE

    except PermissionError as e:
        await update.message.reply_text(f"Помилка доступу: {str(e)}")
    except Exception as e:
        await update.message.reply_text(f"Сталася помилка: {str(e)}")

    return ConversationHandler.END


async def choose_distance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user's distance selection and filter applications."""
    query = update.callback_query
    await query.answer()

    # Отримуємо вибрану дистанцію
    if not query.data.startswith("distance_"):
        await query.edit_message_text("Неправильний вибір. Будь ласка, спробуйте ще раз.")
        return ConversationHandler.END

    selected_distance_index = int(query.data.removeprefix("distance_"))
    selected_distance = DISTANCE_FILTERS[selected_distance_index]
    context.user_data["selected_distance"] = selected_distance

    max_distance = int(selected_distance.split(" ")[1])

    # Фільтруємо заявки за дистанцією
    all_applications = context.user_data.get("all_applications", [])
    filtered_applications = [
        app for app in all_applications
        if app.get("distance", float('inf')) <= max_distance
    ]

    if not filtered_applications:
        await query.edit_message_text("Наразі немає доступних заявок у вибраній дистанції.")
        return ConversationHandler.END


    context.user_data["applications_list"] = filtered_applications
    context.user_data["current_page"] = 0


    await display_application_page(update, context)
    return CHOOSE_APPLICATION


def get_paginated_keyboard(applications_list, page, page_size):
    """Створення клавіатури для заявок із пагінацією."""
    sorted_applications = sorted(applications_list, key=lambda app: app['id'])

    start = page * page_size
    end = start + page_size
    current_apps = sorted_applications[start:end]

    keyboard = [
        [InlineKeyboardButton(f"ID: {app['id']} | {app['description']}", callback_data=f"app_{app['id']}")]
        for app in current_apps
    ]

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data="prev_page"))
    if end < len(sorted_applications):
        nav_buttons.append(InlineKeyboardButton("➡️ Вперед", callback_data="next_page"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("Скасувати", callback_data="cancel")])

    return InlineKeyboardMarkup(keyboard)

async def display_application_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Відображення поточної сторінки заявок."""
    applications_list = context.user_data["applications_list"]
    page = context.user_data["current_page"]

    reply_markup = get_paginated_keyboard(applications_list, page, PAGE_SIZE)

    if update.message:
        await update.message.reply_text("Виберіть заявку зі списку (сортовано за ID):", reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text("Виберіть заявку зі списку (сортовано за ID):", reply_markup=reply_markup)

async def choose_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка вибору заявки користувачем."""
    query = update.callback_query
    await query.answer()

    # Перевіряємо, чи це вибір заявки (починається з "app_")
    if not query.data.startswith("app_"):
        await query.edit_message_text("Неправильний вибір. Будь ласка, спробуйте ще раз.")
        return CHOOSE_APPLICATION

    application_id = query.data.removeprefix("app_")
    application = next((app for app in context.user_data["applications_list"] if str(app["id"]) == application_id), None)

    if not application:
        await query.edit_message_text("Помилка: Заявка не знайдена.")
        return ConversationHandler.END


    context.user_data["selected_application_id"] = application_id


    keyboard = [
        [
            InlineKeyboardButton("Підтвердити", callback_data="confirm"),
            InlineKeyboardButton("Скасувати", callback_data="cancel"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=(
            f"Ви вибрали заявку з ID: {application_id}.\n\n"
            f"Опис: {application['description']}\n"
            f"Ви впевнені, що виконаєте її?"
        ),
        reply_markup=reply_markup,
    )
    return CONFIRM_APPLICATION


from datetime import datetime

async def confirm_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Підтвердження прийняття заявки."""
    query = update.callback_query
    await query.answer()

    application_id = context.user_data.get("selected_application_id")

    try:
        access_token = await ensure_valid_token(context)
    except Exception as e:
        await query.edit_message_text(f"Сталася помилка при перевірці токена: {str(e)}")
        return ConversationHandler.END

    if not application_id:
        await query.edit_message_text("Виберіть заявку перед підтвердженням.")
        return ConversationHandler.END

    try:
        application_data = await accept_application(access_token, int(application_id))

        local_application_data = next((app for app in context.user_data["applications_list"] if str(app["id"]) == application_id), {})

        creator_name = (
                application_data.get("creator", {}).get("first_name")
                or local_application_data.get("creator", {}).get("first_name", "Ім'я не вказано")
        )
        creator_phone = (
                application_data.get("creator", {}).get("phone_num")
                or local_application_data.get("creator", {}).get("phone_num", "Телефон не вказано")
        )

        location = application_data.get("location", {})
        latitude = location.get("latitude", "Не вказано")
        longitude = location.get("longitude", "Не вказано")
        address = location.get("address_name", "Адреса не вказана")


        google_maps_url = f"https://www.google.com/maps?q={latitude},{longitude}" if latitude != "Не вказано" and longitude != "Не вказано" else "Не вказано"


        location_text = f"Координати: {latitude}, {longitude}\nАдреса: {address}\n\nПосилання на Google Maps: {google_maps_url}"

        def format_date(date_str):
            if date_str:
                try:
                    date_obj = datetime.fromisoformat(date_str)
                    return date_obj.strftime("%d.%m.%Y %H:%M")
                except ValueError:
                    return "Невірний формат дати"
            return "Не вказано"

        date_at_formatted = format_date(application_data.get("date_at"))
        active_to_formatted = format_date(application_data.get("active_to"))

        confirmation_text = (
            f"Заявка успішно прийнята!\n"
            f"ID: {application_data['id']}\n"
            f"Категорія: {application_data['category_id']}\n"
            f"Опис: {application_data['description']}\n"
            f"Дата подачі: {date_at_formatted}\n"
            f"Активна до: {active_to_formatted}\n"
            f"Статус: Виконується\n\n"
            f"Ім'я замовника: {creator_name}\n"
            f"Телефон замовника: {creator_phone}\n\n"
            f"{location_text}"
        )

        await query.edit_message_text(confirmation_text)
    except Exception as e:
        await query.edit_message_text(f"Сталася помилка: {str(e)}")

    return ConversationHandler.END



async def navigate_pages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка переходу між сторінками."""
    query = update.callback_query
    await query.answer()


    current_page = context.user_data.get("current_page", 0)
    applications = context.user_data.get("applications_list", [])

    if query.data == "prev_page":
        context.user_data["current_page"] = max(0, current_page - 1)
    elif query.data == "next_page":
        total_pages = (len(applications) + PAGE_SIZE - 1) // PAGE_SIZE
        context.user_data["current_page"] = min(total_pages - 1, current_page + 1)


    await display_application_page(update, context)
    return CHOOSE_APPLICATION


async def cancel_accept_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Скасування прийняття заявки."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Прийняття заявки скасовано.")
    return ConversationHandler.END


accept_application_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^Прийняти заявку в обробку"), start_accept_application)],
    states={
        CHOOSE_DISTANCE: [
            CallbackQueryHandler(choose_distance, pattern="^distance_\\d+$"),
            CallbackQueryHandler(cancel_accept_application, pattern="^cancel$"),
        ],
        CHOOSE_APPLICATION: [
            CallbackQueryHandler(choose_application, pattern="^app_\\d+$"),
            CallbackQueryHandler(navigate_pages, pattern="^(prev_page|next_page)$"),
            CallbackQueryHandler(cancel_accept_application, pattern="^cancel$"),
        ],
        CONFIRM_APPLICATION: [
            CallbackQueryHandler(confirm_application, pattern="^confirm$"),
            CallbackQueryHandler(cancel_accept_application, pattern="^cancel$"),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel_accept_application)],
)

