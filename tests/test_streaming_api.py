"""
Tests for the streaming API functionality using httpx.

This module contains tests specifically for the Server-Sent Events (SSE) streaming
functionality, including connection establishment, event pushing, format compliance,
connection management, and concurrent connections.
"""

import asyncio
import json
import pytest
from datetime import datetime
from typing import AsyncIterator, List
from unittest.mock import Mock, patch, AsyncMock
from contextlib import asynccontextmanager

import httpx
from fastapi.testclient import TestClient

from src.hierarchical_agents.main import app
from src.hierarchical_agents.data_models import ExecutionEvent, ExecutionStatus


@asynccontextmanager
async def async_test_client():
    """Create an async httpx client for testing ASGI app."""
    from httpx import ASGITransport
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_execution_state():
    """Mock execution state for testing."""
    from src.hierarchical_agents.state_manager import ExecutionState
    from src.hierarchical_agents.data_models import ExecutionContext, TeamState, ExecutionConfig
    
    context = ExecutionContext(
        execution_id="exec_test123456",
        team_id="ht_test123456",
        config=ExecutionConfig(),
        started_at=datetime.now()
    )
    
    team_state = TeamState(
        next="running",
        team_id="mock_team_001",
        dependencies_met=True,
        execution_status=ExecutionStatus.RUNNING
    )
    
    return ExecutionState(
        execution_id="exec_test123456",
        team_id="ht_test123456",
        status=ExecutionStatus.RUNNING,
        context=context,
        events=[],
        team_states={"mock_team_001": team_state},
        results={},
        created_at=datetime.now(),
        updated_at=datetime.now()
    )


@pytest.fixture
def sample_events():
    """Sample execution events for testing."""
    return [
        ExecutionEvent(
            timestamp=datetime(2024, 1, 15, 10, 35, 0),
            event_type="execution_started",
            source_type="system",
            execution_id="exec_test123456",
            content="Started execution for team ht_test123456",
            status="started"
        ),
        ExecutionEvent(
            timestamp=datetime(2024, 1, 15, 10, 35, 5),
            event_type="supervisor_routing",
            source_type="supervisor",
            execution_id="exec_test123456",
            supervisor_id="supervisor_main",
            supervisor_name="顶级监督者",
            team_id="ht_test123456",
            action="routing",
            content="分析任务需求，选择研究团队开始执行",
            selected_team="team_a7b9c2d4e5f6"
        ),
        ExecutionEvent(
            timestamp=datetime(2024, 1, 15, 10, 35, 15),
            event_type="agent_started",
            source_type="agent",
            execution_id="exec_test123456",
            team_id="team_a7b9c2d4e5f6",
            agent_id="agent_search_001",
            agent_name="医疗文献搜索专家",
            action="started",
            content="开始搜索AI医疗应用相关信息",
            status="running"
        ),
        ExecutionEvent(
            timestamp=datetime(2024, 1, 15, 10, 37, 30),
            event_type="agent_progress",
            source_type="agent",
            execution_id="exec_test123456",
            team_id="team_a7b9c2d4e5f6",
            agent_id="agent_search_001",
            agent_name="医疗文献搜索专家",
            action="progress",
            content="已找到5篇相关研究论文",
            progress=30
        ),
        ExecutionEvent(
            timestamp=datetime(2024, 1, 15, 11, 5, 0),
            event_type="execution_completed",
            source_type="system",
            execution_id="exec_test123456",
            status="completed",
            result="/api/v1/executions/exec_test123456/results"
        )
    ]


