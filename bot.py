import asyncio
import logging
from threading import Thread
from datetime import datetime, time, timedelta
from io import BytesIO
import os

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from PIL import Image
import imagehash
import psycopg2
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
import uvicorn
import pytz

# Настройка логов
logging.basicConfig(level=logging.INFO)

# Переменные окружения и настройки
API_TOKEN = os.getenv("TELEGRAM_API_TOKEN")
if not API_TOKEN:
    raise ValueError("Не задан TELEGRAM_API_TOKEN в переменных окружения")

DB_URL = "postgresql://tgbotbdhash_owner:npg_gfBetc17QRZO@ep-lingering-glade-a8g30xtc-pooler.eastus2.azure.neon.tech/tgbotbdhash?sslmode=require"
MAX_HAMMING_DISTANCE = 5
chat_ids = [7481122885, 987654321]  # Замените на нужные chat_id
sticker_id = 'CAACAgIAAyEFAASrJ8mAAANMaErQZWKogCvCcFz9Lsbau15gV2EAAvkfAAIbjKlKW3Z0JKAra_42BA'

# Инициализация Aiogram и FastAPI
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Маршруты FastAPI
@app.get("/")
async def root():
    return {"status": "Bot is alive!"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Подключение к БД
def get_db_connection():
    return psycopg2.connect(DB_URL)

def init_db():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS photo_hashes (
                    hash TEXT PRIMARY KEY,
                    message_id INTEGER,
                    chat_id BIGINT,
                    user_id BIGINT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    logging.info("База данных инициализирована")

# Очистка старых хэшей
def clean_old_hashes():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM photo_hashes WHERE timestamp < NOW() - INTERVAL '14 days'")
                logging.info(f"Удалено {cur.rowcount} старых записей")
                conn.commit()
    except Exception as e:
        logging.error(f"Ошибка при очистке хэшей: {e}")

async def periodic_cleanup():
    while True:
        clean_old_hashes()
        await asyncio.sleep(14 * 24 * 3600)

# Загрузка и сохранение хэшей
def load_hashes():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT hash, message_id, chat_id FROM photo_hashes")
                return {(h, c): m for h, m, c in cur.fetchall()}
    except Exception as e:
        logging.error(f"Ошибка загрузки хэшей: {e}")
        return {}

def save_hash(hash_value: str, message_id: int, chat_id: int, user_id: int):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO photo_hashes (hash, message_id, chat_id, user_id)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (hash) DO NOTHING
                """, (hash_value, message_id, chat_id, user_id))
                conn.commit()
    except Exception as e:
        logging.error(f"Ошибка сохранения хэша: {e}")

photo_hashes = load_hashes()

# Тексты напоминаний
CHECKIN_TEXT = (
    "Напоминаю сделать чек-ин в основном боте @PizzaDayStaffBot...\n"
    "1. Фото включенных телевизоров\n"
    "2. Фото формы персонала...\n"
    "9. Фото включенной вытяжки"
)

SIGN_TEXT = "Напоминаю включить вывеску и отправить фотоочет :)"

CHECKOUT_TEXT = (
    "Напоминаю сделать чек-аут в основном боте @PizzaDayStaffBot...\n"
    "1. Модуль нарезки продуктов...\n"
    "11. Чистая лопата\n"
    "1. Выключенные телевизоры и техника...\n"
    "4. Температура в вертикальном холодильнике"
)

# Команды
@dp.message_handler(commands=['menu'])
async def cmd_menu(message: types.Message):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📅 График работы", url="https://docs.google.com/spreadsheets/d/..."),
        InlineKeyboardButton("🛒 Разрешенные продукты", url="https://docs.google.com/spreadsheets/d/...")
    )
    await message.reply("📌 Доступные ресурсы:", reply_markup=kb)

@dp.message_handler(commands=['checkin'])
async def cmd_checkin(message: types.Message):
    await message.reply(CHECKIN_TEXT)

@dp.message_handler(commands=['checkout'])
async def cmd_checkout(message: types.Message):
    await message.reply(CHECKOUT_TEXT)

@dp.message_handler(commands=['sign'])
async def cmd_sign(message: types.Message):
    await message.reply(SIGN_TEXT)

# Фотохэши
def hamming_distance(h1: str, h2: str) -> int:
    return bin(int(h1, 16) ^ int(h2, 16)).count('1')

async def get_image_hash(file_id: str) -> str:
    try:
        file = await bot.get_file(file_id)
        stream = BytesIO()
        await file.download(destination_file=stream)
        image = Image.open(stream).convert("RGB")
        return str(imagehash.phash(image))
    except Exception as e:
        logging.error(f"Ошибка хэша изображения: {e}")
        return ""

@dp.message_handler(content_types=['photo'])
async def handle_photo(message: types.Message):
    if message.chat.id not in chat_ids:
        return

    photo = message.photo[-1]
    photo_hash = await get_image_hash(photo.file_id)

    if not photo_hash:
        await message.reply("⚠️ Ошибка при обработке изображения.")
        return

    for (saved_hash, saved_chat_id), saved_msg_id in photo_hashes.items():
        if saved_chat_id == message.chat.id and hamming_distance(photo_hash, saved_hash) <= MAX_HAMMING_DISTANCE:
            await message.reply(f"⚠️ Похоже на ранее отправленное фото (сообщение #{saved_msg_id})")
            await message.answer_sticker(sticker_id)
            await bot.forward_message(message.chat.id, message.chat.id, saved_msg_id)
            return

    photo_hashes[(photo_hash, message.chat.id)] = message.message_id
    save_hash(photo_hash, message.message_id, message.chat.id, message.from_user.id)
    await message.reply("✅ Фото принято!")

# Напоминания
async def schedule_reminder(remind_time: time, text: str):
    timezone = pytz.timezone("Europe/Kiev")
    while True:
        now = datetime.now(timezone)
        target = datetime.combine(now.date(), remind_time, tzinfo=timezone)
        if target < now:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        await send_reminder_all(text)

async def send_reminder_all(text: str):
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, text)
        except Exception as e:
            logging.error(f"Ошибка при отправке в {chat_id}: {e}")

# Запуск
async def on_startup(dp):
    await bot.delete_webhook(drop_pending_updates=True)
    init_db()
    asyncio.create_task(schedule_reminder(time(9, 45), CHECKIN_TEXT))
    asyncio.create_task(schedule_reminder(time(15, 30), SIGN_TEXT))
    asyncio.create_task(schedule_reminder(time(22, 14), CHECKOUT_TEXT))
    asyncio.create_task(periodic_cleanup())
    logging.info("Бот готов")

def run_fastapi():
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    Thread(target=run_fastapi, daemon=True).start()
    executor.start_polling(dp, on_startup=on_startup, skip_updates=True)