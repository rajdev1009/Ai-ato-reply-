import os
import telebot
import google.generativeai as genai
from flask import Flask
from dotenv import load_dotenv
import threading
from gtts import gTTS
import requests
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# --- 1. SETUP & CONFIGURATION ---
load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY") 
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not API_KEY or not BOT_TOKEN:
    print("Error: Keys missing hain!")

genai.configure(api_key=API_KEY)

# SAFETY SETTINGS (Zaroori hai taaki 'Roast' mode par error na aaye)
safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

# Model Setup
model = genai.GenerativeModel('gemini-pro')

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "Raj Dev Bot is Online!", 200

# --- 2. MODES SYSTEM ---
MODES = {
    "friendly": "Tumhara naam Raj Dev hai. Hindi-English mix mein baat karo.",
    "study": "Tum ek strict Teacher ho. Sirf padhai ki baat karo.",
    "funny": "Tum ek Comedian ho. Funny jawab do aur jokes sunao.",
    "roast": "Tum ek Savage Roaster ho. User ki mazakiya bezzati karo.",
    "romantic": "Tum ek Flirty partner ho. Pyaar se baat karo.",
    "sad": "Tum bahut udaas ho. Har baat mein dukh dikhao.",
    "gk": "Tum GK expert ho. Sirf facts batao.",
    "math": "Tum Math Solver ho. Step-by-step samjhao."
}

user_modes = {} 

@bot.message_handler(commands=['mode'])
def change_mode(message):
    try:
        command_parts = message.text.split()
        if len(command_parts) < 2:
            available_modes = ", ".join([f"`{m}`" for m in MODES.keys()])
            bot.reply_to(message, f"Available Modes:\n{available_modes}\n\nExample: `/mode roast`", parse_mode="Markdown")
            return

        new_mode = command_parts[1].lower()
        if new_mode in MODES:
            user_modes[message.chat.id] = new_mode
            bot.reply_to(message, f"✅ Mood changed to: **{new_mode}**", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ Ye Mood nahi hai. `/mode` try karein.")
    except:
        bot.reply_to(message, "Error in mode change.")

# --- 3. IMAGE GENERATION ---
@bot.message_handler(commands=['img', 'photo'])
def send_ai_image(message):
    prompt = message.text.replace("/img", "").replace("/photo", "").strip()
    if not prompt:
        bot.reply_to(message, "Kuch likho! Example: `/img car`")
        return
    try:
        bot.send_chat_action(message.chat.id, 'upload_photo')
        image_url = f"https://image.pollinations.ai/prompt/{prompt}"
        bot.send_photo(message.chat.id, image_url, caption=f"🎨 {prompt}")
    except:
        bot.reply_to(message, "Photo error.")

# --- 4. VOICE COMMAND ---
@bot.message_handler(commands=['raj'])
def send_voice_greeting(message):
    try:
        bot.send_chat_action(message.chat.id, 'record_audio')
        tts = gTTS(text="Namaste! Main Raj Dev hoon.", lang='hi')
        tts.save("voice.mp3")
        with open("voice.mp3", "rb") as audio:
            bot.send_voice(message.chat.id, audio)
        os.remove("voice.mp3")
    except:
        pass

# --- 5. START & HELP ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "🤖 **Raj Dev Bot**\n/mode [name]\n/img [text]\n/raj", parse_mode="Markdown")

# --- 6. MAIN CHAT LOGIC (CRASH FIX HERE) ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        user_text = message.text
        chat_id = message.chat.id
        
        # Custom Replies
        if "tumhara naam" in user_text.lower():
            bot.reply_to(message, "Mera naam Raj Dev hai.")
            return

        # Gemini Logic
        current_mode = user_modes.get(chat_id, "friendly")
        system_instruction = MODES[current_mode]
        final_prompt = f"Act as: {system_instruction}\n\nUser says: {user_text}"
        
        bot.send_chat_action(chat_id, 'typing')
        
        # Yahan Safety Settings pass ki gayi hain taaki crash na ho
        response = model.generate_content(final_prompt, safety_settings=safety_settings)
        
        # Check karein ki response khali to nahi hai
        if response.text:
            bot.reply_to(message, response.text.replace("*", ""), parse_mode=None)
        else:
            bot.reply_to(message, "Maaf karein, main iska jawab nahi de sakta.")

    except ValueError:
        # Agar Google ne jawaab block kiya
        bot.reply_to(message, "⚠️ Google AI ne is jawaab ko unsafe maan kar rok diya.")
    except Exception as e:
        print(f"Error: {e}")
        bot.reply_to(message, f"Error: {e}")

# --- 7. RUN ---
def run_bot():
    bot.infinity_polling()

if __name__ == "__main__":
    t = threading.Thread(target=run_bot)
    t.start()
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
    
