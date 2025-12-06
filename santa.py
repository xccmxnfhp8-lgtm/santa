import json
import random
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

TOKEN = "8472545439:AAFEN0Ge-xNKEC89_MYOinEh-8Kc0plKn9g"

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

DATA_FILE = "data.json"
PAIRS_FILE = "pairs.json"
user_temp = {}

# ----------------------- JSON УТИЛИТЫ -----------------------
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_data(d):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def load_pairs():
    try:
        with open(PAIRS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"pairs": {}, "chats": {}}

def save_pairs(d):
    with open(PAIRS_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def get_main_keyboard(uid, data):
    """Возвращает основную клавиатуру с учетом статуса жеребьёвки"""
    buttons = []
    
    # Проверяем, зарегистрирован ли пользователь
    is_registered = str(uid) in data.get("users", {})
    
    if not is_registered:
        buttons.append([KeyboardButton(text="🎮 Участвовать")])
    else:
        # Проверяем, была ли уже жеребьёвка
        pairs_data = load_pairs()
        has_pairs = bool(pairs_data.get("pairs", {}))
        
        # Если жеребьёвки еще не было - показываем кнопки редактирования
        if not has_pairs:
            buttons.extend([
                [KeyboardButton(text="📋 Посмотреть анкету")],
                [KeyboardButton(text="✏️ Изменить данные")],
                [KeyboardButton(text="➕ Добавить в вишлист")]
            ])
        else:
            # После жеребьёвки показываем только просмотр анкеты
            buttons.append([KeyboardButton(text="📋 Посмотреть анкету")])
        
        # Проверяем, есть ли активная пара
        # Если пользователь - Санта (даритель)
        if str(uid) in pairs_data.get("pairs", {}):
            buttons.append([KeyboardButton(text="💌 Спросить получателя")])
            buttons.append([KeyboardButton(text="💬 Ответить на вопросы")])
        
        # Если пользователь - получатель
        else:
            # Проверяем, является ли пользователь получателем у кого-то
            is_receiver = False
            for giver_id, receiver_id in pairs_data.get("pairs", {}).items():
                if int(receiver_id) == uid:
                    is_receiver = True
                    break
            
            if is_receiver:
                buttons.append([KeyboardButton(text="💬 Ответить на вопросы")])
    
    # Проверяем, является ли создателем
    if uid == data.get("creator"):
        buttons.append([KeyboardButton(text="👥 Список участников")])
        buttons.append([KeyboardButton(text="🗑️ Удалить игрока")])
        buttons.append([KeyboardButton(text="🎲 Запустить жеребьёвку")])
        buttons.append([KeyboardButton(text="🛑 Остановить игру")])
    
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# ----------------------- ОСТАНОВКА ИГРЫ -----------------------
@dp.message(F.text == "🛑 Остановить игру")
async def stop_game(msg: types.Message):
    data = load_data()
    
    if msg.from_user.id != data.get("creator"):
        await msg.answer("❌ Это доступно только создателю")
        return
    
    # Создаем клавиатуру подтверждения
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Да, остановить игру")],
            [KeyboardButton(text="❌ Нет, вернуться")]
        ],
        resize_keyboard=True
    )
    
    # Сохраняем текущие данные для возможного отката
    user_temp[msg.from_user.id] = {
        "step": "confirm_stop_game",
        "backup_data": data.copy(),
        "backup_pairs": load_pairs().copy()
    }
    
    await msg.answer(
        "⚠️ <b>ВНИМАНИЕ!</b>\n\n"
        "Вы собираетесь остановить игру. Это приведёт к:\n"
        "• Удалению всех участников\n"
        "• Удалению всех пар\n"
        "• Удалению истории чатов\n"
        "• Очистке всех данных\n\n"
        "<b>Игра начнётся заново!</b>\n\n"
        "Вы уверены?",
        reply_markup=kb
    )

@dp.message(lambda m: m.from_user.id in user_temp and user_temp[m.from_user.id].get("step") == "confirm_stop_game")
async def confirm_stop_game(msg: types.Message):
    uid = msg.from_user.id
    
    if msg.text == "✅ Да, остановить игру":
        # Полностью очищаем данные
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"creator": uid, "users": {}}, f, ensure_ascii=False, indent=2)
        
        with open(PAIRS_FILE, "w", encoding="utf-8") as f:
            json.dump({"pairs": {}, "chats": {}}, f, ensure_ascii=False, indent=2)
        
        # Очищаем временные данные
        global user_temp
        user_temp = {}
        
        await msg.answer(
            "✅ <b>Игра остановлена!</b>\n\n"
            "Все данные удалены. Теперь можно начать новую игру!\n\n"
            "Нажмите /start для начала новой игры."
        )
        
    elif msg.text == "❌ Нет, вернуться":
        del user_temp[uid]
        data = load_data()
        kb = get_main_keyboard(uid, data)
        await msg.answer("✅ Отмена. Игра продолжается.", reply_markup=kb)

# ----------------------- СТАРТ -----------------------
@dp.message(Command("start"))
async def start(msg: types.Message):
    data = load_data()
    
    if "creator" not in data:
        data["creator"] = msg.from_user.id
        data["users"] = {}
        save_data(data)
    
    # Если пользователь в процессе регистрации, предлагаем завершить
    if msg.from_user.id in user_temp:
        del user_temp[msg.from_user.id]
    
    welcome_text = """🎄✨ <b>ДОРОГАЯ СЕМЬЯ!</b> ✨🎄

🎅 <i>С НАСТУПАЮЩИМ НОВЫМ ГОДОМ!</i> 🎁

Этот волшебный бот создан специально для нашей семьи!

❤️ <b>С любовью сделали для вас:</b>
   • Крутая Машулька 🦄
   • Супер Федюк 🦸‍♂️"""

    # Проверяем, зарегистрирован ли пользователь
    is_registered = str(msg.from_user.id) in data.get("users", {})
    
    if not is_registered:
        welcome_text += "\n\nНажмите <b>'🎮 Участвовать'</b> чтобы присоединиться к Тайному Санте!"
    else:
        welcome_text += "\n\nВы уже участвуете в Тайном Санте! 🎅"
    
    kb = get_main_keyboard(msg.from_user.id, data)
    await msg.answer(welcome_text, reply_markup=kb)

