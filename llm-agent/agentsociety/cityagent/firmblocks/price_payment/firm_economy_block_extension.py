import json
import logging

import jsonc

from agentsociety.agent.agent_base import Agent
from ....environment import Environment
from ....llm import LLM
from ....logger import get_logger
from ....memory import Memory
from ....agent import Block, FormatPrompt
from .price_decision_prompt import PRICE_DECISION_PROMPT, PAYMENT_METHOD_PROMPT

__all__ = ["FirmEconomyBlockExtension"]


class FirmEconomyBlockExtension(Block):
    """
    Extend the Enterprise Economics module to add product price decisions and payment method decisions
    """

    def __init__(
            self,
            agent: Agent,
            llm: LLM,
            environment: Environment,
            memory: Memory,
    ):
        super().__init__(
            "FirmEconomyBlockExtension", llm=llm, environment=environment, memory=memory
        )
        self._agent = agent
        self.price_prompt = FormatPrompt(template=PRICE_DECISION_PROMPT)
        self.payment_prompt = FormatPrompt(template=PAYMENT_METHOD_PROMPT)


    async def decide_product_price(self, product_name: str,market_price: str,step_count):
        """
        Decide on the price of the product

        Args:
            product_name: Product name

        Returns:
            dict: A dictionary with prices and justifications for decisions
        """
        # 获取企业信息
        company_name = await self.memory.status.get("name") or ""

        # 获取产品信息
        products = await self.memory.status.get("products") or []
        product_info = next((p for p in products if p.get("product_name") == product_name), {})
        # product_description = product_info.get("description", "")
        product_cost = product_info.get("manufacturing_cost", 0)

        # 获取市场信息
        # market_demand_trend = product_info.get("market_demand_trend", "stable")

        # 获取企业状况
        current_fund = await self.memory.status.get("fund") or 0
        current_stock = product_info.get("inventory", 0)
        base_price = product_info.get("base_price", 0)
        # production_capacity = await self.memory.status.get("company_capacity") or 0
        # 格式化prompt
        if step_count >= 100:
            base_price = base_price * 0.75
        current_production_cost = await self.memory.status.get("current_production_cost")
        total_cost = 0
        material_cost = 0
        for cost in current_production_cost:
            if cost["product"] == product_name:
                total_cost = cost["total_cost"]
                material_cost = cost["material_cost"]

        formatted_prompt = self.price_prompt.format(
            company_name=company_name,
            product_name=product_name,
            product_cost=product_cost,
            total_cost=total_cost,
            material_cost=material_cost,
            market_price=market_price,
            # market_demand_trend=market_demand_trend,
            current_fund=current_fund,
            current_stock=current_stock,
            base_price=base_price,
            # production_capacity=production_capacity``
        )
        # 调用LLM获取决策
        response = await self.llm.atext_request(
            dialog=[
                {
                    "role": "system",
                    "content": "You are a corporate product price decision-making system, setting a reasonable price for the product according to the enterprise and market conditions."
                },
                {"role": "user", "content": formatted_prompt}
            ],
            response_format={"type": "json_object"}
        )
        # 解析响应
        try:
            result = jsonc.loads(response)
            # 更新产品价格到内存
            for p in products:
                if p.get("product_name") == product_name:
                    p["sell_price"] = result["price"]
                    if company_name == "A1" or company_name == "A2" or company_name == "A3":
                        if step_count > 100:
                            print("TESTUPDATESELL",company_name)
                            p["sell_price"] = p["sell_price"] * 1.15
                    print("sell_pricesell_price",step_count,company_name,p)
            await self.memory.status.update("products", products)
            return result
        except Exception as e:
            get_logger().error(f"Error parsing price decision response: {e}")
            return {"price": product_cost * 1.2, "reasoning": "默认定价：成本加20%利润"}

    async def decide_payment_method(self, transaction_type: str, transaction_amount: float, transaction_partner: str):
        """
        Decide on a payment method

        Args:
            transaction_type: Transaction type,"purchase"(Buying someone else's product) 或 "sale"(Sell your own products)
            transaction_amount: Transaction amount
            transaction_partner: Transaction partner ID or name

        Returns:
            dict: A dictionary with payment methods and justifications for decisions
        """
        # 获取企业信息
        company_name = await self.memory.status.get("name") or ""

        # 获取企业状况
        current_fund = await self.memory.status.get("fund") or 0

        # 修正：从 inventory_system 获取库存数据
        inventory_system = await self.memory.status.get("inventory_system") or {}
        products_dict = inventory_system.get("products", {})

        # 计算总库存
        total_stock = sum(product_info.get("quantity", 0) for product_info in products_dict.values())

        sell_price = sum(p.get("sell_price", 0) for p in await self.memory.status.get("products") or [])

        # 计算资金流动性（简化计算，实际可能更复杂）
        current_fund = float(current_fund)
        if transaction_amount is None or transaction_amount == "":
            transaction_amount = 0.0
        if isinstance(transaction_amount,str):
            try:
                transaction_amount = float(transaction_amount.strip())
            except ValueError:
                transaction_amount = 0.0
        elif isinstance(transaction_amount,(int,float)):
            transaction_amount = float(transaction_amount)
        else:
            transaction_amount = 0.0
        fund_liquidity = "high" if current_fund > transaction_amount * 3 else "medium" if current_fund > transaction_amount else "low"

        # 获取历史交易记录（简化，实际可能需要从memory中获取更详细的记录）
        # transaction_history = await self.memory.status.get("transaction_history") or []
        # partner_transactions = [t for t in transaction_history if t.get("partner") == transaction_partner]

        # 格式化prompt
        formatted_prompt = self.payment_prompt.format(
            company_name=company_name,
            current_fund=current_fund,
            current_stock=total_stock,
            sell_price=sell_price,
            fund_liquidity=fund_liquidity,
            transaction_type=transaction_type,
            transaction_amount=transaction_amount,
            transaction_partner=transaction_partner,
            # transaction_history=partner_transactions
        )

        # 调用LLM获取决策
        response = await self.llm.atext_request(
            dialog=[
                {
                    "role": "system",
                    "content": "You are a corporate payment method decision-making system, based on the enterprise's situation and transaction details, decide the appropriate payment method."
                },
                {"role": "user", "content": formatted_prompt}
            ],
            response_format={"type": "json_object"}
        )

        # 解析响应
        try:
            result = jsonc.loads(response)
            # 可以在这里添加将决策结果保存到内存的代码
            return result
        except Exception as e:
            get_logger().error(f"Error parsing payment method decision response: {e}")
            # 默认返回一次性付款，30天内
            return {
                "payment_method": "full_payment",
                "details": {"payment_days": 30},
                "reasoning": "Default payment method: Pay after 30 days of delivery"
            }