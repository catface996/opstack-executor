"""
Output Interceptor - 输出拦截器

拦截 stdout 并转换为结构化事件
"""

import sys
import re
import threading
from typing import Callable, Optional, Dict, Any
from contextlib import contextmanager
from io import StringIO

from ..core.api_models import AgentType, EventCategory, EventAction


class OutputInterceptor:
    """输出拦截器 - 拦截 stdout 并转换为结构化事件"""

    # 输出模式匹配（基于 output_formatter.py 的格式）
    PATTERNS = {
        # Global Supervisor 模式
        'global_start': re.compile(r'\*{50,}.*?首席科学家.*?开始', re.DOTALL),
        'global_dispatch': re.compile(r'\[Global Supervisor\].*?📤\s*DISPATCH.*?调度\s*\[([^\]]+)\]'),
        'global_complete': re.compile(r'✅.*?首席科学家.*?完成'),

        # Team Supervisor 模式
        'team_start': re.compile(r'#{50,}.*?(\S+?)主管.*?开始协调', re.DOTALL),
        'team_thinking': re.compile(r'主管的协调过程'),
        'team_complete': re.compile(r'✅.*?(\S+?)主管.*?完成'),
        'team_duplicate': re.compile(r'⚠️.*?已在之前执行过'),
        'team_dispatch': re.compile(r'\[Team:.*?Supervisor\].*?📤\s*DISPATCH.*?调度\s*\[([^\]]+)\]'),

        # Worker 模式
        'worker_start': re.compile(r'={50,}.*?(\S+?).*?开始工作', re.DOTALL),
        'worker_thinking': re.compile(r'思考过程|分析中'),
        'worker_complete': re.compile(r'✅.*?(\S+?).*?完成'),

        # 通用模式
        'error': re.compile(r'❌|错误|Error|Exception', re.IGNORECASE),
        'warning': re.compile(r'⚠️|警告|Warning', re.IGNORECASE),
    }

    # 模式到事件的映射
    PATTERN_TO_EVENT = {
        'global_start': (EventCategory.LIFECYCLE, EventAction.STARTED),
        'global_dispatch': (EventCategory.DISPATCH, EventAction.TEAM),
        'global_complete': (EventCategory.LIFECYCLE, EventAction.COMPLETED),
        'team_start': (EventCategory.LIFECYCLE, EventAction.STARTED),
        'team_thinking': (EventCategory.LLM, EventAction.REASONING),
        'team_complete': (EventCategory.LIFECYCLE, EventAction.COMPLETED),
        'team_duplicate': (EventCategory.SYSTEM, EventAction.WARNING),
        'team_dispatch': (EventCategory.DISPATCH, EventAction.WORKER),
        'worker_start': (EventCategory.LIFECYCLE, EventAction.STARTED),
        'worker_thinking': (EventCategory.LLM, EventAction.REASONING),
        'worker_complete': (EventCategory.LIFECYCLE, EventAction.COMPLETED),
        'error': (EventCategory.SYSTEM, EventAction.ERROR),
        'warning': (EventCategory.SYSTEM, EventAction.WARNING),
    }

    # 标签解析模式
    GLOBAL_SUPERVISOR_PATTERN = re.compile(r'\[Global Supervisor\]')
    TEAM_SUPERVISOR_PATTERN = re.compile(r'\[Team:\s*([^|\]]+?)\s*\|\s*Supervisor\s*\]')
    WORKER_PATTERN = re.compile(r'\[Team:\s*([^|\]]+?)\s*\|\s*Worker:\s*([^\]]+?)\s*\]')

    def __init__(self, event_callback: Callable[[Dict[str, Any]], None]):
        """
        Args:
            event_callback: 事件回调函数 (event_dict) -> None
        """
        self.event_callback = event_callback
        self.original_stdout = None
        self.buffer = StringIO()
        self._lock = threading.Lock()

    def start_interception(self):
        """开始拦截 stdout"""
        with self._lock:
            if self.original_stdout is None:
                self.original_stdout = sys.stdout
                sys.stdout = self

    def stop_interception(self):
        """停止拦截，恢复 stdout"""
        with self._lock:
            if self.original_stdout is not None:
                sys.stdout = self.original_stdout
                self.original_stdout = None

    def write(self, text: str):
        """拦截 write 调用"""
        # 同时写入原始 stdout（用于调试和日志）
        if self.original_stdout:
            self.original_stdout.write(text)

        # 解析文本并发射事件
        self._parse_and_emit(text)

    def flush(self):
        """实现 flush 方法"""
        if self.original_stdout:
            self.original_stdout.flush()

    def _extract_source_info(self, text: str) -> Dict[str, Any]:
        """
        从输出文本中提取来源信息

        返回格式:
        {
            'agent_type': AgentType,
            'agent_name': str,
            'team_name': str or None
        }
        """
        # 1. 检查是否是 Global Supervisor
        if self.GLOBAL_SUPERVISOR_PATTERN.search(text):
            return {
                'agent_type': AgentType.GLOBAL_SUPERVISOR,
                'agent_name': 'Global Supervisor',
                'team_name': None
            }

        # 2. 检查是否是 Team Supervisor
        match = self.TEAM_SUPERVISOR_PATTERN.search(text)
        if match:
            team_name = match.group(1).strip()
            return {
                'agent_type': AgentType.TEAM_SUPERVISOR,
                'agent_name': f'{team_name}主管',
                'team_name': team_name
            }

        # 3. 检查是否是 Worker
        match = self.WORKER_PATTERN.search(text)
        if match:
            team_name = match.group(1).strip()
            worker_name = match.group(2).strip()
            return {
                'agent_type': AgentType.WORKER,
                'agent_name': worker_name,
                'team_name': team_name
            }

        return None

    def _is_separator_line(self, text: str) -> bool:
        """检查是否为纯分隔线（无意义的装饰性输出）"""
        if not text:
            return True
        separator_chars = set('-=#*─━')
        return all(c in separator_chars for c in text)

    def _parse_and_emit(self, text: str):
        """解析文本并发射结构化事件"""
        if not text or not text.strip():
            return

        text_stripped = text.strip()

        # 过滤纯分隔线
        if self._is_separator_line(text_stripped):
            return

        # 提取来源信息
        source_info = self._extract_source_info(text_stripped)

        # 按优先级匹配模式
        for pattern_name, pattern in self.PATTERNS.items():
            match = pattern.search(text_stripped)
            if match:
                # 获取事件类别和动作
                category, action = self.PATTERN_TO_EVENT.get(
                    pattern_name,
                    (EventCategory.SYSTEM, EventAction.WARNING)
                )

                # 构建 data
                data = {
                    'raw_text': text_stripped[:500],
                }

                # 提取匹配的名称
                if match.groups():
                    data['name'] = match.group(1)

                # 根据模式推断来源
                if source_info is None:
                    # 从模式名推断来源
                    if pattern_name.startswith('global_'):
                        source_info = {
                            'agent_type': AgentType.GLOBAL_SUPERVISOR,
                            'agent_name': 'Global Supervisor',
                            'team_name': None
                        }
                    elif pattern_name.startswith('team_'):
                        source_info = {
                            'agent_type': AgentType.TEAM_SUPERVISOR,
                            'agent_name': data.get('name', 'Team Supervisor'),
                            'team_name': data.get('name')
                        }
                    elif pattern_name.startswith('worker_'):
                        source_info = {
                            'agent_type': AgentType.WORKER,
                            'agent_name': data.get('name', 'Worker'),
                            'team_name': None
                        }

                # 发射事件
                self._emit_event(category, action, data, source_info)
                return

        # 非模式匹配的内容作为 LLM stream 事件
        if source_info and len(text_stripped) > 10:
            self._emit_event(
                EventCategory.LLM,
                EventAction.STREAM,
                {'content': text_stripped[:1000]},
                source_info
            )

    def _emit_event(
        self,
        category: EventCategory,
        action: EventAction,
        data: Dict[str, Any],
        source_info: Optional[Dict[str, Any]] = None
    ):
        """
        发射结构化事件

        事件结构:
        {
            "source": { agent_id, agent_type, agent_name, team_name },
            "event": { category, action },
            "data": { ... }
        }
        """
        # 构建 source（如果没有来源信息，使用默认值）
        if source_info:
            source = {
                'agent_id': None,  # output interceptor 没有 agent_id
                'agent_type': source_info['agent_type'].value if isinstance(source_info['agent_type'], AgentType) else source_info['agent_type'],
                'agent_name': source_info['agent_name'],
                'team_name': source_info['team_name']
            }
        else:
            source = None

        event_data = {
            'source': source,
            'event': {
                'category': category.value,
                'action': action.value
            },
            'data': data
        }
        self.event_callback(event_data)


