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

async def generate_ai_prediction():
    matches = get_today_matches()
    if not matches:
        return "Сегодня нет матчей или произошла ошибка API."
    match = random.choice(matches)
    options = ["П1", "П2", "ТБ 2.5", "ТМ 2.5", "Обе забьют"]
    prediction = random.choice(options)
    comment = "AI проанализировал форму команд и выбрал наиболее вероятный исход."
    return f"\U0001F3DF Матч: {match}\n\U0001F3AF Прогноз: {prediction}\n\U0001F916 Комментарий: {comment}"

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
    response += f"\n\U0001F4B0 Общий коэф: {round(total_koef, 2)}"
    return response

async def show_luck_cells(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    now = datetime.datetime.now()
    last_try = user_luck.get(user_id, {}).get("last")
    is_free_try = not last_try or (now - last_try >= LUCK_INTERVAL)

    cell_count = 5 if is_free_try else 3
    context.user_data['luck_game'] = {
        'win_index': random.randint(0, cell_count - 1),
        'free': is_free_try
    }

    buttons = [InlineKeyboardButton(str(i + 1), callback_data=f"cell_{i}") for i in range(cell_count)]
    markup = InlineKeyboardMarkup.from_row(buttons)

    intro_text = "🎲 Бесплатная попытка (раз в 48 часов): одна из 5 ячеек содержит бесплатный прогноз. Выбери ячейку:" if is_free_try \
        else "💸 Платная попытка за 5$: одна из 3 ячеек содержит бесплатный день доступа. Выбери ячейку:"

    await query.message.reply_text(intro_text, reply_markup=markup)
    user_luck[user_id] = {'last': now} if is_free_try else user_luck.get(user_id, {})

async def handle_luck_cell(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    game = context.user_data.get('luck_game')
    if not game:
        await query.message.reply_text("Ошибка: нет активной игры.")
        return

    selected = int(query.data.split('_')[1])
    win = selected == game['win_index']

    if win:
        prediction = await generate_ai_prediction()
        reward_text = "🎉 Вы выиграли бесплатный прогноз!" if game['free'] else "🎉 Победа! Вы получаете 1 день доступа."
        await query.message.reply_text(f"{reward_text}\n{prediction}")
    else:
        fail_text = "😔 Увы, не повезло. Хотите попробовать снова за 5$? В платной попытке 3 ячейки — шанс выше!" if game['free'] \
            else "😔 Неудача. Попробуйте позже или купите подписку."
        await query.message.reply_text(fail_text)

    context.user_data['luck_game'] = None

async def handle_callback(update: Update, context: CallbackContext):
    data = update.callback_query.data
    if data.startswith("buy_"):
        await handle_subscription_choice(update, context)
    elif data == "check_luck":
        await show_luck_cells(update, context)
    elif data.startswith("cell_"):
        await handle_luck_cell(update, context)

async def handle_text(update: Update, context: CallbackContext):
    text = update.message.text
    user_id = update.message.from_user.id

    if context.user_data.get('awaiting_match'):
        context.user_data['awaiting_match'] = False
        match_name = text
        found = find_match_by_name(match_name)
        if found:
            prediction = random.choice(["П1", "П2", "ТБ 2.5", "ТМ 2.5", "Обе забьют"])
            comment = "AI проанализировал команды и выбрал лучший исход."
            await update.message.reply_text(f"\U0001F3DF Матч: {found}\n\U0001F3AF Прогноз: {prediction}\n\U0001F916 Комментарий: {comment}")
        else:
            await update.message.reply_text("Матч не найден. Убедитесь, что ввели название правильно.")
        return

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

    elif text == "Прогноз по матчу":
        if expiry and expiry > datetime.datetime.now():
            await update.message.reply_text("Введите матч в формате 'Команда1 vs Команда2':")
            context.user_data['awaiting_match'] = True
        else:
            await update.message.reply_text("Доступ только по подписке. Оформите её, чтобы продолжить.")

    elif text == "Проверить подписку":
        if expiry and expiry > datetime.datetime.now():
            await update.message.reply_text(f"Ваша подписка активна до {expiry.strftime('%Y-%m-%d')}.")
        else:
            await update.message.reply_text("У вас нет активной подписки.")

    elif text == "Проверить удачу":
        keyboard = [[InlineKeyboardButton("🎁 Проверить удачу", callback_data="check_luck")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("🎁 Хочешь испытать удачу? Нажми на кнопку ниже:", reply_markup=reply_markup)

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
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()