class TestSSEConnectionEstablishment:
    """Test SSE connection establishment using httpx."""
    
    @pytest.mark.asyncio
    async def test_sse_connection_with_httpx(self, mock_execution_state, sample_events):
        """Test SSE connection establishment using httpx."""
        execution_id = "exec_test123456"
        
        with patch('src.hierarchical_agents.api.executions.event_manager') as mock_event_manager, \
             patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            
            # Setup mocks
            mock_event_manager._subscribers = {}
            mock_event_manager.initialize = AsyncMock()
            mock_event_manager.get_buffered_events = AsyncMock(return_value=sample_events[:2])
            
            async def mock_event_stream():
                for event in sample_events[2:]:
                    yield event
                    await asyncio.sleep(0.1)  # Simulate real-time streaming
            
            mock_event_manager.get_events_stream = AsyncMock(return_value=mock_event_stream())
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            # Test with httpx
            async with async_test_client() as client:
                async with client.stream(
                    "GET", 
                    f"/api/v1/executions/{execution_id}/stream"
                ) as response:
                    
                    assert response.status_code == 200
                    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
                    assert response.headers["cache-control"] == "no-cache"
                    assert response.headers["connection"] == "keep-alive"
                    
                    # Read first few events
                    events_received = []
                    async for chunk in response.aiter_text():
                        if chunk.strip():
                            events_received.append(chunk)
                        if len(events_received) >= 3:  # Stop after receiving a few events
                            break
                    
                    # Verify we received events
                    assert len(events_received) > 0
                    
                    # Check SSE format
                    combined_content = "".join(events_received)
                    assert "event: execution_started" in combined_content
                    assert "data: {" in combined_content
    
    @pytest.mark.asyncio
    async def test_sse_connection_invalid_execution(self):
        """Test SSE connection with invalid execution ID."""
        invalid_execution_id = "invalid_id"
        
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(f"/api/v1/executions/{invalid_execution_id}/stream")
            
            assert response.status_code == 404
            data = response.json()
            assert data["success"] is False
            assert data["code"] == "EXECUTION_NOT_FOUND"
    
    @pytest.mark.asyncio
    async def test_sse_connection_execution_not_found(self):
        """Test SSE connection for non-existent execution."""
        execution_id = "exec_notfound123"
        
        with patch('src.hierarchical_agents.api.executions.event_manager') as mock_event_manager, \
             patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            
            mock_event_manager._subscribers = {}
            mock_event_manager.initialize = AsyncMock()
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=None)
            
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                response = await client.get(f"/api/v1/executions/{execution_id}/stream")
                
                assert response.status_code == 404
                data = response.json()
                assert data["success"] is False
                assert data["code"] == "EXECUTION_NOT_FOUND"


class TestEventPushing:
    """Test event pushing and verification."""
    
    @pytest.mark.asyncio
    async def test_event_generation_and_pushing(self, mock_execution_state, sample_events):
        """Test that events are properly generated and pushed via SSE."""
        execution_id = "exec_test123456"
        
        with patch('src.hierarchical_agents.api.executions.event_manager') as mock_event_manager, \
             patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            
            mock_event_manager._subscribers = {}
            mock_event_manager.initialize = AsyncMock()
            mock_event_manager.get_buffered_events = AsyncMock(return_value=[])
            
            # Create a controlled event stream
            async def controlled_event_stream():
                for event in sample_events:
                    yield event
                    await asyncio.sleep(0.05)  # Small delay between events
            
            mock_event_manager.get_events_stream = AsyncMock(return_value=controlled_event_stream())
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                async with client.stream(
                    "GET", 
                    f"/api/v1/executions/{execution_id}/stream"
                ) as response:
                    
                    assert response.status_code == 200
                    
                    # Collect events
                    received_events = []
                    event_data = []
                    
                    async for chunk in response.aiter_text():
                        if chunk.strip():
                            received_events.append(chunk)
                            
                            # Parse SSE events
                            if chunk.startswith("event: "):
                                event_type = chunk.split("event: ")[1].strip()
                            elif chunk.startswith("data: "):
                                try:
                                    data = json.loads(chunk.split("data: ")[1].strip())
                                    event_data.append((event_type, data))
                                except json.JSONDecodeError:
                                    pass
                        
                        # Stop after receiving all expected events
                        if len(event_data) >= len(sample_events):
                            break
                    
                    # Verify all events were received
                    assert len(event_data) == len(sample_events)
                    
                    # Verify event types and content
                    expected_types = [event.event_type for event in sample_events]
                    received_types = [event_type for event_type, _ in event_data]
                    assert received_types == expected_types
                    
                    # Verify specific event content
                    for i, (event_type, data) in enumerate(event_data):
                        expected_event = sample_events[i]
                        assert data["event_type"] == expected_event.event_type
                        assert data["source_type"] == expected_event.source_type
                        assert data["execution_id"] == expected_event.execution_id
    
    @pytest.mark.asyncio
    async def test_buffered_events_sent_first(self, mock_execution_state, sample_events):
        """Test that buffered events are sent before real-time events."""
        execution_id = "exec_test123456"
        
        buffered_events = sample_events[:2]  # First 2 events are buffered
        realtime_events = sample_events[2:]  # Rest are real-time
        
        with patch('src.hierarchical_agents.api.executions.event_manager') as mock_event_manager, \
             patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            
            mock_event_manager._subscribers = {}
            mock_event_manager.initialize = AsyncMock()
            mock_event_manager.get_buffered_events = AsyncMock(return_value=buffered_events)
            
            async def realtime_event_stream():
                for event in realtime_events:
                    yield event
                    await asyncio.sleep(0.05)
            
            mock_event_manager.get_events_stream = AsyncMock(return_value=realtime_event_stream())
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                async with client.stream(
                    "GET", 
                    f"/api/v1/executions/{execution_id}/stream"
                ) as response:
                    
                    received_event_types = []
                    
                    async for chunk in response.aiter_text():
                        if chunk.startswith("event: "):
                            event_type = chunk.split("event: ")[1].strip()
                            received_event_types.append(event_type)
                        
                        if len(received_event_types) >= len(sample_events):
                            break
                    
                    # Verify order: buffered events first, then real-time events
                    expected_order = [event.event_type for event in sample_events]
                    assert received_event_types == expected_order


