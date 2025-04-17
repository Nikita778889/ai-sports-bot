import os
import datetime
import random
import requests
import pytz
import asyncio
from deep_translator import GoogleTranslator
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, MessageHandler, CallbackQueryHandler, filters

user_subscriptions = {}
user_spin_status = {}
SUBSCRIPTIONS = {
    'week': 7,
    '2weeks': 14,
    'month': 30,
}

API_KEY = "1b3004c7259586cf921ab379bc84fd7a"
API_URL = "https://v3.football.api-sports.io/fixtures?date={date}"
HEADERS = {"x-apisports-key": API_KEY}

FREE_SPIN_INTERVAL = datetime.timedelta(hours=48)
WHEEL_SPIN_GIF_URL = "https://media.giphy.com/media/3og0IOUWBvU5S2F1ja/giphy.gif"
WHEEL_IMAGE_URL = "https://i.imgur.com/JQ2W8Te.png"
WHEEL_WIN_GIF_URL = "https://media.giphy.com/media/26AHONQ79FdWZhAI0/giphy.gif"

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
                matches.append(f"{teams['home']['name']} vs {teams['away']['name']} в {time_str} (по Киеву)")
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
                return f"{fixture['teams']['home']['name']} vs {fixture['teams']['away']['name']} в {time_str} (по Киеву)"
    return None

async def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("Купить подписку", callback_data="buy_menu")],
        [InlineKeyboardButton("Запросить прогноз", callback_data="get_prediction")],
        [InlineKeyboardButton("Экспресс от AI", callback_data="get_express")],
        [InlineKeyboardButton("Прогноз по матчу", callback_data="match_prompt")],
        [InlineKeyboardButton("Проверить подписку", callback_data="check_sub")],
        [InlineKeyboardButton("🎡 Крутануть колесо", callback_data="spin_wheel")]
    ]
    await update.message.reply_text(
        "Привет! Я AI Sports Bot. Я анализирую матчи и даю лучшие прогнозы по подписке.\nВыбери действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# остальной код остается без изменений
