import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

API_TOKEN = '7234829726:AAHI1Cx9n-gt0Jxo-8UnpLE6-5HJHCHKo-I'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

products = []
user_states = {}

regions = ["Днепр", "Киев", "Львов"]

region_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=region, callback_data=f"region_{region}")] for region in regions
    ]
)

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("👋 Привет! Выбери регион:", reply_markup=region_keyboard)

@dp.callback_query(F.data.startswith("region_"))
async def region_chosen(callback: CallbackQuery):
    region = callback.data.split("_")[1]
    user_states[callback.from_user.id] = {"region": region}
    await callback.message.answer(
        f"✅ Регион {region} выбран!\nВведите продукт и срок в формате:\nПример: Моцарелла 28.07.2025"
    )
    await callback.answer()

@dp.message()
async def get_product(message: Message):
    uid = message.from_user.id
    if uid not in user_states or "region" not in user_states[uid]:
        return await message.answer("⚠️ Сначала выбери регион: /start")

    try:
        name, date_str = message.text.strip().split()
        exp_date = datetime.strptime(date_str, "%d.%m.%Y")
        notify_date = exp_date - timedelta(days=5)

        products.append({
            "chat_id": message.chat.id,
            "name": name,
            "exp": exp_date,
            "notify": notify_date,
            "region": user_states[uid]["region"]
        })

        await message.answer(
            f"📦 Продукт добавлен!\n"
            f"Название: {name}\n"
            f"Регион: {user_states[uid]['region']}\n"
            f"Срок хранения: {exp_date.strftime('%d.%m.%Y')}\n"
            f"🔔 Напомню: {notify_date.strftime('%d.%m.%Y')}"
        )
    except Exception as e:
        await message.answer("⚠️ Неверный формат. Пример: Моцарелла 28.07.2025")

async def reminder_loop():
    while True:
        now = datetime.now().date()
        for product in products:
            if product["notify"].date() == now:
                await bot.send_message(
                    product["chat_id"],
                    f"⏰ Напоминание!\n"
                    f"Пора вернуть продукт **{product['name']}** (регион: {product['region']}) на склад.\n"
                    f"Срок годности: {product['exp'].strftime('%d.%m.%Y')}."
                )
                product["notify"] += timedelta(days=9999)
        await asyncio.sleep(3600)  # проверять каждый час

async def main():
    asyncio.create_task(reminder_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())