import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import yt_dlp
import os
import threading


# Replace with your actual bot token
TOKEN = "YOUR_BOT_TOKEN_HERE"
bot = telebot.TeleBot(TOKEN)

# Replace with the actual path to your FFMPEG executable
FFMPEG_PATH = "YOUR_FFMPEG_PATH_HERE"

CHANNELS = [
    # Replace with actual channel ID, name, and link
    ("-100xxxxxxxxx", "YOUR_CHANNEL_NAME_1", "YOUR_CHANNEL_LINK_1"),
    ("-100xxxxxxxxx", "YOUR_CHANNEL_NAME_2", "YOUR_CHANNEL_LINK_2"),
]


genders = ["♂️ Male", "♀️ Female"]
sexual_orientations = ["💑 Straight", "🏳️‍🌈 Gay", "💜 Bisexual"]

video_requests = {}

conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    status TEXT,
    gender TEXT,
    orientation TEXT
)
""")
conn.commit()

def get_user(user_id):
    cursor.execute("SELECT status, gender, orientation FROM users WHERE user_id=?", (user_id,))
    return cursor.fetchone()

def set_user(user_id, status=None, gender=None, orientation=None):
    if get_user(user_id) is None:
        cursor.execute("INSERT INTO users (user_id, status, gender, orientation) VALUES (?, ?, ?, ?)",
                       (user_id, status, gender, orientation))
    else:
        if status:
            cursor.execute("UPDATE users SET status=? WHERE user_id=?", (status, user_id))
        if gender:
            cursor.execute("UPDATE users SET gender=? WHERE user_id=?", (gender, user_id))
        if orientation:
            cursor.execute("UPDATE users SET orientation=? WHERE user_id=?", (orientation, user_id))
    conn.commit()

def check_user_membership(user_id):
    not_joined = []
    for channel_id, name, link in CHANNELS:
        try:
            chat_member = bot.get_chat_member(channel_id, user_id)
            if chat_member.status not in ["member", "administrator", "creator"]:
                not_joined.append((name, link))
        except:
            pass
    return not_joined

def send_join_message(user_id, not_joined):
    markup = telebot.types.InlineKeyboardMarkup()
    message_text = "🚨 To use the bot, you must join the following channels:\n\n"
    for name, link in not_joined:
        message_text += f"🔹 {name}\n"
        btn = telebot.types.InlineKeyboardButton(name, url=link)
        markup.add(btn)
    message_text += "\n✅ After joining, press /start again."
    bot.send_message(user_id, message_text, reply_markup=markup)

def ask_gender(user_id):
    markup = telebot.types.InlineKeyboardMarkup()
    for gender in genders:
        markup.add(telebot.types.InlineKeyboardButton(gender, callback_data=f"gender_{gender}"))
    bot.send_message(user_id, "💬 What is your gender?", reply_markup=markup)

def ask_orientation(user_id, message_id):
    bot.delete_message(user_id, message_id)
    markup = telebot.types.InlineKeyboardMarkup()
    for orientation in sexual_orientations:
        markup.add(telebot.types.InlineKeyboardButton(orientation, callback_data=f"orientation_{orientation}"))
    msg = bot.send_message(user_id, "🌈 What is your sexual orientation?", reply_markup=markup)
    return msg.message_id

main_menu_markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
btn_find_video = KeyboardButton("🔍 Find Video")
btn_download_video = KeyboardButton("💾 Download Video")
main_menu_markup.add(btn_find_video, btn_download_video)

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    user = get_user(user_id)

    if user and user[0] == "verified":
        not_joined = check_user_membership(user_id)
        if not_joined:
            send_join_message(user_id, not_joined)
        elif not user[1]:
            ask_gender(user_id)
        elif not user[2]:
            ask_orientation(user_id, message.message_id)
        else:
            bot.send_message(user_id, "✅ Welcome back! You can use the bot.", reply_markup=main_menu_markup)
    elif user and user[0] == "underage":
        bot.send_message(user_id, "🚫 You are under 18! If this is incorrect, use /age to update your status.")
    else:
        markup = telebot.types.InlineKeyboardMarkup()
        markup.row(
            telebot.types.InlineKeyboardButton("✅ I confirm I am 18+", callback_data="verify"),
            telebot.types.InlineKeyboardButton("❌ No, I am under 18", callback_data="underage")
        )
        bot.send_message(user_id, "🔞 You must be 18+ to use this bot. Please confirm:", reply_markup=markup)

@bot.message_handler(commands=['age'])
def update_age(message):
    user_id = message.chat.id
    markup = telebot.types.InlineKeyboardMarkup()
    btn_yes = telebot.types.InlineKeyboardButton("✅ I confirm I am 18+", callback_data="verify")
    btn_no = telebot.types.InlineKeyboardButton("❌ No, I am under 18", callback_data="underage")
    markup.add(btn_yes, btn_no)
    bot.send_message(user_id, "🔄 Update your age confirmation:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("verify"))
def verify_callback(call):
    user_id = call.message.chat.id
    set_user(user_id, status="verified")
    bot.delete_message(user_id, call.message.message_id)
    not_joined = check_user_membership(user_id)
    if not_joined:
        send_join_message(user_id, not_joined)
    else:
        ask_gender(user_id)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("underage"))
def underage_callback(call):
    user_id = call.message.chat.id
    set_user(user_id, status="underage")
    bot.delete_message(user_id, call.message.message_id)
    bot.send_message(user_id, "🚫 You are under 18! If this is incorrect, use /age to update your status.")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("gender_"))
def gender_callback(call):
    user_id = call.message.chat.id
    gender = call.data.split("_")[1]
    set_user(user_id, gender=gender)
    msg_id = ask_orientation(user_id, call.message.message_id)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("orientation_"))
def orientation_callback(call):
    user_id = call.message.chat.id
    orientation = call.data.split("_")[1]
    set_user(user_id, orientation=orientation)
    bot.delete_message(user_id, call.message.message_id)
    bot.send_message(user_id, "✅ Your information has been saved!\n💡 You can update it anytime with /user", reply_markup=main_menu_markup)
    bot.answer_callback_query(call.id)


@bot.message_handler(commands=['user'])
def update_user_info(message):
    user_id = message.chat.id
    ask_gender(user_id)

def is_verified(user_id):
    cursor.execute("SELECT status FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    return result and result[0] == "verified"


@bot.message_handler(func=lambda message: message.text == "💾 Download Video")
def request_video_link(message):
    if not is_verified(message.chat.id):
        bot.send_message(message.chat.id, "🚫 You must verify your age to use this feature!")
        return
    bot.send_message(message.chat.id,
                     "🔗 Please send the Pornhub video link in this format:\nhttps://www.pornhub.com/view_video.php?viewkey=xxx")


@bot.message_handler(func=lambda message: "pornhub.com/view_video.php?viewkey=" in message.text)
def process_video_link(message):
    if not is_verified(message.chat.id):
        bot.send_message(message.chat.id, "🚫 You must verify your age to use this feature!")
        return

    url = message.text.strip()
    user_id = message.chat.id
    loading_msg = bot.send_message(user_id, "⏳ Fetching video details, please wait...")
    thread = threading.Thread(target=fetch_video_details, args=(user_id, url, loading_msg.message_id))
    thread.start()


def fetch_video_details(user_id, url, loading_msg_id):
    ydl_opts = {
        'quiet': True,
        'noplaylist': True,
        'skip_download': True,
        'ffmpeg_location': FFMPEG_PATH
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Unknown Title')
            views = info.get('view_count', 0)
            likes = info.get('like_count', 0)
            uploader = info.get('uploader', 'Unknown')
            duration = info.get('duration', 0)
            thumbnail = info.get('thumbnail', '')
            available_formats = sorted(set([fmt.get('height') for fmt in info.get('formats', []) if fmt.get('height')]),
                                       reverse=True)

            minutes, seconds = divmod(duration, 60)
            duration_text = f"{minutes}:{seconds:02d}"
            caption = f"<b>{title}</b>\n⏳ Duration: {duration_text}\n👀 Views: {views}\n👍 Likes: {likes}\n🎥 Uploader: {uploader}"

            bot.delete_message(user_id, loading_msg_id)
            video_requests[user_id] = url

            markup = InlineKeyboardMarkup()
            for q in available_formats:
                markup.add(InlineKeyboardButton(f"{q}p", callback_data=f"quality_{q}"))

            msg = bot.send_photo(user_id, thumbnail, caption=caption, reply_markup=markup, parse_mode='HTML')
            video_requests[f"msg_{user_id}"] = msg.message_id
        except Exception as e:
            bot.send_message(user_id, f"❌ Error fetching video details: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("quality_"))
def download_video(call):
    quality = call.data.split("_")[1]
    user_id = call.message.chat.id
    url = video_requests.get(user_id)

    if not url:
        bot.send_message(user_id, "❌ No video request found.")
        return

    bot.delete_message(user_id, video_requests.get(f"msg_{user_id}"))
    downloading_msg = bot.send_message(user_id, f"⏳ Downloading video in {quality}p...")
    thread = threading.Thread(target=process_download, args=(user_id, url, quality, downloading_msg.message_id))
    thread.start()


def process_download(user_id, url, quality, downloading_msg_id):
    ydl_opts = {
        'format': f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]',
        'outtmpl': f'video_{user_id}.mp4',
        'quiet': True,
        'retries': 3,
        'ffmpeg_location': FFMPEG_PATH
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            video_path = f'video_{user_id}.mp4'
            duration = info.get('duration', 0)

            bot.delete_message(user_id, downloading_msg_id)

            with open(video_path, 'rb') as video_file:
                sent_message = bot.send_video(user_id, video=video_file, duration=duration)

            bot.send_message(user_id, "⚠️ Save the video in your saved messages. It will be deleted in 30 seconds.")

            threading.Thread(target=delete_video_later, args=(user_id, video_path, sent_message.message_id)).start()

        except Exception as e:
            bot.send_message(user_id, f"❌ Error downloading video: {str(e)}")

def delete_video_later(user_id, video_path, message_id):
    import time
    time.sleep(30)
    try:
        os.remove(video_path)
        bot.delete_message(user_id, message_id)
    except Exception as e:
        print(f"Error deleting file/message: {str(e)}")


@bot.message_handler(func=lambda message: message.text == "🔍 Find Video")
def find_video_response(message):
    response_text = "🍑 This feature will be available soon! 🔥 Based on your preferences, we'll recommend the hottest videos for you. 🔞 Stay tuned! 😉"
    bot.reply_to(message, response_text)


bot.set_my_commands([
    telebot.types.BotCommand("start", "Start the bot"),
    telebot.types.BotCommand("age", "Update your age confirmation"),
    telebot.types.BotCommand("user", "Update your gender and orientation")
])



bot.polling()
