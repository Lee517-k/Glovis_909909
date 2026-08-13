import { makeAutoObservable, runInAction } from "mobx";
import { Agent, AgentDialog, AgentProfile, AgentStatus, AgentSurvey, LngLat, Time } from "./components/type";
import { message } from "antd";
import React from "react";
import { Experiment, Survey } from "../../components/type";
import { round4 } from "../../components/util";
import { Api } from "../../services/api";

const formatStatus = (status: any) => {
    if (typeof status === 'number') {
        return round4(status)
    } else if (typeof status === 'string') {
        if (status == "") {
            return '-'
        }
        return status
    } else if (status === undefined || status === null) {
        return '-'
    } else if (typeof status === 'object') {
        if (Array.isArray(status)) {
            return JSON.stringify(status.map(s => formatStatus(s)))
        } else {
            return Object.fromEntries(Object.entries(status).map(([k, v]) => [k, formatStatus(v)]))
        }
    }
    return status
}

export class ReplayStore {
    mapCenter: LngLat = {
        lng: 116.39124329043085,
        lat: 39.906120097057055,
    }
    mapCenterDone = false // 是否已经根据agent位置设置了mapCenter

    expID?: string
    experiment?: Experiment
    _timeline: Time[] = []
    _currentTime?: Time = undefined
    _agent2Profile: Map<string, AgentProfile> = new Map()
    globalPrompt?: string = undefined
    agents: Map<string, Agent> = new Map()
    clickedAgentID?: string = undefined
    _clickedAgentStatuses: AgentStatus[] = []
    _clickedAgentDialogs: AgentDialog[] = []
    _clickedAgentSurveys: AgentSurvey[] = []

    _id2surveys: Map<string, Survey> = new Map()

    _localData: any[] = [] // 本地数据缓存，供其他组件访问
    _apiData: any = null // API数据缓存，供其他组件访问

    heatmapKeyInStatus?: string = undefined

    // 是否使用本地数据
    get isLocalData(): boolean {
        return localStorage.getItem('localDataPath') !== null;
    }

    constructor() {
        makeAutoObservable(this)
    }

    setCenter(center: LngLat) {
        this.mapCenter = center
    }

    setHeatmapKeyInStatus(key?: string) {
        console.log('set heatmap key: ', key)
        this.heatmapKeyInStatus = key
    }

    setApiData(apiData: any) {
        console.log('Setting API data in store:', apiData)
        this._apiData = apiData
    }

    get apiData() {
        return this._apiData
    }

    get timeline() {
        return this._timeline?.slice() ?? []
    }

    async _fetchSurveys() {
        try {
            const res = await fetch('/api/surveys')
            const data = await res.json()
            runInAction(() => {
                const surveys = data.data as Survey[]
                this._id2surveys = new Map(surveys.map(s => [s.id, s]))
            })
        } catch (err) {
            message.error(`Failed to fetch surveys: ${JSON.stringify(err)}`, 3);
            console.error('Failed to fetch surveys: ', err);
        }
    }

    async _fetchExperiment() {
        if (this.expID === undefined) {
            return
        }
        try {
            const res = await fetch(`/api/experiments/${this.expID}`)
            const data = await res.json()
            runInAction(() => {
                this.experiment = data.data as Experiment
            })
            {
                const res = await fetch(`/api/experiments/${this.expID}/timeline`)
                const data = await res.json()
                runInAction(() => {
                    this._timeline = data.data as Time[]
                    if (this.experiment?.status === 2) {
                        // completed -> set currentTime to the last time
                        this._currentTime = this._timeline[this._timeline.length - 1]
                    } else if (this.experiment?.status === 1) {
                        // running -> set currentTime to the first time
                        this._currentTime = this._timeline[0]
                    }
                })
                if (this._timeline.length === 0) {
                    throw "bad experiment with no timeline"
                }
            }
        } catch (err) {
            message.error(`Failed to fetch experiment: ${JSON.stringify(err)}`, 3);
            console.error('Failed to fetch experiment: ', err);
        }
    }

