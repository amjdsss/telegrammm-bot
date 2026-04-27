# -*- coding: utf-8 -*-
import json
import os
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters,
    PreCheckoutQueryHandler
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_IDS = {1833251444}
CHANNEL_ID = -1003870030895  # ✅ تم التعديل

PLANS_FILE = "plans.json"
USERS_FILE = "users.json"
SETTINGS_FILE = "settings.json"
SUBS_FILE = "subscriptions.json"

def load_json(file, default=None):
    if default is None:
        default = {}
    if not os.path.exists(file):
        return default
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_admin(user_id):
    return user_id in ADMIN_IDS

# =========================
# /start
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    users = load_json(USERS_FILE, [])
    if user_id not in users:
        users.append(user_id)
        save_json(USERS_FILE, users)

    settings = load_json(SETTINGS_FILE, {
        "start": "اهلا بك 👋",
        "plans_button": "📦 عرض الباقات"
    })

    keyboard = [[InlineKeyboardButton(settings["plans_button"], callback_data="plans")]]

    await update.message.reply_text(
        settings["start"],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# لوحة الأدمن
# =========================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    keyboard = [
        [InlineKeyboardButton("➕ إضافة باقة", callback_data="add")],
        [InlineKeyboardButton("🧨 حذف جميع الباقات", callback_data="delete_all")]
    ]

    await update.message.reply_text("لوحة التحكم", reply_markup=InlineKeyboardMarkup(keyboard))

# =========================
# عرض الباقات
# =========================

async def show_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    plans = load_json(PLANS_FILE)

    if not plans:
        await query.edit_message_text("لا توجد باقات")
        return

    text = "📦 الباقات:\n\n"
    keyboard = []

    for name, info in plans.items():
        text += f"{name} - {info['price']}⭐️ - {info['days']} يوم\n"
        keyboard.append([InlineKeyboardButton(name, callback_data=f"buy:{name}")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# =========================
# شراء
# =========================

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    name = query.data.split(":")[1]
    plans = load_json(PLANS_FILE)
    plan = plans.get(name)

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
    user = update.effective_user
    plan_name = update.message.successful_payment.invoice_payload

    plans = load_json(PLANS_FILE)
    days = plans[plan_name]["days"]

    now = datetime.utcnow()
    expire = now + timedelta(days=days)

    invite = await context.bot.create_chat_invite_link(
        CHANNEL_ID,
        member_limit=1
    )

    subs = load_json(SUBS_FILE, {})
    subs[str(user.id)] = {"expires": expire.isoformat()}
    save_json(SUBS_FILE, subs)

    await update.message.reply_text(
        f"✅ تم الدفع\n\n🔗 {invite.invite_link}\n⏳ ينتهي: {expire}"
    )

# =========================
# الطرد التلقائي
# =========================

async def check_expired(context: ContextTypes.DEFAULT_TYPE):
    subs = load_json(SUBS_FILE, {})
    now = datetime.utcnow()

    for uid, data in list(subs.items()):
        exp = datetime.fromisoformat(data["expires"])

        if now >= exp:
            try:
                await context.bot.ban_chat_member(CHANNEL_ID, int(uid))
                await context.bot.unban_chat_member(CHANNEL_ID, int(uid))
            except:
                pass

            del subs[uid]

    save_json(SUBS_FILE, subs)

# =========================
# الأدمن
# =========================

async def admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    step = context.user_data.get("step")
    text = update.message.text

    plans = load_json(PLANS_FILE)

    if text == "➕ إضافة باقة":
        context.user_data["step"] = "add"
        await update.message.reply_text("اسم الباقة؟")

    elif step == "add":
        context.user_data["name"] = text
        context.user_data["step"] = "price"
        await update.message.reply_text("السعر؟")

    elif step == "price":
        context.user_data["price"] = int(text)
        context.user_data["step"] = "days"
        await update.message.reply_text("عدد الأيام؟")

    elif step == "days":
        plans[context.user_data["name"]] = {
            "price": context.user_data["price"],
            "days": int(text)
        }
        save_json(PLANS_FILE, plans)
        context.user_data.clear()
        await update.message.reply_text("تمت الإضافة")

# =========================
# تشغيل
# =========================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))

    app.add_handler(CallbackQueryHandler(show_plans, pattern="plans"))
    app.add_handler(CallbackQueryHandler(buy, pattern="buy:"))

    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, success))

    app.add_handler(MessageHandler(filters.TEXT & filters.User(ADMIN_IDS), admin_input))

    app.job_queue.run_repeating(check_expired, interval=3600)

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
