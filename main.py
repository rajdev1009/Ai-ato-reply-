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
# Quiz State ab advance ho gaya hai
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

# --- 5. UNIVERSAL MODEL LOADER (FIXED SEARCH ERROR) ---
genai.configure(api_key=API_KEY)

def get_working_model():
    print("🔄 Loading AI Models...")
    try:
        my_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                my_models.append(m.name)
        
        # Priority order
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
        # FIX: 'google_search_retrieval' ki jagah simple 'google_search'
        model_search = genai.GenerativeModel(active_model_name, tools='google_search')
        print("✅ Search Tool Fixed & Enabled!")
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

# --- 7. QUIZ SYSTEM (LEVELS + EMOTIONS) ---

def ask_quiz_level(message, topic):
    # User se Level puchne ke liye buttons
    markup = types.InlineKeyboardMarkup(row_width=2)
    levels = [
        ("Basic Level", "Basic"), 
        ("Junior (9-10)", "Class 9-10"),
        ("Senior (11-12)", "Class 11-12"),
        ("Science", "Science Stream"),
        ("Commerce", "Commerce Stream"),
        ("Arts", "Arts Stream"),
        ("🔥 Pro Level", "Expert")
    ]
    
    for label, code in levels:
        markup.add(types.InlineKeyboardButton(label, callback_data=f"qlvl_{code}"))
    
    # Topic ko temporarily save kar lo
    quiz_sessions[message.from_user.id] = {'pending_topic': topic}
    bot.reply_to(message, f"📚 **Topic: {topic}**\n\nApna Level select karein:", reply_markup=markup)

def start_quiz_loop(user_id, chat_id, topic, level):
    # Initialize Session
    quiz_sessions[user_id] = {
        'active': True, 
        'topic': topic, 
        'level': level,
        'score': 0,
        'total': 0,
        'wrong': 0
    }
    send_new_question(user_id, chat_id)

def send_new_question(user_id, chat_id):
    if user_id not in quiz_sessions or not quiz_sessions[user_id]['active']:
        return

    session = quiz_sessions[user_id]
    topic = session['topic']
    level = session['level']
    
    bot.send_chat_action(chat_id, 'typing')

    prompt = f"""
    Create a {level} level MCQ Question about '{topic}'.
    Reply ONLY in JSON:
    {{
        "q": "Question text?",
        "o": ["Option 1", "Option 2", "Option 3", "Option 4"],
        "a": 0,
        "exp": "Short explanation in Hinglish"
    }}
    Index 'a' is 0, 1, 2, or 3.
    """
    
    try:
        response = model_basic.generate_content(prompt)
        text = response.text.strip().replace("```json", "").replace("```", "")
        data = json.loads(text)
        
        # Save Question Data
        quiz_sessions[user_id]['correct_idx'] = data['a']
        quiz_sessions[user_id]['explanation'] = data['exp']
        quiz_sessions[user_id]['question_text'] = data['q']

        # UI FIX: Text message mein rahega, buttons chote rahenge
        labels = ["A", "B", "C", "D"]
        options_text = ""
        for i, opt in enumerate(data['o']):
            options_text += f"**{labels[i]})** {opt}\n"

        full_msg = f"🎮 **Quiz: {topic}** | 📊 {level}\n\n❓ **{data['q']}**\n\n{options_text}\n👇 *Sahi option chuno:*"

        # Buttons A, B, C, D
        markup = types.InlineKeyboardMarkup(row_width=4)
        btns = []
        for i in range(len(data['o'])):
            btns.append(types.InlineKeyboardButton(f" {labels[i]} ", callback_data=f"qz_ans_{i}"))
        markup.add(*btns)
        
        # Control Buttons
        markup.add(types.InlineKeyboardButton("🔊 Suno", callback_data="qz_speak"), 
                   types.InlineKeyboardButton("❌ Radd Karo (Result)", callback_data="qz_stop"))

        msg = bot.send_message(chat_id, full_msg, reply_markup=markup, parse_mode="Markdown")
        quiz_sessions[user_id]['msg_id'] = msg.message_id
        
    except Exception as e:
        time.sleep(1)
        send_new_question(user_id, chat_id)

# --- 8. COMMAND HANDLERS ---

@bot.message_handler(commands=['raj'])
def send_welcome(message):
    bot.reply_to(message, "🔥 **Dev Bot Online!**\n\nNaye Quiz Feature ke saath!\nUse `/help` to see commands.")

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = """
🤖 **Dev Bot Commands List:**

1️⃣ **/raj** - Check Bot Status.
2️⃣ **/quiz [topic]** - Start Level-wise Quiz.
   *(Eg: /quiz history, /quiz math)*
3️⃣ **/img [prompt]** - Generate Images.
4️⃣ **/settings** - Change Mode/Clear Memory.

💡 **Smart Features:**
- Ask "News", "Price" for 2025 Info.
- Quiz mein ab **Levels** aur **Scoreboard** hai!
    """
    bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['settings'])
def settings_menu(message):
    bot.reply_to(message, "🎛️ **Settings**", reply_markup=get_settings_markup(message.from_user.id))

@bot.message_handler(commands=['img'])
def send_image(message):
    prompt = message.text.replace("/img", "").strip()
    if not prompt: return bot.reply_to(message, "Likho: `/img car`")
    bot.send_chat_action(message.chat.id, 'upload_photo')
    try:
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?nologo=true"
        bot.send_photo(message.chat.id, url, caption=f"🖼️ {prompt}")
    except: bot.reply_to(message, "❌ Error.")

