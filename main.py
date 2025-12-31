import asyncio, logging, time, os, json, sys, re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
import socket

# Защита от двойного запуска
LOCK_FILE = "bot.lock"

def check_single_instance():
    if os.path.exists(LOCK_FILE):
        print("❌ ОШИБКА: Бот уже запущен!")
        print("Если вы уверены что бот не запущен, удалите файл bot.lock")
        sys.exit(1)
    
    # Создаем lock файл
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))
    print("✅ Блокировка установлена")

def remove_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
        print("✅ Блокировка снята")

# Проверяем перед запуском
check_single_instance()

# --- КОНФИГ ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 5264650563))
RCON_IP = "188.127.241.8"
RCON_PORT = 55664 
RCON_PASS = os.getenv('RCON_PASSWORD')

# Проверяем наличие обязательных переменных
if not API_TOKEN:
    print("❌ ОШИБКА: Не установлен BOT_TOKEN")
    sys.exit(1)

if not RCON_PASS:
    print("⚠️  ВНИМАНИЕ: Не установлен RCON_PASSWORD")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

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
    wait_console = State()

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

def get_cancel_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Отменить")
    return builder.as_markup(resize_keyboard=True)

def get_back_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="🔙 Вернуться")
    return builder.as_markup(resize_keyboard=True)

def get_control_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="👞 Кикнуть себя", callback_data="kick_me")
    builder.button(text="🔑 Изменить пароль", callback_data="change_pass")
    builder.button(text="❌ Отвязать", callback_data="unlink")
    builder.adjust(2)
    return builder.as_markup()

# RCON клиент для Minecraft Bedrock Edition (PE)
class BedrockRCON:
    def __init__(self, host, port, password):
        self.host = host
        self.port = port
        self.password = password
        self.sock = None
    
    def connect_and_send(self, command):
        try:
            # Проверяем пароль
            if not self.password:
                logging.error("RCON пароль не установлен!")
                return "ERROR: RCON password not set"
            
            logging.info(f"Подключение к Bedrock RCON: {self.host}:{self.port}")
            
            # Создаем новое соединение для каждой команды
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)  # Увеличиваем таймаут
            
            # Пробуем подключиться
            self.sock.connect((self.host, self.port))
            logging.info("TCP соединение установлено")
            
            # Для Bedrock сначала читаем приветствие (если есть)
            time.sleep(0.1)
            
            # Отправляем пароль с нулевым байтом
            password_packet = self.password.encode('utf-8') + b'\x00'
            self.sock.send(password_packet)
            logging.info("Пароль отправлен")
            
            # Ждем ответа на пароль
            time.sleep(0.2)
            
            # Отправляем команду с нулевым байтом в конце
            command_packet = command.encode('utf-8') + b'\x00'
            self.sock.send(command_packet)
            logging.info(f"Команда отправлена: {command}")
            
            # Читаем ответ
            self.sock.settimeout(3)
            response = b""
            
            try:
                while True:
                    chunk = self.sock.recv(4096)
                    if not chunk:
                        break
                    response += chunk
                    # В Bedrock ответ обычно приходит одним пакетом
                    if len(chunk) < 4096:
                        break
            except socket.timeout:
                # Таймаут - возможно ответ закончился
                pass
            
            # Преобразуем в строку, удаляя нулевые байты
            result = response.decode('utf-8', errors='ignore').replace('\x00', '').strip()
            
            # Очищаем от возможных ANSI кодов
            result = re.sub(r'\x1b\[[0-9;]*[mK]', '', result)
            
            logging.info(f"Результат ({len(result)} символов): {result[:200]}")
            
            return result if result else "Пустой ответ"
            
        except socket.timeout:
            logging.error("Таймаут при подключении")
            return "ERROR_TIMEOUT"
        except ConnectionRefusedError:
            logging.error("Соединение отклонено")
            return "ERROR_CONN"
        except Exception as e:
            logging.error(f"Bedrock RCON error: {str(e)}")
            return f"ERROR: {str(e)}"
        finally:
            if self.sock:
                try:
                    self.sock.close()
                    logging.debug("Соединение закрыто")
                except:
                    pass
                self.sock = None

def run_rcon(command):
    try:
        if not RCON_PASS:
            return "ERROR: RCON password not configured"
        
        rcon = BedrockRCON(RCON_IP, RCON_PORT, RCON_PASS)
        result = rcon.connect_and_send(command)
        
        if "ERROR_CONN" in result:
            return "❌ Ошибка подключения к RCON серверу"
        elif "ERROR_TIMEOUT" in result:
            return "⏱️ Таймаут подключения к серверу"
        elif "ERROR:" in result:
            return result
        
        return result if result else "✅ Команда выполнена"
    except Exception as e:
        logging.error(f"RCON Error: {e}")
        return f"❌ Ошибка: {str(e)}"

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer("👋 Добро пожаловать!", reply_markup=get_main_kb(m.from_user.id))

