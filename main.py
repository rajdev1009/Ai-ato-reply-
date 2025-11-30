import os
import telebot
import google.generativeai as genai
from flask import Flask
from dotenv import load_dotenv
import threading
from gtts import gTTS  # Awaaz (Voice) banane ke liye

# --- 1. SETUP & CONFIGURATION ---
# Local computer ke liye .env file load karega
load_dotenv()

# Keys uthana (Koyeb settings ya .env se)
API_KEY = os.getenv("GOOGLE_API_KEY") 
BOT_TOKEN = os.getenv("7793783847:AAF0QSWnyLjUuaY8NfX-GumX0CY_cS2agCY")

# Agar keys nahi mili to console mein error dikhayega
if not API_KEY or not BOT_TOKEN:
    print("Error: API Key ya Bot Token missing hai! Settings check karein.")

# Google Gemini AI Setup
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Telegram Bot Setup
bot = telebot.TeleBot(BOT_TOKEN)

# Flask Server (Koyeb par bot ko zinda rakhne ke liye zaroori hai)
app = Flask(__name__)

@app.route('/')
def home():
    return "Raj Dev Bot is Running Successfully!", 200

# --- 2. SPECIAL VOICE COMMAND (/raj) ---
@bot.message_handler(commands=['raj'])
def send_voice_greeting(message):
    try:
        # User ko dikhao ki bot 'recording' kar raha hai...
        bot.send_chat_action(message.chat.id, 'record_audio')
        
        # Ye text bot bolega
        text_to_speak = "Namaste! Main Raj Dev hoon. Main bolkar bhi jawab de sakta hoon. Bataiye kya seva karun?"
        
        # Text ko Audio (Hindi) mein convert karna
        tts = gTTS(text=text_to_speak, lang='hi')
        file_name = "voice_reply.mp3"
        tts.save(file_name)
        
        # Audio bhejna
        with open(file_name, "rb") as audio:
            bot.send_voice(message.chat.id, audio)
            
        # Bhej ne ke baad file delete kar do (Server safai)
        os.remove(file_name)
        
    except Exception as e:
        print(f"Voice Error: {e}")
        bot.reply_to(message, "Voice message mein kuch takniki dikkat aayi.")

# --- 3. SHORTCUTS (START & HELP) ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "🙏 **Namaste! Main Raj Dev Bot hoon.**\n\n"
        "Main AI se automatic baat karta hoon, par kuch sawal main khud batata hoon.\n\n"
        "🎤 **Try karein:** `/raj` (Mera voice sunne ke liye)\n"
        "❓ **Help:** `/help`"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = (
        "🆘 **Madad Kendra (Help)**\n\n"
        "Main in sawalon ka fix jawab deta hoon:\n"
        "1. `Tumhara naam kya hai?`\n"
        "2. `Tum kahan se ho?`\n"
        "3. `Lumding ka pin code?`\n"
        "4. `Lumding kahan rahte ho?`\n"
        "5. `Who made you?`\n"
        "6. `Religion` / `Age`\n\n"
        "Baaki kuch bhi pucho, main Google AI ka use karke jawab dunga!"
    )
    bot.reply_to(message, help_text, parse_mode="Markdown")

# --- 4. CUSTOM LOGIC (FIXED ANSWERS) ---
def get_custom_reply(text):
    text = text.lower().strip()
    
    # Check for keywords
    if "tumhara naam kya hai" in text or "what is your name" in text:
        return "Mera naam Raj Dev hai."
    
    elif "tum kahan se ho" in text or "where are you from" in text:
        return "Main Lumding se hoon."
    
    elif "lumding ka pin code" in text or "pincode" in text:
        return "Lumding ka pin code 782447 hai."
    
    elif "lumding kahan rahte ho" in text or "address" in text:
        return "Main Dakshin Lumding SK Paultila mein rehta hoon."
    
    elif "who made you" in text or "kisne banaya" in text:
        return "Mujhe Rajdev ne banaya hai."
    
    elif "religion" in text or "dharam" in text:
        return "Mera religion Hindu hai."
        
    elif "how old are you" in text or "age" in text or "umr" in text:
        return "Meri umr 22 saal hai." 

    return None

# --- 5. MAIN MESSAGE HANDLER ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        user_text = message.text
        # Console mein print karein taaki logs mein dikhe
        print(f"User: {user_text}")

        # Pehle check karo: Kya ye koi Fixed Sawal hai?
        custom_reply = get_custom_reply(user_text)
        
        if custom_reply:
            bot.reply_to(message, custom_reply)
        else:
            # Agar Fixed nahi hai, to Google AI se pucho
            chat = model.start_chat(history=[])
            response = chat.send_message(user_text)
            
            # Markdown use karein formatting ke liye
            bot.reply_to(message, response.text, parse_mode="Markdown")

    except Exception as e:
        print(f"Error: {e}")
        # Agar server busy ho ya error aaye
        bot.reply_to(message, "Maaf kijiye, abhi main process nahi kar pa raha hoon.")

# --- 6. SERVER START ---
def run_bot():
    bot.infinity_polling()

if __name__ == "__main__":
    # Bot ko alag thread mein chalana zaroori hai
    t = threading.Thread(target=run_bot)
    t.start()
    
    # Web server start (Koyeb port 8000 par dhundta hai)
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
