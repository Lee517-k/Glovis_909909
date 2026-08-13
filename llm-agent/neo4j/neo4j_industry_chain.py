import json
from neo4j import GraphDatabase

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "12345678"

class IndustryChainGraph:

    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        self.driver.close()
    
    def clear_database(self):
        """清空数据库"""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
    
    def load_industry_data(self, json_file_path):
        """加载产业链数据"""
        with open(json_file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    
    def create_companies(self, data):
        """创建企业节点，包含完整的产品信息作为属性"""
        with self.driver.session() as session:
            for level, companies in data.items():
                level_num = int(level.split('_')[1])
                # 创建动态标签，如 level1_company, level2_company 等
                node_label = f"level{level_num}_company"
                
                for company in companies:
                    # 收集企业基本信息
                    product_names = []
                    product_ids = []
                    material_names = []
                    material_ids = []
                    
                    # 产品详细信息列表
                    products_info = []
                    
                    # 计算企业级别的统计信息
                    total_inventory = 0
                    total_profit_margin = 0
                    total_product_value = 0
                    total_manufacturing_cost = 0
                    product_count = len(company['main_products'])
                    terminal_product_count = 0
                    
                    for product in company['main_products']:
                        product_names.append(product['product_name'])
                        product_ids.append(product['product_id'])
                        
                        # 统计信息
                        inventory = product.get('initial_inventory', 0)
                        base_price = product.get('base_price', 0)
                        profit_margin = product.get('profit_margin', 0)
                        manufacturing_cost = product.get('manufacturing_cost', 0)
                        
                        total_inventory += inventory
                        total_profit_margin += profit_margin
                        total_product_value += base_price * inventory
                        total_manufacturing_cost += manufacturing_cost
                        
                        if product.get('is_terminal_product', False):
                            terminal_product_count += 1
                        
                        # 收集原料信息
                        related_materials = []
                        for mat in product['related_materials']:
                            related_materials.append({
                                'material_name': mat['material_name'],
                                'material_id': mat['material_id']
                            })
                            if mat['material_name'] not in material_names:
                                material_names.append(mat['material_name'])
                            if mat['material_id'] not in material_ids:
                                material_ids.append(mat['material_id'])
                        
                        # 构建产品完整信息
                        product_info = {
                            'product_name': product['product_name'],
                            'product_id': product['product_id'],
                            'base_price': base_price,
                            'manufacturing_cost': manufacturing_cost,
                            'profit_margin': profit_margin,
                            'initial_inventory': inventory,
                            'product_construct': product.get('product_construct', ''),
                            'is_terminal_product': product.get('is_terminal_product', False),
                            'product_type': product.get('product_type', ''),
                            'related_materials': related_materials
                        }
                        
                        # 添加消耗率信息（仅终端产品）
                        if 'consumption_rate' in product:
                            product_info['consumption_rate'] = {
                                'daily_consumption_rate': product['consumption_rate'].get('daily_consumption_rate', 0),
                                'consumption_type': product['consumption_rate'].get('consumption_type', ''),
                                'description': product['consumption_rate'].get('description', '')
                            }
                        
                        products_info.append(product_info)
                    
                    # 收集可提供的原料信息
                    for material in company['available_materials']:
                        if material['material_name'] not in material_names:
                            material_names.append(material['material_name'])
                        if material['material_id'] not in material_ids:
                            material_ids.append(material['material_id'])
                    
                    # 计算平均值
                    avg_profit_margin = total_profit_margin / product_count if product_count > 0 else 0
                    avg_manufacturing_cost = total_manufacturing_cost / product_count if product_count > 0 else 0
                    
                    # 使用动态标签创建企业节点，包含完整产品信息
                    query = f"""
                    CREATE (c:{node_label} {{
                        name: $name,
                        level: $level,
                        level_num: $level_num,
                        
                        // 基础产品列表信息
                        product_names: $product_names,
                        product_ids: $product_ids,
                        material_names: $material_names,
                        material_ids: $material_ids,
                        
                        // 企业统计信息
                        total_inventory: $total_inventory,
                        avg_profit_margin: $avg_profit_margin,
                        avg_manufacturing_cost: $avg_manufacturing_cost,
                        total_product_value: $total_product_value,
                        product_count: $product_count,
                        terminal_product_count: $terminal_product_count,
                        
                        // 完整产品信息（JSON字符串格式）
                        products_detail: $products_detail
                    }})
                    """
                    
                    session.run(
                        query,
                        name=company['name'],
                        level=level,
                        level_num=level_num,
                        product_names=product_names,
                        product_ids=product_ids,
                        material_names=material_names,
                        material_ids=material_ids,
                        total_inventory=total_inventory,
                        avg_profit_margin=round(avg_profit_margin, 2),
                        avg_manufacturing_cost=round(avg_manufacturing_cost, 2),
                        total_product_value=round(total_product_value, 2),
                        product_count=product_count,
                        terminal_product_count=terminal_product_count,
                        products_detail=json.dumps(products_info, ensure_ascii=False)
                    )
    
    def create_supply_relationships(self, data):
        """创建供需关系"""
        with self.driver.session() as session:
            # 获取所有企业数据用于查找供需关系
            all_companies = []
            for level, companies in data.items():
                for company in companies:
                    company['level'] = level
                    all_companies.append(company)
            
            # 为每个企业的每个产品查找原料供应商
            for consumer in all_companies:
                consumer_level = int(consumer['level'].split('_')[1])
                
                for product in consumer['main_products']:
                    for required_material in product['related_materials']:
                        material_id = required_material['material_id']
                        
                        # 查找能提供这种原料的供应商
                        for supplier in all_companies:
                            supplier_level = int(supplier['level'].split('_')[1])
                            
                            # 检查是否是相邻层级且能提供所需原料
                            if (consumer_level == supplier_level + 1 and 
                                any(mat['material_id'] == material_id for mat in supplier['available_materials'])):
                                
                                # 获取供应商产品的详细信息
                                supplier_product = None
                                for sp in supplier['main_products']:
                                    if sp['product_id'] == material_id:
                                        supplier_product = sp
                                        break
                                
                                supply_price = supplier_product.get('base_price', 0) if supplier_product else 0
                                supply_inventory = supplier_product.get('initial_inventory', 0) if supplier_product else 0
                                supply_profit_margin = supplier_product.get('profit_margin', 0) if supplier_product else 0
                                
                                # 计算使用比例
                                usage_ratio = self.extract_usage_ratio(
                                    product.get('product_construct', ''), 
                                    required_material['material_name']
                                )
                                
                                # 创建企业间供需关系
                                session.run(
                                    """
                                    MATCH (supplier {name: $supplier_name})
                                    MATCH (consumer {name: $consumer_name})
                                    CREATE (supplier)-[:SUPPLIES {
                                        material_id: $material_id,
                                        material_name: $material_name,
                                        for_product_name: $product_name,
                                        for_product_id: $product_id,
                                        supply_price: $supply_price,
                                        available_inventory: $supply_inventory,
                                        supplier_profit_margin: $supplier_profit_margin,
                                        usage_ratio: $usage_ratio,
                                        cost_contribution: $cost_contribution,
                                        product_construct: $product_construct
                                    }]->(consumer)
                                    """,
                                    supplier_name=supplier['name'],
                                    consumer_name=consumer['name'],
                                    material_id=material_id,
                                    material_name=required_material['material_name'],
                                    product_name=product['product_name'],
                                    product_id=product['product_id'],
                                    supply_price=supply_price,
                                    supply_inventory=supply_inventory,
                                    supplier_profit_margin=supply_profit_margin,
                                    usage_ratio=usage_ratio,
                                    cost_contribution=round(supply_price * usage_ratio / 100, 2),
                                    product_construct=product.get('product_construct', '')
                                )
    
    def extract_usage_ratio(self, product_construct, material_name):
        """从产品配方中提取原料使用比例"""
        if not product_construct or material_name not in product_construct:
            return 0
        
        try:
            # 解析类似 "原料1*74%+原料4*26%" 的格式
            if product_construct == "无需原料":
                return 0
            
            parts = product_construct.split('+')
            for part in parts:
                if material_name in part and '*' in part and '%' in part:
                    ratio_str = part.split('*')[1].replace('%', '')
                    return float(ratio_str)
        except Exception as e:
            print(f"解析配方出错: {product_construct}, 原料: {material_name}, 错误: {e}")
        
        return 0
    
    def build_graph(self, json_file_path):
        """构建完整的图数据库"""
        print("正在清空数据库...")
        self.clear_database()
        
        print("正在加载数据...")
        data = self.load_industry_data(json_file_path)
        
        print("正在创建企业节点...")
        self.create_companies(data)
        
        print("正在创建供需关系...")
        self.create_supply_relationships(data)
        
        print("图数据库构建完成！")
    
    def get_graph_statistics(self):
        """获取图统计信息"""
        with self.driver.session() as session:
            # 统计企业节点数量
            company_count = session.run("""
                MATCH (n) 
                WHERE any(label IN labels(n) WHERE label CONTAINS 'company')
                RETURN count(n) as count
            """).single()["count"]
            
            # 统计供需关系数量
            supply_rel_count = session.run("MATCH ()-[r:SUPPLIES]->() RETURN count(r) as count").single()["count"]
            
            # 统计总产品数量
            total_products = session.run("""
                MATCH (c) 
                WHERE any(label IN labels(c) WHERE label CONTAINS 'company')
                RETURN sum(c.product_count) as total
            """).single()["total"] or 0
            
            # 统计终端产品数量
            terminal_products = session.run("""
                MATCH (c) 
                WHERE any(label IN labels(c) WHERE label CONTAINS 'company')
                RETURN sum(c.terminal_product_count) as total
            """).single()["total"] or 0
            
            # 统计总库存和总价值
            inventory_value_stats = session.run("""
                MATCH (c) 
                WHERE any(label IN labels(c) WHERE label CONTAINS 'company')
                RETURN sum(c.total_inventory) as total_inventory,
                       sum(c.total_product_value) as total_value,
                       avg(c.avg_profit_margin) as overall_avg_profit
            """).single()
            
            # 动态获取所有层级标签
            labels_result = session.run("""
                CALL db.labels() YIELD label
                WHERE label CONTAINS 'level' AND label CONTAINS 'company'
                RETURN label
                ORDER BY label
            """)
            
            level_stats = []
            for record in labels_result:
                label = record["label"]
                # 查询该层级的详细统计信息
                query = f"""
                    MATCH (c:{label}) 
                    RETURN '{label}' as label, 
                           count(c) as company_count,
                           sum(c.product_count) as product_count,
                           sum(c.terminal_product_count) as terminal_count,
                           avg(c.avg_profit_margin) as avg_profit,
                           sum(c.total_inventory) as total_inventory,
                           sum(c.total_product_value) as total_value,
                           avg(c.avg_manufacturing_cost) as avg_cost
                """
                result = session.run(query).single()
                if result and result["company_count"] > 0:
                    level_stats.append({
                        "label": result["label"],
                        "company_count": result["company_count"],
                        "product_count": result["product_count"] or 0,
                        "terminal_product_count": result["terminal_count"] or 0,
                        "avg_profit_margin": round(result["avg_profit"] or 0, 2),
                        "avg_manufacturing_cost": round(result["avg_cost"] or 0, 2),
                        "total_inventory": result["total_inventory"] or 0,
                        "total_value": round(result["total_value"] or 0, 2)
                    })
            
            return {
                "total_companies": company_count,
                "total_products": total_products,
                "total_supply_relationships": supply_rel_count,
                "terminal_products": terminal_products,
                "total_inventory": inventory_value_stats["total_inventory"] or 0,
                "total_product_value": round(inventory_value_stats["total_value"] or 0, 2),
                "overall_avg_profit_margin": round(inventory_value_stats["overall_avg_profit"] or 0, 2),
                "level_statistics": level_stats
            }
    
    def query_company_products(self, company_name):
        """查询特定企业的产品详细信息"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (c {name: $company_name})
                RETURN c.name as name, c.level as level, c.products_detail as products_detail
                """,
                company_name=company_name
            ).single()
            
            if result:
                products_detail = json.loads(result["products_detail"])
                return {
                    "company_name": result["name"],
                    "level": result["level"],
                    "products": products_detail
                }
            return None

