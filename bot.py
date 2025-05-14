import os
import datetime
import random
import requests
import pytz
from deep_translator import GoogleTranslator
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, MessageHandler, CallbackQueryHandler, filters

# Хранение данных пользователей
user_subscriptions = {}
user_one_time = {}
user_one_time_express = {}
SUBSCRIPTIONS = {
    'week': 7,
    '2weeks': 14,
    'month': 30,
}

# Настройки OddsAPI
ODDS_API_KEY = os.getenv('ODDS_API_KEY', 'd0b434508c21688f0655d4eef265b4c5')
SPORT_KEY = 'soccer'

# Администраторы (ID через запятую в переменной окружения)
ADMIN_IDS = set(int(i) for i in os.getenv('ADMIN_IDS', '').split(',') if i)

def translate_to_english(text):
    try:
        return GoogleTranslator(source='auto', target='en').translate(text)
    except:
        return text

def get_odds_matches():
    matches = []
    tz = pytz.timezone('Europe/Kiev')
    now = datetime.datetime.now(tz)
    url = (
        f'https://api.the-odds-api.com/v4/sports/{SPORT_KEY}/odds'
        f'?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h&oddsFormat=decimal'
    )
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            for match in data:
                home = match['home_team']
                away = match['away_team']
                commence_time = datetime.datetime.fromisoformat(match['commence_time'].replace('Z', '+00:00'))
                commence_kiev = commence_time.astimezone(tz)
                if commence_kiev > now:
                    time_str = commence_kiev.strftime('%H:%M')
                    matches.append(f'{home} vs {away} в {time_str} (по Киеву)')
        else:
            print(f'Ошибка API: {response.status_code} — {response.text}')
    except Exception as e:
        print(f'Ошибка запроса к OddsAPI: {e}')
    return matches

async def start(update: Update, context: CallbackContext):
    keyboard = [
        ['Купить подписку', 'Купить прогноз за $1', 'Купить экспресс за $1'],
        ['Запросить прогноз', 'Экспресс от AI'],
        ['Проверить подписку']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        'Привет! Я AI Sports Bot. Выбирай действие:',
        reply_markup=reply_markup
    )

async def admin_panel(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text('У вас нет доступа к админ-панели.')
        return
    keyboard = [[InlineKeyboardButton('📊 Статистика', callback_data='admin_stats')]]
    await update.message.reply_text('Панель администратора:', reply_markup=InlineKeyboardMarkup(keyboard))

async def generate_ai_prediction():
    matches = get_odds_matches()
    if not matches:
        return 'Сегодня нет матчей или произошла ошибка API.'
    match = random.choice(matches)
    pred = random.choice(['П1','П2','ТБ 2.5','ТМ 2.5','Обе забьют'])
    return f'🎯 Матч: {match}\n🎲 Прогноз: {pred}'

async def generate_ai_express():
    matches = get_odds_matches()
    if len(matches) < 5:
        return 'Недостаточно матчей для экспресса.'
    selected = random.sample(matches, 5)
    response = '⚡ Экспресс от AI:\n'
    for i, m in enumerate(selected,1):
        pred = random.choice(['П1','П2','ТБ 2.5','ТМ 2.5','Обе забьют'])
        response += f'{i}. {m} — {pred}\n'
    return response

async def handle_text(update: Update, context: CallbackContext):
    text = update.message.text
    user_id = update.message.from_user.id
    now = datetime.datetime.now()
    expiry = user_subscriptions.get(user_id)

    if text == '/admin':
        return await admin_panel(update, context)

    if text == 'Купить подписку':
        kb = [[InlineKeyboardButton('1 неделя',callback_data='buy_week'),InlineKeyboardButton('2 недели',callback_data='buy_2weeks'),InlineKeyboardButton('Месяц',callback_data='buy_month')]]
        return await update.message.reply_text('Выберите срок подписки:', reply_markup=InlineKeyboardMarkup(kb))

    if text == 'Купить прогноз за $1':
        user_one_time[user_id] = True
        return await update.message.reply_text('Куплен один прогноз. Нажмите "Запросить прогноз".')

    if text == 'Купить экспресс за $1':
        user_one_time_express[user_id] = True
        return await update.message.reply_text('Куплен один экспресс. Нажмите "Экспресс от AI".')

    if text == 'Запросить прогноз':
        if (expiry and expiry>now) or user_one_time.get(user_id,False):
            resp = await generate_ai_prediction()
            if user_one_time.get(user_id): user_one_time[user_id]=False
            return await update.message.reply_text(resp)
        return await update.message.reply_text('Оформите подписку или купите прогноз за $1.')

    if text == 'Экспресс от AI':
        if user_one_time_express.get(user_id,False):
            resp = await generate_ai_express()
            user_one_time_express[user_id]=False
            return await update.message.reply_text(resp)
        return await update.message.reply_text('Сначала купите экспресс за $1.')

    if text == 'Проверить подписку':
        if expiry and expiry>now:
            return await update.message.reply_text(f'Подписка активна до {expiry.strftime("%Y-%m-%d")}')
        return await update.message.reply_text('У вас нет подписки.')

async def handle_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    now = datetime.datetime.now()

    if query.data == 'admin_stats':
        total_users = len(set(list(user_subscriptions.keys())+list(user_one_time.keys())+list(user_one_time_express.keys())))
        active_subs = sum(1 for d in user_subscriptions.values() if d>now)
        one_time = sum(1 for v in user_one_time.values() if v)
        one_express = sum(1 for v in user_one_time_express.values() if v)
        text = f'👥 Всего пользователей: {total_users}\n✅ Активных подписок: {active_subs}\n🎫 Разовые прогнозы: {one_time}\n⚡ Разовые экспрессы: {one_express}'
        return await query.edit_message_text(text)

    # подписки
    if query.data.startswith('buy_'):
        if query.data=='buy_week': delta=7
        elif query.data=='buy_2weeks': delta=14
        else: delta=30
        user_subscriptions[user_id]=now+datetime.timedelta(days=delta)
        return await query.edit_message_text(f'Подписка на {delta} дней активирована ✅')

if __name__=='__main__':
    TOKEN=os.getenv('YOUR_TELEGRAM_BOT_TOKEN')
    app=ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('admin', admin_panel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()
