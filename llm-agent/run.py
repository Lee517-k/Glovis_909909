import asyncio
import logging

import ray

from agentsociety.cityagent import default
from agentsociety.configs import Config, load_config_from_file
from agentsociety.simulation import AgentSociety

async def main():
    ray.init(logging_level=logging.INFO)
    config = load_config_from_file(
        filepath="config.yaml",
        config_type=Config,
    )
    config = default(config) # This is necessary when using the default cityagent implementation
    agentsociety = AgentSociety(config)
    await agentsociety.init()
    await agentsociety.run()
    await agentsociety.close()
    ray.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
