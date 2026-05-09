"""View function tracer - traces call chains from view functions."""

import ast
from pathlib import Path
from typing import Any

from flask_brain.scanners.base import BaseScanner
from flask_brain.graph import Node, Edge, NodeType, EdgeType


class ViewFunctionTracer(BaseScanner):
    """Tracer for view function call chains."""
    
    def __init__(self, project_path: Path):
        super().__init__(project_path)
        self.view_functions: dict[str, dict[str, Any]] = {}
    
    def scan(self) -> tuple[list[Node], list[Edge]]:
        """Scan project for view functions and their call chains."""
        nodes = []
        edges = []
        
        # First pass: identify view functions (functions with route decorators)
        for py_file in self._get_python_files():
            tree = self._parse_file(py_file)
            if tree:
                self._identify_view_functions(tree, py_file)
        
        # Second pass: trace calls from view functions
        for py_file in self._get_python_files():
            tree = self._parse_file(py_file)
            if tree:
                file_nodes, file_edges = self._trace_view_calls(tree, py_file)
                nodes.extend(file_nodes)
                edges.extend(file_edges)
        
        return nodes, edges
    
    def _identify_view_functions(self, tree: ast.Module, file_path: Path) -> None:
        """Identify view functions by their route decorators."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check if function has route decorator
                for decorator in node.decorator_list:
                    if self._has_route_decorator(decorator):
                        self.view_functions[node.name] = {
                            "file_path": file_path,
                            "line_number": node.lineno,
                            "node": node
                        }
                        break
    
    def _has_route_decorator(self, decorator: ast.expr) -> bool:
        """Check if decorator is a route decorator."""
        if isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Attribute):
                if decorator.func.attr == "route":
                    return True
        return False
    
    def _trace_view_calls(self, tree: ast.Module, file_path: Path) -> tuple[list[Node], list[Edge]]:
        """Trace calls from view functions."""
        nodes = []
        edges = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name in self.view_functions:
                    # Create action node for this view function
                    action_node = Node(
                        id=f"action::{node.name}",
                        type=NodeType.ACTION,
                        label=node.name,
                        file_path=self._get_relative_path(file_path),
                        line_number=node.lineno,
                        metadata={}
                    )
                    nodes.append(action_node)
                    
                    # Trace calls within the function
                    for call_node in ast.walk(node):
                        if isinstance(call_node, ast.Call):
                            target = self._identify_call_target(call_node)
                            if target:
                                edge = Edge(
                                    source=f"action::{node.name}",
                                    target=target,
                                    type=self._classify_edge_type(target)
                                )
                                edges.append(edge)
        
        return nodes, edges
    
    def _identify_call_target(self, call_node: ast.Call) -> str | None:
        """Identify the target of a function call."""
        # Method call: obj.method()
        if isinstance(call_node.func, ast.Attribute):
            attr_name = call_node.func.attr
            
            # Check if it's a service method
            if isinstance(call_node.func.value, ast.Name):
                obj_name = call_node.func.value.id
                if "service" in obj_name.lower() or "repo" in obj_name.lower():
                    # Assume it's calling a service
                    return f"service::{obj_name}"
            
            # Check if it's a model query
            if attr_name in ("query", "filter", "filter_by", "all", "get"):
                if isinstance(call_node.func.value, ast.Name):
                    model_name = call_node.func.value.id
                    return f"model::{model_name}"
            
            # Check if it's a task dispatch
            if attr_name in ("delay", "apply_async"):
                if isinstance(call_node.func.value, ast.Name):
                    task_name = call_node.func.value.id
                    return f"task::{task_name}"
        
        # Direct function call
        elif isinstance(call_node.func, ast.Name):
            func_name = call_node.func.id
            # Check if it's a service function
            if "service" in func_name.lower():
                return f"service::{func_name}"
        
        return None
    
    def _classify_edge_type(self, target: str) -> EdgeType:
        """Classify edge type based on target."""
        if target.startswith("service::"):
            return EdgeType.CALLS
        elif target.startswith("model::"):
            return EdgeType.USES_MODEL
        elif target.startswith("task::"):
            return EdgeType.DISPATCHES_TASK
        return EdgeType.CALLS
