"""Celery task scanner - detects Celery tasks."""

import ast
from pathlib import Path

from flask_brain.scanners.base import BaseScanner
from flask_brain.graph import Node, Edge, NodeType


class CeleryTaskScanner(BaseScanner):
    """Scanner for Celery tasks."""
    
    def scan(self) -> tuple[list[Node], list[Edge]]:
        """Scan project for Celery tasks."""
        nodes = []
        edges = []
        
        for py_file in self._get_python_files():
            tree = self._parse_file(py_file)
            if tree:
                file_nodes = self._extract_tasks(tree, py_file)
                nodes.extend(file_nodes)
        
        return nodes, edges
    
    def _extract_tasks(self, tree: ast.Module, file_path: Path) -> list[Node]:
        """Extract Celery task functions from AST."""
        nodes = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check decorators for @celery.task, @shared_task, @app.task
                for decorator in node.decorator_list:
                    if self._is_task_decorator(decorator):
                        task_node = Node(
                            id=f"task::{node.name}",
                            type=NodeType.TASK,
                            label=node.name,
                            file_path=self._get_relative_path(file_path),
                            line_number=node.lineno,
                            metadata={}
                        )
                        nodes.append(task_node)
                        break
        
        return nodes
    
    def _is_task_decorator(self, decorator: ast.expr) -> bool:
        """Check if decorator is a Celery task decorator."""
        # @celery.task or @app.task
        if isinstance(decorator, ast.Attribute):
            if decorator.attr == "task":
                return True
        # @shared_task
        elif isinstance(decorator, ast.Name):
            if decorator.id == "shared_task":
                return True
        # @celery.task() or @shared_task()
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Attribute):
                if decorator.func.attr == "task":
                    return True
            elif isinstance(decorator.func, ast.Name):
                if decorator.func.id == "shared_task":
                    return True
        return False
