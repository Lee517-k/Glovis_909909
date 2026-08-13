import React, { useContext, useEffect, useRef, useState } from 'react';
import { Button, Flex, Select, Slider, SliderSingleProps, Space, Tooltip, Typography, Badge, InputNumber, message } from 'antd';
import { 
  PlayCircleOutlined, 
  PauseCircleOutlined, 
  FastForwardOutlined, 
  FastBackwardOutlined, 
  ReloadOutlined,
  ClockCircleOutlined,
  DashboardOutlined,
  EnterOutlined
} from '@ant-design/icons';
import { parseT } from '../../components/util';
import { observer } from 'mobx-react-lite';
import { StoreContext } from './store';
import { experimentStatusMap } from '../../components/type';
import FlickeringDot from '../../components/FlickeringDot';
import { Api } from '../../services/api';

const { Text } = Typography;

const TimelinePlayer = observer(({ initialInterval }: {
  initialInterval: number,
}) => {
  const store = useContext(StoreContext);

  const [isLiveMode, setIsLiveMode] = useState<boolean>(false);
  const [sliderChanging, setSliderChanging] = useState(false);
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playInterval, setPlayInterval] = useState<number>(initialInterval);
  const [jumpStep, setJumpStep] = useState<number | null>(null);
  const intervalRef = useRef<any>();

  // API数据状态
  const [apiTransactions, setApiTransactions] = useState([]);
  const [apiCommunications, setApiCommunications] = useState([]);
  const [apiMaxStep, setApiMaxStep] = useState<number>(0);

  const [currentTimeline, setCurrentTimeline] = useState(store.timeline[currentIndex] || { day: 0, t: 0 });

  // 当currentIndex变化时更新currentTimeline
  useEffect(() => {
    const newTimeline = store.timeline[currentIndex] || { day: 0, t: 0 };
    setCurrentTimeline(newTimeline);
  }, [currentIndex, store.timeline]);

  // 获取API数据并获取最大步数
  useEffect(() => {
    const fetchApiData = async () => {
      if (!store.expID) return;

      try {
        console.log('开始获取API数据，实验ID:', store.expID);
        const [transactionsRes, communicationsRes, maxStepRes] = await Promise.all([
          Api.getTransaction(store.expID),
          Api.getCommunications(store.expID),
          Api.getMaxStep(store.expID)
        ]);

        console.log('API调用结果:', {
          transactions: transactionsRes?.length || 0,
          communications: communicationsRes?.length || 0,
          maxStepResponse: maxStepRes
        });

        setApiTransactions(transactionsRes || []);
        setApiCommunications(communicationsRes || []);

        // 直接使用API返回的最大步数
        if (maxStepRes && typeof maxStepRes.max_step === 'number') {
          setApiMaxStep(maxStepRes.max_step);
          console.log('TimelinePlayer: API数据获取成功，最大步数:', maxStepRes.max_step, '交易记录:', transactionsRes?.length, '通信记录:', communicationsRes?.length);
        } else if (maxStepRes && typeof maxStepRes === 'object') {
          // 尝试其他可能的字段名
          const maxStep = maxStepRes.max_step || maxStepRes.maxStep || maxStepRes.total_steps;
          if (typeof maxStep === 'number') {
            setApiMaxStep(maxStep);
            console.log('TimelinePlayer: API数据获取成功（备用字段），最大步数:', maxStep, '原始数据:', maxStepRes);
          } else {
            console.log('TimelinePlayer: API返回的max-step数据格式不正确:', maxStepRes);
          }
        } else {
          // 如果API返回的数据格式不正确，回退到从交易和通信数据中计算
          const allSteps = [];

          // 从交易数据中提取步数
          if (transactionsRes && Array.isArray(transactionsRes)) {
            transactionsRes.forEach(t => {
              const step = t.step;
              if (typeof step === 'number' && step >= 0) {
                allSteps.push(step);
              }
            });
          }

          // 从通信数据中提取步数
          if (communicationsRes && Array.isArray(communicationsRes)) {
            communicationsRes.forEach(c => {
              const step = c.step;
              if (typeof step === 'number' && step >= 0) {
                allSteps.push(step);
              }
            });
          }

          const maxStep = allSteps.length > 0 ? Math.max(...allSteps) : 0;
          setApiMaxStep(maxStep);
          console.log('使用备用方法计算最大步数:', maxStep, '交易记录:', transactionsRes?.length, '通信记录:', communicationsRes?.length);
        }
      } catch (error) {
        console.error('获取API数据失败:', error);
      }
    };

    if (store.expID) {
      fetchApiData();
    }
  }, [store.expID]);

  // 计算最大步数，使用API数据
  const getMaxSteps = () => {
    if (apiMaxStep > 0) {
      return apiMaxStep;
    }
    return Math.max(0, store.timeline.length - 1);
  };



  // 前进到下一个时间点
  const nextIndex = () => {
    if (isLiveMode) {
      store.refresh().then(() => {
        setCurrentIndex(store.timeline.length - 1);
      });
    } else {
      if (currentIndex < getMaxSteps()) {
        setCurrentIndex(currentIndex + 1);
        console.log('Moving to next step:', currentIndex + 1);
      } else {
        clearInterval(intervalRef.current);
        setIsPlaying(false);
        console.log('Reached end of timeline, stopping playback');
      }
    }
  };

  // 回退到上一个时间点
  const prevIndex = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    }
  };

  // 步数跳转处理
  const handleJumpToStep = () => {
    if (jumpStep === null || jumpStep === undefined) {
      message.error('请输入有效的步数');
      return;
    }

    const maxStep = getMaxSteps();

    if (jumpStep < 0) {
      message.error('步数不能为负数');
      return;
    }

    if (jumpStep > maxStep) {
      message.error(`步数不能超过最大值 ${maxStep}`);
      return;
    }

    if (!Number.isInteger(jumpStep)) {
      message.error('步数必须是整数');
      return;
    }

    setCurrentIndex(jumpStep);
    setIsPlaying(false);
    message.success(`已跳转到步数 ${jumpStep}`);
  };

  // 播放控制
  useEffect(() => {
    if (isPlaying) {
      console.log('Starting playback with interval:', playInterval, 'ms');
      intervalRef.current = setInterval(() => {
        setCurrentIndex(prevIndex => {
          if (isLiveMode) {
            store.refresh().then(() => {
              setCurrentIndex(store.timeline.length - 1);
            });
            return prevIndex;
          } else {
            if (prevIndex < getMaxSteps()) {
              console.log('Auto advancing to step:', prevIndex + 1);
              return prevIndex + 1;
            } else {
              console.log('Reached end of timeline, stopping playback');
              setIsPlaying(false);
              return prevIndex;
            }
          }
        });
      }, playInterval);
    } else {
      console.log('Stopping playback');
      clearInterval(intervalRef.current);
    }
    return () => clearInterval(intervalRef.current);
  }, [isPlaying, playInterval, isLiveMode, store.timeline.length, apiMaxStep]);

  // 滑块变化处理
  const handleSliderChange = (value: number) => {
    setSliderChanging(true);
    setCurrentIndex(value);
    setIsPlaying(false);
    console.log('Slider changed to:', value, 'max:', getMaxSteps());
  };

  const handleSliderChangeEnd = (value: number) => {
    setSliderChanging(false);
    setCurrentIndex(value);
    console.log('Slider change ended at:', value, 'timeline length:', store.timeline.length, 'max steps:', getMaxSteps());
  }

  // 滑块提示格式化
  const formatter: NonNullable<SliderSingleProps['tooltip']>['formatter'] = (value) => {
    if (value === undefined) {
      return '';
    }
    // 直接使用滑块的value作为step值
    return `Step ${value}`;
  }

  // 时间点变化时获取数据
  useEffect(() => {
    if (!sliderChanging) {
      store.fetchByTime(currentTimeline);

      // 触发时间轴变化事件，通知其他组件更新
      // 直接使用currentIndex作为step值，确保步数正确传递
      const event = new CustomEvent('timelineChange', {
        detail: {
          step: currentIndex,
          day: currentTimeline.day,
          t: currentTimeline.t
        }
      });
      window.dispatchEvent(event);

      // 打印当前步骤信息，便于调试
      console.log('Timeline changed:', {
        step: currentIndex,
        index: currentIndex,
        totalSteps: getMaxSteps() + 1
      });
    }
  }, [currentTimeline, sliderChanging, store, currentIndex]);

  // 当实验是Completed状态时，禁用Live模式
  useEffect(() => {
    if (store.experiment?.status === 2) {
      setIsLiveMode(false);
    }
  }, [store.experiment?.status, store]);

  // 模式选项
  const modeOptions = [
    { value: 'Replay', label: 'Replay' },
  ];
  if (store.experiment?.status === 1) {
    modeOptions.push({ value: 'Live', label: 'Live' });
  }

  // 获取实验状态颜色
  const getStatusColor = () => {
    switch (store.experiment?.status) {
      case 0: return "#8c8c8c"; // 等待中
      case 1: return "#52c41a"; // 进行中
      case 2: return "#1677ff"; // 已完成
      default: return "#ff4d4f"; // 错误
    }
  };

  return (
    <div className="timeline-player">
      {/* 实验状态 */}
      <div className="player-section status-section">
        <Tooltip title={
          <span>
            {store.experiment?.name}: {experimentStatusMap[store.experiment?.status]}
          </span>
        }>
          <Badge
            status={store.experiment?.status === 1 ? "processing" : "default"}
            color={getStatusColor()}
            text={
              <Text strong>
                {experimentStatusMap[store.experiment?.status]}
              </Text>
            }
          />
        </Tooltip>
        <Button
          type="text"
          icon={<ReloadOutlined />}
          onClick={() => store.init(store.expID)}
          size="small"
        />
      </div>

      {/* 播放控制 */}
      <div className="player-section controls-section">
        <Button
          shape="circle"
          size="small"
          onClick={prevIndex}
          disabled={currentIndex === 0}
          icon={<FastBackwardOutlined />}
        />
        <Button
          shape="circle"
          type={isPlaying ? "primary" : "default"}
          onClick={() => setIsPlaying(!isPlaying)}
          icon={isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
        />
        <Button
          shape="circle"
          size="small"
          onClick={nextIndex}
          disabled={getMaxSteps() === 0 || currentIndex === getMaxSteps()}
          icon={<FastForwardOutlined />}
        />
      </div>

      {/* 步骤信息 */}
      <div className="player-section time-info">
        <DashboardOutlined />
        <Text strong>Step {currentIndex}</Text>
        <Badge
          count={currentIndex}
          style={{ backgroundColor: '#1677ff', marginLeft: '5px' }}
          size="small"
        />
      </div>

      {/* 时间轴滑块 */}
      <div className="player-section slider-section">
        <Slider
          min={0}
          max={getMaxSteps()}
          value={Math.min(currentIndex, getMaxSteps())}
          onChange={handleSliderChange}
          onChangeComplete={handleSliderChangeEnd}
          tooltip={{ formatter }}
          className="timeline-slider"
          marks={{
            0: { style: { color: '#1677ff' }, label: '开始' },
            [getMaxSteps()]: { style: { color: '#1677ff' }, label: '结束' }
          }}
        />

      </div>

      {/* 步数跳转 */}
      <div className="player-section jump-section">
        <InputNumber
          size="small"
          placeholder="步数"
          value={jumpStep}
          onChange={setJumpStep}
          min={0}
          max={getMaxSteps()}
          precision={0}
          style={{ width: 60 }}
          onPressEnter={handleJumpToStep}
        />
        <Button
          size="small"
          icon={<EnterOutlined />}
          onClick={handleJumpToStep}
          disabled={getMaxSteps() === 0}
          title="跳转到指定步数"
        />
      </div>

      {/* 播放速度 */}
      <div className="player-section speed-section">
        <DashboardOutlined />
        <Select
          value={playInterval}
          onChange={value => setPlayInterval(value)}
          size="small"
          className="speed-select"
          options={[
            { value: 10000, label: '10s/step' },
            { value: 5000, label: '5s/step' },
            { value: 2000, label: '2s/step' },
            { value: 1000, label: '1s/step' },
            { value: 500, label: '0.5s/step' },
            { value: 250, label: '0.25s/step' },
            { value: 100, label: '0.1s/step' },
          ]}
        />
      </div>



      {/* 模式选择 */}
      <div className="player-section mode-section">
        <Select
          value={isLiveMode ? "Live" : "Replay"}
          onChange={value => setIsLiveMode(value === "Live")}
          size="small"
          className="mode-select"
          options={modeOptions}
          disabled={store.experiment?.status !== 1}
        />
      </div>
    </div>
  );
});

export default TimelinePlayer;