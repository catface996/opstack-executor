"""
Hierarchy Schemas - 层级团队请求/响应模型
"""

from typing import Optional, List
from pydantic import BaseModel, Field

from .common import PaginationRequest, LLMConfig


class WorkerConfig(BaseModel):
    """Worker 配置"""
    name: str = Field(..., min_length=1, max_length=100, description="Worker 名称")
    role: str = Field(..., min_length=1, max_length=200, description="角色描述")
    system_prompt: str = Field(..., min_length=1, description="系统提示词")
    tools: List[str] = Field(default=[], description="工具列表")
    llm_config: Optional[LLMConfig] = Field(default=None, description="LLM 配置")


class TeamConfig(BaseModel):
    """团队配置"""
    name: str = Field(..., min_length=1, max_length=100, description="团队名称")
    supervisor_prompt: str = Field(..., min_length=1, description="Supervisor 提示词")
    prevent_duplicate: bool = Field(default=True, description="防止重复调用")
    share_context: bool = Field(default=False, description="共享上下文")
    llm_config: Optional[LLMConfig] = Field(default=None, description="Team Supervisor LLM 配置")
    workers: List[WorkerConfig] = Field(..., min_length=1, description="Worker 列表")


class HierarchyCreateRequest(BaseModel):
    """创建层级团队请求"""
    name: str = Field(..., min_length=1, max_length=100, description="层级团队名称")
    description: Optional[str] = Field(default=None, description="描述")
    global_prompt: str = Field(..., min_length=1, description="全局 Supervisor 提示词")
    execution_mode: str = Field(default="sequential", pattern="^(sequential|parallel)$", description="执行模式")
    enable_context_sharing: bool = Field(default=False, description="启用上下文共享")
    llm_config: Optional[LLMConfig] = Field(default=None, description="Global Supervisor LLM 配置")
    teams: List[TeamConfig] = Field(..., min_length=1, description="团队列表")


class HierarchyUpdateRequest(BaseModel):
    """更新层级团队请求"""
    id: str = Field(..., description="层级团队 ID")
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    global_prompt: Optional[str] = None
    execution_mode: Optional[str] = Field(default=None, pattern="^(sequential|parallel)$")
    enable_context_sharing: Optional[bool] = None
    llm_config: Optional[LLMConfig] = Field(default=None, description="Global Supervisor LLM 配置")
    is_active: Optional[bool] = None
    teams: Optional[List[TeamConfig]] = Field(default=None, description="完整替换团队配置")


class HierarchyListRequest(PaginationRequest):
    """层级团队列表请求"""
    is_active: Optional[bool] = Field(default=None, description="过滤激活状态")


class WorkerResponse(BaseModel):
    """Worker 响应"""
    id: str
    name: str
    role: str
    system_prompt: str
    tools: List[str]
    order_index: int
    llm_config: Optional[LLMConfig] = None

    class Config:
        from_attributes = True


class TeamResponse(BaseModel):
    """团队响应"""
    id: str
    name: str
    supervisor_prompt: str
    prevent_duplicate: bool
    share_context: bool
    order_index: int
    llm_config: Optional[LLMConfig] = None
    workers: List[WorkerResponse]

    class Config:
        from_attributes = True


class HierarchyResponse(BaseModel):
    """层级团队响应"""
    id: str
    name: str
    description: Optional[str]
    global_prompt: str
    execution_mode: str
    enable_context_sharing: bool
    llm_config: Optional[LLMConfig] = None
    is_active: bool
    version: int
    teams: List[TeamResponse]
    created_at: Optional[str]
    updated_at: Optional[str]

    class Config:
        from_attributes = True


class HierarchyListItemResponse(BaseModel):
    """层级团队列表项响应（不含完整配置）"""
    id: str
    name: str
    description: Optional[str]
    execution_mode: str
    is_active: bool
    version: int
    team_count: int = 0
    created_at: Optional[str]
    updated_at: Optional[str]

    class Config:
        from_attributes = True
