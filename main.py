from telethon import TelegramClient, events, Button
from telethon.tl.types import Message, KeyboardButton, ChatAdminRights
from telethon.tl.functions.messages import CreateChatRequest, AddChatUserRequest, EditChatAdminRequest
from telethon.tl.functions.channels import EditAdminRequest
from telethon.errors import SessionPasswordNeededError, UserAlreadyParticipantError
import asyncio
import re
import time
import os
import json

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
    {"emoji": "🦀", "name": "Король Рифов"},
    {"emoji": "👁", "name": "Страж Портала"},
    {"emoji": "📡", "name": "Хранитель Сигнала"},
    {"emoji": "🛸", "name": "Повелитель Машин"},
    {"emoji": "🖥️", "name": "Центральный ИИ"}
]

# Путь к сессии бота
BOT_SESSION_PATH = os.path.join(SESSION_DIR, 'bot_session')

# Клиент бота
bot_client = TelegramClient(BOT_SESSION_PATH, API_ID, API_HASH)

# ===== ХРАНЕНИЕ ДАННЫХ ПОЛЬЗОВАТЕЛЕЙ =====
class UserData:
    def __init__(self):
        self.user_client = None
        self.is_active = False
        self.selected_bosses = set()
        self.chat_id = None
        self.chat_created = False
        self.current_target = None
        self.last_equip_time = 0
        self.is_equip_mode = False
        self.auth_step = 'idle'
        self.phone = None
        self.session_name = None
        self.is_authorized = False
        self.owner_id = None
        self.loop_running = False  # Флаг для отслеживания запущенного цикла

# Словарь для хранения данных всех пользователей
users_data = {}

# Файл для сохранения состояния пользователей
STATE_FILE = os.path.join(SESSION_DIR, 'users_state.json')

# ===== СОХРАНЕНИЕ/ЗАГРУЗКА СОСТОЯНИЯ =====
def save_users_state():
    """Сохраняет состояние пользователей в файл"""
    try:
        state = {}
        for user_id, data in users_data.items():
            state[str(user_id)] = {
                'phone': data.phone,
                'session_name': data.session_name,
                'is_authorized': data.is_authorized,
                'selected_bosses': list(data.selected_bosses),
                'is_active': data.is_active,
                'chat_id': data.chat_id,
                'chat_created': data.chat_created,
                'current_target': data.current_target,
                'last_equip_time': data.last_equip_time,
                'owner_id': data.owner_id
            }
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        print(f"💾 Состояние пользователей сохранено в {STATE_FILE}")
    except Exception as e:
        print(f"⚠️ Ошибка сохранения состояния: {e}")

def load_users_state():
    """Загружает состояние пользователей из файла"""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
            print(f"📂 Загружено состояние пользователей из {STATE_FILE}")
            return state
    except Exception as e:
        print(f"⚠️ Ошибка загрузки состояния: {e}")
    return {}

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
def get_user_data(user_id):
    """Получает или создаёт данные пользователя"""
    if user_id not in users_data:
        users_data[user_id] = UserData()
        users_data[user_id].owner_id = user_id
    return users_data[user_id]

async def restore_user_session(user_id, phone, session_name):
    """Восстанавливает сессию пользователя"""
    try:
        session_path = os.path.join(SESSION_DIR, session_name)
        
        if os.path.exists(f"{session_path}.session"):
            print(f"🔄 Восстанавливаю сессию для {phone}")
            
            client = TelegramClient(session_path, API_ID, API_HASH)
            await client.connect()
            
            if await client.is_user_authorized():
                me = await client.get_me()
                print(f"✅ Сессия восстановлена для {me.first_name} ({phone})")
                return client
            else:
                print(f"⚠️ Сессия для {phone} недействительна")
                return None
        else:
            print(f"ℹ️ Файл сессии для {phone} не найден")
            return None
    except Exception as e:
        print(f"❌ Ошибка восстановления сессии: {e}")
        return None

# ===== КЛАВИАТУРЫ =====
def get_main_keyboard(user_data):
    toggle_text = "❌ ВЫКЛЮЧИТЬ" if user_data.is_active else "✅ ВКЛЮЧИТЬ"
    return [
        [KeyboardButton(toggle_text)],
        [KeyboardButton("🎯 ВЫБРАТЬ БОССОВ")],
        [KeyboardButton("📊 СТАТУС БОССОВ"), KeyboardButton("🔄 ОБНОВИТЬ")]
    ]

