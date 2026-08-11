#!/bin/sh
# =============================================================================
# Genius Intelligence - Installer
# =============================================================================
# POSIX sh 호환 스크립트입니다. bash, dash, zsh, ash(alpine) 등에서 모두
# 동작하도록 [[ ]], =~, 배열, read -p/-n, &> 등 bash 전용 문법을 사용하지 않습니다.
#
# Usage (짧은 URL, 권장):
#   curl -fsSL https://senghan1992.github.io/genius_book/install | sh
#   curl -fsSL https://senghan1992.github.io/genius_book/install | sh -s -- --help
#   curl -fsSL https://senghan1992.github.io/genius_book/install | sh -s -- --uninstall
#
# GitHub raw URL로도 동일하게 동작합니다:
#   curl -fsSL https://raw.githubusercontent.com/senghan1992/genius_book/main/install.sh | sh
#
# 설치 방식은 대화형 메뉴로 사용자가 직접 선택합니다 (전역 / 가상환경 / pipx / --user).
# 비대화형(파이프+터미널 없음) 환경에서는 GENIUS_INSTALL_MODE 로 미리 지정하거나,
# 지정하지 않으면 가장 안전한 기본값(가상환경 격리 설치)으로 자동 진행합니다.
# =============================================================================

set -e

GENIUS_VERSION="0.1.0"
GENIUS_REPO="senghan1992/genius_book"
INSTALL_URL="https://raw.githubusercontent.com/${GENIUS_REPO}/main/install.sh"

GENIUS_HOME="$HOME/.genius_intelligence_install"
GENIUS_VENV_DIR="$GENIUS_HOME/venv"
GENIUS_BIN_DIR="$HOME/.local/bin"

# ── 색상 / 스타일 (printf %b 로 해석. 비-tty 환경에선 그냥 무해한 문자로 출력) ──
BOLD='\033[1m'
DIM='\033[2m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

log_info()    { printf "%b[genius]%b %b\n" "$BLUE" "$NC" "$1"; }
log_success() { printf "%b[genius]%b %b\n" "$GREEN" "$NC" "$1"; }
log_warn()    { printf "%b[genius]%b %b\n" "$YELLOW" "$NC" "$1"; }
log_error()   { printf "%b[genius]%b %b\n" "$RED" "$NC" "$1" >&2; }

rule() {
    printf "%b%s%b\n" "$DIM" "────────────────────────────────────────────────────────────" "$NC"
}

banner() {
    printf "\n"
    printf "%b╭──────────────────────────────────────────────────────────╮%b\n" "$CYAN" "$NC"
    printf "%b│%b   %b🧠 Genius Intelligence%b  %bInstaller v%s%b               %b│%b\n" \
        "$CYAN" "$NC" "$BOLD$MAGENTA" "$NC" "$DIM" "$GENIUS_VERSION" "$NC" "$CYAN" "$NC"
    printf "%b╰──────────────────────────────────────────────────────────╯%b\n" "$CYAN" "$NC"
    printf "\n"
}

show_help() {
    cat << EOF
Genius Intelligence Installer

사용법 (짧은 URL, 권장):
    curl -fsSL https://senghan1992.github.io/genius_book/install | sh
    curl -fsSL https://senghan1992.github.io/genius_book/install | sh -s -- --help
    curl -fsSL https://senghan1992.github.io/genius_book/install | sh -s -- --uninstall

또는 GitHub raw URL로도 동일하게 동작합니다:
    curl -fsSL https://raw.githubusercontent.com/${GENIUS_REPO}/main/install.sh | sh

옵션:
    --help              이 도움말 표시
    --uninstall         설치 제거
    --update            업데이트
    --shell-only        셸 통합만 설치 (pip 설치 건너뛰기)
    --yes, -y           질문 없이 기본값(가상환경 격리 설치)으로 자동 진행
    --mode=<MODE>        설치 방식을 미리 지정 (global | venv | pipx | user)

설치 방식 (대화형 메뉴에서 선택 가능):
    global   현재 Python 환경에 바로 설치 (pip install)
    venv     ~/.genius_intelligence_install/venv 전용 가상환경에 격리 설치 (기본값)
    pipx     pipx로 격리된 CLI 도구로 설치 (설치되어 있는 경우 권장)
    user     현재 사용자 site-packages에 설치 (pip install --user)

예시:
    # 대화형 설치 (설치 방식을 직접 선택)
    curl -fsSL https://senghan1992.github.io/genius_book/install | sh

    # 비대화형: 방식을 미리 지정해서 질문 없이 설치
    curl -fsSL https://senghan1992.github.io/genius_book/install | sh -s -- --mode=pipx

    # 제거
    curl -fsSL https://senghan1992.github.io/genius_book/install | sh -s -- --uninstall
EOF
}

