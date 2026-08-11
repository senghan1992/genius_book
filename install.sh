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
# 한 줄 설치 = omp.sh 스타일. 어떤 대화/질문도 없이 자동으로 시스템 PATH에
# 설치되며, 설치 직후 새 셸을 열면 바로 `genius` 명령을 입력할 수 있습니다.
# 우선순위: pipx → --user → global(sudo) → venv (최후의 수단).
# 방식을 직접 지정하고 싶으면 --mode= 를 쓰면 됩니다.
# =============================================================================

set -e

GENIUS_VERSION="0.1.0"
GENIUS_REPO="senghan1992/genius_book"

GENIUS_HOME="$HOME/.genius_intelligence_install"
GENIUS_VENV_DIR="$GENIUS_HOME/venv"
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
    --update            업데이트 (현재 설치된 방식 그대로 업그레이드)
    --shell-only        셸 통합만 설치 (pip 설치 건너뛰기)
    --yes, -y           질문 없이 자동 진행 (현재는 디폴트 동작이므로 무시됨)
    --mode=<MODE>       설치 방식을 강제로 지정 (global | venv | pipx | user)

기본 동작 (omp.sh 스타일):
    어떤 대화/질문도 하지 않고, 시스템 환경에 가장 적합한 방식으로 자동 설치합니다.
    우선순위:
        1) pipx      - 설치되어 있으면 가장 깨끗하고 추천
        2) --user    - sudo 없이 사용자 site-packages에 설치 (모든 시스템에서 동작)
        3) global    - sudo 가능하면 시스템 전역에 설치
        4) venv      - 위 셋이 모두 안 되면 격리된 가상환경 설치 (fallback)

    방식을 명시적으로 지정하고 싶을 때만 --mode= 를 사용하세요.
    예: curl ... | sh -s -- --mode=pipx

설치 후:
    새 터미널을 열면 바로 'genius' 명령을 사용할 수 있습니다.
    코딩 어시스턴트(claude, omp, opencode, codex 등)도 자동으로 Genius와 함께 동작합니다.

예시:
    # 자동 설치 (가장 일반적)
    curl -fsSL https://senghan1992.github.io/genius_book/install | sh

    # 제거
    curl -fsSL https://senghan1992.github.io/genius_book/install | sh -s -- --uninstall

    # pipx 로 강제 설치
    curl -fsSL https://senghan1992.github.io/genius_book/install | sh -s -- --mode=pipx
EOF
}

# =============================================================================
# 공용 헬퍼
# =============================================================================

# /dev/tty 가 실제로 open 가능한지 검사 (파라미터 있는 컨테이너에서도 실패 가능)
_tty_openable() {
    ( : < /dev/tty ) 2>/dev/null
}

is_interactive() {
    [ -t 0 ] && return 0
    _tty_openable && return 0
    return 1
}

detect_pipx() {
    command -v pipx >/dev/null 2>&1
}

# sudo 가 비밀번호 없이 실행 가능한지 (NOPASSWD 또는 캐시된 credential)
detect_passwordless_sudo() {
    command -v sudo >/dev/null 2>&1 || return 1
    sudo -n true >/dev/null 2>&1
}

# =============================================================================
# 설치 방식 자동 선택 (대화형 메뉴 없음 - omp.sh 스타일)
#
# 우선순위:
#   1) --mode= 로 명시 지정된 값
#   2) pipx (가장 깔끔한 격리 + 자동 PATH 처리)
#   3) --user  (sudo 불필요, 모든 시스템에서 동작)
#   4) global  (sudo 가능할 때만)
#   5) venv    (최후의 fallback)
# =============================================================================

# 시스템이 --user 설치를 허용하는지 (PEP 668 같은 externally-managed-environment 가 없는지)
# 빈 pip install --user --dry-run 으로 안전하게 확인한다.
_user_mode_allowed() {
    "$PYTHON_CMD" -m pip install --user --dry-run "genius-intelligence[cli]" >/dev/null 2>&1
}

