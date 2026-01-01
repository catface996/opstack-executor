"""
动态层级团队系统 (Dynamic Hierarchical Team System)

通过配置文件动态构建多智能体团队，带调用追踪和防重复机制。

核心特性:
- 通用的 Global Supervisor、Team Supervisor 和 Worker Agent
- 配置驱动的拓扑结构
- 动态指定系统提示词、工具、模型
- 调用追踪：记录每个团队的调用历史
- 防重复调用：自动检测并阻止重复调用
- 调用统计：提供详细的调用次数和状态信息
"""

import hashlib
import re
import types
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable, Set
from dataclasses import dataclass, field

from strands import Agent, tool
from strands.models import BedrockModel

from strands_tools import calculator, http_request
from ..streaming.llm_callback import (
    CallerContext, LLMCallbackHandler, create_callback_handler
)
from .output_formatter import (
    print_worker_start, print_worker_thinking, print_worker_complete,
    print_worker_warning, print_worker_error,
    print_team_start, print_team_thinking, print_team_complete, print_team_summary,
    print_team_warning, print_team_error, print_team_duplicate_warning, print_team_dispatch,
    print_global_start, print_global_thinking, print_global_dispatch,
    print_global_summary, print_global_complete,
    set_current_team, OutputFormatter
)


# ============================================================================
# 辅助函数
# ============================================================================

def create_model_from_id(model_id: Optional[str], temperature: float = 0.7, max_tokens: int = 2048) -> Optional[Any]:
    """
    根据 model_id 创建模型实例

    Args:
        model_id: 模型 ID（如 anthropic.claude-3-sonnet-20240229-v1:0）
        temperature: 温度参数
        max_tokens: 最大 token 数

    Returns:
        模型实例，如果 model_id 为 None 则返回 None
    """
    if not model_id:
        return None

    # 创建 BedrockModel
    return BedrockModel(
        model_id=model_id,
        temperature=temperature,
        max_tokens=max_tokens
    )


def generate_deterministic_id(*parts: str) -> str:
    """
    生成确定性 ID

    基于输入的各部分生成一个确定性的短 ID，
    同样的输入始终产生相同的输出。

    Args:
        *parts: 用于生成 ID 的字符串部分

    Returns:
        12 字符的确定性 ID
    """
    combined = ":".join(str(p) for p in parts if p)
    hash_obj = hashlib.sha256(combined.encode('utf-8'))
    return hash_obj.hexdigest()[:12]


# ============================================================================
# 调用追踪系统
# ============================================================================

class ExecutionTracker:
    """
    执行追踪器 - 跟踪已执行的 Team 和 Worker
    
    用于防止重复执行和获取执行结果。
    """
    
    def __init__(self):
        """初始化执行追踪器"""
        # 已执行的团队名称集合
        self.executed_teams: Set[str] = set()
        # 已执行的 Worker 名称集合
        self.executed_workers: Set[str] = set()
        # 团队执行结果字典
        self.team_results: Dict[str, str] = {}
        # Worker 执行结果字典
        self.worker_results: Dict[str, str] = {}
    
    def mark_team_executed(self, team_name: str, result: str):
        """
        标记团队已执行
        
        Args:
            team_name: 团队名称
            result: 执行结果
        """
        self.executed_teams.add(team_name)
        self.team_results[team_name] = result
    
    def mark_worker_executed(self, worker_name: str, result: str):
        """
        标记 Worker 已执行
        
        Args:
            worker_name: Worker 名称
            result: 执行结果
        """
        self.executed_workers.add(worker_name)
        self.worker_results[worker_name] = result
    
    def is_team_executed(self, team_name: str) -> bool:
        """
        检查团队是否已执行
        
        Args:
            team_name: 团队名称
            
        Returns:
            True 如果已执行，否则 False
        """
        return team_name in self.executed_teams
    
    def is_worker_executed(self, worker_name: str) -> bool:
        """
        检查 Worker 是否已执行
        
        Args:
            worker_name: Worker 名称
            
        Returns:
            True 如果已执行，否则 False
        """
        return worker_name in self.executed_workers
    
    def get_team_result(self, team_name: str) -> Optional[str]:
        """
        获取团队的执行结果
        
        Args:
            team_name: 团队名称
            
        Returns:
            执行结果字符串，如果未执行则返回 None
        """
        return self.team_results.get(team_name)
    
    def get_worker_result(self, worker_name: str) -> Optional[str]:
        """
        获取 Worker 的执行结果
        
        Args:
            worker_name: Worker 名称
            
        Returns:
            执行结果字符串，如果未执行则返回 None
        """
        return self.worker_results.get(worker_name)
    
    def get_execution_status(self, available_teams: List[str] = None, available_workers: List[str] = None) -> str:
        """
        获取执行状态摘要
        
        生成格式化的执行状态报告，显示哪些团队/Worker 已执行，哪些未执行。
        
        Args:
            available_teams: 可用的团队名称列表
            available_workers: 可用的 Worker 名称列表
            
        Returns:
            格式化的执行状态字符串
        """
        status_lines = []
        
        # 生成团队执行状态
        if available_teams:
            status_lines.append("【团队执行状态】")
            for team in available_teams:
                if team in self.executed_teams:
                    status_lines.append(f"  ✅ {team} - 已执行")
                else:
                    status_lines.append(f"  ⭕ {team} - 未执行")
        
        # 生成 Worker 执行状态
        if available_workers:
            status_lines.append("\n【成员执行状态】")
            for worker in available_workers:
                if worker in self.executed_workers:
                    status_lines.append(f"  ✅ {worker} - 已执行")
                else:
                    status_lines.append(f"  ⭕ {worker} - 未执行")
        
        return "\n".join(status_lines)
    
    def reset(self):
        """重置追踪器，清空所有执行记录"""
        self.executed_teams.clear()
        self.executed_workers.clear()
        self.team_results.clear()
        self.worker_results.clear()


