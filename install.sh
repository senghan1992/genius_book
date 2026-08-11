#!/usr/bin/env bash
# =============================================================================
# Genius Intelligence - Installer
# =============================================================================
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/senghan1992/genius_book/main/install.sh | sh
#   # 또는
#   curl -fsSL https://your-domain.com/install.sh | sh
# =============================================================================

set -e

GENIUS_VERSION="0.1.0"
GENIUS_REPO="senghan1992/genius_book"
INSTALL_URL="https://raw.githubusercontent.com/${GENIUS_REPO}/main/install.sh"

# 색상
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로그 함수
log_info() {
    echo -e "${BLUE}[genius]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[genius]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[genius]${NC} $1"
}

log_error() {
    echo -e "${RED}[genius]${NC} $1" >&2
}

# 도움말
show_help() {
    cat << EOF
Genius Intelligence Installer

사용법:
    curl -fsSL https://raw.githubusercontent.com/senghan1992/genius_book/main/install.sh | sh
    curl -fsSL https://raw.githubusercontent.com/senghan1992/genius_book/main/install.sh | sh -s -- --help
    curl -fsSL https://raw.githubusercontent.com/senghan1992/genius_book/main/install.sh | sh -s -- --uninstall

옵션:
    --help          이 도움말 표시
    --uninstall     설치 제거
    --update        업데이트
    --shell-only    셸 통합만 설치 (pip 설치 건너뛰기)
    --yes           모든 질문에 yes

예시:
    # 기본 설치
    curl -fsSL https://raw.githubusercontent.com/senghan1992/genius_book/main/install.sh | sh

    # 대화형 설치
    curl -fsSL https://raw.githubusercontent.com/senghan1992/genius_book/main/install.sh | sh -s

    # 제거
    curl -fsSL https://raw.githubusercontent.com/senghan1992/genius_book/main/install.sh | sh -s -- --uninstall
EOF
}

# =============================================================================
# 설치 함수
# =============================================================================

check_requirements() {
    log_info "Requirements 체크 중..."

    # Python 체크
    if ! command -v python3 &> /dev/null; then
        if command -v python &> /dev/null; then
            PYTHON_CMD="python"
        else
            log_error "Python3가 설치되어 있지 않습니다."
            log_info "Python3 설치: https://www.python.org/downloads/"
            exit 1
        fi
    else
        PYTHON_CMD="python3"
    fi

    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)

    if [ "$(echo "$PYTHON_VERSION < 3.10" | bc 2>/dev/null || echo 1)" = "1" ]; then
        log_error "Python 3.10 이상이 필요합니다. 현재: $PYTHON_VERSION"
        exit 1
    fi

    log_success "Python $PYTHON_VERSION ✓"

    # pip 체크
    if ! $PYTHON_CMD -m pip --version &> /dev/null; then
        log_info "pip 설치 중..."
        $PYTHON_CMD -m ensurepip --upgrade 2>/dev/null || {
            log_error "pip 설치 실패"
            exit 1
        }
    fi

    log_success "pip ✓"

    # git 체크 (선택사항)
    if command -v git &> /dev/null; then
        log_success "git ✓"
    else
        log_warn "git가 설치되어 있지 않습니다 (선택사항)"
    fi
}

install_pip() {
    log_info "genius-intelligence 설치 중..."

    # 가상환경이 아니면 가상환경 사용 권장
    if [ -z "$VIRTUAL_ENV" ]; then
        log_warn "가상환경이 아닙니다. 설치 권장: python -m venv venv && source venv/bin/activate"
        if [ "${GENIUS_SKIP_VENV_CHECK:-0}" != "1" ]; then
            read -p "계속 진행하시겠습니까? (y/N) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                log_info "설치 취소됨"
                exit 0
            fi
        fi
    fi

    # pip install
    $PYTHON_CMD -m pip install --upgrade pip
    $PYTHON_CMD -m pip install genius-intelligence[cli]

    log_success "genius-intelligence 설치 완료!"
}

