"""
Core data models for the hierarchical multi-agent system.

This module defines all the data structures used throughout the system,
including configurations, execution states, and result formats.
All models use Pydantic for validation and serialization.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

# Note: MessagesState will be imported when langgraph is properly installed
# For now, we'll define a placeholder
try:
    from langgraph.graph import MessagesState
except ImportError:
    # Placeholder for when langgraph is not available
    class MessagesState(BaseModel):  # type: ignore
        """Placeholder for LangGraph MessagesState."""
        pass


class ExecutionStatus(str, Enum):
    """Execution status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class LLMConfig(BaseModel):
    """LLM configuration for different providers."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    provider: str = Field(..., description="LLM provider: openai, openrouter, aws_bedrock")
    model: str = Field(..., description="Model name")
    base_url: Optional[str] = Field(None, description="Custom API endpoint")
    region: Optional[str] = Field(None, description="AWS region (Bedrock only)")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Temperature for generation")
    max_tokens: Optional[int] = Field(None, gt=0, description="Maximum tokens to generate")
    timeout: int = Field(30, gt=0, description="Request timeout in seconds")
    
    @field_validator('provider')
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed_providers = {"openai", "openrouter", "aws_bedrock"}
        if v not in allowed_providers:
            raise ValueError(f"Provider must be one of {allowed_providers}")
        return v
    
    @model_validator(mode='after')
    def validate_provider_requirements(self) -> 'LLMConfig':
        if self.provider == 'aws_bedrock' and not self.region:
            raise ValueError("Region is required for AWS Bedrock provider")
        return self


class SupervisorConfig(BaseModel):
    """Configuration for supervisor agents."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    llm_config: LLMConfig = Field(..., description="LLM configuration")
    system_prompt: str = Field(..., min_length=1, description="System prompt defining role and behavior")
    user_prompt: str = Field(..., min_length=1, description="User prompt with execution instructions")
    max_iterations: int = Field(10, gt=0, description="Maximum iterations allowed")


class AgentConfig(BaseModel):
    """Configuration for worker agents."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    agent_id: str = Field(..., min_length=1, description="Unique agent identifier")
    agent_name: str = Field(..., min_length=1, description="Agent name for display and routing")
    llm_config: LLMConfig = Field(..., description="LLM configuration")
    system_prompt: str = Field(..., min_length=1, description="System prompt defining role and behavior")
    user_prompt: str = Field(..., min_length=1, description="User prompt with task instructions")
    tools: List[str] = Field(default_factory=list, description="Available tools list")
    max_iterations: int = Field(10, gt=0, description="Maximum iterations allowed")


class SubTeam(BaseModel):
    """Sub-team definition within hierarchical structure."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    id: str = Field(..., min_length=1, description="Unique team identifier")
    name: str = Field(..., min_length=1, description="Team name")
    description: str = Field(..., min_length=1, description="Team description")
    supervisor_config: SupervisorConfig = Field(..., description="Team supervisor configuration")
    agent_configs: List[AgentConfig] = Field(..., description="Agent configurations")
    
    @field_validator('agent_configs')
    @classmethod
    def validate_unique_agent_ids(cls, v: List[AgentConfig]) -> List[AgentConfig]:
        agent_ids = [agent.agent_id for agent in v]
        if len(agent_ids) != len(set(agent_ids)):
            raise ValueError("Agent IDs must be unique within a team")
        return v


