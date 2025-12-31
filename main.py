import asyncio, logging, time, os, json, sys, re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
from mcrcon import MCRcon # Используем готовую библиотеку

# --- КОНФИГ ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 5264650563))
RCON_IP = "188.127.241.8"
RCON_PORT = 55664 
RCON_PASS = os.getenv('RCON_PASSWORD')

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

DB_FILE = "users.json"

# --- ФУНКЦИИ БАЗЫ ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_db(db):
    with open(DB_FILE, "w") as f: json.dump(db, f)

class States(StatesGroup):
    wait_helper = State()
    wait_yt = State()
    wait_nick = State()
    wait_pass = State()
    wait_new_pass = State()
    wait_broadcast = State()
    wait_console = State()

# --- КЛАВИАТУРЫ ---
def get_main_kb(user_id):
    builder = ReplyKeyboardBuilder()
    builder.button(text="1. Заявка на хелпера")
    builder.button(text="2. Заявка на ютубера")
    builder.button(text="3. Правила")
    builder.button(text="4. Соц сети")
    builder.button(text="5. Привязка")
    if user_id == ADMIN_ID:
        builder.button(text="📢 Сообщение")
        builder.button(text="⚙️ Консоль")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_control_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="👞 Кикнуть себя", callback_data="kick_me")
    builder.button(text="🔑 Изменить пароль", callback_data="change_pass")
    builder.button(text="❌ Отвязать", callback_data="unlink")
    builder.adjust(2)
    return builder.as_markup()

# --- ИСПРАВЛЕННЫЙ RCON ---
def run_rcon(command):
    if not RCON_PASS:
        return "❌ Ошибка: Пароль RCON не задан в переменных!"
    try:
        # Библиотека mcrcon автоматически обрабатывает протокол PocketMine/Bedrock
        with MCRcon(RCON_IP, RCON_PASS, port=RCON_PORT, timeout=5) as mcr:
            response = mcr.command(command)
            # Очистка от цветовых кодов параграфа (§) и ANSI
            clean_response = re.sub(r'§[0-9a-fk-orx]', '', response)
            clean_response = re.sub(r'\x1b\[[0-9;]*[mK]', '', clean_response)
            return clean_response if clean_response else "✅ Команда выполнена (пустой ответ)"
    except Exception as e:
        logging.error(f"RCON Error: {e}")
        return f"❌ Ошибка подключения: {str(e)}"

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer("👋 Добро пожаловать!", reply_markup=get_main_kb(m.from_user.id))

# Привязка с защитой от дублей
@dp.message(F.text == "5. Привязка")
async def bind_start(m: types.Message, state: FSMContext):
    db = load_db()
    uid = str(m.from_user.id)
    if uid in db:
        nick = db[uid].get("nick")
        await m.answer(f"⚙️ Ваш аккаунт: `{nick}`", reply_markup=get_control_kb(), parse_mode="Markdown")
        return
    await m.answer("👤 Введите ваш ник на сервере:")
    await state.set_state(States.wait_nick)

@dp.message(States.wait_nick)
async def bind_nick(m: types.Message, state: FSMContext):
    nick_input = m.text.strip()
    db = load_db()
    
    # Проверка: не привязан ли этот ник уже кем-то другим
    for user_id, info in db.items():
        if info.get("nick", "").lower() == nick_input.lower():
            await m.answer("❌ Этот ник уже привязан к другому пользователю!")
            await state.clear()
            return

    await state.update_data(nick=nick_input)
    await m.answer(f"🔑 Введите пароль от аккаунта `{nick_input}`:")
    await state.set_state(States.wait_pass)

@dp.message(States.wait_pass)
async def bind_pass(m: types.Message, state: FSMContext):
    data = await state.get_data()
    nick = data['nick']
    
    await m.answer("⏳ Проверяю...")
    res = run_rcon(f"checkpass {nick} {m.text}")

    if "AUTH_SUCCESS" in res:
        db = load_db()
        # Проверка на кейс (один раз на ник)
        case_already = any(i.get("nick").lower() == nick.lower() and i.get("case_received") for i in db.values())
        
        db[str(m.from_user.id)] = {"nick": nick, "case_received": case_already}
        
        if not case_already:
            run_rcon(f"dc give {nick} 1")
            run_rcon(f"tgmsg {nick} SUCCESS_CASE")
            db[str(m.from_user.id)]["case_received"] = True
            await m.answer(f"✅ Привязано! Вам выдан кейс.", reply_markup=get_main_kb(m.from_user.id))
        else:
            run_rcon(f"tgmsg {nick} SUCCESS_NO_CASE")
            await m.answer(f"✅ Привязано! (Кейс уже выдавался ранее)", reply_markup=get_main_kb(m.from_user.id))
        
        save_db(db)
        await state.clear()
    else:
        await m.answer("❌ Ошибка: Неверный пароль или игрок не найден.")
        await state.clear()

# Консоль для админа
@dp.message(F.text == "⚙️ Консоль")
async def console_start(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    await m.answer("💻 Режим консоли. Отправьте любую команду (или 'выход'):")
    await state.set_state(States.wait_console)

@dp.message(States.wait_console)
async def console_run(m: types.Message, state: FSMContext):
    if m.text.lower() == "выход":
        await m.answer("✅ Выход", reply_markup=get_main_kb(m.from_user.id))
        await state.clear()
        return
    
    res = run_rcon(m.text)
    await m.answer(f"📋 Ответ:\n```\n{res[:1000]}\n```", parse_mode="Markdown")

# --- СТАНДАРТНЫЙ ЗАПУСК ---
async def handle(request): return web.Response(text="OK")

async def main():
    # Веб-сервер для Render
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080))).start()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
    

