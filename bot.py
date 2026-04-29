# -*- coding: utf-8 -*-
import json, os, logging
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    PreCheckoutQueryHandler,
    ChatJoinRequestHandler
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_IDS = {1833251444}
CHANNEL_ID = -1003815854366

PLANS_FILE = "plans.json"
USERS_FILE = "users.json"
SETTINGS_FILE = "settings.json"
SUBS_FILE = "subscriptions.json"
STATS_FILE = "stats.json"

# =========================
# LOGGING
# =========================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# =========================
# TOOLS
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

        logger.error(f"LOAD_JSON_ERROR | {e}")

        return default


def save_json(file, data):

    try:

        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    except Exception as e:

        logger.error(f"SAVE_JSON_ERROR | {e}")


def is_admin(user_id):
    return user_id in ADMIN_IDS


def is_num(x):
    return str(x).isdigit()


def fmt(date):

    try:
        return datetime.fromisoformat(date).strftime("%Y-%m-%d %H:%M")

    except:
        return date


# =========================
# START
# =========================

async def start(update, context):

    uid = update.effective_user.id

    logger.info(f"USER_START | user={uid}")

    users = load_json(USERS_FILE, [])

    if uid not in users:

        users.append(uid)

        save_json(USERS_FILE, users)

    settings = load_json(
        SETTINGS_FILE,
        {
            "start": "👋 مرحباً بك",
            "btn": "📦 عرض الباقات",
            "notify": "⏳ تبقى فترة قصيرة على انتهاء اشتراكك"
        }
    )

    kb = [
        [
            InlineKeyboardButton(
                settings["btn"],
                callback_data="plans"
            )
        ]
    ]

    await update.message.reply_text(
        settings["start"],
        reply_markup=InlineKeyboardMarkup(kb)
    )


# =========================
# ME
# =========================

async def me(update, context):

    subs = load_json(SUBS_FILE, {})

    data = subs.get(str(update.effective_user.id))

    if not data:

        await update.message.reply_text(
            "❌ لا يوجد لديك اشتراك"
        )

        return

    await update.message.reply_text(
        f"📦 الباقة: {data['plan']}\n"
        f"⏳ الانتهاء: {fmt(data['expires'])}"
    )


# =========================
# ADMIN
# =========================

async def admin(update, context):

    if not is_admin(update.effective_user.id):
        return

    kb = [

        [InlineKeyboardButton("➕ إضافة", callback_data="add")],

        [InlineKeyboardButton("✏️ تعديل", callback_data="edit")],

        [InlineKeyboardButton("🗑 حذف", callback_data="del")],

        [InlineKeyboardButton("🧨 حذف الكل", callback_data="delall")],

        [InlineKeyboardButton("📝 تعديل الترحيب", callback_data="setwelcome")],

        [InlineKeyboardButton("🔘 تعديل زر الباقات", callback_data="setbtn")],

        [InlineKeyboardButton("🔔 رسالة التنبيه", callback_data="setnotify")],

        [InlineKeyboardButton("📦 عرض الباقات", callback_data="showplans")],

        [InlineKeyboardButton("📢 إذاعة", callback_data="broadcast")],

        [InlineKeyboardButton("📊 الإحصائيات", callback_data="stats")],
    ]

    await update.message.reply_text(
        "🛠 لوحة التحكم",
        reply_markup=InlineKeyboardMarkup(kb)
    )


# =========================
# SHOW PLANS
# =========================

async def plans(update, context):

    q = update.callback_query

    await q.answer()

    plans_data = load_json(PLANS_FILE)

    if not plans_data:

        await q.edit_message_text(
            "❌ لا توجد باقات"
        )

        return

    text = "📦 الباقات المتوفرة:\n\n"

    kb = []

    for name, info in plans_data.items():

        text += (
            f"{name}\n"
            f"💰 {info['price']}⭐️\n"
            f"⏳ {info['days']} يوم\n"
            f"📝 {info.get('description','')}\n\n"
        )

        kb.append([
            InlineKeyboardButton(
                f"🚀 شراء {name}",
                callback_data=f"buy:{name}"
            )
        ])

    kb.append([
        InlineKeyboardButton(
            "🔙 رجوع",
            callback_data="back_user"
        )
    ])

    await q.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(kb)
    )


