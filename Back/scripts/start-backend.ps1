[CmdletBinding()]
param(
    [string]$ApiHost = '127.0.0.1',
    [ValidateRange(1, 65535)][int]$ApiPort = 8000,
    [switch]$WithoutScheduler
)
$ErrorActionPreference = 'Stop'
$backendRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$pythonPath = Join-Path $backendRoot '.venv\Scripts\python.exe'
$localFolder = Join-Path $backendRoot '.local'
$logFolder = Join-Path $localFolder 'logs'
$manifestPath = Join-Path $localFolder 'backend-processes.json'

if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Python virtual environment is missing. Follow Back/README.md first.' }
if (-not (Test-Path -LiteralPath (Join-Path $backendRoot '.env'))) { throw 'Back/.env is missing. Configure PostgreSQL, MinIO and JWT first.' }
if (Test-Path -LiteralPath $manifestPath) {
    $previous = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    foreach ($entry in $previous.processes) {
        $running = Get-Process -Id ([int]$entry.process_id) -ErrorAction SilentlyContinue
        if ($running -and ([string]$running.StartTime.ToUniversalTime().Ticks -eq [string]$entry.start_time_ticks)) {
            throw 'A previously started backend is still running. Use scripts/stop-backend.ps1 first.'
        }
    }
}
if (Get-NetTCPConnection -LocalPort $ApiPort -State Listen -ErrorAction SilentlyContinue) {
    throw "Port $ApiPort is already in use. No existing process has been stopped."
}
New-Item -ItemType Directory -Path $logFolder -Force | Out-Null
$launches = @(
    @{ role = 'api'; args = @('-m', 'uvicorn', 'app.main:app', '--host', $ApiHost, '--port', [string]$ApiPort) },
    @{ role = 'worker'; args = @('-m', 'app.workers.main') }
)
if (-not $WithoutScheduler) {
    $launches += @{ role = 'scheduler'; args = @('-m', 'app.workers.scheduler') }
}
$started = @()
try {
    foreach ($entry in $launches) {
        $process = Start-Process -FilePath $pythonPath -ArgumentList $entry.args -WorkingDirectory $backendRoot `
            -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logFolder ($entry.role + '.out.log')) `
            -RedirectStandardError (Join-Path $logFolder ($entry.role + '.err.log')) -PassThru
        $started += [PSCustomObject]@{
            role = $entry.role
            process_id = $process.Id
            start_time_ticks = [string]$process.StartTime.ToUniversalTime().Ticks
            executable = $pythonPath
        }
    }
    [PSCustomObject]@{ backend_root = $backendRoot; started_at = [DateTime]::UtcNow.ToString('o'); processes = $started } |
        ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    Start-Sleep -Seconds 2
    foreach ($entry in $started) {
        if (-not (Get-Process -Id $entry.process_id -ErrorAction SilentlyContinue)) {
            throw ($entry.role + ' exited during startup. See .local/logs for details.')
        }
    }
    Write-Host "Started API, worker and selected scheduler. API: http://${ApiHost}:$ApiPort/docs"
    Write-Host 'Logs: Back/.local/logs. Stop with scripts/stop-backend.ps1.'
} catch {
    # Stop only processes that this invocation created, after identity checks.
    foreach ($entry in $started) {
        $running = Get-Process -Id $entry.process_id -ErrorAction SilentlyContinue
        if ($running -and ([string]$running.StartTime.ToUniversalTime().Ticks -eq $entry.start_time_ticks)) {
            Stop-Process -Id $entry.process_id -ErrorAction SilentlyContinue
        }
    }
    throw
}
