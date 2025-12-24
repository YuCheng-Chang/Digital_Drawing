import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import pearsonr
import seaborn as sns

# 設定中文字體和全域字體大小
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.size'] = 14  # 全域字體大小

def get_madrs_severity_color(madrs_score):
    """
    🆕 根據 MADRS 分數返回對應的嚴重程度顏色
    
    康復/無症狀：0-6 分 → 綠色
    輕度：7-19 分 → 黃色
    中度：20-34 分 → 橙色
    重度：35-60 分 → 紅色
    
    Args:
        madrs_score: MADRS 分數
    
    Returns:
        顏色代碼
    """
    if madrs_score <= 6:
        return '#2ecc71'  # 綠色 (康復/無症狀)
    elif madrs_score <= 19:
        return '#f1c40f'  # 黃色 (輕度)
    elif madrs_score <= 34:
        return '#e67e22'  # 橙色 (中度)
    else:
        return '#e74c3c'  # 紅色 (重度)


def get_madrs_severity_label(madrs_score):
    """
    🆕 根據 MADRS 分數返回對應的嚴重程度標籤
    
    Args:
        madrs_score: MADRS 分數
    
    Returns:
        嚴重程度標籤
    """
    if madrs_score <= 6:
        return '康復/無症狀 (0-6)'
    elif madrs_score <= 19:
        return '輕度 (7-19)'
    elif madrs_score <= 34:
        return '中度 (20-34)'
    else:
        return '重度 (35-60)'


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
    fig, ax = plt.subplots(figsize=(12, 10))
    
    # 繪製散布圖
    ax.scatter(x, y, s=150, alpha=0.6, color='steelblue', edgecolors='black', linewidth=2)
    
    # 添加趨勢線
    z = np.polyfit(x, y, 1)
    p = np.poly1d(z)
    x_line = np.linspace(x.min(), x.max(), 100)
    ax.plot(x_line, p(x_line), "r--", alpha=0.8, linewidth=3, label='趨勢線')
    
    # 設定標題和軸標籤
    ax.set_xlabel(x_col, fontsize=26, fontweight='bold')
    ax.set_ylabel(y_col, fontsize=26, fontweight='bold')
    ax.set_title(f'{x_col} vs {y_col}', fontsize=28, fontweight='bold', pad=20)
    
    # 設定 X 軸範圍和刻度（整數）
    if '第一大類總分' in x_col:
        ax.set_xlim(-0.5, 9.5)
        ax.set_xticks(range(0, 10))
    elif '第二大類總分' in x_col:
        ax.set_xlim(-0.5, 8.5)
        ax.set_xticks(range(0, 9))
    elif '第三大類總分' in x_col:
        ax.set_xlim(-0.5, 10.5)
        ax.set_xticks(range(0, 11))
    elif '一至三類總分' in x_col:
        ax.set_xlim(-0.5, 27.5)
        ax.set_xticks(range(0, 28, 2))
    
    # 設定 Y 軸刻度（整數）
    y_min = int(np.floor(y.min()))
    y_max = int(np.ceil(y.max()))
    ax.set_ylim(y_min - 1, y_max + 1)
    ax.set_yticks(range(y_min, y_max + 1))
    
    # 放大刻度標籤字體
    ax.tick_params(axis='both', which='major', labelsize=18)
    
    # 顯示相關係數和p值
    significance = "***" if p_value < 0.001 else "**" if p_value < 0.01 else "*" if p_value < 0.05 else "ns"
    stats_text = f'r = {r:.3f}\np = {p_value:.3f} {significance}\nn = {len(valid_data)}'
    
    # 添加文字框（右上角，文字左對齊）
    ax.text(0.95, 0.95, stats_text,
            transform=ax.transAxes,
            fontsize=20,
            verticalalignment='top',
            horizontalalignment='right',
            multialignment='left',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8, edgecolor='black', linewidth=2))
    
    # 美化圖表
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=1.5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_linewidth(2)
    ax.spines['bottom'].set_linewidth(2)
    ax.legend(loc='lower right', fontsize=18)
    
    # 調整佈局
    plt.tight_layout()
    
    # 儲存圖片
    plt.savefig(output_filename, dpi=300, bbox_inches='tight')
    print(f"✅ 已儲存: {output_filename} (r={r:.3f}, p={p_value:.3f})")
    
    plt.close()


