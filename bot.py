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

# Администраторы
ADMIN_IDS = {553253995}  # ваш Telegram ID

def translate_to_english(text):
    try:
        return GoogleTranslator(source='auto', target='en').translate(text)
    except Exception:
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
            for m in data:
                home, away = m['home_team'], m['away_team']
                ct = datetime.datetime.fromisoformat(m['commence_time'].replace('Z', '+00:00'))
                ct_kiev = ct.astimezone(tz)
                if ct_kiev > now:
                    matches.append(f"{home} vs {away} в {ct_kiev.strftime('%H:%M')} (по Киеву)")
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
    await update.message.reply_text(
        'Привет! Я AI Sports Bot. Выбирай действие:',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# Админ: панель и команды
async def admin_panel(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return await update.message.reply_text('У вас нет доступа к админ-панели.')
    buttons = [
        [InlineKeyboardButton('📊 Статистика', callback_data='admin_stats')],
        [InlineKeyboardButton('👤 Список пользователей', callback_data='admin_users')]
    ]
    await update.message.reply_text('Панель администратора:', reply_markup=InlineKeyboardMarkup(buttons))

async def list_users(update: Update, context: CallbackContext):
    # вывод списка пользователей и их статуса
    lines = ['Пользователи и их покупки:']
    now = datetime.datetime.now()
    for uid, exp in user_subscriptions.items():
        status = f'подписка до {exp.strftime("%Y-%m-%d")}' if exp>now else 'подписка истекла'
        lines.append(f'- {uid}: {status}')
    for uid, flag in user_one_time.items():
        if flag:
            lines.append(f'- {uid}: купил один прогноз')
    for uid, flag in user_one_time_express.items():
        if flag:
            lines.append(f'- {uid}: купил один экспресс')
    text = '\n'.join(lines) or 'Нет данных о пользователях.'
    await update.callback_query.edit_message_text(text)

async def revoke_subscription(update: Update, context: CallbackContext):
    # /revoke_sub <user_id>
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return await update.message.reply_text('Доступ запрещен.')
    args = context.args
    if not args:
        return await update.message.reply_text('Укажи ID пользователя: /revoke_sub <ID>')
    uid = int(args[0])
    if uid in user_subscriptions:
        del user_subscriptions[uid]
        return await update.message.reply_text(f'Подписка пользователя {uid} удалена.')
    await update.message.reply_text('У пользователя нет подписки.')

async def revoke_one_time(update: Update, context: CallbackContext):
    # /revoke_one <user_id>
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return await update.message.reply_text('Доступ запрещен.')
    args = context.args
    if not args:
        return await update.message.reply_text('Укажи ID пользователя: /revoke_one <ID>')
    uid = int(args[0])
    if user_one_time.get(uid):
        user_one_time[uid] = False
        return await update.message.reply_text(f'Разовый прогноз пользователя {uid} сброшен.')
    await update.message.reply_text('У пользователя нет разовой покупки прогноза.')

async def revoke_one_express(update: Update, context: CallbackContext):
    # /revoke_express <user_id>
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return await update.message.reply_text('Доступ запрещен.')
    args = context.args
    if not args:
        return await update.message.reply_text('Укажи ID пользователя: /revoke_express <ID>')
    uid = int(args[0])
    if user_one_time_express.get(uid):
        user_one_time_express[uid] = False
        return await update.message.reply_text(f'Разовый экспресс пользователя {uid} сброшен.')
    await update.message.reply_text('У пользователя нет разовой покупки экспресса.')

async def generate_ai_prediction(update: Update=None):
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
    sel = random.sample(matches,5)
    resp = '⚡ Экспресс от AI:\n'
    for i,m in enumerate(sel,1): resp+=f'{i}. {m}\n'
    return resp
async def handle_text(update: Update, context: CallbackContext):
    text = update.message.text
    uid = update.message.from_user.id
    now = datetime.datetime.now()
    exp = user_subscriptions.get(uid)

    if text == '/admin': return await admin_panel(update,context)
    if text == 'Купить подписку':
        kb=[[InlineKeyboardButton('1 неделя',callback_data='buy_week'),InlineKeyboardButton('2 недели',callback_data='buy_2weeks'),InlineKeyboardButton('Месяц',callback_data='buy_month')]]
        return await update.message.reply_text('Выберите срок подписки:',reply_markup=InlineKeyboardMarkup(kb))
    if text == 'Купить прогноз за $1': user_one_time[uid]=True; return await update.message.reply_text('Куплен прогноз. Нажмите запросить прогноз.')
    if text == 'Купить экспресс за $1': user_one_time_express[uid]=True; return await update.message.reply_text('Куплен экспресс. Нажмите экспресс от AI.')
    if text == 'Запросить прогноз':
        if (exp and exp>now) or user_one_time.get(uid,False):
            res=await generate_ai_prediction(); user_one_time[uid]=False; return await update.message.reply_text(res)
        return await update.message.reply_text('Оформи подписку или купи прогноз за $1.')
    if text == 'Экспресс от AI':
        if user_one_time_express.get(uid,False): res=await generate_ai_express(); user_one_time_express[uid]=False; return await update.message.reply_text(res)
        return await update.message.reply_text('Купи экспресс за $1.')
    if text=='Проверить подписку':
        if exp and exp>now: return await update.message.reply_text(f'Подписка до {exp.strftime("%Y-%m-%d")}')
        return await update.message.reply_text('Нет подписки.')

async def handle_callback(update: Update, context: CallbackContext):
    q=update.callback_query; await q.answer(); uid=q.from_user.id; now=datetime.datetime.now()
    if q.data=='admin_stats':
        total=len(set(list(user_subscriptions.keys())+list(user_one_time.keys())+list(user_one_time_express.keys())))
        subs=sum(1 for d in user_subscriptions.values() if d>now)
        one=sum(1 for v in user_one_time.values() if v)
        ex=sum(1 for v in user_one_time_express.values() if v)
        return await q.edit_message_text(f'👥Пользователей: {total}\n✅Подписок: {subs}\n🎫Прогнозов: {one}\n⚡Экспрессов: {ex}')
    if q.data=='admin_users': return await list_users(update,context)
    if q.data.startswith('buy_'):
        days=7 if q.data=='buy_week' else 14 if q.data=='buy_2weeks' else 30
        user_subscriptions[uid]=now+datetime.timedelta(days=days)
        return await q.edit_message_text(f'Подписка на {days} дней активирована ✅')

if __name__=='__main__':
    app=ApplicationBuilder().token(os.getenv('YOUR_TELEGRAM_BOT_TOKEN')).build()
    app.add_handler(CommandHandler('start',start))
    app.add_handler(CommandHandler('admin',admin_panel))
    app.add_handler(CommandHandler('revoke_sub',revoke_subscription))
    app.add_handler(CommandHandler('revoke_one',revoke_one_time))
    app.add_handler(CommandHandler('revoke_express',revoke_one_express))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()
