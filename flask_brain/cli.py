"""CLI entry point for Flask Brain."""

import typer
from pathlib import Path
from rich.console import Console

app = typer.Typer(
    name="flask-brain",
    help="Interactive architecture visualizer for Flask/Python projects",
    add_completion=False,
)
console = Console()


@app.command()
def scan(
    path: Path = typer.Argument(..., help="Path to Flask project to scan"),
    output: Path = typer.Option(None, "--output", "-o", help="Output directory for graph JSON"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch for file changes and re-scan"),
    port: int = typer.Option(7891, "--port", "-p", help="Port for HTTP server"),
    no_serve: bool = typer.Option(False, "--no-serve", help="Don't start HTTP server after scan"),
):
    """Scan a Flask project and generate architecture graph."""
    console.print(f"[bold green]Scanning Flask project:[/bold green] {path}")
    console.print(f"[dim]Output directory: {output or path / '.flask-brain'}[/dim]")
    console.print(f"[dim]Watch mode: {watch}[/dim]")
    console.print(f"[dim]Port: {port}[/dim]")
    console.print(f"[dim]Serve: {not no_serve}[/dim]")
    console.print("[yellow]Scan functionality not yet implemented[/yellow]")


@app.command()
def serve(
    path: Path = typer.Argument(..., help="Path to Flask project (with .flask-brain/ directory)"),
    port: int = typer.Option(7891, "--port", "-p", help="Port for HTTP server"),
):
    """Start HTTP server to view previously scanned project."""
    console.print(f"[bold green]Starting server for:[/bold green] {path}")
    console.print(f"[dim]Port: {port}[/dim]")
    console.print("[yellow]Serve functionality not yet implemented[/yellow]")


@app.command()
def export_context(
    path: Path = typer.Argument(..., help="Path to Flask project (with .flask-brain/ directory)"),
    route: str = typer.Option(None, "--route", help="Route to export context for"),
    node: str = typer.Option(None, "--node", help="Node ID to export context for"),
    format: str = typer.Option("md", "--format", help="Output format (json or md)"),
):
    """Export AI-ready context for a specific node or route."""
    console.print(f"[bold green]Exporting context for:[/bold green] {path}")
    console.print(f"[dim]Route: {route}[/dim]")
    console.print(f"[dim]Node: {node}[/dim]")
    console.print(f"[dim]Format: {format}[/dim]")
    console.print("[yellow]Export context functionality not yet implemented[/yellow]")


if __name__ == "__main__":
    app()
