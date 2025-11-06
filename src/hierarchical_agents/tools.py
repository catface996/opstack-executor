"""
Tool integration framework for hierarchical multi-agent system.

This module provides a flexible framework for integrating various tools
that agents can use to perform tasks. It includes:
- Base tool interface and abstract classes
- Tool registry for dynamic loading and management
- Built-in tools for common operations (search, document processing)
- Error handling and isolation mechanisms
- Tool chaining capabilities
"""

import asyncio
import json
import logging
import traceback
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, Union, Callable
from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


class ToolError(Exception):
    """Base exception for tool-related errors."""
    pass


class ToolExecutionError(ToolError):
    """Exception raised when tool execution fails."""
    pass


class ToolNotFoundError(ToolError):
    """Exception raised when a requested tool is not found."""
    pass


class ToolRegistrationError(ToolError):
    """Exception raised when tool registration fails."""
    pass


class ToolInput(BaseModel):
    """Input parameters for tool execution."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="allow"  # Allow additional fields for flexible tool inputs
    )


class ToolOutput(BaseModel):
    """Output from tool execution."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    success: bool = Field(..., description="Whether the tool execution was successful")
    result: Any = Field(None, description="Tool execution result")
    error: Optional[str] = Field(None, description="Error message if execution failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    execution_time: float = Field(0.0, description="Execution time in seconds")
    timestamp: datetime = Field(default_factory=datetime.now, description="Execution timestamp")


class ToolMetadata(BaseModel):
    """Metadata for tool registration and discovery."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    version: str = Field("1.0.0", description="Tool version")
    author: Optional[str] = Field(None, description="Tool author")
    tags: List[str] = Field(default_factory=list, description="Tool tags for categorization")
    input_schema: Optional[Dict[str, Any]] = Field(None, description="Input schema")
    output_schema: Optional[Dict[str, Any]] = Field(None, description="Output schema")
    requires_auth: bool = Field(False, description="Whether tool requires authentication")
    is_async: bool = Field(False, description="Whether tool supports async execution")


class BaseTool(ABC):
    """Abstract base class for all tools in the system."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the tool with optional configuration."""
        self.config = config or {}
        self._metadata: Optional[ToolMetadata] = None
        self._logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
    
    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata:
        """Return tool metadata."""
        pass
    
    @abstractmethod
    def execute(self, input_data: ToolInput) -> ToolOutput:
        """Execute the tool with given input data."""
        pass
    
    async def execute_async(self, input_data: ToolInput) -> ToolOutput:
        """Execute the tool asynchronously. Default implementation runs sync version in executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.execute, input_data)
    
    def validate_input(self, input_data: ToolInput) -> bool:
        """Validate input data against tool requirements."""
        # Default implementation - can be overridden by specific tools
        return True
    
    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema for documentation and validation."""
        return {
            "name": self.metadata.name,
            "description": self.metadata.description,
            "input_schema": self.metadata.input_schema,
            "output_schema": self.metadata.output_schema,
            "requires_auth": self.metadata.requires_auth,
            "is_async": self.metadata.is_async,
        }
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.metadata.name})"
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.metadata.name}', version='{self.metadata.version}')"


