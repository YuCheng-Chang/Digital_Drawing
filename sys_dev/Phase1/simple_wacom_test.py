# simple_wacom_test.py
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt
import sys

class SimpleWacomTest(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wacom 簡單測試")
        self.setGeometry(100, 100, 600, 400)
        self.setStyleSheet("background-color: white;")
        
    def tabletEvent(self, event):
        print(f"✅ Wacom 輸入偵測!")
        print(f"   位置: ({event.x()}, {event.y()})")
        print(f"   壓力: {event.pressure():.3f}")
        print(f"   類型: {event.pointerType()}")
        event.accept()
        
    def mousePressEvent(self, event):
        print(f"⚠️  偵測到滑鼠事件（非數位板）")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = SimpleWacomTest()
    window.show()
    print("\n🎨 請在視窗中使用 Wacom 筆書寫...")
    print("   如果看到 '✅ Wacom 輸入偵測'，表示設備正常\n")
    sys.exit(app.exec_())
