$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
Write-Host 'AlphaPredictorsAI 2.1 FINAL - setup'
if (-not (Get-Command py -ErrorAction SilentlyContinue) -and -not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Install Python 3.10+ (64-bit) and add it to PATH.' }
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'Install Node.js 22 LTS or later, then restart this terminal.' }
if (-not (Test-Path '.venv\Scripts\python.exe')) {
  if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m venv .venv } else { & python -m venv .venv }
  if ($LASTEXITCODE -ne 0) { throw 'Could not create virtual environment.' }
}
& .\.venv\Scripts\python.exe -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ is required'"
if ($LASTEXITCODE -ne 0) { throw 'Unsupported Python version.' }
& node -e "if(Number(process.versions.node.split('.')[0])<22) process.exit(1)"
if ($LASTEXITCODE -ne 0) { throw 'Node.js 22 or later is required.' }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip update failed.' }
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependencies failed. Check network and Python version.' }
if (-not (Test-Path 'backend\.env')) { Copy-Item backend\.env.example backend\.env }
Push-Location frontend
try {
  & npm.cmd ci
  if ($LASTEXITCODE -ne 0) { throw 'Frontend dependencies failed.' }
  & npm.cmd run build
  if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
Push-Location backend
try {
  & ..\.venv\Scripts\python.exe -c 'from app.database.store import init_db; init_db()'
  if ($LASTEXITCODE -ne 0) { throw 'Database initialization failed.' }
} finally { Pop-Location }
& .\.venv\Scripts\python.exe scripts\launch.py --check
if ($LASTEXITCODE -ne 0) { throw 'Readiness check failed. Close an existing server on port 8000 and rerun.' }
Write-Host 'Setup complete. Run run.bat to start the terminal.' -ForegroundColor Green
