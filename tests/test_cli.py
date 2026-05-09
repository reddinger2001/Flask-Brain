"""Tests for CLI commands."""

import pytest
from pathlib import Path
import json
import shutil
from typer.testing import CliRunner

from flask_brain.cli import app


@pytest.fixture
def cli_runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def blueprint_app_path():
    """Path to blueprint app fixture."""
    return Path(__file__).parent / "fixtures" / "blueprint_app"


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create a temporary output directory."""
    output_dir = tmp_path / ".flask-brain"
    yield output_dir
    # Cleanup
    if output_dir.exists():
        shutil.rmtree(output_dir)


def test_cli_help(cli_runner):
    """Test that --help shows available commands."""
    result = cli_runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "scan" in result.stdout
    assert "serve" in result.stdout


def test_cli_scan_help(cli_runner):
    """Test that scan --help shows scan options."""
    result = cli_runner.invoke(app, ["scan", "--help"])
    assert result.exit_code == 0
    assert "--output" in result.stdout or "-o" in result.stdout
    assert "--no-serve" in result.stdout


def test_cli_scan_creates_output_files(cli_runner, blueprint_app_path, temp_output_dir):
    """Test that scan creates manifest and graph JSON files."""
    result = cli_runner.invoke(app, [
        "scan",
        str(blueprint_app_path),
        "--output", str(temp_output_dir),
        "--no-serve"
    ])
    
    assert result.exit_code == 0
    
    # Check that output files were created
    assert (temp_output_dir / "manifest.json").exists()
    assert (temp_output_dir / "graph-all.json").exists()
    assert (temp_output_dir / "graph-routes.json").exists()
    
    # Verify manifest content
    with open(temp_output_dir / "manifest.json") as f:
        manifest = json.load(f)
        assert "node_count" in manifest
        assert "edge_count" in manifest
        assert manifest["node_count"] > 0
        assert manifest["edge_count"] > 0


def test_cli_scan_nonexistent_path(cli_runner):
    """Test that scan fails gracefully with nonexistent path."""
    result = cli_runner.invoke(app, [
        "scan",
        "/nonexistent/path/to/project",
        "--no-serve"
    ])
    
    assert result.exit_code != 0


def test_cli_scan_creates_default_output_dir(cli_runner, blueprint_app_path):
    """Test that scan creates .flask-brain in project root by default."""
    # Clean up any existing .flask-brain directory
    default_output = blueprint_app_path / ".flask-brain"
    if default_output.exists():
        shutil.rmtree(default_output)
    
    try:
        result = cli_runner.invoke(app, [
            "scan",
            str(blueprint_app_path),
            "--no-serve"
        ])
        
        assert result.exit_code == 0
        assert default_output.exists()
        assert (default_output / "manifest.json").exists()
    finally:
        # Cleanup
        if default_output.exists():
            shutil.rmtree(default_output)


def test_cli_serve_missing_graph_dir(cli_runner, tmp_path):
    """Test that serve fails when .flask-brain directory doesn't exist."""
    result = cli_runner.invoke(app, [
        "serve",
        str(tmp_path)
    ])
    
    assert result.exit_code != 0
    assert ".flask-brain" in result.stdout or "not found" in result.stdout.lower()
