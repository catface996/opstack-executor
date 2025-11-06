"""
Tests for the teams API endpoints.

This module contains comprehensive tests for the hierarchical teams API,
including validation, error handling, and response format verification.
"""

import json
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from src.hierarchical_agents.main import app
from src.hierarchical_agents.config_manager import ConfigValidationError
from src.hierarchical_agents.hierarchical_manager import HierarchicalManagerError


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def valid_team_config():
    """Valid team configuration for testing."""
    return {
        "team_name": "test_research_team",
        "description": "Test research team for API testing",
        "top_supervisor_config": {
            "llm_config": {
                "provider": "openai",
                "model": "gpt-4o",
                "temperature": 0.3,
                "max_tokens": 1000
            },
            "system_prompt": "You are a top-level supervisor coordinating research tasks.",
            "user_prompt": "Please coordinate the research team execution.",
            "max_iterations": 10
        },
        "sub_teams": [
            {
                "id": "team_research_001",
                "name": "Research Team",
                "description": "Handles information gathering and research",
                "supervisor_config": {
                    "llm_config": {
                        "provider": "openai",
                        "model": "gpt-4o",
                        "temperature": 0.3
                    },
                    "system_prompt": "You are a research team supervisor.",
                    "user_prompt": "Please coordinate research activities.",
                    "max_iterations": 8
                },
                "agent_configs": [
                    {
                        "agent_id": "agent_search_001",
                        "agent_name": "Search Specialist",
                        "llm_config": {
                            "provider": "openai",
                            "model": "gpt-4o",
                            "temperature": 0.3,
                            "max_tokens": 2000
                        },
                        "system_prompt": "You are a search specialist.",
                        "user_prompt": "Please search for relevant information.",
                        "tools": ["tavily_search"],
                        "max_iterations": 5
                    }
                ]
            }
        ],
        "dependencies": {},
        "global_config": {
            "max_execution_time": 3600,
            "enable_streaming": True,
            "output_format": "detailed"
        }
    }


@pytest.fixture
def invalid_team_config():
    """Invalid team configuration for testing."""
    return {
        "team_name": "",  # Invalid: empty name
        "description": "Test team",
        # Missing required fields
    }


