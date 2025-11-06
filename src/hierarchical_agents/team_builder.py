"""
Team builder for hierarchical multi-agent system.

This module provides functionality to build hierarchical team structures
from configuration data, including dependency resolution, execution order
calculation, and agent/supervisor instantiation.
"""

import logging
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .data_models import (
    HierarchicalTeam, SubTeam, AgentConfig, SupervisorConfig,
    DependencyGraph, AgentTeam
)
from .agents import WorkerAgent, SupervisorAgent
from .env_key_manager import EnvironmentKeyManager
from .error_handler import ErrorHandler
from .tools import ToolRegistry

logger = logging.getLogger(__name__)


class TeamBuildError(Exception):
    """Raised when team building fails."""
    pass


class DependencyError(Exception):
    """Raised when dependency resolution fails."""
    pass


class AgentFactory:
    """Factory for creating agent instances."""
    
    def __init__(
        self,
        key_manager: Optional[EnvironmentKeyManager] = None,
        error_handler: Optional[ErrorHandler] = None,
        tool_registry: Optional[ToolRegistry] = None
    ):
        """
        Initialize the agent factory.
        
        Args:
            key_manager: Key manager for API keys
            error_handler: Error handler for managing failures
            tool_registry: Tool registry for agent tools
        """
        self.key_manager = key_manager or EnvironmentKeyManager()
        self.error_handler = error_handler or ErrorHandler()
        self.tool_registry = tool_registry or ToolRegistry()
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    def create_worker_agent(self, config: AgentConfig) -> WorkerAgent:
        """
        Create a worker agent instance.
        
        Args:
            config: Agent configuration
            
        Returns:
            WorkerAgent: Created worker agent
            
        Raises:
            TeamBuildError: If agent creation fails
        """
        try:
            agent = WorkerAgent(
                config=config,
                key_manager=self.key_manager,
                error_handler=self.error_handler,
                tool_registry=self.tool_registry
            )
            self.logger.info(f"Created worker agent: {config.agent_name}")
            return agent
        except Exception as e:
            raise TeamBuildError(f"Failed to create worker agent {config.agent_name}: {e}")
    
    def create_supervisor_agent(self, config: SupervisorConfig) -> SupervisorAgent:
        """
        Create a supervisor agent instance.
        
        Args:
            config: Supervisor configuration
            
        Returns:
            SupervisorAgent: Created supervisor agent
            
        Raises:
            TeamBuildError: If supervisor creation fails
        """
        try:
            supervisor = SupervisorAgent(
                config=config,
                key_manager=self.key_manager,
                error_handler=self.error_handler
            )
            self.logger.info("Created supervisor agent")
            return supervisor
        except Exception as e:
            raise TeamBuildError(f"Failed to create supervisor agent: {e}")


