import pandas as pd
import numpy as np

def score_dap_drawing(row):
    """
    根據年齡和座標標準對 DAP 繪畫進行評分
    
    Args:
        row: DataFrame 的一行資料
    
    Returns:
        dict: 包含各項評分的字典
    """
    age = row['Age']
    x_range = row['x_range_norm']
    y_range = row['y_range_norm']
    x_start = row['x_start_norm']
    x_end = row['x_end_norm']
    y_start = row['y_start_norm']
    y_end = row['y_end_norm']
    
    scores = {}
    
    # 根據年齡選擇評分標準
    if age <= 12:
        # 9-12歲計分標準
        scores['高大人物'] = 1 if x_range > 0.491 else 0
        scores['矮小人物'] = 1 if x_range < 0.245 else 0
        scores['巨大人物'] = 1 if (x_range > 0.491 and y_range > 0.355) else 0
        scores['微小人物'] = 1 if (x_range < 0.245 and y_range < 0.143) else 0
        scores['頂部放置'] = 1 if (x_start < 0.157 and x_end < 0.514) else 0
        scores['底部放置'] = 1 if (x_start > 0.4 and x_end > 0.78) else 0
        scores['左側放置'] = 1 if (y_start > 0.505 and y_end > 0.75) else 0
        scores['右側放置'] = 1 if (y_start < 0.33 and y_end < 0.6) else 0
    else:
        # >12歲計分標準
        scores['高大人物'] = 1 if x_range > 0.515 else 0
        scores['矮小人物'] = 1 if x_range < 0.256 else 0
        scores['巨大人物'] = 1 if (x_range > 0.515 and y_range > 0.33) else 0
        scores['微小人物'] = 1 if (x_range < 0.256 and y_range < 0.148) else 0
        scores['頂部放置'] = 1 if (x_start < 0.147 and x_end < 0.507) else 0
        scores['底部放置'] = 1 if (x_start > 0.326 and x_end > 0.767) else 0
        scores['左側放置'] = 1 if (y_start > 0.52 and y_end > 0.75) else 0
        scores['右側放置'] = 1 if (y_start < 0.35 and y_end < 0.61) else 0
    
    return scores


def main():
    """主程式"""
    
    # 讀取 Excel 檔案
    print("📂 讀取 summary_statistics.xlsx...")
    try:
        df = pd.read_excel('./summary_statistics.xlsx')
        print(f"✅ 成功讀取 {len(df)} 筆資料")
    except FileNotFoundError:
        print("❌ 找不到 summary_statistics.xlsx 檔案")
        return
    except Exception as e:
        print(f"❌ 讀取檔案時發生錯誤: {e}")
        return
    
    # 顯示原始欄位
    print(f"\n📋 原始欄位: {list(df.columns)}")
    
    # 檢查必要欄位是否存在
    required_columns = [
        'Age', 'x_range_norm', 'y_range_norm', 
        'x_start_norm', 'x_end_norm', 'y_start_norm', 'y_end_norm'
    ]
    
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"❌ 缺少必要欄位: {missing_columns}")
        return
    
    # 對每一行進行評分
    print("\n🔍 開始評分...")
    score_columns = ['高大人物', '矮小人物', '巨大人物', '微小人物', 
                     '頂部放置', '底部放置', '左側放置', '右側放置']
    
    # 初始化評分欄位
    for col in score_columns:
        df[col] = 0
    
    # 逐行計算評分
    for idx, row in df.iterrows():
        scores = score_dap_drawing(row)
        for col, value in scores.items():
            df.at[idx, col] = value
        
        # 顯示進度
        if (idx + 1) % 5 == 0 or (idx + 1) == len(df):
            print(f"  處理進度: {idx + 1}/{len(df)}")
    
    # 顯示評分統計
    print("\n📊 評分統計:")
    for col in score_columns:
        count = df[col].sum()
        percentage = (count / len(df)) * 100
        print(f"  {col}: {count}/{len(df)} ({percentage:.1f}%)")
    
    # 匯出結果
    output_path = './DAP_score.xlsx'
    print(f"\n💾 匯出結果到 {output_path}...")
    
    try:
        df.to_excel(output_path, index=False, sheet_name='DAP_Scores')
        print(f"✅ 成功匯出到 {output_path}")
        print(f"📋 最終欄位: {list(df.columns)}")
    except Exception as e:
        print(f"❌ 匯出檔案時發生錯誤: {e}")
        return
    
    # 顯示前幾筆資料預覽
    print("\n👀 前 3 筆資料預覽:")
    preview_columns = ['subject_id', 'Age', 'x_range_norm', 'y_range_norm'] + score_columns
    available_preview_columns = [col for col in preview_columns if col in df.columns]
    print(df[available_preview_columns].head(3).to_string(index=False))
    
    print("\n✅ 處理完成！")


if __name__ == "__main__":
    main()
