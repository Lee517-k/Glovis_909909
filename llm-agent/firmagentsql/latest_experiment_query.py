import pandas as pd
from typing import List, Dict, Any, Optional
import psycopg
from datetime import datetime

# 导入配置
from firmagentsql.config import DEFAULT_CONFIG, QueryConfig


class LatestExperimentQuery:
    """最新实验信息查询接口"""

    def __init__(self, config: QueryConfig = None):
        self.config = config or DEFAULT_CONFIG

    async def _execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """执行SQL查询"""
        async with await psycopg.AsyncConnection.connect(self.config.pgsql_dsn) as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                columns = [desc[0] for desc in cur.description] if cur.description else []
                rows = await cur.fetchall()
                return [dict(zip(columns, row)) for row in rows]

    async def _execute_mlflow_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """执行MLflow数据库查询"""
        # 这里需要MLflow数据库的连接字符串，通常与PostgreSQL相同或者是单独的数据库
        # 如果MLflow使用相同的数据库，可以使用相同的连接
        async with await psycopg.AsyncConnection.connect(self.config.pgsql_dsn) as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                columns = [desc[0] for desc in cur.description] if cur.description else []
                rows = await cur.fetchall()
                return [dict(zip(columns, row)) for row in rows]

    def _format_status(self, status_code: int) -> str:
        """将状态码转换为可读状态"""
        status_map = {
            0: "created",
            1: "running",
            2: "completed",
            3: "failed",
            4: "stopped"
        }
        return status_map.get(status_code, "unknown")

    async def get_latest_experiments_with_run_uuid(self, limit: int = 10) -> pd.DataFrame:
        """获取最新的实验信息，包括对应的run_uuid"""
        # 首先获取最新的实验
        query = """
        SELECT 
            id,
            name,
            status,
            cur_day,
            num_day,
            config,
            input_tokens,
            output_tokens,
            created_at as created,
            updated_at as updated
        FROM as_experiment 
        ORDER BY created_at DESC 
        LIMIT %s
        """
        results = await self._execute_query(query, (limit,))

        # 处理结果，添加格式化的状态和进度
        for result in results:
            result['status_text'] = self._format_status(result['status'])
            if result['num_day'] and result['num_day'] > 0:
                result['progress'] = round((result['cur_day'] / result['num_day']) * 100, 2)
            else:
                result['progress'] = 0

            # 生成run_name (在实验ID前加run_)
            result['run_name'] = f"run_{result['id']}"

        # 获取所有run_name，查询对应的run_uuid
        if results:
            run_names = [result['run_name'] for result in results]
            placeholders = ','.join(['%s'] * len(run_names))

            # 查询MLflow runs表获取run_uuid
            mlflow_query = f"""
            SELECT name as run_name, run_uuid 
            FROM runs 
            WHERE name IN ({placeholders})
            """

            try:
                mlflow_results = await self._execute_mlflow_query(mlflow_query, tuple(run_names))
                # 创建run_name到run_uuid的映射
                run_uuid_map = {row['run_name']: row['run_uuid'] for row in mlflow_results}

                # 将run_uuid添加到结果中
                for result in results:
                    result['run_uuid'] = run_uuid_map.get(result['run_name'], None)
            except Exception as e:
                # 如果MLflow表不存在或查询失败，设置run_uuid为None
                print(f"Warning: Could not query MLflow runs table: {e}")
                for result in results:
                    result['run_uuid'] = None

        return pd.DataFrame(results)

    async def get_run_uuid_by_experiment_id(self, exp_id: str) -> Optional[str]:
        """根据实验ID获取对应的run_uuid"""
        run_name = f"run_{exp_id}"

        mlflow_query = """
        SELECT run_uuid 
        FROM runs 
        WHERE name = %s
        """

        try:
            results = await self._execute_mlflow_query(mlflow_query, (run_name,))
            
            print("run_uuid",results,exp_id)
            if results:
                return results[0]['run_uuid']
            return None
        except Exception as e:
            print(f"Error querying MLflow runs table: {e}")
            return None

    async def get_experiment_with_run_info(self, exp_id: str, tenant_id: str = None) -> Dict[str, Any]:
        """获取实验详细信息，包括run_uuid"""
        # 获取实验基本信息
        exp_info = await self.get_experiment_by_id(exp_id, tenant_id)

        if exp_info:
            # 添加run_name和run_uuid
            exp_info['run_name'] = f"run_{exp_id}"
            exp_info['run_uuid'] = await self.get_run_uuid_by_experiment_id(exp_id)

        return exp_info

    async def get_latest_experiments(self, limit: int = 10) -> pd.DataFrame:
        """获取最新的实验信息，包括ID、Name、status、progress、Created"""
        query = """
        SELECT 
            id,
            name,
            status,
            cur_day,
            num_day,
            config,
            input_tokens,
            output_tokens,
            created_at as created,
            updated_at as updated
        FROM as_experiment 
        ORDER BY created_at DESC 
        LIMIT %s
        """
        results = await self._execute_query(query, (limit,))

        # 处理结果，添加格式化的状态和进度
        for result in results:
            result['status_text'] = self._format_status(result['status'])
            if result['num_day'] and result['num_day'] > 0:
                result['progress'] = round((result['cur_day'] / result['num_day']) * 100, 2)
            else:
                result['progress'] = 0

        return pd.DataFrame(results)

    async def get_experiment_by_id(self, exp_id: str, tenant_id: str = None) -> Dict[str, Any]:
        """根据实验ID获取特定实验的详细信息"""
        if tenant_id:
            query = """
            SELECT 
                tenant_id,
                id,
                name,
                status,
                cur_day,
                num_day,
                cur_t,
                config,
                input_tokens,
                output_tokens,
                error,
                created_at as created,
                updated_at as updated
            FROM as_experiment 
            WHERE tenant_id = %s AND id = %s
            """
            params = (tenant_id, exp_id)
        else:
            query = """
            SELECT 
                tenant_id,
                id,
                name,
                status,
                cur_day,
                num_day,
                cur_t,
                config,
                input_tokens,
                output_tokens,
                error,
                created_at as created,
                updated_at as updated
            FROM as_experiment 
            WHERE id = %s
            """
            params = (exp_id,)

        results = await self._execute_query(query, params)
        if results:
            result = results[0]
            result['status_text'] = self._format_status(result['status'])
            if result['num_day'] and result['num_day'] > 0:
                result['progress'] = round((result['cur_day'] / result['num_day']) * 100, 2)
            else:
                result['progress'] = 0
            return result
        return {}

    async def get_running_experiments(self) -> pd.DataFrame:
        """获取正在运行的实验"""
        query = """
        SELECT 
            id,
            name,
            status,
            cur_day,
            num_day,
            config,
            input_tokens,
            output_tokens,
            created_at as created
        FROM as_experiment 
        WHERE status = 1
        ORDER BY created_at DESC
        """
        results = await self._execute_query(query)

        # 处理结果
        for result in results:
            result['status_text'] = self._format_status(result['status'])
            if result['num_day'] and result['num_day'] > 0:
                result['progress'] = round((result['cur_day'] / result['num_day']) * 100, 2)
            else:
                result['progress'] = 0

        return pd.DataFrame(results)

    async def get_completed_experiments(self, limit: int = 20) -> pd.DataFrame:
        """获取已完成的实验"""
        query = """
        SELECT 
            id,
            name,
            status,
            cur_day,
            num_day,
            config,
            input_tokens,
            output_tokens,
            created_at as created,
            updated_at as updated
        FROM as_experiment 
        WHERE status = 2
        ORDER BY created_at DESC 
        LIMIT %s
        """
        results = await self._execute_query(query, (limit,))

        # 处理结果
        for result in results:
            result['status_text'] = self._format_status(result['status'])
            if result['num_day'] and result['num_day'] > 0:
                result['progress'] = round((result['cur_day'] / result['num_day']) * 100, 2)
            else:
                result['progress'] = 0

        return pd.DataFrame(results)

    async def get_experiment_statistics(self) -> Dict[str, Any]:
        """获取实验统计信息"""
        stats = {}

        # 总实验数
        query = "SELECT COUNT(*) as total_count FROM as_experiment"
        result = await self._execute_query(query)
        stats['total_experiments'] = result[0]['total_count'] if result else 0

        # 按状态统计
        query = """
        SELECT status, COUNT(*) as count 
        FROM as_experiment 
        GROUP BY status
        """
        results = await self._execute_query(query)
        stats['by_status'] = {self._format_status(row['status']): row['count'] for row in results}

        # 今日创建的实验数
        query = """
        SELECT COUNT(*) as today_count 
        FROM as_experiment 
        WHERE DATE(created_at) = CURRENT_DATE
        """
        result = await self._execute_query(query)
        stats['today_experiments'] = result[0]['today_count'] if result else 0

        return stats

    async def search_experiments_by_name(self, name_pattern: str, limit: int = 10) -> pd.DataFrame:
        """根据名称模式搜索实验"""
        query = """
        SELECT 
            id,
            name,
            status,
            cur_day,
            num_day,
            config,
            input_tokens,
            output_tokens,
            created_at as created,
            updated_at as updated
        FROM as_experiment 
        WHERE name ILIKE %s
        ORDER BY created_at DESC 
        LIMIT %s
        """
        params = (f"%{name_pattern}%", limit)
        results = await self._execute_query(query, params)

        # 处理结果
        for result in results:
            result['status_text'] = self._format_status(result['status'])
            if result['num_day'] and result['num_day'] > 0:
                result['progress'] = round((result['cur_day'] / result['num_day']) * 100, 2)
            else:
                result['progress'] = 0

        return pd.DataFrame(results)

    def export_to_csv(self, df: pd.DataFrame, filename: str = "latest_experiments") -> str:
        """导出实验数据到CSV文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = f"{filename}_{timestamp}.csv"
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        return filepath

    def format_experiment_info(self, exp_data: Dict[str, Any]) -> str:
        """格式化实验信息为可读字符串"""
        if not exp_data:
            return "实验不存在"

        input_tokens = exp_data.get('input_tokens', 0)
        output_tokens = exp_data.get('output_tokens', 0)
        total_tokens = input_tokens + output_tokens

        return f"""
