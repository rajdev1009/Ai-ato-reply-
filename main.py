import os
import telebot
from telebot import types 
import google.generativeai as genai
from flask import Flask
from dotenv import load_dotenv
import threading
import json 
import time
import urllib.parse
from datetime import datetime
import pytz 

# 👇 Voice Logic Import kar rahe hain doosri file se
from voice_service import generate_audio_file

# --- 1. CONFIGURATION ---
load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OWNER_ID = 5804953849  
LOG_CHANNEL_ID = -1003448442249 

# --- 2. SETUP ---
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

JSON_FILE = "reply.json"
if not os.path.exists(JSON_FILE):
    with open(JSON_FILE, "w", encoding="utf-8") as f: json.dump({}, f)

user_data = {} 

# --- 3. HELPER FUNCTIONS ---
def get_current_time():
    IST = pytz.timezone('Asia/Kolkata')
    return datetime.now(IST).strftime("%d %B %Y, %I:%M %p")

def clean_text_for_audio(text):
    if not text: return ""
    if "Error" in text or "Quota" in text: return None
    import re
    # Remove markdown & citations [1]
    text = re.sub(r'[*_`#]', '', text)
    return re.sub(r'\[\d+\]', '', text)

def get_user_config(user_id):
    if user_id not in user_data:
        # Default voice 'edge' (Male) set hai
        user_data[user_id] = {"mode": "friendly", "memory": True, "voice": "edge", "history": []}
    return user_data[user_id]

# --- 4. MODES & PROMPTS ---
RAW_MODES = {
    "friendly": "Tumhara naam Dev hai. Style: Cool, Hinglish. Don't mention AI/Google.",
    "study": "Tum Strict Teacher ho. Only study related talks.",
    "funny": "Tum Comedian ho. Har baat pe joke maaro.",
    "roast": "Tum Roaster ho. User ki halki bezzati karo.",
    "romantic": "Tum Flirty ho. Pyaar se baat karo.",
    "gk": "Tum GK Expert ho. Factual answers only."
}

# --- 5. AI MODELS ---
model_search = None
model_basic = None

if API_KEY:
    genai.configure(api_key=API_KEY)
    try:
        model_basic = genai.GenerativeModel('gemini-2.0-flash')
        print("✅ Basic Model Ready")
    except: pass

    try:
        tool_config = {"google_search_retrieval": {"dynamic_retrieval_config": {"mode": "dynamic", "dynamic_threshold": 0.6}}}
        model_search = genai.GenerativeModel('gemini-2.0-flash', tools=[tool_config])
        print("✅ Search Model Ready")
    except: pass

# --- 6. ROUTES & COMMANDS ---
@app.route('/')
def home(): return "✅ Bot is Running", 200

@bot.message_handler(commands=['start'])
def start_msg(message):
    bot.reply_to(message, "🔥 **Dev Online!**\nBol bhai kya haal hai? 😎")

@bot.message_handler(commands=['settings'])
def settings_msg(message):
    uid = message.from_user.id
    conf = get_user_config(uid)
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Mode Buttons
    btns = [types.InlineKeyboardButton(f"{'✅' if m==conf['mode'] else '❌'} {m.capitalize()}", callback_data=f"mode_{m}") for m in RAW_MODES]
    markup.add(*btns)
    
    # Voice & Memory Buttons
    v_txt = "🗣️ Voice: ♂️ Male" if conf['voice'] == 'edge' else "🗣️ Voice: ♀️ Female"
    m_txt = "🧠 Memory: ON" if conf['memory'] else "🧠 Memory: OFF"
    markup.add(types.InlineKeyboardButton(v_txt, callback_data="tog_voice"), types.InlineKeyboardButton(m_txt, callback_data="tog_mem"))
    markup.add(types.InlineKeyboardButton("🗑️ Clear Data", callback_data="clr_json"))
    
    bot.reply_to(message, "⚙️ **Settings Panel**", reply_markup=markup)

