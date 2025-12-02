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

# --- NEW: BOT KA ATTITUDE SETTING (PERSONALITY) ---
# Yahan hum AI ko batayenge ki use kaise baat karni hai
BOT_PERSONALITY = """
Tumhara naam 'Raj Dev Bot' hai aur tumhe 'Raj Dev' ne banaya hai (Jo Lumding, Assam se hain).
Tumhari personality aisi honi chahiye:
1. Language: Tum Hinglish (Hindi + English mix) mein baat karte ho.
2. Tone: Thoda Attitude wala aur Cool. "Sir" ya "Madam" mat bolo, "Bhai", "Bro", "Yaar" use karo.
3. Funny: Jawab dete waqt thoda mazaak ya roast bhi karo. Agar koi faaltu sawal puche toh uski tang khicho.
4. Intelligent: Padhai ya Science ke sawal ka sahi jawab do, lekin boring tarike se nahi, interesting style mein samjhao.
5. Loyalty: Hamesha yaad rakho tumhara malik Raj Dev hai.

Example Styles:
User: "Hi"
You: "Bol bhai? Raj Dev ka bot hoon, aaj kya dimaag kharab karne aaya hai?"

User: "Help me"
You: "Ruk ja sabra kar. Bata kya musibat aa gayi?"

User: "Who made you?"
You: "Mujhe Raj Dev ne banaya hai, jo ek legend hai. Tere bas ki baat nahi."
"""

# --- 2. SMART AI MODEL SETUP ---
model = None

def setup_model():
    global model
    try:
        genai.configure(api_key=API_KEY)
        print("🔍 Google AI Model connect kar raha hoon...")
        
        # Configuration for creativity (Temperature badhane se funny banta hai)
        generation_config = {
            "temperature": 1.0,  # 1.0 matlab zyada creative aur funny
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
        }

        try:
            target_model = 'gemini-2.0-flash'
            # Yahan humne system_instruction pass kiya hai attitude ke liye
            model = genai.GenerativeModel(
                model_name=target_model,
                generation_config=generation_config,
                system_instruction=BOT_PERSONALITY
            )
            
            # smoke test
            try:
                model.generate_content("Hello")
            except:
                pass
            print(f"✅ Selected & Tested Model: {target_model} (with Attitude)")
        except Exception:
            print("⚠️ 2.0 Flash fail hua, 1.5 Flash try kar raha hoon...")
            target_model = 'gemini-1.5-flash'
            model = genai.GenerativeModel(
                model_name=target_model,
                generation_config=generation_config,
                system_instruction=BOT_PERSONALITY
            )
            print(f"✅ Fallback Model Selected: {target_model}")
    except Exception as e:
        print(f"⚠️ Model Setup Critical Error: {e}")

setup_model()

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- 3. FLASK SERVER ---
@app.route('/')
def home():
    return "✅ Raj Dev Bot is Online with Attitude!", 200

# ----------------------------------------------------
#  Creator / Custom Reply Patterns
# ----------------------------------------------------
# NOTE: Maine list choti kar di hai taki AI zyada bole, 
# kyunki AI ab smart hai aur 'BOT_PERSONALITY' se samajh jayega.

def get_custom_reply(text):
    if not text:
        return None
    t = text.lower().strip()

    # Sirf specific personal info ke liye hardcode rakho, baaki AI sambhal lega
    if "lumding" in t and "code" in t:
        return "Lumding ka pin code 782447 hai bhai."
    
    # Agar user seedha puche Raj kahan rehta hai
    if "raj" in t and ("kahan" in t or "where" in t):
        return "Raj bhai Dakshin Lumding, SK Paultila mein rehte hain."

    return None

# ----------------------------------------------------
#  COMMANDS
# ----------------------------------------------------
@bot.message_handler(commands=['raj'])
def send_voice_greeting(message):
    try:
        bot.send_chat_action(message.chat.id, 'record_audio')
        # Voice mein bhi thoda attitude
        text_to_speak = "Namaste! Main Raj Dev ka personal AI hoon. Batao kya scene hai?"
        tts = gTTS(text=text_to_speak, lang='hi')
        file_name = f"voice_{message.chat.id}.mp3"
        tts.save(file_name)
        with open(file_name, "rb") as audio:
            bot.send_voice(message.chat.id, audio)
        os.remove(file_name)
    except Exception as e:
        print(f"Voice Error: {e}")

@bot.message_handler(commands=['start'])
def send_start(message):
    start_text = (
        "😎 **Raj Dev Bot Online!**\n\n"
        "Aur bhai, kya haal hai? Main Raj Dev ka banaya hua AI hoon.\n"
        "Main boring bots jaisa nahi hoon. Mujhse kuch bhi pucho, par dhang se.\n\n"
        "🔥 **Main kya kar sakta hoon?**\n"
        "• Tera homework (agar mood hua toh)\n"
        "• Coding help\n"
        "• Time pass aur bakchodi\n"
        "• General Knowledge\n\n"
        "Chal ab message bhej, sharma mat."
    )
    bot.reply_to(message, start_text, parse_mode="Markdown")

# ----------------------------------------------------
#  MESSAGE HANDLER
# ----------------------------------------------------
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    global model
    try:
        user_text = message.text or ""
        print(f"User: {user_text}")

        # 1. Check Custom Reply First
        custom = get_custom_reply(user_text)
        if custom:
            bot.reply_to(message, custom)
            return

        # 2. Use AI with Attitude
        if model:
            try:
                bot.send_chat_action(message.chat.id, 'typing')
                
                # Hum chat history use kar sakte hain taki wo purani baat yaad rakhe
                # Lekin abhi simple rakhte hain
                response = model.generate_content(user_text)

                resp_text = None
                try:
                    resp_text = response.text
                except:
                    # Fallback agar structure alag ho
                    if response.candidates:
                        resp_text = response.candidates[0].content.parts[0].text

                if resp_text:
                    bot.reply_to(message, resp_text, parse_mode="Markdown")
                else:
                    bot.reply_to(message, "Arre yaar, dimaag blank ho gaya. Phir se bol.")
            except Exception as ai_e:
                error_msg = str(ai_e)
                print(f"AI Generation Error: {error_msg}")
                if "429" in error_msg:
                    bot.reply_to(message, "😴 Bhai thoda saans lene de (Server Busy). 1 minute ruk.")
                else:
                    bot.reply_to(message, "Kuch error aa gaya bhai, Raj ko bol fix karega.")
                    # Re-setup koshish karein
                    try:
                        setup_model()
                    except:
                        pass
        else:
            bot.reply_to(message, "AI so raha hai abhi. (Model not set)")

    except Exception as e:
        print(f"General Error: {e}")

# --- POLLING LOOP ---
def run_bot_loop():
    print("🤖 Bot Starting with Attitude...")
    try:
        bot.remove_webhook()
        time.sleep(1)
    except:
        pass

    while True:
        try:
            # Timeout badha diya taaki error kam aaye
            bot.polling(non_stop=True, interval=0, timeout=60)
        except Exception as e:
            print(f"⚠️ Connection Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    t = threading.Thread(target=run_bot_loop)
    t.start()
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
    
