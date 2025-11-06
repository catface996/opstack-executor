"""
Hierarchical Manager for multi-agent system.

This module provides the main management interface for hierarchical multi-agent
teams, integrating team building, execution engine, and output formatting
components to provide a unified API for creating and managing hierarchical teams.
"""

import logging
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from .data_models import (
    HierarchicalTeam,
    ExecutionContext,
    ExecutionEvent,
    ExecutionConfig,
    StandardizedOutput,
    ExecutionSummary,
    TeamResult,
    ErrorInfo,
    ExecutionMetrics
)
from .team_builder import TeamBuilder, TeamBuildError
from .execution_engine import ExecutionEngine, ExecutionSession
from .state_manager import StateManager
from .event_manager import EventManager
from .error_handler import ErrorHandler
from .env_key_manager import EnvironmentKeyManager
from .output_formatter import OutputFormatter


class HierarchicalManagerError(Exception):
    """Raised when hierarchical manager operations fail."""
    pass


class HierarchicalManager:
    """
    Main manager for hierarchical multi-agent system.
    
    This class provides the primary interface for:
    - Building hierarchical team structures from configuration
    - Executing hierarchical teams with proper coordination
    - Formatting and collecting execution results
    - Managing the complete lifecycle of hierarchical team operations
    """
    
    def __init__(
        self,
        key_manager: Optional[EnvironmentKeyManager] = None,
        state_manager: Optional[StateManager] = None,
        event_manager: Optional[EventManager] = None,
        error_handler: Optional[ErrorHandler] = None
    ):
        """
        Initialize the hierarchical manager.
        
        Args:
            key_manager: Environment key manager for API keys
            state_manager: State manager for execution state
            event_manager: Event manager for streaming events
            error_handler: Error handler for managing failures
        """
        # Initialize core components
        self.key_manager = key_manager or EnvironmentKeyManager()
        self.error_handler = error_handler or ErrorHandler()
        self.state_manager = state_manager or StateManager()
        self.event_manager = event_manager or EventManager()
        
        # Initialize dependent components
        self.team_builder = TeamBuilder(
            key_manager=self.key_manager,
            error_handler=self.error_handler
        )
        
        self.execution_engine = ExecutionEngine(
            state_manager=self.state_manager,
            event_manager=self.event_manager,
            error_handler=self.error_handler
        )
        
        self.output_formatter = OutputFormatter()
        
        # Manager state
        self._initialized = False
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    async def initialize(self) -> None:
        """Initialize the hierarchical manager and all components."""
        if self._initialized:
            return
        
        try:
            # Initialize execution engine (which will initialize its dependencies)
            await self.execution_engine.initialize()
            
            self._initialized = True
            self.logger.info("HierarchicalManager initialized successfully")
            
        except Exception as e:
            raise HierarchicalManagerError(f"Failed to initialize HierarchicalManager: {e}")
    
    async def shutdown(self) -> None:
        """Shutdown the hierarchical manager gracefully."""
        if not self._initialized:
            return
        
        try:
            # Shutdown execution engine (which will shutdown its dependencies)
            await self.execution_engine.shutdown()
            
            self._initialized = False
            self.logger.info("HierarchicalManager shutdown successfully")
            
        except Exception as e:
            self.logger.error(f"Error during HierarchicalManager shutdown: {e}")
    
    def build_hierarchy(self, team_config: Dict[str, Any]) -> HierarchicalTeam:
        """
        Build hierarchical team structure from configuration.
        
        Args:
            team_config: Dictionary containing team configuration
            
        Returns:
            HierarchicalTeam: Built hierarchical team with runtime instances
            
        Raises:
            HierarchicalManagerError: If team building fails
        """
        try:
            self.logger.info(f"Building hierarchy from config: {team_config.get('team_name', 'unnamed')}")
            
            # Validate and parse configuration
            if isinstance(team_config, dict):
                # Convert dict to HierarchicalTeam model
                config = HierarchicalTeam.model_validate(team_config)
            else:
                config = team_config
            
            # Validate team configuration
            is_valid, errors = self.team_builder.validate_team_configuration(config)
            if not is_valid:
                raise HierarchicalManagerError(f"Invalid team configuration: {errors}")
            
            # Build the hierarchical team
            built_team = self.team_builder.build_hierarchical_team(config)
            
            self.logger.info(
                f"Successfully built hierarchy '{built_team.team_name}' with "
                f"{len(built_team.sub_teams)} sub-teams"
            )
            
            return built_team
            
        except TeamBuildError as e:
            raise HierarchicalManagerError(f"Team building failed: {e}")
        except Exception as e:
            raise HierarchicalManagerError(f"Failed to build hierarchy: {e}")
    
    async def execute_team(
        self, 
        team: HierarchicalTeam, 
        context: Optional[ExecutionContext] = None
    ) -> AsyncIterator[ExecutionEvent]:
        """
        Execute hierarchical team and stream events.
        
        Args:
            team: The hierarchical team to execute
            context: Optional execution context
            
        Yields:
            ExecutionEvent: Events from the execution process
            
        Raises:
            HierarchicalManagerError: If execution fails to start
        """
        if not self._initialized:
            raise HierarchicalManagerError("HierarchicalManager not initialized")
        
        try:
            self.logger.info(f"Starting execution of team: {team.team_name}")
            
            # Create execution config from context if provided
            config = ExecutionConfig()
            if context and hasattr(context, 'config'):
                config = context.config
            
            # Start execution
            session = await self.execution_engine.start_execution(team, config)
            
            self.logger.info(f"Execution started with ID: {session.execution_id}")
            
            # Stream events from the execution
            async for event in self.execution_engine.stream_events(session.execution_id):
                yield event
                
        except Exception as e:
            raise HierarchicalManagerError(f"Failed to execute team '{team.team_name}': {e}")
    
    def format_results(self, execution_results: List[TeamResult]) -> StandardizedOutput:
        """
        Format execution results into standardized output.
        
        Args:
            execution_results: List of team execution results
            
        Returns:
            StandardizedOutput: Formatted and standardized results
            
        Raises:
            HierarchicalManagerError: If result formatting fails
        """
        try:
            self.logger.info(f"Formatting results for {len(execution_results)} teams")
            
            formatted_output = self.output_formatter.format_results(execution_results)
            
            self.logger.info(f"Successfully formatted results with execution ID: {formatted_output.execution_id}")
            
            return formatted_output
            
        except Exception as e:
            raise HierarchicalManagerError(f"Failed to format results: {e}")
    
    async def create_and_execute_team(
        self,
        team_config: Dict[str, Any],
        execution_config: Optional[ExecutionConfig] = None
    ) -> AsyncIterator[ExecutionEvent]:
        """
        Convenience method to build and execute a team in one call.
        
        Args:
            team_config: Team configuration dictionary
            execution_config: Optional execution configuration
            
        Yields:
            ExecutionEvent: Events from the execution process
            
        Raises:
            HierarchicalManagerError: If creation or execution fails
        """
        try:
            # Build the team
            team = self.build_hierarchy(team_config)
            
            # Create execution context
            context = None
            if execution_config:
                context = ExecutionContext(
                    execution_id="",  # Will be set by execution engine
                    team_id=team.team_name,
                    config=execution_config,
                    started_at=datetime.now()
                )
            
            # Execute the team
            async for event in self.execute_team(team, context):
                yield event
                
        except Exception as e:
            raise HierarchicalManagerError(f"Failed to create and execute team: {e}")
    
    async def get_execution_status(self, execution_id: str) -> Optional[str]:
        """
        Get the status of an execution.
        
        Args:
            execution_id: The execution ID to check
            
        Returns:
            Optional[str]: The execution status, or None if not found
        """
        try:
            status = await self.execution_engine.get_execution_status(execution_id)
            return status.value if status else None
        except Exception as e:
            self.logger.error(f"Failed to get execution status for {execution_id}: {e}")
            return None
    
    async def stop_execution(self, execution_id: str, graceful: bool = True) -> bool:
        """
        Stop an execution.
        
        Args:
            execution_id: The execution ID to stop
            graceful: Whether to stop gracefully
            
        Returns:
            bool: True if execution was stopped, False if not found
        """
        try:
            return await self.execution_engine.stop_execution(execution_id, graceful)
        except Exception as e:
            self.logger.error(f"Failed to stop execution {execution_id}: {e}")
            return False
    
    def get_team_statistics(self, team: HierarchicalTeam) -> Dict[str, Any]:
        """
        Get statistics about a hierarchical team.
        
        Args:
            team: The hierarchical team
            
        Returns:
            Dict[str, Any]: Team statistics
        """
        try:
            return self.team_builder.get_team_statistics(team)
        except Exception as e:
            self.logger.error(f"Failed to get team statistics: {e}")
            return {}
    
    def validate_team_config(self, team_config: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate team configuration.
        
        Args:
            team_config: Team configuration to validate
            
        Returns:
            tuple[bool, List[str]]: (is_valid, list_of_errors)
        """
        try:
            # Convert dict to HierarchicalTeam model for validation
            if isinstance(team_config, dict):
                config = HierarchicalTeam.model_validate(team_config)
            else:
                config = team_config
            
            return self.team_builder.validate_team_configuration(config)
            
        except Exception as e:
            return False, [f"Configuration validation error: {e}"]
    
    async def list_active_executions(self) -> List[str]:
        """
        List all active execution IDs.
        
        Returns:
            List[str]: List of active execution IDs
        """
        try:
            return await self.execution_engine.list_active_executions()
        except Exception as e:
            self.logger.error(f"Failed to list active executions: {e}")
            return []
    
    async def get_manager_stats(self) -> Dict[str, Any]:
        """
        Get hierarchical manager statistics.
        
        Returns:
            Dict[str, Any]: Manager statistics
        """
        try:
            engine_stats = await self.execution_engine.get_stats()
            
            return {
                "initialized": self._initialized,
                "components": {
                    "team_builder": "initialized",
                    "execution_engine": engine_stats,
                    "output_formatter": "initialized",
                    "key_manager": "initialized",
                    "error_handler": "initialized"
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get manager stats: {e}")
            return {
                "initialized": self._initialized,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# Utility functions for common operations
async def create_hierarchical_manager(
    key_manager: Optional[EnvironmentKeyManager] = None,
    state_manager: Optional[StateManager] = None,
    event_manager: Optional[EventManager] = None,
    error_handler: Optional[ErrorHandler] = None
) -> HierarchicalManager:
    """
    Create and initialize a HierarchicalManager instance.
    
    Args:
        key_manager: Optional environment key manager
        state_manager: Optional state manager
        event_manager: Optional event manager
        error_handler: Optional error handler
        
    Returns:
        HierarchicalManager: Initialized hierarchical manager
    """
    manager = HierarchicalManager(key_manager, state_manager, event_manager, error_handler)
    await manager.initialize()
    return manager


def build_team_from_config(team_config: Dict[str, Any]) -> HierarchicalTeam:
    """
    Convenience function to build a team from configuration.
    
    Args:
        team_config: Team configuration dictionary
        
    Returns:
        HierarchicalTeam: Built hierarchical team
    """
    manager = HierarchicalManager()
    return manager.build_hierarchy(team_config)