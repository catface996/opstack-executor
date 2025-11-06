"""
Tests for ExecutionEngine core functionality.

Tests cover:
1. Async execution capabilities
2. Session management with unique execution IDs
3. State transitions (pending → running → completed)
4. Concurrent execution safety
"""

import asyncio
import pytest
import pytest_asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.hierarchical_agents.execution_engine import ExecutionEngine, ExecutionSession
from src.hierarchical_agents.data_models import (
    ExecutionStatus,
    ExecutionConfig,
    HierarchicalTeam,
    SubTeam,
    SupervisorConfig,
    AgentConfig,
    LLMConfig,
    GlobalConfig,
    ExecutionContext
)
from src.hierarchical_agents.state_manager import StateManager
from src.hierarchical_agents.event_manager import EventManager
from src.hierarchical_agents.error_handler import ErrorHandler


@pytest.fixture
def mock_state_manager():
    """Create a mock StateManager."""
    manager = AsyncMock(spec=StateManager)
    manager.initialize = AsyncMock()
    manager.create_execution = AsyncMock()
    manager.update_execution_status = AsyncMock()
    manager.update_execution_summary = AsyncMock()
    manager.update_team_result = AsyncMock()
    manager.add_error = AsyncMock()
    manager.get_execution_status = AsyncMock()
    return manager


@pytest.fixture
def mock_event_manager():
    """Create a mock EventManager."""
    manager = AsyncMock(spec=EventManager)
    manager.initialize = AsyncMock()
    manager.emit_execution_started = AsyncMock()
    manager.emit_execution_completed = AsyncMock()
    manager.emit_event = AsyncMock()
    manager.get_events_stream = AsyncMock()
    return manager


@pytest.fixture
def mock_error_handler():
    """Create a mock ErrorHandler."""
    handler = MagicMock(spec=ErrorHandler)
    handler.handle_error_async = AsyncMock()
    return handler


@pytest.fixture
def sample_team():
    """Create a sample hierarchical team for testing."""
    llm_config = LLMConfig(
        provider="openai",
        model="gpt-4o",
        temperature=0.7
    )
    
    supervisor_config = SupervisorConfig(
        llm_config=llm_config,
        system_prompt="You are a supervisor",
        user_prompt="Coordinate the team",
        max_iterations=5
    )
    
    agent_config = AgentConfig(
        agent_id="agent_001",
        agent_name="Test Agent",
        llm_config=llm_config,
        system_prompt="You are a test agent",
        user_prompt="Execute test task",
        tools=["test_tool"],
        max_iterations=3
    )
    
    sub_team = SubTeam(
        id="team_001",
        name="Test Team",
        description="A test team",
        supervisor_config=supervisor_config,
        agent_configs=[agent_config]
    )
    
    return HierarchicalTeam(
        team_name="test_hierarchical_team",
        description="A test hierarchical team",
        top_supervisor_config=supervisor_config,
        sub_teams=[sub_team],
        dependencies={},
        global_config=GlobalConfig()
    )


@pytest_asyncio.fixture
async def execution_engine(mock_state_manager, mock_event_manager, mock_error_handler):
    """Create an ExecutionEngine instance for testing."""
    engine = ExecutionEngine(
        state_manager=mock_state_manager,
        event_manager=mock_event_manager,
        error_handler=mock_error_handler
    )
    await engine.initialize()
    yield engine
    await engine.shutdown()


