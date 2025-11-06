"""
Tests for EventManager functionality.

This module tests event generation, streaming, subscription management,
and all event types according to the ExecutionEvent data model.
"""

import asyncio
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from typing import List

from src.hierarchical_agents.event_manager import (
    EventManager,
    EventManagerConfig,
    EventSubscriber,
    create_event_manager,
    event_manager_context
)
from src.hierarchical_agents.data_models import ExecutionEvent, ExecutionStatus


class TestEventManager:
    """Test EventManager core functionality."""
    
    @pytest_asyncio.fixture
    async def event_manager(self):
        """Create EventManager for testing."""
        config = EventManagerConfig(
            max_subscribers=10,
            event_buffer_size=100,
            cleanup_interval=1,
            max_event_age=60
        )
        manager = EventManager(config)
        await manager.initialize()
        yield manager
        await manager.close()
    
    @pytest.mark.asyncio
    async def test_event_manager_initialization(self):
        """Test EventManager initialization and cleanup."""
        manager = EventManager()
        await manager.initialize()
        
        # Verify initialization
        assert manager._cleanup_task is not None
        assert not manager._cleanup_task.done()
        
        # Test cleanup
        await manager.close()
        assert manager._cleanup_task.cancelled()
        assert len(manager._subscribers) == 0
    
    @pytest.mark.asyncio
    async def test_event_generation_system(self, event_manager):
        """Test system event generation."""
        execution_id = "test_exec_001"
        
        # Test system event creation
        event = event_manager.create_system_event(
            execution_id=execution_id,
            event_type="execution_started",
            content="Test execution started",
            status="started"
        )
        
        # Verify event structure
        assert isinstance(event, ExecutionEvent)
        assert event.execution_id == execution_id
        assert event.event_type == "execution_started"
        assert event.source_type == "system"
        assert event.content == "Test execution started"
        assert event.status == "started"
        assert isinstance(event.timestamp, datetime)
    
    @pytest.mark.asyncio
    async def test_event_generation_supervisor(self, event_manager):
        """Test supervisor event generation."""
        execution_id = "test_exec_002"
        
        # Test supervisor event creation
        event = event_manager.create_supervisor_event(
            execution_id=execution_id,
            event_type="supervisor_routing",
            supervisor_id="supervisor_001",
            supervisor_name="Test Supervisor",
            team_id="team_001",
            content="Routing to best agent",
            action="routing",
            selected_agent="agent_001"
        )
        
        # Verify event structure
        assert isinstance(event, ExecutionEvent)
        assert event.execution_id == execution_id
        assert event.event_type == "supervisor_routing"
        assert event.source_type == "supervisor"
        assert event.supervisor_id == "supervisor_001"
        assert event.supervisor_name == "Test Supervisor"
        assert event.team_id == "team_001"
        assert event.content == "Routing to best agent"
        assert event.action == "routing"
        assert event.selected_agent == "agent_001"
    
    @pytest.mark.asyncio
    async def test_event_generation_agent(self, event_manager):
        """Test agent event generation."""
        execution_id = "test_exec_003"
        
        # Test agent event creation
        event = event_manager.create_agent_event(
            execution_id=execution_id,
            event_type="agent_progress",
            agent_id="agent_001",
            agent_name="Test Agent",
            team_id="team_001",
            content="Processing task",
            action="progress",
            status="running",
            progress=50,
            result="Partial result"
        )
        
        # Verify event structure
        assert isinstance(event, ExecutionEvent)
        assert event.execution_id == execution_id
        assert event.event_type == "agent_progress"
        assert event.source_type == "agent"
        assert event.agent_id == "agent_001"
        assert event.agent_name == "Test Agent"
        assert event.team_id == "team_001"
        assert event.content == "Processing task"
        assert event.action == "progress"
        assert event.status == "running"
        assert event.progress == 50
        assert event.result == "Partial result"
    
    @pytest.mark.asyncio
    async def test_event_format_validation(self, event_manager):
        """Test that events conform to ExecutionEvent data model."""
        execution_id = "test_exec_004"
        
        # Test all event types
        events = [
            event_manager.create_system_event(
                execution_id=execution_id,
                event_type="execution_started",
                status="started"
            ),
            event_manager.create_supervisor_event(
                execution_id=execution_id,
                event_type="supervisor_routing",
                supervisor_id="sup_001",
                supervisor_name="Supervisor"
            ),
            event_manager.create_agent_event(
                execution_id=execution_id,
                event_type="agent_completed",
                agent_id="agent_001",
                agent_name="Agent"
            )
        ]
        
        # Verify all events are valid ExecutionEvent instances
        for event in events:
            assert isinstance(event, ExecutionEvent)
            
            # Verify required fields
            assert event.timestamp is not None
            assert event.event_type is not None
            assert event.source_type in ["system", "supervisor", "agent"]
            assert event.execution_id == execution_id
            
            # Verify data model validation
            event_dict = event.model_dump()
            validated_event = ExecutionEvent.model_validate(event_dict)
            assert validated_event == event
    
    @pytest.mark.asyncio
    async def test_source_type_validation(self, event_manager):
        """Test that source_type field is correctly set."""
        execution_id = "test_exec_005"
        
        # Test system event
        system_event = event_manager.create_system_event(
            execution_id=execution_id,
            event_type="test_event"
        )
        assert system_event.source_type == "system"
        
        # Test supervisor event
        supervisor_event = event_manager.create_supervisor_event(
            execution_id=execution_id,
            event_type="test_event",
            supervisor_id="sup_001",
            supervisor_name="Supervisor"
        )
        assert supervisor_event.source_type == "supervisor"
        
        # Test agent event
        agent_event = event_manager.create_agent_event(
            execution_id=execution_id,
            event_type="test_event",
            agent_id="agent_001",
            agent_name="Agent"
        )
        assert agent_event.source_type == "agent"
    
    @pytest.mark.asyncio
    async def test_subscription_management(self, event_manager):
        """Test subscriber addition, removal, and notification."""
        execution_id = "test_exec_006"
        
        # Test subscription
        subscriber1 = await event_manager.subscribe(execution_id)
        assert isinstance(subscriber1, EventSubscriber)
        assert subscriber1.execution_id == execution_id
        assert subscriber1.active
        
        # Test global subscription
        subscriber2 = await event_manager.subscribe(None)
        assert subscriber2.execution_id is None
        assert subscriber2.active
        
        # Verify subscriber count
        assert await event_manager.get_subscriber_count(execution_id) == 1
        assert await event_manager.get_subscriber_count(None) == 1
        assert await event_manager.get_total_subscriber_count() == 2
        
        # Test unsubscription
        await event_manager.unsubscribe(subscriber1)
        assert not subscriber1.active
        assert await event_manager.get_subscriber_count(execution_id) == 0
        
        # Cleanup
        await event_manager.unsubscribe(subscriber2)
    
    @pytest.mark.asyncio
    async def test_max_subscribers_limit(self, event_manager):
        """Test maximum subscribers limit."""
        subscribers = []
        
        # Create maximum number of subscribers
        for i in range(event_manager.config.max_subscribers):
            subscriber = await event_manager.subscribe(f"exec_{i}")
            subscribers.append(subscriber)
        
        # Try to create one more subscriber
        with pytest.raises(RuntimeError, match="Maximum number of subscribers reached"):
            await event_manager.subscribe("exec_overflow")
        
        # Cleanup
        for subscriber in subscribers:
            await event_manager.unsubscribe(subscriber)
    
    @pytest.mark.asyncio
    async def test_event_streaming(self, event_manager):
        """Test real-time event streaming using asyncio."""
        execution_id = "test_exec_007"
        received_events = []
        
        # Create subscriber
        subscriber = await event_manager.subscribe(execution_id)
        
        # Start event collection task
        async def collect_events():
            async for event in subscriber.get_events():
                received_events.append(event)
                if len(received_events) >= 3:
                    break
        
        collection_task = asyncio.create_task(collect_events())
        
        # Give some time for subscription to be ready
        await asyncio.sleep(0.1)
        
        # Emit test events
        await event_manager.emit_execution_started(execution_id, "team_001")
        await event_manager.emit_agent_started(
            execution_id, "team_001", "agent_001", "Test Agent", "Starting task"
        )
        await event_manager.emit_agent_completed(
            execution_id, "team_001", "agent_001", "Test Agent", "Task completed"
        )
        
        # Wait for events to be collected
        await asyncio.wait_for(collection_task, timeout=2.0)
        
        # Verify events were received
        assert len(received_events) == 3
        assert received_events[0].event_type == "execution_started"
        assert received_events[1].event_type == "agent_started"
        assert received_events[2].event_type == "agent_completed"
        
        # Cleanup
        await event_manager.unsubscribe(subscriber)
    
    @pytest.mark.asyncio
    async def test_event_buffering(self, event_manager):
        """Test event buffering and retrieval."""
        execution_id = "test_exec_008"
        
        # Emit events before subscription
        await event_manager.emit_execution_started(execution_id, "team_001")
        await event_manager.emit_agent_started(
            execution_id, "team_001", "agent_001", "Test Agent", "Starting task"
        )
        
        # Subscribe and verify buffered events are received
        subscriber = await event_manager.subscribe(execution_id)
        
        # Give time for buffered events to be sent
        await asyncio.sleep(0.1)
        
        # Check buffered events
        buffered_events = await event_manager.get_buffered_events(execution_id)
        assert len(buffered_events) == 2
        assert buffered_events[0].event_type == "execution_started"
        assert buffered_events[1].event_type == "agent_started"
        
        # Test limited buffered events
        limited_events = await event_manager.get_buffered_events(execution_id, limit=1)
        assert len(limited_events) == 1
        assert limited_events[0].event_type == "agent_started"  # Most recent
        
        # Cleanup
        await event_manager.unsubscribe(subscriber)
    
    @pytest.mark.asyncio
    async def test_convenience_event_methods(self, event_manager):
        """Test convenience methods for common event types."""
        execution_id = "test_exec_009"
        received_events = []
        
        # Subscribe to events
        subscriber = await event_manager.subscribe(execution_id)
        
        async def collect_events():
            async for event in subscriber.get_events():
                received_events.append(event)
                if len(received_events) >= 6:
                    break
        
        collection_task = asyncio.create_task(collect_events())
        await asyncio.sleep(0.1)
        
        # Test all convenience methods
        await event_manager.emit_execution_started(execution_id, "team_001")
        await event_manager.emit_supervisor_routing(
            execution_id, "sup_001", "Supervisor", "team_001", 
            "Routing to agent", selected_agent="agent_001"
        )
        await event_manager.emit_agent_started(
            execution_id, "team_001", "agent_001", "Agent", "Starting work"
        )
        await event_manager.emit_agent_progress(
            execution_id, "team_001", "agent_001", "Agent", "Making progress", 50
        )
        await event_manager.emit_agent_completed(
            execution_id, "team_001", "agent_001", "Agent", "Work completed"
        )
        await event_manager.emit_execution_completed(
            execution_id, ExecutionStatus.COMPLETED, "/api/results/123"
        )
        
        # Wait for events
        await asyncio.wait_for(collection_task, timeout=2.0)
        
        # Verify all events
        assert len(received_events) == 6
        event_types = [event.event_type for event in received_events]
        expected_types = [
            "execution_started", "supervisor_routing", "agent_started",
            "agent_progress", "agent_completed", "execution_completed"
        ]
        assert event_types == expected_types
        
        # Verify specific event details
        progress_event = received_events[3]
        assert progress_event.progress == 50
        assert progress_event.action == "progress"
        
        completed_event = received_events[5]
        assert completed_event.status == "completed"
        assert completed_event.result == "/api/results/123"
        
        # Cleanup
        await event_manager.unsubscribe(subscriber)
    
    @pytest.mark.asyncio
    async def test_global_subscription(self, event_manager):
        """Test global subscription receiving events from all executions."""
        received_events = []
        
        # Create global subscriber
        global_subscriber = await event_manager.subscribe(None)
        
        async def collect_events():
            async for event in global_subscriber.get_events():
                received_events.append(event)
                if len(received_events) >= 4:
                    break
        
        collection_task = asyncio.create_task(collect_events())
        await asyncio.sleep(0.1)
        
        # Emit events from different executions
        await event_manager.emit_execution_started("exec_001", "team_001")
        await event_manager.emit_execution_started("exec_002", "team_002")
        await event_manager.emit_agent_started(
            "exec_001", "team_001", "agent_001", "Agent 1", "Starting"
        )
        await event_manager.emit_agent_started(
            "exec_002", "team_002", "agent_002", "Agent 2", "Starting"
        )
        
        # Wait for events
        await asyncio.wait_for(collection_task, timeout=2.0)
        
        # Verify global subscriber received all events
        assert len(received_events) == 4
        execution_ids = [event.execution_id for event in received_events]
        assert "exec_001" in execution_ids
        assert "exec_002" in execution_ids
        
        # Cleanup
        await event_manager.unsubscribe(global_subscriber)
    
    @pytest.mark.asyncio
    async def test_event_manager_stats(self, event_manager):
        """Test EventManager statistics."""
        execution_id = "test_exec_010"
        
        # Create some subscribers and events
        subscriber1 = await event_manager.subscribe(execution_id)
        subscriber2 = await event_manager.subscribe(None)
        
        await event_manager.emit_execution_started(execution_id, "team_001")
        await event_manager.emit_agent_started(
            execution_id, "team_001", "agent_001", "Agent", "Starting"
        )
        
        # Get stats
        stats = await event_manager.get_stats()
        
        # Verify stats structure
        assert "total_subscribers" in stats
        assert "execution_subscriptions" in stats
        assert "total_buffered_events" in stats
        assert "buffer_by_execution" in stats
        assert "config" in stats
        
        # Verify stats values
        assert stats["total_subscribers"] == 2
        assert stats["total_buffered_events"] >= 2
        assert execution_id in stats["buffer_by_execution"]
        
        # Cleanup
        await event_manager.unsubscribe(subscriber1)
        await event_manager.unsubscribe(subscriber2)


