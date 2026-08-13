import copy
import json
import os
import os
import random
from abc import abstractmethod
from collections import deque
from typing import Any, Callable, Dict, List, Optional, Union
import itertools
import jsonc
import numpy as np
from ..agent.distribution import (
    ChoiceDistribution,
    ConstantDistribution,
    Distribution,
    SequentialSampler,
    UniformIntDistribution,
    UniformFloatDistribution,
    get_field_value,
    sample_field_value,
)
from ..agent.memory_config_generator import MemoryT
from ..environment.economy import EconomyEntityType
from utils.path_utils import get_project_path
from utils.path_utils import get_project_path
# 在文件顶部添加
_global_enterprise_sampler = None
pareto_param = 8
payment_max_skill_multiplier_base = 950
payment_max_skill_multiplier = float(payment_max_skill_multiplier_base)
pmsm = payment_max_skill_multiplier
pareto_samples = np.random.pareto(pareto_param, size=(1000, 10))
clipped_skills = np.minimum(pmsm, (pmsm - 1) * pareto_samples + 1)
sorted_clipped_skills = np.sort(clipped_skills, axis=1)
agent_skills = list(sorted_clipped_skills.mean(axis=0))

__all__ = [
    "memory_config_societyagent",
    "memory_config_newfirm",
    "memory_config_firm",
    "memory_config_government",
    "memory_config_bank",
    "memory_config_nbs",
    "DEFAULT_DISTRIBUTIONS",
    "DEFAULT_ENTERPRISE_DISTRIBUTIONS",
    "get_enterprise_distributioons",
]

# Default distributions for different profile fields
DEFAULT_DISTRIBUTIONS: dict[str, Distribution] = {
    "name": ChoiceDistribution(
        choices=[
            "Alice",
            "Bob",
            "Charlie",
            "David",
            "Eve",
            "Frank",
            "Grace",
            "Helen",
            "Ivy",
            "Jack",
            "Kelly",
            "Lily",
            "Mike",
            "Nancy",
            "Oscar",
            "Peter",
            "Queen",
            "Rose",
            "Sam",
            "Tom",
            "Ulysses",
            "Vicky",
            "Will",
            "Xavier",
            "Yvonne",
            "Zack",
        ]
    ),
    "gender": ChoiceDistribution(choices=["male", "female"]),
    "age": UniformIntDistribution(min_value=18, max_value=65),
    "education": ChoiceDistribution(
        choices=["Doctor", "Master", "Bachelor", "College", "High School"]
    ),
    "skill": ChoiceDistribution(
        choices=[
            "Good at problem-solving",
            "Good at communication",
            "Good at creativity",
            "Good at teamwork",
            "Other",
        ]
    ),
    "occupation": ChoiceDistribution(
        choices=[
            "Student",
            "Teacher",
            "Doctor",
            "Engineer",
            "Manager",
            "Businessman",
            "Artist",
            "Athlete",
            "Other",
        ]
    ),
    "family_consumption": ChoiceDistribution(choices=["low", "medium", "high"]),
    "consumption": ChoiceDistribution(
        choices=["low", "slightly low", "medium", "slightly high", "high"]
    ),
    "personality": ChoiceDistribution(
        choices=["outgoint", "introvert", "ambivert", "extrovert"]
    ),
    "income": UniformIntDistribution(min_value=1000, max_value=20000),
    "currency": UniformIntDistribution(min_value=1000, max_value=100000),
    "residence": ChoiceDistribution(choices=["city", "suburb", "rural"]),
    "city": ConstantDistribution(value="New York"),
    "race": ChoiceDistribution(
        choices=[
            "Chinese",
            "American",
            "British",
            "French",
            "German",
            "Japanese",
            "Korean",
            "Russian",
            "Other",
        ]
    ),
    "religion": ChoiceDistribution(
        choices=["none", "Christian", "Muslim", "Buddhist", "Hindu", "Other"]
    ),
    "marital_status": ChoiceDistribution(
        choices=["not married", "married", "divorced", "widowed"]
    ),
}