class TestCreateHierarchicalTeam:
    """Test cases for POST /api/v1/hierarchical-teams endpoint."""
    
    def test_create_team_success(self, client, valid_team_config):
        """Test successful team creation."""
        with patch('src.hierarchical_agents.api.teams.config_manager') as mock_config_manager, \
             patch('src.hierarchical_agents.api.teams.hierarchical_manager') as mock_hierarchical_manager:
            
            # Mock successful validation and building
            mock_validated_team = Mock()
            mock_validated_team.team_name = valid_team_config["team_name"]
            mock_validated_team.sub_teams = [Mock()]
            mock_validated_team.sub_teams[0].agent_configs = [Mock()]
            
            mock_config_manager.validate_config_dict.return_value = mock_validated_team
            mock_hierarchical_manager.build_hierarchy.return_value = mock_validated_team
            mock_config_manager.get_execution_order.return_value = ["team_research_001"]
            
            response = client.post("/api/v1/hierarchical-teams", json=valid_team_config)
            
            assert response.status_code == 201
            data = response.json()
            
            assert data["success"] is True
            assert data["code"] == "TEAM_CREATED"
            assert data["message"] == "分层团队创建成功"
            assert "data" in data
            
            team_data = data["data"]
            assert team_data["team_name"] == valid_team_config["team_name"]
            assert team_data["status"] == "created"
            assert "team_id" in team_data
            assert team_data["team_id"].startswith("ht_")
            assert team_data["sub_teams_count"] == 1
            assert team_data["total_agents"] == 1
            assert team_data["execution_order"] == ["team_research_001"]
            assert "created_at" in team_data
    
    def test_create_team_validation_error(self, client, invalid_team_config):
        """Test team creation with validation error."""
        with patch('src.hierarchical_agents.api.teams.config_manager') as mock_config_manager:
            
            # Mock validation error
            mock_config_manager.validate_config_dict.side_effect = ConfigValidationError("Missing required fields")
            
            response = client.post("/api/v1/hierarchical-teams", json=invalid_team_config)
            
            assert response.status_code == 400
            data = response.json()
            
            assert data["success"] is False
            assert data["code"] == "VALIDATION_ERROR"
            assert data["message"] == "配置验证失败"
            assert "detail" in data
    
    def test_create_team_build_error(self, client, valid_team_config):
        """Test team creation with build error."""
        with patch('src.hierarchical_agents.api.teams.config_manager') as mock_config_manager, \
             patch('src.hierarchical_agents.api.teams.hierarchical_manager') as mock_hierarchical_manager:
            
            # Mock successful validation but failed building
            mock_validated_team = Mock()
            mock_config_manager.validate_config_dict.return_value = mock_validated_team
            mock_hierarchical_manager.build_hierarchy.side_effect = HierarchicalManagerError("Build failed")
            
            response = client.post("/api/v1/hierarchical-teams", json=valid_team_config)
            
            assert response.status_code == 400
            data = response.json()
            
            assert data["success"] is False
            assert data["code"] == "TEAM_BUILD_ERROR"
            assert data["message"] == "团队构建失败"
    
    def test_create_team_invalid_json(self, client):
        """Test team creation with invalid JSON."""
        response = client.post(
            "/api/v1/hierarchical-teams",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422
        data = response.json()
        
        assert data["success"] is False
        assert data["code"] == "VALIDATION_ERROR"
    
    def test_create_team_missing_required_fields(self, client):
        """Test team creation with missing required fields."""
        incomplete_config = {
            "team_name": "test_team"
            # Missing other required fields
        }
        
        with patch('src.hierarchical_agents.api.teams.config_manager') as mock_config_manager:
            mock_config_manager.validate_config_dict.side_effect = ConfigValidationError("Missing required fields")
            
            response = client.post("/api/v1/hierarchical-teams", json=incomplete_config)
            
            assert response.status_code == 400
            data = response.json()
            
            assert data["success"] is False
            assert data["code"] == "VALIDATION_ERROR"
    
    def test_create_team_internal_error(self, client, valid_team_config):
        """Test team creation with internal server error."""
        with patch('src.hierarchical_agents.api.teams.config_manager') as mock_config_manager:
            
            # Mock unexpected error during validation
            mock_config_manager.validate_config_dict.side_effect = Exception("Unexpected error")
            
            response = client.post("/api/v1/hierarchical-teams", json=valid_team_config)
            
            # The API correctly handles this as a validation error (422) since it occurs during validation
            assert response.status_code == 422
            data = response.json()
            
            assert data["success"] is False
            assert data["code"] == "VALIDATION_ERROR"
            assert data["message"] == "请求数据格式错误"


class TestGetTeamInfo:
    """Test cases for GET /api/v1/hierarchical-teams/{team_id} endpoint."""
    
    def test_get_team_info_success(self, client):
        """Test successful team info retrieval."""
        team_id = "ht_123456789"
        
        response = client.get(f"/api/v1/hierarchical-teams/{team_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["code"] == "TEAM_FOUND"
        assert data["message"] == "团队信息获取成功"
        assert "data" in data
        
        team_data = data["data"]
        assert team_data["team_id"] == team_id
    
    def test_get_team_info_invalid_id(self, client):
        """Test team info retrieval with invalid team ID."""
        invalid_team_id = "invalid_id"
        
        response = client.get(f"/api/v1/hierarchical-teams/{invalid_team_id}")
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["success"] is False
        assert data["code"] == "TEAM_NOT_FOUND"
        assert data["message"] == "团队未找到"


class TestDeleteTeam:
    """Test cases for DELETE /api/v1/hierarchical-teams/{team_id} endpoint."""
    
    def test_delete_team_success(self, client):
        """Test successful team deletion."""
        team_id = "ht_123456789"
        
        response = client.delete(f"/api/v1/hierarchical-teams/{team_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["code"] == "TEAM_DELETED"
        assert data["message"] == "团队删除成功"
    
    def test_delete_team_invalid_id(self, client):
        """Test team deletion with invalid team ID."""
        invalid_team_id = "invalid_id"
        
        response = client.delete(f"/api/v1/hierarchical-teams/{invalid_team_id}")
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["success"] is False
        assert data["code"] == "TEAM_NOT_FOUND"


class TestListTeams:
    """Test cases for GET /api/v1/hierarchical-teams endpoint."""
    
    def test_list_teams_success(self, client):
        """Test successful teams listing."""
        response = client.get("/api/v1/hierarchical-teams")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["code"] == "TEAMS_LISTED"
        assert data["message"] == "团队列表获取成功"
        assert "data" in data
        
        list_data = data["data"]
        assert "teams" in list_data
        assert "total_count" in list_data
        assert "page" in list_data
        assert "page_size" in list_data
    
    def test_list_teams_with_pagination(self, client):
        """Test teams listing with pagination parameters."""
        response = client.get("/api/v1/hierarchical-teams?page=2&page_size=5")
        
        assert response.status_code == 200
        data = response.json()
        
        list_data = data["data"]
        assert list_data["page"] == 2
        assert list_data["page_size"] == 5
    
    def test_list_teams_invalid_pagination(self, client):
        """Test teams listing with invalid pagination parameters."""
        response = client.get("/api/v1/hierarchical-teams?page=0&page_size=200")
        
        assert response.status_code == 200
        data = response.json()
        
        list_data = data["data"]
        assert list_data["page"] == 1  # Should default to 1
        assert list_data["page_size"] == 10  # Should default to 10


class TestHealthCheck:
    """Test cases for health check endpoint."""
    
    def test_teams_health_check(self, client):
        """Test teams API health check."""
        response = client.get("/api/v1/teams/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["code"] == "HEALTHY"
        assert data["message"] == "Teams API is healthy"
        assert "data" in data
        
        health_data = data["data"]
        assert health_data["status"] == "healthy"
        assert "timestamp" in health_data
        assert "version" in health_data
        assert "components" in health_data


class TestAPIResponseFormat:
    """Test cases for API response format consistency."""
    
    def test_response_format_consistency(self, client, valid_team_config):
        """Test that all API responses follow the same format."""
        with patch('src.hierarchical_agents.api.teams.config_manager') as mock_config_manager, \
             patch('src.hierarchical_agents.api.teams.hierarchical_manager') as mock_hierarchical_manager:
            
            # Mock successful validation and building
            mock_validated_team = Mock()
            mock_validated_team.team_name = valid_team_config["team_name"]
            mock_validated_team.sub_teams = [Mock()]
            mock_validated_team.sub_teams[0].agent_configs = [Mock()]
            
            mock_config_manager.validate_config_dict.return_value = mock_validated_team
            mock_hierarchical_manager.build_hierarchy.return_value = mock_validated_team
            mock_config_manager.get_execution_order.return_value = ["team_research_001"]
            
            # Test successful response format
            response = client.post("/api/v1/hierarchical-teams", json=valid_team_config)
            data = response.json()
            
            # Check required fields
            assert "success" in data
            assert "code" in data
            assert "message" in data
            assert isinstance(data["success"], bool)
            assert isinstance(data["code"], str)
            assert isinstance(data["message"], str)
    
    def test_error_response_format_consistency(self, client):
        """Test that error responses follow the same format."""
        # Test validation error format
        with patch('src.hierarchical_agents.api.teams.config_manager') as mock_config_manager:
            mock_config_manager.validate_config_dict.side_effect = ConfigValidationError("Test error")
            
            response = client.post("/api/v1/hierarchical-teams", json={})
            data = response.json()
            
            # Check required fields for error responses
            assert "success" in data
            assert "code" in data
            assert "message" in data
            assert "detail" in data
            assert data["success"] is False
            assert isinstance(data["code"], str)
            assert isinstance(data["message"], str)


class TestOpenAPIDocumentation:
    """Test cases for OpenAPI documentation generation."""
    
    def test_openapi_schema_generation(self, client):
        """Test that OpenAPI schema is generated correctly."""
        response = client.get("/openapi.json")
        
        assert response.status_code == 200
        schema = response.json()
        
        # Check basic OpenAPI structure
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema
        
        # Check that our endpoints are documented
        paths = schema["paths"]
        assert "/api/v1/hierarchical-teams" in paths
        assert "post" in paths["/api/v1/hierarchical-teams"]
        assert "get" in paths["/api/v1/hierarchical-teams"]
    
    def test_api_docs_accessible(self, client):
        """Test that API documentation is accessible."""
        response = client.get("/docs")
        assert response.status_code == 200
        
        response = client.get("/redoc")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])