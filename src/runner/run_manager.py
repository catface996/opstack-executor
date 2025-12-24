"""
Run Manager - 运行管理器

管理任务执行生命周期，支持流式输出和取消
"""

import threading
import traceback
from datetime import datetime
from typing import Dict, Optional, Callable
from concurrent.futures import ThreadPoolExecutor

from ..db.models import ExecutionRun, RunStatus
from ..db.database import get_db_session
from ..db.repositories import RunRepository, HierarchyRepository
from ..streaming.sse_manager import SSERegistry, SSEManager
from ..streaming.output_interceptor import intercept_output, EventEmitter
from ..streaming.llm_callback import set_global_event_callback

# 延迟导入 - 避免在模块加载时触发 strands 依赖
# from ..core.hierarchy_executor import execute_hierarchy


def _get_execute_hierarchy():
    """延迟获取 execute_hierarchy 函数"""
    from ..core.hierarchy_executor import execute_hierarchy
    return execute_hierarchy


class RunManager:
    """
    运行管理器 - 管理任务执行生命周期
    """

    _instance: Optional['RunManager'] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.sse_registry = SSERegistry.get_instance()
        self.executor = ThreadPoolExecutor(max_workers=10)

        # 活跃运行追踪
        self._active_runs: Dict[str, dict] = {}
        self._cancellation_flags: Dict[str, threading.Event] = {}
        self._run_lock = threading.Lock()
        self._initialized = True

    @classmethod
    def get_instance(cls) -> 'RunManager':
        """获取单例实例"""
        return cls()

    def start_run(self, hierarchy_id: str, task: str) -> ExecutionRun:
        """
        启动新运行

        Args:
            hierarchy_id: 层级团队 ID
            task: 任务描述

        Returns:
            ExecutionRun 记录
        """
        session = get_db_session()
        run_repo = RunRepository(session)
        hierarchy_repo = HierarchyRepository(session)

        # 检查层级团队是否存在
        hierarchy = hierarchy_repo.get_by_id(hierarchy_id)
        if not hierarchy:
            raise ValueError(f"层级团队不存在: {hierarchy_id}")

        # 创建运行记录
        run = run_repo.create({
            'hierarchy_id': hierarchy_id,
            'task': task,
            'status': RunStatus.PENDING.value,
        })

        # 创建取消标志
        cancel_flag = threading.Event()
        with self._run_lock:
            self._cancellation_flags[run.id] = cancel_flag
            self._active_runs[run.id] = {
                'status': 'pending',
                'started_at': None,
                'hierarchy_id': hierarchy_id
            }

        # 注册 SSE 管理器
        sse_manager = self.sse_registry.register(run.id)

        # 获取执行配置
        config_dict = hierarchy.to_execution_config()
        config_dict['task'] = task

        # 提交到线程池执行
        self.executor.submit(
            self._execute_run,
            run.id,
            config_dict,
            task,
            sse_manager,
            cancel_flag
        )

        return run

    def cancel_run(self, run_id: str) -> bool:
        """
        取消运行

        Args:
            run_id: 运行 ID

        Returns:
            是否成功取消
        """
        with self._run_lock:
            if run_id in self._cancellation_flags:
                self._cancellation_flags[run_id].set()

                # 更新状态
                session = get_db_session()
                run_repo = RunRepository(session)
                run_repo.update_status(run_id, RunStatus.CANCELLED.value)

                return True
        return False

    def is_running(self, run_id: str) -> bool:
        """检查运行是否进行中"""
        with self._run_lock:
            if run_id in self._active_runs:
                return self._active_runs[run_id]['status'] == 'running'
        return False

    def get_active_runs(self) -> list:
        """获取所有活跃运行"""
        with self._run_lock:
            return [
                {'run_id': k, **v}
                for k, v in self._active_runs.items()
            ]

    def _execute_run(
        self,
        run_id: str,
        config_dict: dict,
        task: str,
        sse_manager: SSEManager,
        cancel_flag: threading.Event
    ):
        """
        执行运行（在后台线程中）
        """
        session = get_db_session()
        run_repo = RunRepository(session)

        try:
            # 更新状态为 running
            run_repo.update_status(run_id, RunStatus.RUNNING.value)
            with self._run_lock:
                self._active_runs[run_id]['status'] = 'running'
                self._active_runs[run_id]['started_at'] = datetime.utcnow()

            # 发送开始事件
            sse_manager.emit('execution_started', {'task': task})

            # 定义事件回调
            def event_callback(event_type: str, data: dict):
                # 检查取消标志
                if cancel_flag.is_set():
                    raise InterruptedError("Run was cancelled")

                # 提取来源标签信息（以 _ 开头的内部字段）
                is_global_supervisor = data.pop('_is_global_supervisor', False)
                team_name = data.pop('_team_name', None)
                is_team_supervisor = data.pop('_is_team_supervisor', False)
                worker_name = data.pop('_worker_name', None) or data.get('name')

                # 发送 SSE 事件
                sse_manager.emit(event_type, data)

                # 保存事件到数据库
                run_repo.add_event(
                    run_id,
                    event_type,
                    data,
                    is_global_supervisor=is_global_supervisor,
                    team_name=team_name,
                    is_team_supervisor=is_team_supervisor,
                    worker_name=worker_name
                )

            # 设置全局事件回调（供 LLM callback handler 使用）
            set_global_event_callback(event_callback)

            try:
                # 使用输出拦截器执行
                with intercept_output(event_callback) as interceptor:
                    # 执行层级系统（延迟导入以避免 strands 依赖检查）
                    execute_hierarchy = _get_execute_hierarchy()
                    response = execute_hierarchy(config_dict)
            finally:
                # 清除全局事件回调
                set_global_event_callback(None)

            # 更新结果
            if response.success:
                run_repo.update_result(
                    run_id,
                    RunStatus.COMPLETED.value,
                    result=response.result,
                    statistics=response.statistics
                )
                sse_manager.emit('execution_completed', {
                    'result': response.result[:1000] if response.result else None,
                    'statistics': response.statistics
                })
            else:
                run_repo.update_result(
                    run_id,
                    RunStatus.FAILED.value,
                    error=response.error
                )
                sse_manager.emit('execution_failed', {'error': response.error})

        except InterruptedError:
            # 运行被取消
            run_repo.update_status(run_id, RunStatus.CANCELLED.value)
            sse_manager.emit('execution_cancelled', {})

        except Exception as e:
            # 运行失败
            error_msg = str(e)
            error_details = traceback.format_exc()

            run_repo.update_result(
                run_id,
                RunStatus.FAILED.value,
                error=f"{error_msg}\n{error_details}"
            )
            sse_manager.emit('execution_failed', {
                'error': error_msg,
                'details': error_details
            })

        finally:
            # 清理
            sse_manager.close()
            with self._run_lock:
                self._active_runs.pop(run_id, None)
                self._cancellation_flags.pop(run_id, None)
            self.sse_registry.remove(run_id)

    def shutdown(self):
        """关闭运行管理器"""
        # 取消所有活跃运行
        with self._run_lock:
            for run_id in list(self._cancellation_flags.keys()):
                self._cancellation_flags[run_id].set()

        # 关闭线程池
        self.executor.shutdown(wait=True)
