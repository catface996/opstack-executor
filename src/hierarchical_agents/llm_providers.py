"""
LLM provider support for hierarchical multi-agent system.

This module provides unified interfaces for different LLM providers
including OpenAI, OpenRouter, and AWS Bedrock. It handles client creation,
configuration, and provides a consistent interface across providers.
"""

import logging
from typing import Any, Dict, Optional, Union
from abc import ABC, abstractmethod

from .data_models import LLMConfig
from .key_manager import SecureKeyManager

logger = logging.getLogger(__name__)

# Import LLM libraries with fallback handling
try:
    from langchain_openai import ChatOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    logger.warning("langchain_openai not available. OpenAI support disabled.")
    OPENAI_AVAILABLE = False
    ChatOpenAI = None

try:
    from langchain_aws import ChatBedrock
    AWS_AVAILABLE = True
except ImportError:
    logger.warning("langchain_aws not available. AWS Bedrock support disabled.")
    AWS_AVAILABLE = False
    ChatBedrock = None

try:
    import boto3
    BOTO3_AVAILABLE = True
except ImportError:
    logger.warning("boto3 not available. AWS Bedrock support disabled.")
    BOTO3_AVAILABLE = False
    boto3 = None


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass


class UnsupportedProviderError(LLMProviderError):
    """Raised when an unsupported provider is requested."""
    pass


class ClientCreationError(LLMProviderError):
    """Raised when LLM client creation fails."""
    pass


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def create_client(self, config: LLMConfig, api_key: str) -> Any:
        """
        Create an LLM client instance.
        
        Args:
            config: LLM configuration
            api_key: Decrypted API key
            
        Returns:
            LLM client instance
        """
        pass
    
    @abstractmethod
    def validate_config(self, config: LLMConfig) -> bool:
        """
        Validate provider-specific configuration.
        
        Args:
            config: LLM configuration to validate
            
        Returns:
            bool: True if configuration is valid
        """
        pass
    
    @abstractmethod
    def get_supported_models(self) -> list[str]:
        """
        Get list of supported models for this provider.
        
        Returns:
            List of supported model names
        """
        pass


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM provider implementation."""
    
    def create_client(self, config: LLMConfig, api_key: str) -> Any:
        """Create OpenAI client."""
        if not OPENAI_AVAILABLE:
            raise ClientCreationError("OpenAI support not available. Install langchain-openai.")
        
        try:
            client_kwargs = {
                'model': config.model,
                'api_key': api_key,
                'temperature': config.temperature,
                'timeout': config.timeout,
            }
            
            if config.max_tokens:
                client_kwargs['max_tokens'] = config.max_tokens
            
            if config.base_url:
                client_kwargs['base_url'] = config.base_url
            
            client = ChatOpenAI(**client_kwargs)
            logger.info(f"Created OpenAI client for model: {config.model}")
            return client
            
        except Exception as e:
            raise ClientCreationError(f"Failed to create OpenAI client: {e}")
    
    def validate_config(self, config: LLMConfig) -> bool:
        """Validate OpenAI configuration."""
        if not config.model:
            return False
        
        # Check if model is in supported list
        supported_models = self.get_supported_models()
        if config.model not in supported_models:
            logger.warning(f"Model {config.model} not in known supported models list")
        
        return True
    
    def get_supported_models(self) -> list[str]:
        """Get supported OpenAI models."""
        return [
            'gpt-4o',
            'gpt-4o-mini',
            'gpt-4-turbo',
            'gpt-4',
            'gpt-3.5-turbo',
            'gpt-3.5-turbo-16k',
        ]


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter LLM provider implementation."""
    
    def create_client(self, config: LLMConfig, api_key: str) -> Any:
        """Create OpenRouter client (using OpenAI-compatible interface)."""
        if not OPENAI_AVAILABLE:
            raise ClientCreationError("OpenRouter support not available. Install langchain-openai.")
        
        try:
            # OpenRouter uses OpenAI-compatible API
            client_kwargs = {
                'model': config.model,
                'api_key': api_key,
                'base_url': config.base_url or 'https://openrouter.ai/api/v1',
                'temperature': config.temperature,
                'timeout': config.timeout,
                'default_headers': {
                    'HTTP-Referer': 'https://github.com/hierarchical-agents',
                    'X-Title': 'Hierarchical Multi-Agent System',
                }
            }
            
            if config.max_tokens:
                client_kwargs['max_tokens'] = config.max_tokens
            
            client = ChatOpenAI(**client_kwargs)
            logger.info(f"Created OpenRouter client for model: {config.model}")
            return client
            
        except Exception as e:
            raise ClientCreationError(f"Failed to create OpenRouter client: {e}")
    
    def validate_config(self, config: LLMConfig) -> bool:
        """Validate OpenRouter configuration."""
        if not config.model:
            return False
        
        # OpenRouter requires base_url or uses default
        if not config.base_url:
            logger.info("Using default OpenRouter base URL")
        
        return True
    
    def get_supported_models(self) -> list[str]:
        """Get supported OpenRouter models (popular ones)."""
        return [
            'anthropic/claude-3-opus',
            'anthropic/claude-3-sonnet',
            'anthropic/claude-3-haiku',
            'openai/gpt-4o',
            'openai/gpt-4-turbo',
            'openai/gpt-3.5-turbo',
            'meta-llama/llama-3.1-405b-instruct',
            'meta-llama/llama-3.1-70b-instruct',
            'google/gemini-pro',
            'mistralai/mixtral-8x7b-instruct',
        ]


