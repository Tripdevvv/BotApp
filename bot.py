import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

regions = {
    "dnipro": "Днепр",
    "kyiv": "Киев",
    "lviv": "Львов"
}

@dp.message(CommandStart())
async def start(message: Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=code)]
            for code, name in regions.items()
        ]
    )
    await message.answer("Выбери свой регион:", reply_markup=keyboard)

@dp.callback_query()
async def handle_region(callback: types.CallbackQuery):
    code = callback.data
    name = regions.get(code, "Неизвестно")
    await callback.message.answer(f"✅ Ты выбрал регион: {name}")
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())