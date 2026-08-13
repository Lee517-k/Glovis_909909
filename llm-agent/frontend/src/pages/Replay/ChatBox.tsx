import { Button, Flex, message, Modal, Select, Tabs, Typography, Avatar, Card, Tooltip, Empty, Tag, List, Badge, Drawer, Collapse } from 'antd';
import {
  SendOutlined,
  UserOutlined,
  RobotOutlined,
  FormOutlined,
  EyeOutlined,
  MessageOutlined,
  BuildOutlined,
  ShopOutlined,
  HistoryOutlined,
  DatabaseOutlined,
  BarsOutlined
} from '@ant-design/icons';
import CompanyThinking from './components/CompanyThinking';
import { AgentDialog, AgentSurvey } from './components/type';
import { Bubble, Sender } from '@ant-design/x';
import { parseT } from '../../components/util';
import React, { useContext, useState, useEffect } from 'react';
import { observer } from 'mobx-react-lite';
import { StoreContext } from './store';
import { Model, Survey as SurveyUI } from 'survey-react-ui';
import Item from 'antd/es/list/Item';
import { Api } from '../../services/api';

const { Text, Title } = Typography;

// 定义聊天角色样式
const roles = {
  self: {
    placement: 'start',
    avatar: {
      icon: <RobotOutlined />,
      style: { background: '#1677ff', color: '#fff' }
    },
    style: {
      maxWidth: 600,
      background: 'rgba(22, 119, 255, 0.1)',
      border: '1px solid rgba(22, 119, 255, 0.2)',
    },
  },
  otherAgent: {
    placement: 'end',
    avatar: {
      icon: <RobotOutlined />,
      style: { background: '#52c41a', color: '#fff' }
    },
    style: {
      maxWidth: 600,
      background: 'rgba(82, 196, 26, 0.1)',
      border: '1px solid rgba(82, 196, 26, 0.2)',
    },
  },
  user: {
    placement: 'end',
    avatar: {
      icon: <UserOutlined />,
      style: { background: '#722ed1', color: '#fff' }
    },
    style: {
      maxWidth: 600,
      background: 'rgba(114, 46, 209, 0.1)',
      border: '1px solid rgba(114, 46, 209, 0.2)',
    },
  },
};

interface ChatBoxProps {
  exp_id: string;
}