    async _fetchAgentProfile() {
        if (this.expID === undefined) {
            return
        }
        try {
            const res = await fetch(`/api/experiments/${this.expID}/agents/-/profile`)
            const data = await res.json()
            runInAction(() => {
                this._agent2Profile = new Map((data.data as AgentProfile[]).map(a => {
                    a.profile = Object.fromEntries(Object.entries(a.profile).map(([k, v]) => [k, formatStatus(v)]))
                    return [a.id, a]
                })
                )
            })
        } catch (err) {
            console.error('Failed to fetch agent profile: ', err);
        }
    }

    async _fetchAllAgentStatusAndPrompt(time?: Time) {
        if (this.expID === undefined) {
            return
        }
        try {
            let url = `/api/experiments/${this.expID}/agents/-/status`
            if (time !== undefined) {
                url += `?day=${time.day}&t=${time.t}`
            }
            const res = await fetch(url)
            const data = await res.json()
            const agentStatuses = data.data as AgentStatus[]
            console.log('fetched agent status: ', agentStatuses.length)

            runInAction(() => {
                let center = {
                    lng: 0,
                    lat: 0,
                }
                let cnt = 0
                const newAgents = new Map<string, Agent>()
                // merge status with profile
                agentStatuses.forEach((status) => {
                    // 确保经纬度数据有效
                    if (status.lng === undefined || status.lng === null) {
                        status.lng = 116.39 + Math.random() * 0.1 - 0.05; // 默认经度加随机偏移
                    }
                    if (status.lat === undefined || status.lat === null) {
                        status.lat = 39.90 + Math.random() * 0.1 - 0.05; // 默认纬度加随机偏移
                    }

                    if (!this.mapCenterDone) {
                        center.lng += status.lng;
                        center.lat += status.lat;
                        cnt += 1;
                        console.log('status: ', JSON.stringify(status))
                        console.log('center: ', JSON.stringify(center))
                        console.log('cnt: ', cnt)
                        console.log('mean: ', center.lng / cnt, center.lat / cnt)
                    }

                    status.status = Object.fromEntries(Object.entries(status.status).map(([k, v]) => [k, formatStatus(v)]))
                    const profile = this._agent2Profile.get(status.id)
                    if (profile !== undefined) {
                        newAgents.set(status.id, { ...profile, ...status })
                    } else {
                        console.error('agent profile not found: ', status.id)
                        // 即使没有profile也添加agent，确保地图上显示
                        newAgents.set(status.id, { ...status } as Agent)
                    }
                })

                this.agents = newAgents
                console.log('Total agents loaded:', this.agents.size)

                if (cnt > 0 && !this.mapCenterDone) {
                    center.lng /= cnt
                    center.lat /= cnt
                    this.mapCenter = center
                    console.log('set center: ', JSON.stringify(center))
                    this.mapCenterDone = true
                }
            })
        } catch (err) {
            message.error(`Failed to fetch data: ${JSON.stringify(err)}`, 3);
            console.error('Failed to fetch data: ', err);
        }
        try {
            let url = `/api/experiments/${this.expID}/prompt`
            if (time !== undefined) {
                url += `?day=${time.day}&t=${time.t}`
            }
            const res = await fetch(url)
            let prompt = undefined
            if (res.ok) {
                const data = await res.json()
                prompt = data.data.prompt
            }
            runInAction(() => {
                this.globalPrompt = prompt
            })
        } catch (err) {
            // message.error(`Failed to fetch prompt: ${JSON.stringify(err)}`, 3);
            console.error('Failed to fetch prompt: ', err);
        }
    }

    async _fetchClickedAgent() {
        if (this.expID === undefined || this.clickedAgentID === undefined) {
            return
        }
        try {
            {
                const res = await fetch(`/api/experiments/${this.expID}/agents/${this.clickedAgentID}/status`)
                const data = await res.json()
                for (const status of data.data as AgentStatus[]) {
                    status.status = Object.fromEntries(Object.entries(status.status).map(([k, v]) => [k, formatStatus(v)]))
                }
                runInAction(() => {
                    this._clickedAgentStatuses = data.data as AgentStatus[]
                })
            }
            {
                const res = await fetch(`/api/experiments/${this.expID}/agents/${this.clickedAgentID}/dialog`)
                const data = await res.json()
                runInAction(() => {
                    this._clickedAgentDialogs = data.data as AgentDialog[]
                })
            }
            {
                const res = await fetch(`/api/experiments/${this.expID}/agents/${this.clickedAgentID}/survey`)
                const data = await res.json()
                runInAction(() => {
                    this._clickedAgentSurveys = data.data as AgentSurvey[]
                })
            }
        } catch (err) {
            console.error('Failed to fetch agent: ', err);
        }
    }

