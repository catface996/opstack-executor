"""
Tests for the error handling framework.

This module tests all aspects of error handling including:
- Error classification and categorization
- Retry mechanisms with exponential backoff
- Graceful degradation strategies
- Circuit breaker pattern
- Error propagation and context preservation
"""

import asyncio
import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.hierarchical_agents.error_handler import (
    ErrorHandler,
    ErrorCategory,
    ErrorSeverity,
    RecoveryStrategy,
    ErrorContext,
    RetryConfig,
    ErrorRule,
    CircuitBreaker,
    CircuitBreakerOpenError,
    with_retry,
    with_circuit_breaker,
    default_error_handler,
)

from src.hierarchical_agents.data_models import ErrorInfo


class TestErrorHandler:
    """Test cases for ErrorHandler class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.error_handler = ErrorHandler()
        self.context = ErrorContext(
            execution_id="test_exec_123",
            team_id="test_team",
            agent_id="test_agent",
            operation="test_operation"
        )
    
    def test_error_classification_network_error(self):
        """Test that network errors are correctly classified."""
        error = ConnectionError("Network connection failed")
        rule = self.error_handler.classify_error(error)
        
        assert rule.category == ErrorCategory.NETWORK_ERROR
        assert rule.severity == ErrorSeverity.MEDIUM
        assert rule.recovery_strategy == RecoveryStrategy.RETRY
        assert rule.retry_config is not None
        assert rule.retry_config.max_attempts == 3
    
    def test_error_classification_authentication_error(self):
        """Test that authentication errors are correctly classified."""
        error = PermissionError("Access denied")
        rule = self.error_handler.classify_error(error)
        
        assert rule.category == ErrorCategory.AUTHENTICATION_ERROR
        assert rule.severity == ErrorSeverity.HIGH
        assert rule.recovery_strategy == RecoveryStrategy.FAIL_FAST
    
    def test_error_classification_configuration_error(self):
        """Test that configuration errors are correctly classified."""
        error = ValueError("Invalid configuration value")
        rule = self.error_handler.classify_error(error)
        
        assert rule.category == ErrorCategory.CONFIGURATION_ERROR
        assert rule.severity == ErrorSeverity.HIGH
        assert rule.recovery_strategy == RecoveryStrategy.FAIL_FAST
    
    def test_error_classification_resource_error(self):
        """Test that resource errors are correctly classified."""
        error = MemoryError("Out of memory")
        rule = self.error_handler.classify_error(error)
        
        assert rule.category == ErrorCategory.RESOURCE_ERROR
        assert rule.severity == ErrorSeverity.HIGH
        assert rule.recovery_strategy == RecoveryStrategy.DEGRADE
    
    def test_error_classification_generic_error(self):
        """Test that generic errors get default classification."""
        error = RuntimeError("Generic runtime error")
        rule = self.error_handler.classify_error(error)
        
        assert rule.category == ErrorCategory.SYSTEM_ERROR
        assert rule.severity == ErrorSeverity.MEDIUM
        assert rule.recovery_strategy == RecoveryStrategy.RETRY
    
    def test_retry_mechanism_success_after_failure(self):
        """Test that retry mechanism works when operation succeeds after initial failure."""
        call_count = 0
        
        def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary network error")
            return "success"
        
        result = self.error_handler.handle_error(
            ConnectionError("Initial error"),
            self.context,
            failing_operation
        )
        
        assert result == "success"
        assert call_count == 3
        assert self.context.attempt_count == 3  # 3 total attempts (1 initial + 2 retries)
    
    def test_retry_mechanism_max_attempts_exceeded(self):
        """Test that retry mechanism fails after max attempts."""
        def always_failing_operation():
            raise ConnectionError("Persistent network error")
        
        with pytest.raises(ConnectionError):
            self.error_handler.handle_error(
                ConnectionError("Initial error"),
                self.context,
                always_failing_operation
            )
        
        # Should have attempted max_attempts times
        assert self.context.attempt_count >= 3
    
    def test_retry_mechanism_no_operation_provided(self):
        """Test that retry fails when no operation is provided."""
        error = ConnectionError("Network error")
        
        with pytest.raises(ConnectionError):
            self.error_handler.handle_error(error, self.context, None)
    
    def test_graceful_degradation(self):
        """Test that graceful degradation returns degraded response."""
        error = MemoryError("Out of memory")
        result = self.error_handler.handle_error(error, self.context)
        
        assert isinstance(result, dict)
        assert result["status"] == "degraded"
        assert "error" in result
        assert "timestamp" in result
    
    def test_fail_fast_strategy(self):
        """Test that fail fast strategy immediately raises error."""
        error = PermissionError("Access denied")
        
        with pytest.raises(PermissionError):
            self.error_handler.handle_error(error, self.context)
    
    def test_fallback_handler(self):
        """Test fallback handler functionality."""
        def fallback_handler(error, context):
            return f"fallback_result_for_{context.operation}"
        
        # Add custom rule with fallback
        self.error_handler.add_error_rule(ErrorRule(
            error_types=[ValueError],
            category=ErrorCategory.SYSTEM_ERROR,
            severity=ErrorSeverity.MEDIUM,
            recovery_strategy=RecoveryStrategy.FALLBACK,
            fallback_handler=fallback_handler
        ))
        
        error = ValueError("Test error")
        result = self.error_handler.handle_error(error, self.context)
        
        assert result == "fallback_result_for_test_operation"
    
    def test_error_history_tracking(self):
        """Test that error history is properly tracked."""
        initial_count = len(self.error_handler.error_history)
        
        error = RuntimeError("Test error")
        try:
            self.error_handler.handle_error(error, self.context)
        except:
            pass
        
        assert len(self.error_handler.error_history) == initial_count + 1
        
        error_info = self.error_handler.error_history[-1]
        assert isinstance(error_info, ErrorInfo)
        assert "system_error_RuntimeError" in error_info.error_code
        assert error_info.message == "Test error"
        assert error_info.context["execution_id"] == "test_exec_123"
    
    def test_error_statistics(self):
        """Test error statistics generation."""
        # Generate some errors
        errors = [
            ConnectionError("Network error 1"),
            ConnectionError("Network error 2"),
            PermissionError("Auth error"),
            MemoryError("Memory error")
        ]
        
        for error in errors:
            try:
                self.error_handler.handle_error(error, self.context)
            except:
                pass
        
        stats = self.error_handler.get_error_statistics()
        
        assert stats["total_errors"] >= 4
        assert "errors_by_category" in stats
        assert "errors_by_severity" in stats
        assert "recent_errors" in stats
    
    def test_custom_error_rule(self):
        """Test adding and using custom error rules."""
        class CustomError(Exception):
            pass
        
        def custom_handler(error, context):
            return f"custom_handled_{error}"
        
        custom_rule = ErrorRule(
            error_types=[CustomError],
            category=ErrorCategory.AGENT_ERROR,
            severity=ErrorSeverity.LOW,
            recovery_strategy=RecoveryStrategy.FALLBACK,
            fallback_handler=custom_handler
        )
        
        self.error_handler.add_error_rule(custom_rule)
        
        error = CustomError("Custom test error")
        result = self.error_handler.handle_error(error, self.context)
        
        assert result == "custom_handled_Custom test error"


class TestAsyncErrorHandler:
    """Test cases for async error handling."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.error_handler = ErrorHandler()
        self.context = ErrorContext(
            execution_id="test_exec_async",
            operation="async_test_operation"
        )
    
    @pytest.mark.asyncio
    async def test_async_retry_mechanism(self):
        """Test async retry mechanism."""
        call_count = 0
        
        async def failing_async_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Async network error")
            return "async_success"
        
        result = await self.error_handler.handle_error_async(
            ConnectionError("Initial async error"),
            self.context,
            failing_async_operation
        )
        
        assert result == "async_success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_async_fallback_handler(self):
        """Test async fallback handler."""
        async def async_fallback_handler(error, context):
            return f"async_fallback_{context.operation}"
        
        self.error_handler.add_error_rule(ErrorRule(
            error_types=[ValueError],
            category=ErrorCategory.SYSTEM_ERROR,
            severity=ErrorSeverity.MEDIUM,
            recovery_strategy=RecoveryStrategy.FALLBACK,
            fallback_handler=async_fallback_handler
        ))
        
        error = ValueError("Async test error")
        result = await self.error_handler.handle_error_async(error, self.context)
        
        assert result == "async_fallback_async_test_operation"


