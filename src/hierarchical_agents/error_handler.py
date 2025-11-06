"""
Error handling framework for the hierarchical multi-agent system.

This module provides comprehensive error handling capabilities including:
- Error classification and categorization
- Retry mechanisms with exponential backoff
- Graceful degradation strategies
- Error propagation and context preservation
- Recovery mechanisms for different failure scenarios
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union
from dataclasses import dataclass, field

from .data_models import ErrorInfo


class ErrorCategory(str, Enum):
    """Categories of errors that can occur in the system."""
    AGENT_ERROR = "agent_error"
    NETWORK_ERROR = "network_error"
    SUPERVISOR_ERROR = "supervisor_error"
    SYSTEM_ERROR = "system_error"
    CONFIGURATION_ERROR = "configuration_error"
    AUTHENTICATION_ERROR = "authentication_error"
    TIMEOUT_ERROR = "timeout_error"
    RESOURCE_ERROR = "resource_error"


class ErrorSeverity(str, Enum):
    """Severity levels for errors."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecoveryStrategy(str, Enum):
    """Recovery strategies for different error types."""
    RETRY = "retry"
    FALLBACK = "fallback"
    DEGRADE = "degrade"
    FAIL_FAST = "fail_fast"
    IGNORE = "ignore"


@dataclass
class ErrorContext:
    """Context information for error handling."""
    execution_id: str
    team_id: Optional[str] = None
    agent_id: Optional[str] = None
    supervisor_id: Optional[str] = None
    operation: Optional[str] = None
    attempt_count: int = 0
    max_attempts: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetryConfig:
    """Configuration for retry mechanisms."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    backoff_strategy: str = "exponential"  # exponential, linear, fixed


@dataclass
class ErrorRule:
    """Rule for handling specific error types."""
    error_types: List[Type[Exception]]
    category: ErrorCategory
    severity: ErrorSeverity
    recovery_strategy: RecoveryStrategy
    retry_config: Optional[RetryConfig] = None
    fallback_handler: Optional[Callable] = None
    should_propagate: bool = True
    custom_handler: Optional[Callable] = None


class ErrorHandler:
    """
    Comprehensive error handler for the hierarchical multi-agent system.
    
    Provides error classification, retry mechanisms, graceful degradation,
    and recovery strategies for different types of failures.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the error handler."""
        self.logger = logger or logging.getLogger(__name__)
        self.error_rules: List[ErrorRule] = []
        self.error_history: List[ErrorInfo] = []
        self.circuit_breakers: Dict[str, 'CircuitBreaker'] = {}
        self._setup_default_rules()
    
    def _setup_default_rules(self) -> None:
        """Set up default error handling rules."""
        # Network and connection errors - retry with backoff
        self.add_error_rule(ErrorRule(
            error_types=[ConnectionError, TimeoutError, OSError],
            category=ErrorCategory.NETWORK_ERROR,
            severity=ErrorSeverity.MEDIUM,
            recovery_strategy=RecoveryStrategy.RETRY,
            retry_config=RetryConfig(max_attempts=3, base_delay=1.0),
            should_propagate=True
        ))
        
        # Authentication errors - fail fast
        self.add_error_rule(ErrorRule(
            error_types=[PermissionError],
            category=ErrorCategory.AUTHENTICATION_ERROR,
            severity=ErrorSeverity.HIGH,
            recovery_strategy=RecoveryStrategy.FAIL_FAST,
            should_propagate=True
        ))
        
        # Configuration errors - fail fast
        self.add_error_rule(ErrorRule(
            error_types=[ValueError, KeyError],
            category=ErrorCategory.CONFIGURATION_ERROR,
            severity=ErrorSeverity.HIGH,
            recovery_strategy=RecoveryStrategy.FAIL_FAST,
            should_propagate=True
        ))
        
        # Resource errors - degrade gracefully
        self.add_error_rule(ErrorRule(
            error_types=[MemoryError, FileNotFoundError],
            category=ErrorCategory.RESOURCE_ERROR,
            severity=ErrorSeverity.HIGH,
            recovery_strategy=RecoveryStrategy.DEGRADE,
            should_propagate=True
        ))
        
        # Generic system errors - retry with fallback
        self.add_error_rule(ErrorRule(
            error_types=[RuntimeError, Exception],
            category=ErrorCategory.SYSTEM_ERROR,
            severity=ErrorSeverity.MEDIUM,
            recovery_strategy=RecoveryStrategy.RETRY,
            retry_config=RetryConfig(max_attempts=2, base_delay=0.5),
            should_propagate=True
        ))
    
    def add_error_rule(self, rule: ErrorRule) -> None:
        """Add a new error handling rule."""
        self.error_rules.append(rule)
    
    def classify_error(self, error: Exception) -> ErrorRule:
        """Classify an error and return the appropriate handling rule."""
        # Find the most specific matching rule, with later rules taking precedence
        best_match = None
        best_specificity = -1
        best_rule_index = -1
        
        for rule_index, rule in enumerate(self.error_rules):
            for error_type in rule.error_types:
                if isinstance(error, error_type):
                    # Calculate specificity based on inheritance hierarchy
                    specificity = self._calculate_specificity(type(error), error_type)
                    
                    # If specificity is equal, prefer later-added rules (higher index)
                    if (specificity > best_specificity or 
                        (specificity == best_specificity and rule_index > best_rule_index)):
                        best_specificity = specificity
                        best_rule_index = rule_index
                        best_match = rule
        
        if best_match:
            return best_match
        
        # Default rule for unclassified errors
        return ErrorRule(
            error_types=[Exception],
            category=ErrorCategory.SYSTEM_ERROR,
            severity=ErrorSeverity.MEDIUM,
            recovery_strategy=RecoveryStrategy.RETRY,
            retry_config=RetryConfig(max_attempts=1),
            should_propagate=True
        )
    
    def _calculate_specificity(self, actual_type: type, rule_type: type) -> int:
        """Calculate specificity of a rule match based on inheritance hierarchy."""
        if actual_type == rule_type:
            return 1000  # Exact match gets highest priority
        
        # Calculate distance in inheritance hierarchy
        mro = actual_type.__mro__
        try:
            distance = mro.index(rule_type)
            return 1000 - distance  # Closer in hierarchy = higher specificity
        except ValueError:
            return 0  # Not in hierarchy
    
    def handle_error(
        self,
        error: Exception,
        context: ErrorContext,
        operation: Optional[Callable] = None
    ) -> Any:
        """
        Handle an error according to its classification and recovery strategy.
        
        Args:
            error: The exception that occurred
            context: Context information about the error
            operation: The operation that failed (for retry attempts)
            
        Returns:
            Result of error handling (success result, fallback result, or raises)
        """
        rule = self.classify_error(error)
        
        # Log the error
        error_info = self._create_error_info(error, context, rule)
        self.error_history.append(error_info)
        self._log_error(error_info, rule)
        
        # Handle based on recovery strategy
        if rule.recovery_strategy == RecoveryStrategy.RETRY and operation:
            return self._handle_retry(error, context, rule, operation)
        elif rule.recovery_strategy == RecoveryStrategy.FALLBACK:
            return self._handle_fallback(error, context, rule)
        elif rule.recovery_strategy == RecoveryStrategy.DEGRADE:
            return self._handle_degradation(error, context, rule)
        elif rule.recovery_strategy == RecoveryStrategy.IGNORE:
            return self._handle_ignore(error, context, rule)
        elif rule.recovery_strategy == RecoveryStrategy.FAIL_FAST:
            return self._handle_fail_fast(error, context, rule)
        else:
            # Default: propagate the error
            if rule.should_propagate:
                raise error
            return None
    
    async def handle_error_async(
        self,
        error: Exception,
        context: ErrorContext,
        operation: Optional[Callable] = None
    ) -> Any:
        """Async version of handle_error."""
        rule = self.classify_error(error)
        
        # Log the error
        error_info = self._create_error_info(error, context, rule)
        self.error_history.append(error_info)
        self._log_error(error_info, rule)
        
        # Handle based on recovery strategy
        if rule.recovery_strategy == RecoveryStrategy.RETRY and operation:
            return await self._handle_retry_async(error, context, rule, operation)
        elif rule.recovery_strategy == RecoveryStrategy.FALLBACK:
            return await self._handle_fallback_async(error, context, rule)
        elif rule.recovery_strategy == RecoveryStrategy.DEGRADE:
            return await self._handle_degradation_async(error, context, rule)
        elif rule.recovery_strategy == RecoveryStrategy.IGNORE:
            return self._handle_ignore(error, context, rule)
        elif rule.recovery_strategy == RecoveryStrategy.FAIL_FAST:
            return self._handle_fail_fast(error, context, rule)
        else:
            # Default: propagate the error
            if rule.should_propagate:
                raise error
            return None
    
    def _handle_retry(
        self,
        error: Exception,
        context: ErrorContext,
        rule: ErrorRule,
        operation: Callable
    ) -> Any:
        """Handle error with retry mechanism."""
        if not rule.retry_config:
            raise error
        
        retry_config = rule.retry_config
        
        if context.attempt_count >= retry_config.max_attempts:
            self.logger.error(
                f"Max retry attempts ({retry_config.max_attempts}) exceeded for {context.operation}"
            )
            raise error
        
        # Calculate delay
        delay = self._calculate_delay(context.attempt_count, retry_config)
        
        self.logger.info(
            f"Retrying operation {context.operation} in {delay:.2f}s "
            f"(attempt {context.attempt_count + 1}/{retry_config.max_attempts})"
        )
        
        time.sleep(delay)
        context.attempt_count += 1
        
        try:
            return operation()
        except Exception as retry_error:
            return self.handle_error(retry_error, context, operation)
    
    async def _handle_retry_async(
        self,
        error: Exception,
        context: ErrorContext,
        rule: ErrorRule,
        operation: Callable
    ) -> Any:
        """Async version of retry handling."""
        if not rule.retry_config:
            raise error
        
        retry_config = rule.retry_config
        
        if context.attempt_count >= retry_config.max_attempts:
            self.logger.error(
                f"Max retry attempts ({retry_config.max_attempts}) exceeded for {context.operation}"
            )
            raise error
        
        # Calculate delay
        delay = self._calculate_delay(context.attempt_count, retry_config)
        
        self.logger.info(
            f"Retrying operation {context.operation} in {delay:.2f}s "
            f"(attempt {context.attempt_count + 1}/{retry_config.max_attempts})"
        )
        
        await asyncio.sleep(delay)
        context.attempt_count += 1
        
        try:
            if asyncio.iscoroutinefunction(operation):
                return await operation()
            else:
                return operation()
        except Exception as retry_error:
            return await self.handle_error_async(retry_error, context, operation)
    
    def _handle_fallback(self, error: Exception, context: ErrorContext, rule: ErrorRule) -> Any:
        """Handle error with fallback mechanism."""
        if rule.fallback_handler:
            try:
                self.logger.info(f"Using fallback handler for {context.operation}")
                return rule.fallback_handler(error, context)
            except Exception as fallback_error:
                self.logger.error(f"Fallback handler failed: {fallback_error}")
                raise error
        else:
            self.logger.warning(f"No fallback handler available for {context.operation}")
            raise error
    
    async def _handle_fallback_async(self, error: Exception, context: ErrorContext, rule: ErrorRule) -> Any:
        """Async version of fallback handling."""
        if rule.fallback_handler:
            try:
                self.logger.info(f"Using fallback handler for {context.operation}")
                if asyncio.iscoroutinefunction(rule.fallback_handler):
                    return await rule.fallback_handler(error, context)
                else:
                    return rule.fallback_handler(error, context)
            except Exception as fallback_error:
                self.logger.error(f"Fallback handler failed: {fallback_error}")
                raise error
        else:
            self.logger.warning(f"No fallback handler available for {context.operation}")
            raise error
    
    def _handle_degradation(self, error: Exception, context: ErrorContext, rule: ErrorRule) -> Any:
        """Handle error with graceful degradation."""
        self.logger.warning(f"Degrading service for {context.operation} due to: {error}")
        
        # Return a degraded response
        return {
            "status": "degraded",
            "error": str(error),
            "context": context.metadata,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _handle_degradation_async(self, error: Exception, context: ErrorContext, rule: ErrorRule) -> Any:
        """Async version of degradation handling."""
        return self._handle_degradation(error, context, rule)
    
    def _handle_ignore(self, error: Exception, context: ErrorContext, rule: ErrorRule) -> Any:
        """Handle error by ignoring it."""
        self.logger.debug(f"Ignoring error for {context.operation}: {error}")
        return None
    
    def _handle_fail_fast(self, error: Exception, context: ErrorContext, rule: ErrorRule) -> Any:
        """Handle error by failing fast."""
        self.logger.error(f"Failing fast for {context.operation}: {error}")
        raise error
    
    def _calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """Calculate delay for retry attempts."""
        if config.backoff_strategy == "exponential":
            delay = config.base_delay * (config.exponential_base ** attempt)
        elif config.backoff_strategy == "linear":
            delay = config.base_delay * (attempt + 1)
        else:  # fixed
            delay = config.base_delay
        
        # Apply maximum delay limit
        delay = min(delay, config.max_delay)
        
        # Add jitter if enabled
        if config.jitter:
            import random
            delay *= (0.5 + random.random() * 0.5)
        
        return delay
    
    def _create_error_info(self, error: Exception, context: ErrorContext, rule: ErrorRule) -> ErrorInfo:
        """Create ErrorInfo object from error and context."""
        return ErrorInfo(
            error_code=f"{rule.category.value}_{type(error).__name__}",
            message=str(error),
            timestamp=datetime.now(),
            context={
                "execution_id": context.execution_id,
                "team_id": context.team_id,
                "agent_id": context.agent_id,
                "supervisor_id": context.supervisor_id,
                "operation": context.operation,
                "attempt_count": context.attempt_count,
                "category": rule.category.value,
                "severity": rule.severity.value,
                "recovery_strategy": rule.recovery_strategy.value,
                "error_type": type(error).__name__,
                "metadata": context.metadata
            }
        )
    
    def _log_error(self, error_info: ErrorInfo, rule: ErrorRule) -> None:
        """Log error information."""
        log_level = {
            ErrorSeverity.LOW: logging.DEBUG,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL
        }.get(rule.severity, logging.ERROR)
        
        self.logger.log(
            log_level,
            f"Error [{error_info.error_code}]: {error_info.message} "
            f"(Category: {rule.category.value}, Severity: {rule.severity.value})"
        )
    
    def get_circuit_breaker(self, service_name: str) -> 'CircuitBreaker':
        """Get or create a circuit breaker for a service."""
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreaker(service_name)
        return self.circuit_breakers[service_name]
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics."""
        if not self.error_history:
            return {"total_errors": 0}
        
        stats = {
            "total_errors": len(self.error_history),
            "errors_by_category": {},
            "errors_by_severity": {},
            "recent_errors": len([
                e for e in self.error_history 
                if e.timestamp > datetime.now() - timedelta(hours=1)
            ])
        }
        
        for error in self.error_history:
            if error.context:
                category = error.context.get("category", "unknown")
                severity = error.context.get("severity", "unknown")
                
                stats["errors_by_category"][category] = stats["errors_by_category"].get(category, 0) + 1
                stats["errors_by_severity"][severity] = stats["errors_by_severity"].get(severity, 0) + 1
        
        return stats
    
    def clear_error_history(self) -> None:
        """Clear error history."""
        self.error_history.clear()


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for preventing cascading failures.
    """
    
    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        """Initialize circuit breaker."""
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half_open
        
        self.logger = logging.getLogger(f"{__name__}.CircuitBreaker.{service_name}")
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Call function through circuit breaker."""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half_open"
                self.logger.info(f"Circuit breaker for {self.service_name} is half-open")
            else:
                raise CircuitBreakerOpenError(f"Circuit breaker for {self.service_name} is open")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """Async version of call."""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half_open"
                self.logger.info(f"Circuit breaker for {self.service_name} is half-open")
            else:
                raise CircuitBreakerOpenError(f"Circuit breaker for {self.service_name} is open")
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt to reset."""
        return (
            self.last_failure_time is not None and
            time.time() - self.last_failure_time >= self.recovery_timeout
        )
    
    def _on_success(self) -> None:
        """Handle successful call."""
        self.failure_count = 0
        if self.state == "half_open":
            self.state = "closed"
            self.logger.info(f"Circuit breaker for {self.service_name} is closed")
    
    def _on_failure(self) -> None:
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            self.logger.warning(f"Circuit breaker for {self.service_name} is open")


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


# Convenience functions for common error handling patterns
def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """Decorator for adding retry logic to functions."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            error_handler = ErrorHandler()
            context = ErrorContext(
                execution_id="decorator_retry",
                operation=func.__name__,
                max_attempts=max_attempts
            )
            
            # Add custom retry rule
            error_handler.add_error_rule(ErrorRule(
                error_types=list(exceptions),
                category=ErrorCategory.SYSTEM_ERROR,
                severity=ErrorSeverity.MEDIUM,
                recovery_strategy=RecoveryStrategy.RETRY,
                retry_config=RetryConfig(
                    max_attempts=max_attempts,
                    base_delay=base_delay,
                    exponential_base=exponential_base
                )
            ))
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                return error_handler.handle_error(e, context, lambda: func(*args, **kwargs))
        
        return wrapper
    return decorator


def with_circuit_breaker(
    service_name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0
):
    """Decorator for adding circuit breaker to functions."""
    def decorator(func):
        circuit_breaker = CircuitBreaker(service_name, failure_threshold, recovery_timeout)
        
        def wrapper(*args, **kwargs):
            return circuit_breaker.call(func, *args, **kwargs)
        
        return wrapper
    return decorator


# Global error handler instance
default_error_handler = ErrorHandler()