class TestExecutionEngine:
    """Test ExecutionEngine core functionality."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, mock_state_manager, mock_event_manager, mock_error_handler):
        """Test ExecutionEngine initialization."""
        engine = ExecutionEngine(
            state_manager=mock_state_manager,
            event_manager=mock_event_manager,
            error_handler=mock_error_handler
        )
        
        assert not engine._initialized
        
        await engine.initialize()
        
        assert engine._initialized
        mock_state_manager.initialize.assert_called_once()
        mock_event_manager.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_execution_returns_awaitable_coroutine(self, execution_engine, sample_team):
        """Test that start_execution returns an awaitable ExecutionSession."""
        # This tests the first subtask: "异步执行正常：`start_execution()` 返回可等待的协程"
        
        # Mock the _simulate_execution to complete quickly
        with patch.object(ExecutionSession, '_simulate_execution', new_callable=AsyncMock) as mock_simulate:
            mock_simulate.return_value = None
            
            # Call start_execution
            session = await execution_engine.start_execution(sample_team)
            
            # Verify it returns an ExecutionSession
            assert isinstance(session, ExecutionSession)
            assert session.execution_id.startswith("exec_")
            assert session.team == sample_team
            assert session.status == ExecutionStatus.RUNNING
            
            # Wait a bit for the execution to complete
            await asyncio.sleep(0.2)
            
            # Verify the session completed
            assert session.status == ExecutionStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_unique_execution_ids(self, execution_engine, sample_team):
        """Test that each execution creates a unique execution_id."""
        # This tests the second subtask: "会话管理正确：每次执行创建唯一的execution_id"
        
        with patch.object(ExecutionSession, '_simulate_execution', new_callable=AsyncMock):
            # Start multiple executions
            session1 = await execution_engine.start_execution(sample_team)
            session2 = await execution_engine.start_execution(sample_team)
            session3 = await execution_engine.start_execution(sample_team)
            
            # Verify all execution IDs are unique
            execution_ids = [session1.execution_id, session2.execution_id, session3.execution_id]
            assert len(execution_ids) == len(set(execution_ids)), "Execution IDs should be unique"
            
            # Verify all IDs follow the expected format
            for execution_id in execution_ids:
                assert execution_id.startswith("exec_")
                assert len(execution_id) == 17  # "exec_" + 12 hex chars
            
            # Clean up
            await execution_engine.stop_execution(session1.execution_id)
            await execution_engine.stop_execution(session2.execution_id)
            await execution_engine.stop_execution(session3.execution_id)
    
    @pytest.mark.asyncio
    async def test_state_transitions(self, execution_engine, sample_team, mock_state_manager):
        """Test that execution status correctly transitions from pending→running→completed."""
        # This tests the third subtask: "状态跟踪准确：执行状态正确从pending→running→completed转换"
        
        with patch.object(ExecutionSession, '_simulate_execution', new_callable=AsyncMock) as mock_simulate:
            # Make simulation take a bit of time
            async def slow_simulate():
                await asyncio.sleep(0.1)
            mock_simulate.side_effect = slow_simulate
            
            # Start execution
            session = await execution_engine.start_execution(sample_team)
            
            # Initially should be RUNNING (starts immediately)
            assert session.status == ExecutionStatus.RUNNING
            
            # Verify state manager was called to update status to RUNNING
            mock_state_manager.update_execution_status.assert_called_with(
                session.execution_id, ExecutionStatus.RUNNING
            )
            
            # Wait for execution to complete
            await asyncio.sleep(0.2)
            
            # Should now be COMPLETED
            assert session.status == ExecutionStatus.COMPLETED
            
            # Verify state manager was called to update status to COMPLETED
            assert any(
                call.args == (session.execution_id, ExecutionStatus.COMPLETED)
                for call in mock_state_manager.update_execution_status.call_args_list
            )
    
    @pytest.mark.asyncio
    async def test_concurrent_execution_safety(self, execution_engine, sample_team):
        """Test that multiple executions can run concurrently without interference."""
        # This tests the fourth subtask: "并发安全：多个执行可以并发进行而不互相干扰"
        
        with patch.object(ExecutionSession, '_simulate_execution', new_callable=AsyncMock) as mock_simulate:
            # Make each simulation take different amounts of time
            call_count = 0
            async def variable_simulate():
                nonlocal call_count
                call_count += 1
                await asyncio.sleep(0.05 * call_count)  # Different delays
            mock_simulate.side_effect = variable_simulate
            
            # Start multiple concurrent executions
            sessions = []
            for i in range(5):
                session = await execution_engine.start_execution(sample_team)
                sessions.append(session)
            
            # Verify all sessions are running
            for session in sessions:
                assert session.status == ExecutionStatus.RUNNING
            
            # Verify all execution IDs are unique
            execution_ids = [s.execution_id for s in sessions]
            assert len(execution_ids) == len(set(execution_ids))
            
            # Wait for all executions to complete
            await asyncio.sleep(0.5)
            
            # Verify all sessions completed successfully
            for session in sessions:
                assert session.status == ExecutionStatus.COMPLETED
                assert session.completed_at is not None
                assert session.get_duration() is not None
            
            # Verify sessions didn't interfere with each other
            # (each should have different completion times due to different delays)
            completion_times = [s.completed_at for s in sessions]
            assert len(set(completion_times)) == len(completion_times), "Completion times should be different"
    
    @pytest.mark.asyncio
    async def test_execution_session_lifecycle(self, execution_engine, sample_team):
        """Test complete execution session lifecycle."""
        with patch.object(ExecutionSession, '_simulate_execution', new_callable=AsyncMock):
            # Start execution
            session = await execution_engine.start_execution(sample_team)
            
            # Test session properties
            assert session.execution_id.startswith("exec_")
            assert session.team == sample_team
            assert session.is_active()
            assert not session.is_completed()
            
            # Test pause/resume
            await session.pause()
            assert session.status == ExecutionStatus.PAUSED
            
            await session.resume()
            assert session.status == ExecutionStatus.RUNNING
            
            # Wait for completion
            await asyncio.sleep(0.2)
            
            # Test completed state
            assert session.is_completed()
            assert not session.is_active()
            assert session.get_duration() is not None
    
    @pytest.mark.asyncio
    async def test_execution_engine_management(self, execution_engine, sample_team):
        """Test ExecutionEngine session management capabilities."""
        with patch.object(ExecutionSession, '_simulate_execution', new_callable=AsyncMock):
            # Start multiple executions
            session1 = await execution_engine.start_execution(sample_team)
            session2 = await execution_engine.start_execution(sample_team)
            
            # Test session retrieval
            retrieved_session1 = await execution_engine.get_execution_session(session1.execution_id)
            assert retrieved_session1 == session1
            
            # Test active executions list
            active_executions = await execution_engine.list_active_executions()
            assert session1.execution_id in active_executions
            assert session2.execution_id in active_executions
            
            # Test execution counts
            counts = await execution_engine.get_execution_count()
            assert counts["running"] >= 2
            assert counts["total"] >= 2
            
            # Test stopping execution
            stopped = await execution_engine.stop_execution(session1.execution_id)
            assert stopped
            
            # Test cleanup
            await asyncio.sleep(0.2)  # Let executions complete
            cleaned = await execution_engine.cleanup_completed_sessions()
            assert cleaned >= 0
    
    @pytest.mark.asyncio
    async def test_execution_engine_shutdown(self, execution_engine, sample_team):
        """Test ExecutionEngine graceful shutdown."""
        with patch.object(ExecutionSession, '_simulate_execution', new_callable=AsyncMock) as mock_simulate:
            # Make simulation run longer
            async def long_simulate():
                await asyncio.sleep(1.0)
            mock_simulate.side_effect = long_simulate
            
            # Start execution
            session = await execution_engine.start_execution(sample_team)
            assert session.is_active()
            
            # Shutdown engine
            await execution_engine.shutdown()
            
            # Verify shutdown state
            assert execution_engine._shutdown
            
            # Verify cannot start new executions
            with pytest.raises(RuntimeError, match="ExecutionEngine is shutdown"):
                await execution_engine.start_execution(sample_team)
    
    @pytest.mark.asyncio
    async def test_error_handling_during_execution(self, execution_engine, sample_team, mock_error_handler):
        """Test error handling during execution."""
        with patch.object(ExecutionSession, '_simulate_execution', new_callable=AsyncMock) as mock_simulate:
            # Make simulation raise an error
            mock_simulate.side_effect = RuntimeError("Test execution error")
            
            # Make error handler also raise to trigger failure path
            mock_error_handler.handle_error_async.side_effect = RuntimeError("Error handler failed")
            
            # Start execution
            session = await execution_engine.start_execution(sample_team)
            
            # Wait for execution to handle the error
            await asyncio.sleep(0.2)
            
            # Verify error handler was called
            mock_error_handler.handle_error_async.assert_called_once()
            
            # Verify session failed
            assert session.status == ExecutionStatus.FAILED
    
    @pytest.mark.asyncio
    async def test_execution_context_creation(self, execution_engine, sample_team):
        """Test that ExecutionContext is properly created."""
        with patch.object(ExecutionSession, '_simulate_execution', new_callable=AsyncMock):
            session = await execution_engine.start_execution(sample_team)
            
            # Verify context is properly set
            assert isinstance(session.context, ExecutionContext)
            assert session.context.execution_id == session.execution_id
            assert session.context.team_id == sample_team.team_name
            assert isinstance(session.context.config, ExecutionConfig)
            assert isinstance(session.context.started_at, datetime)
    
    @pytest.mark.asyncio
    async def test_execution_with_custom_config(self, execution_engine, sample_team):
        """Test execution with custom ExecutionConfig."""
        custom_config = ExecutionConfig(
            stream_events=False,
            save_intermediate_results=False,
            max_parallel_teams=2
        )
        
        with patch.object(ExecutionSession, '_simulate_execution', new_callable=AsyncMock):
            session = await execution_engine.start_execution(sample_team, custom_config)
            
            # Verify custom config is used
            assert session.config == custom_config
            assert session.context.config == custom_config
            assert not session.config.stream_events
            assert not session.config.save_intermediate_results
            assert session.config.max_parallel_teams == 2


class TestExecutionSession:
    """Test ExecutionSession functionality."""
    
    @pytest.mark.asyncio
    async def test_session_creation(self, sample_team, mock_state_manager, mock_event_manager, mock_error_handler):
        """Test ExecutionSession creation."""
        execution_id = "test_exec_123"
        config = ExecutionConfig()
        
        session = ExecutionSession(
            execution_id=execution_id,
            team=sample_team,
            config=config,
            state_manager=mock_state_manager,
            event_manager=mock_event_manager,
            error_handler=mock_error_handler
        )
        
        assert session.execution_id == execution_id
        assert session.team == sample_team
        assert session.config == config
        assert session.status == ExecutionStatus.PENDING
        assert isinstance(session.context, ExecutionContext)
    
    @pytest.mark.asyncio
    async def test_session_start_stop(self, sample_team, mock_state_manager, mock_event_manager, mock_error_handler):
        """Test ExecutionSession start and stop."""
        session = ExecutionSession(
            execution_id="test_exec_123",
            team=sample_team,
            config=ExecutionConfig(),
            state_manager=mock_state_manager,
            event_manager=mock_event_manager,
            error_handler=mock_error_handler
        )
        
        with patch.object(session, '_simulate_execution', new_callable=AsyncMock):
            # Test start
            await session.start()
            assert session.status == ExecutionStatus.RUNNING
            assert session.is_active()
            
            # Test stop
            await session.stop()
            assert not session.is_active()
    
    @pytest.mark.asyncio
    async def test_session_pause_resume(self, sample_team, mock_state_manager, mock_event_manager, mock_error_handler):
        """Test ExecutionSession pause and resume."""
        session = ExecutionSession(
            execution_id="test_exec_123",
            team=sample_team,
            config=ExecutionConfig(),
            state_manager=mock_state_manager,
            event_manager=mock_event_manager,
            error_handler=mock_error_handler
        )
        
        with patch.object(session, '_simulate_execution', new_callable=AsyncMock):
            await session.start()
            
            # Test pause
            await session.pause()
            assert session.status == ExecutionStatus.PAUSED
            
            # Test resume
            await session.resume()
            assert session.status == ExecutionStatus.RUNNING
    
    @pytest.mark.asyncio
    async def test_session_state_methods(self, sample_team, mock_state_manager, mock_event_manager, mock_error_handler):
        """Test ExecutionSession state checking methods."""
        session = ExecutionSession(
            execution_id="test_exec_123",
            team=sample_team,
            config=ExecutionConfig(),
            state_manager=mock_state_manager,
            event_manager=mock_event_manager,
            error_handler=mock_error_handler
        )
        
        # Test initial state
        assert not session.is_active()
        assert not session.is_completed()
        assert session.get_duration() is None
        
        with patch.object(session, '_simulate_execution', new_callable=AsyncMock):
            await session.start()
            
            # Test running state
            assert session.is_active()
            assert not session.is_completed()
            
            # Complete the session
            session.status = ExecutionStatus.COMPLETED
            session.completed_at = datetime.now()
            
            # Test completed state
            assert not session.is_active()
            assert session.is_completed()
            assert isinstance(session.get_duration(), int)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])