class TestCircuitBreaker:
    """Test cases for CircuitBreaker class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.circuit_breaker = CircuitBreaker(
            service_name="test_service",
            failure_threshold=3,
            recovery_timeout=1.0
        )
    
    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state."""
        def successful_operation():
            return "success"
        
        result = self.circuit_breaker.call(successful_operation)
        assert result == "success"
        assert self.circuit_breaker.state == "closed"
        assert self.circuit_breaker.failure_count == 0
    
    def test_circuit_breaker_opens_after_failures(self):
        """Test that circuit breaker opens after threshold failures."""
        def failing_operation():
            raise ConnectionError("Service unavailable")
        
        # Trigger failures up to threshold
        for i in range(3):
            with pytest.raises(ConnectionError):
                self.circuit_breaker.call(failing_operation)
        
        assert self.circuit_breaker.state == "open"
        assert self.circuit_breaker.failure_count == 3
    
    def test_circuit_breaker_blocks_calls_when_open(self):
        """Test that circuit breaker blocks calls when open."""
        def failing_operation():
            raise ConnectionError("Service unavailable")
        
        # Open the circuit breaker
        for i in range(3):
            with pytest.raises(ConnectionError):
                self.circuit_breaker.call(failing_operation)
        
        # Now calls should be blocked
        with pytest.raises(CircuitBreakerOpenError):
            self.circuit_breaker.call(failing_operation)
    
    def test_circuit_breaker_half_open_recovery(self):
        """Test circuit breaker recovery through half-open state."""
        def failing_operation():
            raise ConnectionError("Service unavailable")
        
        def successful_operation():
            return "recovered"
        
        # Open the circuit breaker
        for i in range(3):
            with pytest.raises(ConnectionError):
                self.circuit_breaker.call(failing_operation)
        
        assert self.circuit_breaker.state == "open"
        
        # Wait for recovery timeout
        time.sleep(1.1)
        
        # Next call should transition to half-open and succeed
        result = self.circuit_breaker.call(successful_operation)
        assert result == "recovered"
        assert self.circuit_breaker.state == "closed"
        assert self.circuit_breaker.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_async_circuit_breaker(self):
        """Test async circuit breaker functionality."""
        async def async_successful_operation():
            return "async_success"
        
        result = await self.circuit_breaker.call_async(async_successful_operation)
        assert result == "async_success"


