# -*- coding: utf-8 -*-
import json
import os
import logging
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters,
    PreCheckoutQueryHandler, ChatJoinRequestHandler
)

# =========================
# إعدادات
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_IDS = {1833251444}
CHANNEL_ID = -1003870030895

PLANS_FILE = "plans.json"
USERS_FILE = "users.json"
SETTINGS_FILE = "settings.json"
SUBS_FILE = "subscriptions.json"
STATS_FILE = "stats.json"

# =========================
# Logging احترافي
# =========================
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("sub_bot")

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
    except Exception as e:
        logger.error(f"load_json error {file}: {e}")
        return default

def save_json(file, data):
    try:
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"save_json error {file}: {e}")

def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS

def format_time(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%Y-%m-%d %H:%M")
    except:
        return iso

# =========================
# /start
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    logger.info(f"/start from {uid}")

    users = load_json(USERS_FILE, [])
    if uid not in users:
        users.append(uid)
        save_json(USERS_FILE, users)

    settings = load_json(SETTINGS_FILE, {
        "start": "اهلا بك 👋\nاختر باقة للاشتراك:",
        "btn": "📦 عرض الباقات"
    })

    kb = [
        [InlineKeyboardButton(settings["btn"], callback_data="plans")]
    ]

    await update.message.reply_text(settings["start"], reply_markup=InlineKeyboardMarkup(kb))

# =========================
# /me
# =========================

async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    subs = load_json(SUBS_FILE, {})
    data = subs.get(str(uid))

    if not data:
        await update.message.reply_text("❌ لا يوجد لديك اشتراك")
        return

    await update.message.reply_text(
        f"📊 اشتراكك\n\n"
        f"📦 الباقة: {data['plan']}\n"
        f"⏳ ينتهي: {format_time(data['expires'])}"
    )

# =========================
# لوحة الأدمن
# =========================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    kb = [
        [InlineKeyboardButton("➕ إضافة باقة", callback_data="adm:add")],
        [InlineKeyboardButton("✏️ تعديل باقة", callback_data="adm:edit")],
        [InlineKeyboardButton("🗑 حذف باقة", callback_data="adm:delete_one")],
        [InlineKeyboardButton("🧨 حذف الكل", callback_data="adm:delete_all")],
        [InlineKeyboardButton("📝 تعديل الترحيب", callback_data="adm:set_start")],
        [InlineKeyboardButton("🔘 تعديل زر الباقات", callback_data="adm:set_btn")],
        [InlineKeyboardButton("📢 إذاعة", callback_data="adm:broadcast")],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="adm:stats")],
        [InlineKeyboardButton("❌ إغلاق", callback_data="adm:close")]
    ]

    await update.message.reply_text("🛠 لوحة التحكم", reply_markup=InlineKeyboardMarkup(kb))

# =========================
# عرض الباقات
# =========================

async def show_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    plans = load_json(PLANS_FILE)

    if not plans:
        await q.edit_message_text("🚫 لا توجد باقات حالياً")
        return

    text = "📦 الباقات المتاحة:\n\n"
    kb = []

    for name, info in plans.items():
        text += f"{name}\n💰 {info['price']}⭐️ | ⏳ {info['days']} يوم\n📝 {info.get('description','')}\n\n"
        kb.append([InlineKeyboardButton(name, callback_data=f"buy:{name}")])

    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_user")])

    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

# =========================
# شراء
# =========================

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    plan_name = q.data.split(":",1)[1]
    plans = load_json(PLANS_FILE)
    plan = plans.get(plan_name)

    if not plan:
        await q.message.reply_text("❌ الباقة غير موجودة")
        return

    prices = [LabeledPrice(plan_name, int(plan["price"]))]

    try:
        await context.bot.send_invoice(
            chat_id=q.from_user.id,
            title=f"اشتراك: {plan_name}",
            description=plan.get("description",""),
            payload=plan_name,
            provider_token="",
            currency="XTR",
            prices=prices
        )
    except Exception as e:
        logger.error(f"invoice error: {e}")

# =========================
# الدفع
# =========================

async def precheckout(update, context):
    try:
        await update.pre_checkout_query.answer(ok=True)
    except Exception as e:
        logger.error(f"precheckout error: {e}")

