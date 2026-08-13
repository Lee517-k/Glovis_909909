import asyncio
import json
import os
import time
# 添加新的导入

from firmagentsql.insert import EnterpriseDataInserter
from firmagentsql.latest_experiment_query import LatestExperimentQuery

from agentsociety.agent.agent import NewFirmAgentBase
from agentsociety.agent.agent_base import Agent
from agentsociety.cityagent.firmblocks.firm_cognition_block import FirmCognitionBlock
from agentsociety.cityagent.firmblocks.collaboration_block import CollaborationBlock
from agentsociety.cityagent.firmblocks.firm_economy_block import FirmEconomyBlock
from agentsociety.cityagent.firmblocks.firm_need_block import FirmNeedsBlock
from agentsociety.cityagent.firmblocks.stock_block import StockBlock
from agentsociety.cityagent.firmblocks.price_payment.firm_economy_block_extension import FirmEconomyBlockExtension
from agentsociety.cityagent.firmblocks.firm_plan_block import FirmPlanBlock
from ..agent import AgentToolbox, Block
from ..llm import LLM
from ..memory import Memory
from ..environment import Environment

__all__ = ["NewFirmAgent"]


class FirmMindblock(Block):
    cognition_block: FirmCognitionBlock

    def __init__(self, llm: LLM, environment: Environment, memory: Memory):
        super().__init__(
            name="Firm_mind_block",
            llm=llm,
            environment=environment,
            memory=memory,
        )
        self.cognition_block = FirmCognitionBlock(
            llm=self.llm, memory=self.memory, environment=self.environment
        )

    async def forward(self):
        await self.cognition_block.forward()


class FirmPlanAndActionBlock(Block):
    stock_block: StockBlock
    need_block: FirmNeedsBlock
    plan_block: FirmPlanBlock

    def __init__(
            self,
            agent: Agent,
            llm: LLM,
            environment: Environment,
            memory: Memory,
    ):
        super().__init__(
            name="Firm_plan_and_action_block",
            llm=llm,
            environment=environment,
            memory=memory,
        )
        self._agent = agent
        self.stock_block = StockBlock(agent=self._agent, llm=self.llm, environment=self.environment, memory=self.memory)
        self.need_block = FirmNeedsBlock(agent=self._agent, llm=llm, environment=environment, memory=memory)
        self.plan_block = FirmPlanBlock(llm=llm, environment=environment, memory=memory)

    async def reset(self):
        """Reset the plan and action block."""
        pass

    async def plan_generation(self):
        """Generate a new plan if no current plan exists in memory."""
        cognition = None
        current_plan = await self.memory.status.get("current_plan")
        if current_plan is None or not current_plan:
            cognition = (
                await self.plan_block.forward()
            )  # Delegate to PlanBlock for plan creation
        return cognition

    async def step_execution(self):
        """Execute the current step in the active plan based on step type."""
        pass

    async def forward(self):
        # # # Long-term decision
        # # await self.month_plan_block.forward()

        # # update needs
        # cognition = await self.needs_block.forward()
        # if cognition:
        #     await self._agent.save_agent_thought(cognition)

        # # plan generation
        # cognition = await self.plan_generation()
        # # if cognition:
        # #     await self._agent.save_agent_thought(cognition)

        # # # step execution
        # # await self.step_execution()

        # 定期更新库存 -- 生产产品
        await self.stock_block.forward()
        # 确认需求
        await self.need_block.forward()
        pass


