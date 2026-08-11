#!/bin/sh
# =============================================================================
# Genius Intelligence - Installer
# =============================================================================
# POSIX sh 호환 스크립트입니다. bash, dash, zsh, ash(alpine) 등에서 모두
# 동작하도록 [[ ]], =~, 배열, read -p/-n, &> 등 bash 전용 문법을 사용하지 않습니다.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/senghan1992/genius_book/main/install.sh | sh
#   curl -fsSL https://raw.githubusercontent.com/senghan1992/genius_book/main/install.sh | sh -s -- --help
#   curl -fsSL https://raw.githubusercontent.com/senghan1992/genius_book/main/install.sh | sh -s -- --uninstall
# =============================================================================

set -e

GENIUS_VERSION="0.1.0"
GENIUS_REPO="senghan1992/genius_book"
INSTALL_URL="https://raw.githubusercontent.com/${GENIUS_REPO}/main/install.sh"

# 색상 (printf %b 로 해석되는 이스케이프. 터미널이 아니면 무해하게 출력됨)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    printf "%b[genius]%b %s\n" "$BLUE" "$NC" "$1"
}

log_success() {
    printf "%b[genius]%b %s\n" "$GREEN" "$NC" "$1"
}

log_warn() {
    printf "%b[genius]%b %s\n" "$YELLOW" "$NC" "$1"
}

log_error() {
    printf "%b[genius]%b %s\n" "$RED" "$NC" "$1" >&2
}

show_help() {
    cat << EOF
Genius Intelligence Installer

사용법:
    curl -fsSL https://raw.githubusercontent.com/${GENIUS_REPO}/main/install.sh | sh
    curl -fsSL https://raw.githubusercontent.com/${GENIUS_REPO}/main/install.sh | sh -s -- --help
    curl -fsSL https://raw.githubusercontent.com/${GENIUS_REPO}/main/install.sh | sh -s -- --uninstall

옵션:
    --help          이 도움말 표시
    --uninstall     설치 제거
    --update        업데이트
    --shell-only    셸 통합만 설치 (pip 설치 건너뛰기)
    --yes           모든 질문에 yes (비대화형/CI 환경 권장)

예시:
    # 기본 설치
    curl -fsSL https://raw.githubusercontent.com/${GENIUS_REPO}/main/install.sh | sh

    # 비대화형 설치 (CI 등, 질문 없이 진행)
    curl -fsSL https://raw.githubusercontent.com/${GENIUS_REPO}/main/install.sh | sh -s -- --yes

    # 제거
    curl -fsSL https://raw.githubusercontent.com/${GENIUS_REPO}/main/install.sh | sh -s -- --uninstall
EOF
}

# =============================================================================
# 설치 함수
# =============================================================================

check_requirements() {
    log_info "Requirements 체크 중..."

    if command -v python3 >/dev/null 2>&1; then
        PYTHON_CMD="python3"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_CMD="python"
    else
        log_error "Python3가 설치되어 있지 않습니다."
        log_info "Python3 설치: https://www.python.org/downloads/"
        exit 1
    fi

    PYTHON_VERSION=$("$PYTHON_CMD" --version 2>&1 | cut -d' ' -f2)

    # bc 등 외부 도구 없이 파이썬 자체로 버전 체크 (3.10 이상 요구)
    if ! "$PYTHON_CMD" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        log_error "Python 3.10 이상이 필요합니다. 현재: $PYTHON_VERSION"
        exit 1
    fi

    log_success "Python $PYTHON_VERSION ✓"

    if ! "$PYTHON_CMD" -m pip --version >/dev/null 2>&1; then
        log_info "pip 설치 중..."
        if ! "$PYTHON_CMD" -m ensurepip --upgrade >/dev/null 2>&1; then
            log_error "pip 설치 실패"
            exit 1
        fi
    fi

    log_success "pip ✓"

    if command -v git >/dev/null 2>&1; then
        log_success "git ✓"
    else
        log_warn "git가 설치되어 있지 않습니다 (선택사항)"
    fi
}

install_pip() {
    log_info "genius-intelligence 설치 중..."

    if [ -z "$VIRTUAL_ENV" ]; then
        log_warn "가상환경이 아닙니다. 설치 권장: python3 -m venv venv && . venv/bin/activate"
        if [ "${GENIUS_SKIP_VENV_CHECK:-0}" != "1" ]; then
            printf "계속 진행하시겠습니까? (y/N) "
            # 파이프로 실행되는 경우(curl ... | sh) 표준입력이 이미 스크립트
            # 내용으로 채워져 있을 수 있으므로, 터미널에서 직접 응답을 받으려면
            # /dev/tty 에서 읽습니다. 실패하면(비대화형 환경) 기본값 N으로 취급.
            if [ -t 0 ]; then
                read -r REPLY
            elif [ -r /dev/tty ]; then
                read -r REPLY < /dev/tty
            else
                REPLY=""
            fi
            case "$REPLY" in
                [Yy]*) ;;
                *)
                    log_info "설치 취소됨. 비대화형 설치가 필요하면 --yes 옵션을 사용하세요."
                    exit 0
                    ;;
            esac
        fi
    fi

    "$PYTHON_CMD" -m pip install --upgrade pip
    "$PYTHON_CMD" -m pip install "genius-intelligence[cli]"

    log_success "genius-intelligence 설치 완료!"
}

