# setup.ps1 - One-command Windows setup for dex_trade_bot
#
# Usage (from the repo root, in PowerShell):
#     ./setup.ps1
#
# If PowerShell blocks the script, allow local scripts once:
#     Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
#
# This checks for Python, creates an isolated venv, installs dependencies, and
# prepares your .env. It does NOT install Python or any system software for you.

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "=== dex_trade_bot Windows setup ===" -ForegroundColor Cyan

# 1. Find a Python interpreter (prefer the 'py' launcher, fall back to 'python').
function Get-PythonCmd {
    foreach ($candidate in @("py", "python")) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($cmd) {
            # The Windows Store stub returns nothing useful; check it really runs.
            try {
                & $candidate --version *> $null
                if ($LASTEXITCODE -eq 0) { return $candidate }
            } catch { }
        }
    }
    return $null
}

$python = Get-PythonCmd
if (-not $python) {
    Write-Host "Python was not found." -ForegroundColor Red
    Write-Host "Install it, then re-run ./setup.ps1 :"
    Write-Host "    winget install Python.Python.3.12" -ForegroundColor Yellow
    Write-Host "  or download from https://www.python.org/downloads/ and tick 'Add python.exe to PATH'."
    Write-Host "  (If 'python' opens the Microsoft Store, disable the alias in"
    Write-Host "   Settings > Apps > Advanced app settings > App execution aliases.)"
    exit 1
}
Write-Host "Using Python: $python ($(& $python --version 2>&1))" -ForegroundColor Green

# 2. Create the virtual environment if it does not exist.
$venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtual environment in .\venv ..."
    & $python -m venv venv
    if ($LASTEXITCODE -ne 0) { Write-Host "Failed to create venv." -ForegroundColor Red; exit 1 }
} else {
    Write-Host "Virtual environment already exists, reusing .\venv"
}

# 3. Install dependencies into the venv (use the venv's own python; no activation needed).
Write-Host "Upgrading pip and installing dependencies ..."
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements-dex.txt
if ($LASTEXITCODE -ne 0) { Write-Host "Dependency install failed." -ForegroundColor Red; exit 1 }

# 4. Prepare .env from the template if missing.
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example." -ForegroundColor Green
    Write-Host "  -> Edit .env and set WALLET_ADDRESS (keep EXECUTION_MODE=paper to start)." -ForegroundColor Yellow
} else {
    Write-Host ".env already exists, leaving it as-is."
}

# 5. Next steps.
Write-Host ""
Write-Host "=== Setup complete ===" -ForegroundColor Cyan
Write-Host "Next:"
Write-Host "  1) notepad .env        # set WALLET_ADDRESS"
Write-Host "  2) ./run.ps1 --check   # confirm everything is reachable"
Write-Host "  3) ./run.ps1           # run the bot (paper mode)"
Write-Host "  4) ./run.ps1 dashboard # open http://127.0.0.1:8080 in your browser"