# ----------------------- ПОСМОТРЕТЬ АНКЕТУ -----------------------
@dp.message(F.text == "📋 Посмотреть анкету")
async def view_profile(msg: types.Message):
    uid = msg.from_user.id
    data = load_data()
    
    if str(uid) not in data.get("users", {}):
        await msg.answer("❌ Сначала нужно зарегистрироваться через кнопку <b>'🎮 Участвовать'</b>")
        return
    
    user_data = data["users"][str(uid)]
    
    text = "📋 <b>ВАША АНКЕТА:</b>\n\n"
    text += f"👤 <b>Имя:</b> {user_data['name']}\n\n"
    text += f"💭 <b>Хочу получить:</b>\n{user_data['wish']}\n\n"
    text += f"🚫 <b>Не хочу получать:</b>\n{user_data['antis']}\n\n"
    
    if "wishlist_items" in user_data and user_data["wishlist_items"]:
        text += "🎁 <b>Вишлист:</b>\n"
        for i, item in enumerate(user_data["wishlist_items"], 1):
            text += f"{i}. <b>{item['name']}</b>\n"
            text += f"   💰 Цена: {item['price']}\n"
            text += f'   🔗 <a href="{item["link"]}">Ссылка на подарок</a>\n\n'
    
    # Проверяем жеребьёвку
    pairs_data = load_pairs()
    if str(uid) in pairs_data.get("pairs", {}):
        receiver_id = pairs_data["pairs"][str(uid)]
        receiver_name = data["users"][receiver_id]["name"]
        text += f"🎅 <b>Ваш получатель:</b> {receiver_name}\n\n"
        text += "💌 Вы можете задавать вопросы получателю анонимно!"
    
    kb = get_main_keyboard(uid, data)
    await msg.answer(text, reply_markup=kb, parse_mode="HTML")

# ----------------------- УДАЛЕНИЕ ИГРОКА (для админа) -----------------------
@dp.message(F.text == "🗑️ Удалить игрока")
async def delete_player_menu(msg: types.Message):
    data = load_data()
    
    if msg.from_user.id != data.get("creator"):
        await msg.answer("❌ Это доступно только создателю")
        return
    
    users = data.get("users", {})
    if not users:
        await msg.answer("📭 Нет зарегистрированных игроков.")
        return
    
    text = "👥 <b>Выберите игрока для удаления:</b>\n\n"
    buttons = []
    
    for user_id, user_data in users.items():
        try:
            user_info = await bot.get_chat(int(user_id))
            username = f" @{user_info.username}" if user_info.username else ""
            text += f"• {user_data['name']} (ID: {user_id}){username}\n"
            buttons.append([KeyboardButton(text=f"🗑️ Удалить {user_data['name']}")])
        except:
            text += f"• {user_data['name']} (ID: {user_id})\n"
            buttons.append([KeyboardButton(text=f"🗑️ Удалить {user_data['name']}")])
    
    buttons.append([KeyboardButton(text="↩️ Назад")])
    
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    user_temp[msg.from_user.id] = {"step": "delete_player"}
    await msg.answer(text, reply_markup=keyboard)

@dp.message(lambda m: m.from_user.id in user_temp and user_temp[m.from_user.id].get("step") == "delete_player")
async def delete_player_handler(msg: types.Message):
    if msg.text == "↩️ Назад":
        del user_temp[msg.from_user.id]
        await start(msg)
        return
    
    if msg.text.startswith("🗑️ Удалить "):
        player_name = msg.text.replace("🗑️ Удалить ", "").strip()
        data = load_data()
        
        player_id = None
        for user_id, user_data in data.get("users", {}).items():
            if user_data["name"] == player_name:
                player_id = user_id
                break
        
        if player_id:
            # Удаляем из данных
            del data["users"][player_id]
            save_data(data)
            
            # Удаляем из пар
            pairs_data = load_pairs()
            if player_id in pairs_data.get("pairs", {}):
                del pairs_data["pairs"][player_id]
            
            # Удаляем пары, где этот игрок был получателем
            pairs_to_delete = []
            for giver_id, receiver_id in pairs_data.get("pairs", {}).items():
                if receiver_id == player_id:
                    pairs_to_delete.append(giver_id)
            
            for giver_id in pairs_to_delete:
                del pairs_data["pairs"][giver_id]
            
            save_pairs(pairs_data)
            
            # Очищаем временные данные если есть
            if int(player_id) in user_temp:
                del user_temp[int(player_id)]
            
            del user_temp[msg.from_user.id]
            await msg.answer(f"✅ Игрок <b>{player_name}</b> удален из игры!\n\nОн может зарегистрироваться заново через кнопку '🎮 Участвовать'.")
            await start(msg)
        else:
            await msg.answer("❌ Игрок не найден.")

# ----------------------- РЕГИСТРАЦИЯ -----------------------
@dp.message(F.text == "🎮 Участвовать")
async def join(msg: types.Message):
    data = load_data()
    
    # Проверяем, не зарегистрирован ли уже пользователь
    if str(msg.from_user.id) in data.get("users", {}):
        kb = get_main_keyboard(msg.from_user.id, data)
        await msg.answer("✅ Вы уже зарегистрированы!", reply_markup=kb)
        return
    
    user_temp[msg.from_user.id] = {"step": 1}
    await msg.answer("👤 <b>Шаг 1 из 4:</b> Введите ваше имя:")

