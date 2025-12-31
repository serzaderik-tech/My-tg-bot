import asyncio, logging, time, os, json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
from mcrcon import MCRcon

# --- НАСТРОЙКИ (БЕРУТСЯ ИЗ RENDER ENVIRONMENT) ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 5264650563))
RCON_IP = "188.127.241.8"
RCON_PORT = 55664 
RCON_PASS = os.getenv('RCON_PASSWORD')

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
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

# --- СОСТОЯНИЯ ---
class States(StatesGroup):
    wait_helper = State()
    wait_yt = State()
    wait_nick = State()
    wait_pass = State()
    wait_new_pass = State()
    wait_broadcast = State()

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
        logging.error(f"RCON Error: {e}")
        return "ERROR_CONN"

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("👋 Бот сервера **CriaMine** запущен!", reply_markup=get_main_kb(message.from_user.id))

@dp.message(F.text == "3. Правила")
async def rules(m: types.Message): 
    await m.answer("📜 **Правила сервера:**\n1. Не читерить\n2. Не спамить\n3. Уважать игроков.")

@dp.message(F.text == "4. Соц сети")
async def social(m: types.Message): 
    await m.answer("🌐 **Наши соц. сети:**\nВК: vk.com/criamine\nТГ: t.me/criamine")

# --- ЗАЯВКИ (ИСПРАВЛЕНО) ---
@dp.message(F.text == "1. Заявка на хелпера")
async def helper_start(m: types.Message, state: FSMContext):
    await m.answer("✍️ Напишите вашу заявку (возраст, опыт, ник):")
    await state.set_state(States.wait_helper)

@dp.message(States.wait_helper)
async def helper_done(m: types.Message, state: FSMContext):
    await bot.send_message(ADMIN_ID, f"🆕 **Заявка на ХЕЛПЕРА**\nОт: @{m.from_user.username}\nТекст: {m.text}")
    await m.answer("✅ Заявка отправлена!", reply_markup=get_main_kb(m.from_user.id))
    await state.clear()

@dp.message(F.text == "2. Заявка на ютубера")
async def yt_start(m: types.Message, state: FSMContext):
    await m.answer("🎥 Пришлите ссылку на канал и ваш ник:")
    await state.set_state(States.wait_yt)

@dp.message(States.wait_yt)
async def yt_done(m: types.Message, state: FSMContext):
    await bot.send_message(ADMIN_ID, f"🆕 **Заявка на ЮТУБЕРА**\nОт: @{m.from_user.username}\nТекст: {m.text}")
    await m.answer("✅ Заявка на ютубера отправлена!", reply_markup=get_main_kb(m.from_user.id))
    await state.clear()

# --- РАССЫЛКА ---
@dp.message(F.text == "📢 Сообщение")
async def broadcast_start(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    await m.answer("📝 Введите текст для рассылки всем:")
    await state.set_state(States.wait_broadcast)

@dp.message(States.wait_broadcast)
async def broadcast_done(m: types.Message, state: FSMContext):
    db = load_db()
    users = [uid for uid in db.keys() if uid.isdigit()]
    for uid in users:
        try: await bot.send_message(int(uid), f"📢 **Объявление:**\n\n{m.text}")
        except: pass
    await m.answer(f"✅ Отправлено {len(users)} чел.")
    await state.clear()

# --- ПРИВЯЗКА ---
@dp.message(F.text == "5. Привязка")
async def start_bind(m: types.Message, state: FSMContext):
    user_id = str(m.from_user.id)
    db = load_db()
    if user_id in db:
        nick = db[user_id].get("nick")
        await m.answer(f"⚙️ Кабинет игрока: `{nick}`", reply_markup=get_control_kb(), parse_mode="Markdown")
        return
    await m.answer("👤 Введите ваш ник на сервере:")
    await state.set_state(States.wait_nick)

@dp.message(States.wait_nick)
async def proc_nick(m: types.Message, state: FSMContext):
    await state.update_data(nick=m.text)
    await m.answer("🔑 Введите ваш пароль:")
    await state.set_state(States.wait_pass)

@dp.message(States.wait_pass)
async def proc_pass(m: types.Message, state: FSMContext):
    data = await state.get_data()
    nick = data['nick']
    res = run_rcon(f"checkpass {nick} {m.text}")
    
    if "AUTH_SUCCESS" in res:
        user_id = str(m.from_user.id)
        db = load_db()
        # Проверка, получал ли этот НИК кейс (даже с другого ТГ)
        already = any(info.get("nick") == nick and info.get("case_received") for info in db.values() if isinstance(info, dict))
        
        db[user_id] = {"nick": nick, "case_received": already}
        if not already:
            run_rcon(f"dc give {nick} 1")
            run_rcon(f"tgmsg {nick} SUCCESS_CASE")
            db[user_id]["case_received"] = True
            await m.answer("✅ Привязано! Вам выдан кейс.")
        else:
            run_rcon(f"tgmsg {nick} SUCCESS_NO_CASE")
            await m.answer("✅ Привязано! (Кейс уже был выдан ранее)")
        save_db(db)
        await state.clear()
    else:
        await m.answer("❌ Неверный пароль!")
        await state.clear()

# --- CALLBACKS ---
@dp.callback_query(F.data == "kick_me")
async def kick_callback(c: types.CallbackQuery):
    db = load_db()
    nick = db.get(str(c.from_user.id), {}).get("nick")
    if not nick: return
    
    res = run_rcon(f"kick {nick}")
    # Если в ответе от PocketMine есть "Online players" или пустота, значит игрока нет
    if "Online players" in res or res == "" or "ERROR" in res:
        await c.answer("❌ Игрока нет на сервере!", show_alert=True)
    else:
        await c.answer("✅ Вы были кикнуты!", show_alert=True)

@dp.callback_query(F.data == "change_pass")
async def change_pass_btn(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer("📝 Введите новый пароль:")
    await state.set_state(States.wait_new_pass)
    await c.answer()

@dp.message(States.wait_new_pass)
async def proc_new_pass(m: types.Message, state: FSMContext):
    db = load_db()
    nick = db.get(str(m.from_user.id), {}).get("nick")
    if nick:
        run_rcon(f"setpass {nick} {m.text}")
        await m.answer(f"✅ Пароль для `{nick}` изменен!")
    await state.clear()

@dp.callback_query(F.data == "unlink")
async def unlink(c: types.CallbackQuery):
    db = load_db()
    if str(c.from_user.id) in db:
        del db[str(c.from_user.id)]
        save_db(db)
        await c.message.edit_text("❌ Привязка удалена.")
    await c.answer()

# --- WEB SERVER (FIX FOR RENDER) ---
async def handle(request): return web.Response(text="OK")
async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080)))
    await site.start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
    