class CallTracker:
    """
    调用追踪器 - 记录和管理 Agent 调用
    
    跟踪团队调用的历史记录、调用次数和活跃状态。
    """
    
    def __init__(self):
        """初始化调用追踪器"""
        # 调用历史记录列表
        self.call_history: List[Dict[str, Any]] = []
        # 每个团队的调用次数
        self.team_calls: Dict[str, int] = {}
        # 当前正在执行的团队集合
        self.active_teams: Set[str] = set()
        # 执行追踪器实例
        self.execution_tracker = ExecutionTracker()
    
    def start_call(self, team_name: str, task: str) -> str:
        """
        开始一次调用
        
        记录调用开始时间和状态，生成唯一的调用 ID。
        
        Args:
            team_name: 团队名称
            task: 任务描述
            
        Returns:
            调用 ID（格式：团队名_序号）
        """
        # 生成唯一的调用 ID
        call_id = f"{team_name}_{len(self.call_history)}"
        
        # 记录调用信息
        self.call_history.append({
            'call_id': call_id,
            'team_name': team_name,
            'task': task,
            'start_time': datetime.now().isoformat(),
            'status': 'in_progress'
        })
        
        # 更新调用次数
        self.team_calls[team_name] = self.team_calls.get(team_name, 0) + 1
        # 标记团队为活跃状态
        self.active_teams.add(team_name)
        
        return call_id
    
    def end_call(self, call_id: str, result: str):
        """
        结束一次调用
        
        记录调用结束时间和结果，更新状态。
        
        Args:
            call_id: 调用 ID
            result: 执行结果
        """
        # 查找对应的调用记录
        for call in self.call_history:
            if call['call_id'] == call_id:
                # 更新调用记录
                call['end_time'] = datetime.now().isoformat()
                call['result'] = result
                call['status'] = 'completed'
                
                # 从活跃团队中移除
                team_name = call['team_name']
                if team_name in self.active_teams:
                    self.active_teams.remove(team_name)
                break
    
    def is_team_active(self, team_name: str) -> bool:
        """
        检查团队是否正在处理任务
        
        Args:
            team_name: 团队名称
            
        Returns:
            True 如果团队正在执行任务，否则 False
        """
        return team_name in self.active_teams
    
    def get_team_call_count(self, team_name: str) -> int:
        """
        获取团队的调用次数
        
        Args:
            team_name: 团队名称
            
        Returns:
            调用次数
        """
        return self.team_calls.get(team_name, 0)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取调用统计信息
        
        Returns:
            包含总调用次数、各团队调用次数、活跃团队和完成调用数的字典
        """
        return {
            'total_calls': len(self.call_history),
            'team_calls': self.team_calls.copy(),
            'active_teams': list(self.active_teams),
            'completed_calls': sum(1 for c in self.call_history if c['status'] == 'completed')
        }
    
    def get_call_log(self) -> str:
        """
        获取格式化的调用日志
        
        生成包含所有调用记录的格式化字符串。
        
        Returns:
            格式化的调用日志字符串
        """
        log_lines = ["调用日志:", "=" * 60]
        for call in self.call_history:
            log_lines.append(f"\n[{call['call_id']}]")
            log_lines.append(f"  团队: {call['team_name']}")
            log_lines.append(f"  任务: {call['task'][:50]}...")
            log_lines.append(f"  状态: {call['status']}")
            if 'result' in call:
                log_lines.append(f"  结果: {call['result'][:100]}...")
        return "\n".join(log_lines)


# ============================================================================
# 配置数据结构
# ============================================================================

@dataclass
class WorkerConfig:
    """Worker Agent 配置"""
    name: str
    role: str
    system_prompt: str
    id: str
    agent_id: str = ""  # agent_id 用于 stream 事件标识
    user_message: Optional[str] = None  # 预定义的用户消息（优先级：预定义 > 动态生成）
    tools: List[Any] = field(default_factory=list)
    model: Optional[Any] = None
    temperature: float = 0.7
    max_tokens: int = 2048
    model_id: Optional[str] = None  # LLM 模型 ID，如 gemini-2.0-flash


@dataclass
class TeamConfig:
    """Team 配置"""
    name: str
    system_prompt: str  # Team Supervisor 的系统提示词
    workers: List[WorkerConfig]
    id: str
    agent_id: str = ""  # Team Supervisor 的 agent_id
    user_message: Optional[str] = None  # 预定义的用户消息（优先级：预定义 > 动态生成）
    model: Optional[Any] = None
    prevent_duplicate: bool = True
    share_context: bool = False  # 是否接收其他团队的上下文
    temperature: float = 0.7
    max_tokens: int = 2048
    model_id: Optional[str] = None  # Team Supervisor LLM 模型 ID


@dataclass
class GlobalConfig:
    """Global Supervisor 配置"""
    system_prompt: str
    teams: List[TeamConfig]
    id: str
    agent_id: str = ""  # Global Supervisor 的 agent_id
    user_message: Optional[str] = None  # 预定义的用户消息（优先级：task > 预定义）
    model: Optional[Any] = None
    enable_tracking: bool = True
    enable_context_sharing: bool = False  # 全局开关：是否启用跨团队上下文共享
    parallel_execution: bool = False  # 团队执行模式：False=顺序执行，True=并行执行
    temperature: float = 0.7
    max_tokens: int = 2048
    model_id: Optional[str] = None  # Global Supervisor LLM 模型 ID


# ============================================================================
# Worker Agent 工厂
# ============================================================================

class WorkerAgentFactory:
    """
    Worker Agent 工厂 - 动态创建 Worker Agent

    负责创建 Worker Agent 实例，并管理 Worker 的调用追踪和防重复机制。
    """

    # 类级别的调用追踪器（记录任务哈希 -> 结果）
    _worker_call_tracker = {}
    # 类级别的执行追踪器引用
    _execution_tracker: Optional['ExecutionTracker'] = None
    # 类级别的 run_id（用于跨线程回调查找）
    _current_run_id: Optional[int] = None

    @staticmethod
    def set_current_run_id(run_id: Optional[int]):
        """设置当前 run_id（用于跨线程回调查找）"""
        WorkerAgentFactory._current_run_id = run_id

    @staticmethod
    def set_execution_tracker(tracker: 'ExecutionTracker'):
        """
        设置执行追踪器
        
        Args:
            tracker: ExecutionTracker 实例
        """
        WorkerAgentFactory._execution_tracker = tracker
    
    @staticmethod
    def _check_worker_executed(config: WorkerConfig) -> Optional[str]:
        """
        检查 Worker 是否已执行
        
        如果 Worker 已经执行过，返回提示消息；否则返回 None。
        
        Args:
            config: Worker 配置
            
        Returns:
            提示消息字符串或 None
        """
        if WorkerAgentFactory._execution_tracker and WorkerAgentFactory._execution_tracker.is_worker_executed(config.name):
            print_worker_warning(f"⚠️ [{config.name}] 该专家已经执行过，请直接使用之前的结果，不要重复调用")
            return OutputFormatter.format_executed_message(config.name)
        return None
    
    @staticmethod
    def _check_duplicate_task(config: WorkerConfig, task: str) -> Optional[str]:
        """
        检查是否重复任务
        
        基于任务内容的哈希值检查是否已经处理过相同任务。
        
        Args:
            config: Worker 配置
            task: 任务描述
            
        Returns:
            如果是重复任务，返回提示消息；否则返回 call_key
        """
        # 生成任务哈希值（前8位）
        task_hash = hashlib.md5(task.encode('utf-8')).hexdigest()[:8]
        call_key = f"{config.name}_{task_hash}"
        
        # 检查是否已处理过相同任务
        if call_key in WorkerAgentFactory._worker_call_tracker:
            OutputFormatter.print_worker_duplicate_task_warning(config.name)
            return OutputFormatter.format_duplicate_task_message(config.name)
        return call_key
    
    @staticmethod
    def _execute_worker(config: WorkerConfig, task: str, call_key: str) -> str:
        """
        执行 Worker 任务

        创建 Agent 实例并执行任务，记录执行结果。

        Args:
            config: Worker 配置
            task: 任务描述
            call_key: 调用标识符

        Returns:
            执行结果字符串
        """
        # 获取当前团队上下文
        current_team = OutputFormatter.get_current_team()

        # Team Supervisor 发出调度消息
        if current_team:
            print_team_dispatch(current_team, config.name)

        # 打印开始信息
        print_worker_start(config.name, task, current_team)
        print_worker_thinking(config.name, current_team)

        # 创建回调处理器（Worker 上下文，使用 agent_id，传入 run_id 支持跨线程）
        callback_handler = create_callback_handler(
            CallerContext.worker(config.agent_id or config.id, config.name, current_team or "Unknown"),
            run_id=WorkerAgentFactory._current_run_id
        )

        # 确定使用的模型：优先使用 model_id 创建模型，其次使用 config.model
        model = config.model
        if config.model_id:
            model = create_model_from_id(config.model_id, config.temperature, config.max_tokens)

        # 创建并执行 Agent
        # 注意：Agent 串行化已在 SSEManager 的事件发射层实现，无需在此加锁
        agent = Agent(
            system_prompt=config.system_prompt,
            tools=config.tools,
            model=model,
            callback_handler=callback_handler,
        )
        response = agent(task)

        # 打印完成信息
        print_worker_complete(config.name, current_team)

        # 发送 agent.completed 事件（用于 SSEManager 的串行化切换）
        from ..streaming.llm_callback import get_event_callback
        from .api_models import EventCategory, EventAction
        event_callback = get_event_callback(WorkerAgentFactory._current_run_id) if WorkerAgentFactory._current_run_id else None
        if event_callback:
            event_callback({
                'source': callback_handler.caller_context.to_source_dict(),
                'event': {
                    'category': EventCategory.AGENT.value,
                    'action': EventAction.COMPLETED.value
                },
                'data': {'message': f'Worker {config.name} completed'}
            })

        # 将 AgentResult 转为字符串
        response_text = str(response) if response else ""
        result = OutputFormatter.format_result_message(config.name, response_text)

        # 记录执行结果
        WorkerAgentFactory._worker_call_tracker[call_key] = result
        if WorkerAgentFactory._execution_tracker:
            WorkerAgentFactory._execution_tracker.mark_worker_executed(config.name, result)

        return result
    
    @staticmethod
    def create_worker(config: WorkerConfig) -> Callable:
        """
        创建 Worker Agent

        根据配置创建一个 Worker Agent 函数，该函数会：
        1. 检查是否已执行
        2. 检查是否重复任务
        3. 执行任务并返回结果

        Args:
            config: Worker 配置

        Returns:
            Worker Agent 函数（已应用 @tool 装饰器）
        """
        # 生成符合 AWS Bedrock 规范的函数名（使用 worker ID 确保唯一性）
        func_name = f"worker_{config.id.replace('-', '_')}"

        def worker_agent_impl(task: str) -> str:
            # 1. 检查是否已执行
            if executed_msg := WorkerAgentFactory._check_worker_executed(config):
                return executed_msg

            # 2. 检查重复任务
            call_key = WorkerAgentFactory._check_duplicate_task(config, task)
            if isinstance(call_key, str) and call_key.startswith('['):
                return call_key  # 返回重复消息

            # 3. 执行任务
            try:
                return WorkerAgentFactory._execute_worker(config, task, call_key)
            except Exception as e:
                error_msg = f"[{config.name}] 错误: {str(e)}"
                print_worker_error(error_msg)
                return error_msg

        # 创建具有正确名称的函数（在应用 @tool 装饰器之前）
        doc_string = f"调用 {config.name} ({config.role}) 来执行任务"
        worker_agent = types.FunctionType(
            worker_agent_impl.__code__,
            worker_agent_impl.__globals__,
            name=func_name,
            argdefs=worker_agent_impl.__defaults__,
            closure=worker_agent_impl.__closure__
        )
        worker_agent.__doc__ = doc_string

        # 应用 @tool 装饰器
        return tool(worker_agent)
    
    @staticmethod
    def reset_tracker():
        """重置调用追踪器，清空所有调用记录"""
        WorkerAgentFactory._worker_call_tracker.clear()


# ============================================================================
# Team Supervisor 工厂
# ============================================================================

class TeamSupervisorFactory:
    """Team Supervisor 工厂 - 动态创建 Team Supervisor"""
    
    @staticmethod
    def _build_context_sharing_content(
        config: TeamConfig,
        tracker: CallTracker,
        enable_context_sharing: bool
    ) -> List[str]:
        """
        构建跨团队上下文共享内容
        
        Args:
            config: 团队配置
            tracker: 调用追踪器
            enable_context_sharing: 是否启用上下文共享
            
        Returns:
            上下文共享内容列表（可能为空）
        """
        if not enable_context_sharing or not config.share_context:
            return []
        
        other_teams_context = []
        for team_name in tracker.execution_tracker.executed_teams:
            if team_name != config.name:  # 排除自己
                result = tracker.execution_tracker.get_team_result(team_name)
                if result:
                    other_teams_context.append(f"\n【{team_name}的研究成果】：\n{result}")
        
        if other_teams_context:
            return [
                "\n".join(other_teams_context),
                "\n【提示】：以上是其他团队已完成的工作，你可以参考这些成果来完成你的任务。"
            ]
        
        return []
    
    @staticmethod
    def _check_team_executed(config: TeamConfig, tracker: CallTracker) -> Optional[str]:
        """
        检查团队是否已执行
        
        如果团队已经执行过，返回提示消息；否则返回 None。
        
        Args:
            config: 团队配置
            tracker: 调用追踪器
            
        Returns:
            提示消息字符串或 None
        """
        if tracker.execution_tracker.is_team_executed(config.name):
            print_team_warning(f"⚠️ [{config.name}] 该团队已经执行过，请直接使用之前的结果，不要重复调用")
            return OutputFormatter.format_executed_message(config.name)
        return None
    
    @staticmethod
    def _check_team_active(config: TeamConfig, tracker: CallTracker) -> Optional[str]:
        """
        检查团队是否正在执行
        
        如果团队正在执行且启用了防重复机制，返回警告消息；否则返回 None。
        
        Args:
            config: 团队配置
            tracker: 调用追踪器
            
        Returns:
            警告消息字符串或 None
        """
        if config.prevent_duplicate and tracker.is_team_active(config.name):
            message = f"[{config.name}] 警告: 该团队正在处理任务，跳过重复调用"
            print_team_duplicate_warning(message)
            return message
        return None
    
    @staticmethod
    def _build_enhanced_task(
        task: str,
        worker_names: List[str],
        tracker: CallTracker,
        config: TeamConfig,
        enable_context_sharing: bool
    ) -> str:
        """
        构建增强任务内容
        
        将原始任务与执行状态、上下文共享内容和规则组合成增强任务。
        
        Args:
            task: 原始任务描述
            worker_names: Worker 名称列表
            tracker: 调用追踪器
            config: 团队配置
            enable_context_sharing: 是否启用上下文共享
            
        Returns:
            增强后的任务字符串
        """
        # 获取执行状态
        execution_status = tracker.execution_tracker.get_execution_status(available_workers=worker_names)
        enhanced_task_parts = [task, "", execution_status]
        
        # 添加上下文共享内容（如果启用）
        context_sharing_content = TeamSupervisorFactory._build_context_sharing_content(
            config, tracker, enable_context_sharing
        )
        if context_sharing_content:
            enhanced_task_parts.insert(1, context_sharing_content[0])
            enhanced_task_parts.append(context_sharing_content[1])
        
        # 获取团队名称用于标签
        team_name = config.name
        worker_list = ", ".join(worker_names)
        num_workers = len(worker_names)

        # 添加执行规则 - 严格单工具调用限制
        enhanced_task_parts.append(f"""
