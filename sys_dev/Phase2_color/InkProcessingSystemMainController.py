import threading
import time
import queue
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
import json
import logging
from Config import ProcessingConfig
from BufferManager import BufferManager
from RawDataCollector import RawDataCollector
from PointProcessor import PointProcessor
from StrokeDetector import StrokeDetector
from FeatureCalculator import FeatureCalculator
from DigitalInkDataStructure import RawInkPoint, StrokeState

class InkProcessingSystem:
    """
    數位墨水處理系統主控制器

    負責協調所有模組的工作，提供統一的API介面
    """

    def __init__(self, config: ProcessingConfig):
        """
        初始化墨水處理系統

        Args:
            config: 系統配置參數
        """
        self.config = config
        self.is_running = False
        self.is_processing = False

        # 初始化各個模組
        self.buffer_manager = BufferManager(config)
        self.raw_collector = RawDataCollector(config)
        self.point_processor = PointProcessor(config)
        self.stroke_detector = StrokeDetector(config)
        self.feature_calculator = FeatureCalculator(config)

        # 創建數據緩衝區
        self.raw_point_buffer = self.buffer_manager.create_point_buffer(10000)
        self.processed_point_buffer = self.buffer_manager.create_point_buffer(10000)
        self.stroke_buffer = self.buffer_manager.create_stroke_buffer(1000)
        # 🆕🆕🆕 添加鎖來保護 StrokeDetector 的狀態
        self._stroke_detector_lock = threading.Lock()

        # 處理執行緒
        self.processing_threads = []
        self.stop_event = threading.Event()

        # 回調函數
        self.callbacks = {
            'on_stroke_completed': None,
            'on_features_calculated': None,
            'on_error': None,
            'on_status_update': None,
            'on_point_processed': None
        }

        # 統計資訊
        self.processing_stats = {
            'total_raw_points': 0,
            'total_processed_points': 0,
            'total_strokes': 0,
            'total_features': 0,
            'processing_start_time': None,
            'last_activity_time': None
        }

        # 設置日誌
        self._setup_logging()

        # 🆕🆕🆕 時間源管理
        self._time_source = None  # 外部時間源（如 LSL）
        self._use_external_time = False  # 是否使用外部時間
    def set_time_source(self, time_source_func: Optional[Callable[[], float]]):
        """
        設置外部時間源（如 LSL 時間）
        
        Args:
            time_source_func: 返回時間戳的函數（如 lsl.stream_manager.get_stream_time）
        """
        if time_source_func is not None:
            self._time_source = time_source_func
            self._use_external_time = True
            self.logger.info("✅ 已設置外部時間源（LSL 時間）")
        else:
            self._time_source = None
            self._use_external_time = False
            self.logger.info("⚠️ 已移除外部時間源，回退到系統時間")

    def _get_timestamp(self) -> float:
        """
        獲取時間戳（優先使用外部時間源）
        
        Returns:
            float: 時間戳
        """
        if self._use_external_time and self._time_source is not None:
            try:
                return self._time_source()
            except Exception as e:
                self.logger.warning(f"⚠️ 外部時間源失敗，回退到系統時間: {e}")
                return time.time()
        else:
            return time.time()

    def _setup_logging(self):
        """設置系統日誌"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('InkProcessingSystem')

    def initialize(self, device_config: Dict[str, Any]) -> bool:
        """
        初始化系統

        Args:
            device_config: 設備配置參數

        Returns:
            bool: 初始化是否成功
        """
        try:
            self.logger.info("Initializing ink processing system...")

            # 初始化原始數據收集器
            if not self.raw_collector.initialize_device(device_config):
                self.logger.error("Failed to initialize raw data collector")
                return False

            # 初始化點處理器
            if not self.point_processor.initialize():
                self.logger.error("Failed to initialize point processor")
                return False

            # 初始化筆劃檢測器
            if not self.stroke_detector.initialize():
                self.logger.error("Failed to initialize stroke detector")
                return False

            # 初始化特徵計算器
            if not self.feature_calculator.initialize():
                self.logger.error("Failed to initialize feature calculator")
                return False

            self.is_running = True
            self.logger.info("System initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"System initialization failed: {e}")
            return False

    def start_processing(self, callbacks: Optional[Dict[str, callable]] = None, use_external_input: bool = False) -> bool:
        """
        啟動處理管道
        
        Args:
            callbacks: 回調函數字典
            use_external_input: 是否使用外部輸入（PyQt5 集成模式）
            
        Returns:
            bool: 啟動是否成功
        """
        try:
            print("🚀🚀🚀 MainController start_processing 被調用！")
            self.logger.info("🚀🚀🚀 MainController start_processing 被調用！")
            
            if self.is_processing:
                self.logger.warning("Processing pipeline is already running")
                return False

            # 設置回調函數
            if callbacks:
                self.callbacks.update(callbacks)

            # 初始化處理開始時間
            self.processing_stats['processing_start_time'] = self._get_timestamp()
            self.processing_stats['last_activity_time'] = self._get_timestamp()


            # ✅ 修正：只在非外部輸入模式下啟動 RawDataCollector
            if not use_external_input:
                if not self.raw_collector.start_collection():
                    self.logger.error("Failed to start raw data collection")
                    return False
            else:
                self.logger.info("使用外部輸入模式，跳過 RawDataCollector")

            # 設置處理標誌
            self.is_processing = True
            self.stop_event.clear()

            print("🔍🔍🔍 準備啟動處理線程...")
            self.logger.info("🔍🔍🔍 準備啟動處理線程...")

            # ✅ 修正：根據輸入模式決定啟動哪些線程
            if use_external_input:
                # 外部輸入模式：不需要點處理循環（直接在 process_raw_point 中處理）
                self.processing_threads = [
                    threading.Thread(target=self._stroke_detection_loop, name="StrokeDetection"),
                    threading.Thread(target=self._feature_calculation_loop, name="FeatureCalculation"),
                    threading.Thread(target=self._status_monitoring_loop, name="StatusMonitoring")
                ]
            else:
                # 內部模擬模式：需要完整的處理鏈
                self.processing_threads = [
                    threading.Thread(target=self._point_processing_loop, name="PointProcessing"),
                    threading.Thread(target=self._stroke_detection_loop, name="StrokeDetection"),
                    threading.Thread(target=self._feature_calculation_loop, name="FeatureCalculation"),
                    threading.Thread(target=self._status_monitoring_loop, name="StatusMonitoring")
                ]

            for i, thread in enumerate(self.processing_threads):
                print(f"🔍 啟動線程 {i+1}: {thread.name}")
                self.logger.info(f"🔍 啟動線程 {i+1}: {thread.name}")
                thread.start()

            self.logger.info(f"Started {len(self.processing_threads)} processing threads")
            self.logger.info("Processing pipeline started successfully")

            return True

        except Exception as e:
            self.logger.error(f"Failed to start processing pipeline: {str(e)}")
            self.is_processing = False
            return False

# InkProcessingSystemMainController.py

    def process_raw_point(self, point_data: Dict[str, Any]) -> bool:
        """
        處理外部輸入的原始點（用於 PyQt5 集成）
        """
        try:
            # 轉換為 RawInkPoint
            raw_point = RawInkPoint(
                x=point_data['x'],
                y=point_data['y'],
                pressure=point_data.get('pressure', 0.5),
                tilt_x=point_data.get('tilt_x', 0),
                tilt_y=point_data.get('tilt_y', 0),
                twist=point_data.get('twist', 0),
                timestamp=point_data.get('timestamp', self._get_timestamp()),
                device_id='pyqt5_wacom',
                button_state=point_data.get('button_state', 0)
            )
            
            # ✅✅✅ 使用鎖保護整個處理流程
            with self._stroke_detector_lock:
                # 🔚 處理筆劃結束（壓力 = 0）
                if raw_point.pressure == 0.0:
                    if self.stroke_detector.current_state in [StrokeState.ACTIVE, StrokeState.STARTING, StrokeState.ENDING]:
                        self.logger.info(
                            f"🔚 檢測到筆離開屏幕（壓力=0），強制完成當前筆劃 "
                            f"(stroke_id={self.stroke_detector.current_stroke_id})"
                        )
                        
                        # ✅ 處理點
                        processed_point = self.point_processor.process_point(raw_point)
                        
                        if processed_point:
                            # ✅ 立即添加到檢測器並完成筆劃
                            self.stroke_detector.add_point(processed_point)
                            
                            # ✅ 立即獲取完成的筆劃並觸發回調
                            completed_strokes = self.stroke_detector.get_completed_strokes()
                            
                            for stroke_data in completed_strokes:
                                stroke_points = stroke_data['points']
                                stroke_id = stroke_data['stroke_id']
                                
                                # 加入筆劃緩衝區
                                self.stroke_buffer.append(stroke_data)
                                self.processing_stats['total_strokes'] += 1
                                
                                # 觸發筆劃完成回調
                                self._trigger_callback('on_stroke_completed', {
                                    'stroke_id': stroke_id,
                                    'points': stroke_points,
                                    'num_points': len(stroke_points),
                                    'start_time': stroke_data['start_time'],
                                    'end_time': stroke_data['end_time'],
                                    'timestamp': self._get_timestamp()
                                })
                                
                                # 觸發結束點回調
                                if stroke_points:
                                    last_point = stroke_points[-1]
                                    self._trigger_callback('on_point_processed', {
                                        'x': last_point.x,
                                        'y': last_point.y,
                                        'pressure': 0.0,
                                        'tilt_x': last_point.tilt_x,
                                        'tilt_y': last_point.tilt_y,
                                        'velocity': last_point.velocity,
                                        'timestamp': last_point.timestamp,
                                        'stroke_id': stroke_id,
                                        'is_stroke_start': False,
                                        'is_stroke_end': True
                                    })
                                
                                # 清空歷史緩存
                                if hasattr(self.point_processor, 'clear_history'):
                                    self.point_processor.clear_history()
                            
                            self.processing_stats['total_raw_points'] += 1
                            self.processing_stats['total_processed_points'] += 1
                            self.processing_stats['last_activity_time'] = self._get_timestamp()
                    
                    return True
                
                # ✅ 處理壓力 > 0 的點（正常流程）
                processed_point = self.point_processor.process_point(raw_point)
                
                if processed_point is None:
                    self.logger.debug(
                        f"點被過濾: pressure={raw_point.pressure:.3f} < "
                        f"threshold={self.config.pressure_threshold}"
                    )
                    return False
                
                # ✅ 立即添加到檢測器
                old_points_count = len(self.stroke_detector.current_stroke_points)
                self.stroke_detector.add_point(processed_point)
                
                # ✅ 判斷是否為筆劃開始
                is_stroke_start = (old_points_count == 0 and 
                                len(self.stroke_detector.current_stroke_points) == 1)
                
                # ✅ 更新 point 的 stroke_id
                processed_point.stroke_id = self.stroke_detector.current_stroke_id
                
                # ✅ 觸發回調
                self._trigger_callback('on_point_processed', {
                    'x': processed_point.x,
                    'y': processed_point.y,
                    'pressure': processed_point.pressure,
                    'tilt_x': processed_point.tilt_x,
                    'tilt_y': processed_point.tilt_y,
                    'velocity': processed_point.velocity,
                    'timestamp': processed_point.timestamp,
                    'stroke_id': processed_point.stroke_id,
                    'is_stroke_start': is_stroke_start,
                    'is_stroke_end': False
                })
                
                self.processing_stats['total_raw_points'] += 1
                self.processing_stats['total_processed_points'] += 1
                self.processing_stats['last_activity_time'] = self._get_timestamp()
                
                return True
                
        except Exception as e:
            self.logger.error(f"處理外部點失敗: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False



    def _point_processing_loop(self):
        """點處理主循環"""
        print("🎯🎯🎯 _point_processing_loop 線程已啟動！")
        self.logger.info("🎯🎯🎯 _point_processing_loop 線程已啟動！")
        
        self.logger.info("Point processing loop started")

        while self.is_processing and not self.stop_event.is_set():
            try:
                print("🔍 嘗試獲取原始數據點...")
                self.logger.info("🔍 嘗試獲取原始數據點...")
                
                # 從原始數據收集器獲取數據
                raw_points = self.raw_collector.get_raw_points(timeout=0.1)

                self.logger.info(f"🔍 獲取到 {len(raw_points) if raw_points else 0} 個原始點")
                
                if not raw_points:
                    self.logger.info("🔍 沒有獲取到數據，繼續等待...")
                    continue

                self.logger.info(f"✅ 開始處理 {len(raw_points)} 個點")

                # 批量處理點
                for i, raw_point in enumerate(raw_points):
                    self.logger.info(f"🔍 處理第 {i+1} 個點: pressure={raw_point.pressure:.3f}")
                    
                    processed_point = self.point_processor.process_point(raw_point)

                    if processed_point:
                        self.logger.info(f"✅ 點處理成功")
                        # 加入處理後的點緩衝區
                        try:
                            self.processed_point_buffer.put_nowait(processed_point)
                            self.processing_stats['total_processed_points'] += 1
                            self.processing_stats['last_activity_time'] = self._get_timestamp()
                        except queue.Full:
                            # 緩衝區滿，丟棄最舊的點
                            try:
                                self.processed_point_buffer.get_nowait()
                                self.processed_point_buffer.put_nowait(processed_point)
                            except queue.Empty:
                                pass
                    else:
                        self.logger.info(f"❌ 點處理失敗")

                self.processing_stats['total_raw_points'] += len(raw_points)
                self.logger.info(f"📊 統計更新: 總原始點={self.processing_stats['total_raw_points']}, "
                                f"總處理點={self.processing_stats['total_processed_points']}")

            except Exception as e:
                self.logger.error(f"Point processing error: {e}")
                import traceback
                self.logger.error(f"詳細錯誤: {traceback.format_exc()}")
                self._trigger_callback('on_error', {
                    'error_type': 'point_processing_error',
                    'message': str(e),
                    'timestamp': self._get_timestamp()
                })

        self.logger.info("Point processing loop ended")


    def _stroke_detection_loop(self):
        """筆劃檢測主循環"""
        self.logger.info("Stroke detection loop started")

        while self.is_processing and not self.stop_event.is_set():
            try:
                # 嘗試獲取新點
                point = None
                try:
                    point = self.processed_point_buffer.get(timeout=0.05)
                except queue.Empty:
                    pass
                
                # 如果有新點，添加到檢測器
                if point is not None:
                    # ✅✅✅ 記錄處理前的狀態
                    old_stroke_id = self.stroke_detector.current_stroke_id
                    old_state = self.stroke_detector.current_state
                    old_points_count = len(self.stroke_detector.current_stroke_points)  # ← 新增
                    
                    # 將點添加到筆劃檢測器
                    self.stroke_detector.add_point(point)
                    
                    # ✅✅✅ 修改判斷邏輯：使用 current_points 來判斷
                    # 如果處理前點數為 0，處理後點數為 1，說明這是筆劃的第一個點
                    is_stroke_start = (old_points_count == 0 and 
                                    len(self.stroke_detector.current_stroke_points) == 1)
                    
                    # ✅ 更新 point 的 stroke_id
                    point.stroke_id = self.stroke_detector.current_stroke_id
                    
                    # ✅ 觸發回調，包含 is_stroke_start 標記
                    self._trigger_callback('on_point_processed', {
                        'x': point.x,
                        'y': point.y,
                        'pressure': point.pressure,
                        'tilt_x': point.tilt_x,
                        'tilt_y': point.tilt_y,
                        'velocity': point.velocity,
                        'timestamp': point.timestamp,
                        'stroke_id': point.stroke_id,
                        'is_stroke_start': is_stroke_start,  # ← 使用新邏輯
                        'is_stroke_end': False
                    })

                # 檢查完成的筆劃
                completed_strokes = self.stroke_detector.get_completed_strokes()
                
                if completed_strokes:
                    self.logger.info(f"🔍🔍🔍 檢測到 {len(completed_strokes)} 個完成的筆劃")
                
                for stroke_data in completed_strokes:
                    stroke_points = stroke_data['points']
                    stroke_id = stroke_data['stroke_id']
                    
                    self.logger.info(f"🔍 處理完成的筆劃: stroke_id={stroke_id}, points={len(stroke_points)}")
                    
                    # ✅✅✅ 為筆劃的最後一個點觸發 stroke_end 事件（壓力設為 0）
                    if stroke_points:
                        last_point = stroke_points[-1]
                        self._trigger_callback('on_point_processed', {
                            'x': last_point.x,
                            'y': last_point.y,
                            'pressure': 0.0,  # ✅ 關鍵修改：壓力設為 0
                            'tilt_x': last_point.tilt_x,
                            'tilt_y': last_point.tilt_y,
                            'velocity': last_point.velocity,
                            'timestamp': last_point.timestamp,
                            'stroke_id': stroke_id,  # ✅ 使用正確的 stroke_id
                            'is_stroke_start': False,
                            'is_stroke_end': True  # ✅ 筆劃結束標記
                        })
                        # 🆕🆕🆕 清空 PointProcessor 的歷史緩存
                        if hasattr(self.point_processor, 'clear_history'):
                            self.point_processor.clear_history()
                            self.logger.debug(f"🧹 筆劃 {stroke_id} 結束，已清空歷史緩存")

                    
                    # 加入筆劃緩衝區
                    self.stroke_buffer.append(stroke_data)
                    self.processing_stats['total_strokes'] += 1

                    # 觸發筆劃完成回調
                    self._trigger_callback('on_stroke_completed', {
                        'stroke_id': stroke_id,
                        'points': stroke_points,
                        'num_points': len(stroke_points),
                        'start_time': stroke_data['start_time'],
                        'end_time': stroke_data['end_time'],
                        'timestamp': self._get_timestamp()
                    })
                
                # 如果沒有新點也沒有完成的筆劃，短暫休眠
                if point is None and not completed_strokes:
                    time.sleep(0.01)

            except Exception as e:
                self.logger.error(f"Stroke detection error: {e}")
                import traceback
                self.logger.error(f"詳細錯誤: {traceback.format_exc()}")

        self.logger.info("Stroke detection loop ended")



    def _feature_calculation_loop(self):
        """
        特徵計算主循環
        ✅✅✅ 方案 2：移除 feature_buffer，直接調用回調
        """
        self.logger.info("Feature calculation loop started")

        while self.is_processing and not self.stop_event.is_set():
            try:
                # 檢查是否有新的筆劃需要計算特徵
                if len(self.stroke_buffer) == 0:
                    time.sleep(0.1)
                    continue

                # 獲取最新的筆劃
                stroke_data = self.stroke_buffer.popleft()
                
                # 提取點列表
                stroke_points = stroke_data['points']
                stroke_id = stroke_data['stroke_id']
                
                self.logger.info(f"🔍 開始計算特徵: stroke_id={stroke_id}, points={len(stroke_points)}")

                # 計算特徵
                features = self.feature_calculator.calculate_features(stroke_points)
                
                if features:
                    self.logger.info(f"✅ 特徵計算成功: stroke_id={stroke_id}")
                    
                    # ✅✅✅ 直接調用回調函數（不使用 feature_buffer）
                    self._trigger_callback('on_features_calculated', {
                        'stroke_id': stroke_id,
                        'features': features,
                        'timestamp': self._get_timestamp()
                    })
                    
                    # ✅ 更新統計
                    self.processing_stats['total_features'] += 1
                    self.logger.info(f"✅ 特徵處理完成，當前總特徵數: {self.processing_stats['total_features']}")
                    
                else:
                    self.logger.warning(f"⚠️ 特徵計算失敗: stroke_id={stroke_id}")

            except Exception as e:
                self.logger.error(f"Feature calculation error: {e}")
                import traceback
                self.logger.error(f"詳細錯誤: {traceback.format_exc()}")
                self._trigger_callback('on_error', {
                    'error_type': 'feature_calculation_error',
                    'message': str(e),
                    'timestamp': self._get_timestamp()
                })

        self.logger.info("Feature calculation loop ended")

    def _status_monitoring_loop(self):
        """狀態監控主循環"""
        self.logger.info("Status monitoring loop started")

        last_report_time = self._get_timestamp()

        while self.is_processing and not self.stop_event.is_set():
            try:
                current_time = self._get_timestamp()

                # 每5秒報告一次狀態
                if current_time - last_report_time >= 5.0:
                    stats = self.get_processing_statistics()

                    self.logger.info(f"Processing Status: "
                                     f"Raw Points: {stats['total_raw_points']}, "
                                     f"Processed Points: {stats['total_processed_points']}, "
                                     f"Strokes: {stats['total_strokes']}, "
                                     f"Features: {stats['total_features']}")

                    # 觸發狀態更新回調
                    self._trigger_callback('on_status_update', {
                        'status': 'processing_update',
                        'statistics': stats,
                        'timestamp': current_time
                    })

                    last_report_time = current_time

                time.sleep(1.0)

            except Exception as e:
                self.logger.error(f"Status monitoring error: {e}")

        self.logger.info("Status monitoring loop ended")

    def stop_processing(self):
        """停止處理流程"""
        if not self.is_processing:
            self.logger.warning("Processing not started")
            return

        self.logger.info("Stopping processing pipeline...")

        # ✅✅✅ 修復：直接丟棄未完成的筆劃
        try:
            if (hasattr(self, 'stroke_detector') and 
                self.stroke_detector is not None and
                hasattr(self.stroke_detector, 'current_stroke_points') and
                self.stroke_detector.current_stroke_points):
                
                num_points = len(self.stroke_detector.current_stroke_points)
                self.logger.info(f"⚠️ 停止時丟棄未完成的筆劃 (包含 {num_points} 個點)")
                
                # ✅ 清空當前筆劃
                self.stroke_detector.current_stroke_points = []
                self.stroke_detector.current_state = StrokeState.IDLE
                
            else:
                self.logger.debug("沒有未完成的筆劃需要處理")
        except Exception as e:
            self.logger.error(f"清理未完成筆劃時發生錯誤: {str(e)}")
            import traceback
            self.logger.error(f"詳細錯誤: {traceback.format_exc()}")

        # 設置停止標誌
        self.is_processing = False
        self.stop_event.set()

        # 停止原始數據收集
        self.raw_collector.stop_collection()

        # 等待所有處理執行緒結束
        for thread in self.processing_threads:
            if thread.is_alive():
                thread.join(timeout=2.0)

        self.processing_threads.clear()

        # 觸發狀態更新回調
        self._trigger_callback('on_status_update', {
            'status': 'processing_stopped',
            'timestamp': self._get_timestamp()
        })

        self.logger.info("Processing pipeline stopped")

    def shutdown(self):
        """關閉系統"""
        self.logger.info("Shutting down ink processing system...")

        # 停止處理
        if self.is_processing:
            self.stop_processing()

        # 關閉各個模組
        if hasattr(self.raw_collector, 'shutdown'):
            self.raw_collector.shutdown()

        if hasattr(self.point_processor, 'shutdown'):
            self.point_processor.shutdown()

        if hasattr(self.stroke_detector, 'shutdown'):
            self.stroke_detector.shutdown()

        if hasattr(self.feature_calculator, 'shutdown'):
            self.feature_calculator.shutdown()

        self.is_running = False
        self.logger.info("System shutdown complete")

    def register_callback(self, event_type: str, callback: Callable):
        """
        註冊事件回調函數

        Args:
            event_type: 事件類型 ('on_stroke_completed', 'on_features_calculated', 'on_error', 'on_status_update', 'on_point_processed')
            callback: 回調函數
        """
        if event_type in self.callbacks:
            self.callbacks[event_type] = callback
            self.logger.info(f"已註冊回調: {event_type}")
        else:
            self.logger.warning(f"Unknown event type: {event_type}")

    def _trigger_callback(self, event_type: str, data: Any):
        """觸發回調函數"""
        if event_type in self.callbacks and self.callbacks[event_type]:
            try:
                self.callbacks[event_type](data)
            except Exception as e:
                self.logger.error(f"Callback error for {event_type}: {e}")

    def get_processing_statistics(self) -> Dict[str, Any]:
        """獲取處理統計資訊"""
        current_time = self._get_timestamp()
        
        # 🔧 修復：安全獲取開始時間
        start_time = self.processing_stats.get('processing_start_time')
        if start_time is None:
            # 如果沒有設置開始時間，使用當前時間
            start_time = current_time
            self.processing_stats['processing_start_time'] = start_time
        
        duration = current_time - start_time

        stats = self.processing_stats.copy()
        stats['processing_duration'] = duration
        stats['raw_points_per_second'] = stats['total_raw_points'] / duration if duration > 0 else 0
        stats['processed_points_per_second'] = stats['total_processed_points'] / duration if duration > 0 else 0
        stats['strokes_per_minute'] = stats['total_strokes'] / (duration / 60) if duration > 0 else 0

        # ✅✅✅ 緩衝區狀態（移除 feature_buffer）
        stats['buffer_status'] = {
            'raw_points': self.raw_collector.get_buffer_size() if hasattr(self.raw_collector, 'get_buffer_size') else 0,
            'processed_points': self.processed_point_buffer.qsize(),
            'strokes': len(self.stroke_buffer)
            # ✅ 移除 'features': self.feature_buffer.qsize()
        }

        return stats

    def _clear_all_buffers(self):
        """清空所有緩衝區"""
        # 清空點緩衝區
        while not self.processed_point_buffer.empty():
            try:
                self.processed_point_buffer.get_nowait()
            except queue.Empty:
                break

        # 清空筆劃緩衝區
        self.stroke_buffer.clear()

        # ✅✅✅ 移除清空 feature_buffer 的代碼
        # while not self.feature_buffer.empty():
        #     try:
        #         self.feature_buffer.get_nowait()
        #     except queue.Empty:
        #         break

    def get_latest_features(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        獲取最新的特徵數據
        ✅✅✅ 注意：由於移除了 feature_buffer，此方法不再可用
        建議使用回調函數 on_features_calculated 來獲取特徵

        Args:
            count: 要獲取的特徵數量

        Returns:
            List[Dict[str, Any]]: 空列表（功能已移除）
        """
        self.logger.warning("get_latest_features() 已棄用，請使用 on_features_calculated 回調")
        return []
