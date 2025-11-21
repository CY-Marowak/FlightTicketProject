import sys
import requests
import socketio
from plyer import notification
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QMessageBox,
    QHeaderView, QTabWidget, QHBoxLayout
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from matplotlib import pyplot as plt

ICON_PATH = "plane.png"

class FlightApp(QWidget):
    def __init__(self):
        super().__init__()

        self.token = None
        self.user_id = None
        self.sio = None

        self.setWindowTitle("航班查詢與追蹤系統")
        self.setGeometry(200, 200, 900, 600)
        self.setWindowIcon(QIcon(ICON_PATH))

        # --- 主容器：登入 or APP Tabs ---
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # 啟動登入畫面
        self.init_login_ui()

    # -------------------------------------------------
    # Login UI
    # -------------------------------------------------
    def init_login_ui(self):
        """顯示登入頁面"""
        self.clear_layout(self.layout)

        layout = QVBoxLayout()

        layout.addWidget(QLabel("<h2>登入 Flight Tracker</h2>"))

        layout.addWidget(QLabel("帳號："))
        self.login_user = QLineEdit()
        layout.addWidget(self.login_user)

        layout.addWidget(QLabel("密碼："))
        self.login_pass = QLineEdit()
        self.login_pass.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.login_pass)

        login_btn = QPushButton("登入")
        login_btn.clicked.connect(self.attempt_login)
        layout.addWidget(login_btn)

        register_btn = QPushButton("註冊")
        register_btn.clicked.connect(self.attempt_register)
        layout.addWidget(register_btn)

        self.layout.addLayout(layout)

    # -------------------------------------------------
    # Sign out UI
    # -------------------------------------------------
    def init_settings_tab(self):
        layout = QVBoxLayout()

        logout_btn = QPushButton("登出")
        logout_btn.setStyleSheet("background-color: #d9534f; color: white; font-weight: bold;")
        logout_btn.clicked.connect(self.logout)

        layout.addWidget(logout_btn)
        layout.addStretch()

        self.settings_tab.setLayout(layout)


    # -------------------------------------------------
    # Attempt Login
    # -------------------------------------------------
    def attempt_login(self):
        username = self.login_user.text().strip()
        password = self.login_pass.text().strip()

        if not username or not password:
            QMessageBox.warning(self, "錯誤", "請輸入帳號與密碼")
            return

        try:
            res = requests.post(
                "http://127.0.0.1:5000/login",
                json={"username": username, "password": password}
            )
            data = res.json()

            if res.status_code != 200:
                QMessageBox.warning(self, "登入失敗", data.get("error", "Unknown"))
                return

            # 成功
            self.token = data["token"]
            self.user_id = data["user_id"]

            QMessageBox.information(self, "成功", "登入成功！")

            # 啟動主頁 UI
            self.init_main_tabs()

            # 啟動 SocketIO
            self.init_socket()

        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"登入失敗：{e}")

    # -------------------------------------------------
    # Attempt Register
    # -------------------------------------------------
    def attempt_register(self):
        username = self.login_user.text().strip()
        password = self.login_pass.text().strip()

        if not username or not password:
            QMessageBox.warning(self, "錯誤", "請輸入帳號與密碼")
            return

        try:
            res = requests.post(
                "http://127.0.0.1:5000/register",
                json={"username": username, "password": password}
            )
            data = res.json()

            if res.status_code != 200:
                QMessageBox.warning(self, "註冊失敗", data.get("error", "Unknown error"))
                return

            QMessageBox.information(self, "成功", "註冊成功，請重新登入")

        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"註冊失敗：{e}")

    # -------------------------------------------------
    # Attempt Logout
    # -------------------------------------------------
    def logout(self):
        confirm = QMessageBox.question(
            self,
            "登出確認",
            "確定要登出嗎？",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        # 關閉 socketio
        try:
            if self.sio:
                self.sio.disconnect()
                self.sio = None
        except Exception as e:
            print("⚠️ SocketIO disconnect error:", e)

        # 清空 token / user_id
        self.token = None
        self.user_id = None

        # 清空 Tabs
        self.clear_layout(self.layout)

        # 返回登入畫面
        self.init_login_ui()

        QMessageBox.information(self, "成功", "您已成功登出")


    # -------------------------------------------------
    # 初始化主頁 Tabs
    # -------------------------------------------------
    def init_main_tabs(self):
        """登入後顯示主頁 Tabs"""
        self.clear_layout(self.layout)

        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # === 分頁1：查詢航班 ===
        self.query_tab = QWidget()
        self.tabs.addTab(self.query_tab, "查詢航班")
        self.init_query_tab()

        # === 分頁2：我的航班 ===
        self.tracked_tab = QWidget()
        self.tabs.addTab(self.tracked_tab, "我的航班")
        self.init_tracked_tab()

        # === 分頁3：通知紀錄 ===
        self.notify_tab = QWidget()
        self.tabs.addTab(self.notify_tab, "通知紀錄")
        self.init_notify_tab()

        # === 分頁4：排程日誌 ===
        self.log_tab = QWidget()
        self.tabs.addTab(self.log_tab, "排程日誌")
        self.init_log_tab()

        # === 分頁5：設定 ===
        self.settings_tab = QWidget()
        self.tabs.addTab(self.settings_tab, "設定")
        self.init_settings_tab()


    # ---------------------------------------------------------
    # SocketIO：登入後依 user_id 訂閱 price_alert_user_xxx
    # ---------------------------------------------------------
    def init_socket(self):
        self.sio = socketio.Client()
        event_name = f"price_alert_user_{self.user_id}"

        @self.sio.on(event_name)
        def on_price_alert(data):
            flight = data["flight_number"]
            price = data["price"]

            notification.notify(
                title="票價新低通知",
                message=f"{flight} 出現新低價：{price} TWD",
                timeout=5
            )

            QMessageBox.information(
                self,
                "票價新低通知",
                f"{flight} 出現新低價：{price} TWD"
            )

        try:
            self.sio.connect("http://127.0.0.1:5000")
            print(f"🔌 已連線 SocketIO，監聽：{event_name}")
        except Exception as e:
            print("❌ SocketIO 連線錯誤：", e)

    # -------------------------------------------------
    # 1. 查詢航班
    # -------------------------------------------------
    def init_query_tab(self):
        layout = QVBoxLayout()

        layout.addWidget(QLabel("出發機場代碼："))
        self.from_input = QLineEdit("TPE")
        layout.addWidget(self.from_input)

        layout.addWidget(QLabel("抵達機場代碼："))
        self.to_input = QLineEdit("OKA")
        layout.addWidget(self.to_input)

        layout.addWidget(QLabel("出發日期："))
        self.depart_input = QLineEdit("2026-03-12")
        layout.addWidget(self.depart_input)

        layout.addWidget(QLabel("回程日期："))
        self.return_input = QLineEdit("2026-03-15")
        layout.addWidget(self.return_input)

        btn = QPushButton("查詢航班")
        btn.clicked.connect(self.search_flights)
        layout.addWidget(btn)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["航空公司", "航班編號", "出發時間", "抵達時間", "票價", "操作"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        layout.addWidget(self.table)
        self.query_tab.setLayout(layout)

    def search_flights(self):
        from_airport = self.from_input.text().strip()
        to_airport = self.to_input.text().strip()
        depart_date = self.depart_input.text().strip()
        return_date = self.return_input.text().strip()

        url = f"http://127.0.0.1:5000/price?from={from_airport}&to={to_airport}&depart={depart_date}&return={return_date}"

        try:
            response = requests.get(url, headers=self.auth())
            data = response.json()

            if "flights" not in data:
                QMessageBox.warning(self, "錯誤", data.get("error", "查詢失敗"))
                return

            self.display_flights(data["flights"])

        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"查詢失敗: {e}")

    def display_flights(self, flights):
        self.table.setRowCount(len(flights))

        for i, f in enumerate(flights):
            self.table.setItem(i, 0, QTableWidgetItem(f["airline"]))
            self.table.setItem(i, 1, QTableWidgetItem(f["flight_number"]))
            self.table.setItem(i, 2, QTableWidgetItem(f["depart_time"]))
            self.table.setItem(i, 3, QTableWidgetItem(f["arrival_time"]))
            self.table.setItem(i, 4, QTableWidgetItem(str(f["price"])))

            btn = QPushButton("加入追蹤")
            btn.clicked.connect(lambda _, ff=f: self.add_to_tracking(ff))
            self.table.setCellWidget(i, 5, btn)

    # -------------------------------------------------
    # 2. 加入追蹤
    # -------------------------------------------------
    def add_to_tracking(self, f):
        try:
            res = requests.post(
                "http://127.0.0.1:5000/flights",
                json=f,
                headers=self.auth()
            )
            data = res.json()
            if res.status_code == 200:
                QMessageBox.information(self, "成功", data["message"])
            else:
                QMessageBox.warning(self, "錯誤", data.get("error"))
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"加入失敗：{e}")

    # -------------------------------------------------
    # 3. 我的航班
    # -------------------------------------------------
    def init_tracked_tab(self):
        layout = QVBoxLayout()

        refresh_btn = QPushButton("重新整理")
        refresh_btn.clicked.connect(self.load_tracked_flights)
        layout.addWidget(refresh_btn)

        self.tracked_table = QTableWidget()
        self.tracked_table.setColumnCount(7)
        self.tracked_table.setHorizontalHeaderLabels(
            ["航空公司", "航班編號", "出發時間", "抵達時間", "價格", "出發地", "操作"]
        )
        self.tracked_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tracked_table)

        self.tracked_tab.setLayout(layout)

    def load_tracked_flights(self):
        try:
            res = requests.get("http://127.0.0.1:5000/flights", headers=self.auth())
            data = res.json()

            self.tracked_table.setRowCount(len(data))

            for i, f in enumerate(data):
                self.tracked_table.setItem(i, 0, QTableWidgetItem(f["airline"]))
                self.tracked_table.setItem(i, 1, QTableWidgetItem(f["flight_number"]))
                self.tracked_table.setItem(i, 2, QTableWidgetItem(f["depart_time"]))
                self.tracked_table.setItem(i, 3, QTableWidgetItem(f["arrival_time"]))
                self.tracked_table.setItem(i, 4, QTableWidgetItem(str(f["price"])))
                self.tracked_table.setItem(i, 5, QTableWidgetItem(f["from"]))

                # 操作按鈕
                hl = QHBoxLayout()
                hl.setAlignment(Qt.AlignCenter)

                btn_del = QPushButton("刪除")
                btn_del.clicked.connect(lambda _, fid=f["id"]: self.delete_flight(fid))
                hl.addWidget(btn_del)

                btn_chart = QPushButton("折線圖")
                btn_chart.clicked.connect(
                    lambda _, fid=f["id"], fn=f["flight_number"]: self.show_price_chart(fid, fn)
                )
                hl.addWidget(btn_chart)

                cell = QWidget()
                cell.setLayout(hl)
                self.tracked_table.setCellWidget(i, 6, cell)

        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"載入追蹤航班失敗：{e}")

    # -------------------------------------------------
    # 4. 刪除追蹤航班
    # -------------------------------------------------
    def delete_flight(self, flight_id):
        try:
            res = requests.delete(
                f"http://127.0.0.1:5000/flights/{flight_id}",
                headers=self.auth()
            )
            data = res.json()
            if res.status_code == 200:
                QMessageBox.information(self, "成功", data["message"])
                self.load_tracked_flights()
            else:
                QMessageBox.warning(self, "錯誤", data.get("error"))
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"刪除失敗：{e}")

    # -------------------------------------------------
    # 5. 顯示折線圖
    # -------------------------------------------------
    def show_price_chart(self, flight_id, flight_number):
        try:
            res = requests.get(
                f"http://127.0.0.1:5000/prices/{flight_id}",
                headers=self.auth()
            )
            if res.status_code != 200:
                QMessageBox.warning(self, "提示", "此航班尚無紀錄")
                return

            data = res.json()
            times = [x["time"] for x in data]
            prices = [x["price"] for x in data]

            plt.figure(figsize=(7, 4))
            plt.plot(times, prices, marker="o", linewidth=2)
            plt.title(f"{flight_number} 票價變化圖")
            plt.xlabel("時間")
            plt.ylabel("票價")
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.grid(True)
            plt.show()

        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"無法顯示折線圖：{e}")

    # -------------------------------------------------
    # 6. 載入通知紀錄
    # -------------------------------------------------
    def init_notify_tab(self):
        layout = QVBoxLayout()

        btn = QPushButton("重新整理通知紀錄")
        btn.clicked.connect(self.load_notifications)
        layout.addWidget(btn)

        self.notify_table = QTableWidget()
        self.notify_table.setColumnCount(4)
        self.notify_table.setHorizontalHeaderLabels(
            ["時間", "航班ID", "價格", "訊息"]
        )
        self.notify_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.notify_table)

        self.notify_tab.setLayout(layout)

    def load_notifications(self):
        try:
            res = requests.get("http://127.0.0.1:5000/notifications", headers=self.auth())
            data = res.json()

            self.notify_table.setRowCount(len(data))

            for i, n in enumerate(data):
                self.notify_table.setItem(i, 0, QTableWidgetItem(n["time"]))
                self.notify_table.setItem(i, 1, QTableWidgetItem(str(n["flight_id"])))
                self.notify_table.setItem(i, 2, QTableWidgetItem(str(n["price"])))
                self.notify_table.setItem(i, 3, QTableWidgetItem(n["message"]))

        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"通知載入失敗：{e}")

    # -------------------------------------------------
    # 7. 排程日誌
    # -------------------------------------------------
    def init_log_tab(self):
        layout = QVBoxLayout()

        btn = QPushButton("重新整理排程日誌")
        btn.clicked.connect(self.load_logs)
        layout.addWidget(btn)

        self.log_table = QTableWidget()
        self.log_table.setColumnCount(2)
        self.log_table.setHorizontalHeaderLabels(["時間", "狀態"])
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.log_table)

        self.log_tab.setLayout(layout)

    def load_logs(self):
        try:
            res = requests.get("http://127.0.0.1:5000/check_logs", headers=self.auth())
            data = res.json()

            self.log_table.setRowCount(len(data))

            for i, log in enumerate(data):
                self.log_table.setItem(i, 0, QTableWidgetItem(log["time"]))
                self.log_table.setItem(i, 1, QTableWidgetItem(log["status"]))

        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"日誌載入失敗：{e}")

    # -------------------------------------------------
    # Utils
    # -------------------------------------------------
    def auth(self):
        """回傳含 JWT 的 header"""
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    def clear_layout(self, layout):
        """清掉所有 widget"""
        while layout.count():
            w = layout.takeAt(0).widget()
            if w:
                w.deleteLater()


# -------------------------------------------------
# Main
# -------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FlightApp()
    window.show()
    sys.exit(app.exec_())
