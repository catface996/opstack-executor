"""
Tests for hierarchical manager.

This module tests the HierarchicalManager class and its integration
with team building, execution engine, and output formatting components.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List

from src.hierarchical_agents.hierarchical_manager import (
    HierarchicalManager,
    HierarchicalManagerError,
    OutputFormatter,
    create_hierarchical_manager,
    build_team_from_config
)
from src.hierarchical_agents.data_models import (
    HierarchicalTeam,
    SubTeam,
    SupervisorConfig,
    AgentConfig,
    LLMConfig,
    GlobalConfig,
    ExecutionConfig,
    ExecutionContext,
    ExecutionEvent,
    TeamResult,
    StandardizedOutput,
    ExecutionSummary,
    ExecutionMetrics
)
from src.hierarchical_agents.team_builder import TeamBuildError
from src.hierarchical_agents.execution_engine import ExecutionSession


class TestOutputFormatter:
    """Test the placeholder OutputFormatter class."""
    
    def test_format_results_basic(self):
        """Test basic result formatting."""
        formatter = OutputFormatter()
        
        # Create test results
        results = [
            TeamResult(
                status="completed",
                duration=100,
                agents={"agent1": {"status": "completed"}},
                output="Test output 1"
            ),
            TeamResult(
                status="completed", 
                duration=200,
                agents={"agent2": {"status": "completed"}},
                output="Test output 2"
            )
        ]
        
        # Format results
        output = formatter.format_results(results)
        
        # Verify output structure
        assert isinstance(output, StandardizedOutput)
        assert output.execution_id.startswith("exec_")
        assert output.execution_summary.teams_executed == 2
        assert len(output.team_results) == 2
        assert output.errors == []
        assert isinstance(output.metrics, ExecutionMetrics)
    
    def test_format_results_empty(self):
        """Test formatting empty results."""
        formatter = OutputFormatter()
        
        output = formatter.format_results([])
        
        assert isinstance(output, StandardizedOutput)
        assert output.execution_summary.teams_executed == 0
        assert len(output.team_results) == 0


class TestHierarchicalManager:
    """Test the HierarchicalManager class."""
    
    @pytest.fixture
    def sample_team_config(self) -> Dict[str, Any]:
        """Create a sample team configuration."""
        return {
            "team_name": "test_team",
            "description": "Test hierarchical team",
            "top_supervisor_config": {
                "llm_config": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "temperature": 0.3
                },
                "system_prompt": "You are a top supervisor",
                "user_prompt": "Coordinate the team execution",
                "max_iterations": 10
            },
            "sub_teams": [
                {
                    "id": "team1",
                    "name": "Research Team",
                    "description": "Research team",
                    "supervisor_config": {
                        "llm_config": {
                            "provider": "openai",
                            "model": "gpt-4o",
                            "temperature": 0.3
                        },
                        "system_prompt": "You are a research supervisor",
                        "user_prompt": "Coordinate research tasks",
                        "max_iterations": 8
                    },
                    "agent_configs": [
                        {
                            "agent_id": "agent1",
                            "agent_name": "Researcher",
                            "llm_config": {
                                "provider": "openai",
                                "model": "gpt-4o",
                                "temperature": 0.3
                            },
                            "system_prompt": "You are a researcher",
                            "user_prompt": "Conduct research",
                            "tools": ["search"],
                            "max_iterations": 5
                        }
                    ]
                }
            ],
            "dependencies": {},
            "global_config": {
                "max_execution_time": 3600,
                "enable_streaming": True,
                "output_format": "detailed"
            }
        }
    
    @pytest.fixture
    def manager(self):
        """Create a HierarchicalManager instance."""
        return HierarchicalManager()
    
    def test_manager_initialization(self, manager):
        """Test manager initialization."""
        assert manager.key_manager is not None
        assert manager.error_handler is not None
        assert manager.state_manager is not None
        assert manager.event_manager is not None
        assert manager.team_builder is not None
        assert manager.execution_engine is not None
        assert manager.output_formatter is not None
        assert not manager._initialized
    
    @pytest.mark.asyncio
    async def test_initialize_and_shutdown(self, manager):
        """Test manager initialization and shutdown."""
        # Mock the execution engine initialization
        manager.execution_engine.initialize = AsyncMock()
        manager.execution_engine.shutdown = AsyncMock()
        
        # Test initialization
        await manager.initialize()
        assert manager._initialized
        manager.execution_engine.initialize.assert_called_once()
        
        # Test shutdown
        await manager.shutdown()
        assert not manager._initialized
        manager.execution_engine.shutdown.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialize_failure(self, manager):
        """Test manager initialization failure."""
        # Mock initialization failure
        manager.execution_engine.initialize = AsyncMock(side_effect=Exception("Init failed"))
        
        with pytest.raises(HierarchicalManagerError, match="Failed to initialize"):
            await manager.initialize()
        
        assert not manager._initialized
    
    def test_build_hierarchy_success(self, manager, sample_team_config):
        """Test successful hierarchy building."""
        # Mock team builder
        mock_team = Mock(spec=HierarchicalTeam)
        mock_team.team_name = "test_team"
        mock_team.sub_teams = [Mock()]
        
        manager.team_builder.validate_team_configuration = Mock(return_value=(True, []))
        manager.team_builder.build_hierarchical_team = Mock(return_value=mock_team)
        
        # Build hierarchy
        result = manager.build_hierarchy(sample_team_config)
        
        # Verify calls
        manager.team_builder.validate_team_configuration.assert_called_once()
        manager.team_builder.build_hierarchical_team.assert_called_once()
        assert result == mock_team
    
    def test_build_hierarchy_invalid_config(self, manager, sample_team_config):
        """Test hierarchy building with invalid configuration."""
        # Mock validation failure
        manager.team_builder.validate_team_configuration = Mock(
            return_value=(False, ["Invalid config"])
        )
        
        with pytest.raises(HierarchicalManagerError, match="Invalid team configuration"):
            manager.build_hierarchy(sample_team_config)
    
    def test_build_hierarchy_build_failure(self, manager, sample_team_config):
        """Test hierarchy building failure."""
        # Mock validation success but build failure
        manager.team_builder.validate_team_configuration = Mock(return_value=(True, []))
        manager.team_builder.build_hierarchical_team = Mock(
            side_effect=TeamBuildError("Build failed")
        )
        
        with pytest.raises(HierarchicalManagerError, match="Team building failed"):
            manager.build_hierarchy(sample_team_config)
    
    @pytest.mark.asyncio
    async def test_execute_team_success(self, manager):
        """Test successful team execution."""
        # Setup
        manager._initialized = True
        mock_team = Mock(spec=HierarchicalTeam)
        mock_team.team_name = "test_team"
        
        mock_session = Mock(spec=ExecutionSession)
        mock_session.execution_id = "exec_123"
        
        # Mock execution engine
        manager.execution_engine.start_execution = AsyncMock(return_value=mock_session)
        
        # Mock event stream - return the async generator directly
        async def mock_stream():
            yield ExecutionEvent(
                timestamp=datetime.now(),
                event_type="test_event",
                source_type="system",
                execution_id="exec_123"
            )
        
        manager.execution_engine.stream_events = Mock(return_value=mock_stream())
        
        # Execute team
        events = []
        async for event in manager.execute_team(mock_team):
            events.append(event)
        
        # Verify
        assert len(events) == 1
        assert events[0].execution_id == "exec_123"
        manager.execution_engine.start_execution.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_team_not_initialized(self, manager):
        """Test team execution when manager not initialized."""
        mock_team = Mock(spec=HierarchicalTeam)
        mock_team.team_name = "test_team"
        
        with pytest.raises(HierarchicalManagerError, match="not initialized"):
            async for _ in manager.execute_team(mock_team):
                pass
    
    @pytest.mark.asyncio
    async def test_execute_team_failure(self, manager):
        """Test team execution failure."""
        # Setup
        manager._initialized = True
        mock_team = Mock(spec=HierarchicalTeam)
        mock_team.team_name = "test_team"
        
        # Mock execution failure
        manager.execution_engine.start_execution = AsyncMock(
            side_effect=Exception("Execution failed")
        )
        
        with pytest.raises(HierarchicalManagerError, match="Failed to execute team"):
            async for _ in manager.execute_team(mock_team):
                pass
    
    def test_format_results_success(self, manager):
        """Test successful result formatting."""
        # Create test results
        results = [
            TeamResult(status="completed", duration=100),
            TeamResult(status="completed", duration=200)
        ]
        
        # Format results
        output = manager.format_results(results)
        
        # Verify
        assert isinstance(output, StandardizedOutput)
        assert output.execution_summary.teams_executed == 2
    
    def test_format_results_failure(self, manager):
        """Test result formatting failure."""
        # Mock formatter failure
        manager.output_formatter.format_results = Mock(
            side_effect=Exception("Format failed")
        )
        
        with pytest.raises(HierarchicalManagerError, match="Failed to format results"):
            manager.format_results([])
    
    @pytest.mark.asyncio
    async def test_create_and_execute_team(self, manager, sample_team_config):
        """Test create and execute team convenience method."""
        # Setup
        manager._initialized = True
        
        # Mock build_hierarchy
        mock_team = Mock(spec=HierarchicalTeam)
        mock_team.team_name = "test_team"
        manager.build_hierarchy = Mock(return_value=mock_team)
        
        # Mock execute_team - return the async generator directly
        async def mock_execute(team, context=None):
            yield ExecutionEvent(
                timestamp=datetime.now(),
                event_type="test_event",
                source_type="system",
                execution_id="exec_123"
            )
        
        manager.execute_team = Mock(side_effect=mock_execute)
        
        # Execute
        events = []
        async for event in manager.create_and_execute_team(sample_team_config):
            events.append(event)
        
        # Verify
        assert len(events) == 1
        manager.build_hierarchy.assert_called_once_with(sample_team_config)
        manager.execute_team.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_execution_status(self, manager):
        """Test getting execution status."""
        from src.hierarchical_agents.data_models import ExecutionStatus
        
        # Mock execution engine
        manager.execution_engine.get_execution_status = AsyncMock(
            return_value=ExecutionStatus.RUNNING
        )
        
        status = await manager.get_execution_status("exec_123")
        
        assert status == "running"
        manager.execution_engine.get_execution_status.assert_called_once_with("exec_123")
    
    @pytest.mark.asyncio
    async def test_get_execution_status_not_found(self, manager):
        """Test getting execution status when not found."""
        # Mock execution engine returning None
        manager.execution_engine.get_execution_status = AsyncMock(return_value=None)
        
        status = await manager.get_execution_status("exec_123")
        
        assert status is None
    
    @pytest.mark.asyncio
    async def test_stop_execution(self, manager):
        """Test stopping execution."""
        # Mock execution engine
        manager.execution_engine.stop_execution = AsyncMock(return_value=True)
        
        result = await manager.stop_execution("exec_123")
        
        assert result is True
        manager.execution_engine.stop_execution.assert_called_once_with("exec_123", True)
    
    def test_get_team_statistics(self, manager):
        """Test getting team statistics."""
        mock_team = Mock(spec=HierarchicalTeam)
        mock_stats = {"team_name": "test", "agents": 5}
        
        manager.team_builder.get_team_statistics = Mock(return_value=mock_stats)
        
        stats = manager.get_team_statistics(mock_team)
        
        assert stats == mock_stats
        manager.team_builder.get_team_statistics.assert_called_once_with(mock_team)
    
    def test_validate_team_config(self, manager, sample_team_config):
        """Test team configuration validation."""
        # Mock team builder validation
        manager.team_builder.validate_team_configuration = Mock(
            return_value=(True, [])
        )
        
        is_valid, errors = manager.validate_team_config(sample_team_config)
        
        assert is_valid is True
        assert errors == []
        manager.team_builder.validate_team_configuration.assert_called_once()
    
    def test_validate_team_config_invalid(self, manager):
        """Test validation of invalid team configuration."""
        # Test with invalid config that will cause model validation to fail
        invalid_config = {"invalid": "config"}
        
        is_valid, errors = manager.validate_team_config(invalid_config)
        
        assert is_valid is False
        assert len(errors) > 0
        assert "Configuration validation error" in errors[0]
    
    @pytest.mark.asyncio
    async def test_list_active_executions(self, manager):
        """Test listing active executions."""
        # Mock execution engine
        manager.execution_engine.list_active_executions = AsyncMock(
            return_value=["exec_1", "exec_2"]
        )
        
        executions = await manager.list_active_executions()
        
        assert executions == ["exec_1", "exec_2"]
        manager.execution_engine.list_active_executions.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_manager_stats(self, manager):
        """Test getting manager statistics."""
        # Mock execution engine stats
        engine_stats = {"initialized": True, "sessions": 2}
        manager.execution_engine.get_stats = AsyncMock(return_value=engine_stats)
        
        stats = await manager.get_manager_stats()
        
        assert "initialized" in stats
        assert "components" in stats
        assert "timestamp" in stats
        assert stats["components"]["execution_engine"] == engine_stats


class TestUtilityFunctions:
    """Test utility functions."""
    
    @pytest.mark.asyncio
    async def test_create_hierarchical_manager(self):
        """Test creating hierarchical manager."""
        with patch('src.hierarchical_agents.hierarchical_manager.HierarchicalManager') as MockManager:
            mock_instance = Mock()
            mock_instance.initialize = AsyncMock()
            MockManager.return_value = mock_instance
            
            manager = await create_hierarchical_manager()
            
            MockManager.assert_called_once()
            mock_instance.initialize.assert_called_once()
            assert manager == mock_instance
    
    def test_build_team_from_config(self):
        """Test building team from config utility function."""
        config = {"team_name": "test"}
        
        with patch('src.hierarchical_agents.hierarchical_manager.HierarchicalManager') as MockManager:
            mock_instance = Mock()
            mock_team = Mock()
            mock_instance.build_hierarchy.return_value = mock_team
            MockManager.return_value = mock_instance
            
            result = build_team_from_config(config)
            
            MockManager.assert_called_once()
            mock_instance.build_hierarchy.assert_called_once_with(config)
            assert result == mock_team


class TestIntegration:
    """Integration tests for HierarchicalManager."""
    
    @pytest.fixture
    def complete_team_config(self) -> Dict[str, Any]:
        """Create a complete team configuration for integration testing."""
        return {
            "team_name": "integration_test_team",
            "description": "Integration test hierarchical team",
            "top_supervisor_config": {
                "llm_config": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "temperature": 0.3,
                    "max_tokens": 1000
                },
                "system_prompt": "You are a top-level supervisor coordinating multiple teams.",
                "user_prompt": "Coordinate the execution of all sub-teams based on their capabilities.",
                "max_iterations": 10
            },
            "sub_teams": [
                {
                    "id": "research_team",
                    "name": "Research Team",
                    "description": "Team responsible for research and data collection",
                    "supervisor_config": {
                        "llm_config": {
                            "provider": "openai",
                            "model": "gpt-4o",
                            "temperature": 0.3
                        },
                        "system_prompt": "You are a research team supervisor.",
                        "user_prompt": "Coordinate research activities.",
                        "max_iterations": 8
                    },
                    "agent_configs": [
                        {
                            "agent_id": "researcher_1",
                            "agent_name": "Senior Researcher",
                            "llm_config": {
                                "provider": "openai",
                                "model": "gpt-4o",
                                "temperature": 0.3
                            },
                            "system_prompt": "You are a senior researcher.",
                            "user_prompt": "Conduct comprehensive research.",
                            "tools": ["search", "analysis"],
                            "max_iterations": 5
                        },
                        {
                            "agent_id": "data_analyst",
                            "agent_name": "Data Analyst",
                            "llm_config": {
                                "provider": "openai",
                                "model": "gpt-4o",
                                "temperature": 0.2
                            },
                            "system_prompt": "You are a data analyst.",
                            "user_prompt": "Analyze collected data.",
                            "tools": ["analysis", "visualization"],
                            "max_iterations": 3
                        }
                    ]
                },
                {
                    "id": "writing_team",
                    "name": "Writing Team", 
                    "description": "Team responsible for documentation and reporting",
                    "supervisor_config": {
                        "llm_config": {
                            "provider": "openai",
                            "model": "gpt-4o",
                            "temperature": 0.5
                        },
                        "system_prompt": "You are a writing team supervisor.",
                        "user_prompt": "Coordinate writing and documentation tasks.",
                        "max_iterations": 6
                    },
                    "agent_configs": [
                        {
                            "agent_id": "technical_writer",
                            "agent_name": "Technical Writer",
                            "llm_config": {
                                "provider": "openai",
                                "model": "gpt-4o",
                                "temperature": 0.7
                            },
                            "system_prompt": "You are a technical writer.",
                            "user_prompt": "Create comprehensive technical documentation.",
                            "tools": ["document_writer", "editor"],
                            "max_iterations": 5
                        }
                    ]
                }
            ],
            "dependencies": {
                "writing_team": ["research_team"]
            },
            "global_config": {
                "max_execution_time": 3600,
                "enable_streaming": True,
                "output_format": "detailed"
            }
        }
    
    def test_build_hierarchy_integration(self, complete_team_config):
        """Test building hierarchy with complete configuration."""
        manager = HierarchicalManager()
        
        # This should work with the actual implementation
        # but will fail due to missing dependencies in test environment
        # We'll mock the team builder for this test
        
        mock_team = Mock(spec=HierarchicalTeam)
        mock_team.team_name = "integration_test_team"
        mock_team.sub_teams = [Mock(), Mock()]
        
        manager.team_builder.validate_team_configuration = Mock(return_value=(True, []))
        manager.team_builder.build_hierarchical_team = Mock(return_value=mock_team)
        
        result = manager.build_hierarchy(complete_team_config)
        
        assert result.team_name == "integration_test_team"
        assert len(result.sub_teams) == 2
    
    def test_validate_complete_config(self, complete_team_config):
        """Test validation of complete configuration."""
        manager = HierarchicalManager()
        
        # Mock the validation to avoid dependency issues
        manager.team_builder.validate_team_configuration = Mock(return_value=(True, []))
        
        is_valid, errors = manager.validate_team_config(complete_team_config)
        
        assert is_valid is True
        assert errors == []
    
    def test_manager_component_integration(self):
        """Test that all manager components are properly integrated."""
        manager = HierarchicalManager()
        
        # Verify all components are initialized
        assert manager.key_manager is not None
        assert manager.error_handler is not None
        assert manager.state_manager is not None
        assert manager.event_manager is not None
        assert manager.team_builder is not None
        assert manager.execution_engine is not None
        assert manager.output_formatter is not None
        
        # Verify components are properly connected
        assert manager.team_builder.agent_factory.key_manager == manager.key_manager
        assert manager.team_builder.agent_factory.error_handler == manager.error_handler
        assert manager.execution_engine.state_manager == manager.state_manager
        assert manager.execution_engine.event_manager == manager.event_manager
        assert manager.execution_engine.error_handler == manager.error_handler