async def success(update, context):
    try:
        user = update.effective_user
        plan_name = update.message.successful_payment.invoice_payload
        logger.info(f"payment success {user.id} plan {plan_name}")

        plans = load_json(PLANS_FILE)
        if plan_name not in plans:
            logger.error("plan missing after payment")
            return

        plan = plans[plan_name]
        subs = load_json(SUBS_FILE, {})
        old = subs.get(str(user.id))

        # تجميع الاشتراك
        if old:
            try:
                exp = datetime.fromisoformat(old["expires"])
                if exp > datetime.utcnow():
                    exp += timedelta(days=plan["days"])
                else:
                    exp = datetime.utcnow() + timedelta(days=plan["days"])
            except:
                exp = datetime.utcnow() + timedelta(days=plan["days"])
        else:
            exp = datetime.utcnow() + timedelta(days=plan["days"])

        invite = await context.bot.create_chat_invite_link(
            CHANNEL_ID,
            creates_join_request=True
        )

        subs[str(user.id)] = {
            "expires": exp.isoformat(),
            "plan": plan_name,
            "n24": False,
            "n1": False
        }
        save_json(SUBS_FILE, subs)

        # إحصائيات
        stats = load_json(STATS_FILE, {"total":0,"today":0,"sales":[]})
        stats["total"] += plan["price"]
        stats["today"] += plan["price"]
        stats["sales"].append({"plan": plan_name, "date": datetime.utcnow().isoformat()})
        save_json(STATS_FILE, stats)

        await update.message.reply_text(
            f"✅ تم الدفع\n\n🔗 {invite.invite_link}\n⏳ ينتهي: {format_time(exp.isoformat())}"
        )

    except Exception as e:
        logger.error(f"payment error: {e}")

# =========================
# طلب الانضمام
# =========================

async def handle_join_request(update, context):
    uid = update.chat_join_request.from_user.id
    subs = load_json(SUBS_FILE, {})

    if str(uid) in subs:
        exp = datetime.fromisoformat(subs[str(uid)]["expires"])
        if datetime.utcnow() < exp:
            await context.bot.approve_chat_join_request(CHANNEL_ID, uid)
            return

    await context.bot.decline_chat_join_request(CHANNEL_ID, uid)

# =========================
# التنبيهات + الطرد
# =========================

async def check_expired(context):
    subs = load_json(SUBS_FILE, {})
    now = datetime.utcnow()
    plans = load_json(PLANS_FILE)

    for uid, d in list(subs.items()):
        try:
            exp = datetime.fromisoformat(d["expires"])
            rem = (exp - now).total_seconds()
            p = d.get("plan")

            # 24 ساعة
            if not d.get("n24") and 82800 <= rem <= 86400 and p in plans:
                plan = plans[p]
                await context.bot.send_message(int(uid),"⏳ باقي 24 ساعة")
                await context.bot.send_invoice(int(uid),"تجديد","",p,"","XTR",[LabeledPrice(p,plan["price"])])
                d["n24"] = True

            # ساعة
            if not d.get("n1") and 0 < rem <= 3600 and p in plans:
                plan = plans[p]
                await context.bot.send_message(int(uid),"⚠️ باقي أقل من ساعة")
                await context.bot.send_invoice(int(uid),"تجديد","",p,"","XTR",[LabeledPrice(p,plan["price"])])
                d["n1"] = True

            # انتهاء
            if now >= exp:
                await context.bot.ban_chat_member(CHANNEL_ID, int(uid))
                await context.bot.unban_chat_member(CHANNEL_ID, int(uid))
                await context.bot.send_message(int(uid),"❌ انتهى اشتراكك")
                del subs[uid]

        except Exception as e:
            logger.error(f"expire error {uid}: {e}")

    save_json(SUBS_FILE, subs)

# =========================
# تصفير يومي
# =========================

async def reset_daily(context):
    stats = load_json(STATS_FILE, {})
    stats["today"] = 0
    save_json(STATS_FILE, stats)
    logger.info("daily reset done")

# =========================
# إدخال الأدمن (Wizard)
# =========================

