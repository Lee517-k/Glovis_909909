import React, { useEffect, useRef, useState } from 'react';
import { Card, Spin, Select, Button, message, Tooltip, Space, Typography } from 'antd';
import { ReloadOutlined, FullscreenOutlined, ZoomInOutlined, ZoomOutOutlined } from '@ant-design/icons';
import G6, { Graph } from '@antv/g6';
import mapData from './map_data.json';

const { Title } = Typography;

const GraphMap: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const [loading, setLoading] = useState(true);
  const [layout, setLayout] = useState('force');
  const [fullscreen, setFullscreen] = useState(false);

  // 初始化图谱
  useEffect(() => {
    if (!containerRef.current) return;

    // 清理之前的图谱实例，防止重影
    if (graphRef.current) {
      graphRef.current.destroy();
      graphRef.current = null;
    }

    // 彻底清理容器DOM，防止重影
    if (containerRef.current) {
      containerRef.current.innerHTML = '';
    }

    // 设置节点和边的样式
    const nodeConfig = {
      citizen: {
        fill: '#91d5ff',
        stroke: '#1890ff',
        icon: 'user'
      },
      firm: {
        fill: '#b7eb8f',
        stroke: '#52c41a',
        icon: 'shop'
      },
      bank: {
        fill: '#ffe58f',
        stroke: '#faad14',
        icon: 'bank'
      },
      government: {
        fill: '#ffadd2',
        stroke: '#eb2f96',
        icon: 'crown'
      }
    };

    // 图谱配置
    const width = containerRef.current.scrollWidth;
    const height = containerRef.current.scrollHeight || 800;

    // 创建图谱实例
    const graph = new G6.Graph({
      container: containerRef.current,
      width,
      height,
      modes: {
        default: ['drag-canvas', 'zoom-canvas', 'drag-node', 'click-select']
      },
      layout: {
        type: layout,
        preventOverlap: true,
        linkDistance: 100,
        nodeStrength: -100,
        edgeStrength: 0.1,
        nodeSize: 30,
        alpha: 0.3,
        alphaDecay: 0.028,
        alphaMin: 0.01,
      },
      defaultNode: {
        size: 30,
        style: {
          fill: '#91d5ff',
          stroke: '#1890ff',
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
        labelCfg: {
          autoRotate: true,
          style: {
            fill: '#666',
            fontSize: 10,
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

    // 注册节点
    G6.registerNode(
      'custom-node',
      {
        draw(cfg, group) {
          const { id, label, type = 'citizen', size = 30 } = cfg as any;
          const config = nodeConfig[type] || nodeConfig.citizen;
          
          const keyShape = group.addShape('circle', {
            attrs: {
              x: 0,
              y: 0,
              r: size / 2,
              fill: config.fill,
              stroke: config.stroke,
              lineWidth: 2,
            },
            name: 'node-keyshape',
          });

          // 添加文本标签
          group.addShape('text', {
            attrs: {
              text: label,
              x: 0,
              y: size / 2 + 10,
              textAlign: 'center',
              textBaseline: 'top',
              fill: '#666',
              fontSize: 12,
            },
            name: 'node-label',
          });

          return keyShape;
        },
      },
      'circle',
    );

    // 数据处理
    const processedData = {
      nodes: mapData.nodes.map(node => ({
        ...node,
        type: 'custom-node',
        style: {
          ...nodeConfig[node.type],
        },
      })),
      edges: mapData.edges,
    };

    // 加载数据
    graph.data(processedData);
    graph.render();
    graphRef.current = graph;
    setLoading(false);

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
      graph.destroy();
    };
  }, [layout]);

  // 切换布局
  const handleLayoutChange = (value: string) => {
    setLayout(value);
  };

  // 重新加载图谱
  const handleReload = () => {
    if (graphRef.current) {
      setLoading(true);
      setTimeout(() => {
        graphRef.current?.layout();
        graphRef.current?.fitView();
        setLoading(false);
      }, 100);
    }
  };

  // 切换全屏
  const toggleFullscreen = () => {
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
      const currentZoom = graphRef.current.getZoom();
      graphRef.current.zoomTo(currentZoom * 1.2);
    }
  };

  // 缩小
  const zoomOut = () => {
    if (graphRef.current) {
      const currentZoom = graphRef.current.getZoom();
      graphRef.current.zoomTo(currentZoom / 1.2);
    }
  };

  return (
    <Card
      title={<Title level={4}>Agent Society Graph</Title>}
      style={{
        width: '100%',
        height: fullscreen ? '100vh' : 'calc(100vh - 150px)',
        position: fullscreen ? 'fixed' : 'relative',
        top: fullscreen ? 0 : 'auto',
        left: fullscreen ? 0 : 'auto',
        zIndex: fullscreen ? 1000 : 1,
      }}
      extra={
        <Space>
          <Select
            defaultValue={layout}
            style={{ width: 120 }}
            onChange={handleLayoutChange}
            options={[
              { value: 'force', label: 'Force Layout' },
              { value: 'radial', label: 'Radial Layout' },
              { value: 'circular', label: 'Circular Layout' },
              { value: 'grid', label: 'Grid Layout' },
            ]}
          />
          <Tooltip title="Reload">
            <Button icon={<ReloadOutlined />} onClick={handleReload} />
          </Tooltip>
          <Tooltip title="Zoom In">
            <Button icon={<ZoomInOutlined />} onClick={zoomIn} />
          </Tooltip>
          <Tooltip title="Zoom Out">
            <Button icon={<ZoomOutOutlined />} onClick={zoomOut} />
          </Tooltip>
          <Tooltip title={fullscreen ? "Exit Fullscreen" : "Fullscreen"}>
            <Button icon={<FullscreenOutlined />} onClick={toggleFullscreen} />
          </Tooltip>
        </Space>
      }
    >
      <Spin spinning={loading} tip="Loading graph...">
        <div
          ref={containerRef}
          style={{
            width: '100%',
            height: fullscreen ? 'calc(100vh - 64px)' : 'calc(100vh - 214px)',
            background: '#fff',
          }}
        />
      </Spin>
    </Card>
  );
};

export default GraphMap;