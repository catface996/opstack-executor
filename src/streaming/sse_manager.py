"""
SSE Manager - Server-Sent Events 管理器

支持双写策略：同时写入内存队列（低延迟 SSE）和 Redis Stream（持久化+断线恢复）。
"""

import json
import threading
from queue import Queue, Empty
from datetime import datetime
from typing import Generator, Optional, Dict, List

from flask import Response

from .event_store import EventStore, StreamEvent, get_event_store


class SSEManager:
    """
    SSE 管理器 - 管理服务器发送事件

    事件格式:
    {
        "id": "1704067200000-0",  # Redis Stream 消息 ID
        "run_id": "...",
        "timestamp": "...",
        "sequence": 123,
        "source": { agent_id, agent_type, agent_name, team_name },
        "event": { category, action },
        "data": { ... }
    }
    """

    def __init__(self, run_id: int, event_store: Optional[EventStore] = None):
        """
        初始化 SSE 管理器

        Args:
            run_id: 运行 ID
            event_store: EventStore 实例，如果未提供则使用全局实例
        """
        self.run_id = run_id
        self.event_queue: Queue = Queue()
        self.is_active = True
        self._lock = threading.Lock()
        self._sequence = 0
        self._event_store = event_store
        self._last_event_id: Optional[str] = None  # 最后一个事件的 Redis 消息 ID

    @property
    def event_store(self) -> EventStore:
        """延迟获取 EventStore"""
        if self._event_store is None:
            self._event_store = get_event_store()
        return self._event_store

    def emit(self, event_data: Dict) -> Optional[str]:
        """
        发射事件（双写：内存队列 + Redis Stream）

        Args:
            event_data: 事件数据，包含 source, event, data

        Returns:
            Redis 消息 ID 或 None
        """
        if not self.is_active:
            return None

        # 生成毫秒精度的 ISO 8601 时间戳
        now = datetime.utcnow()
        timestamp = now.strftime('%Y-%m-%dT%H:%M:%S.') + f'{now.microsecond // 1000:03d}Z'

        # 自增序列号
        with self._lock:
            self._sequence += 1
            sequence = self._sequence

        source = event_data.get('source')
        event = event_data.get('event', {})
        data = event_data.get('data', {})

        # 写入 Redis Stream
        message_id = self.event_store.add(
            run_id=self.run_id,
            event_category=event.get('category', 'unknown'),
            event_action=event.get('action', 'unknown'),
            data=data,
            source=source,
            timestamp=timestamp,
            sequence=sequence
        )

        # 构建完整事件
        full_event = {
            'id': message_id,  # Redis 消息 ID，用于客户端断线重连
            'run_id': self.run_id,
            'timestamp': timestamp,
            'sequence': sequence,
            'source': source,
            'event': event,
            'data': data
        }

        # 写入内存队列（低延迟 SSE）
        self.event_queue.put(full_event)

        # 更新最后事件 ID
        if message_id:
            self._last_event_id = message_id

        return message_id

    def close(self):
        """关闭 SSE 连接"""
        with self._lock:
            self.is_active = False
            # 发送结束事件
            self.event_queue.put({
                'event': {'category': 'system', 'action': 'close'},
                'data': {'message': 'Stream closed'}
            })

    def generate_events(
        self,
        timeout: float = 30.0,
        initial_events: Optional[List[StreamEvent]] = None
    ) -> Generator[str, None, None]:
        """
        生成 SSE 事件流

        Args:
            timeout: 队列等待超时时间
            initial_events: 初始事件列表（用于断线重连时先发送历史事件）

        Yields:
            格式化的 SSE 事件字符串
        """
        # 先发送初始事件（断线重连恢复的历史事件）
        if initial_events:
            for event in initial_events:
                yield from self._format_stream_event(event)

        heartbeat_interval = 15  # 心跳间隔秒数
        last_heartbeat = datetime.utcnow()

        while self.is_active or not self.event_queue.empty():
            try:
                event = self.event_queue.get(timeout=1.0)

                # 检查是否是关闭事件
                event_meta = event.get('event', {})
                if event_meta.get('category') == 'system' and event_meta.get('action') == 'close':
                    yield f"event: close\ndata: {json.dumps({'message': 'Stream closed'}, ensure_ascii=False)}\n\n"
                    break

                # 格式化 SSE 事件
                yield from self._format_dict_event(event)

            except Empty:
                # 发送心跳保持连接
                now = datetime.utcnow()
                if (now - last_heartbeat).seconds >= heartbeat_interval:
                    yield f": heartbeat {now.isoformat()}Z\n\n"
                    last_heartbeat = now

    def _format_dict_event(self, event: Dict) -> Generator[str, None, None]:
        """格式化字典类型的事件为 SSE 字符串"""
        event_meta = event.get('event', {})
        category = event_meta.get('category', 'unknown')
        action = event_meta.get('action', 'unknown')
        event_type = f"{category}.{action}"

        # 输出 id 字段（用于客户端 Last-Event-ID）
        event_id = event.get('id')
        if event_id:
            yield f"id: {event_id}\n"

        yield f"event: {event_type}\n"
        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    def _format_stream_event(self, event: StreamEvent) -> Generator[str, None, None]:
        """格式化 StreamEvent 为 SSE 字符串"""
        event_type = f"{event.event.get('category', 'unknown')}.{event.event.get('action', 'unknown')}"

        # 构建完整事件数据
        event_data = {
            'id': event.id,
            'run_id': event.run_id,
            'timestamp': event.timestamp,
            'sequence': event.sequence,
            'source': event.source,
            'event': event.event,
            'data': event.data
        }

        yield f"id: {event.id}\n"
        yield f"event: {event_type}\n"
        yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"

    def create_response(
        self,
        initial_events: Optional[List[StreamEvent]] = None
    ) -> Response:
        """
        创建 Flask SSE 响应

        Args:
            initial_events: 初始事件列表（断线重连恢复用）
        """
        return Response(
            self.generate_events(initial_events=initial_events),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no',  # 禁用 nginx 缓冲
                'Access-Control-Allow-Origin': '*',
            }
        )


class SSERegistry:
    """SSE 管理器注册表 - 单例模式"""

    _instance: Optional['SSERegistry'] = None
    _managers: Dict[int, SSEManager] = {}
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._managers = {}
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'SSERegistry':
        """获取单例实例"""
        return cls()

    def register(self, run_id: int, event_store: Optional[EventStore] = None) -> SSEManager:
        """
        注册新的 SSE 管理器

        Args:
            run_id: 运行 ID
            event_store: EventStore 实例（可选）
        """
        with self._lock:
            if run_id in self._managers:
                self._managers[run_id].close()

            manager = SSEManager(run_id, event_store=event_store)
            self._managers[run_id] = manager
            return manager

    def get(self, run_id: int) -> Optional[SSEManager]:
        """获取 SSE 管理器"""
        return self._managers.get(run_id)

    def remove(self, run_id: int):
        """移除 SSE 管理器"""
        with self._lock:
            if run_id in self._managers:
                self._managers[run_id].close()
                del self._managers[run_id]

    def get_all_run_ids(self) -> list:
        """获取所有活跃的运行 ID"""
        return list(self._managers.keys())
