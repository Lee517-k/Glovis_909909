# Neo4j使用指南

### 1.配置虚拟环境

venv环境或者conda环境，激活环境之后，在指令台使用pip install neo4j

### 2.启动neo4j服务

启动neo4j服务，并创建或者打开一个DBMS数据库，记住密码和进入的地址，端口号，用户名

项目默认地址为bolt://localhost:7687

用户名为neo4j      密码为12345678

### 3.项目结构

|           文件名            |                             作用                             |
| :-------------------------: | :----------------------------------------------------------: |
| industry_chain_generator.py | 通过输入企业数量和企业层级数自动生成企业信息，自动分级，自动生成供应关系 |
|   neo4j_industry-chain.py   |             通过读取industry_test.json中企业信息             |
|     industry_test.json      |                      存储生成的企业信息                      |
|           run.py            |                    集成上述函数，统一调用                    |

### 4.使用注意

1. 在neo4j_industry-chain.py的全局变量中定义有neo4j的uri，user和password，部分信息视情况进行更换。
2. industry_chain_generator.py和neo4j_industry-chain.py可以单独使用
3. 统一使用，直接运行run.py