async def admin_input(update, context):
    if not is_admin(update.effective_user.id):
        return

    step = context.user_data.get("step")
    txt = update.message.text
    plans = load_json(PLANS_FILE)

    try:
        # إضافة
        if step == "add_name":
            context.user_data["name"] = txt
            context.user_data["step"] = "add_price"
            await update.message.reply_text("💰 السعر؟")

        elif step == "add_price":
            context.user_data["price"] = int(txt)
            context.user_data["step"] = "add_days"
            await update.message.reply_text("⏳ الأيام؟")

        elif step == "add_days":
            context.user_data["days"] = int(txt)
            context.user_data["step"] = "add_desc"
            await update.message.reply_text("📝 الوصف؟")

        elif step == "add_desc":
            plans[context.user_data["name"]] = {
                "price": context.user_data["price"],
                "days": context.user_data["days"],
                "description": txt
            }
            save_json(PLANS_FILE, plans)
            context.user_data.clear()
            await update.message.reply_text("✅ تمت الإضافة")

        # تعديل
        elif step == "edit_price":
            context.user_data["price"] = int(txt)
            context.user_data["step"] = "edit_days"
            await update.message.reply_text("⏳ الأيام؟")

        elif step == "edit_days":
            context.user_data["days"] = int(txt)
            context.user_data["step"] = "edit_desc"
            await update.message.reply_text("📝 الوصف؟")

        elif step == "edit_desc":
            name = context.user_data["edit_name"]
            plans[name] = {
                "price": context.user_data["price"],
                "days": context.user_data["days"],
                "description": txt
            }
            save_json(PLANS_FILE, plans)
            context.user_data.clear()
            await update.message.reply_text("✅ تم التعديل")

        # الترحيب
        elif step == "set_start":
            settings = load_json(SETTINGS_FILE, {})
            settings["start"] = txt
            save_json(SETTINGS_FILE, settings)
            context.user_data.clear()
            await update.message.reply_text("تم تحديث الترحيب")

        # الزر
        elif step == "set_btn":
            settings = load_json(SETTINGS_FILE, {})
            settings["btn"] = txt
            save_json(SETTINGS_FILE, settings)
            context.user_data.clear()
            await update.message.reply_text("تم تحديث الزر")

        # إذاعة
        elif step == "broadcast":
            users = load_json(USERS_FILE, [])
            ok = fail = 0
            for u in users:
                try:
                    await context.bot.send_message(u, txt)
                    ok += 1
                except:
                    fail += 1
            context.user_data.clear()
            await update.message.reply_text(f"✔ {ok}\n❌ {fail}")

    except:
        await update.message.reply_text("❌ إدخال غير صحيح")

# =========================
# callbacks
# =========================

async def callbacks(update, context):
    q = update.callback_query
    await q.answer()

    if not is_admin(q.from_user.id):
        return

    data = q.data
    plans = load_json(PLANS_FILE)

    if data == "adm:add":
        context.user_data["step"] = "add_name"
        await q.message.reply_text("اسم الباقة؟")

    elif data == "adm:edit":
        kb = [[InlineKeyboardButton(n, callback_data=f"editplan:{n}")] for n in plans]
        await q.message.reply_text("اختر:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("editplan:"):
        name = data.split(":")[1]
        context.user_data["edit_name"] = name
        context.user_data["step"] = "edit_price"
        await q.message.reply_text("السعر؟")

    elif data == "adm:delete_one":
        kb = [[InlineKeyboardButton(n, callback_data=f"del:{n}")] for n in plans]
        await q.message.reply_text("اختر:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("del:"):
        name = data.split(":")[1]
        plans.pop(name, None)
        save_json(PLANS_FILE, plans)
        await q.message.reply_text("تم الحذف")

    elif data == "adm:delete_all":
        save_json(PLANS_FILE, {})
        await q.message.reply_text("تم حذف الكل")

    elif data == "adm:set_start":
        context.user_data["step"] = "set_start"
        await q.message.reply_text("اكتب الترحيب")

    elif data == "adm:set_btn":
        context.user_data["step"] = "set_btn"
        await q.message.reply_text("اكتب نص الزر")

    elif data == "adm:broadcast":
        context.user_data["step"] = "broadcast"
        await q.message.reply_text("اكتب الرسالة")

    elif data == "adm:stats":
        s = load_json(STATS_FILE, {})
        sales = s.get("sales", [])
        count = {}
        for i in sales:
            p = i["plan"]
            count[p] = count.get(p, 0) + 1
        best = max(count, key=count.get) if count else "لا يوجد"

        await q.message.reply_text(
            f"📊\n💰 {s.get('total',0)}\n📅 {s.get('today',0)}\n🛒 {len(sales)}\n🔥 {best}"
        )

    elif data == "adm:close":
        await q.delete_message()

# =========================
# تشغيل
# =========================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("me", me))

    app.add_handler(CallbackQueryHandler(show_plans, pattern="plans"))
    app.add_handler(CallbackQueryHandler(buy, pattern="buy:"))
    app.add_handler(CallbackQueryHandler(callbacks))

    app.add_handler(MessageHandler(filters.TEXT & filters.User(ADMIN_IDS), admin_input))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, success))
    app.add_handler(ChatJoinRequestHandler(handle_join_request))

    app.job_queue.run_repeating(check_expired, interval=3600)
    app.job_queue.run_repeating(reset_daily, interval=86400)

    app.run_polling()

if __name__ == "__main__":
    main()
