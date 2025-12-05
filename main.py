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
except ImportError:
    pass

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
# Quiz State: {user_id: {'active': True, 'topic': 'GK', 'score': 0, 'last_msg': 123}}
quiz_sessions = {} 
EDGE_VOICE_ID = "hi-IN-MadhurNeural" 

# --- 3. TIME ---
def get_current_time():
    IST = pytz.timezone('Asia/Kolkata')
    now = datetime.now(IST)
    return now.strftime("%d %B %Y, %I:%M %p")

# --- 4. MODES & PROMPTS ---
SECURITY_RULE = """
SYSTEM RULES:
1. Current Date: December 2025.
2. US President: Donald Trump.
3. Name: 'Dev'. Creator: Raj Dev.
"""

RAW_MODES = {
    "friendly": f"Friendly & Cool. Hinglish. {SECURITY_RULE}",
    "study": f"Strict Teacher. No nonsense. {SECURITY_RULE}",
    "funny": f"Comedian. Jokes everywhere. {SECURITY_RULE}",
    "gk": f"GK Expert. Factual. {SECURITY_RULE}",
}

# --- 5. UNIVERSAL MODEL LOADER ---
genai.configure(api_key=API_KEY)

def get_working_model():
    print("🔄 Loading AI Models...")
    try:
        my_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                my_models.append(m.name)
        
        preferences = ['models/gemini-2.5-flash', 'models/gemini-1.5-flash', 'models/gemini-pro']
        selected_model = my_models[0] if my_models else None
        
        for pref in preferences:
            if pref in my_models:
                selected_model = pref
                break
        
        print(f"✅ Selected: {selected_model}")
        return genai.GenerativeModel(selected_model), selected_model
    except: return None, None

model_basic, active_model_name = get_working_model()

try:
    if active_model_name and "flash" in active_model_name:
        model_search = genai.GenerativeModel(active_model_name, tools='google_search_retrieval')
    else: model_search = None
except: model_search = None

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

def generate_audio(user_id, text, filename):
    if not text: return False
    config = get_user_config(user_id)
    
    try:
        command = ["edge-tts", "--voice", EDGE_VOICE_ID, "--text", text, "--write-media", filename]
        subprocess.run(command, check=True)
        return True
    except:
        try:
            tts = gTTS(text=text, lang='hi', slow=False)
            tts.save(filename)
            return True
        except: return False

def get_settings_markup(user_id):
    config = get_user_config(user_id)
    markup = types.InlineKeyboardMarkup(row_width=2)
    for m in RAW_MODES.keys():
        text = f"✅ {m.capitalize()}" if m == config['mode'] else f"❌ {m.capitalize()}"
        markup.add(types.InlineKeyboardButton(text, callback_data=f"set_mode_{m}"))
    markup.add(types.InlineKeyboardButton("🗑️ Clear Memory", callback_data="clear_json"))
    return markup

# --- 7. QUIZ SYSTEM (NON-STOP LOOP) ---
def start_quiz_loop(user_id, chat_id, topic="General Knowledge"):
    # Set Session
    quiz_sessions[user_id] = {'active': True, 'topic': topic, 'score': 0}
    send_new_question(user_id, chat_id)

def send_new_question(user_id, chat_id):
    if user_id not in quiz_sessions or not quiz_sessions[user_id]['active']:
        return

    topic = quiz_sessions[user_id]['topic']
    bot.send_chat_action(chat_id, 'typing')

    prompt = f"""
    Create a unique MCQ Quiz question about '{topic}'.
    Reply ONLY in JSON format:
    {{
        "q": "Question text?",
        "o": ["Option A", "Option B", "Option C", "Option D"],
        "a": 0,
        "exp": "Explanation in Hinglish"
    }}
    Index 'a' is 0,1,2, or 3.
    """
    
    try:
        response = model_basic.generate_content(prompt)
        text = response.text.strip().replace("```json", "").replace("```", "")
        data = json.loads(text)
        
        # Save Correct Answer in Session
        quiz_sessions[user_id]['correct_idx'] = data['a']
        quiz_sessions[user_id]['explanation'] = data['exp']
        quiz_sessions[user_id]['question_text'] = data['q']

        markup = types.InlineKeyboardMarkup(row_width=2)
        btns = []
        for i, opt in enumerate(data['o']):
            btns.append(types.InlineKeyboardButton(opt, callback_data=f"qz_ans_{i}"))
        markup.add(*btns)
        
        # Stop & Speak Buttons
        markup.add(types.InlineKeyboardButton("🔊 Suno", callback_data="qz_speak"), 
                   types.InlineKeyboardButton("❌ Radd Karo (Stop)", callback_data="qz_stop"))

        msg = bot.send_message(chat_id, f"🎮 **Quiz Mode: On**\n\n❓ {data['q']}", reply_markup=markup)
        quiz_sessions[user_id]['msg_id'] = msg.message_id
        
    except Exception as e:
        bot.send_message(chat_id, "⚠️ Error generating question. Retrying...")
        time.sleep(1)
        send_new_question(user_id, chat_id)

# --- 8. COMMAND HANDLERS ---

# CHANGED: /start -> /raj
@bot.message_handler(commands=['raj'])
def send_welcome(message):
    bot.reply_to(message, "🔥 **Dev Bot Online!**\n\nCommands:\n• /quiz [topic] - Non-stop Quiz\n• /settings - Control Panel\n• /img [prompt] - Generate Image\n• Ask any question for 2025 Info!")

@bot.message_handler(commands=['settings'])
def settings_menu(message):
    bot.reply_to(message, "🎛️ **Settings**", reply_markup=get_settings_markup(message.from_user.id))

