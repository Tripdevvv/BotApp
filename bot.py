import asyncio
import logging
from datetime import datetime, time, timedelta
from io import BytesIO
import os
import pytz
import sqlite3

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

chat_ids = [7481122885, 987654321]  # Вставь свои chat_id
sticker_id = 'CAACAgIAAyEFAASrJ8mAAANMaErQZWKogCvCcFz9Lsbau15gV2EAAvkfAAIbjKlKW3Z0JKAra_42BA'

DB_FILE = os.path.join('/tmp', 'photo_hashes.db')  # База даних у тимчасовій директорії
MAX_HAMMING_DISTANCE = 5  # Порог похожести

def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS hashes (hash TEXT PRIMARY KEY, message_id INTEGER)''')
        conn.commit()
    except Exception as e:
        logging.error(f"Ошибка при инициализации базы данных: {str(e)}", exc_info=True)
    finally:
        conn.close()

def load_hashes():
    init_db()
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT hash, message_id FROM hashes")
        hashes = dict(c.fetchall())
        logging.info(f"Загружено {len(hashes)} хэшей из базы данных.")
        return hashes
    except Exception as e:
        logging.error(f"Ошибка при загрузке хэшей: {str(e)}", exc_info=True)
        return {}
    finally:
        conn.close()

def save_hashes(hashes_dict):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM hashes")  # Очищаємо таблицю перед оновленням
        c.executemany("INSERT INTO hashes (hash, message_id) VALUES (?, ?)", hashes_dict.items())
        conn.commit()
        logging.info(f"Хэши успешно сохранены в {DB_FILE}")
    except Exception as e:
        logging.error(f"Ошибка при сохранении хэшей в {DB_FILE}: {str(e)}", exc_info=True)
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
    timezone = pytz.timezone("Europe/Kiev")  # EEST, UTC+3
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
            logging.error(f"Ошибка в schedule_reminder: {str(e)}", exc_info=True)
            await asyncio.sleep(60)  # Пауза перед повторною спробою

async def send_reminder_all(text: str):
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, text)
            logging.info(f"Напоминание отправлено в чат {chat_id}")
        except Exception as e:
            logging.error(f"Ошибка при отправке напоминания в чат {chat_id}: {str(e)}", exc_info=True)

@dp.message_handler(commands=['checkin'])
async def cmd_checkin(message: types.Message):
    try:
        await message.reply(CHECKIN_TEXT)
        logging.info(f"Команда /checkin вызвана пользователем {message.from_user.id}")
    except Exception as e:
        logging.error(f"Ошибка в cmd_checkin: {str(e)}", exc_info=True)

@dp.message_handler(commands=['checkout'])
async def cmd_checkout(message: types.Message):
    try:
        await message.reply(CHECKOUT_TEXT)
        logging.info(f"Команда /checkout вызвана пользователем {message.from_user.id}")
    except Exception as e:
        logging.error(f"Ошибка в cmd_checkout: {str(e)}", exc_info=True)

@dp.message_handler(commands=['sign'])
async def cmd_sign(message: types.Message):
    try:
        await message.reply(SIGN_TEXT)
        logging.info(f"Команда /sign вызвана пользователем {message.from_user.id}")
    except Exception as e:
        logging.error(f"Ошибка в cmd_sign: {str(e)}", exc_info=True)

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
        logging.error(f"Ошибка в cmd_menu: {str(e)}", exc_info=True)

async def get_image_hash(file_id: str) -> str:
    try:
        file = await bot.get_file(file_id)
        file_path = file.file_path
        byte_stream = await bot.download_file(file_path)
        image = Image.open(BytesIO(byte_stream.read())).convert("RGB")
        hash_str = str(imagehash.phash(image))
        return hash_str
    except Exception as e:
        logging.error(f"Ошибка при получении хэша фото: {str(e)}", exc_info=True)
        raise

def hamming_distance(hash1: str, hash2: str) -> int:
    try:
        return bin(int(hash1, 16) ^ int(hash2, 16)).count('1')
    except Exception as e:
        logging.error(f"Ошибка при вычислении Hamming расстояния: {str(e)}", exc_info=True)
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
        logging.info(f"Текущие хэши: {processed_hashes}")  # Для відладки

        await message.reply("Фотография принята!")
        logging.info(f"Уникальная фотография от пользователя {user_id} обработана")
    except Exception as e:
        logging.error(f"Ошибка в handle_photo: {str(e)}", exc_info=True)
        await message.reply("Произошла ошибка при обработке фотографии :(")

# Налаштування вебхука
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "https://botapp-c4qw.onrender.com")  # Замініть на ваш URL
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

async def on_startup(dp):
    try:
        await bot.set_webhook(WEBHOOK_URL)
        asyncio.create_task(schedule_reminder(time(hour=9, minute=45), CHECKIN_TEXT))
        asyncio.create_task(schedule_reminder(time(hour=15, minute=30), SIGN_TEXT))
        asyncio.create_task(schedule_reminder(time(hour=22, minute14), CHECKOUT_TEXT))  # Виправлено minute
        logging.info("Бот запущен и вебхук установлен.")
    except Exception as e:
        logging.error(f"Ошибка при старте бота: {str(e)}", exc_info=True)

async def on_shutdown(dp):
    try:
        await bot.delete_webhook()
        logging.info("Бот остановлен.")
    except Exception as e:
        logging.error(f"Ошибка при остановке бота: {str(e)}", exc_info=True)

if __name__ == '__main__':
    try:
        executor.start_webhook(
            dispatcher=dp,
            webhook_path=WEBHOOK_PATH,
            on_startup=on_startup,
            on_shutdown=on_shutdown,
            skip_updates=True,
            host='0.0.0.0',
            port=int(os.getenv('PORT', 10000))
        )
    except Exception as e:
        logging.error(f"Ошибка при запуске вебхука: {str(e)}", exc_info=True)