# =========================
# BUY
# =========================

async def buy(update, context):

    q = update.callback_query

    await q.answer()

    name = q.data.split(":")[1]

    plans_data = load_json(PLANS_FILE)

    plan = plans_data.get(name)

    if not plan:

        await q.message.reply_text(
            "❌ الباقة غير موجودة"
        )

        return

    await q.message.reply_text(
        f"🔥 اخترت باقة {name}\n"
        f"💡 اضغط دفع لإكمال الاشتراك"
    )

    await context.bot.send_invoice(
        chat_id=q.from_user.id,
        title=name,
        description="اشتراك مدفوع",
        payload=name,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(name, plan["price"])]
    )


# =========================
# PRECHECKOUT
# =========================

async def pre(update, context):

    await update.pre_checkout_query.answer(ok=True)


# =========================
# PAYMENT SUCCESS
# =========================

async def ok(update, context):

    try:

        user = update.effective_user

        name = update.message.successful_payment.invoice_payload

        logger.info(
            f"PAYMENT_SUCCESS | user={user.id} | plan={name}"
        )

        plans_data = load_json(PLANS_FILE)

        if name not in plans_data:

            await update.message.reply_text(
                "❌ الباقة غير موجودة"
            )

            return

        plan = plans_data[name]

        subs = load_json(SUBS_FILE, {})

        old = subs.get(str(user.id))

        if old:

            exp = datetime.fromisoformat(old["expires"])

            if exp > datetime.utcnow():
                exp += timedelta(days=plan["days"])

            else:
                exp = datetime.utcnow() + timedelta(days=plan["days"])

        else:

            exp = datetime.utcnow() + timedelta(days=plan["days"])

        # رابط لشخص واحد فقط

        link = await context.bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,
            creates_join_request=False
        )

        logger.info(
            f"INVITE_CREATED | user={user.id}"
        )

        subs[str(user.id)] = {
            "expires": exp.isoformat(),
            "plan": name,
            "n24": False,
            "n1": False
        }

        save_json(SUBS_FILE, subs)

        stats = load_json(
            STATS_FILE,
            {
                "total": 0,
                "today": 0,
                "sales": []
            }
        )

        stats["total"] += plan["price"]

        stats["today"] += plan["price"]

        stats["sales"].append({
            "plan": name
        })

        save_json(STATS_FILE, stats)

        await update.message.reply_text(
            f"✅ تم الاشتراك بنجاح\n\n"
            f"📦 الباقة: {name}\n"
            f"⏳ الانتهاء: {fmt(exp.isoformat())}\n\n"
            f"🔗 رابط الدخول:\n{link.invite_link}"
        )

    except Exception as e:

        logger.error(f"PAYMENT_ERROR | {e}")

        await update.message.reply_text(
            "❌ حدث خطأ أثناء الدفع"
        )


# =========================
# JOIN REQUEST
# =========================

async def join(update, context):

    uid = update.chat_join_request.from_user.id

    subs = load_json(SUBS_FILE, {})

    if str(uid) in subs:

        exp = datetime.fromisoformat(
            subs[str(uid)]["expires"]
        )

        if datetime.utcnow() < exp:

            logger.info(
                f"JOIN_APPROVED | user={uid}"
            )

            await context.bot.approve_chat_join_request(
                CHANNEL_ID,
                uid
            )

            return

    logger.warning(
        f"JOIN_DECLINED | user={uid}"
    )

    await context.bot.decline_chat_join_request(
        CHANNEL_ID,
        uid
    )


# =========================
# CHECK SUBS
# =========================

