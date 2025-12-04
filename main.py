import os
import telebot
import google.generativeai as genai
from flask import Flask
from dotenv import load_dotenv
import threading
from gtts import gTTS
import requests  # Photo ke liye zaroori hai

# --- 1. SETUP & CONFIGURATION ---
load_dotenv()

# Keys uthana (Koyeb settings ya .env se)
API_KEY = os.getenv("GOOGLE_API_KEY") 
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Agar keys nahi mili to error
if not API_KEY or not BOT_TOKEN:
    print("Error: Keys missing hain! Koyeb Settings check karein.")

# Google Gemini AI Setup (Model upgraded to Flash for speed)
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Telegram Bot Setup
bot = telebot.TeleBot(BOT_TOKEN)

# Flask Server (Bot ko zinda rakhne ke liye)
app = Flask(__name__)

@app.route('/')
def home():
    return "Raj Dev Bot is Online!", 200

# --- 2. IMAGE GENERATION FEATURE (/img) ---
@bot.message_handler(commands=['img', 'photo'])
def send_ai_image(message):
    # Prompt nikalna (e.g., "/img cat" -> "cat")
    prompt = message.text.replace("/img", "").replace("/photo", "").strip()
    
    if not prompt:
        bot.reply_to(message, "Kuch likho to sahi! Example:\n`/img indian spiderman`")
        return

    try:
        bot.send_chat_action(message.chat.id, 'upload_photo')
        bot.reply_to(message, "🎨 Photo bana raha hoon, wait karo...")
        
        # Free AI Image Logic
        image_url = f"https://image.pollinations.ai/prompt/{prompt}"
        
        # Image bhejna
        bot.send_photo(message.chat.id, image_url, caption=f"🖼 Generated: {prompt}")
        
    except Exception as e:
        print(f"Image Error: {e}")
        bot.reply_to(message, "Photo banane mein error aaya.")

# --- 3. VOICE COMMAND (/raj) ---
@bot.message_handler(commands=['raj'])
def send_voice_greeting(message):
    try:
        bot.send_chat_action(message.chat.id, 'record_audio')
        text_to_speak = "Namaste! Main Raj Dev hoon. Bataiye kya seva karun?"
        
        tts = gTTS(text=text_to_speak, lang='hi')
        file_name = "voice_reply.mp3"
        tts.save(file_name)
        
        with open(file_name, "rb") as audio:
            bot.send_voice(message.chat.id, audio)
        
        os.remove(file_name) # Cleanup
    except Exception as e:
        print(f"Voice Error: {e}")

# --- 4. START & HELP ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "🙏 **Namaste! Main Raj Dev Bot hoon.**\n\n"
        "🎨 **Photo:** `/img cat in space`\n"
        "🎤 **Voice:** `/raj`\n"
        "❓ **Help:** `/help`"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = (
        "**Main kya kar sakta hoon?**\n"
        "1. Photo bana sakta hoon: `/img [kuch bhi likho]`\n"
        "2. Personal sawaal (Pin code, Address, etc.)\n"
        "3. Google AI se koi bhi jawaab."
    )
    bot.reply_to(message, help_text, parse_mode="Markdown")

# --- 5. CUSTOM LOGIC (Fixed Answers) ---
def get_custom_reply(text):
    text = text.lower().strip()
    if "tumhara naam" in text or "your name" in text:
        return "Mera naam Raj Dev hai."
    elif "kahan se ho" in text or "from" in text:
        return "Main Lumding se hoon."
    elif "pin code" in text:
        return "Lumding ka pin code 782447 hai."
    elif "address" in text or "kahan rahte" in text:
        return "Main Dakshin Lumding SK Paultila mein rehta hoon."
    elif "who made you" in text:
        return "Mujhe Rajdev ne banaya hai."
    return None

# --- 6. MAIN MESSAGE HANDLER ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        user_text = message.text
        print(f"User: {user_text}")

        # Check Custom Reply first
        custom_reply = get_custom_reply(user_text)
        
        if custom_reply:
            bot.reply_to(message, custom_reply)
        else:
            # Gemini AI Reply
            chat = model.start_chat(history=[])
            response = chat.send_message(user_text)
            bot.reply_to(message, response.text.replace("*", ""), parse_mode=None)

    except Exception as e:
        print(f"Error: {e}")
        bot.reply_to(message, "Technical error, dobara try karein.")

# --- 7. SERVER START ---
def run_bot():
    bot.infinity_polling()

if __name__ == "__main__":
    t = threading.Thread(target=run_bot)
    t.start()
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
    
