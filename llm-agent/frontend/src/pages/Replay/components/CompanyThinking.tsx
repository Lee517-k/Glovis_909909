import React from 'react';
import { Card, Empty, Tag, Typography, Tooltip } from 'antd';
import { BuildOutlined, ShopOutlined, DollarOutlined, FileTextOutlined, DashboardOutlined } from '@ant-design/icons';
import { CompanyData, CompanyRecord } from './type';

const { Text } = Typography;

interface CompanyThinkingProps {
  nodeData: CompanyData[] | any;
  nodeId: string | null;
  currentStep: number;
}

/**
 * 企业思考内容组件
 * 显示企业的思考过程、决策逻辑和操作记录
 */
const CompanyThinking: React.FC<CompanyThinkingProps> = ({ nodeData, nodeId, currentStep }) => {
  console.log('CompanyThinking rendered with:', { nodeData, currentStep });
  
  // 如果没有数据，显示空状态
  if (!nodeData) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <Empty 
          description={
            <Text style={{ fontSize: '14px', color: '#666' }}>
              请选择一个企业节点以查看思考内容
            </Text>
          }
          image={Empty.PRESENTED_IMAGE_SIMPLE} 
        />
      </div>
    );
  }

  // 根据被点击节点的ID查找state_1.json中record的from字段匹配的记录，提取detailed_inquiry_text内容
  const getCompanyThinkingByStep = () => {
    if (!Array.isArray(nodeData) || !nodeId) {
      return [];
    }
    
    console.log('CompanyThinking: Processing data for nodeId:', nodeId);
    
    // 创建按步数分组的思考历史
    const thinkingHistory = [];
    
    for (let step = 0; step <= currentStep; step++) {
      // 找到当前步骤的数据
      const stepData = nodeData.find(item => item.step === step);
      const stepThoughts = [];
      
      if (stepData && stepData.record && stepData.record.length > 0) {
        // 查找record中from字段与当前节点ID匹配的记录
        stepData.record.forEach((record: any) => {
          const content = typeof record.content === 'object' ? record.content : record;
          const recordFrom = content.from || record.from;
          
          // 检查from字段是否与当前节点ID匹配
          if (recordFrom && recordFrom.toString() === nodeId.toString()) {
            let detailedText = '';
            
            // 解析嵌套的JSON结构：record.content.content可能是JSON字符串
            if (content.content && typeof content.content === 'string') {
              try {
                const parsedContent = JSON.parse(content.content);
                detailedText = parsedContent.detailed_inquiry_text || '';
              } catch (e) {
                // 如果解析失败，尝试直接获取
                detailedText = content.detailed_inquiry_text || content.content || '';
              }
            } else {
              // 直接获取detailed_inquiry_text
              detailedText = content.detailed_inquiry_text || '';
            }
            
            if (detailedText && detailedText.trim() !== '') {
              stepThoughts.push({
                step,
                detailedText: detailedText,
                content: content,
                from: recordFrom,
                type: 'thinking'
              });
            }
          }
        });
      }
      
      // 如果没有找到思考记录，添加"nothing to think"
      if (stepThoughts.length === 0) {
        stepThoughts.push({
          step,
          detailedText: 'nothing to think',
          content: { type: 'no-thoughts' },
          from: nodeId
        });
      }
      
      thinkingHistory.push({
        step,
        thoughts: stepThoughts
      });
    }
    
    return thinkingHistory;
  };

  const thinkingHistory = getCompanyThinkingByStep();

  // 如果没有思考历史，显示空状态
  if (thinkingHistory.length === 0) {
    return (
      <div style={{ padding: '20px', textAlign: 'center', background: '#f9f9f9', borderRadius: '8px' }}>
        <Empty 
          description={
            <div>
              <Text style={{ fontSize: '14px', color: '#666' }}>
                暂无企业思考记录
              </Text>
              <div style={{ marginTop: '8px', fontSize: '12px', color: '#999' }}>
                当前步骤: {currentStep}
              </div>
            </div>
          }
          image={Empty.PRESENTED_IMAGE_SIMPLE} 
        />
      </div>
    );
  }

  // 渲染思考记录
  const renderThinkingRecord = (thought: any, index: number) => {
    // 处理"nothing to think"的情况
    if (thought.detailedText === 'nothing to think') {
      return (
        <Card 
          key={index}
          className="thinking-card"
          size="small"
          style={{ 
            marginBottom: '12px', 
            borderRadius: '6px',
            boxShadow: '0 1px 2px rgba(0,0,0,0.1)',
            opacity: 0.6
          }}
          headStyle={{ 
            background: '#f5f5f5', 
            borderBottom: '1px solid #e8e8e8',
            padding: '8px 12px'
          }}
          bodyStyle={{ padding: '12px' }}
          title={
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <span style={{ 
                display: 'inline-flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                width: '24px',
                height: '24px',
                borderRadius: '50%',
                background: '#d9d9d9',
                color: '#fff'
              }}>
                <FileTextOutlined />
              </span>
              <span style={{ marginLeft: '8px', fontWeight: 'bold', color: '#999' }}>无思考内容</span>
              <Tag color="default" style={{ marginLeft: '8px' }}>Step {thought.step}</Tag>
            </div>
          }
        >
          <div style={{ 
            background: '#f9f9f9', 
            padding: '10px', 
            borderRadius: '6px', 
            textAlign: 'center',
            color: '#999',
            fontStyle: 'italic'
          }}>
            nothing to think
          </div>
        </Card>
      );
    }

    // 处理有思考内容的情况
    const content = typeof thought.content === 'object' ? thought.content : thought;
    const operationType = content.type || '';
    const thinkingType = thought.type || 'default';
    let detailedText = thought.detailedText || content.detailed_inquiry_text || '';
    
    // 根据思考类型设置图标和颜色
    let icon = <FileTextOutlined />;
    let color = 'blue';
    let title = '企业思考';

    if (thinkingType === 'deal-decision') {
      icon = <ShopOutlined />;
      color = 'purple';
      title = '交易决策';
    } else if (thinkingType === 'received-inquiry') {
      icon = <DollarOutlined />;
      color = 'green';
      title = '收到询价';
    } else if (operationType.includes('operation-price')) {
      icon = <DollarOutlined />;
      color = 'green';
      title = '价格思考';
    } else if (operationType.includes('operation-deal')) {
      icon = <ShopOutlined />;
      color = 'purple';
      title = '交易思考';
    } else if (operationType.includes('operation-build')) {
      icon = <BuildOutlined />;
      color = 'orange';
      title = '生产思考';
    }

    return (
      <Card 
        key={index}
        className="thinking-card"
        size="small"
        style={{ 
          marginBottom: '12px', 
          borderRadius: '6px',
          boxShadow: '0 1px 2px rgba(0,0,0,0.1)'
        }}
        headStyle={{ 
          background: '#f9f9f9', 
          borderBottom: '1px solid #f0f0f0',
          padding: '8px 12px'
        }}
        bodyStyle={{ padding: '12px' }}
        title={
          <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', marginRight: '8px' }}>
              <span style={{ 
                display: 'inline-flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                width: '24px',
                height: '24px',
                borderRadius: '50%',
                background: color,
                color: '#fff'
              }}>
                {icon}
              </span>
              <span style={{ marginLeft: '8px', fontWeight: 'bold' }}>{title}</span>
            </div>
            
            <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '4px' }}>
              <Tag color={color}>Step {thought.step}</Tag>
              {operationType && (
                <Tag color="blue">{operationType.replace('operation-', '')}</Tag>
              )}
              {content.from && (
                <Tag color="green">来自: {content.from}</Tag>
              )}
            </div>
          </div>
        }
      >
        {/* 显示详细思考文本 */}
        {detailedText && (
          <div className="detailed-text" style={{ marginBottom: '12px' }}>
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              marginBottom: '4px',
              borderLeft: `3px solid ${color}`,
              paddingLeft: '8px'
            }}>
              <FileTextOutlined style={{ marginRight: '4px', color: color }} />
              <Text strong>思考内容</Text>
            </div>
            <div style={{ 
              background: '#f5f5f5', 
              padding: '10px', 
              borderRadius: '6px', 
              marginTop: '4px',
              border: '1px solid #eee',
              fontSize: '13px',
              lineHeight: '1.5'
            }}>
              <Text>{detailedText}</Text>
            </div>
          </div>
        )}
      </Card>
    );
  };

  return (
    <div className="company-thinking" style={{ padding: '8px' }}>
      <div className="thinking-header" style={{ 
        marginBottom: '16px', 
        display: 'flex', 
        alignItems: 'center',
        padding: '8px',
        background: '#f0f2f5',
        borderRadius: '4px'
      }}>
        <BuildOutlined style={{ fontSize: '18px', color: '#1890ff' }} />
        <span style={{ marginLeft: '8px', fontWeight: 'bold', fontSize: '16px' }}>Company Thinking</span>
        <Text type="secondary" style={{ marginLeft: '8px' }}>
          (当前步骤: {currentStep})
        </Text>
      </div>
      
      <div className="thinking-records" style={{ 
        maxHeight: '500px', 
        overflowY: 'auto',
        padding: '4px',
        borderRadius: '4px',
        background: '#fafafa'
      }}>
        {thinkingHistory.map((stepHistory, stepIndex) => (
          <div key={stepIndex} style={{ marginBottom: '16px' }}>
            <div style={{ 
              background: '#e6f7ff', 
              padding: '8px 12px', 
              borderRadius: '4px', 
              marginBottom: '8px',
              borderLeft: '4px solid #1890ff'
            }}>
              <Text strong style={{ color: '#1890ff' }}>Step {stepHistory.step}</Text>
            </div>
            {stepHistory.thoughts.map((thought, thoughtIndex) => 
              renderThinkingRecord(thought, `${stepIndex}-${thoughtIndex}`)
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default CompanyThinking;