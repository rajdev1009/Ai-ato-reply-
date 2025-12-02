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
import requests
import urllib.parse

# --- 1. CONFIGURATION ---
load_dotenv()

# Apni API Keys yahan dalein
API_KEY = os.getenv("GOOGLE_API_KEY", "YOUR_GEMINI_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")

# 🚨 ADMIN SETTINGS (Zaroori Hai)
OWNER_ID = 5804953849  # Apni Personal ID
LOG_CHANNEL_ID = -1003448442249 # Apne Channel ki ID yahan daalo (Minus sign ke saath)

if not API_KEY or not BOT_TOKEN:
    print("❌ Error: API Key ya Bot Token missing hai!")

# --- 2. SETTINGS ---
BOT_NAME = "Dev"
OWNER_NAME = "Raj Dev"
LOCATION = "Lumding, Assam"
MEMORY_MODE = True 

# --- 3. PERSONALITY ---
BOT_PERSONALITY = f"""
Tumhara naam '{BOT_NAME}' hai. Tumhe '{OWNER_NAME}' ({LOCATION}) ne banaya hai.
1. Normal baat pe friendly, gali pe savage roast.
2. Movies/Series expert.
3. Maths/Science teacher.
4. Photo create kar sakte ho (/img command).
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

# --- 5. MEMORY & LOGGING SYSTEM ---
JSON_FILE = "reply.json"
if not os.path.exists(JSON_FILE):
    with open(JSON_FILE, "w", encoding="utf-8") as f: json.dump({}, f)

def get_reply_from_memory(text):
    try:
        if not text: return None
        with open(JSON_FILE, "r") as f: data = json.load(f)
        return data.get(text.lower().strip())
    except: return None

def save_to_memory(question, answer):
    try:
        with open(JSON_FILE, "r") as f: data = json.load(f)
        data[question.lower().strip()] = answer
        with open(JSON_FILE, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)
    except: pass

def clean_text_for_audio(text):
    return text.replace("*", "").replace("_", "").replace("`", "")

# 🔥 NEW: LOGGING FUNCTION (Channel mein bhejega)
def send_log_to_channel(user, request_type, query, response):
    try:
        log_text = (
            f"📝 **New Activity Log**\n\n"
            f"👤 **User:** {user.first_name} (ID: `{user.id}`)\n"
            f"📌 **Type:** {request_type}\n"
            f"❓ **Query:** {query}\n"
            f"🤖 **Bot Reply:** {response}"
        )
        bot.send_message(LOG_CHANNEL_ID, log_text, parse_mode="Markdown")
    except Exception as e:
        print(f"Logging Error: {e}")

# --- 6. SERVER ---
@app.route('/')
def home(): return f"✅ {BOT_NAME} Online with Logging!", 200

# --- 7. COMMANDS ---
@bot.message_handler(commands=['start'])
def send_start(message):
    bot.reply_to(message, "🔥 **System Online!**\n• Chat karo\n• `/img cat` likho photo ke liye\n• Voice bhejo baat karne ke liye", parse_mode="Markdown")

# --- 8. IMAGE GENERATION (With Logging) ---
@bot.message_handler(commands=['img', 'image'])
def send_image_generation(message):
    prompt = message.text.replace("/img", "").replace("/image", "").strip()
    if not prompt:
        bot.reply_to(message, "⚠️ Likh toh sahi kya banau! Ex: `/img flying dog`")
        return

    bot.send_chat_action(message.chat.id, 'upload_photo')
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        seed = int(time.time())
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?seed={seed}"
        
        bot.send_photo(message.chat.id, image_url, caption=f"🖼️ **Generated:** {prompt}")
        
        # ✅ LOGGING
        send_log_to_channel(message.from_user, "IMAGE GENERATION", prompt, f"Image Sent: {image_url}")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

# --- 9. OWNER SETTINGS ---
@bot.message_handler(commands=['settings'])
def settings_menu(message):
    if message.from_user.id != OWNER_ID: return
    markup = types.InlineKeyboardMarkup()
    status = "✅ ON" if MEMORY_MODE else "❌ OFF"
    markup.add(types.InlineKeyboardButton(f"Memory: {status}", callback_data="toggle_memory"))
    bot.reply_to(message, "⚙️ **Admin Panel**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "toggle_memory")
def callback_memory(call):
    if call.from_user.id != OWNER_ID: return
    global MEMORY_MODE
    MEMORY_MODE = not MEMORY_MODE
    status = "✅ ON" if MEMORY_MODE else "❌ OFF"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(f"Memory: {status}", callback_data="toggle_memory"))
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="⚙️ **Admin Panel**", reply_markup=markup)

# --- 10. VOICE CHAT (With Logging) ---
@bot.message_handler(content_types=['voice', 'audio'])
def handle_voice_chat(message):
    try:
        bot.send_chat_action(message.chat.id, 'record_audio')
        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        user_audio_path = f"user_{message.from_user.id}.ogg"
        with open(user_audio_path, 'wb') as new_file: new_file.write(downloaded_file)
            
        if model:
            myfile = genai.upload_file(user_audio_path)
            # AI ko bol rahe hain transcribe bhi kare taaki log mein dikhe
            result = model.generate_content(["First transcribe what user said in bracket [], then give reply.", myfile])
            ai_full_text = result.text
            
            # Log ke liye text nikalna
            reply_audio_path = f"reply_{message.from_user.id}.mp3"
            tts = gTTS(text=clean_text_for_audio(ai_full_text), lang='hi')
            tts.save(reply_audio_path)
            
            with open(reply_audio_path, 'rb') as voice:
                bot.send_voice(message.chat.id, voice)
            
            os.remove(user_audio_path)
            os.remove(reply_audio_path)

            # ✅ LOGGING
            send_log_to_channel(message.from_user, "VOICE CHAT", "Audio File", ai_full_text)

    except Exception as e:
        bot.reply_to(message, "❌ Audio samajh nahi aaya.")

# --- 11. TEXT CHAT (With Logging) ---
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    global MEMORY_MODE
    try:
        user_text = message.text
        if not user_text: return
        
        if MEMORY_MODE:
            saved = get_reply_from_memory(user_text)
            if saved:
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔊 Suno", callback_data="speak_msg"))
                bot.reply_to(message, saved, reply_markup=markup)
                return

        if model:
            bot.send_chat_action(message.chat.id, 'typing')
            ai_prompt = (
                f"User: {message.from_user.first_name}. Query: '{user_text}'. "
                "Agar user photo mange, toh bolo '/img' use kare. Reply in Hinglish."
            )
            response = model.generate_content(ai_prompt)
            ai_reply = response.text
            
            if MEMORY_MODE: save_to_memory(user_text, ai_reply)

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔊 Suno", callback_data="speak_msg"))
            bot.reply_to(message, ai_reply, parse_mode="Markdown", reply_markup=markup)
            
            # ✅ LOGGING
            send_log_to_channel(message.from_user, "TEXT CHAT", user_text, ai_reply)

    except Exception as e: print(e)

@bot.callback_query_handler(func=lambda call: call.data == "speak_msg")
def speak_callback(call):
    try:
        bot.send_chat_action(call.message.chat.id, 'record_audio')
        filename = f"tts_{call.from_user.id}.mp3"
        tts = gTTS(text=clean_text_for_audio(call.message.text), lang='hi')
        tts.save(filename)
        with open(filename, "rb") as audio: bot.send_voice(call.message.chat.id, audio)
        os.remove(filename)
    except: pass

# --- POLLING ---
if __name__ == "__main__":
    t = threading.Thread(target=bot.infinity_polling)
    t.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
