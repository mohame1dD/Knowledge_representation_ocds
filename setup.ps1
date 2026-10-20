# Windows version of setup.sh. Run in PowerShell:  .\setup.ps1
# Stops with a clear message if any install step fails.
function Check($what) { if ($LASTEXITCODE -ne 0) { throw "Setup failed at: $what (see the error above)" } }

python -m venv .venv;                                  Check "creating .venv"
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip;                   Check "upgrading pip"
pip install -r requirements.txt;                       Check "requirements.txt"
pip install --no-deps morph-kgc==2.8.1;                Check "morph-kgc"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
Write-Host "Done. Activate with: .\.venv\Scripts\Activate.ps1"
