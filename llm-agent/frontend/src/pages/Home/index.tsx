import React, { useState, useEffect } from 'react';
import { Typography, Button, Space, Row, Col, Card, Divider, Statistic } from 'antd';
import { GithubOutlined, RocketOutlined, BookOutlined, ExperimentOutlined, TeamOutlined, DeploymentUnitOutlined, BarChartOutlined, GlobalOutlined } from '@ant-design/icons';
import { Link } from 'react-router-dom';

const { Title, Text, Paragraph } = Typography;

// 特性卡片组件
const FeatureCard = ({ icon, title, description }: { icon: React.ReactNode, title: string, description: string }) => (
  <Card 
    hoverable 
    style={{ height: '100%', borderRadius: '12px' }}
    bodyStyle={{ height: '100%', display: 'flex', flexDirection: 'column' }}
  >
    <div style={{ fontSize: '32px', color: 'var(--primary-color)', marginBottom: '16px' }}>
      {icon}
    </div>
    <Title level={4}>{title}</Title>
    <Paragraph style={{ flex: 1 }}>{description}</Paragraph>
  </Card>
);

const HomePage = () => {
  const [stars, setStars] = useState(0);

  useEffect(() => {
    fetch('https://api.github.com/repos/tsinghua-fib-lab/agentsociety')
      .then(res => res.json())
      .then(data => setStars(data.stargazers_count))
      .catch(() => setStars(0));
  }, []);

  return (
    <div style={{ width: '100%', maxWidth: '1200px', margin: '0 auto', padding: '40px 20px' }}>
      {/* 顶部新闻条 */}
      <Row justify="center" style={{ marginBottom: '40px' }}>
        <Link to="https://agentsociety.readthedocs.io/en/latest/02-version-1.3/01.v1.3.0.html">
          <div style={{
            background: 'rgba(255, 255, 255, 0.2)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            padding: '10px 20px',
            borderRadius: '32px',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            transition: 'transform 0.3s',
            cursor: 'pointer',
          }}
          onMouseEnter={(e) => e.currentTarget.style.transform = 'translateY(-3px)'}
          onMouseLeave={(e) => e.currentTarget.style.transform = 'translateY(0)'}
          >
            <div
              style={{
                backgroundColor: '#F28F0D',
                color: 'white',
                borderRadius: '16px',
                padding: '4px 12px',
                marginRight: '16px',
                fontWeight: 'bold',
              }}
            >What's New</div>
            <div style={{ color: 'white' }}>
              Release v1.3.0. Click here to view the release notes.
            </div>
          </div>
        </Link>
      </Row>

      {/* 主标题和副标题 */}
      <div style={{ textAlign: 'center', marginBottom: '60px' }}>
        <Title 
          style={{
            color: 'white',
            fontSize: '4.5rem',
            fontWeight: 600,
            marginBottom: '16px',
            textShadow: '0 2px 10px rgba(0,0,0,0.2)',
          }}
        >
          AgentSupplyChain
        </Title>
        <Text
          style={{
            color: 'white',
            fontSize: '1.5rem',
            lineHeight: 1.8,
            display: 'block',
            marginBottom: '40px',
          }}
        >
          Intelligent Supply Chain Management with <strong><em>AI-Powered Agent Networks</em></strong> <br />
          and <strong><em>Real-time Supply Chain Optimization</em></strong>
        </Text>

        {/* 按钮组 */}
        <Space size="large" style={{ marginBottom: '60px' }}>
          <Link to="/console">
            <Button
              type="primary"
              size="large"
              icon={<RocketOutlined />}
              style={{
                height: '56px',
                padding: '0 40px',
                fontSize: '18px',
                fontWeight: 'bold',
                borderRadius: '28px',
                boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
              }}
            >
              Get Started
            </Button>
          </Link>

          <Link to="https://github.com/tsinghua-fib-lab/agentsociety" target="_blank">
            <Button
              icon={<GithubOutlined />}
              size="large"
              style={{
                height: '56px',
                padding: '0 32px',
                fontSize: '18px',
                borderRadius: '28px',
                background: 'rgba(255, 255, 255, 0.2)',
                borderColor: 'white',
                color: 'white',
              }}
            >
              GitHub {stars > 0 && `(${stars} ★)`}
            </Button>
          </Link>

          <Link to="https://agentsociety.readthedocs.io/en/latest/" target="_blank">
            <Button
              icon={<BookOutlined />}
              size="large"
              style={{
                height: '56px',
                padding: '0 32px',
                fontSize: '18px',
                borderRadius: '28px',
                background: 'rgba(255, 255, 255, 0.2)',
                borderColor: 'white',
                color: 'white',
              }}
            >
              Documentation
            </Button>
          </Link>
        </Space>
      </div>

      {/* 特性部分 */}
      <div style={{ background: 'rgba(255, 255, 255, 0.9)', padding: '60px 40px', borderRadius: '16px', marginBottom: '60px' }}>
        <Title level={2} style={{ textAlign: 'center', marginBottom: '40px' }}>Key Features</Title>
        
        <Row gutter={[24, 24]}>
          <Col xs={24} md={8}>
            <FeatureCard 
              icon={<DeploymentUnitOutlined />}
              title="Intelligent Agent Network"
              description="Deploy AI-powered agents across your supply chain to automate decision-making, optimize inventory, and coordinate operations."
            />
          </Col>
          <Col xs={24} md={8}>
            <FeatureCard 
              icon={<BarChartOutlined />}
              title="Real-time Analytics"
              description="Monitor supply chain performance with advanced analytics, predictive insights, and automated reporting dashboards."
            />
          </Col>
          <Col xs={24} md={8}>
            <FeatureCard 
              icon={<GlobalOutlined />}
              title="Global Supply Chain"
              description="Manage complex multi-tier supply networks with real-time visibility, risk assessment, and optimization algorithms."
            />
          </Col>
        </Row>
      </div>

      {/* 统计数据 */}
      <div style={{ background: 'rgba(255, 255, 255, 0.9)', padding: '40px', borderRadius: '16px', marginBottom: '60px' }}>
        <Title level={3} style={{ textAlign: 'center', marginBottom: '40px' }}>Supply Chain Performance</Title>
        
        <Row gutter={48} justify="center">
          <Col span={6}>
            <Statistic title="Active Suppliers" value="500+" valueStyle={{ color: 'var(--primary-color)' }} />
          </Col>
          <Col span={6}>
            <Statistic title="Daily Transactions" value="50,000+" valueStyle={{ color: 'var(--primary-color)' }} />
          </Col>
          <Col span={6}>
            <Statistic title="Cost Reduction" value="25%" suffix="avg" valueStyle={{ color: 'var(--primary-color)' }} />
          </Col>
          <Col span={6}>
            <Statistic title="Delivery Accuracy" value="99.5%" valueStyle={{ color: 'var(--primary-color)' }} />
          </Col>
        </Row>
      </div>

      {/* 底部 */}
      <div style={{ textAlign: 'center', color: 'rgba(255, 255, 255, 0.8)', padding: '20px 0' }}>
        <Divider style={{ borderColor: 'rgba(255, 255, 255, 0.2)' }} />
        <Text style={{ color: 'rgba(255, 255, 255, 0.8)' }}>© {new Date().getFullYear()} AgentSupplyChain - Intelligent Supply Chain Management Platform</Text>
      </div>
    </div>
  );
};

export default HomePage;