# DEFAULT_ENTERPRISE_DISTRIBUTIONS: dict[str, Distribution] = {
#     "company_name": ChoiceDistribution(
#         choices=[
#             "TechNova Inc.",
#             "GreenFuture Ltd.",
#             "OmniCorp",
#             "NeoTrade Group",
#             "AstroDynamics",
#             "GlobalFusion",
#             "BluePeak Industries",
#             "EcoWise Enterprises",
#             "UrbanEdge Holdings",
#             "NextPhase Inc.",
#         ]
#     ),
#     "industry": ChoiceDistribution(
#         choices=[
#             "Technology",
#             "Manufacturing",
#             "Retail",
#             "Finance",
#             "Healthcare",
#             "Energy",
#             "Transportation",
#             "Education",
#             "Hospitality",
#             "Agriculture",
#         ]
#     ),
#     "size": ChoiceDistribution(choices=["Small", "Medium", "Large"]),
#     "registered_capital": UniformIntDistribution(min_value=1_000_000, max_value=500_000_000),
#     "founded_year": UniformIntDistribution(min_value=1950, max_value=2024),
#     "location": ChoiceDistribution(
#         choices=[
#             "New York",
#             "San Francisco",
#             "London",
#             "Berlin",
#             "Shanghai",
#             "Tokyo",
#             "Seoul",
#             "Mumbai",
#             "Dubai",
#             "Toronto",
#         ]
#     ),
#     "main_product": ChoiceDistribution(
#         choices=[
#             "Consumer Electronics",
#             "Financial Services",
#             "Automobiles",
#             "Software Solutions",
#             "Pharmaceuticals",
#             "Renewable Energy",
#             "Clothing",
#             "Food & Beverages",
#             "Machinery",
#             "Education Platforms",
#         ]
#     ),
#     "annual_revenue": UniformIntDistribution(min_value=10_000_000, max_value=5_000_000_000),
#     "profit_margin": UniformFloatDistribution(min_value=0.01, max_value=0.3),
#     "employee_count": UniformIntDistribution(min_value=50, max_value=100_000),
#     "CEO": ChoiceDistribution(
#         choices=[
#             "Alice Zhang",
#             "Robert Lee",
#             "Chen Wei",
#             "Emily Davis",
#             "Michael Brown",
#             "Satoshi Tanaka",
#             "Linda Kim",
#             "Juan Carlos",
#             "Anna Schmidt",
#             "John Smith",
#         ]
#     ),
#     "stock_status": ChoiceDistribution(choices=["Private", "Public"]),
#     "culture": ChoiceDistribution(
#         choices=["Innovative", "Conservative", "Aggressive", "Collaborative"]
#     ),
#     "sustainability_rating": UniformFloatDistribution(min_value=0.0, max_value=1.0),
#     "headcount":UniformIntDistribution(min_value=50, max_value=10000),
#     "ownership_type":ChoiceDistribution(choices=["state enterprise", "foreign enterprise", "private enterprise"]),
# }

