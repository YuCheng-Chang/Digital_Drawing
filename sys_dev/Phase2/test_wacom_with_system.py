# test_wacom_with_system.py
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QHBoxLayout, QVBoxLayout
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QPen, QColor, QTabletEvent
import sys
import time
from datetime import datetime
import logging
from InkProcessingSystemMainController import InkProcessingSystem
from Config import ProcessingConfig
from DigitalInkDataStructure import ToolType, StrokeMetadata 
from EraserTool import EraserTool
import os

class WacomDrawingCanvas(QWidget):
    def __init__(self, ink_system, config: ProcessingConfig):
        super().__init__()
        self.ink_system = ink_system
        self.config = config
        
        # 基本屬性
        self.current_stroke_points = []
        self.all_strokes = []  # ← 這個會被修改為字典格式
        self.stroke_count = 0
        self.total_points = 0
        self.logger = logging.getLogger('WacomDrawingCanvas')
        
        # ✅✅✅ 狀態追蹤
        self.last_point_data = None
        self.pen_is_in_canvas = False
        self.pen_is_touching = False
        self.current_pressure = 0.0
        
        # 🆕🆕🆕 橡皮擦相關
        self.current_tool = ToolType.PEN  # 當前工具
        self.eraser_tool = EraserTool(radius=20.0)  # 橡皮擦工具
        self.current_eraser_points = []  # 當前橡皮擦軌跡
        self.next_stroke_id = 0  # 筆劃 ID 計數器
        
        # 畫布設置
        canvas_width = config.canvas_width
        canvas_height = config.canvas_height
        
        # 🆕🆕🆕 修改窗口佈局（添加工具欄）
        self.setWindowTitle("Wacom 繪圖測試")
        self.setGeometry(100, 100, canvas_width, canvas_height + 50)  # ← 增加高度容納工具欄
        self.setMouseTracking(True)
        
        # 🆕🆕🆕 設置工具欄
        self._setup_toolbar()
        
        # LSL 整合（保持不變）
        from LSLIntegration import LSLIntegration, LSLStreamConfig
        
        lsl_config = LSLStreamConfig(
            device_manufacturer="Wacom",
            device_model="Wacom One 12",
            normalize_coordinates=False,
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

        self.ink_system.set_time_source(self.lsl.stream_manager.get_stream_time)
        self.logger.info("✅ 墨水系統時間源已設置為 LSL 時間")

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
        try:
            # ✅✅✅ 關鍵修復：使用 all_strokes 的長度作為實際的 stroke_id
            actual_stroke_id = len(self.all_strokes)
            stroke_points = stroke_data['points']
            
            self.logger.info(f"✅ Stroke completed: original_id={stroke_data['stroke_id']}, actual_id={actual_stroke_id}")
            
            canvas_width = self.config.canvas_width
            canvas_height = self.config.canvas_height
            
            pixel_points = [
                (
                    p.x * canvas_width, 
                    p.y * canvas_height,
                    p.pressure
                )
                for p in stroke_points
            ]
            
            # 創建元數據（使用實際的 stroke_id）
            metadata = StrokeMetadata(
                stroke_id=actual_stroke_id,  # ← 使用實際 ID
                tool_type=ToolType.PEN,
                timestamp_start=stroke_data['start_time'],
                timestamp_end=stroke_data['end_time'],
                is_deleted=False,
                deleted_by=None,
                deleted_at=None
            )
            
            # 添加到 all_strokes
            self.all_strokes.append({
                'stroke_id': actual_stroke_id,  # ← 使用實際 ID
                'tool_type': ToolType.PEN,
                'points': pixel_points,
                'metadata': metadata,
                'is_deleted': False
            })
            
            self.logger.info(f"📝 筆劃已保存: stroke_id={actual_stroke_id}, points={len(pixel_points)}")
            
            # ✅✅✅ 立即重繪畫布
            self.update()
            
        except Exception as e:
            self.logger.error(f"❌ 處理筆劃完成回調時出錯: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    
    def _setup_toolbar(self):
        """設置工具欄"""
        # 創建工具欄佈局
        toolbar_layout = QHBoxLayout()
        
        # 🖊️ 筆工具按鈕
        self.pen_button = QPushButton("🖊️ 筆")
        self.pen_button.setFixedSize(100, 40)
        self.pen_button.setStyleSheet("background-color: lightblue;")  # 預設選中
        self.pen_button.clicked.connect(lambda: self.switch_tool(ToolType.PEN))
        toolbar_layout.addWidget(self.pen_button)
        
        # 🧹 橡皮擦按鈕
        self.eraser_button = QPushButton("🧹 橡皮擦")
        self.eraser_button.setFixedSize(100, 40)
        self.eraser_button.clicked.connect(lambda: self.switch_tool(ToolType.ERASER))
        toolbar_layout.addWidget(self.eraser_button)
        
        # 🗑️ 清空按鈕
        clear_button = QPushButton("🗑️ 清空")
        clear_button.setFixedSize(100, 40)
        clear_button.clicked.connect(self.clear_canvas)
        toolbar_layout.addWidget(clear_button)
        
        
        # 添加彈性空間
        toolbar_layout.addStretch()
        
        # 創建工具欄容器
        toolbar_widget = QWidget()
        toolbar_widget.setLayout(toolbar_layout)
        toolbar_widget.setFixedHeight(50)
        
        # 創建主佈局
        main_layout = QVBoxLayout()
        main_layout.addWidget(toolbar_widget)
        main_layout.addStretch()  # 畫布區域
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.setLayout(main_layout)
    
    def switch_tool(self, tool_type: ToolType):
        """切換工具（添加切換事件記錄）"""
        try:
            # 記錄工具切換前的狀態
            from_tool = self.current_tool.value
            to_tool = tool_type.value
            
            self.logger.info(f"🔄 準備切換工具: {from_tool} → {to_tool}")
            
            # 🆕🆕🆕 關鍵修復：切換工具前強制完成當前筆劃
            if self.current_tool == ToolType.PEN and tool_type != ToolType.PEN:
                # 從筆切換到其他工具
                if self.pen_is_touching and self.current_stroke_points:
                    self.logger.info("🔄 切換工具前強制完成當前筆劃")
                    
                    if self.last_point_data is not None:
                        # 發送終點（壓力=0）
                        final_point = self.last_point_data.copy()
                        final_point['pressure'] = 0.0
                        final_point['timestamp'] = self.lsl.stream_manager.get_stream_time()
                        
                        self.ink_system.process_raw_point(final_point)
                        
                        # 等待處理完成
                        import time
                        time.sleep(0.05)
            
            # 🆕🆕🆕 記錄工具切換事件
            self.lsl.mark_tool_switch(from_tool, to_tool)
            
            # 清理所有狀態
            self.current_stroke_points = []
            self.current_eraser_points = []
            self.last_point_data = None
            self.pen_is_touching = False
            self.current_pressure = 0.0
            
            # 清理 PointProcessor 的歷史緩存
            if hasattr(self.ink_system, 'point_processor'):
                self.ink_system.point_processor.clear_history()
            
            # 強制重置 StrokeDetector 狀態
            if hasattr(self.ink_system, 'stroke_detector'):
                from StrokeDetector import StrokeState
                self.ink_system.stroke_detector.current_state = StrokeState.IDLE
                self.ink_system.stroke_detector.current_stroke_points = []
                self.logger.info("🔄 StrokeDetector 狀態已重置為 IDLE")
            
            # 切換工具
            self.current_tool = tool_type
            
            if tool_type == ToolType.PEN:
                self.pen_button.setStyleSheet("background-color: lightblue;")
                self.eraser_button.setStyleSheet("")
                self.logger.info("✅ 切換到筆工具")
            else:
                self.eraser_button.setStyleSheet("background-color: lightblue;")
                self.pen_button.setStyleSheet("")
                self.logger.info("✅ 切換到橡皮擦")
            
        except Exception as e:
            self.logger.error(f"❌ 切換工具失敗: {e}")
            import traceback
            self.logger.error(traceback.format_exc())


    
    def _handle_pen_input(self, x_pixel, y_pixel, x_normalized, y_normalized, current_pressure, event):
        """處理筆輸入"""
        try:
            if current_pressure > 0:
                point_data = {
                    'x': x_normalized,
                    'y': y_normalized,
                    'pressure': current_pressure,
                    'timestamp': self.lsl.stream_manager.get_stream_time(),
                    'tilt_x': event.xTilt(),
                    'tilt_y': event.yTilt()
                }
                
                if not self.pen_is_touching:
                    self.logger.info(
                        f"🎨 筆劃開始（第一個點）: "
                        f"像素=({x_pixel:.1f}, {y_pixel:.1f}), "
                        f"歸一化=({x_normalized:.3f}, {y_normalized:.3f}), "
                        f"pressure={current_pressure:.3f}"
                    )
                    self.pen_is_touching = True
                
                self.last_point_data = point_data
                self.ink_system.process_raw_point(point_data)
                
                # 🔧 關鍵修改：y_pixel 已經是調整後的座標，直接使用
                self.current_stroke_points.append((x_pixel, y_pixel, current_pressure))
                
                self.total_points += 1
            
            else:  # pressure = 0
                if self.pen_is_touching and self.current_stroke_points:
                    self.logger.info(
                        f"🔚 筆離開屏幕（壓力=0），筆劃結束 "
                        f"at 像素=({x_pixel:.1f}, {y_pixel:.1f}), "
                        f"歸一化=({x_normalized:.3f}, {y_normalized:.3f})"
                    )
                    
                    point_data = {
                        'x': x_normalized,
                        'y': y_normalized,
                        'pressure': 0.0,
                        'timestamp': self.lsl.stream_manager.get_stream_time(),
                        'tilt_x': event.xTilt(),
                        'tilt_y': event.yTilt()
                    }
                    self.ink_system.process_raw_point(point_data)
                    
                    self.current_stroke_points = []
                    self.stroke_count += 1
                    
                    self.pen_is_touching = False
                    self.current_pressure = 0.0
                    self.last_point_data = None
        
        except Exception as e:
            self.logger.error(f"❌ 處理筆輸入失敗: {e}")


    
    def _handle_eraser_input(self, x_pixel, y_pixel, current_pressure, event):
        """處理橡皮擦輸入"""
        try:
            # ✅✅✅ 關鍵修改：不再減去工具欄高度（已在 tabletEvent 中處理）
            # toolbar_height = 50
            # adjusted_y = y_pixel - toolbar_height  # ← 移除這行
            
            if current_pressure > 0:
                # ✅ 直接使用傳入的 y_pixel（已經是調整後的座標）
                self.current_eraser_points.append((x_pixel, y_pixel))
                
                # 🆕🆕🆕 初始化被刪除的筆劃 ID 集合
                if not hasattr(self, 'current_deleted_stroke_ids'):
                    self.current_deleted_stroke_ids = set()
                
                # 即時檢測碰撞並標記刪除
                eraser_point = (x_pixel, y_pixel)  # ← 直接使用 y_pixel
                for stroke in self.all_strokes:
                    if stroke['is_deleted']:
                        continue
                    
                    if self.eraser_tool.check_collision(eraser_point, stroke['points']):
                        stroke['is_deleted'] = True
                        stroke['metadata'].is_deleted = True
                        self.current_deleted_stroke_ids.add(stroke['stroke_id'])
                        self.logger.info(f"🗑️ 刪除筆劃: {stroke['stroke_id']}")
                
                if not self.pen_is_touching:
                    self.logger.info("🧹 橡皮擦筆劃開始")
                    self.pen_is_touching = True
            
            else:  # pressure = 0
                if self.pen_is_touching and self.current_eraser_points:
                    self.logger.info("🧹 橡皮擦筆劃結束")
                    
                    # 🆕🆕🆕 獲取被刪除的筆劃 ID
                    deleted_stroke_ids = list(getattr(self, 'current_deleted_stroke_ids', set()))
                    
                    # 🆕🆕🆕 記錄到 LSL（即使沒有通過 EraserTool）
                    if deleted_stroke_ids:
                        timestamp = self.lsl.stream_manager.get_stream_time()
                        eraser_id = len(self.eraser_tool.eraser_history)
                        
                        self.lsl.mark_eraser_stroke(
                            eraser_id=eraser_id,
                            deleted_stroke_ids=deleted_stroke_ids,
                            timestamp=timestamp
                        )
                        
                        self.logger.info(
                            f"✅ 橡皮擦事件已記錄到 LSL: eraser_id={eraser_id}, "
                            f"deleted={len(deleted_stroke_ids)} strokes"
                        )
                    else:
                        self.logger.info("⏭️ 沒有刪除任何筆劃，跳過 LSL 記錄")
                    
                    # 清空記錄
                    self.current_eraser_points = []
                    if hasattr(self, 'current_deleted_stroke_ids'):
                        self.current_deleted_stroke_ids = set()
                    self.pen_is_touching = False
                    self.current_pressure = 0.0
                    
                    # 🆕🆕🆕 關鍵修復：清空 last_point_data
                    self.last_point_data = None
                    
                    # 🆕🆕🆕 清理 PointProcessor 歷史
                    if hasattr(self.ink_system, 'point_processor'):
                        self.ink_system.point_processor.clear_history()
            
        except Exception as e:
            self.logger.error(f"❌ 處理橡皮擦輸入失敗: {e}")
            import traceback
            self.logger.error(traceback.format_exc())



    def clear_canvas(self):
        """清空畫布"""
        try:
            self.logger.info("🗑️ 準備清空畫布...")
            
            # ✅✅✅ 關鍵修復：清理所有狀態（類似 switch_tool）
            
            # 1. 清空畫布數據
            self.all_strokes = []
            self.current_stroke_points = []
            self.current_eraser_points = []
            self.stroke_count = 0
            self.total_points = 0
            self.next_stroke_id = 0
            self.eraser_tool.clear_history()
            
            # 2. 🆕🆕🆕 清空所有狀態標記
            self.last_point_data = None
            self.pen_is_touching = False
            self.current_pressure = 0.0
            
            # 3. 🆕🆕🆕 清理 PointProcessor 的歷史緩存
            if hasattr(self.ink_system, 'point_processor'):
                self.ink_system.point_processor.clear_history()
                self.logger.info("🧹 已清空 PointProcessor 歷史緩存")
            
            # 4. 🆕🆕🆕 強制重置 StrokeDetector 狀態
            if hasattr(self.ink_system, 'stroke_detector'):
                from StrokeDetector import StrokeState
                self.ink_system.stroke_detector.current_state = StrokeState.IDLE
                self.ink_system.stroke_detector.current_stroke_points = []
                self.ink_system.stroke_detector.current_stroke_id = 0  # ← 🆕 重置 stroke_id
                self.logger.info("🧹 已重置 StrokeDetector 狀態為 IDLE，stroke_id=0")
            
            # 🆕🆕🆕 5. 清空 LSL 記錄的墨水點和標記
            if hasattr(self, 'lsl') and self.lsl is not None:
                # 清空 LSL 記錄器的緩衝區
                self.lsl.data_recorder.ink_samples.clear()
                self.lsl.data_recorder.markers.clear()
                
                # 重置 stroke_id
                self.lsl.current_stroke_id = 0
                self.lsl._stroke_has_started = False
                
                self.logger.info("🧹 已清空 LSL 記錄緩衝區，stroke_id 重置為 0")
            
            # 🆕🆕🆕 6. 記錄清空事件（作為新的 recording_start）
            if hasattr(self, 'lsl') and self.lsl is not None:
                timestamp = self.lsl.stream_manager.get_stream_time()
                
                # ✅✅✅ 關鍵修復：記錄為 recording_start 事件
                self.lsl.stream_manager.push_marker("recording_start", timestamp)
                self.lsl.data_recorder.record_marker(timestamp, "recording_start")
                
                self.logger.info("✅ 清空畫布事件已記錄為 recording_start")
            
            # 7. 重繪畫布
            self.update()
            
            self.logger.info("✅ 畫布已清空，所有狀態已重置")
            
        except Exception as e:
            self.logger.error(f"❌ 清空畫布失敗: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    
    def export_canvas_image(self, output_path: str):
        """將畫布匯出為 PNG 圖片"""
        try:
            from PyQt5.QtGui import QPixmap
            
            canvas_width = self.config.canvas_width
            canvas_height = self.config.canvas_height
            
            pixmap = QPixmap(canvas_width, canvas_height)
            pixmap.fill(Qt.white)
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # ✅✅✅ 繪製筆劃
            pen = QPen(QColor(0, 0, 0), 2)
            painter.setPen(pen)
            
            for stroke in self.all_strokes:
                if stroke.get('is_deleted', False):
                    continue
                
                points = stroke['points']
                for i in range(len(points) - 1):
                    x1, y1, p1 = points[i]
                    x2, y2, p2 = points[i + 1]
                    
                    # 🔧🔧🔧 關鍵修改:直接使用像素座標(已經減去工具欄高度)
                    width = 1 + p1 * 5
                    pen.setWidthF(width)
                    painter.setPen(pen)
                    painter.drawLine(int(x1), int(y1), int(x2), int(y2))
            
            painter.end()
            
            success = pixmap.save(output_path, 'PNG')
            
            if success:
                self.logger.info(f"✅ 畫布已匯出: {output_path}")
                file_size = os.path.getsize(output_path) / 1024
                self.logger.info(f"   - 檔案大小: {file_size:.2f} KB")
                return True
            else:
                self.logger.error(f"❌ 保存失敗: {output_path}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ 匯出畫布時出錯: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False


    def closeEvent(self, event):
        """視窗關閉時的處理"""
        try:
            self.logger.info("🔚 Canvas closing...")
            
            from StrokeDetector import StrokeState
            
            is_stroke_active = (
                hasattr(self.ink_system, 'stroke_detector') and 
                self.ink_system.stroke_detector.current_state in [StrokeState.ACTIVE, StrokeState.STARTING]
            )
            
            has_unfinished_stroke = (
                self.current_stroke_points and
                self.last_point_data is not None and
                self.pen_is_touching and
                self.current_pressure > 0
            )
            
            if is_stroke_active and has_unfinished_stroke:
                self.logger.info("🔚 關閉視窗前強制完成當前筆劃")
                self.logger.info(f"   - 當前筆劃點數: {len(self.current_stroke_points)}")
                self.logger.info(f"   - 當前壓力: {self.current_pressure:.3f}")
                
                # ✅ 使用已經歸一化的座標
                final_point = self.last_point_data.copy()
                final_point['pressure'] = 0.0
                final_point['timestamp'] = self.lsl.stream_manager.get_stream_time()
                
                self.ink_system.process_raw_point(final_point)
                time.sleep(0.1)
            else:
                reasons = []
                if not is_stroke_active:
                    reasons.append("系統無活動筆劃")
                if not self.current_stroke_points:
                    reasons.append("沒有未完成的點")
                if self.last_point_data is None:
                    reasons.append("無最後點數據")
                if not self.pen_is_touching:
                    reasons.append("筆未接觸屏幕")
                if self.current_pressure <= 0:
                    reasons.append("壓力為0")
                
                self.logger.info(f"🔚 跳過強制完成筆劃: {', '.join(reasons)}")
            
            # 2. 處理已完成但未處理的筆劃
            if hasattr(self.ink_system, 'stroke_detector'):
                completed_strokes = self.ink_system.stroke_detector.get_completed_strokes()
                
                if completed_strokes:
                    self.logger.info(f"🔍 關閉前發現 {len(completed_strokes)} 個已完成但未處理的筆劃")
                    
                    for stroke_data in completed_strokes:
                        stroke_id = stroke_data['stroke_id']
                        stroke_points = stroke_data['points']
                        
                        self.ink_system.stroke_buffer.append(stroke_data)
                        self.ink_system.processing_stats['total_strokes'] += 1
                        
                        self.ink_system._trigger_callback('on_stroke_completed', {
                            'stroke_id': stroke_id,
                            'points': stroke_points,
                            'num_points': len(stroke_points),
                            'start_time': stroke_data['start_time'],
                            'end_time': stroke_data['end_time'],
                            'timestamp': self.lsl.stream_manager.get_stream_time()
                        })
                    
                    time.sleep(0.2)
                    self.logger.info("✅ 特徵計算處理完成")
            
            # 🆕🆕🆕 3. 匯出畫布圖片（在停止 LSL 之前）
            if hasattr(self, 'lsl') and self.lsl is not None:
                try:
                    # 獲取輸出目錄
                    import os
                    output_dir = os.path.join(self.lsl.data_recorder.output_dir, self.lsl.data_recorder.session_id)
                    
                    # 確保目錄存在
                    os.makedirs(output_dir, exist_ok=True)
                    
                    # 生成檔案名
                    canvas_image_path = os.path.join(output_dir, "canvas_drawing.png")
                    
                    # 匯出畫布
                    self.logger.info("🎨 匯出畫布圖片...")
                    if self.export_canvas_image(canvas_image_path):
                        self.logger.info(f"✅ 畫布已保存: {canvas_image_path}")
                    else:
                        self.logger.warning("⚠️ 畫布匯出失敗")
                        
                except Exception as e:
                    self.logger.error(f"❌ 匯出畫布時出錯: {e}")
                    import traceback
                    self.logger.error(traceback.format_exc())
            
            # 4. 停止 LSL 並儲存數據
            if hasattr(self, 'lsl') and self.lsl is not None:
                self.logger.info("🔚 Stopping LSL and saving data...")
                try:
                    saved_files = self.lsl.stop()
                    self.logger.info(f"✅ LSL data saved:")
                    for key, path in saved_files.items():
                        self.logger.info(f"   - {key}: {path}")
                except Exception as e:
                    self.logger.error(f"❌ Error stopping LSL: {e}")
            
            # 5. 停止墨水處理系統
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
                current_time = self.lsl.stream_manager.get_stream_time()
                time_since_last_point = current_time - self.last_point_data['timestamp']
                
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
        """
        try:
            self.logger.info(f"🚪 筆離開畫布區域 (當前壓力: {self.current_pressure:.3f})")
            
            # 更新狀態
            self.pen_is_in_canvas = False
            
            from StrokeDetector import StrokeState
            
            is_stroke_active = (
                hasattr(self.ink_system, 'stroke_detector') and
                self.ink_system.stroke_detector.current_state in [StrokeState.ACTIVE, StrokeState.STARTING]
            )
            
            if (self.pen_is_touching and 
                self.current_pressure > 0 and 
                self.current_stroke_points and
                is_stroke_active):
                
                self.logger.info("🔚 筆接觸屏幕時移出畫布，使用最後一個點作為筆劃終點")
                
                if self.last_point_data is not None:
                    # ✅ 使用已經歸一化的座標
                    final_point = self.last_point_data.copy()
                    final_point['pressure'] = 0.0
                    final_point['timestamp'] = self.lsl.stream_manager.get_stream_time()
                    
                    self.logger.info(
                        f"🔚 發送終點: 歸一化=({final_point['x']:.3f}, {final_point['y']:.3f}), "
                        f"pressure=0 (原壓力: {self.current_pressure:.3f})"
                    )
                    
                    self.ink_system.process_raw_point(final_point)
                    
                    self.all_strokes.append(self.current_stroke_points.copy())
                    self.current_stroke_points = []
                    self.stroke_count += 1
                    
                    self.pen_is_touching = False
                    self.current_pressure = 0.0
                    self.last_point_data = None
                    
                    self.update()
            else:
                reason = []
                if not self.pen_is_touching:
                    reason.append("筆未接觸屏幕")
                if self.current_pressure <= 0:
                    reason.append("壓力為0")
                if not self.current_stroke_points:
                    reason.append("沒有未完成的筆劃")
                if not is_stroke_active:
                    reason.append("系統無活動筆劃")
                
                self.logger.debug(f"⏭️ 跳過處理: {', '.join(reason)}")
            
            event.accept()
            
        except Exception as e:
            self.logger.error(f"❌ leaveEvent 處理失敗: {e}")
            import traceback
            self.logger.error(traceback.format_exc())



        
    def tabletEvent(self, event):
        """接收 Wacom 輸入事件（支持橡皮擦）"""
        try:
            current_pressure = event.pressure()
            self.current_pressure = current_pressure
            
            pos = event.pos()
            is_in_bounds = self.rect().contains(pos)
            
            if not is_in_bounds:
                self.logger.debug(f"⏭️ 點在畫布外，跳過處理: ({pos.x()}, {pos.y()})")
                event.accept()
                return
            
            # 獲取像素座標
            x_pixel = event.x()
            y_pixel = event.y()
            
            # 🔧 關鍵修改：先減去工具欄高度
            toolbar_height = 50
            canvas_width = self.config.canvas_width
            canvas_height = self.config.canvas_height
            
            # 🆕🆕🆕 檢測是否在工具欄區域
            if y_pixel < toolbar_height:
                self.logger.debug(f"⏭️ 點在工具欄區域，跳過墨水處理: ({x_pixel}, {y_pixel})")
                event.accept()
                return  # ← 直接返回，不處理墨水
            
            adjusted_y = y_pixel - toolbar_height
            
            # 基於調整後的座標進行歸一化
            x_normalized = x_pixel / canvas_width
            y_normalized = adjusted_y / canvas_height
            
            # ✅✅✅ 關鍵修改：兩個工具都傳入調整後的座標
            if self.current_tool == ToolType.PEN:
                self._handle_pen_input(x_pixel, adjusted_y, x_normalized, y_normalized, current_pressure, event)
            elif self.current_tool == ToolType.ERASER:
                self._handle_eraser_input(x_pixel, adjusted_y, current_pressure, event)
            
            self.update()
            event.accept()
            
        except Exception as e:
            self.logger.error(f"❌ tabletEvent 處理失敗: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            event.accept()

    def paintEvent(self, event):
        """繪製筆劃(支持橡皮擦)"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 🆕🆕🆕 計算工具欄偏移(避開工具欄)
        toolbar_height = 50
        painter.translate(0, toolbar_height)  # ← 向下平移 50 像素
        
        # 繪製未刪除的筆劃(黑色)
        pen = QPen(QColor(0, 0, 0), 2)
        painter.setPen(pen)
        
        for stroke in self.all_strokes:
            if stroke.get('is_deleted', False):
                continue  # 跳過已刪除的筆劃
            
            points = stroke['points']
            for i in range(len(points) - 1):
                x1, y1, p1 = points[i]
                x2, y2, p2 = points[i + 1]
                
                # 🔧🔧🔧 關鍵修改:不需要再減去工具欄高度(已經在保存時減去)
                width = 1 + p1 * 5
                pen.setWidthF(width)
                painter.setPen(pen)
                painter.drawLine(
                    int(x1), int(y1),  # ← 直接使用保存的座標
                    int(x2), int(y2)
                )
        
        # 繪製當前筆劃（藍色）
        if self.current_tool == ToolType.PEN and self.current_stroke_points:
            pen = QPen(QColor(0, 100, 255), 2)
            painter.setPen(pen)
            
            for i in range(len(self.current_stroke_points) - 1):
                x1, y1, p1 = self.current_stroke_points[i]
                x2, y2, p2 = self.current_stroke_points[i + 1]
                width = 1 + p1 * 5
                pen.setWidthF(width)
                painter.setPen(pen)
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        
        # 🆕🆕🆕 繪製當前橡皮擦軌跡（半透明紅色圓圈）
        if self.current_tool == ToolType.ERASER and self.current_eraser_points:
            pen = QPen(QColor(255, 0, 0, 100), 2)
            painter.setPen(pen)
            painter.setBrush(QColor(255, 0, 0, 50))
            
            for x, y in self.current_eraser_points:
                painter.drawEllipse(
                    int(x - self.eraser_tool.radius),
                    int(y - self.eraser_tool.radius),
                    int(self.eraser_tool.radius * 2),
                    int(self.eraser_tool.radius * 2)
                )
        
        # 統計資訊顯示（調整位置）
        painter.setPen(QPen(QColor(100, 100, 100)))
        
        if self.last_point_data:
            x_pixel = self.last_point_data['x'] * self.width()
            y_pixel = self.last_point_data['y'] * self.height()
            stats_text = (
                f"工具: {self.current_tool.value} | "
                f"筆劃數: {len([s for s in self.all_strokes if not s['is_deleted']])} | "
                f"總點數: {self.total_points} | "
                f"壓力: {self.current_pressure:.3f} | "
                f"位置: ({x_pixel:.0f}, {y_pixel:.0f})"
            )
        else:
            stats_text = (
                f"工具: {self.current_tool.value} | "
                f"筆劃數: {len([s for s in self.all_strokes if not s['is_deleted']])} | "
                f"總點數: {self.total_points} | "
                f"壓力: {self.current_pressure:.3f} | 位置: N/A"
            )
        
        painter.drawText(10, 20, stats_text)  # ← Y 座標改回 20（因為已經平移了 50px）


        
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

    
    # ✅ 修改後
    # ✅ 創建 GUI
    app = QApplication(sys.argv)
    canvas = WacomDrawingCanvas(ink_system, config)

    # 🆕🆕🆕 注意：時間源已在 WacomDrawingCanvas.__init__() 中設置
    # 這裡不需要額外操作，只是確認一下
    print("✅ LSL 時間源已設置")

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
