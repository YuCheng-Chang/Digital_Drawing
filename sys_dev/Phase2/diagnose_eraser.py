# diagnose_eraser.py
"""
診斷橡皮擦事件處理是否正確
"""
import pandas as pd
import os
import re
import json

def diagnose_eraser_processing(data_dir):
    """診斷橡皮擦處理邏輯"""
    
    ink_data_path = os.path.join(data_dir, 'ink_data.csv')
    markers_path = os.path.join(data_dir, 'markers.csv')
    
    print("🔍 診斷橡皮擦事件處理")
    print("=" * 50)
    
    # 讀取數據
    if not os.path.exists(ink_data_path):
        print(f"❌ 找不到: {ink_data_path}")
        return
    
    if not os.path.exists(markers_path):
        print(f"❌ 找不到: {markers_path}")
        return
    
    ink_data = pd.read_csv(ink_data_path)
    markers = pd.read_csv(markers_path)
    
    print(f"📊 墨水數據: {len(ink_data)} 行")
    print(f"📊 標記數據: {len(markers)} 行")
    
    # 分析筆劃分布
    print(f"\n🎨 筆劃分布:")
    stroke_counts = ink_data['stroke_id'].value_counts().sort_index()
    for stroke_id, count in stroke_counts.items():
        print(f"  - Stroke {stroke_id}: {count} 個點")
    
    # 分析標記事件
    print(f"\n📝 標記事件:")
    for idx, row in markers.iterrows():
        print(f"  - {row['timestamp']}: {row['marker_text']}")
    
    # 測試橡皮擦解析邏輯
    print(f"\n🧹 測試橡皮擦解析:")
    eraser_events = {}
    pattern = r'eraser_(\d+)\|deleted_strokes:\[([^\]]*)\]'
    
    for idx, row in markers.iterrows():
        marker_text = row['marker_text']
        
        if marker_text.startswith('eraser_') and 'deleted_strokes:' in marker_text:
            print(f"  處理標記: {marker_text}")
            
            match = re.search(pattern, marker_text)
            if match:
                eraser_id = int(match.group(1))
                deleted_strokes_str = match.group(2)
                
                print(f"    - eraser_id: {eraser_id}")
                print(f"    - deleted_strokes_str: '{deleted_strokes_str}'")
                
                # 解析被刪除的筆劃 ID
                if deleted_strokes_str.strip():
                    try:
                        deleted_stroke_ids = [int(x.strip()) for x in deleted_strokes_str.split(',')]
                        print(f"    - 解析結果: {deleted_stroke_ids}")
                        
                        if eraser_id not in eraser_events:
                            eraser_events[eraser_id] = []
                        eraser_events[eraser_id].extend(deleted_stroke_ids)
                        
                    except Exception as e:
                        print(f"    - ❌ 解析錯誤: {e}")
                else:
                    print(f"    - 空的刪除列表")
            else:
                print(f"    - ❌ 正則匹配失敗")
    
    print(f"\n📋 橡皮擦事件總結:")
    if eraser_events:
        all_deleted = set()
        for eraser_id, deleted_ids in eraser_events.items():
            print(f"  - 橡皮擦 {eraser_id}: 刪除 {deleted_ids}")
            all_deleted.update(deleted_ids)
        
        print(f"  - 總共刪除的筆劃: {sorted(all_deleted)}")
        
        # 計算剩餘筆劃
        all_strokes = set(stroke_counts.index)
        remaining_strokes = all_strokes - all_deleted
        print(f"  - 原始筆劃: {sorted(all_strokes)}")
        print(f"  - 剩餘筆劃: {sorted(remaining_strokes)}")
        
        # 驗證邏輯
        if len(remaining_strokes) == 1 and 1 in remaining_strokes:
            print(f"  - ✅ 預期結果正確：只剩筆劃 1")
        else:
            print(f"  - ❌ 預期結果錯誤：應該只剩筆劃 1")
    else:
        print(f"  - 沒有檢測到橡皮擦事件")
    
    print("\n" + "=" * 50)

def main():
    # 替換為你的數據目錄
    data_dir = "./wacom_recordings/wacom_test_20251028_002657"
    
    if not os.path.exists(data_dir):
        data_dir = input("請輸入數據目錄路徑: ").strip()
    
    diagnose_eraser_processing(data_dir)

if __name__ == "__main__":
    main()