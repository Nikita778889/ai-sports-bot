# [ОБНОВЛЕННЫЙ ПОЛНЫЙ КОД С ПОДДЕРЖКОЙ WELCOME.TXT И WELCOME.JPG ИЗМЕНЕНИЙ]

import os
import datetime
import random
import requests
import pytz
from deep_translator import GoogleTranslator
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, MessageHandler, CallbackQueryHandler, filters

user_subscriptions = {}
user_one_time = {}
user_one_time_express = {}
payment_requests = {}
purchase_history = {}

SUBSCRIPTIONS = {
    'week': 7,
    '2weeks': 14,
    'month': 30,
}

ODDS_API_KEY = os.getenv('ODDS_API_KEY', 'd0b434508c21688f0655d4eef265b4c5')
SPORT_KEY = 'soccer'
WELCOME_TEXT_FILE = 'welcome.txt'
WELCOME_IMAGE_FILE = 'welcome.jpg'

ADMIN_IDS = {553253995}

def translate_to_english(text):
    try:
        return GoogleTranslator(source='auto', target='en').translate(text)
    except Exception:
        return text

def get_odds_matches():
    matches = []
    tz = pytz.timezone('Europe/Kiev')
    now = datetime.datetime.now(tz)
    url = f'https://api.the-odds-api.com/v4/sports/{SPORT_KEY}/odds?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h&oddsFormat=decimal'
    try:
        response = requests.get(url)
        if response.status_code == 200:
            for m in response.json():
                home, away = m['home_team'], m['away_team']
                ct = datetime.datetime.fromisoformat(m['commence_time'].replace('Z', '+00:00'))
                ct_kiev = ct.astimezone(tz)
                if ct_kiev > now:
                    matches.append(f"{home} vs {away} в {ct_kiev.strftime('%H:%M')} (по Киеву)")
    except Exception as e:
        print('Ошибка:', e)
    return matches

