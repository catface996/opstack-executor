"""
API 数据模型 - 定义 HTTP API 的请求和响应结构
"""

from typing import List, Optional, Any, Dict
from dataclasses import dataclass, field, asdict
from enum import Enum


class ExecutionMode(str, Enum):
    """执行模式枚举"""
    SEQUENTIAL = "sequential"  # 顺序执行
    PARALLEL = "parallel"      # 并行执行


class EventType(str, Enum):
    """事件类型枚举"""
    TOPOLOGY_CREATED = "topology_created"
    EXECUTION_STARTED = "execution_started"
    TEAM_STARTED = "team_started"
    TEAM_COMPLETED = "team_completed"
    WORKER_STARTED = "worker_started"
    WORKER_COMPLETED = "worker_completed"
    EXECUTION_COMPLETED = "execution_completed"
    ERROR = "error"


@dataclass
class WorkerConfigRequest:
    """Worker Agent 配置请求"""
    name: str
    role: str
    system_prompt: str
    id: Optional[str] = None
    tools: List[str] = field(default_factory=list)  # Tool names: "calculator", "http_request"
    temperature: float = 0.7
    max_tokens: int = 2048
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class TeamConfigRequest:
    """Team 配置请求"""
    name: str
    supervisor_prompt: str
    workers: List[WorkerConfigRequest]
    id: Optional[str] = None
    prevent_duplicate: bool = True
    share_context: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'supervisor_prompt': self.supervisor_prompt,
            'workers': [w.to_dict() for w in self.workers],
            'id': self.id,
            'prevent_duplicate': self.prevent_duplicate,
            'share_context': self.share_context
        }


@dataclass
class HierarchyConfigRequest:
    """层级配置请求"""
    global_prompt: str
    teams: List[TeamConfigRequest]
    task: str
    enable_context_sharing: bool = False
    execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'global_prompt': self.global_prompt,
            'teams': [t.to_dict() for t in self.teams],
            'task': self.task,
            'enable_context_sharing': self.enable_context_sharing,
            'execution_mode': self.execution_mode.value
        }


@dataclass
class TopologyInfo:
    """拓扑信息"""
    global_supervisor_id: str
    teams: List[Dict[str, Any]]  # [{team_id, team_name, supervisor_id, workers: [{worker_id, worker_name}]}]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class StreamEvent:
    """流式事件"""
    event_type: EventType
    timestamp: str
    data: Dict[str, Any]
    topology_metadata: Optional[Dict[str, str]] = None  # {team_id, supervisor_id, worker_id}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'event_type': self.event_type.value,
            'timestamp': self.timestamp,
            'data': self.data,
            'topology_metadata': self.topology_metadata
        }


@dataclass
class ExecutionResponse:
    """执行响应"""
    success: bool
    topology: TopologyInfo
    events: List[StreamEvent]
    result: Optional[str] = None
    error: Optional[str] = None
    statistics: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'success': self.success,
            'topology': self.topology.to_dict(),
            'events': [e.to_dict() for e in self.events],
            'result': self.result,
            'error': self.error,
            'statistics': self.statistics
        }


@dataclass
class ErrorResponse:
    """错误响应"""
    error: str
    details: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


# ============================================================================
# 辅助函数 - 将字典转换为数据类实例
# ============================================================================

def parse_worker_config(data: Dict[str, Any]) -> WorkerConfigRequest:
    """解析 Worker 配置"""
    return WorkerConfigRequest(
        name=data['name'],
        role=data['role'],
        system_prompt=data['system_prompt'],
        id=data.get('id'),
        tools=data.get('tools', []),
        temperature=data.get('temperature', 0.7),
        max_tokens=data.get('max_tokens', 2048)
    )


def parse_team_config(data: Dict[str, Any]) -> TeamConfigRequest:
    """解析 Team 配置"""
    return TeamConfigRequest(
        name=data['name'],
        supervisor_prompt=data['supervisor_prompt'],
        workers=[parse_worker_config(w) for w in data['workers']],
        id=data.get('id'),
        prevent_duplicate=data.get('prevent_duplicate', True),
        share_context=data.get('share_context', False)
    )


def parse_hierarchy_config(data: Dict[str, Any]) -> HierarchyConfigRequest:
    """解析层级配置"""
    execution_mode_str = data.get('execution_mode', 'sequential')
    execution_mode = ExecutionMode.PARALLEL if execution_mode_str == 'parallel' else ExecutionMode.SEQUENTIAL
    
    return HierarchyConfigRequest(
        global_prompt=data['global_prompt'],
        teams=[parse_team_config(t) for t in data['teams']],
        task=data['task'],
        enable_context_sharing=data.get('enable_context_sharing', False),
        execution_mode=execution_mode
    )
