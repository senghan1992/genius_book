"""
CLI - genius 명령어
===================
"""
import subprocess
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
    """
    genius CLI 그룹 콜백

    주의: 여기서는 GeniusIntelligence 전체 인스턴스를 미리 만들지 않습니다.
    `shell-init`, `--help` 같은 순수 정적 명령까지 매번 DB 연결/플랜 감시
    스레드를 켜는 부작용이 생기고, 로그가 stdout에 섞여 `eval "$(genius
    shell-init)"` 같은 셸 통합이 깨질 수 있기 때문입니다. 프로젝트 경로만
    저장해두고, 실제로 필요한 서브커맨드에서 각자 초기화합니다.
    """
    ctx.ensure_object(dict)
    setup_logging("DEBUG" if verbose else "INFO")
    ctx.obj["project"] = project


def _require_genius(project=None):
    """초기화된 GeniusIntelligence 인스턴스 반환 또는 에러 종료.

    .genius_intelligence 폴더가 없으면 'genius init' 안내 후 종료.
    """
    genius = GeniusIntelligence.for_current_project(project)
    if genius is None:
        click.echo("Error: 이 프로젝트는 초기화되지 않았습니다.")
        click.echo("먼저 'genius init'을 실행하세요.")
        sys.exit(1)
    return genius


@cli.command()
def status():
    genius = _require_genius()
    stats = genius.get_stats()
    pretty_print_stats(stats)


@cli.command()
@click.argument("query")
@click.option("--limit", "-n", default=5, help="결과 개수")
def search(query, limit):
    genius = _require_genius()
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
    genius = _require_genius()
    tree = genius.get_tree()
    output = format_tree(tree)
    click.echo(f"\n{genius.config.genius_dir_name}/")
    click.echo(output)


@cli.command()
@click.option("--days", default=None, type=int, help="미사용 일수")
@click.option("--dry-run", is_flag=True, help="실행 없이 미리보기")
def cleanup(days, dry_run):
    genius = _require_genius()
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
    # init은 for_current_project가 아닌 직접 생성자로 초기화.
    # for_current_project는 .genius_intelligence 폴더가 없으면 None을 반환하므로.
    genius = GeniusIntelligence(str(project), auto_init=True)
    click.echo(f"Initialized: {genius_dir}")


@cli.command()
@click.argument("task_description")
@click.option("--domain", "-d", default=None, help="도메인")
@click.option("--tag", "-t", multiple=True, help="태그")
def add(task_description, domain, tag):
    from ..types.knowledge import KnowledgeNode, KnowledgeType, KnowledgeDomain
    genius = _require_genius()
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
    genius = _require_genius()
    all_stats = genius.db.get_stats()
    cleaner_stats = genius.cleaner.get_cleanup_stats()

    # B3: 피드백 루프 헬스 메트릭
    knowledge_searched = genius.db.get_usage_count("read")
    failure_knowledge = sum(
        1 for n in genius.graph.nodes.values()
        if n.fail_count > 0
    )

    click.echo("\n=== Genius Intelligence Stats ===")
    click.echo(f"Active nodes: {all_stats['total_active_nodes']}")
    click.echo(f"Sessions: {all_stats['total_sessions']}")
    click.echo(f"Login info: {all_stats['total_login_info']}")
    click.echo(f"Stale nodes: {cleaner_stats['stale_nodes_count']}")
    click.echo(f"\n--- Feedback Loop ---")
    click.echo(f"Knowledge searched/injected: {knowledge_searched}")
    click.echo(f"Failure knowledge nodes: {failure_knowledge}")


@cli.command()
def integrate():
    genius = _require_genius()
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
@click.option("--force", "-f", is_flag=True,
              help="지원 목록에 없는 CLI도 강제로 감싸기")
