import asyncio
import json

# 导入必要的模块
from agentsociety.agent.agent_base import Agent
from agentsociety.environment import Environment
from agentsociety.llm import LLM
from agentsociety.memory import Memory
from agentsociety.cityagent.firmblocks.firm_economy_block_extension import FirmEconomyBlockExtension


async def example_usage():
    """
    使用产品价格决策和付款方式决策功能的示例
    这只是一个示例，实际使用时需要根据项目结构进行适当调整
    """
    # 假设我们已经有了agent, llm, environment和memory的实例
    # 在实际使用中，这些应该是从现有系统中获取的
    agent = None  # 实际使用时替换为真实的Agent实例
    llm = None    # 实际使用时替换为真实的LLM实例
    environment = None  # 实际使用时替换为真实的Environment实例
    memory = None  # 实际使用时替换为真实的Memory实例
    
    # 创建FirmEconomyBlockExtension实例
    economy_extension = FirmEconomyBlockExtension(
        agent=agent,
        llm=llm,
        environment=environment,
        memory=memory
    )
    
    # 示例1：决定产品价格
    product_name = "智能手机"
    price_decision = await economy_extension.decide_product_price(product_name)
    print(f"产品 '{product_name}' 的价格决策:")
    print(json.dumps(price_decision, ensure_ascii=False, indent=2))
    
    # 示例2：决定购买付款方式
    transaction_type = "purchase"  # 购买他人产品
    transaction_amount = 50000.0
    transaction_partner = "供应商A"
    payment_decision = await economy_extension.decide_payment_method(
        transaction_type, transaction_amount, transaction_partner
    )
    print(f"购买交易的付款方式决策:")
    print(json.dumps(payment_decision, ensure_ascii=False, indent=2))
    
    # 示例3：决定销售付款方式
    transaction_type = "sale"  # 销售自己产品
    transaction_amount = 30000.0
    transaction_partner = "客户B"
    payment_decision = await economy_extension.decide_payment_method(
        transaction_type, transaction_amount, transaction_partner
    )
    print(f"销售交易的付款方式决策:")
    print(json.dumps(payment_decision, ensure_ascii=False, indent=2))


# 如何在现有的FirmAgent中集成这些新功能（AI跑的）
"""
在现有的FirmAgent类中，可以按照以下方式集成这些新功能：

1. 在FirmAgent的__init__方法中初始化FirmEconomyBlockExtension：

self.economy_extension = FirmEconomyBlockExtension(
    agent=self,
    llm=self.llm,
    environment=self.environment,
    memory=self.memory
)

2. 在需要决定产品价格的地方调用decide_product_price方法：

async def update_product_price(self, product_name):
    price_decision = await self.economy_extension.decide_product_price(product_name)
    # 可以在这里处理价格决策结果
    return price_decision

3. 在需要决定付款方式的地方调用decide_payment_method方法：

async def determine_payment_method(self, transaction_type, amount, partner):
    payment_decision = await self.economy_extension.decide_payment_method(
        transaction_type, amount, partner
    )
    # 可以在这里处理付款方式决策结果
    return payment_decision
"""


# 如果直接运行此文件，执行示例
if __name__ == "__main__":
    asyncio.run(example_usage())