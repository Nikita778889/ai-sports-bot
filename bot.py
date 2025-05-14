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
banned_users = set()

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
            for m in response.json():
                home, away = m['home_team'], m['away_team']
                ct = datetime.datetime.fromisoformat(m['commence_time'].replace('Z', '+00:00'))
                ct_kiev = ct.astimezone(tz)
                if ct_kiev > now:
                    matches.append(f"{home} vs {away} в {ct_kiev.strftime('%H:%M')} (по Киеву)")
    except Exception as e:
        print(f'Ошибка запроса к OddsAPI: {e}')
    return matches

async def start(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    if uid in banned_users:
        return
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
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        return
    buttons = [
        [InlineKeyboardButton('📊 Статистика', callback_data='admin_stats')],
        [InlineKeyboardButton('👤 Список пользователей', callback_data='admin_users')],
        [InlineKeyboardButton('🚫 Список заблокированных', callback_data='admin_banned')]
    ]
    await update.message.reply_text('Панель администратора:', reply_markup=InlineKeyboardMarkup(buttons))

async def list_users(update: Update, context: CallbackContext):
    lines = ['— Подписчики и покупки:']
    now = datetime.datetime.now()
    for uid, exp in user_subscriptions.items():
        status = f'подписка до {exp.strftime('%Y-%m-%d')}' if exp > now else 'подписка истекла'
        lines.append(f'{uid}: {status}')
    for uid, flag in user_one_time.items():
        if flag:
            lines.append(f'{uid}: купил разовый прогноз')
    for uid, flag in user_one_time_express.items():
        if flag:
            lines.append(f'{uid}: купил разовый экспресс')
    text = '\n'.join(lines) if lines else 'Нет данных.'
    await update.callback_query.edit_message_text(text)

async def list_banned(update: Update, context: CallbackContext):
    text = 'Заблокированные пользователи:\n' + '\n'.join(str(uid) for uid in banned_users) if banned_users else 'Список пуст.'
    await update.callback_query.edit_message_text(text)

async def ban_user(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        return
    args = context.args
    if not args:
        return await update.message.reply_text('Использование: /ban <user_id>')
    target = int(args[0])
    banned_users.add(target)
    await update.message.reply_text(f'Пользователь {target} заблокирован.')

async def unban_user(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        return
    args = context.args
    if not args:
        return await update.message.reply_text('Использование: /unban <user_id>')
    target = int(args[0])
    banned_users.discard(target)
    await update.message.reply_text(f'Пользователь {target} разблокирован.')

# Генерация прогнозов
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
    sel = random.sample(matches, 5)
    resp = '⚡ Экспресс от AI:\n'
    for i, m in enumerate(sel,1): resp+=f'{i}. {m}\n'
    return resp

async def handle_text(update: Update, context: CallbackContext):
    text = update.message.text
    uid = update.message.from_user.id
    if uid in banned_users:
        return
    now = datetime.datetime.now()
    exp = user_subscriptions.get(uid)

    if text == '/admin':
        return await admin_panel(update, context)

    if text.startswith('/ban') or text.startswith('/unban'):
        return

    if text == 'Купить подписку':
        kb=[[InlineKeyboardButton('1 неделя',callback_data='buy_week'),InlineKeyboardButton('2 недели',callback_data='buy_2weeks'),InlineKeyboardButton('Месяц',callback_data='buy_month')]]
        return await update.message.reply_text('Срок подписки:',reply_markup=InlineKeyboardMarkup(kb))

    if text == 'Купить прогноз за $1':
        user_one_time[uid]=True
        await update.message.reply_text('Куплен прогноз. Нажмите „Запросить прогноз“')
        for aid in ADMIN_IDS: await context.bot.send_message(aid,f'Пользователь {uid} купил прогноз')
        return

    if text == 'Купить экспресс за $1':
        user_one_time_express[uid]=True
        await update.message.reply_text('Куплен экспресс. Нажмите „Экспресс от AI“')
        for aid in ADMIN_IDS: await context.bot.send_message(aid,f'Пользователь {uid} купил экспресс')
        return

    if text == 'Запросить прогноз':
        if (exp and exp>now) or user_one_time.get(uid,False):
            res=await generate_ai_prediction(); user_one_time[uid]=False
            return await update.message.reply_text(res)
        return await update.message.reply_text('Оформите подписку или купите прогноз')

    if text == 'Экспресс от AI':
        if user_one_time_express.get(uid,False):
            res=await generate_ai_express(); user_one_time_express[uid]=False
            return await update.message.reply_text(res)
        return await update.message.reply_text('Купите экспресс')

    if text == 'Проверить подписку':
        if exp and exp>now: return await update.message.reply_text(f'Подписка до {exp.strftime("%Y-%m-%d")}')
        return await update.message.reply_text('Нет подписки')

async def handle_callback(update: Update, context: CallbackContext):
    q=update.callback_query;await q.answer();uid=q.from_user.id;now=datetime.datetime.now()
    data=q.data
    if data=='admin_stats':
        total=len(set(user_subscriptions)|set(user_one_time)|set(user_one_time_express))
        subs=sum(d>now for d in user_subscriptions.values())
        one=sum(user_one_time.values())
        ex=sum(user_one_time_express.values())
        return await q.edit_message_text(f'👥:{total}\n✅:{subs}\n🎫:{one}\n⚡:{ex}')
    if data=='admin_users': return await list_users(update,context)
    if data=='admin_banned': return await list_banned(update,context)
    if data.startswith('buy_'):
        days=7 if data=='buy_week' else 14 if data=='buy_2weeks' else 30
        user_subscriptions[uid]=now+datetime.timedelta(days=days)
        for aid in ADMIN_IDS: await context.bot.send_message(aid,f'Пользователь {uid} оформил подписку на {days} дней')
        return await q.edit_message_text(f'Подписка на {days} дней активирована ✅')

if __name__=='__main__':
    app=ApplicationBuilder().token(os.getenv('YOUR_TELEGRAM_BOT_TOKEN')).build()
    app.add_handler(CommandHandler('start',start))
    app.add_handler(CommandHandler('admin',admin_panel))
    app.add_handler(CommandHandler('ban',ban_user))
    app.add_handler(CommandHandler('unban',unban_user))
    app.add_handler(CommandHandler('revoke_sub',revoke_subscription))
    app.add_handler(CommandHandler('revoke_one',revoke_one_time))
    app.add_handler(CommandHandler('revoke_express',revoke_one_express))
    app.add_handler(MessageHandler(filters.TEXT&~filters.COMMAND,handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()
