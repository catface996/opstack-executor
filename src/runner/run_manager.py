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
from ..db.database import get_db_session, create_new_session
from ..db.repositories import RunRepository, HierarchyRepository
from ..streaming.sse_manager import SSERegistry, SSEManager
from ..streaming.output_interceptor import intercept_output
from ..streaming.llm_callback import (
    register_event_callback,
    register_cancellation_checker,
    set_current_run_id,
    clear_current_run_id
)
from ..streaming.event_store import get_event_store
from ..core.api_models import EventCategory, EventAction

# 延迟导入 - 避免在模块加载时触发 strands 依赖
# from ..core.hierarchy_executor import execute_hierarchy


def _get_execute_hierarchy():
    """延迟获取 execute_hierarchy 函数"""
    from ..core.hierarchy_executor import execute_hierarchy
    return execute_hierarchy


class RunManager:
    """运行管理器 - 管理任务执行生命周期"""

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
        self._active_runs: Dict[int, dict] = {}
        self._cancellation_flags: Dict[int, threading.Event] = {}
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

        # 调试日志
        print(f"[start] 创建 run_id: {run.id}", flush=True)
        print(f"[start] SSE Registry ID: {id(self.sse_registry)}", flush=True)
        print(f"[start] 已注册的 run_ids: {self.sse_registry.get_all_run_ids()}", flush=True)

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

    def cancel_run(self, run_id: int) -> bool:
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

    def is_running(self, run_id: int) -> bool:
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
        run_id: int,
        config_dict: dict,
        task: str,
        sse_manager: SSEManager,
        cancel_flag: threading.Event
    ):
        """
        执行运行（在后台线程中）

        使用独立的数据库 session，避免与其他线程共享事务状态。
        """
        print(f"[execute] 开始执行 run_id: {run_id}", flush=True)
        # 创建独立的 session，避免线程间事务污染
        session = create_new_session()
        run_repo = RunRepository(session)

        try:
            # 更新状态为 running
            print(f"[execute] 更新状态为 running", flush=True)
            run_repo.update_status(run_id, RunStatus.RUNNING.value)
            with self._run_lock:
                self._active_runs[run_id]['status'] = 'running'
                self._active_runs[run_id]['started_at'] = datetime.utcnow()

            # 发送开始事件
            sse_manager.emit({
                'source': None,  # 系统事件没有 source
                'event': {
                    'category': EventCategory.LIFECYCLE.value,
                    'action': EventAction.STARTED.value
                },
                'data': {'task': task}
            })

            # 定义事件回调
            def event_callback(event_data: dict):
                # 检查取消标志
                if cancel_flag.is_set():
                    raise InterruptedError("Run was cancelled")

                # 发送 SSE 事件（双写：内存队列 + Redis Stream）
                # SSEManager.emit() 会自动写入 Redis Stream
                sse_manager.emit(event_data)

            # 注册回调到全局注册表（使用 run_id 作为 key，支持跨线程访问）
            register_event_callback(run_id, event_callback)
            register_cancellation_checker(run_id, lambda: cancel_flag.is_set())
            set_current_run_id(run_id)  # 设置当前线程的 run_id 上下文

            # 将 run_id 添加到配置中，以便传递给 hierarchy_system
            config_dict['run_id'] = run_id

            try:
                # 使用输出拦截器执行
                with intercept_output(event_callback) as interceptor:
                    # 执行层级系统（延迟导入以避免 strands 依赖检查）
                    execute_hierarchy = _get_execute_hierarchy()
                    response = execute_hierarchy(config_dict)
            finally:
                # 清除回调注册
                register_event_callback(run_id, None)
                register_cancellation_checker(run_id, None)
                clear_current_run_id()

            # 更新结果
            if response.success:
                run_repo.update_result(
                    run_id,
                    RunStatus.COMPLETED.value,
                    result=response.result,
                    statistics=response.statistics
                )
                sse_manager.emit({
                    'source': None,
                    'event': {
                        'category': EventCategory.LIFECYCLE.value,
                        'action': EventAction.COMPLETED.value
                    },
                    'data': {
                        'result': response.result[:1000] if response.result else None,
                        'statistics': response.statistics
                    }
                })
            else:
                run_repo.update_result(
                    run_id,
                    RunStatus.FAILED.value,
                    error=response.error
                )
                sse_manager.emit({
                    'source': None,
                    'event': {
                        'category': EventCategory.LIFECYCLE.value,
                        'action': EventAction.FAILED.value
                    },
                    'data': {'error': response.error}
                })

        except InterruptedError:
            # 运行被取消
            run_repo.update_status(run_id, RunStatus.CANCELLED.value)
            sse_manager.emit({
                'source': None,
                'event': {
                    'category': EventCategory.LIFECYCLE.value,
                    'action': EventAction.CANCELLED.value
                },
                'data': {}
            })

        except Exception as e:
            # 运行失败
            error_msg = str(e)
            error_details = traceback.format_exc()
            print(f"[execute] ❌ 执行失败: {error_msg}", flush=True)
            print(f"[execute] 详情: {error_details}", flush=True)

            run_repo.update_result(
                run_id,
                RunStatus.FAILED.value,
                error=f"{error_msg}\n{error_details}"
            )
            sse_manager.emit({
                'source': None,
                'event': {
                    'category': EventCategory.LIFECYCLE.value,
                    'action': EventAction.FAILED.value
                },
                'data': {
                    'error': error_msg,
                    'details': error_details
                }
            })

        finally:
            # 清理
            print(f"[execute] 清理 run_id: {run_id}", flush=True)

            # 设置 Redis Stream 过期时间（24 小时后自动删除）
            try:
                event_store = get_event_store()
                event_store.set_expire(run_id, ttl_seconds=86400)
                print(f"[execute] 已设置事件流过期时间: 24小时", flush=True)
            except Exception as e:
                print(f"[execute] 设置事件流过期时间失败: {e}", flush=True)

            # 关闭独立的数据库 session
            try:
                session.close()
            except Exception as e:
                print(f"[execute] 关闭 session 异常: {e}", flush=True)

            sse_manager.close()
            with self._run_lock:
                self._active_runs.pop(run_id, None)
                self._cancellation_flags.pop(run_id, None)
            self.sse_registry.remove(run_id)
            print(f"[execute] 清理完成，剩余 run_ids: {self.sse_registry.get_all_run_ids()}", flush=True)

    def shutdown(self):
        """关闭运行管理器"""
        # 取消所有活跃运行
        with self._run_lock:
            for run_id in list(self._cancellation_flags.keys()):
                self._cancellation_flags[run_id].set()

        # 关闭线程池
        self.executor.shutdown(wait=True)
