import os
import datetime
import random
import requests
import pytz
from deep_translator import GoogleTranslator
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, MessageHandler, CallbackQueryHandler, filters

user_subscriptions = {}
SUBSCRIPTIONS = {
    'week': 7,
    '2weeks': 14,
    'month': 30,
}

ODDS_API_KEY = "d0b434508c21688f0655d4eef265b4c5"
SPORT_KEY = "soccer"

def translate_to_english(text):
    try:
        return GoogleTranslator(source='auto', target='en').translate(text)
    except:
        return text

def get_odds_matches():
    matches = []
    tz = pytz.timezone("Europe/Kiev")
    now = datetime.datetime.now(tz)

    url = (
        f"https://api.the-odds-api.com/v4/sports/{SPORT_KEY}/odds"
        f"?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h&oddsFormat=decimal"
    )

    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            for match in data:
                home = match['home_team']
                away = match['away_team']
                match_time = datetime.datetime.fromisoformat(match['commence_time'].replace("Z", "+00:00"))
                match_time_kiev = match_time.astimezone(tz)
                if match_time_kiev > now:
                    time_str = match_time_kiev.strftime('%H:%M')
                    match_str = f"{home} vs {away} в {time_str} (по Киеву)"
                    matches.append(match_str)
        else:
            print(f"Ошибка API: {response.status_code} — {response.text}")
    except Exception as e:
        print(f"Ошибка запроса к OddsAPI: {e}")

    return matches

async def start(update: Update, context: CallbackContext):
    keyboard = [
        ["Купить подписку"],
        ["Запросить прогноз"],
        ["Экспресс от AI"],
        ["Проверить подписку"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Привет! Я AI Sports Bot. Я анализирую матчи и даю лучшие прогнозы по подписке.\nВыбери действие:",
        reply_markup=reply_markup
    )

async def generate_ai_prediction():
    matches = get_odds_matches()
    if not matches:
        return "Сегодня нет матчей или произошла ошибка API."
    match = random.choice(matches)
    options = ["П1", "П2", "ТБ 2.5", "ТМ 2.5", "Обе забьют"]
    prediction = random.choice(options)
    comment = "AI проанализировал форму команд и выбрал наиболее вероятный исход."
    return f"\U0001F3DF Матч: {match}\n\U0001F3AF Прогноз: {prediction}\n\U0001F916 Комментарий: {comment}"

async def generate_ai_express():
    matches = get_odds_matches()
    if len(matches) < 5:
        return "Недостаточно матчей сегодня для экспресса."
    selected = random.sample(matches, 5)
    total_koef = 1
    response = "⚡ Экспресс от AI:\n"
    for i, match in enumerate(selected, 1):
        pred = random.choice(["П1", "П2", "ТБ 2.5", "ТМ 2.5", "Обе забьют"])
        koef = round(random.uniform(1.3, 2.1), 2)
        total_koef *= koef
        response += f"{i}. {match} — {pred} (коэф. {koef})\n"
    response += f"\n\U0001F4B0 Общий коэф: {round(total_koef, 2)}"
    return response

async def handle_text(update: Update, context: CallbackContext):
    text = update.message.text
    user_id = update.message.from_user.id

    expiry = user_subscriptions.get(user_id)
    if text == "Купить подписку":
        keyboard = [
            [InlineKeyboardButton("1 неделя", callback_data='buy_week'),
             InlineKeyboardButton("2 недели", callback_data='buy_2weeks'),
             InlineKeyboardButton("Месяц", callback_data='buy_month')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Выберите срок подписки:", reply_markup=reply_markup)

    elif text == "Запросить прогноз":
        if expiry and expiry > datetime.datetime.now():
            prediction = await generate_ai_prediction()
            await update.message.reply_text(prediction)
        else:
            await update.message.reply_text("Сначала оформите подписку, чтобы получить прогноз.")

    elif text == "Экспресс от AI":
        if expiry and expiry > datetime.datetime.now():
            express = await generate_ai_express()
            await update.message.reply_text(express)
        else:
            await update.message.reply_text("Экспресс доступен только по подписке. Оформите её, чтобы продолжить.")

    elif text == "Проверить подписку":
        if expiry and expiry > datetime.datetime.now():
            await update.message.reply_text(f"Ваша подписка активна до {expiry.strftime('%Y-%m-%d')}.")
        else:
            await update.message.reply_text("У вас нет активной подписки.")

async def handle_subscription_choice(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    now = datetime.datetime.now()

    if query.data == "buy_week":
        user_subscriptions[user_id] = now + datetime.timedelta(days=7)
        await query.edit_message_text("Подписка на 1 неделю активирована ✅")
    elif query.data == "buy_2weeks":
        user_subscriptions[user_id] = now + datetime.timedelta(days=14)
        await query.edit_message_text("Подписка на 2 недели активирована ✅")
    elif query.data == "buy_month":
        user_subscriptions[user_id] = now + datetime.timedelta(days=30)
        await query.edit_message_text("Подписка на месяц активирована ✅")

if __name__ == '__main__':
    TOKEN = os.getenv("YOUR_TELEGRAM_BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_subscription_choice))
    app.run_polling()