    async loadLocalData(dataPath: string) {
        // message.loading({
        //     key: "loading",
        //     content: `Loading local data from ${dataPath} ...`
        // }, 0)

        try {
            let data;

            // 如果是企业数据，从public/enterprise/data目录加载指定的state文件
            if (dataPath.includes('enterprise') || dataPath.includes('state_')) {
                console.log('Loading enterprise data from:', dataPath);

                // 从dataPath中提取文件名，如果dataPath是完整路径则直接使用
                let fileName;
                if (dataPath.includes('state_')) {
                    // 如果dataPath包含state_，提取文件名
                    const match = dataPath.match(/state_(\d+)\.json/);
                    if (match) {
                        fileName = `state_${match[1]}.json`;
                    } else {
                        // 如果没有匹配到，默认使用state_1.json
                        fileName = 'state_1.json';
                    }
                } else {
                    // 如果只是包含enterprise，默认使用state_1.json
                    fileName = 'state_1.json';
                }

                console.log('Loading specific state file:', fileName);

                try {
                    const response = await fetch(`/enterprise/data/${fileName}`);
                    if (!response.ok) {
                        throw new Error(`Failed to load ${fileName}`);
                    }
                    const stateData = await response.json();
                    data = stateData;
                    console.log('Enterprise data loaded:', data.length, 'records from', fileName);
                } catch (err) {
                    console.error(`Failed to load ${fileName}:`, err);
                    throw new Error(`No enterprise data found for ${fileName}`);
                }
            } else {
                // 使用fetch加载本地数据
                const response = await fetch(dataPath);
                if (!response.ok) {
                    throw new Error(`Failed to load data from ${dataPath}`);
                }

                data = await response.json();
                console.log('Loaded local data:', data);
            }

            // 保存本地数据到缓存中
            if (Array.isArray(data)) {
                this._localData = this._localData.concat(data);
            } else {
                console.warn('Loaded data is not an array, skipping merge.');
            }
            console.log('this._localData', this._localData);
            runInAction(() => {
                // 重置状态
                this.mapCenterDone = false;
                this.clickedAgentID = undefined;
                this._clickedAgentStatuses = [];

                // 处理企业数据文件（state_*.json）
                if (Array.isArray(data) && data.length > 0 && data[0].step !== undefined) {
                    // 从数据中提取所有唯一的步骤
                    const steps = [...new Set(data.map((item: any) => item.step))];
                    steps.sort((a, b) => a - b); // 确保步骤按顺序排列

                    console.log('Unique steps found:', steps);

                    // 创建时间线，完全基于step作为主要标识，不再依赖具体时间
                    // 注意：这里使用step作为主要标识，t字段仅作为兼容性保留
                    this._timeline = steps.map(step => ({ day: 0, t: step, step }));
                    console.log('Timeline created with', this._timeline.length, 'steps');
                    this._currentTime = this._timeline[0]; // 从第一个时间点开始

                    // 提取所有唯一的企业ID
                    const companyNames = [...new Set(data.map((item: any) => item.company_name))];
                    // 创建企业节点
                    const newAgents = new Map<string, Agent>();

                    // 从neo4j/industry_test.json加载企业基本信息
                    fetch('/neo4j/industry_test.json')
                        .then(res => res.json())
                        .then(industryData => {
                            runInAction(() => {
                                // 合并所有级别的企业
                                const allCompanies = [
                                    ...(industryData.level_1 || []),
                                    ...(industryData.level_2 || []),
                                    ...(industryData.level_3 || [])
                                ];

                                console.log('All companies from industry_test.json:', allCompanies.length);
                                console.log('Companies with data from state file:', companyNames.length);

                                // 为所有企业创建Agent对象（包括真节点和假节点）
                                allCompanies.forEach(companyInfo => {
                                    const companyName = companyInfo.name;
                                    const hasData = companyNames.includes(parseInt(companyName));
                                    const companyData = hasData ? data.find(d => d.company_name === companyName) : null;

                                    // 确保经纬度数据有效
                                    const lng = 116.39 + Math.random() * 0.1 - 0.05;
                                    const lat = 39.90 + Math.random() * 0.1 - 0.05;

                                    // 确定企业级别
                                    let industryLevel = "";
                                    if (industryData.level_1?.find(c => c.id === companyInfo.id)) {
                                        industryLevel = "level_1";
                                    } else if (industryData.level_2?.find(c => c.id === companyInfo.id)) {
                                        industryLevel = "level_2";
                                    } else if (industryData.level_3?.find(c => c.id === companyInfo.id)) {
                                        industryLevel = "level_3";
                                    }
                                    // 创建Agent对象
                                    const agent: Agent = {
                                        name: companyInfo.name,
                                        lng: lng,
                                        lat: lat,
                                        day: this._currentTime?.day || 0,
                                        t: this._currentTime?.t || 0,
                                        status: {},
                                        profile: {
                                            description: "",
                                            industry_level: industryLevel,
                                            products: companyInfo.main_products || [],
                                            raw_materials: companyInfo.available_materials || [],
                                            required_materials: companyInfo.main_products?.flatMap(p => p.related_materials || []) || [],
                                            hasData: hasData // 标记是否有真实数据
                                        }
                                    };

                                    newAgents.set(agent.name, agent);

                                    // 同时更新profile
                                    this._agent2Profile.set(agent.id, {
                                        id: agent.id,
                                        name: agent.name,
                                        profile: agent.profile
                                    });
                                });

                                this.agents = newAgents;
                                console.log('Total agents loaded (real + fake):', this.agents.size);
                                console.log('Real agents with data:', companyNames.length);
                                console.log('Fake agents without data:', this.agents.size - companyNames.length);

                                // 如果有企业，默认选中第一个有数据的企业，如果没有则选中第一个
                                if (companyNames.length > 0) {
                                    this.setClickedAgentID(companyNames[0].toString());
                                } else if (this.agents.size > 0) {
                                    const firstAgentId = Array.from(this.agents.keys())[0];
                                    this.setClickedAgentID(firstAgentId);
                                }
                            });
                        })
                        .catch(err => {
                            console.error('Failed to load industry data:', err);
                            runInAction(() => {
                                // 即使没有行业数据，也创建基本的Agent对象
                                companyNames.forEach(companyId => {
                                    const companyData = data.find(d => d.id === companyId);

                                    // 确保经纬度数据有效
                                    const lng = 116.39 + Math.random() * 0.1 - 0.05;
                                    const lat = 39.90 + Math.random() * 0.1 - 0.05;

                                    // 创建Agent对象
                                    const agent: Agent = {
                                        id: companyId.toString(),
                                        name: companyData?.company_name || `Company ${companyId}`,
                                        lng: lng,
                                        lat: lat,
                                        day: this._currentTime?.day || 0,
                                        t: this._currentTime?.t || 0,
                                        status: {},
                                        profile: {
                                            description: "",
                                            industry_level: "",
                                            products: [],
                                            raw_materials: [],
                                            required_materials: []
                                        }
                                    };

                                    newAgents.set(agent.id, agent);

                                    // 同时更新profile
                                    this._agent2Profile.set(agent.id, {
                                        id: agent.id,
                                        name: agent.name,
                                        profile: agent.profile
                                    });
                                });

                                this.agents = newAgents;
                                console.log('Total agents loaded from local data (fallback):', this.agents.size);

                                // 如果有企业，默认选中第一个
                                if (companyNames.length > 0) {
                                    this.setClickedAgentID(companyNames[0].toString());
                                }
                            });
                        });
                } else {
                    // 如果不是企业数据格式，使用原来的处理逻辑
                    runInAction(() => {
                        // 设置时间线
                        if (data.timeline) {
                            this._timeline = data.timeline;
                            this._currentTime = this._timeline[0]; // 从第一个时间点开始
                        } else {
                            // 如果没有时间线，创建一个默认的
                            this._timeline = [{day: 0, t: 0, step: 0}];
                            this._currentTime = {day: 0, t: 0, step: 0};
                        }

                        // 设置全局提示
                        this.globalPrompt = data.global_prompt || "";

                        // 处理节点数据
                        if (data.nodes) {
                            const newAgents = new Map<string, Agent>();

                            data.nodes.forEach((node: any) => {
                                // 确保经纬度数据有效
                                if (node.lng === undefined || node.lng === null) {
                                    node.lng = 116.39 + Math.random() * 0.1 - 0.05;
                                }
                                if (node.lat === undefined || node.lat === null) {
                                    node.lat = 39.90 + Math.random() * 0.1 - 0.05;
                                }

                                // 格式化状态数据
                                const status = node.status ? Object.fromEntries(Object.entries(node.status).map(([k, v]) => [k, formatStatus(v)])) : {};

                                // 创建Agent对象
                                const agent: Agent = {
                                    id: node.id || node.company_id,
                                    name: node.name || node.company_name,
                                    lng: node.lng,
                                    lat: node.lat,
                                    day: this._currentTime?.day || 0,
                                    t: this._currentTime?.t || 0,
                                    status: status,
                                    profile: {
                                        description: node.description || "",
                                        industry_level: node.industry_level || "",
                                        products: node.products || [],
                                        raw_materials: node.raw_materials || [],
                                        required_materials: node.required_materials || []
                                    }
                                };

                                newAgents.set(agent.id, agent);

                                // 同时更新profile
                                this._agent2Profile.set(agent.id, {
                                    id: agent.id,
                                    name: agent.name,
                                    profile: agent.profile
                                });
                            });

                            this.agents = newAgents;
                            console.log('Total agents loaded from local data:', this.agents.size);
                        }
                    });
                }
            });

            // 加载本地数据后，如果有expID，也要获取API最大步数并扩展timeline
            if (this.expID) {
                try {
                    const maxStepRes = await Api.getMaxStep(this.expID);
                    if (maxStepRes && typeof maxStepRes.max_step === 'number' && maxStepRes.max_step > this._timeline.length - 1) {
                        console.log('Store: 本地数据加载后，从API获取到更大的最大步数:', maxStepRes.max_step, '当前timeline长度:', this._timeline.length);
                        // 扩展timeline到API返回的最大步数
                        const currentMaxStep = this._timeline.length - 1;
                        for (let i = currentMaxStep + 1; i <= maxStepRes.max_step; i++) {
                            this._timeline.push({ day: 0, t: i, step: i });
                        }
                        console.log('Store: 扩展后的timeline长度:', this._timeline.length);
                    }
                } catch (error) {
                    console.error('Store: 本地数据加载后获取最大步数失败:', error);
                }
            }

            // message.success(`Successfully loaded data from ${dataPath}`);
        } catch (error) {
            console.error('Failed to load local data:', error);
        } finally {
            message.destroy("loading");
        }
    }

