import os
import random
import sqlite3
from datetime import date, datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes
)

TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = 1026211406

def get_db():
    conn = sqlite3.connect("bankmeow.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            first_name  TEXT,
            balance     INTEGER DEFAULT 100,
            cats        INTEGER DEFAULT 0,
            last_daily  TEXT DEFAULT '',
            last_purr   TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cats (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            name        TEXT,
            emoji       TEXT,
            happiness   INTEGER DEFAULT 100,
            last_update TEXT DEFAULT ''
        )
    """)
    # اضافه کردن ستون last_purr اگه وجود نداشت
    try:
        conn.execute("ALTER TABLE users ADD COLUMN last_purr TEXT DEFAULT ''")
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
    return {
        "user_id": row[0], "first_name": row[1],
        "balance": row[2], "cats": row[3],
        "last_daily": row[4], "last_purr": row[5] if len(row) > 5 else ""
    }

def update_balance(user_id, amount):
    conn = get_db()
    conn.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def set_daily(user_id):
    conn = get_db()
    conn.execute("UPDATE users SET last_daily=? WHERE user_id=?", (str(date.today()), user_id))
    conn.commit()
    conn.close()

def set_purr(user_id):
    conn = get_db()
    conn.execute("UPDATE users SET last_purr=? WHERE user_id=?", (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()

def add_cat_db(user_id, name, emoji):
    conn = get_db()
    conn.execute("INSERT INTO cats (user_id, name, emoji, happiness, last_update) VALUES (?,?,?,100,?)",
                 (user_id, name, emoji, datetime.now().isoformat()))
    conn.execute("UPDATE users SET cats = cats + 1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def get_user_cats(user_id):
    conn = get_db()
    # کم کردن خوشحالی بر اساس زمان
    cats = conn.execute("SELECT id, name, emoji, happiness, last_update FROM cats WHERE user_id=?", (user_id,)).fetchall()
    updated_cats = []
    for cat in cats:
        cat_id, name, emoji, happiness, last_update = cat
        if last_update:
            try:
                last_dt = datetime.fromisoformat(last_update)
                hours_passed = (datetime.now() - last_dt).total_seconds() / 3600
                decrease = int(hours_passed / 24 * 10)
                new_happiness = max(0, happiness - decrease)
                if new_happiness != happiness:
                    conn.execute("UPDATE cats SET happiness=?, last_update=? WHERE id=?",
                                 (new_happiness, datetime.now().isoformat(), cat_id))
                happiness = new_happiness
            except:
                pass
        updated_cats.append({"id": cat_id, "name": name, "emoji": emoji, "happiness": happiness})
    conn.commit()
    conn.close()
    return updated_cats

def add_happiness(user_id, amount):
    conn = get_db()
    cats = conn.execute("SELECT id, happiness FROM cats WHERE user_id=?", (user_id,)).fetchall()
    for cat in cats:
        new_happiness = min(100, cat[1] + amount)
        conn.execute("UPDATE cats SET happiness=? WHERE id=?", (new_happiness, cat[0]))
    conn.commit()
    conn.close()
    return len(cats)

def get_top():
    conn = get_db()
    rows = conn.execute("SELECT first_name, balance FROM users ORDER BY balance DESC LIMIT 3").fetchall()
    conn.close()
    return rows

KEYBOARD = ReplyKeyboardMarkup([
    ["💰 موجودی", "🎁 جایزه روزانه"],
    ["🐱 گربه بگیر", "🏆 جدول برترین‌ها"],
    ["🛍️ فروشگاه", "❓ راهنما"],
], resize_keyboard=True)

SHOP_ITEMS = {
    "ماهی":  {"price": 20,  "emoji": "🐟", "happiness": 15},
    "توپ":   {"price": 30,  "emoji": "🎯", "happiness": 20},
    "تخت":   {"price": 80,  "emoji": "🛏️", "happiness": 30},
    "ریبون": {"price": 15,  "emoji": "🎀", "happiness": 10},
    "خانه":  {"price": 200, "emoji": "🏡", "happiness": 50},
    "تاج":   {"price": 500, "emoji": "👑", "happiness": 80},
}

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    get_user(u.id, u.first_name)
    await update.message.reply_text(
        f"🐱 سلام {u.first_name}! خوش اومدی به *بانک‌میو*!\n\n"
        "🪙 واحد پولی ما *میوپوینت* هست!\n"
        "با ۱۰۰ میوپوینت شروع کردی 🎉\n\n"
        "از دکمه‌های پایین استفاده کن 👇",
        parse_mode="Markdown", reply_markup=KEYBOARD
    )

async def balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    user = get_user(u.id, u.first_name)
    await update.message.reply_text(
        f"💰 *کیف پول میوپوینت*\n\n"
        f"🪙 موجودی: *{user['balance']} میوپوینت*\n"
        f"🐱 گربه‌ها: {user['cats']} عدد\n\n"
        f"{'💡 جایزه روزانه‌ات رو بگیر! 🎁' if user['balance'] < 50 else '😸 آفرین! داری پیشرفت می‌کنی!'}",
        parse_mode="Markdown", reply_markup=KEYBOARD
    )

async def daily(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    user = get_user(u.id, u.first_name)
    if user["last_daily"] == str(date.today()):
        await update.message.reply_text("⏳ جایزه روزانه‌ات رو قبلاً گرفتی!\nفردا دوباره بیا 😸", reply_markup=KEYBOARD)
        return
    amount = random.randint(10, 50)
    update_balance(u.id, amount)
    set_daily(u.id)
    await update.message.reply_text(
        f"🎉 *جایزه روزانه دریافت شد!*\n\n"
        f"🪙 *+{amount} میوپوینت* به حسابت اضافه شد!\n"
        f"موجودی جدید: *{user['balance'] + amount} میوپوینت*\n\nفردا دوباره بیا 😺",
        parse_mode="Markdown", reply_markup=KEYBOARD
    )

async def purr(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    user = get_user(u.id, u.first_name)
    # چک کردن ۶ ساعت
    if user["last_purr"]:
        try:
            last_purr_dt = datetime.fromisoformat(user["last_purr"])
            diff = datetime.now() - last_purr_dt
            if diff < timedelta(hours=6):
                remaining = timedelta(hours=6) - diff
                hours = int(remaining.total_seconds() // 3600)
                mins = int((remaining.total_seconds() % 3600) // 60)
                await update.message.reply_text(
                    f"😿 خیلی زود برگشتی!\n⏳ {hours} ساعت و {mins} دقیقه دیگه صبر کن",
                    reply_markup=KEYBOARD
                )
                return
        except:
            pass
    bonus = random.randint(1, 6) if random.random() > 0.4 else 0
    if bonus:
        update_balance(u.id, bonus)
        await update.message.reply_text(f"😸 پوررر! چه صدای قشنگی!\n🪙 +{bonus} میوپوینت بونوس! 🐾", reply_markup=KEYBOARD)
    else:
        await update.message.reply_text("😺 میوووو! عالیه!\nبار بعدی شاید بونوس بگیری 🍀", reply_markup=KEYBOARD)
    set_purr(u.id)

async def adopt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    user = get_user(u.id, u.first_name)
    if user["balance"] < 50:
        await update.message.reply_text(
            f"😿 برای گربه گرفتن به *۵۰ میوپوینت* نیاز داری!\nموجودی فعلی: {user['balance']} میوپوینت",
            parse_mode="Markdown", reply_markup=KEYBOARD
        )
        return
    cat_emojis = ["😸","🐱","😺","😻","🐈","🐈‍⬛"]
    names = ["پیشی","گربولو","میومیو","خرناس","نازگل","شیطون","پنجول","ابری"]
    emoji = random.choice(cat_emojis)
    name = random.choice(names)
    update_balance(u.id, -50)
    add_cat_db(u.id, name, emoji)
    await update.message.reply_text(
        f"🎉 *تبریک! گربه جدیدت اومد!*\n\n{emoji} نام: *{name}*\n"
        f"⭐ سطح: ۱\n❤️ خوشحالی: ۱۰۰٪\n\n"
        f"🪙 ۵۰ میوپوینت کم شد\nموجودی: {user['balance'] - 50} میوپوینت\n\n"
        f"از گربه‌ات نگهداری کن! با /mycats ببینشون 🐾",
        parse_mode="Markdown", reply_markup=KEYBOARD
    )

async def mycats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    cats = get_user_cats(u.id)
    if not cats:
        await update.message.reply_text("😿 هنوز گربه‌ای نداری!\nبا دکمه 🐱 گربه بگیر یه گربه بخر.", reply_markup=KEYBOARD)
        return
    text = "🐱 *گربه‌های تو:*\n\n"
    for cat in cats:
        bar = "❤️" * (cat['happiness'] // 20) + "🖤" * (5 - cat['happiness'] // 20)
        text += f"{cat['emoji']} *{cat['name']}*\n{bar} {cat['happiness']}٪\n\n"
    text += "💡 با خرید از فروشگاه خوشحالیشون رو بالا ببر!"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=KEYBOARD)

async def shop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛍️ *فروشگاه بانک‌میو*\n\n"
        "🐟 ماهی طلایی — 20 میوپوینت — /buy ماهی\n"
        "🎯 توپ موشی — 30 میوپوینت — /buy توپ\n"
        "🛏️ تخت ابری — 80 میوپوینت — /buy تخت\n"
        "🎀 ریبون صورتی — 15 میوپوینت — /buy ریبون\n"
        "🏡 خانه گربه‌ای — 200 میوپوینت — /buy خانه\n"
        "👑 تاج میومیو — 500 میوپوینت — /buy تاج\n\n"
        "💡 هر آیتم خوشحالی گربه‌هات رو بالا میبره!",
        parse_mode="Markdown", reply_markup=KEYBOARD
    )

async def buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    user = get_user(u.id, u.first_name)
    if not ctx.args:
        await update.message.reply_text("برای خرید بنویس:\n`/buy نام_آیتم`\n\nمثال: `/buy ماهی`", parse_mode="Markdown", reply_markup=KEYBOARD)
        return
    item_name = ctx.args[0]
    if item_name not in SHOP_ITEMS:
        await update.message.reply_text("😿 آیتم پیدا نشد!\n\nآیتم‌های موجود:\nماهی، توپ، تخت، ریبون، خانه، تاج", reply_markup=KEYBOARD)
        return
    item = SHOP_ITEMS[item_name]
    if user["balance"] < item["price"]:
        await update.message.reply_text(f"😿 موجودیت کافی نیست!\nقیمت: {item['price']} میوپوینت\nموجودی فعلی: {user['balance']} میوپوینت", reply_markup=KEYBOARD)
        return
    update_balance(u.id, -item["price"])
    cat_count = add_happiness(u.id, item["happiness"])
    msg = f"✅ *خرید موفق!*\n\n{item['emoji']} *{item_name}* رو خریدی!\n🪙 {item['price']} میوپوینت کم شد\nموجودی جدید: {user['balance'] - item['price']} میوپوینت"
    if cat_count > 0:
        msg += f"\n\n😸 خوشحالی {cat_count} گربه‌ات +{item['happiness']} شد!"
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=KEYBOARD)

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
        await update.message.reply_text(f"😿 موجودیت کافی نیست!\nنیاز داری: {total} میوپوینت\nموجودی فعلی: {user['balance']} میوپوینت", reply_markup=KEYBOARD)
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
        await update.message.reply_text("😾 دسترسی نداری!", reply_markup=KEYBOARD)
        return
    if not ctx.args:
        await update.message.reply_text("بنویس: `/addmeow مقدار`", parse_mode="Markdown", reply_markup=KEYBOARD)
        return
    try:
        amount = int(ctx.args[0])
    except:
        await update.message.reply_text("❌ مقدار باید عدد باشه!", reply_markup=KEYBOARD)
        return
    update_balance(u.id, amount)
    user = get_user(u.id, u.first_name)
    await update.message.reply_text(f"👑 *ادمین:* +{amount} میوپوینت اضافه شد!\nموجودی جدید: {user['balance']} میوپوینت 😸", parse_mode="Markdown", reply_markup=KEYBOARD)

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ *راهنمای بانک‌میو*\n\n"
        "/start — شروع\n"
        "/balance — موجودی\n"
        "/daily — جایزه روزانه\n"
        "/purr — بونوس (هر ۶ ساعت)\n"
        "/transfer — انتقال میوپوینت\n"
        "/adopt — گربه بگیر\n"
        "/mycats — لیست گربه‌هات\n"
        "/shop — فروشگاه\n"
        "/buy — خرید از فروشگاه\n"
        "/top — سه برتر 🏆",
        parse_mode="Markdown", reply_markup=KEYBOARD
    )

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "موجودی" in text:
        await balance(update, ctx)
    elif "جایزه" in text:
        await daily(update, ctx)
    elif "گربه" in text:
        await adopt(update, ctx)
    elif "جدول" in text or "برترین" in text:
        await top(update, ctx)
    elif "فروشگاه" in text:
        await shop(update, ctx)
    elif "راهنما" in text:
        await help_cmd(update, ctx)
    else:
        await update.message.reply_text("😸 این دستور رو نمی‌شناسم!\n/help بزن یا از دکمه‌ها استفاده کن.", reply_markup=KEYBOARD)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("purr", purr))
    app.add_handler(CommandHandler("transfer", transfer))
    app.add_handler(CommandHandler("adopt", adopt))
    app.add_handler(CommandHandler("mycats", mycats))
    app.add_handler(CommandHandler("shop", shop))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("addmeow", addmeow))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("🐱 بانک‌میو در حال اجراست...")
    app.run_polling()

if __name__ == "__main__":
    main()
