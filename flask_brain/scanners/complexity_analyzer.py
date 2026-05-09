"""Complexity analyzer - computes cyclomatic complexity."""

import ast
from pathlib import Path

from flask_brain.scanners.base import BaseScanner
from flask_brain.graph import Graph, Node, Edge


class ComplexityAnalyzer(BaseScanner):
    """Analyzer for code complexity metrics."""
    
    def scan(self) -> tuple[list[Node], list[Edge]]:
        """Scan project and return complexity metadata (no new nodes)."""
        # This scanner enriches existing nodes, so it returns empty lists
        # The actual enrichment happens via the enrich() method
        return [], []
    
    def enrich(self, graph: Graph) -> None:
        """Enrich graph nodes with complexity metadata."""
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
            
            # Find the function/class in the AST
            from flask_brain.graph import NodeType
            if node.type in [NodeType.ACTION, NodeType.SERVICE, NodeType.TASK]:
                # Find function by name and line number
                func_node = self._find_function(tree, node.label, node.line_number)
                if func_node:
                    complexity = self._calculate_complexity(func_node)
                    line_count = self._count_lines(func_node)
                    
                    node.metadata["complexity"] = complexity
                    node.metadata["line_count"] = line_count
                    node.metadata["complexity_tier"] = self._get_complexity_tier(complexity)
            
            # For service classes, check if they're "fat"
            if node.type == NodeType.SERVICE and "methods" in node.metadata:
                class_node = self._find_class(tree, node.label, node.line_number)
                if class_node:
                    method_count = len(node.metadata["methods"])
                    line_count = self._count_lines(class_node)
                    
                    node.metadata["line_count"] = line_count
                    node.metadata["is_fat"] = method_count > 10 or line_count > 300
    
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
    
    def _calculate_complexity(self, func_node: ast.FunctionDef) -> int:
        """Calculate cyclomatic complexity for a function."""
        complexity = 1  # Base complexity
        
        for node in ast.walk(func_node):
            # Add 1 for each decision point
            if isinstance(node, ast.If):
                complexity += 1
            elif isinstance(node, ast.While):
                complexity += 1
            elif isinstance(node, ast.For):
                complexity += 1
            elif isinstance(node, ast.ExceptHandler):
                complexity += 1
            elif isinstance(node, ast.With):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                # Add 1 for each and/or operator
                complexity += len(node.values) - 1
            elif isinstance(node, ast.IfExp):
                # Ternary operator
                complexity += 1
        
        return complexity
    
    def _count_lines(self, node: ast.FunctionDef | ast.ClassDef) -> int:
        """Count lines of code in a function or class."""
        # Get the last line number in the node
        last_line = node.lineno
        for child in ast.walk(node):
            if hasattr(child, 'lineno'):
                last_line = max(last_line, child.lineno)
        
        return last_line - node.lineno + 1
    
    def _get_complexity_tier(self, complexity: int) -> str:
        """Get complexity tier based on cyclomatic complexity."""
        if complexity <= 5:
            return "low"
        elif complexity <= 10:
            return "moderate"
        elif complexity <= 20:
            return "high"
        else:
            return "critical"