    async init(expID?: string) {
        // 检查是否有本地数据路径
        const localDataPath = localStorage.getItem('localDataPath');
        if (localDataPath) {
            // 清除本地存储的路径，避免下次刷新页面时再次加载
            localStorage.removeItem('localDataPath');
            await this.loadLocalData(localDataPath);
            return;
        }

        message.loading({
            key: "loading",
            content: `Loading experiment ${expID} ...`
        }, 0)
        this.mapCenterDone = false
        await this._fetchSurveys()
        this.expID = expID
        this.clickedAgentID = undefined
        this._clickedAgentStatuses = []
        if (expID === undefined) {
            this._timeline = []
            this._agent2Profile = new Map()
            this.agents = new Map()
        } else {
            await this._fetchExperiment()
            await this._fetchAgentProfile()

            // 获取API最大步数并创建完整的timeline
            try {
                const maxStepRes = await Api.getMaxStep(expID);
                if (maxStepRes && typeof maxStepRes.max_step === 'number') {
                    console.log('Store: 从API获取到最大步数:', maxStepRes.max_step);
                    // 创建完整的timeline，从0到最大步数
                    this._timeline = [];
                    for (let i = 0; i <= maxStepRes.max_step; i++) {
                        this._timeline.push({ day: 0, t: i, step: i });
                    }
                    console.log('Store: 创建了完整的timeline，长度:', this._timeline.length);
                    this._currentTime = this._timeline[0]; // 从第一个时间点开始
                } else {
                    console.log('Store: API返回的max-step数据格式不正确:', maxStepRes);
                    // 如果API失败，保持原有逻辑
                    this._timeline = [];
                    this._currentTime = undefined;
                }
            } catch (error) {
                console.error('Store: 获取最大步数失败:', error);
                // 如果API失败，保持原有逻辑
                this._timeline = [];
                this._currentTime = undefined;
            }

            if (this.experiment?.status === 2) {
                // completed -> fetch the newest data
                await this._fetchAllAgentStatusAndPrompt(this._currentTime)
            } else if (this.experiment?.status === 1) {
                // running -> fetch the newest data
                await this._fetchAllAgentStatusAndPrompt()
            }
        }
        message.destroy("loading")
    }