async def check(context):

    subs = load_json(SUBS_FILE, {})

    now = datetime.utcnow()

    plans_data = load_json(PLANS_FILE)

    settings = load_json(
        SETTINGS_FILE,
        {
            "notify": "⏳ تبقى فترة قصيرة على انتهاء اشتراكك"
        }
    )

    notify_text = settings.get(
        "notify",
        "⏳ تبقى فترة قصيرة على انتهاء اشتراكك"
    )

    for uid, data in list(subs.items()):

        try:

            exp = datetime.fromisoformat(data["expires"])

            remain = (exp - now).total_seconds()

            plan_name = data["plan"]

            # 24 ساعة
            if (
                not data["n24"]
                and 82800 <= remain <= 86400
            ):

                await context.bot.send_message(
                    uid,
                    notify_text
                )

                await context.bot.send_invoice(
                    uid,
                    "تجديد الاشتراك",
                    "",
                    plan_name,
                    "",
                    "XTR",
                    [
                        LabeledPrice(
                            plan_name,
                            plans_data[plan_name]["price"]
                        )
                    ]
                )

                data["n24"] = True

            # ساعة
            if (
                not data["n1"]
                and 0 < remain <= 3600
            ):

                await context.bot.send_message(
                    uid,
                    notify_text
                )

                await context.bot.send_invoice(
                    uid,
                    "تجديد الاشتراك",
                    "",
                    plan_name,
                    "",
                    "XTR",
                    [
                        LabeledPrice(
                            plan_name,
                            plans_data[plan_name]["price"]
                        )
                    ]
                )

                data["n1"] = True

            # انتهاء
            if now >= exp:

                logger.warning(
                    f"SUB_EXPIRED | user={uid}"
                )

                await context.bot.ban_chat_member(
                    CHANNEL_ID,
                    int(uid)
                )

                await context.bot.unban_chat_member(
                    CHANNEL_ID,
                    int(uid)
                )

                del subs[uid]

        except Exception as e:

            logger.error(
                f"CHECK_ERROR | user={uid} | {e}"
            )

    save_json(SUBS_FILE, subs)


# =========================
# RESET DAILY
# =========================

async def reset(context):

    stats = load_json(STATS_FILE, {})

    old_today = stats.get("today", 0)

    stats["today"] = 0

    save_json(STATS_FILE, stats)

    logger.info(
        f"DAILY_RESET | old_today={old_today}"
    )


# =========================
# ADMIN INPUT
# =========================

