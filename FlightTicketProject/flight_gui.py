import sys
import requests
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QMessageBox,
    QHeaderView, QTabWidget, QHBoxLayout
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

ICON_PATH = "plane.png"

class FlightApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("航班查詢與追蹤系統")
        self.setGeometry(200, 200, 900, 600)
        self.setWindowIcon(QIcon(ICON_PATH))  # 可自行替換icon

        # --- 主分頁 ---
        self.tabs = QTabWidget()
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)

        # === 分頁1：查詢航班 ===
        self.query_tab = QWidget()
        self.tabs.addTab(self.query_tab, "查詢航班")
        self.init_query_tab()

        # === 分頁2：我的航班 ===
        self.tracked_tab = QWidget()
        self.tabs.addTab(self.tracked_tab, "我的航班")
        self.init_tracked_tab()

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
    # 查詢航班（呼叫 Flask /price）
    # -------------------------------------------------
    def search_flights(self):
        from_airport = self.from_input.text().strip()
        to_airport = self.to_input.text().strip()
        depart_date = self.depart_input.text().strip()
        return_date = self.return_input.text().strip()

        url = f"http://127.0.0.1:5000/price?from={from_airport}&to={to_airport}&depart={depart_date}&return={return_date}"

        try:
            response = requests.get(url)
            data = response.json()

            if "flights" not in data or not data["flights"]:
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
        url = "http://127.0.0.1:5000/flights"
        try:
            response = requests.post(url, json=flight)
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
        url = "http://127.0.0.1:5000/flights"
        try:
            response = requests.get(url)
            data = response.json()

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

                del_btn = QPushButton("刪除")
                del_btn.clicked.connect(lambda _, fid=f["id"]: self.delete_flight(fid))
                self.tracked_table.setCellWidget(i, 6, del_btn)

        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"無法載入追蹤清單: {e}")

    # -------------------------------------------------
    # 刪除航班（DELETE /flights/<id>）
    # -------------------------------------------------
    def delete_flight(self, flight_id):
        url = f"http://127.0.0.1:5000/flights/{flight_id}"
        try:
            response = requests.delete(url)
            data = response.json()
            if response.status_code == 200:
                QMessageBox.information(self, "成功", data.get("message", "已刪除航班"))
                self.load_tracked_flights()
            else:
                QMessageBox.warning(self, "失敗", data.get("error", "刪除失敗"))
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"無法刪除航班: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FlightApp()
    window.show()
    sys.exit(app.exec_())
