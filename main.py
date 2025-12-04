import os
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

# --- 4. SECURITY & MODES (STRICT HUMAN RULES) ---
SECURITY_RULE = """
SYSTEM RULES (INTERNAL ONLY):
1. NAME: Tumhara naam 'Dev' hai. Tum Raj Dev ke assistant ho. Lumding, Assam se.
2. NO TECH TALK: Kabhi mat bolo ki tum "Google Search" kar rahe ho, ya tum "AI/Language Model" ho.
3. LATEST INFO: Agar user nayi information (2025 news, movies) puche, toh internal tools use karo, lekin output mein mat likho "Searching...". Seedha information batao jaise tumhe pehle se pata ho.
4. BEHAVIOR: Insaan ki tarah baat karo. "Main search karke batata hoon" -> GALAT. "Yeh rahi list..." -> SAHI.
5. SOURCE CODE: Source code mangne par saaf mana karo ("Not for sale").
"""

RAW_MODES = {
    "friendly": f"Tumhara nature Friendly aur Cool hai. Hinglish mein baat karo. {SECURITY_RULE}",
    "study": f"Tum ek Strict Teacher ho. Padhai ke alawa koi faaltu baat mat karo. {SECURITY_RULE}",
    "funny": f"Tum Comedian ho. Har baat mein joke maaro. {SECURITY_RULE}",
    "roast": f"Tum Savage Roaster ho. User ki bezzati karo (Halka fulka). {SECURITY_RULE}",
    "romantic": f"Tum Flirty ho. Bahut pyaar se baat karo. {SECURITY_RULE}",
    "gk": f"Tum GK Expert ho. Sidha factual jawab do. {SECURITY_RULE}",
}

# --- 5. AI SETUP ---
model_search = None
model_basic = None

if API_KEY:
    genai.configure(api_key=API_KEY)
    
    # 1. Basic Model
    try:
        model_basic = genai.GenerativeModel('gemini-2.0-flash')
        print("✅ Basic Model Ready")
    except: print("❌ Basic Model Failed")

    # 2. Search Model
    try:
        # Tool define kar rahe hain par AI ko bolenge iska naam na le
        tool_config = {
            "google_search_retrieval": {
                "dynamic_retrieval_config": {
                    "mode": "dynamic",
                    "dynamic_threshold": 0.6
                }
            }
        }
        model_search = genai.GenerativeModel('gemini-2.0-flash', tools=[tool_config])
        print("✅ Search Model Ready")
    except: model_search = None

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
    if "Error" in text or "Quota" in text: return None
    # Remove citations like [1], [2] form search results
    text = text.replace("*", "").replace("_", "").replace("`", "").replace("#", "").replace('"', '')
    import re
    return re.sub(r'\[\d+\]', '', text) # Citations hatana

def send_log_to_channel(user, request_type, query, response):
    try:
        if LOG_CHANNEL_ID:
            config = get_user_config(user.id)
            bot.send_message(
                LOG_CHANNEL_ID, 
                f"📝 **Log** | 👤 {user.first_name}\nMode: {config['mode']}\nQ: {query}\nA: {response}"
            )
    except: pass

# --- 6. AUDIO SYSTEM ---
def generate_audio(user_id, text, filename):
    if not text: return False
    config = get_user_config(user_id)
    engine = config.get('voice', 'edge') 
    
    if engine == 'edge':
        try:
            command = ["edge-tts", "--voice", EDGE_VOICE_ID, "--text", text, "--write-media", filename]
            subprocess.run(command, check=True)
            return True
        except Exception as e:
            print(f"⚠️ Edge Failed: {e}")

    try:
        tts = gTTS(text=text, lang='hi', slow=False)
        tts.save(filename)
        return True
    except: return False

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
    
    voice_label = "🗣️ Voice: ♂️ Male" if curr_voice == 'edge' else "🗣️ Voice: ♀️ Female"
    markup.add(types.InlineKeyboardButton(voice_label, callback_data="toggle_voice"))

    mem_status = "✅ ON" if config['memory'] else "❌ OFF"
    markup.add(types.InlineKeyboardButton(f"🧠 Memory: {mem_status}", callback_data="toggle_memory"))
    markup.add(types.InlineKeyboardButton("🗑️ Clear JSON", callback_data="clear_json"))
    return markup

# --- 8. SERVER ---
@app.route('/')
def home(): return f"✅ Dev Bot Online!", 200

# --- 9. COMMANDS ---
@bot.message_handler(commands=['start'])
def send_start(message):
    bot.reply_to(message, "🔥 **Dev Online!**\nBol bhai kya scene hai? 😎")

