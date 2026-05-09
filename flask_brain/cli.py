"""CLI entry point for Flask Brain."""

import typer
import json
from pathlib import Path
from rich.console import Console
from flask_brain.graph import GraphBuilder, Graph
from flask_brain.server import start_server
from flask_brain.context_export import export_context as _export_context

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
    
    # Validate path
    if not path.exists():
        console.print(f"[bold red]Error:[/bold red] Path does not exist: {path}")
        raise typer.Exit(1)
    
    # Determine output directory
    output_dir = output or (path / ".flask-brain")
    console.print(f"[dim]Output directory: {output_dir}[/dim]")
    
    # Build graph
    console.print("[yellow]Running scanners...[/yellow]")
    builder = GraphBuilder()
    graph = builder.build(path)
    
    # Write graph to disk
    console.print(f"[yellow]Writing graph data...[/yellow]")
    graph.write(output_dir)
    
    console.print(f"[bold green]✓[/bold green] Scan complete!")
    console.print(f"  Nodes: {len(graph.nodes)}")
    console.print(f"  Edges: {len(graph.edges)}")
    
    # Start server if requested
    if not no_serve:
        console.print(f"\n[bold blue]Starting HTTP server on port {port}...[/bold blue]")
        if watch:
            console.print("[dim]Watch mode: auto-rescan on .py changes[/dim]")
        start_server(output_dir, port=port, open_browser=True, watch=watch)
    elif watch:
        console.print("[yellow]--watch requires server (remove --no-serve)[/yellow]")


@app.command()
def serve(
    path: Path = typer.Argument(..., help="Path to Flask project (with .flask-brain/ directory)"),
    port: int = typer.Option(7891, "--port", "-p", help="Port for HTTP server"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch for file changes and auto-rescan"),
):
    """Start HTTP server to view previously scanned project."""
    console.print(f"[bold green]Starting server for:[/bold green] {path}")
    
    # Find .flask-brain directory
    graph_dir = path / ".flask-brain"
    if not graph_dir.exists():
        console.print(f"[bold red]Error:[/bold red] No .flask-brain directory found in {path}")
        console.print("Run 'flask-brain scan' first to generate graph data.")
        raise typer.Exit(1)
    
    if watch:
        console.print("[dim]Watch mode: auto-rescan on .py changes[/dim]")
    start_server(graph_dir, port=port, open_browser=True, project_path=path, watch=watch)


@app.command()
def export_context(
    path: Path = typer.Argument(..., help="Path to Flask project (with .flask-brain/ directory)"),
    route: str = typer.Option(None, "--route", help="Route node ID to export context for"),
    node: str = typer.Option(None, "--node", help="Node ID to export context for"),
    format: str = typer.Option("md", "--format", help="Output format: md or json"),
    budget: int = typer.Option(4000, "--budget", help="Approximate token budget"),
    depth: int = typer.Option(3, "--depth", help="BFS depth from focal node"),
    output: Path = typer.Option(None, "--output", "-o", help="Write output to file instead of stdout"),
):
    """Export AI-ready context for a specific node or route."""
    graph_dir = path / ".flask-brain"
    if not graph_dir.exists():
        console.print(f"[bold red]Error:[/bold red] No .flask-brain directory found in {path}")
        console.print("Run 'flask-brain scan' first.")
        raise typer.Exit(1)

    graph_path = graph_dir / "graph-all.json"
    if not graph_path.exists():
        console.print(f"[bold red]Error:[/bold red] graph-all.json not found in {graph_dir}")
        raise typer.Exit(1)

    node_id = node or route
    if not node_id:
        console.print("[bold red]Error:[/bold red] Provide --node or --route")
        raise typer.Exit(1)

    with open(graph_path) as f:
        graph_data = json.load(f)

    graph = Graph.from_dict(graph_data)

    try:
        context_md = _export_context(graph, node_id, budget=budget, depth=depth)
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)

    if format == "json":
        result = json.dumps({"node_id": node_id, "context": context_md}, indent=2)
    else:
        result = context_md

    if output:
        output.write_text(result)
        console.print(f"[bold green]✓[/bold green] Context written to {output}")
    else:
        console.print(result)


if __name__ == "__main__":
    app()