@dp.message(F.text == "✏️ Изменить данные")
async def edit_data(msg: types.Message):
    uid = msg.from_user.id
    data = load_data()
    
    if str(uid) not in data.get("users", {}):
        # Пытаемся найти пользователя в user_temp (в процессе регистрации)
        if uid in user_temp and "name" in user_temp[uid]:
            # Пользователь в процессе регистрации
            await msg.answer("⚠️ Вы в процессе регистрации. Завершите её через кнопку <b>'🎮 Участвовать'</b>")
            return
        else:
            await msg.answer("❌ Сначала нужно зарегистрироваться через кнопку <b>'🎮 Участвовать'</b>")
            return
    
    user_data = data["users"][str(uid)]
    text = "📋 <b>Ваши текущие данные:</b>\n\n"
    text += f"👤 <b>Имя:</b> {user_data['name']}\n"
    text += f"💭 <b>Хочу получить:</b>\n{user_data['wish']}\n"
    text += f"🚫 <b>Не хочу получать:</b>\n{user_data['antis']}\n\n"
    
    if "wishlist_items" in user_data and user_data["wishlist_items"]:
        text += "🎁 <b>Вишлист:</b>\n"
        for i, item in enumerate(user_data["wishlist_items"], 1):
            text += f"{i}. {item['name']} - {item['price']} руб.\n"
    
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✏️ Изменить имя")],
            [KeyboardButton(text="✏️ Изменить 'хочу получить'")],
            [KeyboardButton(text="✏️ Изменить 'не хочу получать'")],
            [KeyboardButton(text="📝 Редактировать вишлист")],
            [KeyboardButton(text="✅ Всё верно, ничего не менять")]
        ],
        resize_keyboard=True
    )
    
    user_temp[uid] = {"step": "edit_choice", "current_data": user_data.copy()}
    await msg.answer(text + "\n<b>Что вы хотите изменить?</b>", reply_markup=kb)

# Обработка выбора в меню редактирования
@dp.message(lambda m: m.from_user.id in user_temp and user_temp[m.from_user.id].get("step") == "edit_choice")
async def edit_choice_handler(msg: types.Message):
    uid = msg.from_user.id
    
    if msg.text == "✏️ Изменить имя":
        user_temp[uid]["step"] = "edit_name"
        await msg.answer("Введите новое имя:")
    
    elif msg.text == "✏️ Изменить 'хочу получить'":
        user_temp[uid]["step"] = "edit_wish"
        await msg.answer("Введите что вы хотите получить:")
    
    elif msg.text == "✏️ Изменить 'не хочу получать'":
        user_temp[uid]["step"] = "edit_antis"
        await msg.answer("Введите что не хотите получать:")
    
    elif msg.text == "📝 Редактировать вишлист":
        user_temp[uid]["step"] = "edit_wishlist_menu"
        await show_wishlist_edit_menu(msg, uid)
    
    elif msg.text == "✅ Всё верно, ничего не менять":
        del user_temp[uid]
        data = load_data()
        kb = get_main_keyboard(uid, data)
        await msg.answer("✅ Данные сохранены!", reply_markup=kb)

# Обработка редактирования полей
@dp.message(lambda m: m.from_user.id in user_temp and user_temp[m.from_user.id].get("step") in ["edit_name", "edit_wish", "edit_antis"])
async def edit_field_handler(msg: types.Message):
    uid = msg.from_user.id
    step = user_temp[uid]["step"]
    
    data = load_data()
    
    if step == "edit_name":
        data["users"][str(uid)]["name"] = msg.text
    elif step == "edit_wish":
        data["users"][str(uid)]["wish"] = msg.text
    elif step == "edit_antis":
        data["users"][str(uid)]["antis"] = msg.text
    
    save_data(data)
    
    del user_temp[uid]
    kb = get_main_keyboard(uid, data)
    await msg.answer("✅ Изменения сохранены!", reply_markup=kb)

# Меню редактирования вишлиста
async def show_wishlist_edit_menu(msg: types.Message, uid: int):
    data = load_data()
    user_data = data["users"][str(uid)]
    
    text = "🎁 <b>Ваш вишлист:</b>\n\n"
    if "wishlist_items" in user_data and user_data["wishlist_items"]:
        for i, item in enumerate(user_data["wishlist_items"], 1):
            text += f"{i}. <b>{item['name']}</b> - {item['price']} руб.\n"
    else:
        text += "Пока пусто.\n"
    
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить подарок")],
            [KeyboardButton(text="🗑️ Удалить подарок")],
            [KeyboardButton(text="✅ Готово")]
        ],
        resize_keyboard=True
    )
    
    user_temp[uid]["step"] = "edit_wishlist_menu"
    await msg.answer(text + "\n<b>Что хотите сделать с вишлистом?</b>", reply_markup=kb)

# Обработка меню редактирования вишлиста
@dp.message(lambda m: m.from_user.id in user_temp and user_temp[m.from_user.id].get("step") == "edit_wishlist_menu")
async def edit_wishlist_menu_handler(msg: types.Message):
    uid = msg.from_user.id
    
    if msg.text == "➕ Добавить подарок":
        user_temp[uid]["step"] = "wishlink"
        user_temp[uid]["mode"] = "edit_existing"
        await msg.answer("🔗 Отправьте ссылку на подарок:")
    
    elif msg.text == "🗑️ Удалить подарок":
        user_temp[uid]["step"] = "delete_wishlist_existing"
        await msg.answer("Введите номер подарка для удаления (только цифру):")
    
    elif msg.text == "✅ Готово":
        del user_temp[uid]
        data = load_data()
        kb = get_main_keyboard(uid, data)
        await msg.answer("✅ Готово!", reply_markup=kb)

@dp.message(F.text == "➕ Добавить в вишлист")
async def add_wishlist(msg: types.Message):
    uid = msg.from_user.id
    data = load_data()
    
    if str(uid) not in data.get("users", {}):
        await msg.answer("❌ Сначала нужно зарегистрироваться через кнопку <b>'🎮 Участвовать'</b>")
        return
    
    user_data = data["users"][str(uid)]
    
    text = "🎁 <b>Ваш текущий вишлист:</b>\n\n"
    if "wishlist_items" in user_data and user_data["wishlist_items"]:
        for i, item in enumerate(user_data["wishlist_items"], 1):
            text += f"{i}. <b>{item['name']}</b>\n   💰 {item['price']}\n   🔗 <a href=\"{item['link']}\">Ссылка на подарок</a>\n\n"
    else:
        text += "Пока пусто. Добавьте первый подарок!\n\n"
    
    user_temp[uid] = {"step": "add_wishlist_menu", "existing_items": user_data.get("wishlist_items", [])}
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить новый подарок")],
            [KeyboardButton(text="🗑️ Удалить подарок")],
            [KeyboardButton(text="✅ Готово")]
        ],
        resize_keyboard=True
    )
    await msg.answer(text + "<b>Что хотите сделать?</b>", reply_markup=kb, parse_mode="HTML")

