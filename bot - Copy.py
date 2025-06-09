import requests
import json
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

API_URL = "https://ahihi.x10.mx/fltik.php?user={username}&key=khang"
WATCHED_USERS = ["khangdino206"]  # Danh sách username cần theo dõi, bạn có thể thêm vào đây
WATCHED_DATA_FILE = "watched_data.json"
NOTIFY_CHAT_ID = None  # Thay bằng chat_id Telegram bạn muốn nhận thông báo, hoặc cập nhật khi bot nhận lệnh /start
session = requests.Session()  # Tái sử dụng kết nối HTTP

# Hàm gửi thông tin đẹp với Markdown, ảnh đại diện, nút bấm
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                else:
                    await update.message.reply_text("Không lấy được thông tin từ API.")
            else:
                await update.message.reply_text("Lỗi kết nối API.")
        except Exception as e:
            await update.message.reply_text("Lỗi khi truy vấn API hoặc API quá chậm.")
    else:
        await update.message.reply_text("Vui lòng nhập username. Ví dụ: /info khangdino206")

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
                    watched_data[username] = {
                        "followers_count": data["followers_count"],
                        "bio": data["bio"]
                    }
        except Exception as e:
            pass
    save_watched_data(watched_data)

# Lệnh /start để lưu chat_id nhận thông báo
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global NOTIFY_CHAT_ID
    NOTIFY_CHAT_ID = update.effective_chat.id
    await update.message.reply_text("Bot đã sẵn sàng gửi thông báo tự động!")

if __name__ == '__main__':
    # Thay YOUR_BOT_TOKEN bằng token bot Telegram của bạn
    app = ApplicationBuilder().token("7805035127:AAEJ84rasINPm4e1erLHle9ErB0szwO19vY").base_url("https://proxy.accpreytb4month.workers.dev/bot").build()
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("start", start))
    # Đăng ký job định kỳ mỗi 5 phút
    app.job_queue.run_repeating(check_and_notify, interval=300, first=10)
    app.run_polling() 