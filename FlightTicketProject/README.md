# Flight Ticket Tracker

## Code
### Backend
app.py

### Desktop Frontend
flight_gui.py

---
## Tech Stack
### Backend
1. 運行 Flask
2. 語言 Python

### Desktop Frontend
1. 運行 PyQt5
2. 語言 Python

---
## Backend API
### API
1. POST   /register
: 註冊、hash密碼加密

2. POST   /login
: 登入、加入前端push_token(用於前端及時通知提醒)

3. GET    /profile   / (JWT token)
: 取得個人資料

4. POST   /change-password  / (JWT token)
: 修改密碼

5. GET    /price
: 查詢航班(使用api-key 來自rapidapi)

6. POST   /flights / (JWT token)
: 航班加入追蹤

7. GET    /flights / (JWT token)
: 查詢使用者追蹤中的航班

8. DELETE /flights/<int:flight_id> / (JWT token)
: 刪除使用者追蹤中的航班

9. GET    /notifications  / (JWT token)
: 查詢使用者通知紀錄(根據user_id)
    
10. GET    /prices/<int:flight_id>  / (JWT token)
: 查詢航班票價歷史

### APScheduler
自動程式: scheduled_price_check <br>
自動檢查所有使用者的所有航班票價變動<br>
+刪除過期航班<br>
+提醒出現歷史最低價(socketio, user_push_token)

---
## Full System Architecture
<a href="https://viewer.diagrams.net/?target=blank&highlight=0000ff&edit=_blank&layers=1&nav=1#Uhttps://github.com/CY-Marowak/FlightTicketProject/raw/refs/heads/master/diagram/App%20flow.svg">
  <img src="diagram/App%20flow.svg" alt="App flow" width="80%">
</a>
