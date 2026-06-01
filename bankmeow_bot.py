import os
import random
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = 1026211406

CAT_NAMES = [
    "پیشی", "گربولو", "میومیو", "خرناس", "نازگل", "شیطون", "پنجول", "ابری",
    "دمبی", "مشکی", "برفی", "زردک", "پیسی", "کرمی", "طوسی", "خالدار",
    "ناز", "گنده", "چاقو", "لوسی", "رامبو", "ببری", "پلنگی", "گلی",
    "شبنم", "آبنبات", "توپی", "موشی", "ملوس", "کوچولو"
]

RARE_CAT_NAMES = ["اژدها", "ققنوس", "یخ", "آتش", "رعد", "کهکشان", "مه", "嗯سایه"]
LEGEND_CAT_NAMES = ["خدای گربه‌ها", "امپراتور", "افسانه", "ابدی", "نامیرا"]

CAT_EMOJIS = ["😸","🐱","😺","😻","🐈","🐈‍⬛","🙀","😹"]
RARE_EMOJIS = ["🦁","🐯","🐆","🦊","🐺"]
LEGEND_EMOJIS = ["🐉","⭐","🌟","👑","🔥"]

SHOP_ITEMS = {
    "ماهی":  {"price": 20,  "emoji": "🐟", "happiness": 15},
    "توپ":   {"price": 30,  "emoji": "🎯", "happiness": 20},
    "تخت":   {"price": 80,  "emoji": "🛏️", "happiness": 30},
    "ریبون": {"price": 15,  "emoji": "🎀", "happiness": 10},
    "خانه":  {"price": 200, "emoji": "🏡", "happiness": 50},
    "تاج":   {"price": 500, "emoji": "👑", "happiness": 80},
}

KEYBOARD = ReplyKeyboardMarkup([
    ["💰 موجودی", "🎁 جایزه"],
    ["🐱 گربه بگیر", "📋 گربه‌هام"],
    ["🛍️ فروشگاه", "😸 پورر"],
    ["🐭 موش‌بگیر", "🏆 برترین‌ها"],
    ["📊 آمار من", "❓ راهنما"],
], resize_keyboard=True)

def shop_keyboard():
    buttons = []
    for name, item in SHOP_ITEMS.items():
        buttons.append([InlineKeyboardButton(
            f"{item['emoji']} {name} — {item['price']} میوپوینت",
            callback_data=f"shop_{name}"
        )])
    buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back")])
    return InlineKeyboardMarkup(buttons)

def cat_select_keyboard(cats, item_name):
    buttons = []
    for cat in cats:
        filled = cat['happiness'] // 20
        bar = "❤️" * filled + "🖤" * (5 - filled)
        buttons.append([InlineKeyboardButton(
            f"{cat['emoji']} {cat['name']} {bar}",
            callback_data=f"buyfor_{item_name}_{cat['id']}"
        )])
    buttons.append([InlineKeyboardButton("🔙 بازگشت به فروشگاه", callback_data="goto_shop")])
    return InlineKeyboardMarkup(buttons)

