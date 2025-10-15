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
            send_message(chat_id,
                "📋 Menu:\n"
                "/clan - Thông tin hội\n"
                "/members - Danh sách thành viên\n"
                "/war - Chiến tranh hiện tại\n"
                "/check - Kiểm tra clan thủ công"
            )

        elif text.startswith("/clan"):
            send_clan_info(chat_id)

        elif text.startswith("/war"):
            send_war_info(chat_id)

        elif text.startswith("/members"):
            send_members_menu(chat_id)

        elif text.startswith("/check"):
            send_message(chat_id, "🔍 Đang kiểm tra clan...")
            try:
                check_clan_changes()
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
    if not r.ok:
        print("⚠️ Gửi tin nhắn lỗi:", r.text)

# ==============================
# KIỂM TRA THAY ĐỔI CLAN (TỐI ƯU PHẢN HỒI NHANH)
# ==============================
import requests, time, os

last_clan_type = None
last_war = {"wins": 0, "losses": 0, "ties": 0, "streak": 0}
last_members = {}
last_attacks = {}  # Lưu lượt đánh trước đó {tag: [stars_l1, stars_l2]}
last_donations_requested = {}  # Lưu số lần xin lính trước đó
error_count = 0
is_checking = False  # 🔒 chống trùng khi schedule và /check cùng gọi

