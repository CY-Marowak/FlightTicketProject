# from calendar import c
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import os
import requests
import sqlite3
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from functools import wraps
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
# 使用 eventlet 啟動 SocketIO 伺服器
import eventlet    
import eventlet.wsgi
import logging

load_dotenv()  # 載入 .env

# 新增 JWT Secret Key
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGO = "HS256"
JWT_EXPIRE_MINUTES = 10080  # 7 天

app = Flask(__name__)
app.json.ensure_ascii = False # 解決中文被轉成uni的問題

# 解決全域開發問題
CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    supports_credentials=True
)

# logger 讓系統可以log每次執行的操作
log = logging.getLogger('werkzeug')
log.setLevel(logging.INFO)
# 自訂 before_request log（讓每個 API 都印出清楚的請求資訊）
@app.before_request
def log_request():
    print(f"[REQ] {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} | "
          f"{request.remote_addr} | {request.method} {request.path}")

# 初始化 SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# === RapidAPI 設定 ===
RAPIDAPI_HOST = "google-flights2.p.rapidapi.com"
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

# === 初始化 SQLite ===
DB_NAME = "flights.db"
# === 建立 users 表格 ===
def init_user_table():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

# === 建立 trackflights 表格 ===
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS tracked_flights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_airport TEXT,
            to_airport TEXT,
            flight_number TEXT,
            airline TEXT,
            depart_time TEXT,
            arrival_time TEXT,
            price REAL,
            user_id INTEGER
        )
    """)
    conn.commit()
    conn.close()

# === 建立 notifications 表格 ===
def init_notification_table():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flight_id INTEGER,
            notify_time TEXT,
            price REAL,
            message TEXT
        )
    """)
    conn.commit()
    conn.close()

# === 建立 scheduler_logs 表格 ===
def init_scheduler_log_table():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS scheduler_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()