class DependencyResolver:
    """Resolves dependencies and calculates execution order."""
    
    def __init__(self):
        """Initialize the dependency resolver."""
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    def build_dependency_graph(self, dependencies: Dict[str, List[str]]) -> DependencyGraph:
        """
        Build a dependency graph from dependency specification.
        
        Args:
            dependencies: Dictionary mapping team IDs to their dependencies
            
        Returns:
            DependencyGraph: Built dependency graph
        """
        # Create a copy to avoid modifying the original
        graph = {}
        for team_id, deps in dependencies.items():
            graph[team_id] = deps.copy()
        
        self.logger.info(f"Built dependency graph with {len(graph)} nodes")
        return graph
    
    def validate_dependencies(
        self, 
        dependencies: Dict[str, List[str]], 
        team_ids: Set[str]
    ) -> Tuple[bool, List[str]]:
        """
        Validate dependency structure for correctness.
        
        Args:
            dependencies: Dependency specification
            team_ids: Set of valid team IDs
            
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_errors)
        """
        errors = []
        
        # Check that all dependency keys exist in team_ids
        for team_id in dependencies.keys():
            if team_id not in team_ids:
                errors.append(f"Dependency key '{team_id}' not found in team IDs")
        
        # Check that all dependency values exist in team_ids
        for team_id, deps in dependencies.items():
            for dep in deps:
                if dep not in team_ids:
                    errors.append(f"Dependency '{dep}' for team '{team_id}' not found in team IDs")
        
        # Check for self-dependencies
        for team_id, deps in dependencies.items():
            if team_id in deps:
                errors.append(f"Team '{team_id}' cannot depend on itself")
        
        return len(errors) == 0, errors
    
    def detect_circular_dependencies(self, dependencies: Dict[str, List[str]]) -> Tuple[bool, List[str]]:
        """
        Detect circular dependencies in the dependency graph.
        
        Args:
            dependencies: Dependency specification
            
        Returns:
            Tuple[bool, List[str]]: (has_cycles, list_of_cycles)
        """
        # Use DFS to detect cycles
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node: str, path: List[str]) -> bool:
            if node in rec_stack:
                # Found a cycle
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                cycles.append(" -> ".join(cycle))
                return True
            
            if node in visited:
                return False
            
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            # Visit all dependencies
            for dep in dependencies.get(node, []):
                if dfs(dep, path):
                    return True
            
            rec_stack.remove(node)
            path.pop()
            return False
        
        # Check all nodes
        all_nodes = set(dependencies.keys())
        for dep_list in dependencies.values():
            all_nodes.update(dep_list)
        
        for node in all_nodes:
            if node not in visited:
                if dfs(node, []):
                    break
        
        has_cycles = len(cycles) > 0
        if has_cycles:
            self.logger.error(f"Circular dependencies detected: {cycles}")
        
        return has_cycles, cycles
    
    def calculate_execution_order(
        self, 
        dependencies: Dict[str, List[str]], 
        team_ids: Set[str]
    ) -> List[str]:
        """
        Calculate execution order using topological sorting.
        
        Args:
            dependencies: Dependency specification
            team_ids: Set of all team IDs
            
        Returns:
            List[str]: Team IDs in execution order
            
        Raises:
            DependencyError: If dependencies cannot be resolved
        """
        # First validate dependencies
        is_valid, errors = self.validate_dependencies(dependencies, team_ids)
        if not is_valid:
            raise DependencyError(f"Invalid dependencies: {errors}")
        
        # Check for circular dependencies
        has_cycles, cycles = self.detect_circular_dependencies(dependencies)
        if has_cycles:
            raise DependencyError(f"Circular dependencies detected: {cycles}")
        
        # Kahn's algorithm for topological sorting
        # Calculate in-degrees
        in_degree = {team_id: 0 for team_id in team_ids}
        
        for team_id, deps in dependencies.items():
            in_degree[team_id] = len(deps)
        
        # Initialize queue with nodes having no dependencies
        queue = deque([team_id for team_id, degree in in_degree.items() if degree == 0])
        result = []
        
        while queue:
            current = queue.popleft()
            result.append(current)
            
            # Update in-degrees for teams that depend on current team
            for team_id, deps in dependencies.items():
                if current in deps:
                    in_degree[team_id] -= 1
                    if in_degree[team_id] == 0:
                        queue.append(team_id)
        
        # Check if all teams are included (no remaining cycles)
        if len(result) != len(team_ids):
            remaining_teams = team_ids - set(result)
            raise DependencyError(f"Cannot resolve dependencies for teams: {remaining_teams}")
        
        self.logger.info(f"Calculated execution order: {result}")
        return result


