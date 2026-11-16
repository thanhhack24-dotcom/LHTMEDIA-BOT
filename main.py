import os
import time
import sqlite3
import requests
from flask import Flask
from threading import Thread

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
API = f"https://api.telegram.org/bot{TOKEN}/"
DB = sqlite3.connect("lhtmedia.db", check_same_thread=False)
DB_LOCK = __import__("threading").Lock()

def init_db():
    with DB_LOCK:
        DB.execute("""CREATE TABLE IF NOT EXISTS uids(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT UNIQUE, note TEXT DEFAULT '',
            status TEXT DEFAULT 'CHƯA KIỂM TRA',
            checked_at TEXT DEFAULT ''
        )""")
        DB.execute("""CREATE TABLE IF NOT EXISTS tasks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT, status TEXT DEFAULT 'Đang làm'
        )""")
        DB.execute("""CREATE TABLE IF NOT EXISTS templates(
            id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT
        )""")
        DB.execute("""CREATE TABLE IF NOT EXISTS links(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT, value TEXT, note TEXT DEFAULT ''
        )""")
        DB.commit()

def api(method, payload):
    try:
        r = requests.post(API + method, json=payload, timeout=25)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            print("Telegram API error:", data)
        return data
    except requests.RequestException as e:
        print("Telegram request error:", e)
        return None

def send(chat_id, text, markup=None):
    p = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if markup:
        p["reply_markup"] = markup
    api("sendMessage", p)

MAIN_MENU = {
    "keyboard": [
        [{"text":"➕ Thêm UID FB"},{"text":"⭐ Check Meta"}],
        [{"text":"📋 Danh sách"},{"text":"🔎 Check Info Full"}],
        [{"text":"🎵 Thêm TikTok"},{"text":"📊 Thống kê"}],
        [{"text":"👤 Tài khoản"},{"text":"🍪 Nạp Cookie"}],
        [{"text":"💬 Chat Support"},{"text":"🎁 Mã Giới Thiệu"}],
        [{"text":"🖼 Avatar Facebook"},{"text":"▶️ Thêm YouTube"}],
        [{"text":"👥 Thêm Group FB"},{"text":"📸 Thêm Instagram"}],
        [{"text":"📝 Thêm Post Facebook"},{"text":"🔄 Check trạng thái UID"}],
        [{"text":"🤖 Bot con của bạn"},{"text":"🖼 Ảnh bìa Facebook"}],
        [{"text":"🎧 Tìm nhạc"},{"text":"🔐 Mã 2FA"}],
        [{"text":"🏠 Menu chính"}]
    ],
    "resize_keyboard": True,
    "is_persistent": True,
    "input_field_placeholder": "Chọn chức năng LHTMEDIA..."
}

def show_menu(chat_id):
    send(chat_id,
         "🟣 LHTMEDIA MANAGER\n"
         "━━━━━━━━━━━━━━━━━━━━\n"
         "Xin chào Admin! Chọn chức năng bên dưới.\n\n"
         "📌 Quản lý UID, lưu liên kết công khai, ghi chú và nhiệm vụ.\n"
         "⚠️ Bot không yêu cầu Cookie, mật khẩu hoặc mã 2FA. "
         "Trạng thái Facebook không thể xác minh tự động với mọi UID.",
         MAIN_MENU)

def count(table):
    with DB_LOCK:
        return DB.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

def list_uids(chat_id):
    with DB_LOCK:
        rows = DB.execute("SELECT id,uid,note,status FROM uids ORDER BY id DESC LIMIT 30").fetchall()
    if not rows:
        send(chat_id, "📋 DANH SÁCH UID\nChưa có UID. Chọn ➕ Thêm UID FB.")
        return
    out = ["📋 DANH SÁCH UID"]
    for rid, uid, note, status in rows:
        out.append(f"#{rid} | UID: {uid}\nTrạng thái: {status}\nGhi chú: {note or '—'}\n/setstatus {rid} LIVE hoặc DIE")
    send(chat_id, "\n\n".join(out))

def add_link(chat_id, category, value, note=""):
    with DB_LOCK:
        DB.execute("INSERT INTO links(category,value,note) VALUES(?,?,?)", (category,value,note))
        DB.commit()
    send(chat_id, f"✅ Đã lưu {category}: {value}")

