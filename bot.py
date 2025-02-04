from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
import os

TOKEN = os.getenv("BOT_TOKEN")  # Токен бота (добавим в Render)
WEBHOOK_URL = os.getenv("https://botapp-jxld.onrender.com/")  # URL, который выдаст Render

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)

@app.post("/")
async def receive_update(request: Request):
    data = await request.json()
    update = Update(**data)
    await dp.feed_update(bot, update)
    return {"ok": True}

@dp.message()
async def echo_handler(message: types.Message):
    await message.answer(f"Вы сказали: {message.text}")
