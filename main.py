import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# گرفتن توکن از Railway Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")

# منیو اصلی
main_menu = ReplyKeyboardMarkup(
    [["📦 لیست کدها"], ["👤 پشتیبانی"]],
    resize_keyboard=True
)

# دیتابیس ساده داخل حافظه (فعلاً)
codes = []

# دستور استارت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "به ربات خوش آمدید ✅",
        reply_markup=main_menu
    )

# نمایش لیست کدها
async def show_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not codes:
        await update.message.reply_text("هیچ کدی موجود نیست ❌")
    else:
        text = "📦 کدهای موجود:\n\n"
        for c in codes:
            text += f"{c}\n"
        await update.message.reply_text(text)

# پیام‌های عادی
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📦 لیست کدها":
        await show_codes(update, context)

    elif text == "👤 پشتیبانی":
        await update.message.reply_text("برای پشتیبانی با ادمین تماس بگیرید.")

# اجرای ربات
def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN تنظیم نشده ❌")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling()

if name == "main":
    main()
