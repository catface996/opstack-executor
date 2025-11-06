"""Test package structure and basic imports."""

import pytest


def test_package_import():
    """Test that the package can be imported successfully."""
    import hierarchical_agents
    
    assert hierarchical_agents.__version__ == "0.1.0"
    assert hierarchical_agents.__author__ == "Hierarchical Agents Team"


def test_package_structure():
    """Test that the package structure is correct."""
    import hierarchical_agents
    import os
    
    # Check that the package has the expected structure
    package_path = os.path.dirname(hierarchical_agents.__file__)
    
    # Check that __init__.py exists
    assert os.path.exists(os.path.join(package_path, "__init__.py"))
    
    # Check that data_models.py exists (even if empty)
    assert os.path.exists(os.path.join(package_path, "data_models.py"))


def test_core_dependencies():
    """Test that core dependencies can be imported."""
    import langgraph
    import langchain
    import fastapi
    import pydantic
    
    # If we get here without ImportError, the dependencies are available
    assert True