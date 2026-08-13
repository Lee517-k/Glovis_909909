from collections import defaultdict, deque
import json
import logging
import re
import time
from turtle import forward

import json_repair
import jsonc
import random

from agentsociety.agent.agent_base import Agent
from ...environment import Environment
from ...llm import LLM
from ...logger import get_logger
from ...memory import Memory
from ...agent import Block, FormatPrompt

__all__ = ["StockBlock"]


class StockBlock(Block):
    # 库存处理模块

    def __init__(
            self,
            agent: Agent,
            llm: LLM,
            environment: Environment,
            memory: Memory,
    ):
        super().__init__(
            "StockBlock", llm=llm, environment=environment, memory=memory
        )
        self._agent = agent
        self.register = False
        self.product_list = []
        # 记录缺乏的物流 --- 已记录的可能正在获取流程中，不反复申请需求
        self.insufficient_list = {}  # 修改：从 [] 改为 {}
        self.step_count = -1
        self.fund_history = []
        self.product_stock_history = defaultdict(lambda: deque(maxlen=20))
        self.had_insuffcient = False

    async def get_product_cost_info(self, product_name):
        """获取产品成本信息"""
        products = await self.memory.status.get("products") or []
        for product in products:
            if product.get("product_name") == product_name:
                return {
                    "manufacturing_cost": product.get("manufacturing_cost", 0),
                    "material_cost": product.get("material_cost", 0),
                    "net_manufacturing_cost": product.get("net_manufacturing_cost", 0)
                }
        return {"manufacturing_cost": 0, "material_cost": 0, "net_manufacturing_cost": 0}

    async def calculate_actual_material_cost(self, product_name, amount, recipe):
        """计算实际原料成本 - 使用inventory_system中保存的unit_cost"""
        total_material_cost = 0
        material_unit_cost = 0
        inventory_system = await self.memory.status.get("inventory_system") or {}
        materials_dict = inventory_system.get("materials", {})
        for material_name, amount_per_product in recipe.items():
            total_consumed = amount_per_product * amount

            # 从materials_dict中获取实际采购的unit_cost
            material_unit_cost = 0
            
            for material_id, material_info in materials_dict.items():
                if material_info.get("product_name") == material_name:
                    material_unit_cost = material_info.get("unit_cost", 0)
                    break
            if material_unit_cost == 0:
                # 查询市场价均价
                state = await self.environment.economy_client.get(id=-1, key="global_company_status")
                market_price = 0
                count = 0
                for company in state:
                    product_list = company["product_list"]
                    for product in product_list:
                        if product["product_name"] == material_name:
                            market_price+=product["sell_price"]
                            count+=1
                if count != 0:
                    material_unit_cost=market_price/count
                
            # 如果没有unit_cost，则从产品信息中获取base_price作为备选
            # 产品信息中只有公司自身产品的base_price，没有存储原料的base_price
            # if material_unit_cost == 0:
            #     products = await self.memory.status.get("products") or []
                
            #     print("TESTmaterials_dict",materials_dict,material_name,amount_per_product,recipe,products)
            #     for product in products:
            #         if product.get("product_name") == material_name:
            #             material_unit_cost = product.get("base_price", 0)
            #             break

            total_material_cost += total_consumed * material_unit_cost

        return total_material_cost,material_unit_cost

    async def get_processing_cost(self, product_name, amount):
        """获取加工费用"""
        cost_info = await self.get_product_cost_info(product_name)
        processing_cost_per_unit = cost_info.get("net_manufacturing_cost", 0)
        if self.step_count>= 100:
            processing_cost_per_unit = processing_cost_per_unit / 2
        
        return processing_cost_per_unit * amount,processing_cost_per_unit

    async def update_financial_metrics(self, cost_details):
        """更新财务指标"""
        financial_metrics = await self.memory.status.get("financial_metrics") or {}

        # 确保所有必需的键都存在
        default_metrics = {
            'total_revenue': 0,
            'total_production_cost': 0,
            'total_material_cost': 0,
            'total_processing_cost': 0,
            'net_profit': 0
        }

        # 合并默认值和现有值
        for key, default_value in default_metrics.items():
            if key not in financial_metrics:
                financial_metrics[key] = default_value

        financial_metrics['total_production_cost'] += cost_details['total_cost']
        financial_metrics['total_material_cost'] += cost_details['material_cost']
        financial_metrics['total_processing_cost'] += cost_details['processing_cost']
        financial_metrics['net_profit'] = financial_metrics['total_revenue'] - financial_metrics[
            'total_production_cost']

        await self.memory.status.update("financial_metrics", financial_metrics)

    async def check_insufficient(self):
        expired = [name for name, added_step in self.insufficient_list.items()
                   if self.step_count - added_step >= 2]  # 修改：使用 self.step_count
        for name in expired:
            del self.insufficient_list[name]
        if not self.had_insuffcient:
            # 主动检查库存
            inventory_system = await self.memory.status.get("inventory_system") or {}
            materials_dict = inventory_system.get("materials", {})
            products = await self.memory.status.get("products")
            products_dict = inventory_system.get("products", {})
            company_capacity = await self.memory.status.get("company_capacity")
            out_production = company_capacity * 1.25
            fid = await self.memory.status.get("id")
            need = await self.memory.status.get("current_need",[])
            for product in products:
                recipe_str = product["product_construct"]
                if recipe_str == "no need material":
                    continue
                else:
                    if True:
                        pattern = r'([\w_]+)\*(\d+(?:\.\d+)?)%'
                        matches = re.findall(pattern, recipe_str)
                        recipe = {name: float(percent) / 100 for name, percent in matches}
                        # 检查材料库存是否充足
                        for name, amount_per_product in recipe.items():
                            total_consumed = amount_per_product * out_production
                            material_stock = 0
                            for material_id, material_info in materials_dict.items():
                                if material_info.get("product_name") == name:
                                    material_stock = material_info.get("quantity", 0)
                                    break
                            has_taged = name in self.insufficient_list  # 修改：简化检查逻辑
                            if total_consumed > material_stock :
                                if not has_taged:
                                    new_need = ["Inventory insufficient", name]
                                    if new_need not in need:
                                        need.append(new_need)
                                        self.insufficient_list[name] = self.step_count  # 修改：直接赋值
                                        self.had_insuffcient = True
            await self.memory.status.update("current_need",need)
      

    def add_material_from_product(self, items):
        new_items = items
        for item in items:
            if isinstance(item.get("name"), str) and item["name"].startswith("product_"):
                # 提取 id 部分
                suffix = item["name"][len("product_"):]
                # 创建新对象
                new_item = {
                    "name": f"material_{suffix}",
                    "stock": item["stock"]
                }
                new_items.append(new_item)
        return new_items

    async def check_manufacturing_decison(self, product,base_price,inventory_system):
        fid = await self.memory.status.get("id")
        intelligence_level = await self.memory.status.get("intelligence_level",1)
        history_product_order = await self.memory.status.get("history_product_order")
        order = []
        for product_order in history_product_order:
            if product_order["name"] == product["product_name"]:
                order = product_order["history_order"]
        order_str = ""
        if len(order)>0:
            order_str = f"- These are the recent product sales order situations, including the quantity and revenue for each round : {order}"
        response_prompt = f"""Based on:
            - My profile: {{
                "company_name": "{await self.memory.status.get("name") or ""}",
                "current_company_fund": "{await self.memory.status.get("fund") or ""}",
                "company_inventory" : "{inventory_system}",
            }}
            - The following shows the outstanding payments for the company’s products. If the list is empty or the corresponding product’s Undelivered_portion value is 0, it means there are no unfinished orders, and processing decisions can be made freely based on circumstances. Otherwise, priority must be given to processing the products with outstanding portions : {await self.memory.status.get("Unfinished_order",[])}
            - If the current assessment shows that the product has no outstanding debts, but other products do, we should consider temporarily halting the production of the current product.
            - Below is the recent information on capital changes : {self.fund_history}
            - The Product name to be processed: {product["product_name"]}
            - The Raw material composition formula of the product : {product["product_construct"]}
            - Below is the latest inventory information for the product : {self.product_stock_history[product["product_name"]]}
            {order_str}
            - If there are products within the company that remain unsold, a maintenance cost of 0.5% of their cost price will be deducted in each round. The cost price : {base_price}
            - I need to decide whether to continue processing this product.
            - It is necessary to observe the company's capital changes and product inventory changes.
            - The sale of product inventory can bring about capital growth, while increasing products can also deplete funds, so it is necessary to maintain a good balance.
            - The short-term stability of funds and inventory is not important; the goal should still be to increase inventory for sales.
            - Only by maintaining sufficient inventory can one generate profitable sales orders.

            Should I continue to process this product? Consider:
            1. Does the current raw material support continued production?
            2. Is the expenditure incurred from purchasing raw materials acceptable to the company?
            3. Producing products and selling them is currently the only way for the company to generate income.

            Answer in JSON format, including four fields, Answer only YES or NO in field "willing_to_process", and provide the corresponding reason in field "reason"
                e.g. {{"willing_to_process" : "YES","reason" : "The reason for my transaction is..."}}""" 
        response = await self.llm.atext_request(
            [
                {
                    "role": "system",
                    "content": "You are helping deciding whether to continue processing this product.",
                },
                {"role": "user", "content": response_prompt},
            ],
            intelligence_level = intelligence_level
        )
        try:
            if not response or not response.strip():
                print(f"Empty or invalid response received: {repr(response)}")
                willing_to_process = None
            else:
                if response.startswith("```"):
                    lines = response.strip().splitlines()
                    if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
                        content_cleaned = "\n".join(lines[1:-1])
                    else:
                        content_cleaned = response
                else:
                    content_cleaned = response
                try:
                    parsed = json_repair.loads(content_cleaned)
                except json.JSONDecodeError as e:
                    get_logger().error(f"PayLoadError Failed to parse content as JSON: {response}. Error: {e}")
                willing_to_process = parsed.get("willing_to_process")
            content1=json.dumps(parsed)
            await self._agent.send_message_to_agent(
                fid,
                content1,
                "check_manufacturing_decison",
                "check_manufacturing_decison"
            )
            if willing_to_process == "YES" or willing_to_process == "Yes" or willing_to_process == "yes":
                return True
            else:
                return False
        except Exception as e:
            get_logger().error(f"Error parsing response: {repr(response)}, error: {e}")
            return False


    async def record_fund_history(self):
        fund = await self.memory.status.get("fund", 0)
        self.fund_history.append({
            "step_fund": fund,
            "step": self.step_count
        })
        
        # 只保留最近 20 条
        if len(self.fund_history) > 20:
            self.fund_history = self.fund_history[-20:]
        
        # 按 step 升序排序
        self.fund_history.sort(key=lambda x: x["step"])
    
    async def record_product_history(self):
        inventory_system = await self.memory.status.get("inventory_system") or {}
        products = inventory_system.get("products", {})
        if isinstance(products, dict):
            for product_id, product_info in products.items():
                if isinstance(product_info, dict):
                    product_name = product_info.get("product_name", "unknown")
                    quantity = product_info.get("quantity", 0)
                    self.product_stock_history.setdefault(product_name, []).append({
                        "step_quantity":quantity,
                        "step":self.step_count
                    })

        return


    async def forward(self):
        self.step_count += 1
        await self.record_fund_history()
        await self.record_product_history()
        # 确保必要的字段存在 - 修复：使用 get 方法检查
        production_cost_history = await self.memory.status.get("production_cost_history", None)
        if production_cost_history is None:
            await self.memory.status.update("production_cost_history", [])
        await self.memory.status.update("current_production_cost", [])
        current_production_cost = []
        financial_metrics = await self.memory.status.get("financial_metrics", None)
        if financial_metrics is None:
            await self.memory.status.update("financial_metrics", {
                'total_revenue': 0,
                'total_production_cost': 0,
                'total_material_cost': 0,
                'total_processing_cost': 0,
                'net_profit': 0
            })
        self.had_insuffcient = False
        if self.register:
            products = await self.memory.status.get("products")
            name = await self.memory.status.get("name")
            company_capacity = await self.memory.status.get("company_capacity")
            firm_id = await self.memory.status.get("id")
            # 修正：统一使用 inventory_system 作为主要数据源
            inventory_system = await self.memory.status.get("inventory_system") or {}
            products_dict = inventory_system.get("products", {})
            materials_dict = inventory_system.get("materials", {})
            

            # 根据生产速率持续制造
            make_count = 0
            for product in self.product_list:
                flag = False
                base_price = 0
                for product1 in products:
                    if product1["product_name"] == product["product_name"]:
                        product_info = product1
                        if product1["is_terminal_product"]:
                            flag = True
                        else:
                            base_price = product1["base_price"]
                if not flag and product_info:
                    flag = await self.check_manufacturing_decison(product_info,base_price,inventory_system)
                if flag:
                    product["state"] = 'making'
                    make_count += 1
                else:
                    product["state"] = 'stop'
            production = company_capacity
            if self.step_count>100 and firm_id == 5:
                company_capacity = company_capacity * 0.7
            if make_count != 0:
                production = company_capacity // make_count
            for product in products:
                target_entry = next((item for item in self.product_list if item['product_name'] == product["product_name"]),
                                    None)
                if not target_entry:
                    print(f"{product['product_name']} not found")
                    continue
                recipe_str = product["product_construct"]
                if recipe_str == "no need material":
                    # 直接更新 inventory_system 中的产品库存
                    product_name = product["product_name"]
                    product_id = str(product.get("product_id", product_name.split("_")[-1]))

                    if product_id in products_dict:
                        products_dict[product_id]["quantity"] = products_dict[product_id].get("quantity",
                                                                                              0) + production
                    else:
                        products_dict[product_id] = {
                            "product_name": product_name,
                            "quantity": production
                        }
                    produce_count = await self.memory.status.get("produce_count")
                    for count in produce_count:
                        if count["product_name"] == product_name:
                            count["count"] = production
                    await self.memory.status.update("produce_count",produce_count)
                    # 计算生产成本（无原料成本，只有加工费用）
                    processing_cost,processing_cost_per_unit = await self.get_processing_cost(product_name, production)
                    total_production_cost = processing_cost

                    # 从企业资金中扣除生产成本
                    current_fund = await self.memory.status.get("fund") or 0
                    new_fund = current_fund - total_production_cost
                    make_cost = await self.memory.status.get("make_cost",0)
                    make_cost = make_cost + total_production_cost
                    await self.memory.status.update("make_cost", make_cost)
                    await self.memory.status.update("fund", new_fund)

                    # 通过经济客户端同步资金变化
                    if total_production_cost > 0:
                        await self.environment.economy_client.delta_update_firms(
                            firm_id=firm_id,
                            delta_currency=-total_production_cost
                        )

                    # 记录生产成本历史
                    cost_details = {
                        'timestamp': time.time(),
                        'product': product_name,
                        'amount': production,
                        'material_cost': 0,
                        'processing_cost': processing_cost,
                        'total_cost': total_production_cost
                    }
                    production_cost_history.append(cost_details)
                    await self.memory.status.update("production_cost_history", production_cost_history)
                    cost_unit_details = {
                            'timestamp': time.time(),
                            'product': product_name,
                            'amount': production,
                            'material_cost': 0,
                            'total_cost': processing_cost_per_unit
                        }
                    current_production_cost.append(cost_unit_details)
                    await self.memory.status.update("current_production_cost", current_production_cost)
                    # 更新财务指标
                    await self.update_financial_metrics(cost_details)

                    # 为了兼容性，同时更新旧的数据结构
                    product["inventory"] = products_dict[product_id]["quantity"]
                else:
                    flag1 = False
                    for product1 in self.product_list:
                        if product1["product_name"] == product["product_name"]:
                            if product1["state"] == "making":
                                flag1 = True
                    if flag1:
                        material_enough = True
                        pattern = r'([\w_]+)\*(\d+(?:\.\d+)?)%'
                        matches = re.findall(pattern, recipe_str)
                        recipe = {name: float(percent) / 100 for name, percent in matches}
                        
                        need = await self.memory.status.get("current_need",[])
                        # 检查材料库存是否充足
                        for name, amount_per_product in recipe.items():
                            total_consumed = amount_per_product * production
                            # if product["is_terminal_product"]:
                            #     print("TESTEXP",firm_id,product)
                            #     if self.step_count>50:
                            #         total_consumed = total_consumed * 1.25
                            material_stock = 0
                            # 从 inventory_system 的 materials 中获取材料库存
                            for material_id, material_info in materials_dict.items():
                                if material_info.get("product_name") == name:
                                    material_stock = material_info.get("quantity", 0)
                                    break

                            has_taged = name in self.insufficient_list  # 修改：简化检查逻辑
                            if total_consumed > material_stock :
                                material_enough = False
                                if not has_taged:
                                    new_need = ["Inventory insufficient", name]
                                    if new_need not in need:
                                        need.append(new_need)
                                        self.insufficient_list[name] = self.step_count  # 修改：直接赋值
                                        self.had_insuffcient = True
                        await self.memory.status.update("current_need", need)
                        if material_enough:
                            # 计算实际生产成本
                            product_name = product["product_name"]
                            actual_material_cost, material_unit_cost = await self.calculate_actual_material_cost(product_name, production,recipe)
                            processing_cost,processing_cost_per_unit = await self.get_processing_cost(product_name, production)
                            total_production_cost = processing_cost + actual_material_cost
                            unit_total_production_cost = material_unit_cost + processing_cost_per_unit
                            # 从企业资金中扣除生产成本
                            current_fund = await self.memory.status.get("fund") or 0
                            # 不需要在此计算原料成本，这部分支出在购买时已经支付了 
                            new_fund = current_fund - processing_cost
                            await self.memory.status.update("fund", new_fund)
                            make_cost = await self.memory.status.get("make_cost",0)
                            make_cost = make_cost + processing_cost
                            await self.memory.status.update("make_cost", make_cost)
                            # 通过经济客户端同步资金变化
                            if total_production_cost > 0:
                                await self.environment.economy_client.delta_update_firms(
                                    firm_id=firm_id,
                                    delta_currency=-total_production_cost
                                )

                            # 记录生产成本历史
                            cost_details = {
                                'timestamp': time.time(),
                                'product': product_name,
                                'amount': production,
                                'material_cost': actual_material_cost,
                                'processing_cost': processing_cost,
                                'total_cost': total_production_cost
                            }
                            production_cost_history.append(cost_details)
                            await self.memory.status.update("production_cost_history", production_cost_history)
                            cost_unit_details = {
                                'timestamp': time.time(),
                                'product': product_name,
                                'amount': production,
                                'material_cost': material_unit_cost,
                                'total_cost': unit_total_production_cost
                            }
                            current_production_cost.append(cost_unit_details)
                            await self.memory.status.update("current_production_cost", current_production_cost)
                            # 更新财务指标
                            await self.update_financial_metrics(cost_details)

                            # 更新产品库存到 inventory_system
                            product_id = str(product.get("product_id", product_name.split("_")[-1]))

                            if product_id in products_dict:
                                products_dict[product_id]["quantity"] = products_dict[product_id].get("quantity",
                                                                                                    0) + production
                            else:
                                products_dict[product_id] = {
                                    "product_name": product_name,
                                    "quantity": production
                                }
                            produce_count = await self.memory.status.get("produce_count")
                            for count in produce_count:
                                if count["product_name"] == product_name:
                                    count["count"] = production
                            await self.memory.status.update("produce_count",produce_count)
                            # 消耗材料库存
                            for name, amount_per_product in recipe.items():
                                total_consumed = amount_per_product * production
                                for material_id, material_info in materials_dict.items():
                                    if material_info.get("product_name") == name:
                                        materials_dict[material_id]["quantity"] = material_info.get("quantity",
                                                                                                        0) - total_consumed
                                        break

                            # 为了兼容性，同时更新旧的数据结构
                            product["inventory"] = products_dict[product_id]["quantity"]

                # 更新 inventory_system
                inventory_system["products"] = products_dict
                inventory_system["materials"] = materials_dict
                await self.memory.status.update("inventory_system", inventory_system)
                
                # 为了兼容性，生成 product_stocks 格式的数据
                product_stocks = []
                for product_id, product_info in products_dict.items():
                    product_stocks.append({
                        "name": product_info.get("product_name", f"product_{product_id}"),
                        "stock": product_info.get("quantity", 0)
                    })

                await self.memory.status.update("products", products)
                await self.memory.status.update("product_stocks", product_stocks)
        else:
            self.register = True
            products = await self.memory.status.get("products")
            history_product_order = await self.memory.status.get("history_product_order")
            new_prodcut_order = []
            produce_count = []
            for product in products:
                self.product_list.append({
                    "product_name": product["product_name"],
                    "state": "making", 
                })
                new_prodcut_order.append({
                    "name":product["product_name"],
                    "history_order":[]
                })
                produce_count.append({
                    "product_name":product["product_name"],
                    "count":0
                })
            await self.memory.status.update("history_product_order",new_prodcut_order)
            await self.memory.status.update("produce_count",produce_count)
        await self.check_insufficient()  # 修改：添加 await
