"""Property scanner - detects property definitions and usages across Python files."""

import ast
from pathlib import Path
from typing import Any

from flask_brain.scanners.base import BaseScanner
from flask_brain.graph import Node, Edge, NodeType, EdgeType


class PropertyScanner(BaseScanner):
    """Scanner for Python properties, class vars, and instance vars."""

    def scan(self) -> tuple[list[Node], list[Edge]]:
        """Scan project for property definitions and usages."""
        # Property registry: key = "ClassName.prop_name", value = property info dict
        properties: dict[str, dict[str, Any]] = {}
        
        # Pass 1: collect all property definitions
        for py_file in self._get_python_files():
            tree = self._parse_file(py_file)
            if tree:
                self._collect_properties(tree, py_file, properties)
        
        # Pass 2: collect all property usages (reads/writes)
        for py_file in self._get_python_files():
            tree = self._parse_file(py_file)
            if tree:
                self._collect_usages(tree, py_file, properties)
        
        # Build nodes and edges
        nodes = []
        edges = []
        
        for prop_key, prop_info in properties.items():
            # Create property node
            node = Node(
                id=f"property::{prop_key}",
                type=NodeType.PROPERTY,  # Will need to add to NodeType enum
                label=prop_info["prop_name"],
                file_path=prop_info["file_path"],
                line_number=prop_info.get("first_line", 1),
                metadata={
                    "class_name": prop_info["class_name"],
                    "prop_name": prop_info["prop_name"],
                    "has_getter": prop_info["has_getter"],
                    "has_setter": prop_info["has_setter"],
                    "has_deleter": prop_info["has_deleter"],
                    "is_class_var": prop_info["is_class_var"],
                    "is_instance_var": prop_info["is_instance_var"],
                    "definitions": prop_info["definitions"],
                    "reads": prop_info["reads"],
                    "writes": prop_info["writes"],
                    "orphaned_getter": prop_info["has_getter"] and not prop_info["has_setter"],
                    "orphaned_setter": prop_info["has_setter"] and not prop_info["has_getter"],
                }
            )
            nodes.append(node)
            
            # Create edges for definitions
            for defn in prop_info["definitions"]:
                if defn.get("parent_node_id"):
                    edge = Edge(
                        source=defn["parent_node_id"],
                        target=f"property::{prop_key}",
                        type=EdgeType.DEFINES_PROPERTY,  # Will need to add to EdgeType enum
                        metadata={"kind": defn["kind"]}
                    )
                    edges.append(edge)
            
            # Create edges for reads
            for read in prop_info["reads"]:
                if read.get("parent_node_id"):
                    edge = Edge(
                        source=read["parent_node_id"],
                        target=f"property::{prop_key}",
                        type=EdgeType.READS_PROPERTY,  # Will need to add to EdgeType enum
                        metadata={}
                    )
                    edges.append(edge)
            
            # Create edges for writes
            for write in prop_info["writes"]:
                if write.get("parent_node_id"):
                    edge = Edge(
                        source=write["parent_node_id"],
                        target=f"property::{prop_key}",
                        type=EdgeType.WRITES_PROPERTY,  # Will need to add to EdgeType enum
                        metadata={}
                    )
                    edges.append(edge)
        
        return nodes, edges
    
    def _collect_properties(
        self,
        tree: ast.Module,
        file_path: Path,
        properties: dict[str, dict[str, Any]]
    ) -> None:
        """Collect property definitions from a file."""
        rel_path = self._get_relative_path(file_path)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_name = node.name
                
                # Scan class body for properties
                for item in node.body:
                    # @property getter
                    if isinstance(item, ast.FunctionDef):
                        for decorator in item.decorator_list:
                            # @property
                            if isinstance(decorator, ast.Name) and decorator.id == "property":
                                prop_key = f"{class_name}.{item.name}"
                                if prop_key not in properties:
                                    properties[prop_key] = self._init_property(
                                        class_name, item.name, rel_path, item.lineno
                                    )
                                properties[prop_key]["has_getter"] = True
                                properties[prop_key]["definitions"].append({
                                    "kind": "getter",
                                    "file": rel_path,
                                    "line": item.lineno,
                                    "class": class_name,
                                    "parent_node_id": f"action::{item.name}",  # Best effort
                                })
                            
                            # @prop_name.setter
                            elif isinstance(decorator, ast.Attribute) and decorator.attr == "setter":
                                if isinstance(decorator.value, ast.Name):
                                    prop_name = decorator.value.id
                                    prop_key = f"{class_name}.{prop_name}"
                                    if prop_key not in properties:
                                        properties[prop_key] = self._init_property(
                                            class_name, prop_name, rel_path, item.lineno
                                        )
                                    properties[prop_key]["has_setter"] = True
                                    properties[prop_key]["definitions"].append({
                                        "kind": "setter",
                                        "file": rel_path,
                                        "line": item.lineno,
                                        "class": class_name,
                                        "parent_node_id": f"action::{item.name}",
                                    })
                            
                            # @prop_name.deleter
                            elif isinstance(decorator, ast.Attribute) and decorator.attr == "deleter":
                                if isinstance(decorator.value, ast.Name):
                                    prop_name = decorator.value.id
                                    prop_key = f"{class_name}.{prop_name}"
                                    if prop_key not in properties:
                                        properties[prop_key] = self._init_property(
                                            class_name, prop_name, rel_path, item.lineno
                                        )
                                    properties[prop_key]["has_deleter"] = True
                                    properties[prop_key]["definitions"].append({
                                        "kind": "deleter",
                                        "file": rel_path,
                                        "line": item.lineno,
                                        "class": class_name,
                                        "parent_node_id": f"action::{item.name}",
                                    })
                    
                    # Class-level variable: x = db.Column(...) or x = None
                    elif isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                prop_name = target.id
                                prop_key = f"{class_name}.{prop_name}"
                                if prop_key not in properties:
                                    properties[prop_key] = self._init_property(
                                        class_name, prop_name, rel_path, item.lineno
                                    )
                                properties[prop_key]["is_class_var"] = True
                                properties[prop_key]["definitions"].append({
                                    "kind": "class_var",
                                    "file": rel_path,
                                    "line": item.lineno,
                                    "class": class_name,
                                    "parent_node_id": f"model::{class_name}",  # Assume model
                                })
                    
                    # Annotated assignment: x: int = 5
                    elif isinstance(item, ast.AnnAssign):
                        if isinstance(item.target, ast.Name) and item.value is not None:
                            prop_name = item.target.id
                            prop_key = f"{class_name}.{prop_name}"
                            if prop_key not in properties:
                                properties[prop_key] = self._init_property(
                                    class_name, prop_name, rel_path, item.lineno
                                )
                            properties[prop_key]["is_class_var"] = True
                            properties[prop_key]["definitions"].append({
                                "kind": "class_var",
                                "file": rel_path,
                                "line": item.lineno,
                                "class": class_name,
                                "parent_node_id": f"model::{class_name}",
                            })
                
                # Scan __init__ for instance vars
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                        for stmt in ast.walk(item):
                            if isinstance(stmt, ast.Assign):
                                for target in stmt.targets:
                                    # self.x = ...
                                    if isinstance(target, ast.Attribute):
                                        if isinstance(target.value, ast.Name) and target.value.id == "self":
                                            prop_name = target.attr
                                            prop_key = f"{class_name}.{prop_name}"
                                            if prop_key not in properties:
                                                properties[prop_key] = self._init_property(
                                                    class_name, prop_name, rel_path, stmt.lineno
                                                )
                                            properties[prop_key]["is_instance_var"] = True
                                            properties[prop_key]["definitions"].append({
                                                "kind": "instance_var",
                                                "file": rel_path,
                                                "line": stmt.lineno,
                                                "class": class_name,
                                                "parent_node_id": f"model::{class_name}",
                                            })
    
    def _collect_usages(
        self,
        tree: ast.Module,
        file_path: Path,
        properties: dict[str, dict[str, Any]]
    ) -> None:
        """Collect property reads and writes from a file."""
        rel_path = self._get_relative_path(file_path)
        
        # Track current context (class, function)
        class ContextVisitor(ast.NodeVisitor):
            def __init__(self, scanner, rel_path, properties):
                self.scanner = scanner
                self.rel_path = rel_path
                self.properties = properties
                self.current_class = None
                self.current_function = None
            
            def visit_ClassDef(self, node):
                old_class = self.current_class
                self.current_class = node.name
                self.generic_visit(node)
                self.current_class = old_class
            
            def visit_FunctionDef(self, node):
                old_function = self.current_function
                self.current_function = node.name
                self.generic_visit(node)
                self.current_function = old_function
            
            def visit_Attribute(self, node):
                # self.x or obj.x
                attr_name = node.attr
                
                # Determine if this is a read or write
                is_write = False
                parent = getattr(node, '_parent', None)
                if isinstance(parent, ast.Assign):
                    # Check if node is a target
                    for target in parent.targets:
                        if target is node:
                            is_write = True
                            break
                elif isinstance(parent, ast.AugAssign) and parent.target is node:
                    is_write = True
                
                # self.x
                if isinstance(node.value, ast.Name) and node.value.id == "self":
                    if self.current_class:
                        prop_key = f"{self.current_class}.{attr_name}"
                        if prop_key in self.properties:
                            context = f"{self.current_class}.{self.current_function}" if self.current_function else self.current_class
                            parent_node_id = f"action::{self.current_function}" if self.current_function else f"model::{self.current_class}"
                            
                            usage_entry = {
                                "file": self.rel_path,
                                "line": node.lineno,
                                "context": context,
                                "parent_node_id": parent_node_id,
                            }
                            
                            if is_write and self.current_function != "__init__":
                                self.properties[prop_key]["writes"].append(usage_entry)
                            elif not is_write:
                                self.properties[prop_key]["reads"].append(usage_entry)
                
                # obj.x (external object) - best effort match
                elif isinstance(node.value, ast.Name):
                    obj_name = node.value.id
                    # Try to match against known properties
                    for prop_key in self.properties:
                        if prop_key.endswith(f".{attr_name}"):
                            context = f"{self.current_class}.{self.current_function}" if self.current_class and self.current_function else "module-level"
                            parent_node_id = f"action::{self.current_function}" if self.current_function else None
                            
                            usage_entry = {
                                "file": self.rel_path,
                                "line": node.lineno,
                                "context": context,
                                "parent_node_id": parent_node_id,
                            }
                            
                            if not is_write:
                                self.properties[prop_key]["reads"].append(usage_entry)
                            break  # Only match first
                
                self.generic_visit(node)
        
        # Add parent references for context
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                child._parent = node
        
        visitor = ContextVisitor(self, rel_path, properties)
        visitor.visit(tree)
    
    def _init_property(
        self,
        class_name: str,
        prop_name: str,
        file_path: str,
        line_number: int
    ) -> dict[str, Any]:
        """Initialize a property info dict."""
        return {
            "class_name": class_name,
            "prop_name": prop_name,
            "file_path": file_path,
            "first_line": line_number,
            "has_getter": False,
            "has_setter": False,
            "has_deleter": False,
            "is_class_var": False,
            "is_instance_var": False,
            "definitions": [],
            "reads": [],
            "writes": [],
        }
