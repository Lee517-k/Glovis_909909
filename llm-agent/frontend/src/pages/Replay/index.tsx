import React, { useContext, useEffect, useState } from "react";
import { Row, Typography, Card, Tooltip, Button } from "antd";
import { InfoCircleOutlined, CommentOutlined, EnvironmentOutlined, UpOutlined, DownOutlined } from "@ant-design/icons";

import InfoPanel from "./InfoPanel";
import { ChatBox } from "./ChatBox";
import IndustryGraphDeck from "./IndustryGraphDeck";
import { useParams } from "react-router-dom";
import { store, StoreContext } from "./store";
import { observer } from 'mobx-react-lite'
import TimelinePlayer from "./TimelinePlayer";
import "./index.css";
import {Api, ApiError} from "../../services/api";
const { Title } = Typography;

const Replay: React.FC = observer(() => {
  const params = useParams();
  const expID = params.id;
  const replayStore = useContext(StoreContext);
  const [showGlobalPrompt, setShowGlobalPrompt] = useState(true);
  const [marketinfo,setMarketInfo] = useState("")  //TODO从接口获取
  useEffect(() => {
    // 从URL参数中提取k值，格式为 /replay/demo-k
    const getKFromExpID = (expID: string | undefined): string => {
      if (!expID) return '1'; // 默认值
      
      // 如果expID格式为 demo-k，提取k值
      const match = expID.match(/demo-(\d+)$/);
      if (match) {
        return match[1];
      }
      
      // 如果expID直接是数字，使用该数字
      if (/^\d+$/.test(expID)) {
        return expID;
      }
      
      // 默认返回1
      return '1';
    };
    
    // const k = getKFromExpID(expID);
    // console.log(`Loading data for k=${k} from URL parameter`);
    
    // 根据k值加载对应的state_k.json文件
    const loadStateFile = async () => {
      // 先设置expID，这样store在加载本地数据后能调用API获取最大步数
      replayStore.expID = expID;

      // 直接读取所有的
      for(let k=1;k<=10;k++){
        try {
        // 传递包含state_k.json的路径，让store.ts解析文件名
        const localDataPath = `/enterprise/data/state_${k}.json`;
        console.log(`Loading state file: state_${k}.json`);
        await replayStore.loadLocalData(localDataPath);
        
        console.log(`Successfully loaded state_${k}.json`);
        } catch (error) {
          console.error(`Failed to load state_${k}.json:`, error);
          // 如果加载本地数据失败，尝试使用远程数据
          replayStore.init(expID);
        }
      }
    };
    
    loadStateFile();

    //测试获取实验的接口
    (async () => {
        try {
            let response = await Api.getExperiments(expID)
            console.log("getExperiments response",response)
        } catch (e) {
          console.log("getExperiments e",e)
        }
    })();

  }, [expID]);



  // 初始化时选择第一个agent（如果有）
  useEffect(() => {
    if (replayStore.agents.size > 0 && !replayStore.clickedAgentID) {
      // 获取第一个agent的ID
      const firstAgentId = Array.from(replayStore.agents.keys())[0];
      replayStore.setClickedAgentID(firstAgentId);
    }
  }, [replayStore.agents]);
  
  // 切换全局提示信息的显示/隐藏
  const toggleGlobalPrompt = () => {
    setShowGlobalPrompt(!showGlobalPrompt);
  };

return (
  <div className="replay-container" style={{
    display: 'flex',
    position: 'relative',
    height: '95vh',
    width: '100vw',
    overflow: 'hidden',
    boxSizing: 'border-box'
  }}>
    {/* 左侧信息面板 */}
    <div  style={{
      width: '23%',
      minWidth: '280px',
      maxWidth: '360px',
      height: '100%',
      overflow: 'auto',
      padding: '12px',
      boxSizing: 'border-box',
      zIndex: 1,
      backgroundColor: 'rgba(255, 255, 255, 0.9)',
      boxShadow: '2px 0 8px rgba(0, 0, 0, 0.1)'
    }}>
      <div className="panel-header">
        <Tooltip title="Agent Information">
          <InfoCircleOutlined />
        </Tooltip>
        <span style={{ marginLeft: '8px', fontWeight: 'bold' }}>Agent Information</span>
      </div>
      <div style={{
        flex: 1,               
        overflow: 'auto',      
        width: '100%'        
      }}>
        <InfoPanel exp_id={expID}/>
      </div>
    </div>

    {/* 中间图谱区域 */}
    <div style={{
      flex: 1,
      height: '100%',
      position: 'relative',
      minWidth: '40%'
    }}>
      <IndustryGraphDeck 
                  style={{ width: '100%', height: '100%', position: 'absolute', left: 0, top: 0 }} 
                  expId={expID} 
                />
    </div>

    {/* 右侧聊天面板 */}
    <div style={{
      width: '23%',
      minWidth: '280px',
      maxWidth: '360px',
      height: '100%',
      overflow: 'auto',
      padding: '12px',
      boxSizing: 'border-box',
      zIndex: 1,
      backgroundColor: 'rgba(255, 255, 255, 0.9)',
      boxShadow: '-2px 0 8px rgba(0, 0, 0, 0.1)'
    }}>
      <div className="panel-header">
        <Tooltip title="Communication">
          <CommentOutlined />
        </Tooltip>
        <span style={{ marginLeft: '8px', fontWeight: 'bold' }}>Communication</span>
      </div>
      <ChatBox exp_id={expID}/>
    </div>

    {/* 全局提示信息 TODO 更新实际的globalPrompt生成与获取 */}
    {/* {(replayStore.globalPrompt ?? "") !== "" && ( */}  
    {true && (
      <div style={{
        position: 'absolute',
        top: '15%',
        left: '50%',
        transform: 'translateX(-50%)',
        width: '60%',
        // backgroundColor: 'rgba(255, 255, 255, 0.9)',
        zIndex: 40,
      }}>
        <div 
          className="global-prompt-row" 
          onClick={toggleGlobalPrompt}
          style={{ 
            display: 'flex',              
            margin: 0,
            padding: 0,
            cursor: 'pointer',
          }}
        >
        <Title 
            level={5} 
            className={showGlobalPrompt ? '' : 'collapsed'} 
            style={{ 
              margin: -5, padding: 2,
              backgroundColor: 'rgba(247, 247, 247, 0.9)',
              border:"dashed 1px",
            }} 
          >
            Market Insight
        </Title>
        {showGlobalPrompt && (
          <p 
            className="global-prompt-inner" 
            style={{ 
              margin: '0 0 0 8px',  // 左侧加一点间距，防止文字粘在标题上
              padding: 0,
              fontSize: '14px' 
            }}
          >
            Market situation: currently the products with the highest market demand are product1, it is recommended to prioritize the stabilization of the product output chain
          </p>
        )}
    </div>
      </div>
    )}


    {/* 时间轴控制器 */}
    <div className='control-progress' style={{
      position: 'absolute',
      bottom: '20px',
      left: '50%',
      transform: 'translateX(-50%)',
      width: '60%',
      // minWidth: '400px',
      // maxWidth: '800px',
      zIndex: 10,
      borderRadius: '8px',
      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)'
    }}>
      <Card 
        bordered={false}
        className="timeline-card"
        style={{ borderRadius: '8px' }}
      >
        <TimelinePlayer initialInterval={1000} />
      </Card>
    </div>
  </div>
);
  });

const Page = () => {
  return (
    <StoreContext.Provider value={store}>
      <Replay />
    </StoreContext.Provider>
  );
}

export default Page;
