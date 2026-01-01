"""
Run Repository - 运行记录数据访问层
"""

import time
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import ExecutionRun, ExecutionEvent, RunStatus


class RunRepository:
    """运行记录仓库"""

    def __init__(self, session: Session):
        self.session = session

    def create(self, data: dict) -> ExecutionRun:
        """创建运行记录"""
        run = ExecutionRun(**data)
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def get_by_id(self, run_id: int) -> Optional[ExecutionRun]:
        """根据 ID 获取运行记录"""
        return self.session.query(ExecutionRun).filter(ExecutionRun.id == run_id).first()

    def list(
        self,
        page: int = 1,
        size: int = 20,
        hierarchy_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> tuple[List[ExecutionRun], int]:
        """
        获取运行记录列表

        Returns:
            (运行列表, 总数)
        """
        query = self.session.query(ExecutionRun)

        if hierarchy_id:
            query = query.filter(ExecutionRun.hierarchy_id == hierarchy_id)
        if status:
            query = query.filter(ExecutionRun.status == status)

        total = query.count()
        runs = query.order_by(ExecutionRun.created_at.desc()) \
                   .offset((page - 1) * size) \
                   .limit(size) \
                   .all()

        return runs, total

    def update_status(self, run_id: int, status: str) -> bool:
        """更新运行状态"""
        run = self.get_by_id(run_id)
        if not run:
            return False

        run.status = status

        if status == RunStatus.RUNNING.value:
            run.started_at = datetime.utcnow()
        elif status in (RunStatus.COMPLETED.value, RunStatus.FAILED.value, RunStatus.CANCELLED.value):
            run.completed_at = datetime.utcnow()

        self.session.commit()
        return True

    def update_result(
        self,
        run_id: int,
        status: str,
        result: str = None,
        error: str = None,
        statistics: dict = None
    ) -> bool:
        """更新运行结果"""
        run = self.get_by_id(run_id)
        if not run:
            return False

        run.status = status
        run.completed_at = datetime.utcnow()

        if result is not None:
            run.result = result
        if error is not None:
            run.error = error
        if statistics is not None:
            run.statistics = statistics

        self.session.commit()
        return True

    # NOTE: add_event() and get_events() methods removed in favor of Redis Stream (EventStore)
    # See src/streaming/event_store.py for the new event storage implementation.
    # The ExecutionEvent MySQL model is kept for backward compatibility but no longer used.

    def set_topology_snapshot(self, run_id: int, topology: dict) -> bool:
        """设置拓扑快照"""
        run = self.get_by_id(run_id)
        if not run:
            return False

        run.topology_snapshot = topology
        self.session.commit()
        return True

    def delete(self, run_id: int) -> bool:
        """删除运行记录"""
        run = self.get_by_id(run_id)
        if not run:
            return False

        # NOTE: Events are now stored in Redis Stream, not MySQL.
        # Redis Stream events will auto-expire after 24 hours (TTL set on run completion).
        # For immediate cleanup, use EventStore.delete(run_id)

        # 删除运行记录
        self.session.delete(run)
        self.session.commit()
        return True
