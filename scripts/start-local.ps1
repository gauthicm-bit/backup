$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendPath = Join-Path $projectRoot 'backend'
$frontendPath = Join-Path $projectRoot 'frontend'
$pythonPath = Join-Path $backendPath '.venv/Scripts/python.exe'
$vitePath = Join-Path $frontendPath 'node_modules/vite/bin/vite.js'
$logPath = Join-Path $projectRoot '.local-logs'

if (-not (Test-Path -LiteralPath $pythonPath) -or -not (Test-Path -LiteralPath $vitePath)) {
    throw 'Install dependencies first: backend: uv sync --frozen; frontend: pnpm install --frozen-lockfile.'
}

function Resolve-NodeExecutable {
    $candidates = @()
    if ($env:MULTIVERSE_NODE_EXE) { $candidates += $env:MULTIVERSE_NODE_EXE }
    $pathCommand = Get-Command node.exe -ErrorAction SilentlyContinue
    if ($pathCommand) { $candidates += $pathCommand.Source }
    $candidates += Join-Path $env:ProgramFiles 'nodejs/node.exe'
    $candidates += Join-Path $env:LOCALAPPDATA 'Programs/nodejs/node.exe'

    # Codex supplies Node privately; ordinary PowerShell does not inherit its PATH.
    if (Get-Command Get-AppxPackage -ErrorAction SilentlyContinue) {
        $packages = @(Get-AppxPackage -Name 'OpenAI.CodexPrimaryRuntime*' -ErrorAction SilentlyContinue |
            Sort-Object Version -Descending)
        foreach ($package in $packages) {
            if ($package.InstallLocation) {
                $candidates += Join-Path $package.InstallLocation 'dependencies/node/bin/node.exe'
            }
        }
    }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            try {
                $version = & $candidate --version 2>$null
                if ($LASTEXITCODE -eq 0 -and $version -match '^v\d+\.') { return $candidate }
            } catch { }
        }
    }
    throw 'Node.js was not found. Install Node.js 24, reopen PowerShell, or set $env:MULTIVERSE_NODE_EXE to the full path of node.exe.'
}

function Wait-LocalEndpoint([string]$Url) {
    $deadline = (Get-Date).AddSeconds(30)
    do {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) { return }
        } catch { }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)
    throw "Server did not become ready at $Url. Check logs in $logPath."
}

# Resolve both runtimes before starting anything, so missing Node cannot leave
# the application half-started.
$nodePath = Resolve-NodeExecutable
Write-Host "Using Node.js: $nodePath"
New-Item -ItemType Directory -Path $logPath -Force | Out-Null
$previousJobMode = $env:JOB_MODE
$env:JOB_MODE = 'inprocess'
try {
    if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
        Start-Process -FilePath $pythonPath -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000') -WorkingDirectory $backendPath -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logPath 'api.out.log') -RedirectStandardError (Join-Path $logPath 'api.err.log')
    }
    if (-not (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue)) {
        Start-Process -FilePath $nodePath -ArgumentList @(('"{0}"' -f $vitePath), '--host', '127.0.0.1', '--port', '5173', '--strictPort') -WorkingDirectory $frontendPath -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logPath 'web.out.log') -RedirectStandardError (Join-Path $logPath 'web.err.log')
    }
    Wait-LocalEndpoint 'http://127.0.0.1:8000/api/v1/health'
    Wait-LocalEndpoint 'http://127.0.0.1:5173'
    Write-Host 'App: http://127.0.0.1:5173'
    Write-Host 'API: http://127.0.0.1:8000/docs'
    Write-Host "Server logs: $logPath"
} finally {
    $env:JOB_MODE = $previousJobMode
}
