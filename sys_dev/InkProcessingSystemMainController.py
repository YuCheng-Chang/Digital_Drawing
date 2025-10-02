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
        self.feature_buffer = queue.Queue(maxsize=500)

        # 處理執行緒
        self.processing_threads = []
        self.stop_event = threading.Event()

        # 回調函數
        self.callbacks = {
            'on_stroke_completed': [],
            'on_features_calculated': [],
            'on_error': [],
            'on_status_update': []
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

    def start_processing(self, callbacks: Optional[Dict[str, callable]] = None) -> bool:
        """
        啟動處理管道
        
        Args:
            callbacks: 回調函數字典
            
        Returns:
            bool: 啟動是否成功
        """
        try:
            # 🔍 添加明顯的調試輸出
            print("🚀🚀🚀 MainController start_processing 被調用！")
            self.logger.info("🚀🚀🚀 MainController start_processing 被調用！")
            
            if self.is_processing:
                self.logger.warning("Processing pipeline is already running")
                return False

            # 設置回調函數
            if callbacks:
                self.callbacks.update(callbacks)

            # 🔧 修復：初始化處理開始時間
            self.processing_stats['processing_start_time'] = time.time()
            self.processing_stats['last_activity_time'] = time.time()

            # 啟動原始數據收集
            if not self.raw_collector.start_collection():
                self.logger.error("Failed to start raw data collection")
                return False

            # 設置處理標誌
            self.is_processing = True
            self.stop_event.clear()

            # 🔍 添加線程啟動調試
            print("🔍🔍🔍 準備啟動處理線程...")
            self.logger.info("🔍🔍🔍 準備啟動處理線程...")

            # 啟動處理線程
            self.processing_threads = [
                threading.Thread(target=self._point_processing_loop, name="PointProcessing"),
                threading.Thread(target=self._stroke_detection_loop, name="StrokeDetection"),
                threading.Thread(target=self._feature_calculation_loop, name="FeatureCalculation"),
                threading.Thread(target=self._status_monitoring_loop, name="StatusMonitoring")
            ]

            # 🔍 添加每個線程的啟動調試
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

    def _start_processing_threads(self):
        """啟動所有處理執行緒"""

        # 點處理執行緒
        point_thread = threading.Thread(
            target=self._point_processing_loop,
            name="PointProcessing"
        )
        point_thread.daemon = True
        self.processing_threads.append(point_thread)
        point_thread.start()

        # 筆劃檢測執行緒
        stroke_thread = threading.Thread(
            target=self._stroke_detection_loop,
            name="StrokeDetection"
        )
        stroke_thread.daemon = True
        self.processing_threads.append(stroke_thread)
        stroke_thread.start()

        # 特徵計算執行緒
        feature_thread = threading.Thread(
            target=self._feature_calculation_loop,
            name="FeatureCalculation"
        )
        feature_thread.daemon = True
        self.processing_threads.append(feature_thread)
        feature_thread.start()

        # 狀態監控執行緒
        monitor_thread = threading.Thread(
            target=self._status_monitoring_loop,
            name="StatusMonitoring"
        )
        monitor_thread.daemon = True
        self.processing_threads.append(monitor_thread)
        monitor_thread.start()

        self.logger.info(f"Started {len(self.processing_threads)} processing threads")

    def _point_processing_loop(self):
        """點處理主循環"""
        # 🔍 線程入口調試 - 最重要！
        print("🎯🎯🎯 _point_processing_loop 線程已啟動！")
        self.logger.info("🎯🎯🎯 _point_processing_loop 線程已啟動！")
        
        self.logger.info("Point processing loop started")

        while self.is_processing and not self.stop_event.is_set():
            try:
                # 🔍 添加調試輸出
                print("🔍 嘗試獲取原始數據點...")
                self.logger.info("🔍 嘗試獲取原始數據點...")
                
                # 從原始數據收集器獲取數據
                raw_points = self.raw_collector.get_raw_points(timeout=0.1)

                # 🔍 調試輸出
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
                            self.processing_stats['last_activity_time'] = time.time()
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
                    'timestamp': time.time()
                })

        self.logger.info("Point processing loop ended")

    def _stroke_detection_loop(self):
        """筆劃檢測主循環"""
        self.logger.info("Stroke detection loop started")

        while self.is_processing and not self.stop_event.is_set():
            try:
                # 從處理後的點緩衝區獲取數據
                points_batch = []

                # 收集一批點進行處理
                for _ in range(50):  # 最多收集50個點
                    try:
                        point = self.processed_point_buffer.get(timeout=0.01)
                        points_batch.append(point)
                    except queue.Empty:
                        break

                if not points_batch:
                    continue

                # 將點添加到筆劃檢測器
                for point in points_batch:
                    self.stroke_detector.add_point(point)

                # 檢查是否有完成的筆劃
                completed_strokes = self.stroke_detector.get_completed_strokes()

                for stroke in completed_strokes:
                    # 加入筆劃緩衝區
                    self.stroke_buffer.append(stroke)
                    self.processing_stats['total_strokes'] += 1

                    # 觸發筆劃完成回調
                    self._trigger_callback('on_stroke_completed', {
                        'stroke': stroke,
                        'timestamp': time.time()
                    })

            except Exception as e:
                self.logger.error(f"Stroke detection error: {e}")
                self._trigger_callback('on_error', {
                    'error_type': 'stroke_detection_error',
                    'message': str(e),
                    'timestamp': time.time()
                })

        self.logger.info("Stroke detection loop ended")

    def _feature_calculation_loop(self):
        """特徵計算主循環"""
        self.logger.info("Feature calculation loop started")

        while self.is_processing and not self.stop_event.is_set():
            try:
                # 檢查是否有新的筆劃需要計算特徵
                if len(self.stroke_buffer) == 0:
                    time.sleep(0.1)
                    continue

                # 獲取最新的筆劃
                stroke = self.stroke_buffer.popleft()

                # 計算特徵
                features = self.feature_calculator.calculate_features(stroke)

                if features:
                    # 加入特徵緩衝區
                    try:
                        self.feature_buffer.put_nowait({
                            'stroke_id': stroke.stroke_id,
                            'features': features,
                            'timestamp': time.time()
                        })
                        self.processing_stats['total_features'] += 1

                        # 觸發特徵計算完成回調
                        self._trigger_callback('on_features_calculated', {
                            'stroke_id': stroke.stroke_id,
                            'features': features,
                            'timestamp': time.time()
                        })

                    except queue.Full:
                        # 緩衝區滿，丟棄最舊的特徵
                        try:
                            self.feature_buffer.get_nowait()
                            self.feature_buffer.put_nowait({
                                'stroke_id': stroke.stroke_id,
                                'features': features,
                                'timestamp': time.time()
                            })
                        except queue.Empty:
                            pass

            except Exception as e:
                self.logger.error(f"Feature calculation error: {e}")
                self._trigger_callback('on_error', {
                    'error_type': 'feature_calculation_error',
                    'message': str(e),
                    'timestamp': time.time()
                })

        self.logger.info("Feature calculation loop ended")

    def _status_monitoring_loop(self):
        """狀態監控主循環"""
        self.logger.info("Status monitoring loop started")

        last_report_time = time.time()

        while self.is_processing and not self.stop_event.is_set():
            try:
                current_time = time.time()

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
            'timestamp': time.time()
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
            event_type: 事件類型 ('on_stroke_completed', 'on_features_calculated', 'on_error', 'on_status_update')
            callback: 回調函數
        """
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
        else:
            self.logger.warning(f"Unknown event type: {event_type}")

    def _trigger_callback(self, event_type: str, data: Any):
        """觸發回調函數"""
        if event_type in self.callbacks:
            for callback in self.callbacks[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    self.logger.error(f"Callback error for {event_type}: {e}")

    def get_processing_statistics(self) -> Dict[str, Any]:
        """獲取處理統計資訊"""
        current_time = time.time()
        
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

        # 緩衝區狀態
        stats['buffer_status'] = {
            'raw_points': self.raw_collector.get_buffer_size() if hasattr(self.raw_collector, 'get_buffer_size') else 0,
            'processed_points': self.processed_point_buffer.qsize(),
            'strokes': len(self.stroke_buffer),
            'features': self.feature_buffer.qsize()
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

        # 清空特徵緩衝區
        while not self.feature_buffer.empty():
            try:
                self.feature_buffer.get_nowait()
            except queue.Empty:
                break

    def get_latest_features(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        獲取最新的特徵數據

        Args:
            count: 要獲取的特徵數量

        Returns:
            List[Dict[str, Any]]: 特徵數據列表
        """
        features = []
        temp_features = []

        # 從緩衝區獲取特徵
        for _ in range(min(count, self.feature_buffer.qsize())):
            try:
                feature = self.feature_buffer.get_nowait()
                features.append(feature)
                temp_features.append(feature)
            except queue.Empty:
                break

        # 將特徵放回緩衝區
        for feature in temp_features:
            try:
                self.feature_buffer.put_nowait(feature)
            except queue.Full:
                break

        return features