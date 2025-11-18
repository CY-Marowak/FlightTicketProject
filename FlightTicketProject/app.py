from calendar import c
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
import os
import requests
import sqlite3
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.json.ensure_ascii = False #解決中文被轉成uni的問題

# 初始化 SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# === RapidAPI 設定 ===
RAPIDAPI_HOST = "google-flights2.p.rapidapi.com"
RAPIDAPI_KEY = "c2e285b6f4msh6a1da4d7047fb58p1f5b65jsn96fa996ffe3c"

# === 初始化 SQLite ===
DB_NAME = "flights.db"
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
            price REAL
        )
    """)
    conn.commit()
    conn.close()

'''def check_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(notifications);")
    columns = cur.fetchall()

    for c in columns:
        print(c)

    conn.close()
'''
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

#  === 建立 scheduler_logs 表格 ===
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

# === 查詢排程結果記錄 ===
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
def get_notifications():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, flight_id, message, notify_time FROM notifications ORDER BY notify_time DESC")
    rows = c.fetchall()
    conn.close()

    data = []
    for r in rows:
        data.append({
            "id": r[0],
            "flight_id": r[1],
            "time": r[3],
            "price": "N/A",
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
def add_flight():
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
        INSERT INTO tracked_flights (from_airport, to_airport, flight_number, airline, depart_time, arrival_time, price)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        data["from"],
        data["to"],
        data["flight_number"],
        data["airline"],
        data["depart_time"],
        data["arrival_time"],
        data["price"]
    ))
    conn.commit()
    conn.close()

    return jsonify({"message": f"已成功加入追蹤航班 {data['flight_number']}"}), 200

# === 查詢目前追蹤中的航班 ===
@app.route("/flights", methods=["GET"])
def get_tracked_flights():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM tracked_flights")
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

@app.route("/prices/<int:flight_id>", methods=["GET"])
def get_price_history(flight_id):
    conn = sqlite3.connect("flights.db")
    c = conn.cursor()
    c.execute("SELECT checked_time, price FROM prices WHERE flight_id = ? ORDER BY checked_time ASC", (flight_id,))
    rows = c.fetchall()
    conn.close()

    if not rows:
        return jsonify({"message": "尚無此航班的歷史票價資料"}), 404

    data = [{"time": r[0], "price": r[1]} for r in rows]
    return jsonify(data)

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

# === 刪除追蹤中的航班 ===
@app.route("/flights/<int:flight_id>", methods=["DELETE"])
def delete_flight(flight_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM tracked_flights WHERE id = ?", (flight_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": f"已刪除追蹤航班 ID {flight_id}"}), 200


# === 排程任務：定期檢查所有追蹤航班 ===
def scheduled_price_check():
    print("🔄 開始自動檢查票價...")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, from_airport, to_airport, flight_number, depart_time, arrival_time, price FROM tracked_flights")
    flights = c.fetchall()

    for f in flights:
        flight_id, from_a, to_a, flight_no, depart, arrive, old_price = f
        new_price = fetch_latest_price(from_a, to_a, depart, arrive, flight_no)
        if new_price is None:
            print(f"⚠️ {flight_no} 票價更新失敗")
            continue

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO prices (flight_id, checked_time, price) VALUES (?, ?, ?)",
                  (flight_id, now, new_price))
        conn.commit()

        # 查詢歷史最低價
        c.execute("SELECT MIN(price) FROM prices WHERE flight_id = ?", (flight_id,))
        min_price = c.fetchone()[0]
        if new_price < min_price:
            message = f"{flight_no} 出現新低價：{new_price} TWD !!!!"
            print("💰 " + message)

            # 儲存通知紀錄
            c.execute("""
                INSERT INTO notifications (flight_id, time, price, message)
                VALUES (?, ?, ?, ?)
            """, (flight_id, now, new_price, message))
            conn.commit()

            # 推播至前端 PyQt
            socketio.emit("price_alert", {
                "flight_number": flight_no,
                "price": new_price
            })
        elif new_price == min_price:
            print(f"💰 {flight_no} 出現歷史低價：{new_price} TWD")
        else:
            print(f"✈️ {flight_no} 目前票價：{new_price} TWD")
    # 記錄此次排程
    c.execute("""
        INSERT INTO scheduler_logs (time, status)
        VALUES (?, ?)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "OK"))
    conn.commit()
            
    conn.close()
    print("✅ 自動票價更新完成")
    

# === 啟動 APScheduler ===
scheduler = BackgroundScheduler()
#設定更新時間
scheduler.add_job(scheduled_price_check, "interval", minutes= 30)
scheduler.start()

# === 主程式啟動 ===
if __name__ == "__main__":
    init_db()
    init_scheduler_log_table()
    init_notification_table()
    init_price_table()

    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        scheduler = BackgroundScheduler()
        scheduler.add_job(scheduled_price_check, "interval", minutes=30)
        scheduler.start()
        print("🕒 APScheduler 已啟動")

    socketio.run(app, debug=True)