def get_db():
    conn = sqlite3.connect("bankmeow.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            first_name  TEXT,
            balance     INTEGER DEFAULT 100,
            cats        INTEGER DEFAULT 0,
            last_daily  TEXT DEFAULT '',
            last_purr   TEXT DEFAULT '',
            last_egg    TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cats (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            name        TEXT,
            emoji       TEXT,
            rarity      TEXT DEFAULT 'normal',
            happiness   INTEGER DEFAULT 100,
            last_update TEXT DEFAULT ''
        )
    """)
    for col in ["last_purr", "last_egg"]:
        try:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT DEFAULT ''")
            conn.commit()
        except:
            pass
    try:
        conn.execute("ALTER TABLE cats ADD COLUMN rarity TEXT DEFAULT 'normal'")
        conn.commit()
    except:
        pass
    conn.commit()
    return conn

def get_user(user_id, first_name=""):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    if not row:
        conn.execute("INSERT INTO users (user_id, first_name) VALUES (?,?)", (user_id, first_name))
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    cols = ["user_id","first_name","balance","cats","last_daily","last_purr","last_egg"]
    return dict(zip(cols, row[:len(cols)]))

def update_balance(user_id, amount):
    conn = get_db()
    conn.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def set_time(user_id, field):
    conn = get_db()
    conn.execute(f"UPDATE users SET {field}=? WHERE user_id=?", (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()

def check_cooldown(last_time_str, hours):
    if not last_time_str:
        return True, None
    try:
        last_dt = datetime.fromisoformat(last_time_str)
        diff = datetime.now() - last_dt
        if diff < timedelta(hours=hours):
            remaining = timedelta(hours=hours) - diff
            h = int(remaining.total_seconds() // 3600)
            m = int((remaining.total_seconds() % 3600) // 60)
            return False, (h, m)
    except:
        pass
    return True, None

def add_cat_db(user_id, name, emoji, rarity="normal"):
    conn = get_db()
    conn.execute("INSERT INTO cats (user_id, name, emoji, rarity, happiness, last_update) VALUES (?,?,?,?,100,?)",
                 (user_id, name, emoji, rarity, datetime.now().isoformat()))
    conn.execute("UPDATE users SET cats = cats + 1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def get_user_cats(user_id):
    conn = get_db()
    cats = conn.execute("SELECT id, name, emoji, rarity, happiness, last_update FROM cats WHERE user_id=?", (user_id,)).fetchall()
    updated = []
    for cat in cats:
        cat_id, name, emoji, rarity, happiness, last_update = cat
        if last_update:
            try:
                last_dt = datetime.fromisoformat(last_update)
                hours = (datetime.now() - last_dt).total_seconds() / 3600
                decrease = int(hours / 24 * 20)
                new_happiness = max(0, happiness - decrease)
                if new_happiness != happiness:
                    conn.execute("UPDATE cats SET happiness=?, last_update=? WHERE id=?",
                                 (new_happiness, datetime.now().isoformat(), cat_id))
                happiness = new_happiness
            except:
                pass
        updated.append({"id": cat_id, "name": name, "emoji": emoji, "rarity": rarity, "happiness": happiness})
    conn.commit()
    conn.close()
    return updated

def add_happiness_to_cat(cat_id, amount):
    conn = get_db()
    row = conn.execute("SELECT happiness FROM cats WHERE id=?", (cat_id,)).fetchone()
    if row:
        new_h = min(100, row[0] + amount)
        conn.execute("UPDATE cats SET happiness=?, last_update=? WHERE id=?",
                     (new_h, datetime.now().isoformat(), cat_id))
    conn.commit()
    conn.close()

def get_top():
    conn = get_db()
    rows = conn.execute("SELECT first_name, balance FROM users ORDER BY balance DESC LIMIT 3").fetchall()
    conn.close()
    return rows

def get_rank(user_id):
    conn = get_db()
    rows = conn.execute("SELECT user_id FROM users ORDER BY balance DESC").fetchall()
    conn.close()
    for i, row in enumerate(rows):
        if row[0] == user_id:
            return i + 1
    return "-"

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    get_user(u.id, u.first_name)
    await update.message.reply_text(
        f"🐱 سلام *{u.first_name}*! خوش اومدی به *بانک‌میو*!\n\n"
        "🪙 واحد پولی ما *میوپوینت* هست!\n"
        "با ۱۰۰ میوپوینت شروع کردی 🎉\n\n"
        "از دکمه‌های پایین استفاده کن 👇",
        parse_mode="Markdown", reply_markup=KEYBOARD
    )

async def balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    user = get_user(u.id, u.first_name)
    await update.message.reply_text(
        f"💰 *کیف پول {u.first_name}*\n\n"
        f"🪙 موجودی: *{user['balance']} میوپوینت*\n"
        f"🐱 گربه‌ها: {user['cats']} عدد",
        parse_mode="Markdown", reply_markup=KEYBOARD
    )

async def daily(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    user = get_user(u.id, u.first_name)
    ok, remaining = check_cooldown(user["last_daily"], 12)
    if not ok:
        await update.message.reply_text(f"⏳ جایزه‌ات رو قبلاً گرفتی!\n{remaining[0]} ساعت و {remaining[1]} دقیقه دیگه برگرد 😸", reply_markup=KEYBOARD)
        return
    amount = random.randint(10, 50)
    update_balance(u.id, amount)
    set_time(u.id, "last_daily")
    await update.message.reply_text(
        f"🎉 *جایزه دریافت شد!*\n\n"
        f"🪙 *+{amount} میوپوینت*\n"
        f"موجودی جدید: *{user['balance'] + amount} میوپوینت*\n\n"
        f"هر ۱۲ ساعت میتونی جایزه بگیری 😺",
        parse_mode="Markdown", reply_markup=KEYBOARD
    )

async def purr(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    user = get_user(u.id, u.first_name)
    ok, remaining = check_cooldown(user["last_purr"], 3)
    if not ok:
        await update.message.reply_text(f"😿 خیلی زود برگشتی!\n⏳ {remaining[0]} ساعت و {remaining[1]} دقیقه دیگه صبر کن", reply_markup=KEYBOARD)
        return
    bonus = random.randint(1, 6) if random.random() > 0.4 else 0
    set_time(u.id, "last_purr")
    if bonus:
        update_balance(u.id, bonus)
        await update.message.reply_text(f"😸 پوررر! چه صدای قشنگی!\n🪙 +{bonus} میوپوینت بونوس! 🐾", reply_markup=KEYBOARD)
    else:
        await update.message.reply_text("😺 میوووو! عالیه!\nبار بعدی شاید بونوس بگیری 🍀", reply_markup=KEYBOARD)

async def egg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    user = get_user(u.id, u.first_name)
    ok, remaining = check_cooldown(user["last_egg"], 24)
    if not ok:
        await update.message.reply_text(f"🐭 موش‌بگیر امروزت رو قبلاً باز کردی!\n⏳ {remaining[0]} ساعت و {remaining[1]} دقیقه دیگه برگرد", reply_markup=KEYBOARD)
        return

    set_time(u.id, "last_egg")
    roll = random.random() * 100

    if roll < 40:
        amount = random.randint(50, 100)
        update_balance(u.id, amount)
        await update.message.reply_text(
            f"🥚 *موش کوچولو !*\n\n"
            f"🪙 *+{amount} میوپوینت* پیدا کردی!\n"
            f"موجودی جدید: {user['balance'] + amount} میوپوینت",
            parse_mode="Markdown", reply_markup=KEYBOARD
        )
    elif roll < 70:
        amount = random.randint(100, 200)
        update_balance(u.id, amount)
        await update.message.reply_text(
            f"🥚✨ *موش فاضلاب !*\n\n"
            f"🪙 *+{amount} میوپوینت* پیدا کردی!\n"
            f"موجودی جدید: {user['balance'] + amount} میوپوینت",
            parse_mode="Markdown", reply_markup=KEYBOARD
        )
    elif roll < 90:
        emoji = random.choice(CAT_EMOJIS)
        name = random.choice(CAT_NAMES)
        add_cat_db(u.id, name, emoji, "normal")
        await update.message.reply_text(
            f"🐱 *یه گربه از تخم‌مرغ در اومد!*\n\n"
            f"{emoji} *{name}* به خانواده‌ات اضافه شد!\n"
            f"❤️ خوشحالی: ۱۰۰٪",
            parse_mode="Markdown", reply_markup=KEYBOARD
        )
    elif roll < 98:
        emoji = random.choice(RARE_EMOJIS)
        name = random.choice(RARE_CAT_NAMES)
        add_cat_db(u.id, name, emoji, "rare")
        await update.message.reply_text(
            f"✨ *گربه نادر پیدا کردی!*\n\n"
            f"{emoji} *{name}* — نادر\n"
            f"❤️ خوشحالی: ۱۰۰٪\n\n"
            f"خوش‌شانسی! 🍀",
            parse_mode="Markdown", reply_markup=KEYBOARD
        )
    else:
        emoji = random.choice(LEGEND_EMOJIS)
        name = random.choice(LEGEND_CAT_NAMES)
        add_cat_db(u.id, name, emoji, "legend")
        await update.message.reply_text(
            f"🥚👑 *گربه افسانه‌ای پیدا کردی!!!*\n\n"
            f"{emoji} *{name}* — افسانه‌ای\n"
            f"❤️ خوشحالی: ۱۰۰٪\n\n"
            f"معجزه! 🌟🌟🌟",
            parse_mode="Markdown", reply_markup=KEYBOARD
        )

async def adopt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    user = get_user(u.id, u.first_name)
    if user["balance"] < 50:
        await update.message.reply_text(
            f"😿 برای گربه گرفتن به *۵۰ میوپوینت* نیاز داری!\nموجودی فعلی: {user['balance']} میوپوینت",
            parse_mode="Markdown", reply_markup=KEYBOARD
        )
        return
    emoji = random.choice(CAT_EMOJIS)
    name = random.choice(CAT_NAMES)
    update_balance(u.id, -50)
    add_cat_db(u.id, name, emoji)
    await update.message.reply_text(
        f"🎉 *تبریک! گربه جدیدت اومد!*\n\n"
        f"{emoji} نام: *{name}*\n"
        f"❤️ خوشحالی: ۱۰۰٪\n\n"
        f"🪙 ۵۰ میوپوینت کم شد\n"
        f"موجودی: {user['balance'] - 50} میوپوینت",
        parse_mode="Markdown", reply_markup=KEYBOARD
    )

async def mycats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    cats = get_user_cats(u.id)
    if not cats:
        await update.message.reply_text("😿 هنوز گربه‌ای نداری!\nبا دکمه 🐱 گربه بگیر یه گربه بخر.", reply_markup=KEYBOARD)
        return
    text = f"📋 *گربه‌های {u.first_name}:*\n\n"
    rarity_label = {"normal": "", "rare": " ✨نادر", "legend": " 👑افسانه‌ای"}
    for cat in cats:
        filled = cat['happiness'] // 20
        bar = "❤️" * filled + "🖤" * (5 - filled)
        text += f"{cat['emoji']} *{cat['name']}*{rarity_label.get(cat['rarity'],'')} — {bar} {cat['happiness']}٪\n"
    text += "\n💡 از فروشگاه خرید کن تا خوشحالیشون بره بالا!"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=KEYBOARD)

async def shop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛍️ *فروشگاه بانک‌میو*\n\n"
        "هر آیتم خوشحالی یه گربه رو بالا میبره!\nیه آیتم انتخاب کن 👇",
        parse_mode="Markdown", reply_markup=shop_keyboard()
    )

async def stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    user = get_user(u.id, u.first_name)
    rank = get_rank(u.id)

    def time_text(last, hours):
        ok, rem = check_cooldown(last, hours)
        return "✅ آماده" if ok else f"⏳ {rem[0]}ساعت {rem[1]}دقیقه"

    await update.message.reply_text(
        f"📊 *آمار {u.first_name}*\n\n"
        f"🪙 موجودی: *{user['balance']} میوپوینت*\n"
        f"🐱 گربه‌ها: {user['cats']} عدد\n"
        f"🏅 رتبه: #{rank}\n"
        f"🎁 جایزه بعدی: {time_text(user['last_daily'], 12)}\n"
        f"😸 پورر بعدی: {time_text(user['last_purr'], 3)}\n"
        f"🐭 موش‌بگیر بعدی: {time_text(user['last_egg'], 24)}",
        parse_mode="Markdown", reply_markup=KEYBOARD
    )

async def top(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = get_top()
    medals = ["🥇","🥈","🥉"]
    text = "🏆 *سه گربه‌دار برتر بانک‌میو:*\n\n"
    for i, row in enumerate(rows):
        text += f"{medals[i]} {row[0] or 'ناشناس'} — 🪙 {row[1]} میوپوینت\n"
    if not rows:
        text += "هنوز کسی ثبت‌نام نکرده!"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=KEYBOARD)

async def transfer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    user = get_user(u.id, u.first_name)
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("📤 *نحوه انتقال:*\n\n`/transfer اسم مقدار`\n\nمثال:\n`/transfer علی 50`", parse_mode="Markdown", reply_markup=KEYBOARD)
        return
    target_name = args[0]
    try:
        amount = int(args[1])
    except:
        await update.message.reply_text("❌ مقدار باید عدد باشه!", reply_markup=KEYBOARD)
        return
    if amount <= 0:
        await update.message.reply_text("❌ مقدار باید مثبت باشه!", reply_markup=KEYBOARD)
        return
    total = amount + 2
    if user["balance"] < total:
        await update.message.reply_text(f"😿 موجودیت کافی نیست!\nنیاز داری: {total} میوپوینت\nموجودی: {user['balance']} میوپوینت", reply_markup=KEYBOARD)
        return
    conn = get_db()
    target = conn.execute("SELECT * FROM users WHERE first_name=?", (target_name,)).fetchone()
    conn.close()
    if not target:
        await update.message.reply_text(f"😿 کاربر {target_name} پیدا نشد!", reply_markup=KEYBOARD)
        return
    update_balance(u.id, -total)
    update_balance(target[0], amount)
    await update.message.reply_text(
        f"✅ *انتقال موفق!*\n\n📤 {amount} میوپوینت به {target_name} فرستادی\nموجودی جدید: {user['balance'] - total} میوپوینت",
        parse_mode="Markdown", reply_markup=KEYBOARD
    )

async def addmeow(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if u.id != ADMIN_ID:
        return
    if not ctx.args:
        await update.message.reply_text("بنویس: `/addmeow مقدار`", parse_mode="Markdown")
        return
    try:
        amount = int(ctx.args[0])
    except:
        await update.message.reply_text("❌ مقدار باید عدد باشه!")
        return
    update_balance(u.id, amount)
    user = get_user(u.id, u.first_name)
    await update.message.reply_text(f"👑 +{amount} میوپوینت اضافه شد!\nموجودی: {user['balance']} میوپوینت 😸", reply_markup=KEYBOARD)

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ *راهنمای بانک‌میو*\n\n"
        "💰 موجودی — کیف پولت\n"
        "🎁 جایزه — هر ۱۲ ساعت\n"
        "🐭 موش‌بگیر — هر ۲۴ ساعت\n"
        "🐱 گربه بگیر — با ۵۰ میوپوینت\n"
        "📋 گربه‌هام — لیست گربه‌هات\n"
        "🛍️ فروشگاه — خرید لوازم\n"
        "😸 پورر — بونوس هر ۳ ساعت\n"
        "🏆 برترین‌ها — سه نفر اول\n"
        "📊 آمار من — وضعیت کامل\n\n"
        "📤 `/transfer اسم مقدار` — انتقال",
        parse_mode="Markdown", reply_markup=KEYBOARD
    )

async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u = query.from_user

    if query.data == "back":
        await query.message.reply_text("به منوی اصلی برگشتی 😸", reply_markup=KEYBOARD)
        await query.message.delete()
        return

    if query.data == "goto_shop":
        await query.edit_message_text(
            "🛍️ *فروشگاه بانک‌میو*\n\nیه آیتم انتخاب کن 👇",
            parse_mode="Markdown", reply_markup=shop_keyboard()
        )
        return

    if query.data.startswith("shop_"):
        item_name = query.data.replace("shop_", "")
        user = get_user(u.id, u.first_name)
        item = SHOP_ITEMS.get(item_name)
        if not item:
            return
        if user["balance"] < item["price"]:
            await query.edit_message_text(
                f"😿 موجودیت کافی نیست!\nقیمت: {item['price']} میوپوینت\nموجودی: {user['balance']} میوپوینت",
                reply_markup=shop_keyboard()
            )
            return
        cats = get_user_cats(u.id)
        if not cats:
            await query.edit_message_text(
                f"😿 هنوز گربه‌ای نداری!\nاول یه گربه بگیر 🐱",
                reply_markup=shop_keyboard()
            )
            return
        await query.edit_message_text(
            f"🛍️ *{item['emoji']} {item_name}* رو برای کدوم گربه میخوای؟",
            parse_mode="Markdown",
            reply_markup=cat_select_keyboard(cats, item_name)
        )
        return

    if query.data.startswith("buyfor_"):
        parts = query.data.split("_")
        item_name = parts[1]
        cat_id = int(parts[2])
        user = get_user(u.id, u.first_name)
        item = SHOP_ITEMS.get(item_name)
        if not item:
            return
        if user["balance"] < item["price"]:
            await query.edit_message_text(
                f"😿 موجودیت کافی نیست!\nموجودی: {user['balance']} میوپوینت",
                reply_markup=shop_keyboard()
            )
            return
        update_balance(u.id, -item["price"])
        add_happiness_to_cat(cat_id, item["happiness"])
        cats = get_user_cats(u.id)
        cat = next((c for c in cats if c["id"] == cat_id), None)
        cat_name = cat["name"] if cat else "گربه‌ات"
        await query.edit_message_text(
            f"✅ *خرید موفق!*\n\n"
            f"{item['emoji']} *{item_name}* رو به *{cat_name}* دادی!\n"
            f"❤️ خوشحالی +{item['happiness']} شد!\n"
            f"🪙 موجودی جدید: {user['balance'] - item['price']} میوپوینت",
            parse_mode="Markdown", reply_markup=shop_keyboard()
        )

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "موجودی" in text:
        await balance(update, ctx)
    elif "جایزه" in text:
        await daily(update, ctx)
    elif "گربه بگیر" in text:
        await adopt(update, ctx)
    elif "گربه‌هام" in text or "گربه هام" in text:
        await mycats(update, ctx)
    elif "فروشگاه" in text:
        await shop(update, ctx)
    elif "پورر" in text:
        await purr(update, ctx)
    elif "موش" in text:
        await egg(update, ctx)
    elif "برترین" in text:
        await top(update, ctx)
    elif "آمار" in text:
        await stats(update, ctx)
    elif "راهنما" in text:
        await help_cmd(update, ctx)
    else:
        await update.message.reply_text("😸 این دستور رو نمی‌شناسم!\nاز دکمه‌های پایین استفاده کن 👇", reply_markup=KEYBOARD)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("purr", purr))
    app.add_handler(CommandHandler("egg", egg))
    app.add_handler(CommandHandler("adopt", adopt))
    app.add_handler(CommandHandler("mycats", mycats))
    app.add_handler(CommandHandler("shop", shop))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("transfer", transfer))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("addmeow", addmeow))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("🐱 بانک‌میو در حال اجراست...")
    app.run_polling()

if __name__ == "__main__":
    main()