class NewFirmAgent(NewFirmAgentBase):
    firm_planAndaction_block: FirmPlanAndActionBlock
    firm_mind_block: FirmMindblock
    collaboration_block: CollaborationBlock
    firm_economy_block: FirmEconomyBlock
    economy_extension: FirmEconomyBlockExtension

    def __init__(
            self,
            id: int,
            name: str,
            toolbox: AgentToolbox,
            memory: Memory,
    ) -> None:
        super().__init__(
            id=id,
            name=name,
            toolbox=toolbox,
            memory=memory, )

        # 保存初始化时的level值作为实例变量
        async def store_initial_level():
            initial_level = await self.memory.status.get("level")
            self.initial_level = initial_level if initial_level is not None else 1
            print(f"Agent {name} stored initial level: {self.initial_level}")

        async def check_level():
            level = await self.memory.status.get("level")
            print(f"Agent {name} (ID: {id}) initialized with level: {level}")

        asyncio.create_task(store_initial_level())
        asyncio.create_task(check_level())
        self.prority = True
        self.step_count = -1
        self.firm_mind_block = FirmMindblock(
            llm=self.llm, environment=self.environment, memory=self.memory
        )
        self.collaboration_block = CollaborationBlock(
            agent=self, llm=self.llm, environment=self.environment, memory=self.memory,
            update_payment_method=self.update_payment_method
        )
        self.firm_economy_block = FirmEconomyBlock(
            agent=self, llm=self.llm, environment=self.environment, memory=self.memory
        )
        self.firm_planAndaction_block = FirmPlanAndActionBlock(
            agent=self, llm=self.llm, environment=self.environment, memory=self.memory
        )
        self.economy_extension = FirmEconomyBlockExtension(
            agent=self,
            llm=self.llm,
            environment=self.environment,
            memory=self.memory
        )
        self.relative_frims = []
        self.record = []
        self.db_inserter = None
        self.current_experiment_id = None
        self.db_initialized = False
        # 添加静态参数上传标志
        # self.static_params_uploaded = False

    async def broadcast_product_info(self):
        # 将自身可销售产品存储到环境信息中--作为全局公开信息
        name = await self.memory.status.get("name")
        id = await self.memory.status.get("id")
        products = await self.memory.status.get("products")
        products = await self.memory.status.get("products")
        info_list = []
        for product in products:
            # 兼容新旧数据格式：优先使用 product_name，如果不存在则使用 material_name
            product_name = product.get("product_name") or product.get("material_name")
            if product_name and product_name not in info_list:
                info_list.append({
                    "product_name":product_name,
                    "sell_price":product["sell_price"],
                    "base_price":product["base_price"],
                })
        await self.environment.economy_client.update(
            -1,
            "global_company_status",
            value=[
                {'company_id': id, 'company_name': name, 'product_list': info_list},
            ],
            mode="merge",
        )

    async def get_company_name(self, fid):
        state = await self.environment.economy_client.get(id=-1, key="global_company_status")
        for company in state:
            if company["company_id"] == fid:
                return company["company_name"]

    async def get_market_price(self,product_name):
        state = await self.environment.economy_client.get(id=-1, key="global_company_status")
        market_price = []
        for company in state:
            product_list = company["product_list"]
            for product in product_list:
                if product["product_name"] == product_name:
                    price = product["sell_price"]
                    if product["sell_price"] == -1:
                        price = 0
                    market_price.append(price)
        filtered_prices = [p for p in market_price if p != -1]
        return filtered_prices

    async def update_sell_price(self):
        fid = await self.memory.status.get("id")
        products = await self.memory.status.get("products")
        price_data = []
        for product in products:
            market_price = await self.get_market_price(product["product_name"])
            market_price_str = ",".join(map(str,market_price ))
            price_decision = await self.economy_extension.decide_product_price(product["product_name"],market_price_str,self.step_count)
            price_decision["product_name"] = product["product_name"]
            price_data.append(price_decision)
        content = json.dumps(price_data)
        await self.send_message_to_agent(
            fid,
            content,
            "update_sell_price",
            "update_sell_price"
        )
        # data = {
        #     "step":self.step_count,
        #     "id":fid,
        #     "price_data":price_data
        # }

        # with open(filename, "a", encoding="utf-8") as f:
        #     json.dump(data, f, ensure_ascii=False, indent=4)
        # pass

    async def update_payment_method(self, transaction_type, transaction_amount, transaction_partner):
        return await self.economy_extension.decide_payment_method(transaction_type, transaction_amount,
                                                                  transaction_partner)
        # print(f"销售交易的付款方式决策:")
        # print(json.dumps(payment_decision, ensure_ascii=False, indent=2))

    async def forward(self):
        """Main agent loop coordinating status updates, plan execution, and cognition."""
        start_time = time.time()
        fid = await self.memory.status.get("id")
        # if fid == 5:
        #     print("TESTFUNDCHANGE",fid)
        #     if self.step_count==50:
        #         fund = await self.memory.status.get("fund")
        #         fund = fund * 0.6
        #         await self.memory.status.update("fund",fund)
        if self.step_count > 200:
            return
        # 初始化数据库连接（只在第一次调用时执行）
        if not self.db_initialized:
            await self.initialize_database_connection()

        await self.broadcast_product_info()
        self.step_count += 1
        if self.step_count % 2 == 1:
            await self.update_sell_price()

        await self.firm_planAndaction_block.forward()
        await self.collaboration_block.forward()
        await self.firm_economy_block.forward()

        # 添加库存监控和MLflow记录
        if self.step_count == 0:
            await self.upload_static_parameters_to_mlflow()

        await self.monitor_and_log_inventory()

        await self.save_state()
        # TODO
        # planning and action
        return

    async def cleanup(self):
        """清理资源"""
        if self.db_inserter:
            await self.db_inserter.disconnect()
            print("数据库连接已关闭")

    async def initialize_database_connection(self):
        """初始化数据库连接和获取当前实验ID"""
        if self.db_initialized:
            return

        try:
            # 初始化数据库插入器
            self.db_inserter = EnterpriseDataInserter()
            await self.db_inserter.connect()
            await self.db_inserter.create_tables()

            # 获取最新实验ID
            experiment_query = LatestExperimentQuery()
            latest_experiments = await experiment_query.get_latest_experiments(1)

            if not latest_experiments.empty:
                self.current_experiment_id = str(latest_experiments.iloc[0]['id'])
                print(f"使用实验ID: {self.current_experiment_id}")
            else:
                # 如果没有找到实验，使用默认ID
                self.current_experiment_id = "enterprise_simulation_default"
                print(f"未找到实验记录，使用默认实验ID: {self.current_experiment_id}")

            self.db_initialized = True
            print("数据库连接初始化成功")

        except Exception as e:
            print(f"数据库初始化失败: {e}")
            self.db_inserter = None
            self.current_experiment_id = None

    async def save_state_to_database(self, state_data=None):
        """将状态数据保存到数据库"""
        if not self.db_inserter or not self.current_experiment_id:
            print("数据库未初始化，跳过数据库保存")
            return
        try:
            if state_data is None:
                # 如果没有传入数据，则构建数据（保持向后兼容）
                fid = await self.memory.status.get("id")

                # 获取inventory_system数据
                inventory_system = await self.memory.status.get("inventory_system") or {}

                # 为了向后兼容，从inventory_system生成product_stocks格式
                product_stocks = []
                if "products" in inventory_system:
                    for product_id, product_info in inventory_system["products"].items():
                        product_stocks.append({
                            "product_id": int(product_id),
                            "product_name": product_info.get("product_name", ""),
                            "quantity": product_info.get("quantity", 0)
                        })

                # 获取并打印level值用于调试
                level_value = await self.memory.status.get("level")
                print(f"Agent {await self.memory.status.get('name')} level from memory: {level_value}")
                print(f"Agent {await self.memory.status.get('name')} level type: {type(level_value)}")

                # 如果内存中的level丢失，使用初始化时保存的值
                if level_value is None and hasattr(self, 'initial_level'):
                    level_value = self.initial_level
                    print(f"Using stored initial level: {level_value}")
                
                state_data = {
                    "step": self.step_count,
                    "id": fid or "",
                    "company_name": await self.memory.status.get("name") or "",
                    "products": await self.memory.status.get("products") or "",
                    "fund": await self.memory.status.get("fund") or "",
                    "product_stocks": product_stocks,
                    "available_materials": await self.memory.status.get("available_materials") or "",
                    "transaction_list": await self.memory.status.get("transaction_list") or "",
                    "record": self.record,
                    "inventory_system": await self.memory.status.get("inventory_system") or {},
                    "intelligence_level": await self.memory.status.get("intelligence_level") or 1,
                    "level": level_value if level_value is not None else 1,
                }

                print(f"State data level before database insert: {state_data.get('level')}")
            # 插入到数据库
            await self.db_inserter.insert_state_data(self.current_experiment_id, state_data)
            print(f"步骤 {self.step_count} 的状态数据已保存到数据库")

        except Exception as e:
            print(f"保存状态到数据库失败: {e}")

    async def save_state(self):
        """保存状态（同时保存到文件和数据库）"""
        fid = await self.memory.status.get("id")
        filename = f"./data/state_{fid}.json"
        level_value = await self.memory.status.get("level")

        # 获取inventory_system数据
        inventory_system = await self.memory.status.get("inventory_system") or {}

        # 为了向后兼容，从inventory_system生成product_stocks格式
        product_stocks = []
        if "products" in inventory_system:
            for product_id, product_info in inventory_system["products"].items():
                product_stocks.append({
                    "product_id": int(product_id),
                    "product_name": product_info.get("product_name", ""),
                    "quantity": product_info.get("quantity", 0)
                })

        # 新一轮要保存的信息
        new_state = {
            "step": self.step_count,
            "id": fid or "",
            "company_name": await self.memory.status.get("name") or "",
            "company_products": await self.memory.status.get("products") or "",
            "company_fund": await self.memory.status.get("fund") or "",
            "product_stocks": product_stocks,  # 使用从inventory_system转换的数据
            "available_materials": await self.memory.status.get("available_materials") or "",
            "transaction_list": await self.memory.status.get("transaction_list") or "",
            "record": self.record,
            # 添加新的库存系统字段（如果存在）
            "inventory_system": await self.memory.status.get("inventory_system") or {},
            "intelligence_level": await self.memory.status.get("intelligence_level") or 1,
            "level": level_value if level_value is not None else 1,
        }

        # # 保存到文件（原有逻辑）
        # if os.path.exists(filename):
        #     with open(filename, "r", encoding="utf-8") as f:
        #         try:
        #             data = json.load(f)
        #         except json.JSONDecodeError:
        #             data = []
        # else:
        #     data = []

        # data.append(new_state)

        # with open(filename, "w", encoding="utf-8") as f:
        #     json.dump(data, f, ensure_ascii=False, indent=4)

        # 同时保存到数据库
        await self.save_state_to_database(new_state)

        self.record = []

    async def reset(self):
        """Reset the FirmAgent."""
        pass

    async def process_agent_chat_response(self, payload: dict) -> str:
        payload_type = payload.get("type")
        payload_topic = payload.get("topic")
        source = payload["from"]
        content = payload["content"]
        self.record.append({
            "source": source,
            "sourceName": await self.get_company_name(source),
            "content": payload,
            "payload_topic":payload_topic,
        })
        if payload_type == "economy":
            await self.firm_economy_block.process_message(payload)
        elif "operation" in payload_type:
            await self.collaboration_block.process_message(payload)
        return ""

    async def reset_position(self):
        """Reset the position of the agent."""
        headquarters = await self.status.get("headquarters")
        headquarters = headquarters["aoi_position"]["hq_aoi_id"]
        await self.environment.reset_person_position(person_id=self.id, aoi_id=headquarters)

    async def react_to_intervention(self, intervention_message: str):
        """React to an intervention"""
        pass
        # cognition
        # conclusion = await self.mind_block.cognition_block.emotion_update(
        #     intervention_message
        # )
        # await self.save_agent_thought(conclusion)
        # await self.memory.stream.add_cognition(description=conclusion)
        # # needs
        # await self.plan_and_action_block.needs_block.reflect_to_intervention(
        #     intervention_message
        # )

    async def upload_static_parameters_to_mlflow(self):
        # 上传企业静态参数到MLflow parameters中，只在初始化时执行一次
        agent_name = None
        try:
            # 检查MLflow是否启用
            if self.mlflow_client is None or not self.mlflow_client.enabled:
                return

            # 直接从memory中获取agent的数据
            agent_id = await self.memory.status.get("id")
            agent_name = await self.memory.status.get("name")

            print(f"开始上传企业 {agent_name} (ID: {agent_id}) 的静态参数到MLflow")

            # 获取智能等级
            intelligence_level = await self.memory.status.get("intelligence_level") or 1
            print(f"设置企业 {agent_name} 的智能等级为: {intelligence_level}")

            # 上传企业基本信息
            await self.mlflow_client.log_param(
                key=f"company_name_{agent_name}",
                value=agent_name
            )

            # 记录agent_id
            await self.mlflow_client.log_param(
                key=f"agent_id_{agent_name}",
                value=str(agent_id)
            )

            # 上传智能等级
            await self.mlflow_client.log_param(
                key=f"intelligence_level_{agent_name}",
                value=str(intelligence_level)
            )

            # 上传产品信息 - 直接从memory获取
            main_products = await self.memory.status.get("products") or []
            for i, product in enumerate(main_products):
                product_prefix = f"product_{i + 1}_{agent_name}"

                # 产品名称
                await self.mlflow_client.log_param(
                    key=f"{product_prefix}_name",
                    value=product.get("product_name", "")
                )

                # 产品ID
                await self.mlflow_client.log_param(
                    key=f"{product_prefix}_id",
                    value=str(product.get("product_id", 0))
                )

                # 初始定价
                await self.mlflow_client.log_param(
                    key=f"{product_prefix}_base_price",
                    value=str(product.get("base_price", 0))
                )

                # 是否终端产品
                await self.mlflow_client.log_param(
                    key=f"{product_prefix}_is_terminal_product",
                    value=str(product.get("is_terminal_product", False))
                )

                # 产品配方
                product_construct = product.get("product_construct", [])
                if isinstance(product_construct, list):
                    construct_str = "; ".join([
                        f"{item['product_name']}(ID:{item['product_id']}): {item['quantity']}"
                        for item in product_construct if isinstance(item, dict)
                    ])
                else:
                    construct_str = str(product_construct)

                await self.mlflow_client.log_param(
                    key=f"{product_prefix}_product_construct",
                    value=construct_str
                )

                # 制造成本
                await self.mlflow_client.log_param(
                    key=f"{product_prefix}_manufacturing_cost",
                    value=str(product.get("manufacturing_cost", 0))
                )

                # 利润率
                await self.mlflow_client.log_param(
                    key=f"{product_prefix}_profit_margin",
                    value=str(product.get("profit_margin", 0))
                )

            # 上传可用材料信息 - 直接从memory获取
            available_materials = await self.memory.status.get("available_materials") or []
            for i, material in enumerate(available_materials):
                material_prefix = f"material_{i + 1}_{agent_name}"

                await self.mlflow_client.log_param(
                    key=f"{material_prefix}_name",
                    value=material.get("product_name", material.get("material_name", ""))
                )

                await self.mlflow_client.log_param(
                    key=f"{material_prefix}_id",
                    value=str(material.get("product_id", material.get("material_id", 0)))
                )

            # 上传库存系统信息 - 直接从memory获取
            inventory_system = await self.memory.status.get("inventory_system") or {}

            # 确保inventory_system是字典格式
            if isinstance(inventory_system, str):
                try:
                    inventory_system = json.loads(inventory_system)
                except json.JSONDecodeError:
                    print(f"Failed to parse inventory_system JSON for {agent_name}")
                    inventory_system = {}

            if not isinstance(inventory_system, dict):
                inventory_system = {}

            # 产品库存
            products = inventory_system.get("products", {})
            if isinstance(products, dict):
                for i, (product_id, product_info) in enumerate(products.items()):
                    if isinstance(product_info, dict):
                        inventory_prefix = f"product_inventory_{i + 1}_{agent_name}"

                        await self.mlflow_client.log_param(
                            key=f"{inventory_prefix}_name",
                            value=product_info.get("product_name", "")
                        )

                        await self.mlflow_client.log_param(
                            key=f"{inventory_prefix}_quantity",
                            value=str(product_info.get("quantity", 0))
                        )

            # 材料库存
            materials = inventory_system.get("materials", {})
            if isinstance(materials, dict):
                for i, (material_id, material_info) in enumerate(materials.items()):
                    if isinstance(material_info, dict):
                        inventory_prefix = f"material_inventory_{i + 1}_{agent_name}"

                        await self.mlflow_client.log_param(
                            key=f"{inventory_prefix}_name",
                            value=material_info.get("product_name", "")
                        )

                        await self.mlflow_client.log_param(
                            key=f"{inventory_prefix}_quantity",
                            value=str(material_info.get("quantity", 0))
                        )

            # 上传资金信息
            company_fund = await self.memory.status.get("fund") or 0
            await self.mlflow_client.log_param(
                key=f"initial_fund_{agent_name}",
                value=str(company_fund)
            )

            print(f"Successfully uploaded static parameters for company {agent_name} to MLflow")

        except Exception as e:
            print(f"Error uploading static parameters for agent {agent_name}: {e}")

    async def monitor_and_log_inventory(self):
        """监控库存数量、订单份额和金额并上传到MLflow"""
        agent_name = None
        try:
            # 检查MLflow是否启用
            if self.mlflow_client is None or not self.mlflow_client.enabled:
                return

            # 获取agent基本信息
            agent_id = await self.memory.status.get("id")
            agent_name = await self.memory.status.get("name")
            current_step = self.step_count

            # === 统一库存系统监控 ===
            inventory_system = await self.memory.status.get("inventory_system") or {}

            # 确保inventory_system是字典格式
            if isinstance(inventory_system, str):
                try:
                    inventory_system = json.loads(inventory_system)
                except json.JSONDecodeError:
                    print(f"Failed to parse inventory_system JSON for {agent_name}")
                    inventory_system = {}

            if not isinstance(inventory_system, dict):
                inventory_system = {}

            # 监控产品库存 - 修正字段名
            products = inventory_system.get("products", {})
            total_product_inventory = 0

            if isinstance(products, dict):
                for product_id, product_info in products.items():
                    if isinstance(product_info, dict):
                        product_name = product_info.get("product_name", "unknown")
                        quantity = product_info.get("quantity", 0)
                        total_product_inventory += quantity

                        await self.mlflow_client.log_metric(
                            key=f"product_inventory_{agent_name}_{product_name}",
                            value=float(quantity),
                            step=current_step
                        )

            # 监控材料库存 - 修正字段名
            materials = inventory_system.get("materials", {})
            total_material_inventory = 0

            if isinstance(materials, dict):
                for material_id, material_info in materials.items():
                    if isinstance(material_info, dict):
                        material_name = material_info.get("product_name", "unknown")
                        quantity = material_info.get("quantity", 0)
                        total_material_inventory += quantity

                        await self.mlflow_client.log_metric(
                            key=f"material_inventory_{agent_name}_{material_name}",
                            value=float(quantity),
                            step=current_step
                        )
            # 添加产品价格变动记录
            products = await self.memory.status.get("products")
            for product in products:
                await self.mlflow_client.log_metric(
                    key=f"{agent_name}_{product['product_name']}_sell_price",
                    value=float(product["sell_price"]),
                    step=current_step
                )
            Unfinished_order = await self.memory.status.get("Unfinished_order")
            for order in Unfinished_order:
                await self.mlflow_client.log_metric(
                    key=f"{agent_name}_Unfinished_{order['product_name']}",
                    value=float(order["Undelivered_portion"]),
                    step=current_step
                )

            Position_cost = await self.memory.status.get("Position_cost")
            await self.mlflow_client.log_metric(
                key=f"company_{agent_name}_Position_cost",
                value=float(Position_cost),
                step=current_step
            )

            make_cost = await self.memory.status.get("make_cost")
            await self.mlflow_client.log_metric(
                key=f"company_{agent_name}_make_cost",
                value=float(make_cost),
                step=current_step
            )

            produce_count = await self.memory.status.get("produce_count")
            for count in produce_count:
                await self.mlflow_client.log_metric(
                key=f"company_{agent_name}_{count['product_name']}_produce",
                value=float(count["count"]),
                step=current_step
                )
            
            current_production_cost = await self.memory.status.get("current_production_cost")

            for cost in current_production_cost:
                await self.mlflow_client.log_metric(
                    key=f"{agent_name}_{cost['product']}_amount",
                    value=float(cost["amount"]),
                    step=current_step
                )
                await self.mlflow_client.log_metric(
                    key=f"{agent_name}_{cost['product']}_total_cost",
                    value=float(cost["total_cost"]),
                    step=current_step
                )
                await self.mlflow_client.log_metric(
                    key=f"{agent_name}_{cost['product']}_material_cost",
                    value=float(cost["material_cost"]),
                    step=current_step
                )
            # 添加产品价格变动记录
            products = await self.memory.status.get("products")
            for product in products:
                await self.mlflow_client.log_metric(
                    key=f"{agent_name}_{product['product_name']}_sell_price",
                    value=float(product["sell_price"]),
                    step=current_step
                )

            current_production_cost = await self.memory.status.get("current_production_cost")

            for cost in current_production_cost:
                await self.mlflow_client.log_metric(
                    key=f"{agent_name}_{cost['product']}_amount",
                    value=float(cost["amount"]),
                    step=current_step
                )
                await self.mlflow_client.log_metric(
                    key=f"{agent_name}_{cost['product']}_total_cost",
                    value=float(cost["total_cost"]),
                    step=current_step
                )
                await self.mlflow_client.log_metric(
                    key=f"{agent_name}_{cost['product']}_material_cost",
                    value=float(cost["material_cost"]),
                    step=current_step
                )

            # 记录库存汇总数据
            await self.mlflow_client.log_metric(
                key=f"total_product_inventory_{agent_name}",
                value=float(total_product_inventory),
                step=current_step
            )

            await self.mlflow_client.log_metric(
                key=f"total_material_inventory_{agent_name}",
                value=float(total_material_inventory),
                step=current_step
            )

            total_inventory = total_product_inventory + total_material_inventory
            await self.mlflow_client.log_metric(
                key=f"total_inventory_{agent_name}",
                value=float(total_inventory),
                step=current_step
            )

            # === 智能等级监控 ===
            intelligence_level = await self.memory.status.get("intelligence_level") or 1
            await self.mlflow_client.log_metric(
                key=f"intelligence_level_{agent_name}",
                value=float(intelligence_level),
                step=current_step
            )

            # === 订单监控 ===
            # 获取交易列表
            transaction_list = await self.memory.status.get("transaction_list") or []
            fid = await self.memory.status.get("id")
            # 统计作为采购方的订单
            purchase_orders = [t for t in transaction_list if t.get("Purchaser") == agent_id]
            # 统计作为供应商的订单
            supply_orders = [t for t in transaction_list if t.get("Supplier") == agent_id]
            # 记录采购订单数量和总金额
            purchase_count = len(purchase_orders)
            purchase_total_amount = 0
            purchase_total_quantity = 0
            purchase_by_product = {}

            for order in purchase_orders:
                unit_price = float(order.get("Unit_price", 0))
                quantity = float(order.get("product_quantity", 0))
                order_amount = unit_price * quantity
                purchase_total_amount += order_amount
                purchase_total_quantity += quantity

                # 按产品统计采购
                product_name = order.get("product_name", "unknown")
                if product_name not in purchase_by_product:
                    purchase_by_product[product_name] = {"amount": 0, "quantity": 0}
                purchase_by_product[product_name]["amount"] += order_amount
                purchase_by_product[product_name]["quantity"] += quantity

            # 记录按产品分类的采购数据
            for product_name, data in purchase_by_product.items():
                await self.mlflow_client.log_metric(
                    key=f"purchase_amount_{agent_name}_{product_name}",
                    value=float(data["amount"]),
                    step=current_step
                )
                await self.mlflow_client.log_metric(
                    key=f"purchase_quantity_{agent_name}_{product_name}",
                    value=float(data["quantity"]),
                    step=current_step
                )

            # 记录采购订单汇总信息
            await self.mlflow_client.log_metric(
                key=f"purchase_orders_count_{agent_name}",
                value=float(purchase_count),
                step=current_step
            )
            await self.mlflow_client.log_metric(
                key=f"purchase_total_amount_{agent_name}",
                value=float(purchase_total_amount),
                step=current_step
            )
            await self.mlflow_client.log_metric(
                key=f"purchase_total_quantity_{agent_name}",
                value=float(purchase_total_quantity),
                step=current_step
            )

            # 记录销售订单数量和总金额
            supply_count = len(supply_orders)
            supply_total_amount = 0
            supply_total_quantity = 0
            supply_by_product = {}

            for order in supply_orders:
                unit_price = float(order.get("Unit_price", 0))
                quantity = float(order.get("product_quantity", 0))
                order_amount = unit_price * quantity
                supply_total_amount += order_amount
                supply_total_quantity += quantity

                # 按产品统计销售
                product_name = order.get("product_name", "unknown")
                if product_name not in supply_by_product:
                    supply_by_product[product_name] = {"amount": 0, "quantity": 0}
                supply_by_product[product_name]["amount"] += order_amount
                supply_by_product[product_name]["quantity"] += quantity

            # 记录按产品分类的销售数据
            for product_name, data in supply_by_product.items():
                await self.mlflow_client.log_metric(
                    key=f"supply_amount_{agent_name}_{product_name}",
                    value=float(data["amount"]),
                    step=current_step
                )
                await self.mlflow_client.log_metric(
                    key=f"supply_quantity_{agent_name}_{product_name}",
                    value=float(data["quantity"]),
                    step=current_step
                )

            # 记录销售订单汇总信息
            await self.mlflow_client.log_metric(
                key=f"supply_orders_count_{agent_name}",
                value=float(supply_count),
                step=current_step
            )
            await self.mlflow_client.log_metric(
                key=f"supply_total_amount_{agent_name}",
                value=float(supply_total_amount),
                step=current_step
            )
            await self.mlflow_client.log_metric(
                key=f"supply_total_quantity_{agent_name}",
                value=float(supply_total_quantity),
                step=current_step
            )

            # 记录净交易金额（销售收入 - 采购支出）
            net_transaction_amount = supply_total_amount - purchase_total_amount
            await self.mlflow_client.log_metric(
                key=f"net_transaction_amount_{agent_name}",
                value=float(net_transaction_amount),
                step=current_step
            )

            # === 资金监控 ===
            company_fund = await self.memory.status.get("fund") or 0
            await self.mlflow_client.log_metric(
                key=f"company_fund_{agent_name}",
                value=float(company_fund),
                step=current_step
            )
            step_profit = await self.memory.status.get("step_profit")
            await self.mlflow_client.log_metric(
                key=f"company_step_profit_{agent_name}",
                value=float(step_profit),
                step=current_step
            )
            # === 库存周转率计算 ===
            # 计算库存周转率（销售数量/平均库存）
            if total_inventory > 0:
                inventory_turnover = supply_total_quantity / total_inventory
                await self.mlflow_client.log_metric(
                    key=f"inventory_turnover_rate_{agent_name}",
                    value=float(inventory_turnover),
                    step=current_step
                )

            # === 库存结构分析 ===
            # 计算产品库存占比
            if total_inventory > 0:
                product_inventory_ratio = total_product_inventory / total_inventory
                material_inventory_ratio = total_material_inventory / total_inventory

                await self.mlflow_client.log_metric(
                    key=f"product_inventory_ratio_{agent_name}",
                    value=float(product_inventory_ratio),
                    step=current_step
                )
                await self.mlflow_client.log_metric(
                    key=f"material_inventory_ratio_{agent_name}",
                    value=float(material_inventory_ratio),
                    step=current_step
                )

            # 强制刷新MLflow数据
            if hasattr(self.mlflow_client, 'client'):
                try:
                    # 确保数据立即写入
                    await asyncio.sleep(0.1)  # 给MLflow一点时间处理
                except Exception as e:
                    print(f"MLflow sync warning: {e}")

        except Exception as e:
            # 记录错误但不中断agent执行
            print(f"Error in monitor_and_log_inventory for {agent_name}: {e}")
            import traceback
            traceback.print_exc()
