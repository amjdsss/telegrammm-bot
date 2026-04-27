# -*- coding: utf-8 -*-
import json
import logging
import os
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, PreCheckoutQueryHandler,
    ContextTypes, filters
)

# =========================
# إعدادات
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")  # 🔐 آمن
CHANNEL_ID = -1003870030895
ADMIN_IDS = {1833251444}

PLANS_FILE = "plans.json"
SUBS_FILE = "subscriptions.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================
# ملفات JSON
# =========================

def load_json(filename, default=None):
    if default is None:
        default = {}
    if not os.path.exists(filename):
        return default
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# =========================
# /start
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📦 عرض الباقات", callback_data="plans")]]
    await update.message.reply_text(
        "اهلا بك 👋\nاختر باقة:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# عرض الباقات
# =========================

async def show_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    plans = load_json(PLANS_FILE)

    if not plans:
        await query.edit_message_text("🚫 لا توجد باقات")
        return

    keyboard = []
    text = "👇 الباقات:\n\n"

    for name, info in plans.items():
        price = info.get("price", 0)
        days = info.get("days", 0)

        text += f"{name} - {price}⭐️ - {days} يوم\n"
        keyboard.append([InlineKeyboardButton(name, callback_data=f"buy:{name}")])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# شراء
# =========================

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, name = query.data.split(":")

    plans = load_json(PLANS_FILE)
    plan = plans.get(name)

    if not plan:
        await query.message.reply_text("❌ الباقة غير موجودة")
        return

    prices = [LabeledPrice(name, plan["price"])]

    await context.bot.send_invoice(
        chat_id=query.from_user.id,
        title=name,
        description="اشتراك",
        payload=name,
        provider_token="",
        currency="XTR",
        prices=prices
    )

# =========================
# الدفع
# =========================

async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def success(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ تم الدفع بنجاح")

# =========================
# تشغيل
# =========================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(show_plans, pattern="plans"))
    app.add_handler(CallbackQueryHandler(buy, pattern="buy:"))

    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, success))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
