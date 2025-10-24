# reconstruct_ink_drawing.py
"""
從 ink_data.csv 重建數位墨水繪圖
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

# 導入配置
from Config import ProcessingConfig

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('InkReconstructor')


class InkDrawingReconstructor:
    """從 CSV 重建數位墨水繪圖"""
    
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
            
            # ✅✅✅ 新增：檢測座標範圍
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
    
    def parse_strokes(self, df: pd.DataFrame) -> list:
        """
        根據 event_type 分割筆劃
        
        Args:
            df: 包含墨水數據的 DataFrame
            
        Returns:
            list of strokes, 每個 stroke 是點的列表 [(x, y, pressure), ...]
        """
        strokes = []
        current_stroke = []
        
        # ✅✅✅ 檢測座標是否已經是像素座標
        x_max = df['x'].max()
        y_max = df['y'].max()
        
        # 如果最大值 > 1，說明已經是像素座標，不需要再乘以畫布大小
        is_normalized = (x_max <= 1.0 and y_max <= 1.0)
        
        if is_normalized:
            logger.info("✅ 檢測到歸一化座標，將轉換為像素座標")
        else:
            logger.info("✅ 檢測到像素座標，直接使用")
        
        for idx, row in df.iterrows():
            event_type = row['event_type']
            
            # ✅✅✅ 根據座標類型決定是否轉換
            if is_normalized:
                # 歸一化座標 → 像素座標
                x_pixel = row['x'] * self.canvas_width
                y_pixel = row['y'] * self.canvas_height
            else:
                # 已經是像素座標，直接使用
                x_pixel = row['x']
                y_pixel = row['y']
            
            pressure = row['pressure']
            
            if event_type == 1:  # 筆劃開始
                if current_stroke:  # 保存前一個筆劃
                    strokes.append(current_stroke)
                current_stroke = [(x_pixel, y_pixel, pressure)]
                
            elif event_type == 0:  # 筆劃中間點
                current_stroke.append((x_pixel, y_pixel, pressure))
                
            elif event_type == 2:  # 筆劃結束
                current_stroke.append((x_pixel, y_pixel, pressure))
                strokes.append(current_stroke)
                current_stroke = []
        
        # 處理未完成的筆劃
        if current_stroke:
            strokes.append(current_stroke)
        
        logger.info(f"✅ 解析出 {len(strokes)} 個筆劃")
        
        # 統計信息
        total_points = sum(len(stroke) for stroke in strokes)
        logger.info(f"   - 總點數: {total_points}")
        if strokes:
            avg_points = total_points / len(strokes)
            logger.info(f"   - 平均每筆劃點數: {avg_points:.1f}")
        
        # ✅✅✅ 新增：顯示像素座標範圍（用於驗證）
        if strokes:
            all_x = [p[0] for stroke in strokes for p in stroke]
            all_y = [p[1] for stroke in strokes for p in stroke]
            logger.info(f"   - 像素 X 範圍: [{min(all_x):.1f}, {max(all_x):.1f}]")
            logger.info(f"   - 像素 Y 範圍: [{min(all_y):.1f}, {max(all_y):.1f}]")
        
        return strokes
    
    def reconstruct_drawing(self, strokes: list, output_path: str) -> bool:
        """
        重建繪圖並保存為 PNG
        
        Args:
            strokes: 筆劃列表
            output_path: 輸出 PNG 路徑
            
        Returns:
            bool: 是否成功
        """
        try:
            logger.info(f"開始重建繪圖...")
            
            # ✅ 確保 QApplication 存在
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
            
            # 繪製每個筆劃
            for stroke_idx, stroke in enumerate(strokes):
                if len(stroke) < 2:
                    logger.warning(f"⚠️ 筆劃 {stroke_idx} 只有 {len(stroke)} 個點，跳過")
                    continue
                
                # 繪製線段
                for i in range(len(stroke) - 1):
                    x1, y1, p1 = stroke[i]
                    x2, y2, p2 = stroke[i + 1]
                    
                    # ✅ 使用與 test_wacom_with_system.py 相同的寬度公式
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
        完整處理流程
        
        Args:
            csv_path: CSV 檔案路徑
            output_path: 輸出 PNG 路徑（預設為同目錄下的 reconstruct.png）
            
        Returns:
            bool: 是否成功
        """
        try:
            # 設置輸出路徑
            if output_path is None:
                csv_dir = os.path.dirname(csv_path)
                output_path = os.path.join(csv_dir, "reconstruct.png")
            
            logger.info("=" * 60)
            logger.info("🎨 開始重建數位墨水繪圖")
            logger.info("=" * 60)
            logger.info(f"輸入: {csv_path}")
            logger.info(f"輸出: {output_path}")
            
            # 1. 讀取數據
            df = self.load_ink_data(csv_path)
            
            # 2. 解析筆劃
            strokes = self.parse_strokes(df)
            
            if not strokes:
                logger.warning("⚠️ 沒有檢測到任何筆劃")
                return False
            
            # 3. 重建繪圖
            success = self.reconstruct_drawing(strokes, output_path)
            
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
    # ✅ 確保 QApplication 存在
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
    print("🎨 數位墨水繪圖重建工具")
    print("=" * 60 + "\n")
    
    # ✅ 在最開始就創建 QApplication
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
