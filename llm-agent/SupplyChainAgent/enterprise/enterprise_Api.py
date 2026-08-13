from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
import asyncio
from datetime import datetime
import json
from contextlib import asynccontextmanager

from starlette.middleware.cors import CORSMiddleware
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
# 导入现有的查询类
from firmagentsql.select import EnterpriseDataQuerier
from firmagentsql.latest_experiment_query import LatestExperimentQuery

## 全局查询器实例
querier = None
mlflow_querier = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global querier, mlflow_querier
    try:
        querier = EnterpriseDataQuerier()
        await querier.connect()

        # LatestExperimentQuery 不需要 connect/disconnect，直接实例化即可
        mlflow_querier = LatestExperimentQuery()

        print("数据库连接成功建立")
        yield
    except Exception as e:
        print(f"数据库连接失败: {e}")
        querier = None
        mlflow_querier = None
        yield
    finally:
        if querier:
            await querier.disconnect()
        # mlflow_querier 不需要 disconnect


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def check_db_connection(func):
    async def wrapper(*args, **kwargs):
        if querier is None:
            return JSONResponse(
                content={"error": "数据库连接未建立"},
                status_code=500
            )
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            return JSONResponse(
                content={"error": f"操作失败: {str(e)}"},
                status_code=500
            )

    return wrapper


# 数据模型定义
class ApiExperiment(BaseModel):
    id: str
    name: str
    num_day: int
    status: str
    cur_day: int
    cur_t: int
    config: str
    error: str
    input_tokens: int
    output_tokens: int
    created_at: str
    updated_at: str


class ApiTime(BaseModel):
    day: int
    t: int


from typing import Dict, Optional


# 修改现有的AgentProfileData模型
class AgentProfileData(BaseModel):
    """Agent档案详细数据"""
    company_id: int
    company_name: str
    intelligence_level: Optional[int] = None  # 新增智能等级
    inventory_system: Optional[Dict[str, Any]] = None  # 新增库存系统
    params: Dict[str, str] = {}  # MLflow参数数据
    metrics: Dict[str, float] = {}  # 当前步骤的指标数据
    historical_metrics: Optional[Dict[str, Dict[str, float]]] = None  # 历史指标数据
    latest_step: int = 0
    run_uuid: Optional[str] = None


class ApiAgentProfile(BaseModel):
    id: int
    name: str
    profile: AgentProfileData  # 使用具体的类型而不是Any


class ApiAgentStatus(BaseModel):
    id: int
    day: int
    t: int
    lng: Optional[float] = None
    lat: Optional[float] = None
    parent_id: Optional[int] = None
    action: str
    status: Any
    created_at: str


class ApiAgentDialog(BaseModel):
    id: int
    day: int
    t: int
    type: int  # 0=思考，1=交谈，2=用户
    speaker: str
    content: str
    created_at: str


class ApiGlobalPrompt(BaseModel):
    day: int
    t: int
    prompt: str
    created_at: str


# 1. 实验相关接口

@app.get("/api/experiments/{id}")
async def get_experiment(id: str):
    """获取实验信息"""
    try:
        # 查询实验基本信息
        query = """
        SELECT 
            id,
            name,
            num_day,
            status,
            cur_day,
            cur_t,
            config,
            error,
            input_tokens,
            output_tokens,
            created_at,
            updated_at
        FROM as_experiment 
        WHERE id = %s
        """

        results = await querier.execute_query(query, (id,))
        if not results:
            return JSONResponse(content={"error": "实验未找到"}, status_code=404)

        result = results[0]
        data = {
            "id": str(result['id']),
            "name": result['name'],
            "num_day": result['num_day'] or 0,
            "status": 'running' if result['status'] == 1 else 'completed' if result['status'] == 2 else 'unknown',
            "cur_day": result['cur_day'] or 0,
            "cur_t": result['cur_t'] or 0,
            "config": result['config'] or '',
            "error": result['error'] or '',
            "input_tokens": result['input_tokens'] or 0,
            "output_tokens": result['output_tokens'] or 0,
            "created_at": result['created_at'].isoformat() if result['created_at'] else '',
            "updated_at": result['updated_at'].isoformat() if result['updated_at'] else ''
        }
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content={"error": f"查询实验信息失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{id}/timeline")
async def get_experiment_timeline(id: str):
    """获取实验时间线"""
    try:
        steps = await querier.get_experiment_steps(id)
        timeline = []
        for step in steps:
            timeline.append({"day": step, "t": 0})  # 假设每步的时间为0
        return JSONResponse(content=timeline)
    except Exception as e:
        return JSONResponse(content={"error": f"查询实验时间线失败: {str(e)}"}, status_code=500)


# 2. Agent相关接口