class TestSSEFormatCompliance:
    """Test Server-Sent Events format compliance."""
    
    @pytest.mark.asyncio
    async def test_sse_format_compliance(self, mock_execution_state, sample_events):
        """Test that events conform to SSE specification."""
        execution_id = "exec_test123456"
        
        with patch('src.hierarchical_agents.api.executions.event_manager') as mock_event_manager, \
             patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            
            mock_event_manager._subscribers = {}
            mock_event_manager.initialize = AsyncMock()
            mock_event_manager.get_buffered_events = AsyncMock(return_value=[sample_events[0]])
            
            async def single_event_stream():
                yield sample_events[1]
            
            mock_event_manager.get_events_stream = AsyncMock(return_value=single_event_stream())
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                async with client.stream(
                    "GET", 
                    f"/api/v1/executions/{execution_id}/stream"
                ) as response:
                    
                    full_content = ""
                    async for chunk in response.aiter_text():
                        full_content += chunk
                        if full_content.count("\n\n") >= 2:  # Stop after 2 complete events
                            break
                    
                    # Split into individual SSE events
                    events = full_content.split("\n\n")
                    events = [event for event in events if event.strip()]
                    
                    for event in events:
                        lines = event.strip().split("\n")
                        
                        # Each event should have event: and data: lines
                        assert any(line.startswith("event: ") for line in lines)
                        assert any(line.startswith("data: ") for line in lines)
                        
                        # Extract and validate JSON data
                        for line in lines:
                            if line.startswith("data: "):
                                json_data = line[6:]  # Remove "data: " prefix
                                try:
                                    parsed_data = json.loads(json_data)
                                    # Should have required fields
                                    assert "timestamp" in parsed_data
                                    assert "event_type" in parsed_data
                                    assert "source_type" in parsed_data
                                    assert "execution_id" in parsed_data
                                    
                                    # Timestamp should be ISO format
                                    assert parsed_data["timestamp"].endswith("Z")
                                    
                                except json.JSONDecodeError:
                                    pytest.fail(f"Invalid JSON in SSE data: {json_data}")
    
    @pytest.mark.asyncio
    async def test_sse_headers_compliance(self, mock_execution_state):
        """Test that SSE response headers comply with specification."""
        execution_id = "exec_test123456"
        
        with patch('src.hierarchical_agents.api.executions.event_manager') as mock_event_manager, \
             patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            
            mock_event_manager._subscribers = {}
            mock_event_manager.initialize = AsyncMock()
            mock_event_manager.get_buffered_events = AsyncMock(return_value=[])
            
            async def empty_event_stream():
                return
                yield  # Make it an async generator
            
            mock_event_manager.get_events_stream = AsyncMock(return_value=empty_event_stream())
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                async with client.stream(
                    "GET", 
                    f"/api/v1/executions/{execution_id}/stream"
                ) as response:
                    
                    # Check required SSE headers
                    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
                    assert response.headers["cache-control"] == "no-cache"
                    assert response.headers["connection"] == "keep-alive"
                    
                    # Check CORS headers
                    assert response.headers["access-control-allow-origin"] == "*"
                    assert "access-control-allow-headers" in response.headers
    
    @pytest.mark.asyncio
    async def test_unicode_handling_in_sse(self, mock_execution_state):
        """Test proper Unicode handling in SSE events."""
        execution_id = "exec_test123456"
        
        unicode_event = ExecutionEvent(
            timestamp=datetime(2024, 1, 15, 10, 35, 0),
            event_type="agent_started",
            source_type="agent",
            execution_id=execution_id,
            agent_name="医疗文献搜索专家",
            content="开始搜索AI医疗应用相关信息"
        )
        
        with patch('src.hierarchical_agents.api.executions.event_manager') as mock_event_manager, \
             patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            
            mock_event_manager._subscribers = {}
            mock_event_manager.initialize = AsyncMock()
            mock_event_manager.get_buffered_events = AsyncMock(return_value=[unicode_event])
            
            async def empty_stream():
                return
                yield
            
            mock_event_manager.get_events_stream = AsyncMock(return_value=empty_stream())
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                async with client.stream(
                    "GET", 
                    f"/api/v1/executions/{execution_id}/stream"
                ) as response:
                    
                    content = ""
                    async for chunk in response.aiter_text():
                        content += chunk
                        if "\n\n" in content:  # Complete event received
                            break
                    
                    # Verify Unicode characters are properly encoded
                    assert "医疗文献搜索专家" in content
                    assert "开始搜索AI医疗应用相关信息" in content
                    
                    # Verify JSON is valid
                    data_line = [line for line in content.split("\n") if line.startswith("data: ")][0]
                    json_data = data_line[6:]  # Remove "data: " prefix
                    parsed_data = json.loads(json_data)
                    assert parsed_data["agent_name"] == "医疗文献搜索专家"
                    assert parsed_data["content"] == "开始搜索AI医疗应用相关信息"


