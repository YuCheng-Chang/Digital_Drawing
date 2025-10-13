# wacom_resolution_test.py
"""
數位板時間和空間解析度測試工具

測試項目：
1. 時間解析度（Temporal Resolution）：點與點之間的時間間隔
2. 空間解析度（Spatial Resolution）：點與點之間的距離
3. 實際採樣率（Sampling Rate）
4. 移動速度分析
"""

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QPen, QColor
import sys
import time
import numpy as np
from collections import defaultdict


class ResolutionTestCanvas(QWidget):
    """解析度測試畫布"""
    
    def __init__(self):
        super().__init__()
        
        # 數據儲存
        self.current_stroke = []  # 當前筆劃：[(x, y, pressure, timestamp), ...]
        self.all_strokes = []     # 所有筆劃
        
        # 統計數據
        self.time_intervals = []   # 時間間隔（ms）
        self.spatial_distances = [] # 空間距離（pixels）
        self.velocities = []        # 速度（px/s）
        
        # UI 設置
        self.init_ui()
        
    def init_ui(self):
        """初始化 UI"""
        self.setWindowTitle("數位板解析度測試")
        self.setGeometry(100, 100, 1200, 800)
        
        # 主布局
        layout = QVBoxLayout()
        
        # 標題
        title = QLabel("🎨 數位板時間與空間解析度測試")
        title.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        layout.addWidget(title)
        
        # 說明
        instruction = QLabel(
            "請在下方白色區域繪製筆劃，程式會自動分析：\n"
            "• 時間解析度：點與點之間的時間間隔\n"
            "• 空間解析度：點與點之間的距離\n"
            "• 實際採樣率和移動速度"
        )
        instruction.setStyleSheet("padding: 5px; background-color: #f0f0f0;")
        layout.addWidget(instruction)
        
        # 繪圖區域
        self.canvas = DrawingArea(self)
        self.canvas.setMinimumHeight(400)
        layout.addWidget(self.canvas)
        
        # 統計顯示
        self.stats_display = QTextEdit()
        self.stats_display.setReadOnly(True)
        self.stats_display.setMaximumHeight(200)
        self.stats_display.setStyleSheet("font-family: monospace; font-size: 11px;")
        layout.addWidget(self.stats_display)
        
        # 按鈕
        clear_btn = QPushButton("清除數據")
        clear_btn.clicked.connect(self.clear_data)
        layout.addWidget(clear_btn)
        
        self.setLayout(layout)
        self.update_stats_display()
        
    def tabletEvent(self, event):
        """處理數位板事件"""
        current_time = time.time()
        
        point = {
            'x': event.x(),
            'y': event.y(),
            'pressure': event.pressure(),
            'timestamp': current_time
        }
        
        if event.pressure() > 0:
            # 筆觸中
            if len(self.current_stroke) > 0:
                # 計算與上一點的間隔
                last_point = self.current_stroke[-1]
                
                # 時間間隔（ms）
                time_interval = (current_time - last_point['timestamp']) * 1000
                self.time_intervals.append(time_interval)
                
                # 空間距離（pixels）
                dx = point['x'] - last_point['x']
                dy = point['y'] - last_point['y']
                distance = np.sqrt(dx**2 + dy**2)
                self.spatial_distances.append(distance)
                
                # 速度（px/s）
                if time_interval > 0:
                    velocity = distance / (time_interval / 1000)
                    self.velocities.append(velocity)
            
            self.current_stroke.append(point)
            
        else:
            # 筆劃結束
            if len(self.current_stroke) > 0:
                self.all_strokes.append(self.current_stroke.copy())
                self.current_stroke = []
                self.update_stats_display()
        
        self.canvas.update()
        event.accept()
        
    def update_stats_display(self):
        """更新統計顯示"""
        if len(self.time_intervals) == 0:
            self.stats_display.setText("等待數據... 請開始繪製")
            return
        
        # 計算統計數據
        time_arr = np.array(self.time_intervals)
        dist_arr = np.array(self.spatial_distances)
        vel_arr = np.array(self.velocities)
        
        # 生成報告
        report = self.generate_report(time_arr, dist_arr, vel_arr)
        self.stats_display.setText(report)
        
    def generate_report(self, time_arr, dist_arr, vel_arr):
        """生成測試報告"""
        report = []
        report.append("=" * 80)
        report.append("📊 數位板解析度測試報告")
        report.append("=" * 80)
        report.append("")
        
        # 基本資訊
        report.append(f"總筆劃數：{len(self.all_strokes)}")
        report.append(f"總採樣點數：{sum(len(s) for s in self.all_strokes)}")
        report.append(f"分析的點對數：{len(time_arr)}")
        report.append("")
        
        # 時間解析度
        report.append("⏱️  時間解析度（Temporal Resolution）")
        report.append("-" * 80)
        report.append(f"  平均時間間隔：{time_arr.mean():.3f} ms")
        report.append(f"  中位數時間間隔：{np.median(time_arr):.3f} ms")
        report.append(f"  最小時間間隔：{time_arr.min():.3f} ms")
        report.append(f"  最大時間間隔：{time_arr.max():.3f} ms")
        report.append(f"  標準差：{time_arr.std():.3f} ms")
        report.append("")
        
        # 實際採樣率
        avg_interval_sec = time_arr.mean() / 1000
        actual_sampling_rate = 1 / avg_interval_sec if avg_interval_sec > 0 else 0
        report.append(f"  ➜ 實際採樣率：{actual_sampling_rate:.1f} Hz")
        report.append(f"  ➜ 理論最大採樣率：{1000/time_arr.min():.1f} Hz")
        report.append("")
        
        # 時間間隔分佈
        report.append("  時間間隔分佈：")
        bins = [0, 2, 5, 10, 15, 20, 50, 100, np.inf]
        labels = ["<2ms", "2-5ms", "5-10ms", "10-15ms", "15-20ms", "20-50ms", "50-100ms", ">100ms"]
        hist, _ = np.histogram(time_arr, bins=bins)
        for label, count in zip(labels, hist):
            percentage = count / len(time_arr) * 100
            bar = "█" * int(percentage / 2)
            report.append(f"    {label:>10}: {count:4d} ({percentage:5.1f}%) {bar}")
        report.append("")
        
        # 空間解析度
        report.append("📏 空間解析度（Spatial Resolution）")
        report.append("-" * 80)
        report.append(f"  平均點間距離：{dist_arr.mean():.3f} pixels")
        report.append(f"  中位數點間距離：{np.median(dist_arr):.3f} pixels")
        report.append(f"  最小點間距離：{dist_arr.min():.3f} pixels")
        report.append(f"  最大點間距離：{dist_arr.max():.3f} pixels")
        report.append(f"  標準差：{dist_arr.std():.3f} pixels")
        report.append("")
        
        # 空間距離分佈
        report.append("  點間距離分佈：")
        bins = [0, 0.5, 1, 2, 5, 10, 20, 50, np.inf]
        labels = ["<0.5px", "0.5-1px", "1-2px", "2-5px", "5-10px", "10-20px", "20-50px", ">50px"]
        hist, _ = np.histogram(dist_arr, bins=bins)
        for label, count in zip(labels, hist):
            percentage = count / len(dist_arr) * 100
            bar = "█" * int(percentage / 2)
            report.append(f"    {label:>10}: {count:4d} ({percentage:5.1f}%) {bar}")
        report.append("")
        
        # 速度分析
        report.append("🚀 移動速度分析（Velocity Analysis）")
        report.append("-" * 80)
        report.append(f"  平均速度：{vel_arr.mean():.1f} px/s")
        report.append(f"  中位數速度：{np.median(vel_arr):.1f} px/s")
        report.append(f"  最小速度：{vel_arr.min():.1f} px/s")
        report.append(f"  最大速度：{vel_arr.max():.1f} px/s")
        report.append(f"  標準差：{vel_arr.std():.1f} px/s")
        report.append("")
        
        # 速度分佈
        report.append("  速度分佈：")
        bins = [0, 50, 100, 200, 500, 1000, 2000, 5000, np.inf]
        labels = ["<50", "50-100", "100-200", "200-500", "500-1k", "1k-2k", "2k-5k", ">5k"]
        hist, _ = np.histogram(vel_arr, bins=bins)
        for label, count in zip(labels, hist):
            percentage = count / len(vel_arr) * 100
            bar = "█" * int(percentage / 2)
            report.append(f"    {label:>10} px/s: {count:4d} ({percentage:5.1f}%) {bar}")
        report.append("")
        
        # 評估
        report.append("📋 評估結果")
        report.append("-" * 80)
        
        # 時間解析度評估
        if actual_sampling_rate >= 200:
            report.append("  ✅ 時間解析度：優秀（≥200 Hz）")
        elif actual_sampling_rate >= 133:
            report.append("  ✅ 時間解析度：良好（≥133 Hz）")
        elif actual_sampling_rate >= 100:
            report.append("  ⚠️  時間解析度：尚可（≥100 Hz）")
        else:
            report.append("  ❌ 時間解析度：偏低（<100 Hz）")
        
        # 空間解析度評估
        avg_dist = dist_arr.mean()
        if avg_dist <= 2:
            report.append("  ✅ 空間解析度：優秀（平均 ≤2 px）")
        elif avg_dist <= 5:
            report.append("  ✅ 空間解析度：良好（平均 ≤5 px）")
        elif avg_dist <= 10:
            report.append("  ⚠️  空間解析度：尚可（平均 ≤10 px）")
        else:
            report.append("  ❌ 空間解析度：偏低（平均 >10 px）")
        
        # 穩定性評估
        time_cv = time_arr.std() / time_arr.mean()  # 變異係數
        if time_cv <= 0.3:
            report.append("  ✅ 採樣穩定性：優秀（CV ≤0.3）")
        elif time_cv <= 0.5:
            report.append("  ⚠️  採樣穩定性：尚可（CV ≤0.5）")
        else:
            report.append("  ❌ 採樣穩定性：不穩定（CV >0.5）")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)
        
    def clear_data(self):
        """清除所有數據"""
        self.current_stroke = []
        self.all_strokes = []
        self.time_intervals = []
        self.spatial_distances = []
        self.velocities = []
        self.canvas.update()
        self.update_stats_display()
        
    def get_drawing_data(self):
        """獲取繪圖數據（供 DrawingArea 使用）"""
        return {
            'current_stroke': self.current_stroke,
            'all_strokes': self.all_strokes
        }


