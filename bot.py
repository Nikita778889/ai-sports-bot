import os
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, CallbackQueryHandler

user_subscriptions = {}

SUBSCRIPTIONS = {
    'week': 7,
    '2weeks': 14,
    'month': 30,
}

async def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("Купить подписку", callback_data='buy')],
        [InlineKeyboardButton("Запросить прогноз", callback_data='bet')],
        [InlineKeyboardButton("Проверить подписку", callback_data='status')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Привет! Я AI Sports Bot. Я анализирую матчи и даю лучшие прогнозы на спорт по подписке.\nВыбери опцию ниже:",
        reply_markup=reply_markup
    )

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
        await query.edit_message_text("Выбери срок подписки:", reply_markup=InlineKeyboardMarkup(keyboard))

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
            await query.edit_message_text("🎯 Прогноз: Победа команды А. Коэф: 2.1. Удачи!")
        else:
            await query.edit_message_text("Сначала оформи подписку, чтобы получить прогноз.")

if __name__ == '__main__':
    TOKEN = os.getenv("YOUR_TELEGRAM_BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling()