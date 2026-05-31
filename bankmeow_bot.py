import os
import random
import sqlite3
from datetime import date
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)

TOKEN = os.environ.get("BOT_TOKEN", "")

def get_db():
    conn = sqlite3.connect("bankmeow.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            first_name  TEXT,
            balance     INTEGER DEFAULT 100,
            cats        INTEGER DEFAULT 0,
            last_daily  TEXT DEFAULT ''
        )
    """)
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
    return {"user_id": row[0], "first_name": row[1], "balance": row[2], "cats": row[3], "last_daily": row[4]}

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

def add_cat(user_id):
    conn = get_db()
    conn.execute("UPDATE users SET cats = cats + 1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def get_top():
    conn = get_db()
    rows = conn.execute("SELECT first_name, balance FROM users ORDER BY balance DESC LIMIT 10").fetchall()
    conn.close()
    return rows

KEYBOARD = ReplyKeyboardMarkup([
    ["💰 موجودی", "🎁 جایزه روزانه"],
    ["🐱 گربه بگیر", "🏆 جدول برترین‌ها"],
    ["🛍️ فروشگاه", "❓ راهنما"],
], resize_keyboard=True)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    get_user(u.id, u.first_name)
    await update.message.reply_text(
        f"🐱 سلام {u.first_name}! خوش اومدی به *بانک‌میو*!\n\n"
        "🪙 واحد پولی ما *میوپوینت* هست!\n"
        "با ۱۰۰ میوپوینت شروع کردی 🎉\n\n"
        "از دکمه‌های پایین استفاده کن 👇",
        parse_mode="Markdown",
        reply_markup=KEYBOARD
    )

async def balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    user = get_user(u.id, u.first_name)
    await update.message.reply_text(
        f"💰 *کیف پول میوپوینت*\n\n"
        f"🪙 موجودی: *{user['balance']} میوپوینت*\n"
        f"🐱 گربه‌ها: {user['cats']} عدد\n\n"
        f"{'💡 جایزه روزانه‌ات رو بگیر! 🎁' if user['balance'] < 50 else '😸 آفرین! داری پیشرفت می‌کنی!'}",
        parse_mode="Markdown",
        reply_markup=KEYBOARD
    )

async def daily(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    user = get_user(u.id, u.first_name)
    today = str(date.today())
    if user["last_daily"] == today:
        await update.message.reply_text("⏳ جایزه روزانه‌ات رو قبلاً گرفتی!\nفردا دوباره بیا 😸", reply_markup=KEYBOARD)
        return
    amount = random.randint(10, 50)
    update_balance(u.id, amount)
    set_daily(u.id)
    new_bal = user["balance"] + amount
    await update.message.reply_text(
        f"🎉 *جایزه روزانه دریافت شد!*\n\n"
        f"🪙 *+{amount} میوپوینت* به حسابت اضافه شد!\n"
        f"موجودی جدید: *{new_bal} میوپوینت*\n\nفردا دوباره بیا 😺",
        parse_mode="Markdown",
        reply_markup=KEYBOARD
    )

async def transfer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    user = get_user(u.id, u.first_name)
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text(
            "📤 *نحوه انتقال:*\n\n`/transfer @username مقدار`\n\nمثال:\n`/transfer @GorbehKhan 50`",
            parse_mode="Markdown", reply_markup=KEYBOARD
        )
        return
    target_username = args[0].replace("@", "")
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
    target = conn.execute("SELECT * FROM users WHERE first_name=?", (target_username,)).fetchone()
    conn.close()
    if not target:
        await update.message.reply_text(f"😿 کاربر {target_username} پیدا نشد!", reply_markup=KEYBOARD)
        return
    update_balance(u.id, -total)
    update_balance(target[0], amount)
    await update.message.reply_text(
        f"✅ *انتقال موفق!*\n\n📤 {amount} میوپوینت به {target_username} فرستادی\nموجودی جدید: {user['balance'] - total} میوپوینت",
        parse_mode="Markdown", reply_markup=KEYBOARD
    )

async def adopt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    user = get_user(u.id, u.first_name)
    if user["balance"] < 50:
        await update.message.reply_text(f"😿 برای گربه گرفتن به *۵۰ میوپوینت* نیاز داری!\nموجودی فعلی: {user['balance']} میوپوینت", parse_mode="Markdown", reply_markup=KEYBOARD)
        return
    cats = ["😸","🐱","😺","😻","🐈","🐈‍⬛"]
    names = ["پیشی","گربولو","میومیو","خرناس","نازگل","شیطون","پنجول","ابری"]
    cat = random.choice(cats)
    name = random.choice(names)
    update_balance(u.id, -50)
    add_cat(u.id)
    await update.message.reply_text(
        f"🎉 *تبریک! گربه جدیدت اومد!*\n\n{cat} نام: *{name}*\n⭐ سطح: ۱\n❤️ خوشحالی: ۱۰۰٪\n\n🪙 ۵۰ میوپوینت کم شد\nموجودی: {user['balance'] - 50} میوپوینت",
        parse_mode="Markdown", reply_markup=KEYBOARD
    )

async def shop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛍️ *فروشگاه بانک‌میو*\n\n"
        "🐟 ماهی طلایی — 20 میوپوینت\n"
        "🎯 توپ موشی — 30 میوپوینت\n"
        "🛏️ تخت ابری — 80 میوپوینت\n"
        "🎀 ریبون صورتی — 15 میوپوینت\n"
        "🏡 خانه گربه‌ای — 200 میوپوینت\n"
        "👑 تاج میومیو — 500 میوپوینت",
        parse_mode="Markdown", reply_markup=KEYBOARD
    )

async def top(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = get_top()
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    text = "🏆 *برترین گربه‌داران بانک‌میو:*\n\n"
    for i, row in enumerate(rows):
        text += f"{medals[i]} {row[0] or 'ناشناس'} — 🪙 {row[1]} میوپوینت\n"
    if not rows:
        text += "هنوز کسی ثبت‌نام نکرده!"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=KEYBOARD)

async def purr(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    bonus = random.randint(1, 6) if random.random() > 0.4 else 0
    if bonus:
        update_balance(u.id, bonus)
        await update.message.reply_text(f"😸 پوررر! چه صدای قشنگی!\n🪙 +{bonus} میوپوینت بونوس! 🐾", reply_markup=KEYBOARD)
    else:
        await update.message.reply_text("😺 میوووو! عالیه!\nبار بعدی شاید بونوس بگیری 🍀", reply_markup=KEYBOARD)

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ *راهنمای بانک‌میو*\n\n"
        "/start — شروع\n/balance — موجودی\n/daily — جایزه روزانه\n"
        "/transfer — انتقال\n/adopt — گربه بگیر\n/shop — فروشگاه\n"
        "/top — جدول برترین‌ها\n/purr — شاید بونوس بگیری 😸",
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
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("transfer", transfer))
    app.add_handler(CommandHandler("adopt", adopt))
    app.add_handler(CommandHandler("shop", shop))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("purr", purr))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("🐱 بانک‌میو در حال اجراست...")
    app.run_polling()

if __name__ == "__main__":
    main()
