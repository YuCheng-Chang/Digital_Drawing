import json
import time
from typing import Dict, List, Any
from datetime import datetime
from InkProcessingSystemMainController import InkProcessingSystem, ProcessingConfig
# ===== 基本使用範例 =====

def basic_usage_example():
    """基本使用範例"""

    # 1. 創建配置
    config = ProcessingConfig(
        device_type="wacom",
        target_sampling_rate=200,
        smoothing_enabled=True,
        smoothing_window_size=5,
        stroke_timeout=0.5,
        feature_types=['basic', 'kinematic', 'pressure']
    )

    # 2. 創建系統實例
    ink_system = InkProcessingSystem(config)

    # 3. 設備配置
    device_config = {
        'device_type': 'wacom',
        'device_path': '/dev/input/wacom',
        'sampling_rate': 200,
        'calibration_data': {
            'x_offset': 0,
            'y_offset': 0,
            'x_scale': 1.0,
            'y_scale': 1.0
        }
    }

    # 4. 初始化系統
    if not ink_system.initialize(device_config):
        print("Failed to initialize system")
        return

    # 5. 註冊回調函數
    def on_stroke_completed(data):
        stroke = data['stroke']
        print(f"Stroke completed: {stroke.stroke_id}, Points: {len(stroke.points)}")

    def on_features_calculated(data):
        features = data['features']
        print(f"Features calculated for stroke {data['stroke_id']}: {len(features)} features")

    def on_error(data):
        print(f"Error: {data['error_type']} - {data['message']}")

    ink_system.register_callback('on_stroke_completed', on_stroke_completed)
    ink_system.register_callback('on_features_calculated', on_features_calculated)
    ink_system.register_callback('on_error', on_error)

    # 6. 開始處理
    if ink_system.start_processing():
        print("Processing started successfully")

        try:
            # 運行一段時間
            time.sleep(60)  # 運行60秒

            # 獲取統計資訊
            stats = ink_system.get_processing_statistics()
            print(f"Processing Statistics: {json.dumps(stats, indent=2)}")

        except KeyboardInterrupt:
            print("Interrupted by user")

        finally:
            # 停止處理
            ink_system.stop_processing()

    # 7. 關閉系統
    ink_system.shutdown()


# ===== 進階使用範例 =====

