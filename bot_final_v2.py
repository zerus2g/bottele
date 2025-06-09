# bot_final_v2.py

import sys
import os
import asyncio
import aiohttp
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

# ==============================================================================
# --- 1. PHẦN CẤU HÌNH (CONFIG) ---
# ==============================================================================
# Lấy các giá trị từ Biến Môi Trường (Environment Variables) của Render.
# Việc này giúp tăng tính bảo mật và linh hoạt khi thay đổi.

# Token của bot Telegram (BẮT BUỘC)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    print("LỖI NGHIÊM TRỌNG: Biến môi trường BOT_TOKEN chưa được thiết lập.", file=sys.stderr)
    sys.exit(1)

# API Key cho dịch vụ tra cứu TikTok (Tùy chọn)
TIKTOK_API_KEY = os.environ.get("TIKTOK_API_KEY", "khang") # Dùng 'khang' làm giá trị mặc định nếu không set

# Template URL cho API, giúp dễ dàng thay đổi sau này
API_URL_TEMPLATE = f"https://ahihi.x10.mx/fltik.php?user={{username}}&key={TIKTOK_API_KEY}"

# Port mà Render yêu cầu ứng dụng phải lắng nghe
PORT = int(os.environ.get("PORT", 8080))


# ==============================================================================
# --- 2. KHỞI TẠO ỨNG DỤNG BOT VÀ FLASK SERVER ---
# ==============================================================================
# Khởi tạo Application của bot, đây là đối tượng chính của thư viện python-telegram-bot
application = Application.builder().token(BOT_TOKEN).build()
# Khởi tạo Flask Server để xử lý các yêu cầu HTTP
server = Flask(__name__)


# ==============================================================================
# --- 3. LOGIC CỐT LÕI CỦA BOT (BOT HANDLERS & CORE FUNCTIONS) ---
# ==============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gửi tin nhắn chào mừng khi người dùng gõ lệnh /start."""
    await update.message.reply_text(
        "Chào mừng bạn đến với Bot Tra Cứu TikTok!\n\n"
        "Gõ <b>/info &lt;username&gt;</b> để bắt đầu tra cứu.",
        parse_mode='HTML'
    )

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý lệnh /info <username> từ người dùng."""
    if context.args:
        username = context.args[0]
        await handle_lookup(update, context, username)
    else:
        await update.message.reply_text(
            "Cú pháp của bạn chưa đúng.\n\n"
            "Vui lòng nhập theo mẫu: <b>/info &lt;username&gt;</b>",
            parse_mode='HTML'
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý khi người dùng nhấn các nút bấm (inline keyboard)."""
    query = update.callback_query
    await query.answer()  # Phản hồi ngay để nút không bị treo

    if query.data and query.data.startswith("info_"):
        username = query.data.replace("info_", "")
        await handle_lookup(update, context, username)

