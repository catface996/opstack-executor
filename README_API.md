# HTTP API 接口 - 层级多智能体系统

## 概述

本项目提供了一个 HTTP API 接口，允许通过 RESTful API 动态创建和执行层级多智能体系统。该 API 完全基于 AWS 原生服务构建，兼容 AWS Bedrock Agent Core 部署要求。

## 快速开始

### 1. 部署到 AWS

```bash
# 安装依赖
pip install aws-sam-cli

# 构建和部署
./deploy.sh
```

### 2. 测试 API

```bash
# 健康检查
curl https://your-api-endpoint.com/prod/health

# 执行任务
curl -X POST https://your-api-endpoint.com/prod/execute \
  -H "Content-Type: application/json" \
  -d @examples/simple_request.json
```

### 3. 本地测试

```bash
# 设置 API Key
export AWS_BEDROCK_API_KEY='your-api-key'

# 运行测试脚本
python test_api.py
```

## 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                          客户端应用                               │
│                   (Web App / Mobile / CLI)                       │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP Request (JSON)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Gateway (REST API)                      │
│                     - CORS 支持                                   │
│                     - API Key 认证 (可选)                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Lambda Function (Python 3.12)                  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 1. 解析配置 JSON                                            │ │
│  │    - Global Supervisor 配置                                 │ │
│  │    - Team Supervisor 配置                                   │ │
│  │    - Worker Agent 配置                                      │ │
│  └────────────────────────────────────────────────────────────┘ │
│                             │                                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 2. 创建层级拓扑                                             │ │
│  │    - HierarchyBuilder                                       │ │
│  │    - GlobalSupervisorFactory                                │ │
│  │    - TeamSupervisorFactory                                  │ │
│  │    - WorkerAgentFactory                                     │ │
│  └────────────────────────────────────────────────────────────┘ │
│                             │                                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 3. 执行任务                                                 │ │
│  │    - ExecutionTracker (追踪执行状态)                        │ │
│  │    - CallTracker (记录调用历史)                             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                             │                                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 4. 生成流式响应                                             │ │
│  │    - 拓扑信息 (TeamId, SupervisorId, WorkerId)              │ │
│  │    - 执行事件流                                             │ │
│  │    - 最终结果                                                │ │
│  └────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   AWS Bedrock (LLM Service)                      │
│                  Claude Sonnet 4 (或其他模型)                     │
└─────────────────────────────────────────────────────────────────┘
```

## 核心特性

### 1. 动态拓扑创建

通过 JSON 配置动态创建三层智能体架构：

```
Global Supervisor (全局协调者)
    ├── Team Supervisor 1 (团队主管)
    │   ├── Worker Agent 1.1
    │   └── Worker Agent 1.2
    └── Team Supervisor 2
        ├── Worker Agent 2.1
        └── Worker Agent 2.2
```

### 2. 流式响应

返回完整的执行事件流，包含拓扑元数据：

```json
{
  "event_type": "worker_completed",
  "timestamp": "2025-12-10T15:30:10.000Z",
  "data": {
    "worker_name": "量子理论专家",
    "result_preview": "..."
  },
  "topology_metadata": {
    "team_id": "team_xyz-456-uvw",
    "supervisor_id": "supervisor_team_xyz-456-uvw",
    "worker_id": "worker_mno-789-pqr"
  }
}
```

### 3. 执行模式

支持两种执行模式：

- **顺序执行** (Sequential): 团队按顺序依次执行，适合有依赖关系的任务
- **并行执行** (Parallel): 团队同时执行，适合独立任务，提高效率

### 4. 上下文共享

支持团队间上下文共享：

- 后续团队可以访问前面团队的执行结果
- 可配置哪些团队接收上下文
- 全局开关控制是否启用

### 5. AWS Bedrock Agent Core 兼容

完全兼容 AWS Bedrock Agent Core 部署要求：

- 标准 REST API 接口
- JSON 格式请求和响应
- 事件流式输出
- AWS 原生服务集成

## API 端点

### 1. 健康检查

```
GET /health
```

### 2. 执行智能体系统

```
POST /execute
```

**请求体:**

```json
{
  "global_prompt": "全局协调者的系统提示词",
  "teams": [
    {
      "name": "团队名称",
      "supervisor_prompt": "团队主管的系统提示词",
      "workers": [
        {
          "name": "Worker 名称",
          "role": "Worker 角色",
          "system_prompt": "Worker 的系统提示词",
          "tools": ["calculator", "http_request"]
        }
      ]
    }
  ],
  "task": "要执行的任务描述",
  "execution_mode": "sequential",  // 或 "parallel"
  "enable_context_sharing": false
}
```

**响应:**

```json
{
  "success": true,
  "topology": {
    "global_supervisor_id": "global_xxx",
    "teams": [...]
  },
  "events": [...],
  "result": "执行结果",
  "statistics": {...}
}
```

## 文件结构

```
hierarchical-agents/
├── lambda_handler.py          # Lambda 函数入口
├── hierarchy_executor.py      # 层级执行器
├── api_models.py             # API 数据模型
├── hierarchy_system.py       # 核心系统（现有）
├── config.py                 # 配置管理（现有）
├── template.yaml             # AWS SAM 模板
├── requirements.txt          # Python 依赖
├── deploy.sh                 # 部署脚本
├── test_api.py               # API 测试脚本
├── examples/                 # 请求示例
│   ├── simple_request.json
│   └── multi_team_parallel_request.json
└── docs/
    ├── API_DEPLOYMENT.md     # 部署指南
    └── API_REFERENCE.md      # API 参考文档
