import requests, time, os
import datetime
from flask import Flask, request
import hashlib
from threading import Thread
import schedule

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
            try:
                send_message(chat_id, "✅ Đã kiểm tra xong!", reply_markup=None)
            except Exception as e:
                send_message(chat_id, f"⚠️ Lỗi khi kiểm tra: {e}")

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


    msg = (
        f"🏰 <b>{name}</b> (Cấp {level})\n"
        f"👑 Thủ lĩnh: <b>{leader}</b>\n"
        f"👥 Thành viên: {members}\n"
        f"⚙️ Quyền: {type_clan}\n"
        f"🏆 Cúp yêu cầu: {required_trophies}\n"
        f"🔥 Chuỗi thắng: {warWinStreak}\n\n"
        f"📜 Mô tả: {desc}\n\n"
        f"⚔️ Nhật ký chiến: {warWins} thắng / {warLosses} thua / {warTies} hòa\n"
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
        f"🎯 Lượt đánh: {clan.get('attacks', 0)}/{team_size * 2} - Địch: {opponent.get('attacks', 0)}/{team_size * 2}\n"
    )

    if state == "preparation":
        msg += "🕐 Trạng thái: <b>Trong ngày chuẩn bị</b>\n"
    elif state == "inWar":
        msg += "🔥 Trạng thái: <b>Trong ngày chiến đấu</b>\n"
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

        # Lấy dữ liệu clan (danh sách thành viên)
        clan_url = f"https://api.clashofclans.com/v1/clans/{clan_tag_encoded}"
        clan_res = requests.get(clan_url, headers=headers, timeout=10)
        clan_res.raise_for_status()
        clan_data = clan_res.json()
    except Exception as e:
        send_message(chat_id, f"⚠️ Lỗi lấy dữ liệu: {e}")
        return

    members = clan_data.get("memberList", [])

    # ==================== TOP DONATE ====================
    if data_callback == "top_donate":
        if not members:
            send_message(chat_id, "❌ Không tìm thấy danh sách thành viên.")
            return
        top = sorted(members, key=lambda m: m.get("donations", 0), reverse=True)[:5]
        msg = "🪖 <b>Top 5 Donate:</b>\n"
        for i, m in enumerate(top, start=1):
            msg += f"{i}. {m['name']} - {m.get('donations', 0)} lính\n"
        send_message(chat_id, msg)
        return

    # ==================== TOP KINH ĐÔ HỘI ====================
    if data_callback == "top_capital":
        try:
            # API lấy thống kê Kinh đô hội
            capital_url = f"https://api.clashofclans.com/v1/clans/{clan_tag_encoded}/capitalraidseasons?limit=1"
            capital_res = requests.get(capital_url, headers=headers, timeout=10)
            capital_res.raise_for_status()
            capital_data = capital_res.json()

            if "items" not in capital_data or not capital_data["items"]:
                send_message(chat_id, "⚠️ Chưa có dữ liệu Kinh Đô Hội (Capital).")
                return

            # Lấy danh sách đóng góp từ season gần nhất
            raids = capital_data["items"][0]
            members_cap = raids.get("members", [])

            if not members_cap:
                send_message(chat_id, "⚠️ Không có dữ liệu đóng góp thành viên.")
                return

            # Sắp xếp top 10 theo tổng số vàng đóng góp
            top = sorted(members_cap, key=lambda m: m.get("capitalResourcesLooted", 0), reverse=True)[:10]

            total = sum(m.get("capitalResourcesLooted", 0) for m in top)
            msg = "🏆 <b>Top 10 Kinh Đô Hội:</b>\n"
            for i, m in enumerate(top, start=1):
                gold = m.get("capitalResourcesLooted", 0)
                msg += f"{i}. {m['name']} - 💰 {gold}\n"
            msg += f"\n📈 Tổng đóng góp top 10: {total}"
            send_message(chat_id, msg)

        except Exception as e:
            send_message(chat_id, f"⚠️ Lỗi lấy dữ liệu Kinh Đô Hội: {e}")
        return

    # ==================== TOP CÚP ====================
    if data_callback == "top_trophies":
        top = sorted(members, key=lambda m: m.get("trophies", 0), reverse=True)[:5]
        msg = "⚔️ <b>Top 5 Chiến tích:</b>\n"
        for i, m in enumerate(top, start=1):
            msg += f"{i}. {m['name']} - 🏆 {m.get('trophies', 0)} cúp\n"
        send_message(chat_id, msg)
        return

    # ==================== TOP TOWN HALL ====================
    if data_callback == "top_hall":
        top = sorted(members, key=lambda m: m.get("townHallLevel", 0), reverse=True)[:5]
        msg = "🏰 <b>Top 5 Town Hall:</b>\n"
        for i, m in enumerate(top, start=1):
            msg += f"{i}. {m['name']} - TH {m.get('townHallLevel', '?')}\n"
        send_message(chat_id, msg)
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

    # Thiết lập webhook Telegram
    try:
        set_webhook()
    except Exception:
        pass

    # Chạy Flask server
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
