"""Query tracer - detects database operations."""

import ast
from pathlib import Path

from flask_brain.scanners.base import BaseScanner
from flask_brain.graph import Node, Edge


class QueryTracer(BaseScanner):
    """Tracer for database operations."""
    
    def scan(self) -> tuple[list[Node], list[Edge]]:
        """Scan project and return query metadata (no new nodes)."""
        # This scanner enriches existing nodes, so it returns empty lists
        return [], []
    
    def analyze_function(self, func_node: ast.FunctionDef) -> list[dict]:
        """Analyze a function and return database operations."""
        operations = []
        
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                op_type = self._classify_db_operation(node)
                if op_type:
                    operations.append({"type": op_type})
        
        return operations
    
    def _classify_db_operation(self, call_node: ast.Call) -> str | None:
        """Classify a call as a database operation."""
        if isinstance(call_node.func, ast.Attribute):
            attr = call_node.func.attr
            
            # db.session operations
            if attr in ("add", "delete", "commit", "execute"):
                if attr in ("add", "commit", "execute"):
                    return "WRITE"
                elif attr == "delete":
                    return "DELETE"
            
            # Model.query operations
            elif attr in ("filter", "filter_by", "all", "first", "get", "one"):
                return "READ"
        
        return None
