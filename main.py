from telethon import TelegramClient, events, Button
from telethon.tl.types import Message, KeyboardButton, ChatAdminRights
from telethon.tl.functions.messages import CreateChatRequest, AddChatUserRequest, EditChatAdminRequest
from telethon.tl.functions.channels import EditAdminRequest
from telethon.errors import SessionPasswordNeededError, UserAlreadyParticipantError
import asyncio
import re
import time
import os

# ===== СОЗДАНИЕ ПАПКИ ДЛЯ СЕССИЙ =====
SESSION_DIR = "sessions"
if not os.path.exists(SESSION_DIR):
    os.makedirs(SESSION_DIR)
    print(f"📁 Создана папка для сессий: {SESSION_DIR}")

# ===== КОНФИГ =====
BOT_TOKEN = "8982270945:AAHWQUkaezlyPONPuJOWUtDNu63fcx3yvqU"
API_ID = 25569323
API_HASH = "061bad708728d3d928054f16c932de6d"

# Список боссов (порядок = порядок кнопок в боте)
BOSSES = [
    {"emoji": "🧚", "name": "Лесная Фея"},
    {"emoji": "🧌", "name": "Гоблин"},
    {"emoji": "🦌", "name": "Дух Рощи"},
    {"emoji": "🫎", "name": "Лесной Владыка"},
    {"emoji": "🧛‍♀️", "name": "Ночной Вампир"},
    {"emoji": "💀", "name": "Костяной Лорд"},
    {"emoji": "☠️", "name": "Король Некромантов"},
    {"emoji": "👑", "name": "Лич"},
    {"emoji": "🐦‍🔥", "name": "Солнечный Феникс"},
    {"emoji": "🌋", "name": "Лавовый Голем"},
    {"emoji": "👺", "name": "Тэнгу"},
    {"emoji": "👹", "name": "Демон"},
    {"emoji": "🤖", "name": "Автоматон"},
    {"emoji": "🐸", "name": "Меха Жаба"},
    {"emoji": "🦂", "name": "Меха Скорпион"},
    {"emoji": "🐛", "name": "Меха Червь"},
    {"emoji": "❄️", "name": "Ледяной Элементаль"},
    {"emoji": "👻", "name": "Призрак"},
    {"emoji": "🌩", "name": "Громовой Страж"},
    {"emoji": "🧊", "name": "Морозный Голем"},
    {"emoji": "🐊", "name": "Крокодил"},
    {"emoji": "🐲", "name": "Дракон"},
    {"emoji": "🐢", "name": "Черепаха"},
    {"emoji": "🦕", "name": "Зауропод"},
    {"emoji": "🐙", "name": "Кракен"},
    {"emoji": "🦈", "name": "Глубинная Акула"},
    {"emoji": "🐳", "name": "Кит"},
    {"emoji": "🦀", "name": "Король Рифов"}
]

# Путь к сессии бота
BOT_SESSION_PATH = os.path.join(SESSION_DIR, 'bot_session')

# Клиент бота
bot_client = TelegramClient(BOT_SESSION_PATH, API_ID, API_HASH)

# Переменные
user_client = None
is_active = False
selected_bosses = set()
chat_id = None
chat_created = False
bot_username = "IsekaiGlobal_bot"
last_equip_time = 0
is_equip_mode = False

# Текущий атакуемый босс (индекс) или None
current_target = None

# Статус авторизации
auth_states = {}
user_codes = {}

# Для авто-переподключения
reconnect_attempts = 0
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = 30  # секунд между попытками
last_activity_check = 0
ACTIVITY_CHECK_INTERVAL = 60  # проверка каждую минуту

# ===== КЛАВИАТУРЫ =====
def get_main_keyboard():
    global is_active
    toggle_text = "❌ ВЫКЛЮЧИТЬ" if is_active else "✅ ВКЛЮЧИТЬ"
    return [
        [KeyboardButton(toggle_text)],
        [KeyboardButton("🎯 ВЫБРАТЬ БОССОВ")],
        [KeyboardButton("📊 СТАТУС БОССОВ"), KeyboardButton("🔄 ОБНОВИТЬ")]
    ]

def get_bosses_keyboard():
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
    return [
        [KeyboardButton("1️⃣"), KeyboardButton("2️⃣"), KeyboardButton("3️⃣")],
        [KeyboardButton("4️⃣"), KeyboardButton("5️⃣"), KeyboardButton("6️⃣")],
        [KeyboardButton("7️⃣"), KeyboardButton("8️⃣"), KeyboardButton("9️⃣")],
        [KeyboardButton("🔙"), KeyboardButton("0️⃣"), KeyboardButton("✅ ГОТОВО")]
    ]