# ── 대화형 여부 판단 & 안전한 입력 읽기 (curl | sh 파이프에서도 /dev/tty 로 응답 받음) ──
#
# 주의: "/dev/tty 파일이 존재하고 읽기 권한이 있음(-r)"과 "실제로 open() 가능함"은
# 다릅니다. 컨테이너/샌드박스 환경에서는 -r 검사는 통과하지만 실제 열 때
# ENXIO 등으로 실패하는 경우가 있어, 서브셸로 실제 open 시도를 해보고
# 그 실패 메시지까지 완전히 억제합니다.
_tty_openable() {
    ( : < /dev/tty ) 2>/dev/null
}

_read_from_user() {
    # $1 에 결과를 저장 (변수명 전달)
    if [ -t 0 ]; then
        read -r "$1" 2>/dev/null || eval "$1=''"
    elif _tty_openable; then
        read -r "$1" < /dev/tty 2>/dev/null || eval "$1=''"
    else
        eval "$1=''"
    fi
}

is_interactive() {
    [ -t 0 ] && return 0
    _tty_openable && return 0
    return 1
}

# =============================================================================
# 설치 방식 선택 메뉴 (예쁜 CLI UI)
# =============================================================================

detect_pipx() {
    command -v pipx >/dev/null 2>&1
}

choose_install_mode() {
    # 이미 --mode= 또는 GENIUS_INSTALL_MODE 로 지정되어 있으면 그대로 사용
    if [ -n "$GENIUS_INSTALL_MODE" ]; then
        log_info "설치 방식이 이미 지정됨: ${BOLD}${GENIUS_INSTALL_MODE}${NC}"
        return 0
    fi

    # --yes 로 자동 진행 모드거나, 대화형이 아니면 안전한 기본값 사용
    if [ "$GENIUS_AUTO_YES" = "1" ] || ! is_interactive; then
        GENIUS_INSTALL_MODE="venv"
        log_warn "비대화형 환경이라 기본 설치 방식(${BOLD}venv${NC}${YELLOW}, 격리된 가상환경)으로 자동 진행합니다."
        log_info "다른 방식을 쓰려면: ${DIM}--mode=global|venv|pipx|user${NC}"
        return 0
    fi

    PIPX_LABEL="pipx 없음 (설치 시 자동 감지)"
    if detect_pipx; then
        PIPX_LABEL="pipx 감지됨 ✓ (가장 깔끔한 격리 설치)"
    fi

    printf "\n"
    printf "%b┌──────────────────────────────────────────────────────────┐%b\n" "$MAGENTA" "$NC"
    printf "%b│%b  설치 방식을 선택해주세요                                  %b│%b\n" "$MAGENTA" "$NC" "$MAGENTA" "$NC"
    printf "%b└──────────────────────────────────────────────────────────┘%b\n" "$MAGENTA" "$NC"
    printf "\n"
    printf "  %b1)%b %b전역 설치%b        현재 Python 환경에 바로 설치\n" "$BOLD$CYAN" "$NC" "$BOLD" "$NC"
    printf "  %b2)%b %b가상환경 설치%b     %b(기본값, 권장)%b\n" "$BOLD$CYAN" "$NC" "$BOLD" "$NC" "$GREEN" "$NC"
    printf "     %b~/.genius_intelligence_install/venv 에 완전히 격리 설치%b\n" "$DIM" "$NC"
    printf "  %b3)%b %bpipx 설치%b         %s\n" "$BOLD$CYAN" "$NC" "$BOLD" "$NC" "$PIPX_LABEL"
    printf "  %b4)%b %b사용자 설치%b       --user 로 내 계정 site-packages에 설치\n" "$BOLD$CYAN" "$NC" "$BOLD" "$NC"
    printf "  %b5)%b %b취소%b\n" "$BOLD$CYAN" "$NC" "$BOLD" "$NC"
    printf "\n"

    while :; do
        printf "  %b선택 [1-5] (기본값 2):%b " "$BOLD" "$NC"
        _read_from_user CHOICE
        case "$CHOICE" in
            ""|2) GENIUS_INSTALL_MODE="venv"; break ;;
            1) GENIUS_INSTALL_MODE="global"; break ;;
            3) GENIUS_INSTALL_MODE="pipx"; break ;;
            4) GENIUS_INSTALL_MODE="user"; break ;;
            5)
                log_info "설치가 취소되었습니다."
                exit 0
                ;;
            *)
                log_warn "1~5 사이의 숫자를 입력해주세요."
                ;;
        esac
    done

    printf "\n"
    log_success "선택된 설치 방식: ${BOLD}${GENIUS_INSTALL_MODE}${NC}"
}

