"""Main CLI application using Typer."""

from __future__ import annotations

import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from cognitive_hydraulics import __version__

app = typer.Typer(
    name="cognitive-hydraulics",
    help="🧠 Cognitive Hydraulics - Hybrid Symbolic/Neural Reasoning Engine",
    add_completion=False,
)
console = Console()


@app.command()
def version():
    """Show version information."""
    console.print(Panel.fit(
        f"[bold cyan]Cognitive Hydraulics[/bold cyan]\n"
        f"Version: [yellow]{__version__}[/yellow]\n"
        f"Hybrid Soar + ACT-R Architecture",
        title="🧠 Version Info",
    ))


@app.command()
def info():
    """Show architecture information."""
    info_text = """
[bold cyan]Cognitive Hydraulics Architecture[/bold cyan]

A hybrid reasoning system combining:

[bold green]• Soar (System 2)[/bold green] - Slow, deliberate, symbolic reasoning
  - Rule-based pattern matching
  - Sub-goal creation
  - Impasse detection

[bold yellow]• ACT-R (System 1)[/bold yellow] - Fast, heuristic reasoning
  - Utility-based selection (U = P*G - C)
  - LLM for probability/cost estimation
  - Automatic fallback on cognitive overload

[bold magenta]• Meta-Cognitive Monitor[/bold magenta]
  - Tracks reasoning depth, time, loops
  - Triggers fallback when pressure ≥ 0.7

[bold blue]• Learning System[/bold blue]
  - Chunks successful ACT-R resolutions
  - ChromaDB for semantic memory
  - 10x speedup on repeated patterns

[bold red]• Safety Layer[/bold red]
  - Human approval for destructive ops
  - Utility-based safety checks
  - Dry-run simulation mode
"""
    console.print(Panel(info_text, title="🧠 Architecture", border_style="cyan"))


@app.command()
def solve(
    goal: str = typer.Argument(..., help="Goal description"),
    working_dir: Path = typer.Option(
        ".", "--dir", "-d", help="Working directory"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Simulate without executing"
    ),
    enable_learning: bool = typer.Option(
        True, "--learning/--no-learning", help="Enable learning from experience"
    ),
    chunk_store: Optional[Path] = typer.Option(
        None, "--chunks", help="Path for persistent chunk storage"
    ),
    max_cycles: Optional[int] = typer.Option(
        None, "--max-cycles", help="Maximum decision cycles (overrides config)"
    ),
    verbose: int = typer.Option(
        2, "--verbose", "-v", help="Verbosity level: 0=silent, 1=basic, 2=thinking (default), 3=debug"
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Quiet mode (equivalent to --verbose=0)"
    ),
    config_path: Optional[Path] = typer.Option(
        None, "--config", help="Path to custom config file"
    ),
    resume: bool = typer.Option(
        False, "--resume", help="Resume from last active context (requires ChromaDB)"
    ),
):
    """
    Solve a goal using the cognitive agent.

    Example:
        cognitive-hydraulics solve "Fix the bug in main.py" --dir ./project
    """
    import asyncio
    from cognitive_hydraulics.engine import CognitiveAgent
    from cognitive_hydraulics.core.state import EditorState, Goal
    from cognitive_hydraulics.safety import SafetyConfig
    from cognitive_hydraulics.config import load_config

    # Load configuration
    config = load_config(custom_path=config_path)

    console.print(Panel.fit(
        f"[bold cyan]Goal:[/bold cyan] {goal}\n"
        f"[bold cyan]Working Directory:[/bold cyan] {working_dir}\n"
        f"[bold cyan]Dry-run:[/bold cyan] {dry_run}\n"
        f"[bold cyan]Learning:[/bold cyan] {enable_learning}\n"
        f"[bold cyan]Resume:[/bold cyan] {resume}\n"
        f"[bold cyan]Config:[/bold cyan] {config.llm_model} @ {config.llm_host}",
        title="🎯 Cognitive Agent",
        border_style="green",
    ))

    # Handle verbosity: quiet overrides verbose
    from cognitive_hydraulics.core.verbosity import normalize_verbose
    verbose_level = 0 if quiet else normalize_verbose(verbose)

    # Check for resume flag - try to resume from last active context
    if resume:
        if not enable_learning:
            console.print("[yellow]⚠ Warning: --resume requires learning to be enabled. Ignoring --resume flag.[/yellow]\n")
            resume = False
        else:
            try:
                # Try to load memory and check for active contexts
                memory_path = str(chunk_store) if chunk_store else None
                memory = UnifiedMemory(persist_directory=memory_path)
                active_context = memory.get_active_context()

                if active_context:
                    metadata = active_context.get('metadata', {})
                    goal_desc = metadata.get('goal_description', 'Unknown')
                    console.print(f"\n[bold green]📂 Resuming from last active context:[/bold green]")
                    console.print(f"[cyan]Goal: {goal_desc}[/cyan]")
                    console.print(f"[cyan]Depth: {metadata.get('depth', 0)}[/cyan]\n")

                    # Override the goal with the one from the context
                    goal = goal_desc
                else:
                    console.print("[yellow]ℹ No active context found to resume. Starting fresh.[/yellow]\n")
                    resume = False
            except Exception as e:
                console.print(f"[yellow]⚠ Warning: Failed to load memory for resume: {e}[/yellow]\n")
                console.print("[yellow]Starting fresh without resume.[/yellow]\n")
                resume = False

    # Create agent (CLI args override config)
    safety_config = SafetyConfig(dry_run=dry_run)
    agent = CognitiveAgent(
        safety_config=safety_config,
        enable_learning=enable_learning,
        chunk_store_path=str(chunk_store) if chunk_store else None,
        max_cycles=max_cycles,  # None means use config, value means override
        config=config,
    )

    # Create initial state and goal
    initial_state = EditorState(working_directory=str(working_dir))
    goal_obj = Goal(description=goal)

    # Run agent
    async def run():
        try:
            success, final_state = await agent.solve(
                goal=goal_obj,
                initial_state=initial_state,
                verbose=verbose_level,
            )

            if success:
                console.print("\n[bold green]✓ Goal achieved![/bold green]")
            else:
                console.print("\n[bold red]✗ Goal not achieved[/bold red]")

            # Show statistics
            if enable_learning and agent.memory:
                stats = agent.memory.get_stats()
                console.print(f"\n[cyan]Memory Stats:[/cyan]")
                console.print(f"  - Contexts: {stats['total_contexts']} (active: {stats['active_contexts']})")
                console.print(f"  - Chunks learned: {stats['total_chunks']}")

        except KeyboardInterrupt:
            console.print("\n[yellow]⚠ Interrupted by user[/yellow]")
        except Exception as e:
            console.print(f"\n[bold red]Error: {e}[/bold red]")
            raise

    asyncio.run(run())


