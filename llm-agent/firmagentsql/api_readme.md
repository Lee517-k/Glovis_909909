# 企业仿真系统 API 接口文档

## 概述

给出示例数据的是正在使用的，无示例数据的可能不可用

**基础信息：**
- 框架：FastAPI
- 数据源：PostgreSQL + MLflow
- 支持：异步处理、CORS跨域、数据验证
- 健康检查：GET /health

---

## 接口分类

### 1. 实验管理接口

#### 1.1 获取实验信息
- **接口：** `GET /api/experiments/{id}`
- **功能：** 获取指定实验的详细信息
- **参数：** 
  - `id` (路径参数): 实验ID
- **返回：** 实验基本信息，包括状态、进度、配置等

#### 1.2 获取实验时间线
- **接口：** `GET /api/experiments/{id}/timeline`
- **功能：** 获取实验的时间线步骤
- **参数：** 
  - `id` (路径参数): 实验ID
- **返回：** 实验各步骤的时间线数据

#### 1.3 获取所有实验列表
- **接口：** `GET /api/experiments`
- **功能：** 获取系统中所有实验的列表
- **返回：** 实验列表数据

#### 1.4 获取实验最大步骤
- **接口：** `GET /api/experiments/{exp_id}/max-step`
- **功能：** 获取实验的最大步骤数和总步骤数
- **参数：** 
  - `exp_id` (路径参数): 实验ID
- **返回：** 最大步骤、总步骤数、所有步骤列表
返回的样例数据，可作为格式参考：{"experiment_id":"293445b5-88c1-4b45-97b1-7a72d4c6ff07","max_step":13,"total_steps":14,"all_steps":[0,1,2,3,4,5,6,7,8,9,10,11,12,13]}

---

### 2. Agent（企业）相关接口

#### 2.1 获取所有Agent档案
- **接口：** `GET /api/experiments/{exp_id}/agents/-/profile`
- **功能：** 获取实验中所有Agent的档案信息，包含MLflow参数和指标
- **参数：** 
  - `exp_id` (路径参数): 实验ID
- **返回：** 所有Agent的档案数据

#### 2.2 获取特定Agent档案
- **接口：** `GET /api/experiments/{exp_id}/agents/{agent_id}/profile`
- **功能：** 获取指定Agent的详细档案，包含历史指标数据
- **参数：** 
  - `exp_id` (路径参数): 实验ID
  - `agent_id` (路径参数): Agent ID
