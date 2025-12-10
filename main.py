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
import re 

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

try:
    LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
except:
    LOG_CHANNEL_ID = None

if not API_KEY or not BOT_TOKEN:
    print("⚠️ Warning: Keys missing in .env file!")

# --- 2. SETUP ---
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

JSON_FILE = "reply.json"
if not os.path.exists(JSON_FILE):
    with open(JSON_FILE, "w", encoding="utf-8") as f: json.dump({}, f)

user_data = {} 
quiz_sessions = {} 
quiz_timers = {} 
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
4. LOCATION: Lumding (Assam).
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
    fallback_model = "gemini-1.5-flash"
    try:
        my_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                my_models.append(m.name)
        
        preferences = ['models/gemini-2.5-flash', 'models/gemini-1.5-flash', 'models/gemini-pro']
        selected_model = fallback_model
        
        if my_models:
            for pref in preferences:
                if pref in my_models:
                    selected_model = pref
                    break
        
        print(f"✅ Selected: {selected_model}")
        return genai.GenerativeModel(selected_model), selected_model

    except Exception as e:
        print(f"⚠️ Model List Error: {e}")
        return genai.GenerativeModel(fallback_model), fallback_model

model_basic, active_model_name = get_working_model()

try:
    if active_model_name and "flash" in active_model_name:
        model_search = genai.GenerativeModel(active_model_name, tools='google_search')
        print("✅ Search Tool Enabled!")
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

def clean_markdown(text):
    if not text: return ""
    return text.replace("*", "").replace("_", "").replace("`", "").replace("[", "").replace("]", "")

def clean_text_for_audio(text):
    if not text: return ""
    return clean_markdown(text)

def generate_audio(user_id, text, filename):
    if not text or len(text.strip()) == 0: return False
    try:
        command = ["edge-tts", "--voice", EDGE_VOICE_ID, "--text", text, "--write-media", filename]
        subprocess.run(command, check=True, timeout=15) 
        return True
    except Exception as e:
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

def send_log_to_channel(user, request_type, query, response):
    if not LOG_CHANNEL_ID: return
    def _log():
        try:
            clean_response = clean_markdown(response[:200]) + "..." if len(response) > 200 else clean_markdown(response)
            log_text = (
                f"📝 NEW LOG\n"
                f"User: {user.first_name} (ID: {user.id})\n"
                f"Type: {request_type}\n"
                f"Input: {query}\n"
                f"Reply: {clean_response}"
            )
            bot.send_message(LOG_CHANNEL_ID, log_text) 
        except Exception as e:
            print(f"Log Failed: {e}")
    threading.Thread(target=_log).start()

# --- 7. QUIZ SYSTEM ---

def ask_quiz_level(message, topic):
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
    
    quiz_sessions[message.from_user.id] = {'pending_topic': topic}
    bot.reply_to(message, f"📚 **Topic: {topic}**\n\nApna Level select karein:", reply_markup=markup)

def ask_quiz_timer(message):
    markup = types.InlineKeyboardMarkup(row_width=3)
    times = [("🚀 10s", "10"), ("⚡ 15s", "15"), ("⏱️ 30s", "30"), ("⏳ 45s", "45"), ("🐢 1 Min", "60")]
    for label, sec in times:
        markup.add(types.InlineKeyboardButton(label, callback_data=f"qtime_{sec}"))
    bot.edit_message_text("⏱️ **Select Timer:**", message.chat.id, message.message_id, reply_markup=markup, parse_mode="Markdown")

def start_quiz_loop(user_id, chat_id, topic, level, time_limit):
    quiz_sessions[user_id] = {
        'active': True, 'topic': topic, 'level': level, 'time_limit': int(time_limit),
        'score': 0, 'total': 0, 'wrong': 0
    }
    send_new_question(user_id, chat_id)

def quiz_timeout_handler(user_id, chat_id, msg_id):
    if user_id in quiz_sessions and quiz_sessions[user_id].get('active'):
        if quiz_sessions[user_id].get('msg_id') == msg_id:
            try:
                bot.edit_message_text("⏰ **Time Up!** ⌛\nYe galat mana jayega.", chat_id, msg_id, parse_mode="Markdown")
                quiz_sessions[user_id]['total'] += 1
                quiz_sessions[user_id]['wrong'] += 1
                time.sleep(2)
                send_new_question(user_id, chat_id)
            except: pass

