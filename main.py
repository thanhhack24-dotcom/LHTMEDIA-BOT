
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
        DB.execute("""CREATE TABLE IF NOT EXISTS uids(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT UNIQUE,
            note TEXT DEFAULT '',
            status TEXT DEFAULT 'CHƯA KIỂM TRA',
            checked_at TEXT DEFAULT ''
        )""")

        DB.execute("""CREATE TABLE IF NOT EXISTS saved_links(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            url TEXT,
            note TEXT DEFAULT ''
        )""")

        DB.execute("""CREATE TABLE IF NOT EXISTS tasks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            status TEXT DEFAULT 'Đang làm'
        )""")
        DB.commit()


def tg(method, payload):
    try:
        r = requests.post(
            API + method,
            json=payload,
            timeout=25
        )
        r.raise_for_status()
        return r.json()
    except requests.RequestException as exc:
        print("Telegram API:", exc)
        return None


def send(chat_id, text, markup=None):
    data = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True
    }

    if markup:
        data["reply_markup"] = markup

    tg("sendMessage", data)


MENU = {
    "keyboard": [
        [{"text": "➕ Thêm UID FB"}, {"text": "⭐ Check Meta"}],
        [{"text": "📋 Danh sách"}, {"text": "🔎 Check Info Full"}],
        [{"text": "🎵 Thêm TikTok"}, {"text": "📊 Thống kê"}],
        [{"text": "👤 Tài khoản"}, {"text": "🍪 Cookie / 🔐 2FA"}],
        [{"text": "💬 Chat Support"}, {"text": "🎁 Mã Giới Thiệu"}],
        [{"text": "🖼 Avatar Facebook"}, {"text": "▶️ Thêm YouTube"}],
        [{"text": "👥 Thêm Group FB"}, {"text": "📸 Thêm Instagram"}],
        [{"text": "📝 Thêm Post Facebook"}, {"text": "🔄 Trạng thái UID"}],
        [{"text": "🤖 Bot con của bạn"}, {"text": "🏞 Ảnh bìa Facebook"}],
        [{"text": "🎧 Tìm nhạc"}, {"text": "📖 Hướng dẫn"}],
        [{"text": "🏠 Menu chính"}]
    ],
    "resize_keyboard": True,
    "is_persistent": True,
    "input_field_placeholder": "Chọn chức năng LHTMEDIA..."
}


WELCOME = (
    "🟣 LHTMEDIA MANAGER ⭐️\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "『QUẢN LÝ & THEO DÕI UID 📌』\n"
    "✦ Thêm UID và lưu ghi chú\n"
    "✦ Quản lý danh sách UID\n"
    "✦ Lưu trạng thái đã xác minh\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "『CÔNG CỤ FACEBOOK 🔵』\n"
    "✦ Tra cứu liên kết/hồ sơ công khai\n"
    "✦ Lưu link avatar và ảnh bìa\n"
    "✦ Quản lý ghi chú và bài viết\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "『TIKTOK • GROUP • INSTAGRAM 🎵』\n"
    "✦ Lưu và quản lý liên kết hồ sơ\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "『BOT & TIỆN ÍCH 🤖』\n"
    "✦ Thống kê, nhiệm vụ, hỗ trợ\n"
    "✦ Tích hợp ngoài cần API phù hợp\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "⚠️ LIVE/DIE không thể xác minh tự động "
    "cho mọi UID."
)


def show_menu(chat_id):
    send(chat_id, WELCOME, MENU)


def stats(chat_id):
    with LOCK:
        n_uid = DB.execute(
            "SELECT COUNT(*) FROM uids"
        ).fetchone()[0]

        n_links = DB.execute(
            "SELECT COUNT(*) FROM saved_links"
        ).fetchone()[0]

        n_tasks = DB.execute(
            "SELECT COUNT(*) FROM tasks"
        ).fetchone()[0]

        rows = DB.execute(
            "SELECT status,COUNT(*) FROM uids GROUP BY status"
        ).fetchall()

    states = dict(rows)

    send(
        chat_id,
        "📊 THỐNG KÊ LHTMEDIA\n"
        f"👤 UID: {n_uid}\n"
        f"🔗 Liên kết: {n_links}\n"
        f"📌 Nhiệm vụ: {n_tasks}\n"
        f"🟢 LIVE: {states.get('LIVE', 0)}\n"
        f"🔴 DIE: {states.get('DIE', 0)}\n"
        f"⚪ Chưa xác định: "
        f"{states.get('KHÔNG XÁC ĐỊNH', 0) + states.get('CHƯA KIỂM TRA', 0)}"
    )


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
            f"Ghi chú: {note or '—'}"
        )

    send(chat_id, "\n\n".join(lines))


def save_link(chat_id, category, url):
    if not url.startswith(("https://", "http://")):
        send(chat_id, "❌ Link không hợp lệ.")
        return

    with LOCK:
        DB.execute(
            "INSERT INTO saved_links(category,url) VALUES(?,?)",
            (category, url)
        )
        DB.commit()

    send(chat_id, f"✅ Đã lưu {category}:\n{url}")


