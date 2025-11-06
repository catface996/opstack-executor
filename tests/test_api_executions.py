"""
Tests for the executions API endpoints.

This module contains comprehensive tests for the hierarchical team execution API,
including execution control, status monitoring, and error handling.
"""

import json
import pytest
import asyncio
from datetime import datetime
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock

from src.hierarchical_agents.main import app
from src.hierarchical_agents.data_models import ExecutionStatus, ExecutionConfig
from src.hierarchical_agents.hierarchical_manager import HierarchicalManagerError


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def valid_execution_config():
    """Valid execution configuration for testing."""
    return {
        "execution_config": {
            "stream_events": True,
            "save_intermediate_results": True,
            "max_parallel_teams": 2
        }
    }


@pytest.fixture
def mock_execution_state():
    """Mock execution state for testing."""
    from src.hierarchical_agents.state_manager import ExecutionState
    from src.hierarchical_agents.data_models import ExecutionContext, TeamState
    
    context = ExecutionContext(
        execution_id="exec_test12345678",  # 17 characters total
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
        execution_id="exec_test12345678",  # 17 characters total
        team_id="ht_test123456",
        status=ExecutionStatus.RUNNING,
        context=context,
        events=[],
        team_states={"mock_team_001": team_state},
        results={},
        created_at=datetime.now(),
        updated_at=datetime.now()
    )


