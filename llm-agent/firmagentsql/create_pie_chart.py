import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

def extract_supply_data(csv_file, product_ids=['product_11', 'product_12'], step_start=100, step_end=191):
    """从CSV文件中提取供应量数据，计算 step_end - step_start 的差值"""
    try:
        df = pd.read_csv(csv_file)
        all_products_data = {}

        for product_id in product_ids:
            # 筛选 supply_amount 相关数据
            supply_data = df[df['key'].str.contains(f'supply_amount_B.*_{product_id}', regex=True)]
            if supply_data.empty:
                print(f"No supply data found for {product_id} in {csv_file}")
                continue

            # 筛选出两个指定 step
            data_start = supply_data[supply_data['step'] == step_start]
            data_end = supply_data[supply_data['step'] == step_end]

            if data_start.empty or data_end.empty:
                print(f"Missing step {step_start} or {step_end} data for {product_id}")
                continue

            companies = {}

            # 先构建一个字典保存 step=100 的值
            start_dict = {}
            for _, row in data_start.iterrows():
                key = row['key']
                parts = key.split('_')
                if len(parts) >= 3 and parts[0] == 'supply' and parts[1] == 'amount':
                    company = parts[2]
                    start_dict[company] = row['value']

            # 再计算 step=200 - step=100 的差值
            for _, row in data_end.iterrows():
                key = row['key']
                parts = key.split('_')
                if len(parts) >= 3 and parts[0] == 'supply' and parts[1] == 'amount':
                    company = parts[2]
                else:
                    continue

                value_start = start_dict.get(company, 0)
                value_end = row['value']
                delta = value_end - value_start

                companies[company] = {
                    'step_start': step_start,
                    'step_end': step_end,
                    'value': delta
                }

            print(f"  {product_id} companies Δ(step {step_start}->{step_end}): {companies}")
            all_products_data[product_id] = companies

        return all_products_data

    except Exception as e:
        print(f"Error processing {csv_file}: {e}")
        return {}

def create_pie_chart(data_dict, title_suffix="", product_id=""):
    """创建饼图"""
    if not data_dict:
        print("No data to plot")
        return None
    
    # 准备数据
    companies = list(data_dict.keys())
    values = [data_dict[company]['value'] for company in companies]
    
    # 计算百分比
    total = sum(values)
    if total == 0:
        print("Total supply amount is 0")
        return None
    
    # 创建饼图
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # 设置颜色
    colors = plt.cm.Set3(np.linspace(0, 1, len(companies)))
    
    # 绘制饼图
    wedges, texts, autotexts = ax.pie(values, labels=companies, autopct='%1.1f%%', 
                                      colors=colors, startangle=90)
    
    # 设置标题
    product_name = product_id.replace('_', ' ').title()
    ax.set_title(f'{product_name} Supply Distribution by Company{title_suffix}', 
                fontsize=16, fontweight='bold', pad=20)
    
    # 添加图例
    ax.legend(wedges, [f'{company}: {value:,.1f}' for company, value in zip(companies, values)],
              title="Companies (Supply Amount)",
              loc="center left",
              bbox_to_anchor=(1, 0, 0.5, 1))
    
    plt.tight_layout()
    return fig

def create_combined_pie_chart(all_data, title_suffix=""):
    """创建合并的饼图，显示所有产品的总供应量"""
    if not all_data:
        print("No data to plot")
        return None
    
    # 合并所有产品的数据
    combined_companies = {}
    
    for product_id, companies_data in all_data.items():
        for company, info in companies_data.items():
            if company not in combined_companies:
                combined_companies[company] = 0
            combined_companies[company] += info['value']
    
    if not combined_companies:
        return None
    
    # 准备数据
    companies = list(combined_companies.keys())
    values = list(combined_companies.values())
    
    # 计算百分比
    total = sum(values)
    if total == 0:
        print("Total supply amount is 0")
        return None
    
    # 创建饼图
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # 设置颜色
    colors = plt.cm.Set3(np.linspace(0, 1, len(companies)))
    
    # 绘制饼图
    wedges, texts, autotexts = ax.pie(values, labels=companies, autopct='%1.1f%%', 
                                      colors=colors, startangle=90)
    
    # 设置标题
    ax.set_title(f'Total Supply Distribution by Company (Product 11 + Product 12){title_suffix}', 
                fontsize=16, fontweight='bold', pad=20)
    
    # 添加图例
    ax.legend(wedges, [f'{company}: {value:,.1f}' for company, value in zip(companies, values)],
              title="Companies (Total Supply Amount)",
              loc="center left",
              bbox_to_anchor=(1, 0, 0.5, 1))
    
    plt.tight_layout()
    return fig

# 主程序
def main():
    base_dir = "./firmagentsql/"
    # csv_files = ['metrics_gpt.csv', 'metrics_deepseek.csv', 'metrics_qwen.csv']
    csv_files = ['metrics_change.csv']
    for csv_file in csv_files:
        file_path = os.path.join(base_dir, csv_file)
        if os.path.exists(file_path):
            print(f"\n=== Processing {csv_file}----{file_path}===")
            data = extract_supply_data(file_path, step_start=100, step_end=191)
            
            if data:
                model_name = csv_file.replace('metrics_', '').replace('.csv', '').upper()
                print(f"Found data for {model_name}: {data}")
                
                # 为每个产品单独创建饼图
                for product_id, companies_data in data.items():
                    if companies_data:
                        print(f"\nCreating chart for {product_id} in {model_name}")
                        fig = create_pie_chart(companies_data, f" - {model_name} Model", product_id)
                        if fig: 
                            output_file = os.path.join(base_dir, f'supply_distribution_{product_id}_{model_name.lower()}.png')
                            fig.savefig(output_file, dpi=300, bbox_inches='tight')
                            print(f"Saved chart: {output_file}")
                            plt.close(fig)  # 关闭图形以释放内存
                
                # 创建合并的饼图（该模型所有产品总和）
                print(f"\nCreating combined chart for {model_name}")
                fig_combined = create_combined_pie_chart(data, f" - {model_name} Model")
                if fig_combined:
                    output_file = os.path.join(base_dir, f'supply_distribution_total_{model_name.lower()}.png')
                    fig_combined.savefig(output_file, dpi=300, bbox_inches='tight')
                    print(f"Saved combined chart: {output_file}")
                    plt.close(fig_combined)  # 关闭图形以释放内存
            else:
                print(f"No data found in {csv_file}")

if __name__ == "__main__":
    main()