export const ChatBox = observer((props: ChatBoxProps) => {
  const exp_id = props.exp_id
  const store = useContext(StoreContext);
  const agent = store.clickedAgent;
  const agentDialogs = store.clickedAgentDialogs;
  const agentSurveys = store.clickedAgentSurveys;

  const [content, setContent] = useState<string>('');
  const [openPreview, setOpenPreview] = useState(false);
  const [previewSurvey, setPreviousSurvey] = useState<string>();
  const [nodeData, setNodeData] = useState<any>(null);
  const [nodeHistory, setNodeHistory] = useState<any[]>([]);
  const [nodeId, setNodeId] = useState<string | null>(null);
  const [nodeInquiries, setNodeInquiries] = useState<any[]>([]);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [allStateData, setAllStateData] = useState<any[]>([]);
  const [behaviorCategories, setBehaviorCategories] = useState<any>({});
  const [showRawDataDrawer, setShowRawDataDrawer] = useState<boolean>(false);
  const [currentThinkingContent, setCurrentThinkingContent] = useState<string[]>([]);
  const [apiCompanies, setApiCompanies] = useState<any[]>([]);
  const [apiTransactions, setApiTransactions] = useState<any[]>([]);
  const [apiCommunications, setApiCommunications] = useState<any[]>([]);
  const [allStepsWorkHistory, setAllStepsWorkHistory] = useState<any>({});

  // 监听节点选择事件 - 完全复制InfoPanel的逻辑
  useEffect(() => {
    const handleNodeSelected = (event: any) => {
      const { nodeId, nodeData } = event.detail;
      console.log('ChatBox: Node selected event received:', nodeId, nodeData);
      console.log('ChatBox: Event detail:', event.detail);
      if (nodeId) {
        // 从store中获取本地数据
        const localData = store._localData;
        console.log('Local data available:', localData ? localData.length : 0, 'records');

        // 调试：打印前几条数据的结构
        if (localData && localData.length > 0) {
          console.log('Sample local data structure:', localData.slice(0, 3).map(item => ({
            id: item.id,
            company_name: item.company_name,
            step: item.step
          })));

          // 查找所有包含ID 15的记录
          const id15Records = localData.filter(item =>
            item.id === 15 || item.id === '15' ||
            item.company_name === '15' || item.company_name === 'D3'
          );
          console.log('Records with ID 15 or company D3:', id15Records.length, id15Records.slice(0, 2));
        }

        if (localData && Array.isArray(localData) && localData.length > 0) {
          // 保存完整的state数据用于思考记录查找
          setAllStateData(localData);
          // 根据节点ID筛选数据，支持通过company_name或id匹配
          // 增强匹配逻辑，支持多种ID格式
          const nodeSpecificData = localData.filter(item => {
            const itemId = item.id ? item.id.toString() : '';
            const itemCompanyName = item.company_name ? item.company_name.toString() : '';
            const searchNodeId = nodeId ? nodeId.toString() : '';

            console.log(`匹配检查: nodeId=${searchNodeId}, item.id=${itemId}(${typeof item.id}), item.company_name=${itemCompanyName}(${typeof item.company_name})`);

            // 尝试多种匹配方式
            const matches = [
              // 直接字符串匹配
              itemId === searchNodeId,
              itemCompanyName === searchNodeId,
              // 数字匹配
              parseInt(itemId) === parseInt(searchNodeId),
              // 如果nodeId是数字，尝试匹配公司名称中的数字部分
              itemCompanyName.match(/\d+/)?.[0] === searchNodeId,
              // 如果nodeId是公司名称格式（如D3），尝试匹配ID
              itemId === searchNodeId.match(/\d+/)?.[0],
              // 特殊处理：如果item.company_name是D3格式，nodeId是15
              itemCompanyName.match(/[A-Z]+(\d+)/)?.[1] === searchNodeId
            ];

            const isMatch = matches.some(match => match === true);
            if (isMatch) {
              console.log(`✅ 节点匹配成功: nodeId=${searchNodeId}, item.id=${itemId}, item.company_name=${itemCompanyName}`);
            }
            return isMatch;
          });
          console.log('Node specific data found:', nodeSpecificData.length, 'records for node', nodeId);
          console.log('All state data saved:', localData.length, 'total records');

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
            console.log('Max step found for node', nodeId, ':', maxStep);

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
            console.log("processedData",fullStepHistory,processedData,currentStep)
            setNodeData(fullStepHistory);
            setNodeHistory(fullStepHistory);
            setNodeId(nodeId);
            setCurrentThinkingContent([]); // 重置思考内容
            console.log('Node history set with steps:', fullStepHistory.map(item => item.step));
            // 分析行为类别
            setTimeout(() => analyzeBehaviorCategories(), 100);
            // 获取所有步数的工作历史
            const numericNodeId = parseInt(nodeId.toString().match(/\d+/)?.[0] || nodeId.toString());
            console.log('WORK-🎯 Node selected, extracting numeric ID:', nodeId, '->', numericNodeId);
            if (!isNaN(numericNodeId)) {
              console.log('WORK-🚀 Starting work history fetch for company:', numericNodeId);
              setTimeout(() => fetchAllStepsWorkHistory(numericNodeId), 200);
            } else {
              console.log('WORK-⚠️ Invalid numeric node ID, skipping work history fetch');
            }
          } else {
            console.log('No data found for node:', nodeId);
            // 即使没有找到通信记录，也要设置基本的节点数据以显示界面
            const emptyNodeData = [{ step: 0, record: [] }];
            setNodeData(emptyNodeData);
            setNodeHistory(emptyNodeData);
            setNodeId(nodeId);
            setCurrentThinkingContent([]); // 重置思考内容
          }
        } else {
          // 如果没有本地数据，使用传入的nodeData
          if (nodeData) {
            setNodeData(nodeData);
            setNodeId(nodeId);
            setCurrentThinkingContent([]); // 重置思考内容
            if (Array.isArray(nodeData)) {
              const sortedData = [...nodeData].sort((a, b) => a.step - b.step);
              setNodeHistory(sortedData);
            } else {
              setNodeHistory([]);
            }
          } else {
            setNodeData(null);
            setNodeHistory([]);
            setNodeId(null);
            setCurrentThinkingContent([]); // 重置思考内容
          }
        }
      } else {
        setNodeData(null);
        setNodeHistory([]);
        setNodeId(null);
        setCurrentThinkingContent([]); // 重置思考内容
      }
    };

    // 监听时间轴变化事件，更新当前步骤 - 完全复制InfoPanel的逻辑
    const handleTimelineChange = (event: any) => {
      const { step } = event.detail;
      // 确保使用step作为主要标识，不再依赖具体时间
      setCurrentStep(step);
      setCurrentThinkingContent([]); // 重置思考内容，让useEffect重新获取
      console.log('Timeline changed, current step:', step);

      // 如果有节点数据，更新显示的历史记录
      if (nodeHistory.length > 0) {
        const filteredHistory = nodeHistory.filter(item => item.step <= step);
        console.log(`Filtered history: ${filteredHistory.length} items of ${nodeHistory.length} total`);

        // 检查当前步骤是否有记录
        const currentStepRecord = nodeHistory.find(item => item.step === step);
        if (currentStepRecord) {
          console.log(`Current step ${step} has record:`, currentStepRecord.record.length > 0 ? 'Yes' : 'No (empty)');
          // 更新nodeData为当前步骤的数据，这样通信详情useEffect会重新触发
          setNodeData(currentStepRecord);
        } else {
          console.log(`Current step ${step} has no record entry`);
          // 如果当前步骤没有记录，使用最近的有效记录或创建空记录
          const latestRecord = filteredHistory[filteredHistory.length - 1];
          if (latestRecord) {
            // 创建一个当前步骤的空记录，保持公司信息但清空record
            const emptyStepRecord = {
              ...latestRecord,
              step: step,
              record: []
            };
            setNodeData(emptyStepRecord);
          }
        }
      }
    };

    // 监听气泡点击事件，高亮连接的节点
    const handleBubbleClick = (event: any) => {
      const { companyId, targetCompanyId } = event.detail;
      if (companyId && targetCompanyId) {
        // 触发自定义事件，通知图谱组件高亮连接
        const highlightEvent = new CustomEvent('highlightConnection', {
          detail: { sourceId: companyId, targetId: targetCompanyId }
        });
        window.dispatchEvent(highlightEvent);
      }
    };

    console.log('ChatBox: Setting up event listeners');
    window.addEventListener('nodeSelected', handleNodeSelected);
    window.addEventListener('timelineChange', handleTimelineChange);
    window.addEventListener('bubbleClick', handleBubbleClick);

    return () => {
      console.log('ChatBox: Cleaning up event listeners');
      window.removeEventListener('nodeSelected', handleNodeSelected);
      window.removeEventListener('timelineChange', handleTimelineChange);
      window.removeEventListener('bubbleClick', handleBubbleClick);
    };
  }, []);

  // 生成Select选项
  const selectOptions = Array.from(store.id2surveys.values()).map(item => ({
    value: item.id,
    label: item.name,
  }));

  // 分析节点的所有行为类别
  const analyzeBehaviorCategories = () => {
    if (!nodeData || !apiData) return;

    const nodeDataItem = Array.isArray(nodeData) ? nodeData[0] : nodeData;
    if (!nodeDataItem) return;

    // 获取节点ID
    let selectedNodeId;
    let agent_id;
    const nodeIdStr = nodeId.toString();

    if (/^\d+$/.test(nodeIdStr)) {
      selectedNodeId = parseInt(nodeIdStr);
      agent_id = selectedNodeId;
    } else {
      const numericMatch = nodeIdStr.match(/\d+/);
      if (numericMatch) {
        selectedNodeId = parseInt(numericMatch[0]);
        agent_id = selectedNodeId;
      } else {
        if (nodeDataItem.id) {
          selectedNodeId = parseInt(nodeDataItem.id.toString());
          agent_id = selectedNodeId;
        } else {
          selectedNodeId = nodeIdStr;
          agent_id = nodeIdStr;
        }
      }
    }

    const categories = {};

    // 分析所有步骤的行为
    for (let step = 0; step <= store.maxStep; step++) {
      const stepTransactions = (apiTransactions || []).filter(t =>
        parseInt(t.purchaser_id) === selectedNodeId && t.step === step
      );

      const stepCommunications = (apiCommunications || []).filter(c =>
        parseInt(c.source_company_id) === selectedNodeId && c.step === step
      );

      // 统计交易行为
      stepTransactions.forEach(transaction => {
        const categoryKey = 'transaction';
        if (!categories[categoryKey]) {
          categories[categoryKey] = {
            name: '交易行为',
            steps: [],
            count: 0
          };
        }
        if (!categories[categoryKey].steps.includes(step)) {
          categories[categoryKey].steps.push(step);
        }
        categories[categoryKey].count++;
      });

      // 统计通信行为
      stepCommunications.forEach(communication => {
        const operationType = communication.operation_type || 'communication';
        let categoryKey = 'communication';
        let categoryName = '通信行为';

        if (operationType === 'operation-price') {
          categoryKey = 'communication-price';
          categoryName = '价格询问';
        } else if (operationType === 'operation-deal') {
          categoryKey = 'communication-deal';
          categoryName = '交易确认';
        } else if (operationType === 'operation-reject') {
          categoryKey = 'communication-reject';
          categoryName = '拒绝通信';
        } else if (operationType === 'operation-build') {
          categoryKey = 'communication-build';
          categoryName = '建立联系';
        } else if (operationType === 'check_manufacturing_decison'){
          categoryKey = 'check_manufacturing_decison';
          categoryName = '生产确认'
        } else if (operationType === 'update_sell_price'){
          categoryKey = 'update_sell_price';
          categoryName = '售价确认'
        } else if (operationType === 'update_payment_method'){
          categoryKey = 'update_payment_method';
          categoryName = '付款方式确认'
        }

        if (!categories[categoryKey]) {
          categories[categoryKey] = {
            name: categoryName,
            steps: [],
            count: 0
          };
        }
        if (!categories[categoryKey].steps.includes(step)) {
          categories[categoryKey].steps.push(step);
        }
        categories[categoryKey].count++;
      });
    }

    // 对每个类别的步骤进行排序
    Object.keys(categories).forEach(key => {
      categories[key].steps.sort((a, b) => a - b);
    });

    setBehaviorCategories(categories);
  };

  // 获取所有步数的工作历史数据
  const fetchAllStepsWorkHistory = async (companyId: number) => {
    try {
      console.log('WORK-🔍 Fetching all steps work history for company:', companyId);

      // 优先使用API数据，如果没有则回退到原有逻辑
      let allTransactions, allCommunications;

      if (apiData && apiTransactions.length > 0 && apiCommunications.length > 0) {
        console.log('WORK-📊 Using API data for work history');
        allTransactions = apiTransactions;
        allCommunications = apiCommunications;
      } else {
        console.log('WORK-📊 Falling back to original API calls');
        // 获取所有交易数据
        allTransactions = await Api.getTransaction(exp_id) || [];
        console.log('WORK-📊 All transactions data:', allTransactions.length, 'records');

        // 获取所有通信数据
        const communicationsResponse = await Api.getCommunications(exp_id, true); // include_details=true
        allCommunications = communicationsResponse?.communications || communicationsResponse || [];
        console.log('WORK-💬 All communications data:', allCommunications.length, 'records');
      }

      // 过滤出当前公司相关的数据 - 包含作为购买者、供应商、通信发起者、接收者的所有行为
       const companyTransactions = allTransactions.filter(t => {
         const isPurchaser = parseInt(t.purchaser_id) === companyId;
         const isSupplier = parseInt(t.supplier_id) === companyId;
         const isRelated = isPurchaser || isSupplier;
         console.log(`WORK-Transaction filter: purchaser_id=${t.purchaser_id}, supplier_id=${t.supplier_id}, companyId=${companyId}, isPurchaser=${isPurchaser}, isSupplier=${isSupplier}, match=${isRelated}`);
         return isRelated;
       });

       const companyCommunications = allCommunications.filter(c => {
         const isSource = parseInt(c.source_company_id) === companyId;
         const isTarget = parseInt(c.company_id) === companyId;
         const isRelated = isSource || isTarget;
         console.log(`WORK-Communication filter: source_company_id=${c.source_company_id}, company_id=${c.company_id}, companyId=${companyId}, isSource=${isSource}, isTarget=${isTarget}, match=${isRelated}`);
         return isRelated;
       });

       console.log('WORK-🎯 Filtered company transactions:', companyTransactions.length, 'records');
       console.log('WORK-🎯 Filtered company communications:', companyCommunications.length, 'records');

      // 按步数分组
      const workHistoryByStep = {};

      // 处理交易数据
      companyTransactions.forEach(transaction => {
        const step = transaction.step;
        if (!workHistoryByStep[step]) {
          workHistoryByStep[step] = {
            transactions: [],
            communications: []
          };
        }
        workHistoryByStep[step].transactions.push(transaction);
      });

      // 处理通信数据
      companyCommunications.forEach(communication => {
        const step = communication.step;
        if (!workHistoryByStep[step]) {
          workHistoryByStep[step] = {
            transactions: [],
            communications: []
          };
        }
        workHistoryByStep[step].communications.push(communication);
      });

      // 分析行为类别
      const behaviorCategories = {};

      // 直接从过滤后的数据分析，正确区分角色
      companyTransactions.forEach(transaction => {
        const isPurchaser = parseInt(transaction.purchaser_id) === companyId;
        const isSupplier = parseInt(transaction.supplier_id) === companyId;
        const behaviorType = isPurchaser ? 'purchase' : 'supply';
        const step = transaction.step;

        console.log(`WORK-🔍 Transaction analysis: step=${step}, isPurchaser=${isPurchaser}, isSupplier=${isSupplier}, behaviorType=${behaviorType}`);

        if (!behaviorCategories[behaviorType]) {
          behaviorCategories[behaviorType] = {
            count: 0,
            steps: [],
            details: []
          };
        }

        behaviorCategories[behaviorType].count++;
        if (!behaviorCategories[behaviorType].steps.includes(step)) {
          behaviorCategories[behaviorType].steps.push(step);
        }

        behaviorCategories[behaviorType].details.push({
          step: step,
          type: 'transaction',
          data: transaction
        });
      });

      companyCommunications.forEach(communication => {
        const isSource = parseInt(communication.source_company_id) === companyId;
        const isTarget = parseInt(communication.company_id) === companyId;
        const operationType = communication.operation_type || 'unknown';
        const behaviorType = isSource ? `send_${operationType}` : `receive_${operationType}`;
        const step = communication.step;

        console.log(`WORK-🔍 Communication analysis: step=${step}, isSource=${isSource}, isTarget=${isTarget}, operationType=${operationType}, behaviorType=${behaviorType}`);

        if (!behaviorCategories[behaviorType]) {
          behaviorCategories[behaviorType] = {
            count: 0,
            steps: [],
            details: []
          };
        }

        behaviorCategories[behaviorType].count++;
        if (!behaviorCategories[behaviorType].steps.includes(step)) {
          behaviorCategories[behaviorType].steps.push(step);
        }

        behaviorCategories[behaviorType].details.push({
          step: step,
          type: 'communication',
          data: communication
        });
      });

      console.log('WORK-📈 Behavior categories analyzed:', behaviorCategories);

       // 对步数进行排序
       Object.keys(behaviorCategories).forEach(key => {
         behaviorCategories[key].steps.sort((a, b) => a - b);
         console.log(`WORK-Sorted steps for ${key}:`, behaviorCategories[key].steps);
       });

       const finalResult = {
         workHistoryByStep,
         behaviorCategories,
         totalSteps: Object.keys(workHistoryByStep).length
       };

       console.log('WORK-📋 Final work history result:', finalResult);
       setAllStepsWorkHistory(finalResult);

       console.log('WORK-✅ All steps work history processing completed successfully');

    } catch (error) {
      console.error('WORK-❌ Error fetching all steps work history:', error);
      setAllStepsWorkHistory({});
    }
  };

  // 渲染工作历史
  const renderWorkHistory = () => {
    console.log('WORK-renderWorkHistory called, allStepsWorkHistory:', allStepsWorkHistory);

    if (!allStepsWorkHistory.behaviorCategories || Object.keys(allStepsWorkHistory.behaviorCategories).length === 0) {
      console.log('WORK-No behavior categories found, showing empty state');
      return (
        <Empty
          description="暂无工作历史数据"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          style={{ padding: '20px' }}
        />
      );
    }

    console.log('WORK-Rendering behavior categories:', Object.keys(allStepsWorkHistory.behaviorCategories));

    const categoryColors = {
      'purchase': 'purple',
      'supply': 'orange',
      'send_operation-price': 'blue',
      'send_operation-deal': 'green',
      'send_operation-reject': 'red',
      'send_operation-build': 'cyan',
      'receive_operation-price': 'geekblue',
      'receive_operation-deal': 'lime',
      'receive_operation-reject': 'volcano',
      'receive_operation-build': 'gold',
      'send_check_manufacturing_decison': 'default',
      'send_update_sell_price':'magenta',
      'send_update_payment_method':'yellow'
    };

    const categoryNames = {
      'purchase': '采购行为',
      'supply': '供应行为',
      'send_operation-price': '发送价格询问',
      'send_operation-deal': '发送交易确认',
      'send_operation-reject': '发送拒绝通信',
      'send_operation-build': '发送建立联系',
      'receive_operation-price': '接收价格询问',
      'receive_operation-deal': '接收交易确认',
      'receive_operation-reject': '接收拒绝通信',
      'receive_operation-build': '接收建立联系',
      'send_check_manufacturing_decison': '进行生产确认',
      'send_update_sell_price': '进行产品定价',
      'send_update_payment_method': '付款方式确认',
    };

    const collapseItems = Object.keys(allStepsWorkHistory.behaviorCategories).map(categoryKey => {
      const category = allStepsWorkHistory.behaviorCategories[categoryKey];
      console.log(`WORK-🏷️ Processing category: ${categoryKey}, count: ${category.count}, steps: ${category.steps.length}`);
      return {
        key: categoryKey,
        label: (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>
              <Tag color={categoryColors[categoryKey] || 'default'}>
                {categoryNames[categoryKey] || categoryKey}
              </Tag>
            </span>
            <Badge count={category.count} style={{ backgroundColor: '#52c41a' }} />
          </div>
        ),
        children: (
          <div>
            <div style={{ marginBottom: '12px' }}>
              <Text type="secondary">发生步数: </Text>
              <Text strong>{category.steps.length} 个步骤</Text>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
              {category.steps.map(step => (
                <Tag
                  key={step}
                  color="blue"
                  style={{ cursor: 'pointer' }}
                  onClick={() => {
                    console.log(`WORK-🎯 Step tag clicked: ${step}, triggering timeline change`);
                    // 触发时间轴变化事件
                    const event = new CustomEvent('timelineChange', {
                      detail: { step }
                    });
                    window.dispatchEvent(event);
                    console.log(`WORK-📡 Timeline change event dispatched for step: ${step}`);
                  }}
                >
                  步骤 {step}
                </Tag>
              ))}
            </div>
          </div>
        )
      };
    });

    return (
      <Collapse
        items={collapseItems}
        size="small"
        style={{ marginTop: '8px' }}
      />
    );
  };

  // 渲染行为类别统计
  const renderBehaviorCategories = () => {
    if (!nodeData || Object.keys(behaviorCategories).length === 0) {
      return (
        <Empty
          description="暂无行为数据"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          style={{ padding: '20px' }}
        />
      );
    }

    const categoryColors = {
      'transaction': 'purple',
      'communication': 'cyan',
      'communication-price': 'blue',
      'communication-deal': 'green',
      'communication-reject': 'red',
      'communication-build': 'orange'
    };

    const collapseItems = Object.keys(behaviorCategories).map(categoryKey => {
      const category = behaviorCategories[categoryKey];
      return {
        key: categoryKey,
        label: (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>
              <Tag color={categoryColors[categoryKey] || 'default'}>
                {category.name}
              </Tag>
            </span>
            <Badge count={category.count} style={{ backgroundColor: '#52c41a' }} />
          </div>
        ),
        children: (
          <div>
            <div style={{ marginBottom: '12px' }}>
              <Text type="secondary">发生步数: </Text>
              <Text strong>{category.steps.length} 个步骤</Text>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
              {category.steps.map(step => (
                <Tag
                  key={step}
                  color={step === currentStep ? 'gold' : 'default'}
                  style={{
                    cursor: 'pointer',
                    border: step === currentStep ? '2px solid #faad14' : '1px solid #d9d9d9'
                  }}
                  onClick={() => {
                    // 触发时间轴变化事件
                    const timelineEvent = new CustomEvent('timelineChange', {
                      detail: { step: step }
                    });
                    window.dispatchEvent(timelineEvent);
                  }}
                >
                  Step {step}
                </Tag>
              ))}
            </div>
          </div>
        )
      };
    });

    return (
      <Collapse
        items={collapseItems}
        size="small"
        ghost
        expandIconPosition="end"
      />
    );
  };

  // 状态管理
  const [selectedSurveyID, setSelectedSurveyID] = useState<string | undefined>(undefined);

  // 处理选择变化
  const handleSelectChange = (value: string) => {
    setSelectedSurveyID(value);
  };

  // 提交操作
  const handleSelectSubmit = async () => {
    if (!agent || !selectedSurveyID) return;

    try {
      const res = await fetch(`/api/experiments/${store.expID}/agents/${agent.id}/survey`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ survey_id: selectedSurveyID }),
      });

      if (res.status !== 200) {
        message.error('Failed to send survey');
        console.error('Failed to send survey:', res);
      } else {
        message.success('Survey sent successfully');
      }
    } catch (error) {
      message.error('Error sending survey');
      console.error('Error sending survey:', error);
    }

    setSelectedSurveyID(undefined);
  };

  // 根据消息类型确定角色
  const getRoleByChatMessage = (m: AgentDialog) => {
    if (m.type === 0) {
      return { role: "self", name: agent?.name };
    }
    if (m.type === 1) {
      if (m.speaker === "" || m.speaker === agent?.id) {
        return { role: "self", name: agent?.name };
      } else {
        const otherId = m.speaker;
        const otherAgent = store.agents.get(otherId);
        return { role: "otherAgent", name: otherAgent?.name };
      }
    }
    if (m.type === 2) {
      if (m.speaker === "") {
        return { role: "self", name: agent?.name };
      } else {
        return { role: "user", name: "User" };
      }
    }
  };

  // 问卷预览模型
  let model = new Model({});
  if (previewSurvey !== undefined) {
    try {
      model = new Model(JSON.parse(previewSurvey));
    } catch (e) {
      console.error('Failed to parse JSON data:', e);
    }
  }
  model.showCompleteButton = false;

  // 渲染节点思考内容 - 从整个state文件数据中查找soucre匹配的记录
  const renderNodeThinking = () => {
    if (!nodeData || !nodeId || !allStateData || allStateData.length === 0) {
      return (
        <div className="thinking-empty">
          <Empty description="No thinking data available" />
        </div>
      );
    }

    // Handle both array and single object cases for nodeData
    const nodeDataItem = Array.isArray(nodeData) ? nodeData[0] : nodeData;
    if (!nodeDataItem || !nodeDataItem.id) {
      return (
        <div className="thinking-empty">
          <Empty description="No valid node data available" />
        </div>
      );
    }

    // 获取当前选中节点的数字ID
    // const selectedNodeId = parseInt(nodeId.toString());  //nodeId是形如A1的名称，不对应ID
    const selectedNodeId = parseInt(nodeDataItem.id.toString());
    const selectedNodeName = nodeId.toString()
    // 创建按步数分组的思考内容
    const thinkingHistory = [];
    for (let step = 0; step <= currentStep; step++) {
      const stepThinking = [];
      // 从所有allStateData数据中查找当前步骤的记录
      allStateData.forEach(stepData => {
        if (stepData.step === step && stepData.record && stepData.record.length > 0) {
          // 根据soucre字段筛选记录（注意：JSON中字段名拼写为soucre）
          const nodeRecords = stepData.record.filter((record: any) => {
            const recordSource = record.source; // 使用正确的字段名
            const recordSourceName = record.sourceName;
            return recordSource && (recordSource === selectedNodeId || recordSourceName === selectedNodeName);
          });

          nodeRecords.forEach((record: any) => {
            // 解析content内容
            let contentText = '';

            if (record.content) {
              if (typeof record.content === 'object' && record.content.content) {
                // 如果content是对象且包含content字段，尝试解析其中的JSON字符串
                try {
                  const innerContent = JSON.parse(record.content.content);
                  if (innerContent.detailed_inquiry_text) {
                    contentText = innerContent.detailed_inquiry_text;
                  } else {
                    contentText = record.content.content;
                  }
                } catch (e) {
                  // 如果解析失败，直接使用content字段
                  contentText = record.content.content || JSON.stringify(record.content, null, 2);
                }
              } else if (typeof record.content === 'string') {
                contentText = record.content;
              } else if (typeof record.content === 'object') {
                contentText = JSON.stringify(record.content, null, 2);
              }
            }

            if (contentText && contentText.trim() !== '') {
              stepThinking.push(contentText);
            }

          });
        }
      });

      // 所有步骤都添加到历史记录，没有内容的显示'nothing to think'
      thinkingHistory.push({
        step,
        thinking: stepThinking.length > 0 ? stepThinking : ['nothing to think']
      });
    }
    return (
      <List
        className="thinking-history-list"
        dataSource={thinkingHistory}
        locale={{ emptyText: <Empty description={`当前步骤 ${currentStep} 没有记录`} /> }}
        renderItem={(item) => (item.step === currentStep && (
          <Card
            className='thinking-history-card'
            size="small"
            bordered={false}
            style={{ marginBottom: '12px' }}
          >
            <div className="thinking-history-time" style={{ marginBottom: '8px' }}>
              Step {item.step}
              <Badge count={item.step} size="small" style={{ backgroundColor: '#1677ff', marginLeft: '5px' }} />
            </div>
            <div className="thinking-history-content">
              {item.thinking.map((text: string, textIndex: number) => (
                <div key={textIndex} className="thinking-text" style={{
                  background: text === 'nothing to think' ? '#f5f5f5' : '#f8f9fa',
                  padding: '12px',
                  borderRadius: '6px',
                  marginBottom: '8px',
                  fontSize: '13px',
                  lineHeight: '1.5',
                  border: text === 'nothing to think' ? '1px solid #d9d9d9' : '1px solid #e9ecef',
                  fontStyle: text === 'nothing to think' ? 'italic' : 'normal',
                  color: text === 'nothing to think' ? '#8c8c8c' : 'inherit'
                }}>
                  {text}
                </div>
              ))}
            </div>
          </Card>
        ))}
      />
    );
  };
  const [firmlist,setFirmList] = useState([]);
  const [allDialogList,setAllDialogList] = useState([]);
  useEffect(() => {
    const fetchData = async () => {
      try {
        let response = await Api.getCompanies(exp_id)
        setFirmList(response);
      } catch (e) {
        console.error('getCompanies e', e);
      }
    };
    fetchData();
  }, [exp_id,currentStep]);

  const getNameById = (id) => {
    let name=""

    // 使用 API 数据
    if (apiCompanies.length > 0) {
      const company = apiCompanies.find(c =>
        parseInt(c.company_id) === parseInt(id) || parseInt(c.id) === parseInt(id)
      );
      if (company) {
        name = company.company_name || company.name || '';
      }
    }

    // 如果 API 数据中没找到，回退到本地数据
    if (!name && firmlist && firmlist.length > 0) {
      firmlist.forEach(firm =>{
        if(parseInt(firm["company_id"]) === parseInt(id)){
          name = firm["company_name"]
        }
      })
    }

    return name || `Company_${id}`;
  }

  const getIdByName = (name) => {
    let id=0

    // 使用 API 数据
    if (apiCompanies.length > 0) {
      const company = apiCompanies.find(c =>
        c.company_name === name || c.name === name
      );
      if (company) {
        id = company.company_id || company.id || 0;
      }
    }

    // 如果 API 数据中没找到，回退到本地数据
    if (!id && firmlist && firmlist.length > 0) {
      firmlist.forEach(firm =>{
        if(firm["company_name"] === name){
          id = firm["company_id"]
        }
      })
    }

    return id;
  }

  useEffect(() => {
    const fetchAllData = async () => {
      // 正确初始化：每个公司一个空数组
      const dialogList = Array.from({ length: firmlist?.length || 0 }, () => []);

      try {
        // 使用新的数据源：transactions 和 communications 接口
        const [transactionsData, communicationsData] = await Promise.all([
          Api.getTransaction(exp_id),
          Api.getCommunications(exp_id, true, currentStep) // 传递include_details=true和step参数获取当前步数的通信数据
        ]);

        console.log('获取到的交易数据:', transactionsData);
        console.log('获取到的通信数据:', communicationsData);

        // 从包装格式中提取实际的通信数据
        const actualCommunicationsData = communicationsData?.communications || communicationsData || [];
        console.log('提取的实际通信数据:', actualCommunicationsData);

        // 处理每个公司的数据
        (firmlist || []).forEach((firm, index) => {
          const companyId = firm["company_id"];

          // 处理交易数据 - 只纳入购买者的行为
          const companyTransactions = (transactionsData || []).filter(t => {
            const buyerId = parseInt(t.purchaser_id);
            return buyerId === companyId && t.step === currentStep;
          }).map(t => ({
            step: t.step,
            speaker: parseInt(t.purchaser_id), // 购买者
            listener: parseInt(t.supplier_id), // 供应商
            type: 'transaction',
            timestamp: t.timestamp,
            content: t
          }));

          // 处理通信数据 - 只纳入通信来源公司的行为
          const companyCommunications = (actualCommunicationsData || []).filter(c => {
            const sourceId = parseInt(c.source_company_id);
            return sourceId === companyId && c.step === currentStep;
          }).map(c => ({
            step: c.step,
            speaker: parseInt(c.source_company_id), // 通信来源
            listener: parseInt(c.company_id), // 通信接收方
            type: 'communication',
            timestamp: c.timestamp,
            content: c
          }));

          // 合并该公司的所有行为数据
          dialogList[index] = [...companyTransactions, ...companyCommunications];
        });

        console.log('处理后的对话列表:', dialogList);
      } catch (e) {
        console.error('获取数据失败:', e);
      }

      // 所有请求完成后再 set
      setAllDialogList(dialogList);
    };

    if (firmlist && firmlist.length > 0) {
      fetchAllData();
    }
  }, [firmlist, currentStep, exp_id]);

  // 单独的useEffect来处理通信详情的提取
  useEffect(() => {
    const fetchCommunicationDetails = async () => {
      // Handle both array and single object cases for nodeData
      const nodeDataItem = Array.isArray(nodeData) ? nodeData[0] : nodeData;
      if (!nodeDataItem) {
        setCurrentThinkingContent([]);
        return;
      }

      try {
        console.log('提取通信详情 - 公司ID:', nodeDataItem.id, '当前步骤:', currentStep);
        const communicationDetails = [];

        // 使用新的数据源：transactions 和 communications 接口
        const [transactionsData, communicationsData] = await Promise.all([
          Api.getTransaction(exp_id),
          Api.getCommunications(exp_id, true, currentStep) // 传递include_details=true和step参数获取当前步数的通信数据
        ]);

        console.log('交易数据:', transactionsData);
        console.log('通信数据:', communicationsData);

        // 从包装格式中提取实际的通信数据
        const actualCommunicationsData = communicationsData?.communications || communicationsData || [];
        console.log('提取的实际通信数据:', actualCommunicationsData);

        // 优先从nodeId解析数字ID，如果无法解析则尝试从nodeDataItem.id获取，最后直接使用nodeId
        let selectedNodeId;
        if (nodeId) {
          const numericMatch = nodeId.toString().match(/\d+/);
          if (numericMatch) {
            selectedNodeId = parseInt(numericMatch[0]);
          } else if (nodeDataItem.id) {
            selectedNodeId = parseInt(nodeDataItem.id.toString());
          } else {
            selectedNodeId = nodeId;
          }
        } else {
          selectedNodeId = nodeDataItem.id ? parseInt(nodeDataItem.id.toString()) : null;
        }

        if (!selectedNodeId) {
          console.log('无法获取有效的节点ID');
          setCurrentThinkingContent([]);
          return;
        }

        // 处理交易数据 - 只显示当前公司作为购买者的交易
        const relatedTransactions = (transactionsData || []).filter(t => {
          const buyerId = parseInt(t.purchaser_id);
          return buyerId === selectedNodeId && t.step === currentStep;
        });

        // 处理通信数据 - 只显示当前公司作为通信来源的通信
        const relatedCommunications = (actualCommunicationsData || []).filter(c => {
          const sourceId = parseInt(c.source_company_id);
          return sourceId === selectedNodeId && c.step === currentStep;
        });

        // 构建交易详情文本
        relatedTransactions.forEach((transaction, index) => {
          const supplierName = getNameById(transaction.supplier_id) || `Company_${transaction.supplier_id}`;
          const detailText = `交易类型: 购买\n` +
            `供应商: ${supplierName} (ID: ${transaction.supplier_id})\n` +
            `产品: ${transaction.product_name}\n` +
            `数量: ${transaction.transaction_count}\n` +
            `总价: ${transaction.total_value}\n` +
            `平均价格: ${transaction.avg_price}\n` +
            `步骤: ${transaction.step}`;

          communicationDetails.push(detailText);
          console.log(`提取交易详情 ${index + 1}:`, detailText);
        });

        // 构建通信详情文本
        relatedCommunications.forEach((communication, index) => {
          const targetName = getNameById(communication.company_id) || `Company_${communication.company_id}`;
          let detailText = `通信类型: ${communication.operation_type}\n` +
            `目标公司: ${targetName} (ID: ${communication.company_id})\n` +
            `消息数量: ${communication.message_count}\n` +
            `步骤: ${communication.step}`;

          // 添加详细通信内容
          if (communication.detail && communication.detail.content) {
            detailText += `\n\n详细通信内容:`;
            const content = communication.detail.content;

            // 根据通信类型格式化内容
            if (communication.operation_type === 'operation-price') {
              if (content.expected_products) {
                detailText += `\n期望产品: ${content.expected_products}`;
              }
              if (content.expected_quantity) {
                detailText += `\n期望数量: ${content.expected_quantity}`;
              }
              if (content.detailed_inquiry_text) {
                detailText += `\n询价详情:\n${content.detailed_inquiry_text}`;
              }
            } else if (communication.operation_type === 'operation-deal') {
              // 处理交易确认类型的通信内容
              if (typeof content === 'object') {
                Object.keys(content).forEach(key => {
                  if (content[key] !== null && content[key] !== undefined) {
                    detailText += `\n${key}: ${content[key]}`;
                  }
                });
              } else {
                detailText += `\n${content}`;
              }
            } else {
              // 其他类型的通信内容
              if (typeof content === 'object') {
                detailText += `\n${JSON.stringify(content, null, 2)}`;
              } else {
                detailText += `\n${content}`;
              }
            }
          }

          communicationDetails.push(detailText);
          console.log(`提取通信详情 ${index + 1}:`, detailText);
        });

        console.log('最终提取的详情数量:', communicationDetails.length);
        setCurrentThinkingContent(communicationDetails);
      } catch (e) {
        console.error('获取详情失败:', e);
        setCurrentThinkingContent([]);
      }
    };

    // 只有当nodeData和currentStep都存在时才提取详情
    if (nodeData && currentStep !== undefined) {
      fetchCommunicationDetails();
    } else {
      setCurrentThinkingContent([]);
    }
    // 当节点或步骤改变时，清除筛选条件
    setSelectedFilters([]);
  }, [nodeData, currentStep, exp_id]);

  const [text,setText] = useState("nothing to think")
  const [selectedFilters, setSelectedFilters] = useState<string[]>([]) // 用于存储选中的筛选条件

  // 数据库 API 数据状态
  const [apiData, setApiData] = useState(null);


  // 获取数据库 API 数据
  useEffect(() => {
    const fetchApiData = async () => {
      try {
        // 并发获取所有数据库 API 数据
        const [companiesRes, transactionsRes, communicationsRes] = await Promise.all([
          Api.getCompanies(exp_id),
          Api.getTransaction(exp_id),
          Api.getCommunications(exp_id, true) // 传递include_details=true获取包装格式
        ]);

        // 从包装格式中提取实际的通信数据
        const actualCommunicationsRes = communicationsRes?.communications || communicationsRes || [];

        setApiCompanies(companiesRes || []);
        setApiTransactions(transactionsRes || []);
        setApiCommunications(actualCommunicationsRes || []);

        // 合并所有 API 数据
        const combinedApiData = {
          companies: companiesRes || [],
          transactions: transactionsRes || [],
          communications: actualCommunicationsRes || [],
          raw_communications_response: communicationsRes // 保留原始响应用于调试
        };
        setApiData(combinedApiData);

        console.log('数据库 API 数据获取成功:', combinedApiData);
        console.log('交易数据详情:', transactionsRes);
        console.log('公司数据详情:', companiesRes);
        console.log('通信数据详情:', communicationsRes);
      } catch (error) {
        console.error('获取数据库 API 数据失败:', error);
        message.error('获取数据库数据失败');
      }
    };

    if (exp_id) {
      fetchApiData();
    }
  }, [exp_id]);

  // 当节点改变时获取该节点的所有步数工作历史
  useEffect(() => {
    if (apiData && nodeId) {
      // 解析节点ID
      const nodeIdStr = nodeId.toString();
      let agent_id;

      if (/^\d+$/.test(nodeIdStr)) {
        agent_id = parseInt(nodeIdStr);
      } else {
        const numericMatch = nodeIdStr.match(/\d+/);
        if (numericMatch) {
          agent_id = parseInt(numericMatch[0]);
        }
      }

      if (agent_id) {
        console.log('节点改变，获取工作历史数据，节点ID:', agent_id);
        fetchAllStepsWorkHistory(agent_id);
      }
    }
  }, [nodeId, apiData]);

  const renderNodeBehavior = () => {
    if (!nodeData) return null;

    // Handle both array and single object cases for nodeData
    const nodeDataItem = Array.isArray(nodeData) ? nodeData[0] : nodeData;
    if (!nodeDataItem) return null;

    // 即使没有id也要继续执行，可以从nodeId获取

    // 增强节点ID处理逻辑，支持多种ID格式
    let selectedNodeId;
    let agent_id;
    const selectedNodeName = nodeId.toString();

    // 优先从nodeId解析，因为这是用户点击的节点ID
    const nodeIdStr = nodeId.toString();
    // 如果nodeId是数字格式，直接使用
    if (/^\d+$/.test(nodeIdStr)) {
      selectedNodeId = parseInt(nodeIdStr);
      agent_id = selectedNodeId;
    } else {
      // 如果nodeId是公司名称格式（如A1, B2等），提取数字部分
      const numericMatch = nodeIdStr.match(/\d+/);
      if (numericMatch) {
        selectedNodeId = parseInt(numericMatch[0]);
        agent_id = selectedNodeId;
      } else {
        // 如果无法解析数字，尝试从nodeDataItem.id获取
        if (nodeDataItem.id) {
          selectedNodeId = parseInt(nodeDataItem.id.toString());
          agent_id = selectedNodeId;
        } else {
          // 最后直接使用nodeId
          selectedNodeId = nodeIdStr;
          agent_id = nodeIdStr;
        }
      }
    }

    let agentDialog=[];

    // 注意：不能在渲染函数中直接调用fetchAllStepsWorkHistory，会导致无限循环
    // 该调用已移至useEffect中

    // 使用数据库 API 数据
     if (apiData) {
       // 从 API 数据中查找相关的通信和交易记录
       // 增强API公司查找逻辑，支持多种ID格式匹配
       const apiCompany = apiCompanies.find(c => {
         const companyId = c.company_id ? c.company_id.toString() : '';
         const cId = c.id ? c.id.toString() : '';
         const agentIdStr = agent_id ? agent_id.toString() : '';

         // 尝试多种匹配方式
         const matches = [
           companyId === agentIdStr,
           cId === agentIdStr,
           parseInt(companyId) === parseInt(agentIdStr),
           parseInt(cId) === parseInt(agentIdStr)
         ];

         return matches.some(match => match === true);
       });

       // 处理交易数据 - 显示当前公司作为购买者或供应商的所有交易
       console.log('开始过滤交易数据，当前agent_id:', agent_id, '类型:', typeof agent_id);
       console.log('所有交易数据:', apiTransactions);
       const relatedTransactions = apiTransactions.filter(t => {
         // API返回字段：step, purchaser_id, supplier_id, product_name, transaction_count, total_value, avg_price
         // 显示当前公司作为购买者或供应商的交易
         const purchaserId = t.purchaser_id ? t.purchaser_id.toString() : '';
         const supplierId = t.supplier_id ? t.supplier_id.toString() : '';
         const agentIdStr = agent_id ? agent_id.toString() : '';

         const isPurchaser = [
           purchaserId === agentIdStr,
           parseInt(purchaserId) === parseInt(agentIdStr)
         ].some(m => m === true);

         const isSupplier = [
           supplierId === agentIdStr,
           parseInt(supplierId) === parseInt(agentIdStr)
         ].some(m => m === true);

         return isPurchaser || isSupplier;
       });
       console.log('过滤后的交易数据:', relatedTransactions);

       // 处理通信数据 - 显示当前公司作为发送方或接收方的所有通信
       const relatedCommunications = apiCommunications.filter(c => {
         // API返回字段：step, company_id, source_company_id, operation_type, message_count
         // 显示当前公司作为发送方或接收方的通信
         const sourceId = c.source_company_id ? c.source_company_id.toString() : '';
         const targetId = c.company_id ? c.company_id.toString() : '';
         const agentIdStr = agent_id ? agent_id.toString() : '';

         const isSource = [
           sourceId === agentIdStr,
           parseInt(sourceId) === parseInt(agentIdStr)
         ].some(m => m === true);

         const isTarget = [
           targetId === agentIdStr,
           parseInt(targetId) === parseInt(agentIdStr)
         ].some(m => m === true);

         return isSource || isTarget;
       });

       // 合并 API 数据作为对话记录
       agentDialog = [
         ...relatedTransactions.map(t => {
           // 对于交易：根据当前公司的角色确定speaker和listener
           const buyerId = parseInt(t.purchaser_id);
           const sellerId = parseInt(t.supplier_id);
           const agentIdNum = parseInt(agent_id);

           // 如果当前公司是购买者
           if (buyerId === agentIdNum) {
             return {
               step: t.step,
               speaker: buyerId, // 购买者（当前公司）
               listener: sellerId, // 供应商
               type: 'transaction',
               role: 'purchaser',
               timestamp: t.timestamp,
               content: t
             };
           } else {
             // 当前公司是供应商
             return {
               step: t.step,
               speaker: sellerId, // 供应商（当前公司）
               listener: buyerId, // 购买者
               type: 'transaction',
               role: 'supplier',
               timestamp: t.timestamp,
               content: t
             };
           }
         }),
         ...relatedCommunications.map(c => {
           // 对于通信：根据当前公司的角色确定speaker和listener
           const sourceId = parseInt(c.source_company_id);
           const targetId = parseInt(c.company_id);
           const agentIdNum = parseInt(agent_id);

           // 如果当前公司是通信发送方
           if (sourceId === agentIdNum) {
             return {
               step: c.step,
               speaker: sourceId, // 通信来源（当前公司）
               listener: targetId, // 通信接收方
               type: 'communication',
               role: 'sender',
               timestamp: c.timestamp,
               content: c
             };
           } else {
             // 当前公司是通信接收方
             return {
               step: c.step,
               speaker: sourceId, // 通信来源
               listener: targetId, // 通信接收方（当前公司）
               type: 'communication',
               role: 'receiver',
               timestamp: c.timestamp,
               content: c
             };
           }
         })
       ].filter(item => item.step === currentStep);

    } else {
      // 回退到原有的本地数据逻辑
      const index = firmlist && firmlist.length > 0 ? firmlist.findIndex(f => f.company_id === agent_id) : -1;
      const fullAgentDialog = allDialogList[index];
      // 过滤当前步数的数据
      agentDialog = fullAgentDialog ? fullAgentDialog.filter(record => record.step === currentStep) : [];
    }

    const statusHistory = [];
    let stepActions = [];
    let number = 0;

    if (agentDialog) {
      if (agentDialog.length > 0) {
        agentDialog.forEach((record) => {
          const actionType = record.type;
          if (actionType) {
            let text = "";
            let displayType = actionType;

            // API 数据的处理逻辑
            const speakerName = getNameById(record.speaker) || record.speaker;
            const listenerName = getNameById(record.listener) || record.listener;

            if (actionType === 'transaction') {
              // 交易：根据当前公司的角色显示不同的文本
              const productName = record.content.product_name || '商品';
              const quantity = record.content.transaction_count || 1;
              const totalValue = record.content.total_value || 0;

              if (record.role === 'purchaser') {
                // 当前公司是购买者
                const supplierName = getNameById(record.listener) || record.listener;
                text = `从 ${supplierName} 购买 ${productName} (数量: ${quantity}, 总价: ${totalValue})`;
              } else {
                // 当前公司是供应商
                const buyerName = getNameById(record.listener) || record.listener;
                text = `向 ${buyerName} 销售 ${productName} (数量: ${quantity}, 总价: ${totalValue})`;
              }
              displayType = 'transaction';
            } else if (actionType === 'communication') {
              // 通信：根据当前公司的角色显示不同的文本
              const operationType = record.content.operation_type || '通信';
              const messageCount = record.content.message_count || 1;

              if (record.role === 'sender') {
                // 当前公司是发送方
                const targetName = getNameById(record.listener) || record.listener;
                text = `向 ${targetName} 发送 ${operationType} (次数: ${messageCount})`;
              } else {
                // 当前公司是接收方
                const sourceName = getNameById(record.speaker) || record.speaker;
                text = `接收来自 ${sourceName} 的 ${operationType} (次数: ${messageCount})`;
              }

              // 根据通信类型设置不同的显示类型
              if (operationType === 'operation-price') {
                displayType = 'communication-price';
              } else if (operationType === 'operation-deal') {
                displayType = 'communication-deal';
              } else if (operationType === 'operation-reject') {
                displayType = 'communication-reject';
              } else if (operationType === 'operation-build') {
                displayType = 'communication-build';
              } else {
                displayType = 'communication';
              }
            } else {
              // 其他类型
              if (record.listener === agent_id) {
                text = `接受来自 ${speakerName} 的 ${actionType}`;
              } else {
                text = `向 ${listenerName} 发送的 ${actionType}`;
              }
              displayType = actionType;
            }

            stepActions.push({
              number: number,
              text: text,
              type: displayType,
              content: record.content
            });
            number++;
          }
        });
      }
    }
    if (stepActions.length === 0) {
      stepActions.push({
        number:-1,
        text: 'nothing to do',
        type: 'none',
        content:"",
      });
    }

    statusHistory.push({
      step: currentStep,
      actions: stepActions
    });

    const actionColors = {
      transaction: 'purple',
      communication: 'cyan',
      'communication-price': 'blue',
      'communication-deal': 'green',
      'communication-reject': 'red',
      'communication-build': 'orange',
      message1: 'green',
      message2: 'orange',
      message3: 'volcano',
      message: 'geekblue',
      default: 'blue',
      none: 'default'
    };

    // 处理筛选功能
    const handleFilterClick = (actionType: string) => {
      setSelectedFilters(prev => {
        if (prev.includes(actionType)) {
          // 如果已选中，则取消选中
          return prev.filter(filter => filter !== actionType);
        } else {
          // 如果未选中，则添加到筛选列表
          return [...prev, actionType];
        }
      });
    };

    const updateText = (action) =>{
      let statusList = statusHistory[0];
      let newStatus = statusList.actions.find(
        (a) => a.number === action.number
      );
      console.log("FCK",newStatus.content,typeof newStatus.content, JSON.stringify(newStatus.content))

      // 格式化显示内容
      let formattedText = '';
      if (newStatus.type === 'transaction' || newStatus.type === 'communication') {
        // API 数据的格式化显示
        if (newStatus.type === 'transaction') {
          const t = newStatus.content;
          const sellerId = t.supplier_id;
          const buyerId = t.purchaser_id;
          const sellerName = getNameById(sellerId) || sellerId;
          const buyerName = getNameById(buyerId) || buyerId;

          formattedText = `交易详情:\n卖方: ${sellerName}\n买方: ${buyerName}\n商品: ${t.product_name || '未知'}\n交易次数: ${t.transaction_count || '未知'}\n总价值: ${t.total_value || '未知'}\n平均价格: ${t.avg_price || '未知'}\n步数: ${t.step || '未知'}`;
        } else if (newStatus.type === 'communication') {
          const c = newStatus.content;
          const speakerId = c.source_company_id;
          const listenerId = c.company_id;
          const speakerName = getNameById(speakerId) || speakerId;
          const listenerName = getNameById(listenerId) || listenerId;

          formattedText = `通信详情:\n发送方: ${speakerName}\n接收方: ${listenerName}\n操作类型: ${c.operation_type || '未知'}\n消息数量: ${c.message_count || '未知'}\n步数: ${c.step || '未知'}`;

          // 添加详细通信内容
          if (c.detail && c.detail.content) {
            formattedText += `\n\n详细通信内容:`;
            const content = c.detail.content;

            // 根据通信类型格式化内容
            if (c.operation_type === 'operation-price') {
              if (content.expected_products) {
                formattedText += `\n期望产品: ${content.expected_products}`;
              }
              if (content.expected_quantity) {
                formattedText += `\n期望数量: ${content.expected_quantity}`;
              }
              if (content.detailed_inquiry_text) {
                formattedText += `\n询价详情:\n${content.detailed_inquiry_text}`;
              }
            } else if (c.operation_type === 'operation-deal') {
              // 处理交易确认类型的通信内容
              if (typeof content === 'object') {
                Object.keys(content).forEach(key => {
                  if (content[key] !== null && content[key] !== undefined) {
                    formattedText += `\n${key}: ${content[key]}`;
                  }
                });
              } else {
                formattedText += `\n${content}`;
              }
            } else {
              // 其他类型的通信内容
              if (typeof content === 'object') {
                formattedText += `\n${JSON.stringify(content, null, 2)}`;
              } else {
                formattedText += `\n${content}`;
              }
            }
          }
        }
      } else {
        // 原有的处理逻辑
        if (typeof newStatus.content === 'string') {
          try {
            const parsedContent = JSON.parse(newStatus.content);
            formattedText = JSON.stringify(parsedContent, null, 2);
          } catch {
            formattedText = newStatus.content;
          }
        } else {
          formattedText = JSON.stringify(newStatus.content, null, 2);
        }
      }

      setText(formattedText);
    }
    return(
      <>
        <div className="info-section">
          <div className="section-header">
            <BuildOutlined />
            <Text strong>节点行为概览</Text>
          </div>
          <div style={{ marginBottom: '16px' }}>
            <Text type="secondary" style={{ fontSize: '12px' }}>
              显示该企业在所有步数中的行为类别和具体步数
            </Text>
          </div>
          {renderWorkHistory()}
        </div>
        <div className="info-section">
          <div className="section-header">
            <HistoryOutlined />
            <Text strong>当前行为</Text>
          </div>
          {(() => {
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
                      Step {currentStep}
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
                            border: action.type === 'none' ? '1px dashed #ccc' :
                                   selectedFilters.includes(action.type) ? '2px solid #1677ff' : 'none',
                            cursor: 'pointer',
                            opacity: selectedFilters.length === 0 || selectedFilters.includes(action.type) ? 1 : 0.5
                          }}
                          onClick={(e)=>{
                            e.stopPropagation();
                            if (e.shiftKey || e.ctrlKey) {
                              // 按住Shift或Ctrl键时进行筛选
                              handleFilterClick(action.type);
                            } else {
                              // 普通点击时更新详情
                              updateText(action);
                            }
                          }}
                          onDoubleClick={()=>{
                            // 双击进行筛选
                            handleFilterClick(action.type);
                          }}
                        >
                          {action.text}
                          {selectedFilters.includes(action.type) && <span style={{marginLeft: '4px'}}>✓</span>}
                        </Tag>
                      ))}
                    </div>
                  </Card>
                )}
              />
            );
          })()}
          <div className="section-header">
            {/* <HistoryOutlined /> */}
            <Text strong>行为详情</Text>
            {selectedFilters.length > 0 && (
              <div style={{ marginTop: '8px', marginBottom: '8px' }}>
                <Text type="secondary" style={{ fontSize: '12px' }}>
                  筛选条件: {selectedFilters.join(', ')}
                </Text>
                <Button
                  size="small"
                  type="link"
                  onClick={() => setSelectedFilters([])}
                  style={{ padding: '0 4px', marginLeft: '8px' }}
                >
                  清除筛选
                </Button>
              </div>
            )}
            {(() => {
              // 根据筛选条件过滤行为详情内容
              let filteredActions = [];

              if (statusHistory.length > 0) {
                const currentStepActions = statusHistory[0].actions;

                if (selectedFilters.length > 0) {
                  // 根据选中的筛选条件过滤行为
                  filteredActions = currentStepActions.filter(action =>
                    selectedFilters.includes(action.type)
                  );
                } else {
                  // 如果没有筛选条件，显示所有行为
                  filteredActions = currentStepActions;
                }
              }

              const displayContent = filteredActions.length > 0 ?
                filteredActions.map(action => {
                  // 格式化每个行为的详细信息
                  let formattedText = '';
                  if (action.type === 'transaction') {
                    const t = action.content;
                    const sellerId = t.supplier_id;
                    const buyerId = t.purchaser_id;
                    const sellerName = getNameById(sellerId) || sellerId;
                    const buyerName = getNameById(buyerId) || buyerId;
                    formattedText = `交易详情:\n卖方: ${sellerName}\n买方: ${buyerName}\n商品: ${t.product_name || '未知'}\n交易次数: ${t.transaction_count || '未知'}\n总价值: ${t.total_value || '未知'}\n平均价格: ${t.avg_price || '未知'}\n步数: ${t.step || '未知'}`;
                  } else if (action.type.startsWith('communication')) {
                    const c = action.content;
                    const speakerId = c.source_company_id;
                    const listenerId = c.company_id;
                    const speakerName = getNameById(speakerId) || speakerId;
                    const listenerName = getNameById(listenerId) || listenerId;
                    formattedText = `通信详情:\n发送方: ${speakerName}\n接收方: ${listenerName}\n操作类型: ${c.operation_type || '未知'}\n消息数量: ${c.message_count || '未知'}\n步数: ${c.step || '未知'}`;

                    // 添加详细通信内容
                    if (c.detail && c.detail.content) {
                      formattedText += `\n\n详细通信内容:`;
                      const content = c.detail.content;
                      if (c.operation_type === 'operation-price') {
                        if (content.expected_products) {
                          formattedText += `\n期望产品: ${content.expected_products}`;
                        }
                        if (content.expected_quantity) {
                          formattedText += `\n期望数量: ${content.expected_quantity}`;
                        }
                        if (content.detailed_inquiry_text) {
                          formattedText += `\n询价详情:\n${content.detailed_inquiry_text}`;
                        }
                      } else if (c.operation_type === 'operation-deal') {
                        if (typeof content === 'object') {
                          Object.keys(content).forEach(key => {
                            if (content[key] !== null && content[key] !== undefined) {
                              formattedText += `\n${key}: ${content[key]}`;
                            }
                          });
                        } else {
                          formattedText += `\n${content}`;
                        }
                      } else {
                        if (typeof content === 'object') {
                          formattedText += `\n${JSON.stringify(content, null, 2)}`;
                        } else {
                          formattedText += `\n${content}`;
                        }
                      }
                    }
                  } else {
                    // 其他类型的行为
                    if (typeof action.content === 'string') {
                      try {
                        const parsedContent = JSON.parse(action.content);
                        formattedText = JSON.stringify(parsedContent, null, 2);
                      } catch {
                        formattedText = action.content;
                      }
                    } else {
                      formattedText = JSON.stringify(action.content, null, 2);
                    }
                  }
                  return formattedText;
                }) :
                selectedFilters.length > 0 ? ['没有匹配筛选条件的内容'] :
                currentThinkingContent.length > 0 ? currentThinkingContent : ['nothing to think'];

              return (
                <div className="thinking-content">
                  {displayContent.map((thinkingText, index) => (
                    <Card
                      key={index}
                      className='thinking-history-card'
                      size="small"
                      bordered={false}
                      style={{ marginBottom: '12px' }}
                    >
                      <div
                        className="thinking-text"
                        style={{
                          background: thinkingText === 'nothing to think' ? '#f5f5f5' : '#f8f9fa',
                          padding: '12px',
                          borderRadius: '6px',
                          marginBottom: '8px',
                          fontSize: '13px',
                          lineHeight: '1.5',
                          border: thinkingText === 'nothing to think' ? '1px solid #d9d9d9' : '1px solid #e9ecef',
                          fontStyle: thinkingText === 'nothing to think' ? 'italic' : 'normal',
                          color: thinkingText === 'nothing to think' ? '#8c8c8c' : 'inherit',
                          /** 加下面两行确保长单词/长字符串自动换行 */
                          wordBreak: 'break-word',
                          whiteSpace: 'pre-wrap'
                        }}
                      >
                        {thinkingText}
                      </div>
                    </Card>
                  ))}
                </div>
              );
            })()}
          </div>
        </div>
      </>
    );
  }

  // 不再使用collapsed类，确保内容始终显示
  const rootClass = "right-inner";

  return (
    <>
      <Flex vertical className={rootClass}>
        <div className="panel-content">
          {!agent && !nodeData && (
            <div style={{ padding: '16px', textAlign: 'center', marginBottom: '16px', background: '#fffbe6', border: '1px solid #ffe58f', borderRadius: '4px' }}>
              <Text strong>请在地图上选择一个节点或Agent以查看详细信息</Text>
            </div>
          )}
          {/* 只显示Company Communications，删除Macro-Planning */}
          {nodeData ? (
            <div>
              <div className="chat-content">
                <div className="content-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <BuildOutlined />
                    <span>Company behavior </span>
                  </div>
                  <div>
                    <Button
                      size="small"
                      icon={<DatabaseOutlined />}
                      onClick={() => setShowRawDataDrawer(true)}
                    >
                      查看原数据
                    </Button>
                  </div>
                </div>
                {renderNodeBehavior()}
              </div>
              {/* <div className="chat-content">
                <div className="content-header">
                  <BuildOutlined />
                  <span>Company Thinking </span>
                </div>
                {renderNodeThinking()}
              </div> */}
            </div>
          ) : (
            <Empty
              description="请在图谱上选择一个节点以查看通信记录"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          )}
        </div>
      </Flex>

      <Modal
        title={
          <div className="survey-preview-header">
            <FormOutlined />
            <span>Survey Preview</span>
          </div>
        }
        open={openPreview}
        onCancel={() => setOpenPreview(false)}
        footer={null}
        width={800}
        className="survey-preview-modal"
      >
        <div className="survey-preview-content">
          <SurveyUI model={model} />
        </div>
      </Modal>

      <Drawer
        title={
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <DatabaseOutlined style={{ marginRight: '8px' }} />
            <span>原始数据查看</span>
          </div>
        }
        open={showRawDataDrawer}
        onClose={() => setShowRawDataDrawer(false)}
        width={1200}
        placement="right"
      >
        <Tabs
          defaultActiveKey="1"
          items={[
            {
              key: '1',
              label: (
                <span>
                  <DatabaseOutlined />
                  数据库数据
                </span>
              ),
              children: (
                <div style={{ maxHeight: '85vh', overflow: 'auto' }}>
                  <div style={{ marginBottom: '16px' }}>
                    <Text strong style={{ fontSize: '14px' }}>完整数据结构预览</Text>
                    <div style={{ marginTop: '8px', color: '#666', fontSize: '12px' }}>
                      公司数据: {apiCompanies.length} 条 | 交易数据: {apiTransactions.length} 条 | 通信数据: {apiCommunications.length} 条
                    </div>
                  </div>
                  <pre style={{
                    background: '#f5f5f5',
                    padding: '16px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    lineHeight: '1.3',
                    border: '1px solid #e8e8e8',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word'
                  }}>
                    {JSON.stringify({
                      companies: apiCompanies,
                      transactions: apiTransactions,
                      communications: apiCommunications,
                      summary: {
                        total_companies: apiCompanies.length,
                        total_transactions: apiTransactions.length,
                        total_communications: apiCommunications.length,
                        data_structure: {
                          companies_fields: apiCompanies.length > 0 ? Object.keys(apiCompanies[0]) : [],
                          transactions_fields: apiTransactions.length > 0 ? Object.keys(apiTransactions[0]) : [],
                          communications_fields: apiCommunications.length > 0 ? Object.keys(apiCommunications[0]) : []
                        }
                      }
                    }, null, 2)}
                  </pre>
                </div>
              ),
            },
            {
              key: '2',
              label: (
                <span>
                  <BarsOutlined />
                  行为类别统计
                </span>
              ),
              children: (
                <div style={{ maxHeight: '85vh', overflow: 'auto' }}>
                  <div style={{ marginBottom: '16px' }}>
                    <Text strong style={{ fontSize: '14px' }}>行为类别统计</Text>
                    <div style={{ marginTop: '8px', color: '#666', fontSize: '12px' }}>
                      当前节点: {nodeId} | 当前步骤: {currentStep} | 行为类别数: {Object.keys(behaviorCategories).length} 种
                    </div>
                  </div>
                  {renderBehaviorCategories()}
                </div>
              ),
            },
            {
              key: '3',
              label: (
                <span>
                  <MessageOutlined />
                  思考内容数据
                </span>
              ),
              children: (
                <div style={{ maxHeight: '85vh', overflow: 'auto' }}>
                  <div style={{ marginBottom: '16px' }}>
                    <Text strong style={{ fontSize: '14px' }}>详细思考内容</Text>
                    <div style={{ marginTop: '8px', color: '#666', fontSize: '12px' }}>
                      当前步骤: {currentStep} | 思考内容条数: {currentThinkingContent.length} 条
                      {nodeData && (
                        <span> | 当前公司: {nodeData.name || nodeData.id}</span>
                      )}
                    </div>
                  </div>
                  {currentThinkingContent.length > 0 ? (
                    <div>
                      {currentThinkingContent.map((thinkingText, index) => (
                        <Card
                          key={index}
                          size="small"
                          style={{ marginBottom: '12px' }}
                          title={`思考内容 ${index + 1}`}
                        >
                          <pre style={{
                            background: '#f8f9fa',
                            padding: '12px',
                            borderRadius: '4px',
                            fontSize: '12px',
                            lineHeight: '1.4',
                            border: '1px solid #e9ecef',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                            margin: 0
                          }}>
                            {thinkingText}
                          </pre>
                        </Card>
                      ))}
                    </div>
                  ) : (
                    <Empty
                      description="当前步骤没有思考内容数据"
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                    />
                  )}

                  <div style={{ marginTop: '24px', borderTop: '1px solid #f0f0f0', paddingTop: '16px' }}>
                    <Text strong style={{ fontSize: '14px' }}>原始对话数据结构</Text>
                    <div style={{ marginTop: '8px', color: '#666', fontSize: '12px' }}>
                      用于调试和查看完整的getAgentDialog接口返回数据
                    </div>
                    <pre style={{
                      background: '#f5f5f5',
                      padding: '16px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      lineHeight: '1.3',
                      border: '1px solid #e8e8e8',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      marginTop: '12px'
                    }}>
                      {JSON.stringify({
                        current_step: currentStep,
                        node_data: nodeData,
                        thinking_content_extracted: currentThinkingContent,
                        all_dialog_list_sample: allDialogList.length > 0 ? {
                          total_companies: allDialogList.length,
                          sample_data: allDialogList[0] ? allDialogList[0].slice(0, 2) : []
                        } : 'No dialog data available'
                      }, null, 2)}
                    </pre>
                  </div>
                </div>
              ),
            },
          ]}
        />
      </Drawer>
    </>
  );
});