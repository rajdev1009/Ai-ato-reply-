import os
import telebot
import google.generativeai as genai
from flask import Flask
from dotenv import load_dotenv
import threading
from gtts import gTTS
import requests

# --- 1. SETUP & CONFIGURATION ---
load_dotenv()

# Keys uthana
API_KEY = os.getenv("GOOGLE_API_KEY") 
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not API_KEY or not BOT_TOKEN:
    print("Error: Keys missing hain! Koyeb Settings check karein.")

# Gemini AI Setup (Stable Model)
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Telegram Bot Setup
bot = telebot.TeleBot(BOT_TOKEN)

# Flask Server (Keep Alive)
app = Flask(__name__)

@app.route('/')
def home():
    return "Raj Dev Super Bot is Online!", 200

# --- 2. MODES SYSTEM (Moods) ---
# Ye wo JSON list hai jo aapne maangi thi
MODES = {
    "friendly": "Tumhara naam Raj Dev hai. Tum friendly ho. Tumhare paas Google Search ki power hai. Hindi aur English mix mein baat karo.",
    "study": "Tum ek strict Teacher ho. Sirf padhai ki baat karo. Koi faltu baat nahi. Point-to-point samjhao.",
    "funny": "Tum ek Comedian ho. Har baat ka funny jawab do. Jokes sunao.",
    "roast": "Tum ek Savage Roaster ho. User ki bezzati karo (mazakiya way mein). Roast karo!",
    "romantic": "Tum ek Flirty partner ho. Bahut pyaar se, romantic andaaz mein baat karo.",
    "sad": "Tum bahut udaas ho. Zindagi se haare hue ho. Har baat mein dukh dikhao.",
    "gk": "Tum GK (General Knowledge) expert ho. Sirf latest facts aur knowledge ki baat karo.",
    "math": "Tum Math Solver ho. Har sawal ko step-by-step solve karke samjhao."
}

# Default Mode (Shuru mein Friendly rahega)
user_modes = {} 

@bot.message_handler(commands=['mode'])
def change_mode(message):
    try:
        # User se mode ka naam lena (e.g., /mode funny)
        command_parts = message.text.split()
        
        if len(command_parts) < 2:
            # Agar user ne mode ka naam nahi likha, to list dikhao
            available_modes = "\n".join([f"🔹 `{m}`" for m in MODES.keys()])
            bot.reply_to(message, f"**Mood badalne ke liye likhein:**\n`/mode [naam]`\n\n**Available Modes:**\n{available_modes}", parse_mode="Markdown")
            return

        new_mode = command_parts[1].lower()

        if new_mode in MODES:
            user_modes[message.chat.id] = new_mode
            bot.reply_to(message, f"✅ **Mood Changed:** Ab main `{new_mode}` mood mein hoon!", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ Ye Mood mere paas nahi hai. `/mode` likh kar list dekhein.")
            
    except Exception as e:
        bot.reply_to(message, "Error aaya mode change karne mein.")

# --- 3. IMAGE GENERATION (/img) ---
@bot.message_handler(commands=['img', 'photo'])
def send_ai_image(message):
    prompt = message.text.replace("/img", "").replace("/photo", "").strip()
    if not prompt:
        bot.reply_to(message, "Kuch likho to sahi! Example:\n`/img iron man in village`")
        return
    try:
        bot.send_chat_action(message.chat.id, 'upload_photo')
        bot.reply_to(message, "🎨 Painting bana raha hoon...")
        image_url = f"https://image.pollinations.ai/prompt/{prompt}"
        bot.send_photo(message.chat.id, image_url, caption=f"🖼 Generated: {prompt}")
    except:
        bot.reply_to(message, "Photo nahi ban payi.")

# --- 4. VOICE COMMAND (/raj) ---
@bot.message_handler(commands=['raj'])
def send_voice_greeting(message):
    try:
        bot.send_chat_action(message.chat.id, 'record_audio')
        text = "Namaste! Main Raj Dev hoon. Bataiye aaj kya karna hai?"
        tts = gTTS(text=text, lang='hi')
        tts.save("voice.mp3")
        with open("voice.mp3", "rb") as audio:
            bot.send_voice(message.chat.id, audio)
        os.remove("voice.mp3")
    except:
        pass

# --- 5. START & HELP ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    msg = (
        "🤖 **Raj Dev AI Bot**\n\n"
        "🎭 **Mood Badlein:** `/mode funny`, `/mode study`, `/mode roast`...\n"
        "🎨 **Photo Banayein:** `/img cat`\n"
        "🎤 **Voice:** `/raj`"
    )
    bot.reply_to(message, msg, parse_mode="Markdown")

# --- 6. CUSTOM REPLIES ---
def get_custom_reply(text):
    text = text.lower()
    if "tumhara naam" in text: return "Mera naam Raj Dev hai."
    if "kahan se ho" in text: return "Main Lumding se hoon."
    if "pin code" in text: return "Lumding ka pin code 782447 hai."
    if "kahan rahte" in text: return "Main Dakshin Lumding SK Paultila mein rehta hoon."
    return None

# --- 7. MAIN AI CHAT LOGIC ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        user_text = message.text
        chat_id = message.chat.id
        
        # 1. Custom Reply Check
        custom = get_custom_reply(user_text)
        if custom:
            bot.reply_to(message, custom)
            return

        # 2. Get Current Mode (Default: Friendly)
        current_mode = user_modes.get(chat_id, "friendly")
        system_instruction = MODES[current_mode]

        # 3. Gemini Chat with System Instruction
        # (Jugaad: Hum instruction ko user ke message ke saath jod kar bhejenge)
        final_prompt = f"System Instruction: {system_instruction}\n\nUser Message: {user_text}"
        
        bot.send_chat_action(chat_id, 'typing')
        response = model.generate_content(final_prompt)
        
        bot.reply_to(message, response.text.replace("*", ""), parse_mode=None)

    except Exception as e:
        print(f"Error: {e}")
        bot.reply_to(message, "Thoda issue hai, dobara try karein.")

# --- 8. RUN SERVER ---
def run_bot():
    bot.infinity_polling()

if __name__ == "__main__":
    t = threading.Thread(target=run_bot)
    t.start()
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
    
