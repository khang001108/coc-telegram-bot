import os
import requests
from flask import Flask, request

app = Flask(__name__)

# Lấy biến môi trường
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CLAN_TAG = os.getenv("CLAN_TAG")
COC_API_KEY = os.getenv("COC_API_KEY")
PORT = int(os.getenv("PORT", 10000))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# -------------------------------
# 1️⃣ Giao diện chính
# -------------------------------
@app.route('/')
def home():
    return "✅ COC Telegram Bot đang hoạt động!"

# -------------------------------
# 2️⃣ Xử lý webhook từ Telegram
# -------------------------------
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    print("📩 Dữ liệu nhận từ Telegram:", data)

    if not data:
        return "No data", 400

    if 'message' in data and 'text' in data['message']:
        text = data['message']['text']
        chat_id = data['message']['chat']['id']

        if text == '/menu':
            message = "📋 Menu chính:\n1️⃣ Thông tin Clan\n2️⃣ Thành viên\n3️⃣ Nhật ký chiến"
            send_message(chat_id, message)

        elif text == '/clan':
            send_coc_data_to_telegram(chat_id)

    return "OK", 200


# -------------------------------
# 3️⃣ Hàm gửi tin nhắn Telegram
# -------------------------------
def send_message(chat_id, text):
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    r = requests.post(url, json={'chat_id': chat_id, 'text': text})
    if not r.ok:
        print("⚠️ Gửi tin nhắn thất bại:", r.text)


# -------------------------------
# 4️⃣ Hàm lấy thông tin Clan
# -------------------------------
def send_coc_data_to_telegram(chat_id):
    headers = {"Authorization": f"Bearer {COC_API_KEY}"}
    clan_tag_encoded = CLAN_TAG.replace('#', '%23')
    url = f"https://api.clashofclans.com/v1/clans/{clan_tag_encoded}"

    response = requests.get(url, headers=headers)
    data = response.json()

    name = data.get('name', 'Không xác định')
    members = data.get('members', 0)
    description = data.get('description', 'Không có mô tả')

    message = f"🏰 Clan: {name}\n👥 Thành viên: {members}\n📜 Mô tả: {description}"
    send_message(chat_id, message)


# -------------------------------
# 5️⃣ Hàm đăng ký webhook
# -------------------------------
def set_webhook():
    # Xoá webhook cũ
    delete_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
    delete_res = requests.get(delete_url)
    print("🧹 Xóa webhook cũ:", delete_res.json())

    # Đăng ký webhook mới
    set_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={WEBHOOK_URL}"
    set_res = requests.get(set_url)
    print("✅ Đăng ký webhook mới:", set_res.json())


# -------------------------------
# 6️⃣ Chạy app
# -------------------------------
if __name__ == '__main__':
    print("🚀 Bot Telegram + Clash of Clans đang khởi động...")
    set_webhook()  # <== thêm dòng này để tự set mỗi lần khởi động
    app.run(host='0.0.0.0', port=PORT)
