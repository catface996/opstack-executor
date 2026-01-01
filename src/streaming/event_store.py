"""
Event Store - Redis Stream 事件存储

提供事件的写入、读取、订阅和管理功能。
使用 Redis Stream 作为底层存储，支持：
- 高性能事件写入 (XADD)
- 范围读取 (XRANGE)
- 断线重连恢复 (get_events_after)
- 自动过期 (EXPIRE)
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any

import redis

from .redis_client import get_redis_client


logger = logging.getLogger(__name__)


# Stream 配置
STREAM_MAXLEN = 10000  # 单个运行最多保留 10000 条事件
STREAM_TTL_SECONDS = 86400  # 24 小时后自动删除


@dataclass
class StreamEvent:
    """Redis Stream 事件"""
    id: str                          # Redis 消息 ID
    run_id: int                      # 运行 ID
    timestamp: str                   # ISO 8601 时间戳
    sequence: int                    # 序列号
    source: Optional[Dict[str, str]] # 来源信息
    event: Dict[str, str]           # 事件类型
    data: Dict[str, Any]            # 事件数据


class EventStore:
    """
    事件存储 - 基于 Redis Stream

    Stream Key 格式: run:{run_id}:events
    消息 ID 格式: <timestamp_ms>-<sequence> (Redis 自动生成)
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        初始化事件存储

        Args:
            redis_client: Redis 客户端实例，如果未提供则使用全局客户端
        """
        self._redis = redis_client

    @property
    def redis(self) -> redis.Redis:
        """延迟获取 Redis 客户端"""
        if self._redis is None:
            self._redis = get_redis_client()
        return self._redis

    def _stream_key(self, run_id: int) -> str:
        """生成 Stream Key"""
        return f"run:{run_id}:events"

    def add(
        self,
        run_id: int,
        event_category: str,
        event_action: str,
        data: dict = None,
        source: dict = None,
        timestamp: str = None,
        sequence: int = None
    ) -> Optional[str]:
        """
        添加事件到 Stream

        Args:
            run_id: 运行 ID
            event_category: 事件类别 (lifecycle, llm, dispatch, system)
            event_action: 事件动作 (started, completed, stream, etc.)
            data: 事件数据
            source: 事件来源 {agent_id, agent_type, agent_name, team_name}
            timestamp: ISO 8601 时间戳（可选，默认自动生成）
            sequence: 序列号（可选，默认自动生成）

        Returns:
            消息 ID 或 None（失败时）
        """
        try:
            # 生成时间戳（毫秒精度）
            if timestamp is None:
                now = datetime.utcnow()
                timestamp = now.strftime('%Y-%m-%dT%H:%M:%S.') + f'{now.microsecond // 1000:03d}Z'

            # 构建消息字段
            fields = {
                'timestamp': timestamp,
                'sequence': str(sequence) if sequence is not None else '0',
                'event_category': event_category,
                'event_action': event_action,
                'data': json.dumps(data or {}, ensure_ascii=False),
            }

            # 添加来源信息
            if source:
                fields['source_agent_id'] = source.get('agent_id') or ''
                fields['source_agent_type'] = source.get('agent_type') or ''
                fields['source_agent_name'] = source.get('agent_name') or ''
                fields['source_team_name'] = source.get('team_name') or ''
            else:
                fields['source_agent_id'] = ''
                fields['source_agent_type'] = ''
                fields['source_agent_name'] = ''
                fields['source_team_name'] = ''

            # 写入 Redis Stream
            stream_key = self._stream_key(run_id)
            message_id = self.redis.xadd(
                stream_key,
                fields,
                maxlen=STREAM_MAXLEN,
                approximate=True  # 近似修剪，性能更好
            )

            return message_id

        except redis.RedisError as e:
            # 不阻塞主流程，仅记录错误日志
            logger.error(f"Redis write failed for run {run_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error writing event for run {run_id}: {e}")
            return None

    def get_events(
        self,
        run_id: int,
        start_id: str = '-',
        end_id: str = '+',
        count: int = None
    ) -> List[StreamEvent]:
        """
        获取事件列表

        Args:
            run_id: 运行 ID
            start_id: 起始 ID（包含），'-' 表示最早
            end_id: 结束 ID（包含），'+' 表示最新
            count: 最大返回数量

        Returns:
            事件列表
        """
        try:
            stream_key = self._stream_key(run_id)
            messages = self.redis.xrange(stream_key, start_id, end_id, count=count)
            return [self._parse_message(run_id, msg_id, fields) for msg_id, fields in messages]
        except redis.RedisError as e:
            logger.error(f"Redis read failed for run {run_id}: {e}")
            return []

    def get_events_after(
        self,
        run_id: int,
        last_id: str,
        count: int = None
    ) -> List[StreamEvent]:
        """
        获取指定 ID 之后的事件（不包含 last_id）

        用于断线重连场景。

        Args:
            run_id: 运行 ID
            last_id: 上次收到的消息 ID
            count: 最大返回数量

        Returns:
            事件列表
        """
        try:
            stream_key = self._stream_key(run_id)
            # 使用 '(' 前缀表示排除起始 ID
            exclusive_start = f"({last_id}"
            messages = self.redis.xrange(stream_key, exclusive_start, '+', count=count)
            return [self._parse_message(run_id, msg_id, fields) for msg_id, fields in messages]
        except redis.RedisError as e:
            logger.error(f"Redis read failed for run {run_id}: {e}")
            return []

    def subscribe(
        self,
        run_id: int,
        last_id: str = '$',
        block_ms: int = 5000
    ) -> List[StreamEvent]:
        """
        订阅新事件（阻塞读取）

        Args:
            run_id: 运行 ID
            last_id: 从此 ID 之后开始读取，'$' 表示只读新消息
            block_ms: 阻塞等待时间（毫秒）

        Returns:
            新事件列表（可能为空，表示超时）
        """
        try:
            stream_key = self._stream_key(run_id)
            result = self.redis.xread({stream_key: last_id}, block=block_ms, count=100)

            if not result:
                return []

            events = []
            for stream_name, messages in result:
                for msg_id, fields in messages:
                    events.append(self._parse_message(run_id, msg_id, fields))

            return events

        except redis.RedisError as e:
            logger.error(f"Redis subscribe failed for run {run_id}: {e}")
            return []

    def set_expire(self, run_id: int, ttl_seconds: int = STREAM_TTL_SECONDS) -> bool:
        """
        设置 Stream 过期时间

        Args:
            run_id: 运行 ID
            ttl_seconds: 过期时间（秒），默认 24 小时

        Returns:
            是否设置成功
        """
        try:
            stream_key = self._stream_key(run_id)
            return self.redis.expire(stream_key, ttl_seconds)
        except redis.RedisError as e:
            logger.error(f"Redis expire failed for run {run_id}: {e}")
            return False

    def delete(self, run_id: int) -> bool:
        """
        删除 Stream

        Args:
            run_id: 运行 ID

        Returns:
            是否删除成功
        """
        try:
            stream_key = self._stream_key(run_id)
            return self.redis.delete(stream_key) > 0
        except redis.RedisError as e:
            logger.error(f"Redis delete failed for run {run_id}: {e}")
            return False

    def exists(self, run_id: int) -> bool:
        """
        检查 Stream 是否存在

        Args:
            run_id: 运行 ID

        Returns:
            是否存在
        """
        try:
            stream_key = self._stream_key(run_id)
            return self.redis.exists(stream_key) > 0
        except redis.RedisError as e:
            logger.error(f"Redis exists check failed for run {run_id}: {e}")
            return False

    def get_length(self, run_id: int) -> int:
        """
        获取 Stream 长度

        Args:
            run_id: 运行 ID

        Returns:
            事件数量
        """
        try:
            stream_key = self._stream_key(run_id)
            return self.redis.xlen(stream_key)
        except redis.RedisError as e:
            logger.error(f"Redis xlen failed for run {run_id}: {e}")
            return 0

    def _parse_message(self, run_id: int, msg_id: str, fields: dict) -> StreamEvent:
        """
        解析 Redis Stream 消息为 StreamEvent

        Args:
            run_id: 运行 ID
            msg_id: 消息 ID
            fields: 消息字段

        Returns:
            StreamEvent 实例
        """
        # 解析来源信息
        source = None
        if fields.get('source_agent_type'):
            source = {
                'agent_id': fields.get('source_agent_id') or None,
                'agent_type': fields.get('source_agent_type') or None,
                'agent_name': fields.get('source_agent_name') or None,
                'team_name': fields.get('source_team_name') or None,
            }

        # 解析事件数据
        try:
            data = json.loads(fields.get('data', '{}'))
        except json.JSONDecodeError:
            data = {}

        return StreamEvent(
            id=msg_id,
            run_id=run_id,
            timestamp=fields.get('timestamp', ''),
            sequence=int(fields.get('sequence', 0)),
            source=source,
            event={
                'category': fields.get('event_category', 'unknown'),
                'action': fields.get('event_action', 'unknown'),
            },
            data=data,
        )


# 全局 EventStore 实例
_event_store: Optional[EventStore] = None


def get_event_store() -> EventStore:
    """
    获取 EventStore 单例实例

    Returns:
        EventStore 实例
    """
    global _event_store
    if _event_store is None:
        _event_store = EventStore()
    return _event_store
