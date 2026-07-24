from telethon import TelegramClient, events, Button
from telethon.tl.types import KeyboardButton, ChatAdminRights
from telethon.tl.functions.messages import CreateChatRequest, AddChatUserRequest, EditChatAdminRequest
from telethon.errors import SessionPasswordNeededError
import asyncio
import re
import time
import os

# ===== КОНФИГ =====
BOT_TOKEN = "8695263973:AAHge3QFURlz1nOJVtGmdav5HQ2NL5-RjeI"
API_ID = 25569323
API_HASH = "061bad708728d3d928054f16c932de6d"

# ===== СПИСОК БОССОВ (НОВЫЙ) =====
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

# ===== ПЕРЕМЕННЫЕ =====
user_client = None
is_active = False
selected_bosses = set()
chat_id = None
chat_created = False
current_target = None
last_equip_time = 0
bot_username = "IsekaiGlobal_bot"

# ===== АВТОРИЗАЦИЯ =====
bot_client = TelegramClient('bot_session', API_ID, API_HASH)

# ===== КЛАВИАТУРЫ =====
def get_main_keyboard():
    toggle = "❌ ВЫКЛЮЧИТЬ" if is_active else "✅ ВКЛЮЧИТЬ"
    return [
        [KeyboardButton(toggle)],
        [KeyboardButton("🎯 ВЫБРАТЬ БОССОВ")],
        [KeyboardButton("📊 СТАТУС БОССОВ"), KeyboardButton("🔄 ОБНОВИТЬ")]
    ]

def get_bosses_keyboard():
    buttons, row = [], []
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
    global user_client, chat_id, chat_created, is_active, selected_bosses, current_target
    
    if not event.is_private:
        return
    
    text = event.raw_text
    user_id = event.sender_id
    
    if user_client:
        await handle_commands(event, text)
        return
    
    if text == '/start' or text == 'начать':
        await event.respond(
            "🔐 **Добро пожаловать!**\n\n"
            "📱 Отправь свой номер телефона в формате:\n"
            "`+79991234567`",
            buttons=Button.clear()
        )
        return
    
    if re.match(r'^\+?\d{10,15}$', text):
        await handle_phone(event, text)
        return
    
    if re.match(r'^\d{3,8}$', text):
        await handle_code(event, text)
        return

async def handle_phone(event, phone):
    global user_client
    
    try:
        session_name = f'user_{phone.replace("+", "")}'
        client = TelegramClient(session_name, API_ID, API_HASH)
        await client.connect()
        
        if await client.is_user_authorized():
            user_client = client
            me = await client.get_me()
            await event.respond(f"✅ Сессия восстановлена для {me.first_name}!", buttons=get_main_keyboard())
            await create_or_get_chat()
            asyncio.create_task(main_loop())
            return
        
        await client.send_code_request(phone)
        user_client = client
        await event.respond(
            f"✅ Код отправлен на `{phone}`!\n\n"
            f"✏️ Отправь код из Telegram:",
            buttons=get_code_keyboard()
        )
        
    except Exception as e:
        await event.respond(f"❌ Ошибка: {e}")

async def handle_code(event, code):
    global user_client
    
    if not user_client:
        await event.respond("❌ Сначала отправь номер телефона!")
        return
    
    try:
        await user_client.sign_in(code=code)
        me = await user_client.get_me()
        await event.respond(f"✅ Успешный вход! {me.first_name}!", buttons=get_main_keyboard())
        await create_or_get_chat()
        asyncio.create_task(main_loop())
        
    except SessionPasswordNeededError:
        await event.respond("🔐 Требуется пароль! Отправь пароль:")
        return
        
    except Exception as e:
        await event.respond(f"❌ Неверный код: {e}")

