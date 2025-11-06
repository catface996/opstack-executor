"""
Tests for LLM provider support.

This module contains comprehensive tests for the LLM provider system,
including provider factories, client creation, and configuration validation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.hierarchical_agents.llm_providers import (
    LLMProviderFactory,
    OpenAIProvider,
    OpenRouterProvider,
    AWSBedrockProvider,
    LLMProviderConfig,
    LLMProviderError,
    UnsupportedProviderError,
    ClientCreationError,
    create_llm_client,
    get_supported_providers,
    get_supported_models,
    validate_llm_config
)
from src.hierarchical_agents.data_models import LLMConfig
from src.hierarchical_agents.key_manager import SecureKeyManager


class TestOpenAIProvider:
    """Test cases for OpenAI provider."""
    
    @pytest.fixture
    def provider(self):
        """Create OpenAI provider instance."""
        return OpenAIProvider()
    
    @pytest.fixture
    def openai_config(self):
        """Create OpenAI configuration."""
        return LLMConfig(
            provider="openai",
            model="gpt-4o",
            api_key_ref="test_key",
            temperature=0.7
        )
    
    def test_validate_config_success(self, provider, openai_config):
        """Test successful configuration validation."""
        assert provider.validate_config(openai_config) is True
    
    def test_validate_config_no_model(self, provider):
        """Test configuration validation with missing model."""
        config = LLMConfig(
            provider="openai",
            model="",
            api_key_ref="test_key"
        )
        assert provider.validate_config(config) is False
    
    def test_get_supported_models(self, provider):
        """Test getting supported models."""
        models = provider.get_supported_models()
        assert isinstance(models, list)
        assert len(models) > 0
        assert "gpt-4o" in models
        assert "gpt-3.5-turbo" in models
    
    @patch('src.hierarchical_agents.llm_providers.OPENAI_AVAILABLE', True)
    @patch('src.hierarchical_agents.llm_providers.ChatOpenAI')
    def test_create_client_success(self, mock_chat_openai, provider, openai_config):
        """Test successful client creation."""
        mock_client = Mock()
        mock_chat_openai.return_value = mock_client
        
        client = provider.create_client(openai_config, "sk-test123")
        
        assert client == mock_client
        mock_chat_openai.assert_called_once_with(
            model="gpt-4o",
            api_key="sk-test123",
            temperature=0.7,
            timeout=30
        )
    
    @patch('src.hierarchical_agents.llm_providers.OPENAI_AVAILABLE', False)
    def test_create_client_not_available(self, provider, openai_config):
        """Test client creation when OpenAI is not available."""
        with pytest.raises(ClientCreationError) as exc_info:
            provider.create_client(openai_config, "sk-test123")
        assert "OpenAI support not available" in str(exc_info.value)
    
    @patch('src.hierarchical_agents.llm_providers.OPENAI_AVAILABLE', True)
    @patch('src.hierarchical_agents.llm_providers.ChatOpenAI')
    def test_create_client_with_optional_params(self, mock_chat_openai, provider):
        """Test client creation with optional parameters."""
        config = LLMConfig(
            provider="openai",
            model="gpt-4o",
            api_key_ref="test_key",
            temperature=0.5,
            max_tokens=1000,
            base_url="https://custom.openai.com",
            timeout=60
        )
        
        mock_client = Mock()
        mock_chat_openai.return_value = mock_client
        
        client = provider.create_client(config, "sk-test123")
        
        mock_chat_openai.assert_called_once_with(
            model="gpt-4o",
            api_key="sk-test123",
            temperature=0.5,
            timeout=60,
            max_tokens=1000,
            base_url="https://custom.openai.com"
        )


class TestOpenRouterProvider:
    """Test cases for OpenRouter provider."""
    
    @pytest.fixture
    def provider(self):
        """Create OpenRouter provider instance."""
        return OpenRouterProvider()
    
    @pytest.fixture
    def openrouter_config(self):
        """Create OpenRouter configuration."""
        return LLMConfig(
            provider="openrouter",
            model="anthropic/claude-3-sonnet",
            api_key_ref="test_key",
            base_url="https://openrouter.ai/api/v1",
            temperature=0.7
        )
    
    def test_validate_config_success(self, provider, openrouter_config):
        """Test successful configuration validation."""
        assert provider.validate_config(openrouter_config) is True
    
    def test_get_supported_models(self, provider):
        """Test getting supported models."""
        models = provider.get_supported_models()
        assert isinstance(models, list)
        assert len(models) > 0
        assert "anthropic/claude-3-sonnet" in models
        assert "openai/gpt-4o" in models
    
    @patch('src.hierarchical_agents.llm_providers.OPENAI_AVAILABLE', True)
    @patch('src.hierarchical_agents.llm_providers.ChatOpenAI')
    def test_create_client_success(self, mock_chat_openai, provider, openrouter_config):
        """Test successful client creation."""
        mock_client = Mock()
        mock_chat_openai.return_value = mock_client
        
        client = provider.create_client(openrouter_config, "sk-or-test123")
        
        assert client == mock_client
        mock_chat_openai.assert_called_once()
        
        # Check the call arguments
        call_args = mock_chat_openai.call_args[1]
        assert call_args['model'] == "anthropic/claude-3-sonnet"
        assert call_args['api_key'] == "sk-or-test123"
        assert call_args['base_url'] == "https://openrouter.ai/api/v1"
        assert call_args['temperature'] == 0.7
        assert 'default_headers' in call_args
        assert 'HTTP-Referer' in call_args['default_headers']


class TestAWSBedrockProvider:
    """Test cases for AWS Bedrock provider."""
    
    @pytest.fixture
    def provider(self):
        """Create AWS Bedrock provider instance."""
        return AWSBedrockProvider()
    
    @pytest.fixture
    def bedrock_config(self):
        """Create Bedrock configuration."""
        return LLMConfig(
            provider="aws_bedrock",
            model="anthropic.claude-3-sonnet-20240229-v1:0",
            api_key_ref="test_key",
            region="us-east-1",
            temperature=0.7
        )
    
    def test_validate_config_success(self, provider, bedrock_config):
        """Test successful configuration validation."""
        assert provider.validate_config(bedrock_config) is True
    
    def test_validate_config_no_region(self, provider):
        """Test configuration validation without region."""
        # Use mock to test provider validation logic without Pydantic validation
        from unittest.mock import Mock
        mock_config = Mock()
        mock_config.model = "anthropic.claude-3-sonnet-20240229-v1:0"
        mock_config.region = None
        
        # Should still be valid, just log a warning
        assert provider.validate_config(mock_config) is True
    
    def test_get_supported_models(self, provider):
        """Test getting supported models."""
        models = provider.get_supported_models()
        assert isinstance(models, list)
        assert len(models) > 0
        assert "anthropic.claude-3-sonnet-20240229-v1:0" in models
        assert "amazon.titan-text-express-v1" in models
    
    def test_parse_aws_credentials(self, provider):
        """Test AWS credentials parsing."""
        # Test basic format
        creds = provider._parse_aws_credentials("access_key:secret_key")
        assert creds['access_key_id'] == "access_key"
        assert creds['secret_access_key'] == "secret_key"
        assert 'session_token' not in creds
        
        # Test with session token
        creds = provider._parse_aws_credentials("access_key:secret_key:session_token")
        assert creds['access_key_id'] == "access_key"
        assert creds['secret_access_key'] == "secret_key"
        assert creds['session_token'] == "session_token"
        
        # Test invalid format
        with pytest.raises(ClientCreationError):
            provider._parse_aws_credentials("invalid_format")
    
    @patch('src.hierarchical_agents.llm_providers.AWS_AVAILABLE', False)
    def test_create_client_not_available(self, provider, bedrock_config):
        """Test client creation when AWS is not available."""
        with pytest.raises(ClientCreationError) as exc_info:
            provider.create_client(bedrock_config, "access_key:secret_key")
        assert "AWS Bedrock support not available" in str(exc_info.value)


class TestLLMProviderFactory:
    """Test cases for LLM provider factory."""
    
    @pytest.fixture
    def factory(self):
        """Create provider factory instance."""
        return LLMProviderFactory()
    
    @pytest.fixture
    def mock_key_manager(self):
        """Create mock key manager."""
        key_manager = Mock(spec=SecureKeyManager)
        key_manager.get_key.return_value = "sk-test123"
        return key_manager
    
    def test_get_provider_success(self, factory):
        """Test successful provider retrieval."""
        provider = factory.get_provider("openai")
        assert isinstance(provider, OpenAIProvider)
        
        provider = factory.get_provider("openrouter")
        assert isinstance(provider, OpenRouterProvider)
        
        provider = factory.get_provider("aws_bedrock")
        assert isinstance(provider, AWSBedrockProvider)
    
    def test_get_provider_unsupported(self, factory):
        """Test unsupported provider retrieval."""
        with pytest.raises(UnsupportedProviderError) as exc_info:
            factory.get_provider("unsupported_provider")
        assert "Provider 'unsupported_provider' is not supported" in str(exc_info.value)
    
    def test_list_supported_providers(self, factory):
        """Test listing supported providers."""
        providers = factory.list_supported_providers()
        assert isinstance(providers, list)
        assert "openai" in providers
        assert "openrouter" in providers
        assert "aws_bedrock" in providers
    
    def test_get_supported_models(self, factory):
        """Test getting supported models for a provider."""
        models = factory.get_supported_models("openai")
        assert isinstance(models, list)
        assert len(models) > 0
        assert "gpt-4o" in models
    
    def test_validate_provider_config(self, factory):
        """Test provider configuration validation."""
        valid_config = LLMConfig(
            provider="openai",
            model="gpt-4o",
            api_key_ref="test_key"
        )
        assert factory.validate_provider_config(valid_config) is True
        
        # Test with unsupported provider using mock
        from unittest.mock import Mock
        invalid_config = Mock()
        invalid_config.provider = "unsupported"
        assert factory.validate_provider_config(invalid_config) is False
    
    @patch('src.hierarchical_agents.llm_providers.OPENAI_AVAILABLE', True)
    @patch('src.hierarchical_agents.llm_providers.ChatOpenAI')
    def test_create_client_with_key_manager(self, mock_chat_openai, mock_key_manager):
        """Test client creation with key manager."""
        factory = LLMProviderFactory(mock_key_manager)
        config = LLMConfig(
            provider="openai",
            model="gpt-4o",
            api_key_ref="test_key_ref"
        )
        
        mock_client = Mock()
        mock_chat_openai.return_value = mock_client
        
        client = factory.create_client(config)
        
        assert client == mock_client
        mock_key_manager.get_key.assert_called_once_with("test_key_ref")
    
    @patch('src.hierarchical_agents.llm_providers.OPENAI_AVAILABLE', True)
    @patch('src.hierarchical_agents.llm_providers.ChatOpenAI')
    def test_create_client_with_direct_key(self, mock_chat_openai):
        """Test client creation with direct API key."""
        factory = LLMProviderFactory()
        config = LLMConfig(
            provider="openai",
            model="gpt-4o",
            api_key_ref="test_key_ref"
        )
        
        mock_client = Mock()
        mock_chat_openai.return_value = mock_client
        
        client = factory.create_client(config, api_key="sk-direct123")
        
        assert client == mock_client
        mock_chat_openai.assert_called_once()
        call_args = mock_chat_openai.call_args[1]
        assert call_args['api_key'] == "sk-direct123"
    
    def test_create_client_no_key(self):
        """Test client creation without key or key manager."""
        factory = LLMProviderFactory()
        config = LLMConfig(
            provider="openai",
            model="gpt-4o",
            api_key_ref="test_key_ref"
        )
        
        with pytest.raises(ClientCreationError) as exc_info:
            factory.create_client(config)
        assert "No API key provided and no key manager available" in str(exc_info.value)


class TestLLMProviderConfig:
    """Test cases for LLM provider configuration helper."""
    
    def test_create_openai_config(self):
        """Test OpenAI configuration creation."""
        config = LLMProviderConfig.create_openai_config(
            model="gpt-4o",
            api_key_ref="my_openai_key",
            temperature=0.5
        )
        
        assert config.provider == "openai"
        assert config.model == "gpt-4o"
        assert config.api_key_ref == "my_openai_key"
        assert config.temperature == 0.5
        assert config.timeout == 30
    
    def test_create_openrouter_config(self):
        """Test OpenRouter configuration creation."""
        config = LLMProviderConfig.create_openrouter_config(
            model="anthropic/claude-3-sonnet",
            api_key_ref="my_openrouter_key",
            temperature=0.3
        )
        
        assert config.provider == "openrouter"
        assert config.model == "anthropic/claude-3-sonnet"
        assert config.api_key_ref == "my_openrouter_key"
        assert config.temperature == 0.3
        assert config.base_url == "https://openrouter.ai/api/v1"
    
    def test_create_bedrock_config(self):
        """Test AWS Bedrock configuration creation."""
        config = LLMProviderConfig.create_bedrock_config(
            model="anthropic.claude-3-sonnet-20240229-v1:0",
            api_key_ref="my_aws_key",
            region="us-west-2",
            temperature=0.4
        )
        
        assert config.provider == "aws_bedrock"
        assert config.model == "anthropic.claude-3-sonnet-20240229-v1:0"
        assert config.api_key_ref == "my_aws_key"
        assert config.region == "us-west-2"
        assert config.temperature == 0.4


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_get_supported_providers(self):
        """Test getting supported providers."""
        providers = get_supported_providers()
        assert isinstance(providers, list)
        assert "openai" in providers
        assert "openrouter" in providers
        assert "aws_bedrock" in providers
    
    def test_get_supported_models(self):
        """Test getting supported models."""
        models = get_supported_models("openai")
        assert isinstance(models, list)
        assert len(models) > 0
        assert "gpt-4o" in models
    
    def test_validate_llm_config(self):
        """Test LLM configuration validation."""
        valid_config = LLMConfig(
            provider="openai",
            model="gpt-4o",
            api_key_ref="test_key"
        )
        assert validate_llm_config(valid_config) is True
        
        # Test with unsupported provider using mock
        from unittest.mock import Mock
        invalid_config = Mock()
        invalid_config.provider = "unsupported"
        assert validate_llm_config(invalid_config) is False
    
    @patch('src.hierarchical_agents.llm_providers.OPENAI_AVAILABLE', True)
    @patch('src.hierarchical_agents.llm_providers.ChatOpenAI')
    def test_create_llm_client(self, mock_chat_openai):
        """Test LLM client creation utility."""
        config = LLMConfig(
            provider="openai",
            model="gpt-4o",
            api_key_ref="test_key"
        )
        
        mock_client = Mock()
        mock_chat_openai.return_value = mock_client
        
        client = create_llm_client(config, api_key="sk-test123")
        
        assert client == mock_client
        mock_chat_openai.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])