auto_pick_install_mode() {
    # 1) 명시 지정 우선
    if [ -n "$GENIUS_INSTALL_MODE" ]; then
        log_info "설치 방식 지정됨: ${BOLD}${GENIUS_INSTALL_MODE}${NC}"
        return 0
    fi

    # 2) pipx 우선 (정확히 이 use-case 를 위해 만들어진 도구)
    if detect_pipx; then
        GENIUS_INSTALL_MODE="pipx"
        log_info "자동 선택: ${BOLD}pipx${NC} (감지됨 ✓)"
        return 0
    fi

    # 3) --user 가 이 시스템에서 허용되는지 (PEP 668 호환성 체크)
    if _user_mode_allowed; then
        GENIUS_INSTALL_MODE="user"
        log_info "자동 선택: ${BOLD}--user${NC} (sudo 없이 사용자 환경에 설치)"
        return 0
    fi

    # 4) --user 가 막혀있으면 (Debian/Ubuntu PEP 668) pipx 를 자동 설치 후 사용
    log_warn "이 시스템은 --user 설치를 막고 있어 (PEP 668) pipx 를 자동 설치합니다..."
    if "$PYTHON_CMD" -m pip install --user pipx >/dev/null 2>&1; then
        # pipx ensurepath 로 PATH 까지 잡아준다
        "$PYTHON_CMD" -m pipx ensurepath >/dev/null 2>&1 || true
        if command -v pipx >/dev/null 2>&1; then
            GENIUS_INSTALL_MODE="pipx"
            log_info "자동 선택: ${BOLD}pipx${NC} (자동 설치됨 ✓)"
            return 0
        fi
    fi

    # 5) 최후의 수단: venv (격리된 가상환경)
    GENIUS_INSTALL_MODE="venv"
    log_warn "기본 설치가 모두 막혀 ${BOLD}venv${NC} (격리 가상환경) 로 fallback 합니다."
    return 0
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

# 현재 OS / python 버전에서 --user 모드 시 bin 경로를 계산
_user_site_bin_dir() {
    # python -m site --user-base 로 user base 를 얻고 그 아래 /bin 을 붙인다.
    # 파이썬이 출력 경로에 줄바꿈을 넣을 수 있어 tr 로 정리한다.
    "$PYTHON_CMD" -m site --user-base 2>/dev/null \
        | tr -d '\r\n' \
        | awk '{ printf "%s/bin\n", $0 }'
}

# 여러 후보 경로 중 가장 가능성 높은 PATH 추가용 디렉토리 반환 (없으면 빈값)
_best_bin_for_path() {
    # pipx 는 거의 항상 $HOME/.local/bin
    if [ "$GENIUS_INSTALL_MODE" = "pipx" ]; then
        printf "%s" "$HOME/.local/bin"
        return 0
    fi

    # user 모드: OS 별 user bin
    if [ "$GENIUS_INSTALL_MODE" = "user" ]; then
        user_bin=$(_user_site_bin_dir 2>/dev/null)
        if [ -n "$user_bin" ] && [ -d "$user_bin" ]; then
            printf "%s" "$user_bin"
            return 0
        fi
        # fallback: ~/.local/bin (Linux XDG)
        if [ -d "$HOME/.local/bin" ]; then
            printf "%s" "$HOME/.local/bin"
            return 0
        fi
    fi

    # global 모드
    if [ "$GENIUS_INSTALL_MODE" = "global" ]; then
        # python -c "import sysconfig; print(sysconfig.get_paths()['scripts'])"
        sys_bin=$("$PYTHON_CMD" -c "import sysconfig; print(sysconfig.get_paths().get('scripts',''))" 2>/dev/null | tr -d '\r\n')
        if [ -n "$sys_bin" ] && [ -d "$sys_bin" ]; then
            printf "%s" "$sys_bin"
            return 0
        fi
    fi

    # venv 모드
    if [ "$GENIUS_INSTALL_MODE" = "venv" ]; then
        printf "%s" "$HOME/.local/bin"
        return 0
    fi

    printf ""
}

# 어떤 디렉토리에 PATH 가 이미 들어있는지 검사
_path_has_dir() {
    case ":$PATH:" in
        *":$1:"*) return 0 ;;
        *) return 1 ;;
    esac
}

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

    mkdir -p "$HOME/.local/bin"
    WRAPPER="$HOME/.local/bin/genius"
    printf '#!/bin/sh\nexec "%s/bin/genius" "$@"\n' "$GENIUS_VENV_DIR" > "$WRAPPER"
    chmod +x "$WRAPPER"

    GENIUS_INSTALLED_PYTHON="$GENIUS_VENV_DIR/bin/python"
    GENIUS_INSTALLED_BIN_DIR="$HOME/.local/bin"
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
    # pipx 가 이미 설치한 경우 강제로 재설치 (업데이트 성격)
    if $PIPX_CMD list --short 2>/dev/null | grep -q "^genius-intelligence"; then
        log_info "이미 설치되어 있어 업그레이드 합니다..."
        $PIPX_CMD upgrade genius-intelligence || true
    else
        $PIPX_CMD install "genius-intelligence[cli]" \
            || $PIPX_CMD install --force "genius-intelligence"
    fi

    GENIUS_INSTALLED_PYTHON="$PYTHON_CMD"
    GENIUS_INSTALLED_BIN_DIR="$HOME/.local/bin"
    log_success "pipx 설치 완료!"
}

