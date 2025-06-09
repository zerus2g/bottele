import requests
import json
import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Thiết lập logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_URL = "https://ahihi.x10.mx/fltik.php?user={username}&key=khang"
WATCHED_USERS = ["khangdino206"]  # Danh sách username cần theo dõi, bạn có thể thêm vào đây
WATCHED_DATA_FILE = "watched_data.json"
NOTIFY_CHAT_ID = None  # Thay bằng chat_id Telegram bạn muốn nhận thông báo, hoặc cập nhật khi bot nhận lệnh /start
session = requests.Session()  # Tái sử dụng kết nối HTTP

# Hàm gửi thông tin đẹp với Markdown, ảnh đại diện, nút bấm
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Nhận lệnh /info từ user {update.effective_user.id} với args: {context.args}")
    if context.args:
        username = context.args[0]
        # Gửi thông báo ngay lập tức
        await update.message.reply_text("⏳ Đang tra cứu, vui lòng chờ...")
        url = API_URL.format(username=username)
        try:
            response = session.get(url, timeout=5)  # Giới hạn timeout
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

# Hàm lưu thông tin theo dõi vào file
def save_watched_data(data):
    with open(WATCHED_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_watched_data():
    if os.path.exists(WATCHED_DATA_FILE):
        with open(WATCHED_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# Hàm kiểm tra thay đổi và gửi thông báo (dùng cho job_queue)
async def check_and_notify(context):
    app = context.application
    watched_data = load_watched_data()
    for username in WATCHED_USERS:
        url = API_URL.format(username=username)
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    old = watched_data.get(username, {})
                    changed = []
                    if old:
                        if str(old.get("followers_count")) != str(data["followers_count"]):
                            changed.append(f"👥 Followers: {old.get('followers_count')} ➡️ {data['followers_count']}")
                        if old.get("bio") != data["bio"]:
                            changed.append(f"📝 Bio thay đổi!")
                    if changed:
                        msg = (
                            f"🔔 *Tài khoản* `{username}` *có thay đổi!*\n" + "\n".join(changed)
                        )
                        keyboard = [
                            [InlineKeyboardButton("Xem trên TikTok", url=f"https://www.tiktok.com/@{username}")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        chat_id = NOTIFY_CHAT_ID or list(app.bot._chat_data.keys())[0] if app.bot._chat_data else None
                        if chat_id:
                            await app.bot.send_photo(
                                chat_id=chat_id,
                                photo=data['profilePic'],
                                caption=msg,
                                parse_mode=ParseMode.MARKDOWN,
                                reply_markup=reply_markup
                            )
                            logger.info(f"Đã gửi thông báo thay đổi cho {username} tới chat_id {chat_id}")
                    watched_data[username] = {
                        "followers_count": data["followers_count"],
                        "bio": data["bio"]
                    }
        except Exception as e:
            logger.exception(f"Lỗi khi kiểm tra thay đổi cho username: {username}")
    save_watched_data(watched_data)

# Lệnh /start để lưu chat_id nhận thông báo
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global NOTIFY_CHAT_ID
    NOTIFY_CHAT_ID = update.effective_chat.id
    await update.message.reply_text("Bot đã sẵn sàng gửi thông báo tự động!")
    logger.info(f"Đã lưu chat_id nhận thông báo: {NOTIFY_CHAT_ID}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """*Các lệnh hỗ trợ:*
/help - Hiển thị hướng dẫn sử dụng và các lệnh
/info <username> - Tra cứu thông tin TikTok của username
/start - Đăng ký nhận thông báo tự động khi có thay đổi
Ví dụ: /info khangdino206
"""
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    logger.info(f"User {update.effective_user.id} đã dùng lệnh /help")

if __name__ == '__main__':
    # Lấy token từ biến môi trường
    TOKEN = os.environ.get("BOT_TOKEN")
    logger.info("Khởi động bot... Đang kết nối Telegram...")
    app = ApplicationBuilder().token(TOKEN).base_url("https://proxy.accpreytb4month.workers.dev/bot").build()
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    # Đăng ký job định kỳ mỗi 5 phút
    app.job_queue.run_repeating(check_and_notify, interval=300, first=10)
    logger.info("Bot đã khởi động và sẵn sàng hoạt động!")
    app.run_polling() 