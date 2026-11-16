
import os
import time
import sqlite3
import requests
from flask import Flask
from threading import Thread, Lock

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
API = f"https://api.telegram.org/bot{TOKEN}/"

DB = sqlite3.connect("lhtmedia.db", check_same_thread=False)
LOCK = Lock()


def init_db():
    with LOCK:
        DB.execute("""
        CREATE TABLE IF NOT EXISTS uids(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT UNIQUE,
            note TEXT DEFAULT '',
            status TEXT DEFAULT 'CHƯA KIỂM TRA',
            checked_at TEXT DEFAULT ''
        )
        """)
        DB.commit()


def tg(method, payload):
    try:
        r = requests.post(API + method, json=payload, timeout=25)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        print("Telegram API error:", e)
        return None


def send(chat_id, text, markup=None):
    data = {"chat_id": chat_id, "text": text}
    if markup:
        data["reply_markup"] = markup
    tg("sendMessage", data)


# MENU NẰM NGAY DƯỚI TIN NHẮN
MENU = {
    "inline_keyboard": [
        [
            {"text": "➕ Thêm UID FB", "callback_data": "add_uid"},
            {"text": "📋 Danh sách UID", "callback_data": "list_uids"}
        ],
        [
            {"text": "🔄 Trạng thái UID", "callback_data": "uid_status"},
            {"text": "📊 Thống kê", "callback_data": "stats"}
        ],
        [
            {"text": "👤 Tài khoản", "callback_data": "account"},
            {"text": "💬 Chat Support", "callback_data": "support"}
        ],
        [
            {"text": "📖 Hướng dẫn", "callback_data": "help"}
        ]
    ]
}


def show_menu(chat_id):
    # Xóa bàn phím cũ của Telegram
    tg("sendMessage", {
        "chat_id": chat_id,
        "text": "🔄 LHTMEDIA đang cập nhật menu...",
        "reply_markup": {"remove_keyboard": True}
    })

    text = (
        "🟣 LHTMEDIA MANAGER ⭐️\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "『QUẢN LÝ UID FACEBOOK 📌』\n"
        "✦ Thêm UID và lưu ghi chú\n"
        "✦ Xem danh sách UID\n"
        "✦ Cập nhật trạng thái UID\n"
        "✦ Xem thống kê UID\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "『QUẢN LÝ HỆ THỐNG 🤖』\n"
        "✦ Quản lý tài khoản Admin\n"
        "✦ Hỗ trợ và hướng dẫn\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Chọn chức năng bên dưới.\n\n"
        "⚠️ LIVE/DIE hiện chưa được tự động xác minh."
    )

    send(chat_id, text, MENU)


def answer_callback(callback_id, text=""):
    tg("answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": text
    })


def list_uids(chat_id):
    with LOCK:
        rows = DB.execute(
            "SELECT id,uid,note,status FROM uids "
            "ORDER BY id DESC LIMIT 30"
        ).fetchall()

    if not rows:
        send(chat_id, "📋 DANH SÁCH UID\nChưa có UID.")
        return

    lines = ["📋 DANH SÁCH UID"]

    for rid, uid, note, status in rows:
        lines.append(
            f"#{rid} | UID: {uid}\n"
            f"Trạng thái: {status}\n"
            f"Ghi chú: {note or '—'}\n"
            f"Cập nhật: /setstatus {rid} LIVE|DIE|UNKNOWN"
        )

    send(chat_id, "\n\n".join(lines))


def show_stats(chat_id):
    with LOCK:
        rows = DB.execute(
            "SELECT status,COUNT(*) FROM uids GROUP BY status"
        ).fetchall()

        total = DB.execute(
            "SELECT COUNT(*) FROM uids"
        ).fetchone()[0]

    states = dict(rows)

    send(
        chat_id,
        "📊 THỐNG KÊ LHTMEDIA\n"
        f"👤 Tổng UID: {total}\n"
        f"🟢 LIVE đã ghi nhận: {states.get('LIVE', 0)}\n"
        f"🔴 DIE đã ghi nhận: {states.get('DIE', 0)}\n"
        f"⚪ Không xác định: {states.get('KHÔNG XÁC ĐỊNH', 0)}\n"
        f"🕓 Chưa kiểm tra: {states.get('CHƯA KIỂM TRA', 0)}"
    )


