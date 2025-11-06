"""
Hierarchical Multi-Agent System

A framework for building and executing hierarchical teams of AI agents
with supervisor-worker architecture and dependency management.
"""

from .data_models import (
    # Core configuration models
    HierarchicalTeam,
    SubTeam,
    AgentConfig,
    SupervisorConfig,
    GlobalConfig,
    LLMConfig,
    
    # Execution models
    ExecutionEvent,
    ExecutionSummary,
    ExecutionConfig,
    ExecutionContext,
    TeamState,
    ExecutionStatus,
    
    # Result models
    TeamResult,
    StandardizedOutput,
    ExecutionMetrics,
    ErrorInfo,
    
    # API models
    APIResponse,
    TeamCreationResponse,
    ExecutionStartResponse,
    ExecutionResultsResponse,
    FormattedResultsResponse,
    
    # Template models
    OutputTemplate,
    ExtractionRules,
    FormatRequest,
    
    # Key management
    KeyConfig,
    
    # Type aliases
    AgentResult,
    DependencyGraph,
    AgentTeam,
    ExecutionSession,
    ErrorResponse,
    UsageStats,
)

from .config_manager import (
    ConfigManager,
    ConfigValidationError,
    load_config_from_file,
    validate_config_from_dict,
    save_config_to_file,
)

from .key_manager import (
    SecureKeyManager,
    KeyManagerError,
    KeyNotFoundError,
    InvalidKeyError,
    create_key_manager,
    generate_master_key,
)

from .env_key_manager import (
    EnvironmentKeyManager,
    EnvironmentKeyError,
    MissingAPIKeyError,
    InvalidKeyFormatError,
    get_api_key,
    check_all_providers,
    validate_environment_setup,
    default_key_manager,
)

from .llm_providers import (
    LLMProviderFactory,
    LLMProviderConfig,
    OpenAIProvider,
    OpenRouterProvider,
    AWSBedrockProvider,
    LLMProviderError,
    UnsupportedProviderError,
    ClientCreationError,
    create_llm_client,
    get_supported_providers,
    get_supported_models,
    validate_llm_config,
)

from .tools import (
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

from .builtin_tools import (
    TavilySearchTool,
    WebScraperTool,
    DocumentWriterTool,
    DataProcessorTool,
    TextEditorTool,
    register_builtin_tools,
)

from .error_handler import (
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

from .agents import (
    BaseAgent,
    WorkerAgent,
    SupervisorAgent,
    AgentError,
    AgentInitializationError,
    AgentExecutionError,
    create_worker_agent,
    create_supervisor_agent,
    validate_agent_config,
)

from .state_manager import (
    StateManager,
    StateManagerConfig,
    ExecutionState,
    create_state_manager,
    with_state_manager,
)

from .event_manager import (
    EventManager,
    EventManagerConfig,
    EventSubscriber,
    create_event_manager,
    event_manager_context,
)

from .execution_engine import (
    ExecutionEngine,
    ExecutionSession,
    create_execution_engine,
    execution_engine_context,
)

from .performance_monitor import (
    PerformanceMonitor,
    PerformanceOptimizer,
    ResourceMonitor,
    PrometheusExporter,
    ResourceUsage,
    PerformanceMetrics,
    ConcurrencyMetrics,
    initialize_performance_monitor,
    get_performance_monitor,
    monitor_execution,
    record_api_metrics,
    record_agent_metrics,
)

__version__ = "0.1.0"
__author__ = "Hierarchical Agents Team"
__email__ = "team@hierarchical-agents.com"

__all__ = [
    # Core configuration models
    "HierarchicalTeam",
    "SubTeam", 
    "AgentConfig",
    "SupervisorConfig",
    "GlobalConfig",
    "LLMConfig",
    
    # Execution models
    "ExecutionEvent",
    "ExecutionSummary", 
    "ExecutionConfig",
    "ExecutionContext",
    "TeamState",
    "ExecutionStatus",
    
    # Result models
    "TeamResult",
    "StandardizedOutput",
    "ExecutionMetrics",
    "ErrorInfo",
    
    # API models
    "APIResponse",
    "TeamCreationResponse",
    "ExecutionStartResponse", 
    "ExecutionResultsResponse",
    "FormattedResultsResponse",
    
    # Template models
    "OutputTemplate",
    "ExtractionRules",
    "FormatRequest",
    
    # Key management
    "KeyConfig",
    
    # Configuration management
    "ConfigManager",
    "ConfigValidationError",
    "load_config_from_file",
    "validate_config_from_dict", 
    "save_config_to_file",
    
    # Key management
    "SecureKeyManager",
    "KeyManagerError",
    "KeyNotFoundError",
    "InvalidKeyError",
    "create_key_manager",
    "generate_master_key",
    
    # Environment key management
    "EnvironmentKeyManager",
    "EnvironmentKeyError",
    "MissingAPIKeyError",
    "InvalidKeyFormatError",
    "get_api_key",
    "check_all_providers",
    "validate_environment_setup",
    "default_key_manager",
    
    # LLM providers
    "LLMProviderFactory",
    "LLMProviderConfig",
    "OpenAIProvider",
    "OpenRouterProvider",
    "AWSBedrockProvider",
    "LLMProviderError",
    "UnsupportedProviderError",
    "ClientCreationError",
    "create_llm_client",
    "get_supported_providers",
    "get_supported_models",
    "validate_llm_config",
    
    # Tools framework
    "BaseTool",
    "ToolInput",
    "ToolOutput",
    "ToolMetadata",
    "ToolRegistry",
    "ToolExecutor",
    "ToolError",
    "ToolExecutionError",
    "ToolNotFoundError",
    "ToolRegistrationError",
    "default_registry",
    "default_executor",
    "register_tool",
    "get_tool",
    "execute_tool",
    "execute_tool_async",
    "list_tools",
    "search_tools",
    
    # Built-in tools
    "TavilySearchTool",
    "WebScraperTool",
    "DocumentWriterTool",
    "DataProcessorTool",
    "TextEditorTool",
    "register_builtin_tools",
    
    # Error handling
    "ErrorHandler",
    "ErrorCategory",
    "ErrorSeverity",
    "RecoveryStrategy",
    "ErrorContext",
    "RetryConfig",
    "ErrorRule",
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "with_retry",
    "with_circuit_breaker",
    "default_error_handler",
    
    # Agents
    "BaseAgent",
    "WorkerAgent",
    "SupervisorAgent",
    "AgentError",
    "AgentInitializationError",
    "AgentExecutionError",
    "create_worker_agent",
    "create_supervisor_agent",
    "validate_agent_config",
    
    # State management
    "StateManager",
    "StateManagerConfig",
    "ExecutionState",
    "create_state_manager",
    "with_state_manager",
    
    # Event management
    "EventManager",
    "EventManagerConfig",
    "EventSubscriber",
    "create_event_manager",
    "event_manager_context",
    
    # Execution engine
    "ExecutionEngine",
    "ExecutionSession",
    "create_execution_engine",
    "execution_engine_context",
    
    # Performance monitoring
    "PerformanceMonitor",
    "PerformanceOptimizer",
    "ResourceMonitor",
    "PrometheusExporter",
    "ResourceUsage",
    "PerformanceMetrics",
    "ConcurrencyMetrics",
    "initialize_performance_monitor",
    "get_performance_monitor",
    "monitor_execution",
    "record_api_metrics",
    "record_agent_metrics",
    
    # Type aliases
    "AgentResult",
    "DependencyGraph", 
    "AgentTeam",
    "ErrorResponse",
    "UsageStats",
]