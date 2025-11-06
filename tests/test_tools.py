"""
Tests for the tool integration framework.

This module tests all aspects of the tool framework including:
- Base tool interface and abstract classes
- Tool registry and dynamic loading
- Built-in tools functionality
- Error handling and isolation
- Tool chaining capabilities
"""

import asyncio
import json
import pytest
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, patch

from src.hierarchical_agents.tools import (
    BaseTool,
    ToolInput,
    ToolOutput,
    ToolMetadata,
    ToolRegistry,
    ToolExecutor,
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolRegistrationError,
    default_registry,
    default_executor,
    register_tool,
    get_tool,
    execute_tool,
    execute_tool_async,
    list_tools,
    search_tools,
)

from src.hierarchical_agents.builtin_tools import (
    TavilySearchTool,
    WebScraperTool,
    DocumentWriterTool,
    DataProcessorTool,
    TextEditorTool,
    register_builtin_tools,
)


class MockTool(BaseTool):
    """Mock tool for testing purposes."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.execution_count = 0
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="mock_tool",
            description="A mock tool for testing",
            version="1.0.0",
            tags=["test", "mock"],
            input_schema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Test message"}
                },
                "required": ["message"]
            }
        )
    
    def validate_input(self, input_data: ToolInput) -> bool:
        return hasattr(input_data, 'message') and bool(getattr(input_data, 'message', ''))
    
    def execute(self, input_data: ToolInput) -> ToolOutput:
        self.execution_count += 1
        message = getattr(input_data, 'message', '')
        
        if message == "error":
            raise Exception("Mock error for testing")
        
        return ToolOutput(
            success=True,
            result=f"Mock response to: {message}",
            metadata={"execution_count": self.execution_count}
        )


class FailingTool(BaseTool):
    """Tool that always fails for testing error handling."""
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="failing_tool",
            description="A tool that always fails",
            version="1.0.0",
            tags=["test", "error"]
        )
    
    def execute(self, input_data: ToolInput) -> ToolOutput:
        raise ToolExecutionError("This tool always fails")


class AsyncMockTool(BaseTool):
    """Mock async tool for testing."""
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="async_mock_tool",
            description="An async mock tool for testing",
            version="1.0.0",
            tags=["test", "async"],
            is_async=True
        )
    
    def execute(self, input_data: ToolInput) -> ToolOutput:
        # Sync version
        return ToolOutput(success=True, result="sync result")
    
    async def execute_async(self, input_data: ToolInput) -> ToolOutput:
        # Async version
        await asyncio.sleep(0.01)  # Simulate async work
        return ToolOutput(success=True, result="async result")


class TestBaseTool:
    """Test the BaseTool abstract class."""
    
    def test_mock_tool_creation(self):
        """Test creating a mock tool instance."""
        tool = MockTool()
        assert tool.metadata.name == "mock_tool"
        assert tool.metadata.description == "A mock tool for testing"
        assert "test" in tool.metadata.tags
        assert "mock" in tool.metadata.tags
    
    def test_tool_with_config(self):
        """Test creating a tool with configuration."""
        config = {"test_param": "test_value"}
        tool = MockTool(config)
        assert tool.config == config
    
    def test_tool_schema(self):
        """Test getting tool schema."""
        tool = MockTool()
        schema = tool.get_schema()
        
        assert schema["name"] == "mock_tool"
        assert schema["description"] == "A mock tool for testing"
        assert schema["input_schema"] is not None
        assert schema["requires_auth"] is False
        assert schema["is_async"] is False
    
    def test_tool_string_representation(self):
        """Test tool string representations."""
        tool = MockTool()
        assert "MockTool" in str(tool)
        assert "mock_tool" in str(tool)
        assert "MockTool" in repr(tool)
        assert "mock_tool" in repr(tool)
        assert "1.0.0" in repr(tool)


class TestToolInput:
    """Test the ToolInput model."""
    
    def test_tool_input_creation(self):
        """Test creating ToolInput instances."""
        input_data = ToolInput(message="test message", param1="value1")
        assert input_data.message == "test message"
        assert input_data.param1 == "value1"
    
    def test_tool_input_extra_fields(self):
        """Test that ToolInput allows extra fields."""
        input_data = ToolInput(
            message="test",
            custom_field="custom_value",
            nested_data={"key": "value"}
        )
        assert input_data.message == "test"
        assert input_data.custom_field == "custom_value"
        assert input_data.nested_data == {"key": "value"}


class TestToolOutput:
    """Test the ToolOutput model."""
    
    def test_tool_output_creation(self):
        """Test creating ToolOutput instances."""
        output = ToolOutput(
            success=True,
            result="test result",
            metadata={"key": "value"}
        )
        assert output.success is True
        assert output.result == "test result"
        assert output.metadata == {"key": "value"}
        assert output.error is None
        assert isinstance(output.timestamp, datetime)
    
    def test_tool_output_error(self):
        """Test creating error ToolOutput."""
        output = ToolOutput(
            success=False,
            error="Test error message"
        )
        assert output.success is False
        assert output.error == "Test error message"
        assert output.result is None


class TestToolRegistry:
    """Test the ToolRegistry class."""
    
    def setup_method(self):
        """Set up test registry."""
        self.registry = ToolRegistry()
    
    def test_register_tool(self):
        """Test registering a tool."""
        self.registry.register(MockTool)
        assert "mock_tool" in self.registry.list_tools()
    
    def test_register_tool_with_custom_name(self):
        """Test registering a tool with custom name."""
        self.registry.register(MockTool, "custom_mock")
        assert "custom_mock" in self.registry.list_tools()
    
    def test_register_duplicate_tool(self):
        """Test registering duplicate tool (should overwrite)."""
        self.registry.register(MockTool)
        self.registry.register(MockTool)  # Should not raise error
        assert "mock_tool" in self.registry.list_tools()
    
    def test_unregister_tool(self):
        """Test unregistering a tool."""
        self.registry.register(MockTool)
        assert "mock_tool" in self.registry.list_tools()
        
        self.registry.unregister("mock_tool")
        assert "mock_tool" not in self.registry.list_tools()
    
    def test_unregister_nonexistent_tool(self):
        """Test unregistering a tool that doesn't exist."""
        with pytest.raises(ToolNotFoundError):
            self.registry.unregister("nonexistent_tool")
    
    def test_get_tool(self):
        """Test getting a tool instance."""
        self.registry.register(MockTool)
        tool = self.registry.get_tool("mock_tool")
        assert isinstance(tool, MockTool)
        assert tool.metadata.name == "mock_tool"
    
    def test_get_tool_with_config(self):
        """Test getting a tool with configuration."""
        self.registry.register(MockTool)
        config = {"test_param": "test_value"}
        tool = self.registry.get_tool("mock_tool", config)
        assert tool.config == config
    
    def test_get_nonexistent_tool(self):
        """Test getting a tool that doesn't exist."""
        with pytest.raises(ToolNotFoundError):
            self.registry.get_tool("nonexistent_tool")
    
    def test_get_tool_metadata(self):
        """Test getting tool metadata."""
        self.registry.register(MockTool)
        metadata = self.registry.get_tool_metadata("mock_tool")
        assert metadata.name == "mock_tool"
        assert metadata.description == "A mock tool for testing"
    
    def test_search_tools_by_tags(self):
        """Test searching tools by tags."""
        self.registry.register(MockTool)
        results = self.registry.search_tools(tags=["test"])
        assert "mock_tool" in results
        
        results = self.registry.search_tools(tags=["nonexistent"])
        assert "mock_tool" not in results
    
    def test_search_tools_by_description(self):
        """Test searching tools by description."""
        self.registry.register(MockTool)
        results = self.registry.search_tools(description_contains="mock")
        assert "mock_tool" in results
        
        results = self.registry.search_tools(description_contains="nonexistent")
        assert "mock_tool" not in results
    
    def test_clear_registry(self):
        """Test clearing the registry."""
        self.registry.register(MockTool)
        assert len(self.registry.list_tools()) > 0
        
        self.registry.clear()
        assert len(self.registry.list_tools()) == 0


