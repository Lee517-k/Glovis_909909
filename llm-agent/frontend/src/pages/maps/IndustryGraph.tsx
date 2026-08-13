import React, { useEffect, useRef, useState, useContext } from 'react';
import { Card, Button, Tooltip, Space, message, Typography, Switch, Spin, Modal, List, Tag, Descriptions } from 'antd';
import { ReloadOutlined, FullscreenOutlined, ZoomInOutlined, ZoomOutOutlined, InfoCircleOutlined, DatabaseOutlined } from '@ant-design/icons';
import G6, { Graph } from '@antv/g6';
import { store, StoreContext } from '../Replay/store';
import { Api } from '../../services/api';

const { Title } = Typography;

// 定义产业图谱组件
interface IndustryGraphProps {
  expId?: string;
}

const IndustryGraph: React.FC<IndustryGraphProps> = ({ expId: propExpId }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const [loading, setLoading] = useState(true);
  const storeContext = useContext(StoreContext);

  const [fullscreen, setFullscreen] = useState(false);
  const [data, setData] = useState<any>(null);
  const [filteredData, setFilteredData] = useState<any>(null);
  const [currentStep, setCurrentStep] = useState<number | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [nodeDetailVisible, setNodeDetailVisible] = useState(false);
  const [currentNodeDetail, setCurrentNodeDetail] = useState<any>(null);
  const [nodeDetailLoading, setNodeDetailLoading] = useState(false);
  const [behaviorHighlightEnabled, setBehaviorHighlightEnabled] = useState(false);
  const [highlightedNodes, setHighlightedNodes] = useState<Set<string>>(new Set());
  const [debugMessage, setDebugMessage] = useState<string>('');
  const [edgeDisplayMode, setEdgeDisplayMode] = useState<'all' | 'material_supply' | 'transaction' | 'communication'>('all');

  // 布局模式状态
  const [layoutMode, setLayoutMode] = useState<'hierarchical' | 'force' | 'dagre' | 'grid'>('hierarchical');

  // API数据相关状态
  const [apiData, setApiData] = useState<any>(null);
  const [apiLoading, setApiLoading] = useState(false);
  const [showApiModal, setShowApiModal] = useState(false);
  const [companies, setCompanies] = useState<any[]>([]);
  const [transactions, setTransactions] = useState<any[]>([]);
  const [communications, setCommunications] = useState<any[]>([]);
  // 获取实验ID：优先使用props，然后从URL参数获取，最后默认为'1'
  const getExpIdFromUrl = () => {
    const path = window.location.pathname;
    const match = path.match(/\/replay\/(\d+)/);
    return match ? match[1] : '1';
  };

  const [expId] = useState(propExpId || getExpIdFromUrl());

  // 获取公司层级的辅助函数
  const getCompanyLevel = async (company: any) => {
    if (!expId) {
      // 如果没有expId，回退到使用首字母判断层级
      const firstLetter = company.company_name?.charAt(0)?.toUpperCase();
      if (firstLetter === 'A') return { level: 1, color: 'blue', text: 'Level 1' };
      if (firstLetter === 'B') return { level: 2, color: 'green', text: 'Level 2' };
      return { level: 3, color: 'orange', text: 'Level 3' };
    }

    try {
      const rawId = company.company_id || company.id;
      const levelData = await Api.getAgentLevel(expId, rawId);
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

  // 存储公司层级信息的状态
  const [companyLevels, setCompanyLevels] = useState<Map<string, any>>(new Map());

  // 添加调试信息
  useEffect(() => {
    console.log('IndustryGraph: 初始化，expId =', expId, '来源:', propExpId ? 'props' : 'URL');
  }, [expId, propExpId]);

  // 不再需要渲染节点详情模态框，详情将显示在左侧边栏中
  // 渲染API数据显示弹窗
  const renderApiDataModal = () => {
    return (
      <Modal
        title="数据库数据"
        open={showApiModal}
        onCancel={() => setShowApiModal(false)}
        footer={[
          <Button key="close" onClick={() => setShowApiModal(false)}>
            关闭
          </Button>
        ]}
        width={800}
        style={{ top: 20 }}
      >
        <Spin spinning={apiLoading} tip="加载数据中...">
          {apiData ? (
            <div>
              {/* 公司数据 */}
              {companies && companies.length > 0 && (
                <div style={{ marginBottom: 24 }}>
                  <Title level={5}>公司列表 ({companies.length})</Title>
                  <List
                    size="small"
                    bordered
                    dataSource={companies} // 显示所有公司
                    renderItem={(company: any) => (
                      <List.Item>
                        <Descriptions size="small" column={2}>
                          <Descriptions.Item label="公司名称">{company.company_name}</Descriptions.Item>
                          <Descriptions.Item label="公司ID">{company.company_id}</Descriptions.Item>
                          <Descriptions.Item label="层级">
                            {(() => {
                              const levelInfo = companyLevels.get(company.company_id || company.id);
                              if (levelInfo) {
                                return (
                                  <Tag color={levelInfo.color}>
                                    {levelInfo.text}
                                  </Tag>
                                );
                              }
                              // 如果没有层级信息，显示加载中或使用默认值
                              const firstLetter = company.company_name?.charAt(0)?.toUpperCase();
                              const defaultColor = firstLetter === 'A' ? 'blue' : firstLetter === 'B' ? 'green' : 'orange';
                              const defaultText = firstLetter === 'A' ? 'Level 1' : firstLetter === 'B' ? 'Level 2' : 'Level 3';
                              return (
                                <Tag color={defaultColor}>
                                  {defaultText}
                                </Tag>
                              );
                            })()}
                          </Descriptions.Item>
                          <Descriptions.Item label="状态">{company.status || '正常'}</Descriptions.Item>
                        </Descriptions>
                      </List.Item>
                    )}
                  />

                </div>
              )}

              {/* 交易数据 */}
              {transactions && transactions.length > 0 && (
                <div style={{ marginBottom: 24 }}>
                  <Title level={5}>交易记录 ({transactions.length})</Title>
                  <List
                    size="small"
                    bordered
                    dataSource={transactions.slice(0, 5)} // 只显示前5个
                    renderItem={(transaction: any) => (
                      <List.Item>
                        <Descriptions size="small" column={2}>
                          <Descriptions.Item label="交易ID">{transaction.id}</Descriptions.Item>
                          <Descriptions.Item label="步数">{transaction.step}</Descriptions.Item>
                          <Descriptions.Item label="买方">{transaction.buyer}</Descriptions.Item>
                          <Descriptions.Item label="卖方">{transaction.seller}</Descriptions.Item>
                          <Descriptions.Item label="产品">{transaction.product}</Descriptions.Item>
                          <Descriptions.Item label="数量">{transaction.quantity}</Descriptions.Item>
                        </Descriptions>
                      </List.Item>
                    )}
                  />
                  {transactions.length > 5 && (
                    <div style={{ textAlign: 'center', marginTop: 8, color: '#666' }}>
                      还有 {transactions.length - 5} 条交易记录未显示...
                    </div>
                  )}
                </div>
              )}

              {/* 通信数据 */}
              {communications && communications.length > 0 && (
                <div>
                  <Title level={5}>通信记录 ({communications.length})</Title>
                  <List
                    size="small"
                    bordered
                    dataSource={communications.slice(0, 5)} // 只显示前5个
                    renderItem={(communication: any) => (
                      <List.Item>
                        <Descriptions size="small" column={2}>
                          <Descriptions.Item label="通信ID">{communication.id}</Descriptions.Item>
                          <Descriptions.Item label="步数">{communication.step}</Descriptions.Item>
                          <Descriptions.Item label="发送方">{communication.sender}</Descriptions.Item>
                          <Descriptions.Item label="接收方">{communication.receiver}</Descriptions.Item>
                          <Descriptions.Item label="消息类型">{communication.message_type}</Descriptions.Item>
                          <Descriptions.Item label="内容">
                            <div style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {communication.content}
                            </div>
                          </Descriptions.Item>
                        </Descriptions>
                      </List.Item>
                    )}
                  />
                  {communications.length > 5 && (
                    <div style={{ textAlign: 'center', marginTop: 8, color: '#666' }}>
                      还有 {communications.length - 5} 条通信记录未显示...
                    </div>
                  )}
                </div>
              )}

              {/* 连线数据 */}
              {data && data.edges && data.edges.length > 0 && (
                <div style={{ marginBottom: 24 }}>
                  <Title level={5}>连线数据 ({data.edges.length})</Title>
                  <List
                    size="small"
                    bordered
                    dataSource={data.edges} // 显示所有连线
                    renderItem={(edge: any) => (
                      <List.Item>
                        <Descriptions size="small" column={2}>
                          <Descriptions.Item label="连线ID">{edge.id}</Descriptions.Item>
                          <Descriptions.Item label="类型">
                            <Tag color={edge.type === 'transaction' ? 'blue' : edge.type === 'communication' ? 'green' : edge.type === 'material_supply' ? 'orange' : 'default'}>
                  {edge.type === 'transaction' ? '交易' : edge.type === 'communication' ? '通信' : edge.type === 'material_supply' ? '材料供应' : edge.type}
                </Tag>
                          </Descriptions.Item>
                          <Descriptions.Item label="起点ID">{edge.source}</Descriptions.Item>
                          <Descriptions.Item label="终点ID">{edge.target}</Descriptions.Item>
                          {edge.transaction_data && (
                            <Descriptions.Item label="交易信息">
                              {edge.transaction_data.product || '未知产品'} - {edge.transaction_data.quantity || '未知数量'}
                            </Descriptions.Item>
                          )}
                          {edge.communication_data && (
                            <Descriptions.Item label="消息内容">
                              {edge.communication_data.message_type || '未知类型'}
                            </Descriptions.Item>
                          )}
                          {edge.material_data && (
                            <>
                              <Descriptions.Item label="材料名称">
                                {edge.material_data.material_name || '未知材料'}
                              </Descriptions.Item>
                              <Descriptions.Item label="供应商">
                                {edge.material_data.supplier_company || '未知供应商'}
                              </Descriptions.Item>
                              <Descriptions.Item label="消费者">
                                {edge.material_data.consumer_company || '未知消费者'}
                              </Descriptions.Item>
                              <Descriptions.Item label="产品序号">
                                {edge.material_data.product_index || '未知'}
                              </Descriptions.Item>
                            </>
                          )}
                        </Descriptions>
                      </List.Item>
                    )}
                  />

                </div>
              )}

              {/* 原始数据库数据 */}
              {apiData && (
                <div style={{ marginBottom: 24 }}>
                  <Title level={5}>原始数据库数据</Title>
                  <div style={{
                    backgroundColor: '#f5f5f5',
                    padding: 16,
                    borderRadius: 6,
                    maxHeight: 400,
                    overflow: 'auto',
                    fontFamily: 'monospace',
                    fontSize: 12,
                    lineHeight: 1.4
                  }}>
                    <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                      {JSON.stringify(apiData, null, 2)}
                    </pre>
                  </div>
                </div>
              )}

              {/* 如果没有任何数据 */}
              {(!companies || companies.length === 0) &&
               (!transactions || transactions.length === 0) &&
               (!communications || communications.length === 0) &&
               (!data || !data.edges || data.edges.length === 0) &&
               !apiData && (
                <div style={{ textAlign: 'center', color: '#666', padding: 40 }}>
                  暂无数据
                </div>
              )}
            </div>
          ) : (
            <div style={{ textAlign: 'center', color: '#666', padding: 40 }}>
              {apiLoading ? '正在加载数据...' : '暂无API数据'}
            </div>
          )}
        </Spin>
      </Modal>
    );
  };

  const renderNodeDetailModal = () => {
    return null;
  };



  // 行为高亮功能：根据当前步数和选中节点高亮相关节点标签和连线
  // 新的高亮功能：根据当前步数高亮所有行为对应的连线
  const highlightBehaviorConnectionsByStep = (step: number) => {
    console.log('highlightBehaviorConnectionsByStep 被调用:', { step });

    // 清除之前的调试信息
    setDebugMessage('');

    if (!behaviorHighlightEnabled) {
      console.log('行为高亮未启用');
      return;
    }

    if (!graphRef.current) {
      console.log('图谱引用不存在');
      return;
    }

    const graph = graphRef.current;
    const edges = graph.getEdges();

    if (!edges || edges.length === 0) {
      console.log('没有边数据');
      return;
    }

    let highlightedEdgeCount = 0;

    console.log('根据步数高亮连线:', step);

    // 重置所有边的样式
    edges.forEach(edge => {
      graph.updateItem(edge, {
        style: {
          stroke: '#aaa',
          lineWidth: 1
        }
      });
    });

    // 如果当前连线显示模式是交易或通信，则高亮对应的边
    if (edgeDisplayMode === 'transaction' || edgeDisplayMode === 'communication') {
      edges.forEach(edge => {
        const edgeModel = edge.getModel();
        let shouldHighlight = false;

        // 检查交易边 - 使用新的steps数组
        if (edgeDisplayMode === 'transaction' && edgeModel.type === 'transaction') {
          console.log('检查交易边:', edgeModel.id, '步数数组:', edgeModel.steps, '当前步数:', step);
          // 检查steps数组中是否包含当前步数
          if (edgeModel.steps && Array.isArray(edgeModel.steps) && edgeModel.steps.includes(step)) {
            shouldHighlight = true;
            console.log('✅ 交易边匹配步数:', edgeModel.id);
          }
          // 兼容旧格式
          else if (edgeModel.transaction_data && edgeModel.transaction_data.step === step) {
            shouldHighlight = true;
            console.log('✅ 交易边匹配步数(旧格式):', edgeModel.id);
          }
        }

        // 检查通信边 - 使用新的steps数组
        if (edgeDisplayMode === 'communication' && edgeModel.type === 'communication') {
          console.log('检查通信边:', edgeModel.id, '步数数组:', edgeModel.steps, '当前步数:', step);
          // 检查steps数组中是否包含当前步数
          if (edgeModel.steps && Array.isArray(edgeModel.steps) && edgeModel.steps.includes(step)) {
            shouldHighlight = true;
            console.log('✅ 通信边匹配步数:', edgeModel.id);
          }
          // 兼容旧格式
          else if (edgeModel.communication_data && edgeModel.communication_data.step === step) {
            shouldHighlight = true;
            console.log('✅ 通信边匹配步数(旧格式):', edgeModel.id);
          }
        }

        if (shouldHighlight) {
          graph.updateItem(edge, {
            style: {
              stroke: '#722ed1', // 紫色连线
              lineWidth: 3
            }
          });
          // edge.toFront(); // 移除toFront调用，避免图谱位置重置
          highlightedEdgeCount++;
          console.log('高亮边:', edgeModel.id, '类型:', edgeModel.type, '步数:', edgeModel.transaction_data?.step || edgeModel.communication_data?.step);
        }
      });
    }

    // 使用轻量级重绘替代强制刷新，避免重影
    graph.paint();

    // 显示调试信息
    setDebugMessage(`行为高亮功能已激活！当前步数: ${step} 连线显示模式: ${edgeDisplayMode} 高亮连线数量: ${highlightedEdgeCount}`);
  };

  // 保留原有的基于节点的高亮功能（用于兼容性）
  const highlightBehaviorConnections = (nodeId: string, step: number) => {
     console.log('highlightBehaviorConnections 被调用:', { nodeId, step });

     // 清除之前的调试信息
     setDebugMessage('');

     console.log('highlightBehaviorConnections called:', { nodeId, step, behaviorHighlightEnabled, hasGraph: !!graphRef.current });

    if (!behaviorHighlightEnabled) {
      console.log('行为高亮未启用');
      return;
    }

    if (!graphRef.current) {
      console.log('图谱引用不存在');
      return;
    }

    const graph = graphRef.current;
    const nodes = graph.getNodes();
    const edges = graph.getEdges();

    if (!nodes || nodes.length === 0 || !edges || edges.length === 0) {
      console.log('没有节点或边数据');
      return;
    }

    const newHighlightedNodes = new Set<string>();

    console.log('查找节点:', nodeId, '步数:', step);

    // 重置所有节点的标签样式
    nodes.forEach(node => {
      node.update({
        labelCfg: {
          style: {
            fill: '#333',
            fontSize: 12,
            fontWeight: 600,
            stroke: '#ffffff',
            lineWidth: 0.3,
          }
        }
      });
    });

    // 重置所有边的样式
    edges.forEach(edge => {
      graph.updateItem(edge, {
        style: {
          stroke: '#aaa',
          lineWidth: 1
        }
      });
    });

    // 从 store 获取本地数据，与 InfoPanel 保持一致
    const localData = store._localData;
    if (!localData || !Array.isArray(localData) || localData.length === 0) {
      console.log('没有可用的本地数据');
      setDebugMessage(`行为高亮调试信息: 当前步数: ${step} 选中节点: ${nodeId} 结果: 没有可用的本地数据 请确保数据已加载`);
      return;
    }

    // 查找当前步骤的数据
    // 注意：图谱中节点ID是company_name，需要通过company_name或id匹配
    const stepData = localData.find(item =>
      item.step === step &&
      (item.company_name === nodeId || item.id.toString() === nodeId.toString())
    );

    if (!stepData) {
      // 未找到当前步骤的数据
      const availableNodes = localData.filter(item => item.step === step).map(item => item.company_name).join(', ');
      setDebugMessage(`行为高亮调试信息: 当前步数: ${step} 选中节点: ${nodeId} 结果: 未找到当前步骤的数据 可用节点: ${availableNodes}`);
      return;
    }

    // 找到步骤数据

    // 统计行为数据
    const transactionCount = stepData.transaction_list ? stepData.transaction_list.length : 0;
    const recordCount = stepData.record ? stepData.record.length : 0;

    // 如果没有任何行为数据，显示提示
    if (transactionCount === 0 && recordCount === 0) {
      setDebugMessage(`行为高亮调试信息: 当前步数: ${step} 选中节点: ${nodeId} 结果: 当前步骤没有行为数据 交易数量: ${transactionCount} 消息数量: ${recordCount}`);
      return;
    }

    // 处理交易行为
    if (stepData.transaction_list && stepData.transaction_list.length > 0) {
      stepData.transaction_list.forEach((transaction) => {
        const { Purchaser: purchaser, Supplier: supplier, product_name } = transaction;
        const currentNodeId = stepData.id; // 当前节点的数字ID
        if (purchaser === currentNodeId || supplier === currentNodeId) {
          const otherPartyId = purchaser === currentNodeId ? supplier : purchaser;
          // 需要将数字ID转换为company_name来查找图谱节点
          const otherPartyData = localData.find(item => item.id === otherPartyId);
          const otherParty = otherPartyData ? otherPartyData.company_name : otherPartyId.toString();
          console.log('找到交易行为，对方节点ID:', otherPartyId, '对方节点名:', otherParty);

          // 查找对方节点并高亮
          const targetNode = graph.findById(otherParty);
          if (targetNode) {
            targetNode.update({
              labelCfg: {
                style: {
                  fill: '#722ed1', // 紫色标签
                  fontSize: 14,
                  fontWeight: 700,
                  stroke: '#ffffff',
                  lineWidth: 0.5,
                }
              }
            });

            newHighlightedNodes.add(otherParty);

            // 高亮连线
            const sourceNode = graph.findById(nodeId);
            if (sourceNode) {
              edges.forEach(edge => {
                const edgeModel = edge.getModel();
                if ((edgeModel.source === nodeId && edgeModel.target === otherParty) ||
                    (edgeModel.source === otherParty && edgeModel.target === nodeId)) {
                  graph.updateItem(edge, {
                    style: {
                      stroke: '#722ed1', // 紫色连线
                      lineWidth: 3
                    }
                  });
                   // edge.toFront(); // 移除toFront调用，避免图谱位置重置
                   console.log('成功高亮交易连线:', nodeId, '<->', otherParty);
                }
              });
            }
          } else {
            console.log('未找到目标节点:', otherParty, '(转换自ID:', otherPartyId, ')');
          }
        }
      });
    }

    // 处理消息行为
    if (stepData.record && stepData.record.length > 0) {
      stepData.record.forEach((record) => {
        const otherPartyId = record.source || record.content?.from;
        const currentNodeId = stepData.id; // 当前节点的数字ID
        if (otherPartyId && otherPartyId !== currentNodeId) {
          // 需要将数字ID转换为company_name来查找图谱节点
          const otherPartyData = localData.find(item => item.id === otherPartyId);
          const otherParty = otherPartyData ? otherPartyData.company_name : otherPartyId.toString();
          console.log('找到消息行为，对方节点ID:', otherPartyId, '对方节点名:', otherParty);

          // 查找对方节点并高亮
           const targetNode = graph.findById(otherParty);
           if (targetNode) {
             targetNode.update({
               labelCfg: {
                 style: {
                   fill: '#722ed1', // 紫色标签
                   fontSize: 14,
                   fontWeight: 700,
                   stroke: '#ffffff',
                   lineWidth: 0.5,
                 }
               }
             });

             newHighlightedNodes.add(otherParty);

             // 高亮连线
             const sourceNode = graph.findById(nodeId);
             if (sourceNode) {
               edges.forEach(edge => {
                 const edgeModel = edge.getModel();
                 if ((edgeModel.source === nodeId && edgeModel.target === otherParty) ||
                     (edgeModel.source === otherParty && edgeModel.target === nodeId)) {
                   graph.updateItem(edge, {
                     style: {
                       stroke: '#722ed1', // 紫色连线
                       lineWidth: 3
                     }
                   });
                   // edge.toFront(); // 移除toFront调用，避免图谱位置重置
                   console.log('成功高亮消息连线:', nodeId, '<->', otherParty);
                 }
               });
             }
           } else {
             console.log('未找到目标节点:', otherParty, '(转换自ID:', otherPartyId, ')');
           }
        }
      });
    }

    // 使用轻量级重绘替代强制刷新，避免重影
    graph.paint();

    console.log('高亮的节点集合:', newHighlightedNodes);
    setHighlightedNodes(newHighlightedNodes);

    // 显示调试信息
    if (newHighlightedNodes.size > 0) {
      const nodeList = Array.from(newHighlightedNodes).join(', ');
      setDebugMessage(`行为高亮功能已激活！当前步数: ${step} 选中节点: ${nodeId} 高亮节点: ${nodeList} 紫色连线已显示`);
      console.log('✅ 成功高亮节点和连线:', Array.from(newHighlightedNodes));
    } else {
      setDebugMessage(`行为高亮调试信息: 当前步数: ${step} 选中节点: ${nodeId} 结果: 未找到需要高亮的节点`);
      // 当前步骤没有行为数据
    }

    console.log('最终高亮的节点:', Array.from(newHighlightedNodes));
  };

  // 清除行为高亮
  const clearBehaviorHighlight = () => {
    if (!graphRef.current) return;

    const graph = graphRef.current;
    const nodes = graph.getNodes();
    const edges = graph.getEdges();

    // 重置所有节点的标签样式
    nodes.forEach(node => {
      node.update({
        labelCfg: {
          style: {
            fill: '#333',
            fontSize: 18,
            fontWeight: 600,
            stroke: '#ffffff',
            lineWidth: 0.3,
          }
        }
      });
    });

    // 重置所有边的样式
    edges.forEach(edge => {
      graph.updateItem(edge, {
        style: {
          stroke: '#aaa',
          lineWidth: 1
        }
      });
    });

    // 使用轻量级重绘替代强制刷新，避免重影
    graph.paint();

    setHighlightedNodes(new Set());
  };

  // 获取节点详情的函数，现在只负责触发nodeSelected事件
  const fetchNodeDetail = async (nodeId: string) => {
    if (!nodeId) {
      message.info('请先选择一个节点');
      return;
    }

    setNodeDetailLoading(true);
    try {
      // 尝试多个可能的路径
      let response;
      try {
        response = await fetch('/neo4j/industry_test_small.json');
        if (!response.ok) throw new Error('Path not found');
      } catch (e) {
        console.log('Trying alternative path...');
        response = await fetch('./neo4j/industry_test_small.json');
        if (!response.ok) throw new Error('Alternative path not found');
      }

      const rawData = await response.json();

      // 查找节点详细信息
      let nodeDetail = null;
      Object.keys(rawData).forEach(level => {
        rawData[level].forEach((company: any) => {
          if (company.name === nodeId) {
            nodeDetail = { ...company, level };
          }
        });
      });

      if (nodeDetail) {
        // 不再显示模态框，而是触发事件传递数据到左侧边栏
        setCurrentNodeDetail(nodeDetail);

        // 触发自定义事件，通知其他组件节点被选中
        // 查找节点的完整数据
        let nodeData = null;
        if (data && data.stateData) {
          // 如果是state_*.json格式的数据
          nodeData = data.stateData.filter((item: any) => item.company_name === nodeId || item.id === nodeId);
          // 触发nodeSelected事件
          const event = new CustomEvent('nodeSelected', {
            detail: { nodeId, nodeData }
          });
          console.log('IndustryGraph: Dispatching nodeSelected event (fetchNodeDetail - state data):', { nodeId, nodeData });
          window.dispatchEvent(event);
        } else {
          // 如果是原有格式的数据
          const event = new CustomEvent('nodeSelected', {
            detail: { nodeId, nodeData: nodeDetail }
          });
          console.log('IndustryGraph: Dispatching nodeSelected event (fetchNodeDetail - industry data):', { nodeId, nodeData: nodeDetail });
          window.dispatchEvent(event);
        }
      } else {
        message.info('未找到该节点的详细信息');
      }
    } catch (error) {
      console.error('Error fetching node details:', error);
    } finally {
      setNodeDetailLoading(false);
    }
  };

  // 加载API数据
  const loadApiData = async () => {
    setApiLoading(true);
    try {
      console.log('IndustryGraph: 开始加载API数据，expId =', expId);

      // 并行获取所有API数据，使用getAllAgent获取包含params的完整agent档案
      const [agentProfilesData, transactionsData, communicationsResponse] = await Promise.all([
        Api.getAllAgent(expId).catch(e => { console.error('IndustryGraph: 获取agent档案数据失败:', e); return []; }),
        Api.getTransaction(expId).catch(e => { console.error('IndustryGraph: 获取交易数据失败:', e); return []; }),
        Api.getCommunications(expId, true).catch(e => { console.error('IndustryGraph: 获取通信数据失败:', e); return {}; }) // 传递include_details=true获取包装格式
      ]);

      // 从包装格式中提取实际的通信数据
      const communicationsData = communicationsResponse?.communications || communicationsResponse || [];

      // 从agent档案中提取公司信息，包含params字段
      const companiesData = (agentProfilesData || []).map(agent => ({
        ...agent.profile, // 包含params字段和其他profile信息
        company_id: agent.id,
        company_name: agent.name,
        agent_id: agent.id,
        agent_name: agent.name
      }));

      // 获取所有agent的材料供应关系数据
      const materialSupplyData = {};
      for (const agent of agentProfilesData || []) {
        try {
          const [requiredMaterials, availableMaterials] = await Promise.all([
            Api.getAgentRequiredMaterials(expId, agent.id).catch(e => { console.error(`获取agent ${agent.id} 所需材料失败:`, e); return null; }),
            Api.getAgentAvailableMaterials(expId, agent.id).catch(e => { console.error(`获取agent ${agent.id} 可提供材料失败:`, e); return null; })
          ]);

          materialSupplyData[agent.id] = {
            required: requiredMaterials,
            available: availableMaterials
          };
        } catch (error) {
          console.error(`获取agent ${agent.id} 材料数据失败:`, error);
        }
      }

      console.log('IndustryGraph: API原始数据:', {
        agentProfiles: agentProfilesData,
        companies: companiesData,
        transactions: transactionsData,
        communications: communicationsData,
        materialSupply: materialSupplyData
      });

      console.log('IndustryGraph: 公司数据示例（包含params）:', companiesData.slice(0, 2));
      console.log('IndustryGraph: 材料供应数据示例:', Object.values(materialSupplyData).slice(0, 2));

      setCompanies(companiesData);
      setTransactions(transactionsData);
      setCommunications(communicationsData);

      // 获取所有公司的层级信息
      const levelMap = new Map();
      for (const company of companiesData) {
        try {
          const levelInfo = await getCompanyLevel(company);
          levelMap.set(company.company_id || company.id, levelInfo);
        } catch (error) {
          console.error(`获取公司 ${company.company_name} 层级失败:`, error);
          // 使用默认层级信息
          const firstLetter = company.company_name?.charAt(0)?.toUpperCase();
          const defaultLevelInfo = {
            level: firstLetter === 'A' ? 1 : firstLetter === 'B' ? 2 : 3,
            color: firstLetter === 'A' ? 'blue' : firstLetter === 'B' ? 'green' : 'orange',
            text: firstLetter === 'A' ? 'Level 1' : firstLetter === 'B' ? 'Level 2' : 'Level 3'
          };
          levelMap.set(company.company_id || company.id, defaultLevelInfo);
        }
      }
      setCompanyLevels(levelMap);

      // 合并API数据
      const combinedApiData = {
        companies: companiesData,
        transactions: transactionsData,
        communications: communicationsData,
        materialSupply: materialSupplyData,
        raw_communications_response: communicationsResponse // 保留原始响应用于调试
      };
      setApiData(combinedApiData);

      // 将API数据存储到store中，供其他组件使用
      storeContext.setApiData(combinedApiData);

      console.log('IndustryGraph: API数据加载完成:', {
        companies: companiesData.length,
        transactions: transactionsData.length,
        communications: communicationsData.length,
        materialSupplyAgents: Object.keys(materialSupplyData).length
      });

      message.success('API数据加载成功');
      return combinedApiData; // 返回加载的数据
    } catch (error) {
      console.error('IndustryGraph: API数据加载失败:', error);
      message.error('API数据加载失败，将使用本地数据');
      return null; // 加载失败返回null
    } finally {
      setApiLoading(false);
    }
  };

  // 加载数据
  useEffect(() => {
    setLoading(true);

    // 先加载API数据，然后根据结果决定是否使用本地数据
    const loadAllData = async () => {
      try {
        // 首先尝试加载API数据
        const loadedApiData = await loadApiData();

        // 检查API数据是否成功加载
        if (loadedApiData && loadedApiData.companies && loadedApiData.companies.length > 0) {
          const apiGraphData = await processApiData(loadedApiData);
          setData(apiGraphData);
          message.success('使用API数据构建图谱成功');
          setLoading(false);
          return;
        }

        // 如果API数据不可用，加载本地数据作为备用
        await loadLocalData();
      } catch (error) {
        console.error('数据加载异常:', error);
        await loadLocalData();
      }
    };

    const loadLocalData = async () => {
      try {
        // 尝试多个可能的路径
        let response;
        let stateData = null;
        let industryData = null;
        let loadedFrom = '';

        // 首先尝试加载state_*.json格式的数据
        const statePaths = [
          '/state_latest.json',
          './state_latest.json',
          '../state_latest.json',
          '../../state_latest.json',
          '/public/state_latest.json',
          './public/state_latest.json'
        ];

        for (const path of statePaths) {
          try {
            console.log(`尝试从 ${path} 加载数据...`);
            response = await fetch(path);
            if (response.ok) {
              stateData = await response.json();
              console.log(`成功从 ${path} 加载state数据`);
              loadedFrom = path;
              break;
            }
          } catch (e) {
            console.log(`从 ${path} 加载失败: ${e.message}`);
          }
        }

        // 使用state数据
        if (stateData) {
          // 处理数据
          const processedData = await processIndustryData(stateData);
          processedData.stateData = stateData;
          setData(processedData);
          message.success(`成功从 ${loadedFrom} 加载本地数据`);
          setLoading(false);
          return;
        }

        // 如果state数据加载失败，尝试加载产业数据
        const industryPaths = [
          '/neo4j/industry_test_small.json',
          './neo4j/industry_test_small.json',
          '../neo4j/industry_test_small.json',
          '../../neo4j/industry_test_small.json',
          '/public/neo4j/industry_test_small.json',
          './public/neo4j/industry_test_small.json'
        ];

        for (const path of industryPaths) {
          try {
            console.log(`尝试从 ${path} 加载产业数据...`);
            response = await fetch(path);
            if (response.ok) {
              industryData = await response.json();
              console.log(`成功从 ${path} 加载产业数据`);
              loadedFrom = path;
              break;
            }
          } catch (e) {
            console.log(`从 ${path} 加载失败: ${e.message}`);
          }
        }

        if (industryData) {
          // 处理数据
          const processedData = await processIndustryData(industryData);
          setData(processedData);
          message.success(`成功从 ${loadedFrom} 加载产业数据`);
          setLoading(false);
          return;
        }

        // 如果所有路径都加载失败，显示错误
        throw new Error('所有数据加载路径都失败');
      } catch (error) {
        console.error('Error loading industry data:', error);
        message.error(`加载数据失败: ${error.message}，请检查控制台获取详细信息`);
        setLoading(false);
      }
    };

    loadAllData();
  }, []);

  // 处理API数据，转换为G6可用的格式
  const processApiData = async (apiData: any) => {
    const nodes: any[] = [];
    const edges: any[] = [];
    const nodeMap = new Map();
    const edgeMap = new Map();
    const companyIdMap = new Map(); // 公司名称/ID到数字ID的映射
    const levelCounts = {
      level_1: 0,
      level_2: 0,
      level_3: 0
    };

    console.log('处理API数据:', apiData);

    // 处理公司数据创建节点
    if (apiData.companies && apiData.companies.length > 0) {
      const processCompany = async (company: any, index: number) => {
        // 确保节点ID是字符串类型（G6要求）
        const rawId = company.company_id || company.id || (index + 1);
        const nodeId = String(rawId); // 转换为字符串
        const label = company.company_name || company.name || `Company_${nodeId}`;
        const companyName = company.company_name || company.name;

        console.log('处理公司节点:', { rawId, nodeId, label, company });

        if (!nodeMap.has(nodeId)) {
          // 使用API获取节点层级
          let level = 'level_1'; // 默认层级

          // 如果有expId，则调用API获取层级
          if (expId) {
            try {
              const levelData = await Api.getAgentLevel(expId, rawId);
              if (levelData && levelData.level) {
                level = `level_${levelData.level}`;
                console.log(`从API获取节点 ${nodeId} 的层级: ${level}`);
              }
            } catch (error) {
              console.error(`获取节点 ${nodeId} 层级失败:`, error);
              // 如果API调用失败，回退到使用首字母判断层级
              const firstLetter = label.charAt(0).toUpperCase();
              if (firstLetter >= 'A' && firstLetter <= 'Z') {
                const levelIndex = firstLetter.charCodeAt(0) - 64; // A=1, B=2, C=3...
                level = `level_${levelIndex}`;
                console.log(`使用首字母判断节点 ${nodeId} 的层级: ${level}`);
              }
            }
          } else {
            // 如果没有expId，回退到使用首字母判断层级
            const firstLetter = label.charAt(0).toUpperCase();
            if (firstLetter >= 'A' && firstLetter <= 'Z') {
              const levelIndex = firstLetter.charCodeAt(0) - 64; // A=1, B=2, C=3...
              level = `level_${levelIndex}`;
              console.log(`使用首字母判断节点 ${nodeId} 的层级: ${level}`);
            }
          }

          nodes.push({
            id: nodeId, // 现在是字符串类型
            label: label,
            type: 'company',
            level: level,
            size: 30,
            company_data: company,
            colIndex: index
          });
          nodeMap.set(nodeId, true);
          levelCounts[level]++;

          // 建立映射关系：公司名称和各种ID都映射到字符串节点ID
          if (companyName) companyIdMap.set(companyName, nodeId);
          if (company.company_id) companyIdMap.set(String(company.company_id), nodeId);
          if (company.id) companyIdMap.set(String(company.id), nodeId);
          // 同时映射原始数字ID
          companyIdMap.set(rawId, nodeId);
        }
      };

      // 处理所有公司
      for (let index = 0; index < apiData.companies.length; index++) {
        await processCompany(apiData.companies[index], index);
      }
    }

    // 使用新的材料供应接口数据创建供应链边
    if (apiData.materialSupply && Object.keys(apiData.materialSupply).length > 0) {
      console.log('开始使用新接口数据创建供应链边');

      // 用于收集同一对公司之间的所有原料关系
      const companyPairMaterials = new Map();

      // 遍历所有agent的材料需求
      Object.keys(apiData.materialSupply).forEach(agentId => {
        const agentMaterialData = apiData.materialSupply[agentId];
        const requiredMaterials = agentMaterialData.required;

        if (!requiredMaterials || !requiredMaterials.required_materials) {
          return;
        }

        const consumerAgentId = String(agentId);
        const consumerNodeId = companyIdMap.get(consumerAgentId) || consumerAgentId;
        const consumerCompanyName = requiredMaterials.agent_name;

        console.log(`处理Agent ${agentId} (${consumerCompanyName}) 的材料需求:`, requiredMaterials.required_materials);

        // 遍历该agent需要的每种材料
        requiredMaterials.required_materials.forEach(requiredMaterial => {
          const materialId = requiredMaterial.material_id;
          const materialName = requiredMaterial.material_name;

          console.log(`查找能提供材料 ${materialName} (ID: ${materialId}) 的供应商`);

          // 在所有其他agent中查找能提供这种材料的供应商
          Object.keys(apiData.materialSupply).forEach(supplierAgentId => {
            if (supplierAgentId === agentId) return; // 跳过自己

            const supplierMaterialData = apiData.materialSupply[supplierAgentId];
            const availableMaterials = supplierMaterialData.available;

            if (!availableMaterials || !availableMaterials.available_materials) {
              return;
            }

            // 检查该供应商是否能提供所需材料
            const canSupply = availableMaterials.available_materials.find(availableMaterial =>
              availableMaterial.material_id === materialId &&
              availableMaterial.can_supply &&
              availableMaterial.available_quantity > 0
            );

            if (canSupply) {
              const supplierNodeId = companyIdMap.get(String(supplierAgentId)) || String(supplierAgentId);
              const supplierCompanyName = availableMaterials.agent_name;

              console.log(`发现供应关系: ${supplierCompanyName} -> ${consumerCompanyName} (${materialName})`);

              // 收集同一对公司之间的原料关系
              const pairKey = `${supplierNodeId}-${consumerNodeId}`;

              if (!companyPairMaterials.has(pairKey)) {
                companyPairMaterials.set(pairKey, {
                  source: String(supplierNodeId),
                  target: String(consumerNodeId),
                  supplier_company: supplierCompanyName,
                  consumer_company: consumerCompanyName,
                  supplier_agent_id: supplierAgentId,
                  consumer_agent_id: agentId,
                  materials: []
                });
              }

              const pairData = companyPairMaterials.get(pairKey);
              if (!pairData.materials.some(m => m.material_id === materialId)) {
                pairData.materials.push({
                  material_id: materialId,
                  material_name: materialName,
                  available_quantity: canSupply.available_quantity,
                  required_quantity: requiredMaterial.current_quantity
                });
              }
            }
          });
        });
      });

      // 为每对公司创建一条边，包含所有原料信息
      companyPairMaterials.forEach((pairData, pairKey) => {
        const edgeId = `${pairData.source}-${pairData.target}-materials`;

        if (!edgeMap.has(edgeId)) {
          edges.push({
            source: pairData.source,
            target: pairData.target,
            id: edgeId,
            type: 'material_supply',
            material_data: {
              material_names: pairData.materials.map(m => m.material_name), // 材料名称数组
              materials_detail: pairData.materials, // 详细材料信息
              supplier_company: pairData.supplier_company,
              consumer_company: pairData.consumer_company,
              supplier_agent_id: pairData.supplier_agent_id,
              consumer_agent_id: pairData.consumer_agent_id
            },
            size: 2,
            style: {
              stroke: '#FF9800',
              lineWidth: 2
            }
          });
          edgeMap.set(edgeId, true);
          console.log(`创建材料供应边: ${pairData.supplier_company} -> ${pairData.consumer_company} (${pairData.materials.map(m => m.material_name).join(', ')})`);
        }
      });
    }

    // 处理交易数据创建边 - 使用新的数据源和step序列逻辑
    if (apiData.transactions && apiData.transactions.length > 0) {
      console.log('开始处理交易数据，数量:', apiData.transactions.length);

      // 用于收集同一对公司之间的所有交易，按边分组
      const transactionEdgeMap = new Map();

      apiData.transactions.forEach((transaction: any) => {
        // API返回字段：step, purchaser_id, supplier_id, product_name, transaction_count, total_value, avg_price
        const sourceKey = transaction.supplier_id;
        const targetKey = transaction.purchaser_id;
        const step = transaction.step;

        // 通过映射获取实际的字符串节点ID
        const sourceId = companyIdMap.get(sourceKey) || companyIdMap.get(String(sourceKey)) || String(sourceKey);
        const targetId = companyIdMap.get(targetKey) || companyIdMap.get(String(targetKey)) || String(targetKey);

        if (sourceId && targetId && sourceId !== targetId) {
          const edgeKey = `${sourceId}-${targetId}-transaction`;

          if (!transactionEdgeMap.has(edgeKey)) {
            transactionEdgeMap.set(edgeKey, {
              source: String(sourceId),
              target: String(targetId),
              id: edgeKey,
              type: 'transaction',
              steps: new Set(), // 使用Set避免重复步数
              transactions: [], // 存储所有相关交易数据
              size: 1
            });
          }

          const edgeData = transactionEdgeMap.get(edgeKey);
          edgeData.steps.add(step); // 添加步数到集合
          edgeData.transactions.push(transaction); // 添加交易数据
        }
      });

      // 将收集的边数据转换为最终格式
      transactionEdgeMap.forEach((edgeData) => {
        const finalEdge = {
          source: edgeData.source,
          target: edgeData.target,
          id: edgeData.id,
          type: 'transaction',
          steps: Array.from(edgeData.steps).sort((a, b) => a - b), // 转换为排序数组
          transaction_data: {
            all_transactions: edgeData.transactions,
            step_count: edgeData.steps.size,
            total_transaction_count: edgeData.transactions.reduce((sum, t) => sum + (t.transaction_count || 0), 0),
            total_value: edgeData.transactions.reduce((sum, t) => sum + (t.total_value || 0), 0)
          },
          size: Math.min(edgeData.steps.size, 5) // 根据出现步数调整边的粗细，最大为5
        };

        edges.push(finalEdge);
        edgeMap.set(edgeData.id, true);

        console.log(`创建交易边: ${edgeData.source} -> ${edgeData.target}, 出现步数: [${finalEdge.steps.join(', ')}], 交易次数: ${finalEdge.transaction_data.total_transaction_count}`);
      });
    }

    // 处理通信数据创建边 - 使用新的数据源和step序列逻辑
    if (apiData.communications && apiData.communications.length > 0) {
      console.log('开始处理通信数据，数量:', apiData.communications.length);

      // 用于收集同一对公司之间的所有通信，按边分组
      const communicationEdgeMap = new Map();

      apiData.communications.forEach((communication: any) => {
        // API返回字段：step, company_id, source_company_id, operation_type, message_count
        const sourceKey = communication.source_company_id;
        const targetKey = communication.company_id;
        const step = communication.step;

        // 通过映射获取实际的字符串节点ID
        const sourceId = companyIdMap.get(sourceKey) || companyIdMap.get(String(sourceKey)) || String(sourceKey);
        const targetId = companyIdMap.get(targetKey) || companyIdMap.get(String(targetKey)) || String(targetKey);

        if (sourceId && targetId && sourceId !== targetId) {
          const edgeKey = `${sourceId}-${targetId}-communication`;

          if (!communicationEdgeMap.has(edgeKey)) {
            communicationEdgeMap.set(edgeKey, {
              source: String(sourceId),
              target: String(targetId),
              id: edgeKey,
              type: 'communication',
              steps: new Set(), // 使用Set避免重复步数
              communications: [], // 存储所有相关通信数据
              size: 1
            });
          }

          const edgeData = communicationEdgeMap.get(edgeKey);
          edgeData.steps.add(step); // 添加步数到集合
          edgeData.communications.push(communication); // 添加通信数据
        }
      });

      // 将收集的边数据转换为最终格式
      communicationEdgeMap.forEach((edgeData) => {
        const finalEdge = {
          source: edgeData.source,
          target: edgeData.target,
          id: edgeData.id,
          type: 'communication',
          steps: Array.from(edgeData.steps).sort((a, b) => a - b), // 转换为排序数组
          communication_data: {
            all_communications: edgeData.communications,
            step_count: edgeData.steps.size,
            total_message_count: edgeData.communications.reduce((sum, c) => sum + (c.message_count || 0), 0),
            operation_types: [...new Set(edgeData.communications.map(c => c.operation_type).filter(Boolean))]
          },
          size: Math.min(edgeData.steps.size, 5) // 根据出现步数调整边的粗细，最大为5
        };

        edges.push(finalEdge);
        edgeMap.set(edgeData.id, true);

        console.log(`创建通信边: ${edgeData.source} -> ${edgeData.target}, 出现步数: [${finalEdge.steps.join(', ')}], 消息次数: ${finalEdge.communication_data.total_message_count}`);
      });
    }

    // 位置计算已移至数据处理阶段，根据布局模式动态处理

    console.log('产业数据处理完成:', {
      nodes: nodes.length,
      edges: edges.length,
      nodesSample: nodes.slice(0, 3),
      edgesSample: edges.slice(0, 3),
      levelCounts: levelCounts,
      allNodeIds: nodes.map(n => n.id)
    });

    return { nodes, edges, apiData: false };
  };

  // 处理产业数据，转换为G6可用的格式
  const processIndustryData = async (industryData: any) => {
    console.log('开始处理产业数据:', industryData);
    const nodes: any[] = [];
    const edges: any[] = [];
    const nodeMap = new Map(); // 用于快速查找节点
    const edgeMap = new Map(); // 用于避免重复边
    const levelCounts = { // 用于统计每个层级的节点数量
      level_1: 0,
      level_2: 0,
      level_3: 0
    };

    // 检查是否是state_*.json格式的数据（包含step字段的数组）
    if (Array.isArray(industryData) && industryData.length > 0 && 'step' in industryData[0]) {
      // 处理包含step字段的数据
      const stepData = industryData;

      // 为每个step中的公司创建节点
      for (const item of stepData) {
        const company = item;
        const nodeId = company.id || company.company_id;
        const label = company.company_name || nodeId;

        if (!nodeMap.has(nodeId)) {
          // 使用API获取节点层级
          let level = 'level_1'; // 默认层级

          // 如果有expId，则调用API获取层级
          if (expId) {
            try {
              const levelData = await Api.getAgentLevel(expId, nodeId);
              if (levelData && levelData.level) {
                level = `level_${levelData.level}`;
                console.log(`从API获取节点 ${nodeId} 的层级: ${level}`);
              }
            } catch (error) {
              console.error(`获取节点 ${nodeId} 层级失败:`, error);
              // 如果API调用失败，回退到使用首字母判断层级
              const firstLetter = label.charAt(0).toUpperCase();
              if (firstLetter >= 'A' && firstLetter <= 'Z') {
                const levelIndex = firstLetter.charCodeAt(0) - 64; // A=1, B=2, C=3...
                level = `level_${levelIndex}`;
                console.log(`使用首字母判断节点 ${nodeId} 的层级: ${level}`);
              }
            }
          } else {
            // 如果没有expId，回退到使用首字母判断层级
            const firstLetter = label.charAt(0).toUpperCase();
            if (firstLetter >= 'A' && firstLetter <= 'Z') {
              const levelIndex = firstLetter.charCodeAt(0) - 64; // A=1, B=2, C=3...
              level = `level_${levelIndex}`;
              console.log(`使用首字母判断节点 ${nodeId} 的层级: ${level}`);
            }
          }

          nodes.push({
            id: nodeId,
            label: label,
            type: 'company',
            level: level,
            size: 30,
            step: company.step, // 添加step字段
            company_data: company, // 保存完整的公司数据
            colIndex: nodes.length // 使用节点数量作为列索引
          });
          nodeMap.set(nodeId, true);
          levelCounts[level]++;
        }
      }

      // 处理公司之间的交互关系作为边
      stepData.forEach((item: any) => {
        const company = item;
        const sourceId = company.id || company.company_id;

        // 如果有record字段，处理交互记录
        if (company.record && Array.isArray(company.record)) {
          company.record.forEach((record: any) => {
            // 检查是否是与其他公司的交互
            if (record.from && record.from !== sourceId) {
              const targetId = record.from;
              const edgeId = `${sourceId}-${targetId}-${company.step}`;

              // 避免重复边
              if (!edgeMap.has(edgeId)) {
                // 添加交互关系边
                edges.push({
                  source: sourceId,
                  target: targetId,
                  id: edgeId,
                  step: company.step, // 添加step字段
                  record_data: record, // 保存完整的记录数据
                  size: 1
                });
                edgeMap.set(edgeId, true);
              }
            }
          });
        }
      });
    } else {
      // 处理原有格式的产业数据
      // 处理不同层级的节点
      const processCompany = async (originalLevel: string, company: any, index: number) => {
        // 添加公司节点
        const nodeId = company.name;
        console.log(`处理公司节点: ${nodeId}, 层级: ${originalLevel}, 是否已存在: ${nodeMap.has(nodeId)}`);
        if (!nodeMap.has(nodeId)) {
          let level = originalLevel; // 默认使用JSON文件中的层级信息

          // 如果有expId，则尝试调用API获取层级
          if (expId) {
            try {
              const levelData = await Api.getAgentLevel(expId, company.id);
              if (levelData && levelData.level) {
                level = `level_${levelData.level}`;
                console.log(`从API获取节点 ${nodeId} 的层级: ${level}`);
              }
            } catch (error) {
              console.error(`获取节点 ${nodeId} 层级失败:`, error);
              // 如果API调用失败，使用JSON文件中的层级信息
              console.log(`使用JSON文件中的层级信息: ${level}`);
            }
          }

          nodes.push({
            id: nodeId,
            label: nodeId,
            type: 'company',
            level: level,
            size: 30,
            // 为层级布局添加列索引，使节点在同一层级内均匀分布
            colIndex: index,
            company_data: company // 保存完整的公司数据
          });
          nodeMap.set(nodeId, true);
          levelCounts[level]++;
          console.log(`成功创建节点: ${nodeId}, 当前节点总数: ${nodes.length}`);
        } else {
          console.log(`跳过重复节点: ${nodeId}`);
        }
      };

      // 处理所有公司
      const processAllCompanies = async () => {
        for (const originalLevel of Object.keys(industryData)) {
          const companies = industryData[originalLevel];
          for (let index = 0; index < companies.length; index++) {
            await processCompany(originalLevel, companies[index], index);
          }
        }
      };

      // 启动处理
      await processAllCompanies();
      console.log('所有公司节点处理完成');
      console.log('各层级节点数量:', levelCounts);

      // 处理边关系
      Object.keys(industryData).forEach(level => {
        const companies = industryData[level];

        companies.forEach((company: any) => {
          // 处理产品与原材料的关系
          company.main_products.forEach((product: any) => {
            if (product.related_materials && product.related_materials.length > 0) {
              product.related_materials.forEach((material: any) => {
                // 查找提供这种原材料的公司
                Object.keys(industryData).forEach(otherLevel => {
                  industryData[otherLevel].forEach((otherCompany: any) => {
                    otherCompany.available_materials.forEach((availableMaterial: any) => {
                      if (availableMaterial.material_id === material.material_id) {
                        // 创建边的唯一标识
                        const edgeId = `${otherCompany.name}-${company.name}-${material.material_id}`;

                        // 避免重复边
                        if (!edgeMap.has(edgeId)) {
                          // 添加供应关系边，包含产品信息
                          edges.push({
                            source: otherCompany.name,
                            target: company.name,
                            id: edgeId,
                            size: 1,
                            type: 'material_supply',
                            materialInfo: {
                              material_id: material.material_id,
                              material_name: material.material_name || availableMaterial.material_name || `材料${material.material_id}`,
                              supplier: otherCompany.name,
                              consumer: company.name,
                              product_name: product.product_name || '未知产品'
                            }
                          });
                          edgeMap.set(edgeId, true);
                        }
                      }
                    });
                  });
                });
              });
            }
          });
        });
      });
    }

    // 位置计算已移至数据处理阶段，根据布局模式动态处理

    console.log('处理后的节点数量:', nodes.length);
    console.log('处理后的边数量:', edges.length);
    console.log('各层级节点数量:', levelCounts);

    return { nodes, edges, apiData: false };
  };

  // 处理高亮连接的函数
  const handleHighlightConnection = (event: CustomEvent) => {
    const { sourceId, targetId } = event.detail;
    if (!graphRef.current || !sourceId || !targetId) return;

    const graph = graphRef.current;
    const nodes = graph.getNodes();
    const edges = graph.getEdges();

    // 重置所有节点和边的状态
    nodes.forEach(n => {
      graph.clearItemStates(n);
      n.update({
        style: {
          lineWidth: 2
        }
      });
    });

    edges.forEach(edge => {
      graph.clearItemStates(edge);
      graph.updateItem(edge, {
        style: {
          stroke: '#aaa',
          lineWidth: 1
        }
      });
    });

    // 高亮源节点和目标节点
    const sourceNode = graph.findById(sourceId);
    const targetNode = graph.findById(targetId);

    if (sourceNode) {
      graph.setItemState(sourceNode, 'selected', true);
      sourceNode.update({
        style: {
          lineWidth: 4,
          stroke: '#1890ff'
        }
      });
      // sourceNode.toFront(); // 移除toFront调用，避免图谱位置重置
    }

    if (targetNode) {
      graph.setItemState(targetNode, 'selected', true);
      targetNode.update({
        style: {
          lineWidth: 4,
          stroke: '#ff7a45'
        }
      });
      // targetNode.toFront(); // 移除toFront调用，避免图谱位置重置
    }

    // 高亮连接这两个节点的边
    edges.forEach(edge => {
      const edgeModel = edge.getModel();
      if ((edgeModel.source === sourceId && edgeModel.target === targetId) ||
          (edgeModel.source === targetId && edgeModel.target === sourceId)) {
        graph.setItemState(edge, 'selected', true);
        graph.updateItem(edge, {
          style: {
            stroke: '#f00',
            lineWidth: 2
          }
        });
        // edge.toFront(); // 移除toFront调用，避免图谱位置重置
      }
    });

    // 设置选中状态
    setSelectedNodeId(sourceId);
  };



  // 监听 filterByStep 事件，根据 step 值过滤数据
  useEffect(() => {
    const handleFilterByStep = (event: CustomEvent) => {
      const { step } = event.detail;
      setCurrentStep(step);

      if (!data) return;

      // 过滤节点和边，只显示当前 step 的数据
      if (step !== undefined && step !== null && data.nodes && data.edges) {
        const filteredNodes = data.nodes.filter((node: any) => {
          // 如果节点有 step 字段，则根据 step 过滤
          if ('step' in node) {
            return node.step === step;
          }
          // 如果节点没有 step 字段，则始终显示
          return true;
        });

        const filteredEdges = data.edges.filter((edge: any) => {
          // 如果边有 step 字段，则根据 step 过滤
          if ('step' in edge) {
            return edge.step === step;
          }
          // 如果边没有 step 字段，则始终显示
          return true;
        });

        setFilteredData({ nodes: filteredNodes, edges: filteredEdges });

        // 如果开启了行为高亮，则触发新的基于步数的行为高亮
        if (behaviorHighlightEnabled && step !== null) {
          setTimeout(() => {
            highlightBehaviorConnectionsByStep(step);
          }, 100); // 延迟执行，确保图谱已更新
        }
      } else {
        // 如果没有指定 step，则显示所有数据
        setFilteredData(data);
      }
    };

    window.addEventListener('filterByStep', handleFilterByStep as EventListener);

    return () => {
      window.removeEventListener('filterByStep', handleFilterByStep as EventListener);
    };
  }, [data, behaviorHighlightEnabled, selectedNodeId]);

  // 监听行为高亮开关状态变化
  useEffect(() => {
    if (behaviorHighlightEnabled && currentStep !== null && (edgeDisplayMode === 'transaction' || edgeDisplayMode === 'communication')) {
      // 开关开启时，触发高亮
      setTimeout(() => {
        highlightBehaviorConnectionsByStep(currentStep);
      }, 100);
    } else if (!behaviorHighlightEnabled && graphRef.current) {
      // 开关关闭时，重置所有边的样式
      const graph = graphRef.current;
      const edges = graph.getEdges();
      if (edges && edges.length > 0) {
        edges.forEach(edge => {
          graph.updateItem(edge, {
            style: {
              stroke: '#aaa',
              lineWidth: 1
            }
          });
        });
        // 使用轻量级重绘替代强制刷新，避免重影
        graph.paint();
      }
      setDebugMessage('');
    }
  }, [behaviorHighlightEnabled, currentStep, edgeDisplayMode]);

  // 初始化图谱数据
  useEffect(() => {
    if (!data) {
      return;
    }

    // 初始时设置过滤后的数据为原始数据
    setFilteredData(data);
  }, [data]);

  // 渲染图谱
  useEffect(() => {
    if (!containerRef.current || !filteredData) return;

    // 清理之前的图谱实例
    if (graphRef.current) {
      graphRef.current.destroy();
      graphRef.current = null;
    }

    // 彻底清理容器DOM，防止重影
    if (containerRef.current) {
      containerRef.current.innerHTML = '';
    }

    // 添加高亮连接事件监听器
    window.addEventListener('highlightConnection', handleHighlightConnection as EventListener);

    // 设置节点样式
    const nodeConfig = {
      company: {
        fill: '#b7eb8f',
        stroke: '#52c41a',
        icon: 'shop'
      }
    };

    // 图谱配置
    const width = containerRef.current.scrollWidth;
    const height = containerRef.current.scrollHeight || 800;

    // 根据布局模式动态配置布局
    const getLayoutConfig = () => {
      switch (layoutMode) {
        case 'force':
          return {
            type: 'force',
            preventOverlap: true,
            nodeSize: 40,
            nodeStrength: -300,
            edgeStrength: 0.1,
            collideStrength: 0.8,
            alpha: 0.3, // 降低初始能量，减少布局变化
            alphaDecay: 0.05, // 加快衰减，更快稳定
            alphaMin: 0.001, // 降低最小能量阈值
            forceSimulation: null,
            tick: 100, // 限制迭代次数
            onTick: () => {
              // 可以在这里添加动画效果
            },
            onLayoutEnd: () => {
              console.log('力导向布局完成');
            }
          };
        case 'dagre':
          return {
            type: 'dagre',
            rankdir: 'TB', // 从上到下布局
            align: 'UL', // 对齐方式
            nodesep: 50, // 节点间距
            ranksep: 80, // 层级间距
            controlPoints: true // 启用控制点
          };
        case 'grid':
          return {
            type: 'grid',
            begin: [0, 0],
            preventOverlap: true,
            nodeSize: 40,
            condense: false,
            rows: Math.ceil(Math.sqrt(filteredData.nodes.length)),
            cols: Math.ceil(Math.sqrt(filteredData.nodes.length)),
            sortBy: 'level' // 按层级排序
          };
        case 'hierarchical':
        default:
          return {
            type: 'preset',
            workerEnabled: false
          };
      }
    };

    // 创建图谱实例
    const graph = new G6.Graph({
      container: containerRef.current,
      width,
      height,
      modes: {
        default: ['drag-canvas', 'zoom-canvas', 'drag-node', 'click-select']
      },
      layout: getLayoutConfig(),
      // 防止自动调整的配置
      fitView: false, // 禁用自动适应视图
      fitViewPadding: 0, // 设置适应视图的内边距为0
      animate: false,
      // 添加渲染优化配置，防止重影
      renderer: 'canvas',
      enabledStack: false, // 禁用操作栈，减少内存占用
      autoPaint: false, // 禁用自动重绘，手动控制渲染时机
      defaultNode: {
        size: 30,
        style: {
          fill: '#b7eb8f',
          stroke: '#52c41a',
          lineWidth: 2,
        },
        labelCfg: {
          style: {
            fill: '#000000',
            fontSize: 12,
          },
        },
      },
      defaultEdge: {
        style: {
          stroke: '#aaa',
          lineWidth: 1,
          endArrow: {
            path: G6.Arrow.triangle(8, 8, 0),
            fill: '#aaa',
          },
        },
      },
      nodeStateStyles: {
        hover: {
          lineWidth: 3,
        },
        selected: {
          lineWidth: 4,
          stroke: '#f00',
        },
      },
      edgeStateStyles: {
        hover: {
          stroke: '#999',
        },
        selected: {
          stroke: '#f00',
          lineWidth: 2,
        },
      },
    });

    // 注册自定义节点
    G6.registerNode(
      'industry-node',
      {
        draw(cfg, group) {
          const { id, label, level = 'level_1', size = 30 } = cfg as any;
          const config = nodeConfig.company;

          // 根据层级设置不同的颜色
          let fillColor = config.fill;
          let strokeColor = config.stroke;
          let labelBgColor = 'rgba(255, 255, 255, 0.8)';

          // 动态颜色配置，支持更多层级
          const levelColors = [
            { fill: '#91d5ff', stroke: '#1890ff' }, // level_1 - 蓝色
            { fill: '#b7eb8f', stroke: '#52c41a' }, // level_2 - 绿色
            { fill: '#ffe58f', stroke: '#faad14' }, // level_3 - 黄色
            { fill: '#ffadd2', stroke: '#eb2f96' }, // level_4 - 粉色
            { fill: '#d3adf7', stroke: '#722ed1' }, // level_5 - 紫色
            { fill: '#ffd591', stroke: '#fa8c16' }, // level_6 - 橙色
            { fill: '#87e8de', stroke: '#13c2c2' }, // level_7 - 青色
            { fill: '#ffb3b3', stroke: '#f5222d' }, // level_8 - 红色
            { fill: '#c7c7c7', stroke: '#8c8c8c' }, // level_9 - 灰色
            { fill: '#bae637', stroke: '#a0d911' }, // level_10 - 亮绿色
          ];

          // 从层级字符串中提取数字
          const levelMatch = level.match(/level_(\d+)/);
          if (levelMatch) {
            const levelNum = parseInt(levelMatch[1]) - 1; // 转换为0基索引
            if (levelNum >= 0 && levelNum < levelColors.length) {
              fillColor = levelColors[levelNum].fill;
              strokeColor = levelColors[levelNum].stroke;
            } else {
              // 如果超出预定义颜色范围，使用循环颜色
              const colorIndex = levelNum % levelColors.length;
              fillColor = levelColors[colorIndex].fill;
              strokeColor = levelColors[colorIndex].stroke;
            }
          }

          // 添加一个白色背景圆形，增加视觉区分度
          group.addShape('circle', {
            attrs: {
              x: 0,
              y: 0,
              r: size / 2 + 4, // 增大背景圆形
              fill: '#fff',
              stroke: '#f0f0f0',
              lineWidth: 1,
              // 添加更明显的阴影效果，增强节点间的区分度
              shadowColor: 'rgba(0,0,0,0.15)',
              shadowBlur: 8,
              shadowOffsetX: 0,
              shadowOffsetY: 3,
            },
            name: 'node-bg',
          });

          const keyShape = group.addShape('circle', {
            attrs: {
              x: 0,
              y: 0,
              r: size / 2,
              fill: fillColor,
              stroke: strokeColor,
              lineWidth: 2,
              // 增强节点主体的视觉效果
              opacity: 0.9, // 略微透明，使颜色更柔和
              // 添加渐变效果，增强视觉层次感
              fillOpacity: 0.9,
              // 添加内部阴影，增强立体感
              shadowColor: strokeColor,
              shadowBlur: 4,
              shadowOffsetX: 0,
              shadowOffsetY: 0,
            },
            name: 'node-keyshape',
          });

          // 添加标签背景，提高文字可读性
          const textWidth = label.length * 12;
          group.addShape('rect', {
            attrs: {
              x: -textWidth / 2 - 6,
              y: size / 2 + 5,
              width: textWidth + 12,
              height: 22,
              radius: 4,
              fill: labelBgColor,
              stroke: strokeColor,
              lineWidth: 0.5,
              // 添加阴影效果，增强标签可读性
              shadowColor: 'rgba(0,0,0,0.1)',
              shadowBlur: 3,
              shadowOffsetX: 0,
              shadowOffsetY: 1,
            },
            name: 'text-bg',
          });

          // 添加文本标签
          group.addShape('text', {
            attrs: {
              text: label,
              x: 0,
              y: size / 2 + 16,
              textAlign: 'center',
              textBaseline: 'middle',
              fill: '#333',
              fontSize: 12,
              fontWeight: 600, // 增加字体粗细，提高可读性
              // 添加文字描边，增强可读性
              stroke: '#ffffff',
              lineWidth: 0.3,
            },
            name: 'node-label',
          });

          return keyShape;
        },
        // 更新节点时的逻辑
        update(cfg, node) {
          const group = node.getContainer();
          const keyShape = group.get('children').find((shape: any) => shape.get('name') === 'node-keyshape');

          if (keyShape) {
            const style = cfg.style || {};
            keyShape.attr(style);
          }
          return true;
        },
      },
      'circle',
    );

    // 处理数据
    if (!filteredData || typeof filteredData !== 'object' || filteredData instanceof Promise) {
      console.error('数据格式不正确 - 数据为空、非对象或Promise:', filteredData);
      message.error('数据格式不正确，无法渲染图谱');
      setLoading(false);
      return;
    }

    if (!filteredData.nodes || !filteredData.edges) {
      console.error('数据格式不正确 - 缺少nodes或edges:', filteredData);
      message.error('数据格式不正确，无法渲染图谱');
      setLoading(false);
      return;
    }

    // 根据连线显示模式过滤边
    let filteredEdges = filteredData.edges;
    if (edgeDisplayMode !== 'all') {
      filteredEdges = filteredData.edges.filter((edge: any) => edge.type === edgeDisplayMode);
    }

    // 处理节点数据，根据布局模式决定是否预设位置
    let processedNodes = filteredData.nodes.map((node: any) => ({
      ...node,
      type: 'industry-node',
    }));

    // 只有在层级布局模式下才预设节点位置
    if (layoutMode === 'hierarchical') {
      // 计算节点位置，确保同一层级的节点居中对齐
      const containerWidth = width || 1200;
      const containerHeight = height || 600;
      const nodeSpacing = 150;

      // 动态按层级分组节点
      const nodesByLevel: { [key: string]: any[] } = {};
      processedNodes.forEach(node => {
        if (!nodesByLevel[node.level]) {
          nodesByLevel[node.level] = [];
        }
        nodesByLevel[node.level].push(node);
      });

      // 获取所有层级并排序
      const levels = Object.keys(nodesByLevel).sort((a, b) => {
        const levelA = parseInt(a.replace('level_', ''));
        const levelB = parseInt(b.replace('level_', ''));
        return levelA - levelB;
      });

      const levelCount = levels.length;
      const levelHeight = levelCount > 0 ? containerHeight / levelCount : containerHeight;

      // 为每个层级的节点计算位置
      levels.forEach((level, levelIndex) => {
        const levelNodes = nodesByLevel[level];
        const nodeCount = levelNodes.length;

        if (nodeCount > 0) {
          // 计算该层级节点的总宽度
          const totalWidth = (nodeCount - 1) * nodeSpacing;
          // 计算起始x坐标，使节点居中
          const startX = (containerWidth - totalWidth) / 2;
          // 计算y坐标
          const y = levelHeight * levelIndex + levelHeight / 2;

          // 为每个节点设置位置
          levelNodes.forEach((node, index) => {
            node.x = startX + index * nodeSpacing;
            node.y = y;
          });
        }
      });
    }
    // 对于其他布局模式，不预设位置，让G6的布局算法自动计算

    const processedData = {
      nodes: processedNodes,
      edges: filteredEdges,
    };

    console.log('图谱渲染数据:', {
      nodes: processedData.nodes.length,
      edges: processedData.edges.length,
      edgesSample: processedData.edges.slice(0, 3)
    });

    // 加载数据
    graph.data(processedData);
    graph.render();
    // 由于设置了autoPaint: false，需要手动触发绘制
    graph.paint();
    graphRef.current = graph;

    // 立即停止布局算法，防止自动调整
    setTimeout(() => {
      if (graph.get('layoutController')) {
        graph.get('layoutController').stop();
      }
    }, 500); // 给布局一些时间完成初始计算

    // 添加节点点击事件
    graph.on('node:click', (evt) => {
      console.log('节点点击事件触发:', evt);
      evt.stopPropagation(); // 阻止事件冒泡到画布
      const node = evt.item;
      const nodeModel = node.getModel();
      const nodeId = nodeModel.id as string;
      console.log('点击的节点ID:', nodeId);
      const edges = graph.getEdges();
      const nodes = graph.getNodes();

      // 批量重置所有节点的状态，减少布局影响
      graph.getNodes().forEach(n => {
        graph.clearItemStates(n);
        graph.updateItem(n, {
          style: {
            lineWidth: 2
          }
        });
      });

      // 如果点击的是已选中的节点，则取消选中状态
      if (selectedNodeId === nodeId) {
        // 重置所有边的状态
        edges.forEach(edge => {
          graph.clearItemStates(edge);
          graph.updateItem(edge, {
            style: {
              stroke: '#aaa',
              lineWidth: 1
            },
            label: '', // 清除标签
            labelCfg: undefined // 清除标签配置
          });
        });
        setSelectedNodeId(null);

        // 触发nodeSelected事件，传递空数据表示取消选中
        const event = new CustomEvent('nodeSelected', {
          detail: { nodeId: null, nodeData: null }
        });
        console.log('IndustryGraph: Dispatching nodeSelected event (node click - deselect):', { nodeId: null, nodeData: null });
        window.dispatchEvent(event);
      } else {
        // 重置所有边的状态
        edges.forEach(edge => {
          graph.clearItemStates(edge);
          graph.updateItem(edge, {
            style: {
              stroke: '#aaa',
              lineWidth: 1
            },
            label: '', // 清除标签
            labelCfg: undefined // 清除标签配置
          });
        });

        // 高亮当前选中的节点
        graph.updateItem(node, {
          style: {
            lineWidth: 4,
            stroke: '#ff7a45'
          }
        });

        // 处理与当前节点相关的边
        edges.forEach(edge => {
          const edgeModel = edge.getModel();

          // 指向此节点的连线变为红色
          if (edgeModel.target === nodeId) {
            const updateConfig: any = {
              style: {
                stroke: '#f00',
                lineWidth: 3
              }
            };

            // 如果是供给模式且是材料供应边，添加原料信息标签
            if (edgeDisplayMode === 'material_supply' && edgeModel.type === 'material_supply') {
              let materialNames;

              // 处理新的materials_detail格式
              if (edgeModel.material_data?.materials_detail && Array.isArray(edgeModel.material_data.materials_detail)) {
                materialNames = edgeModel.material_data.materials_detail.map(m =>
                  `${m.material_name}(${m.available_quantity})`
                ).join('\n');
              } else if (edgeModel.material_data?.material_names && Array.isArray(edgeModel.material_data.material_names)) {
                // 兼容旧的material_names数组格式
                materialNames = edgeModel.material_data.material_names.join('\n');
              } else {
                // 兼容更旧的单个material_name格式
                materialNames = edgeModel.materialInfo?.material_name || edgeModel.material_data?.material_name || '未知原料';
              }

              updateConfig.label = materialNames;
              updateConfig.labelCfg = {
                style: {
                  fill: '#000',
                  fontSize: 10,
                  fontWeight: 'bold',
                  background: {
                    fill: '#f00',
                    padding: [2, 4],
                    radius: 3
                  }
                }
              };
            }

            graph.updateItem(edge, updateConfig);
          }

          // 由此节点出发的连线变为蓝色
          if (edgeModel.source === nodeId) {
            const updateConfig: any = {
              style: {
                stroke: '#1890ff',
                lineWidth: 3
              }
            };

            // 如果是供给模式且是材料供应边，添加原料信息标签
            if (edgeDisplayMode === 'material_supply' && edgeModel.type === 'material_supply') {
              let materialNames;

              // 处理新的materials_detail格式
              if (edgeModel.material_data?.materials_detail && Array.isArray(edgeModel.material_data.materials_detail)) {
                materialNames = edgeModel.material_data.materials_detail.map(m =>
                  `${m.material_name}(${m.available_quantity})`
                ).join('\n');
              } else if (edgeModel.material_data?.material_names && Array.isArray(edgeModel.material_data.material_names)) {
                // 兼容旧的material_names数组格式
                materialNames = edgeModel.material_data.material_names.join('\n');
              } else {
                // 兼容更旧的单个material_name格式
                materialNames = edgeModel.materialInfo?.material_name || edgeModel.material_data?.material_name || '未知原料';
              }

              updateConfig.label = materialNames;
              updateConfig.labelCfg = {
                style: {
                  fill: '#000',
                  fontSize: 10,
                  fontWeight: 'bold',
                  background: {
                    fill: '#1890ff',
                    padding: [2, 4],
                    radius: 3
                  }
                }
              };
            }

            graph.updateItem(edge, updateConfig);
          }
        });

        // 设置选中状态
        setSelectedNodeId(nodeId);
        // node.toFront(); // 移除toFront调用，避免图谱位置重置
        graph.setItemState(node, 'selected', true);

        // 如果开启了行为高亮且有当前步数，则触发行为高亮
        if (behaviorHighlightEnabled && currentStep !== null) {
          setTimeout(() => {
            highlightBehaviorConnections(nodeId, currentStep);
          }, 100); // 延迟执行，确保图谱已更新
        }

        // 高亮相关边和节点
        edges.forEach(edge => {
          const edgeModel = edge.getModel();
          if (edgeModel.source === nodeId || edgeModel.target === nodeId) {
            graph.setItemState(edge, 'selected', true);
            // edge.toFront(); // 移除toFront调用，避免图谱位置重置

            // 高亮相连的节点
            const otherNodeId = edgeModel.source === nodeId ? edgeModel.target : edgeModel.source;
            const otherNode = graph.findById(otherNodeId);
            if (otherNode) {
              graph.setItemState(otherNode, 'selected', true);
              // otherNode.toFront(); // 移除toFront调用，避免图谱位置重置
            }
          }
        });

        // 获取节点详情
        fetchNodeDetail(nodeId);

        // 触发自定义事件，通知其他组件节点被选中
        // 查找节点的完整数据
        let nodeData = null;
        if (data && data.stateData) {
          // 如果是state_*.json格式的数据
          // 始终获取该节点在所有步数中的数据，不按currentStep过滤
          // 这样Work History可以显示完整的工作历史
          nodeData = data.stateData.filter((item: any) =>
            item.company_name === nodeId || item.id === nodeId
          );
          console.log('节点点击事件 - 找到的nodeData (所有步数):', nodeData);
        } else {
          // 如果是原有格式的数据，从节点模型中获取
          nodeData = nodeModel.company_data || nodeModel;
          console.log('节点点击事件 - 从节点模型获取的数据:', nodeData);
        }

        const event = new CustomEvent('nodeSelected', {
          detail: { nodeId, nodeData }
        });
        console.log('IndustryGraph: Dispatching nodeSelected event:', { nodeId, nodeData });
        window.dispatchEvent(event);
      }

      // 最终确保停止布局算法，防止节点位置被重新计算
      setTimeout(() => {
        if (graph.get('layoutController')) {
          graph.get('layoutController').stop();
        }
      }, 50); // 短暂延迟确保所有更新完成
    });

    // 添加画布点击事件，恢复边和节点的默认样式
    graph.on('canvas:click', () => {
      if (selectedNodeId !== null) {
        // 重置所有边的样式
        const edges = graph.getEdges();
        edges.forEach(edge => {
          graph.clearItemStates(edge);
          graph.updateItem(edge, {
            style: {
              stroke: '#aaa',
              lineWidth: 1
            },
            label: '', // 清除标签
            labelCfg: undefined // 清除标签配置
          });
        });

        // 批量重置所有节点的样式，减少布局影响
        graph.getNodes().forEach(node => {
          graph.clearItemStates(node);
          graph.updateItem(node, {
            style: {
              lineWidth: 2
            }
          });
        });

        setSelectedNodeId(null);

        // 清除行为高亮
        if (behaviorHighlightEnabled) {
          clearBehaviorHighlight();
        }

        // 触发nodeSelected事件，传递空数据表示取消选中
        const event = new CustomEvent('nodeSelected', {
          detail: { nodeId: null, nodeData: null }
        });
        console.log('IndustryGraph: Dispatching nodeSelected event (canvas click - deselect):', { nodeId: null, nodeData: null });
        window.dispatchEvent(event);
      }

      // 最终确保停止布局算法，防止节点位置被重新计算
      setTimeout(() => {
        if (graph.get('layoutController')) {
          graph.get('layoutController').stop();
        }
      }, 50); // 短暂延迟确保所有更新完成
    });

    // 添加节点双击事件，显示节点详情
     graph.on('node:dblclick', (evt) => {
       const node = evt.item;
       const nodeModel = node.getModel();
       const nodeId = nodeModel.id as string;
       fetchNodeDetail(nodeId);
     });

    // 监听窗口大小变化
    const handleResize = () => {
      if (containerRef.current && graphRef.current) {
        const width = containerRef.current.scrollWidth;
        const height = containerRef.current.scrollHeight || 800;
        graphRef.current.changeSize(width, height);
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('highlightConnection', handleHighlightConnection as EventListener);
      graph.destroy();
    };
  }, [filteredData, selectedNodeId, edgeDisplayMode, layoutMode]);



  // 重新加载图谱
  const handleReload = () => {
    if (graphRef.current) {
      setLoading(true);
      setSelectedNodeId(null);
      setTimeout(() => {
        // 重新应用当前布局
        graphRef.current?.updateLayout({
          type: layoutMode === 'hierarchical' ? 'preset' : layoutMode,
          ...(() => {
            switch (layoutMode) {
              case 'force':
                return {
                  preventOverlap: true,
                  nodeSize: 40,
                  nodeStrength: -300,
                  edgeStrength: 0.1,
                  collideStrength: 0.8,
                  alpha: 0.8,
                  alphaDecay: 0.028,
                  alphaMin: 0.01
                };
              case 'dagre':
                return {
                  rankdir: 'TB',
                  align: 'UL',
                  nodesep: 50,
                  ranksep: 80,
                  controlPoints: true
                };
              case 'grid':
                return {
                  begin: [0, 0],
                  preventOverlap: true,
                  nodeSize: 40,
                  condense: false,
                  rows: Math.ceil(Math.sqrt(filteredData?.nodes?.length || 1)),
                  cols: Math.ceil(Math.sqrt(filteredData?.nodes?.length || 1)),
                  sortBy: 'level'
                };
              default:
                return { workerEnabled: false };
            }
          })()
        });
        graphRef.current?.fitView();
        setLoading(false);
      }, 100);
    }
  };

  // 切换全屏
  const toggleFullscreen = () => {
    setSelectedNodeId(null);
    setFullscreen(!fullscreen);
    setTimeout(() => {
      if (graphRef.current && containerRef.current) {
        const width = containerRef.current.scrollWidth;
        const height = containerRef.current.scrollHeight || 800;
        graphRef.current.changeSize(width, height);
        graphRef.current.fitView();
      }
    }, 100);
  };

  // 放大
  const zoomIn = () => {
    if (graphRef.current) {
      // 清理画布但保留数据，防止重影
      const canvas = graphRef.current.get('canvas');
      if (canvas) {
        canvas.clear();
      }
      const currentZoom = graphRef.current.getZoom();
      graphRef.current.zoomTo(currentZoom * 1.2);
      // 缩放后重新渲染，确保清晰显示
      setTimeout(() => {
        if (graphRef.current) {
          graphRef.current.paint();
        }
      }, 50);
    }
  };

  // 缩小
  const zoomOut = () => {
    if (graphRef.current) {
      // 清理画布但保留数据，防止重影
      const canvas = graphRef.current.get('canvas');
      if (canvas) {
        canvas.clear();
      }
      const currentZoom = graphRef.current.getZoom();
      graphRef.current.zoomTo(currentZoom / 1.2);
      // 缩放后重新渲染，确保清晰显示
      setTimeout(() => {
        if (graphRef.current) {
          graphRef.current.paint();
        }
      }, 50);
    }
  };

  // 切换布局模式
  const handleLayoutChange = (newLayout: 'hierarchical' | 'force' | 'dagre' | 'grid') => {
    setLayoutMode(newLayout);
    // useEffect会自动检测layoutMode变化并重新渲染图谱
  };

  return (
    <Card
      title={<Title level={5} style={{ margin: 0, fontSize: '16px' }}>产业链图谱</Title>}
      style={{
        width: '100%',
        height: '100%',
        position: fullscreen ? 'fixed' : 'relative',
        top: fullscreen ? 0 : 'auto',
        left: fullscreen ? 0 : 'auto',
        zIndex: fullscreen ? 1000 : 1,
        margin: 0,
        padding: 0,
        overflow: 'hidden',
        border: 'none',
        borderRadius: 0,
        boxShadow: 'none',
        display: 'flex',
        flexDirection: 'column',
      }}
      bodyStyle={{ padding: '8px', flex: 1, display: 'flex', flexDirection: 'column' }}
      extra={
        <Space size="small">
          <Tooltip title="连线显示模式">
            <Space.Compact>
              <Button
                size="small"
                type={edgeDisplayMode === 'all' ? 'primary' : 'default'}
                onClick={() => setEdgeDisplayMode('all')}
              >
                全部
              </Button>
              <Button
                size="small"
                type={edgeDisplayMode === 'material_supply' ? 'primary' : 'default'}
                onClick={() => setEdgeDisplayMode('material_supply')}
              >
                供给
              </Button>
              <Button
                size="small"
                type={edgeDisplayMode === 'transaction' ? 'primary' : 'default'}
                onClick={() => setEdgeDisplayMode('transaction')}
              >
                交易
              </Button>
              <Button
                size="small"
                type={edgeDisplayMode === 'communication' ? 'primary' : 'default'}
                onClick={() => setEdgeDisplayMode('communication')}
              >
                通信
              </Button>
            </Space.Compact>
          </Tooltip>
          <Tooltip title="布局模式">
            <Space.Compact>
              <Button
                size="small"
                type={layoutMode === 'hierarchical' ? 'primary' : 'default'}
                onClick={() => handleLayoutChange('hierarchical')}
              >
                层级
              </Button>
              <Button
                size="small"
                type={layoutMode === 'force' ? 'primary' : 'default'}
                onClick={() => handleLayoutChange('force')}
              >
                力导向
              </Button>
              <Button
                size="small"
                type={layoutMode === 'dagre' ? 'primary' : 'default'}
                onClick={() => handleLayoutChange('dagre')}
              >
                分层
              </Button>
              <Button
                size="small"
                type={layoutMode === 'grid' ? 'primary' : 'default'}
                onClick={() => handleLayoutChange('grid')}
              >
                网格
              </Button>
            </Space.Compact>
          </Tooltip>
          <Tooltip title="查看数据库数据">
            <Button
              size="small"
              icon={<DatabaseOutlined />}
              onClick={() => setShowApiModal(true)}
              loading={apiLoading}
              type={apiData ? "primary" : "default"}
            />
          </Tooltip>
          <Tooltip title="行为高亮：根据当前步数和选中节点高亮相关节点标签">
            <Space size="small">
              <span style={{ fontSize: '12px', color: '#666' }}>行为高亮</span>
              <Switch
                size="small"
                checked={behaviorHighlightEnabled}
                onChange={(checked) => {
                  setBehaviorHighlightEnabled(checked);
                  if (!checked) {
                    clearBehaviorHighlight();
                  } else if (selectedNodeId && currentStep !== null) {
                    setTimeout(() => {
                      highlightBehaviorConnections(selectedNodeId, currentStep);
                    }, 100);
                  }
                }}
              />
            </Space>
          </Tooltip>
          <Tooltip title="重新加载">
            <Button size="small" icon={<ReloadOutlined />} onClick={handleReload} />
          </Tooltip>
          {/* 删除查看详情按钮，详情将显示在左侧边栏 */}
          <Tooltip title="放大">
            <Button size="small" icon={<ZoomInOutlined />} onClick={zoomIn} />
          </Tooltip>
          <Tooltip title="缩小">
            <Button size="small" icon={<ZoomOutOutlined />} onClick={zoomOut} />
          </Tooltip>
          <Tooltip title={fullscreen ? "退出全屏" : "全屏"}>
            <Button size="small" icon={<FullscreenOutlined />} onClick={toggleFullscreen} />
          </Tooltip>
        </Space>
      }
    >
      <Spin spinning={loading} tip="加载图谱中..." style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div style={{ position: 'relative', flex: 1, display: 'flex', flexDirection: 'column' }}>
          {!loading && (
            <div style={{ padding: '4px 8px', background: 'rgba(0,0,0,0.03)', borderRadius: '4px', marginBottom: '4px' }}>
              <Typography.Text type="secondary" style={{ fontSize: '12px' }}>
                提示：点击节点可查看相关连线，指向该节点的连线显示为红色，由该节点出发的连线显示为蓝色。使用上方按钮切换连线显示模式：全部、供给关系、交易关系、通信关系。节点详细信息会显示在左侧边栏中。开启"行为高亮"功能后，会根据当前时间轴步数和选中节点的行为历史，将相关节点的标签高亮为紫色背景。布局模式：层级布局按产业层级排列（蓝色为一级、绿色为二级、橙色为三级），力导向布局通过物理模拟自动调整节点位置避免重叠，分层布局采用有向无环图算法减少连线交叉，网格布局将节点均匀分布在网格中。
              </Typography.Text>
            </div>
          )}
          {debugMessage && (
            <div style={{
              background: '#f0f2f5',
              border: '1px solid #d9d9d9',
              borderRadius: '4px',
              padding: '8px 12px',
              marginBottom: '8px',
              fontSize: '12px',
              color: '#666',
              wordBreak: 'break-all'
            }}>
              {debugMessage}
            </div>
          )}
          <div
            ref={containerRef}
            style={{
              width: '100%',
              flex: 1,
              background: '#fff',
            }}>
          </div>
        </div>
      </Spin>
      {renderNodeDetailModal()}
      {renderApiDataModal()}
    </Card>
  );
};

export default IndustryGraph;
