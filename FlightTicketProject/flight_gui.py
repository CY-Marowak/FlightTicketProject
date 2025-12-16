import sys
import requests
from requests import api
import socketio
from plyer import notification
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView, QTabWidget, QHBoxLayout
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from matplotlib import pyplot as plt

ICON_PATH = "plane.png"
API_URL = "https://flightticketproject.onrender.com"

class FlightApp(QWidget):
    def __init__(self):
        super().__init__()

        self.token = None
        self.user_id = None
        self.sio = None

        self.setWindowTitle("航班查詢與追蹤系統")
        self.setGeometry(200, 200, 900, 600)
        self.setWindowIcon(QIcon(ICON_PATH))  # 可自行替換 icon

        # --- 主分頁 ---
        self.tabs = QTabWidget()
        self.main_layout = QVBoxLayout()
        self.main_layout.addWidget(self.tabs)
        self.setLayout(self.main_layout)

        # 啟動登入畫面
        self.show_login_view()


        # 如果 token 存在 → 自動登入
        try:
            with open("token.txt", "r") as f:
                self.token = f.read().strip()
                self.auto_login()
        except:
            pass

    # =========================
    # View Switcher
    # =========================

    def show_login_view(self):
        """顯示登入畫面"""
        self.reset_main_view()
        self.init_login_ui()

    def show_main_view(self):
        """顯示主功能畫面（Tabs）"""
        self.reset_main_view()
        self.init_main_tabs()

    # -------------------------------------------------
    # 自動登入
    # -------------------------------------------------
    def auto_login(self):
        try:
            res = requests.get(
                f"{API_URL}/profile",
                headers={"Authorization": f"Bearer {self.token}"}
            )
            print("DEBUG /profile status:", res.status_code)
            print("DEBUG /profile text:", res.text[:300])
            
            if res.status_code == 200:
                data = res.json()
                self.user_id = data["user_id"]
                self.show_main_view()
                self.init_socket(self.user_id)
                print("🔓 自動登入成功")
            else:
                print("Token 失效，請重新登入")
        except Exception as e:
            print("自動登入失敗：", e)

    # -------------------------------------------------
    # 登入 UI
    # -------------------------------------------------
    def init_login_ui(self):
        """顯示登入頁面"""
        self.reset_main_view()

        # --- 白色主容器（外層） ---
        login_container = QWidget()
        login_layout = QVBoxLayout(login_container)
        login_layout.setContentsMargins(80, 60, 80, 60)
        login_layout.setSpacing(20)

        login_container.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 2px solid #cccccc;
                border-radius: 15px;
            }
            QLabel {
                font-size: 15px;
            }
            QLineEdit {
                height: 30px;
                border: 1px solid #aaa;
                border-radius: 5px;
                padding: 4px;
            }
            QPushButton {
                height: 34px;
                border-radius: 6px;
            }
        """)

        # 標題
        title = QLabel("<h2>登入 Flight Tracker</h2>")
        title.setAlignment(Qt.AlignCenter)
        login_layout.addWidget(title)

        # 帳號
        user_label = QLabel("帳號：")
        self.login_user = QLineEdit()
        self.login_user.setPlaceholderText("請輸入帳號")
        login_layout.addWidget(user_label)
        login_layout.addWidget(self.login_user)

        # 密碼
        pass_label = QLabel("密碼：")
        self.login_pass = QLineEdit()
        self.login_pass.setEchoMode(QLineEdit.Password)
        self.login_pass.setPlaceholderText("請輸入密碼")
        login_layout.addWidget(pass_label)
        login_layout.addWidget(self.login_pass)

        # 登入 / 註冊按鈕
        login_btn = QPushButton("登入")
        register_btn = QPushButton("註冊")
        login_btn.clicked.connect(self.attempt_login)
        register_btn.clicked.connect(self.attempt_register)
        login_layout.addWidget(login_btn)
        login_layout.addWidget(register_btn)
        
        # --- 把整個白框放入主畫面中央 ---
        outer_layout = QVBoxLayout()
        outer_layout.addStretch()
        outer_layout.addWidget(login_container, alignment=Qt.AlignCenter)
        outer_layout.addStretch()

        self.main_layout.addLayout(outer_layout)

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
                f"{API_URL}/login",
                json={"username": username, "password": password}
            )

            print("DEBUG /login status:", res.status_code)
            print("DEBUG /login text:", res.text[:300])

            # 先確認是不是 JSON
            try:
                data = res.json()
            except Exception:
                QMessageBox.critical(
                    self,
                    "錯誤",
                    f"伺服器回傳非 JSON：\n狀態碼 {res.status_code}\n內容：{res.text[:200]}"
                )
                return
            
            if res.status_code != 200:
                QMessageBox.warning(self, "登入失敗", data.get("error", "Unknown"))
                return

            # 成功
            self.token = data["token"]
            self.user_id = data["user_id"]

            # 記住我（儲存 token）
            with open("token.txt", "w") as f:
                f.write(self.token)

            QMessageBox.information(self, "成功", "登入成功！")

            # 啟動主頁 UI
            self.show_main_view()

            # 啟動 SocketIO
            self.init_socket(self.user_id)

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
                f"{API_URL}/register",
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
        # 返回登入畫面
        self.show_login_view()

        QMessageBox.information(self, "成功", "您已成功登出")


    # -------------------------------------------------
    # 初始化主頁 Tabs
    # -------------------------------------------------
    def init_main_tabs(self):
        """登入後顯示主頁 Tabs"""
        self.reset_main_view()

        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)

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
        
        # === 分頁5：個人資料 === 
        self.profile_tab = QWidget() 
        self.tabs.addTab(self.profile_tab, "個人資料") 
        self.init_profile_tab() 
        
        # === 分頁6：設定 === 
        self.settings_tab = QWidget() 
        self.tabs.addTab(self.settings_tab, "設定") 
        self.init_settings_tab()


    # -------------------------------------------------
    # SocketIO：登入後依 user_id 訂閱 price_alert_user_xxx
    # -------------------------------------------------
    def init_socket(self, user_id):
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
            self.sio.connect(API_URL, transports=["websocket"])
            print(f"🔌 已連線 SocketIO，監聽：{event_name}")
        except Exception as e:
            print("❌ SocketIO 連線錯誤：", e)

    # -------------------------------------------------
    # 查詢航班分頁
    # -------------------------------------------------
    def init_query_tab(self):
        layout = QVBoxLayout()

        layout.addWidget(QLabel("出發機場代碼 (e.g. TPE):"))
        self.from_input = QLineEdit("TPE")
        layout.addWidget(self.from_input)

        layout.addWidget(QLabel("抵達機場代碼 (e.g. OKA):"))
        self.to_input = QLineEdit("OKA")
        layout.addWidget(self.to_input)

        layout.addWidget(QLabel("出發日期 (YYYY-MM-DD):"))
        self.depart_input = QLineEdit("2026-03-12")
        layout.addWidget(self.depart_input)

        layout.addWidget(QLabel("回程日期 (YYYY-MM-DD):"))
        self.return_input = QLineEdit("2026-03-15")
        layout.addWidget(self.return_input)

        # 查詢按鈕
        self.search_btn = QPushButton("查詢航班")
        self.search_btn.clicked.connect(self.search_flights)
        layout.addWidget(self.search_btn)

        # 查詢結果表格
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["航空公司", "航班編號", "出發時間", "抵達時間", "票價 (TWD)", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        layout.addWidget(self.table)
        self.query_tab.setLayout(layout)


    # -------------------------------------------------
    # 我的航班分頁
    # -------------------------------------------------
    def init_tracked_tab(self):
        layout = QVBoxLayout()

        self.refresh_btn = QPushButton("重新整理追蹤清單")
        self.refresh_btn.clicked.connect(self.load_tracked_flights)
        layout.addWidget(self.refresh_btn)

        self.tracked_table = QTableWidget()
        self.tracked_table.setColumnCount(7)
        self.tracked_table.setHorizontalHeaderLabels([
            "航空公司", "航班編號", "出發時間", "抵達時間", "票價 (TWD)", "出發地", "操作"
        ])
        self.tracked_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        layout.addWidget(self.tracked_table)
        self.tracked_tab.setLayout(layout)


    # -------------------------------------------------
    # 通知紀錄分頁
    # -------------------------------------------------
    def init_notify_tab(self):
        layout = QVBoxLayout()
        
        refresh_btn = QPushButton("重新整理通知紀錄")
        refresh_btn.clicked.connect(self.load_notifications)
        layout.addWidget(refresh_btn)

        self.notify_table = QTableWidget()
        self.notify_table.setColumnCount(4)
        self.notify_table.setHorizontalHeaderLabels(["時間", "航班", "價格", "訊息"])
        self.notify_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        layout.addWidget(self.notify_table)
        self.notify_tab.setLayout(layout)


    # -------------------------------------------------
    # 排程日誌分頁
    # -------------------------------------------------
    def init_log_tab(self):
        layout = QVBoxLayout()

        refresh_btn = QPushButton("重新整理排程日誌")
        refresh_btn.clicked.connect(self.load_logs)
        layout.addWidget(refresh_btn)

        self.log_table = QTableWidget()
        self.log_table.setColumnCount(2)
        self.log_table.setHorizontalHeaderLabels(["時間", "狀態"])
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        layout.addWidget(self.log_table)
        self.log_tab.setLayout(layout)


    # -------------------------------------------------
    # 查詢航班（呼叫 Flask /price）
    # -------------------------------------------------
    def search_flights(self):
        from_airport = self.from_input.text().strip()
        to_airport = self.to_input.text().strip()
        depart_date = self.depart_input.text().strip()
        return_date = self.return_input.text().strip()

        url = f"{API_URL}/price?from={from_airport}&to={to_airport}&depart={depart_date}&return={return_date}"

        try:
            response = requests.get(url)
            data = response.json()

            if not data.get("flights"):
                QMessageBox.warning(self, "查詢結果", "查無航班或API連線錯誤")
                return
            
            self.display_flights(data["flights"])
        
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"查詢失敗: {e}")

    def display_flights(self, flights):
        self.table.setRowCount(len(flights))
        for i, flight in enumerate(flights):
            self.table.setItem(i, 0, QTableWidgetItem(flight["airline"]))
            self.table.setItem(i, 1, QTableWidgetItem(flight["flight_number"]))
            self.table.setItem(i, 2, QTableWidgetItem(flight["depart_time"]))
            self.table.setItem(i, 3, QTableWidgetItem(flight["arrival_time"]))
            self.table.setItem(i, 4, QTableWidgetItem(str(flight["price"])))
            
            btn = QPushButton("加入追蹤")
            btn.clicked.connect(lambda _, f=flight: self.add_to_tracking(f))
            self.table.setCellWidget(i, 5, btn)

    # -------------------------------------------------
    # 加入追蹤（POST /flights）
    # -------------------------------------------------
    def add_to_tracking(self, flight):
        url = f"{API_URL}/flights"
        try:
            response = requests.post(url, json=flight, headers=self.auth())
            data = response.json()
            if response.status_code == 200:
                QMessageBox.information(self, "成功", data.get("message", "已加入追蹤"))
            else:
                QMessageBox.warning(self, "失敗", data.get("error", "加入追蹤失敗"))
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"無法加入追蹤: {e}")

    # -------------------------------------------------
    # 載入追蹤中的航班（GET /flights）
    # -------------------------------------------------
    def load_tracked_flights(self):
        url = f"{API_URL}/flights"
        try:
            response = requests.get(url, headers=self.auth())  # ✅ 加上 headers
            data = response.json()
            
            if not isinstance(data, list):
                QMessageBox.warning(self, "錯誤", f"伺服器回傳非清單：{data}")
                return

            if not data:
                QMessageBox.information(self, "提示", "目前沒有追蹤中的航班")
                return

            self.tracked_table.setRowCount(len(data))
            
            for i, f in enumerate(data):
                self.tracked_table.setItem(i, 0, QTableWidgetItem(f["airline"]))
                self.tracked_table.setItem(i, 1, QTableWidgetItem(f["flight_number"]))
                self.tracked_table.setItem(i, 2, QTableWidgetItem(f["depart_time"]))
                self.tracked_table.setItem(i, 3, QTableWidgetItem(f["arrival_time"]))
                self.tracked_table.setItem(i, 4, QTableWidgetItem(str(f["price"])))
                self.tracked_table.setItem(i, 5, QTableWidgetItem(f["from"]))

                # 刪除按鈕
                btn_layout = QHBoxLayout()
                btn_layout.setAlignment(Qt.AlignCenter)

                del_btn = QPushButton("刪除")
                del_btn.clicked.connect(lambda _, fid=f["id"]: self.delete_flight(fid))
                btn_layout.addWidget(del_btn)

                chart_btn = QPushButton("折線圖")
                chart_btn.clicked.connect(lambda _, fid=f["id"], fn=f["flight_number"]: self.show_price_chart(fid, fn))
                btn_layout.addWidget(chart_btn)

                cell_widget = QWidget()
                cell_widget.setLayout(btn_layout)
                self.tracked_table.setCellWidget(i, 6, cell_widget)

        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"無法載入追蹤清單: {e}")


    # -------------------------------------------------
    # 刪除航班（DELETE /flights/<id>）
    # -------------------------------------------------
    def delete_flight(self, flight_id):
        url = f"{API_URL}/flights/{flight_id}"
        try:
            response = requests.delete(url, headers=self.auth())
            data = response.json()
            if response.status_code == 200:
                QMessageBox.information(self, "成功", data.get("message", "已刪除航班"))
                self.load_tracked_flights()
            else:
                QMessageBox.warning(self, "失敗", data.get("error", "刪除失敗"))
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"無法刪除航班: {e}")

    # -------------------------------------------------
    # 加上顯示圖表
    # -------------------------------------------------
    def show_price_chart(self, flight_id, flight_number):
        url = f"{API_URL}/prices/{flight_id}"
        try:
            response = requests.get(url, headers=self.auth())
            if response.status_code != 200:
                QMessageBox.warning(self, "提示", "此航班目前沒有票價紀錄")
                return

            data = response.json()
            times = [d["time"] for d in data]
            prices = [d["price"] for d in data]

            plt.figure(figsize=(7, 4))
            plt.plot(times, prices, marker='o', linestyle='-', linewidth=2)
            plt.title(f"票價變化圖 - {flight_number}")
            plt.xlabel("查詢時間")
            plt.ylabel("票價 (TWD)")
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.grid(True)
            plt.show()

        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"無法顯示折線圖: {e}")


    # -------------------------------------------------
    # 自動在桌面跳出通知
    # -------------------------------------------------
    def handle_price_alert(self, data):
        flight_no = data.get("flight_number")
        price = data.get("price")

        # 在桌面彈出通知
        notification.notify(
            title="票價新低通知",
            message=f"{flight_no} 出現新低價：{price} TWD",
            timeout=5
        )

    # -------------------------------------------------
    # 載入通知
    # -------------------------------------------------
    def load_notifications(self):
        try:
            url = f"{API_URL}/notifications"
            response = requests.get(url, headers=self.auth())  # ✅ 加上 headers

            if response.status_code != 200:
                QMessageBox.warning(self, "錯誤", f"伺服器回傳錯誤：{response.text}")
                return
            
            data = response.json()
            
            if not isinstance(data, list):
                QMessageBox.warning(self, "錯誤", f"伺服器回傳非清單：{data}")
                return

            if not data:
                QMessageBox.information(self, "提示", "目前沒有通知紀錄")
                return

            self.notify_table.setRowCount(len(data))
            
            for i, n in enumerate(data):
                self.notify_table.setItem(i, 0, QTableWidgetItem(n["time"]))
                self.notify_table.setItem(i, 1, QTableWidgetItem(str(n["flight_id"])))
                self.notify_table.setItem(i, 2, QTableWidgetItem(str(n["price"])))
                self.notify_table.setItem(i, 3, QTableWidgetItem(n["message"]))
        
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"無法載入通知紀錄: {e}")


    # -------------------------------------------------
    # 載入排程日誌
    # -------------------------------------------------
    def load_logs(self):
        try:
            url = f"{API_URL}/check_logs"
            response = requests.get(url)
            data = response.json()
            
            self.log_table.setRowCount(len(data))
            
            for i, log in enumerate(data):
                self.log_table.setItem(i, 0, QTableWidgetItem(log["time"]))
                self.log_table.setItem(i, 1, QTableWidgetItem(log["status"]))
        
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"日誌載入失敗：{e}")

    # -------------------------------------------------
    # 8. 個人資料
    # -------------------------------------------------
    def init_profile_tab(self):
        layout = QVBoxLayout()
        title = QLabel("<h2>👤 個人資料</h2>")
        layout.addWidget(title)

        self.profile_label = QLabel("正在載入使用者資料...")
        self.profile_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.profile_label)

        refresh_btn = QPushButton("重新載入個人資料")
        refresh_btn.clicked.connect(self.load_profile)
        layout.addWidget(refresh_btn)

        # === 修改密碼功能 ===
        layout.addSpacing(15)
        pw_title = QLabel("<h3>🔒 修改密碼</h3>")
        layout.addWidget(pw_title)

        old_pw_label = QLabel("舊密碼：")
        self.old_pw_input = QLineEdit()
        self.old_pw_input.setEchoMode(QLineEdit.Password)

        new_pw_label = QLabel("新密碼：")
        self.new_pw_input = QLineEdit()
        self.new_pw_input.setEchoMode(QLineEdit.Password)

        layout.addWidget(old_pw_label)
        layout.addWidget(self.old_pw_input)
        layout.addWidget(new_pw_label)
        layout.addWidget(self.new_pw_input)

        change_btn = QPushButton("修改密碼")
        change_btn.setStyleSheet("background-color: #0275d8; color: white; font-weight: bold;")
        change_btn.clicked.connect(self.open_change_pw)
        layout.addWidget(change_btn)

        layout.addStretch()
        self.profile_tab.setLayout(layout)
        
        # 初始化資料
        self.load_profile()


    def load_profile(self):
        """呼叫 /profile 取得使用者資料"""
        try:
            res = requests.get(f"{API_URL}/profile", headers=self.auth())
            if res.status_code != 200:
                QMessageBox.warning(self, "錯誤", f"讀取失敗：{res.text}")
                return

            data = res.json()
            text = (
                f"🆔 使用者 ID：{data.get('user_id', '未知')}\n"
                f"👤 帳號名稱：{data.get('username', '未知')}\n"
                f"📅 註冊時間：{data.get('created_at', '未知')}"
            )
            self.profile_label.setText(text)
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"無法載入個人資料：{e}")

    def open_change_pw(self):
        """呼叫 /change_password"""
        old_pw = self.old_pw_input.text().strip()
        new_pw = self.new_pw_input.text().strip()
        
        if not old_pw or not new_pw:
            QMessageBox.warning(self, "錯誤", "請輸入舊密碼與新密碼")
            return

        try:
            res = requests.post(
                f"{API_URL}/change_password",
                json={"old_password": old_pw, "new_password": new_pw},
                headers=self.auth()
            )
            data = res.json()
            if res.status_code == 200:
                QMessageBox.information(self, "成功", "密碼修改成功！")
                self.old_pw_input.clear()
                self.new_pw_input.clear()
            else:
                QMessageBox.warning(self, "失敗", data.get("error", "修改失敗"))
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"修改密碼時發生錯誤：{e}")


    # -------------------------------------------------
    # Utils
    # -------------------------------------------------
    def auth(self):
        """回傳含 JWT 的 header"""
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    def reset_main_view(self):
        """
        安全地清空整個主畫面 layout
        避免 widget 殘留 / layout 重複綁定 / memory leak
        """
        old_layout = self.layout()
        if old_layout is not None:
            QWidget().setLayout(old_layout)

        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FlightApp()
    window.show()
    sys.exit(app.exec_())