# Обработка меню добавления в вишлист
@dp.message(lambda m: m.from_user.id in user_temp and user_temp[m.from_user.id].get("step") == "add_wishlist_menu")
async def add_wishlist_menu_handler(msg: types.Message):
    uid = msg.from_user.id
    
    if msg.text == "✅ Готово":
        del user_temp[uid]
        data = load_data()
        kb = get_main_keyboard(uid, data)
        await msg.answer("✅ Готово!", reply_markup=kb)
        return
    
    if msg.text == "➕ Добавить новый подарок":
        user_temp[uid]["step"] = "wishlink"
        user_temp[uid]["mode"] = "add_only"
        await msg.answer("🔗 Отправьте ссылку на подарок:")
        return
    
    if msg.text == "🗑️ Удалить подарок":
        user_temp[uid]["step"] = "delete_wishlist"
        await msg.answer("Введите номер подарка для удаления (только цифру):")
        return

# Шаги основной регистрации
@dp.message(lambda m: m.from_user.id in user_temp and user_temp[m.from_user.id].get("step") in [1, 2, 3])
async def reg_steps(msg: types.Message):
    uid = msg.from_user.id
    step = user_temp[uid]["step"]

    if step == 1:
        user_temp[uid]["name"] = msg.text
        user_temp[uid]["step"] = 2
        await msg.answer("💭 <b>Шаг 2 из 4:</b> Что бы вы хотели получить?\n\n<i>Можно написать общие категории или конкретные вещи</i>")
        return

    if step == 2:
        user_temp[uid]["wish"] = msg.text
        user_temp[uid]["step"] = 3
        await msg.answer("🚫 <b>Шаг 3 из 4:</b> Что точно НЕ хотите получать?")
        return

    if step == 3:
        user_temp[uid]["antis"] = msg.text
        user_temp[uid]["step"] = "ask_wishlist"
        
        kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="✅ Да, добавить")],
                [KeyboardButton(text="❌ Нет, пропустить")]
            ],
            resize_keyboard=True
        )
        await msg.answer("🎁 <b>Хотите добавить ссылки на конкретные подарки в вишлист?</b>\n\nЭто поможет вашему Санте с выбором!", reply_markup=kb)

# Обработка выбора про вишлист
@dp.message(lambda m: m.from_user.id in user_temp and user_temp[m.from_user.id].get("step") == "ask_wishlist")
async def ask_wishlist_handler(msg: types.Message):
    uid = msg.from_user.id
    
    if msg.text == "✅ Да, добавить":
        user_temp[uid]["step"] = "wishlink"
        user_temp[uid]["mode"] = "registration"
        await msg.answer("🔗 Отлично! Отправьте ссылку на первый подарок:")
    elif msg.text == "❌ Нет, пропустить":
        await show_confirmation(msg, uid)

# Обработка вишлиста
@dp.message(lambda m: m.from_user.id in user_temp and user_temp[m.from_user.id].get("step") in ["wishlink", "wishname", "wishprice"])
async def wishlist_steps(msg: types.Message):
    uid = msg.from_user.id
    
    if user_temp[uid].get("step") == "wishlink":
        user_temp[uid]["current_item"] = {"link": msg.text}
        user_temp[uid]["step"] = "wishname"
        await msg.answer("📝 Как называется этот подарок?\n\n<i>Например: Ваза, Книга, Свитер</i>")
    
    elif user_temp[uid].get("step") == "wishname":
        user_temp[uid]["current_item"]["name"] = msg.text
        user_temp[uid]["step"] = "wishprice"
        await msg.answer("💰 Укажите примерную цену:\n\n<i>Например: 1500, 2000-2500, до 3000 рублей</i>")
    
    elif user_temp[uid].get("step") == "wishprice":
        user_temp[uid]["current_item"]["price"] = msg.text
        item = user_temp[uid]["current_item"]
        
        if user_temp[uid].get("mode") == "registration":
            if "wishlist_items" not in user_temp[uid]:
                user_temp[uid]["wishlist_items"] = []
            user_temp[uid]["wishlist_items"].append(item)
            
            kb = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="➕ Добавить ещё")],
                    [KeyboardButton(text="✅ Завершить")]
                ],
                resize_keyboard=True
            )
            
            await msg.answer(f"✅ Подарок добавлен!\n\n🎁 <b>{item['name']}</b>\n💰 {item['price']} руб.\n🔗 <a href=\"{item['link']}\">Ссылка на подарок</a>\n\nДобавить ещё подарок или завершить?", reply_markup=kb, parse_mode="HTML")
            user_temp[uid]["step"] = "wishmore"
        
        elif user_temp[uid].get("mode") in ["add_only", "edit_existing"]:
            data = load_data()
            if str(uid) in data["users"]:
                if "wishlist_items" not in data["users"][str(uid)]:
                    data["users"][str(uid)]["wishlist_items"] = []
                data["users"][str(uid)]["wishlist_items"].append(item)
                save_data(data)
            
            del user_temp[uid]
            kb = get_main_keyboard(uid, data)
            await msg.answer(f"✅ Подарок добавлен в вишлист!", reply_markup=kb)

# Обработка завершения вишлиста при регистрации
@dp.message(lambda m: m.from_user.id in user_temp and user_temp[m.from_user.id].get("step") == "wishmore")
async def wishlist_more(msg: types.Message):
    uid = msg.from_user.id
    
    if msg.text == "➕ Добавить ещё":
        user_temp[uid]["step"] = "wishlink"
        await msg.answer("🔗 Отправьте ссылку на следующий подарок:")
    elif msg.text == "✅ Завершить":
        await show_confirmation(msg, uid)

