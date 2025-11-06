#!/usr/bin/env python3
"""
Demonstration of tool integration in WorkerAgent.

This script shows how agents can intelligently use tools to enhance their capabilities.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hierarchical_agents.agents import WorkerAgent
from hierarchical_agents.data_models import AgentConfig, LLMConfig
from hierarchical_agents.tools import ToolRegistry
from hierarchical_agents.builtin_tools import register_builtin_tools


def setup_environment():
    """Set up environment variables for testing."""
    if "OPENAI_API_KEY" not in os.environ:
        os.environ["OPENAI_API_KEY"] = "sk-test123456789abcdef"  # Mock key for demo


def create_research_agent():
    """Create a research agent with tool capabilities."""
    config = AgentConfig(
        agent_id="research_agent_001",
        agent_name="AI Research Specialist",
        llm_config=LLMConfig(
            provider="openai",
            model="gpt-4o",
            temperature=0.7
        ),
        system_prompt="""You are an AI research specialist with access to powerful tools. 
        You excel at gathering information, analyzing data, and creating comprehensive reports. 
        Use your tools strategically to provide thorough and well-researched responses.""",
        user_prompt="""Research the latest developments in AI applications for medical diagnosis. 
        Focus on deep learning approaches for medical imaging and their clinical impact. 
        Provide a comprehensive analysis with key findings and future prospects.""",
        tools=["tavily_search", "data_processor", "document_writer"],
        max_iterations=5
    )
    
    # Set up tool registry with built-in tools
    tool_registry = ToolRegistry()
    register_builtin_tools()
    
    return WorkerAgent(config, tool_registry=tool_registry)


def create_writing_agent():
    """Create a writing agent with document processing tools."""
    config = AgentConfig(
        agent_id="writing_agent_001",
        agent_name="Technical Writer",
        llm_config=LLMConfig(
            provider="openai",
            model="gpt-4o",
            temperature=0.5
        ),
        system_prompt="""You are a professional technical writer specializing in AI and healthcare topics. 
        You create clear, well-structured documents that are accessible to both technical and non-technical audiences.""",
        user_prompt="""Create a comprehensive report on AI in medical diagnosis based on the research findings. 
        Structure the document with clear sections, include key statistics, and provide actionable insights 
        for healthcare professionals.""",
        tools=["document_writer", "editor"],
        max_iterations=3
    )
    
    tool_registry = ToolRegistry()
    register_builtin_tools()
    
    return WorkerAgent(config, tool_registry=tool_registry)


def demonstrate_tool_selection():
    """Demonstrate intelligent tool selection."""
    print("=== Tool Selection Demonstration ===")
    
    setup_environment()
    research_agent = create_research_agent()
    
    # Show heuristic-based tool selection
    print("\n1. Heuristic-based tool selection:")
    selected_tools = research_agent._select_tools_for_task()
    print(f"   Selected tools: {selected_tools}")
    
    # Show LLM-based tool selection (would use real LLM in production)
    print("\n2. LLM-based tool selection:")
    try:
        task = "Research AI medical applications and analyze market trends"
        llm_selected = research_agent.select_tools_with_llm(task)
        print(f"   LLM selected tools: {llm_selected}")
    except Exception as e:
        print(f"   LLM selection failed (expected with mock): {e}")
    
    # Show tool capabilities
    print("\n3. Agent capabilities:")
    capabilities = research_agent.get_capabilities()
    print(f"   Supports tool integration: {capabilities['supports_tool_integration']}")
    print(f"   Supports LLM tool selection: {capabilities['supports_llm_tool_selection']}")
    print(f"   Available tools: {capabilities['tools']}")


def demonstrate_tool_execution():
    """Demonstrate tool execution with mock results."""
    print("\n=== Tool Execution Demonstration ===")
    
    setup_environment()
    research_agent = create_research_agent()
    
    print("\n1. Executing research agent with tools...")
    try:
        # This would normally make real API calls, but with mock keys it will use fallbacks
        result = research_agent.execute_with_tools(execution_id="demo_001")
        
        print(f"   Execution status: {result['status']}")
        print(f"   Tools used: {len(result.get('tools_used', []))}")
        print(f"   Enhanced with tools: {result.get('enhanced_with_tools', False)}")
        
        # Show tool usage details
        if result.get('tools_used'):
            print("\n   Tool usage details:")
            for tool_info in result['tools_used']:
                status = "✓" if tool_info['success'] else "✗"
                print(f"     {status} {tool_info['tool_name']}: {tool_info.get('execution_time', 0):.2f}s")
                if not tool_info['success']:
                    print(f"       Error: {tool_info.get('error', 'Unknown error')}")
                if tool_info.get('fallback_applied'):
                    print(f"       Fallback applied: {tool_info.get('fallback_result', 'N/A')}")
        
        print(f"\n   Output preview: {result['output'][:200]}...")
        
    except Exception as e:
        print(f"   Execution failed: {e}")


def demonstrate_advanced_features():
    """Demonstrate advanced tool integration features."""
    print("\n=== Advanced Features Demonstration ===")
    
    setup_environment()
    research_agent = create_research_agent()
    
    print("\n1. Tool input preparation:")
    # Show how different tools get different inputs
    search_input = research_agent._prepare_tool_input("tavily_search", None, None)
    print(f"   Search tool input: query='{search_input.query[:50]}...'")
    
    doc_input = research_agent._prepare_tool_input("document_writer", None, None)
    print(f"   Document writer input: title='{doc_input.title}'")
    
    print("\n2. Advanced tool chain configuration:")
    # Example of advanced tool chain
    advanced_chain = [
        {
            "tool": "tavily_search",
            "error_strategy": "retry",
            "retry_count": 2
        },
        {
            "tool": "data_processor",
            "condition": lambda ctx, prev: prev is not None,
            "error_strategy": "continue"
        },
        {
            "tool": "document_writer",
            "result_transform": lambda result: {"formatted_report": result},
            "error_strategy": "stop"
        }
    ]
    
    print(f"   Chain steps: {len(advanced_chain)}")
    for i, step in enumerate(advanced_chain, 1):
        print(f"     {i}. {step['tool']} (strategy: {step.get('error_strategy', 'default')})")
    
    try:
        chain_results = research_agent.execute_tool_chain_advanced(advanced_chain)
        print(f"   Chain execution completed: {len(chain_results)} tools succeeded")
    except Exception as e:
        print(f"   Chain execution failed: {e}")


def main():
    """Run the tool integration demonstration."""
    print("🔧 WorkerAgent Tool Integration Demonstration")
    print("=" * 50)
    
    try:
        demonstrate_tool_selection()
        demonstrate_tool_execution()
        demonstrate_advanced_features()
        
        print("\n" + "=" * 50)
        print("✅ Demonstration completed successfully!")
        print("\nKey features demonstrated:")
        print("• Intelligent tool selection (heuristic and LLM-based)")
        print("• Automatic tool execution with error handling")
        print("• Tool result integration into LLM prompts")
        print("• Fallback strategies for failed tools")
        print("• Advanced tool chaining capabilities")
        print("• Enhanced agent capabilities reporting")
        
    except Exception as e:
        print(f"\n❌ Demonstration failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()