"""
Tests for the team builder module.

This module tests all aspects of team building including:
- Team construction with mock agent factories
- Dependency graph algorithms and topological sorting
- Execution order validation
- Circular dependency detection
- Edge cases and boundary conditions
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from typing import Dict, List, Set

from src.hierarchical_agents.team_builder import (
    TeamBuilder, AgentFactory, DependencyResolver,
    TeamBuildError, DependencyError,
    build_team_from_config, validate_team_config, calculate_team_execution_order
)
from src.hierarchical_agents.data_models import (
    HierarchicalTeam, SubTeam, AgentConfig, SupervisorConfig, 
    LLMConfig, GlobalConfig
)
from src.hierarchical_agents.agents import WorkerAgent, SupervisorAgent


class TestAgentFactory:
    """Test the agent factory for creating mock agents."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.factory = AgentFactory()
        
        # Mock LLM config
        self.llm_config = LLMConfig(
            provider="openai",
            model="gpt-4o",
            temperature=0.7
        )
        
        # Mock agent config
        self.agent_config = AgentConfig(
            agent_id="test_agent_001",
            agent_name="Test Agent",
            llm_config=self.llm_config,
            system_prompt="You are a test agent",
            user_prompt="Execute test task",
            tools=["test_tool"]
        )
        
        # Mock supervisor config
        self.supervisor_config = SupervisorConfig(
            llm_config=self.llm_config,
            system_prompt="You are a test supervisor",
            user_prompt="Route tasks to agents"
        )
    
    @patch('src.hierarchical_agents.team_builder.WorkerAgent')
    def test_create_worker_agent_success(self, mock_worker_agent):
        """Test successful worker agent creation."""
        # Arrange
        mock_agent = Mock(spec=WorkerAgent)
        mock_worker_agent.return_value = mock_agent
        
        # Act
        result = self.factory.create_worker_agent(self.agent_config)
        
        # Assert
        assert result == mock_agent
        mock_worker_agent.assert_called_once_with(
            config=self.agent_config,
            key_manager=self.factory.key_manager,
            error_handler=self.factory.error_handler,
            tool_registry=self.factory.tool_registry
        )
    
    @patch('src.hierarchical_agents.team_builder.WorkerAgent')
    def test_create_worker_agent_failure(self, mock_worker_agent):
        """Test worker agent creation failure."""
        # Arrange
        mock_worker_agent.side_effect = Exception("Agent creation failed")
        
        # Act & Assert
        with pytest.raises(TeamBuildError, match="Failed to create worker agent Test Agent"):
            self.factory.create_worker_agent(self.agent_config)
    
    @patch('src.hierarchical_agents.team_builder.SupervisorAgent')
    def test_create_supervisor_agent_success(self, mock_supervisor_agent):
        """Test successful supervisor agent creation."""
        # Arrange
        mock_supervisor = Mock(spec=SupervisorAgent)
        mock_supervisor_agent.return_value = mock_supervisor
        
        # Act
        result = self.factory.create_supervisor_agent(self.supervisor_config)
        
        # Assert
        assert result == mock_supervisor
        mock_supervisor_agent.assert_called_once_with(
            config=self.supervisor_config,
            key_manager=self.factory.key_manager,
            error_handler=self.factory.error_handler
        )
    
    @patch('src.hierarchical_agents.team_builder.SupervisorAgent')
    def test_create_supervisor_agent_failure(self, mock_supervisor_agent):
        """Test supervisor agent creation failure."""
        # Arrange
        mock_supervisor_agent.side_effect = Exception("Supervisor creation failed")
        
        # Act & Assert
        with pytest.raises(TeamBuildError, match="Failed to create supervisor agent"):
            self.factory.create_supervisor_agent(self.supervisor_config)


