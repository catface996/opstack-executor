"""
Event management for hierarchical multi-agent system.

This module provides real-time event generation, streaming, and subscription
management for monitoring execution progress and system events.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Set
from contextlib import asynccontextmanager
from collections import defaultdict

from pydantic import BaseModel

from .data_models import ExecutionEvent, ExecutionStatus


class EventManagerConfig(BaseModel):
    """Configuration for EventManager."""
    max_subscribers: int = 100
    event_buffer_size: int = 1000
    cleanup_interval: int = 300  # 5 minutes
    max_event_age: int = 3600    # 1 hour


class EventSubscriber:
    """Event subscriber for receiving real-time events."""
    
    def __init__(self, subscriber_id: str, execution_id: Optional[str] = None):
        """Initialize subscriber."""
        self.subscriber_id = subscriber_id
        self.execution_id = execution_id
        self.queue: asyncio.Queue[ExecutionEvent] = asyncio.Queue()
        self.active = True
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
    
    async def send_event(self, event: ExecutionEvent) -> bool:
        """Send event to subscriber."""
        if not self.active:
            return False
        
        try:
            # Non-blocking put with size limit
            if self.queue.qsize() >= 100:  # Prevent memory buildup
                # Remove oldest event
                try:
                    self.queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            
            self.queue.put_nowait(event)
            self.last_activity = datetime.now()
            return True
        except asyncio.QueueFull:
            return False
    
    async def get_events(self) -> AsyncIterator[ExecutionEvent]:
        """Get events from subscriber queue."""
        while self.active:
            try:
                event = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                self.last_activity = datetime.now()
                yield event
            except asyncio.TimeoutError:
                continue
            except Exception:
                break
    
    def close(self) -> None:
        """Close subscriber."""
        self.active = False


class EventManager:
    """
    Event manager for hierarchical multi-agent system.
    
    Provides real-time event generation, streaming, and subscription management
    for monitoring execution progress and system events.
    """
    
    def __init__(self, config: Optional[EventManagerConfig] = None):
        """Initialize EventManager with configuration."""
        self.config = config or EventManagerConfig()
        self._subscribers: Dict[str, EventSubscriber] = {}
        self._execution_subscribers: Dict[str, Set[str]] = defaultdict(set)
        self._event_buffer: Dict[str, List[ExecutionEvent]] = defaultdict(list)
        self._cleanup_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    async def initialize(self) -> None:
        """Initialize EventManager."""
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def close(self) -> None:
        """Close EventManager and cleanup resources."""
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all subscribers
        async with self._lock:
            for subscriber in self._subscribers.values():
                subscriber.close()
            self._subscribers.clear()
            self._execution_subscribers.clear()
            self._event_buffer.clear()
    
    async def emit_event(self, event: ExecutionEvent) -> None:
        """Emit an event to all relevant subscribers."""
        async with self._lock:
            # Add to event buffer
            self._event_buffer[event.execution_id].append(event)
            
            # Limit buffer size
            if len(self._event_buffer[event.execution_id]) > self.config.event_buffer_size:
                self._event_buffer[event.execution_id] = \
                    self._event_buffer[event.execution_id][-self.config.event_buffer_size:]
            
            # Send to execution-specific subscribers
            execution_subscriber_ids = self._execution_subscribers.get(event.execution_id, set())
            for subscriber_id in execution_subscriber_ids.copy():
                subscriber = self._subscribers.get(subscriber_id)
                if subscriber and subscriber.active:
                    success = await subscriber.send_event(event)
                    if not success:
                        # Remove inactive subscriber
                        await self._remove_subscriber(subscriber_id)
                else:
                    # Remove invalid subscriber reference
                    execution_subscriber_ids.discard(subscriber_id)
            
            # Send to global subscribers (execution_id is None)
            global_subscriber_ids = self._execution_subscribers.get(None, set())
            for subscriber_id in global_subscriber_ids.copy():
                subscriber = self._subscribers.get(subscriber_id)
                if subscriber and subscriber.active:
                    success = await subscriber.send_event(event)
                    if not success:
                        await self._remove_subscriber(subscriber_id)
                else:
                    global_subscriber_ids.discard(subscriber_id)
    
    async def subscribe(self, execution_id: Optional[str] = None) -> EventSubscriber:
        """Subscribe to events for a specific execution or all executions."""
        async with self._lock:
            if len(self._subscribers) >= self.config.max_subscribers:
                raise RuntimeError("Maximum number of subscribers reached")
            
            subscriber_id = str(uuid.uuid4())
            subscriber = EventSubscriber(subscriber_id, execution_id)
            
            self._subscribers[subscriber_id] = subscriber
            self._execution_subscribers[execution_id].add(subscriber_id)
            
            # Send buffered events for specific execution
            if execution_id and execution_id in self._event_buffer:
                for event in self._event_buffer[execution_id]:
                    await subscriber.send_event(event)
            
            return subscriber
    
    async def unsubscribe(self, subscriber: EventSubscriber) -> None:
        """Unsubscribe from events."""
        await self._remove_subscriber(subscriber.subscriber_id)
    
    async def _remove_subscriber(self, subscriber_id: str) -> None:
        """Remove subscriber (internal method)."""
        subscriber = self._subscribers.get(subscriber_id)
        if subscriber:
            subscriber.close()
            del self._subscribers[subscriber_id]
            
            # Remove from execution subscribers
            for execution_id, subscriber_ids in self._execution_subscribers.items():
                subscriber_ids.discard(subscriber_id)
    
    async def get_events_stream(
        self, 
        execution_id: Optional[str] = None
    ) -> AsyncIterator[ExecutionEvent]:
        """Get real-time event stream."""
        subscriber = await self.subscribe(execution_id)
        try:
            async for event in subscriber.get_events():
                yield event
        finally:
            await self.unsubscribe(subscriber)
    
    async def get_buffered_events(
        self, 
        execution_id: str, 
        limit: Optional[int] = None
    ) -> List[ExecutionEvent]:
        """Get buffered events for an execution."""
        async with self._lock:
            events = self._event_buffer.get(execution_id, [])
            if limit:
                events = events[-limit:]
            return events.copy()
    
    def create_system_event(
        self,
        execution_id: str,
        event_type: str,
        content: Optional[str] = None,
        status: Optional[str] = None,
        **kwargs
    ) -> ExecutionEvent:
        """Create a system event."""
        return ExecutionEvent(
            timestamp=datetime.now(),
            event_type=event_type,
            source_type="system",
            execution_id=execution_id,
            content=content,
            status=status,
            **kwargs
        )
    
    def create_supervisor_event(
        self,
        execution_id: str,
        event_type: str,
        supervisor_id: str,
        supervisor_name: str,
        team_id: Optional[str] = None,
        content: Optional[str] = None,
        action: Optional[str] = None,
        selected_team: Optional[str] = None,
        selected_agent: Optional[str] = None,
        **kwargs
    ) -> ExecutionEvent:
        """Create a supervisor event."""
        return ExecutionEvent(
            timestamp=datetime.now(),
            event_type=event_type,
            source_type="supervisor",
            execution_id=execution_id,
            team_id=team_id,
            supervisor_id=supervisor_id,
            supervisor_name=supervisor_name,
            content=content,
            action=action,
            selected_team=selected_team,
            selected_agent=selected_agent,
            **kwargs
        )
    
    def create_agent_event(
        self,
        execution_id: str,
        event_type: str,
        agent_id: str,
        agent_name: str,
        team_id: Optional[str] = None,
        content: Optional[str] = None,
        action: Optional[str] = None,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        result: Optional[str] = None,
        **kwargs
    ) -> ExecutionEvent:
        """Create an agent event."""
        return ExecutionEvent(
            timestamp=datetime.now(),
            event_type=event_type,
            source_type="agent",
            execution_id=execution_id,
            team_id=team_id,
            agent_id=agent_id,
            agent_name=agent_name,
            content=content,
            action=action,
            status=status,
            progress=progress,
            result=result,
            **kwargs
        )
    
    async def emit_execution_started(self, execution_id: str, team_id: str) -> None:
        """Emit execution started event."""
        event = self.create_system_event(
            execution_id=execution_id,
            event_type="execution_started",
            content=f"Started execution for team {team_id}",
            status="started"
        )
        await self.emit_event(event)
    
    async def emit_execution_completed(
        self, 
        execution_id: str, 
        status: ExecutionStatus,
        result_url: Optional[str] = None
    ) -> None:
        """Emit execution completed event."""
        event = self.create_system_event(
            execution_id=execution_id,
            event_type="execution_completed",
            content=f"Execution completed with status: {status.value}",
            status=status.value,
            result=result_url
        )
        await self.emit_event(event)
    
    async def emit_supervisor_routing(
        self,
        execution_id: str,
        supervisor_id: str,
        supervisor_name: str,
        team_id: str,
        content: str,
        selected_team: Optional[str] = None,
        selected_agent: Optional[str] = None
    ) -> None:
        """Emit supervisor routing event."""
        event = self.create_supervisor_event(
            execution_id=execution_id,
            event_type="supervisor_routing",
            supervisor_id=supervisor_id,
            supervisor_name=supervisor_name,
            team_id=team_id,
            content=content,
            action="routing",
            selected_team=selected_team,
            selected_agent=selected_agent
        )
        await self.emit_event(event)
    
    async def emit_agent_started(
        self,
        execution_id: str,
        team_id: str,
        agent_id: str,
        agent_name: str,
        content: str
    ) -> None:
        """Emit agent started event."""
        event = self.create_agent_event(
            execution_id=execution_id,
            event_type="agent_started",
            agent_id=agent_id,
            agent_name=agent_name,
            team_id=team_id,
            content=content,
            action="started",
            status="running"
        )
        await self.emit_event(event)
    
    async def emit_agent_progress(
        self,
        execution_id: str,
        team_id: str,
        agent_id: str,
        agent_name: str,
        content: str,
        progress: int
    ) -> None:
        """Emit agent progress event."""
        event = self.create_agent_event(
            execution_id=execution_id,
            event_type="agent_progress",
            agent_id=agent_id,
            agent_name=agent_name,
            team_id=team_id,
            content=content,
            action="progress",
            progress=progress
        )
        await self.emit_event(event)
    
    async def emit_agent_completed(
        self,
        execution_id: str,
        team_id: str,
        agent_id: str,
        agent_name: str,
        result: str
    ) -> None:
        """Emit agent completed event."""
        event = self.create_agent_event(
            execution_id=execution_id,
            event_type="agent_completed",
            agent_id=agent_id,
            agent_name=agent_name,
            team_id=team_id,
            action="completed",
            status="completed",
            result=result
        )
        await self.emit_event(event)
    
    async def emit_team_transition(
        self,
        execution_id: str,
        supervisor_id: str,
        supervisor_name: str,
        from_team: str,
        to_team: str,
        content: str
    ) -> None:
        """Emit team transition event."""
        event = self.create_supervisor_event(
            execution_id=execution_id,
            event_type="team_transition",
            supervisor_id=supervisor_id,
            supervisor_name=supervisor_name,
            content=content,
            action="team_transition"
        )
        # Add custom fields for team transition
        event.selected_team = from_team  # Reuse field for from_team
        event.selected_agent = to_team   # Reuse field for to_team
        await self.emit_event(event)
    
    async def get_subscriber_count(self, execution_id: Optional[str] = None) -> int:
        """Get number of active subscribers for a specific execution."""
        async with self._lock:
            return len(self._execution_subscribers.get(execution_id, set()))
    
    async def get_total_subscriber_count(self) -> int:
        """Get total number of active subscribers."""
        async with self._lock:
            return len(self._subscribers)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get EventManager statistics."""
        async with self._lock:
            total_events = sum(len(events) for events in self._event_buffer.values())
            
            return {
                "total_subscribers": len(self._subscribers),
                "execution_subscriptions": {
                    k: len(v) for k, v in self._execution_subscribers.items()
                },
                "total_buffered_events": total_events,
                "buffer_by_execution": {
                    k: len(v) for k, v in self._event_buffer.items()
                },
                "config": self.config.model_dump()
            }
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup task."""
        while True:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                await self._cleanup_inactive_subscribers()
                await self._cleanup_old_events()
            except asyncio.CancelledError:
                break
            except Exception:
                # Log error in production
                continue
    
    async def _cleanup_inactive_subscribers(self) -> None:
        """Remove inactive subscribers."""
        async with self._lock:
            now = datetime.now()
            inactive_subscribers = []
            
            for subscriber_id, subscriber in self._subscribers.items():
                # Remove subscribers inactive for more than 1 hour
                if (now - subscriber.last_activity).total_seconds() > 3600:
                    inactive_subscribers.append(subscriber_id)
            
            for subscriber_id in inactive_subscribers:
                await self._remove_subscriber(subscriber_id)
    
    async def _cleanup_old_events(self) -> None:
        """Remove old events from buffer."""
        async with self._lock:
            now = datetime.now()
            
            for execution_id, events in list(self._event_buffer.items()):
                # Remove events older than max_event_age
                filtered_events = [
                    event for event in events
                    if (now - event.timestamp).total_seconds() < self.config.max_event_age
                ]
                
                if filtered_events:
                    self._event_buffer[execution_id] = filtered_events
                else:
                    del self._event_buffer[execution_id]


# Utility functions for common operations
async def create_event_manager(
    max_subscribers: int = 100,
    event_buffer_size: int = 1000
) -> EventManager:
    """Create and initialize an EventManager instance."""
    config = EventManagerConfig(
        max_subscribers=max_subscribers,
        event_buffer_size=event_buffer_size
    )
    manager = EventManager(config)
    await manager.initialize()
    return manager


@asynccontextmanager
async def event_manager_context(
    max_subscribers: int = 100,
    event_buffer_size: int = 1000
):
    """Context manager for EventManager operations."""
    manager = await create_event_manager(max_subscribers, event_buffer_size)
    try:
        yield manager
    finally:
        await manager.close()