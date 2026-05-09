"""Complexity analyzer - computes cyclomatic complexity."""

import ast
from pathlib import Path

from flask_brain.scanners.base import BaseScanner
from flask_brain.graph import Node, Edge


class ComplexityAnalyzer(BaseScanner):
    """Analyzer for code complexity metrics."""
    
    def scan(self) -> tuple[list[Node], list[Edge]]:
        """Scan project and return complexity metadata (no new nodes)."""
        # This scanner enriches existing nodes, so it returns empty lists
        # The actual enrichment happens in GraphBuilder
        return [], []
    
    def analyze_file(self, file_path: Path) -> dict[str, int]:
        """Analyze a file and return complexity metrics for each function."""
        tree = self._parse_file(file_path)
        if not tree:
            return {}
        
        complexities = {}
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                complexity = self._calculate_complexity(node)
                complexities[node.name] = complexity
        
        return complexities
    
    def _calculate_complexity(self, func_node: ast.FunctionDef) -> int:
        """Calculate cyclomatic complexity for a function."""
        complexity = 1  # Base complexity
        
        for node in ast.walk(func_node):
            # Add 1 for each decision point
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                # Add 1 for each and/or
                complexity += len(node.values) - 1
        
        return complexity
