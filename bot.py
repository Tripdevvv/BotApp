import asyncio
import logging
from datetime import datetime, time, timedelta
from io import BytesIO
import json
import os

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from PIL import Image
import imagehash

API_TOKEN = os.getenv("TELEGRAM_API_TOKEN")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

chat_ids = [7481122885, 987654321]  # Вставь свои chat_id
sticker_id = 'CAACAgIAAyEFAASrJ8mAAANMaErQZWKogCvCcFz9Lsbau15gV2EAAvkfAAIbjKlKW3Z0JKAra_42BA'

HASHES_FILE = 'photo_hashes.json'
MAX_HAMMING_DISTANCE = 5  # Порог похожести (можно подстроить)

def load_hashes():
    if not os.path.exists(HASHES_FILE):
        logging.info("Файл с хешами не найден, создаём новый.")
        return {}
    with open(HASHES_FILE, 'r') as f:
        data = json.load(f)
    logging.info(f"Загружено {len(data)} хэшей из файла.")
    return data

def save_hashes(hashes_dict):
    with open(HASHES_FILE, 'w') as f:
        json.dump(hashes_dict, f)

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
    while True:
        now = datetime.now()
        target = datetime.combine(now.date(), remind_time)
        if target < now:
            target += timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        logging.info(f"Жду {wait_seconds} секунд до напоминания '{text[:20]}...'")
        await asyncio.sleep(wait_seconds)
        await send_reminder_all(text)

async def send_reminder_all(text: str):
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, text)
            logging.info(f"Напоминание отправлено в чат {chat_id}")
        except Exception as e:
            logging.error(f"Ошибка при отправке напоминания в чат {chat_id}: {e}")

@dp.message_handler(commands=['checkin'])
async def cmd_checkin(message: types.Message):
    await message.reply(CHECKIN_TEXT)
    logging.info(f"Команда /checkin вызвана пользователем {message.from_user.id}")

@dp.message_handler(commands=['checkout'])
async def cmd_checkout(message: types.Message):
    await message.reply(CHECKOUT_TEXT)
    logging.info(f"Команда /checkout вызвана пользователем {message.from_user.id}")

@dp.message_handler(commands=['sign'])
async def cmd_sign(message: types.Message):
    await message.reply(SIGN_TEXT)
    logging.info(f"Команда /sign вызвана пользователем {message.from_user.id}")

async def get_image_hash(file_id: str) -> str:
    file = await bot.get_file(file_id)
    file_path = file.file_path
    byte_stream = await bot.download_file(file_path)
    image = Image.open(BytesIO(byte_stream.read())).convert("RGB")
    hash_str = str(imagehash.phash(image))
    return hash_str

def hamming_distance(hash1: str, hash2: str) -> int:
    return bin(int(hash1, 16) ^ int(hash2, 16)).count('1')

@dp.message_handler(content_types=['photo'])
async def handle_photo(message: types.Message):
    photo = message.photo[-1]
    user_id = message.from_user.id
    chat_id = message.chat.id
    file_id = photo.file_id
    message_id = message.message_id

    logging.info(f"Получена фотография от пользователя {user_id} в чате {chat_id}")

    try:
        photo_hash = await get_image_hash(file_id)
    except Exception as e:
        logging.error(f"Ошибка при получении хэша фото: {e}")
        await message.reply("Не удалось обработать фотографию :(")
        return

    for saved_hash, msg_id in processed_hashes.items():
        dist = hamming_distance(photo_hash, saved_hash)
        if dist <= MAX_HAMMING_DISTANCE:
            logging.info(f"Фото похожее найдено с расстоянием {dist}: {photo_hash} vs {saved_hash}")
            try:
                await message.reply(
                    f"Это фото уже очень похоже на ранее загруженное (похожесть: {dist}). "
                    f"Предыдущее сообщение #{msg_id}"
                )
                await message.answer_sticker(sticker_id)
                await bot.forward_message(chat_id=chat_id, from_chat_id=chat_id, message_id=msg_id)
            except Exception as e:
                logging.error(f"Ошибка пересылки сообщения: {e}")
            return

    processed_hashes[photo_hash] = message_id
    save_hashes(processed_hashes)

    await message.reply("Фотография принята!")
    logging.info(f"Уникальная фотография от пользователя {user_id} обработана")

async def on_startup(dp):
    asyncio.create_task(schedule_reminder(time(hour=9, minute=45), CHECKIN_TEXT))
    asyncio.create_task(schedule_reminder(time(hour=15, minute=30), SIGN_TEXT))
    asyncio.create_task(schedule_reminder(time(hour=22, minute=14), CHECKOUT_TEXT))
    logging.info("Бот запущен и задачи по напоминаниям созданы.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