# === 建立 prices 表格 ===
def init_price_table():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flight_id INTEGER,
            checked_time TEXT,
            price REAL,
            FOREIGN KEY(flight_id) REFERENCES tracked_flights(id)
        )
    """)
    conn.commit()
    conn.close()

# --- DB INIT ---
init_user_table()
init_db()
init_notification_table()
init_scheduler_log_table()
init_price_table()
# ------------------------------------


# === 正常顯示首頁 ===
@app.route("/", methods=["GET"])
def index():
    return "✅ Flight Ticket Tracker Backend is running!"

# === 建立 token 驗證 (所有 API 加上登入保護) ===
def login_required(f):
    @wraps(f)
    def login_wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "缺少或無效的 token"}), 401
        
        token = auth_header.split(" ")[1]
        
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
            request.user_id = payload["user_id"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token 已過期"}), 401
        except Exception:
            return jsonify({"error": "Token 無效"}), 401
        
        return f(*args, **kwargs)
    return login_wrapper

# -------------------------
# 驗證 JWT 用的 decorator
# -------------------------
def token_required(f):
    @wraps(f)
    def token_wrapper(*args, **kwargs):
        token = request.headers.get("Authorization")
        
        if not token:
            return jsonify({"error": "缺少 Token"}), 401
        try:
            token = token.replace("Bearer ", "")
            data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
            request.user_id = data["user_id"]
        except Exception as e:
            return jsonify({"error": f"Token 無效: {e}"}), 401
        
        return f(*args, **kwargs)
    return token_wrapper


# === Hash 密碼 + 註冊 API (POST /register) ===
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data:
        return jsonify({"error": "缺少資料"}), 400
    
    username = data.get("username")
    password = data.get("password")
    
    if not username or not password:
        return jsonify({"error": "請輸入 username 與 password"}), 400

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    try:
        c.execute("""
            INSERT INTO users (username, password_hash, created_at)
            VALUES (?, ?, ?)
        """, (username, password_hash, datetime.now(timezone.utc).isoformat()))
        conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "此使用者已存在"}), 400
    finally:
        conn.close()
    
    return jsonify({"message": "註冊成功"}), 200

# === 登入 API ===
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"error": "缺少資料"}), 400
    
    username = data.get("username")
    password = data.get("password")
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return jsonify({"error": "使用者不存在"}), 400
    
    user_id, password_hash = row
    
    if not bcrypt.checkpw(password.encode(), password_hash.encode()):
        return jsonify({"error": "密碼錯誤"}), 400
    
    token = jwt.encode(
        {
            "user_id": user_id,
            "username": username,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
        },
        JWT_SECRET,
        algorithm=JWT_ALGO
    )

    return jsonify({
    "message": "登入成功",
    "token": token,
    "user_id": user_id,
    "username": username
}), 200

# === 修改密碼 ===
@app.route("/change_password", methods=["POST"])
@token_required
def change_password():
    json_data = request.get_json()
    old_pw = json_data.get("old_password")
    new_pw = json_data.get("new_password")
    
    if not old_pw or not new_pw:
        return jsonify({"error": "缺少 old/new password"}), 400

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE id = ?", (request.user_id,))
    row = c.fetchone()
    
    if not row:
        conn.close()
        return jsonify({"error": "找不到使用者"}), 404
    hashed = row[0]

    # 驗證舊密碼
    if not bcrypt.checkpw(old_pw.encode(), hashed.encode()):
        conn.close()
        return jsonify({"error": "舊密碼錯誤"}), 400

    # 新密碼加密
    new_hashed = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
    c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hashed, request.user_id))
    conn.commit()
    conn.close()
    
    return jsonify({"message": "密碼更新成功"})

# === 取得個人資料 ===
@app.route("/profile", methods=["GET"])
@token_required
def get_profile():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, username, created_at FROM users WHERE id = ?", (request.user_id,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return jsonify({"error": "找不到使用者"}), 404
    return jsonify({
        "user_id": row[0],
        "username": row[1],
        "created_at": row[2]
    })


# === 查詢排程結果記錄 (所有使用者的) ===
@app.route("/check_logs", methods=["GET"])
def get_scheduler_logs():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT time, status FROM scheduler_logs ORDER BY time DESC LIMIT 20")
    rows = c.fetchall()
    conn.close()
    
    return jsonify([{"time": r[0], "status": r[1]} for r in rows])

# === 查詢通知紀錄 ===
@app.route("/notifications", methods=["GET"])
@login_required
def get_notifications():
    user_id = request.user_id
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT n.id, n.flight_id, n.message, n.notify_time, n.price
        FROM notifications AS n
        JOIN tracked_flights AS t ON n.flight_id = t.id
        WHERE t.user_id = ?
        ORDER BY n.notify_time DESC
    """, (user_id,))
    rows = c.fetchall()
    conn.close()
    
    data = []
    for r in rows:
        data.append({
            "id": r[0],
            "flight_id": r[1],
            "time": r[3],
            "price": r[4],
            "message": r[2]
        })

    return jsonify(data)

# === 查詢航班 ===
@app.route("/price", methods=["GET"])
def get_price():
    departure_id = request.args.get("from")
    arrival_id = request.args.get("to")
    outbound_date = request.args.get("depart")
    return_date = request.args.get("return")

    url = f"https://{RAPIDAPI_HOST}/api/v1/searchFlights"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }
    querystring = {
        "departure_id": departure_id,
        "arrival_id": arrival_id,
        "outbound_date": outbound_date,
        "return_date": return_date,
        "adults": "1",
        "currency": "TWD"
    }

    response = requests.get(url, headers=headers, params=querystring)
    if response.status_code != 200:
        return jsonify({
            "error": "API 呼叫失敗",
            "status_code": response.status_code,
            "response": response.text
        }), 400

    data = response.json()
    try:
        top_flights = data.get("data", {}).get("itineraries", {}).get("topFlights", [])
        if not top_flights:
            return jsonify({
                "from": departure_id,
                "to": arrival_id,
                "outbound_date": outbound_date,
                "return_date": return_date,
                "message": "查無符合的航班資料"
            })
        
        flights = []
        for f in top_flights:
            if f["price"] == "unavailable": # 取全部來看 跳過unavailable
                continue
            flights.append({
                "from": departure_id,
                "to": arrival_id,
                "airline": f["flights"][0]["airline"],
                "flight_number": f["flights"][0]["flight_number"],
                "depart_time": f["flights"][0]["departure_airport"]["time"],
                "arrival_time": f["flights"][0]["arrival_airport"]["time"],
                "price": float(f["price"])
            })
        
            flights.sort(key=lambda x: x["price"])
        cheapest_flights = flights[:5]
        
        return jsonify({
            "from": departure_id,
            "to": arrival_id,
            "outbound_date": outbound_date,
            "return_date": return_date,
            "flights": cheapest_flights
        })
    
    except Exception as e:
        return jsonify({
            "error": "無法解析航班資料",
            "details": str(e),
            "raw": data
        }), 500