================================================================================
CRITICAL INSTRUCTIONS FOR TEAM SUPERVISOR - STRICT SEQUENTIAL EXECUTION
================================================================================

You are the TEAM SUPERVISOR of [{team_name}].
Your ONLY job is to delegate tasks to your team members (workers).

[ABSOLUTE RULES - VIOLATION IS FORBIDDEN]

1. You must NEVER answer questions directly. NO EXCEPTIONS.
2. You must ALWAYS call worker tools to handle the task.
3. Each worker can ONLY be called ONCE.
4. You MUST call EVERY worker ({num_workers} total).

[YOUR TEAM MEMBERS]
{worker_list}

================================================================================
⛔⛔⛔ STRICT SINGLE TOOL CALL RULE ⛔⛔⛔
================================================================================

**ABSOLUTE REQUIREMENT: You can ONLY call ONE tool per response!**

After calling a tool, you MUST:
1. STOP generating any more content
2. WAIT for the tool result to come back
3. Only AFTER receiving the result, continue with next action

❌ FORBIDDEN: Calling multiple tools in one response
❌ FORBIDDEN: Continuing to write after a tool call
❌ FORBIDDEN: Planning next steps before seeing tool result

✅ CORRECT: Call ONE tool → STOP → Wait for result → Then respond again