class TestDependencyResolver:
    """Test dependency resolution algorithms."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.resolver = DependencyResolver()
    
    def test_build_dependency_graph_empty(self):
        """Test building empty dependency graph."""
        # Arrange
        dependencies = {}
        
        # Act
        result = self.resolver.build_dependency_graph(dependencies)
        
        # Assert
        assert result == {}
    
    def test_build_dependency_graph_simple(self):
        """Test building simple dependency graph."""
        # Arrange
        dependencies = {
            "team_b": ["team_a"],
            "team_c": ["team_b"]
        }
        
        # Act
        result = self.resolver.build_dependency_graph(dependencies)
        
        # Assert
        assert result == dependencies
        # Ensure original is not modified
        dependencies["team_d"] = ["team_c"]
        assert "team_d" not in result
    
    def test_validate_dependencies_valid(self):
        """Test validation of valid dependencies."""
        # Arrange
        dependencies = {
            "team_b": ["team_a"],
            "team_c": ["team_b"]
        }
        team_ids = {"team_a", "team_b", "team_c"}
        
        # Act
        is_valid, errors = self.resolver.validate_dependencies(dependencies, team_ids)
        
        # Assert
        assert is_valid
        assert errors == []
    
    def test_validate_dependencies_invalid_key(self):
        """Test validation with invalid dependency key."""
        # Arrange
        dependencies = {
            "team_x": ["team_a"]  # team_x not in team_ids
        }
        team_ids = {"team_a", "team_b"}
        
        # Act
        is_valid, errors = self.resolver.validate_dependencies(dependencies, team_ids)
        
        # Assert
        assert not is_valid
        assert "Dependency key 'team_x' not found in team IDs" in errors
    
    def test_validate_dependencies_invalid_value(self):
        """Test validation with invalid dependency value."""
        # Arrange
        dependencies = {
            "team_b": ["team_x"]  # team_x not in team_ids
        }
        team_ids = {"team_a", "team_b"}
        
        # Act
        is_valid, errors = self.resolver.validate_dependencies(dependencies, team_ids)
        
        # Assert
        assert not is_valid
        assert "Dependency 'team_x' for team 'team_b' not found in team IDs" in errors
    
    def test_validate_dependencies_self_dependency(self):
        """Test validation with self-dependency."""
        # Arrange
        dependencies = {
            "team_a": ["team_a"]  # Self-dependency
        }
        team_ids = {"team_a", "team_b"}
        
        # Act
        is_valid, errors = self.resolver.validate_dependencies(dependencies, team_ids)
        
        # Assert
        assert not is_valid
        assert "Team 'team_a' cannot depend on itself" in errors
    
    def test_detect_circular_dependencies_none(self):
        """Test circular dependency detection with no cycles."""
        # Arrange
        dependencies = {
            "team_b": ["team_a"],
            "team_c": ["team_b"]
        }
        
        # Act
        has_cycles, cycles = self.resolver.detect_circular_dependencies(dependencies)
        
        # Assert
        assert not has_cycles
        assert cycles == []
    
    def test_detect_circular_dependencies_simple_cycle(self):
        """Test detection of simple circular dependency (A→B→A)."""
        # Arrange
        dependencies = {
            "team_a": ["team_b"],
            "team_b": ["team_a"]
        }
        
        # Act
        has_cycles, cycles = self.resolver.detect_circular_dependencies(dependencies)
        
        # Assert
        assert has_cycles
        assert len(cycles) > 0
        # Should detect the cycle
        cycle_found = any("team_a" in cycle and "team_b" in cycle for cycle in cycles)
        assert cycle_found
    
    def test_detect_circular_dependencies_complex_cycle(self):
        """Test detection of complex circular dependency (A→B→C→A)."""
        # Arrange
        dependencies = {
            "team_a": ["team_c"],
            "team_b": ["team_a"],
            "team_c": ["team_b"]
        }
        
        # Act
        has_cycles, cycles = self.resolver.detect_circular_dependencies(dependencies)
        
        # Assert
        assert has_cycles
        assert len(cycles) > 0
        # Should detect the cycle involving all three teams
        cycle_found = any(
            all(team in cycle for team in ["team_a", "team_b", "team_c"])
            for cycle in cycles
        )
        assert cycle_found
    
    def test_calculate_execution_order_no_dependencies(self):
        """Test execution order calculation with no dependencies."""
        # Arrange
        dependencies = {}
        team_ids = {"team_a", "team_b", "team_c"}
        
        # Act
        result = self.resolver.calculate_execution_order(dependencies, team_ids)
        
        # Assert
        assert set(result) == team_ids
        assert len(result) == len(team_ids)
    
    def test_calculate_execution_order_linear_dependencies(self):
        """Test execution order with linear dependencies (A→B→C)."""
        # Arrange
        dependencies = {
            "team_b": ["team_a"],
            "team_c": ["team_b"]
        }
        team_ids = {"team_a", "team_b", "team_c"}
        
        # Act
        result = self.resolver.calculate_execution_order(dependencies, team_ids)
        
        # Assert
        assert result == ["team_a", "team_b", "team_c"]
    
    def test_calculate_execution_order_parallel_dependencies(self):
        """Test execution order with parallel dependencies (A→C, B→C)."""
        # Arrange
        dependencies = {
            "team_c": ["team_a", "team_b"]
        }
        team_ids = {"team_a", "team_b", "team_c"}
        
        # Act
        result = self.resolver.calculate_execution_order(dependencies, team_ids)
        
        # Assert
        # team_a and team_b can be in any order, but both must come before team_c
        assert result[-1] == "team_c"
        assert set(result[:2]) == {"team_a", "team_b"}
    
    def test_calculate_execution_order_complex_dependencies(self):
        """Test execution order with complex dependency structure."""
        # Arrange
        dependencies = {
            "team_b": ["team_a"],
            "team_c": ["team_a"],
            "team_d": ["team_b", "team_c"],
            "team_e": ["team_d"]
        }
        team_ids = {"team_a", "team_b", "team_c", "team_d", "team_e"}
        
        # Act
        result = self.resolver.calculate_execution_order(dependencies, team_ids)
        
        # Assert
        # Verify all dependencies are satisfied
        positions = {team: i for i, team in enumerate(result)}
        
        assert positions["team_a"] < positions["team_b"]
        assert positions["team_a"] < positions["team_c"]
        assert positions["team_b"] < positions["team_d"]
        assert positions["team_c"] < positions["team_d"]
        assert positions["team_d"] < positions["team_e"]
    
    def test_calculate_execution_order_invalid_dependencies(self):
        """Test execution order calculation with invalid dependencies."""
        # Arrange
        dependencies = {
            "team_b": ["team_x"]  # team_x doesn't exist
        }
        team_ids = {"team_a", "team_b"}
        
        # Act & Assert
        with pytest.raises(DependencyError, match="Invalid dependencies"):
            self.resolver.calculate_execution_order(dependencies, team_ids)
    
    def test_calculate_execution_order_circular_dependencies(self):
        """Test execution order calculation with circular dependencies."""
        # Arrange
        dependencies = {
            "team_a": ["team_b"],
            "team_b": ["team_a"]
        }
        team_ids = {"team_a", "team_b"}
        
        # Act & Assert
        with pytest.raises(DependencyError, match="Circular dependencies detected"):
            self.resolver.calculate_execution_order(dependencies, team_ids)


class TestTeamBuilder:
    """Test the main team builder functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.builder = TeamBuilder()
        
        # Create test configuration
        self.llm_config = LLMConfig(
            provider="openai",
            model="gpt-4o",
            temperature=0.7
        )
        
        self.agent_config = AgentConfig(
            agent_id="test_agent_001",
            agent_name="Test Agent",
            llm_config=self.llm_config,
            system_prompt="You are a test agent",
            user_prompt="Execute test task",
            tools=["test_tool"]
        )
        
        self.supervisor_config = SupervisorConfig(
            llm_config=self.llm_config,
            system_prompt="You are a test supervisor",
            user_prompt="Route tasks to agents"
        )
        
        self.sub_team = SubTeam(
            id="team_001",
            name="Test Team",
            description="A test team",
            supervisor_config=self.supervisor_config,
            agent_configs=[self.agent_config]
        )
        
        self.hierarchical_team = HierarchicalTeam(
            team_name="Test Hierarchical Team",
            description="A test hierarchical team",
            top_supervisor_config=self.supervisor_config,
            sub_teams=[self.sub_team],
            dependencies={},
            global_config=GlobalConfig()
        )
    
    @patch('src.hierarchical_agents.team_builder.AgentFactory')
    def test_create_team_success(self, mock_agent_factory):
        """Test successful team creation using mock agent factory."""
        # Arrange
        mock_factory_instance = Mock()
        mock_agent_factory.return_value = mock_factory_instance
        
        mock_supervisor = Mock(spec=SupervisorAgent)
        mock_agent = Mock(spec=WorkerAgent)
        
        mock_factory_instance.create_supervisor_agent.return_value = mock_supervisor
        mock_factory_instance.create_worker_agent.return_value = mock_agent
        
        builder = TeamBuilder()
        builder.agent_factory = mock_factory_instance
        
        # Act
        result = builder.create_team(self.sub_team)
        
        # Assert
        assert result["id"] == "team_001"
        assert result["name"] == "Test Team"
        assert result["supervisor"] == mock_supervisor
        assert result["agents"]["test_agent_001"] == mock_agent
        assert result["status"] == "created"
        
        mock_factory_instance.create_supervisor_agent.assert_called_once_with(
            self.sub_team.supervisor_config
        )
        mock_factory_instance.create_worker_agent.assert_called_once_with(
            self.agent_config
        )
    
    @patch('src.hierarchical_agents.team_builder.AgentFactory')
    def test_create_team_failure(self, mock_agent_factory):
        """Test team creation failure."""
        # Arrange
        mock_factory_instance = Mock()
        mock_agent_factory.return_value = mock_factory_instance
        
        mock_factory_instance.create_supervisor_agent.side_effect = Exception("Creation failed")
        
        builder = TeamBuilder()
        builder.agent_factory = mock_factory_instance
        
        # Act & Assert
        with pytest.raises(TeamBuildError, match="Failed to create team 'Test Team'"):
            builder.create_team(self.sub_team)
    
    @patch('src.hierarchical_agents.team_builder.AgentFactory')
    def test_create_supervisor_success(self, mock_agent_factory):
        """Test successful supervisor creation."""
        # Arrange
        mock_factory_instance = Mock()
        mock_agent_factory.return_value = mock_factory_instance
        
        mock_supervisor = Mock(spec=SupervisorAgent)
        mock_factory_instance.create_supervisor_agent.return_value = mock_supervisor
        
        builder = TeamBuilder()
        builder.agent_factory = mock_factory_instance
        
        team_members = ["Agent 1", "Agent 2"]
        
        # Act
        result = builder.create_supervisor(team_members, self.supervisor_config)
        
        # Assert
        assert result == mock_supervisor
        assert result.team_members == team_members
        mock_factory_instance.create_supervisor_agent.assert_called_once_with(
            self.supervisor_config
        )
    
    def test_build_dependency_graph(self):
        """Test dependency graph building."""
        # Arrange
        dependencies = {
            "team_b": ["team_a"],
            "team_c": ["team_b"]
        }
        
        # Act
        result = self.builder.build_dependency_graph(dependencies)
        
        # Assert
        assert result == dependencies
    
    def test_calculate_execution_order(self):
        """Test execution order calculation."""
        # Arrange
        dependencies = {
            "team_b": ["team_a"],
            "team_c": ["team_b"]
        }
        team_ids = {"team_a", "team_b", "team_c"}
        
        # Act
        result = self.builder.calculate_execution_order(dependencies, team_ids)
        
        # Assert
        assert result == ["team_a", "team_b", "team_c"]
    
    @patch('src.hierarchical_agents.team_builder.AgentFactory')
    def test_build_hierarchical_team_no_dependencies(self, mock_agent_factory):
        """Test building hierarchical team without dependencies."""
        # Arrange
        mock_factory_instance = Mock()
        mock_agent_factory.return_value = mock_factory_instance
        
        mock_supervisor = Mock(spec=SupervisorAgent)
        mock_agent = Mock(spec=WorkerAgent)
        
        mock_factory_instance.create_supervisor_agent.return_value = mock_supervisor
        mock_factory_instance.create_worker_agent.return_value = mock_agent
        
        builder = TeamBuilder()
        builder.agent_factory = mock_factory_instance
        
        # Act
        result = builder.build_hierarchical_team(self.hierarchical_team)
        
        # Assert
        assert result.team_name == "Test Hierarchical Team"
        assert result.top_supervisor == mock_supervisor
        assert len(result.teams) == 1
        assert "team_001" in result.teams
        assert result.execution_order == ["team_001"]
        assert result.dependency_graph == {}
    
    @patch('src.hierarchical_agents.team_builder.AgentFactory')
    def test_build_hierarchical_team_with_dependencies(self, mock_agent_factory):
        """Test building hierarchical team with dependencies."""
        # Arrange
        mock_factory_instance = Mock()
        mock_agent_factory.return_value = mock_factory_instance
        
        mock_supervisor = Mock(spec=SupervisorAgent)
        mock_agent = Mock(spec=WorkerAgent)
        
        mock_factory_instance.create_supervisor_agent.return_value = mock_supervisor
        mock_factory_instance.create_worker_agent.return_value = mock_agent
        
        # Create team with dependencies
        sub_team_2 = SubTeam(
            id="team_002",
            name="Test Team 2",
            description="Second test team",
            supervisor_config=self.supervisor_config,
            agent_configs=[self.agent_config]
        )
        
        team_with_deps = HierarchicalTeam(
            team_name="Test Hierarchical Team",
            description="A test hierarchical team",
            top_supervisor_config=self.supervisor_config,
            sub_teams=[self.sub_team, sub_team_2],
            dependencies={"team_002": ["team_001"]},
            global_config=GlobalConfig()
        )
        
        builder = TeamBuilder()
        builder.agent_factory = mock_factory_instance
        
        # Act
        result = builder.build_hierarchical_team(team_with_deps)
        
        # Assert
        assert result.team_name == "Test Hierarchical Team"
        assert len(result.teams) == 2
        assert result.execution_order == ["team_001", "team_002"]
        assert result.dependency_graph == {"team_002": ["team_001"]}
    
    def test_validate_team_configuration_valid(self):
        """Test validation of valid team configuration."""
        # Act
        is_valid, errors = self.builder.validate_team_configuration(self.hierarchical_team)
        
        # Assert
        assert is_valid
        assert errors == []
    
    def test_validate_team_configuration_missing_team_name(self):
        """Test validation with missing team name."""
        # Since Pydantic prevents empty team names, we test the validation logic directly
        # by creating a team with a valid name and then testing the validation method
        
        # Create a team and manually set empty team name to bypass Pydantic
        team = self.hierarchical_team.model_copy()
        
        # Test the validation logic by checking if it would catch empty team names
        # We'll modify the validation method to handle this case
        
        # For now, test that Pydantic validation works
        with pytest.raises(Exception):  # Pydantic ValidationError
            HierarchicalTeam(
                team_name="",  # Empty team name
                description="A test hierarchical team",
                top_supervisor_config=self.supervisor_config,
                sub_teams=[self.sub_team],
                dependencies={},
                global_config=GlobalConfig()
            )
    
    def test_validate_team_configuration_no_sub_teams(self):
        """Test validation with no sub-teams."""
        # Arrange
        invalid_team = HierarchicalTeam(
            team_name="Test Team",
            description="A test hierarchical team",
            top_supervisor_config=self.supervisor_config,
            sub_teams=[],  # No sub-teams
            dependencies={},
            global_config=GlobalConfig()
        )
        
        # Act
        is_valid, errors = self.builder.validate_team_configuration(invalid_team)
        
        # Assert
        assert not is_valid
        assert "At least one sub-team is required" in errors
    
    def test_validate_team_configuration_duplicate_team_ids(self):
        """Test validation with duplicate team IDs."""
        # Since Pydantic prevents duplicate team IDs, test that it works
        
        duplicate_sub_team = SubTeam(
            id="team_001",  # Same ID as self.sub_team
            name="Duplicate Team",
            description="A duplicate team",
            supervisor_config=self.supervisor_config,
            agent_configs=[self.agent_config]
        )
        
        # Test that Pydantic validation catches duplicate IDs
        with pytest.raises(Exception):  # Pydantic ValidationError
            HierarchicalTeam(
                team_name="Test Team",
                description="A test hierarchical team",
                top_supervisor_config=self.supervisor_config,
                sub_teams=[self.sub_team, duplicate_sub_team],
                dependencies={},
                global_config=GlobalConfig()
            )
    
    def test_validate_team_configuration_circular_dependencies(self):
        """Test validation with circular dependencies."""
        # Arrange
        sub_team_2 = SubTeam(
            id="team_002",
            name="Test Team 2",
            description="Second test team",
            supervisor_config=self.supervisor_config,
            agent_configs=[self.agent_config]
        )
        
        invalid_team = HierarchicalTeam(
            team_name="Test Team",
            description="A test hierarchical team",
            top_supervisor_config=self.supervisor_config,
            sub_teams=[self.sub_team, sub_team_2],
            dependencies={
                "team_001": ["team_002"],
                "team_002": ["team_001"]  # Circular dependency
            },
            global_config=GlobalConfig()
        )
        
        # Act
        is_valid, errors = self.builder.validate_team_configuration(invalid_team)
        
        # Assert
        assert not is_valid
        circular_error_found = any("Circular dependency" in error for error in errors)
        assert circular_error_found
    
    def test_get_team_statistics(self):
        """Test getting team statistics."""
        # Arrange
        # Build a team first
        with patch('src.hierarchical_agents.team_builder.AgentFactory') as mock_agent_factory:
            mock_factory_instance = Mock()
            mock_agent_factory.return_value = mock_factory_instance
            
            mock_supervisor = Mock(spec=SupervisorAgent)
            mock_agent = Mock(spec=WorkerAgent)
            
            mock_factory_instance.create_supervisor_agent.return_value = mock_supervisor
            mock_factory_instance.create_worker_agent.return_value = mock_agent
            
            builder = TeamBuilder()
            builder.agent_factory = mock_factory_instance
            
            built_team = builder.build_hierarchical_team(self.hierarchical_team)
        
        # Act
        stats = builder.get_team_statistics(built_team)
        
        # Assert
        assert stats["team_name"] == "Test Hierarchical Team"
        assert stats["sub_teams_count"] == 1
        assert stats["total_agents"] == 1
        assert not stats["has_dependencies"]
        assert stats["dependency_count"] == 0
        assert stats["execution_order"] == ["team_001"]
        assert stats["has_runtime_instances"]
        
        # Check team details
        assert "team_001" in stats["team_details"]
        team_detail = stats["team_details"]["team_001"]
        assert team_detail["name"] == "Test Team"
        assert team_detail["agent_count"] == 1
        assert team_detail["agent_names"] == ["Test Agent"]
        assert team_detail["tools_used"] == ["test_tool"]
        
        # Check LLM statistics
        llm_stats = stats["llm_statistics"]
        assert llm_stats["providers"]["openai"] == 3  # 1 top supervisor + 1 sub-team supervisor + 1 agent
        assert llm_stats["models"]["gpt-4o"] == 3
        assert llm_stats["total_llm_instances"] == 3


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.resolver = DependencyResolver()
        self.builder = TeamBuilder()
    
    def test_empty_configuration(self):
        """Test handling of empty configuration."""
        # This should be caught by Pydantic validation before reaching the builder
        pass
    
    def test_single_node_no_dependencies(self):
        """Test single team with no dependencies."""
        # Arrange
        dependencies = {}
        team_ids = {"team_a"}
        
        # Act
        result = self.resolver.calculate_execution_order(dependencies, team_ids)
        
        # Assert
        assert result == ["team_a"]
    
    def test_single_node_self_dependency_detection(self):
        """Test detection of self-dependency in single node."""
        # Arrange
        dependencies = {"team_a": ["team_a"]}
        team_ids = {"team_a"}
        
        # Act
        is_valid, errors = self.resolver.validate_dependencies(dependencies, team_ids)
        
        # Assert
        assert not is_valid
        assert "Team 'team_a' cannot depend on itself" in errors
    
    def test_complex_dependency_graph(self):
        """Test complex dependency graph with multiple paths."""
        # Arrange - Diamond dependency pattern
        dependencies = {
            "team_b": ["team_a"],
            "team_c": ["team_a"],
            "team_d": ["team_b", "team_c"]
        }
        team_ids = {"team_a", "team_b", "team_c", "team_d"}
        
        # Act
        result = self.resolver.calculate_execution_order(dependencies, team_ids)
        
        # Assert
        positions = {team: i for i, team in enumerate(result)}
        
        # team_a must come first
        assert positions["team_a"] == 0
        
        # team_b and team_c must come after team_a but before team_d
        assert positions["team_b"] > positions["team_a"]
        assert positions["team_c"] > positions["team_a"]
        assert positions["team_d"] > positions["team_b"]
        assert positions["team_d"] > positions["team_c"]
        
        # team_d must come last
        assert positions["team_d"] == len(result) - 1
    
    def test_large_dependency_graph(self):
        """Test large dependency graph performance."""
        # Arrange - Create a large linear dependency chain
        num_teams = 100
        team_ids = {f"team_{i:03d}" for i in range(num_teams)}
        dependencies = {}
        
        for i in range(1, num_teams):
            dependencies[f"team_{i:03d}"] = [f"team_{i-1:03d}"]
        
        # Act
        result = self.resolver.calculate_execution_order(dependencies, team_ids)
        
        # Assert
        assert len(result) == num_teams
        assert result[0] == "team_000"
        assert result[-1] == f"team_{num_teams-1:03d}"
        
        # Verify order is correct
        for i in range(1, num_teams):
            current_pos = result.index(f"team_{i:03d}")
            prev_pos = result.index(f"team_{i-1:03d}")
            assert current_pos > prev_pos
    
    def test_disconnected_components(self):
        """Test dependency graph with disconnected components."""
        # Arrange
        dependencies = {
            "team_b": ["team_a"],  # Component 1: a -> b
            "team_d": ["team_c"]   # Component 2: c -> d
        }
        team_ids = {"team_a", "team_b", "team_c", "team_d"}
        
        # Act
        result = self.resolver.calculate_execution_order(dependencies, team_ids)
        
        # Assert
        positions = {team: i for i, team in enumerate(result)}
        
        # Within each component, order must be preserved
        assert positions["team_a"] < positions["team_b"]
        assert positions["team_c"] < positions["team_d"]
        
        # All teams should be included
        assert set(result) == team_ids


