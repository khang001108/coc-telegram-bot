import os
import requests
from flask import Flask, request

# ==== Cấu hình từ biến môi trường ====
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CLAN_TAG = os.getenv("CLAN_TAG")
COC_API_KEY = os.getenv("COC_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 10000))

app = Flask(__name__)

# ==== Hàm gọi API Clash of Clans ====
def get_clan_info():
    headers = {"Authorization": f"Bearer {COC_API_KEY}"}
    tag = CLAN_TAG.replace("#", "%23")
    url = f"https://api.clashofclans.com/v1/clans/{tag}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    return None

# ==== Xử lý webhook Telegram ====
@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    if not update:
        return "No update", 200

    message = update.get("message", {})
    text = message.get("text", "").strip().lower()

    if text == "/check":
        clan_info = get_clan_info()
        if clan_info:
            name = clan_info.get("name", "")
            level = clan_info.get("clanLevel", "")
            members = clan_info.get("members", "")
            msg = f"🏰 Clan: {name}\n⭐ Level: {level}\n👥 Thành viên: {members}"
        else:
            msg = "❌ Không thể lấy thông tin clan."
        send_message(msg)
    else:
        send_message("⚙️ Gõ /check để xem thông tin clan.")

    return "OK", 200

# ==== Hàm gửi tin nhắn ====
def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

# ==== Webhook control ====
def delete_webhook():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
    requests.get(url, timeout=5)

def set_webhook():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    params = {"url": f"{WEBHOOK_URL}/webhook"}
    requests.get(url, params=params, timeout=5)

# ==== Chạy Flask app ====
if __name__ == "__main__":
    delete_webhook()
    set_webhook()
    app.run(host="0.0.0.0", port=PORT)
