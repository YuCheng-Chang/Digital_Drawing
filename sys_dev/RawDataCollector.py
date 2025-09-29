import time
import threading
import queue
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import json
from InkProcessingSystemMainController import ProcessingConfig
from DigitalInkDataStructure import *

# 自定義異常類
class DeviceInitializationError(Exception):
    """設備初始化失敗異常"""
    pass

class UnsupportedDeviceError(Exception):
    """不支援的設備類型異常"""
    pass

class CollectionStartError(Exception):
    """無法開始數據收集異常"""
    pass

class DeviceStatus(Enum):
    """設備狀態枚舉"""
    DISCONNECTED = 0
    CONNECTED = 1
    COLLECTING = 2
    ERROR = 3

class RawDataCollector:
    """原始數據收集器 - 負責從設備獲取原始墨水數據"""

    def __init__(self, config: ProcessingConfig):
        """
        初始化原始數據收集器

        Args:
            config: 處理配置參數
        """
        self.config = config
        self.device_config = None
        self.device_status = DeviceStatus.DISCONNECTED
        self.device_info = {}

        # 數據收集相關
        self.collection_thread = None
        self.collection_active = False
        self.data_queue = queue.Queue(maxsize=10000)
        self.collection_lock = threading.Lock()

        # 統計資訊
        self.statistics = {
            'total_points': 0,
            'collection_start_time': None,
            'collection_duration': 0.0,
            'average_rate': 0.0,
            'dropped_points': 0,
            'last_point_timestamp': 0.0,
            'error_count': 0
        }

        # 校準數據
        self.calibration_matrix = None
        self.coordinate_transform = None

        # 設備特定的處理器
        self.device_handlers = {
            'wacom': self._handle_wacom_device,
            'touch': self._handle_touch_device,
            'mouse': self._handle_mouse_device,
            'simulator': self._handle_simulator_device  # 用於測試
        }

        # 日誌設定
        self.logger = logging.getLogger(__name__)

    def initialize_device(self, device_config: Dict[str, Any]) -> bool:
        """
        初始化墨水輸入設備

        Args:
            device_config: 設備配置字典，包含：
                - device_type: str, 設備類型 ('wacom', 'touch', 'mouse')
                - device_path: str, 設備路径或識別碼
                - sampling_rate: int, 設備採樣率
                - calibration_data: Dict, 校準數據

        Returns:
            bool: 初始化是否成功

        Raises:
            DeviceInitializationError: 設備初始化失敗
            UnsupportedDeviceError: 不支援的設備類型
        """
        try:
            self.logger.info(f"正在初始化設備: {device_config.get('device_type', 'unknown')}")

            # 驗證設備配置
            if not self._validate_device_config(device_config):
                raise DeviceInitializationError("設備配置無效")

            self.device_config = device_config.copy()
            device_type = device_config['device_type'].lower()

            # 檢查設備類型支援
            if device_type not in self.device_handlers:
                raise UnsupportedDeviceError(f"不支援的設備類型: {device_type}")

            # 調用對應的設備處理器
            success = self.device_handlers[device_type](device_config)

            if success:
                self.device_status = DeviceStatus.CONNECTED
                self._setup_calibration(device_config.get('calibration_data', {}))
                self.logger.info("設備初始化成功")
                return True
            else:
                self.device_status = DeviceStatus.ERROR
                raise DeviceInitializationError("設備初始化失敗")

        except Exception as e:
            self.logger.error(f"設備初始化錯誤: {str(e)}")
            self.device_status = DeviceStatus.ERROR
            raise

    def start_collection(self) -> bool:
        """
        開始數據收集

        Returns:
            bool: 是否成功開始收集

        Raises:
            CollectionStartError: 無法開始數據收集
        """
        try:
            with self.collection_lock:
                if self.device_status != DeviceStatus.CONNECTED:
                    raise CollectionStartError("設備未連接或狀態異常")

                if self.collection_active:
                    self.logger.warning("數據收集已在進行中")
                    return True

                # 清空數據隊列
                while not self.data_queue.empty():
                    try:
                        self.data_queue.get_nowait()
                    except queue.Empty:
                        break

                # 重置統計資訊
                self.statistics['total_points'] = 0
                self.statistics['collection_start_time'] = time.time()
                self.statistics['dropped_points'] = 0
                self.statistics['error_count'] = 0

                # 啟動收集線程
                self.collection_active = True
                self.collection_thread = threading.Thread(
                    target=self._collection_worker,
                    name="InkDataCollector",
                    daemon=True
                )
                self.collection_thread.start()

                self.device_status = DeviceStatus.COLLECTING
                self.logger.info("數據收集已開始")
                return True

        except Exception as e:
            self.logger.error(f"啟動數據收集失敗: {str(e)}")
            self.collection_active = False
            raise CollectionStartError(f"無法開始數據收集: {str(e)}")

    def stop_collection(self) -> bool:
        """
        停止數據收集

        Returns:
            bool: 是否成功停止收集
        """
        try:
            with self.collection_lock:
                if not self.collection_active:
                    self.logger.warning("數據收集未在進行中")
                    return True

                self.collection_active = False

                # 等待收集線程結束
                if self.collection_thread and self.collection_thread.is_alive():
                    self.collection_thread.join(timeout=2.0)
                    if self.collection_thread.is_alive():
                        self.logger.warning("收集線程未能正常結束")

                # 更新統計資訊
                if self.statistics['collection_start_time']:
                    self.statistics['collection_duration'] = (
                        time.time() - self.statistics['collection_start_time']
                    )
                    if self.statistics['collection_duration'] > 0:
                        self.statistics['average_rate'] = (
                            self.statistics['total_points'] /
                            self.statistics['collection_duration']
                        )

                self.device_status = DeviceStatus.CONNECTED
                self.logger.info("數據收集已停止")
                return True

        except Exception as e:
            self.logger.error(f"停止數據收集失敗: {str(e)}")
            return False

    def get_raw_point(self, timeout: float = 0.1) -> Optional[RawInkPoint]:
        """
        獲取一個原始墨水點 (阻塞式)

        Args:
            timeout: 超時時間 (秒)

        Returns:
            Optional[RawInkPoint]: 原始墨水點，如果超時則返回None
        """
        try:
            return self.data_queue.get(timeout=timeout)
        except queue.Empty:
            return None
        except Exception as e:
            self.logger.error(f"獲取原始點失敗: {str(e)}")
            return None

    def get_raw_points_batch(self, max_count: int = 100) -> List[RawInkPoint]:
        """
        批次獲取原始墨水點 (非阻塞式)

        Args:
            max_count: 最大獲取數量

        Returns:
            List[RawInkPoint]: 原始墨水點列表
        """
        points = []
        try:
            for _ in range(max_count):
                try:
                    point = self.data_queue.get_nowait()
                    points.append(point)
                except queue.Empty:
                    break
        except Exception as e:
            self.logger.error(f"批次獲取原始點失敗: {str(e)}")

        return points

    def is_device_connected(self) -> bool:
        """
        檢查設備連接狀態

        Returns:
            bool: 設備是否連接
        """
        return self.device_status in [DeviceStatus.CONNECTED, DeviceStatus.COLLECTING]

    def get_device_info(self) -> Dict[str, Any]:
        """
        獲取設備資訊

        Returns:
            Dict[str, Any]: 設備資訊字典，包含：
                - name: str, 設備名稱
                - model: str, 設備型號
                - resolution: Tuple[int, int], 解析度
                - pressure_levels: int, 壓力等級數
                - tilt_support: bool, 是否支援傾斜
                - twist_support: bool, 是否支援旋轉
        """
        return self.device_info.copy()

    def calibrate_device(self, calibration_points: List[Tuple[float, float]]) -> bool:
        """
        校準設備座標系統

        Args:
            calibration_points: 校準點列表 [(x, y), ...]

        Returns:
            bool: 校準是否成功
        """
        try:
            if len(calibration_points) < 4:
                self.logger.error("校準點數量不足，至少需要4個點")
                return False

            # 計算校準矩陣 (簡化實現，實際應使用更複雜的變換)
            self.calibration_matrix = self._calculate_calibration_matrix(calibration_points)

            # 設置座標變換函數
            self.coordinate_transform = self._create_coordinate_transform()

            self.logger.info("設備校準完成")
            return True

        except Exception as e:
            self.logger.error(f"設備校準失敗: {str(e)}")
            return False

    def get_collection_statistics(self) -> Dict[str, Any]:
        """
        獲取收集統計資訊

        Returns:
            Dict[str, Any]: 統計資訊，包含：
                - total_points: int, 總點數
                - collection_duration: float, 收集持續時間
                - average_rate: float, 平均採樣率
                - dropped_points: int, 丟失點數
                - last_point_timestamp: float, 最後一點時間戳
        """
        stats = self.statistics.copy()

        # 如果正在收集，更新持續時間
        if self.collection_active and stats['collection_start_time']:
            stats['collection_duration'] = time.time() - stats['collection_start_time']
            if stats['collection_duration'] > 0:
                stats['average_rate'] = stats['total_points'] / stats['collection_duration']

        return stats

    # 私有方法實現

    def _validate_device_config(self, config: Dict[str, Any]) -> bool:
        """驗證設備配置"""
        required_fields = ['device_type', 'device_path', 'sampling_rate']
        return all(field in config for field in required_fields)

    def _setup_calibration(self, calibration_data: Dict[str, Any]) -> None:
        """設置校準數據"""
        if calibration_data:
            self.calibration_matrix = calibration_data.get('matrix')
            # 其他校準設置...

    def _collection_worker(self) -> None:
        """數據收集工作線程"""
        self.logger.info("數據收集線程啟動")

        try:
            while self.collection_active:
                # 模擬數據收集 (實際實現需要調用設備API)
                raw_point = self._simulate_data_point()

                if raw_point:
                    try:
                        # 應用座標變換
                        if self.coordinate_transform:
                            raw_point = self.coordinate_transform(raw_point)

                        self.data_queue.put(raw_point, timeout=0.01)
                        self.statistics['total_points'] += 1
                        self.statistics['last_point_timestamp'] = raw_point.timestamp

                    except queue.Full:
                        self.statistics['dropped_points'] += 1
                        self.logger.warning("數據隊列已滿，丟棄數據點")

                # 控制採樣率
                time.sleep(1.0 / self.device_config.get('sampling_rate', 200))

        except Exception as e:
            self.logger.error(f"數據收集線程錯誤: {str(e)}")
            self.statistics['error_count'] += 1
        finally:
            self.logger.info("數據收集線程結束")

    def _simulate_data_point(self) -> Optional[RawInkPoint]:
        """模擬數據點生成 (用於測試)"""
        import random

        return RawInkPoint(
            x=random.uniform(0, 1000),
            y=random.uniform(0, 1000),
            pressure=random.uniform(0.0, 1.0),
            tilt_x=random.uniform(-60, 60),
            tilt_y=random.uniform(-60, 60),
            twist=random.uniform(0, 360),
            timestamp=time.time(),
            device_id=self.device_config.get('device_path', 'simulator'),
            button_state=0
        )

    def _handle_wacom_device(self, config: Dict[str, Any]) -> bool:
        """處理Wacom設備初始化"""
        try:
            # 實際實現需要調用Wacom SDK
            self.device_info = {
                'name': 'Wacom Tablet',
                'model': config.get('model', 'Unknown'),
                'resolution': (5080, 3175),  # 示例解析度
                'pressure_levels': 8192,
                'tilt_support': True,
                'twist_support': True
            }
            self.logger.info("Wacom設備初始化完成")
            return True
        except Exception as e:
            self.logger.error(f"Wacom設備初始化失敗: {str(e)}")
            return False

    def _handle_touch_device(self, config: Dict[str, Any]) -> bool:
        """處理觸控設備初始化"""
        try:
            self.device_info = {
                'name': 'Touch Device',
                'model': config.get('model', 'Unknown'),
                'resolution': (1920, 1080),
                'pressure_levels': 256,
                'tilt_support': False,
                'twist_support': False
            }
            self.logger.info("觸控設備初始化完成")
            return True
        except Exception as e:
            self.logger.error(f"觸控設備初始化失敗: {str(e)}")
            return False

    def _handle_mouse_device(self, config: Dict[str, Any]) -> bool:
        """處理滑鼠設備初始化"""
        try:
            self.device_info = {
                'name': 'Mouse Device',
                'model': config.get('model', 'Unknown'),
                'resolution': (1920, 1080),
                'pressure_levels': 1,  # 滑鼠沒有壓力感應
                'tilt_support': False,
                'twist_support': False
            }
            self.logger.info("滑鼠設備初始化完成")
            return True
        except Exception as e:
            self.logger.error(f"滑鼠設備初始化失敗: {str(e)}")
            return False

    def _handle_simulator_device(self, config: Dict[str, Any]) -> bool:
        """處理模擬器設備初始化"""
        try:
            self.device_info = {
                'name': 'Simulator Device',
                'model': 'Test Simulator',
                'resolution': (1000, 1000),
                'pressure_levels': 1024,
                'tilt_support': True,
                'twist_support': True
            }
            self.logger.info("模擬器設備初始化完成")
            return True
        except Exception as e:
            self.logger.error(f"模擬器設備初始化失敗: {str(e)}")
            return False

    def _calculate_calibration_matrix(self, points: List[Tuple[float, float]]) -> Any:
        """計算校準矩陣"""
        # 簡化實現，實際需要更複雜的數學計算
        return {
            'scale_x': 1.0,
            'scale_y': 1.0,
            'offset_x': 0.0,
            'offset_y': 0.0,
            'rotation': 0.0
        }

    def _create_coordinate_transform(self) -> callable:
        """創建座標變換函數"""
        def transform(point: RawInkPoint) -> RawInkPoint:
            if not self.calibration_matrix:
                return point

            # 應用校準變換
            transformed_point = RawInkPoint(
                x=point.x * self.calibration_matrix['scale_x'] + self.calibration_matrix['offset_x'],
                y=point.y * self.calibration_matrix['scale_y'] + self.calibration_matrix['offset_y'],
                pressure=point.pressure,
                tilt_x=point.tilt_x,
                tilt_y=point.tilt_y,
                twist=point.twist,
                timestamp=point.timestamp,
                device_id=point.device_id,
                button_state=point.button_state
            )
            return transformed_point

        return transform

    def __del__(self):
        """析構函數，確保資源清理"""
        if self.collection_active:
            self.stop_collection()