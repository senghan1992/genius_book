# Genius Intelligence - PowerShell Integration
# 이 스크립트를 로드하면 코딩 어시스턴트 CLI가 자동으로 감싸집니다.

# Genius Intelligence 함수 정의
function Global:Get-GeniusPath {
    python -c "import genius_intelligence, os; print(os.path.dirname(genius_intelligence.__file__))" 2>$null
}

# 지원 CLI 목록
$Global:GeniusSupportedCLIs = @(
    "claude", "claude-code",
    "omp", "opencode",
    "aider", "aider-chat",
    "codex", "openai-codex",
    "cursor", "cursor-ai",
    "copilot", "github-copilot",
    "llm", "ollama"
)

function Global:Test-GeniusSupportedCLI {
    param([string]$Cmd)
    $cmdLower = $Cmd.ToLower()
    foreach ($cli in $GeniusSupportedCLIs) {
        if ($cmdLower -eq $cli) { return $true }
    }
    return $false
}

# CLI 래핑 함수
function Global:Invoke-GeniusWrappedCommand {
    param([string]$Cmd, [string[]]$Args)

    $geniusPath = Get-GeniusPath
    if (-not $geniusPath) {
        # 설치 안 됨 - 그냥 실행
        & $Cmd @Args
        return
    }

    Write-Host "[genius] Wrapping: $Cmd $Args" -ForegroundColor Cyan
    python -m genius_intelligence.auto.universal $Cmd @Args
}

# Set-Alias로 기존 명령 오버라이드
foreach ($cli in $GeniusSupportedCLIs) {
    if (-not (Get-Command $cli -ErrorAction SilentlyContinue)) {
        # 명령이 없으면 함수 정의만
        Set-Alias -Name $cli -Value "genius-$cli" -Scope Global -Option AllScope 2>$null
    }
}

Write-Host "[genius] Genius Intelligence PowerShell integration loaded" -ForegroundColor Green
Write-Host "[genius] Supported CLIs: $($GeniusSupportedCLIs.Count) tools" -ForegroundColor Green
