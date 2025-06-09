# bot_final_v3.py

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
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    print("LỖI NGHIÊM TRỌNG: Biến môi trường BOT_TOKEN chưa được thiết lập.", file=sys.stderr)
    sys.exit(1)

TIKTOK_API_KEY = os.environ.get("TIKTOK_API_KEY", "khang")
API_URL_TEMPLATE = f"https://ahihi.x10.mx/fltik.php?user={{username}}&key={TIKTOK_API_KEY}"
PORT = int(os.environ.get("PORT", 8080))

# ==============================================================================
# --- 2. KHỞI TẠO ỨNG DỤNG BOT VÀ FLASK SERVER ---
# ==============================================================================
application = Application.builder().token(BOT_TOKEN).build()
app = Flask(__name__)

# Khởi tạo event loop toàn cục và initialize bot khi app start
loop = asyncio.get_event_loop()
loop.run_until_complete(application.initialize())

# ==============================================================================
# --- 3. LOGIC CỐT LÕI CỦA BOT (BOT HANDLERS & CORE FUNCTIONS) ---
# ==============================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gửi tin nhắn chào mừng khi người dùng gõ lệnh /start."""
    await update.message.reply_text("Chào mừng bạn! Gõ <b>/info &lt;username&gt;</b> để tra cứu.", parse_mode='HTML')

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý lệnh /info <username> từ người dùng."""
    if context.args:
        await handle_lookup(update, context, context.args[0])
    else:
        await update.message.reply_text("Cú pháp sai. Mẫu: <b>/info &lt;username&gt;</b>", parse_mode='HTML')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý khi người dùng nhấn các nút bấm (inline keyboard)."""
    query = update.callback_query
    await query.answer()
    if query.data and query.data.startswith("info_"):
        await handle_lookup(update, context, query.data.replace("info_", ""))
    elif query.data and query.data.startswith("copy_"):
        username = query.data.replace("copy_", "")
        await query.message.reply_text(f"📋 Username: <code>{username}</code>\nBạn có thể copy username này!", parse_mode='HTML')

async def handle_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE, username: str) -> None:
    """Hàm tra cứu thông tin chính."""
    if hasattr(update, 'message') and update.message:
        reply_obj = update.message
        status_msg = await reply_obj.reply_text("⏳ Đang tra cứu...")
    elif hasattr(update, 'callback_query') and update.callback_query:
        reply_obj = update.callback_query.message
        status_msg = await reply_obj.chat.send_message("⏳ Đang tra cứu lại...")
    else: return

    api_url = API_URL_TEMPLATE.format(username=username)
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
                        try:
                            await status_msg.edit_text(f"⚠️ Lỗi: {data.get('message', 'Không tìm thấy user.')}")
                        except Exception as e:
                            print(f"[Edit Message Error] {e}", file=sys.stderr)
                            await reply_obj.chat.send_message(f"⚠️ Lỗi: {data.get('message', 'Không tìm thấy user.')}")
                else:
                    try:
                        await status_msg.edit_text(f"⚠️ Lỗi: API tra cứu gặp sự cố (mã {response.status}).")
                    except Exception as e:
                        print(f"[Edit Message Error] {e}", file=sys.stderr)
                        await reply_obj.chat.send_message(f"⚠️ Lỗi: API tra cứu gặp sự cố (mã {response.status}).")
    except asyncio.TimeoutError:
        try:
            await status_msg.edit_text("⚠️ Lỗi: API tra cứu mất quá nhiều thời gian phản hồi.")
        except Exception as e:
            print(f"[Edit Message Error] {e}", file=sys.stderr)
            await reply_obj.chat.send_message("⚠️ Lỗi: API tra cứu mất quá nhiều thời gian phản hồi.")
    except Exception as e:
        print(f"[CRITICAL] Lỗi không xác định: {e}", file=sys.stderr)
        try:
            await status_msg.edit_text("⚠️ Lỗi: Có sự cố không mong muốn xảy ra.")
        except Exception as e2:
            print(f"[Edit Message Error] {e2}", file=sys.stderr)
            await reply_obj.chat.send_message("⚠️ Lỗi: Có sự cố không mong muốn xảy ra.")

