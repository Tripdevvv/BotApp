from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, CallbackContext
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = 'YOUR_BOT_TOKEN'  # Вставьте ваш токен
bot = Bot(TOKEN)

# Функция для обработки команды /start
def start(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id  # Получаем Telegram ID
    user_name = update.message.from_user.first_name  # Имя пользователя

    # Отправляем приветственное сообщение с кнопкой для открытия WebApp
    keyboard = [
        [InlineKeyboardButton("Перейти в WebApp", url="https://testbot-8npt.onrender.com/")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        f"Привет, {user_name}!\nЯ могу помочь тебе с расчетом сроков годности продуктов.",
        reply_markup=reply_markup
    )

    # Логирование ID пользователя для отправки данных
    print(f"Telegram ID пользователя: {user_id}")
    
    # Можете сохранить user_id в базе данных или файле для дальнейшего использования
    # Например, в файл:
    with open("user_ids.txt", "a") as f:
        f.write(f"{user_id}\n")

# Функция для отправки данных с сайта в Telegram
def send_to_telegram(telegram_id, product_name, shelf_life, start_date, end_date):
    message = f"Продукт: {product_name}\n"
    message += f"Срок годности: {shelf_life} дней\n"
    message += f"Начальный срок: {start_date}\n"
    message += f"Конечный срок: {end_date}"
    bot.send_message(chat_id=telegram_id, text=message)

def main() -> None:
    # Создаем объект Updater
    updater = Updater(TOKEN)

    # Получаем диспетчер для регистрации обработчиков
    dispatcher = updater.dispatcher

    # Добавляем обработчик для команды /start
    dispatcher.add_handler(CommandHandler("start", start))

    # Запускаем бота
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