    async fetchByTime(time: Time) {
        if (this.expID === undefined) {
            return
        }
        this._currentTime = time

        // 如果是本地数据，处理本地数据的时间切换
        if (this._localData && this._localData.length > 0) {
            console.log('Fetching by time for local data:', time);

            // 更新所有agent的时间点，完全基于step作为主要标识
            for (const agent of this.agents.values()) {
                agent.day = time.day;
                agent.t = time.t;
                // 确保agent有step属性，并更新它
                if (time.step !== undefined) {
                    (agent as any).step = time.step;
                }
            }

            // 如果有选中的Agent，更新其详细信息
            if (this.clickedAgentID) {
                this._updateClickedAgentData(this.clickedAgentID, time);
            }
            return;
        }

        // 获取远程数据
        await this._fetchAllAgentStatusAndPrompt(time)
        await this._fetchClickedAgent()
    }

    // 从本地数据中更新选中节点的状态和对话
    _updateClickedAgentData(agentId: string, time: Time) {
        // 如果没有本地数据，直接返回
        if (!this._localData || !Array.isArray(this._localData) || this._localData.length === 0) {
            return;
        }

        // 清空之前的状态和对话
        this._clickedAgentStatuses = [];
        this._clickedAgentDialogs = [];

        // 获取当前时间点，完全基于step作为主要标识
        const currentStep = time.step !== undefined ? time.step : time.t;
        console.log('Updating clicked agent data for step:', currentStep, 'agentId:', agentId);

        // 从本地数据中筛选出当前时间点之前的数据，基于step进行筛选
        const relevantData = this._localData.filter(item => item.step <= currentStep);
        console.log('Relevant data for step', currentStep, ':', relevantData.length, 'items');

        // 处理每个时间点的数据
        relevantData.forEach(data => {
            // 如果数据属于当前选中的节点
            if (data.id === agentId) {
                // 添加状态
                this._clickedAgentStatuses.push({
                    id: agentId,
                    day: 0,
                    t: data.step,
                    status: {
                        company_name: data.company_name || '',
                        company_fund: data.company_fund || 0,
                        company_products: data.company_products || [],
                        product_stocks: data.product_stocks || [],
                        available_materials: data.available_materials || []
                    }
                });
            }

            // 处理行为记录和思考内容
            if (data.record && Array.isArray(data.record)) {
                data.record.forEach(record => {
                    if (record.from === agentId || record.source === agentId) {
                        this._clickedAgentDialogs.push({
                            id: agentId,
                            day: 0,
                            t: data.step,
                            dialog: record.detailed_inquiry_text || JSON.stringify(record),
                            type: record.type || 'text',
                            from: record.from || record.source,
                            to: record.to || record.target,
                            product_name: record.product_name,
                            quantity: record.quantity,
                            price: record.price
                        });
                    }
                });
            }

            // 处理交易列表
            if (data.transaction_list && Array.isArray(data.transaction_list)) {
                data.transaction_list.forEach(transaction => {
                    // 确保交易属于当前节点
                    if (transaction.from === agentId || transaction.to === agentId) {
                        this._clickedAgentDialogs.push({
                            id: agentId,
                            day: 0,
                            t: data.step,
                            dialog: JSON.stringify(transaction),
                            type: 'transaction',
                            from: transaction.from,
                            to: transaction.to,
                            product_name: transaction.product_name,
                            quantity: transaction.quantity,
                            price: transaction.price
                        });
                    }
                });
            }
        });

        // 按时间排序
        this._clickedAgentStatuses.sort((a, b) => a.t - b.t);
        this._clickedAgentDialogs.sort((a, b) => a.t - b.t);
    }

