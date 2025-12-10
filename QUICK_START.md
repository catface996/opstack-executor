# 快速开始指南 - HTTP API

## 🚀 5 分钟快速上手

本指南帮助您在 5 分钟内部署并测试层级多智能体系统的 HTTP API。

## 前提条件

确保您已安装：
- ✅ AWS CLI
- ✅ AWS SAM CLI
- ✅ Python 3.12+
- ✅ 有效的 AWS Bedrock API Key

## 步骤 1: 部署到 AWS（2 分钟）

```bash
# 进入项目目录
cd /projects/sandbox/hierarchical-agents

# 运行部署脚本
./deploy.sh
```

按照提示输入：
- Stack Name: `hierarchical-agents-api`
- AWS Region: `us-east-1`（或您的首选区域）
- Bedrock API Key: `your-api-key`
- 其他参数使用默认值

## 步骤 2: 获取 API 端点（30 秒）

部署完成后，记录输出的 API 端点：

```
ExecuteEndpoint: https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prod/execute
HealthCheckEndpoint: https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prod/health
```

## 步骤 3: 测试 API（1 分钟）

### 测试健康检查

```bash
curl https://your-endpoint.com/prod/health
```

预期响应：
```json
{
  "status": "healthy",
  "service": "hierarchical-agents-api",
  "version": "1.0.0"
}
```

### 执行简单任务

```bash
curl -X POST https://your-endpoint.com/prod/execute \
  -H "Content-Type: application/json" \
  -d @examples/simple_request.json
```

## 步骤 4: 查看结果（1 分钟）

响应将包含：
- ✅ 拓扑信息（所有团队和 Worker 的 ID）
- ✅ 执行事件流（每个步骤的详细记录）
- ✅ 最终结果（智能体系统的输出）
- ✅ 统计信息（调用次数、执行状态）

## 完整示例

```bash
# 部署
cd /projects/sandbox/hierarchical-agents
./deploy.sh

# 记录端点（从部署输出获取）
export API_ENDPOINT="https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prod"

# 健康检查
curl $API_ENDPOINT/health

# 执行任务
curl -X POST $API_ENDPOINT/execute \
  -H "Content-Type: application/json" \
  -d '{
    "global_prompt": "你是研究中心的首席科学家。",
    "teams": [{
      "name": "研究团队",
      "supervisor_prompt": "你是研究团队的负责人。",
      "workers": [{
        "name": "研究员",
        "role": "数据分析",
        "system_prompt": "你是数据分析专家。"
      }]
    }],
    "task": "分析量子计算的最新发展趋势"
  }'
```

## 本地测试（可选）

如果想在本地测试：

```bash
# 设置 API Key
export AWS_BEDROCK_API_KEY='your-api-key'

# 运行测试脚本
python test_api.py
```

## 常见问题

### Q: 部署失败怎么办？

A: 检查：
1. AWS CLI 是否正确配置
2. AWS 账户是否有足够权限
3. Bedrock API Key 是否有效

### Q: API 调用超时？

A: 复杂任务可能需要较长时间。可以：
1. 增加 Lambda 超时配置
2. 减少团队和 Worker 数量
3. 使用顺序执行模式

### Q: 如何查看日志？

A: 使用 SAM CLI：
```bash
sam logs -n HierarchicalAgentsFunction --tail
```

## 下一步

- 📖 阅读 [API 参考文档](docs/API_REFERENCE.md)
- 📖 阅读 [部署指南](docs/API_DEPLOYMENT.md)
- 🧪 尝试 [多团队并行示例](examples/multi_team_parallel_request.json)
- 🎨 自定义您的智能体配置

## 需要帮助？

- 查看 [实现总结](IMPLEMENTATION_SUMMARY.md)
- 查看 [验证清单](VERIFICATION_CHECKLIST.md)
- 查看 CloudWatch 日志

---

**祝您使用愉快！** 🎉
