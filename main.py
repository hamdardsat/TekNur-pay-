import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 255196166  # آیدی خودت را بگذار

if not TOKEN:
    raise ValueError("BOT_TOKEN تنظیم نشده است ❌")

CUSTOMER_PRICES = {
    "60": 0.89,
    "325": 4.5,
    "660": 8.99,
    "1800": 22.5,
    "3850": 44.5,
    "8100": 89
}

conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS sellers (user_id INTEGER PRIMARY KEY, status TEXT, balance REAL DEFAULT 0, total_sales REAL DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS codes (code TEXT UNIQUE, amount TEXT, seller_id INTEGER, status TEXT)")
conn.commit()

user_states = {}

# ===== MENU =====
def reply_menu(user_id):
    cursor.execute("SELECT status FROM sellers WHERE user_id=?", (user_id,))
    seller = cursor.fetchone()

    keyboard = [["🛒 Buy UC", "💰 Wallet"]]

    if seller and seller[0] == "approved":
        keyboard.append(["📦 Seller Panel"])

    if user_id == ADMIN_ID:
        keyboard.append(["👑 Admin Panel"])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    await update.message.reply_text("🔥 Welcome to UC Shop", reply_markup=reply_menu(user_id))


# ===== BUY =====
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []

    for pkg, price in CUSTOMER_PRICES.items():
        cursor.execute("SELECT COUNT(*) FROM codes WHERE amount=? AND status='available'", (pkg,))
        stock = cursor.fetchone()[0]

        keyboard.append([
            InlineKeyboardButton(
                f"{pkg} UC - {price} USDT (Stock: {stock})",
                callback_data=f"buy_{pkg}"
            )
        ])

    await update.message.reply_text("Select Package:", reply_markup=InlineKeyboardMarkup(keyboard))


# ===== WALLET =====
async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    balance = result[0] if result else 0
    await update.message.reply_text(f"💰 Balance: {balance} USDT")


# ===== BUTTON HANDLER =====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data.startswith("buy_"):
        package = query.data.split("_")[1]
        price = CUSTOMER_PRICES[package]

        cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        balance = cursor.fetchone()[0]

        if balance < price:
            await query.edit_message_text("❌ Insufficient Balance")
            return

        cursor.execute("SELECT code FROM codes WHERE amount=? AND status='available' LIMIT 1", (package,))
        result = cursor.fetchone()

        if not result:
            await query.edit_message_text("❌ Out of Stock")
            return

        code = result[0]

        cursor.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (price, user_id))
        cursor.execute("UPDATE codes SET status='sold' WHERE code=?", (code,))
        conn.commit()

        await query.edit_message_text(f"✅ Code:\n{code}")


# ===== APPROVE =====
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Usage: /approve user_id")
        return

    seller_id = int(context.args[0])

    cursor.execute("""
        INSERT INTO sellers (user_id, status, balance, total_sales)
        VALUES (?, 'approved', 0, 0)
        ON CONFLICT(user_id) DO UPDATE SET status='approved'
    """, (seller_id,))
    conn.commit()

    await update.message.reply_text("✅ Seller Approved")


# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("wallet", wallet))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
