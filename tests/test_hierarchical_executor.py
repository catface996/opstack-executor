"""
Tests for hierarchical execution coordinator.

This module tests the hierarchical execution logic including:
- Three-layer execution flow (top supervisor → team supervisors → agents)
- Dependency handling and execution order
- State synchronization across layers
- Error propagation and recovery
"""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.hierarchical_agents.hierarchical_executor import (
    HierarchicalExecutor, TeamExecutionContext, HierarchicalExecutionError
)
from src.hierarchical_agents.data_models import (
    HierarchicalTeam, SubTeam, AgentConfig, SupervisorConfig, LLMConfig,
    ExecutionContext, ExecutionConfig, ExecutionStatus, TeamState, TeamResult,
    GlobalConfig, ExecutionEvent, ErrorInfo
)
from src.hierarchical_agents.agents import SupervisorAgent, WorkerAgent
from src.hierarchical_agents.state_manager import StateManager
from src.hierarchical_agents.event_manager import EventManager
from src.hierarchical_agents.error_handler import ErrorHandler


@pytest.fixture
def mock_state_manager():
    """Create mock state manager."""
    manager = Mock(spec=StateManager)
    manager.update_team_state = AsyncMock()
    manager.update_team_result = AsyncMock()
    manager.add_error = AsyncMock()
    return manager


@pytest.fixture
def mock_event_manager():
    """Create mock event manager."""
    manager = Mock(spec=EventManager)
    manager.emit_supervisor_routing = AsyncMock()
    manager.emit_agent_started = AsyncMock()
    manager.emit_agent_completed = AsyncMock()
    return manager


@pytest.fixture
def mock_error_handler():
    """Create mock error handler."""
    handler = Mock(spec=ErrorHandler)
    handler.handle_error_async = AsyncMock()
    return handler


@pytest.fixture
def sample_llm_config():
    """Create sample LLM configuration."""
    return LLMConfig(
        provider="openai",
        model="gpt-4o",
        temperature=0.3
    )


@pytest.fixture
def sample_agent_config(sample_llm_config):
    """Create sample agent configuration."""
    return AgentConfig(
        agent_id="agent_001",
        agent_name="Test Agent",
        llm_config=sample_llm_config,
        system_prompt="You are a test agent.",
        user_prompt="Execute test task.",
        tools=["test_tool"]
    )


@pytest.fixture
def sample_supervisor_config(sample_llm_config):
    """Create sample supervisor configuration."""
    return SupervisorConfig(
        llm_config=sample_llm_config,
        system_prompt="You are a test supervisor.",
        user_prompt="Route tasks to appropriate agents."
    )


@pytest.fixture
def sample_sub_team(sample_supervisor_config, sample_agent_config):
    """Create sample sub-team."""
    return SubTeam(
        id="team_001",
        name="Test Team",
        description="A test team",
        supervisor_config=sample_supervisor_config,
        agent_configs=[sample_agent_config]
    )


@pytest.fixture
def sample_hierarchical_team(sample_supervisor_config, sample_sub_team):
    """Create sample hierarchical team."""
    team = HierarchicalTeam(
        team_name="Test Hierarchical Team",
        description="A test hierarchical team",
        top_supervisor_config=sample_supervisor_config,
        sub_teams=[sample_sub_team],
        dependencies={},
        global_config=GlobalConfig()
    )
    
    # Add runtime instances (mock)
    team.top_supervisor = Mock(spec=SupervisorAgent)
    team.teams = {
        "team_001": {
            "id": "team_001",
            "name": "Test Team",
            "supervisor": Mock(spec=SupervisorAgent),
            "agents": {
                "agent_001": Mock(spec=WorkerAgent)
            }
        }
    }
    team.execution_order = ["team_001"]
    
    return team


@pytest.fixture
def sample_execution_context():
    """Create sample execution context."""
    return ExecutionContext(
        execution_id="exec_001",
        team_id="test_team",
        config=ExecutionConfig(),
        started_at=datetime.now()
    )