class TestEventManagerUtilities:
    """Test EventManager utility functions."""
    
    @pytest.mark.asyncio
    async def test_create_event_manager(self):
        """Test create_event_manager utility function."""
        manager = await create_event_manager(max_subscribers=5, event_buffer_size=50)
        
        assert isinstance(manager, EventManager)
        assert manager.config.max_subscribers == 5
        assert manager.config.event_buffer_size == 50
        assert manager._cleanup_task is not None
        
        await manager.close()
    
    @pytest.mark.asyncio
    async def test_event_manager_context(self):
        """Test event_manager_context context manager."""
        async with event_manager_context(max_subscribers=3) as manager:
            assert isinstance(manager, EventManager)
            assert manager.config.max_subscribers == 3
            
            # Test basic functionality
            subscriber = await manager.subscribe("test_exec")
            assert subscriber.active
            
            await manager.emit_execution_started("test_exec", "team_001")
            events = await manager.get_buffered_events("test_exec")
            assert len(events) == 1
        
        # Manager should be closed after context
        assert manager._cleanup_task.cancelled()


class TestEventSubscriber:
    """Test EventSubscriber functionality."""
    
    @pytest.mark.asyncio
    async def test_subscriber_creation(self):
        """Test EventSubscriber creation and properties."""
        subscriber = EventSubscriber("sub_001", "exec_001")
        
        assert subscriber.subscriber_id == "sub_001"
        assert subscriber.execution_id == "exec_001"
        assert subscriber.active
        assert isinstance(subscriber.created_at, datetime)
        assert isinstance(subscriber.last_activity, datetime)
    
    @pytest.mark.asyncio
    async def test_subscriber_event_handling(self):
        """Test subscriber event sending and receiving."""
        subscriber = EventSubscriber("sub_001", "exec_001")
        
        # Create test event
        event = ExecutionEvent(
            timestamp=datetime.now(),
            event_type="test_event",
            source_type="system",
            execution_id="exec_001"
        )
        
        # Send event
        success = await subscriber.send_event(event)
        assert success
        
        # Receive event
        received_events = []
        async def collect_one_event():
            async for event in subscriber.get_events():
                received_events.append(event)
                break
        
        await asyncio.wait_for(collect_one_event(), timeout=1.0)
        
        assert len(received_events) == 1
        assert received_events[0].event_type == "test_event"
        
        # Close subscriber
        subscriber.close()
        assert not subscriber.active
    
    @pytest.mark.asyncio
    async def test_subscriber_queue_overflow(self):
        """Test subscriber queue overflow handling."""
        subscriber = EventSubscriber("sub_001", "exec_001")
        
        # Fill queue beyond capacity
        event = ExecutionEvent(
            timestamp=datetime.now(),
            event_type="test_event",
            source_type="system",
            execution_id="exec_001"
        )
        
        # Send many events to trigger overflow handling
        for i in range(150):  # More than queue capacity
            await subscriber.send_event(event)
        
        # Queue should not exceed reasonable size
        assert subscriber.queue.qsize() <= 100
        
        subscriber.close()


if __name__ == "__main__":
    # Run tests with asyncio
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--run":
        pytest.main([__file__, "-v"])