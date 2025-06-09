# bot_webhook.py

import sys
import os
import asyncio
import aiohttp
from flask import Flask, request, jsonify

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

# --- PHẦN BOT CỦA CẬU (giữ nguyên logic) ---
API_URL_TIKTOK = "https://ahihi.x10.mx/fltik.php?user={username}&key=khang"
BOT_TOKEN = "7805035127:AAEA5bsioLvnaZKo4XoXy4P1n-VMfmaGbK0" # Token của cậu

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Chào bạn! Gõ /info <username> để lấy thông tin TikTok.")

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        username = context.args[0]
        await handle_lookup(update, context, username)
    else:
        await update.message.reply_text("Vui lòng nhập username. Ví dụ: /info khangdino206")

async def handle_lookup(update_or_query, context, username):
    # Xác định đối tượng để trả lời tin nhắn
    if hasattr(update_or_query, 'message') and update_or_query.message:
        reply_obj = update_or_query.message
        status_msg = await reply_obj.reply_text("⏳ Đang tra cứu thông tin...")
    elif hasattr(update_or_query, 'callback_query') and update_or_query.callback_query:
        reply_obj = update_or_query.callback_query.message
        # Gửi một tin nhắn mới thay vì chỉnh sửa tin nhắn cũ có nút bấm
        status_msg = await reply_obj.chat.send_message("⏳ Đang tra cứu lại thông tin...")
    else: # Fallback an toàn
        return

    api_url = API_URL_TIKTOK.format(username=username)
    print(f"[DEBUG] Gọi API: {api_url}", file=sys.stderr)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=10) as response: # Tăng timeout lên 10s
                print(f"[DEBUG] HTTP status: {response.status}", file=sys.stderr)
                if response.status == 200:
                    data = await response.json()
                    print(f"[DEBUG] Dữ liệu trả về: {data}", file=sys.stderr)
                    if data.get("success") or data.get("status") == "success":
                        tiktok_url = f"https://www.tiktok.com/@{data.get('username', username)}"
                        keyboard = [
                            [InlineKeyboardButton("🔗 Xem profile TikTok", url=tiktok_url)],
                            [InlineKeyboardButton("🔄 Tra cứu lại", callback_data=f"info_{username}")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        msg = (
                            f"👤 <b>Username:</b> {data.get('username', 'N/A')}\n"
                            f"🏷️ <b>Nickname:</b> {data.get('nickname', 'N/A')}\n"
                            f"🌍 <b>Region:</b> {data.get('region', 'N/A')}\n"
                            f"👥 <b>Followers:</b> {data.get('followers_count', data.get('followers', 'N/A'))}\n"
                            f"➡️ <b>Following:</b> {data.get('following_count', 'N/A')}\n"
                            f"📝 <b>Bio:</b> {data.get('bio', '(trống)')}\n"
                            f"🔒 <b>Private Account:</b> {'Riêng tư' if data.get('privateAccount', False) else 'Công khai'}"
                        )
                        avatar = data.get('profilePic', data.get('profile_pic', ''))
                        await status_msg.delete()
                        if avatar:
                            await reply_obj.reply_photo(photo=avatar, caption=msg, parse_mode='HTML', reply_markup=reply_markup)
                        else:
                            await reply_obj.reply_text(msg, parse_mode='HTML', reply_markup=reply_markup)
                    else:
                        await status_msg.edit_text(f"Lỗi: {data.get('message', 'Không tìm thấy user hoặc API lỗi')}")
                else:
                    error_text = await response.text()
                    await status_msg.edit_text(f"Lỗi HTTP {response.status}: Server API không phản hồi.")
    except Exception as e:
        print(f"[DEBUG] Exception: {e}", file=sys.stderr)
        await status_msg.edit_text(f"Đã xảy ra lỗi khi tra cứu: {e}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("info_"):
        username = query.data.replace("info_", "")
        # Gọi lại hàm tra cứu
        await handle_lookup(update, context, username)

# --- PHẦN SERVER (thêm vào để chạy trên Render) ---
# Khởi tạo web server bằng Flask
server = Flask(__name__)

# Khởi tạo bot application
# Chú ý: không có .build() ở đây vội
application = Application.builder().token(BOT_TOKEN).build()

# Thêm các handler vào application như cũ
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("info", info))
application.add_handler(CallbackQueryHandler(button_callback))

# Route mặc định để cron-job.org gọi vào, giúp bot luôn "thức"
@server.route("/")
def index():
    return "Bot đang hoạt động ngon lành cành đào!", 200

# Route để Telegram gửi update (webhook)
@server.route("/webhook", methods=["POST"])
async def webhook():
    # Lấy dữ liệu Telegram gửi đến và đưa cho application xử lý
    await application.update_queue.put(Update.de_json(request.get_json(force=True), application.bot))
    return "OK", 200

# Hàm main để khởi chạy mọi thứ
async def main():
    # Lấy URL của web service trên Render
    # Render sẽ tự động set biến môi trường RENDER_EXTERNAL_URL
    webhook_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not webhook_url:
        print("Không tìm thấy RENDER_EXTERNAL_URL, không thể set webhook.", file=sys.stderr)
        return

    # Khởi tạo event loop để chạy các tác vụ bất đồng bộ
    # Đây là một kỹ thuật để chạy application.initialize() và application.start() mà không block
    # toàn bộ chương trình, cho phép Flask server chạy song song.
    async with application:
        await application.initialize()
        await application.start()
        
        # Set webhook cho Telegram, chỉ đường cho nó đến URL của chúng ta
        # Thêm /webhook vào cuối URL
        print(f"Đang set webhook tới: {webhook_url}/webhook", file=sys.stderr)
        await application.bot.set_webhook(url=f"{webhook_url}/webhook")

        # Lấy port mà Render cung cấp
        port = int(os.environ.get("PORT", 8080))
        # Chạy Flask server
        # Dùng `if __name__ == '__main__':` để đảm bảo phần này chỉ chạy khi file được thực thi trực tiếp
        # Gunicorn (sẽ dùng trên Render) sẽ không chạy vào đây.
        # Dòng này chủ yếu để test trên máy cá nhân.
        # server.run(host="0.0.0.0", port=port) # Dòng này không cần thiết khi deploy với gunicorn

# Chạy hàm main khi khởi động
# Dùng asyncio.run() để thực thi hàm async main
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    if loop.is_running():
        print("Asyncio loop is already running.")
        task = loop.create_task(main())
    else:
        asyncio.run(main())