#!/usr/bin/env bash
# =============================================================================
# Genius Intelligence - Shell Integration
# =============================================================================
# 이 스크립트를 소싱하면 지정된 코딩 어시스턴트 CLI만 자동으로 감싸집니다.
#
# 사용법:
#   . /path/to/genius_intelligence_shell.sh
#   # 또는
#   eval "$(genius shell-init)"
#
# 기본으로 감싸지는 CLI: claude, omp, opencode, aider, codex, cursor 등
#
# 주의: 이 스크립트는 배열, [[ ]], bash completion 등 bash/zsh 전용 기능을
# 사용합니다. 순수 POSIX sh/dash 대화형 셸(예: 일부 배포판의 기본 로그인 셸)
# 에서는 아래 가드에서 조용히 아무 것도 하지 않고 종료합니다 (에러 없이).
# 자동 CLI 래핑 기능을 쓰려면 bash 또는 zsh 를 사용해주세요.
# =============================================================================

if [ -z "${BASH_VERSION:-}" ] && [ -z "${ZSH_VERSION:-}" ]; then
    return 0 2>/dev/null || exit 0
fi

set -e

if command -v python3 >/dev/null 2>&1; then
    _GENIUS_PY="python3"
elif command -v python >/dev/null 2>&1; then
    _GENIUS_PY="python"
else
    return 0 2>/dev/null || exit 0
fi

_GENIUS_ROOT="${GENIUS_INTELLIGENCE_ROOT:-$($_GENIUS_PY -c 'import genius_intelligence; import os; print(os.path.dirname(genius_intelligence.__file__))' 2>/dev/null || echo '')}"

# =============================================================================
# 지원 CLI 목록 (이 목록에 있는 CLI만 감싸짐)
# =============================================================================

_SUPPORTED_CLIS=(
    # Claude
    claude claude-code claude-code-bin
    # OMP
    omp
    # OpenCode
    opencode opencode-cli
    # Aider
    aider aider-chat
    # Codex
    codex openai-codex
    # Cursor
    cursor cursor-ai
    # Copilot
    copilot github-copilot
    # 기타 AI CLI
    llm llm-cli mistral gemini-cli ollama
    # 코딩 어시스턴트
    devin devin-cli swe-agent autogpt auto-gpt gptme continue zed windsurf
)

# CLI가 지원 목록에 있는지 확인
genius_is_supported() {
    local cmd="$1"
    for supported in "${_SUPPORTED_CLIS[@]}"; do
        if [[ "$cmd" == "$supported" ]]; then
            return 0
        fi
    done
    return 1
}

# =============================================================================
# 내부 함수
# =============================================================================

genius_log() {
    if [[ "${GENIUS_DEBUG:-0}" == "1" ]]; then
        echo "[genius] $*" >&2
    fi
}

# 지원 CLI만 감싸기
genius_wrap() {
    local cmd="$1"
    shift

    # 지원 목록 체크
    if ! genius_is_supported "$cmd"; then
        echo "[genius] Skipping: '$cmd' is not in supported CLIs" >&2
        echo "[genius] Use 'genius run <cmd>' to force wrapping" >&2
        # 그냥 일반 명령으로 실행
        "$cmd" "$@"
        return $?
    fi

    genius_log "Wrapping: $cmd $@"

    $_GENIUS_PY -m genius_intelligence.auto.universal "$cmd" "$@"
    return $?
}

# =============================================================================
# CLI 래핑 (지원 목록에 있는 것만)
# =============================================================================

# Claude
claude() {
    genius_wrap claude "$@"
}

# OMP
omp() {
    genius_wrap omp "$@"
}

# OpenCode
opencode() {
    genius_wrap opencode "$@"
}

# Aider
aider() {
    genius_wrap aider "$@"
}

# Codex
codex() {
    genius_wrap codex "$@"
}

# Cursor
cursor() {
    genius_wrap cursor "$@"
}

# Copilot
copilot() {
    genius_wrap copilot "$@"
}

# 기타 AI CLI
llm() {
    genius_wrap llm "$@"
}

