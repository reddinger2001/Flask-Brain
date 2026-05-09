"""Service scanner - detects service classes and modules."""

import ast
from pathlib import Path

from flask_brain.scanners.base import BaseScanner
from flask_brain.graph import Node, Edge, NodeType


class ServiceScanner(BaseScanner):
    """Scanner for service classes and modules."""
    
    def scan(self) -> tuple[list[Node], list[Edge]]:
        """Scan project for service classes."""
        nodes = []
        edges = []
        
        for py_file in self._get_python_files():
            # Check if file is a service module by name
            if self._is_service_file(py_file):
                tree = self._parse_file(py_file)
                if tree:
                    file_nodes = self._extract_services(tree, py_file)
                    nodes.extend(file_nodes)
        
        return nodes, edges
    
    def _is_service_file(self, file_path: Path) -> bool:
        """Check if file is a service module by naming convention."""
        name = file_path.stem
        return (name.endswith('_service') or 
                name.endswith('_repository') or
                'service' in file_path.parts)
    
    def _extract_services(self, tree: ast.Module, file_path: Path) -> list[Node]:
        """Extract service classes from AST."""
        nodes = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if class name suggests it's a service
                if self._is_service_class(node.name):
                    service_node = Node(
                        id=f"service::{node.name}",
                        type=NodeType.SERVICE,
                        label=node.name,
                        file_path=self._get_relative_path(file_path),
                        line_number=node.lineno,
                        metadata={
                            "methods": [m.name for m in node.body if isinstance(m, ast.FunctionDef)]
                        }
                    )
                    nodes.append(service_node)
        
        return nodes
    
    def _is_service_class(self, class_name: str) -> bool:
        """Check if class name suggests it's a service."""
        return (class_name.endswith('Service') or 
                class_name.endswith('Repository') or
                class_name.endswith('Manager'))