    // 获取最新的experiment数据，刷新所有数据，如果有clickedAgentID，也刷新clickedAgentID的数据
    async refresh() {
        // 1. 刷新experiment数据
        await this._fetchExperiment()
        // 2. 刷新所有agent数据
        await this._fetchAllAgentStatusAndPrompt(this._currentTime)
        // 3. 刷新clickedAgent数据
        await this._fetchClickedAgent()
    }

    async setClickedAgentID(agentID?: string) {
        console.log('Setting clicked agent ID:', agentID);
        runInAction(() => {
            this.clickedAgentID = agentID
            this._clickedAgentStatuses = []
            this._clickedAgentDialogs = []
            this._clickedAgentSurveys = []
        });

        if (agentID === undefined) {
            return
        }

        // 确保该 agent 存在于 agents 中
        if (!this.agents.has(agentID)) {
            console.warn(`Agent with ID ${agentID} not found in agents map. Current agents:`, Array.from(this.agents.keys()));
            // 如果 agent 不存在，尝试从 _agent2Profile 中获取
            const profile = this._agent2Profile.get(agentID);
            if (profile) {
                runInAction(() => {
                    // 创建一个临时 agent 并添加到 agents 中
                    const tempAgent: Agent = {
                        ...profile,
                        lng: 116.39 + Math.random() * 0.1 - 0.05,
                        lat: 39.90 + Math.random() * 0.1 - 0.05,
                        day: this._currentTime?.day || 0,
                        t: this._currentTime?.t || 0,
                        status: {}
                    };
                    this.agents.set(agentID, tempAgent);
                });
                console.log('Created temporary agent:', tempAgent);
            }
        }
        
        await this._fetchClickedAgent()
    }

