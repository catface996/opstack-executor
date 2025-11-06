"""
Execution engine for hierarchical multi-agent system.

This module provides the core execution engine that manages the lifecycle
of hierarchical team executions, including async execution, state management,
session management, and coordination with other system components.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional, Union
from contextlib import asynccontextmanager

from .data_models import (
    ExecutionStatus,
    ExecutionEvent,
    ExecutionContext,
    ExecutionConfig,
    ExecutionSummary,
    TeamResult,
    HierarchicalTeam,
    ErrorInfo,
    ExecutionMetrics
)
from .state_manager import StateManager
from .event_manager import EventManager
from .error_handler import ErrorHandler, ErrorContext as ErrorHandlerContext
from .hierarchical_executor import HierarchicalExecutor
from .performance_monitor import monitor_execution


class ExecutionSession:
    """
    Represents an active execution session.
    
    Manages the lifecycle of a single hierarchical team execution,
    including state tracking, event emission, and error handling.
    """
    
    def __init__(
        self,
        execution_id: str,
        team: HierarchicalTeam,
        config: ExecutionConfig,
        state_manager: StateManager,
        event_manager: EventManager,
        error_handler: ErrorHandler,
        hierarchical_executor: HierarchicalExecutor
    ):
        """Initialize execution session."""
        self.execution_id = execution_id
        self.team = team
        self.config = config
        self.state_manager = state_manager
        self.event_manager = event_manager
        self.error_handler = error_handler
        self.hierarchical_executor = hierarchical_executor
        
        self.context = ExecutionContext(
            execution_id=execution_id,
            team_id=team.team_name,
            config=config,
            started_at=datetime.now()
        )
        
        self.status = ExecutionStatus.PENDING
        self.started_at = datetime.now()
        self.completed_at: Optional[datetime] = None
        self.results: Dict[str, TeamResult] = {}
        self.errors: List[ErrorInfo] = []
        self.metrics = ExecutionMetrics()
        
        # Execution control
        self._stop_event = asyncio.Event()
        self._execution_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start the execution session."""
        if self.status != ExecutionStatus.PENDING:
            raise RuntimeError(f"Cannot start execution in status: {self.status}")
        
        # Update status to running
        self.status = ExecutionStatus.RUNNING
        await self.state_manager.update_execution_status(self.execution_id, self.status)
        
        # Emit execution started event
        await self.event_manager.emit_execution_started(
            self.execution_id, 
            self.team.team_name
        )
        
        # Start execution task
        self._execution_task = asyncio.create_task(self._execute())
    
    async def stop(self, graceful: bool = True) -> None:
        """Stop the execution session."""
        if self.status not in [ExecutionStatus.RUNNING, ExecutionStatus.PAUSED]:
            return
        
        self._stop_event.set()
        
        if self._execution_task and not self._execution_task.done():
            if graceful:
                # Wait for graceful shutdown
                try:
                    await asyncio.wait_for(self._execution_task, timeout=30.0)
                except asyncio.TimeoutError:
                    # Force cancellation if graceful shutdown takes too long
                    self._execution_task.cancel()
                    try:
                        await self._execution_task
                    except asyncio.CancelledError:
                        pass
            else:
                # Force immediate cancellation
                self._execution_task.cancel()
                try:
                    await self._execution_task
                except asyncio.CancelledError:
                    pass
    
    async def pause(self) -> None:
        """Pause the execution session."""
        if self.status != ExecutionStatus.RUNNING:
            raise RuntimeError(f"Cannot pause execution in status: {self.status}")
        
        self.status = ExecutionStatus.PAUSED
        await self.state_manager.update_execution_status(self.execution_id, self.status)
    
    async def resume(self) -> None:
        """Resume the execution session."""
        if self.status != ExecutionStatus.PAUSED:
            raise RuntimeError(f"Cannot resume execution in status: {self.status}")
        
        self.status = ExecutionStatus.RUNNING
        await self.state_manager.update_execution_status(self.execution_id, self.status)
    
    async def _execute(self) -> None:
        """Main execution loop using hierarchical executor."""
        try:
            # Use performance monitoring for execution
            async with monitor_execution(self.execution_id, self.team.team_name):
                # Use hierarchical executor for actual execution
                team_results = await self.hierarchical_executor.execute_hierarchical_team(
                    team=self.team,
                    execution_context=self.context
                )
            
                # Store results
                self.results = team_results
                
                # Mark as completed
                self.status = ExecutionStatus.COMPLETED
                self.completed_at = datetime.now()
                
                # Update state
                await self.state_manager.update_execution_status(self.execution_id, self.status)
                
                # Create execution summary
                summary = ExecutionSummary(
                    status=self.status.value,
                    started_at=self.started_at,
                    completed_at=self.completed_at,
                    total_duration=int((self.completed_at - self.started_at).total_seconds()),
                    teams_executed=len(team_results),
                    agents_involved=sum(
                        len(result.agents) if result.agents else 0 
                        for result in team_results.values()
                    )
                )
                
                await self.state_manager.update_execution_summary(self.execution_id, summary)
                
                # Emit completion event
                await self.event_manager.emit_execution_completed(
                    self.execution_id,
                    self.status,
                    f"/api/v1/executions/{self.execution_id}/results"
                )
            
        except asyncio.CancelledError:
            self.status = ExecutionStatus.FAILED
            self.completed_at = datetime.now()
            await self.state_manager.update_execution_status(self.execution_id, self.status)
            raise
        except Exception as e:
            # Handle execution error
            error_context = ErrorHandlerContext(
                execution_id=self.execution_id,
                team_id=self.team.team_name,
                operation="execution"
            )
            
            try:
                await self.error_handler.handle_error_async(e, error_context)
            except Exception:
                # If error handling fails, mark execution as failed
                self.status = ExecutionStatus.FAILED
                self.completed_at = datetime.now()
                
                error_info = ErrorInfo(
                    error_code="EXECUTION_FAILED",
                    message=str(e),
                    timestamp=datetime.now(),
                    context={"execution_id": self.execution_id, "team_id": self.team.team_name}
                )
                
                self.errors.append(error_info)
                await self.state_manager.add_error(self.execution_id, error_info)
                await self.state_manager.update_execution_status(self.execution_id, self.status)
                
                # Emit failure event
                await self.event_manager.emit_execution_completed(
                    self.execution_id,
                    self.status
                )
    
    async def _simulate_execution(self) -> None:
        """Simulate execution for testing purposes."""
        # Simulate processing each sub-team
        for i, sub_team in enumerate(self.team.sub_teams):
            if self._stop_event.is_set():
                break
            
            # Simulate team processing
            await asyncio.sleep(0.1)  # Simulate work
            
            # Create mock result
            result = TeamResult(
                status="completed",
                duration=100,
                agents={
                    agent.agent_id: {
                        "agent_name": agent.agent_name,
                        "status": "completed",
                        "output": f"Mock output from {agent.agent_name}"
                    }
                    for agent in sub_team.agent_configs
                },
                output=f"Mock output from {sub_team.name}"
            )
            
            self.results[sub_team.id] = result
            await self.state_manager.update_team_result(self.execution_id, sub_team.id, result)
            
            # Emit progress events
            progress = int(((i + 1) / len(self.team.sub_teams)) * 100)
            event = ExecutionEvent(
                timestamp=datetime.now(),
                event_type="execution_progress",
                source_type="system",
                execution_id=self.execution_id,
                content=f"Completed team {sub_team.name}",
                progress=progress
            )
            await self.event_manager.emit_event(event)
    
    def is_active(self) -> bool:
        """Check if execution session is active."""
        return self.status in [ExecutionStatus.RUNNING, ExecutionStatus.PAUSED]
    
    def is_completed(self) -> bool:
        """Check if execution session is completed."""
        return self.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]
    
    def get_duration(self) -> Optional[int]:
        """Get execution duration in seconds."""
        if not self.completed_at:
            return None
        return int((self.completed_at - self.started_at).total_seconds())