# ===== СОЗДАНИЕ ЧАТА =====
async def create_or_get_chat():
    global user_client, chat_id, chat_created
    
    try:
        me = await user_client.get_me()
        chat_name = f"МБЛ ({me.username or me.first_name})"
        
        async for dialog in user_client.iter_dialogs():
            if dialog.name == chat_name:
                chat_id = dialog.id
                chat_created = True
                print(f"✅ Найден чат: {chat_name}")
                await give_admin_rights(chat_id)
                return
        
        result = await user_client(CreateChatRequest(
            users=[bot_username],
            title=chat_name
        ))
        chat_id = result.chats[0].id
        chat_created = True
        print(f"✅ Чат создан: {chat_name}")
        await give_admin_rights(chat_id)
        await user_client.send_message(chat_id, "🤖 Бот активирован!")
        
    except Exception as e:
        print(f"❌ Ошибка чата: {e}")
        chat_created = False

async def give_admin_rights(chat_id):
    try:
        bot = await user_client.get_entity(bot_username)
        rights = ChatAdminRights(
            change_info=True, post_messages=True, edit_messages=True,
            delete_messages=True, ban_users=True, invite_users=True,
            pin_messages=True, add_admins=True, anonymous=False,
            manage_call=True, other=True
        )
        await user_client(EditChatAdminRequest(chat_id=chat_id, user_id=bot, rights=rights, is_admin=True))
        print(f"✅ {bot_username} получил права")
    except Exception as e:
        print(f"⚠️ Ошибка прав: {e}")

# ===== АВТО ПОЧИНКА (ЭКИПИРОВКА) =====
async def do_equip():
    """Выполняет экипировку: пишет 'экип', нажимает 8-ю кнопку (слоты), затем 6-ю"""
    global user_client
    
    try:
        print("🔧 Начинаю экипировку...")
        
        # 1. Пишем "экип"
        await user_client.send_message(bot_username, "экип")
        print("✏️ Отправил 'экип'")
        await asyncio.sleep(1)
        
        # 2. Получаем сообщение с кнопками
        messages = await user_client.get_messages(bot_username, limit=2)
        if not messages:
            print("❌ Нет сообщений от бота")
            return
        
        # 3. Ищем кнопку №8 (слоты) - индекс 7
        for msg in messages:
            if msg.buttons:
                flat_buttons = [btn for row in msg.buttons for btn in row]
                
                # Нажимаем 8-ю кнопку (индекс 7)
                if len(flat_buttons) >= 8:
                    await asyncio.sleep(1)
                    await msg.click(7)
                    print("✅ Нажата 8-я кнопка (Слоты)")
                    await asyncio.sleep(1)
                    
                    # 4. Получаем новое сообщение с кнопками
                    new_messages = await user_client.get_messages(bot_username, limit=2)
                    if new_messages:
                        for new_msg in new_messages:
                            if new_msg.buttons:
                                new_buttons = [btn for row in new_msg.buttons for btn in row]
                                
                                # Нажимаем 6-ю кнопку (индекс 5)
                                if len(new_buttons) >= 6:
                                    await asyncio.sleep(1)
                                    await new_msg.click(5)
                                    print("✅ Нажата 6-я кнопка")
                                    await asyncio.sleep(1)
                                    break
                    break
        
        print("✅ Экипировка завершена!")
        
    except Exception as e:
        print(f"❌ Ошибка экипировки: {e}")