# === 加入追蹤 ===
@app.route("/flights", methods=["POST"])
@login_required
def add_flight():
    user_id = request.user_id
    data = request.get_json()
    if not data:
        return jsonify({"error": "缺少航班資料"}), 400

    required_fields = ["from", "to", "flight_number", "airline", "depart_time", "arrival_time", "price"]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"缺少必要欄位：{field}"}), 400

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO tracked_flights (from_airport, to_airport, flight_number, airline, depart_time, arrival_time, price, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["from"], data["to"], data["flight_number"], data["airline"],
        data["depart_time"], data["arrival_time"], data["price"], user_id
    ))
    conn.commit()
    conn.close()
    
    return jsonify({"message": f"已成功加入追蹤航班 {data['flight_number']}"}), 200

# === 查詢目前追蹤中的航班 ===
@app.route("/flights", methods=["GET"])
@login_required
def get_tracked_flights():
    user_id = request.user_id
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT id, from_airport, to_airport, flight_number, airline, depart_time, arrival_time, price
        FROM tracked_flights
        WHERE user_id = ?
    """, (user_id,))
    rows = c.fetchall()
    conn.close()
    
    flights = []
    for row in rows:
        flights.append({
            "id": row[0],
            "from": row[1],
            "to": row[2],
            "flight_number": row[3],
            "airline": row[4],
            "depart_time": row[5],
            "arrival_time": row[6],
            "price": row[7]
        })
    return jsonify(flights)

# === 查詢票價歷史 ===
@app.route("/prices/<int:flight_id>", methods=["GET"])
@login_required
def get_price_history(flight_id):
    user_id = request.user_id
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 確認這個 flight 是此使用者的
    c.execute("SELECT 1 FROM tracked_flights WHERE id = ? AND user_id = ?", (flight_id, user_id))
    if not c.fetchone():
        conn.close()
        return jsonify({"error": "無權查詢此航班或航班不存在"}), 404
    
    c.execute("SELECT checked_time, price FROM prices WHERE flight_id = ? ORDER BY checked_time ASC", (flight_id,))
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        return jsonify({"message": "尚無此航班的歷史票價資料"}), 404
    
    data = [{"time": r[0], "price": r[1]} for r in rows]
    return jsonify(data)

# === 刪除追蹤中的航班 ===
@app.route("/flights/<int:flight_id>", methods=["DELETE"])
@login_required
def delete_flight(flight_id):
    user_id = request.user_id
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM tracked_flights WHERE id = ? AND user_id = ?", (flight_id, user_id))
    deleted = c.rowcount
    conn.commit()
    conn.close()
    
    if deleted == 0:
        return jsonify({"error": "找不到此航班或無權刪除"}), 404
    
    return jsonify({"message": f"已刪除追蹤航班 ID {flight_id}"}), 200


# === 查詢最新票價 ===
def fetch_latest_price(from_airport, to_airport, depart_time, return_time, flight_number):
    # 清理航班編號與日期格式
    flight_number = flight_number.replace(" ", "").strip()
    def normalize_date(dt):
        try:
            return datetime.strptime(dt[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
        except Exception:
            # 假如格式像 2026-3-12，補零
            parts = dt.split(" ")[0].split("-")
            return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"

    url = f"https://{RAPIDAPI_HOST}/api/v1/searchFlights"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }
    query = {
        "departure_id": from_airport,
        "arrival_id": to_airport,
        "outbound_date": normalize_date(depart_time),
        "return_date": normalize_date(return_time),
        "adults": "1",
        "currency": "TWD"
    }

    try:
        res = requests.get(url, headers=headers, params=query, timeout=30)
        if res.status_code != 200:
            print(f"⚠️ API 錯誤: {res.status_code} {res.text[:200]}")
            return None
        
        data = res.json()
        top_flights = data.get("data", {}).get("itineraries", {}).get("topFlights", [])
        for f in top_flights:
            f_no = f["flights"][0]["flight_number"].replace(" ", "").strip()
            if f["price"] != "unavailable" and f_no == flight_number:
                return float(f["price"])
        print(f"⚠️ 找不到航班 {flight_number} 的最新票價")
        return None
    
    except Exception as e:
        print(f"⚠️ 抓取票價錯誤: {e}")
        return None


def scheduled_price_check():
    print("🔄 開始自動檢查票價...")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # 先取得所有 user_id（避免混亂）
    c.execute("SELECT DISTINCT user_id FROM tracked_flights WHERE user_id IS NOT NULL")
    all_users = [row[0] for row in c.fetchall()]

    for user_id in all_users:
        print(f"👤 正在檢查使用者 {user_id} 的航班...")
        
        # 取得此使用者的航班
        c.execute("""
            SELECT id, from_airport, to_airport, flight_number, depart_time, arrival_time, price
            FROM tracked_flights
            WHERE user_id = ?
        """, (user_id,))
        flights = c.fetchall()

        for f in flights:
            flight_id, from_a, to_a, flight_no, depart, arrive, old_price = f
            new_price = fetch_latest_price(from_a, to_a, depart, arrive, flight_no)
            
            if new_price is None:
                print(f"⚠️ {flight_no}（user {user_id}）票價更新失敗")
                continue

            now = datetime.now(timezone.utc).isoformat()

            # 寫入 price history
            c.execute("""
                INSERT INTO prices (flight_id, checked_time, price)
                VALUES (?, ?, ?)
            """, (flight_id, now, new_price))
            conn.commit()

            # 查詢歷史最低價
            c.execute("SELECT MIN(price) FROM prices WHERE flight_id = ?", (flight_id,))
            min_price = c.fetchone()[0]

            if new_price < min_price:
                message = f"{flight_no} 出現新低價：{new_price} TWD !!!!"
                print(f"💰 User {user_id} | {message}")
                
                # 寫入通知紀錄
                c.execute("""
                    INSERT INTO notifications (flight_id, message, notify_time, price)
                    VALUES (?, ?, ?, ?)
                """, (flight_id, message, now, new_price))
                conn.commit()
                
                # 推播到前端 —— 指定 user_id
                socketio.emit(f"price_alert_user_{user_id}", {
                    "flight_number": flight_no,
                    "price": new_price
                })
            
            elif new_price == min_price:
                print(f"💰 User {user_id} | {flight_no} 出現歷史低價：{new_price} TWD")
            else:
                print(f"✈️ User {user_id} | {flight_no} 目前票價：{new_price} TWD")

    # 排程紀錄（全系統）
    c.execute("""
        INSERT INTO scheduler_logs (time, status)
        VALUES (?, ?)
    """, (datetime.now(timezone.utc).isoformat(), "OK"))
    conn.commit()
    conn.close()
    
    print("✅ 所有使用者的自動票價更新完成")


# ==============================================
# 正式啟動後端（eventlet + SocketIO）
# ==============================================
if __name__ == "__main__":
    # 避免 Flask debug reload 啟動兩次 scheduler
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        scheduler = BackgroundScheduler()
        scheduler.add_job(scheduled_price_check, "interval", minutes=10)
        scheduler.start()
        print("🕒 APScheduler 已啟動")

    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 使用 eventlet 啟動 SocketIO Server，埠號：{port}")

    # 必須用 socketio.run，而不是 wsgi.server
    socketio.run(app, host="0.0.0.0", port=port, debug=False)

