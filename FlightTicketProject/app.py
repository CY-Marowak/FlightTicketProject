from flask import Flask, request, jsonify
import requests
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.json.ensure_ascii = False #解決中文被轉成uni的問題


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

# === 刪除追蹤中的航班 ===
@app.route("/flights/<int:flight_id>", methods=["DELETE"])
def delete_flight(flight_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM tracked_flights WHERE id = ?", (flight_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": f"已刪除追蹤航班 ID {flight_id}"}), 200

# === 主程式啟動 ===
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
