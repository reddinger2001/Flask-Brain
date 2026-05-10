"""Tests for property scanner."""

import pytest
from pathlib import Path
from flask_brain.scanners.property_scanner import PropertyScanner
from flask_brain.graph import NodeType, EdgeType


@pytest.fixture
def property_app_path():
    """Path to property test fixture."""
    return Path(__file__).parent / "fixtures" / "property_app"


def test_detects_property_getter(property_app_path):
    """Test that @property getter is detected."""
    scanner = PropertyScanner(property_app_path)
    nodes, edges = scanner.scan()
    
    # Find portal_link property node
    portal_link_node = next(
        (n for n in nodes if n.label == "portal_link" and n.metadata["class_name"] == "Contract"),
        None
    )
    assert portal_link_node is not None
    assert portal_link_node.metadata["has_getter"] is True
    assert portal_link_node.metadata["has_setter"] is False
    assert any(d["kind"] == "getter" for d in portal_link_node.metadata["definitions"])


def test_detects_property_setter(property_app_path):
    """Test that @x.setter is detected."""
    scanner = PropertyScanner(property_app_path)
    nodes, edges = scanner.scan()
    
    # Find full_status property node
    full_status_node = next(
        (n for n in nodes if n.label == "full_status" and n.metadata["class_name"] == "Contract"),
        None
    )
    assert full_status_node is not None
    assert full_status_node.metadata["has_getter"] is True
    assert full_status_node.metadata["has_setter"] is True
    assert any(d["kind"] == "getter" for d in full_status_node.metadata["definitions"])
    assert any(d["kind"] == "setter" for d in full_status_node.metadata["definitions"])


def test_detects_class_var(property_app_path):
    """Test that class-level variables are detected."""
    scanner = PropertyScanner(property_app_path)
    nodes, edges = scanner.scan()
    
    # Find portal_link_id class var
    portal_link_id_node = next(
        (n for n in nodes if n.label == "portal_link_id" and n.metadata["class_name"] == "Contract"),
        None
    )
    assert portal_link_id_node is not None
    assert portal_link_id_node.metadata["is_class_var"] is True
    assert any(d["kind"] == "class_var" for d in portal_link_id_node.metadata["definitions"])


def test_detects_instance_var(property_app_path):
    """Test that self.x = ... in __init__ is detected."""
    scanner = PropertyScanner(property_app_path)
    nodes, edges = scanner.scan()
    
    # Find created_at instance var
    created_at_node = next(
        (n for n in nodes if n.label == "created_at" and n.metadata["class_name"] == "Contract"),
        None
    )
    assert created_at_node is not None
    assert created_at_node.metadata["is_instance_var"] is True
    assert any(d["kind"] == "instance_var" for d in created_at_node.metadata["definitions"])


def test_detects_property_read(property_app_path):
    """Test that self.x read in a method is detected."""
    scanner = PropertyScanner(property_app_path)
    nodes, edges = scanner.scan()
    
    # Find status property node
    status_node = next(
        (n for n in nodes if n.label == "status" and n.metadata["class_name"] == "Contract"),
        None
    )
    assert status_node is not None
    # Should have reads from process() method
    assert len(status_node.metadata["reads"]) > 0
    assert any("process" in r["context"] for r in status_node.metadata["reads"])


def test_detects_property_write(property_app_path):
    """Test that self.x = ... outside __init__ is detected."""
    scanner = PropertyScanner(property_app_path)
    nodes, edges = scanner.scan()
    
    # Find status property node
    status_node = next(
        (n for n in nodes if n.label == "status" and n.metadata["class_name"] == "Contract"),
        None
    )
    assert status_node is not None
    # Should have writes from update_status() method
    assert len(status_node.metadata["writes"]) > 0
    assert any("update_status" in w["context"] for w in status_node.metadata["writes"])


def test_flags_orphaned_getter(property_app_path):
    """Test that orphaned getter (no setter) is flagged."""
    scanner = PropertyScanner(property_app_path)
    nodes, edges = scanner.scan()
    
    # portal_link has getter but no setter
    portal_link_node = next(
        (n for n in nodes if n.label == "portal_link" and n.metadata["class_name"] == "Contract"),
        None
    )
    assert portal_link_node is not None
    assert portal_link_node.metadata["orphaned_getter"] is True
    assert portal_link_node.metadata["orphaned_setter"] is False


def test_no_orphaned_when_both_present(property_app_path):
    """Test that no orphan flag when both getter and setter present."""
    scanner = PropertyScanner(property_app_path)
    nodes, edges = scanner.scan()
    
    # full_status has both getter and setter
    full_status_node = next(
        (n for n in nodes if n.label == "full_status" and n.metadata["class_name"] == "Contract"),
        None
    )
    assert full_status_node is not None
    assert full_status_node.metadata["orphaned_getter"] is False
    assert full_status_node.metadata["orphaned_setter"] is False


def test_creates_reads_property_edges(property_app_path):
    """Test that reads_property edges are created correctly."""
    scanner = PropertyScanner(property_app_path)
    nodes, edges = scanner.scan()
    
    # Should have reads_property edges
    reads_edges = [e for e in edges if e.type == "reads_property"]
    assert len(reads_edges) > 0


def test_creates_writes_property_edges(property_app_path):
    """Test that writes_property edges are created correctly."""
    scanner = PropertyScanner(property_app_path)
    nodes, edges = scanner.scan()
    
    # Should have writes_property edges
    writes_edges = [e for e in edges if e.type == "writes_property"]
    assert len(writes_edges) > 0


def test_records_parent_file_and_class(property_app_path):
    """Test that parent file and class are recorded correctly."""
    scanner = PropertyScanner(property_app_path)
    nodes, edges = scanner.scan()
    
    # Check that definitions have file and class info
    portal_link_node = next(
        (n for n in nodes if n.label == "portal_link" and n.metadata["class_name"] == "Contract"),
        None
    )
    assert portal_link_node is not None
    for defn in portal_link_node.metadata["definitions"]:
        assert "file" in defn
        assert "class" in defn
        assert "line" in defn
        assert defn["class"] == "Contract"