# Показать анкету для подтверждения
async def show_confirmation(msg: types.Message, uid: int):
    user_data = user_temp[uid]
    
    text = "📋 <b>ВАША АНКЕТА ДЛЯ ПРОВЕРКИ:</b>\n\n"
    text += f"👤 <b>Имя:</b> {user_data['name']}\n\n"
    text += f"💭 <b>Хочу получить:</b>\n{user_data['wish']}\n\n"
    text += f"🚫 <b>Не хочу получать:</b>\n{user_data['antis']}\n\n"
    
    if "wishlist_items" in user_data and user_data["wishlist_items"]:
        text += "🎁 <b>Вишлист:</b>\n"
        for i, item in enumerate(user_data["wishlist_items"], 1):
            text += f"{i}. <b>{item['name']}</b> - {item['price']} руб.\n"
            text += f'   🔗 <a href="{item["link"]}">Ссылка на подарок</a>\n\n'
    
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Всё верно, завершить")],
            [KeyboardButton(text="✏️ Что-то изменить")]
        ],
        resize_keyboard=True
    )
    
    user_temp[uid]["step"] = "confirmation"
    await msg.answer(text + "<b>Всё верно?</b>", reply_markup=kb, parse_mode="HTML")

# Обработка подтверждения анкеты
@dp.message(lambda m: m.from_user.id in user_temp and user_temp[m.from_user.id].get("step") == "confirmation")
async def confirmation_handler(msg: types.Message):
    uid = msg.from_user.id
    
    if msg.text == "✅ Всё верно, завершить":
        save_user_data(uid, user_temp[uid])
        del user_temp[uid]
        
        data = load_data()
        kb = get_main_keyboard(uid, data)
        await msg.answer("🎉 <b>РЕГИСТРАЦИЯ ЗАВЕРШЕНА!</b>\n\nТеперь ждите жеребьёвки! ✨", reply_markup=kb)
    
    elif msg.text == "✏️ Что-то изменить":
        kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="👤 Изменить имя")],
                [KeyboardButton(text="💭 Изменить 'хочу получить'")],
                [KeyboardButton(text="🚫 Изменить 'не хочу получать'")],
                [KeyboardButton(text="🎁 Редактировать вишлист")],
                [KeyboardButton(text="↩️ Назад к проверке")]
            ],
            resize_keyboard=True
        )
        user_temp[uid]["step"] = "edit_specific"
        await msg.answer("Что именно вы хотите изменить?", reply_markup=kb)

# Обработка редактирования в проверке анкеты
@dp.message(lambda m: m.from_user.id in user_temp and user_temp[m.from_user.id].get("step") == "edit_specific")
async def edit_specific_handler(msg: types.Message):
    uid = msg.from_user.id
    
    if msg.text == "👤 Изменить имя":
        user_temp[uid]["edit_field"] = "name"
        user_temp[uid]["step"] = "edit_value"
        await msg.answer("Введите новое имя:")
    
    elif msg.text == "💭 Изменить 'хочу получить'":
        user_temp[uid]["edit_field"] = "wish"
        user_temp[uid]["step"] = "edit_value"
        await msg.answer("Введите новые пожелания:")
    
    elif msg.text == "🚫 Изменить 'не хочу получать'":
        user_temp[uid]["edit_field"] = "antis"
        user_temp[uid]["step"] = "edit_value"
        await msg.answer("Введите что не хотите получать:")
    
    elif msg.text == "🎁 Редактировать вишлист":
        user_temp[uid]["step"] = "edit_wishlist_confirm"
        await show_wishlist_edit_confirm(msg, uid)
    
    elif msg.text == "↩️ Назад к проверке":
        await show_confirmation(msg, uid)

# Показать редактирование вишлиста при проверке
async def show_wishlist_edit_confirm(msg: types.Message, uid: int):
    user_data = user_temp[uid]
    
    text = "🎁 <b>Ваш вишлист:</b>\n\n"
    if "wishlist_items" in user_data and user_data["wishlist_items"]:
        for i, item in enumerate(user_data["wishlist_items"], 1):
            text += f"{i}. <b>{item['name']}</b> - {item['price']} руб.\n"
    
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить подарок")],
            [KeyboardButton(text="🗑️ Удалить подарок")],
            [KeyboardButton(text="✅ Готово, вернуться к проверке")]
        ],
        resize_keyboard=True
    )
    
    await msg.answer(text + "\n<b>Что хотите сделать с вишлистом?</b>", reply_markup=kb)

# Обработка редактирования вишлиста при проверке
@dp.message(lambda m: m.from_user.id in user_temp and user_temp[m.from_user.id].get("step") == "edit_wishlist_confirm")
async def edit_wishlist_confirm_handler(msg: types.Message):
    uid = msg.from_user.id
    
    if msg.text == "➕ Добавить подарок":
        user_temp[uid]["step"] = "wishlink"
        user_temp[uid]["mode"] = "registration"
        await msg.answer("🔗 Отправьте ссылку на подарок:")
    
    elif msg.text == "🗑️ Удалить подарок":
        user_temp[uid]["step"] = "delete_wishlist_confirm"
        await msg.answer("Введите номер подарка для удаления (только цифру):")
    
    elif msg.text == "✅ Готово, вернуться к проверке":
        await show_confirmation(msg, uid)

