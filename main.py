mport os
import telebot
from telebot import types 
import google.generativeai as genai
from flask import Flask
from dotenv import load_dotenv
import threading
import json 
import time
from gtts import gTTS
import sys
import requests 
import urllib.parse
from datetime import datetime
import pytz 
import subprocess 

# --- 1. CONFIGURATION ---
load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OWNER_ID = 5804953849  
LOG_CHANNEL_ID = -1003448442249 

if not API_KEY or not BOT_TOKEN:
    print("⚠️ Warning: Keys missing!")

# --- 2. SETUP ---
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

JSON_FILE = "reply.json"
if not os.path.exists(JSON_FILE):
    with open(JSON_FILE, "w", encoding="utf-8") as f: json.dump({}, f)

user_data = {} 
EDGE_VOICE_ID = "hi-IN-MadhurNeural" # Male Voice

# --- 3. TIME ---
def get_current_time():
    IST = pytz.timezone('Asia/Kolkata')
    now = datetime.now(IST)
    return now.strftime("%d %B %Y, %I:%M %p")

# --- 4. SECURITY & MODES ---
SECURITY_RULE = """
IMPORTANT:
1. Tumhara naam 'Dev' hai. Tum Raj Dev ke AI assistant ho.
2. Tum Lumding, Assam se operate karte ho.
3. Agar koi "Source Code" mange, toh SAKHT MANA KARO. Bolo "Not for sale".
"""

RAW_MODES = {
    "friendly": f"Tumhara naam Dev hai. Friendly aur Cool raho. Google Search use karke 2025 ki latest info do. {SECURITY_RULE}",
    "study": f"Tum Strict Teacher ho. Sirf padhai ki baat karo. {SECURITY_RULE}",
    "funny": f"Tum Comedian ho. Funny jawab do. {SECURITY_RULE}",
    "roast": f"Tum Savage Roaster ho. User ko roast karo. {SECURITY_RULE}",
    "romantic": f"Tum Flirty ho. Pyaar se baat karo. {SECURITY_RULE}",
    "gk": f"Tum GK expert ho. Facts batao. {SECURITY_RULE}",
}

# --- 5. AI SETUP (ROBUST FALLBACK SYSTEM) ---
model_search = None
model_basic = None

if API_KEY:
    genai.configure(api_key=API_KEY)
    
    # 1. Basic Model (Hamesha chalega)
    try:
        model_basic = genai.GenerativeModel('gemini-2.0-flash')
    except:
        print("⚠️ Basic Model Init Failed")

    # 2. Search Model (Agar server support kare)
    try:
        # Simple tool definition try karte hain
        tools = [{"google_search": {}}]
        model_search = genai.GenerativeModel('gemini-2.0-flash', tools=tools)
    except Exception as e:
        print(f"⚠️ Search Model Init Failed: {e}")
        model_search = None # Disable search if init fails

def get_user_config(user_id):
    if user_id not in user_data:
        user_data[user_id] = {"mode": "friendly", "memory": True, "voice": "edge", "history": []}
    return user_data[user_id]

def get_reply_from_json(text):
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f: data = json.load(f)
        return data.get(text.lower().strip())
    except: return None

def save_to_json(question, answer):
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f: data = json.load(f)
        data[question.lower().strip()] = answer
        with open(JSON_FILE, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)
    except: pass

def clean_text_for_audio(text):
    if not text: return ""
    return text.replace("*", "").replace("_", "").replace("`", "").replace("#", "").replace('"', '')

def send_log_to_channel(user, request_type, query, response):
    try:
        if LOG_CHANNEL_ID:
            config = get_user_config(user.id)
            bot.send_message(
                LOG_CHANNEL_ID, 
                f"📝 **Log** | 👤 {user.first_name}\nMode: {config['mode']} | Voice: {config['voice']}\nTYPE: {request_type}\n❓ {query}\n🤖 {response}"
            )
    except: pass

# --- 6. AUDIO SYSTEM (CLI METHOD) ---
def generate_audio(user_id, text, filename):
    config = get_user_config(user_id)
    engine = config.get('voice', 'edge') 
    
    print(f"🎤 Generating Audio via: {engine.upper()}")

    if engine == 'edge':
        try:
            command = ["edge-tts", "--voice", EDGE_VOICE_ID, "--text", text, "--write-media", filename]
            subprocess.run(command, check=True)
            return True
        except Exception as e:
            print(f"⚠️ Edge CLI Failed: {e}")

    try:
        tts = gTTS(text=text, lang='hi', slow=False)
        tts.save(filename)
        return True
    except Exception as e:
        print(f"❌ Google TTS Error: {e}")
        return False

