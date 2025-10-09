"""
LSL Integration Module

整合 LSL 串流管理器和數據記錄器到墨水處理系統
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from LSLStreamManager import LSLStreamManager, LSLStreamConfig
from LSLDataRecorder import LSLDataRecorder


class LSLIntegration:
    """
    LSL 整合模組
    
    提供簡化的 API 來管理 LSL 串流和數據記錄
    """
    
    def __init__(self, 
                 stream_config: Optional[LSLStreamConfig] = None,
                 output_dir: str = "./lsl_recordings"):
        """
        初始化 LSL 整合模組
        
        Args:
            stream_config: LSL 串流配置（如果為 None，使用預設配置）
            output_dir: 數據輸出目錄
        """
        self.logger = logging.getLogger('LSLIntegration')
        
        # 使用預設配置或自訂配置
        if stream_config is None:
            stream_config = LSLStreamConfig()
        
        # 初始化模組
        self.stream_manager = LSLStreamManager(stream_config)
        self.data_recorder = LSLDataRecorder(output_dir)
        
        # 狀態
        self.is_active = False
        self.current_stroke_id = 0
        self.current_session_id = None
    
    def start(self, session_id: Optional[str] = None, metadata: Optional[Dict] = None) -> bool:
        """
        啟動 LSL 串流和數據記錄
        
        Args:
            session_id: 會話 ID（如果為 None，自動生成）
            metadata: 額外的元數據
        
        Returns:
            bool: 是否成功啟動
        """
        try:
            self.logger.info("Starting LSL integration...")
            
            # 初始化串流
            if not self.stream_manager.initialize_streams():
                self.logger.error("Failed to initialize LSL streams")
                return False
            
            # 開始記錄
            self.current_session_id = self.data_recorder.start_recording(session_id, metadata)
            
            # 發送開始標記
            timestamp = self.stream_manager.get_stream_time()
            self.stream_manager.push_marker("recording_start", timestamp)
            self.data_recorder.record_marker(timestamp, "recording_start")
            
            self.is_active = True
            self.current_stroke_id = 0
            
            self.logger.info(f"LSL integration started: session_id={self.current_session_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start LSL integration: {e}")
            return False
    
    def process_ink_point(self,
                         x: float,
                         y: float,
                         pressure: float,
                         tilt_x: float = 0.0,
                         tilt_y: float = 0.0,
                         velocity: float = 0.0,
                         is_stroke_start: bool = False,
                         is_stroke_end: bool = False):
        """
        處理墨水點數據
        
        自動處理：
        - 事件類型判斷
        - 筆劃 ID 管理
        - 事件標記推送
        - 雙重記錄（串流 + 本地）
        
        Args:
            x, y: 座標
            pressure: 壓力
            tilt_x, tilt_y: 傾斜角度
            velocity: 速度
            is_stroke_start: 是否為筆劃開始
            is_stroke_end: 是否為筆劃結束
        """
        if not self.is_active:
            return
        
        try:
            # 獲取統一時間戳
            timestamp = self.stream_manager.get_stream_time()
            
            # 確定事件類型
            event_type = 0  # 正常點
            
            if is_stroke_start:
                self.current_stroke_id += 1
                event_type = 1
                # 推送筆劃開始標記
                marker = f"stroke_start_{self.current_stroke_id}"
                self.stream_manager.push_marker(marker, timestamp)
                self.data_recorder.record_marker(timestamp, marker)
                self.logger.debug(f"Stroke started: {self.current_stroke_id}")
                
            elif is_stroke_end:
                event_type = 2
                # 推送筆劃結束標記
                marker = f"stroke_end_{self.current_stroke_id}"
                self.stream_manager.push_marker(marker, timestamp)
                self.data_recorder.record_marker(timestamp, marker)
                self.logger.debug(f"Stroke ended: {self.current_stroke_id}")
            
            # 推送墨水數據到串流
            self.stream_manager.push_ink_sample(
                x=x,
                y=y,
                pressure=pressure,
                tilt_x=tilt_x,
                tilt_y=tilt_y,
                velocity=velocity,
                stroke_id=self.current_stroke_id,
                event_type=event_type,
                timestamp=timestamp
            )
            
            # 記錄到本地
            self.data_recorder.record_ink_sample(
                timestamp=timestamp,
                x=x,
                y=y,
                pressure=pressure,
                tilt_x=tilt_x,
                tilt_y=tilt_y,
                velocity=velocity,
                stroke_id=self.current_stroke_id,
                event_type=event_type
            )
            
        except Exception as e:
            self.logger.error(f"Error processing ink point: {e}")
    
    def mark_experiment_phase(self, phase_name: str):
        """
        標記實驗階段
        
        Args:
            phase_name: 階段名稱（例如："baseline_start", "task_start", "rest_start"）
        """
        if not self.is_active:
            self.logger.warning("Cannot mark phase: LSL integration not active")
            return
        
        try:
            timestamp = self.stream_manager.get_stream_time()
            marker = f"phase_{phase_name}"
            
            self.stream_manager.push_marker(marker, timestamp)
            self.data_recorder.record_marker(timestamp, marker)
            
            self.logger.info(f"Experiment phase marked: {phase_name}")
            
        except Exception as e:
            self.logger.error(f"Error marking experiment phase: {e}")
    
    def mark_custom_event(self, event_name: str, event_data: Optional[Dict] = None):
        """
        標記自訂事件
        
        Args:
            event_name: 事件名稱
            event_data: 事件相關數據（可選）
        """
        if not self.is_active:
            self.logger.warning("Cannot mark event: LSL integration not active")
            return
        
        try:
            timestamp = self.stream_manager.get_stream_time()
            
            # 構建標記文字
            if event_data:
                import json
                marker = f"{event_name}|{json.dumps(event_data)}"
            else:
                marker = event_name
            
            self.stream_manager.push_marker(marker, timestamp)
            self.data_recorder.record_marker(timestamp, marker)
            
            self.logger.info(f"Custom event marked: {event_name}")
            
        except Exception as e:
            self.logger.error(f"Error marking custom event: {e}")
    
    def pause_recording(self):
        """
        暫停記錄（但保持串流）
        """
        if not self.is_active:
            return
        
        try:
            timestamp = self.stream_manager.get_stream_time()
            self.stream_manager.push_marker("recording_paused", timestamp)
            self.data_recorder.record_marker(timestamp, "recording_paused")
            self.logger.info("Recording paused")
            
        except Exception as e:
            self.logger.error(f"Error pausing recording: {e}")
    
    def resume_recording(self):
        """
        恢復記錄
        """
        if not self.is_active:
            return
        
        try:
            timestamp = self.stream_manager.get_stream_time()
            self.stream_manager.push_marker("recording_resumed", timestamp)
            self.data_recorder.record_marker(timestamp, "recording_resumed")
            self.logger.info("Recording resumed")
            
        except Exception as e:
            self.logger.error(f"Error resuming recording: {e}")
    
    def get_recording_stats(self) -> Dict[str, Any]:
        """
        獲取當前記錄統計
        
        Returns:
            Dict: 統計資訊
        """
        if not self.is_active:
            return {
                'is_active': False,
                'message': 'LSL integration not active'
            }
        
        try:
            stats = self.data_recorder.get_recording_stats()
            stats['current_stroke_id'] = self.current_stroke_id
            stats['session_id'] = self.current_session_id
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting recording stats: {e}")
            return {'error': str(e)}
    
    def stop(self) -> Dict[str, str]:
        """
        停止 LSL 串流和數據記錄
        
        Returns:
            Dict: 儲存的檔案路徑
        """
        if not self.is_active:
            self.logger.warning("LSL integration is not active")
            return {}
        
        try:
            self.logger.info("Stopping LSL integration...")
            
            # 發送結束標記
            timestamp = self.stream_manager.get_stream_time()
            self.stream_manager.push_marker("recording_end", timestamp)
            self.data_recorder.record_marker(timestamp, "recording_end")
            
            # 關閉串流
            self.stream_manager.close_streams()
            
            # 停止記錄並儲存數據
            saved_files = self.data_recorder.stop_recording()
            
            self.is_active = False
            self.current_stroke_id = 0
            self.current_session_id = None
            
            self.logger.info(f"LSL integration stopped. Files saved: {len(saved_files)}")
            return saved_files
            
        except Exception as e:
            self.logger.error(f"Error stopping LSL integration: {e}")
            return {}
    
    def is_recording(self) -> bool:
        """
        檢查是否正在記錄
        
        Returns:
            bool: 是否正在記錄
        """
        return self.is_active
    
    def get_current_stroke_id(self) -> int:
        """
        獲取當前筆劃 ID
        
        Returns:
            int: 當前筆劃 ID
        """
        return self.current_stroke_id
    
    def get_session_id(self) -> Optional[str]:
        """
        獲取當前會話 ID
        
        Returns:
            Optional[str]: 會話 ID（如果未啟動則為 None）
        """
        return self.current_session_id
    
    def __enter__(self):
        """支援 context manager"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """支援 context manager"""
        self.stop()
        return False


# ============================================================================
# 使用範例
# ============================================================================

def example_basic_usage():
    """基本使用範例"""
    
    # 配置 LSL 串流
    config = LSLStreamConfig(
        device_manufacturer="Wacom",
        device_model="Wacom One 12",
        normalize_coordinates=True,
        screen_width=1920,
        screen_height=1080
    )
    
    # 初始化整合模組
    lsl = LSLIntegration(
        stream_config=config,
        output_dir="./my_experiments"
    )
    
    # 啟動
    lsl.start(
        session_id="P001_baseline_001",
        metadata={
            'participant_id': 'P001',
            'experiment_condition': 'baseline',
            'experimenter': 'Yu-Cheng'
        }
    )
    
    # 標記實驗階段
    lsl.mark_experiment_phase("baseline_start")
    
    # 模擬繪圖數據
    for i in range(100):
        lsl.process_ink_point(
            x=0.5 + i * 0.001,
            y=0.5 + i * 0.001,
            pressure=0.5,
            velocity=100.0,
            is_stroke_start=(i == 0),
            is_stroke_end=(i == 99)
        )
    
    # 標記階段結束
    lsl.mark_experiment_phase("baseline_end")
    
    # 獲取統計
    stats = lsl.get_recording_stats()
    print(f"Recording stats: {stats}")
    
    # 停止並儲存
    saved_files = lsl.stop()
    print(f"Saved files: {saved_files}")


def example_context_manager():
    """使用 context manager 的範例"""
    
    config = LSLStreamConfig(
        device_manufacturer="Wacom",
        device_model="Wacom One 12"
    )
    
    # 使用 with 語句自動管理啟動和停止
    with LSLIntegration(config, "./recordings") as lsl:
        lsl.mark_experiment_phase("task_start")
        
        # 處理數據
        for i in range(50):
            lsl.process_ink_point(
                x=i * 0.01,
                y=i * 0.01,
                pressure=0.5
            )
        
        lsl.mark_experiment_phase("task_end")
    
    # 離開 with 區塊時自動調用 stop()
    print("Recording completed and saved")


def example_with_ink_processing_system():
    """
    與 InkProcessingSystem 整合的範例
    
    這個範例展示如何將 LSL 整合到你的第一階段代碼中
    """
    from InkProcessingSystemMainController import InkProcessingSystem
    from Config import ProcessingConfig
    
    # 初始化墨水處理系統
    ink_config = ProcessingConfig(
        sampling_rate=200.0,
        buffer_size=10000
    )
    ink_system = InkProcessingSystem(ink_config)
    
    # 初始化 LSL 整合
    lsl_config = LSLStreamConfig(
        device_manufacturer="Wacom",
        device_model="Wacom One 12",
        ink_sampling_rate=ink_config.sampling_rate
    )
    lsl = LSLIntegration(lsl_config, "./recordings")
    
    # 啟動兩個系統
    ink_system.initialize()
    lsl.start(
        session_id="experiment_001",
        metadata={'experiment': 'drawing_task'}
    )
    
    # 註冊回調函數：當點處理完成時，推送到 LSL
    def on_point_processed(point_data):
        lsl.process_ink_point(
            x=point_data['x'],
            y=point_data['y'],
            pressure=point_data['pressure'],
            tilt_x=point_data.get('tilt_x', 0),
            tilt_y=point_data.get('tilt_y', 0),
            velocity=point_data.get('velocity', 0),
            is_stroke_start=point_data.get('is_stroke_start', False),
            is_stroke_end=point_data.get('is_stroke_end', False)
        )
    
    ink_system.register_callback('on_point_processed', on_point_processed)
    
    # 註冊筆劃事件回調
    def on_stroke_completed(stroke_data):
        print(f"Stroke {stroke_data['stroke_id']} completed")
    
    ink_system.register_callback('on_stroke_completed', on_stroke_completed)
    
    # 開始處理（這裡應該連接到實際的 Wacom 輸入）
    ink_system.start_processing()
    
    # ... 處理數據 ...
    
    # 停止兩個系統
    ink_system.stop_processing()
    saved_files = lsl.stop()
    
    print(f"Data saved to: {saved_files}")


def example_experiment_phases():
    """實驗階段管理範例"""
    
    lsl = LSLIntegration(output_dir="./experiment_data")
    lsl.start(
        session_id="P001_full_experiment",
        metadata={
            'participant_id': 'P001',
            'age': 25,
            'handedness': 'right'
        }
    )
    
    # 基線期
    lsl.mark_experiment_phase("baseline_start")
    # ... 收集基線數據 ...
    lsl.mark_experiment_phase("baseline_end")
    
    # 任務期
    lsl.mark_experiment_phase("task_start")
    lsl.mark_custom_event("stimulus_presented", {'stimulus_id': 'A1'})
    # ... 執行任務 ...
    lsl.mark_custom_event("response_recorded", {'response': 'correct'})
    lsl.mark_experiment_phase("task_end")
    
    # 休息期
    lsl.mark_experiment_phase("rest_start")
    lsl.pause_recording()  # 暫停記錄
    # ... 休息 ...
    lsl.resume_recording()  # 恢復記錄
    lsl.mark_experiment_phase("rest_end")
    
    # 結束
    saved_files = lsl.stop()
    print(f"Experiment completed. Data saved to: {saved_files}")


if __name__ == "__main__":
    # 設定日誌
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 70)
    print("LSL Integration Examples")
    print("=" * 70)
    
    print("\n1. Basic Usage Example:")
    print("-" * 70)
    example_basic_usage()
    
    print("\n2. Context Manager Example:")
    print("-" * 70)
    example_context_manager()
    
    print("\n3. Experiment Phases Example:")
    print("-" * 70)
    example_experiment_phases()
    
    print("\n" + "=" * 70)
    print("All examples completed!")
    print("=" * 70)
