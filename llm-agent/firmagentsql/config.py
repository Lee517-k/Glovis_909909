import os
import yaml
from pydantic import BaseModel
from pathlib import Path
from utils.path_utils import get_project_path
from utils.path_utils import get_project_path

class QueryConfig(BaseModel):
    """查询配置类 - 仅PostgreSQL"""
    # PostgreSQL配置
    pgsql_dsn: str = "postgresql://postgres:CHANGE_ME@localhost:5432/postgres"

    @classmethod
    def from_config_file(cls, config_path: str = "../config.yaml") -> "QueryConfig":
        """从配置文件加载PostgreSQL配置"""
        config_file = get_project_path("agentsociety-enterprise/SupplyChainAgent/enterprise/config.yaml")
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)

            # 提取PostgreSQL配置
            pgsql_config = config_data.get('env', {}).get('pgsql', {})
            pgsql_dsn = pgsql_config.get('dsn', 'postgresql://postgres:CHANGE_ME@localhost:5432/postgres')

            return cls(pgsql_dsn=pgsql_dsn)
        except Exception as e:
            print(f"读取配置文件失败: {e}，使用默认配置")
            return cls()


# 从主配置文件加载配置
DEFAULT_CONFIG = QueryConfig.from_config_file()


# 也可以手动指定配置文件路径
def load_config(config_path: str = "../config.yaml") -> QueryConfig:
    """加载配置"""
    return QueryConfig.from_config_file(config_path)
