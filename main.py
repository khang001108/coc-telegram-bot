import os
import requests
from flask import Flask, request

app = Flask(__name__)

# ==============================
# CẤU HÌNH
# ==============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CLAN_TAG = os.getenv("CLAN_TAG")
COC_API_KEY = os.getenv("COC_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 10000))

BASE_TELEGRAM = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ==============================
# 1️⃣ TRANG CHỦ
# ==============================
@app.route('/')
def home():
    return "✅ COC Telegram Bot đang hoạt động!"

# ==============================
# 2️⃣ WEBHOOK TỪ TELEGRAM
# ==============================
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    print("📩 Dữ liệu Telegram:", data)

    if not data:
        return "No data", 400

    message = data.get("message", {})
    callback = data.get("callback_query")

    # Nếu người dùng bấm nút
    if callback:
        chat_id = callback["message"]["chat"]["id"]
        data_callback = callback["data"]
        handle_callback(chat_id, data_callback)
        return "OK", 200

    # Nếu người dùng gửi tin nhắn
    if "text" in message:
        text = message["text"]
        chat_id = message["chat"]["id"]

        if text.startswith("/menu"):
            send_message(chat_id, "📋 Menu:\n/war - Thông tin chiến tranh\n/clan - Thông tin Clan")

        elif text == "/clan":
            send_coc_data_to_telegram(chat_id)

        elif text == "/war":
            send_war_info(chat_id)

    return "OK", 200

# ==============================
# 3️⃣ GỬI TIN NHẮN TELEGRAM
# ==============================
def send_message(chat_id, text, reply_markup=None):
    url = f"{BASE_TELEGRAM}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    r = requests.post(url, json=payload)
    if not r.ok:
        print("⚠️ Gửi tin nhắn lỗi:", r.text)

# ==============================
# 4️⃣ THÔNG TIN CLAN
# ==============================
def send_coc_data_to_telegram(chat_id):
    headers = {"Authorization": f"Bearer {COC_API_KEY}"}
    clan_tag_encoded = CLAN_TAG.replace("#", "%23")
    url = f"https://api.clashofclans.com/v1/clans/{clan_tag_encoded}"

    res = requests.get(url, headers=headers)
    data = res.json()

    name = data.get("name", "Không rõ")
    members = data.get("members", 0)
    desc = data.get("description", "Không có mô tả")

    msg = f"🏰 <b>Clan:</b> {name}\n👥 <b>Thành viên:</b> {members}\n📜 <b>Mô tả:</b> {desc}"
    send_message(chat_id, msg)

# ==============================
# 5️⃣ THÔNG TIN WAR
# ==============================
def send_war_info(chat_id):
    headers = {"Authorization": f"Bearer {COC_API_KEY}"}
    clan_tag_encoded = CLAN_TAG.replace("#", "%23")
    url = f"https://api.clashofclans.com/v1/clans/{clan_tag_encoded}/currentwar"

    res = requests.get(url, headers=headers)
    data = res.json()

    state = data.get("state", "notInWar")
    if state == "notInWar":
        send_message(chat_id, "❌ Hiện không có war nào đang diễn ra.")
        return

    clan = data.get("clan", {})
    opponent = data.get("opponent", {})
    team_size = data.get("teamSize", 0)

    msg = (
        f"⚔️ <b>{clan.get('name', '?')}</b> 🆚 <b>{opponent.get('name', '?')}</b>\n"
        f"⭐ <b>{clan.get('stars', 0)}</b> - <b>{opponent.get('stars', 0)}</b>\n"
        f"🎯 Lượt đánh: {clan.get('attacks', 0)}/{team_size} - Địch: {opponent.get('attacks', 0)}/{team_size}\n"
    )

    if state == "preparation":
        msg += "🕐 Trạng thái: <b>Trong ngày chuẩn bị</b>\n"
    elif state == "inWar":
        msg += "🔥 Trạng thái: <b>Trong ngày chiến</b>\n"
    elif state == "warEnded":
        msg += "🏁 Trận chiến đã kết thúc!\n"

    msg += f"👥 Thành viên tham gia: {team_size}"

    # Thêm nút
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "🔝 Top War", "callback_data": "top_war"},
                {"text": "⚔️ Chưa đánh", "callback_data": "not_attack"}
            ]
        ]
    }

    send_message(chat_id, msg, reply_markup)

# ==============================
# 6️⃣ XỬ LÝ NÚT BẤM
# ==============================
def handle_callback(chat_id, data_callback):
    headers = {"Authorization": f"Bearer {COC_API_KEY}"}
    clan_tag_encoded = CLAN_TAG.replace("#", "%23")
    url = f"https://api.clashofclans.com/v1/clans/{clan_tag_encoded}/currentwar"
    res = requests.get(url, headers=headers)
    data = res.json()

    if "clan" not in data:
        send_message(chat_id, "⚠️ Không có dữ liệu war.")
        return

    members = data["clan"].get("members", [])

    if data_callback == "top_war":
        top_players = sorted(members, key=lambda x: sum(a["stars"] for a in x.get("attacks", [])), reverse=True)
        msg = "🏅 <b>Top 3 người đánh war tốt nhất:</b>\n"
        for i, m in enumerate(top_players[:3], start=1):
            stars = sum(a["stars"] for a in m.get("attacks", []))
            msg += f"{i}. {m['name']} - ⭐ {stars}\n"
        send_message(chat_id, msg)

    elif data_callback == "not_attack":
        not_attacked = [m["name"] for m in members if "attacks" not in m or len(m["attacks"]) == 0]
        if not not_attacked:
            msg = "✅ Tất cả thành viên đã đánh!"
        else:
            msg = "⚔️ <b>Thành viên chưa đánh:</b>\n" + "\n".join(not_attacked)
        send_message(chat_id, msg)

# ==============================
# 7️⃣ ĐĂNG KÝ WEBHOOK
# ==============================
def set_webhook():
    requests.get(f"{BASE_TELEGRAM}/deleteWebhook")
    r = requests.get(f"{BASE_TELEGRAM}/setWebhook?url={WEBHOOK_URL}/webhook")
    print("🔗 Webhook:", r.json())

# ==============================
# 8️⃣ CHẠY APP
# ==============================
if __name__ == '__main__':
    print("🚀 Khởi động bot Telegram Clash of Clans...")
    set_webhook()
    app.run(host='0.0.0.0', port=PORT)
