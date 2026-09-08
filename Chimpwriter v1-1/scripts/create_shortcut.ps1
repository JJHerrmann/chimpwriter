$root = Split-Path -Parent $PSScriptRoot
$icon = Join-Path $root "assets\chimpwriter.ico"
$desktop = [Environment]::GetFolderPath("Desktop")
$exe = Join-Path $root "dist\Chimpwriter\Chimpwriter.exe"
$bat = Join-Path $root "Chimpwriter.bat"

function New-Shortcut([string]$Target, [string]$LinkPath, [string]$IconPath) {
  $wsh = New-Object -ComObject WScript.Shell
  $shortcut = $wsh.CreateShortcut($LinkPath)
  $shortcut.TargetPath = $Target
  $shortcut.WorkingDirectory = Split-Path $Target -Parent
  if (Test-Path $IconPath) { $shortcut.IconLocation = $IconPath }
  $shortcut.Save()
}

if (Test-Path $exe) {
  $lnkExe = Join-Path $desktop "Chimpwriter.lnk"
  New-Shortcut -Target $exe -LinkPath $lnkExe -IconPath $icon
}

if (Test-Path $bat) {
  $lnkBat = Join-Path $desktop "Chimpwriter (Launcher).lnk"
  New-Shortcut -Target $bat -LinkPath $lnkBat -IconPath $icon
}
