[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$backendRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$pythonPath = Join-Path $backendRoot '.venv\Scripts\python.exe'
$manifestPath = Join-Path $backendRoot '.local\backend-processes.json'
if (-not (Test-Path -LiteralPath $manifestPath)) {
    Write-Host 'No process manifest was found. Services started manually are not affected.'
    return
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.backend_root -ne $backendRoot) { throw 'Process manifest belongs to another backend directory.' }
foreach ($entry in $manifest.processes) {
    $running = Get-Process -Id ([int]$entry.process_id) -ErrorAction SilentlyContinue
    if (-not $running) { continue }
    $sameStart = [string]$running.StartTime.ToUniversalTime().Ticks -eq [string]$entry.start_time_ticks
    $sameExecutable = $running.Path -eq $pythonPath
    if (-not ($sameStart -and $sameExecutable)) {
        Write-Warning ('Skipped process ' + $entry.process_id + ': identity no longer matches the original service.')
        continue
    }
    Stop-Process -Id $entry.process_id
    Write-Host ('Stopped ' + $entry.role)
}
Remove-Item -LiteralPath $manifestPath
Write-Host 'Service process records removed. Database, MinIO files and local credentials were not deleted.'