def handle(m):
    chat_id = m["chat"]["id"]
    user_id = m.get("from", {}).get("id")
    text = (m.get("text") or "").strip()

    if user_id != ADMIN_ID:
        send(chat_id, "⛔ Chỉ Admin được sử dụng bot.")
        return

    if not text:
        return

    if text in ("/start", "/menu", "🏠 Menu chính"):
        show_menu(chat_id)

    elif text == "➕ Thêm UID FB":
        send(
            chat_id,
            "➕ THÊM UID FACEBOOK\n"
            "Gửi:\n/adduid UID ghi_chu\n"
            "Ví dụ: /adduid 123456789 can_theo_doi"
        )

    elif text.startswith("/adduid "):
        p = text.split(maxsplit=2)

        if len(p) < 2 or not p[1].isdigit():
            send(chat_id, "Cú pháp: /adduid UID ghi_chu")
            return

        note = p[2] if len(p) > 2 else ""

        try:
            with LOCK:
                cur = DB.execute(
                    "INSERT INTO uids(uid,note) VALUES(?,?)",
                    (p[1], note)
                )
                DB.commit()

            send(chat_id, f"✅ Đã thêm UID. Mã quản lý: #{cur.lastrowid}")

        except sqlite3.IntegrityError:
            send(chat_id, "ℹ️ UID này đã tồn tại.")

    elif text in ("📋 Danh sách", "/uids"):
        list_uids(chat_id)

    elif text.startswith("/setstatus "):
        p = text.split()

        if (
            len(p) != 3
            or not p[1].isdigit()
            or p[2].upper() not in ("LIVE", "DIE", "UNKNOWN")
        ):
            send(chat_id, "Cú pháp: /setstatus ID LIVE|DIE|UNKNOWN")
            return

        state = {
            "LIVE": "LIVE",
            "DIE": "DIE",
            "UNKNOWN": "KHÔNG XÁC ĐỊNH"
        }[p[2].upper()]

        with LOCK:
            row = DB.execute(
                "SELECT uid,status FROM uids WHERE id=?",
                (p[1],)
            ).fetchone()

            if row:
                DB.execute(
                    "UPDATE uids SET status=?,checked_at=datetime('now') WHERE id=?",
                    (state, p[1])
                )
                DB.commit()

        if row:
            send(
                chat_id,
                f"🔔 CẬP NHẬT UID\n"
                f"UID: {row[0]}\n"
                f"{row[1]} → {state}\n"
                f"Nguồn: Admin cập nhật thủ công."
            )
        else:
            send(chat_id, "❌ Không tìm thấy mã UID.")

    elif text in (
        "⭐ Check Meta",
        "🔎 Check Info Full",
        "🔄 Trạng thái UID"
    ):
        send(
            chat_id,
            "🔎 TRA CỨU TRẠNG THÁI\n"
            "Chức năng này cần API chính thức và quyền phù hợp. "
            "Bot chưa tự động xác minh LIVE/DIE."
        )

    elif text in ("📊 Thống kê", "/stats"):
        stats(chat_id)

    elif text in (
        "🎵 Thêm TikTok",
        "▶️ Thêm YouTube",
        "👥 Thêm Group FB",
        "📸 Thêm Instagram",
        "📝 Thêm Post Facebook",
        "🖼 Avatar Facebook",
        "🏞 Ảnh bìa Facebook"
    ):
        categories = {
            "🎵 Thêm TikTok": "TikTok",
            "▶️ Thêm YouTube": "YouTube",
            "👥 Thêm Group FB": "Facebook Group",
            "📸 Thêm Instagram": "Instagram",
            "📝 Thêm Post Facebook": "Facebook Post",
            "🖼 Avatar Facebook": "Facebook Avatar",
            "🏞 Ảnh bìa Facebook": "Facebook Cover"
        }

        cat = categories[text]
        send(chat_id, f"Gửi link theo cú pháp:\n/save {cat} https://...")

    elif text.startswith("/save "):
        p = text.split(maxsplit=2)

        if len(p) < 3:
            send(chat_id, "Cú pháp: /save LOẠI LINK")
        else:
            save_link(chat_id, p[1], p[2])

    elif text == "👤 Tài khoản":
        send(
            chat_id,
            f"👤 LHTMEDIA ADMIN\nTelegram ID: {ADMIN_ID}"
        )

    elif text == "🍪 Cookie / 🔐 2FA":
        send(
            chat_id,
            "🔐 Bot không nhận hoặc lưu Cookie, mật khẩu hay mã 2FA. "
            "Không gửi thông tin đăng nhập vào Telegram."
        )

    elif text == "💬 Chat Support":
        send(chat_id, "💬 Hãy gửi nội dung lỗi hoặc ảnh chụp màn hình.")

    elif text == "🎁 Mã Giới Thiệu":
        send(chat_id, "🎁 Chức năng mã giới thiệu chưa cấu hình.")

    elif text == "🤖 Bot con của bạn":
        send(
            chat_id,
            "🤖 Chức năng bot con cần cấu hình riêng. "
            "Không gửi Bot Token vào cuộc trò chuyện."
        )

    elif text == "🎧 Tìm nhạc":
        send(chat_id, "🎧 Chức năng tìm nhạc chưa kết nối API.")

    elif text in ("📖 Hướng dẫn", "/help"):
        send(
            chat_id,
            "📖 HƯỚNG DẪN\n"
            "/start - Mở menu\n"
            "/adduid UID ghi_chu - Thêm UID\n"
            "/uids - Danh sách UID\n"
            "/setstatus ID LIVE|DIE|UNKNOWN - Cập nhật thủ công\n"
            "/stats - Thống kê\n"
            "/save LOẠI LINK - Lưu liên kết"
        )

    elif text == "/uidstatus":
        stats(chat_id)

    else:
        send(chat_id, "Gửi /start để mở menu.")


def polling():
    offset = None
    print("LHTMEDIA started")

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
                    handle(update["message"])

        except Exception as exc:
            print("Polling error:", exc)
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
