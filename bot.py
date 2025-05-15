# [ВЕСЬ ОБНОВЛЕННЫЙ КОД С УЧЁТОМ УСЛОВИЙ]

import os
import datetime
import random
import requests
import pytz
from deep_translator import GoogleTranslator
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, MessageHandler, CallbackQueryHandler, filters

user_subscriptions = {}
user_one_time = {}
user_one_time_express = {}
payment_requests = {}

SUBSCRIPTIONS = {
    'week': 7,
    '2weeks': 14,
    'month': 30,
}

ODDS_API_KEY = os.getenv('ODDS_API_KEY', 'd0b434508c21688f0655d4eef265b4c5')
SPORT_KEY = 'soccer'

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
        ['Купить подписку', 'Купить прогноз за $1', 'Купить экспресс за $1'],
        ['Запросить прогноз', 'Экспресс от AI'],
        ['Проверить подписку']
    ]
    await update.message.reply_text('Привет! Я AI Sports Bot. Выбирай действие:', reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def admin_panel(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        return
    buttons = [
        [InlineKeyboardButton('📊 Статистика', callback_data='admin_stats')],
        [InlineKeyboardButton('👤 Список пользователей', callback_data='admin_users')],
        [InlineKeyboardButton('✅ Выдать подписку', callback_data='give_sub')],
        [InlineKeyboardButton('🎫 Выдать прогноз', callback_data='give_one')],
        [InlineKeyboardButton('⚡ Выдать экспресс', callback_data='give_express')],
        [InlineKeyboardButton('❌ Удалить подписку', callback_data='remove_sub')],
        [InlineKeyboardButton('❌ Удалить прогноз', callback_data='remove_one')],
        [InlineKeyboardButton('❌ Удалить экспресс', callback_data='remove_express')]
    ]
    await update.message.reply_text('Панель администратора:', reply_markup=InlineKeyboardMarkup(buttons))

async def handle_text(update: Update, context: CallbackContext):
    text = update.message.text
    uid = update.message.from_user.id
    now = datetime.datetime.now()
    exp = user_subscriptions.get(uid)

    if text == '/admin':
        return await admin_panel(update, context)

    if text == 'Купить подписку':
        payment_requests[uid] = 'sub'
        btn = InlineKeyboardMarkup([[InlineKeyboardButton('Я оплатил', callback_data='paid')]])
        return await update.message.reply_text('Оплатите подписку $ и нажмите кнопку ниже.', reply_markup=btn)

    if text == 'Купить прогноз за $1':
        payment_requests[uid] = 'one'
        btn = InlineKeyboardMarkup([[InlineKeyboardButton('Я оплатил', callback_data='paid')]])
        return await update.message.reply_text('Оплатите $1 за прогноз и нажмите «Я оплатил».', reply_markup=btn)

    if text == 'Купить экспресс за $1':
        payment_requests[uid] = 'express'
        btn = InlineKeyboardMarkup([[InlineKeyboardButton('Я оплатил', callback_data='paid')]])
        return await update.message.reply_text('Оплатите $1 за экспресс и нажмите «Я оплатил».', reply_markup=btn)

    if text == 'Запросить прогноз':
        if exp and exp > now or user_one_time.get(uid):
            user_one_time[uid] = False
            return await update.message.reply_text(await generate_ai_prediction())
        return await update.message.reply_text('Нет доступа. Обратитесь к администратору.')

    if text == 'Экспресс от AI':
        if user_one_time_express.get(uid):
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
        return await update.message.reply_text(f'Подписка выдана пользователю {uid} на {days} дней.')

    if action == 'give_one' and len(parts) == 1:
        uid = int(parts[0])
        user_one_time[uid] = True
        return await update.message.reply_text(f'Разовый прогноз выдан пользователю {uid}.')

    if action == 'give_express' and len(parts) == 1:
        uid = int(parts[0])
        user_one_time_express[uid] = True
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, route_messages))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()