# Обработка удаления из вишлиста (при проверке)
@dp.message(lambda m: m.from_user.id in user_temp and user_temp[m.from_user.id].get("step") == "delete_wishlist_confirm")
async def delete_wishlist_confirm_handler(msg: types.Message):
    uid = msg.from_user.id
    
    # Проверяем кнопки меню
    if msg.text == "✅ Готово, вернуться к проверке":
        await show_confirmation(msg, uid)
        return
    
    if msg.text == "➕ Добавить подарок":
        user_temp[uid]["step"] = "wishlink"
        user_temp[uid]["mode"] = "registration"
        await msg.answer("🔗 Отправьте ссылку на подарок:")
        return
    
    if msg.text == "🗑️ Удалить подарок":
        await msg.answer("Введите номер подарка для удаления (только цифру):")
        return
    
    # Только потом пытаемся парсить цифру
    try:
        num = int(msg.text) - 1
        if "wishlist_items" in user_temp[uid] and 0 <= num < len(user_temp[uid]["wishlist_items"]):
            deleted = user_temp[uid]["wishlist_items"].pop(num)
            await msg.answer(f"✅ Подарок <b>'{deleted['name']}'</b> удален из вишлиста.")
            await show_wishlist_edit_confirm(msg, uid)
        else:
            await msg.answer("❌ Неверный номер. Попробуйте еще раз.")
    except ValueError:
        await msg.answer("❌ Введите только цифру (номер подарка).")

# Обработка ввода нового значения для поля
@dp.message(lambda m: m.from_user.id in user_temp and user_temp[m.from_user.id].get("step") == "edit_value")
async def edit_value_handler(msg: types.Message):
    uid = msg.from_user.id
    field = user_temp[uid]["edit_field"]
    
    user_temp[uid][field] = msg.text
    await show_confirmation(msg, uid)

# Обработка удаления из вишлиста (из меню добавления)
@dp.message(lambda m: m.from_user.id in user_temp and user_temp[m.from_user.id].get("step") == "delete_wishlist")
async def delete_wishlist_handler(msg: types.Message):
    uid = msg.from_user.id
    
    # ПРОВЕРЯЕМ СПЕЦИАЛЬНЫЕ КНОПКИ ПРЕЖДЕ ВСЕГО
    if msg.text == "✅ Готово":
        del user_temp[uid]
        data = load_data()
        kb = get_main_keyboard(uid, data)
        await msg.answer("✅ Готово!", reply_markup=kb)
        return
    
    if msg.text == "➕ Добавить новый подарок":
        user_temp[uid]["step"] = "wishlink"
        user_temp[uid]["mode"] = "add_only"
        await msg.answer("🔗 Отправьте ссылку на подарок:")
        return
    
    # ТОЛЬКО ЕСЛИ ЭТО НЕ КНОПКА, ПЫТАЕМСЯ ПАРСИТЬ ЦИФРУ
    try:
        num = int(msg.text) - 1
        data = load_data()
        
        if str(uid) not in data["users"]:
            await msg.answer("❌ Ошибка: пользователь не найден.")
            return
        
        if "wishlist_items" in data["users"][str(uid)] and 0 <= num < len(data["users"][str(uid)]["wishlist_items"]):
            deleted = data["users"][str(uid)]["wishlist_items"].pop(num)
            save_data(data)
            await msg.answer(f"✅ Подарок <b>'{deleted['name']}'</b> удален из вишлиста.")
            
            user_temp[uid] = {"step": "add_wishlist_menu", "existing_items": data["users"][str(uid)].get("wishlist_items", [])}
            text = "🎁 <b>Ваш обновленный вишлист:</b>\n\n"
            if data["users"][str(uid)]["wishlist_items"]:
                for i, item in enumerate(data["users"][str(uid)]["wishlist_items"], 1):
                    text += f"{i}. <b>{item['name']}</b>\n   💰 {item['price']}\n   🔗 <a href=\"{item['link']}\">Ссылка на подарок</a>\n\n"
            else:
                text += "Пока пусто.\n\n"
            
            kb = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="➕ Добавить новый подарок")],
                    [KeyboardButton(text="🗑️ Удалить подарок")],
                    [KeyboardButton(text="✅ Готово")]
                ],
                resize_keyboard=True
            )
            await msg.answer(text + "<b>Что дальше?</b>", reply_markup=kb, parse_mode="HTML")
        else:
            await msg.answer("❌ Неверный номер. Попробуйте еще раз.")
    except ValueError:
        await msg.answer("❌ Введите только цифру (номер подарка).")

# Обработка удаления из вишлиста (из меню редактирования)
@dp.message(lambda m: m.from_user.id in user_temp and user_temp[m.from_user.id].get("step") == "delete_wishlist_existing")
async def delete_wishlist_existing_handler(msg: types.Message):
    uid = msg.from_user.id
    
    # Проверяем кнопки меню
    if msg.text == "✅ Готово":
        del user_temp[uid]
        data = load_data()
        kb = get_main_keyboard(uid, data)
        await msg.answer("✅ Готово!", reply_markup=kb)
        return
    
    if msg.text == "➕ Добавить подарок":
        user_temp[uid]["step"] = "wishlink"
        user_temp[uid]["mode"] = "edit_existing"
        await msg.answer("🔗 Отправьте ссылку на подарок:")
        return
    
    # Только потом пытаемся парсить цифру
    try:
        num = int(msg.text) - 1
        data = load_data()
        
        if str(uid) not in data["users"]:
            await msg.answer("❌ Ошибка: пользователь не найден.")
            return
        
        if "wishlist_items" in data["users"][str(uid)] and 0 <= num < len(data["users"][str(uid)]["wishlist_items"]):
            deleted = data["users"][str(uid)]["wishlist_items"].pop(num)
            save_data(data)
            await msg.answer(f"✅ Подарок <b>'{deleted['name']}'</b> удален из вишлиста.")
            
            await show_wishlist_edit_menu(msg, uid)
        else:
            await msg.answer("❌ Неверный номер. Попробуйте еще раз.")
    except ValueError:
        await msg.answer("❌ Введите только цифру (номер подарка).")

def save_user_data(uid, user_data):
    """Сохраняет данные пользователя"""
    data = load_data()
    
    user_dict = {
        "name": user_data["name"],
        "wish": user_data["wish"],
        "antis": user_data["antis"]
    }
    
    if "wishlist_items" in user_data:
        user_dict["wishlist_items"] = user_data["wishlist_items"]
    
    data["users"][str(uid)] = user_dict
    save_data(data)

