# bot_final.py

import sys
import os
import asyncio
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

# ==============================================================================
# --- PHẦN CẤU HÌNH (CONFIG) ---
# ==============================================================================
# Lấy các giá trị từ Biến Môi Trường (Environment Variables) của Render.
# Việc này giúp tăng tính bảo mật và linh hoạt khi thay đổi.

# Token của bot Telegram
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    print("LỖI NGHIÊM TRỌNG: Biến môi trường BOT_TOKEN chưa được thiết lập.", file=sys.stderr)
    sys.exit(1)

# API Key cho dịch vụ tra cứu TikTok
TIKTOK_API_KEY = os.environ.get("TIKTOK_API_KEY", "khang") # Dùng 'khang' làm giá trị mặc định nếu không set

# Template URL cho API, giúp dễ dàng thay đổi sau này
API_URL_TEMPLATE = f"https://ahihi.x10.mx/fltik.php?user={{username}}&key={TIKTOK_API_KEY}"

# Port mà Render yêu cầu ứng dụng phải lắng nghe
PORT = int(os.environ.get("PORT", 8080))


# ==============================================================================
# --- CÁC HÀM XỬ LÝ LỆNH (HANDLERS) ---
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
        # Gọi lại hàm tra cứu, truyền `update` để có thể gửi tin nhắn mới
        await handle_lookup(update, context, username)


# ==============================================================================
# --- LOGIC XỬ LÝ CỐT LÕI (CORE LOGIC) ---
# ==============================================================================

async def handle_lookup(update_or_query: Update, context: ContextTypes.DEFAULT_TYPE, username: str) -> None:
    """
    Hàm tra cứu thông tin chính.
    Gửi tin nhắn chờ, gọi API, xử lý kết quả và các lỗi có thể xảy ra.
    """
    # Xác định đối tượng tin nhắn để tương tác (trả lời, chỉnh sửa)
    if hasattr(update_or_query, 'message') and update_or_query.message:
        reply_obj = update_or_query.message
        status_msg = await reply_obj.reply_text("⏳ Đang tra cứu, vui lòng chờ một lát...")
    elif hasattr(update_or_query, 'callback_query') and update_or_query.callback_query:
        reply_obj = update_or_query.callback_query.message
        status_msg = await reply_obj.chat.send_message("⏳ Đang tra cứu lại, vui lòng chờ...")
    else:
        print("[ERROR] Không thể xác định đối tượng tin nhắn để trả lời.", file=sys.stderr)
        return

    api_url = API_URL_TEMPLATE.format(username=username)
    print(f"[INFO] Bắt đầu tra cứu cho user '{username}'", file=sys.stderr)

    try:
        # Thiết lập timeout toàn diện cho request là 15 giây để tránh bị treo
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(api_url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and (data.get("success") or data.get("status") == "success"):
                        await status_msg.delete()  # Xóa tin nhắn chờ
                        await send_profile_info(reply_obj, data, username)
                    else:
                        error_message = data.get('message', 'Không tìm thấy người dùng hoặc API gặp lỗi.')
                        await status_msg.edit_text(f"⚠️ **Lỗi:** {error_message}")
                else:
                    await status_msg.edit_text(f"⚠️ **Lỗi:** Server API tra cứu gặp sự cố (mã lỗi: {response.status}). Vui lòng thử lại sau.")

    except asyncio.TimeoutError:
        print(f"[ERROR] Request tới API bị timeout cho user '{username}'.", file=sys.stderr)
        await status_msg.edit_text("⚠️ **Lỗi:** Yêu cầu tới server API mất quá nhiều thời gian để phản hồi. Vui lòng thử lại sau.")
    except aiohttp.ClientError as e:
        print(f"[ERROR] Lỗi network aiohttp khi tra cứu '{username}': {e}", file=sys.stderr)
        await status_msg.edit_text("⚠️ **Lỗi:** Không thể kết nối đến server API. Vui lòng kiểm tra lại sau.")
    except Exception as e:
        print(f"[CRITICAL] Lỗi không xác định khi tra cứu '{username}': {e}", file=sys.stderr)
        await status_msg.edit_text("⚠️ **Lỗi:** Đã có lỗi không mong muốn xảy ra trong quá trình xử lý.")

async def send_profile_info(reply_obj, data: dict, username: str) -> None:
    """Hàm tách riêng để định dạng và gửi tin nhắn chứa thông tin profile."""
    # Lấy username từ dữ liệu trả về, nếu không có thì dùng username người dùng nhập vào
    actual_username = data.get('username', username)
    tiktok_url = f"https://www.tiktok.com/@{actual_username}"
    
    keyboard = [
        [InlineKeyboardButton("🔗 Xem Profile TikTok", url=tiktok_url)],
        [InlineKeyboardButton("🔄 Tra Cứu Lại", callback_data=f"info_{actual_username}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Định dạng các con số để dễ đọc hơn
    followers = data.get('followers_count', data.get('followers', 0))
    following = data.get('following_count', 0)
    
    msg = (
        f"👤 <b>Username:</b> {data.get('username', 'N/A')}\n"
        f"🏷️ <b>Nickname:</b> {data.get('nickname', 'N/A')}\n"
        f"🌍 <b>Region:</b> {data.get('region', 'N/A')}\n"
        f"👥 <b>Followers:</b> {int(followers):,}\n"
        f"➡️ <b>Following:</b> {int(following):,}\n"
        f"📝 <b>Bio:</b> {data.get('bio', '(trống)')}\n"
        f"🔒 <b>Private Account:</b> {'Riêng tư' if data.get('privateAccount', False) else 'Công khai'}"
    )
    
    avatar = data.get('profilePic', data.get('profile_pic', ''))
    if avatar:
        await reply_obj.reply_photo(photo=avatar, caption=msg, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await reply_obj.reply_text(msg, parse_mode='HTML', reply_markup=reply_markup)


# ==============================================================================
# --- PHẦN KHỞI CHẠY BOT (ENTRY POINT) ---
# ==============================================================================

def main() -> None:
    """Hàm main để thiết lập và khởi chạy bot."""
    application = Application.builder().token(BOT_TOKEN).build()

    # Đăng ký các handler cho bot
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("info", info))
    application.add_handler(CallbackQueryHandler(button_callback))

    # Lấy URL mà Render cung cấp cho web service qua biến môi trường
    webhook_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not webhook_url:
        print("LỖI: không tìm thấy biến môi trường RENDER_EXTERNAL_URL. Không thể chạy webhook.", file=sys.stderr)
        sys.exit(1)

    # Khởi chạy bot bằng webserver có sẵn của thư viện telegram-bot.
    # Phương thức này sẽ tự động làm 2 việc:
    # 1. Gọi API setWebhook của Telegram để chỉ cho Telegram biết URL của bot.
    # 2. Khởi động một webserver đơn giản để lắng nghe các yêu cầu từ Telegram.
    print(f"Bot sẽ lắng nghe trên 0.0.0.0:{PORT}", file=sys.stderr)
    print(f"Webhook sẽ được set tới URL: {webhook_url}", file=sys.stderr)
    
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="",  # Để trống để webhook là URL gốc, dễ cho cron-job ping
        webhook_url=webhook_url
    )

if __name__ == "__main__":
    main()