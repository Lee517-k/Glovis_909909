import json
import psycopg
from typing import Dict, Any
from pathlib import Path
import asyncio

# 导入配置（仿照 firmagentsql/latest_experiment_query.py 的方式）
from firmagentsql.config import DEFAULT_CONFIG, QueryConfig


class EnterpriseDataInserter:
    def __init__(self, config: QueryConfig = None):
        """
        初始化数据库连接

        Args:
            config: 数据库配置对象（可选，默认使用配置文件）
        """
        self.config = config or DEFAULT_CONFIG
        self.conn = None
        self.cursor = None

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

    async def create_tables(self):
        """创建数据库表结构"""
        create_tables_sql = """
        -- 企业状态主表
        CREATE TABLE IF NOT EXISTS company_states (
            id SERIAL PRIMARY KEY,
            experiment_id VARCHAR(100) NOT NULL,
            step INTEGER NOT NULL,
            company_id INTEGER NOT NULL,
            company_name VARCHAR(100) NOT NULL,
            level INTEGER,               -- 新增企业层级字段
            intelligence_level INTEGER,  -- 新增智能等级字段
            inventory_system JSONB,      -- 新增库存系统字段
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(experiment_id, step, company_id)
        );

        -- 交易列表表
        CREATE TABLE IF NOT EXISTS transaction_list (
            id SERIAL PRIMARY KEY,
            state_id INTEGER REFERENCES company_states(id) ON DELETE CASCADE,
            experiment_id VARCHAR(100) NOT NULL,
            step INTEGER NOT NULL,
            company_id INTEGER NOT NULL,
            purchaser_id VARCHAR(50),
            supplier_id VARCHAR(50),
            product_name VARCHAR(100),
            unit_price DECIMAL(10,2),
            product_quantity VARCHAR(50),
            payment_method VARCHAR(50),
            payment_days INTEGER,
            transaction_state VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 记录表
        CREATE TABLE IF NOT EXISTS company_records (
            id SERIAL PRIMARY KEY,
            state_id INTEGER REFERENCES company_states(id) ON DELETE CASCADE,
            experiment_id VARCHAR(100) NOT NULL,
            step INTEGER NOT NULL,
            company_id INTEGER NOT NULL,
            source_company_id VARCHAR(50),
            source_company_name VARCHAR(100),
            operation_type VARCHAR(50),
            timestamp_value BIGINT,
            raw_content JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 创建索引
        CREATE INDEX IF NOT EXISTS idx_company_states_exp_step ON company_states(experiment_id, step);
        CREATE INDEX IF NOT EXISTS idx_company_states_level ON company_states(level);
        CREATE INDEX IF NOT EXISTS idx_company_states_intelligence ON company_states(intelligence_level);
        CREATE INDEX IF NOT EXISTS idx_inventory_system_gin ON company_states USING GIN (inventory_system);
        CREATE INDEX IF NOT EXISTS idx_transaction_list_exp_step ON transaction_list(experiment_id, step);
        CREATE INDEX IF NOT EXISTS idx_company_records_exp_step ON company_records(experiment_id, step);
        CREATE INDEX IF NOT EXISTS idx_company_records_operation ON company_records(operation_type);
        """

        async with self.conn.cursor() as cursor:
            await cursor.execute(create_tables_sql)
            await self.conn.commit()
            print("数据库表创建成功")
        print("数据库表结构创建完成")

    async def insert_state_data(self, experiment_id: str, state_data: Dict[str, Any]):
        """插入单个状态数据"""
        step = state_data['step']
        company_id = state_data['id']
        company_name = state_data['company_name']
        # 构建inventory_system从state数据
        # 修复后的逻辑
        inventory_system = {'products': {}, 'materials': {}}
        # 如果state_data中直接包含inventory_system，优先使用
        if 'inventory_system' in state_data and state_data['inventory_system']:
            inventory_system = state_data['inventory_system']
        else:
            # 否则从product_stocks和available_materials构建
            product_stocks = state_data.get('product_stocks', [])
            available_materials = state_data.get('available_materials', [])

            # 使用available_materials判断哪些是材料
            material_names = {mat.get('product_name', '') for mat in available_materials}

            for stock in product_stocks:
                product_name = stock.get('name', stock.get('product_name', ''))  # 修复字段名
                quantity = stock.get('stock', stock.get('quantity', 0))  # 修复字段名

                if product_name in material_names:
                    inventory_system['materials'][str(stock.get('product_id', ''))] = {
                        'product_name': product_name,
                        'quantity': quantity
                    }
                else:
                    inventory_system['products'][str(stock.get('product_id', ''))] = {
                        'product_name': product_name,
                        'quantity': quantity
                    }

        # 获取intelligence_level（默认值为1）
        intelligence_level = state_data.get('intelligence_level', 1)

        # 获取level（默认值为1）
        level = state_data.get('level', 1)
        print(f"Inserting level to database: {level} for company {company_name}")

        async with self.conn.cursor() as cursor:
            # 插入企业状态
            insert_state_sql = """
            INSERT INTO company_states (experiment_id, step, company_id, company_name, level, intelligence_level, inventory_system)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (experiment_id, step, company_id) DO UPDATE SET
                company_name = EXCLUDED.company_name,
                level = EXCLUDED.level,
                intelligence_level = EXCLUDED.intelligence_level,
                inventory_system = EXCLUDED.inventory_system
            RETURNING id
            """

            await cursor.execute(insert_state_sql, (
                experiment_id, step, company_id, company_name,
                level, intelligence_level, json.dumps(inventory_system) if inventory_system else None
            ))
            state_id = (await cursor.fetchone())[0]
            # 插入交易列表
            transaction_list = state_data.get('transaction_list', [])
            if transaction_list:
                for transaction in transaction_list:
                    insert_transaction_sql = """
                    INSERT INTO transaction_list (
                    
                        state_id, experiment_id, step, company_id,
                        purchaser_id, supplier_id, product_name, unit_price,
                        product_quantity, payment_method, payment_days, transaction_state
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """

                    # === 字段名统一 & 类型转换 ===
                    purchaser_id = transaction.get('purchaser') or transaction.get('Purchaser')
                    supplier_id = transaction.get('supplier') or transaction.get('Supplier')
                    purchaser_id = str(transaction.get('purchaser') or transaction.get('Purchaser') or "")
                    supplier_id = str(transaction.get('supplier') or transaction.get('Supplier') or "")
                    product_name = transaction.get('product_name')
                    trans_step = transaction.get('step')
                    trans_step = str(transaction.get('step') or transaction.get('Step') or "")

                    unit_price = str(transaction.get('unit_price') or transaction.get('Unit_price') or "0")
                    product_quantity = str(transaction.get('product_quantity') or "0")

                    payment_method = transaction.get('payment_method')
                    transaction_state = transaction.get('state')

                    # 支付天数
                    details = transaction.get('details') or {}
                    payment_days = details.get('payment_days')
                    payment_days = str(payment_days) if payment_days is not None else None

                    # === 检查是否已有完全相同的数据 ===
                    # 关键点：对可能出错的数值型字段强制 CAST，避免 varchar=int 的报错
                    check_sql = """
                    SELECT 1 FROM transaction_list
                    WHERE experiment_id=%s AND step=%s
                    AND purchaser_id=%s
                    AND supplier_id=%s
                    AND product_name=%s
                    LIMIT 1
                    """

                    await cursor.execute(check_sql, (
                        experiment_id, trans_step,
                        purchaser_id, supplier_id, product_name,
                    ))
                    exists = await cursor.fetchone()
                    # === 插入数据 ===
                    if not exists:
                        await cursor.execute(insert_transaction_sql, (
                            state_id, experiment_id, trans_step, company_id,
                            purchaser_id, supplier_id, product_name, unit_price,
                            product_quantity, payment_method, payment_days, transaction_state
                        ))

                    await self.conn.commit()
            
            records = state_data.get('record', [])
            if records:
                for record in records:
                    content = record.get('content', {})
                    operation_type = content.get('type')
                    timestamp_value = content.get('timestamp')

                    insert_record_sql = """
                    INSERT INTO company_records (
                        state_id, experiment_id, step, company_id,
                        source_company_id, source_company_name, operation_type,
                        timestamp_value, raw_content
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """

                    await cursor.execute(insert_record_sql, (
                        state_id, experiment_id, trans_step, company_id,
                        record.get('source'),
                        record.get('sourceName'),
                        operation_type,
                        timestamp_value,
                        json.dumps(content)
                    ))

            await self.conn.commit()
    async def insert_all_data(self, experiment_id: str, data_directory: str = "."):
        """插入所有状态文件的数据"""
        data_path = Path(data_directory)
        state_files = sorted(data_path.glob("state_*.json"))

        if not state_files:
            print(f"在目录 {data_directory} 中未找到 state_*.json 文件")
            return

        print(f"找到 {len(state_files)} 个状态文件")

        for state_file in state_files:
            print(f"正在处理文件: {state_file.name}")

            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state_data_list = json.load(f)  # 这是一个数组

                # 处理数组中的每个状态对象
                if isinstance(state_data_list, list):
                    for state_data in state_data_list:
                        await self.insert_state_data(experiment_id, state_data)
                else:
                    # 如果不是数组，按原来的方式处理
                    await self.insert_state_data(experiment_id, state_data_list)

                print(f"文件 {state_file.name} 处理完成")

            except Exception as e:
                print(f"处理文件 {state_file.name} 时出错: {e}")
                continue

        print(f"实验 {experiment_id} 的所有数据插入完成")


async def main():
    """主函数"""
    # 使用配置文件中的数据库连接
    inserter = EnterpriseDataInserter()

    try:
        # 连接数据库
        await inserter.connect()

        # 创建表结构
        await inserter.create_tables()

        # 插入数据（使用当前目录下的 state_*.json 文件）
        experiment_id = "enterprise_simulation_001"
        await inserter.insert_all_data(experiment_id)

        print("\n数据插入完成！")

    except Exception as e:
        print(f"插入数据失败: {e}")
        print("\n注意事项:")
        print("1. 请确保 Docker 服务已启动")
        print("2. 请确保已修改 config.yaml 中的 PostgreSQL 密码")
        print(f"3. 当前使用的数据库配置: {DEFAULT_CONFIG.pgsql_dsn}")
    finally:
        # 关闭连接
        await inserter.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
