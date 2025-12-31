import asyncio, logging, time, os, json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
from mcrcon import MCRcon

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
    except: return "ERROR_CONN"

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer("👋 Добро пожаловать!", reply_markup=get_main_kb(m.from_user.id))

# Заявки
@dp.message(F.text == "1. Заявка на хелпера")
async def h_start(m: types.Message, state: FSMContext):
    await m.answer("✍️ Напишите вашу заявку:")
    await state.set_state(States.wait_helper)

@dp.message(States.wait_helper)
async def h_done(m: types.Message, state: FSMContext):
    username = m.from_user.username if m.from_user.username else "без_username"
    user_id = m.from_user.id
    
    # Отправляем заявку админу с указанием ID пользователя в тексте
    msg_text = f"🆕 ЗАЯВКА НА ХЕЛПЕРА\n\n"
    msg_text += f"От: @{username}\n"
    msg_text += f"ID: {user_id}\n\n"
    msg_text += f"Текст заявки:\n{m.text}\n\n"
    msg_text += f"#user_{user_id}"  # Хештег для идентификации
    
    await bot.send_message(ADMIN_ID, msg_text)
    await m.answer("✅ Заявка отправлена!", reply_markup=get_main_kb(m.from_user.id))
    await state.clear()

@dp.message(F.text == "2. Заявка на ютубера")
async def y_start(m: types.Message, state: FSMContext):
    await m.answer("🎥 Укажите ссылку на канал и ник:")
    await state.set_state(States.wait_yt)

@dp.message(States.wait_yt)
async def y_done(m: types.Message, state: FSMContext):
    username = m.from_user.username if m.from_user.username else "без_username"
    user_id = m.from_user.id
    
    # Отправляем заявку админу с указанием ID пользователя в тексте
    msg_text = f"🆕 ЗАЯВКА НА ЮТУБЕРА\n\n"
    msg_text += f"От: @{username}\n"
    msg_text += f"ID: {user_id}\n\n"
    msg_text += f"Текст заявки:\n{m.text}\n\n"
    msg_text += f"#user_{user_id}"  # Хештег для идентификации
    
    await bot.send_message(ADMIN_ID, msg_text)
    await m.answer("✅ Заявка отправлена!", reply_markup=get_main_kb(m.from_user.id))
    await state.clear()

# ОБРАБОТЧИК ОТВЕТОВ АДМИНА НА ЗАЯВКИ
@dp.message(F.reply_to_message, F.from_user.id == ADMIN_ID)
async def admin_reply(m: types.Message):
    # Проверяем что это ответ на сообщение от бота
    if m.reply_to_message.from_user.id != bot.id:
        return
    
    # Извлекаем ID пользователя из текста заявки
    original_text = m.reply_to_message.text
    
    try:
        # Ищем хештег с ID пользователя
        if "#user_" in original_text:
            user_id_str = original_text.split("#user_")[1].strip()
            user_id = int(user_id_str)
            
            # Отправляем ответ пользователю
            response_text = f"📬 Ответ администрации:\n\n{m.text}"
            await bot.send_message(user_id, response_text)
            
            # Подтверждение админу
            await m.reply("✅ Ответ отправлен пользователю!")
        else:
            await m.reply("❌ Не удалось определить ID пользователя")
    except Exception as e:
        await m.reply(f"❌ Ошибка отправки: {e}")
        logging.error(f"Ошибка при ответе на заявку: {e}")

# Правила и соц сети
@dp.message(F.text == "3. Правила")
async def rules(m: types.Message):
    await m.answer("📜 Правила сервера:\n1. Не читерить\n2. Уважать игроков\n3. Не спамить")

@dp.message(F.text == "4. Соц сети")
async def socials(m: types.Message):
    await m.answer("📱 Наши соц. сети:\nYouTube: ...\nDiscord: ...")

# Привязка
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
    
    for user_id, info in db.items():
        if info.get("nick", "").lower() == nick_input.lower():
            await m.answer("❌ Этот аккаунт уже привязан к другому Telegram!")
            await state.clear()
            return

    await state.update_data(nick=nick_input)
    await m.answer("🔑 Введите пароль от аккаунта:")
    await state.set_state(States.wait_pass)

@dp.message(States.wait_pass)
async def bind_pass(m: types.Message, state: FSMContext):
    data = await state.get_data()
    nick = data['nick']
    res = run_rcon(f"checkpass {nick} {m.text}")

    if "AUTH_SUCCESS" in res:
        db = load_db()
        case_already = any(i.get("nick") == nick and i.get("case_received") for i in db.values())
        
        db[str(m.from_user.id)] = {"nick": nick, "case_received": case_already}
        
        if not case_already:
            run_rcon(f"dc give {nick} 1")
            run_rcon(f"tgmsg {nick} SUCCESS_CASE")
            db[str(m.from_user.id)]["case_received"] = True
            await m.answer(f"✅ Успешно! Аккаунт `{nick}` привязан. Вам выдан кейс!", parse_mode="Markdown")
        else:
            run_rcon(f"tgmsg {nick} SUCCESS_NO_CASE")
            await m.answer(f"✅ Успешно! Аккаунт `{nick}` привязан. (Кейс уже выдавался)", parse_mode="Markdown")
        
        save_db(db)
        await state.clear()
    else:
        await m.answer("❌ Неверный пароль!")
        await state.clear()

# Кнопки управления
@dp.callback_query(F.data == "kick_me")
async def kick_c(c: types.CallbackQuery):
    db = load_db()
    nick = db.get(str(c.from_user.id), {}).get("nick")
    if nick:
        res = run_rcon(f"kick {nick}")
        if "Online players" in res or res == "" or "ERROR" in res:
            await c.answer("❌ Вас нет на сервере!", show_alert=True)
        else:
            await c.answer("✅ Кикнут!", show_alert=True)
    else:
        await c.answer("❌ Аккаунт не привязан!", show_alert=True)

@dp.callback_query(F.data == "change_pass")
async def ch_pass_c(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer("📝 Введите новый пароль:")
    await state.set_state(States.wait_new_pass)
    await c.answer()

@dp.message(States.wait_new_pass)
async def proc_new_p(m: types.Message, state: FSMContext):
    db = load_db()
    nick = db.get(str(m.from_user.id), {}).get("nick")
    if nick:
        run_rcon(f"setpass {nick} {m.text}")
        await m.answer(f"✅ Пароль для `{nick}` изменен!", parse_mode="Markdown")
    await state.clear()

@dp.callback_query(F.data == "unlink")
async def unl_c(c: types.CallbackQuery):
    db = load_db()
    if str(c.from_user.id) in db:
        del db[str(c.from_user.id)]
        save_db(db)
        await c.message.edit_text("❌ Привязка удалена.")
    await c.answer()

# Рассылка
@dp.message(F.text == "📢 Сообщение")
async def br_start(m: types.Message, state: FSMContext):
    if m.from_user.id == ADMIN_ID:
        await m.answer("Введите текст рассылки:")
        await state.set_state(States.wait_broadcast)

@dp.message(States.wait_broadcast)
async def br_done(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        await state.clear()
        return
    
    db = load_db()
    success_count = 0
    fail_count = 0
    
    for uid in db.keys():
        try:
            await bot.send_message(int(uid), f"📢 Объявление:\n\n{m.text}")
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            fail_count += 1
            logging.warning(f"Не удалось отправить {uid}: {e}")
    
    await m.answer(f"✅ Рассылка завершена!\n✅ Отправлено: {success_count}\n❌ Не удалось: {fail_count}")
    await state.clear()

async def handle(request): 
    return web.Response(text="OK")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080))).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
