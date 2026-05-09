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

        # --- Pass 1: collect all mixin column definitions across every file ---
        # key: mixin class name  →  value: {col_name: col_info_dict}
        mixin_columns: dict[str, dict[str, dict]] = {}
        for py_file in self._get_python_files():
            tree = self._parse_file(py_file)
            if tree:
                self._collect_mixins(tree, mixin_columns)

        # --- Pass 2: extract model classes, merging inherited mixin columns ---
        for py_file in self._get_python_files():
            tree = self._parse_file(py_file)
            if tree:
                file_nodes, file_edges = self._extract_models(tree, py_file, mixin_columns)
                nodes.extend(file_nodes)
                edges.extend(file_edges)

        return nodes, edges

    # ------------------------------------------------------------------ #
    #  Pass-1 helpers: mixin discovery                                    #
    # ------------------------------------------------------------------ #

    def _collect_mixins(
        self,
        tree: ast.Module,
        mixin_columns: dict[str, dict[str, dict]],
    ) -> None:
        """Scan every class that is NOT a db.Model and record its columns."""
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if self._is_model_class(node):
                continue  # actual model — handled in pass 2
            # Heuristic: any class whose name ends in "Mixin" or whose body
            # contains Column() assignments is treated as a mixin donor.
            cols = self._extract_columns_from_body(node.body, source_mixin=node.name)
            if cols:
                mixin_columns.setdefault(node.name, {}).update(cols)

    # ------------------------------------------------------------------ #
    #  Pass-2 helpers: model extraction                                   #
    # ------------------------------------------------------------------ #

    def _extract_models(
        self,
        tree: ast.Module,
        file_path: Path,
        mixin_columns: dict[str, dict[str, dict]],
    ) -> tuple[list[Node], list[Edge]]:
        """Extract model classes from AST, merging mixin columns."""
        nodes = []
        edges = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if self._is_model_class(node):
                    model_node, model_edges = self._parse_model_class(
                        node, file_path, mixin_columns
                    )
                    if model_node:
                        nodes.append(model_node)
                        edges.extend(model_edges)

        return nodes, edges

    def _is_model_class(self, class_node: ast.ClassDef) -> bool:
        """Check if a class is a SQLAlchemy model (inherits from db.Model / Base)."""
        for base in class_node.bases:
            if isinstance(base, ast.Attribute):
                if base.attr == "Model":
                    return True
            elif isinstance(base, ast.Name):
                if base.id in ("Model", "Base", "DeclarativeBase"):
                    return True
        return False

    def _base_names(self, class_node: ast.ClassDef) -> list[str]:
        """Return simple string names of all base classes."""
        names = []
        for base in class_node.bases:
            if isinstance(base, ast.Name):
                names.append(base.id)
            elif isinstance(base, ast.Attribute):
                names.append(base.attr)
        return names

    def _parse_model_class(
        self,
        class_node: ast.ClassDef,
        file_path: Path,
        mixin_columns: dict[str, dict[str, dict]],
    ) -> tuple[Node | None, list[Edge]]:
        """Parse a model class, extract own columns/relationships, merge mixins."""
        model_name = class_node.name

        # Own columns and relationships from this class body
        own_columns = self._extract_columns_from_body(class_node.body)
        relationships = self._extract_relationships_from_body(class_node.body)

        # Merge inherited mixin columns (tagged with from_mixin)
        merged_columns: dict[str, dict] = {}
        for base_name in self._base_names(class_node):
            if base_name in mixin_columns:
                for col_name, col_info in mixin_columns[base_name].items():
                    if col_name not in merged_columns:
                        merged_columns[col_name] = dict(col_info)  # copy
        # Own columns win over inherited ones
        merged_columns.update(own_columns)

        node = Node(
            id=f"model::{model_name}",
            type=NodeType.MODEL,
            label=model_name,
            file_path=self._get_relative_path(file_path),
            line_number=class_node.lineno,
            metadata={
                "columns": merged_columns,
                "relationships": [r["name"] for r in relationships],
                "base_classes": self._base_names(class_node),
            },
        )

        # Relationship edges — skip self-loops
        edges = []
        for rel in relationships:
            source = f"model::{model_name}"
            target = f"model::{rel['target']}"
            if source == target:
                continue
            edge = Edge(
                source=source,
                target=target,
                type=EdgeType.HAS_RELATIONSHIP,
                metadata={"relationship_name": rel["name"]},
            )
            edges.append(edge)

        return node, edges

    # ------------------------------------------------------------------ #
    #  Shared body parsers                                                 #
    # ------------------------------------------------------------------ #

    def _extract_columns_from_body(
        self,
        body: list[ast.stmt],
        source_mixin: str | None = None,
    ) -> dict[str, dict]:
        """Return {col_name: {type, ?from_mixin}} for every Column() in body."""
        columns: dict[str, dict] = {}
        for item in body:
            col_name = None
            call_node = None

            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        col_name = target.id
                if col_name and isinstance(item.value, ast.Call):
                    call_node = item.value

            elif isinstance(item, ast.AnnAssign):
                if isinstance(item.target, ast.Name) and item.value is not None:
                    col_name = item.target.id
                    if isinstance(item.value, ast.Call):
                        call_node = item.value

            if col_name and call_node and self._is_column_call(call_node):
                col_type = self._extract_column_type(call_node)
                info: dict[str, Any] = {"type": col_type}
                if source_mixin:
                    info["from_mixin"] = source_mixin
                columns[col_name] = info

        return columns

    def _extract_relationships_from_body(
        self, body: list[ast.stmt]
    ) -> list[dict]:
        """Return list of {name, target} for every relationship() in body."""
        relationships = []
        for item in body:
            col_name = None
            call_node = None

            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        col_name = target.id
                if col_name and isinstance(item.value, ast.Call):
                    call_node = item.value

            elif isinstance(item, ast.AnnAssign):
                if isinstance(item.target, ast.Name) and item.value is not None:
                    col_name = item.target.id
                    if isinstance(item.value, ast.Call):
                        call_node = item.value

            if col_name and call_node and self._is_relationship_call(call_node):
                rel_target = self._extract_relationship_target(call_node)
                if rel_target:
                    relationships.append({"name": col_name, "target": rel_target})

        return relationships

    # ------------------------------------------------------------------ #
    #  Low-level AST helpers                                              #
    # ------------------------------------------------------------------ #

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
        """Extract the SQLAlchemy type name from a Column() call.

        Handles these shapes of first argument:
          - db.Integer          → ast.Attribute  → "Integer"
          - Integer             → ast.Name       → "Integer"
          - db.String(128)      → ast.Call       → "String"  (nested call)
          - String(128)         → ast.Call       → "String"
          - "col_alias", ...    → ast.Constant   → look at second arg for type
        """
        if not call_node.args:
            return "Unknown"

        first_arg = call_node.args[0]

        # Column("alias", db.Integer, ...) — string alias as first arg
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            # The actual type is the second positional arg
            if len(call_node.args) >= 2:
                first_arg = call_node.args[1]
            else:
                return "Unknown"

        if isinstance(first_arg, ast.Attribute):
            return first_arg.attr

        if isinstance(first_arg, ast.Name):
            return first_arg.id

        if isinstance(first_arg, ast.Call):
            # db.String(128), String(64), db.Numeric(10, 2) …
            func = first_arg.func
            if isinstance(func, ast.Attribute):
                return func.attr
            if isinstance(func, ast.Name):
                return func.id

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
