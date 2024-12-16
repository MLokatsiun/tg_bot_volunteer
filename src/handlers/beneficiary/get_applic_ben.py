import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes

from services.api_client import get_applications_by_type, refresh_token_log

PAGE_SIZE = 5


async def ensure_valid_token(context):
    """
    Перевіряє дійсність access_token і оновлює його за потреби.
    """
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


async def choose_application_type_for_beneficiary(update, context):
    keyboard = [
        [InlineKeyboardButton("В доступі", callback_data='accessible')],
        [InlineKeyboardButton("В процесі", callback_data='is_progressing')],
        [InlineKeyboardButton("Виконані", callback_data='complete')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Оберіть тип заявок для перегляду або іншу функцію:",
        reply_markup=reply_markup
    )


async def application_type_button_handler(update, context):
    query = update.callback_query
    application_type = query.data

    if application_type == 'view_all':
        await view_all_applications(query, context)
        return

    try:
        access_token = await ensure_valid_token(context)
    except Exception as e:
        await query.answer(text="Ви не авторизовані або виникла помилка з токеном. Спробуйте знову.")
        return

    logging.info(f"Fetching applications of type: {application_type} with access token.")

    try:
        applications = await get_applications_by_type(access_token, application_type, "beneficiary")

        logging.info(f"API response: {applications}")

        if isinstance(applications, dict) and 'detail' in applications:
            logging.error(f"Error fetching applications: {applications['detail']}")
            await query.edit_message_text(f"Помилка при отриманні заявок: {applications['detail']}")
        elif not applications:
            await query.edit_message_text(f"Немає заявок із типом '{application_type}'.")
        else:

            applications = sorted(applications, key=lambda x: x['id'])

            context.user_data["applications_list"] = applications
            context.user_data["current_page"] = 0

            reply_markup = await get_paginated_keyboard(applications, 0)
            await query.edit_message_text(
                f"Заявки з типом '{application_type}':\n\n",
                reply_markup=reply_markup
            )
    except Exception as e:
        logging.error(f"Error fetching applications: {str(e)}")
        await query.edit_message_text(f"Помилка при отриманні заявок: {str(e)}")


async def get_paginated_keyboard(applications, page):
    """Створення клавіатури з пагінацією."""
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    current_apps = applications[start:end]

    keyboard = [
        [InlineKeyboardButton(f"ID: {app['id']} | {app['description']}", callback_data=f"app_{app['id']}")]
        for app in current_apps
    ]

    navigation_buttons = []
    if page > 0:
        navigation_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data="prev_page"))
    if end < len(applications):
        navigation_buttons.append(InlineKeyboardButton("➡️ Вперед", callback_data="next_page"))

    if navigation_buttons:
        keyboard.append(navigation_buttons)

    return InlineKeyboardMarkup(keyboard)


async def navigate_pages(update, context):
    query = update.callback_query
    current_page = context.user_data.get("current_page", 0)
    applications = context.user_data.get("applications_list", [])

    if query.data == "prev_page":
        context.user_data["current_page"] = max(0, current_page - 1)
    elif query.data == "next_page":
        context.user_data["current_page"] = min(len(applications) // PAGE_SIZE, current_page + 1)

    reply_markup = await get_paginated_keyboard(applications, context.user_data["current_page"])
    await query.edit_message_text(
        f"Заявки з типом '{applications[0]['type']}':\n\n",
        reply_markup=reply_markup
    )


async def view_all_applications(query, context):
    """
    Функція для перегляду всіх заявок.
    Відображає всі заявки без фільтрації за типом.
    """
    # Отримуємо всі заявки
    try:
        access_token = await ensure_valid_token(context)
    except Exception as e:
        await query.answer(text="Ви не авторизовані або виникла помилка з токеном. Спробуйте знову.")
        return

    try:
        applications = await get_applications_by_type(access_token, 'all', "beneficiary")

        if not applications:
            await query.edit_message_text(f"Немає доступних заявок.")
        else:

            applications = sorted(applications, key=lambda x: x['id'])

            response_text = "Всі заявки:\n\n"
            for app in applications:
                description = app.get("description", "Немає опису")
                active_to = app.get("active_to", "Немає дати")

                response_text += (
                    f"ID заявки: {app['id']}\n"
                    f"Опис: {description}\n"
                    f"Активна до: {active_to}\n\n"
                )
            await query.edit_message_text(response_text)
    except Exception as e:
        logging.error(f"Error fetching applications: {str(e)}")
        await query.edit_message_text(f"Помилка при отриманні заявок: {str(e)}")
