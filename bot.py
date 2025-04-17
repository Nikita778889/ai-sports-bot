import os
import datetime
import random
import requests
import pytz
from deep_translator import GoogleTranslator
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, MessageHandler, CallbackQueryHandler, filters

user_subscriptions = {}
SUBSCRIPTIONS = {
    'week': 7,
    '2weeks': 14,
    'month': 30,
}

user_luck = {}
LUCK_INTERVAL = datetime.timedelta(hours=48)

API_KEY = "1b3004c7259586cf921ab379bc84fd7a"
API_URL = "https://v3.football.api-sports.io/fixtures?date={date}"
HEADERS = {
    "x-apisports-key": API_KEY
}

def translate_to_english(text):
    try:
        return GoogleTranslator(source='auto', target='en').translate(text)
    except:
        return text

def get_today_matches():
    tz = pytz.timezone("Europe/Kiev")
    now = datetime.datetime.now(tz)
    today = now.date().isoformat()
    response = requests.get(API_URL.format(date=today), headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        matches = []
        for fixture in data.get("response", []):
            match_time_utc = datetime.datetime.fromisoformat(fixture["fixture"]["date"].replace("Z", "+00:00"))
            match_time_kiev = match_time_utc.astimezone(tz)

            if match_time_kiev > now:
                teams = fixture["teams"]
                time_str = match_time_kiev.strftime('%H:%M')
                match_str = f"{teams['home']['name']} vs {teams['away']['name']} в {time_str} (по Киеву)"
                matches.append(match_str)
        return matches
    return []

def find_match_by_name(name):
    name = translate_to_english(name)
    tz = pytz.timezone("Europe/Kiev")
    now = datetime.datetime.now(tz)
    today = now.date().isoformat()
    response = requests.get(API_URL.format(date=today), headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        for fixture in data.get("response", []):
            home = fixture["teams"]["home"]["name"].lower()
            away = fixture["teams"]["away"]["name"].lower()
            full_name = f"{home} vs {away}"
            if name.lower() in full_name:
                match_time_utc = datetime.datetime.fromisoformat(fixture["fixture"]["date"].replace("Z", "+00:00"))
                match_time_kiev = match_time_utc.astimezone(tz)
                time_str = match_time_kiev.strftime('%H:%M')
                match_str = f"{fixture['teams']['home']['name']} vs {fixture['teams']['away']['name']} в {time_str} (по Киеву)"
                return match_str
    return None

async def start(update: Update, context: CallbackContext):
    keyboard = [[
        KeyboardButton("Купить подписку"),
        KeyboardButton("Запросить прогноз"),
        KeyboardButton("Экспресс от AI")
    ], [
        KeyboardButton("Прогноз по матчу"),
        KeyboardButton("Проверить подписку"),
        KeyboardButton("Проверить удачу")
    ]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Привет! Я AI Sports Bot. Я анализирую матчи и даю лучшие прогнозы по подписке.\nВыбери действие:",
        reply_markup=reply_markup
    )

async def handle_text(update: Update, context: CallbackContext):
    text = update.message.text
    user_id = update.message.from_user.id
    now = datetime.datetime.now()

    if text == "Проверить удачу":
        keyboard = [
            [InlineKeyboardButton("🎯 Бесплатная попытка", callback_data='free_luck')],
            [InlineKeyboardButton("💰 Платная попытка за $5", callback_data='paid_luck')]
        ]
        await update.message.reply_text("Выберите тип попытки:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    now = datetime.datetime.now()

    if query.data == "free_luck":
        last_try = user_luck.get(user_id)
        if last_try and now - last_try < LUCK_INTERVAL:
            remaining = LUCK_INTERVAL - (now - last_try)
            hours, remainder = divmod(remaining.total_seconds(), 3600)
            minutes = remainder // 60
            await query.edit_message_text(f"⏳ Вы уже использовали бесплатную попытку. Подождите ещё {int(hours)}ч {int(minutes)}м.")
        else:
            user_luck[user_id] = now
            win_index = random.randint(0, 4)
            context.user_data['luck_type'] = 'free'
            context.user_data['win_index'] = win_index
            keyboard = [[InlineKeyboardButton("❓", callback_data=f"try_luck_{i}") for i in range(5)]]
            await query.edit_message_text("🎲 Бесплатная попытка: выберите ячейку:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "paid_luck":
        win_index = random.randint(0, 2)
        context.user_data['luck_type'] = 'paid'
        context.user_data['win_index'] = win_index
        keyboard = [[InlineKeyboardButton("❓", callback_data=f"try_luck_{i}") for i in range(3)]]
        await query.edit_message_text("💵 Платная попытка за $5: выберите ячейку:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("try_luck_"):
        choice = int(query.data.split("_")[-1])
        win_index = context.user_data.get('win_index')
        luck_type = context.user_data.get('luck_type')

        if win_index is None or luck_type not in ['free', 'paid']:
            await query.edit_message_text("Произошла ошибка. Попробуйте снова.")
            return

        if choice == win_index:
            if luck_type == 'free':
                await query.edit_message_text("🎉 Вы выиграли бесплатный прогноз!")
            else:
                user_subscriptions[user_id] = datetime.datetime.now() + datetime.timedelta(days=1)
                await query.edit_message_text("🎊 Победа! Вы получаете 1 день доступа.")
        else:
            if luck_type == 'free':
                await query.edit_message_text("😔 Не повезло! Попробуйте снова позже или воспользуйтесь платной попыткой.")
            else:
                await query.edit_message_text("😞 Увы, не повезло! Попробуйте снова позже.")
