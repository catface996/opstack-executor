"""
Agent implementations for the hierarchical multi-agent system.

This module provides the core agent classes including WorkerAgent and SupervisorAgent.
Agents integrate with LLM providers, tools, and error handling to execute tasks
within the hierarchical team structure.
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from abc import ABC, abstractmethod

from .data_models import (
    AgentConfig, SupervisorConfig, LLMConfig, AgentResult,
    ExecutionEvent, ErrorInfo
)
from .env_key_manager import EnvironmentKeyManager, EnvironmentKeyError
from .llm_providers import LLMProviderFactory, LLMProviderError
from .tools import ToolExecutor, ToolRegistry, ToolInput, ToolOutput, ToolError
from .error_handler import ErrorHandler, ErrorContext, ErrorCategory
from .performance_monitor import record_agent_metrics

logger = logging.getLogger(__name__)


class AgentError(Exception):
    """Base exception for agent-related errors."""
    pass


class AgentInitializationError(AgentError):
    """Raised when agent initialization fails."""
    pass


class AgentExecutionError(AgentError):
    """Raised when agent execution fails."""
    pass


class BaseAgent(ABC):
    """Abstract base class for all agents in the system."""
    
    def __init__(
        self,
        config: Union[AgentConfig, SupervisorConfig],
        key_manager: Optional[EnvironmentKeyManager] = None,
        error_handler: Optional[ErrorHandler] = None
    ):
        """
        Initialize the base agent.
        
        Args:
            config: Agent configuration
            key_manager: Key manager for API keys
            error_handler: Error handler for managing failures
        """
        self.config = config
        self.key_manager = key_manager or EnvironmentKeyManager()
        self.error_handler = error_handler or ErrorHandler()
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        
        # Initialize LLM client
        self.llm_client = None
        self._initialize_llm_client()
        
        # Execution state
        self.execution_id: Optional[str] = None
        self.is_executing = False
        self.execution_start_time: Optional[datetime] = None
        self.execution_events: List[ExecutionEvent] = []
    
    def _initialize_llm_client(self) -> None:
        """Initialize the LLM client based on configuration."""
        try:
            # Get API key from environment
            api_key = self.key_manager.get_api_key(self.config.llm_config.provider)
            
            # Create LLM client
            factory = LLMProviderFactory()
            self.llm_client = factory.create_client(self.config.llm_config, api_key)
            
            self.logger.info(
                f"Initialized LLM client for {self.config.llm_config.provider} "
                f"with model {self.config.llm_config.model}"
            )
            
        except (EnvironmentKeyError, LLMProviderError) as e:
            raise AgentInitializationError(f"Failed to initialize LLM client: {e}")
    
    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """Execute the agent's primary function."""
        pass
    
    def _create_execution_event(
        self,
        event_type: str,
        content: Optional[str] = None,
        action: Optional[str] = None,
        status: Optional[str] = None,
        **kwargs
    ) -> ExecutionEvent:
        """Create an execution event."""
        agent_id = getattr(self.config, 'agent_id', None)
        agent_name = getattr(self.config, 'agent_name', self.__class__.__name__)
        
        return ExecutionEvent(
            timestamp=datetime.now(),
            event_type=event_type,
            source_type="agent",
            execution_id=self.execution_id or "unknown",
            agent_id=agent_id,
            agent_name=agent_name,
            content=content,
            action=action,
            status=status,
            **kwargs
        )
    
    def _emit_event(self, event: ExecutionEvent) -> None:
        """Emit an execution event."""
        self.execution_events.append(event)
        self.logger.debug(f"Event emitted: {event.event_type} - {event.content}")
    
    def get_execution_events(self) -> List[ExecutionEvent]:
        """Get all execution events for this agent."""
        return self.execution_events.copy()
    
    def clear_execution_events(self) -> None:
        """Clear execution events."""
        self.execution_events.clear()


