import sqlite3
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

TOKEN = "8296495325:AAEPHqQIgE2DmvBfaj045Yl4uXQg25P10TA"
ADMIN_ID = 255196166

CUSTOMER_PRICES = {
    "60": 0.89,
    "325": 4.5,
    "660": 8.99,
    "1800": 22.5,
    "3850": 44.5,
    "8100": 89
}

SELLER_PRICES = {
    "60": 0.870,
    "325": 4.425,
    "660": 8.850,
    "1800": 22.120,
    "3850": 44,
    "8100": 88
}

conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS sellers (user_id INTEGER PRIMARY KEY, status TEXT, balance REAL DEFAULT 0, total_sales REAL DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS codes (code TEXT UNIQUE, amount TEXT, seller_id INTEGER, status TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS withdrawals (seller_id INTEGER, amount REAL, status TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS profit (id INTEGER PRIMARY KEY, total REAL DEFAULT 0)")
conn.commit()

cursor.execute("INSERT OR IGNORE INTO profit (id, total) VALUES (1, 0)")
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


# ===== COMMANDS =====
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


async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    balance = cursor.fetchone()[0]
    await update.message.reply_text(f"💰 Your Balance: {balance} USDT")


async def seller_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("➕ Add Code", callback_data="add_code")],
        [InlineKeyboardButton("💰 Seller Balance", callback_data="seller_balance")],
        [InlineKeyboardButton("📤 Withdraw", callback_data="withdraw")]
    ]
    await update.message.reply_text("Seller Panel:", reply_markup=InlineKeyboardMarkup(keyboard))


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT total FROM profit WHERE id=1")
    total_profit = cursor.fetchone()[0]
    await update.message.reply_text(f"👑 Total Profit: {total_profit} USDT")


# ===== BUTTON HANDLER =====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # BUY PROCESS
    if query.data.startswith("buy_"):
        package = query.data.split("_")[1]
        price = CUSTOMER_PRICES[package]

        cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        balance = cursor.fetchone()[0]

        if balance < price:
            await query.edit_message_text("❌ Insufficient Balance")
            return

        cursor.execute("SELECT code, seller_id FROM codes WHERE amount=? AND status='available' LIMIT 1", (package,))
        result = cursor.fetchone()

        if not result:
            await query.edit_message_text("❌ Out of Stock")
            return

        code, seller_id = result

        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (price, user_id))

        seller_share = SELLER_PRICES[package]
        cursor.execute("UPDATE sellers SET balance = balance + ?, total_sales = total_sales + ? WHERE user_id=?",
                       (seller_share, seller_share, seller_id))

        profit_value = price - seller_share
        cursor.execute("UPDATE profit SET total = total + ? WHERE id=1", (profit_value,))

        cursor.execute("UPDATE codes SET status='sold' WHERE code=?", (code,))
        conn.commit()

        await query.edit_message_text(f"✅ Purchase Successful\n\nCode:\n{code}")

    # ADD CODE
    elif query.data == "add_code":
        keyboard = []
        for pkg in SELLER_PRICES.keys():
            keyboard.append([InlineKeyboardButton(f"{pkg} UC", callback_data=f"pkg_{pkg}")])
        await query.edit_message_text("Select Package:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("pkg_"):
        package = query.data.split("_")[1]
        user_states[user_id] = {"action": "add_code", "package": package}
        await query.edit_message_text(f"Send Code for {package} UC")

    elif query.data == "seller_balance":
        cursor.execute("SELECT balance FROM sellers WHERE user_id=?", (user_id,))
        balance = cursor.fetchone()[0]
        await query.edit_message_text(f"💰 Seller Balance: {balance} USDT")

    elif query.data == "withdraw":
        cursor.execute("SELECT balance FROM sellers WHERE user_id=?", (user_id,))
        balance = cursor.fetchone()[0]

        if balance <= 0:
            await query.edit_message_text("No balance available")
            return

        cursor.execute("INSERT INTO withdrawals VALUES (?, ?, 'pending')", (user_id, balance))
        cursor.execute("UPDATE sellers SET balance=0 WHERE user_id=?", (user_id,))
        conn.commit()

        await context.bot.send_message(ADMIN_ID, f"Withdrawal request from {user_id} Amount: {balance}")
        await query.edit_message_text("Withdrawal request sent")


# ===== STEP HANDLER =====
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id in user_states:
        state = user_states[user_id]
        if state["action"] == "add_code":
            package = state["package"]
            code = text.strip()

            try:
                cursor.execute("INSERT INTO codes VALUES (?, ?, ?, 'available')",
                               (code, package, user_id))
                conn.commit()
                await update.message.reply_text("✅ Code Added Successfully")
            except:
                await update.message.reply_text("❌ Code already exists")

            user_states.pop(user_id)
            return


# ===== APPROVE SELLER =====
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Use: /approve USER_ID")
        return

    seller_id = int(context.args[0])

    cursor.execute("INSERT OR IGNORE INTO sellers (user_id, status, balance, total_sales) VALUES (?, 'approved', 0, 0)", (seller_id,))
    cursor.execute("UPDATE sellers SET status='approved' WHERE user_id=?", (seller_id,))
    conn.commit()

    await update.message.reply_text(f"Seller {seller_id} Approved ✅")
    await context.bot.send_message(seller_id, "🎉 You are now approved seller\nPress /start")


# ===== CONFIRM WITHDRAW =====
async def confirmwithdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    seller_id = int(context.args[0])
    cursor.execute("UPDATE withdrawals SET status='paid' WHERE seller_id=? AND status='pending'", (seller_id,))
    conn.commit()

    await update.message.reply_text("Withdrawal Confirmed")


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("buy", buy))
app.add_handler(CommandHandler("wallet", wallet))
app.add_handler(CommandHandler("seller", seller_panel))
app.add_handler(CommandHandler("admin", admin_panel))
app.add_handler(CommandHandler("approve", approve))
app.add_handler(CommandHandler("confirmwithdraw", confirmwithdraw))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

app.run_polling()
