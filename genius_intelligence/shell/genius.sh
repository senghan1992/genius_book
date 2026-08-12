#!/usr/bin/env bash
# =============================================================================
# Genius Intelligence - Shell Integration
# =============================================================================
# 이 스크립트를 소싱하면 지정된 코딩 어시스턴트 CLI만 자동으로 감싸집니다.
#
# 사용법:
#   . /path/to/genius_intelligence_shell.sh
#   # 또는 (권장)
#   eval "$(genius shell-init)"
#
# 기본으로 감싸지는 CLI: claude, omp, opencode, aider, codex, cursor 등
#
# 중요한 설계 원칙:
#   이 스크립트는 절대로 "python3 -m ..." 같이 파이썬 인터프리터를 직접
#   추측해서 호출하지 않습니다. 오직 `genius` 명령(PATH에 있는 것)에만
#   위임합니다. 이유: install.sh 는 사용자가 고른 방식(전역/venv/pipx/user)에
#   따라 genius_intelligence 패키지를 서로 다른 파이썬 환경에 설치하지만,
#   어떤 방식이든 항상 `genius` 실행 파일 하나는 PATH에서 올바르게 그
#   환경을 가리키도록 보장합니다 (venv는 래퍼 스크립트, pipx는 자체 shim 등).
#   만약 여기서 시스템 python3를 직접 불렀다면, venv/pipx로 격리 설치한
#   경우 시스템 python3에는 패키지가 없어서 ModuleNotFoundError로 깨집니다.
#
# 주의: 이 스크립트는 배열, [[ ]], bash completion 등 bash/zsh 전용 기능을
# 사용합니다. 순수 POSIX sh/dash 대화형 셸(예: 일부 배포판의 기본 로그인 셸)
# 에서는 아래 가드에서 조용히 아무 것도 하지 않고 종료합니다 (에러 없이).
# 자동 CLI 래핑 기능을 쓰려면 bash 또는 zsh 를 사용해주세요.
# =============================================================================

if [ -z "${BASH_VERSION:-}" ] && [ -z "${ZSH_VERSION:-}" ]; then
    return 0 2>/dev/null || exit 0
fi

# genius 실행 파일이 PATH에 없으면 아무 것도 하지 않고 조용히 종료
# (설치가 덜 됐거나, PATH 갱신 전 상태일 수 있음. 에러로 셸을 방해하지 않음)
if ! command -v genius >/dev/null 2>&1; then
    return 0 2>/dev/null || exit 0
fi

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

# 지원 CLI만 감싸기 (항상 `genius wrap` 명령에 위임)
genius_wrap() {
    local cmd="$1"
    shift

    if ! genius_is_supported "$cmd"; then
        echo "[genius] Skipping: '$cmd' is not in supported CLIs" >&2
        echo "[genius] Use 'genius-run $cmd ...' to force wrapping" >&2
        command "$cmd" "$@"
        return $?
    fi

    # .genius_intelligence 폴더가 없으면 감싸지 않고 원본 실행
    if [ ! -d ".genius_intelligence" ]; then
        echo "[genius] 프로젝트가 초기화되지 않았습니다. 'genius init'을 먼저 실행하세요." >&2
        echo "[genius] CLI를 감싸지 않고 그대로 실행합니다." >&2
        command "$cmd" "$@"
        return $?
    fi

    genius_log "Wrapping: $cmd $*"

    genius wrap "$cmd" -- "$@"
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
# 유틸리티 (모두 `genius` 실행 파일에 위임 - 설치 방식과 무관하게 항상 동작)
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

    echo "[genius] Force wrapping: $cmd $*" >&2
    genius wrap --force "$cmd" -- "$@"
    return $?
}

genius-status() {
    genius status
}

genius-search() {
    genius search "$@"
}

genius-tree() {
    genius tree
}

genius-cleanup() {
    genius cleanup "$@"
}

genius-init() {
    genius init
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