class TestToolExecutor:
    """Test the ToolExecutor class."""
    
    def setup_method(self):
        """Set up test executor."""
        self.registry = ToolRegistry()
        self.executor = ToolExecutor(self.registry)
        self.registry.register(MockTool)
        self.registry.register(FailingTool)
        self.registry.register(AsyncMockTool)
    
    def test_execute_tool_success(self):
        """Test successful tool execution."""
        input_data = ToolInput(message="test message")
        result = self.executor.execute_tool("mock_tool", input_data)
        
        assert result.success is True
        assert "Mock response to: test message" in result.result
        assert result.error is None
        assert result.execution_time > 0
    
    def test_execute_tool_with_config(self):
        """Test executing tool with configuration."""
        input_data = ToolInput(message="test message")
        config = {"test_param": "test_value"}
        result = self.executor.execute_tool("mock_tool", input_data, config)
        
        assert result.success is True
    
    def test_execute_nonexistent_tool(self):
        """Test executing a tool that doesn't exist."""
        input_data = ToolInput(message="test message")
        result = self.executor.execute_tool("nonexistent_tool", input_data)
        
        assert result.success is False
        assert "not found" in result.error
    
    def test_execute_tool_with_invalid_input(self):
        """Test executing tool with invalid input."""
        input_data = ToolInput()  # Missing required 'message' field
        result = self.executor.execute_tool("mock_tool", input_data)
        
        assert result.success is False
        assert "Invalid input" in result.error
    
    def test_execute_failing_tool(self):
        """Test executing a tool that always fails."""
        input_data = ToolInput()
        result = self.executor.execute_tool("failing_tool", input_data)
        
        assert result.success is False
        assert "Tool execution failed" in result.error
        assert result.execution_time > 0
    
    def test_execute_tool_with_exception(self):
        """Test executing tool that raises an exception."""
        input_data = ToolInput(message="error")  # This triggers an exception in MockTool
        result = self.executor.execute_tool("mock_tool", input_data)
        
        assert result.success is False
        assert "Mock error for testing" in result.error
    
    @pytest.mark.asyncio
    async def test_execute_tool_async(self):
        """Test asynchronous tool execution."""
        input_data = ToolInput(message="test message")
        result = await self.executor.execute_tool_async("async_mock_tool", input_data)
        
        assert result.success is True
        assert result.result == "async result"
    
    @pytest.mark.asyncio
    async def test_execute_sync_tool_async(self):
        """Test executing sync tool asynchronously."""
        input_data = ToolInput(message="test message")
        result = await self.executor.execute_tool_async("mock_tool", input_data)
        
        assert result.success is True
        assert "Mock response to: test message" in result.result
    
    def test_execute_tool_chain_success(self):
        """Test executing a successful tool chain."""
        chain = [
            {
                "tool": "mock_tool",
                "input": {"message": "first step"}
            },
            {
                "tool": "mock_tool",
                "input": {"message": "second step"},
                "use_previous_output": False
            }
        ]
        
        results = self.executor.execute_tool_chain(chain)
        
        assert len(results) == 2
        assert all(result.success for result in results)
        assert "first step" in results[0].result
        assert "second step" in results[1].result
    
    def test_execute_tool_chain_with_failure(self):
        """Test executing tool chain with failure."""
        chain = [
            {
                "tool": "mock_tool",
                "input": {"message": "success"}
            },
            {
                "tool": "failing_tool",
                "input": {},
                "stop_on_error": True
            },
            {
                "tool": "mock_tool",
                "input": {"message": "should not execute"}
            }
        ]
        
        results = self.executor.execute_tool_chain(chain)
        
        assert len(results) == 2  # Third step should not execute
        assert results[0].success is True
        assert results[1].success is False
    
    def test_execute_tool_chain_continue_on_error(self):
        """Test executing tool chain that continues on error."""
        chain = [
            {
                "tool": "failing_tool",
                "input": {},
                "stop_on_error": False
            },
            {
                "tool": "mock_tool",
                "input": {"message": "should execute"}
            }
        ]
        
        results = self.executor.execute_tool_chain(chain)
        
        assert len(results) == 2
        assert results[0].success is False
        assert results[1].success is True


