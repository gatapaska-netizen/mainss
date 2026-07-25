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

BOT_USERNAME = "IsekaiGlobal_bot"
BOT_ID = None

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

BOT_SESSION_PATH = os.path.join(SESSION_DIR, 'bot_session')
bot_client = TelegramClient(BOT_SESSION_PATH, API_ID, API_HASH)

user_client = None
is_active = False
selected_bosses = set()
chat_id = None
chat_created = False
last_equip_time = 0
is_equip_mode = False
current_target = None

auth_states = {}
user_codes = {}

reconnect_attempts = 0
MAX_RECONNECT_ATTEMPTS = 5
last_activity_check = 0
ACTIVITY_CHECK_INTERVAL = 60

# Для атаки
attack_running = False
attack_task = None
heal_mode = False
last_attack_time = 0

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

# ===== ПРОСТОЙ ВАТЧЕР ДЛЯ СООБЩЕНИЙ ОТ БОТА =====
@bot_client.on(events.NewMessage)
async def watcher(event):
    """Следит за новыми сообщениями от бота"""
    global attack_running
    
    if not event.message or not event.message.text:
        return
    
    # Если это сообщение от IsekaiGlobal_bot в ЛС
    if event.message.chat_id == BOT_ID and attack_running:
        print(f"📩 Получено сообщение от бота")
        await handle_bot_message(event.message)

@bot_client.on(events.MessageEdited)
async def watcher_edit(event):
    """Следит за изменениями сообщений от бота"""
    global attack_running
    
    if not event.message or not event.message.text:
        return
    
    # Если это сообщение от IsekaiGlobal_bot в ЛС
    if event.message.chat_id == BOT_ID and attack_running:
        print(f"✏️ Изменено сообщение от бота")
        await handle_bot_message(event.message)

# ===== ОБРАБОТКА СООБЩЕНИЯ ОТ БОТА =====
async def handle_bot_message(message):
    """Обрабатывает сообщение от бота - нажимает кнопку если нужно"""
    global heal_mode, last_attack_time
    
    try:
        text = message.text or ""
        
        # Проверяем наличие кнопок
        if not message.buttons:
            print("❌ Нет кнопок в сообщении")
            return
        
        print(f"📝 Текст: {text[:100]}...")
        
        # Проверяем победу
        if "повержен" in text.lower() or "убил" in text.lower():
            print("🏆 ПОБЕДА! Забираем награду...")
            try:
                await message.click(0)
                print("✅ Награда забрана!")
                # Останавливаем атаку
                global attack_running
                attack_running = False
                if attack_task:
                    attack_task.cancel()
                return
            except Exception as e:
                print(f"⚠️ Ошибка забора награды: {e}")
                return
        
        # Проверяем наличие "Босс:" и "Ты:" - значит это бой
        if "Босс:" in text and "Ты:" in text:
            print("⚔️ Обнаружен бой!")
            
            # Проверяем здоровье игрока
            player_health = None
            health_match = re.search(r'Ты\s*:\s*([\d,]+\.?\d*[K]?)\s*/\s*[\d,]+\.?\d*[K]?', text, re.IGNORECASE)
            if health_match:
                health_str = health_match.group(1).replace(',', '')
                if 'K' in health_str.upper():
                    health_str = health_str.upper().replace('K', '')
                    player_health = float(health_str) * 1000
                else:
                    player_health = float(health_str)
                print(f"❤️ Твоё здоровье: {player_health}")
            
            # Проверяем критическое здоровье
            if current_target is not None and player_health is not None:
                boss = BOSSES[current_target]
                critical = boss.get('critical_health', 60)
                if player_health < critical:
                    if not heal_mode:
                        print(f"⚠️ КРИТИЧЕСКОЕ ЗДОРОВЬЕ! {player_health} < {critical}")
                        heal_mode = True
                else:
                    if heal_mode:
                        print(f"✅ Здоровье восстановлено!")
                        heal_mode = False
            
            # Нажимаем кнопку
            await click_button(message)
        
    except Exception as e:
        print(f"⚠️ Ошибка обработки сообщения: {e}")