class TestConnectionManagement:
    """Test connection management and resource cleanup."""
    
    @pytest.mark.asyncio
    async def test_connection_cleanup_on_client_disconnect(self, mock_execution_state):
        """Test that resources are cleaned up when client disconnects."""
        execution_id = "exec_test123456"
        
        with patch('src.hierarchical_agents.api.executions.event_manager') as mock_event_manager, \
             patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            
            mock_event_manager._subscribers = {}
            mock_event_manager.initialize = AsyncMock()
            mock_event_manager.get_buffered_events = AsyncMock(return_value=[])
            
            # Create a long-running event stream
            async def long_running_stream():
                for i in range(100):  # Many events
                    yield ExecutionEvent(
                        timestamp=datetime.now(),
                        event_type="agent_progress",
                        source_type="agent",
                        execution_id=execution_id,
                        progress=i
                    )
                    await asyncio.sleep(0.1)
            
            mock_event_manager.get_events_stream = AsyncMock(return_value=long_running_stream())
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                async with client.stream(
                    "GET", 
                    f"/api/v1/executions/{execution_id}/stream"
                ) as response:
                    
                    # Read a few events then disconnect
                    event_count = 0
                    async for chunk in response.aiter_text():
                        if chunk.startswith("event: "):
                            event_count += 1
                        if event_count >= 3:  # Disconnect after 3 events
                            break
                    
                    # Connection should close gracefully
                    assert event_count >= 3
    
    @pytest.mark.asyncio
    async def test_error_handling_in_event_stream(self, mock_execution_state):
        """Test error handling when event stream encounters errors."""
        execution_id = "exec_test123456"
        
        with patch('src.hierarchical_agents.api.executions.event_manager') as mock_event_manager, \
             patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            
            mock_event_manager._subscribers = {}
            mock_event_manager.initialize = AsyncMock()
            mock_event_manager.get_buffered_events = AsyncMock(return_value=[])
            
            # Create an event stream that raises an exception
            async def error_stream():
                yield ExecutionEvent(
                    timestamp=datetime.now(),
                    event_type="execution_started",
                    source_type="system",
                    execution_id=execution_id
                )
                raise Exception("Stream error")
            
            mock_event_manager.get_events_stream = AsyncMock(return_value=error_stream())
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                async with client.stream(
                    "GET", 
                    f"/api/v1/executions/{execution_id}/stream"
                ) as response:
                    
                    content = ""
                    async for chunk in response.aiter_text():
                        content += chunk
                        # Look for error event
                        if "stream_error" in content:
                            break
                    
                    # Should receive error event
                    assert "event: stream_error" in content
                    assert '"event_type": "stream_error"' in content
                    assert '"source_type": "system"' in content


