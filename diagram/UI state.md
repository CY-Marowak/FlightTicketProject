# 三端共用 UI 狀態流程圖
統一 UI 狀態邏輯，而非 UI 技術實作

UI 不是畫面切換，UI 是「狀態轉移」

---

## 一、核心 UI 狀態定義

```
[APP 啟動]
     |
     v
[CHECK_AUTH]
     |
     |-- Token 有效 --> [MAIN_VIEW]
     |
     |-- 無 Token / Token 失效 --> [LOGIN_VIEW]
```

---

## 二、完整 UI 狀態流程（標準版）

```
┌──────────────┐
│   APP START  │
└──────┬───────┘
       v
┌────────────────────┐
│  CHECK AUTH STATE  │
│ (auto_login / JWT) │
└──────┬─────────────┘
       │
       │ Token Valid
       v
┌────────────────────┐
│     MAIN_VIEW      │◄────────────┐
│  (Tabs / Dashboard)│             │
└──────┬─────────────┘             │
       │                           │
       │ Logout                    │
       v                           │
┌────────────────────┐             │
│    LOGIN_VIEW      │             │
│ (Login / Register) │             │
└──────┬─────────────┘             │
       │                           │
       │ Login Success             │
       └───────────────────────────┘
```

---

## 三、各狀態「責任邊界」定義

### 1️⃣ CHECK_AUTH（啟動判斷）

**責任**

* 檢查 Token 是否存在
* 呼叫 `/profile` 驗證 Token


---

### 2️⃣ LOGIN_VIEW

**顯示內容**

* 帳號
* 密碼
* 登入 / 註冊

---

### 3️⃣ MAIN_VIEW

**顯示內容**

* 查詢航班
* 我的航班
* 通知紀錄
* 個人資料 (更改密碼和登出)

**進入時做**

* 初始化 Tabs
* 初始化 SocketIO
* 初始化 User_token (Mobile)

**離開時做**

* 中斷 SocketIO
* 清除 session 狀態

---

## 四、三端對照表

| UI State   | 桌面版（PyQt）         | Web(React+Vite)                    | Mobile(Expo+ReactNative)             |
| ---------- | ----------------- | ---------------------- | ------------------ |
| CHECK_AUTH | auto_login()      | App.tsx  | _layout.tsx      |
| LOGIN_VIEW | show_login_view() | /Login           | (auth)         |
| MAIN_VIEW  | show_main_view()  | /Dashboard             | (tabs)          |
| LOGOUT     | logout()          | clear token + redirect | clear token + clear push_token +redirect |



