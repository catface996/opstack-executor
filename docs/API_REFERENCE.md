# HTTP API 参考文档

本文档详细描述了层级多智能体系统 HTTP API 的所有端点、请求格式、响应格式和使用示例。

## 目录

- [概述](#概述)
- [基础 URL](#基础-url)
- [认证](#认证)
- [端点](#端点)
  - [健康检查](#健康检查)
  - [执行智能体系统](#执行智能体系统)
- [数据模型](#数据模型)
- [错误处理](#错误处理)
- [速率限制](#速率限制)
- [示例](#示例)

## 概述

层级多智能体系统 HTTP API 允许您通过 HTTP 请求动态创建和执行多层级的智能体系统。

**主要特性：**
- 动态创建 Global Supervisor、Team Supervisor 和 Worker Agent 拓扑
- 支持顺序和并行执行模式
- 提供实时事件流，包含拓扑元数据（TeamId, SupervisorId, WorkerId）
- 完全兼容 AWS Bedrock Agent Core

## 基础 URL

```
Production: https://<api-id>.execute-api.<region>.amazonaws.com/prod
Development: http://localhost:3000 (SAM Local)
```

## 认证

当前版本使用 AWS Bedrock API Key 进行认证。API Key 通过环境变量配置在 Lambda 函数中。

未来版本将支持：
- API Key 认证（通过 API Gateway）
- IAM 授权
- OAuth 2.0

## 端点

### 健康检查

检查服务健康状态。

**端点:** `GET /health`

**请求示例:**

```bash
curl https://your-api-endpoint.com/prod/health
```

**响应示例:**

```json
{
  "status": "healthy",
  "service": "hierarchical-agents-api",
  "version": "1.0.0"
}
```

**状态码:**
- `200 OK` - 服务正常运行

---

### 执行智能体系统

根据提供的配置动态创建智能体层级结构并执行任务。

**端点:** `POST /execute`

**Content-Type:** `application/json`

**请求体结构:**

```json
{
  "global_prompt": "string (required)",
  "teams": [TeamConfig] (required),
  "task": "string (required)",
  "execution_mode": "sequential" | "parallel" (optional, default: "sequential"),
  "enable_context_sharing": boolean (optional, default: false)
}
```

**响应结构:**

```json
{
  "success": boolean,
  "topology": TopologyInfo,
  "events": [StreamEvent],
  "result": "string",
  "error": "string | null",
  "statistics": object
}
```

**状态码:**
- `200 OK` - 执行成功
- `400 Bad Request` - 请求格式错误
- `500 Internal Server Error` - 服务器内部错误

## 数据模型

### HierarchyConfigRequest

顶层配置对象。

```typescript
interface HierarchyConfigRequest {
  global_prompt: string;           // 全局协调者的系统提示词
  teams: TeamConfig[];             // 团队配置列表
  task: string;                    // 要执行的任务描述
  execution_mode?: "sequential" | "parallel";  // 执行模式，默认 "sequential"
  enable_context_sharing?: boolean;  // 是否启用团队间上下文共享，默认 false
}
```

**字段说明：**

| 字段 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `global_prompt` | string | 是 | - | 全局协调者的系统提示词，定义全局协调者的角色和职责 |
| `teams` | array | 是 | - | 团队配置列表，至少包含一个团队 |
| `task` | string | 是 | - | 要执行的任务描述 |
| `execution_mode` | string | 否 | "sequential" | 执行模式：sequential（顺序）或 parallel（并行） |
| `enable_context_sharing` | boolean | 否 | false | 是否启用团队间上下文共享 |

---

### TeamConfig

团队配置对象。

```typescript
interface TeamConfig {
  name: string;                    // 团队名称
  supervisor_prompt: string;       // 团队主管的系统提示词
  workers: WorkerConfig[];         // Worker 配置列表
  id?: string;                     // 团队 ID（可选，自动生成）
  prevent_duplicate?: boolean;     // 是否防止重复调用，默认 true
  share_context?: boolean;         // 是否接收其他团队的上下文，默认 false
}
```

**字段说明：**

| 字段 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `name` | string | 是 | - | 团队名称，用于标识团队 |
| `supervisor_prompt` | string | 是 | - | 团队主管的系统提示词 |
| `workers` | array | 是 | - | Worker 配置列表，至少包含一个 Worker |
| `id` | string | 否 | auto | 团队 ID，如果不提供将自动生成 UUID |
| `prevent_duplicate` | boolean | 否 | true | 是否防止重复调用同一团队 |
| `share_context` | boolean | 否 | false | 是否接收已执行团队的上下文（需要 enable_context_sharing=true） |

---

### WorkerConfig

Worker Agent 配置对象。

```typescript
interface WorkerConfig {
  name: string;                    // Worker 名称
  role: string;                    // Worker 角色
  system_prompt: string;           // Worker 的系统提示词
  id?: string;                     // Worker ID（可选，自动生成）
  tools?: string[];                // 工具列表，默认 []
  temperature?: number;            // 生成温度，默认 0.7
  max_tokens?: number;             // 最大 token 数，默认 2048
}
```

**字段说明：**

| 字段 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `name` | string | 是 | - | Worker 名称 |
| `role` | string | 是 | - | Worker 角色描述 |
| `system_prompt` | string | 是 | - | Worker 的系统提示词，定义其行为和能力 |
| `id` | string | 否 | auto | Worker ID，如果不提供将自动生成 UUID |
| `tools` | array | 否 | [] | 工具名称列表，可选值：["calculator", "http_request"] |
| `temperature` | number | 否 | 0.7 | 生成温度，控制输出的随机性（0.0-1.0） |
| `max_tokens` | number | 否 | 2048 | 最大 token 数，控制输出长度 |

---

### ExecutionResponse

执行响应对象。

```typescript
interface ExecutionResponse {
  success: boolean;                // 执行是否成功
  topology: TopologyInfo;          // 拓扑信息
  events: StreamEvent[];           // 事件流列表
  result?: string;                 // 执行结果（如果成功）
  error?: string;                  // 错误信息（如果失败）
  statistics?: object;             // 统计信息
}
```

**字段说明：**

| 字段 | 类型 | 描述 |
|------|------|------|
| `success` | boolean | 执行是否成功 |
| `topology` | object | 拓扑信息，包含所有团队和 Worker 的 ID |
| `events` | array | 事件流列表，记录执行过程中的所有事件 |
| `result` | string | 执行结果（仅当成功时） |
| `error` | string | 错误信息（仅当失败时） |
| `statistics` | object | 统计信息，包含调用次数等 |

---

### TopologyInfo

拓扑信息对象。

```typescript
interface TopologyInfo {
  global_supervisor_id: string;    // 全局协调者 ID
  teams: TeamInfo[];               // 团队信息列表
}

interface TeamInfo {
  team_id: string;                 // 团队 ID
  team_name: string;               // 团队名称
  supervisor_id: string;           // 团队主管 ID
  workers: WorkerInfo[];           // Worker 信息列表
}

interface WorkerInfo {
  worker_id: string;               // Worker ID
  worker_name: string;             // Worker 名称
  role: string;                    // Worker 角色
}
```

---

### StreamEvent

流式事件对象。

```typescript
interface StreamEvent {
  event_type: EventType;           // 事件类型
  timestamp: string;               // 时间戳（ISO 8601 格式）
  data: object;                    // 事件数据
  topology_metadata?: TopologyMetadata;  // 拓扑元数据（可选）
}

type EventType = 
  | "topology_created"             // 拓扑创建完成
  | "execution_started"            // 执行开始
  | "team_started"                 // 团队开始执行
  | "team_completed"               // 团队完成执行
  | "worker_started"               // Worker 开始执行
  | "worker_completed"             // Worker 完成执行
  | "execution_completed"          // 执行完成
  | "error";                       // 错误

interface TopologyMetadata {
  team_id?: string;                // 团队 ID
  supervisor_id?: string;          // 主管 ID
  worker_id?: string;              // Worker ID
}
```

---

### ErrorResponse

错误响应对象。

```typescript
interface ErrorResponse {
  error: string;                   // 错误消息
  details?: string;                // 错误详情（仅在 DEBUG 模式）
}
```

## 错误处理

### HTTP 状态码

| 状态码 | 描述 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求格式错误（缺少必需字段、类型错误等） |
| 500 | 服务器内部错误 |

### 错误响应格式

```json
{
  "error": "Missing required field: task",
  "details": "详细错误堆栈（仅在 DEBUG=true 时返回）"
}
```

### 常见错误

#### 1. 缺少必需字段

**请求:**
```json
{
  "global_prompt": "测试"
  // 缺少 teams 和 task
}
```

**响应:**
```json
{
  "error": "Missing required field: teams"
}
```

#### 2. 无效的团队配置

**请求:**
```json
{
  "global_prompt": "测试",
  "teams": [],  // 空列表
  "task": "任务"
}
```

**响应:**
```json
{
  "error": "At least one team is required"
}
```

#### 3. Worker 配置错误

**请求:**
```json
{
  "global_prompt": "测试",
  "teams": [
    {
      "name": "团队1",
      "supervisor_prompt": "提示词",
      "workers": [
        {
          "name": "Worker1"
          // 缺少 role 和 system_prompt
        }
      ]
    }
  ],
  "task": "任务"
}
```

**响应:**
```json
{
  "error": "Team 0, Worker 0: Missing required field 'role'"
}
```

## 速率限制

当前版本没有硬性速率限制，但受 AWS Lambda 和 Bedrock 的限制：

- **Lambda 并发限制**: 默认 1000 个并发执行
- **Lambda 超时**: 900 秒（15 分钟）
- **Bedrock API 限制**: 根据您的 AWS 账户配额

建议实施客户端速率限制以避免超出配额。

## 示例

### 示例 1: 简单单团队请求

**请求:**

```bash
curl -X POST https://your-api-endpoint.com/prod/execute \
  -H "Content-Type: application/json" \
  -d '{
    "global_prompt": "你是研究中心的首席科学家。",
    "teams": [
      {
        "name": "研究团队",
        "supervisor_prompt": "你是研究团队的负责人。",
        "workers": [
          {
            "name": "研究员",
            "role": "数据分析",
            "system_prompt": "你是数据分析专家。",
            "tools": ["calculator"]
          }
        ]
      }
    ],
    "task": "分析最新的量子计算趋势"
  }'
```

**响应:**

```json
{
  "success": true,
  "topology": {
    "global_supervisor_id": "global_abc-123-def",
    "teams": [
      {
        "team_id": "team_xyz-456-uvw",
        "team_name": "研究团队",
        "supervisor_id": "supervisor_team_xyz-456-uvw",
        "workers": [
          {
            "worker_id": "worker_mno-789-pqr",
            "worker_name": "研究员",
            "role": "数据分析"
          }
        ]
      }
    ]
  },
  "events": [
    {
      "event_type": "topology_created",
      "timestamp": "2025-12-10T15:30:00.000Z",
      "data": { ... }
    },
    {
      "event_type": "team_started",
      "timestamp": "2025-12-10T15:30:01.000Z",
      "data": {
        "team_name": "研究团队",
        "task": "分析最新的量子计算趋势"
      },
      "topology_metadata": {
        "team_id": "team_xyz-456-uvw",
        "supervisor_id": "supervisor_team_xyz-456-uvw"
      }
    },
    {
      "event_type": "worker_completed",
      "timestamp": "2025-12-10T15:30:10.000Z",
      "data": {
        "worker_name": "研究员",
        "result_preview": "量子计算的最新趋势包括..."
      },
      "topology_metadata": {
        "team_id": "team_xyz-456-uvw",
        "supervisor_id": "supervisor_team_xyz-456-uvw",
        "worker_id": "worker_mno-789-pqr"
      }
    },
    {
      "event_type": "execution_completed",
      "timestamp": "2025-12-10T15:30:15.000Z",
      "data": {
        "result_preview": "综合研究结果显示..."
      }
    }
  ],
  "result": "根据研究团队的分析，量子计算的最新趋势包括...",
  "statistics": {
    "total_calls": 1,
    "team_calls": {
      "研究团队": 1
    },
    "completed_calls": 1
  }
}
```

### 示例 2: 多团队并行执行

**请求:**

```bash
curl -X POST https://your-api-endpoint.com/prod/execute \
  -H "Content-Type: application/json" \
  -d @examples/multi_team_parallel_request.json
```

请求体内容（文件 `examples/multi_team_parallel_request.json`）：

```json
{
  "global_prompt": "你是量子研究中心的首席科学家。",
  "teams": [
    {
      "name": "理论物理学团队",
      "supervisor_prompt": "你是理论物理学团队的负责人。",
      "workers": [
        {
          "name": "量子理论专家",
          "role": "量子理论研究",
          "system_prompt": "你精通量子力学理论。",
          "tools": ["calculator"]
        }
      ]
    },
    {
      "name": "实验物理学团队",
      "supervisor_prompt": "你是实验物理学团队的负责人。",
      "workers": [
        {
          "name": "实验设计师",
          "role": "实验设计",
          "system_prompt": "你擅长设计量子实验。"
        }
      ],
      "share_context": true
    }
  ],
  "task": "研究量子纠缠现象",
  "execution_mode": "parallel",
  "enable_context_sharing": true
}
```

**响应:**

响应将包含两个团队的执行事件，展示并行执行和上下文共享。

### 示例 3: 使用 Python 客户端

```python
import requests
import json

# API 端点
API_ENDPOINT = "https://your-api-endpoint.com/prod/execute"

# 请求配置
config = {
    "global_prompt": "你是AI研究中心的首席科学家。",
    "teams": [
        {
            "name": "机器学习团队",
            "supervisor_prompt": "你是机器学习团队的负责人。",
            "workers": [
                {
                    "name": "深度学习专家",
                    "role": "神经网络研究",
                    "system_prompt": "你精通深度学习和神经网络。",
                    "tools": ["calculator"]
                }
            ]
        }
    ],
    "task": "分析 Transformer 架构的创新点",
    "execution_mode": "sequential"
}

# 发送请求
response = requests.post(
    API_ENDPOINT,
    headers={"Content-Type": "application/json"},
    json=config
)

# 处理响应
if response.status_code == 200:
    result = response.json()
    if result['success']:
        print("执行成功！")
        print(f"拓扑: {result['topology']}")
        print(f"事件数量: {len(result['events'])}")
        print(f"结果: {result['result'][:200]}...")
    else:
        print(f"执行失败: {result['error']}")
else:
    print(f"HTTP 错误: {response.status_code}")
    print(response.text)
```

### 示例 4: 使用 JavaScript/Node.js 客户端

```javascript
const fetch = require('node-fetch');

const API_ENDPOINT = 'https://your-api-endpoint.com/prod/execute';

const config = {
  global_prompt: '你是量子研究中心的首席科学家。',
  teams: [
    {
      name: '理论团队',
      supervisor_prompt: '你是理论团队的负责人。',
      workers: [
        {
          name: '理论专家',
          role: '量子理论',
          system_prompt: '你精通量子理论。',
          tools: ['calculator']
        }
      ]
    }
  ],
  task: '研究量子纠缠',
  execution_mode: 'sequential'
};

fetch(API_ENDPOINT, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(config)
})
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      console.log('执行成功！');
      console.log('拓扑:', data.topology);
      console.log('事件:', data.events.length);
      console.log('结果:', data.result.substring(0, 200) + '...');
    } else {
      console.error('执行失败:', data.error);
    }
  })
  .catch(error => {
    console.error('请求错误:', error);
  });
```

## 最佳实践

### 1. 提示词设计

- **具体明确**: 清晰描述 Agent 的角色、职责和能力
- **中英文混合**: 可以使用中英文，但保持一致性
- **任务导向**: 明确每个 Agent 应该完成什么任务

### 2. 团队组织

- **职责分离**: 每个团队负责特定领域
- **合理规模**: 每个团队 2-5 个 Worker 最佳
- **层次清晰**: Global → Team → Worker 的层级关系明确

### 3. 执行模式选择

- **顺序执行**: 适合有依赖关系的任务
- **并行执行**: 适合独立任务，提高效率

### 4. 上下文共享

- **默认不共享**: 除非明确需要团队间协作
- **选择性共享**: 只让需要前置信息的团队接收上下文

### 5. 错误处理

- **验证输入**: 在发送请求前验证配置
- **处理超时**: 设置合理的客户端超时时间
- **重试机制**: 实现指数退避重试

### 6. 性能优化

- **减少 Worker 数量**: 过多 Worker 会增加执行时间
- **缓存结果**: 对相同任务缓存结果
- **监控指标**: 跟踪执行时间和成本

## 版本历史

### v1.0.0 (2025-12-10)

- 初始版本发布
- 支持动态创建层级拓扑
- 支持顺序和并行执行
- 提供事件流和拓扑元数据
- AWS Lambda + API Gateway 部署

## 支持

如有问题或建议，请：
- 查看 [部署指南](API_DEPLOYMENT.md)
- 查看 [CloudWatch Logs](https://console.aws.amazon.com/cloudwatch/)
- 提交 Issue 或 Pull Request

---

**最后更新**: 2025-12-10  
**API 版本**: 1.0.0
