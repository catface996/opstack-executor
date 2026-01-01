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
    """事件类型枚举 - 用于内部执行跟踪"""
    TOPOLOGY_CREATED = "topology_created"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    TEAM_STARTED = "team_started"
    TEAM_COMPLETED = "team_completed"
    WORKER_STARTED = "worker_started"
    WORKER_COMPLETED = "worker_completed"
    ERROR = "error"


class AgentType(str, Enum):
    """Agent 类型枚举"""
    GLOBAL_SUPERVISOR = "global_supervisor"
    TEAM_SUPERVISOR = "team_supervisor"
    WORKER = "worker"


class EventCategory(str, Enum):
    """事件类别枚举"""
    LIFECYCLE = "lifecycle"  # 生命周期事件
    LLM = "llm"              # LLM 相关事件
    DISPATCH = "dispatch"    # 调度事件
    SYSTEM = "system"        # 系统事件
    AGENT = "agent"          # Agent 级别事件（用于串行化控制）


class EventAction(str, Enum):
    """事件动作枚举"""
    # lifecycle actions
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    # llm actions
    STREAM = "stream"
    REASONING = "reasoning"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"

    # dispatch actions
    TEAM = "team"
    WORKER = "worker"

    # system actions
    TOPOLOGY = "topology"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class EventSource:
    """事件来源"""
    agent_id: str
    agent_type: AgentType
    agent_name: str
    team_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'agent_id': self.agent_id,
            'agent_type': self.agent_type.value if isinstance(self.agent_type, AgentType) else self.agent_type,
            'agent_name': self.agent_name,
            'team_name': self.team_name
        }

    @classmethod
    def global_supervisor(cls, agent_id: str, agent_name: str = "Global Supervisor") -> 'EventSource':
        """创建 Global Supervisor 来源"""
        return cls(
            agent_id=agent_id,
            agent_type=AgentType.GLOBAL_SUPERVISOR,
            agent_name=agent_name,
            team_name=None
        )

    @classmethod
    def team_supervisor(cls, agent_id: str, agent_name: str, team_name: str) -> 'EventSource':
        """创建 Team Supervisor 来源"""
        return cls(
            agent_id=agent_id,
            agent_type=AgentType.TEAM_SUPERVISOR,
            agent_name=agent_name,
            team_name=team_name
        )

    @classmethod
    def worker(cls, agent_id: str, agent_name: str, team_name: str) -> 'EventSource':
        """创建 Worker 来源"""
        return cls(
            agent_id=agent_id,
            agent_type=AgentType.WORKER,
            agent_name=agent_name,
            team_name=team_name
        )


@dataclass
class EventMeta:
    """事件元信息"""
    category: EventCategory
    action: EventAction

    def to_dict(self) -> Dict[str, Any]:
        return {
            'category': self.category.value if isinstance(self.category, EventCategory) else self.category,
            'action': self.action.value if isinstance(self.action, EventAction) else self.action
        }


@dataclass
class StreamEvent:
    """
    流式事件结构 - 用于 SSE 实时流

    {
        "run_id": "...",
        "timestamp": "...",
        "sequence": 123,
        "source": { agent_id, agent_type, agent_name, team_name },
        "event": { category, action },
        "data": { ... }
    }
    """
    run_id: str
    timestamp: str
    sequence: int
    source: EventSource
    event: EventMeta
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'run_id': self.run_id,
            'timestamp': self.timestamp,
            'sequence': self.sequence,
            'source': self.source.to_dict() if self.source else None,
            'event': self.event.to_dict(),
            'data': self.data
        }


@dataclass
class InternalEvent:
    """
    内部事件结构 - 用于执行跟踪器

    {
        "event_type": "...",
        "timestamp": "...",
        "data": { ... },
        "topology_metadata": { team_id, supervisor_id, worker_id }
    }
    """
    event_type: EventType
    timestamp: str
    data: Dict[str, Any]
    topology_metadata: Optional[Dict[str, str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_type': self.event_type.value,
            'timestamp': self.timestamp,
            'data': self.data,
            'topology_metadata': self.topology_metadata
        }


@dataclass
class WorkerConfigRequest:
    """Worker Agent 配置请求"""
    name: str
    role: str
    system_prompt: str
    id: Optional[str] = None
    agent_id: Optional[str] = None
    user_message: Optional[str] = None
    tools: List[str] = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 2048
    model_id: Optional[str] = None  # LLM 模型 ID，如 gemini-2.0-flash

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class TeamConfigRequest:
    """Team 配置请求"""
    name: str
    supervisor_prompt: str  # 保持兼容性，实际上是 system_prompt
    workers: List[WorkerConfigRequest]
    id: Optional[str] = None
    agent_id: Optional[str] = None
    user_message: Optional[str] = None
    prevent_duplicate: bool = True
    share_context: bool = False
    temperature: float = 0.7
    max_tokens: int = 2048
    model_id: Optional[str] = None  # Team Supervisor LLM 模型 ID

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'supervisor_prompt': self.supervisor_prompt,
            'workers': [w.to_dict() for w in self.workers],
            'id': self.id,
            'agent_id': self.agent_id,
            'user_message': self.user_message,
            'prevent_duplicate': self.prevent_duplicate,
            'share_context': self.share_context,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'model_id': self.model_id
        }


