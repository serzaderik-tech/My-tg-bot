import asyncio
import logging
import time
import os
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiohttp import web
from mcrcon import MCRcon

# --- НАСТРОЙКИ ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 5264650563))
RCON_IP = "188.127.241.8"
RCON_PORT = 55664 
RCON_PASS = os.getenv('RCON_PASSWORD')

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# --- БАЗА ДАННЫХ (ФАЙЛ) ---
DB_FILE = "users.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_db(db):
    with open(DB_FILE, "w") as f: json.dump(db, f)

# --- СОСТОЯНИЯ (FSM) ---
class Form(StatesGroup):
    waiting_for_helper_text = State()
    waiting_for_yt_text = State()

class BindState(StatesGroup):
    waiting_for_nickname = State()
    waiting_for_password = State()
    waiting_for_new_pass = State()

block_list = {}

# --- ТЕКСТЫ ---
RULES_TEXT = (
    "📜 **ПРАВИЛА СЕРВЕРА CRIAMINE**\n\n"
    "1.1. Запрещено использование читов (Ban 30d).\n"
    "1.2. Запрещен мат и оскорбления в чате (Mute 60m).\n"
    "1.3. Запрещена реклама сторонних ресурсов (Ban Permanent).\n"
    "1.4. Запрещен грифинг спавна и системных построек.\n\n"
    "Полный список правил доступен на сайте или в обсуждениях."
)

SOCIAL_TEXT = (
    "🌐 **НАШИ СОЦ. СЕТИ**\n\n"
    "🔹 Группа ВК: vk.com/criamine\n"
    "🔹 Discord: discord.gg/criamine\n"
    "🔹 Telegram: t.me/criamine_channel\n"
    "🔹 Сайт: www.criamine.ru"
)

# --- КЛАВИАТУРЫ ---
def get_main_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="1. Заявка на хелпера")
    builder.button(text="2. Заявка на ютубера")
    builder.button(text="3. Правила")
    builder.button(text="4. Соц сети")
    builder.button(text="5. Привязка")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_control_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="👞 Кикнуть себя", callback_data="kick_me")
    builder.button(text="🔑 Изменить пароль", callback_data="change_pass")
    builder.button(text="❌ Отвязать", callback_data="unlink")
    builder.adjust(2)
    return builder.as_markup()

# --- ФУНКЦИЯ RCON ---
def run_rcon(command):
    try:
        with MCRcon(RCON_IP, RCON_PASS, port=RCON_PORT) as mcr:
            return mcr.command(command).strip()
    except Exception as e:
        logging.error(f"RCON Error: {e}")
        return "CONNECTION_ERROR"

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("👋 Добро пожаловать в бот сервера **CriaMine**!", reply_markup=get_main_kb())

# 3. Правила
@dp.message(F.text == "3. Правила")
async def show_rules(message: types.Message):
    await message.answer(RULES_TEXT, parse_mode="Markdown")

# 4. Соц сети
@dp.message(F.text == "4. Соц сети")
async def show_social(message: types.Message):
    await message.answer(SOCIAL_TEXT, parse_mode="Markdown")

# 1. Заявка на хелпера
@dp.message(F.text == "1. Заявка на хелпера")
async def helper_start(message: types.Message, state: FSMContext):
    await message.answer("✍️ Опишите ваш опыт и почему мы должны взять именно вас:")
    await state.set_state(Form.waiting_for_helper_text)

@dp.message(Form.waiting_for_helper_text)
async def helper_done(message: types.Message, state: FSMContext):
    await bot.send_message(ADMIN_ID, f"🆕 **Заявка на ХЕЛПЕРА**\nОт: @{message.from_user.username}\nТекст: {message.text}")
    await message.answer("✅ Заявка отправлена администрации!", reply_markup=get_main_kb())
    await state.clear()