@contextmanager
def intercept_output(event_callback: Callable[[Dict[str, Any]], None]):
    """
    上下文管理器 - 拦截输出

    Usage:
        def my_callback(event_dict):
            print(f"Event: {event_dict}")

        with intercept_output(my_callback):
            # 执行任务，所有 print 输出会被拦截
            execute_hierarchy(config)
    """
    interceptor = OutputInterceptor(event_callback)
    interceptor.start_interception()
    try:
        yield interceptor
    finally:
        interceptor.stop_interception()


class EventEmitter:
    """事件发射器 - 直接发射结构化事件（不依赖 stdout 拦截）"""

    def __init__(self, callback: Callable[[Dict[str, Any]], None]):
        self.callback = callback

    def emit(
        self,
        category: EventCategory,
        action: EventAction,
        data: Dict[str, Any],
        source: Optional[Dict[str, Any]] = None
    ):
        """发射结构化事件"""
        event_data = {
            'source': source,
            'event': {
                'category': category.value if isinstance(category, EventCategory) else category,
                'action': action.value if isinstance(action, EventAction) else action
            },
            'data': data
        }
        self.callback(event_data)

    def execution_started(self, task: str):
        """执行开始"""
        self.emit(EventCategory.LIFECYCLE, EventAction.STARTED, {'task': task})

    def execution_completed(self, result: str, statistics: dict = None):
        """执行完成"""
        self.emit(EventCategory.LIFECYCLE, EventAction.COMPLETED, {
            'result': result,
            'statistics': statistics
        })

    def execution_failed(self, error: str):
        """执行失败"""
        self.emit(EventCategory.LIFECYCLE, EventAction.FAILED, {'error': error})

    def execution_cancelled(self):
        """执行取消"""
        self.emit(EventCategory.LIFECYCLE, EventAction.CANCELLED, {})

    def topology_created(self, topology: dict):
        """拓扑创建"""
        self.emit(EventCategory.SYSTEM, EventAction.TOPOLOGY, {'topology': topology})
