# ===== EraserTool.py =====
"""
橡皮擦工具模組

提供筆劃級橡皮擦功能（向量擦除，支持撤銷）
"""

import math
import logging
from typing import List, Tuple, Set, Dict, Any, Optional
from DigitalInkDataStructure import ProcessedInkPoint, EraserStroke, ToolType


class EraserTool:
    """
    橡皮擦工具
    
    功能：
    - 檢測橡皮擦軌跡與筆劃的碰撞
    - 標記被擦除的筆劃
    - 記錄橡皮擦歷史（支持撤銷）
    """
    
    def __init__(self, radius: float = 20.0):
        """
        初始化橡皮擦工具
        
        Args:
            radius: 橡皮擦半徑（像素）
        """
        self.radius = radius
        self.logger = logging.getLogger('EraserTool')
        
        # 當前橡皮擦筆劃
        self.current_eraser_points = []
        
        # 橡皮擦歷史
        self.eraser_history = []  # List[EraserStroke]
        
        # 統計資訊
        self.stats = {
            'total_eraser_strokes': 0,
            'total_deleted_strokes': 0
        }
        
        self.logger.info(f"✅ 橡皮擦工具初始化完成，半徑={radius}px")
    
    def check_collision(self, 
                       eraser_point: Tuple[float, float],
                       stroke_points: List[Tuple[float, float, float]]) -> bool:
        """
        檢查橡皮擦點是否與筆劃碰撞
        
        Args:
            eraser_point: (x_pixel, y_pixel) 橡皮擦中心（像素座標）
            stroke_points: [(x_pixel, y_pixel, pressure), ...] 筆劃點列表
            
        Returns:
            bool: 是否碰撞
        """
        try:
            ex, ey = eraser_point
            
            # 檢查橡皮擦圓與筆劃線段的碰撞
            for i in range(len(stroke_points)):
                px, py, _ = stroke_points[i]
                
                # 點到點的距離
                dx = px - ex
                dy = py - ey
                distance = math.sqrt(dx * dx + dy * dy)
                
                if distance <= self.radius:
                    return True
                
                # 檢查與線段的距離（如果不是最後一個點）
                if i < len(stroke_points) - 1:
                    px2, py2, _ = stroke_points[i + 1]
                    
                    # 計算點到線段的距離
                    line_distance = self._point_to_line_segment_distance(
                        ex, ey, px, py, px2, py2
                    )
                    
                    if line_distance <= self.radius:
                        return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"❌ 碰撞檢測失敗: {e}")
            return False
    
    def find_colliding_strokes(self,
                              eraser_points: List[Tuple[float, float]],
                              all_strokes: List[Dict],
                              canvas_width: int,
                              canvas_height: int) -> Set[int]:
        """
        找出與橡皮擦軌跡碰撞的所有筆劃
        
        Args:
            eraser_points: [(x_pixel, y_pixel), ...] 橡皮擦軌跡點
            all_strokes: 所有筆劃列表（字典格式）
            canvas_width: 畫布寬度
            canvas_height: 畫布高度
            
        Returns:
            Set[int]: 碰撞的筆劃 ID 集合
        """
        try:
            colliding_ids = set()
            
            for stroke in all_strokes:
                # 跳過已刪除的筆劃
                if stroke.get('is_deleted', False):
                    continue
                
                stroke_id = stroke['stroke_id']
                stroke_points = stroke['points']
                
                # 檢查橡皮擦軌跡的每個點
                for eraser_point in eraser_points:
                    if self.check_collision(eraser_point, stroke_points):
                        colliding_ids.add(stroke_id)
                        break  # 已碰撞，檢查下一個筆劃
            
            return colliding_ids
            
        except Exception as e:
            self.logger.error(f"❌ 查找碰撞筆劃失敗: {e}")
            return set()
    
    def start_eraser_stroke(self):
        """開始新的橡皮擦筆劃"""
        self.current_eraser_points = []
        self.logger.debug("🧹 開始橡皮擦筆劃")
    
    def add_eraser_point(self, x: float, y: float):
        """
        添加橡皮擦軌跡點
        
        Args:
            x: X 座標（像素）
            y: Y 座標（像素）
        """
        self.current_eraser_points.append((x, y))
    
    def finalize_eraser_stroke(self,
                              all_strokes: List[Dict],
                              canvas_width: int,
                              canvas_height: int,
                              timestamp: float) -> Optional[EraserStroke]:
        """
        完成橡皮擦筆劃並記錄
        
        Args:
            all_strokes: 所有筆劃列表
            canvas_width: 畫布寬度
            canvas_height: 畫布高度
            timestamp: 時間戳
            
        Returns:
            Optional[EraserStroke]: 橡皮擦筆劃對象（如果有刪除筆劃）
        """
        try:
            if not self.current_eraser_points:
                self.logger.debug("⏭️ 沒有橡皮擦軌跡點，跳過")
                return None
            
            # 找出碰撞的筆劃
            deleted_ids = self.find_colliding_strokes(
                self.current_eraser_points,
                all_strokes,
                canvas_width,
                canvas_height
            )
            
            if not deleted_ids:
                self.logger.debug("⏭️ 沒有碰撞的筆劃")
                self.current_eraser_points = []
                return None
            
            # 標記筆劃為已刪除
            eraser_id = len(self.eraser_history)
            for stroke in all_strokes:
                if stroke['stroke_id'] in deleted_ids:
                    stroke['is_deleted'] = True
                    stroke['metadata'].is_deleted = True  # 🆕 同步更新 metadata
                    stroke['metadata'].deleted_by = eraser_id
                    stroke['metadata'].deleted_at = timestamp

            
            # 創建橡皮擦筆劃記錄
            eraser_stroke = EraserStroke(
                eraser_id=eraser_id,
                points=[],  # 簡化：不保存完整的 ProcessedInkPoint
                radius=self.radius,
                deleted_stroke_ids=list(deleted_ids),
                timestamp_start=timestamp,
                timestamp_end=timestamp
            )
            
            self.eraser_history.append(eraser_stroke)
            
            # 更新統計
            self.stats['total_eraser_strokes'] += 1
            self.stats['total_deleted_strokes'] += len(deleted_ids)
            
            self.logger.info(
                f"🧹 橡皮擦筆劃完成: eraser_id={eraser_id}, "
                f"刪除了 {len(deleted_ids)} 個筆劃"
            )
            
            # 清空當前軌跡
            self.current_eraser_points = []
            
            return eraser_stroke
            
        except Exception as e:
            self.logger.error(f"❌ 完成橡皮擦筆劃失敗: {e}")
            self.current_eraser_points = []
            return None
    
    def undo_last_erase(self, all_strokes: List[Dict]) -> bool:
        """
        撤銷最後一次橡皮擦操作
        
        Args:
            all_strokes: 所有筆劃列表
            
        Returns:
            bool: 是否成功撤銷
        """
        try:
            if not self.eraser_history:
                self.logger.warning("⚠️ 沒有可撤銷的橡皮擦操作")
                return False
            
            # 取出最後一次橡皮擦操作
            last_eraser = self.eraser_history.pop()
            
            # 🆕🆕🆕 記錄撤銷前的狀態
            self.logger.debug(
                f"🔍 準備撤銷: eraser_id={last_eraser.eraser_id}, "
                f"deleted_stroke_ids={last_eraser.deleted_stroke_ids}"
            )
            
            # 恢復被刪除的筆劃
            restored_count = 0  # 🆕 計數器
            for stroke in all_strokes:
                if stroke['stroke_id'] in last_eraser.deleted_stroke_ids:
                    # 🆕🆕🆕 檢查筆劃是否真的被刪除
                    if not stroke.get('is_deleted', False):
                        self.logger.warning(
                            f"⚠️ 筆劃 {stroke['stroke_id']} 已經是未刪除狀態"
                        )
                        continue
                    
                    # 恢復筆劃
                    stroke['is_deleted'] = False
                    stroke['metadata'].is_deleted = False  # 🆕 同步更新 metadata
                    stroke['metadata'].deleted_by = None
                    stroke['metadata'].deleted_at = None
                    
                    restored_count += 1
                    self.logger.debug(f"✅ 恢復筆劃: {stroke['stroke_id']}")
            
            self.logger.info(
                f"↩️ 撤銷橡皮擦操作: eraser_id={last_eraser.eraser_id}, "
                f"恢復了 {restored_count} 個筆劃"
            )
            
            # 🆕🆕🆕 驗證是否有筆劃被恢復
            if restored_count == 0:
                self.logger.warning("⚠️ 沒有筆劃被恢復，可能數據不一致")
            
            # 更新統計
            self.stats['total_eraser_strokes'] -= 1
            self.stats['total_deleted_strokes'] -= len(last_eraser.deleted_stroke_ids)
            
            return restored_count > 0  # 🆕 返回是否真的恢復了筆劃
            
        except Exception as e:
            self.logger.error(f"❌ 撤銷失敗: {e}")
            import traceback
            self.logger.error(traceback.format_exc())  # 🆕 詳細錯誤
            return False

    def set_radius(self, radius: float):
        """設置橡皮擦半徑"""
        self.radius = max(5.0, min(100.0, radius))  # 限制範圍
        self.logger.info(f"🔧 橡皮擦半徑已設置為: {self.radius}px")
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取統計資訊"""
        return self.stats.copy()
    
    def clear_history(self):
        """清空橡皮擦歷史"""
        self.eraser_history.clear()
        self.current_eraser_points = []
        self.stats = {
            'total_eraser_strokes': 0,
            'total_deleted_strokes': 0
        }
        self.logger.info("🧹 橡皮擦歷史已清空")
    
    # ==================== 私有方法 ====================
    
    def _point_to_line_segment_distance(self, 
                                       px: float, py: float,
                                       x1: float, y1: float,
                                       x2: float, y2: float) -> float:
        """
        計算點到線段的最短距離
        
        Args:
            px, py: 點座標
            x1, y1: 線段起點
            x2, y2: 線段終點
            
        Returns:
            float: 最短距離
        """
        # 線段向量
        dx = x2 - x1
        dy = y2 - y1
        
        # 線段長度的平方
        length_sq = dx * dx + dy * dy
        
        if length_sq == 0:
            # 線段退化為點
            return math.sqrt((px - x1) ** 2 + (py - y1) ** 2)
        
        # 計算投影參數 t
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / length_sq))
        
        # 投影點
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        
        # 計算距離
        distance = math.sqrt((px - proj_x) ** 2 + (py - proj_y) ** 2)
        
        return distance


# ============================================================================
# 使用範例
# ============================================================================

def example_usage():
    """橡皮擦工具使用範例"""
    
    # 初始化橡皮擦
    eraser = EraserTool(radius=20.0)
    
    # 模擬筆劃數據
    all_strokes = [
        {
            'stroke_id': 0,
            'points': [(100, 100, 0.5), (150, 150, 0.6), (200, 200, 0.7)],
            'is_deleted': False,
            'metadata': type('obj', (object,), {
                'deleted_by': None,
                'deleted_at': None
            })()
        },
        {
            'stroke_id': 1,
            'points': [(300, 100, 0.5), (350, 150, 0.6), (400, 200, 0.7)],
            'is_deleted': False,
            'metadata': type('obj', (object,), {
                'deleted_by': None,
                'deleted_at': None
            })()
        }
    ]
    
    # 開始橡皮擦筆劃
    eraser.start_eraser_stroke()
    
    # 添加橡皮擦軌跡點
    for x in range(90, 210, 10):
        eraser.add_eraser_point(x, x)
    
    # 完成橡皮擦筆劃
    eraser_stroke = eraser.finalize_eraser_stroke(
        all_strokes,
        canvas_width=800,
        canvas_height=600,
        timestamp=1234567890.0
    )
    
    if eraser_stroke:
        print(f"✅ 刪除了 {len(eraser_stroke.deleted_stroke_ids)} 個筆劃")
    
    # 檢查筆劃狀態
    for stroke in all_strokes:
        status = "已刪除" if stroke['is_deleted'] else "未刪除"
        print(f"筆劃 {stroke['stroke_id']}: {status}")
    
    # 撤銷橡皮擦操作
    if eraser.undo_last_erase(all_strokes):
        print("↩️ 撤銷成功")
    
    # 再次檢查筆劃狀態
    for stroke in all_strokes:
        status = "已刪除" if stroke['is_deleted'] else "未刪除"
        print(f"筆劃 {stroke['stroke_id']}: {status}")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    example_usage()
