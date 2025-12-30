import asyncio
import logging
import time
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiohttp import web

# --- НАСТРОЙКИ (Берем из настроек Render) ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 5264650563)) 

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# --- ХРАНИЛИЩЕ ЛИМИТОВ ---
user_limits = {}

def get_main_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="1. Заявка на хелпера")
    builder.button(text="2. Заявка на ютубера")
    builder.button(text="3. Правила")
    builder.button(text="4. Соц сети")
    builder.button(text="5. Привязка")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_cancel_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="Отменить")
    return builder.as_markup(resize_keyboard=True)

def is_limit_exceeded(user_id, z_type):
    current_time = time.time()
    limit = 15 if z_type == "helper" else 20
    cooldown = 2 * 3600 
    if user_id not in user_limits:
        user_limits[user_id] = {'count': 1, 'first_msg_time': current_time}
        return False
    data = user_limits[user_id]
    if current_time - data['first_msg_time'] > cooldown:
        user_limits[user_id] = {'count': 1, 'first_msg_time': current_time}
        return False
    if data['count'] >= limit: return True
    user_limits[user_id]['count'] += 1
    return False

# --- ОБРАБОТЧИКИ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("👋 Бот запущен! Выберите раздел:", reply_markup=get_main_kb())

@dp.message(F.text == "Отменить")
async def cmd_cancel(message: types.Message):
    await message.answer("Возвращаю в меню.", reply_markup=get_main_kb())

@dp.message(F.chat.type == "private")
async def handle_private(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        if message.reply_to_message:
            target_id = None
            if message.reply_to_message.text and "ID:" in message.reply_to_message.text:
                try: 
                    target_id = int(message.reply_to_message.text.split("ID: ")[1].split("\n")[0].strip())
                except: pass
            if target_id:
                try:
                    await bot.copy_message(chat_id=target_id, from_chat_id=ADMIN_ID, message_id=message.message_id)
                    await message.answer("✅ Ответ отправлен.")
                except: pass
        return

    if message.text in ["1. Заявка на хелпера", "2. Заявка на ютубера"]:
        await message.answer(f"Напишите вашу анкету на {message.text}.", reply_markup=get_cancel_kb())
        return

    z_type = "yt" if "ютуб" in str(message.text).lower() else "helper"
    if is_limit_exceeded(message.from_user.id, z_type):
        await message.answer("⚠️ Лимит! Ждите 2 часа.")
        return

    await bot.send_message(ADMIN_ID, f"📑 **Новая заявка!**\nОт: {message.from_user.full_name}\nID: {message.from_user.id}")
    await bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    await message.answer("✅ Доставлено!", reply_markup=get_main_kb())

# --- ВЕБ-СЕРВЕР ---
async def handle_web(request):
    return web.Response(text="Бот работает!")

async def start_web():
    app = web.Application()
    app.router.add_get("/", handle_web)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    await start_web() 
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())