- **返回：** Agent详细档案信息
{"id": 5,"name": "B2","profile": {"company_id": 5,"company_name": "B2","params": {"agent_id_B2": "5","company_name_B2": "B2","initial_fund_B2": "100000.0","intelligence_level_B2": "1","material_1_B2_id": "9","material_1_B2_name": "product_9","material_2_B2_id": "7","material_2_B2_name": "product_7","material_inventory_1_B2_name": "product_9","material_inventory_1_B2_quantity": "1210","material_inventory_2_B2_name": "product_7","material_inventory_2_B2_quantity": "385","product_1_B2_base_price": "146.8","product_1_B2_id": "9","product_1_B2_is_terminal_product": "False","product_1_B2_manufacturing_cost": "124.14","product_1_B2_name": "product_9","product_1_B2_product_construct": "product_2*50%+product_5*50%","product_1_B2_profit_margin": "15.44","product_2_B2_base_price": "149.48","product_2_B2_id": "7","product_2_B2_is_terminal_product": "False","product_2_B2_manufacturing_cost": "126.02","product_2_B2_name": "product_7","product_2_B2_product_construct": "product_5*100%","product_2_B2_profit_margin": "15.69","product_inventory_1_B2_name": "product_14","product_inventory_1_B2_quantity": "570"},"metrics": {"material_inventory_ratio_B2": 0.4968847352024922,"product_inventory_ratio_B2": 0.5031152647975078,"inventory_turnover_rate_B2": 0.0,"company_fund_B2": 118101.20000000001,"net_transaction_amount_B2": 0.0,"supply_total_quantity_B2": 0.0,"supply_total_amount_B2": 0.0,"supply_orders_count_B2": 0.0,"purchase_total_quantity_B2": 0.0,"purchase_total_amount_B2": 0.0,"purchase_orders_count_B2": 0.0,"intelligence_level_B2": 1.0,"total_inventory_B2": 3210.0,"total_material_inventory_B2": 1595.0,"total_product_inventory_B2": 1615.0,"material_inventory_B2_product_7": 385.0,"material_inventory_B2_product_9": 1210.0,"product_inventory_B2_product_7": 1045.0,"product_inventory_B2_product_14": 570.0},"historical_metrics": {"step_0": {"material_inventory_ratio_B2": 0.7367205542725174,"product_inventory_ratio_B2": 0.2632794457274827,"inventory_turnover_rate_B2": 0.0,"company_fund_B2": 100000.0,"net_transaction_amount_B2": 0.0,"supply_total_quantity_B2": 0.0,"supply_total_amount_B2": 0.0,"supply_orders_count_B2": 0.0,"purchase_total_quantity_B2": 0.0,"purchase_total_amount_B2": 0.0,"purchase_orders_count_B2": 0.0,"intelligence_level_B2": 1.0,"total_inventory_B2": 2165.0,"total_material_inventory_B2": 1595.0,"total_product_inventory_B2": 570.0,"material_inventory_B2_product_7": 385.0,"material_inventory_B2_product_9": 1210.0,"product_inventory_B2_product_14": 570.0},"step_1": {"material_inventory_ratio_B2": 0.728310502283105,"product_inventory_ratio_B2": 0.271689497716895,"inventory_turnover_rate_B2": 0.0,"company_fund_B2": 100000.0,"net_transaction_amount_B2": 0.0,"supply_total_quantity_B2": 0.0,"supply_total_amount_B2": 0.0,"supply_orders_count_B2": 0.0,"purchase_total_quantity_B2": 0.0,"purchase_total_amount_B2": 0.0,"purchase_orders_count_B2": 0.0,"intelligence_level_B2": 1.0,"total_inventory_B2": 2190.0,"total_material_inventory_B2": 1595.0,"total_product_inventory_B2": 595.0,"material_inventory_B2_product_7": 385.0,"material_inventory_B2_product_9": 1210.0,"product_inventory_B2_product_7": 25.0,"product_inventory_B2_product_14": 570.0}},"latest_step": 1,"run_uuid": "7ad109b978bc44e19346fbf7399e5d6e"}}

#### 2.3 获取所有Agent状态
- **接口：** `GET /api/experiments/{exp_id}/agents/-/status`
- **功能：** 获取指定时间点所有Agent的状态
- **参数：** 
  - `exp_id` (路径参数): 实验ID
  - `day` (查询参数): 天数
  - `t` (查询参数): 时间点
- **返回：** 所有Agent的状态数据

#### 2.4 获取特定Agent状态历史
- **接口：** `GET /api/experiments/{exp_id}/agents/{agent_id}/status`
- **功能：** 获取指定Agent的状态历史记录
- **参数：** 
  - `exp_id` (路径参数): 实验ID
  - `agent_id` (路径参数): Agent ID
- **返回：** Agent状态历史数据

#### 2.5 获取Agent对话记录
- **接口：** `GET /api/experiments/{exp_id}/agents/{agent_id}/dialog`
- **功能：** 获取指定Agent的对话和交互记录
- **参数：** 
  - `exp_id` (路径参数): 实验ID
  - `agent_id` (路径参数): Agent ID
- **返回：** Agent对话记录，按步骤分组

#### 2.6 获取Agent指标数据
- **接口：** `GET /api/experiments/{exp_id}/agents/{agent_id}/metrics?step={step}`
- **功能：** 获取指定步骤中特定Agent的metrics数据
- **参数：** 
  - `exp_id` (路径参数): 实验ID
  - `agent_id` (路径参数): Agent ID
  - `step` (查询参数): 步骤数
- **返回：** Agent在指定步骤的指标数据
{"experiment_id":"293445b5-88c1-4b45-97b1-7a72d4c6ff07","agent_id":5,"agent_name":"B2","step":2,"metrics":{"material_inventory_ratio_B2":0.7200902934537246,"product_inventory_ratio_B2":0.2799097065462754,"inventory_turnover_rate_B2":0.0,"company_fund_B2":100000.0,"net_transaction_amount_B2":0.0,"supply_total_quantity_B2":0.0,"supply_total_amount_B2":0.0,"supply_orders_count_B2":0.0,"purchase_total_quantity_B2":0.0,"purchase_total_amount_B2":0.0,"purchase_orders_count_B2":0.0,"intelligence_level_B2":1.0,"total_inventory_B2":2215.0,"total_material_inventory_B2":1595.0,"total_product_inventory_B2":620.0,"material_inventory_B2_product_7":385.0,"material_inventory_B2_product_9":1210.0,"product_inventory_B2_product_7":50.0,"product_inventory_B2_product_14":570.0},"run_uuid":"7ad109b978bc44e19346fbf7399e5d6e"}
---