class WorkerAgent(BaseAgent):
    """
    Worker agent that executes specific tasks using LLM and tools.
    
    WorkerAgent is responsible for:
    - Executing tasks based on its configuration
    - Using tools to perform operations
    - Handling errors and retries
    - Providing execution feedback
    """
    
    def __init__(
        self,
        config: AgentConfig,
        key_manager: Optional[EnvironmentKeyManager] = None,
        error_handler: Optional[ErrorHandler] = None,
        tool_registry: Optional[ToolRegistry] = None
    ):
        """
        Initialize the worker agent.
        
        Args:
            config: Agent configuration
            key_manager: Key manager for API keys
            error_handler: Error handler for managing failures
            tool_registry: Tool registry for accessing tools
        """
        super().__init__(config, key_manager, error_handler)
        self.config: AgentConfig = config  # Type hint for better IDE support
        
        # Initialize tool executor
        self.tool_registry = tool_registry or ToolRegistry()
        self.tool_executor = ToolExecutor(self.tool_registry)
        
        self.logger.info(f"Initialized WorkerAgent: {self.config.agent_name}")
    
    def execute(
        self,
        execution_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """
        Execute the agent's task.
        
        This method automatically determines whether to use tools based on the agent's configuration.
        If tools are configured, it will use the enhanced tool integration. Otherwise, it will
        execute the task directly.
        
        Args:
            execution_id: Optional execution ID for tracking
            context: Optional context data for execution
            
        Returns:
            AgentResult: Result of the agent execution
        """
        # If tools are configured, use the enhanced tool execution
        if self.config.tools:
            return self.execute_with_tools(execution_id, context)
        
        # Otherwise, execute without tools
        self.execution_id = execution_id or f"exec_{datetime.now().timestamp()}"
        self.is_executing = True
        self.execution_start_time = datetime.now()
        
        # Emit start event
        start_event = self._create_execution_event(
            event_type="agent_started",
            action="started",
            status="running",
            content=f"Starting execution of {self.config.agent_name}"
        )
        self._emit_event(start_event)
        
        try:
            # Create error context
            error_context = ErrorContext(
                execution_id=self.execution_id,
                agent_id=self.config.agent_id,
                operation="agent_execution",
                metadata={"agent_name": self.config.agent_name}
            )
            
            # Execute with error handling
            result = self.error_handler.handle_error(
                Exception("placeholder"),  # This won't be used in normal flow
                error_context,
                self._execute_task
            )
            
            # If we get here without exception, call _execute_task directly
            if result is None:
                result = self._execute_task()
            
            # Emit completion event
            completion_event = self._create_execution_event(
                event_type="agent_completed",
                action="completed",
                status="completed",
                content=f"Completed execution of {self.config.agent_name}",
                result=str(result)
            )
            self._emit_event(completion_event)
            
            # Record performance metrics
            execution_time = (datetime.now() - self.execution_start_time).total_seconds()
            record_agent_metrics(self.config.agent_id, "success", execution_time)
            
            return result
            
        except Exception as e:
            # Emit error event
            error_event = self._create_execution_event(
                event_type="agent_error",
                action="error",
                status="failed",
                content=f"Error in {self.config.agent_name}: {str(e)}"
            )
            self._emit_event(error_event)
            
            # Handle error through error handler
            error_context = ErrorContext(
                execution_id=self.execution_id,
                agent_id=self.config.agent_id,
                operation="agent_execution",
                metadata={"agent_name": self.config.agent_name, "error": str(e)}
            )
            
            # Record performance metrics for failure
            execution_time = (datetime.now() - self.execution_start_time).total_seconds()
            record_agent_metrics(self.config.agent_id, "failure", execution_time)
            
            return self.error_handler.handle_error(e, error_context)
            
        finally:
            self.is_executing = False
    
    def _execute_task(self) -> AgentResult:
        """Execute the core task logic."""
        try:
            # Prepare messages for LLM
            messages = [
                {"role": "system", "content": self.config.system_prompt},
                {"role": "user", "content": self.config.user_prompt}
            ]
            
            # Execute LLM call
            self.logger.info(f"Executing LLM call for {self.config.agent_name}")
            
            # Emit progress event
            progress_event = self._create_execution_event(
                event_type="agent_progress",
                action="llm_call",
                status="running",
                content="Executing LLM call",
                progress=50
            )
            self._emit_event(progress_event)
            
            # Make LLM call
            response = self.llm_client.invoke(messages)
            
            # Extract content from response
            if hasattr(response, 'content'):
                result_content = response.content
            elif isinstance(response, dict) and 'content' in response:
                result_content = response['content']
            else:
                result_content = str(response)
            
            # Create result
            result = {
                "agent_id": self.config.agent_id,
                "agent_name": self.config.agent_name,
                "status": "completed",
                "output": result_content,
                "execution_time": (datetime.now() - self.execution_start_time).total_seconds(),
                "tools_used": [],
                "metadata": {
                    "model": self.config.llm_config.model,
                    "provider": self.config.llm_config.provider,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            self.logger.info(f"Successfully executed task for {self.config.agent_name}")
            return result
            
        except Exception as e:
            self.logger.error(f"Task execution failed for {self.config.agent_name}: {e}")
            raise AgentExecutionError(f"Task execution failed: {e}")
    
    def execute_with_tools(
        self,
        execution_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """
        Execute the agent's task with intelligent tool usage.
        
        This method integrates tools into the agent's execution flow by:
        1. Analyzing the task to determine which tools are needed
        2. Executing tools in the appropriate order
        3. Using tool results to inform the LLM's response
        4. Handling tool failures gracefully with fallback strategies
        
        Args:
            execution_id: Optional execution ID for tracking
            context: Optional context data for execution
            
        Returns:
            AgentResult: Result of the agent execution including tool usage
        """
        self.execution_id = execution_id or f"exec_{datetime.now().timestamp()}"
        self.is_executing = True
        self.execution_start_time = datetime.now()
        
        # Emit start event
        start_event = self._create_execution_event(
            event_type="agent_started",
            action="started",
            status="running",
            content=f"Starting execution with tools: {self.config.agent_name}"
        )
        self._emit_event(start_event)
        
        tools_used = []
        tool_results = {}
        
        try:
            # Step 1: Determine which tools to use based on task analysis
            selected_tools = self._select_tools_for_task(context)
            
            # Step 2: Execute tools in order and collect results
            if selected_tools:
                tool_results = self._execute_tool_chain(selected_tools, context, tools_used)
            
            # Step 3: Execute main task with tool results as context
            result = self._execute_task_with_tool_context(tool_results, context)
            
            # Add tool information to result
            result["tools_used"] = tools_used
            result["tool_results"] = tool_results
            
            # Emit completion event
            completion_event = self._create_execution_event(
                event_type="agent_completed",
                action="completed",
                status="completed",
                content=f"Completed execution with tools: {self.config.agent_name}",
                result=str(result)
            )
            self._emit_event(completion_event)
            
            return result
            
        except Exception as e:
            # Emit error event
            error_event = self._create_execution_event(
                event_type="agent_error",
                action="error",
                status="failed",
                content=f"Error in {self.config.agent_name}: {str(e)}"
            )
            self._emit_event(error_event)
            
            # Handle error through error handler with fallback
            error_context = ErrorContext(
                execution_id=self.execution_id,
                agent_id=self.config.agent_id,
                operation="agent_execution_with_tools",
                metadata={
                    "agent_name": self.config.agent_name, 
                    "error": str(e),
                    "tools_attempted": [t["tool_name"] for t in tools_used]
                }
            )
            
            # Try to provide partial results if some tools succeeded
            if tools_used and any(t.get("success", False) for t in tools_used):
                self.logger.warning(f"Partial tool execution for {self.config.agent_name}, attempting fallback")
                try:
                    fallback_result = self._execute_task_with_tool_context(tool_results, context)
                    fallback_result["tools_used"] = tools_used
                    fallback_result["status"] = "partial_success"
                    fallback_result["error"] = str(e)
                    return fallback_result
                except Exception:
                    pass
            
            raise AgentExecutionError(f"Agent execution with tools failed: {e}")
            
        finally:
            self.is_executing = False
    
    def _select_tools_for_task(self, context: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Intelligently select which tools to use based on the task and context.
        
        Args:
            context: Optional context data
            
        Returns:
            List[str]: List of tool names to use
        """
        if not self.config.tools:
            return []
        
        # Get available tools from registry
        available_tools = self.tool_registry.list_tools()
        configured_tools = [tool for tool in self.config.tools if tool in available_tools]
        
        if not configured_tools:
            self.logger.warning(f"No configured tools available for {self.config.agent_name}")
            return []
        
        # Simple heuristic-based tool selection
        # In a more advanced implementation, this could use LLM to decide
        task_text = (self.config.user_prompt + " " + self.config.system_prompt).lower()
        selected_tools = []
        
        # Search tools for information gathering tasks
        if any(keyword in task_text for keyword in ["search", "find", "collect", "gather", "research"]):
            search_tools = [t for t in configured_tools if t in ["tavily_search", "web_scraper"]]
            selected_tools.extend(search_tools)
        
        # Data processing tools for analysis tasks
        if any(keyword in task_text for keyword in ["analyze", "process", "data", "statistics"]):
            data_tools = [t for t in configured_tools if t in ["data_processor"]]
            selected_tools.extend(data_tools)
        
        # Writing tools for content creation tasks
        if any(keyword in task_text for keyword in ["write", "create", "document", "report", "format"]):
            writing_tools = [t for t in configured_tools if t in ["document_writer", "editor"]]
            selected_tools.extend(writing_tools)
        
        # If no specific tools selected, use all configured tools
        if not selected_tools:
            selected_tools = configured_tools
        
        # Remove duplicates while preserving order
        seen = set()
        unique_tools = []
        for tool in selected_tools:
            if tool not in seen:
                seen.add(tool)
                unique_tools.append(tool)
        
        self.logger.info(f"Selected tools for {self.config.agent_name}: {unique_tools}")
        return unique_tools
    
    def _execute_tool_chain(
        self, 
        tool_names: List[str], 
        context: Optional[Dict[str, Any]], 
        tools_used: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Execute a chain of tools and collect their results.
        
        Args:
            tool_names: List of tool names to execute
            context: Execution context
            tools_used: List to append tool execution info to
            
        Returns:
            Dict[str, Any]: Combined tool results
        """
        tool_results = {}
        previous_result = None
        
        for tool_name in tool_names:
            try:
                # Emit tool usage event
                tool_event = self._create_execution_event(
                    event_type="agent_tool_usage",
                    action="tool_execution",
                    status="running",
                    content=f"Using tool: {tool_name}"
                )
                self._emit_event(tool_event)
                
                # Prepare tool input based on task and previous results
                tool_input = self._prepare_tool_input(tool_name, context, previous_result)
                
                # Execute tool with error handling
                tool_result = self._execute_single_tool(tool_name, tool_input)
                
                # Record tool usage
                tool_usage_info = {
                    "tool_name": tool_name,
                    "success": tool_result.success,
                    "execution_time": tool_result.execution_time,
                    "timestamp": tool_result.timestamp.isoformat()
                }
                
                if tool_result.success:
                    tool_usage_info["result"] = tool_result.result
                    tool_results[tool_name] = tool_result.result
                    previous_result = tool_result.result
                    
                    # Emit success event
                    success_event = self._create_execution_event(
                        event_type="agent_tool_success",
                        action="tool_completed",
                        status="completed",
                        content=f"Tool {tool_name} completed successfully"
                    )
                    self._emit_event(success_event)
                    
                else:
                    tool_usage_info["error"] = tool_result.error
                    self.logger.warning(f"Tool {tool_name} failed: {tool_result.error}")
                    
                    # Emit failure event
                    failure_event = self._create_execution_event(
                        event_type="agent_tool_failure",
                        action="tool_failed",
                        status="failed",
                        content=f"Tool {tool_name} failed: {tool_result.error}"
                    )
                    self._emit_event(failure_event)
                    
                    # Apply fallback strategy
                    fallback_result = self._apply_tool_fallback(tool_name, tool_result.error, context)
                    if fallback_result:
                        tool_results[tool_name] = fallback_result
                        tool_usage_info["fallback_applied"] = True
                        tool_usage_info["fallback_result"] = fallback_result
                
                tools_used.append(tool_usage_info)
                
            except Exception as e:
                self.logger.error(f"Unexpected error executing tool {tool_name}: {e}")
                tools_used.append({
                    "tool_name": tool_name,
                    "success": False,
                    "error": f"Unexpected error: {str(e)}",
                    "execution_time": 0.0
                })
        
        return tool_results
    
    def _prepare_tool_input(
        self, 
        tool_name: str, 
        context: Optional[Dict[str, Any]], 
        previous_result: Any
    ) -> ToolInput:
        """
        Prepare input for a specific tool based on the task and context.
        
        Args:
            tool_name: Name of the tool
            context: Execution context
            previous_result: Result from previous tool in chain
            
        Returns:
            ToolInput: Prepared input for the tool
        """
        input_data = {}
        
        # Extract relevant information from prompts for tool input
        task_text = self.config.user_prompt
        
        if tool_name == "tavily_search":
            # Extract search query from task
            input_data["query"] = self._extract_search_query(task_text)
            input_data["max_results"] = 5
            
        elif tool_name == "web_scraper":
            # Use URLs from previous search results or context
            if previous_result and isinstance(previous_result, dict):
                results = previous_result.get("results", [])
                if results and isinstance(results, list) and len(results) > 0:
                    input_data["url"] = results[0].get("url", "https://example.com")
                else:
                    input_data["url"] = "https://example.com"
            else:
                input_data["url"] = "https://example.com"
            input_data["extract_text"] = True
            input_data["max_length"] = 5000
            
        elif tool_name == "data_processor":
            # Use data from previous results or context
            if previous_result:
                input_data["data"] = previous_result
                input_data["operation"] = "analyze"
            else:
                input_data["data"] = task_text
                input_data["operation"] = "analyze"
            
        elif tool_name == "document_writer":
            # Prepare document content
            content = task_text
            if previous_result:
                if isinstance(previous_result, dict):
                    content += f"\n\nBased on analysis: {previous_result}"
                else:
                    content += f"\n\nBased on data: {str(previous_result)}"
            
            input_data["content"] = content
            input_data["title"] = f"Report by {self.config.agent_name}"
            input_data["format"] = "markdown"
            
        elif tool_name == "editor":
            # Prepare text for editing
            text_to_edit = task_text
            if previous_result and isinstance(previous_result, str):
                text_to_edit = previous_result
            elif previous_result and isinstance(previous_result, dict):
                text_to_edit = str(previous_result)
            
            input_data["text"] = text_to_edit
            input_data["operation"] = "format"
            input_data["parameters"] = {"remove_extra_whitespace": True, "fix_line_breaks": True}
        
        # Add context data if available
        if context:
            input_data.update({k: v for k, v in context.items() if k not in input_data})
        
        return ToolInput(**input_data)
    
    def _extract_search_query(self, task_text: str) -> str:
        """
        Extract a search query from the task text.
        
        Args:
            task_text: The task description
            
        Returns:
            str: Extracted search query
        """
        # Simple extraction - look for key phrases
        task_lower = task_text.lower()
        
        # Look for explicit search terms
        search_patterns = [
            r"search for (.+?)(?:\.|$)",
            r"find information about (.+?)(?:\.|$)",
            r"research (.+?)(?:\.|$)",
            r"collect data on (.+?)(?:\.|$)"
        ]
        
        for pattern in search_patterns:
            match = re.search(pattern, task_lower)
            if match:
                return match.group(1).strip()
        
        # Fallback: extract key terms from the task
        # Remove common words and extract meaningful terms
        words = re.findall(r'\b\w{3,}\b', task_text)
        stop_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'who', 'boy', 'did', 'she', 'use', 'way', 'will', 'with'}
        meaningful_words = [w for w in words if w.lower() not in stop_words]
        
        if meaningful_words:
            return " ".join(meaningful_words[:5])  # Use first 5 meaningful words
        
        return task_text[:100]  # Fallback to first 100 characters
    
    def _execute_single_tool(self, tool_name: str, tool_input: ToolInput) -> ToolOutput:
        """
        Execute a single tool with error handling.
        
        Args:
            tool_name: Name of the tool to execute
            tool_input: Input for the tool
            
        Returns:
            ToolOutput: Result of tool execution
        """
        try:
            return self.tool_executor.execute_tool(tool_name, tool_input)
        except ToolError as e:
            return ToolOutput(
                success=False,
                error=f"Tool error: {str(e)}",
                execution_time=0.0
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                error=f"Unexpected error: {str(e)}",
                execution_time=0.0
            )
    
    def _apply_tool_fallback(
        self, 
        tool_name: str, 
        error: str, 
        context: Optional[Dict[str, Any]]
    ) -> Optional[Any]:
        """
        Apply fallback strategy when a tool fails.
        
        Args:
            tool_name: Name of the failed tool
            error: Error message from the tool
            context: Execution context
            
        Returns:
            Optional[Any]: Fallback result if available
        """
        self.logger.info(f"Applying fallback for failed tool: {tool_name}")
        
        # Simple fallback strategies
        if tool_name == "tavily_search":
            # Fallback: return mock search results
            return {
                "results": [
                    {
                        "title": "Fallback Search Result",
                        "url": "https://example.com/fallback",
                        "snippet": "This is a fallback result when search tool failed.",
                        "score": 0.5
                    }
                ],
                "query": "fallback query",
                "total_results": 1,
                "fallback": True
            }
        
        elif tool_name == "web_scraper":
            # Fallback: return basic content
            return {
                "content": "Fallback content when web scraping failed.",
                "title": "Fallback Content",
                "metadata": {"fallback": True}
            }
        
        elif tool_name == "data_processor":
            # Fallback: return basic analysis
            return {
                "result": {"analysis": "Basic fallback analysis", "fallback": True},
                "statistics": {"fallback": True},
                "operation": "fallback_analyze"
            }
        
        # No fallback available
        return None
    
    def _execute_task_with_tool_context(
        self, 
        tool_results: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """
        Execute the main task with tool results as additional context.
        
        Args:
            tool_results: Results from tool execution
            context: Additional context data
            
        Returns:
            AgentResult: Result of the agent execution
        """
        try:
            # Prepare enhanced prompt with tool results
            enhanced_prompt = self._create_enhanced_prompt(tool_results, context)
            
            # Prepare messages for LLM
            messages = [
                {"role": "system", "content": self.config.system_prompt},
                {"role": "user", "content": enhanced_prompt}
            ]
            
            # Execute LLM call
            self.logger.info(f"Executing LLM call with tool context for {self.config.agent_name}")
            
            # Emit progress event
            progress_event = self._create_execution_event(
                event_type="agent_progress",
                action="llm_call_with_tools",
                status="running",
                content="Executing LLM call with tool results",
                progress=75
            )
            self._emit_event(progress_event)
            
            # Make LLM call
            response = self.llm_client.invoke(messages)
            
            # Extract content from response
            if hasattr(response, 'content'):
                result_content = response.content
            elif isinstance(response, dict) and 'content' in response:
                result_content = response['content']
            else:
                result_content = str(response)
            
            # Create enhanced result
            result = {
                "agent_id": self.config.agent_id,
                "agent_name": self.config.agent_name,
                "status": "completed",
                "output": result_content,
                "execution_time": (datetime.now() - self.execution_start_time).total_seconds(),
                "tools_used": [],  # Will be populated by caller
                "tool_results": tool_results,
                "enhanced_with_tools": bool(tool_results),
                "metadata": {
                    "model": self.config.llm_config.model,
                    "provider": self.config.llm_config.provider,
                    "timestamp": datetime.now().isoformat(),
                    "tools_count": len(tool_results)
                }
            }
            
            self.logger.info(f"Successfully executed task with tools for {self.config.agent_name}")
            return result
            
        except Exception as e:
            self.logger.error(f"Task execution with tools failed for {self.config.agent_name}: {e}")
            raise AgentExecutionError(f"Task execution with tools failed: {e}")
    
    def _create_enhanced_prompt(
        self, 
        tool_results: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create an enhanced prompt that includes tool results.
        
        Args:
            tool_results: Results from tool execution
            context: Additional context data
            
        Returns:
            str: Enhanced prompt with tool results
        """
        prompt_parts = [self.config.user_prompt]
        
        if tool_results:
            prompt_parts.append("\n\n--- Tool Results ---")
            
            for tool_name, result in tool_results.items():
                prompt_parts.append(f"\n{tool_name.upper()} RESULTS:")
                
                if isinstance(result, dict):
                    # Format dictionary results nicely
                    for key, value in result.items():
                        if key == "results" and isinstance(value, list):
                            # Special formatting for search results
                            prompt_parts.append(f"  {key}:")
                            for i, item in enumerate(value[:3], 1):  # Show first 3 results
                                if isinstance(item, dict):
                                    title = item.get("title", "No title")
                                    snippet = item.get("snippet", "No description")
                                    prompt_parts.append(f"    {i}. {title}: {snippet}")
                        else:
                            prompt_parts.append(f"  {key}: {str(value)[:200]}...")
                else:
                    prompt_parts.append(f"  {str(result)[:500]}...")
        
        if context:
            prompt_parts.append("\n\n--- Additional Context ---")
            for key, value in context.items():
                prompt_parts.append(f"{key}: {str(value)[:200]}...")
        
        prompt_parts.append("\n\n--- Instructions ---")
        prompt_parts.append("Please use the above tool results and context to provide a comprehensive response to the original task.")
        
        return "\n".join(prompt_parts)
    
    async def execute_async(
        self,
        execution_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """
        Execute the agent's task asynchronously.
        
        Args:
            execution_id: Optional execution ID for tracking
            context: Optional context data for execution
            
        Returns:
            AgentResult: Result of the agent execution
        """
        # For now, run sync version in executor
        # In future, this could be enhanced for true async LLM calls
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.execute, execution_id, context)
    
    def validate_configuration(self) -> Tuple[bool, List[str]]:
        """
        Validate the agent configuration.
        
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_errors)
        """
        errors = []
        
        # Check required fields
        if not self.config.agent_id:
            errors.append("agent_id is required")
        
        if not self.config.agent_name:
            errors.append("agent_name is required")
        
        if not self.config.system_prompt:
            errors.append("system_prompt is required")
        
        if not self.config.user_prompt:
            errors.append("user_prompt is required")
        
        # Check LLM configuration
        try:
            self.key_manager.get_api_key(self.config.llm_config.provider)
        except EnvironmentKeyError as e:
            errors.append(f"LLM configuration error: {e}")
        
        # Check tools
        if self.config.tools:
            available_tools = self.tool_registry.list_tools()
            for tool_name in self.config.tools:
                if tool_name not in available_tools:
                    errors.append(f"Tool '{tool_name}' not found in registry")
        
        return len(errors) == 0, errors
    
    def select_tools_with_llm(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Use LLM to intelligently select which tools to use for a given task.
        
        This method provides more sophisticated tool selection by asking the LLM
        to analyze the task and recommend appropriate tools.
        
        Args:
            task_description: Description of the task to be performed
            context: Optional context data
            
        Returns:
            List[str]: List of recommended tool names
        """
        if not self.config.tools:
            return []
        
        # Get available tools and their descriptions
        available_tools = []
        for tool_name in self.config.tools:
            try:
                tool_metadata = self.tool_registry.get_tool_metadata(tool_name)
                available_tools.append({
                    "name": tool_name,
                    "description": tool_metadata.description,
                    "tags": tool_metadata.tags
                })
            except Exception as e:
                self.logger.warning(f"Could not get metadata for tool {tool_name}: {e}")
        
        if not available_tools:
            return []
        
        # Create tool selection prompt
        tools_info = "\n".join([
            f"- {tool['name']}: {tool['description']} (tags: {', '.join(tool['tags'])})"
            for tool in available_tools
        ])
        
        selection_prompt = f"""
Task: {task_description}

Available tools:
{tools_info}

Context: {context if context else 'None'}

Please analyze the task and select the most appropriate tools to accomplish it.
Consider the task requirements, tool capabilities, and optimal execution order.

Respond with only the tool names, one per line, in the order they should be executed.
If no tools are needed, respond with "NONE".
"""
        
        try:
            # Use LLM to select tools
            messages = [
                {"role": "system", "content": "You are a tool selection expert. Analyze tasks and recommend the most appropriate tools."},
                {"role": "user", "content": selection_prompt}
            ]
            
            response = self.llm_client.invoke(messages)
            
            # Parse response
            if hasattr(response, 'content'):
                content = response.content.strip()
            elif isinstance(response, dict) and 'content' in response:
                content = response['content'].strip()
            else:
                content = str(response).strip()
            
            if content.upper() == "NONE":
                return []
            
            # Extract tool names from response
            selected_tools = []
            for line in content.split('\n'):
                tool_name = line.strip()
                if tool_name and tool_name in [t['name'] for t in available_tools]:
                    selected_tools.append(tool_name)
            
            self.logger.info(f"LLM selected tools for task: {selected_tools}")
            return selected_tools
            
        except Exception as e:
            self.logger.error(f"LLM tool selection failed: {e}")
            # Fallback to heuristic selection
            return self._select_tools_for_task(context)
    
    def execute_tool_chain_advanced(
        self,
        tool_chain: List[Dict[str, Any]],
        execution_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a complex tool chain with advanced configuration.
        
        This method allows for more sophisticated tool chaining with:
        - Custom input preparation for each tool
        - Conditional execution based on previous results
        - Error handling strategies per tool
        - Result transformation between tools
        
        Args:
            tool_chain: List of tool configurations with advanced options
            execution_id: Optional execution ID for tracking
            context: Optional context data
            
        Returns:
            Dict[str, Any]: Combined results from tool chain execution
        """
        self.execution_id = execution_id or f"chain_{datetime.now().timestamp()}"
        
        results = {}
        previous_result = None
        
        for i, tool_config in enumerate(tool_chain):
            tool_name = tool_config.get("tool")
            if not tool_name:
                self.logger.error(f"Tool name missing in chain step {i}")
                continue
            
            try:
                # Prepare input based on configuration
                if "input_preparation" in tool_config:
                    # Custom input preparation function
                    input_prep_func = tool_config["input_preparation"]
                    tool_input = input_prep_func(context, previous_result)
                else:
                    # Default input preparation
                    tool_input = self._prepare_tool_input(tool_name, context, previous_result)
                
                # Check execution condition
                if "condition" in tool_config:
                    condition_func = tool_config["condition"]
                    if not condition_func(context, previous_result):
                        self.logger.info(f"Skipping tool {tool_name} due to condition")
                        continue
                
                # Execute tool
                tool_result = self._execute_single_tool(tool_name, tool_input)
                
                if tool_result.success:
                    # Apply result transformation if specified
                    if "result_transform" in tool_config:
                        transform_func = tool_config["result_transform"]
                        transformed_result = transform_func(tool_result.result)
                        results[tool_name] = transformed_result
                        previous_result = transformed_result
                    else:
                        results[tool_name] = tool_result.result
                        previous_result = tool_result.result
                else:
                    # Handle error based on strategy
                    error_strategy = tool_config.get("error_strategy", "continue")
                    
                    if error_strategy == "stop":
                        self.logger.error(f"Tool chain stopped due to {tool_name} failure")
                        break
                    elif error_strategy == "retry":
                        retry_count = tool_config.get("retry_count", 1)
                        for retry in range(retry_count):
                            self.logger.info(f"Retrying tool {tool_name} (attempt {retry + 1})")
                            retry_result = self._execute_single_tool(tool_name, tool_input)
                            if retry_result.success:
                                results[tool_name] = retry_result.result
                                previous_result = retry_result.result
                                break
                    # "continue" strategy just continues to next tool
                
            except Exception as e:
                self.logger.error(f"Error in tool chain step {i} ({tool_name}): {e}")
                if tool_config.get("error_strategy", "continue") == "stop":
                    break
        
        return results
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Get agent capabilities and status.
        
        Returns:
            Dict[str, Any]: Agent capabilities information
        """
        is_valid, validation_errors = self.validate_configuration()
        
        # Get tool information
        tool_info = []
        if self.config.tools:
            for tool_name in self.config.tools:
                try:
                    metadata = self.tool_registry.get_tool_metadata(tool_name)
                    tool_info.append({
                        "name": tool_name,
                        "description": metadata.description,
                        "version": metadata.version,
                        "tags": metadata.tags
                    })
                except Exception as e:
                    tool_info.append({
                        "name": tool_name,
                        "error": f"Could not load metadata: {e}"
                    })
        
        return {
            "agent_id": self.config.agent_id,
            "agent_name": self.config.agent_name,
            "provider": self.config.llm_config.provider,
            "model": self.config.llm_config.model,
            "tools": self.config.tools,
            "tool_details": tool_info,
            "max_iterations": self.config.max_iterations,
            "is_valid": is_valid,
            "validation_errors": validation_errors,
            "is_executing": self.is_executing,
            "execution_events_count": len(self.execution_events),
            "supports_tool_integration": True,
            "supports_llm_tool_selection": True,
            "supports_advanced_tool_chains": True
        }


class SupervisorAgent(BaseAgent):
    """
    Supervisor agent that coordinates and routes tasks to worker agents.
    
    SupervisorAgent is responsible for:
    - Intelligent routing of tasks to appropriate agents
    - Coordinating team execution
    - Making decisions based on context and agent capabilities
    """
    
    def __init__(
        self,
        config: SupervisorConfig,
        key_manager: Optional[EnvironmentKeyManager] = None,
        error_handler: Optional[ErrorHandler] = None
    ):
        """
        Initialize the supervisor agent.
        
        Args:
            config: Supervisor configuration
            key_manager: Key manager for API keys
            error_handler: Error handler for managing failures
        """
        super().__init__(config, key_manager, error_handler)
        self.config: SupervisorConfig = config  # Type hint for better IDE support
        
        self.logger.info("Initialized SupervisorAgent")
    
    def execute(
        self,
        task: str,
        available_options: List[str],
        execution_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Execute supervisor routing decision.
        
        Args:
            task: Task description to route
            available_options: List of available options (agents/teams)
            execution_id: Optional execution ID for tracking
            context: Optional context data
            
        Returns:
            str: Selected option name
            
        Raises:
            AgentExecutionError: If routing fails or no options available
        """
        # Validate inputs
        if not available_options:
            raise AgentExecutionError("No available options provided for routing")
        
        if not task or not task.strip():
            raise AgentExecutionError("Task description cannot be empty")
        
        self.execution_id = execution_id or f"supervisor_{datetime.now().timestamp()}"
        self.is_executing = True
        self.execution_start_time = datetime.now()
        
        # Emit start event
        start_event = self._create_execution_event(
            event_type="supervisor_routing",
            action="routing",
            status="running",
            content=f"Routing task: {task[:100]}..."
        )
        self._emit_event(start_event)
        
        try:
            # Create routing prompt
            options_text = "\n".join([f"- {option}" for option in available_options])
            
            routing_prompt = f"""
{self.config.user_prompt}

Task to route: {task}

Available options:
{options_text}

Please select the most appropriate option and return only the option name.
"""
            
            # Prepare messages
            messages = [
                {"role": "system", "content": self.config.system_prompt},
                {"role": "user", "content": routing_prompt}
            ]
            
            # Execute LLM call
            self.logger.info("Executing supervisor routing decision")
            response = self.llm_client.invoke(messages)
            
            # Extract selected option
            if hasattr(response, 'content'):
                selected_option = response.content.strip()
            elif isinstance(response, dict) and 'content' in response:
                selected_option = response['content'].strip()
            else:
                selected_option = str(response).strip()
            
            # Validate selection
            if selected_option not in available_options:
                # Try to find closest match
                selected_option = self._find_closest_match(selected_option, available_options)
            
            # Emit completion event
            completion_event = self._create_execution_event(
                event_type="supervisor_routing",
                action="routing",
                status="completed",
                content=f"Selected option: {selected_option}",
                selected_agent=selected_option
            )
            self._emit_event(completion_event)
            
            self.logger.info(f"Supervisor selected: {selected_option}")
            return selected_option
            
        except Exception as e:
            # Emit error event
            error_event = self._create_execution_event(
                event_type="supervisor_error",
                action="error",
                status="failed",
                content=f"Routing error: {str(e)}"
            )
            self._emit_event(error_event)
            
            # Handle error through error handler
            error_context = ErrorContext(
                execution_id=self.execution_id,
                supervisor_id="supervisor",
                operation="routing_decision",
                metadata={"task": task, "options": available_options, "error": str(e)}
            )
            
            raise AgentExecutionError(f"Supervisor routing failed: {e}")
            
        finally:
            self.is_executing = False
    
    def route_task_structured(
        self,
        task: str,
        available_agents: List[Dict[str, Any]],
        execution_id: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Route task with structured output including reasoning.
        
        Args:
            task: Task description
            available_agents: List of agent information dicts
            execution_id: Optional execution ID
            
        Returns:
            Tuple[str, str]: (selected_agent_name, reasoning)
            
        Raises:
            AgentExecutionError: If routing fails or no agents available
        """
        # Validate inputs
        if not available_agents:
            raise AgentExecutionError("No available agents provided for structured routing")
        
        if not task or not task.strip():
            raise AgentExecutionError("Task description cannot be empty")
        
        self.execution_id = execution_id or f"supervisor_{datetime.now().timestamp()}"
        
        try:
            # Format agent information
            agent_info = "\n".join([
                f"- {agent.get('name', 'Unknown')}: {agent.get('description', 'No description')[:100]}..."
                for agent in available_agents
            ])
            
            routing_prompt = f"""
Task: {task}

Available agents:
{agent_info}

Please analyze the task requirements and select the most suitable agent.
Provide your reasoning for the selection.

Format your response as:
SELECTED: [agent_name]
REASONING: [your reasoning]
"""
            
            messages = [
                {"role": "system", "content": self.config.system_prompt},
                {"role": "user", "content": routing_prompt}
            ]
            
            response = self.llm_client.invoke(messages)
            
            # Parse structured response
            if hasattr(response, 'content'):
                content = response.content
            elif isinstance(response, dict) and 'content' in response:
                content = response['content']
            else:
                content = str(response)
            
            selected_agent, reasoning = self._parse_structured_response(content, available_agents)
            
            # Emit event
            event = self._create_execution_event(
                event_type="supervisor_routing",
                action="structured_routing",
                status="completed",
                content=f"Selected {selected_agent}: {reasoning[:100]}...",
                selected_agent=selected_agent
            )
            self._emit_event(event)
            
            return selected_agent, reasoning
            
        except Exception as e:
            self.logger.error(f"Structured routing failed: {e}")
            raise AgentExecutionError(f"Structured routing failed: {e}")
    
    def _find_closest_match(self, selected: str, options: List[str]) -> str:
        """Find the closest matching option."""
        selected_lower = selected.lower()
        
        # First try exact match (case insensitive)
        for option in options:
            if option.lower() == selected_lower:
                return option
        
        # Then try partial match
        for option in options:
            if selected_lower in option.lower() or option.lower() in selected_lower:
                return option
        
        # Default to first option
        self.logger.warning(f"No close match found for '{selected}', defaulting to '{options[0]}'")
        return options[0]
    
    def _parse_structured_response(
        self,
        content: str,
        available_agents: List[Dict[str, Any]]
    ) -> Tuple[str, str]:
        """Parse structured response from LLM."""
        lines = content.strip().split('\n')
        selected_agent = None
        reasoning = None
        
        # Try to parse structured format first
        for line in lines:
            line = line.strip()
            if line.startswith('SELECTED:'):
                selected_agent = line.replace('SELECTED:', '').strip()
            elif line.startswith('REASONING:'):
                reasoning = line.replace('REASONING:', '').strip()
        
        # If structured parsing failed, try to extract agent name from content
        agent_names = [agent.get('name', '') for agent in available_agents]
        
        if not selected_agent:
            # Look for agent names mentioned in the response
            content_lower = content.lower()
            for agent_name in agent_names:
                if agent_name.lower() in content_lower:
                    selected_agent = agent_name
                    break
        
        # Validate and fallback if needed
        if selected_agent not in agent_names:
            if selected_agent:
                # Try to find closest match
                selected_agent = self._find_closest_match(selected_agent, agent_names)
            else:
                # Fallback to first agent if no selection found
                selected_agent = agent_names[0] if agent_names else "Unknown"
                self.logger.warning(f"Could not parse agent selection from response, defaulting to: {selected_agent}")
        
        # Extract reasoning if not found in structured format
        if not reasoning:
            # Try to extract reasoning from the content
            reasoning_keywords = ["because", "since", "due to", "reason", "suitable", "best"]
            for line in lines:
                line_lower = line.lower()
                if any(keyword in line_lower for keyword in reasoning_keywords):
                    reasoning = line.strip()
                    break
        
        reasoning = reasoning or "No reasoning provided"
        
        return selected_agent, reasoning
    
    def route_task_intelligently(
        self,
        task: str,
        available_agents: List[Dict[str, Any]],
        execution_id: Optional[str] = None
    ) -> str:
        """
        Intelligently route task to the most appropriate agent using LLM reasoning.
        
        This method provides more sophisticated routing by analyzing agent capabilities
        and task requirements to make optimal routing decisions.
        
        Args:
            task: Task description to route
            available_agents: List of agent information dicts with name, description, capabilities
            execution_id: Optional execution ID for tracking
            
        Returns:
            str: Selected agent name
        """
        if not available_agents:
            raise AgentExecutionError("No available agents provided for intelligent routing")
        
        self.execution_id = execution_id or f"supervisor_{datetime.now().timestamp()}"
        
        try:
            # Format agent information with capabilities
            agent_descriptions = []
            for agent in available_agents:
                name = agent.get('name', 'Unknown')
                description = agent.get('description', 'No description')
                capabilities = agent.get('capabilities', [])
                tools = agent.get('tools', [])
                
                agent_info = f"- {name}: {description}"
                if capabilities:
                    agent_info += f" (Capabilities: {', '.join(capabilities)})"
                if tools:
                    agent_info += f" (Tools: {', '.join(tools)})"
                
                agent_descriptions.append(agent_info)
            
            agent_info_text = "\n".join(agent_descriptions)
            
            routing_prompt = f"""
{self.config.user_prompt}

Task to analyze and route: {task}

Available team members:
{agent_info_text}

Analyze the task requirements and select the team member who is best equipped to handle this task.
Consider their capabilities, tools, and expertise when making your decision.

Return only the name of the selected team member.
"""
            
            messages = [
                {"role": "system", "content": self.config.system_prompt},
                {"role": "user", "content": routing_prompt}
            ]
            
            # Execute LLM call with lower temperature for more consistent routing
            response = self.llm_client.invoke(messages)
            
            # Extract selected agent
            if hasattr(response, 'content'):
                selected_agent = response.content.strip()
            elif isinstance(response, dict) and 'content' in response:
                selected_agent = response['content'].strip()
            else:
                selected_agent = str(response).strip()
            
            # Validate and find closest match if needed
            agent_names = [agent.get('name', '') for agent in available_agents]
            if selected_agent not in agent_names:
                selected_agent = self._find_closest_match(selected_agent, agent_names)
            
            # Emit event
            event = self._create_execution_event(
                event_type="supervisor_routing",
                action="intelligent_routing",
                status="completed",
                content=f"Intelligently selected: {selected_agent}",
                selected_agent=selected_agent
            )
            self._emit_event(event)
            
            self.logger.info(f"Intelligent routing selected: {selected_agent}")
            return selected_agent
            
        except Exception as e:
            self.logger.error(f"Intelligent routing failed: {e}")
            raise AgentExecutionError(f"Intelligent routing failed: {e}")
    
    def validate_configuration(self) -> Tuple[bool, List[str]]:
        """
        Validate the supervisor configuration.
        
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_errors)
        """
        errors = []
        
        # Check LLM configuration
        try:
            self.key_manager.get_api_key(self.config.llm_config.provider)
        except EnvironmentKeyError as e:
            errors.append(f"LLM configuration error: {e}")
        
        # Check required prompts
        if not self.config.system_prompt:
            errors.append("system_prompt is required")
        
        if not self.config.user_prompt:
            errors.append("user_prompt is required")
        
        return len(errors) == 0, errors


# Utility functions for agent management
def create_worker_agent(
    config: AgentConfig,
    key_manager: Optional[EnvironmentKeyManager] = None,
    error_handler: Optional[ErrorHandler] = None,
    tool_registry: Optional[ToolRegistry] = None
) -> WorkerAgent:
    """
    Create a worker agent with the given configuration.
    
    Args:
        config: Agent configuration
        key_manager: Optional key manager
        error_handler: Optional error handler
        tool_registry: Optional tool registry
        
    Returns:
        WorkerAgent: Configured worker agent
    """
    return WorkerAgent(config, key_manager, error_handler, tool_registry)


def create_supervisor_agent(
    config: SupervisorConfig,
    key_manager: Optional[EnvironmentKeyManager] = None,
    error_handler: Optional[ErrorHandler] = None
) -> SupervisorAgent:
    """
    Create a supervisor agent with the given configuration.
    
    Args:
        config: Supervisor configuration
        key_manager: Optional key manager
        error_handler: Optional error handler
        
    Returns:
        SupervisorAgent: Configured supervisor agent
    """
    return SupervisorAgent(config, key_manager, error_handler)


def validate_agent_config(config: Union[AgentConfig, SupervisorConfig]) -> Tuple[bool, List[str]]:
    """
    Validate agent configuration.
    
    Args:
        config: Agent or supervisor configuration
        
    Returns:
        Tuple[bool, List[str]]: (is_valid, list_of_errors)
    """
    try:
        if isinstance(config, AgentConfig):
            agent = WorkerAgent(config)
        else:
            agent = SupervisorAgent(config)
        
        return agent.validate_configuration()
    except Exception as e:
        return False, [f"Configuration validation failed: {e}"]