async def start(update: Update, context: CallbackContext):
    keyboard = [
        ['Купить подписку на месяц 2000 гривен', 'Купить один прогноз 200 гривен', 'Купить Экспресс из 5 событий 400 гривен'],
        ['Запросить прогноз', 'Экспресс от AI'],
        ['Проверить подписку']
    ]
    text = 'Привет!'
    if os.path.exists(WELCOME_TEXT_FILE):
        with open(WELCOME_TEXT_FILE, 'r', encoding='utf-8') as f:
            text = f.read()
    if os.path.exists(WELCOME_IMAGE_FILE):
        with open(WELCOME_IMAGE_FILE, 'rb') as img:
            await update.message.reply_photo(photo=InputFile(img), caption=text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    else:
        await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def set_welcome(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        return
    text = update.message.text.replace('/set_welcome', '').strip()
    if not text:
        return await update.message.reply_text('Укажи текст приветствия после команды.')
    with open(WELCOME_TEXT_FILE, 'w', encoding='utf-8') as f:
        f.write(text)
    await update.message.reply_text('Текст приветствия обновлён.')

async def save_welcome_image(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        return
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    await file.download_to_drive(WELCOME_IMAGE_FILE)
    await update.message.reply_text('Изображение приветствия обновлено.')

async def notify_user_access(context: CallbackContext, user_id: int, service: str):
    try:
        text = f"✅ Вам выдан доступ к услуге: {service}"
        await context.bot.send_message(chat_id=user_id, text=text)
    except Exception as e:
        print(f"Ошибка отправки уведомления: {e}")


async def give_access_subscription(context: CallbackContext, user_id: int):
    user_subscriptions[user_id] = datetime.datetime.now() + datetime.timedelta(days=30)
    await notify_user_access(context, user_id, "Подписка")

async def give_access_prediction(context: CallbackContext, user_id: int):
    user_one_time[user_id] = True
    await notify_user_access(context, user_id, "Прогноз")

async def give_access_express(context: CallbackContext, user_id: int):
    user_one_time_express[user_id] = True
    await notify_user_access(context, user_id, "Экспресс")
async def admin_panel(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        return

    buttons = [
        [InlineKeyboardButton("📊 Статистика", callback_data='admin_stats')],
        [InlineKeyboardButton("📋 Список пользователей", callback_data='admin_users')],
        [InlineKeyboardButton("📜 История покупок", callback_data='admin_history')],
        [InlineKeyboardButton("✅ Выдать подписку", callback_data='give_sub')],
        [InlineKeyboardButton("📌 Выдать прогноз", callback_data='give_one')],
        [InlineKeyboardButton("⚡ Выдать экспресс", callback_data='give_express')],
        [InlineKeyboardButton("❌ Удалить подписку", callback_data='remove_sub')],
        [InlineKeyboardButton("❌ Удалить прогноз", callback_data='remove_one')],
        [InlineKeyboardButton("❌ Удалить экспресс", callback_data='remove_express')],
        [InlineKeyboardButton("📩 Отправить сообщение", callback_data='send_message')]
    ]
    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("Панель администратора:", reply_markup=markup)

async def send_all_command(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args:
        return await update.message.reply_text("Формат: /sendall сообщение")

    message = ' '.join(context.args)
    all_users = set(user_subscriptions) | set(user_one_time) | set(user_one_time_express) | set(payment_requests) | set(purchase_history)
    all_users.add(update.effective_user.id)
    all_users.update(getattr(context.application, 'user_data', {}).keys())

    count = 0
    for uid in all_users:
        try:
            await context.bot.send_message(chat_id=uid, text=message)
            count += 1
        except:
            continue
    await update.message.reply_text(f"Сообщение отправлено {count} пользователям ✅")


async def send_message_command(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        return
    args = context.args
    if len(args) < 2:
        return await update.message.reply_text("Формат: /send ID сообщение")
    try:
        target_id = int(args[0])
        message = ' '.join(args[1:])
        await context.bot.send_message(chat_id=target_id, text=message)
        await update.message.reply_text("Сообщение отправлено ✅")
    except Exception as e:
        await update.message.reply_text("Ошибка отправки сообщения. Убедитесь, что ID указан верно.")


async def handle_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'send_message':
        context.user_data['awaiting_message_uid'] = True
        await query.message.reply_text("Введите ID пользователя и сообщение через точку с запятой.\nПример: 123456789;Привет!")


async def handle_custom_message(update: Update, context: CallbackContext):
    print(f"🟡 Получено сообщение от {update.effective_user.id}, ожидается ли ввод ID: {context.user_data.get('awaiting_message_uid')}")
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return

    if context.user_data.get('awaiting_message_uid'):
        if not update.message or not update.message.text:
            await update.message.reply_text("Ожидается текстовое сообщение.")
            return
        try:
            text = update.message.text
            if not text or ';' not in text:
                await update.message.reply_text("Неверный формат. Используйте: ID;сообщение")
                return
            target_id_str, message = text.split(';', 1)
            target_id = int(target_id_str.strip())
            await context.bot.send_message(chat_id=target_id, text=message.strip())
            await update.message.reply_text("Сообщение отправлено ✅")
        except Exception as e:
            await update.message.reply_text("Ошибка. Убедитесь, что формат: ID;сообщение")
        finally:
            context.user_data['awaiting_message_uid'] = False

def setup_handlers(app):
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(CommandHandler("send", send_message_command))

async def handle_text(update: Update, context: CallbackContext):
    text = update.message.text
    uid = update.message.from_user.id
    now = datetime.datetime.now()
    exp = user_subscriptions.get(uid)

    if text == '/admin':
        return await admin_panel(update, context)

    if text == 'Купить подписку на месяц 2000 гривен':
        payment_requests[uid] = 'sub'
        btn = InlineKeyboardMarkup([[InlineKeyboardButton('Я оплатил', callback_data='paid')]])
        return await update.message.reply_text('Оплатите подписку 2000 гривен и нажмите кнопку ниже.', reply_markup=btn)

    if text == 'Купить один прогноз 200 гривен':
        payment_requests[uid] = 'one'
        btn = InlineKeyboardMarkup([[InlineKeyboardButton('Я оплатил', callback_data='paid')]])
        return await update.message.reply_text('Оплатите 200 гривен за прогноз и нажмите «Я оплатил».', reply_markup=btn)

    if text == 'Купить Экспресс из 5 событий 400 гривен':
        payment_requests[uid] = 'express'
        btn = InlineKeyboardMarkup([[InlineKeyboardButton('Я оплатил', callback_data='paid')]])
        return await update.message.reply_text('Оплатите 400 гривен за экспресс и нажмите «Я оплатил».', reply_markup=btn)

    if text == 'Запросить прогноз':
        if exp and exp > now or user_one_time.get(uid) is True:
            user_one_time[uid] = False
            return await update.message.reply_text(await generate_ai_prediction())
        return await update.message.reply_text('Нет доступа. Обратитесь к администратору.')

    if text == 'Экспресс от AI':
        if user_one_time_express.get(uid) is True:
            user_one_time_express[uid] = False
            return await update.message.reply_text(await generate_ai_express())
        return await update.message.reply_text('Нет доступа. Обратитесь к администратору.')

    if text == 'Проверить подписку':
        if exp and exp > now:
            return await update.message.reply_text(f'Подписка активна до {exp.strftime("%Y-%m-%d")}')
        return await update.message.reply_text('Подписка не активна.')

async def handle_callback(update: Update, context: CallbackContext):
    q = update.callback_query
    uid = q.from_user.id
    await q.answer()

    if q.data == 'paid':
        req = payment_requests.get(uid)
        if not req:
            return await q.edit_message_text('Нет активного запроса.')
        for aid in ADMIN_IDS:
            await context.bot.send_message(aid, f'Пользователь {uid} оплатил покупку: {req}')
        return await q.edit_message_text('Спасибо! Ожидайте активации.')

    now = datetime.datetime.now()
    if q.data == 'admin_stats':
        total = len(user_subscriptions) + len(user_one_time) + len(user_one_time_express)
        subs = sum(1 for d in user_subscriptions.values() if d > now)
        one = sum(user_one_time.values())
        exp = sum(user_one_time_express.values())
        return await q.edit_message_text(f'👥 Пользователей: {total}\n✅ Подписок: {subs}\n🎫 Прогнозов: {one}\n⚡ Экспрессов: {exp}')

    if q.data == 'admin_users':
        lines = []
        for u in user_subscriptions:
            status = user_subscriptions[u].strftime('%Y-%m-%d')
            lines.append(f'{u}: подписка до {status}')
        for u in user_one_time:
            if user_one_time[u]: lines.append(f'{u}: разовый прогноз')
        for u in user_one_time_express:
            if user_one_time_express[u]: lines.append(f'{u}: разовый экспресс')
        return await q.edit_message_text('\n'.join(lines) or 'Нет пользователей.')

    if q.data == 'admin_history':
        lines = []
        for uid, entries in purchase_history.items():
            lines.append(f'{uid}: ' + ', '.join(entries))
        return await q.edit_message_text('\n'.join(lines) or 'Покупок нет.')

    if q.data == 'give_sub':
        context.user_data['admin_action'] = 'give_sub'
        return await q.edit_message_text('Введите ID и срок в днях (пример: 123456789 7)')

    if q.data == 'give_one':
        context.user_data['admin_action'] = 'give_one'
        return await q.edit_message_text('Введите ID пользователя для выдачи прогноза:')

    if q.data == 'give_express':
        context.user_data['admin_action'] = 'give_express'
        return await q.edit_message_text('Введите ID пользователя для выдачи экспресса:')

    if q.data == 'remove_sub':
        context.user_data['admin_action'] = 'remove_sub'
        return await q.edit_message_text('Введите ID пользователя для удаления подписки:')

    if q.data == 'remove_one':
        context.user_data['admin_action'] = 'remove_one'
        return await q.edit_message_text('Введите ID пользователя для удаления прогноза:')

    if q.data == 'remove_express':
        context.user_data['admin_action'] = 'remove_express'
        return await q.edit_message_text('Введите ID пользователя для удаления экспресса:')

async def generate_ai_prediction():
    matches = get_odds_matches()
    if not matches:
        return 'Нет матчей сегодня.'
    match = random.choice(matches)
    pred = random.choice(['П1','П2','ТБ 2.5','ТМ 2.5','Обе забьют'])
    return f'🎯 Матч: {match}\n🎲 Прогноз: {pred}'

async def generate_ai_express():
    matches = get_odds_matches()
    if len(matches) < 5:
        return 'Недостаточно матчей.'
    sel = random.sample(matches, 5)
    return '⚡ Экспресс:\n' + '\n'.join(f'{i+1}. {m}' for i, m in enumerate(sel))

async def process_admin_input(update: Update, context: CallbackContext):
    if 'admin_action' not in context.user_data:
        return
    action = context.user_data['admin_action']
    context.user_data['admin_action'] = None
    parts = update.message.text.strip().split()

    if action == 'give_sub' and len(parts) == 2:
        uid, days = int(parts[0]), int(parts[1])
        user_subscriptions[uid] = datetime.datetime.now() + datetime.timedelta(days=days)
        purchase_history.setdefault(uid, []).append(f'Подписка {days}д')
        return await update.message.reply_text(f'Подписка выдана пользователю {uid} на {days} дней.')

    if action == 'give_one' and len(parts) == 1:
        uid = int(parts[0])
        user_one_time[uid] = True
        purchase_history.setdefault(uid, []).append('Разовый прогноз')
        return await update.message.reply_text(f'Разовый прогноз выдан пользователю {uid}.')

    if action == 'give_express' and len(parts) == 1:
        uid = int(parts[0])
        user_one_time_express[uid] = True
        purchase_history.setdefault(uid, []).append('Разовый экспресс')
        return await update.message.reply_text(f'Разовый экспресс выдан пользователю {uid}.')

    if action == 'remove_sub' and len(parts) == 1:
        uid = int(parts[0])
        user_subscriptions.pop(uid, None)
        return await update.message.reply_text(f'Подписка у пользователя {uid} удалена.')

    if action == 'remove_one' and len(parts) == 1:
        uid = int(parts[0])
        user_one_time.pop(uid, None)
        return await update.message.reply_text(f'Прогноз у пользователя {uid} удален.')

    if action == 'remove_express' and len(parts) == 1:
        uid = int(parts[0])
        user_one_time_express.pop(uid, None)
        return await update.message.reply_text(f'Экспресс у пользователя {uid} удален.')

async def route_messages(update: Update, context: CallbackContext):
    if 'admin_action' in context.user_data:
        await process_admin_input(update, context)
    else:
        await handle_text(update, context)

if __name__ == '__main__':
    app = ApplicationBuilder().token(os.getenv('YOUR_TELEGRAM_BOT_TOKEN')).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('admin', admin_panel))
    app.add_handler(CommandHandler('set_welcome', set_welcome))
    app.add_handler(CommandHandler('send', send_message_command))
    app.add_handler(CommandHandler('sendall', send_all_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, route_messages))
    app.add_handler(MessageHandler(filters.PHOTO, save_welcome_image))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()
