# reconstruct.py
"""
從 ink_data.csv 和 markers.csv 重建數位墨水繪圖（支援橡皮擦 + 顏色）
"""
import pandas as pd
import numpy as np
from PyQt5.QtWidgets import QApplication, QFileDialog
from PyQt5.QtGui import QPainter, QPen, QColor, QPixmap
from PyQt5.QtCore import Qt
import sys
import os
from pathlib import Path
import logging
import re
import json

# 導入配置
from Config import ProcessingConfig

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('InkReconstructor')


class InkDrawingReconstructor:
    """從 CSV 重建數位墨水繪圖（支援橡皮擦 + 顏色）"""
    
    def __init__(self, canvas_width: int = None, canvas_height: int = None):
        """
        初始化重建器
        
        Args:
            canvas_width: 畫布寬度（若為 None，則從 metadata.json 讀取）
            canvas_height: 畫布高度（若為 None，則從 metadata.json 讀取）
        """
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        
        if canvas_width and canvas_height:
            logger.info(f"初始化重建器: 畫布大小 {self.canvas_width}x{self.canvas_height}")
        else:
            logger.info("初始化重建器: 畫布大小將從 metadata.json 讀取")
    
    def load_metadata(self, csv_dir: str) -> dict:
        """
        讀取 metadata.json
        
        Args:
            csv_dir: CSV 檔案所在目錄
            
        Returns:
            dict: metadata 字典，若檔案不存在則返回空字典
        """
        metadata_path = os.path.join(csv_dir, "metadata.json")
        
        if not os.path.exists(metadata_path):
            logger.warning(f"⚠️ metadata.json 不存在: {metadata_path}")
            return {}
        
        try:
            logger.info(f"讀取 metadata.json: {metadata_path}")
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            logger.info(f"✅ 成功讀取 metadata.json")
            
            # 顯示關鍵資訊
            if 'canvas_width' in metadata and 'canvas_height' in metadata:
                logger.info(f"   - 畫布尺寸: {metadata['canvas_width']} x {metadata['canvas_height']}")
            
            if 'subject_info' in metadata:
                subject_id = metadata['subject_info'].get('subject_id', 'N/A')
                logger.info(f"   - 受試者: {subject_id}")
            
            if 'drawing_info' in metadata:
                drawing_type = metadata['drawing_info'].get('drawing_type', 'N/A')
                logger.info(f"   - 繪畫類型: {drawing_type}")
            
            return metadata
            
        except Exception as e:
            logger.error(f"❌ 讀取 metadata.json 失敗: {e}")
            return {}
    
    def set_canvas_size_from_metadata(self, metadata: dict) -> bool:
        """
        從 metadata 設置畫布尺寸
        
        Args:
            metadata: metadata 字典
            
        Returns:
            bool: 是否成功設置
        """
        if 'canvas_width' in metadata and 'canvas_height' in metadata:
            self.canvas_width = metadata['canvas_width']
            self.canvas_height = metadata['canvas_height']
            logger.info(f"✅ 從 metadata 設置畫布尺寸: {self.canvas_width} x {self.canvas_height}")
            return True
        else:
            logger.warning("⚠️ metadata 中沒有畫布尺寸資訊")
            return False
    
    def load_ink_data(self, csv_path: str) -> pd.DataFrame:
        """
        讀取 ink_data.csv
        
        Args:
            csv_path: CSV 檔案路徑
            
        Returns:
            DataFrame 包含墨水數據
        """
        try:
            logger.info(f"讀取 CSV: {csv_path}")
            df = pd.read_csv(csv_path)
            
            # 驗證必要欄位
            required_columns = ['timestamp', 'x', 'y', 'pressure', 'event_type']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                raise ValueError(f"CSV 缺少必要欄位: {missing_columns}")
            
            # 🆕 檢查是否有顏色欄位
            if 'color' in df.columns:
                logger.info(f"✅ 檢測到顏色欄位")
                unique_colors = df['color'].unique()
                logger.info(f"   - 使用的顏色: {list(unique_colors)}")
            else:
                logger.warning(f"⚠️ 沒有顏色欄位，將使用預設黑色")
                df['color'] = 'black'
            
            logger.info(f"✅ 成功讀取 {len(df)} 個點")
            logger.info(f"   - 欄位: {list(df.columns)}")
            
            # 檢測座標範圍
            x_min, x_max = df['x'].min(), df['x'].max()
            y_min, y_max = df['y'].min(), df['y'].max()
            
            logger.info(f"   - X 範圍: [{x_min:.6f}, {x_max:.6f}]")
            logger.info(f"   - Y 範圍: [{y_min:.6f}, {y_max:.6f}]")
            
            # 判斷座標類型
            if x_max <= 1.0 and y_max <= 1.0:
                logger.info("   - 座標類型: 歸一化座標 [0, 1]")
            else:
                logger.info("   - 座標類型: 像素座標")
            
            return df
            
        except Exception as e:
            logger.error(f"❌ 讀取 CSV 失敗: {e}")
            raise
    
    def load_markers(self, csv_dir: str) -> pd.DataFrame:
        """
        讀取 markers.csv（橡皮擦事件）
        
        Args:
            csv_dir: CSV 檔案所在目錄
            
        Returns:
            DataFrame 包含標記數據，若檔案不存在則返回空 DataFrame
        """
        markers_path = os.path.join(csv_dir, "markers.csv")
        
        if not os.path.exists(markers_path):
            logger.warning(f"⚠️ markers.csv 不存在: {markers_path}")
            return pd.DataFrame(columns=['timestamp', 'marker_text'])
        
        try:
            logger.info(f"讀取 markers.csv: {markers_path}")
            df = pd.read_csv(markers_path)
            
            logger.info(f"✅ 成功讀取 {len(df)} 個標記")
            
            # 統計不同類型的標記
            marker_types = {
                'stroke_start': len(df[df['marker_text'].str.contains('stroke_start_', na=False)]),
                'stroke_end': len(df[df['marker_text'].str.contains('stroke_end_', na=False)]),
                'eraser': len(df[df['marker_text'].str.contains('eraser_', na=False)]),
                'color_switch': len(df[df['marker_text'].str.contains('color_switch', na=False)]),
                'canvas_cleared': len(df[df['marker_text'] == 'canvas_cleared'])
            }
            
            logger.info(f"   - 標記統計: {marker_types}")
            
            return df
            
        except Exception as e:
            logger.error(f"❌ 讀取 markers.csv 失敗: {e}")
            return pd.DataFrame(columns=['timestamp', 'marker_text'])
    
    def parse_canvas_clear_events(self, markers_df: pd.DataFrame, strokes: dict) -> set:
        """
        解析清空畫布事件，找出應該被清除的筆劃
        
        Args:
            markers_df: 標記數據 DataFrame
            strokes: 所有筆劃字典 {stroke_id: {'points': [...], 'color': '...'}}
            
        Returns:
            set: 應該被清除的筆劃 ID 集合
        """
        cleared_stroke_ids = set()
        
        # 找出所有清空畫布事件的時間戳
        canvas_clear_events = markers_df[
            markers_df['marker_text'] == 'canvas_cleared'
        ]['timestamp'].tolist()
        
        if not canvas_clear_events:
            logger.info("ℹ️ 沒有檢測到清空畫布事件")
            return cleared_stroke_ids
        
        logger.info(f"🗑️ 檢測到 {len(canvas_clear_events)} 個清空畫布事件")
        
        # 找出每個清空事件之前結束的筆劃
        for clear_time in canvas_clear_events:
            # 找出在清空事件之前結束的筆劃
            strokes_before_clear = markers_df[
                (markers_df['marker_text'].str.contains('stroke_end_')) &
                (markers_df['timestamp'] < clear_time)
            ]['marker_text'].tolist()
            
            # 提取筆劃 ID
            for marker in strokes_before_clear:
                match = re.search(r'stroke_end_(\d+)', marker)
                if match:
                    stroke_id = int(match.group(1))
                    cleared_stroke_ids.add(stroke_id)
            
            logger.info(f"🗑️ 清空畫布事件 (時間: {clear_time:.4f}): 將清除筆劃 {sorted(cleared_stroke_ids)}")
        
        return cleared_stroke_ids

    def parse_eraser_events(self, markers_df: pd.DataFrame) -> dict:
        """
        解析橡皮擦事件，提取被刪除的筆劃 ID
        
        Args:
            markers_df: 標記數據 DataFrame
            
        Returns:
            dict: {eraser_id: [deleted_stroke_ids]}
        """
        eraser_events = {}
        
        # 正則表達式：匹配 "eraser_X|deleted_strokes:[1,2,3]"
        pattern = r'eraser_(\d+)\|deleted_strokes:\[([^\]]*)\]'
        
        for idx, row in markers_df.iterrows():
            marker_text = row['marker_text']
            
            match = re.search(pattern, marker_text)
            if match:
                eraser_id = int(match.group(1))
                deleted_strokes_str = match.group(2)
                
                # 解析被刪除的筆劃 ID
                if deleted_strokes_str.strip():
                    deleted_stroke_ids = [int(x.strip()) for x in deleted_strokes_str.split(',')]
                else:
                    deleted_stroke_ids = []
                
                # 累積模式
                if eraser_id in eraser_events:
                    eraser_events[eraser_id].extend(deleted_stroke_ids)
                    logger.info(f"🧹 橡皮擦事件 {eraser_id}: 累積刪除筆劃 {deleted_stroke_ids} (總計: {eraser_events[eraser_id]})")
                else:
                    eraser_events[eraser_id] = deleted_stroke_ids
                    logger.info(f"🧹 橡皮擦事件 {eraser_id}: 刪除筆劃 {deleted_stroke_ids}")
        
        if not eraser_events:
            logger.info("ℹ️ 沒有檢測到橡皮擦事件")
        
        return eraser_events
    
    def parse_strokes(self, df: pd.DataFrame) -> dict:
        """
        根據 event_type 和 stroke_id 分割筆劃（🆕 添加顏色支援）
        
        Args:
            df: 包含墨水數據的 DataFrame
            
        Returns:
            dict: {stroke_id: {'points': [(x, y, pressure), ...], 'color': '#rrggbb'}}
        """
        strokes = {}
        current_stroke_id = None
        current_stroke = []
        current_color = 'black'  # 🆕 追蹤當前顏色
        
        # 檢測座標是否已經是像素座標
        x_max = df['x'].max()
        y_max = df['y'].max()
        is_normalized = (x_max <= 1.0 and y_max <= 1.0)
        
        if is_normalized:
            logger.info("✅ 檢測到歸一化座標，將轉換為像素座標")
        else:
            logger.info("✅ 檢測到像素座標，直接使用")
        
        for idx, row in df.iterrows():
            event_type = row['event_type']
            stroke_id = row.get('stroke_id', None)
            color = row.get('color', 'black')  # 🆕 讀取顏色
            
            # 跳過無效的 stroke_id
            if stroke_id is None or pd.isna(stroke_id):
                logger.warning(f"⚠️ 跳過無效的 stroke_id: {stroke_id} at index {idx}")
                continue
            
            stroke_id = int(stroke_id)
            
            # 根據座標類型決定是否轉換
            if is_normalized:
                x_pixel = row['x'] * self.canvas_width
                y_pixel = row['y'] * self.canvas_height
            else:
                x_pixel = row['x']
                y_pixel = row['y']
            
            pressure = row['pressure']
            
            if event_type == 1:  # 筆劃開始
                if current_stroke:  # 保存前一個筆劃
                    strokes[current_stroke_id] = {
                        'points': current_stroke,
                        'color': current_color  # 🆕 保存顏色
                    }
                
                current_stroke_id = stroke_id
                current_stroke = [(x_pixel, y_pixel, pressure)]
                current_color = color  # 🆕 更新當前顏色
                
            elif event_type == 0:  # 筆劃中間點
                current_stroke.append((x_pixel, y_pixel, pressure))
                
            elif event_type == 2:  # 筆劃結束
                current_stroke.append((x_pixel, y_pixel, pressure))
                strokes[current_stroke_id] = {
                    'points': current_stroke,
                    'color': current_color  # 🆕 保存顏色
                }
                current_stroke = []
                current_stroke_id = None
        
        # 處理未完成的筆劃
        if current_stroke and current_stroke_id is not None:
            strokes[current_stroke_id] = {
                'points': current_stroke,
                'color': current_color  # 🆕 保存顏色
            }
        
        # 移除 None 鍵
        strokes = {k: v for k, v in strokes.items() if k is not None}
        
        logger.info(f"✅ 解析出 {len(strokes)} 個筆劃")
        
        # 統計信息
        total_points = sum(len(stroke['points']) for stroke in strokes.values())
        logger.info(f"   - 總點數: {total_points}")
        
        if strokes:
            avg_points = total_points / len(strokes)
            logger.info(f"   - 平均每筆劃點數: {avg_points:.1f}")
            
            valid_stroke_ids = [sid for sid in strokes.keys() if sid is not None]
            if valid_stroke_ids:
                logger.info(f"   - 筆劃 ID 範圍: {min(valid_stroke_ids)} ~ {max(valid_stroke_ids)}")
            
            # 🆕 統計顏色使用
            colors_used = set(stroke['color'] for stroke in strokes.values())
            logger.info(f"   - 使用的顏色: {list(colors_used)}")
        
        # 顯示像素座標範圍
        if strokes:
            all_x = [p[0] for stroke in strokes.values() for p in stroke['points']]
            all_y = [p[1] for stroke in strokes.values() for p in stroke['points']]
            logger.info(f"   - 像素 X 範圍: [{min(all_x):.1f}, {max(all_x):.1f}]")
            logger.info(f"   - 像素 Y 範圍: [{min(all_y):.1f}, {max(all_y):.1f}]")
        
        return strokes
    
    def apply_deletion_events(self, strokes: dict, eraser_events: dict, cleared_strokes: set) -> dict:
        """
        應用刪除事件（橡皮擦 + 清空畫布）
        
        Args:
            strokes: {stroke_id: {'points': [...], 'color': '...'}}
            eraser_events: {eraser_id: [deleted_stroke_ids]}
            cleared_strokes: 清空畫布事件刪除的筆劃 ID 集合
            
        Returns:
            dict: 刪除後的筆劃字典
        """
        # 收集所有被刪除的筆劃 ID
        all_deleted_ids = set(cleared_strokes)
        
        # 加入橡皮擦刪除的筆劃
        for eraser_id, deleted_ids in eraser_events.items():
            all_deleted_ids.update(deleted_ids)
        
        if not all_deleted_ids:
            logger.info("ℹ️ 沒有刪除事件，返回原始筆劃")
            return strokes
        
        logger.info(f"🗑️ 應用刪除事件: 將刪除筆劃 {sorted(all_deleted_ids)}")
        
        if cleared_strokes:
            logger.info(f"   - 清空畫布刪除: {sorted(cleared_strokes)}")
        
        if eraser_events:
            eraser_deleted = set()
            for deleted_ids in eraser_events.values():
                eraser_deleted.update(deleted_ids)
            logger.info(f"   - 橡皮擦刪除: {sorted(eraser_deleted)}")
        
        # 創建新的筆劃字典（排除被刪除的）
        remaining_strokes = {
            stroke_id: stroke 
            for stroke_id, stroke in strokes.items() 
            if stroke_id not in all_deleted_ids
        }
        
        deleted_count = len(strokes) - len(remaining_strokes)
        logger.info(f"✅ 刪除了 {deleted_count} 個筆劃，剩餘 {len(remaining_strokes)} 個筆劃")
        
        if remaining_strokes:
            valid_remaining_ids = [sid for sid in remaining_strokes.keys() if sid is not None]
            if valid_remaining_ids:
                logger.info(f"   - 剩餘筆劃 ID: {sorted(valid_remaining_ids)}")
        
        return remaining_strokes
    
    def _parse_color(self, color_str: str) -> QColor:
        """
        🆕 解析顏色字符串為 QColor
        
        Args:
            color_str: 顏色字符串（如 'black', '#000000', '#ff0000'）
            
        Returns:
            QColor: Qt 顏色對象
        """
        # 如果是十六進制格式（如 '#ff0000'）
        if color_str.startswith('#'):
            return QColor(color_str)
        
        # 如果是顏色名稱（如 'black', 'red'）
        color_map = {
            'black': QColor(0, 0, 0),
            'red': QColor(255, 0, 0),
            'blue': QColor(0, 0, 255),
            'green': QColor(0, 128, 0),
            'orange': QColor(255, 165, 0),
            'purple': QColor(128, 0, 128),
        }
        
        return color_map.get(color_str.lower(), QColor(0, 0, 0))  # 預設黑色
    
    def reconstruct_drawing(self, strokes: dict, output_path: str) -> bool:
        """
        重建繪圖並保存為 PNG（🆕 支援顏色）
        
        Args:
            strokes: 筆劃字典 {stroke_id: {'points': [(x, y, pressure), ...], 'color': '#rrggbb'}}
            output_path: 輸出 PNG 路徑
            
        Returns:
            bool: 是否成功
        """
        try:
            logger.info(f"開始重建繪圖（支援顏色）...")
            
            # 過濾掉 None 鍵
            strokes = {k: v for k, v in strokes.items() if k is not None}
            
            if not strokes:
                logger.warning("⚠️ 沒有有效的筆劃可繪製，生成空白圖片")
            
            # 確保 QApplication 存在
            app = QApplication.instance()
            if app is None:
                logger.warning("⚠️ QApplication 不存在，創建臨時實例")
                app = QApplication(sys.argv)
            
            # 創建 QPixmap
            pixmap = QPixmap(self.canvas_width, self.canvas_height)
            pixmap.fill(Qt.white)  # 白色背景
            
            # 創建 QPainter
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 繪製每個筆劃（按 stroke_id 排序）
            for stroke_id in sorted(strokes.keys()):
                stroke_data = strokes[stroke_id]
                stroke_points = stroke_data['points']
                stroke_color_str = stroke_data.get('color', 'black')  # 🆕 獲取顏色
                
                if len(stroke_points) == 0:
                    logger.warning(f"⚠️ 筆劃 {stroke_id} 沒有點，跳過")
                    continue
                
                # 🆕 解析顏色
                stroke_color = self._parse_color(stroke_color_str)
                
                # 計算筆劃的平均壓力（排除壓力為0的點）
                pressures = [p for _, _, p in stroke_points if p > 0]
                if pressures:
                    avg_pressure = sum(pressures) / len(pressures)
                else:
                    avg_pressure = 0.5
                
                # 計算筆劃的實際移動距離
                all_x = [x for x, _, _ in stroke_points]
                all_y = [y for _, y, _ in stroke_points]
                x_range = max(all_x) - min(all_x)
                y_range = max(all_y) - min(all_y)
                max_distance = max(x_range, y_range)
                
                # 如果筆劃移動距離 < 3 像素，視為單點筆畫
                if max_distance < 3.0:
                    # 計算中心點
                    center_x = sum(all_x) / len(all_x)
                    center_y = sum(all_y) / len(all_y)
                    
                    # 使用平均壓力計算寬度
                    width = max(3.0, 1 + avg_pressure * 5)
                    
                    # 🆕 設置畫筆顏色
                    pen = QPen(stroke_color)
                    pen.setWidthF(width)
                    pen.setCapStyle(Qt.RoundCap)
                    painter.setPen(pen)
                    
                    # 繪製一個點
                    painter.drawPoint(int(center_x), int(center_y))
                    
                    logger.info(f"✅ 繪製極短筆畫（視為點）: stroke_id={stroke_id}, "
                            f"pos=({center_x:.1f}, {center_y:.1f}), "
                            f"width={width:.1f}, "
                            f"color={stroke_color_str}, "
                            f"max_distance={max_distance:.2f}px, "
                            f"points={len(stroke_points)}")
                
                else:
                    # 正常筆畫：繪製線段
                    logger.info(f"✅ 繪製正常筆畫: stroke_id={stroke_id}, "
                            f"points={len(stroke_points)}, "
                            f"color={stroke_color_str}, "
                            f"distance={max_distance:.1f}px")
                    
                    for i in range(len(stroke_points) - 1):
                        x1, y1, p1 = stroke_points[i]
                        x2, y2, p2 = stroke_points[i + 1]
                        
                        # 使用平均壓力來計算寬度
                        if p1 > 0:
                            width = max(2.0, 1 + p1 * 5)
                        else:
                            width = max(2.0, 1 + avg_pressure * 5)
                        
                        # 🆕 設置畫筆顏色
                        pen = QPen(stroke_color)
                        pen.setWidthF(width)
                        pen.setCapStyle(Qt.RoundCap)
                        pen.setJoinStyle(Qt.RoundJoin)
                        painter.setPen(pen)
                        
                        # 繪製線段
                        painter.drawLine(
                            int(x1), int(y1),
                            int(x2), int(y2)
                        )
            
            painter.end()
            
            # 保存為 PNG
            success = pixmap.save(output_path, 'PNG')
            
            if success:
                logger.info(f"✅ 繪圖已保存: {output_path}")
                
                # 顯示檔案大小
                file_size = os.path.getsize(output_path) / 1024  # KB
                logger.info(f"   - 檔案大小: {file_size:.2f} KB")
                
                return True
            else:
                logger.error(f"❌ 保存失敗: {output_path}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 重建繪圖時出錯: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def process(self, csv_path: str, output_path: str = None) -> bool:
        """
        完整處理流程（支援橡皮擦 + 清空畫布 + 顏色）
        
        Args:
            csv_path: CSV 檔案路徑
            output_path: 輸出 PNG 路徑（預設為同目錄下的 reconstruct.png）
            
        Returns:
            bool: 是否成功
        """
        try:
            # 設置輸出路徑
            csv_dir = os.path.dirname(csv_path)
            if output_path is None:
                output_path = os.path.join(csv_dir, "reconstruct.png")
            
            logger.info("=" * 60)
            logger.info("🎨 開始重建數位墨水繪圖（支援橡皮擦 + 清空畫布 + 顏色）")
            logger.info("=" * 60)
            logger.info(f"輸入: {csv_path}")
            logger.info(f"輸出: {output_path}")
            
            # 1. 讀取 metadata（如果畫布尺寸未設置）
            if self.canvas_width is None or self.canvas_height is None:
                metadata = self.load_metadata(csv_dir)
                
                if not self.set_canvas_size_from_metadata(metadata):
                    # 如果 metadata 中沒有畫布尺寸，使用預設值
                    logger.warning("⚠️ 使用預設畫布尺寸: 1800 x 700")
                    self.canvas_width = 1800
                    self.canvas_height = 700
            
            # 2. 讀取墨水數據
            df = self.load_ink_data(csv_path)
            
            # 3. 讀取標記數據（橡皮擦事件 + 清空畫布）
            markers_df = self.load_markers(csv_dir)
            
            # 4. 解析筆劃（包含顏色）
            strokes = self.parse_strokes(df)
            
            if not strokes:
                logger.warning("⚠️ 沒有檢測到任何筆劃")
                return False
            
            # 5. 解析橡皮擦事件
            eraser_events = self.parse_eraser_events(markers_df)
            
            # 6. 解析清空畫布事件
            cleared_strokes = self.parse_canvas_clear_events(markers_df, strokes)
            
            # 7. 應用刪除事件（橡皮擦 + 清空畫布）
            final_strokes = self.apply_deletion_events(strokes, eraser_events, cleared_strokes)
            
            if not final_strokes:
                logger.warning("⚠️ 所有筆劃都被刪除了")
            
            # 8. 重建繪圖（使用顏色）
            success = self.reconstruct_drawing(final_strokes, output_path)
            
            if success:
                logger.info("=" * 60)
                logger.info("✅ 重建完成")
                logger.info("=" * 60)
            
            return success
            
        except Exception as e:
            logger.error(f"❌ 處理失敗: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False


def select_csv_file() -> str:
    """
    使用 QFileDialog 選擇 CSV 檔案
    
    Returns:
        str: 選擇的檔案路徑,若取消則返回 None
    """
    # 確保 QApplication 存在
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # 設置起始目錄
    start_dir = "./wacom_recordings"
    if not os.path.exists(start_dir):
        start_dir = "."
    
    # 開啟檔案選擇對話框
    file_path, _ = QFileDialog.getOpenFileName(
        None,
        "選擇 ink_data.csv 檔案",
        start_dir,
        "CSV Files (*.csv);;All Files (*)"
    )
    
    return file_path if file_path else None


def main():
    """主程式"""
    print("\n" + "=" * 60)
    print("🎨 數位墨水繪圖重建工具（支援橡皮擦 + 清空畫布 + 顏色）")
    print("=" * 60 + "\n")
    
    # 在最開始就創建 QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # 1. 選擇 CSV 檔案
    csv_path = select_csv_file()
    
    if not csv_path:
        print("❌ 未選擇檔案，程式結束")
        return
    
    print(f"✅ 選擇的檔案: {csv_path}\n")
    
    # 創建重建器（畫布尺寸從 metadata.json 讀取）
    reconstructor = InkDrawingReconstructor()
    
    # 2. 處理
    success = reconstructor.process(csv_path)
    
    if success:
        print("\n✅ 處理成功！")
        
        # 顯示輸出路徑
        output_path = os.path.join(os.path.dirname(csv_path), "reconstruct.png")
        print(f"📁 輸出檔案: {output_path}")
        
        # 詢問是否開啟圖片
        try:
            import platform
            response = input("\n是否開啟圖片？(y/n): ").strip().lower()
            
            if response == 'y':
                if platform.system() == 'Windows':
                    os.startfile(output_path)
                elif platform.system() == 'Darwin':  # macOS
                    os.system(f'open "{output_path}"')
                else:  # Linux
                    os.system(f'xdg-open "{output_path}"')
        except:
            pass
    else:
        print("\n❌ 處理失敗")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
