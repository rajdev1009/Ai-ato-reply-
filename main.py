import os
import telebot
import google.generativeai as genai
from flask import Flask
from dotenv import load_dotenv
import threading
import time
from gtts import gTTS
from datetime import datetime, timedelta

--- 1. CONFIGURATION ---

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not API_KEY or not BOT_TOKEN:
print("❌ Error: API Key ya Bot Token missing hai! .env file check karein.")

--- 2. SMART AI MODEL SETUP ---

model = None

def setup_model():
global model
try:
genai.configure(api_key=API_KEY)
print("🔍 Google AI Model connect kar raha hoon...")
try:
target_model = 'gemini-2.0-flash'
model = genai.GenerativeModel(target_model)
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
app = Flask(name)

--- 3. FLASK SERVER ---

@app.route('/')
def home():
return "✅ Raj Dev Bot is Online and Fixed!", 200

--- 4. USER MEMORY & REMINDERS ---

user_memory = {}
user_reminders = {}

def get_user_context(user_id):
return user_memory.get(user_id, [])

def add_to_user_context(user_id, message, response):
if user_id not in user_memory:
user_memory[user_id] = []
user_memory[user_id].append({"user": message, "bot": response})
if len(user_memory[user_id]) > 20:
user_memory[user_id] = user_memory[user_id][-20:]

def set_reminder(user_id, time_str, reminder_text):
hour, minute = map(int, time_str.split(":"))
now = datetime.now()
target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
if target_time < now:
target_time += timedelta(days=1)

def alarm_thread():
    delta = (target_time - datetime.now()).total_seconds()
    time.sleep(delta)
    bot.send_message(user_id, f"⏰ Reminder: {reminder_text}")

t = threading.Thread(target=alarm_thread)
t.start()
user_reminders[user_id] = t

def remove_reminder(user_id):
if user_id in user_reminders:
user_reminders.pop(user_id)
bot.send_message(user_id, "❌ Reminder cancelled.")

--- 5. CUSTOM REPLIES ---

creator_keywords = [
"kisne banaya","kisne tumhe banaya","creator kaun","maker","developer kaun","raj kon",
"owner kaun","tumhara creator","who made you","who created you","who is your creator"
]

def get_custom_reply(text):
if not text:
return None
t = text.lower().strip()
for key in creator_keywords:
if key in t:
return "Mujhe Raj Dev ne banaya hai."
if "tumhara naam" in t or "what is your name" in t:
return "Mera naam Raj Dev hai."
if "kahan se ho" in t or "where are you from" in t:
return "Main Assam, Lumding se hoon."
if "how old are you" in t or "umar" in t:
return "It is personal."
if "raj kaun" in t or "who is raj" in t:
return "Raj Developer hai."
return None

--- 6. COMMANDS ---

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
)@bot.message_handler(commands=['help'])
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

@bot.message_handler(commands=['setalarm'])
def command_set_alarm(message):
try:
args = message.text.split()[1:]  # /setalarm 16:00 Reminder text
if len(args) < 2:
bot.reply_to(message, "Usage: /setalarm HH:MM Reminder message")
return
time_str = args[0]
reminder_text = " ".join(args[1:])
set_reminder(message.chat.id, time_str, reminder_text)
bot.reply_to(message, f"✅ Reminder set at {time_str}")
except Exception as e:
bot.reply_to(message, f"Error: {e}")

@bot.message_handler(commands=['removealarm'])
def command_remove_alarm(message):
remove_reminder(message.chat.id)

--- 7. MESSAGE HANDLER ---

@bot.message_handler(func=lambda message: True)
def handle_message(message):
global model
try:
user_text = message.text or ""
print(f"User: {user_text}")

    # Custom override first
    custom = get_custom_reply(user_text)
    if custom:
        add_to_user_context(message.chat.id, user_text, custom)
        bot.reply_to(message, custom)
        return

    # AI response with memory + fun style
    if model:
        try:
            bot.send_chat_action(message.chat.id, 'typing')
            context = get_user_context(message.chat.id)
            prompt = ""
            for c in context:
                prompt += f"User: {c['user']}\nBot: {c['bot']}\n"
            prompt += f"User: {user_text}\nBot:"

            # fun personality hint
            prompt += "\nNote: Reply funny, casual, flirtatious style, jokes allowed, language free."

            response = model.generate_content(prompt)
            resp_text = getattr(response, "text", None)
            if not resp_text:
                try:
                    resp_text = response.candidates[0].content
                except:
                    resp_text = "AI ne kuch samajh nahi paaya."

            add_to_user_context(message.chat.id, user_text, resp_text)
            bot.reply_to(message, resp_text)
        except Exception as ai_e:
            error_msg = str(ai_e)
            print(f"AI Generation Error: {error_msg}")
            if "429" in error_msg:
                bot.reply_to(message, "⏳ Abhi server busy hai (Quota Exceeded). Thodi der baad try karein.")
            else:
                bot.reply_to(message, "Kuch gadbad ho gayi. Dobara try karein.")
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

--- 8. POLLING LOOP ---

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
        print(f"⚠️ Error: {e}")
        time.sleep(5)

if name == "main":
t = threading.Thread(target=run_bot_loop)
t.start()
port = int(os.environ.get("PORT", 8000))
app.run(host="0.0.0.0", port=port)
bot.reply_to(message, start_text)
