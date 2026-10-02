param(
    [string]$ExpectedComputerName = "DESKTOP-MVV1FD4",
    [string]$ValidationOutput = "artifacts/wsl_opencode_audit_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

if ($env:COMPUTERNAME -ne $ExpectedComputerName) {
    throw "Refusing WSL OpenCode audit on $($env:COMPUTERNAME); expected $ExpectedComputerName."
}

$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
if ($null -eq $wsl) {
    throw "WSL_NOT_AVAILABLE"
}

function Invoke-WslText {
    param(
        [string]$Distro,
        [string]$Command
    )

    $output = & wsl.exe -d $Distro -- sh -lc $Command 2>$null
    $exitCode = [int]$LASTEXITCODE
    return @{
        exit_code = $exitCode
        text = [string](($output | Out-String).Trim())
    }
}

$rawDistros = @(& wsl.exe -l -q 2>$null)
$distros = @(
    $rawDistros |
    ForEach-Object { ([string]$_).Trim([char]0).Trim() } |
    Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
    Select-Object -Unique
)

$results = @()
foreach ($distro in $distros) {
    $pathResult = Invoke-WslText -Distro $distro -Command "command -v opencode || true"
    $opencodePath = $pathResult.text

    $version = $null
    $runHelpAvailable = $false
    if (-not [string]::IsNullOrWhiteSpace($opencodePath)) {
        $versionResult = Invoke-WslText -Distro $distro -Command "opencode --version"
        if ($versionResult.exit_code -eq 0 -and -not [string]::IsNullOrWhiteSpace($versionResult.text)) {
            $version = ($versionResult.text -split "\r?\n")[0]
        }

        $helpResult = Invoke-WslText -Distro $distro -Command "opencode run --help >/dev/null 2>&1"
        $runHelpAvailable = ($helpResult.exit_code -eq 0)
    }

    $ollamaReachable = $false
    $qwenAvailable = $false
    $ollamaCheck = Invoke-WslText -Distro $distro -Command @'
python3 - <<'PY'
import json
import urllib.request
try:
    with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3) as r:
        data = json.load(r)
    names = [m.get("name", "") for m in data.get("models", [])]
    print(json.dumps({"reachable": True, "qwen3_8b": "qwen3:8b" in names}))
except Exception:
    print(json.dumps({"reachable": False, "qwen3_8b": False}))
PY
'@
    if ($ollamaCheck.exit_code -eq 0 -and -not [string]::IsNullOrWhiteSpace($ollamaCheck.text)) {
        try {
            $parsed = $ollamaCheck.text | ConvertFrom-Json
            $ollamaReachable = [bool]$parsed.reachable
            $qwenAvailable = [bool]$parsed.qwen3_8b
        } catch {}
    }

    $results += @{
        distro = $distro
        opencode_found = -not [string]::IsNullOrWhiteSpace($opencodePath)
        opencode_path = $opencodePath
        opencode_version = $version
        opencode_run_available = $runHelpAvailable
        ollama_local_api_reachable = $ollamaReachable
        qwen3_8b_available = $qwenAvailable
    }
}

$preferred = $results | Where-Object {
    $_.opencode_found -and $_.opencode_run_available
} | Select-Object -First 1

$validation = @{
    status = "audited"
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    computer_name = $env:COMPUTERNAME
    expected_computer_name = $ExpectedComputerName
    commit_sha = (& git rev-parse HEAD).Trim()
    wsl_available = $true
    distro_count = $distros.Count
    distros = $results
    preferred_distro = if ($null -ne $preferred) { [string]$preferred.distro } else { $null }
    free_only_policy = @{
        opencode_allowed = $true
        ollama_local_allowed = $true
        required_model = "qwen3:8b"
        paid_cloud_provider_allowed = $false
        api_key_usage_allowed = $false
        codex_allowed = $false
    }
    secrets_included = $false
    live_execution_enabled = $false
}

$validationPath = Join-Path $ProjectRoot $ValidationOutput
$validationDir = Split-Path -Parent $validationPath
New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
$validation | ConvertTo-Json -Depth 8 |
    Set-Content -LiteralPath $validationPath -Encoding UTF8

Write-Host "WSL OpenCode audit PASS."
Write-Host "distro_count=$($distros.Count)"
Write-Host "preferred_distro=$($validation.preferred_distro)"
foreach ($item in $results) {
    Write-Host "$($item.distro): opencode=$($item.opencode_found) run=$($item.opencode_run_available) ollama=$($item.ollama_local_api_reachable) qwen3_8b=$($item.qwen3_8b_available)"
}