class TestRetryDecorator:
    """Test cases for retry decorator."""
    
    def test_retry_decorator_success(self):
        """Test retry decorator with successful operation."""
        call_count = 0
        
        @with_retry(max_attempts=3, base_delay=0.1)
        def operation_with_retry():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Temporary error")
            return "success"
        
        result = operation_with_retry()
        assert result == "success"
        assert call_count == 2
    
    def test_retry_decorator_failure(self):
        """Test retry decorator with persistent failure."""
        call_count = 0
        
        @with_retry(max_attempts=2, base_delay=0.1)
        def always_failing_operation():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Persistent error")
        
        with pytest.raises(ConnectionError):
            always_failing_operation()
        
        assert call_count >= 2


class TestCircuitBreakerDecorator:
    """Test cases for circuit breaker decorator."""
    
    def test_circuit_breaker_decorator(self):
        """Test circuit breaker decorator functionality."""
        call_count = 0
        
        @with_circuit_breaker("test_service", failure_threshold=2, recovery_timeout=0.5)
        def decorated_operation():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("Service error")
            return "success"
        
        # First two calls should fail and open circuit
        with pytest.raises(ConnectionError):
            decorated_operation()
        
        with pytest.raises(ConnectionError):
            decorated_operation()
        
        # Third call should be blocked by circuit breaker
        with pytest.raises(CircuitBreakerOpenError):
            decorated_operation()


