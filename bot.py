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

LUCK_CHECK_INTERVAL = datetime.timedelta(hours=48)


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
        [InlineKeyboardButton("Проверить удачу 🎁", callback_data="check_luck")]
    ]
    await update.message.reply_text(
        "Привет! Я AI Sports Bot. Я анализирую матчи и даю лучшие прогнозы по подписке.\nВыбери действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def check_luck(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    now = datetime.datetime.now()
    last_try = user_spin_status.get(user_id, {}).get("last_luck")
    paid_try = user_spin_status.get(user_id, {}).get("paid")

    is_free_try = not last_try or (now - last_try >= LUCK_CHECK_INTERVAL)

    if is_free_try:
        # бесплатная попытка — 5 ячеек, 1 выигрыш
        grid = ["❌"] * 5
        win_index = random.randint(0, 4)
        grid[win_index] = "🎉"
        message = "🎲 Бесплатная попытка: в одной из 5 ячеек спрятан бесплатный прогноз."
        message += "\n\n" + " ".join(grid)
        if grid[win_index] == "🎉":
            user_spin_status[user_id] = {"last_luck": now}
            await query.message.reply_text(message + "\n\n🎁 Вы выиграли бесплатный прогноз!")
        else:
            user_spin_status[user_id] = {"last_luck": now}
            await query.message.reply_text(message + "\n\nУвы, вы не выиграли. Хотите попробовать снова за 5$? В платной попытке 3 ячейки, шанс выше!")
    else:
        # платная попытка — 3 ячейки, 1 выигрыш
        grid = ["❌"] * 3
        win_index = random.randint(0, 2)
        grid[win_index] = "🎁"
        message = "💸 Платная попытка за 5$: выигрыш в одной из 3 ячеек."
        message += "\n\n" + " ".join(grid)
        if grid[win_index] == "🎁":
            await query.message.reply_text(message + "\n\n🎉 Поздравляем! Вы выиграли 1 день доступа к прогнозам!")
        else:
            await query.message.reply_text(message + "\n\n😔 Не повезло. Попробуйте снова позже или оформите подписку.")

if __name__ == '__main__':
    TOKEN = os.getenv("YOUR_TELEGRAM_BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_luck, pattern="^check_luck$"))
    app.run_polling()