@app.get("/api/experiments/{exp_id}/agents/-/profile")
async def get_all_agent_profiles(exp_id: str):
    """获取所有Agent档案，包含params和metrics"""
    try:
        # 获取run_uuid
        run_uuid = await mlflow_querier.get_run_uuid_by_experiment_id(exp_id)
        if not run_uuid:
            return JSONResponse(content={"error": "未找到对应的MLflow运行记录"}, status_code=404)

        companies = await querier.get_experiment_companies(exp_id)
        profiles = []

        for company in companies:
            agent_id = company['company_id']
            agent_name = company['company_name']

            # 获取该agent的所有params
            all_params = await mlflow_querier.get_all_params_by_run_uuid(run_uuid)
            agent_params = {k: v for k, v in all_params.items() if agent_name in k}

            # 获取最新step的metrics
            latest_steps = await querier.get_experiment_steps(exp_id)
            latest_step = max(latest_steps) if latest_steps else 0

            all_metrics = await mlflow_querier.get_metrics_by_run_uuid_and_step(run_uuid, latest_step)
            agent_metrics = {k: v for k, v in all_metrics.items() if agent_name in k}

            profile_data = {
                "id": agent_id,
                "name": agent_name,
                "profile": {
                    "company_id": agent_id,
                    "company_name": agent_name,
                    "params": agent_params,
                    "metrics": agent_metrics,
                    "latest_step": latest_step
                }
            }
            profiles.append(profile_data)

        return JSONResponse(content=profiles)
    except Exception as e:
        return JSONResponse(content={"error": f"查询Agent档案失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/agents/{agent_id}/profile")
async def get_agent_profile(exp_id: str, agent_id: int):
    """获取特定Agent档案，包含params和metrics"""
    try:
        # 获取run_uuid
        run_uuid = await mlflow_querier.get_run_uuid_by_experiment_id(exp_id)
        if not run_uuid:
            return JSONResponse(content={"error": "未找到对应的MLflow运行记录"}, status_code=404)

        # 获取agent基本信息
        query = """
        SELECT DISTINCT company_id, company_name 
        FROM company_states 
        WHERE experiment_id = %s AND company_id = %s
        """
        results = await querier.execute_query(query, (exp_id, agent_id))
        if not results:
            return JSONResponse(content={"error": "Agent未找到"}, status_code=404)

        company = results[0]
        agent_name = company['company_name']

        # 获取该agent的所有params
        all_params = await mlflow_querier.get_all_params_by_run_uuid(run_uuid)
        agent_params = {k: v for k, v in all_params.items() if agent_name in k}

        # 获取最新step的metrics
        latest_steps = await querier.get_experiment_steps(exp_id)
        latest_step = max(latest_steps) if latest_steps else 0

        all_metrics = await mlflow_querier.get_metrics_by_run_uuid_and_step(run_uuid, latest_step)
        agent_metrics = {k: v for k, v in all_metrics.items() if agent_name in k}

        # 获取所有step的metrics
        historical_metrics = {}
        all_steps = await querier.get_experiment_steps(exp_id)
        for step in all_steps:
            step_metrics = await mlflow_querier.get_metrics_by_run_uuid_and_step(run_uuid, step)
            step_agent_metrics = {k: v for k, v in step_metrics.items() if agent_name in k}
            if step_agent_metrics:
                historical_metrics[f"step_{step}"] = step_agent_metrics

        data = {
            "id": company['company_id'],
            "name": agent_name,
            "profile": {
                "company_id": company['company_id'],
                "company_name": agent_name,
                "params": agent_params,
                "metrics": agent_metrics,
                "historical_metrics": historical_metrics,
                "latest_step": latest_step,
                "run_uuid": run_uuid
            }
        }
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content={"error": f"查询Agent档案失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/agents/-/status")
async def get_all_agent_status(exp_id: str, day: int = Query(...), t: int = Query(...)):
    """获取所有Agent状态（按时间）"""
    try:
        # 使用step作为day
        step_data = await querier.get_company_state_by_step(exp_id, day)
        statuses = []
        for company_data in step_data:
            statuses.append({
                "id": company_data['company_id'],
                "day": company_data['step'],
                "t": t,
                "action": "business_operation",
                "status": {
                    "company_name": company_data['company_name'],
                    "transaction_count": len(company_data['transaction_list']),
                    "record_count": len(company_data['records'])
                },
                "created_at": datetime.now().isoformat()
            })
        return JSONResponse(content=statuses)
    except Exception as e:
        return JSONResponse(content={"error": f"查询Agent状态失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/agents/{agent_id}/status")
async def get_agent_status_history(exp_id: str, agent_id: int):
    """获取特定Agent状态历史"""
    try:
        query = """
        SELECT 
            company_id,
            step,
            company_name,
            created_at
        FROM company_states 
        WHERE experiment_id = %s AND company_id = %s
        ORDER BY step
        """
        results = await querier.execute_query(query, (exp_id, agent_id))

        statuses = []
        for result in results:
            statuses.append({
                "id": result['company_id'],
                "day": result['step'],
                "t": 0,
                "action": "business_operation",
                "status": {"company_name": result['company_name']},
                "created_at": result['created_at'].isoformat() if result['created_at'] else datetime.now().isoformat()
            })
        return JSONResponse(content=statuses)
    except Exception as e:
        return JSONResponse(content={"error": f"查询Agent状态历史失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/agents/{agent_id}/dialog")
async def get_agent_dialog(exp_id: str, agent_id: int):
    """获取特定Agent对话记录"""
    try:
        # 查询公司基本信息
        company_query = """
        SELECT DISTINCT cs.company_name
        FROM company_states cs
        WHERE cs.experiment_id = %s AND cs.company_id = %s
        LIMIT 1
        """
        company_results = await querier.execute_query(company_query, (exp_id, agent_id))
        company_name = company_results[0]['company_name'] if company_results else f"Company_{agent_id}"

        # 查询记录数据，按步骤分组
        query = """
        SELECT 
            cr.step,
            cr.company_id,
            cr.source_company_id,
            cr.source_company_name,
            cr.operation_type,
            cr.timestamp_value,
            cr.raw_content,
            cr.created_at
        FROM company_records cr
        WHERE cr.experiment_id = %s AND cr.company_id = %s
        ORDER BY cr.step, cr.timestamp_value, cr.created_at
        """
        results = await querier.execute_query(query, (exp_id, agent_id))

        # 按步骤分组数据
        step_data = {}
        for result in results:
            step = result['step']
            if step not in step_data:
                step_data[step] = []

            # 构造record项
            record_item = {
                "source": result['source_company_id'],
                "sourceName": result['source_company_name'] or "system",
                "content": {
                    "content": json.dumps(result['raw_content'], ensure_ascii=False) if result['raw_content'] else "",
                    "type": result['operation_type'] or "unknown",
                    "timestamp": result['timestamp_value'] or int(datetime.now().timestamp() * 1000),
                    "from": result['source_company_id']  # 保持兼容性
                },
            }
            step_data[step].append(record_item)

        # 构造前端期望的数据格式
        dialogs = []
        for step, records in step_data.items():
            dialogs.append({
                "step": step,
                "id": agent_id,
                "company_name": company_name,
                "record": records
            })

        # 按步骤排序
        dialogs.sort(key=lambda x: x['step'])

        return JSONResponse(content=dialogs)
    except Exception as e:
        return JSONResponse(content={"error": f"查询Agent对话记录失败: {str(e)}"}, status_code=500)


# 3. 全局提示接口

@app.get("/api/experiments/{exp_id}/prompt")
async def get_global_prompt(exp_id: str, day: int = Query(...), t: int = Query(...)):
    """获取全局提示（Market Insight）"""
    try:
        # 基于交易数据生成市场洞察
        transaction_summary = await querier.get_transaction_summary(exp_id, (day, day))

        if not transaction_summary:
            data = [{
                "day": day,
                "t": t,
                "prompt": f"第{day}天暂无交易活动",
                "created_at": datetime.now().isoformat()
            }]
            return JSONResponse(content=data)

        # 生成市场洞察提示
        total_transactions = len(transaction_summary)
        total_value = sum(float(trans['total_value'] or 0) for trans in transaction_summary)

        prompt = f"第{day}天市场概况：共发生{total_transactions}笔交易，总交易额{total_value:.2f}。"

        # 添加热门产品信息
        product_stats = {}
        for trans in transaction_summary:
            product = trans['product_name']
            if product not in product_stats:
                product_stats[product] = {'count': 0, 'value': 0}
            product_stats[product]['count'] += trans['transaction_count']
            product_stats[product]['value'] += float(trans['total_value'] or 0)

        if product_stats:
            top_product = max(product_stats.items(), key=lambda x: x[1]['value'])
            prompt += f" 热门产品：{top_product[0]}（交易额{top_product[1]['value']:.2f}）。"

        data = [{
            "day": day,
            "t": t,
            "prompt": prompt,
            "created_at": datetime.now().isoformat()
        }]
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content={"error": f"查询全局提示失败: {str(e)}"}, status_code=500)


# 额外的实用接口

@app.get("/api/experiments")
async def get_all_experiments():
    """获取所有实验列表"""
    try:
        experiments = await querier.get_experiments()
        return JSONResponse(content=experiments)
    except Exception as e:
        return JSONResponse(content={"error": f"查询实验列表失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/companies")
async def get_experiment_companies(exp_id: str):
    """获取实验中的所有公司"""
    try:
        companies = await querier.get_experiment_companies(exp_id)
        return JSONResponse(content=companies)
    except Exception as e:
        return JSONResponse(content={"error": f"查询公司列表失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/transactions")
async def get_transaction_summary_api(exp_id: str, start_step: Optional[int] = None, end_step: Optional[int] = None):
    """获取交易汇总"""
    try:
        step_range = None
        if start_step is not None and end_step is not None:
            step_range = (start_step, end_step)

        transactions = await querier.get_transaction_summary(exp_id, step_range)
        return JSONResponse(content=transactions)
    except Exception as e:
        return JSONResponse(content={"error": f"查询交易汇总失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/communications")
async def get_communication_summary_api(
        exp_id: str,
        operation_type: Optional[str] = None,
        include_details: Optional[bool] = Query(False, description="是否包含详细对话内容"),
        step: Optional[int] = Query(None, description="指定步骤查询")
):
    """获取通信汇总

    Args:
        exp_id: 实验ID
        operation_type: 操作类型过滤 (operation-price, operation-deal, operation-build, operation-reject)
        include_details: 是否包含详细对话内容，默认为False只返回汇总统计
        step: 指定步骤查询，可选

    Returns:
        如果include_details=False: 返回汇总统计信息
        如果include_details=True: 返回详细对话内容，包含detail字段
        如果指定step: 只返回该步骤的数据
    """
    try:
        communications = await querier.get_communication_summary(exp_id, operation_type, include_details, step)

        response_data = {
            "experiment_id": exp_id,
            "operation_type_filter": operation_type,
            "include_details": include_details,
            "step_filter": step,
            "total_records": len(communications),
            "communications": communications
        }

        if include_details:
            # 按operation_type分组统计
            type_stats = {}
            for comm in communications:
                op_type = comm['operation_type']
                if op_type not in type_stats:
                    type_stats[op_type] = 0
                type_stats[op_type] += 1
            response_data["operation_type_stats"] = type_stats

        if step is not None:
            response_data["step_summary"] = f"第{step}步的通信记录"

        return JSONResponse(content=response_data)
    except Exception as e:
        return JSONResponse(content={"error": f"查询通信汇总失败: {str(e)}"}, status_code=500)


# 健康检查接口
@app.get("/health")
async def health_check():
    """健康检查"""
    data = {"status": "healthy", "timestamp": datetime.now().isoformat()}
    return JSONResponse(content=data)


# 在现有的API基础上添加新的端点

@app.get("/api/experiments/{exp_id}/intelligence")
async def get_intelligence_distribution(id: str):
    """获取实验中企业智能等级分布"""
    try:
        distribution = await mlflow_querier.get_company_intelligence_distribution(id)
        return JSONResponse(content=distribution)
    except Exception as e:
        return JSONResponse(content={"error": f"查询智能等级分布失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/inventory")
async def get_inventory_summary(id: str, step: Optional[int] = Query(None)):
    """获取实验库存汇总信息"""
    try:
        summary = await mlflow_querier.get_inventory_summary(id, step)
        return JSONResponse(content=summary)
    except Exception as e:
        return JSONResponse(content={"error": f"查询库存信息失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/companies/{company_id}/inventory")
async def get_company_inventory(id: str, company_id: int, step: Optional[int] = Query(None)):
    """获取特定企业的库存详情"""
    try:
        if step is None:
            # 获取最新步骤
            steps = await querier.get_experiment_steps(id)
            step = max(steps) if steps else 0

        company_data = await querier.get_company_state_by_step(id, step, company_id)
        if not company_data:
            return JSONResponse(content={"error": "企业数据未找到"}, status_code=404)

        company = company_data[0]
        inventory_data = {
            'company_id': company['company_id'],
            'company_name': company['company_name'],
            'intelligence_level': company.get('intelligence_level'),
            'inventory_system': company.get('inventory_system'),
            'step': step
        }

        return JSONResponse(content=inventory_data)
    except Exception as e:
        return JSONResponse(content={"error": f"查询企业库存失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/metrics")
async def get_all_companies_metrics_by_step(exp_id: str, step: int = Query(...)):
    """获取特定步骤所有企业的metrics"""
    try:
        # 获取run_uuid
        run_uuid = await mlflow_querier.get_run_uuid_by_experiment_id(exp_id)
        if not run_uuid:
            return JSONResponse(content={"error": "未找到对应的MLflow运行记录"}, status_code=404)

        # 获取实验中的所有公司
        companies = await querier.get_experiment_companies(exp_id)

        # 获取指定step的所有metrics
        all_metrics = await mlflow_querier.get_metrics_by_run_uuid_and_step(run_uuid, step)

        # 为每个公司整理metrics数据
        companies_metrics = []
        for company in companies:
            company_id = company['company_id']
            company_name = company['company_name']

            # 过滤出该公司的metrics
            company_metrics = {k: v for k, v in all_metrics.items() if company_name in k}

            companies_metrics.append({
                "company_id": company_id,
                "company_name": company_name,
                "step": step,
                "metrics": company_metrics
            })

        return JSONResponse(content={
            "experiment_id": exp_id,
            "step": step,
            "companies_metrics": companies_metrics,
            "total_companies": len(companies_metrics)
        })
    except Exception as e:
        return JSONResponse(content={"error": f"查询企业metrics失败: {str(e)}"}, status_code=500)


# 在现有的API基础上添加新的端点

@app.get("/api/experiments/{exp_id}/max-step")
async def get_experiment_max_step(exp_id: str):
    """获取实验的最大step"""
    try:
        # 获取实验的所有步骤
        steps = await querier.get_experiment_steps(exp_id)

        if not steps:
            return JSONResponse(content={
                "experiment_id": exp_id,
                "max_step": 0,
                "total_steps": 0,
                "message": "实验暂无步骤数据"
            })

        max_step = max(steps)
        total_steps = len(steps)

        return JSONResponse(content={
            "experiment_id": exp_id,
            "max_step": max_step,
            "total_steps": total_steps,
            "all_steps": sorted(steps)
        })
    except Exception as e:
        return JSONResponse(content={"error": f"查询实验最大步骤失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/agents/{agent_id}/metrics")
async def get_agent_metrics_by_step(exp_id: str, agent_id: int, step: int = Query(...)):
    """获取特定步骤中特定agent的metrics数据"""
    try:
        # 获取run_uuid
        run_uuid = await mlflow_querier.get_run_uuid_by_experiment_id(exp_id)
        if not run_uuid:
            return JSONResponse(content={"error": "未找到对应的MLflow运行记录"}, status_code=404)

        # 获取agent基本信息
        query = """
        SELECT DISTINCT company_id, company_name 
        FROM company_states 
        WHERE experiment_id = %s AND company_id = %s
        """
        results = await querier.execute_query(query, (exp_id, agent_id))
        if not results:
            return JSONResponse(content={"error": "Agent未找到"}, status_code=404)

        company = results[0]
        agent_name = company['company_name']

        # 获取指定step的metrics
        all_metrics = await mlflow_querier.get_metrics_by_run_uuid_and_step(run_uuid, step)
        agent_metrics = {k: v for k, v in all_metrics.items() if agent_name in k}

        data = {
            "experiment_id": exp_id,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "step": step,
            "metrics": agent_metrics,
            "run_uuid": run_uuid
        }

        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content={"error": f"查询Agent metrics失败: {str(e)}"}, status_code=500)


# 新增的原料相关API接口
@app.get("/api/experiments/{exp_id}/agents/{agent_id}/products/{product_id}/materials")
async def get_product_required_materials(exp_id: str, agent_id: int, product_id: int,
                                         step: Optional[int] = Query(None)):
    """获取指定agent某个产品所需原料"""
    try:
        if step is None:
            # 默认获取step0的数据
            step = 0

        # 获取企业数据
        company_data = await querier.get_company_state_by_step(exp_id, step, agent_id)
        if not company_data:
            return JSONResponse(content={"error": "企业数据未找到"}, status_code=404)

        company = company_data[0]

        # 从inventory_system中获取产品信息
        inventory_system = company.get('inventory_system', {})
        if isinstance(inventory_system, str):
            import json
            inventory_system = json.loads(inventory_system)

        products = inventory_system.get('products', {})
        materials = inventory_system.get('materials', {})

        # 查找指定产品
        target_product = None
        product_key = str(product_id)

        if product_key in products:
            target_product = products[product_key]
            # 从产品的related_materials中获取所需原料
            related_materials = target_product.get('related_materials', [])
        else:
            return JSONResponse(content={"error": f"产品ID {product_id} 未找到"}, status_code=404)

        # 构建所需原料列表，包含当前库存信息
        required_materials_list = []
        for material in related_materials:
            material_id = str(material.get('material_id', material.get('product_id', '')))
            material_name = material.get('material_name', material.get('product_name', ''))

            # 从materials库存中获取当前数量
            current_quantity = materials.get(material_id, {}).get('quantity', 0)

            required_materials_list.append({
                'material_id': material.get('material_id', material.get('product_id')),
                'material_name': material_name,
                'current_quantity': current_quantity,
                'required_for_production': True
            })

        result = {
            'experiment_id': exp_id,
            'agent_id': agent_id,
            'agent_name': company.get('company_name'),
            'product_id': product_id,
            'product_name': target_product.get('product_name'),
            'product_construct': target_product.get('product_construct', ''),
            'required_materials': required_materials_list,
            'step': step
        }

        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={"error": f"查询产品所需原料失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/agents/{agent_id}/required-materials")
async def get_agent_all_required_materials(exp_id: str, agent_id: int, step: Optional[int] = Query(None)):
    """获取指定agent所需要的所有原料"""
    try:
        if step is None:
            # 默认获取step0的数据
            step = 0

        # 获取企业数据
        company_data = await querier.get_company_state_by_step(exp_id, step, agent_id)
        if not company_data:
            return JSONResponse(content={"error": "企业数据未找到"}, status_code=404)

        company = company_data[0]

        # 从inventory_system中获取materials信息
        inventory_system = company.get('inventory_system', {})
        if isinstance(inventory_system, str):
            import json
            inventory_system = json.loads(inventory_system)

        materials = inventory_system.get('materials', {})

        # 构建所需原料列表
        required_materials = []
        for material_id, material_info in materials.items():
            required_materials.append({
                'material_id': int(material_id),
                'material_name': material_info.get('product_name'),
                'current_quantity': material_info.get('quantity', 0),
                'is_sufficient': material_info.get('quantity', 0) > 0
            })

        result = {
            'experiment_id': exp_id,
            'agent_id': agent_id,
            'agent_name': company.get('company_name'),
            'intelligence_level': company.get('intelligence_level'),
            'total_required_materials': len(required_materials),
            'required_materials': required_materials,
            'step': step
        }

        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={"error": f"查询所需原料失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/agents/{agent_id}/available-materials")
async def get_agent_available_materials(exp_id: str, agent_id: int, step: Optional[int] = Query(None)):
    """获取指定agent所能提供的原材料"""
    try:
        if step is None:
            # 默认获取step0的数据
            step = 0

        # 获取企业数据
        company_data = await querier.get_company_state_by_step(exp_id, step, agent_id)
        if not company_data:
            return JSONResponse(content={"error": "企业数据未找到"}, status_code=404)

        company = company_data[0]

        # 从inventory_system中获取products信息（这些产品可以作为原材料提供给其他企业）
        inventory_system = company.get('inventory_system', {})
        if isinstance(inventory_system, str):
            import json
            inventory_system = json.loads(inventory_system)

        products = inventory_system.get('products', {})

        # 构建可提供的原材料列表
        available_materials = []
        for product_id, product_info in products.items():
            available_materials.append({
                'material_id': int(product_id),
                'material_name': product_info.get('product_name'),
                'available_quantity': product_info.get('quantity', 0),
                'can_supply': product_info.get('quantity', 0) > 0
            })

        result = {
            'experiment_id': exp_id,
            'agent_id': agent_id,
            'agent_name': company.get('company_name'),
            'intelligence_level': company.get('intelligence_level'),
            'total_available_materials': len(available_materials),
            'available_materials': available_materials,
            'step': step
        }

        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={"error": f"查询可提供原材料失败: {str(e)}"}, status_code=500)


# 细化的企业信息获取接口

@app.get("/api/experiments/{exp_id}/agents/{agent_id}/company-id")
async def get_agent_company_id(exp_id: str, agent_id: int):
    """获取企业ID"""
    try:
        # 获取agent基本信息
        query = """
        SELECT DISTINCT company_id 
        FROM company_states 
        WHERE experiment_id = %s AND company_id = %s
        """
        results = await querier.execute_query(query, (exp_id, agent_id))
        if not results:
            return JSONResponse(content={"error": "企业未找到"}, status_code=404)

        data = {
            "experiment_id": exp_id,
            "company_id": results[0]['company_id']
        }
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content={"error": f"查询企业ID失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/agents/{agent_id}/company-name")
async def get_agent_company_name(exp_id: str, agent_id: int):
    """获取企业名称"""
    try:
        # 获取agent基本信息
        query = """
        SELECT DISTINCT company_name 
        FROM company_states 
        WHERE experiment_id = %s AND company_id = %s
        """
        results = await querier.execute_query(query, (exp_id, agent_id))
        if not results:
            return JSONResponse(content={"error": "企业未找到"}, status_code=404)

        data = {
            "experiment_id": exp_id,
            "agent_id": agent_id,
            "company_name": results[0]['company_name']
        }
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content={"error": f"查询企业名称失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/agents/{agent_id}/company-fund")
async def get_agent_company_fund(exp_id: str, agent_id: int, step: Optional[int] = Query(None)):
    """获取企业资金"""
    try:
        # 获取run_uuid
        run_uuid = await mlflow_querier.get_run_uuid_by_experiment_id(exp_id)
        if not run_uuid:
            return JSONResponse(content={"error": "未找到对应的MLflow运行记录"}, status_code=404)

        # 获取agent基本信息
        query = """
        SELECT DISTINCT company_name 
        FROM company_states 
        WHERE experiment_id = %s AND company_id = %s
        """
        results = await querier.execute_query(query, (exp_id, agent_id))
        if not results:
            return JSONResponse(content={"error": "企业未找到"}, status_code=404)

        agent_name = results[0]['company_name']

        # 如果没有指定步骤，获取最新步骤
        if step is None:
            latest_steps = await querier.get_experiment_steps(exp_id)
            step = max(latest_steps) if latest_steps else 0

        # 获取指定步骤的资金metrics
        all_metrics = await mlflow_querier.get_metrics_by_run_uuid_and_step(run_uuid, step)
        fund_key = f"company_fund_{agent_name}"
        company_fund = all_metrics.get(fund_key, 0)

        data = {
            "experiment_id": exp_id,
            "agent_id": agent_id,
            "company_name": agent_name,
            "step": step,
            "company_fund": company_fund
        }
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content={"error": f"查询企业资金失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/agents/{agent_id}/intelligence-level")
async def get_agent_intelligence_level(exp_id: str, agent_id: int):
    """获取企业智能水平"""
    try:
        # 获取run_uuid
        run_uuid = await mlflow_querier.get_run_uuid_by_experiment_id(exp_id)
        if not run_uuid:
            return JSONResponse(content={"error": "未找到对应的MLflow运行记录"}, status_code=404)

        # 获取agent基本信息
        query = """
        SELECT DISTINCT company_name 
        FROM company_states 
        WHERE experiment_id = %s AND company_id = %s
        """
        results = await querier.execute_query(query, (exp_id, agent_id))
        if not results:
            return JSONResponse(content={"error": "企业未找到"}, status_code=404)

        agent_name = results[0]['company_name']

        # 获取该agent的所有params
        all_params = await mlflow_querier.get_all_params_by_run_uuid(run_uuid)
        intelligence_key = f"intelligence_level_{agent_name}"
        intelligence_level = all_params.get(intelligence_key, "1")

        data = {
            "experiment_id": exp_id,
            "agent_id": agent_id,
            "company_name": agent_name,
            "intelligence_level": int(intelligence_level)
        }
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content={"error": f"查询企业智能水平失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/agents/{agent_id}/products")
async def get_agent_products(exp_id: str, agent_id: int, step: Optional[int] = Query(None)):
    """获取企业所有产品信息"""
    try:
        if step is None:
            step = 0

        # 获取企业数据
        company_data = await querier.get_company_state_by_step(exp_id, step, agent_id)
        if not company_data:
            return JSONResponse(content={"error": "企业数据未找到"}, status_code=404)

        company = company_data[0]

        # 从inventory_system中获取产品信息
        inventory_system = company.get('inventory_system', {})
        if isinstance(inventory_system, str):
            import json
            inventory_system = json.loads(inventory_system)

        products = inventory_system.get('products', {})

        # 整理产品信息
        product_list = []
        for product_id, product_info in products.items():
            product_list.append({
                "product_id": product_id,
                "product_name": product_info.get('product_name', f'product_{product_id}'),
                "base_price": product_info.get('base_price', 0),
                "manufacturing_cost": product_info.get('manufacturing_cost', 0),
                "profit_margin": product_info.get('profit_margin', 0),
                "is_terminal_product": product_info.get('is_terminal_product', False),
                "product_construct": product_info.get('product_construct', ''),
                "related_materials": product_info.get('related_materials', [])
            })

        data = {
            "experiment_id": exp_id,
            "agent_id": agent_id,
            "company_name": company.get('company_name', f'Company_{agent_id}'),
            "step": step,
            "products": product_list
        }

        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content={"error": f"查询企业产品信息失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/agents/{agent_id}/materials")
async def get_agent_materials(exp_id: str, agent_id: int, step: Optional[int] = Query(None)):
    """获取企业所有原料信息"""
    try:
        if step is None:
            step = 0

        # 获取企业数据
        company_data = await querier.get_company_state_by_step(exp_id, step, agent_id)
        if not company_data:
            return JSONResponse(content={"error": "企业数据未找到"}, status_code=404)

        company = company_data[0]

        # 从inventory_system中获取原料信息
        inventory_system = company.get('inventory_system', {})
        if isinstance(inventory_system, str):
            import json
            inventory_system = json.loads(inventory_system)

        materials = inventory_system.get('materials', {})

        # 整理原料信息
        material_list = []
        for material_id, material_info in materials.items():
            material_list.append({
                "material_id": material_id,
                "material_name": material_info.get('product_name', f'material_{material_id}'),
                "current_quantity": material_info.get('quantity', 0),
                "unit_price": material_info.get('unit_price', 0),
                "supplier_info": material_info.get('supplier_info', {})
            })

        data = {
            "experiment_id": exp_id,
            "agent_id": agent_id,
            "company_name": company.get('company_name', f'Company_{agent_id}'),
            "step": step,
            "materials": material_list
        }

        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content={"error": f"查询企业原料信息失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/agents/{agent_id}/material-inventory-ratio")
async def get_agent_material_inventory_ratio(exp_id: str, agent_id: int, step: Optional[int] = Query(None)):
    """获取企业原料库存比率"""
    try:
        # 获取run_uuid
        run_uuid = await mlflow_querier.get_run_uuid_by_experiment_id(exp_id)
        if not run_uuid:
            return JSONResponse(content={"error": "未找到对应的MLflow运行记录"}, status_code=404)

        # 获取agent基本信息
        query = """
        SELECT DISTINCT company_name 
        FROM company_states 
        WHERE experiment_id = %s AND company_id = %s
        """
        results = await querier.execute_query(query, (exp_id, agent_id))
        if not results:
            return JSONResponse(content={"error": "企业未找到"}, status_code=404)

        agent_name = results[0]['company_name']

        # 如果没有指定步骤，获取最新步骤
        if step is None:
            latest_steps = await querier.get_experiment_steps(exp_id)
            step = max(latest_steps) if latest_steps else 0

        # 获取指定步骤的metrics
        all_metrics = await mlflow_querier.get_metrics_by_run_uuid_and_step(run_uuid, step)
        ratio_key = f"material_inventory_ratio_{agent_name}"
        material_inventory_ratio = all_metrics.get(ratio_key, 0.0)

        data = {
            "experiment_id": exp_id,
            "agent_id": agent_id,
            "company_name": agent_name,
            "step": step,
            "material_inventory_ratio": material_inventory_ratio
        }
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content={"error": f"查询原料库存比率失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/agents/{agent_id}/product-inventory-ratio")
async def get_agent_product_inventory_ratio(exp_id: str, agent_id: int, step: Optional[int] = Query(None)):
    """获取企业产品库存比率"""
    try:
        # 获取run_uuid
        run_uuid = await mlflow_querier.get_run_uuid_by_experiment_id(exp_id)
        if not run_uuid:
            return JSONResponse(content={"error": "未找到对应的MLflow运行记录"}, status_code=404)

        # 获取agent基本信息
        query = """
        SELECT DISTINCT company_name 
        FROM company_states 
        WHERE experiment_id = %s AND company_id = %s
        """
        results = await querier.execute_query(query, (exp_id, agent_id))
        if not results:
            return JSONResponse(content={"error": "企业未找到"}, status_code=404)

        agent_name = results[0]['company_name']

        # 如果没有指定步骤，获取最新步骤
        if step is None:
            latest_steps = await querier.get_experiment_steps(exp_id)
            step = max(latest_steps) if latest_steps else 0

        # 获取指定步骤的metrics
        all_metrics = await mlflow_querier.get_metrics_by_run_uuid_and_step(run_uuid, step)
        ratio_key = f"product_inventory_ratio_{agent_name}"
        product_inventory_ratio = all_metrics.get(ratio_key, 0.0)

        data = {
            "experiment_id": exp_id,
            "agent_id": agent_id,
            "company_name": agent_name,
            "step": step,
            "product_inventory_ratio": product_inventory_ratio
        }
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content={"error": f"查询产品库存比率失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/agents/{agent_id}/net-transaction-amount")
async def get_agent_net_transaction_amount(exp_id: str, agent_id: int, step: Optional[int] = Query(None)):
    """获取企业净交易金额"""
    try:
        # 获取run_uuid
        run_uuid = await mlflow_querier.get_run_uuid_by_experiment_id(exp_id)
        if not run_uuid:
            return JSONResponse(content={"error": "未找到对应的MLflow运行记录"}, status_code=404)

        # 获取agent基本信息
        query = """
        SELECT DISTINCT company_name 
        FROM company_states 
        WHERE experiment_id = %s AND company_id = %s
        """
        results = await querier.execute_query(query, (exp_id, agent_id))
        if not results:
            return JSONResponse(content={"error": "企业未找到"}, status_code=404)

        agent_name = results[0]['company_name']

        # 如果没有指定步骤，获取最新步骤
        if step is None:
            latest_steps = await querier.get_experiment_steps(exp_id)
            step = max(latest_steps) if latest_steps else 0

        # 获取指定步骤的metrics
        all_metrics = await mlflow_querier.get_metrics_by_run_uuid_and_step(run_uuid, step)
        amount_key = f"net_transaction_amount_{agent_name}"
        net_transaction_amount = all_metrics.get(amount_key, 0.0)

        data = {
            "experiment_id": exp_id,
            "agent_id": agent_id,
            "company_name": agent_name,
            "step": step,
            "net_transaction_amount": net_transaction_amount
        }
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content={"error": f"查询净交易金额失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/agents/{agent_id}/supply-info")
async def get_agent_supply_info(exp_id: str, agent_id: int, step: Optional[int] = Query(None)):
    """获取企业供应信息（包括总量、金额、订单数）"""
    try:
        # 获取run_uuid
        run_uuid = await mlflow_querier.get_run_uuid_by_experiment_id(exp_id)
        if not run_uuid:
            return JSONResponse(content={"error": "未找到对应的MLflow运行记录"}, status_code=404)

        # 获取agent基本信息
        query = """
        SELECT DISTINCT company_name 
        FROM company_states 
        WHERE experiment_id = %s AND company_id = %s
        """
        results = await querier.execute_query(query, (exp_id, agent_id))
        if not results:
            return JSONResponse(content={"error": "企业未找到"}, status_code=404)

        agent_name = results[0]['company_name']

        # 如果没有指定步骤，获取最新步骤
        if step is None:
            latest_steps = await querier.get_experiment_steps(exp_id)
            step = max(latest_steps) if latest_steps else 0

        # 获取指定步骤的metrics
        all_metrics = await mlflow_querier.get_metrics_by_run_uuid_and_step(run_uuid, step)

        # 获取供应相关指标
        supply_quantity_key = f"supply_total_quantity_{agent_name}"
        supply_amount_key = f"supply_total_amount_{agent_name}"
        supply_orders_key = f"supply_total_orders_{agent_name}"

        supply_total_quantity = all_metrics.get(supply_quantity_key, 0)
        supply_total_amount = all_metrics.get(supply_amount_key, 0.0)
        supply_total_orders = all_metrics.get(supply_orders_key, 0)

        data = {
            "experiment_id": exp_id,
            "agent_id": agent_id,
            "company_name": agent_name,
            "step": step,
            "supply_info": {
                "total_quantity": supply_total_quantity,
                "total_amount": supply_total_amount,
                "total_orders": supply_total_orders
            }
        }
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content={"error": f"查询供应信息失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/agents/{agent_id}/purchase-info")
async def get_agent_purchase_info(exp_id: str, agent_id: int, step: Optional[int] = Query(None)):
    """获取企业采购信息（包括总量、金额、订单数）"""
    try:
        # 获取run_uuid
        run_uuid = await mlflow_querier.get_run_uuid_by_experiment_id(exp_id)
        if not run_uuid:
            return JSONResponse(content={"error": "未找到对应的MLflow运行记录"}, status_code=404)

        # 获取agent基本信息
        query = """
        SELECT DISTINCT company_name 
        FROM company_states 
        WHERE experiment_id = %s AND company_id = %s
        """
        results = await querier.execute_query(query, (exp_id, agent_id))
        if not results:
            return JSONResponse(content={"error": "企业未找到"}, status_code=404)

        agent_name = results[0]['company_name']

        # 如果没有指定步骤，获取最新步骤
        if step is None:
            latest_steps = await querier.get_experiment_steps(exp_id)
            step = max(latest_steps) if latest_steps else 0

        # 获取指定步骤的metrics
        all_metrics = await mlflow_querier.get_metrics_by_run_uuid_and_step(run_uuid, step)

        # 获取采购相关指标
        purchase_quantity_key = f"purchase_total_quantity_{agent_name}"
        purchase_amount_key = f"purchase_total_amount_{agent_name}"
        purchase_orders_key = f"purchase_total_orders_{agent_name}"

        purchase_total_quantity = all_metrics.get(purchase_quantity_key, 0)
        purchase_total_amount = all_metrics.get(purchase_amount_key, 0.0)
        purchase_total_orders = all_metrics.get(purchase_orders_key, 0)

        data = {
            "experiment_id": exp_id,
            "agent_id": agent_id,
            "company_name": agent_name,
            "step": step,
            "purchase_info": {
                "total_quantity": purchase_total_quantity,
                "total_amount": purchase_total_amount,
                "total_orders": purchase_total_orders
            }
        }
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content={"error": f"查询采购信息失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/agents/{agent_id}/inventory-summary")
async def get_agent_inventory_summary(exp_id: str, agent_id: int, step: Optional[int] = Query(None)):
    """获取企业当前库存汇总（总库存，总原料库存，总产品库存）"""
    try:
        # 获取run_uuid
        run_uuid = await mlflow_querier.get_run_uuid_by_experiment_id(exp_id)
        if not run_uuid:
            return JSONResponse(content={"error": "未找到对应的MLflow运行记录"}, status_code=404)

        # 获取agent基本信息
        query = """
        SELECT DISTINCT company_name 
        FROM company_states 
        WHERE experiment_id = %s AND company_id = %s
        """
        results = await querier.execute_query(query, (exp_id, agent_id))
        if not results:
            return JSONResponse(content={"error": "企业未找到"}, status_code=404)

        agent_name = results[0]['company_name']

        # 如果没有指定步骤，获取最新步骤
        if step is None:
            latest_steps = await querier.get_experiment_steps(exp_id)
            step = max(latest_steps) if latest_steps else 0

        # 获取指定步骤的metrics
        all_metrics = await mlflow_querier.get_metrics_by_run_uuid_and_step(run_uuid, step)

        # 获取库存相关指标
        total_inventory_key = f"total_inventory_{agent_name}"
        total_inventory = all_metrics.get(total_inventory_key, 0)

        # 计算原料和产品库存（从详细metrics中筛选）
        material_inventory = 0
        product_inventory = 0

        for key, value in all_metrics.items():
            if agent_name in key:
                if "material_inventory" in key.lower() and "ratio" not in key.lower():
                    material_inventory += value
                elif "product_inventory" in key.lower() and "ratio" not in key.lower():
                    product_inventory += value

        data = {
            "experiment_id": exp_id,
            "agent_id": agent_id,
            "company_name": agent_name,
            "step": step,
            "total_inventory": total_inventory,
            "total_material_inventory": material_inventory,
            "total_product_inventory": product_inventory
        }
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content={"error": f"查询库存汇总失败: {str(e)}"}, status_code=500)


@app.get("/api/experiments/{exp_id}/agents/{agent_id}/level")
async def get_agent_level(exp_id: str, agent_id: int, step: Optional[int] = Query(0)):
    """获取企业的level值，默认查询step=0时的level"""
    try:
        # 查询指定企业在指定step的level值
        query = """
        SELECT 
            company_id,
            company_name,
            level as level
        FROM company_states 
        WHERE experiment_id = %s AND company_id = %s AND step = %s
        LIMIT 1
        """
        results = await querier.execute_query(query, (exp_id, agent_id, step))

        if not results:
            return JSONResponse(content={"error": "未找到企业数据"}, status_code=404)

        result = results[0]
        data = {
            "experiment_id": exp_id,
            "agent_id": agent_id,
            "company_name": result['company_name'],
            "step": step,
            "level": result['level'] or 1  # 如果level为None，默认返回1
        }
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content={"error": f"查询企业level失败: {str(e)}"}, status_code=500)
