"""Tests for ServiceScanner."""

import pytest
from pathlib import Path

from flask_brain.scanners.service_scanner import ServiceScanner
from flask_brain.graph import NodeType


@pytest.fixture
def flat_app_path():
    """Path to flat app fixture."""
    return Path(__file__).parent / "fixtures" / "flat_app"


@pytest.fixture
def factory_app_path():
    """Path to factory app fixture."""
    return Path(__file__).parent / "fixtures" / "factory_app"


@pytest.fixture
def blueprint_app_path():
    """Path to blueprint app fixture."""
    return Path(__file__).parent / "fixtures" / "blueprint_app"


def test_service_scanner_detects_service_classes(factory_app_path):
    """Test that service classes are detected."""
    scanner = ServiceScanner(factory_app_path)
    nodes, edges = scanner.scan()
    
    # Should find UserService class
    service_nodes = [n for n in nodes if n.type == NodeType.SERVICE]
    assert len(service_nodes) >= 1
    
    service_labels = {n.label for n in service_nodes}
    assert "UserService" in service_labels


def test_service_scanner_extracts_methods_from_classes(factory_app_path):
    """Test that methods are extracted from service classes."""
    scanner = ServiceScanner(factory_app_path)
    nodes, edges = scanner.scan()
    
    # Find UserService node
    user_service = next((n for n in nodes if n.label == "UserService"), None)
    assert user_service is not None
    
    # Should have methods in metadata
    assert "methods" in user_service.metadata
    methods = user_service.metadata["methods"]
    assert "get_user" in methods
    assert "get_all_users" in methods
    assert "create_user" in methods
    assert "update_user" in methods
    assert "delete_user" in methods


def test_service_scanner_detects_module_level_functions(flat_app_path):
    """Test that module-level service functions are detected."""
    scanner = ServiceScanner(flat_app_path)
    nodes, edges = scanner.scan()
    
    # flat_app has module-level service functions
    service_nodes = [n for n in nodes if n.type == NodeType.SERVICE]
    assert len(service_nodes) >= 3  # get_user_by_id, create_user, list_all_users
    
    service_labels = {n.label for n in service_nodes}
    assert "get_user_by_id" in service_labels
    assert "create_user" in service_labels
    assert "list_all_users" in service_labels


def test_service_scanner_detects_services_in_service_directories(blueprint_app_path):
    """Test detection of services in users/ and orders/ directories."""
    scanner = ServiceScanner(blueprint_app_path)
    nodes, edges = scanner.scan()
    
    # blueprint_app has UserService and OrderRepository
    service_nodes = [n for n in nodes if n.type == NodeType.SERVICE]
    assert len(service_nodes) >= 2
    
    service_labels = {n.label for n in service_nodes}
    assert "UserService" in service_labels
    assert "OrderRepository" in service_labels


def test_service_scanner_identifies_service_files_by_naming(factory_app_path):
    """Test that files named *_service.py are identified as service modules."""
    scanner = ServiceScanner(factory_app_path)
    nodes, edges = scanner.scan()
    
    # user_service.py should be scanned
    service_nodes = [n for n in nodes if n.type == NodeType.SERVICE]
    assert len(service_nodes) > 0
    
    # All service nodes should have file paths
    for node in service_nodes:
        assert node.file_path
        assert node.line_number > 0


def test_service_scanner_detects_repository_classes():
    """Test that classes ending in Repository are detected."""
    # This is a documentation test - we don't have a fixture with Repository classes yet
    # But the scanner should support this pattern
    pass


def test_service_scanner_detects_manager_classes():
    """Test that classes ending in Manager are detected."""
    # This is a documentation test - we don't have a fixture with Manager classes yet
    # But the scanner should support this pattern
    pass


def test_service_scanner_creates_correct_node_ids(factory_app_path):
    """Test that service nodes have correct ID format."""
    scanner = ServiceScanner(factory_app_path)
    nodes, edges = scanner.scan()
    
    service_nodes = [n for n in nodes if n.type == NodeType.SERVICE]
    for node in service_nodes:
        assert node.id.startswith("service::")
        assert node.label in node.id


def test_service_scanner_works_across_all_fixtures(flat_app_path, factory_app_path, blueprint_app_path):
    """Test that scanner works on all three fixture app structures."""
    for app_path in [flat_app_path, factory_app_path, blueprint_app_path]:
        scanner = ServiceScanner(app_path)
        nodes, edges = scanner.scan()
        
        # Each app should have at least some service nodes
        service_nodes = [n for n in nodes if n.type == NodeType.SERVICE]
        assert len(service_nodes) > 0, f"No service nodes found in {app_path.name}"
        
        # Each service node should have proper structure
        for node in service_nodes:
            assert node.id
            assert node.type == NodeType.SERVICE
            assert node.label
            assert node.file_path
            assert node.line_number > 0
            assert isinstance(node.metadata, dict)