# ----------------------- АНОНИМНЫЕ ВОПРОСЫ -----------------------
# Кнопка "Спросить получателя" (только для Санты)
@dp.message(F.text == "💌 Спросить получателя")
async def ask_receiver(msg: types.Message):
    uid = msg.from_user.id
    pairs_data = load_pairs()
    data = load_data()
    
    # Проверяем, является ли пользователь Сантой
    if str(uid) not in pairs_data.get("pairs", {}):
        await msg.answer("❌ Вы еще не получили своего получателя. Дождитесь жеребьёвки!")
        return
    
    receiver_id = int(pairs_data["pairs"][str(uid)])
    
    if str(receiver_id) not in data.get("users", {}):
        await msg.answer("❌ Ошибка: получатель не найден.")
        return
    
    receiver_name = data["users"][str(receiver_id)]["name"]
    
    user_temp[uid] = {
        "step": "ask_receiver_question",
        "receiver_id": receiver_id,
        "receiver_name": receiver_name
    }
    
    await msg.answer(f"💌 <b>Напишите вопрос для вашего получателя:</b> {receiver_name}\n\n"
                    f"<i>Вопрос будет отправлен анонимно</i>")

# Обработка вопроса Санты получателю
@dp.message(lambda m: m.from_user.id in user_temp and user_temp[m.from_user.id].get("step") == "ask_receiver_question")
async def send_question_to_receiver(msg: types.Message):
    uid = msg.from_user.id
    
    if uid not in user_temp or "receiver_id" not in user_temp[uid]:
        await msg.answer("❌ Ошибка: данные не найдены. Начните заново.")
        return
    
    temp_data = user_temp[uid]
    receiver_id = temp_data["receiver_id"]
    question = msg.text
    
    # Загружаем данные для имени получателя
    data = load_data()
    if str(receiver_id) not in data.get("users", {}):
        await msg.answer("❌ Ошибка: получатель не найден в базе.")
        del user_temp[uid]
        return
    
    receiver_name = data["users"][str(receiver_id)]["name"]
    
    try:
        # Отправляем вопрос получателю
        await bot.send_message(
            receiver_id,
            f"💌 <b>Вам анонимный вопрос от вашего Тайного Санты!</b>\n\n"
            f"❓ <b>Вопрос:</b>\n{question}\n\n"
            f"<i>Напишите ответ прямо сейчас:</i>"
        )
        
        # Сохраняем в историю
        pairs_data = load_pairs()
        chat_key = f"{min(uid, receiver_id)}_{max(uid, receiver_id)}"
        
        if chat_key not in pairs_data["chats"]:
            pairs_data["chats"][chat_key] = []
        
        pairs_data["chats"][chat_key].append({
            "from": uid,
            "to": receiver_id,
            "message": question,
            "type": "question",
            "time": str(asyncio.get_event_loop().time())
        })
        save_pairs(pairs_data)
        
        # Записываем, что у получателя есть ожидающий ответа вопрос
        if receiver_id not in user_temp:
            user_temp[receiver_id] = {}
        user_temp[receiver_id]["waiting_answer_from"] = uid
        
        # Отправляем подтверждение Санте
        await msg.answer(f"✅ Ваш вопрос отправлен {receiver_name} анонимно!\n\nОжидайте ответа.")
        
        # Очищаем временные данные
        del user_temp[uid]
        
    except Exception as e:
        await msg.answer(f"❌ Не удалось отправить вопрос: {str(e)}")

# Кнопка "Ответить на вопросы" (для получателей)
@dp.message(F.text == "💬 Ответить на вопросы")
async def answer_questions_menu(msg: types.Message):
    uid = msg.from_user.id
    pairs_data = load_pairs()
    data = load_data()
    
    # Проверяем, есть ли у пользователя ожидающий ответа вопрос
    if uid in user_temp and "waiting_answer_from" in user_temp[uid]:
        questioner_id = user_temp[uid]["waiting_answer_from"]
        if str(questioner_id) in data.get("users", {}):
            questioner_name = data["users"][str(questioner_id)]["name"]
            
            # Ищем последний вопрос
            chat_key = f"{min(uid, questioner_id)}_{max(uid, questioner_id)}"
            if chat_key in pairs_data.get("chats", {}):
                for msg_data in reversed(pairs_data["chats"][chat_key]):
                    if msg_data["type"] == "question" and msg_data["from"] == questioner_id:
                        user_temp[uid] = {
                            "step": "send_answer",
                            "questioner_id": questioner_id,
                            "questioner_name": questioner_name
                        }
                        
                        await msg.answer(
                            f"💌 <b>Вам вопрос от вашего Тайного Санты:</b>\n\n"
                            f"❓ <b>Вопрос:</b>\n{msg_data['message']}\n\n"
                            f"<i>Напишите ответ прямо сейчас:</i>"
                        )
                        return
    
    # Если нет ожидающих вопросов, проверяем стандартную логику
    has_unanswered = False
    
    # Проверяем, является ли пользователь получателем
    receiver_for = None
    for giver_id_str, receiver_id in pairs_data.get("pairs", {}).items():
        if int(receiver_id) == uid:
            receiver_for = int(giver_id_str)
            break
    
    # Также проверяем, является ли пользователь Сантой (может быть получатель у своего Санты)
    is_santa = str(uid) in pairs_data.get("pairs", {})
    
    if receiver_for:
        # Пользователь - получатель, проверяем вопросы от его Санты
        chat_key = f"{min(uid, receiver_for)}_{max(uid, receiver_for)}"
        
        if chat_key in pairs_data.get("chats", {}):
            for msg_data in reversed(pairs_data["chats"][chat_key]):
                if msg_data["type"] == "question" and msg_data["from"] == receiver_for:
                    giver_name = data["users"][str(receiver_for)]["name"]
                    
                    user_temp[uid] = {
                        "step": "send_answer",
                        "questioner_id": receiver_for,
                        "questioner_name": "ваш Тайный Санта"
                    }
                    
                    await msg.answer(
                        f"💌 <b>Вам вопрос от вашего Тайного Санты:</b>\n\n"
                        f"❓ <b>Вопрос:</b>\n{msg_data['message']}\n\n"
                        f"<i>Напишите ответ прямо сейчас:</i>"
                    )
                    has_unanswered = True
                    break
    
    elif is_santa:
        # Пользователь - Санта, проверяем ответы от своего получателя
        receiver_id = int(pairs_data["pairs"][str(uid)])
        chat_key = f"{min(uid, receiver_id)}_{max(uid, receiver_id)}"
        
        if chat_key in pairs_data.get("chats", {}):
            for msg_data in reversed(pairs_data["chats"][chat_key]):
                if msg_data["type"] == "answer" and msg_data["from"] == receiver_id:
                    receiver_name = data["users"][str(receiver_id)]["name"]
                    
                    await msg.answer(
                        f"💌 <b>Ответ от вашего получателя</b> {receiver_name}:\n\n"
                        f"💬 <b>Ответ:</b>\n{msg_data['message']}"
                    )
                    has_unanswered = True
                    break
    
    if not has_unanswered:
        if receiver_for:
            await msg.answer("📭 У вас пока нет вопросов для ответа.")
        elif is_santa:
            await msg.answer("📭 У вас пока нет новых ответов от получателя.")
        else:
            await msg.answer("❌ Вы не участвуете в обмене вопросами.")