class TestBuiltinTools:
    """Test the built-in tools."""
    
    def test_tavily_search_tool(self):
        """Test TavilySearchTool."""
        tool = TavilySearchTool()
        
        # Test metadata
        assert tool.metadata.name == "tavily_search"
        assert "search" in tool.metadata.tags
        assert tool.metadata.requires_auth is True
        
        # Test execution
        input_data = ToolInput(query="AI medical applications", max_results=3)
        result = tool.execute(input_data)
        
        assert result.success is True
        assert "results" in result.result
        assert "query" in result.result
        assert result.result["query"] == "AI medical applications"
        assert len(result.result["results"]) <= 3
    
    def test_tavily_search_tool_invalid_input(self):
        """Test TavilySearchTool with invalid input."""
        tool = TavilySearchTool()
        
        # Test with empty query
        input_data = ToolInput(query="")
        assert not tool.validate_input(input_data)
        
        # Test with missing query
        input_data = ToolInput()
        assert not tool.validate_input(input_data)
    
    def test_web_scraper_tool(self):
        """Test WebScraperTool."""
        tool = WebScraperTool()
        
        # Test metadata
        assert tool.metadata.name == "web_scraper"
        assert "scraping" in tool.metadata.tags
        
        # Test execution
        input_data = ToolInput(
            url="https://example.com/test",
            extract_text=True,
            extract_links=True
        )
        result = tool.execute(input_data)
        
        assert result.success is True
        assert "content" in result.result
        assert "title" in result.result
        assert "links" in result.result
        assert "metadata" in result.result
    
    def test_web_scraper_tool_invalid_url(self):
        """Test WebScraperTool with invalid URL."""
        tool = WebScraperTool()
        
        # Test with invalid URL
        input_data = ToolInput(url="not-a-url")
        assert not tool.validate_input(input_data)
        
        # Test with missing URL
        input_data = ToolInput()
        assert not tool.validate_input(input_data)
    
    def test_document_writer_tool(self):
        """Test DocumentWriterTool."""
        tool = DocumentWriterTool()
        
        # Test metadata
        assert tool.metadata.name == "document_writer"
        assert "document" in tool.metadata.tags
        
        # Test markdown formatting
        input_data = ToolInput(
            content="This is test content",
            title="Test Document",
            format="markdown",
            metadata={"author": "Test Author"}
        )
        result = tool.execute(input_data)
        
        assert result.success is True
        assert "document" in result.result
        assert "word_count" in result.result
        assert "# Test Document" in result.result["document"]
        assert "Test Author" in result.result["document"]
    
    def test_document_writer_tool_html_format(self):
        """Test DocumentWriterTool with HTML format."""
        tool = DocumentWriterTool()
        
        input_data = ToolInput(
            content="Test content",
            title="Test Document",
            format="html"
        )
        result = tool.execute(input_data)
        
        assert result.success is True
        assert "<html>" in result.result["document"]
        assert "<title>Test Document</title>" in result.result["document"]
    
    def test_data_processor_tool(self):
        """Test DataProcessorTool."""
        tool = DataProcessorTool()
        
        # Test metadata
        assert tool.metadata.name == "data_processor"
        assert "data" in tool.metadata.tags
        
        # Test with list data
        test_data = ["item1", "item2", "item3"]
        input_data = ToolInput(data=test_data, operation="analyze")
        result = tool.execute(input_data)
        
        assert result.success is True
        assert "result" in result.result
        assert "statistics" in result.result
        assert result.result["statistics"]["size"] == 3
    
    def test_data_processor_tool_json_string(self):
        """Test DataProcessorTool with JSON string."""
        tool = DataProcessorTool()
        
        json_data = '{"key1": "value1", "key2": "value2"}'
        input_data = ToolInput(data=json_data, format="json", operation="analyze")
        result = tool.execute(input_data)
        
        assert result.success is True
        assert result.result["statistics"]["data_type"] == "dict"
    
    def test_text_editor_tool(self):
        """Test TextEditorTool."""
        tool = TextEditorTool()
        
        # Test metadata
        assert tool.metadata.name == "editor"
        assert "text" in tool.metadata.tags
        
        # Test text formatting
        messy_text = "  This   is    messy   text   with   extra   spaces.  "
        input_data = ToolInput(text=messy_text, operation="format")
        result = tool.execute(input_data)
        
        assert result.success is True
        assert "edited_text" in result.result
        assert "changes" in result.result
        assert "statistics" in result.result
        assert len(result.result["changes"]) > 0
    
    def test_text_editor_tool_summarize(self):
        """Test TextEditorTool summarization."""
        tool = TextEditorTool()
        
        long_text = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence."
        input_data = ToolInput(
            text=long_text,
            operation="summarize",
            parameters={"max_sentences": 2}
        )
        result = tool.execute(input_data)
        
        assert result.success is True
        assert len(result.result["edited_text"]) < len(long_text)


