# annotate_drawing.py
"""
Draw-a-Person 測驗標註工具（批次處理版）
- 支援多受試者批次處理
- 自動計算預設邊界框（基於未刪除的筆劃）
- 提供互動式調整功能
- 匯出標註結果（PNG + Excel + 統計圖表）
"""

import pandas as pd
import numpy as np
import sys
import os
import json
import logging
import re
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox, QGroupBox,
    QListWidget, QDialog, QDialogButtonBox, QCheckBox, QScrollArea
)
from PyQt5.QtGui import QPainter, QPen, QColor, QPixmap, QImage, QBrush, QCursor
from PyQt5.QtCore import Qt, QRect, QPoint
import matplotlib
matplotlib.use('Agg')  # 使用非互動式後端
import matplotlib.pyplot as plt

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('DrawingAnnotator')


class DrawingSelectionDialog(QDialog):
    """繪畫選擇對話框"""
    
    def __init__(self, subject_drawings, parent=None):
        """
        Args:
            subject_drawings: {subject_id: [drawing_folder_paths]}
        """
        super().__init__(parent)
        self.subject_drawings = subject_drawings
        self.selected_drawings = {}  # {subject_id: [selected_paths]}
        
        self.setWindowTitle("選擇要分析的繪畫")
        self.setMinimumSize(600, 400)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """設置 UI"""
        layout = QVBoxLayout()
        
        # 說明標籤
        info_label = QLabel("請勾選要分析的繪畫資料夾：")
        layout.addWidget(info_label)
        
        # 捲動區域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        
        self.checkboxes = {}  # {subject_id: {drawing_path: checkbox}}
        
        for subject_id in sorted(self.subject_drawings.keys()):
            drawings = self.subject_drawings[subject_id]
            
            # 受試者標題
            subject_label = QLabel(f"\n📁 {subject_id} ({len(drawings)} 個繪畫)")
            subject_label.setStyleSheet("font-weight: bold; font-size: 14px;")
            scroll_layout.addWidget(subject_label)
            
            self.checkboxes[subject_id] = {}
            
            for drawing_path in sorted(drawings):
                folder_name = os.path.basename(drawing_path)
                checkbox = QCheckBox(f"  ✓ {folder_name}")
                checkbox.setChecked(True)  # 預設全選
                
                self.checkboxes[subject_id][drawing_path] = checkbox
                scroll_layout.addWidget(checkbox)
        
        scroll_layout.addStretch()
        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)
        
        layout.addWidget(scroll)
        
        # 按鈕
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def accept(self):
        """確認選擇"""
        self.selected_drawings = {}
        
        for subject_id, drawings_dict in self.checkboxes.items():
            selected = []
            for drawing_path, checkbox in drawings_dict.items():
                if checkbox.isChecked():
                    selected.append(drawing_path)
            
            if selected:
                self.selected_drawings[subject_id] = selected
        
        if not self.selected_drawings:
            QMessageBox.warning(self, "警告", "請至少選擇一個繪畫資料夾")
            return
        
        super().accept()


