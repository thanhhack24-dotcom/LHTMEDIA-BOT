
import os
import sqlite3
import requests

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


def send(chat_id, text, keyboard=None):
    data = {"chat_id": chat_id, "text": text}
    if keyboard:
        data["reply_markup"] = {
            "inline_keyboard": keyboard
        }
    requests.post(API + "sendMessage", json=data, timeout=20)


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
             "/start - Mở menu\n"
             "/adduid UID ghi_chu - Thêm UID\n"
             "/uids - Xem UID\n"
             "/addtemplate nội_dung - Thêm mẫu\n"
             "/templates - Xem mẫu\n"
             "/addtask nội_dung - Thêm nhiệm vụ\n"
             "/tasks - Xem nhiệm vụ")

    elif text.startswith("/adduid "):
        parts = text.split(maxsplit=2)
        if len(parts) < 2:
            send(chat_id, "Cú pháp: /adduid UID ghi_chu")
            return
        note = parts[2] if len(parts) > 2 else ""
        cur.execute("INSERT INTO uids(uid,note) VALUES(?,?)",
                    (parts[1], note))
        db.commit()
        send(chat_id, "✅ Đã lưu UID.")

    elif text == "/uids":
        rows = cur.execute("SELECT id,uid,note FROM uids").fetchall()
        result = "\n".join(
            f"#{r[0]} | {r[1]} | {r[2]}" for r in rows
        )
        send(chat_id, "👤 DANH SÁCH UID\n" + (result or "Chưa có UID."))

    elif text.startswith("/addtemplate "):
        content = text.split(maxsplit=1)[1]
        cur.execute("INSERT INTO templates(content) VALUES(?)",
                    (content,))
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
                  json={"callback_query_id": query["id"]},
                  timeout=20)

    if user_id != ADMIN_ID:
        return

    if data == "uids":
        rows = cur.execute("SELECT COUNT(*) FROM uids").fetchone()[0]
        send(chat_id, f"👤 Tổng UID đã lưu: {rows}")

    elif data == "templates":
        rows = cur.execute("SELECT COUNT(*) FROM templates").fetchone()[0]
        send(chat_id, f"💬 Tổng mẫu đã lưu: {rows}")

    elif data == "tasks":
        rows = cur.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        send(chat_id, f"📋 Tổng nhiệm vụ: {rows}")

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
                API + "getUpdates",
                params=params,
                timeout=40
            ).json()

            for update in response.get("result", []):
                offset = update["update_id"] + 1

                if "message" in update:
                    handle_message(update["message"])

                elif "callback_query" in update:
                    handle_callback(update["callback_query"])

        except Exception as error:
            print("Bot error:", error)


if __name__ == "__main__":
    main()
