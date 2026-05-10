"""Tests for CeleryTaskScanner."""

import pytest
from pathlib import Path

from flask_brain.scanners.celery_scanner import CeleryTaskScanner
from flask_brain.graph import NodeType


@pytest.fixture
def blueprint_app_path():
    """Path to blueprint app fixture."""
    return Path(__file__).parent / "fixtures" / "blueprint_app"


def test_celery_scanner_detects_task_decorator(blueprint_app_path):
    """Test that @celery.task decorated functions are detected."""
    scanner = CeleryTaskScanner(blueprint_app_path)
    nodes, edges = scanner.scan()
    
    # blueprint_app/tasks.py has two tasks
    task_nodes = [n for n in nodes if n.type == NodeType.TASK]
    assert len(task_nodes) >= 2
    
    task_labels = {n.label for n in task_nodes}
    assert "send_welcome_email" in task_labels
    assert "process_order_task" in task_labels


def test_celery_scanner_creates_correct_node_structure(blueprint_app_path):
    """Test that task nodes have correct structure."""
    scanner = CeleryTaskScanner(blueprint_app_path)
    nodes, edges = scanner.scan()
    
    task_nodes = [n for n in nodes if n.type == NodeType.TASK]
    assert len(task_nodes) > 0
    
    for node in task_nodes:
        assert node.id.startswith("task::")
        assert node.type == NodeType.TASK
        assert node.label
        assert node.file_path
        assert node.line_number > 0
        assert isinstance(node.metadata, dict)


def test_celery_scanner_extracts_task_names(blueprint_app_path):
    """Test that task names are extracted correctly."""
    scanner = CeleryTaskScanner(blueprint_app_path)
    nodes, edges = scanner.scan()
    
    # Find send_welcome_email task
    welcome_task = next((n for n in nodes if n.label == "send_welcome_email"), None)
    assert welcome_task is not None
    assert welcome_task.id == "task::send_welcome_email"
    
    # Find process_order_task
    order_task = next((n for n in nodes if n.label == "process_order_task"), None)
    assert order_task is not None
    assert order_task.id == "task::process_order_task"


def test_celery_scanner_detects_task_with_call_decorator(blueprint_app_path):
    """Test detection of @celery.task() with parentheses."""
    scanner = CeleryTaskScanner(blueprint_app_path)
    nodes, edges = scanner.scan()
    
    # process_order_task uses @celery.task(name='process_order')
    task_nodes = [n for n in nodes if n.type == NodeType.TASK]
    task_labels = {n.label for n in task_nodes}
    assert "process_order_task" in task_labels


def test_celery_scanner_handles_shared_task_decorator(tmp_path):
    """Test detection of @shared_task decorator (lines 56-57)."""
    # Create a file with @shared_task decorator
    tasks_file = tmp_path / "tasks.py"
    tasks_file.write_text("""
from celery import shared_task

@shared_task
def send_notification(user_id):
    return True
""")
    
    scanner = CeleryTaskScanner(tmp_path)
    nodes, edges = scanner.scan()
    
    task_nodes = [n for n in nodes if n.type == NodeType.TASK]
    assert len(task_nodes) == 1
    assert task_nodes[0].label == "send_notification"


def test_celery_scanner_handles_shared_task_with_call(tmp_path):
    """Test detection of @shared_task() with parentheses (lines 63-65)."""
    # Create a file with @shared_task() decorator
    tasks_file = tmp_path / "tasks.py"
    tasks_file.write_text("""
from celery import shared_task

@shared_task(name='custom_task')
def process_data(data_id):
    return True
""")
    
    scanner = CeleryTaskScanner(tmp_path)
    nodes, edges = scanner.scan()
    
    task_nodes = [n for n in nodes if n.type == NodeType.TASK]
    assert len(task_nodes) == 1
    assert task_nodes[0].label == "process_data"


def test_celery_scanner_handles_app_task_decorator():
    """Test detection of @app.task decorator."""
    # This is a documentation test - we don't have a fixture with @app.task yet
    # But the scanner should support this pattern
    pass


def test_celery_scanner_returns_no_edges(blueprint_app_path):
    """Test that scanner returns empty edges list."""
    scanner = CeleryTaskScanner(blueprint_app_path)
    nodes, edges = scanner.scan()
    
    # CeleryTaskScanner doesn't create edges
    assert edges == []


def test_celery_scanner_handles_no_tasks():
    """Test scanner handles projects with no Celery tasks."""
    # flat_app and factory_app don't have tasks
    flat_app_path = Path(__file__).parent / "fixtures" / "flat_app"
    scanner = CeleryTaskScanner(flat_app_path)
    nodes, edges = scanner.scan()
    
    task_nodes = [n for n in nodes if n.type == NodeType.TASK]
    assert len(task_nodes) == 0


def test_celery_scanner_file_paths_are_relative(blueprint_app_path):
    """Test that file paths in nodes are relative to project root."""
    scanner = CeleryTaskScanner(blueprint_app_path)
    nodes, edges = scanner.scan()
    
    task_nodes = [n for n in nodes if n.type == NodeType.TASK]
    for node in task_nodes:
        # File paths should be relative, not absolute
        assert not node.file_path.startswith('/')
        assert 'tasks.py' in node.file_path
