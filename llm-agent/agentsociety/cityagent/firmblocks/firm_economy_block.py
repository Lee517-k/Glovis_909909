import json
import logging
import re
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

__all__ = ["FirmEconomyBlock"]


class FirmEconomyBlock(Block):

    def __init__(
            self,
            agent: Agent,
            llm: LLM,
            environment: Environment,
            memory: Memory,
    ):
        super().__init__(
            "FirmEconomyBlock", llm=llm, environment=environment, memory=memory
        )
        self._agent = agent
        self.time_clock = 0
        self.judge_clock = random.randint(2, 5)
        self.get_invitation = False
        self.invite_subsidy = 0.0
        self.accept_invitation = False
        self.government_id = -1
        self.company_partner = []
        self.partner_platform = []
        self.step_count = -1

    async def init_installment_system(self):
        """初始化分期付款系统"""
        installment_plans = await self.memory.status.get("installment_plans") or []
        if not installment_plans:
            await self.memory.status.update("installment_plans", [])

    async def make_joining_decision(self):
        intelligence_level = await self.memory.status.get("intelligence_level")
        response_prompt = f"""Based on:
        - My profile: {{
            "company_name": "{await self.memory.status.get("name") or ""}",
            "company_size": "{await self.memory.status.get("company_size") or ""}",
            "company_type": "{await self.memory.status.get("company_type") or ""}",
            "partner_list": "{await self.memory.status.get("company_partner")}",
        }}
        - I need to decide whether to join an assistance platform or trade independently.
        - My Self-inclusion tendencys: {await self.memory.status.get("p_join") or ""}
        - My previous earnings record: {await self.memory.status.get("payoff_list") or ""}
        - Does the government provide incentive subsidies? : {self.get_invitation}
        - Government subsidy per transaction : {self.invite_subsidy}
        - Basic income from executing transactions -- base_profit: {await self.memory.status.get("base_profit") or ""}
        - The cost of joining the platform -- trans_cost: {await self.memory.status.get("trans_cost") or ""}
        - The coordinated revenue coefficient of Joining the platform -- collab_coeff: {await self.memory.status.get("collab_coeff") or ""}
        - Calculation of earnings when not joining the platform :  payoff = length of company_partner * base_profit
        - Calculation of earnings when  joining the platform :  payoff = length of company_partner * base_profit * collab_coeff - trans_cost

        Should I join ? Consider:
        1. Will the returns be higher after joining the platform?
        2. Can you afford the costs of joining the platform?

        Answer only YES or NO, in JSON format, e.g. {{"should_join": "YES"}}"""
        should_respond = await self.llm.atext_request(
            dialog=[
                {
                    "role": "system",
                    "content": "You are helping decide whether to join the platform",
                },
                {"role": "user", "content": response_prompt},
            ],
            response_format={"type": "json_object"},
            intelligence_level = intelligence_level
        )
        should_respond = jsonc.loads(should_respond)["should_join"]
        if should_respond == "YES":
            await self.memory.status.update("has_join", True)
            if self.get_invitation:
                await self._agent.send_message_to_agent(
                    self.government_id,
                    "accept",
                    "economy",
                )
            for id in self.company_partner:
                # 告知合作伙伴平台化情况
                await self._agent.send_message_to_agent(
                    id,
                    "platform",
                    "economy",
                )
        else:
            await self.memory.status.update("has_join", False)

    async def process_message(self, payload: dict) -> str:
        self.get_invitation = True
        from_id = payload["from"]

        if from_id in self.company_partner or str(from_id) in self.company_partner:
            self.partner_platform.append(from_id)
        else:
            self.government_id = from_id
            received = payload.get("content")
            received_Info = json_repair.loads(received)
            self.invite_subsidy = received_Info["subsidy_cost"]
        return ""

    def safe_float(self, value):
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            match = re.search(r"[-+]?\d*\.?\d+", value)
            if match:
                return float(match.group())
        return 0.0

    def safe_int(self, val, default=0):
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def get_product_cost_info(self, product_name, products_list):
        """获取产品的成本信息"""
        for product in products_list:
            if product.get("product_name") == product_name:
                return {
                    "manufacturing_cost": product.get("manufacturing_cost", 0),
                    "material_cost": product.get("material_cost", 0),
                    "net_manufacturing_cost": product.get("net_manufacturing_cost", 0),
                    "base_price": product.get("base_price", 0)
                }
        return None

    def calculate_material_costs(self, product_construct, quantity, materials_dict):
        """计算实际原料成本"""
        if product_construct == "no need material":
            return 0

        pattern = r'([\w_]+)\*(\d+)%'
        matches = re.findall(pattern, product_construct)
        total_material_cost = 0

        for material_name, percent in matches:
            material_ratio = int(percent) / 100
            material_quantity = material_ratio * quantity

            # 查找材料的单价
            for material_id, material_info in materials_dict.items():
                if material_info.get("product_name") == material_name:
                    unit_cost = material_info.get("unit_cost", material_info.get("base_price", 0))
                    total_material_cost += unit_cost * material_quantity
                    break

        return total_material_cost

    async def forward(self):
        self.step_count += 1
        transaction_list = await self.memory.status.get("transaction_list",[])
        fid = await self.memory.status.get("id")
        fund = await self.memory.status.get("fund")
        products = await self.memory.status.get("products")
        Unfinished_order = await self.memory.status.get("Unfinished_order",[])
        inventory_system = await self.memory.status.get("inventory_system") or {}
        products_dict = inventory_system.get("products", {})
        step_profit = await self.memory.status.get("step_profit",0)
        if len(Unfinished_order) > 0:
            for order in Unfinished_order:
                if order["Undelivered_portion"] > 0:
                    p_name = order["product_name"]
                    try:
                        for product_id, product_info in products_dict.items():
                            if product_info["product_name"] == p_name:
                                if product_info["quantity"] >= order["Undelivered_portion"]:
                                    product_info["quantity"] = product_info["quantity"] - order["Undelivered_portion"]
                                    order["Undelivered_portion"] = 0
                                else:
                                    order["Undelivered_portion"] -= product_info["quantity"]
                                    product_info["quantity"] = 0
                    except Exception as e:
                        print("TESTUnfinished_orderError",e,"\n",products_dict,Unfinished_order)
            inventory_system["products"] = products_dict
            await self.memory.status.update("inventory_system",inventory_system)
            await self.memory.status.update("Unfinished_order",Unfinished_order)
        if len(transaction_list) > 0:
            # 获取产品信息用于成本计算
            products = await self.memory.status.get("products") or []

            for transaction in transaction_list:
                try:
                    if transaction["state"] != "done":
                        transaction["state"] = "in process"

                        # 修正：统一使用 inventory_system
                        
                        materials_dict = inventory_system.get("materials", {})

                        arg = 0
                        # 供应商视角
                        if fid == transaction["Supplier"]:
                            arg = 1
                        # 采购商视角
                        elif fid == transaction["Purchaser"]:
                            arg = -1

                        if transaction["payment_method"] == "full_payment" or transaction[
                            "payment_method"] == "one-time payment" or True:
                            # 从交易的产品名称中提取产品ID
                            transaction_product_name = transaction["product_name"]
                            transaction_product_id = transaction_product_name.split("_")[-1]

                            # 获取产品数量和单价
                            product_quantity = self.safe_float(transaction["product_quantity"])
                            unit_price = self.safe_float(transaction["Unit_price"])

                            # 获取产品成本信息
                            product_cost_info = self.get_product_cost_info(transaction_product_name, products)
                            # 供应商视角 - 计算详细的收入和成本
                            if arg == 1:  # 供应商
                                revenue = unit_price * product_quantity
                                fund = fund + revenue
                                step_profit = step_profit + revenue
                                if product_cost_info:
                                    # 计算实际原料成本
                                    product_info = next(
                                        (p for p in products if p.get("product_name") == transaction_product_name), None)
                                    if product_info:
                                        actual_material_cost = self.calculate_material_costs(
                                            product_info.get("product_construct", ""),
                                            product_quantity,
                                            materials_dict
                                        )
                                    else:
                                        actual_material_cost = product_cost_info["material_cost"] * product_quantity

                                    # 加工费用
                                    processing_cost = product_cost_info["net_manufacturing_cost"] * product_quantity
                                    total_production_cost = actual_material_cost + processing_cost

                                    # 净收入 = 销售收入 - 生产成本
                                    net_income = revenue - total_production_cost

                                    # 记录详细的交易成本信息
                                    transaction_details = {
                                        "transaction_type": "sale",
                                        "product_name": transaction_product_name,
                                        "quantity": product_quantity,
                                        "unit_price": unit_price,
                                        "revenue": revenue,
                                        "actual_material_cost": actual_material_cost,
                                        "processing_cost": processing_cost,
                                        "total_production_cost": total_production_cost,
                                        "net_income": net_income,
                                        "profit_margin": (net_income / revenue * 100) if revenue > 0 else 0
                                    }

                                    # 保存交易详情到历史记录
                                    transaction_history = await self.memory.status.get("transaction_cost_history") or []
                                    transaction_history.append(transaction_details)
                                    await self.memory.status.update("transaction_cost_history", transaction_history)
                                    order = {
                                        "product_quantity":product_quantity,
                                        "order_profit":revenue,
                                        "step":self.step_count
                                    }
                                    history_product_order = await self.memory.status.get("history_product_order")
                                    for product_order in history_product_order:
                                        if product_order["name"] == transaction_product_name:
                                            product_order["history_order"].append(order)
                                            product_order["history_order"] = product_order["history_order"][-20:]
                                    await self.memory.status.update("history_product_order",history_product_order)
                                    print(
                                        f"销售交易完成 - 产品: {transaction_product_name}, 净收入: {net_income:.2f}, 利润率: {transaction_details['profit_margin']:.2f}%")
                            # 在采购商视角的处理中添加unit_cost保存逻辑
                            elif arg == -1:  # 采购商
                                total_cost = unit_price * product_quantity
                                fund = fund - total_cost
                                step_profit = step_profit -total_cost
                                # 更新材料库存时同时保存unit_cost
                                if transaction_product_id in materials_dict:
                                    materials_dict[transaction_product_id]["quantity"] = materials_dict[
                                                                                        transaction_product_id].get(
                                    "quantity", 0) + product_quantity
                                    materials_dict[transaction_product_id]["unit_cost"] = unit_price  # 保存实际采购单价
                                else:
                                    materials_dict[transaction_product_id] = {
                                        "product_name": transaction_product_name,
                                        "quantity": product_quantity,
                                        "unit_cost": unit_price  # 保存实际采购单价
                                    }

                                # 记录采购详情
                                purchase_details = {
                                    "transaction_type": "purchase",
                                    "product_name": transaction_product_name,
                                    "quantity": product_quantity,
                                    "unit_price": unit_price,
                                    "total_cost": total_cost
                                }

                                # 保存采购详情到历史记录
                                transaction_history = await self.memory.status.get("transaction_cost_history") or []
                                transaction_history.append(purchase_details)
                                await self.memory.status.update("transaction_cost_history", transaction_history)
                            # 直接从 inventory_system 更新库存

                            if transaction_product_id in products_dict:
                                portion = int(round(product_quantity))
                                if arg == -1:
                                    products_dict[transaction_product_id]["quantity"] = products_dict[transaction_product_id].get("quantity", 0) + portion
                                else:
                                    stock = products_dict[transaction_product_id].get("quantity", 0)
                                    product_name = products_dict[transaction_product_id]["product_name"]
                                    if stock - portion < 0:
                                        products_dict[transaction_product_id]["quantity"] = 0
                                        flag = False
                                        Outstanding = portion - products_dict[transaction_product_id].get("quantity", 0)
                                        for order in Unfinished_order:
                                            if order["product_name"] == product_name:
                                                order["Undelivered_portion"] += Outstanding
                                                flag = True
                                        if not flag:
                                            Unfinished_order.append({"product_name":product_name,"Undelivered_portion":Outstanding})
                                    elif stock - portion >= 0:
                                        products_dict[transaction_product_id]["quantity"] -= portion
                                    await self.memory.status.update("Unfinished_order",Unfinished_order)

                            # 保存更新后的数据
                            inventory_system["products"] = products_dict
                            await self.memory.status.update("inventory_system", inventory_system)
                            await self.memory.status.update("fund", fund)
        
                            # 为了兼容性，同时更新 product_stocks
                            product_stocks = []
                            for product_id, product_info in products_dict.items():
                                product_stocks.append({
                                    "name": product_info.get("product_name", f"product_{product_id}"),
                                    "stock": product_info.get("quantity", 0)
                                })
                            await self.memory.status.update("product_stocks", product_stocks)
                            transaction["state"] = "done"

                        elif transaction["payment_method"] == "installment":
                            product_quantity = self.safe_float(transaction["product_quantity"])
                            product_quantity = int(int(product_quantity) / 3)

                            # 从交易的产品名称中提取产品ID
                            transaction_product_name = transaction["product_name"]
                            transaction_product_id = transaction_product_name.split("_")[-1]

                            # 直接从 inventory_system 更新库存
                            if transaction_product_id in products_dict:
                                products_dict[transaction_product_id]["quantity"] = max(0,
                                                                                        products_dict[
                                                                                            transaction_product_id].get(
                                                                                            "quantity", 0) - int(
                                                                                            int(product_quantity) * arg))

                            fund = fund + (self.safe_float(transaction["Unit_price"]) * float(product_quantity) * arg)
                            step_profit = step_profit + (self.safe_float(transaction["Unit_price"]) * float(product_quantity) * arg)
                            # 保存更新后的数据
                            inventory_system["products"] = products_dict
                            await self.memory.status.update("inventory_system", inventory_system)
                            await self.memory.status.update("fund", fund)

                            # 为了兼容性，同时更新 product_stocks
                            product_stocks = []
                            for product_id, product_info in products_dict.items():
                                product_stocks.append({
                                    "name": product_info.get("product_name", f"product_{product_id}"),
                                    "stock": product_info.get("quantity", 0)
                                })
                            await self.memory.status.update("product_stocks", product_stocks)

                            transaction["state"] = transaction["state"] + "1"
                            if transaction["state"] == "in process111":
                                transaction["state"] = "done"
                            print("TESTinstallment",transaction,transaction["state"])
                except Exception as e:
                    print("TESTtransaction_list1",type(transaction),transaction,"\n error:",e)
            await self.memory.status.update("transaction_list", transaction_list)

            # 计算和更新财务统计信息
            await self.update_financial_metrics()
        # 作为产业链末端，加入自行消耗产品的逻辑
        Position_cost = 0
        for product in products:
            is_terminal_product = product.get("is_terminal_product", False)
            products_dict = inventory_system.get("products", {})
            product_id = product.get("product_id",0)
            pid = str(product_id)
            base_price = product.get("base_price",0)
            if is_terminal_product:
                consumption_rate = product.get("consumption_rate", {})
                sell_price = product.get("sell_price",0)
                daily_consumption_rate = consumption_rate.get("daily_consumption_rate",0)
                
                if pid in products_dict:
                    consumption_rate = int(daily_consumption_rate * random.uniform(0.85, 1.15))
                    products_dict[pid]["quantity"] = max(0,products_dict[pid].get("quantity", 0) - consumption_rate)
                    if sell_price == -1:
                        sell_price = base_price
                    quantity = 0.0
                    if products_dict[pid]["quantity"] > 0:
                        quantity = products_dict[pid]["quantity"]
                    profit = self.safe_float(sell_price) * quantity
                    fund = fund + profit

                    history_product_order = await self.memory.status.get("history_product_order")
                    for product_order in history_product_order:
                        if product_order["name"] == product.get("product_name",""):
                            product_order["history_order"].append({
                                    "product_quantity":quantity,
                                    "order_profit":profit,
                                    "step":self.step_count
                                })
                            product_order["history_order"] = product_order["history_order"][-20:]
                    await self.memory.status.update("history_product_order",history_product_order)

                        # 保存更新后的数据
                    inventory_system["products"] = products_dict
                    await self.memory.status.update("inventory_system", inventory_system)
                    # 为了兼容性，同时更新 product_stocks
                    product_stocks = []
                    for pid, product_info in products_dict.items():
                        product_stocks.append({
                            "name": product_info.get("product_name", f"product_{pid}"),
                            "stock": product_info.get("quantity", 0)
                        })
                    await self.memory.status.update("product_stocks", product_stocks)
            constrain_inventory = products_dict[pid].get("quantity", 0)
            Position_cost = Position_cost + constrain_inventory * base_price * 0.0005   
                # 减去持仓成本
            fund = fund - Position_cost
        await self.memory.status.update("fund",fund)
        await self.memory.status.update("step_profit",step_profit)
        await self.memory.status.update("Position_cost",Position_cost)
                

    async def update_financial_metrics(self):
        """更新财务指标"""
        transaction_history = await self.memory.status.get("transaction_cost_history") or []

        if transaction_history:
            # 计算总收入、总支出、总利润
            total_revenue = sum(t.get("revenue", 0) for t in transaction_history if t.get("transaction_type") == "sale")
            total_expenses = sum(
                t.get("total_cost", 0) for t in transaction_history if t.get("transaction_type") == "purchase")
            total_production_cost = sum(
                t.get("total_production_cost", 0) for t in transaction_history if t.get("transaction_type") == "sale")
            total_profit = sum(
                t.get("net_income", 0) for t in transaction_history if t.get("transaction_type") == "sale")

            # 计算平均利润率
            sales_transactions = [t for t in transaction_history if
                                  t.get("transaction_type") == "sale" and t.get("revenue", 0) > 0]
            avg_profit_margin = sum(t.get("profit_margin", 0) for t in sales_transactions) / len(
                sales_transactions) if sales_transactions else 0

            financial_metrics = {
                "total_revenue": total_revenue,
                "total_expenses": total_expenses,
                "total_production_cost": total_production_cost,
                "total_profit": total_profit,
                "avg_profit_margin": avg_profit_margin,
                "transaction_count": len(transaction_history)
            }

            await self.memory.status.update("financial_metrics", financial_metrics)

    async def check_installment_payments(self):
        """检查所有分期付款计划"""
        installment_plans = await self.memory.status.get("installment_plans") or []

        for plan in installment_plans:
            if plan["current_installment"] < plan["installments"]:
                time_since_start = self.time_clock - plan["start_time"]
                expected_installment = min(time_since_start // plan["payment_interval"] + 1, plan["installments"])

                if expected_installment > plan["current_installment"]:
                    print(f"提醒: 交易 {plan['transaction_id']} 有待处理的分期付款")

    def calculate_installment_payment(self, principal, periods, annual_rate):
        """计算分期付款金额（等额本息）"""
        if annual_rate == 0:
            return principal / periods

        monthly_rate = annual_rate / 12
        payment = principal * (monthly_rate * (1 + monthly_rate) ** periods) / ((1 + monthly_rate) ** periods - 1)
        return round(payment, 2)

    def generate_payment_schedule(self, principal, periods, annual_rate):
        """生成分期付款时间表"""
        monthly_payment = self.calculate_installment_payment(principal, periods, annual_rate)
        monthly_rate = annual_rate / 12

        schedule = []
        remaining_balance = principal

        for period in range(1, periods + 1):
            interest_payment = remaining_balance * monthly_rate
            principal_payment = monthly_payment - interest_payment
            remaining_balance -= principal_payment

            schedule.append({
                "period": period,
                "payment_amount": monthly_payment,
                "principal_payment": round(principal_payment, 2),
                "interest_payment": round(interest_payment, 2),
                "remaining_balance": round(max(0, remaining_balance), 2)
            })

        return schedule