@dataclass
class HierarchyConfigRequest:
    """层级配置请求"""
    global_prompt: str  # 保持兼容性，实际上是 global_supervisor_agent.system_prompt
    teams: List[TeamConfigRequest]
    task: str
    global_agent_id: Optional[str] = None
    global_user_message: Optional[str] = None
    enable_context_sharing: bool = False
    execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    global_temperature: float = 0.7
    global_max_tokens: int = 2048
    global_model_id: Optional[str] = None  # Global Supervisor LLM 模型 ID
    run_id: Optional[int] = None  # 运行 ID，用于跨线程回调查找

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'global_prompt': self.global_prompt,
            'teams': [t.to_dict() for t in self.teams],
            'task': self.task,
            'global_agent_id': self.global_agent_id,
            'global_user_message': self.global_user_message,
            'enable_context_sharing': self.enable_context_sharing,
            'execution_mode': self.execution_mode.value,
            'global_temperature': self.global_temperature,
            'global_max_tokens': self.global_max_tokens,
            'global_model_id': self.global_model_id,
            'run_id': self.run_id
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
class ExecutionResponse:
    """执行响应"""
    success: bool
    topology: TopologyInfo
    events: List[InternalEvent]
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
    # 从 llm_config 或顶层读取 LLM 参数
    llm_config = data.get('llm_config') or {}
    temperature = llm_config.get('temperature') or data.get('temperature', 0.7)
    max_tokens = llm_config.get('max_tokens') or data.get('max_tokens', 2048)
    model_id = llm_config.get('model_id') or data.get('model_id')

    return WorkerConfigRequest(
        name=data['name'],
        role=data['role'],
        system_prompt=data['system_prompt'],
        id=data.get('id'),
        agent_id=data.get('agent_id'),
        user_message=data.get('user_message'),
        tools=data.get('tools', []),
        temperature=temperature,
        max_tokens=max_tokens,
        model_id=model_id
    )


def parse_team_config(data: Dict[str, Any]) -> TeamConfigRequest:
    """解析 Team 配置（支持新旧两种格式）"""
    # 新格式：team_supervisor_agent
    team_agent = data.get('team_supervisor_agent', {})
    system_prompt = team_agent.get('system_prompt') or data.get('supervisor_prompt', '')
    agent_id = team_agent.get('agent_id') or data.get('agent_id')
    user_message = team_agent.get('user_message') or data.get('user_message')

    # 从 llm_config 或顶层读取 LLM 参数
    llm_config = team_agent.get('llm_config') or {}
    temperature = llm_config.get('temperature') or data.get('temperature', 0.7)
    max_tokens = llm_config.get('max_tokens') or data.get('max_tokens', 2048)
    model_id = llm_config.get('model_id') or data.get('model_id')

    return TeamConfigRequest(
        name=data['name'],
        supervisor_prompt=system_prompt,
        workers=[parse_worker_config(w) for w in data.get('workers', [])],
        id=data.get('id'),
        agent_id=agent_id,
        user_message=user_message,
        prevent_duplicate=data.get('prevent_duplicate', True),
        share_context=data.get('share_context', False),
        temperature=temperature,
        max_tokens=max_tokens,
        model_id=model_id
    )


def parse_hierarchy_config(data: Dict[str, Any]) -> HierarchyConfigRequest:
    """解析层级配置（支持新旧两种格式）"""
    execution_mode_str = data.get('execution_mode', 'sequential')
    execution_mode = ExecutionMode.PARALLEL if execution_mode_str == 'parallel' else ExecutionMode.SEQUENTIAL

    # 新格式：global_supervisor_agent
    global_agent = data.get('global_supervisor_agent', {})
    global_prompt = global_agent.get('system_prompt') or data.get('global_prompt', '')
    global_agent_id = global_agent.get('agent_id') or data.get('global_agent_id')
    global_user_message = global_agent.get('user_message') or data.get('global_user_message')

    # 从 llm_config 或顶层读取 Global Supervisor LLM 参数
    llm_config = global_agent.get('llm_config') or {}
    global_temperature = llm_config.get('temperature') or data.get('global_temperature', 0.7)
    global_max_tokens = llm_config.get('max_tokens') or data.get('global_max_tokens', 2048)
    global_model_id = llm_config.get('model_id') or data.get('global_model_id')

    return HierarchyConfigRequest(
        global_prompt=global_prompt,
        teams=[parse_team_config(t) for t in data.get('teams', [])],
        task=data.get('task', ''),
        global_agent_id=global_agent_id,
        global_user_message=global_user_message,
        enable_context_sharing=data.get('enable_context_sharing', False),
        execution_mode=execution_mode,
        global_temperature=global_temperature,
        global_max_tokens=global_max_tokens,
        global_model_id=global_model_id,
        run_id=data.get('run_id')
    )
