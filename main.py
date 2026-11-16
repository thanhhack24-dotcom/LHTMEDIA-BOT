import os
import time
import sqlite3
import requests
from flask import Flask
from threading import Thread

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
API = f"https://api.telegram.org/bot{TOKEN}/"

db = sqlite3.connect("lhtmedia.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS uids (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid TEXT,
    note TEXT
)""")

# Add status columns safely for databases created by the older version.
columns = {row[1] for row in cur.execute("PRAGMA table_info(uids)").fetchall()}
if "status" not in columns:
    cur.execute("ALTER TABLE uids ADD COLUMN status TEXT DEFAULT 'CHƯA KIỂM TRA'")
if "checked_at" not in columns:
    cur.execute("ALTER TABLE uids ADD COLUMN checked_at TEXT DEFAULT ''")

cur.execute("""CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT,
    status TEXT DEFAULT 'Đang làm'
)""")
db.commit()


def send(chat_id, text, keyboard=None, parse_mode=None):
    data = {"chat_id": chat_id, "text": text}
    if parse_mode:
        data["parse_mode"] = parse_mode
    if keyboard:
        data["reply_markup"] = {"inline_keyboard": keyboard}
    try:
        requests.post(API + "sendMessage", json=data, timeout=20).raise_for_status()
    except requests.RequestException as error:
        print("Telegram send error:", error)


def menu(chat_id):
    keyboard = [
        [
            {"text": "👤 Quản lý UID", "callback_data": "uids"},
            {"text": "💬 Mẫu bình luận", "callback_data": "templates"}
        ],
        [
            {"text": "📋 Nhiệm vụ", "callback_data": "tasks"},
            {"text": "📊 Thống kê", "callback_data": "stats"}
        ],
        [{"text": "🔎 Trạng thái UID", "callback_data": "uid_status"}],
        [{"text": "ℹ️ Hướng dẫn", "callback_data": "help"}]
    ]
    send(chat_id, "🟣 LHTMEDIA\nBẢNG ĐIỀU KHIỂN ADMIN", keyboard)


def handle_message(message):
    user = message.get("from", {})
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    if user.get("id") != ADMIN_ID:
        send(chat_id, "⛔ Bạn không có quyền sử dụng bot.")
        return

    if text == "/start":
        menu(chat_id)

    elif text == "/help":
        send(chat_id,
             "LHTMEDIA – LỆNH ADMIN\n"
             "/adduid UID ghi_chu - Thêm UID\n"
             "/uids - Xem UID và trạng thái đã ghi nhận\n"
             "/setstatus ID LIVE|DIE|UNKNOWN - Cập nhật trạng thái thủ công\n"
             "/uidstatus - Xem tổng hợp trạng thái\n"
             "/addtemplate nội_dung - Thêm mẫu\n"
             "/templates - Xem mẫu\n"
             "/addtask nội_dung - Thêm nhiệm vụ\n"
             "/tasks - Xem nhiệm vụ\n\n"
             "Lưu ý: LIVE/DIE ở đây là trạng thái do admin xác minh và cập nhật. "
             "Bot chưa tự động xác minh tài khoản Facebook.")

    elif text.startswith("/adduid "):
        parts = text.split(maxsplit=2)
        if len(parts) < 2:
            send(chat_id, "Cú pháp: /adduid UID ghi_chu")
            return
        note = parts[2] if len(parts) > 2 else ""
        cur.execute("INSERT INTO uids(uid,note) VALUES(?,?)", (parts[1], note))
        db.commit()
        send(chat_id, f"✅ Đã lưu UID. Mã quản lý: #{cur.lastrowid}")

    elif text == "/uids":
        rows = cur.execute(
            "SELECT id,uid,note,status FROM uids ORDER BY id DESC"
        ).fetchall()
        result = "\n".join(
            f"#{r[0]} | UID: {r[1]} | {r[3]} | {r[2]}" for r in rows
        )
        send(chat_id, "👤 DANH SÁCH UID\n" + (result or "Chưa có UID."))

    elif text.startswith("/setstatus "):
        parts = text.split(maxsplit=3)
        if len(parts) < 3:
            send(chat_id, "Cú pháp: /setstatus ID LIVE|DIE|UNKNOWN")
            return

        record_id = parts[1]
        status_input = parts[2].upper()
        status_map = {
            "LIVE": "LIVE",
            "DIE": "DIE",
            "UNKNOWN": "KHÔNG XÁC ĐỊNH",
            "KHONGXACDINH": "KHÔNG XÁC ĐỊNH"
        }
        if status_input not in status_map:
            send(chat_id, "Trạng thái hợp lệ: LIVE, DIE hoặc UNKNOWN.")
            return

        row = cur.execute(
            "SELECT uid,status FROM uids WHERE id=?", (record_id,)
        ).fetchone()
        if not row:
            send(chat_id, "❌ Không tìm thấy mã UID này. Gửi /uids để xem mã.")
            return

        new_status = status_map[status_input]
        old_status = row[1] or "CHƯA KIỂM TRA"
        cur.execute(
            "UPDATE uids SET status=?, checked_at=datetime('now') WHERE id=?",
            (new_status, record_id)
        )
        db.commit()

        if new_status != old_status:
            status_icon = {
                "LIVE": "🟢",
                "DIE": "🔴",
                "KHÔNG XÁC ĐỊNH": "⚪"
            }[new_status]
            profile_link = f"https://www.facebook.com/{row[0]}"
            send(
                chat_id,
                "📘 <b>FACEBOOK PROFILE</b>\n"
                f"👤 UID: <code>{row[0]}</code>\n"
                f"🔗 <a href=\"{profile_link}\">Mở hồ sơ Facebook</a>\n"
                f"{status_icon} <b>Trạng thái:</b> {new_status}\n"
                f"🕒 <b>Thời gian cập nhật:</b> {time.strftime('%d/%m/%Y %H:%M:%S')}\n"
                "📊 <b>Nguồn:</b> Admin xác nhận thủ công\n"
                "ℹ️ Đây không phải kết quả quét tự động từ Facebook.",
                parse_mode="HTML"
            )
        else:
            send(chat_id, f"ℹ️ UID {row[0]} vẫn ở trạng thái {new_status}.")

    elif text == "/uidstatus":
        rows = cur.execute(
            "SELECT status, COUNT(*) FROM uids GROUP BY status"
        ).fetchall()
        counts = {status or "CHƯA KIỂM TRA": count for status, count in rows}
        send(chat_id,
             "🔎 TỔNG HỢP TRẠNG THÁI UID\n"
             f"🟢 LIVE: {counts.get('LIVE', 0)}\n"
             f"🔴 DIE: {counts.get('DIE', 0)}\n"
             f"⚪ Không xác định: {counts.get('KHÔNG XÁC ĐỊNH', 0)}\n"
             f"🕓 Chưa kiểm tra: {counts.get('CHƯA KIỂM TRA', 0)}")

    elif text.startswith("/addtemplate "):
        content = text.split(maxsplit=1)[1]
        cur.execute("INSERT INTO templates(content) VALUES(?)", (content,))
        db.commit()
        send(chat_id, "✅ Đã lưu mẫu.")

    elif text == "/templates":
        rows = cur.execute("SELECT id,content FROM templates").fetchall()
        result = "\n".join(f"#{r[0]} | {r[1]}" for r in rows)
        send(chat_id, "💬 MẪU BÌNH LUẬN\n" + (result or "Chưa có mẫu."))

    elif text.startswith("/addtask "):
        content = text.split(maxsplit=1)[1]
        cur.execute("INSERT INTO tasks(content) VALUES(?)", (content,))
        db.commit()
        send(chat_id, "✅ Đã thêm nhiệm vụ.")

    elif text == "/tasks":
        rows = cur.execute(
            "SELECT id,content,status FROM tasks"
        ).fetchall()
        result = "\n".join(
            f"#{r[0]} | {r[1]} | {r[2]}" for r in rows
        )
        send(chat_id, "📋 NHIỆM VỤ\n" + (result or "Chưa có nhiệm vụ."))


def handle_callback(query):
    user_id = query["from"]["id"]
    chat_id = query["message"]["chat"]["id"]
    data = query["data"]

    requests.post(API + "answerCallbackQuery",
                  json={"callback_query_id": query["id"]}, timeout=20)

    if user_id != ADMIN_ID:
        return

    if data == "uids":
        rows = cur.execute("SELECT COUNT(*) FROM uids").fetchone()[0]
        send(chat_id, f"👤 Tổng UID đã lưu: {rows}. Gửi /uids để xem danh sách.")
    elif data == "templates":
        rows = cur.execute("SELECT COUNT(*) FROM templates").fetchone()[0]
        send(chat_id, f"💬 Tổng mẫu đã lưu: {rows}. Gửi /templates để xem.")
    elif data == "tasks":
        rows = cur.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        send(chat_id, f"📋 Tổng nhiệm vụ: {rows}. Gửi /tasks để xem.")
    elif data == "uid_status":
        send(chat_id, "Gửi /uidstatus để xem tổng hợp hoặc /uids để xem từng UID.")
    elif data == "stats":
        a = cur.execute("SELECT COUNT(*) FROM uids").fetchone()[0]
        b = cur.execute("SELECT COUNT(*) FROM templates").fetchone()[0]
        c = cur.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        send(chat_id, f"📊 LHTMEDIA\nUID: {a}\nMẫu: {b}\nNhiệm vụ: {c}")
    elif data == "help":
        send(chat_id, "Gửi /help để xem danh sách lệnh.")


def main():
    offset = None
    print("LHTMEDIA BOT started")
    while True:
        try:
            params = {"timeout": 30}
            if offset is not None:
                params["offset"] = offset
            response = requests.get(
                API + "getUpdates", params=params, timeout=40
            ).json()

            for update in response.get("result", []):
                offset = update["update_id"] + 1
                if "message" in update:
                    handle_message(update["message"])
                elif "callback_query" in update:
                    handle_callback(update["callback_query"])
        except Exception as error:
            print("Bot error:", error)
            time.sleep(3)


app = Flask(__name__)

@app.route("/")
def home():
    return "LHTMEDIA BOT is running", 200


if __name__ == "__main__":
    Thread(target=main, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
