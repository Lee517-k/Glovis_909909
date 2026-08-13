import { useEffect, useState, useRef } from "react";
import { Col, Row, message, Button, Space, Popconfirm, Modal, Dropdown, Card, Typography, Tag, Tooltip } from 'antd';
import { parseT } from "../../components/util";
import { useNavigate } from "react-router-dom";
import React from "react";
import { Experiment, experimentStatusMap } from "../../components/type";
import { ProColumns, ProDescriptions, ProTable } from "@ant-design/pro-components";
import { ActionType } from "@ant-design/pro-table";
import { EllipsisOutlined, PlayCircleOutlined, InfoCircleOutlined, ExportOutlined, DeleteOutlined, PlusOutlined, ReloadOutlined } from "@ant-design/icons";

const { Title, Text } = Typography;

// 状态标签组件
const StatusTag = ({ status }: { status: number }) => {
  const statusConfig: Record<number, { color: string, text: string, icon?: React.ReactNode }> = {
    0: { color: 'default', text: 'Initializing' },
    1: { color: 'processing', text: 'Running', icon: <PlayCircleOutlined /> },
    2: { color: 'success', text: 'Finished' },
    3: { color: 'error', text: 'Error' },
  };

  const config = statusConfig[status] || statusConfig[0];

  return (
    <Tag color={config.color} icon={config.icon}>
      {config.text}
    </Tag>
  );
};

