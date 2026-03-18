# LSLDataRecorder.py
"""
LSL Data Recorder with Extended Time-Range Based Cleaning

負責記錄 LSL 串流數據並儲存到檔案
自動清理規則：
1. stroke_start → tool_switch|from:pen|to:eraser
2. stroke_start → tool_switch|from:pen|to:pen
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
    """墨水數據樣本（添加顏色）"""
    timestamp: float
    x: float
    y: float
    pressure: float
    tilt_x: float
    tilt_y: float
    velocity: float
    stroke_id: int
    event_type: int
    color: str = 'black'  # 🆕 添加顏色欄位


@dataclass
class MarkerEvent:
    """事件標記"""
    timestamp: float
    marker_text: str


class LSLDataRecorder:
    """
    LSL 數據記錄器（擴展清理模式）
    
    記錄墨水數據和事件標記，並在串流結束時儲存到檔案
    清理規則：
    1. stroke_start → tool_switch|from:pen|to:eraser
    2. stroke_start → tool_switch|from:pen|to:pen
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
                        event_type: int = 0,
                        color: str = 'black'):  # 🆕 添加顏色參數
        """記錄墨水數據樣本（添加顏色）"""
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
            event_type=event_type,
            color=color  # 🆕 添加顏色
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
    
    def _clean_invalid_strokes_extended(self, markers: List[MarkerEvent], ink_samples: List[InkSample]) -> tuple:
        """
        🆕 擴展版：支援兩種 invalid stroke 模式 + 去除重複的 stroke_start
        
        清理規則：
        1. stroke_start → tool_switch|from:pen|to:eraser
        2. stroke_start → tool_switch|from:pen|to:pen
        3. 🆕 去除重複的 stroke_start_X 事件（保留第一個）
        
        ✅✅✅ 保留所有 recording_start 事件（不刪除）
        
        Args:
            markers: 原始標記列表
            ink_samples: 原始墨水點列表
        
        Returns:
            tuple: (清理後的標記, 清理後的墨水點, 清理統計)
        """
        if not markers:
            return markers, ink_samples, {}
        
        self.logger.info("🧹 開始清理（擴展模式：pen→eraser、pen→pen + 去重）...")
        
        # ✅✅✅ 找到最後一個 recording_start 的時間戳
        last_recording_start_time = None
        for marker in reversed(markers):
            if marker.marker_text == "recording_start":
                last_recording_start_time = marker.timestamp
                self.logger.info(f"✅ 找到最後一個 recording_start: {last_recording_start_time:.3f}")
                break
        
        # 🆕🆕🆕 步驟 1：去除重複的 stroke_start
        deduplicated_markers = []
        seen_stroke_starts = set()  # 記錄已經見過的 stroke_start_X
        duplicate_count = 0
        
        for marker in markers:
            marker_text = marker.marker_text
            
            # 檢查是否為 stroke_start
            if marker_text.startswith('stroke_start_'):
                if marker_text in seen_stroke_starts:
                    # 重複的 stroke_start，跳過
                    duplicate_count += 1
                    self.logger.info(f"🗑️ 移除重複的標記: {marker_text} at {marker.timestamp:.3f}")
                    continue
                else:
                    # 第一次見到，記錄並保留
                    seen_stroke_starts.add(marker_text)
            
            deduplicated_markers.append(marker)
        
        self.logger.info(f"✅ 去重完成，移除 {duplicate_count} 個重複的 stroke_start 標記")
        
        # 🆕🆕🆕 步驟 2：使用去重後的標記進行後續清理
        markers = deduplicated_markers
        
        # 按時間排序標記
        sorted_markers = sorted(enumerate(markers), key=lambda x: x[1].timestamp)
        
        invalid_time_ranges = []  # 儲存需要刪除的時間範圍 [(start_time, end_time, stroke_id, reason), ...]
        invalid_marker_indices = set()
        
        # 遍歷標記找出無效的 stroke_start 及其時間範圍
        for i in range(len(sorted_markers)):
            current_idx, current_marker = sorted_markers[i]
            current_text = current_marker.marker_text
            
            # ✅✅✅ 跳過 recording_start 事件（不刪除）
            if current_text == "recording_start":
                continue
            
            # ✅✅✅ 如果有最後一個 recording_start，只清理它之後的數據
            if last_recording_start_time is not None:
                if current_marker.timestamp < last_recording_start_time:
                    # 這個標記在最後一次 recording_start 之前，標記為刪除
                    invalid_marker_indices.add(current_idx)
                    continue
            
            # 檢查當前標記是否為 stroke_start
            if current_text.startswith('stroke_start_'):
                stroke_id = current_text.replace('stroke_start_', '')
                stroke_start_time = current_marker.timestamp
                
                # 向前查找，找到下一個相關事件
                found_invalid_tool_switch = False
                invalid_reason = None
                next_event_time = None
                
                # 查找後續事件
                for j in range(i + 1, len(sorted_markers)):
                    next_idx, next_marker = sorted_markers[j]
                    next_text = next_marker.marker_text
                    
                    # 如果遇到 stroke_end，說明這是正常筆劃，跳出
                    if next_text == f'stroke_end_{stroke_id}':
                        break
                    
                    # 如果遇到另一個 stroke_start，記錄時間作為刪除範圍的結束點
                    if next_text.startswith('stroke_start_'):
                        next_event_time = next_marker.timestamp
                        break
                    
                    # 🆕🆕🆕 檢查兩種 invalid tool_switch 模式
                    if 'tool_switch' in next_text and 'from:pen' in next_text:
                        # 模式 1: pen → eraser
                        if 'to:eraser' in next_text:
                            found_invalid_tool_switch = True
                            invalid_reason = 'pen→eraser'
                            # 不要 break，繼續找下一個 stroke_start 作為結束點
                        
                        # 模式 2: pen → pen
                        elif 'to:pen' in next_text:
                            found_invalid_tool_switch = True
                            invalid_reason = 'pen→pen'
                            # 不要 break，繼續找下一個 stroke_start 作為結束點
                
                # 如果找到 invalid tool_switch，記錄時間範圍
                if found_invalid_tool_switch:
                    # 如果沒有找到下一個 stroke_start，使用無窮大作為結束時間
                    if next_event_time is None:
                        next_event_time = float('inf')
                    
                    self.logger.info(f"🗑️ 發現無效筆劃: {current_text} (原因: {invalid_reason})")
                    self.logger.info(f"   刪除時間範圍: {stroke_start_time:.3f} ~ {next_event_time:.3f}")
                    
                    invalid_time_ranges.append((stroke_start_time, next_event_time, stroke_id, invalid_reason))
                    invalid_marker_indices.add(current_idx)
        
        # 清理標記（移除無效的 stroke_start 和 recording_start 之前的標記）
        cleaned_markers = []
        for i, marker in enumerate(markers):
            if i not in invalid_marker_indices:
                cleaned_markers.append(marker)
        
        # ✅✅✅ 清理墨水點（基於時間範圍刪除 + 刪除 recording_start 之前的點）
        cleaned_ink_samples = []
        removed_samples_count = 0
        removal_reasons = {'pen→eraser': 0, 'pen→pen': 0, 'before_recording_start': 0}
        
        for sample in ink_samples:
            should_remove = False
            removal_reason = None
            
            # ✅✅✅ 如果有最後一個 recording_start，刪除它之前的所有墨水點
            if last_recording_start_time is not None:
                if sample.timestamp < last_recording_start_time:
                    should_remove = True
                    removal_reason = 'before_recording_start'
            
            # 檢查是否在任何無效時間範圍內
            if not should_remove:
                for start_time, end_time, stroke_id, reason in invalid_time_ranges:
                    # 只刪除在時間範圍內且 stroke_id 匹配的墨水點
                    if start_time <= sample.timestamp < end_time and str(sample.stroke_id) == stroke_id:
                        should_remove = True
                        removal_reason = reason
                        self.logger.debug(f"   刪除墨水點: timestamp={sample.timestamp:.3f}, stroke_id={sample.stroke_id}, 原因={reason}")
                        break
            
            if not should_remove:
                cleaned_ink_samples.append(sample)
            else:
                removed_samples_count += 1
                if removal_reason:
                    removal_reasons[removal_reason] += 1
        
        # 統計結果
        removed_markers = len(invalid_marker_indices)
        
        cleaning_stats = {
            'invalid_time_ranges': len(invalid_time_ranges),
            'removed_markers': removed_markers,
            'removed_ink_samples': removed_samples_count,
            'removal_by_reason': removal_reasons,
            'remaining_markers': len(cleaned_markers),
            'remaining_ink_samples': len(cleaned_ink_samples),
            'last_recording_start_time': last_recording_start_time,
            'duplicate_stroke_starts_removed': duplicate_count  # 🆕 新增統計
        }
        
        self.logger.info(f"✅ 清理完成:")
        self.logger.info(f"   - 重複 stroke_start 移除: {duplicate_count} 個")  # 🆕
        self.logger.info(f"   - 無效時間範圍: {cleaning_stats['invalid_time_ranges']} 個")
        self.logger.info(f"   - 移除標記: {cleaning_stats['removed_markers']} 個")
        self.logger.info(f"   - 移除墨水點: {cleaning_stats['removed_ink_samples']} 個")
        self.logger.info(f"     • pen→eraser: {removal_reasons['pen→eraser']} 個")
        self.logger.info(f"     • pen→pen: {removal_reasons['pen→pen']} 個")
        self.logger.info(f"     • before_recording_start: {removal_reasons['before_recording_start']} 個")
        self.logger.info(f"   - 剩餘標記: {cleaning_stats['remaining_markers']} 個")
        self.logger.info(f"   - 剩餘墨水點: {cleaning_stats['remaining_ink_samples']} 個")
        
        return cleaned_markers, cleaned_ink_samples, cleaning_stats


    
    def _save_data(self) -> Dict[str, str]:
        """
        儲存數據到檔案（含擴展清理功能）
        
        Returns:
            Dict: 儲存的檔案路徑
        """
        session_dir = self.output_dir
        session_dir.mkdir(parents=True, exist_ok=True)
        
        saved_files = {}
        
        # 🆕🆕🆕 在保存前使用擴展清理
        cleaned_markers, cleaned_ink_samples, cleaning_stats = self._clean_invalid_strokes_extended(
            self.markers, self.ink_samples
        )
        
        # 1. 儲存清理後的墨水數據（CSV 格式）
        ink_csv_path = session_dir / "ink_data.csv"
        self._save_ink_data_csv_cleaned(ink_csv_path, cleaned_ink_samples)
        saved_files['ink_csv'] = str(ink_csv_path)
        
        # 2. 儲存清理後的墨水數據（JSON 格式）
        ink_json_path = session_dir / "ink_data.json"
        self._save_ink_data_json_cleaned(ink_json_path, cleaned_ink_samples)
        saved_files['ink_json'] = str(ink_json_path)
        
        # 3. 儲存清理後的事件標記（CSV 格式）
        markers_csv_path = session_dir / "markers.csv"
        self._save_markers_csv_cleaned(markers_csv_path, cleaned_markers)
        saved_files['markers_csv'] = str(markers_csv_path)
        
        # ✅✅✅ 修復：總是儲存原始數據（移除條件判斷）
        raw_markers_path = session_dir / "markers_raw.csv"
        self._save_markers_csv_raw(raw_markers_path)
        saved_files['markers_raw'] = str(raw_markers_path)
        
        raw_ink_path = session_dir / "ink_data_raw.csv"
        self._save_ink_data_csv_raw(raw_ink_path)
        saved_files['ink_data_raw'] = str(raw_ink_path)
        
        # 記錄是否有數據被清理
        if len(cleaned_markers) != len(self.markers) or len(cleaned_ink_samples) != len(self.ink_samples):
            self.logger.info("💾 已保存原始數據（有數據被清理）")
        else:
            self.logger.info("💾 已保存原始數據（沒有數據被清理，但仍保存用於對比）")
        
        # 5. 儲存元數據
        metadata_path = session_dir / "metadata.json"
        self._save_metadata_with_cleaning_stats(metadata_path, cleaning_stats)
        saved_files['metadata'] = str(metadata_path)
        
        # 6. 儲存統計摘要
        summary_path = session_dir / "summary.txt"
        self._save_summary_with_cleaning_stats(summary_path, cleaned_markers, cleaned_ink_samples, cleaning_stats)
        saved_files['summary'] = str(summary_path)
        
        return saved_files

    def _save_ink_data_csv_cleaned(self, filepath: Path, cleaned_samples: List[InkSample]):
        """儲存清理後的墨水數據為 CSV（添加顏色欄位）"""
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 寫入標頭（添加 color）
            writer.writerow([
                'timestamp', 'x', 'y', 'pressure',
                'tilt_x', 'tilt_y', 'velocity',
                'stroke_id', 'event_type', 'color'  # 🆕 添加 color
            ])
            
            # 寫入清理後的數據
            for sample in cleaned_samples:
                writer.writerow([
                    f"{sample.timestamp:.6f}",
                    f"{sample.x:.6f}",
                    f"{sample.y:.6f}",
                    f"{sample.pressure:.6f}",
                    f"{sample.tilt_x:.3f}",
                    f"{sample.tilt_y:.3f}",
                    f"{sample.velocity:.3f}",
                    sample.stroke_id,
                    sample.event_type,
                    sample.color  # 🆕 添加顏色
                ])

    
    def _save_ink_data_json_cleaned(self, filepath: Path, cleaned_samples: List[InkSample]):
        """儲存清理後的墨水數據為 JSON"""
        data = {
            'session_id': self.session_id,
            'samples': [asdict(sample) for sample in cleaned_samples],
            'data_cleaned': True,
            'cleaning_method': 'time_range_based_extended',
            'cleaning_rules': [
                'stroke_start → tool_switch|from:pen|to:eraser (delete by time range)',
                'stroke_start → tool_switch|from:pen|to:pen (delete by time range)'
            ],
            'original_sample_count': len(self.ink_samples),
            'cleaned_sample_count': len(cleaned_samples)
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    def _save_markers_csv_cleaned(self, filepath: Path, cleaned_markers: List[MarkerEvent]):
        """儲存清理後的事件標記為 CSV"""
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 寫入標頭
            writer.writerow(['timestamp', 'marker_text'])
            
            # 寫入清理後的數據
            for marker in cleaned_markers:
                writer.writerow([
                    f"{marker.timestamp:.6f}",
                    marker.marker_text
                ])
    
    def _save_ink_data_csv_raw(self, filepath: Path):
        """儲存原始墨水數據為 CSV（添加顏色欄位）"""
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 寫入標頭（添加 color）
            writer.writerow([
                'timestamp', 'x', 'y', 'pressure',
                'tilt_x', 'tilt_y', 'velocity',
                'stroke_id', 'event_type', 'color'  # 🆕 添加 color
            ])
            
            # 寫入原始數據
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
                    sample.event_type,
                    sample.color  # 🆕 添加顏色
                ])

    
    def _save_markers_csv_raw(self, filepath: Path):
        """儲存原始事件標記為 CSV（調試用）"""
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 寫入標頭
            writer.writerow(['timestamp', 'marker_text'])
            
            # 寫入原始數據
            for marker in self.markers:
                writer.writerow([
                    f"{marker.timestamp:.6f}",
                    marker.marker_text
                ])
    
    def _save_metadata_with_cleaning_stats(self, filepath: Path, cleaning_stats: Dict):
        """儲存包含清理統計的元數據"""
        # 添加清理統計到元數據
        self.metadata['data_cleaning'] = {
            'removed_markers': cleaning_stats.get('removed_markers', 0),
            'removed_ink_samples': cleaning_stats.get('removed_ink_samples', 0),
            'removal_by_reason': cleaning_stats.get('removal_by_reason', {}),
            'duplicate_stroke_starts_removed': cleaning_stats.get('duplicate_stroke_starts_removed', 0),  # 🆕
            'cleaning_enabled': True,
            'cleaning_method': 'time_range_based_extended_with_deduplication',  # 🆕
            'cleaning_rules': [
                'Remove duplicate stroke_start_X markers (keep first occurrence)',  # 🆕
                'stroke_start → tool_switch|from:pen|to:eraser (delete by time range)',
                'stroke_start → tool_switch|from:pen|to:pen (delete by time range)'
            ],
            'cleaning_timestamp': datetime.now().isoformat()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2)

    
    def _save_summary_with_cleaning_stats(self, filepath: Path, 
                                         cleaned_markers: List[MarkerEvent], 
                                         cleaned_ink_samples: List[InkSample],
                                         cleaning_stats: Dict):
        """儲存包含清理統計的摘要"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("LSL Recording Summary (Extended Time-Range Based Cleaned Data)\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"Session ID: {self.session_id}\n")
            f.write(f"Recording Start: {self.metadata['recording_start']}\n")
            f.write(f"Recording End: {self.metadata['recording_end']}\n")
            f.write(f"Duration: {self.metadata['recording_duration']:.2f} seconds\n\n")
            
            # 🆕🆕🆕 擴展清理統計
            removal_reasons = cleaning_stats.get('removal_by_reason', {})
            
            f.write("Data Cleaning Summary:\n")
            f.write(f"  Cleaning Method: Time-Range Based (Extended)\n")
            f.write(f"  Cleaning Rules:\n")
            f.write(f"    1. stroke_start → tool_switch|from:pen|to:eraser (delete by time range)\n")
            f.write(f"    2. stroke_start → tool_switch|from:pen|to:pen (delete by time range)\n")
            f.write(f"  Original Markers: {len(self.markers)}\n")
            f.write(f"  Cleaned Markers: {len(cleaned_markers)}\n")
            f.write(f"  Removed Markers: {cleaning_stats.get('removed_markers', 0)}\n")
            f.write(f"  Original Ink Samples: {len(self.ink_samples)}\n")
            f.write(f"  Cleaned Ink Samples: {len(cleaned_ink_samples)}\n")
            f.write(f"  Removed Ink Samples: {cleaning_stats.get('removed_ink_samples', 0)}\n")
            f.write(f"    • pen→eraser: {removal_reasons.get('pen→eraser', 0)} samples\n")
            f.write(f"    • pen→pen: {removal_reasons.get('pen→pen', 0)} samples\n\n")
            
            f.write(f"Final Data Counts:\n")
            f.write(f"  Total Ink Samples: {len(cleaned_ink_samples)}\n")
            f.write(f"  Total Markers: {len(cleaned_markers)}\n\n")
            
            # 計算統計資訊（使用清理後的數據）
            if len(cleaned_ink_samples) > 0:
                timestamps = [s.timestamp for s in cleaned_ink_samples]
                pressures = [s.pressure for s in cleaned_ink_samples]
                
                f.write("Cleaned Ink Data Statistics:\n")
                f.write(f"  Time range: {min(timestamps):.3f} - {max(timestamps):.3f} s\n")
                f.write(f"  Average sampling rate: {len(cleaned_ink_samples) / (max(timestamps) - min(timestamps)):.1f} Hz\n")
                f.write(f"  Pressure range: {min(pressures):.3f} - {max(pressures):.3f}\n")
                f.write(f"  Average pressure: {np.mean(pressures):.3f}\n\n")
            
            # 列出所有清理後的標記
            if len(cleaned_markers) > 0:
                f.write("Event Markers (Extended Time-Range Based Cleaned):\n")
                for marker in cleaned_markers:
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
            'total_markers': len(self.markers),
            'cleaning_method': 'time_range_based_extended',
            'cleaning_rules': [
                'stroke_start → tool_switch|from:pen|to:eraser (delete by time range)',
                'stroke_start → tool_switch|from:pen|to:pen (delete by time range)'
            ]
        }
        
        if self.recording_start_time:
            stats['recording_duration'] = time.time() - self.recording_start_time
        
        return stats