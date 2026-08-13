import { Typography, Flex, Tooltip, Divider, Button, List, Card, Tag, Avatar, Empty, Spin, Badge, Collapse, Descriptions } from 'antd';
import { CloseOutlined, UserOutlined, HistoryOutlined, DashboardOutlined, BuildOutlined } from '@ant-design/icons';
import { AgentStatus } from './components/type';
import React, { useContext, useState, useEffect, useMemo, useCallback } from 'react';
import { parseT } from '../../components/util';
import { StoreContext } from './store';
import { observer } from 'mobx-react-lite';
import { Api } from '../../services/api';

const { Title, Text } = Typography;

interface InfoPanelProps {
  exp_id: string;
}

const InfoPanel = observer((props: InfoPanelProps) => {
  const exp_id = props.exp_id
  const store = useContext(StoreContext);
  const agent = store.clickedAgent;
  const agentStatuses = store.clickedAgentStatuses;
  const [dataReady, setDataReady] = useState(false);
  const [nodeData, setNodeData] = useState<any>(null);
  const [nodeHistory, setNodeHistory] = useState<any[]>([]);
  const [currentStep, setCurrentStep] = useState<number>(0);

  const [transaction,setTransaction] = useState([])
  // API数据状态
  const [apiCompanies, setApiCompanies] = useState<any[]>([]);
  const [apiDataLoaded, setApiDataLoaded] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  // 历史指标数据状态
  const [historicalMetrics, setHistoricalMetrics] = useState<any[]>([]);
  const [metricsLoaded, setMetricsLoaded] = useState(false);
  // 新增状态用于存储当前步骤的metrics和params数据
  const [currentStepMetrics, setCurrentStepMetrics] = useState<any>(null);
  const [currentStepParams, setCurrentStepParams] = useState<any>(null);
  const [currentDataLoaded, setCurrentDataLoaded] = useState(false);
  // 公司层级信息状态
  const [companyLevel, setCompanyLevel] = useState<any>(null);

  // 获取公司层级的辅助函数（参照IndustryGraph.tsx实现）
  const getCompanyLevel = async (company: any) => {
    if (!exp_id) {
      // 如果没有exp_id，回退到使用首字母判断层级
      const firstLetter = company.company_name?.charAt(0)?.toUpperCase();
      if (firstLetter === 'A') return { level: 1, color: 'blue', text: 'Level 1' };
      if (firstLetter === 'B') return { level: 2, color: 'green', text: 'Level 2' };
      return { level: 3, color: 'orange', text: 'Level 3' };
    }

    try {
      const rawId = company.company_id || company.id;
      const levelData = await Api.getAgentLevel(exp_id, rawId);
      if (levelData && levelData.level) {
        const level = levelData.level;
        const colors = ['blue', 'green', 'orange', 'purple', 'red'];
        const color = colors[level - 1] || 'gray';
        return { level, color, text: `Level ${level}` };
      }
    } catch (error) {
      console.error(`获取公司 ${company.company_name} 层级失败:`, error);
    }

    // 如果API调用失败，回退到使用首字母判断层级
    const firstLetter = company.company_name?.charAt(0)?.toUpperCase();
    if (firstLetter === 'A') return { level: 1, color: 'blue', text: 'Level 1' };
    if (firstLetter === 'B') return { level: 2, color: 'green', text: 'Level 2' };
    return { level: 3, color: 'orange', text: 'Level 3' };
  };

  // 使用useMemo缓存公司数据映射，避免重复查找
  const apiCompaniesMap = useMemo(() => {
    const map = new Map();
    apiCompanies.forEach(company => {
      const id = company.company_id?.toString() || company.id?.toString();
      if (id) {
        map.set(id, company);
        map.set(company.company_name, company);
      }
    });
    return map;
  }, [apiCompanies]);
  // 加载API数据
  // 从store中获取API数据
  useEffect(() => {
    const apiData = store.apiData;
    if (apiData && apiData.companies) {
      console.log('InfoPanel: 使用store中的API数据:', apiData);
      setApiCompanies(apiData.companies);
      setApiDataLoaded(true);
    } else {
      console.log('InfoPanel: store中暂无API数据');
      setApiDataLoaded(false);
    }
  }, [store.apiData]);

  // 获取选中公司的层级信息
  useEffect(() => {
    const fetchCompanyLevel = async () => {
      if (selectedNodeId && apiDataLoaded) {
        const company = apiCompanies.find(c =>
          c.company_id?.toString() === selectedNodeId.toString() ||
          c.id?.toString() === selectedNodeId.toString() ||
          c.company_name === selectedNodeId.toString()
        );

        if (company) {
          try {
            const levelInfo = await getCompanyLevel(company);
            setCompanyLevel(levelInfo);
            console.log('InfoPanel: 获取到公司层级信息:', levelInfo);
          } catch (error) {
            console.error('InfoPanel: 获取公司层级失败:', error);
            setCompanyLevel(null);
          }
        }
      } else if (nodeData && !Array.isArray(nodeData)) {
        // 处理本地数据的情况
        const company = { company_name: nodeData.name, company_id: nodeData.id };
        try {
          const levelInfo = await getCompanyLevel(company);
          setCompanyLevel(levelInfo);
        } catch (error) {
          console.error('InfoPanel: 获取本地数据公司层级失败:', error);
          setCompanyLevel(null);
        }
      }
    };

    fetchCompanyLevel();
  }, [selectedNodeId, apiDataLoaded, apiCompanies, nodeData, exp_id]);

  // 使用useMemo缓存交易数据，避免重复过滤
  const [allTransactions, setAllTransactions] = useState([]);
  const [transactionsLoaded, setTransactionsLoaded] = useState(false);

  // 只在exp_id变化时加载所有交易数据
  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await Api.getTransaction(exp_id);
        console.log("getTransaction", response);
        setAllTransactions(response || []);
        setTransactionsLoaded(true);
      } catch (e) {
        console.error('getTransaction e', e);
        setAllTransactions([]);
        setTransactionsLoaded(false);
      }
    };
    fetchData();
  }, [exp_id]);

  // 使用useMemo根据当前步数过滤交易数据
  const filteredTransactions = useMemo(() => {
    console.log("transcation",selectedNodeId,allTransactions)
    if (!transactionsLoaded) return [];
    // return allTransactions.filter(item => item.step === currentStep);
    return allTransactions;
  }, [allTransactions, currentStep, transactionsLoaded]);

  // 获取选中节点的历史指标数据
  useEffect(() => {
    const fetchHistoricalMetrics = async () => {
      if (selectedNodeId && apiDataLoaded) {
        try {
          const metricsData = await Api.getAgentStepInfo(exp_id, selectedNodeId);
          const validMetricsData = Array.isArray(metricsData) ? metricsData : [];
          setHistoricalMetrics(validMetricsData);
          setMetricsLoaded(true);
        } catch (error) {
          setHistoricalMetrics([]);
          setMetricsLoaded(false);
        }
      } else {
        setHistoricalMetrics([]);
        setMetricsLoaded(false);
      }
    };

    fetchHistoricalMetrics();
  }, [selectedNodeId, exp_id, apiDataLoaded]);

  // 获取当前步骤的metrics和params数据
  useEffect(() => {
    const fetchCurrentStepData = async () => {
      if (selectedNodeId && currentStep >= 0) {
        try {
          // 并行获取metrics和params数据
          const [metricsResponse, paramsResponse] = await Promise.all([
            Api.getAgentMetrics(exp_id, selectedNodeId, currentStep),
            Api.getAgentParams(exp_id, selectedNodeId, currentStep)
          ]);

          setCurrentStepMetrics(metricsResponse?.metrics || null);
          setCurrentStepParams(paramsResponse?.params || null);
          setCurrentDataLoaded(true);
        } catch (error) {
          console.error('获取当前步骤数据失败:', error);
          setCurrentStepMetrics(null);
          setCurrentStepParams(null);
          setCurrentDataLoaded(false);
        }
      } else {
        setCurrentStepMetrics(null);
        setCurrentStepParams(null);
        setCurrentDataLoaded(false);
      }
    };

    fetchCurrentStepData();
  }, [selectedNodeId, currentStep, exp_id]);

  // 使用useMemo缓存当前选中的API公司数据
  const selectedApiCompany = useMemo(() => {
    if (!apiDataLoaded || !selectedNodeId || apiCompaniesMap.size === 0) {
      return null;
    }
    return apiCompaniesMap.get(selectedNodeId) || null;
  }, [apiDataLoaded, selectedNodeId, apiCompaniesMap]);


  // 使用 useState 和 useEffect 延迟渲染，避免直接渲染大量 JSON 数据
  useEffect(() => {
    if (agent) {
      // 延迟 100ms 渲染，给浏览器时间处理数据
      const timer = setTimeout(() => {
        setDataReady(true);
      }, 100);
      return () => clearTimeout(timer);
    } else {
      setDataReady(false);
    }
  }, [agent?.id]);

  // 使用useCallback优化事件处理函数
  const handleNodeSelected = useCallback((event: any) => {
    const { nodeId, nodeData } = event.detail;

    if (nodeId) {
      setSelectedNodeId(nodeId);

      // 优先使用API数据
      const apiCompany = apiCompaniesMap.get(nodeId);
      if (apiCompany) {
        // 将API数据转换为nodeData格式
        const apiNodeData = [{
          id: apiCompany.company_id || apiCompany.id,
          company_name: apiCompany.company_name,
          company_fund: apiCompany.company_fund || 0,
          company_products: apiCompany.company_products || [],
          company_materials: apiCompany.company_materials || [],
          step: currentStep,
          record: [],
          transaction_list: []
        }];
        setNodeData(apiNodeData);
        setNodeHistory(apiNodeData);
        return;
      }

        // 如果API数据不可用，回退到本地数据
        const localData = store._localData;
        if (localData && Array.isArray(localData) && localData.length > 0) {
          // 根据节点ID筛选数据，支持通过company_name或id匹配
          const nodeSpecificData = localData.filter(item =>
            item.id.toString() === nodeId.toString() ||
            item.company_name === nodeId.toString()
          );

          if (nodeSpecificData.length > 0) {
            // 按step排序
            const sortedData = [...nodeSpecificData].sort((a, b) => a.step - b.step);

            // 确保每个记录都有record字段，即使为空
            const processedData = sortedData.map(item => ({
              ...item,
              record: item.record || [],
              step: item.step !== undefined ? item.step : 0
            }));

            // 获取最大步数
            const maxStep = Math.max(...processedData.map(item => item.step), 0);

            // 确保每个步骤都有记录，即使是空记录
            const fullStepHistory = [];
            for (let step = 0; step <= maxStep; step++) {
              // 查找当前步骤的记录
              const stepData = processedData.find(item => item.step === step);
              if (stepData) {
                fullStepHistory.push(stepData);
              } else {
                // 如果当前步骤没有记录，创建一个空记录
                const baseData = processedData[0] || {};
                fullStepHistory.push({
                  step: step,
                  id: nodeId,
                  company_name: baseData.company_name || `Company ${nodeId}`,
                  record: [],
                  company_fund: baseData.company_fund || 0,
                  company_products: baseData.company_products || [],
                  product_stocks: baseData.product_stocks || [],
                  available_materials: baseData.available_materials || []
                });
              }
            }

            setNodeData(fullStepHistory);
            setNodeHistory(fullStepHistory);
          } else {
            setNodeData(null);
            setNodeHistory([]);
          }
        } else {
          // 如果没有本地数据，使用传入的nodeData
          if (nodeData) {
            setNodeData(nodeData);
            if (Array.isArray(nodeData)) {
              const sortedData = [...nodeData].sort((a, b) => a.step - b.step);
              setNodeHistory(sortedData);
            } else {
              setNodeHistory([]);
            }
          } else {
            setNodeData(null);
            setNodeHistory([]);
          }
        }
      } else {
        setNodeData(null);
        setNodeHistory([]);
      }
    }, [apiCompaniesMap, currentStep, store._localData]);

    // 使用useCallback优化时间轴变化处理函数
    const handleTimelineChange = useCallback((event: any) => {
      const { step } = event.detail;
      setCurrentStep(step);
    }, []);

  // 监听节点选择和时间轴变化事件
  useEffect(() => {
    console.log('InfoPanel: Setting up event listeners');
    window.addEventListener('nodeSelected', handleNodeSelected);
    window.addEventListener('timelineChange', handleTimelineChange);

    return () => {
      console.log('InfoPanel: Cleaning up event listeners');
      window.removeEventListener('nodeSelected', handleNodeSelected);
      window.removeEventListener('timelineChange', handleTimelineChange);
    };
  }, [handleNodeSelected, handleTimelineChange]);

  // 状态历史记录项渲染
  const renderItem = useCallback((item: AgentStatus, index: number) => (
    <Card
      className='status-history-card'
      size="small"
      bordered={false}
      style={{ marginBottom: '8px' }}
    >
      <div className="status-history-time">
        Day {item.day} {parseT(item.t)}
      </div>
      <div className="status-history-action">
        <Tag color="blue">{item.action}</Tag>
      </div>
    </Card>
  ), []);

  const agentName = agent ? (agent.name !== "" ? agent?.name : "[Unknown]") : nodeData ? (Array.isArray(nodeData) ? nodeData[0].company_name : nodeData.name) : "Please select an agent or node";
  // 不再使用collapsed类，确保内容始终显示
  const rootClass = "left-inner";

  // 处理产品数据显示
  const formatProductList = useCallback((productData) => {
    if (!productData) return '';
    try {
      // 如果是字符串，尝试解析为JSON
      const productList = typeof productData === 'string' ? JSON.parse(productData) : productData;

      // 限制显示的产品数量，避免过多数据导致渲染缓慢
      const maxDisplayItems = 10;
      let validProducts = [];

      // 处理不同格式的产品数据
      if (Array.isArray(productList)) {
        validProducts = productList
          .map(item => {
            // 如果是简单字符串
            if (typeof item === 'string') return item;

            // 处理不同格式的产品对象
            if (item.product_name) return item.product_name;
            if (item.material_name) return item.material_name;
            if (item.name) return item.name;

            // 处理包含ID和名称的对象
            if (item.material_id !== undefined && item.material_name) {
              return `${item.material_name}`;
            }
            if (item.product_id !== undefined && item.product_name) {
              return `${item.product_name}`;
            }

            // 如果是其他格式的对象，尝试提取有意义的信息
            const values = Object.values(item).filter(v =>
              typeof v === 'string' || typeof v === 'number'
            );
            if (values.length > 0) {
              return values.join(': ');
            }

            // 最后尝试直接转换为字符串
            return JSON.stringify(item);
          })
          .filter(Boolean);
      } else if (typeof productList === 'object' && productList !== null) {
        // 如果是对象而不是数组，尝试提取键值对
        validProducts = Object.entries(productList)
          .map(([key, value]) => `${key}: ${typeof value === 'object' ? JSON.stringify(value) : value}`)
          .filter(Boolean);
      }

      if (validProducts.length === 0) {
        // 如果没有有效产品，返回原始字符串
        return typeof productData === 'string' ? productData : JSON.stringify(productData);
      }

      if (validProducts.length <= maxDisplayItems) {
        return validProducts.join(', ');
      } else {
        const displayProducts = validProducts.slice(0, maxDisplayItems);
        return `${displayProducts.join(', ')} 等 ${validProducts.length} 种产品`;
      }
    } catch (e) {
      console.error("解析产品数据出错：", e);
      // 如果解析失败，尝试直接显示原始数据的字符串表示
      return typeof productData === 'string' ? productData : JSON.stringify(productData);
    }
  }, []);

  // 渲染节点内容
  const renderNodeContent = useCallback(() => {
    if (!nodeData) return null;
    const selectedNodeName = Array.isArray(nodeData) ? nodeData[0]?.company_name : nodeData?.company_name;
        // 从store中获取对应的agent信息（包含industry_test.json的详细信息）
    const agentInfo = store.agents.get(selectedNodeName);

    // 判断是否为真节点（有state数据或API数据）
    const isRealNode = Array.isArray(nodeData) || (selectedNodeId && apiDataLoaded);
    const INDUSTRY_LEVEL_MAP: Record<string, string> = {
      level_1: '一级产业',
      level_2: '二级产业',
      level_3: '三级产业',
    };
    const StaticInfo = React.memo(({ agentInfo }: { agentInfo: any }) => {
      const profile = agentInfo?.profile || {};

      // 优先使用API数据
      let companyName, industryLevel, products, companyFund, productStocks, availableMaterials, companyProducts, params;
      let apiCompany = null;

      if (apiDataLoaded && selectedNodeId) {
        apiCompany = apiCompanies.find(company =>
          company.company_id?.toString() === selectedNodeId.toString() ||
          company.id?.toString() === selectedNodeId.toString() ||
          company.company_name === selectedNodeId.toString()
        );

        if (apiCompany) {
          companyName = apiCompany.company_name;
          // 层级信息现在通过companyLevel状态统一管理
          industryLevel = apiCompany.industry_level || apiCompany.level;
          products = apiCompany.products || apiCompany.main_products;
          companyFund = apiCompany.company_fund;
          productStocks = apiCompany.product_stocks;
          availableMaterials = apiCompany.available_materials;
          companyProducts = apiCompany.company_products;
          params = apiCompany.params;
        }
      }

      // 如果API数据不可用，回退到本地数据
      if (!companyName) {
        companyName = agentInfo?.name || profile.company_name;
        industryLevel = profile.industry_level;
        products = profile.products || profile.main_products;
        companyFund = profile.company_fund;
        productStocks = profile.product_stocks;
        availableMaterials = profile.available_materials;
        companyProducts = profile.company_products;
        params = profile.params;
      }

      // 处理params中的静态属性信息 - 分类展示
      const renderParamsInfo = () => {
        // 优先使用新的params接口数据
        let paramsData = null;
        if (currentDataLoaded && currentStepParams) {
          console.log('Using new params API data for step:', currentStep);
          paramsData = currentStepParams;
        } else if (params && typeof params === 'object') {
          console.log('Using fallback params data');
          paramsData = params;
        }

        if (!paramsData || typeof paramsData !== 'object') return null;

        // 字段分类函数
        const categorizeFields = (data: any) => {
          const categories = {
            basicInfo: [] as Array<[string, any]>,
            productConfig: [] as Array<[string, any]>,
            materialConfig: [] as Array<[string, any]>,
            intelligenceConfig: [] as Array<[string, any]>,
            otherConfig: [] as Array<[string, any]>
          };

          Object.entries(data).forEach(([key, value]) => {
            if (value === undefined || value === null || value === '') return;

            // 基本信息类别
            if (key === 'company_name' || key.includes('company_name_') ||
                key === 'description' || key.includes('description_') ||
                key.includes('agent_id_') || key === 'company_fund' ||
                key.includes('initial_fund_') || key === 'industry_level' ||
                key.includes('industry_level_')) {
              categories.basicInfo.push([key, value]);
            }
            // 产品配置类别
            else if (key.match(/^product_(\d+)_([A-Z]\d+)_(.+)$/) ||
                     key.includes('product_') || key.includes('main_products') ||
                     key.includes('relative_products')) {
              categories.productConfig.push([key, value]);
            }
            // 原料配置类别
            else if (key.match(/^material_(\d+)_([A-Z]\d+)_(id|name)$/) ||
                     key.includes('material_inventory_') || key.includes('material_') ||
                     key.includes('available_materials')) {
              categories.materialConfig.push([key, value]);
            }
            // 智能配置类别
            else if (key === 'intelligence_level' || key.includes('intelligence_level_') ||
                     key.includes('ai_') || key.includes('smart_') ||
                     key.includes('algorithm_') || key.includes('strategy_')) {
              categories.intelligenceConfig.push([key, value]);
            }
            // 其他配置
            else {
              categories.otherConfig.push([key, value]);
            }
          });

          return categories;
        };

        // 动态字段名映射函数
        const getFieldDisplayName = (key: string): string => {
          // 公司名称字段
          if (key === 'company_name' || key.includes('company_name_')) {
            return '公司名称';
          }
          // 产业层级
          if (key === 'industry_level' || key.includes('industry_level_')) {
            return '产业层级';
          }
          // 智能水平
          if (key === 'intelligence_level' || key.includes('intelligence_level_')) {
            return '智能水平';
          }
          // 公司资金
          if (key === 'company_fund' || key.includes('company_fund_')) {
            return '公司资金';
          }
          // 公司描述
          if (key === 'description' || key.includes('description_')) {
            return '公司描述';
          }
          // 代理ID
          if (key.includes('agent_id_')) {
            return '代理ID';
          }
          // 初始资金
          if (key.includes('initial_fund_')) {
            return '初始资金';
          }
          // 原料库存名称
          if (key.includes('material_inventory_') && key.includes('_name')) {
            const match = key.match(/material_inventory_(\d+)_.*_name/);
            if (match) {
              const materialNum = match[1];
              return `原料${materialNum}库存名称`;
            }
            return '原料库存名称';
          }
          // 原料库存数量
          if (key.includes('material_inventory_') && key.includes('_quantity')) {
            const match = key.match(/material_inventory_(\d+)_.*_quantity/);
            if (match) {
              const materialNum = match[1];
              return `原料${materialNum}库存数量`;
            }
            return '原料库存数量';
          }

          // 原料字段模式匹配
          const materialMatch = key.match(/^material_(\d+)_([A-Z]\d+)_(id|name)$/);
          if (materialMatch) {
            const [, materialNum, , type] = materialMatch;
            return type === 'id' ? `原料${materialNum}产品ID` : `原料${materialNum}名称`;
          }

          // 产品字段模式匹配
          const productMatch = key.match(/^product_(\d+)_([A-Z]\d+)_(.+)$/);
          if (productMatch) {
            const [, productNum, , attribute] = productMatch;
            const attributeMap: Record<string, string> = {
              'base_price': '基础价格',
              'initial_inventory': '初始库存',
              'is_terminal_product': '是否终端产品',
              'manufacturing_cost': '生产成本',
              'name': '名称',
              'product_construct': '原料构成',
              'profit_margin': '利润率'
            };
            const displayAttribute = attributeMap[attribute] || attribute;
            return `产品${productNum}${displayAttribute}`;
          }

          // 如果没有匹配到模式，返回原字段名
          return key;
        };

        const categories = categorizeFields(paramsData);
        const collapseItems = [];

        // 基本信息
        if (categories.basicInfo.length > 0) {
          collapseItems.push({
            key: 'basic-info',
            label: `基本信息 (${categories.basicInfo.length})`,
            children: (
              <Descriptions
                size="small"
                column={1}
                bordered
                style={{ maxWidth: '400px', wordBreak: 'break-word', whiteSpace: 'normal' }}
              >
                {categories.basicInfo.map(([key, value]) => {
                   let displayValue = value;
                   if (typeof value === 'object') {
                     displayValue = JSON.stringify(value);
                   } else if (typeof value === 'string' && value.length > 100) {
                     displayValue = value.substring(0, 100) + '...';
                   }

                   const displayLabel = getFieldDisplayName(key);
                   return (
                     <Descriptions.Item key={key} label={displayLabel}>
                       {String(displayValue)}
                     </Descriptions.Item>
                   );
                 })}
               </Descriptions>
             )
           });
         }

         // 产品配置
         if (categories.productConfig.length > 0) {
           collapseItems.push({
             key: 'product-config',
             label: `产品配置 (${categories.productConfig.length})`,
             children: (
               <Descriptions
                 size="small"
                 column={1}
                 bordered
                 style={{ maxWidth: '400px', wordBreak: 'break-word', whiteSpace: 'normal' }}
               >
                 {categories.productConfig.map(([key, value]) => {
                   let displayValue = value;
                   if (typeof value === 'object') {
                     displayValue = JSON.stringify(value);
                   } else if (typeof value === 'string' && value.length > 100) {
                     displayValue = value.substring(0, 100) + '...';
                   }

                   const displayLabel = getFieldDisplayName(key);
                   return (
                     <Descriptions.Item key={key} label={displayLabel}>
                       {String(displayValue)}
                     </Descriptions.Item>
                   );
                 })}
               </Descriptions>
             )
           });
         }

         // 原料配置
         if (categories.materialConfig.length > 0) {
           collapseItems.push({
             key: 'material-config',
             label: `原料配置 (${categories.materialConfig.length})`,
             children: (
               <Descriptions
                 size="small"
                 column={1}
                 bordered
                 style={{ maxWidth: '400px', wordBreak: 'break-word', whiteSpace: 'normal' }}
               >
                 {categories.materialConfig.map(([key, value]) => {
                   let displayValue = value;
                   if (typeof value === 'object') {
                     displayValue = JSON.stringify(value);
                   } else if (typeof value === 'string' && value.length > 100) {
                     displayValue = value.substring(0, 100) + '...';
                   }

                   const displayLabel = getFieldDisplayName(key);
                   return (
                     <Descriptions.Item key={key} label={displayLabel}>
                       {String(displayValue)}
                     </Descriptions.Item>
                   );
                 })}
               </Descriptions>
             )
           });
         }

         // 智能配置
         if (categories.intelligenceConfig.length > 0) {
           collapseItems.push({
             key: 'intelligence-config',
             label: `智能配置 (${categories.intelligenceConfig.length})`,
             children: (
               <Descriptions
                 size="small"
                 column={1}
                 bordered
                 style={{ maxWidth: '400px', wordBreak: 'break-word', whiteSpace: 'normal' }}
               >
                 {categories.intelligenceConfig.map(([key, value]) => {
                   let displayValue = value;
                   if (typeof value === 'object') {
                     displayValue = JSON.stringify(value);
                   } else if (typeof value === 'string' && value.length > 100) {
                     displayValue = value.substring(0, 100) + '...';
                   }

                   const displayLabel = getFieldDisplayName(key);
                   return (
                     <Descriptions.Item key={key} label={displayLabel}>
                       {String(displayValue)}
                     </Descriptions.Item>
                   );
                 })}
               </Descriptions>
             )
           });
         }

         // 其他配置
         if (categories.otherConfig.length > 0) {
           collapseItems.push({
             key: 'other-config',
             label: `其他配置 (${categories.otherConfig.length})`,
             children: (
               <Descriptions
                 size="small"
                 column={1}
                 bordered
                 style={{ maxWidth: '400px', wordBreak: 'break-word', whiteSpace: 'normal' }}
               >
                 {categories.otherConfig.map(([key, value]) => {
                   let displayValue = value;
                   if (typeof value === 'object') {
                     displayValue = JSON.stringify(value);
                   } else if (typeof value === 'string' && value.length > 100) {
                     displayValue = value.substring(0, 100) + '...';
                   }

                   const displayLabel = getFieldDisplayName(key);
                   return (
                     <Descriptions.Item key={key} label={displayLabel}>
                       {String(displayValue)}
                     </Descriptions.Item>
                   );
                 })}
               </Descriptions>
             )
           });
         }

         if (collapseItems.length === 0) return null;

         return (
           <Collapse
             size="small"
             style={{ marginTop: 16 }}
             items={collapseItems}
           />
         );
      }



      return (
          <>
            <div style={{
              display: 'flex', flexDirection: 'column', gap: '8px',
              }}>

            {products && products.length > 0 && (
              <Descriptions
                title="主要产品"
                size="small"
                bordered
                column={1}
                style={{ maxWidth: '400px', wordBreak: 'break-word', whiteSpace: 'normal' }}
              >
                {products.map((product, index) => (
                  <Descriptions.Item
                    key={index}
                    label={product.product_name || '未知产品'}
                  >
                    <div>基准价: {product.base_price}</div>
                    <div>初始库存: {product.initial_inventory}</div>
                    <div>利润率: {product.profit_margin}%</div>
                    <div>是否终端产品: {product.is_terminal_product}</div>
                    <div>产品配方: {product.manufacturing_cost}</div>
                  </Descriptions.Item>
                ))}
              </Descriptions>
            )}

            {/* 渲染params中的静态属性信息 */}
            {renderParamsInfo()}
          </div>
        </>
      );
    });

    const DynamicInfo = React.memo(({ nodeData, historicalMetrics, metricsLoaded, currentStep, currentStepMetrics, currentDataLoaded }: { nodeData: any[], historicalMetrics: any[], metricsLoaded: boolean, currentStep: number, currentStepMetrics: any, currentDataLoaded: boolean }) => {
      // 优先使用API数据
      let companyFund, companyProducts, companyMaterials;

      if (apiDataLoaded && selectedNodeId) {
        const apiCompany = selectedApiCompany;

        if (apiCompany) {
          companyFund = apiCompany.company_fund;
          companyProducts = apiCompany.company_products;
          companyMaterials = apiCompany.company_materials;
        }
      }

      // 如果API数据不可用，回退到本地数据
      if (companyFund === undefined && nodeData && nodeData.length > 0) {
        const company = nodeData[0];
        companyFund = company.company_fund;
        companyProducts = company.company_products;
        companyMaterials = company.company_materials;
      }

      // 获取指标数据 - 只使用metrics接口数据
      const getCurrentStepMetrics = () => {
        // 只使用新的metrics接口数据，确保显示当前步数的动态属性信息
        if (currentDataLoaded && currentStepMetrics) {
          return currentStepMetrics;
        }

        return null;
      };

      const currentMetrics = getCurrentStepMetrics();



      // 渲染历史指标信息
      const renderHistoricalMetrics = () => {
        if (!currentMetrics) {
          return null;
        }

        // 动态指标字段名映射函数
        const getMetricsDisplayName = (key: string): string => {
          // 净交易金额
          if (key.includes('net_transaction_amount_')) {
            return '净交易金额';
          }
          // 总供应量
          if (key.includes('supply_total_quantity_')) {
            return '总供应量';
          }
          // 总供应金额
          if (key.includes('supply_total_amount_')) {
            return '总供应金额';
          }
          // 供应订单数
          if (key.includes('supply_orders_count_')) {
            return '供应订单数';
          }
          // 采购总量
          if (key.includes('purchase_total_quantity_')) {
            return '采购总量';
          }
          // 采购总金额
          if (key.includes('purchase_total_amount_')) {
            return '采购总金额';
          }
          // 采购订单数量
          if (key.includes('purchase_orders_count_')) {
            return '采购订单数量';
          }
          // 当前总库存
          if (key.includes('total_inventory_')) {
            return '当前总库存';
          }
          // 公司资金
          if (key === 'company_fund' || key.includes('company_fund_')) {
            return '公司资金';
          }
          // 智能水平
          if (key === 'intelligence_level' || key.includes('intelligence_level_')) {
            return '智能水平';
          }
          // 原料库存比率
          if (key.includes('material_inventory_ratio_')) {
            return '原料库存比率';
          }
          // 产品库存比率
          if (key.includes('product_inventory_ratio_')) {
            return '产品库存比率';
          }
          // 库存周转率
          if (key.includes('inventory_turnover_rate_')) {
            return '库存周转率';
          }
          // 总原料库存
          if (key.includes('total_material_inventory_')) {
            return '总原料库存';
          }
          // 总产品库存
          if (key.includes('total_product_inventory_')) {
            return '总产品库存';
          }

          // 产品库存模式匹配
          const productInventoryMatch = key.match(/^inventory_([A-Z]\d+)_product_(\d+)$/);
          if (productInventoryMatch) {
            const [, , productNum] = productInventoryMatch;
            return `产品${productNum}库存`;
          }

          // 原料库存模式匹配
          const materialInventoryMatch = key.match(/^inventory_([A-Z]\d+)_material_(\d+)$/);
          if (materialInventoryMatch) {
            const [, , materialNum] = materialInventoryMatch;
            return `原料${materialNum}库存`;
          }

          // 如果没有匹配到模式，返回原字段名
          return key;
        };

        // 动态指标分类函数
        const categorizeDynamicFields = (entries: [string, any][]) => {
          const categories = {
            financial: { name: '财务指标', fields: [] as [string, any][] },
            inventory: { name: '库存指标', fields: [] as [string, any][] },
            trading: { name: '交易指标', fields: [] as [string, any][] },
            operational: { name: '运营指标', fields: [] as [string, any][] },
            other: { name: '其他指标', fields: [] as [string, any][] }
          };

          entries.forEach(([key, value]) => {
            if (key.includes('fund') || key.includes('cost') || key.includes('amount') || key.includes('price')) {
              categories.financial.fields.push([key, value]);
            } else if (key.includes('inventory') || key.includes('stock') || key.includes('material') || key.includes('product')) {
              categories.inventory.fields.push([key, value]);
            } else if (key.includes('supply') || key.includes('purchase') || key.includes('order') || key.includes('trade')) {
              categories.trading.fields.push([key, value]);
            } else if (key.includes('intelligence') || key.includes('ratio') || key.includes('rate') || key.includes('level')) {
              categories.operational.fields.push([key, value]);
            } else {
              categories.other.fields.push([key, value]);
            }
          });

          return categories;
        };

        // 过滤掉一些基本字段，只显示指标相关的字段
        const excludeFields = ['step', 'agent_id', 'id', 'company_name', 'company_id'];
        const metricsEntries = Object.entries(currentMetrics)
          .filter(([key, value]) =>
            !excludeFields.includes(key) &&
            value !== undefined &&
            value !== null &&
            value !== ''
          );

        if (metricsEntries.length === 0) return null;

        const categorizedFields = categorizeDynamicFields(metricsEntries);

        // 渲染分类的指标
        const renderCategoryFields = (fields: [string, any][]) => {
          if (fields.length === 0) return null;

          return (
            <Descriptions
              size="small"
              column={1}
              bordered
              style={{ maxWidth: '400px', wordBreak: 'break-word', whiteSpace: 'normal' }}
            >
              {fields.map(([key, value]) => {
                let displayValue = value;

                // 格式化显示值
                if (typeof value === 'number') {
                  displayValue = value.toLocaleString();
                } else if (typeof value === 'object') {
                  displayValue = JSON.stringify(value);
                } else if (typeof value === 'string' && value.length > 100) {
                  displayValue = value.substring(0, 100) + '...';
                }

                // 获取中文字段名
                const displayLabel = getMetricsDisplayName(key);

                return (
                  <Descriptions.Item key={key} label={displayLabel}>
                    {String(displayValue)}
                  </Descriptions.Item>
                );
              })}
            </Descriptions>
          );
        };

        // 构建折叠面板项
        const collapseItems = Object.entries(categorizedFields)
          .filter(([, category]) => category.fields.length > 0)
          .map(([key, category]) => ({
            key: `dynamic-${key}`,
            label: `${category.name} (${category.fields.length})`,
            children: renderCategoryFields(category.fields)
          }));

        if (collapseItems.length === 0) return null;

        return (
          <Collapse
            size="small"
            style={{ marginTop: 16 }}
            items={collapseItems}
          />
        );
      };

      // 如果没有任何数据，返回null
      if (companyFund === undefined && (!nodeData || nodeData.length === 0) && !currentMetrics) {
        return null;
      }

      return (
        <div style={{display: 'flex', flexDirection: 'column', gap: '8px'}}>
          {/* 渲染当前步数的历史指标信息 */}
          {renderHistoricalMetrics()}
        </div>
      );
    });


       const TranscationInfo = React.memo(({ nodeData }: { nodeData: any[] }) => {
      if (!nodeData || nodeData.length === 0) return null;

      const firm_id = nodeData[0].id;
      let firm_transcations_pruchase = filteredTransactions.filter(item =>
        Number(item.purchaser_id) === firm_id 
      );
      let firm_transcations_supplier = filteredTransactions.filter(item =>
        Number(item.supplier_id) === firm_id 
      );
      const [expandedIndex1, setExpandedIndex1] = useState(null); 
      const [expandedIndex2, setExpandedIndex2] = useState(null); 
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <Collapse
            size="small"
              items={[
                {
                  key: "transaction-info",
                  label: `采购订单信息（${firm_transcations_pruchase?.length || 0}）`,
                  children: (
                    <List
                      dataSource={firm_transcations_pruchase}
                      locale={{ emptyText: "暂无交易数据" }}
                      renderItem={(item, index) => (
                        <div style={{ marginBottom: "8px" }}>
                          {/* step 方块 */}
                          <Button
                            type={expandedIndex1 === index ? "primary" : "default"}
                            shape="round"
                            size="small"
                            onClick={() =>
                              setExpandedIndex1(expandedIndex1 === index ? null : index)
                            }
                          >
                            Step {item.step}
                          </Button>

                          {/* 点击后显示详细信息 */}
                          {expandedIndex1 === index && (
                            <Descriptions
                              key={index}
                              size="small"
                              column={1}
                              bordered
                              title="交易订单"
                              style={{
                                marginTop: "8px",
                                maxWidth: "400px",
                                wordBreak: "break-word",
                                whiteSpace: "normal",
                              }}
                            >
                              <Descriptions.Item label="采购方ID">
                                {item.purchaser_id}
                              </Descriptions.Item>
                              <Descriptions.Item label="供应方ID">
                                {item.supplier_id}
                              </Descriptions.Item>
                              <Descriptions.Item label="产品名称">
                                {item.product_name}
                              </Descriptions.Item>
                              <Descriptions.Item label="交易次数">
                                {item.transaction_count}
                              </Descriptions.Item>
                              <Descriptions.Item label="总交易额">
                                {item.total_value}
                              </Descriptions.Item>
                              <Descriptions.Item label="平均单价">
                                {item.avg_price}
                              </Descriptions.Item>
                            </Descriptions>
                          )}
                        </div>
                      )}
                    />
                  ),
                },
            ]}
          />
          <></>
          <Collapse
            size="small"
              items={[
                {
                  key: "transaction-info",
                  label: `供应订单信息（${firm_transcations_supplier?.length || 0}）`,
                  children: (
                    <List
                      dataSource={firm_transcations_supplier}
                      locale={{ emptyText: "暂无交易数据" }}
                      renderItem={(item, index) => (
                        <div style={{ marginBottom: "8px" }}>
                          {/* step 方块 */}
                          <Button
                            type={expandedIndex2 === index ? "primary" : "default"}
                            shape="round"
                            size="small"
                            onClick={() =>
                              setExpandedIndex2(expandedIndex2 === index ? null : index)
                            }
                          >
                            Step {item.step}
                          </Button>

                          {/* 点击后显示详细信息 */}
                          {expandedIndex2 === index && (
                            <Descriptions
                              key={index}
                              size="small"
                              column={1}
                              bordered
                              title="交易订单"
                              style={{
                                marginTop: "8px",
                                maxWidth: "400px",
                                wordBreak: "break-word",
                                whiteSpace: "normal",
                              }}
                            >
                              <Descriptions.Item label="采购方ID">
                                {item.purchaser_id}
                              </Descriptions.Item>
                              <Descriptions.Item label="供应方ID">
                                {item.supplier_id}
                              </Descriptions.Item>
                              <Descriptions.Item label="产品名称">
                                {item.product_name}
                              </Descriptions.Item>
                              <Descriptions.Item label="交易次数">
                                {item.transaction_count}
                              </Descriptions.Item>
                              <Descriptions.Item label="总交易额">
                                {item.total_value}
                              </Descriptions.Item>
                              <Descriptions.Item label="平均单价">
                                {item.avg_price}
                              </Descriptions.Item>
                            </Descriptions>
                          )}
                        </div>
                      )}
                    />
                  ),
                },
            ]}
          />
        </div>
      );
    });
    return (
      <>
        {/* 节点基本信息 */}
        <div className="agent-header">
          <Avatar
            size={64}
            icon={<BuildOutlined />}
            style={{ backgroundColor: '#1677ff' }}
          />
          <div className="agent-title">
            <Title level={4}>
              {Array.isArray(nodeData) ? nodeData[0].company_name : nodeData.name}
            </Title>
            <Tooltip title={<span>Industry Level</span>}>
              {(() => {
                // 优先使用通过API获取的层级信息
                if (companyLevel) {
                  const levelText = `${companyLevel.level}级产业`;
                  return <Tag color={companyLevel.color}>{levelText}</Tag>;
                }

                // 回退逻辑：如果没有API层级信息，使用原有逻辑
                let displayLevel = '';
                if (Array.isArray(nodeData)) {
                  const company = nodeData[0];
                  displayLevel = company.industry_level || company.level;

                  if (!displayLevel) {
                    const companyName = company.company_name;
                    const firstLetter = companyName.charAt(0).toUpperCase();
                    if (firstLetter === 'A') {
                      displayLevel = 'level_1';
                    } else if (firstLetter === 'B') {
                      displayLevel = 'level_2';
                    } else if (firstLetter === 'C') {
                      displayLevel = 'level_3';
                    } else {
                      const charCode = firstLetter.charCodeAt(0) - 65;
                      const levelIndex = (charCode % 3) + 1;
                      displayLevel = `level_${levelIndex}`;
                    }
                  }
                } else {
                  displayLevel = nodeData?.level || 'unknown';
                }

                const levelText = displayLevel === 'level_1' ? '一级产业' :
                                 displayLevel === 'level_2' ? '二级产业' :
                                 displayLevel === 'level_3' ? '三级产业' : '未知类型';

                const levelColor = displayLevel === 'level_1' ? 'blue' :
                                  displayLevel === 'level_2' ? 'green' :
                                  displayLevel === 'level_3' ? 'orange' : 'default';

                return <Tag color={levelColor}>{levelText}</Tag>;
              })()}
            </Tooltip>
          </div>
          <Button
            shape="circle"
            icon={<CloseOutlined />}
            size='small'
            className="close-button"
            onClick={() => {
              // 触发自定义事件，通知其他组件节点被取消选中
              const event = new CustomEvent('nodeSelected', {
                detail: { nodeId: null, nodeData: null }
              });
              window.dispatchEvent(event);
              setNodeData(null);
              setNodeHistory([]);
            }}
          />
        </div>

        <Divider style={{ margin: '12px 0' }} />

        {/* 节点详细信息 */}
        <div className="info-section">
          <div className="section-header">
            <BuildOutlined />
            <Text strong>静态属性信息</Text>
          </div>
          <div className="info-grid" style={{marginTop:10,maxHeight:"300px"}}>
            {(() => {
              return (
                <>
                  <StaticInfo agentInfo={agentInfo} />
                </>
              );
            })()}
          </div>
        </div>

        <Divider style={{ margin: '12px 0' }} />

        <div className="info-section">
          <div className="section-header">
            <BuildOutlined />
            <Text strong>动态属性信息</Text>
          </div>
          <div className="info-grid" style={{marginTop:10,maxHeight:"300px"}}>
            {(() => {
              return (
                <>
                  {isRealNode && <DynamicInfo nodeData={nodeData} historicalMetrics={historicalMetrics} metricsLoaded={metricsLoaded} currentStep={currentStep} currentStepMetrics={currentStepMetrics} currentDataLoaded={currentDataLoaded} />}
                </>
              );
            })()}
          </div>
        </div>

        <Divider style={{ margin: '12px 0' }} />

        <div className="info-section">
          <div className="section-header">
            <BuildOutlined />
            <Text strong>订单信息</Text>
          </div>
          <div className="info-grid" style={{marginTop:10,maxHeight:"300px"}}>
            {(() => {
              return (
                <>
                  {isRealNode && <TranscationInfo nodeData={nodeData} />}
                </>
              );
            })()}
          </div>
        </div>

        <Divider style={{ margin: '12px 0' }} />


        {/* Status History - 显示节点行为 */}
        {/* <div className="info-section">
          <div className="section-header">
            <HistoryOutlined />
            <Text strong>Status History</Text>
          </div>
          {(() => {
            const selectedNodeId = Array.isArray(nodeData) ? nodeData[0]?.id : nodeData?.id;
            const agentInfo = store.agents.get(selectedNodeId?.toString());
            const isRealNode = Array.isArray(nodeData) || (agentInfo?.profile?.hasData === true);

            const statusHistory = [];
            for (let step = 0; step <= currentStep; step++) {
              let stepActions = [];

              if (!isRealNode) {
                // 假节点行为
                stepActions.push({
                  text: 'nothing to do',
                  type: 'none'
                });
              } else {
                const stepData = nodeHistory.find(item => item.step === step);

                if (stepData && stepData.id === selectedNodeId) {
                  // 1. 处理交易行为 (transaction_list)
                  if (stepData.transaction_list?.length > 0) {
                    stepData.transaction_list.forEach((transaction) => {
                      const { Purchaser: purchaser, Supplier: supplier, product_name } = transaction;
                      if (purchaser === selectedNodeId || supplier === selectedNodeId) {
                        const otherParty = purchaser === selectedNodeId ? supplier : purchaser;
                        const role = purchaser === selectedNodeId ? '买方' : '卖方';
                        stepActions.push({
                          text: `交易: 作为${role} - 与节点${otherParty}交易${product_name}`,
                          type: 'transaction'
                        });
                      }
                    });
                  }

                  // 2. 处理消息行为 (record)
                  if (stepData.record?.length > 0) {
                    stepData.record.forEach((record) => {
                      const actionType = record.content?.type || record.operation_type;
                      if (actionType) {
                        const otherPartyId = record.source || record.content?.from || 'unknown';
                        stepActions.push({
                          text: `${actionType} - 与节点${otherPartyId}`,
                          type: actionType==="operation-price"?'message':'message1' // 之后type多了再详细区分这俩的type用于颜色划分
                        });
                      }
                    });
                  }
                }

                // 没有行为的情况
                if (stepActions.length === 0) {
                  stepActions.push({
                    text: 'nothing to do',
                    type: 'none'
                  });
                }
              }

              statusHistory.push({
                step,
                actions: stepActions
              });
            }

            // 类型到颜色的映射
            const actionColors = {
              transaction: 'blue',
              message1: 'green',
              message2: 'orange',
              default: 'purple',
              none: 'default'
            };

            return (
              <List
                className="status-history-list"
                dataSource={statusHistory}
                locale={{ emptyText: <Empty description={`当前步骤 ${currentStep} 没有记录`} /> }}
                renderItem={(item) => (
                  <Card
                    className='status-history-card'
                    size="small"
                    bordered={false}
                    style={{ marginBottom: '8px' }}
                  >
                    <div className="status-history-time">
                      Step {item.step}
                      <Badge count={item.step} size="small" style={{ backgroundColor: '#1677ff', marginLeft: '5px' }} />
                    </div>
                    <div className="status-history-action">
                      {item.actions.map((action, actionIndex) => (
                        <Tag
                          key={actionIndex}
                          color={actionColors[action.type] || actionColors.default}
                          style={{
                            marginBottom: '4px',
                            marginRight: '4px',
                            border: action.type === 'none' ? '1px dashed #ccc' : 'none'
                          }}
                        >
                          {action.text}
                        </Tag>
                      ))}
                    </div>
                  </Card>
                )}
              />
            );
          })()}
        </div> */}
      </>
    );
  }, [nodeData, currentStep, historicalMetrics, metricsLoaded, formatProductList, selectedApiCompany, filteredTransactions, store.agents]);

  return (
    <Flex vertical className={rootClass}>
      {/* 头部区域 */}
      <div className="panel-content" style={{
          width: '100%',         // 重要：确保填满容器
          display: 'flex',
          flexDirection: 'column',
          gap: '12px'
      }}>
        {nodeData ? (
          renderNodeContent()
        ) : agent ? (
          <>
            {/* Agent基本信息 */}
            <div className="agent-header">
              <Avatar
                size={64}
                icon={<UserOutlined />}
                style={{ backgroundColor: '#1677ff' }}
              />
              <div className="agent-title">
                <Title level={4}>{agentName}</Title>
                <Tooltip title={<span>Agent ID: {agent?.id}</span>}>
                  <Tag color="processing">ID: {typeof agent?.id === 'string' ? agent.id.substring(0, 8) : agent?.id}...</Tag>
                </Tooltip>
              </div>
              <Button
                shape="circle"
                icon={<CloseOutlined />}
                size='small'
                className="close-button"
                onClick={() => { store.setClickedAgentID(undefined) }}
              />
            </div>

            <Divider style={{ margin: '12px 0' }} />

            {/* Agent详细信息 */}
            <div className="info-section">
              <div className="section-header">
                <UserOutlined />
                <Text strong>Profile</Text>
              </div>
              <div className="info-grid">
                {agent && agent.profile && !dataReady ? (
                  <div style={{ padding: '20px', textAlign: 'center', gridColumn: 'span 2' }}>
                    <Spin size="small" />
                    <div style={{ marginTop: '8px' }}>加载中...</div>
                  </div>
                ) : (
                  agent && agent.profile &&
                  Object.entries(agent.profile)
                    .filter(([k, v]) => v !== undefined && v !== null && v !== '' && v !== '-' && v !== 0)
                    .map(([k, v]) => {
                      let displayValue = v;
                      try {
                        if (k === 'main_products' || k === 'relative_products' || k.includes('product') || k.includes('material')) {
                          displayValue = formatProductList(v);
                        } else if (typeof v === 'object') {
                          // 对象类型，转换为格式化的字符串
                          if (Array.isArray(v) && v.length > 0) {
                             // 如果是对象数组，尝试提取关键信息
                             displayValue = v.map(item => {
                               if (typeof item === 'string') return item;
                               if (typeof item !== 'object' || item === null) return String(item);

                               // 处理不同类型的对象
                               if (item.name) return item.name;
                               if (item.id && (item.name || item.title)) return `${item.id}: ${item.name || item.title}`;
                               if (item.material_id !== undefined && item.material_name) return item.material_name;
                               if (item.product_id !== undefined && item.product_name) return item.product_name;

                               // 尝试提取有意义的信息
                               const values = Object.values(item).filter(val =>
                                 typeof val === 'string' || typeof val === 'number'
                               );
                               if (values.length > 0) return values.join(': ');

                               return JSON.stringify(item);
                             }).join(', ');

                            // 如果结果太长，截断显示
                            if (displayValue.length > 100) {
                              displayValue = displayValue.substring(0, 100) + '...';
                            }
                          } else {
                            // 其他对象类型，转换为格式化的字符串
                            displayValue = JSON.stringify(v, null, 2);
                          }
                        } else if (typeof v === 'string' && v.length > 100) {
                          // 长字符串截断
                          displayValue = v.substring(0, 100) + '...';
                        }
                      } catch (error) {
                        // 处理错误，确保不会因为格式化失败而导致渲染失败
                        console.error(`Error formatting value for key ${k}:`, error);
                        displayValue = String(v);
                      }
                      return (
                        <div className='info-item' key={k}>
                          <Text type="secondary">{k}:</Text>
                          <Text strong className="info-value">{displayValue}</Text>
                        </div>
                      );
                    })
                )}
              </div>
            </div>

            <Divider style={{ margin: '12px 0' }} />

            {/* 当前状态 */}
            <div className="info-section">
              <div className="section-header">
                <DashboardOutlined />
                <Text strong>Current Status</Text>
              </div>
              <div className="info-grid">
                {agent && agent.status && !dataReady ? (
                  <div style={{ padding: '20px', textAlign: 'center', gridColumn: 'span 2' }}>
                    <Spin size="small" />
                    <div style={{ marginTop: '8px' }}>加载中...</div>
                  </div>
                ) : (agent && agent.status && (() => {
                  const entries = Object.entries(agent.status)
                    .filter(([k, v]) => k !== "firm_list" && k !== 'product_inventory');
                  return (
                    <>
                      {entries.map(([k, v]) => {
                        let displayValue = v;
                        try {
                          if (k === 'main_products' || k.includes('product') || k.includes('material')) {
                            displayValue = formatProductList(v);
                          } else if (typeof v === 'object') {
                            // 对象类型，转换为格式化的字符串
                            if (Array.isArray(v) && v.length > 0) {
                               // 如果是对象数组，尝试提取关键信息
                               displayValue = v.map(item => {
                                 if (typeof item === 'string') return item;
                                 if (typeof item !== 'object' || item === null) return String(item);

                                 // 处理不同类型的对象
                                 if (item.name) return item.name;
                                 if (item.id && (item.name || item.title)) return `${item.id}: ${item.name || item.title}`;
                                 if (item.material_id !== undefined && item.material_name) return item.material_name;
                                 if (item.product_id !== undefined && item.product_name) return item.product_name;

                                 // 尝试提取有意义的信息
                                 const values = Object.values(item).filter(val =>
                                   typeof val === 'string' || typeof val === 'number'
                                 );
                                 if (values.length > 0) return values.join(': ');

                                 return JSON.stringify(item);
                               }).join(', ');

                              // 如果结果太长，截断显示
                              if (displayValue.length > 100) {
                                displayValue = displayValue.substring(0, 100) + '...';
                              }
                            } else {
                              // 其他对象类型，转换为格式化的字符串
                              displayValue = JSON.stringify(v, null, 2);
                            }
                          } else if (typeof v === 'string' && v.length > 100) {
                            // 长字符串截断
                            displayValue = v.substring(0, 100) + '...';
                          }
                        } catch (error) {
                          // 处理错误，确保不会因为格式化失败而导致渲染失败
                          console.error(`Error formatting value for key ${k}:`, error);
                          displayValue = String(v);
                        }
                        return (
                          <div className='info-item' key={k}>
                            <Text type="secondary">{getFieldDisplayName(k)}:</Text>
                            <Text strong className="info-value">{displayValue}</Text>
                          </div>
                        );
                      })}

                      {/* 特殊处理 product_inventory */}
                      {agent.status.product_inventory && typeof agent.status.product_inventory === 'object' && !dataReady ? (
                        <div className="inventory-section">
                          <Text type="secondary" className="inventory-title">{getFieldDisplayName('product_inventory')}:</Text>
                          <div style={{ padding: '10px', textAlign: 'center' }}>
                            <Spin size="small" />
                            <div style={{ marginTop: '8px' }}>加载库存数据...</div>
                          </div>
                        </div>
                      ) : (agent.status.product_inventory && (() => {
                        // 限制显示的产品数量，避免过多数据导致渲染缓慢
                        const maxDisplayItems = 20;
                        const inventory = agent.status.product_inventory;
                        let entries = [];

                        try {
                          // 处理不同格式的库存数据
                          if (typeof inventory === 'string') {
                            // 如果是字符串，尝试解析为JSON
                            const parsed = JSON.parse(inventory);
                            if (Array.isArray(parsed)) {
                              // 如果是数组，尝试提取产品信息
                              entries = parsed.map(item => {
                                if (typeof item === 'object' && item !== null) {
                                  // 处理不同格式的产品对象
                                  const name = item.product_name || item.material_name || item.name || Object.values(item)[0];
                                  const quantity = item.quantity || item.count || item.amount || 1;
                                  return [name, quantity];
                                }
                                return [String(item), 1];
                              });
                            } else if (typeof parsed === 'object' && parsed !== null) {
                              // 如果是对象，直接使用键值对
                              entries = Object.entries(parsed);
                            }
                          } else if (typeof inventory === 'object' && inventory !== null) {
                            if (Array.isArray(inventory)) {
                              // 如果是数组，尝试提取产品信息
                              entries = inventory.map(item => {
                                if (typeof item === 'object' && item !== null) {
                                  // 处理不同格式的产品对象
                                  const name = item.product_name || item.material_name || item.name ||
                                    (item.material_id !== undefined && item.material_name ? item.material_name : null) ||
                                    (item.product_id !== undefined && item.product_name ? item.product_name : null) ||
                                    JSON.stringify(item);
                                  const quantity = item.quantity || item.count || item.amount || 1;
                                  return [name, quantity];
                                }
                                return [String(item), 1];
                              });
                            } else {
                              // 如果是对象，直接使用键值对
                              entries = Object.entries(inventory);
                            }
                          }
                        } catch (error) {
                          console.error('解析库存数据出错：', error);
                          // 如果解析失败，尝试直接显示原始数据
                          entries = [[typeof inventory === 'string' ? inventory : JSON.stringify(inventory), '']];
                        }

                        // 过滤掉无效条目
                        entries = entries.filter(([name]) => name && name !== 'undefined' && name !== 'null');

                        const displayEntries = entries.slice(0, maxDisplayItems);
                        const hasMore = entries.length > maxDisplayItems;

                        return (
                          <div className="inventory-section">
                            <Text type="secondary" className="inventory-title">
                              {getFieldDisplayName('product_inventory')}: {entries.length > 0 ? `(${entries.length} items)` : ''}
                            </Text>
                            <div className="inventory-grid">
                              {displayEntries.map(([product, quantity], index) => (
                                <div className="inventory-item" key={index}>
                                  <Text>{product}</Text>
                                  <Tag color="blue">{String(quantity)}</Tag>
                                </div>
                              ))}
                              {hasMore && (
                                <div className="inventory-item">
                                  <Text type="secondary">...and {entries.length - maxDisplayItems} more items</Text>
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })())}
                    </>
                  );
                })())}
              </div>
            </div>

            <Divider style={{ margin: '12px 0' }} />

            {/* 状态历史 */}
            <div className="info-section">
              <div className="section-header">
                <HistoryOutlined />
                <Text strong>Status History</Text>
              </div>
              {!dataReady ? (
                <div style={{ padding: '20px', textAlign: 'center' }}>
                  <Spin size="small" />
                  <div style={{ marginTop: '8px' }}>加载历史记录...</div>
                </div>
              ) : (
                <List
                  className="status-history-list"
                  dataSource={agentStatuses.slice().reverse()}
                  renderItem={renderItem}
                  locale={{ emptyText: <Empty description="No history records" /> }}
                />
              )}
            </div>
          </>
        ) : (
          <div className="empty-state">
            <Empty 
              description="Select a node or agent to view details" 
              image={Empty.PRESENTED_IMAGE_SIMPLE} 
            />
            {store.agents.size > 0 && (
              <div style={{ marginTop: '20px', textAlign: 'center' }}>
                <Text strong>Available Agents:</Text>
                <div style={{ marginTop: '10px' }}>
                  {Array.from(store.agents.values()).map(agent => (
                    <Button 
                      key={agent.id}
                      type="primary"
                      style={{ margin: '5px' }}
                      onClick={() => store.setClickedAgentID(agent.id)}
                    >
                      {agent.name || (typeof agent.id === 'string' ? agent.id.substring(0, 8) : agent.id)}
                    </Button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </Flex>
  );
});

export default InfoPanel;