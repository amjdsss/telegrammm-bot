# -*- coding: utf-8 -*-
import json
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = {1833251444}

PLANS_FILE = "plans.json"
USERS_FILE = "users.json"
SETTINGS_FILE = "settings.json"

# =========================
# أدوات
# =========================

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

    settings = load_json(SETTINGS_FILE, {"start": "اهلا بك 👋"})
    text = settings.get("start", "اهلا بك 👋")

    await update.message.reply_text(text)

# =========================
# لوحة الأدمن
# =========================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    keyboard = [
        [InlineKeyboardButton("➕ إضافة باقة", callback_data="add")],
        [InlineKeyboardButton("✏️ تعديل الباقات", callback_data="edit")],
        [InlineKeyboardButton("🗑 حذف باقة", callback_data="delete")],
        [InlineKeyboardButton("📝 تعديل رسالة الترحيب", callback_data="welcome")],
        [InlineKeyboardButton("📢 إذاعة", callback_data="broadcast")]
    ]

    await update.message.reply_text(
        "لوحة التحكم 🔧",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# إضافة / تعديل / حذف
# =========================

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    data = query.data

    if data == "add":
        context.user_data["step"] = "add_name"
        await query.message.reply_text("اسم الباقة؟")

    elif data == "edit":
        plans = load_json(PLANS_FILE)
        text = "اكتب اسم الباقة لتعديلها:"
        await query.message.reply_text(text)
        context.user_data["step"] = "edit_name"

    elif data == "delete":
        plans = load_json(PLANS_FILE)
        text = "اكتب اسم الباقة لحذفها:"
        await query.message.reply_text(text)
        context.user_data["step"] = "delete_name"

    elif data == "welcome":
        context.user_data["step"] = "welcome"
        await query.message.reply_text("اكتب رسالة الترحيب الجديدة:")

    elif data == "broadcast":
        context.user_data["step"] = "broadcast"
        await query.message.reply_text("اكتب الرسالة للإذاعة:")

# =========================
# معالجة الإدخال
# =========================

async def admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    step = context.user_data.get("step")
    text = update.message.text

    plans = load_json(PLANS_FILE)

    # إضافة
    if step == "add_name":
        context.user_data["name"] = text
        context.user_data["step"] = "add_price"
        await update.message.reply_text("السعر؟")

    elif step == "add_price":
        context.user_data["price"] = int(text)
        context.user_data["step"] = "add_days"
        await update.message.reply_text("عدد الأيام؟")

    elif step == "add_days":
        name = context.user_data["name"]
        price = context.user_data["price"]

        plans[name] = {
            "price": price,
            "days": int(text),
            "description": "تمت إضافتها"
        }

        save_json(PLANS_FILE, plans)
        context.user_data.clear()
        await update.message.reply_text("✅ تمت الإضافة")

    # تعديل
    elif step == "edit_name":
        if text in plans:
            context.user_data["edit"] = text
            context.user_data["step"] = "edit_price"
            await update.message.reply_text("السعر الجديد؟")
        else:
            await update.message.reply_text("❌ غير موجود")

    elif step == "edit_price":
        name = context.user_data["edit"]
        plans[name]["price"] = int(text)
        save_json(PLANS_FILE, plans)
        context.user_data.clear()
        await update.message.reply_text("✅ تم التعديل")

    # حذف
    elif step == "delete_name":
        if text in plans:
            del plans[text]
            save_json(PLANS_FILE, plans)
            await update.message.reply_text("🗑 تم الحذف")
        else:
            await update.message.reply_text("❌ غير موجود")
        context.user_data.clear()

    # رسالة الترحيب
    elif step == "welcome":
        save_json(SETTINGS_FILE, {"start": text})
        context.user_data.clear()
        await update.message.reply_text("✅ تم التحديث")

    # إذاعة
    elif step == "broadcast":
        users = load_json(USERS_FILE, [])
        sent = 0

        for uid in users:
            try:
                await context.bot.send_message(uid, text)
                sent += 1
            except:
                pass

        context.user_data.clear()
        await update.message.reply_text(f"📢 تم الإرسال إلى {sent} مستخدم")

# =========================
# تشغيل
# =========================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))

    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & filters.User(ADMIN_IDS), admin_input))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
