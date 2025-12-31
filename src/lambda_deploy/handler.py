"""
AWS Lambda Handler - HTTP API 接口
支持通过 API Gateway 调用的 Lambda 函数
"""

import json
import os
import traceback
from typing import Dict, Any

# 导入配置管理
from ..core.config import setup_config

# 导入执行器
from ..core.hierarchy_executor import execute_hierarchy
from ..core.api_models import ErrorResponse


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda 函数入口
    
    处理来自 API Gateway 的 HTTP 请求，执行层级多智能体系统。
    
    Args:
        event: API Gateway 事件对象
        context: Lambda 运行时上下文
        
    Returns:
        API Gateway 响应对象
    """
    try:
        # 1. 设置配置（从环境变量加载）
        setup_config()
        
        # 2. 解析请求体
        body = _parse_request_body(event)
        
        # 3. 验证请求
        validation_error = _validate_request(body)
        if validation_error:
            return _create_error_response(400, validation_error)
        
        # 4. 执行层级系统
        response = execute_hierarchy(body)
        
        # 5. 返回响应
        return _create_success_response(response.to_dict())
        
    except Exception as e:
        # 错误处理
        error_msg = str(e)
        error_details = traceback.format_exc()
        
        print(f"Error: {error_msg}")
        print(f"Details: {error_details}")
        
        error_response = ErrorResponse(
            error=error_msg,
            details=error_details if os.environ.get('DEBUG') == 'true' else None
        )
        
        return _create_error_response(500, error_response.to_dict())


def _parse_request_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    解析请求体
    
    Args:
        event: API Gateway 事件
        
    Returns:
        解析后的请求体字典
    """
    body = event.get('body', '{}')
    
    # 如果 body 是字符串，解析为 JSON
    if isinstance(body, str):
        body = json.loads(body)
    
    return body


def _validate_request(body: Dict[str, Any]) -> Any:
    """
    验证请求
    
    Args:
        body: 请求体
        
    Returns:
        错误消息（如果有），否则返回 None
    """
    # Support both old format (global_prompt) and new format (global_supervisor_agent)
    has_global_prompt = 'global_prompt' in body
    has_global_agent = 'global_supervisor_agent' in body and isinstance(body.get('global_supervisor_agent'), dict)
    if not has_global_prompt and not has_global_agent:
        return "Missing required field: 'global_prompt' or 'global_supervisor_agent.system_prompt'"
    if has_global_agent and 'system_prompt' not in body['global_supervisor_agent']:
        return "Missing required field: 'global_supervisor_agent.system_prompt'"

    if 'teams' not in body:
        return "Missing required field: 'teams'"
    if 'task' not in body:
        return "Missing required field: 'task'"

    # 检查 teams 是否为列表
    if not isinstance(body['teams'], list):
        return "Field 'teams' must be a list"

    # 检查至少有一个团队
    if len(body['teams']) == 0:
        return "At least one team is required"

    # 验证每个团队
    for i, team in enumerate(body['teams']):
        if 'name' not in team:
            return f"Team {i}: Missing required field 'name'"
        if 'workers' not in team:
            return f"Team {i}: Missing required field 'workers'"

        # Support both old format (supervisor_prompt) and new format (team_supervisor_agent)
        has_supervisor_prompt = 'supervisor_prompt' in team
        has_team_agent = 'team_supervisor_agent' in team and isinstance(team.get('team_supervisor_agent'), dict)
        if not has_supervisor_prompt and not has_team_agent:
            return f"Team {i}: Missing required field 'supervisor_prompt' or 'team_supervisor_agent.system_prompt'"
        if has_team_agent and 'system_prompt' not in team['team_supervisor_agent']:
            return f"Team {i}: Missing required field 'team_supervisor_agent.system_prompt'"

        # 检查 workers 是否为列表
        if not isinstance(team['workers'], list):
            return f"Team {i}: Field 'workers' must be a list"

        # 检查至少有一个 worker
        if len(team['workers']) == 0:
            return f"Team {i}: At least one worker is required"

        # 验证每个 worker
        for j, worker in enumerate(team['workers']):
            worker_required = ['name', 'role', 'system_prompt']
            for field in worker_required:
                if field not in worker:
                    return f"Team {i}, Worker {j}: Missing required field '{field}'"

    return None


def _create_success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    创建成功响应
    
    Args:
        data: 响应数据
        
    Returns:
        API Gateway 响应对象
    """
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',  # CORS 支持
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        },
        'body': json.dumps(data, ensure_ascii=False)
    }


def _create_error_response(status_code: int, error: Any) -> Dict[str, Any]:
    """
    创建错误响应
    
    Args:
        status_code: HTTP 状态码
        error: 错误信息（字符串或字典）
        
    Returns:
        API Gateway 响应对象
    """
    if isinstance(error, str):
        error = {'error': error}
    
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        },
        'body': json.dumps(error, ensure_ascii=False)
    }


# ============================================================================
# Health Check Handler
# ============================================================================

def health_check_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    健康检查处理器
    
    Args:
        event: API Gateway 事件
        context: Lambda 运行时上下文
        
    Returns:
        健康状态响应
    """
    return _create_success_response({
        'status': 'healthy',
        'service': 'hierarchical-agents-api',
        'version': '1.0.0'
    })


# ============================================================================
# 本地测试支持
# ============================================================================

def test_locally():
    """本地测试函数"""
    # 示例请求（使用新格式）
    test_event = {
        'body': json.dumps({
            'global_supervisor_agent': {
                'system_prompt': '你是全局协调者，负责协调所有团队完成任务。'
            },
            'teams': [
                {
                    'name': '研究团队',
                    'team_supervisor_agent': {
                        'system_prompt': '你是研究团队的负责人。'
                    },
                    'workers': [
                        {
                            'name': '研究员A',
                            'role': '数据分析',
                            'system_prompt': '你是数据分析专家。'
                        }
                    ]
                }
            ],
            'task': '分析量子计算的发展趋势',
            'execution_mode': 'sequential'
        })
    }
    
    # 模拟 context
    class MockContext:
        function_name = 'test-function'
        memory_limit_in_mb = 512
        invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test'
        aws_request_id = 'test-request-id'
    
    # 调用 handler
    response = lambda_handler(test_event, MockContext())
    
    # 打印响应
    print(json.dumps(response, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    # 本地测试
    test_locally()
