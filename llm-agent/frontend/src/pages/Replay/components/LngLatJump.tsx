import { useState } from "react";
import { Button, Input, Popover, Space, Tooltip, Typography } from "antd";
import { LngLat } from "./type";
import React from "react";
import { EnvironmentOutlined, SendOutlined } from "@ant-design/icons";

const { Text } = Typography;

const LngLatJump = (props: {
    onFlyTo: (location: LngLat) => void;
}) => {
    const [lng, setLng] = useState<number | undefined>(undefined);
    const [lat, setLat] = useState<number | undefined>(undefined);

    const handleConfirm = () => {
        if (lng !== undefined && lat !== undefined) {
            props.onFlyTo({ lng, lat });
        }
    };

    const lnglatInput = (
        <div className="lnglat-input-container">
            <Text strong style={{ marginBottom: '8px', display: 'block' }}>
                Enter coordinates to navigate
            </Text>
            <Space direction="vertical" style={{ width: '100%' }}>
                <Input
                    prefix={<Text type="secondary">Lng:</Text>}
                    placeholder="Longitude"
                    onChange={(e) => setLng(parseFloat(e.target.value))}
                    onPressEnter={handleConfirm}
                />
                <Input
                    prefix={<Text type="secondary">Lat:</Text>}
                    placeholder="Latitude"
                    onChange={(e) => setLat(parseFloat(e.target.value))}
                    onPressEnter={handleConfirm}
                />
                <Button 
                    onClick={handleConfirm} 
                    type="primary"
                    icon={<SendOutlined />}
                    block
                >
                    Navigate
                </Button>
            </Space>
        </div>
    );

    return (
        <div className="lnglat-jump">
            <Tooltip title="Navigate to coordinates">
                <Popover 
                    placement="bottom" 
                    content={lnglatInput} 
                    trigger="click"
                    title="Map Navigation"
                >
                    <Button 
                        icon={<EnvironmentOutlined />} 
                        type="text" 
                        className="map-control-button"
                    />
                </Popover>
            </Tooltip>
        </div>
    );
};

export default LngLatJump;