"""Tests for BaseScanner."""

import pytest
from pathlib import Path
from flask_brain.scanners.base import BaseScanner
from flask_brain.graph import Node, Edge


class ConcreteScanner(BaseScanner):
    """Concrete implementation of BaseScanner for testing."""
    
    def scan(self) -> tuple[list[Node], list[Edge]]:
        """Implement abstract scan method."""
        return [], []


def test_base_scanner_abstract_scan_method():
    """Test that scan() is abstract and must be implemented (line 21)."""
    # Cannot instantiate BaseScanner directly
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        BaseScanner(Path("."))


def test_base_scanner_parse_file_handles_syntax_error(tmp_path):
    """Test _parse_file handles SyntaxError (lines 29-31)."""
    # Create file with invalid Python syntax
    bad_file = tmp_path / "bad_syntax.py"
    bad_file.write_text("def broken(\n  this is not valid python")
    
    scanner = ConcreteScanner(tmp_path)
    result = scanner._parse_file(bad_file)
    
    # Should return None for unparseable files
    assert result is None


def test_base_scanner_parse_file_handles_unicode_error(tmp_path):
    """Test _parse_file handles UnicodeDecodeError (lines 29-31)."""
    # Create file with invalid UTF-8
    bad_file = tmp_path / "bad_encoding.py"
    bad_file.write_bytes(b'\xff\xfe# invalid utf-8')
    
    scanner = ConcreteScanner(tmp_path)
    result = scanner._parse_file(bad_file)
    
    # Should return None for files with encoding issues
    assert result is None


def test_base_scanner_get_python_files_excludes_dirs(tmp_path):
    """Test _get_python_files excludes directories from EXCLUDED_DIRS (line 47)."""
    # Create structure with excluded directories
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("# main")
    
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "lib.py").write_text("# venv lib")
    
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cache.py").write_text("# cache")
    
    (tmp_path / "migrations").mkdir()
    (tmp_path / "migrations" / "version.py").write_text("# migration")
    
    scanner = ConcreteScanner(tmp_path)
    files = scanner._get_python_files()
    
    # Should only include main.py, not files in excluded dirs
    file_names = [f.name for f in files]
    assert "main.py" in file_names
    assert "lib.py" not in file_names
    assert "cache.py" not in file_names
    assert "version.py" not in file_names


def test_base_scanner_get_relative_path_handles_value_error(tmp_path):
    """Test _get_relative_path handles ValueError for paths outside project (lines 55-56)."""
    scanner = ConcreteScanner(tmp_path)
    
    # Path outside project root
    outside_path = Path("/some/other/path/file.py")
    result = scanner._get_relative_path(outside_path)
    
    # Should return absolute path as string when relative_to fails
    assert result == str(outside_path)


def test_base_scanner_parse_file_success(tmp_path):
    """Test _parse_file successfully parses valid Python file."""
    good_file = tmp_path / "good.py"
    good_file.write_text("def hello():\n    return 'world'")
    
    scanner = ConcreteScanner(tmp_path)
    result = scanner._parse_file(good_file)
    
    # Should return AST module
    assert result is not None
    assert hasattr(result, 'body')


def test_base_scanner_get_python_files_finds_nested_files(tmp_path):
    """Test _get_python_files finds Python files in nested directories."""
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "views").mkdir()
    (tmp_path / "app" / "views" / "user.py").write_text("# user views")
    (tmp_path / "app" / "models.py").write_text("# models")
    
    scanner = ConcreteScanner(tmp_path)
    files = scanner._get_python_files()
    
    # Should find both files
    file_names = [f.name for f in files]
    assert "user.py" in file_names
    assert "models.py" in file_names
    assert len(files) == 2


def test_base_scanner_get_relative_path_success(tmp_path):
    """Test _get_relative_path returns relative path for files in project."""
    (tmp_path / "app").mkdir()
    file_path = tmp_path / "app" / "main.py"
    file_path.write_text("# main")
    
    scanner = ConcreteScanner(tmp_path)
    result = scanner._get_relative_path(file_path)
    
    # Should return relative path
    assert result == "app/main.py" or result == "app\\main.py"  # Handle Windows paths