# ===== ОБРАБОТЧИК СООБЩЕНИЙ =====
@bot_client.on(events.NewMessage)
async def handle_message(event):
    if event.is_private:
        user_id = event.sender_id
        text = event.raw_text
        
        if text == '/start':
            await start_auth(event, user_id)
            return
        
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
    auth_states[user_id] = {'step': 'phone'}
    user_codes[user_id] = ""
    
    await event.respond(
        "🔐 **Добро пожаловать в охотника на боссов!**\n\n"
        "Для начала работы нужно авторизоваться.\n"
        "📱 **Отправь свой номер телефона** в формате:\n"
        "`+79991234567`",
        buttons=Button.clear()
    )

async def handle_phone(event, user_id, phone):
    phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    if not phone.startswith('+'):
        await event.respond("❌ Неверный формат! Номер должен начинаться с `+`\nПример: `+79991234567`")
        return
    
    try:
        session_name = f'user_{phone.replace("+", "")}'
        session_path = os.path.join(SESSION_DIR, session_name)
        client = TelegramClient(session_path, API_ID, API_HASH)
        await client.connect()
        await client.send_code_request(phone)
        
        auth_states[user_id] = {
            'step': 'code',
            'phone': phone,
            'client': client,
            'session_name': session_name
        }
        user_codes[user_id] = ""
        
        await event.respond(
            f"✅ Код подтверждения отправлен на номер `{phone}`!\n\n"
            f"✏️ **Введи код**, используя кнопки ниже:",
            buttons=get_code_keyboard()
        )
        
    except Exception as e:
        await event.respond(f"❌ Ошибка: {str(e)}\nПопробуй ещё раз отправить номер.")

async def handle_code_input(event, user_id, text):
    global user_codes
    
    if text == "✅ ГОТОВО":
        code = user_codes.get(user_id, "")
        if len(code) < 3:
            await event.respond("❌ Код должен содержать минимум 3 цифры!", buttons=get_code_keyboard())
            return
        
        await handle_code(event, user_id, code)
        return
    
    if text == "🔙":
        user_codes[user_id] = user_codes.get(user_id, "")[:-1]
        current_code = user_codes.get(user_id, "")
        await event.respond(
            f"✏️ **Введи код:**\n`{current_code}`",
            buttons=get_code_keyboard()
        )
        return
    
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
    global user_client, chat_id, chat_created, reconnect_attempts, last_activity_check
    
    user_client = client
    me = await client.get_me()
    
    auth_states[user_id] = {
        'step': 'done',
        'phone': auth_states[user_id]['phone']
    }
    
    # Сбрасываем счётчик попыток и время проверки
    reconnect_attempts = 0
    last_activity_check = time.time()
    
    await event.respond(
        f"✅ **Успешный вход!** \n\n"
        f"👤 Аккаунт: {me.first_name} {me.last_name or ''}\n"
        f"📱 Номер: {auth_states[user_id]['phone']}\n"
        f"🆔 ID: {me.id}\n\n"
        f"🎮 **Открываю меню управления...**",
        buttons=get_main_keyboard()
    )
    
    chat_created = await create_or_get_chat(client)
    if chat_created:
        await event.respond("✅ Чат успешно создан и настроен!")
    else:
        await event.respond("ℹ️ Чат уже существует, подключаюсь...")
    
    # Запускаем основной цикл, если ещё не запущен
    asyncio.create_task(main_loop())

