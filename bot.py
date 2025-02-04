from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# Токен вашего бота
TOKEN = '8068604657:AAFUkVGe3OMcs8WTiqNaoKcQm9sAU3_OTDQ'

# Функция обработки команды /start
def start(update: Update, context: CallbackContext):
    update.message.reply_text("Привет! Я ваш бот!")

# Основная функция для запуска бота
def main():
    # Создание экземпляра Updater с вашим токеном
    updater = Updater(TOKEN, use_context=True)

    # Получаем диспетчер для регистрации обработчиков
    dispatcher = updater.dispatcher

    # Регистрация обработчика команды /start
    dispatcher.add_handler(CommandHandler("start", start))

    # Запуск polling (периодический опрос серверов Telegram)
    updater.start_polling()

    # Бот будет работать до остановки
    updater.idle()

if __name__ == '__main__':
    main()