    get id2surveys() {
        return this._id2surveys
    }

    get clickedAgent() {
        if (this.clickedAgentID === undefined) {
            return undefined
        }
        const a = this.agents.get(this.clickedAgentID)
        if (a === undefined) {
            return undefined
        }
        return { ...a }
    }

    get clickedAgentStatuses() {
        if (this._currentTime === undefined) {
            return []
        }
        if (this._clickedAgentStatuses === undefined) {
            return []
        }
        // filter by current time
        return this._clickedAgentStatuses.slice().filter(s => (s.day < this._currentTime!.day || s.day === this._currentTime!.day && s.t <= this._currentTime!.t))
    }

    get clickedAgentDialogs() {
        if (this._currentTime === undefined) {
            return []
        }
        if (this._clickedAgentDialogs === undefined) {
            return []
        }
        // filter by current time
        return this._clickedAgentDialogs.slice().filter(d => d.day < this._currentTime!.day || d.day === this._currentTime!.day && d.t <= this._currentTime!.t)
    }

    get clickedAgentSurveys() {
        if (this._currentTime === undefined) {
            return []
        }
        if (this._clickedAgentSurveys === undefined) {
            return []
        }
        // filter by current time
        return this._clickedAgentSurveys.slice().filter(s => s.day < this._currentTime!.day || s.day === this._currentTime!.day && s.t <= this._currentTime!.t)
    }
}

export const store = new ReplayStore()
export const StoreContext = React.createContext(store)
