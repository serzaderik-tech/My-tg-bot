import asyncio, logging, time, os, json
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

DB_FILE = "users.json"

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
    wait_broadcast = State() # Для рассылки

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
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_control_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="👞 Кикнуть себя", callback_data="kick_me")
    builder.button(text="🔑 Изменить пароль", callback_data="change_pass")
    builder.button(text="❌ Отвязать", callback_data="unlink")
    builder.adjust(2)
    return builder.as_markup()

def run_rcon(command):
    try:
        with MCRcon(RCON_IP, RCON_PASS, port=RCON_PORT) as mcr:
            return mcr.command(command).strip()
    except Exception as e:
        return "ERROR"

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("👋 Бот сервера **CriaMine** запущен!", reply_markup=get_main_kb(message.from_user.id))

@dp.message(F.text == "3. Правила")
async def rules(m: types.Message): await m.answer("📜 Правила сервера...")

@dp.message(F.text == "4. Соц сети")
async def social(m: types.Message): await m.answer("🌐 Наши соц. сети...")

# --- РАССЫЛКА ---
@dp.message(F.text == "📢 Сообщение")
async def broadcast_start(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    await m.answer("📝 Напишите текст сообщения для всех пользователей бота:")
    await state.set_state(States.wait_broadcast)

@dp.message(States.wait_broadcast)
async def broadcast_done(m: types.Message, state: FSMContext):
    db = load_db()
    count = 0
    for uid in db.keys():
        try:
            if uid.isdigit():
                await bot.send_message(int(uid), f"📢 **Объявление от администрации:**\n\n{m.text}", parse_mode="Markdown")
                count += 1
        except: continue
    await m.answer(f"✅ Сообщение отправлено {count} пользователям.")
    await state.clear()

# --- ПРИВЯЗКА И КЕЙС ---
@dp.message(F.text == "5. Привязка")
async def start_bind(m: types.Message, state: FSMContext):
    user_id = str(m.from_user.id)
    db = load_db()
    if user_id in db:
        nick = db[user_id].get("nick")
        await m.answer(f"⚙️ Кабинет: `{nick}`", reply_markup=get_control_kb(), parse_mode="Markdown")
        return
    await m.answer("👤 Введите ваш ник:")
    await state.set_state(States.wait_nick)

@dp.message(States.wait_nick)
async def proc_nick(m: types.Message, state: FSMContext):
    await state.update_data(nick=m.text)
    await m.answer("🔑 Введите пароль:")
    await state.set_state(States.wait_pass)

@dp.message(States.wait_pass)
async def proc_pass(m: types.Message, state: FSMContext):
    data = await state.get_data()
    nick = data['nick']
    res = run_rcon(f"checkpass {nick} {m.text}")
    
    if "AUTH_SUCCESS" in res:
        user_id = str(m.from_user.id)
        db = load_db()
        
        # Проверка на повторный кейс
        already_got_case = False
        for info in db.values():
            if isinstance(info, dict) and info.get("nick") == nick and info.get("case_received"):
                already_got_case = True
        
        db[user_id] = {"nick": nick, "case_received": already_got_case}
        
        if not already_got_case:
            run_rcon(f"dc give {nick} 1")
            run_rcon(f"tgmsg {nick} SUCCESS_CASE") # Специальная команда для уведомления в игре
            db[user_id]["case_received"] = True
            await m.answer(f"✅ Привязано! Вам выдан кейс на сервере.")
        else:
            await m.answer(f"✅ Привязано! (Кейс уже выдавался ранее)")
            run_rcon(f"tgmsg {nick} SUCCESS_NO_CASE")

        save_db(db)
        await state.clear()
    else:
        await m.answer("❌ Ошибка авторизации.")
        await state.clear()

# --- ОСТАЛЬНАЯ ЛОГИКА (KICK, CHANGE PASS И Т.Д.) ---
# ... (оставь из предыдущего кода callbacks для kick_me, change_pass, unlink) ...

async def main():
    # Запуск веб-сервера и бота
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