class InkDataAnalyzer:
    """墨水數據分析器 - 展示如何使用系統進行數據分析"""

    def __init__(self):
        self.collected_strokes = []
        self.collected_features = []
        self.analysis_results = {}
        self.ink_system = None

    def setup_system(self):
        """設置處理系統"""
        config = ProcessingConfig(
            device_type="universal_ink",
            target_sampling_rate=300,
            smoothing_enabled=True,
            feature_types=['basic', 'kinematic', 'pressure', 'geometric', 'temporal']
        )

        self.ink_system = InkProcessingSystem(config)

        # 註冊回調
        self.ink_system.register_callback('on_stroke_completed', self._on_stroke_completed)
        self.ink_system.register_callback('on_features_calculated', self._on_features_calculated)
        self.ink_system.register_callback('on_status_update', self._on_status_update)
        self.ink_system.register_callback('on_error', self._on_error)

    def _on_stroke_completed(self, data):
        """筆劃完成回調"""
        stroke = data['stroke']
        self.collected_strokes.append(stroke)
        print(f"Collected stroke {len(self.collected_strokes)}: {len(stroke.points)} points")

    def _on_features_calculated(self, data):
        """特徵計算完成回調"""
        feature_data = {
            'stroke_id': data['stroke_id'],
            'features': data['features'],
            'timestamp': data['timestamp']
        }
        self.collected_features.append(feature_data)
        print(f"Collected features for {len(self.collected_features)} strokes")

    def _on_status_update(self, data):
        """狀態更新回調"""
        if data['status'] == 'processing_update':
            stats = data['statistics']
            print(f"Status: {stats['total_strokes']} strokes, {stats['total_features']} features")

    def _on_error(self, data):
        """錯誤回調"""
        print(f"Error occurred: {data['error_type']} - {data['message']}")

    def start_collection(self, duration: int = 300):
        """開始數據收集"""
        device_config = {
            'device_type': 'universal_ink',
            'input_source': 'tablet',
            'sampling_rate': 300
        }

        if not self.ink_system.initialize(device_config):
            raise RuntimeError("Failed to initialize ink system")

        if not self.ink_system.start_processing():
            raise RuntimeError("Failed to start processing")

        print(f"Starting data collection for {duration} seconds...")
        print("Please start writing/drawing...")

        try:
            time.sleep(duration)
        except KeyboardInterrupt:
            print("Collection interrupted by user")
        finally:
            self.ink_system.stop_processing()
            print(f"Collection completed: {len(self.collected_strokes)} strokes collected")

    def analyze_data(self):
        """分析收集的數據"""
        if not self.collected_strokes:
            print("No data to analyze")
            return

        print("Analyzing collected data...")

        # 基本統計
        total_points = sum(len(stroke.points) for stroke in self.collected_strokes)
        avg_points_per_stroke = total_points / len(self.collected_strokes)

        # 筆劃長度分析
        stroke_lengths = []
        stroke_durations = []

        for stroke in self.collected_strokes:
            # 計算筆劃長度
            length = 0
            for i in range(1, len(stroke.points)):
                p1, p2 = stroke.points[i-1], stroke.points[i]
                length += ((p2.x - p1.x)**2 + (p2.y - p1.y)**2)**0.5
            stroke_lengths.append(length)

            # 計算筆劃持續時間
            if len(stroke.points) > 1:
                duration = stroke.points[-1].timestamp - stroke.points[0].timestamp
                stroke_durations.append(duration)

        avg_stroke_length = sum(stroke_lengths) / len(stroke_lengths) if stroke_lengths else 0
        avg_stroke_duration = sum(stroke_durations) / len(stroke_durations) if stroke_durations else 0

        # 壓力分析
        pressure_values = []
        for stroke in self.collected_strokes:
            for point in stroke.points:
                if hasattr(point, 'pressure') and point.pressure is not None:
                    pressure_values.append(point.pressure)

        avg_pressure = sum(pressure_values) / len(pressure_values) if pressure_values else 0
        max_pressure = max(pressure_values) if pressure_values else 0
        min_pressure = min(pressure_values) if pressure_values else 0

        # 特徵分析
        if self.collected_features:
            feature_types = set()
            for feature_data in self.collected_features:
                feature_types.update(feature_data['features'].keys())
        else:
            feature_types = set()

        self.analysis_results = {
            'collection_info': {
                'total_strokes': len(self.collected_strokes),
                'total_points': total_points,
                'total_features': len(self.collected_features),
                'collection_timestamp': datetime.now().isoformat()
            },
            'stroke_statistics': {
                'average_points_per_stroke': round(avg_points_per_stroke, 2),
                'average_stroke_length': round(avg_stroke_length, 2),
                'average_stroke_duration': round(avg_stroke_duration, 3),
                'min_stroke_length': round(min(stroke_lengths), 2) if stroke_lengths else 0,
                'max_stroke_length': round(max(stroke_lengths), 2) if stroke_lengths else 0
            },
            'pressure_statistics': {
                'average_pressure': round(avg_pressure, 3),
                'max_pressure': round(max_pressure, 3),
                'min_pressure': round(min_pressure, 3),
                'pressure_range': round(max_pressure - min_pressure, 3) if pressure_values else 0
            },
            'feature_info': {
                'feature_types': list(feature_types),
                'total_feature_sets': len(self.collected_features)
            }
        }

        print("Analysis Results:")
        print(json.dumps(self.analysis_results, indent=2))

        return self.analysis_results

    def _stroke_to_dict(self, stroke):
        """將筆劃對象轉換為字典"""
        return {
            'stroke_id': stroke.stroke_id,
            'timestamp': stroke.timestamp.isoformat() if hasattr(stroke, 'timestamp') else None,
            'points': [
                {
                    'x': point.x,
                    'y': point.y,
                    'pressure': getattr(point, 'pressure', None),
                    'timestamp': point.timestamp.isoformat() if hasattr(point, 'timestamp') else None,
                    'tilt_x': getattr(point, 'tilt_x', None),
                    'tilt_y': getattr(point, 'tilt_y', None)
                }
                for point in stroke.points
            ],
            'metadata': getattr(stroke, 'metadata', {})
        }

    def save_data(self, filename: str):
        """保存數據到文件"""
        data = {
            'metadata': {
                'version': '1.0',
                'created_at': datetime.now().isoformat(),
                'total_strokes': len(self.collected_strokes),
                'total_features': len(self.collected_features)
            },
            'strokes': [self._stroke_to_dict(stroke) for stroke in self.collected_strokes],
            'features': self.collected_features,
            'analysis': self.analysis_results
        }

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Data saved successfully to {filename}")
            print(f"File size: {len(json.dumps(data))} characters")
        except Exception as e:
            print(f"Failed to save data: {str(e)}")

    def load_data(self, filename: str):
        """從文件載入數據"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 重建筆劃對象（這裡需要根據實際的筆劃類來實現）
            self.collected_strokes = []  # 需要實際的重建邏輯
            self.collected_features = data.get('features', [])
            self.analysis_results = data.get('analysis', {})

            print(f"Data loaded successfully from {filename}")
            print(f"Loaded {len(self.collected_features)} feature sets")
            return True

        except Exception as e:
            print(f"Failed to load data: {str(e)}")
            return False

    def export_summary_report(self, filename: str):
        """導出摘要報告"""
        if not self.analysis_results:
            print("No analysis results to export. Run analyze_data() first.")
            return

        report = f"""
