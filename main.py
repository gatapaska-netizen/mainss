from telethon import TelegramClient, events, Button
from telethon.tl.types import Message, KeyboardButton, ChatAdminRights
from telethon.tl.functions.messages import CreateChatRequest, AddChatUserRequest, EditChatAdminRequest
from telethon.tl.functions.channels import EditAdminRequest
from telethon.errors import SessionPasswordNeededError, UserAlreadyParticipantError
import asyncio
import re
import time
import os
import sqlite3

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

# КД атаки в секундах
ATTACK_COOLDOWN = 0.95

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

BOT_SESSION_PATH = os.path.join(SESSION_DIR, 'bot_session')
bot_client = TelegramClient(BOT_SESSION_PATH, API_ID, API_HASH)

user_client = None
user_session_path = None
is_active = False
selected_bosses = set()
chat_id = None
chat_created = False
last_equip_time = 0
is_equip_mode = False
current_target = None
current_user_id = None

auth_states = {}
user_codes = {}

reconnect_attempts = 0
MAX_RECONNECT_ATTEMPTS = 5
last_activity_check = 0
ACTIVITY_CHECK_INTERVAL = 60

# Для атаки
is_attacking = False
attack_task = None
attack_message_id = None
last_attack_time = 0
boss_selected = False  # Флаг для предотвращения двойного выбора босса

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

# ===== ВАТЧЕР ДЛЯ СООБЩЕНИЙ ОТ БОТА =====
@bot_client.on(events.NewMessage)
async def watcher_new(event):
    """Следит за новыми сообщениями от бота"""
    if not event.message or not event.message.text:
        return
    
    if event.message.chat_id == BOT_ID:
        print(f"📩 Новое сообщение от бота (ID: {event.message.id})")
        if is_attacking:
            await check_and_click(event.message)

@bot_client.on(events.MessageEdited)
async def watcher_edit(event):
    """Следит за изменениями сообщений от бота"""
    if not event.message or not event.message.text:
        return
    
    if event.message.chat_id == BOT_ID:
        print(f"✏️ Изменено сообщение от бота (ID: {event.message.id})")
        if is_attacking:
            await check_and_click(event.message)

# ===== ПРОВЕРКА И НАЖАТИЕ КНОПКИ =====
async def check_and_click(message):
    """Проверяет наличие 💕 и нажимает кнопку"""
    global is_attacking, current_target, last_attack_time
    
    if not message or not message.text:
        return
    
    text = message.text
    
    # Проверяем победу
    if "повержен" in text.lower() or "убил" in text.lower():
        print("🏆 ПОБЕДА! Забираем награду...")
        if message.buttons:
            try:
                await message.click(0)
                print("✅ Награда забрана!")
                is_attacking = False
                current_target = None
                if attack_task:
                    attack_task.cancel()
                return
            except Exception as e:
                print(f"⚠️ Ошибка забора награды: {e}")
                return
    
    # Проверяем наличие 💕
    if "💕" in text:
        current_time = time.time()
        if current_time - last_attack_time >= ATTACK_COOLDOWN:
            print("💕 Найден смайлик 💕 - нажимаю кнопку")
            if message.buttons:
                try:
                    await message.click(0)
                    last_attack_time = current_time
                    print(f"✅ Нажата первая кнопка (КД: {ATTACK_COOLDOWN}с)")
                except Exception as e:
                    print(f"⚠️ Ошибка нажатия: {e}")
        else:
            remaining = ATTACK_COOLDOWN - (current_time - last_attack_time)
            print(f"⏳ Ожидание КД: {remaining:.2f}с")
    else:
        print("❌ Нет 💕 в сообщении - атака завершена!")
        is_attacking = False
        current_target = None
        if attack_task:
            attack_task.cancel()

# ===== ФУНКЦИЯ АТАКИ =====
async def attack_loop():
    """Цикл атаки - каждую секунду проверяет сообщение"""
    global is_attacking, attack_message_id
    
    while is_attacking:
        try:
            if attack_message_id:
                msg = await user_client.get_messages(BOT_ID, ids=attack_message_id)
                if msg:
                    await check_and_click(msg)
                else:
                    print("⚠️ Сообщение не найдено, завершаю атаку")
                    is_attacking = False
                    break
            
            await asyncio.sleep(0.5)
            
        except Exception as e:
            print(f"⚠️ Ошибка в цикле атаки: {e}")
            await asyncio.sleep(0.5)