@app.command()
def chunks(
    store_path: Optional[Path] = typer.Option(
        None, "--path", "-p", help="Path to chunk store"
    ),
    list_chunks: bool = typer.Option(
        False, "--list", "-l", help="List all chunks"
    ),
    clear: bool = typer.Option(
        False, "--clear", help="Clear all chunks"
    ),
):
    """
    Manage learned chunks.

    Examples:
        cognitive-hydraulics chunks --path ./chunks --list
        cognitive-hydraulics chunks --clear
    """
    from cognitive_hydraulics.memory import ChunkStore

    store = ChunkStore(persist_directory=str(store_path) if store_path else None)

    if clear:
        if typer.confirm("Clear all chunks?"):
            store.clear()
            console.print("[green]✓ Chunks cleared[/green]")
        return

    # Show stats
    stats = store.get_stats()
    console.print(Panel(
        f"[cyan]Total chunks:[/cyan] {stats['total_chunks']}\n"
        f"[cyan]Collection:[/cyan] {stats['collection_name']}",
        title="📊 Chunk Statistics",
    ))

    if list_chunks:
        console.print("\n[yellow]Chunk listing not yet implemented[/yellow]")


@app.command()
def example(
    name: str = typer.Argument("basic", help="Example name (basic, debug, learn)"),
):
    """
    Run an example scenario.

    Examples:
        cognitive-hydraulics example basic
        cognitive-hydraulics example debug
        cognitive-hydraulics example learn
    """
    examples = {
        "basic": "Demonstrate basic Soar reasoning",
        "debug": "Debug a code file with errors",
        "learn": "Show learning from repeated tasks",
    }

    if name not in examples:
        console.print(f"[red]Unknown example: {name}[/red]")
        console.print("\n[cyan]Available examples:[/cyan]")
        for ex_name, description in examples.items():
            console.print(f"  • {ex_name}: {description}")
        return

    console.print(Panel(
        f"[bold cyan]{name}[/bold cyan]\n{examples[name]}",
        title="📖 Example",
    ))

    console.print("\n[yellow]Example execution not yet implemented[/yellow]")
    console.print("[dim]This will run a full end-to-end scenario demonstrating the architecture[/dim]")


def version_callback(value: bool) -> None:
    """Callback for --version flag."""
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def callback(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
):
    """
    🧠 Cognitive Hydraulics - Hybrid Reasoning Engine

    Combines symbolic reasoning (Soar) with neural heuristics (ACT-R + LLM)
    for intelligent, adaptive problem solving.
    """
    pass


if __name__ == "__main__":
    app()