def get_bosses_keyboard(user_data):
    buttons = []
    row = []
    
    for i, boss in enumerate(BOSSES):
        icon = "✅" if i in user_data.selected_bosses else "⬜"
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
        user_data = get_user_data(user_id)
        
        if text == '/start':
            await start_auth(event, user_id)
            return
        
        step = user_data.auth_step
        
        if step == 'idle' or step == 'start':
            await start_auth(event, user_id)
        elif step == 'phone':
            await handle_phone(event, user_id, text)
        elif step == 'code':
            await handle_code_input(event, user_id, text)
        elif step == 'password':
            await handle_password(event, user_id, text)
        elif step == 'done':
            await handle_main_commands(event, user_id, text)

# ===== АВТОРИЗАЦИЯ =====
async def start_auth(event, user_id):
    user_data = get_user_data(user_id)
    
    # Проверяем, есть ли уже сохранённая сессия
    if user_data.is_authorized and user_data.user_client:
        try:
            await user_data.user_client.get_me()
            await event.respond(
                f"✅ Вы уже авторизованы!\n"
                f"📱 Номер: {user_data.phone}\n\n"
                f"🎮 Открываю меню управления...",
                buttons=get_main_keyboard(user_data)
            )
            # Запускаем цикл
            if not user_data.loop_running:
                asyncio.create_task(main_loop(user_id))
            return
        except:
            user_data.is_authorized = False
            user_data.user_client = None
    
    user_data.auth_step = 'phone'
    
    await event.respond(
        "🔐 **Добро пожаловать в охотника на боссов!**\n\n"
        "Для начала работы нужно авторизоваться.\n"
        "📱 **Отправь свой номер телефона** в формате:\n"
        "`+79991234567`",
        buttons=Button.clear()
    )

async def handle_phone(event, user_id, phone):
    user_data = get_user_data(user_id)
    phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    if not phone.startswith('+'):
        await event.respond("❌ Неверный формат! Номер должен начинаться с `+`\nПример: `+79991234567`")
        return
    
    try:
        session_name = f'user_{phone.replace("+", "")}'
        session_path = os.path.join(SESSION_DIR, session_name)
        
        saved_client = await restore_user_session(user_id, phone, session_name)
        if saved_client:
            user_data.user_client = saved_client
            user_data.phone = phone
            user_data.session_name = session_name
            user_data.is_authorized = True
            user_data.auth_step = 'done'
            
            me = await saved_client.get_me()
            await event.respond(
                f"✅ **Сессия восстановлена!** \n\n"
                f"👤 Аккаунт: {me.first_name} {me.last_name or ''}\n"
                f"📱 Номер: {phone}\n\n"
                f"🎮 **Открываю меню управления...**",
                buttons=get_main_keyboard(user_data)
            )
            
            user_data.chat_created = await create_or_get_chat(saved_client, user_data)
            save_users_state()
            
            if not user_data.loop_running:
                asyncio.create_task(main_loop(user_id))
            return
        
        client = TelegramClient(session_path, API_ID, API_HASH)
        await client.connect()
        await client.send_code_request(phone)
        
        user_data.auth_step = 'code'
        user_data.phone = phone
        user_data.client = client
        user_data.session_name = session_name
        
        await event.respond(
            f"✅ Код подтверждения отправлен на номер `{phone}`!\n\n"
            f"✏️ **Введи код**, используя кнопки ниже:",
            buttons=get_code_keyboard()
        )
        
    except Exception as e:
        await event.respond(f"❌ Ошибка: {str(e)}\nПопробуй ещё раз отправить номер.")

async def handle_code_input(event, user_id, text):
    user_data = get_user_data(user_id)
    
    if text == "✅ ГОТОВО":
        code = user_data.__dict__.get('code_buffer', '')
        if len(code) < 3:
            await event.respond("❌ Код должен содержать минимум 3 цифры!", buttons=get_code_keyboard())
            return
        
        await handle_code(event, user_id, code)
        return
    
    if text == "🔙":
        user_data.code_buffer = user_data.__dict__.get('code_buffer', '')[:-1]
        current_code = user_data.__dict__.get('code_buffer', '')
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
        if not hasattr(user_data, 'code_buffer'):
            user_data.code_buffer = ""
        user_data.code_buffer += digit_map[text]
        current_code = user_data.code_buffer
        await event.respond(
            f"✏️ **Введи код:**\n`{current_code}`",
            buttons=get_code_keyboard()
        )

