"""
Redis Client - Redis 连接管理

提供 Redis 连接池和自动重连机制。
"""

import os
import redis
from typing import Optional


# 全局 Redis 客户端实例
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """
    获取 Redis 客户端实例（单例模式）

    Returns:
        redis.Redis: Redis 客户端实例
    """
    global _redis_client

    if _redis_client is None:
        _redis_client = _create_redis_client()

    return _redis_client


def _create_redis_client() -> redis.Redis:
    """
    创建 Redis 客户端

    支持通过 REDIS_URL 环境变量配置，或使用默认本地连接。
    """
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

    return redis.from_url(
        redis_url,
        decode_responses=True,  # 自动将 bytes 解码为 str
        socket_connect_timeout=5,
        socket_keepalive=True,
        retry_on_timeout=True,
        health_check_interval=30,
    )


def reset_redis_client():
    """
    重置 Redis 客户端（用于测试或重新连接）
    """
    global _redis_client
    if _redis_client is not None:
        try:
            _redis_client.close()
        except Exception:
            pass
        _redis_client = None


def check_redis_connection() -> bool:
    """
    检查 Redis 连接是否可用

    Returns:
        bool: 连接是否可用
    """
    try:
        client = get_redis_client()
        return client.ping()
    except redis.RedisError:
        return False
