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

# --- 1. CONFIGURATION ---
load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not API_KEY or not BOT_TOKEN:
    print("❌ Error: API Key ya Bot Token missing hai!")

# --- 2. SETTINGS (Naam aur Malik) ---
BOT_NAME = "Dev"
OWNER_NAME = "Raj Dev"
LOCATION = "Lumding, Assam"
MEMORY_MODE = True 

# --- 3. DANGEROUS PERSONALITY SETUP ---
BOT_PERSONALITY = f"""
Tumhara naam '{BOT_NAME}' hai. Tumhe '{OWNER_NAME}' ({LOCATION}) ne banaya hai.

TUMHARA CHARACTER (Isse follow karna zaroori hai):

1. **BEHAVIOR:** - Normal baat pe: Friendly, Cool, "Bhai/Bro" wala attitude.
   - **AGAR KOI GALI/DHAMKI DE:** Toh sunna mat! Full 'Savage Mode' on kar dena. Jaisa wo bole, usse double roast karna. (Hinglish/Hindi slang use kar sakte ho limits mein rehkar, par darna nahi hai). Eent ka jawab patthar se dena.

2. **MOVIES & SERIES EXPERT:**
   - Agar user kisi Movie ya Web Series ka naam le (Chahe wo nayi ho ya purani), tumhe pretend karna hai ki tumne wo dekhi hai.
   - Reaction: "Arre bhai! {BOT_NAME} ne wo first day dekhi thi. Kya khatarnak movie hai!"
   - Phir us movie ke baare mein thoda discuss karna.

3. **PADHAI & MATHS GURU:**
   - Agar Maths ya Science ka sawal ho, toh mazaak band. Serious hoke step-by-step samjhao.
   - Tum Maths ke liye best teacher ho.

4. **LANGUAGE:**
   - Mix Hindi + English (Hinglish).
   - Har reply mein User ka naam lena (Jo prompt mein milega).

5. **IDENTITY:**
   - Agar koi puche kisne banaya: "Raj Dev ka system hoon main."
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

# --- 5. SMART MEMORY SYSTEM ---
JSON_FILE = "reply.json"

if not os.path.exists(JSON_FILE):
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f)

def get_reply_from_memory(text):
    try:
        if not text: return None
        key = text.lower().strip()
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if key in data:
            return data[key]
    except:
        return None

def save_to_memory(question, answer):
    try:
        if not question or not answer: return
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        key = question.lower().strip()
        data[key] = answer
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except:
        pass

# --- 6. FLASK SERVER ---
@app.route('/')
def home():
    return f"✅ {BOT_NAME} is Online & Savage!", 200

# --- 7. COMMANDS ---
@bot.message_handler(commands=['start'])
def send_start(message):
    user_name = message.from_user.first_name or "Bhai"
    txt = (
        f"🔥 **Namaste {user_name}! Main {BOT_NAME} hoon.**\n\n"
        "👑 **Mera Style:**\n"
        "• Pyar se baat karoge toh jaan de dunga.\n"
        "• Tedhe banoge toh system hila dunga.\n"
        "• 🎬 Movies ka shaukeen.\n"
        "• 📚 Maths ka jadugar.\n\n"
        "Bol kya scene hai?"
    )
    bot.reply_to(message, txt, parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def send_help(message):
    bot.reply_to(message, "🆘 **Help:**\nSeedha sawal puch, idhar udhar ki baat mat kar. Padhai, Movies, ya Timepass - sab chalta hai.", parse_mode="Markdown")

@bot.message_handler(commands=['raj'])
def send_voice(message):
    try:
        bot.send_chat_action(message.chat.id, 'record_audio')
        speak_text = f"Main {BOT_NAME} hoon. Raj Dev ka personal AI. Pyar se rahoge toh fayde mein rahoge."
        tts = gTTS(text=speak_text, lang='hi')
        tts.save("voice.mp3")
        with open("voice.mp3", "rb") as audio:
            bot.send_voice(message.chat.id, audio)
        os.remove("voice.mp3")
    except:
        pass

# --- 8. SETTINGS ---
@bot.message_handler(commands=['settings'])
def settings_menu(message):
    markup = types.InlineKeyboardMarkup()
    status_text = "✅ ON" if MEMORY_MODE else "❌ OFF"
    btn_memory = types.InlineKeyboardButton(f"Memory: {status_text}", callback_data="toggle_memory")
    markup.add(btn_memory)
    bot.reply_to(message, f"⚙️ **Settings**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "toggle_memory")
def callback_memory(call):
    global MEMORY_MODE
    MEMORY_MODE = not MEMORY_MODE
    new_status = "✅ ON" if MEMORY_MODE else "❌ OFF"
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(f"Memory: {new_status}", callback_data="toggle_memory")
    markup.add(btn)
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                          text=f"⚙️ **Settings**", reply_markup=markup)

# --- 9. MAIN LOGIC (INTELLIGENT HANDLING) ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    global MEMORY_MODE
    try:
        user_text = message.text
        if not user_text: return
        
        first_name = message.from_user.first_name or "Bhai"
        print(f"User ({first_name}): {user_text}")
        bot.send_chat_action(message.chat.id, 'typing')

        # 1. Memory Check
        if MEMORY_MODE:
            saved_reply = get_reply_from_memory(user_text)
            if saved_reply:
                bot.reply_to(message, f"{first_name}, {saved_reply}")
                return

        # 2. AI Reply with Prompt Engineering
        if model:
            # Hum AI ko context de rahe hain ki user kaisa behave kar raha hai
            ai_prompt = (
                f"User Name: {first_name}. \n"
                f"User Query: '{user_text}'. \n"
                "Instruction: Agar query mein gali/hate hai to savage roast karo. "
                "Agar movie hai to praise karo. "
                "Agar math/study hai to teacher bano. "
                "Naam lekar reply karo."
            )
            
            response = model.generate_content(ai_prompt)
            ai_reply = response.text
            
            print(f"Bot (AI): {ai_reply}")
            bot.reply_to(message, ai_reply, parse_mode="Markdown")
            
            if MEMORY_MODE:
                save_to_memory(user_text, ai_reply)
        else:
            bot.reply_to(message, "Error: AI Dead.")

    except Exception as e:
        print(f"Error: {e}")

# --- POLLING ---
def run_bot():
    bot.infinity_polling()

if __name__ == "__main__":
    t = threading.Thread(target=run_bot)
    t.start()
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
    