async def admin_input(update, context):

    if not is_admin(update.effective_user.id):
        return

    step = context.user_data.get("step")

    txt = update.message.text.strip()

    plans_data = load_json(PLANS_FILE)

    # ADD
    if step == "add_name":

        context.user_data["name"] = txt

        context.user_data["step"] = "add_price"

        await update.message.reply_text(
            "💰 السعر؟"
        )

    elif step == "add_price":

        if not is_num(txt):

            await update.message.reply_text(
                "❌ اكتب رقم صحيح"
            )

            return

        context.user_data["price"] = int(txt)

        context.user_data["step"] = "add_days"

        await update.message.reply_text(
            "⏳ الأيام؟"
        )

    elif step == "add_days":

        if not is_num(txt):

            await update.message.reply_text(
                "❌ اكتب رقم صحيح"
            )

            return

        context.user_data["days"] = int(txt)

        context.user_data["step"] = "add_desc"

        await update.message.reply_text(
            "📝 الوصف؟"
        )

    elif step == "add_desc":

        logger.info(
            f"PLAN_ADDED | {context.user_data['name']}"
        )

        plans_data[context.user_data["name"]] = {
            "price": context.user_data["price"],
            "days": context.user_data["days"],
            "description": txt
        }

        save_json(PLANS_FILE, plans_data)

        context.user_data.clear()

        await update.message.reply_text(
            "✅ تمت إضافة الباقة"
        )

    # EDIT
    elif step == "edit_price":

        if not is_num(txt):

            await update.message.reply_text(
                "❌ اكتب رقم صحيح"
            )

            return

        context.user_data["price"] = int(txt)

        context.user_data["step"] = "edit_days"

        await update.message.reply_text(
            "⏳ الأيام؟"
        )

    elif step == "edit_days":

        if not is_num(txt):

            await update.message.reply_text(
                "❌ اكتب رقم صحيح"
            )

            return

        context.user_data["days"] = int(txt)

        context.user_data["step"] = "edit_desc"

        await update.message.reply_text(
            "📝 الوصف؟"
        )

    elif step == "edit_desc":

        name = context.user_data["edit_name"]

        logger.info(
            f"PLAN_EDITED | {name}"
        )

        plans_data[name] = {
            "price": context.user_data["price"],
            "days": context.user_data["days"],
            "description": txt
        }

        save_json(PLANS_FILE, plans_data)

        context.user_data.clear()

        await update.message.reply_text(
            "✅ تم تعديل الباقة"
        )

    # SET WELCOME
    elif step == "setwelcome":

        settings = load_json(SETTINGS_FILE, {})

        settings["start"] = txt

        save_json(SETTINGS_FILE, settings)

        logger.info("WELCOME_UPDATED")

        context.user_data.clear()

        await update.message.reply_text(
            "✅ تم تحديث رسالة الترحيب"
        )

    # SET BUTTON
    elif step == "setbtn":

        settings = load_json(SETTINGS_FILE, {})

        settings["btn"] = txt

        save_json(SETTINGS_FILE, settings)

        logger.info("BUTTON_UPDATED")

        context.user_data.clear()

        await update.message.reply_text(
            "✅ تم تحديث نص زر الباقات"
        )

    # SET NOTIFY
    elif step == "setnotify":

        settings = load_json(SETTINGS_FILE, {})

        settings["notify"] = txt

        save_json(SETTINGS_FILE, settings)

        logger.info("NOTIFY_UPDATED")

        context.user_data.clear()

        await update.message.reply_text(
            "✅ تم تحديث رسالة التنبيه"
        )

    # BROADCAST
    elif step == "broadcast":

        logger.info(
            f"BROADCAST_STARTED | admin={update.effective_user.id}"
        )

        users = load_json(USERS_FILE, [])

        ok = 0
        fail = 0

        for user_id in users:

            try:

                await context.bot.send_message(
                    user_id,
                    txt
                )

                ok += 1

            except:

                fail += 1

        logger.info(
            f"BROADCAST_FINISHED | success={ok} | fail={fail}"
        )

        context.user_data.clear()

        await update.message.reply_text(
            f"✔ نجح: {ok}\n"
            f"❌ فشل: {fail}"
        )


# =========================
# CALLBACKS
# =========================

