import edge_tts
import asyncio
import os
from gtts import gTTS

# --- SETTINGS ---
# Male Voice ID (Hindi)
MALE_VOICE_ID = "hi-IN-MadhurNeural" 

async def _run_edge_tts(text, filename):
    """
    Internal function to run Edge TTS securely.
    Pitch '-5Hz' makes the voice deeper (more masculine).
    """
    communicate = edge_tts.Communicate(text, MALE_VOICE_ID, rate="+0%", pitch="-5Hz")
    await communicate.save(filename)

def generate_audio_file(text, filename, voice_mode='edge'):
    """
    Main function to generate audio.
    voice_mode: 'edge' (Male) or 'google' (Female)
    """
    if not text: return False

    # --- OPTION 1: EDGE TTS (MALE) ---
    if voice_mode == 'edge':
        try:
            # IMPORTANT: Creating a NEW loop for every request to prevent Flask crashes
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_run_edge_tts(text, filename))
            loop.close()
            
            # Check if file actually exists
            if os.path.exists(filename) and os.path.getsize(filename) > 0:
                return True
            else:
                print("⚠️ Edge-TTS file empty, switching to backup.")
        except Exception as e:
            print(f"⚠️ Edge-TTS Error: {e}")
            # Fallback to Google naturally happens below

    # --- OPTION 2: GOOGLE TTS (FEMALE) ---
    # Used if user selected 'google' OR if 'edge' failed above
    try:
        print("ℹ️ Using Google TTS (Female)")
        tts = gTTS(text=text, lang='hi', slow=False)
        tts.save(filename)
        return True
    except Exception as e:
        print(f"❌ Audio Generation Failed Completely: {e}")
        return False