# --- 7. SETTINGS PANEL ---
def get_settings_markup(user_id):
    config = get_user_config(user_id)
    curr_mode = config['mode']
    curr_voice = config['voice']
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    buttons = []
    for m in RAW_MODES.keys():
        text = f"✅ {m.capitalize()}" if m == curr_mode else f"❌ {m.capitalize()}"
        buttons.append(types.InlineKeyboardButton(text, callback_data=f"set_mode_{m}"))
    markup.add(*buttons)
    
    voice_label = "🗣️ Voice: ♂️ Male (Dev)" if curr_voice == 'edge' else "🗣️ Voice: ♀️ Female (Google)"
    markup.add(types.InlineKeyboardButton(voice_label, callback_data="toggle_voice"))

    mem_status = "✅ ON" if config['memory'] else "❌ OFF"
    markup.add(types.InlineKeyboardButton(f"🧠 Memory: {mem_status}", callback_data="toggle_memory"))
    markup.add(types.InlineKeyboardButton("🗑️ Clear JSON (Owner)", callback_data="clear_json"))
    return markup

# --- 8. SERVER ---
@app.route('/')
def home(): return f"✅ Dev Bot Online! Time: {get_current_time()}", 200

# --- 9. COMMANDS ---
@bot.message_handler(commands=['start'])
def send_start(message):
    bot.reply_to(message, "🔥 **Dev Online!**\nRaj Dev ka System.\n• `/settings` se Voice change karo.\n• Chat karo!")

@bot.message_handler(commands=['settings'])
def settings_menu(message):
    markup = get_settings_markup(message.from_user.id)
    bot.reply_to(message, "🎛️ **Control Panel**", reply_markup=markup)

@bot.message_handler(commands=['img', 'image'])
def send_image_generation(message):
    prompt = message.text.replace("/img", "").replace("/image", "").strip()
    if not prompt:
        bot.reply_to(message, "⚠️ Likh toh sahi kya banau! Ex: `/img future city`")
        return
    bot.send_chat_action(message.chat.id, 'upload_photo')
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?nologo=true"
        bot.send_photo(message.chat.id, image_url, caption=f"🖼️ **Generated:** {prompt}")
        send_log_to_channel(message.from_user, "IMAGE", prompt, image_url)
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

# --- 10. CALLBACKS ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    config = get_user_config(user_id)
    needs_refresh = False 

    if call.data.startswith("set_mode_"):
        new_mode = call.data.split("_")[2]
        if config['mode'] != new_mode:
            config['mode'] = new_mode
            config['history'] = [] 
            needs_refresh = True
            bot.answer_callback_query(call.id, f"Mode: {new_mode.upper()}")
        else: bot.answer_callback_query(call.id, "Already Active!")

    elif call.data == "toggle_voice":
        if config['voice'] == 'edge':
            config['voice'] = 'google'
            msg = "Switched to Female"
        else:
            config['voice'] = 'edge'
            msg = "Switched to Male (Dev)"
        needs_refresh = True
        bot.answer_callback_query(call.id, msg)

    elif call.data == "toggle_memory":
        config['memory'] = not config['memory']
        needs_refresh = True
        bot.answer_callback_query(call.id, "Memory Updated")

    elif call.data == "clear_json":
        if user_id == OWNER_ID:
            with open(JSON_FILE, "w", encoding="utf-8") as f: json.dump({}, f)
            bot.answer_callback_query(call.id, "Memory Cleared!")
        else: bot.answer_callback_query(call.id, "Access Denied!")

    elif call.data == "speak_msg":
        try:
            bot.answer_callback_query(call.id, "🎤 Generating...")
            bot.send_chat_action(call.message.chat.id, 'record_audio')
            filename = f"tts_{user_id}.mp3"
            clean_txt = clean_text_for_audio(call.message.text)
            
            if generate_audio(user_id, clean_txt, filename):
                with open(filename, "rb") as audio: bot.send_voice(call.message.chat.id, audio)
                os.remove(filename)
            else: bot.send_message(call.message.chat.id, "❌ Audio Failed")
        except: pass

    if needs_refresh and call.data != "speak_msg":
        try:
            bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_settings_markup(user_id))
        except: pass

