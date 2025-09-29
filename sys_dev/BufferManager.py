import time
import threading
from threading import Lock, RLock
from collections import deque
import queue
from typing import List, Dict, Any, Optional, Callable, Tuple
import logging
import weakref
from dataclasses import dataclass
import gc
from InkProcessingSystemMainController import ProcessingConfig
from DigitalInkDataStructure import ProcessedInkPoint, InkStroke, InkEvent

@dataclass
class BufferStatistics:
    """緩衝區統計資訊"""
    buffer_name: str
    current_size: int
    max_size: int
    total_added: int
    total_removed: int
    total_dropped: int
    utilization_rate: float
    peak_size: int
    last_access_time: float

class BufferManager:
    """緩衝管理器 - 負責管理各種數據緩衝區"""

    def __init__(self, config: ProcessingConfig):
        """
        初始化緩衝管理器

        Args:
            config: 處理配置參數
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # 緩衝區註冊表
        self._buffers = {}
        self._buffer_locks = {}
        self._buffer_stats = {}
        self._buffer_callbacks = {}

        # 全局鎖
        self._global_lock = RLock()

        # 監控參數
        self.monitoring_enabled = True
        self.auto_cleanup_enabled = True
        self.cleanup_interval = 60.0  # 秒

        # 性能統計
        self.performance_stats = {
            'total_operations': 0,
            'failed_operations': 0,
            'memory_usage': 0,
            'cleanup_count': 0
        }

        # 啟動清理線程
        if self.auto_cleanup_enabled:
            self._start_cleanup_thread()

        self.logger.info("BufferManager 初始化完成")

    def create_point_buffer(self, buffer_size: int = 10000, 
                           buffer_name: str = None) -> queue.Queue:
        """
        創建點數據緩衝區

        Args:
            buffer_size: 緩衝區大小
            buffer_name: 緩衝區名稱

        Returns:
            queue.Queue: 線程安全的點緩衝區
        """
        try:
            with self._global_lock:
                buffer_name = buffer_name or f"point_buffer_{len(self._buffers)}"

                # 創建有界隊列
                buffer = queue.Queue(maxsize=buffer_size)

                # 註冊緩衝區
                self._register_buffer(buffer_name, buffer, 'point', buffer_size)

                self.logger.info(f"創建點緩衝區: {buffer_name}, 大小: {buffer_size}")
                return buffer

        except Exception as e:
            self.logger.error(f"創建點緩衝區失敗: {str(e)}")
            self.performance_stats['failed_operations'] += 1
            raise

    def create_stroke_buffer(self, buffer_size: int = 1000,
                            buffer_name: str = None) -> deque:
        """
        創建筆劃緩衝區

        Args:
            buffer_size: 緩衝區大小
            buffer_name: 緩衝區名稱

        Returns:
            deque: 筆劃緩衝區
        """
        try:
            with self._global_lock:
                buffer_name = buffer_name or f"stroke_buffer_{len(self._buffers)}"

                # 創建有界雙端隊列
                buffer = deque(maxlen=buffer_size)

                # 註冊緩衝區
                self._register_buffer(buffer_name, buffer, 'stroke', buffer_size)

                self.logger.info(f"創建筆劃緩衝區: {buffer_name}, 大小: {buffer_size}")
                return buffer

        except Exception as e:
            self.logger.error(f"創建筆劃緩衝區失敗: {str(e)}")
            self.performance_stats['failed_operations'] += 1
            raise

    def create_event_buffer(self, buffer_size: int = 5000,
                           buffer_name: str = None) -> queue.Queue:
        """
        創建事件緩衝區

        Args:
            buffer_size: 緩衝區大小
            buffer_name: 緩衝區名稱

        Returns:
            queue.Queue: 事件緩衝區
        """
        try:
            with self._global_lock:
                buffer_name = buffer_name or f"event_buffer_{len(self._buffers)}"

                # 創建優先級隊列
                buffer = queue.PriorityQueue(maxsize=buffer_size)

                # 註冊緩衝區
                self._register_buffer(buffer_name, buffer, 'event', buffer_size)

                self.logger.info(f"創建事件緩衝區: {buffer_name}, 大小: {buffer_size}")
                return buffer

        except Exception as e:
            self.logger.error(f"創建事件緩衝區失敗: {str(e)}")
            self.performance_stats['failed_operations'] += 1
            raise

    def add_point_to_buffer(self, buffer: queue.Queue, 
                           point: ProcessedInkPoint,
                           timeout: float = 0.1,
                           drop_on_full: bool = True) -> bool:
        """
        添加點到緩衝區

        Args:
            buffer: 目標緩衝區
            point: 要添加的點
            timeout: 超時時間
            drop_on_full: 緩衝區滿時是否丟棄

        Returns:
            bool: 是否成功添加
        """
        try:
            self.performance_stats['total_operations'] += 1

            # 獲取緩衝區名稱
            buffer_name = self._get_buffer_name(buffer)

            if drop_on_full and buffer.full():
                # 緩衝區滿，嘗試移除最舊的元素
                try:
                    buffer.get_nowait()
                    self._update_buffer_stats(buffer_name, 'dropped', 1)
                except queue.Empty:
                    pass

            # 添加新點
            buffer.put(point, timeout=timeout)

            # 更新統計
            self._update_buffer_stats(buffer_name, 'added', 1)
            self._update_buffer_stats(buffer_name, 'last_access', time.time())

            return True

        except queue.Full:
            self.logger.warning(f"緩衝區已滿，無法添加點")
            self._update_buffer_stats(buffer_name, 'dropped', 1)
            self.performance_stats['failed_operations'] += 1
            return False
        except Exception as e:
            self.logger.error(f"添加點到緩衝區失敗: {str(e)}")
            self.performance_stats['failed_operations'] += 1
            return False

    def get_point_from_buffer(self, buffer: queue.Queue,
                             timeout: float = 0.1) -> Optional[ProcessedInkPoint]:
        """
        從緩衝區獲取點

        Args:
            buffer: 源緩衝區
            timeout: 超時時間

        Returns:
            Optional[ProcessedInkPoint]: 獲取的點，超時返回None
        """
        try:
            self.performance_stats['total_operations'] += 1

            point = buffer.get(timeout=timeout)

            # 更新統計
            buffer_name = self._get_buffer_name(buffer)
            self._update_buffer_stats(buffer_name, 'removed', 1)
            self._update_buffer_stats(buffer_name, 'last_access', time.time())

            return point

        except queue.Empty:
            return None
        except Exception as e:
            self.logger.error(f"從緩衝區獲取點失敗: {str(e)}")
            self.performance_stats['failed_operations'] += 1
            return None

    def add_stroke_to_buffer(self, buffer: deque,
                            stroke: InkStroke) -> bool:
        """
        添加筆劃到緩衝區

        Args:
            buffer: 目標緩衝區
            stroke: 要添加的筆劃

        Returns:
            bool: 是否成功添加
        """
        try:
            self.performance_stats['total_operations'] += 1

            # 檢查是否會超出容量
            if len(buffer) >= buffer.maxlen:
                self._update_buffer_stats(self._get_buffer_name(buffer), 'dropped', 1)

            buffer.append(stroke)

            # 更新統計
            buffer_name = self._get_buffer_name(buffer)
            self._update_buffer_stats(buffer_name, 'added', 1)
            self._update_buffer_stats(buffer_name, 'last_access', time.time())

            return True

        except Exception as e:
            self.logger.error(f"添加筆劃到緩衝區失敗: {str(e)}")
            self.performance_stats['failed_operations'] += 1
            return False

    def get_stroke_from_buffer(self, buffer: deque) -> Optional[InkStroke]:
        """
        從緩衝區獲取筆劃

        Args:
            buffer: 源緩衝區

        Returns:
            Optional[InkStroke]: 獲取的筆劃，空則返回None
        """
        try:
            self.performance_stats['total_operations'] += 1

            if not buffer:
                return None

            stroke = buffer.popleft()

            # 更新統計
            buffer_name = self._get_buffer_name(buffer)
            self._update_buffer_stats(buffer_name, 'removed', 1)
            self._update_buffer_stats(buffer_name, 'last_access', time.time())

            return stroke

        except IndexError:
            return None
        except Exception as e:
            self.logger.error(f"從緩衝區獲取筆劃失敗: {str(e)}")
            self.performance_stats['failed_operations'] += 1
            return None

    def add_event_to_buffer(self, buffer: queue.PriorityQueue,
                           event: InkEvent,
                           priority: int = 0,
                           timeout: float = 0.1) -> bool:
        """
        添加事件到緩衝區

        Args:
            buffer: 目標緩衝區
            event: 要添加的事件
            priority: 事件優先級 (數字越小優先級越高)
            timeout: 超時時間

        Returns:
            bool: 是否成功添加
        """
        try:
            self.performance_stats['total_operations'] += 1

            # 創建優先級項目
            priority_item = (priority, time.time(), event)

            buffer.put(priority_item, timeout=timeout)

            # 更新統計
            buffer_name = self._get_buffer_name(buffer)
            self._update_buffer_stats(buffer_name, 'added', 1)
            self._update_buffer_stats(buffer_name, 'last_access', time.time())

            return True

        except queue.Full:
            self.logger.warning(f"事件緩衝區已滿")
            self._update_buffer_stats(buffer_name, 'dropped', 1)
            self.performance_stats['failed_operations'] += 1
            return False
        except Exception as e:
            self.logger.error(f"添加事件到緩衝區失敗: {str(e)}")
            self.performance_stats['failed_operations'] += 1
            return False

    def get_event_from_buffer(self, buffer: queue.PriorityQueue,
                             timeout: float = 0.1) -> Optional[InkEvent]:
        """
        從緩衝區獲取事件

        Args:
            buffer: 源緩衝區
            timeout: 超時時間

        Returns:
            Optional[InkEvent]: 獲取的事件，超時返回None
        """
        try:
            self.performance_stats['total_operations'] += 1

            priority_item = buffer.get(timeout=timeout)
            priority, timestamp, event = priority_item

            # 更新統計
            buffer_name = self._get_buffer_name(buffer)
            self._update_buffer_stats(buffer_name, 'removed', 1)
            self._update_buffer_stats(buffer_name, 'last_access', time.time())

            return event

        except queue.Empty:
            return None
        except Exception as e:
            self.logger.error(f"從緩衝區獲取事件失敗: {str(e)}")
            self.performance_stats['failed_operations'] += 1
            return None

    def get_buffer_batch(self, buffer: queue.Queue,
                        max_count: int = 100,
                        timeout: float = 0.1) -> List[Any]:
        """
        批次獲取緩衝區數據

        Args:
            buffer: 源緩衝區
            max_count: 最大獲取數量
            timeout: 單次獲取超時時間

        Returns:
            List[Any]: 獲取的數據列表
        """
        try:
            items = []
            start_time = time.time()

            for _ in range(max_count):
                try:
                    # 動態調整超時時間
                    remaining_time = max(0.001, timeout - (time.time() - start_time))
                    item = buffer.get(timeout=remaining_time)
                    items.append(item)
                except queue.Empty:
                    break

            # 更新統計
            if items:
                buffer_name = self._get_buffer_name(buffer)
                self._update_buffer_stats(buffer_name, 'removed', len(items))
                self._update_buffer_stats(buffer_name, 'last_access', time.time())

            return items

        except Exception as e:
            self.logger.error(f"批次獲取緩衝區數據失敗: {str(e)}")
            return []

    def clear_buffer(self, buffer: Any) -> int:
        """
        清空緩衝區

        Args:
            buffer: 要清空的緩衝區

        Returns:
            int: 清空的項目數量
        """
        try:
            cleared_count = 0
            buffer_name = self._get_buffer_name(buffer)

            if isinstance(buffer, queue.Queue):
                while not buffer.empty():
                    try:
                        buffer.get_nowait()
                        cleared_count += 1
                    except queue.Empty:
                        break
            elif isinstance(buffer, deque):
                cleared_count = len(buffer)
                buffer.clear()

            # 更新統計
            self._update_buffer_stats(buffer_name, 'removed', cleared_count)
            self._update_buffer_stats(buffer_name, 'last_access', time.time())

            self.logger.info(f"清空緩衝區 {buffer_name}: {cleared_count} 項目")
            return cleared_count

        except Exception as e:
            self.logger.error(f"清空緩衝區失敗: {str(e)}")
            return 0

    def get_buffer_size(self, buffer: Any) -> int:
        """
        獲取緩衝區當前大小

        Args:
            buffer: 緩衝區

        Returns:
            int: 當前大小
        """
        try:
            if isinstance(buffer, queue.Queue):
                return buffer.qsize()
            elif isinstance(buffer, deque):
                return len(buffer)
            else:
                return 0
        except Exception:
            return 0

    def is_buffer_empty(self, buffer: Any) -> bool:
        """
        檢查緩衝區是否為空

        Args:
            buffer: 緩衝區

        Returns:
            bool: 是否為空
        """
        try:
            if isinstance(buffer, queue.Queue):
                return buffer.empty()
            elif isinstance(buffer, deque):
                return len(buffer) == 0
            else:
                return True
        except Exception:
            return True

    def is_buffer_full(self, buffer: Any) -> bool:
        """
        檢查緩衝區是否已滿

        Args:
            buffer: 緩衝區

        Returns:
            bool: 是否已滿
        """
        try:
            if isinstance(buffer, queue.Queue):
                return buffer.full()
            elif isinstance(buffer, deque):
                return len(buffer) >= buffer.maxlen
            else:
                return False
        except Exception:
            return False

    def register_buffer_callback(self, buffer_name: str,
                                callback_type: str,
                                callback: Callable) -> bool:
        """
        註冊緩衝區回調函數

        Args:
            buffer_name: 緩衝區名稱
            callback_type: 回調類型 ('full', 'empty', 'threshold')
            callback: 回調函數

        Returns:
            bool: 是否成功註冊
        """
        try:
            with self._global_lock:
                if buffer_name not in self._buffer_callbacks:
                    self._buffer_callbacks[buffer_name] = {}

                self._buffer_callbacks[buffer_name][callback_type] = callback
                self.logger.info(f"註冊緩衝區回調: {buffer_name}.{callback_type}")
                return True

        except Exception as e:
            self.logger.error(f"註冊緩衝區回調失敗: {str(e)}")
            return False

    def get_buffer_statistics(self, buffer_name: str = None) -> Dict[str, BufferStatistics]:
        """
        獲取緩衝區統計資訊

        Args:
            buffer_name: 特定緩衝區名稱，None則返回所有

        Returns:
            Dict[str, BufferStatistics]: 統計資訊字典
        """
        try:
            with self._global_lock:
                if buffer_name:
                    if buffer_name in self._buffer_stats:
                        return {buffer_name: self._create_buffer_statistics(buffer_name)}
                    else:
                        return {}
                else:
                    stats = {}
                    for name in self._buffer_stats:
                        stats[name] = self._create_buffer_statistics(name)
                    return stats

        except Exception as e:
            self.logger.error(f"獲取緩衝區統計失敗: {str(e)}")
            return {}

    def get_memory_usage(self) -> Dict[str, Any]:
        """
        獲取內存使用情況

        Returns:
            Dict[str, Any]: 內存使用統計
        """
        try:
            import psutil
            import sys

            process = psutil.Process()
            memory_info = process.memory_info()

            # 估算緩衝區內存使用
            buffer_memory = 0
            for buffer_name, buffer in self._buffers.items():
                buffer_memory += sys.getsizeof(buffer)

            return {
                'total_memory': memory_info.rss,
                'buffer_memory': buffer_memory,
                'buffer_count': len(self._buffers),
                'memory_percent': process.memory_percent()
            }

        except ImportError:
            return {'error': 'psutil not available'}
        except Exception as e:
            self.logger.error(f"獲取內存使用失敗: {str(e)}")
            return {}

    def cleanup_inactive_buffers(self, inactive_threshold: float = 300.0) -> int:
        """
        清理不活躍的緩衝區

        Args:
            inactive_threshold: 不活躍閾值 (秒)

        Returns:
            int: 清理的緩衝區數量
        """
        try:
            current_time = time.time()
            cleaned_count = 0

            with self._global_lock:
                inactive_buffers = []

                for buffer_name, stats in self._buffer_stats.items():
                    last_access = stats.get('last_access_time', 0)
                    if current_time - last_access > inactive_threshold:
                        inactive_buffers.append(buffer_name)

                for buffer_name in inactive_buffers:
                    if buffer_name in self._buffers:
                        buffer = self._buffers[buffer_name]
                        self.clear_buffer(buffer)
                        cleaned_count += 1
                        self.logger.info(f"清理不活躍緩衝區: {buffer_name}")

            self.performance_stats['cleanup_count'] += cleaned_count
            return cleaned_count

        except Exception as e:
            self.logger.error(f"清理不活躍緩衝區失敗: {str(e)}")
            return 0

    def shutdown(self) -> None:
        """關閉緩衝管理器"""
        try:
            self.logger.info("正在關閉 BufferManager...")

            # 停止清理線程
            if hasattr(self, '_cleanup_thread'):
                self._cleanup_stop_event.set()
                self._cleanup_thread.join(timeout=5.0)

            # 清空所有緩衝區
            with self._global_lock:
                for buffer_name, buffer in self._buffers.items():
                    try:
                        self.clear_buffer(buffer)
                    except Exception as e:
                        self.logger.warning(f"清空緩衝區 {buffer_name} 失敗: {str(e)}")

                self._buffers.clear()
                self._buffer_stats.clear()
                self._buffer_callbacks.clear()

            self.logger.info("BufferManager 已關閉")

        except Exception as e:
            self.logger.error(f"關閉 BufferManager 失敗: {str(e)}")

    # 私有輔助方法

    def _register_buffer(self, name: str, buffer: Any, buffer_type: str, max_size: int) -> None:
        """註冊緩衝區"""
        self._buffers[name] = buffer
        self._buffer_locks[name] = Lock()
        self._buffer_stats[name] = {
            'buffer_type': buffer_type,
            'max_size': max_size,
            'total_added': 0,
            'total_removed': 0,
            'total_dropped': 0,
            'peak_size': 0,
            'last_access_time': time.time(),
            'created_time': time.time()
        }

    def _get_buffer_name(self, buffer: Any) -> str:
        """獲取緩衝區名稱"""
        for name, registered_buffer in self._buffers.items():
            if registered_buffer is buffer:
                return name
        return 'unknown'

    def _update_buffer_stats(self, buffer_name: str, stat_type: str, value: Any) -> None:
        """更新緩衝區統計"""
        if buffer_name in self._buffer_stats:
            if stat_type == 'added':
                self._buffer_stats[buffer_name]['total_added'] += value
            elif stat_type == 'removed':
                self._buffer_stats[buffer_name]['total_removed'] += value
            elif stat_type == 'dropped':
                self._buffer_stats[buffer_name]['total_dropped'] += value
            elif stat_type == 'last_access':
                self._buffer_stats[buffer_name]['last_access_time'] = value

            # 更新峰值大小
            if buffer_name in self._buffers:
                current_size = self.get_buffer_size(self._buffers[buffer_name])
                if current_size > self._buffer_stats[buffer_name]['peak_size']:
                    self._buffer_stats[buffer_name]['peak_size'] = current_size

    def _create_buffer_statistics(self, buffer_name: str) -> BufferStatistics:
        """創建緩衝區統計對象"""
        stats = self._buffer_stats[buffer_name]
        current_size = self.get_buffer_size(self._buffers[buffer_name]) if buffer_name in self._buffers else 0

        utilization_rate = current_size / stats['max_size'] if stats['max_size'] > 0 else 0.0

        return BufferStatistics(
            buffer_name=buffer_name,
            current_size=current_size,
            max_size=stats['max_size'],
            total_added=stats['total_added'],
            total_removed=stats['total_removed'],
            total_dropped=stats['total_dropped'],
            utilization_rate=utilization_rate,
            peak_size=stats['peak_size'],
            last_access_time=stats['last_access_time']
        )

    def _start_cleanup_thread(self) -> None:
        """啟動清理線程"""
        self._cleanup_stop_event = threading.Event()
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_worker,
            name="BufferManager-Cleanup",
            daemon=True
        )
        self._cleanup_thread.start()

    def _cleanup_worker(self) -> None:
        """清理工作線程"""
        while not self._cleanup_stop_event.wait(self.cleanup_interval):
            try:
                self.cleanup_inactive_buffers()
                gc.collect()  # 強制垃圾回收
            except Exception as e:
                self.logger.error(f"清理線程錯誤: {str(e)}")

    def __del__(self):
        """析構函數"""
        try:
            self.shutdown()
        except Exception:
            pass