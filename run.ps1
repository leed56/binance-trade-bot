# run.ps1 - Convenience launcher for dex_trade_bot on Windows.
#
#   ./run.ps1 --check     # pre-flight connectivity & config check
#   ./run.ps1             # run the bot (paper mode by default)
#   ./run.ps1 --once      # run a single cycle
#   ./run.ps1 dashboard   # start the PnL dashboard at http://127.0.0.1:8080
#
# Runs inside the project venv created by ./setup.ps1 - no activation needed.

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "No virtual environment found. Run ./setup.ps1 first." -ForegroundColor Red
    exit 1
}

if ($args.Count -ge 1 -and $args[0] -eq "dashboard") {
    $rest = @($args | Select-Object -Skip 1)
    & $venvPython -m dex_trade_bot.dashboard @rest
} else {
    & $venvPython -m dex_trade_bot @args
}
exit $LASTEXITCODE
