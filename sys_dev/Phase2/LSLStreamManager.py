"""
LSL Stream Manager for Digital Ink Data

負責建立和管理數位墨水的 LSL 串流，包括：
- 墨水數據串流（座標、壓力、傾斜等）
- 事件標記串流（筆劃開始/結束、任務階段）
"""

import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pylsl import StreamInfo, StreamOutlet, local_clock
import numpy as np


@dataclass
class LSLStreamConfig:
    """LSL 串流配置"""
    # 墨水數據串流配置
    ink_stream_name: str = "DigitalInk"
    ink_stream_type: str = "Ink"
    ink_channel_count: int = 8  # x, y, pressure, tilt_x, tilt_y, velocity, stroke_id, event_type
    ink_sampling_rate: float = 200.0  # Hz（標稱採樣率）
    
    # 事件標記串流配置
    marker_stream_name: str = "InkMarkers"
    marker_stream_type: str = "Markers"
    marker_channel_count: int = 1
    
    # 設備資訊
    device_manufacturer: str = "Wacom"
    device_model: str = "Wacom One 12"
    device_serial: str = ""
    
    # 座標標準化範圍
    normalize_coordinates: bool = True
    screen_width: float = 1920.0
    screen_height: float = 1080.0


class LSLStreamManager:
    """
    LSL 串流管理器
    
    負責建立、管理和關閉 LSL 串流
    """
    
    def __init__(self, config: LSLStreamConfig):
        """
        初始化 LSL 串流管理器
        
        Args:
            config: LSL 串流配置
        """
        self.config = config
        self.logger = logging.getLogger('LSLStreamManager')
        
        # 串流物件
        self.ink_outlet: Optional[StreamOutlet] = None
        self.marker_outlet: Optional[StreamOutlet] = None
        
        # 串流狀態
        self.is_streaming = False
        self.stream_start_time = None
        
        # 統計資訊
        self.stats = {
            'total_ink_samples': 0,
            'total_markers': 0,
            'stream_duration': 0.0,
            'last_sample_time': None
        }
        
    def initialize_streams(self) -> bool:
        """
        初始化 LSL 串流
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            self.logger.info("Initializing LSL streams...")
            
            # 建立墨水數據串流
            if not self._create_ink_stream():
                return False
            
            # 建立事件標記串流
            if not self._create_marker_stream():
                return False
            
            self.is_streaming = True
            self.stream_start_time = local_clock()
            
            self.logger.info("LSL streams initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize LSL streams: {e}")
            return False
    
    def _create_ink_stream(self) -> bool:
        """建立墨水數據串流"""
        try:
            # 創建串流資訊
            info = StreamInfo(
                name=self.config.ink_stream_name,
                type=self.config.ink_stream_type,
                channel_count=self.config.ink_channel_count,
                nominal_srate=self.config.ink_sampling_rate,
                channel_format='float32',
                source_id=f"{self.config.device_manufacturer}_{self.config.device_model}"
            )
            
            # 添加設備 metadata
            channels = info.desc().append_child("channels")
            
            channel_names = [
                "x", "y", "pressure", 
                "tilt_x", "tilt_y", 
                "velocity", "stroke_id", "event_type"
            ]
            
            channel_units = [
                "normalized" if self.config.normalize_coordinates else "pixels",
                "normalized" if self.config.normalize_coordinates else "pixels",
                "normalized",  # 0-1
                "degrees",     # -90 to 90
                "degrees",     # -90 to 90
                "pixels/s",
                "count",       # 筆劃 ID
                "enum"         # 事件類型（0=normal, 1=start, 2=end）
            ]
            
            for name, unit in zip(channel_names, channel_units):
                ch = channels.append_child("channel")
                ch.append_child_value("label", name)
                ch.append_child_value("unit", unit)
                ch.append_child_value("type", "Ink")
            
            # 添加設備資訊
            acquisition = info.desc().append_child("acquisition")
            acquisition.append_child_value("manufacturer", self.config.device_manufacturer)
            acquisition.append_child_value("model", self.config.device_model)
            if self.config.device_serial:
                acquisition.append_child_value("serial_number", self.config.device_serial)
            
            # 創建輸出串流
            self.ink_outlet = StreamOutlet(info, chunk_size=32, max_buffered=360)
            
            self.logger.info(f"Ink stream created: {self.config.ink_stream_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create ink stream: {e}")
            return False
    
    def _create_marker_stream(self) -> bool:
        """建立事件標記串流"""
        try:
            # 創建串流資訊
            info = StreamInfo(
                name=self.config.marker_stream_name,
                type=self.config.marker_stream_type,
                channel_count=self.config.marker_channel_count,
                nominal_srate=0,  # 不規則採樣
                channel_format='string',
                source_id=f"{self.config.device_manufacturer}_{self.config.device_model}_markers"
            )
            
            # 添加 metadata
            desc = info.desc()
            desc.append_child_value("manufacturer", self.config.device_manufacturer)
            desc.append_child_value("model", self.config.device_model)
            
            # 創建輸出串流
            self.marker_outlet = StreamOutlet(info)
            
            self.logger.info(f"Marker stream created: {self.config.marker_stream_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create marker stream: {e}")
            return False
    
    def push_ink_sample(self, 
                        x: float, 
                        y: float, 
                        pressure: float,
                        tilt_x: float = 0.0,
                        tilt_y: float = 0.0,
                        velocity: float = 0.0,
                        stroke_id: int = 0,
                        event_type: int = 0,
                        timestamp: Optional[float] = None) -> bool:
        """
        推送墨水數據樣本到 LSL 串流
        
        Args:
            x: X 座標
            y: Y 座標
            pressure: 壓力值 (0-1)
            tilt_x: X 軸傾斜角度 (degrees)
            tilt_y: Y 軸傾斜角度 (degrees)
            velocity: 移動速度 (pixels/s)
            stroke_id: 筆劃 ID
            event_type: 事件類型 (0=normal, 1=stroke_start, 2=stroke_end)
            timestamp: 時間戳（如果為 None，使用當前時間）
        
        Returns:
            bool: 是否成功推送
        """
        if not self.is_streaming or self.ink_outlet is None:
            return False
        
        try:
            # 座標標準化
            if self.config.normalize_coordinates:
                x_norm = x / self.config.screen_width
                y_norm = y / self.config.screen_height
            else:
                x_norm = x
                y_norm = y
            
            # 構建樣本數據
            sample = [
                float(x_norm),
                float(y_norm),
                float(pressure),
                float(tilt_x),
                float(tilt_y),
                float(velocity),
                float(stroke_id),
                float(event_type)
            ]
            
            # 推送到 LSL
            if timestamp is None:
                self.ink_outlet.push_sample(sample)
            else:
                self.ink_outlet.push_sample(sample, timestamp)
            
            # 更新統計
            self.stats['total_ink_samples'] += 1
            self.stats['last_sample_time'] = local_clock()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to push ink sample: {e}")
            return False
    
    def push_marker(self, 
                    marker_text: str, 
                    timestamp: Optional[float] = None) -> bool:
        """
        推送事件標記到 LSL 串流
        
        Args:
            marker_text: 標記文字（例如："stroke_start", "stroke_end", "task_begin"）
            timestamp: 時間戳（如果為 None，使用當前時間）
        
        Returns:
            bool: 是否成功推送
        """
        if not self.is_streaming or self.marker_outlet is None:
            return False
        
        try:
            # 推送標記
            if timestamp is None:
                self.marker_outlet.push_sample([marker_text])
            else:
                self.marker_outlet.push_sample([marker_text], timestamp)
            
            # 更新統計
            self.stats['total_markers'] += 1
            
            self.logger.debug(f"Marker pushed: {marker_text}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to push marker: {e}")
            return False
    
    def get_stream_time(self) -> float:
        """
        獲取當前 LSL 時間戳
        
        Returns:
            float: LSL 時間戳
        """
        return local_clock()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        獲取串流統計資訊
        
        Returns:
            Dict: 統計資訊
        """
        if self.stream_start_time:
            self.stats['stream_duration'] = local_clock() - self.stream_start_time
        
        return self.stats.copy()
    
    def close_streams(self):
        """關閉 LSL 串流"""
        try:
            self.logger.info("Closing LSL streams...")
            
            # 發送結束標記
            if self.marker_outlet:
                self.push_marker("stream_end")
            
            # 關閉串流
            self.ink_outlet = None
            self.marker_outlet = None
            self.is_streaming = False
            
            # 記錄最終統計
            final_stats = self.get_stats()
            self.logger.info(f"Stream closed. Final stats: {final_stats}")
            
        except Exception as e:
            self.logger.error(f"Error closing streams: {e}")