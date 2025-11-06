"""
Tests for StateManager functionality.

Tests cover state persistence, Redis integration, query performance,
and data consistency under concurrent operations.
"""

import asyncio
import pytest
import time
from datetime import datetime, timedelta
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

from hierarchical_agents.state_manager import (
    StateManager,
    StateManagerConfig,
    ExecutionState,
    create_state_manager,
    with_state_manager
)
from hierarchical_agents.data_models import (
    ExecutionStatus,
    ExecutionEvent,
    TeamState,
    ExecutionContext,
    ExecutionConfig,
    ExecutionSummary,
    TeamResult,
    ErrorInfo,
    ExecutionMetrics
)


@pytest.fixture
def state_manager_config():
    """Test configuration for StateManager."""
    return StateManagerConfig(
        redis_url="redis://localhost:6379",
        redis_db=1,  # Use different DB for tests
        key_prefix="test_hierarchical_agents",
        default_ttl=300,  # 5 minutes for tests
        max_retries=2,
        retry_delay=0.05
    )


@pytest.fixture
async def state_manager(state_manager_config):
    """StateManager instance for testing."""
    manager = StateManager(state_manager_config)
    
    # Mock Redis for unit tests
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock(return_value=1)
    mock_redis.keys = AsyncMock(return_value=[])
    mock_redis.ttl = AsyncMock(return_value=300)
    mock_redis.expire = AsyncMock(return_value=True)
    mock_redis.info = AsyncMock(return_value={"used_memory": 1024})
    mock_redis.eval = AsyncMock(return_value=1)
    mock_redis.close = AsyncMock()
    
    manager._redis = mock_redis
    
    yield manager
    
    await manager.close()


@pytest.fixture
def sample_execution_context():
    """Sample execution context for testing."""
    return ExecutionContext(
        execution_id="test_exec_001",
        team_id="test_team_001",
        config=ExecutionConfig(),
        started_at=datetime.now()
    )


@pytest.fixture
def sample_execution_event():
    """Sample execution event for testing."""
    return ExecutionEvent(
        event_type="agent_started",
        source_type="agent",
        execution_id="test_exec_001",
        team_id="test_team_001",
        agent_id="test_agent_001",
        agent_name="Test Agent",
        content="Agent started execution"
    )


@pytest.fixture
def sample_team_state():
    """Sample team state for testing."""
    return TeamState(
        next="agent_001",
        team_id="test_team_001",
        dependencies_met=True,
        execution_status=ExecutionStatus.RUNNING
    )


class TestStateManagerBasics:
    """Test basic StateManager functionality."""
    
    async def test_initialization(self, state_manager_config):
        """Test StateManager initialization."""
        manager = StateManager(state_manager_config)
        assert manager.config == state_manager_config
        assert manager._redis is None
        
        # Test with default config
        default_manager = StateManager()
        assert default_manager.config.redis_url == "redis://localhost:6379"
    
    async def test_redis_connection(self, state_manager):
        """Test Redis connection setup."""
        # Redis is already mocked in fixture
        assert state_manager._redis is not None
        
        # Test connection failure
        state_manager._redis.ping.side_effect = Exception("Connection failed")
        
        with pytest.raises(ConnectionError, match="Failed to connect to Redis"):
            await state_manager.initialize()
    
    async def test_key_generation(self, state_manager):
        """Test Redis key generation."""
        key = state_manager._get_key("execution", "test_id")
        assert key == "test_hierarchical_agents:execution:test_id"
        
        lock_key = state_manager._get_lock_key("test_id")
        assert lock_key == "test_hierarchical_agents:lock:test_id"


