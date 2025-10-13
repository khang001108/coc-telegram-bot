import os, requests
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CLAN_TAG = os.getenv("CLAN_TAG")
COC_API_KEY = os.getenv("COC_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 10000))

app = Flask(__name__)

def get_clan_info():
    tag = CLAN_TAG.replace("#", "%23")
    r = requests.get(f"https://api.clashofclans.com/v1/clans/{tag}",
                     headers={"Authorization": f"Bearer {COC_API_KEY}"})
    return r.json() if r.status_code == 200 else None

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    text = data.get("message", {}).get("text", "").strip().lower() if data else ""
    msg = "⚙️ Gõ /check để xem thông tin clan."
    if text == "/check":
        c = get_clan_info()
        msg = f"🏰 Clan: {c['name']}\n⭐ Level: {c['clanLevel']}\n👥 Thành viên: {c['members']}" if c else "❌ Không thể lấy thông tin clan."
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                  json={"chat_id": CHAT_ID, "text": msg}, timeout=5)
    return "OK", 200

def update_webhook():
    base = f"https://api.telegram.org/bot{BOT_TOKEN}"
    requests.get(f"{base}/deleteWebhook", timeout=5)
    requests.get(f"{base}/setWebhook", params={"url": f"{WEBHOOK_URL}/webhook"}, timeout=5)

if __name__ == "__main__":
    update_webhook()
    app.run(host="0.0.0.0", port=PORT)
