from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes
import requests
import json
import os
import asyncio
import logging

# Thiết lập logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_URL = "https://ahihi.x10.mx/fltik.php?user={username}&key=khang"
session = requests.Session()  # Tái sử dụng kết nối HTTP

app = Flask(__name__)

# --- Telegram Application ---
TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # Lấy từ biến môi trường
if not TOKEN or not WEBHOOK_URL:
    raise ValueError("BOT_TOKEN và WEBHOOK_URL phải được thiết lập trong biến môi trường")

TELEGRAM_APP = Application.builder().token(TOKEN).base_url("https://proxy.accpreytb4month.workers.dev/bot").build()

# Hàm gửi thông tin đẹp với Markdown, ảnh đại diện, nút bấm
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Nhận lệnh /info từ user {update.effective_user.id} với args: {context.args}")
    if context.args:
        username = context.args[0]
        await update.message.reply_text("⏳ Đang tra cứu, vui lòng chờ...")
        url = API_URL.format(username=username)
        try:
            response = session.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    msg = (
                        f"*👤 Username:* `{data['username']}`\n"
                        f"*🆔 User ID:* `{data['user_id']}`\n"
                        f"*🌍 Region:* `{data['region']}`\n"
                        f"*👥 Followers:* `{data['followers_count']}`\n"
                        f"*➡️ Following:* `{data['following_count']}`\n"
                        f"*📝 Bio:* _{data['bio']}_\n"
                        f"*🏷️ Nickname:* `{data['nickname']}`\n"
                        f"*🔒 Private:* `{data['privateAccount']}`\n"
                    )
                    keyboard = [
                        [InlineKeyboardButton("Xem trên TikTok", url=f"https://www.tiktok.com/@{data['username']}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await update.message.reply_photo(
                        photo=data['profilePic'],
                        caption=msg,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=reply_markup
                    )
                    logger.info(f"Đã gửi thông tin TikTok cho user {update.effective_user.id} ({username})")
                else:
                    await update.message.reply_text("Không lấy được thông tin từ API.")
                    logger.warning(f"API trả về không thành công cho username: {username}")
            else:
                await update.message.reply_text("Lỗi kết nối API.")
                logger.error(f"Lỗi kết nối API với username: {username}, status_code: {response.status_code}")
        except Exception as e:
            await update.message.reply_text("Lỗi khi truy vấn API hoặc API quá chậm.")
            logger.exception(f"Lỗi khi truy vấn API cho username: {username}")
    else:
        await update.message.reply_text("Vui lòng nhập username. Ví dụ: /info khangdino206")
        logger.warning("Lệnh /info không có username đi kèm.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot đã sẵn sàng hỗ trợ tra cứu thông tin TikTok!")
    logger.info(f"User {update.effective_user.id} đã dùng lệnh /start")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """*Các lệnh hỗ trợ:*
/help - Hiển thị hướng dẫn sử dụng và các lệnh
/info <username> - Tra cứu thông tin TikTok của username
/start - Chào bot
Ví dụ: /info khangdino206
"""
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    logger.info(f"User {update.effective_user.id} đã dùng lệnh /help")

# Thêm handler cho các lệnh
TELEGRAM_APP.add_handler(CommandHandler("start", start))
TELEGRAM_APP.add_handler(CommandHandler("help", help_command))
TELEGRAM_APP.add_handler(CommandHandler("info", info))

# Flask endpoint để kiểm tra server
@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "Bot is running"})

# Flask endpoint nhận webhook từ Telegram
@app.route("/webhook", methods=["POST"])
async def webhook():
    await TELEGRAM_APP.initialize()  # Đảm bảo đã initialize trước khi xử lý update
    update = Update.de_json(request.get_json(force=True), TELEGRAM_APP.bot)
    await TELEGRAM_APP.process_update(update)
    return jsonify({"ok": True})

# Hàm thiết lập webhook
async def set_webhook():
    logger.info("Đang thiết lập webhook...")
    try:
        await TELEGRAM_APP.initialize()  # Đảm bảo đã initialize trước khi set webhook
        await TELEGRAM_APP.bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Webhook được thiết lập thành công tại: {WEBHOOK_URL}")
    except Exception as e:
        logger.error(f"Lỗi khi thiết lập webhook: {e}")

# Hàm chạy ứng dụng
def run_app():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(set_webhook())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

if __name__ == '__main__':
    run_app()