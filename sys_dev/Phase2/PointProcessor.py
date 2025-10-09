import math
import numpy as np
from typing import List, Optional, Tuple, Dict, Any
from scipy import signal
from scipy.interpolate import interp1d
import logging
from collections import deque
from DigitalInkDataStructure import *
from Config import ProcessingConfig
class PointProcessor:
    """點處理器 - 負責處理和增強原始墨水點"""

    def __init__(self, config: ProcessingConfig):
        """
        初始化點處理器

        Args:
            config: 處理配置參數
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # 設備邊界 (預設值，可由設備資訊更新)
        self.device_bounds = (0, 0, 1000, 1000)  # (min_x, min_y, max_x, max_y)

        # 平滑濾波器設置
        self.smoothing_buffer = deque(maxlen=config.smoothing_window_size)

        # 品質評估參數
        self.quality_thresholds = {
            'max_distance_jump': config.max_point_distance,
            'max_velocity_jump': 10.0,  # 最大速度跳躍
            'max_pressure_jump': 0.5,   # 最大壓力跳躍
            'min_time_delta': 1e-6,     # 最小時間間隔
            'max_time_delta': 0.1       # 最大時間間隔
        }

        # 插值參數
        self.interpolation_method = 'cubic'  # 插值方法

        # 統計資訊
        self.processing_stats = {
            'total_processed': 0,
            'interpolated_points': 0,
            'smoothed_points': 0,
            'low_quality_points': 0
        }

    def initialize(self) -> bool:
        """
        初始化點處理器
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            self.logger.info("正在初始化點處理器...")
            
            # 重置統計資訊
            self.reset_statistics()
            
            # 清空平滑緩衝區
            self.smoothing_buffer.clear()
            
            # 驗證配置參數
            if not self._validate_config():
                self.logger.error("點處理器配置無效")
                return False
            
            # 設置預設設備邊界（如果沒有設置）
            if not hasattr(self, 'device_bounds') or self.device_bounds is None:
                self.device_bounds = (0, 0, 1000, 1000)
                self.logger.info(f"使用預設設備邊界: {self.device_bounds}")
            
            # 初始化品質評估參數
            self._initialize_quality_thresholds()
            
            self.logger.info("點處理器初始化成功")
            return True
            
        except Exception as e:
            self.logger.error(f"點處理器初始化失敗: {str(e)}")
            return False

    def _validate_config(self) -> bool:
        """驗證配置參數"""
        try:
            # 檢查必要的配置參數
            required_attrs = ['smoothing_window_size', 'max_point_distance', 'smoothing_enabled']
            
            for attr in required_attrs:
                if not hasattr(self.config, attr):
                    self.logger.error(f"缺少配置參數: {attr}")
                    return False
            
            # 檢查參數值的合理性
            if self.config.smoothing_window_size <= 0:
                self.logger.error("平滑窗口大小必須大於0")
                return False
                
            if self.config.max_point_distance <= 0:
                self.logger.error("最大點距離必須大於0")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"配置驗證失敗: {str(e)}")
            return False

    def _initialize_quality_thresholds(self) -> None:
        """初始化品質評估閾值"""
        try:
            # 基於配置更新品質閾值
            self.quality_thresholds.update({
                'max_distance_jump': self.config.max_point_distance,
                'max_velocity_jump': getattr(self.config, 'max_velocity_jump', 10.0),
                'max_pressure_jump': getattr(self.config, 'max_pressure_jump', 0.5),
                'min_time_delta': getattr(self.config, 'min_time_delta', 1e-6),
                'max_time_delta': getattr(self.config, 'max_time_delta', 0.1)
            })
            
            self.logger.info(f"品質閾值已設置: {self.quality_thresholds}")
            
        except Exception as e:
            self.logger.error(f"初始化品質閾值失敗: {str(e)}")

    def shutdown(self) -> None:
        """關閉點處理器，清理資源"""
        try:
            self.logger.info("正在關閉點處理器...")
            
            # 清空緩衝區
            self.smoothing_buffer.clear()
            
            # 重置統計資訊
            self.reset_statistics()
            
            self.logger.info("點處理器已關閉")
            
        except Exception as e:
            self.logger.error(f"關閉點處理器失敗: {str(e)}")

    # def process_point(self, raw_point: RawInkPoint) -> Optional[ProcessedInkPoint]:
    #     """
    #     處理單個原始墨水點（兼容主控制器調用）
        
    #     Args:
    #         raw_point: 原始墨水點
            
    #     Returns:
    #         Optional[ProcessedInkPoint]: 處理後的墨水點
    #     """
    #     try:
    #         # 使用空的前置點列表調用原有方法
    #         return self.process_raw_point(raw_point, previous_points=[])
            
    #     except Exception as e:
    #         self.logger.error(f"處理點失敗: {str(e)}")
    #         return None
    def process_point(self, raw_point: RawInkPoint) -> Optional[ProcessedInkPoint]:
        """
        處理單個原始墨水點（兼容主控制器調用）
        
        Args:
            raw_point: 原始墨水點
            
        Returns:
            Optional[ProcessedInkPoint]: 處理後的墨水點
        """
        try:
            # 🔍 添加調試輸出
            self.logger.info(f"🔍 處理點: x={raw_point.x:.1f}, y={raw_point.y:.1f}, "
                            f"pressure={raw_point.pressure:.3f}, "  # ← 移除逗號
                            f"tiltX={raw_point.tilt_x:.3f}, "      # ← 移除逗號
                            f"tiltY={raw_point.tilt_y:.3f}, "      # ← 移除逗號
                            f"閾值={getattr(self.config, 'pressure_threshold', 'N/A')}")

            
            # 🔍 檢查壓力閾值
            if hasattr(self.config, 'pressure_threshold'):
                if raw_point.pressure < self.config.pressure_threshold:
                    self.logger.info(f"❌ 點被壓力閾值過濾: {raw_point.pressure:.3f} < {self.config.pressure_threshold}")
                    return None
                else:
                    self.logger.info(f"✅ 點通過壓力檢查: {raw_point.pressure:.3f} >= {self.config.pressure_threshold}")
            
            # 使用空的前置點列表調用原有方法
            result = self.process_raw_point(raw_point, previous_points=[])
            
            if result:
                self.logger.info(f"✅ 點處理成功")
            else:
                self.logger.info(f"❌ 點處理失敗")
            
            return result
            
        except Exception as e:
            self.logger.error(f"處理點失敗: {str(e)}")
            import traceback
            self.logger.error(f"詳細錯誤: {traceback.format_exc()}")
            return None
    def process_raw_point(self, raw_point: RawInkPoint,
                         previous_points: List[ProcessedInkPoint] = None) -> ProcessedInkPoint:
        """
        處理單個原始墨水點

        Args:
            raw_point: 原始墨水點
            previous_points: 前面的處理點列表 (用於計算衍生特徵)

        Returns:
            ProcessedInkPoint: 處理後的墨水點

        Note:
            - 座標正規化到 [0, 1] 範圍
            - 計算速度、加速度、方向等衍生特徵
            - 應用平滑濾波 (如果啟用)
        """
        try:
            # 1. 座標正規化
            norm_x, norm_y = self.normalize_coordinates(
                raw_point.x, raw_point.y, self.device_bounds
            )

            # 2. 創建基礎處理點
            processed_point = ProcessedInkPoint(
                x=norm_x,
                y=norm_y,
                pressure=max(0.0, min(1.0, raw_point.pressure)),  # 確保在 [0,1] 範圍
                tilt_x=raw_point.tilt_x,
                tilt_y=raw_point.tilt_y,
                twist=raw_point.twist,
                timestamp=raw_point.timestamp,

                # 初始化計算屬性
                velocity=0.0,
                acceleration=0.0,
                direction=0.0,
                curvature=0.0,

                # 初始化上下文屬性
                stroke_id=-1,  # 將由 StrokeDetector 設置
                point_index=-1,
                distance_from_start=0.0,

                # 初始化品質指標
                confidence=1.0,
                is_interpolated=False
            )

            # 3. 計算衍生特徵 (如果有前面的點)
            if previous_points and len(previous_points) > 0:
                processed_point = self._calculate_derived_features(
                    processed_point, previous_points
                )

            # 4. 評估點品質
            processed_point.confidence = self.validate_point_quality(
                processed_point, previous_points
            )

            # 5. 應用平滑濾波 (如果啟用)
            if self.config.smoothing_enabled and previous_points:
                processed_point = self._apply_point_smoothing(
                    processed_point, previous_points
                )

            # 6. 更新統計資訊
            self.processing_stats['total_processed'] += 1
            if processed_point.confidence < 0.5:
                self.processing_stats['low_quality_points'] += 1

            return processed_point

        except Exception as e:
            self.logger.error(f"處理原始點失敗: {str(e)}")
            # 返回基本的處理點作為備用
            return self._create_fallback_point(raw_point)

    def normalize_coordinates(self, x: float, y: float,
                            device_bounds: Tuple[float, float, float, float]) -> Tuple[float, float]:
        """
        正規化座標到標準範圍

        Args:
            x: 原始X座標
            y: 原始Y座標
            device_bounds: 設備邊界 (min_x, min_y, max_x, max_y)

        Returns:
            Tuple[float, float]: 正規化後的 (x, y) 座標
        """
        min_x, min_y, max_x, max_y = device_bounds

        # 避免除零錯誤
        width = max_x - min_x
        height = max_y - min_y

        if width <= 0 or height <= 0:
            self.logger.warning("設備邊界無效，使用預設正規化")
            return (0.5, 0.5)

        # 正規化到 [0, 1] 範圍
        norm_x = max(0.0, min(1.0, (x - min_x) / width))
        norm_y = max(0.0, min(1.0, (y - min_y) / height))

        return (norm_x, norm_y)

    def calculate_velocity(self, current_point: ProcessedInkPoint,
                          previous_point: ProcessedInkPoint) -> float:
        """
        計算兩點間的速度

        Args:
            current_point: 當前點
            previous_point: 前一個點

        Returns:
            float: 速度值 (單位/秒)
        """
        try:
            # 計算時間差
            time_delta = current_point.timestamp - previous_point.timestamp
            if time_delta <= 0:
                return 0.0

            # 計算空間距離
            dx = current_point.x - previous_point.x
            dy = current_point.y - previous_point.y
            distance = math.sqrt(dx * dx + dy * dy)

            # 計算速度
            velocity = distance / time_delta

            return velocity

        except Exception as e:
            self.logger.error(f"計算速度失敗: {str(e)}")
            return 0.0

    def calculate_acceleration(self, current_velocity: float,
                             previous_velocity: float,
                             time_delta: float) -> float:
        """
        計算加速度

        Args:
            current_velocity: 當前速度
            previous_velocity: 前一個速度
            time_delta: 時間差

        Returns:
            float: 加速度值 (單位/秒²)
        """
        try:
            if time_delta <= 0:
                return 0.0

            velocity_change = current_velocity - previous_velocity
            acceleration = velocity_change / time_delta

            return acceleration

        except Exception as e:
            self.logger.error(f"計算加速度失敗: {str(e)}")
            return 0.0

    def calculate_direction(self, current_point: ProcessedInkPoint,
                           previous_point: ProcessedInkPoint) -> float:
        """
        計算移動方向角度

        Args:
            current_point: 當前點
            previous_point: 前一個點

        Returns:
            float: 方向角度 (弧度, 0-2π)
        """
        try:
            dx = current_point.x - previous_point.x
            dy = current_point.y - previous_point.y

            # 使用 atan2 計算角度
            angle = math.atan2(dy, dx)

            # 轉換到 [0, 2π] 範圍
            if angle < 0:
                angle += 2 * math.pi

            return angle

        except Exception as e:
            self.logger.error(f"計算方向失敗: {str(e)}")
            return 0.0

    def calculate_curvature(self, points: List[ProcessedInkPoint],
                           center_index: int) -> float:
        """
        計算指定點的曲率

        Args:
            points: 點列表
            center_index: 中心點索引

        Returns:
            float: 曲率值

        Note:
            使用三點法計算曲率，需要center_index前後至少各有一個點
        """
        try:
            if (center_index <= 0 or center_index >= len(points) - 1 or
                len(points) < 3):
                return 0.0

            # 取三個點
            p1 = points[center_index - 1]
            p2 = points[center_index]
            p3 = points[center_index + 1]

            # 計算向量
            v1x, v1y = p2.x - p1.x, p2.y - p1.y
            v2x, v2y = p3.x - p2.x, p3.y - p2.y

            # 計算向量長度
            len1 = math.sqrt(v1x * v1x + v1y * v1y)
            len2 = math.sqrt(v2x * v2x + v2y * v2y)

            if len1 == 0 or len2 == 0:
                return 0.0

            # 計算角度變化
            dot_product = v1x * v2x + v1y * v2y
            cross_product = v1x * v2y - v1y * v2x

            # 計算曲率 (使用角度變化除以弧長)
            angle_change = math.atan2(cross_product, dot_product)
            arc_length = (len1 + len2) / 2.0

            if arc_length == 0:
                return 0.0

            curvature = abs(angle_change) / arc_length

            return curvature

        except Exception as e:
            self.logger.error(f"計算曲率失敗: {str(e)}")
            return 0.0

    def apply_smoothing(self, points: List[ProcessedInkPoint],
                       window_size: int = 5) -> List[ProcessedInkPoint]:
        """
        對點序列應用平滑濾波

        Args:
            points: 原始點列表
            window_size: 平滑窗口大小

        Returns:
            List[ProcessedInkPoint]: 平滑後的點列表

        Note:
            使用移動平均或高斯濾波進行平滑處理
        """
        try:
            if len(points) < window_size:
                return points.copy()

            smoothed_points = []
            half_window = window_size // 2

            for i in range(len(points)):
                # 確定窗口範圍
                start_idx = max(0, i - half_window)
                end_idx = min(len(points), i + half_window + 1)
                window_points = points[start_idx:end_idx]

                # 計算加權平均 (高斯權重)
                smoothed_point = self._gaussian_smooth_point(window_points, i - start_idx)
                smoothed_points.append(smoothed_point)

            self.processing_stats['smoothed_points'] += len(smoothed_points)
            return smoothed_points

        except Exception as e:
            self.logger.error(f"平滑濾波失敗: {str(e)}")
            return points.copy()

    def interpolate_points(self, point1: ProcessedInkPoint,
                          point2: ProcessedInkPoint,
                          target_interval: float) -> List[ProcessedInkPoint]:
        """
        在兩點間插值生成中間點

        Args:
            point1: 起始點
            point2: 結束點
            target_interval: 目標時間間隔

        Returns:
            List[ProcessedInkPoint]: 插值點列表 (不包含起始和結束點)
        """
        try:
            time_diff = point2.timestamp - point1.timestamp
            if time_diff <= target_interval:
                return []  # 不需要插值

            # 計算需要插值的點數
            num_interpolated = int(time_diff / target_interval) - 1
            if num_interpolated <= 0:
                return []

            interpolated_points = []

            for i in range(1, num_interpolated + 1):
                # 計算插值比例
                ratio = i / (num_interpolated + 1)

                # 線性插值各個屬性
                interpolated_point = ProcessedInkPoint(
                    x=point1.x + (point2.x - point1.x) * ratio,
                    y=point1.y + (point2.y - point1.y) * ratio,
                    pressure=point1.pressure + (point2.pressure - point1.pressure) * ratio,
                    tilt_x=point1.tilt_x + (point2.tilt_x - point1.tilt_x) * ratio,
                    tilt_y=point1.tilt_y + (point2.tilt_y - point1.tilt_y) * ratio,
                    twist=self._interpolate_angle(point1.twist, point2.twist, ratio),
                    timestamp=point1.timestamp + time_diff * ratio,

                    # 插值計算屬性
                    velocity=(point1.velocity + point2.velocity) / 2,
                    acceleration=0.0,  # 插值點的加速度設為0
                    direction=self._interpolate_angle(point1.direction, point2.direction, ratio),
                    curvature=(point1.curvature + point2.curvature) / 2,

                    # 設置上下文屬性
                    stroke_id=point1.stroke_id,
                    point_index=-1,  # 將由調用者設置
                    distance_from_start=point1.distance_from_start +
                                       self._calculate_distance(point1, point2) * ratio,

                    # 標記為插值點
                    confidence=min(point1.confidence, point2.confidence) * 0.9,  # 略微降低信心度
                    is_interpolated=True
                )

                interpolated_points.append(interpolated_point)

            self.processing_stats['interpolated_points'] += len(interpolated_points)
            return interpolated_points

        except Exception as e:
            self.logger.error(f"插值失敗: {str(e)}")
            return []

    def validate_point_quality(self, point: ProcessedInkPoint,
                              previous_points: List[ProcessedInkPoint] = None) -> float:
        """
        評估點的品質信心度

        Args:
            point: 待評估的點
            previous_points: 前面的點列表

        Returns:
            float: 品質信心度 (0.0-1.0)

        Note:
            基於以下因素評估品質：
            - 與前點的距離合理性
            - 速度變化的連續性
            - 壓力值的合理性
            - 時間戳的連續性
        """
        try:
            quality_score = 1.0

            # 基本數值檢查
            if not (0.0 <= point.x <= 1.0 and 0.0 <= point.y <= 1.0):
                quality_score *= 0.5  # 座標超出範圍

            if not (0.0 <= point.pressure <= 1.0):
                quality_score *= 0.5  # 壓力值異常

            if point.timestamp <= 0:
                quality_score *= 0.3  # 時間戳異常

            # 如果有前面的點，進行連續性檢查
            if previous_points and len(previous_points) > 0:
                last_point = previous_points[-1]

                # 1. 距離檢查
                distance = self._calculate_distance(point, last_point)
                if distance > self.quality_thresholds['max_distance_jump']:
                    quality_score *= 0.6  # 距離跳躍過大

                # 2. 時間連續性檢查
                time_delta = point.timestamp - last_point.timestamp
                if time_delta <= 0:
                    quality_score *= 0.2  # 時間倒退
                elif time_delta > self.quality_thresholds['max_time_delta']:
                    quality_score *= 0.7  # 時間間隔過大

                # 3. 速度變化檢查
                if len(previous_points) >= 2:
                    prev_velocity = previous_points[-1].velocity
                    velocity_change = abs(point.velocity - prev_velocity)
                    if velocity_change > self.quality_thresholds['max_velocity_jump']:
                        quality_score *= 0.8  # 速度變化過大

                # 4. 壓力變化檢查
                pressure_change = abs(point.pressure - last_point.pressure)
                if pressure_change > self.quality_thresholds['max_pressure_jump']:
                    quality_score *= 0.9  # 壓力變化較大

            return max(0.0, min(1.0, quality_score))

        except Exception as e:
            self.logger.error(f"品質驗證失敗: {str(e)}")
            return 0.5  # 返回中等品質作為備用

    def update_device_bounds(self, bounds: Tuple[float, float, float, float]) -> None:
        """更新設備邊界"""
        self.device_bounds = bounds

    def get_processing_statistics(self) -> Dict[str, Any]:
        """獲取處理統計資訊"""
        return self.processing_stats.copy()

    def reset_statistics(self) -> None:
        """重置統計資訊"""
        self.processing_stats = {
            'total_processed': 0,
            'interpolated_points': 0,
            'smoothed_points': 0,
            'low_quality_points': 0
        }

    # 私有輔助方法

    def _calculate_derived_features(self, point: ProcessedInkPoint,
                                   previous_points: List[ProcessedInkPoint]) -> ProcessedInkPoint:
        """計算衍生特徵"""
        if len(previous_points) == 0:
            return point

        last_point = previous_points[-1]

        # 計算速度
        point.velocity = self.calculate_velocity(point, last_point)

        # 計算方向
        point.direction = self.calculate_direction(point, last_point)

        # 計算加速度 (需要至少兩個前面的點)
        if len(previous_points) >= 2:
            prev_velocity = previous_points[-1].velocity
            time_delta = point.timestamp - last_point.timestamp
            point.acceleration = self.calculate_acceleration(
                point.velocity, prev_velocity, time_delta
            )

        # 計算曲率 (需要構建臨時點列表)
        if len(previous_points) >= 2:
            temp_points = previous_points[-2:] + [point]
            point.curvature = self.calculate_curvature(temp_points, 2)

        # 計算累積距離
        point.distance_from_start = (
            last_point.distance_from_start +
            self._calculate_distance(point, last_point)
        )

        return point

    def _apply_point_smoothing(self, point: ProcessedInkPoint,
                              previous_points: List[ProcessedInkPoint]) -> ProcessedInkPoint:
        """對單個點應用平滑"""
        # 簡化的單點平滑實現
        if len(previous_points) < 2:
            return point

        # 使用最近幾個點的加權平均
        window_size = min(3, len(previous_points))
        recent_points = previous_points[-window_size:]

        # 計算平滑後的座標
        total_weight = 1.0
        smooth_x = point.x
        smooth_y = point.y

        for i, prev_point in enumerate(reversed(recent_points)):
            weight = 0.5 ** (i + 1)  # 指數衰減權重
            smooth_x += prev_point.x * weight
            smooth_y += prev_point.y * weight
            total_weight += weight

        point.x = smooth_x / total_weight
        point.y = smooth_y / total_weight

        return point

    def _gaussian_smooth_point(self, window_points: List[ProcessedInkPoint],
                              center_idx: int) -> ProcessedInkPoint:
        """使用高斯權重平滑點"""
        if center_idx >= len(window_points):
            return window_points[-1]

        center_point = window_points[center_idx]

        # 生成高斯權重
        sigma = len(window_points) / 4.0
        weights = []
        for i in range(len(window_points)):
            distance = abs(i - center_idx)
            weight = math.exp(-(distance ** 2) / (2 * sigma ** 2))
            weights.append(weight)

        # 正規化權重
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]

        # 計算加權平均
        smooth_x = sum(p.x * w for p, w in zip(window_points, weights))
        smooth_y = sum(p.y * w for p, w in zip(window_points, weights))
        smooth_pressure = sum(p.pressure * w for p, w in zip(window_points, weights))

        # 創建平滑後的點
        smoothed_point = ProcessedInkPoint(
            x=smooth_x,
            y=smooth_y,
            pressure=smooth_pressure,
            tilt_x=center_point.tilt_x,
            tilt_y=center_point.tilt_y,
            twist=center_point.twist,
            timestamp=center_point.timestamp,
            velocity=center_point.velocity,
            acceleration=center_point.acceleration,
            direction=center_point.direction,
            curvature=center_point.curvature,
            stroke_id=center_point.stroke_id,
            point_index=center_point.point_index,
            distance_from_start=center_point.distance_from_start,
            confidence=center_point.confidence,
            is_interpolated=center_point.is_interpolated
        )

        return smoothed_point

    def _interpolate_angle(self, angle1: float, angle2: float, ratio: float) -> float:
        """插值角度 (處理角度的周期性)"""
        # 確保角度在 [0, 2π] 範圍內
        angle1 = angle1 % (2 * math.pi)
        angle2 = angle2 % (2 * math.pi)

        # 計算角度差
        diff = angle2 - angle1

        # 處理跨越0點的情況
        if diff > math.pi:
            diff -= 2 * math.pi
        elif diff < -math.pi:
            diff += 2 * math.pi

        # 線性插值
        result = angle1 + diff * ratio

        # 確保結果在 [0, 2π] 範圍內
        return result % (2 * math.pi)

    def _calculate_distance(self, point1: ProcessedInkPoint,
                           point2: ProcessedInkPoint) -> float:
        """計算兩點間的歐氏距離"""
        dx = point1.x - point2.x
        dy = point1.y - point2.y
        return math.sqrt(dx * dx + dy * dy)

    def _create_fallback_point(self, raw_point: RawInkPoint) -> ProcessedInkPoint:
        """創建備用處理點"""
        norm_x, norm_y = self.normalize_coordinates(
            raw_point.x, raw_point.y, self.device_bounds
        )

        return ProcessedInkPoint(
            x=norm_x,
            y=norm_y,
            pressure=max(0.0, min(1.0, raw_point.pressure)),
            tilt_x=raw_point.tilt_x,
            tilt_y=raw_point.tilt_y,
            twist=raw_point.twist,
            timestamp=raw_point.timestamp,
            velocity=0.0,
            acceleration=0.0,
            direction=0.0,
            curvature=0.0,
            stroke_id=-1,
            point_index=-1,
            distance_from_start=0.0,
            confidence=0.5,  # 低信心度
            is_interpolated=False
        )