"""
Hierarchy Schemas - 层级团队请求/响应模型
"""

from typing import Optional, List
from pydantic import BaseModel, Field

from .common import PaginationRequest, LLMConfig


class AgentConfig(BaseModel):
    """Agent 配置对象（统一结构，用于所有层级的 Agent）"""
    agent_id: Optional[str] = Field(default=None, max_length=100, description="Agent 唯一标识，在同一 Hierarchy 内唯一")
    system_prompt: str = Field(..., min_length=1, description="系统提示词，定义 Agent 角色")
    user_message: Optional[str] = Field(default=None, description="预定义的用户消息")
    llm_config: Optional[LLMConfig] = Field(default=None, description="LLM 配置")


class WorkerConfig(BaseModel):
    """Worker 配置"""
    agent_id: Optional[str] = Field(default=None, max_length=100, description="Worker 的 agent_id")
    name: str = Field(..., min_length=1, max_length=100, description="Worker 名称")
    role: str = Field(..., min_length=1, max_length=200, description="角色描述")
    system_prompt: str = Field(..., min_length=1, description="系统提示词")
    user_message: Optional[str] = Field(default=None, description="预定义的用户消息")
    tools: Optional[List[str]] = Field(default=[], description="工具列表，可以为 null 或空数组")
    llm_config: Optional[LLMConfig] = Field(default=None, description="LLM 配置")

    def model_post_init(self, __context):
        # 将 null 转换为空列表
        if self.tools is None:
            object.__setattr__(self, 'tools', [])


class TeamConfig(BaseModel):
    """团队配置"""
    name: str = Field(..., min_length=1, max_length=100, description="团队名称")
    team_supervisor_agent: AgentConfig = Field(..., description="Team Supervisor Agent 配置")
    prevent_duplicate: bool = Field(default=True, description="防止重复调用")
    share_context: bool = Field(default=False, description="共享上下文")
    workers: List[WorkerConfig] = Field(..., min_length=1, description="Worker 列表")


class HierarchyCreateRequest(BaseModel):
    """创建层级团队请求"""
    name: str = Field(..., min_length=1, max_length=100, description="层级团队名称")
    description: Optional[str] = Field(default=None, description="描述")
    execution_mode: str = Field(default="sequential", pattern="^(sequential|parallel)$", description="执行模式")
    enable_context_sharing: bool = Field(default=False, description="启用上下文共享")
    global_supervisor_agent: AgentConfig = Field(..., description="Global Supervisor Agent 配置")
    teams: List[TeamConfig] = Field(..., min_length=1, description="团队列表")


class HierarchyUpdateRequest(BaseModel):
    """更新层级团队请求"""
    id: str = Field(..., description="层级团队 ID")
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    execution_mode: Optional[str] = Field(default=None, pattern="^(sequential|parallel)$")
    enable_context_sharing: Optional[bool] = None
    global_supervisor_agent: Optional[AgentConfig] = Field(default=None, description="Global Supervisor Agent 配置")
    teams: Optional[List[TeamConfig]] = Field(default=None, description="完整替换团队配置")
    is_active: Optional[bool] = None


class HierarchyListRequest(PaginationRequest):
    """层级团队列表请求"""
    is_active: Optional[bool] = Field(default=None, description="过滤激活状态")