# ===== НАЖАТИЕ КНОПКИ =====
async def click_button(message):
    """Нажимает нужную кнопку в сообщении"""
    global heal_mode, last_attack_time
    
    try:
        current_time = time.time()
        
        # Проверяем кд - не чаще 1 раза в секунду
        if current_time - last_attack_time < 1:
            return
        
        if heal_mode:
            # Ищем кнопку "Обновить"
            for row in message.buttons:
                for btn in row:
                    if "Обновить" in btn.text or "🟢" in btn.text:
                        print("🔄 Нажимаю ОБНОВИТЬ (лечение)")
                        await message.click(btn)
                        last_attack_time = current_time
                        return
        else:
            # Ищем кнопку "Атаковать"
            for row in message.buttons:
                for btn in row:
                    if "Атаковать" in btn.text:
                        print("⚔️ Нажимаю АТАКОВАТЬ")
                        await message.click(btn)
                        last_attack_time = current_time
                        return
            
            # Если не нашли "Атаковать", пробуем первую кнопку
            try:
                print("⚔️ Нажимаю первую кнопку")
                await message.click(0)
                last_attack_time = current_time
            except Exception as e:
                print(f"⚠️ Ошибка нажатия: {e}")
                
    except Exception as e:
        print(f"⚠️ Ошибка нажатия кнопки: {e}")

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

# ===== ЗАПУСК АТАКИ =====
async def start_attack(boss_index):
    """Запускает атаку на босса"""
    global attack_running, attack_task, heal_mode, user_client, BOT_ID
    
    if attack_running:
        print("⚠️ Атака уже запущена")
        return False
    
    if BOT_ID is None:
        await get_bot_id()
        if BOT_ID is None:
            print("❌ Не удалось получить ID бота!")
            return False
    
    try:
        # Отправляем "бо" боту
        await user_client.send_message(BOT_ID, "бо")
        print(f"✏️ Отправил 'бо' в ЛС @{BOT_USERNAME}")
        await asyncio.sleep(2)
        
        # Получаем сообщение с кнопками боссов
        messages = await user_client.get_messages(BOT_ID, limit=3)
        if not messages:
            print("❌ Нет сообщений от бота")
            return False
        
        # Нажимаем кнопку босса
        boss_selected = False
        for msg in messages:
            if msg.buttons:
                flat_buttons = [btn for row in msg.buttons for btn in row]
                if boss_index < len(flat_buttons):
                    await msg.click(boss_index)
                    print(f"✅ Нажата кнопка {boss_index + 1}: {flat_buttons[boss_index].text}")
                    boss_selected = True
                    break
        
        if not boss_selected:
            print(f"❌ Кнопка с индексом {boss_index} не найдена")
            return False
        
        # Запускаем атаку
        heal_mode = False
        attack_running = True
        print("✅ Атака запущена! Ожидаю сообщения от бота...")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка запуска атаки: {e}")
        return False

# ===== ОСТАНОВКА АТАКИ =====
async def stop_attack():
    global attack_running, attack_task
    attack_running = False
    if attack_task and not attack_task.done():
        try:
            attack_task.cancel()
        except Exception:
            pass
    attack_task = None
    print("🛑 Атака остановлена")

# ===== МОНИТОРИНГ БОССОВ =====
async def check_bosses():
    global is_active, selected_bosses, chat_id, user_client, chat_created, last_equip_time, is_equip_mode, current_target, reconnect_attempts, last_activity_check, attack_running, BOT_ID
    
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
    
    if attack_running:
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
            print(f"⚔️ Запускаю атаку на {boss['name']} в ЛС @{BOT_USERNAME}...")
            success = await start_attack(boss_index)
            if success:
                current_target = boss_index
                print(f"✅ {boss['name']} атакуется в ЛС! Блокирую всех боссов до его смерти...")
            else:
                print(f"❌ Не удалось запустить атаку на {boss['name']}")
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
    global is_active, selected_bosses, current_target, attack_running
    
    if text in ["✅ ВКЛЮЧИТЬ", "❌ ВЫКЛЮЧИТЬ"]:
        is_active = not is_active
        status = "🟢 ВКЛЮЧЕН" if is_active else "🔴 ВЫКЛЮЧЕН"
        if not is_active:
            current_target = None
            if attack_running:
                await stop_attack()
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
        attack_status = "🟢 Активна" if attack_running else "🔴 Неактивна"
        bot_id_status = f"✅ {BOT_ID}" if BOT_ID else "❌ Не получен"
        await event.respond(
            f"📊 **Текущий статус:**\n"
            f"🟢 Бот: {'ВКЛЮЧЕН' if is_active else 'ВЫКЛЮЧЕН'}\n"
            f"🎯 Выбрано боссов: {len(selected_bosses)}\n"
            f"⚔️ Атакуется: {target_name}\n"
            f"📁 Чат: {chat_status}\n"
            f"💬 Атака: {attack_status}\n"
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
                        if attack_running:
                            await stop_attack()
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