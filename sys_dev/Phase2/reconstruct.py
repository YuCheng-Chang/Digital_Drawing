# reconstruct.py
"""
從 ink_data.csv 和 markers.csv 重建數位墨水繪圖（支援橡皮擦）
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

# 導入配置
from Config import ProcessingConfig

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('InkReconstructor')


class InkDrawingReconstructor:
    """從 CSV 重建數位墨水繪圖（支援橡皮擦）"""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
        self.canvas_width = config.canvas_width
        self.canvas_height = config.canvas_height
        logger.info(f"初始化重建器: 畫布大小 {self.canvas_width}x{self.canvas_height}")
    
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
            
            # 顯示標記內容
            for idx, row in df.iterrows():
                logger.info(f"   - {row['marker_text']}")
            
            return df
            
        except Exception as e:
            logger.error(f"❌ 讀取 markers.csv 失敗: {e}")
            return pd.DataFrame(columns=['timestamp', 'marker_text'])
    
    def parse_eraser_events(self, markers_df: pd.DataFrame) -> dict:
        """
        解析橡皮擦事件，提取被刪除的筆劃 ID
        
        Args:
            markers_df: 標記數據 DataFrame
            
        Returns:
            dict: {eraser_id: [deleted_stroke_ids]}
            例如: {0: [0], 1: [2, 3]}
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
                
                # 🔧 修復：累積模式，而不是覆蓋
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
        根據 event_type 和 stroke_id 分割筆劃
        
        Args:
            df: 包含墨水數據的 DataFrame
            
        Returns:
            dict: {stroke_id: [(x, y, pressure), ...]}
        """
        strokes = {}
        current_stroke_id = None
        current_stroke = []
        
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
            stroke_id = row.get('stroke_id', 0)  # 如果沒有 stroke_id 欄位，預設為 0
            
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
        
        # 處理未完成的筆劃
        if current_stroke and current_stroke_id is not None:
            strokes[current_stroke_id] = current_stroke
        
        logger.info(f"✅ 解析出 {len(strokes)} 個筆劃")
        
        # 統計信息
        total_points = sum(len(stroke) for stroke in strokes.values())
        logger.info(f"   - 總點數: {total_points}")
        if strokes:
            avg_points = total_points / len(strokes)
            logger.info(f"   - 平均每筆劃點數: {avg_points:.1f}")
            logger.info(f"   - 筆劃 ID 範圍: {min(strokes.keys())} ~ {max(strokes.keys())}")
        
        # 顯示像素座標範圍
        if strokes:
            all_x = [p[0] for stroke in strokes.values() for p in stroke]
            all_y = [p[1] for stroke in strokes.values() for p in stroke]
            logger.info(f"   - 像素 X 範圍: [{min(all_x):.1f}, {max(all_x):.1f}]")
            logger.info(f"   - 像素 Y 範圍: [{min(all_y):.1f}, {max(all_y):.1f}]")
        
        return strokes
    
    def apply_eraser_events(self, strokes: dict, eraser_events: dict) -> dict:
        """
        應用橡皮擦事件，刪除對應的筆劃
        
        Args:
            strokes: {stroke_id: [(x, y, pressure), ...]}
            eraser_events: {eraser_id: [deleted_stroke_ids]}
            
        Returns:
            dict: 刪除後的筆劃字典
        """
        if not eraser_events:
            logger.info("ℹ️ 沒有橡皮擦事件，返回原始筆劃")
            return strokes
        
        # 收集所有被刪除的筆劃 ID
        all_deleted_ids = set()
        for eraser_id, deleted_ids in eraser_events.items():
            all_deleted_ids.update(deleted_ids)
        
        logger.info(f"🧹 應用橡皮擦事件: 將刪除筆劃 {sorted(all_deleted_ids)}")
        
        # 創建新的筆劃字典（排除被刪除的）
        remaining_strokes = {
            stroke_id: stroke 
            for stroke_id, stroke in strokes.items() 
            if stroke_id not in all_deleted_ids
        }
        
        deleted_count = len(strokes) - len(remaining_strokes)
        logger.info(f"✅ 刪除了 {deleted_count} 個筆劃，剩餘 {len(remaining_strokes)} 個筆劃")
        
        if remaining_strokes:
            logger.info(f"   - 剩餘筆劃 ID: {sorted(remaining_strokes.keys())}")
        
        return remaining_strokes
    
    def reconstruct_drawing(self, strokes: dict, output_path: str) -> bool:
        """
        重建繪圖並保存為 PNG
        
        Args:
            strokes: 筆劃字典 {stroke_id: [(x, y, pressure), ...]}
            output_path: 輸出 PNG 路徑
            
        Returns:
            bool: 是否成功
        """
        try:
            logger.info(f"開始重建繪圖...")
            
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
                stroke = strokes[stroke_id]
                
                if len(stroke) < 2:
                    logger.warning(f"⚠️ 筆劃 {stroke_id} 只有 {len(stroke)} 個點，跳過")
                    continue
                
                # 繪製線段
                for i in range(len(stroke) - 1):
                    x1, y1, p1 = stroke[i]
                    x2, y2, p2 = stroke[i + 1]
                    
                    # 使用與 test_wacom_with_system.py 相同的寬度公式
                    width = 1 + p1 * 5
                    
                    # 設置畫筆
                    pen = QPen(QColor(0, 0, 0))  # 黑色
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
        完整處理流程（支援橡皮擦）
        
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
            logger.info("🎨 開始重建數位墨水繪圖（支援橡皮擦）")
            logger.info("=" * 60)
            logger.info(f"輸入: {csv_path}")
            logger.info(f"輸出: {output_path}")
            
            # 1. 讀取墨水數據
            df = self.load_ink_data(csv_path)
            
            # 2. 讀取標記數據（橡皮擦事件）
            markers_df = self.load_markers(csv_dir)
            
            # 3. 解析筆劃
            strokes = self.parse_strokes(df)
            
            if not strokes:
                logger.warning("⚠️ 沒有檢測到任何筆劃")
                return False
            
            # 4. 解析橡皮擦事件
            eraser_events = self.parse_eraser_events(markers_df)
            
            # 5. 應用橡皮擦事件
            final_strokes = self.apply_eraser_events(strokes, eraser_events)
            
            if not final_strokes:
                logger.warning("⚠️ 所有筆劃都被橡皮擦刪除了")
                # 仍然生成空白圖片
            
            # 6. 重建繪圖
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
    print("🎨 數位墨水繪圖重建工具（支援橡皮擦）")
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
    
    # 2. 載入配置
    config = ProcessingConfig()
    print(f"📐 畫布配置: {config.canvas_width} x {config.canvas_height}\n")
    
    # 3. 創建重建器
    reconstructor = InkDrawingReconstructor(config)
    
    # 4. 處理
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
