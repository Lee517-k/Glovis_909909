# 企业智能体价格决策和付款方式说明

## 功能概述

企业智能体添加了两个新的决策功能：

1. **产品价格决策**：根据企业的资金、库存、销量、产能和市场价格等因素，为企业产出的产品制定合理的价格。
2. **付款方式决策**：根据企业的库存、资金、销量等状况，决定企业在购买或销售产品时的付款方式，包括分期付款（分期数、利息）和一次性结清（付款时间）。

## 文件结构

- `price_decision_prompt.py`：包含产品价格决策和付款方式决策的prompt模板
- `firm_economy_block_extension.py`：实现产品价格决策和付款方式决策的功能扩展模块
- `usage_example.py`：展示如何使用这些新功能的示例代码

## 使用方法

### 1. 产品价格决策

```python
# 创建FirmEconomyBlockExtension实例
economy_extension = FirmEconomyBlockExtension(
    agent=agent,
    llm=llm,
    environment=environment,
    memory=memory
)

# 决定产品价格
product_name = "智能手机"
price_decision = await economy_extension.decide_product_price(product_name)
```

返回结果示例：
```json
{
  "price": 199.99,
  "reasoning": "基于产品成本、市场价格和当前库存情况，设定略低于市场均价的价格以提高销量，同时保持合理利润。"
}
```

### 2. 付款方式决策

```python
# 决定购买付款方式
transaction_type = "purchase"  # 购买他人产品
transaction_amount = 50000.0
transaction_partner = "供应商A"
payment_decision = await economy_extension.decide_payment_method(
    transaction_type, transaction_amount, transaction_partner
)
```

返回结果示例（分期付款）：
```json
{
  "payment_method": "installment",
  "details": {
    "installment_count": 3,
    "interest_rate": 0.05
  },
  "reasoning": "由于交易金额较大且当前资金有限，选择3期付款以减轻资金压力，同时提供合理利率以维持良好合作关系。"
}
```

返回结果示例（一次性付款）：
```json
{
  "payment_method": "full_payment",
  "details": {
    "payment_days": 30
  },
  "reasoning": "企业资金充足，选择交货后30天内一次性付款，以简化交易流程并获得可能的现金折扣。"
}
```

## 集成到现有系统

要将这些新功能集成到现有的FirmAgent中，可以按照以下步骤操作：

1. 在FirmAgent的`__init__`方法中初始化FirmEconomyBlockExtension：

```python
self.economy_extension = FirmEconomyBlockExtension(
    agent=self,
    llm=self.llm,
    environment=self.environment,
    memory=memory
)
```

2. 在需要决定产品价格的地方调用`decide_product_price`方法：

```python
async def update_product_price(self, product_name):
    price_decision = await self.economy_extension.decide_product_price(product_name)
    # 可以在这里处理价格决策结果
    return price_decision
```

3. 在需要决定付款方式的地方调用`decide_payment_method`方法：

```python
async def determine_payment_method(self, transaction_type, amount, partner):
    payment_decision = await self.economy_extension.decide_payment_method(
        transaction_type, amount, partner
    )
    # 可以在这里处理付款方式决策结果
    return payment_decision
```

## 设计思路

### 产品价格决策

产品价格决策考虑了以下因素：

1. **企业信息**：企业名称、类型、规模
2. **产品信息**：产品名称、描述、成本
3. **市场情况**：市场平均价格、市场需求趋势
4. **企业状况**：当前资金、当前库存、近期销量、当前产能

基于这些信息，智能体会考虑以下几点来制定价格：
- 价格应该能够覆盖成本并产生合理利润
- 价格应该考虑市场竞争情况
- 价格应该根据库存和销量情况进行调整
- 价格应该考虑企业的资金状况和产能

### 付款方式决策

付款方式决策考虑了以下因素：

1. **企业信息**：企业名称、类型、规模
2. **企业状况**：当前资金、当前库存、近期销量、资金流动性
3. **交易信息**：交易类型（购买/销售）、交易金额、交易对象、历史交易记录

基于这些信息，智能体会考虑以下几点来决定付款方式：
- 企业当前的资金状况和流动性
- 库存和销量情况
- 交易金额的大小
- 与交易对象的历史关系

## 注意事项

1. 这些功能依赖于企业智能体的内存状态，确保相关状态字段（如products、fund、product_stocks等）已正确初始化。
2. 在实际使用中，可能需要根据项目的具体需求调整prompt模板和方法实现。
3. 错误处理机制会在LLM响应解析失败时提供默认值，确保系统的稳定性。