def wrap(cli_tool, args, project, force):
    """코딩 어시스턴트 CLI를 Genius Intelligence와 함께 실행

    이 명령은 install.sh 가 어떤 방식으로 설치했든(global/venv/pipx/user)
    항상 올바른 파이썬 인터프리터로 실행되도록 보장되는 유일한 진입점입니다.
    셸 통합 스크립트(genius.sh)는 반드시 이 명령을 통해서만 CLI를 감싸며,
    "python3 -m ..." 같이 시스템 파이썬을 직접 추측해서 호출하지 않습니다.
    (venv/pipx로 격리 설치한 경우 시스템 파이썬에는 패키지가 없어서
    직접 호출하면 ModuleNotFoundError로 깨지기 때문입니다.)

    예시:
        genius wrap claude --no-input
        genius wrap omp --project .
        genius wrap aider main.py
        genius wrap --force some-unlisted-cli
    """
    from ..auto.universal import UniversalWrapper
    from ..core.manager import GeniusIntelligence

    if project is None:
        project = GeniusIntelligence.find_project_root() or "."

    supported_clis = None
    if force:
        supported_clis = UniversalWrapper.DEFAULT_SUPPORTED_CLIS | {cli_tool}

    wrapper = UniversalWrapper(project, supported_clis=supported_clis)

    # 초기화되지 않은 프로젝트면 경고 후 그냥 CLI 실행
    if not wrapper.genius or not wrapper.genius._genius_initialized:
        print(f"[genius] 이 프로젝트는 초기화되지 않았습니다. "
              f"'genius init'을 먼저 실행하세요.", file=sys.stderr)
        print(f"[genius] CLI를 감싸지 않고 그대로 실행합니다.", file=sys.stderr)
        cmd = [cli_tool] + list(args)
        sys.exit(subprocess.run(cmd).returncode)

    # B2: 세션 시작 시 컨텍스트 파일 자동 갱신
    try:
        from ..context import write_context_file
        genius_inst = wrapper.genius
        context_path = write_context_file(genius_inst, limit=10)
        if context_path:
            print(f"[genius] Context: {context_path}", file=sys.stderr)
            print(f"[genius] Include @.genius_intelligence/context.md in your CLAUDE.md / context file.", file=sys.stderr)
    except Exception as e:
        print(f"[genius] Context generation skipped: {e}", file=sys.stderr)

    cmd = [cli_tool] + list(args)
    sys.exit(wrapper.run(cmd))


@cli.command()
@click.argument("query", required=False, default="")
@click.option("--limit", "-n", default=10, help="결과 개수")
@click.option("--write", "-w", is_flag=True, help="context.md 파일로 쓰기")
def context(query, limit, write):
    """저장된 지식을 마크다운 컨텍스트로 출력 (주입 가능)

    stdout으로 마크다운을 출력. shell-init처럼 로그를 섞지 않는다.
    빈 결과면 아무것도 출력하지 않는다.
    """
    from ..context import render_knowledge_context, write_context_file
    genius = _require_genius()

    if write:
        path = write_context_file(genius, query, limit)
        if path:
            click.echo(f"Context written: {path}")
        else:
            click.echo("No knowledge to write.")
        return

    md = render_knowledge_context(genius, query, limit)
    if md:
        click.echo(md)


def shell_init():
    """셸 통합 스니펫 출력 (POSIX sh/dash/bash/zsh 모두 호환)

    사용법:
        eval "$(genius shell-init)"

    주의: 이 명령의 출력은 stdout으로만 나가야 하며, eval로 그대로
    실행되므로 절대 로그/진단 메시지를 여기서 print 하지 마세요.
    또한 "source"는 bash/zsh 전용이라 dash 등에서 실패하므로
    POSIX 표준 "." (dot) 커맨드를 사용합니다.
    """
    shell_script = Path(__file__).parent.parent / "shell" / "genius.sh"
    if shell_script.exists():
        script_path = str(shell_script)
        print("# Genius Intelligence Shell Integration")
        print(f'. "{script_path}"')
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