# ===== АВТОРИЗАЦИЯ =====
async def start_auth(event, user_id):
    global current_user_id
    current_user_id = user_id
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
    global user_client, user_session_path
    
    phone = re.sub(r'[\s\-\(\)]', '', phone)
    if not phone.startswith('+'):
        await event.respond("❌ Неверный формат! Номер должен начинаться с `+`\nПример: `+79991234567`")
        return
    
    try:
        if user_client:
            try:
                if user_client.is_connected():
                    await user_client.disconnect()
                await user_client._disconnect()
            except Exception:
                pass
            user_client = None
        
        session_name = f'user_{phone.replace("+", "")}'
        user_session_path = os.path.join(SESSION_DIR, session_name)
        
        lock_file = f"{user_session_path}.lock"
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
                print(f"🗑️ Удалён файл блокировки: {lock_file}")
            except Exception:
                pass
        
        client = TelegramClient(user_session_path, API_ID, API_HASH)
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
        
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            await event.respond(
                "⚠️ **База данных занята!**\n\n"
                "Попробуйте:\n"
                "1. Подождать 5-10 секунд\n"
                "2. Написать `/start` заново\n"
                "3. Перезапустить бота"
            )
        else:
            await event.respond(f"❌ Ошибка: {str(e)}\nПопробуй ещё раз отправить номер.")
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
    global user_client, chat_id, chat_created, reconnect_attempts, last_activity_check, BOT_ID, current_user_id
    
    user_client = client
    current_user_id = user_id
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
    global is_attacking, attack_task, attack_message_id, user_client, BOT_ID, current_target, last_attack_time, boss_selected
    
    if is_attacking:
        print("⚠️ Атака уже запущена")
        return False
    
    if BOT_ID is None:
        await get_bot_id()
        if BOT_ID is None:
            print("❌ Не удалось получить ID бота!")
            return False
    
    try:
        # Отправляем "бо" только если не было выбрано
        if not boss_selected:
            await user_client.send_message(BOT_ID, "бо")
            print(f"✏️ Отправил 'бо' в ЛС @{BOT_USERNAME}")
            await asyncio.sleep(2)
        
        messages = await user_client.get_messages(BOT_ID, limit=3)
        if not messages:
            print("❌ Нет сообщений от бота")
            return False
        
        # Выбираем босса
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
        
        await asyncio.sleep(2)
        
        last_msg = await user_client.get_messages(BOT_ID, limit=1)
        if last_msg and last_msg[0]:
            attack_message_id = last_msg[0].id
            print(f"✅ Сохранён ID сообщения: {attack_message_id}")
        
        last_attack_time = 0
        is_attacking = True
        attack_task = asyncio.create_task(attack_loop())
        print(f"✅ Атака запущена! КД: {ATTACK_COOLDOWN}с. Ожидаю 💕 в сообщении...")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка запуска атаки: {e}")
        return False

# ===== ОСТАНОВКА АТАКИ =====
async def stop_attack():
    global is_attacking, attack_task, boss_selected
    is_attacking = False
    boss_selected = False
    if attack_task and not attack_task.done():
        try:
            attack_task.cancel()
        except Exception:
            pass
    attack_task = None
    print("🛑 Атака остановлена")

# ===== МОНИТОРИНГ БОССОВ =====
async def check_bosses():
    global is_active, selected_bosses, chat_id, user_client, chat_created, last_equip_time, is_equip_mode, current_target, reconnect_attempts, last_activity_check, is_attacking, BOT_ID, boss_selected
    
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
    
    if is_attacking:
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
                    boss_selected = False  # Сбрасываем флаг при смерти босса
                    return
            else:
                print(f"⚠️ Не найден статус для {boss['name']}, разблокирую...")
                current_target = None
                boss_selected = False
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
                boss_selected = False
        else:
            print("⏳ Нет живых боссов из выбранных")
            boss_selected = False
        
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
    global is_active, selected_bosses, current_target, is_attacking, boss_selected
    
    if text in ["✅ ВКЛЮЧИТЬ", "❌ ВЫКЛЮЧИТЬ"]:
        is_active = not is_active
        status = "🟢 ВКЛЮЧЕН" if is_active else "🔴 ВЫКЛЮЧЕН"
        if not is_active:
            current_target = None
            boss_selected = False
            if is_attacking:
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
        attack_status = "🟢 Активна" if is_attacking else "🔴 Неактивна"
        bot_id_status = f"✅ {BOT_ID}" if BOT_ID else "❌ Не получен"
        await event.respond(
            f"📊 **Текущий статус:**\n"
            f"🟢 Бот: {'ВКЛЮЧЕН' if is_active else 'ВЫКЛЮЧЕН'}\n"
            f"🎯 Выбрано боссов: {len(selected_bosses)}\n"
            f"⚔️ Атакуется: {target_name}\n"
            f"📁 Чат: {chat_status}\n"
            f"💬 Атака: {attack_status}\n"
            f"🤖 ID бота: {bot_id_status}\n"
            f"⏱️ КД атаки: {ATTACK_COOLDOWN}с"
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
                        boss_selected = False
                        if is_attacking:
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
    print(f"⏱️ КД атаки: {ATTACK_COOLDOWN}с")
    await bot_client.start(bot_token=BOT_TOKEN)
    print("✅ Бот запущен! Жду авторизации...")
    await bot_client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())