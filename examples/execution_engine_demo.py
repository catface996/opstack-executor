#!/usr/bin/env python3
"""
ExecutionEngine Demo

This script demonstrates the core functionality of the ExecutionEngine,
including async execution, session management, state transitions, and
concurrent execution capabilities.
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.hierarchical_agents import (
    ExecutionEngine,
    StateManager,
    EventManager,
    ErrorHandler,
    HierarchicalTeam,
    SubTeam,
    SupervisorConfig,
    AgentConfig,
    LLMConfig,
    GlobalConfig,
    ExecutionConfig,
    StateManagerConfig,
    EventManagerConfig
)


def create_sample_team() -> HierarchicalTeam:
    """Create a sample hierarchical team for demonstration."""
    # LLM configuration
    llm_config = LLMConfig(
        provider="openai",
        model="gpt-4o",
        temperature=0.7
    )
    
    # Supervisor configuration
    supervisor_config = SupervisorConfig(
        llm_config=llm_config,
        system_prompt="You are a team supervisor responsible for coordinating tasks.",
        user_prompt="Please coordinate the team to complete the research and analysis task.",
        max_iterations=5
    )
    
    # Agent configurations
    researcher_config = AgentConfig(
        agent_id="researcher_001",
        agent_name="Research Specialist",
        llm_config=llm_config,
        system_prompt="You are a research specialist focused on gathering information.",
        user_prompt="Research the latest developments in AI technology.",
        tools=["web_search", "document_reader"],
        max_iterations=3
    )
    
    analyst_config = AgentConfig(
        agent_id="analyst_001",
        agent_name="Data Analyst",
        llm_config=llm_config,
        system_prompt="You are a data analyst who processes and analyzes information.",
        user_prompt="Analyze the research data and identify key trends.",
        tools=["data_processor", "chart_generator"],
        max_iterations=3
    )
    
    # Sub-team
    research_team = SubTeam(
        id="research_team_001",
        name="Research Team",
        description="Team responsible for research and analysis",
        supervisor_config=supervisor_config,
        agent_configs=[researcher_config, analyst_config]
    )
    
    # Hierarchical team
    return HierarchicalTeam(
        team_name="ai_research_team",
        description="AI Research and Analysis Team",
        top_supervisor_config=supervisor_config,
        sub_teams=[research_team],
        dependencies={},
        global_config=GlobalConfig(
            max_execution_time=1800,
            enable_streaming=True,
            output_format="detailed"
        )
    )


async def create_mock_components():
    """Create mock components for demonstration."""
    # Mock StateManager
    state_manager = AsyncMock(spec=StateManager)
    state_manager.initialize = AsyncMock()
    state_manager.create_execution = AsyncMock()
    state_manager.update_execution_status = AsyncMock()
    state_manager.update_execution_summary = AsyncMock()
    state_manager.update_team_result = AsyncMock()
    state_manager.add_error = AsyncMock()
    state_manager.get_execution_status = AsyncMock()
    
    # Mock EventManager
    event_manager = AsyncMock(spec=EventManager)
    event_manager.initialize = AsyncMock()
    event_manager.emit_execution_started = AsyncMock()
    event_manager.emit_execution_completed = AsyncMock()
    event_manager.emit_event = AsyncMock()
    event_manager.get_events_stream = AsyncMock()
    
    # Real ErrorHandler
    error_handler = ErrorHandler()
    
    return state_manager, event_manager, error_handler


async def demo_basic_execution():
    """Demonstrate basic execution functionality."""
    print("🚀 Demo 1: Basic Execution")
    print("=" * 50)
    
    # Create components
    state_manager, event_manager, error_handler = await create_mock_components()
    
    # Create ExecutionEngine
    engine = ExecutionEngine(state_manager, event_manager, error_handler)
    await engine.initialize()
    
    # Create sample team
    team = create_sample_team()
    
    # Start execution
    print(f"Starting execution for team: {team.team_name}")
    session = await engine.start_execution(team)
    
    print(f"✓ Execution started with ID: {session.execution_id}")
    print(f"✓ Initial status: {session.status.value}")
    print(f"✓ Team: {session.team.team_name}")
    print(f"✓ Started at: {session.started_at}")
    
    # Wait for execution to complete
    await asyncio.sleep(0.2)
    
    print(f"✓ Final status: {session.status.value}")
    if session.completed_at:
        print(f"✓ Completed at: {session.completed_at}")
        print(f"✓ Duration: {session.get_duration()} seconds")
    
    # Cleanup
    await engine.shutdown()
    print("✓ Engine shutdown complete\n")


async def demo_concurrent_execution():
    """Demonstrate concurrent execution capabilities."""
    print("🔄 Demo 2: Concurrent Execution")
    print("=" * 50)
    
    # Create components
    state_manager, event_manager, error_handler = await create_mock_components()
    
    # Create ExecutionEngine
    engine = ExecutionEngine(state_manager, event_manager, error_handler)
    await engine.initialize()
    
    # Create sample team
    team = create_sample_team()
    
    # Start multiple concurrent executions
    print("Starting 3 concurrent executions...")
    sessions = []
    for i in range(3):
        session = await engine.start_execution(team)
        sessions.append(session)
        print(f"✓ Started execution {i+1}: {session.execution_id}")
    
    # Verify all are running
    print("\nVerifying concurrent execution:")
    for i, session in enumerate(sessions):
        print(f"  Session {i+1}: {session.status.value}")
    
    # Check engine stats
    stats = await engine.get_stats()
    print(f"\nEngine stats:")
    print(f"  Total sessions: {stats['total_sessions']}")
    print(f"  Running: {stats['execution_counts']['running']}")
    
    # Wait for completion
    await asyncio.sleep(0.3)
    
    print("\nFinal status:")
    for i, session in enumerate(sessions):
        print(f"  Session {i+1}: {session.status.value}")
    
    # Cleanup
    await engine.shutdown()
    print("✓ Engine shutdown complete\n")


async def demo_session_management():
    """Demonstrate session management capabilities."""
    print("📋 Demo 3: Session Management")
    print("=" * 50)
    
    # Create components
    state_manager, event_manager, error_handler = await create_mock_components()
    
    # Create ExecutionEngine
    engine = ExecutionEngine(state_manager, event_manager, error_handler)
    await engine.initialize()
    
    # Create sample team
    team = create_sample_team()
    
    # Start execution
    session = await engine.start_execution(team)
    execution_id = session.execution_id
    
    print(f"✓ Started execution: {execution_id}")
    
    # Test session retrieval
    retrieved_session = await engine.get_execution_session(execution_id)
    print(f"✓ Retrieved session: {retrieved_session.execution_id == execution_id}")
    
    # Test pause/resume
    await session.pause()
    print(f"✓ Paused execution: {session.status.value}")
    
    await session.resume()
    print(f"✓ Resumed execution: {session.status.value}")
    
    # Test active executions list
    active_executions = await engine.list_active_executions()
    print(f"✓ Active executions: {len(active_executions)}")
    
    # Test execution counts
    counts = await engine.get_execution_count()
    print(f"✓ Execution counts: {json.dumps(counts, indent=2)}")
    
    # Wait for completion
    await asyncio.sleep(0.2)
    
    # Test cleanup
    cleaned = await engine.cleanup_completed_sessions()
    print(f"✓ Cleaned up {cleaned} completed sessions")
    
    # Cleanup
    await engine.shutdown()
    print("✓ Engine shutdown complete\n")


async def demo_custom_configuration():
    """Demonstrate execution with custom configuration."""
    print("⚙️  Demo 4: Custom Configuration")
    print("=" * 50)
    
    # Create components
    state_manager, event_manager, error_handler = await create_mock_components()
    
    # Create ExecutionEngine
    engine = ExecutionEngine(state_manager, event_manager, error_handler)
    await engine.initialize()
    
    # Create sample team
    team = create_sample_team()
    
    # Custom execution configuration
    custom_config = ExecutionConfig(
        stream_events=False,
        save_intermediate_results=True,
        max_parallel_teams=2
    )
    
    print("Custom configuration:")
    print(f"  Stream events: {custom_config.stream_events}")
    print(f"  Save intermediate results: {custom_config.save_intermediate_results}")
    print(f"  Max parallel teams: {custom_config.max_parallel_teams}")
    
    # Start execution with custom config
    session = await engine.start_execution(team, custom_config)
    
    print(f"✓ Started execution with custom config: {session.execution_id}")
    print(f"✓ Config applied: {session.config == custom_config}")
    
    # Wait for completion
    await asyncio.sleep(0.2)
    
    print(f"✓ Execution completed: {session.status.value}")
    
    # Cleanup
    await engine.shutdown()
    print("✓ Engine shutdown complete\n")


async def main():
    """Run all demonstrations."""
    print("ExecutionEngine Demonstration")
    print("=" * 60)
    print("This demo shows the core capabilities of the ExecutionEngine:")
    print("- Async execution with unique session IDs")
    print("- State transitions (pending → running → completed)")
    print("- Concurrent execution safety")
    print("- Session management and control")
    print("- Custom configuration support")
    print("=" * 60)
    print()
    
    try:
        await demo_basic_execution()
        await demo_concurrent_execution()
        await demo_session_management()
        await demo_custom_configuration()
        
        print("🎉 All demonstrations completed successfully!")
        print("\nKey features demonstrated:")
        print("✓ Async execution with coroutine-based start_execution()")
        print("✓ Unique execution ID generation for each session")
        print("✓ Proper state transitions (pending → running → completed)")
        print("✓ Concurrent execution without interference")
        print("✓ Session management and control operations")
        print("✓ Integration with StateManager, EventManager, and ErrorHandler")
        
    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())