import json
import psycopg
from typing import Dict, List, Any, Optional
import pandas as pd
import asyncio

from firmagentsql.config import DEFAULT_CONFIG, QueryConfig


class EnterpriseDataQuerier:
    def __init__(self, config: QueryConfig = None):
        """
        初始化数据库连接

        Args:
            config: 数据库配置对象（可选，默认使用配置文件）
        """
        self.config = config or DEFAULT_CONFIG
        self.conn = None

    async def connect(self):
        """建立数据库连接"""
        try:
            self.conn = await psycopg.AsyncConnection.connect(self.config.pgsql_dsn)
            print("数据库连接成功")
        except Exception as e:
            print(f"数据库连接失败: {e}")
            print(f"使用的连接配置: {self.config.pgsql_dsn}")
            raise

    async def disconnect(self):
        """关闭数据库连接"""
        if self.conn:
            await self.conn.close()
        print("数据库连接已关闭")

    async def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """执行SQL查询"""
        async with self.conn.cursor() as cursor:
            await cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = await cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]

    def is_connected(self) -> bool:
        """检查数据库连接状态"""
        return self.conn is not None and not self.conn.closed

    async def get_experiments(self) -> List[str]:
        """获取所有实验ID列表"""
        query = "SELECT DISTINCT experiment_id FROM company_states ORDER BY experiment_id"
        results = await self.execute_query(query)
        return [row['experiment_id'] for row in results]

    async def get_experiment_steps(self, experiment_id: str) -> List[int]:
        """获取指定实验的所有步骤"""
        query = "SELECT DISTINCT step FROM company_states WHERE experiment_id = %s ORDER BY step"
        results = await self.execute_query(query, (experiment_id,))
        return [row['step'] for row in results]

    async def get_experiment_companies(self, experiment_id: str) -> List[Dict]:
        """获取指定实验的所有公司信息"""
        query = """
        SELECT DISTINCT company_id, company_name 
        FROM company_states 
        WHERE experiment_id = %s 
        ORDER BY company_id
        """
        results = await self.execute_query(query, (experiment_id,))
        return results

    async def get_company_state_by_step(self, experiment_id: str, step: int, company_id: Optional[int] = None) -> List[
        Dict]:
        """获取指定实验、步骤的企业状态（包含交易和记录）"""
        base_query = """
        SELECT 
            cs.experiment_id,
            cs.step,
            cs.company_id,
            cs.company_name,
            cs.intelligence_level,        -- 新增智能等级
            cs.inventory_system,          -- 新增库存系统
            -- 交易列表聚合
            COALESCE(
                JSON_AGG(
                    JSON_BUILD_OBJECT(
                        'Purchaser', tl.purchaser_id,
                        'Supplier', tl.supplier_id,
                        'product_name', tl.product_name,
                        'Unit_price', tl.unit_price,
                        'product_quantity', tl.product_quantity,
                        'payment_method', tl.payment_method,
                        'details', JSON_BUILD_OBJECT('payment_days', tl.payment_days),
                        'state', tl.transaction_state
                    )
                ) FILTER (WHERE tl.id IS NOT NULL), 
                '[]'::json
            ) AS transaction_list,
            -- 记录列表聚合
            COALESCE(
                JSON_AGG(
                    JSON_BUILD_OBJECT(
                        'source', cr.source_company_id,
                        'sourceName', cr.source_company_name,
                        'content', cr.raw_content::json
                    )
                ) FILTER (WHERE cr.id IS NOT NULL),
                '[]'::json
            ) AS records
        FROM company_states cs
        LEFT JOIN transaction_list tl ON cs.id = tl.state_id
        LEFT JOIN company_records cr ON cs.id = cr.state_id
        WHERE cs.experiment_id = %s AND cs.step = %s
        """

        params = [experiment_id, step]

        if company_id is not None:
            base_query += " AND cs.company_id = %s"
            params.append(company_id)

        base_query += " GROUP BY cs.id, cs.experiment_id, cs.step, cs.company_id, cs.company_name ORDER BY cs.company_id"

        return await self.execute_query(base_query, tuple(params))

    async def get_transaction_summary(self, experiment_id: str, step_range: Optional[tuple] = None) -> List[Dict]:
        """
        获取交易汇总信息

        Args:
            experiment_id: 实验ID
            step_range: 步骤范围 (start_step, end_step)，可选
        """
        query = """
        SELECT 
            step,
            purchaser_id,
            supplier_id,
            product_name,
            COUNT(*) as transaction_count,
            SUM(unit_price * CAST(product_quantity AS DECIMAL)) as total_value,
            AVG(unit_price) as avg_price
        FROM transaction_list
        WHERE experiment_id = %s
        """

        params = [experiment_id]

        if step_range:
            query += " AND step BETWEEN %s AND %s"
            params.extend(step_range)

        query += """
        GROUP BY step, purchaser_id, supplier_id, product_name
        ORDER BY step, purchaser_id, supplier_id
        """

        results = await self.execute_query(query, tuple(params))

        # 转换 Decimal 类型为 float 以支持 JSON 序列化
        for result in results:
            if result.get('total_value') is not None:
                result['total_value'] = float(result['total_value'])
            if result.get('avg_price') is not None:
                result['avg_price'] = float(result['avg_price'])

        return results

    async def get_communication_summary(self, experiment_id: str, operation_type: Optional[str] = None,
                                        include_details: bool = False, step: Optional[int] = None) -> List[Dict]:
        """
        获取通信汇总信息

        Args:
            experiment_id: 实验ID
            operation_type: 操作类型过滤，可选
            include_details: 是否包含详细对话内容
            step: 指定步骤，可选
        """
        if include_details:
            # 返回详细信息，包含具体对话内容
            query = """
            SELECT 
                cr.step,
                cr.company_id,
                cs.company_name,
                cr.source_company_id,
                cr.source_company_name,
                cr.operation_type,
                cr.timestamp_value,
                cr.raw_content,
                COUNT(*) OVER (PARTITION BY cr.step, cr.company_id, cr.source_company_id, cr.operation_type) as message_count
            FROM company_records cr
            JOIN company_states cs ON cr.state_id = cs.id
            WHERE cr.experiment_id = %s
            """

            params = [experiment_id]

            if operation_type:
                query += " AND cr.operation_type = %s"
                params.append(operation_type)

            if step is not None:
                query += " AND cr.step = %s"
                params.append(step)

            query += """
            ORDER BY cr.step, cr.company_id, cr.source_company_id, cr.timestamp_value
            """

            results = await self.execute_query(query, tuple(params))

            # 解析和格式化详细内容
            for record in results:
                if record['raw_content']:
                    try:
                        content_data = record['raw_content']
                        if isinstance(content_data, dict) and 'content' in content_data:
                            # 解析content字段中的JSON字符串
                            content_str = content_data['content']
                            if isinstance(content_str, str):
                                try:
                                    parsed_content = json.loads(content_str)
                                    record['detail'] = {
                                        'operation_type': record['operation_type'],
                                        'timestamp': content_data.get('timestamp'),
                                        'day': content_data.get('day'),
                                        't': content_data.get('t'),
                                        'content': parsed_content
                                    }
                                except json.JSONDecodeError:
                                    # 如果不是JSON格式，直接使用原始内容
                                    record['detail'] = {
                                        'operation_type': record['operation_type'],
                                        'timestamp': content_data.get('timestamp'),
                                        'day': content_data.get('day'),
                                        't': content_data.get('t'),
                                        'content': content_str
                                    }
                            else:
                                record['detail'] = {
                                    'operation_type': record['operation_type'],
                                    'timestamp': content_data.get('timestamp'),
                                    'day': content_data.get('day'),
                                    't': content_data.get('t'),
                                    'content': content_str
                                }
                        else:
                            record['detail'] = {
                                'operation_type': record['operation_type'],
                                'content': content_data
                            }
                    except Exception as e:
                        record['detail'] = {
                            'operation_type': record['operation_type'],
                            'error': f"解析内容时出错: {str(e)}",
                            'raw_content': record['raw_content']
                        }
                else:
                    record['detail'] = {
                        'operation_type': record['operation_type'],
                        'content': None
                    }

            return results
        else:
            # 原有的汇总逻辑
            query = """
            SELECT 
                step,
                company_id,
                source_company_id,
                operation_type,
                COUNT(*) as message_count
            FROM company_records
            WHERE experiment_id = %s
            """

            params = [experiment_id]

            if operation_type:
                query += " AND operation_type = %s"
                params.append(operation_type)

            if step is not None:
                query += " AND step = %s"
                params.append(step)

            query += """
            GROUP BY step, company_id, source_company_id, operation_type
            ORDER BY step, company_id, source_company_id
            """

            return await self.execute_query(query, tuple(params))

    async def get_company_transactions_by_step(self, experiment_id: str, company_name: str, step: int) -> List[Dict]:
        """
        获取指定实验、公司、步骤的所有交易列表

        Args:
            experiment_id: 实验ID
            company_name: 公司名称
            step: 步骤

        Returns:
            包含交易详情的列表
        """
        query = """
        SELECT 
            tl.id,
            tl.experiment_id,
            tl.step,
            tl.company_id,
            cs.company_name,
            tl.purchaser_id,
            tl.supplier_id,
            tl.product_name,
            tl.unit_price,
            tl.product_quantity,
            tl.payment_method,
            tl.payment_days,
            tl.transaction_state,
            tl.created_at
        FROM transaction_list tl
        JOIN company_states cs ON tl.state_id = cs.id
        WHERE tl.experiment_id = %s 
            AND cs.company_name = %s 
            AND tl.step = %s
        ORDER BY tl.id
        """

        results = await self.execute_query(query, (experiment_id, company_name, step))

        # 计算交易总价值
        for transaction in results:
            if transaction['unit_price'] and transaction['product_quantity']:
                try:
                    quantity = float(transaction['product_quantity'])
                    price = float(transaction['unit_price'])
                    transaction['total_value'] = quantity * price
                except (ValueError, TypeError):
                    transaction['total_value'] = None
            else:
                transaction['total_value'] = None

        return results

    async def export_to_json(self, experiment_id: str, output_file: str):
        """
        将指定实验的数据导出为JSON文件

        Args:
            experiment_id: 实验ID
            output_file: 输出文件路径
        """
        steps = await self.get_experiment_steps(experiment_id)
        all_data = []

        for step in steps:
            step_data = await self.get_company_state_by_step(experiment_id, step)
            all_data.extend(step_data)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2, default=str)

        print(f"数据已导出到: {output_file}")

    async def get_company_records_by_step(self, experiment_id: str, company_name: str, step: int) -> List[Dict]:
        """
        获取指定实验、公司、步骤的所有记录和内容

        Args:
            experiment_id: 实验ID
            company_name: 公司名称
            step: 步骤

        Returns:
            包含记录详情的列表
        """
        query = """
        SELECT 
            cr.id,
            cr.experiment_id,
            cr.step,
            cr.company_id,
            cs.company_name,
            cr.source_company_id,
            cr.source_company_name,
            cr.operation_type,
            cr.timestamp_value,
            cr.raw_content,
            cr.created_at
        FROM company_records cr
        JOIN company_states cs ON cr.state_id = cs.id
        WHERE cr.experiment_id = %s 
            AND cs.company_name = %s 
            AND cr.step = %s
        ORDER BY cr.timestamp_value, cr.id
        """

        results = await self.execute_query(query, (experiment_id, company_name, step))

        # 解析 raw_content JSON 字段
        for record in results:
            if record['raw_content']:
                try:
                    record['content_parsed'] = record['raw_content']
                except Exception as e:
                    record['content_parsed'] = None
                    print(f"解析记录内容时出错: {e}")

        return results

    async def export_to_csv(self, experiment_id: str, output_prefix: str):
        """
        将指定实验的数据导出为CSV文件

        Args:
            experiment_id: 实验ID
            output_prefix: 输出文件前缀
        """
        # 导出企业状态
        query = "SELECT * FROM company_states WHERE experiment_id = %s ORDER BY step, company_id"
        results = await self.execute_query(query, (experiment_id,))
        df_states = pd.DataFrame(results)
        df_states.to_csv(f"{output_prefix}_states.csv", index=False, encoding='utf-8')

        # 导出交易列表
        query = "SELECT * FROM transaction_list WHERE experiment_id = %s ORDER BY step, company_id"
        results = await self.execute_query(query, (experiment_id,))
        if results:
            df_transactions = pd.DataFrame(results)
            df_transactions.to_csv(f"{output_prefix}_transactions.csv", index=False, encoding='utf-8')

        # 导出记录
        query = "SELECT * FROM company_records WHERE experiment_id = %s ORDER BY step, company_id, timestamp_value"
        results = await self.execute_query(query, (experiment_id,))
        if results:
            df_records = pd.DataFrame(results)
            df_records.to_csv(f"{output_prefix}_records.csv", index=False, encoding='utf-8')

        print(f"CSV文件已导出，前缀: {output_prefix}")