# 使用示例
def main():
    # 创建图数据库实例
    graph = IndustryChainGraph(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    try:
        # 构建图数据库
        graph.build_graph("industry_test.json")
        
        # 获取统计信息
        stats = graph.get_graph_statistics()
        print("\n=== 图数据库统计信息 ===")
        print(f"企业总数: {stats['total_companies']}")
        print(f"产品总数: {stats['total_products']}")
        print(f"供需关系总数: {stats['total_supply_relationships']}")
        print(f"终端产品数量: {stats['terminal_products']}")
        print(f"总库存量: {stats['total_inventory']}")
        print(f"总产品价值: {stats['total_product_value']}元")
        print(f"整体平均利润率: {stats['overall_avg_profit_margin']}%")
        print("\n各层级统计:")
        for level_stat in stats['level_statistics']:
            print(f"  {level_stat['label']}: {level_stat['company_count']}家企业")
            print(f"    产品数量: {level_stat['product_count']}")
            print(f"    终端产品: {level_stat['terminal_product_count']}")
            print(f"    平均利润率: {level_stat['avg_profit_margin']}%")
            print(f"    平均制造成本: {level_stat['avg_manufacturing_cost']}元")
            print(f"    总库存量: {level_stat['total_inventory']}")
            print(f"    总产品价值: {level_stat['total_value']}元")
        
        # 示例：查询特定企业的产品信息
        print("\n=== 企业A1的产品详情 ===")
        company_info = graph.query_company_products("A1")
        if company_info:
            print(f"企业: {company_info['company_name']} ({company_info['level']})")
            for product in company_info['products']:
                print(f"  产品: {product['product_name']} (ID: {product['product_id']})")
                print(f"    基础价格: {product['base_price']}元")
                print(f"    制造成本: {product['manufacturing_cost']}元")
                print(f"    利润率: {product['profit_margin']}%")
                print(f"    库存: {product['initial_inventory']}")
                print(f"    配方: {product['product_construct']}")
                if product['is_terminal_product'] and 'consumption_rate' in product:
                    print(f"    消耗率: {product['consumption_rate']['daily_consumption_rate']}% ({product['consumption_rate']['consumption_type']})")
        
    finally:
        graph.close()

if __name__ == "__main__":
    main()