async def handle_code(event, user_id, code):
    user_data = get_user_data(user_id)
    client = user_data.client
    
    if not client:
        await event.respond("❌ Ошибка! Начни заново с `/start`")
        return
    
    try:
        await client.sign_in(user_data.phone, code)
        await complete_auth(event, user_id, client)
        
    except SessionPasswordNeededError:
        user_data.auth_step = 'password'
        await event.respond(
            "🔐 **Требуется пароль двухфакторной аутентификации!**\n\n"
            "✏️ **Напиши свой пароль:**",
            buttons=Button.clear()
        )
        
    except Exception as e:
        await event.respond(f"❌ Неверный код: {str(e)}\nПопробуй ещё раз.", buttons=get_code_keyboard())

async def handle_password(event, user_id, password):
    user_data = get_user_data(user_id)
    client = user_data.client
    
    if not client:
        await event.respond("❌ Ошибка! Начни заново с `/start`")
        return
    
    try:
        await client.sign_in(password=password)
        await complete_auth(event, user_id, client)
        
    except Exception as e:
        await event.respond(f"❌ Неверный пароль: {str(e)}\nПопробуй ещё раз.")

async def complete_auth(event, user_id, client):
    user_data = get_user_data(user_id)
    
    user_data.user_client = client
    user_data.is_authorized = True
    me = await client.get_me()
    
    user_data.auth_step = 'done'
    
    await event.respond(
        f"✅ **Успешный вход!** \n\n"
        f"👤 Аккаунт: {me.first_name} {me.last_name or ''}\n"
        f"📱 Номер: {user_data.phone}\n"
        f"🆔 ID: {me.id}\n\n"
        f"🎮 **Открываю меню управления...**",
        buttons=get_main_keyboard(user_data)
    )
    
    user_data.chat_created = await create_or_get_chat(client, user_data)
    if user_data.chat_created:
        await event.respond("✅ Чат успешно создан и настроен!")
    else:
        await event.respond("ℹ️ Чат уже существует, подключаюсь...")
    
    save_users_state()
    
    if not user_data.loop_running:
        asyncio.create_task(main_loop(user_id))

# ===== СОЗДАНИЕ ЧАТА =====
async def create_or_get_chat(client, user_data):
    try:
        me = await client.get_me()
        username = me.username or me.first_name
        chat_name = f"МБЛ ({username})"
        
        async for dialog in client.iter_dialogs():
            if dialog.name == chat_name:
                user_data.chat_id = dialog.id
                print(f"✅ Найден существующий чат: {chat_name}")
                
                try:
                    bot_entity = await client.get_entity(bot_username)
                    await client(AddChatUserRequest(
                        chat_id=user_data.chat_id,
                        user_id=bot_entity,
                        fwd_limit=0
                    ))
                except UserAlreadyParticipantError:
                    pass
                except Exception as e:
                    print(f"⚠️ Ошибка: {e}")
                
                await give_admin_rights(client, user_data.chat_id)
                return True
        
        result = await client(CreateChatRequest(
            users=[bot_username],
            title=chat_name
        ))
        
        chat = result.chats[0]
        user_data.chat_id = chat.id
        print(f"✅ Чат создан: {chat_name}")
        
        await give_admin_rights(client, user_data.chat_id)
        await client.send_message(user_data.chat_id, "🤖 Бот для мониторинга боссов активирован!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания чата: {e}")
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
        print(f"⚠️ Ошибка выдачи прав: {e}")

# ===== ФУНКЦИЯ ЭКИПИРОВКИ =====
async def do_equip(user_data):
    try:
        print("🔄 Начинаю экипировку...")
        user_data.is_equip_mode = True
        
        await user_data.user_client.send_message(bot_username, "экип")
        print("✏️ Отправил 'экип'")
        await asyncio.sleep(2)
        
        messages = await user_data.user_client.get_messages(bot_username, limit=2)
        if not messages:
            print("❌ Нет сообщений от бота")
            user_data.is_equip_mode = False
            return
        
        for msg in messages:
            if msg.buttons:
                flat_buttons = [btn for row in msg.buttons for btn in row]
                
                if len(flat_buttons) >= 8:
                    await asyncio.sleep(2)
                    await msg.click(7)
                    print("✅ Нажата 8-я кнопка (Слоты)")
                    await asyncio.sleep(2)
                    
                    new_messages = await user_data.user_client.get_messages(bot_username, limit=2)
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
        user_data.is_equip_mode = False
        
    except Exception as e:
        print(f"❌ Ошибка экипировки: {e}")
        user_data.is_equip_mode = False