class TestExecuteHierarchicalTeam:
    """Test cases for the execute hierarchical team endpoint."""
    
    def test_execute_team_success(self, client, valid_execution_config):
        """Test successful team execution start."""
        team_id = "ht_123456789"
        
        with patch('src.hierarchical_agents.api.executions.hierarchical_manager') as mock_manager:
            # Mock the hierarchical manager
            mock_manager._initialized = False
            mock_manager.initialize = AsyncMock()
            mock_manager.build_hierarchy = Mock()
            mock_manager.build_hierarchy.return_value = Mock()
            
            # Mock asyncio.create_task to avoid actual background execution
            with patch('asyncio.create_task') as mock_create_task:
                response = client.post(
                    f"/api/v1/hierarchical-teams/{team_id}/execute",
                    json=valid_execution_config
                )
        
        assert response.status_code == 202
        data = response.json()
        assert data["success"] is True
        assert data["code"] == "EXECUTION_STARTED"
        assert data["message"] == "团队执行已启动"
        assert "execution_id" in data["data"]
        assert data["data"]["team_id"] == team_id
        assert data["data"]["status"] == "started"
        assert "stream_url" in data["data"]
    
    def test_execute_team_invalid_team_id(self, client, valid_execution_config):
        """Test execution with invalid team ID format."""
        invalid_team_id = "invalid_id"
        
        response = client.post(
            f"/api/v1/hierarchical-teams/{invalid_team_id}/execute",
            json=valid_execution_config
        )
        
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "TEAM_NOT_FOUND"
    
    def test_execute_team_invalid_config(self, client):
        """Test execution with invalid execution configuration."""
        team_id = "ht_123456789"
        invalid_config = {
            "execution_config": {
                "stream_events": "invalid_boolean",  # Should be boolean
                "max_parallel_teams": -1  # Should be positive
            }
        }
        
        response = client.post(
            f"/api/v1/hierarchical-teams/{team_id}/execute",
            json=invalid_config
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "INVALID_REQUEST"
    
    def test_execute_team_build_error(self, client, valid_execution_config):
        """Test execution when team building fails."""
        team_id = "ht_123456789"
        
        with patch('src.hierarchical_agents.api.executions.hierarchical_manager') as mock_manager:
            mock_manager.build_hierarchy.side_effect = HierarchicalManagerError("Build failed")
            
            response = client.post(
                f"/api/v1/hierarchical-teams/{team_id}/execute",
                json=valid_execution_config
            )
        
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "TEAM_BUILD_ERROR"
    
    def test_execute_team_default_config(self, client):
        """Test execution with default configuration."""
        team_id = "ht_123456789"
        
        with patch('src.hierarchical_agents.api.executions.hierarchical_manager') as mock_manager:
            mock_manager._initialized = False
            mock_manager.initialize = AsyncMock()
            mock_manager.build_hierarchy = Mock()
            mock_manager.build_hierarchy.return_value = Mock()
            
            with patch('asyncio.create_task') as mock_create_task:
                response = client.post(
                    f"/api/v1/hierarchical-teams/{team_id}/execute",
                    json={}  # Empty config should use defaults
                )
        
        assert response.status_code == 202
        data = response.json()
        assert data["success"] is True


class TestGetExecutionStatus:
    """Test cases for the get execution status endpoint."""
    
    def test_get_status_success(self, client, mock_execution_state):
        """Test successful execution status retrieval."""
        execution_id = "exec_test123456"
        
        with patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            mock_state_manager._redis = Mock()  # Mock Redis connection
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            response = client.get(f"/api/v1/executions/{execution_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["code"] == "EXECUTION_FOUND"
        assert data["data"]["execution_id"] == execution_id
        assert data["data"]["status"] == "running"
        assert "progress" in data["data"]
        assert "teams_completed" in data["data"]
    
    def test_get_status_invalid_id(self, client):
        """Test status retrieval with invalid execution ID format."""
        invalid_execution_id = "invalid_id"
        
        response = client.get(f"/api/v1/executions/{invalid_execution_id}")
        
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "EXECUTION_NOT_FOUND"
    
    def test_get_status_not_found(self, client):
        """Test status retrieval for non-existent execution."""
        execution_id = "exec_notfound123"
        
        with patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=None)
            
            response = client.get(f"/api/v1/executions/{execution_id}")
        
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "EXECUTION_NOT_FOUND"
    
    def test_get_status_completed_execution(self, client, mock_execution_state):
        """Test status retrieval for completed execution."""
        execution_id = "exec_test123456"
        
        # Modify mock to show completed status
        mock_execution_state.status = ExecutionStatus.COMPLETED
        mock_execution_state.team_states["mock_team_001"].execution_status = ExecutionStatus.COMPLETED
        
        with patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            response = client.get(f"/api/v1/executions/{execution_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == "completed"
        assert "completed_at" in data["data"]
        assert "duration" in data["data"]


class TestStopExecution:
    """Test cases for the stop execution endpoint."""
    
    def test_stop_execution_success(self, client):
        """Test successful execution stop."""
        execution_id = "exec_test123456"
        
        with patch('src.hierarchical_agents.api.executions.hierarchical_manager') as mock_manager:
            mock_manager._initialized = False
            mock_manager.initialize = AsyncMock()
            mock_manager.stop_execution = AsyncMock(return_value=True)
            
            response = client.delete(f"/api/v1/executions/{execution_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["code"] == "EXECUTION_STOPPED"
    
    def test_stop_execution_not_found(self, client):
        """Test stopping non-existent execution."""
        execution_id = "exec_notfound123"
        
        with patch('src.hierarchical_agents.api.executions.hierarchical_manager') as mock_manager:
            mock_manager._initialized = False
            mock_manager.initialize = AsyncMock()
            mock_manager.stop_execution = AsyncMock(return_value=False)
            
            response = client.delete(f"/api/v1/executions/{execution_id}")
        
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "EXECUTION_NOT_FOUND"
    
    def test_stop_execution_invalid_id(self, client):
        """Test stopping execution with invalid ID format."""
        invalid_execution_id = "invalid_id"
        
        response = client.delete(f"/api/v1/executions/{invalid_execution_id}")
        
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "EXECUTION_NOT_FOUND"


class TestListExecutions:
    """Test cases for the list executions endpoint."""
    
    def test_list_executions_success(self, client):
        """Test successful execution listing."""
        mock_execution_ids = ["exec_test123456", "exec_test789012"]
        
        with patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.list_executions = AsyncMock(return_value=mock_execution_ids)
            
            # Mock execution states
            mock_state1 = Mock()
            mock_state1.team_id = "ht_test123456"
            mock_state1.status = ExecutionStatus.COMPLETED
            mock_state1.created_at = datetime.now()
            mock_state1.updated_at = datetime.now()
            
            mock_state2 = Mock()
            mock_state2.team_id = "ht_test789012"
            mock_state2.status = ExecutionStatus.RUNNING
            mock_state2.created_at = datetime.now()
            mock_state2.updated_at = datetime.now()
            
            mock_state_manager.get_execution_state = AsyncMock(
                side_effect=[mock_state1, mock_state2]
            )
            
            response = client.get("/api/v1/executions")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["code"] == "EXECUTIONS_LISTED"
        assert len(data["data"]["executions"]) == 2
        assert data["data"]["total_count"] == 2
    
    def test_list_executions_with_filters(self, client):
        """Test execution listing with filters."""
        with patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.list_executions = AsyncMock(return_value=[])
            
            response = client.get(
                "/api/v1/executions",
                params={
                    "team_id": "ht_test123456",
                    "execution_status": "running",
                    "page": 1,
                    "page_size": 5
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["page"] == 1
        assert data["data"]["page_size"] == 5
    
    def test_list_executions_invalid_status(self, client):
        """Test execution listing with invalid status filter."""
        response = client.get(
            "/api/v1/executions",
            params={"execution_status": "invalid_status"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "INVALID_PARAMETER"
    
    def test_list_executions_pagination(self, client):
        """Test execution listing pagination."""
        with patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.list_executions = AsyncMock(return_value=[])
            
            # Test invalid pagination parameters
            response = client.get(
                "/api/v1/executions",
                params={"page": 0, "page_size": 200}  # Invalid values
            )
        
        assert response.status_code == 200
        data = response.json()
        # Should be corrected to valid values
        assert data["data"]["page"] == 1
        assert data["data"]["page_size"] == 10


class TestExecutionsHealthCheck:
    """Test cases for the executions API health check."""
    
    def test_health_check_success(self, client):
        """Test successful health check."""
        response = client.get("/api/v1/executions/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["code"] == "HEALTHY"
        assert data["data"]["status"] == "healthy"
        assert "timestamp" in data["data"]
        assert "components" in data["data"]


class TestExecutionAPIIntegration:
    """Integration tests for execution API endpoints."""
    
    def test_execution_lifecycle(self, client, valid_execution_config):
        """Test complete execution lifecycle: start -> status -> stop."""
        team_id = "ht_123456789"
        
        # Mock all dependencies
        with patch('src.hierarchical_agents.api.executions.hierarchical_manager') as mock_manager, \
             patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager, \
             patch('asyncio.create_task') as mock_create_task:
            
            # Setup mocks
            mock_manager._initialized = False
            mock_manager.initialize = AsyncMock()
            mock_manager.build_hierarchy = Mock()
            mock_manager.build_hierarchy.return_value = Mock()
            mock_manager.stop_execution = AsyncMock(return_value=True)
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            
            # Step 1: Start execution
            response = client.post(
                f"/api/v1/hierarchical-teams/{team_id}/execute",
                json=valid_execution_config
            )
            assert response.status_code == 202
            execution_id = response.json()["data"]["execution_id"]
            
            # Step 2: Check status
            mock_execution_state = Mock()
            mock_execution_state.team_id = team_id
            mock_execution_state.status = ExecutionStatus.RUNNING
            mock_execution_state.created_at = datetime.now()
            mock_execution_state.updated_at = datetime.now()
            mock_execution_state.team_states = {}
            
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            response = client.get(f"/api/v1/executions/{execution_id}")
            assert response.status_code == 200
            assert response.json()["data"]["status"] == "running"
            
            # Step 3: Stop execution
            response = client.delete(f"/api/v1/executions/{execution_id}")
            assert response.status_code == 200
            assert response.json()["code"] == "EXECUTION_STOPPED"
    
    def test_error_handling_consistency(self, client):
        """Test that error responses are consistent across endpoints."""
        invalid_execution_id = "invalid_id"
        
        # Test consistent error format across different endpoints
        endpoints_and_methods = [
            ("GET", f"/api/v1/executions/{invalid_execution_id}"),
            ("DELETE", f"/api/v1/executions/{invalid_execution_id}")
        ]
        
        for method, endpoint in endpoints_and_methods:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "DELETE":
                response = client.delete(endpoint)
            
            assert response.status_code == 404
            data = response.json()
            assert data["success"] is False
            assert data["code"] == "EXECUTION_NOT_FOUND"
            assert "message" in data


# Async helper functions for testing
async def mock_async_generator():
    """Mock async generator for testing."""
    yield {"event": "test"}


# Fixtures for mock objects
@pytest.fixture
def mock_hierarchical_team():
    """Mock hierarchical team for testing."""
    team = Mock()
    team.team_name = "test_team"
    team.sub_teams = []
    return team


@pytest.fixture
def mock_execution_context():
    """Mock execution context for testing."""
    from src.hierarchical_agents.data_models import ExecutionContext
    return ExecutionContext(
        execution_id="exec_test123456",
        team_id="ht_test123456",
        config=ExecutionConfig(),
        started_at=datetime.now()
    )


# Performance and edge case tests
class TestStreamExecutionEvents:
    """Test cases for the stream execution events endpoint."""
    
    def test_stream_events_success(self, client, mock_execution_state):
        """Test successful SSE connection establishment."""
        execution_id = "exec_test12345678"  # 17 characters total
        
        # Mock event data
        from src.hierarchical_agents.data_models import ExecutionEvent
        mock_event = ExecutionEvent(
            timestamp=datetime.now(),
            event_type="execution_started",
            source_type="system",
            execution_id=execution_id,
            content="Execution started",
            status="started"
        )
        
        with patch('src.hierarchical_agents.api.executions.event_manager') as mock_event_manager, \
             patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            
            # Setup mocks
            mock_event_manager._subscribers = {}
            mock_event_manager.initialize = AsyncMock()
            mock_event_manager.get_buffered_events = AsyncMock(return_value=[mock_event])
            
            # Mock async generator for event stream
            async def mock_event_stream():
                yield mock_event
            
            mock_event_manager.get_events_stream = AsyncMock(return_value=mock_event_stream())
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            # Test SSE connection
            response = client.get(f"/api/v1/executions/{execution_id}/stream")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert "Cache-Control" in response.headers
        assert response.headers["Cache-Control"] == "no-cache"
        assert "Connection" in response.headers
        assert response.headers["Connection"] == "keep-alive"
    
    def test_stream_events_invalid_execution_id(self, client):
        """Test SSE connection with invalid execution ID format."""
        invalid_execution_id = "invalid_id"
        
        response = client.get(f"/api/v1/executions/{invalid_execution_id}/stream")
        
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "EXECUTION_NOT_FOUND"
    
    def test_stream_events_execution_not_found(self, client):
        """Test SSE connection for non-existent execution."""
        execution_id = "exec_notfound123"
        
        with patch('src.hierarchical_agents.api.executions.event_manager') as mock_event_manager, \
             patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            
            mock_event_manager._subscribers = {}
            mock_event_manager.initialize = AsyncMock()
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=None)
            
            response = client.get(f"/api/v1/executions/{execution_id}/stream")
        
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "EXECUTION_NOT_FOUND"
    
    def test_stream_events_sse_format(self, client, mock_execution_state):
        """Test that events are properly formatted as SSE."""
        execution_id = "exec_test12345678"  # 17 characters total
        
        from src.hierarchical_agents.data_models import ExecutionEvent
        mock_event = ExecutionEvent(
            timestamp=datetime.now(),
            event_type="supervisor_routing",
            source_type="supervisor",
            execution_id=execution_id,
            supervisor_id="supervisor_main",
            supervisor_name="顶级监督者",
            team_id="ht_123456789",
            action="routing",
            content="分析任务需求，选择研究团队开始执行",
            selected_team="team_a7b9c2d4e5f6"
        )
        
        with patch('src.hierarchical_agents.api.executions.event_manager') as mock_event_manager, \
             patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            
            mock_event_manager._subscribers = {}
            mock_event_manager.initialize = AsyncMock()
            mock_event_manager.get_buffered_events = AsyncMock(return_value=[mock_event])
            
            async def mock_event_stream():
                yield mock_event
            
            mock_event_manager.get_events_stream = AsyncMock(return_value=mock_event_stream())
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            response = client.get(f"/api/v1/executions/{execution_id}/stream")
        
        # Check response format
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        
        # Verify SSE format
        assert "event: supervisor_routing\n" in content
        assert "data: {" in content
        assert '"event_type": "supervisor_routing"' in content
        assert '"source_type": "supervisor"' in content
        assert '"supervisor_name": "顶级监督者"' in content
        assert content.endswith("\n\n")
    
    def test_stream_events_multiple_event_types(self, client, mock_execution_state):
        """Test streaming multiple different event types."""
        execution_id = "exec_test12345678"  # 17 characters total
        
        from src.hierarchical_agents.data_models import ExecutionEvent
        
        # Create different event types
        events = [
            ExecutionEvent(
                timestamp=datetime.now(),
                event_type="execution_started",
                source_type="system",
                execution_id=execution_id,
                status="started"
            ),
            ExecutionEvent(
                timestamp=datetime.now(),
                event_type="supervisor_routing",
                source_type="supervisor",
                execution_id=execution_id,
                supervisor_id="supervisor_main",
                supervisor_name="顶级监督者",
                action="routing"
            ),
            ExecutionEvent(
                timestamp=datetime.now(),
                event_type="agent_started",
                source_type="agent",
                execution_id=execution_id,
                agent_id="agent_001",
                agent_name="研究专家",
                action="started",
                status="running"
            ),
            ExecutionEvent(
                timestamp=datetime.now(),
                event_type="execution_completed",
                source_type="system",
                execution_id=execution_id,
                status="completed"
            )
        ]
        
        with patch('src.hierarchical_agents.api.executions.event_manager') as mock_event_manager, \
             patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            
            mock_event_manager._subscribers = {}
            mock_event_manager.initialize = AsyncMock()
            mock_event_manager.get_buffered_events = AsyncMock(return_value=events)
            
            async def mock_event_stream():
                for event in events:
                    yield event
            
            mock_event_manager.get_events_stream = AsyncMock(return_value=mock_event_stream())
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            response = client.get(f"/api/v1/executions/{execution_id}/stream")
        
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        
        # Verify all event types are present
        assert "event: execution_started\n" in content
        assert "event: supervisor_routing\n" in content
        assert "event: agent_started\n" in content
        assert "event: execution_completed\n" in content
    
    def test_stream_events_connection_management(self, client, mock_execution_state):
        """Test proper connection management and resource cleanup."""
        execution_id = "exec_test12345678"  # 17 characters total
        
        from src.hierarchical_agents.data_models import ExecutionEvent
        mock_event = ExecutionEvent(
            timestamp=datetime.now(),
            event_type="execution_started",
            source_type="system",
            execution_id=execution_id
        )
        
        with patch('src.hierarchical_agents.api.executions.event_manager') as mock_event_manager, \
             patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            
            mock_event_manager._subscribers = {}
            mock_event_manager.initialize = AsyncMock()
            mock_event_manager.get_buffered_events = AsyncMock(return_value=[])
            
            # Mock event stream that raises exception to test cleanup
            async def mock_event_stream_with_error():
                yield mock_event
                raise Exception("Connection lost")
            
            mock_event_manager.get_events_stream = AsyncMock(
                return_value=mock_event_stream_with_error()
            )
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            response = client.get(f"/api/v1/executions/{execution_id}/stream")
        
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        
        # Should contain error event
        assert "event: stream_error\n" in content
        assert '"event_type": "stream_error"' in content
    
    def test_stream_events_concurrent_connections(self, client, mock_execution_state):
        """Test handling multiple concurrent SSE connections."""
        execution_id = "exec_test12345678"  # 17 characters total
        
        from src.hierarchical_agents.data_models import ExecutionEvent
        mock_event = ExecutionEvent(
            timestamp=datetime.now(),
            event_type="execution_started",
            source_type="system",
            execution_id=execution_id
        )
        
        with patch('src.hierarchical_agents.api.executions.event_manager') as mock_event_manager, \
             patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            
            mock_event_manager._subscribers = {}
            mock_event_manager.initialize = AsyncMock()
            mock_event_manager.get_buffered_events = AsyncMock(return_value=[mock_event])
            
            async def mock_event_stream():
                yield mock_event
            
            mock_event_manager.get_events_stream = AsyncMock(return_value=mock_event_stream())
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            # Simulate multiple concurrent connections
            responses = []
            for _ in range(3):
                response = client.get(f"/api/v1/executions/{execution_id}/stream")
                responses.append(response)
            
            # All connections should succeed
            for response in responses:
                assert response.status_code == 200
                assert response.headers["content-type"] == "text/event-stream; charset=utf-8"


class TestSSEFormatting:
    """Test cases for SSE event formatting."""
    
    def test_format_sse_event_basic(self):
        """Test basic SSE event formatting."""
        from src.hierarchical_agents.data_models import ExecutionEvent
        from src.hierarchical_agents.api.executions import _format_sse_event
        
        event = ExecutionEvent(
            timestamp=datetime(2024, 1, 15, 10, 35, 0),
            event_type="execution_started",
            source_type="system",
            execution_id="exec_test123456",
            status="started"
        )
        
        sse_formatted = _format_sse_event(event)
        
        assert sse_formatted.startswith("event: execution_started\n")
        assert "data: {" in sse_formatted
        assert '"event_type": "execution_started"' in sse_formatted
        assert '"source_type": "system"' in sse_formatted
        assert '"execution_id": "exec_test123456"' in sse_formatted
        assert '"timestamp": "2024-01-15T10:35:00Z"' in sse_formatted
        assert sse_formatted.endswith("\n\n")
    
    def test_format_sse_event_with_optional_fields(self):
        """Test SSE formatting with optional fields."""
        from src.hierarchical_agents.data_models import ExecutionEvent
        from src.hierarchical_agents.api.executions import _format_sse_event
        
        event = ExecutionEvent(
            timestamp=datetime(2024, 1, 15, 10, 35, 0),
            event_type="supervisor_routing",
            source_type="supervisor",
            execution_id="exec_test123456",
            supervisor_id="supervisor_main",
            supervisor_name="顶级监督者",
            team_id="ht_123456789",
            action="routing",
            content="分析任务需求，选择研究团队开始执行",
            selected_team="team_a7b9c2d4e5f6"
        )
        
        sse_formatted = _format_sse_event(event)
        
        assert "event: supervisor_routing\n" in sse_formatted
        assert '"supervisor_name": "顶级监督者"' in sse_formatted
        assert '"selected_team": "team_a7b9c2d4e5f6"' in sse_formatted
        assert '"content": "分析任务需求，选择研究团队开始执行"' in sse_formatted
    
    def test_format_sse_event_excludes_none_values(self):
        """Test that SSE formatting excludes None values."""
        from src.hierarchical_agents.data_models import ExecutionEvent
        from src.hierarchical_agents.api.executions import _format_sse_event
        
        event = ExecutionEvent(
            timestamp=datetime(2024, 1, 15, 10, 35, 0),
            event_type="execution_started",
            source_type="system",
            execution_id="exec_test123456",
            # These fields are None and should be excluded
            team_id=None,
            supervisor_id=None,
            agent_id=None
        )
        
        sse_formatted = _format_sse_event(event)
        
        # Should not contain None fields
        assert '"team_id": null' not in sse_formatted
        assert '"supervisor_id": null' not in sse_formatted
        assert '"agent_id": null' not in sse_formatted
        
        # Should contain non-None fields
        assert '"event_type": "execution_started"' in sse_formatted
        assert '"source_type": "system"' in sse_formatted
    
    def test_format_sse_event_unicode_handling(self):
        """Test SSE formatting with Unicode characters."""
        from src.hierarchical_agents.data_models import ExecutionEvent
        from src.hierarchical_agents.api.executions import _format_sse_event
        
        event = ExecutionEvent(
            timestamp=datetime(2024, 1, 15, 10, 35, 0),
            event_type="agent_started",
            source_type="agent",
            execution_id="exec_test123456",
            agent_name="医疗文献搜索专家",
            content="开始搜索AI医疗应用相关信息"
        )
        
        sse_formatted = _format_sse_event(event)
        
        # Should properly handle Unicode characters
        assert '"agent_name": "医疗文献搜索专家"' in sse_formatted
        assert '"content": "开始搜索AI医疗应用相关信息"' in sse_formatted
        assert sse_formatted.endswith("\n\n")


class TestExecutionAPIPerformance:
    """Performance and edge case tests for execution API."""
    
    def test_concurrent_execution_requests(self, client, valid_execution_config):
        """Test handling of concurrent execution requests."""
        team_id = "ht_123456789"
        
        with patch('src.hierarchical_agents.api.executions.hierarchical_manager') as mock_manager, \
             patch('asyncio.create_task') as mock_create_task:
            
            mock_manager._initialized = False
            mock_manager.initialize = AsyncMock()
            mock_manager.build_hierarchy = Mock()
            mock_manager.build_hierarchy.return_value = Mock()
            
            # Simulate multiple concurrent requests
            responses = []
            for _ in range(3):
                response = client.post(
                    f"/api/v1/hierarchical-teams/{team_id}/execute",
                    json=valid_execution_config
                )
                responses.append(response)
            
            # All requests should succeed
            for response in responses:
                assert response.status_code == 202
                data = response.json()
                assert data["success"] is True
    
    def test_large_execution_list(self, client):
        """Test handling of large execution lists."""
        # Generate many execution IDs
        large_execution_list = [f"exec_{i:012d}" for i in range(1000)]
        
        with patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.list_executions = AsyncMock(return_value=large_execution_list)
            mock_state_manager.get_execution_state = AsyncMock(return_value=None)
            
            response = client.get("/api/v1/executions", params={"page_size": 50})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total_count"] == 1000
        # Should only return page_size items
        assert len(data["data"]["executions"]) <= 50


class TestGetExecutionResults:
    """Test cases for the get execution results endpoint."""
    
    def test_get_results_success(self, client, mock_execution_state):
        """Test successful execution results retrieval."""
        execution_id = "exec_test12345678"  # 17 characters total
        
        # Mock completed execution state
        mock_execution_state.status = ExecutionStatus.COMPLETED
        
        with patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager, \
             patch('src.hierarchical_agents.api.executions.output_formatter') as mock_formatter:
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            # Mock standardized output
            from src.hierarchical_agents.data_models import StandardizedOutput, ExecutionSummary, ExecutionMetrics
            mock_standardized_output = StandardizedOutput(
                execution_id=execution_id,
                execution_summary=ExecutionSummary(
                    status="completed",
                    started_at=datetime.now(),
                    completed_at=datetime.now(),
                    total_duration=1800,
                    teams_executed=2,
                    agents_involved=3
                ),
                team_results={},
                errors=[],
                metrics=ExecutionMetrics()
            )
            
            mock_formatter.state_manager = mock_state_manager
            mock_formatter.format_execution_results = AsyncMock(return_value=mock_standardized_output)
            
            response = client.get(f"/api/v1/executions/{execution_id}/results")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["code"] == "RESULTS_RETRIEVED"
        assert data["data"]["execution_id"] == execution_id
        assert data["data"]["execution_summary"]["status"] == "completed"
    
    def test_get_results_invalid_execution_id(self, client):
        """Test results retrieval with invalid execution ID format."""
        invalid_execution_id = "invalid_id"
        
        response = client.get(f"/api/v1/executions/{invalid_execution_id}/results")
        
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "EXECUTION_NOT_FOUND"
    
    def test_get_results_execution_not_found(self, client):
        """Test results retrieval for non-existent execution."""
        execution_id = "exec_notfound1234"  # 17 characters total
        
        with patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=None)
            
            response = client.get(f"/api/v1/executions/{execution_id}/results")
        
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "EXECUTION_NOT_FOUND"
    
    def test_get_results_execution_not_completed(self, client, mock_execution_state):
        """Test results retrieval for running execution."""
        execution_id = "exec_test12345678"  # 17 characters total
        
        # Mock running execution state
        mock_execution_state.status = ExecutionStatus.RUNNING
        
        with patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            response = client.get(f"/api/v1/executions/{execution_id}/results")
        
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "EXECUTION_NOT_COMPLETED"
    
    def test_get_results_formatting_error(self, client, mock_execution_state):
        """Test results retrieval when formatting fails."""
        execution_id = "exec_test12345678"  # 17 characters total
        
        # Mock completed execution state
        mock_execution_state.status = ExecutionStatus.COMPLETED
        
        with patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager, \
             patch('src.hierarchical_agents.api.executions.output_formatter') as mock_formatter:
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            from src.hierarchical_agents.output_formatter import OutputFormatterError
            mock_formatter.state_manager = mock_state_manager
            mock_formatter.format_execution_results = AsyncMock(
                side_effect=OutputFormatterError("Formatting failed")
            )
            
            response = client.get(f"/api/v1/executions/{execution_id}/results")
        
        assert response.status_code == 500
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "FORMATTING_ERROR"
    
    def test_get_results_with_format_parameter(self, client, mock_execution_state):
        """Test results retrieval with format parameter."""
        execution_id = "exec_test12345678"  # 17 characters total
        
        # Mock completed execution state
        mock_execution_state.status = ExecutionStatus.COMPLETED
        
        with patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager, \
             patch('src.hierarchical_agents.api.executions.output_formatter') as mock_formatter:
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            from src.hierarchical_agents.data_models import StandardizedOutput, ExecutionSummary, ExecutionMetrics
            mock_standardized_output = StandardizedOutput(
                execution_id=execution_id,
                execution_summary=ExecutionSummary(
                    status="completed",
                    started_at=datetime.now(),
                    completed_at=datetime.now(),
                    total_duration=1800,
                    teams_executed=2,
                    agents_involved=3
                ),
                team_results={},
                errors=[],
                metrics=ExecutionMetrics()
            )
            
            mock_formatter.state_manager = mock_state_manager
            mock_formatter.format_execution_results = AsyncMock(return_value=mock_standardized_output)
            
            # Test with valid format
            response = client.get(f"/api/v1/executions/{execution_id}/results?format=json")
            assert response.status_code == 200
            
            # Test with invalid format
            response = client.get(f"/api/v1/executions/{execution_id}/results?format=invalid")
            assert response.status_code == 400
            data = response.json()
            assert data["code"] == "INVALID_FORMAT"


class TestFormatExecutionResults:
    """Test cases for the format execution results endpoint."""
    
    def test_format_results_success(self, client, mock_execution_state):
        """Test successful execution results formatting."""
        execution_id = "exec_test12345678"  # 17 characters total
        
        format_request = {
            "output_template": {
                "report_title": "Test Report",
                "summary": "{executive_summary}",
                "findings": {
                    "technologies": "{key_technologies}",
                    "trends": "{market_trends}"
                }
            },
            "extraction_rules": {
                "executive_summary": "总结所有团队的核心发现，不超过200字",
                "key_technologies": "从搜索结果中提取3-5个关键技术",
                "market_trends": "从分析结果中提取市场趋势"
            }
        }
        
        # Mock completed execution state
        mock_execution_state.status = ExecutionStatus.COMPLETED
        
        with patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager, \
             patch('src.hierarchical_agents.api.executions.output_formatter') as mock_formatter:
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            # Mock formatted output
            mock_formatted_output = {
                "report_title": "Test Report",
                "summary": "This is a test summary",
                "findings": {
                    "technologies": ["AI", "ML", "NLP"],
                    "trends": ["Growth in AI market", "Increased adoption"]
                }
            }
            
            mock_formatter.state_manager = mock_state_manager
            mock_formatter.parse_template = Mock(return_value=format_request["output_template"])
            mock_formatter.validate_extraction_rules = Mock(return_value=format_request["extraction_rules"])
            mock_formatter.format_execution_with_template = AsyncMock(return_value=mock_formatted_output)
            
            response = client.post(
                f"/api/v1/executions/{execution_id}/results/format",
                json=format_request
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["code"] == "FORMATTED_RESULTS_GENERATED"
        assert data["data"]["report_title"] == "Test Report"
        assert data["data"]["summary"] == "This is a test summary"
    
    def test_format_results_invalid_execution_id(self, client):
        """Test formatting with invalid execution ID format."""
        invalid_execution_id = "invalid_id"
        
        format_request = {
            "output_template": {"title": "Test"},
            "extraction_rules": {"title": "Extract title"}
        }
        
        response = client.post(
            f"/api/v1/executions/{invalid_execution_id}/results/format",
            json=format_request
        )
        
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "EXECUTION_NOT_FOUND"
    
    def test_format_results_missing_template(self, client):
        """Test formatting with missing template."""
        execution_id = "exec_test12345678"  # 17 characters total
        
        invalid_request = {
            "extraction_rules": {"title": "Extract title"}
            # Missing output_template
        }
        
        response = client.post(
            f"/api/v1/executions/{execution_id}/results/format",
            json=invalid_request
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "MISSING_TEMPLATE"
    
    def test_format_results_missing_rules(self, client):
        """Test formatting with missing extraction rules."""
        execution_id = "exec_test12345678"  # 17 characters total
        
        invalid_request = {
            "output_template": {"title": "Test"}
            # Missing extraction_rules
        }
        
        response = client.post(
            f"/api/v1/executions/{execution_id}/results/format",
            json=invalid_request
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "MISSING_RULES"
    
    def test_format_results_invalid_request_body(self, client):
        """Test formatting with invalid request body."""
        execution_id = "exec_test12345678"  # 17 characters total
        
        # Send string instead of JSON object
        response = client.post(
            f"/api/v1/executions/{execution_id}/results/format",
            json="invalid_request"
        )
        
        # FastAPI returns 422 for validation errors
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
    
    def test_format_results_execution_not_found(self, client):
        """Test formatting for non-existent execution."""
        execution_id = "exec_notfound1234"  # 17 characters total
        
        format_request = {
            "output_template": {"title": "Test"},
            "extraction_rules": {"title": "Extract title"}
        }
        
        with patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=None)
            
            response = client.post(
                f"/api/v1/executions/{execution_id}/results/format",
                json=format_request
            )
        
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "EXECUTION_NOT_FOUND"
    
    def test_format_results_execution_not_completed(self, client, mock_execution_state):
        """Test formatting for running execution."""
        execution_id = "exec_test12345678"  # 17 characters total
        
        format_request = {
            "output_template": {"title": "Test"},
            "extraction_rules": {"title": "Extract title"}
        }
        
        # Mock running execution state
        mock_execution_state.status = ExecutionStatus.RUNNING
        
        with patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager:
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            response = client.post(
                f"/api/v1/executions/{execution_id}/results/format",
                json=format_request
            )
        
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "EXECUTION_NOT_COMPLETED"
    
    def test_format_results_invalid_template(self, client, mock_execution_state):
        """Test formatting with invalid template."""
        execution_id = "exec_test12345678"  # 17 characters total
        
        format_request = {
            "output_template": {"title": "Test"},
            "extraction_rules": {"title": "Extract title"}
        }
        
        # Mock completed execution state
        mock_execution_state.status = ExecutionStatus.COMPLETED
        
        with patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager, \
             patch('src.hierarchical_agents.api.executions.output_formatter') as mock_formatter:
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            from src.hierarchical_agents.output_formatter import OutputFormatterError
            mock_formatter.state_manager = mock_state_manager
            mock_formatter.parse_template = Mock(
                side_effect=OutputFormatterError("Template parsing failed: Template must be a dictionary")
            )
            
            response = client.post(
                f"/api/v1/executions/{execution_id}/results/format",
                json=format_request
            )
        
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "INVALID_TEMPLATE"
    
    def test_format_results_invalid_rules(self, client, mock_execution_state):
        """Test formatting with invalid extraction rules."""
        execution_id = "exec_test12345678"  # 17 characters total
        
        format_request = {
            "output_template": {"title": "Test"},
            "extraction_rules": {"title": "Extract title"}
        }
        
        # Mock completed execution state
        mock_execution_state.status = ExecutionStatus.COMPLETED
        
        with patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager, \
             patch('src.hierarchical_agents.api.executions.output_formatter') as mock_formatter:
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            from src.hierarchical_agents.output_formatter import OutputFormatterError
            mock_formatter.state_manager = mock_state_manager
            mock_formatter.parse_template = Mock(return_value=format_request["output_template"])
            mock_formatter.validate_extraction_rules = Mock(
                side_effect=OutputFormatterError("Rule validation failed: Invalid rule format")
            )
            
            response = client.post(
                f"/api/v1/executions/{execution_id}/results/format",
                json=format_request
            )
        
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "INVALID_RULES"
    
    def test_format_results_extraction_error(self, client, mock_execution_state):
        """Test formatting when information extraction fails."""
        execution_id = "exec_test12345678"  # 17 characters total
        
        format_request = {
            "output_template": {"title": "Test"},
            "extraction_rules": {"title": "Extract title"}
        }
        
        # Mock completed execution state
        mock_execution_state.status = ExecutionStatus.COMPLETED
        
        with patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager, \
             patch('src.hierarchical_agents.api.executions.output_formatter') as mock_formatter:
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            from src.hierarchical_agents.output_formatter import OutputFormatterError
            mock_formatter.state_manager = mock_state_manager
            mock_formatter.parse_template = Mock(return_value=format_request["output_template"])
            mock_formatter.validate_extraction_rules = Mock(return_value=format_request["extraction_rules"])
            mock_formatter.format_execution_with_template = AsyncMock(
                side_effect=OutputFormatterError("Information extraction failed")
            )
            
            response = client.post(
                f"/api/v1/executions/{execution_id}/results/format",
                json=format_request
            )
        
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["code"] == "EXTRACTION_ERROR"
    
    def test_format_results_complex_template(self, client, mock_execution_state):
        """Test formatting with complex nested template."""
        execution_id = "exec_test12345678"  # 17 characters total
        
        complex_format_request = {
            "output_template": {
                "report_title": "AI医疗应用分析报告",
                "executive_summary": "{executive_summary}",
                "research_findings": {
                    "key_technologies": "{key_technologies}",
                    "market_trends": "{market_trends}",
                    "challenges": "{challenges}"
                },
                "recommendations": "{recommendations}",
                "appendix": {
                    "data_sources": "{data_sources}",
                    "methodology": "{methodology}"
                }
            },
            "extraction_rules": {
                "executive_summary": "总结所有团队的核心发现，不超过200字",
                "key_technologies": "从搜索结果中提取3-5个关键技术",
                "market_trends": "从分析结果中提取市场趋势，以列表形式呈现",
                "challenges": "识别并列出主要技术和商业挑战",
                "recommendations": "基于分析结果提供3-5条具体建议",
                "data_sources": "列出所有数据来源",
                "methodology": "描述研究方法"
            }
        }
        
        # Mock completed execution state
        mock_execution_state.status = ExecutionStatus.COMPLETED
        
        with patch('src.hierarchical_agents.api.executions.state_manager') as mock_state_manager, \
             patch('src.hierarchical_agents.api.executions.output_formatter') as mock_formatter:
            
            mock_state_manager._redis = Mock()
            mock_state_manager.initialize = AsyncMock()
            mock_state_manager.get_execution_state = AsyncMock(return_value=mock_execution_state)
            
            # Mock complex formatted output
            mock_formatted_output = {
                "report_title": "AI医疗应用分析报告",
                "executive_summary": "本报告全面分析了人工智能在医疗领域的当前应用状况...",
                "research_findings": {
                    "key_technologies": ["深度学习医学影像诊断", "自然语言处理病历分析"],
                    "market_trends": ["AI医疗市场预计2030年达到1000亿美元"],
                    "challenges": ["数据隐私保护", "算法可解释性"]
                },
                "recommendations": ["建立统一的医疗AI数据标准", "加强跨学科人才培养"],
                "appendix": {
                    "data_sources": ["PubMed医学文献数据库", "IEEE Xplore技术论文"],
                    "methodology": "采用系统性文献综述方法"
                }
            }
            
            mock_formatter.state_manager = mock_state_manager
            mock_formatter.parse_template = Mock(return_value=complex_format_request["output_template"])
            mock_formatter.validate_extraction_rules = Mock(return_value=complex_format_request["extraction_rules"])
            mock_formatter.format_execution_with_template = AsyncMock(return_value=mock_formatted_output)
            
            response = client.post(
                f"/api/v1/executions/{execution_id}/results/format",
                json=complex_format_request
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["code"] == "FORMATTED_RESULTS_GENERATED"
        assert data["data"]["report_title"] == "AI医疗应用分析报告"
        assert "research_findings" in data["data"]
        assert "key_technologies" in data["data"]["research_findings"]
        assert "appendix" in data["data"]