@bot.message_handler(commands=['img'])
def send_image(message):
    prompt = message.text.replace("/img", "").strip()
    if not prompt: return bot.reply_to(message, "Likho: `/img cat`")
    bot.send_chat_action(message.chat.id, 'upload_photo')
    try:
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?nologo=true"
        bot.send_photo(message.chat.id, url, caption=f"🖼️ {prompt}")
    except: bot.reply_to(message, "❌ Error.")

@bot.message_handler(commands=['quiz'])
def handle_quiz_command(message):
    topic = message.text.replace("/quiz", "").strip()
    if not topic: topic = "General Knowledge"
    
    # Check if already active
    if message.from_user.id in quiz_sessions and quiz_sessions[message.from_user.id]['active']:
        bot.reply_to(message, "⚠️ Quiz already chal raha hai! Stop karne ke liye button dabao.")
    else:
        bot.reply_to(message, f"🚀 **Starting Non-stop Quiz: {topic}**\nRukne ke liye 'Radd Karo' dabana.")
        start_quiz_loop(message.from_user.id, message.chat.id, topic)

# --- 9. CALLBACK HANDLER (QUIZ + SETTINGS) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    
    # --- QUIZ LOGIC ---
    if call.data.startswith("qz_"):
        if user_id not in quiz_sessions or not quiz_sessions[user_id]['active']:
            bot.answer_callback_query(call.id, "⚠️ Session Expired.")
            return

        session = quiz_sessions[user_id]
        
        if call.data == "qz_stop":
            quiz_sessions[user_id]['active'] = False
            bot.edit_message_text(f"🛑 **Quiz Radd Kar Diya!**\n🏆 Final Score: {session['score']}", 
                                  call.message.chat.id, call.message.message_id)
            return

        if call.data == "qz_speak":
            bot.answer_callback_query(call.id, "🔊 Bol raha hoon...")
            fname = f"q_{user_id}.mp3"
            if generate_audio(user_id, session['question_text'], fname):
                with open(fname, "rb") as f: bot.send_voice(call.message.chat.id, f)
                os.remove(fname)
            return

        if call.data.startswith("qz_ans_"):
            selected = int(call.data.split("_")[2])
            correct = session['correct_idx']
            
            if selected == correct:
                session['score'] += 1
                result = "✅ Sahi Jawab!"
            else:
                result = "❌ Galat Jawab!"

            # Show Result & Explanation
            new_text = f"{call.message.text}\n\n{result}\n💡 {session['explanation']}\n\n⏳ **Agla sawal aa raha hai...**"
            bot.edit_message_text(new_text, call.message.chat.id, call.message.message_id)
            
            # Wait 2 seconds and Next Question (LOOP)
            time.sleep(2)
            if quiz_sessions[user_id]['active']:
                send_new_question(user_id, call.message.chat.id)
        return

    # --- SETTINGS LOGIC ---
    if call.data == "clear_json":
        if user_id == OWNER_ID:
            with open(JSON_FILE, "w", encoding="utf-8") as f: json.dump({}, f)
            bot.answer_callback_query(call.id, "Cleared!")
        else: bot.answer_callback_query(call.id, "Admin Only!")
    
    elif call.data == "speak_msg":
        # Normal chat speak button
        bot.answer_callback_query(call.id, "🔊...")
        generate_audio(user_id, call.message.text, "tts.mp3")
        with open("tts.mp3", "rb") as f: bot.send_voice(call.message.chat.id, f)

# --- 10. TEXT HANDLER (SMART 2025 MODE) ---
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    try:
        user_id = message.from_user.id
        
        # Agar Quiz Mode ON hai, toh text ignore karo (taaki quiz beech mein na toote)
        if user_id in quiz_sessions and quiz_sessions[user_id]['active']:
            return

        user_text = message.text
        if not user_text: return
        
        config = get_user_config(user_id)
        
        # Trigger List for Search
        triggers = ["news", "rate", "price", "weather", "who", "what", "where", "kab", "kahan", "kaise", "president", "winner"]
        force_search = any(x in user_text.lower() for x in triggers)

        saved_reply = get_reply_from_json(user_text)
        
        if saved_reply and config['memory'] and not force_search:
            ai_reply = saved_reply
            source = "JSON"
        else:
            bot.send_chat_action(message.chat.id, 'typing')
            
            sys_prompt = f"""
            [System]: Date: {get_current_time()}. Era: Late 2025.
            [INSTRUCTION]: USE GOOGLE SEARCH for facts.
            [Persona]: {RAW_MODES.get(config['mode'])}
            """
            
            try:
                if model_search and force_search:
                    response = model_search.generate_content(f"{sys_prompt}\nUser: {user_text}")
                    ai_reply = response.text
                elif model_basic:
                    response = model_basic.generate_content(f"{sys_prompt}\nUser: {user_text}")
                    ai_reply = response.text
                else: ai_reply = "❌ Error."
            except Exception as e: ai_reply = f"⚠️ Error: {e}"

            source = "AI"
            if "Error" not in ai_reply: save_to_json(user_text, ai_reply)

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔊 Suno", callback_data="speak_msg"))
        bot.reply_to(message, ai_reply, reply_markup=markup)
        
    except Exception as e: print(e)

# --- 11. RUN ---
@app.route('/')
def home(): return "✅ Bot Live", 200

def run_bot():
    print("🤖 Bot Started...")
    while True:
        try: bot.infinity_polling(timeout=90, long_polling_timeout=90)
        except: time.sleep(5)

if __name__ == "__main__":
    t = threading.Thread(target=run_bot)
    t.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