class ToolRegistry:
    """Registry for managing and discovering tools."""
    
    def __init__(self):
        """Initialize the tool registry."""
        self._tools: Dict[str, Type[BaseTool]] = {}
        self._instances: Dict[str, BaseTool] = {}
        self._logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
    
    def register(self, tool_class: Type[BaseTool], name: Optional[str] = None) -> None:
        """Register a tool class in the registry."""
        try:
            # Create temporary instance to get metadata
            temp_instance = tool_class()
            tool_name = name or temp_instance.metadata.name
            
            if tool_name in self._tools:
                self._logger.warning(f"Tool '{tool_name}' is already registered. Overwriting.")
            
            self._tools[tool_name] = tool_class
            self._logger.info(f"Registered tool: {tool_name}")
            
        except Exception as e:
            raise ToolRegistrationError(f"Failed to register tool {tool_class.__name__}: {str(e)}")
    
    def unregister(self, name: str) -> None:
        """Unregister a tool from the registry."""
        if name in self._tools:
            del self._tools[name]
            if name in self._instances:
                del self._instances[name]
            self._logger.info(f"Unregistered tool: {name}")
        else:
            raise ToolNotFoundError(f"Tool '{name}' not found in registry")
    
    def get_tool(self, name: str, config: Optional[Dict[str, Any]] = None) -> BaseTool:
        """Get a tool instance by name."""
        if name not in self._tools:
            raise ToolNotFoundError(f"Tool '{name}' not found in registry")
        
        # Create new instance with config or return cached instance
        cache_key = f"{name}_{hash(str(config))}" if config else name
        
        if cache_key not in self._instances:
            tool_class = self._tools[name]
            self._instances[cache_key] = tool_class(config)
        
        return self._instances[cache_key]
    
    def list_tools(self) -> List[str]:
        """List all registered tool names."""
        return list(self._tools.keys())
    
    def get_tool_metadata(self, name: str) -> ToolMetadata:
        """Get metadata for a specific tool."""
        if name not in self._tools:
            raise ToolNotFoundError(f"Tool '{name}' not found in registry")
        
        temp_instance = self._tools[name]()
        return temp_instance.metadata
    
    def search_tools(self, tags: Optional[List[str]] = None, 
                    description_contains: Optional[str] = None) -> List[str]:
        """Search for tools by tags or description."""
        matching_tools = []
        
        for name in self._tools:
            try:
                metadata = self.get_tool_metadata(name)
                
                # Check tags
                if tags and not any(tag in metadata.tags for tag in tags):
                    continue
                
                # Check description
                if description_contains and description_contains.lower() not in metadata.description.lower():
                    continue
                
                matching_tools.append(name)
                
            except Exception as e:
                self._logger.warning(f"Error checking metadata for tool '{name}': {e}")
        
        return matching_tools
    
    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
        self._instances.clear()
        self._logger.info("Cleared all tools from registry")


