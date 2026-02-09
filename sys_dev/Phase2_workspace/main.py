# main.py
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QHBoxLayout, QVBoxLayout, QMessageBox, QDesktopWidget, QLabel,QColorDialog, QDialog
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QPen, QColor, QTabletEvent,QPixmap, QCursor, QBrush
import sys
import time
from datetime import datetime
import logging
from InkProcessingSystemMainController import InkProcessingSystem
from DigitalInkDataStructure import ToolType, StrokeMetadata 
from EraserTool import EraserTool
import os
from Config import ProcessingConfig, WorkspaceConfig, get_default_workspace, ColorPickerMode
from SubjectInfoDialog import SubjectInfoDialog, DrawingTypeDialog, WorkspaceSelectionDialog

# 配置日誌
logging.basicConfig(
  level=logging.DEBUG,
  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# main.py (部分修改)

class ExperimenterControlWindow(QWidget):
    """實驗者控制視窗（顯示在主螢幕）"""
    
    def __init__(self, canvas, primary_screen, is_extended_mode):
        super().__init__()
        self.canvas = canvas
        self.primary_screen = primary_screen
        self.is_extended_mode = is_extended_mode
        self.logger = logging.getLogger('ExperimenterControlWindow')
        
        self._setup_ui()
        self._setup_window_position()
    
    def _setup_ui(self):
        """設置 UI (放大版)"""
        self.setWindowTitle("實驗者控制面板")
        # 🆕 修改：加大視窗尺寸 (原 400x230 -> 600x400)
        self.setFixedSize(600, 400)
        
        # 主佈局
        main_layout = QVBoxLayout()
        main_layout.setSpacing(25)  # 增加間距
        main_layout.setContentsMargins(30, 30, 30, 30)  # 增加邊距
        
        # === 資訊顯示區域 ===
        info_layout = QVBoxLayout()
        info_layout.setSpacing(15) # 資訊標籤間距
        
        # 🆕 修改：統一加大字體樣式
        label_style = "font-size: 24px; font-weight: bold;"
        value_style = "font-size: 24px; font-weight: bold; color: #2196F3;"
        
        # 受試者編號標籤
        self.subject_label = QLabel("受試者編號: N/A")
        self.subject_label.setStyleSheet(label_style)
        info_layout.addWidget(self.subject_label)
        
        # 當前繪畫編號標籤
        self.drawing_number_label = QLabel("當前繪畫編號: N/A")
        self.drawing_number_label.setStyleSheet(value_style)
        info_layout.addWidget(self.drawing_number_label)
        
        # 當前繪畫類型標籤
        self.drawing_type_label = QLabel("當前繪畫類型: N/A")
        self.drawing_type_label.setStyleSheet(label_style)
        info_layout.addWidget(self.drawing_type_label)
        
        main_layout.addLayout(info_layout)
        
        # 分隔線
        line = QWidget()
        line.setFixedHeight(4) # 加粗分隔線
        line.setStyleSheet("background-color: #cccccc;")
        main_layout.addWidget(line)
        
        # === 控制按鈕區域 ===
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)
        
        # 🆕 修改：按鈕樣式 (高度 50->80, 字體 16->24)
        btn_height = 80
        btn_font_size = "24px"
        
        # 新繪畫按鈕
        self.new_drawing_button = QPushButton("➕ 新繪畫")
        self.new_drawing_button.setFixedHeight(btn_height)
        self.new_drawing_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #4CAF50;
                color: white;
                font-size: {btn_font_size};
                font-weight: bold;
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background-color: #45a049;
            }}
        """)
        self.new_drawing_button.clicked.connect(self.on_new_drawing_clicked)
        button_layout.addWidget(self.new_drawing_button)
        
        # 關閉程式按鈕
        self.close_button = QPushButton("❌ 關閉程式")
        self.close_button.setFixedHeight(btn_height)
        self.close_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #f44336;
                color: white;
                font-size: {btn_font_size};
                font-weight: bold;
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background-color: #da190b;
            }}
        """)
        self.close_button.clicked.connect(self.on_close_clicked)
        button_layout.addWidget(self.close_button)
        
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)


    
    def _setup_window_position(self):
        """設置視窗位置（主螢幕右上角）"""
        if self.is_extended_mode:
            # 延伸模式：放在主螢幕右上角
            x = self.primary_screen.x() + self.primary_screen.width() - self.width() - 20
            y = self.primary_screen.y() + 20
            self.move(x, y)
            self.logger.info(f"✅ 控制視窗已設置在主螢幕右上角: ({x}, {y})")
        else:
            # 單螢幕模式：放在螢幕右上角
            x = self.primary_screen.width() - self.width() - 20
            y = 20
            self.move(x, y)
            self.logger.info(f"✅ 控制視窗已設置在螢幕右上角: ({x}, {y})")
        
        # 設置視窗置頂
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
    
    def update_info(self, subject_id, drawing_number, drawing_type):
        """更新顯示的資訊"""
        self.subject_label.setText(f"受試者編號: {subject_id}")
        self.drawing_number_label.setText(f"當前繪畫編號: {drawing_number}")  # 🆕
        self.drawing_type_label.setText(f"當前繪畫類型: {drawing_type}")
        self.logger.info(f"📝 控制面板資訊已更新: {subject_id}, #{drawing_number}, {drawing_type}")

    
    def on_new_drawing_clicked(self):
        """新繪畫按鈕點擊事件"""
        self.logger.info("🎨 點擊新繪畫按鈕")
        self.canvas.start_new_drawing()
    
    def on_close_clicked(self):
        """關閉程式按鈕點擊事件"""
        self.logger.info("❌ 點擊關閉程式按鈕")
        
        # 確認對話框
        reply = QMessageBox.question(
            self,
            '確認關閉',
            '確定要關閉程式嗎？\n所有數據將被保存。',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.logger.info("✅ 用戶確認關閉程式")
            self.canvas.close()  # 關閉畫布視窗
            self.close()  # 關閉控制視窗
    
    def closeEvent(self, event):
        """控制視窗關閉時同時關閉畫布"""
        self.logger.info("🔚 控制視窗關閉")
        if self.canvas:
            self.canvas.close()
        event.accept()

class WacomDrawingCanvas(QWidget):
    def __init__(self, ink_system, config: ProcessingConfig, workspace: WorkspaceConfig = None):
        super().__init__()
        self.ink_system = ink_system
        self.config = config
        
        # 🔧 修復：先初始化 logger
        self.logger = logging.getLogger('WacomDrawingCanvas')
        
        # 🆕🆕🆕 Workspace 配置
        if workspace is None:
            workspace = get_default_workspace()
        self.workspace = workspace
        self.current_test_config = None  # 當前測試配置
        
        # 🆕 顏色相關屬性
        self.current_color = QColor('#000000')  # 使用 hex code 創建
        self.current_color_name = self.current_color.name()  # '#000000'

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

        # 🆕🆕🆕 創建實驗者控制視窗
        self.control_window = None
        self._create_control_window()

        # 🆕🆕🆕 初始化自定義游標
        self._update_cursor()
        
        self.logger.info("✅ WacomDrawingCanvas 初始化完成")
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

    def _create_pen_cursor(self, color: QColor, size: int = 8) -> QCursor:
        """
        創建自定義筆頭游標（增強版：帶陰影，無邊框，無高光點）
        
        Args:
            color: 游標顏色
            size: 游標大小（像素）
        
        Returns:
            QCursor: 自定義游標
        """
        from PyQt5.QtGui import QPixmap, QCursor, QPainter, QBrush, QRadialGradient
        from PyQt5.QtCore import Qt, QPointF
        
        try:
            # 創建透明背景的 pixmap（稍大一點以容納陰影）
            pixmap_size = size + 8
            pixmap = QPixmap(pixmap_size, pixmap_size)
            pixmap.fill(Qt.transparent)
            
            # 繪製筆頭
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            center = pixmap_size // 2
            
            # 🎨 繪製陰影（可選）
            shadow_color = QColor(0, 0, 0, 50)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(shadow_color))
            painter.drawEllipse(center - size // 2 + 1, center - size // 2 + 1, size, size)
            
            # 🎨 繪製主體（使用漸變增加立體感）
            gradient = QRadialGradient(QPointF(center - size // 4, center - size // 4), size)
            gradient.setColorAt(0, color.lighter(130))  # 高光
            gradient.setColorAt(1, color)  # 主色
            
            painter.setPen(Qt.NoPen)  # 無邊框
            painter.setBrush(QBrush(gradient))
            painter.drawEllipse(center - size // 2, center - size // 2, size, size)
            
            # 🆕🆕🆕 移除高光點（刪除以下代碼）
            # painter.setPen(Qt.NoPen)
            # painter.setBrush(QBrush(QColor(255, 255, 255, 150)))
            # highlight_size = size // 4
            # painter.drawEllipse(
            #     center - size // 4 - highlight_size // 2,
            #     center - size // 4 - highlight_size // 2,
            #     highlight_size,
            #     highlight_size
            # )
            
            painter.end()
            
            # 創建游標（熱點在中心）
            cursor = QCursor(pixmap, center, center)
            
            self.logger.debug(f"✅ 創建自定義游標（無邊框，無高光點）: color={color.name()}, size={size}")
            return cursor
            
        except Exception as e:
            self.logger.error(f"❌ 創建自定義游標失敗: {e}")
            return QCursor(Qt.CrossCursor)


    def _update_cursor(self):
        """
        根據當前工具和顏色更新游標
        """
        try:
            if self.current_tool == ToolType.PEN:
                # 🖊️ 筆工具：使用當前顏色的圓點
                cursor = self._create_pen_cursor(self.current_color, size=8)
                self.setCursor(cursor)
                self.logger.debug(f"🖱️ 游標已更新為筆頭（顏色: {self.current_color_name}）")
            
            elif self.current_tool == ToolType.ERASER:
                # 🧈 橡皮擦：使用圓形游標（灰色）
                cursor = self._create_pen_cursor(QColor(200, 200, 200), size=12)
                self.setCursor(cursor)
                self.logger.debug("🖱️ 游標已更新為橡皮擦")
            
            else:
                # 其他工具：使用默認箭頭
                self.setCursor(Qt.ArrowCursor)
                self.logger.debug("🖱️ 游標已重置為箭頭")
        
        except Exception as e:
            self.logger.error(f"❌ 更新游標失敗: {e}")

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
            # 延伸模式：使用副螢幕完整尺寸（全螢幕，不保留工作列空間）
            canvas_width = self.secondary_screen.width()
            canvas_height = self.secondary_screen.height() - toolbar_height  # 減去工具列高度
            self.logger.info(f"📐 畫布尺寸（延伸模式 - 副螢幕全螢幕）: {canvas_width} x {canvas_height}")
        else:
            # 單螢幕模式：使用主螢幕可用區域（保留工作列空間）
            desktop = QDesktopWidget()
            screen_rect = desktop.availableGeometry()
            canvas_width = screen_rect.width()
            canvas_height = screen_rect.height() - toolbar_height
            self.logger.info(f"📐 畫布尺寸（單螢幕模式）: {canvas_width} x {canvas_height}")
        
        # 更新配置
        self.config.canvas_width = canvas_width
        self.config.canvas_height = canvas_height
        
    def _setup_window(self):
        """🆕 根據螢幕模式設置視窗屬性（延伸模式時副螢幕全螢幕）"""
        # 設置視窗標題
        self.setWindowTitle("Wacom 繪圖測試")
        
        if self.is_extended_mode:
            # 🎯 延伸模式：副螢幕使用全螢幕（自動隱藏工作列）
            self.move(self.secondary_screen.x(), self.secondary_screen.y())
            # 🆕🆕🆕 移除關閉按鈕，只保留無邊框和置頂
            self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.CustomizeWindowHint)
            self.showFullScreen()
            
            self.logger.info("=" * 60)
            self.logger.info("✅ 畫布視窗已設置在副螢幕（全螢幕模式，無關閉按鈕）")
            self.logger.info(f"   位置: ({self.secondary_screen.x()}, {self.secondary_screen.y()})")
            self.logger.info(f"   尺寸: {self.secondary_screen.width()} x {self.secondary_screen.height()}")
            self.logger.info("   Windows 工作列已自動隱藏")
            self.logger.info("=" * 60)
        else:
            # 單螢幕模式：使用視窗模式（保留工作列）
            self.move(0, 0)
            self.setFixedSize(self.config.canvas_width, self.config.canvas_height + 50)
            # 🆕🆕🆕 禁用關閉按鈕
            self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowMinimizeButtonHint)
            
            self.logger.info("=" * 60)
            self.logger.info("✅ 畫布視窗已設置在主螢幕（視窗模式，無關閉按鈕）")
            self.logger.info("   位置: (0, 0)")
            self.logger.info(f"   尺寸: {self.config.canvas_width} x {self.config.canvas_height + 50}")
            self.logger.info("   Windows 工作列保持可見")
            self.logger.info("=" * 60)
        
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
        dialog = DrawingTypeDialog(self.drawing_counter, self.workspace, self)  # 🆕 添加 workspace 參數
        
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
            
            # 🆕🆕🆕 根據 drawing_type 獲取對應的測試配置
            drawing_type = self.current_drawing_info['drawing_type']
            for test in self.workspace.drawing_sequence:
                if test.drawing_type == drawing_type:
                    self.current_test_config = test
                    break
            
            self.logger.info(f"✅ 繪畫資訊: {self.current_drawing_info}")
            self.logger.info(f"✅ 測試配置: {self.current_test_config.display_name}")
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
            # ✅ 修正：添加 self.workspace 參數
            dialog = DrawingTypeDialog(next_drawing_counter, self.workspace, self)
            
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
            
            # 🆕🆕🆕 根據 drawing_type 獲取對應的測試配置
            drawing_type = self.current_drawing_info['drawing_type']
            for test in self.workspace.drawing_sequence:
                if test.drawing_type == drawing_type:
                    self.current_test_config = test
                    break
            
            self.logger.info(f"✅ 新繪畫資訊: {self.current_drawing_info}")
            self.logger.info(f"✅ 測試配置: {self.current_test_config.display_name}")
            
            # 7. 更新視窗標題
            self._update_window_title()
            
            # 8. 重置畫布狀態
            self._reset_canvas_state()
            
            # 9. 重新初始化LSL（新目錄）
            self._initialize_lsl()
            
            # 10. 重新設置墨水系統
            self._reset_ink_system()
                    
            # 🆕🆕🆕 11. 更新顏色按鈕可見性
            self._update_color_button_visibility()
                    
            self.logger.info(f"✅ 新繪畫已開始 (繪畫編號: {self.drawing_counter})")
            
            # 🆕🆕🆕 更新控制視窗資訊
            if self.control_window:
                subject_id = self.subject_info.get('subject_id', 'N/A')
                drawing_number = self.drawing_counter  # 🆕 添加繪畫編號
                drawing_type = self.current_drawing_info.get('drawing_type', 'N/A')
                self.control_window.update_info(subject_id, drawing_number, drawing_type)  # 🆕 傳遞三個參數
            
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
        """處理點數據並推送到 LSL（使用當前顏色）"""
        self.lsl.process_ink_point(
            x=point_data['x'],
            y=point_data['y'],
            pressure=point_data['pressure'],
            tilt_x=point_data.get('tilt_x', 0),
            tilt_y=point_data.get('tilt_y', 0),
            velocity=point_data.get('velocity', 0),
            is_stroke_start=point_data.get('is_stroke_start', False),
            is_stroke_end=point_data.get('is_stroke_end', False),
            color=self.current_color_name  # ✅ 添加這一行
        )

    

    def _on_stroke_completed_callback(self, stroke_data):
        """筆劃完成時的處理（優化版：添加邊界框緩存）"""
        try:
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
            
            # 創建元數據
            metadata = StrokeMetadata(
                stroke_id=stroke_id,
                tool_type=ToolType.PEN,
                timestamp_start=stroke_data['start_time'],
                timestamp_end=stroke_data['end_time'],
                is_deleted=False,
                deleted_by=None,
                deleted_at=None
            )
            
            # 🆕🆕🆕 計算邊界框緩存
            xs = [p[0] for p in pixel_points]
            ys = [p[1] for p in pixel_points]
            bbox_cache = (min(xs), max(xs), min(ys), max(ys))
            
            # 添加到 all_strokes
            self.all_strokes.append({
                'stroke_id': stroke_id,
                'tool_type': ToolType.PEN,
                'points': pixel_points,
                'metadata': metadata,
                'is_deleted': False,
                '_bbox_cache': bbox_cache,  # 🆕 添加邊界框緩存,
                'color': self.current_color_name  # 🆕 保存顏色
            })
            
            self.logger.info(f"📝 筆劃已保存: stroke_id={stroke_id}, points={len(pixel_points)}, bbox={bbox_cache}")
            
            # 立即重繪畫布
            self.update()
            
        except Exception as e:
            self.logger.error(f"❌ 處理筆劃完成回調時出錯: {e}")
            import traceback
            self.logger.error(traceback.format_exc())


    def _setup_toolbar(self):
        """設置工具欄（修改版：垂直佈局，左側邊置中，放大圖示）"""
        
        # 🆕 使用垂直佈局（VBoxLayout）
        toolbar_layout = QVBoxLayout()
        toolbar_layout.setSpacing(20)  # 增加按鈕間距
        toolbar_layout.setContentsMargins(10, 0, 10, 0)  # 左右邊距
        
        # 🆕 設置更大的按鈕尺寸
        button_size = 80  # 從 60 增加到 80
        
        # 🆕 添加頂部彈性空間（讓按鈕垂直置中）
        toolbar_layout.addStretch()
        
        # 筆工具按鈕
        self.pen_button = QPushButton("🖊️")
        self.pen_button.setFixedSize(button_size, button_size)
        self.pen_button.setStyleSheet("""
            QPushButton {
                background-color: lightblue;
                font-size: 40px;  /* 放大圖示 */
                border-radius: 10px;
                border: 2px solid #2196F3;
            }
            QPushButton:hover {
                background-color: #81D4FA;
            }
        """)
        self.pen_button.setToolTip("筆")
        self.pen_button.clicked.connect(lambda: self.switch_tool(ToolType.PEN))
        toolbar_layout.addWidget(self.pen_button, alignment=Qt.AlignCenter)
        
        # 橡皮擦按鈕
        self.eraser_button = QPushButton("🧈")
        self.eraser_button.setFixedSize(button_size, button_size)
        self.eraser_button.setStyleSheet("""
            QPushButton {
                background-color: white;
                font-size: 40px;  /* 放大圖示 */
                border-radius: 10px;
                border: 2px solid #cccccc;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
        self.eraser_button.setToolTip("橡皮擦")
        self.eraser_button.clicked.connect(lambda: self.switch_tool(ToolType.ERASER))
        toolbar_layout.addWidget(self.eraser_button, alignment=Qt.AlignCenter)
        
        # 🆕 顏色選擇按鈕
        self.color_button = QPushButton("🎨")
        self.color_button.setFixedSize(button_size, button_size)
        self.color_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.current_color.name()};
                font-size: 40px;  /* 放大圖示 */
                border-radius: 10px;
                border: 2px solid #666666;
            }}
            QPushButton:hover {{
                border: 3px solid #333333;
            }}
        """)
        self.color_button.setToolTip("選擇顏色")
        self.color_button.clicked.connect(self.choose_color)
        toolbar_layout.addWidget(self.color_button, alignment=Qt.AlignCenter)
        
        # 🆕🆕🆕 根據繪畫類型決定是否顯示顏色按鈕
        self._update_color_button_visibility()
        
        # 🆕 添加底部彈性空間（讓按鈕垂直置中）
        toolbar_layout.addStretch()
        
        # 🆕 創建工具欄容器（垂直條）
        toolbar_widget = QWidget()
        toolbar_widget.setLayout(toolbar_layout)
        toolbar_widget.setFixedWidth(120)  # 設置工具欄寬度
        toolbar_widget.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-right: 2px solid #cccccc;
            }
        """)
        
        # 🆕 創建主佈局（水平佈局：工具欄 + 畫布）
        main_layout = QHBoxLayout()
        main_layout.addWidget(toolbar_widget)  # 左側工具欄
        main_layout.addStretch()  # 右側畫布區域（自動填充）
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.setLayout(main_layout)


    def _update_color_button_visibility(self):
        """🆕 根據測試配置更新顏色按鈕可見性"""
        if self.current_test_config is None:
            self.color_button.hide()
            self.current_color = QColor('#000000')
            self.current_color_name = '#000000'
            return
        
        # 🆕 根據 Workspace 配置決定是否顯示
        if self.current_test_config.toolbar.color_picker_enabled:
            self.color_button.show()
            self._update_color_button_style()
            self.logger.info(f"✅ 顏色按鈕已顯示（{self.current_test_config.drawing_type}）")
        else:
            self.color_button.hide()
            self.current_color = QColor('#000000')
            self.current_color_name = '#000000'
            self.logger.info(f"⚠️ 顏色按鈕已隱藏（{self.current_test_config.drawing_type}）")



    def _update_color_button_style(self):
        """🆕 更新顏色按鈕的樣式（背景色）- 統一管理"""
        self.color_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.current_color_name};
                font-size: 40px;
                border-radius: 10px;
                border: 2px solid #666666;
            }}
            QPushButton:hover {{
                border: 3px solid #333333;
            }}
        """)
        self.logger.debug(f"🎨 顏色按鈕樣式已更新: {self.current_color_name}")

    def choose_color(self):
        """選擇顏色（支援 24 色調色盤）"""
        
        try:
            # 強制完成當前筆劃
            if self.pen_is_touching and self.current_stroke_points:
                self.logger.info("🎨 切換顏色前強制完成當前筆劃")
                
                if self.last_point_data is not None:
                    final_point = self.last_point_data.copy()
                    final_point['pressure'] = 0.0
                    final_point['timestamp'] = self.lsl.stream_manager.get_stream_time()
                    self.ink_system.process_raw_point(final_point)
                    
                    import time
                    time.sleep(0.05)
            
            # 清理狀態
            self.current_stroke_points = []
            self.last_point_data = None
            self.pen_is_touching = False
            self.current_pressure = 0.0
            
            if hasattr(self.ink_system, 'point_processor'):
                self.ink_system.point_processor.clear_history()
            
            if hasattr(self.ink_system, 'stroke_detector'):
                from StrokeDetector import StrokeState
                self.ink_system.stroke_detector.current_state = StrokeState.IDLE
                self.ink_system.stroke_detector.current_stroke_points = []
            
            # 記錄切換前的顏色
            old_color = self.current_color_name
            
            # 🆕🆕🆕 根據配置選擇顏色選擇器類型
            if self.current_test_config.toolbar.color_picker_mode == ColorPickerMode.PALETTE_24:
                # 使用 24 色調色盤
                color = self._show_palette_color_picker()
            else:
                # 使用完整色譜
                color = QColorDialog.getColor(self.current_color, self, "選擇畫筆顏色")
            
            if color and color.isValid():
                # 更新為 hex code
                self.current_color = color
                self.current_color_name = color.name()
                
                # ✅ 使用統一方法更新按鈕樣式
                self._update_color_button_style()
                
                # 記錄顏色切換事件到 LSL
                self.lsl.mark_color_switch(old_color, self.current_color_name)
                
                # 更新游標顏色
                self._update_cursor()
                
                self.logger.info(f"🎨 顏色已切換: {old_color} → {self.current_color_name}")
            else:
                self.logger.info("❌ 用戶取消顏色選擇")
                
        except Exception as e:
            self.logger.error(f"❌ 選擇顏色失敗: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _show_palette_color_picker(self) -> QColor:
        """🆕 顯示 24 色調色盤選擇器"""
        from PyQt5.QtWidgets import QDialog, QGridLayout, QPushButton, QVBoxLayout, QLabel
        
        dialog = QDialog(self)
        dialog.setWindowTitle("選擇顏色")
        dialog.setModal(True)
        
        main_layout = QVBoxLayout()
        
        # 標題
        title = QLabel("請選擇顏色:")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        main_layout.addWidget(title)
        
        # 顏色網格
        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)
        
        palette = self.current_test_config.toolbar.color_palette
        selected_color = [None]  # 使用列表以便在閉包中修改
        
        def create_color_button(color_hex):
            btn = QPushButton()
            btn.setFixedSize(60, 60)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color_hex};
                    border: 2px solid #666666;
                    border-radius: 5px;
                }}
                QPushButton:hover {{
                    border: 3px solid #333333;
                }}
            """)
            btn.clicked.connect(lambda: on_color_selected(color_hex))
            return btn
        
        def on_color_selected(color_hex):
            selected_color[0] = QColor(color_hex)
            dialog.accept()
        
        # 排列為 6x4 網格
        for i, color_hex in enumerate(palette[:24]):  # 確保只取 24 個
            row = i // 6
            col = i % 6
            grid_layout.addWidget(create_color_button(color_hex), row, col)
        
        main_layout.addLayout(grid_layout)
        
        # 取消按鈕
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-size: 18px;
                min-height: 40px;
                border-radius: 5px;
            }
        """)
        cancel_btn.clicked.connect(dialog.reject)
        main_layout.addWidget(cancel_btn)
        
        dialog.setLayout(main_layout)
        
        # 顯示對話框
        if dialog.exec_() == QDialog.Accepted and selected_color[0]:
            return selected_color[0]
        else:
            return QColor()  # 返回無效顏色


    def _create_control_window(self):
        """🆕 創建實驗者控制視窗"""
        try:
            self.control_window = ExperimenterControlWindow(
                canvas=self,
                primary_screen=self.primary_screen,
                is_extended_mode=self.is_extended_mode
            )
            
            # 更新控制視窗的資訊
            subject_id = self.subject_info.get('subject_id', 'N/A') if self.subject_info else 'N/A'
            drawing_number = self.drawing_counter  # 🆕 添加繪畫編號
            drawing_type = self.current_drawing_info.get('drawing_type', 'N/A') if self.current_drawing_info else 'N/A'
            self.control_window.update_info(subject_id, drawing_number, drawing_type)  # 🆕 傳遞三個參數
            
            # 顯示控制視窗
            self.control_window.show()
            
            self.logger.info("✅ 實驗者控制視窗已創建並顯示")
            
        except Exception as e:
            self.logger.error(f"❌ 創建控制視窗失敗: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

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
        
        # 🆕🆕🆕 重置顏色為黑色
        self.current_color = QColor('#000000')
        self.current_color_name = '#000000'
        self.logger.info("🎨 顏色已重置為黑色")
        
        # 重置工具為筆
        self.current_tool = ToolType.PEN
        
        # 🔧 修復：保留 font-size
        self.pen_button.setStyleSheet("""
            QPushButton {
                background-color: lightblue;
                font-size: 40px;
                border-radius: 10px;
                border: 2px solid #2196F3;
            }
            QPushButton:hover {
                background-color: #81D4FA;
            }
        """)
        self.eraser_button.setStyleSheet("""
            QPushButton {
                background-color: white;
                font-size: 40px;
                border-radius: 10px;
                border: 2px solid #cccccc;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
        
        # 🆕🆕🆕 更新游標（使用黑色）
        self._update_cursor()
        
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
        """匯出當前畫布（保存到兩個位置）"""
        try:
            if hasattr(self, 'lsl') and self.lsl is not None:
                # 🆕 方案 1：保存到 session_id 子目錄（原有路徑）
                output_dir_with_session = os.path.join(
                    self.lsl.data_recorder.output_dir, 
                    self.lsl.data_recorder.session_id
                )
                os.makedirs(output_dir_with_session, exist_ok=True)
                
                canvas_image_path_1 = os.path.join(output_dir_with_session, "canvas_drawing.png")
                
                # 🆕 方案 2：保存到 output_dir 根目錄（新增路徑）
                canvas_image_path_2 = os.path.join(self.lsl.data_recorder.output_dir, "canvas_drawing.png")
                
                # 保存到第一個位置
                if self.export_canvas_image(canvas_image_path_1):
                    self.logger.info(f"✅ 畫布已保存（位置 1）: {canvas_image_path_1}")
                else:
                    self.logger.warning("⚠️ 畫布匯出失敗（位置 1）")
                
                # 🆕 保存到第二個位置
                if self.export_canvas_image(canvas_image_path_2):
                    self.logger.info(f"✅ 畫布已保存（位置 2）: {canvas_image_path_2}")
                else:
                    self.logger.warning("⚠️ 畫布匯出失敗（位置 2）")
                    
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
                # 🔧 修復：保留 font-size
                self.pen_button.setStyleSheet("""
                    QPushButton {
                        background-color: lightblue;
                        font-size: 40px;
                        border-radius: 10px;
                        border: 2px solid #2196F3;
                    }
                    QPushButton:hover {
                        background-color: #81D4FA;
                    }
                """)
                self.eraser_button.setStyleSheet("""
                    QPushButton {
                        background-color: white;
                        font-size: 40px;
                        border-radius: 10px;
                        border: 2px solid #cccccc;
                    }
                    QPushButton:hover {
                        background-color: #f0f0f0;
                    }
                """)
                self.logger.info("✅ 切換到筆工具")
            else:
                # 🔧 修復：保留 font-size
                self.eraser_button.setStyleSheet("""
                    QPushButton {
                        background-color: lightblue;
                        font-size: 40px;
                        border-radius: 10px;
                        border: 2px solid #2196F3;
                    }
                    QPushButton:hover {
                        background-color: #81D4FA;
                    }
                """)
                self.pen_button.setStyleSheet("""
                    QPushButton {
                        background-color: white;
                        font-size: 40px;
                        border-radius: 10px;
                        border: 2px solid #cccccc;
                    }
                    QPushButton:hover {
                        background-color: #f0f0f0;
                    }
                """)
                self.logger.info("✅ 切換到橡皮擦")
            
            # 🆕🆕🆕 更新游標
            self._update_cursor()
            
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
                    'tilt_y': event.yTilt(),
                    'color': self.current_color_name  # 🆕 添加顏色
                }

                
                if not self.pen_is_touching:
                    self.logger.info(
                        f"🎨 筆劃開始（第一個點）: "
                        f"像素=({x_pixel:.1f}, {y_pixel:.1f}), "
                        f"歸一化=({x_normalized:.3f}, {y_normalized:.3f}), "
                        f"pressure={current_pressure:.3f}, "
                        f"color={self.current_color_name}"
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
                        'tilt_y': event.yTilt(),
                        'color': self.current_color_name  # 🆕 添加顏色
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
        """處理橡皮擦輸入（優化版：邊界框過濾 + 降低重繪頻率）"""
        try:
            if current_pressure > 0:
                self.current_eraser_points.append((x_pixel, y_pixel))
                
                if not hasattr(self, 'current_deleted_stroke_ids'):
                    self.current_deleted_stroke_ids = set()
                
                # 🆕🆕🆕 優化 1：邊界框快速過濾
                eraser_point = (x_pixel, y_pixel)
                eraser_radius = self.eraser_tool.radius
                
                # 計算橡皮擦的邊界框
                eraser_min_x = x_pixel - eraser_radius
                eraser_max_x = x_pixel + eraser_radius
                eraser_min_y = y_pixel - eraser_radius
                eraser_max_y = y_pixel + eraser_radius
                
                for stroke in self.all_strokes:
                    if stroke['is_deleted']:
                        continue
                    
                    points = stroke['points']
                    if not points:
                        continue
                    
                    # 🆕 快速邊界框檢查（只計算一次）
                    if not hasattr(stroke, '_bbox_cache'):
                        xs = [p[0] for p in points]
                        ys = [p[1] for p in points]
                        stroke['_bbox_cache'] = (min(xs), max(xs), min(ys), max(ys))
                    
                    min_x, max_x, min_y, max_y = stroke['_bbox_cache']
                    
                    # 檢查橡皮擦邊界框是否與筆劃邊界框重疊
                    if (eraser_max_x < min_x or eraser_min_x > max_x or
                        eraser_max_y < min_y or eraser_min_y > max_y):
                        continue  # 跳過不可能碰撞的筆劃
                    
                    # 🆕 只對可能碰撞的筆劃進行精確檢測
                    if self.eraser_tool.check_collision(eraser_point, points):
                        stroke['is_deleted'] = True
                        stroke['metadata'].is_deleted = True
                        
                        deleted_stroke_id = stroke['stroke_id']
                        self.current_deleted_stroke_ids.add(deleted_stroke_id)
                        
                        # 🆕 刪除邊界框緩存
                        if '_bbox_cache' in stroke:
                            del stroke['_bbox_cache']
                        
                        self.logger.info(f"🗑️ 刪除筆劃: stroke_id={deleted_stroke_id}")
                
                if not self.pen_is_touching:
                    self.logger.info("🧹 橡皮擦筆劃開始")
                    self.pen_is_touching = True
                
                # 🆕🆕🆕 優化 2：降低重繪頻率（每 2 個事件重繪一次）
                if not hasattr(self, '_eraser_update_counter'):
                    self._eraser_update_counter = 0
                
                self._eraser_update_counter += 1
                if self._eraser_update_counter % 2 == 0:
                    self.update()
            
            else:  # pressure = 0
                if self.pen_is_touching and self.current_eraser_points:
                    self.logger.info("🧹 橡皮擦筆劃結束")
                    
                    deleted_stroke_ids = list(getattr(self, 'current_deleted_stroke_ids', set()))
                    
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
                    
                    self.current_eraser_points = []
                    if hasattr(self, 'current_deleted_stroke_ids'):
                        self.current_deleted_stroke_ids = set()
                    self.pen_is_touching = False
                    self.current_pressure = 0.0
                    self.last_point_data = None
                    
                    if hasattr(self.ink_system, 'point_processor'):
                        self.ink_system.point_processor.clear_history()
                    
                    # ✅ 橡皮擦結束時強制重繪
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
        """將畫布匯出為 PNG 圖片（🆕 使用顏色）"""
        try:
            from PyQt5.QtGui import QPixmap
            
            canvas_width = self.config.canvas_width
            canvas_height = self.config.canvas_height
            
            pixmap = QPixmap(canvas_width, canvas_height)
            pixmap.fill(Qt.white)
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            for stroke in self.all_strokes:
                if stroke.get('is_deleted', False):
                    continue
                
                # 🆕 獲取筆劃的顏色
                stroke_color_name = stroke.get('color', '#000000')
                stroke_color = QColor(stroke_color_name)
                
                pen = QPen(stroke_color, 2)  # 🆕 使用筆劃的顏色
                painter.setPen(pen)
                
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
            
            # 🆕🆕🆕 關閉控制視窗
            if self.control_window:
                self.control_window.close()
            
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
        """筆進入畫布區域時觸發（副螢幕）"""
        try:
            self.logger.info(f"🚪 筆進入畫布區域 (當前壓力: {self.current_pressure:.3f})")
            
            self.pen_is_in_canvas = True
            
            # 🆕🆕🆕 進入副螢幕時顯示自定義游標
            self._update_cursor()
            
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
        """筆離開畫布區域時觸發（回到主螢幕）"""
        try:
            self.logger.info(f"🚪 筆離開畫布區域 (當前壓力: {self.current_pressure:.3f})")
            
            self.pen_is_in_canvas = False
            
            # 🆕🆕🆕 離開副螢幕時恢復正常游標
            self.setCursor(Qt.ArrowCursor)
            self.logger.debug("🖱️ 游標已恢復為箭頭（離開畫布）")
            
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
            
            # 🆕🆕🆕 修改：工具欄在左側
            toolbar_width = 120  # 工具欄寬度
            canvas_width = self.config.canvas_width
            canvas_height = self.config.canvas_height
            
            # 🆕🆕🆕 檢查是否在工具欄區域（左側 120 像素）
            if x_pixel < toolbar_width:
                self.logger.debug(f"⏭️ 點在工具欄區域，跳過墨水處理: ({x_pixel}, {y_pixel})")
                
                if self.pen_is_touching or self.current_stroke_points:
                    self.logger.info("🔚 筆進入工具欄區域，強制結束當前筆劃")
                    self._force_end_current_stroke()
                
                event.accept()
                return
            
            # 🆕🆕🆕 調整座標（減去工具欄寬度）
            adjusted_x = x_pixel - toolbar_width
            
            # 🆕🆕🆕 歸一化座標
            x_normalized = adjusted_x / canvas_width
            y_normalized = y_pixel / canvas_height
            
            if self.current_tool == ToolType.PEN:
                self._handle_pen_input(adjusted_x, y_pixel, x_normalized, y_normalized, current_pressure, event)
            elif self.current_tool == ToolType.ERASER:
                self._handle_eraser_input(adjusted_x, y_pixel, current_pressure, event)
            
            # 🆕🆕🆕 橡皮擦模式下不在這裡觸發 update()（由 _handle_eraser_input 控制）
            if self.current_tool != ToolType.ERASER:
                self.update()
            
            event.accept()
            
        except Exception as e:
            self.logger.error(f"❌ tabletEvent 處理失敗: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            event.accept()

    def paintEvent(self, event):
        """繪製筆劃（優化版：調整左側工具欄偏移）"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 🆕🆕🆕 修改：左側工具欄偏移（從 toolbar_height 改為 toolbar_width）
        toolbar_width = 120  # 工具欄寬度
        painter.translate(toolbar_width, 0)  # 向右偏移 120 像素
        
        # 🆕🆕🆕 優化 1：只繪製可見區域的筆劃
        visible_rect = event.rect()
        visible_rect.translate(-toolbar_width, 0)  # 🆕 調整工具欄偏移
        
        # 🆕🆕🆕 優化 2：預先過濾未刪除的筆劃（提前定義，避免後續未定義錯誤）
        active_strokes = [s for s in self.all_strokes if not s.get('is_deleted', False)]
        
        # 繪製已完成的筆劃（使用各自的顏色）
        for stroke in active_strokes:
            points = stroke['points']
            
            if not points:
                continue
            
            # 🆕 獲取筆劃的顏色（直接使用 hex code）
            stroke_color_name = stroke.get('color', '#000000')
            stroke_color = QColor(stroke_color_name)  # 直接創建 QColor
            
            pen = QPen(stroke_color, 2)
            painter.setPen(pen)
            
            # 🆕 邊界框裁剪（跳過不可見的筆劃）
            if hasattr(stroke, '_bbox_cache'):
                min_x, max_x, min_y, max_y = stroke['_bbox_cache']
                if (max_x < visible_rect.left() or min_x > visible_rect.right() or
                    max_y < visible_rect.top() or min_y > visible_rect.bottom()):
                    continue
            
            # 繪製筆劃
            for i in range(len(points) - 1):
                x1, y1, p1 = points[i]
                x2, y2, p2 = points[i + 1]
                
                width = 1 + p1 * 5
                pen.setWidthF(width)
                painter.setPen(pen)
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        
        # 繪製當前筆劃（使用當前選擇的顏色）
        if self.current_tool == ToolType.PEN and self.current_stroke_points:
            pen = QPen(self.current_color, 2)  # 🆕 使用當前顏色
            painter.setPen(pen)
            
            for i in range(len(self.current_stroke_points) - 1):
                x1, y1, p1 = self.current_stroke_points[i]
                x2, y2, p2 = self.current_stroke_points[i + 1]
                width = 1 + p1 * 5
                pen.setWidthF(width)
                painter.setPen(pen)
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        
        # 🆕🆕🆕 優化 3：橡皮擦紅點使用簡化繪製（只繪製最後 5 個點）
        if self.current_tool == ToolType.ERASER and self.current_eraser_points:
            pen = QPen(QColor(255, 0, 0, 150), 2)
            painter.setPen(pen)
            painter.setBrush(QColor(255, 0, 0, 80))
            
            # 只繪製最後 5 個點（減少繪製量）
            recent_points = self.current_eraser_points[-5:]
            
            for x, y in recent_points:
                painter.drawEllipse(
                    int(x - self.eraser_tool.radius),
                    int(y - self.eraser_tool.radius),
                    int(self.eraser_tool.radius * 2),
                    int(self.eraser_tool.radius * 2)
                )
        
        # 狀態列顯示
        painter.setPen(QPen(QColor(100, 100, 100)))
        
        drawing_type = self.current_drawing_info.get('drawing_type', 'N/A') if self.current_drawing_info else 'N/A'
        
        if self.last_point_data:
            x_pixel = self.last_point_data['x'] * self.width()
            y_pixel = self.last_point_data['y'] * self.height()
            stats_text = (
                f"類型: {drawing_type} | "
                f"工具: {self.current_tool.value} | "
                f"筆劃數: {len(active_strokes)} | "
                f"總點數: {self.total_points} | "
                f"壓力: {self.current_pressure:.3f} | "
                f"位置: ({x_pixel:.0f}, {y_pixel:.0f})"
            )
        else:
            stats_text = (
                f"類型: {drawing_type} | "
                f"工具: {self.current_tool.value} | "
                f"筆劃數: {len(active_strokes)} | "
                f"總點數: {self.total_points} | "
                f"壓力: {self.current_pressure:.3f} | 位置: N/A"
            )
        
        # 🆕 可選：在畫布底部顯示狀態文字（如果需要的話）
        # painter.drawText(10, self.height() - toolbar_height - 10, stats_text)


        
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
    
    # 🆕🆕🆕 先選擇 Workspace
    workspace_dialog = WorkspaceSelectionDialog()
    
    # ✅ 修正：處理取消情況
    if workspace_dialog.exec_() != QDialog.Accepted:
        print("❌ 用戶取消選擇 Workspace，程式結束")
        ink_system.stop_processing()  # ✅ 停止墨水系統
        return  # ✅ 直接返回，不啟動 app.exec_()
    
    workspace = workspace_dialog.selected_workspace
    print(f"✅ 已載入 Workspace: {workspace.project_name}")
    
    # 🆕🆕🆕 傳遞 workspace 到 canvas
    canvas = WacomDrawingCanvas(ink_system, config, workspace)

    print("✅ LSL 時間源已設置")

    canvas.show()

    print("\n" + "=" * 60)
    print("🎨 使用說明:")
    print("   1. 已載入 Workspace 配置") 
    print("   2. 輸入受試者資訊")
    print("   3. 選擇繪畫類型（根據 Workspace 配置）")
    print("   4. 完成繪畫後點擊「新繪畫」按鈕")
    print("   5. 關閉視窗結束所有測試")
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
