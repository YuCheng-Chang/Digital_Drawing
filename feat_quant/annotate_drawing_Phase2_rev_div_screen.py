# annotate_drawing.py
"""
Draw-a-Person 測驗標註工具
- 讀取 ink_data.csv 和 markers.csv
- 自動計算預設邊界框（基於未刪除的筆劃）
- 提供互動式調整功能
- 匯出標註結果（PNG + Excel）
"""

import pandas as pd
import numpy as np
import sys
import os
import json
import logging
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox, QGroupBox
)
from PyQt5.QtGui import QPainter, QPen, QColor, QPixmap, QImage, QBrush, QCursor
from PyQt5.QtCore import Qt, QRect, QPoint

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('DrawingAnnotator')


class BoundingBoxWidget(QWidget):
    """可拖動調整的邊界框繪製區域"""
    
    def __init__(self, canvas_width, canvas_height, strokes, parent=None):
        super().__init__(parent)
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.strokes = strokes  # {stroke_id: [(x, y, pressure), ...]}
        
        # 計算預設邊界框
        self.bbox = self._calculate_default_bbox()
        
        # 拖動狀態
        self.dragging = False
        self.drag_handle = None  # 'tl', 'tr', 'bl', 'br', 'top', 'bottom', 'left', 'right', 'move'
        self.drag_start_pos = None
        self.drag_start_bbox = None
        
        # 手柄大小
        self.handle_size = 10
        
        # 設置最小尺寸
        self.setMinimumSize(800, 600)
        
        # 啟用滑鼠追蹤
        self.setMouseTracking(True)
        
        # 生成繪圖背景
        self._generate_drawing_background()
        
        logger.info(f"✅ 初始化邊界框: {self.bbox}")
    
    def _calculate_default_bbox(self):
        """計算預設邊界框（基於所有未刪除的筆劃）"""
        if not self.strokes:
            # 沒有筆劃，返回畫布中心的小框
            center_x = self.canvas_width / 2
            center_y = self.canvas_height / 2
            size = 100
            return QRect(
                int(center_x - size/2),
                int(center_y - size/2),
                size, size
            )
        
        # 收集所有點的座標
        all_x = []
        all_y = []
        
        for stroke in self.strokes.values():
            for x, y, _ in stroke:
                all_x.append(x)
                all_y.append(y)
        
        if not all_x:
            # 沒有有效點，返回預設框
            return QRect(100, 100, 200, 200)
        
        # 計算邊界
        min_x = min(all_x)
        max_x = max(all_x)
        min_y = min(all_y)
        max_y = max(all_y)
        
        # 添加 5% 的邊距
        width = max_x - min_x
        height = max_y - min_y
        padding_x = width * 0.05
        padding_y = height * 0.05
        
        bbox = QRect(
            int(min_x - padding_x),
            int(min_y - padding_y),
            int(width + 2 * padding_x),
            int(height + 2 * padding_y)
        )
        
        logger.info(f"📐 計算預設邊界框: x=[{min_x:.1f}, {max_x:.1f}], y=[{min_y:.1f}, {max_y:.1f}]")
        logger.info(f"   邊界框: {bbox}")
        
        return bbox
    
    def _generate_drawing_background(self):
        """生成繪圖背景（只生成一次）"""
        self.background_pixmap = QPixmap(self.canvas_width, self.canvas_height)
        self.background_pixmap.fill(Qt.white)
        
        painter = QPainter(self.background_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 繪製所有筆劃
        for stroke_id in sorted(self.strokes.keys()):
            stroke = self.strokes[stroke_id]
            
            if len(stroke) == 0:
                continue
            
            # 計算平均壓力
            pressures = [p for _, _, p in stroke if p > 0]
            avg_pressure = sum(pressures) / len(pressures) if pressures else 0.5
            
            # 計算筆劃移動距離
            all_x = [x for x, _, _ in stroke]
            all_y = [y for _, y, _ in stroke]
            x_range = max(all_x) - min(all_x)
            y_range = max(all_y) - min(all_y)
            max_distance = max(x_range, y_range)
            
            # 極短筆畫（視為點）
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
                # 正常筆畫
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
        
        # 計算縮放比例（適應視窗大小）
        scale_x = self.width() / self.canvas_width
        scale_y = self.height() / self.canvas_height
        scale = min(scale_x, scale_y)
        
        # 計算偏移（居中）
        offset_x = (self.width() - self.canvas_width * scale) / 2
        offset_y = (self.height() - self.canvas_height * scale) / 2
        
        # 保存變換
        painter.save()
        painter.translate(offset_x, offset_y)
        painter.scale(scale, scale)
        
        # 繪製背景圖
        painter.drawPixmap(0, 0, self.background_pixmap)
        
        # 繪製邊界框
        pen = QPen(QColor(255, 0, 0), 2)
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor(255, 0, 0, 30)))
        painter.drawRect(self.bbox)
        
        # 繪製手柄
        self._draw_handles(painter)
        
        painter.restore()
    
    def _draw_handles(self, painter):
        """繪製拖動手柄"""
        handle_color = QColor(255, 0, 0)
        painter.setBrush(QBrush(handle_color))
        painter.setPen(QPen(Qt.white, 1))
        
        # 四個角
        handles = [
            self.bbox.topLeft(),
            self.bbox.topRight(),
            self.bbox.bottomLeft(),
            self.bbox.bottomRight()
        ]
        
        for point in handles:
            painter.drawEllipse(point, self.handle_size, self.handle_size)
        
        # 四條邊的中點
        mid_handles = [
            QPoint(self.bbox.center().x(), self.bbox.top()),      # 上
            QPoint(self.bbox.center().x(), self.bbox.bottom()),   # 下
            QPoint(self.bbox.left(), self.bbox.center().y()),     # 左
            QPoint(self.bbox.right(), self.bbox.center().y())     # 右
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
        # 轉換座標到畫布空間
        canvas_pos = self._widget_to_canvas_pos(pos)
        
        threshold = self.handle_size + 5
        
        # 檢查四個角
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
        
        # 檢查四條邊
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
        
        # 檢查是否在邊界框內（移動整個框）
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
            
            # 根據手柄類型調整邊界框
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
            
            # 確保邊界框有效（寬高 > 10）
            if new_bbox.width() > 10 and new_bbox.height() > 10:
                self.bbox = new_bbox.normalized()
                self.update()
        else:
            # 更新游標
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
    """標註主視窗"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Draw-a-Person 標註工具")
        self.setGeometry(100, 100, 1200, 800)
        
        # 數據
        self.csv_dir = None
        self.canvas_width = None
        self.canvas_height = None
        self.strokes = None
        self.bbox_widget = None
        
        # 設置 UI
        self._setup_ui()
        
        # 自動載入（如果有預設路徑）
        default_path = r"C:\Users\bml\OneDrive\Desktop\wacom_recordings"
        if os.path.exists(default_path):
            self.load_data(default_path)
    
    def _setup_ui(self):
        """設置 UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # 控制面板
        control_panel = self._create_control_panel()
        main_layout.addWidget(control_panel)
        
        # 繪圖區域（稍後添加）
        self.drawing_container = QWidget()
        self.drawing_layout = QVBoxLayout()
        self.drawing_container.setLayout(self.drawing_layout)
        main_layout.addWidget(self.drawing_container, stretch=1)
        
        # 狀態列
        self.status_label = QLabel("請選擇資料夾...")
        main_layout.addWidget(self.status_label)
    
    def _create_control_panel(self):
        """創建控制面板"""
        group = QGroupBox("控制面板")
        layout = QHBoxLayout()
        
        # 載入按鈕
        self.load_btn = QPushButton("📁 選擇資料夾")
        self.load_btn.clicked.connect(self.on_load_clicked)
        layout.addWidget(self.load_btn)
        
        # 重置按鈕
        self.reset_btn = QPushButton("🔄 重置邊界框")
        self.reset_btn.clicked.connect(self.on_reset_clicked)
        self.reset_btn.setEnabled(False)
        layout.addWidget(self.reset_btn)
        
        # 匯出按鈕
        self.export_btn = QPushButton("💾 匯出結果")
        self.export_btn.clicked.connect(self.on_export_clicked)
        self.export_btn.setEnabled(False)
        layout.addWidget(self.export_btn)
        
        layout.addStretch()
        
        group.setLayout(layout)
        return group
    
    def on_load_clicked(self):
        """載入按鈕點擊"""
        default_dir = r"C:\Users\bml\OneDrive\Desktop\wacom_recordings"
        
        folder = QFileDialog.getExistingDirectory(
            self,
            "選擇包含 ink_data.csv 的資料夾",
            default_dir
        )
        
        if folder:
            self.load_data(folder)
    
    def load_data(self, folder_path):
        """載入數據"""
        try:
            logger.info(f"📂 載入資料夾: {folder_path}")
            
            # 檢查必要檔案
            ink_data_path = os.path.join(folder_path, "ink_data.csv")
            
            if not os.path.exists(ink_data_path):
                QMessageBox.warning(self, "錯誤", f"找不到 ink_data.csv\n路徑: {ink_data_path}")
                return
            
            self.csv_dir = folder_path
            
            # 載入 metadata
            metadata = self._load_metadata()
            
            # 載入墨水數據
            df = pd.read_csv(ink_data_path)
            logger.info(f"✅ 載入 {len(df)} 個點")
            
            # 載入標記（橡皮擦事件）
            markers_df = self._load_markers()
            
            # 解析筆劃
            self.strokes = self._parse_strokes(df)
            
            # 應用刪除事件
            eraser_events = self._parse_eraser_events(markers_df)
            self.strokes = self._apply_deletion_events(self.strokes, eraser_events)
            
            logger.info(f"✅ 最終筆劃數: {len(self.strokes)}")
            
            # 創建邊界框視窗
            self._create_bbox_widget()
            
            # 更新狀態
            self.status_label.setText(f"✅ 已載入: {folder_path}")
            self.reset_btn.setEnabled(True)
            self.export_btn.setEnabled(True)
            
        except Exception as e:
            logger.error(f"❌ 載入失敗: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "錯誤", f"載入失敗:\n{e}")
    
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
        
        # 判斷座標類型
        x_max = df['x'].max()
        y_max = df['y'].max()
        is_normalized = (x_max <= 1.0 and y_max <= 1.0)
        
        for idx, row in df.iterrows():
            event_type = row['event_type']
            stroke_id = row.get('stroke_id', None)
            
            if stroke_id is None or pd.isna(stroke_id):
                continue
            
            stroke_id = int(stroke_id)
            
            # 轉換座標
            if is_normalized:
                x_pixel = row['x'] * self.canvas_width
                y_pixel = row['y'] * self.canvas_height
            else:
                x_pixel = row['x']
                y_pixel = row['y']
            
            pressure = row['pressure']
            
            if event_type == 1:  # 筆劃開始
                if current_stroke:
                    strokes[current_stroke_id] = current_stroke
                
                current_stroke_id = stroke_id
                current_stroke = [(x_pixel, y_pixel, pressure)]
                
            elif event_type == 0:  # 筆劃中間點
                current_stroke.append((x_pixel, y_pixel, pressure))
                
            elif event_type == 2:  # 筆劃結束
                current_stroke.append((x_pixel, y_pixel, pressure))
                strokes[current_stroke_id] = current_stroke
                current_stroke = []
                current_stroke_id = None
        
        if current_stroke and current_stroke_id is not None:
            strokes[current_stroke_id] = current_stroke
        
        return {k: v for k, v in strokes.items() if k is not None}
    
    def _parse_eraser_events(self, markers_df):
        """解析橡皮擦事件"""
        import re
        
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
        # 清除舊的視窗
        for i in reversed(range(self.drawing_layout.count())):
            self.drawing_layout.itemAt(i).widget().setParent(None)
        
        # 創建新視窗
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
    
    def on_export_clicked(self):
        """匯出結果"""
        if not self.bbox_widget:
            QMessageBox.warning(self, "錯誤", "請先載入數據")
            return
        
        try:
            # 獲取邊界框資訊
            bbox_info = self.bbox_widget.get_bbox_info()
            
            # 生成輸出路徑
            output_png = os.path.join(self.csv_dir, "annotated_drawing.png")
            output_excel = os.path.join(self.csv_dir, "annotation_data.xlsx")
            
            # 1. 匯出 PNG（帶標註框）
            self._export_annotated_image(output_png, bbox_info)
            
            # 2. 匯出 Excel
            self._export_excel(output_excel, bbox_info)
            
            QMessageBox.information(
                self,
                "成功",
                f"✅ 匯出成功！\n\nPNG: {output_png}\nExcel: {output_excel}"
            )
            
            logger.info("✅ 匯出完成")
            
        except Exception as e:
            logger.error(f"❌ 匯出失敗: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "錯誤", f"匯出失敗:\n{e}")
    
    def _export_annotated_image(self, output_path, bbox_info):
        """匯出帶標註框的圖片"""
        # 使用背景圖
        pixmap = QPixmap(self.bbox_widget.background_pixmap)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 繪製邊界框
        pen = QPen(QColor(255, 0, 0), 3)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.bbox_widget.bbox)
        
        # 繪製標籤
        painter.setPen(QPen(QColor(255, 0, 0)))
        painter.drawText(
            self.bbox_widget.bbox.topLeft() + QPoint(5, -5),
            f"Person ({bbox_info['width']}x{bbox_info['height']})"
        )
        
        painter.end()
        
        pixmap.save(output_path, 'PNG')
        logger.info(f"✅ PNG 已保存: {output_path}")
    
    def _export_excel(self, output_path, bbox_info):
        """匯出 Excel"""
        data = {
            '項目': [
                '全圖寬度', '全圖高度', '全圖面積',
                '物件 X 起點', '物件 Y 起點', '物件寬度', '物件高度',
                '物件面積', '物件長寬比', '物件中心 X', '物件中心 Y'
            ],
            '數值': [
                self.canvas_width,
                self.canvas_height,
                self.canvas_width * self.canvas_height,
                bbox_info['x'],
                bbox_info['y'],
                bbox_info['width'],
                bbox_info['height'],
                bbox_info['area'],
                f"{bbox_info['aspect_ratio']:.2f}",
                f"{bbox_info['center_x']:.1f}",
                f"{bbox_info['center_y']:.1f}"
            ]
        }
        
        df = pd.DataFrame(data)
        df.to_excel(output_path, index=False, sheet_name='標註數據')
        
        logger.info(f"✅ Excel 已保存: {output_path}")


def main():
    """主程式"""
    app = QApplication(sys.argv)
    
    window = AnnotationWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
