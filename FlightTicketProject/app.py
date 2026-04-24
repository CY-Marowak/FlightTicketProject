# from calendar import c
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import os
import requests
import psycopg2
#import sqlite3
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone, date
from functools import wraps
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from psycopg2 import IntegrityError # PostgreSQL 約束錯誤
# 使用 eventlet 啟動 SocketIO 伺服器
import eventlet    
import eventlet.wsgi
import logging
from backend_version import BACKEND_VERSION

print(f"Backend Version: {BACKEND_VERSION}") # 目前後端版本

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

# 在 Render 的 Environment 設定中增加 DATABASE_URL
DB_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    # PostgreSQL 連線方式
    conn = psycopg2.connect(DB_URL)
    return conn

# === 統一初始化所有 PostgreSQL 表格 ===
def init_all_tables():
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # 1. Users
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT,
                expo_push_token TEXT
            )
        """)
        
        # 2. Tracked Flights
        c.execute("""
            CREATE TABLE IF NOT EXISTS tracked_flights (
                id SERIAL PRIMARY KEY,
                from_airport TEXT,
                to_airport TEXT,
                flight_number TEXT,
                airline TEXT,
                depart_time TEXT,
                arrival_time TEXT,
                price DOUBLE PRECISION,
                user_id INTEGER REFERENCES users(id)
            )
        """)
        
        # 3. Notifications
        c.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                flight_id INTEGER REFERENCES tracked_flights(id) ON DELETE SET NULL,
                notify_time TEXT,
                price DOUBLE PRECISION,
                message TEXT
            )
        """)
        
        # 4. Scheduler Logs
        c.execute("""
            CREATE TABLE IF NOT EXISTS scheduler_logs (
                id SERIAL PRIMARY KEY,
                time TEXT,
                status TEXT
            )
        """)
        
        # 5. Prices
        c.execute("""
            CREATE TABLE IF NOT EXISTS prices (
                id SERIAL PRIMARY KEY,
                flight_id INTEGER REFERENCES tracked_flights(id) ON DELETE CASCADE,
                checked_time TEXT,
                price DOUBLE PRECISION
            )
        """)
        
        conn.commit()
        print("✅ PostgreSQL 資料表初始化完成")
    except Exception as e:
        print(f"❌ 初始化資料表失敗: {e}")
        conn.rollback()
    finally:
        c.close()
        conn.close()
# ------------------------------------
# === 刪除所有 PostgreSQL 表格 ===
def drop_all_tables():
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # 依序刪除（或使用 CASCADE）
        c.execute("DROP TABLE IF EXISTS prices CASCADE")
        c.execute("DROP TABLE IF EXISTS notifications CASCADE")
        c.execute("DROP TABLE IF EXISTS scheduler_logs CASCADE")
        c.execute("DROP TABLE IF EXISTS tracked_flights CASCADE")
        c.execute("DROP TABLE IF EXISTS users CASCADE")

        conn.commit()
        print("🗑️ 所有 PostgreSQL 資料表已刪除")

    except Exception as e:
        print(f"❌ 刪除資料表失敗: {e}")
        conn.rollback()

    finally:
        c.close()
        conn.close()
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
    
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute("""
            INSERT INTO users (username, password_hash, created_at)
            VALUES (%s, %s, %s)
        """, (username, password_hash, datetime.now(timezone.utc).isoformat()))
        conn.commit()
    except IntegrityError:
        return jsonify({"error": "此使用者已存在"}), 400
    finally:
        c.close()
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
    push_token = data.get("push_token") # 接收前端傳來的 Token
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, password_hash FROM users WHERE username = %s", (username,))
    row = c.fetchone()
    c.close()
    conn.close()
    
    if not row:
        return jsonify({"error": "使用者不存在"}), 400
    
    user_id, password_hash = row
    
    if not bcrypt.checkpw(password.encode(), password_hash.encode()):
        return jsonify({"error": "密碼錯誤"}), 400

    # 登入成功後，更新 Push Token
    if push_token:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET expo_push_token = %s WHERE id = %s", (push_token, user_id))
        conn.commit()
        cur.close()
        conn.close()
    
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

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE id = %s", (request.user_id,))
    row = c.fetchone()
    
    if not row:
        c.close()
        conn.close()
        return jsonify({"error": "找不到使用者"}), 404
    hashed = row[0]

    # 驗證舊密碼
    if not bcrypt.checkpw(old_pw.encode(), hashed.encode()):
        c.close()
        conn.close()
        return jsonify({"error": "舊密碼錯誤"}), 400

    # 新密碼加密
    new_hashed = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
    c.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hashed, request.user_id))
    conn.commit()
    c.close()
    conn.close()
    
    return jsonify({"message": "密碼更新成功"})

