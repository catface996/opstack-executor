"""
Tests for the configuration manager.

This module contains comprehensive tests for the ConfigManager class,
including validation, loading, saving, and error handling scenarios.
"""

import json
import pytest
import tempfile
from pathlib import Path
from typing import Dict, Any

from src.hierarchical_agents.config_manager import (
    ConfigManager,
    ConfigValidationError,
    load_config_from_file,
    validate_config_from_dict,
    save_config_to_file
)
from src.hierarchical_agents.data_models import HierarchicalTeam


class TestConfigManager:
    """Test cases for ConfigManager class."""
    
    @pytest.fixture
    def config_manager(self):
        """Create a ConfigManager instance for testing."""
        return ConfigManager()
    
    @pytest.fixture
    def valid_config_data(self) -> Dict[str, Any]:
        """Create a valid configuration dictionary for testing."""
        return {
            "team_name": "test_team",
            "description": "Test hierarchical team",
            "top_supervisor_config": {
                "llm_config": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "api_key_ref": "openai_key_001",
                    "temperature": 0.3
                },
                "system_prompt": "You are a top-level supervisor.",
                "user_prompt": "Coordinate the team execution.",
                "max_iterations": 10
            },
            "sub_teams": [
                {
                    "id": "team_001",
                    "name": "Research Team",
                    "description": "Handles research tasks",
                    "supervisor_config": {
                        "llm_config": {
                            "provider": "openai",
                            "model": "gpt-4o",
                            "api_key_ref": "openai_key_001",
                            "temperature": 0.3
                        },
                        "system_prompt": "You are a research team supervisor.",
                        "user_prompt": "Coordinate research activities.",
                        "max_iterations": 8
                    },
                    "agent_configs": [
                        {
                            "agent_id": "agent_001",
                            "agent_name": "Research Agent",
                            "llm_config": {
                                "provider": "openai",
                                "model": "gpt-4o",
                                "api_key_ref": "openai_key_001",
                                "temperature": 0.5
                            },
                            "system_prompt": "You are a research agent.",
                            "user_prompt": "Conduct research tasks.",
                            "tools": ["search", "analyze"],
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
    
    def test_validate_config_dict_success(self, config_manager, valid_config_data):
        """Test successful configuration validation."""
        team = config_manager.validate_config_dict(valid_config_data)
        
        assert isinstance(team, HierarchicalTeam)
        assert team.team_name == "test_team"
        assert len(team.sub_teams) == 1
        assert team.sub_teams[0].id == "team_001"
        assert len(team.sub_teams[0].agent_configs) == 1
    
    def test_validate_config_missing_required_fields(self, config_manager):
        """Test validation failure with missing required fields."""
        invalid_config = {
            "team_name": "test_team"
            # Missing other required fields
        }
        
        with pytest.raises(ConfigValidationError) as exc_info:
            config_manager.validate_config_dict(invalid_config)
        
        assert "Missing required fields" in str(exc_info.value)
    
    def test_validate_config_invalid_provider(self, config_manager, valid_config_data):
        """Test validation failure with invalid LLM provider."""
        valid_config_data["top_supervisor_config"]["llm_config"]["provider"] = "invalid_provider"
        
        with pytest.raises(ConfigValidationError) as exc_info:
            config_manager.validate_config_dict(valid_config_data)
        
        assert "Invalid provider" in str(exc_info.value)
    
    def test_validate_config_aws_bedrock_missing_region(self, config_manager, valid_config_data):
        """Test validation failure for AWS Bedrock without region."""
        valid_config_data["top_supervisor_config"]["llm_config"]["provider"] = "aws_bedrock"
        # Missing region field
        
        with pytest.raises(ConfigValidationError) as exc_info:
            config_manager.validate_config_dict(valid_config_data)
        
        assert "Region is required for AWS Bedrock" in str(exc_info.value)
    
    def test_validate_config_duplicate_agent_ids(self, config_manager, valid_config_data):
        """Test validation failure with duplicate agent IDs."""
        # Add another sub-team with duplicate agent ID
        duplicate_team = {
            "id": "team_002",
            "name": "Analysis Team",
            "description": "Handles analysis tasks",
            "supervisor_config": valid_config_data["sub_teams"][0]["supervisor_config"],
            "agent_configs": [
                {
                    "agent_id": "agent_001",  # Duplicate ID
                    "agent_name": "Analysis Agent",
                    "llm_config": valid_config_data["sub_teams"][0]["agent_configs"][0]["llm_config"],
                    "system_prompt": "You are an analysis agent.",
                    "user_prompt": "Conduct analysis tasks.",
                    "tools": ["analyze"],
                    "max_iterations": 5
                }
            ]
        }
        valid_config_data["sub_teams"].append(duplicate_team)
        
        with pytest.raises(ConfigValidationError) as exc_info:
            config_manager.validate_config_dict(valid_config_data)
        
        assert "Duplicate agent IDs" in str(exc_info.value)
    
    def test_validate_config_circular_dependencies(self, config_manager, valid_config_data):
        """Test validation failure with circular dependencies."""
        # Add another team and create circular dependency
        team_002 = {
            "id": "team_002",
            "name": "Analysis Team",
            "description": "Handles analysis tasks",
            "supervisor_config": valid_config_data["sub_teams"][0]["supervisor_config"],
            "agent_configs": [
                {
                    "agent_id": "agent_002",
                    "agent_name": "Analysis Agent",
                    "llm_config": valid_config_data["sub_teams"][0]["agent_configs"][0]["llm_config"],
                    "system_prompt": "You are an analysis agent.",
                    "user_prompt": "Conduct analysis tasks.",
                    "tools": ["analyze"],
                    "max_iterations": 5
                }
            ]
        }
        valid_config_data["sub_teams"].append(team_002)
        
        # Create circular dependency: team_001 -> team_002 -> team_001
        valid_config_data["dependencies"] = {
            "team_001": ["team_002"],
            "team_002": ["team_001"]
        }
        
        with pytest.raises(ConfigValidationError) as exc_info:
            config_manager.validate_config_dict(valid_config_data)
        
        assert "Circular dependency detected" in str(exc_info.value)
    
    def test_get_execution_order_no_dependencies(self, config_manager, valid_config_data):
        """Test execution order calculation with no dependencies."""
        team = config_manager.validate_config_dict(valid_config_data)
        execution_order = config_manager.get_execution_order(team)
        
        assert execution_order == ["team_001"]
    
    def test_get_execution_order_with_dependencies(self, config_manager, valid_config_data):
        """Test execution order calculation with dependencies."""
        # Add more teams with dependencies
        team_002 = {
            "id": "team_002",
            "name": "Analysis Team",
            "description": "Handles analysis tasks",
            "supervisor_config": valid_config_data["sub_teams"][0]["supervisor_config"],
            "agent_configs": [
                {
                    "agent_id": "agent_002",
                    "agent_name": "Analysis Agent",
                    "llm_config": valid_config_data["sub_teams"][0]["agent_configs"][0]["llm_config"],
                    "system_prompt": "You are an analysis agent.",
                    "user_prompt": "Conduct analysis tasks.",
                    "tools": ["analyze"],
                    "max_iterations": 5
                }
            ]
        }
        
        team_003 = {
            "id": "team_003",
            "name": "Writing Team",
            "description": "Handles writing tasks",
            "supervisor_config": valid_config_data["sub_teams"][0]["supervisor_config"],
            "agent_configs": [
                {
                    "agent_id": "agent_003",
                    "agent_name": "Writing Agent",
                    "llm_config": valid_config_data["sub_teams"][0]["agent_configs"][0]["llm_config"],
                    "system_prompt": "You are a writing agent.",
                    "user_prompt": "Conduct writing tasks.",
                    "tools": ["write"],
                    "max_iterations": 5
                }
            ]
        }
        
        valid_config_data["sub_teams"].extend([team_002, team_003])
        
        # team_002 depends on team_001, team_003 depends on team_002
        valid_config_data["dependencies"] = {
            "team_002": ["team_001"],
            "team_003": ["team_002"]
        }
        
        team = config_manager.validate_config_dict(valid_config_data)
        execution_order = config_manager.get_execution_order(team)
        
        assert execution_order == ["team_001", "team_002", "team_003"]
    
    def test_load_config_from_file(self, config_manager, valid_config_data):
        """Test loading configuration from file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(valid_config_data, f, indent=2)
            temp_path = f.name
        
        try:
            team = config_manager.load_config(temp_path)
            assert isinstance(team, HierarchicalTeam)
            assert team.team_name == "test_team"
        finally:
            Path(temp_path).unlink()
    
    def test_load_config_file_not_found(self, config_manager):
        """Test loading configuration from non-existent file."""
        with pytest.raises(FileNotFoundError):
            config_manager.load_config("non_existent_file.json")
    
    def test_load_config_invalid_json(self, config_manager):
        """Test loading configuration from invalid JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                config_manager.load_config(temp_path)
            assert "Invalid JSON" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()
    
    def test_save_config(self, config_manager, valid_config_data):
        """Test saving configuration to file."""
        team = config_manager.validate_config_dict(valid_config_data)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            config_manager.save_config(team, temp_path)
            
            # Verify the file was created and contains valid JSON
            assert Path(temp_path).exists()
            
            with open(temp_path, 'r') as f:
                saved_data = json.load(f)
            
            assert saved_data["team_name"] == "test_team"
            assert len(saved_data["sub_teams"]) == 1
        finally:
            Path(temp_path).unlink()
    
    def test_validate_config_completeness(self, config_manager, valid_config_data):
        """Test configuration completeness validation."""
        team = config_manager.validate_config_dict(valid_config_data)
        warnings = config_manager.validate_config_completeness(team)
        
        assert isinstance(warnings, dict)
        assert "missing_optional_fields" in warnings
        assert "configuration_recommendations" in warnings
        assert "potential_issues" in warnings
        
        # Should warn about single agent team
        assert any("only one agent" in warning for warning in warnings["potential_issues"])


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    @pytest.fixture
    def valid_config_data(self) -> Dict[str, Any]:
        """Create a valid configuration dictionary for testing."""
        return {
            "team_name": "test_team",
            "description": "Test hierarchical team",
            "top_supervisor_config": {
                "llm_config": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "api_key_ref": "openai_key_001",
                    "temperature": 0.3
                },
                "system_prompt": "You are a top-level supervisor.",
                "user_prompt": "Coordinate the team execution.",
                "max_iterations": 10
            },
            "sub_teams": [
                {
                    "id": "team_001",
                    "name": "Research Team",
                    "description": "Handles research tasks",
                    "supervisor_config": {
                        "llm_config": {
                            "provider": "openai",
                            "model": "gpt-4o",
                            "api_key_ref": "openai_key_001",
                            "temperature": 0.3
                        },
                        "system_prompt": "You are a research team supervisor.",
                        "user_prompt": "Coordinate research activities.",
                        "max_iterations": 8
                    },
                    "agent_configs": [
                        {
                            "agent_id": "agent_001",
                            "agent_name": "Research Agent",
                            "llm_config": {
                                "provider": "openai",
                                "model": "gpt-4o",
                                "api_key_ref": "openai_key_001",
                                "temperature": 0.5
                            },
                            "system_prompt": "You are a research agent.",
                            "user_prompt": "Conduct research tasks.",
                            "tools": ["search", "analyze"],
                            "max_iterations": 5
                        }
                    ]
                }
            ]
        }
    
    def test_load_config_from_file_convenience(self, valid_config_data):
        """Test convenience function for loading config from file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(valid_config_data, f, indent=2)
            temp_path = f.name
        
        try:
            team = load_config_from_file(temp_path)
            assert isinstance(team, HierarchicalTeam)
            assert team.team_name == "test_team"
        finally:
            Path(temp_path).unlink()
    
    def test_validate_config_from_dict_convenience(self, valid_config_data):
        """Test convenience function for validating config from dict."""
        team = validate_config_from_dict(valid_config_data)
        assert isinstance(team, HierarchicalTeam)
        assert team.team_name == "test_team"
    
    def test_save_config_to_file_convenience(self, valid_config_data):
        """Test convenience function for saving config to file."""
        team = validate_config_from_dict(valid_config_data)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            save_config_to_file(team, temp_path)
            
            # Verify the file was created
            assert Path(temp_path).exists()
            
            # Load it back and verify
            loaded_team = load_config_from_file(temp_path)
            assert loaded_team.team_name == team.team_name
        finally:
            Path(temp_path).unlink()


if __name__ == "__main__":
    pytest.main([__file__])