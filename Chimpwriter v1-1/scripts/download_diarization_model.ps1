param(
  [string]$ModelId = "pyannote/speaker-diarization-3.1",
  [string]$TargetDir = "R:\Rookworks\011_AI_Operations\03_Audio\models\pyannote\speaker-diarization-3.1",
  [string]$Token = ""
)

$root = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $root ".venv"
if (-not (Test-Path $venv)) {
  throw "Venv not found. Run scripts\setup.ps1 first."
}

$python = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $python)) {
  throw "Venv python not found at $python"
}

& $python -m pip install -U "huggingface_hub>=0.23" "pyannote.audio>=3.1"

if (-not (Test-Path $TargetDir)) {
  New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
}

if (-not $Token) {
  $Token = Read-Host -Prompt "Enter Hugging Face token"
}

$env:MODEL_ID = $ModelId
$env:TARGET_DIR = $TargetDir
$env:HF_TOKEN = $Token

@'
from huggingface_hub import snapshot_download
import os

model_id = os.environ.get("MODEL_ID")
target_dir = os.environ.get("TARGET_DIR")
token = os.environ.get("HF_TOKEN")

snapshot_download(
    repo_id=model_id,
    local_dir=target_dir,
    local_dir_use_symlinks=False,
    token=token,
)
print(f"Downloaded {model_id} to {target_dir}")
'@ | & $python -
