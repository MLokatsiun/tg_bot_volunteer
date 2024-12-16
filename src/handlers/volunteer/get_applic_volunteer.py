from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ContextTypes
from services.api_client import get_applications_by_type, refresh_token_log

# Константи для пагінації та фільтрації
ITEMS_PER_PAGE = 5
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


async def choose_application_type(update, context):
    keyboard = [
        [InlineKeyboardButton("Доступні", callback_data='available')],
        [InlineKeyboardButton("Виконуються", callback_data='in_progress')],
        [InlineKeyboardButton("Завершені", callback_data='finished')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Оберіть тип заявки:",
        reply_markup=reply_markup
    )


from datetime import datetime


async def button(update, context):
    query = update.callback_query
    data = query.data.split('|')
    application_type = data[0]

    current_page = int(data[1]) if len(data) > 1 else 0
    distance_filter = data[2] if len(data) > 2 else None

    try:
        access_token = await ensure_valid_token(context)
    except Exception as e:
        await query.answer(text=f"Помилка: {str(e)}")
        return

    if application_type == "available" and not distance_filter:
        keyboard = [[InlineKeyboardButton(f, callback_data=f"available|0|{f}") for f in DISTANCE_FILTERS]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Оберіть фільтр за відстанню:", reply_markup=reply_markup)
        return

    applications = await get_applications_by_type(
        access_token, application_type, "volunteer"
    )

    if isinstance(applications, dict) and 'detail' in applications:
        await query.answer(text=applications["detail"])
    else:
        if not applications:
            await query.answer(text=f"Немає заявок зі статусом '{application_type}'.")
        else:
            if distance_filter:
                max_distance = int(distance_filter.split()[1])
                applications = [app for app in applications if app.get("distance", float('inf')) <= max_distance]

            applications.sort(key=lambda app: app['id'])

            total_pages = (len(applications) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
            start = current_page * ITEMS_PER_PAGE
            end = start + ITEMS_PER_PAGE
            paginated_apps = applications[start:end]

            response_text = f"Заявки зі статусом '{application_type}':\n\n"

            def format_date(date_str):
                if date_str:
                    try:
                        date_obj = datetime.fromisoformat(date_str)
                        return date_obj.strftime("%d.%m.%Y %H:%M")
                    except ValueError:
                        return "Невірний формат дати"
                return "Не вказано"

            for app in paginated_apps:
                description = app.get("description", "Немає опису")
                distance = app.get("distance", None)
                active_to = app.get("active_to", "Невідомо")
                first_name = app.get("creator", {}).get("first_name", "Невідомо")
                phone_num = app.get("creator", {}).get("phone_num", "Невідомо")

                if distance is not None:
                    distance = round(distance, 1)
                    distance_text = f"{distance} км від вас"
                else:
                    distance_text = "Відстань невідома"

                active_to_formatted = format_date(active_to)

                if application_type in ["in_progress", "finished"]:
                    creator_info = f"Автор: {first_name}, Телефон: {phone_num}"
                else:
                    creator_info = ""

                response_text += (
                    f"Заявка {app['id']}:\n"
                    f"Опис: {description}\n"
                    f"Відстань: {distance_text}\n"
                    f"Дійсна до: {active_to_formatted}\n"
                    f"{creator_info}\n\n"
                )

            keyboard = []

            nav_buttons = []
            if current_page > 0:
                nav_buttons.append(InlineKeyboardButton("⬅️ Назад",
                                                        callback_data=f"{application_type}|{current_page - 1}|{distance_filter}"))
            if current_page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton("Вперед ➡️",
                                                        callback_data=f"{application_type}|{current_page + 1}|{distance_filter}"))

            if nav_buttons:
                keyboard.append(nav_buttons)

            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(response_text, reply_markup=reply_markup)



