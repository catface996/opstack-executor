"""
API集成测试

测试HTTP API接口的端到端功能，包括团队创建、执行控制、流式事件和结果查询。
"""

import pytest
import asyncio
import json
import httpx
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from hierarchical_agents.main import app
from hierarchical_agents.hierarchical_manager import HierarchicalManager
from hierarchical_agents.execution_engine import ExecutionEngine
from hierarchical_agents.state_manager import StateManager
from hierarchical_agents.event_manager import EventManager


class TestAPIIntegration:
    """API集成测试类"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)
    
    @pytest.fixture
    def sample_team_request(self):
        """示例团队创建请求"""
        return {
            "team_name": "api_test_team",
            "description": "API测试团队",
            "top_supervisor_config": {
                "llm_config": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "temperature": 0.3,
                    "max_tokens": 1000
                },
                "system_prompt": "API测试顶级监督者",
                "user_prompt": "协调API测试团队",
                "max_iterations": 10
            },
            "sub_teams": [{
                "id": "api_test_sub_team",
                "name": "API测试子团队",
                "description": "API测试子团队",
                "supervisor_config": {
                    "llm_config": {
                        "provider": "openai",
                        "model": "gpt-4o",
                        "temperature": 0.3
                    },
                    "system_prompt": "API测试子团队监督者",
                    "user_prompt": "执行API测试任务",
                    "max_iterations": 5
                },
                "agent_configs": [{
                    "agent_id": "api_test_agent",
                    "agent_name": "API测试智能体",
                    "llm_config": {
                        "provider": "openai",
                        "model": "gpt-4o",
                        "temperature": 0.3
                    },
                    "system_prompt": "API测试智能体",
                    "user_prompt": "执行API测试子任务",
                    "tools": [],
                    "max_iterations": 3
                }]
            }],
            "dependencies": {},
            "global_config": {
                "max_execution_time": 3600,
                "enable_streaming": True,
                "output_format": "detailed"
            }
        }
    
    def test_create_hierarchical_team_api(self, client, sample_team_request):
        """测试创建分层团队API"""
        with patch('hierarchical_agents.api.teams.HierarchicalManager') as mock_manager_class:
            # Mock团队管理器
            mock_manager = Mock()
            mock_team = Mock()
            mock_team.team_name = "api_test_team"
            mock_manager.build_hierarchy.return_value = mock_team
            mock_manager_class.return_value = mock_manager
            
            # 发送创建团队请求
            response = client.post(
                "/api/v1/hierarchical-teams",
                json=sample_team_request
            )
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["code"] == "TEAM_CREATED"
            assert "team_id" in data["data"]
            assert data["data"]["team_name"] == "api_test_team"
            assert data["data"]["status"] == "created"
    
    def test_execute_team_api(self, client):
        """测试执行团队API"""
        team_id = "test_team_123"
        
        with patch('hierarchical_agents.api.executions.get_hierarchical_manager') as mock_get_manager:
            with patch('hierarchical_agents.api.executions.get_execution_engine') as mock_get_engine:
                # Mock管理器和执行引擎
                mock_manager = Mock()
                mock_team = Mock()
                mock_manager.get_team.return_value = mock_team
                mock_get_manager.return_value = mock_manager
                
                mock_engine = Mock()
                mock_engine.start_execution = AsyncMock(return_value="exec_456")
                mock_get_engine.return_value = mock_engine
                
                # 发送执行请求
                response = client.post(
                    f"/api/v1/hierarchical-teams/{team_id}/execute",
                    json={
                        "execution_config": {
                            "stream_events": True,
                            "save_intermediate_results": True,
                            "max_parallel_teams": 1
                        }
                    }
                )
                
                # 验证响应
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["code"] == "EXECUTION_STARTED"
                assert data["data"]["execution_id"] == "exec_456"
                assert data["data"]["team_id"] == team_id
                assert data["data"]["status"] == "started"
    
    def test_get_execution_status_api(self, client):
        """测试获取执行状态API"""
        execution_id = "exec_789"
        
        with patch('hierarchical_agents.api.executions.get_state_manager') as mock_get_state:
            # Mock状态管理器
            mock_state_manager = Mock()
            mock_state_manager.get_execution_state = AsyncMock(return_value={
                "execution_id": execution_id,
                "status": "running",
                "started_at": "2024-01-15T10:35:00Z",
                "progress": 50,
                "current_team": "test_team"
            })
            mock_get_state.return_value = mock_state_manager
            
            # 发送状态查询请求
            response = client.get(f"/api/v1/executions/{execution_id}")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["execution_id"] == execution_id
            assert data["data"]["status"] == "running"
            assert data["data"]["progress"] == 50
    
    @pytest.mark.asyncio
    async def test_streaming_events_api(self):
        """测试流式事件API"""
        execution_id = "exec_stream_123"
        
        with patch('hierarchical_agents.api.executions.get_event_manager') as mock_get_events:
            # Mock事件管理器
            mock_event_manager = Mock()
            
            async def mock_event_stream():
                events = [
                    {
                        "timestamp": "2024-01-15T10:35:00Z",
                        "event_type": "execution_started",
                        "source_type": "system",
                        "execution_id": execution_id
                    },
                    {
                        "timestamp": "2024-01-15T10:35:30Z",
                        "event_type": "agent_started",
                        "source_type": "agent",
                        "execution_id": execution_id,
                        "agent_name": "测试智能体"
                    },
                    {
                        "timestamp": "2024-01-15T10:36:00Z",
                        "event_type": "execution_completed",
                        "source_type": "system",
                        "execution_id": execution_id
                    }
                ]
                for event in events:
                    yield f"data: {json.dumps(event)}\n\n"
            
            mock_event_manager.get_event_stream.return_value = mock_event_stream()
            mock_get_events.return_value = mock_event_manager
            
            # 使用httpx异步客户端测试SSE
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                async with client.stream(
                    "GET", 
                    f"/api/v1/executions/{execution_id}/stream"
                ) as response:
                    assert response.status_code == 200
                    assert response.headers["content-type"] == "text/event-stream"
                    
                    events_received = []
                    async for chunk in response.aiter_text():
                        if chunk.startswith("data: "):
                            event_data = json.loads(chunk[6:])
                            events_received.append(event_data)
                            if len(events_received) >= 3:
                                break
                    
                    # 验证接收到的事件
                    assert len(events_received) == 3
                    assert events_received[0]["event_type"] == "execution_started"
                    assert events_received[1]["event_type"] == "agent_started"
                    assert events_received[2]["event_type"] == "execution_completed"
    
    def test_get_execution_results_api(self, client):
        """测试获取执行结果API"""
        execution_id = "exec_results_123"
        
        with patch('hierarchical_agents.api.executions.get_output_formatter') as mock_get_formatter:
            # Mock输出格式化器
            mock_formatter = Mock()
            mock_results = {
                "execution_id": execution_id,
                "execution_summary": {
                    "status": "completed",
                    "started_at": "2024-01-15T10:35:00Z",
                    "completed_at": "2024-01-15T11:05:00Z",
                    "total_duration": 1800,
                    "teams_executed": 1,
                    "agents_involved": 1
                },
                "team_results": {
                    "test_team": {
                        "status": "completed",
                        "duration": 1800,
                        "agents": {
                            "test_agent": {
                                "status": "completed",
                                "output": "任务完成"
                            }
                        }
                    }
                },
                "errors": [],
                "metrics": {
                    "total_tokens_used": 1000,
                    "api_calls_made": 5,
                    "success_rate": 1.0,
                    "average_response_time": 2.0
                }
            }
            mock_formatter.get_execution_results.return_value = mock_results
            mock_get_formatter.return_value = mock_formatter
            
            # 发送结果查询请求
            response = client.get(f"/api/v1/executions/{execution_id}/results")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["execution_id"] == execution_id
            assert data["data"]["execution_summary"]["status"] == "completed"
            assert data["data"]["team_results"]["test_team"]["status"] == "completed"
    
    def test_format_execution_results_api(self, client):
        """测试格式化执行结果API"""
        execution_id = "exec_format_123"
        
        format_request = {
            "output_template": {
                "report_title": "测试报告",
                "summary": "{从执行结果中提取摘要}",
                "details": {
                    "teams": "{列出所有团队}",
                    "agents": "{列出所有智能体}"
                }
            },
            "extraction_rules": {
                "summary": "总结执行结果，不超过100字",
                "teams": "列出所有参与的团队",
                "agents": "列出所有参与的智能体"
            }
        }
        
        with patch('hierarchical_agents.api.executions.get_output_formatter') as mock_get_formatter:
            # Mock输出格式化器
            mock_formatter = Mock()
            mock_formatted_results = {
                "report_title": "测试报告",
                "summary": "执行成功完成，所有任务按预期执行",
                "details": {
                    "teams": ["测试团队"],
                    "agents": ["测试智能体"]
                }
            }
            mock_formatter.apply_template.return_value = mock_formatted_results
            mock_get_formatter.return_value = mock_formatter
            
            # 发送格式化请求
            response = client.post(
                f"/api/v1/executions/{execution_id}/results/format",
                json=format_request
            )
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["code"] == "FORMATTED_RESULTS_GENERATED"
            assert data["data"]["report_title"] == "测试报告"
            assert "summary" in data["data"]
            assert "details" in data["data"]
    
    def test_api_error_handling(self, client):
        """测试API错误处理"""
        # 测试无效团队ID
        response = client.post(
            "/api/v1/hierarchical-teams/invalid_team_id/execute",
            json={"execution_config": {}}
        )
        assert response.status_code == 404
        
        # 测试无效执行ID
        response = client.get("/api/v1/executions/invalid_exec_id")
        assert response.status_code == 404
        
        # 测试无效请求体
        response = client.post(
            "/api/v1/hierarchical-teams",
            json={"invalid": "data"}
        )
        assert response.status_code == 400
    
    def test_api_validation(self, client):
        """测试API请求验证"""
        # 测试缺少必需字段的团队创建请求
        invalid_request = {
            "team_name": "test_team"
            # 缺少其他必需字段
        }
        
        response = client.post(
            "/api/v1/hierarchical-teams",
            json=invalid_request
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "validation" in data["message"].lower() or "required" in data["message"].lower()
    
    @pytest.mark.asyncio
    async def test_concurrent_api_requests(self, client):
        """测试并发API请求"""
        team_id = "concurrent_test_team"
        
        with patch('hierarchical_agents.api.executions.get_execution_engine') as mock_get_engine:
            # Mock执行引擎
            mock_engine = Mock()
            mock_engine.start_execution = AsyncMock(
                side_effect=lambda team, config: f"exec_{id(team)}"
            )
            mock_get_engine.return_value = mock_engine
            
            # 创建多个并发请求
            async def make_request(client, request_id):
                response = client.post(
                    f"/api/v1/hierarchical-teams/{team_id}/execute",
                    json={
                        "execution_config": {
                            "stream_events": True,
                            "request_id": request_id
                        }
                    }
                )
                return response
            
            # 使用httpx异步客户端
            async with httpx.AsyncClient(app=app, base_url="http://test") as async_client:
                # 发送5个并发请求
                tasks = [
                    async_client.post(
                        f"/api/v1/hierarchical-teams/{team_id}/execute",
                        json={
                            "execution_config": {
                                "stream_events": True,
                                "request_id": i
                            }
                        }
                    )
                    for i in range(5)
                ]
                
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 验证所有请求都成功处理
                successful_responses = [
                    r for r in responses 
                    if not isinstance(r, Exception) and r.status_code == 200
                ]
                
                # 至少应该有一些成功的响应
                assert len(successful_responses) > 0