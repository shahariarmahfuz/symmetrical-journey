import os
from flask import Flask, request, jsonify
import google.generativeai as genai
import threading
import time
import requests
from collections import deque
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging

app = Flask(__name__)

# লগিং কনফিগার করা
logging.basicConfig(level=logging.INFO)

# পরিবেশ ভেরিয়েবল থেকে API কী পাওয়া
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY পরিবেশ ভেরিয়েবল সেট করা হয়নি")

# Gemini API ইনিশিয়ালাইজ করা
genai.configure(api_key=GEMINI_API_KEY)

# Generation কনফিগারেশন
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-1.5-pro",  # আপনার আসল মডেলের নাম দিয়ে প্রতিস্থাপন করুন
    generation_config=generation_config,
)

# রেট লিমিটার ইনিশিয়ালাইজ করা
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]  # প্রয়োজন অনুযায়ী সীমা সামঞ্জস্য করুন
)

# চ্যাট সেশনগুলি একটি ডিকশনারিতে সংরক্ষণ করা
chat_sessions = {}

@app.route('/ask', methods=['GET'])
@limiter.limit("10 per minute")  # প্রতি মিনিটে ১০টি অনুরোধ সীমিত করুন
def ask():
    query = request.args.get('q')
    user_id = request.args.get('id')

    if not query or not user_id:
        return jsonify({"error": "অনুগ্রহ করে উভয় প্রশ্ন এবং আইডি প্যারামিটার প্রদান করুন।"}), 400

    # একটি নতুন চ্যাট সেশন তৈরি করা যদি না থাকে
    if user_id not in chat_sessions:
        chat_sessions[user_id] = {
            "chat": model.start_chat(history=[]),
            "history": deque(maxlen=25)
        }

    chat_session = chat_sessions[user_id]["chat"]
    history = chat_sessions[user_id]["history"]

    # ব্যবহারকারীর প্রশ্ন ইতিহাসে যোগ করা
    history.append(f"User: {query}")
    try:
        response = chat_session.send_message(query)
        # বটের উত্তর ইতিহাসে যোগ করা
        history.append(f"Bot: {response.text}")
        return jsonify({"response": response.text})
    except Exception as e:
        logging.error(f"প্রশ্ন প্রক্রিয়াকরণে ত্রুটি: {e}")
        return jsonify({"error": "প্রশ্ন প্রক্রিয়াকরণ ব্যর্থ হয়েছে। অনুগ্রহ করে পরে আবার চেষ্টা করুন।"}), 500

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"status": "alive"})

def keep_alive():
    url = "https://your-app-name.onrender.com/ping"  # আপনার অ্যাপের URL দিয়ে প্রতিস্থাপন করুন
    while True:
        time.sleep(600)  # প্রতি ১০ মিনিটে পিং করা
        try:
            requests.get(url)
        except requests.RequestException as e:
            logging.error(f"কিপ-অ্যালাইভ পিং ব্যর্থ হয়েছে: {e}")

if __name__ == '__main__':
    threading.Thread(target=keep_alive, daemon=True).start()
    app.run(host='0.0.0.0', port=8080)
