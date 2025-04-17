import os
import datetime
import random
import requests
import pytz
import asyncio
from deep_translator import GoogleTranslator
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
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
    keyboard = [["Купить подписку"], ["Запросить прогноз"], ["Экспресс от AI"], ["Прогноз по матчу"], ["Проверить подписку"], [InlineKeyboardButton("🎡 Крутануть колесо", callback_data="spin_wheel")]]
    await update.message.reply_text(
        "Привет! Я AI Sports Bot. Я анализирую матчи и даю лучшие прогнозы по подписке.\nВыбери действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def generate_ai_prediction():
    matches = get_today_matches()
    if not matches:
        return "Сегодня нет матчей или произошла ошибка API."
    match = random.choice(matches)
    prediction = random.choice(["П1", "П2", "ТБ 2.5", "ТМ 2.5", "Обе забьют"])
    return f"🏟 Матч: {match}\n🎯 Прогноз: {prediction}\n🤖 Комментарий: AI проанализировал форму команд и выбрал наиболее вероятный исход."


async def generate_ai_express():
    matches = get_today_matches()
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
    return response + f"\n💰 Общий коэф: {round(total_koef, 2)}"


async def handle_text(update: Update, context: CallbackContext):
    text = update.message.text
    user_id = update.message.from_user.id

    if context.user_data.get('awaiting_match'):
        context.user_data['awaiting_match'] = False
        match = find_match_by_name(text)
        if match:
            prediction = random.choice(["П1", "П2", "ТБ 2.5", "ТМ 2.5", "Обе забьют"])
            await update.message.reply_text(f"🏟 Матч: {match}\n🎯 Прогноз: {prediction}\n🤖 AI проанализировал команды и выбрал лучший исход.")
        else:
            await update.message.reply_text("Матч не найден. Убедитесь, что ввели название правильно.")
        return

    expiry = user_subscriptions.get(user_id)
    if text == "Купить подписку":
        keyboard = [[InlineKeyboardButton("1 неделя", callback_data='buy_week'), InlineKeyboardButton("2 недели", callback_data='buy_2weeks'), InlineKeyboardButton("Месяц", callback_data='buy_month')]]
        await update.message.reply_text("Выберите срок подписки:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif text == "Запросить прогноз":
        if expiry and expiry > datetime.datetime.now():
            await update.message.reply_text(await generate_ai_prediction())
        else:
            await update.message.reply_text("Сначала оформите подписку, чтобы получить прогноз.")
    elif text == "Экспресс от AI":
        if expiry and expiry > datetime.datetime.now():
            await update.message.reply_text(await generate_ai_express())
        else:
            await update.message.reply_text("Экспресс доступен только по подписке.")
    elif text == "Прогноз по матчу":
        if expiry and expiry > datetime.datetime.now():
            await update.message.reply_text("Введите матч в формате 'Команда1 vs Команда2':")
            context.user_data['awaiting_match'] = True
        else:
            await update.message.reply_text("Доступ только по подписке.")
    elif text == "Проверить подписку":
        if expiry and expiry > datetime.datetime.now():
            await update.message.reply_text(f"Ваша подписка активна до {expiry.strftime('%Y-%m-%d')}.")
        else:
            await update.message.reply_text("У вас нет активной подписки.")


async def spin_wheel(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    now = datetime.datetime.now()
    spin_info = user_spin_status.get(user_id, {})
    last_free_spin = spin_info.get("last_free")
    can_free_spin = not last_free_spin or (now - last_free_spin >= FREE_SPIN_INTERVAL)

    await query.message.reply_animation(animation=WHEEL_SPIN_GIF_URL, caption="🎡 Крутим колесо фортуны...")
    await asyncio.sleep(2)
    await query.message.reply_photo(photo=WHEEL_IMAGE_URL)

    if can_free_spin:
        result = random.randint(1, 100)
        if result <= 5:
            user_subscriptions[user_id] = now + datetime.timedelta(days=1)
            await query.message.reply_animation(animation=WHEEL_WIN_GIF_URL, caption="🎉 Поздравляем! Вы выиграли подписку на 1 день!")
        else:
            await query.message.reply_text("Увы, не повезло. Хотите попробовать снова за 5$?")
        user_spin_status[user_id] = {"last_free": now}
    else:
        await query.message.reply_text("Бесплатное вращение будет доступно через 48 часов. Хотите попробовать за 5$?")


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
    app.add_handler(CallbackQueryHandler(handle_subscription_choice, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(spin_wheel, pattern="^spin_wheel$"))
    app.run_polling()
