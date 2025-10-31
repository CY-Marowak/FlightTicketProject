import sys
import requests
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QMessageBox, QSystemTrayIcon
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt

API_URL = "http://127.0.0.1:5000/price"  # 你的 Flask 後端 API


class FlightApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("航班票價查詢系統 ✈️")
        self.setGeometry(500, 200, 600, 400)

        # === 新增系統通知圖示 ===
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon())  # 這裡可以放一個 icon.png
        self.tray_icon.show()

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        self.label_info = QLabel("輸入航班資訊：")
        layout.addWidget(self.label_info)

        self.input_from = QLineEdit()
        self.input_from.setPlaceholderText("出發地（如：TPE）")
        layout.addWidget(self.input_from)

        self.input_to = QLineEdit()
        self.input_to.setPlaceholderText("目的地（如：OKA）")
        layout.addWidget(self.input_to)

        self.input_depart = QLineEdit()
        self.input_depart.setPlaceholderText("出發日期（格式：YYYY-MM-DD）")
        layout.addWidget(self.input_depart)

        self.input_return = QLineEdit()
        self.input_return.setPlaceholderText("回程日期（格式：YYYY-MM-DD）")
        layout.addWidget(self.input_return)

        self.btn_search = QPushButton("查詢票價")
        self.btn_search.clicked.connect(self.search_flights)
        layout.addWidget(self.btn_search)

        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        layout.addWidget(self.result_box)

        self.setLayout(layout)

    def search_flights(self):
        depart = self.input_from.text().strip()
        dest = self.input_to.text().strip()
        depart_date = self.input_depart.text().strip()
        return_date = self.input_return.text().strip()

        params = {
            "from": depart,
            "to": dest,
            "depart": depart_date,
            "return": return_date
        }

        try:
            res = requests.get(API_URL, params=params, timeout=30)
            if res.status_code != 200:
                QMessageBox.warning(self, "API錯誤", f"查詢失敗：{res.text}")
                return

            data = res.json()
            if "flights" not in data or not data["flights"]:
                QMessageBox.information(self, "查無航班", "目前查無可用航班或票價。")
                return

            flights = data["flights"]
            output = f"✈️ {depart} → {dest}\n出發日: {depart_date} 回程日: {return_date}\n\n"

            for f in flights:
                output += (
                    f"航空公司: {f['airline']}\n"
                    f"航班號: {f['flight_number']}\n"
                    f"出發時間: {f['depart_time']}\n"
                    f"抵達時間: {f['arrival_time']}\n"
                    f"票價: {f['price']} TWD\n"
                    f"{'-'*30}\n"
                )

            self.result_box.setText(output)

            # ✅ 使用 Qt 系統通知（不會報錯）
            cheapest = flights[0]
            msg = f"{cheapest['airline']} 最低票價 {cheapest['price']} 元"
            self.tray_icon.showMessage("查詢成功", msg, QSystemTrayIcon.Information, 5000)

        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"查詢過程中發生錯誤：{str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FlightApp()
    window.show()
    sys.exit(app.exec_())