async def send_profile_info(reply_obj, data: dict, username: str) -> None:
    """Hàm tách riêng để định dạng và gửi tin nhắn chứa thông tin profile."""
    print(f"[DEBUG] Data nhận được từ API: {data}", file=sys.stderr)
    actual_username = data.get('username', username)
    tiktok_url = f"https://www.tiktok.com/@{actual_username}"
    keyboard = [
        [
            InlineKeyboardButton("🔗 Xem Profile TikTok", url=tiktok_url),
            InlineKeyboardButton("📋 Copy Username", callback_data=f"copy_{actual_username}")
        ],
        [
            InlineKeyboardButton("🔄 Tra Cứu Lại", callback_data=f"info_{actual_username}"),
            InlineKeyboardButton("📤 Chia sẻ Profile", switch_inline_query=tiktok_url)
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    followers_raw = data.get('followers_count', data.get('followers', 0))
    following_raw = data.get('following_count', 0)
    try:
        followers = int(str(followers_raw).replace(',', '').replace('.', ''))
    except Exception as e:
        print(f"[DEBUG] Lỗi chuyển followers_count: {e} | Giá trị: {followers_raw}", file=sys.stderr)
        followers = followers_raw
    try:
        following = int(str(following_raw).replace(',', '').replace('.', ''))
    except Exception as e:
        print(f"[DEBUG] Lỗi chuyển following_count: {e} | Giá trị: {following_raw}", file=sys.stderr)
        following = following_raw
    msg = (
        f"👤 <b>Username:</b> <code>{data.get('username', 'N/A')}</code>\n"
        f"🏷️ <b>Nickname:</b> <i>{data.get('nickname', 'N/A')}</i>\n"
        f"👥 <b>Followers:</b> <b>{followers}</b>\n"
        f"➡️ <b>Following:</b> <b>{following}</b>\n"
        f"🔗 <a href='{tiktok_url}'>Xem TikTok Profile</a>"
    )
    avatar = data.get('profilePic', data.get('profile_pic', ''))
    print(f"[DEBUG] Gửi thông tin profile cho user: {actual_username}", file=sys.stderr)
    if avatar:
        await reply_obj.chat.send_photo(photo=avatar, caption=msg, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await reply_obj.chat.send_message(text=msg, parse_mode='HTML', reply_markup=reply_markup)

# ==============================================================================
# --- 4. LOGIC CỦA FLASK SERVER (WEB SERVER ROUTING) ---
# ==============================================================================
@app.route("/")
def health_check():
    """Route cho cron-job.org ping vào."""
    return "Bot is alive and ready!", 200

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook_handler():
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        loop.run_until_complete(application.process_update(update))
    except Exception as e:
        print(f"[Webhook Error] {e}", file=sys.stderr)
    return "OK", 200

# ==============================================================================
# --- 5. PHẦN KHỞI CHẠY (ENTRY POINT & SETUP) ---
# ==============================================================================
def setup_application():
    """Hàm chạy một lần khi Gunicorn khởi động server để setup bot."""
    print("Bắt đầu quá trình thiết lập ứng dụng bot...", file=sys.stderr)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("info", info))
    application.add_handler(CallbackQueryHandler(button_callback))
    webhook_url = os.environ.get("RENDER_EXTERNAL_URL")
    if webhook_url:
        full_webhook_url = f"{webhook_url}/{BOT_TOKEN}"
        import requests
        set_webhook_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        requests.post(set_webhook_url, data={"url": full_webhook_url})
        print(f"Webhook đã được thiết lập tới URL: {full_webhook_url}", file=sys.stderr)
    else:
        print("Không tìm thấy RENDER_EXTERNAL_URL.", file=sys.stderr)
    print("Thiết lập ứng dụng bot hoàn tất.", file=sys.stderr)

# Khối lệnh này đảm bảo hàm setup được chạy đúng cách trong môi trường Gunicorn.
if __name__ != '__main__':
    setup_application()

# Lệnh `app.run()` chỉ dùng khi bạn test trên máy cá nhân.
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=PORT)
    print("Để chạy bot này, hãy dùng một server WSGI như Gunicorn. Ví dụ: gunicorn main:app")