install_mode_user() {
    log_info "사용자(--user) 설치 진행 중..."
    if ! "$PYTHON_CMD" -m pip install --user --upgrade pip 2>/dev/null; then
        # PEP 668 환경이면 pip 자체가 --user 설치 거부 → pipx 로 위임
        log_warn "--user pip 업그레이드 실패 (PEP 668 환경 가능성). pipx 로 위임합니다."
        if ! detect_pipx; then
            "$PYTHON_CMD" -m pip install --user pipx 2>/dev/null ||                 "$PYTHON_CMD" -m pip install --break-system-packages --user pipx 2>/dev/null || true
            "$PYTHON_CMD" -m pipx ensurepath >/dev/null 2>&1 || true
        fi
        if command -v pipx >/dev/null 2>&1; then
            GENIUS_INSTALL_MODE="pipx"
            install_mode_pipx
            return $?
        fi
        log_error "--user 모드로 설치할 수 없고 pipx 도 설치할 수 없습니다."
        exit 1
    fi

    "$PYTHON_CMD" -m pip install --user "genius-intelligence[cli]"

    # user-bin 경로를 미리 계산해둔다 (PATH 자동 보정에 사용)
    user_bin=$(_user_site_bin_dir 2>/dev/null)
    if [ -n "$user_bin" ]; then
        GENIUS_INSTALLED_BIN_DIR="$user_bin"
    else
        GENIUS_INSTALLED_BIN_DIR="$HOME/.local/bin"
    fi
    GENIUS_INSTALLED_PYTHON="$PYTHON_CMD"
    log_success "사용자 설치 완료! (실행 파일 위치: $GENIUS_INSTALLED_BIN_DIR)"
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
# install.sh 가 어떤 방식으로 genius_intelligence 를 설치했든, genius.sh 통합
# 스니펫은 항상 (PATH 에서 찾을 수 있는) `genius` 실행 파일에 위임하므로
# 안전합니다. 추가로, pipx/user/global 모드의 bin 디렉토리가 현재 PATH 에
# 없으면 셸 rc 에 PATH 줄을 함께 넣어줍니다.
# =============================================================================

install_shell_integration() {
    log_info "셸 통합 설치 중..."

    if [ -n "${ZSH_VERSION:-}" ]; then
        SHELL_RC="$HOME/.zshrc"
    elif [ -n "${BASH_VERSION:-}" ]; then
        SHELL_RC="$HOME/.bashrc"
    else
        SHELL_RC="$HOME/.profile"
    fi

    # 어떤 디렉토리를 PATH 에 보장해야 하는지 계산
    NEEDED_BIN=""
    if [ -n "$GENIUS_INSTALLED_BIN_DIR" ]; then
        NEEDED_BIN="$GENIUS_INSTALLED_BIN_DIR"
    else
        # 최후의 시도: 가장 가능성 높은 bin 디렉토리
        NEEDED_BIN=$(_best_bin_for_path)
    fi

    PATH_LINE=""
    if [ -n "$NEEDED_BIN" ] && ! _path_has_dir "$NEEDED_BIN"; then
        PATH_LINE='export PATH="'"$NEEDED_BIN"':$PATH"'
    fi

    GENIUS_INTEGRATION_LINE='command -v genius >/dev/null 2>&1 && eval "$(genius shell-init 2>/dev/null)"'

    # 이미 통합되어 있는지 검사 (둘 중 하나라도 있으면 OK)
    HAS_INTEGRATION=0
    if [ -f "$SHELL_RC" ] && grep -q "genius shell-init" "$SHELL_RC" 2>/dev/null; then
        HAS_INTEGRATION=1
    fi

    if [ "$HAS_INTEGRATION" = "1" ]; then
        # 통합은 있지만 PATH 가 누락된 경우엔 PATH 줄만 추가
        if [ -n "$PATH_LINE" ] && ! grep -qF "$PATH_LINE" "$SHELL_RC" 2>/dev/null; then
            # rc 파일 맨 마지막 줄 앞에 안전하게 추가
            printf '\n# Genius Intelligence (PATH)\n%s\n' "$PATH_LINE" >> "$SHELL_RC"
            log_success "PATH 추가 완료: $NEEDED_BIN → $SHELL_RC"
        else
            log_success "셸 통합이 이미 설치되어 있습니다 ($SHELL_RC)"
        fi
    else
        {
            printf "\n# Genius Intelligence\n"
            if [ -n "$PATH_LINE" ]; then
                printf '%s\n' "$PATH_LINE"
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

    # 현재 스크립트 셸에서 즉시 genius 를 찾을 수 있도록 PATH 보정
    if [ -n "$GENIUS_INSTALLED_BIN_DIR" ]; then
        PATH="$GENIUS_INSTALLED_BIN_DIR:$PATH"
    fi
    export PATH

    if command -v genius >/dev/null 2>&1; then
        log_success "CLI ✓  $(command -v genius)"
    else
        log_warn "이 셸에서 바로 'genius' 를 찾을 수 없습니다. 새 셸을 열거나 '. $HOME/.bashrc' (또는 ~/.zshrc) 를 실행하면 PATH 가 잡힙니다."
    fi

    if "$PYTHON_CMD" -c "import genius_intelligence" 2>/dev/null \
       || ( [ -n "$GENIUS_INSTALLED_PYTHON" ] && "$GENIUS_INSTALLED_PYTHON" -c "import genius_intelligence" 2>/dev/null ); then
        log_success "Python 모듈 ✓"
    else
        log_warn "Python 모듈 검증을 건너뜁니다 (설치 방식에 따라 정상일 수 있음)"
    fi
}

show_next_steps() {
    printf "\n"
    printf "%b╔══════════════════════════════════════════════════════════╗%b\n" "$GREEN" "$NC"
    printf "%b║%b   🎉  설치가 완료되었습니다!                                %b║%b\n" "$GREEN" "$NC" "$GREEN" "$NC"
    printf "%b╚══════════════════════════════════════════════════════════╝%b\n" "$GREEN" "$NC"
    printf "\n"

    printf "  %b실행 위치%b\n" "$BOLD" "$NC"
    rule
    if command -v genius >/dev/null 2>&1; then
        printf "   genius  →  %b%s%b\n" "$CYAN" "$(command -v genius)" "$NC"
    elif [ -n "$GENIUS_INSTALLED_BIN_DIR" ]; then
        printf "   genius  →  %b%s/genius%b\n" "$CYAN" "$GENIUS_INSTALLED_BIN_DIR" "$NC"
    fi
    printf "\n"

    printf "  %b다음 단계%b\n" "$BOLD" "$NC"
    rule
    printf "   %b1.%b 새 셸을 열거나 (PATH 자동 적용):\n" "$CYAN" "$NC"
    if [ -n "${ZSH_VERSION:-}" ]; then
        printf "      %bexec zsh%b    또는    %b. ~/.zshrc%b\n" "$DIM" "$NC" "$DIM" "$NC"
    elif [ -n "${BASH_VERSION:-}" ]; then
        printf "      %bexec bash%b   또는    %b. ~/.bashrc%b\n" "$DIM" "$NC" "$DIM" "$NC"
    else
        printf "      %b. ~/.profile%b\n" "$DIM" "$NC"
    fi
    printf "\n"
    printf "   %b2.%b 코딩 어시스턴트 실행 (자동으로 Genius 와 함께 동작):\n" "$CYAN" "$NC"
    printf "      %bclaude%b   %bomp%b   %bopencode%b   %bcodex%b   %baider%b   ...\n" "$DIM" "$NC" "$DIM" "$NC" "$DIM" "$NC" "$DIM" "$NC" "$DIM" "$NC"
    printf "\n"
    printf "   %b3.%b Genius 상태 확인:\n" "$CYAN" "$NC"
    printf "      %bgenius status%b\n" "$DIM" "$NC"
    printf "\n"
    printf "   %b4.%b 자주 쓰는 명령어\n" "$CYAN" "$NC"
    printf "      %bgenius status%b     현재 상태\n" "$DIM" "$NC"
    printf "      %bgenius search%b     지식 검색\n" "$DIM" "$NC"
    printf "      %bgenius tree%b       저장된 지식 트리 보기\n" "$DIM" "$NC"
    printf "      %bgenius cleanup%b    오래된 지식 정리\n" "$DIM" "$NC"
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

    # pip uninstall
    if "$PY_UNINSTALL_CMD" -m pip show genius-intelligence >/dev/null 2>&1; then
        "$PY_UNINSTALL_CMD" -m pip uninstall -y genius-intelligence 2>/dev/null || true
        log_success "pip 패키지 제거 완료"
    fi

    # pipx uninstall
    if command -v pipx >/dev/null 2>&1 && pipx list --short 2>/dev/null | grep -q "^genius-intelligence"; then
        pipx uninstall genius-intelligence 2>/dev/null || true
        log_success "pipx 패키지 제거 완료"
    fi

    # sudo pip uninstall (global)
    if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
        sudo -n "$PY_UNINSTALL_CMD" -m pip uninstall -y genius-intelligence 2>/dev/null || true
    fi

    # venv
    if [ -d "$GENIUS_VENV_DIR" ]; then
        rm -rf "$GENIUS_HOME"
        log_success "가상환경 제거 완료: $GENIUS_HOME"
    fi

    # venv 래퍼
    rm -f "$HOME/.local/bin/genius" 2>/dev/null || true

    # 셸 rc 정리 (# Genius Intelligence 블록 전체 - 코멘트 + PATH + 통합 라인)
    for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
        if [ -f "$rc" ] && grep -q "Genius Intelligence" "$rc" 2>/dev/null; then
            # "# Genius Intelligence" 로 시작하는 블록을 다음 빈 줄 전까지 통째로 삭제
            # BSD sed (macOS) 와 GNU sed 모두 호환되는 방식으로 awk 사용
            awk '
                BEGIN { skip=0 }
                /^# Genius Intelligence/ { skip=1; next }
                skip==1 && /^$/ { skip=0; next }
                skip==1 { next }
                { print }
            ' "$rc" > "$rc.tmp" && mv "$rc.tmp" "$rc"
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
            # omp.sh 스타일: 디폴트 동작이 이미 비대화형 자동 설치이므로
            # 옵션 자체는 호환을 위해 받아들인다 (no-op).
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
    # 설치된 방식 감지: pipx > --user > global 순으로 우선 시도
    UPDATED=0
    if command -v pipx >/dev/null 2>&1 && pipx list --short 2>/dev/null | grep -q "^genius-intelligence"; then
        pipx upgrade genius-intelligence && UPDATED=1
    fi
    if [ "$UPDATED" -eq 0 ] && command -v python3 >/dev/null 2>&1; then
        python3 -m pip install --user --upgrade "genius-intelligence[cli]" && UPDATED=1
    fi
    if [ "$UPDATED" -eq 0 ] && command -v python >/dev/null 2>&1; then
        python -m pip install --user --upgrade "genius-intelligence[cli]" && UPDATED=1
    fi
    if [ "$UPDATED" -eq 0 ]; then
        log_error "설치된 genius-intelligence 를 찾지 못했습니다. 먼저 설치해주세요."
        exit 1
    fi
    log_success "업데이트 완료!"
    exit 0
fi

if [ "$SKIP_PIP" -eq 0 ]; then
    check_requirements
    auto_pick_install_mode
    run_install
fi

install_shell_integration
verify_installation
show_next_steps