================================================================================
MANDATORY WORKFLOW - ONE TOOL CALL THEN STOP
================================================================================

**Each response should follow this pattern:**

[Team: {team_name} | Supervisor] THINKING: <brief analysis>
[Team: {team_name} | Supervisor] SELECT: <worker name>
<call the worker tool>
<STOP HERE - DO NOT WRITE ANYTHING ELSE>

**After receiving the tool result, in your NEXT response:**
- Analyze the result
- If more workers needed: repeat the pattern above
- If all workers done: output SUMMARY

================================================================================
EXECUTION STATUS
================================================================================
- Workers marked ⭕ = NOT executed yet (you MUST call these)
- Workers marked ✅ = Already completed (do NOT call again)

================================================================================
FAILURE CONDITIONS
================================================================================
- ❌ Calling multiple tools in one response
- ❌ Writing content after a tool call (must STOP immediately)
- ❌ Skipping any worker marked ⭕
- ❌ Answering directly without calling workers
""")
        
        return "\n".join(enhanced_task_parts)
    
    @staticmethod
    def create_supervisor(config: TeamConfig, tracker: CallTracker, enable_context_sharing: bool = False) -> Callable:
        """
        创建 Team Supervisor
        
        根据配置创建一个 Team Supervisor 函数，该函数会：
        1. 检查团队是否已执行
        2. 检查团队是否正在执行
        3. 协调 Worker 完成任务
        
        Args:
            config: 团队配置
            tracker: 调用追踪器
            enable_context_sharing: 是否启用跨团队上下文共享
            
        Returns:
            Team Supervisor 函数（已应用 @tool 装饰器）
        """
        # 创建 Worker 工具列表
        worker_tools = [WorkerAgentFactory.create_worker(w) for w in config.workers]
        # 生成符合 AWS Bedrock 规范的函数名
        func_name = f"team_{config.id.replace('-', '_')}"
        
        def team_supervisor_impl(task: str) -> str:
            """Team Supervisor 实现函数"""
            # 1. 检查是否已执行
            if executed_msg := TeamSupervisorFactory._check_team_executed(config, tracker):
                return executed_msg

            # 2. 检查是否正在执行
            if active_msg := TeamSupervisorFactory._check_team_active(config, tracker):
                return active_msg

            # 3. Global Supervisor 发出调度消息
            print_global_dispatch(config.name)

            # 4. 开始执行
            call_id = tracker.start_call(config.name, task)

            try:
                # 5. 准备执行（打印开始信息）
                worker_names = [w.name for w in config.workers]
                team_agent_id = config.agent_id or config.id
                print_team_start(config.name, call_id, task, worker_names, agent_id=team_agent_id)
                print_team_thinking(config.name, agent_id=team_agent_id)

                # 6. 构建增强任务
                enhanced_task = TeamSupervisorFactory._build_enhanced_task(
                    task, worker_names, tracker, config, enable_context_sharing
                )

                # 7. 创建回调处理器（Team Supervisor 上下文，使用 agent_id，传入 run_id 支持跨线程）
                team_callback_handler = create_callback_handler(
                    CallerContext.team_supervisor(config.agent_id or config.id, f"{config.name}主管", config.name),
                    run_id=WorkerAgentFactory._current_run_id
                )

                # 确定使用的模型：优先使用 model_id 创建模型，其次使用 config.model
                model = config.model
                if config.model_id:
                    model = create_model_from_id(config.model_id, config.temperature, config.max_tokens)

                # 8. 创建 Agent
                supervisor = Agent(
                    system_prompt=config.system_prompt,
                    tools=worker_tools,
                    model=model,
                    callback_handler=team_callback_handler
                )

                # 执行任务
                response = supervisor(enhanced_task)

                # 9. 完成执行（记录结果）
                print_team_complete(config.name, agent_id=team_agent_id)

                # 发送 agent.completed 事件
                from ..streaming.llm_callback import get_event_callback
                from .api_models import EventCategory, EventAction
                event_callback = get_event_callback(WorkerAgentFactory._current_run_id) if WorkerAgentFactory._current_run_id else None
                if event_callback:
                    event_callback({
                        'source': team_callback_handler.caller_context.to_source_dict(),
                        'event': {
                            'category': EventCategory.AGENT.value,
                            'action': EventAction.COMPLETED.value
                        },
                        'data': {'message': f'Team Supervisor {config.name} completed'}
                    })

                # 将 AgentResult 转为字符串
                response_text = str(response) if response else ""
                result = OutputFormatter.format_result_message(config.name, response_text)
                tracker.end_call(call_id, result)
                tracker.execution_tracker.mark_team_executed(config.name, result)

                return result

            except Exception as e:
                # 处理异常
                error_msg = f"[{config.name}] 错误: {str(e)}"
                print_team_error(error_msg)
                tracker.end_call(call_id, error_msg)
                return error_msg
        
        # 创建具有正确名称的函数
        doc_string = f"调用{config.name} - 协调 {len(config.workers)} 名团队成员完成任务"
        team_supervisor = types.FunctionType(
            team_supervisor_impl.__code__,
            team_supervisor_impl.__globals__,
            name=func_name,
            argdefs=team_supervisor_impl.__defaults__,
            closure=team_supervisor_impl.__closure__
        )
        team_supervisor.__doc__ = doc_string
        
        # 应用 @tool 装饰器
        return tool(team_supervisor)


# ============================================================================
# Global Supervisor 工厂
# ============================================================================

class GlobalSupervisorFactory:
    """
    Global Supervisor 工厂 - 动态创建 Global Supervisor
    
    负责创建全局协调者，管理多个团队的协作。
    """
    
    @staticmethod
    def create_global_supervisor(config: GlobalConfig, tracker: CallTracker) -> tuple[Agent, List[str]]:
        """
        创建 Global Supervisor
        
        根据配置创建全局协调者 Agent，负责协调多个团队完成复杂任务。
        
        Args:
            config: 全局配置
            tracker: 调用追踪器
            
        Returns:
            (Global Supervisor Agent, 团队名称列表)
        """
        # 创建所有团队的 Supervisor 工具
        team_tools = [
            TeamSupervisorFactory.create_supervisor(team_config, tracker, config.enable_context_sharing)
            for team_config in config.teams
        ]
        
        # 提取团队名称列表
        team_names = [team.name for team in config.teams]
        
        # Build team list for prompt
        team_list_str = "\n".join([f"  - {team.name}" for team in config.teams])

        # Enhanced system prompt with STRICT single tool call constraint
        execution_mode = "SEQUENTIAL" if not config.parallel_execution else "PARALLEL"

        enhanced_prompt = f"""{config.system_prompt}