def send_new_question(user_id, chat_id):
    if user_id not in quiz_sessions or not quiz_sessions[user_id].get('active'): return
    if not model_basic:
        bot.send_message(chat_id, "⚠️ AI Model Connect Nahi Hua.")
        return

    session = quiz_sessions[user_id]
    time_limit = session.get('time_limit', 15)
    
    bot.send_chat_action(chat_id, 'typing')

    prompt = f"""
    Create a {session['level']} level MCQ Question about '{session['topic']}'.
    Reply ONLY in JSON:
    {{
        "q": "Question text?",
        "o": ["Option 1", "Option 2", "Option 3", "Option 4"],
        "a": 0,
        "exp": "Short explanation"
    }}
    Index 'a' is 0-3. NO MARKDOWN.
    """
    
    try:
        response = model_basic.generate_content(prompt)
        text = response.text.strip().replace("```json", "").replace("```", "")
        data = json.loads(text)
        
        safe_q = clean_markdown(data['q'])
        safe_opts = [clean_markdown(o) for o in data['o']]
        
        quiz_sessions[user_id]['correct_idx'] = data['a']
        quiz_sessions[user_id]['explanation'] = clean_markdown(data.get('exp', ''))
        quiz_sessions[user_id]['question_text'] = safe_q
        quiz_sessions[user_id]['options'] = safe_opts

        labels = ["A", "B", "C", "D"]
        options_text = ""
        for i, opt in enumerate(safe_opts):
            options_text += f"**{labels[i]})** {opt}\n"

        full_msg = f"🎮 **Quiz: {session['topic']}**\n⏳ **{time_limit} Seconds**\n\n❓ **{safe_q}**\n\n{options_text}\n👇 *Jaldi Jawab Do!*"

        markup = types.InlineKeyboardMarkup(row_width=4)
        btns = []
        for i in range(len(safe_opts)):
            btns.append(types.InlineKeyboardButton(f" {labels[i]} ", callback_data=f"qz_ans_{i}"))
        markup.add(*btns)
        markup.add(types.InlineKeyboardButton("🔊 Suno", callback_data="qz_speak"), 
                   types.InlineKeyboardButton("❌ Stop", callback_data="qz_stop"))

        try:
            msg = bot.send_message(chat_id, full_msg, reply_markup=markup, parse_mode="Markdown")
        except:
            msg = bot.send_message(chat_id, full_msg.replace("*", ""), reply_markup=markup)

        quiz_sessions[user_id]['msg_id'] = msg.message_id
        
        timer = threading.Timer(float(time_limit), quiz_timeout_handler, args=[user_id, chat_id, msg.message_id])
        quiz_timers[user_id] = timer
        timer.start()
        
    except Exception as e:
        print(f"Quiz Error: {e}")
        try:
            bot.send_message(chat_id, "⚠️ Retrying...")
            time.sleep(2)
            send_new_question(user_id, chat_id)
        except: quiz_sessions[user_id]['active'] = False

# --- 8. COMMAND HANDLERS ---

@bot.message_handler(commands=['raj'])
def send_welcome(message):
    bot.reply_to(message, "🔥 **Dev Bot Online!**\n\n✅ Voice Forwarding Active\n✅ Logs Active\n✅ Quiz Timer Active")
    send_log_to_channel(message.from_user, "COMMAND", "/raj", "Bot Status Checked")

