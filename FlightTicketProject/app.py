from flask import Flask, request, jsonify
import requests
import sqlite3
from datetime import datetime


app = Flask(__name__)
app.json.ensure_ascii = False #解決中文被轉成uni的問題


# ===== RapidAPI 設定 =====
RAPIDAPI_HOST = "google-flights2.p.rapidapi.com"
RAPIDAPI_KEY = "c2e285b6f4msh6a1da4d7047fb58p1f5b65jsn96fa996ffe3c"

# ===== 建立 / 連接資料庫 =====
DB_NAME = "flights.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 使用者追蹤的航班
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS flights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_code TEXT NOT NULL,
            to_code TEXT NOT NULL,
            depart_date TEXT NOT NULL,
            return_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 價格紀錄（之後折線圖會用到）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flight_id INTEGER,
            checked_time TEXT,
            price INTEGER,
            FOREIGN KEY(flight_id) REFERENCES flights(id)
        )
    """)

    # 通知紀錄（之後通知頁會用）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flight_id INTEGER,
            message TEXT,
            notify_time TEXT,
            FOREIGN KEY(flight_id) REFERENCES flights(id)
        )
    """)

    conn.commit()
    conn.close()

# ===== 查詢航班票價 =====
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
        flights = []
        for f in top_flights:
            if f["price"] == "unavailable":# 取全部來看 跳過unavailable 
                continue
            flights.append({
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
        })

# ===== 我的航班管理 =====

@app.route("/flights", methods=["POST"])
def add_flight():
    data = request.get_json()
    from_code = data.get("from")
    to_code = data.get("to")
    depart = data.get("depart")
    ret = data.get("return")

    if not (from_code and to_code and depart):
        return jsonify({"error": "缺少必要欄位"}), 400

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO flights (from_code, to_code, depart_date, return_date) VALUES (?, ?, ?, ?)",
                   (from_code, to_code, depart, ret))
    conn.commit()
    conn.close()

    return jsonify({"message": "成功加入追蹤航班"})


@app.route("/flights", methods=["GET"])
def get_all_flights():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, from_code, to_code, depart_date, return_date, created_at FROM flights")
    rows = cursor.fetchall()
    conn.close()

    flights = [
        {
            "id": r[0],
            "from": r[1],
            "to": r[2],
            "depart": r[3],
            "return": r[4],
            "created_at": r[5]
        } for r in rows
    ]

    return jsonify(flights)


@app.route("/flights/<int:flight_id>", methods=["DELETE"])
def delete_flight(flight_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM flights WHERE id = ?", (flight_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "已刪除航班"})


# ===== 主程式 =====
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