def create_bar_chart(df, score_col, chart_title, output_filename, show_legend=False):
    """
    🆕 創建柱狀圖，主橫軸為受試者編號，副橫軸為 MADRS_T，縱軸為總分
    根據 MADRS 分數範圍使用不同顏色
    
    Args:
        df: DataFrame（已按 MADRS_T 排序）
        score_col: 分數欄位名稱
        chart_title: 圖表標題
        output_filename: 輸出檔案名稱
        show_legend: 是否顯示圖例（預設 False）
    """
    # 移除缺失值
    valid_data = df[['受試者編號', 'MADRS_T', score_col]].dropna()
    
    if len(valid_data) == 0:
        print(f"⚠️ {score_col}: 無有效資料")
        return
    
    # 創建圖表（加大高度以容納副橫軸）
    fig, ax = plt.subplots(figsize=(16, 10))
    
    # 使用位置索引作為 X 軸
    x_positions = np.arange(len(valid_data))
    y_values = valid_data[score_col].values
    subject_ids = valid_data['受試者編號'].values
    madrs_scores = valid_data['MADRS_T'].values
    
    # 根據 MADRS 分數設定顏色
    colors = [get_madrs_severity_color(madrs) for madrs in madrs_scores]
    
    bars = ax.bar(x_positions, y_values, width=0.8, alpha=0.8, 
                   color=colors, edgecolor='black', linewidth=1.5)
    
    # 🆕 在柱子上方顯示數值（放大字體）
    for i, (x, y) in enumerate(zip(x_positions, y_values)):
        ax.text(x, y + 0.15, f'{y:.0f}', ha='center', va='bottom', 
                fontsize=18, fontweight='bold')  # 🆕 12 → 18
    
    # 🆕 設定標題和軸標籤（放大字體）
    ax.set_xlabel('受試者編號', fontsize=32, fontweight='bold', labelpad=15)  # 🆕 26 → 32
    ax.set_ylabel('總分', fontsize=32, fontweight='bold')  # 🆕 26 → 32
    ax.set_title(chart_title, fontsize=36, fontweight='bold', pad=50)  # 🆕 28 → 36
    
    # 🆕 設定主橫軸（受試者編號）（放大字體）
    ax.set_xticks(x_positions)
    ax.set_xticklabels(subject_ids, rotation=45, ha='right', fontsize=20)  # 🆕 14 → 20
    
    # 設定 Y 軸刻度（統一 0-6）
    ax.set_ylim(-0.3, 6.5)
    ax.set_yticks(range(0, 7))
    
    # 🆕 放大刻度標籤字體
    ax.tick_params(axis='y', which='major', labelsize=24)  # 🆕 18 → 24
    
    # 🆕 添加副橫軸（MADRS_T）（放大字體）
    ax2 = ax.twiny()  # 創建共享 Y 軸的第二個 X 軸
    ax2.set_xlim(ax.get_xlim())
    ax2.set_xticks(x_positions)
    ax2.set_xticklabels(madrs_scores, fontsize=20)  # 🆕 14 → 20
    ax2.set_xlabel('MADRS_T', fontsize=32, fontweight='bold', labelpad=15)  # 🆕 26 → 32
    ax2.tick_params(axis='x', which='major', labelsize=20)  # 🆕 14 → 20
    
    # 🆕 只在 show_legend=True 時顯示圖例（放大字體）
    if show_legend:
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#2ecc71', edgecolor='black', label='康復/無症狀 (0-6)'),
            Patch(facecolor='#f1c40f', edgecolor='black', label='輕度 (7-19)'),
            Patch(facecolor='#e67e22', edgecolor='black', label='中度 (20-34)'),
            Patch(facecolor='#e74c3c', edgecolor='black', label='重度 (35-60)')
        ]
        ax.legend(handles=legend_elements, loc='upper left', fontsize=20, framealpha=0.9)  # 🆕 16 → 20
    
    # 美化圖表
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=1.5, axis='y')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_linewidth(2)
    ax.spines['bottom'].set_linewidth(2)
    
    # 調整佈局
    plt.tight_layout()
    
    # 儲存圖片
    plt.savefig(output_filename, dpi=300, bbox_inches='tight')
    print(f"✅ 已儲存: {output_filename}")
    
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
    
    # 依照 MADRS_T 排序
    df_sorted = df.sort_values('MADRS_T').reset_index(drop=True)
    
    # 顯示排序後的受試者資料（包含嚴重程度）
    print(f"\n📋 所有受試者資料 (依 MADRS_T 排序):")
    for idx, row in df_sorted.iterrows():
        severity = get_madrs_severity_label(row['MADRS_T'])
        print(f"  {row['受試者編號']}: MADRS_T = {row['MADRS_T']} [{severity}], "
              f"第一類 = {row['第一大類總分']}, "
              f"第二類 = {row['第二大類總分']}, "
              f"第三類 = {row['第三大類總分']}, "
              f"總分 = {row['一至三類總分']}")
    
    # 統計各嚴重程度的人數
    print(f"\n📊 MADRS 嚴重程度分布:")
    severity_counts = {
        '康復/無症狀 (0-6)': len(df[df['MADRS_T'] <= 6]),
        '輕度 (7-19)': len(df[(df['MADRS_T'] >= 7) & (df['MADRS_T'] <= 19)]),
        '中度 (20-34)': len(df[(df['MADRS_T'] >= 20) & (df['MADRS_T'] <= 34)]),
        '重度 (35-60)': len(df[df['MADRS_T'] >= 35])
    }
    for severity, count in severity_counts.items():
        print(f"  {severity}: {count} 人")
    
    # 顯示資料摘要
    print("\n📊 資料摘要:")
    print(df[['第一大類總分', '第二大類總分', '第三大類總分', '一至三類總分', 'MADRS_T']].describe())
    
    # 檢查缺失值
    print("\n🔍 缺失值檢查:")
    missing_counts = df[required_columns].isnull().sum()
    has_missing = False
    for col, count in missing_counts.items():
        if count > 0:
            print(f"  {col}: {count} 筆缺失")
            has_missing = True
    if not has_missing:
        print("  ✅ 無缺失值")
    
    # 定義要繪製的散布圖
    scatter_plots = [
        ('第一大類總分', 'MADRS_T', 'scatter_category1_vs_MADRS.png'),
        ('第二大類總分', 'MADRS_T', 'scatter_category2_vs_MADRS.png'),
        ('第三大類總分', 'MADRS_T', 'scatter_category3_vs_MADRS.png'),
        ('一至三類總分', 'MADRS_T', 'scatter_total_vs_MADRS.png')
    ]
    
    # 繪製散布圖
    print("\n📈 開始繪製散布圖...")
    for x_col, y_col, filename in scatter_plots:
        create_scatter_plot(df, x_col, y_col, filename)
    
    # 定義要繪製的柱狀圖（包含圖表標題和是否顯示圖例）
    bar_charts = [
        ('第一大類總分', '第一大類', 'bar_category1_vs_MADRS.png', True),
        ('第二大類總分', '第二大類', 'bar_category2_vs_MADRS.png', False),
        ('第三大類總分', '第三大類', 'bar_category3_vs_MADRS.png', False),
        ('一至三類總分', '三類總分', 'bar_total_vs_MADRS.png', False)
    ]
    
    # 繪製柱狀圖（傳入圖表標題）
    print("\n📊 開始繪製柱狀圖...")
    for score_col, chart_title, filename, show_legend in bar_charts:
        create_bar_chart(df_sorted, score_col, chart_title, filename, show_legend=show_legend)
    
    # 計算並顯示相關矩陣
    print("\n📊 相關係數矩陣:")
    correlation_cols = ['第一大類總分', '第二大類總分', '第三大類總分', '一至三類總分', 'MADRS_T']
    corr_matrix = df[correlation_cols].corr()
    print(corr_matrix.round(3))
    
    # 繪製相關矩陣熱圖
    print("\n🎨 繪製相關矩陣熱圖...")
    plt.figure(figsize=(12, 10))
    sns.heatmap(corr_matrix, annot=True, fmt='.3f', cmap='coolwarm', 
                center=0, square=True, linewidths=2, 
                cbar_kws={"shrink": 0.8},
                annot_kws={"size": 16})
    plt.title('相關係數矩陣', fontsize=22, fontweight='bold', pad=20)
    plt.xticks(fontsize=16, rotation=45, ha='right')
    plt.yticks(fontsize=16, rotation=0)
    plt.tight_layout()
    plt.savefig('correlation_matrix_heatmap.png', dpi=300, bbox_inches='tight')
    print("✅ 已儲存: correlation_matrix_heatmap.png")
    plt.close()
    
    # 生成詳細報告
    print("\n📋 詳細相關分析報告:")
    print("=" * 70)
    for x_col, y_col, _ in scatter_plots:
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
        else:
            print(f"{x_col} vs {y_col}:")
            print(f"  ⚠️ 資料點不足 (n={len(valid_data)})")
            print("-" * 70)
    
    print("\n✅ 所有圖表已生成完成！")
    print(f"\n📊 分析摘要:")
    print(f"  總資料筆數: {len(df)} 筆")
    print("\n📁 生成的檔案:")
    print("  【散布圖】")
    print("  1. scatter_category1_vs_MADRS.png")
    print("  2. scatter_category2_vs_MADRS.png")
    print("  3. scatter_category3_vs_MADRS.png")
    print("  4. scatter_total_vs_MADRS.png")
    print("  【柱狀圖】")
    print("  5. bar_category1_vs_MADRS.png (含圖例)")
    print("  6. bar_category2_vs_MADRS.png")
    print("  7. bar_category3_vs_MADRS.png")
    print("  8. bar_total_vs_MADRS.png")
    print("  【其他】")
    print("  9. correlation_matrix_heatmap.png")


if __name__ == "__main__":
    main()