class TestRetryConfig:
    """Test cases for RetryConfig and delay calculations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.error_handler = ErrorHandler()
    
    def test_exponential_backoff_delay(self):
        """Test exponential backoff delay calculation."""
        config = RetryConfig(
            base_delay=1.0,
            exponential_base=2.0,
            jitter=False
        )
        
        # Test delay calculation for different attempts
        delay_0 = self.error_handler._calculate_delay(0, config)
        delay_1 = self.error_handler._calculate_delay(1, config)
        delay_2 = self.error_handler._calculate_delay(2, config)
        
        assert delay_0 == 1.0  # 1.0 * 2^0
        assert delay_1 == 2.0  # 1.0 * 2^1
        assert delay_2 == 4.0  # 1.0 * 2^2
    
    def test_linear_backoff_delay(self):
        """Test linear backoff delay calculation."""
        config = RetryConfig(
            base_delay=1.0,
            backoff_strategy="linear",
            jitter=False
        )
        
        delay_0 = self.error_handler._calculate_delay(0, config)
        delay_1 = self.error_handler._calculate_delay(1, config)
        delay_2 = self.error_handler._calculate_delay(2, config)
        
        assert delay_0 == 1.0  # 1.0 * (0 + 1)
        assert delay_1 == 2.0  # 1.0 * (1 + 1)
        assert delay_2 == 3.0  # 1.0 * (2 + 1)
    
    def test_fixed_backoff_delay(self):
        """Test fixed backoff delay calculation."""
        config = RetryConfig(
            base_delay=2.0,
            backoff_strategy="fixed",
            jitter=False
        )
        
        delay_0 = self.error_handler._calculate_delay(0, config)
        delay_1 = self.error_handler._calculate_delay(1, config)
        delay_2 = self.error_handler._calculate_delay(2, config)
        
        assert delay_0 == 2.0
        assert delay_1 == 2.0
        assert delay_2 == 2.0
    
    def test_max_delay_limit(self):
        """Test that delay is capped at max_delay."""
        config = RetryConfig(
            base_delay=1.0,
            max_delay=5.0,
            exponential_base=2.0,
            jitter=False
        )
        
        delay_10 = self.error_handler._calculate_delay(10, config)
        assert delay_10 == 5.0  # Should be capped at max_delay
    
    def test_jitter_adds_randomness(self):
        """Test that jitter adds randomness to delay."""
        config = RetryConfig(
            base_delay=2.0,
            jitter=True
        )
        
        delays = [self.error_handler._calculate_delay(1, config) for _ in range(10)]
        
        # All delays should be between 1.0 and 2.0 (base_delay * 2^1 * [0.5, 1.0])
        assert all(1.0 <= delay <= 4.0 for delay in delays)
        
        # There should be some variation (not all delays identical)
        assert len(set(delays)) > 1


class TestErrorPropagation:
    """Test cases for error propagation and context preservation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.error_handler = ErrorHandler()
    
    def test_error_context_preservation(self):
        """Test that error context is preserved through handling."""
        context = ErrorContext(
            execution_id="test_exec_456",
            team_id="team_alpha",
            agent_id="agent_beta",
            supervisor_id="supervisor_gamma",
            operation="complex_operation",
            metadata={"custom_field": "custom_value"}
        )
        
        error = RuntimeError("Context preservation test")
        
        try:
            self.error_handler.handle_error(error, context)
        except:
            pass
        
        # Check that error was recorded with full context
        error_info = self.error_handler.error_history[-1]
        assert error_info.context["execution_id"] == "test_exec_456"
        assert error_info.context["team_id"] == "team_alpha"
        assert error_info.context["agent_id"] == "agent_beta"
        assert error_info.context["supervisor_id"] == "supervisor_gamma"
        assert error_info.context["operation"] == "complex_operation"
        assert error_info.context["metadata"]["custom_field"] == "custom_value"
    
    def test_error_propagation_with_should_propagate_true(self):
        """Test that errors are propagated when should_propagate is True."""
        rule = ErrorRule(
            error_types=[ValueError],
            category=ErrorCategory.SYSTEM_ERROR,
            severity=ErrorSeverity.MEDIUM,
            recovery_strategy=RecoveryStrategy.FAIL_FAST,
            should_propagate=True
        )
        
        self.error_handler.add_error_rule(rule)
        
        error = ValueError("Should propagate")
        context = ErrorContext(execution_id="test", operation="test")
        
        with pytest.raises(ValueError):
            self.error_handler.handle_error(error, context)
    
    def test_error_suppression_with_should_propagate_false(self):
        """Test that errors are suppressed when should_propagate is False."""
        rule = ErrorRule(
            error_types=[ValueError],
            category=ErrorCategory.SYSTEM_ERROR,
            severity=ErrorSeverity.LOW,
            recovery_strategy=RecoveryStrategy.IGNORE,
            should_propagate=False
        )
        
        self.error_handler.add_error_rule(rule)
        
        error = ValueError("Should not propagate")
        context = ErrorContext(execution_id="test", operation="test")
        
        # Should not raise exception
        result = self.error_handler.handle_error(error, context)
        assert result is None


class TestDefaultErrorHandler:
    """Test cases for the default error handler instance."""
    
    def test_default_error_handler_exists(self):
        """Test that default error handler is available."""
        assert default_error_handler is not None
        assert isinstance(default_error_handler, ErrorHandler)
    
    def test_default_error_handler_has_rules(self):
        """Test that default error handler has default rules."""
        assert len(default_error_handler.error_rules) > 0
        
        # Test that it can classify common errors
        network_error = ConnectionError("Test")
        rule = default_error_handler.classify_error(network_error)
        assert rule.category == ErrorCategory.NETWORK_ERROR