# 墨水數據分析報告

## 收集資訊
- 總筆劃數: {self.analysis_results['collection_info']['total_strokes']}
- 總點數: {self.analysis_results['collection_info']['total_points']}
- 收集時間: {self.analysis_results['collection_info']['collection_timestamp']}

## 筆劃統計
- 平均每筆劃點數: {self.analysis_results['stroke_statistics']['average_points_per_stroke']}
- 平均筆劃長度: {self.analysis_results['stroke_statistics']['average_stroke_length']}
- 平均筆劃持續時間: {self.analysis_results['stroke_statistics']['average_stroke_duration']}s

## 壓力統計
- 平均壓力: {self.analysis_results['pressure_statistics']['average_pressure']}
- 最大壓力: {self.analysis_results['pressure_statistics']['max_pressure']}
- 最小壓力: {self.analysis_results['pressure_statistics']['min_pressure']}

## 特徵資訊
- 特徵類型: {', '.join(self.analysis_results['feature_info']['feature_types'])}
- 特徵集總數: {self.analysis_results['feature_info']['total_feature_sets']}
"""

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"Summary report exported to {filename}")
        except Exception as e:
            print(f"Failed to export report: {str(e)}")

    def cleanup(self):
        """清理資源"""
        if self.ink_system:
            self.ink_system.shutdown()
        self.collected_strokes.clear()
        self.collected_features.clear()
        self.analysis_results.clear()


# ===== 使用範例 =====

def run_basic_example():
    """運行基本範例"""
    print("=== Running Basic Example ===")
    basic_usage_example()


def run_advanced_example():
    """運行進階範例"""
    print("=== Running Advanced Example ===")

    # 創建分析器
    analyzer = InkDataAnalyzer()

    try:
        # 設置系統
        analyzer.setup_system()

        # 開始收集數據（收集30秒）
        analyzer.start_collection(duration=30)

        # 分析數據
        results = analyzer.analyze_data()

        # 保存數據
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        data_filename = f"ink_data_{timestamp}.json"
        report_filename = f"ink_report_{timestamp}.md"

        analyzer.save_data(data_filename)
        analyzer.export_summary_report(report_filename)

        print(f"Analysis completed. Files saved:")
        print(f"- Data: {data_filename}")
        print(f"- Report: {report_filename}")

    except Exception as e:
        print(f"Error in advanced example: {str(e)}")

    finally:
        # 清理資源
        analyzer.cleanup()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "advanced":
        run_advanced_example()
    else:
        run_basic_example()