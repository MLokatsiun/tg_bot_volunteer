from telegram.ext import Application, CallbackQueryHandler
from telegram.ext import CommandHandler, MessageHandler, filters

from handlers.volunteer.accept_application import accept_application_handler
from handlers.volunteer.cancel_application import cancel_application_handler
from handlers.volunteer.close_application import close_application_handler
from handlers.beneficiary.confirm_application import finished_application_confirmation_handler
from handlers.beneficiary.create_application import application_creation_handler
from handlers.moderator.create_categories import category_creation_handler
from handlers.beneficiary.delete_application_ben import accessible_application_deletion_handler
from handlers.moderator.delete_application_moderator import deactivate_application_handler
from handlers.moderator.delete_categories import category_deactivation_handler
from handlers.beneficiary.delete_profile_beneficiary import start_deactivation, confirm_deactivation, deactivation_handler_ben
from handlers.beneficiary.get_applic_ben import choose_application_type_for_beneficiary, application_type_button_handler
from handlers.moderator.moderator_login import moderator_auth_handler
from handlers.authorization.registration import registration_handler
from handlers.authorization.auth import auth_handler, handle_exit
from handlers.volunteer.delete_profile_volunteer import \
    deactivation_handler_vol
from handlers.volunteer.edit_profile import edit_profile_handler
from handlers.volunteer.get_applic_volunteer import choose_application_type, button
from handlers.moderator.verify_user import verify_user_handler
from decouple import config
# Токен бота
TELEGRAM_TOKEN = config("TELEGRAM_TOKEN")

async def start(update, context) -> None:
    """Головне меню."""
    from telegram import ReplyKeyboardMarkup, KeyboardButton
    keyboard = [
        [KeyboardButton("Стати волонтером"), KeyboardButton("Стати бенефіціаром")],
        [KeyboardButton("Авторизація модератора")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Вітаємо! Оберіть дію:", reply_markup=reply_markup)

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(registration_handler)
    application.add_handler(auth_handler)


    application.add_handler(moderator_auth_handler)
    application.add_handler((MessageHandler(filters.Regex("^Вихід$"), handle_exit)))

    application.add_handler(category_creation_handler)
    application.add_handler(category_deactivation_handler)
    application.add_handler(deactivate_application_handler)
    application.add_handler(verify_user_handler)


    application.add_handler(application_creation_handler)
    application.add_handler(finished_application_confirmation_handler)
    application.add_handler(accessible_application_deletion_handler)
    application.add_handler(MessageHandler(filters.Regex("^Переглянути мої заявки$"), choose_application_type_for_beneficiary))
    application.add_handler(CallbackQueryHandler(application_type_button_handler, pattern="^(accessible|is_progressing|complete)$"))


    application.add_handler(deactivation_handler_ben)
    application.add_handler(deactivation_handler_vol)

    application.add_handler(close_application_handler)
    application.add_handler(accept_application_handler)
    application.add_handler(cancel_application_handler)
    application.add_handler(edit_profile_handler)
    application.add_handler(MessageHandler(filters.Regex("^Список завдань$"), choose_application_type))
    application.add_handler(CallbackQueryHandler(button, pattern="(available|in_progress|finished)"))


  # Обробник для підтвердження деактивації


    application.run_polling()

if __name__ == "__main__":
    main()