def handle_callback(callback):
    user_id = callback.get("from", {}).get("id")
    callback_id = callback["id"]
    chat_id = callback["message"]["chat"]["id"]
    data = callback.get("data", "")

    if user_id != ADMIN_ID:
        answer_callback(callback_id, "Bạn không có quyền.")
        return

    answer_callback(callback_id)

    if data == "add_uid":
        send(
            chat_id,
            "➕ THÊM UID FACEBOOK\n"
            "Gửi lệnh:\n"
            "/adduid UID ghi_chu\n"
            "Ví dụ: /adduid 123456789 can_theo_doi"
        )

    elif data == "list_uids":
        list_uids(chat_id)

    elif data in ("uid_status", "stats"):
        show_stats(chat_id)

    elif data == "account":
        send(
            chat_id,
            f"👤 LHTMEDIA ADMIN\nTelegram ID: {ADMIN_ID}"
        )

    elif data == "support":
        send(
            chat_id,
            "💬 HỖ TRỢ LHTMEDIA\n"
            "Gửi nội dung lỗi hoặc ảnh chụp màn hình."
        )

    elif data == "help":
        send(
            chat_id,
            "📖 HƯỚNG DẪN\n"
            "/start - Mở menu\n"
            "/adduid UID ghi_chu - Thêm UID\n"
            "/uids - Danh sách UID\n"
            "/setstatus ID LIVE|DIE|UNKNOWN - Cập nhật thủ công\n"
            "/stats - Thống kê"
        )


def handle_message(message):
    chat_id = message["chat"]["id"]
    user_id = message.get("from", {}).get("id")
    text = (message.get("text") or "").strip()

    if user_id != ADMIN_ID:
        send(chat_id, "⛔ Chỉ Admin được sử dụng bot.")
        return

    if text in ("/start", "/menu"):
        show_menu(chat_id)

    elif text.startswith("/adduid "):
        parts = text.split(maxsplit=2)

        if len(parts) < 2 or not parts[1].isdigit():
            send(chat_id, "Cú pháp: /adduid UID ghi_chu")
            return

        note = parts[2] if len(parts) > 2 else ""

        try:
            with LOCK:
                cur = DB.execute(
                    "INSERT INTO uids(uid,note) VALUES(?,?)",
                    (parts[1], note)
                )
                DB.commit()

            send(chat_id, f"✅ Đã lưu UID. Mã quản lý: #{cur.lastrowid}")

        except sqlite3.IntegrityError:
            send(chat_id, "ℹ️ UID này đã tồn tại.")

    elif text == "/uids":
        list_uids(chat_id)

    elif text.startswith("/setstatus "):
        parts = text.split()

        if (
            len(parts) != 3
            or not parts[1].isdigit()
            or parts[2].upper() not in ("LIVE", "DIE", "UNKNOWN")
        ):
            send(chat_id, "Cú pháp: /setstatus ID LIVE|DIE|UNKNOWN")
            return

        status = {
            "LIVE": "LIVE",
            "DIE": "DIE",
            "UNKNOWN": "KHÔNG XÁC ĐỊNH"
        }[parts[2].upper()]

        with LOCK:
            row = DB.execute(
                "SELECT uid,status FROM uids WHERE id=?",
                (parts[1],)
            ).fetchone()

            if row:
                DB.execute(
                    "UPDATE uids SET status=?, "
                    "checked_at=datetime('now') WHERE id=?",
                    (status, parts[1])
                )
                DB.commit()

        if row:
            send(
                chat_id,
                f"🔔 LHTMEDIA CẬP NHẬT UID\n"
                f"UID: {row[0]}\n"
                f"{row[1]} → {status}\n"
                f"Nguồn: Admin cập nhật thủ công."
            )
        else:
            send(chat_id, "❌ Không tìm thấy mã UID.")

    elif text in ("/stats", "/uidstatus"):
        show_stats(chat_id)

    elif text == "/help":
        send(
            chat_id,
            "/start - Mở menu\n"
            "/adduid UID ghi_chu - Thêm UID\n"
            "/uids - Danh sách UID\n"
            "/setstatus ID LIVE|DIE|UNKNOWN - Cập nhật thủ công\n"
            "/stats - Thống kê"
        )

    else:
        send(chat_id, "Gửi /start để mở menu.")


def polling():
    offset = None
    print("LHTMEDIA polling started")

    while True:
        try:
            params = {"timeout": 25}

            if offset is not None:
                params["offset"] = offset

            r = requests.get(
                API + "getUpdates",
                params=params,
                timeout=35
            )
            r.raise_for_status()

            for update in r.json().get("result", []):
                offset = update["update_id"] + 1

                if "message" in update:
                    handle_message(update["message"])

                elif "callback_query" in update:
                    handle_callback(update["callback_query"])

        except Exception as e:
            print("Polling error:", e)
            time.sleep(4)


app = Flask(__name__)


@app.get("/")
def home():
    return "LHTMEDIA BOT is running", 200


if __name__ == "__main__":
    init_db()

    Thread(target=polling, daemon=True).start()

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "10000"))
    )
