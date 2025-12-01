import os
import telebot
import google.generativeai as genai
from flask import Flask
from dotenv import load_dotenv
import threading
import time
from gtts import gTTS

# --- 1. CONFIGURATION ---
load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not API_KEY or not BOT_TOKEN:
    print("❌ Error: API Key ya Bot Token missing hai! .env file check karein.")

# --- 2. SMART AI MODEL SETUP ---
model = None

def setup_model():
    global model
    try:
        genai.configure(api_key=API_KEY)
        print("🔍 Google AI Model connect kar raha hoon...")
        try:
            target_model = 'gemini-2.0-flash'
            model = genai.GenerativeModel(target_model)
            # quick smoke test (non-blocking)
            try:
                model.generate_content("Hello")
            except:
                pass
            print(f"✅ Selected & Tested Model: {target_model}")
        except Exception:
            print("⚠️ 2.0 Flash fail hua, 1.5 Flash try kar raha hoon...")
            target_model = 'gemini-1.5-flash'
            model = genai.GenerativeModel(target_model)
            print(f"✅ Fallback Model Selected: {target_model}")
    except Exception as e:
        print(f"⚠️ Model Setup Critical Error: {e}")

setup_model()

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- 3. FLASK SERVER ---
@app.route('/')
def home():
    return "✅ Raj Dev Bot is Online and Fixed!", 200

# ----------------------------------------------------
#  Creator / Custom Reply Patterns (210+ style)
# ----------------------------------------------------
creator_keywords = [
    "kisne banaya","kisne tumhe banaya","kisne tumko banaya","kisne bnaya",
    "creator kaun","creater kaun","crator","cr8r","maker","owner kaun",
    "developer kaun","programmer kaun","coder kaun","banane wala",
    "tumhara creator","tumhara owner","tumhara developer","tumhara coder",
    "tumhara malik","tumhara master","who made you","who create you",
    "who created you","who built you","who programmed you","who coded you",
    "who trained you","who developed you","who owns you","who is your creator",
    "who is your owner","who is your developer","who designed you",
    "who built this bot","who created this bot","who made this bot",
    "who is behind you","who is your admin","who controls you",
    "tell me your creator","tell me who made you","your creator?",
    "ur creator","ur owner","ur maker","ur dev","maker??","creator??",
    "behind you who","made by who","who coded this","creator name",
    "who is your boss","who is your founder","who founded you",
    "who wrote your code","who invented you","ye bot kisne banaya",
    "kisne tumko create kiya","kisne tumko program kiya",
    "kisne tumhe build kiya","kisne banaya bot","kisne banayi",
    "kisne tumhe bnaya","kisne tumko bnaya","kisne tumhe ready kiya",
    "kisne tumhe set kiya","kisne tumhe chalaya","teacher kaun",
    "tumhara banayak","kisne banayaaa","tumhara origin","tumhara source",
    "tumhara base kisne banaya","system kisne banaya","bot ka creator",
    "bot ka owner","bot ka maker","bot ka programmer",
    "kisne tumhara code likha","tumhara parent","tumhara janm","ustad kaun",
    "background kaun","behind this bot","who’s behind this bot",
    # extra variations / slang / misspellings
    "who made u","who made u?","who created u","who created u?","who built u",
    "who coded u","ur creator?","ur creater?","who is ur dev","who is ur owner",
    "who is ur creator","who is ur maker","who is ur owner?","who made this bot?",
    "who created this bot?","who coded this?","who programmed this","who coded this?",
    "kisne banaya tumko","kisne bnaya","kisne banaya re","kisne bnaya bro",
    "kisne tumhe banaya re","who is behind this bot","who is behind u",
    "who's behind this bot","who s behind this bot","who bossed you",
    "who's your creator","who is your creator?","who is your owner?"
]

def get_custom_reply(text):
    if not text:
        return None
    t = text.lower().strip()

    # Check creator/owner related patterns first (override AI)
    for key in creator_keywords:
        if key in t:
            return "Mujhe Raj Dev ne banaya hai."

    # Other explicit custom replies
    if "tumhara naam" in t or "what is your name" in t or "your name" in t or "name kya" in t:
        return "Mera naam Raj Dev hai."

    if "kahan se ho" in t or "where are you from" in t or "where do you live" in t:
        return "Main Assam, Lumding se hoon."

    if "how old are you" in t or "umar" in t or "age" in t:
        return "It is personal."

    if "raj kaun" in t or "who is raj" in t:
        return "Raj Developer hai."

    return None

