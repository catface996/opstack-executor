"""
State management for hierarchical multi-agent system.

This module provides state persistence and querying capabilities using Redis
for caching and ensuring data consistency across concurrent operations.
"""

import json
import time
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from contextlib import asynccontextmanager

import redis.asyncio as redis
from pydantic import BaseModel

from .data_models import (
    ExecutionStatus,
    ExecutionEvent,
    TeamState,
    ExecutionContext,
    ExecutionSummary,
    TeamResult,
    StandardizedOutput,
    ErrorInfo,
    ExecutionMetrics
)


class StateManagerConfig(BaseModel):
    """Configuration for StateManager."""
    redis_url: str = "redis://localhost:6379"
    redis_db: int = 0
    key_prefix: str = "hierarchical_agents"
    default_ttl: int = 3600  # 1 hour
    max_retries: int = 3
    retry_delay: float = 0.1


class ExecutionState(BaseModel):
    """Complete execution state."""
    execution_id: str
    team_id: str
    status: ExecutionStatus
    context: ExecutionContext
    events: List[ExecutionEvent]
    team_states: Dict[str, TeamState]
    results: Dict[str, TeamResult]
    summary: Optional[ExecutionSummary] = None
    errors: List[ErrorInfo] = []
    metrics: ExecutionMetrics = ExecutionMetrics()
    created_at: datetime
    updated_at: datetime


