import asyncio, os, json, threading, logging
from flask import Flask
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile
from telethon import TelegramClient

# --- Конфигурация ---
BOT_TOKEN = "8996968114:AAGr9djQk1eRc73mgy_iUdO18433T4d6otU"
API_ID = 20468631
API_HASH = "a1969eb057b96fc4104918e44d3df6fb"
TARGET_CHANNEL = "prufscamm"
ADMIN_ID = 7832453655
DB_FILE = "stats.json"

# --- Состояния ---
class AdminState(StatesGroup):
    waiting_for_target = State()
    waiting_for_action = State()
    waiting_for_value = State()

# --- База данных ---
if os.path.exists(DB_FILE):
    with open(DB_FILE, "r") as f: STATS_DB = json.load(f)
else: STATS_DB = {}

def save_db():
    with open(DB_FILE, "w") as f: json.dump(STATS_DB, f)

def normalize(key): return str(key).lower().replace("@", "")

# --- Flask ---
app = Flask(__name__)
@app.route('/')
def home(): return "Бот активен!"
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- Инициализация ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = TelegramClient("bot_user", API_ID, API_HASH)

def get_kb(key):
    key = normalize(key)
    stats = STATS_DB.get(key, {"likes": 0, "dislikes": 0, "voters": []})
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text=f"👍 {stats['likes']}", callback_data=f"like:{key}"),
                types.InlineKeyboardButton(text=f"👎 {stats['dislikes']}", callback_data=f"dis:{key}"))
    return builder.as_markup()

# --- Хэндлеры ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    total_users = len(STATS_DB)
    await message.answer(
        f"👋 Привет! Я бот для проверки репутации.\n"
        f"📊 Всего записей: {total_users}\n\nВведите юзернейм или ID:",
        reply_markup=InlineKeyboardBuilder().row(
            types.InlineKeyboardButton(text="📢 Отправить жалобу", url=f"https://t.me/{TARGET_CHANNEL}")
        ).as_markup()
    )

@dp.message(Command("shalun"))
async def admin_panel(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("🛠 Режим админа. Введите юзернейм для изменения рейтинга:")
    await state.set_state(AdminState.waiting_for_target)

@dp.message(AdminState.waiting_for_target)
async def ask_action(message: types.Message, state: FSMContext):
    target = normalize(message.text)
    await state.update_data(target=target)
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="👍 Лайки", callback_data="act_like"),
                types.InlineKeyboardButton(text="👎 Дизы", callback_data="act_dis"))
    await message.answer(f"Цель: {target}. Что добавляем?", reply_markup=builder.as_markup())
    await state.set_state(AdminState.waiting_for_action)

@dp.callback_query(AdminState.waiting_for_action)
async def ask_value(callback: types.CallbackQuery, state: FSMContext):
    action = callback.data.split("_")[1]
    await state.update_data(action=action)
    await callback.message.edit_text("Введите число:")
    await state.set_state(AdminState.waiting_for_value)

@dp.message(AdminState.waiting_for_value)
async def process_admin_action(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return
    val = int(message.text)
    data = await state.get_data()
    target, action = data['target'], data['action']
    if target not in STATS_DB: STATS_DB[target] = {"likes": 0, "dislikes": 0, "voters": []}
    STATS_DB[target]["likes" if action == "like" else "dislikes"] += val
    save_db()
    await message.answer(f"✅ Добавлено {val} {action} для {target}!")
    await state.clear()

@dp.callback_query(F.data.startswith(("like:", "dis:")))
async def handle_feedback(callback: types.CallbackQuery):
    action, key = callback.data.split(":")
    key = normalize(key)
    uid = str(callback.from_user.id)
    if key not in STATS_DB: STATS_DB[key] = {"likes": 0, "dislikes": 0, "voters": []}
    if uid in STATS_DB[key]["voters"]:
        await callback.answer("Ты уже голосовал!")
        return
    STATS_DB[key]["likes" if action == "like" else "dislikes"] += 1
    STATS_DB[key]["voters"].append(uid)
    save_db()
    await callback.message.edit_reply_markup(reply_markup=get_kb(key))
    await callback.answer("Голос учтен!")

@dp.message()
async def search(message: types.Message):
    query = normalize(message.text)
    if len(query) < 3 or query.startswith("/"): return
    try:
        channel = await client.get_entity(TARGET_CHANNEL)
        msg_found = None
        user_id_str = "скрыт"
        try:
            user = await client.get_input_entity(query)
            user_id_str = str(user.user_id)
        except: pass
        
        async for msg in client.iter_messages(channel, limit=100):
            if msg.text and query in msg.text.lower():
                msg_found = msg
                break
        
        kb = get_kb(query)
        if msg_found:
            text = (f"<b>SCAM</b> @{query} [{user_id_str}]\n"
                    f"Искали: 🟦 {query}\n"
                    f"Зарегистрирован ~ узнать\n\n"
                    f"⚪️ <b>Репутация: мошенник.</b>\n"
                    f"Добавлен в скам-базу <a href='https://t.me/{TARGET_CHANNEL}/{msg_found.id}'>@{TARGET_CHANNEL}</a> (пруфы по ID). "
                    f"Сделки недопустимы.")
        else:
            text = (f"@{query} [{user_id_str}]\n"
                    f"Искали: 🟦 {query} [о реакциях]\n"
                    f"Зарегистрирован ~ узнать\n\n"
                    f"⚪️ <b>Репутация: чист.</b>\n"
                    f"Жалоб и скама не зафиксировано. Соблюдайте бдительность при сотрудничестве.")
            
        img_name = "scam.jpg" if msg_found else "clean.jpg"
        if os.path.exists(img_name):
            await message.answer_photo(photo=FSInputFile(img_name), caption=text, parse_mode="HTML", reply_markup=kb)
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    await client.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