async def handle_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE, username: str) -> None:
    """
    Hàm tra cứu thông tin chính.
    Gửi tin nhắn chờ, gọi API, xử lý kết quả và các lỗi có thể xảy ra.
    """
    if hasattr(update, 'message') and update.message:
        reply_obj = update.message
        status_msg = await reply_obj.reply_text("⏳ Đang tra cứu, vui lòng chờ một lát...")
    elif hasattr(update, 'callback_query') and update.callback_query:
        reply_obj = update.callback_query.message
        status_msg = await reply_obj.chat.send_message("⏳ Đang tra cứu lại, vui lòng chờ...")
    else:
        print("[ERROR] Không thể xác định đối tượng tin nhắn để trả lời.", file=sys.stderr)
        return

    api_url = API_URL_TEMPLATE.format(username=username)
    print(f"[INFO] Bắt đầu tra cứu cho user '{username}'", file=sys.stderr)

    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(api_url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and (data.get("success") or data.get("status") == "success"):
                        await status_msg.delete()
                        await send_profile_info(reply_obj, data, username)
                    else:
                        error_message = data.get('message', 'Không tìm thấy người dùng hoặc API gặp lỗi.')
                        await status_msg.edit_text(f"⚠️ **Lỗi:** {error_message}")
                else:
                    await status_msg.edit_text(f"⚠️ **Lỗi:** Server API tra cứu gặp sự cố (mã lỗi: {response.status}). Vui lòng thử lại sau.")
    except asyncio.TimeoutError:
        print(f"[ERROR] Request tới API bị timeout cho user '{username}'.", file=sys.stderr)
        await status_msg.edit_text("⚠️ **Lỗi:** Yêu cầu tới server API mất quá nhiều thời gian để phản hồi.")
    except Exception as e:
        print(f"[CRITICAL] Lỗi không xác định khi tra cứu '{username}': {e}", file=sys.stderr)
        await status_msg.edit_text("⚠️ **Lỗi:** Đã có lỗi không mong muốn xảy ra trong quá trình xử lý.")

async def send_profile_info(reply_obj, data: dict, username: str) -> None:
    """Hàm tách riêng để định dạng và gửi tin nhắn chứa thông tin profile."""
    actual_username = data.get('username', username)
    tiktok_url = f"https://www.tiktok.com/@{actual_username}"
    keyboard = [[InlineKeyboardButton("🔗 Xem Profile TikTok", url=tiktok_url)], [InlineKeyboardButton("🔄 Tra Cứu Lại", callback_data=f"info_{actual_username}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    followers = data.get('followers_count', data.get('followers', 0))
    following = data.get('following_count', 0)
    
    msg = (f"👤 <b>Username:</b> {data.get('username', 'N/A')}\n"
           f"🏷️ <b>Nickname:</b> {data.get('nickname', 'N/A')}\n"
           f"🌍 <b>Region:</b> {data.get('region', 'N/A')}\n"
           f"👥 <b>Followers:</b> {int(followers):,}\n"
           f"➡️ <b>Following:</b> {int(following):,}\n"
           f"📝 <b>Bio:</b> {data.get('bio', '(trống)')}\n"
           f"🔒 <b>Private Account:</b> {'Riêng tư' if data.get('privateAccount', False) else 'Công khai'}")
    
    avatar = data.get('profilePic', data.get('profile_pic', ''))
    if avatar:
        await reply_obj.chat.send_photo(photo=avatar, caption=msg, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await reply_obj.chat.send_message(text=msg, parse_mode='HTML', reply_markup=reply_markup)


# ==============================================================================
# --- 4. LOGIC CỦA FLASK SERVER (WEB SERVER ROUTING) ---
# ==============================================================================

@server.route("/")
def health_check():
    """
    Route cho cron-job.org ping vào bằng phương thức GET.
    Chỉ cần trả về mã 200 OK là Render biết service vẫn "sống".
    """
    return "Bot is alive and ready to receive updates!", 200

@server.route(f"/{BOT_TOKEN}", methods=["POST"])
async def webhook_handler():
    """
    Route để nhận update từ Telegram bằng phương thức POST.
    Sử dụng token trong URL làm một lớp bảo mật đơn giản để tránh các request lạ.
    """
    update_data = request.get_json()
    update = Update.de_json(update_data, application.bot)
    await application.process_update(update)
    return "OK", 200


# ==============================================================================
# --- 5. PHẦN KHỞI CHẠY (ENTRY POINT & SETUP) ---
# ==============================================================================

async def setup_application():
    """
    Hàm này được chạy một lần khi Gunicorn khởi động server.
    Nó thực hiện 3 việc quan trọng:
    1. Đăng ký các handler (bộ xử lý lệnh) cho bot.
    2. Khởi tạo và sẵn sàng ứng dụng bot (sửa lỗi 'not initialized').
    3. Thiết lập webhook để Telegram biết nơi gửi tin nhắn đến.
    """
    print("Bắt đầu quá trình thiết lập ứng dụng bot...", file=sys.stderr)
    
    await application.initialize()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("info", info))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    webhook_url = os.environ.get("RENDER_EXTERNAL_URL")
    if webhook_url:
        full_webhook_url = f"{webhook_url}/{BOT_TOKEN}"
        await application.bot.set_webhook(url=full_webhook_url, allowed_updates=Update.ALL_TYPES)
        print(f"Webhook đã được thiết lập tới URL: {full_webhook_url}", file=sys.stderr)
    else:
        print("Không tìm thấy RENDER_EXTERNAL_URL, bỏ qua bước tự động set webhook.", file=sys.stderr)
    
    print("Thiết lập ứng dụng bot hoàn tất.", file=sys.stderr)

# `if __name__ != '__main__':` đảm bảo khối lệnh này được Gunicorn thực thi khi khởi động.
if __name__ != '__main__':
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.create_task(setup_application())
    else:
        loop.run_until_complete(setup_application())

# Biến `server` sẽ được Gunicorn tìm đến và chạy.
# Lệnh `server.run()` chỉ dùng khi bạn test trên máy cá nhân.
if __name__ == '__main__':
    print("Để chạy bot này, hãy dùng một server WSGI như Gunicorn. Ví dụ: gunicorn bot_final_v2:server")