================================================================================
CRITICAL INSTRUCTIONS - STRICT SEQUENTIAL EXECUTION
================================================================================

You are a COORDINATOR/DISPATCHER. Your ONLY job is to delegate tasks to teams.

[ABSOLUTE RULES - VIOLATION IS FORBIDDEN]

1. You must NEVER answer questions directly. NO EXCEPTIONS.
2. You must ALWAYS call team tools to handle the task.
3. Even if the task is unclear, you MUST select the most appropriate team(s).
4. You are NOT allowed to ask clarifying questions - just delegate to teams.
5. You must call ALL available teams - not just one or two.

[EXECUTION MODE: {execution_mode}]

- Each team can ONLY be called ONCE
- Teams marked with ✅ are already completed - do NOT call them again
- Only call teams marked with ⭕ (not executed)

[AVAILABLE TEAMS]
{team_list_str}

================================================================================
⛔⛔⛔ STRICT SINGLE TOOL CALL RULE ⛔⛔⛔
================================================================================

**ABSOLUTE REQUIREMENT: You can ONLY call ONE tool per response!**

After calling a tool, you MUST:
1. STOP generating any more content immediately
2. WAIT for the tool result to come back
3. Only AFTER receiving the result, continue with next action in a NEW response

❌ FORBIDDEN: Calling multiple tools in one response
❌ FORBIDDEN: Continuing to write after a tool call
❌ FORBIDDEN: Planning next steps before seeing tool result