def check_clan_changes():
    global last_clan_type, last_war, last_members, last_attacks, last_donations_requested, error_count, is_checking

    if is_checking:
        print("⚙️ Đang check, bỏ qua lần này.")
        return
    is_checking = True

    headers = {"Authorization": f"Bearer {COC_API_KEY}"}
    clan_tag_encoded = CLAN_TAG.replace("#", "%23")
    clan_url = f"https://api.clashofclans.com/v1/clans/{clan_tag_encoded}"

    try:
        # --- Lấy dữ liệu clan ---
        res = requests.get(clan_url, headers=headers, timeout=8)
        if res.status_code == 429:
            print("⏳ Bị giới hạn rate, tạm nghỉ 1 lượt check.")
            return
        data = res.json()
        if "memberList" not in data:
            return

        members = {m["tag"]: m["name"] for m in data["memberList"]}
        clan_type = data.get("type", "open")

        # --- Lần đầu ---
        if not last_members:
            last_members.update(members)
            last_clan_type = clan_type
            last_war.update({
                "wins": data.get("warWins", 0),
                "losses": data.get("warLosses", 0),
                "ties": data.get("warTies", 0),
                "streak": data.get("warWinStreak", 0),
            })
            for m in data["memberList"]:
                last_attacks[m["tag"]] = [0, 0]
                last_donations_requested[m["tag"]] = m.get("donationsRequested", 0)
            print("✅ Khởi tạo dữ liệu clan lần đầu.")
            return

        changes = []

        # --- Thành viên mới ---
        joined = [f"{members[tag]} ({tag})" for tag in members if tag not in last_members]
        if joined:
            changes.append("🟢 Thành viên mới:\n" + "\n".join(joined))

        # --- Thành viên rời ---
        left = [f"{last_members[tag]} ({tag})" for tag in last_members if tag not in members]
        if left:
            changes.append("🔴 Thành viên rời:\n" + "\n".join(left))

        # --- Loại clan thay đổi ---
        if clan_type != last_clan_type:
            changes.append(f"⚙️ Loại clan thay đổi: {last_clan_type} → {clan_type}")
            last_clan_type = clan_type

        # --- DonationsRequested (xin lính) ---
        requests_msg = []
        for m in data["memberList"]:
            tag = m["tag"]
            requested_now = m.get("donationsRequested", 0)
            prev = last_donations_requested.get(tag, 0)
            if requested_now > prev:
                requests_msg.append(f"🪖 {m['name']} vừa xin {requested_now - prev} lính")
            # Cập nhật trạng thái
            last_donations_requested[tag] = requested_now
        if requests_msg:
            changes.append("📢 Ai vừa xin lính:\n" + "\n".join(requests_msg))

        # --- Lấy dữ liệu war hiện tại ---
        war_url = f"https://api.clashofclans.com/v1/clans/{clan_tag_encoded}/currentwar"
        war_res = requests.get(war_url, headers=headers, timeout=8)
        if war_res.ok:
            war_data = war_res.json()
            state = war_data.get("state", "notInWar")

            if state in ["preparation", "inWar"]:
                just_attacked = []
                clan_total = 0
                opp_total = 0

                # Tổng sao hiện tại & ai vừa đánh
                for m in war_data["clan"].get("members", []):
                    attacks = m.get("attacks", [])
                    clan_total += sum(a.get("stars", 0) for a in attacks)
                    prev = last_attacks.get(m["tag"], [0,0])
                    for a in attacks:
                        idx = a["order"] - 1
                        stars = a.get("stars",0)
                        if stars > prev[idx]:
                            just_attacked.append(f"  - {m['name']}: lượt {a['order']} ⭐{stars}")
                    # Cập nhật last_attacks
                    last_attacks[m["tag"]] = [a.get("stars",0) for a in attacks] + [0]*(2-len(attacks))

                # Tổng sao đối thủ
                for m in war_data["opponent"].get("members", []):
                    attacks = m.get("attacks", [])
                    opp_total += sum(a.get("stars",0) for a in attacks)

                if just_attacked:
                    msg = f"🔥 War đang diễn ra:\n👥 Vừa đánh:\n" + "\n".join(just_attacked)
                    msg += f"\nTổng sao hiện tại: Clan {clan_total} - Địch {opp_total}"
                    changes.append(msg)

            elif state == "warEnded":
                # Tổng sao cuối
                clan_total = sum(sum(a.get("stars",0) for a in m.get("attacks",[])) for m in war_data["clan"].get("members",[]))
                opp_total = sum(sum(a.get("stars",0) for a in m.get("attacks",[])) for m in war_data["opponent"].get("members",[]))
                # Kết quả war
                if clan_total > opp_total:
                    result = "🏆 Thắng"
                elif clan_total < opp_total:
                    result = "💀 Thua"
                else:
                    result = "🤝 Hòa"
                # Tấn công anh dũng nhất
                top_attack = max(war_data["clan"]["members"], key=lambda m: sum(a.get("stars",0) for a in m.get("attacks",[])))
                top_attack_stars = sum(a.get("stars",0) for a in top_attack.get("attacks",[]))
                # Phòng thủ anh dũng nhất
                top_defense = max(war_data["opponent"]["members"], key=lambda m: sum(a.get("stars",0) for a in m.get("attacks",[])))
                top_defense_stars = sum(a.get("stars",0) for a in top_defense.get("attacks",[]))

                changes.append(
                    f"🏁 War kết thúc!\n"
                    f"Kết quả: {result} (Clan {clan_total}⭐ - Địch {opp_total}⭐)\n"
                    f"⭐ Tấn công anh dũng nhất: {top_attack['name']} ({top_attack_stars} ⭐)\n"
                    f"🛡️ Phòng thủ anh dũng nhất: {top_defense['name']} ({top_defense_stars} ⭐)"
                )

        # --- Kết quả war tổng quan (win/loss/tie cũ) ---
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

        # --- Cập nhật danh sách thành viên ---
        last_members = members

        # --- Gửi thông báo nếu có thay đổi ---
        if changes:
            msg = "\n\n".join(changes)
            print("📢 Gửi thông báo:\n", msg)
            send_message(int(CHAT_ID), msg)

    except Exception as e:
        print("⚠️ Lỗi khi check clan:", e)

    finally:
        is_checking = False

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

    # --- Thêm schedule ở đây ---
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(1)

    # Check mỗi 1 phút (bạn có thể đổi)
    schedule.every(1).minutes.do(check_clan_changes)

    # Chạy scheduler song song Flask
    threading.Thread(target=run_scheduler, daemon=True).start()
    # ----------------------------

    # Chạy Flask server
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