install_shell_integration() {
    log_info "셸 통합 설치 중..."

    # 셸 감지
    if [ -n "$ZSH_VERSION" ]; then
        SHELL_RC="$HOME/.zshrc"
        SHELL_NAME="zsh"
    elif [ -n "$BASH_VERSION" ]; then
        SHELL_RC="$HOME/.bashrc"
        SHELL_NAME="bash"
    else
        SHELL_RC="$HOME/.profile"
        SHELL_NAME="unknown"
    fi

    # 통합 줄
    GENIUS_LINE='[[ -f "$(python -c "import genius_intelligence; import os; print(os.path.dirname(genius_intelligence.__file__))" 2>/dev/null)"/shell/genius.sh ]] && source "$(python -c "import genius_intelligence; import os; print(os.path.dirname(genius_intelligence.__file__))" 2>/dev/null)"/shell/genius.sh'

    # 이미 추가되어 있는지 확인
    if grep -q "genius.sh" "$SHELL_RC" 2>/dev/null; then
        log_success "셸 통합이 이미 설치되어 있습니다 ($SHELL_RC)"
    else
        echo "" >> "$SHELL_RC"
        echo "# Genius Intelligence" >> "$SHELL_RC"
        echo '[[ -f "$(python -c "import genius_intelligence; import os; print(os.path.dirname(genius_intelligence.__file__))" 2>/dev/null)/shell/genius.sh" ]] && source "$(python -c "import genius_intelligence; import os; print(os.path.dirname(genius_intelligence.__file__))" 2>/dev/null)/shell/genius.sh"' >> "$SHELL_RC"

        log_success "셸 통합 설치 완료! ($SHELL_RC)"
        log_info "셸을 재시작하거나 'source $SHELL_RC' 를 실행하세요"
    fi

    log_info "설치 확인: python -c 'import genius_intelligence'"
}

verify_installation() {
    log_info "설치 확인 중..."

    if python3 -c "import genius_intelligence" 2>/dev/null; then
        log_success "Python 모듈 ✓"
    else
        log_error "Python 모듈 확인 실패"
        exit 1
    fi

    # CLI 확인
    if command -v genius &> /dev/null; then
        log_success "CLI 설치 ✓"
    elif python3 -m genius_intelligence.cli.main &> /dev/null; then
        log_success "CLI 설치 ✓ (python -m)"
    else
        log_warn "CLI를 직접 실행하려면 PATH에 추가하거나 'pip install -e .' 하세요"
    fi
}

show_next_steps() {
    echo ""
    echo "============================================================"
    echo "  설치 완료! 🎉"
    echo "============================================================"
    echo ""
    echo "  다음 단계:"
    echo ""
    echo "  1. 셸을 재시작하거나:"
    echo "     source $SHELL_RC"
    echo ""
    echo "  2. 코딩 어시스턴트 실행:"
    echo "     claude --no-input"
    echo "     # 또는"
    echo "     omp"
    echo ""
    echo "  3. 상태 확인:"
    echo "     genius-status"
    echo ""
    echo "  4. 지원 명령어:"
    echo "     genius-status     # 상태"
    echo "     genius-search     # 검색"
    echo "     genius-tree       # 트리"
    echo "     genius-cleanup    # 정리"
    echo ""
    echo "============================================================"
    echo ""
}

# =============================================================================
# 제거 함수
# =============================================================================

uninstall() {
    log_warn "Genius Intelligence 제거..."

    # pip 제거
    if python3 -m pip show genius-intelligence &> /dev/null; then
        python3 -m pip uninstall -y genius-intelligence
        log_success "pip 패키지 제거 완료"
    fi

    # 셸 통합 제거
    for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
        if [ -f "$rc" ]; then
            # genius.sh 관련 줄 제거
            if grep -q "genius.sh" "$rc" 2>/dev/null; then
                # Genius Intelligence 관련 줄만 제거
                sed -i.bak '/# Genius Intelligence/d' "$rc"
                sed -i.bak '/genius.sh/d' "$rc"
                rm -f "${rc}.bak"
                log_success "셸 통합 제거: $rc"
            fi
        fi
    done

    log_success "제거 완료!"
}

# =============================================================================
# 메인
# =============================================================================

main() {
    # 인자 파싱
    SKIP_PIP=0
    SKIP_SHELL=0
    UNINSTALL_MODE=0
    UPDATE_MODE=0
    YES_MODE=0

    while [[ $# -gt 0 ]]; do
        case $1 in
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
                YES_MODE=1
                export GENIUS_SKIP_VENV_CHECK=1
                shift
                ;;
            *)
                log_error "알 수 없는 옵션: $1"
                show_help
                exit 1
                ;;
        esac
    done

    echo ""
    echo "============================================================"
    echo "  Genius Intelligence Installer v${GENIUS_VERSION}"
    echo "============================================================"
    echo ""

    # 제거 모드
    if [ $UNINSTALL_MODE -eq 1 ]; then
        uninstall
        exit 0
    fi

    # 업데이트 모드
    if [ $UPDATE_MODE -eq 1 ]; then
        log_info "업데이트 중..."
        python3 -m pip install --upgrade genius-intelligence[cli]
        log_success "업데이트 완료!"
        exit 0
    fi

    # 설치
    if [ $SKIP_PIP -eq 0 ]; then
        check_requirements
        install_pip
    fi

    install_shell_integration
    verify_installation
    show_next_steps
}

# 스크립트 직접 실행 시
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