# Команда для теста RCON (только админ)
@dp.message(Command("testrcon"))
async def test_rcon(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        return
    
    await m.answer("🔄 Тестирую RCON подключение...")
    
    if not RCON_PASS:
        await m.answer("❌ RCON_PASSWORD не установлен в переменных окружения!")
        return
    
    # Тест 1: Простая команда
    await m.answer("📡 Тест 1: Команда 'list'...")
    result1 = run_rcon("list")
    await m.answer(f"Результат: {result1[:500]}")
    
    await asyncio.sleep(1)
    
    # Тест 2: Say команда
    await m.answer("📡 Тест 2: Команда 'say Тест'...")
    result2 = run_rcon("say Тест из Telegram")
    await m.answer(f"Результат: {result2[:500]}")
    
    # Показываем настройки
    await m.answer(
        f"🔧 RCON настройки:\n"
        f"IP: {RCON_IP}\n"
        f"Port: {RCON_PORT}\n"
        f"Pass: {'✅ установлен' if RCON_PASS else '❌ НЕ установлен'}"
    )

# Команда для проверки RCON (только админ)
@dp.message(Command("checkrcon"))
async def check_rcon(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        return
    
    await m.answer("🔍 Проверяю RCON подключение...")
    
    if not RCON_PASS:
        await m.answer("❌ RCON_PASSWORD не установлен!")
        return
    
    # Простая тестовая команда
    test_commands = [
        "list",  # Список игроков
        "help",  # Помощь
        "time query daytime",  # Проверка времени
    ]
    
    for cmd in test_commands:
        await m.answer(f"🔄 Выполняю: `{cmd}`...", parse_mode="Markdown")
        result = run_rcon(cmd)
        
        # Определяем статус
        if "ERROR" in result or "Ошибка" in result:
            status = "❌"
        else:
            status = "✅"
        
        await m.answer(f"{status} `{cmd}`:\n```\n{result[:1000]}\n```", parse_mode="Markdown")
        await asyncio.sleep(1)

# Заявки
@dp.message(F.text == "1. Заявка на хелпера")
async def h_start(m: types.Message, state: FSMContext):
    await m.answer("✍️ Напишите вашу заявку:", reply_markup=get_cancel_kb())
    await state.set_state(States.wait_helper)

@dp.message(States.wait_helper)
async def h_done(m: types.Message, state: FSMContext):
    if m.text == "❌ Отменить":
        await m.answer("❌ Отменено", reply_markup=get_main_kb(m.from_user.id))
        await state.clear()
        return
    
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
    await m.answer("🎥 Укажите ссылку на канал и ник:", reply_markup=get_cancel_kb())
    await state.set_state(States.wait_yt)

@dp.message(States.wait_yt)
async def y_done(m: types.Message, state: FSMContext):
    if m.text == "❌ Отменить":
        await m.answer("❌ Отменено", reply_markup=get_main_kb(m.from_user.id))
        await state.clear()
        return
    
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
    
    if not RCON_PASS:
        await m.answer("❌ Система привязки временно недоступна (RCON не настроен)")
        await state.clear()
        return
    
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
    if not RCON_PASS:
        await c.answer("❌ Система временно недоступна", show_alert=True)
        return
    
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
    if not RCON_PASS:
        await c.answer("❌ Система временно недоступна", show_alert=True)
        return
    
    await c.message.answer("📝 Введите новый пароль:")
    await state.set_state(States.wait_new_pass)
    await c.answer()

@dp.message(States.wait_new_pass)
async def proc_new_p(m: types.Message, state: FSMContext):
    if not RCON_PASS:
        await m.answer("❌ Система временно недоступна")
        await state.clear()
        return
    
    db = load_db()
    nick = db.get(str(m.from_user.id), {}).get("nick")
    if nick:
        result = run_rcon(f"setpass {nick} {m.text}")
        await m.answer(f"✅ Пароль для `{nick}` изменен!\nРезультат: {result}", parse_mode="Markdown")
    else:
        await m.answer("❌ Аккаунт не привязан")
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

# Консоль
@dp.message(F.text == "⚙️ Консоль")
async def console_start(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    
    if not RCON_PASS:
        await m.answer("❌ RCON не настроен. Установите переменную окружения RCON_PASSWORD")
        return
    
    # Скрываем все кнопки - отправляем сообщение с кнопкой "Вернуться"
    await m.answer(
        "⚙️ Режим консоли\n"
        "Отправьте команду для выполнения на сервере\n"
        "Для выхода нажмите кнопку ниже",
        reply_markup=get_back_kb()  # Только кнопка "Вернуться"
    )
    await state.set_state(States.wait_console)

@dp.message(States.wait_console)
async def console_command(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        await state.clear()
        return
    
    # Если нажата кнопка "Вернуться"
    if m.text == "🔙 Вернуться":
        await m.answer("✅ Выход из режима консоли", reply_markup=get_main_kb(m.from_user.id))
        await state.clear()
        return
    
    # Отправляем команду на сервер
    await m.answer(f"🔄 Выполняю: `{m.text}`", parse_mode="Markdown")
    
    result = run_rcon(m.text)
    
    # Обрезаем слишком длинные ответы
    if len(result) > 4000:
        result = result[:4000] + "\n\n... (сообщение обрезано)"
    
    await m.answer(f"📋 Результат:\n```\n{result}\n```", parse_mode="Markdown")

# Команда /console для удобства
@dp.message(Command("console"))
async def cmd_console(m: types.Message, state: FSMContext):
    await console_start(m, state)

# Веб-сервер для хостингов (Heroku, Railway и т.д.)
async def handle(request): 
    return web.Response(text="OK")

async def main():
    # Проверяем наличие токена
    if not API_TOKEN:
        print("❌ ОШИБКА: BOT_TOKEN не установлен!")
        print("Установите переменную окружения BOT_TOKEN")
        remove_lock()
        sys.exit(1)
    
    print(f"✅ Бот запускается...")
    print(f"🤖 ID администратора: {ADMIN_ID}")
    print(f"🎮 RCON: {RCON_IP}:{RCON_PORT}")
    print(f"🔑 RCON пароль: {'✅ установлен' if RCON_PASS else '❌ НЕ установлен'}")
    
    # Удаляем webhook и сбрасываем все обновления
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("Webhook удален, бот запускается...")
    except Exception as e:
        logging.error(f"Ошибка при удалении webhook: {e}")
    
    # Запускаем веб-сервер для хостингов
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 8080))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    logging.info(f"Веб-сервер запущен на по
