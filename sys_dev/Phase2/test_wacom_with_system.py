# test_wacom_with_system.py
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QPen, QColor, QTabletEvent
import sys
import time
from datetime import datetime
import logging
from InkProcessingSystemMainController import InkProcessingSystem
from Config import ProcessingConfig

class WacomDrawingCanvas(QWidget):
    def __init__(self, ink_system, config: ProcessingConfig):
        super().__init__()
        self.ink_system = ink_system
        self.config = config
        
        # 基本屬性
        self.current_stroke_points = []
        self.all_strokes = []
        self.stroke_count = 0
        self.total_points = 0
        self.logger = logging.getLogger('WacomDrawingCanvas')
        
        # ✅✅✅ 狀態追蹤
        self.last_point_data = None
        self.pen_is_in_canvas = False      # 筆是否在畫布內
        self.pen_is_touching = False       # 筆是否接觸屏幕（壓力 > 0）
        self.current_pressure = 0.0        # ✅ 新增：當前壓力值
        
        # 畫布設置
        canvas_width = config.canvas_width
        canvas_height = config.canvas_height
        
        self.setWindowTitle("Wacom 繪圖測試")
        self.setGeometry(100, 100, canvas_width, canvas_height)
        self.setMouseTracking(True)
        
        # LSL 整合
        from LSLIntegration import LSLIntegration, LSLStreamConfig
        
        lsl_config = LSLStreamConfig(
            device_manufacturer="Wacom",
            device_model="Wacom One 12",
            normalize_coordinates=True,
            screen_width=canvas_width,
            screen_height=canvas_height
        )
        
        self.lsl = LSLIntegration(
            stream_config=lsl_config,
            output_dir="./wacom_recordings"
        )
        
        self.lsl.start(
            session_id=f"wacom_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            metadata={
                'experiment': 'wacom_drawing_test',
                'screen_resolution': f"{canvas_width}x{canvas_height}",
                'canvas_width': canvas_width,
                'canvas_height': canvas_height
            }
        )
        
        # 註冊回調
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
        self.logger.info(f"✅ Stroke {stroke_data['stroke_id']} completed")
    
    def closeEvent(self, event):
        """視窗關閉時的處理"""
        try:
            self.logger.info("🔚 Canvas closing...")
            
            from StrokeDetector import StrokeState
            
            # ✅✅✅ 修復 1：檢查是否有未完成的筆劃
            if (hasattr(self.ink_system, 'stroke_detector') and 
                self.ink_system.stroke_detector.current_state in [StrokeState.ACTIVE, StrokeState.STARTING]):
                
                self.logger.info("🔚 關閉視窗前強制完成當前筆劃")
                
                if self.last_point_data is not None:
                    final_point = self.last_point_data.copy()
                    final_point['pressure'] = 0.0
                    final_point['timestamp'] = time.time()
                    
                    self.ink_system.process_raw_point(final_point)
                    
                    # 等待處理完成
                    time.sleep(0.1)
            
            # ✅✅✅ 修復 2：強制檢查已完成但未處理的筆劃
            if hasattr(self.ink_system, 'stroke_detector'):
                completed_strokes = self.ink_system.stroke_detector.get_completed_strokes()
                
                if completed_strokes:
                    self.logger.info(f"🔍 關閉前發現 {len(completed_strokes)} 個已完成但未處理的筆劃")
                    
                    for stroke_data in completed_strokes:
                        stroke_id = stroke_data['stroke_id']
                        stroke_points = stroke_data['points']
                        
                        self.logger.info(f"🔍 手動處理筆劃: stroke_id={stroke_id}, points={len(stroke_points)}")
                        
                        # 加入筆劃緩衝區
                        self.ink_system.stroke_buffer.append(stroke_data)
                        self.ink_system.processing_stats['total_strokes'] += 1
                        
                        # 觸發回調
                        self.ink_system._trigger_callback('on_stroke_completed', {
                            'stroke_id': stroke_id,
                            'points': stroke_points,
                            'num_points': len(stroke_points),
                            'start_time': stroke_data['start_time'],
                            'end_time': stroke_data['end_time'],
                            'timestamp': time.time()
                        })
                    
                    # 等待特徵計算完成
                    max_wait = 2.0
                    start_time = time.time()
                    
                    while time.time() - start_time < max_wait:
                        if len(self.ink_system.stroke_buffer) == 0:
                            self.logger.info("✅ stroke_buffer 已清空")
                            break
                        time.sleep(0.05)
                    
                    time.sleep(0.2)
                    self.logger.info("✅ 特徵計算處理完成")
            
            # 停止系統
            if self.ink_system:
                self.logger.info("Stopping ink processing system...")
                self.ink_system.stop_processing()
                self.ink_system.shutdown()
                self.logger.info("Ink processing system stopped")
            
            event.accept()
            self.logger.info("Canvas closed successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Error during close: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            event.accept()


    def enterEvent(self, event):
        """
        ✅✅✅ 筆進入畫布區域時觸發
        """
        try:
            self.logger.info(f"🚪 筆進入畫布區域 (當前壓力: {self.current_pressure:.3f})")
            
            # 更新狀態
            self.pen_is_in_canvas = True
            
            # ✅ 清理過舊的未完成筆劃（防止狀態混亂）
            if self.current_stroke_points and self.last_point_data is not None:
                time_since_last_point = time.time() - self.last_point_data['timestamp']
                
                if time_since_last_point > 1.0:  # 超過 1 秒
                    self.logger.warning(f"⚠️ 清理舊筆劃（{time_since_last_point:.2f}s 前）")
                    self.current_stroke_points = []
                    self.last_point_data = None
                    self.pen_is_touching = False
            
            event.accept()
            
        except Exception as e:
            self.logger.error(f"❌ enterEvent 處理失敗: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def leaveEvent(self, event):
        """
        ✅✅✅ 筆離開畫布區域時觸發
        需求：從內移出時，將離開畫布前最後一個點當筆劃終點
        
        關鍵：只有在「筆接觸屏幕」(壓力 > 0) 時才結束筆劃
        """
        try:
            self.logger.info(f"🚪 筆離開畫布區域 (當前壓力: {self.current_pressure:.3f})")
            
            # 更新狀態
            self.pen_is_in_canvas = False
            
            # ✅✅✅ 關鍵檢查：同時考慮位置和壓力
            # 只有在「筆接觸屏幕」且「有未完成筆劃」時才結束
            if self.pen_is_touching and self.current_pressure > 0 and self.current_stroke_points:
                self.logger.info("🔚 筆接觸屏幕時移出畫布，使用最後一個點作為筆劃終點")
                
                if self.last_point_data is not None:
                    # 使用最後一個點的位置，但壓力設為 0
                    final_point = self.last_point_data.copy()
                    final_point['pressure'] = 0.0
                    final_point['timestamp'] = time.time()
                    
                    self.logger.info(
                        f"🔚 發送終點: ({final_point['x']:.1f}, {final_point['y']:.1f}), "
                        f"pressure=0 (原壓力: {self.current_pressure:.3f})"
                    )
                    
                    self.ink_system.process_raw_point(final_point)
                    
                    # 清空當前筆劃
                    self.all_strokes.append(self.current_stroke_points.copy())
                    self.current_stroke_points = []
                    self.stroke_count += 1
                    
                    # 重置狀態
                    self.pen_is_touching = False
                    self.current_pressure = 0.0
                    self.last_point_data = None
                    
                    self.update()
            else:
                # 筆懸空移出畫布，不需要處理
                reason = []
                if not self.pen_is_touching:
                    reason.append("筆未接觸屏幕")
                if self.current_pressure <= 0:
                    reason.append("壓力為0")
                if not self.current_stroke_points:
                    reason.append("沒有未完成的筆劃")
                
                self.logger.debug(f"⏭️ 跳過處理: {', '.join(reason)}")
            
            event.accept()
            
        except Exception as e:
            self.logger.error(f"❌ leaveEvent 處理失敗: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

        
    def tabletEvent(self, event):
        """
        ✅✅✅ 接收 Wacom 輸入事件
        需求：從外進入時，接觸畫布的第一個點當筆劃起始點
        
        關鍵：只處理「在畫布內」且「壓力 > 0」的點
        """
        try:
            # ✅ 獲取當前壓力
            current_pressure = event.pressure()
            self.current_pressure = current_pressure  # 更新全局壓力狀態
            
            # ✅ 檢查點是否在畫布範圍內
            pos = event.pos()
            is_in_bounds = self.rect().contains(pos)
            
            # ✅ 更新筆在畫布內的狀態
            if is_in_bounds and not self.pen_is_in_canvas:
                self.logger.debug(f"✅ 筆進入畫布範圍: ({pos.x()}, {pos.y()}), pressure={current_pressure:.3f}")
                self.pen_is_in_canvas = True
            elif not is_in_bounds and self.pen_is_in_canvas:
                self.logger.debug(f"⚠️ 筆移出畫布範圍: ({pos.x()}, {pos.y()}), pressure={current_pressure:.3f}")
                self.pen_is_in_canvas = False
            
            # ✅✅✅ 關鍵：只處理在畫布範圍內的點
            if not is_in_bounds:
                self.logger.debug(f"⏭️ 點在畫布外，跳過處理: ({pos.x()}, {pos.y()})")
                event.accept()
                return
            
            # ✅✅✅ 處理壓力 > 0 的情況（筆接觸屏幕）
            if current_pressure > 0:
                point_data = {
                    'x': event.x(),
                    'y': event.y(),
                    'pressure': current_pressure,
                    'timestamp': time.time(),
                    'tilt_x': event.xTilt(),
                    'tilt_y': event.yTilt()
                }
                
                # ✅ 檢查是否是筆劃的第一個點
                if not self.pen_is_touching:
                    self.logger.info(
                        f"🎨 筆劃開始（第一個點）: "
                        f"({point_data['x']:.1f}, {point_data['y']:.1f}), "
                        f"pressure={current_pressure:.3f}"
                    )
                    self.pen_is_touching = True
                
                # ✅ 記錄最後一個點
                self.last_point_data = point_data
                
                # ✅ 傳遞給墨水處理系統
                self.ink_system.process_raw_point(point_data)
                
                # ✅ 用於即時繪製
                self.current_stroke_points.append((event.x(), event.y(), current_pressure))
                self.total_points += 1
            
            # ✅✅✅ 處理壓力 = 0 的情況（筆離開屏幕）
            else:
                if self.pen_is_touching and self.current_stroke_points:
                    self.logger.info(
                        f"🔚 筆離開屏幕（壓力=0），筆劃結束 "
                        f"at ({event.x():.1f}, {event.y():.1f})"
                    )
                    
                    # ✅ 發送壓力 = 0 的事件通知筆劃結束
                    point_data = {
                        'x': event.x(),
                        'y': event.y(),
                        'pressure': 0.0,
                        'timestamp': time.time(),
                        'tilt_x': event.xTilt(),
                        'tilt_y': event.yTilt()
                    }
                    self.ink_system.process_raw_point(point_data)
                    
                    # ✅ 畫布上的處理
                    self.all_strokes.append(self.current_stroke_points.copy())
                    self.current_stroke_points = []
                    self.stroke_count += 1
                    
                    # ✅ 重置狀態
                    self.pen_is_touching = False
                    self.last_point_data = None
            
            self.update()
            event.accept()
            
        except Exception as e:
            self.logger.error(f"❌ tabletEvent 處理失敗: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
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
        stats_text = f"筆劃數: {self.stroke_count} | 總點數: {self.total_points} | 壓力: {self.current_pressure:.3f}"
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
    
    # ✅ 創建配置（可以自定義畫布大小）
    config = ProcessingConfig(
        device_type="wacom",
        target_sampling_rate=200,
        smoothing_enabled=True,
        feature_types=['basic', 'kinematic', 'pressure'],
        canvas_width=800,
        canvas_height=600
    )
    
    print(f"\n📐 畫布配置: {config.canvas_width} x {config.canvas_height}")
    
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
        """筆劃完成回調"""
        try:
            stroke_id = data.get('stroke_id', 'N/A')
            points = data.get('points', [])
            num_points = data.get('num_points', len(points))
            
            print(f"\n✅ 筆劃完成:")
            print(f"   - ID: {stroke_id}")
            print(f"   - 點數: {num_points}")
            
            # 計算持續時間
            if points and len(points) >= 2:
                duration = points[-1].timestamp - points[0].timestamp
                print(f"   - 持續時間: {duration:.3f}s")
                
                # ✅ 計算像素長度
                canvas_width = config.canvas_width
                canvas_height = config.canvas_height
                
                total_length = 0
                for i in range(1, len(points)):
                    p1 = points[i-1]
                    p2 = points[i]
                    
                    x1 = p1.x * canvas_width
                    y1 = p1.y * canvas_height
                    x2 = p2.x * canvas_width
                    y2 = p2.y * canvas_height
                    
                    dx = x2 - x1
                    dy = y2 - y1
                    total_length += (dx**2 + dy**2)**0.5
                
                print(f"   - 總長度: {total_length:.2f} 像素")
        
        except Exception as e:
            print(f"❌ 處理筆劃完成回調時出錯: {e}")
            import traceback
            print(traceback.format_exc())

    def on_features_calculated(data):
        """特徵計算完成回調"""
        try:
            stroke_id = data.get('stroke_id', 'N/A')
            features = data.get('features', {})
            
            print(f"\n📊 特徵計算完成:")
            print(f"   - 筆劃 ID: {stroke_id}")
            
            if 'basic_statistics' in features:
                basic = features['basic_statistics']
                print(f"   - 點數: {basic.get('point_count', 'N/A')}")
                
                total_length = basic.get('total_length', 0)
                print(f"   - 總長度: {total_length:.2f} 像素")
                print(f"   - 持續時間: {basic.get('duration', 'N/A'):.3f}s")
        
        except Exception as e:
            print(f"❌ 處理特徵計算回調時出錯: {e}")
            import traceback
            print(traceback.format_exc())

    
    def on_error(data):
        print(f"\n❌ 錯誤: {data['error_type']}")
        print(f"   訊息: {data['message']}")
    
    ink_system.register_callback('on_stroke_completed', on_stroke_completed)
    ink_system.register_callback('on_features_calculated', on_features_calculated)
    ink_system.register_callback('on_error', on_error)
    
    # 啟動處理（使用外部輸入模式）
    print("\n🚀 啟動數據處理...")
    if not ink_system.start_processing(use_external_input=True):
        print("❌ 無法啟動處理")
        return

    print("✅ 處理已啟動（外部輸入模式）")

    
    # ✅ 創建 GUI
    app = QApplication(sys.argv)
    canvas = WacomDrawingCanvas(ink_system, config)
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