def handle_message(m):
    user = m.get("from", {})
    chat_id = m["chat"]["id"]
    text = (m.get("text") or "").strip()
    if user.get("id") != ADMIN_ID:
        send(chat_id, "⛔ Chức năng này chỉ dành cho quản trị viên.")
        return
    if not text:
        return

    if text in ("/start","/menu","🏠 Menu chính"):
        show_menu(chat_id)
    elif text in ("/help","ℹ️ Hướng dẫn"):
        send(chat_id,
             "📖 HƯỚNG DẪN LHTMEDIA\n"
             "/adduid UID ghi_chu – lưu UID\n"
             "/uids – danh sách UID\n"
             "/setstatus ID LIVE|DIE|UNKNOWN – cập nhật thủ công\n"
             "/uidstatus – thống kê trạng thái\n"
             "/addtask nội_dung – thêm nhiệm vụ\n"
             "/tasks – xem nhiệm vụ\n"
             "/addtemplate nội_dung – lưu mẫu nội dung\n"
             "/templates – xem mẫu\n"
             "Các mục thêm TikTok/Instagram/YouTube lưu liên kết do bạn cung cấp.\n"
             "Bot không tự xác định khóa/mở khóa tài khoản Facebook.")
    elif text.startswith("/adduid "):
        p = text.split(maxsplit=2)
        if len(p) < 2 or not p[1].isdigit():
            send(chat_id, "Cú pháp: /adduid UID ghi_chu")
            return
        note = p[2] if len(p) > 2 else ""
        try:
            with DB_LOCK:
                cur = DB.execute("INSERT INTO uids(uid,note) VALUES(?,?)", (p[1],note))
                DB.commit()
                rid = cur.lastrowid
            send(chat_id, f"✅ Đã lưu UID.\nMã quản lý: #{rid}")
        except sqlite3.IntegrityError:
            send(chat_id, "ℹ️ UID này đã có trong danh sách.")
    elif text == "➕ Thêm UID FB":
        send(chat_id, "➕ THÊM UID FACEBOOK\nGửi:\n/adduid UID ghi_chu\nVí dụ: /adduid 123456789 can_kiem_tra")
    elif text in ("/uids","📋 Danh sách"):
        list_uids(chat_id)
    elif text.startswith("/setstatus "):
        p = text.split()
        if len(p) != 3 or not p[1].isdigit() or p[2].upper() not in ("LIVE","DIE","UNKNOWN"):
            send(chat_id, "Cú pháp: /setstatus ID LIVE|DIE|UNKNOWN")
            return
        state = {"LIVE":"LIVE","DIE":"DIE","UNKNOWN":"KHÔNG XÁC ĐỊNH"}[p[2].upper()]
        with DB_LOCK:
            row = DB.execute("SELECT uid,status FROM uids WHERE id=?", (p[1],)).fetchone()
            if row:
                DB.execute("UPDATE uids SET status=?,checked_at=datetime('now') WHERE id=?", (state,p[1]))
                DB.commit()
        if not row:
            send(chat_id, "❌ Không tìm thấy mã quản lý. Gửi /uids để xem.")
        else:
            send(chat_id, f"🔔 LHTMEDIA – CẬP NHẬT UID\nUID: {row[0]}\nTrạng thái: {row[1]} → {state}\nNguồn: admin cập nhật thủ công.")
    elif text in ("/uidstatus","🔄 Check trạng thái UID","⭐ Check Meta","🔎 Check Info Full"):
        with DB_LOCK:
            rows = DB.execute("SELECT status,COUNT(*) FROM uids GROUP BY status").fetchall()
        c = {s:n for s,n in rows}
        send(chat_id,
             "🔎 TỔNG HỢP UID\n"
             f"🟢 LIVE đã ghi nhận: {c.get('LIVE',0)}\n"
             f"🔴 DIE đã ghi nhận: {c.get('DIE',0)}\n"
             f"⚪ Không xác định: {c.get('KHÔNG XÁC ĐỊNH',0)}\n"
             f"🕓 Chưa kiểm tra: {c.get('CHƯA KIỂM TRA',0)}\n\n"
             "Đây là dữ liệu đã lưu, không phải kết quả quét tự động Facebook.")
    elif text == "📊 Thống kê":
        send(chat_id, f"📊 THỐNG KÊ LHTMEDIA\nUID: {count('uids')}\nMẫu nội dung: {count('templates')}\nNhiệm vụ: {count('tasks')}\nLiên kết đã lưu: {count('links')}")
    elif text.startswith("/addtask "):
        content = text.split(maxsplit=1)[1]
        with DB_LOCK:
            DB.execute("INSERT INTO tasks(content) VALUES(?)",(content,))
            DB.commit()
        send(chat_id,"✅ Đã thêm nhiệm vụ.")
    elif text in ("/tasks","📌 Nhiệm vụ"):
        with DB_LOCK:
            rows = DB.execute("SELECT id,content,status FROM tasks ORDER BY id DESC LIMIT 30").fetchall()
        send(chat_id, "📌 NHIỆM VỤ\n" + ("\n".join(f"#{i} | {c} | {s}" for i,c,s in rows) or "Chưa có nhiệm vụ."))
    elif text.startswith("/addtemplate "):
        content = text.split(maxsplit=1)[1]
        with DB_LOCK:
            DB.execute("INSERT INTO templates(content) VALUES(?)",(content,))
            DB.commit()
        send(chat_id,"✅ Đã lưu mẫu nội dung.")
    elif text in ("/templates","💬 Mẫu bình luận"):
        with DB_LOCK:
            rows = DB.execute("SELECT id,content FROM templates ORDER BY id DESC LIMIT 30").fetchall()
        send(chat_id, "💬 MẪU NỘI DUNG\n" + ("\n".join(f"#{i} | {c}" for i,c in rows) or "Chưa có mẫu."))
    elif text in ("🎵 Thêm TikTok","▶️ Thêm YouTube","👥 Thêm Group FB","📸 Thêm Instagram","📝 Thêm Post Facebook"):
        category = {
            "🎵 Thêm TikTok":"TikTok","▶️ Thêm YouTube":"YouTube",
            "👥 Thêm Group FB":"Group Facebook","📸 Thêm Instagram":"Instagram",
            "📝 Thêm Post Facebook":"Bài viết Facebook"
        }[text]
        send(chat_id, f"🔗 Gửi liên kết công khai {category} theo cú pháp:\n/save {category} LINK ghi_chu")
    elif text.startswith("/save "):
        p = text.split(maxsplit=2)
        if len(p) < 3 or not p[2].startswith(("https://","http://")):
            send(chat_id, "Cú pháp: /save LOẠI LINK ghi_chu\nVí dụ: /save TikTok https://tiktok.com/@ten")
        else:
            add_link(chat_id,p[1],p[2])
    elif text in ("👤 Tài khoản","🤖 Bot con của bạn"):
        send(chat_id, f"👤 LHTMEDIA ADMIN\nTelegram ID: {ADMIN_ID}\nBot: đang chạy nếu bạn nhận được tin nhắn này.")
    elif text in ("💬 Chat Support",):
        send(chat_id, "💬 HỖ TRỢ LHTMEDIA\nGửi nội dung lỗi hoặc ảnh chụp màn hình trong cuộc trò chuyện này.")
    elif text in ("🎁 Mã Giới Thiệu",):
        send(chat_id, "🎁 MÃ GIỚI THIỆU\nChức năng mã giới thiệu chưa được cấu hình.")
    elif text in ("🖼 Avatar Facebook","🖼 Ảnh bìa Facebook"):
        send(chat_id, "🖼 Gửi đường dẫn ảnh công khai hoặc mô tả yêu cầu. Bot hiện chưa tự tải ảnh đại diện/ảnh bìa từ Facebook.")
    elif text in ("🍪 Nạp Cookie","🔐 Mã 2FA"):
        send(chat_id, "🔒 Vì bảo mật, LHTMEDIA không nhận hoặc lưu Cookie đăng nhập, mật khẩu hay mã 2FA. Không gửi các thông tin này vào bot.")
    elif text in ("🎧 Tìm nhạc",):
        send(chat_id, "🎧 TÌM NHẠC\nChức năng này chưa được kết nối nguồn tìm kiếm.")
    elif text == "/stats":
        send(chat_id, f"UID: {count('uids')} | Tasks: {count('tasks')} | Templates: {count('templates')}")
    else:
        send(chat_id, "Mình chưa nhận diện được lệnh. Gửi /menu để mở bảng chức năng.")

def poll():
    offset = None
    print("LHTMEDIA polling started")
    while True:
        try:
            params = {"timeout":25}
            if offset is not None:
                params["offset"] = offset
            res = requests.get(API+"getUpdates",params=params,timeout=35)
            res.raise_for_status()
            payload = res.json()
            for upd in payload.get("result",[]):
                offset = upd["update_id"] + 1
                if "message" in upd:
                    handle_message(upd["message"])
        except Exception as e:
            print("Polling error:",e)
            time.sleep(4)

app = Flask(__name__)
@app.get("/")
def home():
    return "LHTMEDIA BOT is running", 200

if __name__ == "__main__":
    init_db()
    Thread(target=poll,daemon=True).start()
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT","10000")))