const Page = () => {
  const navigate = useNavigate();
  const [detail, setDetail] = useState<Experiment | null>(null);
  const actionRef = useRef<ActionType>();

  const columns: ProColumns<Experiment>[] = [
    { 
      title: 'ID', 
      dataIndex: 'id', 
      width: '10%',
      render: (text) => <Text copyable>{text}</Text>
    },
    { 
      title: 'Name', 
      dataIndex: 'name', 
      width: '15%',
      render: (text) => <Text strong>{text}</Text>
    },
    {
      title: 'Status',
      dataIndex: 'status',
      width: '10%',
      valueEnum: experimentStatusMap,
      render: (_, record) => <StatusTag status={record.status} />
    },
    { 
      title: 'Progress', 
      width: '15%', 
      search: false,
      render: (_, record) => (
        <Space>
          <Text>{record.cur_day}/{record.num_day} days</Text>
          <Text type="secondary">({parseT(record.cur_t)})</Text>
        </Space>
      )
    },
    { 
      title: 'Tokens', 
      width: '15%', 
      search: false,
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Text>Input: {record.input_tokens?.toLocaleString() || 0}</Text>
          <Text>Output: {record.output_tokens?.toLocaleString() || 0}</Text>
        </Space>
      )
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      width: '15%',
      valueType: "dateTime",
      search: false
    },
    {
      title: 'Action',
      width: '15%',
      search: false,
      render: (_, record) => {
        // copy record to avoid reference change
        record = { ...record };
        return (
          <Space size="small">
            <Tooltip title="Go to experiment">
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={() => navigate(`/exp/${record.id}`)}
                disabled={record.status === 0}
                shape="round"
              >
                View
              </Button>
            </Tooltip>
            
            <Dropdown
              menu={{
                items: [
                  {
                    key: 'detail',
                    label: 'View Details',
                    icon: <InfoCircleOutlined />,
                    onClick: () => setDetail(record)
                  },
                  {
                    key: 'export',
                    label: 'Export Data',
                    icon: <ExportOutlined />,
                    onClick: () => {
                      const url = `/api/experiments/${record.id}/export`
                      // use form post to download the file
                      const form = document.createElement('form');
                      form.action = url;
                      form.method = 'POST';
                      form.target = '_blank';
                      document.body.appendChild(form);
                      form.submit();
                      document.body.removeChild(form);
                    }
                  },
                  {
                    key: 'delete',
                    label: (
                      <Popconfirm
                        title="Delete this experiment?"
                        description="This action cannot be undone."
                        onConfirm={async () => {
                          try {
                            const res = await fetch(`/api/experiments/${record.id}`, {
                              method: 'DELETE',
                            })
                            if (res.ok) {
                              message.success('Experiment deleted successfully');
                              actionRef.current?.reload();
                            } else {
                              // Read the error message as text
                              const errMessage = await res.text();
                              throw new Error(errMessage);
                            }
                          } catch (err) {
                            message.error('Failed to delete experiment: ' + err);
                          }
                        }}
                        okText="Yes, delete it"
                        cancelText="Cancel"
                        okButtonProps={{ danger: true }}
                      >
                        <span style={{ color: '#ff4d4f' }}>Delete Experiment</span>
                      </Popconfirm>
                    ),
                    icon: <DeleteOutlined style={{ color: '#ff4d4f' }} />
                  }
                ]
              }}
            >
              <Button icon={<EllipsisOutlined />} shape="round" />
            </Dropdown>
          </Space>
        );
      },
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      {/* 添加回放数据入口卡片 */}
      {/* <Card
        className="replay-data-card"
        title={
          <Space size="middle">
            <Title level={4} style={{ margin: 0 }}>回放数据</Title>
            <Text type="secondary">查看示例回放数据</Text>
          </Space>
        }
        style={{ marginBottom: '24px' }}
        bordered={false}
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
          {Array.from({ length: 10 }, (_, i) => i + 1).map(num => (
            <Button
              key={num}
              type="primary"
              onClick={() => {
                // 设置本地存储，以便在Replay页面加载数据
                localStorage.setItem('localDataPath', `examples/enterprise/data/state_${num}.json`);
                // 导航到回放页面
                navigate(`/replay/demo-${num}`);
              }}
            >
              回放数据 {num}
            </Button>
          ))}
        </div>
      </Card> */}

      <Card 
        className="console-card"
        title={
          <Space size="middle">
            <Title level={4} style={{ margin: 0 }}>Experiment Console</Title>
            <Text type="secondary">Manage and monitor your simulation experiments</Text>
          </Space>
        }
        extra={
          <Space>
            <Button 
              type="primary" 
              icon={<PlusOutlined />} 
              onClick={() => navigate('/experiment/create')}
              shape="round"
            >
              New Experiment
            </Button>
            <Button 
              icon={<ReloadOutlined />} 
              onClick={() => actionRef.current?.reload()}
              shape="round"
            >
              Refresh
            </Button>
          </Space>
        }
        bordered={false}
      >
        <ProTable<Experiment>
          actionRef={actionRef}
          columns={columns}
          request={async (params) => {
            try {
              const res = await fetch('/api/experiments')
              let data = await res.json()
              data = data.data;
              if (params.name !== undefined && params.name !== '') {
                data = data.filter((d: Experiment) => d.name.includes(params.name))
              }
              if (params.id !== undefined && params.id !== '') {
                data = data.filter((d: Experiment) => d.id === params.id)
              }
              if (params.status !== undefined) {
                data = data.filter((d: Experiment) => d.status == params.status)
              }
              return { data, success: true };
            } catch (err) {
              console.error('Failed to fetch experiments:', err)
              return { data: [], success: false }
            }
          }}
          rowKey="id"
          columnEmptyText="-"
          search={{
            filterType: 'light',
          }}
          dateFormatter="string"
          headerTitle={false}
          options={{
            density: true,
            fullScreen: true,
            setting: true,
          }}
        />
      </Card>

      <Modal
        title={
          <Space>
            <InfoCircleOutlined />
            <span>Experiment Details</span>
          </Space>
        }
        width="70vw"
        open={detail !== null}
        onCancel={() => setDetail(null)}
        footer={[
          <Button key="close" onClick={() => setDetail(null)}>
            Close
          </Button>,
          detail && detail.status !== 0 && (
            <Button 
              key="view" 
              type="primary" 
              onClick={() => {
                navigate(`/exp/${detail.id}`);
                setDetail(null);
              }}
            >
              View Experiment
            </Button>
          )
        ]}
      >
        {detail && (
          <ProDescriptions<Experiment>
            column={2}
            title={<Title level={4}>{detail.name}</Title>}
            request={async () => ({
              success: true,
              data: detail,
            })}
            columns={[
              { title: 'ID', dataIndex: 'id', render: (text) => <Text copyable>{text}</Text> },
              { title: 'Name', dataIndex: 'name' },
              { title: 'Created At', dataIndex: 'created_at', valueType: 'dateTime' },
              { title: 'Updated At', dataIndex: 'updated_at', valueType: 'dateTime' },
              { title: 'Num Day', dataIndex: 'num_day' },
              { 
                title: 'Status', 
                dataIndex: 'status', 
                render: (_, record) => <StatusTag status={record.status} />
              },
              { title: 'Current Day', dataIndex: 'cur_day' },
              { title: 'Current Time', dataIndex: 'cur_t', render: (t: number) => parseT(t) },
              { 
                title: 'Configuration', 
                dataIndex: 'config', 
                span: 2, 
                valueType: 'jsonCode',
                contentStyle: { maxHeight: '400px', overflow: 'auto' }
              },
              { 
                title: 'Error', 
                dataIndex: 'error', 
                span: 2, 
                valueType: 'code',
                contentStyle: { maxHeight: '200px', overflow: 'auto' } 
              },
            ]}
          />
        )}
      </Modal>
    </div>
  );
}

export default Page;
