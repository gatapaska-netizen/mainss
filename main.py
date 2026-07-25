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

# Имя бота IsekaiGlobal_bot
BOT_USERNAME = "IsekaiGlobal_bot"
BOT_ID = None  # Будет получен при запуске

# Список боссов (порядок = порядок кнопок в боте)
BOSSES = [
    {"emoji": "🧚", "name": "Лесная Фея", "critical_health": 20},
    {"emoji": "🧌", "name": "Гоблин", "critical_health": 20},
    {"emoji": "🦌", "name": "Дух Рощи", "critical_health": 20},
    {"emoji": "🫎", "name": "Лесной Владыка", "critical_health": 20},
    {"emoji": "🧛‍♀️", "name": "Ночной Вампир", "critical_health": 30},
    {"emoji": "💀", "name": "Костяной Лорд", "critical_health": 30},
    {"emoji": "☠️", "name": "Король Некромантов", "critical_health": 30},
    {"emoji": "👑", "name": "Лич", "critical_health": 30},
    {"emoji": "🐦‍🔥", "name": "Солнечный Феникс", "critical_health": 40},
    {"emoji": "🌋", "name": "Лавовый Голем", "critical_health": 40},
    {"emoji": "👺", "name": "Тэнгу", "critical_health": 40},
    {"emoji": "👹", "name": "Демон", "critical_health": 40},
    {"emoji": "🤖", "name": "Автоматон", "critical_health": 60},
    {"emoji": "🐸", "name": "Меха Жаба", "critical_health": 60},
    {"emoji": "🦂", "name": "Меха Скорпион", "critical_health": 60},
    {"emoji": "🐛", "name": "Меха Червь", "critical_health": 60},
    {"emoji": "❄️", "name": "Ледяной Элементаль", "critical_health": 60},
    {"emoji": "👻", "name": "Призрак", "critical_health": 60},
    {"emoji": "🌩", "name": "Громовой Страж", "critical_health": 60},
    {"emoji": "🧊", "name": "Морозный Голем", "critical_health": 60},
    {"emoji": "🐊", "name": "Крокодил", "critical_health": 60},
    {"emoji": "🐲", "name": "Дракон", "critical_health": 60},
    {"emoji": "🐢", "name": "Черепаха", "critical_health": 60},
    {"emoji": "🦕", "name": "Зауропод", "critical_health": 60},
    {"emoji": "🐙", "name": "Кракен", "critical_health": 60},
    {"emoji": "🦈", "name": "Глубинная Акула", "critical_health": 60},
    {"emoji": "🐳", "name": "Кит", "critical_health": 60},
    {"emoji": "🦀", "name": "Король Рифов", "critical_health": 60}
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
last_equip_time = 0
is_equip_mode = False
current_target = None

# Статус авторизации
auth_states = {}
user_codes = {}

# Для авто-переподключения
reconnect_attempts = 0
MAX_RECONNECT_ATTEMPTS = 5
last_activity_check = 0
ACTIVITY_CHECK_INTERVAL = 60

# Для DM-автоатаки
dm_attack_running = False
dm_attack_task = None
dm_battle_msg_id = None
heal_mode = False
clicked_after_boss = set()  # Для отслеживания уже обработанных побед

# ===== ФУНКЦИЯ ПОЛУЧЕНИЯ ID БОТА =====
async def get_bot_id():
    global BOT_ID, user_client
    if not user_client:
        return None
    try:
        bot_entity = await user_client.get_entity(BOT_USERNAME)
        BOT_ID = bot_entity.id
        print(f"✅ Найден бот @{BOT_USERNAME} с ID: {BOT_ID}")
        return BOT_ID
    except Exception as e:
        print(f"❌ Ошибка получения ID бота: {e}")
        return None

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

# ===== ОБРАБОТЧИК НОВЫХ СООБЩЕНИЙ =====
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

# ===== ОБРАБОТЧИК ИЗМЕНЕНИЙ СООБЩЕНИЙ (ВАЖНО!) =====
@bot_client.on(events.MessageEdited)
async def handle_edited_message(event):
    """Обрабатывает изменения сообщений (как в модуле)"""
    try:
        # Проверяем, что это сообщение от бота в ЛС
        if not event.message or not event.message.text:
            return
        
        # Если DM-атака запущена и это сообщение от IsekaiGlobal_bot
        if dm_attack_running and event.message.chat_id == BOT_ID:
            await process_battle_message(event.message)
        
        # Также обрабатываем победу в ЛС
        if event.message.chat_id == BOT_ID and is_victory(event.message.text):
            await process_victory(event.message)
            
    except Exception as e:
        print(f"⚠️ Ошибка в обработчике изменений: {e}")

# ===== ОБРАБОТЧИК СООБЩЕНИЙ ОТ БОТА (КАК WATCHER В МОДУЛЕ) =====
@bot_client.on(events.NewMessage)
async def watcher(event):
    """Отслеживает новые сообщения от бота (как watcher в модуле)"""
    try:
        if not event.message or not event.message.text:
            return
        
        # Если DM-атака запущена и это сообщение от IsekaiGlobal_bot
        if dm_attack_running and event.message.chat_id == BOT_ID:
            await process_battle_message(event.message)
        
        # Обработка победы
        if event.message.chat_id == BOT_ID and is_victory(event.message.text):
            await process_victory(event.message)
            
    except Exception as e:
        print(f"⚠️ Ошибка в watcher: {e}")

# ===== ОБРАБОТКА СООБЩЕНИЯ БОЯ =====
async def process_battle_message(message):
    """Обрабатывает сообщение с боем (как в модуле)"""
    global dm_attack_running, dm_battle_msg_id, heal_mode, current_target
    
    if not message or not message.text:
        return
    
    try:
        # Парсим данные боя
        battle_data = parse_all_battle_data(message.text)
        if not battle_data or not battle_data['has_battle']:
            return
        
        # Если нет кнопок - выходим
        if not message.buttons:
            return
        
        # Проверяем критическое здоровье
        if current_target is not None and battle_data['player_health'] is not None:
            is_critical, critical_health = check_critical_health(battle_data['player_health'], current_target)
            
            if is_critical and not heal_mode:
                print(f"⚠️ КРИТИЧЕСКОЕ ЗДОРОВЬЕ! {battle_data['player_health']:.0f} < {critical_health}")
                heal_mode = True
            elif not is_critical and heal_mode:
                print(f"✅ Здоровье восстановлено! {battle_data['player_health']:.0f} >= {critical_health}")
                heal_mode = False
        
        # Выводим статус
        status_text = format_battle_status(battle_data)
        if status_text:
            print(f"\n📊 {status_text}")
        
        # Нажимаем кнопку
        await click_battle_button(message)
        
    except Exception as e:
        print(f"⚠️ Ошибка обработки боя: {e}")

# ===== НАЖАТИЕ КНОПКИ В БОЮ =====
async def click_battle_button(message):
    """Нажимает нужную кнопку в бою (атака или лечение)"""
    global dm_attack_running, dm_battle_msg_id, heal_mode
    
    if not message or not message.buttons:
        return
    
    try:
        found_action = False
        
        if heal_mode:
            # Ищем кнопку "Обновить"
            for row in message.buttons:
                for btn in row:
                    if "Обновить" in btn.text or "🟢" in btn.text:
                        await message.click(btn)
                        print("🔄 Нажата кнопка ОБНОВИТЬ (лечение)")
                        found_action = True
                        break
                if found_action:
                    break
        else:
            # Ищем кнопку "Атаковать"
            attack_found = False
            for row in message.buttons:
                for btn in row:
                    if "Атаковать" in btn.text or "✘" in btn.text:
                        await message.click(btn)
                        print(f"⚔️ Нажата кнопка АТАКОВАТЬ")
                        found_action = True
                        attack_found = True
                        break
                if attack_found:
                    break
            
            # Если не нашли "Атаковать", нажимаем первую кнопку
            if not attack_found:
                try:
                    await message.click(0)
                    print(f"⚔️ Нажата кнопка 0 (атака)")
                    found_action = True
                except Exception as e:
                    print(f"⚠️ Ошибка нажатия: {e}")
        
        if found_action:
            dm_battle_msg_id = message.id
            
    except Exception as e:
        print(f"⚠️ Ошибка нажатия кнопки: {e}")

# ===== ОБРАБОТКА ПОБЕДЫ =====
async def process_victory(message):
    """Обрабатывает победу над боссом"""
    global dm_attack_running, current_target, clicked_after_boss
    
    if not message or not message.text:
        return
    
    msg_id = (message.chat_id, message.id)
    if msg_id in clicked_after_boss:
        return
    
    try:
        print("🏆 БОСС ПОВЕРЖЕН! Забираем награду...")
        if message.buttons:
            await message.click(0)
            clicked_after_boss.add(msg_id)
            
            # Останавливаем DM-атаку
            dm_attack_running = False
            if dm_attack_task and not dm_attack_task.done():
                try:
                    dm_attack_task.cancel()
                except Exception:
                    pass
            
            current_target = None
            heal_mode = False
            dm_battle_msg_id = None
            print("✅ Награда получена! Бот готов к следующей цели")
            
    except Exception as e:
        print(f"⚠️ Ошибка обработки победы: {e}")

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
        await event.respond(f"✏️ **Введи код:**\n`{current_code}`", buttons=get_code_keyboard())
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
        await event.respond(f"✏️ **Введи код:**\n`{current_code}`", buttons=get_code_keyboard())

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
        await event.respond("🔐 **Требуется пароль двухфакторной аутентификации!**\n\n✏️ **Напиши свой пароль:**", buttons=Button.clear())
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
    global user_client, chat_id, chat_created, reconnect_attempts, last_activity_check, BOT_ID
    
    user_client = client
    me = await client.get_me()
    
    auth_states[user_id] = {
        'step': 'done',
        'phone': auth_states[user_id]['phone']
    }
    
    reconnect_attempts = 0
    last_activity_check = time.time()
    
    await get_bot_id()
    
    await event.respond(
        f"✅ **Успешный вход!** \n\n"
        f"👤 Аккаунт: {me.first_name} {me.last_name or ''}\n"
        f"📱 Номер: {auth_states[user_id]['phone']}\n"
        f"🆔 ID: {me.id}\n"
        f"🤖 Бот @{BOT_USERNAME} ID: {BOT_ID}\n\n"
        f"🎮 **Открываю меню управления...**",
        buttons=get_main_keyboard()
    )
    
    chat_created = await create_or_get_chat(client)
    if chat_created:
        await event.respond("✅ Чат успешно создан и настроен!")
    else:
        await event.respond("ℹ️ Чат уже существует, подключаюсь...")
    
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
                bot_entity = await client.get_entity(BOT_USERNAME)
                await client(AddChatUserRequest(chat_id=chat_id, user_id=bot_entity, fwd_limit=0))
            except UserAlreadyParticipantError:
                pass
            except Exception as e:
                print(f"⚠️ Ошибка: {e}")
            await give_admin_rights(client, chat_id)
            return True
    
    try:
        result = await client(CreateChatRequest(users=[BOT_USERNAME], title=chat_name))
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
        bot_entity = await client.get_entity(BOT_USERNAME)
        admin_rights = ChatAdminRights(
            change_info=True, post_messages=True, edit_messages=True,
            delete_messages=True, ban_users=True, invite_users=True,
            pin_messages=True, add_admins=True, anonymous=False,
            manage_call=True, other=True
        )
        await client(EditChatAdminRequest(chat_id=chat_id, user_id=bot_entity, rights=admin_rights, is_admin=True))
        print(f"✅ {BOT_USERNAME} получил права администратора")
    except Exception as e:
        print(f"⚠️ Ошибка: {e}")

# ===== ФУНКЦИЯ ПРОВЕРКИ АКТИВНОСТИ =====
async def check_user_activity():
    global user_client, reconnect_attempts
    if not user_client:
        return False
    try:
        await user_client.get_me()
        reconnect_attempts = 0
        return True
    except Exception as e:
        print(f"⚠️ Ошибка проверки активности: {e}")
        return False

# ===== ФУНКЦИЯ ПЕРЕПОДКЛЮЧЕНИЯ =====
async def reconnect_user():
    global user_client, reconnect_attempts, is_active, current_target, chat_created
    if not user_client:
        return False
    
    try:
        print(f"🔄 Попытка переподключения #{reconnect_attempts + 1}...")
        if user_client.is_connected():
            await user_client.disconnect()
            await asyncio.sleep(2)
        
        await user_client.connect()
        me = await user_client.get_me()
        print(f"✅ Успешное переподключение! Аккаунт: {me.first_name}")
        reconnect_attempts = 0
        
        if is_active:
            if not chat_created:
                chat_created = await create_or_get_chat(user_client)
                if chat_created:
                    print("✅ Чат восстановлен!")
        return True
    except Exception as e:
        print(f"❌ Ошибка переподключения: {e}")
        reconnect_attempts += 1
        if reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
            print("🔴 Слишком много ошибок подключения!")
            is_active = False
            current_target = None
            await notify_user_about_disconnect()
            reconnect_attempts = 0
        return False

async def notify_user_about_disconnect():
    try:
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
    global user_client, is_equip_mode
    try:
        print("🔄 Начинаю экипировку...")
        is_equip_mode = True
        await user_client.send_message(BOT_USERNAME, "экип")
        print("✏️ Отправил 'экип'")
        await asyncio.sleep(1)
        
        messages = await user_client.get_messages(BOT_USERNAME, limit=2)
        if not messages:
            print("❌ Нет сообщений от бота")
            is_equip_mode = False
            return
        
        for msg in messages:
            if msg.buttons:
                flat_buttons = [btn for row in msg.buttons for btn in row]
                if len(flat_buttons) >= 8:
                    await asyncio.sleep(1)
                    await msg.click(7)
                    print("✅ Нажата 8-я кнопка (Слоты)")
                    await asyncio.sleep(1)
                    new_messages = await user_client.get_messages(BOT_USERNAME, limit=2)
                    if new_messages:
                        for new_msg in new_messages:
                            if new_msg.buttons:
                                new_buttons = [btn for row in new_msg.buttons for btn in row]
                                if len(new_buttons) >= 6:
                                    await asyncio.sleep(1)
                                    await new_msg.click(5)
                                    print("✅ Нажата 6-я кнопка")
                                    await asyncio.sleep(1)
                                    break
                    break
        
        print("✅ Экипировка завершена!")
        is_equip_mode = False
    except Exception as e:
        print(f"❌ Ошибка экипировки: {e}")
        is_equip_mode = False

# ===== ФУНКЦИИ ПАРСИНГА =====
def parse_player_health(message_text):
    try:
        patterns = [
            r'❤️\s*Ты\s*:\s*([\d,]+\.?\d*[K]?)\s*/\s*[\d,]+\.?\d*[K]?\s*ОЗ',
            r'❤️\s*Ты\s*([\d,]+\.?\d*[K]?)\s*/\s*[\d,]+\.?\d*[K]?\s*ОЗ',
            r'Ты\s*:\s*([\d,]+\.?\d*[K]?)\s*/\s*[\d,]+\.?\d*[K]?\s*ОЗ',
        ]
        for pattern in patterns:
            match = re.search(pattern, message_text, re.IGNORECASE | re.MULTILINE)
            if match:
                health_str = match.group(1).replace(',', '')
                if 'K' in health_str.upper():
                    health_str = health_str.upper().replace('K', '')
                    return float(health_str) * 1000
                return float(health_str)
        return None
    except Exception:
        return None

def parse_boss_health(message_text):
    try:
        patterns = [
            r'❤️\s*Босс\s*:\s*([\d,]+\.?\d*[K]?)\s*/\s*[\d,]+\.?\d*[K]?\s*ОЗ',
            r'❤️\s*Босс\s*([\d,]+\.?\d*[K]?)\s*/\s*[\d,]+\.?\d*[K]?\s*ОЗ',
            r'Босс\s*:\s*([\d,]+\.?\d*[K]?)\s*/\s*[\d,]+\.?\d*[K]?\s*ОЗ',
        ]
        for pattern in patterns:
            match = re.search(pattern, message_text, re.IGNORECASE | re.MULTILINE)
            if match:
                health_str = match.group(1).replace(',', '')
                if 'K' in health_str.upper():
                    health_str = health_str.upper().replace('K', '')
                    return float(health_str) * 1000
                return float(health_str)
        return None
    except Exception:
        return None

def parse_boss_name(message_text):
    try:
        lines = message_text.strip().split('\n')
        if lines:
            first_line = lines[0].strip()
            if first_line and not any(emoji in first_line for emoji in ['❤️', '⚔️', '✘', '✔️', '🟢']):
                name = re.sub(r'[^\w\s-]', '', first_line).strip()
                if name and len(name) > 1:
                    return name.lower()
        patterns = [
            r'❤️\s*Босс\s*:\s*([^\n]+)',
            r'✘\s*([^\n]+)\s*промахнулся',
        ]
        for pattern in patterns:
            match = re.search(pattern, message_text, re.IGNORECASE | re.MULTILINE)
            if match:
                name = match.group(1).strip()
                name = re.sub(r'[^\w\s-]', '', name).strip()
                if name and len(name) > 1 and name.lower() not in ['босс', 'ты']:
                    return name.lower()
        return None
    except Exception:
        return None

def parse_damage(message_text):
    try:
        patterns = [
            r'✘\s*Ты бьёшь на\s*✘([\d,]+\.?\d*)\s*урона',
            r'Ты бьёшь на\s*✘([\d,]+\.?\d*)\s*урона',
            r'Ты бьёшь на\s*([\d,]+\.?\d*)\s*урона',
        ]
        for pattern in patterns:
            match = re.search(pattern, message_text, re.IGNORECASE | re.MULTILINE)
            if match:
                return float(match.group(1).replace(',', ''))
        return None
    except Exception:
        return None

def parse_heal(message_text):
    try:
        patterns = [
            r'\+([\d,]+\.?\d*)❤️',
            r'\+([\d,]+\.?\d*)💕',
            r'\(\+([\d,]+\.?\d*)❤️',
        ]
        for pattern in patterns:
            match = re.search(pattern, message_text, re.IGNORECASE | re.MULTILINE)
            if match:
                return float(match.group(1).replace(',', ''))
        return None
    except Exception:
        return None

def parse_weapon_durability(message_text):
    try:
        pattern = r'✔️\s*Прочность оружия:\s*([\d,]+\.?\d*)%'
        match = re.search(pattern, message_text, re.IGNORECASE | re.MULTILINE)
        if match:
            return float(match.group(1))
        return None
    except Exception:
        return None

def detect_boss_health(message_text):
    try:
        text = message_text or ""
        has_boss = re.search(r'❤️\s*Босс\s*:', text, re.IGNORECASE)
        has_you = re.search(r'❤️\s*Ты\s*:', text, re.IGNORECASE)
        return bool(has_boss and has_you)
    except Exception:
        return False

def is_victory(message_text):
    try:
        text = (message_text or "").lower()
        victory_phrases = [
            "босс был повержен",
            "тебе удалось убить",
            "ты победил",
            "поздравляем! ты убил",
            "вы победили",
            "босс побеждён",
            "повержен"
        ]
        return any(phrase in text for phrase in victory_phrases)
    except Exception:
        return False

def is_attack_available(message_text):
    try:
        text = message_text or ""
        has_attack_button = "✘ Атаковать" in text or "Атаковать" in text
        return has_attack_button and not is_victory(text)
    except Exception:
        return False

def parse_all_battle_data(message_text):
    try:
        if not message_text:
            return None
        data = {
            'player_health': parse_player_health(message_text),
            'boss_health': parse_boss_health(message_text),
            'boss_name': parse_boss_name(message_text),
            'damage': parse_damage(message_text),
            'heal': parse_heal(message_text),
            'weapon_durability': parse_weapon_durability(message_text),
            'is_victory': is_victory(message_text),
            'has_battle': detect_boss_health(message_text),
            'can_attack': is_attack_available(message_text)
        }
        return data
    except Exception:
        return None

def format_battle_status(battle_data):
    if not battle_data:
        return "❌ Нет данных"
    lines = []
    if battle_data['boss_name']:
        lines.append(f"👾 Босс: {battle_data['boss_name'].title()}")
    if battle_data['boss_health'] is not None:
        health = battle_data['boss_health']
        lines.append(f"💀 Здоровье босса: {health/1000:.2f}K" if health >= 1000 else f"💀 Здоровье босса: {health:.0f}")
    if battle_data['player_health'] is not None:
        lines.append(f"❤️ Твоё здоровье: {battle_data['player_health']:.0f}")
    if battle_data['damage'] is not None:
        lines.append(f"⚔️ Урон: {battle_data['damage']:.0f}")
    if battle_data['heal'] is not None:
        lines.append(f"💕 Восстановление: +{battle_data['heal']:.0f}")
    if battle_data['weapon_durability'] is not None:
        lines.append(f"🔧 Прочность оружия: {battle_data['weapon_durability']:.0f}%")
    lines.append("✅ Можно атаковать" if battle_data['can_attack'] else "⏳ Ожидание...")
    return "\n".join(lines)

def check_critical_health(player_health, boss_index):
    try:
        boss = BOSSES[boss_index]
        critical_health = boss.get('critical_health', 60)
        return player_health < critical_health, critical_health
    except Exception:
        return False, 60

# ===== ЗАПУСК DM АТАКИ =====
async def start_dm_attack(boss_index):
    global dm_attack_running, dm_attack_task, heal_mode, user_client, BOT_ID, dm_battle_msg_id
    
    if dm_attack_running:
        print("⚠️ DM-атака уже запущена")
        return False
    
    if BOT_ID is None:
        await get_bot_id()
        if BOT_ID is None:
            print("❌ Не удалось получить ID бота!")
            return False
    
    try:
        await user_client.send_message(BOT_ID, "бо")
        print(f"✏️ Отправил 'бо' в ЛС боту @{BOT_USERNAME} (ID: {BOT_ID})")
        await asyncio.sleep(2)
        
        messages = await user_client.get_messages(BOT_ID, limit=3)
        if not messages:
            print("❌ Нет сообщений от бота")
            return False
        
        boss_selected = False
        for msg in messages:
            if msg.buttons:
                flat_buttons = [btn for row in msg.buttons for btn in row]
                if boss_index < len(flat_buttons):
                    await msg.click(boss_index)
                    boss_name = flat_buttons[boss_index].text
                    print(f"✅ Нажата кнопка {boss_index + 1}: {boss_name}")
                    boss_selected = True
                    break
        
        if not boss_selected:
            print(f"❌ Кнопка с индексом {boss_index} не найдена")
            return False
        
        heal_mode = False
        dm_attack_running = True
        dm_battle_msg_id = None
        print("✅ DM-атака запущена! Ожидаю сообщения от бота...")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка запуска DM-атаки: {e}")
        return False

# ===== ОСТАНОВКА DM АТАКИ =====
async def stop_dm_attack():
    global dm_attack_running, dm_attack_task
    dm_attack_running = False
    if dm_attack_task and not dm_attack_task.done():
        try:
            dm_attack_task.cancel()
        except Exception:
            pass
    dm_attack_task = None
    print("🛑 DM-атака остановлена")

# ===== МОНИТОРИНГ БОССОВ =====
async def check_bosses():
    global is_active, selected_bosses, chat_id, user_client, chat_created, last_equip_time, is_equip_mode, current_target, reconnect_attempts, last_activity_check, dm_attack_running, BOT_ID
    
    if not user_client:
        return
    
    current_time = time.time()
    if current_time - last_activity_check >= ACTIVITY_CHECK_INTERVAL:
        last_activity_check = current_time
        if not await check_user_activity():
            print("⚠️ Аккаунт неактивен, пытаюсь переподключиться...")
            if await reconnect_user():
                print("✅ Аккаунт восстановлен!")
                await get_bot_id()
            else:
                return
    
    if dm_attack_running:
        return
    
    if not is_active or not selected_bosses or not chat_created:
        return
    
    current_time = time.time()
    if current_time - last_equip_time >= 1200:
        print("⏰ Пора делать экипировку!")
        await do_equip()
        last_equip_time = current_time
        print("⏳ Жду 1 минуту после экипировки...")
        await asyncio.sleep(60)
        return
    
    if is_equip_mode:
        return
    
    try:
        await user_client.send_message(chat_id, "бл")
        await asyncio.sleep(2)
        
        messages = await user_client.get_messages(chat_id, limit=10)
        boss_message = None
        bot_entity = await user_client.get_entity(BOT_USERNAME)
        for msg in messages:
            if msg.sender_id == bot_entity.id:
                boss_message = msg.text
                break
        
        if not boss_message:
            print("⚠️ Сообщение с боссами не найдено")
            return
        
        if current_target is not None:
            boss = BOSSES[current_target]
            pattern = rf"{boss['emoji']}.*{boss['name']}.*(Жив!|\d+[мс. ]+\d*[мс.]*)"
            match = re.search(pattern, boss_message)
            if match:
                status = match.group(1)
                if status == "Жив!":
                    print(f"⏳ {boss['name']} ещё жив ({status}), жду смерти...")
                    return
                else:
                    print(f"💀 {boss['name']} умер! Разблокирован для новой атаки!")
                    current_target = None
                    return
            else:
                print(f"⚠️ Не найден статус для {boss['name']}, разблокирую...")
                current_target = None
                return
        
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
        
        if alive_bosses:
            boss_index = alive_bosses[0]
            boss = BOSSES[boss_index]
            print(f"⚔️ Запускаю DM-атаку на {boss['name']} в ЛС @{BOT_USERNAME}...")
            success = await start_dm_attack(boss_index)
            if success:
                current_target = boss_index
                print(f"✅ {boss['name']} атакуется в ЛС! Блокирую всех боссов до его смерти...")
            else:
                print(f"❌ Не удалось запустить DM-атаку на {boss['name']}")
        else:
            print("⏳ Нет живых боссов из выбранных")
        
    except Exception as e:
        print(f"Ошибка в check_bosses: {e}")

# ===== ОСНОВНОЙ ЦИКЛ =====
async def main_loop():
    global is_active
    while True:
        try:
            await check_bosses()
            if is_active and user_client and not user_client.is_connected():
                print("⚠️ Потеряно соединение, пытаюсь восстановить...")
                await reconnect_user()
                if user_client and user_client.is_connected():
                    await create_or_get_chat(user_client)
            await asyncio.sleep(20)
        except Exception as e:
            print(f"❌ Ошибка в главном цикле: {e}")
            await asyncio.sleep(30)

# ===== ОБРАБОТКА КОМАНД =====
async def handle_main_commands(event, text):
    global is_active, selected_bosses, current_target, dm_attack_running
    
    if text in ["✅ ВКЛЮЧИТЬ", "❌ ВЫКЛЮЧИТЬ"]:
        is_active = not is_active
        status = "🟢 ВКЛЮЧЕН" if is_active else "🔴 ВЫКЛЮЧЕН"
        if not is_active:
            current_target = None
            if dm_attack_running:
                await stop_dm_attack()
        await event.respond(
            f"📊 Статус: {status}\n🎯 Выбрано боссов: {len(selected_bosses)}",
            buttons=get_main_keyboard()
        )
    
    elif text == "🎯 ВЫБРАТЬ БОССОВ":
        await event.respond(
            "🎯 **Выбери боссов для охоты:**\n✅ - выбран, ⬜ - не выбран",
            buttons=get_bosses_keyboard()
        )
    
    elif text == "📊 СТАТУС БОССОВ":
        chat_status = "✅ Создан" if chat_created else "❌ Не создан"
        target_name = BOSSES[current_target]['name'] if current_target is not None else "Нет"
        dm_status = "🟢 Активна" if dm_attack_running else "🔴 Неактивна"
        bot_id_status = f"✅ {BOT_ID}" if BOT_ID else "❌ Не получен"
        await event.respond(
            f"📊 **Текущий статус:**\n"
            f"🟢 Бот: {'ВКЛЮЧЕН' if is_active else 'ВЫКЛЮЧЕН'}\n"
            f"🎯 Выбрано боссов: {len(selected_bosses)}\n"
            f"⚔️ Атакуется: {target_name}\n"
            f"📁 Чат: {chat_status}\n"
            f"💬 DM-атака: {dm_status}\n"
            f"🤖 ID бота: {bot_id_status}"
        )
    
    elif text == "🔄 ОБНОВИТЬ":
        await event.respond("🔄 Обновляю статус...")
        await get_bot_id()
        await check_bosses()
        await event.respond("✅ Готово! Проверь ЛС с @IsekaiGlobal_bot")
    
    elif text == "🔙 НАЗАД":
        await event.respond("🔙 Возвращаюсь в главное меню", buttons=get_main_keyboard())
    
    elif any(emoji in text for emoji in ["✅", "⬜"]):
        for i, boss in enumerate(BOSSES):
            if boss['emoji'] in text:
                if i in selected_bosses:
                    selected_bosses.remove(i)
                    if current_target == i:
                        current_target = None
                        if dm_attack_running:
                            await stop_dm_attack()
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
    print(f"🤖 Работаем с ботом: @{BOT_USERNAME}")
    await bot_client.start(bot_token=BOT_TOKEN)
    print("✅ Бот запущен! Жду авторизации...")
    await bot_client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())