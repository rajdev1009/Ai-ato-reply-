import os
import telebot
from telebot import types 
import google.generativeai as genai
from flask import Flask
from dotenv import load_dotenv
import threading
import time
import json 
from gtts import gTTS
import re
import requests  # Nayi Library: Images download karne ke liye

# --- 1. CONFIGURATION (APNI DETAILS YAHAN BHARO) ---
load_dotenv()

# Agar .env file use nahi kar rahe, toh direct strings yahan likh sakte ho
API_KEY = os.getenv("GOOGLE_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# SABSE ZAROORI: Apni Telegram Numeric ID yahan daalo
OWNER_ID = 5804953849  # Replace with your actual ID

if not API_KEY or not BOT_TOKEN:
    print("❌ Error: API Key ya Bot Token missing hai!")

# --- 2. SETTINGS ---
BOT_NAME = "Dev"
OWNER_NAME = "Raj Dev"
LOCATION = "Lumding, Assam"
MEMORY_MODE = True 

# --- 3. DANGEROUS PERSONALITY SETUP ---
BOT_PERSONALITY = f"""
Tumhara naam '{BOT_NAME}' hai. Tumhe '{OWNER_NAME}' ({LOCATION}) ne banaya hai.

TUMHARA CHARACTER:
1. **BEHAVIOR:** Normal baat pe friendly, gali dene wale ko savage roast.
2. **MOVIES & SERIES:** Tum expert ho.
3. **PADHAI:** Maths/Science serious hoke padhana.
4. **CREATIVITY:** Tumhe pata hai ki tum photos bhi bana sakte ho (User ko bolo '/img' use kare).
5. **IDENTITY:** Raj Dev ka system hoon.
"""

# --- 4. AI MODEL SETUP ---
model = None
def setup_model():
    global model
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel(
            model_name='gemini-2.0-flash', 
            generation_config={"temperature": 1.0, "max_output_tokens": 800},
            system_instruction=BOT_PERSONALITY
        )
        print("✅ AI Model Connected!")
    except Exception as e:
        print(f"⚠️ Model Error: {e}")

setup_model()

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- 5. SMART MEMORY SYSTEM ---
JSON_FILE = "reply.json"
if not os.path.exists(JSON_FILE):
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f)

def get_reply_from_memory(text):
    try:
        if not text: return None
        key = text.lower().strip()
        with open(JSON_FILE, "r") as f: data = json.load(f)
        return data.get(key)
    except: return None

def save_to_memory(question, answer):
    try:
        with open(JSON_FILE, "r") as f: data = json.load(f)
        data[question.lower().strip()] = answer
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except: pass

def clean_text_for_audio(text):
    return text.replace("*", "").replace("_", "").replace("`", "")

# --- 6. FLASK SERVER ---
@app.route('/')
def home():
    return f"✅ {BOT_NAME} is Online!", 200

# --- 7. BASIC COMMANDS ---
@bot.message_handler(commands=['start'])
def send_start(message):
    user_name = message.from_user.first_name or "Bhai"
    txt = (
        f"🔥 **Namaste {user_name}! Main {BOT_NAME} hoon.**\n\n"
        "👑 **Features:**\n"
        "• 🗣️ Baat-cheet & Roast\n"
        "• 🎨 **Image Generation:** `/img <prompt>` use karo\n"
        "• 🎬 Movie Reviews\n"
        "• 📚 Study Help\n\n"
        "Bol kya scene hai?"
    )
    bot.reply_to(message, txt, parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def send_help(message):
    bot.reply_to(message, "🆘 **Help:**\n• Chat karo normal.\n• Photo ke liye: `/img cat on bike` likho.\n• Settings sirf Boss ke liye.", parse_mode="Markdown")

# --- 8. IMAGE GENERATION COMMAND (NEW) ---
@bot.message_handler(commands=['img', 'image'])
def send_image_generation(message):
    # Prompt nikalna: "/img" ko hata kar baaki text lena
    prompt = message.text.replace("/img", "").replace("/image", "").strip()
    
    if not prompt:
        bot.reply_to(message, "⚠️ **Abe gadhe!** Photo kiski banau? \nAise likh: `/img flying dog`")
        return

    bot.send_chat_action(message.chat.id, 'upload_photo')
    bot.reply_to(message, "🎨 **Photo bana raha hoon, ruko...**")
    
    try:
        # Free Pollinations API use kar rahe hain (Best for Telegram Bots)
        # Kyunki Google ka Imagen API kabhi kabhi free keys pe nahi chalta
        image_url = f"https://image.pollinations.ai/prompt/{prompt}"
        
        bot.send_photo(message.chat.id, image_url, caption=f"🖼️ **Generated:** {prompt}\n🤖 By: {BOT_NAME}")
    except Exception as e:
        bot.reply_to(message, f"❌ Error aa gaya: {e}")

# --- 9. OWNER SETTINGS ---
@bot.message_handler(commands=['settings'])
def settings_menu(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "🚫 **Access Denied!**")
        return
    markup = types.InlineKeyboardMarkup()
    status_text = "✅ ON" if MEMORY_MODE else "❌ OFF"
    markup.add(types.InlineKeyboardButton(f"Memory: {status_text}", callback_data="toggle_memory"))
    bot.reply_to(message, f"⚙️ **Admin Panel**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "toggle_memory")
def callback_memory(call):
    if call.from_user.id != OWNER_ID: return
    global MEMORY_MODE
    MEMORY_MODE = not MEMORY_MODE
    new_status = "✅ ON" if MEMORY_MODE else "❌ OFF"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(f"Memory: {new_status}", callback_data="toggle_memory"))
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                          text=f"⚙️ **Admin Panel**", reply_markup=markup)

# --- 10. AUDIO HANDLER ---
@bot.callback_query_handler(func=lambda call: call.data == "speak_msg")
def speak_message_callback(call):
    try:
        bot.send_chat_action(call.message.chat.id, 'record_audio')
        bot.answer_callback_query(call.id, "Processing...")
        original_text = call.message.text
        if not original_text: return
        
        filename = f"voice_{call.from_user.id}.mp3"
        tts = gTTS(text=clean_text_for_audio(original_text), lang='hi')
        tts.save(filename)
        with open(filename, "rb") as audio:
            bot.send_voice(call.message.chat.id, audio)
        os.remove(filename)
    except Exception as e:
        print(e)

# --- 11. MAIN CHAT LOGIC ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    global MEMORY_MODE
    try:
        user_text = message.text
        if not user_text: return
        first_name = message.from_user.first_name or "Bhai"
        
        # Check Memory
        if MEMORY_MODE:
            saved = get_reply_from_memory(user_text)
            if saved:
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔊 Suno", callback_data="speak_msg"))
                bot.reply_to(message, f"{first_name}, {saved}", reply_markup=markup)
                return

        # AI Generation
        if model:
            bot.send_chat_action(message.chat.id, 'typing')
            ai_prompt = (
                f"User: {first_name}. Query: '{user_text}'. "
                "Agar user photo mange, toh bolo '/img' command use kare. "
                "Normal baat pe friendly, gali pe savage roast."
            )
            response = model.generate_content(ai_prompt)
            ai_reply = response.text
            
            if MEMORY_MODE: save_to_memory(user_text, ai_reply)

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔊 Suno", callback_data="speak_msg"))
            bot.reply_to(message, ai_reply, parse_mode="Markdown", reply_markup=markup)
            
    except Exception as e:
        print(f"Error: {e}")

# --- POLLING ---
if __name__ == "__main__":
    t = threading.Thread(target=bot.infinity_polling)
    t.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