class TestConcurrentConnections:
    """Test handling of multiple concurrent SSE connections."""
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_connections(self, mock_execution_state, sample_events):
        """Test that multiple clients can connect simultaneously."""
        execution_id = "exec_test123456"
        
        with patch('src.hierarchical_agents.api.executions.event_manager') as mock_event_manager, \
             patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            
            mock_event_manager._subscribers = {}
            mock_event_manager.initialize = AsyncMock()
            mock_event_manager.get_buffered_events = AsyncMock(return_value=[sample_events[0]])
            
            async def shared_event_stream():
                for event in sample_events[1:3]:  # Send a few events
                    yield event
                    await asyncio.sleep(0.1)
            
            mock_event_manager.get_events_stream = AsyncMock(return_value=shared_event_stream())
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            # Create multiple concurrent connections
            async def client_connection(client_id: int) -> List[str]:
                """Simulate a client connection and return received events."""
                received_events = []
                
                async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                    async with client.stream(
                        "GET", 
                        f"/api/v1/executions/{execution_id}/stream"
                    ) as response:
                        
                        assert response.status_code == 200
                        
                        async for chunk in response.aiter_text():
                            if chunk.startswith("event: "):
                                event_type = chunk.split("event: ")[1].strip()
                                received_events.append(f"client_{client_id}:{event_type}")
                            
                            # Stop after receiving a few events
                            if len(received_events) >= 3:
                                break
                
                return received_events
            
            # Run multiple clients concurrently
            tasks = [client_connection(i) for i in range(3)]
            results = await asyncio.gather(*tasks)
            
            # All clients should receive events
            for client_events in results:
                assert len(client_events) >= 2  # At least buffered + some real-time events
                assert any("execution_started" in event for event in client_events)
    
    @pytest.mark.asyncio
    async def test_connection_isolation(self, mock_execution_state):
        """Test that connections are properly isolated."""
        execution_id1 = "exec_test123456"
        execution_id2 = "exec_test789012"
        
        # Create different execution states
        execution_state2 = mock_execution_state
        execution_state2.execution_id = execution_id2
        
        with patch('src.hierarchical_agents.api.executions.event_manager') as mock_event_manager, \
             patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            
            mock_event_manager._subscribers = {}
            mock_event_manager.initialize = AsyncMock()
            
            # Different events for different executions
            def get_buffered_events(exec_id):
                if exec_id == execution_id1:
                    return [ExecutionEvent(
                        timestamp=datetime.now(),
                        event_type="execution_started",
                        source_type="system",
                        execution_id=execution_id1,
                        content="Execution 1 started"
                    )]
                else:
                    return [ExecutionEvent(
                        timestamp=datetime.now(),
                        event_type="execution_started",
                        source_type="system",
                        execution_id=execution_id2,
                        content="Execution 2 started"
                    )]
            
            mock_event_manager.get_buffered_events = AsyncMock(side_effect=get_buffered_events)
            
            async def empty_stream():
                return
                yield
            
            mock_event_manager.get_events_stream = AsyncMock(return_value=empty_stream())
            
            def get_execution_state(exec_id):
                if exec_id == execution_id1:
                    return mock_execution_state
                else:
                    return execution_state2
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(side_effect=get_execution_state)
            
            # Connect to both executions simultaneously
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                async with client.stream(
                    "GET", 
                    f"/api/v1/executions/{execution_id1}/stream"
                ) as response1:
                    async with client.stream(
                        "GET", 
                        f"/api/v1/executions/{execution_id2}/stream"
                    ) as response2:
                        
                        # Both connections should succeed
                        assert response1.status_code == 200
                        assert response2.status_code == 200
                        
                        # Read content from both streams
                        content1 = ""
                        content2 = ""
                        
                        async for chunk in response1.aiter_text():
                            content1 += chunk
                            if "\n\n" in content1:
                                break
                        
                        async for chunk in response2.aiter_text():
                            content2 += chunk
                            if "\n\n" in content2:
                                break
                        
                        # Each should receive events for their respective execution
                        assert execution_id1 in content1
                        assert "Execution 1 started" in content1
                        assert execution_id2 in content2
                        assert "Execution 2 started" in content2
                        
                        # Cross-contamination check
                        assert execution_id2 not in content1
                        assert execution_id1 not in content2


