from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = '8068604657:AAFUkVGe3OMcs8WTiqNaoKcQm9sAU3_OTDQ'  # Вставьте ваш токен

# Функция для обработки команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id  # Получаем Telegram ID
    user_name = update.message.from_user.first_name  # Имя пользователя

    # Отправляем приветственное сообщение с кнопкой для открытия WebApp
    keyboard = [
        [InlineKeyboardButton("Перейти в WebApp", url="https://testbot-8npt.onrender.com/")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Привет, {user_name}!\nЯ могу помочь тебе с расчетом сроков годности продуктов.",
        reply_markup=reply_markup
    )

    # Логирование ID пользователя для отправки данных
    print(f"Telegram ID пользователя: {user_id}")
    
    # Тут вы просто используете полученный user_id для отправки данных с сайта

# Функция для отправки данных с сайта в Telegram
async def send_to_telegram(telegram_id, product_name, shelf_life, start_date, end_date):
    message = f"Продукт: {product_name}\n"
    message += f"Срок годности: {shelf_life} дней\n"
    message += f"Начальный срок: {start_date}\n"
    message += f"Конечный срок: {end_date}"
    await bot.send_message(chat_id=telegram_id, text=message)

async def main() -> None:
    # Создаем объект Application для работы с ботом
    application = Application.builder().token(TOKEN).build()

    # Добавляем обработчик для команды /start
    application.add_handler(CommandHandler("start", start))

    # Запускаем бота (без использования asyncio.run)
    await application.run_polling()

if __name__ == '__main__':
    import asyncio
    # Запуск с использованием run_polling() без asyncio.run()
    asyncio.get_event_loop().run_until_complete(main())
