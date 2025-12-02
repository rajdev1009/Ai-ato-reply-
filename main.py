import os
import telebot
from telebot import types 
import google.generativeai as genai
from flask import Flask
from dotenv import load_dotenv
import threading
import time
import json 
import edge_tts
import asyncio

# --- 1. CONFIGURATION ---
load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# 🚨 IMPORTANT: Yahan apni numeric ID aur Channel ki ID daalo
# Channel ID hamesha -100 se shuru hoti hai. 
# Bot ko us channel mein ADMIN banana zaroori hai.
OWNER_ID = 5804953849  
LOG_CHANNEL_ID = -1003448442249 

if not API_KEY or not BOT_TOKEN:
    print("⚠️ Warning: API Key ya Bot Token code mein nahi mila.")

# --- 2. SETTINGS ---
BOT_NAME = "Dev"
MEMORY_MODE = True 

# Voice ID (Male - Hindi)
VOICE_ID = "hi-IN-MadhurNeural"

# --- 3. PERSONALITY ---
# Yahan humne add kiya hai ki wo user ka naam use kare
BOT_PERSONALITY = f"""
Tumhara naam '{BOT_NAME}' hai.
1. Baat cheet mein Friendly, Cool aur thoda Attitude mein raho.
2. Agar koi Gali de, toh Savage Roast karo.
3. Jawab hamesha Hinglish (Hindi+English mix) mein do.
4. User ke sath baat karte waqt uska NAAM lekar baat karo (Jaise: "Arre Rahul bhai...", "Sun Amit...").
5. Tum ek AI Assistant ho jo ab 'Edge TTS' voice use karta hai.
"""

# --- 4. AI MODEL SETUP ---
model = None
def setup_model():
    global model
    try:
        if API_KEY:
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

# --- 5. MEMORY SYSTEM ---
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
    return text.replace("*", "").replace("_", "").replace("`", "").replace("#", "")

# 📝 LOGGING FUNCTION (Ye Channel pe message bhejega)
def send_log_to_channel(user, request_type, query, response):
    try:
        if LOG_CHANNEL_ID:
            log_text = (
                f"📝 **New Interaction**\n"
                f"👤 **User:** {user.first_name} (ID: `{user.id}`)\n"
                f"📌 **Type:** {request_type}\n\n"
                f"❓ **Query:** {query}\n"
                f"🤖 **Bot Reply:** {response}"
            )
            # Log channel mein bhejna
            bot.send_message(LOG_CHANNEL_ID, log_text, parse_mode="Markdown")
    except Exception as e:
        print(f"❌ Log Error: {e}")

# --- 6. VOICE ENGINE (EDGE TTS) ---
async def generate_voice_edge(text, filename):
    try:
        communicate = edge_tts.Communicate(text, VOICE_ID)
        await communicate.save(filename)
        return True
    except Exception as e:
        print(f"TTS Error: {e}")
        return False

def text_to_speech_file(text, filename):
    try:
        asyncio.run(generate_voice_edge(text, filename))
        return True
    except Exception as e:
        print(f"Sync TTS Error: {e}")
        return False

# --- 7. SERVER ROUTE ---
@app.route('/')
def home():
    return f"✅ {BOT_NAME} is Running!", 200

# --- 8. COMMANDS ---
@bot.message_handler(commands=['start'])
def send_start(message):
    user_name = message.from_user.first_name
    welcome_text = f"🔥 **Dev is Online!**\nSwagat hai {user_name} bhai.\nText ya Audio bhejo, main reply karunga."
    bot.reply_to(message, welcome_text, parse_mode="Markdown")
    send_log_to_channel(message.from_user, "COMMAND", "/start", "Welcome Message Sent")

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

# --- 9. VOICE & AUDIO HANDLER (Updated for Name) ---
@bot.message_handler(content_types=['voice', 'audio'])
def handle_voice_chat(message):
    try:
        bot.send_chat_action(message.chat.id, 'record_audio')
        
        # User ka naam nikala
        user_name = message.from_user.first_name

        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        user_audio_path = f"user_{message.from_user.id}.ogg"
        with open(user_audio_path, 'wb') as new_file: new_file.write(downloaded_file)
            
        if model:
            # Send to Gemini with NAME instruction
            myfile = genai.upload_file(user_audio_path)
            
            # 🔥 Prompt mein User ka naam add kar diya taaki wo naam se reply kare
            prompt_parts = [
                f"User ka naam '{user_name}' hai. Uski baat suno aur Hinglish mein naturally reply karo. Uska naam use karke address karna.",
                myfile
            ]
            
            result = model.generate_content(prompt_parts)
            ai_full_text = result.text
            
            # Generate Audio Reply
            reply_audio_path = f"reply_{message.from_user.id}.mp3"
            clean_txt = clean_text_for_audio(ai_full_text)
            
            success = text_to_speech_file(clean_txt, reply_audio_path)
            
            if success:
                with open(reply_audio_path, 'rb') as voice:
                    bot.send_voice(message.chat.id, voice)
                os.remove(reply_audio_path)
            else:
                bot.reply_to(message, ai_full_text)

            if os.path.exists(user_audio_path): os.remove(user_audio_path)
            
            # Log to Channel
            send_log_to_channel(message.from_user, "VOICE CHAT", "Audio Message", ai_full_text)

    except Exception as e:
        bot.reply_to(message, "❌ Audio Error.")
        print(e)

# --- 10. TEXT CHAT HANDLER (Updated for Name) ---
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    global MEMORY_MODE
    try:
        user_text = message.text
        user_name = message.from_user.first_name # User Name
        
        if not user_text: return
        
        saved = get_reply_from_memory(user_text) if MEMORY_MODE else None
        
        ai_reply = ""
        if saved:
            ai_reply = saved
        elif model:
            bot.send_chat_action(message.chat.id, 'typing')
            # 🔥 Prompt mein Naam bheja
            prompt = f"User Name: {user_name}. User Message: '{user_text}'. Reply in Hinglish and address user by name."
            response = model.generate_content(prompt)
            ai_reply = response.text
            if MEMORY_MODE: save_to_memory(user_text, ai_reply)

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔊 Suno", callback_data="speak_msg"))
        bot.reply_to(message, ai_reply, parse_mode="Markdown", reply_markup=markup)
        
        # Log to Channel
        send_log_to_channel(message.from_user, "TEXT CHAT", user_text, ai_reply)

    except Exception as e: print(e)

# --- 11. TTS CALLBACK ---
@bot.callback_query_handler(func=lambda call: call.data == "speak_msg")
def speak_callback(call):
    try:
        bot.send_chat_action(call.message.chat.id, 'record_audio')
        filename = f"tts_{call.from_user.id}.mp3"
        clean_txt = clean_text_for_audio(call.message.text)
        
        success = text_to_speech_file(clean_txt, filename)
        
        if success:
            with open(filename, "rb") as audio: bot.send_voice(call.message.chat.id, audio)
            os.remove(filename)
    except: pass

# --- RUN BOT ---
def run_bot():
    print("🤖 Bot Started...")
    bot.infinity_polling()

if __name__ == "__main__":
    t = threading.Thread(target=run_bot)
    t.start()
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