✅ CORRECT: Call ONE tool → STOP → Wait for result → Then respond again

================================================================================
MANDATORY WORKFLOW - ONE TOOL CALL THEN STOP
================================================================================

**Each response should follow this pattern:**

[Global Supervisor] THINKING: <brief analysis of current status>
[Global Supervisor] SELECT: <team name>
<call the team tool>
<STOP HERE - DO NOT WRITE ANYTHING ELSE>

**After receiving the tool result, in your NEXT response:**
- Review the result briefly
- If more teams marked ⭕: repeat the pattern above
- If all teams are ✅: output SYNTHESIS with final summary

================================================================================
FAILURE CONDITIONS
================================================================================
- ❌ Calling multiple tools in one response
- ❌ Writing content after a tool call (must STOP immediately)
- ❌ Skipping any team marked ⭕
- ❌ Answering directly without calling teams

[CRITICAL REMINDER]
- You are a COORDINATOR, not an executor
- You must call ALL teams eventually, one at a time
- After each tool call, STOP and wait for the result
"""
        
        # 创建回调处理器（Global Supervisor 上下文，使用 agent_id，传入 run_id 支持跨线程）
        global_callback_handler = create_callback_handler(
            CallerContext.global_supervisor(config.agent_id or config.id),
            run_id=WorkerAgentFactory._current_run_id
        )

        # 确定使用的模型：优先使用 model_id 创建模型，其次使用 config.model
        model = config.model
        if config.model_id:
            model = create_model_from_id(config.model_id, config.temperature, config.max_tokens)

        # 创建 Global Supervisor Agent
        # 注意：并行/顺序执行主要通过系统提示词来引导 Agent 的行为
        global_supervisor = Agent(
            system_prompt=enhanced_prompt,
            tools=team_tools,
            model=model,
            callback_handler=global_callback_handler
        )

        return global_supervisor, team_names
    
    @staticmethod
    def stream_global_supervisor(agent: Agent, task: str, tracker: CallTracker, team_names: List[str], global_agent_id: str = None):
        """
        执行 Global Supervisor 并输出工作过程

        执行全局协调者的任务，并打印执行过程和状态。

        Args:
            agent: Global Supervisor Agent
            task: 任务描述
            tracker: 调用追踪器
            team_names: 团队名称列表
            global_agent_id: Global Supervisor 的 agent_id

        Returns:
            执行结果字符串
        """
        # 1. 打印开始分析
        print_global_start(task, agent_id=global_agent_id)
        print_global_thinking(agent_id=global_agent_id)
        
        # 2. 获取团队执行状态
        execution_status = tracker.execution_tracker.get_execution_status(available_teams=team_names)
        
        # 3. 构建增强任务（添加执行状态和规则）
        enhanced_task = f"""
