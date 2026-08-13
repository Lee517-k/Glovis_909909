 ## 依赖安装
根目录下 
pip install . -e

## 项目运行
docker目录下运行docker compose -f ./docker-compose-cn.yml up -d启动
该目录下python main.py
同步在data目录下生成数据

## 后端数据
项目目录下运行 agentsociety ui -c config.yaml 启动后端数据


## 前端
需要npm install 最新组件
在frontend 目录下运行npm run dev


## 后端运行
SupplyChainAgent/enterprise目录
uvicorn enterprise_Api:app --host localhost --port 8000 --reload
运行成功后可在对应端口获取
例如
http://127.0.0.1:8000/api/state/1

## API——KEY
安装依赖
pip install python-dotenv
在根目录创建/更新.env文件  输入OPENAI_API_KEY=XXXXXXXXXXXXXXX


## agent运行
PYTHONPATH=/home/cuda/agentsociety-enterprise venv/bin/python SupplyChainAgent/enterprise/main.py

为确保运行，还需补充config中的map信息（实际未使用），从可[AgentSociety官网](https://agentsociety.fiblab.net/ "AgentSociety官网")内的地图页面下载获取map文件