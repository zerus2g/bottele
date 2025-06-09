# bot_webhook.py

import sys
import os
import asyncio
import aiohttp
from flask import Flask, request

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

# --- CẤU HÌNH ---
# Lấy token từ biến môi trường của Render để bảo mật hơn, nếu không có thì dùng token dự phòng.
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7805035127:AAEA5bsioLvnaZKo4XoXy4P1n-VMfmaGbK0") 
API_URL_TIKTOK = "https://ahihi.x10.mx/fltik.php?user={username}&key=khang"

# --- LOGIC CỐT LÕI CỦA BOT ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gửi tin nhắn chào mừng khi người dùng gõ /start"""
    await update.message.reply_text("Chào bạn! Gõ /info <username> để lấy thông tin tài khoản TikTok.")

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /info"""
    if context.args:
        username = context.args[0]
        # Gọi hàm xử lý tra cứu chính
        await handle_lookup(update, context, username)
    else:
        await update.message.reply_text("Cú pháp sai! Vui lòng nhập theo mẫu: /info <username>")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi người dùng nhấn nút 'Tra cứu lại'"""
    query = update.callback_query
    await query.answer()  # Phản hồi để nút không bị treo
    if query.data and query.data.startswith("info_"):
        username = query.data.replace("info_", "")
        # Gọi lại hàm tra cứu, truyền vào `update` để có thể trả lời tin nhắn mới
        await handle_lookup(update, context, username)

async def handle_lookup(update_or_query, context: ContextTypes.DEFAULT_TYPE, username: str):
    """
    Hàm tra cứu thông tin chính, được trang bị khả năng xử lý lỗi toàn diện.
    """
    # Xác định đối tượng tin nhắn để tương tác (trả lời, chỉnh sửa)
    if hasattr(update_or_query, 'message') and update_or_query.message:
        reply_obj = update_or_query.message
        # Gửi tin nhắn chờ và giữ lại để có thể chỉnh sửa nếu có lỗi
        status_msg = await reply_obj.reply_text("⏳ Đang tra cứu, vui lòng chờ...")
    elif hasattr(update_or_query, 'callback_query') and update_or_query.callback_query:
        reply_obj = update_or_query.callback_query.message
        # Khi nhấn nút, gửi một tin nhắn chờ mới thay vì sửa tin nhắn cũ
        status_msg = await reply_obj.chat.send_message("⏳ Đang tra cứu lại, vui lòng chờ...")
    else:
        # Trường hợp không xác định được đối tượng tin nhắn
        print("[ERROR] Không thể xác định đối tượng tin nhắn để trả lời.", file=sys.stderr)
        return

    # Tạo URL API
    api_url = API_URL_TIKTOK.format(username=username)
    print(f"[INFO] Bắt đầu tra cứu cho user '{username}' tại URL: {api_url}", file=sys.stderr)

    try:
        # Thiết lập timeout toàn diện cho request là 15 giây
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(api_url) as response:
                # Kiểm tra xem API có trả về thành công không
                if response.status == 200:
                    data = await response.json()
                    
                    # Kiểm tra xem dữ liệu có hợp lệ không
                    if data and (data.get("success") or data.get("status") == "success"):
                        # Xóa tin nhắn chờ và gửi kết quả
                        await status_msg.delete()
                        await send_profile_info(reply_obj, data, username)
                    else:
                        # API trả về success=false hoặc thông báo lỗi
                        error_message = data.get('message', 'Không tìm thấy người dùng hoặc API gặp lỗi.')
                        await status_msg.edit_text(f"⚠️ Lỗi: {error_message}")
                else:
                    # Lỗi HTTP từ server API (ví dụ: 500, 404, 403)
                    await status_msg.edit_text(f"⚠️ Lỗi: Server API TikTok gặp sự cố (mã lỗi {response.status}). Vui lòng thử lại sau.")

    except asyncio.TimeoutError:
        # Lỗi khi request mất quá nhiều thời gian
        print(f"[ERROR] Request tới API bị timeout cho user '{username}'.", file=sys.stderr)
        await status_msg.edit_text("⚠️ Lỗi: Yêu cầu tới server API mất quá nhiều thời gian để phản hồi. Vui lòng thử lại sau.")
    except aiohttp.ClientError as e:
        # Các lỗi khác liên quan đến network từ aiohttp
        print(f"[ERROR] Lỗi network aiohttp khi tra cứu '{username}': {e}", file=sys.stderr)
        await status_msg.edit_text("⚠️ Lỗi: Không thể kết nối đến server API. Vui lòng kiểm tra lại sau.")
    except Exception as e:
        # Bắt tất cả các lỗi không lường trước khác
        print(f"[CRITICAL] Lỗi không xác định khi tra cứu '{username}': {e}", file=sys.stderr)
        await status_msg.edit_text("⚠️ Lỗi: Đã có lỗi không mong muốn xảy ra trong quá trình xử lý.")

async def send_profile_info(reply_obj, data: dict, username: str):
    """Hàm tách riêng để gửi tin nhắn chứa thông tin profile."""
    tiktok_url = f"https://www.tiktok.com/@{data.get('username', username)}"
    keyboard = [
        [InlineKeyboardButton("🔗 Xem profile TikTok", url=tiktok_url)],
        [InlineKeyboardButton("🔄 Tra cứu lại", callback_data=f"info_{data.get('username', username)}")]
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
    if avatar:
        await reply_obj.reply_photo(photo=avatar, caption=msg, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await reply_obj.reply_text(msg, parse_mode='HTML', reply_markup=reply_markup)

# --- PHẦN SERVER VÀ WEBHOOK CHO RENDER ---
server = Flask(__name__)
application = Application.builder().token(BOT_TOKEN).build()

# Thêm các handler
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("info", info))
application.add_handler(CallbackQueryHandler(button_callback))

@server.route("/")
def index():
    """Route để cron-job.org gọi vào, giúp bot không bị 'ngủ đông'."""
    return "Bot is live and running!", 200

@server.route("/webhook", methods=["POST"])
async def webhook():
    """Route chính nhận update từ Telegram."""
    try:
        await application.update_queue.put(Update.de_json(request.get_json(force=True), application.bot))
    except Exception as e:
        print(f"[ERROR] Lỗi khi xử lý webhook: {e}", file=sys.stderr)
    return "OK", 200

async def setup_bot():
    """Hàm chạy một lần khi server khởi động để set webhook."""
    webhook_url = os.environ.get("RENDER_EXTERNAL_URL")
    if webhook_url:
        await application.bot.set_webhook(url=f"{webhook_url}/webhook")
        print(f"Webhook đã được set tới {webhook_url}/webhook", file=sys.stderr)
    else:
        print("Không tìm thấy RENDER_EXTERNAL_URL, bỏ qua set webhook.", file=sys.stderr)

# Khởi chạy bot và server
if __name__ == '__main__':
    # Chạy hàm setup một lần khi ứng dụng khởi động
    loop = asyncio.get_event_loop()
    loop.run_until_complete(setup_bot())
    
    # Gunicorn sẽ chạy biến `server` này
    # Dòng server.run() chỉ để test trên máy cá nhân, không cần thiết khi deploy
    # server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 8080)))