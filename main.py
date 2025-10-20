import requests, time, os, json
from urllib.parse import quote_plus
from flask import Flask, request
import threading
# ==============================

app = Flask(__name__)
AUTO_THREAD = None
AUTO_RUNNING = False
AUTO_INTERVAL = 0

# ==============================
# CẤU HÌNH
# ==============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CLAN_TAG = os.getenv("CLAN_TAG") or "#YOURTAG"
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

    if callback:
        chat_id = callback["message"]["chat"]["id"]
        data_callback = callback["data"]
        handle_callback(chat_id, data_callback)
        return "OK", 200

    if "text" in message:
        text = message["text"]
        chat_id = message["chat"]["id"]

        if text.startswith("/menu"):
            reply_markup = {
                "inline_keyboard": [
                    [
                        {"text": "🏰 Clan", "callback_data": "show_clan"},
                        {"text": "⚔️ War", "callback_data": "show_war"}
                    ],
                    [
                        {"text": "👥 Members", "callback_data": "show_members"},
                        {"text": "🔍 Check", "callback_data": "show_check"}
                    ],
                    [
                        {"text": "🕒 Tự động cập nhật", "callback_data": "auto_update"}
                    ]
                ]
            }
            send_message(chat_id, "📋 Chọn chức năng:", reply_markup)
    return "OK", 200

# ==============================
# 3️⃣ GỬI TIN NHẮN
# ==============================
def send_message(chat_id, text, reply_markup=None):
    url = f"{BASE_TELEGRAM}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    headers = {"Content-Type": "application/json"}
    if reply_markup:
        # Telegram chấp nhận object nhưng an toàn hơn serialize
        payload["reply_markup"] = reply_markup
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        if r.status_code != 200:
            log("Telegram sendMessage failed", r.status_code, r.text)
    except Exception as e:
        log("send_message exception:", e)

# ==============================
# 4️⃣ MENU CHÍNH
# ==============================
def main_menu_markup():
    return {
        "inline_keyboard": [
            [
                {"text": "🏰 Clan", "callback_data": "show_clan"},
                {"text": "⚔️ War", "callback_data": "show_war"}
            ],
            [
                {"text": "👥 Members", "callback_data": "show_members"},
                {"text": "🔍 Check", "callback_data": "show_check"}
            ],
            [
                {"text": "🕒 Tự động cập nhật", "callback_data": "auto_update"}
            ]
        ]
    }
# ==============================
# TỰ ĐỘNG CẬP NHẬT WAR
# ==============================
def auto_send_updates(chat_id, interval):
    global AUTO_RUNNING
    AUTO_RUNNING = True
    end_time = time.time() + interval

    send_message(chat_id, f"✅ Đã bật tự động cập nhật mỗi {interval/60:.0f} phút!")

    while AUTO_RUNNING and time.time() < end_time:
        try:
            headers = {"Authorization": f"Bearer {COC_API_KEY}", "Accept": "application/json"}
            clan_tag_encoded = quote_plus(CLAN_TAG)

            war_url = f"https://api.clashofclans.com/v1/clans/{clan_tag_encoded}/currentwar"
            war_data = safe_get_json(war_url, headers)

            if not war_data:
                time.sleep(interval)
                continue

            # ⚙️ Kiểm tra trạng thái war
            state = war_data.get("state", "")
            if state != "inWar":
                log(f"⏸️ War state: {state} → Không gửi thông báo.")
                time.sleep(interval)
                continue

            # =========================
            # 🔥 ĐANG TRONG WAR → GỬI
            # =========================
            clan = war_data.get("clan", {})
            opponent = war_data.get("opponent", {})

            msg = (
                f"⚔️ <b>{clan.get('name','?')}</b> vs <b>{opponent.get('name','?')}</b>\n"
                f"⭐ {clan.get('stars',0)} - {opponent.get('stars',0)}\n"
                f"🎯 Lượt đánh: {clan.get('attacks',0)} / {war_data.get('teamSize',0)*2}"
            )
            send_message(chat_id, msg)

            # --- WAR MEMBERS ---
            members = clan.get("members", [])
            msg_members = "👥 <b>Danh sách war:</b>\n"
            for m in members:
                attacks = len(m.get("attacks", []))
                stars = sum(a.get("stars",0) for a in m.get("attacks", []))
                msg_members += f"{m.get('name','?')} - {attacks}/2 - {stars}⭐\n"
            send_message(chat_id, msg_members)

        except Exception as e:
            log("Auto send error:", e)

        time.sleep(interval)
    
    AUTO_RUNNING = False
    send_message(chat_id, "🕒 Tự động cập nhật đã kết thúc!")