================================================================================
USER TASK
================================================================================
{task}

================================================================================
TEAM EXECUTION STATUS
================================================================================
{execution_status}

================================================================================
EXECUTION REMINDER
================================================================================
- Teams marked ⭕ = NOT executed yet (you MUST call these)
- Teams marked ✅ = Already completed (do NOT call again)
- You MUST call at least one team - direct answers are FORBIDDEN
- Follow the MANDATORY WORKFLOW: ANALYZE → DISPATCH → SYNTHESIZE
"""
        
        # 4. 执行任务
        # 注意：不在 Global Supervisor 层加锁，因为它调用的 Team tools 可能在不同线程执行
        # 锁只加在 Team Supervisor 和 Worker 层
        response = agent(enhanced_task)

        # 5. 打印完成分析
        print_global_complete(agent_id=global_agent_id)

        # 发送 agent.completed 事件（用于 SSEManager 的串行化切换）
        from ..streaming.llm_callback import get_event_callback
        from .api_models import EventCategory, EventAction
        event_callback = get_event_callback(WorkerAgentFactory._current_run_id) if WorkerAgentFactory._current_run_id else None
        if event_callback:
            event_callback({
                'source': CallerContext.global_supervisor(global_agent_id or 'global').to_source_dict(),
                'event': {
                    'category': EventCategory.AGENT.value,
                    'action': EventAction.COMPLETED.value
                },
                'data': {'message': 'Global Supervisor completed'}
            })

        # 将 AgentResult 转为字符串返回
        return str(response) if response else ""


# ============================================================================
# 配置构建器
# ============================================================================

class HierarchyBuilder:
    """
    层级团队构建器 - 提供流式 API 构建配置
    
    使用构建器模式创建层级团队系统，支持链式调用。
    
    示例:
        builder = HierarchyBuilder()
        agent, tracker, teams = (
            builder
            .set_global_prompt("全局协调者提示词")
            .add_team("团队1", "团队1提示词", workers=[...])
            .add_team("团队2", "团队2提示词", workers=[...])
            .build()
        )
    """
    
    def __init__(self, enable_tracking: bool = True, enable_context_sharing: bool = False, parallel_execution: bool = False):
        """
        初始化构建器

        Args:
            enable_tracking: 是否启用调用追踪
            enable_context_sharing: 是否启用跨团队上下文共享
            parallel_execution: 团队执行模式（False=顺序执行，True=并行执行）
        """
        self.teams: List[TeamConfig] = []
        self.global_system_prompt: str = ""
        self.global_user_message: Optional[str] = None
        self.global_model: Optional[Any] = None
        self.global_agent_id: str = ""  # Global Supervisor 的 agent_id
        self.global_temperature: float = 0.7  # Global Supervisor LLM 温度参数
        self.global_max_tokens: int = 2048  # Global Supervisor LLM 最大 token 数
        self.global_model_id: Optional[str] = None  # Global Supervisor LLM 模型 ID
        self.enable_tracking = enable_tracking
        self.enable_context_sharing = enable_context_sharing
        self.parallel_execution = parallel_execution
        self.tracker = CallTracker() if enable_tracking else None

    def set_global_system_prompt(self, prompt: str) -> 'HierarchyBuilder':
        """
        设置全局协调者的系统提示词

        Args:
            prompt: 系统提示词

        Returns:
            self（支持链式调用）
        """
        self.global_system_prompt = prompt
        return self

    def set_global_user_message(self, user_message: str) -> 'HierarchyBuilder':
        """
        设置全局协调者的预定义用户消息

        Args:
            user_message: 用户消息

        Returns:
            self（支持链式调用）
        """
        self.global_user_message = user_message
        return self

    def set_global_agent_id(self, agent_id: str) -> 'HierarchyBuilder':
        """
        设置全局协调者的 agent_id

        Args:
            agent_id: agent_id 标识符

        Returns:
            self（支持链式调用）
        """
        self.global_agent_id = agent_id
        return self
    
    def set_global_model(self, model: Any) -> 'HierarchyBuilder':
        """
        设置全局协调者的模型

        Args:
            model: 模型实例

        Returns:
            self（支持链式调用）
        """
        self.global_model = model
        return self

    def set_global_temperature(self, temperature: float) -> 'HierarchyBuilder':
        """
        设置全局协调者的 LLM 温度参数

        Args:
            temperature: 温度参数 (0.0-2.0)

        Returns:
            self（支持链式调用）
        """
        self.global_temperature = temperature
        return self

    def set_global_max_tokens(self, max_tokens: int) -> 'HierarchyBuilder':
        """
        设置全局协调者的 LLM 最大 token 数

        Args:
            max_tokens: 最大 token 数

        Returns:
            self（支持链式调用）
        """
        self.global_max_tokens = max_tokens
        return self

    def set_global_model_id(self, model_id: str) -> 'HierarchyBuilder':
        """
        设置全局协调者的 LLM 模型 ID

        Args:
            model_id: 模型 ID，如 gemini-2.0-flash

        Returns:
            self（支持链式调用）
        """
        self.global_model_id = model_id
        return self

    def set_parallel_execution(self, parallel: bool) -> 'HierarchyBuilder':
        """
        设置团队执行模式
        
        Args:
            parallel: True=并行执行，False=顺序执行（默认）
            
        Returns:
            self（支持链式调用）
        """
        self.parallel_execution = parallel
        return self
    
    def add_team(
        self,
        name: str,
        system_prompt: str,
        workers: List[Dict[str, Any]],
        agent_id: str = "",
        user_message: Optional[str] = None,
        model: Optional[Any] = None,
        prevent_duplicate: bool = True,
        share_context: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        model_id: Optional[str] = None
    ) -> 'HierarchyBuilder':
        """
        添加一个团队

        Args:
            name: 团队名称
            system_prompt: 团队主管的系统提示词
            workers: Worker 配置列表，每个 Worker 需包含 name, role, system_prompt
            agent_id: Team Supervisor 的 agent_id
            user_message: 预定义的用户消息
            model: 团队使用的模型（可选）
            prevent_duplicate: 是否防止重复调用
            share_context: 是否接收其他团队的上下文
            temperature: Team Supervisor LLM 温度参数
            max_tokens: Team Supervisor LLM 最大 token 数
            model_id: Team Supervisor LLM 模型 ID

        Returns:
            self（支持链式调用）
        """
        # 创建 Worker 配置列表
        worker_configs = []
        for w in workers:
            worker_agent_id = w.get('agent_id', '')
            # 优先使用 agent_id，没有则生成确定性 ID
            worker_id = worker_agent_id or generate_deterministic_id('worker', name, w['name'])
            worker_configs.append(WorkerConfig(
                name=w['name'],
                role=w['role'],
                system_prompt=w['system_prompt'],
                id=worker_id,
                agent_id=worker_agent_id,
                user_message=w.get('user_message'),
                tools=w.get('tools', []),
                model=w.get('model'),
                temperature=w.get('temperature', 0.7),
                max_tokens=w.get('max_tokens', 2048),
                model_id=w.get('model_id')
            ))

        # 团队 ID：优先使用 agent_id，没有则生成确定性 ID
        team_id = agent_id or generate_deterministic_id('team', name)

        # 创建团队配置
        team_config = TeamConfig(
            name=name,
            system_prompt=system_prompt,
            workers=worker_configs,
            id=team_id,
            agent_id=agent_id,
            user_message=user_message,
            model=model,
            prevent_duplicate=prevent_duplicate,
            share_context=share_context,
            temperature=temperature,
            max_tokens=max_tokens,
            model_id=model_id
        )

        self.teams.append(team_config)
        return self
    
    def build(self) -> tuple[Agent, Optional[CallTracker], List[str]]:
        """
        构建并返回 Global Supervisor、Tracker 和团队名称列表

        完成配置后调用此方法创建实际的 Agent 实例。

        Returns:
            (Global Supervisor Agent, CallTracker 或 None, 团队名称列表)
        """
        # Global ID：优先使用 agent_id，没有则生成确定性 ID
        global_id = self.global_agent_id or generate_deterministic_id('global_supervisor')

        # 创建全局配置
        config = GlobalConfig(
            system_prompt=self.global_system_prompt,
            teams=self.teams,
            id=global_id,
            agent_id=self.global_agent_id,
            user_message=self.global_user_message,
            model=self.global_model,
            enable_tracking=self.enable_tracking,
            enable_context_sharing=self.enable_context_sharing,
            parallel_execution=self.parallel_execution,
            temperature=self.global_temperature,
            max_tokens=self.global_max_tokens,
            model_id=self.global_model_id
        )

        # 设置执行追踪器
        if self.tracker:
            WorkerAgentFactory.set_execution_tracker(self.tracker.execution_tracker)

        # 创建 Global Supervisor
        agent, team_names = GlobalSupervisorFactory.create_global_supervisor(config, self.tracker)
        return agent, self.tracker, team_names


# ============================================================================
# 便捷函数
# ============================================================================

def create_hierarchy_from_config(config: dict, enable_tracking: bool = True) -> tuple[Agent, Optional[CallTracker], List[str]]:
    """
    从新格式的配置创建层级团队

    Args:
        config: 配置字典（新格式，包含 global_supervisor_agent 和 teams）
        enable_tracking: 是否启用调用追踪

    Returns:
        (Global Supervisor Agent, CallTracker 或 None, 团队名称列表)
    """
    # 提取配置
    execution_mode = config.get('execution_mode', 'sequential')
    enable_context_sharing = config.get('enable_context_sharing', False)
    global_agent = config.get('global_supervisor_agent', {})
    teams = config.get('teams', [])

    builder = HierarchyBuilder(
        enable_tracking=enable_tracking,
        enable_context_sharing=enable_context_sharing,
        parallel_execution=(execution_mode == 'parallel')
    )

    # 设置 Global Supervisor
    builder.set_global_system_prompt(global_agent.get('system_prompt', ''))
    if global_agent.get('agent_id'):
        builder.set_global_agent_id(global_agent['agent_id'])
    if global_agent.get('user_message'):
        builder.set_global_user_message(global_agent['user_message'])

    # 添加团队
    for team in teams:
        team_agent = team.get('team_supervisor_agent', {})
        builder.add_team(
            name=team['name'],
            system_prompt=team_agent.get('system_prompt', ''),
            workers=team.get('workers', []),
            agent_id=team_agent.get('agent_id', ''),
            user_message=team_agent.get('user_message'),
            model=team.get('model'),
            prevent_duplicate=team.get('prevent_duplicate', True),
            share_context=team.get('share_context', False)
        )

    return builder.build()


# ============================================================================
# 注意：演示代码已移至 test/test_quantum_research_full.py
# ============================================================================