@bot.message_handler(commands=['debug'])
def debug_bot(message):
    try:
        if LOG_CHANNEL_ID:
            bot.send_message(LOG_CHANNEL_ID, "✅ **Test Log from Dev Bot**")
            bot.reply_to(message, f"✅ Log Sent to ID: {LOG_CHANNEL_ID}")
        else:
            bot.reply_to(message, "❌ LOG_CHANNEL_ID Missing.")
    except Exception as e:
        bot.reply_to(message, f"❌ Log Failed! Error: {e}")

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = """
🤖 **Commands:**
/raj - Status
/debug - Check Logs
/quiz [topic] - Play Quiz
/img [prompt] - AI Image
/settings - Settings
**Voice:** Send audio to chat!
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
        # --- CHANGES START HERE: Removed 'https' ---
        url = f"image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?nologo=true"
        # --- CHANGES END HERE ---
        bot.send_photo(message.chat.id, url, caption=f"🖼️ {prompt}")
        send_log_to_channel(message.from_user, "IMAGE", prompt, "Image Generated")
    except: bot.reply_to(message, "❌ Error.")

@bot.message_handler(commands=['quiz'])
def handle_quiz_command(message):
    topic = message.text.replace("/quiz", "").strip()
    if not topic: topic = "General Knowledge"
    ask_quiz_level(message, topic)
    send_log_to_channel(message.from_user, "QUIZ START", topic, "Level Selection")

# --- 9. VOICE HANDLER ---
@bot.message_handler(content_types=['voice', 'audio'])
def handle_voice_chat(message):
    try:
        user_id = message.from_user.id
        
        # 1. Forward Audio to Log Channel
        if LOG_CHANNEL_ID:
            try:
                bot.forward_message(LOG_CHANNEL_ID, message.chat.id, message.message_id)
            except: pass

        bot.send_chat_action(message.chat.id, 'record_audio')
        
        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        user_audio_path = f"user_{user_id}.ogg"
        
        with open(user_audio_path, 'wb') as f: f.write(downloaded_file)

        if model_basic:
            myfile = genai.upload_file(user_audio_path)
            config = get_user_config(user_id)
            prompt = f"Listen to this audio. Reply in spoken Hinglish style. {RAW_MODES[config['mode']]}"
            
            try:
                result = model_basic.generate_content([prompt, myfile])
                ai_reply = result.text
            except Exception as e:
                ai_reply = f"Audio samajh nahi aaya. Error: {e}"
            
            reply_audio_path = f"reply_{user_id}.mp3"
            clean_txt = clean_text_for_audio(ai_reply)
            
            if generate_audio(user_id, clean_txt, reply_audio_path):
                with open(reply_audio_path, 'rb') as f: bot.send_voice(message.chat.id, f)
                os.remove(reply_audio_path)
            else:
                bot.reply_to(message, ai_reply) 
            
            try: os.remove(user_audio_path)
            except: pass
            
            send_log_to_channel(message.from_user, "VOICE REPLY", "Audio Processed", clean_txt)
            
    except Exception as e:
        bot.reply_to(message, "❌ Voice Error")
        print(f"Voice Error: {e}")

# --- 10. CALLBACKS ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    
    if call.data.startswith("set_mode_"):
        new_mode = call.data.split("_")[2]
        config = get_user_config(user_id)
        config['mode'] = new_mode
        try:
            bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_settings_markup(user_id))
            bot.answer_callback_query(call.id, f"Mode: {new_mode}")
        except: pass
        return

    if call.data.startswith("qlvl_"):
        if user_id not in quiz_sessions:
            bot.answer_callback_query(call.id, "Expired. Start again.")
            return
        quiz_sessions[user_id]['pending_level'] = call.data.split("_")[1]
        ask_quiz_timer(call.message)
        return

    if call.data.startswith("qtime_"):
        if user_id not in quiz_sessions:
            bot.answer_callback_query(call.id, "Session Expired. Start again.")
            return
        
        seconds = call.data.split("_")[1]
        topic = quiz_sessions[user_id]['pending_topic']
        level = quiz_sessions[user_id]['pending_level']
        bot.edit_message_text(f"🚀 **Quiz Started!**\n{topic} | {level} | {seconds}s", call.message.chat.id, call.message.message_id)
        start_quiz_loop(user_id, call.message.chat.id, topic, level, seconds)
        return

    if call.data.startswith("qz_"):
        if user_id not in quiz_sessions or not quiz_sessions[user_id].get('active'):
            bot.answer_callback_query(call.id, "Ended.")
            return
        
        if user_id in quiz_timers:
            quiz_timers[user_id].cancel()
            del quiz_timers[user_id]

        session = quiz_sessions[user_id]
        
        if call.data == "qz_stop":
            quiz_sessions[user_id]['active'] = False
            score = session['score']
            total = session['total']
            wrong = session['wrong']
            percent = int((score / total) * 100) if total > 0 else 0
            if percent >= 90: emote = "🏆 **Genius!**"
            elif percent >= 40: emote = "🙂 **Nice!**"
            else: emote = "🥺 **Try Again!**"
            report = f"🛑 **Result:**\n✅ {score} | ❌ {wrong}\n📉 **{percent}%**\n{emote}"
            try: bot.edit_message_text(report, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            except: pass
            send_log_to_channel(call.from_user, "QUIZ END", session['topic'], f"Score: {score}/{total}")
            return

        if call.data == "qz_speak":
            bot.answer_callback_query(call.id, "🔊...")
            fname = f"q_{user_id}.mp3"
            q_text = session.get('question_text', '')
            opts = session.get('options', [])
            full_speech = f"Sawal: {q_text}... A: {opts[0]}... B: {opts[1]}... C: {opts[2]}... D: {opts[3]}"
            if generate_audio(user_id, clean_text_for_audio(full_speech), fname):
                with open(fname, "rb") as f: bot.send_voice(call.message.chat.id, f)
                os.remove(fname)
            return

        if call.data.startswith("qz_ans_"):
            selected = int(call.data.split("_")[2])
            labels = ["A", "B", "C", "D"]
            session['total'] += 1
            if selected == session['correct_idx']:
                session['score'] += 1
                result = f"✅ **Correct!** ({labels[session['correct_idx']]})"
            else:
                session['wrong'] += 1
                result = f"❌ **Wrong!** ({labels[session['correct_idx']]})"
            try:
                bot.edit_message_text(f"{result}\n💡 {session['explanation']}\n\n⏳ **Next...**", 
                                      call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            except:
                bot.edit_message_text(f"{result.replace('*', '')}\n\n⏳ Next...", call.message.chat.id, call.message.message_id)

            time.sleep(2)
            if quiz_sessions[user_id]['active']:
                send_new_question(user_id, call.message.chat.id)
        return

    if call.data == "clear_json":
        if user_id == OWNER_ID:
            with open(JSON_FILE, "w", encoding="utf-8") as f: json.dump({}, f)
            bot.answer_callback_query(call.id, "Cleared!")
        else: bot.answer_callback_query(call.id, "Admin Only!")
    
    elif call.data == "speak_msg":
        bot.answer_callback_query(call.id, "🔊...")
        generate_audio(user_id, clean_text_for_audio(call.message.text), "tts.mp3")
        try:
            with open("tts.mp3", "rb") as f: bot.send_voice(call.message.chat.id, f)
        except: pass

# --- 11. TEXT HANDLER ---
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    try:
        user_id = message.from_user.id
        if user_id in quiz_sessions and quiz_sessions[user_id].get('active'): return

        user_text = message.text
        if not user_text: return
        
        config = get_user_config(user_id)
        triggers = ["news", "rate", "price", "weather", "who", "what", "where", "kab", "kahan", "kaise", "president", "winner", "live", "movie", "film", "release", "aayegi"]
        force_search = any(x in user_text.lower() for x in triggers)

        saved_reply = get_reply_from_json(user_text)
        
        if saved_reply and config['memory'] and not force_search:
            ai_reply = saved_reply
            source = "JSON"
        else:
            bot.send_chat_action(message.chat.id, 'typing')
            sys_prompt = f"""
            [System]: Date: {get_current_time()}. Era: Late 2025.
            [INSTRUCTION]: USE GOOGLE SEARCH for Facts/News.
            [Persona]: {RAW_MODES.get(config['mode'])}
            """
            try:
                if model_search and force_search:
                    response = model_search.generate_content(f"{sys_prompt}\nUser: {user_text}")
                elif model_basic:
                    # --- CODE COMPLETION START HERE ---
                    response = model_basic.generate_content(f"{sys_prompt}\nUser: {user_text}")
                else: 
                    ai_reply = "AI model is not ready."
                    source = "Error"
                    # Exit the handler early if models are missing
                    bot.reply_to(message, ai_reply)
                    send_log_to_channel(message.from_user, "TEXT REPLY", user_text, ai_reply)
                    return
                
                ai_reply = response.text
                source = "AI"
                if config['memory'] and source == "AI" and len(ai_reply) < 500: # Only save short AI replies
                    save_to_json(user_text, ai_reply) 

            except Exception as e:
                ai_reply = f"Sorry! AI se connect nahi ho paya. Error: {e}"
                source = "Error"
                print(f"Gemini API Error: {e}")

        # Send the final reply
        bot.reply_to(message, ai_reply, parse_mode="Markdown")
        send_log_to_channel(message.from_user, "TEXT REPLY", user_text, ai_reply)

    except Exception as e:
        print(f"Text Handler Error: {e}")
        try: bot.reply_to(message, "Kuchh gadbad ho gayi. Kripya phir se prayas karein.")
        except: pass

# --- 12. RUN BOT ---
if __name__ == "__main__":
    def run_bot():
        print("🤖 Bot Polling Started...")
        while True:
            try:
                bot.polling(none_stop=True, interval=0, timeout=20)
            except Exception as e:
                print(f"Threaded polling exception: {e}")
                time.sleep(5)
    
    # Use threading for Flask and Telebot
    threading.Thread(target=run_bot).start()
    
    # Simple Flask server for deployment/health checks
    @app.route("/")
    def index():
        return "Dev Bot is Running!", 200

    if os.getenv("PORT"):
        app.run(host="0.0.0.0", port=os.getenv("PORT"))
    else:
        print("Flask server not started. Set PORT in .env for web deployment.")
        