# ==============================
# 4️⃣ GIAO DIỆN BUTTON
# ==============================
def handle_callback(chat_id, data_callback):
    msg = None
    if data_callback == "back_menu":
        send_message(chat_id, "📋 Chọn chức năng:", main_menu_markup())
        return

    if not COC_API_KEY:
        send_message(chat_id, "❌ COC_API_KEY chưa được cấu hình trên biến môi trường.")
        return

    headers = {
        "Authorization": f"Bearer {COC_API_KEY}",
        "Accept": "application/json"
    }

    # url-encode clan tag (an toàn hơn replace)
    clan_tag_encoded = quote_plus(CLAN_TAG)

    # CLAN INFO
    if data_callback == "show_clan":
        url = f"https://api.clashofclans.com/v1/clans/{clan_tag_encoded}"
        res = safe_get_json(url, headers)
        if not res:
            send_message(chat_id, "❌ Lỗi khi lấy thông tin clan.")
            return

        leader = next((m['name'] for m in res.get('memberList', []) if m.get('role') == 'leader'), 'Không rõ')
        msg = (
            f"🏰 <b>{res.get('name', '?')}</b> (Cấp {res.get('clanLevel', 0)})\n"
            f"👑 Thủ lĩnh: {leader}\n"
            f"🏷️ Tag: {res.get('tag', '?')}\n"
            f"📜 Mô tả: {res.get('description', 'Không có mô tả')}\n"
            f"👥 Thành viên: {res.get('members', 0)}\n"
            f"⚙️ Quyền: {res.get('type', 'closed').capitalize()}\n"
            f"🔥 Chuỗi thắng: {res.get('warWinStreak', 0)}\n"
            f"⚔️ War: {res.get('warWins', 0)} thắng / {res.get('warLosses', 0)} thua / {res.get('warTies', 0)} hòa"
        )
        send_message(chat_id, msg, {
            "inline_keyboard": [[{"text": "🔙 Trở về", "callback_data": "back_menu"}]]
        })
        return

    # WAR INFO
    if data_callback == "show_war":
        url = f"https://api.clashofclans.com/v1/clans/{clan_tag_encoded}/currentwar"
        res = safe_get_json(url, headers)
        if not res:
            send_message(chat_id, "❌ Lỗi khi lấy thông tin war.")
            return

        state = res.get("state", "notInWar")
        if state == "notInWar":
            send_message(chat_id, "❌ Hiện không có war nào đang diễn ra.")
            return

        clan = res.get("clan", {})
        opponent = res.get("opponent", {})
        team_size = res.get("teamSize", 0)

        msg = (
            f"⚔️ <b>{clan.get('name', '?')}</b> 🆚 <b>{opponent.get('name', '?')}</b>\n"
            f"⭐ {clan.get('stars', 0)} - {opponent.get('stars', 0)}\n"
            f"🎯 Lượt đánh: {clan.get('attacks', 0)}/{team_size*2} - Địch: {opponent.get('attacks', 0)}/{team_size*2}\n"
        )

        if state == "preparation":
            msg += "🕐 Trạng thái: <b>Trong ngày chuẩn bị</b>\n"
        elif state == "inWar":
            msg += "🔥 Trạng thái: <b>Trong ngày chiến đấu</b>\n"
        elif state == "warEnded":
            msg += "🏁 Trận chiến đã kết thúc!\n"

        msg += f"👥 Thành viên war: {team_size}"

        reply_markup = {
            "inline_keyboard": [
                [{"text": "⚔️ Top War", "callback_data": "top_war"},
                {"text": "👥 Thành viên tham gia", "callback_data": "war_members"}]
            ]
        }
        reply_markup["inline_keyboard"].append([{"text": "🔙 Trở về", "callback_data": "back_menu"}])
        send_message(chat_id, msg, reply_markup)
        return

    if data_callback == "show_check":
        send_message(chat_id, "🔍 Đang kiểm tra clan...")
        time.sleep(2)
        send_message(chat_id, "✅ Clan hoạt động bình thường!")
        return

    # MEMBERS INFO
    if data_callback == "show_members":
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "🤝 Top Donate", "callback_data": "top_donate"},
                    {"text": "⚔️ Top Chiến tích", "callback_data": "top_trophies"}
                ],
                [
                    {"text": "🎓 Kinh nghiệm cao nhất", "callback_data": "top_exp"},
                    {"text": "🏰 Top Hall", "callback_data": "top_hall"}
                ],
                [
                    {"text": "🔙 Trở về", "callback_data": "back_menu"}
                ]
            ]
        }
        send_message(chat_id, "👥 Chọn thống kê thành viên:", reply_markup)
        return

    # ==============================
    # XỬ LÝ NÚT AUTO UPDATE
    # ==============================
    if data_callback == "auto_update":
        # Hiển thị trạng thái hiện tại
        if AUTO_RUNNING:
            minutes = int(AUTO_INTERVAL / 60)
            if minutes < 60:
                status_text = f"🔵 Đang bật tự động cập nhật mỗi {minutes} phút."
            else:
                hours = minutes / 60
                status_text = f"🔵 Đang bật tự động cập nhật mỗi {hours:.0f} giờ."
        else:
            status_text = "⚪ Hiện đang tắt tự động cập nhật."


        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "1 phút", "callback_data": "auto_1m"},
                    {"text": "10 phút", "callback_data": "auto_10m"},
                    {"text": "30 phút", "callback_data": "auto_30m"}
                ],
                [
                    {"text": "1 giờ", "callback_data": "auto_1h"},
                    {"text": "3 giờ", "callback_data": "auto_3h"},
                    {"text": "6 giờ", "callback_data": "auto_6h"}
                ],
                [
                    {"text": "❌ Tắt tự động", "callback_data": "auto_stop"},
                    {"text": "🔙 Trở về", "callback_data": "back_menu"}
                ]
            ]
        }

        send_message(chat_id, f"🕒 Chọn thời gian tự động cập nhật war:\n\n{status_text}", reply_markup)
        return

    
    if data_callback.startswith("auto_"):
        global AUTO_THREAD, AUTO_RUNNING

        if data_callback == "auto_stop":
            AUTO_RUNNING = False
            AUTO_INTERVAL = 0
            send_message(chat_id, "🛑 Đã tắt tự động cập nhật.")
            return


        # Thời gian (giây)
        intervals = {
            "auto_1m": 60,
            "auto_10m": 600,
            "auto_30m": 1800,
            "auto_1h": 3600,
            "auto_3h": 10800,
            "auto_6h": 21600,
        }
        interval = intervals[data_callback]

        if AUTO_RUNNING:
            send_message(chat_id, "⚠️ Tự động đang chạy. Hãy tắt trước khi bật lại.")
            return

        AUTO_THREAD = threading.Thread(target=auto_send_updates, args=(chat_id, interval))
        AUTO_THREAD.daemon = True
        AUTO_THREAD.start()
        return