class ToolExecutor:
    """Executor for running tools with error handling and isolation."""
    
    def __init__(self, registry: ToolRegistry):
        """Initialize the tool executor."""
        self.registry = registry
        self._logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
    
    def execute_tool(self, tool_name: str, input_data: ToolInput, 
                    config: Optional[Dict[str, Any]] = None) -> ToolOutput:
        """Execute a tool with error handling and isolation."""
        start_time = datetime.now()
        
        try:
            # Get tool instance
            tool = self.registry.get_tool(tool_name, config)
            
            # Validate input
            if not tool.validate_input(input_data):
                return ToolOutput(
                    success=False,
                    error=f"Invalid input for tool '{tool_name}'",
                    execution_time=0.0,
                    timestamp=start_time
                )
            
            # Execute tool
            self._logger.info(f"Executing tool: {tool_name}")
            result = tool.execute(input_data)
            
            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            result.execution_time = execution_time
            
            self._logger.info(f"Tool '{tool_name}' executed successfully in {execution_time:.2f}s")
            return result
            
        except ToolNotFoundError:
            return ToolOutput(
                success=False,
                error=f"Tool '{tool_name}' not found",
                execution_time=0.0,
                timestamp=start_time
            )
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_msg = f"Tool execution failed: {str(e)}"
            self._logger.error(f"Error executing tool '{tool_name}': {error_msg}")
            self._logger.debug(f"Tool execution traceback: {traceback.format_exc()}")
            
            return ToolOutput(
                success=False,
                error=error_msg,
                execution_time=execution_time,
                timestamp=start_time,
                metadata={"traceback": traceback.format_exc()}
            )
    
    async def execute_tool_async(self, tool_name: str, input_data: ToolInput,
                                config: Optional[Dict[str, Any]] = None) -> ToolOutput:
        """Execute a tool asynchronously with error handling."""
        start_time = datetime.now()
        
        try:
            # Get tool instance
            tool = self.registry.get_tool(tool_name, config)
            
            # Validate input
            if not tool.validate_input(input_data):
                return ToolOutput(
                    success=False,
                    error=f"Invalid input for tool '{tool_name}'",
                    execution_time=0.0,
                    timestamp=start_time
                )
            
            # Execute tool asynchronously
            self._logger.info(f"Executing tool asynchronously: {tool_name}")
            result = await tool.execute_async(input_data)
            
            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            result.execution_time = execution_time
            
            self._logger.info(f"Tool '{tool_name}' executed successfully in {execution_time:.2f}s")
            return result
            
        except ToolNotFoundError:
            return ToolOutput(
                success=False,
                error=f"Tool '{tool_name}' not found",
                execution_time=0.0,
                timestamp=start_time
            )
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_msg = f"Tool execution failed: {str(e)}"
            self._logger.error(f"Error executing tool '{tool_name}': {error_msg}")
            self._logger.debug(f"Tool execution traceback: {traceback.format_exc()}")
            
            return ToolOutput(
                success=False,
                error=error_msg,
                execution_time=execution_time,
                timestamp=start_time,
                metadata={"traceback": traceback.format_exc()}
            )
    
    def execute_tool_chain(self, chain: List[Dict[str, Any]]) -> List[ToolOutput]:
        """Execute a chain of tools, passing output from one to the next."""
        results = []
        previous_output = None
        
        for step in chain:
            tool_name = step.get("tool")
            input_data = step.get("input", {})
            config = step.get("config")
            
            if not tool_name:
                results.append(ToolOutput(
                    success=False,
                    error="Tool name not specified in chain step"
                ))
                break
            
            # Use previous output as input if specified
            if step.get("use_previous_output", False) and previous_output:
                if isinstance(previous_output.result, dict):
                    input_data.update(previous_output.result)
                else:
                    input_data["previous_result"] = previous_output.result
            
            # Execute tool
            tool_input = ToolInput(**input_data)
            result = self.execute_tool(tool_name, tool_input, config)
            results.append(result)
            
            # Stop chain if tool failed and stop_on_error is True
            if not result.success and step.get("stop_on_error", True):
                break
            
            previous_output = result
        
        return results


# Global tool registry instance
default_registry = ToolRegistry()
default_executor = ToolExecutor(default_registry)


def register_tool(tool_class: Type[BaseTool], name: Optional[str] = None) -> None:
    """Register a tool in the default registry."""
    default_registry.register(tool_class, name)


def get_tool(name: str, config: Optional[Dict[str, Any]] = None) -> BaseTool:
    """Get a tool from the default registry."""
    return default_registry.get_tool(name, config)


def execute_tool(tool_name: str, input_data: Union[Dict[str, Any], ToolInput],
                config: Optional[Dict[str, Any]] = None) -> ToolOutput:
    """Execute a tool using the default executor."""
    if isinstance(input_data, dict):
        input_data = ToolInput(**input_data)
    return default_executor.execute_tool(tool_name, input_data, config)


async def execute_tool_async(tool_name: str, input_data: Union[Dict[str, Any], ToolInput],
                            config: Optional[Dict[str, Any]] = None) -> ToolOutput:
    """Execute a tool asynchronously using the default executor."""
    if isinstance(input_data, dict):
        input_data = ToolInput(**input_data)
    return await default_executor.execute_tool_async(tool_name, input_data, config)


def list_tools() -> List[str]:
    """List all registered tools."""
    return default_registry.list_tools()


def search_tools(tags: Optional[List[str]] = None, 
                description_contains: Optional[str] = None) -> List[str]:
    """Search for tools by tags or description."""
    return default_registry.search_tools(tags, description_contains)