# ===== МОНИТОРИНГ БОССОВ =====
async def check_bosses(user_id):
    user_data = get_user_data(user_id)
    
    if not user_data.user_client or not user_data.is_active or not user_data.selected_bosses or not user_data.chat_created:
        return
    
    current_time = time.time()
    if current_time - user_data.last_equip_time >= 1200:
        print(f"👤 {user_id}: ⏰ Пора делать экипировку!")
        await do_equip(user_data)
        user_data.last_equip_time = current_time
        print(f"👤 {user_id}: ⏳ Жду 1 минуту после экипировки...")
        await asyncio.sleep(60)
        return
    
    if user_data.is_equip_mode:
        return
    
    try:
        # 1. Пишем "бл" в чат
        await user_data.user_client.send_message(user_data.chat_id, "бл")
        await asyncio.sleep(2)
        
        # 2. Получаем последние сообщения
        messages = await user_data.user_client.get_messages(user_data.chat_id, limit=10)
        
        # 3. Ищем сообщение от IsekaiGlobal_bot
        boss_message = None
        bot_entity = await user_data.user_client.get_entity(bot_username)
        for msg in messages:
            if msg.sender_id == bot_entity.id:
                boss_message = msg.text
                break
        
        if not boss_message:
            print(f"👤 {user_id}: ⚠️ Сообщение с боссами не найдено")
            return
        
        # 4. Если есть текущая цель — проверяем её статус
        if user_data.current_target is not None:
            boss = BOSSES[user_data.current_target]
            pattern = rf"{boss['emoji']}.*{boss['name']}.*(Жив!|\d+[мс. ]+\d*[мс.]*)"
            match = re.search(pattern, boss_message)
            
            if match:
                status = match.group(1)
                is_alive = status == "Жив!"
                
                if is_alive:
                    print(f"👤 {user_id}: ⏳ {boss['name']} ещё жив ({status}), жду смерти...")
                    return
                else:
                    print(f"👤 {user_id}: 💀 {boss['name']} умер! Разблокирован для новой атаки!")
                    user_data.current_target = None
                    return
            else:
                print(f"👤 {user_id}: ⚠️ Не найден статус для {boss['name']}, разблокирую...")
                user_data.current_target = None
                return
        
        # 5. Нет текущей цели — ищем живого босса для атаки
        alive_bosses = []
        for index in user_data.selected_bosses:
            boss = BOSSES[index]
            pattern = rf"{boss['emoji']}.*{boss['name']}.*(Жив!|\d+[мс. ]+\d*[мс.]*)"
            match = re.search(pattern, boss_message)
            
            if match:
                status = match.group(1)
                if status == "Жив!":
                    alive_bosses.append(index)
                    print(f"👤 {user_id}: 🔥 {boss['name']} жив!")
        
        # 6. Если есть живые боссы — атакуем первого
        if alive_bosses:
            boss_index = alive_bosses[0]
            boss = BOSSES[boss_index]
            
            print(f"👤 {user_id}: ⚔️ Атакую {boss['name']}...")
            success = await attack_boss(user_data, boss_index)
            
            if success:
                user_data.current_target = boss_index
                print(f"👤 {user_id}: ✅ {boss['name']} атакован! Блокирую всех боссов до его смерти...")
            else:
                print(f"👤 {user_id}: ❌ Не удалось атаковать {boss['name']}")
        else:
            print(f"👤 {user_id}: ⏳ Нет живых боссов из выбранных")
        
    except Exception as e:
        print(f"👤 {user_id}: Ошибка в check_bosses: {e}")

# ===== АТАКА БОССА =====
async def attack_boss(user_data, boss_index):
    try:
        # 1. Пишем "бо" в бота
        await user_data.user_client.send_message(bot_username, "бо")
        await asyncio.sleep(2)
        
        # 2. Получаем сообщение с кнопками
        messages = await user_data.user_client.get_messages(bot_username, limit=2)
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
                    await user_data.user_client.send_message(bot_username, "ав+")
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
async def main_loop(user_id):
    """Основной цикл для пользователя"""
    user_data = get_user_data(user_id)
    user_data.loop_running = True
    print(f"👤 {user_id}: ✅ Основной цикл запущен!")
    
    try:
        while True:
            await check_bosses(user_id)
            await asyncio.sleep(20)
    except asyncio.CancelledError:
        print(f"👤 {user_id}: Цикл остановлен")
        user_data.loop_running = False
        raise
    except Exception as e:
        print(f"👤 {user_id}: ❌ Ошибка в основном цикле: {e}")
        user_data.loop_running = False

