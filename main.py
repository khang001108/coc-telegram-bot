import os
import requests
import datetime
from flask import Flask, request
import hashlib
import time
from threading import Thread

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
# KIỂM TRA THAY ĐỔI CLAN (TỐI ƯU & AN TOÀN)
# ==============================
import requests, time, os

last_clan_type = None
last_war = {"wins": 0, "losses": 0, "ties": 0, "streak": 0}
last_members = {}  # lưu {tag: name}
error_count = 0

def check_clan_changes():
    global last_clan_type, last_war, last_members, error_count
    headers = {"Authorization": f"Bearer {COC_API_KEY}"}
    clan_tag_encoded = CLAN_TAG.replace("#", "%23")
    url = f"https://api.clashofclans.com/v1/clans/{clan_tag_encoded}"

    while True:
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 429:
                print("⚠️ Bị giới hạn API — chờ 2 phút rồi thử lại...")
                time.sleep(120)
                continue

            data = res.json()
            if "memberList" not in data:
                print("⚠️ API trả về lỗi hoặc không có dữ liệu.")
                time.sleep(60)
                continue

            members = {m["tag"]: m["name"] for m in data["memberList"]}
            clan_type = data.get("type", "open")

            # --- Lần đầu khởi tạo ---
            if not last_members:
                last_members = members
                last_clan_type = clan_type
                last_war = {
                    "wins": data.get("warWins", 0),
                    "losses": data.get("warLosses", 0),
                    "ties": data.get("warTies", 0),
                    "streak": data.get("warWinStreak", 0),
                }
                print("✅ Khởi tạo dữ liệu ban đầu.")
                time.sleep(20)
                continue

            changes = []

            # --- 1️⃣ Thành viên mới vào ---
            joined = [f"{members[tag]} ({tag})" for tag in members if tag not in last_members]
            if joined:
                changes.append("🟢 Thành viên mới vào clan:\n" + "\n".join(joined))

            # --- 2️⃣ Thành viên rời clan ---
            left = [f"{last_members[tag]} ({tag})" for tag in last_members if tag not in members]
            if left:
                changes.append("🔴 Thành viên rời clan:\n" + "\n".join(left))

            # --- 3️⃣ Thay đổi loại clan ---
            if clan_type != last_clan_type:
                changes.append(f"⚙️ Loại clan thay đổi: {last_clan_type} → {clan_type}")
                last_clan_type = clan_type

            # --- 4️⃣ Kết quả war hoặc chuỗi thắng ---
            current_war = {
                "wins": data.get("warWins", 0),
                "losses": data.get("warLosses", 0),
                "ties": data.get("warTies", 0),
                "streak": data.get("warWinStreak", 0),
            }

            if (
                current_war["wins"] != last_war["wins"]
                or current_war["losses"] != last_war["losses"]
                or current_war["ties"] != last_war["ties"]
            ):
                if current_war["wins"] > last_war["wins"]:
                    result = "🏆 Clan vừa thắng 1 trận war!"
                elif current_war["losses"] > last_war["losses"]:
                    result = "💀 Clan vừa thua 1 trận war!"
                else:
                    result = "🤝 Clan vừa hòa 1 trận war!"
                changes.append(f"{result}\n🔥 Chuỗi thắng hiện tại: {current_war['streak']}")
                last_war = current_war

            # --- 5️⃣ Cập nhật danh sách thành viên ---
            last_members = members

            # --- 6️⃣ Gửi thông báo nếu có thay đổi ---
            if changes:
                msg = "\n\n".join(changes)
                send_message(int(CHAT_ID), msg)

            error_count = 0  # reset lỗi nếu thành công

        except Exception as e:
            error_count += 1
            print("⚠️ Lỗi kiểm tra clan:", e)
            # Nếu lỗi liên tiếp quá 5 lần → tạm dừng lâu hơn
            if error_count >= 5:
                print("⚠️ Quá nhiều lỗi liên tiếp, tạm dừng 2 phút...")
                time.sleep(120)
                error_count = 0

        time.sleep(20)  # kiểm tra mỗi 20 giây

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

    # Lấy ngày tạo clan
    created = data.get("createdDate")
    if created:
        created_date = datetime.datetime.strptime(created, "%Y%m%dT%H%M%S.%fZ")
        created_date = created_date.replace(tzinfo=datetime.timezone.utc)  # gán timezone UTC
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        days_alive = (now_utc - created_date).days
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
    import threading

    # Thiết lập webhook Telegram
    try:
        set_webhook()
    except Exception:
        pass

    # Chạy luồng kiểm tra thay đổi clan ở nền
    try:
        threading.Thread(target=check_clan_changes, daemon=True).start()
    except Exception:
        pass

    # Khởi chạy Flask server
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
