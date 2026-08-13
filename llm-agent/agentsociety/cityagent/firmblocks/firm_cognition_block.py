from curses import has_key
import logging

import jsonc
import random
from ...environment import Environment
from ...llm import LLM
from ...logger import get_logger
from ...memory import Memory
from ...agent import Block, FormatPrompt

__all__ = ["FirmCognitionBlock"]


def extract_json(output_str):
    try:
        start = output_str.find("{")
        end = output_str.rfind("}")
        json_str = output_str[start : end + 1]
        return json_str
    except (ValueError, jsonc.JSONDecodeError) as e:
        get_logger().warning(f"Failed to extract JSON: {e}")
        return None


class FirmCognitionBlock(Block):
    # status / profile contorller
    configurable_fields = ["top_k"]
    default_values = {"top_k": 20}
    fields_description = {
        "top_k": "Number of most relevant memories to return, defaults to 20"
    }

    def __init__(self, llm: LLM, environment: Environment, memory: Memory):
        super().__init__(
            "FirmCognitionBlock", llm=llm, environment=environment, memory=memory
        )
        self.top_k = 20
        self.last_check_day = 0
        self.register = False 

    async def set_status(self, status):
        """Update multiple status fields in memory.

        Args:
            status: Dictionary of key-value pairs to update.
        """
        for key in status:
            await self.memory.status.update(key, status[key])
        return

    async def update_stock(self):
        # 静态
        name =await self.memory.status.get("name")
        company_name = await self.memory.status.get("company_name")
        registered_capital = await self.memory.status.get("registered_capital")
        main_product = await self.memory.status.get("main_products")
        culture = await self.memory.status.get("culture")
        ownership_type = await self.memory.status.get("ownership_type")
        stock_status = await self.memory.status.get("stock_status")
        founded_year = await self.memory.status.get("founded_year")
        # 动态
        product_inventory = await self.memory.status.get("product_inventory")
        revenue = await self.memory.status.get("revenue")
        profit = await self.memory.status.get("profit")
        clients = await self.memory.status.get("clients")
        fund = await self.memory.status.get("fund")
        partners = await self.memory.status.get("partners")

        company_size = await self.memory.status.get("company_size")
        company_type = await self.memory.status.get("company_type")
        base_profit=await self.memory.status.get("base_profit")
        p_join=await self.memory.status.get("p_join")
        trans_cost=await self.memory.status.get("trans_cost")
        collab_coeff=await self.memory.status.get("collab_coeff")


    async def forward(self):
        if self.register:
            # await self.update_stock()
            # 
            pass
        else:
            # 初次注册的企业先对自身属性作处理
            main_product = await self.memory.status.get("main_products")
            product_list = []
            related_product_list = []
            for product in main_product:
                product_list.append(product["product_name"])
                related_product_list.append(product["related_products"])
            await self.memory.status.update("main_products",product_list)
            await self.memory.status.update("relative_products",related_product_list)
            inventory = {}
            for product in product_list:
                inventory[product] = random.randint(5000, 80000) 
            for list in related_product_list:
                for product in list:
                    if not product in inventory.keys():
                        inventory[product] = random.randint(5000, 80000) 
            await self.memory.status.update("product_inventory",inventory)

            # 属性补充 
            company_size = await self.memory.status.get("company_size")
            attribute_size_map = {
                "small":  {"base_profit": 50, "p_joinR": 0.8},
                "middle": {"base_profit": 70, "p_joinR": 0.5},
                "large":  {"base_profit": 100, "p_joinR": 0.4},
            }
            attributes1 = attribute_size_map[company_size]
            base_profit = attributes1["base_profit"]
            p_joinR = attributes1["p_joinR"]
            p_join = random.uniform(0.2, p_joinR)
            company_type = await self.memory.status.get("company_type")
            attribute_type_map = {
                "manufacture":  {"trans_cost": 20, "collab_coeff": 1.5},
                "supply":  {"trans_cost": 15, "collab_coeff": 0.5},
            }
            attributes2 = attribute_type_map[company_type]
            trans_cost = attributes2["trans_cost"]
            collab_coeff = attributes2["collab_coeff"]

            await self.memory.status.update("base_profit",base_profit)
            await self.memory.status.update("p_join",p_join)
            await self.memory.status.update("trans_cost",trans_cost)
            await self.memory.status.update("collab_coeff",collab_coeff)
            self.register = True

            
            
      

