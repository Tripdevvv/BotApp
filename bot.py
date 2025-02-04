from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Токен вашего бота
TOKEN = '8068604657:AAFUkVGe3OMcs8WTiqNaoKcQm9sAU3_OTDQ'

# Функция обработки команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я ваш бот!")

# Основная функция для запуска бота
def main():
    # Создание экземпляра Application с вашим токеном
    application = Application.builder().token(TOKEN).build()

    # Регистрация обработчика команды /start
    application.add_handler(CommandHandler("start", start))

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()
