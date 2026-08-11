"""
CLI - genius 명령어
===================
"""
import sys
import json
from pathlib import Path

try:
    import click
    HAS_CLICK = True
except ImportError:
    HAS_CLICK = False

from ..core.manager import GeniusIntelligence
from ..utils.helpers import format_tree, pretty_print_stats, setup_logging


@click.group()
@click.option("--project", "-p", default=None, help="프로젝트 경로")
@click.option("--verbose", "-v", is_flag=True, help="상세 출력")
@click.pass_context
def cli(ctx, project, verbose):
    ctx.ensure_object(dict)
    setup_logging("DEBUG" if verbose else "INFO")
    if project is None:
        project = GeniusIntelligence.find_project_root() or "."
    ctx.obj["project"] = project
    ctx.obj["genius"] = GeniusIntelligence.for_current_project(project)


@cli.command()
def status():
    genius = GeniusIntelligence.for_current_project()
    if genius is None:
        click.echo("Error: Genius Intelligence 프로젝트가 아닙니다.")
        sys.exit(1)
    stats = genius.get_stats()
    pretty_print_stats(stats)


@cli.command()
@click.argument("query")
@click.option("--limit", "-n", default=5, help="결과 개수")
def search(query, limit):
    genius = GeniusIntelligence.for_current_project()
    if genius is None:
        click.echo("Error: Genius Intelligence 프로젝트가 아닙니다.")
        sys.exit(1)
    results = genius.search_knowledge(query, limit=limit)
    if not results:
        click.echo(f"'{query}' 관련 지식이 없습니다.")
        return
    click.echo(f"\n SEARCH: {len(results)} results:\n")
    for i, node in enumerate(results, 1):
        click.echo(f"  {i}. [{node.knowledge_type.value}] {node.name}")
        click.echo(f"     Domain: {node.domain} | Attempts: {node.attempt_count}")


@cli.command()
def tree():
    genius = GeniusIntelligence.for_current_project()
    if genius is None:
        click.echo("Error: Genius Intelligence 프로젝트가 아닙니다.")
        sys.exit(1)
    tree = genius.get_tree()
    output = format_tree(tree)
    click.echo(f"\n{genius.config.genius_dir_name}/")
    click.echo(output)


@cli.command()
@click.option("--days", default=None, type=int, help="미사용 일수")
@click.option("--dry-run", is_flag=True, help="실행 없이 미리보기")
def cleanup(days, dry_run):
    genius = GeniusIntelligence.for_current_project()
    if genius is None:
        click.echo("Error: Genius Intelligence 프로젝트가 아닙니다.")
        sys.exit(1)
    if days is None:
        days = genius.config.stale_days
    if dry_run:
        stale = genius.db.get_stale_nodes(days)
        click.echo(f"\nCleanup target: {len(stale)} nodes")
        return
    result = genius.cleaner.cleanup(max_days=days)
    click.echo(f"\nCleanup done: {result['deleted']} nodes deleted")


@cli.command()
@click.option("--force", is_flag=True, help="강제 초기화")
def init(force):
    project = Path.cwd()
    genius_dir = project / ".genius_intelligence"
    if genius_dir.exists() and not force:
        click.echo("Already initialized. Use --force to reinitialize.")
        sys.exit(1)
    genius = GeniusIntelligence.for_current_project(str(project))
    click.echo(f"Initialized: {genius_dir}")


@cli.command()
@click.argument("task_description")
@click.option("--domain", "-d", default=None, help="도메인")
@click.option("--tag", "-t", multiple=True, help="태그")
def add(task_description, domain, tag):
    from ..types.knowledge import KnowledgeNode, KnowledgeType, KnowledgeDomain
    genius = GeniusIntelligence.for_current_project()
    if genius is None:
        click.echo("Error: Genius Intelligence 프로젝트가 아닙니다.")
        sys.exit(1)
    if domain is None:
        domain = KnowledgeDomain.detect_domain(task_description, genius.config.custom_domains)
    topic = genius._extract_topic(task_description)
    node = KnowledgeNode(
        name=topic or task_description[:50],
        domain=domain,
        topic=topic,
        depth=2 if topic else 1,
        knowledge_type=KnowledgeType.BEST_PRACTICE,
        description=task_description,
        raw_input=task_description,
        tags=list(tag),
    )
    genius.graph.add_node(node)
    path = genius.store.save_node(node, genius.db)
    click.echo(f"Knowledge added: {path}")


@cli.command()
def stats():
    genius = GeniusIntelligence.for_current_project()
    if genius is None:
        click.echo("Error: Genius Intelligence 프로젝트가 아닙니다.")
        sys.exit(1)
    all_stats = genius.db.get_stats()
    cleaner_stats = genius.cleaner.get_cleanup_stats()
    click.echo("\n=== Genius Intelligence Stats ===")
    click.echo(f"Active nodes: {all_stats['total_active_nodes']}")
    click.echo(f"Sessions: {all_stats['total_sessions']}")
    click.echo(f"Login info: {all_stats['total_login_info']}")
    click.echo(f"Stale nodes: {cleaner_stats['stale_nodes_count']}")


@cli.command()
def integrate():
    genius = GeniusIntelligence.for_current_project()
    if genius is None:
        click.echo("Error: Genius Intelligence 프로젝트가 아닙니다.")
        sys.exit(1)
    from ..hooks.adapter import HookAdapter
    adapter = HookAdapter.auto_detect()
    if adapter is None:
        click.echo("Error: 호환되는 CLI 도구를 찾을 수 없습니다.")
        sys.exit(1)
    if adapter.install():
        click.echo(f"Hooks installed for {adapter.name}")
    else:
        click.echo(f"Hook installation failed")




@cli.command()
@click.argument("cli_tool")
@click.argument("args", nargs=-1)
@click.option("--project", "-p", default=None, help="프로젝트 경로")
def wrap(cli_tool, args, project):
    """코딩 어시스턴트 CLI를 Genius Intelligence와 함께 실행

    예시:
        genius wrap claude --no-input
        genius wrap omp --project .
        genius wrap aider main.py
    """
    from ..auto.wrapper import wrap_cli
    import os

    if project is None:
        from ..core.manager import GeniusIntelligence
        project = GeniusIntelligence.find_project_root() or "."

    cmd = [cli_tool] + list(args)
    sys.exit(wrap_cli(cmd, project_root=project))


@cli.command()
def shell_init():
    """Bash 셸 통합 스크립트 출력

    사용법:
        eval "$(genius shell-init)"
    """
    import os
    shell_script = Path(__file__).parent.parent / "shell" / "genius.sh"
    if shell_script.exists():
        script_path = str(shell_script)
        print("# Genius Intelligence Shell Integration")
        print(f"source {script_path}")
    else:
        click.echo("Error: Shell script not found", err=True)
        sys.exit(1)


def main():
    if not HAS_CLICK:
        print("Error: click is needed. pip install genius-intelligence[cli]")
        sys.exit(1)
    cli(obj={})


if __name__ == "__main__":
    main()
