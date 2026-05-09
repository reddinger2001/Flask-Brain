"""Model scanner - detects SQLAlchemy models, columns, and relationships."""

import ast
from pathlib import Path
from typing import Any

from flask_brain.scanners.base import BaseScanner
from flask_brain.graph import Node, Edge, NodeType, EdgeType


class ModelScanner(BaseScanner):
    """Scanner for SQLAlchemy models."""
    
    def scan(self) -> tuple[list[Node], list[Edge]]:
        """Scan project for SQLAlchemy models."""
        nodes = []
        edges = []
        
        for py_file in self._get_python_files():
            tree = self._parse_file(py_file)
            if tree:
                file_nodes, file_edges = self._extract_models(tree, py_file)
                nodes.extend(file_nodes)
                edges.extend(file_edges)
        
        return nodes, edges
    
    def _extract_models(self, tree: ast.Module, file_path: Path) -> tuple[list[Node], list[Edge]]:
        """Extract model classes from AST."""
        nodes = []
        edges = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if class inherits from Model or Base
                if self._is_model_class(node):
                    model_node, model_edges = self._parse_model_class(node, file_path)
                    if model_node:
                        nodes.append(model_node)
                        edges.extend(model_edges)
        
        return nodes, edges
    
    def _is_model_class(self, class_node: ast.ClassDef) -> bool:
        """Check if a class is a SQLAlchemy model."""
        for base in class_node.bases:
            # Check for db.Model, Base, DeclarativeBase
            if isinstance(base, ast.Attribute):
                if base.attr == "Model":
                    return True
            elif isinstance(base, ast.Name):
                if base.id in ("Model", "Base", "DeclarativeBase"):
                    return True
        return False
    
    def _parse_model_class(self, class_node: ast.ClassDef, file_path: Path) -> tuple[Node | None, list[Edge]]:
        """Parse a model class and extract columns and relationships."""
        model_name = class_node.name
        columns = {}
        relationships = []
        
        # Extract columns and relationships from class body.
        # Two AST node shapes must be handled:
        #   - ast.Assign:    name = db.Column(...)           (classic style)
        #   - ast.AnnAssign: name: type = db.Column(...)     (PEP-526 annotated style)
        for item in class_node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        col_name = target.id
                        if isinstance(item.value, ast.Call):
                            if self._is_column_call(item.value):
                                col_type = self._extract_column_type(item.value)
                                columns[col_name] = {"type": col_type}
                            elif self._is_relationship_call(item.value):
                                rel_target = self._extract_relationship_target(item.value)
                                if rel_target:
                                    relationships.append({
                                        "name": col_name,
                                        "target": rel_target
                                    })
            elif isinstance(item, ast.AnnAssign):
                # PEP-526 annotated assignment: `name: Type = db.Column(...)`
                # item.target is a single Name node (not a list)
                if isinstance(item.target, ast.Name) and item.value is not None:
                    col_name = item.target.id
                    if isinstance(item.value, ast.Call):
                        if self._is_column_call(item.value):
                            col_type = self._extract_column_type(item.value)
                            columns[col_name] = {"type": col_type}
                        elif self._is_relationship_call(item.value):
                            rel_target = self._extract_relationship_target(item.value)
                            if rel_target:
                                relationships.append({
                                    "name": col_name,
                                    "target": rel_target
                                })
        
        # Create model node
        node = Node(
            id=f"model::{model_name}",
            type=NodeType.MODEL,
            label=model_name,
            file_path=self._get_relative_path(file_path),
            line_number=class_node.lineno,
            metadata={
                "columns": columns,
                "relationships": [r["name"] for r in relationships]
            }
        )
        
        # Create relationship edges — skip self-loops
        edges = []
        for rel in relationships:
            source = f"model::{model_name}"
            target = f"model::{rel['target']}"
            if source == target:
                continue  # self-referential FK — skip, Cytoscape can't draw it
            edge = Edge(
                source=source,
                target=target,
                type=EdgeType.HAS_RELATIONSHIP,
                metadata={"relationship_name": rel["name"]}
            )
            edges.append(edge)
        
        return node, edges
    
    def _is_column_call(self, call_node: ast.Call) -> bool:
        """Check if a call is db.Column() or mapped_column()."""
        if isinstance(call_node.func, ast.Attribute):
            if call_node.func.attr in ("Column", "mapped_column"):
                return True
        elif isinstance(call_node.func, ast.Name):
            if call_node.func.id in ("Column", "mapped_column"):
                return True
        return False
    
    def _is_relationship_call(self, call_node: ast.Call) -> bool:
        """Check if a call is db.relationship() or relationship()."""
        if isinstance(call_node.func, ast.Attribute):
            if call_node.func.attr == "relationship":
                return True
        elif isinstance(call_node.func, ast.Name):
            if call_node.func.id == "relationship":
                return True
        return False
    
    def _extract_column_type(self, call_node: ast.Call) -> str:
        """Extract column type from Column() call."""
        if call_node.args:
            first_arg = call_node.args[0]
            if isinstance(first_arg, ast.Attribute):
                return first_arg.attr
            elif isinstance(first_arg, ast.Name):
                return first_arg.id
        return "Unknown"
    
    def _extract_relationship_target(self, call_node: ast.Call) -> str | None:
        """Extract target model name from relationship() call."""
        if call_node.args:
            first_arg = call_node.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                return first_arg.value
            elif isinstance(first_arg, ast.Str):  # Python < 3.8
                return first_arg.s
        return None
