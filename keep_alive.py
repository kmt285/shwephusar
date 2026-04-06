from flask import Flask
from threading import Thread
import requests
import time
import os
import logging

app = Flask(__name__)
# Flask ရဲ့ မလိုအပ်တဲ့ Log တွေ မပေါ်အောင် ပိတ်ထားမယ်
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@app.route('/')
def home():
    # Render ကနေ ဝင်ကြည့်ရင် မြင်ရမယ့် စာသားပါ
    return "LeoMatch Bot is Running 24/7!"

def run():
    # Render က အလိုအလျောက် ပေးတဲ့ PORT ကို ယူပါမယ် (မရှိရင် 8080)
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def ping_self():
    """၁၀ မိနစ်တစ်ခါ ကိုယ့် URL ကိုယ် ပြန်ခေါ်မယ့် Function"""
    while True:
        # စက္ကန့် ၆၀၀ (၁၀ မိနစ်) ကြာတိုင်း အလုပ်လုပ်မယ်
        time.sleep(600)
        try:
            # Render က Web Service တင်ရင် RENDER_EXTERNAL_URL ကို အလိုအလျောက် ပေးပါတယ်
            url = os.environ.get("RENDER_EXTERNAL_URL")
            if url:
                requests.get(url)
                print(f"✅ Keep-alive ping sent to: {url}")
            else:
                # Local မှာ စမ်းနေတဲ့ အချိန်အတွက်
                requests.get(f"http://localhost:{os.environ.get('PORT', 8080)}")
        except Exception as e:
            print(f"⚠️ Ping error: {e}")

def keep_alive():
    """Thread များခွဲ၍ Server နှင့် Ping စနစ်ကို သက်ဝင်စေမည့် Function"""
    # Web Server ကို Thread သီးသန့်ခွဲ၍ Run မည်
    server_thread = Thread(target=run)
    server_thread.daemon = True
    server_thread.start()
    
    # Ping စနစ်ကို Thread သီးသန့်ခွဲ၍ Run မည်
    ping_thread = Thread(target=ping_self)
    ping_thread.daemon = True
    ping_thread.start()