@pytest.fixture
def hierarchical_executor(mock_state_manager, mock_event_manager, mock_error_handler):
    """Create hierarchical executor instance."""
    return HierarchicalExecutor(
        state_manager=mock_state_manager,
        event_manager=mock_event_manager,
        error_handler=mock_error_handler
    )


class TestTeamExecutionContext:
    """Test TeamExecutionContext functionality."""
    
    def test_initialization(self, sample_execution_context):
        """Test team execution context initialization."""
        supervisor = Mock(spec=SupervisorAgent)
        agents = {"agent_001": Mock(spec=WorkerAgent)}
        
        context = TeamExecutionContext(
            team_id="team_001",
            team_name="Test Team",
            execution_id="exec_001",
            parent_context=sample_execution_context,
            dependencies=["team_002"],
            supervisor=supervisor,
            agents=agents
        )
        
        assert context.team_id == "team_001"
        assert context.team_name == "Test Team"
        assert context.execution_id == "exec_001"
        assert context.dependencies == ["team_002"]
        assert context.supervisor == supervisor
        assert context.agents == agents
        assert context.status == ExecutionStatus.PENDING
        assert not context.dependencies_met
        assert context.waiting_for_dependencies == {"team_002"}
    
    def test_dependency_completion(self, sample_execution_context):
        """Test dependency completion tracking."""
        context = TeamExecutionContext(
            team_id="team_001",
            team_name="Test Team",
            execution_id="exec_001",
            parent_context=sample_execution_context,
            dependencies=["team_002", "team_003"],
            supervisor=Mock(spec=SupervisorAgent),
            agents={}
        )
        
        # Initially not ready
        assert not context.is_ready_to_execute()
        
        # Mark one dependency as completed
        context.mark_dependency_completed("team_002")
        assert not context.dependencies_met
        assert not context.is_ready_to_execute()
        
        # Mark second dependency as completed
        context.mark_dependency_completed("team_003")
        assert context.dependencies_met
        assert context.is_ready_to_execute()
    
    def test_get_available_agents(self, sample_execution_context, sample_agent_config):
        """Test getting available agents for routing."""
        # Create mock agent with config
        mock_agent = Mock(spec=WorkerAgent)
        mock_agent.config = sample_agent_config
        
        context = TeamExecutionContext(
            team_id="team_001",
            team_name="Test Team",
            execution_id="exec_001",
            parent_context=sample_execution_context,
            dependencies=[],
            supervisor=Mock(spec=SupervisorAgent),
            agents={"agent_001": mock_agent}
        )
        
        available_agents = context.get_available_agents()
        
        assert len(available_agents) == 1
        assert available_agents[0]["name"] == "Test Agent"
        assert available_agents[0]["id"] == "agent_001"
        assert "description" in available_agents[0]
        assert available_agents[0]["tools"] == ["test_tool"]


