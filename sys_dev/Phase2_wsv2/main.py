# main.py
import ctypes          # 🆕 用於 Windows 螢幕旋轉 API
import ctypes.wintypes # 🆕
from PyQt5 import sip
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

# ============================================================
# 🆕 螢幕旋轉管理器（Windows API）
# ============================================================
class ScreenRotationManager:
    """
    管理副螢幕旋轉（透過 Windows ChangeDisplaySettingsEx API）
    
    方向對應：
      DMDO_DEFAULT  = 0  → 橫向 (Landscape)
      DMDO_90       = 1  → 直向 (Portrait，順時針 90°)
      DMDO_180      = 2  → 橫向倒置
      DMDO_270      = 3  → 直向倒置
    """
    DMDO_DEFAULT = 0   # 橫向
    DMDO_90      = 1   # 直向（順時針 90°）

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger('ScreenRotationManager')
        self._original_orientation = None   # 程式啟動前的原始方向
        self._device_name = None            # 副螢幕裝置名稱
        self._current_orientation = None    # 目前套用的方向

    # ── 內部常數 ──────────────────────────────────────────────
    _DM_DISPLAYORIENTATION = 0x00000080
    _CDS_UPDATEREGISTRY    = 0x00000001
    _CDS_RESET             = 0x40000000
    _DISP_CHANGE_SUCCESSFUL = 0

    def _get_devmode(self, device_name: str):
        """取得指定裝置的 DEVMODE 結構"""
        import ctypes
        dm = ctypes.create_string_buffer(220)  # sizeof DEVMODE
        # 設定 dmSize
        ctypes.cast(dm, ctypes.POINTER(ctypes.c_uint16))[0] = 220
        if ctypes.windll.user32.EnumDisplaySettingsW(device_name, -1, dm):
            return dm
        return None

    def _get_orientation_from_devmode(self, dm) -> int:
        """從 DEVMODE 取得目前方向值"""
        import ctypes, struct
        # dmDisplayOrientation 在 DEVMODE 的偏移量為 164 (bytes)
        orientation = struct.unpack_from('<I', dm, 164)[0]
        return orientation

    def _set_orientation(self, device_name: str, orientation: int) -> bool:
        import ctypes, struct
        try:
            dm = self._get_devmode(device_name)
            if dm is None:
                self.logger.error(f"❌ 無法取得裝置 DEVMODE: {device_name}")
                return False

            current_orientation = self._get_orientation_from_devmode(dm)
            if current_orientation == orientation:
                self.logger.info(f"✅ 螢幕方向已是目標方向 ({orientation})，無需旋轉")
                return True

            width  = struct.unpack_from('<I', dm, 156)[0]
            height = struct.unpack_from('<I', dm, 160)[0]
            struct.pack_into('<I', dm, 156, height)
            struct.pack_into('<I', dm, 160, width)
            struct.pack_into('<I', dm, 164, orientation)

            fields = struct.unpack_from('<I', dm, 40)[0]
            fields |= self._DM_DISPLAYORIENTATION
            struct.pack_into('<I', dm, 40, fields)

            # ── 第一次嘗試：寫入登錄檔（需管理員）──
            result = ctypes.windll.user32.ChangeDisplaySettingsExW(
                device_name, dm, None,
                self._CDS_UPDATEREGISTRY,
                None
            )

            if result == self._DISP_CHANGE_SUCCESSFUL:
                self.logger.info(
                    f"✅ 螢幕旋轉成功（已寫入登錄檔）: {device_name} → orientation={orientation}"
                )
                return True

            # ── 第二次嘗試：暫時旋轉（不需管理員，旗標=0）──
            self.logger.warning(
                f"⚠️ 寫入登錄檔失敗（錯誤碼: {result}），改用暫時旋轉模式（旗標=0）"
            )

            # 重新取得 DEVMODE（第一次呼叫可能已修改緩衝區狀態）
            dm2 = self._get_devmode(device_name)
            if dm2 is None:
                self.logger.error("❌ 無法重新取得 DEVMODE")
                return False

            # 再次設定旋轉參數
            w2 = struct.unpack_from('<I', dm2, 156)[0]
            h2 = struct.unpack_from('<I', dm2, 160)[0]
            struct.pack_into('<I', dm2, 156, h2)
            struct.pack_into('<I', dm2, 160, w2)
            struct.pack_into('<I', dm2, 164, orientation)
            fields2 = struct.unpack_from('<I', dm2, 40)[0]
            fields2 |= self._DM_DISPLAYORIENTATION
            struct.pack_into('<I', dm2, 40, fields2)

            result2 = ctypes.windll.user32.ChangeDisplaySettingsExW(
                device_name, dm2, None,
                0,   # ✅ 旗標=0：暫時套用，不寫入登錄檔，不需管理員
                None
            )

            if result2 == self._DISP_CHANGE_SUCCESSFUL:
                self.logger.info(
                    f"✅ 螢幕暫時旋轉成功（不寫入登錄檔）: {device_name} → orientation={orientation}"
                )
                return True
            else:
                self.logger.error(f"❌ 螢幕旋轉失敗，錯誤碼: {result2}")
                return False

        except Exception as e:
            self.logger.error(f"❌ 螢幕旋轉例外: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False


    def save_original_and_apply(self, device_name: str, target_orientation: str) -> bool:
        """
        儲存原始方向並套用新方向
        
        Args:
            device_name: 副螢幕裝置名稱
            target_orientation: "landscape" 或 "portrait"
        
        Returns:
            bool: 是否成功
        """
        self._device_name = device_name

        # 儲存原始方向（只儲存一次）
        if self._original_orientation is None:
            dm = self._get_devmode(device_name)
            if dm is not None:
                self._original_orientation = self._get_orientation_from_devmode(dm)
                self.logger.info(f"📌 已儲存原始螢幕方向: {self._original_orientation}")

        # 套用目標方向
        target_dmdo = (self.DMDO_90 if target_orientation == "portrait"
                       else self.DMDO_DEFAULT)
        success = self._set_orientation(device_name, target_dmdo)
        if success:
            self._current_orientation = target_dmdo
        return success

    def apply_orientation(self, target_orientation: str) -> bool:
        """
        套用方向（使用已儲存的裝置名稱）
        
        Args:
            target_orientation: "landscape" 或 "portrait"
        """
        if self._device_name is None:
            self.logger.warning("⚠️ 尚未設定裝置名稱，無法旋轉")
            return False
        target_dmdo = (self.DMDO_90 if target_orientation == "portrait"
                       else self.DMDO_DEFAULT)
        if self._current_orientation == target_dmdo:
            return True  # 已是目標方向，不需重複旋轉
        success = self._set_orientation(self._device_name, target_dmdo)
        if success:
            self._current_orientation = target_dmdo
        return success

    def restore_original(self) -> bool:
        """恢復到程式啟動前的原始方向"""
        if self._original_orientation is None or self._device_name is None:
            self.logger.info("ℹ️ 無需恢復（未儲存原始方向）")
            return True
        success = self._set_orientation(self._device_name, self._original_orientation)
        if success:
            self.logger.info(f"✅ 已恢復原始螢幕方向: {self._original_orientation}")
        return success

    @staticmethod
    def get_secondary_device_name() -> str:
        """
        取得副螢幕的裝置名稱（例如 "\\\\.\\DISPLAY2"）
        
        Returns:
            str: 裝置名稱，找不到時回傳空字串
        """
        import ctypes, struct
        try:
            for i in range(10):
                dd = ctypes.create_string_buffer(840)
                ctypes.cast(dd, ctypes.POINTER(ctypes.c_uint32))[0] = 840
                if not ctypes.windll.user32.EnumDisplayDevicesW(None, i, dd, 0):
                    break
                # StateFlags 在偏移量 8
                state_flags = struct.unpack_from('<I', dd, 8)[0]
                DISPLAY_DEVICE_ATTACHED_TO_DESKTOP = 0x00000001
                DISPLAY_DEVICE_PRIMARY_DEVICE       = 0x00000004
                is_attached = bool(state_flags & DISPLAY_DEVICE_ATTACHED_TO_DESKTOP)
                is_primary  = bool(state_flags & DISPLAY_DEVICE_PRIMARY_DEVICE)
                if is_attached and not is_primary:
                    # DeviceName 從偏移量 0 開始，長度 32 個 wchar
                    device_name = dd[0:64].decode('utf-16-le').rstrip('\x00')
                    return device_name
        except Exception:
            pass
        return ""
# ============================================================
# 🆕 繪畫成品展示視窗（副螢幕全螢幕）
# ============================================================
class ArtworkDisplayWindow(QWidget):
    """
    在副螢幕全螢幕展示當前繪畫成品（不影響 LSL 記錄）
    直接從 all_strokes 繪製，不需匯出 PNG
    """

    def __init__(self, all_strokes: list, canvas_width: int, canvas_height: int,
                 secondary_screen, toolbar_size: int, orientation: str,
                 is_single_screen: bool = False,
                 on_close_callback=None,
                 parent=None):
        super().__init__(parent)
        self.all_strokes = all_strokes
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.secondary_screen = secondary_screen
        self.toolbar_size = toolbar_size
        self.orientation = orientation
        self.is_single_screen = is_single_screen
        self.on_close_callback = on_close_callback
        self.logger = logging.getLogger('ArtworkDisplayWindow')

        self.setStyleSheet("background-color: white;")

        if self.is_single_screen:
            self.setWindowTitle("🖼️ 繪畫成品預覽")
            self.setWindowFlags(
                Qt.Window
                | Qt.WindowTitleHint
                | Qt.WindowCloseButtonHint
                | Qt.WindowStaysOnTopHint
            )

            screen_w = secondary_screen.width()
            screen_h = secondary_screen.height()
            win_w = int(screen_w * 0.50)
            win_h = int(screen_h * 0.60)
            x = secondary_screen.x() + 10
            y = secondary_screen.y() + (screen_h - win_h) // 2
            self.resize(win_w, win_h)
            self.move(x, y)
            self.show()
            self.raise_()            # ✅ 確保視窗在最前面
            self.activateWindow()    # ✅ 確保視窗可接收滑鼠/鍵盤事件
            self.logger.info(
                f"🖼️ 成品展示視窗已開啟（單螢幕普通視窗）: {win_w}x{win_h} at ({x},{y})"
            )

        else:
            # 延伸模式：副螢幕全螢幕 + 無邊框 + 置頂
            self.setWindowFlags(
                Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
            )
            self.move(secondary_screen.x(), secondary_screen.y())
            self.showFullScreen()
            self.logger.info("🖼️ 成品展示視窗已開啟（延伸模式全螢幕）")

    def keyPressEvent(self, event):
        """ESC 鍵關閉展示視窗（延伸模式用）"""
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """關閉時通知 callback"""
        if self.on_close_callback is not None:
            try:
                self.on_close_callback()
            except Exception:
                pass
        event.accept()

    def paintEvent(self, event):
        """繪製所有筆劃（支援直向 Qt 旋轉）"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor('white'))

        if self.orientation == "portrait":
            # ✅ 直向模式：與 WacomDrawingCanvas.paintEvent 相同的旋轉邏輯
            # 工具列在左側（不旋轉），畫布區域旋轉 -90°
            # translate(toolbar_size, H) → rotate(-90)
            h = self.height()
            painter.translate(self.toolbar_size, h)
            painter.rotate(-90)
        else:
            # 橫向：工具列在左側，畫布向右偏移
            painter.translate(self.toolbar_size, 0)

        active_strokes = [s for s in self.all_strokes if not s.get('is_deleted', False)]

        for stroke in active_strokes:
            points = stroke['points']
            if not points:
                continue

            stroke_color = QColor(stroke.get('color', '#000000'))
            pen = QPen(stroke_color, 2)
            painter.setPen(pen)

            for i in range(len(points) - 1):
                x1, y1, p1 = points[i]
                x2, y2, p2 = points[i + 1]
                pen.setWidthF(1 + p1 * 5)
                painter.setPen(pen)
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))


class ExperimenterControlWindow(QWidget):
    """實驗者控制視窗（顯示在主螢幕）"""
    
    def __init__(self, canvas, primary_screen, is_extended_mode):
        super().__init__()
        self.canvas = canvas
        self.primary_screen = primary_screen
        self.is_extended_mode = is_extended_mode
        self.logger = logging.getLogger('ExperimenterControlWindow')
        
        # ✅ 碼表相關
        self._elapsed_seconds = 0          # 已計時秒數
        self._timer = QTimer(self)
        self._timer.setInterval(1000)      # 每 1 秒觸發一次
        self._timer.timeout.connect(self._on_timer_tick)
        
        self._setup_ui()
        self._setup_window_position()
    
    def _setup_ui(self):
        """設置 UI"""
        self.setWindowTitle("施測者控制面板")
        self.setFixedSize(600, 460)  # ✅ 移除重置按鈕後高度從 500 改回 460
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)
        
        # === 資訊顯示區域 ===
        info_layout = QVBoxLayout()
        info_layout.setSpacing(15)
        
        label_style = "font-size: 24px; font-weight: bold;"
        # value_style = "font-size: 24px; font-weight: bold; color: #2196F3;"
        value_style = "font-size: 24px; font-weight: bold;"
        self.subject_label = QLabel("受試者編號: N/A")
        self.subject_label.setStyleSheet(label_style)
        info_layout.addWidget(self.subject_label)
        
        self.drawing_number_label = QLabel("當前繪畫編號: N/A")
        self.drawing_number_label.setStyleSheet(value_style)
        info_layout.addWidget(self.drawing_number_label)
        
        self.drawing_type_label = QLabel("當前繪畫類型: N/A")
        self.drawing_type_label.setStyleSheet(label_style)
        info_layout.addWidget(self.drawing_type_label)
        
        main_layout.addLayout(info_layout)
        
        # 分隔線
        line1 = QWidget()
        line1.setFixedHeight(4)
        line1.setStyleSheet("background-color: #cccccc;")
        main_layout.addWidget(line1)
        
        # ✅ === 碼表區域 ===
        stopwatch_layout = QHBoxLayout()
        stopwatch_layout.setSpacing(15)

        # 碼表標籤
        stopwatch_title = QLabel("作畫用時:")
        stopwatch_title.setStyleSheet("font-size: 24px; font-weight: bold;")
        stopwatch_layout.addWidget(stopwatch_title)

        # 碼表顯示（分鐘:秒）
        self.stopwatch_label = QLabel("00:00")
        self.stopwatch_label.setStyleSheet("""
            font-size: 36px;
            font-weight: bold;
            color: #000000;
            font-family: monospace;
        """)
        stopwatch_layout.addWidget(self.stopwatch_label)

        stopwatch_layout.addStretch()
        main_layout.addLayout(stopwatch_layout)

        
        # 分隔線
        line2 = QWidget()
        line2.setFixedHeight(4)
        line2.setStyleSheet("background-color: #cccccc;")
        main_layout.addWidget(line2)
        
        # === 控制按鈕區域 ===
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)
        
        btn_height = 80
        btn_font_size = "24px"
        
        self.new_drawing_button = QPushButton("➕ 新繪畫")
        self.new_drawing_button.setFixedHeight(btn_height)
        self.new_drawing_button.setStyleSheet(f"""
            QPushButton {{
                font-size: {btn_font_size};
                font-weight: bold;
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background-color: #e0e0e0;
            }}
            QPushButton:pressed {{
                background-color: #c0c0c0;
            }}
        """)

        self.new_drawing_button.clicked.connect(self.on_new_drawing_clicked)
        button_layout.addWidget(self.new_drawing_button)
        
        self.close_button = QPushButton("❌ 關閉程式")
        self.close_button.setFixedHeight(btn_height)
        self.close_button.setStyleSheet(f"""
            QPushButton {{
                font-size: {btn_font_size};
                font-weight: bold;
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background-color: #e0e0e0;
            }}
            QPushButton:pressed {{
                background-color: #c0c0c0;
            }}
        """)

        self.close_button.clicked.connect(self.on_close_clicked)
        button_layout.addWidget(self.close_button)
        
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)

    # ✅ === 碼表方法 ===

    def start_stopwatch(self):
        """啟動碼表（重置並開始計時）"""
        self._elapsed_seconds = 0
        self.stopwatch_label.setText("00:00")
        self._timer.start()
        self.logger.info("⏱ 碼表已啟動")

    def stop_stopwatch(self):
        """停止碼表"""
        self._timer.stop()
        self.logger.info(f"⏱ 碼表已停止: {self.stopwatch_label.text()}")

    def reset_stopwatch(self):
        """重置碼表（停止並歸零）"""
        self._timer.stop()
        self._elapsed_seconds = 0
        self.stopwatch_label.setText("00:00")
        self.logger.info("⏱ 碼表已重置")

    def _on_timer_tick(self):
        """每秒觸發，更新碼表顯示"""
        self._elapsed_seconds += 1
        minutes = self._elapsed_seconds // 60
        seconds = self._elapsed_seconds % 60
        self.stopwatch_label.setText(f"{minutes:02d}:{seconds:02d}")

    # ✅ === 原有方法（不變）===

    def _setup_window_position(self):
        """設置視窗位置（主螢幕右上角）"""
        if self.is_extended_mode:
            x = self.primary_screen.x() + self.primary_screen.width() - self.width() - 20
            y = self.primary_screen.y() + 20
            self.move(x, y)
            self.logger.info(f"✅ 控制視窗已設置在主螢幕右上角: ({x}, {y})")
        else:
            x = self.primary_screen.width() - self.width() - 20
            y = 20
            self.move(x, y)
            self.logger.info(f"✅ 控制視窗已設置在螢幕右上角: ({x}, {y})")
        
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
    
    def update_info(self, subject_id, drawing_number, drawing_type):
        """更新顯示的資訊"""
        self.subject_label.setText(f"受試者編號: {subject_id}")
        self.drawing_number_label.setText(f"當前繪畫編號: {drawing_number}")
        self.drawing_type_label.setText(f"當前繪畫類型: {drawing_type}")
        self.logger.info(f"📝 控制面板資訊已更新: {subject_id}, #{drawing_number}, {drawing_type}")
    
    def on_new_drawing_clicked(self):
        """新繪畫按鈕點擊事件"""
        self.logger.info("🎨 點擊新繪畫按鈕")
        self.stop_stopwatch()          # ✅ 按下按鈕時先暫停碼表
        self.canvas.start_new_drawing()

    
    def on_close_clicked(self):
        """關閉程式按鈕點擊事件"""
        self.logger.info("❌ 點擊關閉程式按鈕")
        
        reply = QMessageBox.question(
            self,
            '確認關閉',
            '是否確定關閉程式?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.logger.info("✅ 用戶確認關閉程式")
            self.canvas.close()
            self.close()
    
    def closeEvent(self, event):
        """控制視窗關閉時同時關閉畫布"""
        self.logger.info("🔚 控制視窗關閉")
        self._timer.stop()  # ✅ 關閉時停止計時器
        if self.canvas:
            self.canvas.close()
        event.accept()

# main.py (WacomDrawingCanvas.__init__ 修改)

class WacomDrawingCanvas(QWidget):
    def __init__(self, ink_system, config: ProcessingConfig, workspace: WorkspaceConfig = None):
        super().__init__()
        self._should_restart = False  # 🆕

        self.ink_system = ink_system
        self.config = config
        
        self.logger = logging.getLogger('WacomDrawingCanvas')
        
        if workspace is None:
            workspace = get_default_workspace()
        self.workspace = workspace
        self.current_test_config = None
        
        self.current_color = QColor('#000000')
        self.current_color_name = self.current_color.name()

        self.primary_screen, self.secondary_screen, self.is_extended_mode = self._detect_screens()
        self._setup_screen_size()
        
        self.subject_info = None
        self.current_drawing_info = None
        self.drawing_counter = 1
        
        self.current_stroke_points = []
        self.all_strokes = []
        self.stroke_count = 0
        self.total_points = 0
        
        self.last_point_data = None
        self.pen_is_in_canvas = False
        self.pen_is_touching = False
        self.current_pressure = 0.0
        
        self.current_tool = ToolType.PEN
        self.eraser_tool = EraserTool(radius=10.0)
        self.current_eraser_points = []
        self.next_stroke_id = 0
        # 🆕 螢幕旋轉管理器
        self.screen_rotation_manager = ScreenRotationManager(self.logger)
        if self.is_extended_mode:
            device_name = ScreenRotationManager.get_secondary_device_name()
            if device_name:
                self.logger.info(f"🖥️ 副螢幕裝置名稱: {device_name}")
                self.screen_rotation_manager._device_name = device_name
                # 儲存原始方向（尚未旋轉）
                dm = self.screen_rotation_manager._get_devmode(device_name)
                if dm:
                    self.screen_rotation_manager._original_orientation = \
                        self.screen_rotation_manager._get_orientation_from_devmode(dm)
                    self.logger.info(
                        f"📌 原始螢幕方向已儲存: "
                        f"{self.screen_rotation_manager._original_orientation}"
                    )

        # 🆕 成品展示視窗參考
        self._artwork_display_window = None

        # 🆕🆕🆕 修改：第一次取消則退出程式
        if not self.get_subject_info():
            self.logger.info("❌ 受試者資訊取消，返回 Workspace 選擇")
            self._should_restart = True   # 🆕 旗標
            return                        # 🆕 提早返回，不繼續初始化

        
        # 🆕🆕🆕 修改：第一次取消則退出程式
        if not self.get_drawing_type():
            self.logger.critical("❌ 第一次未選擇繪畫類型，程式退出")
            # 🆕 停止墨水系統
            if self.ink_system:
                self.ink_system.stop_processing()
                self.ink_system.shutdown()
            # 🆕 退出應用（不顯示錯誤訊息）
            QApplication.quit()
            sys.exit(0)  # 🆕 確保終端機輸出停止
        
        self._setup_window()
        self._update_window_title()
        self._setup_toolbar()
        
        self.control_window = None
        self._create_control_window()
        self._update_cursor()
        
        self.logger.info("✅ WacomDrawingCanvas 初始化完成")
        
        self._initialize_lsl()
        
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
    def _wait_for_screen_rotation(self, expected_orientation: str, timeout: float = 3.0) -> bool:
        """
        ✅ Wacom 不支援軟體旋轉，改用 Qt 畫面旋轉
        此方法只更新 secondary_screen 資訊，不等待實體旋轉
        """
        from PyQt5.QtWidgets import QDesktopWidget
        from PyQt5.QtCore import QCoreApplication

        QCoreApplication.processEvents()

        desktop = QDesktopWidget()
        if desktop.screenCount() > 1:
            self.secondary_screen = desktop.screenGeometry(1)

        self.logger.info(
            f"📐 螢幕資訊更新（{expected_orientation}，Qt旋轉模式）: "
            f"{self.secondary_screen.width()}x{self.secondary_screen.height()}"
        )
        return True


    def _setup_screen_size(self, orientation: str = "landscape"):
        """根據螢幕模式和方向設置畫布尺寸（Qt旋轉版）"""
        toolbar_size = 120

        if self.is_extended_mode:
            screen_w = self.secondary_screen.width()
            screen_h = self.secondary_screen.height()

            if orientation == "portrait":
                # ✅ 螢幕不旋轉，Qt 畫面旋轉 -90°
                # 實體螢幕橫向 (screen_w x screen_h)，例如 1920x1080
                # 旋轉後邏輯畫布：寬=screen_h，高=screen_w-toolbar
                canvas_width  = screen_h                  # 邏輯寬 = 實體短邊
                canvas_height = screen_w - toolbar_size   # 邏輯高 = 實體長邊 - toolbar
            else:
                canvas_width  = screen_w - toolbar_size
                canvas_height = screen_h

            self.logger.info(
                f"📐 畫布尺寸（延伸模式 - {orientation}）: {canvas_width} x {canvas_height}"
            )
        else:
            desktop = QDesktopWidget()
            screen_rect = desktop.availableGeometry()
            canvas_width  = screen_rect.width() - toolbar_size
            canvas_height = screen_rect.height()
            self.logger.info(f"📐 畫布尺寸（單螢幕模式）: {canvas_width} x {canvas_height}")

        self.config.canvas_width  = canvas_width
        self.config.canvas_height = canvas_height
        self._current_toolbar_size = toolbar_size


        
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
        """獲取受試者資訊"""
        dialog = SubjectInfoDialog(self)
        
        if self.is_extended_mode:
            dialog_width = dialog.width()
            dialog_height = dialog.height()
            x = self.primary_screen.x() + (self.primary_screen.width() - dialog_width) // 2
            y = self.primary_screen.y() + (self.primary_screen.height() - dialog_height) // 2
            dialog.move(x, y)
        
        if dialog.exec_() == dialog.Accepted:
            self.subject_info = dialog.subject_info
            self.logger.info(f"✅ 受試者資訊: {self.subject_info}")
            
            # 🆕🆕🆕 使用第一層目錄（受試者ID_姓名_生日）
            from SubjectInfoDialog import save_workspace_config_summary
            base_output_dir = "./wacom_recordings"
            subject_root_dir = os.path.join(
                base_output_dir,
                self.subject_info['subject_folder_name']  # 🆕 改用 subject_folder_name
            )
            os.makedirs(subject_root_dir, exist_ok=True)
            save_workspace_config_summary(self.workspace, subject_root_dir)
            
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
        dialog = DrawingTypeDialog(self.drawing_counter, self.workspace,
                           canvas_ref=None, parent=self)  # 🆕 初次不傳 canvas_ref

        
        if self.is_extended_mode:
            dialog_width = dialog.width()
            dialog_height = dialog.height()
            x = self.primary_screen.x() + (self.primary_screen.width() - dialog_width) // 2
            y = self.primary_screen.y() + (self.primary_screen.height() - dialog_height) // 2
            dialog.move(x, y)
            self.logger.info(f"🎨 繪畫類型對話框顯示在主螢幕: ({x}, {y})")
        else:
            self.logger.info("🎨 繪畫類型對話框顯示在螢幕中央（單螢幕模式）")
        
        # 🆕🆕🆕 修復：如果取消，返回 False（不退出程式）
        if dialog.exec_() == dialog.Accepted:
            self.current_drawing_info = dialog.drawing_info
            
            drawing_type = self.current_drawing_info['drawing_type']
            for test in self.workspace.drawing_sequence:
                if test.drawing_type == drawing_type:
                    self.current_test_config = test
                    break
            
            self.logger.info(f"✅ 繪畫資訊: {self.current_drawing_info}")
            self.logger.info(f"✅ 測試配置: {self.current_test_config.display_name}")
            
            # ✅ 在顯示指導語前先旋轉螢幕，並等待完成
            if self.is_extended_mode and self.screen_rotation_manager._device_name:
                orientation = self.current_test_config.screen_orientation
                self.logger.info(f"🖥️ 預先套用螢幕方向（指導語前）: {orientation}")
                self.screen_rotation_manager.save_original_and_apply(
                    self.screen_rotation_manager._device_name, orientation
                )
                self._wait_for_screen_rotation(orientation)  # ✅ 確保指導語顯示在正確方向

            
            if not self._show_instructions(self.current_test_config):
                self.logger.info("❌ 指導語確認取消，程式退出")
                return False
            return True
        else:
            # 🆕🆕🆕 用戶取消，返回 False（不退出程式）
            self.logger.info("❌ 用戶取消選擇繪畫類型")
            return False
    
    def _initialize_lsl(self):
        """初始化LSL整合（🆕 使用三層目錄結構）"""
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
        
        base_output_dir = "./wacom_recordings"
        
        # 🆕🆕🆕 三層目錄結構
        # 第一層：受試者ID_姓名_生日
        subject_root_dir = os.path.join(
            base_output_dir,
            self.subject_info['subject_folder_name']
        )
        # 第二層：受試者ID_姓名_收案年月日_時間
        session_dir = os.path.join(
            subject_root_dir,
            self.subject_info['session_folder_name']
        )
        # 第三層：編號_繪畫類型_收案年月日_時間
        drawing_dir = os.path.join(
            session_dir,
            self.current_drawing_info['folder_name']
        )
        
        os.makedirs(drawing_dir, exist_ok=True)
        
        self.lsl = LSLIntegration(
            stream_config=lsl_config,
            output_dir=drawing_dir
        )
        
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
                'display_mode': 'extended' if self.is_extended_mode else 'single',
                'drawing_test_config': {
                    'drawing_type': self.current_test_config.drawing_type,
                    'display_name': self.current_test_config.display_name,
                    'order': self.current_test_config.order,
                    'enabled_tools': {
                        'pen': self.current_test_config.toolbar.pen_enabled,
                        'eraser': self.current_test_config.toolbar.eraser_enabled,
                        'color_picker': self.current_test_config.toolbar.color_picker_enabled
                    },
                    'color_picker_mode': self.current_test_config.toolbar.color_picker_mode.value,
                    'constraints': {
                        'time_limit_enabled': self.current_test_config.constraints.time_limit_enabled,
                        'time_limit_seconds': self.current_test_config.constraints.time_limit_seconds,
                        'stroke_limit_enabled': self.current_test_config.constraints.stroke_limit_enabled,
                        'stroke_limit_count': self.current_test_config.constraints.stroke_limit_count
                    }
                }
            }
        )
        
        self._setup_logging_to_file(session_id, drawing_dir)
        
        self.ink_system.set_time_source(self.lsl.stream_manager.get_stream_time)
        self.logger.info("✅ 墨水系統時間源已設置為 LSL 時間")

    def _show_instructions(self, test_config):
        """
        選定繪畫類型後顯示指導語。
        
        流程：
        1. 若有施測者指導語檔案 → 用系統預設程式開啟（主螢幕）
        2. 若有受試者指導語檔案 → 在副螢幕顯示對話框，等待確認
        
        Returns:
            bool: True 表示繼續，False 表示使用者取消
        """
        import subprocess, platform
        from SubjectInfoDialog import ParticipantInstructionDialog
        
        exp_file = test_config.instructions.experimenter_instruction_file
        par_file = test_config.instructions.participant_instruction_file
        
        # ── 1. 施測者指導語：用系統預設程式開啟 ──
        if exp_file and os.path.exists(exp_file):
            try:
                if platform.system() == 'Windows':
                    os.startfile(exp_file)
                elif platform.system() == 'Darwin':
                    subprocess.Popen(['open', exp_file])
                else:
                    subprocess.Popen(['xdg-open', exp_file])
                self.logger.info(f"📄 已開啟施測者指導語: {exp_file}")
            except Exception as e:
                self.logger.error(f"❌ 開啟施測者指導語失敗: {e}")
                QMessageBox.warning(self, "警告", f"無法開啟施測者指導語檔案：\n{e}")
        elif exp_file:
            self.logger.warning(f"⚠️ 施測者指導語檔案不存在: {exp_file}")
            QMessageBox.warning(self, "警告", f"施測者指導語檔案不存在：\n{exp_file}")
        
        # ── 2. 受試者指導語：在副螢幕顯示對話框 ──
        if par_file and os.path.exists(par_file):
            dialog = ParticipantInstructionDialog(
                instruction_file=par_file,
                drawing_type_name=test_config.display_name,
                parent=self
            )
            
            if self.is_extended_mode:
                # ✅ 設定旋轉角度（必須在 showFullScreen 前呼叫）
                orientation = test_config.screen_orientation
                if orientation == "portrait":
                    dialog.set_rotation(-90)
                dialog.move(self.secondary_screen.x(), self.secondary_screen.y())
                dialog.showFullScreen()  # ✅ 內部會自動根據 rotation 重建 UI


            else:
                # 單螢幕模式：最大化視窗
                dialog.showMaximized()
            
            self.logger.info(f"📋 顯示受試者指導語: {par_file}")
            result = dialog.exec_()
            
            if result != QDialog.Accepted:
                self.logger.info("❌ 受試者取消指導語確認")
                return False
            
            self.logger.info("✅ 受試者已確認指導語")
        elif par_file:
            self.logger.warning(f"⚠️ 受試者指導語檔案不存在: {par_file}")
            QMessageBox.warning(self, "警告", f"受試者指導語檔案不存在：\n{par_file}")
        
        return True
        
    def start_new_drawing(self):
        # 先不中止當前繪畫，但時間暫停，等待用戶確認或取消
        try:
            self.logger.info("🎨 準備開始新繪畫")
            next_drawing_counter = self.drawing_counter + 1

            # ✅ 1. 先強制結束當前筆劃
            self._force_end_current_stroke()

            # ✅ 2. 暫停 LSL 記錄（對話框期間不記錄數據）
            if hasattr(self, 'lsl') and self.lsl is not None:
                self.lsl.pause_recording()
                self.logger.info("⏸️ LSL 記錄已暫停（等待用戶選擇）")

            dialog = DrawingTypeDialog(next_drawing_counter, self.workspace,
                           canvas_ref=self, parent=self)  # 🆕 傳入 canvas_ref

            
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
                # ✅ 3a. 用戶取消 → 恢復記錄，繼續當前繪畫
                if hasattr(self, 'lsl') and self.lsl is not None:
                    self.lsl.resume_recording()
                    self.logger.info("▶️ 用戶取消，LSL 記錄已恢復")
                self.logger.info("❌ 用戶取消新繪畫，繼續當前繪畫")
                # ✅ 用戶取消 → 恢復碼表繼續計時
                if self.control_window:
                    self.control_window._timer.start()
                    self.logger.info("▶️ 用戶取消，碼表已恢復計時")
                return

            
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
            # 🆕 6.3 套用新測驗的螢幕方向
            if self.is_extended_mode:
                new_orientation = self.current_test_config.screen_orientation
                self.logger.info(f"🖥️ 套用螢幕方向: {new_orientation}")
                self.screen_rotation_manager.apply_orientation(new_orientation)
                # ✅ 等待旋轉完成並自動更新 secondary_screen
                self._wait_for_screen_rotation(new_orientation)
                self._setup_screen_size(new_orientation)
                self._rebuild_toolbar(new_orientation)



            # 6.5 顯示指導語（若有設定）
            if not self._show_instructions(self.current_test_config):
                self.logger.info("❌ 指導語確認取消，恢復當前繪畫")
                # 恢復計數器（因為已提前遞增）
                self.drawing_counter = self.drawing_counter  # 此時尚未賦值，不需回退
                return
            # 7. 更新視窗標題
            self._update_window_title()
            
            # 8. 重置畫布狀態
            self._reset_canvas_state()
            
            # 9. 重新初始化LSL（新目錄）
            self._initialize_lsl()
            
            # 10. 重新設置墨水系統
            self._reset_ink_system()
                    
            # 🆕🆕🆕 11. 更新顏色按鈕可見性
            self._update_toolbar_buttons_visibility()
                    
            self.logger.info(f"✅ 新繪畫已開始 (繪畫編號: {self.drawing_counter})")
            
            # 🆕🆕🆕 更新控制視窗資訊
            if self.control_window:
                subject_id = self.subject_info.get('subject_id', 'N/A')
                drawing_number = self.drawing_counter
                drawing_type = self.current_drawing_info.get('drawing_type', 'N/A')
                self.control_window.update_info(subject_id, drawing_number, drawing_type)
                self.control_window.start_stopwatch()  # ✅ 新繪畫開始時重啟碼表
            
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
        # 🆕 初始化工具列方向記錄（預設橫向）
        self._toolbar_orientation = "landscape"
        self._toolbar_size = 120

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
        
        toolbar_layout.addWidget(self.eraser_button, alignment=Qt.AlignCenter)  # 橡皮擦在上
        toolbar_layout.addWidget(self.pen_button,    alignment=Qt.AlignCenter)  # 筆在下
        toolbar_layout.addWidget(self.color_button,  alignment=Qt.AlignCenter)

        # 🆕🆕🆕 根據繪畫類型決定是否顯示顏色按鈕
        self._update_toolbar_buttons_visibility()
        
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
        # 🆕 套用第一個測驗的螢幕方向
        if self.current_test_config is not None and self.is_extended_mode:
            orientation = self.current_test_config.screen_orientation
            if orientation == "portrait":
                # ✅ Qt 旋轉模式：不需要旋轉螢幕，直接重建工具列和畫布尺寸
                self._wait_for_screen_rotation(orientation)  # 只更新 secondary_screen 資訊
                self._setup_screen_size(orientation)
                self._rebuild_toolbar(orientation)




    def _rebuild_toolbar(self, orientation: str = "landscape"):
        """
        🆕 根據方向重建工具列佈局
        
        橫向：工具列在左側（垂直排列）
        直向：工具列在上側（水平排列）
        """
        try:
            self.logger.info(f"🔧 重建工具列: orientation={orientation}")

            # 1. 移除舊的 layout（Qt 不能直接刪除 layout，需透過 QWidget 容器）
            old_layout = self.layout()
            if old_layout is not None:
                # 清空舊 layout 中的所有 widget
                while old_layout.count():
                    item = old_layout.takeAt(0)
                    if item.widget():
                        item.widget().setParent(None)
                # 刪除舊 layout
                
                sip.delete(old_layout)

            # 2. 重新建立按鈕（保留原有 signal 連接）
            button_size = 80

            self.pen_button = QPushButton("🖊️")
            self.pen_button.setFixedSize(button_size, button_size)
            self.pen_button.setToolTip("筆")
            self.pen_button.clicked.connect(lambda: self.switch_tool(ToolType.PEN))

            self.eraser_button = QPushButton("🧈")
            self.eraser_button.setFixedSize(button_size, button_size)
            self.eraser_button.setToolTip("橡皮擦")
            self.eraser_button.clicked.connect(lambda: self.switch_tool(ToolType.ERASER))

            self.color_button = QPushButton("🎨")
            self.color_button.setFixedSize(button_size, button_size)
            self.color_button.setToolTip("選擇顏色")
            self.color_button.clicked.connect(self.choose_color)

            # 3. 根據方向建立不同的工具列
            if orientation == "portrait":
                # ✅ 直向：工具列仍在左側（垂直排列），畫布區域用 paintEvent 旋轉
                # 不改變 layout 結構，只記錄方向供 tabletEvent/paintEvent 使用
                toolbar_layout = QVBoxLayout()
                toolbar_layout.setSpacing(20)
                toolbar_layout.setContentsMargins(10, 0, 10, 0)
                toolbar_layout.addStretch()
                toolbar_layout.addWidget(self.eraser_button, alignment=Qt.AlignCenter)
                toolbar_layout.addWidget(self.pen_button,    alignment=Qt.AlignCenter)
                toolbar_layout.addWidget(self.color_button,  alignment=Qt.AlignCenter)

                toolbar_layout.addStretch()

                toolbar_widget = QWidget()
                toolbar_widget.setLayout(toolbar_layout)
                toolbar_widget.setFixedWidth(120)
                toolbar_widget.setStyleSheet("""
                    QWidget {
                        background-color: #f5f5f5;
                        border-right: 2px solid #cccccc;
                    }
                """)

                main_layout = QHBoxLayout()
                main_layout.addWidget(toolbar_widget)   # 左側工具列（不變）
                main_layout.addStretch()
                main_layout.setContentsMargins(0, 0, 0, 0)
                main_layout.setSpacing(0)

                # ✅ 記錄為 portrait，供 tabletEvent/paintEvent 使用
                self._toolbar_orientation = "portrait"
                self._toolbar_size = 120


            else:
                # ── 橫向：工具列在左側（垂直排列）──
                toolbar_layout = QVBoxLayout()
                toolbar_layout.setSpacing(20)
                toolbar_layout.setContentsMargins(10, 0, 10, 0)
                toolbar_layout.addStretch()
                toolbar_layout.addWidget(self.eraser_button, alignment=Qt.AlignCenter)
                toolbar_layout.addWidget(self.pen_button,    alignment=Qt.AlignCenter)
                toolbar_layout.addWidget(self.color_button,  alignment=Qt.AlignCenter)

                toolbar_layout.addStretch()

                toolbar_widget = QWidget()
                toolbar_widget.setLayout(toolbar_layout)
                toolbar_widget.setFixedWidth(120)
                toolbar_widget.setStyleSheet("""
                    QWidget {
                        background-color: #f5f5f5;
                        border-right: 2px solid #cccccc;
                    }
                """)

                main_layout = QHBoxLayout()
                main_layout.addWidget(toolbar_widget)   # 左側工具列
                main_layout.addStretch()
                main_layout.setContentsMargins(0, 0, 0, 0)
                main_layout.setSpacing(0)

                self._toolbar_orientation = "landscape"
                self._toolbar_size = 120

            self.setLayout(main_layout)

            # 4. 更新按鈕樣式和可見性
            self._apply_tool_button_styles()
            self._update_toolbar_buttons_visibility()
            self._update_cursor()

            self.logger.info(f"✅ 工具列重建完成: {orientation}")

        except Exception as e:
            self.logger.error(f"❌ 重建工具列失敗: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _apply_tool_button_styles(self):
        """🆕 根據當前工具套用按鈕樣式"""
        pen_active   = (self.current_tool == ToolType.PEN)
        eraser_active = (self.current_tool == ToolType.ERASER)

        self.pen_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {'lightblue' if pen_active else 'white'};
                font-size: 40px;
                border-radius: 10px;
                border: 2px solid {'#2196F3' if pen_active else '#cccccc'};
            }}
            QPushButton:hover {{ background-color: #81D4FA; }}
        """)
        self.eraser_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {'lightblue' if eraser_active else 'white'};
                font-size: 40px;
                border-radius: 10px;
                border: 2px solid {'#2196F3' if eraser_active else '#cccccc'};
            }}
            QPushButton:hover {{ background-color: #f0f0f0; }}
        """)

    def _update_toolbar_buttons_visibility(self):
        """根據測試配置更新所有工具列按鈕的可見性（pen / eraser / color）"""
        if self.current_test_config is None:
            # 無配置時全部隱藏，顏色重置黑色
            self.pen_button.hide()
            self.eraser_button.hide()
            self.color_button.hide()
            self.current_color = QColor('#000000')
            self.current_color_name = '#000000'
            return

        toolbar = self.current_test_config.toolbar

        # ── 筆按鈕 ──
        if toolbar.pen_enabled:
            self.pen_button.show()
            self.logger.info(f"✅ 筆按鈕已顯示（{self.current_test_config.drawing_type}）")
        else:
            self.pen_button.hide()
            self.logger.info(f"⚠️ 筆按鈕已隱藏（{self.current_test_config.drawing_type}）")

        # ── 橡皮擦按鈕 ──
        if toolbar.eraser_enabled:
            self.eraser_button.show()
            self.logger.info(f"✅ 橡皮擦按鈕已顯示（{self.current_test_config.drawing_type}）")
        else:
            self.eraser_button.hide()
            self.logger.info(f"⚠️ 橡皮擦按鈕已隱藏（{self.current_test_config.drawing_type}）")

        # ── 顏色按鈕 ──
        if toolbar.color_picker_enabled:
            self.color_button.show()
            self._update_color_button_style()
            self.logger.info(f"✅ 顏色按鈕已顯示（{self.current_test_config.drawing_type}）")
        else:
            self.color_button.hide()
            self.current_color = QColor('#000000')
            self.current_color_name = '#000000'
            self.logger.info(f"⚠️ 顏色按鈕已隱藏（{self.current_test_config.drawing_type}）")

        # ── 若當前工具被停用，自動切換到可用工具 ──
        if self.current_tool == ToolType.ERASER and not toolbar.eraser_enabled:
            if toolbar.pen_enabled:
                self.current_tool = ToolType.PEN
                self._apply_tool_button_styles()
                self._update_cursor()
                self.logger.info("⚠️ 橡皮擦被停用，自動切換回筆工具")


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

            mode = self.current_test_config.toolbar.color_picker_mode
            if mode in (ColorPickerMode.PALETTE_12,
                        ColorPickerMode.PALETTE_24,
                        ColorPickerMode.PALETTE_48):
                color = self._show_palette_color_picker()
            else:
                color = self._show_full_spectrum_color_picker()


            if color and color.isValid():
                self.current_color = color
                self.current_color_name = color.name()
                self._update_color_button_style()
                self.lsl.mark_color_switch(old_color, self.current_color_name)
                self._update_cursor()
                self.logger.info(f"🎨 顏色已切換: {old_color} → {self.current_color_name}")
            else:
                self.logger.info("❌ 用戶取消顏色選擇")

        except Exception as e:
            self.logger.error(f"❌ 選擇顏色失敗: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _wrap_dialog_with_rotation(self, inner_widget: 'QWidget') -> 'QDialog':
        """將任意 QWidget 包裝成旋轉對話框（直向模式用）"""
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QGraphicsView,
                                    QGraphicsScene, QGraphicsProxyWidget,
                                    QDesktopWidget)

        desktop = QDesktopWidget()
        screen = desktop.screenGeometry(1 if desktop.screenCount() > 1 else 0)
        screen_w = screen.width()
        screen_h = screen.height()

        content_w = inner_widget.width()
        content_h = inner_widget.height()

        # 🆕 保護：尺寸為 0 時使用預設值
        if content_w <= 0:
            content_w = 600
        if content_h <= 0:
            content_h = 500

        scene = QGraphicsScene()
        proxy = QGraphicsProxyWidget()
        proxy.setWidget(inner_widget)
        scene.addItem(proxy)

        proxy.setTransformOriginPoint(content_w / 2, content_h / 2)
        proxy.setRotation(-90)

        scene.setSceneRect(
            -(content_h - content_w) / 2,
            -(content_w - content_h) / 2,
            content_h,
            content_w
        )

        view = QGraphicsView(scene)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setFrameShape(view.NoFrame)
        view.setStyleSheet("background-color: rgba(0,0,0,128); border: none;")

        outer_dialog = QDialog(self)
        outer_dialog.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        outer_dialog.setModal(True)

        outer_layout = QVBoxLayout(outer_dialog)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        outer_layout.addWidget(view)

        outer_dialog.move(screen.x(), screen.y())
        outer_dialog.resize(screen_w, screen_h)

        return outer_dialog


    def _show_full_spectrum_color_picker(self) -> QColor:
        """顯示完整色譜選擇器（支援直向旋轉）"""
        orientation = getattr(self, '_toolbar_orientation', 'landscape')

        if orientation == "portrait":
            return self._show_rotated_color_picker()   # ✅ 呼叫下方新增的方法
        else:
            return QColorDialog.getColor(self.current_color, self, "選擇畫筆顏色")


    def _show_rotated_color_picker(self) -> QColor:
        """🆕 直向模式的完整色譜選擇器（旋轉版）"""
        from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGraphicsView,
                                    QGraphicsScene, QGraphicsProxyWidget)

        # ── 1. 建立內層容器 ──
        inner_container = QWidget()
        inner_container.setStyleSheet("background-color: white;")
        inner_layout = QVBoxLayout(inner_container)
        inner_layout.setContentsMargins(0, 0, 0, 0)

        color_dialog = QColorDialog(self.current_color)
        color_dialog.setWindowFlags(Qt.Widget)
        color_dialog.setOption(QColorDialog.DontUseNativeDialog, True)
        inner_layout.addWidget(color_dialog)

        inner_container.adjustSize()
        inner_container.setFixedSize(inner_container.sizeHint())

        # ── 2. 包裝旋轉 ──
        outer_dialog = self._wrap_dialog_with_rotation(inner_container)

        # ── 3. 連接信號 ──
        selected_color = [self.current_color]

        def on_color_selected(color):
            selected_color[0] = color
            outer_dialog.accept()

        def on_rejected():
            selected_color[0] = QColor()
            outer_dialog.reject()

        color_dialog.colorSelected.connect(on_color_selected)
        color_dialog.rejected.connect(on_rejected)

        outer_dialog.exec_()
        return selected_color[0]


    def _show_palette_color_picker(self) -> QColor:
        """顯示調色盤選擇器（支援直向旋轉）"""
        from PyQt5.QtWidgets import (QDialog, QGridLayout, QPushButton,
                                    QVBoxLayout, QLabel, QWidget)

        orientation = getattr(self, '_toolbar_orientation', 'landscape')

        # ── 建立調色盤內容 Widget ──
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: white;")

        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(15)

        title = QLabel("請選擇顏色:")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        main_layout.addWidget(title)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)

        palette = self.current_test_config.toolbar.color_palette
        selected_color = [None]

        # ── 決定顯示幾色、幾欄 ──
        mode = self.current_test_config.toolbar.color_picker_mode
        if mode == ColorPickerMode.PALETTE_12:
            max_colors, cols = 12, 6
        elif mode == ColorPickerMode.PALETTE_48:
            max_colors, cols = 48, 8
        else:  # PALETTE_24
            max_colors, cols = 24, 6

        # ── 建立顏色按鈕 ──
        # dialog 用列表存放，讓閉包能存取
        dialog_ref = [None]

        def on_color_selected(color_hex):
            selected_color[0] = QColor(color_hex)
            if dialog_ref[0]:
                dialog_ref[0].accept()

        for i, color_hex in enumerate(palette[:max_colors]):
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
            btn.clicked.connect(lambda checked, c=color_hex: on_color_selected(c))
            grid_layout.addWidget(btn, i // cols, i % cols)

        main_layout.addLayout(grid_layout)

        # ── 取消按鈕 ──
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                min-height: 40px;
                border-radius: 5px;
            }
        """)
        cancel_btn.clicked.connect(lambda: dialog_ref[0].reject() if dialog_ref[0] else None)
        main_layout.addWidget(cancel_btn)

        # ── 根據方向決定顯示方式 ──
        if orientation == "portrait":
            # 直向：先固定尺寸，再包裝旋轉
            content_widget.adjustSize()
            content_widget.setFixedSize(content_widget.sizeHint())

            outer_dialog = self._wrap_dialog_with_rotation(content_widget)
            dialog_ref[0] = outer_dialog

            if outer_dialog.exec_() == QDialog.Accepted and selected_color[0]:
                return selected_color[0]
            return QColor()

        else:
            # 橫向：直接顯示普通對話框
            dialog = QDialog(self)
            dialog.setWindowTitle("選擇顏色")
            dialog.setModal(True)
            dialog_ref[0] = dialog

            layout = QVBoxLayout(dialog)
            layout.addWidget(content_widget)

            if dialog.exec_() == QDialog.Accepted and selected_color[0]:
                return selected_color[0]
            return QColor()



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
            self.control_window.start_stopwatch() # ✅ 程式啟動時立即開始計時
            
            self.logger.info("✅ 實驗者控制視窗已創建並顯示")
            
        except Exception as e:
            self.logger.error(f"❌ 創建控制視窗失敗: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def show_artwork_display(self):
        try:
            if self._artwork_display_window is not None:
                self._artwork_display_window.close()
                self._artwork_display_window = None

            orientation = (self.current_test_config.screen_orientation
                        if self.current_test_config else "landscape")
            toolbar_size = getattr(self, '_toolbar_size', 120)

            self._artwork_display_window = ArtworkDisplayWindow(
                all_strokes=self.all_strokes,
                canvas_width=self.config.canvas_width,
                canvas_height=self.config.canvas_height,
                secondary_screen=self.secondary_screen,
                toolbar_size=toolbar_size,
                orientation=orientation,
                is_single_screen=not self.is_extended_mode,
                on_close_callback=self._on_artwork_window_closed,
                parent=self          # ✅ 改為 self，不再是 None
            )

            self.logger.info("🖼️ 繪畫成品展示視窗已開啟")
            return self._artwork_display_window

        except Exception as e:
            self.logger.error(f"❌ 開啟成品展示視窗失敗: {e}")
            return None

    def _on_artwork_window_closed(self):
        """🆕 展示視窗被外部關閉（例如 ESC）時的處理"""
        self._artwork_display_window = None
        self.logger.info("🖼️ 展示視窗已被外部關閉，通知對話框恢復狀態")
        # 注意：此時無法直接存取 DrawingTypeDialog，
        # 但 hide_artwork_display() 已將 _artwork_display_window 設為 None
        # DrawingTypeDialog 的 _toggle_artwork 下次被呼叫時會正確處理

    def hide_artwork_display(self):
        """🆕 關閉繪畫成品展示視窗"""
        if self._artwork_display_window is not None:
            # 暫時移除 callback 避免循環呼叫
            self._artwork_display_window.on_close_callback = None
            self._artwork_display_window.close()
            self._artwork_display_window = None
            self.logger.info("❌ 繪畫成品展示視窗已關閉")


    def _finish_current_drawing(self):
        """完成當前繪畫的保存工作（🆕 添加配置到 metadata）"""
        try:
            self._force_complete_current_stroke()
            self._output_drawing_statistics()
            self._export_current_canvas()
            
            if hasattr(self, 'lsl') and self.lsl is not None:
                self.logger.info("🔚 保存當前繪畫數據...")
                saved_files = self.lsl.stop()
                self.logger.info(f"✅ 當前繪畫數據已保存: {saved_files}")
                
                # 🆕🆕🆕 將繪畫測驗配置添加到 metadata.json
                if 'metadata' in saved_files:
                    from SubjectInfoDialog import save_drawing_config_to_metadata
                    save_drawing_config_to_metadata(saved_files['metadata'], self.current_test_config)
                
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
        # 根據新測試配置更新工具列可見性
        self._update_toolbar_buttons_visibility()
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
        """匯出當前畫布（保存到 output_dir 根目錄）"""
        try:
            if hasattr(self, 'lsl') and self.lsl is not None:
                canvas_image_path = os.path.join(
                    str(self.lsl.data_recorder.output_dir),
                    "canvas_drawing.png"
                )
                
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
            # ── 防護：若目標工具被 Workspace 停用，忽略此次切換 ──
            if self.current_test_config is not None:
                if tool_type == ToolType.PEN and not self.current_test_config.toolbar.pen_enabled:
                    self.logger.warning("⚠️ 筆工具已被停用，忽略切換")
                    return
                if tool_type == ToolType.ERASER and not self.current_test_config.toolbar.eraser_enabled:
                    self.logger.warning("⚠️ 橡皮擦已被停用，忽略切換")
                    return

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
            # 🆕 恢復副螢幕原始方向
            if self.is_extended_mode:
                self.screen_rotation_manager.restore_original()

            # 🆕 關閉成品展示視窗（若有）
            self.hide_artwork_display()

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
            
            canvas_width  = self.config.canvas_width
            canvas_height = self.config.canvas_height
            toolbar_orientation = getattr(self, '_toolbar_orientation', 'landscape')
            toolbar_size        = getattr(self, '_toolbar_size', 120)

            if toolbar_orientation == "portrait":
                # ✅ 直向模式座標轉換
                # 實體螢幕橫向 (W x H)，畫布旋轉 -90°
                # paintEvent 的旋轉：translate(toolbar_size, H) → rotate(-90)
                #
                # 旋轉後邏輯座標對應關係：
                #   邏輯X = H - y_pixel          （實體Y軸反轉）
                #   邏輯Y = x_pixel - toolbar_size（實體X軸減去toolbar）
                #
                # 工具列區域：x_pixel < toolbar_size（實體左側）

                h = self.height()  # 實體螢幕高（短邊），例如 1080

                # 工具列區域判斷（實體左側 = 邏輯上側）
                if x_pixel < toolbar_size:
                    self.logger.debug(
                        f"⏭️ 點在工具欄區域（直向，實體左側），跳過: ({x_pixel}, {y_pixel})"
                    )
                    if self.pen_is_touching or self.current_stroke_points:
                        self._force_end_current_stroke()
                    event.accept()
                    return

                # ✅ 座標轉換：實體 → 邏輯直向
                # 對應 paintEvent 的 translate(toolbar_size, h) + rotate(-90)
                logical_x = h - y_pixel                    # 邏輯X = H - 實體Y
                logical_y = x_pixel - toolbar_size         # 邏輯Y = 實體X - toolbar

                # 邊界檢查
                if logical_x < 0 or logical_x > canvas_width:
                    event.accept()
                    return
                if logical_y < 0 or logical_y > canvas_height:
                    event.accept()
                    return

                adjusted_x   = logical_x
                adjusted_y   = logical_y
                x_normalized = adjusted_x / canvas_width
                y_normalized = adjusted_y / canvas_height

            else:
                # 橫向：工具列在左側，x < toolbar_size 為工具列區域
                if x_pixel < toolbar_size:
                    self.logger.debug(f"⏭️ 點在工具欄區域（左側），跳過: ({x_pixel}, {y_pixel})")
                    if self.pen_is_touching or self.current_stroke_points:
                        self._force_end_current_stroke()
                    event.accept()
                    return
                adjusted_x   = x_pixel - toolbar_size
                adjusted_y   = y_pixel
                x_normalized = adjusted_x / canvas_width
                y_normalized = adjusted_y / canvas_height


            if self.current_tool == ToolType.PEN:
                self._handle_pen_input(adjusted_x, adjusted_y, x_normalized, y_normalized,
                                    current_pressure, event)
            elif self.current_tool == ToolType.ERASER:
                self._handle_eraser_input(adjusted_x, adjusted_y, current_pressure, event)
            
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
        
        toolbar_orientation = getattr(self, '_toolbar_orientation', 'landscape')
        toolbar_size        = getattr(self, '_toolbar_size', 120)

        if toolbar_orientation == "portrait":
            # ✅ 直向模式：
            # - 工具列在左側（x < toolbar_size），不旋轉
            # - 畫布區域（x >= toolbar_size）旋轉 -90°
            #
            # 實體螢幕橫向 (W x H)，例如 1920x1080
            # 畫布邏輯尺寸：canvas_width=H=1080, canvas_height=W-toolbar=1800
            #
            # 旋轉原點設在畫布區域的左上角 (toolbar_size, 0)
            # 旋轉 -90° 後：
            #   原點移到 (toolbar_size, H)
            #   新X軸 = 原Y軸（向上）
            #   新Y軸 = 原X軸（向右）

            w = self.width()    # 實體螢幕寬，例如 1920
            h = self.height()   # 實體螢幕高，例如 1080

            # 先平移到畫布區域左下角，再旋轉
            painter.translate(toolbar_size, h)
            painter.rotate(-90)
            # 旋轉後，(0,0) 對應實體 (toolbar_size, h)
            # 旋轉後座標系中：
            #   x 方向 = 實體 y 減少方向（向上）
            #   y 方向 = 實體 x 增加方向（向右）

            visible_rect = event.rect()
        else:
            painter.translate(toolbar_size, 0)
            visible_rect = event.rect()
            visible_rect.translate(-toolbar_size, 0)



        
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

    # 🆕 載入 Qt 中文翻譯（解決 QColorDialog 英文問題）
    from PyQt5.QtCore import QTranslator, QLocale, QLibraryInfo

    translator = QTranslator()
    qt_translations_path = QLibraryInfo.location(QLibraryInfo.TranslationsPath)

    # ✅ 修正：用 QLocale(QLocale.Chinese) 建立物件，而非直接傳 Language 枚舉
    if translator.load(QLocale(QLocale.Chinese), "qtbase", "_", qt_translations_path):
        app.installTranslator(translator)
        print("✅ Qt 中文翻譯已載入")
    else:
        # 🆕 備用方案：直接指定繁體中文檔名
        fallback_loaded = (
            translator.load("qtbase_zh_TW", qt_translations_path) or
            translator.load("qtbase_zh",    qt_translations_path)
        )
        if fallback_loaded:
            app.installTranslator(translator)
            print("✅ Qt 中文翻譯已載入（備用方案）")
        else:
            print("⚠️ Qt 中文翻譯載入失敗（翻譯檔可能不存在）")


    
    # 先選擇 Workspace
    while True:
        # 選擇 Workspace
        workspace_dialog = WorkspaceSelectionDialog()
        if workspace_dialog.exec_() != QDialog.Accepted:
            print("❌ 用戶取消選擇 Workspace，程式結束")
            ink_system.stop_processing()
            ink_system.shutdown()
            sys.exit(0)

        workspace = workspace_dialog.selected_workspace
        print(f"✅ 已載入 Workspace: {workspace.project_name}")

        canvas = WacomDrawingCanvas(ink_system, config, workspace)

        # 🆕 若受試者資訊取消，重新回到 Workspace 選擇
        if canvas._should_restart:
            print("🔄 返回 Workspace 選擇畫面")
            continue

        break  # 正常繼續

    
    # 🆕🆕🆕 儲存 Workspace 配置說明檔到受試者根目錄（第一層）
    if canvas.subject_info:
        from SubjectInfoDialog import save_workspace_config_summary
        subject_root_dir = os.path.join(
            "./wacom_recordings",
            canvas.subject_info['subject_folder_name']  # 🆕 改用 subject_folder_name
        )
        os.makedirs(subject_root_dir, exist_ok=True)
        save_workspace_config_summary(workspace, subject_root_dir)


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
    ink_system.shutdown()
    
    print("\n✅ 測試完成")

if __name__ == "__main__":
    test_wacom_with_full_system()