```

## 部署

### 前置条件

- AWS CLI 已安装并配置
- AWS SAM CLI 已安装
- Python 3.12+
- 有效的 AWS Bedrock API Key

### 部署步骤

1. **克隆仓库**

```bash
cd /projects/sandbox/hierarchical-agents
```

2. **运行部署脚本**

```bash
./deploy.sh
```

3. **输入配置参数**

按照提示输入：
- Stack Name
- AWS Region
- Bedrock API Key
- 其他参数

4. **获取 API 端点**

部署成功后，记录输出的 API 端点 URL。

### 本地测试

使用 SAM Local 在本地运行 API：

```bash
# 启动本地 API
sam local start-api

# 在另一个终端测试
curl -X POST http://127.0.0.1:3000/execute \
  -H "Content-Type: application/json" \
  -d @examples/simple_request.json
```

## 使用示例

### 示例 1: 简单研究任务

```bash
curl -X POST https://your-api-endpoint.com/prod/execute \
  -H "Content-Type: application/json" \
  -d '{
    "global_prompt": "你是研究中心的首席科学家。",
    "teams": [
      {
        "name": "理论研究团队",
        "supervisor_prompt": "你是理论研究团队的负责人。",
        "workers": [
          {
            "name": "理论专家",
            "role": "理论研究",
            "system_prompt": "你是理论物理专家。",
            "tools": ["calculator"]
          }
        ]
      }
    ],
    "task": "分析量子纠缠现象"
  }'
```

### 示例 2: 多团队协作

使用预定义的配置文件：

```bash
curl -X POST https://your-api-endpoint.com/prod/execute \
  -H "Content-Type: application/json" \
  -d @examples/multi_team_parallel_request.json
```

### 示例 3: Python 客户端

```python
import requests

response = requests.post(
    "https://your-api-endpoint.com/prod/execute",
    json={
        "global_prompt": "你是AI研究中心的首席科学家。",
        "teams": [...],
        "task": "研究大语言模型的涌现能力",
        "execution_mode": "parallel"
    }
)

result = response.json()
print(f"成功: {result['success']}")
print(f"结果: {result['result']}")
```

## 配置参数

### 全局配置

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `global_prompt` | string | 是 | - | 全局协调者提示词 |
| `teams` | array | 是 | - | 团队配置列表 |
| `task` | string | 是 | - | 任务描述 |
| `execution_mode` | string | 否 | "sequential" | 执行模式 |
| `enable_context_sharing` | boolean | 否 | false | 上下文共享 |

### 团队配置

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `name` | string | 是 | - | 团队名称 |
| `supervisor_prompt` | string | 是 | - | 主管提示词 |
| `workers` | array | 是 | - | Worker 列表 |
| `share_context` | boolean | 否 | false | 接收上下文 |

### Worker 配置

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `name` | string | 是 | - | Worker 名称 |
| `role` | string | 是 | - | Worker 角色 |
| `system_prompt` | string | 是 | - | 系统提示词 |
| `tools` | array | 否 | [] | 工具列表 |

详细配置说明请参考 [API Reference](docs/API_REFERENCE.md)。

## 监控和日志

### CloudWatch Logs

查看 Lambda 函数日志：

```bash
sam logs -n HierarchicalAgentsFunction --tail
```

### CloudWatch Metrics

在 AWS 控制台监控：
- Lambda 调用次数
- 错误率
- 执行时间
- 并发数

## 安全

### 当前实现

- API Key 存储在环境变量中
- CORS 已启用（支持跨域请求）
- CloudWatch 日志记录所有请求

### 生产环境建议

1. **API Key 认证**: 在 API Gateway 启用 API Key
2. **IAM 授权**: 使用 IAM 角色限制访问
3. **VPC 部署**: 将 Lambda 部署在 VPC 中
4. **加密**: 使用 Secrets Manager 存储敏感信息
5. **限流**: 配置 API Gateway 的使用计划和配额

## 性能优化

### Lambda 配置

根据实际负载调整：

```yaml
# template.yaml
Globals:
  Function:
    Timeout: 900       # 增加超时时间
    MemorySize: 3008   # 增加内存
```

### 并发控制

配置预留并发以处理高峰流量：

```bash
aws lambda put-function-concurrency \
  --function-name hierarchical-agents-api \
  --reserved-concurrent-executions 100
```

## 成本估算

### Lambda 成本示例

假设每月 10,000 次请求，每次 60 秒，2048 MB 内存：

- 请求费用: ~$0.002
- 计算费用: ~$20
- **总计**: ~$20/月

### API Gateway 成本

- REST API: $3.50 / 100万次请求

### Bedrock 成本

根据实际使用的 token 数量计费。

## 文档

- [API 参考文档](docs/API_REFERENCE.md) - 完整的 API 规范
- [部署指南](docs/API_DEPLOYMENT.md) - 详细的部署步骤
- [配置指南](docs/CONFIGURATION.md) - 系统配置说明

## 故障排查

### 常见问题

1. **Lambda 超时**
   - 增加超时配置
   - 减少任务复杂度
   - 使用并行执行模式

2. **内存不足**
   - 增加 Lambda 内存
   - 优化代码
   - 减少并发团队数

3. **Bedrock 限流**
   - 实现重试机制
   - 增加请求配额
   - 使用顺序执行

## 更新和维护

### 更新代码

```bash
# 修改代码
vim lambda_handler.py

# 重新部署
sam build
sam deploy
```

### 回滚

```bash
aws cloudformation rollback-stack \
  --stack-name hierarchical-agents-api
```

### 删除

```bash
sam delete
```

## 贡献

欢迎贡献！请：

1. Fork 项目
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 许可证

MIT License

## 联系方式

如有问题或建议，请通过以下方式联系：

- 提交 Issue
- 发送 Pull Request
- 查看文档

---

**版本**: 1.0.0  
**最后更新**: 2025-12-10  
**作者**: Built with ❤️ using Strands Agent SDK and AWS Services
