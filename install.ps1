# Genius Intelligence - Windows Installer
# Usage:
#   irm https://.../install.ps1 | iex
#   # 또는
#   .\install.ps1

param(
    [switch]$Uninstall,
    [switch]$Update,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
$GENIUS_VERSION = "0.1.0"

function Write-Info($msg) { Write-Host "[genius] $msg" -ForegroundColor Cyan }
function Write-Success($msg) { Write-Host "[genius] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[genius] $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "[genius] $msg" -ForegroundColor Red }

function Show-Help {
    @"
Genius Intelligence Installer

사용법:
    irm https://.../install.ps1 | iex
    .\install.ps1

옵션:
    -Uninstall    설치 제거
    -Update       업데이트
    -Help         도움말
"@
}

function Check-Requirements {
    Write-Info "Requirements 체크 중..."

    # Python 체크
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        $python = Get-Command python3 -ErrorAction SilentlyContinue
    }

    if (-not $python) {
        Write-Err "Python가 설치되어 있지 않습니다."
        exit 1
    }

    $pyVersion = python --version 2>&1
    Write-Success "Python: $pyVersion"

    # pip 체크
    if (-not (python -m pip --version 2>$null)) {
        Write-Info "pip 설치 중..."
        python -m ensurepip --upgrade
    }
    Write-Success "pip ✓"
}

function Install-Pip {
    Write-Info "genius-intelligence 설치 중..."
    python -m pip install --upgrade pip
    python -m pip install genius-intelligence[cli]
    Write-Success "설치 완료!"
}

function Install-ShellIntegration {
    Write-Info "PowerShell 통합 설치 중..."

    $profilePath = $PROFILE
    $geniusLine = @'
# Genius Intelligence
$geniusPath = python -c "import genius_intelligence, os; print(os.path.dirname(genius_intelligence.__file__))" 2>$null
if ($geniusPath) {
    $geniusSh = Join-Path $geniusPath "shell/genius.ps1"
    if (Test-Path $geniusSh) { . $geniusSh }
}
'@

    if (Test-Path $profilePath) {
        $content = Get-Content $profilePath -Raw -ErrorAction SilentlyContinue
        if ($content -match "genius.sh") {
            Write-Success "이미 설치되어 있습니다"
        } else {
            Add-Content $profilePath -Value "`n$geniusLine"
            Write-Success "PowerShell 통합 설치 완료!"
        }
    } else {
        New-Item -ItemType File -Path $profilePath -Force | Out-Null
        Add-Content $profilePath -Value $geniusLine
        Write-Success "PowerShell 통합 설치 완료!"
    }
}

function Verify-Installation {
    Write-Info "설치 확인 중..."
    python -c "import genius_intelligence"
    Write-Success "Python 모듈 ✓"
}

# 메인
if ($Help) {
    Show-Help
    exit 0
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Genius Intelligence Installer v$GENIUS_VERSION"
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

if ($Uninstall) {
    Write-Warn "제거 중..."
    python -m pip uninstall -y genius-intelligence
    Write-Success "제거 완료!"
    exit 0
}

if ($Update) {
    Write-Info "업데이트 중..."
    python -m pip install --upgrade genius-intelligence[cli]
    Write-Success "업데이트 완료!"
    exit 0
}

Check-Requirements
Install-Pip
Install-ShellIntegration
Verify-Installation

Write-Host ""
Write-Success "설치 완료! 🎉"
Write-Info "PowerShell을 재시작하거나 '. `$PROFILE' 를 실행하세요"