class DrawingArea(QWidget):
    """繪圖區域"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_canvas = parent
        self.setStyleSheet("background-color: white;")
        
    def paintEvent(self, event):
        """繪製筆劃"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        data = self.parent_canvas.get_drawing_data()
        
        # 繪製已完成的筆劃（黑色）
        pen = QPen(QColor(0, 0, 0), 2)
        painter.setPen(pen)
        
        for stroke in data['all_strokes']:
            for i in range(len(stroke) - 1):
                p1 = stroke[i]
                p2 = stroke[i + 1]
                
                # 根據壓力調整線寬
                width = 1 + p1['pressure'] * 4
                pen.setWidthF(width)
                painter.setPen(pen)
                
                painter.drawLine(
                    int(p1['x']), int(p1['y']),
                    int(p2['x']), int(p2['y'])
                )
        
        # 繪製當前筆劃（藍色）
        if len(data['current_stroke']) > 1:
            pen = QPen(QColor(0, 100, 255), 2)
            
            for i in range(len(data['current_stroke']) - 1):
                p1 = data['current_stroke'][i]
                p2 = data['current_stroke'][i + 1]
                
                width = 1 + p1['pressure'] * 4
                pen.setWidthF(width)
                painter.setPen(pen)
                
                painter.drawLine(
                    int(p1['x']), int(p1['y']),
                    int(p2['x']), int(p2['y'])
                )


def main():
    """主程式"""
    print("=" * 80)
    print("🎨 數位板解析度測試工具")
    print("=" * 80)
    print("\n請在視窗中繪製筆劃，程式會自動分析時間和空間解析度")
    print("\n測試建議：")
    print("  1. 繪製慢速筆劃（測試最小空間解析度）")
    print("  2. 繪製快速筆劃（測試採樣率和速度範圍）")
    print("  3. 繪製不同壓力的筆劃（測試壓力感應）")
    print("  4. 繪製多條筆劃以獲得統計意義的結果")
    print("\n" + "=" * 80 + "\n")
    
    app = QApplication(sys.argv)
    canvas = ResolutionTestCanvas()
    canvas.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()