"""
LSL Data Recorder

負責記錄 LSL 串流數據並儲存到檔案
"""

import time
import json
import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import numpy as np


@dataclass
class InkSample:
    """墨水數據樣本"""
    timestamp: float
    x: float
    y: float
    pressure: float
    tilt_x: float
    tilt_y: float
    velocity: float
    stroke_id: int
    event_type: int


@dataclass
class MarkerEvent:
    """事件標記"""
    timestamp: float
    marker_text: str


class LSLDataRecorder:
    """
    LSL 數據記錄器
    
    記錄墨水數據和事件標記，並在串流結束時儲存到檔案
    """
    
    def __init__(self, output_dir: str = "./lsl_recordings"):
        """
        初始化數據記錄器
        
        Args:
            output_dir: 輸出目錄路徑
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger('LSLDataRecorder')
        
        # 數據緩衝
        self.ink_samples: List[InkSample] = []
        self.markers: List[MarkerEvent] = []
        
        # 記錄狀態
        self.is_recording = False
        self.recording_start_time = None
        self.session_id = None
        
        # 元數據
        self.metadata = {
            'recording_start': None,
            'recording_end': None,
            'device_info': {},
            'stream_config': {}
        }
    
    def start_recording(self, 
                        session_id: Optional[str] = None,
                        metadata: Optional[Dict] = None) -> str:
        """
        開始記錄
        
        Args:
            session_id: 會話 ID（如果為 None，自動生成）
            metadata: 額外的元數據
        
        Returns:
            str: 會話 ID
        """
        if self.is_recording:
            self.logger.warning("Recording already in progress")
            return self.session_id
        
        # 生成會話 ID
        if session_id is None:
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        self.session_id = session_id
        self.recording_start_time = time.time()
        self.is_recording = True
        
        # 清空緩衝
        self.ink_samples.clear()
        self.markers.clear()
        
        # 設置元數據
        self.metadata['recording_start'] = datetime.now().isoformat()
        self.metadata['session_id'] = session_id
        
        if metadata:
            self.metadata.update(metadata)
        
        self.logger.info(f"Recording started: session_id={session_id}")
        return session_id
    
    def record_ink_sample(self,
                         timestamp: float,
                         x: float,
                         y: float,
                         pressure: float,
                         tilt_x: float = 0.0,
                         tilt_y: float = 0.0,
                         velocity: float = 0.0,
                         stroke_id: int = 0,
                         event_type: int = 0):
        """
        記錄墨水數據樣本
        
        Args:
            timestamp: LSL 時間戳
            x, y: 座標
            pressure: 壓力
            tilt_x, tilt_y: 傾斜角度
            velocity: 速度
            stroke_id: 筆劃 ID
            event_type: 事件類型
        """
        if not self.is_recording:
            return
        
        sample = InkSample(
            timestamp=timestamp,
            x=x,
            y=y,
            pressure=pressure,
            tilt_x=tilt_x,
            tilt_y=tilt_y,
            velocity=velocity,
            stroke_id=stroke_id,
            event_type=event_type
        )
        
        self.ink_samples.append(sample)
    
    def record_marker(self, timestamp: float, marker_text: str):
        """
        記錄事件標記
        
        Args:
            timestamp: LSL 時間戳
            marker_text: 標記文字
        """
        if not self.is_recording:
            return
        
        marker = MarkerEvent(
            timestamp=timestamp,
            marker_text=marker_text
        )
        
        self.markers.append(marker)
        self.logger.debug(f"Marker recorded: {marker_text} at {timestamp:.3f}")
    
    def stop_recording(self) -> Dict[str, str]:
        """
        停止記錄並儲存數據
        
        Returns:
            Dict: 儲存的檔案路徑
        """
        if not self.is_recording:
            self.logger.warning("No recording in progress")
            return {}
        
        self.is_recording = False
        self.metadata['recording_end'] = datetime.now().isoformat()
        self.metadata['recording_duration'] = time.time() - self.recording_start_time
        self.metadata['total_ink_samples'] = len(self.ink_samples)
        self.metadata['total_markers'] = len(self.markers)
        
        self.logger.info(f"Recording stopped. Saving {len(self.ink_samples)} ink samples and {len(self.markers)} markers...")
        
        # 儲存數據
        saved_files = self._save_data()
        
        self.logger.info(f"Data saved successfully: {saved_files}")
        return saved_files
    
    def _save_data(self) -> Dict[str, str]:
        """
        儲存數據到檔案
        
        Returns:
            Dict: 儲存的檔案路徑
        """
        session_dir = self.output_dir / self.session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        saved_files = {}
        
        # 1. 儲存墨水數據（CSV 格式）
        ink_csv_path = session_dir / "ink_data.csv"
        self._save_ink_data_csv(ink_csv_path)
        saved_files['ink_csv'] = str(ink_csv_path)
        
        # 2. 儲存墨水數據（JSON 格式）
        ink_json_path = session_dir / "ink_data.json"
        self._save_ink_data_json(ink_json_path)
        saved_files['ink_json'] = str(ink_json_path)
        
        # 3. 儲存事件標記（CSV 格式）
        markers_csv_path = session_dir / "markers.csv"
        self._save_markers_csv(markers_csv_path)
        saved_files['markers_csv'] = str(markers_csv_path)
        
        # 4. 儲存元數據
        metadata_path = session_dir / "metadata.json"
        self._save_metadata(metadata_path)
        saved_files['metadata'] = str(metadata_path)
        
        # 5. 儲存統計摘要
        summary_path = session_dir / "summary.txt"
        self._save_summary(summary_path)
        saved_files['summary'] = str(summary_path)
        
        return saved_files
    
    def _save_ink_data_csv(self, filepath: Path):
        """儲存墨水數據為 CSV"""
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 寫入標頭
            writer.writerow([
                'timestamp', 'x', 'y', 'pressure',
                'tilt_x', 'tilt_y', 'velocity',
                'stroke_id', 'event_type'
            ])
            
            # 寫入數據
            for sample in self.ink_samples:
                writer.writerow([
                    f"{sample.timestamp:.6f}",
                    f"{sample.x:.6f}",
                    f"{sample.y:.6f}",
                    f"{sample.pressure:.6f}",
                    f"{sample.tilt_x:.3f}",
                    f"{sample.tilt_y:.3f}",
                    f"{sample.velocity:.3f}",
                    sample.stroke_id,
                    sample.event_type
                ])
    
    def _save_ink_data_json(self, filepath: Path):
        """儲存墨水數據為 JSON"""
        data = {
            'session_id': self.session_id,
            'samples': [asdict(sample) for sample in self.ink_samples]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    def _save_markers_csv(self, filepath: Path):
        """儲存事件標記為 CSV"""
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 寫入標頭
            writer.writerow(['timestamp', 'marker_text'])
            
            # 寫入數據
            for marker in self.markers:
                writer.writerow([
                    f"{marker.timestamp:.6f}",
                    marker.marker_text
                ])
    
    def _save_metadata(self, filepath: Path):
        """儲存元數據"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2)
    
    def _save_summary(self, filepath: Path):
        """儲存統計摘要"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("LSL Recording Summary\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"Session ID: {self.session_id}\n")
            f.write(f"Recording Start: {self.metadata['recording_start']}\n")
            f.write(f"Recording End: {self.metadata['recording_end']}\n")
            f.write(f"Duration: {self.metadata['recording_duration']:.2f} seconds\n\n")
            
            f.write(f"Total Ink Samples: {len(self.ink_samples)}\n")
            f.write(f"Total Markers: {len(self.markers)}\n\n")
            
            # 計算統計資訊
            if len(self.ink_samples) > 0:
                timestamps = [s.timestamp for s in self.ink_samples]
                pressures = [s.pressure for s in self.ink_samples]
                velocities = [s.velocity for s in self.ink_samples]
                
                f.write("Ink Data Statistics:\n")
                f.write(f"  Time range: {min(timestamps):.3f} - {max(timestamps):.3f} s\n")
                f.write(f"  Average sampling rate: {len(self.ink_samples) / (max(timestamps) - min(timestamps)):.1f} Hz\n")
                f.write(f"  Pressure range: {min(pressures):.3f} - {max(pressures):.3f}\n")
                f.write(f"  Average pressure: {np.mean(pressures):.3f}\n")
                f.write(f"  Average velocity: {np.mean(velocities):.1f} px/s\n")
                f.write(f"  Max velocity: {max(velocities):.1f} px/s\n\n")
            
            # 列出所有標記
            if len(self.markers) > 0:
                f.write("Event Markers:\n")
                for marker in self.markers:
                    f.write(f"  [{marker.timestamp:.3f}] {marker.marker_text}\n")
    
    def get_recording_stats(self) -> Dict[str, Any]:
        """
        獲取當前記錄統計
        
        Returns:
            Dict: 統計資訊
        """
        stats = {
            'is_recording': self.is_recording,
            'session_id': self.session_id,
            'total_ink_samples': len(self.ink_samples),
            'total_markers': len(self.markers)
        }
        
        if self.recording_start_time:
            stats['recording_duration'] = time.time() - self.recording_start_time
        
        return stats