ollama() {
    genius_wrap ollama "$@"
}

# Continue.dev
continue() {
    genius_wrap continue "$@"
}

# =============================================================================
# 유틸리티
# =============================================================================

# 지원 CLI 목록 보기
genius-supported() {
    echo "Supported CLIs:"
    echo "==============="
    for cli in "${_SUPPORTED_CLIS[@]}"; do
        echo "  - $cli"
    done
}

# 강제 래핑 (지원 목록에 없어도)
genius-run() {
    local cmd="$1"
    shift

    if [[ -z "$cmd" ]]; then
        echo "Usage: genius-run <cli> [args...]" >&2
        echo "Force wrapping any CLI with Genius Intelligence" >&2
        return 1
    fi

    echo "[genius] Force wrapping: $cmd $@" >&2
    $_GENIUS_PY -m genius_intelligence.auto.universal "$cmd" "$@"
    return $?
}

# 상태 확인
genius-status() {
    $_GENIUS_PY -c "
from genius_intelligence import GeniusIntelligence
genius = GeniusIntelligence.for_current_project()
stats = genius.get_stats()
print('Genius Intelligence Status')
print('=' * 40)
print(f'Project: {genius.project_root}')
print(f'Active Nodes: {stats.get(\"total_active_nodes\", 0)}')
print(f'Sessions: {stats.get(\"total_sessions\", 0)}')
"
}

# 검색
genius-search() {
    $_GENIUS_PY -c "
import sys
from genius_intelligence import GeniusIntelligence
query = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else ''
genius = GeniusIntelligence.for_current_project()
if not query:
    print('Usage: genius-search <query>')
    sys.exit(1)
results = genius.search_knowledge(query, limit=5)
if not results:
    print(f'No results for: {query}')
else:
    print(f'Results for: {query}')
    for node in results:
        print(f'  [{node.knowledge_type.value}] {node.name} - {node.domain}')
" "$@"
}

# 트리
genius-tree() {
    $_GENIUS_PY -c "
from genius_intelligence import GeniusIntelligence
from genius_intelligence.utils.helpers import format_tree
genius = GeniusIntelligence.for_current_project()
print(format_tree(tree))
" 2>/dev/null || $_GENIUS_PY -c "
from genius_intelligence import GeniusIntelligence
genius = GeniusIntelligence.for_current_project()
tree = genius.get_tree()
from genius_intelligence.utils.helpers import format_tree
print(format_tree(tree))
"
}

# 정리
genius-cleanup() {
    $_GENIUS_PY -c "
from genius_intelligence import GeniusIntelligence
genius = GeniusIntelligence.for_current_project()
result = genius.cleaner.cleanup()
print(f'Cleaned up {result[\"deleted\"]} nodes')
"
}

# 초기화
genius-init() {
    $_GENIUS_PY -c "
from genius_intelligence import GeniusIntelligence
genius = GeniusIntelligence.for_current_project()
print(f'Initialized: {genius.project_root}')
print(f'Knowledge dir: {genius.config.genius_dir_name}')
"
}

# =============================================================================
# Bash Completion
# =============================================================================

_genius_complete() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    COMPREPLY=($(compgen -W "status search tree cleanup init supported run help" -- ${cur}))
}

complete -F _genius_complete genius-status
complete -F _genius_complete genius-search
complete -F _genius_complete genius-tree
complete -F _genius_complete genius-cleanup
complete -F _genius_complete genius-init
complete -F _genius_complete genius-supported
complete -F _genius_complete genius-run

# =============================================================================
# 시작 메시지
# =============================================================================

if [[ "${GENIUS_QUIET:-0}" != "1" ]]; then
    echo "[genius] Genius Intelligence shell integration loaded"
    echo "[genius] Supported CLIs: ${#_SUPPORTED_CLIS[@]} tools"
    echo "[genius] Commands: genius-status, genius-search, genius-tree, genius-cleanup"
    echo "[genius] Use 'genius-run <cmd>' for unsupported CLIs"
    echo "[genius] Use 'genius-supported' to list all supported CLIs"
fi
