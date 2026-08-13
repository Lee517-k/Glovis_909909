const BackendApiUrl = "http://localhost:8000/api";

export class ApiError extends Error {
    message: string;

    constructor( message: string) {
        super("错误描述：" + message);
        this.message = message;
    }
}

export const ApiErrorCode = {
    UnknownError: -1,
    NoError: 0,
    LoginError: 1,
    Unauthenticated: 2,
    AccessDenied: 3,
    ObjectNotFound: 4,
    IllegalParameter: 5,
}

async function requestPassByBody(path: string, params?: object) {
    console.log("requestPassByBody:", path, params);
    let result;
    await fetch(BackendApiUrl + path)
     .then(response => response.json())
      .then(data => (result = data))
      .catch(error => console.error('Error fetching states:', error));
    console.log("result",result)
    return result;
}

async function requestPassByFormData(path: string, params?: { key: string, value: string | Blob }[]) {
    console.log("requestPassByFormData:", path, params);
    let formData = new FormData();
    if (params !== undefined) {
        for (let i = 0; i < params.length; i++) {
            formData.append(params[i].key, params[i].value);
        }
    }
    let res = await fetch(BackendApiUrl + path, {
        method: 'POST',
        headers: {
        },
        credentials: 'include',
        // mode: 'cors',
        body: formData
    });
    let resText = await res.text();
    let result = JSON.parse(resText);
    console.log("result:", JSON.parse(resText));
    return result.result;
}

interface QueryParam {
    key: string;
    value: null | number | string | boolean;
}

async function requestPassByParam(path: string, params: QueryParam[]) {
    console.log("requestPassByParam:", path, params);
    let url = new URL(BackendApiUrl + path);
    params.forEach((param) => {
        if (param.value !== null)
            url.searchParams.set(param.key, param.value.toString());
    });
    let res = await fetch(url.toString(), {
        mode: 'cors', 
        method: 'GET',
    });
    let resText = await res.text();
    let result = JSON.parse(resText);
    console.log("result:", JSON.parse(resText));
    return result.result;
}

async function getExperiments(exp_id){
    let url = "/experiments/" + exp_id;
    return await requestPassByBody(url);
}

async function getMarketInsight(exp_id,day,t){
    return await requestPassByParam("/experiments/{exp_id}/prompt?day={day}&t={t}", [{key: "exp_id", value: exp_id},{key: "day", value: day},{key:"t",value:t}]);
}

// 获取当前轮次所有agent信息
async function getAllAgent(exp_id){
    let url = "/experiments/" + exp_id+ "/agents/-/profile";
    return await requestPassByBody(url);
}

// 获取指定Agent所有轮次信息
async function getAgentStepInfo(exp_id,agent_id) {
    let url = "/experiments/" + exp_id + "/agents/" + agent_id + "/profile";
    return await requestPassByBody(url);
}

async function getAgentStatus(exp_id,agent_id) {
    let url = "/experiments/"+exp_id+"/agents/" + agent_id + "/status";
    return await requestPassByBody(url);
}

// 获取某个 Agent 的对话记录
async function getAgentDialog(exp_id,agent_id){
    let url = "/experiments/"+exp_id+"/agents/" + agent_id + "/dialog";
    return await requestPassByBody(url);
}

// 获取交易汇总
async function getTransaction(exp_id){
    let url = "/experiments/"+exp_id+"/transactions"
    return await requestPassByBody(url);
}

// 获取通信汇总
async function getCommunications(exp_id, include_details = false, step = null) {
    let url = "/experiments/"+exp_id+"/communications"
    let params = [];

    if (include_details) {
        params.push("include_details=true");
    }

    if (step !== null && step !== undefined) {
        params.push(`step=${step}`);
    }

    if (params.length > 0) {
        url += "?" + params.join("&");
    }

    return await requestPassByBody(url);
}

async function getCompanies(exp_id) {
    let url = "/experiments/"+exp_id+"/companies"
    return await requestPassByBody(url);
}

// 获取Agent所需原料
async function getAgentRequiredMaterials(exp_id, agent_id, step = null) {
    let url = `/experiments/${exp_id}/agents/${agent_id}/required-materials`;
    if (step !== null) {
        url += `?step=${step}`;
    }
    return await requestPassByBody(url);
}

// 获取Agent可提供原料
async function getAgentAvailableMaterials(exp_id, agent_id, step = null) {
    let url = `/experiments/${exp_id}/agents/${agent_id}/available-materials`;
    if (step !== null) {
        url += `?step=${step}`;
    }
    return await requestPassByBody(url);
}

// 获取实验最大步数
async function getMaxStep(exp_id) {
    let url = "/experiments/" + exp_id + "/max-step";
    return await requestPassByBody(url);
}

// 获取Agent指标数据
async function getAgentMetrics(exp_id, agent_id, step) {
    let url = `/experiments/${exp_id}/agents/${agent_id}/metrics?step=${step}`;
    return await requestPassByBody(url);
}

// 获取Agent参数数据
async function getAgentParams(exp_id, agent_id, step) {
    let url = `/experiments/${exp_id}/agents/${agent_id}/params?step=${step}`;
    return await requestPassByBody(url);
}

// 获取Agent层级信息
async function getAgentLevel(exp_id, agent_id, step = 0) {
    let url = `/experiments/${exp_id}/agents/${agent_id}/level`;
    if (step !== null) {
        url += `?step=${step}`;
    }
    return await requestPassByBody(url);
}

export const Api = {
    getExperiments:getExperiments,
    getMarketInsight:getMarketInsight,
    getAllAgent:getAllAgent,
    getAgentStepInfo:getAgentStepInfo,
    getAgentStatus:getAgentStatus,
    getAgentDialog:getAgentDialog,
    getTransaction:getTransaction,
    getCommunications:getCommunications,
    getCompanies:getCompanies,
    getAgentRequiredMaterials:getAgentRequiredMaterials,
    getAgentAvailableMaterials:getAgentAvailableMaterials,
    getMaxStep:getMaxStep,
    getAgentMetrics:getAgentMetrics,
    getAgentParams:getAgentParams,
    getAgentLevel:getAgentLevel
}