class BoundingBoxWidget(QWidget):
    """可拖動調整的邊界框繪製區域"""
    
    def __init__(self, canvas_width, canvas_height, strokes, parent=None):
        super().__init__(parent)
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.strokes = strokes
        
        self.bbox = self._calculate_default_bbox()
        
        self.dragging = False
        self.drag_handle = None
        self.drag_start_pos = None
        self.drag_start_bbox = None
        
        self.handle_size = 10
        
        self.setMinimumSize(800, 600)
        self.setMouseTracking(True)
        
        self._generate_drawing_background()
        
        logger.info(f"✅ 初始化邊界框: {self.bbox}")
    
    def _calculate_default_bbox(self):
        """計算預設邊界框（不添加邊距）"""
        if not self.strokes:
            center_x = self.canvas_width / 2
            center_y = self.canvas_height / 2
            size = 100
            return QRect(
                int(center_x - size/2),
                int(center_y - size/2),
                size, size
            )
        
        all_x = []
        all_y = []
        
        for stroke in self.strokes.values():
            for x, y, _ in stroke:
                all_x.append(x)
                all_y.append(y)
        
        if not all_x:
            return QRect(100, 100, 200, 200)
        
        min_x = min(all_x)
        max_x = max(all_x)
        min_y = min(all_y)
        max_y = max(all_y)
        
        width = max_x - min_x
        height = max_y - min_y
        
        bbox = QRect(
            int(min_x),
            int(min_y),
            int(width),
            int(height)
        )
        
        logger.info(f"📐 計算預設邊界框: x=[{min_x:.1f}, {max_x:.1f}], y=[{min_y:.1f}, {max_y:.1f}]")
        
        return bbox
    
    def _generate_drawing_background(self):
        """生成繪圖背景"""
        self.background_pixmap = QPixmap(self.canvas_width, self.canvas_height)
        self.background_pixmap.fill(Qt.white)
        
        painter = QPainter(self.background_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        for stroke_id in sorted(self.strokes.keys()):
            stroke = self.strokes[stroke_id]
            
            if len(stroke) == 0:
                continue
            
            pressures = [p for _, _, p in stroke if p > 0]
            avg_pressure = sum(pressures) / len(pressures) if pressures else 0.5
            
            all_x = [x for x, _, _ in stroke]
            all_y = [y for _, y, _ in stroke]
            x_range = max(all_x) - min(all_x)
            y_range = max(all_y) - min(all_y)
            max_distance = max(x_range, y_range)
            
            if max_distance < 3.0:
                center_x = sum(all_x) / len(all_x)
                center_y = sum(all_y) / len(all_y)
                width = max(3.0, 1 + avg_pressure * 5)
                
                pen = QPen(QColor(0, 0, 0))
                pen.setWidthF(width)
                pen.setCapStyle(Qt.RoundCap)
                painter.setPen(pen)
                painter.drawPoint(int(center_x), int(center_y))
            else:
                for i in range(len(stroke) - 1):
                    x1, y1, p1 = stroke[i]
                    x2, y2, p2 = stroke[i + 1]
                    
                    width = max(2.0, 1 + (p1 if p1 > 0 else avg_pressure) * 5)
                    
                    pen = QPen(QColor(0, 0, 0))
                    pen.setWidthF(width)
                    pen.setCapStyle(Qt.RoundCap)
                    pen.setJoinStyle(Qt.RoundJoin)
                    painter.setPen(pen)
                    
                    painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        
        painter.end()
        logger.info("✅ 繪圖背景已生成")
    
    def paintEvent(self, event):
        """繪製事件"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        scale_x = self.width() / self.canvas_width
        scale_y = self.height() / self.canvas_height
        scale = min(scale_x, scale_y)
        
        offset_x = (self.width() - self.canvas_width * scale) / 2
        offset_y = (self.height() - self.canvas_height * scale) / 2
        
        painter.save()
        painter.translate(offset_x, offset_y)
        painter.scale(scale, scale)
        
        painter.drawPixmap(0, 0, self.background_pixmap)
        
        pen = QPen(QColor(255, 0, 0), 2)
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor(255, 0, 0, 30)))
        painter.drawRect(self.bbox)
        
        self._draw_handles(painter)
        
        painter.restore()
    
    def _draw_handles(self, painter):
        """繪製拖動手柄"""
        handle_color = QColor(255, 0, 0)
        painter.setBrush(QBrush(handle_color))
        painter.setPen(QPen(Qt.white, 1))
        
        handles = [
            self.bbox.topLeft(),
            self.bbox.topRight(),
            self.bbox.bottomLeft(),
            self.bbox.bottomRight()
        ]
        
        for point in handles:
            painter.drawEllipse(point, self.handle_size, self.handle_size)
        
        mid_handles = [
            QPoint(self.bbox.center().x(), self.bbox.top()),
            QPoint(self.bbox.center().x(), self.bbox.bottom()),
            QPoint(self.bbox.left(), self.bbox.center().y()),
            QPoint(self.bbox.right(), self.bbox.center().y())
        ]
        
        for point in mid_handles:
            painter.drawRect(
                point.x() - self.handle_size // 2,
                point.y() - self.handle_size // 2,
                self.handle_size,
                self.handle_size
            )
    
    def _get_handle_at_pos(self, pos):
        """判斷滑鼠位置是否在手柄上"""
        canvas_pos = self._widget_to_canvas_pos(pos)
        
        threshold = self.handle_size + 5
        
        corners = {
            'tl': self.bbox.topLeft(),
            'tr': self.bbox.topRight(),
            'bl': self.bbox.bottomLeft(),
            'br': self.bbox.bottomRight()
        }
        
        for handle, point in corners.items():
            if (abs(canvas_pos.x() - point.x()) < threshold and
                abs(canvas_pos.y() - point.y()) < threshold):
                return handle
        
        if abs(canvas_pos.x() - self.bbox.center().x()) < threshold:
            if abs(canvas_pos.y() - self.bbox.top()) < threshold:
                return 'top'
            if abs(canvas_pos.y() - self.bbox.bottom()) < threshold:
                return 'bottom'
        
        if abs(canvas_pos.y() - self.bbox.center().y()) < threshold:
            if abs(canvas_pos.x() - self.bbox.left()) < threshold:
                return 'left'
            if abs(canvas_pos.x() - self.bbox.right()) < threshold:
                return 'right'
        
        if self.bbox.contains(canvas_pos):
            return 'move'
        
        return None
    
    def _widget_to_canvas_pos(self, pos):
        """將視窗座標轉換為畫布座標"""
        scale_x = self.width() / self.canvas_width
        scale_y = self.height() / self.canvas_height
        scale = min(scale_x, scale_y)
        
        offset_x = (self.width() - self.canvas_width * scale) / 2
        offset_y = (self.height() - self.canvas_height * scale) / 2
        
        canvas_x = (pos.x() - offset_x) / scale
        canvas_y = (pos.y() - offset_y) / scale
        
        return QPoint(int(canvas_x), int(canvas_y))
    
    def mousePressEvent(self, event):
        """滑鼠按下事件"""
        if event.button() == Qt.LeftButton:
            handle = self._get_handle_at_pos(event.pos())
            
            if handle:
                self.dragging = True
                self.drag_handle = handle
                self.drag_start_pos = self._widget_to_canvas_pos(event.pos())
                self.drag_start_bbox = QRect(self.bbox)
                logger.info(f"🖱️ 開始拖動: {handle}")
    
    def mouseMoveEvent(self, event):
        """滑鼠移動事件"""
        if self.dragging:
            current_pos = self._widget_to_canvas_pos(event.pos())
            dx = current_pos.x() - self.drag_start_pos.x()
            dy = current_pos.y() - self.drag_start_pos.y()
            
            new_bbox = QRect(self.drag_start_bbox)
            
            if self.drag_handle == 'tl':
                new_bbox.setTopLeft(self.drag_start_bbox.topLeft() + QPoint(dx, dy))
            elif self.drag_handle == 'tr':
                new_bbox.setTopRight(self.drag_start_bbox.topRight() + QPoint(dx, dy))
            elif self.drag_handle == 'bl':
                new_bbox.setBottomLeft(self.drag_start_bbox.bottomLeft() + QPoint(dx, dy))
            elif self.drag_handle == 'br':
                new_bbox.setBottomRight(self.drag_start_bbox.bottomRight() + QPoint(dx, dy))
            elif self.drag_handle == 'top':
                new_bbox.setTop(self.drag_start_bbox.top() + dy)
            elif self.drag_handle == 'bottom':
                new_bbox.setBottom(self.drag_start_bbox.bottom() + dy)
            elif self.drag_handle == 'left':
                new_bbox.setLeft(self.drag_start_bbox.left() + dx)
            elif self.drag_handle == 'right':
                new_bbox.setRight(self.drag_start_bbox.right() + dx)
            elif self.drag_handle == 'move':
                new_bbox.translate(dx, dy)
            
            if new_bbox.width() > 10 and new_bbox.height() > 10:
                self.bbox = new_bbox.normalized()
                self.update()
        else:
            handle = self._get_handle_at_pos(event.pos())
            
            if handle in ['tl', 'br']:
                self.setCursor(Qt.SizeFDiagCursor)
            elif handle in ['tr', 'bl']:
                self.setCursor(Qt.SizeBDiagCursor)
            elif handle in ['top', 'bottom']:
                self.setCursor(Qt.SizeVerCursor)
            elif handle in ['left', 'right']:
                self.setCursor(Qt.SizeHorCursor)
            elif handle == 'move':
                self.setCursor(Qt.SizeAllCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
    
    def mouseReleaseEvent(self, event):
        """滑鼠釋放事件"""
        if event.button() == Qt.LeftButton and self.dragging:
            self.dragging = False
            self.drag_handle = None
            logger.info(f"✅ 邊界框已更新: {self.bbox}")
    
    def get_bbox_info(self):
        """獲取邊界框資訊"""
        return {
            'x': self.bbox.x(),
            'y': self.bbox.y(),
            'width': self.bbox.width(),
            'height': self.bbox.height(),
            'center_x': self.bbox.center().x(),
            'center_y': self.bbox.center().y(),
            'area': self.bbox.width() * self.bbox.height(),
            'aspect_ratio': self.bbox.width() / self.bbox.height() if self.bbox.height() > 0 else 0
        }


class AnnotationWindow(QMainWindow):
    """標註主視窗（批次處理版）"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Draw-a-Person Annotation Tool (Batch Processing)")
        self.setGeometry(100, 100, 1200, 800)
        
        # 批次處理數據
        self.root_dir = None
        self.selected_drawings = {}  # {subject_id: [drawing_paths]}
        self.current_drawing_index = 0
        self.all_results = []  # 所有標註結果
        
        # 當前繪畫數據
        self.csv_dir = None
        self.canvas_width = None
        self.canvas_height = None
        self.strokes = None
        self.bbox_widget = None
        
        # 🆕 當前繪畫資訊（用於視窗標題）
        self.current_subject_id = None
        self.current_drawing_id = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """設置 UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        control_panel = self._create_control_panel()
        main_layout.addWidget(control_panel)
        
        self.drawing_container = QWidget()
        self.drawing_layout = QVBoxLayout()
        self.drawing_container.setLayout(self.drawing_layout)
        main_layout.addWidget(self.drawing_container, stretch=1)
        
        self.status_label = QLabel("Please select subject folders...")
        main_layout.addWidget(self.status_label)
    
    def _create_control_panel(self):
        """創建控制面板"""
        group = QGroupBox("Control Panel")
        layout = QHBoxLayout()
        
        self.load_btn = QPushButton("📁 Select Subject Folders")
        self.load_btn.clicked.connect(self.on_load_clicked)
        layout.addWidget(self.load_btn)
        
        self.reset_btn = QPushButton("🔄 Reset Bounding Box")
        self.reset_btn.clicked.connect(self.on_reset_clicked)
        self.reset_btn.setEnabled(False)
        layout.addWidget(self.reset_btn)
        
        self.next_btn = QPushButton("➡️ Next")
        self.next_btn.clicked.connect(self.on_next_clicked)
        self.next_btn.setEnabled(False)
        layout.addWidget(self.next_btn)
        
        self.finish_btn = QPushButton("✅ Finish & Export")
        self.finish_btn.clicked.connect(self.on_finish_clicked)
        self.finish_btn.setEnabled(False)
        layout.addWidget(self.finish_btn)
        
        layout.addStretch()
        
        group.setLayout(layout)
        return group
    
    def on_load_clicked(self):
        """載入按鈕點擊"""
        default_dir = r"C:\Users\bml\OneDrive\Desktop\wacom_recordings"
        
        # 🆕 支援多選
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        
        # 啟用多選
        file_view = dialog.findChild(QListWidget, "listView")
        if file_view:
            file_view.setSelectionMode(QListWidget.MultiSelection)
        
        tree_view = dialog.findChild(QWidget, "treeView")
        if tree_view:
            tree_view.setSelectionMode(QListWidget.MultiSelection)
        
        if dialog.exec_() == QDialog.Accepted:
            selected_folders = dialog.selectedFiles()
            
            if selected_folders:
                self.root_dir = default_dir
                self._process_selected_folders(selected_folders)
    
    def _process_selected_folders(self, selected_folders):
        """處理選擇的資料夾"""
        try:
            logger.info(f"📂 選擇了 {len(selected_folders)} 個資料夾")
            
            # 🆕 找出所有符合格式的繪畫資料夾
            subject_drawings = {}
            pattern = re.compile(r'^\d+_DAP_\d{8}_\d{6}$')
            
            for subject_folder in selected_folders:
                subject_id = os.path.basename(subject_folder)
                
                # 搜尋符合格式的子資料夾
                if not os.path.isdir(subject_folder):
                    continue
                
                matching_drawings = []
                
                for item in os.listdir(subject_folder):
                    item_path = os.path.join(subject_folder, item)
                    
                    if os.path.isdir(item_path) and pattern.match(item):
                        # 檢查是否有內層資料夾
                        inner_folder_name = item.split('_')[0] + '_DAP'
                        inner_folder_path = os.path.join(item_path, inner_folder_name)
                        
                        if os.path.isdir(inner_folder_path):
                            ink_data_path = os.path.join(inner_folder_path, "ink_data.csv")
                            
                            if os.path.exists(ink_data_path):
                                matching_drawings.append(inner_folder_path)
                
                if matching_drawings:
                    subject_drawings[subject_id] = matching_drawings
            
            if not subject_drawings:
                QMessageBox.warning(self, "Warning", "No matching drawing folders found")
                return
            
            logger.info(f"✅ 找到 {len(subject_drawings)} 個受試者的繪畫")
            
            # 🆕 讓使用者選擇要分析的繪畫
            dialog = DrawingSelectionDialog(subject_drawings, self)
            
            if dialog.exec_() == QDialog.Accepted:
                self.selected_drawings = dialog.selected_drawings
                self.current_drawing_index = 0
                self.all_results = []
                
                # 載入第一個繪畫
                self._load_next_drawing()
            
        except Exception as e:
            logger.error(f"❌ 處理資料夾失敗: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Processing failed:\n{e}")
    
    def _load_next_drawing(self):
        """載入下一個繪畫"""
        # 獲取所有繪畫的平面列表
        all_drawings = []
        for subject_id in sorted(self.selected_drawings.keys()):
            for drawing_path in self.selected_drawings[subject_id]:
                all_drawings.append((subject_id, drawing_path))
        
        if self.current_drawing_index >= len(all_drawings):
            QMessageBox.information(self, "Complete", "All drawings have been annotated!")
            self.finish_btn.setEnabled(True)
            return
        
        subject_id, drawing_path = all_drawings[self.current_drawing_index]
        
        logger.info(f"📂 載入繪畫 {self.current_drawing_index + 1}/{len(all_drawings)}: {drawing_path}")
        
        self.load_data(drawing_path, subject_id)
        
        # 更新狀態
        self.status_label.setText(
            f"Progress: {self.current_drawing_index + 1}/{len(all_drawings)} | "
            f"Subject: {subject_id} | Folder: {os.path.basename(drawing_path)}"
        )
        
        self.reset_btn.setEnabled(True)
        self.next_btn.setEnabled(True)
    
    def load_data(self, folder_path, subject_id):
        """載入數據"""
        try:
            ink_data_path = os.path.join(folder_path, "ink_data.csv")
            
            if not os.path.exists(ink_data_path):
                logger.warning(f"⚠️ 找不到 ink_data.csv: {ink_data_path}")
                return
            
            self.csv_dir = folder_path
            self.current_subject_id = subject_id
            
            # 🆕🆕🆕 提取繪畫 ID（從資料夾名稱）
            folder_name = os.path.basename(folder_path)
            # 假設格式為 "繪畫id_DAP"，例如 "2_DAP"
            match = re.match(r'^(\d+)_DAP$', folder_name)
            if match:
                self.current_drawing_id = match.group(1)
            else:
                self.current_drawing_id = "unknown"
            
            # 🆕🆕🆕 更新視窗標題（格式：PSP001_2_DAP）
            window_title = f"{self.current_subject_id}_{self.current_drawing_id}_DAP"
            self.setWindowTitle(window_title)
            logger.info(f"📝 視窗標題已更新: {window_title}")
            
            metadata = self._load_metadata()
            
            df = pd.read_csv(ink_data_path)
            logger.info(f"✅ 載入 {len(df)} 個點")
            
            markers_df = self._load_markers()
            
            self.strokes = self._parse_strokes(df)
            
            eraser_events = self._parse_eraser_events(markers_df)
            self.strokes = self._apply_deletion_events(self.strokes, eraser_events)
            
            logger.info(f"✅ 最終筆劃數: {len(self.strokes)}")
            
            self._create_bbox_widget()
            
        except Exception as e:
            logger.error(f"❌ 載入失敗: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Loading failed:\n{e}")
    
    def _load_metadata(self):
        """載入 metadata.json"""
        metadata_path = os.path.join(self.csv_dir, "metadata.json")
        
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            self.canvas_width = metadata.get('canvas_width', 1800)
            self.canvas_height = metadata.get('canvas_height', 700)
            
            logger.info(f"✅ 畫布尺寸: {self.canvas_width} x {self.canvas_height}")
            return metadata
        else:
            logger.warning("⚠️ metadata.json 不存在，使用預設尺寸")
            self.canvas_width = 1800
            self.canvas_height = 700
            return {}
    
    def _load_markers(self):
        """載入 markers.csv"""
        markers_path = os.path.join(self.csv_dir, "markers.csv")
        
        if os.path.exists(markers_path):
            return pd.read_csv(markers_path)
        else:
            logger.warning("⚠️ markers.csv 不存在")
            return pd.DataFrame(columns=['timestamp', 'marker_text'])
    
    def _parse_strokes(self, df):
        """解析筆劃"""
        strokes = {}
        current_stroke_id = None
        current_stroke = []
        
        x_max = df['x'].max()
        y_max = df['y'].max()
        is_normalized = (x_max <= 1.0 and y_max <= 1.0)
        
        for idx, row in df.iterrows():
            event_type = row['event_type']
            stroke_id = row.get('stroke_id', None)
            
            if stroke_id is None or pd.isna(stroke_id):
                continue
            
            stroke_id = int(stroke_id)
            
            if is_normalized:
                x_pixel = row['x'] * self.canvas_width
                y_pixel = row['y'] * self.canvas_height
            else:
                x_pixel = row['x']
                y_pixel = row['y']
            
            pressure = row['pressure']
            
            if event_type == 1:
                if current_stroke:
                    strokes[current_stroke_id] = current_stroke
                
                current_stroke_id = stroke_id
                current_stroke = [(x_pixel, y_pixel, pressure)]
                
            elif event_type == 0:
                current_stroke.append((x_pixel, y_pixel, pressure))
                
            elif event_type == 2:
                current_stroke.append((x_pixel, y_pixel, pressure))
                strokes[current_stroke_id] = current_stroke
                current_stroke = []
                current_stroke_id = None
        
        if current_stroke and current_stroke_id is not None:
            strokes[current_stroke_id] = current_stroke
        
        return {k: v for k, v in strokes.items() if k is not None}
    
    def _parse_eraser_events(self, markers_df):
        """解析橡皮擦事件"""
        eraser_events = {}
        pattern = r'eraser_(\d+)\|deleted_strokes:\[([^\]]*)\]'
        
        for idx, row in markers_df.iterrows():
            marker_text = row['marker_text']
            
            match = re.search(pattern, marker_text)
            if match:
                eraser_id = int(match.group(1))
                deleted_strokes_str = match.group(2)
                
                if deleted_strokes_str.strip():
                    deleted_stroke_ids = [int(x.strip()) for x in deleted_strokes_str.split(',')]
                else:
                    deleted_stroke_ids = []
                
                if eraser_id in eraser_events:
                    eraser_events[eraser_id].extend(deleted_stroke_ids)
                else:
                    eraser_events[eraser_id] = deleted_stroke_ids
        
        return eraser_events
    
    def _apply_deletion_events(self, strokes, eraser_events):
        """應用刪除事件"""
        all_deleted_ids = set()
        
        for deleted_ids in eraser_events.values():
            all_deleted_ids.update(deleted_ids)
        
        if all_deleted_ids:
            logger.info(f"🗑️ 刪除筆劃: {sorted(all_deleted_ids)}")
        
        return {
            stroke_id: stroke
            for stroke_id, stroke in strokes.items()
            if stroke_id not in all_deleted_ids
        }
    
    def _create_bbox_widget(self):
        """創建邊界框視窗"""
        for i in reversed(range(self.drawing_layout.count())):
            self.drawing_layout.itemAt(i).widget().setParent(None)
        
        self.bbox_widget = BoundingBoxWidget(
            self.canvas_width,
            self.canvas_height,
            self.strokes
        )
        
        self.drawing_layout.addWidget(self.bbox_widget)
    
    def on_reset_clicked(self):
        """重置邊界框"""
        if self.bbox_widget:
            self.bbox_widget.bbox = self.bbox_widget._calculate_default_bbox()
            self.bbox_widget.update()
            logger.info("🔄 邊界框已重置")
    
    def on_next_clicked(self):
        """下一個按鈕"""
        if not self.bbox_widget:
            return
        
        # 保存當前結果
        bbox_info = self.bbox_widget.get_bbox_info()
        
        # 🆕 計算新特徵
        canvas_area = self.canvas_width * self.canvas_height
        size_ratio = bbox_info['area'] / canvas_area
        y_ratio = bbox_info['height'] / self.canvas_height
        x_ratio = bbox_info['width'] / self.canvas_width
        
        result = {
            'subject_id': self.current_subject_id,
            'drawing_id': self.current_drawing_id,  # 🆕 添加繪畫 ID
            'folder_name': os.path.basename(self.csv_dir),
            'canvas_width': self.canvas_width,
            'canvas_height': self.canvas_height,
            'canvas_area': canvas_area,
            'bbox_x': bbox_info['x'],
            'bbox_y': bbox_info['y'],
            'bbox_width': bbox_info['width'],
            'bbox_height': bbox_info['height'],
            'bbox_area': bbox_info['area'],
            'bbox_center_x': bbox_info['center_x'],
            'bbox_center_y': bbox_info['center_y'],
            'aspect_ratio': bbox_info['aspect_ratio'],
            'size_ratio': size_ratio,  # 🆕
            'y_ratio': y_ratio,  # 🆕
            'x_ratio': x_ratio  # 🆕
        }
        
        self.all_results.append(result)
        
        # 🆕 匯出個別結果
        self._export_individual_result(result)
        
        # 載入下一個
        self.current_drawing_index += 1
        self._load_next_drawing()
    
    def _export_individual_result(self, result):
        """匯出個別結果"""
        try:
            parent_dir = os.path.dirname(self.csv_dir)
            output_dir = os.path.join(parent_dir, "feature_quantization")
            os.makedirs(output_dir, exist_ok=True)
            
            folder_name = result['folder_name']
            
            # 匯出 PNG
            output_png = os.path.join(output_dir, f"{folder_name}_annotated.png")
            self._export_annotated_image(output_png, result)
            
            # 匯出 Excel
            output_excel = os.path.join(output_dir, f"{folder_name}_annotation.xlsx")
            self._export_excel(output_excel, result)
            
            logger.info(f"✅ 個別結果已匯出: {folder_name}")
            
        except Exception as e:
            logger.error(f"❌ 匯出個別結果失敗: {e}")
    
    def _export_annotated_image(self, output_path, result):
        """匯出帶標註框的圖片"""
        pixmap = QPixmap(self.bbox_widget.background_pixmap)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        pen = QPen(QColor(255, 0, 0), 3)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.bbox_widget.bbox)
        
        painter.setPen(QPen(QColor(255, 0, 0)))
        painter.drawText(
            self.bbox_widget.bbox.topLeft() + QPoint(5, -5),
            f"Person ({result['bbox_width']}x{result['bbox_height']})"
        )
        
        painter.end()
        
        pixmap.save(output_path, 'PNG')
        logger.info(f"✅ PNG 已保存: {output_path}")
    
    def _export_excel(self, output_path, result):
        """匯出 Excel"""
        data = {
            '項目': [
                '全圖寬度', '全圖高度', '全圖面積',
                '物件 X 起點', '物件 Y 起點', '物件寬度', '物件高度',
                '物件面積', '物件長寬比', '物件中心 X', '物件中心 Y',
                '物件大小比例', 'Y軸比例', 'X軸比例'  # 🆕
            ],
            '數值': [
                result['canvas_width'],
                result['canvas_height'],
                result['canvas_area'],
                result['bbox_x'],
                result['bbox_y'],
                result['bbox_width'],
                result['bbox_height'],
                result['bbox_area'],
                f"{result['aspect_ratio']:.2f}",
                f"{result['bbox_center_x']:.1f}",
                f"{result['bbox_center_y']:.1f}",
                f"{result['size_ratio']:.4f}",  # 🆕
                f"{result['y_ratio']:.4f}",  # 🆕
                f"{result['x_ratio']:.4f}"  # 🆕
            ]
        }
        
        df = pd.DataFrame(data)
        df.to_excel(output_path, index=False, sheet_name='標註數據')
        
        logger.info(f"✅ Excel 已保存: {output_path}")
    
    def on_finish_clicked(self):
        """完成並匯出統計結果"""
        if not self.all_results:
            QMessageBox.warning(self, "Warning", "No results to export")
            return
        
        try:
            # 🆕 匯出統計結果
            self._export_summary_statistics()
            
            QMessageBox.information(
                self,
                "Success",
                f"✅ All results exported!\n\nProcessed {len(self.all_results)} drawings"
            )
            
            logger.info("✅ 批次處理完成")
            
        except Exception as e:
            logger.error(f"❌ 匯出統計結果失敗: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Export failed:\n{e}")
    
    def _export_summary_statistics(self):
        """匯出統計結果（含 histogram）"""
        # 創建 DataFrame
        df = pd.DataFrame(self.all_results)
        
        # 匯出到根目錄
        output_dir = os.path.join(self.root_dir, "feature_quantization")
        os.makedirs(output_dir, exist_ok=True)
        
        # 匯出 Excel
        excel_path = os.path.join(output_dir, "summary_statistics.xlsx")
        df.to_excel(excel_path, index=False, sheet_name='All Subjects')
        logger.info(f"✅ 統計 Excel 已保存: {excel_path}")
        
        # 🆕 生成 histogram
        self._generate_histograms(df, output_dir)
    
    def _generate_histograms(self, df, output_dir):
        """生成 histogram（🆕 全英文版本）"""
        features = [
            ('size_ratio', 'Object Size Ratio'),  # 🆕 英文
            ('y_ratio', 'Y-axis Ratio'),  # 🆕 英文
            ('x_ratio', 'X-axis Ratio')  # 🆕 英文
        ]
        
        for feature_key, feature_name in features:
            plt.figure(figsize=(10, 6))
            
            data = df[feature_key]
            mean_val = data.mean()
            std_val = data.std()
            
            plt.hist(data, bins=20, color='skyblue', edgecolor='black', alpha=0.7)
            plt.axvline(mean_val, color='red', linestyle='--', linewidth=2, label=f'Mean = {mean_val:.2f}')
            
            # 🆕🆕🆕 全部改為英文
            plt.xlabel(feature_name, fontsize=12)
            plt.ylabel('Frequency', fontsize=12)
            plt.title(f'{feature_name} Distribution\nMean ± SD = {mean_val:.2f} ± {std_val:.2f}', fontsize=14)
            plt.legend()
            plt.grid(axis='y', alpha=0.3)
            
            # 保存
            output_path = os.path.join(output_dir, f"histogram_{feature_key}.png")
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close()
            
            logger.info(f"✅ Histogram saved: {output_path}")


def main():
    """主程式"""
    app = QApplication(sys.argv)
    
    window = AnnotationWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
