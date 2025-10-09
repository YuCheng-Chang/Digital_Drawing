# test_wacom_with_system.py
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QPen, QColor
import sys
import time
from datetime import datetime
import logging
from InkProcessingSystemMainController import InkProcessingSystem
from Config import ProcessingConfig

class WacomDrawingCanvas(QWidget):
    def __init__(self, ink_system):
        super().__init__()
        self.ink_system = ink_system
        
        # ✅ 添加缺失的屬性初始化
        self.current_stroke_points = []
        self.all_strokes = []
        self.stroke_count = 0
        self.total_points = 0
        self.logger = logging.getLogger('WacomDrawingCanvas')
        
        # 設置視窗
        self.setWindowTitle("Wacom 繪圖測試")
        self.setGeometry(100, 100, 800, 600)
        self.setMouseTracking(True)
        
        # ===== LSL 整合 =====
        from LSLIntegration import LSLIntegration, LSLStreamConfig
        
        lsl_config = LSLStreamConfig(
            device_manufacturer="Wacom",
            device_model="Wacom One 12",
            normalize_coordinates=True,
            screen_width=self.width(),
            screen_height=self.height()
        )
        
        self.lsl = LSLIntegration(
            stream_config=lsl_config,
            output_dir="./wacom_recordings"
        )
        
        # 啟動 LSL 串流和記錄
        self.lsl.start(
            session_id=f"wacom_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            metadata={
                'experiment': 'wacom_drawing_test',
                'screen_resolution': f"{self.width()}x{self.height()}"
            }
        )
        
        # 註冊回調函數
        self.ink_system.register_callback(
            'on_point_processed',
            self._on_point_processed_callback
        )
        self.ink_system.register_callback(
            'on_stroke_completed',
            self._on_stroke_completed_callback
        )

    
    def _on_point_processed_callback(self, point_data):
        """處理點數據並推送到 LSL"""
        self.lsl.process_ink_point(
            x=point_data['x'],
            y=point_data['y'],
            pressure=point_data['pressure'],
            tilt_x=point_data.get('tilt_x', 0),
            tilt_y=point_data.get('tilt_y', 0),
            velocity=point_data.get('velocity', 0),
            is_stroke_start=point_data.get('is_stroke_start', False),
            is_stroke_end=point_data.get('is_stroke_end', False)
        )
    
    def _on_stroke_completed_callback(self, stroke_data):
        """筆劃完成時的處理"""
        self.logger.info(f"Stroke {stroke_data['stroke_id']} completed")
    
    def closeEvent(self, event):
        """視窗關閉時停止 LSL"""
        if hasattr(self, 'lsl'):
            saved_files = self.lsl.stop()
            self.logger.info(f"LSL data saved: {saved_files}")
        
        # 原有的關閉邏輯
        super().closeEvent(event)
        
    def tabletEvent(self, event):
        """接收 Wacom 輸入事件"""
        point_data = {
            'x': event.x(),
            'y': event.y(),
            'pressure': event.pressure(),
            'timestamp': time.time(),
            'tilt_x': event.xTilt(),
            'tilt_y': event.yTilt()
        }
        
        # 傳遞給墨水處理系統
        self.ink_system.process_raw_point(point_data)
        
        # 用於即時繪製
        if event.pressure() > 0:
            self.current_stroke_points.append((event.x(), event.y(), event.pressure()))
            self.total_points += 1
        else:
            # 筆劃結束
            if self.current_stroke_points:
                self.all_strokes.append(self.current_stroke_points.copy())
                self.current_stroke_points = []
                self.stroke_count += 1
        
        self.update()  # 重繪
        event.accept()
        
    def paintEvent(self, event):
        """繪製筆劃"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 繪製已完成的筆劃（黑色）
        pen = QPen(QColor(0, 0, 0), 2)
        painter.setPen(pen)
        
        for stroke in self.all_strokes:
            for i in range(len(stroke) - 1):
                x1, y1, p1 = stroke[i]
                x2, y2, p2 = stroke[i + 1]
                # 根據壓力調整線寬
                width = 1 + p1 * 5
                pen.setWidthF(width)
                painter.setPen(pen)
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        
        # 繪製當前筆劃（藍色）
        pen = QPen(QColor(0, 100, 255), 2)
        painter.setPen(pen)
        
        for i in range(len(self.current_stroke_points) - 1):
            x1, y1, p1 = self.current_stroke_points[i]
            x2, y2, p2 = self.current_stroke_points[i + 1]
            width = 1 + p1 * 5
            pen.setWidthF(width)
            painter.setPen(pen)
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        
        # 顯示統計資訊
        painter.setPen(QPen(QColor(100, 100, 100)))
        stats_text = f"筆劃數: {self.stroke_count} | 總點數: {self.total_points}"
        painter.drawText(10, 20, stats_text)
        
    def update_stats_display(self):
        """更新統計顯示"""
        self.setWindowTitle(
            f"Wacom 測試 - 筆劃: {self.stroke_count}, 點數: {self.total_points}"
        )

def test_wacom_with_full_system():
    """
    完整的 Wacom + 墨水處理系統測試
    """
    print("=" * 60)
    print("🎨 Wacom 墨水處理系統完整測試")
    print("=" * 60)
    
    # 創建配置
    config = ProcessingConfig(
        device_type="wacom",
        target_sampling_rate=200,
        smoothing_enabled=True,
        feature_types=['basic', 'kinematic', 'pressure']
    )
    
    # 創建墨水處理系統
    ink_system = InkProcessingSystem(config)
    
    # 設備配置
    device_config = {
        'device_type': 'wacom',
        'sampling_rate': 200
    }
    
    # 初始化系統
    print("\n🔧 初始化墨水處理系統...")
    if not ink_system.initialize(device_config):
        print("❌ 系統初始化失敗")
        return
    
    print("✅ 系統初始化成功")
    
    # 註冊回調函數
    def on_stroke_completed(data):
        stroke = data['stroke']
        print(f"\n✓ 筆劃完成:")
        print(f"  - 點數: {len(stroke.points)}")
        print(f"  - 持續時間: {stroke.duration:.3f} 秒")
        if hasattr(stroke, 'pressure_stats'):
            print(f"  - 平均壓力: {stroke.pressure_stats.get('mean', 0):.3f}")
    
    def on_features_calculated(data):
        features = data['features']
        print(f"\n✓ 特徵計算完成:")
        
        if 'basic' in features:
            basic = features['basic']
            print(f"  [基本特徵]")
            print(f"    長度: {basic.get('length', 0):.2f} px")
            print(f"    速度: {basic.get('avg_velocity', 0):.2f} px/s")
        
        if 'kinematic' in features:
            kinematic = features['kinematic']
            print(f"  [運動學特徵]")
            print(f"    加速度: {kinematic.get('avg_acceleration', 0):.2f}")
            print(f"    急動度: {kinematic.get('avg_jerk', 0):.2f}")
        
        if 'pressure' in features:
            pressure = features['pressure']
            print(f"  [壓力特徵]")
            print(f"    平均壓力: {pressure.get('mean_pressure', 0):.3f}")
            print(f"    壓力變化: {pressure.get('pressure_variation', 0):.3f}")
    
    def on_error(data):
        print(f"\n❌ 錯誤: {data['error_type']}")
        print(f"   訊息: {data['message']}")
    
    ink_system.register_callback('on_stroke_completed', on_stroke_completed)
    ink_system.register_callback('on_features_calculated', on_features_calculated)
    ink_system.register_callback('on_error', on_error)
    
    # 啟動處理（使用外部輸入模式）
    print("\n🚀 啟動數據處理...")
    if not ink_system.start_processing(use_external_input=True):  # ✅ 添加參數
        print("❌ 無法啟動處理")
        return

    print("✅ 處理已啟動（外部輸入模式）")

    
    # 創建 GUI
    app = QApplication(sys.argv)
    canvas = WacomDrawingCanvas(ink_system)
    canvas.show()
    
    print("\n" + "=" * 60)
    print("🎨 請在視窗中使用 Wacom 筆書寫")
    print("   - 筆劃會即時顯示")
    print("   - 特徵會自動計算並顯示在終端")
    print("   - 關閉視窗即結束測試")
    print("=" * 60 + "\n")
    
    # 運行應用
    try:
        app.exec_()
    except KeyboardInterrupt:
        print("\n⚠️  使用者中斷")
    
    # 清理
    print("\n🛑 停止處理...")
    ink_system.stop_processing()
    
    print("\n📈 最終統計:")
    stats = ink_system.get_processing_statistics()
    print(f"  - 總筆劃數: {stats.get('total_strokes', 0)}")
    print(f"  - 總原始點數: {stats.get('total_raw_points', 0)}")
    print(f"  - 總處理點數: {stats.get('total_processed_points', 0)}")
    print(f"  - 平均採樣率: {stats.get('raw_points_per_second', 0):.1f} 點/秒")
    
    ink_system.shutdown()
    print("\n✅ 測試完成")

if __name__ == "__main__":
    test_wacom_with_full_system()
