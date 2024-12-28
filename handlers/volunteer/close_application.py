from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram import KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from services.api_client import get_applications_by_status, close_application, refresh_token_log


CHOOSE_APPLICATION, UPLOAD_FILES = range(2)
PAGE_SIZE = 5

MAX_FILE_SIZE = 5 * 1024 * 1024
main_menu_buttons = [
    [KeyboardButton("Список завдань")],
    [KeyboardButton("Прийняти заявку в обробку")],
    [KeyboardButton("Закрити заявку")],
    [KeyboardButton("Скасувати заявку")],
    [KeyboardButton("Редагувати профіль")],
    [KeyboardButton("Деактивувати профіль волонтера")],
    [KeyboardButton("Вихід")],
]
main_menu_markup = ReplyKeyboardMarkup(main_menu_buttons, resize_keyboard=True, one_time_keyboard=False)

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


async def start_closing_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Початок процесу закриття заявки."""

    if not context.user_data.get("access_token"):
        await update.message.reply_text("🚫 Ви не авторизовані. Спочатку виконайте вхід до системи.")
        return ConversationHandler.END

    try:

        access_token = await ensure_valid_token(context)

        applications = await get_applications_by_status(access_token, status="in_progress")
        if not applications:
            await update.message.reply_text("❌ Немає заявок, доступних для закриття.")
            return ConversationHandler.END

        context.user_data["applications_list"] = applications
        context.user_data["current_page"] = 0

        await display_application_page(update, context)

        return CHOOSE_APPLICATION

    except Exception as e:
        await update.message.reply_text(f"⚠️ Сталася помилка: {str(e)}")
        return ConversationHandler.END


def get_paginated_keyboard(applications, page, page_size):
    """Створення клавіатури для пагінації."""
    start = page * page_size
    end = start + page_size
    current_apps = applications[start:end]

    keyboard = [
        [InlineKeyboardButton(f"🆔 ID: {app['id']} | 📝 {app['description']}", callback_data=f"app_{app['id']}")]
        for app in current_apps
    ]

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data="prev_page"))
    if end < len(applications):
        nav_buttons.append(InlineKeyboardButton("➡️ Вперед", callback_data="next_page"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    return InlineKeyboardMarkup(keyboard)


async def display_application_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Відображення сторінки заявок."""
    applications = context.user_data["applications_list"]
    page = context.user_data["current_page"]
    reply_markup = get_paginated_keyboard(applications, page, PAGE_SIZE)

    if hasattr(update, "callback_query") and update.callback_query:
        await update.callback_query.edit_message_text("Виберіть заявку для закриття:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Виберіть заявку для закриття:", reply_markup=reply_markup)


async def navigate_pages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка переходу між сторінками."""
    query = update.callback_query
    await query.answer()

    if query.data == "prev_page":
        context.user_data["current_page"] -= 1
    elif query.data == "next_page":
        context.user_data["current_page"] += 1

    await display_application_page(update, context)
    return CHOOSE_APPLICATION


async def choose_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка вибору заявки користувачем."""
    query = update.callback_query
    await query.answer()
    application_id = query.data

    context.user_data["application_id"] = application_id

    keyboard = [
        [InlineKeyboardButton("Скасувати", callback_data="cancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=f"Ви вибрали заявку з ID: {application_id}. Завантажте файл для заявки (розмір до 5 МБ). Фото має бути надіслане як документ. 📤",
        reply_markup=reply_markup
    )
    return UPLOAD_FILES


async def upload_files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Завантаження файлів до заявки."""
    document = update.message.document

    if not document:
        await update.message.reply_text("❗ Файл має бути надісланий як документ, а не як фото.")
        return UPLOAD_FILES

    if document.file_size > MAX_FILE_SIZE:
        await update.message.reply_text("⚠️ Файл занадто великий. Спробуємо його стиснути...")

    file = await document.get_file()
    file_name = document.file_name
    file_data = await file.download_as_bytearray()

    await update.message.reply_text("🕒 Зачекайте, файл завантажується та стискається...")

    compressed_file = compress_file(file_data)
    if len(compressed_file) > MAX_FILE_SIZE:
        await update.message.reply_text("🚫 Файл навіть після стиснення перевищує дозволений розмір 5 МБ.")
        return UPLOAD_FILES

    if not context.user_data.get("files"):
        context.user_data["files"] = []

    context.user_data["files"].append((file_name, compressed_file))

    keyboard = [
        [InlineKeyboardButton("Завершити", callback_data="done")],
        [InlineKeyboardButton("Скасувати", callback_data="cancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "📥 Файл отримано та стиснуто. Якщо бажаєте, завантажте ще один або натисніть 'Завершити'.",
        reply_markup=reply_markup
    )
    return UPLOAD_FILES


async def handle_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка дії 'Завершити'. """
    query = update.callback_query
    await query.answer()

    await query.edit_message_reply_markup(reply_markup=None)
    await query.edit_message_text("🛠️ Зачекайте, обробка завершення заявки...")

    return await confirm_close_application(update, context)


async def confirm_close_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Підтвердження закриття заявки. """
    application_id = context.user_data.get("application_id")
    files = context.user_data.get("files", [])

    message = update.message or update.callback_query.message

    if not application_id:
        await message.reply_text("❗ Виберіть заявку перед підтвердженням закриття.")
        return ConversationHandler.END

    try:
        access_token = await ensure_valid_token(context)

        uploaded_files = []
        for file_name, file_data in files:
            uploaded_files.append((file_name, file_data))

        response = await close_application(access_token, application_id, uploaded_files)

        if response and isinstance(response, dict) and 'application_id' in response:
            await message.reply_text(
                f"✅ Заявка {response['application_id']} успішно закрита. Додано файлів: {len(response['files'])}."
            )
        else:
            error_detail = response.get('detail', 'Невідома помилка') if response else 'Невідома помилка'
            await message.reply_text(f"⚠️ Сталася помилка: {error_detail}")

    except Exception as e:
        await message.reply_text(f"⚠️ Сталася помилка: {str(e)}")

    return ConversationHandler.END


def compress_file(file_data: bytes) -> bytes:
    """Стискання файлу перед відправкою. """
    from io import BytesIO
    from PIL import Image

    try:
        image = Image.open(BytesIO(file_data))
        output = BytesIO()
        image.save(output, format="JPEG", quality=30)  # Максимальне стиснення
        return output.getvalue()
    except Exception:
        return file_data


async def cancel_closing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Скасування закриття заявки та повернення до головного меню. """
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    await query.edit_message_text("❌ Закриття заявки скасовано.")

    await update.callback_query.message.reply_text("🔙 Вас повернуто до головного меню.", reply_markup=main_menu_markup)
    return ConversationHandler.END


close_application_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^Закрити заявку$"), start_closing_application)],
    states={
        CHOOSE_APPLICATION: [
            CallbackQueryHandler(choose_application, pattern="^\d+$"),
            CallbackQueryHandler(navigate_pages, pattern="^(prev_page|next_page)$")
        ],
        UPLOAD_FILES: [
            MessageHandler(filters.Document.ALL, upload_files),
            CallbackQueryHandler(handle_done, pattern="^done$"),
            CallbackQueryHandler(cancel_closing, pattern="^cancel$")
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel_closing)],
)
