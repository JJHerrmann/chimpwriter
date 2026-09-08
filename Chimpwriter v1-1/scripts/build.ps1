param(
  [string]$PythonExe = "python"
)

$root = Split-Path -Parent $PSScriptRoot
$icon = Join-Path $root "assets\chimpwriter.ico"
$main = Join-Path $root "app\main.py"

& $PythonExe -m PyInstaller --noconsole --onedir --name Chimpwriter --icon $icon $main
