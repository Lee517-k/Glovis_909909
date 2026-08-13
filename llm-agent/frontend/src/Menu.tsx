import { ExportOutlined, GithubOutlined, PlusOutlined, ExperimentOutlined, ApiOutlined, TeamOutlined, GlobalOutlined, NodeIndexOutlined, BookOutlined, QuestionCircleOutlined, EllipsisOutlined } from "@ant-design/icons";
import { Menu, MenuProps, Space, Dropdown, Button, Tooltip } from "antd";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

const RootMenu = ({ selectedKey }: {
    selectedKey: string
}) => {
    const [mlflowUrl, setMlflowUrl] = useState<string>("");

    useEffect(() => {
        fetch("/api/mlflow/url")
            .then(res => res.json())
            .then(res => {
                setMlflowUrl(res.data);
            });
    }, []);

    // Experiment submenu items
    const experimentItems: MenuProps['items'] = [
        {
            key: '/console',
            label: <Link to="/console">Console</Link>,
            icon: <ExperimentOutlined />,
        },
        {
            key: '/llms',
            label: <Link to="/llms">LLM Configs</Link>,
            icon: <ApiOutlined />,
        },
        // {
        //     key: '/graph',
        //     label: <Link to="/graph">Graph View</Link>,
        //     icon: <NodeIndexOutlined />,
        // },
        {
            key: '/industry',
            label: <Link to="/industry">Industry Chain</Link>,
            icon: <NodeIndexOutlined />,
        },
        {
            key: '/agents',
            label: <Link to="/agents">Agents</Link>,
            icon: <TeamOutlined />,
        },
        {
            key: '/workflows',
            label: <Link to="/workflows">Workflows</Link>,
            icon: <NodeIndexOutlined />,
        },
        {
            key: '/create-experiment',
            label: <Link to="/create-experiment">Create New</Link>,
            icon: <PlusOutlined />,
        },
    ];

    // 主菜单项
    const menuItems: MenuProps['items'] = [
        { 
            key: "/console", 
            label: (
                <Dropdown menu={{ items: experimentItems }} placement="bottomLeft" arrow>
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                        <ExperimentOutlined style={{ marginRight: 8 }} />
                        <span>Experiments</span>
                    </div>
                </Dropdown>
            ),
        },
    ];

    // 添加Survey菜单项
    menuItems.push({ 
        key: "/survey", 
        label: <Link to="/survey" style={{ display: 'flex', alignItems: 'center' }}>
            <QuestionCircleOutlined style={{ marginRight: 8 }} />
            <span>Survey</span>
        </Link> 
    });

    // 添加MLFlow菜单项（如果URL可用）
    if (mlflowUrl !== "") {
        menuItems.push({ 
            key: "/mlflow", 
            label: <Link to={mlflowUrl} rel="noopener noreferrer" target="_blank" style={{ display: 'flex', alignItems: 'center' }}>
                <ExportOutlined style={{ marginRight: 8 }} />
                <span>MLFlow</span>
            </Link> 
        });
    }

    // 添加Documentation菜单项
    // menuItems.push({ 
    //     key: "/Documentation", 
    //     label: <Link to="https://agentsociety.readthedocs.io/en/latest/" rel="noopener noreferrer" target="_blank" style={{ display: 'flex', alignItems: 'center' }}>
    //         <BookOutlined style={{ marginRight: 8 }} />
    //         <span>Docs</span>
    //     </Link> 
    // });
    
    // 添加GitHub菜单项
    // menuItems.push({ 
    //     key: "/Github", 
    //     label: <Link to="https://github.com/tsinghua-fib-lab/agentsociety/" rel="noopener noreferrer" target="_blank" style={{ display: 'flex', alignItems: 'center' }}>
    //         <GithubOutlined style={{ marginRight: 8 }} />
    //         <span>GitHub</span>
    //     </Link> 
    // });

    // 移动端适配：创建一个更多菜单，包含Survey、MLFlow、Docs和GitHub
    const moreMenuItems: MenuProps['items'] = [
        { 
            key: "/survey-more", 
            label: <Link to="/survey" style={{ display: 'flex', alignItems: 'center' }}>
                <QuestionCircleOutlined style={{ marginRight: 8 }} />
                <span>Survey</span>
            </Link> 
        },
    ];
    
    // 添加MLFlow到更多菜单（如果URL可用）
    if (mlflowUrl !== "") {
        moreMenuItems.push({ 
            key: "/mlflow-more", 
            label: <Link to={mlflowUrl} rel="noopener noreferrer" target="_blank" style={{ display: 'flex', alignItems: 'center' }}>
                <ExportOutlined style={{ marginRight: 8 }} />
                <span>MLFlow</span>
            </Link> 
        });
    }
    
    // 添加Documentation到更多菜单
    moreMenuItems.push({ 
        key: "/Documentation-more", 
        label: <Link to="https://agentsociety.readthedocs.io/en/latest/" rel="noopener noreferrer" target="_blank" style={{ display: 'flex', alignItems: 'center' }}>
            <BookOutlined style={{ marginRight: 8 }} />
            <span>Docs</span>
        </Link> 
    });
    
    // 添加GitHub到更多菜单
    moreMenuItems.push({ 
        key: "/Github-more", 
        label: <Link to="https://github.com/tsinghua-fib-lab/agentsociety/" rel="noopener noreferrer" target="_blank" style={{ display: 'flex', alignItems: 'center' }}>
            <GithubOutlined style={{ marginRight: 8 }} />
            <span>GitHub</span>
        </Link> 
    });
    
    // 检查窗口宽度，如果小于特定值，则使用更多菜单
    const [useMoreMenu, setUseMoreMenu] = useState(window.innerWidth < 768);
    
    useEffect(() => {
        const handleResize = () => {
            setUseMoreMenu(window.innerWidth < 768);
        };
        
        window.addEventListener('resize', handleResize);
        return () => {
            window.removeEventListener('resize', handleResize);
        };
    }, []);
    
    // 如果使用更多菜单，则添加一个下拉菜单
    if (useMoreMenu) {
        // 移除原来的菜单项
        const experimentItem = menuItems[0]; // 保留Experiments菜单项
        menuItems.length = 0;
        menuItems.push(experimentItem);
        
        // 添加更多菜单
        menuItems.push({
            key: "/more",
            label: (
                <Dropdown menu={{ items: moreMenuItems }} placement="bottomRight" arrow>
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                        <EllipsisOutlined style={{ marginRight: 8 }} />
                        <span>更多</span>
                    </div>
                </Dropdown>
            ),
        });
    }
    
    return (
        <Menu
            theme="dark"
            mode="horizontal"
            items={menuItems}
            selectedKeys={[selectedKey]}
            style={{ background: 'transparent', border: 'none' }}
        />
    );
};

export default RootMenu;
