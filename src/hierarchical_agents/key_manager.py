"""
Secure key management for hierarchical multi-agent system.

This module provides secure storage and retrieval of API keys for different
LLM providers using AES-256 encryption. Keys are stored encrypted and
referenced by unique identifiers.
"""

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from .data_models import KeyConfig

logger = logging.getLogger(__name__)


class KeyManagerError(Exception):
    """Base exception for key manager errors."""
    pass


class KeyNotFoundError(KeyManagerError):
    """Raised when a key reference is not found."""
    pass


class InvalidKeyError(KeyManagerError):
    """Raised when a key is invalid or corrupted."""
    pass


class SecureKeyManager:
    """
    Secure key manager for API keys using AES-256 encryption.
    
    This class provides secure storage and retrieval of API keys for different
    LLM providers. Keys are encrypted using AES-256 and stored with unique
    references. The encryption key is derived from a master password using PBKDF2.
    """
    
    def __init__(self, storage_path: Optional[str] = None, master_password: Optional[str] = None):
        """
        Initialize the secure key manager.
        
        Args:
            storage_path: Path to store encrypted keys (default: ~/.hierarchical_agents/keys.json)
            master_password: Master password for encryption (default: from environment)
        """
        self.storage_path = Path(storage_path or Path.home() / ".hierarchical_agents" / "keys.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Get master password from environment or parameter
        self.master_password = master_password or os.getenv("HIERARCHICAL_AGENTS_MASTER_KEY")
        if not self.master_password:
            raise KeyManagerError(
                "Master password required. Set HIERARCHICAL_AGENTS_MASTER_KEY environment variable "
                "or provide master_password parameter."
            )
        
        # Initialize encryption
        self._cipher = self._create_cipher(self.master_password)
        
        # Load existing keys
        self._keys: Dict[str, KeyConfig] = {}
        self._load_keys()
        
        logger.info(f"SecureKeyManager initialized with storage at: {self.storage_path}")
    
    def _create_cipher(self, password: str) -> Fernet:
        """Create a Fernet cipher from password using PBKDF2."""
        # Use a fixed salt for consistency (in production, consider storing salt separately)
        salt = b'hierarchical_agents_salt_2024'
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return Fernet(key)
    
    def store_key(self, provider: str, api_key: str, key_id: Optional[str] = None) -> str:
        """
        Store an API key securely and return its reference.
        
        Args:
            provider: LLM provider name (openai, openrouter, aws_bedrock)
            api_key: The actual API key to store
            key_id: Optional custom key ID (auto-generated if not provided)
            
        Returns:
            str: Key reference ID for later retrieval
            
        Raises:
            KeyManagerError: If encryption or storage fails
        """
        if not api_key or not api_key.strip():
            raise KeyManagerError("API key cannot be empty")
        
        if not provider or not provider.strip():
            raise KeyManagerError("Provider cannot be empty")
        
        # Generate unique key ID if not provided
        if not key_id:
            key_id = f"{provider}_key_{uuid.uuid4().hex[:8]}"
        
        try:
            # Encrypt the API key
            encrypted_key = self._cipher.encrypt(api_key.encode()).decode()
            
            # Create key configuration
            key_config = KeyConfig(
                key_id=key_id,
                provider=provider,
                encrypted_key=encrypted_key,
                created_at=datetime.now(),
                is_active=True
            )
            
            # Store in memory and persist
            self._keys[key_id] = key_config
            self._save_keys()
            
            logger.info(f"Stored key for provider '{provider}' with ID: {key_id}")
            return key_id
            
        except Exception as e:
            raise KeyManagerError(f"Failed to store key: {e}")
    
    def get_key(self, key_ref: str) -> str:
        """
        Retrieve and decrypt an API key by reference.
        
        Args:
            key_ref: Key reference ID returned by store_key()
            
        Returns:
            str: Decrypted API key
            
        Raises:
            KeyNotFoundError: If key reference is not found
            InvalidKeyError: If key cannot be decrypted
        """
        if key_ref not in self._keys:
            raise KeyNotFoundError(f"Key reference '{key_ref}' not found")
        
        key_config = self._keys[key_ref]
        
        if not key_config.is_active:
            raise InvalidKeyError(f"Key '{key_ref}' is inactive")
        
        try:
            # Decrypt the API key
            decrypted_key = self._cipher.decrypt(key_config.encrypted_key.encode()).decode()
            
            # Update usage statistics
            key_config.last_used = datetime.now()
            key_config.usage_count += 1
            self._save_keys()
            
            logger.debug(f"Retrieved key for provider '{key_config.provider}' (ID: {key_ref})")
            return decrypted_key
            
        except Exception as e:
            raise InvalidKeyError(f"Failed to decrypt key '{key_ref}': {e}")
    
    def delete_key(self, key_ref: str) -> bool:
        """
        Delete a stored API key.
        
        Args:
            key_ref: Key reference ID to delete
            
        Returns:
            bool: True if key was deleted, False if not found
        """
        if key_ref not in self._keys:
            return False
        
        provider = self._keys[key_ref].provider
        del self._keys[key_ref]
        self._save_keys()
        
        logger.info(f"Deleted key for provider '{provider}' (ID: {key_ref})")
        return True
    
    def list_keys(self) -> Dict[str, Dict[str, Any]]:
        """
        List all stored keys (without revealing actual keys).
        
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of key metadata
        """
        result = {}
        for key_id, key_config in self._keys.items():
            result[key_id] = {
                'provider': key_config.provider,
                'created_at': key_config.created_at.isoformat(),
                'last_used': key_config.last_used.isoformat() if key_config.last_used else None,
                'usage_count': key_config.usage_count,
                'is_active': key_config.is_active
            }
        return result
    
    def deactivate_key(self, key_ref: str) -> bool:
        """
        Deactivate a key without deleting it.
        
        Args:
            key_ref: Key reference ID to deactivate
            
        Returns:
            bool: True if key was deactivated, False if not found
        """
        if key_ref not in self._keys:
            return False
        
        self._keys[key_ref].is_active = False
        self._save_keys()
        
        logger.info(f"Deactivated key: {key_ref}")
        return True
    
    def activate_key(self, key_ref: str) -> bool:
        """
        Activate a previously deactivated key.
        
        Args:
            key_ref: Key reference ID to activate
            
        Returns:
            bool: True if key was activated, False if not found
        """
        if key_ref not in self._keys:
            return False
        
        self._keys[key_ref].is_active = True
        self._save_keys()
        
        logger.info(f"Activated key: {key_ref}")
        return True
    
    def rotate_key(self, key_ref: str, new_api_key: str) -> bool:
        """
        Rotate an existing API key with a new value.
        
        Args:
            key_ref: Key reference ID to rotate
            new_api_key: New API key value
            
        Returns:
            bool: True if key was rotated, False if not found
            
        Raises:
            KeyManagerError: If encryption fails
        """
        if key_ref not in self._keys:
            return False
        
        if not new_api_key or not new_api_key.strip():
            raise KeyManagerError("New API key cannot be empty")
        
        try:
            # Encrypt the new API key
            encrypted_key = self._cipher.encrypt(new_api_key.encode()).decode()
            
            # Update the key configuration
            key_config = self._keys[key_ref]
            key_config.encrypted_key = encrypted_key
            key_config.last_used = None  # Reset usage stats
            key_config.usage_count = 0
            
            self._save_keys()
            
            logger.info(f"Rotated key for provider '{key_config.provider}' (ID: {key_ref})")
            return True
            
        except Exception as e:
            raise KeyManagerError(f"Failed to rotate key '{key_ref}': {e}")
    
    def get_usage_stats(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """
        Get usage statistics for keys.
        
        Args:
            provider: Optional provider filter
            
        Returns:
            Dict[str, Any]: Usage statistics
        """
        keys_to_analyze = self._keys.values()
        if provider:
            keys_to_analyze = [k for k in keys_to_analyze if k.provider == provider]
        
        total_keys = len(keys_to_analyze)
        active_keys = len([k for k in keys_to_analyze if k.is_active])
        total_usage = sum(k.usage_count for k in keys_to_analyze)
        
        providers = {}
        for key_config in keys_to_analyze:
            if key_config.provider not in providers:
                providers[key_config.provider] = {
                    'total_keys': 0,
                    'active_keys': 0,
                    'total_usage': 0
                }
            providers[key_config.provider]['total_keys'] += 1
            if key_config.is_active:
                providers[key_config.provider]['active_keys'] += 1
            providers[key_config.provider]['total_usage'] += key_config.usage_count
        
        return {
            'total_keys': total_keys,
            'active_keys': active_keys,
            'inactive_keys': total_keys - active_keys,
            'total_usage': total_usage,
            'providers': providers
        }
    
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
        
        # Basic format validation for different providers
        if provider == "openai":
            return api_key.startswith("sk-") and len(api_key) > 20
        elif provider == "openrouter":
            return api_key.startswith("sk-or-") and len(api_key) > 20
        elif provider == "aws_bedrock":
            # AWS access keys are typically 20 characters
            return len(api_key) >= 16 and api_key.isalnum()
        else:
            # Generic validation - just check it's not empty
            return len(api_key.strip()) > 0
    
    def _load_keys(self) -> None:
        """Load keys from storage file."""
        if not self.storage_path.exists():
            logger.info("No existing key storage found, starting fresh")
            return
        
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for key_id, key_data in data.items():
                # Convert datetime strings back to datetime objects
                key_data['created_at'] = datetime.fromisoformat(key_data['created_at'])
                if key_data.get('last_used'):
                    key_data['last_used'] = datetime.fromisoformat(key_data['last_used'])
                
                self._keys[key_id] = KeyConfig(**key_data)
            
            logger.info(f"Loaded {len(self._keys)} keys from storage")
            
        except Exception as e:
            logger.error(f"Failed to load keys from storage: {e}")
            # Continue with empty key store rather than failing
            self._keys = {}
    
    def _save_keys(self) -> None:
        """Save keys to storage file."""
        try:
            # Convert to serializable format
            data = {}
            for key_id, key_config in self._keys.items():
                data[key_id] = {
                    'key_id': key_config.key_id,
                    'provider': key_config.provider,
                    'encrypted_key': key_config.encrypted_key,
                    'created_at': key_config.created_at.isoformat(),
                    'last_used': key_config.last_used.isoformat() if key_config.last_used else None,
                    'usage_count': key_config.usage_count,
                    'is_active': key_config.is_active
                }
            
            # Write to temporary file first, then rename for atomic operation
            temp_path = self.storage_path.with_suffix('.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            temp_path.replace(self.storage_path)
            logger.debug(f"Saved {len(self._keys)} keys to storage")
            
        except Exception as e:
            logger.error(f"Failed to save keys to storage: {e}")
            raise KeyManagerError(f"Failed to save keys: {e}")
    
    def backup_keys(self, backup_path: str) -> None:
        """
        Create a backup of encrypted keys.
        
        Args:
            backup_path: Path for backup file
        """
        backup_path = Path(backup_path)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Copy current storage to backup location
            if self.storage_path.exists():
                import shutil
                shutil.copy2(self.storage_path, backup_path)
                logger.info(f"Keys backed up to: {backup_path}")
            else:
                logger.warning("No keys to backup")
        except Exception as e:
            raise KeyManagerError(f"Failed to backup keys: {e}")
    
    def restore_keys(self, backup_path: str) -> None:
        """
        Restore keys from a backup file.
        
        Args:
            backup_path: Path to backup file
        """
        backup_path = Path(backup_path)
        
        if not backup_path.exists():
            raise KeyManagerError(f"Backup file not found: {backup_path}")
        
        try:
            # Copy backup to current storage location
            import shutil
            shutil.copy2(backup_path, self.storage_path)
            
            # Reload keys
            self._keys = {}
            self._load_keys()
            
            logger.info(f"Keys restored from: {backup_path}")
        except Exception as e:
            raise KeyManagerError(f"Failed to restore keys: {e}")


# Utility functions for key management
def create_key_manager(storage_path: Optional[str] = None, master_password: Optional[str] = None) -> SecureKeyManager:
    """
    Create a SecureKeyManager instance.
    
    Args:
        storage_path: Optional custom storage path
        master_password: Optional master password (uses environment if not provided)
        
    Returns:
        SecureKeyManager: Configured key manager instance
    """
    return SecureKeyManager(storage_path=storage_path, master_password=master_password)


def generate_master_key() -> str:
    """
    Generate a secure master key for encryption.
    
    Returns:
        str: Base64-encoded master key
    """
    key = Fernet.generate_key()
    return base64.urlsafe_b64encode(key).decode()