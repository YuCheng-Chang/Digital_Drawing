# main.py
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QHBoxLayout, QVBoxLayout, QMessageBox, QDesktopWidget
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
from SubjectInfoDialog import SubjectInfoDialog, DrawingTypeDialog

# 配置日誌
logging.basicConfig(
  level=logging.DEBUG,
  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class WacomDrawingCanvas(QWidget):
    def __init__(self, ink_system, config: ProcessingConfig):
        super().__init__()
        self.ink_system = ink_system
        self.config = config
        
        # 🔧 修復：先初始化 logger
        self.logger = logging.getLogger('WacomDrawingCanvas')
        
        # 🆕 獲取螢幕資訊並判斷模式
        self.primary_screen, self.secondary_screen, self.is_extended_mode = self._detect_screens()
        
        # 🆕 根據螢幕模式更新配置
        self._setup_screen_size()
        
        # 受試者和繪畫資訊
        self.subject_info = None
        self.current_drawing_info = None
        self.drawing_counter = 1
        
        # 基本屬性
        self.current_stroke_points = []
        self.all_strokes = []
        self.stroke_count = 0
        self.total_points = 0
        
        # 狀態追蹤
        self.last_point_data = None
        self.pen_is_in_canvas = False
        self.pen_is_touching = False
        self.current_pressure = 0.0
        
        # 橡皮擦相關
        self.current_tool = ToolType.PEN
        self.eraser_tool = EraserTool(radius=10.0)
        self.current_eraser_points = []
        self.next_stroke_id = 0
        
        # 🆕 首先獲取受試者資訊
        if not self.get_subject_info():
            sys.exit()
        
        # 🆕 獲取第一次繪畫類型
        if not self.get_drawing_type():
            sys.exit()
        
        # 🆕 設置視窗屬性
        self._setup_window()
        
        # 🆕 更新視窗標題
        self._update_window_title()
        
        # 設置工具欄
        self._setup_toolbar()
        
        # 初始化LSL
        self._initialize_lsl()
        
        # 註冊回調
        self.ink_system.register_callback(
            'on_point_processed',
            self._on_point_processed_callback
        )
        self.ink_system.register_callback(
            'on_stroke_completed',
            self._on_stroke_completed_callback
        )

    def _detect_screens(self):
        """🆕 檢測螢幕配置並判斷是否為延伸模式"""
        desktop = QDesktopWidget()
        screen_count = desktop.screenCount()
        
        self.logger.info("=" * 60)
        self.logger.info("🖥️ 螢幕配置檢測")
        self.logger.info("=" * 60)
        self.logger.info(f"檢測到 {screen_count} 個螢幕")
        
        # 獲取主螢幕（索引 0）
        primary_screen = desktop.screenGeometry(0)
        self.logger.info(f"主螢幕 (索引 0): {primary_screen.width()} x {primary_screen.height()} "
                        f"at ({primary_screen.x()}, {primary_screen.y()})")
        
        # 判斷是否為延伸螢幕模式
        is_extended_mode = False
        secondary_screen = primary_screen  # 預設使用主螢幕
        
        if screen_count > 1:
            secondary_screen = desktop.screenGeometry(1)
            self.logger.info(f"副螢幕 (索引 1): {secondary_screen.width()} x {secondary_screen.height()} "
                           f"at ({secondary_screen.x()}, {secondary_screen.y()})")
            
            # 🔍 判斷是否為延伸模式：檢查兩個螢幕的 X 座標是否不同
            if primary_screen.x() != secondary_screen.x():
                is_extended_mode = True
                self.logger.info("✅ 偵測到延伸螢幕模式：對話框在主螢幕，畫布在副螢幕")
            else:
                self.logger.warning("⚠️ 偵測到多螢幕但非延伸模式（可能是鏡像模式），將使用單螢幕模式")
                secondary_screen = primary_screen
        else:
            self.logger.warning("⚠️ 只檢測到一個螢幕，將使用單螢幕模式")
        
        self.logger.info("=" * 60)
        
        return primary_screen, secondary_screen, is_extended_mode
    
    def _setup_screen_size(self):
        """🆕 根據螢幕模式設置畫布尺寸"""
        toolbar_height = 50
        
        if self.is_extended_mode:
            # 延伸模式：使用副螢幕尺寸
            canvas_width = self.secondary_screen.width()
            canvas_height = self.secondary_screen.height() - toolbar_height
            self.logger.info(f"📐 畫布尺寸（延伸模式 - 副螢幕）: {canvas_width} x {canvas_height}")
        else:
            # 單螢幕模式：使用主螢幕可用區域
            desktop = QDesktopWidget()
            screen_rect = desktop.availableGeometry()
            canvas_width = screen_rect.width()
            canvas_height = screen_rect.height() - toolbar_height
            self.logger.info(f"📐 畫布尺寸（單螢幕模式）: {canvas_width} x {canvas_height}")
        
        # 更新配置
        self.config.canvas_width = canvas_width
        self.config.canvas_height = canvas_height
    
    def _setup_window(self):
        """🆕 根據螢幕模式設置視窗屬性"""
        # 設置視窗標題
        self.setWindowTitle("Wacom 繪圖測試")
        
        # 🔧 禁止調整視窗大小
        self.setFixedSize(self.config.canvas_width, self.config.canvas_height + 50)
        
        if self.is_extended_mode:
            # 延伸模式：移動視窗到副螢幕左上角
            self.move(self.secondary_screen.x(), self.secondary_screen.y())
            self.logger.info(f"✅ 畫布視窗已設置在副螢幕: 位置=({self.secondary_screen.x()}, {self.secondary_screen.y()})")
        else:
            # 單螢幕模式：移動視窗到主螢幕左上角
            self.move(0, 0)
            self.logger.info("✅ 畫布視窗已設置在主螢幕: 位置=(0, 0)")
        
        # 🔧 設置視窗標誌
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        
        # 設置滑鼠追蹤
        self.setMouseTracking(True)
    
    def get_subject_info(self):
        """獲取受試者資訊（根據模式決定對話框位置）"""
        dialog = SubjectInfoDialog(self)
        
        if self.is_extended_mode:
            # 🆕 延伸模式：將對話框移動到主螢幕中央
            dialog_width = dialog.width()
            dialog_height = dialog.height()
            x = self.primary_screen.x() + (self.primary_screen.width() - dialog_width) // 2
            y = self.primary_screen.y() + (self.primary_screen.height() - dialog_height) // 2
            dialog.move(x, y)
            self.logger.info(f"📋 受試者資訊對話框顯示在主螢幕: ({x}, {y})")
        else:
            # 單螢幕模式：使用預設位置（螢幕中央）
            self.logger.info("📋 受試者資訊對話框顯示在螢幕中央（單螢幕模式）")
        
        if dialog.exec_() == dialog.Accepted:
            self.subject_info = dialog.subject_info
            self.logger.info(f"✅ 受試者資訊: {self.subject_info}")
            return True
        return False
    
    def _update_window_title(self):
        """更新視窗標題以顯示當前繪畫類型"""
        if self.current_drawing_info:
            drawing_type = self.current_drawing_info.get('drawing_type', 'N/A')
            drawing_id = self.current_drawing_info.get('drawing_id', 'N/A')
            subject_id = self.subject_info.get('subject_id', 'N/A') if self.subject_info else 'N/A'
            
            title = f"Wacom 繪圖測試 - {subject_id} - 繪畫 #{drawing_id} ({drawing_type})"
            self.setWindowTitle(title)
            self.logger.info(f"📝 視窗標題已更新: {title}")
        else:
            self.setWindowTitle("Wacom 繪圖測試")
    
    def get_drawing_type(self):
        """獲取繪畫類型（根據模式決定對話框位置）"""
        dialog = DrawingTypeDialog(self.drawing_counter, self)
        
        if self.is_extended_mode:
            # 🆕 延伸模式：將對話框移動到主螢幕中央
            dialog_width = dialog.width()
            dialog_height = dialog.height()
            x = self.primary_screen.x() + (self.primary_screen.width() - dialog_width) // 2
            y = self.primary_screen.y() + (self.primary_screen.height() - dialog_height) // 2
            dialog.move(x, y)
            self.logger.info(f"🎨 繪畫類型對話框顯示在主螢幕: ({x}, {y})")
        else:
            # 單螢幕模式：使用預設位置（螢幕中央）
            self.logger.info("🎨 繪畫類型對話框顯示在螢幕中央（單螢幕模式）")
        
        if dialog.exec_() == dialog.Accepted:
            self.current_drawing_info = dialog.drawing_info
            self.logger.info(f"✅ 繪畫資訊: {self.current_drawing_info}")
            return True
        return False
    
    def _initialize_lsl(self):
        """初始化LSL整合（使用新目錄結構）"""
        from LSLIntegration import LSLIntegration, LSLStreamConfig
        
        canvas_width = self.config.canvas_width
        canvas_height = self.config.canvas_height
        
        lsl_config = LSLStreamConfig(
            device_manufacturer="Wacom",
            device_model="Wacom One 12",
            normalize_coordinates=False,
            screen_width=canvas_width,
            screen_height=canvas_height
        )
        
        # 🆕 使用新的目錄結構
        base_output_dir = "./wacom_recordings"
        subject_dir = os.path.join(base_output_dir, self.subject_info['folder_name'])
        drawing_dir = os.path.join(subject_dir, self.current_drawing_info['folder_name'])
        
        # 確保目錄存在
        os.makedirs(drawing_dir, exist_ok=True)
        
        self.lsl = LSLIntegration(
            stream_config=lsl_config,
            output_dir=drawing_dir
        )
        
        # 🆕 使用繪畫ID和類型作為session_id（格式：1_DAP）
        session_id = f"{self.current_drawing_info['drawing_id']}_{self.current_drawing_info['drawing_type']}"
        
        self.lsl.start(
            session_id=session_id,
            metadata={
                'subject_info': self.subject_info,
                'drawing_info': self.current_drawing_info,
                'experiment': 'wacom_drawing_test',
                'screen_resolution': f"{canvas_width}x{canvas_height}",
                'canvas_width': canvas_width,
                'canvas_height': canvas_height,
                'display_mode': 'extended' if self.is_extended_mode else 'single'  # 🆕 記錄顯示模式
            }
        )
        
        # 設置日誌到文件
        self._setup_logging_to_file(session_id, drawing_dir)
        
        self.ink_system.set_time_source(self.lsl.stream_manager.get_stream_time)
        self.logger.info("✅ 墨水系統時間源已設置為 LSL 時間")
    
    def start_new_drawing(self):
        """🆕 開始新繪畫（修改版：先顯示對話框，確認後才終止當前繪畫）"""
        try:
            self.logger.info("=" * 60)
            self.logger.info("🎨 準備開始新繪畫")
            self.logger.info("=" * 60)
            
            # 1. 先遞增繪畫計數器（用於對話框顯示）
            next_drawing_counter = self.drawing_counter + 1
            
            # 2. 先獲取新的繪畫類型（不終止當前繪畫）
            dialog = DrawingTypeDialog(next_drawing_counter, self)
            
            if self.is_extended_mode:
                # 延伸模式：將對話框移動到主螢幕中央
                dialog_width = dialog.width()
                dialog_height = dialog.height()
                x = self.primary_screen.x() + (self.primary_screen.width() - dialog_width) // 2
                y = self.primary_screen.y() + (self.primary_screen.height() - dialog_height) // 2
                dialog.move(x, y)
                self.logger.info(f"🎨 繪畫類型對話框顯示在主螢幕: ({x}, {y})")
            else:
                # 單螢幕模式：使用預設位置（螢幕中央）
                self.logger.info("🎨 繪畫類型對話框顯示在螢幕中央（單螢幕模式）")
            
            # 3. 只有當用戶點擊「確定」時才執行後續操作
            if dialog.exec_() != dialog.Accepted:
                self.logger.info("❌ 用戶取消新繪畫，繼續當前繪畫")
                return  # 用戶取消，直接返回，當前繪畫繼續
            
            # 4. 用戶確認，現在才開始終止當前繪畫
            self.logger.info("✅ 用戶確認新繪畫，開始終止當前繪畫")
            
            # 5. 完成當前繪畫的保存工作
            self._finish_current_drawing()
            
            # 6. 更新繪畫計數器和資訊
            self.drawing_counter = next_drawing_counter
            self.current_drawing_info = dialog.drawing_info
            self.logger.info(f"✅ 新繪畫資訊: {self.current_drawing_info}")
            
            # 7. 更新視窗標題
            self._update_window_title()
            
            # 8. 重置畫布狀態
            self._reset_canvas_state()
            
            # 9. 重新初始化LSL（新目錄）
            self._initialize_lsl()
            
            # 10. 重新設置墨水系統
            self._reset_ink_system()
            
            self.logger.info(f"✅ 新繪畫已開始 (繪畫編號: {self.drawing_counter})")
            
        except Exception as e:
            self.logger.error(f"❌ 開始新繪畫失敗: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            QMessageBox.critical(self, "錯誤", f"開始新繪畫失敗: {e}")

    
    def _setup_logging_to_file(self, session_id: str, output_dir: str):
        """設置日誌輸出到文件"""
        try:
            log_filename = os.path.join(output_dir, "system_log.txt")
            
            file_handler = logging.FileHandler(log_filename, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            
            root_logger = logging.getLogger()
            root_logger.addHandler(file_handler)
            
            self.logger.info(f"✅ 日誌已配置輸出到: {log_filename}")
            self.log_file_path = log_filename
            
        except Exception as e:
            self.logger.error(f"❌ 設置日誌文件失敗: {e}")

    
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
            # ✅✅✅ 使用 LSL 的 stroke_id（這是唯一的真相來源）
            stroke_id = stroke_data['stroke_id']
            stroke_points = stroke_data['points']
            
            self.logger.info(f"✅ Stroke completed: stroke_id={stroke_id}, points={len(stroke_points)}")
            
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
            
            # 創建元數據（使用 LSL 的 stroke_id）
            metadata = StrokeMetadata(
                stroke_id=stroke_id,
                tool_type=ToolType.PEN,
                timestamp_start=stroke_data['start_time'],
                timestamp_end=stroke_data['end_time'],
                is_deleted=False,
                deleted_by=None,
                deleted_at=None
            )
            
            # ✅✅✅ 添加到 all_strokes（使用 LSL 的 stroke_id）
            self.all_strokes.append({
                'stroke_id': stroke_id,
                'tool_type': ToolType.PEN,
                'points': pixel_points,
                'metadata': metadata,
                'is_deleted': False
            })
            
            self.logger.info(f"📝 筆劃已保存: stroke_id={stroke_id}, points={len(pixel_points)}")
            
            # ✅✅✅ 立即重繪畫布
            self.update()
            
        except Exception as e:
            self.logger.error(f"❌ 處理筆劃完成回調時出錯: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _setup_toolbar(self):
        """設置工具欄（修改版：只顯示圖示，懸停顯示提示）"""
        toolbar_layout = QHBoxLayout()
        
        # 筆工具按鈕
        self.pen_button = QPushButton("🖊️")
        self.pen_button.setFixedSize(60, 40)
        self.pen_button.setStyleSheet("background-color: lightblue; font-size: 20px;")
        self.pen_button.setToolTip("筆")
        self.pen_button.clicked.connect(lambda: self.switch_tool(ToolType.PEN))
        toolbar_layout.addWidget(self.pen_button)
        
        # 橡皮擦按鈕
        self.eraser_button = QPushButton("🧈")
        self.eraser_button.setFixedSize(60, 40)
        self.eraser_button.setStyleSheet("font-size: 20px;")
        self.eraser_button.setToolTip("橡皮擦")
        self.eraser_button.clicked.connect(lambda: self.switch_tool(ToolType.ERASER))
        toolbar_layout.addWidget(self.eraser_button)
        
        # 新繪畫按鈕
        self.new_drawing_button = QPushButton("🎨")
        self.new_drawing_button.setFixedSize(60, 40)
        self.new_drawing_button.setStyleSheet("background-color: lightgreen; font-size: 20px;")
        self.new_drawing_button.setToolTip("新繪畫")
        self.new_drawing_button.clicked.connect(self.start_new_drawing)
        toolbar_layout.addWidget(self.new_drawing_button)
        
        # 添加彈性空間
        toolbar_layout.addStretch()
        
        # 創建工具欄容器
        toolbar_widget = QWidget()
        toolbar_widget.setLayout(toolbar_layout)
        toolbar_widget.setFixedHeight(50)
        
        # 創建主佈局
        main_layout = QVBoxLayout()
        main_layout.addWidget(toolbar_widget)
        main_layout.addStretch()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.setLayout(main_layout)
      
    def _finish_current_drawing(self):
        """完成當前繪畫的保存工作"""
        try:
            # 1. 強制完成未完成的筆劃
            self._force_complete_current_stroke()
            
            # 2. 輸出統計資訊
            self._output_drawing_statistics()
            
            # 3. 匯出畫布圖片
            self._export_current_canvas()
            
            # 4. 停止並保存LSL數據
            if hasattr(self, 'lsl') and self.lsl is not None:
                self.logger.info("🔚 保存當前繪畫數據...")
                saved_files = self.lsl.stop()
                self.logger.info(f"✅ 當前繪畫數據已保存: {saved_files}")
                
        except Exception as e:
            self.logger.error(f"❌ 完成當前繪畫失敗: {e}")

    def _reset_canvas_state(self):
        """重置畫布狀態"""
        # 清空畫布數據
        self.all_strokes = []
        self.current_stroke_points = []
        self.current_eraser_points = []
        self.stroke_count = 0
        self.total_points = 0
        self.next_stroke_id = 0
        self.eraser_tool.clear_history()
        
        # 重置狀態標記
        self.last_point_data = None
        self.pen_is_touching = False
        self.current_pressure = 0.0
        
        # 重置工具為筆
        self.current_tool = ToolType.PEN
        self.pen_button.setStyleSheet("background-color: lightblue;")
        self.eraser_button.setStyleSheet("")
        
        # 重繪畫布
        self.update()
        
        self.logger.info("✅ 畫布狀態已重置")
        
    def _reset_ink_system(self):
        """重置墨水系統"""
        try:
            # 清理處理器歷史
            if hasattr(self.ink_system, 'point_processor'):
                self.ink_system.point_processor.clear_history()
            
            # 重置檢測器狀態
            if hasattr(self.ink_system, 'stroke_detector'):
                from StrokeDetector import StrokeState
                self.ink_system.stroke_detector.current_state = StrokeState.IDLE
                self.ink_system.stroke_detector.current_stroke_points = []
                self.ink_system.stroke_detector.current_stroke_id = 0
            
            # 重新設置時間源
            self.ink_system.set_time_source(self.lsl.stream_manager.get_stream_time)
            
            self.logger.info("✅ 墨水系統已重置")
            
        except Exception as e:
            self.logger.error(f"❌ 重置墨水系統失敗: {e}")
            
    def _force_complete_current_stroke(self):
        """強制完成當前筆劃"""
        try:
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
                self.logger.info("🔚 強制完成當前筆劃")
                
                final_point = self.last_point_data.copy()
                final_point['pressure'] = 0.0
                final_point['timestamp'] = self.lsl.stream_manager.get_stream_time()
                
                self.ink_system.process_raw_point(final_point)
                time.sleep(0.1)
                
        except Exception as e:
            self.logger.error(f"❌ 強制完成筆劃失敗: {e}")
            
    def _output_drawing_statistics(self):
        """輸出繪畫統計資訊（增強版）"""
        try:
            self.logger.info("=" * 60)
            self.logger.info("📈 繪畫統計")
            self.logger.info("=" * 60)
            
            # 基本資訊
            self.logger.info(f"受試者編號: {self.subject_info.get('subject_id', 'N/A')}")
            self.logger.info(f"繪畫類型: {self.current_drawing_info.get('drawing_type', 'N/A')}")
            self.logger.info(f"繪畫計數: {self.drawing_counter}")
            self.logger.info(f"繪畫ID: {self.current_drawing_info.get('drawing_id', 'N/A')}")
            self.logger.info(f"顯示模式: {'延伸螢幕' if self.is_extended_mode else '單螢幕'}")  # 🆕
            
            self.logger.info("-" * 60)
            
            # 墨水系統統計
            stats = self.ink_system.get_processing_statistics()
            self.logger.info(f"總筆劃數: {stats.get('total_strokes', 0)}")
            self.logger.info(f"總原始點數: {stats.get('total_raw_points', 0)}")
            self.logger.info(f"總處理點數: {stats.get('total_processed_points', 0)}")
            
            # 計算平均採樣率
            sampling_rate = 0.0
            
            # 嘗試從 LSL 數據計算
            if hasattr(self, 'lsl') and self.lsl is not None:
                ink_samples = self.lsl.data_recorder.ink_samples
                if len(ink_samples) > 1:
                    time_span = ink_samples[-1].timestamp - ink_samples[0].timestamp
                    if time_span > 0:
                        sampling_rate = len(ink_samples) / time_span
                        self.logger.info(f"平均採樣率: {sampling_rate:.1f} 點/秒")
                        self.logger.info(f"記錄時長: {time_span:.2f} 秒")
                    else:
                        self.logger.info("平均採樣率: N/A (時間跨度為0)")
                else:
                    self.logger.info(f"平均採樣率: N/A (樣本數不足: {len(ink_samples)})")
            else:
                # 從墨水系統統計獲取
                sampling_rate = stats.get('raw_points_per_second', 0)
                if sampling_rate > 0:
                    self.logger.info(f"平均採樣率: {sampling_rate:.1f} 點/秒")
                else:
                    self.logger.info("平均採樣率: N/A")
            
            # 畫布統計
            self.logger.info("-" * 60)
            active_strokes = len([s for s in self.all_strokes if not s.get('is_deleted', False)])
            deleted_strokes = len([s for s in self.all_strokes if s.get('is_deleted', False)])
            self.logger.info(f"畫布筆劃數: {active_strokes} (已刪除: {deleted_strokes})")
            
            self.logger.info("=" * 60)
            
        except Exception as e:
            self.logger.error(f"❌ 輸出統計失敗: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    
    def _export_current_canvas(self):
        """匯出當前畫布"""
        try:
            if hasattr(self, 'lsl') and self.lsl is not None:
                output_dir = os.path.join(
                    self.lsl.data_recorder.output_dir, 
                    self.lsl.data_recorder.session_id
                )
                os.makedirs(output_dir, exist_ok=True)
                
                canvas_image_path = os.path.join(output_dir, "canvas_drawing.png")
                
                if self.export_canvas_image(canvas_image_path):
                    self.logger.info(f"✅ 畫布已保存: {canvas_image_path}")
                else:
                    self.logger.warning("⚠️ 畫布匯出失敗")
                    
        except Exception as e:
            self.logger.error(f"❌ 匯出畫布失敗: {e}")

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
                # ✅✅✅ 創建點數據
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
                    # 🆕 記錄開始時間
                    self._stroke_start_time = self.lsl.stream_manager.get_stream_time()
                
                # ✅✅✅ 關鍵修復：發送點數據到處理系統
                self.last_point_data = point_data
                self.ink_system.process_raw_point(point_data)
                
                # ✅ 添加到 Canvas 緩存（僅用於即時顯示）
                self.current_stroke_points.append((x_pixel, y_pixel, current_pressure))
                self.total_points += 1
            
            else:  # pressure = 0
                if self.pen_is_touching and self.current_stroke_points:
                    self.logger.info(
                        f"🔚 筆離開屏幕（壓力=0），筆劃結束 "
                        f"at 像素=({x_pixel:.1f}, {y_pixel:.1f}), "
                        f"歸一化=({x_normalized:.3f}, {y_normalized:.3f})"
                    )
                    
                    # ❌❌❌ 移除這段：不要在這裡添加到 all_strokes
                    # stroke_id = len(self.all_strokes)
                    # self.all_strokes.append(...)
                    
                    # ✅ 只發送結束點到處理系統（由回調統一處理）
                    point_data = {
                        'x': x_normalized,
                        'y': y_normalized,
                        'pressure': 0.0,
                        'timestamp': self.lsl.stream_manager.get_stream_time(),
                        'tilt_x': event.xTilt(),
                        'tilt_y': event.yTilt()
                    }
                    self.ink_system.process_raw_point(point_data)
                    
                    # ✅ 清空 Canvas 緩存（等待回調添加到 all_strokes）
                    self.current_stroke_points = []
                    self.stroke_count += 1
                    
                    self.pen_is_touching = False
                    self.current_pressure = 0.0
                    self.last_point_data = None
                    
                    # 立即重繪（此時 all_strokes 還沒更新，但會在回調後更新）
                    # self.update()  # ← 移除這行，讓回調觸發重繪
        
        except Exception as e:
            self.logger.error(f"❌ 處理筆輸入失敗: {e}")
            import traceback
            self.logger.error(traceback.format_exc())


    
    def _handle_eraser_input(self, x_pixel, y_pixel, current_pressure, event):
        """處理橡皮擦輸入"""
        try:
            if current_pressure > 0:
                self.current_eraser_points.append((x_pixel, y_pixel))
                
                # 🆕🆕🆕 初始化被刪除的筆劃 ID 集合
                if not hasattr(self, 'current_deleted_stroke_ids'):
                    self.current_deleted_stroke_ids = set()
                
                # 即時檢測碰撞並標記刪除
                eraser_point = (x_pixel, y_pixel)
                for stroke in self.all_strokes:
                    if stroke['is_deleted']:
                        continue
                    
                    if self.eraser_tool.check_collision(eraser_point, stroke['points']):
                        stroke['is_deleted'] = True
                        stroke['metadata'].is_deleted = True
                        
                        # ✅✅✅ 使用 stroke 字典中的 stroke_id（這是 LSL 的 ID）
                        deleted_stroke_id = stroke['stroke_id']
                        self.current_deleted_stroke_ids.add(deleted_stroke_id)
                        
                        self.logger.info(f"🗑️ 刪除筆劃: stroke_id={deleted_stroke_id}")
                
                if not self.pen_is_touching:
                    self.logger.info("🧹 橡皮擦筆劃開始")
                    self.pen_is_touching = True
            
            else:  # pressure = 0
                if self.pen_is_touching and self.current_eraser_points:
                    self.logger.info("🧹 橡皮擦筆劃結束")
                    
                    # 🆕🆕🆕 獲取被刪除的筆劃 ID
                    deleted_stroke_ids = list(getattr(self, 'current_deleted_stroke_ids', set()))
                    
                    # 🆕🆕🆕 記錄到 LSL
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
                            f"deleted_stroke_ids={deleted_stroke_ids}"
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
                    
                    # ✅ 重繪畫布
                    self.update()
            
        except Exception as e:
            self.logger.error(f"❌ 處理橡皮擦輸入失敗: {e}")
            import traceback
            self.logger.error(traceback.format_exc())


    def clear_canvas(self):
        """清空畫布"""
        try:
            self.logger.info("🗑️ 準備清空畫布...")
            
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
                self.ink_system.stroke_detector.current_stroke_id = 0
                self.logger.info("🧹 已重置 StrokeDetector 狀態為 IDLE，stroke_id=0")
            
            # 🆕🆕🆕 5. 清空 LSL 記錄的墨水點和標記
            if hasattr(self, 'lsl') and self.lsl is not None:
                self.lsl.data_recorder.ink_samples.clear()
                self.lsl.data_recorder.markers.clear()
                
                self.lsl.current_stroke_id = 0
                self.lsl._stroke_has_started = False
                
                self.logger.info("🧹 已清空 LSL 記錄緩衝區，stroke_id 重置為 0")
            
            # 🆕🆕🆕 6. 記錄清空事件
            if hasattr(self, 'lsl') and self.lsl is not None:
                timestamp = self.lsl.stream_manager.get_stream_time()
                
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
            
            pen = QPen(QColor(0, 0, 0), 2)
            painter.setPen(pen)
            
            for stroke in self.all_strokes:
                if stroke.get('is_deleted', False):
                    continue
                
                points = stroke['points']
                for i in range(len(points) - 1):
                    x1, y1, p1 = points[i]
                    x2, y2, p2 = points[i + 1]
                    
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
        """視窗關閉時的處理（簡化版）"""
        try:
            self.logger.info("=" * 60)
            self.logger.info("🔚 程序關閉")
            self.logger.info("=" * 60)
            
            # 完成最後一次繪畫
            self._finish_current_drawing()
            
            # 停止墨水處理系統
            if self.ink_system:
                self.logger.info("停止墨水處理系統...")
                self.ink_system.stop_processing()
                self.ink_system.shutdown()
            
            # 關閉日誌處理器
            if hasattr(self, 'log_file_path'):
                root_logger = logging.getLogger()
                for handler in root_logger.handlers[:]:
                    if isinstance(handler, logging.FileHandler):
                        handler.close()
                        root_logger.removeHandler(handler)
            
            self.logger.info("✅ 程序已安全關閉")
            event.accept()
            
        except Exception as e:
            self.logger.error(f"❌ 關閉程序時出錯: {e}")
            event.accept()


    def enterEvent(self, event):
        """筆進入畫布區域時觸發"""
        try:
            self.logger.info(f"🚪 筆進入畫布區域 (當前壓力: {self.current_pressure:.3f})")
            
            self.pen_is_in_canvas = True
            
            if self.current_stroke_points and self.last_point_data is not None:
                current_time = self.lsl.stream_manager.get_stream_time()
                time_since_last_point = current_time - self.last_point_data['timestamp']
                
                if time_since_last_point > 1.0:
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
        """筆離開畫布區域時觸發"""
        try:
            self.logger.info(f"🚪 筆離開畫布區域 (當前壓力: {self.current_pressure:.3f})")
            
            self.pen_is_in_canvas = False
            
            self._force_end_current_stroke()
            
            event.accept()
            
        except Exception as e:
            self.logger.error(f"❌ leaveEvent 處理失敗: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _force_end_current_stroke(self):
        """強制結束當前筆劃"""
        try:
            from StrokeDetector import StrokeState
            
            has_active_stroke = (
                hasattr(self.ink_system, 'stroke_detector') and
                self.ink_system.stroke_detector.current_state in [StrokeState.ACTIVE, StrokeState.STARTING]
            )
            
            has_unfinished_points = (
                self.current_stroke_points and
                self.last_point_data is not None
            )
            
            if has_active_stroke and has_unfinished_points:
                self.logger.info(
                    f"🔚 強制結束筆劃: stroke_id={self.ink_system.stroke_detector.current_stroke_id}, "
                    f"points={len(self.current_stroke_points)}"
                )
                
                final_point = self.last_point_data.copy()
                final_point['pressure'] = 0.0
                final_point['timestamp'] = self.lsl.stream_manager.get_stream_time()
                
                self.ink_system.process_raw_point(final_point)
                
                import time
                time.sleep(0.05)
            
            self.current_stroke_points = []
            self.last_point_data = None
            self.pen_is_touching = False
            self.current_pressure = 0.0
            
            if hasattr(self.ink_system, 'point_processor'):
                self.ink_system.point_processor.clear_history()
                self.logger.info("🧹 已清空 PointProcessor 歷史緩存")
            
            if hasattr(self.ink_system, 'stroke_detector'):
                self.ink_system.stroke_detector.force_reset_state()
                self.logger.info("🧹 已強制重置 StrokeDetector 狀態")
            
            self.logger.info("✅ 筆劃已強制結束，所有狀態已清理")
            
        except Exception as e:
            self.logger.error(f"❌ 強制結束筆劃失敗: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def tabletEvent(self, event):
        """接收 Wacom 輸入事件"""
        try:
            # ✅✅✅ 診斷日誌
            self.logger.debug(f"🖊️ tabletEvent: pos=({event.x()}, {event.y()}), pressure={event.pressure():.3f}")
            
            current_pressure = event.pressure()
            self.current_pressure = current_pressure
            
            pos = event.pos()
            is_in_bounds = self.rect().contains(pos)
            
            if not is_in_bounds:
                self.logger.debug(f"⏭️ 筆移出畫布邊界: ({pos.x()}, {pos.y()})")
                
                if self.pen_is_touching or self.current_stroke_points:
                    self.logger.info("🔚 筆移出畫布，強制結束當前筆劃")
                    self._force_end_current_stroke()
                
                event.accept()
                return
            
            x_pixel = event.x()
            y_pixel = event.y()
            
            toolbar_height = 50
            canvas_width = self.config.canvas_width
            canvas_height = self.config.canvas_height
            
            if y_pixel < toolbar_height:
                self.logger.debug(f"⏭️ 點在工具欄區域，跳過墨水處理: ({x_pixel}, {y_pixel})")
                
                if self.pen_is_touching or self.current_stroke_points:
                    self.logger.info("🔚 筆進入工具欄區域，強制結束當前筆劃")
                    self._force_end_current_stroke()
                
                event.accept()
                return
            
            adjusted_y = y_pixel - toolbar_height
            
            x_normalized = x_pixel / canvas_width
            y_normalized = adjusted_y / canvas_height
            
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
        """繪製筆劃"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        toolbar_height = 50
        painter.translate(0, toolbar_height)
        
        pen = QPen(QColor(0, 0, 0), 2)
        painter.setPen(pen)
        
        for stroke in self.all_strokes:
            if stroke.get('is_deleted', False):
                continue
            
            points = stroke['points']
            for i in range(len(points) - 1):
                x1, y1, p1 = points[i]
                x2, y2, p2 = points[i + 1]
                
                width = 1 + p1 * 5
                pen.setWidthF(width)
                painter.setPen(pen)
                painter.drawLine(
                    int(x1), int(y1),
                    int(x2), int(y2)
                )
        
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
        
        # 🔧 修改狀態列顯示，添加繪畫類型
        painter.setPen(QPen(QColor(100, 100, 100)))
        
        drawing_type = self.current_drawing_info.get('drawing_type', 'N/A') if self.current_drawing_info else 'N/A'
        
        if self.last_point_data:
            x_pixel = self.last_point_data['x'] * self.width()
            y_pixel = self.last_point_data['y'] * self.height()
            stats_text = (
                f"類型: {drawing_type} | "  # 🆕 添加繪畫類型
                f"工具: {self.current_tool.value} | "
                f"筆劃數: {len([s for s in self.all_strokes if not s['is_deleted']])} | "
                f"總點數: {self.total_points} | "
                f"壓力: {self.current_pressure:.3f} | "
                f"位置: ({x_pixel:.0f}, {y_pixel:.0f})"
            )
        else:
            stats_text = (
                f"類型: {drawing_type} | "  # 🆕 添加繪畫類型
                f"工具: {self.current_tool.value} | "
                f"筆劃數: {len([s for s in self.all_strokes if not s['is_deleted']])} | "
                f"總點數: {self.total_points} | "
                f"壓力: {self.current_pressure:.3f} | 位置: N/A"
            )
        
        # painter.drawText(10, 20, stats_text)
        
    def update_stats_display(self):
        """更新統計顯示"""
        self.setWindowTitle(
            f"Wacom 測試 - 筆劃: {self.stroke_count}, 點數: {self.total_points}"
        )


# 主函數
def test_wacom_with_full_system():
    """完整的 Wacom + 墨水處理系統測試（自動偵測延伸螢幕模式）"""
    print("=" * 60)
    print("🎨 Wacom 墨水處理系統完整測試（自動螢幕配置）")
    print("=" * 60)
    
    config = ProcessingConfig(
        device_type="wacom",
        target_sampling_rate=200,
        smoothing_enabled=True,
        feature_types=['basic', 'kinematic', 'pressure'],
    )
    
    print(f"\n📐 畫布配置: {config.canvas_width} x {config.canvas_height}")
    
    ink_system = InkProcessingSystem(config)
    
    device_config = {
        'device_type': 'wacom',
        'sampling_rate': 200
    }
    
    print("\n🔧 初始化墨水處理系統...")
    if not ink_system.initialize(device_config):
        print("❌ 系統初始化失敗")
        return
    
    print("✅ 系統初始化成功")
    
    def on_stroke_completed(data):
        """筆劃完成回調"""
        try:
            stroke_id = data.get('stroke_id', 'N/A')
            points = data.get('points', [])
            num_points = data.get('num_points', len(points))
            
            print(f"\n✅ 筆劃完成:")
            print(f"   - ID: {stroke_id}")
            print(f"   - 點數: {num_points}")
            
            if points and len(points) >= 2:
                duration = points[-1].timestamp - points[0].timestamp
                print(f"   - 持續時間: {duration:.3f}s")
                
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
    
    print("\n🚀 啟動數據處理...")
    if not ink_system.start_processing(use_external_input=True):
        print("❌ 無法啟動處理")
        return

    print("✅ 處理已啟動（外部輸入模式）")

    app = QApplication(sys.argv)
    canvas = WacomDrawingCanvas(ink_system, config)

    print("✅ LSL 時間源已設置")

    canvas.show()

    print("\n" + "=" * 60)
    print("🎨 使用說明:")
    print("   1. 輸入受試者資訊後開始") 
    print("   2. 選擇繪畫類型")
    print("   3. 完成繪畫後點擊「新繪畫」按鈕開始下一個")
    print("   4. 關閉視窗結束所有測試")
    print("=" * 60 + "\n")
    
    try:
        app.exec_()
    except KeyboardInterrupt:
        print("\n⚠️  使用者中斷")
    
    print("\n🛑 停止處理...")
    ink_system.stop_processing()
    
    print("\n✅ 測試完成")

if __name__ == "__main__":
    test_wacom_with_full_system()
