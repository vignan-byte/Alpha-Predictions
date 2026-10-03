$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Run setup.bat first to create the Python environment.' }
if (-not (Test-Path 'frontend\dist\index.html')) { throw 'Frontend build missing. Run setup.bat first.' }
& $python (Join-Path $PSScriptRoot 'scripts\launch.py')
if ($LASTEXITCODE -ne 0) { throw 'Startup failed. See the diagnostic above.' }