# === 取得個人資料 ===
@app.route("/profile", methods=["GET"])
@token_required
def get_profile():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, username, created_at FROM users WHERE id = %s", (request.user_id,))
    row = c.fetchone()
    c.close()
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
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT time, status FROM scheduler_logs ORDER BY time DESC LIMIT 20")
    rows = c.fetchall()
    c.close()
    conn.close()
    
    return jsonify([{"time": r[0], "status": r[1]} for r in rows])

# === 查詢通知紀錄 ===
@app.route("/notifications", methods=["GET"])
@login_required
def get_notifications():
    user_id = request.user_id
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, flight_id, message, notify_time, price
        FROM notifications
        WHERE user_id = %s
        ORDER BY notify_time DESC
    """, (user_id,))

    rows = c.fetchall()
    c.close()
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
        # "return_date": return_date, 不看回程 所有都預設單趟
        "adults": "1",
        "currency": "TWD",
        "trip_type": "one_way" # 強制告訴 API 我只要看單程
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
        itineraries = data.get("data", {}).get("itineraries", {})
        all_itineraries = itineraries.get("topFlights", []) + itineraries.get("otherFlights", [])

        if not all_itineraries:
            return jsonify({
                "from": departure_id,
                "to": arrival_id,
                "outbound_date": outbound_date,
                "message": "查無符合的航班資料"
            })
        
        flights = []
        for f in all_itineraries:
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
        cheapest_flights = flights[:10]
        
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

    conn = get_db_connection()
    c = conn.cursor()

    # 檢查是否已經追蹤過（同user、同航班號、同出發時間）
    c.execute("""
        SELECT id FROM tracked_flights 
        WHERE user_id = %s AND flight_number = %s AND depart_time = %s
    """, (user_id, data["flight_number"], data["depart_time"]))

    existing_flight = c.fetchone()
    if existing_flight:
        c.close()
        conn.close()
        return jsonify({"error": f"您已經追蹤過此航班 {data['flight_number']} 了"}), 409

    # 沒追蹤過 加入追蹤
    c.execute("""
        INSERT INTO tracked_flights (from_airport, to_airport, flight_number, airline, depart_time, arrival_time, price, user_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        data["from"], data["to"], data["flight_number"], data["airline"],
        data["depart_time"], data["arrival_time"], data["price"], user_id
    ))
    flight_id = c.fetchone()[0]

    # 寫入 price history
    now = datetime.now(timezone.utc).isoformat()
    c.execute("""
        INSERT INTO prices (flight_id, checked_time, price)
        VALUES (%s, %s, %s)
    """, (flight_id, now, data["price"]))
    
    conn.commit()
    c.close()
    conn.close()
    
    return jsonify({"message": f"已成功加入追蹤航班 {data['flight_number']}"}), 200

