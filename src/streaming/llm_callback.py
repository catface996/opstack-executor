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


# 全局事件回调（由 RunManager 设置）
_global_event_callback: Optional[Callable[[Dict[str, Any]], None]] = None


def set_global_event_callback(callback: Optional[Callable[[Dict[str, Any]], None]]):
    """设置全局事件回调"""
    global _global_event_callback
    _global_event_callback = callback


def get_global_event_callback() -> Optional[Callable[[Dict[str, Any]], None]]:
    """获取全局事件回调"""
    return _global_event_callback


class LLMCallbackHandler:
    """
    LLM 回调处理器 - 带有调用者身份追踪

    用于 strands-agents 的 callback_handler 参数
    """

    def __init__(
        self,
        caller_context: CallerContext,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        verbose: bool = False
    ):
        """
        初始化回调处理器

        Args:
            caller_context: 调用者上下文（标识谁在调用 LLM）
            event_callback: 事件回调函数，如果为 None 则使用全局回调
            verbose: 是否打印详细信息
        """
        self.caller_context = caller_context
        self.event_callback = event_callback
        self.verbose = verbose
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
        """
        reasoning_text = kwargs.get("reasoningText", "")
        data = kwargs.get("data", "")
        complete = kwargs.get("complete", False)
        current_tool_use = kwargs.get("current_tool_use", {})

        # 获取有效的事件回调
        callback = self.event_callback or get_global_event_callback()

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

        # 完成时清空缓冲区
        if complete:
            self._buffer = []
            if self.verbose and data:
                print("\n")

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
    verbose: bool = False
) -> LLMCallbackHandler:
    """
    创建 LLM 回调处理器

    Args:
        caller_context: 调用者上下文
        event_callback: 事件回调
        verbose: 是否打印详细信息

    Returns:
        LLMCallbackHandler 实例
    """
    return LLMCallbackHandler(caller_context, event_callback, verbose)