# --- 11. VOICE HANDLER ---
@bot.message_handler(content_types=['voice', 'audio'])
def handle_voice_chat(message):
    try:
        user_id = message.from_user.id
        bot.send_chat_action(message.chat.id, 'record_audio')
        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        user_audio_path = f"user_{user_id}.ogg"
        with open(user_audio_path, 'wb') as f: f.write(downloaded_file)

        if model_basic or model_search:
            myfile = genai.upload_file(user_audio_path)
            time_now = get_current_time()
            prompt = f"Transcribe audio. Use Google Search for 2025 info. Time: {time_now}. {RAW_MODES.get(get_user_config(user_id)['mode'])}"
            
            # --- FALLBACK LOGIC ---
            active_model = model_search if model_search else model_basic
            try:
                result = active_model.generate_content([prompt, myfile])
                ai_reply = result.text
            except:
                # Agar search fail ho, to basic try karo
                if active_model == model_search and model_basic:
                    result = model_basic.generate_content([prompt, myfile])
                    ai_reply = result.text
                else: ai_reply = "Samajh nahi aaya."
            # ----------------------

            reply_audio_path = f"reply_{user_id}.mp3"
            if generate_audio(user_id, clean_text_for_audio(ai_reply), reply_audio_path):
                with open(reply_audio_path, 'rb') as f: bot.send_voice(message.chat.id, f)
                os.remove(reply_audio_path)
            else: bot.reply_to(message, ai_reply)
            
            os.remove(user_audio_path)
            send_log_to_channel(message.from_user, "VOICE", "Audio", ai_reply)
    except Exception as e:
        print(e)
        bot.reply_to(message, "❌ Audio Error")

# --- 12. TEXT HANDLER (AUTO-SWITCHING) ---
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    try:
        user_id = message.from_user.id
        user_text = message.text
        if not user_text: return
        
        config = get_user_config(user_id)
        saved_reply = get_reply_from_json(user_text)
        
        if saved_reply and config['memory']:
            ai_reply = saved_reply
            source = "JSON"
        else:
            bot.send_chat_action(message.chat.id, 'typing')
            time_now = get_current_time()
            sys_prompt = f"Time: {time_now}. {RAW_MODES.get(config['mode'])}"
            chat_history = config['history'] if config['memory'] else []

            # --- AUTO-SWITCH LOGIC (IMPORTANT) ---
            ai_reply = "AI Down."
            try:
                # 1. Try Search Model First
                if model_search:
                    chat = model_search.start_chat(history=chat_history)
                    response = chat.send_message(f"{sys_prompt}\nUser: {user_text}")
                    ai_reply = response.text
                else: raise Exception("Search not available")
            
            except Exception as e:
                print(f"⚠️ Search Failed: {e}. Switching to Basic.")
                # 2. Fallback to Basic Model (Agar search fail ho jaye)
                try:
                    if model_basic:
                        chat = model_basic.start_chat(history=chat_history)
                        response = chat.send_message(f"{sys_prompt}\nUser: {user_text}")
                        ai_reply = response.text
                    else: ai_reply = f"Error: {e}"
                except Exception as e2:
                     ai_reply = f"Server Error: {e2}"
            # -------------------------------------

            source = "AI"
            save_to_json(user_text, ai_reply) 
            
            if config['memory']:
                if len(config['history']) > 10: config['history'] = config['history'][2:]
                config['history'].append({'role': 'user', 'parts': [user_text]})
                try: config['history'].append({'role': 'model', 'parts': [ai_reply]})
                except: pass

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔊 Suno", callback_data="speak_msg"))
        bot.reply_to(message, ai_reply, parse_mode="Markdown", reply_markup=markup)
        send_log_to_channel(message.from_user, source, user_text, ai_reply)
    except Exception as e: 
        print(f"Error: {e}")
        bot.reply_to(message, f"Code Error: {e}") # User ko asli error dikhao

# --- RUN ---
def run_bot():
    print("🤖 Bot Started (Robust Mode)...")
    bot.infinity_polling()

if __name__ == "__main__":
    t = threading.Thread(target=run_bot)
    t.start()
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