# === 查詢目前追蹤中的航班 ===
@app.route("/flights", methods=["GET"])
@login_required
def get_tracked_flights():
    user_id = request.user_id
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, from_airport, to_airport, flight_number, airline, depart_time, arrival_time, price
        FROM tracked_flights
        WHERE user_id = %s
    """, (user_id,))
    rows = c.fetchall()
    c.close()
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
    conn = get_db_connection()
    c = conn.cursor()
    
    # 確認這個 flight 是此使用者的
    c.execute("SELECT 1 FROM tracked_flights WHERE id = %s AND user_id = %s", (flight_id, user_id))
    if not c.fetchone():
        c.close()
        conn.close()
        return jsonify({"error": "無權查詢此航班或航班不存在"}), 404
    
    c.execute("SELECT checked_time, price FROM prices WHERE flight_id = %s ORDER BY checked_time ASC", (flight_id,))
    rows = c.fetchall()
    c.close()
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
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM tracked_flights WHERE id = %s AND user_id = %s", (flight_id, user_id))
    deleted = c.rowcount
    conn.commit()
    c.close()
    conn.close()
    
    if deleted == 0:
        return jsonify({"error": "找不到此航班或無權刪除"}), 404
    
    return jsonify({"message": f"已刪除追蹤航班 ID {flight_id}"}), 200

# 檢查expo_push_token
@app.route("/debug/tokens")
def debug_tokens():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT username, expo_push_token FROM users")
    users = c.fetchall()
    c.close()
    conn.close()
    return jsonify(users)

# ------------------------------------
# 發送推播
def send_push_notification(expo_token, title, body):
    if not expo_token or not expo_token.startswith("ExponentPushToken"):
        return
        
    url = "https://exp.host/--/api/v2/push/send"
    payload = {
        "to": expo_token,
        "title": title,
        "body": body,
        "sound": "default",
        "data": {"type": "price_drop"} # 可以放自訂資料
    }
    
    try:
        response = requests.post(url, json=payload)
        print(f"📡 推播發送結果: {response.json()}")
    except Exception as e:
        print(f"❌ 推播發送失敗: {e}")

# == 標準日期 ==
def normalize_date(dt):
    return datetime.strptime(dt.split()[0], "%Y-%m-%d").strftime("%Y-%m-%d")

# === 查詢最新票價 ===
def fetch_latest_price(from_airport, to_airport, depart_time, return_time, flight_number):
    # 清理航班編號與日期格式
    flight_number = flight_number.replace(" ", "").strip()

    url = f"https://{RAPIDAPI_HOST}/api/v1/searchFlights"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }
    query = {
        "departure_id": from_airport,
        "arrival_id": to_airport,
        "outbound_date": normalize_date(depart_time),
        "adults": "1",
        "currency": "TWD",
        "trip_type": "one_way" # 提示 API 單程
    }
    # 確保 flight_number 乾淨，例如 "MM930"
    target_f_no = flight_number.replace(" ", "").upper().strip()

    try:
        res = requests.get(url, headers=headers, params=query, timeout=30)
        if res.status_code != 200:
            print(f"⚠️ API 錯誤: {res.status_code} {res.text[:200]}")
            return None
        
        data = res.json()
        itineraries = data.get("data", {}).get("itineraries", {})
        
        # 把所有可能的航班清單合併
        all_itineraries = (
            itineraries.get("topFlights", []) + 
            itineraries.get("otherFlights", [])
        )

        for f in all_itineraries:
            f_no = f["flights"][0]["flight_number"].replace(" ", "").upper().strip()
          
            # 比對價格與編號
            if f["price"] != "unavailable" and f_no == target_f_no:
                return float(f["price"])
        
        print(f"⚠️ 找不到航班 {flight_number} 的最新票價")
        return None
    
    except Exception as e:
        print(f"⚠️ 抓取票價錯誤: {e}")
        return None

# 自動檢查票價
def scheduled_price_check():
    print("🔄 開始自動檢查票價...")
    conn = get_db_connection()
    c = conn.cursor()

    # 取得今天的日期 (格式需與資料庫中的 depart 格式一致，假設為 yyyy-MM-dd)
    today_str = date.today().isoformat()
    print(f"今天日期: {today_str}")

    # 先取得所有 user_id
    c.execute("SELECT DISTINCT user_id FROM tracked_flights WHERE user_id IS NOT NULL")
    all_users = [row[0] for row in c.fetchall()]

    for user_id in all_users:
        print(f"👤 正在檢查使用者 {user_id} 的航班...")
        
        # 取得此使用者的航班
        c.execute("""
            SELECT id, from_airport, to_airport, flight_number, depart_time, arrival_time, price
            FROM tracked_flights
            WHERE user_id = %s
        """, (user_id,))
        flights = c.fetchall()

        for f in flights:
            flight_id, from_a, to_a, flight_no, depart, arrive, old_price = f
            now = datetime.now(timezone.utc).isoformat()

            # 檢查航班是否過期
            if normalize_date(depart) < today_str:
                print(f"🗑️ 航班 {flight_no} 已過期，正在進行最後紀錄並移除...")
    
                # 1. 寫入最後一則通知訊息
                expiry_msg = f"系統通知：航班 {flight_no} ({from_a} -> {to_a}) 已於 {depart} 出發，追蹤任務結束。"
                c.execute("""
                    INSERT INTO notifications (flight_id, user_id, message, notify_time, price)
                    VALUES (%s, %s, %s, %s, %s)
                """, (flight_id, user_id, expiry_msg, now, old_price))
    
                # 2. 執行刪除
                c.execute("DELETE FROM tracked_flights WHERE id = %s", (flight_id,))
                conn.commit()
                continue
            
            new_price = fetch_latest_price(from_a, to_a, depart, arrive, flight_no)
            
            if new_price is None:
                print(f"⚠️ {flight_no}（user {user_id}）票價更新失敗")
                continue

            # 查詢歷史最低價 (用於判斷是否發送低價通知)
            c.execute("SELECT MIN(price) FROM prices WHERE flight_id = %s", (flight_id,))
            min_price_row = c.fetchone()
            # 預防 min_price 為 None，第一次加入
            min_price = min_price_row[0] if min_price_row[0] is not None else new_price

            # 寫入 price history
            c.execute("""
                INSERT INTO prices (flight_id, checked_time, price)
                VALUES (%s, %s, %s)
            """, (flight_id, now, new_price))
            conn.commit()

            # 價格變動 更新 tracked_flights 表中的當前價格
            if new_price != old_price:
                c.execute("""
                    UPDATE tracked_flights 
                    SET price = %s 
                    WHERE id = %s
                """, (new_price, flight_id))
                print(f"📝 {flight_no} 價格已從 {old_price} 更新為 {new_price}")
            
            if new_price < min_price:
                message = f""""
                    {flight_no} 出現新低價: {new_price} TWD
                    {from_a} -> {to_a} | 出發日期: {depart}
                    """
                print(f"💰 User {user_id} | {message}")
                
                # 寫入通知紀錄
                c.execute("""
                    INSERT INTO notifications (flight_id, user_id, message, notify_time, price)
                    VALUES (%s, %s, %s, %s, %s)
                """, (flight_id, user_id, message, now, new_price))
                #獲取該使用者的 Push Token (新加入)
                c.execute("""
                    SELECT u.expo_push_token 
                    FROM users u
                    JOIN tracked_flights tf ON tf.user_id = u.id
                    WHERE tf.id = %s
                """, (flight_id,))

                result = c.fetchone()
                user_push_token = result[0] if result else None

                # 發送真正的手機系統通知
                if user_push_token:
                    send_push_notification(
                        user_push_token, 
                        "💰 降價提醒", 
                        message
                    )
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
        VALUES (%s, %s)
    """, (datetime.now(timezone.utc).isoformat(), "OK"))
    conn.commit()
    c.close()
    conn.close()
    
    print("✅ 所有使用者的自動票價更新與過期清理完成")

def keep_alive():
    try:
        url = "https://flightticketproject.onrender.com/" 
        requests.get(url, timeout=10)
        print("⛽ 自我喚醒請求成功")
    except Exception as e:
        print(f"⚠️ 自我喚醒失敗: {e}")


# ==============================================
# 正式啟動後端（eventlet + SocketIO）
# ==============================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 使用 eventlet 啟動 SocketIO Server，埠號：{port}")
    
    # 刪除資料表
    drop_all_tables()
    # 在啟動伺服器前先檢查並建立資料表
    init_all_tables()

    # 取得當前是否為 Debug 模式
    is_debug = False

    # 1. 生產環境(debug=False)直接啟動 2. 開發環境(debug=True) 則檢查是否為 Werkzeug 的主進程
    if not is_debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        scheduler = BackgroundScheduler()
        # 每11分鐘戳自己一下，防止render休眠 (15mins)
        scheduler.add_job(keep_alive, "interval", minutes=11)
        # 檢查機票
        scheduler.add_job(scheduled_price_check, "interval", minutes=60)
        scheduler.start()
        print("🕒 APScheduler 已啟動")

    # 用socketio.run 不是 wsgi.server
    socketio.run(app, host="0.0.0.0", port=port, debug=False)
