"""
Tests for the secure key manager.

This module contains comprehensive tests for the SecureKeyManager class,
including encryption, storage, retrieval, and error handling scenarios.
"""

import os
import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from src.hierarchical_agents.key_manager import (
    SecureKeyManager,
    KeyManagerError,
    KeyNotFoundError,
    InvalidKeyError,
    create_key_manager,
    generate_master_key
)


class TestSecureKeyManager:
    """Test cases for SecureKeyManager class."""
    
    @pytest.fixture
    def temp_storage(self):
        """Create a temporary storage directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir) / "test_keys.json"
    
    @pytest.fixture
    def key_manager(self, temp_storage):
        """Create a SecureKeyManager instance for testing."""
        return SecureKeyManager(
            storage_path=str(temp_storage),
            master_password="test_master_password_123"
        )
    
    def test_initialization_success(self, temp_storage):
        """Test successful initialization of key manager."""
        manager = SecureKeyManager(
            storage_path=str(temp_storage),
            master_password="test_password"
        )
        assert manager.storage_path == temp_storage
        assert len(manager._keys) == 0
    
    def test_initialization_no_master_password(self, temp_storage):
        """Test initialization failure without master password."""
        # Clear environment variable if it exists
        old_env = os.environ.get("HIERARCHICAL_AGENTS_MASTER_KEY")
        if old_env:
            del os.environ["HIERARCHICAL_AGENTS_MASTER_KEY"]
        
        try:
            with pytest.raises(KeyManagerError) as exc_info:
                SecureKeyManager(storage_path=str(temp_storage))
            assert "Master password required" in str(exc_info.value)
        finally:
            # Restore environment variable
            if old_env:
                os.environ["HIERARCHICAL_AGENTS_MASTER_KEY"] = old_env
    
    def test_store_key_success(self, key_manager):
        """Test successful key storage."""
        api_key = "sk-test123456789"
        key_ref = key_manager.store_key("openai", api_key)
        
        assert key_ref is not None
        assert key_ref.startswith("openai_key_")
        assert len(key_manager._keys) == 1
        assert key_ref in key_manager._keys
    
    def test_store_key_custom_id(self, key_manager):
        """Test key storage with custom ID."""
        api_key = "sk-test123456789"
        custom_id = "my_custom_key_001"
        key_ref = key_manager.store_key("openai", api_key, key_id=custom_id)
        
        assert key_ref == custom_id
        assert custom_id in key_manager._keys
    
    def test_store_key_empty_key(self, key_manager):
        """Test key storage with empty API key."""
        with pytest.raises(KeyManagerError) as exc_info:
            key_manager.store_key("openai", "")
        assert "API key cannot be empty" in str(exc_info.value)
        
        with pytest.raises(KeyManagerError) as exc_info:
            key_manager.store_key("openai", "   ")
        assert "API key cannot be empty" in str(exc_info.value)
    
    def test_store_key_empty_provider(self, key_manager):
        """Test key storage with empty provider."""
        with pytest.raises(KeyManagerError) as exc_info:
            key_manager.store_key("", "sk-test123")
        assert "Provider cannot be empty" in str(exc_info.value)
    
    def test_get_key_success(self, key_manager):
        """Test successful key retrieval."""
        original_key = "sk-test123456789"
        key_ref = key_manager.store_key("openai", original_key)
        
        retrieved_key = key_manager.get_key(key_ref)
        assert retrieved_key == original_key
        
        # Check usage statistics were updated
        key_config = key_manager._keys[key_ref]
        assert key_config.usage_count == 1
        assert key_config.last_used is not None
    
    def test_get_key_not_found(self, key_manager):
        """Test key retrieval with non-existent reference."""
        with pytest.raises(KeyNotFoundError) as exc_info:
            key_manager.get_key("non_existent_key")
        assert "Key reference 'non_existent_key' not found" in str(exc_info.value)
    
    def test_get_key_inactive(self, key_manager):
        """Test key retrieval with inactive key."""
        api_key = "sk-test123456789"
        key_ref = key_manager.store_key("openai", api_key)
        
        # Deactivate the key
        key_manager.deactivate_key(key_ref)
        
        with pytest.raises(InvalidKeyError) as exc_info:
            key_manager.get_key(key_ref)
        assert f"Key '{key_ref}' is inactive" in str(exc_info.value)
    
    def test_delete_key_success(self, key_manager):
        """Test successful key deletion."""
        api_key = "sk-test123456789"
        key_ref = key_manager.store_key("openai", api_key)
        
        assert key_ref in key_manager._keys
        result = key_manager.delete_key(key_ref)
        
        assert result is True
        assert key_ref not in key_manager._keys
    
    def test_delete_key_not_found(self, key_manager):
        """Test key deletion with non-existent reference."""
        result = key_manager.delete_key("non_existent_key")
        assert result is False
    
    def test_list_keys(self, key_manager):
        """Test listing stored keys."""
        # Store multiple keys
        key1_ref = key_manager.store_key("openai", "sk-test1")
        key2_ref = key_manager.store_key("openrouter", "sk-or-test2")
        
        keys_list = key_manager.list_keys()
        
        assert len(keys_list) == 2
        assert key1_ref in keys_list
        assert key2_ref in keys_list
        
        # Check that actual keys are not exposed
        for key_info in keys_list.values():
            assert 'provider' in key_info
            assert 'created_at' in key_info
            assert 'usage_count' in key_info
            assert 'is_active' in key_info
            assert 'encrypted_key' not in key_info  # Should not expose encrypted key
    
    def test_deactivate_activate_key(self, key_manager):
        """Test key deactivation and activation."""
        api_key = "sk-test123456789"
        key_ref = key_manager.store_key("openai", api_key)
        
        # Test deactivation
        result = key_manager.deactivate_key(key_ref)
        assert result is True
        assert not key_manager._keys[key_ref].is_active
        
        # Test activation
        result = key_manager.activate_key(key_ref)
        assert result is True
        assert key_manager._keys[key_ref].is_active
        
        # Test with non-existent key
        assert key_manager.deactivate_key("non_existent") is False
        assert key_manager.activate_key("non_existent") is False
    
    def test_rotate_key(self, key_manager):
        """Test key rotation."""
        original_key = "sk-test123456789"
        new_key = "sk-newtest987654321"
        key_ref = key_manager.store_key("openai", original_key)
        
        # Use the key once to set usage stats
        key_manager.get_key(key_ref)
        assert key_manager._keys[key_ref].usage_count == 1
        
        # Rotate the key
        result = key_manager.rotate_key(key_ref, new_key)
        assert result is True
        
        # Verify new key works and stats were reset
        retrieved_key = key_manager.get_key(key_ref)
        assert retrieved_key == new_key
        assert key_manager._keys[key_ref].usage_count == 1  # Reset to 0, then incremented by get_key
        
        # Test with non-existent key
        assert key_manager.rotate_key("non_existent", "new_key") is False
        
        # Test with empty new key
        with pytest.raises(KeyManagerError):
            key_manager.rotate_key(key_ref, "")
    
    def test_get_usage_stats(self, key_manager):
        """Test usage statistics retrieval."""
        # Store keys for different providers
        key1_ref = key_manager.store_key("openai", "sk-test1")
        key2_ref = key_manager.store_key("openai", "sk-test2")
        key3_ref = key_manager.store_key("openrouter", "sk-or-test3")
        
        # Use some keys
        key_manager.get_key(key1_ref)
        key_manager.get_key(key1_ref)  # Use twice
        key_manager.get_key(key3_ref)
        
        # Deactivate one key
        key_manager.deactivate_key(key2_ref)
        
        # Test overall stats
        stats = key_manager.get_usage_stats()
        assert stats['total_keys'] == 3
        assert stats['active_keys'] == 2
        assert stats['inactive_keys'] == 1
        assert stats['total_usage'] == 3
        
        # Test provider-specific stats
        openai_stats = key_manager.get_usage_stats("openai")
        assert openai_stats['total_keys'] == 2
        assert openai_stats['active_keys'] == 1
        assert openai_stats['total_usage'] == 2
    
    def test_validate_key_format(self, key_manager):
        """Test API key format validation."""
        # OpenAI keys
        assert key_manager.validate_key_format("openai", "sk-1234567890abcdef1234567890abcdef")
        assert not key_manager.validate_key_format("openai", "invalid_key")
        assert not key_manager.validate_key_format("openai", "sk-short")
        
        # OpenRouter keys
        assert key_manager.validate_key_format("openrouter", "sk-or-1234567890abcdef1234567890abcdef")
        assert not key_manager.validate_key_format("openrouter", "sk-1234567890abcdef")
        
        # AWS Bedrock keys
        assert key_manager.validate_key_format("aws_bedrock", "AKIAIOSFODNN7EXAMPLE")
        assert not key_manager.validate_key_format("aws_bedrock", "short")
        
        # Generic provider
        assert key_manager.validate_key_format("custom_provider", "any_non_empty_key")
        assert not key_manager.validate_key_format("custom_provider", "")
        assert not key_manager.validate_key_format("custom_provider", "   ")
    
    def test_persistence(self, temp_storage):
        """Test key persistence across manager instances."""
        # Create first manager and store a key
        manager1 = SecureKeyManager(
            storage_path=str(temp_storage),
            master_password="test_password"
        )
        api_key = "sk-test123456789"
        key_ref = manager1.store_key("openai", api_key)
        
        # Create second manager with same storage and password
        manager2 = SecureKeyManager(
            storage_path=str(temp_storage),
            master_password="test_password"
        )
        
        # Should be able to retrieve the key
        retrieved_key = manager2.get_key(key_ref)
        assert retrieved_key == api_key
        assert len(manager2._keys) == 1
    
    def test_wrong_master_password(self, temp_storage):
        """Test that wrong master password cannot decrypt keys."""
        # Store key with first password
        manager1 = SecureKeyManager(
            storage_path=str(temp_storage),
            master_password="correct_password"
        )
        api_key = "sk-test123456789"
        key_ref = manager1.store_key("openai", api_key)
        
        # Try to access with wrong password
        manager2 = SecureKeyManager(
            storage_path=str(temp_storage),
            master_password="wrong_password"
        )
        
        # Should fail to decrypt
        with pytest.raises(InvalidKeyError):
            manager2.get_key(key_ref)
    
    def test_backup_restore(self, key_manager, temp_storage):
        """Test key backup and restore functionality."""
        # Store some keys
        key1_ref = key_manager.store_key("openai", "sk-test1")
        key2_ref = key_manager.store_key("openrouter", "sk-or-test2")
        
        # Create backup
        backup_path = temp_storage.parent / "backup_keys.json"
        key_manager.backup_keys(str(backup_path))
        assert backup_path.exists()
        
        # Delete keys and verify they're gone
        key_manager.delete_key(key1_ref)
        key_manager.delete_key(key2_ref)
        assert len(key_manager._keys) == 0
        
        # Restore from backup
        key_manager.restore_keys(str(backup_path))
        assert len(key_manager._keys) == 2
        assert key1_ref in key_manager._keys
        assert key2_ref in key_manager._keys
        
        # Verify keys still work
        assert key_manager.get_key(key1_ref) == "sk-test1"
        assert key_manager.get_key(key2_ref) == "sk-or-test2"


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_create_key_manager(self):
        """Test key manager creation utility."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "test_keys.json"
            manager = create_key_manager(
                storage_path=str(storage_path),
                master_password="test_password"
            )
            assert isinstance(manager, SecureKeyManager)
            assert manager.storage_path == storage_path
    
    def test_generate_master_key(self):
        """Test master key generation."""
        key1 = generate_master_key()
        key2 = generate_master_key()
        
        assert isinstance(key1, str)
        assert isinstance(key2, str)
        assert len(key1) > 20  # Should be reasonably long
        assert key1 != key2  # Should be unique


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.fixture
    def key_manager(self):
        """Create a key manager for error testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "test_keys.json"
            yield SecureKeyManager(
                storage_path=str(storage_path),
                master_password="test_password"
            )
    
    def test_corrupted_storage_file(self, key_manager):
        """Test handling of corrupted storage file."""
        # Store a key first
        key_ref = key_manager.store_key("openai", "sk-test123")
        
        # Corrupt the storage file
        with open(key_manager.storage_path, 'w') as f:
            f.write("{ invalid json }")
        
        # Create new manager - should handle corruption gracefully
        new_manager = SecureKeyManager(
            storage_path=str(key_manager.storage_path),
            master_password="test_password"
        )
        
        # Should start with empty key store
        assert len(new_manager._keys) == 0
    
    def test_storage_permission_error(self, key_manager):
        """Test handling of storage permission errors."""
        # Make storage directory read-only (if possible on this system)
        storage_dir = key_manager.storage_path.parent
        try:
            storage_dir.chmod(0o444)  # Read-only
            
            # Try to store a key - should raise KeyManagerError
            with pytest.raises(KeyManagerError):
                key_manager.store_key("openai", "sk-test123")
                
        except (OSError, PermissionError):
            # Skip test if we can't change permissions (e.g., on some CI systems)
            pytest.skip("Cannot test permission errors on this system")
        finally:
            # Restore permissions
            try:
                storage_dir.chmod(0o755)
            except (OSError, PermissionError):
                pass


if __name__ == "__main__":
    pytest.main([__file__])