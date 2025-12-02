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
import tempfile

# --- 1. CONFIGURATION ---
load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# 🚨 APNI ID AUR CHANNEL ID YAHAN DAALO
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
BOT_PERSONALITY = f"""
Tumhara naam '{BOT_NAME}' hai.
1. Baat cheet mein Friendly aur Cool raho.
2. Agar koi Gali de, toh Savage Roast karo.
3. Jawab hamesha Hinglish (Hindi+English mix) mein do.
4. Tum ek AI Assistant ho jo ab 'Edge TTS' voice use karta hai.
5. STRICT RULE: Tum Images (Photos) na dekh sakte ho, na hi bana (generate) sakte ho.
6. Agar user bole "Photo banao", toh saaf mana kar do.
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

def send_log_to_channel(user, request_type, query, response):
    try:
        if LOG_CHANNEL_ID:
            log_text = (
                f"📝 **Log** | 👤 {user.first_name}\n"
                f"📌 {request_type}\n"
                f"❓ {query}\n"
                f"🤖 {response}"
            )
            bot.send_message(LOG_CHANNEL_ID, log_text)
    except: pass

# --- 6. VOICE ENGINE (FIXED LOOP) ---
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
        # Create a new loop for this thread to avoid "Loop Closed" errors
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(generate_voice_edge(text, filename))
        loop.close()
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
    bot.reply_to(message, "🔥 **Dev is Online!**\nText ya Audio bhejo.", parse_mode="Markdown")

@bot.message_handler(commands=['settings'])
def settings_menu(message):
    if message.from_user.id != OWNER_ID: return
    markup = types.InlineKeyboardMarkup()
    status = "✅ ON" if MEMORY_MODE else "❌ OFF"
    markup.add(types.InlineKeyboardButton(f"Memory: {status}", callback_data="toggle_memory"))
    markup.add(types.InlineKeyboardButton("🗑️ Clear Memory", callback_data="clear_memory"))
    bot.reply_to(message, "⚙️ **Admin Panel**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "toggle_memory")
def callback_memory(call):
    if call.from_user.id != OWNER_ID: return
    global MEMORY_MODE
    MEMORY_MODE = not MEMORY_MODE
    status = "✅ ON" if MEMORY_MODE else "❌ OFF"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(f"Memory: {status}", callback_data="toggle_memory"))
    markup.add(types.InlineKeyboardButton("🗑️ Clear Memory", callback_data="clear_memory"))
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="⚙️ **Admin Panel**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "clear_memory")
def callback_clear_mem(call):
    if call.from_user.id != OWNER_ID: return
    with open(JSON_FILE, "w", encoding="utf-8") as f: json.dump({}, f)
    bot.answer_callback_query(call.id, "Memory Cleared! 🗑️")

# --- 9. VOICE & AUDIO HANDLER (IMPROVED) ---
@bot.message_handler(content_types=['voice', 'audio'])
def handle_voice_chat(message):
    try:
        bot.send_chat_action(message.chat.id, 'record_audio')
        
        # Save file to temp path
        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        user_audio_path = f"user_{message.from_user.id}.ogg"
        with open(user_audio_path, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        if model:
            # Upload to Gemini
            myfile = genai.upload_file(user_audio_path)
            
            prompt = [
                "Listen to this audio.",
                "Reply naturally in Hindi/Hinglish to the speech.",
                "DO NOT generate images. Just talk.",
                myfile
            ]
            
            result = model.generate_content(prompt)
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
                bot.reply_to(message, ai_full_text + "\n(Voice generation failed)")

            # Cleanup
            if os.path.exists(user_audio_path): os.remove(user_audio_path)
            send_log_to_channel(message.from_user, "VOICE CHAT", "Audio Message", ai_full_text)

    except Exception as e:
        # Error details user ko dikhana taaki debug kar sakein
        bot.reply_to(message, f"❌ Audio Error: {str(e)}")
        print(f"Error: {e}")

# --- 10. TEXT CHAT HANDLER ---
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    global MEMORY_MODE
    try:
        user_text = message.text
        if not user_text: return
        
        saved = get_reply_from_memory(user_text) if MEMORY_MODE else None
        
        ai_reply = ""
        if saved:
            ai_reply = saved
        elif model:
            bot.send_chat_action(message.chat.id, 'typing')
            response = model.generate_content(f"User: '{user_text}'. Reply in Hinglish. No images.")
            ai_reply = response.text
            if MEMORY_MODE: save_to_memory(user_text, ai_reply)

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔊 Suno", callback_data="speak_msg"))
        bot.reply_to(message, ai_reply, parse_mode="Markdown", reply_markup=markup)
        
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
        else:
            bot.answer_callback_query(call.id, "Voice generation failed!")
    except Exception as e:
        print(f"Callback Error: {e}")

# --- RUN BOT ---
def run_bot():
    print("🤖 Bot Started...")
    bot.infinity_polling()

if __name__ == "__main__":
    t = threading.Thread(target=run_bot)
    t.start()
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
