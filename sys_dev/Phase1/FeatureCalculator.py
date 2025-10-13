import math
import numpy as np
from typing import List, Dict, Tuple, Any, Optional
import logging
from scipy import signal, stats
from scipy.spatial import ConvexHull
from scipy.interpolate import interp1d
from collections import deque
import warnings
from Config import ProcessingConfig
from DigitalInkDataStructure import ProcessedInkPoint, StrokeStatistics

class FeatureCalculator:
    """特徵計算器 - 負責計算筆劃和點的各種特徵"""

    def __init__(self, config: ProcessingConfig):
        """
        初始化特徵計算器

        Args:
            config: 處理配置參數
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # 特徵計算參數
        self.feature_params = {
            'smoothness_window': 5,           # 平滑度計算窗口
            'complexity_threshold': 0.1,      # 複雜度閾值
            'tremor_freq_range': (4, 12),     # 顫抖頻率範圍 (Hz)
            'rhythm_window': 10,              # 節奏分析窗口
            'geometric_precision': 1e-6,      # 幾何計算精度
            'min_points_for_analysis': 3,     # 最少分析點數
            'outlier_threshold': 3.0,         # 異常值閾值 (標準差倍數)
        }

        # 緩存計算結果
        self._calculation_cache = {}
        self._cache_enabled = True

        # 統計計數器
        self.calculation_stats = {
            'total_calculations': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'failed_calculations': 0
        }

    def initialize(self) -> bool:
        """
        初始化特徵計算器
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            self.logger.info("正在初始化特徵計算器...")
            
            # 重置統計資訊
            self.calculation_stats = {
                'total_calculations': 0,
                'cache_hits': 0,
                'cache_misses': 0,
                'failed_calculations': 0
            }
            
            # 清空緩存
            self._calculation_cache.clear()
            
            # 驗證配置參數
            if not self._validate_feature_config():
                self.logger.error("特徵計算器配置無效")
                return False
            
            # 初始化特徵參數
            self._initialize_feature_parameters()
            
            self.logger.info("特徵計算器初始化成功")
            return True
            
        except Exception as e:
            self.logger.error(f"特徵計算器初始化失敗: {str(e)}")
            return False

    def _validate_feature_config(self) -> bool:
        """驗證特徵計算配置"""
        try:
            # 檢查必要的配置參數
            required_attrs = ['smoothing_window_size', 'max_point_distance']
            
            for attr in required_attrs:
                if not hasattr(self.config, attr):
                    self.logger.warning(f"缺少配置參數: {attr}，使用預設值")
            
            # 檢查特徵參數的合理性
            if self.feature_params['smoothness_window'] <= 0:
                self.feature_params['smoothness_window'] = 5
                self.logger.warning("平滑度窗口大小無效，使用預設值 5")
                
            if self.feature_params['min_points_for_analysis'] <= 0:
                self.feature_params['min_points_for_analysis'] = 3
                self.logger.warning("最小分析點數無效，使用預設值 3")
            
            return True
            
        except Exception as e:
            self.logger.error(f"配置驗證失敗: {str(e)}")
            return False

    def _initialize_feature_parameters(self) -> None:
        """初始化特徵參數"""
        try:
            # 基於配置更新特徵參數
            if hasattr(self.config, 'smoothing_window_size'):
                self.feature_params['smoothness_window'] = self.config.smoothing_window_size
            
            if hasattr(self.config, 'complexity_threshold'):
                self.feature_params['complexity_threshold'] = self.config.complexity_threshold
            
            self.logger.info(f"特徵參數已初始化: {self.feature_params}")
            
        except Exception as e:
            self.logger.error(f"初始化特徵參數失敗: {str(e)}")

    def shutdown(self) -> None:
        """關閉特徵計算器，清理資源"""
        try:
            self.logger.info("正在關閉特徵計算器...")
            
            # 清空緩存
            self._calculation_cache.clear()
            
            # 重置統計資訊
            self.calculation_stats = {
                'total_calculations': 0,
                'cache_hits': 0,
                'cache_misses': 0,
                'failed_calculations': 0
            }
            
            self.logger.info("特徵計算器已關閉")
            
        except Exception as e:
            self.logger.error(f"關閉特徵計算器失敗: {str(e)}")

    def calculate_features(self, stroke_points: List[ProcessedInkPoint]) -> Dict[str, Any]:
        """
        計算筆劃的所有特徵（兼容主控制器調用）
        
        Args:
            stroke_points: 筆劃的所有點
            
        Returns:
            Dict[str, Any]: 包含所有計算特徵的字典
        """
        try:
            if not stroke_points or len(stroke_points) < 2:
                return {}
            
            # 計算基本統計特徵
            statistics = self.calculate_stroke_statistics(stroke_points)
            
            # 計算壓力動態特徵
            pressure_dynamics = self.calculate_pressure_dynamics(stroke_points)
            
            # 計算節奏特徵
            rhythm_features = self.calculate_rhythm_features(stroke_points)
            
            # 計算幾何特徵
            geometric_features = self.extract_geometric_features(stroke_points)
            
            # 組合所有特徵
            all_features = {
                'basic_statistics': {
                    'point_count': statistics.point_count,
                    'total_length': statistics.total_length,
                    'duration': statistics.duration,
                    'width': statistics.width,
                    'height': statistics.height,
                    'average_pressure': statistics.average_pressure,
                    'max_pressure': statistics.max_pressure,
                    'average_velocity': statistics.average_velocity,
                    'max_velocity': statistics.max_velocity,
                    'smoothness': statistics.smoothness,
                    'complexity': statistics.complexity,
                    'tremor_index': statistics.tremor_index
                },
                'pressure_dynamics': pressure_dynamics,
                'rhythm_features': rhythm_features,
                'geometric_features': geometric_features
            }
            
            return all_features
            
        except Exception as e:
            self.logger.error(f"計算特徵失敗: {str(e)}")
            return {}

    def calculate_stroke_statistics(self, points: List[ProcessedInkPoint]) -> StrokeStatistics:
        """
        計算筆劃的統計特徵

        Args:
            points: 筆劃的所有點

        Returns:
            StrokeStatistics: 筆劃統計資訊

        Note:
            計算的統計量包括：
            - 總長度、持續時間
            - 平均/最大壓力和速度
            - 邊界框
            - 點數量等
        """
        try:
            if not points or len(points) < 2:
                return self._create_empty_statistics()

            self.calculation_stats['total_calculations'] += 1

            # 基本統計
            total_length = self.calculate_total_length(points)
            duration = points[-1].timestamp - points[0].timestamp
            point_count = len(points)

            # 邊界框
            min_x, min_y, max_x, max_y = self.calculate_bounding_box(points)
            width = max_x - min_x
            height = max_y - min_y

            # 壓力統計
            pressure_stats = self.calculate_pressure_statistics(points)

            # 速度統計
            velocity_stats = self.calculate_velocity_statistics(points)

            # 高級特徵
            smoothness = self.calculate_smoothness(points)
            complexity = self.calculate_complexity(points)
            tremor_index = self.calculate_tremor_index(points)

            # 創建統計對象
            statistics = StrokeStatistics(
                stroke_id=points[0].stroke_id if points else 0,
                point_count=point_count,
                total_length=total_length,
                duration=duration,
                bounding_box=(min_x, min_y, max_x, max_y),
                width=width,
                height=height,
                average_pressure=pressure_stats['mean'],
                max_pressure=pressure_stats['max'],
                min_pressure=pressure_stats['min'],
                pressure_std=pressure_stats['std'],
                average_velocity=velocity_stats['mean'],
                max_velocity=velocity_stats['max'],
                min_velocity=velocity_stats['min'],
                velocity_std=velocity_stats['std'],
                smoothness=smoothness,
                complexity=complexity,
                tremor_index=tremor_index,
                start_time=points[0].timestamp,
                end_time=points[-1].timestamp
            )

            return statistics

        except Exception as e:
            self.logger.error(f"計算筆劃統計失敗: {str(e)}")
            self.calculation_stats['failed_calculations'] += 1
            return self._create_empty_statistics()

    def calculate_total_length(self, points: List[ProcessedInkPoint]) -> float:
        """
        計算筆劃總長度

        Args:
            points: 筆劃點列表

        Returns:
            float: 總長度
        """
        try:
            if len(points) < 2:
                return 0.0

            total_length = 0.0
            for i in range(1, len(points)):
                dx = points[i].x - points[i-1].x
                dy = points[i].y - points[i-1].y
                distance = math.sqrt(dx * dx + dy * dy)
                total_length += distance

            return total_length

        except Exception as e:
            self.logger.error(f"計算總長度失敗: {str(e)}")
            return 0.0

    def calculate_bounding_box(self, points: List[ProcessedInkPoint]) -> Tuple[float, float, float, float]:
        """
        計算筆劃的邊界框

        Args:
            points: 筆劃點列表

        Returns:
            Tuple[float, float, float, float]: (min_x, min_y, max_x, max_y)
        """
        try:
            if not points:
                return (0.0, 0.0, 0.0, 0.0)

            x_coords = [p.x for p in points]
            y_coords = [p.y for p in points]

            min_x = min(x_coords)
            max_x = max(x_coords)
            min_y = min(y_coords)
            max_y = max(y_coords)

            return (min_x, min_y, max_x, max_y)

        except Exception as e:
            self.logger.error(f"計算邊界框失敗: {str(e)}")
            return (0.0, 0.0, 0.0, 0.0)

    def calculate_pressure_statistics(self, points: List[ProcessedInkPoint]) -> Dict[str, float]:
        """
        計算壓力相關統計

        Args:
            points: 筆劃點列表

        Returns:
            Dict[str, float]: 壓力統計，包含：
                - mean: 平均壓力
                - std: 壓力標準差
                - min: 最小壓力
                - max: 最大壓力
                - median: 中位數壓力
        """
        try:
            if not points:
                return self._create_empty_pressure_stats()

            pressures = [p.pressure for p in points]

            # 過濾異常值
            pressures = self._filter_outliers(pressures)

            if not pressures:
                return self._create_empty_pressure_stats()

            return {
                'mean': np.mean(pressures),
                'std': np.std(pressures),
                'min': np.min(pressures),
                'max': np.max(pressures),
                'median': np.median(pressures),
                'q25': np.percentile(pressures, 25),
                'q75': np.percentile(pressures, 75),
                'range': np.max(pressures) - np.min(pressures),
                'cv': np.std(pressures) / np.mean(pressures) if np.mean(pressures) > 0 else 0.0
            }

        except Exception as e:
            self.logger.error(f"計算壓力統計失敗: {str(e)}")
            return self._create_empty_pressure_stats()

    def calculate_velocity_statistics(self, points: List[ProcessedInkPoint]) -> Dict[str, float]:
        """
        計算速度相關統計

        Args:
            points: 筆劃點列表

        Returns:
            Dict[str, float]: 速度統計，包含：
                - mean: 平均速度
                - std: 速度標準差
                - min: 最小速度
                - max: 最大速度
                - median: 中位數速度
        """
        try:
            if not points:
                return self._create_empty_velocity_stats()

            velocities = [p.velocity for p in points]

            # 過濾異常值
            velocities = self._filter_outliers(velocities)

            if not velocities:
                return self._create_empty_velocity_stats()

            return {
                'mean': np.mean(velocities),
                'std': np.std(velocities),
                'min': np.min(velocities),
                'max': np.max(velocities),
                'median': np.median(velocities),
                'q25': np.percentile(velocities, 25),
                'q75': np.percentile(velocities, 75),
                'range': np.max(velocities) - np.min(velocities),
                'cv': np.std(velocities) / np.mean(velocities) if np.mean(velocities) > 0 else 0.0
            }

        except Exception as e:
            self.logger.error(f"計算速度統計失敗: {str(e)}")
            return self._create_empty_velocity_stats()

    def calculate_smoothness(self, points: List[ProcessedInkPoint]) -> float:
        """
        計算筆劃平滑度

        Args:
            points: 筆劃點列表

        Returns:
            float: 平滑度指標 (0-1, 1為最平滑)

        Note:
            基於加速度變化和方向變化計算平滑度
        """
        try:
            if len(points) < self.feature_params['min_points_for_analysis']:
                return 0.0

            # 計算加速度變化的平滑度
            accelerations = [p.acceleration for p in points if hasattr(p, 'acceleration')]
            if len(accelerations) < 3:
                # 如果沒有加速度數據，從速度計算
                accelerations = self._calculate_accelerations_from_velocity(points)

            if len(accelerations) < 2:
                return 0.0

            # 計算加速度變化率 (jerk)
            jerks = []
            for i in range(1, len(accelerations)):
                jerk = abs(accelerations[i] - accelerations[i-1])
                jerks.append(jerk)

            if not jerks:
                return 1.0

            # 計算方向變化的平滑度
            direction_changes = self._calculate_direction_changes(points)

            # 綜合平滑度分數
            jerk_smoothness = 1.0 / (1.0 + np.mean(jerks))
            direction_smoothness = 1.0 / (1.0 + np.mean(direction_changes)) if direction_changes else 1.0

            # 加權平均
            smoothness = 0.6 * jerk_smoothness + 0.4 * direction_smoothness

            return max(0.0, min(1.0, smoothness))

        except Exception as e:
            self.logger.error(f"計算平滑度失敗: {str(e)}")
            return 0.0

    def calculate_complexity(self, points: List[ProcessedInkPoint]) -> float:
        """
        計算筆劃複雜度

        Args:
            points: 筆劃點列表

        Returns:
            float: 複雜度指標

        Note:
            基於曲率變化、方向變化頻率等計算
        """
        try:
            if len(points) < self.feature_params['min_points_for_analysis']:
                return 0.0

            # 計算曲率變化
            curvatures = [p.curvature for p in points if hasattr(p, 'curvature')]
            if len(curvatures) < 3:
                curvatures = self._calculate_curvatures(points)

            # 計算方向變化
            direction_changes = self._calculate_direction_changes(points)

            # 計算長度與直線距離的比率 (tortuosity)
            total_length = self.calculate_total_length(points)
            straight_distance = math.sqrt(
                (points[-1].x - points[0].x) ** 2 +
                (points[-1].y - points[0].y) ** 2
            )

            tortuosity = total_length / straight_distance if straight_distance > 0 else 1.0

            # 計算轉向點數量
            turning_points = self._count_turning_points(points)
            turning_density = turning_points / len(points) if len(points) > 0 else 0.0

            # 綜合複雜度分數
            curvature_complexity = np.std(curvatures) if curvatures else 0.0
            direction_complexity = len(direction_changes) / len(points) if len(points) > 0 else 0.0

            complexity = (
                0.3 * curvature_complexity +
                0.3 * direction_complexity +
                0.2 * (tortuosity - 1.0) +
                0.2 * turning_density
            )

            return max(0.0, complexity)

        except Exception as e:
            self.logger.error(f"計算複雜度失敗: {str(e)}")
            return 0.0

    def calculate_tremor_index(self, points: List[ProcessedInkPoint]) -> float:
        """
        計算顫抖指數

        Args:
            points: 筆劃點列表

        Returns:
            float: 顫抖指數 (越高表示越不穩定)

        Note:
            基於高頻振動成分分析
        """
        try:
            if len(points) < 10:  # 需要足夠的點進行頻域分析
                return 0.0

            # 提取座標序列
            x_coords = [p.x for p in points]
            y_coords = [p.y for p in points]
            timestamps = [p.timestamp for p in points]

            # 計算採樣頻率
            time_diffs = np.diff(timestamps)
            avg_dt = np.mean(time_diffs)
            fs = 1.0 / avg_dt if avg_dt > 0 else 100.0  # 默認100Hz

            # 計算速度序列
            velocities = [p.velocity for p in points]

            # 對速度信號進行頻域分析
            if len(velocities) >= 8:  # FFT需要足夠的點
                # 去除直流分量
                velocities_detrended = signal.detrend(velocities)

                # 計算功率譜密度
                freqs, psd = signal.welch(velocities_detrended, fs=fs, nperseg=min(len(velocities)//2, 64))

                # 找到顫抖頻率範圍內的功率
                tremor_freq_min, tremor_freq_max = self.feature_params['tremor_freq_range']
                tremor_mask = (freqs >= tremor_freq_min) & (freqs <= tremor_freq_max)

                if np.any(tremor_mask):
                    tremor_power = np.sum(psd[tremor_mask])
                    total_power = np.sum(psd)
                    tremor_ratio = tremor_power / total_power if total_power > 0 else 0.0
                else:
                    tremor_ratio = 0.0
            else:
                tremor_ratio = 0.0

            # 計算位置變化的高頻成分
            x_high_freq = self._calculate_high_frequency_component(x_coords, fs)
            y_high_freq = self._calculate_high_frequency_component(y_coords, fs)

            # 綜合顫抖指數
            tremor_index = (
                0.5 * tremor_ratio +
                0.25 * x_high_freq +
                0.25 * y_high_freq
            )

            return max(0.0, min(1.0, tremor_index))

        except Exception as e:
            self.logger.error(f"計算顫抖指數失敗: {str(e)}")
            return 0.0

    def calculate_pressure_dynamics(self, points: List[ProcessedInkPoint]) -> Dict[str, float]:
        """
        計算壓力動態特徵

        Args:
            points: 筆劃點列表

        Returns:
            Dict[str, float]: 壓力動態特徵，包含：
                - pressure_buildup_time: 壓力建立時間
                - pressure_release_time: 壓力釋放時間
                - pressure_stability: 壓力穩定性
                - pressure_variation: 壓力變化度
        """
        try:
            if len(points) < 5:
                return self._create_empty_pressure_dynamics()

            pressures = [p.pressure for p in points]
            timestamps = [p.timestamp for p in points]

            # 計算壓力建立時間 (從開始到達到峰值的時間)
            max_pressure = max(pressures)
            max_pressure_idx = pressures.index(max_pressure)
            pressure_buildup_time = timestamps[max_pressure_idx] - timestamps[0]

            # 計算壓力釋放時間 (從峰值到結束的時間)
            pressure_release_time = timestamps[-1] - timestamps[max_pressure_idx]

            # 計算壓力穩定性 (峰值附近的變化程度)
            peak_region_start = max(0, max_pressure_idx - 2)
            peak_region_end = min(len(pressures), max_pressure_idx + 3)
            peak_pressures = pressures[peak_region_start:peak_region_end]
            pressure_stability = 1.0 - (np.std(peak_pressures) / np.mean(peak_pressures)) if np.mean(peak_pressures) > 0 else 0.0

            # 計算壓力變化度 (整體變化率)
            pressure_gradients = np.gradient(pressures)
            pressure_variation = np.std(pressure_gradients)

            # 計算壓力上升/下降速率
            pressure_rise_rate = self._calculate_pressure_rise_rate(pressures, timestamps)
            pressure_fall_rate = self._calculate_pressure_fall_rate(pressures, timestamps)

            return {
                'pressure_buildup_time': pressure_buildup_time,
                'pressure_release_time': pressure_release_time,
                'pressure_stability': max(0.0, min(1.0, pressure_stability)),
                'pressure_variation': pressure_variation,
                'pressure_rise_rate': pressure_rise_rate,
                'pressure_fall_rate': pressure_fall_rate,
                'max_pressure_position': max_pressure_idx / len(points),  # 歸一化位置
                'pressure_asymmetry': abs(pressure_buildup_time - pressure_release_time) / (pressure_buildup_time + pressure_release_time) if (pressure_buildup_time + pressure_release_time) > 0 else 0.0
            }

        except Exception as e:
            self.logger.error(f"計算壓力動態失敗: {str(e)}")
            return self._create_empty_pressure_dynamics()

    def calculate_rhythm_features(self, points: List[ProcessedInkPoint]) -> Dict[str, float]:
        """
        計算節奏特徵

        Args:
            points: 筆劃點列表

        Returns:
            Dict[str, float]: 節奏特徵，包含：
                - tempo: 節拍
                - rhythm_regularity: 節奏規律性
                - pause_frequency: 暫停頻率
                - acceleration_patterns: 加速模式
        """
        try:
            if len(points) < self.feature_params['rhythm_window']:
                return self._create_empty_rhythm_features()

            timestamps = [p.timestamp for p in points]
            velocities = [p.velocity for p in points]

            # 計算節拍 (基於速度變化的頻率)
            tempo = self._calculate_tempo(velocities, timestamps)

            # 計算節奏規律性 (時間間隔的一致性)
            time_intervals = np.diff(timestamps)
            rhythm_regularity = 1.0 - (np.std(time_intervals) / np.mean(time_intervals)) if np.mean(time_intervals) > 0 else 0.0
            rhythm_regularity = max(0.0, min(1.0, rhythm_regularity))

            # 計算暫停頻率
            pause_threshold = np.mean(velocities) * 0.1  # 10% 的平均速度作為暫停閾值
            pauses = [v for v in velocities if v < pause_threshold]
            pause_frequency = len(pauses) / len(velocities)

            # 計算加速模式
            accelerations = [p.acceleration for p in points if hasattr(p, 'acceleration')]
            if len(accelerations) < 3:
                accelerations = self._calculate_accelerations_from_velocity(points)

            acceleration_patterns = self._analyze_acceleration_patterns(accelerations)

            # 計算速度變化的週期性
            velocity_periodicity = self._calculate_periodicity(velocities)

            return {
                'tempo': tempo,
                'rhythm_regularity': rhythm_regularity,
                'pause_frequency': pause_frequency,
                'acceleration_patterns': acceleration_patterns,
                'velocity_periodicity': velocity_periodicity,
                'time_interval_cv': np.std(time_intervals) / np.mean(time_intervals) if np.mean(time_intervals) > 0 else 0.0
            }

        except Exception as e:
            self.logger.error(f"計算節奏特徵失敗: {str(e)}")
            return self._create_empty_rhythm_features()

    def extract_geometric_features(self, points: List[ProcessedInkPoint]) -> Dict[str, Any]:
        """
        提取幾何特徵

        Args:
            points: 筆劃點列表

        Returns:
            Dict[str, Any]: 幾何特徵，包含：
                - aspect_ratio: 長寬比
                - circularity: 圓度
                - rectangularity: 矩形度
                - convex_hull_ratio: 凸包比率
                - turning_angles: 轉向角度列表
        """
        try:
            if len(points) < 3:
                return self._create_empty_geometric_features()

            # 計算邊界框
            min_x, min_y, max_x, max_y = self.calculate_bounding_box(points)
            width = max_x - min_x
            height = max_y - min_y

            # 長寬比
            aspect_ratio = width / height if height > 0 else float('inf')

            # 計算面積和周長
            area = self._calculate_polygon_area(points)
            perimeter = self.calculate_total_length(points)

            # 圓度 (4π * 面積 / 周長²)
            circularity = (4 * math.pi * area) / (perimeter * perimeter) if perimeter > 0 else 0.0

            # 矩形度 (實際面積 / 邊界框面積)
            bounding_box_area = width * height
            rectangularity = area / bounding_box_area if bounding_box_area > 0 else 0.0

            # 凸包比率
            convex_hull_ratio = self._calculate_convex_hull_ratio(points)

            # 轉向角度
            turning_angles = self._calculate_turning_angles(points)

            # 中心性特徵
            centroid = self._calculate_centroid(points)

            # 對稱性特徵
            symmetry_features = self._calculate_symmetry_features(points, centroid)

            # 形狀描述符
            shape_descriptors = self._calculate_shape_descriptors(points)

            return {
                'aspect_ratio': aspect_ratio,
                'circularity': max(0.0, min(1.0, circularity)),
                'rectangularity': max(0.0, min(1.0, rectangularity)),
                'convex_hull_ratio': convex_hull_ratio,
                'turning_angles': turning_angles,
                'centroid': centroid,
                'area': area,
                'perimeter': perimeter,
                'bounding_box_area': bounding_box_area,
                'width': width,
                'height': height,
                **symmetry_features,
                **shape_descriptors
            }

        except Exception as e:
            self.logger.error(f"提取幾何特徵失敗: {str(e)}")
            return self._create_empty_geometric_features()

    # 私有輔助方法

    def _create_empty_statistics(self) -> StrokeStatistics:
        """創建空的統計對象"""
        return StrokeStatistics(
            stroke_id=0, point_count=0, total_length=0.0, duration=0.0,
            bounding_box=(0.0, 0.0, 0.0, 0.0), width=0.0, height=0.0,
            average_pressure=0.0, max_pressure=0.0, min_pressure=0.0, pressure_std=0.0,
            average_velocity=0.0, max_velocity=0.0, min_velocity=0.0, velocity_std=0.0,
            smoothness=0.0, complexity=0.0, tremor_index=0.0,
            start_time=0.0, end_time=0.0
        )

    def _create_empty_pressure_stats(self) -> Dict[str, float]:
        """創建空的壓力統計"""
        return {
            'mean': 0.0, 'std': 0.0, 'min': 0.0, 'max': 0.0, 'median': 0.0,
            'q25': 0.0, 'q75': 0.0, 'range': 0.0, 'cv': 0.0
        }

    def _create_empty_velocity_stats(self) -> Dict[str, float]:
        """創建空的速度統計"""
        return {
            'mean': 0.0, 'std': 0.0, 'min': 0.0, 'max': 0.0, 'median': 0.0,
            'q25': 0.0, 'q75': 0.0, 'range': 0.0, 'cv': 0.0
        }

    def _create_empty_pressure_dynamics(self) -> Dict[str, float]:
        """創建空的壓力動態特徵"""
        return {
            'pressure_buildup_time': 0.0, 'pressure_release_time': 0.0,
            'pressure_stability': 0.0, 'pressure_variation': 0.0,
            'pressure_rise_rate': 0.0, 'pressure_fall_rate': 0.0,
            'max_pressure_position': 0.0, 'pressure_asymmetry': 0.0
        }

    def _create_empty_rhythm_features(self) -> Dict[str, float]:
        """創建空的節奏特徵"""
        return {
            'tempo': 0.0, 'rhythm_regularity': 0.0, 'pause_frequency': 0.0,
            'acceleration_patterns': 0.0, 'velocity_periodicity': 0.0, 'time_interval_cv': 0.0
        }

    def _create_empty_geometric_features(self) -> Dict[str, Any]:
        """創建空的幾何特徵"""
        return {
            'aspect_ratio': 1.0, 'circularity': 0.0, 'rectangularity': 0.0,
            'convex_hull_ratio': 1.0, 'turning_angles': [],
            'centroid': (0.0, 0.0), 'area': 0.0, 'perimeter': 0.0,
            'bounding_box_area': 0.0, 'width': 0.0, 'height': 0.0
        }

    def _filter_outliers(self, data: List[float]) -> List[float]:
        """過濾異常值"""
        if len(data) < 3:
            return data

        data_array = np.array(data)
        mean_val = np.mean(data_array)
        std_val = np.std(data_array)
        # 過濾異常值
        threshold = self.feature_params['outlier_threshold']
        mask = np.abs(data_array - mean_val) <= threshold * std_val
        filtered_data = data_array[mask].tolist()

        return filtered_data if filtered_data else data

    def _calculate_accelerations_from_velocity(self, points: List[ProcessedInkPoint]) -> List[float]:
        """從速度計算加速度"""
        if len(points) < 3:
            return []

        velocities = [p.velocity for p in points]
        timestamps = [p.timestamp for p in points]

        accelerations = []
        for i in range(1, len(velocities)):
            dt = timestamps[i] - timestamps[i-1]
            if dt > 0:
                acc = (velocities[i] - velocities[i-1]) / dt
                accelerations.append(acc)
            else:
                accelerations.append(0.0)

        return accelerations

    def _calculate_direction_changes(self, points: List[ProcessedInkPoint]) -> List[float]:
        """計算方向變化"""
        if len(points) < 3:
            return []

        direction_changes = []
        for i in range(1, len(points) - 1):
            # 計算前後兩段的方向向量
            dx1 = points[i].x - points[i-1].x
            dy1 = points[i].y - points[i-1].y
            dx2 = points[i+1].x - points[i].x
            dy2 = points[i+1].y - points[i].y

            # 計算角度變化
            angle1 = math.atan2(dy1, dx1)
            angle2 = math.atan2(dy2, dx2)

            angle_diff = abs(angle2 - angle1)
            if angle_diff > math.pi:
                angle_diff = 2 * math.pi - angle_diff

            direction_changes.append(angle_diff)

        return direction_changes

    def _calculate_curvatures(self, points: List[ProcessedInkPoint]) -> List[float]:
        """計算曲率"""
        if len(points) < 3:
            return []

        curvatures = []
        for i in range(1, len(points) - 1):
            # 使用三點計算曲率
            p1, p2, p3 = points[i-1], points[i], points[i+1]

            # 計算向量
            v1x, v1y = p2.x - p1.x, p2.y - p1.y
            v2x, v2y = p3.x - p2.x, p3.y - p2.y

            # 計算叉積和點積
            cross_product = v1x * v2y - v1y * v2x
            dot_product = v1x * v2x + v1y * v2y

            # 計算長度
            len1 = math.sqrt(v1x * v1x + v1y * v1y)
            len2 = math.sqrt(v2x * v2x + v2y * v2y)

            if len1 > 0 and len2 > 0:
                # 曲率 = |叉積| / (長度1 * 長度2 * 長度3)
                len3 = math.sqrt((p3.x - p1.x)**2 + (p3.y - p1.y)**2)
                if len3 > 0:
                    curvature = abs(cross_product) / (len1 * len2 * len3)
                    curvatures.append(curvature)
                else:
                    curvatures.append(0.0)
            else:
                curvatures.append(0.0)

        return curvatures

    def _count_turning_points(self, points: List[ProcessedInkPoint]) -> int:
        """計算轉向點數量"""
        if len(points) < 5:
            return 0

        # 計算方向變化
        direction_changes = self._calculate_direction_changes(points)

        # 設定轉向閾值
        turning_threshold = math.pi / 6  # 30度

        # 計算轉向點
        turning_points = 0
        for change in direction_changes:
            if change > turning_threshold:
                turning_points += 1

        return turning_points

    def _calculate_high_frequency_component(self, signal_data: List[float], fs: float) -> float:
        """計算高頻成分"""
        try:
            if len(signal_data) < 8:
                return 0.0

            # 去趨勢
            detrended = signal.detrend(signal_data)

            # 計算功率譜
            freqs, psd = signal.welch(detrended, fs=fs, nperseg=min(len(signal_data)//2, 64))

            # 定義高頻範圍 (> 2Hz)
            high_freq_mask = freqs > 2.0

            if np.any(high_freq_mask):
                high_freq_power = np.sum(psd[high_freq_mask])
                total_power = np.sum(psd)
                return high_freq_power / total_power if total_power > 0 else 0.0
            else:
                return 0.0

        except Exception:
            return 0.0

    def _calculate_pressure_rise_rate(self, pressures: List[float], timestamps: List[float]) -> float:
        """計算壓力上升速率"""
        if len(pressures) < 2:
            return 0.0

        max_pressure = max(pressures)
        max_idx = pressures.index(max_pressure)

        if max_idx == 0:
            return 0.0

        # 計算到峰值的平均上升速率
        pressure_rise = max_pressure - pressures[0]
        time_rise = timestamps[max_idx] - timestamps[0]

        return pressure_rise / time_rise if time_rise > 0 else 0.0

    def _calculate_pressure_fall_rate(self, pressures: List[float], timestamps: List[float]) -> float:
        """計算壓力下降速率"""
        if len(pressures) < 2:
            return 0.0

        max_pressure = max(pressures)
        max_idx = pressures.index(max_pressure)

        if max_idx == len(pressures) - 1:
            return 0.0

        # 計算從峰值的平均下降速率
        pressure_fall = max_pressure - pressures[-1]
        time_fall = timestamps[-1] - timestamps[max_idx]

        return pressure_fall / time_fall if time_fall > 0 else 0.0

    def _calculate_tempo(self, velocities: List[float], timestamps: List[float]) -> float:
        """計算節拍"""
        try:
            if len(velocities) < 10:
                return 0.0

            # 計算速度變化的週期
            velocity_changes = np.diff(velocities)

            # 找到局部極值
            peaks, _ = signal.find_peaks(np.abs(velocity_changes))

            if len(peaks) < 2:
                return 0.0

            # 計算峰值間的時間間隔
            peak_intervals = []
            for i in range(1, len(peaks)):
                interval = timestamps[peaks[i]] - timestamps[peaks[i-1]]
                peak_intervals.append(interval)

            if not peak_intervals:
                return 0.0

            # 節拍 = 1 / 平均間隔
            avg_interval = np.mean(peak_intervals)
            tempo = 1.0 / avg_interval if avg_interval > 0 else 0.0

            return tempo

        except Exception:
            return 0.0

    def _analyze_acceleration_patterns(self, accelerations: List[float]) -> float:
        """分析加速模式"""
        if len(accelerations) < 5:
            return 0.0

        # 計算加速度變化的規律性
        acc_changes = np.diff(accelerations)

        # 計算自相關性
        try:
            correlation = np.correlate(acc_changes, acc_changes, mode='full')
            max_corr = np.max(correlation[len(correlation)//2+1:])
            normalized_corr = max_corr / correlation[len(correlation)//2]
            return min(1.0, normalized_corr)
        except Exception:
            return 0.0

    def _calculate_periodicity(self, signal_data: List[float]) -> float:
        """計算週期性"""
        try:
            if len(signal_data) < 10:
                return 0.0

            # 計算自相關函數
            signal_array = np.array(signal_data)
            signal_normalized = (signal_array - np.mean(signal_array)) / np.std(signal_array)

            autocorr = np.correlate(signal_normalized, signal_normalized, mode='full')
            autocorr = autocorr[len(autocorr)//2:]

            # 找到第一個顯著的峰值 (排除零延遲)
            if len(autocorr) > 1:
                peaks, _ = signal.find_peaks(autocorr[1:], height=0.3)
                if len(peaks) > 0:
                    return autocorr[peaks[0] + 1] / autocorr[0]

            return 0.0

        except Exception:
            return 0.0

    def _calculate_polygon_area(self, points: List[ProcessedInkPoint]) -> float:
        """計算多邊形面積 (使用鞋帶公式)"""
        if len(points) < 3:
            return 0.0

        area = 0.0
        n = len(points)

        for i in range(n):
            j = (i + 1) % n
            area += points[i].x * points[j].y
            area -= points[j].x * points[i].y

        return abs(area) / 2.0

    def _calculate_convex_hull_ratio(self, points: List[ProcessedInkPoint]) -> float:
        """計算凸包比率"""
        try:
            if len(points) < 4:
                return 1.0

            # 準備點座標
            coords = [(p.x, p.y) for p in points]
            coords_array = np.array(coords)

            # 計算凸包
            hull = ConvexHull(coords_array)

            # 計算原始路徑長度和凸包周長
            original_length = self.calculate_total_length(points)
            hull_perimeter = hull.area  # 在2D中，area屬性實際上是周長

            return hull_perimeter / original_length if original_length > 0 else 1.0

        except Exception:
            return 1.0

    def _calculate_turning_angles(self, points: List[ProcessedInkPoint]) -> List[float]:
        """計算轉向角度"""
        if len(points) < 3:
            return []

        turning_angles = []
        for i in range(1, len(points) - 1):
            # 計算三個連續點的角度
            p1, p2, p3 = points[i-1], points[i], points[i+1]

            # 向量
            v1 = (p2.x - p1.x, p2.y - p1.y)
            v2 = (p3.x - p2.x, p3.y - p2.y)

            # 計算角度
            dot_product = v1[0] * v2[0] + v1[1] * v2[1]
            cross_product = v1[0] * v2[1] - v1[1] * v2[0]

            angle = math.atan2(cross_product, dot_product)
            turning_angles.append(angle)

        return turning_angles

    def _calculate_centroid(self, points: List[ProcessedInkPoint]) -> Tuple[float, float]:
        """計算重心"""
        if not points:
            return (0.0, 0.0)

        x_sum = sum(p.x for p in points)
        y_sum = sum(p.y for p in points)
        n = len(points)

        return (x_sum / n, y_sum / n)

    def _calculate_symmetry_features(self, points: List[ProcessedInkPoint],
                                     centroid: Tuple[float, float]) -> Dict[str, float]:
        """計算對稱性特徵"""
        try:
            if len(points) < 4:
                return {'horizontal_symmetry': 0.0, 'vertical_symmetry': 0.0}

            cx, cy = centroid

            # 計算水平對稱性
            upper_points = [p for p in points if p.y > cy]
            lower_points = [p for p in points if p.y < cy]

            horizontal_symmetry = 0.0
            if upper_points and lower_points:
                # 簡化的對稱性計算
                upper_distances = [abs(p.y - cy) for p in upper_points]
                lower_distances = [abs(p.y - cy) for p in lower_points]

                if upper_distances and lower_distances:
                    upper_avg = np.mean(upper_distances)
                    lower_avg = np.mean(lower_distances)
                    horizontal_symmetry = 1.0 - abs(upper_avg - lower_avg) / max(upper_avg, lower_avg)

            # 計算垂直對稱性
            left_points = [p for p in points if p.x < cx]
            right_points = [p for p in points if p.x > cx]

            vertical_symmetry = 0.0
            if left_points and right_points:
                left_distances = [abs(p.x - cx) for p in left_points]
                right_distances = [abs(p.x - cx) for p in right_points]

                if left_distances and right_distances:
                    left_avg = np.mean(left_distances)
                    right_avg = np.mean(right_distances)
                    vertical_symmetry = 1.0 - abs(left_avg - right_avg) / max(left_avg, right_avg)

            return {
                'horizontal_symmetry': max(0.0, min(1.0, horizontal_symmetry)),
                'vertical_symmetry': max(0.0, min(1.0, vertical_symmetry))
            }

        except Exception:
            return {'horizontal_symmetry': 0.0, 'vertical_symmetry': 0.0}

    def _calculate_shape_descriptors(self, points: List[ProcessedInkPoint]) -> Dict[str, float]:
        """計算形狀描述符"""
        try:
            if len(points) < 4:
                return {'compactness': 0.0, 'elongation': 0.0, 'solidity': 0.0}

            # 計算緊密度 (4π * 面積 / 周長²)
            area = self._calculate_polygon_area(points)
            perimeter = self.calculate_total_length(points)
            compactness = (4 * math.pi * area) / (perimeter * perimeter) if perimeter > 0 else 0.0

            # 計算伸長度 (基於主軸分析)
            coords = np.array([(p.x, p.y) for p in points])
            cov_matrix = np.cov(coords.T)
            eigenvalues = np.linalg.eigvals(cov_matrix)
            eigenvalues = np.sort(eigenvalues)[::-1]  # 降序排列

            elongation = eigenvalues[0] / eigenvalues[1] if len(eigenvalues) > 1 and eigenvalues[1] > 0 else 1.0

            # 計算實心度 (面積 / 凸包面積)
            try:
                coords_array = np.array([(p.x, p.y) for p in points])
                hull = ConvexHull(coords_array)
                hull_area = hull.volume  # 在2D中，volume屬性是面積
                solidity = area / hull_area if hull_area > 0 else 0.0
            except Exception:
                solidity = 0.0

            return {
                'compactness': max(0.0, min(1.0, compactness)),
                'elongation': elongation,
                'solidity': max(0.0, min(1.0, solidity))
            }

        except Exception:
            return {'compactness': 0.0, 'elongation': 0.0, 'solidity': 0.0}

    def get_calculation_statistics(self) -> Dict[str, Any]:
        """獲取計算統計資訊"""
        total_calls = self.calculation_stats['total_calculations']
        cache_hit_rate = (self.calculation_stats['cache_hits'] / total_calls * 100) if total_calls > 0 else 0.0
        failure_rate = (self.calculation_stats['failed_calculations'] / total_calls * 100) if total_calls > 0 else 0.0

        return {
            'total_calculations': total_calls,
            'cache_hits': self.calculation_stats['cache_hits'],
            'cache_misses': self.calculation_stats['cache_misses'],
            'failed_calculations': self.calculation_stats['failed_calculations'],
            'cache_hit_rate': cache_hit_rate,
            'failure_rate': failure_rate,
            'cache_enabled': self._cache_enabled
        }

    def clear_cache(self) -> None:
        """清空計算緩存"""
        self._calculation_cache.clear()
        self.logger.info("特徵計算緩存已清空")

    def update_feature_params(self, new_params: Dict[str, Any]) -> None:
        """更新特徵計算參數"""
        for key, value in new_params.items():
            if key in self.feature_params:
                self.feature_params[key] = value
                self.logger.info(f"更新特徵參數 {key}: {value}")
            else:
                self.logger.warning(f"未知的特徵參數: {key}")
