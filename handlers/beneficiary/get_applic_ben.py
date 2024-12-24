import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes

from services.api_client import get_applications_by_type, refresh_token_log

ITEMS_PER_PAGE = 5


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
        [InlineKeyboardButton("🟢 В доступі", callback_data='accessible')],
        [InlineKeyboardButton("🟠 В процесі", callback_data='is_progressing')],
        [InlineKeyboardButton("✅ Виконані", callback_data='complete')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Оберіть тип заявок для перегляду або іншу функцію:",
        reply_markup=reply_markup
    )


async def application_type_button_handler(update, context):
    query = update.callback_query
    application_type = query.data

    try:
        access_token = await ensure_valid_token(context)
    except Exception as e:
        await query.answer(text="🚫 Ви не авторизовані або виникла помилка з токеном. Спробуйте знову.")
        return

    try:
        applications = await get_applications_by_type(access_token, application_type, "beneficiary")

        if isinstance(applications, dict) and 'detail' in applications:
            await query.edit_message_text(f"❌ Помилка при отриманні заявок: {applications['detail']}")
        elif not applications:
            await query.edit_message_text(f"❌ Немає заявок із типом '{application_type}'.")
        else:
            applications = sorted(applications, key=lambda x: x['id'])

            # Зберігаємо заявки у користувацьких даних
            context.user_data["applications_list"] = applications

            response_text = "Заявки з типом '{}' (відсортовані за ID):\n\n".format(application_type)

            # Формуємо текст для відображення всіх заявок
            for app in applications:
                description = app.get("description", "Немає опису")
                active_to = app.get("active_to", "Немає дати")

                response_text += (
                    f"📝 Заявка {app['id']}:\n"
                    f"📋 Опис: {description}\n"
                    f"📅 Активна до: {active_to}\n\n"
                )

            await query.edit_message_text(response_text)

    except Exception as e:
        await query.edit_message_text(f"❌ Помилка при отриманні заявок: {str(e)}")


async def view_all_applications(query, context):
    """
    Функція для перегляду всіх заявок.
    Відображає всі заявки без фільтрації за типом.
    """
    try:
        access_token = await ensure_valid_token(context)
    except Exception as e:
        await query.answer(text="🚫 Ви не авторизовані або виникла помилка з токеном. Спробуйте знову.")
        return

    try:
        applications = await get_applications_by_type(access_token, 'all', "beneficiary")

        if not applications:
            await query.edit_message_text(f"❌ Немає доступних заявок.")
        else:

            applications = sorted(applications, key=lambda x: x['id'])

            response_text = "📝 Всі заявки (відсортовані за ID):\n\n"
            for app in applications:
                description = app.get("description", "Немає опису")
                active_to = app.get("active_to", "Немає дати")

                response_text += (
                    f"📝 Заявка {app['id']}:\n"
                    f"📋 Опис: {description}\n"
                    f"📅 Активна до: {active_to}\n\n"
                )
            await query.edit_message_text(response_text)
    except Exception as e:
        logging.error(f"Error fetching applications: {str(e)}")
        await query.edit_message_text(f"❌ Помилка при отриманні заявок: {str(e)}")
