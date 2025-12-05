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

# --- IMPORT OPTIONAL MODULES ---
try:
    import web_tools
    import quiz_game
except ImportError:
    print("⚠️ Warning: Helper modules missing.")

# --- 1. CONFIGURATION ---
load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OWNER_ID = 5804953849  
LOG_CHANNEL_ID = -1003448442249 

if not API_KEY or not BOT_TOKEN:
    print("⚠️ Warning: Keys missing in .env file!")

# --- 2. SETUP ---
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

JSON_FILE = "reply.json"
if not os.path.exists(JSON_FILE):
    with open(JSON_FILE, "w", encoding="utf-8") as f: json.dump({}, f)

user_data = {} 
EDGE_VOICE_ID = "hi-IN-MadhurNeural" 

# --- 3. TIME ---
def get_current_time():
    IST = pytz.timezone('Asia/Kolkata')
    now = datetime.now(IST)
    return now.strftime("%d %B %Y, %I:%M %p")

# --- 4. MODES ---
SECURITY_RULE = """
SYSTEM RULES:
1. NAME: Tumhara naam 'Dev' hai.
2. NO TECH TALK: Kabhi mat bolo ki tum AI ho. Natural baat karo.
3. Creator: Raj Dev.
"""

RAW_MODES = {
    "friendly": f"Tumhara nature Friendly aur Cool hai. Hinglish mein baat karo. {SECURITY_RULE}",
    "study": f"Tum ek Strict Teacher ho. Padhai ke alawa koi faaltu baat mat karo. {SECURITY_RULE}",
    "funny": f"Tum Comedian ho. Har baat mein joke maaro. {SECURITY_RULE}",
    "roast": f"Tum Roast karte ho. User ki bezzati karo (limit mein). Hinglish. {SECURITY_RULE}",
    "romantic": f"Tum Flirty ho. Bahut pyaar se baat karo. {SECURITY_RULE}",
    "gk": f"Tum GK Expert ho. Factual jawab do. {SECURITY_RULE}",
}

# --- 5. UNIVERSAL MODEL LOADER (AUTO-LISTING) ---
genai.configure(api_key=API_KEY)

def get_working_model():
    print("🔄 Connecting to Google to fetch YOUR available models...")
    try:
        my_models = []
        # Google se pucho ki mere account par kya kya active hai
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                my_models.append(m.name)
        
        print(f"📋 Your Account Models: {my_models}")

        if not my_models:
            print("❌ No models found! Your API Key might be invalid or restricted.")
            return None, None

        # Hamari pasand (Priority)
        preferences = ['models/gemini-2.5-flash', 'models/gemini-1.5-flash', 'models/gemini-1.5-flash-latest', 'models/gemini-pro', 'models/gemini-1.0-pro']
        
        selected_model = my_models[0] # Jo pehla mile wo lelo (Fallback)

        # Agar hamari pasand ka koi model list mein hai, to wo select karo
        for pref in preferences:
            if pref in my_models:
                selected_model = pref
                break
        
        print(f"✅ FINAL SELECTION: {selected_model}")
        return genai.GenerativeModel(selected_model), selected_model

    except Exception as e:
        print(f"⚠️ Critical Error listing models: {e}")
        return None, None

# Initialize Model
model_basic, active_model_name = get_working_model()

# Search Tool Setup
try:
    if active_model_name and "flash" in active_model_name:
        model_search = genai.GenerativeModel(active_model_name, tools='google_search_retrieval')
        print("✅ Search Tool Enabled!")
    else:
        model_search = None
        print("ℹ️ Search Tool Disabled (Model compatibility)")
except:
    model_search = None

# --- 6. HELPER FUNCTIONS ---
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
    import re
    text = text.replace("*", "").replace("#", "")
    return re.sub(r'\[\d+\]', '', text) 

def send_log_to_channel(user, request_type, query, response):
    try:
        if LOG_CHANNEL_ID:
            bot.send_message(
                LOG_CHANNEL_ID, 
                f"📝 **Log** | 👤 {user.first_name}\nType: {request_type}\nQ: {query}\nA: {response}"
            )
    except: pass

def generate_audio(user_id, text, filename):
    if not text: return False
    config = get_user_config(user_id)
    engine = config.get('voice', 'edge') 
    
    if engine == 'edge':
        try:
            command = ["edge-tts", "--voice", EDGE_VOICE_ID, "--text", text, "--write-media", filename]
            subprocess.run(command, check=True)
            return True
        except: pass
    
    try:
        tts = gTTS(text=text, lang='hi', slow=False)
        tts.save(filename)
        return True
    except: return False

def get_settings_markup(user_id):
    config = get_user_config(user_id)
    curr_mode = config['mode']
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    buttons = []
    for m in RAW_MODES.keys():
        text = f"✅ {m.capitalize()}" if m == curr_mode else f"❌ {m.capitalize()}"
        buttons.append(types.InlineKeyboardButton(text, callback_data=f"set_mode_{m}"))
    markup.add(*buttons)
    
    voice_label = "🗣️ Voice: ♂️ Male (Edge)" if config['voice'] == 'edge' else "🗣️ Voice: ♀️ Female (Google)"
    markup.add(types.InlineKeyboardButton(voice_label, callback_data="toggle_voice"))
    mem_status = "✅ Memory ON" if config['memory'] else "❌ Memory OFF"
    markup.add(types.InlineKeyboardButton(mem_status, callback_data="toggle_memory"))
    markup.add(types.InlineKeyboardButton("🗑️ Clear JSON", callback_data="clear_json"))
    return markup