# 2. Заявка на ютубера
@dp.message(F.text == "2. Заявка на ютубера")
async def yt_start(message: types.Message, state: FSMContext):
    await message.answer("🎥 Ссылку на ваш канал и количество подписчиков:")
    await state.set_state(Form.waiting_for_yt_text)

@dp.message(Form.waiting_for_yt_text)
async def yt_done(message: types.Message, state: FSMContext):
    await bot.send_message(ADMIN_ID, f"🆕 **Заявка на ЮТУБЕРА**\nОт: @{message.from_user.username}\nТекст: {message.text}")
    await message.answer("✅ Заявка отправлена!", reply_markup=get_main_kb())
    await state.clear()

# 5. Привязка и управление
@dp.message(F.text == "5. Привязка")
async def start_bind(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    db = load_db()

    if user_id in db:
        nickname = db[user_id]
        await message.answer(f"⚙️ **Личный кабинет: {nickname}**", reply_markup=get_control_kb())
        return

    if user_id in block_list and time.time() < block_list[user_id]:
        await message.answer(f"⚠️ Попробуйте позже.")
        return

    await message.answer("👤 Введите ваш ник на сервере:")
    await state.set_state(BindState.waiting_for_nickname)

# --- ЛОГИКА ИНЛАЙН КНОПОК ---

@dp.callback_query(F.data == "kick_me")
async def kick_callback(callback: types.CallbackQuery):
    db = load_db()
    nickname = db.get(str(callback.from_user.id))
    if nickname:
        run_rcon(f"kick {nickname} §bКикнут через Telegram")
        await callback.answer("✅ Вы кикнуты с сервера!", show_alert=True)
    else:
        await callback.answer("Ошибка привязки")

@dp.callback_query(F.data == "change_pass")
async def change_pass_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📝 Введите НОВЫЙ пароль:")
    await state.set_state(BindState.waiting_for_new_pass)
    await callback.answer()

@dp.callback_query(F.data == "unlink")
async def unlink_callback(callback: types.CallbackQuery):
    db = load_db()
    user_id = str(callback.from_user.id)
    if user_id in db:
        del db[user_id]
        save_db(db)
        await callback.message.edit_text("✅ Привязка удалена.")
    await callback.answer()

# --- ПРОЦЕССЫ ПРИВЯЗКИ ---

@dp.message(BindState.waiting_for_nickname)
async def process_nickname(message: types.Message, state: FSMContext):
    await state.update_data(nickname=message.text)
    await message.answer("🔑 Введите ТЕКУЩИЙ пароль от сервера:")
    await state.set_state(BindState.waiting_for_password)

@dp.message(BindState.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    nickname = user_data['nickname']
    password = message.text
    user_id = str(message.from_user.id)

    res = run_rcon(f"checkpass {nickname} {password}")

    if "AUTH_SUCCESS" in res:
        db = load_db()
        db[user_id] = nickname
        save_db(db)
        await message.answer(f"✅ Аккаунт **{nickname}** привязан!", reply_markup=get_main_kb(), parse_mode="Markdown")
        await state.clear()
    else:
        block_list[user_id] = time.time() + 300
        await message.answer("❌ Пароль неверен. Блок на 5 минут.")
        await state.clear()

@dp.message(BindState.waiting_for_new_pass)
async def process_new_password(message: types.Message, state: FSMContext):
    new_password = message.text
    db = load_db()
    nickname = db.get(str(message.from_user.id))

    if nickname:
        res = run_rcon(f"setpass {nickname} {new_password}")
        if "PASS_CHANGED" in res:
            await message.answer(f"✅ Пароль для **{nickname}** изменен!")
        else:
            await message.answer("❌ Ошибка сервера.")
    await state.clear()

# --- ВЕБ-СЕРВЕР ---
async def handle_web(request): return web.Response(text="Bot is running")
async def start_web():
    app = web.Application()
    app.router.add_get("/", handle_web)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000)))
    await site.start()

async def main():
    await start_web()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
