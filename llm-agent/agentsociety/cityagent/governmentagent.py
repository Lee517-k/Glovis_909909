import asyncio
import json
import logging
from typing import Optional

import jsonc
import numpy as np

from agentsociety.agent.agent_base import Agent
from ..agent import GovernmentAgentBase, AgentToolbox
from ..environment import EconomyClient
from ..llm import LLM
from ..memory import Memory
from ..message import Messager
from ..environment import Environment
from ..agent import Block, FormatPrompt

__all__ = ["GovernmentAgent"]

class PolicyManagementBlock(Block):
    """
    政府的政策管理模块
    """
    def __init__(
        self,
        agent: Agent,
        llm: LLM,
        environment: Environment,
        memory: Memory,
    ):
        super().__init__(
            "PolicyManagementBlock", llm=llm, environment=environment, memory=memory
        )
        self._agent = agent
        self.company_info_list = []
        self.enable_incentives = False
        self.incentive_companies_list = []
        self.expenditure = 0.0

    async def deside_enable_incentives(self):
        response_prompt = f"""Based on:
        - My profile: {{
            "My budget spending limit": "{await self.memory.status.get("budget_max") or ""}",
            "The subsidy cost per unit required to incentivize each company": "{await self.memory.status.get("subsidy_cost") or ""}",
            "Efficiency coefficient of government regulation and incentives": "{await self.memory.status.get("supervison_eff") or ""}",
            "My initial willingness to provide incentive subsidies (0-1)": "{await self.memory.status.get("p_subsidy")}",
            "The current state of platformization at various companies": "{self.company_info_list}",
        }}
        - I need to consider whether to provide incentive subsidies for companies participating in the platform.
        - My current remaining budget: {await self.memory.status.get("budget_rem") or ""}
        - Cost of providing incentives: 
        For each company that participates in the platform under my incentive, I need to provide a subsidy of “subsidy_cost” for the platform transactions it conducts.

        Should I provide incentive subsidies ? Consider:
        1. My ultimate goal is to encourage as many companies as possible to participate in the platform.
        2. At the same time, it is necessary to consider one's own cost expenditures.

        Answer only YES or NO, in JSON format, e.g. {{"should_provide": "YES"}}"""
        should_respond = await self.llm.atext_request(
            dialog=[
                        {
                            "role": "system",
                            "content": "You are helping decide whether to provide incentive subsidies for companies participating in the platform.",
                        },
                        {"role": "user", "content": response_prompt},
                    ],
                    response_format={"type": "json_object"},
            )
        print("should_provide",should_respond)
        should_respond = jsonc.loads(should_respond)["should_provide"]
        if should_respond == "YES":
            await self.memory.status.update("enable_incentives",True)
        else:
            await self.memory.status.update("enable_incentives",False)

    async def send_invitation(self):
        company_info = self.company_info_list[0]
        if not company_info["has_join"]:
            content_info = {
                "subsidy_cost" : await self.memory.status.get("subsidy_cost"),
            }
            content = json.dumps(content_info)
            await self._agent.send_message_to_agent(
                company_info["company_id"],
                content,
                "economy",
            )

    async def process_message(self, payload: dict) -> str:
        content = payload.get("content")
        company_id = payload["from"]
        already_added = any(p == company_id for p in self.company_info_list)
        if content == "accept" and not already_added:
            self.company_info_list.append(company_id)
        if content == "deal" and already_added:
            subsidy_cost = await self.memory.status.get("subsidy_cost")
            self.expenditure = self.expenditure + subsidy_cost
            # TODO 替换成周期性整体更新
            await self.memory.status.update("expenditure",self.expenditure)
            budget_rem = await self.memory.status.get("budget_rem") - self.expenditure
            await self.memory.status.update("budget_rem",budget_rem)
        return ""

    async def forward(self): 
        self.company_info_list = await self.memory.status.get("policy_survey")
        self.enable_incentive = await self.memory.status.get("enable_incentives")
        if not self.enable_incentive:
            await self.deside_enable_incentives()
        if len(self.company_info_list)!=0 and self.enable_incentive:
            await self.send_invitation()

