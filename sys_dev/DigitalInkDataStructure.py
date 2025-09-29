from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import numpy as np

class StrokeState(Enum):
  """筆劃狀態枚舉"""
  IDLE = 0
  STARTING = 1
  ACTIVE = 2
  ENDING = 3
  COMPLETED = 4

class EventType(Enum):
  """事件類型枚舉"""
  PEN_DOWN = 1
  PEN_MOVE = 2
  PEN_UP = 3
  PEN_HOVER = 4
  STROKE_START = 5
  STROKE_END = 6
  PAUSE_DETECTED = 7
  RESUME_DETECTED = 8

@dataclass
class RawInkPoint:
  """原始墨水點數據結構"""
  x: float                    # X座標 (設備座標系)
  y: float                    # Y座標 (設備座標系)
  pressure: float             # 壓力值 (0.0-1.0)
  tilt_x: float               # X軸傾斜角度 (度)
  tilt_y: float               # Y軸傾斜角度 (度)
  twist: float                # 筆桿旋轉角度 (度)
  timestamp: float            # 設備時間戳
  device_id: str              # 設備識別碼
  button_state: int           # 按鈕狀態位元遮罩

@dataclass
class ProcessedInkPoint:
  """處理後的墨水點數據結構"""
  # 基本屬性 (從RawInkPoint繼承)
  x: float                    # 正規化X座標 (0.0-1.0)
  y: float                    # 正規化Y座標 (0.0-1.0)
  pressure: float             # 正規化壓力值 (0.0-1.0)
  tilt_x: float               # X軸傾斜角度
  tilt_y: float               # Y軸傾斜角度
  twist: float                # 筆桿旋轉角度
  timestamp: float            # 統一時間戳

  # 計算屬性
  velocity: float             # 瞬時速度 (單位/秒)
  acceleration: float         # 瞬時加速度 (單位/秒²)
  direction: float            # 移動方向角度 (弧度)
  curvature: float            # 曲率

  # 上下文屬性
  stroke_id: int              # 所屬筆劃ID
  point_index: int            # 在筆劃中的索引
  distance_from_start: float  # 從筆劃起點的累積距離

  # 品質指標
  confidence: float           # 數據品質信心度 (0.0-1.0)
  is_interpolated: bool       # 是否為插值點

@dataclass
class StrokeStatistics:
  """筆劃統計資訊"""
  stroke_id: int
  point_count: int
  total_length: float
  duration: float            # 持續時間 (秒)
  avg_pressure: float
  max_pressure: float
  avg_velocity: float
  max_velocity: float
  total_acceleration: float
  bounding_box: Tuple[float, float, float, float]  # (min_x, min_y, max_x, max_y)
  start_timestamp: float
  end_timestamp: float

@dataclass
class InkStroke:
  """完整的墨水筆劃"""
  stroke_id: int
  points: List[ProcessedInkPoint]
  statistics: StrokeStatistics
  state: StrokeState
  metadata: Dict[str, Any]

@dataclass
class InkEvent:
  """墨水事件"""
  event_type: EventType
  timestamp: float
  stroke_id: Optional[int]
  point_data: Optional[ProcessedInkPoint]
  metadata: Dict[str, Any]

@dataclass
class ProcessingConfig:
  """處理配置參數"""
  # 採樣設定
  target_sampling_rate: int = 200        # 目標採樣率 (Hz)
  interpolation_enabled: bool = True     # 是否啟用插值

  # 筆劃檢測參數
  pressure_threshold: float = 0.05       # 壓力閾值
  velocity_threshold: float = 0.1        # 速度閾值
  pause_duration_threshold: float = 0.5  # 暫停檢測閾值 (秒)

  # 濾波參數
  smoothing_enabled: bool = True
  smoothing_window_size: int = 5

  # 座標正規化
  coordinate_bounds: Tuple[float, float, float, float] = (0, 0, 1, 1)  # (min_x, min_y, max_x, max_y)

  # 品質控制
  min_stroke_length: float = 0.01       # 最小筆劃長度
  max_point_distance: float = 0.1       # 最大點間距離