import logging
from typing import cast

import jsonc

from agentsociety.cityagent.blocks.utils import clean_json_response
from agentsociety.agent.agent_base import Agent
from ...agent import Block, FormatPrompt
from ...environment import Environment
from ...llm import LLM
from ...logger import get_logger
from ...memory import Memory

# TODO
# prompt需要精细调整，目前只完成了适用性粗略调整
INITIAL_NEEDS_PROMPT = """You are an intelligent agent Enterprise inventory demand management initialization system. Based on the profile information below, please help initialize the Enterprise inventory demand and related parameters.

Profile Information:
- main_products: {main_products}
- relative_products: {relative_products} 
- culture: {culture}
- ownership_type: {ownership_type}
- stock_status: {stock_status}

Current Time: {now_time}

Please initialize the agent's inventory handling behavior demand level and parameters according to the above configuration file. Returns the value in JSON format according to the following structure:

Current inventory handling behavior demand level levels (0-1 float values, lower means less demand):
- selling_demand: Selling demand level (Normally, the agent will be higner demand with inventory is higner)
- replenish_demand: Replenishing demand level(Normally, the agent will be higner demand with inventory is low)

Please response in json format (Do not return any other text), example:
{{
    "current_demand": {{
        "selling_demand": 0.8,
        "replenish_demand": 0.7,
    }}
}}
"""

EVALUATION_PROMPT = """You are an evaluation system for an intelligent agent. The agent has performed the following actions to satisfy the {current_need} need:

Goal: {plan_target}
Execution situation:
{evaluation_results}

Current satisfaction: 
- hunger_satisfaction: {hunger_satisfaction}
- energy_satisfaction: {energy_satisfaction}
- safety_satisfaction: {safety_satisfaction}
- social_satisfaction: {social_satisfaction}

Please evaluate and adjust the value of {current_need} satisfaction based on the execution results above.

Notes:
1. Satisfaction values range from 0-1, where:
   - 1 means the need is fully satisfied
   - 0 means the need is completely unsatisfied 
   - Higher values indicate greater need satisfaction
2. If the current need is not "whatever", only return the new value for the current need. Otherwise, return both safe and social need values.
3. Ensure the return value is in valid JSON format, examples below:

Please response in json format for specific need (hungry here) adjustment (Do not return any other text), example:
{{
    "hunger_satisfaction": new_hunger_satisfaction_value
}}

Please response in json format for whatever need adjustment (Do not return any other text), example:
{{
    "safety_satisfaction": new_safety_satisfaction_value,
    "social_satisfaction": new_social_satisfaction_value
}}
"""

REFLECT_PROMPT = """You are an intelligent agent reflection system. Based on the intervention message below, please help to rebuild the satisfaction levels of the agent.

The agent has received/sense the following intervention message:
--------------------------------
{intervention_message}
--------------------------------

And the agent's current needs are:
- hunger_satisfaction: {hunger_satisfaction}
- energy_satisfaction: {energy_satisfaction}
- safety_satisfaction: {safety_satisfaction}
- social_satisfaction: {social_satisfaction}

The agent's current action is:
--------------------------------
{current_action}
--------------------------------

Please response in json format, example:
{{
    "hunger_satisfaction": new_hunger_satisfaction_value,
    "energy_satisfaction": new_energy_satisfaction_value,
    "safety_satisfaction": new_safety_satisfaction_value,
    "social_satisfaction": new_social_satisfaction_value,
}}
If you think the agent has to stop the current action and do something to satisfy the needs, please response in json format, example:
{{
    "do_something": True,
    "description": "Go to the hospital"
}}
"""

__all__ = ["FirmNeedsBlock"]

class FirmNeedsBlock(Block):
    def __init__(
        self,
        agent: Agent,
        llm: LLM,
        environment: Environment,
        memory: Memory,
    ):
        super().__init__(
            "FirmNeedsBlock", llm=llm, environment=environment, memory=memory
        )
        self._agent = agent
        self.initial_prompt = FormatPrompt(INITIAL_NEEDS_PROMPT)
        self.evaluation_prompt = FormatPrompt(EVALUATION_PROMPT)
        self.reflect_prompt = FormatPrompt(REFLECT_PROMPT)
        self.now_day = -1
        self.last_evaluation_time = None
        self.trigger_time = 0
        self.token_consumption = 0
        self.initialized = False
        self._need_to_do = None
        self._need_to_do_checked = False
        self.step_count = -1

    async def forward(self):
        current_need = await self.memory.status.get("current_need") 
        plan = []
        current_plan = await self.memory.status.get("current_plan")
        fid = await self.memory.status.get("id")
        self.step_count += 1
        for c_p in current_plan:
            plan.append(c_p)
        for need in current_need:
            if need[0] == "Inventory insufficient":
                plan.append(need)
        await self.memory.status.update("current_plan",plan)
        await self.memory.status.update("current_need", [])