class GovernmentAgent(GovernmentAgentBase):
    """A government institution agent that handles periodic economic operations such as tax collection."""

    policy_management_block:PolicyManagementBlock

    configurable_fields = ["time_diff"]
    default_values = {
        "time_diff": 30 * 24 * 60 * 60,
    }
    fields_description = {
        "time_diff": "Time difference between each forward, day * hour * minute * second",
    }

    def __init__(
        self,
        id: int,
        name: str,
        toolbox: AgentToolbox,
        memory: Memory,
    ) -> None:
        """
        Initialize the GovernmentAgent.

        Args:
            - `name` (`str`): The name or identifier of the agent.
            - `toolbox` (`AgentToolbox`): The toolbox of the agent.
            - `memory` (`Memory`): The memory of the agent.

        - **Description**:
            - Initializes the GovernmentAgent with the provided parameters and sets up necessary internal states.
        """
        super().__init__(
            id=id,
            name=name,
            toolbox=toolbox,
            memory=memory,
        )
        self.policy_management_block = PolicyManagementBlock(
            agent=self,llm=self.llm,environment=self.environment, memory=self.memory
        )
        self.initailzed = False
        self.last_time_trigger = None
        self.time_diff = 30 * 24 * 60 * 60
        self.forward_times = 0

    async def process_agent_chat_response(self, payload: dict) -> str:
        self.policy_management_block.process_message(payload)
        return ""

    async def forward(self):
        # await self.policy_management_block.forward()
        pass

    # async def forward(self):
    #     """Execute the government's periodic tax collection and notification cycle."""
    #    
    #     print("FUCASDHJKLASDLKASDJLTEST",test_GROO)
    #     if await self.month_trigger():
    #         citizen_ids = await self.memory.status.get("citizen_ids")
    #         agents_forward = await self.gather_messages(citizen_ids, "forward")
    #         if not np.all(np.array(agents_forward) > self.forward_times):
    #             return
    #         incomes = await self.gather_messages(citizen_ids, "income_currency") 
    #         _, post_tax_incomes = (
    #             await self.environment.economy_client.calculate_taxes_due(
    #                 self.id, citizen_ids, incomes, enable_redistribution=False
    #             )
    #         )
    #         for citizen_id, income, post_tax_income in zip(
    #             citizen_ids, incomes, post_tax_incomes
    #         ):
    #             tax_paid = income - post_tax_income
    #             await self.send_message_to_agent(
    #                 citizen_id, f"tax_paid@{tax_paid}", "economy"
    #             )
    #         self.forward_times += 1
    #         for citizen_id in citizen_ids:
    #             await self.send_message_to_agent(
    #                 citizen_id, f"government_forward@{self.forward_times}", "economy"
    #             )

    async def reset(self):
        """Reset the GovernmentAgent."""
        pass

    async def month_trigger(self):
        """
        Check if the monthly tax cycle should be triggered based on elapsed time.

        Returns:
            True if the time difference since last trigger exceeds `time_diff`, False otherwise.
        """
        now_tick = self.environment.get_tick()
        if self.last_time_trigger is None:
            self.last_time_trigger = now_tick
            return False
        if now_tick - self.last_time_trigger >= self.time_diff:
            self.last_time_trigger = now_tick
            return True
        return False



    async def gather_messages(self, agent_ids, content):
        """
        Collect messages from specified agents filtered by content type.

        Args:
            agent_ids: List of agent IDs to gather messages from.
            content: Message content type to filter (e.g., "forward", "income_currency").

        Returns:
            List of message contents from the specified agents.
        """
        infos = await super().gather_messages(agent_ids, content)
        return [info["content"] for info in infos]