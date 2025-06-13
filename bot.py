import os
import asyncio
import logging
from threading import Thread
from datetime import datetime, time, timedelta
from io import BytesIO

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from PIL import Image
import imagehash
import psycopg2
from psycopg2.extras import DictCursor

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
import uvicorn
import pytz

logging.basicConfig(level=logging.INFO)

# --- Конфигурация ---
API_TOKEN = os.getenv("TELEGRAM_API_TOKEN")
if not API_TOKEN:
    raise ValueError("Переменная окружения TELEGRAM_API_TOKEN не установлена")

DB_URL = "postgresql://tgbotbdhash_owner:npg_gfBetc17QRZO@ep-lingering-glade-a8g30xtc-pooler.eastus2.azure.neon.tech/tgbotbdhash?sslmode=require"

MAX_HAMMING_DISTANCE = 5
CHAT_IDS = [7481122885]  # Добавь нужные chat_id
STICKER_ID = 'CAACAgIAAyEFAASrJ8mAAANMaErQZWKogCvCcFz9Lsbau15gV2EAAvkfAAIbjKlKW3Z0JKAra_42BA'

CHECKIN_TEXT = (
    "Напоминаю сделать чек-ин в основном боте @PizzaDayStaffBot, не сделанный чек-ин — потеря денюжек :(\n\n"
    "1. Фото включенных телевизоров\n"
    "2. Фото формы персонала, который работает в смене\n"
    "3. Фото количества заготовок на кухне\n"
    "4. Фото включенной вывески\n"
    "5. Фото включенной печи\n"
    "6. Фото температуры в холодильниках (раскладка и вертикальный холодильник)\n"
    "7. Фото холодильника с напитками\n"
    "8. Фото морозилки\n"
    "9. Фото включенной вытяжки"
)

SIGN_TEXT = "Напоминаю включить вывеску и отправить фотоочет :)"

CHECKOUT_TEXT = (
    "Напоминаю сделать чек-аут в основном боте @PizzaDayStaffBot\n\n"
    "Также жду Фотоотчет замывки:\n"
    "1. Модуль нарезки продуктов, снаружи и внутри\n"
    "2. Металлическую полку над мойкой\n"
    "3. Мойку\n"
    "4. Модуль раскатки теста\n"
    "5. Тестомес\n"
    "6. Раскладку снаружи и внутри\n"
    "7. Желтые полки\n"
    "8. Модуль нарезки пицц\n"
    "9. Кассовую зону\n"
    "10. Чистый пол\n"
    "11. Чистую лопату\n"
    "———————————————\n"
    "1. Выключенные телевизоры/кондиционеры/печь/мухобойка/вытяжка\n"
    "2. Закрытая расклада\n"
    "3. Температура в раскладе\n"
    "4. Температура в вертикальном холодильнике"
)

# --- Инициализация бота ---
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- Инициализация FastAPI ---
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/")
async def root():
    return {"status": "Bot is alive!"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# --- Работа с БД ---
def get_db_connection():
    return psycopg2.connect(DB_URL, cursor_factory=DictCursor)

def init_db():
    conn = get_db_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS photos (
                    id SERIAL PRIMARY KEY,
                    photo_hash TEXT UNIQUE,
                    timestamp TIMESTAMP NOT NULL DEFAULT NOW()
                );
            """)
    conn.close()

def photo_exists(photo_hash):
    conn = get_db_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT photo_hash FROM photos WHERE photo_hash = %s;", (photo_hash,))
            res = cur.fetchone()
    conn.close()
    return res is not None

def add_photo_hash(photo_hash):
    conn = get_db_connection()
    with conn:
        with conn.cursor() as cur:
            try:
                cur.execute("INSERT INTO photos (photo_hash) VALUES (%s);", (photo_hash,))
            except psycopg2.errors.UniqueViolation:
                # Если хэш уже есть, игнорируем ошибку
                pass
    conn.close()

def cleanup_old_photos(days=30):
    conn = get_db_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM photos WHERE timestamp < NOW() - INTERVAL '%s days';", (days,))
    conn.close()

# --- Хэширование и сравнение фото ---
async def get_image_hash(file_id):
    file = await bot.get_file(file_id)
    file_path = file.file_path
    file_bytes = await bot.download_file(file_path)
    img = Image.open(BytesIO(file_bytes.getvalue()))
    img_hash = imagehash.average_hash(img)
    return img_hash

def is_similar_hash(hash1, hash2, max_distance=MAX_HAMMING_DISTANCE):
    return hash1 - hash2 <= max_distance

# --- Обработчики команд и сообщений ---
@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message):
    await message.reply("Привет! Отправь фото для проверки.")

@dp.message_handler(content_types=types.ContentType.PHOTO)
async def handle_photo(message: types.Message):
    # Берем фото с максимальным разрешением
    photo = message.photo[-1]
    img_hash = await get_image_hash(photo.file_id)

    # Проверяем в базе наличие похожего фото
    conn = get_db_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT photo_hash FROM photos;")
            all_hashes = cur.fetchall()

    for row in all_hashes:
        stored_hash = imagehash.hex_to_hash(row['photo_hash'])
        if is_similar_hash(img_hash, stored_hash):
            await message.reply("Это фото уже было отправлено ранее.")
            return

    # Если не нашли похожих - добавляем новый хэш
    add_photo_hash(str(img_hash))
    await message.reply("Фото принято и сохранено!")

# --- Планировщик напоминаний ---
async def schedule_reminder(remind_time: time, text: str):
    tz = pytz.timezone("Europe/Moscow")
    while True:
        now = datetime.now(tz)
        target = datetime.combine(now.date(), remind_time, tzinfo=tz)
        if now > target:
            target += timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        for chat_id in CHAT_IDS:
            try:
                await bot.send_sticker(chat_id, STICKER_ID)
                await bot.send_message(chat_id, text)
            except Exception as e:
                logging.error(f"Ошибка отправки напоминания {e}")

# --- Очистка базы ---
async def periodic_cleanup():
    while True:
        cleanup_old_photos(days=30)
        await asyncio.sleep(24*60*60)  # каждый день

# --- Запуск бота ---
async def on_startup(dp):
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("Webhook успешно удалён")
    except Exception as e:
        logging.error(f"Ошибка при удалении webhook: {e}")

    init_db()

    asyncio.create_task(schedule_reminder(time(9, 45), CHECKIN_TEXT))
    asyncio.create_task(schedule_reminder(time(15, 30), SIGN_TEXT))
    asyncio.create_task(schedule_reminder(time(22, 14), CHECKOUT_TEXT))
    asyncio.create_task(periodic_cleanup())

    logging.info("Бот запущен и задачи созданы")

def run_fastapi():
    port = int(os.getenv("PORT", 10000))
    logging.info(f"Запуск FastAPI на порту: {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == '__main__':
    fastapi_thread = Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start() 

    executor.start_polling(dp, on_startup=on_startup, skip_updates=True)