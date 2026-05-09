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


@app.command()
def snapshot(
    path: Path = typer.Argument(..., help="Path to Flask project (with .flask-brain/ directory)"),
    label: str = typer.Option(None, "--label", "-l", help="Human-readable snapshot label"),
):
    """Create a named snapshot of the current graph."""
    from flask_brain.diff import SnapshotManager

    graph_dir = path / ".flask-brain"
    if not graph_dir.exists():
        console.print(f"[bold red]Error:[/bold red] No .flask-brain directory found in {path}")
        console.print("Run 'flask-brain scan' first.")
        raise typer.Exit(1)

    sm = SnapshotManager(path)
    try:
        sid = sm.create_snapshot(label=label)
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)

    console.print(f"[bold green]✓[/bold green] Snapshot created: [bold]{sid}[/bold]")
    if label:
        console.print(f"  Label: {label}")
    snaps_dir = graph_dir / "snapshots"
    console.print(f"  Saved to: {snaps_dir / f'snapshot-{sid}.json'}")


@app.command()
def snapshots(
    path: Path = typer.Argument(..., help="Path to Flask project (with .flask-brain/ directory)"),
    delete: str = typer.Option(None, "--delete", help="Delete a snapshot by ID"),
):
    """List (or delete) graph snapshots."""
    from flask_brain.diff import SnapshotManager

    sm = SnapshotManager(path)

    if delete:
        try:
            sm.delete_snapshot(delete)
            console.print(f"[bold green]✓[/bold green] Snapshot deleted: {delete}")
        except ValueError as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(1)
        return

    all_snaps = sm.list_snapshots()
    if not all_snaps:
        console.print("[dim]No snapshots found. Run 'flask-brain snapshot <path>' to create one.[/dim]")
        return

    console.print(f"[bold]Snapshots for {path}:[/bold]\n")
    for s in all_snaps:
        label_str = f"  {s['label']}" if s.get("label") else ""
        console.print(
            f"  [bold cyan]{s['id']}[/bold cyan]  "
            f"{s['created_at'][:16].replace('T', ' ')}  "
            f"{s.get('node_count', '?')} nodes, {s.get('edge_count', '?')} edges"
            f"{label_str}"
        )


@app.command(name="diff")
def diff_cmd(
    path: Path = typer.Argument(..., help="Path to Flask project"),
    baseline: str = typer.Option(..., "--baseline", "-b", help="Baseline snapshot ID"),
    current: str = typer.Option("current", "--current", "-c", help="Current snapshot ID or 'current'"),
    output: str = typer.Option("summary", "--output", help="Output format: summary or json"),
):
    """Compare current graph (or a snapshot) against a baseline snapshot."""
    import json as _json
    from flask_brain.diff import SnapshotManager, DiffEngine

    sm = SnapshotManager(path)

    try:
        baseline_graph = sm.load_snapshot(baseline)
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)

    if current == "current":
        graph_path = path / ".flask-brain" / "graph-all.json"
        if not graph_path.exists():
            console.print("[bold red]Error:[/bold red] No current graph. Run 'flask-brain scan' first.")
            raise typer.Exit(1)
        with open(graph_path) as f:
            from flask_brain.graph import Graph
            current_graph = Graph.from_dict(_json.load(f))
        current_label = "Current scan"
    else:
        try:
            current_graph = sm.load_snapshot(current)
        except ValueError as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(1)
        current_label = current

    diff = DiffEngine().compute_diff(baseline_graph, current_graph, baseline, current)

    if output == "json":
        console.print(_json.dumps(diff.to_dict(), indent=2))
        return

    # Summary mode
    snaps = {s["id"]: s for s in sm.list_snapshots()}
    baseline_label = snaps.get(baseline, {}).get("label") or baseline

    console.print(f"\n[bold]Comparing:[/bold]")
    console.print(f"  Baseline: [cyan]{baseline}[/cyan]{f'  ({baseline_label})' if baseline_label != baseline else ''}")
    console.print(f"  Current:  [cyan]{current_label}[/cyan]\n")
    console.print(f"[bold]Summary:[/bold]")

    s = diff.summary
    console.print(
        f"  Nodes:  [green]+{s['nodes_added']} added[/green]  "
        f"[red]-{s['nodes_removed']} removed[/red]  "
        f"[yellow]~{s['nodes_modified']} modified[/yellow]"
    )
    console.print(
        f"  Edges:  [green]+{s['edges_added']} added[/green]  "
        f"[red]-{s['edges_removed']} removed[/red]"
    )

    if diff.node_changes:
        console.print(f"\n[bold]Node Changes:[/bold]")
        for nc in sorted(diff.node_changes, key=lambda x: x.change_type):
            icon = {"added": "[green][+][/green]", "removed": "[red][-][/red]", "modified": "[yellow][~][/yellow]"}[nc.change_type]
            node = nc.new_node or nc.old_node or {}
            fp = node.get("file_path", "")
            ln = node.get("line_number", "")
            loc = f"{fp}:{ln}" if ln else fp
            changes_str = ""
            if nc.changes and nc.change_type == "modified":
                parts = []
                for field, vals in nc.changes.items():
                    if field != "metadata":
                        parts.append(f"{field}: {vals['old']} → {vals['new']}")
                if parts:
                    changes_str = f"  ({', '.join(parts)})"
            console.print(f"  {icon} {nc.node_id}  [dim]{loc}[/dim]{changes_str}")

    if diff.edge_changes:
        console.print(f"\n[bold]Edge Changes:[/bold]")
        for ec in sorted(diff.edge_changes, key=lambda x: x.change_type):
            icon = {"added": "[green][+][/green]", "removed": "[red][-][/red]"}[ec.change_type]
            console.print(f"  {icon} {ec.source} → {ec.target}  [dim]({ec.edge_type})[/dim]")


if __name__ == "__main__":
    app()