async def main():
    """主函数示例"""
    # 使用配置文件中的数据库连接
    querier = EnterpriseDataQuerier()

    try:
        # 连接数据库
        await querier.connect()

        # 查询示例
        print("=== 所有实验列表 ===")
        experiments = await querier.get_experiments()
        for exp in experiments:
            print(f"实验ID: {exp}")

        if experiments:
            exp_id = experiments[0]  # 使用第一个实验
            print(f"\n=== 实验 {exp_id} 的详细信息 ===")

            # 获取步骤列表
            steps = await querier.get_experiment_steps(exp_id)
            print(f"步骤列表: {steps}")

            # 获取公司列表
            companies = await querier.get_experiment_companies(exp_id)
            print(f"公司列表: {companies}")

            # 获取第一步的数据
            if steps:
                step_data = await querier.get_company_state_by_step(exp_id, steps[0])
                print(f"\n第{steps[0]}步数据:")
                for company_data in step_data:
                    print(f"  公司: {company_data['company_name']}")
                    print(f"  交易数量: {len(company_data['transaction_list'])}")
                    print(f"  记录数量: {len(company_data['records'])}")

            # 获取交易汇总
            print(f"\n=== 交易汇总 ===")
            transaction_summary = await querier.get_transaction_summary(exp_id)
            for trans in transaction_summary[:5]:  # 显示前5条
                print(
                    f"  步骤{trans['step']}: {trans['purchaser_id']}→{trans['supplier_id']} {trans['product_name']} 总价值:{trans['total_value']}")

            # 查询特定公司在特定步骤的记录
            print(f"\n=== A1公司在第4步的记录 ===")
            company_records = await querier.get_company_records_by_step(exp_id, "B4", 3)
            for record in company_records:
                print(f"  记录ID: {record['id']}")
                print(f"  来源公司: {record['source_company_name']} (ID: {record['source_company_id']})")
                print(f"  操作类型: {record['operation_type']}")
                print(f"  时间戳: {record['timestamp_value']}")
                print(f"  内容: {record['content_parsed']}")
                print("  ---")

            # 查询特定公司在特定步骤的交易列表
            print(f"\n=== A1公司在第5步的交易列表 ===")
            company_transactions = await querier.get_company_transactions_by_step(exp_id, "A1", 5)
            if company_transactions:
                for transaction in company_transactions:
                    print(f"  交易ID: {transaction['id']}")
                    print(f"  购买方: {transaction['purchaser_id']}")
                    print(f"  供应方: {transaction['supplier_id']}")
                    print(f"  产品: {transaction['product_name']}")
                    print(f"  单价: {transaction['unit_price']}")
                    print(f"  数量: {transaction['product_quantity']}")
                    print(f"  总价值: {transaction['total_value']}")
                    print(f"  支付方式: {transaction['payment_method']}")
                    print(f"  支付天数: {transaction['payment_days']}")
                    print(f"  交易状态: {transaction['transaction_state']}")
                    print("  ---")
            else:
                print("  该公司在此步骤没有交易记录")
            # 导出数据
            print(f"\n=== 导出数据 ===")
            await querier.export_to_json(exp_id, f"{exp_id}_export.json")
            await querier.export_to_csv(exp_id, f"{exp_id}_export")

    except Exception as e:
        print(f"查询失败: {e}")
        print("\n注意事项:")
        print("1. 请确保 Docker 服务已启动")
        print("2. 请确保已修改 config.yaml 中的 PostgreSQL 密码")
        print("3. 请确保已运行 insert.py 插入数据")
        print(f"4. 当前使用的数据库配置: {DEFAULT_CONFIG.pgsql_dsn}")
    finally:
        # 关闭连接
        await querier.disconnect()


