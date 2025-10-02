"""
Config.py - 數位墨水處理系統配置模組
將 ProcessingConfig 從 MainController 中分離，解決循環導入問題
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum

class DeviceType(Enum):
  """設備類型枚舉"""
  WACOM = "wacom"
  TOUCH = "touch"
  MOUSE = "mouse"
  SIMULATOR = "simulator"

@dataclass
class ProcessingConfig:
    """系統處理配置"""
    
    # 設備配置
    device_type: str = "wacom"
    target_sampling_rate: int = 200

    # 處理參數
    smoothing_enabled: bool = True
    smoothing_window_size: int = 5
    noise_threshold: float = 0.1

    # 筆劃檢測參數
    stroke_timeout: float = 0.5
    min_stroke_points: int = 3
    pressure_threshold: float = 0.05
    pause_duration_threshold: float = 500.0    # 暫停持續時間閾值 (毫秒)
    
    # 特徵計算參數
    feature_types: List[str] = None
    
    # ==================== PointProcessor 所需的參數 ====================
    max_point_distance: float = 50.0        # 最大點間距離
    max_velocity_jump: float = 1000.0       # 最大速度跳躍
    max_pressure_jump: float = 0.5          # 最大壓力跳躍
    min_time_delta: float = 1e-6            # 最小時間間隔
    max_time_delta: float = 0.1             # 最大時間間隔
    
    # 插值參數
    interpolation_method: str = "cubic"     # 插值方法 ('linear', 'cubic', 'quadratic')
    enable_interpolation: bool = True       # 是否啟用插值
    max_interpolation_points: int = 10      # 最大插值點數
    
    # 品質控制參數
    enable_quality_check: bool = True       # 是否啟用品質檢查
    quality_score_threshold: float = 0.5    # 品質分數閾值
    
    # ==================== StrokeDetector 所需的參數 ====================
    velocity_threshold: float = 10.0        # 速度閾值 (px/ms)
    min_velocity: float = 0.1               # 最小速度
    max_velocity: float = 2000.0            # 最大速度
    velocity_smoothing_window: int = 3      # 速度平滑視窗大小
    
    # 加速度相關參數
    acceleration_threshold: float = 100.0   # 加速度閾值 (px/ms²)
    max_acceleration: float = 5000.0        # 最大加速度
    
    # 筆劃分割參數
    stroke_gap_threshold: float = 100.0     # 筆劃間隔閾值 (ms)
    min_stroke_duration: float = 10.0      # 最小筆劃持續時間 (ms)
    max_stroke_duration: float = 10000.0   # 最大筆劃持續時間 (ms)
    min_stroke_length: float = 5.0         # 最小筆劃長度 (px)
    max_stroke_length: float = 10000.0     # 最大筆劃長度 (px)
    stroke_smoothness_threshold: float = 0.8  # 筆劃平滑度閾值
    curvature_threshold: float = 0.1        # 曲率閾值
    direction_change_threshold: float = 45.0 # 方向變化閾值 (度)
    stroke_detection_method: str = "velocity_based"  # 檢測方法
    enable_stroke_merging: bool = True      # 是否啟用筆劃合併
    stroke_merge_distance: float = 20.0    # 筆劃合併距離閾值
    stroke_merge_time: float = 200.0       # 筆劃合併時間閾值 (ms)
    
    # ==================== 新增：RawDataCollector 所需的參數 ====================
    # 數據收集配置
    data_collection_rate: int = 1000        # 數據收集頻率 (Hz)
    enable_data_validation: bool = True     # 是否啟用數據驗證
    data_format: str = "standard"           # 數據格式 ('standard', 'extended', 'minimal')
    
    # 設備連接配置
    device_connection_timeout: float = 5.0  # 設備連接超時 (秒)
    device_retry_attempts: int = 3          # 設備重試次數
    device_retry_delay: float = 1.0        # 重試延遲 (秒)
    
    # 數據緩衝配置
    raw_data_buffer_size: int = 50000      # 原始數據緩衝區大小
    data_queue_timeout: float = 0.1        # 數據隊列超時 (秒)
    enable_data_compression: bool = False   # 是否啟用數據壓縮
    
    # 校準配置
    enable_auto_calibration: bool = True    # 是否啟用自動校準
    calibration_points: int = 9            # 校準點數量
    calibration_timeout: float = 30.0      # 校準超時 (秒)
    
    # 模擬器特定配置
    simulator_noise_level: float = 0.05    # 模擬器噪聲級別
    simulator_latency: float = 1.0         # 模擬器延遲 (ms)
    simulator_jitter: float = 0.5          # 模擬器抖動 (ms)
    enable_simulator_pressure: bool = False # 模擬器是否支援壓力
    enable_simulator_tilt: bool = False    # 模擬器是否支援傾斜
    
    # 設備特定配置
    wacom_driver_path: str = ""            # Wacom 驅動路徑
    wacom_tablet_id: str = ""              # Wacom 平板 ID
    touch_multitouch_enabled: bool = True  # 觸控多點支援
    touch_gesture_enabled: bool = False    # 觸控手勢支援
    mouse_acceleration: bool = False       # 滑鼠加速
    mouse_sensitivity: float = 1.0         # 滑鼠靈敏度
    
    # 數據品質控制
    enable_outlier_detection: bool = True   # 是否啟用異常值檢測
    outlier_threshold: float = 3.0         # 異常值閾值 (標準差倍數)
    enable_data_smoothing: bool = True     # 是否啟用數據平滑
    data_smoothing_window: int = 3         # 數據平滑視窗大小
    
    # 座標系統參數
    coordinate_system: str = "screen"       # 座標系統 ('screen', 'normalized', 'device')
    device_width: float = 1920.0           # 設備寬度
    device_height: float = 1080.0          # 設備高度
    
    # 壓力處理參數
    pressure_normalization: bool = True     # 是否標準化壓力值
    min_pressure: float = 0.0              # 最小壓力值
    max_pressure: float = 1.0              # 最大壓力值
    
    # 傾斜角處理參數 (針對 Wacom 等支援傾斜的設備)
    enable_tilt_processing: bool = False    # 是否處理傾斜角
    max_tilt_angle: float = 90.0           # 最大傾斜角度
    
    # 緩衝區配置
    point_buffer_size: int = 10000         # 點緩衝區大小
    stroke_buffer_size: int = 1000         # 筆劃緩衝區大小
    event_buffer_size: int = 100           # 事件緩衝區大小
    
    # 性能配置
    processing_threads: int = 2            # 處理執行緒數
    enable_statistics: bool = True         # 是否啟用統計
    
    # 調試配置
    debug_mode: bool = False               # 調試模式
    log_level: str = "INFO"               # 日誌級別
    save_debug_data: bool = False         # 是否保存調試數據

    def __post_init__(self):
        """初始化後處理"""
        if self.feature_types is None:
            self.feature_types = ['basic', 'kinematic', 'pressure', 'geometric']
        
        # 根據設備類型調整預設參數
        self._adjust_device_specific_settings()
    
    # 在 Config.py 的 _adjust_device_specific_settings 方法中修正：

    def _adjust_device_specific_settings(self):
        """根據設備類型調整特定設置"""
        if self.device_type == "wacom":
            # Wacom 設備通常有更高的精度和壓力支援
            self.max_point_distance = 30.0
            self.pressure_threshold = 0.02          # ✅ 適合 Wacom 的低閾值
            self.velocity_threshold = 5.0
            self.pause_duration_threshold = 300.0
            self.enable_tilt_processing = True
            self.target_sampling_rate = 200
            self.data_collection_rate = 200
            self.enable_simulator_pressure = True
            self.enable_simulator_tilt = True
            self.simulator_noise_level = 0.02
            
        elif self.device_type == "touch":
            # 觸控設備通常沒有壓力，但有多點觸控
            self.max_point_distance = 50.0
            self.pressure_threshold = 0.01         # ✅ 修正：改為小正值而非 0.0
            self.velocity_threshold = 15.0
            self.pause_duration_threshold = 600.0
            self.enable_tilt_processing = False
            self.target_sampling_rate = 100
            self.data_collection_rate = 100
            self.touch_multitouch_enabled = True
            self.enable_simulator_pressure = False
            self.simulator_noise_level = 0.08
            
        elif self.device_type == "mouse":
            # 滑鼠設備沒有壓力和傾斜
            self.max_point_distance = 100.0
            self.pressure_threshold = 0.01         # ✅ 修正：改為小正值而非 0.0
            self.velocity_threshold = 20.0
            self.pause_duration_threshold = 800.0
            self.enable_tilt_processing = False
            self.target_sampling_rate = 100
            self.data_collection_rate = 100
            self.mouse_acceleration = False
            self.enable_simulator_pressure = False
            self.simulator_noise_level = 0.1
            
        elif self.device_type == "simulator":
            # 模擬器使用中等設置
            self.max_point_distance = 50.0
            self.pressure_threshold = 0.05         # ✅ 修正：從 0.0 改為 0.05
            self.velocity_threshold = 10.0
            self.pause_duration_threshold = 500.0
            self.enable_tilt_processing = False
            self.target_sampling_rate = 100
            self.data_collection_rate = 100
            self.debug_mode = True
            self.enable_simulator_pressure = True   # ✅ 修正：改為 True 以支援壓力測試
            self.enable_simulator_tilt = False
            self.simulator_noise_level = 0.05
            self.simulator_latency = 1.0
            self.simulator_jitter = 0.5
  
    def validate(self) -> bool:
        """驗證配置有效性"""
        try:
            # 基本參數驗證
            if self.target_sampling_rate <= 0:
                return False
            if self.stroke_timeout <= 0:
                return False
            if self.min_stroke_points < 1:
                return False
            if self.noise_threshold < 0:
                return False
            if self.pressure_threshold < 0:
                return False
            if not isinstance(self.feature_types, list):
                return False
            
            # RawDataCollector 參數驗證
            if self.data_collection_rate <= 0:
                return False
            if self.device_connection_timeout <= 0:
                return False
            if self.device_retry_attempts < 0:
                return False
            if self.device_retry_delay < 0:
                return False
            if self.raw_data_buffer_size <= 0:
                return False
            if self.data_queue_timeout <= 0:
                return False
            if self.calibration_points < 4:  # 至少需要4個校準點
                return False
            if self.calibration_timeout <= 0:
                return False
            
            # 模擬器參數驗證
            if self.simulator_noise_level < 0 or self.simulator_noise_level > 1:
                return False
            if self.simulator_latency < 0:
                return False
            if self.simulator_jitter < 0:
                return False
            
            # 數據品質參數驗證
            if self.outlier_threshold <= 0:
                return False
            if self.data_smoothing_window < 1:
                return False
            
            # 點處理參數驗證
            if self.max_point_distance <= 0:
                return False
            if self.max_velocity_jump <= 0:
                return False
            if self.min_time_delta <= 0:
                return False
            if self.max_time_delta <= self.min_time_delta:
                return False
            
            # 筆劃檢測參數驗證
            if self.velocity_threshold < 0:
                return False
            if self.min_velocity < 0 or self.max_velocity <= self.min_velocity:
                return False
            if self.acceleration_threshold < 0:
                return False
            if self.stroke_gap_threshold < 0:
                return False
            if self.min_stroke_duration < 0 or self.max_stroke_duration <= self.min_stroke_duration:
                return False
            if self.min_stroke_length < 0 or self.max_stroke_length <= self.min_stroke_length:
                return False
            
            # 設備尺寸驗證
            if self.device_width <= 0 or self.device_height <= 0:
                return False
            
            # 壓力值驗證
            if self.min_pressure < 0 or self.max_pressure <= self.min_pressure:
                return False
            
            # 緩衝區大小驗證
            if (self.point_buffer_size <= 0 or 
                self.stroke_buffer_size <= 0 or 
                self.event_buffer_size <= 0):
                return False
            
            return True
        except Exception:
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            # 基本配置
            'device_type': self.device_type,
            'target_sampling_rate': self.target_sampling_rate,
            'smoothing_enabled': self.smoothing_enabled,
            'smoothing_window_size': self.smoothing_window_size,
            'noise_threshold': self.noise_threshold,
            
            # 筆劃檢測
            'stroke_timeout': self.stroke_timeout,
            'min_stroke_points': self.min_stroke_points,
            'pressure_threshold': self.pressure_threshold,
            'pause_duration_threshold': self.pause_duration_threshold,
            
            # 特徵計算
            'feature_types': self.feature_types.copy() if self.feature_types else [],
            
            # 點處理
            'max_point_distance': self.max_point_distance,
            'max_velocity_jump': self.max_velocity_jump,
            'max_pressure_jump': self.max_pressure_jump,
            'min_time_delta': self.min_time_delta,
            'max_time_delta': self.max_time_delta,
            'interpolation_method': self.interpolation_method,
            'enable_interpolation': self.enable_interpolation,
            
            # 筆劃檢測參數
            'velocity_threshold': self.velocity_threshold,
            'min_velocity': self.min_velocity,
            'max_velocity': self.max_velocity,
            'acceleration_threshold': self.acceleration_threshold,
            'stroke_gap_threshold': self.stroke_gap_threshold,
            'min_stroke_duration': self.min_stroke_duration,
            'max_stroke_duration': self.max_stroke_duration,
            'min_stroke_length': self.min_stroke_length,
            'max_stroke_length': self.max_stroke_length,
            'stroke_detection_method': self.stroke_detection_method,
            'enable_stroke_merging': self.enable_stroke_merging,
            
            # RawDataCollector 參數
            'data_collection_rate': self.data_collection_rate,
            'enable_data_validation': self.enable_data_validation,
            'data_format': self.data_format,
            'device_connection_timeout': self.device_connection_timeout,
            'device_retry_attempts': self.device_retry_attempts,
            'device_retry_delay': self.device_retry_delay,
            'raw_data_buffer_size': self.raw_data_buffer_size,
            'data_queue_timeout': self.data_queue_timeout,
            'enable_data_compression': self.enable_data_compression,
            'enable_auto_calibration': self.enable_auto_calibration,
            'calibration_points': self.calibration_points,
            'calibration_timeout': self.calibration_timeout,
            
            # 模擬器配置
            'simulator_noise_level': self.simulator_noise_level,
            'simulator_latency': self.simulator_latency,
            'simulator_jitter': self.simulator_jitter,
            'enable_simulator_pressure': self.enable_simulator_pressure,
            'enable_simulator_tilt': self.enable_simulator_tilt,
            
            # 設備特定配置
            'wacom_driver_path': self.wacom_driver_path,
            'wacom_tablet_id': self.wacom_tablet_id,
            'touch_multitouch_enabled': self.touch_multitouch_enabled,
            'touch_gesture_enabled': self.touch_gesture_enabled,
            'mouse_acceleration': self.mouse_acceleration,
            'mouse_sensitivity': self.mouse_sensitivity,
            
            # 數據品質控制
            'enable_outlier_detection': self.enable_outlier_detection,
            'outlier_threshold': self.outlier_threshold,
            'enable_data_smoothing': self.enable_data_smoothing,
            'data_smoothing_window': self.data_smoothing_window,
            
            # 品質控制
            'enable_quality_check': self.enable_quality_check,
            'quality_score_threshold': self.quality_score_threshold,
            
            # 座標系統
            'coordinate_system': self.coordinate_system,
            'device_width': self.device_width,
            'device_height': self.device_height,
            
            # 壓力處理
            'pressure_normalization': self.pressure_normalization,
            'min_pressure': self.min_pressure,
            'max_pressure': self.max_pressure,
            
            # 緩衝區
            'point_buffer_size': self.point_buffer_size,
            'stroke_buffer_size': self.stroke_buffer_size,
            'event_buffer_size': self.event_buffer_size,
            
            # 性能
            'processing_threads': self.processing_threads,
            'enable_statistics': self.enable_statistics,
            
            # 調試
            'debug_mode': self.debug_mode,
            'log_level': self.log_level,
            'save_debug_data': self.save_debug_data
        }
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'ProcessingConfig':
        """從字典創建配置"""
        return cls(**config_dict)
    
    @classmethod
    def get_default_config(cls, device_type: str = "wacom") -> 'ProcessingConfig':
        """獲取預設配置"""
        configs = {
            "wacom": cls(
                device_type="wacom",
                target_sampling_rate=200,
                feature_types=['basic', 'kinematic', 'pressure', 'geometric'],
                max_point_distance=30.0,
                velocity_threshold=5.0,
                pause_duration_threshold=300.0,
                pressure_threshold=0.02,
                enable_tilt_processing=True,
                point_buffer_size=20000,
                data_collection_rate=200,
                enable_simulator_pressure=True,
                enable_simulator_tilt=True
            ),
            "touch": cls(
                device_type="touch",
                target_sampling_rate=100,
                feature_types=['basic', 'kinematic', 'geometric'],
                max_point_distance=50.0,
                velocity_threshold=15.0,
                pause_duration_threshold=600.0,
                pressure_threshold=0.01,
                enable_tilt_processing=False,
                point_buffer_size=15000,
                data_collection_rate=100,
                touch_multitouch_enabled=True
            ),
            "mouse": cls(
                device_type="mouse",
                target_sampling_rate=100,
                feature_types=['basic', 'kinematic'],
                max_point_distance=100.0,
                velocity_threshold=20.0,
                pause_duration_threshold=800.0,
                pressure_threshold=0.01,
                enable_tilt_processing=False,
                point_buffer_size=10000,
                data_collection_rate=100,
                mouse_acceleration=False
            ),
            "simulator": cls(
                device_type="simulator",
                target_sampling_rate=100,
                feature_types=['basic', 'kinematic'],
                max_point_distance=50.0,
                velocity_threshold=10.0,
                pause_duration_threshold=500.0,
                pressure_threshold=0.05,
                enable_tilt_processing=False,
                point_buffer_size=10000,
                data_collection_rate=100,
                debug_mode=True,
                simulator_noise_level=0.05,
                simulator_latency=1.0,
                simulator_jitter=0.5,
                enable_simulator_pressure=True,
                enable_simulator_tilt=False
            )
        }
        return configs.get(device_type, configs["wacom"])

# 預設配置常數
DEFAULT_WACOM_CONFIG = ProcessingConfig.get_default_config("wacom")
DEFAULT_TOUCH_CONFIG = ProcessingConfig.get_default_config("touch")
DEFAULT_MOUSE_CONFIG = ProcessingConfig.get_default_config("mouse")
DEFAULT_SIMULATOR_CONFIG = ProcessingConfig.get_default_config("simulator")

# 配置驗證函數
def validate_config(config: ProcessingConfig) -> tuple[bool, str]:
    """
    驗證配置並返回詳細信息
    
    Returns:
        tuple: (是否有效, 錯誤信息)
    """
    try:
        if not isinstance(config, ProcessingConfig):
            return False, "配置必須是 ProcessingConfig 實例"
        
        if not config.validate():
            return False, "配置參數驗證失敗"
        
        # 檢查設備類型
        valid_devices = [e.value for e in DeviceType]
        if config.device_type not in valid_devices:
            return False, f"不支援的設備類型: {config.device_type}"
        
        # 檢查特徵類型
        valid_features = ['basic', 'kinematic', 'pressure', 'geometric', 'temporal']
        for feature in config.feature_types:
            if feature not in valid_features:
                return False, f"不支援的特徵類型: {feature}"
        
        # 檢查插值方法
        valid_interpolation = ['linear', 'cubic', 'quadratic']
        if config.interpolation_method not in valid_interpolation:
            return False, f"不支援的插值方法: {config.interpolation_method}"
        
        # 檢查座標系統
        valid_coordinate_systems = ['screen', 'normalized', 'device']
        if config.coordinate_system not in valid_coordinate_systems:
            return False, f"不支援的座標系統: {config.coordinate_system}"
        
        # 檢查筆劃檢測方法
        valid_stroke_methods = ['velocity_based', 'pressure_based', 'time_based', 'hybrid']
        if config.stroke_detection_method not in valid_stroke_methods:
            return False, f"不支援的筆劃檢測方法: {config.stroke_detection_method}"
        
        # 檢查數據格式
        valid_data_formats = ['standard', 'extended', 'minimal']
        if config.data_format not in valid_data_formats:
            return False, f"不支援的數據格式: {config.data_format}"
        
        return True, "配置驗證通過"
        
    except Exception as e:
        return False, f"配置驗證異常: {str(e)}"

def create_config_from_device_type(device_type: str, **kwargs) -> ProcessingConfig:
    """
    根據設備類型創建配置
    
    Args:
        device_type: 設備類型
        **kwargs: 額外的配置參數
    
    Returns:
        ProcessingConfig: 配置實例
    """
    base_config = ProcessingConfig.get_default_config(device_type)
    
    # 更新額外參數
    for key, value in kwargs.items():
        if hasattr(base_config, key):
            setattr(base_config, key, value)
    
    return base_config

def get_config_summary(config: ProcessingConfig) -> str:
    """
    獲取配置摘要字符串
    
    Args:
        config: 配置實例
    
    Returns:
        str: 配置摘要
    """
    return f"""
    配置摘要:
    設備類型: {config.device_type}
    採樣率: {config.target_sampling_rate} Hz
    數據收集率: {config.data_collection_rate} Hz
    最大點距: {config.max_point_distance} px
    速度閾值: {config.velocity_threshold} px/ms
    暫停閾值: {config.pause_duration_threshold} ms
    筆劃超時: {config.stroke_timeout} s
    特徵類型: {', '.join(config.feature_types)}
    平滑化: {'啟用' if config.smoothing_enabled else '停用'}
    品質檢查: {'啟用' if config.enable_quality_check else '停用'}
    筆劃檢測: {config.stroke_detection_method}
    數據格式: {config.data_format}
    模擬器噪聲: {config.simulator_noise_level}
    調試模式: {'啟用' if config.debug_mode else '停用'}
    """