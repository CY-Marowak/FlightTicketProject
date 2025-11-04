# TEMP
目前程式的問題在於他把要找的整個時段裡面的每個Flights都加入追蹤 <br>
但我希望是找一個時間段後 <br>
讓使用者選擇要加入哪一台Flight來追蹤 <br>


# Overview
## 已完成
1. 後端資料提取 (Python+flask)
2. 資料庫整合 (SQLAlchemy)

## 待完成
🧩 阶段性開發策略
階段 1 — Windows 電腦版本（開發測試用）

目標：
✅ 能直接在 Windows 上執行
✅ 有圖形介面（可輸入航線/日期、查看結果）
✅ 能彈出通知（或系統提示框）

💡 建議技術：

Python + Flask (API) → 你已經完成 ✅

Python GUI 前端：

Option A：PyQt5 / PySide6（完整視窗應用，最推薦）

Option B：Tkinter（簡單但外觀老舊）

Option C：Electron + React 前端（需要 Node.js，比較重）

📦 通知功能：

可用 plyer.notification 或 win10toast 彈出 Windows 系統通知。

之後可整合背景排程（用 schedule 或 APScheduler）自動查票價。

📊 優點：

直接在同一台機器上開發、除錯 API。

GUI 方便你測試 API 參數與資料庫變化。

可順便打包成 .exe（用 PyInstaller）。

📘 結論：
👉 第一階段推薦用 Flask + PyQt5 + SQLite，通知用 win10toast。
這樣你在電腦上就能完整模擬最終功能。

階段 2 — Android / iOS 手機 App（用戶版本）

目標：
✅ 在背景自動查價
✅ 可推播票價變動通知
✅ 可在 Play Store / App Store 發佈

💡 建議技術：

後端：繼續使用你現在的 Flask API（部署到雲端）

行動前端：

React Native (Expo) 👉 跨平台 Android + iOS

或 Flutter 👉 跨平台 UI 表現更一致（但要換語言）

📱 通知功能：

使用 Firebase Cloud Messaging (FCM) 或 Expo Notifications

App 定期呼叫你的 /price API，若票價下降 → 發通知

📊 優點：

真正原生 App 體驗

可利用後端資料庫儲存使用者航線追蹤清單

可做到背景更新 + 推播通知

📘 結論：
👉 第二階段用 React Native (Expo)。
直接連到你的 Flask API，不需改後端邏輯。

# 階段1 進度

🎯 你的目前進度

✅ Flask 後端：已能查詢航班並回傳票價
✅ PyQt5 前端：能查詢航班、顯示結果、顯示通知
❌ 尚未完成的部分：

「我的航班」資料儲存與管理

價格波動紀錄（折線圖）

自動排程（每 30 分鐘查詢一次）

價格通知邏輯（比較歷史最低價）

通知紀錄頁面

🚀 接下來的開發順序建議

我建議照這個步驟來做（這樣風險低、debug 也簡單）：

第 1 步：建立資料庫（SQLite）

👉 儲存：

使用者追蹤的航班

每次查詢的價格紀錄

通知紀錄

📘 建議資料表：

資料表	欄位	說明
flights	id, from_code, to_code, depart_date, return_date	使用者追蹤中的航班
prices	id, flight_id, checked_time, price	每次查詢結果（折線圖用）
notifications	id, flight_id, message, notify_time	通知紀錄

📍 這步完成後，就能開始「加入/刪除我的航班」。

第 2 步：在 PyQt5 加上 “我的航班” 頁面

可以查看目前追蹤的航班清單

按下刪除按鈕可移除

每次查詢完成可按「加入我的航班」

第 3 步：自動排程功能

讓後端每 30 分鐘自動執行一次：

### 用 APScheduler
from apscheduler.schedulers.background import BackgroundScheduler


查詢所有追蹤航班 → 更新價格 → 寫入資料庫

第 4 步：最低價通知邏輯

每次查詢到的票價 < 歷史最低價 → 建立一筆通知紀錄

PyQt5 前端定期（例如每 1 分鐘）檢查通知紀錄表 → 顯示通知氣泡

第 5 步：顯示折線圖（價格波動圖）

利用 matplotlib 或 pyqtgraph：

選擇一個航班

顯示它的價格變化趨勢

第 6 步：通知紀錄頁面

顯示：
| 時間 | 航班 | 價格 | 通知內容 |