# Отправка ответа получателя Санте
@dp.message(lambda m: m.from_user.id in user_temp and user_temp[m.from_user.id].get("step") == "send_answer")
async def send_answer(msg: types.Message):
    uid = msg.from_user.id
    temp_data = user_temp[uid]
    questioner_id = temp_data["questioner_id"]
    answer = msg.text
    
    try:
        await bot.send_message(
            questioner_id,
            f"💌 <b>Ответ на ваш вопрос от получателя!</b>\n\n"
            f"💬 <b>Ответ:</b>\n{answer}"
        )
        
        pairs_data = load_pairs()
        chat_key = f"{min(uid, questioner_id)}_{max(uid, questioner_id)}"
        
        if chat_key not in pairs_data["chats"]:
            pairs_data["chats"][chat_key] = []
        
        pairs_data["chats"][chat_key].append({
            "from": uid,
            "to": questioner_id,
            "message": answer,
            "type": "answer",
            "time": str(asyncio.get_event_loop().time())
        })
        save_pairs(pairs_data)
        
        # Очищаем ожидающий вопрос если есть
        if uid in user_temp and "waiting_answer_from" in user_temp[uid]:
            del user_temp[uid]["waiting_answer_from"]
            if not user_temp[uid]:
                del user_temp[uid]
        
        del user_temp[uid]
        data = load_data()
        kb = get_main_keyboard(uid, data)
        await msg.answer("✅ Ваш ответ отправлен анонимно!", reply_markup=kb)
        
    except Exception as e:
        await msg.answer(f"❌ Не удалось отправить ответ: {str(e)}")

# ----------------------- СПИСОК УЧАСТНИКОВ -----------------------
@dp.message(F.text == "👥 Список участников")
async def list_users(msg: types.Message):
    data = load_data()
    if msg.from_user.id != data.get("creator"):
        return await msg.answer("❌ Это доступно только создателю")

    users = data.get("users", {})
    if not users:
        return await msg.answer("📭 Пока никто не зарегистрировался.")

    text = "👥 <b>Участники Тайного Санты:</b>\n\n"
    for u in users.values():
        text += f"🎅 <b>{u['name']}</b>\n"
        if "wishlist_items" in u:
            text += f"   🎁 Подарков в вишлисте: {len(u['wishlist_items'])}\n"
        text += "\n"

    await msg.answer(text)

# ----------------------- ЖЕРЕБЬЁВКА -----------------------
@dp.message(F.text == "🎲 Запустить жеребьёвку")
async def draw(msg: types.Message):
    data = load_data()
    if msg.from_user.id != data.get("creator"):
        return await msg.answer("❌ Только создатель может запускать жеребьёвку.")

    users = data.get("users", {})
    if len(users) < 2:
        return await msg.answer("👥 Нужно минимум 2 участника.")

    ids = list(users.keys())
    shuffled = ids.copy()

    for _ in range(10000):
        random.shuffle(shuffled)
        if all(shuffled[i] != ids[i] for i in range(len(ids))):
            break
    
    pairs_data = load_pairs()
    pairs_data["pairs"] = {}
    
    for giver, receiver in zip(ids, shuffled):
        pairs_data["pairs"][giver] = receiver
    
    save_pairs(pairs_data)

    for giver, receiver in zip(ids, shuffled):
        try:
            g = int(giver)
            r = users[receiver]
            
            text = f"🎅✨ <b>ВАШ ПОЛУЧАТЕЛЬ:</b> {r['name']} ✨\n\n"
            text += f"💭 <b>Хочет получить:</b>\n{r['wish']}\n\n"
            text += f"🚫 <b>Не хочет получать:</b>\n{r['antis']}\n\n"
            
            if "wishlist_items" in r and r["wishlist_items"]:
                text += "🎁 <b>Конкретные предложения:</b>\n"
                for i, item in enumerate(r["wishlist_items"], 1):
                    text += f"\n{i}. <b>{item['name']}</b>\n"
                    text += f"   💰 Цена: {item['price']}\n"
                    text += f'   🔗 <a href="{item["link"]}">Ссылка на подарок</a>\n'
            
            text += "\n\n💌 <b>Хотите что-то уточнить у получателя?</b>\n"
            text += "Используйте кнопку '💌 Спросить получателя' для общения!"
            
            kb = get_main_keyboard(g, data)
            
            await bot.send_message(g, text, reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            print(f"Ошибка отправки: {e}")

    await msg.answer("✅ <b>Жеребьёвка завершена!</b>\n\nВсе участники получили свои пары и могут общаться анонимно! 🎉")

# ----------------------- ЗАПУСК -----------------------
async def main():
    print("🎅 Бот Тайный Санта запускается...")
    print("✨ Сделано с любовью Машулькой и Федюком ✨")
    
    try:
        me = await bot.get_me()
        print(f"✅ Бот подключен: @{me.username}")
        print("📱 Напишите /start в Telegram")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
