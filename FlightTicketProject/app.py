from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import requests
import atexit

app = Flask(__name__)

RAPIDAPI_HOST = "google-flights2.p.rapidapi.com"
RAPIDAPI_KEY = "c2e285b6f4msh6a1da4d7047fb58p1f5b65jsn96fa996ffe3c"

# 上次航班
lsat_flight = None
# 用來暫存上次查到的最低價
last_price = None  

def check_flight_price():
    """定期執行的任務：查詢航班票價並檢查是否有變化"""
    global last_price

    url = f"https://{RAPIDAPI_HOST}/api/v1/searchFlights"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }
    query = {
        "departure_id": "TPE",
        "arrival_id": "OKA",
        "outbound_date": "2026-03-12",
        "return_date": "2026-03-15",
        "adults": "1",
        "currency": "TWD"
    }

    try:
        response = requests.get(url, headers=headers, params=query)
        if response.status_code != 200:
            print(f"❌ API 錯誤 ({response.status_code}): {response.text}")
            return

        data = response.json()
        flights = data.get("data", {}).get("itineraries", {}).get("topFlights", [])

        flight = []
        for f in flights:
            if(f["price"] == "unavailable"):
                continue
            flight.append({ 
                "price": float(f["price"]) ,
                "airline": f["flights"][0]["airline"]
            })
        
        if not flight:
            print("⚠️ 沒有找到可用票價")
            return

        cheapest = min(flight, key=lambda x: x["price"])
        
        if last_price is None:
            last_price = cheapest['price']
            last_flight = cheapest['airline']
            print(f"航班號碼：{last_flight} ") #初次航班
            print(f"📡 初次查詢票價：{last_price} TWD")
        elif cheapest['price'] != last_price:
            print(f"航班號碼：{cheapest['airline']} ")
            print(f"💰 票價變動！之前 {last_price} → 現在 {cheapest['price']} TWD")
            last_price = cheapest['price']
        else:
            print(f"✅ 票價無變化：{cheapest['price']} TWD")

    except Exception as e:
        print(f"⚠️ 排程任務發生錯誤: {e}")

# 啟動 Flask 時同步啟動背景排程
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_flight_price, trigger="interval", seconds=10) #多久呼叫一次
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

#找出當日所有航班 印出前5便宜的航班
#此功能之後可以給使用者選擇要追蹤的航班
@app.route("/price", methods=["GET"])
def get_price():
    """即時查票價（與你原本的一樣）"""
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
    top_flights = data.get("data", {}).get("itineraries", {}).get("topFlights", [])

    flights = [] 
    for f in top_flights: # 取全部來看 跳過unavailable 
        if f["price"] == "unavailable": 
            continue 
        flights.append({ 
            "airline": f["flights"][0]["airline"], 
            "flight_number": f["flights"][0]["flight_number"], 
            "depart_time": f["flights"][0]["departure_airport"]["time"], 
            "arrival_time": f["flights"][0]["arrival_airport"]["time"], 
            "price": f["price"] 
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

if __name__ == "__main__":
    print("🚀 Flask 啟動中，背景排程已開始執行...")
    app.run(debug=True)
