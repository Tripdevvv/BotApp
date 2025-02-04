import os
import logging
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, filters
import uvicorn

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "ваш_токен_бота"
WEBHOOK_URL = "ваш_вебхук_url"  # Указывайте URL вебхука, если используете его

if not TOKEN:
    raise ValueError("Токен не найден!")

# Создаём FastAPI-приложение
fastapi_app = FastAPI()

# Объект бота
bot = Bot(token=TOKEN)
app = None  # Глобальная переменная для бота


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """Инициализация и завершение работы бота."""
    global app
    app = Application.builder().token(TOKEN).build()

    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_message))

    # Запуск бота
    await app.initialize()
    
    # Используем polling или вебхук
    if WEBHOOK_URL:
        await bot.set_webhook(WEBHOOK_URL)
        logger.info(f"Webhook установлен: {WEBHOOK_URL}")
    else:
        await app.start()
        await app.updater.start_polling()
        logger.info("Бот запущен через polling")

    yield  # Ожидание завершения

    # Остановка бота
    await app.updater.stop()
    await app.stop()
    await app.shutdown()
    logger.info("Бот остановлен!")


# Команда /start
async def start_command(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Привет! Я бот для расчёта сроков годности продуктов.")


# Команда /help
async def help_command(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Доступные команды:\n/start - Начать\n/help - Помощь")


# Эхо-ответ на сообщения
async def echo_message(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(f"Вы сказали: {update.message.text}")


# Обработка вебхука
@fastapi_app.post("/webhook")
async def webhook(request: Request):
    """Обработка обновлений от Telegram через вебхук."""
    try:
        data = await request.json()
        update = Update.de_json(data, bot)
        await app.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Ошибка обработки вебхука: {e}")
        return {"error": str(e)}

# Обработчик для корневого маршрута
@fastapi_app.get("/")
async def root():
    return {"message": "Hello, this is the bot server!"}

# Запуск приложения с uvicorn
if __name__ == "__main__":
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)
