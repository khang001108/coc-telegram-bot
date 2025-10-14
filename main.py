import os
import requests
import datetime
from flask import Flask, request
import hashlib
import threading
import time

last_clan_hash = None


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
    print("📩 Dữ liệu Telegram:", data)

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
            send_message(chat_id, "📋 Menu:\n/clan - Thông tin hội\n/members - Danh sách thành viên\n/war - Chiến tranh hiện tại")

        elif text.startswith("/clan"):
            send_clan_info(chat_id)

        elif text.startswith("/war"):
            send_war_info(chat_id)

        elif text.startswith("/members"):
            send_members_menu(chat_id)

    return "OK", 200

# ==============================
# 3️⃣ GỬI TIN NHẮN
# ==============================
def send_message(chat_id, text, reply_markup=None):
    url = f"{BASE_TELEGRAM}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    r = requests.post(url, json=payload)
    if not r.ok:
        print("⚠️ Gửi tin nhắn lỗi:", r.text)

# ==============================
# 4️⃣ THÔNG TIN CLAN
# ==============================
def send_clan_info(chat_id):
    headers = {"Authorization": f"Bearer {COC_API_KEY}"}
    clan_tag_encoded = CLAN_TAG.replace("#", "%23")
    url = f"https://api.clashofclans.com/v1/clans/{clan_tag_encoded}"

    res = requests.get(url, headers=headers)
    data = res.json()

    if "name" not in data:
        send_message(chat_id, "⚠️ Không thể lấy thông tin Clan.")
        return

    name = data["name"]
    level = data.get("clanLevel", 0)
    leader = next((m["name"] for m in data["memberList"] if m["role"] == "leader"), "Không rõ")
    members = data.get("members", 0)
    desc = data.get("description", "Không có mô tả")
    warWins = data.get("warWins", 0)
    warLosses = data.get("warLosses", 0)
    warTies = data.get("warTies", 0)
    warWinStreak = data.get("warWinStreak", 0)
    type_clan = data.get("type", "open")
    required_trophies = data.get("requiredTrophies", 0)

    # Tính ngày thành lập (giả sử dùng createdDate nếu API có)
    created = data.get("createdDate", None)
    if created:
        created_date = datetime.datetime.strptime(created, "%Y%m%dT%H%M%S.%fZ")
        days_alive = (datetime.datetime.utcnow() - created_date).days
    else:
        days_alive = "?"

    msg = (
        f"🏰 <b>{name}</b> (Cấp {level})\n"
        f"👑 Thủ lĩnh: <b>{leader}</b>\n"
        f"👥 Thành viên: {members}\n"
        f"⚙️ Quyền: {type_clan}\n"
        f"🏆 Cúp yêu cầu: {required_trophies}\n"
        f"🔥 Chuỗi thắng: {warWinStreak}\n\n"
        f"📜 Mô tả: {desc}\n\n"
        f"⚔️ Nhật ký chiến: {warWins} thắng / {warLosses} thua / {warTies} hòa\n"
        f"📅 Ngày hoạt động: {days_alive} ngày"
    )
    send_message(chat_id, msg)

# ==============================
# KIỂM TRA THAY ĐỔI CLAN
# ==============================

def check_clan_changes():
    global last_clan_hash
    headers = {"Authorization": f"Bearer {COC_API_KEY}"}
    clan_tag_encoded = CLAN_TAG.replace("#", "%23")
    url = f"https://api.clashofclans.com/v1/clans/{clan_tag_encoded}"

    while True:
        try:
            res = requests.get(url, headers=headers, timeout=10)
            data = res.json()
            leader = next((m["name"] for m in data.get("memberList", []) if m["role"] == "leader"), "")
            relevant = f"{data.get('name')}-{data.get('type')}-{leader}-{data.get('warWins')}-{data.get('warLosses')}-{data.get('warTies')}"
            hash_now = hashlib.md5(relevant.encode()).hexdigest()
            if last_clan_hash and hash_now != last_clan_hash:
                send_message(int(CHAT_ID), f"⚠️ Clan đã thay đổi thông tin hoặc cài đặt!\nTên: {data.get('name')}\nLeader: {leader}\nLoại: {data.get('type')}\nWar Wins: {data.get('warWins')}\nWar Losses: {data.get('warLosses')}\nWar Ties: {data.get('warTies')}")
            last_clan_hash = hash_now
        except Exception as e:
            print("⚠️ Lỗi kiểm tra clan:", e)
        time.sleep(300)


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
        f"⭐ {clan.get('stars', 0)} - {opponent.get('stars', 0)}\n"
        f"🎯 Lượt đánh: {clan.get('attacks', 0)}/{team_size} - Địch: {opponent.get('attacks', 0)}/{team_size}\n"
    )

    if state == "preparation":
        msg += "🕐 Trạng thái: <b>Trong ngày chuẩn bị</b>\n"
    elif state == "inWar":
        msg += "🔥 Trạng thái: <b>Trong ngày chiến</b>\n"
    elif state == "warEnded":
        msg += "🏁 Trận chiến đã kết thúc!\n"

    msg += f"👥 Thành viên tham gia: {team_size}"

    reply_markup = {
        "inline_keyboard": [
            [{"text": "🔝 Top War", "callback_data": "top_war"},
             {"text": "⚔️ Chưa đánh", "callback_data": "not_attack"}]
        ]
    }
    send_message(chat_id, msg, reply_markup)