install_shell_integration() {
    log_info "셸 통합 설치 중..."

    if [ -n "$ZSH_VERSION" ]; then
        SHELL_RC="$HOME/.zshrc"
    elif [ -n "$BASH_VERSION" ]; then
        SHELL_RC="$HOME/.bashrc"
    else
        SHELL_RC="$HOME/.profile"
    fi

    GENIUS_INTEGRATION_LINE='[ -f "$(python3 -c "import genius_intelligence, os; print(os.path.dirname(genius_intelligence.__file__))" 2>/dev/null)/shell/genius.sh" ] && . "$(python3 -c "import genius_intelligence, os; print(os.path.dirname(genius_intelligence.__file__))" 2>/dev/null)/shell/genius.sh"'

    if [ -f "$SHELL_RC" ] && grep -q "genius.sh" "$SHELL_RC" 2>/dev/null; then
        log_success "셸 통합이 이미 설치되어 있습니다 ($SHELL_RC)"
    else
        printf "\n# Genius Intelligence\n%s\n" "$GENIUS_INTEGRATION_LINE" >> "$SHELL_RC"
        log_success "셸 통합 설치 완료! ($SHELL_RC)"
        log_info "셸을 재시작하거나 '. $SHELL_RC' 를 실행하세요"
    fi

    log_info "설치 확인: python3 -c 'import genius_intelligence'"
}

verify_installation() {
    log_info "설치 확인 중..."

    if "$PYTHON_CMD" -c "import genius_intelligence" 2>/dev/null; then
        log_success "Python 모듈 ✓"
    else
        log_error "Python 모듈 확인 실패"
        exit 1
    fi

    if command -v genius >/dev/null 2>&1; then
        log_success "CLI 설치 ✓"
    elif "$PYTHON_CMD" -m genius_intelligence.cli.main --help >/dev/null 2>&1; then
        log_success "CLI 설치 ✓ (python -m)"
    else
        log_warn "CLI를 직접 실행하려면 PATH에 추가하거나 'pip install -e .' 하세요"
    fi
}

show_next_steps() {
    printf "\n"
    echo "============================================================"
    echo "  설치 완료! 🎉"
    echo "============================================================"
    printf "\n"
    echo "  다음 단계:"
    printf "\n"
    echo "  1. 셸을 재시작하거나:"
    echo "     . $SHELL_RC"
    printf "\n"
    echo "  2. 코딩 어시스턴트 실행:"
    echo "     claude --no-input"
    echo "     # 또는"
    echo "     omp"
    printf "\n"
    echo "  3. 상태 확인:"
    echo "     genius-status"
    printf "\n"
    echo "  4. 지원 명령어:"
    echo "     genius-status     # 상태"
    echo "     genius-search     # 검색"
    echo "     genius-tree       # 트리"
    echo "     genius-cleanup    # 정리"
    printf "\n"
    echo "============================================================"
    printf "\n"
}

# =============================================================================
# 제거 함수
# =============================================================================

uninstall() {
    log_warn "Genius Intelligence 제거..."

    if command -v python3 >/dev/null 2>&1; then
        PY_UNINSTALL_CMD="python3"
    else
        PY_UNINSTALL_CMD="python"
    fi

    if "$PY_UNINSTALL_CMD" -m pip show genius-intelligence >/dev/null 2>&1; then
        "$PY_UNINSTALL_CMD" -m pip uninstall -y genius-intelligence
        log_success "pip 패키지 제거 완료"
    fi

    for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
        if [ -f "$rc" ] && grep -q "genius.sh" "$rc" 2>/dev/null; then
            sed -i.bak '/# Genius Intelligence/d' "$rc" 2>/dev/null || sed -i '' '/# Genius Intelligence/d' "$rc"
            sed -i.bak '/genius.sh/d' "$rc" 2>/dev/null || sed -i '' '/genius.sh/d' "$rc"
            rm -f "${rc}.bak"
            log_success "셸 통합 제거: $rc"
        fi
    done

    log_success "제거 완료!"
}

# =============================================================================
# 메인
# =============================================================================

SKIP_PIP=0
UNINSTALL_MODE=0
UPDATE_MODE=0

while [ $# -gt 0 ]; do
    case "$1" in
        --help|-h)
            show_help
            exit 0
            ;;
        --uninstall)
            UNINSTALL_MODE=1
            shift
            ;;
        --update)
            UPDATE_MODE=1
            shift
            ;;
        --shell-only)
            SKIP_PIP=1
            shift
            ;;
        --yes|-y)
            GENIUS_SKIP_VENV_CHECK=1
            export GENIUS_SKIP_VENV_CHECK
            shift
            ;;
        *)
            log_error "알 수 없는 옵션: $1"
            show_help
            exit 1
            ;;
    esac
done

printf "\n"
echo "============================================================"
echo "  Genius Intelligence Installer v${GENIUS_VERSION}"
echo "============================================================"
printf "\n"

if [ "$UNINSTALL_MODE" -eq 1 ]; then
    uninstall
    exit 0
fi

if [ "$UPDATE_MODE" -eq 1 ]; then
    log_info "업데이트 중..."
    if command -v python3 >/dev/null 2>&1; then
        python3 -m pip install --upgrade "genius-intelligence[cli]"
    else
        python -m pip install --upgrade "genius-intelligence[cli]"
    fi
    log_success "업데이트 완료!"
    exit 0
fi

if [ "$SKIP_PIP" -eq 0 ]; then
    check_requirements
    install_pip
fi

install_shell_integration
verify_installation
show_next_steps