class TestGlobalFunctions:
    """Test global convenience functions."""
    
    def setup_method(self):
        """Set up test environment."""
        # Clear default registry
        default_registry.clear()
    
    def teardown_method(self):
        """Clean up after tests."""
        default_registry.clear()
    
    def test_register_tool_global(self):
        """Test global register_tool function."""
        register_tool(MockTool)
        assert "mock_tool" in list_tools()
    
    def test_get_tool_global(self):
        """Test global get_tool function."""
        register_tool(MockTool)
        tool = get_tool("mock_tool")
        assert isinstance(tool, MockTool)
    
    def test_execute_tool_global(self):
        """Test global execute_tool function."""
        register_tool(MockTool)
        result = execute_tool("mock_tool", {"message": "test"})
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_execute_tool_async_global(self):
        """Test global execute_tool_async function."""
        register_tool(AsyncMockTool)
        result = await execute_tool_async("async_mock_tool", {"message": "test"})
        assert result.success is True
    
    def test_search_tools_global(self):
        """Test global search_tools function."""
        register_tool(MockTool)
        results = search_tools(tags=["test"])
        assert "mock_tool" in results
    
    def test_register_builtin_tools(self):
        """Test registering all built-in tools."""
        register_builtin_tools()
        tools = list_tools()
        
        expected_tools = [
            "tavily_search",
            "web_scraper", 
            "document_writer",
            "data_processor",
            "editor"
        ]
        
        for tool_name in expected_tools:
            assert tool_name in tools