### 3. 企业数据接口

#### 3.1 获取实验中的所有公司
- **接口：** `GET /api/experiments/{exp_id}/companies`
- **功能：** 获取实验中所有参与的公司列表
- **参数：** 
  - `exp_id` (路径参数): 实验ID
- **返回：** 公司列表数据
[{"company_id":1,"company_name":"A1"},{"company_id":2,"company_name":"A2"},{"company_id":3,"company_name":"A3"},{"company_id":4,"company_name":"B1"},{"company_id":5,"company_name":"B2"},{"company_id":6,"company_name":"B3"},{"company_id":7,"company_name":"B4"},{"company_id":8,"company_name":"B5"},{"company_id":9,"company_name":"C1"},{"company_id":10,"company_name":"C2"},{"company_id":11,"company_name":"C3"},{"company_id":12,"company_name":"C4"},{"company_id":13,"company_name":"D1"},{"company_id":14,"company_name":"D2"},{"company_id":15,"company_name":"D3"}]

#### 3.2 获取所有企业指标
- **接口：** `GET /api/experiments/{exp_id}/metrics?step={step}`
- **功能：** 获取特定步骤所有企业的metrics数据
- **参数：** 
  - `exp_id` (路径参数): 实验ID
  - `step` (查询参数): 步骤数
- **返回：** 所有企业在指定步骤的指标数据

#### 3.3 获取企业智能等级分布
- **接口：** `GET /api/experiments/{exp_id}/intelligence`
- **功能：** 获取实验中企业智能等级的分布情况
- **参数：** 
  - `exp_id` (路径参数): 实验ID
- **返回：** 智能等级分布数据

---

### 4. 库存管理接口

#### 4.1 获取实验库存汇总
- **接口：** `GET /api/experiments/{exp_id}/inventory`
- **功能：** 获取实验的库存汇总信息
- **参数：** 
  - `exp_id` (路径参数): 实验ID
  - `step` (查询参数，可选): 步骤数
- **返回：** 库存汇总数据

#### 4.2 获取企业库存详情
- **接口：** `GET /api/experiments/{exp_id}/companies/{company_id}/inventory`
- **功能：** 获取特定企业的库存详细信息
- **参数：** 
  - `exp_id` (路径参数): 实验ID
  - `company_id` (路径参数): 公司ID
  - `step` (查询参数，可选): 步骤数
- **返回：** 企业库存详情

---

### 5. 原料管理接口

#### 5.1 获取产品所需原料
- **接口：** `GET /api/experiments/{exp_id}/agents/{agent_id}/products/{product_id}/materials`
- **功能：** 获取指定产品生产所需的原料清单
- **参数：** 
  - `exp_id` (路径参数): 实验ID
  - `agent_id` (路径参数): Agent ID
  - `product_id` (路径参数): 产品ID
  - `step` (查询参数，可选): 步骤数
- **返回：** 产品所需原料列表及当前库存

#### 5.2 获取Agent所需原料
- **接口：** `GET /api/experiments/{exp_id}/agents/{agent_id}/required-materials`
- **功能：** 获取Agent所需要的所有原料
- **参数：** 
  - `exp_id` (路径参数): 实验ID
  - `agent_id` (路径参数): Agent ID
  - `step` (查询参数，可选): 步骤数
- **返回：** Agent所需原料清单
返回的样例数据，可作为格式参考：{"experiment_id":"293445b5-88c1-4b45-97b1-7a72d4c6ff07","agent_id":2,"agent_name":"A2","intelligence_level":1,"total_required_materials":2,"required_materials":[{"material_id":7,"material_name":"product_7","current_quantity":385,"is_sufficient":true},{"material_id":9,"material_name":"product_9","current_quantity":1210,"is_sufficient":true}],"step":53}

#### 5.3 获取Agent可提供原料
- **接口：** `GET /api/experiments/{exp_id}/agents/{agent_id}/available-materials`
- **功能：** 获取Agent可以提供给其他企业的原材料
- **参数：** 
  - `exp_id` (路径参数): 实验ID
  - `agent_id` (路径参数): Agent ID
  - `step` (查询参数，可选): 步骤数
