param(
  [string]$PythonExe = "py"
)

$root = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $root ".venv"
$requirements = Join-Path $root "requirements.txt"

if (-not (Test-Path $venv)) {
  Write-Host "Creating venv at $venv"
  & $PythonExe -m venv $venv
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to create venv. Ensure Python 3.11+ is installed."
  }
}

$python = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $python)) {
  throw "Venv python not found at $python"
}

& $python -m pip install -U pip
if (Test-Path $requirements) {
  & $python -m pip install -r $requirements
} else {
  Write-Warning "requirements.txt not found; skipping dependency install."
}

$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ffmpeg) {
  Write-Warning "ffmpeg not found in PATH. Install ffmpeg and reopen the terminal."
} else {
  Write-Host "ffmpeg found: $($ffmpeg.Path)"
}