# ===== ОСНОВНОЙ ЦИКЛ =====
async def main_loop():
    global is_active, selected_bosses, chat_id, user_client, chat_created, current_target, last_equip_time
    
    print("🔄 Цикл запущен!")
    
    while True:
        try:
            if not user_client or not is_active or not selected_bosses or not chat_created:
                await asyncio.sleep(20)
                continue
            
            current_time = time.time()
            
            # ===== АВТО ПОЧИНКА (раз в 20 минут) =====
            if current_time - last_equip_time >= 1200:
                print("⏰ Пора делать экипировку!")
                await do_equip()
                last_equip_time = current_time
                print("⏳ Жду 5 секунд после экипировки...")
                await asyncio.sleep(5)
                continue
            
            # ===== ОХОТА =====
            await user_client.send_message(chat_id, "бл")
            print("📤 Отправлен 'бл'")
            await asyncio.sleep(2)
            
            messages = await user_client.get_messages(chat_id, limit=10)
            boss_message = None
            bot_entity = await user_client.get_entity(bot_username)
            
            for msg in messages:
                if msg.sender_id == bot_entity.id:
                    boss_message = msg.text
                    break
            
            if not boss_message:
                await asyncio.sleep(20)
                continue
            
            if current_target is not None:
                boss = BOSSES[current_target]
                pattern = rf"{boss['emoji']}.*{boss['name']}.*(Жив!|\d+[мс. ]+\d*[мс.]*)"
                match = re.search(pattern, boss_message)
                
                if match:
                    status = match.group(1)
                    if status == "Жив!":
                        print(f"⏳ {boss['name']} ещё жив, жду...")
                        await asyncio.sleep(20)
                        continue
                    else:
                        print(f"💀 {boss['name']} умер! Разблокирую...")
                        current_target = None
                        await asyncio.sleep(20)
                        continue
            
            alive_bosses = []
            for index in selected_bosses:
                boss = BOSSES[index]
                pattern = rf"{boss['emoji']}.*{boss['name']}.*(Жив!|\d+[мс. ]+\d*[мс.]*)"
                match = re.search(pattern, boss_message)
                
                if match and match.group(1) == "Жив!":
                    alive_bosses.append(index)
                    print(f"🔥 {boss['name']} жив!")
            
            if alive_bosses:
                boss_index = alive_bosses[0]
                boss = BOSSES[boss_index]
                
                print(f"⚔️ Атакую {boss['name']}...")
                success = await attack_boss(boss_index)
                
                if success:
                    current_target = boss_index
                    print(f"✅ {boss['name']} атакован! Жду смерти...")
            
            await asyncio.sleep(20)
            
        except Exception as e:
            print(f"❌ Ошибка цикла: {e}")
            await asyncio.sleep(20)

# ===== АТАКА БОССА =====
async def attack_boss(boss_index):
    global user_client
    
    try:
        await user_client.send_message(bot_username, "бо")
        await asyncio.sleep(2)
        
        messages = await user_client.get_messages(bot_username, limit=2)
        if not messages:
            return False
        
        for msg in messages:
            if msg.buttons:
                flat_buttons = [btn for row in msg.buttons for btn in row]
                if boss_index < len(flat_buttons):
                    await msg.click(boss_index)
                    print(f"✅ Нажата кнопка {boss_index + 1}")
                    
                    await asyncio.sleep(1)
                    await user_client.send_message(bot_username, "ав+")
                    print("✅ Отправлено 'ав+'")
                    return True
        
        return False
        
    except Exception as e:
        print(f"❌ Ошибка атаки: {e}")
        return False

# ===== ОБРАБОТКА КОМАНД =====
async def handle_commands(event, text):
    global is_active, selected_bosses, current_target, chat_id
    
    if text in ["✅ ВКЛЮЧИТЬ", "❌ ВЫКЛЮЧИТЬ"]:
        is_active = not is_active
        if not is_active:
            current_target = None
        await event.respond(
            f"📊 Статус: {'🟢 ВКЛЮЧЕН' if is_active else '🔴 ВЫКЛЮЧЕН'}",
            buttons=get_main_keyboard()
        )
    
    elif text == "🎯 ВЫБРАТЬ БОССОВ":
        await event.respond("🎯 Выбери боссов:", buttons=get_bosses_keyboard())
    
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
        await event.respond("🔄 Обновляю...")
    
    elif text == "🔙 НАЗАД":
        await event.respond("🔙 Назад", buttons=get_main_keyboard())
    
    elif any(emoji in text for emoji in ["✅", "⬜"]):
        for i, boss in enumerate(BOSSES):
            if boss['emoji'] in text:
                if i in selected_bosses:
                    selected_bosses.remove(i)
                    if current_target == i:
                        current_target = None
                else:
                    selected_bosses.add(i)
                
                await event.respond(
                    f"{'✅ Выбран' if i in selected_bosses else '❌ Убран'} {boss['name']}",
                    buttons=get_bosses_keyboard()
                )
                break

# ===== ЗАПУСК =====
async def main():
    print("🚀 Запуск бота...")
    await bot_client.start(bot_token=BOT_TOKEN)
    print("✅ Бот запущен!")
    await bot_client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())