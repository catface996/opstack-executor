"""
Configuration manager for hierarchical multi-agent system.

This module provides functionality to load, validate, and manage
configuration files for hierarchical teams. It supports JSON format
and provides comprehensive validation of team structures.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from .data_models import (
    HierarchicalTeam,
    SubTeam,
    AgentConfig,
    SupervisorConfig,
    GlobalConfig,
    LLMConfig
)

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


class ConfigManager:
    """
    Configuration manager for loading and validating hierarchical team configurations.
    
    Supports JSON configuration files and provides comprehensive validation
    including dependency checking, unique ID validation, and required field verification.
    """
    
    def __init__(self):
        """Initialize the configuration manager."""
        self._required_fields = {
            'team_name', 'description', 'top_supervisor_config', 'sub_teams'
        }
        self._required_supervisor_fields = {
            'llm_config', 'system_prompt', 'user_prompt'
        }
        self._required_agent_fields = {
            'agent_id', 'agent_name', 'llm_config', 'system_prompt', 'user_prompt'
        }
        self._required_llm_fields = {
            'provider', 'model'
        }
    
    def load_config(self, config_path: Union[str, Path]) -> HierarchicalTeam:
        """
        Load and validate a hierarchical team configuration from a JSON file.
        
        Args:
            config_path: Path to the JSON configuration file
            
        Returns:
            HierarchicalTeam: Validated hierarchical team configuration
            
        Raises:
            ConfigValidationError: If configuration is invalid
            FileNotFoundError: If configuration file doesn't exist
            json.JSONDecodeError: If JSON is malformed
        """
        config_path = Path(config_path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        logger.info(f"Loading configuration from: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigValidationError(f"Invalid JSON in configuration file: {e}")
        
        # Validate the configuration structure
        self._validate_config_structure(config_data)
        
        # Create and validate the hierarchical team
        try:
            team = HierarchicalTeam.model_validate(config_data)
        except Exception as e:
            raise ConfigValidationError(f"Configuration validation failed: {e}")
        
        # Additional business logic validation
        self._validate_business_logic(team)
        
        logger.info(f"Successfully loaded configuration for team: {team.team_name}")
        return team
    
    def validate_config_dict(self, config_data: Dict[str, Any]) -> HierarchicalTeam:
        """
        Validate a configuration dictionary without loading from file.
        
        Args:
            config_data: Configuration dictionary
            
        Returns:
            HierarchicalTeam: Validated hierarchical team configuration
            
        Raises:
            ConfigValidationError: If configuration is invalid
        """
        logger.info("Validating configuration dictionary")
        
        # Validate the configuration structure
        self._validate_config_structure(config_data)
        
        # Create and validate the hierarchical team
        try:
            team = HierarchicalTeam.model_validate(config_data)
        except Exception as e:
            raise ConfigValidationError(f"Configuration validation failed: {e}")
        
        # Additional business logic validation
        self._validate_business_logic(team)
        
        logger.info(f"Successfully validated configuration for team: {team.team_name}")
        return team
    
    def save_config(self, team: HierarchicalTeam, config_path: Union[str, Path]) -> None:
        """
        Save a hierarchical team configuration to a JSON file.
        
        Args:
            team: Hierarchical team configuration to save
            config_path: Path where to save the configuration
        """
        config_path = Path(config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Saving configuration to: {config_path}")
        
        # Convert to dictionary and save
        config_data = team.model_dump(exclude={'top_supervisor', 'teams', 'dependency_graph', 'execution_order'})
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"Successfully saved configuration for team: {team.team_name}")
    
    def _validate_config_structure(self, config_data: Dict[str, Any]) -> None:
        """
        Validate the basic structure of the configuration.
        
        Args:
            config_data: Configuration dictionary to validate
            
        Raises:
            ConfigValidationError: If structure is invalid
        """
        # Check required top-level fields
        missing_fields = self._required_fields - set(config_data.keys())
        if missing_fields:
            raise ConfigValidationError(f"Missing required fields: {missing_fields}")
        
        # Validate top supervisor config
        supervisor_config = config_data.get('top_supervisor_config', {})
        self._validate_supervisor_config(supervisor_config, "top_supervisor_config")
        
        # Validate sub-teams
        sub_teams = config_data.get('sub_teams', [])
        if not isinstance(sub_teams, list) or len(sub_teams) == 0:
            raise ConfigValidationError("sub_teams must be a non-empty list")
        
        for i, sub_team in enumerate(sub_teams):
            self._validate_sub_team_config(sub_team, f"sub_teams[{i}]")
        
        # Validate dependencies if present
        dependencies = config_data.get('dependencies', {})
        if dependencies:
            self._validate_dependencies_structure(dependencies, sub_teams)
    
    def _validate_supervisor_config(self, supervisor_config: Dict[str, Any], context: str) -> None:
        """Validate supervisor configuration structure."""
        missing_fields = self._required_supervisor_fields - set(supervisor_config.keys())
        if missing_fields:
            raise ConfigValidationError(f"{context}: Missing required supervisor fields: {missing_fields}")
        
        # Validate LLM config
        llm_config = supervisor_config.get('llm_config', {})
        self._validate_llm_config(llm_config, f"{context}.llm_config")
    
    def _validate_sub_team_config(self, sub_team: Dict[str, Any], context: str) -> None:
        """Validate sub-team configuration structure."""
        required_sub_team_fields = {'id', 'name', 'description', 'supervisor_config', 'agent_configs'}
        missing_fields = required_sub_team_fields - set(sub_team.keys())
        if missing_fields:
            raise ConfigValidationError(f"{context}: Missing required sub-team fields: {missing_fields}")
        
        # Validate supervisor config
        supervisor_config = sub_team.get('supervisor_config', {})
        self._validate_supervisor_config(supervisor_config, f"{context}.supervisor_config")
        
        # Validate agent configs
        agent_configs = sub_team.get('agent_configs', [])
        if not isinstance(agent_configs, list) or len(agent_configs) == 0:
            raise ConfigValidationError(f"{context}: agent_configs must be a non-empty list")
        
        for i, agent_config in enumerate(agent_configs):
            self._validate_agent_config(agent_config, f"{context}.agent_configs[{i}]")
    
    def _validate_agent_config(self, agent_config: Dict[str, Any], context: str) -> None:
        """Validate agent configuration structure."""
        missing_fields = self._required_agent_fields - set(agent_config.keys())
        if missing_fields:
            raise ConfigValidationError(f"{context}: Missing required agent fields: {missing_fields}")
        
        # Validate LLM config
        llm_config = agent_config.get('llm_config', {})
        self._validate_llm_config(llm_config, f"{context}.llm_config")
    
    def _validate_llm_config(self, llm_config: Dict[str, Any], context: str) -> None:
        """Validate LLM configuration structure."""
        missing_fields = self._required_llm_fields - set(llm_config.keys())
        if missing_fields:
            raise ConfigValidationError(f"{context}: Missing required LLM fields: {missing_fields}")
        
        # Validate provider
        provider = llm_config.get('provider')
        allowed_providers = {'openai', 'openrouter', 'aws_bedrock'}
        if provider not in allowed_providers:
            raise ConfigValidationError(f"{context}: Invalid provider '{provider}'. Must be one of {allowed_providers}")
        
        # Validate AWS Bedrock specific requirements
        if provider == 'aws_bedrock' and not llm_config.get('region'):
            raise ConfigValidationError(f"{context}: Region is required for AWS Bedrock provider")
    
    def _validate_dependencies_structure(self, dependencies: Dict[str, Any], sub_teams: List[Dict[str, Any]]) -> None:
        """Validate dependencies structure."""
        team_ids = {team.get('id') for team in sub_teams}
        
        for team_id, deps in dependencies.items():
            if team_id not in team_ids:
                raise ConfigValidationError(f"Dependency key '{team_id}' not found in sub_teams")
            
            if not isinstance(deps, list):
                raise ConfigValidationError(f"Dependencies for '{team_id}' must be a list")
            
            for dep in deps:
                if dep not in team_ids:
                    raise ConfigValidationError(f"Dependency '{dep}' for team '{team_id}' not found in sub_teams")
    
    def _validate_business_logic(self, team: HierarchicalTeam) -> None:
        """
        Validate business logic constraints.
        
        Args:
            team: Hierarchical team to validate
            
        Raises:
            ConfigValidationError: If business logic validation fails
        """
        # Check for circular dependencies
        self._check_circular_dependencies(team.dependencies, team.sub_teams)
        
        # Validate unique agent IDs across all teams
        self._validate_global_agent_uniqueness(team.sub_teams)
        
        # Validate LLM configurations
        self._validate_llm_configurations(team)
    
    def _check_circular_dependencies(self, dependencies: Dict[str, List[str]], sub_teams: List[SubTeam]) -> None:
        """Check for circular dependencies in team structure."""
        if not dependencies:
            return
        
        team_ids = {team.id for team in sub_teams}
        
        def has_cycle(node: str, visited: Set[str], rec_stack: Set[str]) -> bool:
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in dependencies.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        visited: Set[str] = set()
        for team_id in team_ids:
            if team_id not in visited:
                if has_cycle(team_id, visited, set()):
                    raise ConfigValidationError(f"Circular dependency detected involving team: {team_id}")
    
    def _validate_global_agent_uniqueness(self, sub_teams: List[SubTeam]) -> None:
        """Validate that agent IDs are unique across all teams."""
        all_agent_ids: Set[str] = set()
        duplicate_ids: Set[str] = set()
        
        for team in sub_teams:
            for agent in team.agent_configs:
                if agent.agent_id in all_agent_ids:
                    duplicate_ids.add(agent.agent_id)
                all_agent_ids.add(agent.agent_id)
        
        if duplicate_ids:
            raise ConfigValidationError(f"Duplicate agent IDs found across teams: {duplicate_ids}")
    
    def _validate_llm_configurations(self, team: HierarchicalTeam) -> None:
        """Validate LLM configurations for consistency."""
        # Collect all LLM configs
        llm_configs = [team.top_supervisor_config.llm_config]
        
        for sub_team in team.sub_teams:
            llm_configs.append(sub_team.supervisor_config.llm_config)
            for agent in sub_team.agent_configs:
                llm_configs.append(agent.llm_config)
        
        # Validate each config
        for i, llm_config in enumerate(llm_configs):
            try:
                # This will trigger Pydantic validation
                LLMConfig.model_validate(llm_config.model_dump())
            except Exception as e:
                raise ConfigValidationError(f"Invalid LLM configuration at index {i}: {e}")
    
    def get_execution_order(self, team: HierarchicalTeam) -> List[str]:
        """
        Calculate the execution order based on dependencies.
        
        Args:
            team: Hierarchical team configuration
            
        Returns:
            List[str]: Team IDs in execution order
            
        Raises:
            ConfigValidationError: If dependencies cannot be resolved
        """
        if not team.dependencies:
            # No dependencies, return teams in original order
            return [sub_team.id for sub_team in team.sub_teams]
        
        # Topological sort
        in_degree = {sub_team.id: 0 for sub_team in team.sub_teams}
        
        # Calculate in-degrees
        for team_id, deps in team.dependencies.items():
            in_degree[team_id] = len(deps)
        
        # Find teams with no dependencies
        queue = [team_id for team_id, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            current = queue.pop(0)
            result.append(current)
            
            # Update in-degrees for dependent teams
            for team_id, deps in team.dependencies.items():
                if current in deps:
                    in_degree[team_id] -= 1
                    if in_degree[team_id] == 0:
                        queue.append(team_id)
        
        # Check if all teams are included (no cycles)
        if len(result) != len(team.sub_teams):
            raise ConfigValidationError("Cannot resolve team dependencies - circular dependency detected")
        
        return result
    
    def validate_config_completeness(self, team: HierarchicalTeam) -> Dict[str, List[str]]:
        """
        Validate configuration completeness and return any warnings.
        
        Args:
            team: Hierarchical team configuration
            
        Returns:
            Dict[str, List[str]]: Dictionary of validation warnings by category
        """
        warnings: Dict[str, List[str]] = {
            'missing_optional_fields': [],
            'configuration_recommendations': [],
            'potential_issues': []
        }
        
        # Check for missing optional but recommended fields
        if not team.global_config.max_execution_time:
            warnings['missing_optional_fields'].append("max_execution_time not set, using default")
        
        # Check for configuration recommendations
        total_agents = sum(len(sub_team.agent_configs) for sub_team in team.sub_teams)
        if total_agents > 10:
            warnings['configuration_recommendations'].append(
                f"Large number of agents ({total_agents}) may impact performance"
            )
        
        # Check for potential issues
        for sub_team in team.sub_teams:
            if len(sub_team.agent_configs) == 1:
                warnings['potential_issues'].append(
                    f"Team '{sub_team.name}' has only one agent - consider adding more for redundancy"
                )
        
        return warnings


# Utility functions for configuration management
def load_config_from_file(config_path: Union[str, Path]) -> HierarchicalTeam:
    """
    Convenience function to load configuration from file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        HierarchicalTeam: Loaded and validated configuration
    """
    manager = ConfigManager()
    return manager.load_config(config_path)


def validate_config_from_dict(config_data: Dict[str, Any]) -> HierarchicalTeam:
    """
    Convenience function to validate configuration from dictionary.
    
    Args:
        config_data: Configuration dictionary
        
    Returns:
        HierarchicalTeam: Validated configuration
    """
    manager = ConfigManager()
    return manager.validate_config_dict(config_data)


def save_config_to_file(team: HierarchicalTeam, config_path: Union[str, Path]) -> None:
    """
    Convenience function to save configuration to file.
    
    Args:
        team: Hierarchical team configuration
        config_path: Path where to save the configuration
    """
    manager = ConfigManager()
    manager.save_config(team, config_path)