class GlobalConfig(BaseModel):
    """Global configuration for the hierarchical team."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    max_execution_time: int = Field(3600, gt=0, description="Maximum execution time in seconds")
    enable_streaming: bool = Field(True, description="Enable streaming events")
    output_format: str = Field("detailed", description="Output format: detailed|summary|minimal")
    
    @field_validator('output_format')
    @classmethod
    def validate_output_format(cls, v: str) -> str:
        allowed_formats = {"detailed", "summary", "minimal"}
        if v not in allowed_formats:
            raise ValueError(f"Output format must be one of {allowed_formats}")
        return v


class HierarchicalTeam(BaseModel):
    """Complete hierarchical team structure."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    team_name: str = Field(..., min_length=1, description="Team name")
    description: str = Field(..., min_length=1, description="Team description")
    top_supervisor_config: SupervisorConfig = Field(..., description="Top-level supervisor configuration")
    sub_teams: List[SubTeam] = Field(..., description="Sub-teams list")
    dependencies: Dict[str, List[str]] = Field(default_factory=dict, description="Team dependencies")
    global_config: GlobalConfig = Field(default_factory=GlobalConfig, description="Global configuration")  # type: ignore
    
    # Runtime fields (not included in serialization by default)
    top_supervisor: Optional[Any] = Field(None, exclude=True, description="Runtime supervisor instance")
    teams: Optional[Dict[str, Any]] = Field(None, exclude=True, description="Runtime team instances")
    dependency_graph: Optional[Any] = Field(None, exclude=True, description="Runtime dependency graph")
    execution_order: Optional[List[str]] = Field(None, exclude=True, description="Runtime execution order")
    
    @field_validator('sub_teams')
    @classmethod
    def validate_unique_team_ids(cls, v: List[SubTeam]) -> List[SubTeam]:
        team_ids = [team.id for team in v]
        if len(team_ids) != len(set(team_ids)):
            raise ValueError("Team IDs must be unique")
        return v
    
    @field_validator('dependencies')
    @classmethod
    def validate_dependencies(cls, v: Dict[str, List[str]], info: Any) -> Dict[str, List[str]]:
        if 'sub_teams' in info.data:
            team_ids = {team.id for team in info.data['sub_teams']}
            for team_id, deps in v.items():
                if team_id not in team_ids:
                    raise ValueError(f"Dependency key '{team_id}' not found in sub_teams")
                for dep in deps:
                    if dep not in team_ids:
                        raise ValueError(f"Dependency '{dep}' not found in sub_teams")
        return v


class ExecutionEvent(BaseModel):
    """Event generated during execution."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    timestamp: datetime = Field(default_factory=datetime.now, description="Event timestamp")
    event_type: str = Field(..., description="Event type: execution_started, supervisor_routing, etc.")
    source_type: str = Field(..., description="Event source: system, supervisor, agent")
    execution_id: str = Field(..., description="Execution ID")
    team_id: Optional[str] = Field(None, description="Team ID")
    supervisor_id: Optional[str] = Field(None, description="Supervisor ID")
    supervisor_name: Optional[str] = Field(None, description="Supervisor name")
    agent_id: Optional[str] = Field(None, description="Agent ID")
    agent_name: Optional[str] = Field(None, description="Agent name")
    content: Optional[str] = Field(None, description="Event content")
    action: Optional[str] = Field(None, description="Action performed")
    status: Optional[str] = Field(None, description="Status")
    progress: Optional[int] = Field(None, ge=0, le=100, description="Progress percentage")
    result: Optional[str] = Field(None, description="Execution result")
    selected_team: Optional[str] = Field(None, description="Selected team")
    selected_agent: Optional[str] = Field(None, description="Selected agent")
    
    @field_validator('source_type')
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        allowed_sources = {"system", "supervisor", "agent"}
        if v not in allowed_sources:
            raise ValueError(f"Source type must be one of {allowed_sources}")
        return v


class ExecutionSummary(BaseModel):
    """Summary of execution results."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    status: str = Field(..., description="Overall execution status")
    started_at: datetime = Field(..., description="Execution start time")
    completed_at: Optional[datetime] = Field(None, description="Execution completion time")
    total_duration: Optional[int] = Field(None, ge=0, description="Total duration in seconds")
    teams_executed: int = Field(0, ge=0, description="Number of teams executed")
    agents_involved: int = Field(0, ge=0, description="Number of agents involved")


class TeamResult(BaseModel):
    """Result from a team execution."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    status: str = Field(..., description="Team execution status")
    duration: Optional[int] = Field(None, ge=0, description="Execution duration in seconds")
    agents: Optional[Dict[str, Any]] = Field(None, description="Agent results")
    output: Optional[str] = Field(None, description="Team output")


class ErrorInfo(BaseModel):
    """Error information."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    error_code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")
    context: Optional[Dict[str, Any]] = Field(None, description="Error context")


