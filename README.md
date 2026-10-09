# 智能工单分流 Demo

一个可运行的 React + FastAPI + SQLite 工单分流项目。

## 功能

- 输入工单文本，调用 JEV 做结构化分流
- 支持工单类型、优先级、负责团队、处理动作、置信度
- 低置信度、高风险工单自动进入人工复核
- JEV 没有配置时使用内置 mock，方便先跑通页面
- 可选接入 OpenAI-compatible 普通大模型作为兜底
- 保存工单记录，并展示分流统计
- 支持配置 JEV URL、JEV Key、普通大模型中转站 URL、Key、Model

## 启动后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

如果暂时不填写 Key，JEV 会使用 mock 结果，页面仍然可以完整演示。

## 启动前端

另开一个终端：

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173。

## 模型配置

后端 `.env`：

```env
# JEV 官方 API
# 可填 https://api.typesafe.ai/v1 或 https://api.typesafe.ai/v1/systemone
JEV_API_URL=https://api.typesafe.ai/v1
JEV_API_KEY=
JEV_MODEL=jev-latest

# 可选的普通大模型兜底，默认按 OpenAI-compatible chat/completions 调用
LLM_ENABLED=false
LLM_BASE_URL=https://your-relay.example.com/v1
LLM_API_KEY=
LLM_MODEL=
```

说明：

- 右上角「JEV 已配置」只表示 `.env` 里填写了 URL 和 Key，不代表本次调用一定成功。
- 真正使用的模型来源看接口返回里的 `source`：
  - `jev`：JEV 官方 API
  - `llm_fallback`：普通大模型兜底
  - `mock`：本地规则模拟
- JEV 按官方 System One 协议调用：`state` + `questions`（choice / noul）。
- 如果 JEV 调用失败且开启了 `LLM_ENABLED=true`，会自动切换到大模型兜底，并在 `reason` 中附带失败原因。

## 目录

```text
ticket-router-demo/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── schemas.py
│   │   └── services/
│   ├── .env.example
│   └── requirements.txt
└── frontend/
    ├── src/
    ├── package.json
    └── vite.config.js
```
