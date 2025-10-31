from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import requests

app = Flask(__name__)

# ====== RapidAPI 設定 ======
RAPIDAPI_HOST = "google-flights2.p.rapidapi.com"
RAPIDAPI_KEY = "c2e285b6f4msh6a1da4d7047fb58p1f5b65jsn96fa996ffe3c"

# ====== SQLite 設定 ======
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///flights.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


# ====== 資料表定義 ======
class Flight(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_airport = db.Column(db.String(10))
    to_airport = db.Column(db.String(10))
    outbound_date = db.Column(db.String(20))
    return_date = db.Column(db.String(20))
    airline = db.Column(db.String(100))
    flight_number = db.Column(db.String(20))
    depart_time = db.Column(db.String(50))
    arrival_time = db.Column(db.String(50))
    price = db.Column(db.Float)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)


# ====== 初始化資料庫 ======
with app.app_context():
    db.create_all()


# ====== API: 查詢航班票價 ======
@app.route("/price", methods=["GET"])
def get_price():
    departure_id = request. args.get("from")
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
            flight_info = {
                "airline": f["flights"][0]["airline"],
                "flight_number": f["flights"][0]["flight_number"],
                "depart_time": f["flights"][0]["departure_airport"]["time"],
                "arrival_time": f["flights"][0]["arrival_airport"]["time"],
                "price": float(f["price"])
            }
            flights.append(flight_info)

            # --- 儲存進資料庫 ---
            existing = Flight.query.filter_by(
                from_airport=departure_id,
                to_airport=arrival_id,
                outbound_date=outbound_date,
                return_date=return_date,
                flight_number=flight_info["flight_number"]
            ).first()

            if existing:
                existing.price = flight_info["price"]
                existing.last_updated = datetime.utcnow()
            else:
                new_flight = Flight(
                    from_airport=departure_id,
                    to_airport=arrival_id,
                    outbound_date=outbound_date,
                    return_date=return_date,
                    airline=flight_info["airline"],
                    flight_number=flight_info["flight_number"],
                    depart_time=flight_info["depart_time"],
                    arrival_time=flight_info["arrival_time"],
                    price=flight_info["price"]
                )
                db.session.add(new_flight)

        db.session.commit()

        # --- 取前 5 便宜的航班 ---
        flights.sort(key=lambda x: x["price"])
        cheapest_flights = flights[:5]

        return jsonify({
            "from": departure_id,
            "to": arrival_id,
            "outbound_date": outbound_date,
            "return_date": return_date,
            "flights": cheapest_flights,
            "count_saved": len(cheapest_flights)
        })
    except Exception as e:
        return jsonify({
            "error": "無法解析航班資料",
            "details": str(e),
            "raw": data
        })


# ====== 查詢資料庫歷史記錄 ======
@app.route("/history", methods=["GET"])
def get_history():
    flights = Flight.query.order_by(Flight.last_updated.desc()).limit(20).all()
    result = []
    for f in flights:
        result.append({
            "from": f.from_airport,
            "to": f.to_airport,
            "airline": f.airline,
            "flight_number": f.flight_number,
            "depart_time": f.depart_time,
            "arrival_time": f.arrival_time,
            "price": f.price,
            "updated": f.last_updated.strftime("%Y-%m-%d %H:%M:%S")
        })
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)
