#!/bin/bash

echo "🚀 开始流式响应测试"
echo "================================"

# 使用正确格式的execution_id进行测试
EXECUTION_ID="exec_123456789abc"

echo "📡 连接流式接口: /api/v1/executions/$EXECUTION_ID/stream"
echo "⏰ 开始时间: $(date)"
echo "--------------------------------"

# 使用curl进行流式请求，逐行打印
curl -N -H "Accept: text/event-stream" \
     -H "Cache-Control: no-cache" \
     "http://localhost:8000/api/v1/executions/$EXECUTION_ID/stream" \
     2>/dev/null | while IFS= read -r line; do
    
    # 打印时间戳和接收到的行
    echo "[$(date '+%H:%M:%S')] $line"
    
    # 如果是空行，添加分隔符
    if [ -z "$line" ]; then
        echo "    --- 事件分隔 ---"
    fi
    
    # 检查是否是结束事件
    if echo "$line" | grep -q "execution_complete\|stream_error\|connection_closed"; then
        echo "🏁 检测到结束事件，停止流式监听"
        break
    fi
done

echo "--------------------------------"
echo "⏰ 结束时间: $(date)"
echo "✅ 流式响应测试完成"
