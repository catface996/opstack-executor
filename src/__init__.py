"""
Hierarchical Agents - 层级多智能体系统

模块结构:
- core/: 核心业务逻辑 (需要 strands 依赖)
- lambda_deploy/: AWS Lambda 部署
- ec2/: EC2/Docker 部署
- db/: 数据库模块
- api/: REST API 模块
- streaming/: 流式输出模块
- runner/: 运行管理模块
"""

__version__ = '2.0.0'

# 延迟导入 - 只在需要时导入依赖 strands 的模块
# 避免在不需要时触发 strands 依赖检查

def get_core_exports():
    """获取核心模块导出（需要 strands 依赖）"""
    from .core import (
        ExecutionMode,
        EventType,
        InternalEvent,
        WorkerConfigRequest,
        TeamConfigRequest,
        HierarchyConfigRequest,
        StreamEvent,
        ExecutionResponse,
        TopologyInfo,
        ErrorResponse,
        Config,
        setup_config,
        get_config,
        OutputFormatter,
        HierarchyBuilder,
        GlobalSupervisorFactory,
        ExecutionTracker,
        CallTracker,
        execute_hierarchy,
    )
    return {
        'ExecutionMode': ExecutionMode,
        'EventType': EventType,
        'InternalEvent': InternalEvent,
        'WorkerConfigRequest': WorkerConfigRequest,
        'TeamConfigRequest': TeamConfigRequest,
        'HierarchyConfigRequest': HierarchyConfigRequest,
        'StreamEvent': StreamEvent,
        'ExecutionResponse': ExecutionResponse,
        'TopologyInfo': TopologyInfo,
        'ErrorResponse': ErrorResponse,
        'Config': Config,
        'setup_config': setup_config,
        'get_config': get_config,
        'OutputFormatter': OutputFormatter,
        'HierarchyBuilder': HierarchyBuilder,
        'GlobalSupervisorFactory': GlobalSupervisorFactory,
        'ExecutionTracker': ExecutionTracker,
        'CallTracker': CallTracker,
        'execute_hierarchy': execute_hierarchy,
    }


def get_lambda_exports():
    """获取 Lambda 模块导出（需要 strands 依赖）"""
    from .lambda_deploy import lambda_handler, health_check_handler
    return {
        'lambda_handler': lambda_handler,
        'health_check_handler': health_check_handler,
    }


def get_ec2_exports():
    """获取 EC2 模块导出"""
    from .ec2 import app
    return {'app': app}
