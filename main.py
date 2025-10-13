from flask import Flask, request
import os
import requests
import urllib.parse

# ===========================
# CẤU HÌNH
# ===========================
COC_API_KEY = os.getenv("COC_API_KEY")
CLAN_TAG = os.getenv("CLAN_TAG", "#2JUVCQ9VC")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)
BASE_TELEGRAM = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else None

# ===========================
# GỬI TELEGRAM
# ===========================
def send_telegram(text, chat_id=CHAT_ID):
    url = f"{BASE_TELEGRAM}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print("Lỗi Telegram:", e)
        return False

# ===========================
# LẤY DỮ LIỆU CLAN
# ===========================
def get_clan_status():
    headers = {"Authorization": f"Bearer {COC_API_KEY}"}
    encoded_tag = urllib.parse.quote(CLAN_TAG)
    url = f"https://api.clashofclans.com/v1/clans/{encoded_tag}/members"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            members = data.get("items", [])
            total = len(members)
            return {"total": total}, None
        else:
            return None, f"❌ Lỗi COC API: {r.status_code} - {r.text}"
    except Exception as e:
        return None, f"⚠️ Lỗi khi gọi COC API: {e}"

# ===========================
# LỆNH CHỦ ĐỘNG /check
# ===========================
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = request.get_json(force=True)

    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "").strip().lower()

        if text.startswith("/check"):
            status, err = get_clan_status()
            if err:
                send_telegram(err, chat_id)
            else:
                msg_text = f"⚔️ Báo cáo Clan:\n👥 Tổng thành viên: {status['total']}"
                send_telegram(msg_text, chat_id)

    return "ok"

# ===========================
# FLASK KEEP-ALIVE
# ===========================
@app.route("/")
def home():
    return "✅ Clash of Clans Bot đang chạy!"

# ===========================
# TỰ ĐỘNG GỌI 1 LẦN KHI START
# ===========================
if __name__ == "__main__":
    status, err = get_clan_status()
    if status:
        send_telegram(f"🚀 Bot khởi động!\n👥 Tổng thành viên: {status['total']}")
    else:
        send_telegram(f"⚠️ Khởi động bot lỗi: {err}")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)