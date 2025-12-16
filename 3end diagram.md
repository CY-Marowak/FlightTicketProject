# 三端共用 UI 狀態流程圖

> 適用對象：**桌面版（PyQt） / 網頁版（Web） / 手機 App（Mobile）**
> 核心目的：**統一 UI 狀態邏輯，而非 UI 技術實作**

---

## 一、核心 UI 狀態定義（跨三端共用）

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

這一層是**所有版本都一致的 UI State Machine**。

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

## 三、各狀態「責任邊界」定義（非常重要）

### 1️⃣ CHECK_AUTH（啟動判斷）

**責任**

* 檢查 Token 是否存在
* 呼叫 `/profile` 驗證 Token

**不可做**

* 不建立 UI
* 不顯示錯誤對話框

---

### 2️⃣ LOGIN_VIEW

**顯示內容**

* 帳號
* 密碼
* 登入 / 註冊

**成功事件**

```
LOGIN_SUCCESS
  ↓
show_main_view()
```

**失敗事件**

* 顯示錯誤訊息
* 停留在 LOGIN_VIEW

---

### 3️⃣ MAIN_VIEW

**顯示內容（你目前已有）**

* 查詢航班
* 我的航班
* 通知紀錄
* 排程日誌
* 個人資料
* 設定（登出）

**進入時必做**

* 初始化 Tabs
* 初始化 SocketIO

**離開時必做**

* 中斷 SocketIO
* 清除 session 狀態

---

## 四、三端對照表

| UI State   | 桌面版（PyQt）         | Web                    | Mobile             |
| ---------- | ----------------- | ---------------------- | ------------------ |
| CHECK_AUTH | auto_login()      | App Init / Middleware  | Splash Screen      |
| LOGIN_VIEW | show_login_view() | /login route           | Login Page         |
| MAIN_VIEW  | show_main_view()  | /dashboard             | Home Tabs          |
| LOGOUT     | logout()          | clear token + redirect | clear token + push |

👉 **邏輯 100% 相同，只差技術實作**

---

## 五、你目前程式對應位置（實際落點）

```
__init__()
  └─ show_login_view()
       └─ auto_login()
            ├─ success → show_main_view()
            └─ fail    → 留在 login

attempt_login()
  └─ success → show_main_view()

logout()
  └─ show_login_view()
```

---

## 六、進階擴充（你之後一定會加）

### 🔹 LOADING_VIEW

```
LOGIN_VIEW
   ↓
LOADING_VIEW
   ↓
MAIN_VIEW
```

### 🔹 ERROR_VIEW

```
ANY_STATE
   ↓ (API error)
ERROR_VIEW
```

這些都**不需要改現有流程**，只新增 state。

---

## 七、一句話總結（架構層）

> UI 不是畫面切換，
> UI 是「狀態轉移」。

你現在的專案已經具備：

* 後端 API 分層
* JWT 狀態管理
* UI State Machine 雛型

這是**可以長期演進成正式產品的架構**。

