"""
LLM Callback Handler - 追踪 LLM 调用来源

根据调用者身份（Global Supervisor / Team Supervisor / Worker）
生成带有来源标识的 stream event
"""

from typing import Any, Callable, Dict, Optional
from dataclasses import dataclass

from ..core.api_models import AgentType, EventCategory, EventAction


@dataclass
class CallerContext:
    """
    调用者上下文信息

    存储 Agent 来源信息，用于生成事件格式
    """
    agent_id: str
    agent_type: AgentType
    agent_name: str
    team_name: Optional[str] = None

    @classmethod
    def global_supervisor(cls, agent_id: str, agent_name: str = "Global Supervisor") -> 'CallerContext':
        """创建 Global Supervisor 上下文"""
        return cls(
            agent_id=agent_id,
            agent_type=AgentType.GLOBAL_SUPERVISOR,
            agent_name=agent_name,
            team_name=None
        )

    @classmethod
    def team_supervisor(cls, agent_id: str, agent_name: str, team_name: str) -> 'CallerContext':
        """创建 Team Supervisor 上下文"""
        return cls(
            agent_id=agent_id,
            agent_type=AgentType.TEAM_SUPERVISOR,
            agent_name=agent_name,
            team_name=team_name
        )

    @classmethod
    def worker(cls, agent_id: str, agent_name: str, team_name: str) -> 'CallerContext':
        """创建 Worker 上下文"""
        return cls(
            agent_id=agent_id,
            agent_type=AgentType.WORKER,
            agent_name=agent_name,
            team_name=team_name
        )

    def to_source_dict(self) -> Dict[str, Any]:
        """转换为 source 字典（新版事件格式）"""
        return {
            'agent_id': self.agent_id,
            'agent_type': self.agent_type.value if isinstance(self.agent_type, AgentType) else self.agent_type,
            'agent_name': self.agent_name,
            'team_name': self.team_name
        }

    def to_db_fields(self) -> Dict[str, Any]:
        """转换为数据库字段（用于持久化）"""
        return {
            'agent_id': self.agent_id,
            'agent_type': self.agent_type.value if isinstance(self.agent_type, AgentType) else self.agent_type,
            'agent_name': self.agent_name,
            'team_name': self.team_name
        }

    def get_source_label(self) -> str:
        """获取来源标签（用于日志）"""
        if self.agent_type == AgentType.GLOBAL_SUPERVISOR:
            return f"[Global Supervisor: {self.agent_name}]"
        elif self.agent_type == AgentType.TEAM_SUPERVISOR:
            return f"[Team: {self.team_name} | Supervisor: {self.agent_name}]"
        elif self.agent_type == AgentType.WORKER:
            return f"[Team: {self.team_name} | Worker: {self.agent_name}]"
        return f"[Agent: {self.agent_id}]"


# 使用 run_id 作为 key 的全局回调注册表，支持跨线程访问
# 因为 strands-agents 内部使用自己的线程池，线程本地存储无法工作
import threading
from contextlib import contextmanager

_callback_registry: Dict[int, Callable[[Dict[str, Any]], None]] = {}
_checker_registry: Dict[int, Callable[[], bool]] = {}
_registry_lock = threading.Lock()

# 当前 run_id 上下文（用于在不知道 run_id 时查找回调）
_current_run_id: Dict[int, int] = {}  # 执行线程 ID -> run_id



def set_current_run_id(run_id: int):
    """设置当前执行线程的 run_id"""
    _current_run_id[threading.current_thread().ident] = run_id


def get_current_run_id() -> Optional[int]:
    """获取当前执行线程的 run_id"""
    return _current_run_id.get(threading.current_thread().ident)


def clear_current_run_id():
    """清除当前执行线程的 run_id"""
    _current_run_id.pop(threading.current_thread().ident, None)


def register_event_callback(run_id: int, callback: Optional[Callable[[Dict[str, Any]], None]]):
    """
    注册指定 run 的事件回调

    Args:
        run_id: 运行 ID
        callback: 回调函数，None 表示注销
    """
    with _registry_lock:
        if callback is None:
            _callback_registry.pop(run_id, None)
        else:
            _callback_registry[run_id] = callback


def get_event_callback(run_id: int) -> Optional[Callable[[Dict[str, Any]], None]]:
    """获取指定 run 的事件回调"""
    with _registry_lock:
        return _callback_registry.get(run_id)


def register_cancellation_checker(run_id: int, checker: Optional[Callable[[], bool]]):
    """
    注册指定 run 的取消检查器

    Args:
        run_id: 运行 ID
        checker: 检查函数，返回 True 表示已取消
    """
    with _registry_lock:
        if checker is None:
            _checker_registry.pop(run_id, None)
        else:
            _checker_registry[run_id] = checker


def get_cancellation_checker(run_id: int) -> Optional[Callable[[], bool]]:
    """获取指定 run 的取消检查器"""
    with _registry_lock:
        return _checker_registry.get(run_id)


# 兼容旧 API（用于不知道 run_id 的场景）
def set_global_event_callback(callback: Optional[Callable[[Dict[str, Any]], None]]):
    """兼容旧 API - 设置当前线程 run 的回调"""
    run_id = get_current_run_id()
    if run_id is not None:
        register_event_callback(run_id, callback)


def get_global_event_callback() -> Optional[Callable[[Dict[str, Any]], None]]:
    """兼容旧 API - 获取当前线程 run 的回调"""
    run_id = get_current_run_id()
    if run_id is not None:
        return get_event_callback(run_id)
    return None