# --- 7. COMMAND HANDLERS ---
@bot.message_handler(commands=['start'])
def send_start(message):
    bot.reply_to(message, "🔥 **Dev Bot Online!**\n\nAb main **Smart Mode** mein hoon.\nTry asking: 'Aaj ki news kya hai?'")

@bot.message_handler(commands=['settings'])
def settings_menu(message):
    markup = get_settings_markup(message.from_user.id)
    bot.reply_to(message, "🎛️ **Control Panel**", reply_markup=markup)

@bot.message_handler(commands=['img'])
def send_image_generation(message):
    prompt = message.text.replace("/img", "").strip()
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

@bot.message_handler(commands=['quiz'])
def handle_quiz(message):
    try:
        if model_basic:
            quiz_game.generate_quiz(bot, message, model_basic)
        else:
            bot.reply_to(message, "❌ AI Model not loaded.")
    except:
        bot.reply_to(message, "❌ Quiz module error.")

# --- 8. CALLBACK HANDLERS ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if call.data.startswith("quiz_"):
        try: quiz_game.check_answer(call, bot)
        except: pass
        return

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

    if needs_refresh:
        try: bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_settings_markup(user_id))
        except: pass

# --- 9. VOICE & WEB HANDLERS ---
@bot.message_handler(content_types=['voice', 'audio'])
def handle_voice_chat(message):
    try:
        user_id = message.from_user.id
        bot.send_chat_action(message.chat.id, 'record_audio')
        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        user_audio_path = f"user_{user_id}.ogg"
        with open(user_audio_path, 'wb') as f: f.write(downloaded_file)

        if model_basic:
            myfile = genai.upload_file(user_audio_path)
            config = get_user_config(user_id)
            prompt = f"Time: {get_current_time()}. Mode: {config['mode']}. Reply short."
            result = model_basic.generate_content([prompt, myfile])
            ai_reply = result.text
            
            reply_audio_path = f"reply_{user_id}.mp3"
            clean_txt = clean_text_for_audio(ai_reply)
            if clean_txt and generate_audio(user_id, clean_txt, reply_audio_path):
                with open(reply_audio_path, 'rb') as f: bot.send_voice(message.chat.id, f)
                os.remove(reply_audio_path)
            else: bot.reply_to(message, ai_reply)
            try: os.remove(user_audio_path)
            except: pass
    except Exception as e: bot.reply_to(message, "❌ Audio Error")

@bot.message_handler(func=lambda m: m.text and ("http://" in m.text or "https://" in m.text))
def handle_links(message):
    try:
        url = message.text.strip()
        bot.send_chat_action(message.chat.id, 'typing')
        content = web_tools.scrape_website(url)
        if content and model_basic:
            response = model_basic.generate_content(f"Summarize this website in Hinglish:\n\n{content}")
            bot.reply_to(message, f"📄 **Summary:**\n\n{response.text}", parse_mode="Markdown")
        else: bot.reply_to(message, "❌ Link read nahi kar paya.")
    except: bot.reply_to(message, "❌ Error reading link.")


# --- 10. TEXT HANDLER (FORCED SEARCH) ---
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    try:
        user_id = message.from_user.id
        user_text = message.text
        if not user_text: return
        
        config = get_user_config(user_id)
        
        # 1. Check Memory (Offline)
        saved_reply = get_reply_from_json(user_text)
        if saved_reply and config['memory']:
            ai_reply = saved_reply
            source = "JSON"
        else:
            # 2. AI Processing
            bot.send_chat_action(message.chat.id, 'typing')
            
            # --- STRONG INSTRUCTION FOR SEARCH ---
            sys_prompt = f"""
            [System]: Today's Date: {get_current_time()}.
            [TOOLS]: You have access to Google Search.
            [INSTRUCTION]: If the user asks for Real-time info (News, Prices, Weather, Scores), YOU MUST USE THE SEARCH TOOL. Do not say "I cannot". Search and answer.
            [PERSONA]: {RAW_MODES.get(config['mode'])}
            """
            
            chat_history = config['history'] if config['memory'] else []
            full_prompt = f"{sys_prompt}\n\nChat History: {chat_history}\n\nUser: {user_text}"

            # HYBRID LOGIC
            try:
                # Trigger words jo search force karenge
                triggers = ["news", "rate", "price", "bhav", "weather", "mausam", "score", "match", "kab", "kahan", "kaun"]
                force_search = any(x in user_text.lower() for x in triggers)

                if model_search and force_search:
                    print(f"🔎 Force Searching for: {user_text}")
                    response = model_search.generate_content(full_prompt)
                    ai_reply = response.text
                elif model_basic:
                    response = model_basic.generate_content(full_prompt)
                    ai_reply = response.text
                else:
                    ai_reply = "❌ AI System Down. No models available."
            except Exception as e:
                # Fallback to basic model
                if model_basic:
                    try:
                        response = model_basic.generate_content(full_prompt)
                        ai_reply = response.text
                    except Exception as e2:
                        ai_reply = f"⚠️ Critical AI Error: {e2}"
                else:
                    ai_reply = f"⚠️ AI Error: {e}"

            source = "AI"
            
            if "Error" not in ai_reply:
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

    except Exception as e:
        bot.reply_to(message, f"❌ Bot Error: {e}")

# --- 11. RUN (AUTO RESTART) ---
@app.route('/')
def home(): return "✅ Dev Bot is Live!", 200

def run_bot():
    print("🤖 Bot Started with UNIVERSAL MODEL LOADER...")
    while True:
        try:
            bot.infinity_polling(timeout=90, long_polling_timeout=90)
        except Exception as e:
            print(f"⚠️ Reconnecting: {e}")
            time.sleep(5)

if __name__ == "__main__":
    t = threading.Thread(target=run_bot)
    t.start()
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