# ===== СОЗДАНИЕ ЧАТА =====
async def create_or_get_chat(client):
    global chat_id, chat_created
    
    me = await client.get_me()
    username = me.username or me.first_name
    chat_name = f"МБЛ ({username})"
    
    async for dialog in client.iter_dialogs():
        if dialog.name == chat_name:
            chat_id = dialog.id
            print(f"✅ Найден существующий чат: {chat_name}")
            
            try:
                bot_entity = await client.get_entity(bot_username)
                await client(AddChatUserRequest(
                    chat_id=chat_id,
                    user_id=bot_entity,
                    fwd_limit=0
                ))
            except UserAlreadyParticipantError:
                pass
            except Exception as e:
                print(f"⚠️ Ошибка: {e}")
            
            await give_admin_rights(client, chat_id)
            return True
    
    try:
        result = await client(CreateChatRequest(
            users=[bot_username],
            title=chat_name
        ))
        
        chat = result.chats[0]
        chat_id = chat.id
        print(f"✅ Чат создан: {chat_name}")
        
        await give_admin_rights(client, chat_id)
        await client.send_message(chat_id, "🤖 Бот для мониторинга боссов активирован!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

async def give_admin_rights(client, chat_id):
    try:
        bot_entity = await client.get_entity(bot_username)
        
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
        
        await client(EditChatAdminRequest(
            chat_id=chat_id,
            user_id=bot_entity,
            rights=admin_rights,
            is_admin=True
        ))
        
        print(f"✅ {bot_username} получил права администратора")
        
    except Exception as e:
        print(f"⚠️ Ошибка: {e}")

# ===== ФУНКЦИЯ ПРОВЕРКИ АКТИВНОСТИ =====
async def check_user_activity():
    """Проверяет активность пользовательского аккаунта"""
    global user_client, reconnect_attempts
    
    if not user_client:
        return False
    
    try:
        # Пытаемся получить информацию о себе - если ошибка, значит сессия неактивна
        await user_client.get_me()
        reconnect_attempts = 0  # Сброс попыток при успехе
        return True
    except Exception as e:
        print(f"⚠️ Ошибка проверки активности: {e}")
        return False

# ===== ФУНКЦИЯ ПЕРЕПОДКЛЮЧЕНИЯ =====
async def reconnect_user():
    """Переподключает пользовательский аккаунт с сохранённой сессией"""
    global user_client, reconnect_attempts, is_active, current_target, chat_created
    
    if not user_client:
        print("❌ Нет клиента для переподключения")
        return False
    
    try:
        print(f"🔄 Попытка переподключения #{reconnect_attempts + 1}...")
        
        # Отключаем текущий клиент если он есть
        if user_client.is_connected():
            await user_client.disconnect()
            await asyncio.sleep(2)
        
        # Переподключаемся с той же сессией
        await user_client.connect()
        
        # Проверяем что сессия работает
        me = await user_client.get_me()
        print(f"✅ Успешное переподключение! Аккаунт: {me.first_name}")
        
        # Сбрасываем флаги ошибок
        reconnect_attempts = 0
        
        # Если бот был активен - продолжаем работу
        if is_active:
            print("🔄 Восстанавливаем активный режим...")
            # Пересоздаём чат если нужно
            if not chat_created:
                chat_created = await create_or_get_chat(user_client)
                if chat_created:
                    print("✅ Чат восстановлен!")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка переподключения: {e}")
        reconnect_attempts += 1
        
        # Если слишком много ошибок - отключаем бота
        if reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
            print("🔴 Слишком много ошибок подключения!")
            is_active = False
            current_target = None
            await notify_user_about_disconnect()
            reconnect_attempts = 0
        
        return False

# ===== ФУНКЦИЯ УВЕДОМЛЕНИЯ =====
async def notify_user_about_disconnect():
    """Уведомляет пользователя об отключении бота"""
    try:
        # Ищем пользователя в auth_states
        for user_id, state in auth_states.items():
            if state.get('step') == 'done':
                await bot_client.send_message(
                    user_id,
                    "⚠️ **Бот был автоматически отключён!**\n\n"
                    "Причина: слишком много ошибок подключения к аккаунту.\n"
                    "Пожалуйста, перезапустите бота командой `/start` и авторизуйтесь заново."
                )
                break
    except Exception as e:
        print(f"⚠️ Не удалось уведомить пользователя: {e}")

# ===== ФУНКЦИЯ ЭКИПИРОВКИ =====
async def do_equip():
    """Выполняет экипировку: пишет 'экип', нажимает 8-ю кнопку (слоты), затем 6-ю"""
    global user_client, is_equip_mode
    
    try:
        print("🔄 Начинаю экипировку...")
        is_equip_mode = True
        
        await user_client.send_message(bot_username, "экип")
        print("✏️ Отправил 'экип'")
        await asyncio.sleep(1)  # Изменено: 2 → 1 секунда
        
        messages = await user_client.get_messages(bot_username, limit=2)
        if not messages:
            print("❌ Нет сообщений от бота")
            is_equip_mode = False
            return
        
        for msg in messages:
            if msg.buttons:
                flat_buttons = [btn for row in msg.buttons for btn in row]
                
                if len(flat_buttons) >= 8:
                    await asyncio.sleep(1)  # Изменено: 2 → 1 секунда
                    await msg.click(7)
                    print("✅ Нажата 8-я кнопка (Слоты)")
                    await asyncio.sleep(1)  # Изменено: 2 → 1 секунда
                    
                    new_messages = await user_client.get_messages(bot_username, limit=2)
                    if new_messages:
                        for new_msg in new_messages:
                            if new_msg.buttons:
                                new_buttons = [btn for row in new_msg.buttons for btn in row]
                                
                                if len(new_buttons) >= 6:
                                    await asyncio.sleep(1)  # Изменено: 2 → 1 секунда
                                    await new_msg.click(5)
                                    print("✅ Нажата 6-я кнопка")
                                    await asyncio.sleep(1)  # Изменено: 2 → 1 секунда
                                    break
                    break
        
        print("✅ Экипировка завершена!")
        is_equip_mode = False
        
    except Exception as e:
        print(f"❌ Ошибка экипировки: {e}")
        is_equip_mode = False

# ===== МОНИТОРИНГ БОССОВ =====
async def check_bosses():
    global is_active, selected_bosses, chat_id, user_client, chat_created, last_equip_time, is_equip_mode, current_target, reconnect_attempts, last_activity_check
    
    if not user_client:
        print("⚠️ Нет подключения к аккаунту")
        return
    
    # Проверка активности аккаунта
    current_time = time.time()
    if current_time - last_activity_check >= ACTIVITY_CHECK_INTERVAL:
        last_activity_check = current_time
        
        if not await check_user_activity():
            print("⚠️ Аккаунт неактивен, пытаюсь переподключиться...")
            
            # Пытаемся переподключиться
            if await reconnect_user():
                print("✅ Аккаунт восстановлен!")
            else:
                print(f"❌ Не удалось переподключиться ({reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS})")
                return
    
    if not is_active or not selected_bosses or not chat_created:
        return
    
    current_time = time.time()
    if current_time - last_equip_time >= 1200:
        print("⏰ Пора делать экипировку!")
        await do_equip()
        last_equip_time = current_time
        print("⏳ Жду 1 минуту после экипировки...")
        await asyncio.sleep(60)  # Изменено: 10 → 60 секунд
        return
    
    if is_equip_mode:
        return
    
    try:
        # 1. Пишем "бл" в чат
        await user_client.send_message(chat_id, "бл")
        await asyncio.sleep(2)
        
        # 2. Получаем последние сообщения
        messages = await user_client.get_messages(chat_id, limit=10)
        
        # 3. Ищем сообщение от IsekaiGlobal_bot
        boss_message = None
        bot_entity = await user_client.get_entity(bot_username)
        for msg in messages:
            if msg.sender_id == bot_entity.id:
                boss_message = msg.text
                break
        
        if not boss_message:
            print("⚠️ Сообщение с боссами не найдено")
            return
        
        # 4. Если есть текущая цель — проверяем её статус
        if current_target is not None:
            boss = BOSSES[current_target]
            pattern = rf"{boss['emoji']}.*{boss['name']}.*(Жив!|\d+[мс. ]+\d*[мс.]*)"
            match = re.search(pattern, boss_message)
            
            if match:
                status = match.group(1)
                is_alive = status == "Жив!"
                
                if is_alive:
                    # Босс ещё жив → ждём
                    print(f"⏳ {boss['name']} ещё жив ({status}), жду смерти...")
                    return
                else:
                    # Босс умер → разблокируем
                    print(f"💀 {boss['name']} умер! Разблокирован для новой атаки!")
                    current_target = None
                    return
            else:
                # Не нашли босса в сообщении (может быть ошибка)
                print(f"⚠️ Не найден статус для {boss['name']}, разблокирую...")
                current_target = None
                return
        
        # 5. Нет текущей цели — ищем живого босса для атаки
        alive_bosses = []
        for index in selected_bosses:
            boss = BOSSES[index]
            pattern = rf"{boss['emoji']}.*{boss['name']}.*(Жив!|\d+[мс. ]+\d*[мс.]*)"
            match = re.search(pattern, boss_message)
            
            if match:
                status = match.group(1)
                if status == "Жив!":
                    alive_bosses.append(index)
                    print(f"🔥 {boss['name']} жив!")
        
        # 6. Если есть живые боссы — атакуем первого
        if alive_bosses:
            boss_index = alive_bosses[0]
            boss = BOSSES[boss_index]
            
            print(f"⚔️ Атакую {boss['name']}...")
            success = await attack_boss(boss_index)
            
            if success:
                current_target = boss_index
                print(f"✅ {boss['name']} атакован! Блокирую всех боссов до его смерти...")
            else:
                print(f"❌ Не удалось атаковать {boss['name']}")
        else:
            print("⏳ Нет живых боссов из выбранных")
        
    except Exception as e:
        print(f"Ошибка в check_bosses: {e}")

# ===== АТАКА БОССА =====
async def attack_boss(boss_index):
    """Атакует босса по индексу (1-я кнопка = 1-й босс)"""
    global user_client
    
    try:
        # 1. Пишем "бо" в бота
        await user_client.send_message(bot_username, "бо")
        await asyncio.sleep(2)
        
        # 2. Получаем сообщение с кнопками
        messages = await user_client.get_messages(bot_username, limit=2)
        if not messages:
            print("❌ Нет сообщений от бота")
            return False
        
        # 3. Ищем кнопку по индексу босса
        for msg in messages:
            if msg.buttons:
                flat_buttons = [btn for row in msg.buttons for btn in row]
                
                if boss_index < len(flat_buttons):
                    await msg.click(boss_index)
                    print(f"✅ Нажата кнопка {boss_index + 1}: {flat_buttons[boss_index].text}")
                    
                    # 4. После нажатия кнопки отправляем "ав+" в бота
                    await asyncio.sleep(1)
                    await user_client.send_message(bot_username, "ав+")
                    print(f"✅ Отправлено 'ав+' в бота")
                    
                    return True
                else:
                    print(f"❌ Кнопка с индексом {boss_index} не найдена (всего {len(flat_buttons)})")
                    return False
        
        print("❌ Кнопки не найдены")
        return False
        
    except Exception as e:
        print(f"Ошибка атаки: {e}")
        return False

# ===== ОСНОВНОЙ ЦИКЛ =====
async def main_loop():
    """Главный цикл с проверкой подключения"""
    global is_active
    
    while True:
        try:
            await check_bosses()
            
            # Если бот активен, но нет подключения - пробуем восстановить
            if is_active and user_client:
                if not user_client.is_connected():
                    print("⚠️ Потеряно соединение, пытаюсь восстановить...")
                    await reconnect_user()
                    
                    # Если восстановились - проверяем чат
                    if user_client and user_client.is_connected():
                        await create_or_get_chat(user_client)
            
            await asyncio.sleep(20)
            
        except Exception as e:
            print(f"❌ Ошибка в главном цикле: {e}")
            await asyncio.sleep(30)  # Ждём 30 секунд перед следующей попыткой

# ===== ОБРАБОТКА КОМАНД =====
async def handle_main_commands(event, text):
    global is_active, selected_bosses, chat_id, user_client, chat_created, current_target
    
    if text in ["✅ ВКЛЮЧИТЬ", "❌ ВЫКЛЮЧИТЬ"]:
        is_active = not is_active
        status = "🟢 ВКЛЮЧЕН" if is_active else "🔴 ВЫКЛЮЧЕН"
        if not is_active:
            # При выключении сбрасываем цель
            current_target = None
        await event.respond(
            f"📊 Статус: {status}\n"
            f"🎯 Выбрано боссов: {len(selected_bosses)}",
            buttons=get_main_keyboard()
        )
    
    elif text == "🎯 ВЫБРАТЬ БОССОВ":
        await event.respond(
            "🎯 **Выбери боссов для охоты:**\n"
            "✅ - выбран, ⬜ - не выбран",
            buttons=get_bosses_keyboard()
        )
    
    elif text == "📊 СТАТУС БОССОВ":
        chat_status = "✅ Создан" if chat_created else "❌ Не создан"
        target_name = BOSSES[current_target]['name'] if current_target is not None else "Нет"
        await event.respond(
            f"📊 **Текущий статус:**\n"
            f"🟢 Бот: {'ВКЛЮЧЕН' if is_active else 'ВЫКЛЮЧЕН'}\n"
            f"🎯 Выбрано боссов: {len(selected_bosses)}\n"
            f"⚔️ Атакуется: {target_name}\n"
            f"📁 Чат: {chat_status}"
        )
    
    elif text == "🔄 ОБНОВИТЬ":
        await event.respond("🔄 Обновляю статус...")
        await check_bosses()
        await event.respond("✅ Готово! Проверь чат МБЛ")
    
    elif text == "🔙 НАЗАД":
        await event.respond("🔙 Возвращаюсь в главное меню", buttons=get_main_keyboard())
    
    elif any(emoji in text for emoji in ["✅", "⬜"]):
        for i, boss in enumerate(BOSSES):
            if boss['emoji'] in text:
                if i in selected_bosses:
                    selected_bosses.remove(i)
                    # Если босс убран из выбора и он был целью — сбрасываем
                    if current_target == i:
                        current_target = None
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
    print(f"📁 Сессии сохраняются в папку: {SESSION_DIR}")
    await bot_client.start(bot_token=BOT_TOKEN)
    print("✅ Бот запущен! Жду авторизации...")
    
    await bot_client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())