"""
Logging and monitoring framework for the hierarchical multi-agent system.

This module provides comprehensive logging and monitoring capabilities including:
- Structured JSON logging with proper log levels
- Execution metrics collection and statistics
- Audit logging for critical operations
- Performance monitoring and alerting
- Integration with external monitoring systems
"""

import json
import logging
import logging.handlers
import time
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from contextlib import contextmanager
import threading
from collections import defaultdict, deque

from .data_models import ExecutionEvent, ExecutionMetrics, ErrorInfo


class LogLevel(str, Enum):
    """Log levels for structured logging."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AuditEventType(str, Enum):
    """Types of audit events."""
    TEAM_CREATED = "team_created"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    AGENT_INVOKED = "agent_invoked"
    SUPERVISOR_ROUTING = "supervisor_routing"
    ERROR_OCCURRED = "error_occurred"
    CONFIGURATION_CHANGED = "configuration_changed"
    API_KEY_ACCESSED = "api_key_accessed"
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"


@dataclass
class LogEntry:
    """Structured log entry."""
    timestamp: datetime
    level: LogLevel
    logger_name: str
    message: str
    execution_id: Optional[str] = None
    team_id: Optional[str] = None
    agent_id: Optional[str] = None
    supervisor_id: Optional[str] = None
    operation: Optional[str] = None
    duration_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert log entry to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "logger": self.logger_name,
            "message": self.message,
            "execution_id": self.execution_id,
            "team_id": self.team_id,
            "agent_id": self.agent_id,
            "supervisor_id": self.supervisor_id,
            "operation": self.operation,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata
        }
    
    def to_json(self) -> str:
        """Convert log entry to JSON string."""
        return json.dumps(self.to_dict(), default=str, ensure_ascii=False)


@dataclass
class AuditEntry:
    """Audit log entry for critical operations."""
    timestamp: datetime
    event_type: AuditEventType
    user_id: Optional[str]
    execution_id: Optional[str]
    resource_id: Optional[str]
    action: str
    result: str  # success, failure, partial
    details: Dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert audit entry to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "user_id": self.user_id,
            "execution_id": self.execution_id,
            "resource_id": self.resource_id,
            "action": self.action,
            "result": self.result,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent
        }
    
    def to_json(self) -> str:
        """Convert audit entry to JSON string."""
        return json.dumps(self.to_dict(), default=str, ensure_ascii=False)


@dataclass
class MetricPoint:
    """Single metric data point."""
    timestamp: datetime
    name: str
    value: Union[int, float]
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metric point to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "name": self.name,
            "value": self.value,
            "tags": self.tags
        }


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def __init__(self, include_metadata: bool = True):
        """Initialize JSON formatter."""
        super().__init__()
        self.include_metadata = include_metadata
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Extract custom fields from record
        execution_id = getattr(record, 'execution_id', None)
        team_id = getattr(record, 'team_id', None)
        agent_id = getattr(record, 'agent_id', None)
        supervisor_id = getattr(record, 'supervisor_id', None)
        operation = getattr(record, 'operation', None)
        duration_ms = getattr(record, 'duration_ms', None)
        
        # Build metadata from extra fields
        metadata = {}
        if self.include_metadata:
            for key, value in record.__dict__.items():
                if key not in {
                    'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                    'filename', 'module', 'lineno', 'funcName', 'created',
                    'msecs', 'relativeCreated', 'thread', 'threadName',
                    'processName', 'process', 'message', 'exc_info', 'exc_text',
                    'stack_info', 'execution_id', 'team_id', 'agent_id',
                    'supervisor_id', 'operation', 'duration_ms'
                }:
                    metadata[key] = value
        
        # Create structured log entry
        log_entry = LogEntry(
            timestamp=datetime.fromtimestamp(record.created),
            level=LogLevel(record.levelname),
            logger_name=record.name,
            message=record.getMessage(),
            execution_id=execution_id,
            team_id=team_id,
            agent_id=agent_id,
            supervisor_id=supervisor_id,
            operation=operation,
            duration_ms=duration_ms,
            metadata=metadata
        )
        
        return log_entry.to_json()


class MetricsCollector:
    """Collector for execution metrics and statistics."""
    
    def __init__(self, max_history_size: int = 10000):
        """Initialize metrics collector."""
        self.max_history_size = max_history_size
        self.metrics_history: deque = deque(maxlen=max_history_size)
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.timers: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()
    
    def increment_counter(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter metric."""
        with self._lock:
            key = self._make_key(name, tags or {})
            self.counters[key] += value
            
            # Record metric point
            self.metrics_history.append(MetricPoint(
                timestamp=datetime.now(),
                name=name,
                value=self.counters[key],
                tags=tags or {}
            ))
    
    def set_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric value."""
        with self._lock:
            key = self._make_key(name, tags or {})
            self.gauges[key] = value
            
            # Record metric point
            self.metrics_history.append(MetricPoint(
                timestamp=datetime.now(),
                name=name,
                value=value,
                tags=tags or {}
            ))
    
    def record_histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record a value in a histogram."""
        with self._lock:
            key = self._make_key(name, tags or {})
            self.histograms[key].append(value)
            
            # Keep only recent values to prevent memory growth
            if len(self.histograms[key]) > 1000:
                self.histograms[key] = self.histograms[key][-1000:]
            
            # Record metric point
            self.metrics_history.append(MetricPoint(
                timestamp=datetime.now(),
                name=name,
                value=value,
                tags=tags or {}
            ))
    
    def record_timer(self, name: str, duration_ms: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record a timing measurement."""
        with self._lock:
            key = self._make_key(name, tags or {})
            self.timers[key].append(duration_ms)
            
            # Keep only recent values
            if len(self.timers[key]) > 1000:
                self.timers[key] = self.timers[key][-1000:]
            
            # Record metric point
            self.metrics_history.append(MetricPoint(
                timestamp=datetime.now(),
                name=f"{name}.duration",
                value=duration_ms,
                tags=tags or {}
            ))
    
    def get_counter(self, name: str, tags: Optional[Dict[str, str]] = None) -> int:
        """Get current counter value."""
        with self._lock:
            key = self._make_key(name, tags or {})
            return self.counters.get(key, 0)
    
    def get_gauge(self, name: str, tags: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get current gauge value."""
        with self._lock:
            key = self._make_key(name, tags or {})
            return self.gauges.get(key)
    
    def get_histogram_stats(self, name: str, tags: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """Get histogram statistics."""
        with self._lock:
            key = self._make_key(name, tags or {})
            values = self.histograms.get(key, [])
            
            if not values:
                return {}
            
            sorted_values = sorted(values)
            count = len(sorted_values)
            
            def percentile(p: float) -> float:
                """Calculate percentile value."""
                if count == 1:
                    return sorted_values[0]
                index = (count - 1) * p
                lower = int(index)
                upper = min(lower + 1, count - 1)
                weight = index - lower
                return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
            
            return {
                "count": count,
                "min": sorted_values[0],
                "max": sorted_values[-1],
                "mean": sum(sorted_values) / count,
                "p50": percentile(0.5),
                "p90": percentile(0.9),
                "p95": percentile(0.95),
                "p99": percentile(0.99)
            }
    
    def get_timer_stats(self, name: str, tags: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """Get timer statistics."""
        with self._lock:
            key = self._make_key(name, tags or {})
            return self.get_histogram_stats(name, tags)
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all current metrics."""
        with self._lock:
            # For performance, return raw counts instead of computing stats for all histograms/timers
            histogram_counts = {k: len(v) for k, v in self.histograms.items()}
            timer_counts = {k: len(v) for k, v in self.timers.items()}
            
            return {
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "histograms": histogram_counts,
                "timers": timer_counts
            }
    
    def reset_metrics(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self.counters.clear()
            self.gauges.clear()
            self.histograms.clear()
            self.timers.clear()
            self.metrics_history.clear()
    
    def _make_key(self, name: str, tags: Dict[str, str]) -> str:
        """Create a key from metric name and tags."""
        if not tags:
            return name
        
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}|{tag_str}"
    
    def _parse_tags(self, tag_str: str) -> Dict[str, str]:
        """Parse tags from string."""
        if not tag_str:
            return {}
        
        tags = {}
        for pair in tag_str.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                tags[k] = v
        return tags


class LoggingMonitor:
    """
    Main logging and monitoring system for the hierarchical multi-agent system.
    
    Provides structured logging, metrics collection, audit logging, and monitoring
    capabilities with proper log levels and JSON formatting.
    """
    
    def __init__(
        self,
        log_dir: Optional[Path] = None,
        log_level: LogLevel = LogLevel.INFO,
        enable_console_logging: bool = True,
        enable_file_logging: bool = True,
        enable_audit_logging: bool = True,
        max_log_file_size: int = 10 * 1024 * 1024,  # 10MB
        max_log_files: int = 5
    ):
        """Initialize the logging and monitoring system."""
        self.log_dir = log_dir or Path("logs")
        self.log_level = log_level
        self.enable_console_logging = enable_console_logging
        self.enable_file_logging = enable_file_logging
        self.enable_audit_logging = enable_audit_logging
        
        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.metrics_collector = MetricsCollector()
        self.audit_entries: List[AuditEntry] = []
        self._setup_logging(max_log_file_size, max_log_files)
        
        # Create specialized loggers
        self.system_logger = logging.getLogger("hierarchical_agents.system")
        self.execution_logger = logging.getLogger("hierarchical_agents.execution")
        self.agent_logger = logging.getLogger("hierarchical_agents.agent")
        self.supervisor_logger = logging.getLogger("hierarchical_agents.supervisor")
        self.api_logger = logging.getLogger("hierarchical_agents.api")
        self.audit_logger = logging.getLogger("hierarchical_agents.audit")
        
        # Log system startup
        self.log_audit_event(
            event_type=AuditEventType.SYSTEM_STARTUP,
            action="system_startup",
            result="success",
            details={"log_level": log_level.value, "log_dir": str(self.log_dir)}
        )
    
    def _setup_logging(self, max_file_size: int, max_files: int) -> None:
        """Set up logging configuration."""
        # Create JSON formatter
        json_formatter = JSONFormatter(include_metadata=True)
        
        # Configure root logger
        root_logger = logging.getLogger("hierarchical_agents")
        root_logger.setLevel(getattr(logging, self.log_level.value))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Console handler
        if self.enable_console_logging:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(json_formatter)
            console_handler.setLevel(getattr(logging, self.log_level.value))
            root_logger.addHandler(console_handler)
        
        # File handler for general logs
        if self.enable_file_logging:
            log_file = self.log_dir / "hierarchical_agents.log"
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_file_size,
                backupCount=max_files,
                encoding='utf-8'
            )
            file_handler.setFormatter(json_formatter)
            file_handler.setLevel(getattr(logging, self.log_level.value))
            root_logger.addHandler(file_handler)
        
        # Separate audit log file
        if self.enable_audit_logging:
            audit_file = self.log_dir / "audit.log"
            audit_handler = logging.handlers.RotatingFileHandler(
                audit_file,
                maxBytes=max_file_size,
                backupCount=max_files,
                encoding='utf-8'
            )
            audit_handler.setFormatter(json_formatter)
            audit_handler.setLevel(logging.INFO)
            
            # Create audit logger
            audit_logger = logging.getLogger("hierarchical_agents.audit")
            audit_logger.addHandler(audit_handler)
            audit_logger.setLevel(logging.INFO)
            audit_logger.propagate = False  # Don't propagate to root logger
    
    def log_system_event(
        self,
        message: str,
        level: LogLevel = LogLevel.INFO,
        operation: Optional[str] = None,
        duration_ms: Optional[float] = None,
        **metadata
    ) -> None:
        """Log a system-level event."""
        self._log_with_context(
            self.system_logger,
            level,
            message,
            operation=operation,
            duration_ms=duration_ms,
            **metadata
        )
    
    def log_execution_event(
        self,
        message: str,
        execution_id: str,
        level: LogLevel = LogLevel.INFO,
        team_id: Optional[str] = None,
        operation: Optional[str] = None,
        duration_ms: Optional[float] = None,
        **metadata
    ) -> None:
        """Log an execution-related event."""
        self._log_with_context(
            self.execution_logger,
            level,
            message,
            execution_id=execution_id,
            team_id=team_id,
            operation=operation,
            duration_ms=duration_ms,
            **metadata
        )
        
        # Update execution metrics
        self.metrics_collector.increment_counter(
            "execution.events",
            tags={"level": level.value, "team_id": team_id or "unknown"}
        )
    
    def log_agent_event(
        self,
        message: str,
        agent_id: str,
        level: LogLevel = LogLevel.INFO,
        execution_id: Optional[str] = None,
        team_id: Optional[str] = None,
        operation: Optional[str] = None,
        duration_ms: Optional[float] = None,
        **metadata
    ) -> None:
        """Log an agent-related event."""
        self._log_with_context(
            self.agent_logger,
            level,
            message,
            execution_id=execution_id,
            team_id=team_id,
            agent_id=agent_id,
            operation=operation,
            duration_ms=duration_ms,
            **metadata
        )
        
        # Update agent metrics
        self.metrics_collector.increment_counter(
            "agent.events",
            tags={"level": level.value, "agent_id": agent_id}
        )
        
        if duration_ms is not None:
            self.metrics_collector.record_timer(
                "agent.operation_duration",
                duration_ms,
                tags={"agent_id": agent_id, "operation": operation or "unknown"}
            )
    
    def log_supervisor_event(
        self,
        message: str,
        supervisor_id: str,
        level: LogLevel = LogLevel.INFO,
        execution_id: Optional[str] = None,
        team_id: Optional[str] = None,
        operation: Optional[str] = None,
        duration_ms: Optional[float] = None,
        **metadata
    ) -> None:
        """Log a supervisor-related event."""
        self._log_with_context(
            self.supervisor_logger,
            level,
            message,
            execution_id=execution_id,
            team_id=team_id,
            supervisor_id=supervisor_id,
            operation=operation,
            duration_ms=duration_ms,
            **metadata
        )
        
        # Update supervisor metrics
        self.metrics_collector.increment_counter(
            "supervisor.events",
            tags={"level": level.value, "supervisor_id": supervisor_id}
        )
        
        if duration_ms is not None:
            self.metrics_collector.record_timer(
                "supervisor.operation_duration",
                duration_ms,
                tags={"supervisor_id": supervisor_id, "operation": operation or "unknown"}
            )
    
    def log_api_event(
        self,
        message: str,
        endpoint: str,
        method: str,
        status_code: int,
        level: LogLevel = LogLevel.INFO,
        duration_ms: Optional[float] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        **metadata
    ) -> None:
        """Log an API-related event."""
        self._log_with_context(
            self.api_logger,
            level,
            message,
            operation=f"{method} {endpoint}",
            duration_ms=duration_ms,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            user_id=user_id,
            ip_address=ip_address,
            **metadata
        )
        
        # Update API metrics
        self.metrics_collector.increment_counter(
            "api.requests",
            tags={
                "endpoint": endpoint,
                "method": method,
                "status_code": str(status_code)
            }
        )
        
        if duration_ms is not None:
            self.metrics_collector.record_timer(
                "api.response_time",
                duration_ms,
                tags={"endpoint": endpoint, "method": method}
            )
    
    def log_error_event(
        self,
        error: Exception,
        error_info: ErrorInfo,
        execution_id: Optional[str] = None,
        team_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        supervisor_id: Optional[str] = None,
        **metadata
    ) -> None:
        """Log an error event."""
        self._log_with_context(
            self.system_logger,
            LogLevel.ERROR,
            f"Error occurred: {error}",
            execution_id=execution_id,
            team_id=team_id,
            agent_id=agent_id,
            supervisor_id=supervisor_id,
            operation="error_handling",
            error_code=error_info.error_code,
            error_type=type(error).__name__,
            **metadata
        )
        
        # Update error metrics
        self.metrics_collector.increment_counter(
            "errors.total",
            tags={
                "error_type": type(error).__name__,
                "error_code": error_info.error_code
            }
        )
        
        # Log audit event for errors
        self.log_audit_event(
            event_type=AuditEventType.ERROR_OCCURRED,
            action="error_occurred",
            result="failure",
            execution_id=execution_id,
            details={
                "error_type": type(error).__name__,
                "error_code": error_info.error_code,
                "error_message": str(error),
                "team_id": team_id,
                "agent_id": agent_id,
                "supervisor_id": supervisor_id
            }
        )
    
    def log_audit_event(
        self,
        event_type: AuditEventType,
        action: str,
        result: str,
        user_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """Log an audit event."""
        audit_entry = AuditEntry(
            timestamp=datetime.now(),
            event_type=event_type,
            user_id=user_id,
            execution_id=execution_id,
            resource_id=resource_id,
            action=action,
            result=result,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Store audit entry
        self.audit_entries.append(audit_entry)
        
        # Log to audit logger
        self.audit_logger.info(
            f"Audit: {event_type.value} - {action} ({result})",
            extra={
                "audit_event": audit_entry.to_dict(),
                "event_type": event_type.value,
                "action": action,
                "result": result,
                "user_id": user_id,
                "execution_id": execution_id,
                "resource_id": resource_id
            }
        )
        
        # Update audit metrics
        self.metrics_collector.increment_counter(
            "audit.events",
            tags={
                "event_type": event_type.value,
                "result": result
            }
        )
    
    @contextmanager
    def time_operation(
        self,
        operation_name: str,
        logger_type: str = "system",
        level: LogLevel = LogLevel.INFO,
        execution_id: Optional[str] = None,
        team_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        supervisor_id: Optional[str] = None
    ):
        """Context manager for timing operations."""
        start_time = time.time()
        
        try:
            yield
            duration_ms = (time.time() - start_time) * 1000
            
            # Log successful operation
            if logger_type == "execution":
                self.log_execution_event(
                    f"Operation {operation_name} completed successfully",
                    execution_id=execution_id or "unknown",
                    level=level,
                    team_id=team_id,
                    operation=operation_name,
                    duration_ms=duration_ms
                )
            elif logger_type == "agent":
                self.log_agent_event(
                    f"Agent operation {operation_name} completed successfully",
                    agent_id=agent_id or "unknown",
                    level=level,
                    execution_id=execution_id,
                    team_id=team_id,
                    operation=operation_name,
                    duration_ms=duration_ms
                )
            elif logger_type == "supervisor":
                self.log_supervisor_event(
                    f"Supervisor operation {operation_name} completed successfully",
                    supervisor_id=supervisor_id or "unknown",
                    level=level,
                    execution_id=execution_id,
                    team_id=team_id,
                    operation=operation_name,
                    duration_ms=duration_ms
                )
            else:
                self.log_system_event(
                    f"Operation {operation_name} completed successfully",
                    level=level,
                    operation=operation_name,
                    duration_ms=duration_ms
                )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            # Log failed operation
            if logger_type == "execution":
                self.log_execution_event(
                    f"Operation {operation_name} failed: {e}",
                    execution_id=execution_id or "unknown",
                    level=LogLevel.ERROR,
                    team_id=team_id,
                    operation=operation_name,
                    duration_ms=duration_ms,
                    error=str(e)
                )
            elif logger_type == "agent":
                self.log_agent_event(
                    f"Agent operation {operation_name} failed: {e}",
                    agent_id=agent_id or "unknown",
                    level=LogLevel.ERROR,
                    execution_id=execution_id,
                    team_id=team_id,
                    operation=operation_name,
                    duration_ms=duration_ms,
                    error=str(e)
                )
            elif logger_type == "supervisor":
                self.log_supervisor_event(
                    f"Supervisor operation {operation_name} failed: {e}",
                    supervisor_id=supervisor_id or "unknown",
                    level=LogLevel.ERROR,
                    execution_id=execution_id,
                    team_id=team_id,
                    operation=operation_name,
                    duration_ms=duration_ms,
                    error=str(e)
                )
            else:
                self.log_system_event(
                    f"Operation {operation_name} failed: {e}",
                    level=LogLevel.ERROR,
                    operation=operation_name,
                    duration_ms=duration_ms,
                    error=str(e)
                )
            
            raise
    
    def _log_with_context(
        self,
        logger: logging.Logger,
        level: LogLevel,
        message: str,
        execution_id: Optional[str] = None,
        team_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        supervisor_id: Optional[str] = None,
        operation: Optional[str] = None,
        duration_ms: Optional[float] = None,
        **metadata
    ) -> None:
        """Log with structured context."""
        log_level = getattr(logging, level.value)
        
        # Create extra context for the log record
        extra = {
            "execution_id": execution_id,
            "team_id": team_id,
            "agent_id": agent_id,
            "supervisor_id": supervisor_id,
            "operation": operation,
            "duration_ms": duration_ms,
            **metadata
        }
        
        logger.log(log_level, message, extra=extra)
    
    def get_execution_metrics(self, execution_id: str) -> ExecutionMetrics:
        """Get metrics for a specific execution."""
        # This would typically query stored metrics for the execution
        # For now, return current aggregate metrics
        all_metrics = self.metrics_collector.get_all_metrics()
        
        return ExecutionMetrics(
            total_tokens_used=self.metrics_collector.get_counter("tokens.used"),
            api_calls_made=self.metrics_collector.get_counter("api.calls"),
            success_rate=self._calculate_success_rate(),
            average_response_time=self._calculate_average_response_time()
        )
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get comprehensive system metrics."""
        return {
            "metrics": self.metrics_collector.get_all_metrics(),
            "audit_events_count": len(self.audit_entries),
            "recent_errors": self.metrics_collector.get_counter("errors.total"),
            "uptime_seconds": self._get_uptime_seconds(),
            "log_files": self._get_log_file_info()
        }
    
    def get_audit_trail(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_type: Optional[AuditEventType] = None,
        user_id: Optional[str] = None,
        execution_id: Optional[str] = None
    ) -> List[AuditEntry]:
        """Get filtered audit trail."""
        filtered_entries = self.audit_entries
        
        if start_time:
            filtered_entries = [e for e in filtered_entries if e.timestamp >= start_time]
        
        if end_time:
            filtered_entries = [e for e in filtered_entries if e.timestamp <= end_time]
        
        if event_type:
            filtered_entries = [e for e in filtered_entries if e.event_type == event_type]
        
        if user_id:
            filtered_entries = [e for e in filtered_entries if e.user_id == user_id]
        
        if execution_id:
            filtered_entries = [e for e in filtered_entries if e.execution_id == execution_id]
        
        return filtered_entries
    
    def _calculate_success_rate(self) -> float:
        """Calculate overall success rate."""
        total_operations = self.metrics_collector.get_counter("operations.total")
        failed_operations = self.metrics_collector.get_counter("operations.failed")
        
        if total_operations == 0:
            return 1.0
        
        return (total_operations - failed_operations) / total_operations
    
    def _calculate_average_response_time(self) -> float:
        """Calculate average response time."""
        timer_stats = self.metrics_collector.get_timer_stats("api.response_time")
        return timer_stats.get("mean", 0.0)
    
    def _get_uptime_seconds(self) -> float:
        """Get system uptime in seconds."""
        # This would typically track actual startup time
        # For now, return a placeholder
        return 0.0
    
    def _get_log_file_info(self) -> Dict[str, Any]:
        """Get information about log files."""
        log_files = {}
        
        for log_file in self.log_dir.glob("*.log"):
            try:
                stat = log_file.stat()
                log_files[log_file.name] = {
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                }
            except Exception:
                pass
        
        return log_files
    
    def shutdown(self) -> None:
        """Shutdown the logging and monitoring system."""
        self.log_audit_event(
            event_type=AuditEventType.SYSTEM_SHUTDOWN,
            action="system_shutdown",
            result="success",
            details={"total_audit_events": len(self.audit_entries)}
        )
        
        # Close all handlers
        for handler in logging.getLogger("hierarchical_agents").handlers:
            handler.close()


# Global logging monitor instance
_global_monitor: Optional[LoggingMonitor] = None


def get_logging_monitor() -> LoggingMonitor:
    """Get the global logging monitor instance."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = LoggingMonitor()
    return _global_monitor


def initialize_logging_monitor(
    log_dir: Optional[Path] = None,
    log_level: LogLevel = LogLevel.INFO,
    **kwargs
) -> LoggingMonitor:
    """Initialize the global logging monitor."""
    global _global_monitor
    _global_monitor = LoggingMonitor(log_dir=log_dir, log_level=log_level, **kwargs)
    return _global_monitor


# Convenience functions for common logging operations
def log_system(message: str, level: LogLevel = LogLevel.INFO, **kwargs) -> None:
    """Log a system event."""
    get_logging_monitor().log_system_event(message, level, **kwargs)


def log_execution(message: str, execution_id: str, level: LogLevel = LogLevel.INFO, **kwargs) -> None:
    """Log an execution event."""
    get_logging_monitor().log_execution_event(message, execution_id, level, **kwargs)


def log_agent(message: str, agent_id: str, level: LogLevel = LogLevel.INFO, **kwargs) -> None:
    """Log an agent event."""
    get_logging_monitor().log_agent_event(message, agent_id, level, **kwargs)


def log_supervisor(message: str, supervisor_id: str, level: LogLevel = LogLevel.INFO, **kwargs) -> None:
    """Log a supervisor event."""
    get_logging_monitor().log_supervisor_event(message, supervisor_id, level, **kwargs)


def log_api(message: str, endpoint: str, method: str, status_code: int, level: LogLevel = LogLevel.INFO, **kwargs) -> None:
    """Log an API event."""
    get_logging_monitor().log_api_event(message, endpoint, method, status_code, level, **kwargs)


def log_audit(event_type: AuditEventType, action: str, result: str, **kwargs) -> None:
    """Log an audit event."""
    get_logging_monitor().log_audit_event(event_type, action, result, **kwargs)