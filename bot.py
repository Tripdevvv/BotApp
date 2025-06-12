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

# Настройки логирования
logging.basicConfig(level=logging.INFO)

# Настройки бота
API_TOKEN = os.getenv("TELEGRAM_API_TOKEN")
if not API_TOKEN:
    raise ValueError("Переменная окружения TELEGRAM_API_TOKEN не установлена")

DB_URL = "postgresql://tgbotbdhash_owner:npg_gfBetc17QRZO@ep-lingering-glade-a8g30xtc-pooler.eastus2.azure.neon.tech/tgbotbdhash?sslmode=require"
MAX_HAMMING_DISTANCE = 5
chat_ids = [7481122885, 987654321]
sticker_id = 'CAACAgIAAyEFAASrJ8mAAANMaErQZWKogCvCcFz9Lsbau15gV2EAAvkfAAIbjKlKW3Z0JKAra_42BA'

# Инициализация бота
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# FastAPI для предотвращения засыпания
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/")
async def root():
    logging.info("Root endpoint called")
    return {"status": "Bot is alive!"}

@app.get("/health")
async def health_check():
    logging.info("Health check endpoint called")
    return {"status": "healthy"}

# Функции для работы с базой данных
def get_db_connection():
    return psycopg2.connect(DB_URL)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Создаем таблицу, если она не существует
        cur.execute("""
            CREATE TABLE IF NOT EXISTS photo_hashes (
                hash TEXT PRIMARY KEY,
                message_id INTEGER,
                chat_id BIGINT,
                user_id BIGINT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Проверяем, существует ли столбец chat_id, и добавляем его, если отсутствует
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_name = 'photo_hashes' AND column_name = 'chat_id'
                ) THEN
                    ALTER TABLE photo_hashes ADD COLUMN chat_id BIGINT;
                END IF;
            END $$;
        """)
        conn.commit()
        logging.info("База данных инициализирована")
    except Exception as e:
        logging.error(f"Ошибка при инициализации БД: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def clean_old_hashes():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM photo_hashes WHERE timestamp < NOW() - INTERVAL '14 days'")
        deleted = cur.rowcount
        conn.commit()
        logging.info(f"Удалено {deleted} старых записей из базы данных.")
    except Exception as e:
        logging.error(f"Ошибка при очистке базы: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

async def periodic_cleanup():
    while True:
        clean_old_hashes()
        await asyncio.sleep(14 * 24 * 60 * 60)  # 14 дней

def load_hashes():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT hash, message_id, chat_id FROM photo_hashes WHERE chat_id IS NOT NULL")
        return {(row[0], row[2]): row[1] for row in cur.fetchall()}  # (hash, chat_id): message_id
    except Exception as e:
        logging.error(f"Ошибка при загрузке хэшей: {e}")
        return {}
    finally:
        if 'conn' in locals():
            conn.close()

def save_hash(hash_value: str, message_id: int, chat_id: int, user_id: int):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO photo_hashes (hash, message_id, chat_id, user_id) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (hash) DO NOTHING",
            (hash_value, message_id, chat_id, user_id)
        )
        conn.commit()
        logging.info(f"Хэш сохранен: {hash_value}")
    except Exception as e:
        logging.error(f"Ошибка при сохранении хэша: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

# Глобальная переменная для хранения хэшей
photo_hashes = load_hashes()

# Тексты напоминаний
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

# Обработчики команд
@dp.message_handler(commands=['menu'])
async def cmd_menu(message: types.Message):
    keyboard = InlineKeyboardMarkup(row_width=1)
    buttons = [
        InlineKeyboardButton(text="📅 График работы", url="https://docs.google.com/spreadsheets/d/1HtCpJSc_Y8MF4BcYzYaz6rL7RvzrPY7s/edit"),
        InlineKeyboardButton(text="🛒 Разрешенные продукты", url="https://docs.google.com/spreadsheets/d/1HtCpJSc_Y8MF4BcYzYaz6rL7RvzrPY7s/edit")
    ]
    keyboard.add(*buttons)
    await message.reply("📌 Доступные ресурсы:", reply_markup=keyboard)

@dp.message_handler(commands=['checkin'])
async def cmd_checkin(message: types.Message):
    await message.reply(CHECKIN_TEXT)

@dp.message_handler(commands=['checkout'])
async def cmd_checkout(message: types.Message):
    await message.reply(CHECKOUT_TEXT)

@dp.message_handler(commands=['sign'])
async def cmd_sign(message: types.Message):
    await message.reply(SIGN_TEXT)

# Обработка фотографий
def hamming_distance(hash1: str, hash2: str) -> int:
    try:
        return bin(int(hash1, 16) ^ int(hash2, 16)).count('1')
    except Exception:
        return float('inf')

async def get_image_hash(file_id: str) -> str:
    try:
        file = await bot.get_file(file_id)
        byte_stream = BytesIO()
        await file.download(destination_file=byte_stream)
        image = Image.open(byte_stream).convert("RGB")
        return str(imagehash.phash(image))
    except Exception as e:
        logging.error(f"Ошибка при получении хэша изображения: {e}")
        return ""

@dp.message_handler(content_types=['photo'])
async def handle_photo(message: types.Message):
    if message.chat.id not in chat_ids:
        return
    
    try:
        photo = message.photo[-1]
        photo_hash = await get_image_hash(photo.file_id)
        
        if not photo_hash:
            await message.reply("Не удалось обработать фотографию. Пожалуйста, попробуйте еще раз.")
            return
        
        # Проверяем только хэши из текущего чата
        duplicate_found = False
        for (saved_hash, saved_chat_id), saved_msg_id in photo_hashes.items():
            if saved_chat_id == message.chat.id and hamming_distance(photo_hash, saved_hash) <= MAX_HAMMING_DISTANCE:
                duplicate_found = True
                await message.reply(
                    f"⚠️ Это фото похоже на ранее загруженное (сообщение #{saved_msg_id})"
                )
                await message.answer_sticker(sticker_id)
                await bot.forward_message(
                    chat_id=message.chat.id,
                    from_chat_id=message.chat.id,
                    message_id=saved_msg_id
                )
                break
        
        if not duplicate_found:
            photo_hashes[(photo_hash, message.chat.id)] = message.message_id
            save_hash(photo_hash, message.message_id, message.chat.id, message.from_user.id)
            await message.reply("✅ Фотография принята!")
            
    except Exception as e:
        logging.error(f"Ошибка при обработке фото: {e}")
        await message.reply("Произошла ошибка при обработке фотографии. Пожалуйста, попробуйте еще раз.")

# Планировщик напоминаний
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
            logging.info(f"Напоминание отправлено в чат {chat_id}")
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение в {chat_id}: {e}")

# Запуск бота
async def on_startup(dp):
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("Webhook deleted successfully")
    except Exception as e:
        logging.error(f"Error deleting webhook: {e}")

    init_db()
    asyncio.create_task(schedule_reminder(time(9, 45), CHECKIN_TEXT))
    asyncio.create_task(schedule_reminder(time(15, 30), SIGN_TEXT))
    asyncio.create_task(schedule_reminder(time(22, 14), CHECKOUT_TEXT))
    asyncio.create_task(periodic_cleanup())
    logging.info("Бот запущен")

def run_fastapi():
    port = int(os.getenv("PORT", 10000))
    logging.info(f"Starting FastAPI on port: {port}")
    try:
        uvicorn.run(app, host="0.0.0.0", port=port)
    except Exception as e:
        logging.error(f"Failed to start FastAPI: {e}")

if __name__ == '__main__':
    # Запускаем FastAPI в отдельном потоке
    fastapi_thread = Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()

    # Запускаем Telegram-бота
    executor.start_polling(dp, on_startup=on_startup, skip_updates=True)