class StateManager:
    """
    State manager for hierarchical multi-agent system.
    
    Provides state persistence, querying, and caching using Redis.
    Ensures data consistency and high performance for concurrent operations.
    """
    
    def __init__(self, config: Optional[StateManagerConfig] = None):
        """Initialize StateManager with configuration."""
        self.config = config or StateManagerConfig()
        self._redis: Optional[redis.Redis] = None
        self._lock_timeout = 10  # seconds
        
    async def initialize(self) -> None:
        """Initialize Redis connection."""
        self._redis = redis.from_url(
            self.config.redis_url,
            db=self.config.redis_db,
            decode_responses=True,
            retry_on_timeout=True,
            socket_keepalive=True,
            socket_keepalive_options={}
        )
        
        # Test connection
        try:
            await self._redis.ping()
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Redis: {e}")
    
    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
    
    def _get_key(self, key_type: str, identifier: str) -> str:
        """Generate Redis key with prefix."""
        return f"{self.config.key_prefix}:{key_type}:{identifier}"
    
    def _get_lock_key(self, identifier: str) -> str:
        """Generate lock key for distributed locking."""
        return f"{self.config.key_prefix}:lock:{identifier}"
    
    @asynccontextmanager
    async def _distributed_lock(self, identifier: str):
        """Distributed lock for ensuring data consistency."""
        if not self._redis:
            raise RuntimeError("StateManager not initialized")
        
        lock_key = self._get_lock_key(identifier)
        lock_value = str(time.time())
        acquired = False
        
        try:
            # Try to acquire lock with timeout
            for _ in range(self.config.max_retries):
                acquired = await self._redis.set(
                    lock_key, 
                    lock_value, 
                    nx=True, 
                    ex=self._lock_timeout
                )
                if acquired:
                    break
                await asyncio.sleep(self.config.retry_delay)
            
            if not acquired:
                raise RuntimeError(f"Failed to acquire lock for {identifier}")
            
            yield
            
        finally:
            if acquired:
                # Release lock only if we own it
                lua_script = """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("del", KEYS[1])
                else
                    return 0
                end
                """
                await self._redis.eval(lua_script, 1, lock_key, lock_value)
    
    async def create_execution(
        self, 
        execution_id: str, 
        team_id: str, 
        context: ExecutionContext
    ) -> None:
        """Create a new execution state."""
        if not self._redis:
            raise RuntimeError("StateManager not initialized")
        
        async with self._distributed_lock(execution_id):
            # Check if execution already exists
            existing = await self.get_execution_state(execution_id)
            if existing:
                raise ValueError(f"Execution {execution_id} already exists")
            
            # Create initial state
            now = datetime.now()
            state = ExecutionState(
                execution_id=execution_id,
                team_id=team_id,
                status=ExecutionStatus.PENDING,
                context=context,
                events=[],
                team_states={},
                results={},
                created_at=now,
                updated_at=now
            )
            
            # Store in Redis
            key = self._get_key("execution", execution_id)
            await self._redis.setex(
                key,
                self.config.default_ttl,
                state.model_dump_json()
            )
    
    async def update_execution_status(
        self, 
        execution_id: str, 
        status: ExecutionStatus
    ) -> None:
        """Update execution status."""
        if not self._redis:
            raise RuntimeError("StateManager not initialized")
        
        async with self._distributed_lock(execution_id):
            state = await self.get_execution_state(execution_id)
            if not state:
                raise ValueError(f"Execution {execution_id} not found")
            
            state.status = status
            state.updated_at = datetime.now()
            
            key = self._get_key("execution", execution_id)
            await self._redis.setex(
                key,
                self.config.default_ttl,
                state.model_dump_json()
            )
    
    async def add_event(self, execution_id: str, event: ExecutionEvent) -> None:
        """Add an event to execution state."""
        if not self._redis:
            raise RuntimeError("StateManager not initialized")
        
        async with self._distributed_lock(execution_id):
            state = await self.get_execution_state(execution_id)
            if not state:
                raise ValueError(f"Execution {execution_id} not found")
            
            state.events.append(event)
            state.updated_at = datetime.now()
            
            key = self._get_key("execution", execution_id)
            await self._redis.setex(
                key,
                self.config.default_ttl,
                state.model_dump_json()
            )
    
    async def update_team_state(
        self, 
        execution_id: str, 
        team_id: str, 
        team_state: TeamState
    ) -> None:
        """Update team state within execution."""
        if not self._redis:
            raise RuntimeError("StateManager not initialized")
        
        async with self._distributed_lock(execution_id):
            state = await self.get_execution_state(execution_id)
            if not state:
                raise ValueError(f"Execution {execution_id} not found")
            
            state.team_states[team_id] = team_state
            state.updated_at = datetime.now()
            
            key = self._get_key("execution", execution_id)
            await self._redis.setex(
                key,
                self.config.default_ttl,
                state.model_dump_json()
            )
    
    async def update_team_result(
        self, 
        execution_id: str, 
        team_id: str, 
        result: TeamResult
    ) -> None:
        """Update team result within execution."""
        if not self._redis:
            raise RuntimeError("StateManager not initialized")
        
        async with self._distributed_lock(execution_id):
            state = await self.get_execution_state(execution_id)
            if not state:
                raise ValueError(f"Execution {execution_id} not found")
            
            state.results[team_id] = result
            state.updated_at = datetime.now()
            
            key = self._get_key("execution", execution_id)
            await self._redis.setex(
                key,
                self.config.default_ttl,
                state.model_dump_json()
            )
    
    async def update_execution_summary(
        self, 
        execution_id: str, 
        summary: ExecutionSummary
    ) -> None:
        """Update execution summary."""
        if not self._redis:
            raise RuntimeError("StateManager not initialized")
        
        async with self._distributed_lock(execution_id):
            state = await self.get_execution_state(execution_id)
            if not state:
                raise ValueError(f"Execution {execution_id} not found")
            
            state.summary = summary
            state.updated_at = datetime.now()
            
            key = self._get_key("execution", execution_id)
            await self._redis.setex(
                key,
                self.config.default_ttl,
                state.model_dump_json()
            )
    
    async def add_error(self, execution_id: str, error: ErrorInfo) -> None:
        """Add error to execution state."""
        if not self._redis:
            raise RuntimeError("StateManager not initialized")
        
        async with self._distributed_lock(execution_id):
            state = await self.get_execution_state(execution_id)
            if not state:
                raise ValueError(f"Execution {execution_id} not found")
            
            state.errors.append(error)
            state.updated_at = datetime.now()
            
            key = self._get_key("execution", execution_id)
            await self._redis.setex(
                key,
                self.config.default_ttl,
                state.model_dump_json()
            )
    
    async def update_metrics(
        self, 
        execution_id: str, 
        metrics: ExecutionMetrics
    ) -> None:
        """Update execution metrics."""
        if not self._redis:
            raise RuntimeError("StateManager not initialized")
        
        async with self._distributed_lock(execution_id):
            state = await self.get_execution_state(execution_id)
            if not state:
                raise ValueError(f"Execution {execution_id} not found")
            
            state.metrics = metrics
            state.updated_at = datetime.now()
            
            key = self._get_key("execution", execution_id)
            await self._redis.setex(
                key,
                self.config.default_ttl,
                state.model_dump_json()
            )
    
    async def get_execution_state(self, execution_id: str) -> Optional[ExecutionState]:
        """Get complete execution state."""
        if not self._redis:
            raise RuntimeError("StateManager not initialized")
        
        start_time = time.time()
        
        key = self._get_key("execution", execution_id)
        data = await self._redis.get(key)
        
        query_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        if not data:
            return None
        
        try:
            state_dict = json.loads(data)
            return ExecutionState.model_validate(state_dict)
        except Exception as e:
            raise ValueError(f"Failed to deserialize execution state: {e}")
    
    async def get_execution_status(self, execution_id: str) -> Optional[ExecutionStatus]:
        """Get execution status quickly."""
        state = await self.get_execution_state(execution_id)
        return state.status if state else None
    
    async def get_execution_events(
        self, 
        execution_id: str, 
        limit: Optional[int] = None
    ) -> List[ExecutionEvent]:
        """Get execution events."""
        state = await self.get_execution_state(execution_id)
        if not state:
            return []
        
        events = state.events
        if limit:
            events = events[-limit:]  # Get most recent events
        
        return events
    
    async def get_team_state(
        self, 
        execution_id: str, 
        team_id: str
    ) -> Optional[TeamState]:
        """Get specific team state."""
        state = await self.get_execution_state(execution_id)
        if not state:
            return None
        
        return state.team_states.get(team_id)
    
    async def get_team_result(
        self, 
        execution_id: str, 
        team_id: str
    ) -> Optional[TeamResult]:
        """Get specific team result."""
        state = await self.get_execution_state(execution_id)
        if not state:
            return None
        
        return state.results.get(team_id)
    
    async def get_standardized_output(
        self, 
        execution_id: str
    ) -> Optional[StandardizedOutput]:
        """Get standardized output format."""
        state = await self.get_execution_state(execution_id)
        if not state or not state.summary:
            return None
        
        return StandardizedOutput(
            execution_id=execution_id,
            execution_summary=state.summary,
            team_results=state.results,
            errors=state.errors,
            metrics=state.metrics
        )
    
    async def list_executions(
        self, 
        team_id: Optional[str] = None,
        status: Optional[ExecutionStatus] = None,
        limit: int = 100
    ) -> List[str]:
        """List execution IDs with optional filtering."""
        if not self._redis:
            raise RuntimeError("StateManager not initialized")
        
        pattern = self._get_key("execution", "*")
        keys = await self._redis.keys(pattern)
        
        execution_ids = []
        for key in keys[:limit]:  # Limit to prevent memory issues
            execution_id = key.split(":")[-1]
            
            # Apply filters if specified
            if team_id or status:
                state = await self.get_execution_state(execution_id)
                if not state:
                    continue
                
                if team_id and state.team_id != team_id:
                    continue
                
                if status and state.status != status:
                    continue
            
            execution_ids.append(execution_id)
        
        return execution_ids
    
    async def delete_execution(self, execution_id: str) -> bool:
        """Delete execution state."""
        if not self._redis:
            raise RuntimeError("StateManager not initialized")
        
        async with self._distributed_lock(execution_id):
            key = self._get_key("execution", execution_id)
            result = await self._redis.delete(key)
            return result > 0
    
    async def cleanup_expired_executions(self) -> int:
        """Clean up expired executions (manual cleanup for debugging)."""
        if not self._redis:
            raise RuntimeError("StateManager not initialized")
        
        pattern = self._get_key("execution", "*")
        keys = await self._redis.keys(pattern)
        
        deleted_count = 0
        for key in keys:
            ttl = await self._redis.ttl(key)
            if ttl == -1:  # Key exists but has no expiration
                # Set expiration for keys without TTL
                await self._redis.expire(key, self.config.default_ttl)
            elif ttl == -2:  # Key doesn't exist
                deleted_count += 1
        
        return deleted_count
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get StateManager statistics."""
        if not self._redis:
            raise RuntimeError("StateManager not initialized")
        
        pattern = self._get_key("execution", "*")
        keys = await self._redis.keys(pattern)
        
        stats = {
            "total_executions": len(keys),
            "redis_info": await self._redis.info("memory"),
            "config": self.config.model_dump()
        }
        
        # Count by status
        status_counts = {}
        for key in keys[:50]:  # Limit to prevent performance issues
            execution_id = key.split(":")[-1]
            state = await self.get_execution_state(execution_id)
            if state:
                status = state.status.value
                status_counts[status] = status_counts.get(status, 0) + 1
        
        stats["status_distribution"] = status_counts
        
        return stats


# Utility functions for common operations
async def create_state_manager(
    redis_url: str = "redis://localhost:6379",
    redis_db: int = 0
) -> StateManager:
    """Create and initialize a StateManager instance."""
    config = StateManagerConfig(redis_url=redis_url, redis_db=redis_db)
    manager = StateManager(config)
    await manager.initialize()
    return manager


async def with_state_manager(
    func,
    redis_url: str = "redis://localhost:6379",
    redis_db: int = 0
):
    """Context manager for StateManager operations."""
    manager = await create_state_manager(redis_url, redis_db)
    try:
        return await func(manager)
    finally:
        await manager.close()