# ----------------------------------------------------
#  COMMANDS
# ----------------------------------------------------
@bot.message_handler(commands=['raj'])
def send_voice_greeting(message):
    try:
        bot.send_chat_action(message.chat.id, 'record_audio')
        text_to_speak = "Namaste! Main Raj Dev hoon."
        tts = gTTS(text=text_to_speak, lang='hi')
        file_name = f"voice_{message.chat.id}.mp3"
        tts.save(file_name)
        with open(file_name, "rb") as audio:
            bot.send_voice(message.chat.id, audio)
        os.remove(file_name)
    except Exception as e:
        print(f"Voice Error: {e}")
        try:
            bot.reply_to(message, "Voice error.")
        except:
            pass

@bot.message_handler(commands=['start'])
def send_start(message):
    start_text = (
        "🙏 Namaste! Main Raj Dev Bot hoon.\n\n"
        "Aap mujhse yeh sab pooch sakte ho:\n"
        "• 📚 Padhai se related questions\n"
        "• 🧪 Science related sawal\n"
        "• 🧠 General knowledge\n"
        "• 🎓 Exam preparation help\n"
        "• 💡 School/college problems\n"
        "• 🤖 AI, coding, tech related questions\n\n"
        "Mujhe banane wale creator ka naam: Raj\n\n"
        "Bas message bhejo, main jawab dunga."
    )
    bot.reply_to(message, start_text)

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = (
        "📌 Aap yeh questions puch sakte hain:\n"
        "• Padhai se related\n"
        "• Exam se related\n"
        "• Science related\n"
        "• General Knowledge\n"
        "• Biology\n"
        "• Railway topics\n"
        "• Aur bhi bahut kuch!\n\n"
        "Creator: Raj"
    )
    bot.reply_to(message, help_text)

# ----------------------------------------------------
#  MESSAGE HANDLER
# ----------------------------------------------------
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    global model
    try:
        user_text = message.text or ""
        print(f"User: {user_text}")

        # Custom override first
        custom = get_custom_reply(user_text)
        if custom:
            bot.reply_to(message, custom)
            return

        # If no custom reply, use AI
        if model:
            try:
                bot.send_chat_action(message.chat.id, 'typing')
                response = model.generate_content(user_text)

                # Some genai responses may have different shape; guard carefully
                resp_text = None
                try:
                    resp_text = response.text if hasattr(response, "text") else None
                except:
                    resp_text = None

                if not resp_text:
                    # try alternative paths if structure differs
                    try:
                        # if response has 'candidates' or similar
                        if hasattr(response, "candidates") and response.candidates:
                            resp_text = response.candidates[0].content
                    except:
                        resp_text = None

                if resp_text:
                    # send AI reply
                    bot.reply_to(message, resp_text, parse_mode="Markdown")
                else:
                    bot.reply_to(message, "AI ne khali jawab diya.")
            except Exception as ai_e:
                error_msg = str(ai_e)
                print(f"AI Generation Error: {error_msg}")
                if "429" in error_msg:
                    bot.reply_to(message, "⏳ Abhi server busy hai (Quota Exceeded). Thodi der baad try karein.")
                else:
                    bot.reply_to(message, "Kuch gadbad ho gayi. Dobara try karein.")
                    # attempt re-init model
                    try:
                        setup_model()
                    except:
                        pass
        else:
            bot.reply_to(message, "AI Model set nahi hai. Admin ko contact karein.")
            try:
                setup_model()
            except:
                pass

    except Exception as e:
        print(f"General Error: {e}")

# --- 6. POLLING LOOP ---
def run_bot_loop():
    print("🤖 Bot Starting...")
    try:
        bot.remove_webhook()
        time.sleep(1)
    except:
        pass

    while True:
        try:
            print("🔄 Polling...")
            bot.polling(non_stop=False, interval=0, timeout=20)
        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ Error: {error_msg}")
            time.sleep(5)

if __name__ == "__main__":
    t = threading.Thread(target=run_bot_loop)
    t.start()
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