# ==============================
# 6️⃣ DANH SÁCH THÀNH VIÊN
# ==============================
def send_members_menu(chat_id):
    reply_markup = {
        "inline_keyboard": [
            [{"text": "🪖 Top Donate", "callback_data": "top_donate"},
             {"text": "⚔️ Top Chiến tích", "callback_data": "top_trophies"}],
            [{"text": "🕒 Top Online", "callback_data": "top_online"},
             {"text": "🏰 Top Hall", "callback_data": "top_hall"}]
        ]
    }
    send_message(chat_id, "📋 Chọn bảng xếp hạng thành viên:", reply_markup)

# ==============================
# 7️⃣ CALLBACK XỬ LÝ NÚT (CẬP NHẬT /currentwar)
# ==============================
def handle_callback(chat_id, data_callback):
    headers = {"Authorization": f"Bearer {COC_API_KEY}"}
    clan_tag_encoded = CLAN_TAG.replace("#", "%23")

    try:
        # Lấy dữ liệu war hiện tại
        war_url = f"https://api.clashofclans.com/v1/clans/{clan_tag_encoded}/currentwar"
        war_res = requests.get(war_url, headers=headers, timeout=10)
        war_res.raise_for_status()
        war_data = war_res.json()

        # Lấy dữ liệu danh sách clan để các nút /members
        clan_url = f"https://api.clashofclans.com/v1/clans/{clan_tag_encoded}"
        clan_res = requests.get(clan_url, headers=headers, timeout=10)
        clan_res.raise_for_status()
        clan_data = clan_res.json()
    except Exception as e:
        send_message(chat_id, f"⚠️ Lỗi lấy dữ liệu: {e}")
        return

    # ==================== /members buttons ====================
    members = clan_data.get("memberList", [])
    if data_callback == "top_donate":
        top = sorted(members, key=lambda m: m.get("donations", 0), reverse=True)[:5]
        msg = "🪖 <b>Top 5 Donate:</b>\n"
        for i, m in enumerate(top, start=1):
            msg += f"{i}. {m['name']} - {m.get('donations', 0)} lính\n"
        send_message(chat_id, msg)
        return

    if data_callback == "top_trophies":
        top = sorted(members, key=lambda m: m.get("trophies", 0), reverse=True)[:5]
        msg = "⚔️ <b>Top 5 Chiến tích:</b>\n"
        for i, m in enumerate(top, start=1):
            msg += f"{i}. {m['name']} - 🏆 {m.get('trophies', 0)} cúp\n"
        send_message(chat_id, msg)
        return

    if data_callback == "top_hall":
        top = sorted(members, key=lambda m: m.get("townHallLevel", 0), reverse=True)[:5]
        msg = "🏰 <b>Top 5 Town Hall:</b>\n"
        for i, m in enumerate(top, start=1):
            msg += f"{i}. {m['name']} - TH {m.get('townHallLevel', '?')}\n"
        send_message(chat_id, msg)
        return

    if data_callback == "top_online":
        send_message(chat_id,
            "🕒 Clash API không cung cấp dữ liệu online trực tiếp.\n"
            "👉 Có thể thay bằng thống kê donate/hoạt động gần nhất.")
        return

    # ==================== /war buttons ====================
    if "clan" not in war_data:
        send_message(chat_id, "⚠️ Hiện không có war đang diễn ra.")
        return

    war_members = war_data["clan"].get("members", [])
    if data_callback == "top_war":
        top_players = sorted(
            war_members,
            key=lambda m: sum(a["stars"] for a in m.get("attacks", [])),
            reverse=True
        )
        msg = "🏅 <b>Top 3 người đánh war tốt nhất:</b>\n"
        for i, m in enumerate(top_players[:3], start=1):
            stars = sum(a["stars"] for a in m.get("attacks", []))
            msg += f"{i}. {m['name']} - ⭐ {stars}\n"
        send_message(chat_id, msg)
        return

    if data_callback == "not_attack":
        not_attacked = [
            m["name"] for m in war_members
            if "attacks" not in m or len(m["attacks"]) == 0
        ]
        if not not_attacked:
            msg = "✅ Tất cả thành viên trong war đã đánh!"
        else:
            msg = "⚔️ <b>Thành viên chưa đánh:</b>\n" + "\n".join(not_attacked)
        send_message(chat_id, msg)
        return

    send_message(chat_id, "⚠️ Nút không hợp lệ hoặc chưa được hỗ trợ.")

# ==============================
# 8️⃣ WEBHOOK
# ==============================
def set_webhook():
    requests.get(f"{BASE_TELEGRAM}/deleteWebhook")
    r = requests.get(f"{BASE_TELEGRAM}/setWebhook?url={WEBHOOK_URL}/webhook")
    print("🔗 Webhook:", r.json())

# ==============================
# 9️⃣ KHỞI ĐỘNG
# ==============================
if __name__ == '__main__':
    print("🚀 Khởi động bot Telegram Clash of Clans...")
    set_webhook()

    # Bắt đầu thread kiểm tra clan thay đổi
    threading.Thread(target=check_clan_changes, daemon=True).start()

    app.run(host='0.0.0.0', port=PORT)
    
