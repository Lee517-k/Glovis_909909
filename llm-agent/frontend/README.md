修改代码内部分文件路径为自己对应文件的绝对路径，项目根目录下要修改的相关代码所在文件的相对路径

agentsociety\cityagent\memory_config.py

firmagentsql\config.py

examples\enterprise\config.yaml

config.yaml

---

运行实验

---

两个后端指令

项目目录下运行 agentsociety ui -c config.yaml 启动后端数据

进入examples/enterprise目录 uvicorn enterprise_Api:app --host localhost --port 8000 --reload

---

前端npm run dev

---

