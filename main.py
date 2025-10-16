import requests, time, os
from flask import Flask, request

app = Flask(__name__)

# ==============================
# CẤU HÌNH
# ==============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
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
# 2️⃣ WEBHOOK
# ==============================
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if not data:
        return "No data", 400

    message = data.get("message", {})
    callback = data.get("callback_query")

    # Nếu bấm nút
    if callback:
        chat_id = callback["message"]["chat"]["id"]
        data_callback = callback["data"]
        handle_callback(chat_id, data_callback)
        return "OK", 200

    # Nếu là lệnh
    if "text" in message:
        text = message["text"]
        chat_id = message["chat"]["id"]

        if text.startswith("/menu"):
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "🏰 Clan", "callback_data": "show_clan"}],
                    [{"text": "⚔️ War", "callback_data": "show_war"}],
                    [{"text": "👥 Members", "callback_data": "show_members"}]
                ]
            }
            send_message(chat_id, "📋 Chọn chức năng:", reply_markup)

        elif text.startswith("/check"):
            send_message(chat_id, "🔍 Đang kiểm tra clan...")
            send_message(chat_id, "✅ Đã kiểm tra xong!")

    return "OK", 200

# ==============================
# 3️⃣ GỬI TIN NHẮN
# ==============================
def send_message(chat_id, text, reply_markup=None):
    url = f"{BASE_TELEGRAM}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(url, json=payload)

# ==============================
# 4️⃣ XỬ LÝ CALLBACK BUTTON
# ==============================
def handle_callback(chat_id, data_callback):
    headers = {"Authorization": f"Bearer {COC_API_KEY}"}
    clan_tag_encoded = CLAN_TAG.replace("#", "%23")

    # CLAN INFO
    if data_callback == "show_clan":
        url = f"https://api.clashofclans.com/v1/clans/{clan_tag_encoded}"
        res = requests.get(url, headers=headers).json()
        msg = (
            f"🏰 <b>{res.get('name', '?')}</b> (Cấp {res.get('clanLevel', 0)})\n"
            f"👑 Thủ lĩnh: {next((m['name'] for m in res.get('memberList', []) if m['role'] == 'leader'), 'Không rõ')}\n"
            f"👥 Thành viên: {res.get('members', 0)}\n"
            f"🔥 Chuỗi thắng: {res.get('warWinStreak', 0)}\n"
            f"⚔️ War: {res.get('warWins', 0)} thắng / {res.get('warLosses', 0)} thua / {res.get('warTies', 0)} hòa"
        )
        send_message(chat_id, msg)
        return

    # WAR INFO
    if data_callback == "show_war":
        url = f"https://api.clashofclans.com/v1/clans/{clan_tag_encoded}/currentwar"
        res = requests.get(url, headers=headers).json()
        if res.get("state") == "notInWar":
            send_message(chat_id, "❌ Không có war đang diễn ra.")
            return

        clan = res.get("clan", {})
        opponent = res.get("opponent", {})
        team_size = res.get("teamSize", 0)
        msg = (
            f"⚔️ <b>{clan.get('name', '?')}</b> 🆚 <b>{opponent.get('name', '?')}</b>\n"
            f"⭐ {clan.get('stars', 0)} - {opponent.get('stars', 0)}\n"
            f"🎯 Lượt đánh: {clan.get('attacks', 0)}/{team_size*2} - Địch: {opponent.get('attacks', 0)}/{team_size*2}\n"
        )
        reply_markup = {
            "inline_keyboard": [
                [{"text": "🏅 Top War", "callback_data": "top_war"}],
                [{"text": "👥 Thành viên tham gia", "callback_data": "war_members"}]
            ]
        }
        send_message(chat_id, msg, reply_markup)
        return

    # MEMBERS MENU
    if data_callback == "show_members":
        reply_markup = {
            "inline_keyboard": [
                [{"text": "🎓 Kinh nghiệm cao nhất", "callback_data": "top_exp"}],
                [{"text": "🏰 Làng chính", "callback_data": "top_main"}],
                [{"text": "⚒️ Căn cứ thợ xây", "callback_data": "top_builder"}],
                [{"text": "🏆 Kinh đô hội", "callback_data": "top_capital"}],
            ]
        }
        send_message(chat_id, "📊 Chọn bảng xếp hạng:", reply_markup)
        return

    # === WAR DETAIL ===
    if data_callback in ["top_war", "war_members"]:
        url = f"https://api.clashofclans.com/v1/clans/{clan_tag_encoded}/currentwar"
        war_data = requests.get(url, headers=headers).json()
        members = war_data.get("clan", {}).get("members", [])

        if data_callback == "top_war":
            top = sorted(members, key=lambda m: sum(a["stars"] for a in m.get("attacks", [])), reverse=True)[:5]
            msg = "🏅 <b>Top 5 người đánh nhiều sao nhất:</b>\n"
            for i, m in enumerate(top, 1):
                stars = sum(a["stars"] for a in m.get("attacks", []))
                msg += f"{i}. {m['name']} - ⭐ {stars}\n"
            send_message(chat_id, msg)
            return

        if data_callback == "war_members":
            msg = "👥 <b>Danh sách thành viên war:</b>\n"
            for m in members:
                attacks = len(m.get("attacks", []))
                stars = sum(a["stars"] for a in m.get("attacks", []))
                msg += f"{m['name']} - {attacks}/2 - {stars}⭐\n"
            send_message(chat_id, msg)
            return

    # === MEMBERS DETAIL ===
    if data_callback.startswith("top_"):
        url = f"https://api.clashofclans.com/v1/clans/{clan_tag_encoded}"
        data = requests.get(url, headers=headers).json()
        members = data.get("memberList", [])

        if data_callback == "top_exp":
            top = sorted(members, key=lambda m: m.get("expLevel", 0), reverse=True)[:10]
            msg = "🎓 <b>Top 10 kinh nghiệm cao nhất:</b>\n"
            for i, m in enumerate(top, 1):
                msg += f"{i}. {m['name']} - LV {m['expLevel']}\n"

        elif data_callback == "top_main":
            top = sorted(members, key=lambda m: m.get("trophies", 0), reverse=True)[:10]
            msg = "🏰 <b>Top 10 làng chính:</b>\n"
            for i, m in enumerate(top, 1):
                msg += f"{i}. {m['name']} - 🏆 {m['trophies']}\n"

        elif data_callback == "top_builder":
            top = sorted(members, key=lambda m: m.get("builderBaseTrophies", 0), reverse=True)[:10]
            msg = "⚒️ <b>Top 10 căn cứ thợ xây:</b>\n"
            for i, m in enumerate(top, 1):
                msg += f"{i}. {m['name']} - ⚒️ {m['builderBaseTrophies']}\n"

        elif data_callback == "top_capital":
            top = sorted(members, key=lambda m: m.get("clanCapitalContributions", 0), reverse=True)[:10]
            msg = "🏆 <b>Top 10 Kinh đô hội:</b>\n"
            for i, m in enumerate(top, 1):
                msg += f"{i}. {m['name']} - 💰 {m['clanCapitalContributions']}\n"

        send_message(chat_id, msg)
        return

# ==============================
# 5️⃣ THIẾT LẬP WEBHOOK
# ==============================
def set_webhook():
    requests.get(f"{BASE_TELEGRAM}/deleteWebhook")
    requests.get(f"{BASE_TELEGRAM}/setWebhook?url={WEBHOOK_URL}/webhook")

# ==============================
# 6️⃣ KHỞI ĐỘNG
# ==============================
if __name__ == '__main__':
    try:
        set_webhook()
    except Exception:
        pass
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