class ExecutionMetrics(BaseModel):
    """Execution metrics and statistics."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    total_tokens_used: int = Field(0, ge=0, description="Total tokens used")
    api_calls_made: int = Field(0, ge=0, description="Total API calls made")
    success_rate: float = Field(0.0, ge=0.0, le=1.0, description="Success rate")
    average_response_time: float = Field(0.0, ge=0.0, description="Average response time in seconds")


class StandardizedOutput(BaseModel):
    """Standardized output format for execution results."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    execution_id: str = Field(..., description="Execution ID")
    execution_summary: ExecutionSummary = Field(..., description="Execution summary")
    team_results: Dict[str, TeamResult] = Field(..., description="Team results")
    errors: List[ErrorInfo] = Field(default_factory=list, description="Error list")
    metrics: ExecutionMetrics = Field(default_factory=ExecutionMetrics, description="Execution metrics")  # type: ignore


class ExecutionConfig(BaseModel):
    """Configuration for execution."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    stream_events: bool = Field(True, description="Enable streaming events")
    save_intermediate_results: bool = Field(True, description="Save intermediate results")
    max_parallel_teams: int = Field(1, gt=0, description="Maximum parallel teams")


class KeyConfig(BaseModel):
    """Configuration for API keys."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    key_id: str = Field(..., description="Key ID")
    provider: str = Field(..., description="Provider name")
    encrypted_key: str = Field(..., description="Encrypted key")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    last_used: Optional[datetime] = Field(None, description="Last used timestamp")
    usage_count: int = Field(0, ge=0, description="Usage count")
    is_active: bool = Field(True, description="Whether key is active")


class ExecutionContext(BaseModel):
    """Context for execution."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    execution_id: str = Field(..., description="Execution ID")
    team_id: str = Field(..., description="Team ID")
    config: ExecutionConfig = Field(..., description="Execution configuration")
    started_at: datetime = Field(default_factory=datetime.now, description="Start timestamp")
    current_team: Optional[str] = Field(None, description="Current team")


class TeamState(BaseModel):
    """Team state extending LangGraph's MessagesState."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    next: str
    team_id: str
    dependencies_met: bool
    execution_status: ExecutionStatus
    current_agent: Optional[str] = None


# API Response Models
class APIResponse(BaseModel):
    """Base API response model."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    success: bool = Field(..., description="Whether the request was successful")
    code: str = Field(..., description="Response code")
    message: str = Field(..., description="Response message")


class TeamCreationResponse(APIResponse):
    """Response for team creation."""
    data: Dict[str, Any] = Field(..., description="Team creation data")


class ExecutionStartResponse(APIResponse):
    """Response for execution start."""
    data: Dict[str, Any] = Field(..., description="Execution start data")


class ExecutionResultsResponse(APIResponse):
    """Response for execution results."""
    data: StandardizedOutput = Field(..., description="Execution results")


class FormattedResultsResponse(APIResponse):
    """Response for formatted results."""
    data: Dict[str, Any] = Field(..., description="Formatted results data")


# Template Models for Output Formatting
class OutputTemplate(BaseModel):
    """Template for output formatting."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="allow"  # Allow additional fields for flexible templates
    )


class ExtractionRules(BaseModel):
    """Rules for extracting information from results."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="allow"  # Allow additional fields for flexible rules
    )


class FormatRequest(BaseModel):
    """Request for formatting results."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    output_template: OutputTemplate = Field(..., description="Output template")
    extraction_rules: ExtractionRules = Field(..., description="Extraction rules")


# Utility type aliases for better code readability
AgentResult = Dict[str, Any]
DependencyGraph = Dict[str, List[str]]
AgentTeam = Dict[str, Any]
ExecutionSession = Dict[str, Any]
ErrorResponse = Dict[str, Any]
UsageStats = Dict[str, Any]