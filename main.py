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
# HÀM TIỆN ÍCH
# =============================
def get_json(url):
    r = requests.get(url, headers={"Authorization": f"Bearer {COC_API_KEY}"}, timeout=5)
    return r.json() if r.status_code == 200 else None

def send_message(text, keyboard=None):
    data = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    if keyboard:
        data["reply_markup"] = {"inline_keyboard": keyboard}
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=data, timeout=5)


# =============================
# THÔNG TIN CLAN
# =============================
def get_clan_info():
    tag = CLAN_TAG.replace("#", "%23")
    return get_json(f"https://api.clashofclans.com/v1/clans/{tag}")


# =============================
# TOP DONATE
# =============================
def get_top_donators(limit=5):
    clan = get_clan_info()
    if not clan: return None
    members = clan.get("memberList", [])
    top = sorted(members, key=lambda m: m.get("donations", 0), reverse=True)[:limit]
    msg = "💎 <b>TOP DONATE</b>\n"
    for i, m in enumerate(top, start=1):
        msg += f"{i}. {m['name']} — {m['donations']} 💰 donate\n"
    return msg


# =============================
# TOP WAR ATTACKS
# =============================
def get_top_war(limit=5):
    tag = CLAN_TAG.replace("#", "%23")
    war = get_json(f"https://api.clashofclans.com/v1/clans/{tag}/currentwar")
    if not war or war.get("state") not in ["inWar", "warEnded"]:
        return "❌ Không có war đang diễn ra."
    
    attacks = []
    for m in war.get("clan", {}).get("members", []):
        if "attacks" in m:
            total_stars = sum(a["stars"] for a in m["attacks"])
            total_dmg = sum(a["destructionPercentage"] for a in m["attacks"]) / len(m["attacks"])
            attacks.append((m["name"], total_stars, total_dmg))
    
    top = sorted(attacks, key=lambda x: (x[1], x[2]), reverse=True)[:limit]
    msg = "⚔️ <b>TOP WAR ATTACKERS</b>\n"
    for i, (name, stars, dmg) in enumerate(top, start=1):
        msg += f"{i}. {name} — ⭐ {stars}, 💥 {dmg:.1f}%\n"
    return msg


# =============================
# THÀNH VIÊN CHƯA ĐÁNH WAR
# =============================
def get_unattacked_members():
    tag = CLAN_TAG.replace("#", "%23")
    war = get_json(f"https://api.clashofclans.com/v1/clans/{tag}/currentwar")
    if not war or war.get("state") != "inWar":
        return "❌ Không có war đang diễn ra."

    no_attack = [m["name"] for m in war["clan"]["members"] if "attacks" not in m]
    if not no_attack:
        return "✅ Tất cả thành viên đã đánh war."
    
    msg = "🚫 <b>CHƯA ĐÁNH WAR</b>\n" + "\n".join(f"- {n}" for n in no_attack)
    return msg


# =============================
# THÀNH VIÊN ONLINE GẦN ĐÂY
# =============================
def get_recent_active(limit=10):
    clan = get_clan_info()
    if not clan: return None
    members = clan.get("memberList", [])
    
    active = []
    for m in members[:limit]:
        tag = m["tag"].replace("#", "%23")
        player = get_json(f"https://api.clashofclans.com/v1/players/{tag}")
        if player and "lastSeen" in player:
            last_seen = player["lastSeen"].replace("T", " ").replace(".000Z", "")
            active.append((m["name"], last_seen))
    
    msg = "🕒 <b>THÀNH VIÊN ONLINE GẦN ĐÂY</b>\n"
    for name, time in active:
        msg += f"- {name}: {time}\n"
    return msg


# =============================
# WEBHOOK
# =============================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if not data:
        return "NO DATA", 400

    message = data.get("message", {})
    callback = data.get("callback_query", {})
    text = message.get("text", "").strip().lower()

    # Callback button
    if callback:
        query_data = callback["data"]
        if query_data == "top_donate":
            send_message(get_top_donators() or "❌ Không thể lấy danh sách donate.")
        elif query_data == "clan_info":
            c = get_clan_info()
            msg = f"🏰 Clan: {c['name']}\n⭐ Level: {c['clanLevel']}\n👥 Thành viên: {c['members']}" if c else "❌ Không thể lấy thông tin clan."
            send_message(msg)
        elif query_data == "top_war":
            send_message(get_top_war())
        elif query_data == "war_turn":
            send_message(get_unattacked_members())
        elif query_data == "active":
            send_message(get_recent_active())
        return "OK", 200

    # Text command
    if text == "/menu":
        keyboard = [
            [{"text": "🔝 Top Donate", "callback_data": "top_donate"}],
            [{"text": "⚔️ Top War", "callback_data": "top_war"}],
            [{"text": "🚫 Chưa Đánh War", "callback_data": "war_turn"}],
            [{"text": "🕒 Thành viên hoạt động", "callback_data": "active"}],
            [{"text": "🏰 Thông tin Clan", "callback_data": "clan_info"}]
        ]
        send_message("📋 <b>Menu chọn chức năng</b>:", keyboard)
    else:
        send_message("⚙️ Gõ /menu để xem các lựa chọn.")
    return "OK", 200


# =============================
# WEBHOOK SETUP
# =============================
def update_webhook():
    base = f"https://api.telegram.org/bot{BOT_TOKEN}"
    requests.get(f"{base}/deleteWebhook", timeout=5)
    requests.get(f"{base}/setWebhook", params={"url": f"{WEBHOOK_URL}/webhook"}, timeout=5)

if __name__ == "__main__":
    update_webhook()
    app.run(host="0.0.0.0", port=PORT)
