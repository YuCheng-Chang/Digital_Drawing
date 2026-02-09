# StrokeDetector.py
import math
import numpy as np
from typing import List, Optional, Tuple, Dict, Any
import logging
from collections import deque
from DigitalInkDataStructure import ProcessedInkPoint, StrokeState, EventType
from Config import ProcessingConfig


class StrokeDetector:
    """
    筆劃檢測器 - 使用簡單且可靠的邏輯
    基於 test_wacom_with_system.py 的成功經驗
    """
    
    def __init__(self, config: ProcessingConfig):
        """初始化筆劃檢測器"""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # ✅ 核心狀態
        self.current_stroke_points = []      # 當前筆劃的點
        self.completed_strokes = []          # 已完成的筆劃
        self.current_stroke_id = 0           # 當前筆劃 ID（從 0 開始，第一個筆劃是 1）
        self.current_state = StrokeState.IDLE
        
        # ✅ 簡化的閾值
        self.pressure_threshold = config.pressure_threshold
        
        # ✅ 統計資訊
        self.detection_stats = {
            'strokes_detected': 0,
            'strokes_validated': 0,
            'strokes_rejected': 0,
            'total_points': 0
        }
        
        self.logger.info("✅ StrokeDetector 初始化完成（簡化版）")

    def initialize(self) -> bool:
        """初始化檢測器"""
        try:
            self.logger.info("正在初始化筆劃檢測器（簡化版）...")
            self.reset_state()
            self.reset_statistics()
            self.logger.info("✅ 筆劃檢測器初始化成功")
            return True
        except Exception as e:
            self.logger.error(f"❌ 初始化失敗: {e}")
            return False

    def shutdown(self) -> None:
        """關閉檢測器"""
        self.logger.info("正在關閉筆劃檢測器...")
        self.reset_state()
        self.logger.info("✅ 筆劃檢測器已關閉")


    def add_point(self, point: ProcessedInkPoint) -> None:
        try:
            self.logger.info(
                f"🔍 add_point 被調用: pressure={point.pressure:.3f}, "
                f"current_state={self.current_state.name}, "
                f"current_stroke_id={self.current_stroke_id}, "
                f"current_points={len(self.current_stroke_points)}"
            )
            
            if point.pressure > 0:
                # ✅✅✅ 新增：狀態一致性檢查
                if self.current_state == StrokeState.ACTIVE and not self.current_stroke_points:
                    self.logger.warning(
                        f"⚠️ 檢測到狀態不一致：ACTIVE 但沒有點，強制重置為 IDLE"
                    )
                    self.current_state = StrokeState.IDLE
                
                # 🆕🆕🆕 新增：檢查是否為新筆劃的第一個點
                # 如果當前狀態是 IDLE，或者距離上一個點時間過長，開始新筆劃
                if self.current_state == StrokeState.IDLE:
                    # 🎨 開始新筆劃
                    self.current_state = StrokeState.ACTIVE
                    point.stroke_id = self.current_stroke_id
                    self.current_stroke_points = [point]
                    self.detection_stats['strokes_detected'] += 1
                    self.logger.info(f"🎨 筆劃開始: stroke_id={self.current_stroke_id}")
                
                # 🆕🆕🆕 新增：檢查時間間隔，防止跨筆劃污染
                elif self.current_stroke_points:
                    last_point = self.current_stroke_points[-1]
                    time_gap = point.timestamp - last_point.timestamp
                    
                    # 如果時間間隔超過閾值（例如 0.5 秒），認為是新筆劃
                    if time_gap > 0.5:
                        self.logger.warning(
                            f"⚠️ 檢測到異常時間間隔: {time_gap:.3f}s，"
                            f"強制完成當前筆劃並開始新筆劃"
                        )
                        
                        # 完成當前筆劃
                        self.finalize_current_stroke()
                        
                        # 開始新筆劃
                        self.current_state = StrokeState.ACTIVE
                        point.stroke_id = self.current_stroke_id
                        self.current_stroke_points = [point]
                        self.detection_stats['strokes_detected'] += 1
                        self.logger.info(f"🎨 新筆劃開始: stroke_id={self.current_stroke_id}")
                    else:
                        # ✅ 繼續當前筆劃
                        point.stroke_id = self.current_stroke_id
                        self.current_stroke_points.append(point)
                        self.detection_stats['total_points'] += 1
                        self.logger.debug(f"➕ 添加點到筆劃: stroke_id={self.current_stroke_id}, total_points={len(self.current_stroke_points)}")
                else:
                    # 狀態異常，重置
                    self.logger.warning("⚠️ 狀態異常，重置並開始新筆劃")
                    self.current_state = StrokeState.ACTIVE
                    point.stroke_id = self.current_stroke_id
                    self.current_stroke_points = [point]
                    self.detection_stats['strokes_detected'] += 1
            
            else:
                # 🔚 壓力 = 0：筆劃結束
                if self.current_state == StrokeState.ACTIVE and self.current_stroke_points:
                    current_stroke_id = self.current_stroke_id
                    num_points = len(self.current_stroke_points)
                    
                    self.logger.info(f"🔚 準備完成筆劃: stroke_id={current_stroke_id}, points={num_points}")
                    
                    # ✅ 完成當前筆劃
                    self.finalize_current_stroke()
                    # ✅✅✅ 確保狀態被重置（雙重保險）
                    self.current_state = StrokeState.IDLE
                    
                    self.logger.info(f"🔚 筆劃結束: stroke_id={current_stroke_id}")
                else:
                    self.logger.debug(f"⏭️ 跳過壓力=0的點（沒有活動筆劃）")
        
        except Exception as e:
            self.logger.error(f"❌ 添加點失敗: {e}", exc_info=True)


    def finalize_current_stroke(self) -> None:
        """完成當前筆劃"""
        try:
            if not self.current_stroke_points:
                self.logger.warning("⚠️ 沒有點，無法完成筆劃")
                # ✅✅✅ 確保重置狀態
                self.current_state = StrokeState.IDLE
                return
            
            stroke_id = self.current_stroke_id
            num_points = len(self.current_stroke_points)
            
            # 🗑️ 過濾無效筆劃（只有一個結束事件的幽靈筆劃）
            if num_points == 1:
                first_point = self.current_stroke_points[0]
                if hasattr(first_point, 'event_type') and first_point.event_type == EventType.STROKE_END:
                    self.logger.info(
                        f"🗑️ 跳過無效筆劃: stroke_id={stroke_id}, "
                        f"只有結束事件 (pressure={first_point.pressure:.3f})"
                    )
                    self.detection_stats['strokes_rejected'] += 1
                    self.current_stroke_points = []
                    # ✅✅✅ 重置狀態為 IDLE
                    self.current_state = StrokeState.IDLE
                    # ⚠️ 不遞增 stroke_id，因為這個筆劃根本不存在
                    return
            
            # ✅ 驗證筆劃（但不影響保存）
            is_valid = self.validate_stroke(self.current_stroke_points)
            
            # ✅✅✅ 無論驗證結果如何，都保存筆劃
            self.completed_strokes.append({
                'stroke_id': stroke_id,
                'points': self.current_stroke_points.copy(),
                'start_time': self.current_stroke_points[0].timestamp,
                'end_time': self.current_stroke_points[-1].timestamp,
                'num_points': num_points,
                'is_valid': is_valid  # 🆕 添加驗證標記
            })
            
            if is_valid:
                self.logger.info(f"✅ 筆劃完成並保存（驗證通過）: stroke_id={stroke_id}, points={num_points}")
                self.detection_stats['strokes_validated'] += 1
            else:
                self.logger.warning(f"⚠️ 筆劃完成並保存（驗證失敗）: stroke_id={stroke_id}, points={num_points}")
                self.detection_stats['strokes_rejected'] += 1
            
            # ✅ 關鍵修復：立即遞增 stroke_id
            self.current_stroke_id += 1
            self.logger.info(f"🔄 stroke_id 已遞增，下一筆將使用: {self.current_stroke_id}")
            
            # ✅ 清空當前筆劃
            self.current_stroke_points = []
            
            # ✅✅✅ 強制重置狀態為 IDLE
            self.current_state = StrokeState.IDLE
            self.logger.info(f"🔄 狀態已重置為 IDLE，下一筆將使用 stroke_id={self.current_stroke_id}")
        
        except Exception as e:
            self.logger.error(f"❌ 完成筆劃失敗: {e}", exc_info=True)
            # ✅✅✅ 發生錯誤時也重置狀態
            self.current_state = StrokeState.IDLE


    def force_reset_state(self) -> None:
        """
        🆕🆕🆕 強制重置檢測器狀態（用於筆離開畫布的情況）
        
        與 reset_state() 的區別：
        - reset_state(): 完全重置，包括 stroke_id 歸零
        - force_reset_state(): 只重置當前筆劃狀態，保留 stroke_id
        """
        try:
            self.logger.info(
                f"🔄 強制重置狀態: current_state={self.current_state.name}, "
                f"current_stroke_id={self.current_stroke_id}, "
                f"current_points={len(self.current_stroke_points)}"
            )
            
            # 只清空當前筆劃數據，不重置 stroke_id
            self.current_stroke_points = []
            self.current_state = StrokeState.IDLE
            
            self.logger.info(
                f"✅ 狀態已重置為 IDLE，下一筆將使用 stroke_id={self.current_stroke_id}"
            )
            
        except Exception as e:
            self.logger.error(f"❌ 強制重置狀態失敗: {e}")


    def get_completed_strokes(self) -> List[Dict[str, Any]]:
        """獲取已完成的筆劃並清空緩衝區"""
        try:
            strokes = self.completed_strokes.copy()
            self.completed_strokes.clear()
            
            if strokes:
                self.logger.debug(f"📦 返回 {len(strokes)} 個完成的筆劃")
            
            return strokes
        
        except Exception as e:
            self.logger.error(f"❌ 獲取完成筆劃失敗: {e}")
            return []

    def validate_stroke(self, points: List[ProcessedInkPoint]) -> bool:
        """
        驗證筆劃的有效性
        
        簡化的驗證條件：
        - 至少 3 個點
        - 總長度 > 最小閾值（像素）
        """
        try:
            # ✅ 檢查點數
            if len(points) < 2:
                self.logger.warning(f"❌ 點數不足: {len(points)} < 2")
                return False
            
            # ✅ 計算總長度（像素）
            canvas_width = getattr(self.config, 'canvas_width', 800)
            canvas_height = getattr(self.config, 'canvas_height', 600)
            
            total_length = 0.0
            for i in range(1, len(points)):
                x1 = points[i-1].x * canvas_width
                y1 = points[i-1].y * canvas_height
                x2 = points[i].x * canvas_width
                y2 = points[i].y * canvas_height
                
                dx = x2 - x1
                dy = y2 - y1
                total_length += math.sqrt(dx * dx + dy * dy)
            
            # ✅ 檢查長度
            min_length = getattr(self.config, 'min_stroke_length', 10.0)  # 10 像素
            if total_length < min_length:
                self.logger.warning(f"❌ 長度不足: {total_length:.1f} < {min_length}")
                return False
            
            self.logger.info(f"✅ 筆劃驗證通過: points={len(points)}, length={total_length:.1f}px")
            return True
        
        except Exception as e:
            self.logger.error(f"❌ 驗證失敗: {e}")
            return False

    def detect_stroke_event(self, current_point: ProcessedInkPoint,
                           previous_points: List[ProcessedInkPoint],
                           current_state: StrokeState) -> Tuple[StrokeState, Optional[EventType]]:
        """
        檢測筆劃事件（保留接口兼容性）
        
        實際上這個方法在簡化版中不需要，但為了兼容性保留
        """
        # 簡化版不需要複雜的狀態轉換
        if current_point.pressure > 0:
            if current_state == StrokeState.IDLE:
                return StrokeState.ACTIVE, EventType.STROKE_START
            else:
                return StrokeState.ACTIVE, EventType.PEN_MOVE
        else:
            if current_state == StrokeState.ACTIVE:
                return StrokeState.IDLE, EventType.STROKE_END
            else:
                return StrokeState.IDLE, None

    def is_stroke_start(self, current_point: ProcessedInkPoint,
                       previous_points: List[ProcessedInkPoint]) -> bool:
        """判斷是否為筆劃開始"""
        return current_point.pressure > 0

    def is_stroke_end(self, current_point: ProcessedInkPoint,
                     previous_points: List[ProcessedInkPoint],
                     stroke_start_time: float) -> bool:
        """判斷是否為筆劃結束"""
        return current_point.pressure == 0

    def detect_pause(self, points: List[ProcessedInkPoint],
                    current_time: float) -> bool:
        """檢測暫停（簡化版不需要）"""
        return False

    def detect_resume(self, current_point: ProcessedInkPoint,
                     last_active_time: float) -> bool:
        """檢測恢復（簡化版不需要）"""
        return False

    def split_stroke(self, points: List[ProcessedInkPoint],
                    split_criteria: str = 'pause') -> List[List[ProcessedInkPoint]]:
        """分割筆劃（簡化版不需要）"""
        return [points]

    def merge_strokes(self, stroke1_points: List[ProcessedInkPoint],
                     stroke2_points: List[ProcessedInkPoint],
                     max_gap_time: float = 0.5) -> Optional[List[ProcessedInkPoint]]:
        """合併筆劃（簡化版不需要）"""
        return None

    def get_detection_statistics(self) -> Dict[str, Any]:
        """獲取檢測統計資訊"""
        return self.detection_stats.copy()

    def reset_statistics(self) -> None:
        """重置統計資訊"""
        self.detection_stats = {
            'strokes_detected': 0,
            'strokes_validated': 0,
            'strokes_rejected': 0,
            'total_points': 0
        }

    def reset_state(self) -> None:
        """重置檢測器狀態"""
        self.current_stroke_id = 0
        self.current_stroke_points = []
        self.completed_strokes = []
        self.current_state = StrokeState.IDLE
        self.logger.info("✅ 檢測器狀態已重置")

    def get_current_thresholds(self) -> Dict[str, float]:
        """獲取當前閾值"""
        return {
            'pressure_threshold': self.pressure_threshold
        }

    def update_thresholds(self, new_thresholds: Dict[str, float]) -> None:
        """更新閾值"""
        for key, value in new_thresholds.items():
            if hasattr(self, key):
                setattr(self, key, value)
                self.logger.info(f"✅ 更新閾值 {key}: {value}")

    def export_detection_log(self) -> Dict[str, Any]:
        """導出檢測日誌"""
        return {
            'statistics': self.get_detection_statistics(),
            'thresholds': self.get_current_thresholds(),
            'current_stroke_id': self.current_stroke_id,
            'current_state': self.current_state.name
        }
