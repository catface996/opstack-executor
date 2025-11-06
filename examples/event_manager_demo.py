#!/usr/bin/env python3
"""
EventManager demonstration script.

This script demonstrates the key features of the EventManager:
- Event generation and classification
- Real-time streaming
- Subscription management
- Event buffering
"""

import asyncio
from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.hierarchical_agents import (
    EventManager, 
    EventManagerConfig,
    ExecutionStatus
)


async def demonstrate_event_manager():
    """Demonstrate EventManager functionality."""
    print("🚀 EventManager Demonstration")
    print("=" * 50)
    
    # Create EventManager with custom configuration
    config = EventManagerConfig(
        max_subscribers=5,
        event_buffer_size=50,
        cleanup_interval=60,
        max_event_age=300
    )
    
    manager = EventManager(config)
    await manager.initialize()
    
    try:
        # Demonstrate event generation
        print("\n📝 1. Event Generation")
        print("-" * 30)
        
        execution_id = "demo_execution_001"
        
        # System events
        await manager.emit_execution_started(execution_id, "research_team")
        print("✅ Emitted execution_started event")
        
        # Supervisor events
        await manager.emit_supervisor_routing(
            execution_id=execution_id,
            supervisor_id="supervisor_001",
            supervisor_name="Research Team Supervisor",
            team_id="research_team",
            content="Selecting best agent for literature search",
            selected_agent="literature_search_agent"
        )
        print("✅ Emitted supervisor_routing event")
        
        # Agent events
        await manager.emit_agent_started(
            execution_id=execution_id,
            team_id="research_team",
            agent_id="agent_001",
            agent_name="Literature Search Agent",
            content="Starting literature search task"
        )
        print("✅ Emitted agent_started event")
        
        await manager.emit_agent_progress(
            execution_id=execution_id,
            team_id="research_team",
            agent_id="agent_001",
            agent_name="Literature Search Agent",
            content="Found 15 relevant papers",
            progress=60
        )
        print("✅ Emitted agent_progress event")
        
        await manager.emit_agent_completed(
            execution_id=execution_id,
            team_id="research_team",
            agent_id="agent_001",
            agent_name="Literature Search Agent",
            result="Successfully collected 25 research papers"
        )
        print("✅ Emitted agent_completed event")
        
        await manager.emit_execution_completed(
            execution_id, 
            ExecutionStatus.COMPLETED,
            "/api/results/demo_execution_001"
        )
        print("✅ Emitted execution_completed event")
        
        # Demonstrate event buffering
        print("\n📚 2. Event Buffering")
        print("-" * 30)
        
        buffered_events = await manager.get_buffered_events(execution_id)
        print(f"📊 Total buffered events: {len(buffered_events)}")
        
        for i, event in enumerate(buffered_events, 1):
            print(f"  {i}. {event.event_type} ({event.source_type}) - {event.timestamp.strftime('%H:%M:%S')}")
        
        # Demonstrate subscription and streaming
        print("\n📡 3. Real-time Streaming")
        print("-" * 30)
        
        # Create subscriber
        subscriber = await manager.subscribe(execution_id)
        print(f"✅ Created subscriber: {subscriber.subscriber_id}")
        
        # Emit some new events for streaming demonstration
        new_execution_id = "demo_execution_002"
        
        async def emit_demo_events():
            """Emit events for streaming demo."""
            await asyncio.sleep(0.1)  # Small delay
            await manager.emit_execution_started(new_execution_id, "analysis_team")
            await asyncio.sleep(0.1)
            await manager.emit_agent_started(
                new_execution_id, "analysis_team", "agent_002", 
                "Data Analyst", "Starting data analysis"
            )
            await asyncio.sleep(0.1)
            await manager.emit_agent_completed(
                new_execution_id, "analysis_team", "agent_002",
                "Data Analyst", "Analysis completed successfully"
            )
        
        # Start event emission task
        emit_task = asyncio.create_task(emit_demo_events())
        
        # Subscribe to new execution and collect events
        new_subscriber = await manager.subscribe(new_execution_id)
        received_events = []
        
        async def collect_events():
            async for event in new_subscriber.get_events():
                received_events.append(event)
                print(f"📨 Received: {event.event_type} from {event.source_type}")
                if len(received_events) >= 3:
                    break
        
        # Collect events with timeout
        try:
            await asyncio.wait_for(collect_events(), timeout=2.0)
            print(f"✅ Successfully streamed {len(received_events)} events")
        except asyncio.TimeoutError:
            print("⏰ Streaming timeout (this is normal for demo)")
        
        await emit_task
        
        # Demonstrate subscription management
        print("\n👥 4. Subscription Management")
        print("-" * 30)
        
        # Check subscriber counts
        total_subscribers = await manager.get_total_subscriber_count()
        exec1_subscribers = await manager.get_subscriber_count(execution_id)
        exec2_subscribers = await manager.get_subscriber_count(new_execution_id)
        
        print(f"📊 Total subscribers: {total_subscribers}")
        print(f"📊 Execution 1 subscribers: {exec1_subscribers}")
        print(f"📊 Execution 2 subscribers: {exec2_subscribers}")
        
        # Clean up subscribers
        await manager.unsubscribe(subscriber)
        await manager.unsubscribe(new_subscriber)
        print("✅ Cleaned up subscribers")
        
        # Demonstrate statistics
        print("\n📈 5. Statistics")
        print("-" * 30)
        
        stats = await manager.get_stats()
        print(f"📊 Total subscribers: {stats['total_subscribers']}")
        print(f"📊 Total buffered events: {stats['total_buffered_events']}")
        print(f"📊 Executions with events: {len(stats['buffer_by_execution'])}")
        
        for exec_id, event_count in stats['buffer_by_execution'].items():
            print(f"  - {exec_id}: {event_count} events")
        
        print("\n🎉 EventManager demonstration completed successfully!")
        
    finally:
        await manager.close()
        print("🔒 EventManager closed")


if __name__ == "__main__":
    asyncio.run(demonstrate_event_manager())