# =============================================================================
# 요구사항 체크
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

# =============================================================================
# 설치 방식별 설치 함수
# =============================================================================

# 설치 후 genius 실행 파일이 있는 디렉토리를 담을 변수
GENIUS_INSTALLED_BIN_DIR=""

install_mode_global() {
    log_info "전역 설치 진행 중... (${PYTHON_CMD})"
    "$PYTHON_CMD" -m pip install --upgrade pip
    "$PYTHON_CMD" -m pip install "genius-intelligence[cli]"
    GENIUS_INSTALLED_PYTHON="$PYTHON_CMD"
    log_success "전역 설치 완료!"
}

install_mode_venv() {
    log_info "가상환경 생성 중: ${GENIUS_VENV_DIR}"
    mkdir -p "$GENIUS_HOME"
    "$PYTHON_CMD" -m venv "$GENIUS_VENV_DIR"

    log_info "가상환경에 genius-intelligence 설치 중..."
    "$GENIUS_VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null 2>&1
    "$GENIUS_VENV_DIR/bin/python" -m pip install "genius-intelligence[cli]"

    mkdir -p "$GENIUS_BIN_DIR"
    WRAPPER="$GENIUS_BIN_DIR/genius"
    printf '#!/bin/sh\nexec "%s/bin/genius" "$@"\n' "$GENIUS_VENV_DIR" > "$WRAPPER"
    chmod +x "$WRAPPER"

    GENIUS_INSTALLED_PYTHON="$GENIUS_VENV_DIR/bin/python"
    GENIUS_INSTALLED_BIN_DIR="$GENIUS_BIN_DIR"
    log_success "가상환경 설치 완료! (실행 파일: $WRAPPER)"
}

install_mode_pipx() {
    if ! detect_pipx; then
        log_warn "pipx가 설치되어 있지 않습니다. pipx를 먼저 설치합니다..."
        "$PYTHON_CMD" -m pip install --user pipx
        "$PYTHON_CMD" -m pipx ensurepath >/dev/null 2>&1 || true
        if command -v pipx >/dev/null 2>&1; then
            PIPX_CMD="pipx"
        else
            PIPX_CMD="$PYTHON_CMD -m pipx"
        fi
    else
        PIPX_CMD="pipx"
    fi

    log_info "pipx로 설치 중..."
    $PIPX_CMD install "genius-intelligence[cli]" || $PIPX_CMD install --force "genius-intelligence"

    GENIUS_INSTALLED_PYTHON="$PYTHON_CMD"
    GENIUS_INSTALLED_BIN_DIR="$HOME/.local/bin"
    log_success "pipx 설치 완료!"
    log_warn "pipx 설치 경로가 PATH에 없다면: ${DIM}pipx ensurepath${NC} 실행 후 셸을 재시작하세요."
}

