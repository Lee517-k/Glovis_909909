import json
import random
import math
from collections import defaultdict


class IndustryChainGenerator:
    def __init__(self):
        self.companies = {}
        self.products = []
        self.total_companies = 0
        self.total_levels = 0
        self.total_products = 0

    def get_user_input(self):
        """获取用户输入参数"""
        print("=== 产业链生成器 ===")

        while True:
            try:
                self.total_companies = int(input("请输入企业总数: "))
                if self.total_companies < 4:
                    print("企业总数至少需要4家，请重新输入")
                    continue
                break
            except ValueError:
                print("请输入有效的数字")

        while True:
            try:
                self.total_levels = int(input("请输入层级数: "))
                if self.total_levels < 2:
                    print("层级数至少需要2级，请重新输入")
                    continue
                break
            except ValueError:
                print("请输入有效的数字")

        # 自动计算产品数量：企业数量的1.5-2倍，确保有足够的产品流动
        self.total_products = max(self.total_levels * 3, int(self.total_companies * 1.5))
        print(f"自动计算产品数量: {self.total_products}")

    def distribute_companies(self):
        """分配企业到各层级"""
        # 确保level1和最后一级至少有2-3个企业
        min_first_last = max(2, min(3, self.total_companies // self.total_levels))

        # 如果企业总数太少，调整最小值
        if self.total_companies < self.total_levels * 2:
            min_first_last = max(1, self.total_companies // self.total_levels)

        # 计算平均每层级的企业数量
        avg_per_level = self.total_companies // self.total_levels
        remainder = self.total_companies % self.total_levels

        # 初始化每层级企业数量
        level_counts = [avg_per_level] * self.total_levels

        # 分配剩余企业到前几个层级
        for i in range(remainder):
            level_counts[i] += 1

        # 调整level1和最后一级
        max_diff = 6  # 与其他层级最大差距

        if self.total_levels > 2:
            # 找到中间层级的最大企业数
            middle_max = max(level_counts[1:-1])

            # 计算level1和最后一级的目标数量
            target_first_last = max(min_first_last, middle_max - max_diff)

            # 计算需要重新分配的企业数量
            excess_first = max(0, level_counts[0] - target_first_last)
            excess_last = max(0, level_counts[-1] - target_first_last)

            # 如果当前数量少于目标，需要从中间层级借企业
            deficit_first = max(0, target_first_last - level_counts[0])
            deficit_last = max(0, target_first_last - level_counts[-1])

            # 设置level1和最后一级的企业数量
            level_counts[0] = target_first_last
            level_counts[-1] = target_first_last

            # 重新分配企业
            total_excess = excess_first + excess_last
            total_deficit = deficit_first + deficit_last

            if total_excess > 0:
                # 将多余的企业分配到中间层级
                middle_levels = self.total_levels - 2
                extra_per_middle = total_excess // middle_levels
                extra_remainder = total_excess % middle_levels

                for i in range(1, self.total_levels - 1):
                    level_counts[i] += extra_per_middle
                    if i - 1 < extra_remainder:
                        level_counts[i] += 1

            elif total_deficit > 0:
                # 从中间层级借企业给level1和最后一级
                middle_levels = self.total_levels - 2
                borrow_per_middle = total_deficit // middle_levels
                borrow_remainder = total_deficit % middle_levels

                for i in range(1, self.total_levels - 1):
                    borrow_amount = borrow_per_middle
                    if i - 1 < borrow_remainder:
                        borrow_amount += 1

                    # 确保中间层级至少保留1个企业
                    actual_borrow = min(borrow_amount, level_counts[i] - 1)
                    level_counts[i] -= actual_borrow

        else:
            # 只有2个层级的情况
            level_counts[0] = max(min_first_last, level_counts[0])
            level_counts[-1] = max(min_first_last, level_counts[-1])

        # 确保每个层级至少有1家企业
        for i in range(self.total_levels):
            if level_counts[i] < 1:
                level_counts[i] = 1

        # 验证并调整总数
        current_total = sum(level_counts)
        if current_total != self.total_companies:
            diff = self.total_companies - current_total

            if diff > 0:
                # 需要增加企业，优先给中间层级
                for i in range(abs(diff)):
                    if self.total_levels > 2:
                        # 给中间层级
                        level_idx = (i % (self.total_levels - 2)) + 1
                    else:
                        # 只有2层级时，随机给一个
                        level_idx = i % self.total_levels
                    level_counts[level_idx] += 1

            elif diff < 0:
                # 需要减少企业，从企业数最多的层级减少
                for i in range(abs(diff)):
                    # 找到企业数最多且不是level1和最后一级的层级
                    max_count = 0
                    max_idx = 1 if self.total_levels > 2 else 0

                    for j in range(self.total_levels):
                        # 优先从中间层级减少
                        if self.total_levels > 2 and (j == 0 or j == self.total_levels - 1):
                            continue
                        if level_counts[j] > max_count and level_counts[j] > min_first_last:
                            max_count = level_counts[j]
                            max_idx = j

                    if level_counts[max_idx] > 1:
                        level_counts[max_idx] -= 1

        return level_counts

    def generate_company_names(self, level_counts):
        """生成企业名称"""
        company_data = {}
        company_id = 1  # 添加公司ID计数器

        for level in range(1, self.total_levels + 1):
            level_key = f"level_{level}"
            company_data[level_key] = []

            # 修复：level_counts是列表，使用索引访问
            count = level_counts[level - 1]  # level从1开始，但列表索引从0开始

            for i in range(count):
                # 生成企业名称（A1, A2, A3, B1, B2, ...）
                level_letter = chr(ord('A') + level - 1)
                company_name = f"{level_letter}{i + 1}"

                company_info = {
                    "id": company_id,  # 添加公司ID字段
                    "name": company_name,
                    "level": level,  # 添加层级字段
                    "company_capacity": random.randint(30, 100),  # 产能范围：30-100
                    "initial_capital": random.randint(20000, 100000),  # 初始资金范围：20000-100000
                    "main_products": [],  # 改为产品-原料对应结构
                    "available_materials": []  # 该企业可提供的原料
                }

                company_data[level_key].append(company_info)
                company_id += 1  # 递增ID

        return company_data

    def generate_product_construct(self, related_materials):
        """根据原料生成产品配方"""
        if not related_materials:
            return "no need material"

        # 生成随机占比，确保总和为100%
        num_materials = len(related_materials)
        if num_materials == 1:
            return f"{related_materials[0]['product_name']}*100%"

        # 为多种原料生成占比
        ratios = []
        remaining = 100

        for i in range(num_materials - 1):
            # 为前n-1种原料随机分配占比
            max_ratio = min(80, remaining - (num_materials - i - 1) * 10)  # 确保每种原料至少10%
            min_ratio = max(10, remaining - (num_materials - i - 1) * 80)  # 确保每种原料最多80%
            ratio = random.randint(min_ratio, max_ratio)
            ratios.append(ratio)
            remaining -= ratio

        # 最后一种原料使用剩余占比
        ratios.append(remaining)

        # 生成配方字符串
        construct_parts = []
        for i, material in enumerate(related_materials):
            construct_parts.append(f"{material['product_name']}*{ratios[i]}%")

        return "+".join(construct_parts)

    def generate_base_prices(self):
        """根据产业链层级生成分级价格"""
        base_prices = {}

        # 计算每个层级的产品范围
        products_per_level = self.total_products // self.total_levels
        extra_products = self.total_products % self.total_levels

        current_product = 1

        for level_idx in range(self.total_levels):
            # 计算当前层级的产品数量
            products_count = products_per_level + (1 if level_idx < extra_products else 0)

            # 根据层级确定价格范围（上游便宜，下游昂贵）
            # level_1: 50-150元（原材料层）
            # level_2: 120-250元（初加工层）
            # level_3: 200-350元（深加工层）
            # level_4+: 300-500元（终端产品层）

            if level_idx == 0:  # level_1 - 原材料层
                min_price, max_price = 50, 150
            elif level_idx == 1:  # level_2 - 初加工层
                min_price, max_price = 120, 250
            elif level_idx == 2:  # level_3 - 深加工层
                min_price, max_price = 200, 350
            else:  # level_4+ - 终端产品层
                min_price, max_price = 300, 500

            # 为当前层级的所有产品生成价格
            for i in range(products_count):
                product_id = current_product + i
                base_prices[product_id] = random.randint(min_price, max_price)

            current_product += products_count

        return base_prices

    def calculate_manufacturing_cost(self, related_materials, product_construct, base_prices):
        """计算制造成本"""
        material_cost = 0  # 原料成本

        # 如果没有原材料（A级产业），设置基础生产成本
        if not related_materials or product_construct == "no need material":
            # A级产业的基础生产成本：人工、设备、能源等
            base_production_cost = random.uniform(15, 35)  # 15-35元的基础生产成本
            total_manufacturing_cost = base_production_cost
            return round(total_manufacturing_cost, 2), 0  # material_cost为0

        # 有原材料的情况
        processing_fee = random.uniform(5, 15)  # 加工费：5-15元

        # 解析产品配方并计算原料成本
        if "+" in product_construct:
            parts = product_construct.split("+")
        else:
            parts = [product_construct]

        for part in parts:
            try:
                product_name, ratio_str = part.split("*")
                ratio = float(ratio_str.replace("%", "")) / 100

                # 从product_name中提取product_id
                product_id = int(product_name.replace("product_", ""))

                # 计算该原料的成本
                if product_id in base_prices:
                    material_cost += base_prices[product_id] * ratio

            except (ValueError, IndexError) as e:
                print(f"解析配方出错: {part}, 错误: {e}")
                continue

        total_manufacturing_cost = material_cost + processing_fee
        return round(total_manufacturing_cost, 2), round(material_cost, 2)

    def generate_initial_inventory(self, product_id, company_size_factor=1.0):
        """为产品生成初始库存"""
        # 基础库存范围：100-1000件
        base_min = 100
        base_max = 1000

        # 根据公司规模因子调整库存范围
        min_inventory = int(base_min * company_size_factor)
        max_inventory = int(base_max * company_size_factor)

        # 确保库存不超过2000
        max_inventory = min(max_inventory, 2000)
        min_inventory = min(min_inventory, max_inventory)

        # 生成随机库存量
        inventory = random.randint(min_inventory, max_inventory)

        return inventory

    def get_company_size_factor(self, company_name):
        """根据公司名称获取公司规模因子"""
        # 根据公司名称的字母/数字来确定规模
        # A级公司：0.8-1.2倍，B级：0.6-1.0倍，C级：0.4-0.8倍，等等
        if company_name.startswith('A'):
            return random.uniform(0.8, 1.2)
        elif company_name.startswith('B'):
            return random.uniform(0.6, 1.0)
        elif company_name.startswith('C'):
            return random.uniform(0.4, 0.8)
        elif company_name.startswith('D'):
            return random.uniform(0.3, 0.7)
        elif company_name.startswith('E'):
            return random.uniform(0.2, 0.6)
        elif company_name.startswith('F'):
            return random.uniform(0.1, 0.5)
        else:
            return random.uniform(0.5, 1.0)  # 默认规模因子

    def generate_products_and_relationships(self, company_data):
        """生成产品和供需关系"""
        # 生成所有产品的基础价格
        base_prices = self.generate_base_prices()

        # 为每个层级分配产品范围
        products_per_level = self.total_products // self.total_levels
        extra_products = self.total_products % self.total_levels

        level_product_ranges = {}
        current_product = 1

        for level_idx in range(self.total_levels):
            level_key = f"level_{level_idx + 1}"
            products_count = products_per_level + (1 if level_idx < extra_products else 0)

            level_product_ranges[level_key] = {
                'start': current_product,
                'end': current_product + products_count - 1
            }
            current_product += products_count

        # 记录每个层级实际生产的产品
        level_actual_products = {}

        # 移除全局产品配方缓存，每个企业根据自己的原料生成配方
        # product_constructs = {}  # 删除这行

        # 为每个企业分配主要产品和原料需求
        for level_idx, (level_key, companies) in enumerate(company_data.items()):
            product_range = level_product_ranges[level_key]
            available_products = list(range(product_range['start'], product_range['end'] + 1))

            # 记录当前层级实际生产的产品
            current_level_products = set()

            # 增加竞争性：让更多企业生产相同产品
            competition_products = []
            if len(available_products) >= 2 and len(companies) >= 2:
                # 选择20-40%的产品作为竞争产品
                num_competition_products = max(1, int(len(available_products) * random.uniform(0.2, 0.4)))
                competition_products = random.sample(available_products, num_competition_products)

            for company in companies:
                company_size_factor = self.get_company_size_factor(company['name'])

                # 增加产品数量：每个企业生产1-3个产品
                num_products = random.randint(1, min(3, len(available_products)))

                # 50%概率选择竞争产品，50%概率选择独特产品
                selected_products = []

                # 优先选择竞争产品
                if competition_products and random.random() < 0.6:  # 60%概率参与竞争
                    selected_products.append(random.choice(competition_products))
                    num_products -= 1

                # 剩余产品从所有可用产品中选择
                if num_products > 0:
                    remaining_products = [p for p in available_products if p not in selected_products]
                    if remaining_products:
                        additional_products = random.sample(
                            remaining_products,
                            min(num_products, len(remaining_products))
                        )
                        selected_products.extend(additional_products)

                for product_id in selected_products:
                    current_level_products.add(product_id)
                    product_info = {
                        "product_name": f"product_{product_id}",
                        "product_id": product_id,
                        "related_materials": [],
                        "base_price": base_prices[product_id]  # 删除了 initial_inventory 字段
                    }

                    # 判断是否为终端产品（最后一级）
                    is_terminal_product = (level_idx == len(company_data) - 1)

                    if is_terminal_product:
                        # 为终端产品添加特殊标识和消耗率
                        product_info["is_terminal_product"] = True
                        product_info["consumption_rate"] = self.generate_consumption_rate()
                        product_info["product_type"] = "end_stuff"
                    else:
                        product_info["is_terminal_product"] = False
                        product_info["product_type"] = "process_stuff"

                    # 如果不是第一级，需要原料
                    if level_idx > 0:
                        # 获取上一级实际生产的产品作为可用原料
                        prev_level_key = f"level_{level_idx}"
                        if prev_level_key in level_actual_products:
                            available_materials = list(level_actual_products[prev_level_key])

                            if available_materials:
                                # 进一步降低原料需求：60%概率只需要1种原料，40%概率需要2种
                                if random.random() < 0.6:  # 60%概率只需要1种原料
                                    num_materials = 1
                                else:
                                    # 最多只需要2种原料
                                    num_materials = min(2, len(available_materials))

                                selected_materials = random.sample(available_materials, num_materials)

                                for material_id in selected_materials:
                                    product_info["related_materials"].append({
                                        "product_name": f"product_{material_id}",
                                        "product_id": material_id
                                    })

                    # 直接生成产品配方字段（移除了对 product_constructs 的引用）
                    product_info["product_construct"] = self.generate_product_construct(
                        product_info["related_materials"])

                    # 计算制造成本
                    # 在 generate_products_and_relationships 方法中，大约第430-460行
                    # 计算制造成本
                    manufacturing_cost, material_cost = self.calculate_manufacturing_cost(
                        product_info["related_materials"],
                        product_info["product_construct"],
                        base_prices
                    )
                    product_info["manufacturing_cost"] = manufacturing_cost
                    product_info["material_cost"] = material_cost
                    product_info["net_manufacturing_cost"] = round(manufacturing_cost - material_cost, 2)

                    # 计算利润率（确保在10%-20%区间内）
                    if manufacturing_cost > 0:
                        # 目标利润率：10%-20%
                        target_profit_margin = random.uniform(10.0, 20.0)

                        # 根据目标利润率和制造成本计算基础价格
                        # profit_margin = ((base_price - manufacturing_cost) / base_price) * 100
                        # 解得：base_price = manufacturing_cost / (1 - target_profit_margin/100)
                        adjusted_base_price = manufacturing_cost / (1 - target_profit_margin / 100)

                        # 更新基础价格
                        base_prices[product_id] = round(adjusted_base_price, 2)
                        product_info["base_price"] = base_prices[product_id]

                        # 设置利润率
                        product_info["profit_margin"] = round(target_profit_margin, 2)
                    else:
                        # 这种情况不应该发生，但作为保险
                        print(f"警告：产品 {product_id} 的制造成本为0")
                        target_profit_margin = 15.0
                        product_info["profit_margin"] = target_profit_margin

                    company["main_products"].append(product_info)

                # 设置该企业可提供的原料（即其生产的产品）
                company["available_materials"] = [
                    {
                        "product_name": product['product_name'],
                        "product_id": product['product_id']
                    }
                    for product in company["main_products"]
                ]

            # 记录当前层级实际生产的产品
            level_actual_products[level_key] = current_level_products

        # 确保每个非最后级别的企业都至少给下一级别提供原料
        self.ensure_downstream_supply(company_data, level_actual_products)

        return company_data

    def generate_consumption_rate(self):
        """生成终端产品的消耗率（每日消耗百分比）"""
        # 终端产品的消耗率范围：0.1% - 5.0% 每日
        # 不同类型产品有不同的消耗率：
        # - 快消品：2.0% - 5.0%
        # - 耐用品：0.1% - 1.0%
        # - 一般消费品：0.5% - 2.5%

        product_type_prob = random.random()

        if product_type_prob < 0.3:  # 30% 快消品
            consumption_rate = round(random.uniform(2.0, 5.0), 2)
            consumption_type = "fast consum"
        elif product_type_prob < 0.6:  # 30% 耐用品
            consumption_rate = round(random.uniform(0.1, 1.0), 2)
            consumption_type = "slow consum"
        else:  # 40% 一般消费品
            consumption_rate = round(random.uniform(0.5, 2.5), 2)
            consumption_type = "normal consum"

        return {
            "daily_consumption_rate": consumption_rate,  # 每日消耗率（%）
            "consumption_type": consumption_type,  # 消费品类型
            "description": f"consumption_rate:{consumption_rate}%"
        }

    def ensure_downstream_supply(self, company_data, level_actual_products):
        """确保每个非最后级别的企业都至少给下一级别提供原料"""
        level_keys = list(company_data.keys())

        for level_idx in range(len(level_keys) - 1):  # 排除最后一级
            current_level_key = level_keys[level_idx]
            next_level_key = level_keys[level_idx + 1]

            # 获取当前级别所有企业的产品
            current_level_products = set()
            for company in company_data[current_level_key]:
                for product in company['main_products']:
                    current_level_products.add(product['product_id'])

            # 获取下一级别所有企业已使用的原料
            used_materials = set()
            for company in company_data[next_level_key]:
                for product in company['main_products']:
                    for material in product['related_materials']:
                        used_materials.add(material['product_id'])

            # 找出未被使用的产品
            unused_products = current_level_products - used_materials

            # 为未被使用的产品分配给下一级别的企业
            if unused_products:
                next_level_companies = company_data[next_level_key]
                unused_list = list(unused_products)

                for i, unused_product_id in enumerate(unused_list):
                    # 选择一个下一级别的企业
                    target_company = next_level_companies[i % len(next_level_companies)]

                    # 为该企业的第一个产品添加这个原料
                    if target_company['main_products']:
                        target_product = target_company['main_products'][0]

                        # 检查是否已经有这个原料
                        has_material = any(mat['product_id'] == unused_product_id
                                           for mat in target_product['related_materials'])

                        if not has_material:
                            target_product['related_materials'].append({
                                "product_name": f"product_{unused_product_id}",
                                "product_id": unused_product_id
                            })

    def print_statistics(self, company_data):
        """打印统计信息"""
        print("\n=== 产业链生成统计 ===")
        print(f"总企业数: {self.total_companies}")
        print(f"总层级数: {self.total_levels}")
        print(f"总产品数: {self.total_products}")
        print("\n各层级企业分布:")

        total_relationships = 0
        for level_key, companies in company_data.items():
            print(f"{level_key}: {len(companies)}家企业")

            # 统计该层级的产品-原料关系数量
            level_relationships = 0
            for company in companies:
                for product in company['main_products']:
                    level_relationships += len(product['related_materials'])

            total_relationships += level_relationships
            print(f"  - 产品-原料关系: {level_relationships}个")

        print(f"\n总供需关系数: {total_relationships}")
        print("\n数据已生成完成！")

    def save_to_file(self, company_data, filename="industry_test.json"):
        """保存数据到JSON文件"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(company_data, f, ensure_ascii=False, indent=2)
            print(f"\n数据已保存到 {filename}")
        except Exception as e:
            print(f"\n保存文件时出错: {e}")

    def detect_competition_relationships(self, company_data):
        """检测竞争关系"""
        product_companies = defaultdict(list)

        # 收集每个产品的生产企业
        for level_key, companies in company_data.items():
            for company in companies:
                for product in company.get('main_products', []):
                    product_name = product.get('product_name')
                    if product_name:
                        product_companies[product_name].append(company['name'])

        # 识别竞争关系（生产相同产品的企业）
        competition_groups = {}

        for product_name, company_names in product_companies.items():
            if len(company_names) >= 2:  # 至少2家企业才构成竞争
                competition_groups[product_name] = {
                    'competing_companies': company_names,
                    'product': product_name
                }

        return competition_groups

    def print_competition_analysis(self, company_data, competition_groups):
        """打印竞争分析和控制变量信息"""
        print("\n=== 竞争关系和控制变量分析 ===")

        if not competition_groups:
            print("未发现竞争关系")
            return

        print(f"发现 {len(competition_groups)} 个竞争组：\n")

        for product_name, competition_info in competition_groups.items():
            companies = competition_info['competing_companies']
            control_var = competition_info.get('control_variable', '未设置')

            print(f"竞争组: {product_name}")
            print(f"  竞争产品: {product_name}")
            print(f"  参与企业: {', '.join(companies)}")
            print(f"  控制变量: {control_var}")

            # 显示具体的差异化指标
            if control_var == 'capacity':
                print(f"  竞争维度: 产能差异化 (其他指标统一: 资金、库存、配方)")
            elif control_var == 'inventory':
                print(f"  竞争维度: 库存策略差异化 (其他指标统一: 产能、资金、配方)")
            elif control_var == 'capital':
                print(f"  竞争维度: 资金实力差异化 (其他指标统一: 产能、库存、配方)")
            elif control_var == 'recipe':
                print(f"  竞争维度: 配方复杂度差异化 (其他指标统一: 产能、资金、库存)")

            print("  企业详情:")
            for company_name in companies:
                company = self.find_company_by_name(company_data, company_name)
                if company:
                    capacity = company.get('company_capacity', 'N/A')
                    capital = company.get('initial_capital', 'N/A')
                    inventory_factor = company.get('inventory_factor', 'N/A')
                    recipe_complexity = company.get('recipe_complexity', 'N/A')

                    print(
                        f"    {company['name']}: 产能={capacity}, 资金={capital}, 库存因子={inventory_factor:.2f}, 配方复杂度={recipe_complexity}")
            print()

    def assign_intelligence_levels(self, company_data):
        """为企业分配智能等级（1-4数值，基于产品名称竞争关系）"""
        # 简化的智能等级：1, 2, 3, 4
        intelligence_levels = [1, 2, 3, 4]

        # 检测竞争关系（基于产品名称）
        competition_groups = self.detect_competition_relationships(company_data)

        # 记录已分配智能等级的企业
        assigned_companies = set()

        # 为有竞争关系的企业分配不同智能等级
        for product_name, competition_info in competition_groups.items():
            competing_companies = competition_info['competing_companies']

            # 随机打乱竞争企业顺序
            random.shuffle(competing_companies)

            # 为竞争企业分配不同的智能等级
            for i, company_name in enumerate(competing_companies):
                level_index = i % len(intelligence_levels)
                intelligence_level = intelligence_levels[level_index]

                # 找到对应的企业并添加智能等级
                for level_key, companies in company_data.items():
                    for company in companies:
                        if company['name'] == company_name:
                            company['intelligence_level'] = intelligence_level
                            assigned_companies.add(company_name)
                            break

        # 为没有竞争关系的企业分配随机智能等级
        for level_key, companies in company_data.items():
            for company in companies:
                if company['name'] not in assigned_companies:
                    # 随机分配智能等级
                    intelligence_level = random.choice(intelligence_levels)
                    company['intelligence_level'] = intelligence_level

        return company_data

    def generate_inventory_system(self, company_data):
        """为企业生成统一的库存管理系统"""
        # 第一步：统计每种产品的供应量和需求量
        product_supply = {}  # 产品ID -> 总供应量
        product_demand = {}  # 产品ID -> 需求该产品作为原料的企业列表

        # 统计产品供应量
        for level_key, companies in company_data.items():
            for company in companies:
                company_size_factor = self.get_company_size_factor(company['name'])

                for product in company["main_products"]:
                    product_id = product["product_id"]
                    product_inventory = self.generate_initial_inventory(product_id, company_size_factor)

                    if product_id not in product_supply:
                        product_supply[product_id] = 0
                    product_supply[product_id] += product_inventory

        # 统计产品需求量（哪些企业需要哪些原料）
        for level_key, companies in company_data.items():
            for company in companies:
                for product in company["main_products"]:
                    for material in product["related_materials"]:
                        material_id = material["product_id"]
                        if material_id not in product_demand:
                            product_demand[material_id] = []
                        product_demand[material_id].append({
                            'company': company,
                            'company_size_factor': self.get_company_size_factor(company['name'])
                        })

        # 第二步：为每个企业生成库存系统
        for level_key, companies in company_data.items():
            for company in companies:
                company_size_factor = self.get_company_size_factor(company['name'])

                # 初始化库存系统
                inventory_system = {
                    "products": {},  # 产品库存
                    "materials": {}  # 原料库存
                }

                # 为公司生产的产品生成库存
                for product in company["main_products"]:
                    product_id = product["product_id"]
                    product_inventory = self.generate_initial_inventory(product_id, company_size_factor)

                    inventory_system["products"][product_id] = {
                        "product_name": product["product_name"],
                        "quantity": product_inventory
                    }

                # 为公司需要的原料生成库存（考虑供需平衡）
                all_materials = set()
                for product in company["main_products"]:
                    for material in product["related_materials"]:
                        all_materials.add((material["product_id"], material["product_name"]))

                for material_id, material_name in all_materials:
                    # 计算该原料的合理库存分配
                    material_inventory = self.calculate_balanced_material_inventory(
                        material_id, company, company_size_factor, product_supply, product_demand
                    )

                    inventory_system["materials"][material_id] = {
                        "product_name": material_name,
                        "quantity": material_inventory
                    }

                # 添加库存系统到公司数据
                company["inventory_system"] = inventory_system

        return company_data

    def calculate_balanced_material_inventory(self, material_id, company, company_size_factor, product_supply,
                                              product_demand):
        """计算平衡的原料库存，确保总需求不超过总供应"""
        # 获取该原料的总供应量
        total_supply = product_supply.get(material_id, 0)

        if total_supply == 0:
            return 0

        # 获取需要该原料的所有企业
        demanding_companies = product_demand.get(material_id, [])

        if not demanding_companies:
            return 0

        # 计算当前企业在所有需求企业中的权重（基于公司规模因子）
        total_demand_weight = sum(dc['company_size_factor'] for dc in demanding_companies)
        current_company_weight = company_size_factor

        # 按权重分配原料库存，确保总和不超过供应量
        # 预留10%的供应量作为缓冲
        available_supply = int(total_supply * 0.9)

        if total_demand_weight > 0:
            allocated_inventory = int((current_company_weight / total_demand_weight) * available_supply)
        else:
            allocated_inventory = 0

        # 确保分配的库存不少于最小值
        min_inventory = int(self.generate_initial_inventory(material_id, company_size_factor) * 0.3)
        allocated_inventory = max(allocated_inventory, min_inventory)

        return allocated_inventory

    def apply_controlled_variables(self, company_data, competition_groups):
        """为竞争组应用控制变量实验设计"""
        control_variables = ['capacity', 'inventory', 'capital', 'recipe']

        # 为每个竞争组分配控制变量
        for product_name, competition_info in competition_groups.items():
            competing_companies = competition_info['competing_companies']

            if len(competing_companies) < 2:
                continue

            # 随机选择控制变量
            control_var = random.choice(control_variables)
            competition_info['control_variable'] = control_var

            # 为竞争组设置基准值
            if control_var == 'capacity':
                # 产能控制：其他变量统一，只有产能不同
                base_capital = random.randint(40000, 80000)
                base_inventory_factor = random.uniform(0.7, 1.0)

                for i, company_name in enumerate(competing_companies):
                    company = self.find_company_by_name(company_data, company_name)
                    if company:
                        company['initial_capital'] = base_capital
                        company['inventory_factor'] = base_inventory_factor
                        company['recipe_complexity'] = 'standard'
                        # 产能分层：低、中、高
                        if i == 0:
                            company['company_capacity'] = random.randint(30, 50)  # 低产能
                        elif i == 1:
                            company['company_capacity'] = random.randint(51, 75)  # 中产能
                        else:
                            company['company_capacity'] = random.randint(76, 100)  # 高产能

            elif control_var == 'inventory':
                # 库存控制：其他变量统一，只有初始库存不同
                base_capacity = random.randint(60, 80)
                base_capital = random.randint(40000, 80000)

                for i, company_name in enumerate(competing_companies):
                    company = self.find_company_by_name(company_data, company_name)
                    if company:
                        company['company_capacity'] = base_capacity
                        company['initial_capital'] = base_capital
                        company['recipe_complexity'] = 'standard'
                        # 库存因子分层
                        if i == 0:
                            company['inventory_factor'] = random.uniform(0.3, 0.6)  # 低库存
                        elif i == 1:
                            company['inventory_factor'] = random.uniform(0.6, 0.9)  # 中库存
                        else:
                            company['inventory_factor'] = random.uniform(0.9, 1.3)  # 高库存（不超过2000限制）

            elif control_var == 'capital':
                # 资金控制：其他变量统一，只有初始资金不同
                base_capacity = random.randint(60, 80)
                base_inventory_factor = random.uniform(0.7, 1.0)

                for i, company_name in enumerate(competing_companies):
                    company = self.find_company_by_name(company_data, company_name)
                    if company:
                        company['company_capacity'] = base_capacity
                        company['inventory_factor'] = base_inventory_factor
                        company['recipe_complexity'] = 'standard'
                        # 资金分层
                        if i == 0:
                            company['initial_capital'] = random.randint(20000, 40000)  # 低资金
                        elif i == 1:
                            company['initial_capital'] = random.randint(40000, 70000)  # 中资金
                        else:
                            company['initial_capital'] = random.randint(70000, 100000)  # 高资金

            elif control_var == 'recipe':
                # 配方控制：其他变量统一，配方需求不同
                base_capacity = random.randint(60, 80)
                base_capital = random.randint(40000, 80000)
                base_inventory_factor = random.uniform(0.7, 1.0)

                for i, company_name in enumerate(competing_companies):
                    company = self.find_company_by_name(company_data, company_name)
                    if company:
                        company['company_capacity'] = base_capacity
                        company['initial_capital'] = base_capital
                        company['inventory_factor'] = base_inventory_factor
                        # 在capacity、inventory、capital控制的情况下，也需要添加：
                        company['recipe_complexity'] = 'standard'  # 统一配方复杂度
                        if i == 1:
                            company['recipe_complexity'] = 'medium'  # 中等配方
                        else:
                            company['recipe_complexity'] = 'complex'  # 复杂配方

    def find_company_by_name(self, company_data, company_name):
        """根据公司名称查找公司对象"""
        for level_key, companies in company_data.items():
            for company in companies:
                if company['name'] == company_name:
                    return company
        return None

    def generate(self):
        """生成完整的产业链"""
        print("开始生成产业链...")

        # 获取用户输入
        self.get_user_input()

        # 分配企业到各层级
        level_counts = self.distribute_companies()
        print(f"企业分配: {level_counts}")

        # 生成企业名称和基本信息
        company_data = self.generate_company_names(level_counts)

        # 生成产品和供需关系
        self.generate_products_and_relationships(company_data)

        # 检测竞争关系并分配控制变量
        competition_groups = self.detect_competition_relationships(company_data)

        # 应用控制变量实验设计
        self.apply_controlled_variables(company_data, competition_groups)

        # 生成库存系统
        self.generate_inventory_system(company_data)

        # 分配智能等级
        self.assign_intelligence_levels(company_data)

        # 打印统计信息
        self.print_statistics(company_data)

        # 打印竞争分析和控制变量信息
        self.print_competition_analysis(company_data, competition_groups)

        # 保存到文件
        self.save_to_file(company_data)

        print("产业链生成完成！")
        return company_data


# 使用示例
def main():
    generator = IndustryChainGenerator()
    generator.generate()


if __name__ == "__main__":
    main()


