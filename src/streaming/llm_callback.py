"""
LLM Callback Handler - 追踪 LLM 调用来源

根据调用者身份（Global Supervisor / Team Supervisor / Worker）
生成带有来源标识的 stream event
"""

from typing import Any, Callable, Dict, Optional
from dataclasses import dataclass


@dataclass
class CallerContext:
    """调用者上下文信息"""
    is_global_supervisor: bool = False
    team_name: Optional[str] = None
    is_team_supervisor: bool = False
    worker_name: Optional[str] = None

    @classmethod
    def global_supervisor(cls) -> 'CallerContext':
        """创建 Global Supervisor 上下文"""
        return cls(is_global_supervisor=True)

    @classmethod
    def team_supervisor(cls, team_name: str) -> 'CallerContext':
        """创建 Team Supervisor 上下文"""
        return cls(team_name=team_name, is_team_supervisor=True)

    @classmethod
    def worker(cls, worker_name: str, team_name: str) -> 'CallerContext':
        """创建 Worker 上下文"""
        return cls(team_name=team_name, worker_name=worker_name)

    def to_event_fields(self) -> Dict[str, Any]:
        """转换为事件字段（以 _ 开头的内部字段）"""
        return {
            '_is_global_supervisor': self.is_global_supervisor,
            '_team_name': self.team_name,
            '_is_team_supervisor': self.is_team_supervisor,
            '_worker_name': self.worker_name
        }

    def get_source_label(self) -> str:
        """获取来源标签"""
        if self.is_global_supervisor:
            return "[Global Supervisor]"
        elif self.is_team_supervisor:
            return f"[Team: {self.team_name} | Supervisor]"
        elif self.worker_name:
            return f"[Team: {self.team_name} | Worker: {self.worker_name}]"
        return "[Unknown]"


# 全局事件回调（由 RunManager 设置）
_global_event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None


def set_global_event_callback(callback: Optional[Callable[[str, Dict[str, Any]], None]]):
    """设置全局事件回调"""
    global _global_event_callback
    _global_event_callback = callback


def get_global_event_callback() -> Optional[Callable[[str, Dict[str, Any]], None]]:
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
        event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
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
                self._emit_event(callback, 'llm_reasoning', {
                    'content': reasoning_text
                })

        # 处理输出数据
        if data:
            self._buffer.append(data)
            if self.verbose:
                print(data, end="" if not complete else "\n")

        # 处理工具调用
        if current_tool_use and current_tool_use.get("name"):
            if self.previous_tool_use != current_tool_use:
                self.previous_tool_use = current_tool_use
                self.tool_count += 1
                tool_name = current_tool_use.get("name", "Unknown")
                if self.verbose:
                    print(f"\nTool #{self.tool_count}: {tool_name}")
                if callback:
                    self._emit_event(callback, 'llm_tool_call', {
                        'tool_name': tool_name,
                        'tool_count': self.tool_count
                    })

        # 完成时发送累积的文本
        if complete:
            if self._buffer and callback:
                full_text = ''.join(self._buffer)
                self._emit_event(callback, 'llm_output', {
                    'content': full_text[:2000]  # 限制长度
                })
            self._buffer = []
            if self.verbose and data:
                print("\n")

    def _emit_event(self, callback: Callable, event_type: str, data: Dict[str, Any]):
        """发射带有调用者信息的事件"""
        # 添加来源标识字段
        event_data = {
            **data,
            **self.caller_context.to_event_fields()
        }
        callback(event_type, event_data)


def create_callback_handler(
    caller_context: CallerContext,
    event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
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
