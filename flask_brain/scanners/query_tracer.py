"""Query tracer - detects database operations."""

import ast
from pathlib import Path

from flask_brain.scanners.base import BaseScanner
from flask_brain.graph import Graph, Node, NodeType


class QueryTracer(BaseScanner):
    """Tracer for database operations."""
    
    def scan(self) -> tuple[list[Node], list]:
        """Scan project and return query metadata (no new nodes)."""
        # This scanner enriches existing nodes, so it returns empty lists
        return [], []
    
    def enrich(self, graph: Graph) -> None:
        """Enrich graph nodes with db_operations metadata."""
        # Build a map of file_path -> AST for efficient lookup
        file_asts: dict[str, ast.Module] = {}
        
        for node in graph.nodes.values():
            # Get the full file path
            full_path = self.project_path / node.file_path
            
            # Skip if file doesn't exist
            if not full_path.exists():
                continue
            
            # Parse file if not already parsed
            if node.file_path not in file_asts:
                tree = self._parse_file(full_path)
                if tree:
                    file_asts[node.file_path] = tree
            
            # Skip if file couldn't be parsed
            if node.file_path not in file_asts:
                continue
            
            tree = file_asts[node.file_path]
            
            # Analyze functions and classes for DB operations
            if node.type in [NodeType.ACTION, NodeType.SERVICE, NodeType.TASK]:
                # Find function by name and line number
                func_node = self._find_function(tree, node.label, node.line_number)
                if func_node:
                    operations = self._analyze_function(func_node)
                    node.metadata["db_operations"] = operations
                
                # For service classes, analyze all methods
                elif node.type == NodeType.SERVICE and "methods" in node.metadata:
                    class_node = self._find_class(tree, node.label, node.line_number)
                    if class_node:
                        operations = self._analyze_class(class_node)
                        node.metadata["db_operations"] = operations
    
    def _find_function(self, tree: ast.Module, name: str, line_number: int) -> ast.FunctionDef | None:
        """Find a function in the AST by name and approximate line number."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name == name and abs(node.lineno - line_number) < 5:
                    return node
        return None
    
    def _find_class(self, tree: ast.Module, name: str, line_number: int) -> ast.ClassDef | None:
        """Find a class in the AST by name and approximate line number."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if node.name == name and abs(node.lineno - line_number) < 5:
                    return node
        return None
    
    def _analyze_function(self, func_node: ast.FunctionDef) -> list[dict]:
        """Analyze a function and return database operations."""
        operations = []
        
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                op_type, pattern = self._classify_db_operation(node)
                if op_type:
                    operations.append({
                        "type": op_type,
                        "pattern": pattern
                    })
        
        return operations
    
    def _analyze_class(self, class_node: ast.ClassDef) -> list[dict]:
        """Analyze all methods in a class and return database operations."""
        operations = []
        
        for node in ast.walk(class_node):
            if isinstance(node, ast.FunctionDef):
                func_ops = self._analyze_function(node)
                operations.extend(func_ops)
        
        return operations
    
    def _classify_db_operation(self, call_node: ast.Call) -> tuple[str | None, str]:
        """Classify a call as a database operation."""
        if isinstance(call_node.func, ast.Attribute):
            attr = call_node.func.attr
            
            # Check for db.session.* operations
            if isinstance(call_node.func.value, ast.Attribute):
                if isinstance(call_node.func.value.value, ast.Name):
                    obj_name = call_node.func.value.value.id
                    middle_attr = call_node.func.value.attr
                    
                    # db.session.add(), db.session.delete(), db.session.commit()
                    if obj_name == "db" and middle_attr == "session":
                        if attr == "add":
                            return "WRITE", "db.session.add()"
                        elif attr == "delete":
                            return "DELETE", "db.session.delete()"
                        elif attr == "commit":
                            return "WRITE", "db.session.commit()"
                        elif attr == "execute":
                            return "READ", "db.session.execute()"
                        elif attr == "query":
                            return "READ", "db.session.query()"
            
            # Check for Model.query.* operations
            if isinstance(call_node.func.value, ast.Attribute):
                if call_node.func.value.attr == "query":
                    if attr in ("filter", "filter_by", "all", "first", "get", "one"):
                        return "READ", f"Model.query.{attr}()"
            
            # Direct Model.query.* calls
            if attr in ("filter", "filter_by", "all", "first", "get", "one"):
                return "READ", f".{attr}()"
        
        return None, ""
