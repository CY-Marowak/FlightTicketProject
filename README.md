# 已完成
1. 後端資料提取 (Python+flask)
2. 資料庫整合 (SQLAlchemy)

# 待完成
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