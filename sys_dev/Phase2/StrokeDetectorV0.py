import math
import numpy as np
from typing import List, Optional, Tuple, Dict, Any
import logging
from collections import deque
from scipy import signal
from scipy.spatial.distance import euclidean
from DigitalInkDataStructure import ProcessedInkPoint, StrokeState, EventType
from Config import ProcessingConfig
class StrokeDetector:
    """筆劃檢測器 - 負責檢測和管理筆劃邊界"""
    def __init__(self, config: ProcessingConfig):
        """
        初始化筆劃檢測器
        
        Args:
            config: 處理配置參數
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 筆劃管理
        self.current_stroke_points = []  # 當前筆劃的點
        self.completed_strokes = []      # 已完成的筆劃
        self.current_state = StrokeState.IDLE  # 當前狀態
        # 檢測參數
        self.pressure_threshold = config.pressure_threshold
        self.velocity_threshold = config.velocity_threshold
        self.pause_duration_threshold = config.pause_duration_threshold
        self.min_stroke_length = config.min_stroke_length
        
        # 狀態管理
        self.current_stroke_id = 0
        self.stroke_start_time = None
        self.last_active_time = None
        
        # 檢測歷史緩衝
        self.pressure_history = deque(maxlen=10)  # 壓力歷史
        self.velocity_history = deque(maxlen=10)  # 速度歷史
        self.state_history = deque(maxlen=5)      # 狀態歷史
        
        # 檢測閾值 (可調整)
        self.detection_thresholds = {
            'min_stroke_duration': 0.02,      # 最小筆劃持續時間 (秒)
            'max_stroke_duration': 30.0,      # 最大筆劃持續時間 (秒)
            'min_points_per_stroke': 3,       # 最小點數
            'max_point_gap': 0.2,             # 最大點間時間間隔
            'pressure_stability_window': 5,   # 壓力穩定性檢查窗口
            'velocity_stability_window': 5,   # 速度穩定性檢查窗口
            'direction_change_threshold': math.pi / 3,  # 方向變化閾值
            'pressure_drop_threshold': 0.3,   # 壓力下降閾值
        }
        
        # 統計資訊
        self.detection_stats = {
            'strokes_detected': 0,
            'strokes_validated': 0,
            'strokes_rejected': 0,
            'pauses_detected': 0,
            'resumes_detected': 0,
            'splits_performed': 0,
            'merges_performed': 0
        }

    def initialize(self) -> bool:
        """
        初始化筆劃檢測器
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            self.logger.info("正在初始化筆劃檢測器...")
            
            # 重置狀態
            self.reset_state()
            
            # 重置統計資訊
            self.reset_statistics()
            
            # 驗證配置參數
            if not self._validate_detector_config():
                self.logger.error("筆劃檢測器配置無效")
                return False
            
            # 初始化檢測閾值
            self._initialize_detection_thresholds()
            
            self.logger.info("筆劃檢測器初始化成功")
            return True
            
        except Exception as e:
            self.logger.error(f"筆劃檢測器初始化失敗: {str(e)}")
            return False

    def _validate_detector_config(self) -> bool:
        """驗證檢測器配置"""
        try:
            # 檢查必要的配置參數
            required_attrs = [
                'pressure_threshold', 'velocity_threshold', 
                'pause_duration_threshold', 'min_stroke_length'
            ]
            
            for attr in required_attrs:
                if not hasattr(self.config, attr):
                    self.logger.error(f"缺少配置參數: {attr}")
                    return False
            
            # 檢查參數值的合理性
            if self.config.pressure_threshold < 0 or self.config.pressure_threshold > 1:
                self.logger.error(f"壓力閾值無效: {self.config.pressure_threshold}")
                return False
                
            if self.config.velocity_threshold <= 0:
                self.logger.error(f"速度閾值無效: {self.config.velocity_threshold}")
                return False
                
            if self.config.pause_duration_threshold <= 0:
                self.logger.error(f"暫停持續時間閾值無效: {self.config.pause_duration_threshold}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"配置驗證失敗: {str(e)}")
            return False

    def _initialize_detection_thresholds(self) -> None:
        """初始化檢測閾值"""
        try:
            # 從配置更新閾值
            self.pressure_threshold = self.config.pressure_threshold
            self.velocity_threshold = self.config.velocity_threshold
            self.pause_duration_threshold = self.config.pause_duration_threshold
            self.min_stroke_length = self.config.min_stroke_length
            
            # 設置其他檢測參數的預設值
            if hasattr(self.config, 'min_stroke_duration'):
                self.detection_thresholds['min_stroke_duration'] = self.config.min_stroke_duration
            
            if hasattr(self.config, 'max_stroke_duration'):
                self.detection_thresholds['max_stroke_duration'] = self.config.max_stroke_duration
            
            self.logger.info(f"檢測閾值已設置: pressure={self.pressure_threshold}, "
                            f"velocity={self.velocity_threshold}, "
                            f"pause_duration={self.pause_duration_threshold}")
            
        except Exception as e:
            self.logger.error(f"初始化檢測閾值失敗: {str(e)}")

    def shutdown(self) -> None:
        """關閉筆劃檢測器，清理資源"""
        try:
            self.logger.info("正在關閉筆劃檢測器...")
            
            # 重置狀態
            self.reset_state()
            
            # 重置統計資訊
            self.reset_statistics()
            
            self.logger.info("筆劃檢測器已關閉")
            
        except Exception as e:
            self.logger.error(f"關閉筆劃檢測器失敗: {str(e)}")


    def add_point(self, point: ProcessedInkPoint) -> None:
        """
        添加點到檢測器並進行實時筆劃檢測
        
        Args:
            point: 要添加的處理後點
        """
        try:
            # ✅✅✅ 診斷日誌（可選，調試完成後可以移除）
            self.logger.debug(f"🔍 add_point: state={self.current_state}, "
                            f"stroke_id={self.current_stroke_id}, "
                            f"points={len(self.current_stroke_points)}, "
                            f"pressure={point.pressure:.3f}")
            
            # ✅ 防止重複處理 COMPLETED 狀態
            if self.current_state == StrokeState.COMPLETED:
                self.logger.debug("⚠️ 當前筆劃已完成，重置為 IDLE 狀態")
                self.current_state = StrokeState.IDLE
                self.current_stroke_points = []
            
            # 更新檢測歷史
            self._update_detection_history(point)
            
            # ✅ 執行筆劃事件檢測
            new_state, event_type = self.detect_stroke_event(
                current_point=point,
                previous_points=self.current_stroke_points,
                current_state=self.current_state
            )
            
            # ✅✅✅ 關鍵修復：根據狀態轉換正確處理點
            if new_state == StrokeState.STARTING:
                # 🎨 開始新筆劃
                self.current_stroke_points = [point]  # ✅ 立即添加第一個點
                self.logger.info(f"🎨 筆劃開始: stroke_id={self.current_stroke_id}")
            
            elif new_state == StrokeState.ACTIVE:
                # ✅✅✅ 修復：無論從哪個狀態轉換來，都要添加當前點
                if self.current_state == StrokeState.STARTING:
                    # 從 STARTING 轉換到 ACTIVE
                    self.current_stroke_points.append(point)  # ✅ 添加當前點
                    self.logger.debug(f"✅ 筆劃轉為 ACTIVE: stroke_id={self.current_stroke_id}, "
                                    f"points={len(self.current_stroke_points)}")
                elif self.current_state == StrokeState.ACTIVE:
                    # 保持 ACTIVE 狀態
                    self.current_stroke_points.append(point)
                else:
                    # 從其他狀態轉換到 ACTIVE（不太可能，但為了安全）
                    self.logger.warning(f"⚠️ 從 {self.current_state} 轉換到 ACTIVE")
                    self.current_stroke_points.append(point)
            
            elif new_state == StrokeState.ENDING:
                # 筆劃結束中
                self.current_stroke_points.append(point)
                self.logger.debug(f"🔚 筆劃進入 ENDING 狀態: stroke_id={self.current_stroke_id}")
            
            elif new_state == StrokeState.COMPLETED:
                # 筆劃完成
                if self.current_stroke_points:
                    # 驗證筆劃
                    if self.validate_stroke(self.current_stroke_points):
                        # 將完成的筆劃加入緩衝區
                        self.completed_strokes.append({
                            'stroke_id': self.current_stroke_id,
                            'points': self.current_stroke_points.copy(),  # ✅ 複製點列表
                            'start_time': self.current_stroke_points[0].timestamp,
                            'end_time': self.current_stroke_points[-1].timestamp,
                            'num_points': len(self.current_stroke_points)
                        })
                        self.logger.info(f"✅ 筆劃完成: stroke_id={self.current_stroke_id}, "
                                        f"points={len(self.current_stroke_points)}")
                        self.detection_stats['strokes_validated'] += 1
                    else:
                        self.logger.warning(f"❌ 筆劃驗證失敗: stroke_id={self.current_stroke_id}, "
                                        f"points={len(self.current_stroke_points)}")
                        self.detection_stats['strokes_rejected'] += 1
                    
                    # ✅ 重置當前筆劃（為下一個筆劃做準備）
                    self.current_stroke_points = []
                else:
                    self.logger.warning(f"⚠️ COMPLETED 狀態但沒有點: stroke_id={self.current_stroke_id}")
            
            elif new_state == StrokeState.IDLE:
                # 空閒狀態
                if self.current_stroke_points:
                    # 如果有未完成的筆劃，清空
                    self.logger.debug(f"⚠️ 轉為 IDLE 狀態，清空 {len(self.current_stroke_points)} 個點")
                    self.current_stroke_points = []
            
            # ✅ 更新狀態
            self.current_state = new_state
            
        except Exception as e:
            self.logger.error(f"添加點失敗: {str(e)}", exc_info=True)



    def get_completed_strokes(self) -> List[Dict[str, Any]]:
        """
        獲取已完成的筆劃列表並清空緩衝區
        
        Returns:
            List[Dict[str, Any]]: 已完成的筆劃列表
        """
        try:
            # 返回所有已完成的筆劃
            strokes = self.completed_strokes.copy()
            
            # 清空緩衝區（避免重複處理）
            self.completed_strokes.clear()
            
            if strokes:
                self.logger.debug(f"📦 返回 {len(strokes)} 個完成的筆劃")
            
            return strokes
            
        except Exception as e:
            self.logger.error(f"獲取完成筆劃失敗: {str(e)}")
            return []


    def detect_stroke_event(self, current_point: ProcessedInkPoint,
                        previous_points: List[ProcessedInkPoint],
                        current_state: StrokeState) -> Tuple[StrokeState, Optional[EventType]]:
        """
        檢測筆劃事件和狀態變化
        
        Args:
            current_point: 當前處理的點
            previous_points: 前面的點列表
            current_state: 當前筆劃狀態
            
        Returns:
            Tuple[StrokeState, Optional[EventType]]: 新狀態和檢測到的事件類型
            
        Note:
            狀態轉換邏輯：
            IDLE -> STARTING (壓力 > 閾值)
            STARTING -> ACTIVE (持續壓力)
            ACTIVE -> ENDING (壓力 < 閾值)
            ENDING -> COMPLETED (確認結束)
            COMPLETED -> IDLE (準備下一筆劃)
        """
        try:
            # 更新檢測歷史
            self._update_detection_history(current_point)
            
            new_state = current_state
            event_type = None
            
            # 狀態轉換邏輯
            if current_state == StrokeState.IDLE:
                if self.is_stroke_start(current_point, previous_points):
                    new_state = StrokeState.STARTING
                    event_type = EventType.STROKE_START
                    self.stroke_start_time = current_point.timestamp
                    self.current_stroke_id += 1
                    self.detection_stats['strokes_detected'] += 1
                    self.logger.debug(f"檢測到筆劃開始: stroke_id={self.current_stroke_id}")
            
            elif current_state == StrokeState.STARTING:
                if self._is_pressure_stable_high(current_point):
                    new_state = StrokeState.ACTIVE
                    event_type = EventType.PEN_MOVE
                    self.logger.debug(f"筆劃變為活躍狀態: stroke_id={self.current_stroke_id}")
                elif current_point.pressure < self.pressure_threshold:
                    # 假開始，回到IDLE
                    new_state = StrokeState.IDLE
                    self.stroke_start_time = None
            
            elif current_state == StrokeState.ACTIVE:
                if self.is_stroke_end(current_point, previous_points, self.stroke_start_time):
                    new_state = StrokeState.ENDING
                    event_type = EventType.PEN_UP
                    self.logger.debug(f"檢測到筆劃結束: stroke_id={self.current_stroke_id}")
                elif self.detect_pause(previous_points, current_point.timestamp):
                    event_type = EventType.PAUSE_DETECTED
                    self.detection_stats['pauses_detected'] += 1
                else:
                    event_type = EventType.PEN_MOVE
            
            elif current_state == StrokeState.ENDING:
                if self._is_stroke_end_confirmed(current_point, previous_points):
                    new_state = StrokeState.COMPLETED
                    event_type = EventType.STROKE_END
                elif current_point.pressure > self.pressure_threshold:
                    # 重新開始，回到ACTIVE
                    new_state = StrokeState.ACTIVE
                    event_type = EventType.RESUME_DETECTED
                    self.detection_stats['resumes_detected'] += 1
            
            elif current_state == StrokeState.COMPLETED:
                new_state = StrokeState.IDLE
                self.stroke_start_time = None
                # 準備下一個筆劃
            
            # 更新狀態歷史
            self.state_history.append((current_state, new_state, current_point.timestamp))
            self.last_active_time = current_point.timestamp
            
            return new_state, event_type
            
        except Exception as e:
            self.logger.error(f"檢測筆劃事件失敗: {str(e)}")
            return current_state, None

    def is_stroke_start(self, current_point: ProcessedInkPoint,
                    previous_points: List[ProcessedInkPoint]) -> bool:
        """
        判斷是否為筆劃開始
        
        Args:
            current_point: 當前點
            previous_points: 前面的點列表
            
        Returns:
            bool: 是否為筆劃開始
            
        Note:
            檢測條件：
            - 壓力從低於閾值變為高於閾值
            - 前面沒有活躍的筆劃
            - 可選：檢測筆的接觸事件
        """
        try:
            # 基本壓力檢查
            if current_point.pressure < self.pressure_threshold:
                return False
            
            # 檢查壓力變化趨勢
            if len(previous_points) > 0:
                # 檢查前面幾個點的壓力是否都低於閾值
                recent_points = previous_points[-3:] if len(previous_points) >= 3 else previous_points
                
                # 所有前面的點壓力都應該低於閾值
                for point in recent_points:
                    if point.pressure >= self.pressure_threshold:
                        return False
                
                # 檢查壓力上升趨勢
                if len(recent_points) >= 2:
                    pressure_trend = self._calculate_pressure_trend(recent_points + [current_point])
                    if pressure_trend <= 0:  # 壓力沒有上升趨勢
                        return False
            
            # 檢查是否有足夠的移動 (避免誤觸)
            if len(previous_points) > 0:
                last_point = previous_points[-1]
                distance = self._calculate_distance(current_point, last_point)
                if distance < 0.001:  # 移動距離太小
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"檢測筆劃開始失敗: {str(e)}")
            return False

    def is_stroke_end(self, current_point: ProcessedInkPoint,
                    previous_points: List[ProcessedInkPoint],
                    stroke_start_time: float) -> bool:
        """
        判斷是否為筆劃結束
        
        Args:
            current_point: 當前點
            previous_points: 前面的點列表  
            stroke_start_time: 筆劃開始時間
            
        Returns:
            bool: 是否為筆劃結束
            
        Note:
            檢測條件：
            - 壓力持續低於閾值
            - 筆劃持續時間超過最小閾值
            - 可選：檢測筆的離開事件
        """
        try:
            # 基本壓力檢查
            if current_point.pressure >= self.pressure_threshold:
                return False
            
            # 檢查筆劃持續時間
            if stroke_start_time is not None:
                duration = current_point.timestamp - stroke_start_time
                if duration < self.detection_thresholds['min_stroke_duration']:
                    return False
            
            # 檢查壓力下降趨勢
            if len(previous_points) >= 3:
                recent_points = previous_points[-3:]
                
                # 檢查最近幾個點的壓力是否都在下降
                pressure_trend = self._calculate_pressure_trend(recent_points + [current_point])
                if pressure_trend >= 0:  # 壓力沒有下降趨勢
                    return False
                
                # 檢查是否所有最近的點壓力都低於閾值
                for point in recent_points:
                    if point.pressure >= self.pressure_threshold:
                        return False
            
            # 檢查速度是否降低 (筆離開時通常速度會降低)
            if len(previous_points) >= 2:
                recent_velocities = [p.velocity for p in previous_points[-2:]] + [current_point.velocity]
                if np.mean(recent_velocities) > self.velocity_threshold * 2:
                    return False  # 速度太高，可能不是真正的結束
            
            return True
            
        except Exception as e:
            self.logger.error(f"檢測筆劃結束失敗: {str(e)}")
            return False

    def detect_pause(self, points: List[ProcessedInkPoint],
                    current_time: float) -> bool:
        """
        檢測繪畫暫停
        
        Args:
            points: 最近的點列表
            current_time: 當前時間
            
        Returns:
            bool: 是否檢測到暫停
            
        Note:
            暫停條件：
            - 在閾值時間內沒有新的點
            - 最後幾個點的速度都很低
            - 壓力保持在較低水平
        """
        try:
            if len(points) == 0:
                return False
            
            # 檢查時間間隔
            last_point = points[-1]
            time_gap = current_time - last_point.timestamp
            
            if time_gap < self.pause_duration_threshold:
                return False
            
            # 檢查最近點的速度
            recent_points = points[-5:] if len(points) >= 5 else points
            if len(recent_points) >= 2:
                avg_velocity = np.mean([p.velocity for p in recent_points])
                if avg_velocity > self.velocity_threshold:
                    return False  # 速度太高，不是暫停
            
            # 檢查壓力穩定性
            if len(recent_points) >= 3:
                pressures = [p.pressure for p in recent_points]
                pressure_std = np.std(pressures)
                if pressure_std > 0.1:  # 壓力變化太大
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"檢測暫停失敗: {str(e)}")
            return False

    def detect_resume(self, current_point: ProcessedInkPoint,
                    last_active_time: float) -> bool:
        """
        檢測繪畫恢復
        
        Args:
            current_point: 當前點
            last_active_time: 最後活躍時間
            
        Returns:
            bool: 是否檢測到恢復
        """
        try:
            # 檢查時間間隔
            time_gap = current_point.timestamp - last_active_time
            if time_gap < self.pause_duration_threshold:
                return False
            
            # 檢查壓力是否重新上升
            if current_point.pressure < self.pressure_threshold:
                return False
            
            # 檢查是否有足夠的移動
            if current_point.velocity < self.velocity_threshold:
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"檢測恢復失敗: {str(e)}")
            return False

    def finalize_current_stroke(self) -> None:
        """
        強制完成當前筆劃（用於外部觸發）
        """
        try:
            self.logger.info(f"🔍 finalize_current_stroke 被調用，當前狀態: {self.current_state}, 點數: {len(self.current_stroke_points)}")
            
            if not self.current_stroke_points:
                self.logger.warning("⚠️ 沒有當前筆劃點，無法完成")
                return
            
            # ✅ 記錄當前筆劃信息
            num_points = len(self.current_stroke_points)
            stroke_id = self.current_stroke_id
            
            # ✅ 驗證並保存當前筆劃
            if self.validate_stroke(self.current_stroke_points):
                self.completed_strokes.append({
                    'stroke_id': stroke_id,
                    'points': self.current_stroke_points.copy(),
                    'start_time': self.current_stroke_points[0].timestamp,
                    'end_time': self.current_stroke_points[-1].timestamp,
                    'num_points': num_points
                })
                self.logger.info(f"✅ 筆劃完成: stroke_id={stroke_id}, points={num_points}")
                self.detection_stats['strokes_validated'] += 1
            else:
                self.logger.warning(f"❌ 筆劃驗證失敗: stroke_id={stroke_id}, points={num_points}")
                self.detection_stats['strokes_rejected'] += 1
            
            # ✅✅✅ 修復：重置狀態並清空點列表
            self.current_stroke_points = []
            self.current_state = StrokeState.COMPLETED
            
            # ✅ 不在這裡增加 stroke_id，而是在檢測到新筆劃開始時增加
            
        except Exception as e:
            self.logger.error(f"強制完成筆劃失敗: {str(e)}", exc_info=True)



    def validate_stroke(self, points: List[ProcessedInkPoint]) -> bool:
        """
        驗證筆劃的有效性
        
        Args:
            points: 筆劃的所有點
            
        Returns:
            bool: 筆劃是否有效
            
        Note:
            驗證條件：
            - 點數量超過最小閾值
            - 總長度超過最小閾值
            - 持續時間在合理範圍內
            - 沒有異常的跳躍或斷點
        """
        try:
            # ✅ 添加開始驗證的日誌
            self.logger.info(f"🔍 開始驗證筆劃: points={len(points)}")
            
            # 檢查點數
            min_points = self.detection_thresholds['min_points_per_stroke']
            if len(points) < min_points:
                self.logger.warning(f"❌ 筆劃點數不足: {len(points)} < {min_points}")
                self.detection_stats['strokes_rejected'] += 1
                return False
            self.logger.info(f"✅ 點數檢查通過: {len(points)} >= {min_points}")
            
            # 計算總長度
            total_length = self._calculate_total_length(points)
            if total_length < self.min_stroke_length:
                self.logger.warning(f"❌ 筆劃長度不足: {total_length:.3f} < {self.min_stroke_length}")
                self.detection_stats['strokes_rejected'] += 1
                return False
            self.logger.info(f"✅ 長度檢查通過: {total_length:.3f} >= {self.min_stroke_length}")
            
            # 檢查持續時間
            duration = points[-1].timestamp - points[0].timestamp
            min_duration = self.detection_thresholds['min_stroke_duration']
            max_duration = self.detection_thresholds['max_stroke_duration']
            
            if duration < min_duration:
                self.logger.warning(f"❌ 筆劃持續時間過短: {duration:.3f}s < {min_duration}s")
                self.detection_stats['strokes_rejected'] += 1
                return False
            
            if duration > max_duration:
                self.logger.warning(f"❌ 筆劃持續時間過長: {duration:.3f}s > {max_duration}s")
                self.detection_stats['strokes_rejected'] += 1
                return False
            
            self.logger.info(f"✅ 持續時間檢查通過: {duration:.3f}s ({min_duration}s ~ {max_duration}s)")
            
            # ✅✅✅ 修復：檢查點間時間間隔，但允許暫停
            max_gap = self.detection_thresholds['max_point_gap']
            pause_detected = False
            
            for i in range(1, len(points)):
                time_gap = points[i].timestamp - points[i-1].timestamp
                if time_gap > max_gap:
                    # ✅ 記錄暫停，但不拒絕筆劃
                    self.logger.warning(f"⚠️ 檢測到暫停: {time_gap:.3f}s > {max_gap}s (點 {i-1} -> {i})")
                    pause_detected = True
                    # ❌ 不再直接返回 False
                    # return False
            
            if pause_detected:
                self.logger.info(f"⚠️ 筆劃包含暫停，但仍然有效")
            else:
                self.logger.info(f"✅ 時間間隔檢查通過: 所有間隔 <= {max_gap}s")
            
            # 檢查異常跳躍
            if not self._check_spatial_continuity(points):
                self.logger.warning("❌ 檢測到空間不連續性")
                self.detection_stats['strokes_rejected'] += 1
                return False
            self.logger.info("✅ 空間連續性檢查通過")
            
            # ✅ 所有檢查通過
            self.detection_stats['strokes_validated'] += 1
            self.logger.info(f"✅✅✅ 筆劃驗證通過: points={len(points)}, length={total_length:.3f}, duration={duration:.3f}s")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 驗證筆劃時發生異常: {str(e)}")
            self.detection_stats['strokes_rejected'] += 1
            return False



    def split_stroke(self, points: List[ProcessedInkPoint],
                    split_criteria: str = 'pause') -> List[List[ProcessedInkPoint]]:
        """
        根據指定條件分割筆劃
        
        Args:
            points: 原始筆劃點列表
            split_criteria: 分割條件 ('pause', 'direction_change', 'pressure_drop')
            
        Returns:
            List[List[ProcessedInkPoint]]: 分割後的筆劃段列表
        """
        try:
            if len(points) < 6:  # 太短的筆劃不分割
                return [points]
            
            split_indices = []
            
            if split_criteria == 'pause':
                split_indices = self._find_pause_split_points(points)
            elif split_criteria == 'direction_change':
                split_indices = self._find_direction_change_split_points(points)
            elif split_criteria == 'pressure_drop':
                split_indices = self._find_pressure_drop_split_points(points)
            else:
                self.logger.warning(f"未知的分割條件: {split_criteria}")
                return [points]
            
            if not split_indices:
                return [points]
            
            # 執行分割
            segments = []
            start_idx = 0
            
            for split_idx in sorted(split_indices):
                if split_idx > start_idx and split_idx < len(points):
                    segment = points[start_idx:split_idx + 1]
                    if len(segment) >= 2:  # 確保段落有足夠的點
                        segments.append(segment)
                    start_idx = split_idx
            
            # 添加最後一段
            if start_idx < len(points) - 1:
                final_segment = points[start_idx:]
                if len(final_segment) >= 2:
                    segments.append(final_segment)
            
            self.detection_stats['splits_performed'] += 1
            self.logger.debug(f"筆劃分割完成: {len(segments)} 段")
            
            return segments if segments else [points]
            
        except Exception as e:
            self.logger.error(f"分割筆劃失敗: {str(e)}")
            return [points]

    def merge_strokes(self, stroke1_points: List[ProcessedInkPoint],
                    stroke2_points: List[ProcessedInkPoint],
                    max_gap_time: float = 0.5) -> Optional[List[ProcessedInkPoint]]:
        """
        合併兩個相鄰的筆劃
        
        Args:
            stroke1_points: 第一個筆劃的點
            stroke2_points: 第二個筆劃的點
            max_gap_time: 最大允許的時間間隔
            
        Returns:
            Optional[List[ProcessedInkPoint]]: 合併後的點列表，如果無法合併則返回None
        """
        try:
            if not stroke1_points or not stroke2_points:
                return None
            
            # 檢查時間順序
            end_time_1 = stroke1_points[-1].timestamp
            start_time_2 = stroke2_points[0].timestamp
            
            if start_time_2 <= end_time_1:
                self.logger.debug("筆劃時間順序錯誤，無法合併")
                return None
            
            # 檢查時間間隔
            time_gap = start_time_2 - end_time_1
            if time_gap > max_gap_time:
                self.logger.debug(f"時間間隔過大: {time_gap}")
                return None
            
            # 檢查空間距離
            end_point_1 = stroke1_points[-1]
            start_point_2 = stroke2_points[0]
            spatial_gap = self._calculate_distance(end_point_1, start_point_2)
            
            if spatial_gap > 0.1:  # 空間距離閾值
                self.logger.debug(f"空間距離過大: {spatial_gap}")
                return None
            
            # 檢查方向連續性
            if not self._check_direction_continuity(stroke1_points, stroke2_points):
                self.logger.debug("方向不連續，無法合併")
                return None
            
            # 執行合併
            merged_points = stroke1_points.copy()
            
            # 可選：在兩個筆劃間插值
            if time_gap > 0.01:  # 如果有明顯間隔，進行插值
                interpolated = self._interpolate_gap(end_point_1, start_point_2)
                merged_points.extend(interpolated)
            
            merged_points.extend(stroke2_points)
            
            # 重新分配筆劃ID和索引
            self._reassign_stroke_properties(merged_points)
            
            self.detection_stats['merges_performed'] += 1
            self.logger.debug(f"筆劃合併完成: {len(merged_points)} 個點")
            
            return merged_points
            
        except Exception as e:
            self.logger.error(f"合併筆劃失敗: {str(e)}")
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
            'pauses_detected': 0,
            'resumes_detected': 0,
            'splits_performed': 0,
            'merges_performed': 0
        }

    def reset_state(self) -> None:
        """重置檢測器狀態"""
        self.current_stroke_id = 0
        self.stroke_start_time = None
        self.last_active_time = None
        self.pressure_history.clear()
        self.velocity_history.clear()
        self.state_history.clear()
        self.current_stroke_points = []
        self.completed_strokes = []
        self.current_state = StrokeState.IDLE


    # 私有輔助方法

    def _update_detection_history(self, point: ProcessedInkPoint) -> None:
        """更新檢測歷史"""
        self.pressure_history.append(point.pressure)
        self.velocity_history.append(point.velocity)

    def _is_pressure_stable_high(self, point: ProcessedInkPoint) -> bool:
        """檢查壓力是否穩定高於閾值"""
        if len(self.pressure_history) < self.detection_thresholds['pressure_stability_window']:
            return point.pressure > self.pressure_threshold
        
        recent_pressures = list(self.pressure_history)[-self.detection_thresholds['pressure_stability_window']:]
        return all(p > self.pressure_threshold for p in recent_pressures)

    def _is_stroke_end_confirmed(self, current_point: ProcessedInkPoint,
                                previous_points: List[ProcessedInkPoint]) -> bool:
        """確認筆劃結束"""
        # 檢查壓力是否持續低於閾值
        if current_point.pressure >= self.pressure_threshold:
            return False
        
        # 檢查最近幾個點的壓力
        if len(previous_points) >= 2:
            recent_points = previous_points[-2:]
            for point in recent_points:
                if point.pressure >= self.pressure_threshold:
                    return False
        
        return True

    def _calculate_pressure_trend(self, points: List[ProcessedInkPoint]) -> float:
        """計算壓力變化趨勢"""
        if len(points) < 2:
            return 0.0
        
        pressures = [p.pressure for p in points]
        # 使用線性回歸計算趨勢
        x = np.arange(len(pressures))
        coeffs = np.polyfit(x, pressures, 1)
        return coeffs[0]  # 斜率

    def _calculate_distance(self, point1: ProcessedInkPoint,
                        point2: ProcessedInkPoint) -> float:
        """計算兩點間距離"""
        dx = point1.x - point2.x
        dy = point1.y - point2.y
        return math.sqrt(dx * dx + dy * dy)

    def _calculate_total_length(self, points: List[ProcessedInkPoint]) -> float:
        """
        計算筆劃總長度（像素單位）
        
        Args:
            points: 筆劃的所有點
            
        Returns:
            float: 總長度（像素單位）
        """
        if len(points) < 2:
            return 0.0
        
        # ✅ 獲取畫布尺寸（用於反歸一化）
        # 方法 1：從配置中獲取
        canvas_width = getattr(self.config, 'canvas_width', 800)
        canvas_height = getattr(self.config, 'canvas_height', 600)
        
        # 或者方法 2：如果沒有配置，使用固定值
        # canvas_width = 800
        # canvas_height = 600
        
        total_length = 0.0
        for i in range(1, len(points)):
            # ✅ 將歸一化座標轉換為像素座標
            x1 = points[i-1].x * canvas_width
            y1 = points[i-1].y * canvas_height
            x2 = points[i].x * canvas_width
            y2 = points[i].y * canvas_height
            
            # ✅ 計算像素距離
            dx = x2 - x1
            dy = y2 - y1
            segment_length = math.sqrt(dx * dx + dy * dy)
            total_length += segment_length
        
        return total_length


    def _check_spatial_continuity(self, points: List[ProcessedInkPoint]) -> bool:
        """檢查空間連續性（像素單位）"""
        if len(points) < 2:
            return True
        
        # ✅ 獲取畫布尺寸
        canvas_width = getattr(self.config, 'canvas_width', 800)
        canvas_height = getattr(self.config, 'canvas_height', 600)
        
        # ✅✅✅ 修復：放寬跳躍閾值到 200 像素（適應快速繪製）
        max_allowed_jump = 200.0  # 從 50.0 改為 200.0
        
        for i in range(1, len(points)):
            # ✅ 轉換為像素座標
            x1 = points[i-1].x * canvas_width
            y1 = points[i-1].y * canvas_height
            x2 = points[i].x * canvas_width
            y2 = points[i].y * canvas_height
            
            # ✅ 計算像素距離
            dx = x2 - x1
            dy = y2 - y1
            distance = math.sqrt(dx * dx + dy * dy)
            
            if distance > max_allowed_jump:
                self.logger.warning(f"檢測到異常跳躍: {distance:.1f} 像素")
                return False
        
        return True


    def _find_pause_split_points(self, points: List[ProcessedInkPoint]) -> List[int]:
        """找到基於暫停的分割點"""
        split_points = []
        
        for i in range(1, len(points) - 1):
            # 檢查時間間隔
            time_gap = points[i+1].timestamp - points[i].timestamp
            if time_gap > self.pause_duration_threshold:
                split_points.append(i)
        
        return split_points

    def _find_direction_change_split_points(self, points: List[ProcessedInkPoint]) -> List[int]:
        """找到基於方向變化的分割點"""
        split_points = []
        
        if len(points) < 4:
            return split_points
        
        for i in range(2, len(points) - 1):
            # 計算前後方向
            dir1 = math.atan2(points[i].y - points[i-1].y, points[i].x - points[i-1].x)
            dir2 = math.atan2(points[i+1].y - points[i].y, points[i+1].x - points[i].x)
            
            # 計算角度差
            angle_diff = abs(dir2 - dir1)
            if angle_diff > math.pi:
                angle_diff = 2 * math.pi - angle_diff
            
            if angle_diff > self.detection_thresholds['direction_change_threshold']:
                split_points.append(i)
        
        return split_points

    def _find_pressure_drop_split_points(self, points: List[ProcessedInkPoint]) -> List[int]:
        """找到基於壓力下降的分割點"""
        split_points = []
        
        for i in range(1, len(points) - 1):
            pressure_drop = points[i-1].pressure - points[i].pressure
            if pressure_drop > self.detection_thresholds['pressure_drop_threshold']:
                split_points.append(i)
        
        return split_points
  
    def _check_direction_continuity(self, stroke1: List[ProcessedInkPoint],
                                 stroke2: List[ProcessedInkPoint]) -> bool:
        """檢查兩個筆劃的方向連續性"""
        if len(stroke1) < 2 or len(stroke2) < 2:
            return True
      
        # 計算第一個筆劃末尾的方向
        end_dir1 = math.atan2(
            stroke1[-1].y - stroke1[-2].y,
            stroke1[-1].x - stroke1[-2].x
        )
      
        # 計算第二個筆劃開頭的方向
        start_dir2 = math.atan2(
            stroke2[1].y - stroke2[0].y,
            stroke2[1].x - stroke2[0].x
        )
      
        # 計算角度差
        angle_diff = abs(end_dir1 - start_dir2)
        if angle_diff > math.pi:
            angle_diff = 2 * math.pi - angle_diff
      
        return angle_diff < math.pi / 2  # 允許90度以內的方向變化
  
    def _interpolate_gap(self, point1: ProcessedInkPoint,
                      point2: ProcessedInkPoint) -> List[ProcessedInkPoint]:
        """在兩點間插值"""
        interpolated = []
        
        time_gap = point2.timestamp - point1.timestamp
        if time_gap <= 0.01:  # 間隔太小不需要插值
            return interpolated
        # 計算插值點數量 (基於時間間隔)
        target_interval = 0.005  # 5ms 間隔
        num_points = int(time_gap / target_interval) - 1
            
        if num_points <= 0:
            return interpolated
            
        # 限制插值點數量，避免過多
        num_points = min(num_points, 10)
            
        # 線性插值座標
        x_step = (point2.x - point1.x) / (num_points + 1)
        y_step = (point2.y - point1.y) / (num_points + 1)
            
        # 插值壓力 (使用三次樣條或線性)
        pressure_step = (point2.pressure - point1.pressure) / (num_points + 1)
            
        # 插值時間戳
        time_step = time_gap / (num_points + 1)
            
        for i in range(1, num_points + 1):
            # 創建插值點
            interp_point = ProcessedInkPoint(
                x=point1.x + x_step * i,
                y=point1.y + y_step * i,
                pressure=max(0.0, point1.pressure + pressure_step * i),
                timestamp=point1.timestamp + time_step * i,
                stroke_id=point1.stroke_id,
                point_index=point1.point_index + i,
                velocity=0.0,  # 將在後續計算
                acceleration=0.0,
                direction=0.0,
                curvature=0.0,
                is_interpolated=True
            )
                
            # 計算速度 (簡單估算)
            if i == 1:
                prev_point = point1
            else:
                prev_point = interpolated[-1]
                
            distance = self._calculate_distance(interp_point, prev_point)
            time_diff = interp_point.timestamp - prev_point.timestamp
            interp_point.velocity = distance / time_diff if time_diff > 0 else 0.0
                
            interpolated.append(interp_point)
            
        return interpolated
    def _reassign_stroke_properties(self, points: List[ProcessedInkPoint]) -> None:
        """重新分配筆劃屬性 (ID和索引)"""
        for i, point in enumerate(points):
            point.stroke_id = self.current_stroke_id
            point.point_index = i
    
    def _smooth_detection_signal(self, signal_data: List[float], 
                                window_size: int = 5) -> List[float]:
        """平滑檢測信號以減少噪音"""
        if len(signal_data) < window_size:
            return signal_data
        
        # 使用移動平均
        smoothed = []
        half_window = window_size // 2
        
        for i in range(len(signal_data)):
            start_idx = max(0, i - half_window)
            end_idx = min(len(signal_data), i + half_window + 1)
            window_values = signal_data[start_idx:end_idx]
            smoothed.append(np.mean(window_values))
        
        return smoothed
    
    def _detect_anomalies(self, points: List[ProcessedInkPoint]) -> List[int]:
        """檢測異常點的索引"""
        anomaly_indices = []
        
        if len(points) < 5:
            return anomaly_indices
        
        # 檢測壓力異常
        pressures = [p.pressure for p in points]
        pressure_mean = np.mean(pressures)
        pressure_std = np.std(pressures)
        
        for i, pressure in enumerate(pressures):
            if abs(pressure - pressure_mean) > 3 * pressure_std:
                anomaly_indices.append(i)
        
        # 檢測位置跳躍異常
        for i in range(1, len(points)):
            distance = self._calculate_distance(points[i], points[i-1])
            time_diff = points[i].timestamp - points[i-1].timestamp
            
            if time_diff > 0:
                speed = distance / time_diff
                if speed > 10.0:  # 異常高速移動
                    anomaly_indices.append(i)
        
        return list(set(anomaly_indices))  # 去重
    
    def _calculate_stroke_quality_score(self, points: List[ProcessedInkPoint]) -> float:
        """計算筆劃品質分數 (0-1)"""
        if len(points) < 2:
            return 0.0
        
        score = 1.0
        
        # 檢查時間連續性
        time_gaps = []
        for i in range(1, len(points)):
            gap = points[i].timestamp - points[i-1].timestamp
            time_gaps.append(gap)
        
        avg_gap = np.mean(time_gaps)
        gap_variance = np.var(time_gaps)
        
        # 時間間隔過大或變化太大會降低分數
        if avg_gap > 0.05:  # 50ms
            score *= 0.8
        if gap_variance > 0.001:
            score *= 0.9
        
        # 檢查壓力穩定性
        pressures = [p.pressure for p in points]
        pressure_std = np.std(pressures)
        if pressure_std > 0.3:
            score *= 0.7
        
        # 檢查空間連續性
        distances = []
        for i in range(1, len(points)):
            dist = self._calculate_distance(points[i], points[i-1])
            distances.append(dist)
        
        if distances:
            max_distance = max(distances)
            if max_distance > 0.1:
                score *= 0.6
        
        # 檢查異常點比例
        anomalies = self._detect_anomalies(points)
        anomaly_ratio = len(anomalies) / len(points)
        if anomaly_ratio > 0.1:
            score *= (1.0 - anomaly_ratio)
        
        return max(0.0, min(1.0, score))
    
    def _adaptive_threshold_adjustment(self, recent_performance: Dict[str, float]) -> None:
        """根據最近的性能調整檢測閾值"""
        # 如果檢測到太多假陽性，提高閾值
        false_positive_rate = recent_performance.get('false_positive_rate', 0.0)
        if false_positive_rate > 0.2:
            self.pressure_threshold *= 1.1
            self.velocity_threshold *= 1.1
            self.logger.info("提高檢測閾值以減少假陽性")
        
        # 如果漏檢率太高，降低閾值
        false_negative_rate = recent_performance.get('false_negative_rate', 0.0)
        if false_negative_rate > 0.2:
            self.pressure_threshold *= 0.9
            self.velocity_threshold *= 0.9
            self.logger.info("降低檢測閾值以減少漏檢")
        
        # 確保閾值在合理範圍內
        self.pressure_threshold = max(0.01, min(0.8, self.pressure_threshold))
        self.velocity_threshold = max(0.001, min(1.0, self.velocity_threshold))
    
    def get_current_thresholds(self) -> Dict[str, float]:
        """獲取當前的檢測閾值"""
        return {
            'pressure_threshold': self.pressure_threshold,
            'velocity_threshold': self.velocity_threshold,
            'pause_duration_threshold': self.pause_duration_threshold,
            'min_stroke_length': self.min_stroke_length,
            **self.detection_thresholds
        }
    
    def update_thresholds(self, new_thresholds: Dict[str, float]) -> None:
        """更新檢測閾值"""
        for key, value in new_thresholds.items():
            if hasattr(self, key):
                setattr(self, key, value)
                self.logger.info(f"更新閾值 {key}: {value}")
            elif key in self.detection_thresholds:
                self.detection_thresholds[key] = value
                self.logger.info(f"更新檢測閾值 {key}: {value}")
            else:
                self.logger.warning(f"未知的閾值參數: {key}")
    
    def export_detection_log(self) -> Dict[str, Any]:
        """導出檢測日誌用於分析"""
        return {
            'statistics': self.get_detection_statistics(),
            'thresholds': self.get_current_thresholds(),
            'state_history': list(self.state_history),
            'pressure_history': list(self.pressure_history),
            'velocity_history': list(self.velocity_history),
            'current_stroke_id': self.current_stroke_id,
            'last_active_time': self.last_active_time
        }