class TestErrorHandling:
    """Test error handling and isolation."""
    
    def setup_method(self):
        """Set up test environment."""
        self.registry = ToolRegistry()
        self.executor = ToolExecutor(self.registry)
    
    def test_tool_registration_error(self):
        """Test tool registration error handling."""
        # Try to register an invalid tool class
        class InvalidTool:
            pass
        
        with pytest.raises(ToolRegistrationError):
            self.registry.register(InvalidTool)
    
    def test_tool_execution_isolation(self):
        """Test that tool execution errors don't affect the executor."""
        self.registry.register(FailingTool)
        self.registry.register(MockTool)
        
        # Execute failing tool
        result1 = self.executor.execute_tool("failing_tool", ToolInput())
        assert result1.success is False
        
        # Execute working tool - should still work
        result2 = self.executor.execute_tool("mock_tool", ToolInput(message="test"))
        assert result2.success is True
    
    def test_tool_exception_handling(self):
        """Test that tool exceptions are properly caught and handled."""
        self.registry.register(MockTool)
        
        # This should trigger an exception in MockTool
        result = self.executor.execute_tool("mock_tool", ToolInput(message="error"))
        
        assert result.success is False
        assert "Mock error for testing" in result.error
        assert "traceback" in result.metadata
    
    def test_invalid_tool_input_handling(self):
        """Test handling of invalid tool inputs."""
        self.registry.register(MockTool)
        
        # Test with invalid input
        result = self.executor.execute_tool("mock_tool", ToolInput())
        assert result.success is False
        assert "Invalid input" in result.error


if __name__ == "__main__":
    pytest.main([__file__])