install_mode_user() {
    log_info "사용자(--user) 설치 진행 중..."
    "$PYTHON_CMD" -m pip install --user --upgrade pip
    "$PYTHON_CMD" -m pip install --user "genius-intelligence[cli]"
    GENIUS_INSTALLED_PYTHON="$PYTHON_CMD"
    GENIUS_INSTALLED_BIN_DIR="$HOME/.local/bin"
    log_success "사용자 설치 완료!"
}

run_install() {
    case "$GENIUS_INSTALL_MODE" in
        global) install_mode_global ;;
        venv)   install_mode_venv ;;
        pipx)   install_mode_pipx ;;
        user)   install_mode_user ;;
        *)
            log_error "알 수 없는 설치 방식: $GENIUS_INSTALL_MODE (global|venv|pipx|user 중 하나)"
            exit 1
            ;;
    esac
}

# =============================================================================
# 셸 통합
#
# 설치 방식에 관계없이 항상 `genius shell-init` 명령으로 통합 스니펫을 가져옵니다.
# (venv/pipx/user 등 어떤 방식으로 설치했든, genius 실행 파일이 PATH에서
#  찾아지기만 하면 스스로 올바른 shell/genius.sh 경로를 알려주므로 안전합니다.)
# =============================================================================

install_shell_integration() {
    log_info "셸 통합 설치 중..."

    if [ -n "$ZSH_VERSION" ]; then
        SHELL_RC="$HOME/.zshrc"
    elif [ -n "$BASH_VERSION" ]; then
        SHELL_RC="$HOME/.bashrc"
    else
        SHELL_RC="$HOME/.profile"
    fi

    NEEDS_PATH_LINE=0
    case ":$PATH:" in
        *":$HOME/.local/bin:"*) ;;
        *) NEEDS_PATH_LINE=1 ;;
    esac

    GENIUS_INTEGRATION_LINE='command -v genius >/dev/null 2>&1 && eval "$(genius shell-init 2>/dev/null)"'

    if [ -f "$SHELL_RC" ] && grep -q "genius shell-init" "$SHELL_RC" 2>/dev/null; then
        log_success "셸 통합이 이미 설치되어 있습니다 ($SHELL_RC)"
    else
        {
            printf "\n# Genius Intelligence\n"
            if [ "$NEEDS_PATH_LINE" = "1" ]; then
                printf 'export PATH="%s/.local/bin:$PATH"\n' "$HOME"
            fi
            printf '%s\n' "$GENIUS_INTEGRATION_LINE"
        } >> "$SHELL_RC"
        log_success "셸 통합 설치 완료! ($SHELL_RC)"
        log_info "셸을 재시작하거나 '. $SHELL_RC' 를 실행하세요"
    fi
}

# =============================================================================
# 설치 검증
# =============================================================================

verify_installation() {
    log_info "설치 확인 중..."

    case "$GENIUS_INSTALL_MODE" in
        venv)
            CHECK_PY="$GENIUS_VENV_DIR/bin/python"
            ;;
        *)
            CHECK_PY="$PYTHON_CMD"
            ;;
    esac

    if [ -x "$CHECK_PY" ] && "$CHECK_PY" -c "import genius_intelligence" 2>/dev/null; then
        log_success "Python 모듈 ✓"
    elif "$PYTHON_CMD" -c "import genius_intelligence" 2>/dev/null; then
        log_success "Python 모듈 ✓"
    else
        log_warn "Python 모듈을 현재 셸에서 바로 확인할 수 없습니다 (설치 방식에 따라 정상일 수 있음)"
    fi

    # PATH 갱신 없이 이 스크립트 내에서 즉시 genius 를 찾을 수 있도록 보정
    if [ -n "$GENIUS_INSTALLED_BIN_DIR" ]; then
        PATH="$GENIUS_INSTALLED_BIN_DIR:$PATH"
    fi

    if command -v genius >/dev/null 2>&1; then
        log_success "CLI 설치 ✓ ($(command -v genius))"
    else
        log_warn "genius 명령을 아직 찾을 수 없습니다. 셸을 재시작한 뒤 다시 확인해주세요."
    fi
}

