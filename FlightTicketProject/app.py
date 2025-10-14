#寫好地點以及日期 輸出前5 跳過"unavailable"
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

RAPIDAPI_HOST = "google-flights2.p.rapidapi.com"
RAPIDAPI_KEY = "c2e285b6f4msh6a1da4d7047fb58p1f5b65jsn96fa996ffe3c"

@app.route("/price", methods=["GET"])
def get_price():
    departure_id = request.args.get("from", "TPE")
    arrival_id = request.args.get("to", "OKA")
    outbound_date = request.args.get("depart", "2026-03-12")
    return_date = request.args.get("return", "2026-03-15")

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

        if not top_flights:  # 沒有航班
            return jsonify({
                "from": departure_id,
                "to": arrival_id,
                "outbound_date": outbound_date,
                "return_date": return_date,
                "message": "查無符合的航班資料，請確認日期或機場代碼是否正確"
            })

        flights = []
        for f in top_flights:  # 取全部來看 跳過unavailable
            if f["price"] == "unavailable":
                continue
            flights.append({
                "airline": f["flights"][0]["airline"],
                "flight_number": f["flights"][0]["flight_number"],
                "depart_time": f["flights"][0]["departure_airport"]["time"],
                "arrival_time": f["flights"][0]["arrival_airport"]["time"],
                "price": f["price"]
            })

        # 按票價排序，取前5便宜的航班
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

if __name__ == "__main__":
    app.run(debug=True)