@bot.message_handler(commands=['quiz'])
def handle_quiz_command(message):
    topic = message.text.replace("/quiz", "").strip()
    if not topic: topic = "General Knowledge"
    
    # Pehle Level Pucho
    ask_quiz_level(message, topic)

# --- 9. CALLBACKS (LOGIC HUB) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    
    # --- LEVEL SELECTION ---
    if call.data.startswith("qlvl_"):
        if user_id not in quiz_sessions or 'pending_topic' not in quiz_sessions[user_id]:
            bot.answer_callback_query(call.id, "Session Expired. Type /quiz again.")
            return
        
        selected_level = call.data.split("_")[1]
        topic = quiz_sessions[user_id]['pending_topic']
        
        bot.edit_message_text(f"🚀 **Starting {selected_level} Quiz on {topic}...**", 
                              call.message.chat.id, call.message.message_id)
        
        start_quiz_loop(user_id, call.message.chat.id, topic, selected_level)
        return

    # --- QUIZ GAMEPLAY ---
    if call.data.startswith("qz_"):
        if user_id not in quiz_sessions or not quiz_sessions[user_id]['active']:
            bot.answer_callback_query(call.id, "Quiz Khatam.")
            return
        
        session = quiz_sessions[user_id]
        
        # STOP & SCOREBOARD LOGIC
        if call.data == "qz_stop":
            quiz_sessions[user_id]['active'] = False
            
            score = session['score']
            total = session['total']
            wrong = session['wrong']
            
            # Percentage Calculation
            if total > 0:
                percent = int((score / total) * 100)
            else:
                percent = 0
            
            # Emotional Response Logic
            if percent >= 90:
                emote = "🏆 **Kya baat hai! Tum to Genius ho!** 🎉"
            elif percent >= 70:
                emote = "😎 **Bahut badhiya khela! Keep it up!**"
            elif percent >= 40:
                emote = "🙂 **Nice try! Thodi aur mehnat aur tum Pro ban jaoge.**"
            else:
                emote = "🥺 **Koi baat nahi dost! Gir kar hi log seekhte hain. Agli baar pakka phod denge!** ❤️"

            report = f"""
🛑 **Quiz Radd Kar Diya!**

📊 **Final Scoreboard:**
✅ Sahi: {score}
❌ Galat: {wrong}
total: {total}
📉 Percentage: **{percent}%**

{emote}
            """
            bot.edit_message_text(report, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            return

        if call.data == "qz_speak":
            bot.answer_callback_query(call.id, "🔊...")
            fname = f"q_{user_id}.mp3"
            if generate_audio(user_id, session['question_text'], fname):
                with open(fname, "rb") as f: bot.send_voice(call.message.chat.id, f)
                os.remove(fname)
            return

        # ANSWER CHECKING
        if call.data.startswith("qz_ans_"):
            selected = int(call.data.split("_")[2])
            labels = ["A", "B", "C", "D"]
            
            session['total'] += 1
            
            if selected == session['correct_idx']:
                session['score'] += 1
                result = f"✅ **Sahi Jawab!** (Ans: {labels[session['correct_idx']]})"
            else:
                session['wrong'] += 1
                result = f"❌ **Galat!** Sahi tha: {labels[session['correct_idx']]}"

            bot.edit_message_text(f"{result}\n💡 {session['explanation']}\n\n⏳ **Agla sawal...**", 
                                  call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            time.sleep(2)
            if quiz_sessions[user_id]['active']:
                send_new_question(user_id, call.message.chat.id)
        return

    # --- SETTINGS ---
    if call.data == "clear_json":
        if user_id == OWNER_ID:
            with open(JSON_FILE, "w", encoding="utf-8") as f: json.dump({}, f)
            bot.answer_callback_query(call.id, "Memory Cleared!")
        else: bot.answer_callback_query(call.id, "Admin Only!")
    
    elif call.data == "speak_msg":
        bot.answer_callback_query(call.id, "🔊...")
        generate_audio(user_id, call.message.text, "tts.mp3")
        with open("tts.mp3", "rb") as f: bot.send_voice(call.message.chat.id, f)

# --- 10. TEXT HANDLER ---
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    try:
        user_id = message.from_user.id
        if user_id in quiz_sessions and quiz_sessions[user_id].get('active'): return

        user_text = message.text
        if not user_text: return
        
        config = get_user_config(user_id)
        
        triggers = ["news", "rate", "price", "weather", "who", "what", "where", "kab", "kahan", "kaise", "president", "winner", "live"]
        force_search = any(x in user_text.lower() for x in triggers)

        saved_reply = get_reply_from_json(user_text)
        
        if saved_reply and config['memory'] and not force_search:
            ai_reply = saved_reply
            source = "JSON"
        else:
            bot.send_chat_action(message.chat.id, 'typing')
            sys_prompt = f"[System]: Date: {get_current_time()}. Era: Late 2025. USE SEARCH for facts. Persona: {RAW_MODES.get(config['mode'])}"
            
            try:
                if model_search and force_search:
                    response = model_search.generate_content(f"{sys_prompt}\nUser: {user_text}")
                elif model_basic:
                    response = model_basic.generate_content(f"{sys_prompt}\nUser: {user_text}")
                else: response = None
                
                ai_reply = response.text if response else "❌ Error."
            except Exception as e: ai_reply = f"⚠️ {e}"

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
                    
