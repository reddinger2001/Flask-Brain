"""Service scanner - detects service classes and modules."""

import ast
from pathlib import Path

from flask_brain.scanners.base import BaseScanner
from flask_brain.graph import Node, Edge, NodeType


class ServiceScanner(BaseScanner):
    """Scanner for service classes and modules."""
    
    def scan(self) -> tuple[list[Node], list[Edge]]:
        """Scan project for service classes and functions."""
        nodes = []
        edges = []
        
        for py_file in self._get_python_files():
            tree = self._parse_file(py_file)
            if tree:
                # Always scan for service classes and functions
                # (not just in files identified as service files)
                file_nodes = self._extract_services(tree, py_file)
                nodes.extend(file_nodes)
        
        return nodes, edges
    
    def _is_service_file(self, file_path: Path) -> bool:
        """Check if file is a service module by naming convention or location."""
        name = file_path.stem
        parts = file_path.parts
        
        # Check file name patterns
        if (name.endswith('_service') or 
            name.endswith('_repository') or
            name == 'service' or
            name == 'repository'):
            return True
        
        # Check if in services/ directory
        if 'services' in parts:
            return True
        
        # Check if in domain directories with service.py
        # (e.g., users/service.py, orders/service.py)
        if name in ('service', 'repository') and len(parts) > 1:
            return True
        
        return False
    
    def _extract_services(self, tree: ast.Module, file_path: Path) -> list[Node]:
        """Extract service classes and functions from AST."""
        nodes = []
        
        for node in ast.walk(tree):
            # Extract service classes
            if isinstance(node, ast.ClassDef):
                if self._is_service_class(node.name):
                    service_node = Node(
                        id=f"service::{node.name}",
                        type=NodeType.SERVICE,
                        label=node.name,
                        file_path=self._get_relative_path(file_path),
                        line_number=node.lineno,
                        metadata={
                            "methods": [m.name for m in node.body if isinstance(m, ast.FunctionDef) and not m.name.startswith('_')]
                        }
                    )
                    nodes.append(service_node)
            
            # Extract module-level service functions
            # Only extract top-level functions (not nested or class methods)
            elif isinstance(node, ast.FunctionDef):
                # Check if this is a top-level function (not inside a class)
                if self._is_top_level_function(tree, node) and self._is_service_function(node.name):
                    function_node = Node(
                        id=f"service::{node.name}",
                        type=NodeType.SERVICE,
                        label=node.name,
                        file_path=self._get_relative_path(file_path),
                        line_number=node.lineno,
                        metadata={
                            "is_function": True,
                            "methods": []  # Functions don't have methods
                        }
                    )
                    nodes.append(function_node)
        
        return nodes
    
    def _is_service_class(self, class_name: str) -> bool:
        """Check if class name suggests it's a service."""
        return (class_name.endswith('Service') or 
                class_name.endswith('Repository') or
                class_name.endswith('Manager'))
    
    def _is_service_function(self, func_name: str) -> bool:
        """Check if function name suggests it's a service function."""
        # Don't include private functions or special methods
        if func_name.startswith('_'):
            return False
        
        # Common service function prefixes
        service_prefixes = ['get_', 'create_', 'update_', 'delete_', 'list_', 'find_', 'fetch_', 'save_', 'remove_']
        return any(func_name.startswith(prefix) for prefix in service_prefixes)
    
    def _is_top_level_function(self, tree: ast.Module, func_node: ast.FunctionDef) -> bool:
        """Check if a function is defined at module level (not inside a class)."""
        # Walk through the module body to find top-level functions
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == func_node.name:
                return True
        return False