show_next_steps() {
    printf "\n"
    printf "%b╔══════════════════════════════════════════════════════════╗%b\n" "$GREEN" "$NC"
    printf "%b║%b   🎉  설치가 완료되었습니다!                                %b║%b\n" "$GREEN" "$NC" "$GREEN" "$NC"
    printf "%b╚══════════════════════════════════════════════════════════╝%b\n" "$GREEN" "$NC"
    printf "\n"
    printf "  %b다음 단계%b\n" "$BOLD" "$NC"
    rule
    printf "   %b1.%b 셸을 재시작하거나:\n" "$CYAN" "$NC"
    printf "      %b. %s%b\n" "$DIM" "$SHELL_RC" "$NC"
    printf "\n"
    printf "   %b2.%b 코딩 어시스턴트 실행 (자동으로 감지/추적됩니다):\n" "$CYAN" "$NC"
    printf "      %bclaude --no-input%b   %b또는%b   %bomp%b\n" "$DIM" "$NC" "$DIM" "$NC" "$DIM" "$NC"
    printf "\n"
    printf "   %b3.%b 상태 확인:\n" "$CYAN" "$NC"
    printf "      %bgenius-status%b\n" "$DIM" "$NC"
    printf "\n"
    printf "   %b4.%b 자주 쓰는 명령어\n" "$CYAN" "$NC"
    printf "      %bgenius-status%b     현재 상태\n" "$DIM" "$NC"
    printf "      %bgenius-search%b     지식 검색\n" "$DIM" "$NC"
    printf "      %bgenius-tree%b       저장된 지식 트리 보기\n" "$DIM" "$NC"
    printf "      %bgenius-cleanup%b    오래된 지식 정리\n" "$DIM" "$NC"
    rule
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

    if command -v pipx >/dev/null 2>&1 && pipx list --short 2>/dev/null | grep -q "^genius-intelligence"; then
        pipx uninstall genius-intelligence
        log_success "pipx 패키지 제거 완료"
    fi

    if [ -d "$GENIUS_VENV_DIR" ]; then
        rm -rf "$GENIUS_HOME"
        log_success "가상환경 제거 완료: $GENIUS_HOME"
    fi

    rm -f "$GENIUS_BIN_DIR/genius" 2>/dev/null || true

    for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
        if [ -f "$rc" ] && grep -q "Genius Intelligence" "$rc" 2>/dev/null; then
            sed -i.bak '/# Genius Intelligence/d' "$rc" 2>/dev/null || sed -i '' '/# Genius Intelligence/d' "$rc"
            sed -i.bak '/genius shell-init/d' "$rc" 2>/dev/null || sed -i '' '/genius shell-init/d' "$rc"
            sed -i.bak '/genius\.sh/d' "$rc" 2>/dev/null || sed -i '' '/genius\.sh/d' "$rc"
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
GENIUS_AUTO_YES=0
GENIUS_INSTALL_MODE="${GENIUS_INSTALL_MODE:-}"

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
            GENIUS_AUTO_YES=1
            shift
            ;;
        --mode=*)
            GENIUS_INSTALL_MODE="${1#--mode=}"
            shift
            ;;
        *)
            log_error "알 수 없는 옵션: $1"
            show_help
            exit 1
            ;;
    esac
done

banner

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
    choose_install_mode
    run_install
fi

install_shell_integration
verify_installation
show_next_steps
