import asyncio
import logging
from datetime import datetime, time, timedelta
from io import BytesIO
import os
import pytz
import psycopg2
import json

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from PIL import Image
import imagehash

# Налаштування
API_TOKEN = os.getenv("TELEGRAM_API_TOKEN")
if not API_TOKEN:
    raise ValueError("Переменная окружения TELEGRAM_API_TOKEN не установлена")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

chat_ids = [7481122885, 987654321]
sticker_id = 'CAACAgIAAyEFAASrJ8mAAANMaErQZWKogCvCcFz9Lsbau15gV2EAAvkfAAIbjKlKW3Z0JKAra_42BA'

# Настройка подключения к PostgreSQL
DB_URL = "postgresql://tgbotbdhash_owner:npg_gfBetc17QRZO@ep-lingering-glade-a8g30xtc-pooler.eastus2.azure.neon.tech/tgbotbdhash?sslmode=require"
MAX_HAMMING_DISTANCE = 5

def init_db():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS photo_hashes (
                hash TEXT PRIMARY KEY,
                message_id INTEGER
            )
        """)
        conn.commit()
        logging.info("Таблица photo_hashes успешно создана или уже существует.")
    except Exception as e:
        logging.error(f"Ошибка при инициализации базы данных: {str(e)}")
    finally:
        conn.close()

def load_hashes():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT hash, message_id FROM photo_hashes")
        hashes = dict(cur.fetchall())
        logging.info(f"Загружено {len(hashes)} хэшей из базы данных.")
        return hashes
    except Exception as e:
        logging.error(f"Ошибка при загрузке хэшей: {str(e)}")
        return {}
    finally:
        conn.close()

def save_hashes(hashes_dict):
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        # Очищаем таблицу и вставляем новые данные
        cur.execute("DELETE FROM photo_hashes")
        for hash_value, msg_id in hashes_dict.items():
            cur.execute("INSERT INTO photo_hashes (hash, message_id) VALUES (%s, %s)", (hash_value, msg_id))
        conn.commit()
        logging.info(f"Хэши успешно сохранены в базе данных.")
    except Exception as e:
        logging.error(f"Ошибка при сохранении хэшей: {str(e)}")
    finally:
        conn.close()

processed_hashes = load_hashes()

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

async def schedule_reminder(remind_time: time, text: str):
    timezone = pytz.timezone("Europe/Kiev")
    while True:
        try:
            now = datetime.now(timezone)
            target = datetime.combine(now.date(), remind_time, tzinfo=timezone)
            if target < now:
                target += timedelta(days=1)
            wait_seconds = (target - now).total_seconds()
            logging.info(f"Жду {wait_seconds} секунд до напоминания '{text[:20]}...'")
            await asyncio.sleep(wait_seconds)
            await send_reminder_all(text)
        except Exception as e:
            logging.error(f"Ошибка в schedule_reminder: {str(e)}")
            await asyncio.sleep(60)

async def send_reminder_all(text: str):
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, text)
            logging.info(f"Напоминание отправлено в чат {chat_id}")
        except Exception as e:
            logging.error(f"Ошибка при отправке напоминания в чат {chat_id}: {str(e)}")

@dp.message_handler(commands=['checkin'])
async def cmd_checkin(message: types.Message):
    try:
        await message.reply(CHECKIN_TEXT)
        logging.info(f"Команда /checkin вызвана пользователем {message.from_user.id}")
    except Exception as e:
        logging.error(f"Ошибка в cmd_checkin: {str(e)}")

@dp.message_handler(commands=['checkout'])
async def cmd_checkout(message: types.Message):
    try:
        await message.reply(CHECKOUT_TEXT)
        logging.info(f"Команда /checkout вызвана пользователем {message.from_user.id}")
    except Exception as e:
        logging.error(f"Ошибка в cmd_checkout: {str(e)}")

@dp.message_handler(commands=['sign'])
async def cmd_sign(message: types.Message):
    try:
        await message.reply(SIGN_TEXT)
        logging.info(f"Команда /sign вызвана пользователем {message.from_user.id}")
    except Exception as e:
        logging.error(f"Ошибка в cmd_sign: {str(e)}")

@dp.message_handler(commands=['menu'])
async def cmd_menu(message: types.Message):
    try:
        keyboard = InlineKeyboardMarkup()
        schedule_button = InlineKeyboardButton(
            text="График",
            url="https://docs.google.com/spreadsheets/u/0/d/1HtCpJSc_Y8MF4BcYzYaz6rL7RvzrPY7s/htmlview?pli=1"
        )
        products_button = InlineKeyboardButton(
            text="Разрешенные продукты",
            url="https://docs.google.com/spreadsheets/u/0/d/1HtCpJSc_Y8MF4BcYzYaz6rL7RvzrPY7s/htmlview?pli=1"
        )
        keyboard.row(schedule_button, products_button)
        await message.reply("Выберите опцию:", reply_markup=keyboard)
        logging.info(f"Команда /menu вызвана пользователем {message.from_user.id}")
    except Exception as e:
        logging.error(f"Ошибка в cmd_menu: {str(e)}")

async def get_image_hash(file_id: str) -> str:
    try:
        file = await bot.get_file(file_id)
        file_path = file.file_path
        byte_stream = await bot.download_file(file_path)
        image = Image.open(BytesIO(byte_stream.read())).convert("RGB")
        hash_str = str(imagehash.phash(image))
        return hash_str
    except Exception as e:
        logging.error(f"Ошибка при получении хэша фото: {str(e)}")
        raise

def hamming_distance(hash1: str, hash2: str) -> int:
    try:
        return bin(int(hash1, 16) ^ int(hash2, 16)).count('1')
    except Exception as e:
        logging.error(f"Ошибка при вычислении Hamming расстояния: {str(e)}")
        return float('inf')

@dp.message_handler(content_types=['photo'])
async def handle_photo(message: types.Message):
    try:
        photo = message.photo[-1]
        user_id = message.from_user.id
        chat_id = message.chat.id
        file_id = photo.file_id
        message_id = message.message_id

        logging.info(f"Получена фотография от пользователя {user_id} в чате {chat_id}")

        photo_hash = await get_image_hash(file_id)

        for saved_hash, msg_id in processed_hashes.items():
            dist = hamming_distance(photo_hash, saved_hash)
            if dist <= MAX_HAMMING_DISTANCE:
                logging.info(f"Фото похожее найдено с расстоянием {dist}: {photo_hash} vs {saved_hash}")
                await message.reply(
                    f"Это фото уже очень похоже на ранее загруженное (похожесть: {dist}). "
                    f"Предыдущее сообщение #{msg_id}"
                )
                await message.answer_sticker(sticker_id)
                await bot.forward_message(chat_id=chat_id, from_chat_id=chat_id, message_id=msg_id)
                return

        processed_hashes[photo_hash] = message_id
        save_hashes(processed_hashes)
        logging.info(f"Текущие хэши: {processed_hashes}")

        await message.reply("Фотография принята!")
        logging.info(f"Уникальная фотография от пользователя {user_id} обработана")
    except Exception as e:
        logging.error(f"Ошибка в handle_photo: {str(e)}")
        await message.reply("Произошла ошибка при обработке фотографии :(")

# Налаштування вебхука
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "https://botapp-c4qw.onrender.com")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

async def on_startup(dp):
    try:
        await bot.set_webhook(WEBHOOK_URL)
        asyncio.create_task(schedule_reminder(time(hour=9, minute=45), CHECKIN_TEXT))
        asyncio.create_task(schedule_reminder(time(hour=15, minute=30), SIGN_TEXT))
        asyncio.create_task(schedule_reminder(time(hour=22, minute=14), CHECKOUT_TEXT))
        init_db()  # Инициализация таблицы при старте
        logging.info("Бот запущен и вебхук установлен.")
    except Exception as e:
        logging.error(f"Ошибка при старте бота: {str(e)}")

async def on_shutdown(dp):
    try:
        await bot.delete_webhook()
        logging.info("Бот остановлен.")
    except Exception as e:
        logging.error(f"Ошибка при остановке бота: {str(e)}")

if __name__ == '__main__':
    executor.start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host='0.0.0.0',
        port=int(os.getenv('PORT', 10000))
    )