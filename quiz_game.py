import json
from telebot import types

# Temporary memory to store correct answers
# Format: {message_id: correct_option_index}
quiz_state = {}

def generate_quiz(bot, message, model_basic):
    """
    Gemini se Quiz generate karke user ko bhejta hai.
    """
    topic = message.text.replace("/quiz", "").strip()
    if not topic: 
        topic = "General Knowledge"
    
    bot.send_chat_action(message.chat.id, 'typing')
    
    # Prompt to get strict JSON output
    prompt = f"""
    Create a unique, tricky multiple-choice question about '{topic}'.
    Reply ONLY in valid JSON format. No extra text.
    Format:
    {{
        "question": "Question text here?",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "correct_index": 0,
        "explanation": "Short explanation why it is correct."
    }}
    Language: Hinglish.
    """
    
    try:
        response = model_basic.generate_content(prompt)
        text = response.text.strip()
        
        # Cleaning JSON format (agar AI ne ```json laga diya ho)
        if "```" in text:
            text = text.replace("```json", "").replace("```", "")
        
        data = json.loads(text)
        
        # Buttons banana
        markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = []
        for i, option in enumerate(data['options']):
            # Callback data mein answer aur index bhejne ki jagah sirf index bhej rahe hain
            buttons.append(types.InlineKeyboardButton(option, callback_data=f"quiz_{i}"))
        markup.add(*buttons)
        
        # Question bhejna
        msg = bot.send_message(message.chat.id, f"🎮 **Quiz: {topic}**\n\n❓ {data['question']}", reply_markup=markup, parse_mode="Markdown")
        
        # Correct answer memory mein save karna
        quiz_state[msg.message_id] = {
            "correct": data['correct_index'],
            "explanation": data.get("explanation", "Sahi jawab ye hai.")
        }
        
    except Exception as e:
        bot.reply_to(message, "❌ Quiz generate nahi ho paya. Dobara try karo.")
        print(f"Quiz Error: {e}")

def check_answer(call, bot):
    """
    Button dabane par answer check karta hai.
    """
    try:
        msg_id = call.message.message_id
        user_choice = int(call.data.split("_")[1])
        
        if msg_id in quiz_state:
            correct_data = quiz_state[msg_id]
            correct_index = correct_data["correct"]
            explanation = correct_data["explanation"]
            
            if user_choice == correct_index:
                bot.answer_callback_query(call.id, "🎉 Sahi Jawab! +10 Points", show_alert=True)
                final_text = f"✅ **Correct!**\n\n{call.message.text}\n\n💡 _Reason: {explanation}_"
                bot.edit_message_text(final_text, call.message.chat.id, msg_id, parse_mode="Markdown")
            else:
                bot.answer_callback_query(call.id, "❌ Galat Jawab! Try again.", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "⚠️ Ye quiz expire ho chuka hai.")
    except Exception as e:
        print(e)

