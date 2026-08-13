import asyncio
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

__all__ = ["CollaborationBlock"]


class CollaborationBlock(Block):
    """
    记录并交流有依赖关系的企业
    """
    configurable_fields = [
        "firm_id_list",
        "firm_product_list"
    ]
    default_values = {
        "firm_id_list": [],
        "firm_product_list": []
    }
    fields_description = {
        "firm_id_list": "relative firms` id",
        "firm_product_list": "relative firms` products"
    }

    def __init__(
            self,
            agent: Agent,
            llm: LLM,
            environment: Environment,
            memory: Memory,
            update_payment_method,
    ):
        super().__init__(
            "CollaborationBlock", llm=llm, environment=environment, memory=memory
        )
        self._agent = agent
        self.firm_id_list = []
        self.firm_product_list = []
        self.id = -1
        self.judge = False
        self.potential_partner = []
        self.send_list = []
        self.partner = []
        self.update_payment_method = update_payment_method
        self.orderCount = 0
        self.step_count = -1
        self.need_record = []
        self.received_requests = []
        self._lock = asyncio.Lock()

    async def process_message(self, payload: dict) -> str:
        payload_type = payload.get("type")
        payload_topic = payload.get("topic")
        fid = await self.memory.status.get("id")
        if payload_type == "operation-price":
            content = payload.get("content")
            if not content:
                get_logger().error(f"PayLoadError Empty content in payload: {payload}")
                return
            if content.startswith("```"):
                lines = content.strip().splitlines()
                if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
                    content_cleaned = "\n".join(lines[1:-1])
                else:
                    content_cleaned = content
            else:
                content_cleaned = content
            try:
                parsed = json_repair.loads(content_cleaned)
            except json.JSONDecodeError as e:
                get_logger().error(f"PayLoadError Failed to parse content as JSON: {content}. Error: {e}")
                return
            self.received_requests.append({
                "requesting_company_id": payload.get("from"),
                "expected_products": parsed["expected_products"],
                "expected_quantity": parsed["expected_quantity"],
                "detailed_inquiry_text": parsed["detailed_inquiry_text"],
                "topic" : payload_topic,
            })
            plan = []
            current_plan = await self.memory.status.get("current_plan")
            for c_p in current_plan:
                plan.append(c_p)
            new_frag = ["Product Asking", parsed["expected_products"]]
            seen = {tuple(p) for p in current_plan}
            if tuple(new_frag) not in seen:        
                plan.append(new_frag)
            await self.memory.status.update("current_plan", plan)
        elif payload_type == "operation-deal":
            await self.decide_transaction_order(payload)
        elif payload_type == "operation-reject":
            # TODO 存储失败原因并作为后续依据
            pass
        elif payload_type == "operation-build":
            content = payload.get("content")
            transaction_order = json_repair.loads(content)
            await self.build_transaction(transaction_order)
        pass

    async def decide_transaction_order(self, payload):
        content = payload.get("content")
        payload_topic = payload.get("topic")
        transaction_order = json_repair.loads(content)
        intelligence_level = await self.memory.status.get("intelligence_level")
        intelligence_level = await self.memory.status.get("intelligence_level")
        # 修正：从 inventory_system 获取库存数据
        inventory_system = await self.memory.status.get("inventory_system") or {}
        products_dict = inventory_system.get("products", {})

        # 构建产品库存信息用于显示
        product_stocks_info = []
        for product_id, product_info in products_dict.items():
            product_stocks_info.append({
                "name": product_info.get("product_name", f"product_{product_id}"),
                "stock": product_info.get("quantity", 0)
            })

        response_prompt = f"""Based on:
            - My profile: {{
                "company_name": "{await self.memory.status.get("name") or ""}",
                "company_products": "{await self.memory.status.get("products") or ""}",
                "company_fund": "{await self.memory.status.get("fund") or ""}",
                "product_stocks": "{product_stocks_info}",
            }}
            - This is the response I received to the cooperation request I sent earlier, which is the cooperation order provided by the other party : {transaction_order}
            - I don't need to consider the 'reason' field of the above content.
            - In the information above, the attribute "product_name" means the name of the product you can get, "Unit_price" means the unit price you need to pay for the product, and "product_quantity" means the total quantity of the product you can obtain.
            - I need to consider whether to accept this purchase order.
            - I need to consider whether the unit price of the products given in the order and the payment method are reasonable.

            Should I accept? Consider:
            1. Can my current fund support fulfilling this transaction ?

             Answer in JSON format, including four fields, Answer only YES or NO in field "willing_to_transaction", and provide the corresponding reason in field "reason"
                e.g. {{"willing_to_transaction" : "YES","reason" : "The reason for my transaction is..."}}"""
        response = await self.llm.atext_request(
            [
                {
                    "role": "system",
                    "content": "You are helping choosing one from the list of customers received",
                },
                {"role": "user", "content": response_prompt},
            ],
            intelligence_level = intelligence_level
        )
        try:
            if not response or not response.strip():
                print(f"Empty or invalid response received: {repr(response)}")
                willing_to_transaction = None
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
                    get_logger().error(f"PayLoadError Failed to parse content as JSON: {content}. Error: {e}")
                willing_to_transaction = parsed.get("willing_to_transaction")
            if willing_to_transaction == "YES" or willing_to_transaction == "Yes" or willing_to_transaction == "yes":
                await self.build_transaction(transaction_order)
                try:
                    content_dict = json_repair.loads(content)
                    content_dict["reason"] = parsed.get("reason")
                    content = json.dumps(content_dict, ensure_ascii=False)
                except Exception as e:
                    get_logger().error(f"Failed to replace reason in content: {e}")
                await self._agent.send_message_to_agent(
                    payload.get("from"),
                    content,
                    "operation-build",
                    payload_topic
                )
                productName = transaction_order.get("product_name")
                self.need_record = [item for item in self.need_record if item.get("product") != productName]
            else:
                await self._agent.send_message_to_agent(
                    payload.get("from"),
                    parsed.get("reason"),
                    "operation-reject",
                    payload_topic
                )
                fid = self.memory.status.get("id")
        except Exception as e:
            get_logger().error(f"Error parsing response: {repr(response)}, error: {e}")
            willing_to_transaction = None

    async def build_transaction(self, transaction_order):
        async with self._lock:  # 确保并发安全
            transaction_list = await self.memory.status.get("transaction_list", [])
            transaction_list_new = list(transaction_list)
            transaction_list_new.append(transaction_order)
            await self.memory.status.update("transaction_list", transaction_list_new)

    async def select_partner_new(self, target_product):
        state = await self.environment.economy_client.get(id=-1, key="global_company_status")
        for company in state:
            product_list = company["product_list"]
            has_taged = any(item.get('company_id') == company['company_id'] for item in self.potential_partner)
            if has_taged:
                continue
            for product in product_list:
                if product["product_name"] == target_product:
                    self.potential_partner.append({
                        "company_id": company["company_id"],
                        "company_name": company["company_name"],
                        "company_product": product
                    })

    async def sending_price_check(self, target_product, current_quantity):
        fid = await self.memory.status.get("id")
        intelligence_level = await self.memory.status.get("intelligence_level")
        step_in = next(
            (item["step"] for item in self.need_record if item.get("product") == target_product),
            self.step_count
        )
        step_diff = self.step_count - step_in
        state = await self.environment.economy_client.get(id=-1, key="global_company_status")
        for potential_company in self.potential_partner:
            company_id = potential_company["company_id"]
            company_name = potential_company["company_name"]

            market_price = 0
            base_price = 0
            for company in state:
                product_list = company["product_list"]
                if company["company_id"] == company_id:
                    for product in product_list:
                        if product["product_name"] == target_product:
                            if product["sell_price"] != -1:
                                market_price += product["sell_price"]
                            elif product["base_price"] != 0:
                                base_price += product["base_price"]

            response_prompt = f"""Based on:
                - My profile: {{
                    "company_name": "{await self.memory.status.get("name") or ""}",
                    "company_products": "{await self.memory.status.get("products") or ""}",
                    "company_fund": "{await self.memory.status.get("fund") or ""}"
                }}
                - I would like to establish a business relationship with the target company and request a quotation for their products.
                - The company name I would like to communication : {company_name}
                - The products I am interested in purchasing : {target_product}
                - The current quantity of this product I still have in stock : {current_quantity}
                - The average price of this product on the market : {market_price}
                - The average cost price of this product on the market : {base_price}
                - If the price is 0, it means that it is a product that has not yet flowed out, ignoring its price reference
                - The company's funds, inventory situation, and the prices of target products will serve as the basis for your analysis, but this information cannot be disclosed to external companies.
                - It is important to note that it takes steps to procure and obtain materials.

                Which one should I consider? Consider:
                1. How many units should I consider purchasing ?
                2. How much amount I am willing to invest in this transaction, don`t too much ? 
                3. Ask the other party at what price their company is willing to sell.

                Answer in JSON format, including four fields:"expected_products","expected_quantity","detailed_inquiry_text", 
                When you consider the "expected_quantity" value, analyze it in combination with the value of the {step_diff}, which indicates the compactness of the product demand, the higher the value, the more urgent, and the less expected_quantity quantity should be required.
                The content of the third field should be combined with the above content to generate appropriate business communication language.
                e.g. {{"expected_products" : "{target_product}","expected_quantity": "50" ,  "detailed_inquiry_text" : "I am interested in establishing a business relationship with your company......"}}"""
            response = await self.llm.atext_request(
                [
                    {
                        "role": "system",
                        "content": "You are helping generate a product inquiry message addressed to potential partners.",
                    },
                    {"role": "user", "content": response_prompt},
                ],
                intelligence_level = intelligence_level,
            )
            try:
                await self._agent.send_message_to_agent(
                    company_id,
                    response,
                    "operation-price",
                    f"operation-{fid}-{self.orderCount}"
                )
                self.orderCount += 1
            except Exception as e:
                get_logger().error(f"Error happen: {e}")

        return

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

    async def handle_product_request(self, received_requests):
        fid = await self.memory.status.get("id")
        # 修正：从 inventory_system 获取库存数据
        inventory_system = await self.memory.status.get("inventory_system") or {}
        products_dict = inventory_system.get("products", {})
        intelligence_level = await self.memory.status.get("intelligence_level")
        # 构建统一的库存数据格式
        stocks = []
        company_map = []
        # 添加产品库存
        for product_id, product_info in products_dict.items():
            stocks.append({
                "name": product_info.get("product_name", f"product_{product_id}"),
                "stock": product_info.get("quantity", 0)
            })

        newStocks = self.add_material_from_product(stocks)
        received_length = len(received_requests)
        
        except_prompt = f"""
            I received  purchase requests with a total of {received_length}.
            Below are the details of each request.
        """
        for requests in received_requests:
            except_prompt = except_prompt + f"""
                The company ID that sent me the request: {requests["requesting_company_id"]}
                The name of the product that the client wants to purchase from me: {requests["expected_products"]},
                The selling price of this product: {requests["sell_price"]}
                The quantity of products that the client wants to purchase from me: {requests["expected_quantity"]},
                The detailed inquiry text sent to me by the client: \n{requests["detailed_inquiry_text"]} \n
                ---------------------------------------------------------------------------------------------
            """

        response_prompt = f"""Based on:
            - My profile: {{
                "company_name": "{await self.memory.status.get("name") or ""}",
                "company_products": "{await self.memory.status.get("products") or ""}",
                "company_fund": "{await self.memory.status.get("fund") or ""}",
                "product_stocks": "{newStocks}",
                "available_materials": "{await self.memory.status.get("available_materials") or ""}",
            }}
            - I need to handle a series transaction requests from the received requests.
            - This available_materials is the product content you can offer to the outside.
            - {except_prompt}
            - The received purchase request information has been displayed.
            - The following shows the outstanding payments for the company’s products. If the list is empty or the corresponding product’s Undelivered_portion value is 0, it indicates that there are no unfinished orders. Otherwise, it means the inventory of the corresponding product is depleted, and careful consideration is needed before accepting new orders : {await self.memory.status.get("Unfinished_order",[])}
            - These are the recent product sales order situations, including the quantity and revenue for each round : {await self.memory.status.get("history_product_order")}
            - If there are products within the company that remain unsold, a maintenance cost of 1% of their base_price will be deducted in each round.
            - I need to decide whether to accept or reject each request.
            - I can analyze the requested product categories, product quantities, and specific request information in conjunction with my company's information. As well as my own production capacity
            - When considering the number of products required by the other party, it can appropriately exceed the inventory it already has.
            - Do not disclose your own financial and inventory situation to outsiders.


            How can I respond to these requests.? Consider:
            1. Are the requested product quantities and the expected payment amounts in the transaction request reasonable ?
            2. Can my current and future inventory support fulfilling this transaction ?
            3. When considering multiple orders comprehensively, one must take into account how much inventory and production capacity can be supplied.

            Please generate a JSON list whose length equals the value of {received_length}.
            And each object inside represents a response to one of the requests in the request list.  
            Each element of the list should be an object containing exactly two fields:  
            - "willing_to_transaction": answer only "YES" or "NO"
            - "reason": explain why you chose YES or NO

            For example, if length is 3, return something like:
            [
                {{"willing_to_transaction": "YES", "reason": "We have enough stock"}},
                {{"willing_to_transaction": "NO", "reason": "Not enough demand"}},
                {{"willing_to_transaction": "YES", "reason": "Price is acceptable"}}
            ]

            Only output the JSON list, do not add any extra explanation."""

        response = await self.llm.atext_request(
            [
                {
                    "role": "system",
                    "content": "You are helping generate replies to different requests from the list of customers received",
                },
                {"role": "user", "content": response_prompt},
            ],
            intelligence_level = intelligence_level
        )
        try:
            if not response or not response.strip():
                print(f"Empty or invalid response received: {repr(response)}")
                willing_to_transaction = None
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
                    parsed_list = json_repair.loads(content_cleaned)
                    if not isinstance(parsed_list, list) or not parsed_list:
                        raise ValueError("Parsed JSON is not a non-empty list")
                except Exception as e:
                    get_logger().error(f"PayLoadError Failed to parse content as JSON list: {content_cleaned}. Error: {e}")
                    parsed = {}
            index = 0
            for parsed in parsed_list:
                willing_to_transaction = parsed.get("willing_to_transaction")
                reason = parsed.get("reason")
                received_request = received_requests[index]
                if received_request["requesting_company_id"] in company_map:
                    continue
                else:
                    company_map.append(received_request["requesting_company_id"])
                index+=1
                if willing_to_transaction and willing_to_transaction.lower() == "yes":
                    payment_decision = await self.update_payment_method("sale",self.safe_parse_quantity(received_request["expected_quantity"]),
                                                                    received_request["requesting_company_id"])
                    content1 = json.dumps(payment_decision)
                    await self._agent.send_message_to_agent(
                        fid,
                        content1,
                        "update_payment_method",
                        "update_payment_method"
                    )
                    transaction_order = {
                        "Purchaser": received_request["requesting_company_id"],
                        "Supplier": await self.memory.status.get("id"),
                        "product_name": received_request["expected_products"],
                        "Unit_price": received_request["sell_price"],
                        "product_quantity": received_request["expected_quantity"],
                        "payment_method": payment_decision["payment_method"],
                        "details": payment_decision["details"],
                        "state": "Preparation phase",
                        "reason": reason,
                        "step": self.step_count
                    }
                    content = json.dumps(transaction_order)
                    await self._agent.send_message_to_agent(
                        received_request["requesting_company_id"],
                        content,
                        "operation-deal",
                        received_request["topic"]
                    )
                else:
                    reason = parsed.get("reason", "Rejected without specific reason")
                    await self._agent.send_message_to_agent(
                        received_request["requesting_company_id"],
                        reason,
                        "operation-reject",
                        received_request["topic"]
                    )
                    print(f"Agent not willing to transaction or response invalid: {willing_to_transaction}")

        except Exception as e:
            get_logger().error(f"Error parsing response: {repr(response)}, error: {e}")
            willing_to_transaction = None

    def safe_parse_quantity(value: str, default: int = 0) -> int:
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            # 提取字符串中的数字
            match = re.search(r"\d+", value)
            if match:
                return int(match.group())
        return default

    def priority_key(self,item):
        return 0 if item[0] == "Product Asking" else 1

    async def forward(self):
        update_plan = []
        current_plan = await self.memory.status.get("current_plan")
        self.step_count += 1
        fid = await self.memory.status.get("id")
        for c_p in current_plan:
            update_plan.append(c_p)
        update_plan.sort(key=self.priority_key)
        while len(update_plan)>0:
            plan = update_plan.pop(0)
            if plan[0] == "Inventory insufficient":
                needed_product = plan[1]
                # 采货流程
                # 1.选择供应商
                await self.select_partner_new(needed_product)
                # 2.询价 & 投标
                inventory_system = await self.memory.status.get("inventory_system") or {}
                products_dict = inventory_system.get("products", {})
                materials_dict = inventory_system.get("materials", {})
                current_quantity = 0

                # 先检查产品库存
                for product_id, product_info in products_dict.items():
                    if product_info.get("product_name") == needed_product:
                        current_quantity = product_info.get("quantity", 0)
                        break

                # 如果产品库存中没有，检查材料库存
                if current_quantity == 0:
                    for material_id, material_info in materials_dict.items():
                        if material_info.get("product_name") == needed_product:
                            current_quantity = material_info.get("quantity", 0)
                            break
                exists = any(item.get("product") == needed_product for item in self.need_record) 
                if not exists:
                    self.need_record.append({
                        "product":needed_product,
                        "step":self.step_count
                    })
                await self.sending_price_check(needed_product, current_quantity)
                self.potential_partner = []
            elif plan[0] == "Product Asking":
                fid = await self.memory.status.get('id')
                target_product = plan[1]
                products = await self.memory.status.get("products")
                received_request_list = []
                remaining_requests = []
                while len(self.received_requests)>0:
                    received_request = self.received_requests.pop(0)
                    if received_request["expected_products"] == target_product:
                        sell_price = -1
                        for product in products:
                            if product["product_name"] == received_request["expected_products"]:
                                sell_price = product["sell_price"]
                                break
                        received_request['sell_price'] = sell_price
                        received_request_list.append(received_request)
                    else:
                        remaining_requests.append(received_request)
                self.received_requests = remaining_requests
                await self.handle_product_request(received_request_list)
        await self.memory.status.update("current_plan",update_plan)