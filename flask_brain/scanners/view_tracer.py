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
        self.imports: dict[str, dict[str, str]] = {}  # file_path -> {name: module}
    
    def scan(self) -> tuple[list[Node], list[Edge]]:
        """Scan project for view functions and their call chains."""
        nodes = []
        edges = []
        
        # First pass: identify view functions and collect imports
        for py_file in self._get_python_files():
            tree = self._parse_file(py_file)
            if tree:
                self._collect_imports(tree, py_file)
                self._identify_view_functions(tree, py_file)
        
        # Second pass: trace calls from view functions
        for py_file in self._get_python_files():
            tree = self._parse_file(py_file)
            if tree:
                file_nodes, file_edges = self._trace_view_calls(tree, py_file)
                nodes.extend(file_nodes)
                edges.extend(file_edges)
        
        return nodes, edges
    
    def _collect_imports(self, tree: ast.Module, file_path: Path) -> None:
        """Collect import statements from a file."""
        if str(file_path) not in self.imports:
            self.imports[str(file_path)] = {}
        
        for node in ast.walk(tree):
            # from module import Name
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    self.imports[str(file_path)][name] = f"{module}.{alias.name}" if module else alias.name
            
            # import module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    self.imports[str(file_path)][name] = alias.name
    
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
                            targets = self._identify_call_targets(call_node, file_path)
                            for target, edge_type in targets:
                                edge = Edge(
                                    source=f"action::{node.name}",
                                    target=target,
                                    type=edge_type
                                )
                                edges.append(edge)
        
        return nodes, edges
    
    def _identify_call_targets(self, call_node: ast.Call, file_path: Path) -> list[tuple[str, EdgeType]]:
        """Identify the targets of a function call."""
        targets = []
        
        # Method call: obj.method()
        if isinstance(call_node.func, ast.Attribute):
            attr_name = call_node.func.attr
            
            # Check if it's a method call on an object
            if isinstance(call_node.func.value, ast.Name):
                obj_name = call_node.func.value.id
                
                # Check if object is an imported service
                file_imports = self.imports.get(str(file_path), {})
                if obj_name in file_imports:
                    imported_module = file_imports[obj_name]
                    # If imported from a service module, create service edge
                    if "service" in imported_module.lower() or "Service" in imported_module:
                        targets.append((f"service::{imported_module}.{attr_name}", EdgeType.CALLS))
                    else:
                        # Generic call
                        targets.append((f"service::{imported_module}.{attr_name}", EdgeType.CALLS))
                
                # Check if it's a service instance (by naming convention)
                elif "service" in obj_name.lower() or "repo" in obj_name.lower():
                    targets.append((f"service::{obj_name}.{attr_name}", EdgeType.CALLS))
                
                # Check if it's a model query
                elif attr_name in ("query", "filter", "filter_by", "all", "get", "first", "one"):
                    targets.append((f"model::{obj_name}", EdgeType.USES_MODEL))
                
                # Check if it's a task dispatch
                elif attr_name in ("delay", "apply_async"):
                    targets.append((f"task::{obj_name}", EdgeType.DISPATCHES_TASK))
            
            # Check for db.session.* calls
            elif isinstance(call_node.func.value, ast.Attribute):
                if isinstance(call_node.func.value.value, ast.Name):
                    obj_name = call_node.func.value.value.id
                    middle_attr = call_node.func.value.attr
                    
                    # db.session.add(), db.session.query(), etc.
                    if obj_name == "db" and middle_attr == "session":
                        if attr_name in ("query", "execute"):
                            # Try to extract model from arguments
                            if call_node.args and isinstance(call_node.args[0], ast.Name):
                                model_name = call_node.args[0].id
                                targets.append((f"model::{model_name}", EdgeType.USES_MODEL))
        
        # Direct function call
        elif isinstance(call_node.func, ast.Name):
            func_name = call_node.func.id
            
            # Check if it's an imported function
            file_imports = self.imports.get(str(file_path), {})
            if func_name in file_imports:
                imported_module = file_imports[func_name]
                targets.append((f"service::{func_name}", EdgeType.CALLS))
            
            # Check if it's a service function by naming convention
            elif any(keyword in func_name.lower() for keyword in ["get_", "create_", "update_", "delete_", "list_", "find_"]):
                targets.append((f"service::{func_name}", EdgeType.CALLS))
        
        return targets
    
    def _classify_edge_type(self, target: str) -> EdgeType:
        """Classify edge type based on target."""
        if target.startswith("service::"):
            return EdgeType.CALLS
        elif target.startswith("model::"):
            return EdgeType.USES_MODEL
        elif target.startswith("task::"):
            return EdgeType.DISPATCHES_TASK
        return EdgeType.CALLS
