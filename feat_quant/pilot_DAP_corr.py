import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import pearsonr
import seaborn as sns

# 設定中文字體
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False

def create_scatter_plot(df, x_col, y_col, output_filename):
    """
    創建散布圖並計算相關係數
    
    Args:
        df: DataFrame
        x_col: X軸欄位名稱
        y_col: Y軸欄位名稱
        output_filename: 輸出檔案名稱
    """
    # 移除缺失值
    valid_data = df[[x_col, y_col]].dropna()
    
    if len(valid_data) < 2:
        print(f"⚠️ {x_col} vs {y_col}: 資料點不足，無法計算相關係數")
        return
    
    x = valid_data[x_col]
    y = valid_data[y_col]
    
    # 計算皮爾森相關係數
    r, p_value = pearsonr(x, y)
    
    # 創建圖表
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # 繪製散布圖
    ax.scatter(x, y, s=100, alpha=0.6, color='steelblue', edgecolors='black', linewidth=1.5)
    
    # 添加趨勢線
    z = np.polyfit(x, y, 1)
    p = np.poly1d(z)
    x_line = np.linspace(x.min(), x.max(), 100)
    ax.plot(x_line, p(x_line), "r--", alpha=0.8, linewidth=2, label='趨勢線')
    
    # 設定標題和軸標籤
    ax.set_xlabel(x_col, fontsize=14, fontweight='bold')
    ax.set_ylabel(y_col, fontsize=14, fontweight='bold')
    ax.set_title(f'{x_col} vs {y_col}', fontsize=16, fontweight='bold', pad=20)
    
    # 顯示相關係數和p值
    significance = "***" if p_value < 0.001 else "**" if p_value < 0.01 else "*" if p_value < 0.05 else "ns"
    stats_text = f'r = {r:.3f}\np = {p_value:.3f} {significance}\nn = {len(valid_data)}'
    
    # 添加文字框
    ax.text(0.05, 0.95, stats_text, 
            transform=ax.transAxes,
            fontsize=13,
            verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8, edgecolor='black', linewidth=1.5))
    
    # 美化圖表
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(loc='lower right', fontsize=11)
    
    # 調整佈局
    plt.tight_layout()
    
    # 儲存圖片
    plt.savefig(output_filename, dpi=300, bbox_inches='tight')
    print(f"✅ 已儲存: {output_filename} (r={r:.3f}, p={p_value:.3f})")
    
    plt.close()


def main():
    """主程式"""
    
    # 讀取 Excel 檔案
    print("📂 讀取 corr.xlsx...")
    try:
        df = pd.read_excel('./corr.xlsx')
        print(f"✅ 成功讀取 {len(df)} 筆資料")
    except FileNotFoundError:
        print("❌ 找不到 corr.xlsx 檔案")
        return
    except Exception as e:
        print(f"❌ 讀取檔案時發生錯誤: {e}")
        return
    
    # 顯示欄位
    print(f"\n📋 欄位列表: {list(df.columns)}")
    
    # 檢查必要欄位
    required_columns = ['受試者編號', '第一大類總分', '第二大類總分', '第三大類總分', '一至三類總分', 'MADRS_T']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        print(f"❌ 缺少必要欄位: {missing_columns}")
        print(f"   現有欄位: {list(df.columns)}")
        return
    
    # 顯示資料摘要
    print("\n📊 資料摘要:")
    print(df[['第一大類總分', '第二大類總分', '第三大類總分', '一至三類總分', 'MADRS_T']].describe())
    
    # 檢查缺失值
    print("\n🔍 缺失值檢查:")
    missing_counts = df[required_columns].isnull().sum()
    for col, count in missing_counts.items():
        if count > 0:
            print(f"  {col}: {count} 筆缺失")
    
    # 定義要繪製的圖表
    plots = [
        ('第一大類總分', 'MADRS_T', 'scatter_category1_vs_MADRS.png'),
        ('第二大類總分', 'MADRS_T', 'scatter_category2_vs_MADRS.png'),
        ('第三大類總分', 'MADRS_T', 'scatter_category3_vs_MADRS.png'),
        ('一至三類總分', 'MADRS_T', 'scatter_total_vs_MADRS.png')
    ]
    
    # 繪製散布圖
    print("\n📈 開始繪製散布圖...")
    for x_col, y_col, filename in plots:
        create_scatter_plot(df, x_col, y_col, filename)
    
    # 計算並顯示相關矩陣
    print("\n📊 相關係數矩陣:")
    correlation_cols = ['第一大類總分', '第二大類總分', '第三大類總分', '一至三類總分', 'MADRS_T']
    corr_matrix = df[correlation_cols].corr()
    print(corr_matrix.round(3))
    
    # 繪製相關矩陣熱圖
    print("\n🎨 繪製相關矩陣熱圖...")
    plt.figure(figsize=(10, 8))
    sns.heatmap(corr_matrix, annot=True, fmt='.3f', cmap='coolwarm', 
                center=0, square=True, linewidths=1, cbar_kws={"shrink": 0.8})
    plt.title('相關係數矩陣', fontsize=16, fontweight='bold', pad=20)
    plt.tight_layout()
    plt.savefig('correlation_matrix_heatmap.png', dpi=300, bbox_inches='tight')
    print("✅ 已儲存: correlation_matrix_heatmap.png")
    plt.close()
    
    # 生成詳細報告
    print("\n📋 詳細相關分析報告:")
    print("=" * 70)
    for x_col, y_col, _ in plots:
        valid_data = df[[x_col, y_col]].dropna()
        if len(valid_data) >= 2:
            r, p_value = pearsonr(valid_data[x_col], valid_data[y_col])
            significance = "***" if p_value < 0.001 else "**" if p_value < 0.01 else "*" if p_value < 0.05 else "ns"
            print(f"{x_col} vs {y_col}:")
            print(f"  樣本數: {len(valid_data)}")
            print(f"  相關係數 (r): {r:.3f}")
            print(f"  p值: {p_value:.3f} {significance}")
            print(f"  效果量: {'大' if abs(r) >= 0.5 else '中' if abs(r) >= 0.3 else '小'}")
            print("-" * 70)
    
    print("\n✅ 所有圖表已生成完成！")
    print("\n📁 生成的檔案:")
    print("  1. scatter_category1_vs_MADRS.png")
    print("  2. scatter_category2_vs_MADRS.png")
    print("  3. scatter_category3_vs_MADRS.png")
    print("  4. scatter_total_vs_MADRS.png")
    print("  5. correlation_matrix_heatmap.png (額外贈送)")


if __name__ == "__main__":
    main()
