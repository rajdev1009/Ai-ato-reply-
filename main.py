import os
import telebot
import google.generativeai as genai
from flask import Flask
from dotenv import load_dotenv
import threading
import time
from gtts import gTTS

# --- 1. CONFIGURATION ---
load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY") 
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not API_KEY or not BOT_TOKEN:
    print("❌ Error: API Key ya Bot Token missing hai!")

# --- 2. SMART AI MODEL SETUP ---
model = None

def setup_model():
    global model
    try:
        genai.configure(api_key=API_KEY)
        print("🔍 Google AI Models check kar raha hoon...")
        
        # Available models ki list nikalo
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        print(f"📋 Available Models: {available_models}")

        # Best Model Select karo
        target_model = ""
        if "models/gemini-1.5-flash" in available_models:
            target_model = "gemini-1.5-flash"
        elif "models/gemini-pro" in available_models:
            target_model = "gemini-pro"
        else:
            # Agar upar wale nahi mile, to list ka pehla model utha lo
            if available_models:
                target_model = available_models[0].replace("models/", "")
        
        if target_model:
            print(f"✅ Selected Model: {target_model}")
            model = genai.GenerativeModel(target_model)
        else:
            print("❌ Koi bhi compatible Gemini Model nahi mila!")

    except Exception as e:
        print(f"⚠️ Model Setup Error: {e}")

# Bot start hone se pehle model setup karo
setup_model()

# Telegram Bot Setup
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- 3. FLASK SERVER ---
@app.route('/')
def home():
    return "✅ Raj Dev Bot is Online!", 200

# --- 4. COMMANDS ---
@bot.message_handler(commands=['raj'])
def send_voice_greeting(message):
    try:
        bot.send_chat_action(message.chat.id, 'record_audio')
        text_to_speak = "Namaste! Main Raj Dev hoon."
        tts = gTTS(text=text_to_speak, lang='hi')
        file_name = f"voice_{message.chat.id}.mp3"
        tts.save(file_name)
        with open(file_name, "rb") as audio:
            bot.send_voice(message.chat.id, audio)
        os.remove(file_name)
    except Exception as e:
        print(f"Voice Error: {e}")
        bot.reply_to(message, "Voice error.")

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "🙏 Namaste! Main Raj Dev Bot hoon. Puchiye kya puchna hai.")

# --- 5. MESSAGE HANDLER ---
def get_custom_reply(text):
    text = text.lower().strip()
    if "tumhara naam" in text: return "Mera naam Raj Dev hai."
    if "kahan se ho" in text: return "Main Lumding se hoon."
    return None

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    global model
    try:
        print(f"User: {message.text}")
        
        # Custom Reply
        custom = get_custom_reply(message.text)
        if custom:
            bot.reply_to(message, custom)
            return

        # AI Reply
        if model:
            try:
                chat = model.start_chat(history=[])
                response = chat.send_message(message.text)
                if response and response.text:
                    bot.reply_to(message, response.text, parse_mode="Markdown")
                else:
                    bot.reply_to(message, "AI ne khali jawab diya.")
            except Exception as ai_e:
                print(f"AI Generation Error: {ai_e}")
                # Agar model fail hua, to dubara setup try karo
                bot.reply_to(message, "AI Error. Retrying connection...")
                setup_model()
        else:
            bot.reply_to(message, "AI Model set nahi hai. Check logs.")
            setup_model()

    except Exception as e:
        print(f"General Error: {e}")

# --- 6. POLLING LOOP ---
def run_bot_loop():
    print("🤖 Bot Starting...")
    try:
        bot.remove_webhook()
        time.sleep(1)
    except:
        pass

    while True:
        try:
            print("🔄 Polling...")
            bot.polling(non_stop=False, interval=0, timeout=20)
        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ Error: {error_msg}")
            if "409" in error_msg:
                print("🛑 Conflict! Waiting 15s...")
                time.sleep(15)
            elif "Connection" in error_msg:
                time.sleep(5)
            else:
                time.sleep(3)

if __name__ == "__main__":
    t = threading.Thread(target=run_bot_loop)
    t.start()
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