async def cb(update, context):

    q = update.callback_query

    await q.answer()

    plans_data = load_json(PLANS_FILE)

    if (
        not is_admin(q.from_user.id)
        and q.data not in ["back_user"]
    ):
        return

    # ADD
    if q.data == "add":

        context.user_data["step"] = "add_name"

        await q.message.reply_text(
            "📦 اسم الباقة؟"
        )

    # EDIT
    elif q.data == "edit":

        if not plans_data:

            await q.message.reply_text(
                "❌ لا توجد باقات"
            )

            return

        kb = [
            [
                InlineKeyboardButton(
                    name,
                    callback_data=f"editplan:{name}"
                )
            ]
            for name in plans_data
        ]

        await q.message.reply_text(
            "✏️ اختر الباقة:",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif q.data.startswith("editplan:"):

        name = q.data.split(":")[1]

        if name not in plans_data:

            await q.message.reply_text(
                "❌ الباقة غير موجودة"
            )

            return

        context.user_data["edit_name"] = name

        context.user_data["step"] = "edit_price"

        await q.message.reply_text(
            "💰 السعر؟"
        )

    # DELETE
    elif q.data == "del":

        if not plans_data:

            await q.message.reply_text(
                "❌ لا توجد باقات"
            )

            return

        kb = [
            [
                InlineKeyboardButton(
                    name,
                    callback_data=f"delplan:{name}"
                )
            ]
            for name in plans_data
        ]

        await q.message.reply_text(
            "🗑 اختر للحذف:",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif q.data.startswith("delplan:"):

        name = q.data.split(":")[1]

        if name not in plans_data:

            await q.message.reply_text(
                "❌ الباقة غير موجودة"
            )

            return

        logger.warning(
            f"PLAN_DELETED | {name}"
        )

        plans_data.pop(name, None)

        save_json(PLANS_FILE, plans_data)

        await q.message.reply_text(
            "✅ تم حذف الباقة"
        )

    # DELETE ALL
    elif q.data == "delall":

        logger.warning(
            "ALL_PLANS_DELETED"
        )

        save_json(PLANS_FILE, {})

        await q.message.reply_text(
            "🧨 تم حذف جميع الباقات"
        )

    # SET WELCOME
    elif q.data == "setwelcome":

        context.user_data["step"] = "setwelcome"

        await q.message.reply_text(
            "📝 ارسل رسالة الترحيب الجديدة"
        )

    # SET BUTTON
    elif q.data == "setbtn":

        context.user_data["step"] = "setbtn"

        await q.message.reply_text(
            "🔘 ارسل النص الجديد للزر"
        )

    # SET NOTIFY
    elif q.data == "setnotify":

        context.user_data["step"] = "setnotify"

        await q.message.reply_text(
            "🔔 ارسل رسالة التنبيه الجديدة"
        )

    # SHOW
    elif q.data == "showplans":

        if not plans_data:

            await q.message.reply_text(
                "❌ لا توجد باقات"
            )

            return

        text = "📦 الباقات:\n\n"

        for name, info in plans_data.items():

            text += (
                f"{name}\n"
                f"💰 {info['price']}⭐️\n"
                f"⏳ {info['days']} يوم\n\n"
            )

        await q.message.reply_text(text)

    # BROADCAST
    elif q.data == "broadcast":

        context.user_data["step"] = "broadcast"

        await q.message.reply_text(
            "📢 ارسل الرسالة"
        )

    # STATS
    elif q.data == "stats":

        stats = load_json(
            STATS_FILE,
            {"sales": []}
        )

        count = {}

        for item in stats["sales"]:

            plan_name = item["plan"]

            count[plan_name] = (
                count.get(plan_name, 0) + 1
            )

        best = (
            max(count, key=count.get)
            if count else "لا يوجد"
        )

        await q.message.reply_text(
            f"💰 الإجمالي: {stats.get('total',0)}\n"
            f"📅 اليوم: {stats.get('today',0)}\n"
            f"🛒 العمليات: {len(stats['sales'])}\n"
            f"🔥 الأكثر مبيعاً: {best}"
        )

    # BACK
    elif q.data == "back_user":

        await q.message.delete()


# =========================
# MAIN
# =========================

def main():

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(CommandHandler("admin", admin))

    app.add_handler(CommandHandler("me", me))

    app.add_handler(
        CallbackQueryHandler(
            plans,
            pattern="plans"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            buy,
            pattern="buy:"
        )
    )

    app.add_handler(
        CallbackQueryHandler(cb)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.User(ADMIN_IDS),
            admin_input
        )
    )

    app.add_handler(
        PreCheckoutQueryHandler(pre)
    )

    app.add_handler(
        MessageHandler(
            filters.SUCCESSFUL_PAYMENT,
            ok
        )
    )

    app.add_handler(
        ChatJoinRequestHandler(join)
    )

    app.job_queue.run_repeating(
        check,
        interval=3600
    )

    app.job_queue.run_repeating(
        reset,
        interval=86400
    )

    app.run_polling()


if __name__ == "__main__":
    main()