class AWSBedrockProvider(BaseLLMProvider):
    """AWS Bedrock LLM provider implementation."""
    
    def create_client(self, config: LLMConfig, api_key: str) -> Any:
        """Create AWS Bedrock client."""
        if not AWS_AVAILABLE:
            raise ClientCreationError("AWS Bedrock support not available. Install langchain-aws.")
        
        if not BOTO3_AVAILABLE:
            raise ClientCreationError("AWS Bedrock support not available. Install boto3.")
        
        try:
            # For Bedrock, api_key is actually the AWS access key
            # We need to parse credentials (simplified approach)
            credentials = self._parse_aws_credentials(api_key)
            
            # Create boto3 session
            session = boto3.Session(
                aws_access_key_id=credentials.get('access_key_id'),
                aws_secret_access_key=credentials.get('secret_access_key'),
                aws_session_token=credentials.get('session_token'),
                region_name=config.region or 'us-east-1'
            )
            
            client_kwargs = {
                'model_id': config.model,
                'client': session.client('bedrock-runtime', region_name=config.region or 'us-east-1'),
                'model_kwargs': {
                    'temperature': config.temperature,
                }
            }
            
            if config.max_tokens:
                client_kwargs['model_kwargs']['max_tokens'] = config.max_tokens
            
            client = ChatBedrock(**client_kwargs)
            logger.info(f"Created AWS Bedrock client for model: {config.model}")
            return client
            
        except Exception as e:
            raise ClientCreationError(f"Failed to create AWS Bedrock client: {e}")
    
    def validate_config(self, config: LLMConfig) -> bool:
        """Validate AWS Bedrock configuration."""
        if not config.model:
            return False
        
        if not config.region:
            logger.warning("No region specified for AWS Bedrock, using us-east-1")
        
        # Check if model is in supported list
        supported_models = self.get_supported_models()
        if config.model not in supported_models:
            logger.warning(f"Model {config.model} not in known supported models list")
        
        return True
    
    def get_supported_models(self) -> list[str]:
        """Get supported AWS Bedrock models."""
        return [
            'anthropic.claude-3-opus-20240229-v1:0',
            'anthropic.claude-3-sonnet-20240229-v1:0',
            'anthropic.claude-3-haiku-20240307-v1:0',
            'anthropic.claude-v2:1',
            'anthropic.claude-v2',
            'anthropic.claude-instant-v1',
            'amazon.titan-text-express-v1',
            'amazon.titan-text-lite-v1',
            'meta.llama2-70b-chat-v1',
            'meta.llama2-13b-chat-v1',
            'mistral.mixtral-8x7b-instruct-v0:1',
            'mistral.mistral-7b-instruct-v0:2',
        ]
    
    def _parse_aws_credentials(self, credentials_string: str) -> Dict[str, str]:
        """
        Parse AWS credentials from string.
        
        Expected format: "access_key_id:secret_access_key" or 
                        "access_key_id:secret_access_key:session_token"
        """
        parts = credentials_string.split(':')
        if len(parts) < 2:
            raise ClientCreationError("Invalid AWS credentials format. Expected 'access_key:secret_key[:session_token]'")
        
        result = {
            'access_key_id': parts[0],
            'secret_access_key': parts[1]
        }
        
        if len(parts) > 2:
            result['session_token'] = parts[2]
        
        return result