class TestStreamingAPIIntegration:
    """Integration tests for the streaming API."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_streaming_workflow(self, mock_execution_state, sample_events):
        """Test complete streaming workflow from connection to completion."""
        execution_id = "exec_test123456"
        
        with patch('src.hierarchical_agents.api.executions.event_manager') as mock_event_manager, \
             patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            
            mock_event_manager._subscribers = {}
            mock_event_manager.initialize = AsyncMock()
            mock_event_manager.get_buffered_events = AsyncMock(return_value=[sample_events[0]])
            
            # Simulate complete execution lifecycle
            async def lifecycle_event_stream():
                for event in sample_events[1:]:
                    yield event
                    await asyncio.sleep(0.05)
            
            mock_event_manager.get_events_stream = AsyncMock(return_value=lifecycle_event_stream())
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                async with client.stream(
                    "GET", 
                    f"/api/v1/executions/{execution_id}/stream"
                ) as response:
                    
                    assert response.status_code == 200
                    
                    # Track execution lifecycle
                    lifecycle_events = []
                    
                    async for chunk in response.aiter_text():
                        if chunk.startswith("event: "):
                            event_type = chunk.split("event: ")[1].strip()
                            lifecycle_events.append(event_type)
                        
                        # Stop when execution completes
                        if "execution_completed" in lifecycle_events:
                            break
                    
                    # Verify complete lifecycle
                    expected_lifecycle = [
                        "execution_started",
                        "supervisor_routing", 
                        "agent_started",
                        "agent_progress",
                        "execution_completed"
                    ]
                    
                    assert lifecycle_events == expected_lifecycle
    
    @pytest.mark.asyncio
    async def test_streaming_performance_under_load(self, mock_execution_state):
        """Test streaming performance with high event volume."""
        execution_id = "exec_test123456"
        
        # Generate many events
        many_events = []
        for i in range(50):
            many_events.append(ExecutionEvent(
                timestamp=datetime.now(),
                event_type="agent_progress",
                source_type="agent",
                execution_id=execution_id,
                progress=i * 2,
                content=f"Progress update {i}"
            ))
        
        with patch('src.hierarchical_agents.api.executions.event_manager') as mock_event_manager, \
             patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            
            mock_event_manager._subscribers = {}
            mock_event_manager.initialize = AsyncMock()
            mock_event_manager.get_buffered_events = AsyncMock(return_value=[])
            
            async def high_volume_stream():
                for event in many_events:
                    yield event
                    await asyncio.sleep(0.01)  # Fast event generation
            
            mock_event_manager.get_events_stream = AsyncMock(return_value=high_volume_stream())
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            start_time = asyncio.get_event_loop().time()
            
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                async with client.stream(
                    "GET", 
                    f"/api/v1/executions/{execution_id}/stream"
                ) as response:
                    
                    events_received = 0
                    async for chunk in response.aiter_text():
                        if chunk.startswith("event: "):
                            events_received += 1
                        
                        if events_received >= len(many_events):
                            break
                    
                    end_time = asyncio.get_event_loop().time()
                    duration = end_time - start_time
                    
                    # Should handle high volume efficiently
                    assert events_received == len(many_events)
                    assert duration < 10.0  # Should complete within 10 seconds
                    
                    # Calculate events per second
                    events_per_second = events_received / duration
                    assert events_per_second > 5  # Should handle at least 5 events/second