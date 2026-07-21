#!/usr/bin/env python3
"""
Phantom CLI - Command-line interface for Phantom AI toolkit.

Usage:
    phantom extract -i <input> -o <output>   Extract insights from documents
    phantom analyze <file>                    Analyze a single file
    phantom classify <dir>                    Classify files into categories
    phantom scan <dir>                        Scan for sensitive data patterns
    phantom rag query <question>              Query RAG pipeline
    phantom rag ingest <dir>                  Ingest documents into RAG
    phantom tools vram                        Calculate VRAM requirements
"""

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="phantom",
    help="Phantom AI - Document Intelligence & Classification Pipeline",
    add_completion=False,
)
console = Console()


@app.command()
def extract(
    input_path: Path = typer.Option(
        ..., "-i", "--input", help="Input directory or file"
    ),
    output_path: Path = typer.Option(..., "-o", "--output", help="Output file (JSONL)"),
    format: str = typer.Option("jsonl", "-f", "--format", help="Output format"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output"),
):
    """Extract insights from markdown documents using LLM."""
    from phantom.core.cortex import CortexProcessor

    if not input_path.exists():
        console.print(f"[red]Error: {input_path} does not exist[/]")
        raise typer.Exit(1)

    processor = CortexProcessor(enable_vectors=False, verbose=verbose)

    # Collect files
    files: list[Path] = []
    if input_path.is_file():
        files = [input_path]
    else:
        files = sorted(
            f for f in input_path.rglob("*")
            if f.is_file() and f.suffix in (".md", ".txt", ".rst", ".tex")
        )

    if not files:
        console.print("[yellow]No processable files found[/]")
        raise typer.Exit(0)

    console.print(f"[cyan]Extracting insights from {len(files)} file(s)[/]")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    results = []

    for filepath in files:
        try:
            insights = processor.process_document(filepath)
            results.append(insights.model_dump())
        except Exception as e:
            console.print(f"[red]Failed: {filepath.name}: {e}[/]")

    with open(output_path, "w", encoding="utf-8") as f:
        if format == "jsonl":
            for r in results:
                f.write(json.dumps(r, default=str) + "\n")
        else:
            json.dump(results, f, indent=2, default=str)

    console.print(f"[green]Extracted {len(results)} document(s) -> {output_path}[/]")


@app.command()
def analyze(
    file: Path = typer.Argument(..., help="File to analyze"),
    sentiment: bool = typer.Option(
        True, "--sentiment", help="Include sentiment analysis"
    ),
    entities: bool = typer.Option(True, "--entities", help="Include entity extraction"),
):
    """Perform comprehensive analysis on a document."""
    if not file.exists():
        console.print(f"[red]Error: {file} does not exist[/]")
        raise typer.Exit(1)

    content = file.read_text(encoding="utf-8")
    console.print(f"[cyan]Analyzing: {file.name} ({len(content.split())} words)[/]")

    # CORTEX extraction
    from phantom.core.cortex import CortexProcessor

    processor = CortexProcessor(enable_vectors=False, verbose=False)
    insights = processor.process_document(file)

    # Sentiment analysis
    if sentiment:
        try:
            from phantom.analysis.sentiment_analysis import SentimentEngine

            engine = SentimentEngine(use_spacy=False)
            sent_result = engine.analyze(content)
            console.print(
                f"\n[bold]Sentiment:[/] {sent_result.label} "
                f"(score: {sent_result.score:.3f})"
            )
        except Exception as e:
            console.print(f"[yellow]Sentiment analysis unavailable: {e}[/]")

    # Display insights
    table = Table(title=f"Insights: {file.name}")
    table.add_column("Category", style="cyan")
    table.add_column("Count", style="green")

    table.add_row("Themes", str(len(insights.themes)))
    table.add_row("Patterns", str(len(insights.patterns)))
    table.add_row("Learnings", str(len(insights.learnings)))
    table.add_row("Concepts", str(len(insights.concepts)))
    table.add_row("Recommendations", str(len(insights.recommendations)))
    table.add_row("Chunks", str(insights.chunk_count))
    table.add_row("Words", str(insights.word_count))

    console.print(table)
    console.print(f"\n[dim]Processing time: {insights.processing_time_seconds:.2f}s[/]")


@app.command()
def classify(
    input_dir: Path = typer.Argument(..., help="Directory to classify"),
    output_dir: Path = typer.Option(None, "-o", "--output", help="Output directory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate without moving"),
):
    """Classify files into categories using the DAG pipeline."""
    from phantom.pipeline.phantom_dag import (
        PipelineContext,
        PhantomPipeline,
        SanitizationPolicy,
    )

    if not input_dir.exists() or not input_dir.is_dir():
        console.print(f"[red]Error: {input_dir} is not a valid directory[/]")
        raise typer.Exit(1)

    if output_dir is None:
        output_dir = input_dir.parent / f"{input_dir.name}_classified"

    staging_dir = output_dir / ".staging"
    quarantine_dir = output_dir / ".quarantine"

    console.print(f"[cyan]Classifying: {input_dir}[/]")
    console.print(f"[cyan]Output: {output_dir}[/]")
    if dry_run:
        console.print("[yellow]DRY RUN - no files will be moved[/]")

    ctx = PipelineContext(
        input_dir=input_dir,
        output_dir=output_dir,
        staging_dir=staging_dir,
        quarantine_dir=quarantine_dir,
        dry_run=dry_run,
        sanitization_policy=SanitizationPolicy.STRIP_METADATA,
    )

    pipeline = PhantomPipeline(ctx)
    pipeline.execute()

    console.print(f"[green]Classification complete: {ctx.processed} files processed[/]")
    if ctx.failed > 0:
        console.print(f"[red]{ctx.failed} files failed[/]")
    if ctx.quarantined > 0:
        console.print(f"[yellow]{ctx.quarantined} files quarantined[/]")


@app.command()
def scan(
    directory: Path = typer.Argument(".", help="Directory to scan"),
    strict: bool = typer.Option(
        False, "--strict", help="Exit with code 1 when findings are detected (CI gate mode)"
    ),
):
    """Scan for sensitive data patterns."""
    from phantom.pipeline.phantom_dag import ClassificationEngine

    directory = directory.resolve()
    if not directory.exists():
        console.print(f"[red]Error: {directory} does not exist[/]")
        raise typer.Exit(1)

    console.print(f"[cyan]Scanning: {directory}[/]")

    files = [f for f in directory.rglob("*") if f.is_file()]
    total_findings = 0

    table = Table(title="Sensitive Data Scan")
    table.add_column("File", style="cyan", max_width=50)
    table.add_column("Findings", style="red")
    table.add_column("Risk", style="yellow")

    for filepath in files:
        try:
            findings = ClassificationEngine.scan_sensitive_content(filepath)
            if findings:
                total_findings += len(findings)
                max_risk = max(f.risk_score for f in findings)
                patterns = ", ".join(f.pattern_name for f in findings)
                table.add_row(
                    str(filepath.relative_to(directory)),
                    patterns,
                    f"{max_risk:.2f}",
                )
        except Exception:
            pass

    if total_findings > 0:
        console.print(table)
        console.print(f"\n[red]Found {total_findings} sensitive pattern(s)[/]")
        if strict:
            raise typer.Exit(1)
    else:
        console.print("[green]No sensitive patterns detected[/]")


# RAG subcommands
rag_app = typer.Typer(help="RAG pipeline commands")
app.add_typer(rag_app, name="rag")


@rag_app.command("query")
def rag_query(
    question: str = typer.Argument(..., help="Question to ask"),
    collection: str = typer.Option(
        "default", "-c", "--collection", help="Collection name"
    ),
    top_k: int = typer.Option(5, "-k", "--top-k", help="Number of results"),
):
    """Query the RAG pipeline with semantic search."""
    from phantom.core.embeddings import EmbeddingGenerator
    from phantom.rag.vectors import FAISSVectorStore

    index_path = Path(f"data/index_{collection}.faiss")
    if not index_path.exists():
        console.print(
            f"[red]No index found for collection '{collection}'. "
            f"Run 'phantom rag ingest' first.[/]"
        )
        raise typer.Exit(1)

    embedder = EmbeddingGenerator()
    store = FAISSVectorStore.load(str(index_path))

    query_embedding = embedder.encode([question])[0]
    results = store.search(query_embedding, top_k=top_k)

    if not results:
        console.print("[yellow]No relevant results found[/]")
        raise typer.Exit(0)

    console.print(f"[cyan]Top {len(results)} results for:[/] {question}\n")

    for i, r in enumerate(results, 1):
        score_color = "green" if r.score > 0.7 else "yellow" if r.score > 0.4 else "red"
        console.print(f"[bold]{i}.[/] [{score_color}]Score: {r.score:.4f}[/]")
        console.print(f"   {r.text[:200]}{'...' if len(r.text) > 200 else ''}\n")


@rag_app.command("ingest")
def rag_ingest(
    directory: Path = typer.Argument(..., help="Directory to ingest"),
    collection: str = typer.Option(
        "default", "-c", "--collection", help="Collection name"
    ),
):
    """Ingest documents into RAG index."""
    from phantom.core.cortex import SemanticChunker
    from phantom.core.embeddings import EmbeddingGenerator
    from phantom.rag.vectors import FAISSVectorStore

    if not directory.exists():
        console.print(f"[red]Error: {directory} does not exist[/]")
        raise typer.Exit(1)

    files = sorted(
        f for f in directory.rglob("*")
        if f.is_file() and f.suffix in (".md", ".txt", ".rst", ".tex", ".py", ".js", ".ts")
    )

    if not files:
        console.print("[yellow]No ingestable files found[/]")
        raise typer.Exit(0)

    console.print(f"[cyan]Ingesting {len(files)} file(s) into collection '{collection}'[/]")

    chunker = SemanticChunker(max_tokens=1024, overlap=128)
    embedder = EmbeddingGenerator()
    store = FAISSVectorStore(embedding_dim=embedder.dimension)

    total_chunks = 0
    for filepath in files:
        try:
            content = filepath.read_text(encoding="utf-8")
            chunks = chunker.chunk_text(content, filepath.name)
            if not chunks:
                continue

            texts = [c.text for c in chunks]
            embeddings = embedder.encode(texts)
            metadata = [
                {"source": str(filepath), "chunk_id": c.chunk_id}
                for c in chunks
            ]
            store.add(embeddings, texts, metadata)
            total_chunks += len(chunks)
            console.print(f"  [green]{filepath.name}[/] -> {len(chunks)} chunks")
        except Exception as e:
            console.print(f"  [red]{filepath.name}: {e}[/]")

    index_path = Path(f"data/index_{collection}.faiss")
    index_path.parent.mkdir(parents=True, exist_ok=True)
    store.save(str(index_path))

    console.print(f"\n[green]Ingested {total_chunks} chunks -> {index_path}[/]")


# Tools subcommands
tools_app = typer.Typer(help="Utility tools")
app.add_typer(tools_app, name="tools")


@tools_app.command("vram")
def tools_vram(
    model: str | None = typer.Option(None, "-m", "--model", help="Model name"),
):
    """Calculate VRAM requirements for models."""
    from phantom.core.cortex import SystemMonitor

    monitor = SystemMonitor()
    vram = monitor.get_vram_usage()
    ram = monitor.get_ram_usage()

    table = Table(title="System Resources")
    table.add_column("Resource", style="cyan")
    table.add_column("Used", style="yellow")
    table.add_column("Total", style="green")

    if vram.get("available"):
        table.add_row(
            "VRAM",
            f"{vram['used_mb']} MB",
            f"{vram['total_mb']} MB",
        )
    else:
        table.add_row("VRAM", "N/A", "No GPU detected")

    table.add_row(
        "RAM",
        f"{ram['used_mb']} MB",
        f"{ram['total_mb']} MB",
    )

    console.print(table)

    if model:
        console.print(f"\n[dim]Model-specific estimates for '{model}' not yet available[/]")


@tools_app.command("prompt")
def tools_prompt():
    """Open the prompt workbench (interactive prompt testing)."""
    console.print("[cyan]Prompt Workbench[/]")
    console.print("Enter a prompt template with {variable} placeholders.")
    console.print("Type 'quit' to exit.\n")

    while True:
        template = console.input("[bold]Template:[/] ")
        if template.lower() in ("quit", "exit", "q"):
            break

        import re

        variables = re.findall(r"\{(\w+)\}", template)
        if not variables:
            console.print("[yellow]No variables found in template[/]")
            continue

        values = {}
        for var in variables:
            values[var] = console.input(f"  {var} = ")

        rendered = template
        for k, v in values.items():
            rendered = rendered.replace("{" + k + "}", v)

        console.print(f"\n[green]Rendered:[/] {rendered}")
        console.print(f"[dim]Approx tokens: {len(rendered) // 4}[/]\n")


@tools_app.command("audit")
def tools_audit(
    directory: Path = typer.Argument(".", help="Directory to audit"),
):
    """Audit a project directory for classification and sensitive data."""
    from phantom.pipeline.phantom_dag import ClassificationEngine

    directory = directory.resolve()
    if not directory.exists():
        console.print(f"[red]Error: {directory} does not exist[/]")
        raise typer.Exit(1)

    files = [f for f in directory.rglob("*") if f.is_file()]
    console.print(f"[cyan]Auditing {len(files)} file(s) in {directory}[/]\n")

    from collections import Counter

    classifications: Counter[str] = Counter()
    sensitive_count = 0

    for filepath in files:
        try:
            cls, mime, sensitivity = ClassificationEngine.classify(filepath)
            classifications[cls.value] += 1
            findings = ClassificationEngine.scan_sensitive_content(filepath)
            if findings:
                sensitive_count += 1
        except Exception:
            classifications["error"] += 1

    table = Table(title="Audit Summary")
    table.add_column("Classification", style="cyan")
    table.add_column("Count", style="green")

    for cls_name, count in classifications.most_common():
        table.add_row(cls_name, str(count))

    console.print(table)
    console.print(f"\n[bold]Total files:[/] {len(files)}")
    if sensitive_count:
        console.print(f"[red]Files with sensitive data: {sensitive_count}[/]")


# API subcommands
api_app = typer.Typer(help="API server commands")
app.add_typer(api_app, name="api")


@api_app.command("serve")
def api_serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind"),
    port: int = typer.Option(8000, "--port", help="Port to bind"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
):
    """Start the REST API server."""
    console.print(f"[cyan]🚀 Starting API server on {host}:{port}[/]")

    import uvicorn

    uvicorn.run(
        "phantom.api.app:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )


@app.command()
def version():
    """Show version information."""
    from phantom import __codename__, __version__

    console.print(f"[cyan]🔮 Phantom[/] v{__version__} ({__codename__})")


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
