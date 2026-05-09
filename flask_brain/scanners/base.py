"""Base scanner class."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
import ast

from flask_brain.graph import Node, Edge


class BaseScanner(ABC):
    """Base class for all scanners."""
    
    def __init__(self, project_path: Path):
        """Initialize scanner with project path."""
        self.project_path = Path(project_path)
    
    @abstractmethod
    def scan(self) -> tuple[list[Node], list[Edge]]:
        """Scan the project and return nodes and edges."""
        pass
    
    def _parse_file(self, file_path: Path) -> ast.Module | None:
        """Parse a Python file and return its AST."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return ast.parse(content, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError) as e:
            # Skip files that can't be parsed
            return None
    
    def _get_python_files(self) -> list[Path]:
        """Get all Python files in the project."""
        return list(self.project_path.rglob('*.py'))
    
    def _get_relative_path(self, file_path: Path) -> str:
        """Get path relative to project root."""
        try:
            return str(file_path.relative_to(self.project_path))
        except ValueError:
            return str(file_path)