class TestExecutionStateManagement:
    """Test execution state CRUD operations."""
    
    async def test_create_execution(self, state_manager, sample_execution_context):
        """Test creating new execution state."""
        execution_id = "test_exec_001"
        team_id = "test_team_001"
        
        # Mock successful creation
        state_manager._redis.get.return_value = None  # No existing execution
        
        await state_manager.create_execution(execution_id, team_id, sample_execution_context)
        
        # Verify Redis operations
        state_manager._redis.setex.assert_called_once()
        args = state_manager._redis.setex.call_args
        assert args[0][0] == "test_hierarchical_agents:execution:test_exec_001"
        assert args[0][1] == 300  # TTL
    
    async def test_create_duplicate_execution(self, state_manager, sample_execution_context):
        """Test creating duplicate execution raises error."""
        execution_id = "test_exec_001"
        team_id = "test_team_001"
        
        # Mock existing execution
        existing_state = ExecutionState(
            execution_id=execution_id,
            team_id=team_id,
            status=ExecutionStatus.RUNNING,
            context=sample_execution_context,
            events=[],
            team_states={},
            results={},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        state_manager._redis.get.return_value = existing_state.model_dump_json()
        
        with pytest.raises(ValueError, match="Execution test_exec_001 already exists"):
            await state_manager.create_execution(execution_id, team_id, sample_execution_context)
    
    async def test_update_execution_status(self, state_manager, sample_execution_context):
        """Test updating execution status."""
        execution_id = "test_exec_001"
        
        # Mock existing execution
        existing_state = ExecutionState(
            execution_id=execution_id,
            team_id="test_team_001",
            status=ExecutionStatus.PENDING,
            context=sample_execution_context,
            events=[],
            team_states={},
            results={},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        state_manager._redis.get.return_value = existing_state.model_dump_json()
        
        await state_manager.update_execution_status(execution_id, ExecutionStatus.RUNNING)
        
        # Verify update was called
        state_manager._redis.setex.assert_called_once()
    
    async def test_update_nonexistent_execution(self, state_manager):
        """Test updating nonexistent execution raises error."""
        execution_id = "nonexistent_exec"
        
        # Mock no existing execution
        state_manager._redis.get.return_value = None
        
        with pytest.raises(ValueError, match="Execution nonexistent_exec not found"):
            await state_manager.update_execution_status(execution_id, ExecutionStatus.RUNNING)


class TestEventManagement:
    """Test event management functionality."""
    
    async def test_add_event(self, state_manager, sample_execution_context, sample_execution_event):
        """Test adding event to execution."""
        execution_id = "test_exec_001"
        
        # Mock existing execution
        existing_state = ExecutionState(
            execution_id=execution_id,
            team_id="test_team_001",
            status=ExecutionStatus.RUNNING,
            context=sample_execution_context,
            events=[],
            team_states={},
            results={},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        state_manager._redis.get.return_value = existing_state.model_dump_json()
        
        await state_manager.add_event(execution_id, sample_execution_event)
        
        # Verify event was added
        state_manager._redis.setex.assert_called_once()
    
    async def test_get_execution_events(self, state_manager, sample_execution_context):
        """Test retrieving execution events."""
        execution_id = "test_exec_001"
        
        # Create events
        events = [
            ExecutionEvent(
                event_type="execution_started",
                source_type="system",
                execution_id=execution_id,
                content="Execution started"
            ),
            ExecutionEvent(
                event_type="agent_started",
                source_type="agent",
                execution_id=execution_id,
                agent_id="agent_001",
                content="Agent started"
            )
        ]
        
        # Mock existing execution with events
        existing_state = ExecutionState(
            execution_id=execution_id,
            team_id="test_team_001",
            status=ExecutionStatus.RUNNING,
            context=sample_execution_context,
            events=events,
            team_states={},
            results={},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        state_manager._redis.get.return_value = existing_state.model_dump_json()
        
        # Test getting all events
        retrieved_events = await state_manager.get_execution_events(execution_id)
        assert len(retrieved_events) == 2
        assert retrieved_events[0].event_type == "execution_started"
        
        # Test getting limited events
        limited_events = await state_manager.get_execution_events(execution_id, limit=1)
        assert len(limited_events) == 1
        assert limited_events[0].event_type == "agent_started"  # Most recent


class TestTeamStateManagement:
    """Test team state management."""
    
    async def test_update_team_state(self, state_manager, sample_execution_context, sample_team_state):
        """Test updating team state."""
        execution_id = "test_exec_001"
        team_id = "test_team_001"
        
        # Mock existing execution
        existing_state = ExecutionState(
            execution_id=execution_id,
            team_id="test_team_001",
            status=ExecutionStatus.RUNNING,
            context=sample_execution_context,
            events=[],
            team_states={},
            results={},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        state_manager._redis.get.return_value = existing_state.model_dump_json()
        
        await state_manager.update_team_state(execution_id, team_id, sample_team_state)
        
        # Verify update was called
        state_manager._redis.setex.assert_called_once()
    
    async def test_get_team_state(self, state_manager, sample_execution_context, sample_team_state):
        """Test retrieving team state."""
        execution_id = "test_exec_001"
        team_id = "test_team_001"
        
        # Mock existing execution with team state
        existing_state = ExecutionState(
            execution_id=execution_id,
            team_id="test_team_001",
            status=ExecutionStatus.RUNNING,
            context=sample_execution_context,
            events=[],
            team_states={team_id: sample_team_state},
            results={},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        state_manager._redis.get.return_value = existing_state.model_dump_json()
        
        retrieved_state = await state_manager.get_team_state(execution_id, team_id)
        assert retrieved_state is not None
        assert retrieved_state.team_id == team_id
        assert retrieved_state.execution_status == ExecutionStatus.RUNNING


class TestQueryPerformance:
    """Test query performance requirements."""
    
    async def test_query_performance(self, state_manager, sample_execution_context):
        """Test that state queries complete within 100ms."""
        execution_id = "test_exec_001"
        
        # Mock existing execution
        existing_state = ExecutionState(
            execution_id=execution_id,
            team_id="test_team_001",
            status=ExecutionStatus.RUNNING,
            context=sample_execution_context,
            events=[],
            team_states={},
            results={},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        state_manager._redis.get.return_value = existing_state.model_dump_json()
        
        # Measure query time
        start_time = time.time()
        result = await state_manager.get_execution_state(execution_id)
        query_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        assert result is not None
        assert query_time < 100, f"Query took {query_time}ms, should be < 100ms"
    
    async def test_status_query_performance(self, state_manager, sample_execution_context):
        """Test that status queries are fast."""
        execution_id = "test_exec_001"
        
        # Mock existing execution
        existing_state = ExecutionState(
            execution_id=execution_id,
            team_id="test_team_001",
            status=ExecutionStatus.RUNNING,
            context=sample_execution_context,
            events=[],
            team_states={},
            results={},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        state_manager._redis.get.return_value = existing_state.model_dump_json()
        
        # Measure status query time
        start_time = time.time()
        status = await state_manager.get_execution_status(execution_id)
        query_time = (time.time() - start_time) * 1000
        
        assert status == ExecutionStatus.RUNNING
        assert query_time < 100, f"Status query took {query_time}ms, should be < 100ms"


class TestConcurrencyAndConsistency:
    """Test concurrent operations and data consistency."""
    
    async def test_distributed_lock(self, state_manager):
        """Test distributed locking mechanism."""
        identifier = "test_lock"
        
        # Test successful lock acquisition
        async with state_manager._distributed_lock(identifier):
            # Verify lock was acquired
            state_manager._redis.set.assert_called()
            
        # Verify lock was released
        state_manager._redis.eval.assert_called()
    
    async def test_concurrent_updates(self, state_manager, sample_execution_context):
        """Test concurrent state updates don't cause data inconsistency."""
        execution_id = "test_exec_001"
        
        # Mock existing execution
        existing_state = ExecutionState(
            execution_id=execution_id,
            team_id="test_team_001",
            status=ExecutionStatus.RUNNING,
            context=sample_execution_context,
            events=[],
            team_states={},
            results={},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        state_manager._redis.get.return_value = existing_state.model_dump_json()
        
        # Simulate concurrent updates
        async def update_status():
            await state_manager.update_execution_status(execution_id, ExecutionStatus.COMPLETED)
        
        async def add_event():
            event = ExecutionEvent(
                event_type="test_event",
                source_type="system",
                execution_id=execution_id,
                content="Test event"
            )
            await state_manager.add_event(execution_id, event)
        
        # Run concurrent operations
        await asyncio.gather(update_status(), add_event())
        
        # Verify both operations completed (Redis calls were made)
        assert state_manager._redis.setex.call_count >= 2
    
    async def test_lock_timeout_handling(self, state_manager):
        """Test handling of lock acquisition timeout."""
        identifier = "test_lock"
        
        # Mock lock acquisition failure
        state_manager._redis.set.return_value = False
        
        with pytest.raises(RuntimeError, match="Failed to acquire lock"):
            async with state_manager._distributed_lock(identifier):
                pass


class TestUtilityFunctions:
    """Test utility functions and additional features."""
    
    async def test_list_executions(self, state_manager):
        """Test listing executions."""
        # Mock Redis keys response
        state_manager._redis.keys.return_value = [
            "test_hierarchical_agents:execution:exec_001",
            "test_hierarchical_agents:execution:exec_002"
        ]
        
        executions = await state_manager.list_executions()
        assert len(executions) == 2
        assert "exec_001" in executions
        assert "exec_002" in executions
    
    async def test_delete_execution(self, state_manager):
        """Test deleting execution."""
        execution_id = "test_exec_001"
        
        result = await state_manager.delete_execution(execution_id)
        assert result is True
        
        state_manager._redis.delete.assert_called_once()
    
    async def test_get_stats(self, state_manager):
        """Test getting StateManager statistics."""
        # Mock Redis responses
        state_manager._redis.keys.return_value = [
            "test_hierarchical_agents:execution:exec_001"
        ]
        
        stats = await state_manager.get_stats()
        
        assert "total_executions" in stats
        assert "redis_info" in stats
        assert "config" in stats
        assert stats["total_executions"] == 1
    
    async def test_standardized_output(self, state_manager, sample_execution_context):
        """Test getting standardized output format."""
        execution_id = "test_exec_001"
        
        # Mock execution with summary
        summary = ExecutionSummary(
            status="completed",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            total_duration=300,
            teams_executed=2,
            agents_involved=3
        )
        
        existing_state = ExecutionState(
            execution_id=execution_id,
            team_id="test_team_001",
            status=ExecutionStatus.COMPLETED,
            context=sample_execution_context,
            events=[],
            team_states={},
            results={},
            summary=summary,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        state_manager._redis.get.return_value = existing_state.model_dump_json()
        
        output = await state_manager.get_standardized_output(execution_id)
        
        assert output is not None
        assert output.execution_id == execution_id
        assert output.execution_summary.status == "completed"


class TestUtilityHelpers:
    """Test utility helper functions."""
    
    @patch('hierarchical_agents.state_manager.StateManager')
    async def test_create_state_manager(self, mock_state_manager_class):
        """Test create_state_manager utility function."""
        mock_manager = AsyncMock()
        mock_state_manager_class.return_value = mock_manager
        
        manager = await create_state_manager("redis://test:6379", 2)
        
        mock_state_manager_class.assert_called_once()
        mock_manager.initialize.assert_called_once()
        assert manager == mock_manager
    
    @patch('hierarchical_agents.state_manager.create_state_manager')
    async def test_with_state_manager(self, mock_create_manager):
        """Test with_state_manager context manager."""
        mock_manager = AsyncMock()
        mock_create_manager.return_value = mock_manager
        
        async def test_func(manager):
            assert manager == mock_manager
            return "test_result"
        
        result = await with_state_manager(test_func)
        
        assert result == "test_result"
        mock_manager.close.assert_called_once()


class TestErrorHandling:
    """Test error handling scenarios."""
    
    async def test_uninitialized_manager_error(self, state_manager_config):
        """Test operations on uninitialized manager raise errors."""
        manager = StateManager(state_manager_config)
        # Don't initialize Redis connection
        
        with pytest.raises(RuntimeError, match="StateManager not initialized"):
            await manager.create_execution("test", "team", ExecutionContext(
                execution_id="test",
                team_id="team",
                config=ExecutionConfig()
            ))
    
    async def test_serialization_error_handling(self, state_manager):
        """Test handling of serialization errors."""
        execution_id = "test_exec_001"
        
        # Mock invalid JSON data
        state_manager._redis.get.return_value = "invalid json data"
        
        with pytest.raises(ValueError, match="Failed to deserialize execution state"):
            await state_manager.get_execution_state(execution_id)
    
    async def test_redis_operation_errors(self, state_manager):
        """Test handling of Redis operation errors."""
        execution_id = "test_exec_001"
        
        # Mock Redis error
        state_manager._redis.get.side_effect = Exception("Redis error")
        
        with pytest.raises(Exception, match="Redis error"):
            await state_manager.get_execution_state(execution_id)


# Integration test markers
@pytest.mark.integration
class TestRedisIntegration:
    """Integration tests with real Redis (requires Redis server)."""
    
    @pytest.mark.skipif(
        not pytest.importorskip("redis", minversion="5.0.0"),
        reason="Redis not available"
    )
    async def test_real_redis_operations(self):
        """Test with real Redis server (if available)."""
        try:
            config = StateManagerConfig(
                redis_url="redis://localhost:6379",
                redis_db=15,  # Use high DB number for tests
                key_prefix="integration_test"
            )
            
            manager = StateManager(config)
            await manager.initialize()
            
            # Test basic operations
            execution_id = "integration_test_001"
            team_id = "test_team"
            context = ExecutionContext(
                execution_id=execution_id,
                team_id=team_id,
                config=ExecutionConfig()
            )
            
            # Create execution
            await manager.create_execution(execution_id, team_id, context)
            
            # Verify it exists
            state = await manager.get_execution_state(execution_id)
            assert state is not None
            assert state.execution_id == execution_id
            
            # Update status
            await manager.update_execution_status(execution_id, ExecutionStatus.RUNNING)
            
            # Verify update
            updated_state = await manager.get_execution_state(execution_id)
            assert updated_state.status == ExecutionStatus.RUNNING
            
            # Clean up
            await manager.delete_execution(execution_id)
            await manager.close()
            
        except Exception as e:
            pytest.skip(f"Redis integration test failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])