class TeamBuilder:
    """
    Team builder for creating hierarchical team structures.
    
    This class is responsible for:
    - Creating agent and supervisor instances from configurations
    - Building dependency graphs and calculating execution order
    - Assembling complete hierarchical team structures
    """
    
    def __init__(
        self,
        key_manager: Optional[EnvironmentKeyManager] = None,
        error_handler: Optional[ErrorHandler] = None,
        tool_registry: Optional[ToolRegistry] = None
    ):
        """
        Initialize the team builder.
        
        Args:
            key_manager: Key manager for API keys
            error_handler: Error handler for managing failures
            tool_registry: Tool registry for agent tools
        """
        self.agent_factory = AgentFactory(key_manager, error_handler, tool_registry)
        self.dependency_resolver = DependencyResolver()
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    def create_team(self, sub_team: SubTeam) -> AgentTeam:
        """
        Create an agent team from sub-team configuration.
        
        Args:
            sub_team: Sub-team configuration
            
        Returns:
            AgentTeam: Created agent team with supervisor and workers
            
        Raises:
            TeamBuildError: If team creation fails
        """
        try:
            self.logger.info(f"Creating team: {sub_team.name}")
            
            # Create supervisor
            supervisor = self.agent_factory.create_supervisor_agent(sub_team.supervisor_config)
            
            # Create worker agents
            agents = {}
            for agent_config in sub_team.agent_configs:
                agent = self.agent_factory.create_worker_agent(agent_config)
                agents[agent_config.agent_id] = agent
            
            # Create team structure
            team = {
                "id": sub_team.id,
                "name": sub_team.name,
                "description": sub_team.description,
                "supervisor": supervisor,
                "agents": agents,
                "agent_configs": sub_team.agent_configs,
                "supervisor_config": sub_team.supervisor_config,
                "created_at": None,  # Will be set when team is built
                "status": "created"
            }
            
            self.logger.info(f"Successfully created team '{sub_team.name}' with {len(agents)} agents")
            return team
            
        except Exception as e:
            raise TeamBuildError(f"Failed to create team '{sub_team.name}': {e}")
    
    def create_supervisor(self, team_members: List[str], config: SupervisorConfig) -> SupervisorAgent:
        """
        Create a supervisor for coordinating team members.
        
        Args:
            team_members: List of team member names/IDs
            config: Supervisor configuration
            
        Returns:
            SupervisorAgent: Created supervisor agent
            
        Raises:
            TeamBuildError: If supervisor creation fails
        """
        try:
            self.logger.info(f"Creating supervisor for {len(team_members)} team members")
            
            supervisor = self.agent_factory.create_supervisor_agent(config)
            
            # Store team member information for routing decisions
            supervisor.team_members = team_members
            
            self.logger.info("Successfully created supervisor")
            return supervisor
            
        except Exception as e:
            raise TeamBuildError(f"Failed to create supervisor: {e}")
    
    def build_dependency_graph(self, dependencies: Dict[str, List[str]]) -> DependencyGraph:
        """
        Build dependency graph from dependency specification.
        
        Args:
            dependencies: Dictionary mapping team IDs to their dependencies
            
        Returns:
            DependencyGraph: Built dependency graph
        """
        return self.dependency_resolver.build_dependency_graph(dependencies)
    
    def calculate_execution_order(
        self, 
        dependencies: Dict[str, List[str]], 
        team_ids: Set[str]
    ) -> List[str]:
        """
        Calculate execution order based on dependencies.
        
        Args:
            dependencies: Dependency specification
            team_ids: Set of all team IDs
            
        Returns:
            List[str]: Team IDs in execution order
            
        Raises:
            DependencyError: If dependencies cannot be resolved
        """
        return self.dependency_resolver.calculate_execution_order(dependencies, team_ids)
    
    def build_hierarchical_team(self, config: HierarchicalTeam) -> HierarchicalTeam:
        """
        Build complete hierarchical team structure from configuration.
        
        Args:
            config: Hierarchical team configuration
            
        Returns:
            HierarchicalTeam: Built hierarchical team with runtime instances
            
        Raises:
            TeamBuildError: If team building fails
        """
        try:
            self.logger.info(f"Building hierarchical team: {config.team_name}")
            
            # Create a copy of the configuration to avoid modifying the original
            team = HierarchicalTeam.model_validate(config.model_dump())
            
            # Create top-level supervisor
            team_names = [sub_team.name for sub_team in team.sub_teams]
            top_supervisor = self.create_supervisor(team_names, team.top_supervisor_config)
            team.top_supervisor = top_supervisor
            
            # Create sub-teams
            teams = {}
            team_ids = {sub_team.id for sub_team in team.sub_teams}
            
            for sub_team in team.sub_teams:
                agent_team = self.create_team(sub_team)
                teams[sub_team.id] = agent_team
            
            team.teams = teams
            
            # Build dependency graph
            if team.dependencies:
                team.dependency_graph = self.build_dependency_graph(team.dependencies)
                team.execution_order = self.calculate_execution_order(team.dependencies, team_ids)
            else:
                # No dependencies, use original order
                team.dependency_graph = {}
                team.execution_order = [sub_team.id for sub_team in team.sub_teams]
            
            self.logger.info(
                f"Successfully built hierarchical team '{team.team_name}' with "
                f"{len(team.sub_teams)} sub-teams, execution order: {team.execution_order}"
            )
            
            return team
            
        except Exception as e:
            raise TeamBuildError(f"Failed to build hierarchical team '{config.team_name}': {e}")
    
    def validate_team_configuration(self, config: HierarchicalTeam) -> Tuple[bool, List[str]]:
        """
        Validate team configuration before building.
        
        Args:
            config: Hierarchical team configuration
            
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_errors)
        """
        errors = []
        
        try:
            # Validate basic structure
            if not config.team_name:
                errors.append("Team name is required")
            
            if not config.sub_teams:
                errors.append("At least one sub-team is required")
            
            # Validate sub-teams
            team_ids = set()
            for i, sub_team in enumerate(config.sub_teams):
                if not sub_team.id:
                    errors.append(f"Sub-team {i} missing ID")
                elif sub_team.id in team_ids:
                    errors.append(f"Duplicate sub-team ID: {sub_team.id}")
                else:
                    team_ids.add(sub_team.id)
                
                if not sub_team.name:
                    errors.append(f"Sub-team {i} missing name")
                
                if not sub_team.agent_configs:
                    errors.append(f"Sub-team '{sub_team.name}' has no agents")
                
                # Validate agent configurations
                agent_ids = set()
                for j, agent_config in enumerate(sub_team.agent_configs):
                    if not agent_config.agent_id:
                        errors.append(f"Agent {j} in team '{sub_team.name}' missing ID")
                    elif agent_config.agent_id in agent_ids:
                        errors.append(f"Duplicate agent ID in team '{sub_team.name}': {agent_config.agent_id}")
                    else:
                        agent_ids.add(agent_config.agent_id)
            
            # Validate dependencies
            if config.dependencies:
                is_valid, dep_errors = self.dependency_resolver.validate_dependencies(
                    config.dependencies, team_ids
                )
                if not is_valid:
                    errors.extend(dep_errors)
                
                # Check for circular dependencies
                has_cycles, cycles = self.dependency_resolver.detect_circular_dependencies(
                    config.dependencies
                )
                if has_cycles:
                    errors.extend([f"Circular dependency: {cycle}" for cycle in cycles])
            
        except Exception as e:
            errors.append(f"Configuration validation error: {e}")
        
        is_valid = len(errors) == 0
        if is_valid:
            self.logger.info(f"Team configuration '{config.team_name}' is valid")
        else:
            self.logger.error(f"Team configuration '{config.team_name}' has errors: {errors}")
        
        return is_valid, errors
    
    def get_team_statistics(self, team: HierarchicalTeam) -> Dict[str, Any]:
        """
        Get statistics about the built team.
        
        Args:
            team: Built hierarchical team
            
        Returns:
            Dict[str, Any]: Team statistics
        """
        stats = {
            "team_name": team.team_name,
            "sub_teams_count": len(team.sub_teams),
            "total_agents": sum(len(sub_team.agent_configs) for sub_team in team.sub_teams),
            "has_dependencies": bool(team.dependencies),
            "dependency_count": len(team.dependencies) if team.dependencies else 0,
            "execution_order": team.execution_order,
            "has_runtime_instances": team.top_supervisor is not None and team.teams is not None
        }
        
        # Agent statistics by team
        team_stats = {}
        for sub_team in team.sub_teams:
            team_stats[sub_team.id] = {
                "name": sub_team.name,
                "agent_count": len(sub_team.agent_configs),
                "agent_names": [agent.agent_name for agent in sub_team.agent_configs],
                "tools_used": list(set(
                    tool for agent in sub_team.agent_configs for tool in agent.tools
                ))
            }
        
        stats["team_details"] = team_stats
        
        # LLM provider statistics
        providers = defaultdict(int)
        models = defaultdict(int)
        
        # Count top supervisor
        providers[team.top_supervisor_config.llm_config.provider] += 1
        models[team.top_supervisor_config.llm_config.model] += 1
        
        # Count sub-team supervisors and agents
        for sub_team in team.sub_teams:
            providers[sub_team.supervisor_config.llm_config.provider] += 1
            models[sub_team.supervisor_config.llm_config.model] += 1
            
            for agent in sub_team.agent_configs:
                providers[agent.llm_config.provider] += 1
                models[agent.llm_config.model] += 1
        
        stats["llm_statistics"] = {
            "providers": dict(providers),
            "models": dict(models),
            "total_llm_instances": sum(providers.values())
        }
        
        return stats
    
    def rebuild_team_with_changes(
        self, 
        team: HierarchicalTeam, 
        changes: Dict[str, Any]
    ) -> HierarchicalTeam:
        """
        Rebuild team with configuration changes.
        
        Args:
            team: Existing hierarchical team
            changes: Dictionary of changes to apply
            
        Returns:
            HierarchicalTeam: Rebuilt team with changes
            
        Raises:
            TeamBuildError: If rebuild fails
        """
        try:
            self.logger.info(f"Rebuilding team '{team.team_name}' with changes")
            
            # Create new configuration with changes
            config_dict = team.model_dump(exclude={'top_supervisor', 'teams', 'dependency_graph', 'execution_order'})
            
            # Apply changes
            for key, value in changes.items():
                if '.' in key:
                    # Handle nested keys like 'global_config.max_execution_time'
                    keys = key.split('.')
                    current = config_dict
                    for k in keys[:-1]:
                        if k not in current:
                            current[k] = {}
                        current = current[k]
                    current[keys[-1]] = value
                else:
                    config_dict[key] = value
            
            # Create new configuration
            new_config = HierarchicalTeam.model_validate(config_dict)
            
            # Build new team
            return self.build_hierarchical_team(new_config)
            
        except Exception as e:
            raise TeamBuildError(f"Failed to rebuild team with changes: {e}")


# Utility functions for team building
def build_team_from_config(config: HierarchicalTeam) -> HierarchicalTeam:
    """
    Convenience function to build a team from configuration.
    
    Args:
        config: Hierarchical team configuration
        
    Returns:
        HierarchicalTeam: Built hierarchical team
    """
    builder = TeamBuilder()
    return builder.build_hierarchical_team(config)


def validate_team_config(config: HierarchicalTeam) -> Tuple[bool, List[str]]:
    """
    Convenience function to validate team configuration.
    
    Args:
        config: Hierarchical team configuration
        
    Returns:
        Tuple[bool, List[str]]: (is_valid, list_of_errors)
    """
    builder = TeamBuilder()
    return builder.validate_team_configuration(config)


def calculate_team_execution_order(
    dependencies: Dict[str, List[str]], 
    team_ids: Set[str]
) -> List[str]:
    """
    Convenience function to calculate execution order.
    
    Args:
        dependencies: Dependency specification
        team_ids: Set of all team IDs
        
    Returns:
        List[str]: Team IDs in execution order
    """
    resolver = DependencyResolver()
    return resolver.calculate_execution_order(dependencies, team_ids)