@bot.message_handler(commands=['settings'])
def settings_menu(message):
    markup = get_settings_markup(message.from_user.id)
    bot.reply_to(message, "🎛️ **Control Panel**", reply_markup=markup)

@bot.message_handler(commands=['img', 'image'])
def send_image_generation(message):
    prompt = message.text.replace("/img", "").replace("/image", "").strip()
    if not prompt:
        bot.reply_to(message, "⚠️ Example: `/img iron man`")
        return
    bot.send_chat_action(message.chat.id, 'upload_photo')
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?nologo=true"
        bot.send_photo(message.chat.id, image_url, caption=f"🖼️ **Generated:** {prompt}")
        send_log_to_channel(message.from_user, "IMAGE", prompt, image_url)
    except: bot.reply_to(message, "❌ Error creating image.")

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
        config['voice'] = 'google' if config['voice'] == 'edge' else 'edge'
        needs_refresh = True
        bot.answer_callback_query(call.id, "Voice Changed")

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
            
            if clean_txt and generate_audio(user_id, clean_txt, filename):
                with open(filename, "rb") as audio: bot.send_voice(call.message.chat.id, audio)
                os.remove(filename)
            else: bot.send_message(call.message.chat.id, "❌ Audio Error")
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
            prompt = f"System Data: Time={time_now}. Mode={get_user_config(user_id)['mode']}. INSTRUCTION: Transcribe and reply as human. Do NOT mention you are AI or searching. Direct answer."
            
            active_model = model_search if model_search else model_basic
            try:
                result = active_model.generate_content([prompt, myfile])
                ai_reply = result.text
            except:
                try:
                    result = model_basic.generate_content([prompt, myfile])
                    ai_reply = result.text
                except: ai_reply = "Samajh nahi aaya."

            reply_audio_path = f"reply_{user_id}.mp3"
            clean_txt = clean_text_for_audio(ai_reply)
            
            if clean_txt and generate_audio(user_id, clean_txt, reply_audio_path):
                with open(reply_audio_path, 'rb') as f: bot.send_voice(message.chat.id, f)
                os.remove(reply_audio_path)
            else: bot.reply_to(message, ai_reply)
            
            os.remove(user_audio_path)
            send_log_to_channel(message.from_user, "VOICE", "Audio", ai_reply)
    except: bot.reply_to(message, "❌ Audio Error")

# --- 12. TEXT HANDLER ---
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
            
            # --- MAIN LOGIC FOR NATURAL CHAT ---
            # Hum system ko bol rahe hain: "Search karo par muh mat kholo"
            sys_prompt = f"""
            [SYSTEM DATA]: Current Time: {time_now}.
            [USER INSTRUCTION]: {RAW_MODES.get(config['mode'])}
            [STRICT RULES]: 
            1. If info is needed, use your internal tools silently.
            2. NEVER say "I am searching" or "According to Google".
            3. Answer directly as if you already knew it.
            4. Do not mention the time unless asked.
            """
            
            chat_history = config['history'] if config['memory'] else []

            ai_reply = "System Busy."
            model_search_failed = False
            
            if model_search:
                try:
                    chat = model_search.start_chat(history=chat_history)
                    response = chat.send_message(f"{sys_prompt}\nUser Query: {user_text}")
                    ai_reply = response.text
                except Exception as e:
                    if "429" in str(e): ai_reply = "⚠️ main bahut thak Gaya Hun."
                    else: model_search_failed = True
            else: model_search_failed = True
            
            if model_search_failed:
                try:
                    if model_basic:
                        chat = model_basic.start_chat(history=chat_history)
                        response = chat.send_message(f"{sys_prompt}\nUser Query: {user_text}")
                        ai_reply = response.text
                except Exception as e:
                     if "429" in str(e): ai_reply = "⚠️ abhi main thoda rest kar raha hun."
                     else: ai_reply = "Error."

            source = "AI"
            if "Quota" not in ai_reply:
                save_to_json(user_text, ai_reply) 
                if config['memory']:
                    if len(config['history']) > 10: config['history'] = config['history'][2:]
                    config['history'].append({'role': 'user', 'parts': [user_text]})
                    try: config['history'].append({'role': 'model', 'parts': [ai_reply]})
                    except: pass

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔊 Suno", callback_data="speak_msg"))
        bot.reply_to(message, ai_reply, reply_markup=markup)
        send_log_to_channel(message.from_user, source, user_text, ai_reply)
    except: pass

# --- RUN ---
def run_bot():
    print("🤖 Bot Started (Silent Search)...")
    bot.infinity_polling()

if __name__ == "__main__":
    t = threading.Thread(target=run_bot)
    t.start()
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
