import asyncio
import math
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
import json
from datetime import datetime
import os
import matplotlib.font_manager as fm
import warnings
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
import networkx as nx

# 导入现有的查询类
from firmagentsql.select import EnterpriseDataQuerier
from firmagentsql.latest_experiment_query import LatestExperimentQuery
from firmagentsql.config import DEFAULT_CONFIG, QueryConfig


# Setup fonts - Completely avoid Chinese font issues
def setup_fonts():
    """Setup font support"""
    try:
        # Suppress all font-related warnings
        warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')
        warnings.filterwarnings('ignore', message='.*Glyph.*missing from font.*')

        # Use English fonts to avoid Chinese character issues
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['font.sans-serif'] = ['Arial', 'Liberation Sans', 'Helvetica', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False
        plt.rcParams['font.size'] = 10

        # Set seaborn style
        sns.set_style("whitegrid")
        plt.rcParams['figure.figsize'] = (12, 8)

        print("Font setup completed - Using English display")

    except Exception as e:
        print(f"Font setup error: {e}")


# 初始化字体设置
setup_fonts()


class DataVisualization:
    """企业仿真数据可视化类"""

    def __init__(self, config: QueryConfig = None):
        self.config = config or DEFAULT_CONFIG
        self.querier = EnterpriseDataQuerier(self.config)
        self.exp_querier = LatestExperimentQuery(self.config)
        self.output_dir = "visualization_output"

        # 创建输出目录
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        # 指定的实验ID和run_uuid
        self.experiment_id = "e7ec8d6e-dbdb-4f59-8749-959b898d7613"
        self.run_uuid = "b07b54ee51bd416bba07bfd6b156c93f"

    async def connect(self):
        """建立数据库连接"""
        await self.querier.connect()
        print("Data visualization module connected to database")

    async def disconnect(self):
        """关闭数据库连接"""
        await self.querier.disconnect()
        print("Data visualization module disconnected from database")

    def query_transaction_value(self,data, company, step, product,role):
        """
        查询某公司在指定轮次、指定产品的交易数量和价格
        返回 (total_count, total_value, avg_price)
        - total_count: 总成交数量
        - total_value: 成交总价
        - avg_price: 加权平均价格
        """
        # 既当采购商也当供应商查
        subset = data[
            ((data[role] == company)) &
            (data["step"] == step) &
            (data["product_name"] == product)
        ]
        
        if subset.empty:
            return 0, 0.0, 0.0

        total_value = subset["total_value"].sum()
        avg_price = subset["avg_price"].sum()
        total_count = total_value / avg_price if avg_price > 0 else 0.0
        
        return int(total_count), float(total_value), float(avg_price)

    def query_produce_unfinished(self,csv_path: str, name: str, product_name: str, step: int = None):
        """
        查询指定公司和产品的 produce 和 unfinished 值。
        
        参数:
            csv_path: CSV 文件路径
            name: 公司名，如 "D2"
            product_name: 产品名，如 "26"
            step: 指定 step（可选），不传则返回最新值
        
        返回:
            dict: {"produce": int, "unfinished": int}
        """
        df = pd.read_csv(csv_path)
        
        # 构造 key
        produce_key = f"company_{name}_product_{product_name}_produce"
        unfinished_key = f"{name}_Unfinished_product_{product_name}"
        
        def get_value(key):
            df_key = df[df["key"] == key]
            if df_key.empty:
                return 0
            if step is not None:
                df_key_step = df_key[df_key["step"] == step]
                if df_key_step.empty:
                    return 0
                return int(df_key_step.iloc[0]["value"])
            else:
                return int(df_key.sort_values("step").iloc[-1]["value"])
        
        produce_val = get_value(produce_key)
        unfinished_val = get_value(unfinished_key)
        
        return {"produce": produce_val, "unfinished": unfinished_val}

    async def get_metrics_data(self, run_uuid: str, metric_pattern: str) -> pd.DataFrame:
        """从 metrics 表获取指定模式的指标数据

        Args:
            run_uuid: MLflow运行的UUID
            metric_pattern: 指标名称模式（用于LIKE查询）

        Returns:
            包含指标数据的DataFrame
        """
        query = """
        SELECT key, value, step, timestamp
        FROM metrics 
        WHERE run_uuid = %s AND key LIKE %s
        ORDER BY step, key
        """

        try:
            results = await self.querier.execute_query(query, (run_uuid, metric_pattern))
            if results:
                df = pd.DataFrame(results)
                return df
            else:
                print(f"No metrics data found for pattern: {metric_pattern}")
                return pd.DataFrame()
        except Exception as e:
            print(f"Error querying metrics data: {e}")
            return pd.DataFrame()

    async def _plot_new(self):
        step_length = 190
        fund_data = await self.get_metrics_data(self.run_uuid, 'company_fund_%')
        company_fund_dict = {
            company: df.set_index("step")["value"]
            for company, df in fund_data.groupby("key")
        }
        # print(company_fund_dict["company_fund_A1"].loc[50])
        
        company_info = {
            "company_id": [1, 2, 3, 4, 5, 6, 7, 8,9,10, 11, 12,13,14,15,16],
            "company_name": ["A1", "A2", "A3", "B1", "B2", "B3","C1", "C2", "C3","C4","C5", "D1", "D2","D3","D4","D5"]
        }
        id_to_name = dict(zip(company_info["company_id"], company_info["company_name"]))
        
        # print("id_to_name",id_to_name.get(1, "Unknown"))
        transactions = await self.querier.get_transaction_summary(self.experiment_id)
        if not transactions:
            print(f"No transaction data found for experiment {self.experiment_id}")
            return None

        df_transaction = pd.DataFrame(transactions)
        # count, value, price = self.query_transaction_value(df_transaction, company="4", step=4, product="product_6",role="purchaser_id")
        # print(f"交易数量={count}, 成交总价={value}, 平均单价={price}")

        # result = self.query_produce_unfinished("./firmagentsql/metrics.csv", "B1", "11",step=11)
        # print("result",result)

        company_list = [
            {
                "id":"4",
                "name":"B1",
                "product_name":"product_11",
                "cv_sell":0,
                "cv_count":0,
                "turn_prods":0,
                "sell_list":[],
                "count_list":[],
            },{
                "id":"4",
                "name":"B1",
                "product_name":"product_12",
                "cv_sell":0,
                "cv_count":0,
                "turn_prods":0,
                "sell_list":[],
                "count_list":[],
            },{
                "id":"5",
                "name":"B2",
                "product_name":"product_11",
                "cv_sell":0,
                "cv_count":0,
                "turn_prods":0,
                "sell_list":[],
                "count_list":[],
            },{
                "id":"5",
                "name":"B2",
                "product_name":"product_12",
                "cv_sell":0,
                "cv_count":0,
                "turn_prods":0,
                "sell_list":[],
                "count_list":[],
            },{
                "id":"6",
                "name":"B3",
                "product_name":"product_11",
                "cv_sell":0,
                "cv_count":0,
                "turn_prods":0,
                "sell_list":[],
                "count_list":[],
            },{
                "id":"6",
                "name":"B3",
                "product_name":"product_12",
                "cv_sell":0,
                "cv_count":0,
                "turn_prods":0,
                "sell_list":[],
                "count_list":[],
            },
            {
                "id":"7",
                "name":"C1",
                "product_name":"product_17",
                "cv_sell":0,
                "cv_count":0,
                "turn_prods":0,
                "sell_list":[],
                "count_list":[],
            },{
                "id":"8",
                "name":"C2",
                "product_name":"product_18",
                "cv_sell":0,
                "cv_count":0,
                "turn_prods":0,
                "sell_list":[],
                "count_list":[],
            },{
                "id":"9",
                "name":"C3",
                "product_name":"product_19",
                "cv_sell":0,
                "cv_count":0,
                "turn_prods":0,
                "sell_list":[],
                "count_list":[],
            },{
                "id":"10",
                "name":"C4",
                "product_name":"product_20",
                "cv_sell":0,
                "cv_count":0,
                "turn_prods":0,
                "sell_list":[],
                "count_list":[],
            },{
                "id":"11",
                "name":"C5",
                "product_name":"product_21",
                "cv_sell":0,
                "cv_count":0,
                "turn_prods":0,
                "sell_list":[],
                "count_list":[],
            }
        ]
        # for company in company_list:
        #     # 成交价/成交规模波动
        #     avg_price_list = []
        #     a_price = 0
        #     avg_count_list = []
        #     a_count = 0
            
        #     pre_count = 0.0
        #     pre_value=0.0
        #     length = 0
        #     for i in range(step_length+1):
        #         count, value, avg_price = self.query_transaction_value(df_transaction, company=company["id"], step=i, product=company["product_name"],role="supplier_id")
        #         if value > pre_value or count>pre_count or True:
        #             avg_price_list.append(avg_price)
        #             avg_count_list.append(count)
        #             a_price += avg_price
        #             a_count += count
        #             length +=1
        #             if company["id"] == "4":
        #                 print(i,count,value,avg_price)
        #         pre_count = count
        #         pre_value = value
        #     company["sell_list"] = avg_price_list
        #     company["count_list"] = avg_count_list
        #     a_price = a_price / length
        #     a_count = a_count / length
        #     p_sell = 0
        #     p_count = 0
        #     for price in avg_price_list:
        #         p_sell += math.pow(price-a_price,2)
        #     for count in avg_count_list:
        #         p_count += math.pow(count-a_count,2)
        #     p_sell = p_sell / length
        #     p_count = p_count / length
        #     #  成交价标准差
        #     p_sell = math.sqrt(p_sell)
        #     #  成交规模标准差
        #     p_count = math.sqrt(p_count)
        #     # 变异系数  变异系数越大，表示价格波动相对于其均值更为剧烈。这个值对于判断企业定价策略的灵活性有很大帮助
        #     cv_sell = p_sell / a_price
        #     cv_count = p_count / a_count
        #     company["cv_sell"] = cv_sell
        #     company["cv_count"] = cv_count
        #     if company["id"] == "4":
        #         print(length)
        # output_dir = "charts"
        # os.makedirs(output_dir, exist_ok=True)

        # 遍历每个公司/产品
        # for comp in company_list:
        #     name = comp["name"]
        #     product = comp["product_name"]

        #     # # --- 折线图1：sell_list ---
        #     if comp["sell_list"]:
            #     plt.figure(figsize=(8, 5))
            #     plt.plot(range(1, len(comp["sell_list"]) + 1), comp["sell_list"], marker="o", color="blue")
            #     plt.title(f"{name} - {product} : Sell List Trend")
            #     plt.xlabel("Time Index")
            #     plt.ylabel("Sell Value")
            #     plt.grid(True, linestyle="--", alpha=0.6)
            #     plt.tight_layout()
            #     file_path = os.path.join(output_dir, f"{name}_{product}_sell.png")
            #     plt.savefig(file_path, dpi=300)
            #     plt.close()

            # # --- 折线图2：count_list ---
            # if comp["count_list"]:
            #     plt.figure(figsize=(8, 5))
            #     plt.plot(range(1, len(comp["count_list"]) + 1), comp["count_list"], marker="o", color="green")
            #     plt.title(f"{name} - {product} : Count List Trend")
            #     plt.xlabel("Time Index")
            #     plt.ylabel("Count Value")
            #     plt.grid(True, linestyle="--", alpha=0.6)
            #     plt.tight_layout()
            #     file_path = os.path.join(output_dir, f"{name}_{product}_count.png")
            #     plt.savefig(file_path, dpi=300)
        #     #     plt.close()
        # for company in company_list:
        #     inventory_data = await self.get_metrics_data(self.run_uuid, f'product_inventory_{company["name"]}_{company["product_name"]}')
        #     all_stock = 0
        #     all_count = 0
        #     for i in range(step_length+1):
        #         stock = inventory_data.loc[inventory_data["step"] == i, "value"].squeeze()
        #         count, value, avg_price = self.query_transaction_value(df_transaction, company=company["id"], step=i, product=company["product_name"],role="supplier_id")
        #         all_stock += stock
        #         all_count += count
        #     a_stock = all_stock / step_length
        #     # 成品周转率 库存转化为销售的频率。较高的周转率意味着企业能够更快速地销售库存，从而减少资金占用。
        #     turn_prods = all_count / (a_stock * all_stock)
        #     company["turn_prods"] = turn_prods

        # 资金占用率 ：每单位库存和产品占用资金的比例，资本效率越高，说明企业对资金的使用更有效，能够更快地实现库存周转
        company_list2 = [
            # {
            #     "id":"4",
            #     "name":"B1",
            #     "fund_efficiency":0
            # },{
            #     "id":"5",
            #     "name":"B2",
            #     "fund_efficiency":0
            # },{
            #     "id":"6",
            #     "name":"B3",
            #     "fund_efficiency":0
            # },
            {
                "id":"7",
                "name":"C1",
                "fund_efficiency":0
            },{
                "id":"8",
                "name":"C2",
                "fund_efficiency":0
            },{
                "id":"9",
                "name":"C3",
                "fund_efficiency":0
            },{
                "id":"10",
                "name":"C4",
                "fund_efficiency":0
            },{
                "id":"11",
                "name":"C5",
                "fund_efficiency":0
            }
        ]
        for company in company_list2:
            all_fund = 0
            all_product = 0
            all_material = 0
            product_data = await self.get_metrics_data(self.run_uuid, f'total_product_inventory_{company["name"]}')
            material_data = await self.get_metrics_data(self.run_uuid, f'total_material_inventory_{company["name"]}')
            for i in range(step_length+1):
                fund = company_fund_dict[f"company_fund_{company["name"]}"].loc[i]
                all_fund += fund
                stock = product_data.loc[product_data["step"] == i, "value"].squeeze()
                all_product += stock
                material = material_data.loc[material_data["step"] == i, "value"].squeeze()
                all_material += material
            avg_fund = all_fund / step_length
            avg_product = all_product / step_length
            avg_material = all_material / step_length
            fund_efficiency = avg_fund / (avg_product + avg_material)
            company["fund_efficiency"] = fund_efficiency
        
        # # 转换成 DataFrame
        df = pd.DataFrame(company_list)
        df["label"] = df["name"] + " - " + df["product_name"]

        # # --- 图1: 价格变异系数 (折线图) ---
        # plt.figure(figsize=(10, 6))
        # plt.plot(df["label"], df["cv_sell"], marker="o", color="blue")
        # plt.xticks(rotation=45, ha="right")
        # plt.ylabel("Price Coefficient of Variation")
        # plt.title("Transaction price fluctuation")
        # plt.tight_layout()
        # plt.savefig("cv_sell_line.png", dpi=300)
        # plt.close()

        # # --- 图2: 交易量变异系数 (折线图) ---
        # plt.figure(figsize=(8, 6))
        # plt.plot(df["label"], df["cv_count"], marker="o", color="blue")
        # plt.xticks(rotation=45, ha="right")
        # plt.ylabel("Count Coefficient of Variation")
        # plt.title("Transaction volume fluctuation")
        # plt.tight_layout()
        # plt.savefig("cv_count_box.png", dpi=300)
        # plt.close()

        # # --- 图3: 成品转换率 (热力图) ---
        # pivot_df = df.pivot(index="name", columns="product_name", values="turn_prods")

        # plt.figure(figsize=(8, 6))
        # sns.heatmap(pivot_df, annot=True, fmt=".2e", cmap="YlOrRd", cbar_kws={'label': 'turn_prods'})
        # plt.title("Finished Product Conversion Rate Heatmap")
        # plt.tight_layout()
        # plt.savefig("B类_turn_prods_heatmap.png", dpi=300)
        # plt.close()

        # 转 DataFrame
        df = pd.DataFrame(company_list2)

        # 维度 & 数据
        labels = df["name"].tolist()
        values = df["fund_efficiency"].tolist()

        # 角度划分
        angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()

        # 闭合
        values += values[:1]
        angles += angles[:1]

        # 绘制雷达图
        plt.figure(figsize=(8, 8))
        ax = plt.subplot(111, polar=True)

        ax.plot(angles, values, 'o-', linewidth=2, label="fund_efficiency")
        ax.fill(angles, values, alpha=0.25)

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels)

        plt.title("Capital Occupancy Radar Chart", y=1.1)
        plt.legend(loc="upper right", bbox_to_anchor=(1.1, 1.1))
        plt.tight_layout()
        plt.savefig("C类_fund_efficiency_radar.png", dpi=300)
        plt.show()

 
    
    def query_produce_unfinished(self,csv_path: str, name: str, product_name: str, step: int = None):
        df = pd.read_csv(csv_path)
        
        # 构造 key
        unfinished_key = f"{name}_Unfinished_product_{product_name}"
        product_inventory_key = f"product_inventory_{name}_product_{product_name}"
        supply_amount_key = f"supply_amount_{name}_product_{product_name}"
        
        def get_value(key):
            df_key = df[df["key"] == key]
            if df_key.empty:
                return 0
            if step is not None:
                df_key_step = df_key[df_key["step"] == step]
                if df_key_step.empty:
                    return 0
                return int(df_key_step.iloc[0]["value"])
            else:
                return int(df_key.sort_values("step").iloc[-1]["value"])
        
        unfinished_val = get_value(unfinished_key)
        product_inventory_val = get_value(product_inventory_key)
        supply_amount_val = get_value(supply_amount_key)
        
        return {"unfinished": unfinished_val,"product_inventory":product_inventory_val,"supply_amount":supply_amount_val}


    def _plot_data(self):
        product_11_list = []
        for i in range(191):
            OGR1 = 0
            OGR2 = 0
            OGR3 = 0
            UR1 = 0
            UR2 = 0
            UR3 = 0
            ICR1 = 0
            ICR2 = 0
            ICR3 = 0

            if i > 0:
                result1 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B1", "11",step=i-1)
                result2 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B1", "11",step=i)
                if result1["supply_amount"] != 0:
                    OGR1 = result2["supply_amount"] -  result1["supply_amount"]
                    OGR1 = OGR1 /  result1["supply_amount"]
                if result1["unfinished"] != 0:
                    UR1 = result2["unfinished"] -  result1["unfinished"]
                    UR1 = UR1 /  result1["unfinished"]
                if result1["supply_amount"] != 0:
                    ICR1 = result2["supply_amount"] -  result1["unfinished"]
                    ICR1 = ICR1 /  result1["supply_amount"]

                result3 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B2", "11",step=i-1)
                result4 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B2", "11",step=i)
                if result3["supply_amount"] != 0:
                    OGR2 = result4["supply_amount"] -  result3["supply_amount"]
                    OGR2 = OGR2 /  result3["supply_amount"]
                if result3["unfinished"] != 0:
                    UR2 = result4["unfinished"] -  result3["unfinished"]
                    UR2 = UR2 /  result3["unfinished"]
                if result3["supply_amount"] != 0:
                    ICR2 = result4["supply_amount"] -  result3["unfinished"]
                    ICR2 = ICR2 /  result3["supply_amount"]

                result5 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B3", "11",step=i-1)
                result6 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B3", "11",step=i)
                if result5["supply_amount"] != 0:
                    OGR3 = result6["supply_amount"] -  result5["supply_amount"]
                    OGR3 = OGR3 /  result5["supply_amount"]
                if result5["unfinished"] != 0:
                    UR3 = result6["unfinished"] -  result5["unfinished"]
                    UR3 = UR3 /  result5["unfinished"]
                if result5["supply_amount"] != 0:
                    ICR3 = result6["supply_amount"] -  result5["unfinished"]
                    ICR3 = ICR3 /  result5["supply_amount"]

                OGRmax = max(OGR1,OGR2,OGR3)
                OGRmin = min(OGR1,OGR2,OGR3)
                if OGRmax==OGRmin:
                    OGRnorml1=0
                    OGRnorml2=0
                    OGRnorml3=0
                else:
                    OGRnorml1 =  (OGR1 - OGRmin) / (OGRmax-OGRmin)
                    OGRnorml2 =  (OGR2 - OGRmin) / (OGRmax-OGRmin)
                    OGRnorml3 =  (OGR3 - OGRmin) / (OGRmax-OGRmin)

                URmax = max(UR1,UR2,UR3)
                URmin = min(UR1,UR2,UR3)
                if URmax==URmin:
                    URnorml1=0
                    URnorml2=0
                    URnorml3=0
                else:
                    URnorml1 =  (UR1 - URmin) / (URmax-URmin)
                    URnorml2 =  (UR2 - URmin) / (URmax-URmin)
                    URnorml3 =  (UR3 - URmin) / (URmax-URmin)

                ICRmax = max(ICR1,ICR2,ICR3)
                ICRmin = min(ICR1,ICR2,ICR3)
                if ICRmax==ICRmin:
                    ICRnorml1=0
                    ICRnorml2=0
                    ICRnorml3=0
                else:
                    ICRnorml1 =  (ICR1 - ICRmin) / (ICRmax-ICRmin)
                    ICRnorml2 =  (ICR2 - ICRmin) / (ICRmax-ICRmin)
                    ICRnorml3 =  (ICR3 - ICRmin) / (ICRmax-ICRmin)
                product_11_list.append({
                    "B1":0.3*OGRnorml1+0.5*URnorml1+0.2*ICRnorml1,
                    "B2":0.3*OGRnorml2+0.5*URnorml2+0.2*ICRnorml2,
                    "B3":0.3*OGRnorml3+0.5*URnorml3+0.2*ICRnorml3,
                })
        
        product_12_list = []
        for i in range(191):
            OGR1 = 0
            OGR2 = 0
            OGR3 = 0
            UR1 = 0
            UR2 = 0
            UR3 = 0
            ICR1 = 0
            ICR2 = 0
            ICR3 = 0
            if i > 0:
                result1 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B1", "12",step=i-1)
                result2 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B1", "12",step=i)
                if result1["supply_amount"] != 0:
                    OGR1 = result2["supply_amount"] -  result1["supply_amount"]
                    OGR1 = OGR1 /  result1["supply_amount"]
                if result1["unfinished"] != 0:
                    UR1 = result2["unfinished"] -  result1["unfinished"]
                    UR1 = UR1 /  result1["unfinished"]
                if result1["supply_amount"] != 0:
                    ICR1 = result2["supply_amount"] -  result1["unfinished"]
                    ICR1 = ICR1 /  result1["supply_amount"]

                result3 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B2", "12",step=i-1)
                result4 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B2", "12",step=i)
                if result3["supply_amount"] != 0:
                    OGR2 = result4["supply_amount"] -  result3["supply_amount"]
                    OGR2 = OGR2 /  result3["supply_amount"]
                if result3["unfinished"] != 0:
                    UR2 = result4["unfinished"] -  result3["unfinished"]
                    UR2 = UR2 /  result3["unfinished"]
                if result3["supply_amount"] != 0:
                    ICR2 = result4["supply_amount"] -  result3["unfinished"]
                    ICR2 = ICR2 /  result3["supply_amount"]

                result5 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B3", "12",step=i-1)
                result6 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B3", "12",step=i)
                if result5["supply_amount"] != 0:
                    OGR3 = result6["supply_amount"] -  result5["supply_amount"]
                    OGR3 = OGR3 /  result5["supply_amount"]
                if result5["unfinished"] != 0:
                    UR3 = result6["unfinished"] -  result5["unfinished"]
                    UR3 = UR3 /  result5["unfinished"]
                if result5["supply_amount"] != 0:
                    ICR3 = result6["supply_amount"] -  result5["unfinished"]
                    ICR3 = ICR3 /  result5["supply_amount"]

                OGRmax = max(OGR1,OGR2,OGR3)
                OGRmin = min(OGR1,OGR2,OGR3)
                if OGRmax==OGRmin:
                    OGRnorml1=0
                    OGRnorml2=0
                    OGRnorml3=0
                else:
                    OGRnorml1 =  (OGR1 - OGRmin) / (OGRmax-OGRmin)
                    OGRnorml2 =  (OGR2 - OGRmin) / (OGRmax-OGRmin)
                    OGRnorml3 =  (OGR3 - OGRmin) / (OGRmax-OGRmin)

                URmax = max(UR1,UR2,UR3)
                URmin = min(UR1,UR2,UR3)
                if URmax==URmin:
                    URnorml1=0
                    URnorml2=0
                    URnorml3=0
                else:
                    URnorml1 =  (UR1 - URmin) / (URmax-URmin)
                    URnorml2 =  (UR2 - URmin) / (URmax-URmin)
                    URnorml3 =  (UR3 - URmin) / (URmax-URmin)

                ICRmax = max(ICR1,ICR2,ICR3)
                ICRmin = min(ICR1,ICR2,ICR3)
                if ICRmax==ICRmin:
                    ICRnorml1=0
                    ICRnorml2=0
                    ICRnorml3=0
                else:
                    ICRnorml1 =  (ICR1 - ICRmin) / (ICRmax-ICRmin)
                    ICRnorml2 =  (ICR2 - ICRmin) / (ICRmax-ICRmin)
                    ICRnorml3 =  (ICR3 - ICRmin) / (ICRmax-ICRmin)
                product_12_list.append({
                    "B1":0.3*OGRnorml1+0.5*URnorml1+0.2*ICRnorml1,
                    "B2":0.3*OGRnorml2+0.5*URnorml2+0.2*ICRnorml2,
                    "B3":0.3*OGRnorml3+0.5*URnorml3+0.2*ICRnorml3,
                })

        danger_list = []
        b1_avg = 0
        b2_avg = 0
        b3_avg = 0
        b1_high = 0
        b2_high = 0
        b3_high = 0
        for d1, d2 in zip(product_11_list, product_12_list):
            danger_list.append({
                "B1":(d1["B1"]+d2["B1"])/2,
                "B2":(d1["B2"]+d2["B2"])/2,
                "B3":(d1["B3"]+d2["B3"])/2,
            })
            b1_avg+=(d1["B1"]+d2["B1"])/2
            b2_avg+= (d1["B2"]+d2["B2"])/2
            b3_avg+= (d1["B3"]+d2["B3"])/2
            if (d1["B1"]+d2["B1"])/2 > 0.67:
                b1_high +=1
            if (d1["B2"]+d2["B2"])/2 > 0.67:
                b2_high +=1
            if (d1["B3"]+d2["B3"])/2 > 0.67:
                b3_high +=1
        b1_high = b1_high / 190
        b2_high = b2_high / 190
        b3_high = b3_high / 190

        
        b1_avg = b1_avg / 190
        b2_avg = b2_avg / 190
        b3_avg = b3_avg / 190

        print(b1_avg,b2_avg,b3_avg)
        print(b1_high,b2_high,b3_high)
        # # 假设 B1_11_list 已经有数据
        # 将三个属性分别提取出来
        B1 = [item["B1"] for item in danger_list]
        # B2 = [item["B2"] for item in danger_list]
        # B3 = [item["B3"] for item in danger_list]

        # x 轴为迭代次数（第几个点）
        x = range(1, len(danger_list) + 1)

        # 绘制折线图
        plt.figure(figsize=(8, 5))
        plt.plot(x, B1, marker="o", label="B1")
        # plt.plot(x, B2, marker="s", label="B2")
        # plt.plot(x, B3, marker="^", label="B3")

        plt.xlabel("Step")
        plt.ylabel("Value")
        plt.title("danger_change")
        plt.legend()
        plt.grid(True)
        plt.show()
        plt.savefig("gpt_B1.png", dpi=300)

    def _plot_New_data(self):
        product_11_list = []

        # --- 新增：为 OGR/UR/ICR 做累加器（按产品、按公司） ---
        ogr_sum_11 = {"B1": 0.0, "B2": 0.0, "B3": 0.0}
        ur_sum_11  = {"B1": 0.0, "B2": 0.0, "B3": 0.0}
        icr_sum_11 = {"B1": 0.0, "B2": 0.0, "B3": 0.0}
        ogr_cnt_11 = {"B1": 0, "B2": 0, "B3": 0}
        ur_cnt_11  = {"B1": 0, "B2": 0, "B3": 0}
        icr_cnt_11 = {"B1": 0, "B2": 0, "B3": 0}

        for i in range(191):
            OGR1 = OGR2 = OGR3 = 0
            UR1  = UR2  = UR3  = 0
            ICR1 = ICR2 = ICR3 = 0

            if i > 0:
                # B1, product_11
                result1 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B1", "11", step=i-1)
                result2 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B1", "11", step=i)
                if result1["supply_amount"] != 0:
                    OGR1 = (result2["supply_amount"] - result1["supply_amount"]) / result1["supply_amount"]
                    ICR1 = (result2["supply_amount"] - result1["unfinished"]) / result1["supply_amount"]
                    ogr_sum_11["B1"] += OGR1; ogr_cnt_11["B1"] += 1
                    icr_sum_11["B1"] += ICR1; icr_cnt_11["B1"] += 1
                if result1["unfinished"] != 0:
                    UR1 = (result2["unfinished"] - result1["unfinished"]) / result1["unfinished"]
                    ur_sum_11["B1"] += UR1; ur_cnt_11["B1"] += 1

                # B2, product_11
                result3 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B2", "11", step=i-1)
                result4 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B2", "11", step=i)
                if result3["supply_amount"] != 0:
                    OGR2 = (result4["supply_amount"] - result3["supply_amount"]) / result3["supply_amount"]
                    ICR2 = (result4["supply_amount"] - result3["unfinished"]) / result3["supply_amount"]
                    ogr_sum_11["B2"] += OGR2; ogr_cnt_11["B2"] += 1
                    icr_sum_11["B2"] += ICR2; icr_cnt_11["B2"] += 1
                if result3["unfinished"] != 0:
                    UR2 = (result4["unfinished"] - result3["unfinished"]) / result3["unfinished"]
                    ur_sum_11["B2"] += UR2; ur_cnt_11["B2"] += 1

                # B3, product_11
                result5 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B3", "11", step=i-1)
                result6 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B3", "11", step=i)
                if result5["supply_amount"] != 0:
                    OGR3 = (result6["supply_amount"] - result5["supply_amount"]) / result5["supply_amount"]
                    ICR3 = (result6["supply_amount"] - result5["unfinished"]) / result5["supply_amount"]
                    ogr_sum_11["B3"] += OGR3; ogr_cnt_11["B3"] += 1
                    icr_sum_11["B3"] += ICR3; icr_cnt_11["B3"] += 1
                if result5["unfinished"] != 0:
                    UR3 = (result6["unfinished"] - result5["unfinished"]) / result5["unfinished"]
                    ur_sum_11["B3"] += UR3; ur_cnt_11["B3"] += 1

                # 归一化 + 危险系数（保持你原来的做法）
                OGRmax, OGRmin = max(OGR1, OGR2, OGR3), min(OGR1, OGR2, OGR3)
                if OGRmax == OGRmin:
                    OGRnorml1 = OGRnorml2 = OGRnorml3 = 0
                else:
                    OGRnorml1 = (OGR1 - OGRmin) / (OGRmax - OGRmin)
                    OGRnorml2 = (OGR2 - OGRmin) / (OGRmax - OGRmin)
                    OGRnorml3 = (OGR3 - OGRmin) / (OGRmax - OGRmin)

                URmax, URmin = max(UR1, UR2, UR3), min(UR1, UR2, UR3)
                if URmax == URmin:
                    URnorml1 = URnorml2 = URnorml3 = 0
                else:
                    URnorml1 = (UR1 - URmin) / (URmax - URmin)
                    URnorml2 = (UR2 - URmin) / (URmax - URmin)
                    URnorml3 = (UR3 - URmin) / (URmax - URmin)

                ICRmax, ICRmin = max(ICR1, ICR2, ICR3), min(ICR1, ICR2, ICR3)
                if ICRmax == ICRmin:
                    ICRnorml1 = ICRnorml2 = ICRnorml3 = 0
                else:
                    ICRnorml1 = (ICR1 - ICRmin) / (ICRmax - ICRmin)
                    ICRnorml2 = (ICR2 - ICRmin) / (ICRmax - ICRmin)
                    ICRnorml3 = (ICR3 - ICRmin) / (ICRmax - ICRmin)

                product_11_list.append({
                    "B1": 0.3 * OGRnorml1 + 0.5 * URnorml1 + 0.2 * ICRnorml1,
                    "B2": 0.3 * OGRnorml2 + 0.5 * URnorml2 + 0.2 * ICRnorml2,
                    "B3": 0.3 * OGRnorml3 + 0.5 * URnorml3 + 0.2 * ICRnorml3,
                })

        product_12_list = []

        # --- 新增：为 OGR/UR/ICR 做累加器（按产品、按公司） ---
        ogr_sum_12 = {"B1": 0.0, "B2": 0.0, "B3": 0.0}
        ur_sum_12  = {"B1": 0.0, "B2": 0.0, "B3": 0.0}
        icr_sum_12 = {"B1": 0.0, "B2": 0.0, "B3": 0.0}
        ogr_cnt_12 = {"B1": 0, "B2": 0, "B3": 0}
        ur_cnt_12  = {"B1": 0, "B2": 0, "B3": 0}
        icr_cnt_12 = {"B1": 0, "B2": 0, "B3": 0}

        for i in range(191):
            OGR1 = OGR2 = OGR3 = 0
            UR1  = UR2  = UR3  = 0
            ICR1 = ICR2 = ICR3 = 0

            if i > 0:
                # B1, product_12
                result1 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B1", "12", step=i-1)
                result2 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B1", "12", step=i)
                if result1["supply_amount"] != 0:
                    OGR1 = (result2["supply_amount"] - result1["supply_amount"]) / result1["supply_amount"]
                    ICR1 = (result2["supply_amount"] - result1["unfinished"]) / result1["supply_amount"]
                    ogr_sum_12["B1"] += OGR1; ogr_cnt_12["B1"] += 1
                    icr_sum_12["B1"] += ICR1; icr_cnt_12["B1"] += 1
                if result1["unfinished"] != 0:
                    UR1 = (result2["unfinished"] - result1["unfinished"]) / result1["unfinished"]
                    ur_sum_12["B1"] += UR1; ur_cnt_12["B1"] += 1

                # B2, product_12
                result3 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B2", "12", step=i-1)
                result4 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B2", "12", step=i)
                if result3["supply_amount"] != 0:
                    OGR2 = (result4["supply_amount"] - result3["supply_amount"]) / result3["supply_amount"]
                    ICR2 = (result4["supply_amount"] - result3["unfinished"]) / result3["supply_amount"]
                    ogr_sum_12["B2"] += OGR2; ogr_cnt_12["B2"] += 1
                    icr_sum_12["B2"] += ICR2; icr_cnt_12["B2"] += 1
                if result3["unfinished"] != 0:
                    UR2 = (result4["unfinished"] - result3["unfinished"]) / result3["unfinished"]
                    ur_sum_12["B2"] += UR2; ur_cnt_12["B2"] += 1

                # B3, product_12
                result5 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B3", "12", step=i-1)
                result6 = self.query_produce_unfinished("./firmagentsql/metrics_deepseek.csv", "B3", "12", step=i)
                if result5["supply_amount"] != 0:
                    OGR3 = (result6["supply_amount"] - result5["supply_amount"]) / result5["supply_amount"]
                    ICR3 = (result6["supply_amount"] - result5["unfinished"]) / result5["supply_amount"]
                    ogr_sum_12["B3"] += OGR3; ogr_cnt_12["B3"] += 1
                    icr_sum_12["B3"] += ICR3; icr_cnt_12["B3"] += 1
                if result5["unfinished"] != 0:
                    UR3 = (result6["unfinished"] - result5["unfinished"]) / result5["unfinished"]
                    ur_sum_12["B3"] += UR3; ur_cnt_12["B3"] += 1

                # 归一化 + 危险系数（保持你原来的做法）
                OGRmax, OGRmin = max(OGR1, OGR2, OGR3), min(OGR1, OGR2, OGR3)
                if OGRmax == OGRmin:
                    OGRnorml1 = OGRnorml2 = OGRnorml3 = 0
                else:
                    OGRnorml1 = (OGR1 - OGRmin) / (OGRmax - OGRmin)
                    OGRnorml2 = (OGR2 - OGRmin) / (OGRmax - OGRmin)
                    OGRnorml3 = (OGR3 - OGRmin) / (OGRmax - OGRmin)

                URmax, URmin = max(UR1, UR2, UR3), min(UR1, UR2, UR3)
                if URmax == URmin:
                    URnorml1 = URnorml2 = URnorml3 = 0
                else:
                    URnorml1 = (UR1 - URmin) / (URmax - URmin)
                    URnorml2 = (UR2 - URmin) / (URmax - URmin)
                    URnorml3 = (UR3 - URmin) / (URmax - URmin)

                ICRmax, ICRmin = max(ICR1, ICR2, ICR3), min(ICR1, ICR2, ICR3)
                if ICRmax == ICRmin:
                    ICRnorml1 = ICRnorml2 = ICRnorml3 = 0
                else:
                    ICRnorml1 = (ICR1 - ICRmin) / (ICRmax - ICRmin)
                    ICRnorml2 = (ICR2 - ICRmin) / (ICRmax - ICRmin)
                    ICRnorml3 = (ICR3 - ICRmin) / (ICRmax - ICRmin)

                product_12_list.append({
                    "B1": 0.3 * OGRnorml1 + 0.5 * URnorml1 + 0.2 * ICRnorml1,
                    "B2": 0.3 * OGRnorml2 + 0.5 * URnorml2 + 0.2 * ICRnorml2,
                    "B3": 0.3 * OGRnorml3 + 0.5 * URnorml3 + 0.2 * ICRnorml3,
                })

        # --- 你原有的危险系数统计 ---
        danger_list = []
        b1_avg = b2_avg = b3_avg = 0
        b1_high = b2_high = b3_high = 0
        for d1, d2 in zip(product_11_list, product_12_list):
            danger_list.append({
                "B1": (d1["B1"] + d2["B1"]) / 2,
                "B2": (d1["B2"] + d2["B2"]) / 2,
                "B3": (d1["B3"] + d2["B3"]) / 2,
            })
            b1_avg += (d1["B1"] + d2["B1"]) / 2
            b2_avg += (d1["B2"] + d2["B2"]) / 2
            b3_avg += (d1["B3"] + d2["B3"]) / 2
            if (d1["B1"] + d2["B1"]) / 2 > 0.67: b1_high += 1
            if (d1["B2"] + d2["B2"]) / 2 > 0.67: b2_high += 1
            if (d1["B3"] + d2["B3"]) / 2 > 0.67: b3_high += 1

        b1_high /= 190; b2_high /= 190; b3_high /= 190
        b1_avg  /= 190; b2_avg  /= 190; b3_avg  /= 190

        print("Danger avg:", b1_avg, b2_avg, b3_avg)
        print("Danger high ratio:", b1_high, b2_high, b3_high)

        # --- 计算 OGR/UR/ICR 的“产品内均值”（按公司） ---
        def safe_avg(s, c):  # 避免除零
            return {k: (s[k] / c[k]) if c[k] > 0 else None for k in s.keys()}

        ogr_avg_11 = safe_avg(ogr_sum_11, ogr_cnt_11)
        ur_avg_11  = safe_avg(ur_sum_11,  ur_cnt_11)
        icr_avg_11 = safe_avg(icr_sum_11, icr_cnt_11)

        ogr_avg_12 = safe_avg(ogr_sum_12, ogr_cnt_12)
        ur_avg_12  = safe_avg(ur_sum_12,  ur_cnt_12)
        icr_avg_12 = safe_avg(icr_sum_12, icr_cnt_12)

        print("Product_11 OGR avg:", ogr_avg_11)
        print("Product_11 UR  avg:", ur_avg_11)
        print("Product_11 ICR avg:", icr_avg_11)

        print("Product_12 OGR avg:", ogr_avg_12)
        print("Product_12 UR  avg:", ur_avg_12)
        print("Product_12 ICR avg:", icr_avg_12)

        # --- 计算两个产品“合并均值”（按公司，按计数加权）---
        ogr_sum_all = {k: ogr_sum_11[k] + ogr_sum_12[k] for k in ogr_sum_11.keys()}
        ur_sum_all  = {k: ur_sum_11[k]  + ur_sum_12[k]  for k in ur_sum_11.keys()}
        icr_sum_all = {k: icr_sum_11[k] + icr_sum_12[k] for k in icr_sum_11.keys()}

        ogr_cnt_all = {k: ogr_cnt_11[k] + ogr_cnt_12[k] for k in ogr_cnt_11.keys()}
        ur_cnt_all  = {k: ur_cnt_11[k]  + ur_cnt_12[k]  for k in ur_cnt_11.keys()}
        icr_cnt_all = {k: icr_cnt_11[k] + icr_cnt_12[k] for k in icr_cnt_11.keys()}

        ogr_avg_all = safe_avg(ogr_sum_all, ogr_cnt_all)
        ur_avg_all  = safe_avg(ur_sum_all,  ur_cnt_all)
        icr_avg_all = safe_avg(icr_sum_all, icr_cnt_all)

        print("Combined OGR avg (P11+P12):", ogr_avg_all)
        print("Combined UR  avg (P11+P12):", ur_avg_all)
        print("Combined ICR avg (P11+P12):", icr_avg_all)

        import pandas as pd
        import numpy as np
        import matplotlib.pyplot as plt

        # ---- 1) 组装为统一的 DataFrame（按指标 × 范围汇总到一张表） ----
        def to_series(d, name):
            # 将 {"B1": v1, "B2": v2, "B3": v3} -> pandas.Series；把 None 转为 NaN
            return pd.Series({k: (np.nan if d[k] is None else d[k]) for k in ["B1","B2","B3"]}, name=name)

        rows = []

        # 危险系数（两产品均值后的公司均值 & 高风险比例）
        rows.append(to_series({"B1": b1_avg, "B2": b2_avg, "B3": b3_avg}, ("Danger Avg", "Combined")))
        rows.append(to_series({"B1": b1_high, "B2": b2_high, "B3": b3_high}, ("Danger High Ratio(>0.67)", "Combined")))

        # OGR / UR / ICR - Product 11
        rows.append(to_series(ogr_avg_11, ("OGR Avg", "Product_11")))
        rows.append(to_series(ur_avg_11,  ("UR Avg",  "Product_11")))
        rows.append(to_series(icr_avg_11, ("ICR Avg", "Product_11")))

        # OGR / UR / ICR - Product 12
        rows.append(to_series(ogr_avg_12, ("OGR Avg", "Product_12")))
        rows.append(to_series(ur_avg_12,  ("UR Avg",  "Product_12")))
        rows.append(to_series(icr_avg_12, ("ICR Avg", "Product_12")))

        # OGR / UR / ICR - Combined (P11+P12 计数加权)
        rows.append(to_series(ogr_avg_all, ("OGR Avg", "Combined")))
        rows.append(to_series(ur_avg_all,  ("UR Avg",  "Combined")))
        rows.append(to_series(icr_avg_all, ("ICR Avg", "Combined")))

        df = pd.DataFrame(rows)
        df.index = pd.MultiIndex.from_tuples(df.index, names=["Metric", "Scope"])
        df = df[["B1","B2","B3"]]  # 固定列顺序

        # ---- 2) 导出 CSV（便于留档） ----
        df.to_csv("metrics_summary.csv", float_format="%.6f")

        # ---- 3) 渲染为表格图片并保存 PNG ----
        # 注：不使用 seaborn，仅用 matplotlib；自适应行高/列宽，适合论文/汇报粘贴
        fig, ax = plt.subplots(figsize=(10, max(3.5, 0.45 * len(df) + 1)))  # 高度随行数伸缩
        ax.axis("off")

        # 将 MultiIndex 拆成两列展示：Metric, Scope
        df_to_show = df.copy()
        df_to_show.insert(0, "Scope", [idx[1] for idx in df_to_show.index])
        df_to_show.insert(0, "Metric", [idx[0] for idx in df_to_show.index])

        # 数字格式化（保留4位小数），NaN 显示为 "-"
        df_fmt = df_to_show.copy()
        for col in ["B1","B2","B3"]:
            df_fmt[col] = df_fmt[col].map(lambda x: "-" if pd.isna(x) else f"{x:.4f}")

        # 生成表格
        table = ax.table(
            cellText=df_fmt.values,
            colLabels=df_fmt.columns,
            cellLoc="center",
            loc="center"
        )

        # 样式美化
        table.auto_set_font_size(False)
        table.set_fontsize(10)

        # 列宽自适应
        col_widths = [0.18, 0.16, 0.22, 0.22, 0.22]  # Metric, Scope, B1,B2,B3
        for i, w in enumerate(col_widths):
            table.auto_set_column_width(col=i)
            table._cells[(0,i)].set_width(w)  # header
            for r in range(1, len(df_fmt) + 1):
                table._cells[(r,i)].set_width(w)

        # 交替行底色，增强可读性
        for r in range(1, len(df_fmt) + 1):
            for c in range(len(df_fmt.columns)):
                if r % 2 == 0:
                    table._cells[(r, c)].set_facecolor("#F5F7FA")  # 淡灰蓝
                else:
                    table._cells[(r, c)].set_facecolor("#FFFFFF")

        # Header 行加粗
        for c in range(len(df_fmt.columns)):
            cell = table._cells[(0, c)]
            cell.set_facecolor("#E9EEF5")
            cell.set_text_props(weight="bold")

        # 标题
        title = "Summary of OGR / UR / ICR Averages and Danger Indicators (B1–B3)"
        ax.set_title(title, fontsize=12, pad=12)

        plt.tight_layout()
        plt.savefig("metrics_summary.png", dpi=300, bbox_inches="tight")
        plt.close(fig)

        print("Saved: metrics_summary.png & metrics_summary.csv")
        import pandas as pd
        import numpy as np
        import matplotlib.pyplot as plt
        from textwrap import dedent

        # --- 读取你之前导出的汇总 ---
        df = pd.read_csv("metrics_summary.csv", index_col=[0,1])  # MultiIndex: (Metric, Scope)
        df = df[["B1","B2","B3"]].astype(float)

        # 统一格式化函数
        def fmt(x):
            return "-" if pd.isna(x) else f"{x:.3f}"

        # 拉取特定行的便捷函数
        def row(metric, scope):
            s = df.loc[(metric, scope)]
            return fmt(s["B1"]), fmt(s["B2"]), fmt(s["B3"])

        # ---- 1) 生成 LaTeX (booktabs) 文件 ----
        sections = [
            ("Danger Indicators", [
                ("Danger Avg", "Combined"),
                ("Danger High Ratio(>0.67)", "Combined"),
            ]),
            ("OGR (Order Growth Rate)", [
                ("OGR Avg", "Product_11"),
                ("OGR Avg", "Product_12"),
                ("OGR Avg", "Combined"),
            ]),
            ("UR (Unfinished Ratio Change)", [
                ("UR Avg", "Product_11"),
                ("UR Avg", "Product_12"),
                ("UR Avg", "Combined"),
            ]),
            ("ICR (Inventory–Commitment Ratio)", [
                ("ICR Avg", "Product_11"),
                ("ICR Avg", "Product_12"),
                ("ICR Avg", "Combined"),
            ]),
        ]

        lines = []
        lines.append(dedent(r"""
        % Auto-generated from metrics_summary.csv
        % \usepackage{booktabs}
        \begin{table*}[t]
        \centering
        \caption{Averages of OGR/UR/ICR and Danger Indicators for B1--B3}
        \label{tab:metrics}
        \begin{tabular}{llccc}
            \toprule
            \textbf{Metric} & \textbf{Scope} & \textbf{B1} & \textbf{B2} & \textbf{B3} \\
            \midrule
        """).strip("\n"))

        for sec_title, items in sections:
            lines.append(rf"\multicolumn{{5}}{{l}}{{\textit{{{sec_title}}}}} \\")
            lines.append(r"\addlinespace[2pt]")
            for m, sc in items:
                b1, b2, b3 = row(m, sc)
                m_tex = m.replace("_", r"\_")  # 转义下划线
                sc_tex = sc.replace("_", r"\_")
                lines.append(rf"{m_tex} & {sc_tex} & {b1} & {b2} & {b3} \\")
            lines.append(r"\addlinespace[4pt]")

        lines.append(dedent(r"""
            \bottomrule
        \end{tabular}

        \vspace{4pt}
        \footnotesize
        \textbf{Notes.} Values are step-wise averages; “Combined” aggregates Product\_11 and Product\_12 using valid-step counts as weights.
        \end{table*}
        """).strip("\n"))

        with open("metrics_paper_table.tex", "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print("Saved LaTeX: metrics_paper_table.tex")

        # ---- 2) 生成 PNG（黑白论文风）----
        # 将 MultiIndex 展平为二维表便于绘制
        plot_df = []
        for sec_title, items in sections:
            for m, sc in items:
                b1, b2, b3 = df.loc[(m, sc)]
                plot_df.append([m, sc, b1, b2, b3])
        plot_df = pd.DataFrame(plot_df, columns=["Metric","Scope","B1","B2","B3"])

        # 字符串化并格式化数值
        disp = plot_df.copy()
        for col in ["B1","B2","B3"]:
            disp[col] = disp[col].map(lambda x: "-" if pd.isna(x) else f"{x:.3f}")

        # 使用 matplotlib.table（黑白、细线、等宽字体）
        fig_h = max(3.5, 0.42 * len(disp) + 1.2)
        fig, ax = plt.subplots(figsize=(9.5, fig_h))
        ax.axis("off")

        # 头部列
        cols = ["Metric","Scope","B1","B2","B3"]
        table = ax.table(
            cellText=disp.values,
            colLabels=cols,
            cellLoc="center",
            loc="center"
        )

        # 样式：黑白、细线、等宽字体
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        for (r,c), cell in table.get_celld().items():
            cell.set_linewidth(0.6)  # 细线
            if r == 0:
                cell.set_text_props(weight="bold")  # 表头加粗
            cell.set_edgecolor("black")
            # 等宽字更像论文中的数字列效果
            cell.get_text().set_fontfamily("monospace")

        # 适度列宽
        for i, w in enumerate([0.30, 0.22, 0.16, 0.16, 0.16]):
            table._cells[(0,i)].set_width(w)
            for r in range(1, len(disp) + 1):
                table._cells[(r,i)].set_width(w)

        # 标题
        ax.set_title("Averages of OGR / UR / ICR and Danger Indicators (B1–B3)", fontsize=12, pad=12)

        plt.tight_layout()
        plt.savefig("metrics_paper_table.png", dpi=300, bbox_inches="tight")
        plt.close(fig)

        print("Saved PNG: metrics_paper_table.png")

    async def _plot_(self):
        step_length = 190
        fund_data = await self.get_metrics_data(self.run_uuid, 'company_fund_%')
        company_fund_dict = {
            company: df.set_index("step")["value"]
            for company, df in fund_data.groupby("key")
        }
        # print(company_fund_dict["company_fund_A1"].loc[50])
        
        company_info = {
            "company_id": [1, 2, 3, 4, 5, 6, 7, 8,9,10, 11, 12,13,14,15,16],
            "company_name": ["A1", "A2", "A3", "B1", "B2", "B3","C1", "C2", "C3","C4","C5", "D1", "D2","D3","D4","D5"]
        }
        id_to_name = dict(zip(company_info["company_id"], company_info["company_name"]))
        
        # print("id_to_name",id_to_name.get(1, "Unknown"))
        transactions = await self.querier.get_transaction_summary(self.experiment_id)
        if not transactions:
            print(f"No transaction data found for experiment {self.experiment_id}")
            return None

        df_transaction = pd.DataFrame(transactions)
        # count, value, price = self.query_transaction_value(df_transaction, company="4", step=4, product="product_6",role="purchaser_id")
        # print(f"交易数量={count}, 成交总价={value}, 平均单价={price}")

        # result = self.query_produce_unfinished("./firmagentsql/metrics.csv", "B1", "11",step=11)
        # print("result",result)

        company_list = [
            {
                "id":"4",
                "name":"B1",
                "product_name":"product_11",
                "cv_sell":0,
                "cv_count":0,
                "turn_prods":0,
                "sell_list":[],
                "count_list":[],
            },
            {
                "id":"4",
                "name":"B1",
                "product_name":"product_12",
                "cv_sell":0,
                "cv_count":0,
                "turn_prods":0,
                "sell_list":[],
                "count_list":[],
            },{
                "id":"5",
                "name":"B2",
                "product_name":"product_11",
                "cv_sell":0,
                "cv_count":0,
                "turn_prods":0,
                "sell_list":[],
                "count_list":[],
            },{
                "id":"5",
                "name":"B2",
                "product_name":"product_12",
                "cv_sell":0,
                "cv_count":0,
                "turn_prods":0,
                "sell_list":[],
                "count_list":[],
            },{
                "id":"6",
                "name":"B3",
                "product_name":"product_11",
                "cv_sell":0,
                "cv_count":0,
                "turn_prods":0,
                "sell_list":[],
                "count_list":[],
            },{
                "id":"6",
                "name":"B3",
                "product_name":"product_12",
                "cv_sell":0,
                "cv_count":0,
                "turn_prods":0,
                "sell_list":[],
                "count_list":[],
            },
            {
                "id":"7",
                "name":"C1",
                "product_name":"product_17",
                "cv_sell":0,
                "cv_count":0,
                "turn_prods":0,
                "sell_list":[],
                "count_list":[],
            },{
                "id":"8",
                "name":"C2",
                "product_name":"product_18",
                "cv_sell":0,
                "cv_count":0,
                "turn_prods":0,
                "sell_list":[],
                "count_list":[],
            },{
                "id":"9",
                "name":"C3",
                "product_name":"product_19",
                "cv_sell":0,
                "cv_count":0,
                "turn_prods":0,
                "sell_list":[],
                "count_list":[],
            },{
                "id":"10",
                "name":"C4",
                "product_name":"product_20",
                "cv_sell":0,
                "cv_count":0,
                "turn_prods":0,
                "sell_list":[],
                "count_list":[],
            },{
                "id":"11",
                "name":"C5",
                "product_name":"product_21",
                "cv_sell":0,
                "cv_count":0,
                "turn_prods":0,
                "sell_list":[],
                "count_list":[],
            }
        ]


        for company in company_list:
            inventory_data = await self.get_metrics_data(self.run_uuid, f'product_inventory_{company["name"]}_{company["product_name"]}')
            all_stock = 0
            all_count = 0
            df = pd.read_csv("./firmagentsql/transactions_deepseek.csv")
            step_list = df.loc[df["key"] == f"supply_amount_{company['name']}_{company["product_name"]}", "step"].tolist()
            print(step_list)
            for i in step_list:
                stock = inventory_data.loc[inventory_data["step"] == i, "value"].squeeze()
                count, value, avg_price = self.query_transaction_value(df_transaction, company=company["id"], step=i, product=company["product_name"],role="supplier_id") 
                all_stock += stock
                all_count += count
            a_stock = all_stock / step_length
            # # 成品周转率 库存转化为销售的频率。较高的周转率意味着企业能够更快速地销售库存，从而减少资金占用。
            turn_prods = all_count / (a_stock * all_stock)
            company["turn_prods"] = turn_prods

        # 资金占用率 ：每单位库存和产品占用资金的比例，资本效率越高，说明企业对资金的使用更有效，能够更快地实现库存周转
        company_list2 = [
            # {
            #     "id":"4",
            #     "name":"B1",
            #     "fund_efficiency":0
            # },{
            #     "id":"5",
            #     "name":"B2",
            #     "fund_efficiency":0
            # },{
            #     "id":"6",
            #     "name":"B3",
            #     "fund_efficiency":0
            # },
            {
                "id":"7",
                "name":"C1",
                "fund_efficiency":0
            },{
                "id":"8",
                "name":"C2",
                "fund_efficiency":0
            },{
                "id":"9",
                "name":"C3",
                "fund_efficiency":0
            },{
                "id":"10",
                "name":"C4",
                "fund_efficiency":0
            },{
                "id":"11",
                "name":"C5",
                "fund_efficiency":0
            }
        ]
        # for company in company_list2:
        #     all_fund = 0
        #     all_product = 0
        #     all_material = 0
        #     product_data = await self.get_metrics_data(self.run_uuid, f'total_product_inventory_{company["name"]}')
        #     material_data = await self.get_metrics_data(self.run_uuid, f'total_material_inventory_{company["name"]}')
        #     for i in range(step_length+1):
        #         fund = company_fund_dict[f"company_fund_{company["name"]}"].loc[i]
        #         all_fund += fund
        #         stock = product_data.loc[product_data["step"] == i, "value"].squeeze()
        #         all_product += stock
        #         material = material_data.loc[material_data["step"] == i, "value"].squeeze()
        #         all_material += material
        #     avg_fund = all_fund / step_length
        #     avg_product = all_product / step_length
        #     avg_material = all_material / step_length
        #     fund_efficiency = avg_fund / (avg_product + avg_material)
        #     company["fund_efficiency"] = fund_efficiency
        
        # # # 转换成 DataFrame
        # df = pd.DataFrame(company_list)
        # df["label"] = df["name"] + " - " + df["product_name"]

        # # --- 图1: 价格变异系数 (折线图) ---
        # plt.figure(figsize=(10, 6))
        # plt.plot(df["label"], df["cv_sell"], marker="o", color="blue")
        # plt.xticks(rotation=45, ha="right")
        # plt.ylabel("Price Coefficient of Variation")
        # plt.title("Transaction price fluctuation")
        # plt.tight_layout()
        # plt.savefig("cv_sell_line.png", dpi=300)
        # plt.close()

        # # --- 图2: 交易量变异系数 (折线图) ---
        # plt.figure(figsize=(8, 6))
        # plt.plot(df["label"], df["cv_count"], marker="o", color="blue")
        # plt.xticks(rotation=45, ha="right")
        # plt.ylabel("Count Coefficient of Variation")
        # plt.title("Transaction volume fluctuation")
        # plt.tight_layout()
        # plt.savefig("cv_count_box.png", dpi=300)
        # plt.close()

        # # --- 图3: 成品转换率 (热力图) ---
        pivot_df = df.pivot(index="name", columns="product_name", values="turn_prods")

        plt.figure(figsize=(8, 6))
        sns.heatmap(pivot_df, annot=True, fmt=".2e", cmap="YlOrRd", cbar_kws={'label': 'turn_prods'})
        plt.title("Finished Product Conversion Rate Heatmap")
        plt.tight_layout()
        plt.savefig("turn_prods_heatmap1.png", dpi=300)
        plt.close()

        # 转 DataFrame
        # df = pd.DataFrame(company_list2)

        # # 维度 & 数据
        # labels = df["name"].tolist()
        # values = df["fund_efficiency"].tolist()

        # # 角度划分
        # angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()

        # # 闭合
        # values += values[:1]
        # angles += angles[:1]

        # # 绘制雷达图
        plt.figure(figsize=(8, 8))
        ax = plt.subplot(111, polar=True)

        ax.plot(angles, values, 'o-', linewidth=2, label="fund_efficiency")
        ax.fill(angles, values, alpha=0.25)

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels)

        plt.title("Capital Occupancy Radar Chart", y=1.1)
        plt.legend(loc="upper right", bbox_to_anchor=(1.1, 1.1))
        plt.tight_layout()
        plt.savefig("C类_fund_efficiency_radar.png", dpi=300)
        plt.show()

    async def _plot_radio(self):
        step_length = 190
        fund_data = await self.get_metrics_data(self.run_uuid, 'company_fund_%')
        company_fund_dict = {
            company: df.set_index("step")["value"]
            for company, df in fund_data.groupby("key")
        }
        transactions = await self.querier.get_transaction_summary(self.experiment_id)
        if not transactions:
            print(f"No transaction data found for experiment {self.experiment_id}")
            return None

        # 资金占用率 ：每单位库存和产品占用资金的比例，资本效率越高，说明企业对资金的使用更有效，能够更快地实现库存周转
        company_list2 = [
            {
                "id":"4",
                "name":"B1",
                "fund_efficiency":0
            },{
                "id":"5",
                "name":"B2",
                "fund_efficiency":0
            },{
                "id":"6",
                "name":"B3",
                "fund_efficiency":0
            },
            {
                "id":"7",
                "name":"C1",
                "fund_efficiency":0
            },{
                "id":"8",
                "name":"C2",
                "fund_efficiency":0
            },{
                "id":"9",
                "name":"C3",
                "fund_efficiency":0
            },{
                "id":"10",
                "name":"C4",
                "fund_efficiency":0
            },{
                "id":"11",
                "name":"C5",
                "fund_efficiency":0
            }
        ]
        for company in company_list2:
            all_fund = 0
            all_product = 0
            all_material = 0
            product_data = await self.get_metrics_data(self.run_uuid, f'total_product_inventory_{company["name"]}')
            material_data = await self.get_metrics_data(self.run_uuid, f'total_material_inventory_{company["name"]}')
            for i in range(step_length+1):
                fund = company_fund_dict[f"company_fund_{company["name"]}"].loc[i]
                all_fund += fund
                stock = product_data.loc[product_data["step"] == i, "value"].squeeze()
                all_product += stock
                material = material_data.loc[material_data["step"] == i, "value"].squeeze()
                all_material += material
            avg_fund = all_fund / step_length
            avg_product = all_product / step_length
            avg_material = all_material / step_length
            fund_efficiency = avg_fund / (avg_product + avg_material)
            company["fund_efficiency"] = fund_efficiency
        
        # 转 DataFrame
        df = pd.DataFrame(company_list2)

        df_b = df[df["name"].str.startswith("B")]
        df_c = df[df["name"].str.startswith("C")]

        def plot_radar(df, title, filename):
            labels = df["name"].tolist()
            values = df["fund_efficiency"].tolist()

            # 闭合曲线
            values += values[:1]
            angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
            angles += angles[:1]

            # 绘制雷达图
            plt.figure(figsize=(8, 8))
            ax = plt.subplot(111, polar=True)

            ax.plot(angles, values, 'o-', linewidth=2, label="fund_efficiency")
            ax.fill(angles, values, alpha=0.25)

            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(labels)
            ax.set_yticklabels([])  # 可选：隐藏径向坐标标签

            plt.title(title, y=1.1)
            plt.legend(loc="upper right", bbox_to_anchor=(1.1, 1.1))
            plt.tight_layout()
            plt.savefig(filename, dpi=300)
            plt.show()
        plot_radar(df, "Capital Occupancy Radar Chart - B-C", "fund_efficiency_radar_B&C.png")
        plot_radar(df_b, "Capital Occupancy Radar Chart - B", "fund_efficiency_radar_B.png")
        plot_radar(df_c, "Capital Occupancy Radar Chart - C", "fund_efficiency_radar_C.png")

    def _plot_exp_data(self):

        import pandas as pd
        import numpy as np
        import matplotlib.pyplot as plt
        import re
        from textwrap import dedent

        # -------------------------
        # 参数
        # -------------------------
        CSV_PATH = "./firmagentsql/metrics_gpt.csv"  # 改为你的实际文件名
        COMPANIES = ["B1", "B2", "B3"]
        PRODUCTS = ["11", "12"]
        eps = 1e-9

        # Danger 权重（保持原来）
        w_OGR, w_UR, w_ICR = 0.3, 0.5, 0.2

        # 绝对风险权重
        w_backlog, w_supply, w_IAR, w_LCB, w_FGR = 0.25, 0.20, 0.20, 0.20, 0.10
        alpha = 0.7  # R_final = alpha*R_abs + (1-alpha)*R_rel

        # 高风险分位阈值（最终风险）
        high_q = 0.80
        very_high_q = 0.90

        # -------------------------
        # 读取 CSV（结构：run_id,key,value,step,timestamp）
        # -------------------------
        try:
            df_raw = pd.read_csv(CSV_PATH)
        except Exception as e:
            raise RuntimeError(f"CSV 读取失败: {CSV_PATH}, {e}")

        # 标准列
        for col in ["key", "value", "step"]:
            if col not in df_raw.columns:
                raise RuntimeError(f"CSV 缺少必需列: {col}")

        df = df_raw[["key", "value", "step"]].copy()
        # 转类型
        df["step"] = df["step"].astype(int)
        # value 转浮点；无效则 NaN
        def to_float(x):
            try:
                return float(x)
            except:
                return np.nan
        df["value"] = df["value"].map(to_float)

        # 最大步数（用于主循环）
        STEPS = int(df["step"].max()) + 1 if len(df) > 0 else 0

        # -------------------------
        # 解析 key 并建立索引映射
        # -------------------------
        # 映射：
        # supply_map[(company, product, step)] = value
        # unfin_map[(company, product, step)]  = value
        # state_map[(company, step)] = {'fund': ..., 'inv11': ..., 'inv12': ...}
        supply_map = {}
        unfin_map  = {}
        state_map  = {}  # company+step 的公司级状态（资金/两产品库存）

        def set_state(c, s, k, v):
            key = (c, s)
            if key not in state_map:
                state_map[key] = {'fund': np.nan, 'inv11': np.nan, 'inv12': np.nan}
            state_map[key][k] = v

        # 正则
        pat_fund      = re.compile(r"^company_fund_(B\d+)$")
        pat_inventory = re.compile(r"^product_inventory_(B\d+)_product_(\d+)$")
        pat_supply    = re.compile(r"^supply_amount_(B\d+)_product_(\d+)$")
        pat_unfin     = re.compile(r"^(B\d+)_Unfinished_product_(\d+)$")

        for _, r in df.iterrows():
            k = str(r["key"])
            v = r["value"]
            s = int(r["step"])

            m = pat_fund.match(k)
            if m:
                c = m.group(1)
                set_state(c, s, "fund", v)
                continue

            m = pat_inventory.match(k)
            if m:
                c = m.group(1)
                p = m.group(2)
                if p == "11":
                    set_state(c, s, "inv11", v)
                elif p == "12":
                    set_state(c, s, "inv12", v)
                continue

            m = pat_supply.match(k)
            if m:
                c = m.group(1)
                p = m.group(2)
                supply_map[(c, p, s)] = v
                continue

            m = pat_unfin.match(k)
            if m:
                c = m.group(1)
                p = m.group(2)
                unfin_map[(c, p, s)] = v
                continue

        # 安全取值
        def get_supply(c, p, s):
            return supply_map.get((c, p, s), np.nan)
        def get_unfin(c, p, s):
            return unfin_map.get((c, p, s), np.nan)
        def get_state(c, s):
            st = state_map.get((c, s), None)
            if st is None:
                return {'fund': np.nan, 'inv11': np.nan, 'inv12': np.nan}
            return st

        # -------------------------
        # 工具函数
        # -------------------------
        def log_growth(curr, prev):
            # 非正值或缺失跳过
            if pd.isna(curr) or pd.isna(prev): return np.nan
            if curr <= 0 or prev <= 0: return np.nan
            return np.log((curr + eps) / (prev + eps))

        def sigmoid(x, k=2.0):
            if pd.isna(x): return np.nan
            return 1.0 / (1.0 + np.exp(-k * x))

        def deficit_ratio(x, tau):
            # 当覆盖度 < tau 时，风险上升；映射到 [0,1]
            if pd.isna(x): return np.nan
            r = (tau - x) / tau
            return float(np.clip(r, 0.0, 1.0))

        def safe_avg(s, c):
            return {k: (s[k] / c[k]) if c[k] > 0 else None for k in s.keys()}

        # -------------------------
        # 累加器
        # -------------------------
        ogr_sum_11 = {c: 0.0 for c in COMPANIES}
        ur_sum_11  = {c: 0.0 for c in COMPANIES}
        icr_sum_11 = {c: 0.0 for c in COMPANIES}
        ogr_cnt_11 = {c: 0   for c in COMPANIES}
        ur_cnt_11  = {c: 0   for c in COMPANIES}
        icr_cnt_11 = {c: 0   for c in COMPANIES}

        ogr_sum_12 = {c: 0.0 for c in COMPANIES}
        ur_sum_12  = {c: 0.0 for c in COMPANIES}
        icr_sum_12 = {c: 0.0 for c in COMPANIES}
        ogr_cnt_12 = {c: 0   for c in COMPANIES}
        ur_cnt_12  = {c: 0   for c in COMPANIES}
        icr_cnt_12 = {c: 0   for c in COMPANIES}

        IAR_sum_11 = {c: 0.0 for c in COMPANIES}
        IAR_cnt_11 = {c: 0   for c in COMPANIES}
        IAR_sum_12 = {c: 0.0 for c in COMPANIES}
        IAR_cnt_12 = {c: 0   for c in COMPANIES}

        LCB_sum    = {c: 0.0 for c in COMPANIES}
        LCB_cnt    = {c: 0   for c in COMPANIES}

        FGR_sum    = {c: 0.0 for c in COMPANIES}
        FGR_cnt    = {c: 0   for c in COMPANIES}

        R_abs_sum  = {c: 0.0 for c in COMPANIES}
        R_abs_cnt  = {c: 0   for c in COMPANIES}
        R_rel_sum  = {c: 0.0 for c in COMPANIES}
        R_rel_cnt  = {c: 0   for c in COMPANIES}
        R_fin_sum  = {c: 0.0 for c in COMPANIES}
        R_fin_cnt  = {c: 0   for c in COMPANIES}

        product_11_list = []
        product_12_list = []
        R_final_series  = {c: [] for c in COMPANIES}

        # -------------------------
        # 主循环
        # -------------------------
        for i in range(STEPS):
            rel_11, rel_12 = {}, {}

            OGR_11 = {c: 0.0 for c in COMPANIES}
            UR_11  = {c: 0.0 for c in COMPANIES}
            ICR_11 = {c: 0.0 for c in COMPANIES}
            OGR_12 = {c: 0.0 for c in COMPANIES}
            UR_12  = {c: 0.0 for c in COMPANIES}
            ICR_12 = {c: 0.0 for c in COMPANIES}

            r_abs_by_company = {c: np.nan for c in COMPANIES}

            if i > 0:
                for c in COMPANIES:
                    # ---- 产品 11
                    s11_prev = get_supply(c, "11", i-1)
                    s11_curr = get_supply(c, "11", i)
                    u11_prev = get_unfin(c,  "11", i-1)
                    u11_curr = get_unfin(c,  "11", i)
                    st_curr  = get_state(c, i)

                    if pd.notna(s11_prev) and s11_prev != 0:
                        OGR_11[c] = (s11_curr - s11_prev) / (s11_prev if s11_prev != 0 else eps)
                        ogr_sum_11[c] += OGR_11[c]; ogr_cnt_11[c] += 1
                        if pd.notna(u11_prev):
                            ICR_11[c] = (s11_curr - u11_prev) / (s11_prev if s11_prev != 0 else eps)
                            icr_sum_11[c] += ICR_11[c]; icr_cnt_11[c] += 1
                    if pd.notna(u11_prev) and u11_prev != 0:
                        UR_11[c] = (u11_curr - u11_prev) / (u11_prev if u11_prev != 0 else eps)
                        ur_sum_11[c] += UR_11[c];  ur_cnt_11[c] += 1

                    # IAR_11（库存对未完成覆盖）
                    inv11 = st_curr['inv11']
                    IAR_11_val = np.nan
                    if pd.notna(inv11) and pd.notna(u11_curr):
                        denom = max(u11_curr, eps)
                        IAR_11_val = inv11 / denom
                        IAR_sum_11[c] += IAR_11_val; IAR_cnt_11[c] += 1

                    # ---- 产品 12
                    s12_prev = get_supply(c, "12", i-1)
                    s12_curr = get_supply(c, "12", i)
                    u12_prev = get_unfin(c,  "12", i-1)
                    u12_curr = get_unfin(c,  "12", i)

                    if pd.notna(s12_prev) and s12_prev != 0:
                        OGR_12[c] = (s12_curr - s12_prev) / (s12_prev if s12_prev != 0 else eps)
                        ogr_sum_12[c] += OGR_12[c]; ogr_cnt_12[c] += 1
                        if pd.notna(u12_prev):
                            ICR_12[c] = (s12_curr - u12_prev) / (s12_prev if s12_prev != 0 else eps)
                            icr_sum_12[c] += ICR_12[c]; icr_cnt_12[c] += 1
                    if pd.notna(u12_prev) and u12_prev != 0:
                        UR_12[c] = (u12_curr - u12_prev) / (u12_prev if u12_prev != 0 else eps)
                        ur_sum_12[c] += UR_12[c];  ur_cnt_12[c] += 1

                    # ---- 绝对风险（公司层合成）
                    UR_log_11 = log_growth(u11_curr, u11_prev)
                    UR_log_12 = log_growth(u12_curr, u12_prev)
                    r_backlog = np.nanmean([sigmoid(UR_log_11), sigmoid(UR_log_12)])

                    OGR_log_11 = log_growth(s11_curr, s11_prev)
                    OGR_log_12 = log_growth(s12_curr, s12_prev)
                    r_supply  = np.nanmean([sigmoid(-OGR_log_11), sigmoid(-OGR_log_12)])

                    r_IAR_11  = deficit_ratio(IAR_11_val, tau=1.0) if pd.notna(IAR_11_val) else np.nan
                    # IAR_12 使用 product_12 的库存与未完成
                    inv12 = st_curr['inv12']
                    IAR_12_val = np.nan
                    if pd.notna(inv12) and pd.notna(u12_curr):
                        denom = max(u12_curr, eps)
                        IAR_12_val = inv12 / denom
                        IAR_sum_12[c] += IAR_12_val; IAR_cnt_12[c] += 1
                    r_IAR_12  = deficit_ratio(IAR_12_val, tau=1.0) if pd.notna(IAR_12_val) else np.nan
                    r_IAR     = np.nanmean([r_IAR_11, r_IAR_12])

                    # LCB：资金对未完成总量覆盖（至少有一个未完成值才计算）
                    total_unfin_vals = [x for x in [u11_curr, u12_curr] if pd.notna(x)]
                    LCB = np.nan
                    if pd.notna(st_curr['fund']) and len(total_unfin_vals) > 0:
                        denom = max(sum(total_unfin_vals), eps)
                        LCB = st_curr['fund'] / denom
                        LCB_sum[c] += LCB; LCB_cnt[c] += 1
                    r_LCB = deficit_ratio(LCB, tau=1.5) if pd.notna(LCB) else np.nan

                    # FGR：资金对数动量
                    st_prev = get_state(c, i-1)
                    FGR = log_growth(st_curr['fund'], st_prev['fund'])
                    r_FGR = sigmoid(-FGR) if pd.notna(FGR) else np.nan
                    if pd.notna(FGR):
                        FGR_sum[c] += FGR; FGR_cnt[c] += 1

                    parts = [w_backlog * r_backlog, w_supply * r_supply, w_IAR * r_IAR, w_LCB * r_LCB, w_FGR * r_FGR]
                    R_abs = np.nanmean(parts)
                    r_abs_by_company[c] = R_abs
                    if pd.notna(R_abs):
                        R_abs_sum[c] += R_abs; R_abs_cnt[c] += 1

                # ---- 产品 11：相对危险（min-max归一化）
                for metric_name, metric_dict in [("OGR", OGR_11), ("UR", UR_11), ("ICR", ICR_11)]:
                    vals = [metric_dict[c] for c in COMPANIES]
                    finite_vals = [v for v in vals if np.isfinite(v)]
                    vmax = max(finite_vals) if finite_vals else 0.0
                    vmin = min(finite_vals) if finite_vals else 0.0
                    for c in COMPANIES:
                        v = metric_dict[c]
                        if not np.isfinite(v) or vmax == vmin:
                            norm = 0.0
                        else:
                            norm = (v - vmin) / (vmax - vmin)
                        rel_11[c] = rel_11.get(c, 0.0) + (w_OGR if metric_name == "OGR" else w_UR if metric_name == "UR" else w_ICR) * norm

                # ---- 产品 12：相对危险
                for metric_name, metric_dict in [("OGR", OGR_12), ("UR", UR_12), ("ICR", ICR_12)]:
                    vals = [metric_dict[c] for c in COMPANIES]
                    finite_vals = [v for v in vals if np.isfinite(v)]
                    vmax = max(finite_vals) if finite_vals else 0.0
                    vmin = min(finite_vals) if finite_vals else 0.0
                    for c in COMPANIES:
                        v = metric_dict[c]
                        if not np.isfinite(v) or vmax == vmin:
                            norm = 0.0
                        else:
                            norm = (v - vmin) / (vmax - vmin)
                        rel_12[c] = rel_12.get(c, 0.0) + (w_OGR if metric_name == "OGR" else w_UR if metric_name == "UR" else w_ICR) * norm

                product_11_list.append({c: rel_11.get(c, 0.0) for c in COMPANIES})
                product_12_list.append({c: rel_12.get(c, 0.0) for c in COMPANIES})

                # 合成最终风险
                for c in COMPANIES:
                    R_rel = 0.5 * (rel_11.get(c, 0.0) + rel_12.get(c, 0.0))
                    R_final = alpha * r_abs_by_company[c] + (1 - alpha) * R_rel if pd.notna(r_abs_by_company[c]) else R_rel
                    R_final_series[c].append(R_final)

                    R_rel_sum[c] += R_rel; R_rel_cnt[c] += 1
                    if pd.notna(R_final):
                        R_fin_sum[c] += R_final; R_fin_cnt[c] += 1

        # -------------------------
        # 原有危险系数统计（两产品相对危险）
        # -------------------------
        danger_list = []
        b_avg  = {c: 0.0 for c in COMPANIES}
        b_high = {c: 0.0 for c in COMPANIES}
        denom_steps = max(1, STEPS - 1)

        for d11, d12 in zip(product_11_list, product_12_list):
            row = {c: 0.5 * (d11[c] + d12[c]) for c in COMPANIES}
            danger_list.append(row)
            for c in COMPANIES:
                b_avg[c] += row[c]
                if row[c] > 0.67:
                    b_high[c] += 1

        for c in COMPANIES:
            b_avg[c]  /= denom_steps
            b_high[c] /= denom_steps

        print("Danger avg:", b_avg["B1"], b_avg["B2"], b_avg["B3"])
        print("Danger high ratio:", b_high["B1"], b_high["B2"], b_high["B3"])

        # -------------------------
        # OGR/UR/ICR 产品内均值与合并
        # -------------------------
        ogr_avg_11 = safe_avg(ogr_sum_11, ogr_cnt_11)
        ur_avg_11  = safe_avg(ur_sum_11,  ur_cnt_11)
        icr_avg_11 = safe_avg(icr_sum_11, icr_cnt_11)

        ogr_avg_12 = safe_avg(ogr_sum_12, ogr_cnt_12)
        ur_avg_12  = safe_avg(ur_sum_12,  ur_cnt_12)
        icr_avg_12 = safe_avg(icr_sum_12, icr_cnt_12)

        ogr_sum_all = {k: ogr_sum_11[k] + ogr_sum_12[k] for k in COMPANIES}
        ur_sum_all  = {k: ur_sum_11[k]  + ur_sum_12[k]  for k in COMPANIES}
        icr_sum_all = {k: icr_sum_11[k] + icr_sum_12[k] for k in COMPANIES}
        ogr_cnt_all = {k: ogr_cnt_11[k] + ogr_cnt_12[k] for k in COMPANIES}
        ur_cnt_all  = {k: ur_cnt_11[k]  + ur_cnt_12[k]  for k in COMPANIES}
        icr_cnt_all = {k: icr_cnt_11[k] + icr_cnt_12[k] for k in COMPANIES}

        ogr_avg_all = safe_avg(ogr_sum_all, ogr_cnt_all)
        ur_avg_all  = safe_avg(ur_sum_all,  ur_cnt_all)
        icr_avg_all = safe_avg(icr_sum_all, icr_cnt_all)

        print("Product_11 OGR avg:", ogr_avg_11)
        print("Product_11 UR  avg:", ur_avg_11)
        print("Product_11 ICR avg:", icr_avg_11)
        print("Product_12 OGR avg:", ogr_avg_12)
        print("Product_12 UR  avg:", ur_avg_12)
        print("Product_12 ICR avg:", icr_avg_12)
        print("Combined OGR avg (P11+P12):", ogr_avg_all)
        print("Combined UR  avg (P11+P12):", ur_avg_all)
        print("Combined ICR avg (P11+P12):", icr_avg_all)

        # -------------------------
        # 新增指标均值与高风险比例
        # -------------------------
        IAR_avg_11 = safe_avg(IAR_sum_11, IAR_cnt_11)
        IAR_avg_12 = safe_avg(IAR_sum_12, IAR_cnt_12)
        LCB_avg    = safe_avg(LCB_sum,    LCB_cnt)
        FGR_avg    = safe_avg(FGR_sum,    FGR_cnt)
        R_abs_avg  = safe_avg(R_abs_sum,  R_abs_cnt)
        R_rel_avg  = safe_avg(R_rel_sum,  R_rel_cnt)
        R_fin_avg  = safe_avg(R_fin_sum,  R_fin_cnt)

        R_high_ratio  = {c: None for c in COMPANIES}
        R_vhigh_ratio = {c: None for c in COMPANIES}
        for c in COMPANIES:
            series = np.array([x for x in R_final_series[c] if pd.notna(x)])
            if len(series) > 0:
                thr_h  = float(np.quantile(series, high_q))
                thr_vh = float(np.quantile(series, very_high_q))
                R_high_ratio[c]  = float(np.mean(series > thr_h))
                R_vhigh_ratio[c] = float(np.mean(series > thr_vh))

        # -------------------------
        # 汇总到 DataFrame 并导出
        # -------------------------
        def to_series(d, name):
            return pd.Series({k: (np.nan if d[k] is None else d[k]) for k in COMPANIES}, name=name)

        rows = []
        rows.append(to_series({"B1": b_avg["B1"], "B2": b_avg["B2"], "B3": b_avg["B3"]}, ("Danger Avg", "Combined")))
        rows.append(to_series({"B1": b_high["B1"], "B2": b_high["B2"], "B3": b_high["B3"]}, ("Danger High Ratio(>0.67)", "Combined")))

        rows.append(to_series(R_rel_avg, ("R_rel Avg", "Combined")))
        rows.append(to_series(R_abs_avg, ("R_abs Avg", "Combined")))
        rows.append(to_series(R_fin_avg, ("R_final Avg", "Combined")))
        rows.append(to_series(R_high_ratio, ("R_final High Ratio(80p)", "Combined")))
        rows.append(to_series(R_vhigh_ratio, ("R_final Very High Ratio(90p)", "Combined")))

        rows.append(to_series(IAR_avg_11, ("IAR Avg", "Product_11")))
        rows.append(to_series(IAR_avg_12, ("IAR Avg", "Product_12")))
        rows.append(to_series(LCB_avg,    ("LCB Avg", "Combined")))
        rows.append(to_series(FGR_avg,    ("FGR Avg (log growth)", "Combined")))

        rows.append(to_series(ogr_avg_11, ("OGR Avg", "Product_11")))
        rows.append(to_series(ur_avg_11,  ("UR Avg",  "Product_11")))
        rows.append(to_series(icr_avg_11, ("ICR Avg", "Product_11")))
        rows.append(to_series(ogr_avg_12, ("OGR Avg", "Product_12")))
        rows.append(to_series(ur_avg_12,  ("UR Avg",  "Product_12")))
        rows.append(to_series(icr_avg_12, ("ICR Avg", "Product_12")))
        rows.append(to_series(ogr_avg_all, ("OGR Avg", "Combined")))
        rows.append(to_series(ur_avg_all,  ("UR Avg",  "Combined")))
        rows.append(to_series(icr_avg_all, ("ICR Avg", "Combined")))

        df_sum = pd.DataFrame(rows)
        df_sum.index = pd.MultiIndex.from_tuples(df_sum.index, names=["Metric", "Scope"])
        df_sum = df_sum[COMPANIES]

        df_sum.to_csv("metrics_summary.csv", float_format="%.6f")
        print("Saved: metrics_summary.csv")

        # 渲染彩色 PNG
        fig_h = max(3.5, 0.45 * len(df_sum) + 1)
        fig, ax = plt.subplots(figsize=(10, fig_h))
        ax.axis("off")

        df_to_show = df_sum.copy()
        df_to_show.insert(0, "Scope", [idx[1] for idx in df_to_show.index])
        df_to_show.insert(0, "Metric", [idx[0] for idx in df_to_show.index])

        df_fmt = df_to_show.copy()
        for col in COMPANIES:
            df_fmt[col] = df_fmt[col].map(lambda x: "-" if pd.isna(x) else f"{x:.4f}")

        table = ax.table(
            cellText=df_fmt.values,
            colLabels=df_fmt.columns,
            cellLoc="center",
            loc="center"
        )
        table.auto_set_font_size(False)
        table.set_fontsize(10)

        col_widths = [0.22, 0.18, 0.20, 0.20, 0.20]
        for i, w in enumerate(col_widths):
            table.auto_set_column_width(col=i)
            table._cells[(0,i)].set_width(w)
            for r in range(1, len(df_fmt) + 1):
                table._cells[(r,i)].set_width(w)

        for r in range(1, len(df_fmt) + 1):
            for c in range(len(df_fmt.columns)):
                table._cells[(r, c)].set_facecolor("#F5F7FA" if r % 2 == 0 else "#FFFFFF")
        for c in range(len(df_fmt.columns)):
            cell = table._cells[(0, c)]
            cell.set_facecolor("#E9EEF5")
            cell.set_text_props(weight="bold")

        ax.set_title("Summary of Risk Metrics (Danger/R_rel/R_abs/R_final) and OGR/UR/ICR (B1–B3)", fontsize=12, pad=12)
        plt.tight_layout()
        plt.savefig("metrics_summary.png", dpi=300, bbox_inches="tight")
        plt.close(fig)
        print("Saved: metrics_summary.png")

        # 生成 LaTeX 与黑白 PNG
        df_ltx = pd.read_csv("metrics_summary.csv", index_col=[0,1]).astype(float)
        def fmt3(x): return "-" if pd.isna(x) else f"{x:.3f}"
        def row(metric, scope):
            s = df_ltx.loc[(metric, scope)]
            return fmt3(s["B1"]), fmt3(s["B2"]), fmt3(s["B3"])

        sections = [
            ("Danger (Relative per-step)", [
                ("Danger Avg", "Combined"),
                ("Danger High Ratio(>0.67)", "Combined"),
            ]),
            ("Relative Risk (R_rel)", [
                ("R_rel Avg", "Combined"),
            ]),
            ("Absolute Risk (R_abs) and Final Risk", [
                ("R_abs Avg", "Combined"),
                ("R_final Avg", "Combined"),
                ("R_final High Ratio(80p)", "Combined"),
                ("R_final Very High Ratio(90p)", "Combined"),
            ]),
            ("Inventory Adequacy (IAR)", [
                ("IAR Avg", "Product_11"),
                ("IAR Avg", "Product_12"),
            ]),
            ("Liquidity Coverage (LCB) & Funding Momentum (FGR)", [
                ("LCB Avg", "Combined"),
                ("FGR Avg (log growth)", "Combined"),
            ]),
            ("OGR / UR / ICR (Original)", [
                ("OGR Avg", "Product_11"),
                ("UR Avg",  "Product_11"),
                ("ICR Avg", "Product_11"),
                ("OGR Avg", "Product_12"),
                ("UR Avg",  "Product_12"),
                ("ICR Avg", "Product_12"),
                ("OGR Avg", "Combined"),
                ("UR Avg",  "Combined"),
                ("ICR Avg", "Combined"),
            ]),
        ]

        lines = []
        lines.append(dedent(r"""
        % Auto-generated from metrics_summary.csv
        % \usepackage{booktabs}
        \begin{table*}[t]
        \centering
        \caption{Risk Metrics (Danger/R\_rel/R\_abs/R\_final) and OGR/UR/ICR for B1--B3}
        \label{tab:metrics}
        \begin{tabular}{llccc}
            \toprule
            \textbf{Metric} & \textbf{Scope} & \textbf{B1} & \textbf{B2} & \textbf{B3} \\
            \midrule
        """).strip("\n"))

        for sec_title, items in sections:
            lines.append(rf"\multicolumn{{5}}{{l}}{{\textit{{{sec_title}}}}} \\")
            lines.append(r"\addlinespace[2pt]")
            for m, sc in items:
                b1, b2, b3 = row(m, sc)
                m_tex  = m.replace("_", r"\_")
                sc_tex = sc.replace("_", r"\_")
                lines.append(rf"{m_tex} & {sc_tex} & {b1} & {b2} & {b3} \\")
            lines.append(r"\addlinespace[4pt]")

        lines.append(dedent(r"""
            \bottomrule
        \end{tabular}

        \vspace{4pt}
        \footnotesize
        \textbf{Notes.} R\_final = 0.7 R\_abs + 0.3 R\_rel; High/Very High ratios use per-company 80/90th percentiles over time.
        \end{table*}
        """).strip("\n"))

        with open("metrics_paper_table.tex", "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print("Saved LaTeX: metrics_paper_table.tex")

        plot_df = []
        for sec_title, items in sections:
            for m, sc in items:
                s = df_ltx.loc[(m, sc)]
                plot_df.append([m, sc, s["B1"], s["B2"], s["B3"]])
        plot_df = pd.DataFrame(plot_df, columns=["Metric","Scope","B1","B2","B3"])

        disp = plot_df.copy()
        for col in COMPANIES:
            disp[col] = disp[col].map(lambda x: "-" if pd.isna(x) else f"{x:.3f}")

        fig_h = max(3.5, 0.42 * len(disp) + 1.2)
        fig, ax = plt.subplots(figsize=(9.5, fig_h))
        ax.axis("off")

        cols = ["Metric","Scope","B1","B2","B3"]
        table = ax.table(
            cellText=disp.values,
            colLabels=cols,
            cellLoc="center",
            loc="center"
        )
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        for (r,c), cell in table.get_celld().items():
            cell.set_linewidth(0.6)
            if r == 0:
                cell.set_text_props(weight="bold")
            cell.set_edgecolor("black")
            cell.get_text().set_fontfamily("monospace")

        for i, w in enumerate([0.34, 0.22, 0.15, 0.15, 0.15]):
            table._cells[(0,i)].set_width(w)
            for r in range(1, len(disp) + 1):
                table._cells[(r,i)].set_width(w)

        ax.set_title("Risk Metrics (R_rel/R_abs/R_final) and OGR/UR/ICR (B1–B3)", fontsize=12, pad=12)
        plt.tight_layout()
        plt.savefig("metrics_paper_table.png", dpi=300, bbox_inches="tight")
        plt.close(fig)
        print("Saved PNG: metrics_paper_table.png")

async def main():
    viz = DataVisualization()
    try:
        await viz.connect()
        # await viz._plot_new()
        # viz._plot_data()
        # viz._plot_New_data()
        # await viz._plot_radio()
        viz._plot_exp_data()
    except Exception as e:
        print(f"执行过程中出错: {e}")
    finally:
        await viz.disconnect()
if __name__ == "__main__":
    asyncio.run(main())
