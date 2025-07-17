import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

API_TOKEN = 'YOUR_BOT_TOKEN'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Простая in-memory база (можно заменить на БД)
products = []

@dp.message(Command("добавить"))
async def cmd_add(message: Message):
    try:
        _, region, name, date_str = message.text.split()
        exp_date = datetime.strptime(date_str, "%d.%m.%Y")
        notify_date = exp_date - timedelta(days=5)
        
        products.append({
            "region": region,
            "name": name,
            "exp": exp_date,
            "notify": notify_date,
            "chat_id": message.chat.id
        })

        await message.answer(
            f"✅ Добавлено!\n"
            f"Продукт: {name}\n"
            f"Регион: {region}\n"
            f"Срок хранения: {exp_date.strftime('%d.%m.%Y')}\n"
            f"🔔 Напомню {notify_date.strftime('%d.%m.%Y')}"
        )
    except Exception as e:
        await message.answer("⚠️ Неверный формат. Пример: /добавить Днепр Моцарелла 28.07.2025")

async def reminder_loop():
    while True:
        now = datetime.now()
        for p in products:
            if p["notify"].date() == now.date():
                await bot.send_message(
                    p["chat_id"],
                    f"📦 Напоминание!\n"
                    f"Пора вернуть продукт **{p['name']}** (регион: {p['region']}) на склад.\n"
                    f"Срок истекает {p['exp'].strftime('%d.%m.%Y')}."
                )
                p["notify"] += timedelta(days=9999)  # больше не напоминать
        await asyncio.sleep(3600)  # Проверять каждый час

async def main():
    asyncio.create_task(reminder_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())