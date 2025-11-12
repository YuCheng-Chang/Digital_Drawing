# visualize_directory_structure_advanced.py
"""
進階版目錄結構可視化工具

新增功能：
1. 搜尋特定檔案
2. 過濾特定類型
3. 顯示檔案修改時間
4. 顯示檔案數量統計
"""

import os
from pathlib import Path
from datetime import datetime
import json
import re


class AdvancedDirectoryVisualizer:
    """進階目錄結構可視化工具"""
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.total_files = 0
        self.total_dirs = 0
        self.total_size = 0
        self.file_types = {}
        self.search_results = []
        
    def get_size_str(self, size_bytes: int) -> str:
        """將位元組轉換為可讀格式"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"
    
    def search_files(self, pattern: str, case_sensitive: bool = False):
        """
        搜尋符合模式的檔案
        
        Args:
            pattern: 搜尋模式（支援正則表達式）
            case_sensitive: 是否區分大小寫
        """
        print(f"\n🔍 搜尋檔案: {pattern}")
        print("=" * 70)
        
        flags = 0 if case_sensitive else re.IGNORECASE
        regex = re.compile(pattern, flags)
        
        self.search_results = []
        
        for item in self.root_path.rglob('*'):
            if item.is_file() and regex.search(item.name):
                self.search_results.append(item)
        
        if self.search_results:
            print(f"找到 {len(self.search_results)} 個符合的檔案:\n")
            
            for file_path in self.search_results:
                relative_path = file_path.relative_to(self.root_path)
                stat = file_path.stat()
                size_str = self.get_size_str(stat.st_size)
                modified = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                
                print(f"📄 {relative_path}")
                print(f"   大小: {size_str} | 修改時間: {modified}")
                print()
        else:
            print("❌ 沒有找到符合的檔案")
        
        print("=" * 70)
    
    def filter_by_extension(self, extensions: list):
        """
        只顯示特定副檔名的檔案
        
        Args:
            extensions: 副檔名列表（例如 ['.csv', '.json']）
        """
        print(f"\n📋 過濾檔案類型: {', '.join(extensions)}")
        print("=" * 70)
        
        filtered_files = []
        
        for item in self.root_path.rglob('*'):
            if item.is_file() and item.suffix in extensions:
                filtered_files.append(item)
        
        if filtered_files:
            print(f"找到 {len(filtered_files)} 個檔案:\n")
            
            # 按副檔名分組
            grouped = {}
            for file_path in filtered_files:
                ext = file_path.suffix
                if ext not in grouped:
                    grouped[ext] = []
                grouped[ext].append(file_path)
            
            for ext, files in sorted(grouped.items()):
                print(f"\n{ext} 檔案 ({len(files)} 個):")
                for file_path in sorted(files):
                    relative_path = file_path.relative_to(self.root_path)
                    stat = file_path.stat()
                    size_str = self.get_size_str(stat.st_size)
                    print(f"  📄 {relative_path} ({size_str})")
        else:
            print("❌ 沒有找到符合的檔案")
        
        print("\n" + "=" * 70)
    
    def show_largest_files(self, count: int = 10):
        """顯示最大的 N 個檔案"""
        print(f"\n📊 最大的 {count} 個檔案")
        print("=" * 70)
        
        all_files = []
        for item in self.root_path.rglob('*'):
            if item.is_file():
                all_files.append((item, item.stat().st_size))
        
        # 按大小排序
        all_files.sort(key=lambda x: x[1], reverse=True)
        
        for i, (file_path, size) in enumerate(all_files[:count], 1):
            relative_path = file_path.relative_to(self.root_path)
            size_str = self.get_size_str(size)
            print(f"{i:2d}. {relative_path}")
            print(f"    {size_str}")
            print()
        
        print("=" * 70)
    
    def analyze_subject_data(self):
        """分析受試者數據結構"""
        print("\n👤 受試者數據分析")
        print("=" * 70)
        
        # 假設結構為: wacom_recordings/受試者ID/繪畫類型/檔案
        subjects = {}
        
        for subject_dir in self.root_path.iterdir():
            if not subject_dir.is_dir():
                continue
            
            subject_id = subject_dir.name
            subjects[subject_id] = {
                'drawings': [],
                'total_size': 0,
                'file_count': 0
            }
            
            for drawing_dir in subject_dir.iterdir():
                if not drawing_dir.is_dir():
                    continue
                
                drawing_info = {
                    'id': drawing_dir.name,
                    'files': [],
                    'size': 0
                }
                
                for file in drawing_dir.iterdir():
                    if file.is_file():
                        size = file.stat().st_size
                        drawing_info['files'].append({
                            'name': file.name,
                            'size': size
                        })
                        drawing_info['size'] += size
                        subjects[subject_id]['file_count'] += 1
                
                subjects[subject_id]['drawings'].append(drawing_info)
                subjects[subject_id]['total_size'] += drawing_info['size']
        
        # 顯示分析結果
        for subject_id, data in sorted(subjects.items()):
            print(f"\n📁 受試者: {subject_id}")
            print(f"   繪畫數量: {len(data['drawings'])}")
            print(f"   總檔案數: {data['file_count']}")
            print(f"   總大小: {self.get_size_str(data['total_size'])}")
            
            if data['drawings']:
                print(f"   繪畫列表:")
                for drawing in data['drawings']:
                    print(f"     - {drawing['id']}: {len(drawing['files'])} 個檔案, "
                          f"{self.get_size_str(drawing['size'])}")
        
        print("\n" + "=" * 70)
    
    def visualize_tree(self, directory: Path = None, prefix: str = "", 
                      is_last: bool = True, show_size: bool = True,
                      show_time: bool = False):
        """
        遞迴繪製目錄樹（增強版）
        
        Args:
            directory: 要掃描的目錄
            prefix: 前綴字符
            is_last: 是否為最後一個項目
            show_size: 是否顯示檔案大小
            show_time: 是否顯示修改時間
        """
        if directory is None:
            directory = self.root_path
        
        if not directory.exists():
            print(f"❌ 目錄不存在: {directory}")
            return
        
        try:
            items = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name))
        except PermissionError:
            print(f"{prefix}❌ 無權限訪問")
            return
        
        for index, item in enumerate(items):
            is_last_item = (index == len(items) - 1)
            connector = "└── " if is_last_item else "├── "
            
            if item.is_dir():
                self.total_dirs += 1
                
                # 計算資料夾內的檔案數
                try:
                    file_count = sum(1 for _ in item.rglob('*') if _.is_file())
                    print(f"{prefix}{connector}📁 {item.name}/ ({file_count} 個檔案)")
                except:
                    print(f"{prefix}{connector}📁 {item.name}/")
                
                extension = "    " if is_last_item else "│   "
                self.visualize_tree(item, prefix + extension, is_last_item, 
                                  show_size, show_time)
            else:
                self.total_files += 1
                stat = item.stat()
                self.total_size += stat.st_size
                
                ext = item.suffix
                self.file_types[ext] = self.file_types.get(ext, 0) + 1
                
                icon = self._get_file_icon(item.name)
                info_parts = [item.name]
                
                if show_size:
                    info_parts.append(self.get_size_str(stat.st_size))
                
                if show_time:
                    modified = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                    info_parts.append(modified)
                
                info_str = " | ".join(info_parts)
                print(f"{prefix}{connector}{icon} {info_str}")
    
    def _get_file_icon(self, filename: str) -> str:
        """根據檔案類型返回圖示"""
        ext = Path(filename).suffix.lower()
        
        icon_map = {
            '.csv': '📊',
            '.json': '📋',
            '.txt': '📄',
            '.log': '📝',
            '.png': '🖼️',
            '.jpg': '🖼️',
            '.jpeg': '🖼️',
            '.xdf': '💾',
            '.py': '🐍',
            '.md': '📖',
        }
        
        return icon_map.get(ext, '📄')
    
    def print_statistics(self):
        """輸出統計資訊"""
        print("\n" + "=" * 70)
        print("📊 統計資訊")
        print("=" * 70)
        print(f"總資料夾數: {self.total_dirs}")
        print(f"總檔案數: {self.total_files}")
        print(f"總大小: {self.get_size_str(self.total_size)}")
        
        if self.file_types:
            print("\n檔案類型分布:")
            for ext, count in sorted(self.file_types.items(), key=lambda x: x[1], reverse=True):
                ext_name = ext if ext else "(無副檔名)"
                print(f"  {ext_name}: {count} 個")
        
        print("=" * 70)


def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description='進階目錄結構可視化工具')
    parser.add_argument('path', nargs='?', default='./wacom_recordings',
                       help='要掃描的目錄路徑')
    parser.add_argument('--search', type=str,
                       help='搜尋檔案（支援正則表達式）')
    parser.add_argument('--filter', type=str, nargs='+',
                       help='過濾特定副檔名（例如: .csv .json）')
    parser.add_argument('--largest', type=int, metavar='N',
                       help='顯示最大的 N 個檔案')
    parser.add_argument('--analyze', action='store_true',
                       help='分析受試者數據結構')
    parser.add_argument('--show-time', action='store_true',
                       help='顯示檔案修改時間')
    parser.add_argument('--json', action='store_true',
                       help='匯出為 JSON')
    
    args = parser.parse_args()
    
    visualizer = AdvancedDirectoryVisualizer(args.path)
    
    # 顯示樹狀圖
    print("=" * 70)
    print(f"📁 目錄結構: {visualizer.root_path}")
    print("=" * 70)
    print()
    
    visualizer.visualize_tree(show_time=args.show_time)
    visualizer.print_statistics()
    
    # 搜尋功能
    if args.search:
        visualizer.search_files(args.search)
    
    # 過濾功能
    if args.filter:
        visualizer.filter_by_extension(args.filter)
    
    # 顯示最大檔案
    if args.largest:
        visualizer.show_largest_files(args.largest)
    
    # 分析受試者數據
    if args.analyze:
        visualizer.analyze_subject_data()


if __name__ == "__main__":
    main()