class LLMProviderFactory:
    """Factory for creating LLM providers and clients."""
    
    def __init__(self, key_manager: Optional[SecureKeyManager] = None):
        """
        Initialize the provider factory.
        
        Args:
            key_manager: Optional key manager for retrieving API keys
        """
        self.key_manager = key_manager
        self._providers = {
            'openai': OpenAIProvider(),
            'openrouter': OpenRouterProvider(),
            'aws_bedrock': AWSBedrockProvider(),
        }
    
    def get_provider(self, provider_name: str) -> BaseLLMProvider:
        """
        Get a provider instance by name.
        
        Args:
            provider_name: Name of the provider
            
        Returns:
            BaseLLMProvider: Provider instance
            
        Raises:
            UnsupportedProviderError: If provider is not supported
        """
        if provider_name not in self._providers:
            raise UnsupportedProviderError(f"Provider '{provider_name}' is not supported")
        
        return self._providers[provider_name]
    
    def create_client(self, config: LLMConfig, api_key: Optional[str] = None) -> Any:
        """
        Create an LLM client from configuration.
        
        Args:
            config: LLM configuration
            api_key: Optional API key (if not provided, will use key_manager)
            
        Returns:
            LLM client instance
            
        Raises:
            UnsupportedProviderError: If provider is not supported
            ClientCreationError: If client creation fails
        """
        provider = self.get_provider(config.provider)
        
        # Validate configuration
        if not provider.validate_config(config):
            raise ClientCreationError(f"Invalid configuration for provider '{config.provider}'")
        
        # Get API key
        if api_key is None:
            if self.key_manager is None:
                raise ClientCreationError("No API key provided and no key manager available")
            api_key = self.key_manager.get_key(config.api_key_ref)
        
        # Create client
        return provider.create_client(config, api_key)
    
    def list_supported_providers(self) -> list[str]:
        """Get list of supported provider names."""
        return list(self._providers.keys())
    
    def get_supported_models(self, provider_name: str) -> list[str]:
        """
        Get supported models for a provider.
        
        Args:
            provider_name: Name of the provider
            
        Returns:
            List of supported model names
        """
        provider = self.get_provider(provider_name)
        return provider.get_supported_models()
    
    def validate_provider_config(self, config: LLMConfig) -> bool:
        """
        Validate configuration for a specific provider.
        
        Args:
            config: LLM configuration to validate
            
        Returns:
            bool: True if configuration is valid
        """
        try:
            provider = self.get_provider(config.provider)
            return provider.validate_config(config)
        except UnsupportedProviderError:
            return False


class LLMProviderConfig:
    """
    Configuration helper for LLM providers.
    
    This class provides utilities for creating and managing LLM configurations
    for different providers with appropriate defaults and validation.
    """
    
    @staticmethod
    def create_openai_config(
        model: str = "gpt-4o",
        api_key_ref: str = "openai_default",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        base_url: Optional[str] = None,
        timeout: int = 30
    ) -> LLMConfig:
        """Create OpenAI configuration."""
        return LLMConfig(
            provider="openai",
            model=model,
            api_key_ref=api_key_ref,
            temperature=temperature,
            max_tokens=max_tokens,
            base_url=base_url,
            timeout=timeout
        )
    
    @staticmethod
    def create_openrouter_config(
        model: str = "anthropic/claude-3-sonnet",
        api_key_ref: str = "openrouter_default",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: int = 30
    ) -> LLMConfig:
        """Create OpenRouter configuration."""
        return LLMConfig(
            provider="openrouter",
            model=model,
            api_key_ref=api_key_ref,
            temperature=temperature,
            max_tokens=max_tokens,
            base_url=base_url,
            timeout=timeout
        )
    
    @staticmethod
    def create_bedrock_config(
        model: str = "anthropic.claude-3-sonnet-20240229-v1:0",
        api_key_ref: str = "aws_bedrock_default",
        region: str = "us-east-1",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: int = 30
    ) -> LLMConfig:
        """Create AWS Bedrock configuration."""
        return LLMConfig(
            provider="aws_bedrock",
            model=model,
            api_key_ref=api_key_ref,
            region=region,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        )


# Utility functions
def create_llm_client(config: LLMConfig, key_manager: Optional[SecureKeyManager] = None, api_key: Optional[str] = None) -> Any:
    """
    Convenience function to create an LLM client.
    
    Args:
        config: LLM configuration
        key_manager: Optional key manager for retrieving API keys
        api_key: Optional API key (if not using key manager)
        
    Returns:
        LLM client instance
    """
    factory = LLMProviderFactory(key_manager)
    return factory.create_client(config, api_key)


def get_supported_providers() -> list[str]:
    """Get list of all supported LLM providers."""
    factory = LLMProviderFactory()
    return factory.list_supported_providers()


def get_supported_models(provider: str) -> list[str]:
    """
    Get supported models for a specific provider.
    
    Args:
        provider: Provider name
        
    Returns:
        List of supported model names
    """
    factory = LLMProviderFactory()
    return factory.get_supported_models(provider)


def validate_llm_config(config: LLMConfig) -> bool:
    """
    Validate an LLM configuration.
    
    Args:
        config: LLM configuration to validate
        
    Returns:
        bool: True if configuration is valid
    """
    factory = LLMProviderFactory()
    return factory.validate_provider_config(config)