class TestHierarchicalExecutor:
    """Test HierarchicalExecutor functionality."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, hierarchical_executor):
        """Test hierarchical executor initialization."""
        assert hierarchical_executor.state_manager is not None
        assert hierarchical_executor.event_manager is not None
        assert hierarchical_executor.error_handler is not None
        assert hierarchical_executor._active_executions == {}
    
    @pytest.mark.asyncio
    async def test_execute_hierarchical_team_success(
        self, 
        hierarchical_executor, 
        sample_hierarchical_team, 
        sample_execution_context
    ):
        """Test successful hierarchical team execution."""
        # Mock agent execution
        mock_agent = sample_hierarchical_team.teams["team_001"]["agents"]["agent_001"]
        mock_agent.config = sample_hierarchical_team.sub_teams[0].agent_configs[0]
        mock_agent.execute.return_value = {
            "agent_id": "agent_001",
            "agent_name": "Test Agent",
            "status": "completed",
            "output": "Test output",
            "execution_time": 1.0,
            "tools_used": []
        }
        
        # Mock supervisor routing
        mock_supervisor = sample_hierarchical_team.teams["team_001"]["supervisor"]
        mock_supervisor.route_task_intelligently.return_value = "Test Agent"
        
        # Execute hierarchical team
        results = await hierarchical_executor.execute_hierarchical_team(
            team=sample_hierarchical_team,
            execution_context=sample_execution_context
        )
        
        # Verify results
        assert len(results) == 1
        assert "team_001" in results
        assert results["team_001"].status == "completed"
        assert results["team_001"].agents is not None
        
        # Verify state manager calls
        hierarchical_executor.state_manager.update_team_state.assert_called()
        hierarchical_executor.state_manager.update_team_result.assert_called()
        
        # Verify event manager calls
        hierarchical_executor.event_manager.emit_supervisor_routing.assert_called()
        hierarchical_executor.event_manager.emit_agent_started.assert_called()
        hierarchical_executor.event_manager.emit_agent_completed.assert_called()
    
    @pytest.mark.asyncio
    async def test_dependency_handling(
        self, 
        hierarchical_executor, 
        sample_supervisor_config, 
        sample_agent_config
    ):
        """Test dependency handling and execution order."""
        # Create team with dependencies
        team1 = SubTeam(
            id="team_001",
            name="Team 1",
            description="First team",
            supervisor_config=sample_supervisor_config,
            agent_configs=[sample_agent_config]
        )
        
        team2_config = AgentConfig(
            agent_id="agent_002",
            agent_name="Agent 2",
            llm_config=sample_supervisor_config.llm_config,
            system_prompt="You are agent 2.",
            user_prompt="Execute task 2.",
            tools=[]
        )
        
        team2 = SubTeam(
            id="team_002",
            name="Team 2",
            description="Second team",
            supervisor_config=sample_supervisor_config,
            agent_configs=[team2_config]
        )
        
        hierarchical_team = HierarchicalTeam(
            team_name="Dependent Teams",
            description="Teams with dependencies",
            top_supervisor_config=sample_supervisor_config,
            sub_teams=[team1, team2],
            dependencies={"team_002": ["team_001"]},  # team_002 depends on team_001
            global_config=GlobalConfig()
        )
        
        # Add runtime instances
        hierarchical_team.top_supervisor = Mock(spec=SupervisorAgent)
        hierarchical_team.teams = {
            "team_001": {
                "id": "team_001",
                "name": "Team 1",
                "supervisor": Mock(spec=SupervisorAgent),
                "agents": {"agent_001": Mock(spec=WorkerAgent)}
            },
            "team_002": {
                "id": "team_002", 
                "name": "Team 2",
                "supervisor": Mock(spec=SupervisorAgent),
                "agents": {"agent_002": Mock(spec=WorkerAgent)}
            }
        }
        hierarchical_team.execution_order = ["team_001", "team_002"]
        
        # Mock agent executions
        for team_data in hierarchical_team.teams.values():
            for agent in team_data["agents"].values():
                agent.config = Mock()
                agent.config.agent_name = "Mock Agent"
                agent.config.agent_id = "mock_agent"
                agent.execute.return_value = {
                    "agent_id": "mock_agent",
                    "agent_name": "Mock Agent",
                    "status": "completed",
                    "output": "Mock output",
                    "execution_time": 1.0,
                    "tools_used": []
                }
            
            # Mock supervisor routing
            team_data["supervisor"].route_task_intelligently.return_value = "Mock Agent"
        
        execution_context = ExecutionContext(
            execution_id="exec_dep_test",
            team_id="dependent_teams",
            config=ExecutionConfig(),
            started_at=datetime.now()
        )
        
        # Execute hierarchical team
        results = await hierarchical_executor.execute_hierarchical_team(
            team=hierarchical_team,
            execution_context=execution_context
        )
        
        # Verify both teams executed
        assert len(results) == 2
        assert "team_001" in results
        assert "team_002" in results
        assert results["team_001"].status == "completed"
        assert results["team_002"].status == "completed"
    
    @pytest.mark.asyncio
    async def test_supervisor_routing(
        self, 
        hierarchical_executor, 
        sample_hierarchical_team, 
        sample_execution_context
    ):
        """Test supervisor routing functionality."""
        # Mock supervisor routing to return specific agent
        mock_supervisor = sample_hierarchical_team.teams["team_001"]["supervisor"]
        mock_supervisor.route_task_intelligently.return_value = "Test Agent"
        
        # Mock agent execution
        mock_agent = sample_hierarchical_team.teams["team_001"]["agents"]["agent_001"]
        mock_agent.config = sample_hierarchical_team.sub_teams[0].agent_configs[0]
        mock_agent.execute.return_value = {
            "agent_id": "agent_001",
            "agent_name": "Test Agent",
            "status": "completed",
            "output": "Routed execution result",
            "execution_time": 1.0,
            "tools_used": []
        }
        
        # Execute team
        results = await hierarchical_executor.execute_hierarchical_team(
            team=sample_hierarchical_team,
            execution_context=sample_execution_context
        )
        
        # Verify supervisor was called for routing
        mock_supervisor.route_task_intelligently.assert_called_once()
        
        # Verify routing event was emitted
        hierarchical_executor.event_manager.emit_supervisor_routing.assert_called()
        
        # Verify correct agent was executed
        mock_agent.execute.assert_called_once()
        
        # Verify results contain routed execution
        assert results["team_001"].agents["agent_001"]["output"] == "Routed execution result"
    
    @pytest.mark.asyncio
    async def test_state_synchronization(
        self, 
        hierarchical_executor, 
        sample_hierarchical_team, 
        sample_execution_context
    ):
        """Test state synchronization across execution layers."""
        # Mock agent execution
        mock_agent = sample_hierarchical_team.teams["team_001"]["agents"]["agent_001"]
        mock_agent.config = sample_hierarchical_team.sub_teams[0].agent_configs[0]
        mock_agent.execute.return_value = {
            "agent_id": "agent_001",
            "agent_name": "Test Agent",
            "status": "completed",
            "output": "State sync test",
            "execution_time": 1.0,
            "tools_used": []
        }
        
        # Mock supervisor routing
        mock_supervisor = sample_hierarchical_team.teams["team_001"]["supervisor"]
        mock_supervisor.route_task_intelligently.return_value = "Test Agent"
        
        # Execute team
        await hierarchical_executor.execute_hierarchical_team(
            team=sample_hierarchical_team,
            execution_context=sample_execution_context
        )
        
        # Verify state updates were called in correct order
        state_calls = hierarchical_executor.state_manager.update_team_state.call_args_list
        
        # Should have at least 3 calls: pending -> running -> completed
        assert len(state_calls) >= 3
        
        # Verify team result was stored
        hierarchical_executor.state_manager.update_team_result.assert_called_once()
        
        # Verify the final state is completed
        final_call = state_calls[-1]
        final_state = final_call[0][2]  # Third argument is the TeamState
        assert final_state.execution_status == ExecutionStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_error_propagation(
        self, 
        hierarchical_executor, 
        sample_hierarchical_team, 
        sample_execution_context
    ):
        """Test error propagation and handling."""
        # Mock agent to raise an exception
        mock_agent = sample_hierarchical_team.teams["team_001"]["agents"]["agent_001"]
        mock_agent.config = sample_hierarchical_team.sub_teams[0].agent_configs[0]
        mock_agent.execute.side_effect = Exception("Agent execution failed")
        
        # Mock supervisor routing
        mock_supervisor = sample_hierarchical_team.teams["team_001"]["supervisor"]
        mock_supervisor.route_task_intelligently.return_value = "Test Agent"
        
        # Mock error handler to not re-raise
        hierarchical_executor.error_handler.handle_error_async.return_value = None
        
        # Execute team (should handle error gracefully)
        results = await hierarchical_executor.execute_hierarchical_team(
            team=sample_hierarchical_team,
            execution_context=sample_execution_context
        )
        
        # Verify error was handled
        hierarchical_executor.error_handler.handle_error_async.assert_called()
        
        # Verify error was recorded in state manager
        hierarchical_executor.state_manager.add_error.assert_called()
        
        # Verify team result shows failure
        assert results["team_001"].status == "failed"
    
    @pytest.mark.asyncio
    async def test_execution_progress_tracking(
        self, 
        hierarchical_executor, 
        sample_hierarchical_team, 
        sample_execution_context
    ):
        """Test execution progress tracking."""
        execution_id = sample_execution_context.execution_id
        
        # Initialize execution context
        await hierarchical_executor._initialize_execution_context(
            sample_hierarchical_team, 
            sample_execution_context
        )
        
        # Get initial progress
        progress = await hierarchical_executor.get_execution_progress(execution_id)
        
        assert progress["execution_id"] == execution_id
        assert progress["total_teams"] == 1
        assert progress["completed_teams"] == 0
        assert progress["overall_progress"] == 0
        assert "teams" in progress
        assert "team_001" in progress["teams"]
        
        # Verify team status
        team_progress = progress["teams"]["team_001"]
        assert team_progress["status"] == "pending"
        assert team_progress["dependencies_met"] == True  # No dependencies
    
    @pytest.mark.asyncio
    async def test_execution_stop(
        self, 
        hierarchical_executor, 
        sample_hierarchical_team, 
        sample_execution_context
    ):
        """Test stopping execution gracefully."""
        execution_id = sample_execution_context.execution_id
        
        # Initialize execution context
        await hierarchical_executor._initialize_execution_context(
            sample_hierarchical_team, 
            sample_execution_context
        )
        
        # Stop execution
        result = await hierarchical_executor.stop_execution(execution_id, graceful=True)
        
        assert result == True
        
        # Verify execution is no longer active
        progress = await hierarchical_executor.get_execution_progress(execution_id)
        assert "error" in progress
    
    @pytest.mark.asyncio
    async def test_stats_collection(self, hierarchical_executor):
        """Test statistics collection."""
        stats = await hierarchical_executor.get_stats()
        
        assert "active_executions" in stats
        assert "total_teams" in stats
        assert "team_status_distribution" in stats
        assert "average_teams_per_execution" in stats
        
        # Initially should be empty
        assert stats["active_executions"] == 0
        assert stats["total_teams"] == 0


class TestIntegrationScenarios:
    """Test complex integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_complex_dependency_chain(
        self, 
        hierarchical_executor, 
        sample_supervisor_config, 
        sample_llm_config
    ):
        """Test complex dependency chain: A -> B -> C."""
        # Create three teams with chain dependencies
        teams = []
        for i in range(3):
            agent_config = AgentConfig(
                agent_id=f"agent_{i:03d}",
                agent_name=f"Agent {i}",
                llm_config=sample_llm_config,
                system_prompt=f"You are agent {i}.",
                user_prompt=f"Execute task {i}.",
                tools=[]
            )
            
            team = SubTeam(
                id=f"team_{i:03d}",
                name=f"Team {i}",
                description=f"Team {i} description",
                supervisor_config=sample_supervisor_config,
                agent_configs=[agent_config]
            )
            teams.append(team)
        
        # Create dependencies: team_001 -> team_000, team_002 -> team_001
        dependencies = {
            "team_001": ["team_000"],
            "team_002": ["team_001"]
        }
        
        hierarchical_team = HierarchicalTeam(
            team_name="Chain Dependencies",
            description="Teams with chain dependencies",
            top_supervisor_config=sample_supervisor_config,
            sub_teams=teams,
            dependencies=dependencies,
            global_config=GlobalConfig()
        )
        
        # Add runtime instances
        hierarchical_team.top_supervisor = Mock(spec=SupervisorAgent)
        hierarchical_team.teams = {}
        
        for i, team in enumerate(teams):
            mock_agent = Mock(spec=WorkerAgent)
            mock_agent.config = team.agent_configs[0]
            mock_agent.execute.return_value = {
                "agent_id": f"agent_{i:03d}",
                "agent_name": f"Agent {i}",
                "status": "completed",
                "output": f"Output from agent {i}",
                "execution_time": 1.0,
                "tools_used": []
            }
            
            mock_supervisor = Mock(spec=SupervisorAgent)
            mock_supervisor.route_task_intelligently.return_value = f"Agent {i}"
            
            hierarchical_team.teams[team.id] = {
                "id": team.id,
                "name": team.name,
                "supervisor": mock_supervisor,
                "agents": {f"agent_{i:03d}": mock_agent}
            }
        
        hierarchical_team.execution_order = ["team_000", "team_001", "team_002"]
        
        execution_context = ExecutionContext(
            execution_id="exec_chain_test",
            team_id="chain_dependencies",
            config=ExecutionConfig(),
            started_at=datetime.now()
        )
        
        # Execute hierarchical team
        results = await hierarchical_executor.execute_hierarchical_team(
            team=hierarchical_team,
            execution_context=execution_context
        )
        
        # Verify all teams executed in correct order
        assert len(results) == 3
        for i in range(3):
            team_id = f"team_{i:03d}"
            assert team_id in results
            assert results[team_id].status == "completed"
    
    @pytest.mark.asyncio
    async def test_parallel_execution_with_convergence(
        self, 
        hierarchical_executor, 
        sample_supervisor_config, 
        sample_llm_config
    ):
        """Test parallel execution with convergence: A,B -> C."""
        # Create three teams: A and B can run in parallel, C depends on both
        teams = []
        for i in range(3):
            agent_config = AgentConfig(
                agent_id=f"agent_{i:03d}",
                agent_name=f"Agent {i}",
                llm_config=sample_llm_config,
                system_prompt=f"You are agent {i}.",
                user_prompt=f"Execute task {i}.",
                tools=[]
            )
            
            team = SubTeam(
                id=f"team_{i:03d}",
                name=f"Team {i}",
                description=f"Team {i} description",
                supervisor_config=sample_supervisor_config,
                agent_configs=[agent_config]
            )
            teams.append(team)
        
        # Create dependencies: team_002 depends on both team_000 and team_001
        dependencies = {
            "team_002": ["team_000", "team_001"]
        }
        
        hierarchical_team = HierarchicalTeam(
            team_name="Parallel with Convergence",
            description="Parallel teams converging to final team",
            top_supervisor_config=sample_supervisor_config,
            sub_teams=teams,
            dependencies=dependencies,
            global_config=GlobalConfig()
        )
        
        # Add runtime instances
        hierarchical_team.top_supervisor = Mock(spec=SupervisorAgent)
        hierarchical_team.teams = {}
        
        for i, team in enumerate(teams):
            mock_agent = Mock(spec=WorkerAgent)
            mock_agent.config = team.agent_configs[0]
            mock_agent.execute.return_value = {
                "agent_id": f"agent_{i:03d}",
                "agent_name": f"Agent {i}",
                "status": "completed",
                "output": f"Output from agent {i}",
                "execution_time": 1.0,
                "tools_used": []
            }
            
            mock_supervisor = Mock(spec=SupervisorAgent)
            mock_supervisor.route_task_intelligently.return_value = f"Agent {i}"
            
            hierarchical_team.teams[team.id] = {
                "id": team.id,
                "name": team.name,
                "supervisor": mock_supervisor,
                "agents": {f"agent_{i:03d}": mock_agent}
            }
        
        # Execution order should handle parallel execution
        hierarchical_team.execution_order = ["team_000", "team_001", "team_002"]
        
        execution_context = ExecutionContext(
            execution_id="exec_parallel_test",
            team_id="parallel_convergence",
            config=ExecutionConfig(),
            started_at=datetime.now()
        )
        
        # Execute hierarchical team
        results = await hierarchical_executor.execute_hierarchical_team(
            team=hierarchical_team,
            execution_context=execution_context
        )
        
        # Verify all teams executed successfully
        assert len(results) == 3
        for i in range(3):
            team_id = f"team_{i:03d}"
            assert team_id in results
            assert results[team_id].status == "completed"


if __name__ == "__main__":
    pytest.main([__file__])