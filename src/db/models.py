"""
Database Models - SQLAlchemy 数据库模型定义
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Column, String, Float, Integer, BigInteger, Boolean, DateTime,
    Text, JSON, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


def generate_uuid() -> str:
    """生成 UUID 字符串"""
    return str(uuid.uuid4())


class RunStatus(str, Enum):
    """运行状态枚举"""
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class AIModel(Base):
    """AI 模型配置"""
    __tablename__ = 'ai_model'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False, unique=True, comment='模型名称')
    model_id = Column(String(200), nullable=False, comment='AWS Bedrock 模型 ID')
    region = Column(String(50), default='us-east-1', comment='AWS 区域')
    temperature = Column(Float, default=0.7, comment='温度参数')
    max_tokens = Column(Integer, default=2048, comment='最大 Token 数')
    top_p = Column(Float, default=0.9, comment='Top-P 参数')
    description = Column(Text, nullable=True, comment='模型描述')
    is_active = Column(Boolean, default=True, comment='是否激活')

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'model_id': self.model_id,
            'region': self.region,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'top_p': self.top_p,
            'description': self.description,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class HierarchyTeam(Base):
    """层级团队配置 - 使用 JSON 存储整个层级结构"""
    __tablename__ = 'hierarchy_team'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False, unique=True, comment='层级团队名称')
    description = Column(Text, nullable=True, comment='描述')

    # 整个层级配置存储为 JSON
    config = Column(JSON, nullable=False, comment='层级配置 JSON')

    # 元数据
    is_active = Column(Boolean, default=True)
    version = Column(Integer, default=1)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'config': self.config,
            'is_active': self.is_active,
            'version': self.version,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_execution_config(self) -> dict:
        """转换为执行配置格式"""
        return self.config


class ExecutionRun(Base):
    """执行运行记录"""
    __tablename__ = 'execution_run'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    hierarchy_id = Column(String(36), nullable=False, comment='关联的层级团队 ID')

    # 任务信息
    task = Column(Text, nullable=False, comment='任务描述')
    status = Column(String(20), default=RunStatus.PENDING.value, comment='运行状态')

    # 执行结果
    result = Column(Text, nullable=True, comment='执行结果')
    error = Column(Text, nullable=True, comment='错误信息')
    statistics = Column(JSON, nullable=True, comment='执行统计')

    # 拓扑信息快照
    topology_snapshot = Column(JSON, nullable=True, comment='拓扑快照')

    # 时间戳
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'hierarchy_id': self.hierarchy_id,
            'task': self.task,
            'status': self.status,
            'result': self.result,
            'error': self.error,
            'statistics': self.statistics,
            'topology_snapshot': self.topology_snapshot,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# NOTE: ExecutionEvent 表已删除，事件改用 Redis Stream 存储
# See src/streaming/event_store.py for the new event storage implementation.