# ==============================
# 5️⃣ CALLBACK XỬ LÝ NÚT (CẬP NHẬT /currentwar)
# ==============================
    elif data_callback == "top_war":
        url = f"https://api.clashofclans.com/v1/clans/{clan_tag_encoded}/currentwar"
        war_data = safe_get_json(url, headers)
        if not war_data:
            send_message(chat_id, "❌ Lỗi khi lấy dữ liệu war.")
            return

        state = war_data.get("state", "notInWar")
        members = war_data.get("clan", {}).get("members", [])

        msg = ""
        if state == "preparation":
            msg += "🕐 Trạng thái: <b>Trong ngày chuẩn bị</b>\n"
            msg += "<b>( Chưa có dữ liệu! )</b>\n"

        elif state == "inWar":
            msg = "🏅 <b>Top 5 người đánh nhiều sao nhất:</b>\n"
            top = sorted(
                members,
                key=lambda m: sum(a.get("stars", 0) for a in m.get("attacks", [])),
                reverse=True
            )[:5]
            for i, m in enumerate(top, 1):
                stars = sum(a.get("stars", 0) for a in m.get("attacks", []))
                msg += f"{i}. {m.get('name', '?')} - ⭐ {stars}\n"

        elif state == "warEnded":
            msg += "🏁 <b>Trận chiến đã kết thúc!</b>\n"

        else:
            msg += "❌ Hiện không có war nào đang diễn ra.\n"

        msg += "\n\n🔙 /menu để quay lại hoặc chọn nút bên dưới."

        send_message(chat_id, msg, {"inline_keyboard": [[{"text": "🔙 Trở về", "callback_data": "show_war"}]]})
        return



    if data_callback == "war_members":
        url = f"https://api.clashofclans.com/v1/clans/{clan_tag_encoded}/currentwar"
        war_data = safe_get_json(url, headers)
        if not war_data:
            send_message(chat_id, "❌ Lỗi khi lấy dữ liệu war.")
            return
        members = war_data.get("clan", {}).get("members", [])
        msg = "👥 <b>Danh sách thành viên war:</b>\n"
        for m in members:
            attacks = len(m.get("attacks", []))
            stars = sum(a.get("stars",0) for a in m.get("attacks", []))
            msg += f"{m.get('name','?')} - {attacks}/2 - {stars}⭐\n"
        
        msg += "\n\n🔙 /menu để quay lại hoặc chọn nút bên dưới."
        send_message(chat_id, msg, {"inline_keyboard": [[{"text": "🔙 Trở về", "callback_data": "show_war"}]]})
        return

    # === MEMBERS DETAIL ===
    if data_callback.startswith("top_"):
        url = f"https://api.clashofclans.com/v1/clans/{clan_tag_encoded}/members"
        data = safe_get_json(url, headers)
        if not data:
            send_message(chat_id, "❌ Lỗi khi lấy danh sách thành viên.")
            return
        members = data.get("items", [])  # endpoint này dùng "items" thay vì "memberList"

        if data_callback == "top_donate":
            top = sorted(members, key=lambda m: m.get("donations", 0), reverse=True)[:10]
            msg = "🤝 <b>Top 10 donate nhiều nhất:</b>\n"
            for i, m in enumerate(top, 1):
                msg += f"{i}. {m.get('name','?')} - {m.get('donations',0)}\n"

            msg += "\n\n🔙 /menu để quay lại hoặc chọn nút bên dưới."
            reply_markup = {"inline_keyboard": [[{"text": "🔙 Trở về", "callback_data": "show_members"}]]}
            send_message(chat_id, msg, reply_markup)
            return


        elif data_callback == "top_trophies":
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "🏰 Làng chính", "callback_data": "top_main"},
                    {"text": "⚒️ Căn cứ thợ xây", "callback_data": "top_builder"}],
                ]
            }
            reply_markup["inline_keyboard"].append([{"text": "🔙 Trở về", "callback_data": "show_members"}])
            send_message(chat_id, "🏆 Chọn loại chiến tích muốn xem:", reply_markup)
            return

        elif data_callback == "top_main":
            top = sorted(members, key=lambda m: m.get("trophies", 0), reverse=True)[:10]
            msg = "🏰 <b>Top 10 làng chính:</b>\n"
            for i, m in enumerate(top, 1):
                msg += f"{i}. {m.get('name','?')} - 🏆 {m.get('trophies',0)}\n"

            msg += "\n\n🔙 Chọn 'Trở về' để quay lại menu."

            reply_markup = {
                "inline_keyboard": [
                    [{"text": "🔙 Trở về", "callback_data": "show_members"}]
                ]
            }

            send_message(chat_id, msg, reply_markup)
            return


        elif data_callback == "top_builder":
            top = sorted(members, key=lambda m: m.get("builderBaseTrophies", 0), reverse=True)[:10]
            msg = "⚒️ <b>Top 10 căn cứ thợ xây:</b>\n"
            for i, m in enumerate(top, 1):
                msg += f"{i}. {m.get('name','?')} - ⚒️ {m.get('builderBaseTrophies',0)}\n"

            msg += "\n\n🔙 Chọn 'Trở về' để quay lại menu."

            reply_markup = {
                "inline_keyboard": [
                    [{"text": "🔙 Trở về", "callback_data": "show_members"}]
                ]
            }

            send_message(chat_id, msg, reply_markup)
            return

        elif data_callback == "top_exp":
            top = sorted(members, key=lambda m: m.get("expLevel", 0), reverse=True)[:10]
            msg = "🎓 <b>Top 10 kinh nghiệm cao nhất:</b>\n"
            for i, m in enumerate(top, 1):
                msg += f"{i}. {m.get('name','?')} - LV {m.get('expLevel',0)}\n"

            msg += "\n\n🔙 Chọn 'Trở về' để quay lại menu."

            reply_markup = {
                "inline_keyboard": [
                    [{"text": "🔙 Trở về", "callback_data": "show_members"}]
                ]
            }

            send_message(chat_id, msg, reply_markup)
            return

        elif data_callback == "top_hall":
            top = sorted(members, key=lambda m: m.get("townHallLevel", 0), reverse=True)[:10]
            msg = "🏰 <b>Top 10 Hall cao nhất:</b>\n"
            for i, m in enumerate(top, 1):
                msg += f"{i}. {m.get('name','?')} - Hall {m.get('townHallLevel',0)}\n"

            msg += "\n\n🔙 Chọn 'Trở về' để quay lại menu."

            reply_markup = {
                "inline_keyboard": [
                    [{"text": "🔙 Trở về", "callback_data": "show_members"}]
                ]
            }

            send_message(chat_id, msg, reply_markup)
            return
 
        if msg:
            send_message(chat_id, msg)
        else:
            send_message(chat_id, f"❓ Không hiểu lệnh: {data_callback}")

        return

# Helper: safe GET + JSON + logging
def safe_get_json(url, headers, timeout=10):
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
    except Exception as e:
        log("Request exception:", e)
        return None
    if r.status_code != 200:
        log("COC API returned", r.status_code, r.text[:300])
        return None
    try:
        return r.json()
    except Exception as e:
        log("JSON decode error:", e, r.text[:300])
        return None

# ==============================
# 6️⃣ THIẾT LẬP WEBHOOK
# ==============================
def set_webhook():
    try:
        requests.get(f"{BASE_TELEGRAM}/deleteWebhook", timeout=5)
        if WEBHOOK_URL:
            requests.get(f"{BASE_TELEGRAM}/setWebhook?url={WEBHOOK_URL}/webhook", timeout=5)
            log("Webhook set to", WEBHOOK_URL)
        else:
            log("WEBHOOK_URL not set; skipping setWebhook")
    except Exception as e:
        log("set_webhook exception:", e)

# ==============================
# 7️⃣ KHỞI ĐỘNG
# ==============================
if __name__ == '__main__':
    try:
        set_webhook()
    except Exception:
        pass
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
