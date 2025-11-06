"""
Environment variable key management for hierarchical multi-agent system.

This module provides a simplified key management system that reads API keys
directly from environment variables, eliminating the need for complex
encryption and storage mechanisms.
"""

import os
import logging
from typing import Dict, Optional, Tuple
from pathlib import Path

from .data_models import LLMConfig

logger = logging.getLogger(__name__)

# Try to load python-dotenv for .env file support
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    logger.info("python-dotenv not available. .env file support disabled.")
    DOTENV_AVAILABLE = False
    load_dotenv = None


class EnvironmentKeyError(Exception):
    """Base exception for environment key management errors."""
    pass


class MissingAPIKeyError(EnvironmentKeyError):
    """Raised when required API key environment variable is missing."""
    pass


class InvalidKeyFormatError(EnvironmentKeyError):
    """Raised when API key format is invalid."""
    pass


class EnvironmentKeyManager:
    """
    Simplified key manager that reads API keys from environment variables.
    
    This class provides a clean interface for accessing API keys from
    environment variables with proper validation and error handling.
    Supports .env files for development convenience.
    """
    
    def __init__(self, env_file: Optional[str] = None, auto_load_dotenv: bool = True):
        """
        Initialize the environment key manager.
        
        Args:
            env_file: Optional path to .env file (default: .env in current directory)
            auto_load_dotenv: Whether to automatically load .env file if available
        """
        self.key_mappings = {
            "openai": "OPENAI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "aws_bedrock": {
                "access_key": "AWS_ACCESS_KEY_ID",
                "secret_key": "AWS_SECRET_ACCESS_KEY", 
                "session_token": "AWS_SESSION_TOKEN",  # Optional
                "region": "AWS_DEFAULT_REGION"
            }
        }
        
        # Load .env file if available and requested
        if auto_load_dotenv and DOTENV_AVAILABLE:
            env_path = env_file or ".env"
            if Path(env_path).exists():
                load_dotenv(env_path)
                logger.info(f"Loaded environment variables from: {env_path}")
            elif env_file:
                logger.warning(f"Specified .env file not found: {env_file}")
        
        logger.info("EnvironmentKeyManager initialized")
    
    def get_api_key(self, provider: str) -> str:
        """
        Get API key for the specified provider from environment variables.
        
        Args:
            provider: LLM provider name (openai, openrouter, aws_bedrock)
            
        Returns:
            str: API key or credentials string
            
        Raises:
            MissingAPIKeyError: If required environment variables are missing
            InvalidKeyFormatError: If key format is invalid
        """
        if provider not in self.key_mappings:
            raise EnvironmentKeyError(f"Unsupported provider: {provider}")
        
        if provider == "aws_bedrock":
            return self._get_aws_credentials()
        else:
            env_var = self.key_mappings[provider]
            api_key = os.getenv(env_var)
            
            if not api_key or not api_key.strip():
                raise MissingAPIKeyError(
                    f"API key not found in environment variable: {env_var}. "
                    f"Please set {env_var} in your environment or .env file."
                )
            
            # Validate key format
            if not self.validate_key_format(provider, api_key):
                raise InvalidKeyFormatError(f"Invalid API key format for provider: {provider}")
            
            return api_key
    
    def _get_aws_credentials(self) -> str:
        """
        Get AWS credentials from environment variables.
        
        Returns:
            str: Formatted credentials string (access_key:secret_key[:session_token])
        """
        aws_vars = self.key_mappings["aws_bedrock"]
        
        access_key = os.getenv(aws_vars["access_key"])
        secret_key = os.getenv(aws_vars["secret_key"])
        session_token = os.getenv(aws_vars["session_token"])
        
        if not access_key or not secret_key:
            missing_vars = []
            if not access_key:
                missing_vars.append(aws_vars["access_key"])
            if not secret_key:
                missing_vars.append(aws_vars["secret_key"])
            
            raise MissingAPIKeyError(
                f"AWS credentials not found in environment variables: {missing_vars}. "
                f"Please set {aws_vars['access_key']} and {aws_vars['secret_key']} "
                f"in your environment or .env file."
            )
        
        # Return formatted credentials
        if session_token:
            return f"{access_key}:{secret_key}:{session_token}"
        return f"{access_key}:{secret_key}"
    
    def validate_key_format(self, provider: str, api_key: str) -> bool:
        """
        Validate API key format for different providers.
        
        Args:
            provider: LLM provider name
            api_key: API key to validate
            
        Returns:
            bool: True if format is valid
        """
        if not api_key or not api_key.strip():
            return False
        
        if provider == "openai":
            return api_key.startswith("sk-") and len(api_key) > 20
        elif provider == "openrouter":
            return api_key.startswith("sk-or-") and len(api_key) > 20
        elif provider == "aws_bedrock":
            # For AWS, we expect the formatted credentials string
            parts = api_key.split(":")
            return len(parts) >= 2 and len(parts[0]) >= 16 and len(parts[1]) >= 16
        else:
            # Generic validation - just check it's not empty
            return len(api_key.strip()) > 0
    
    def check_provider_availability(self, provider: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a provider's API key is available and valid.
        
        Args:
            provider: LLM provider name
            
        Returns:
            Tuple[bool, Optional[str]]: (is_available, error_message)
        """
        try:
            api_key = self.get_api_key(provider)
            return True, None
        except EnvironmentKeyError as e:
            return False, str(e)
    
    def list_available_providers(self) -> Dict[str, bool]:
        """
        List all supported providers and their availability status.
        
        Returns:
            Dict[str, bool]: Provider name -> availability status
        """
        availability = {}
        for provider in self.key_mappings.keys():
            is_available, _ = self.check_provider_availability(provider)
            availability[provider] = is_available
        
        return availability
    
    def get_environment_info(self) -> Dict[str, any]:
        """
        Get information about the current environment configuration.
        
        Returns:
            Dict[str, any]: Environment information
        """
        info = {
            "dotenv_available": DOTENV_AVAILABLE,
            "supported_providers": list(self.key_mappings.keys()),
            "provider_availability": self.list_available_providers(),
            "environment_variables": {}
        }
        
        # Check which environment variables are set (without revealing values)
        for provider, env_vars in self.key_mappings.items():
            if provider == "aws_bedrock":
                info["environment_variables"][provider] = {
                    var_name: bool(os.getenv(var_name))
                    for var_name in env_vars.values()
                }
            else:
                info["environment_variables"][provider] = {
                    env_vars: bool(os.getenv(env_vars))
                }
        
        return info
    
    def create_llm_client_with_key(self, config: LLMConfig) -> str:
        """
        Get API key for creating LLM client with the given configuration.
        
        Args:
            config: LLM configuration
            
        Returns:
            str: API key for the provider
            
        Raises:
            MissingAPIKeyError: If API key is not available
            InvalidKeyFormatError: If key format is invalid
        """
        return self.get_api_key(config.provider)


# Utility functions for easy access
def get_api_key(provider: str, env_file: Optional[str] = None) -> str:
    """
    Convenience function to get API key for a provider.
    
    Args:
        provider: LLM provider name
        env_file: Optional path to .env file
        
    Returns:
        str: API key
    """
    manager = EnvironmentKeyManager(env_file=env_file)
    return manager.get_api_key(provider)


def check_all_providers(env_file: Optional[str] = None) -> Dict[str, bool]:
    """
    Convenience function to check availability of all providers.
    
    Args:
        env_file: Optional path to .env file
        
    Returns:
        Dict[str, bool]: Provider availability status
    """
    manager = EnvironmentKeyManager(env_file=env_file)
    return manager.list_available_providers()


def validate_environment_setup(env_file: Optional[str] = None) -> Dict[str, any]:
    """
    Validate the current environment setup for API keys.
    
    Args:
        env_file: Optional path to .env file
        
    Returns:
        Dict[str, any]: Validation results and recommendations
    """
    manager = EnvironmentKeyManager(env_file=env_file)
    info = manager.get_environment_info()
    
    # Add validation results
    validation = {
        "environment_info": info,
        "validation_results": {
            "total_providers": len(info["supported_providers"]),
            "available_providers": sum(info["provider_availability"].values()),
            "missing_providers": [
                provider for provider, available in info["provider_availability"].items()
                if not available
            ]
        },
        "recommendations": []
    }
    
    # Generate recommendations
    if not info["dotenv_available"]:
        validation["recommendations"].append(
            "Install python-dotenv for .env file support: pip install python-dotenv"
        )
    
    for provider in validation["validation_results"]["missing_providers"]:
        if provider == "aws_bedrock":
            validation["recommendations"].append(
                f"Set AWS credentials: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION"
            )
        else:
            env_var = manager.key_mappings[provider]
            validation["recommendations"].append(
                f"Set {provider} API key: {env_var}"
            )
    
    if not validation["validation_results"]["missing_providers"]:
        validation["recommendations"].append("✅ All supported providers are properly configured!")
    
    return validation


# Create a default instance for easy access
default_key_manager = EnvironmentKeyManager()