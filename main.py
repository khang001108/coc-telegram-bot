from tkinter import W
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
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # URL công khai của bạn

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
# WEBHOOK XỬ LÝ TIN NHẮN TELEGRAM
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
# XÓA WEBHOOK CŨ
# ===========================
def delete_webhook():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
    try:
        r = requests.get(url, timeout=10)
        print("🗑️ Xóa webhook cũ:", r.text)
    except Exception as e:
        print("⚠️ Lỗi khi xóa webhook:", e)

# ===========================
# ĐĂNG KÝ WEBHOOK MỚI
# ===========================
def set_webhook():
    webhook_url = f"{WEBHOOK_URL}/{BOT_TOKEN}"  # ⚠️ đổi domain nếu bạn deploy khác
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    payload = {"url": webhook_url}

    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code == 200:
            print("✅ Đã đăng ký webhook thành công!")
        else:
            print("❌ Lỗi khi đăng ký webhook:", r.text)
    except Exception as e:
        print("⚠️ Lỗi kết nối Telegram:", e)

# ===========================
# KHỞI ĐỘNG
# ===========================
if __name__ == "__main__":
    delete_webhook()
    set_webhook()

    status, err = get_clan_status()
    if status:
        send_telegram(f"🚀 Bot khởi động!\n👥 Tổng thành viên: {status['total']}")
    else:
        send_telegram(f"⚠️ Khởi động bot lỗi: {err}")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