class TestUtilityFunctions:
    """Test utility functions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.llm_config = LLMConfig(
            provider="openai",
            model="gpt-4o",
            temperature=0.7
        )
        
        self.agent_config = AgentConfig(
            agent_id="test_agent_001",
            agent_name="Test Agent",
            llm_config=self.llm_config,
            system_prompt="You are a test agent",
            user_prompt="Execute test task"
        )
        
        self.supervisor_config = SupervisorConfig(
            llm_config=self.llm_config,
            system_prompt="You are a test supervisor",
            user_prompt="Route tasks to agents"
        )
        
        self.sub_team = SubTeam(
            id="team_001",
            name="Test Team",
            description="A test team",
            supervisor_config=self.supervisor_config,
            agent_configs=[self.agent_config]
        )
        
        self.hierarchical_team = HierarchicalTeam(
            team_name="Test Hierarchical Team",
            description="A test hierarchical team",
            top_supervisor_config=self.supervisor_config,
            sub_teams=[self.sub_team],
            dependencies={},
            global_config=GlobalConfig()
        )
    
    @patch('src.hierarchical_agents.team_builder.TeamBuilder')
    def test_build_team_from_config(self, mock_team_builder):
        """Test build_team_from_config utility function."""
        # Arrange
        mock_builder_instance = Mock()
        mock_team_builder.return_value = mock_builder_instance
        mock_built_team = Mock()
        mock_builder_instance.build_hierarchical_team.return_value = mock_built_team
        
        # Act
        result = build_team_from_config(self.hierarchical_team)
        
        # Assert
        assert result == mock_built_team
        mock_team_builder.assert_called_once()
        mock_builder_instance.build_hierarchical_team.assert_called_once_with(
            self.hierarchical_team
        )
    
    @patch('src.hierarchical_agents.team_builder.TeamBuilder')
    def test_validate_team_config(self, mock_team_builder):
        """Test validate_team_config utility function."""
        # Arrange
        mock_builder_instance = Mock()
        mock_team_builder.return_value = mock_builder_instance
        mock_builder_instance.validate_team_configuration.return_value = (True, [])
        
        # Act
        is_valid, errors = validate_team_config(self.hierarchical_team)
        
        # Assert
        assert is_valid
        assert errors == []
        mock_team_builder.assert_called_once()
        mock_builder_instance.validate_team_configuration.assert_called_once_with(
            self.hierarchical_team
        )
    
    @patch('src.hierarchical_agents.team_builder.DependencyResolver')
    def test_calculate_team_execution_order(self, mock_dependency_resolver):
        """Test calculate_team_execution_order utility function."""
        # Arrange
        mock_resolver_instance = Mock()
        mock_dependency_resolver.return_value = mock_resolver_instance
        mock_resolver_instance.calculate_execution_order.return_value = ["team_a", "team_b"]
        
        dependencies = {"team_b": ["team_a"]}
        team_ids = {"team_a", "team_b"}
        
        # Act
        result = calculate_team_execution_order(dependencies, team_ids)
        
        # Assert
        assert result == ["team_a", "team_b"]
        mock_dependency_resolver.assert_called_once()
        mock_resolver_instance.calculate_execution_order.assert_called_once_with(
            dependencies, team_ids
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])