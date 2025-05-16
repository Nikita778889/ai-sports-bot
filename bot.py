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
        ['Купить подписку на месяц 1500 гривен', 'Купить один прогноз 200 гривен', 'Купить Экспресс из 5 событий 400 гривен'],
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

# функция для уведомления пользователя после выдачи доступа
async def notify_user_access(context: CallbackContext, user_id: int, service: str):
    try:
        text = f"✅ Вам выдан доступ к услуге: {service}"
        await context.bot.send_message(chat_id=user_id, text=text)
    except Exception as e:
        print(f"Ошибка отправки уведомления: {e}")

# вызовы уведомлений
async def give_access_subscription(context: CallbackContext, user_id: int):
    user_subscriptions[user_id] = datetime.datetime.now() + datetime.timedelta(days=30)
    await notify_user_access(context, user_id, "Подписка")

async def give_access_prediction(context: CallbackContext, user_id: int):
    user_one_time[user_id] = True
    await notify_user_access(context, user_id, "Прогноз")

async def give_access_express(context: CallbackContext, user_id: int):
    user_one_time_express[user_id] = True
    await notify_user_access(context, user_id, "Экспресс")

# АВТОМАТИЧЕСКИЕ ВСТАВКИ В АДМИН-ПАНЕЛЬ:
# - при выдаче подписки вызывай: await give_access_subscription(context, user_id)
# - при выдаче прогноза вызывай: await give_access_prediction(context, user_id)
# - при выдаче экспресса вызывай: await give_access_express(context, user_id)

# остальной код без изменений ниже...

# ПРИМЕР ВСТАВКИ В АДМИН-КОЛБЭК:
async def handle_text(update: Update, context: CallbackContext):
    text = update.message.text

    if context.user_data.get('awaiting_uid') == 'give_sub':
        try:
            user_id = int(text)
            await give_access_subscription(context, user_id)
            await update.message.reply_text("Подписка выдана.")
        except Exception:
            await update.message.reply_text("Ошибка выдачи подписки.")
        context.user_data['awaiting_uid'] = None

    elif context.user_data.get('awaiting_uid') == 'give_one':
        try:
            user_id = int(text)
            await give_access_prediction(context, user_id)
            await update.message.reply_text("Прогноз выдан.")
        except Exception:
            await update.message.reply_text("Ошибка выдачи прогноза.")
        context.user_data['awaiting_uid'] = None

    elif context.user_data.get('awaiting_uid') == 'give_express':
        try:
            user_id = int(text)
            await give_access_express(context, user_id)
            await update.message.reply_text("Экспресс выдан.")
        except Exception:
            await update.message.reply_text("Ошибка выдачи экспресса.")
        context.user_data['awaiting_uid'] = None

async def handle_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'give_sub':
        context.user_data['awaiting_uid'] = 'give_sub'
        await query.message.reply_text("Введите ID пользователя для выдачи подписки:")
    elif data == 'give_one':
        context.user_data['awaiting_uid'] = 'give_one'
        await query.message.reply_text("Введите ID пользователя для выдачи прогноза:")
    elif data == 'give_express':
        context.user_data['awaiting_uid'] = 'give_express'
        await query.message.reply_text("Введите ID пользователя для выдачи экспресса:")
