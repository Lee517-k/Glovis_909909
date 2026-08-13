#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版B类企业跨模型聚类分析 - 支持SQL和CSV混合数据源
包含未完成产品指标的综合分析
"""

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import json
from datetime import datetime
import os
import warnings
import re
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, silhouette_samples
import matplotlib.patches as mpatches

warnings.filterwarnings('ignore')


def setup_fonts():
    """设置中文字体"""
    try:
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        print("字体设置成功")
    except Exception as e:
        print(f"字体设置失败: {e}")
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans']


setup_fonts()


class EnhancedHybridBCompanyClusteringAnalysis:
    """增强版B类企业聚类分析，支持SQL和CSV混合数据源"""

    def __init__(self, base_path: str = None):

        if base_path is None:
            base_path = "./firmagentsql/"

        self.base_path = base_path
        self.output_dir = "enhanced_hybrid_clustering_output"

        # 模型配置 - 包含SQL和CSV的不同标识符和路径
        self.model_configs = {
            'deepseek': {
                'name': 'DeepSeek',
                'run_uuid': 'b07b54ee51bd416bba07bfd6b156c93f',  # SQL文件中的标识符
                'run_id': 'b07b54ee51bd416bba07bfd6b156c93f',  # CSV文件中的标识符
                'sql_path': os.path.join(self.base_path,'postgres_metrics_2025-10-09_202907.sql'),
                'csv_path': os.path.join(self.base_path, 'metrics_deepseek.csv')
            },
            'gpt': {
                'name': 'GPT',
                'run_uuid': '9b591b7e0585400b86f1c42792d141ec',  # SQL文件中的标识符
                'run_id': '9b591b7e0585400b86f1c42792d141ec',  # 需要从CSV中查找或确认
                'sql_path': os.path.join(self.base_path,'postgres_metrics_2025-10-09_202907.sql'),
                'csv_path': os.path.join(self.base_path, 'metrics_gpt.csv')
            },
            'qwen': {
                'name': 'Qwen',
                'run_uuid': '6bf78eb01f29432688291ac139bd1096',  # SQL文件中的标识符
                'run_id': '6bf78eb01f29432688291ac139bd1096',  # 需要从CSV中查找或确认
                'sql_path': os.path.join(self.base_path,'postgres_metrics_2025-10-09_202907.sql'),
                'csv_path': os.path.join(self.base_path, 'metrics_qwen.csv')
            }
        }

        # 创建输出目录
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def parse_sql_to_dataframe(self, sql_file_path: str, run_uuid: str) -> pd.DataFrame:
        """从SQL文件解析数据并转换为DataFrame"""
        try:
            if not os.path.exists(sql_file_path):
                print(f"SQL文件不存在: {sql_file_path}")
                return pd.DataFrame()

            print(f"正在解析SQL文件: {sql_file_path}")

            # 读取SQL文件内容
            with open(sql_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 查找COPY语句开始的位置
            copy_start = content.find("COPY public.metrics")
            if copy_start == -1:
                print("未找到COPY语句")
                return pd.DataFrame()

            # 查找数据开始的位置（FROM stdin;之后）
            data_start = content.find("FROM stdin;", copy_start)
            if data_start == -1:
                print("未找到数据开始标记")
                return pd.DataFrame()

            # 查找数据结束的位置（\\.）
            data_end = content.find("\\.", data_start)
            if data_end == -1:
                print("未找到数据结束标记")
                return pd.DataFrame()

            # 提取数据部分
            data_section = content[data_start + len("FROM stdin;"):data_end].strip()

            # 按行分割数据
            lines = [line.strip() for line in data_section.split('\n') if line.strip()]

            # 解析每行数据
            records = []
            for line in lines:
                parts = line.split('\t')
                if len(parts) >= 6:  # key, value, timestamp, run_uuid, step, is_nan
                    key = parts[0]
                    value = float(parts[1]) if parts[1] != '\\N' else 0.0
                    timestamp = int(parts[2]) if parts[2] != '\\N' else 0
                    line_run_uuid = parts[3]
                    step = int(parts[4]) if parts[4] != '\\N' else 0
                    is_nan = parts[5] == 't'

                    # 只保留指定run_uuid的数据
                    if line_run_uuid == run_uuid:
                        records.append({
                            'key': key,
                            'value': value,
                            'timestamp': timestamp,
                            'run_uuid': line_run_uuid,
                            'step': step,
                            'is_nan': is_nan
                        })

            df = pd.DataFrame(records)
            print(f"从SQL文件解析出 {len(df)} 条记录")
            return df

        except Exception as e:
            print(f"解析SQL文件失败 {sql_file_path}: {e}")
            return pd.DataFrame()

    def load_csv_data(self, csv_path: str, run_id: str) -> pd.DataFrame:
        """从CSV文件加载指定run_id的数据"""
        try:
            if not os.path.exists(csv_path):
                print(f"CSV文件不存在: {csv_path}")
                return pd.DataFrame()

            print(f"正在加载CSV文件: {csv_path}")
            df = pd.read_csv(csv_path)

            if run_id:
                df = df[df['run_id'] == run_id]
                print(f"筛选run_id={run_id}后，剩余 {len(df)} 条记录")
            else:
                print(f"未指定run_id，加载所有 {len(df)} 条记录")

            return df

        except Exception as e:
            print(f"加载CSV文件失败: {e}")
            return pd.DataFrame()

    def extract_enhanced_b_company_data(self, model_key: str) -> Optional[Dict]:
        """提取增强版B类企业数据，混合使用SQL和CSV数据源"""
        try:
            config = self.model_configs[model_key]
            print(f"\n正在处理模型: {config['name']}")

            # 从SQL文件加载资金等数据
            sql_df = self.parse_sql_to_dataframe(config['sql_path'], config['run_uuid'])

            # 从CSV文件加载未完成产品数据
            csv_df = self.load_csv_data(config['csv_path'], config['run_id']) if config['run_id'] else pd.DataFrame()

            if sql_df.empty and csv_df.empty:
                print(f"模型 {config['name']} 没有可用数据")
                return None

            # 从SQL数据中分离不同类型的数据
            fund_data = sql_df[
                sql_df['key'].str.contains('company_fund_', na=False)].copy() if not sql_df.empty else pd.DataFrame()
            finished_data = sql_df[sql_df['key'].str.contains('_Finished_product_',
                                                              na=False)].copy() if not sql_df.empty else pd.DataFrame()
            total_inventory_data = sql_df[sql_df['key'].str.contains('total_product_inventory_',
                                                                     na=False)].copy() if not sql_df.empty else pd.DataFrame()

            # 从CSV数据中提取未完成产品数据
            unfinished_data = csv_df[csv_df['key'].str.contains('_Unfinished_product_',
                                                                na=False)].copy() if not csv_df.empty else pd.DataFrame()

            # 检查是否有足够的数据
            if fund_data.empty and unfinished_data.empty:
                print(f"模型 {config['name']} 缺少关键数据（资金或未完成产品）")
                return None

            # 提取企业ID
            all_companies = set()

            if not fund_data.empty:
                fund_data['company_id'] = fund_data['key'].str.extract(r'company_fund_(.+)')
                all_companies.update(fund_data['company_id'].dropna().unique())

            # 处理未完成产品数据
            if not unfinished_data.empty:
                unfinished_data['company_id'] = unfinished_data['key'].str.extract(r'(.+)_Unfinished_product_\d+')[0]
                all_companies.update(unfinished_data['company_id'].dropna().unique())
                # 按企业和步骤聚合未完成产品数据
                unfinished_agg = unfinished_data.groupby(['company_id', 'step'])['value'].sum().reset_index()
            else:
                unfinished_agg = pd.DataFrame()

            # 处理已完成产品数据
            if not finished_data.empty:
                finished_data['company_id'] = finished_data['key'].str.extract(r'(.+)_Finished_product_\d+')[0]
                all_companies.update(finished_data['company_id'].dropna().unique())
                finished_agg = finished_data.groupby(['company_id', 'step'])['value'].sum().reset_index()
            else:
                finished_agg = pd.DataFrame()

            # 处理总库存数据
            if not total_inventory_data.empty:
                total_inventory_data['company_id'] = total_inventory_data['key'].str.extract(
                    r'total_product_inventory_(.+)')
                all_companies.update(total_inventory_data['company_id'].dropna().unique())

            # 筛选B类企业数据
            b_companies = [c for c in all_companies if c and str(c).startswith('B')]

            if len(b_companies) == 0:
                print(f"模型 {config['name']} 没有B类企业数据")
                return None

            print(f"找到 {len(b_companies)} 个B类企业: {list(b_companies)}")

            # 计算特征
            features = {}

            for company in b_companies:
                # 资金数据（来自SQL）
                company_fund = fund_data[fund_data['company_id'] == company][
                    'value'] if not fund_data.empty else pd.Series([0])

                # 未完成产品数据（来自CSV）
                company_unfinished = unfinished_agg[unfinished_agg['company_id'] == company][
                    'value'] if not unfinished_agg.empty else pd.Series([0])

                # 已完成产品数据（来自SQL）
                company_finished = finished_agg[finished_agg['company_id'] == company][
                    'value'] if not finished_agg.empty else pd.Series([0])

                # 总库存数据（来自SQL）
                company_inventory = total_inventory_data[total_inventory_data['company_id'] == company][
                    'value'] if not total_inventory_data.empty else pd.Series([0])

                # 基础资金特征
                fund_mean = company_fund.mean() if len(company_fund) > 0 else 0
                fund_std = company_fund.std() if len(company_fund) > 1 else 0
                fund_cv = fund_std / abs(fund_mean) if fund_mean != 0 else 0
                fund_range = company_fund.max() - company_fund.min() if len(company_fund) > 1 else 0

                # 基础库存特征
                inventory_mean = company_inventory.mean() if len(company_inventory) > 0 else 0
                inventory_std = company_inventory.std() if len(company_inventory) > 1 else 0
                inventory_cv = inventory_std / inventory_mean if inventory_mean != 0 else 0
                inventory_range = company_inventory.max() - company_inventory.min() if len(company_inventory) > 1 else 0

                # 未完成产品特征（关键指标）
                unfinished_mean = company_unfinished.mean() if len(company_unfinished) > 0 else 0
                unfinished_std = company_unfinished.std() if len(company_unfinished) > 1 else 0
                unfinished_cv = unfinished_std / unfinished_mean if unfinished_mean != 0 else 0
                unfinished_range = company_unfinished.max() - company_unfinished.min() if len(
                    company_unfinished) > 1 else 0

                # 已完成产品特征
                finished_mean = company_finished.mean() if len(company_finished) > 0 else 0
                finished_std = company_finished.std() if len(company_finished) > 1 else 0
                finished_cv = finished_std / finished_mean if finished_mean != 0 else 0
                finished_range = company_finished.max() - company_finished.min() if len(company_finished) > 1 else 0

                # 相关性分析
                fund_inventory_corr = 0
                fund_unfinished_corr = 0
                fund_finished_corr = 0
                unfinished_finished_corr = 0

                # 计算资金与未完成产品的相关性（跨数据源）
                if len(company_fund) > 1 and len(company_unfinished) > 1:
                    # 需要确保两个序列长度一致
                    min_len = min(len(company_fund), len(company_unfinished))
                    if min_len > 1:
                        fund_subset = company_fund.iloc[:min_len]
                        unfinished_subset = company_unfinished.iloc[:min_len]
                        fund_unfinished_corr = np.corrcoef(fund_subset, unfinished_subset)[0, 1]
                        if np.isnan(fund_unfinished_corr):
                            fund_unfinished_corr = 0

                # 计算其他相关性
                if len(company_fund) > 1 and len(company_inventory) > 1:
                    min_len = min(len(company_fund), len(company_inventory))
                    if min_len > 1:
                        fund_subset = company_fund.iloc[:min_len]
                        inventory_subset = company_inventory.iloc[:min_len]
                        fund_inventory_corr = np.corrcoef(fund_subset, inventory_subset)[0, 1]
                        if np.isnan(fund_inventory_corr):
                            fund_inventory_corr = 0

                if len(company_fund) > 1 and len(company_finished) > 1:
                    min_len = min(len(company_fund), len(company_finished))
                    if min_len > 1:
                        fund_subset = company_fund.iloc[:min_len]
                        finished_subset = company_finished.iloc[:min_len]
                        fund_finished_corr = np.corrcoef(fund_subset, finished_subset)[0, 1]
                        if np.isnan(fund_finished_corr):
                            fund_finished_corr = 0

                if len(company_unfinished) > 1 and len(company_finished) > 1:
                    min_len = min(len(company_unfinished), len(company_finished))
                    if min_len > 1:
                        unfinished_subset = company_unfinished.iloc[:min_len]
                        finished_subset = company_finished.iloc[:min_len]
                        unfinished_finished_corr = np.corrcoef(unfinished_subset, finished_subset)[0, 1]
                        if np.isnan(unfinished_finished_corr):
                            unfinished_finished_corr = 0

                # 效率指标
                efficiency_ratio = fund_mean / inventory_mean if inventory_mean != 0 else 0
                unfinished_ratio = unfinished_mean / (inventory_mean + 1) if inventory_mean > 0 else unfinished_mean
                production_efficiency = finished_mean / (unfinished_mean + 1) if unfinished_mean > 0 else finished_mean
                order_fulfillment_capacity = 1 / (1 + unfinished_cv) if unfinished_cv > 0 else 1

                features[company] = {
                    # 基础特征
                    'fund_mean': fund_mean,
                    'fund_std': fund_std,
                    'fund_cv': fund_cv,
                    'fund_range': fund_range,
                    'inventory_mean': inventory_mean,
                    'inventory_std': inventory_std,
                    'inventory_cv': inventory_cv,
                    'inventory_range': inventory_range,

                    # 未完成产品特征（关键）
                    'unfinished_mean': unfinished_mean,
                    'unfinished_std': unfinished_std,
                    'unfinished_cv': unfinished_cv,
                    'unfinished_range': unfinished_range,

                    # 已完成产品特征
                    'finished_mean': finished_mean,
                    'finished_std': finished_std,
                    'finished_cv': finished_cv,
                    'finished_range': finished_range,

                    # 相关性特征
                    'fund_inventory_corr': fund_inventory_corr,
                    'fund_unfinished_corr': fund_unfinished_corr,  # 跨数据源相关性
                    'fund_finished_corr': fund_finished_corr,
                    'unfinished_finished_corr': unfinished_finished_corr,

                    # 效率特征
                    'efficiency_ratio': efficiency_ratio,
                    'unfinished_ratio': unfinished_ratio,
                    'production_efficiency': production_efficiency,
                    'order_fulfillment_capacity': order_fulfillment_capacity
                }

            return {
                'model': config['name'],
                'features': features,
                'summary': {
                    'total_companies': len(b_companies),
                    'fund_records': len(fund_data),
                    'unfinished_records': len(unfinished_data),
                    'finished_records': len(finished_data),
                    'inventory_records': len(total_inventory_data),
                    'data_sources': {
                        'sql_file': config['sql_path'],
                        'csv_file': config['csv_path'],
                        'run_uuid': config['run_uuid'],
                        'run_id': config['run_id']
                    }
                }
            }

        except Exception as e:
            print(f"提取模型 {model_key} 数据失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def prepare_enhanced_clustering_data(self, models_data: List[Dict]) -> Tuple[np.ndarray, List[str], List[str]]:
        """准备聚类数据"""
        feature_names = [
            'fund_mean', 'fund_std', 'fund_cv', 'fund_range',
            'inventory_mean', 'inventory_std', 'inventory_cv', 'inventory_range',
            'unfinished_mean', 'unfinished_std', 'unfinished_cv', 'unfinished_range',
            'finished_mean', 'finished_std', 'finished_cv', 'finished_range',
            'fund_inventory_corr', 'fund_unfinished_corr', 'fund_finished_corr', 'unfinished_finished_corr',
            'efficiency_ratio', 'unfinished_ratio', 'production_efficiency', 'order_fulfillment_capacity'
        ]

        all_features = []
        all_labels = []
        all_model_labels = []

        for model_data in models_data:
            model_name = model_data['model']
            for company, features in model_data['features'].items():
                feature_vector = [features.get(name, 0) for name in feature_names]
                all_features.append(feature_vector)
                all_labels.append(f"{model_name}_{company}")
                all_model_labels.append(model_name)

        return np.array(all_features), all_labels, all_model_labels

    def extract_company_data_by_type(self, model_key: str, company_types: List[str] = ['B']) -> Optional[Dict]:
        """提取指定类型企业数据（支持B类、C类或BC合并）"""
        try:
            config = self.model_configs[model_key]
            print(f"\n正在处理模型: {config['name']}, 企业类型: {company_types}")

            # 从SQL文件加载资金等数据
            sql_df = self.parse_sql_to_dataframe(config['sql_path'], config['run_uuid'])

            # 从CSV文件加载未完成产品数据
            csv_df = self.load_csv_data(config['csv_path'], config['run_id']) if config['run_id'] else pd.DataFrame()

            if sql_df.empty and csv_df.empty:
                print(f"模型 {config['name']} 没有可用数据")
                return None

            # 从SQL数据中分离不同类型的数据
            fund_data = sql_df[sql_df['key'].str.contains('company_fund_', na=False)].copy() if not sql_df.empty else pd.DataFrame()
            finished_data = sql_df[sql_df['key'].str.contains('_Finished_product_', na=False)].copy() if not sql_df.empty else pd.DataFrame()
            total_inventory_data = sql_df[sql_df['key'].str.contains('total_product_inventory_', na=False)].copy() if not sql_df.empty else pd.DataFrame()

            # 从CSV数据中提取未完成产品数据
            unfinished_data = csv_df[csv_df['key'].str.contains('_Unfinished_product_', na=False)].copy() if not csv_df.empty else pd.DataFrame()

            # 检查是否有足够的数据
            if fund_data.empty and unfinished_data.empty:
                print(f"模型 {config['name']} 缺少关键数据（资金或未完成产品）")
                return None

            # 提取企业ID
            all_companies = set()

            if not fund_data.empty:
                fund_data['company_id'] = fund_data['key'].str.extract(r'company_fund_(.+)')
                all_companies.update(fund_data['company_id'].dropna().unique())

            # 处理未完成产品数据
            if not unfinished_data.empty:
                unfinished_data['company_id'] = unfinished_data['key'].str.extract(r'(.+)_Unfinished_product_\d+')[0]
                all_companies.update(unfinished_data['company_id'].dropna().unique())
                unfinished_agg = unfinished_data.groupby(['company_id', 'step'])['value'].sum().reset_index()
            else:
                unfinished_agg = pd.DataFrame()

            # 处理已完成产品数据
            if not finished_data.empty:
                finished_data['company_id'] = finished_data['key'].str.extract(r'(.+)_Finished_product_\d+')[0]
                all_companies.update(finished_data['company_id'].dropna().unique())
                finished_agg = finished_data.groupby(['company_id', 'step'])['value'].sum().reset_index()
            else:
                finished_agg = pd.DataFrame()

            # 处理总库存数据
            if not total_inventory_data.empty:
                total_inventory_data['company_id'] = total_inventory_data['key'].str.extract(r'total_product_inventory_(.+)')
                all_companies.update(total_inventory_data['company_id'].dropna().unique())

            # 筛选指定类型企业数据
            target_companies = []
            for company_type in company_types:
                type_companies = [c for c in all_companies if c and str(c).startswith(company_type)]
                target_companies.extend(type_companies)

            if len(target_companies) == 0:
                print(f"模型 {config['name']} 没有 {company_types} 类企业数据")
                return None

            print(f"找到 {len(target_companies)} 个 {company_types} 类企业: {list(target_companies)}")

            # 计算特征（使用与现有方法相同的逻辑）
            features = {}

            for company in target_companies:
                # 资金数据（来自SQL）
                company_fund = fund_data[fund_data['company_id'] == company]['value'] if not fund_data.empty else pd.Series([0])

                # 未完成产品数据（来自CSV）
                company_unfinished = unfinished_agg[unfinished_agg['company_id'] == company]['value'] if not unfinished_agg.empty else pd.Series([0])

                # 已完成产品数据（来自SQL）
                company_finished = finished_agg[finished_agg['company_id'] == company]['value'] if not finished_agg.empty else pd.Series([0])

                # 总库存数据（来自SQL）
                company_inventory = total_inventory_data[total_inventory_data['company_id'] == company]['value'] if not total_inventory_data.empty else pd.Series([0])

                # 基础资金特征
                fund_mean = company_fund.mean() if len(company_fund) > 0 else 0
                fund_std = company_fund.std() if len(company_fund) > 1 else 0
                fund_cv = fund_std / abs(fund_mean) if fund_mean != 0 else 0
                fund_range = company_fund.max() - company_fund.min() if len(company_fund) > 1 else 0

                # 基础库存特征
                inventory_mean = company_inventory.mean() if len(company_inventory) > 0 else 0
                inventory_std = company_inventory.std() if len(company_inventory) > 1 else 0
                inventory_cv = inventory_std / inventory_mean if inventory_mean != 0 else 0
                inventory_range = company_inventory.max() - company_inventory.min() if len(company_inventory) > 1 else 0

                # 基础未完成产品特征
                unfinished_mean = company_unfinished.mean() if len(company_unfinished) > 0 else 0
                unfinished_std = company_unfinished.std() if len(company_unfinished) > 1 else 0
                unfinished_cv = unfinished_std / unfinished_mean if unfinished_mean != 0 else 0
                unfinished_range = company_unfinished.max() - company_unfinished.min() if len(company_unfinished) > 1 else 0

                # 基础已完成产品特征
                finished_mean = company_finished.mean() if len(company_finished) > 0 else 0
                finished_std = company_finished.std() if len(company_finished) > 1 else 0
                finished_cv = finished_std / finished_mean if finished_mean != 0 else 0
                finished_range = company_finished.max() - company_finished.min() if len(company_finished) > 1 else 0

                # 相关性分析
                fund_inventory_corr = 0
                fund_unfinished_corr = 0
                fund_finished_corr = 0
                unfinished_finished_corr = 0

                if len(company_fund) > 1 and len(company_inventory) > 1:
                    try:
                        fund_inventory_corr = np.corrcoef(company_fund, company_inventory)[0, 1]
                        if np.isnan(fund_inventory_corr):
                            fund_inventory_corr = 0
                    except:
                        fund_inventory_corr = 0

                if len(company_fund) > 1 and len(company_unfinished) > 1:
                    try:
                        fund_unfinished_corr = np.corrcoef(company_fund, company_unfinished)[0, 1]
                        if np.isnan(fund_unfinished_corr):
                            fund_unfinished_corr = 0
                    except:
                        fund_unfinished_corr = 0

                if len(company_fund) > 1 and len(company_finished) > 1:
                    try:
                        fund_finished_corr = np.corrcoef(company_fund, company_finished)[0, 1]
                        if np.isnan(fund_finished_corr):
                            fund_finished_corr = 0
                    except:
                        fund_finished_corr = 0

                if len(company_unfinished) > 1 and len(company_finished) > 1:
                    try:
                        unfinished_finished_corr = np.corrcoef(company_unfinished, company_finished)[0, 1]
                        if np.isnan(unfinished_finished_corr):
                            unfinished_finished_corr = 0
                    except:
                        unfinished_finished_corr = 0

                # 效率指标
                efficiency_ratio = fund_mean / inventory_mean if inventory_mean > 0 else 0
                unfinished_ratio = unfinished_mean / (finished_mean + 1) if finished_mean >= 0 else unfinished_mean
                production_efficiency = finished_mean / (unfinished_mean + finished_mean + 1)
                order_fulfillment_capacity = finished_mean / (unfinished_mean + 1) if unfinished_mean > 0 else finished_mean

                features[company] = {
                    'fund_mean': fund_mean,
                    'fund_std': fund_std,
                    'fund_cv': fund_cv,
                    'fund_range': fund_range,
                    'inventory_mean': inventory_mean,
                    'inventory_std': inventory_std,
                    'inventory_cv': inventory_cv,
                    'inventory_range': inventory_range,
                    'unfinished_mean': unfinished_mean,
                    'unfinished_std': unfinished_std,
                    'unfinished_cv': unfinished_cv,
                    'unfinished_range': unfinished_range,
                    'finished_mean': finished_mean,
                    'finished_std': finished_std,
                    'finished_cv': finished_cv,
                    'finished_range': finished_range,
                    'fund_inventory_corr': fund_inventory_corr,
                    'fund_unfinished_corr': fund_unfinished_corr,
                    'fund_finished_corr': fund_finished_corr,
                    'unfinished_finished_corr': unfinished_finished_corr,
                    'efficiency_ratio': efficiency_ratio,
                    'unfinished_ratio': unfinished_ratio,
                    'production_efficiency': production_efficiency,
                    'order_fulfillment_capacity': order_fulfillment_capacity
                }

            return {
                'model': config['name'],
                'model_key': model_key,
                'company_types': company_types,
                'companies': target_companies,
                'features': features,
                'raw_data': {
                    'fund_data': fund_data,
                    'unfinished_data': unfinished_agg,
                    'finished_data': finished_agg,
                    'inventory_data': total_inventory_data
                }
            }

        except Exception as e:
            print(f"提取企业数据时出错: {e}")
            return None

    def prepare_single_model_clustering_data(self, company_data: Dict) -> Tuple[np.ndarray, List[str]]:
        """准备单模型聚类数据"""
        feature_names = [
            'fund_mean', 'fund_std', 'fund_cv', 'fund_range',
            'inventory_mean', 'inventory_std', 'inventory_cv', 'inventory_range',
            'unfinished_mean', 'unfinished_std', 'unfinished_cv', 'unfinished_range',
            'finished_mean', 'finished_std', 'finished_cv', 'finished_range',
            'fund_inventory_corr', 'fund_unfinished_corr', 'fund_finished_corr', 'unfinished_finished_corr',
            'efficiency_ratio', 'unfinished_ratio', 'production_efficiency', 'order_fulfillment_capacity'
        ]

        all_features = []
        all_labels = []

        for company, features in company_data['features'].items():
            feature_vector = [features.get(name, 0) for name in feature_names]
            all_features.append(feature_vector)
            all_labels.append(company)

        return np.array(all_features), all_labels

    def run_bc_combined_analysis(self, model_key: str, n_clusters: int = None) -> Dict[str, Any]:
        """运行BC合并分析（单模型内B类和C类企业一起聚类）"""
        print(f"\n开始 {model_key} 模型 BC合并聚类分析...")
        
        # 提取BC企业数据
        company_data = self.extract_company_data_by_type(model_key, ['B', 'C'])
        if not company_data:
            raise ValueError(f"无法提取 {model_key} 模型的BC企业数据")
        
        # 准备聚类数据
        features, labels = self.prepare_single_model_clustering_data(company_data)
        print(f"准备聚类数据: {features.shape[0]} 个样本, {features.shape[1]} 个特征")
        
        # 执行聚类
        cluster_labels, kmeans, scaler = self.perform_clustering(features, n_clusters)
        
        # 生成可视化和报告
        viz_path = self.visualize_single_model_results(features, cluster_labels, labels, company_data, kmeans, scaler, "BC合并")
        report_path = self.generate_single_model_report(features, cluster_labels, labels, company_data, "BC合并")
        
        return {
            'analysis_type': 'BC合并分析',
            'model_key': model_key,
            'company_data': company_data,
            'features': features,
            'labels': labels,
            'cluster_labels': cluster_labels,
            'kmeans': kmeans,
            'scaler': scaler,
            'visualization_path': viz_path,
            'report_path': report_path
        }

    def run_b_only_analysis(self, model_key: str, n_clusters: int = None) -> Dict[str, Any]:
        """运行B类单独分析（单模型内只对B类企业聚类）"""
        print(f"\n开始 {model_key} 模型 B类单独聚类分析...")
        
        # 提取B类企业数据
        company_data = self.extract_company_data_by_type(model_key, ['B'])
        if not company_data:
            raise ValueError(f"无法提取 {model_key} 模型的B类企业数据")
        
        # 准备聚类数据
        features, labels = self.prepare_single_model_clustering_data(company_data)
        print(f"准备聚类数据: {features.shape[0]} 个样本, {features.shape[1]} 个特征")
        
        # 执行聚类
        cluster_labels, kmeans, scaler = self.perform_clustering(features, n_clusters)
        
        # 生成可视化和报告
        viz_path = self.visualize_single_model_results(features, cluster_labels, labels, company_data, kmeans, scaler, "B类单独")
        report_path = self.generate_single_model_report(features, cluster_labels, labels, company_data, "B类单独")
        
        return {
            'analysis_type': 'B类单独分析',
            'model_key': model_key,
            'company_data': company_data,
            'features': features,
            'labels': labels,
            'cluster_labels': cluster_labels,
            'kmeans': kmeans,
            'scaler': scaler,
            'visualization_path': viz_path,
            'report_path': report_path
        }

    def run_c_only_analysis(self, model_key: str, n_clusters: int = None) -> Dict[str, Any]:
        """运行C类单独分析（单模型内只对C类企业聚类）"""
        print(f"\n开始 {model_key} 模型 C类单独聚类分析...")
        
        # 提取C类企业数据
        company_data = self.extract_company_data_by_type(model_key, ['C'])
        if not company_data:
            raise ValueError(f"无法提取 {model_key} 模型的C类企业数据")
        
        # 准备聚类数据
        features, labels = self.prepare_single_model_clustering_data(company_data)
        print(f"准备聚类数据: {features.shape[0]} 个样本, {features.shape[1]} 个特征")
        
        # 执行聚类
        cluster_labels, kmeans, scaler = self.perform_clustering(features, n_clusters)
        
        # 生成可视化和报告
        viz_path = self.visualize_single_model_results(features, cluster_labels, labels, company_data, kmeans, scaler, "C类单独")
        report_path = self.generate_single_model_report(features, cluster_labels, labels, company_data, "C类单独")
        
        return {
            'analysis_type': 'C类单独分析',
            'model_key': model_key,
            'company_data': company_data,
            'features': features,
            'labels': labels,
            'cluster_labels': cluster_labels,
            'kmeans': kmeans,
            'scaler': scaler,
            'visualization_path': viz_path,
            'report_path': report_path
        }

    def visualize_single_model_results(self, features: np.ndarray, cluster_labels: np.ndarray, 
                                labels: List[str], company_data: Dict, 
                                kmeans: KMeans, scaler: StandardScaler, analysis_type: str) -> str:
        """生成单模型聚类可视化结果（坐标轴放大 + 自动裁剪无点空间版）"""
        model_name = company_data['model']
        company_types_str = '+'.join(company_data['company_types'])
        
        # 文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{model_name}_{analysis_type}_clustering_{timestamp}.png"
        filepath = os.path.join(self.output_dir, filename)

        # 图形
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(f'{model_name}模型 - {analysis_type}聚类分析', fontsize=20, fontweight='bold')

        # PCA降维
        pca = PCA(n_components=2)
        features_pca = pca.fit_transform(scaler.transform(features))

        # 绘制散点图
        ax1 = axes[0, 0]
        scatter = ax1.scatter(
            features_pca[:, 0], features_pca[:, 1],
            c=cluster_labels, cmap='viridis', alpha=0.8,
            s=120, edgecolors='k', linewidths=0.4
        )

        ax1.set_title('PCA-Clustering（放大坐标轴+自动收缩）', fontsize=16, fontweight='bold')
        ax1.set_xlabel(f'PC1 ({pca.explained_variance_ratio_[0]:.2%} variance)', fontsize=13)
        ax1.set_ylabel(f'PC2 ({pca.explained_variance_ratio_[1]:.2%} variance)', fontsize=13)
        ax1.tick_params(axis='both', labelsize=11)

        # === 坐标轴放大，增加密集感 ===
        expand_factor = 2.0  # 越大越密集，可调
        x_min, x_max = features_pca[:, 0].min(), features_pca[:, 0].max()
        y_min, y_max = features_pca[:, 1].min(), features_pca[:, 1].max()
        x_center, y_center = (x_min + x_max) / 2, (y_min + y_max) / 2
        x_half_range = (x_max - x_min) / 2 * expand_factor
        y_half_range = (y_max - y_min) / 2 * expand_factor

        ax1.set_xlim(x_center - x_half_range, x_center + x_half_range)
        ax1.set_ylim(y_center - y_half_range, y_center + y_half_range)

        # === 自动收缩视野：去掉四周无点空间 ===
        # 获取所有点的边界框，并保留一定比例的边距
        x_pad = (x_max - x_min) * 0.1
        y_pad = (y_max - y_min) * 0.1
        ax1.set_xlim(x_min - x_pad, x_max + x_pad)
        ax1.set_ylim(y_min - y_pad, y_max + y_pad)

        # 添加标签
        for i, label in enumerate(labels):
            ax1.annotate(label, (features_pca[i, 0], features_pca[i, 1]),
                        xytext=(5, 5), textcoords='offset points',
                        fontsize=9, weight='medium')

        plt.colorbar(scatter, ax=ax1)

        # === 自动去除图形外空白 ===
        plt.tight_layout(pad=0.5)
        plt.subplots_adjust(wspace=0.3, hspace=0.3)
        plt.savefig(filepath, dpi=600, bbox_inches='tight', pad_inches=0.05)
        plt.close()

        print(f"可视化结果已保存到: {filepath}")
        return filepath


    def generate_single_model_report(self, features: np.ndarray, cluster_labels: np.ndarray,
                                   labels: List[str], company_data: Dict, analysis_type: str) -> str:
        """生成单模型聚类分析报告"""
        model_name = company_data['model']
        company_types_str = '+'.join(company_data['company_types'])
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{model_name}_{analysis_type}_report_{timestamp}.txt"
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# {model_name}模型 - {analysis_type}聚类分析报告\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            # 数据源信息
            f.write("## 数据源信息\n")
            f.write(f"- 模型: {model_name}\n")
            f.write(f"- 分析类型: {analysis_type}\n")
            f.write(f"- 企业类型: {company_types_str}类企业\n")
            f.write(f"- 企业数量: {len(labels)}\n")
            f.write(f"- 特征维度: {features.shape[1]}\n")
            f.write(f"- 聚类数量: {len(np.unique(cluster_labels))}\n\n")

            # 企业列表
            f.write("## 分析企业列表\n")
            for i, company in enumerate(labels):
                f.write(f"{i+1}. {company}\n")
            f.write("\n")

            # 聚类结果分析
            f.write("## 聚类结果分析\n\n")
            
            unique_labels = np.unique(cluster_labels)
            for cluster_id in unique_labels:
                cluster_mask = cluster_labels == cluster_id
                cluster_companies = [labels[i] for i in range(len(labels)) if cluster_mask[i]]
                
                f.write(f"### 聚类 {cluster_id}\n")
                f.write(f"**企业数量**: {len(cluster_companies)}\n")
                f.write(f"**包含企业**: {', '.join(cluster_companies)}\n\n")
                
                # 计算聚类特征统计
                if len(cluster_companies) > 0:
                    avg_fund = np.mean([company_data['features'][comp]['fund_mean'] for comp in cluster_companies])
                    avg_inventory = np.mean([company_data['features'][comp]['inventory_mean'] for comp in cluster_companies])
                    avg_unfinished = np.mean([company_data['features'][comp]['unfinished_mean'] for comp in cluster_companies])
                    avg_finished = np.mean([company_data['features'][comp]['finished_mean'] for comp in cluster_companies])
                    avg_fund_unfinished_corr = np.mean([company_data['features'][comp]['fund_unfinished_corr'] for comp in cluster_companies])
                    avg_production_efficiency = np.mean([company_data['features'][comp]['production_efficiency'] for comp in cluster_companies])
                    avg_fulfillment_capacity = np.mean([company_data['features'][comp]['order_fulfillment_capacity'] for comp in cluster_companies])
                    
                    f.write("**关键指标**:\n")
                    f.write(f"- 平均资金: {avg_fund:.2f}\n")
                    f.write(f"- 平均库存: {avg_inventory:.2f}\n")
                    f.write(f"- 平均未完成: {avg_unfinished:.2f}\n")
                    f.write(f"- 平均已完成: {avg_finished:.2f}\n")
                    f.write(f"- 资金-未完成相关性: {avg_fund_unfinished_corr:.3f}\n")
                    f.write(f"- 生产效率: {avg_production_efficiency:.3f}\n")
                    f.write(f"- 订单履行能力: {avg_fulfillment_capacity:.3f}\n\n")
                    
                    # 聚类特征描述
                    description = self._describe_enhanced_cluster(
                        avg_fund, avg_inventory, avg_unfinished, avg_finished,
                        avg_fund_unfinished_corr, avg_production_efficiency, avg_fulfillment_capacity
                    )
                    f.write(f"**聚类特征**: {description}\n\n")

        print(f"分析报告已保存到: {filepath}")
        return filepath

    def run_all_single_model_analyses(self, models: List[str] = None, n_clusters: int = None) -> Dict[str, Any]:
        """运行所有单模型聚类分析"""
        if models is None:
            models = ['deepseek', 'gpt', 'qwen']
        
        print("开始单模型聚类分析...")
        all_results = {}
        
        for model in models:
            print(f"\n=== 分析模型: {model.upper()} ===")
            model_results = {}
            
            # BC合并分析
            try:
                result = self.run_bc_combined_analysis(model, n_clusters)
                model_results['BC合并分析'] = result
                print(f"✓ 完成 {model} - BC合并分析")
            except Exception as e:
                print(f"✗ {model} - BC合并分析失败: {e}")
                model_results['BC合并分析'] = None
            
            # B类单独分析
            try:
                result = self.run_b_only_analysis(model, n_clusters)
                model_results['B类单独分析'] = result
                print(f"✓ 完成 {model} - B类单独分析")
            except Exception as e:
                print(f"✗ {model} - B类单独分析失败: {e}")
                model_results['B类单独分析'] = None
            
            # C类单独分析
            try:
                result = self.run_c_only_analysis(model, n_clusters)
                model_results['C类单独分析'] = result
                print(f"✓ 完成 {model} - C类单独分析")
            except Exception as e:
                print(f"✗ {model} - C类单独分析失败: {e}")
                model_results['C类单独分析'] = None
            
            all_results[model] = model_results
        
        # 生成综合报告
        comprehensive_report_path = self.generate_all_analyses_comprehensive_report(all_results)
        
        # 将综合报告路径添加到结果中
        all_results['comprehensive_report_path'] = comprehensive_report_path
        
        return all_results

    def generate_all_analyses_comprehensive_report(self, all_results: Dict[str, Any]) -> str:
        """生成所有分析的综合报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"all_clustering_analyses_report_{timestamp}.txt"
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("# 所有聚类分析综合报告\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            f.write("## 分析概述\n")
            f.write("本报告包含以下聚类分析结果：\n")
            f.write("1. **跨模型分析**：所有模型的B类企业混合聚类（原有分析）\n")
            f.write("2. **单模型分析**：每个模型内部的聚类分析\n")
            f.write("   - BC合并分析：B类和C类企业一起聚类\n")
            f.write("   - B类单独分析：只对B类企业聚类\n")
            f.write("   - C类单独分析：只对C类企业聚类\n\n")

            # 分析结果汇总
            f.write("## 单模型分析结果汇总\n\n")
            
            for model, model_results in all_results.items():
                f.write(f"### {model.upper()} 模型\n")
                
                for analysis_name, result in model_results.items():
                    if result:
                        company_count = len(result['labels'])
                        cluster_count = len(np.unique(result['cluster_labels']))
                        f.write(f"- **{analysis_name}**: {company_count}个企业, {cluster_count}个聚类 ✓\n")
                    else:
                        f.write(f"- **{analysis_name}**: 分析失败 ✗\n")
                
                f.write("\n")

            # 对比分析
            f.write("## 跨模型 vs 单模型分析对比\n\n")
            f.write("### 分析方式对比\n")
            f.write("| 分析类型 | 跨模型分析 | 单模型分析 |\n")
            f.write("|---------|-----------|----------|\n")
            f.write("| **数据范围** | 所有模型企业混合 | 每个模型内部 |\n")
            f.write("| **聚类对象** | DeepSeek+GPT+Qwen企业 | 单个模型的企业 |\n")
            f.write("| **比较方式** | 模型间企业相似性 | 模型内企业分组 |\n")
            f.write("| **分析目标** | 不同模型企业的分布 | 每个模型的内部结构 |\n\n")

        print(f"综合报告已保存到: {filepath}")
        return filepath

    def run_enhanced_analysis(self, models: List[str] = None, n_clusters: int = None) -> Dict[str, Any]:
        """运行增强版聚类分析"""
        if models is None:
            models = ['deepseek', 'gpt', 'qwen']

        print("开始增强版B类企业聚类分析...")

        # 提取各模型数据
        models_data = []
        for model in models:
            data = self.extract_enhanced_b_company_data(model)
            if data:
                models_data.append(data)

        if not models_data:
            raise ValueError("没有成功提取到任何模型数据")

        # 准备聚类数据
        features, labels, model_labels = self.prepare_enhanced_clustering_data(models_data)
        print(f"准备聚类数据: {features.shape[0]} 个样本, {features.shape[1]} 个特征")

        # 执行聚类
        cluster_labels, kmeans, scaler = self.perform_clustering(features, n_clusters)

        # 生成可视化
        viz_path = self.visualize_enhanced_results(features, cluster_labels, labels, model_labels, kmeans, scaler)

        # 生成报告
        report_path = self.generate_enhanced_report(features, cluster_labels, labels, model_labels, models_data)

        return {
            'models_data': models_data,
            'features': features,
            'labels': labels,
            'model_labels': model_labels,
            'cluster_labels': cluster_labels,
            'kmeans': kmeans,
            'scaler': scaler,
            'visualization_path': viz_path,
            'report_path': report_path
        }

    def perform_clustering(self, features: np.ndarray, n_clusters: int = None) -> Tuple[
        np.ndarray, KMeans, StandardScaler]:
        """执行聚类分析"""
        # 标准化特征
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features)

        # 确定最优聚类数 - 修复样本数不足的问题
        n_samples = features.shape[0]
        if n_clusters is None:
            # 聚类数应该在2到n_samples-1之间
            n_clusters = min(4, max(2, n_samples // 2))
        else:
            # 确保聚类数在有效范围内
            n_clusters = max(2, min(n_clusters, n_samples - 1))
        
        print(f"样本数: {n_samples}, 使用聚类数: {n_clusters}")

        # 执行K-means聚类
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(features_scaled)

        # 计算轮廓系数 - 只有当聚类数大于1且小于样本数时才计算
        if len(np.unique(cluster_labels)) > 1 and len(np.unique(cluster_labels)) < n_samples:
            try:
                silhouette_avg = silhouette_score(features_scaled, cluster_labels)
                print(f"聚类完成: {n_clusters} 个聚类, 轮廓系数: {silhouette_avg:.3f}")
            except ValueError as e:
                print(f"聚类完成: {n_clusters} 个聚类 (无法计算轮廓系数: {e})")
        else:
            print(f"聚类完成: {n_clusters} 个聚类 (样本数不足，无法计算轮廓系数)")

        return cluster_labels, kmeans, scaler

    def visualize_enhanced_results(self, features: np.ndarray, cluster_labels: np.ndarray,
                                   labels: List[str], model_labels: List[str],
                                   kmeans: KMeans, scaler: StandardScaler) -> str:
        """生成增强版可视化结果"""
        features_scaled = scaler.transform(features)

        # 设置图形样式
        plt.style.use('default')
        fig = plt.figure(figsize=(20, 16))

        # 颜色映射
        unique_clusters = np.unique(cluster_labels)
        colors = plt.cm.Set3(np.linspace(0, 1, len(unique_clusters)))

        # 1. PCA降维可视化
        plt.subplot(3, 3, 1)
        pca = PCA(n_components=2)
        features_pca = pca.fit_transform(features_scaled)

        for i, cluster in enumerate(unique_clusters):
            mask = cluster_labels == cluster
            plt.scatter(features_pca[mask, 0], features_pca[mask, 1],
                        c=[colors[i]], label=f'聚类 {cluster}', alpha=0.7, s=60)

        plt.title('PCA--12312312', fontsize=14, fontweight='bold')
        plt.xlabel(f'PC1 (解释方差: {pca.explained_variance_ratio_[0]:.2%})')
        plt.ylabel(f'PC2 (解释方差: {pca.explained_variance_ratio_[1]:.2%})')
        plt.legend()
        plt.grid(True, alpha=0.3)

        # 2. 资金vs未完成产品散点图（关键对比）
        plt.subplot(3, 3, 2)
        fund_mean_idx = 0  # fund_mean的索引
        unfinished_mean_idx = 8  # unfinished_mean的索引

        for i, cluster in enumerate(unique_clusters):
            mask = cluster_labels == cluster
            plt.scatter(features[mask, fund_mean_idx], features[mask, unfinished_mean_idx],
                        c=[colors[i]], label=f'聚类 {cluster}', alpha=0.7, s=60)

        plt.title('资金 vs 未完成产品分布', fontsize=14, fontweight='bold')
        plt.xlabel('平均资金')
        plt.ylabel('平均未完成产品数量')
        plt.legend()
        plt.grid(True, alpha=0.3)

        # 3. 聚类中心热力图
        plt.subplot(3, 3, 3)
        centers = kmeans.cluster_centers_
        feature_names_short = [
            'Fund_M', 'Fund_S', 'Fund_CV', 'Fund_R',
            'Inv_M', 'Inv_S', 'Inv_CV', 'Inv_R',
            'Unf_M', 'Unf_S', 'Unf_CV', 'Unf_R',
            'Fin_M', 'Fin_S', 'Fin_CV', 'Fin_R',
            'F_I_Corr', 'F_U_Corr', 'F_F_Corr', 'U_F_Corr',
            'Eff_R', 'Unf_R', 'Prod_E', 'Ord_F'
        ]

        sns.heatmap(centers.T, annot=True, fmt='.2f', cmap='RdYlBu_r',
                    xticklabels=[f'聚类{i}' for i in unique_clusters],
                    yticklabels=feature_names_short, cbar_kws={'label': '标准化值'})
        plt.title('聚类中心特征热力图', fontsize=14, fontweight='bold')
        plt.xticks(rotation=0)
        plt.yticks(rotation=0)

        # 4. 未完成产品特征雷达图
        plt.subplot(3, 3, 4, projection='polar')
        unfinished_features = [8, 9, 10, 11]  # 未完成产品的4个特征
        angles = np.linspace(0, 2 * np.pi, len(unfinished_features), endpoint=False).tolist()
        angles += angles[:1]  # 闭合

        for i, cluster in enumerate(unique_clusters):
            mask = cluster_labels == cluster
            cluster_unfinished = features_scaled[mask][:, unfinished_features].mean(axis=0)
            cluster_unfinished = np.concatenate([cluster_unfinished, [cluster_unfinished[0]]])  # 闭合

            plt.plot(angles, cluster_unfinished, 'o-', linewidth=2, label=f'聚类{cluster}', color=colors[i])
            plt.fill(angles, cluster_unfinished, alpha=0.25, color=colors[i])

        plt.xticks(angles[:-1], ['均值', '标准差', '变异系数', '范围'])
        plt.title('未完成产品特征雷达图', fontsize=14, fontweight='bold', pad=20)
        plt.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))

        # 5. 生产效率箱线图
        plt.subplot(3, 3, 5)
        production_efficiency_idx = 22  # production_efficiency的索引
        efficiency_data = [features[cluster_labels == cluster, production_efficiency_idx]
                           for cluster in unique_clusters]

        box_plot = plt.boxplot(efficiency_data, labels=[f'聚类{i}' for i in unique_clusters], patch_artist=True)
        for patch, color in zip(box_plot['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        plt.title('生产效率分布', fontsize=14, fontweight='bold')
        plt.ylabel('生产效率')
        plt.grid(True, alpha=0.3)

        # 6. 订单履约能力对比
        plt.subplot(3, 3, 6)
        fulfillment_capacity_idx = 23  # order_fulfillment_capacity的索引
        cluster_fulfillment = [features[cluster_labels == cluster, fulfillment_capacity_idx].mean()
                               for cluster in unique_clusters]

        bars = plt.bar([f'聚类{i}' for i in unique_clusters], cluster_fulfillment,
                       color=colors, alpha=0.7)
        plt.title('订单履约能力对比', fontsize=14, fontweight='bold')
        plt.ylabel('履约能力')
        plt.grid(True, alpha=0.3, axis='y')

        # 添加数值标签
        for bar, value in zip(bars, cluster_fulfillment):
            plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                     f'{value:.3f}', ha='center', va='bottom')

        # 7. 模型分布饼图
        plt.subplot(3, 3, 7)
        model_counts = pd.Series(model_labels).value_counts()
        plt.pie(model_counts.values, labels=model_counts.index, autopct='%1.1f%%', startangle=90)
        plt.title('模型数据分布', fontsize=14, fontweight='bold')

        # 8. 相关性矩阵（关键相关性）
        plt.subplot(3, 3, 8)
        corr_indices = [16, 17, 18, 19]  # 相关性特征的索引
        corr_names = ['资金-库存', '资金-未完成', '资金-已完成', '未完成-已完成']
        corr_data = features[:, corr_indices]

        corr_matrix = np.corrcoef(corr_data.T)
        sns.heatmap(corr_matrix, annot=True, fmt='.3f', cmap='RdYlBu_r',
                    xticklabels=corr_names, yticklabels=corr_names)
        plt.title('关键相关性矩阵', fontsize=14, fontweight='bold')
        plt.xticks(rotation=45)
        plt.yticks(rotation=0)

        # 9. 聚类轮廓分析
        plt.subplot(3, 3, 9)
        if len(unique_clusters) > 1:
            silhouette_vals = silhouette_samples(features_scaled, cluster_labels)
            y_lower = 10

            for i, cluster in enumerate(unique_clusters):
                cluster_silhouette_vals = silhouette_vals[cluster_labels == cluster]
                cluster_silhouette_vals.sort()

                size_cluster_i = cluster_silhouette_vals.shape[0]
                y_upper = y_lower + size_cluster_i

                plt.fill_betweenx(np.arange(y_lower, y_upper), 0, cluster_silhouette_vals,
                                  facecolor=colors[i], edgecolor=colors[i], alpha=0.7)

                plt.text(-0.05, y_lower + 0.5 * size_cluster_i, str(cluster))
                y_lower = y_upper + 10

            plt.axvline(x=silhouette_score(features_scaled, cluster_labels), color="red", linestyle="--")

        plt.title('聚类轮廓分析', fontsize=14, fontweight='bold')
        plt.xlabel('轮廓系数')
        plt.ylabel('聚类标签')

        plt.tight_layout()

        # 保存图片
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        viz_path = os.path.join(self.output_dir, f'enhanced_hybrid_clustering_analysis_{timestamp}.png')
        plt.savefig(viz_path, dpi=300, bbox_inches='tight')
        plt.close()

        print(f"可视化结果已保存: {viz_path}")
        return viz_path

    def generate_enhanced_report(self, features: np.ndarray, cluster_labels: np.ndarray,
                                 labels: List[str], model_labels: List[str],
                                 models_data: List[Dict]) -> str:
        """生成增强版分析报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(self.output_dir, f'enhanced_hybrid_clustering_report_{timestamp}.txt')

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("增强版B类企业跨模型聚类分析报告（混合数据源）\n")
            f.write("=" * 80 + "\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            # 数据源信息
            f.write("数据源信息:\n")
            f.write("-" * 40 + "\n")
            for model_data in models_data:
                summary = model_data['summary']
                f.write(f"模型: {model_data['model']}\n")
                f.write(f"  企业数量: {summary['total_companies']}\n")
                f.write(f"  资金记录: {summary['fund_records']} (来源: SQL)\n")
                f.write(f"  未完成记录: {summary['unfinished_records']} (来源: CSV)\n")
                f.write(f"  已完成记录: {summary['finished_records']} (来源: SQL)\n")
                f.write(f"  库存记录: {summary['inventory_records']} (来源: SQL)\n")
                f.write(f"  SQL文件: {summary['data_sources']['sql_file']}\n")
                f.write(f"  CSV文件: {summary['data_sources']['csv_file']}\n")
                f.write(f"  run_uuid: {summary['data_sources']['run_uuid']}\n")
                f.write(f"  run_id: {summary['data_sources']['run_id']}\n\n")

            # 特征说明
            f.write("特征说明:\n")
            f.write("-" * 40 + "\n")
            feature_descriptions = [
                "1-4: 资金特征 (均值、标准差、变异系数、范围)",
                "5-8: 库存特征 (均值、标准差、变异系数、范围)",
                "9-12: 未完成产品特征 (均值、标准差、变异系数、范围) - 关键指标",
                "13-16: 已完成产品特征 (均值、标准差、变异系数、范围)",
                "17-20: 相关性特征 (资金-库存、资金-未完成、资金-已完成、未完成-已完成)",
                "21-24: 效率特征 (效率比、未完成比例、生产效率、订单履约能力)"
            ]
            for desc in feature_descriptions:
                f.write(f"  {desc}\n")
            f.write("\n")

            # 聚类结果分析
            unique_clusters = np.unique(cluster_labels)
            f.write(f"聚类结果分析 (共{len(unique_clusters)}个聚类):\n")
            f.write("-" * 40 + "\n")

            for cluster in unique_clusters:
                mask = cluster_labels == cluster
                cluster_features = features[mask]
                cluster_labels_list = [labels[i] for i in range(len(labels)) if mask[i]]

                f.write(f"\n聚类 {cluster} (共{np.sum(mask)}个企业):\n")
                f.write(f"  企业: {', '.join(cluster_labels_list)}\n")

                # 关键指标分析
                avg_fund = cluster_features[:, 0].mean()
                avg_inventory = cluster_features[:, 4].mean()
                avg_unfinished = cluster_features[:, 8].mean()  # 关键指标
                avg_finished = cluster_features[:, 12].mean()
                avg_fund_unfinished_corr = cluster_features[:, 17].mean()  # 跨数据源相关性
                avg_production_efficiency = cluster_features[:, 22].mean()
                avg_fulfillment_capacity = cluster_features[:, 23].mean()

                f.write(f"  平均资金: {avg_fund:.2f}\n")
                f.write(f"  平均库存: {avg_inventory:.2f}\n")
                f.write(f"  平均未完成产品: {avg_unfinished:.2f} (关键指标)\n")
                f.write(f"  平均已完成产品: {avg_finished:.2f}\n")
                f.write(f"  资金-未完成相关性: {avg_fund_unfinished_corr:.3f} (跨数据源)\n")
                f.write(f"  生产效率: {avg_production_efficiency:.3f}\n")
                f.write(f"  订单履约能力: {avg_fulfillment_capacity:.3f}\n")

                # 聚类特征描述
                description = self._describe_enhanced_cluster(
                    avg_fund, avg_inventory, avg_unfinished, avg_finished,
                    avg_fund_unfinished_corr, avg_production_efficiency, avg_fulfillment_capacity
                )
                f.write(f"  特征描述: {description}\n")

            # 跨模型对比分析
            f.write("\n跨模型对比分析:\n")
            f.write("-" * 40 + "\n")
            model_stats = {}
            for model in set(model_labels):
                model_mask = np.array(model_labels) == model
                if np.any(model_mask):
                    model_features = features[model_mask]
                    model_stats[model] = {
                        'count': np.sum(model_mask),
                        'avg_fund': model_features[:, 0].mean(),
                        'avg_unfinished': model_features[:, 8].mean(),
                        'avg_production_efficiency': model_features[:, 22].mean()
                    }

            for model, stats in model_stats.items():
                f.write(f"{model}: {stats['count']}个企业, ")
                f.write(f"平均资金={stats['avg_fund']:.0f}, ")
                f.write(f"平均未完成={stats['avg_unfinished']:.0f}, ")
                f.write(f"生产效率={stats['avg_production_efficiency']:.3f}\n")

            # 关键发现
            f.write("\n关键发现:\n")
            f.write("-" * 40 + "\n")
            f.write("1. 数据源整合: 成功整合SQL文件(资金、库存)和CSV文件(未完成产品)数据\n")
            f.write("2. 跨数据源相关性: 分析了资金与未完成产品之间的关联性\n")
            f.write("3. 未完成产品指标: 作为关键的库存和资金影响因子进行重点分析\n")
            f.write("4. 生产效率评估: 基于已完成与未完成产品比例计算效率指标\n")
            f.write("5. 订单履约能力: 基于未完成产品波动性评估企业履约稳定性\n")

        print(f"分析报告已保存: {report_path}")
        return report_path

    def _describe_enhanced_cluster(self, avg_fund: float, avg_inventory: float,
                                   avg_unfinished: float, avg_finished: float,
                                   avg_fund_unfinished_corr: float, avg_production_efficiency: float,
                                   avg_fulfillment_capacity: float) -> str:
        """描述聚类特征"""
        descriptions = []

        # 资金水平
        if avg_fund > 10000:
            descriptions.append("高资金")
        elif avg_fund > 5000:
            descriptions.append("中等资金")
        else:
            descriptions.append("低资金")

        # 未完成产品水平（关键指标）
        if avg_unfinished > 100:
            descriptions.append("高未完成订单")
        elif avg_unfinished > 50:
            descriptions.append("中等未完成订单")
        else:
            descriptions.append("低未完成订单")

        # 生产效率
        if avg_production_efficiency > 2:
            descriptions.append("高效生产")
        elif avg_production_efficiency > 1:
            descriptions.append("正常生产")
        else:
            descriptions.append("低效生产")

        # 履约能力
        if avg_fulfillment_capacity > 0.8:
            descriptions.append("稳定履约")
        elif avg_fulfillment_capacity > 0.6:
            descriptions.append("一般履约")
        else:
            descriptions.append("履约风险")

        # 资金与未完成产品相关性（跨数据源）
        if abs(avg_fund_unfinished_corr) > 0.5:
            if avg_fund_unfinished_corr > 0:
                descriptions.append("资金与未完成正相关")
            else:
                descriptions.append("资金与未完成负相关")

        return ", ".join(descriptions)


def main():
    """主函数"""
    try:
        # 创建分析实例
        analyzer = EnhancedHybridBCompanyClusteringAnalysis()

        # 运行单模型聚类分析 - 每个模型内部单独聚类
        print("开始运行单模型聚类分析...")
        results = analyzer.run_all_single_model_analyses(models=['deepseek', 'gpt', 'qwen'], n_clusters=None)

        print("\n" + "=" * 50)
        print("单模型聚类分析完成!")
        print(f"综合报告: {results['comprehensive_report_path']}")
        
        # 显示各个分析的结果
        for analysis_type in ['BC合并分析', 'B类分析', 'C类分析']:
            if analysis_type in results:
                print(f"\n{analysis_type}结果:")
                for model in ['deepseek', 'gpt', 'qwen']:
                    if model in results[analysis_type]:
                        model_result = results[analysis_type][model]
                        print(f"  {model}: 可视化 - {model_result['visualization_path']}")
                        print(f"  {model}: 报告 - {model_result['report_path']}")
        
        print("=" * 50)

    except Exception as e:
        print(f"分析过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()