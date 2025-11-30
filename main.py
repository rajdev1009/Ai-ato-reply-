import os
import telebot
import google.generativeai as genai
from flask import Flask
from dotenv import load_dotenv
import threading
import time
from gtts import gTTS
from telebot import apihelper

# --- 1. CONFIGURATION & SETUP ---
load_dotenv()

# Keys check
API_KEY = os.getenv("GOOGLE_API_KEY") 
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not API_KEY or not BOT_TOKEN:
    print("❌ Error: API Key ya Bot Token missing hai! Environment Variables check karein.")

# Google Gemini AI Setup
# NOTE: 'gemini-pro' model use kar rahe hain kyunki ye sabse stable hai
# Agar 'gemini-1.5-flash' error de raha hai, to ye best option hai.
try:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-pro')
except Exception as e:
    print(f"Model setup error: {e}")

# Telegram Bot Setup
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- 2. FLASK SERVER (Bot ko zinda rakhne ke liye) ---
@app.route('/')
def home():
    return "✅ Raj Dev Bot is Online & Running!", 200

# --- 3. BOT COMMANDS & LOGIC ---

# Voice Command (/raj)
@bot.message_handler(commands=['raj'])
def send_voice_greeting(message):
    try:
        bot.send_chat_action(message.chat.id, 'record_audio')
        text_to_speak = "Namaste! Main Raj Dev hoon. Main bolkar bhi jawab de sakta hoon."
        
        # Audio file banao
        tts = gTTS(text=text_to_speak, lang='hi')
        file_name = f"voice_{message.chat.id}.mp3"
        tts.save(file_name)
        
        # Audio bhejo
        with open(file_name, "rb") as audio:
            bot.send_voice(message.chat.id, audio)
            
        # File delete karo (cleanup)
        os.remove(file_name)
    except Exception as e:
        print(f"Voice Error: {e}")
        bot.reply_to(message, "Voice message bhejne mein dikkat aayi.")

# Start & Help Commands
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "🙏 Namaste! Main Raj Dev Bot hoon.\n\nMain Google AI se connect hoon. Mujhse kuch bhi puchiye!")

# Fixed Custom Replies
def get_custom_reply(text):
    text = text.lower().strip()
    if "tumhara naam" in text: return "Mera naam Raj Dev hai."
    if "kahan se ho" in text: return "Main Lumding se hoon."
    if "pin code" in text: return "Lumding ka pin code 782447 hai."
    if "who made you" in text: return "Mujhe Rajdev ne banaya hai."
    return None

# Main Message Handler (Text & AI)
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        print(f"User: {message.text}") # Log user text
        
        # 1. Custom Reply Check
        custom = get_custom_reply(message.text)
        if custom:
            bot.reply_to(message, custom)
            return

        # 2. Google AI Reply
        try:
            # History blank rakhi hai taaki simple sawal jawab ho sake
            chat = model.start_chat(history=[])
            response = chat.send_message(message.text)
            
            if response and response.text:
                bot.reply_to(message, response.text, parse_mode="Markdown")
            else:
                bot.reply_to(message, "AI ne koi jawab nahi diya.")
                
        except Exception as ai_error:
            print(f"AI Error: {ai_error}")
            bot.reply_to(message, "Maaf kijiye, abhi main connect nahi kar pa raha hoon (Model Error).")

    except Exception as e:
        print(f"General Error: {e}")

# --- 4. SMART POLLING LOOP ---
def run_bot_loop():
    print("🤖 Bot System Starting...")
    
    # Step 1: Purane webhook/connections ko force delete karein
    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception as e:
        print(f"Webhook cleanup warning: {e}")

    # Step 2: Infinite Loop
    while True:
        try:
            print("🔄 Polling start kar raha hoon...")
            bot.infinity_polling(timeout=20, long_polling_timeout=10)
        
        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ CRASH DETECTED: {error_msg}")
            
            if "409" in error_msg or "Conflict" in error_msg:
                print("🛑 DUPLICATE INSTANCE! 15 second ruk raha hoon...")
                time.sleep(15)
            elif "Connection" in error_msg or "104" in error_msg:
                print("📡 Network Issue. 5 second mein retry karunga...")
                time.sleep(5)
            else:
                time.sleep(3)

# --- 5. EXECUTION START ---
if __name__ == "__main__":
    # Bot ko alag thread mein start karein
    t = threading.Thread(target=run_bot_loop)
    t.start()
    
    # Web Server ko start karein
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
    
