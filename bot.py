import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime, timedelta

API_TOKEN = '7234829726:AAHI1Cx9n-gt0Jxo-8UnpLE6-5HJHCHKo-I'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# временное хранилище
user_data = {}  # user_id: {region, stage, name, date}
products = []

# клавиатура для выбора региона
region_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Днепр")],
        [KeyboardButton(text="Киев")],
        [KeyboardButton(text="Львов")]
    ],
    resize_keyboard=True
)

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("👋 Привет! Выбери регион:", reply_markup=region_kb)
    user_data[message.from_user.id] = {"stage": "region"}

@dp.message()
async def handle_all(message: Message):
    user_id = message.from_user.id
    if user_id not in user_data:
        await message.answer("Нажмите /start чтобы начать.")
        return

    data = user_data[user_id]
    stage = data.get("stage")

    # шаг 1: выбор региона
    if stage == "region":
        region = message.text
        if region not in ["Днепр", "Киев", "Львов"]:
            await message.answer("❗ Пожалуйста, выбери регион с кнопки.")
            return
        data["region"] = region
        data["stage"] = "name"
        await message.answer("Введите название продукта:")
    
    # шаг 2: ввод названия продукта
    elif stage == "name":
        data["name"] = message.text
        data["stage"] = "date"
        await message.answer("Введите срок годности в формате ДД.ММ.ГГГГ (например: 28.07.2025):")
    
    # шаг 3: ввод даты
    elif stage == "date":
        try:
            exp = datetime.strptime(message.text, "%d.%m.%Y")
            notify = exp - timedelta(days=5)
            products.append({
                "region": data["region"],
                "name": data["name"],
                "exp": exp,
                "notify": notify,
                "chat_id": message.chat.id
            })
            user_data.pop(user_id)
            await message.answer(
                f"✅ Продукт добавлен:\n"
                f"📍 Регион: {data['region']}\n"
                f"🧀 Продукт: {data['name']}\n"
                f"📅 Срок: {exp.strftime('%d.%m.%Y')}\n"
                f"🔔 Напоминание: {notify.strftime('%d.%m.%Y')}",
                reply_markup=types.ReplyKeyboardRemove()
            )
        except:
            await message.answer("❗ Неверный формат даты. Пример: 28.07.2025")

async def reminder_loop():
    while True:
        now = datetime.now().date()
        for p in products:
            if p["notify"].date() == now:
                await bot.send_message(
                    p["chat_id"],
                    f"📦 Напоминание!\n"
                    f"Вернуть {p['name']} (регион: {p['region']}) на склад.\n"
                    f"Срок годности до {p['exp'].strftime('%d.%m.%Y')}."
                )
                p["notify"] += timedelta(days=9999)
        await asyncio.sleep(3600)  # раз в час

async def main():
    asyncio.create_task(reminder_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())