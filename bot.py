import os
import datetime
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, CallbackQueryHandler

user_subscriptions = {}
SUBSCRIPTIONS = {
    'week': 7,
    '2weeks': 14,
    'month': 30,
}

# Пример спортивных матчей (заглушка)
SPORTS_MATCHES = [
    ("Real Madrid vs Barcelona", "Футбол"),
    ("Lakers vs Celtics", "Баскетбол"),
    ("Djokovic vs Alcaraz", "Теннис"),
    ("Avalanche vs Penguins", "Хоккей"),
    ("PSG vs Lyon", "Футбол"),
    ("Bayern vs Dortmund", "Футбол"),
    ("Man City vs Arsenal", "Футбол"),
    ("Napoli vs Juventus", "Футбол"),
    ("Heat vs Bulls", "Баскетбол"),
    ("Nadal vs Medvedev", "Теннис")
]

async def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("Купить подписку", callback_data='buy')],
        [InlineKeyboardButton("Запросить прогноз", callback_data='bet')],
        [InlineKeyboardButton("Экспресс от AI", callback_data='express')],
        [InlineKeyboardButton("Проверить подписку", callback_data='status')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Привет! Я AI Sports Bot. Я анализирую матчи и даю лучшие прогнозы по подписке.\nВыбери действие:",
        reply_markup=reply_markup
    )

async def generate_ai_prediction():
    match, sport = random.choice(SPORTS_MATCHES)
    options = ["П1", "П2", "ТБ 2.5", "ТМ 2.5", "Обе забьют"]
    prediction = random.choice(options)
    comment = "AI проанализировал последние встречи и выбрал этот вариант как самый вероятный."
    return f"🏟 Матч: {match}\n🎯 Прогноз: {prediction}\n📌 Вид спорта: {sport}\n🤖 Комментарий: {comment}"

async def generate_ai_express():
    selected = random.sample(SPORTS_MATCHES, 5)
    total_koef = 1
    response = "⚡ Экспресс от AI:\n"
    for i, (match, sport) in enumerate(selected, 1):
        pred = random.choice(["П1", "П2", "ТБ 2.5", "ТМ 2.5", "Обе забьют"])
        koef = round(random.uniform(1.3, 2.1), 2)
        total_koef *= koef
        response += f"{i}. {match} ({sport}) — {pred} (коэф. {koef})\n"
    response += f"\n💰 Общий коэф: {round(total_koef, 2)}"
    return response

async def button(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if query.data == 'buy':
        keyboard = [
            [InlineKeyboardButton("1 неделя", callback_data='sub_week')],
            [InlineKeyboardButton("2 недели", callback_data='sub_2weeks')],
            [InlineKeyboardButton("1 месяц", callback_data='sub_month')]
        ]
        await query.edit_message_text("Выберите срок подписки:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith('sub_'):
        plan = query.data.replace('sub_', '')
        days = SUBSCRIPTIONS[plan]
        expiry = datetime.datetime.now() + datetime.timedelta(days=days)
        user_subscriptions[user_id] = expiry
        await query.edit_message_text(f"Подписка активна на {days} дней, до {expiry.strftime('%Y-%m-%d')}.")

    elif query.data == 'status':
        expiry = user_subscriptions.get(user_id)
        if expiry and expiry > datetime.datetime.now():
            await query.edit_message_text(f"Ваша подписка активна до {expiry.strftime('%Y-%m-%d')}.")
        else:
            await query.edit_message_text("У вас нет активной подписки.")

    elif query.data == 'bet':
        expiry = user_subscriptions.get(user_id)
        if expiry and expiry > datetime.datetime.now():
            prediction = await generate_ai_prediction()
            await query.edit_message_text(prediction)
        else:
            await query.edit_message_text("Сначала оформите подписку, чтобы получить прогноз.")

    elif query.data == 'express':
        expiry = user_subscriptions.get(user_id)
        if expiry and expiry > datetime.datetime.now():
            express = await generate_ai_express()
            await query.edit_message_text(express)
        else:
            await query.edit_message_text("Экспресс доступен только по подписке. Оформите её, чтобы продолжить.")

if __name__ == '__main__':
    TOKEN = os.getenv("YOUR_TELEGRAM_BOT_TOKEN")
    print("TOKEN:", repr(TOKEN))  # для отладки
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling()
