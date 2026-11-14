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

New-Item -ItemType Directory -Path $logPath -Force | Out-Null
$env:JOB_MODE = 'inprocess'
if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath $pythonPath -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000') -WorkingDirectory $backendPath -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logPath 'api.out.log') -RedirectStandardError (Join-Path $logPath 'api.err.log')
}
if (-not (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue)) {
    $nodePath = (Get-Command node.exe).Source
    Start-Process -FilePath $nodePath -ArgumentList @($vitePath, '--host', '127.0.0.1', '--port', '5173', '--strictPort') -WorkingDirectory $frontendPath -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logPath 'web.out.log') -RedirectStandardError (Join-Path $logPath 'web.err.log')
}
Write-Host 'App: http://127.0.0.1:5173'
Write-Host 'API: http://127.0.0.1:8000/docs'
Write-Host "Server logs: $logPath"
