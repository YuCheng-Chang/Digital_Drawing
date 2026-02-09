from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import numpy as np
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional

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

# ✅ 修正後
@dataclass
class StrokeStatistics:
    """筆劃統計資訊"""
    stroke_id: int
    point_count: int
    total_length: float
    duration: float
    bounding_box: Tuple[float, float, float, float]
    width: float
    height: float
    
    # 壓力統計
    average_pressure: float
    max_pressure: float
    min_pressure: float
    pressure_std: float
    
    # 速度統計
    average_velocity: float
    max_velocity: float
    min_velocity: float
    velocity_std: float
    
    # 高級特徵
    smoothness: float
    complexity: float
    tremor_index: float
    
    # 時間戳
    start_time: float
    end_time: float


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





class ToolType(Enum):
    """工具類型"""
    PEN = "pen"
    ERASER = "eraser"

@dataclass
class StrokeMetadata:
    """筆劃元數據"""
    stroke_id: int
    tool_type: ToolType
    timestamp_start: float
    timestamp_end: float
    is_deleted: bool = False          # 是否被橡皮擦刪除
    deleted_by: Optional[int] = None  # 被哪個橡皮擦筆劃刪除
    deleted_at: Optional[float] = None  # 刪除時間

@dataclass
class EraserStroke:
    """橡皮擦筆劃"""
    eraser_id: int
    points: List[ProcessedInkPoint]  # 橡皮擦軌跡點
    radius: float                     # 橡皮擦半徑（像素）
    deleted_stroke_ids: List[int]     # 刪除了哪些筆劃
    timestamp_start: float
    timestamp_end: float
