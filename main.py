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
BOT_TOKEN = "8695263973:AAHge3QFURlz1nOJVtGmdav5HQ2NL5-RjeI"
API_ID = 25569323
API_HASH = "061bad708728d3d928054f16c932de6d"

# Список боссов (порядок = порядок кнопок в боте)
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

# Словарь для отслеживания атакованных боссов
# {индекс: True} - босс атакован и ждём его смерти
attacked_bosses = {}

# Статус авторизации
auth_states = {}
user_codes = {}

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

# ===== ФУНКЦИЯ ЭКИПИРОВКИ =====
async def do_equip():
    """Выполняет экипировку: пишет 'экип', нажимает 8-ю кнопку (слоты), затем 6-ю"""
    global user_client, is_equip_mode
    
    try:
        print("🔄 Начинаю экипировку...")
        is_equip_mode = True
        
        await user_client.send_message(bot_username, "экип")
        print("✏️ Отправил 'экип'")
        await asyncio.sleep(2)
        
        messages = await user_client.get_messages(bot_username, limit=2)
        if not messages:
            print("❌ Нет сообщений от бота")
            is_equip_mode = False
            return
        
        for msg in messages:
            if msg.buttons:
                flat_buttons = [btn for row in msg.buttons for btn in row]
                
                if len(flat_buttons) >= 8:
                    await asyncio.sleep(2)
                    await msg.click(7)
                    print("✅ Нажата 8-я кнопка (Слоты)")
                    await asyncio.sleep(2)
                    
                    new_messages = await user_client.get_messages(bot_username, limit=2)
                    if new_messages:
                        for new_msg in new_messages:
                            if new_msg.buttons:
                                new_buttons = [btn for row in new_msg.buttons for btn in row]
                                
                                if len(new_buttons) >= 6:
                                    await asyncio.sleep(2)
                                    await new_msg.click(5)
                                    print("✅ Нажата 6-я кнопка")
                                    await asyncio.sleep(2)
                                    break
                    break
        
        print("✅ Экипировка завершена!")
        is_equip_mode = False
        
    except Exception as e:
        print(f"❌ Ошибка экипировки: {e}")
        is_equip_mode = False

# ===== МОНИТОРИНГ БОССОВ =====
async def check_bosses():
    global is_active, selected_bosses, chat_id, user_client, chat_created, last_equip_time, is_equip_mode, attacked_bosses
    
    if not user_client or not is_active or not selected_bosses or not chat_created:
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
        
        # 4. Парсим статусы выбранных боссов
        for index in selected_bosses:
            boss = BOSSES[index]
            
            # Ищем строку с боссом
            pattern = rf"{boss['emoji']}.*{boss['name']}.*(Жив!|\d+[мс. ]+\d*[мс.]*)"
            match = re.search(pattern, boss_message)
            
            if match:
                status = match.group(1)
                is_alive = status == "Жив!"
                
                # Проверяем, атакован ли босс
                is_attacked = attacked_bosses.get(index, False)
                
                if is_alive:
                    if not is_attacked:
                        # Босс жив и не атакован → АТАКУЕМ!
                        print(f"🔥 {boss['name']} жив! Атакую...")
                        success = await attack_boss(index)
                        if success:
                            attacked_bosses[index] = True
                            print(f"✅ {boss['name']} атакован! Жду смерти...")
                        else:
                            print(f"❌ Не удалось атаковать {boss['name']}")
                    else:
                        # Босс уже атакован, ждём смерти
                        print(f"⏳ {boss['name']} атакован, жду смерти...")
                else:
                    if is_attacked:
                        # Босс умер! Разблокируем
                        attacked_bosses[index] = False
                        print(f"💀 {boss['name']} умер! Разблокирован для новой атаки!")
                    else:
                        print(f"⏳ {boss['name']} не жив ({status}), пропускаю")
        
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
    while True:
        await check_bosses()
        await asyncio.sleep(20)  # Проверка каждые 20 секунд

# ===== ОБРАБОТКА КОМАНД =====
async def handle_main_commands(event, text):
    global is_active, selected_bosses, chat_id, user_client, chat_created, attacked_bosses
    
    if text in ["✅ ВКЛЮЧИТЬ", "❌ ВЫКЛЮЧИТЬ"]:
        is_active = not is_active
        status = "🟢 ВКЛЮЧЕН" if is_active else "🔴 ВЫКЛЮЧЕН"
        if not is_active:
            # При выключении сбрасываем список атакованных боссов
            attacked_bosses = {}
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
        attacked_count = sum(1 for v in attacked_bosses.values() if v)
        await event.respond(
            f"📊 **Текущий статус:**\n"
            f"🟢 Бот: {'ВКЛЮЧЕН' if is_active else 'ВЫКЛЮЧЕН'}\n"
            f"🎯 Выбрано боссов: {len(selected_bosses)}\n"
            f"⚔️ Атаковано боссов: {attacked_count}\n"
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
                    # Если босс убран из выбора — сбрасываем его статус атаки
                    attacked_bosses.pop(i, None)
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