@bot.message_handler(commands=['img'])
def gen_image(message):
    prompt = message.text.replace("/img", "").strip()
    if not prompt: return bot.reply_to(message, "Likho: `/img cat in space`")
    try:
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?nologo=true"
        bot.send_photo(message.chat.id, url, caption=f"🎨 {prompt}")
    except: bot.reply_to(message, "❌ Image Failed")

# --- 7. CALLBACKS ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = call.from_user.id
    conf = get_user_config(uid)
    data = call.data

    if data.startswith("mode_"):
        conf['mode'] = data.split("_")[1]
        conf['history'] = []
        bot.answer_callback_query(call.id, f"Mode: {conf['mode']}")
        settings_msg(call.message) # Refresh UI

    elif data == "tog_voice":
        conf['voice'] = 'google' if conf['voice'] == 'edge' else 'edge'
        bot.answer_callback_query(call.id, "Voice Switched!")
        settings_msg(call.message)

    elif data == "speak_msg":
        bot.answer_callback_query(call.id, "🎤 Processing...")
        bot.send_chat_action(call.message.chat.id, 'record_audio')
        
        # 👇 Using separate file function
        fname = f"tts_{uid}.mp3"
        txt = clean_text_for_audio(call.message.text)
        
        if generate_audio_file(txt, fname, conf['voice']):
            with open(fname, "rb") as f: bot.send_voice(call.message.chat.id, f)
            os.remove(fname)
        else:
            bot.send_message(call.message.chat.id, "❌ Audio Failed")

# --- 8. VOICE & TEXT CHAT ---
@bot.message_handler(content_types=['voice', 'audio'])
def voice_chat(message):
    uid = message.from_user.id
    bot.send_chat_action(message.chat.id, 'record_audio')
    
    # 1. Save User Voice
    finfo = bot.get_file(message.voice.file_id)
    dl = bot.download_file(finfo.file_path)
    user_aud = f"user_{uid}.ogg"
    with open(user_aud, 'wb') as f: f.write(dl)

    # 2. Process with AI
    reply_txt = "Samajh nahi aaya."
    try:
        model = model_search if model_search else model_basic
        if model:
            up_file = genai.upload_file(user_aud)
            prompt = f"System: Mode={get_user_config(uid)['mode']}. Reply naturally in Hindi/Hinglish."
            reply_txt = model.generate_content([prompt, up_file]).text
    except Exception as e: reply_txt = f"Error: {e}"
    
    os.remove(user_aud)

    # 3. Generate Reply Audio (Using Separate File)
    fname = f"reply_{uid}.mp3"
    cln_txt = clean_text_for_audio(reply_txt)
    conf = get_user_config(uid)
    
    if generate_audio_file(cln_txt, fname, conf['voice']):
        with open(fname, 'rb') as f: bot.send_voice(message.chat.id, f)
        os.remove(fname)
    else:
        bot.reply_to(message, reply_txt)

@bot.message_handler(func=lambda m: True)
def text_chat(message):
    uid = message.from_user.id
    txt = message.text
    conf = get_user_config(uid)
    
    # AI Logic (Simplified)
    bot.send_chat_action(message.chat.id, 'typing')
    sys_p = f"System: Time={get_current_time()}. Rules: {RAW_MODES[conf['mode']]}"
    
    reply = "System Busy."
    try:
        model = model_search if model_search else model_basic
        chat = model.start_chat(history=conf['history'] if conf['memory'] else [])
        reply = chat.send_message(f"{sys_p}\nUser: {txt}").text
    except: pass
    
    # Memory Update
    if conf['memory']:
        conf['history'].append({'role':'user','parts':[txt]})
        conf['history'].append({'role':'model','parts':[reply]})

    # Reply with Speak Button
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔊 Suno", callback_data="speak_msg"))
    bot.reply_to(message, reply, reply_markup=kb)

# --- RUN ---
if __name__ == "__main__":
    t = threading.Thread(target=bot.infinity_polling)
    t.start()
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
        
