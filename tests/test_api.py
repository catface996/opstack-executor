#!/usr/bin/env python3
"""
API 测试脚本 - 本地测试 Lambda Handler
"""

import json
import os
import sys

# 设置 API Key
if 'AWS_BEDROCK_API_KEY' not in os.environ:
    print("错误: 请设置 AWS_BEDROCK_API_KEY 环境变量")
    print("export AWS_BEDROCK_API_KEY='your-api-key'")
    sys.exit(1)

from src.lambda_deploy.handler import lambda_handler


class MockContext:
    """模拟 Lambda 上下文"""
    function_name = 'test-function'
    memory_limit_in_mb = 2048
    invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test'
    aws_request_id = 'test-request-id'


def test_health_check():
    """测试健康检查端点"""
    print("=" * 80)
    print("测试 1: 健康检查")
    print("=" * 80)
    
    from src.lambda_deploy.handler import health_check_handler
    
    event = {'httpMethod': 'GET', 'path': '/health'}
    response = health_check_handler(event, MockContext())
    
    print(f"状态码: {response['statusCode']}")
    print(f"响应: {response['body']}")
    print()


def test_simple_request():
    """测试简单请求"""
    print("=" * 80)
    print("测试 2: 简单请求（单团队）")
    print("=" * 80)
    
    # 加载示例请求
    with open('examples/simple_request.json', 'r') as f:
        request_body = json.load(f)
    
    event = {
        'httpMethod': 'POST',
        'path': '/execute',
        'body': json.dumps(request_body)
    }
    
    response = lambda_handler(event, MockContext())
    
    print(f"状态码: {response['statusCode']}")
    
    # 解析响应
    response_body = json.loads(response['body'])
    
    if response_body.get('success'):
        print("✓ 执行成功")
        print(f"拓扑信息:")
        print(f"  - 全局协调者 ID: {response_body['topology']['global_supervisor_id']}")
        print(f"  - 团队数量: {len(response_body['topology']['teams'])}")
        print(f"事件数量: {len(response_body['events'])}")
        print(f"结果预览: {response_body['result'][:200]}...")
    else:
        print("✗ 执行失败")
        print(f"错误: {response_body.get('error')}")
    
    print()


def test_multi_team_request():
    """测试多团队并行请求"""
    print("=" * 80)
    print("测试 3: 多团队并行请求")
    print("=" * 80)
    
    # 加载示例请求
    with open('examples/multi_team_parallel_request.json', 'r') as f:
        request_body = json.load(f)
    
    event = {
        'httpMethod': 'POST',
        'path': '/execute',
        'body': json.dumps(request_body)
    }
    
    response = lambda_handler(event, MockContext())
    
    print(f"状态码: {response['statusCode']}")
    
    # 解析响应
    response_body = json.loads(response['body'])
    
    if response_body.get('success'):
        print("✓ 执行成功")
        print(f"拓扑信息:")
        print(f"  - 全局协调者 ID: {response_body['topology']['global_supervisor_id']}")
        print(f"  - 团队数量: {len(response_body['topology']['teams'])}")
        
        # 打印每个团队的信息
        for team in response_body['topology']['teams']:
            print(f"\n  团队: {team['team_name']}")
            print(f"    - 团队 ID: {team['team_id']}")
            print(f"    - 主管 ID: {team['supervisor_id']}")
            print(f"    - Worker 数量: {len(team['workers'])}")
            for worker in team['workers']:
                print(f"      * {worker['worker_name']} (ID: {worker['worker_id']})")
        
        print(f"\n事件数量: {len(response_body['events'])}")
        print(f"统计信息: {json.dumps(response_body['statistics'], indent=2, ensure_ascii=False)}")
        print(f"\n结果预览: {response_body['result'][:300]}...")
    else:
        print("✗ 执行失败")
        print(f"错误: {response_body.get('error')}")
    
    print()


def test_invalid_request():
    """测试无效请求"""
    print("=" * 80)
    print("测试 4: 无效请求（缺少必需字段）")
    print("=" * 80)
    
    event = {
        'httpMethod': 'POST',
        'path': '/execute',
        'body': json.dumps({
            'global_prompt': '测试提示词'
            # 缺少 teams 和 task
        })
    }
    
    response = lambda_handler(event, MockContext())
    
    print(f"状态码: {response['statusCode']}")
    response_body = json.loads(response['body'])
    print(f"错误信息: {response_body.get('error')}")
    print()


def main():
    """主函数"""
    print("\n")
    print("🚀 层级多智能体系统 API 测试")
    print("=" * 80)
    print()
    
    # 运行测试
    tests = [
        ("健康检查", test_health_check),
        ("简单请求", test_simple_request),
        ("多团队并行请求", test_multi_team_request),
        ("无效请求", test_invalid_request)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            test_func()
            results.append((name, "✓ 通过"))
        except Exception as e:
            results.append((name, f"✗ 失败: {str(e)}"))
    
    # 打印测试摘要
    print("=" * 80)
    print("测试摘要")
    print("=" * 80)
    for name, result in results:
        print(f"{name}: {result}")
    print()


if __name__ == '__main__':
    main()