class ExecutionEngine:
    """
    Core execution engine for hierarchical multi-agent system.
    
    Manages the lifecycle of execution sessions, provides async execution
    capabilities, and coordinates with state management, event streaming,
    and error handling components.
    """
    
    def __init__(
        self,
        state_manager: StateManager,
        event_manager: EventManager,
        error_handler: Optional[ErrorHandler] = None
    ):
        """Initialize ExecutionEngine."""
        self.state_manager = state_manager
        self.event_manager = event_manager
        self.error_handler = error_handler or ErrorHandler()
        
        # Initialize hierarchical executor
        self.hierarchical_executor = HierarchicalExecutor(
            state_manager=state_manager,
            event_manager=event_manager,
            error_handler=self.error_handler
        )
        
        # Active sessions
        self._sessions: Dict[str, ExecutionSession] = {}
        self._session_lock = asyncio.Lock()
        
        # Engine state
        self._initialized = False
        self._shutdown = False
    
    async def initialize(self) -> None:
        """Initialize the execution engine."""
        if self._initialized:
            return
        
        # Ensure dependencies are initialized
        if hasattr(self.state_manager, 'initialize'):
            await self.state_manager.initialize()
        
        if hasattr(self.event_manager, 'initialize'):
            await self.event_manager.initialize()
        
        self._initialized = True
    
    async def shutdown(self) -> None:
        """Shutdown the execution engine gracefully."""
        if self._shutdown:
            return
        
        self._shutdown = True
        
        # Stop all active sessions
        async with self._session_lock:
            stop_tasks = []
            for session in self._sessions.values():
                if session.is_active():
                    stop_tasks.append(session.stop(graceful=True))
            
            if stop_tasks:
                await asyncio.gather(*stop_tasks, return_exceptions=True)
            
            self._sessions.clear()
    
    async def start_execution(
        self,
        team: HierarchicalTeam,
        config: Optional[ExecutionConfig] = None
    ) -> ExecutionSession:
        """
        Start a new execution session.
        
        Args:
            team: The hierarchical team to execute
            config: Execution configuration (optional)
            
        Returns:
            ExecutionSession: The created execution session
            
        Raises:
            RuntimeError: If engine is not initialized or is shutdown
        """
        if not self._initialized:
            raise RuntimeError("ExecutionEngine not initialized")
        
        if self._shutdown:
            raise RuntimeError("ExecutionEngine is shutdown")
        
        # Generate unique execution ID
        execution_id = self._generate_execution_id()
        
        # Use default config if not provided
        if config is None:
            config = ExecutionConfig()
        
        # Create execution context
        context = ExecutionContext(
            execution_id=execution_id,
            team_id=team.team_name,
            config=config,
            started_at=datetime.now()
        )
        
        # Create execution session
        session = ExecutionSession(
            execution_id=execution_id,
            team=team,
            config=config,
            state_manager=self.state_manager,
            event_manager=self.event_manager,
            error_handler=self.error_handler,
            hierarchical_executor=self.hierarchical_executor
        )
        
        # Store session
        async with self._session_lock:
            self._sessions[execution_id] = session
        
        # Initialize state in StateManager
        await self.state_manager.create_execution(execution_id, team.team_name, context)
        
        # Start the session
        await session.start()
        
        return session
    
    async def get_execution_session(self, execution_id: str) -> Optional[ExecutionSession]:
        """Get an execution session by ID."""
        async with self._session_lock:
            return self._sessions.get(execution_id)
    
    async def stop_execution(self, execution_id: str, graceful: bool = True) -> bool:
        """
        Stop an execution session.
        
        Args:
            execution_id: The execution ID to stop
            graceful: Whether to stop gracefully
            
        Returns:
            bool: True if session was stopped, False if not found
        """
        session = await self.get_execution_session(execution_id)
        if not session:
            return False
        
        await session.stop(graceful)
        
        # Remove from active sessions if completed
        if session.is_completed():
            async with self._session_lock:
                self._sessions.pop(execution_id, None)
        
        return True
    
    async def pause_execution(self, execution_id: str) -> bool:
        """Pause an execution session."""
        session = await self.get_execution_session(execution_id)
        if not session:
            return False
        
        await session.pause()
        return True
    
    async def resume_execution(self, execution_id: str) -> bool:
        """Resume an execution session."""
        session = await self.get_execution_session(execution_id)
        if not session:
            return False
        
        await session.resume()
        return True
    
    async def get_execution_status(self, execution_id: str) -> Optional[ExecutionStatus]:
        """Get execution status."""
        # First check active sessions
        session = await self.get_execution_session(execution_id)
        if session:
            return session.status
        
        # Fall back to state manager
        return await self.state_manager.get_execution_status(execution_id)
    
    async def stream_events(self, execution_id: str) -> AsyncIterator[ExecutionEvent]:
        """
        Stream events for a specific execution.
        
        Args:
            execution_id: The execution ID to stream events for
            
        Yields:
            ExecutionEvent: Events from the execution
        """
        async for event in self.event_manager.get_events_stream(execution_id):
            yield event
    
    async def list_active_executions(self) -> List[str]:
        """List all active execution IDs."""
        async with self._session_lock:
            return [
                execution_id for execution_id, session in self._sessions.items()
                if session.is_active()
            ]
    
    async def get_execution_count(self) -> Dict[str, int]:
        """Get count of executions by status."""
        async with self._session_lock:
            counts = {
                "total": len(self._sessions),
                "running": 0,
                "paused": 0,
                "completed": 0,
                "failed": 0
            }
            
            for session in self._sessions.values():
                if session.status == ExecutionStatus.RUNNING:
                    counts["running"] += 1
                elif session.status == ExecutionStatus.PAUSED:
                    counts["paused"] += 1
                elif session.status == ExecutionStatus.COMPLETED:
                    counts["completed"] += 1
                elif session.status == ExecutionStatus.FAILED:
                    counts["failed"] += 1
            
            return counts
    
    async def cleanup_completed_sessions(self) -> int:
        """Clean up completed sessions and return count of cleaned sessions."""
        cleaned_count = 0
        
        async with self._session_lock:
            completed_sessions = [
                execution_id for execution_id, session in self._sessions.items()
                if session.is_completed()
            ]
            
            for execution_id in completed_sessions:
                self._sessions.pop(execution_id, None)
                cleaned_count += 1
        
        return cleaned_count
    
    def _generate_execution_id(self) -> str:
        """Generate a unique execution ID."""
        return f"exec_{uuid.uuid4().hex[:12]}"
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get execution engine statistics."""
        execution_counts = await self.get_execution_count()
        
        return {
            "initialized": self._initialized,
            "shutdown": self._shutdown,
            "execution_counts": execution_counts,
            "total_sessions": len(self._sessions)
        }


# Utility functions for common operations
async def create_execution_engine(
    state_manager: StateManager,
    event_manager: EventManager,
    error_handler: Optional[ErrorHandler] = None
) -> ExecutionEngine:
    """Create and initialize an ExecutionEngine instance."""
    engine = ExecutionEngine(state_manager, event_manager, error_handler)
    await engine.initialize()
    return engine


@asynccontextmanager
async def execution_engine_context(
    state_manager: StateManager,
    event_manager: EventManager,
    error_handler: Optional[ErrorHandler] = None
):
    """Context manager for ExecutionEngine operations."""
    engine = await create_execution_engine(state_manager, event_manager, error_handler)
    try:
        yield engine
    finally:
        await engine.shutdown()