def generate_enterprise_distributions(json_path: str, limit: int) -> Dict[str, Any]:
    with open(json_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    all_entries = []
    for level_data in raw_data.values():  # 遍历 level
        all_entries.extend(level_data)

    # all_entries = all_entries[:limit]

    names = []
    products = []
    product_stocks = []
    available_materials = []
    inventory_systems = []
    company_capacitys = []
    funds = []
    company_capacitys = []
    funds = []
    for entry in all_entries:
        names.append(entry.get("name", ""))
        company_capacitys.append(entry.get("company_capacity", 50))
        funds.append(entry.get("initial_capital",10000))
        company_capacitys.append(entry.get("company_capacity", 50))
        funds.append(entry.get("initial_capital",10000))
        product_infos = entry.get("main_products", [])
        available_materials.append(entry.get("available_materials", []))
        # 获取库存系统信息并转换为正确格式
        inventory_system = entry.get("inventory_system", {})
        product_inventory_data = inventory_system.get("products", {})
        material_inventory_data = inventory_system.get("materials", {})

        # 转换为列表格式以兼容monitor_and_log_inventory方法
        product_inventory_list = []
        for product_id, product_info in product_inventory_data.items():
            product_inventory_list.append({
                "product_name": product_info.get("product_name", ""),
                "product_id": int(product_id),
                "quantity": product_info.get("quantity", 0)
            })

        material_inventory_list = []
        for material_id, material_info in material_inventory_data.items():
            material_inventory_list.append({
                "product_name": material_info.get("product_name", ""),
                "product_id": int(material_id),
                "quantity": material_info.get("quantity", 0)
            })

        # 保持原始格式用于block操作，同时添加列表格式用于MLflow记录
        formatted_inventory_system = {
            "products": product_inventory_data,  # 保持原始字典格式
            "materials": material_inventory_data,  # 保持原始字典格式
            "product_inventory": product_inventory_list,  # 添加列表格式
            "material_inventory": material_inventory_list  # 添加列表格式
        }

        inventory_systems.append(formatted_inventory_system)

        product = []
        product_stock = []

        for product_info in product_infos:
            product_name = product_info.get("product_name", "")
            product_id = product_info.get("product_id", 0)
            consumption_rate = product_info.get("consumption_rate", {})
            net_manufacturing_cost = product_info.get("net_manufacturing_cost",0)
            # 处理相关材料
            related_materials = product_info.get("related_materials", [])
            product_materials = []
            for material in related_materials:
                product_materials.append({
                    "material_name": material.get("material_name", ""),
                    "material_id": material.get("material_id", 0),
                    "quantity_needed": material.get("quantity_needed", 1)
                })

            # 使用从inventory_system获取的库存值
            inventory_value = 100  # 默认值
            if str(product_id) in product_inventory_data:
                inventory_value = product_inventory_data[str(product_id)].get("quantity", 100)

            product.append({
                "product_name": product_name,
                "product_id": product_id,
                "base_price": product_info.get("base_price", 0),
                "sell_price": -1,
                "inventory": inventory_value,
                "is_terminal_product": product_info.get("is_terminal_product", False),
                "product_type": product_info.get("product_type", ""),
                "product_construct": product_info.get("product_construct", {}),
                "manufacturing_cost": product_info.get("manufacturing_cost", 50),
                "profit_margin": product_info.get("profit_margin", 0.2),
                "consumption_rate": consumption_rate,
                "related_materials": product_materials,
                "net_manufacturing_cost":net_manufacturing_cost,
            })

            # 添加到product_stock
            product_stock.append({
                "product_id": product_id,
                "product_name": product_name,
                "quantity": inventory_value
            })

        products.append(product)
        product_stocks.append(product_stock)

    return {
        "name": ChoiceDistribution(choices=names),
        "products": ChoiceDistribution(choices=products),
        "product_stocks": ChoiceDistribution(choices=product_stocks),
        "available_materials": ChoiceDistribution(choices=available_materials),
        "inventory_system": ChoiceDistribution(choices=inventory_systems),
        "company_capacity": ChoiceDistribution(choices=company_capacitys),
        "fund":ChoiceDistribution(choices=funds)
    }


def get_enterprise_distributioons(limit):
    json_file = get_project_path("neo4j/industry_test.json")
    return generate_enterprise_distributions(json_file, limit)
    json_file = get_project_path("neo4j/industry_test.json")
    return generate_enterprise_distributions(json_file, limit)


def memory_config_societyagent(
        distributions: dict[str, Distribution],
) -> tuple[dict[str, MemoryT], dict[str, MemoryT], dict[str, Any]]:
    EXTRA_ATTRIBUTES = {
        "type": (str, "citizen"),
        # Needs Model
        "hunger_satisfaction": (float, 0.9, False),  # hunger satisfaction
        "energy_satisfaction": (float, 0.9, False),  # energy satisfaction
        "safety_satisfaction": (float, 0.4, False),  # safety satisfaction
        "social_satisfaction": (float, 0.6, False),  # social satisfaction
        "current_need": (str, "none", False),
        # Plan Behavior Model
        "current_plan": (dict, {}, False),
        "execution_context": (dict, {}, False),
        "plan_history": (list, [], False),
        # cognition
        "emotion": (
            dict,
            {
                "sadness": 5,
                "joy": 5,
                "fear": 5,
                "disgust": 5,
                "anger": 5,
                "surprise": 5,
            },
            False,
        ),
        "attitude": (dict, {}, True),
        "thought": (str, "Currently nothing good or bad is happening", True),
        "emotion_types": (str, "Relief", True),
        # economy
        "work_skill": (
            float,
            random.choice(agent_skills),
            True,
        ),  # work skill
        "tax_paid": (float, 0.0, False),  # tax paid
        "consumption_currency": (float, 0.0, False),  # consumption
        "goods_demand": (int, 0, False),
        "goods_consumption": (int, 0, False),
        "work_propensity": (float, 0.0, False),
        "consumption_propensity": (float, 0.0, False),
        "to_consumption_currency": (float, 0.0, False),
        "firm_id": (int, sample_field_value(distributions, "firm_id"), False),
        "government_id": (
            int,
            sample_field_value(distributions, "government_id"),
            False,
        ),
        "bank_id": (int, sample_field_value(distributions, "bank_id"), False),
        "nbs_id": (int, sample_field_value(distributions, "nbs_id"), False),
        "dialog_queue": (deque(maxlen=3), [], False),
        "firm_forward": (int, 0, False),
        "bank_forward": (int, 0, False),
        "nbs_forward": (int, 0, False),
        "government_forward": (int, 0, False),
        "forward": (int, 0, False),
        "depression": (float, 0.0, False),
        "ubi_opinion": (list, [], False),
        "working_experience": (list, [], False),
        "work_hour_month": (float, 160, False),
        "work_hour_finish": (float, 0, False),
        # social
        "friends": (list, [], False),  # friends list
        "relationships": (dict, {}, False),  # relationship strength with each friend
        "relation_types": (dict, {}, False),
        "chat_histories": (dict, {}, False),  # all chat histories
        "interactions": (dict, {}, False),  # all interaction records
        # mobility
        "number_poi_visited": (int, 1, False),
        "location_knowledge": (dict, {}, False),  # location knowledge
    }

    PROFILE = {
        "name": (str, sample_field_value(distributions, "name"), True),
        "gender": (str, sample_field_value(distributions, "gender"), True),
        "age": (int, sample_field_value(distributions, "age"), True),
        "education": (str, sample_field_value(distributions, "education"), True),
        "skill": (str, sample_field_value(distributions, "skill"), True),
        "occupation": (str, sample_field_value(distributions, "occupation"), True),
        "family_consumption": (
            str,
            sample_field_value(distributions, "family_consumption"),
            True,
        ),
        "consumption": (str, sample_field_value(distributions, "consumption"), True),
        "personality": (str, sample_field_value(distributions, "personality"), True),
        "income": (float, sample_field_value(distributions, "income"), True),
        "currency": (float, sample_field_value(distributions, "currency"), True),
        "residence": (str, sample_field_value(distributions, "residence"), True),
        "city": (str, sample_field_value(distributions, "city"), True),
        "race": (str, sample_field_value(distributions, "race"), True),
        "religion": (str, sample_field_value(distributions, "religion"), True),
        "marital_status": (
            str,
            sample_field_value(distributions, "marital_status"),
            True,
        ),
    }

    BASE = {
        "home": {
            "aoi_position": {"aoi_id": sample_field_value(distributions, "home_aoi_id")}
        },
        "work": {
            "aoi_position": {"aoi_id": sample_field_value(distributions, "work_aoi_id")}
        },
    }

    return EXTRA_ATTRIBUTES, PROFILE, BASE


def get_enterprise_data_by_id(agent_id):
    """根据agent_id直接从industry_test.json获取企业数据"""
    import os

    # 构建正确的文件路径
    json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "neo4j", "industry_test.json")

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except FileNotFoundError:
        # 如果相对路径不工作，尝试绝对路径
        json_path = "/home/cuda/agentsociety-enterprise/neo4j/industry_test.json"
        with open(json_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

    # 遍历所有level找到对应id的企业
    for level_data in raw_data.values():
        for enterprise in level_data:
            if enterprise.get("id") == agent_id:
                # 处理产品信息，保持与原有格式兼容
                product_infos = enterprise.get("main_products", [])
                inventory_system = enterprise.get("inventory_system", {})
                product_inventory_data = inventory_system.get("products", {})
                material_inventory_data = inventory_system.get("materials", {})
                company_capacitys = enterprise.get("company_capacity",50)
                funds = enterprise.get("initial_capital")
                company_capacitys = enterprise.get("company_capacity",50)
                funds = enterprise.get("initial_capital")
                # 转换为列表格式以兼容monitor_and_log_inventory方法
                product_inventory_list = []
                for product_id, product_info in product_inventory_data.items():
                    product_inventory_list.append({
                        "product_name": product_info.get("product_name", ""),
                        "product_id": int(product_id),
                        "quantity": product_info.get("quantity", 0)
                    })

                material_inventory_list = []
                for material_id, material_info in material_inventory_data.items():
                    material_inventory_list.append({
                        "product_name": material_info.get("product_name", ""),
                        "product_id": int(material_id),
                        "quantity": material_info.get("quantity", 0)
                    })

                # 保持原始格式用于block操作，同时添加列表格式用于MLflow记录
                formatted_inventory_system = {
                    "products": product_inventory_data,  # 保持原始字典格式
                    "materials": material_inventory_data,  # 保持原始字典格式
                    "product_inventory": product_inventory_list,  # 添加列表格式
                    "material_inventory": material_inventory_list  # 添加列表格式
                }

                # 处理产品信息
                products = []
                product_stocks = []

                for product_info in product_infos:
                    product_name = product_info.get("product_name", "")
                    product_id = product_info.get("product_id", 0)
                    consumption_rate = product_info.get("consumption_rate", {})
                    net_manufacturing_cost = product_info.get("net_manufacturing_cost",0)
                    # 处理相关材料
                    related_materials = product_info.get("related_materials", [])
                    product_materials = []
                    for material in related_materials:
                        product_materials.append({
                            "material_name": material.get("product_name", ""),  # 注意这里用product_name
                            "material_id": material.get("product_id", 0),  # 注意这里用product_id
                            "quantity_needed": material.get("quantity_needed", 1)
                        })

                    # 使用从inventory_system获取的库存值
                    inventory_value = 100  # 默认值
                    if str(product_id) in product_inventory_data:
                        inventory_value = product_inventory_data[str(product_id)].get("quantity", 100)

                    products.append({
                        "product_name": product_name,
                        "product_id": product_id,
                        "base_price": product_info.get("base_price", 100),
                        "sell_price": -1,
                        "inventory": inventory_value,
                        "is_terminal_product": product_info.get("is_terminal_product", False),
                        "product_type": product_info.get("product_type", ""),
                        "product_construct": product_info.get("product_construct", {}),
                        "manufacturing_cost": product_info.get("manufacturing_cost", 50),
                        "profit_margin": product_info.get("profit_margin", 0.2),
                        "consumption_rate": consumption_rate,
                        "related_materials": product_materials,
                        "net_manufacturing_cost":net_manufacturing_cost,
                    })

                    # 添加到product_stock
                    product_stocks.append({
                        "product_id": product_id,
                        "product_name": product_name,
                        "quantity": inventory_value
                    })

                return {
                    "name": enterprise.get("name"),
                    "products": products,
                    "product_stocks": product_stocks,
                    "available_materials": enterprise.get("available_materials", []),
                    "inventory_system": formatted_inventory_system,
                    "intelligence_level": enterprise.get("intelligence_level", 1),
                    "level": enterprise.get("level", 1),  # 新增level字段
                    "company_capacity": company_capacitys,
                    "fund": funds
                }

    # 如果没找到对应ID，返回默认值或抛出异常
    raise ValueError(f"未找到ID为 {agent_id} 的企业数据")


def memory_config_newfirm(distributions, agent_id=None):
    global _global_enterprise_sampler

    # 首先定义默认的financial_metrics
    default_financial_metrics = {
        'total_revenue': 0,
        'total_production_cost': 0,
        'total_material_cost': 0,
        'total_processing_cost': 0,
        'net_profit': 0
    }

    EXTRA_ATTRIBUTES = {
        "type": (str, "corporation"),  # 经营状态
        "firm_list": (list, [], False),  # 整体企业列表

        "product_inventory": (dict, {}, False),  # 产品库存
        "current_need": (list, [], False),
        "current_plan": (dict, [], False),
        # 新增：分期付款系统初始化
        "installment_plans": (list, [], False),  # 分期付款计划列表
        "history_product_order":(list,[],False),

        # 原有需求
        "price": (float, float(np.mean(agent_skills))),
        "inventory": (int, 0),
        "employees": (list, []),
        "demand": (int, 0),
        "sales": (int, 0),
        # "currency": (float, 1e12, False),  # currency is already defined in PROFILE_ATTRIBUTES
        "selling_demand": (float, 0.4, False),
        "replenish_demand": (float, 0.4, False),

        # 补充属性
        "base_profit": (int, 50, False),
        "freeRide_gain": (float, 5.0, False),
        "trans_cost": (int, 20, False),
        "collab_coeff": (float, 1.5, False),

        "has_join": (bool, False, False),
        "company_partner": (list, [], False),

        "p_join": (float, 0.4, False),
        "decision": (bool, False, False),
        "payoff_list": (list, [], False),

        "transaction_list": (list, [], False),

        # 需求参数
        "raw_material_urgency": (float, 0.1, False),  # 原材料紧缺度
        "inventory_pressure": (float, 0.1, False),  # 成品库存压力
        "capital_liquidity": (float, 0.1, False),  # 资金流动性，随支出下降，收入上升
        "order_fulfillment": (float, 0.1, False),  # 供应订单完成率
        "resource_utilization": (float, 0.1, False),  # 资源利用率
        "cashflow_health": (float, 0.1, False),  # 现金流健康度，应收账款延迟时下降
        "step_profit":(float,0.0,False),
        "make_cost":(float,0.0,False),

        # 制造类参数
        "product_value": (int, 50, False),
        "raw_material_stock": (int, 0, False),
        "finished_goods_stock": (int, 0, False),
        "cash_reserve": (int, 0, False),
        "credit_rating": (int, 1, False),

        # 新增：生产成本和财务指标
        "production_cost_history": [],
        "current_production_cost": [],
        "financial_metrics": (dict, {
            'total_revenue': 0,
            'total_production_cost': 0,
            'total_material_cost': 0,
            'total_processing_cost': 0,
            'net_profit': 0
        }, False),
        "transaction_cost_history": (list, [], False),  # 交易成本历史记录
        "Unfinished_order":(list,[],False),
        "produce_count":(list,[],False),
        "Position_cost":(float,0.0,False),

        # 供应类参数
        "max_production_cap": (int, 100, False),
        "production_cost": (int, 20, False),
        "raw_material_reserve": (int, 0, False),
        "equipment_efficiency": (float, 0.7, False),
        "accounts_receivable": (int, 0, False),
        "market_share": (float, 0.05, False),
    }

    # 如果提供了agent_id，直接从JSON数据中获取对应企业数据
    if agent_id is not None:
        try:
            enterprise_data = get_enterprise_data_by_id(agent_id)
            PROFILE = enterprise_data

            # inventory_system and intelligence_level are already defined in PROFILE_ATTRIBUTES
            # No need to add them to EXTRA_ATTRIBUTES to avoid duplicate declarations
            # product_stocks is already defined in PROFILE_ATTRIBUTES, no need to add to EXTRA_ATTRIBUTES

            # 确保financial_metrics始终存在且包含所有必要的键
            enterprise_financial_metrics = enterprise_data.get("financial_metrics", {})
            # 合并默认值和企业数据中的值
            merged_financial_metrics = {**default_financial_metrics, **enterprise_financial_metrics}
            EXTRA_ATTRIBUTES["financial_metrics"] = (
                dict,
                merged_financial_metrics,
                False
            )

        except (ValueError, FileNotFoundError) as e:
            print(f"警告：无法为agent_id={agent_id}获取企业数据，使用默认分配方式: {e}")
            # 回退到原有逻辑
            if _global_enterprise_sampler is None:
                _global_enterprise_sampler = SequentialSampler(distributions)
            PROFILE = _global_enterprise_sampler.sample_next()

            # inventory_system and intelligence_level are already defined in PROFILE_ATTRIBUTES
            # No need to add them to EXTRA_ATTRIBUTES to avoid duplicate declarations
            # product_stocks is already defined in PROFILE_ATTRIBUTES, no need to add to EXTRA_ATTRIBUTES
    else:
        # 保持原有逻辑作为fallback
        if _global_enterprise_sampler is None:
            _global_enterprise_sampler = SequentialSampler(distributions)
        PROFILE = _global_enterprise_sampler.sample_next()

        # inventory_system and intelligence_level are already defined in PROFILE_ATTRIBUTES
        # No need to add them to EXTRA_ATTRIBUTES to avoid duplicate declarations
        # product_stocks is already defined in PROFILE_ATTRIBUTES, no need to add to EXTRA_ATTRIBUTES

    BASE = {
        "headquarters": {
            "aoi_position": {"aoi_id": get_field_value(distributions, "hq_aoi_id")}
        },
    }

    return EXTRA_ATTRIBUTES, PROFILE, BASE


def memory_config_firm(
        distributions: dict[str, Distribution],
) -> tuple[dict[str, MemoryT], dict[str, Union[MemoryT, float]], dict[str, Any]]:
    EXTRA_ATTRIBUTES = {
        "type": (int, EconomyEntityType.Firm),
        "location": {
            "aoi_position": {"aoi_id": sample_field_value(distributions, "aoi_id")}
        },
        "price": (float, float(np.mean(agent_skills))),
        "inventory": (int, 0),
        "employees": (list, []),
        "employees_agent_id": (list, []),
        "nominal_gdp": (list, []),  # useless
        "real_gdp": (list, []),
        "unemployment": (list, []),
        "wages": (list, []),
        "demand": (int, 0),
        "sales": (int, 0),
        "prices": (list, [float(np.mean(agent_skills))]),
        "working_hours": (list, []),
        "depression": (list, []),
        "consumption_currency": (list, []),
        "income_currency": (list, []),
        "locus_control": (list, []),
        "bracket_cutoffs": (
            list,
            list(np.array([0, 9875, 40125, 85525, 163300, 207350, 518400]) / 12),
        ),
        "bracket_rates": (list, [0.1, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37]),
        "interest_rate": (float, 0.03),
        "citizen_ids": (list, []),
        "firm_id": (int, 0),
    }
    return EXTRA_ATTRIBUTES, {"currency": 1e12}, {}


def memory_config_government(
        distributions: dict[str, Distribution],
) -> tuple[dict[str, MemoryT], dict[str, Union[MemoryT, float]], dict[str, Any]]:
    p_subsidy_ini = random.uniform(0.5, 0.8)
    EXTRA_ATTRIBUTES = {
        "type": (int, EconomyEntityType.Government),
        # 'bracket_cutoffs': (list, list(np.array([0, 97, 394.75, 842, 1607.25, 2041, 5103])*100/12)),
        "bracket_cutoffs": (
            list,
            list(np.array([0, 9875, 40125, 85525, 163300, 207350, 518400]) / 12),
        ),
        "bracket_rates": (list, [0.1, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37]),
        "citizen_ids": (list, []),
        "citizens_agent_id": (list, []),
        "nominal_gdp": (list, []),  # useless
        "real_gdp": (list, []),
        "unemployment": (list, []),
        "wages": (list, []),
        "prices": (list, [float(np.mean(agent_skills))]),
        "working_hours": (list, []),
        "depression": (list, []),
        "consumption_currency": (list, []),
        "income_currency": (list, []),
        "locus_control": (list, []),
        "inventory": (int, 0),
        "interest_rate": (float, 0.03),
        "price": (float, float(np.mean(agent_skills))),
        "employees": (list, []),
        "firm_id": (int, 0),

        # 补充属性
        "budget_max": (float, 100.0),
        "subsidy_cost": (float, 1.0),
        "supervison_eff": (float, 1),

        "p_subsidy": (float, p_subsidy_ini),
        "desicion": (bool, False),
        "budget_rem": (float, 100.0),
        "expenditure": (float, 0),

        "enable_incentives": (bool, False),
        "policy_survey": (list, [])
    }
    return EXTRA_ATTRIBUTES, {"currency": 1e12}, {}


def memory_config_bank(
        distributions: dict[str, Distribution],
) -> tuple[dict[str, MemoryT], dict[str, Union[MemoryT, float]], dict[str, Any]]:
    EXTRA_ATTRIBUTES = {
        "type": (int, EconomyEntityType.Bank),
        "interest_rate": (float, 0.03),
        "citizen_ids": (list, []),
        "bracket_cutoffs": (
            list,
            list(np.array([0, 9875, 40125, 85525, 163300, 207350, 518400]) / 12),
        ),  # useless
        "bracket_rates": (list, [0.1, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37]),
        "inventory": (int, 0),
        "nominal_gdp": (list, []),  # useless
        "real_gdp": (list, []),
        "unemployment": (list, []),
        "wages": (list, []),
        "prices": (list, [float(np.mean(agent_skills))]),
        "working_hours": (list, []),
        "depression": (list, []),
        "consumption_currency": (list, []),
        "income_currency": (list, []),
        "locus_control": (list, []),
        "price": (float, float(np.mean(agent_skills))),
        "employees": (list, []),
        "firm_id": (int, 0),

        "policy_survey": (list, [])
    }
    return EXTRA_ATTRIBUTES, {"currency": 1e12}, {}


def memory_config_nbs(
        distributions: dict[str, Distribution],
) -> tuple[dict[str, MemoryT], dict[str, Union[MemoryT, float]], dict[str, Any]]:
    EXTRA_ATTRIBUTES = {
        "type": (int, EconomyEntityType.NBS),
        # economy simulator
        "citizen_ids": (list, []),
        "nominal_gdp": (dict, {}),
        "real_gdp": (dict, {}),
        "unemployment": (dict, {}),
        "wages": (dict, {}),
        "prices": (dict, {"0": float(np.mean(agent_skills))}),
        "working_hours": (dict, {}),
        "depression": (dict, {}),
        "consumption_currency": (dict, {}),
        "income_currency": (dict, {}),
        "locus_control": (dict, {}),
        # other
        "firm_id": (int, 0),
        "bracket_cutoffs": (
            list,
            list(np.array([0, 9875, 40125, 85525, 163300, 207350, 518400]) / 12),
        ),  # useless
        "bracket_rates": (list, [0.1, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37]),
        "inventory": (int, 0),
        "interest_rate": (float, 0.03),
        "price": (float, float(np.mean(agent_skills))),
        "employees": (list, []),
        "forward_times": (int, 0),

        "policy_survey": (list, [])
    }
    return EXTRA_ATTRIBUTES, {"currency": 1e12}, {}
