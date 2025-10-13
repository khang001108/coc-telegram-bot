import os, requests
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CLAN_TAG = os.getenv("CLAN_TAG")
COC_API_KEY = os.getenv("COC_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 10000))

app = Flask(__name__)

# =============================
# HÀM LẤY THÔNG TIN CLAN
# =============================
def get_clan_info():
    tag = CLAN_TAG.replace("#", "%23")
    r = requests.get(f"https://api.clashofclans.com/v1/clans/{tag}",
                     headers={"Authorization": f"Bearer {COC_API_KEY}"})
    return r.json() if r.status_code == 200 else None


# =============================
# HÀM GỬI TIN NHẮN TELEGRAM
# =============================
def send_message(text, keyboard=None):
    data = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    if keyboard:
        data["reply_markup"] = {"inline_keyboard": keyboard}
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=data, timeout=5)


# =============================
# HÀM LẤY TOP DONATE
# =============================
def get_top_donators(limit=5):
    clan = get_clan_info()
    if not clan:
        return None
    members = clan.get("memberList", [])
    top = sorted(members, key=lambda m: m.get("donations", 0), reverse=True)[:limit]
    msg = "💎 <b>TOP DONATE</b>\n"
    for i, m in enumerate(top, start=1):
        msg += f"{i}. {m['name']} — {m['donations']} 👥 donate\n"
    return msg


# =============================
# XỬ LÝ WEBHOOK
# =============================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if not data:
        return "NO DATA", 400

    message = data.get("message", {})
    callback = data.get("callback_query", {})
    text = message.get("text", "").strip().lower()

    # 🧭 Nếu là callback button
    if callback:
        query_data = callback["data"]
        if query_data == "top_donate":
            msg = get_top_donators() or "❌ Không thể lấy danh sách donate."
            send_message(msg)
        elif query_data == "clan_info":
            c = get_clan_info()
            msg = f"🏰 Clan: {c['name']}\n⭐ Level: {c['clanLevel']}\n👥 Thành viên: {c['members']}" if c else "❌ Không thể lấy thông tin clan."
            send_message(msg)
        return "OK", 200

    # 🧭 Nếu là text command
    if text == "/check":
        c = get_clan_info()
        msg = f"🏰 Clan: {c['name']}\n⭐ Level: {c['clanLevel']}\n👥 Thành viên: {c['members']}" if c else "❌ Không thể lấy thông tin clan."
        send_message(msg)
    elif text == "/menu":
        keyboard = [
            [{"text": "🔝 Top Donate", "callback_data": "top_donate"}],
            [{"text": "🏰 Thông tin Clan", "callback_data": "clan_info"}]
        ]
        send_message("📋 <b>Menu chọn chức năng</b>:", keyboard)
    else:
        send_message("⚙️ Gõ /menu để xem các lựa chọn.")

    return "OK", 200


# =============================
# CẬP NHẬT WEBHOOK
# =============================
def update_webhook():
    base = f"https://api.telegram.org/bot{BOT_TOKEN}"
    requests.get(f"{base}/deleteWebhook", timeout=5)
    requests.get(f"{base}/setWebhook", params={"url": f"{WEBHOOK_URL}/webhook"}, timeout=5)


# =============================
# CHẠY APP
# =============================
if __name__ == "__main__":
    update_webhook()
    app.run(host="0.0.0.0", port=PORT)
