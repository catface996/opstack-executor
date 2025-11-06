"""
Tests for environment variable key manager.

This module contains comprehensive tests for the EnvironmentKeyManager class,
including environment variable reading, validation, and error handling.
"""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock

from src.hierarchical_agents.env_key_manager import (
    EnvironmentKeyManager,
    EnvironmentKeyError,
    MissingAPIKeyError,
    InvalidKeyFormatError,
    get_api_key,
    check_all_providers,
    validate_environment_setup
)
from src.hierarchical_agents.data_models import LLMConfig


class TestEnvironmentKeyManager:
    """Test cases for EnvironmentKeyManager class."""
    
    @pytest.fixture
    def clean_env(self):
        """Clean environment fixture that removes API key environment variables."""
        # Store original values
        original_env = {}
        env_vars = [
            "OPENAI_API_KEY", "OPENROUTER_API_KEY", 
            "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", 
            "AWS_SESSION_TOKEN", "AWS_DEFAULT_REGION"
        ]
        
        for var in env_vars:
            original_env[var] = os.environ.get(var)
            if var in os.environ:
                del os.environ[var]
        
        yield
        
        # Restore original values
        for var, value in original_env.items():
            if value is not None:
                os.environ[var] = value
            elif var in os.environ:
                del os.environ[var]
    
    @pytest.fixture
    def key_manager(self, clean_env):
        """Create EnvironmentKeyManager instance with clean environment."""
        return EnvironmentKeyManager(auto_load_dotenv=False)
    
    @pytest.fixture
    def temp_env_file(self):
        """Create temporary .env file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("OPENAI_API_KEY=sk-test123456789abcdef\n")
            f.write("OPENROUTER_API_KEY=sk-or-test123456789abcdef\n")
            f.write("AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n")
            f.write("AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\n")
            f.write("AWS_DEFAULT_REGION=us-east-1\n")
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        Path(temp_path).unlink()
    
    def test_initialization_success(self, clean_env):
        """Test successful initialization."""
        manager = EnvironmentKeyManager(auto_load_dotenv=False)
        assert manager.key_mappings is not None
        assert "openai" in manager.key_mappings
        assert "openrouter" in manager.key_mappings
        assert "aws_bedrock" in manager.key_mappings
    
    @patch('src.hierarchical_agents.env_key_manager.DOTENV_AVAILABLE', True)
    @patch('src.hierarchical_agents.env_key_manager.load_dotenv')
    def test_initialization_with_dotenv(self, mock_load_dotenv, temp_env_file):
        """Test initialization with .env file loading."""
        manager = EnvironmentKeyManager(env_file=temp_env_file)
        mock_load_dotenv.assert_called_once_with(temp_env_file)
    
    def test_get_openai_api_key_success(self, key_manager):
        """Test successful OpenAI API key retrieval."""
        test_key = "sk-test123456789abcdef"
        os.environ["OPENAI_API_KEY"] = test_key
        
        api_key = key_manager.get_api_key("openai")
        assert api_key == test_key
    
    def test_get_openai_api_key_missing(self, key_manager):
        """Test OpenAI API key retrieval when environment variable is missing."""
        with pytest.raises(MissingAPIKeyError) as exc_info:
            key_manager.get_api_key("openai")
        
        assert "OPENAI_API_KEY" in str(exc_info.value)
        assert "environment variable" in str(exc_info.value)
    
    def test_get_openrouter_api_key_success(self, key_manager):
        """Test successful OpenRouter API key retrieval."""
        test_key = "sk-or-test123456789abcdef"
        os.environ["OPENROUTER_API_KEY"] = test_key
        
        api_key = key_manager.get_api_key("openrouter")
        assert api_key == test_key
    
    def test_get_aws_credentials_success(self, key_manager):
        """Test successful AWS credentials retrieval."""
        os.environ["AWS_ACCESS_KEY_ID"] = "AKIAIOSFODNN7EXAMPLE"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        
        credentials = key_manager.get_api_key("aws_bedrock")
        expected = "AKIAIOSFODNN7EXAMPLE:wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        assert credentials == expected
    
    def test_get_aws_credentials_with_session_token(self, key_manager):
        """Test AWS credentials retrieval with session token."""
        os.environ["AWS_ACCESS_KEY_ID"] = "AKIAIOSFODNN7EXAMPLE"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        os.environ["AWS_SESSION_TOKEN"] = "session_token_example"
        
        credentials = key_manager.get_api_key("aws_bedrock")
        expected = "AKIAIOSFODNN7EXAMPLE:wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY:session_token_example"
        assert credentials == expected
    
    def test_get_aws_credentials_missing_access_key(self, key_manager):
        """Test AWS credentials retrieval with missing access key."""
        os.environ["AWS_SECRET_ACCESS_KEY"] = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        
        with pytest.raises(MissingAPIKeyError) as exc_info:
            key_manager.get_api_key("aws_bedrock")
        
        assert "AWS_ACCESS_KEY_ID" in str(exc_info.value)
    
    def test_get_aws_credentials_missing_secret_key(self, key_manager):
        """Test AWS credentials retrieval with missing secret key."""
        os.environ["AWS_ACCESS_KEY_ID"] = "AKIAIOSFODNN7EXAMPLE"
        
        with pytest.raises(MissingAPIKeyError) as exc_info:
            key_manager.get_api_key("aws_bedrock")
        
        assert "AWS_SECRET_ACCESS_KEY" in str(exc_info.value)
    
    def test_get_api_key_unsupported_provider(self, key_manager):
        """Test API key retrieval for unsupported provider."""
        with pytest.raises(EnvironmentKeyError) as exc_info:
            key_manager.get_api_key("unsupported_provider")
        
        assert "Unsupported provider" in str(exc_info.value)
    
    def test_validate_key_format_openai_valid(self, key_manager):
        """Test OpenAI key format validation with valid key."""
        valid_key = "sk-test123456789abcdef"
        assert key_manager.validate_key_format("openai", valid_key) is True
    
    def test_validate_key_format_openai_invalid(self, key_manager):
        """Test OpenAI key format validation with invalid key."""
        invalid_keys = ["invalid_key", "sk-short", "", "   "]
        for key in invalid_keys:
            assert key_manager.validate_key_format("openai", key) is False
    
    def test_validate_key_format_openrouter_valid(self, key_manager):
        """Test OpenRouter key format validation with valid key."""
        valid_key = "sk-or-test123456789abcdef"
        assert key_manager.validate_key_format("openrouter", valid_key) is True
    
    def test_validate_key_format_openrouter_invalid(self, key_manager):
        """Test OpenRouter key format validation with invalid key."""
        invalid_keys = ["sk-test123456789abcdef", "sk-or-short", "", "invalid"]
        for key in invalid_keys:
            assert key_manager.validate_key_format("openrouter", key) is False
    
    def test_validate_key_format_aws_valid(self, key_manager):
        """Test AWS credentials format validation with valid credentials."""
        valid_creds = "AKIAIOSFODNN7EXAMPLE:wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        assert key_manager.validate_key_format("aws_bedrock", valid_creds) is True
        
        valid_creds_with_token = "AKIAIOSFODNN7EXAMPLE:wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY:session_token"
        assert key_manager.validate_key_format("aws_bedrock", valid_creds_with_token) is True
    
    def test_validate_key_format_aws_invalid(self, key_manager):
        """Test AWS credentials format validation with invalid credentials."""
        invalid_creds = ["invalid", "short:key", "", "only_one_part"]
        for creds in invalid_creds:
            assert key_manager.validate_key_format("aws_bedrock", creds) is False
    
    def test_check_provider_availability_available(self, key_manager):
        """Test provider availability check when provider is available."""
        os.environ["OPENAI_API_KEY"] = "sk-test123456789abcdef"
        
        is_available, error_msg = key_manager.check_provider_availability("openai")
        assert is_available is True
        assert error_msg is None
    
    def test_check_provider_availability_unavailable(self, key_manager):
        """Test provider availability check when provider is unavailable."""
        is_available, error_msg = key_manager.check_provider_availability("openai")
        assert is_available is False
        assert error_msg is not None
        assert "OPENAI_API_KEY" in error_msg
    
    def test_list_available_providers(self, key_manager):
        """Test listing available providers."""
        # Set up some providers
        os.environ["OPENAI_API_KEY"] = "sk-test123456789abcdef"
        os.environ["AWS_ACCESS_KEY_ID"] = "AKIAIOSFODNN7EXAMPLE"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        
        availability = key_manager.list_available_providers()
        
        assert isinstance(availability, dict)
        assert availability["openai"] is True
        assert availability["aws_bedrock"] is True
        assert availability["openrouter"] is False  # Not set
    
    def test_get_environment_info(self, key_manager):
        """Test getting environment information."""
        os.environ["OPENAI_API_KEY"] = "sk-test123456789abcdef"
        
        info = key_manager.get_environment_info()
        
        assert isinstance(info, dict)
        assert "dotenv_available" in info
        assert "supported_providers" in info
        assert "provider_availability" in info
        assert "environment_variables" in info
        
        assert "openai" in info["supported_providers"]
        assert info["provider_availability"]["openai"] is True
    
    def test_create_llm_client_with_key(self, key_manager):
        """Test getting API key for LLM client creation."""
        test_key = "sk-test123456789abcdef"
        os.environ["OPENAI_API_KEY"] = test_key
        
        config = LLMConfig(provider="openai", model="gpt-4o")
        api_key = key_manager.create_llm_client_with_key(config)
        
        assert api_key == test_key
    
    def test_invalid_key_format_raises_error(self, key_manager):
        """Test that invalid key format raises appropriate error."""
        os.environ["OPENAI_API_KEY"] = "invalid_key_format"
        
        with pytest.raises(InvalidKeyFormatError) as exc_info:
            key_manager.get_api_key("openai")
        
        assert "Invalid API key format" in str(exc_info.value)


class TestUtilityFunctions:
    """Test utility functions."""
    
    @pytest.fixture
    def clean_env(self):
        """Clean environment fixture."""
        original_openai = os.environ.get("OPENAI_API_KEY")
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
        
        yield
        
        if original_openai:
            os.environ["OPENAI_API_KEY"] = original_openai
    
    def test_get_api_key_utility(self, clean_env):
        """Test get_api_key utility function."""
        test_key = "sk-test123456789abcdef"
        os.environ["OPENAI_API_KEY"] = test_key
        
        api_key = get_api_key("openai")
        assert api_key == test_key
    
    def test_check_all_providers_utility(self, clean_env):
        """Test check_all_providers utility function."""
        os.environ["OPENAI_API_KEY"] = "sk-test123456789abcdef"
        
        availability = check_all_providers()
        assert isinstance(availability, dict)
        assert availability["openai"] is True
        assert availability["openrouter"] is False
    
    def test_validate_environment_setup_utility(self, clean_env):
        """Test validate_environment_setup utility function."""
        os.environ["OPENAI_API_KEY"] = "sk-test123456789abcdef"
        
        validation = validate_environment_setup()
        
        assert isinstance(validation, dict)
        assert "environment_info" in validation
        assert "validation_results" in validation
        assert "recommendations" in validation
        
        results = validation["validation_results"]
        assert "total_providers" in results
        assert "available_providers" in results
        assert "missing_providers" in results
        
        assert results["available_providers"] >= 1  # At least OpenAI should be available
        assert isinstance(validation["recommendations"], list)


class TestDotenvIntegration:
    """Test .env file integration."""
    
    @pytest.fixture
    def temp_env_file(self):
        """Create temporary .env file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("OPENAI_API_KEY=sk-dotenv123456789abcdef\n")
            f.write("OPENROUTER_API_KEY=sk-or-dotenv123456789abcdef\n")
            temp_path = f.name
        
        yield temp_path
        
        Path(temp_path).unlink()
    
    @patch('src.hierarchical_agents.env_key_manager.DOTENV_AVAILABLE', True)
    @patch('src.hierarchical_agents.env_key_manager.load_dotenv')
    def test_dotenv_loading(self, mock_load_dotenv, temp_env_file):
        """Test that .env file is loaded when available."""
        manager = EnvironmentKeyManager(env_file=temp_env_file)
        mock_load_dotenv.assert_called_once_with(temp_env_file)
    
    @patch('src.hierarchical_agents.env_key_manager.DOTENV_AVAILABLE', False)
    def test_dotenv_not_available(self):
        """Test behavior when python-dotenv is not available."""
        # Should not raise an error
        manager = EnvironmentKeyManager()
        assert manager is not None


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.fixture
    def key_manager(self):
        """Create key manager for error testing."""
        return EnvironmentKeyManager(auto_load_dotenv=False)
    
    def test_empty_environment_variable(self, key_manager):
        """Test handling of empty environment variable."""
        os.environ["OPENAI_API_KEY"] = ""
        
        with pytest.raises(MissingAPIKeyError):
            key_manager.get_api_key("openai")
    
    def test_whitespace_only_environment_variable(self, key_manager):
        """Test handling of whitespace-only environment variable."""
        os.environ["OPENAI_API_KEY"] = "   "
        
        with pytest.raises(MissingAPIKeyError):
            key_manager.get_api_key("openai")
    
    def test_partial_aws_credentials(self, key_manager):
        """Test handling of partial AWS credentials."""
        os.environ["AWS_ACCESS_KEY_ID"] = "AKIAIOSFODNN7EXAMPLE"
        # Missing AWS_SECRET_ACCESS_KEY
        
        with pytest.raises(MissingAPIKeyError) as exc_info:
            key_manager.get_api_key("aws_bedrock")
        
        assert "AWS_SECRET_ACCESS_KEY" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__])