# ===== ОБРАБОТКА КОМАНД =====
async def handle_main_commands(event, user_id, text):
    user_data = get_user_data(user_id)
    
    if text in ["✅ ВКЛЮЧИТЬ", "❌ ВЫКЛЮЧИТЬ"]:
        user_data.is_active = not user_data.is_active
        status = "🟢 ВКЛЮЧЕН" if user_data.is_active else "🔴 ВЫКЛЮЧЕН"
        if not user_data.is_active:
            user_data.current_target = None
        await event.respond(
            f"📊 Статус: {status}\n"
            f"🎯 Выбрано боссов: {len(user_data.selected_bosses)}",
            buttons=get_main_keyboard(user_data)
        )
        save_users_state()
    
    elif text == "🎯 ВЫБРАТЬ БОССОВ":
        await event.respond(
            "🎯 **Выбери боссов для охоты:**\n"
            "✅ - выбран, ⬜ - не выбран",
            buttons=get_bosses_keyboard(user_data)
        )
    
    elif text == "📊 СТАТУС БОССОВ":
        chat_status = "✅ Создан" if user_data.chat_created else "❌ Не создан"
        target_name = BOSSES[user_data.current_target]['name'] if user_data.current_target is not None else "Нет"
        await event.respond(
            f"📊 **Текущий статус:**\n"
            f"🟢 Бот: {'ВКЛЮЧЕН' if user_data.is_active else 'ВЫКЛЮЧЕН'}\n"
            f"🎯 Выбрано боссов: {len(user_data.selected_bosses)}\n"
            f"⚔️ Атакуется: {target_name}\n"
            f"📁 Чат: {chat_status}"
        )
    
    elif text == "🔄 ОБНОВИТЬ":
        await event.respond("🔄 Обновляю статус...")
        await check_bosses(user_id)
        await event.respond("✅ Готово! Проверь чат МБЛ")
    
    elif text == "🔙 НАЗАД":
        await event.respond("🔙 Возвращаюсь в главное меню", buttons=get_main_keyboard(user_data))
    
    elif any(emoji in text for emoji in ["✅", "⬜"]):
        for i, boss in enumerate(BOSSES):
            if boss['emoji'] in text:
                if i in user_data.selected_bosses:
                    user_data.selected_bosses.remove(i)
                    if user_data.current_target == i:
                        user_data.current_target = None
                else:
                    user_data.selected_bosses.add(i)
                
                await event.respond(
                    f"{'✅ Выбран' if i in user_data.selected_bosses else '❌ Убран'} босс: {boss['name']}",
                    buttons=get_bosses_keyboard(user_data)
                )
                save_users_state()
                break

# ===== ВОССТАНОВЛЕНИЕ ПОЛЬЗОВАТЕЛЕЙ =====
async def restore_all_users():
    """Восстанавливает всех пользователей при запуске"""
    state = load_users_state()
    restored_count = 0
    
    for user_id_str, data in state.items():
        user_id = int(user_id_str)
        user_data = get_user_data(user_id)
        
        phone = data.get('phone')
        session_name = data.get('session_name')
        is_authorized = data.get('is_authorized', False)
        
        if phone and session_name and is_authorized:
            try:
                client = await restore_user_session(user_id, phone, session_name)
                if client:
                    user_data.user_client = client
                    user_data.phone = phone
                    user_data.session_name = session_name
                    user_data.is_authorized = True
                    user_data.auth_step = 'done'
                    user_data.selected_bosses = set(data.get('selected_bosses', []))
                    user_data.is_active = data.get('is_active', False)
                    user_data.chat_id = data.get('chat_id')
                    user_data.chat_created = data.get('chat_created', False)
                    user_data.current_target = data.get('current_target')
                    user_data.last_equip_time = data.get('last_equip_time', 0)
                    user_data.owner_id = user_id
                    
                    # Если чат не создан — создаём
                    if not user_data.chat_created:
                        user_data.chat_created = await create_or_get_chat(client, user_data)
                    
                    # Запускаем цикл
                    asyncio.create_task(main_loop(user_id))
                    restored_count += 1
                    print(f"✅ Восстановлен пользователь {user_id} ({phone})")
                else:
                    user_data.is_authorized = False
                    print(f"⚠️ Пользователь {user_id} требует повторной авторизации")
            except Exception as e:
                print(f"❌ Ошибка восстановления пользователя {user_id}: {e}")
    
    if restored_count > 0:
        print(f"✅ Восстановлено {restored_count} пользователей")
    else:
        print("ℹ️ Нет сохранённых пользователей для восстановления")

# ===== ЗАПУСК =====
async def main():
    print("🚀 Запуск бота-охотника...")
    print(f"📁 Сессии сохраняются в папку: {SESSION_DIR}")
    print("👥 Поддерживается несколько пользователей одновременно!")
    
    await bot_client.start(bot_token=BOT_TOKEN)
    print("✅ Бот запущен! Жду авторизации...")
    
    # Восстанавливаем пользователей
    await restore_all_users()
    
    await bot_client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())