if __name__ == "__main__":
    asyncio.run(main())


    async def get_company_records_by_step(self, experiment_id: str, company_name: str, step: int) -> List[Dict]:
        """
        获取指定实验、公司、步骤的所有记录和内容

        Args:
            experiment_id: 实验ID
            company_name: 公司名称
            step: 步骤

        Returns:
            包含记录详情的列表
        """
        query = """
        SELECT 
            cr.id,
            cr.experiment_id,
            cr.step,
            cr.company_id,
            cs.company_name,
            cr.source_company_id,
            cr.source_company_name,
            cr.operation_type,
            cr.timestamp_value,
            cr.raw_content,
            cr.created_at
        FROM company_records cr
        JOIN company_states cs ON cr.state_id = cs.id
        WHERE cr.experiment_id = %s 
            AND cs.company_name = %s 
            AND cr.step = %s
        ORDER BY cr.timestamp_value, cr.id
        """

        results = await self.execute_query(query, (experiment_id, company_name, step))

        # 解析 raw_content JSON 字段
        for record in results:
            if record['raw_content']:
                try:
                    record['content_parsed'] = record['raw_content']
                except Exception as e:
                    record['content_parsed'] = None
                    print(f"解析记录内容时出错: {e}")

        return results


    async def get_inventory_analysis(self, experiment_id: str, step: Optional[int] = None) -> List[Dict]:
        """获取库存分析数据"""
        query = """
        SELECT 
            company_id,
            company_name,
            intelligence_level,
            inventory_system,
            step
        FROM company_states
        WHERE experiment_id = %s
        """

        params = [experiment_id]
        if step is not None:
            query += " AND step = %s"
            params.append(step)

        query += " ORDER BY step, company_id"

        return await self.execute_query(query, tuple(params))
