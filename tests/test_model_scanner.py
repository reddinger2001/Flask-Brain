"""Tests for ModelScanner."""

import pytest
from pathlib import Path
from flask_brain.scanners.model_scanner import ModelScanner
from flask_brain.graph import NodeType, EdgeType


@pytest.fixture
def flat_app_path():
    """Path to flat_app fixture."""
    return Path(__file__).parent / "fixtures" / "flat_app"


@pytest.fixture
def factory_app_path():
    """Path to factory_app fixture."""
    return Path(__file__).parent / "fixtures" / "factory_app"


@pytest.fixture
def blueprint_app_path():
    """Path to blueprint_app fixture."""
    return Path(__file__).parent / "fixtures" / "blueprint_app"


def test_model_scanner_flat_app(flat_app_path):
    """Test ModelScanner on flat app."""
    scanner = ModelScanner(flat_app_path)
    nodes, edges = scanner.scan()
    
    # Should find User model
    model_nodes = [n for n in nodes if n.type == NodeType.MODEL]
    assert len(model_nodes) == 1
    assert model_nodes[0].id == "model::User"
    assert model_nodes[0].label == "User"
    
    # Check columns
    user_model = model_nodes[0]
    assert "columns" in user_model.metadata
    columns = user_model.metadata["columns"]
    assert "id" in columns
    assert "name" in columns
    assert "email" in columns


def test_model_scanner_factory_app(factory_app_path):
    """Test ModelScanner on factory app."""
    scanner = ModelScanner(factory_app_path)
    nodes, edges = scanner.scan()
    
    # Should find User model
    model_nodes = [n for n in nodes if n.type == NodeType.MODEL]
    assert len(model_nodes) == 1
    assert model_nodes[0].id == "model::User"


def test_model_scanner_blueprint_app(blueprint_app_path):
    """Test ModelScanner on blueprint app with relationships."""
    scanner = ModelScanner(blueprint_app_path)
    nodes, edges = scanner.scan()
    
    # Should find User and Order models
    model_nodes = [n for n in nodes if n.type == NodeType.MODEL]
    assert len(model_nodes) == 2
    
    model_ids = {n.id for n in model_nodes}
    assert "model::User" in model_ids
    assert "model::Order" in model_ids
    
    # Should find relationship edges
    relationship_edges = [e for e in edges if e.type == EdgeType.HAS_RELATIONSHIP]
    assert len(relationship_edges) >= 1
    
    # Check User -> Order relationship
    user_order_edges = [e for e in relationship_edges if e.source == "model::User" and e.target == "model::Order"]
    assert len(user_order_edges) >= 1


def test_model_scanner_extracts_columns(flat_app_path):
    """Test that scanner extracts column information."""
    scanner = ModelScanner(flat_app_path)
    nodes, edges = scanner.scan()
    
    user_model = next(n for n in nodes if n.id == "model::User")
    columns = user_model.metadata["columns"]
    
    # Should have column details
    assert isinstance(columns, dict)
    assert len(columns) >= 3