- **返回：** Agent可提供的原材料清单
返回的样例数据，可作为格式参考：{"experiment_id":"293445b5-88c1-4b45-97b1-7a72d4c6ff07","agent_id":2,"agent_name":"A2","intelligence_level":1,"total_available_materials":3,"available_materials":[{"material_id":2,"material_name":"product_2","available_quantity":90,"can_supply":true},{"material_id":5,"material_name":"product_5","available_quantity":225,"can_supply":true},{"material_id":14,"material_name":"product_14","available_quantity":570,"can_supply":true}],"step":53}

---

### 6. 交易与通信接口

#### 6.1 获取交易汇总
- **接口：** `GET /api/experiments/{exp_id}/transactions`
- **功能：** 获取实验中的交易汇总数据
- **参数：** 
  - `exp_id` (路径参数): 实验ID
  - `start_step` (查询参数，可选): 开始步骤
  - `end_step` (查询参数，可选): 结束步骤
- **返回：** 交易汇总统计
[{"step":4,"purchaser_id":"9","supplier_id":"4","product_name":"product_6","transaction_count":2,"total_value":29998.0,"avg_price":149.99},{"step":5,"purchaser_id":"6","supplier_id":"1","product_name":"product_2","transaction_count":1,"total_value":2999.0,"avg_price":29.99},{"step":5,"purchaser_id":"6","supplier_id":"2","product_name":"product_2","transaction_count":1,"total_value":1499.0,"avg_price":14.99},{"step":6,"purchaser_id":"6","supplier_id":"1","product_name":"product_2","transaction_count":1,"total_value":2999.0,"avg_price":29.99}]

#### 6.2 获取通信汇总
- **接口：** `GET /api/experiments/{exp_id}/communications`
- **功能：** 获取实验中的通信汇总数据
- **参数：** 
  - `exp_id` (路径参数): 实验ID
  - `operation_type` (查询参数，可选): 操作类型
- **返回：** 通信汇总统计
[{"step":2,"company_id":6,"source_company_id":"10","operation_type":"operation-price","message_count":1},{"step":3,"company_id":1,"source_company_id":"6","operation_type":"operation-price","message_count":1},{"step":3,"company_id":2,"source_company_id":"5","operation_type":"operation-price","message_count":1},{"step":3,"company_id":2,"source_company_id":"6","operation_type":"operation-price","message_count":1},{"step":3,"company_id":4,"source_company_id":"9","operation_type":"operation-price","message_count":2},{"step":3,"company_id":5,"source_company_id":"2","operation_type":"operation-reject","message_count":1},{"step":3,"company_id":6,"source_company_id":"1","operation_type":"operation-reject","message_count":1},{"step":3,"company_id":6,"source_company_id":"10","operation_type":"operation-price","message_count":1},{"step":3,"company_id":7,"source_company_id":"9","operation_type":"operation-price","message_count":2},{"step":3,"company_id":9,"source_company_id":"7","operation_type":"operation-deal","message_count":1},{"step":4,"company_id":2,"source_company_id":"5","operation_type":"operation-price","message_count":2},{"step":4,"company_id":2,"source_company_id":"6","operation_type":"operation-price","message_count":1},{"step":4,"company_id":4,"source_company_id":"9","operation_type":"operation-build","message_count":1},{"step":4,"company_id":7,"source_company_id":"9","operation_type":"operation-reject","message_count":1},{"step":4,"company_id":9,"source_company_id":"4","operation_type":"operation-deal","message_count":2}]

---

### 7. 全局信息接口

#### 7.1 获取全局提示
- **接口：** `GET /api/experiments/{exp_id}/prompt`
- **功能：** 获取市场洞察等全局提示信息
- **参数：** 
  - `exp_id` (路径参数): 实验ID
  - `day` (查询参数): 天数
  - `t` (查询参数): 时间点
- **返回：** 市场洞察和全局提示

---

### 8. 系统接口

#### 8.1 健康检查
- **接口：** `GET /health`
- **功能：** 检查系统健康状态
- **返回：** 系统状态和时间戳

### 数据源说明

- **PostgreSQL**: 存储企业状态、交易记录、通信记录等核心业务数据
- **MLflow**: 存储实验参数、指标数据等机器学习相关信息

---

## 使用说明

1. 所有接口返回JSON格式数据
2. 错误情况下返回包含error字段的JSON响应
3. 支持查询参数进行数据过滤和分页
4. 时间相关参数使用ISO格式
5. 数据库连接失败时返回500状态码

---