def set_global_cancellation_checker(checker: Optional[Callable[[], bool]]):
    """兼容旧 API - 设置当前线程 run 的取消检查器"""
    run_id = get_current_run_id()
    if run_id is not None:
        register_cancellation_checker(run_id, checker)


def get_global_cancellation_checker() -> Optional[Callable[[], bool]]:
    """兼容旧 API - 获取当前线程 run 的取消检查器"""
    run_id = get_current_run_id()
    if run_id is not None:
        return get_cancellation_checker(run_id)
    return None


def check_cancellation():
    """
    检查是否已取消

    如果已取消，抛出 InterruptedError
    """
    run_id = get_current_run_id()
    if run_id is not None:
        checker = get_cancellation_checker(run_id)
        if checker and checker():
            raise InterruptedError("Run was cancelled")


class LLMCallbackHandler:
    """
    LLM 回调处理器 - 带有调用者身份追踪

    用于 strands-agents 的 callback_handler 参数
    """

    def __init__(
        self,
        caller_context: CallerContext,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        verbose: bool = False,
        run_id: Optional[int] = None
    ):
        """
        初始化回调处理器

        Args:
            caller_context: 调用者上下文（标识谁在调用 LLM）
            event_callback: 事件回调函数，如果为 None 则使用注册表查找
            verbose: 是否打印详细信息
            run_id: 运行 ID，用于从注册表查找回调（跨线程场景）
        """
        self.caller_context = caller_context
        self.event_callback = event_callback
        self.verbose = verbose
        self.run_id = run_id  # 存储 run_id 以便跨线程查找回调
        self.tool_count = 0
        self.previous_tool_use = None
        self._buffer = []  # 缓冲区，用于累积文本

    def __call__(self, **kwargs: Any) -> None:
        """
        处理 LLM 回调事件

        Args:
            **kwargs: 回调事件数据，包括：
                - reasoningText: 推理文本
                - data: 流式输出的文本内容
                - complete: 是否为最后一个 chunk
                - current_tool_use: 当前工具调用信息

        Raises:
            InterruptedError: 如果运行已被取消
        """
        # 检查是否已取消（使用 run_id 查找）
        if self.run_id is not None:
            checker = get_cancellation_checker(self.run_id)
            if checker and checker():
                raise InterruptedError("Run was cancelled")

        reasoning_text = kwargs.get("reasoningText", "")
        data = kwargs.get("data", "")
        complete = kwargs.get("complete", False)
        current_tool_use = kwargs.get("current_tool_use", {})

        # 获取有效的事件回调（优先使用显式传入的，其次使用 run_id 查找）
        callback = self.event_callback
        if callback is None and self.run_id is not None:
            callback = get_event_callback(self.run_id)

        # 处理推理文本
        if reasoning_text:
            if self.verbose:
                print(reasoning_text, end="")
            if callback:
                self._emit_event(
                    callback,
                    EventCategory.LLM,
                    EventAction.REASONING,
                    {'content': reasoning_text}
                )

        # 处理输出数据（实时发射）
        if data:
            self._buffer.append(data)
            if self.verbose:
                print(data, end="" if not complete else "\n")
            # 实时发射 LLM 输出片段
            if callback and len(data.strip()) > 0:
                self._emit_event(
                    callback,
                    EventCategory.LLM,
                    EventAction.STREAM,
                    {'content': data}
                )

        # 处理工具调用
        if current_tool_use and current_tool_use.get("name"):
            if self.previous_tool_use != current_tool_use:
                self.previous_tool_use = current_tool_use
                self.tool_count += 1
                tool_name = current_tool_use.get("name", "Unknown")
                if self.verbose:
                    print(f"\nTool #{self.tool_count}: {tool_name}")
                if callback:
                    self._emit_event(
                        callback,
                        EventCategory.LLM,
                        EventAction.TOOL_CALL,
                        {
                            'tool_name': tool_name,
                            'tool_count': self.tool_count
                        }
                    )

        # 完成时清空缓冲区并发送 llm.completed 事件
        if complete:
            self._buffer = []
            if self.verbose and data:
                print("\n")
            # 发送 llm.completed 事件，用于 SSEManager 在调用 tool 时切换活跃 agent
            if callback:
                self._emit_event(
                    callback,
                    EventCategory.LLM,
                    EventAction.COMPLETED,
                    {'message': 'LLM round completed'}
                )

    def _emit_event(
        self,
        callback: Callable,
        category: EventCategory,
        action: EventAction,
        data: Dict[str, Any]
    ):
        """
        发射事件

        事件结构:
        {
            "source": { agent_id, agent_type, agent_name, team_name },
            "event": { category, action },
            "data": { ... }
        }
        """
        event_data = {
            'source': self.caller_context.to_source_dict(),
            'event': {
                'category': category.value,
                'action': action.value
            },
            'data': data
        }
        callback(event_data)


def create_callback_handler(
    caller_context: CallerContext,
    event_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    verbose: bool = False,
    run_id: Optional[int] = None
) -> LLMCallbackHandler:
    """
    创建 LLM 回调处理器

    Args:
        caller_context: 调用者上下文
        event_callback: 事件回调
        verbose: 是否打印详细信息
        run_id: 运行 ID，用于跨线程回调查找

    Returns:
        LLMCallbackHandler 实例
    """
    return LLMCallbackHandler(caller_context, event_callback, verbose, run_id)