实验信息:
- ID: {exp_data.get('id', 'N/A')}
- 名称: {exp_data.get('name', 'N/A')}
- 状态: {exp_data.get('status_text', 'N/A')} ({exp_data.get('status', 'N/A')})
- 进度: {exp_data.get('progress', 'N/A')}% ({exp_data.get('cur_day', 0)}/{exp_data.get('num_day', 0)} 天)
- Input Tokens: {input_tokens:,}
- Output Tokens: {output_tokens:,}
- Total Tokens: {total_tokens:,}
- 创建时间: {exp_data.get('created', 'N/A')}
- 更新时间: {exp_data.get('updated', 'N/A')}
        """.strip()

    async def get_metric_value_by_run_uuid_step_key(self, run_uuid: str, step: int, key: str) -> Optional[float]:
        """通过run_uuid、step和key查询metric的value

        Args:
            run_uuid: MLflow运行的UUID
            step: 指定的步骤
            key: 指标名称（如'accuracy', 'loss'等）

        Returns:
            指标值，如果未找到则返回None
        """
        mlflow_query = """
        SELECT value 
        FROM metrics 
        WHERE run_uuid = %s AND step = %s AND key = %s
        ORDER BY timestamp DESC
        LIMIT 1
        """

        try:
            results = await self._execute_mlflow_query(mlflow_query, (run_uuid, step, key))
            if results:
                return results[0]['value']
            return None
        except Exception as e:
            print(f"Error querying metric value: {e}")
            return None

    async def get_metrics_by_run_uuid_and_step(self, run_uuid: str, step: int) -> Dict[str, float]:
        """获取指定run_uuid和step的所有metrics

        Args:
            run_uuid: MLflow运行的UUID
            step: 指定的步骤

        Returns:
            包含所有指标的字典，格式为 {key: value}
        """
        mlflow_query = """
        SELECT key, value 
        FROM metrics 
        WHERE run_uuid = %s AND step = %s
        ORDER BY timestamp DESC
        """

        try:
            results = await self._execute_mlflow_query(mlflow_query, (run_uuid, step))
            return {row['key']: row['value'] for row in results}
        except Exception as e:
            print(f"Error querying metrics: {e}")
            return {}

    async def get_metric_history_by_run_uuid_key(self, run_uuid: str, key: str) -> pd.DataFrame:
        """获取指定run_uuid和key的完整历史记录

        Args:
            run_uuid: MLflow运行的UUID
            key: 指标名称

        Returns:
            包含step、value、timestamp的DataFrame
        """
        mlflow_query = """
        SELECT step, value, timestamp 
        FROM metrics 
        WHERE run_uuid = %s AND key = %s
        ORDER BY step ASC
        """

        try:
            results = await self._execute_mlflow_query(mlflow_query, (run_uuid, key))
            return pd.DataFrame(results)
        except Exception as e:
            print(f"Error querying metric history: {e}")
            return pd.DataFrame()

    async def get_latest_metric_value_by_run_uuid_key(self, run_uuid: str, key: str) -> Optional[Dict[str, Any]]:
        """获取指定run_uuid和key的最新metric值

        Args:
            run_uuid: MLflow运行的UUID
            key: 指标名称

        Returns:
            包含step、value、timestamp的字典，如果未找到则返回None
        """
        mlflow_query = """
        SELECT step, value, timestamp 
        FROM metrics 
        WHERE run_uuid = %s AND key = %s
        ORDER BY step DESC, timestamp DESC
        LIMIT 1
        """

        try:
            results = await self._execute_mlflow_query(mlflow_query, (run_uuid, key))
            if results:
                return results[0]
            return None
        except Exception as e:
            print(f"Error querying latest metric value: {e}")
            return None

    async def get_param_value_by_run_uuid_key(self, run_uuid: str, key: str) -> Optional[str]:
        """通过run_uuid和key查询param的value

        Args:
            run_uuid: MLflow运行的UUID
            key: 参数名称（如'learning_rate', 'batch_size'等）

        Returns:
            参数值，如果未找到则返回None
        """
        mlflow_query = """
        SELECT value 
        FROM params 
        WHERE run_uuid = %s AND key = %s
        """

        try:
            results = await self._execute_mlflow_query(mlflow_query, (run_uuid, key))
            if results:
                return results[0]['value']
            return None
        except Exception as e:
            print(f"Error querying param value: {e}")
            return None

    async def get_all_params_by_run_uuid(self, run_uuid: str) -> Dict[str, str]:
        """获取指定run_uuid的所有参数

        Args:
            run_uuid: MLflow运行的UUID

        Returns:
            包含所有参数的字典，格式为 {key: value}
        """
        mlflow_query = """
        SELECT key, value 
        FROM params 
        WHERE run_uuid = %s
        ORDER BY key
        """

        try:
            results = await self._execute_mlflow_query(mlflow_query, (run_uuid,))
            return {row['key']: row['value'] for row in results}
        except Exception as e:
            print(f"Error querying params: {e}")
            return {}

    async def search_params_by_key_pattern(self, key_pattern: str, limit: int = 50) -> pd.DataFrame:
        """根据key模式搜索参数

        Args:
            key_pattern: 参数名称模式（支持SQL LIKE语法）
            limit: 返回结果的最大数量

        Returns:
            包含run_uuid、key、value的DataFrame
        """
        mlflow_query = """
        SELECT run_uuid, key, value 
        FROM params 
        WHERE key LIKE %s
        ORDER BY key, run_uuid
        LIMIT %s
        """

        try:
            results = await self._execute_mlflow_query(mlflow_query, (f"%{key_pattern}%", limit))
            return pd.DataFrame(results)
        except Exception as e:
            print(f"Error searching params: {e}")
            return pd.DataFrame()

    async def get_experiment_params_by_exp_id(self, exp_id: str) -> Dict[str, str]:
        """根据实验ID获取对应的参数（通过run_uuid）

        Args:
            exp_id: 实验ID

        Returns:
            包含所有参数的字典，格式为 {key: value}
        """
        # 首先获取run_uuid
        run_uuid = await self.get_run_uuid_by_experiment_id(exp_id)
        if run_uuid:
            return await self.get_all_params_by_run_uuid(run_uuid)
        return {}

    async def get_company_intelligence_distribution(self, exp_id: str) -> Dict[str, Any]:
        """获取企业智能等级分布（仅查询step0，包含每个等级的企业列表）"""
        # 查询step0的企业智能等级分布和企业列表
        query = """
        SELECT 
            intelligence_level,
            company_id,
            company_name,
            COUNT(*) OVER (PARTITION BY intelligence_level) as company_count
        FROM company_states
        WHERE experiment_id = %s AND step = 0
        ORDER BY intelligence_level, company_id
        """

        results = await self._execute_query(query, (exp_id,))

        # 按智能等级分组企业
        intelligence_groups = {}
        total_companies = 0

        for result in results:
            intelligence_level = result['intelligence_level']
            if intelligence_level not in intelligence_groups:
                intelligence_groups[intelligence_level] = {
                    'company_count': result['company_count'],
                    'companies': []
                }

            intelligence_groups[intelligence_level]['companies'].append({
                'company_id': result['company_id'],
                'company_name': result['company_name']
            })

        # 计算总企业数
        total_companies = sum(group['company_count'] for group in intelligence_groups.values())

        # 构建返回结果
        intelligence_distribution = []
        for level in sorted(intelligence_groups.keys()):
            group = intelligence_groups[level]
            intelligence_distribution.append({
                'intelligence_level': level,
                'company_count': group['company_count'],
                'companies': group['companies']
            })

        return {
            'step': 0,  # 明确标识查询的是step0
            'intelligence_distribution': intelligence_distribution,
            'total_companies': total_companies
        }

    async def get_inventory_summary(self, exp_id: str, step: Optional[int] = None) -> Dict[str, Any]:
        """获取库存汇总信息"""
        query = """
        SELECT 
            company_id,
            company_name,
            intelligence_level,
            inventory_system
        FROM company_states
        WHERE experiment_id = %s
        """

        params = [exp_id]
        if step is not None:
            query += " AND step = %s"
            params.append(step)

        results = await self._execute_query(query, tuple(params))

        # 处理库存数据
        inventory_summary = {
            'total_companies': len(results),
            'companies_with_inventory': 0,
            'total_products': 0,
            'total_materials': 0
        }

        for result in results:
            if result['inventory_system']:
                inventory_summary['companies_with_inventory'] += 1
                inventory = result['inventory_system']
                if 'products' in inventory:
                    inventory_summary['total_products'] += len(inventory['products'])
                if 'materials' in inventory:
                    inventory_summary['total_materials'] += len(inventory['materials'])

        return inventory_summary


# 便捷函数
async def get_latest_experiment_info(limit: int = 5, config: QueryConfig = None) -> pd.DataFrame:
    """快速获取最新实验信息"""
    query = LatestExperimentQuery(config)
    return await query.get_latest_experiments(limit)


async def get_experiment_overview(config: QueryConfig = None) -> Dict[str, Any]:
    """获取实验概览信息"""
    query = LatestExperimentQuery(config)

    overview = {}
    overview['latest_experiments'] = await query.get_latest_experiments(5)
    overview['running_experiments'] = await query.get_running_experiments()
    overview['statistics'] = await query.get_experiment_statistics()

    return overview
