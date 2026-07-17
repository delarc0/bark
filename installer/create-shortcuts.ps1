$barkDir = Split-Path -Parent $PSScriptRoot
if (-not $barkDir -or -not (Test-Path $barkDir)) {
    Write-Error "Cannot resolve the Bark repo root. Run this script from its file (not piped): powershell -File installer\create-shortcuts.ps1"
    exit 1
}
$target = Join-Path $barkDir "launch.vbs"
$icon = Join-Path $barkDir "icon.ico"

$ws = New-Object -ComObject WScript.Shell

# Desktop shortcut
$desktop = [Environment]::GetFolderPath("Desktop")
$lnk = $ws.CreateShortcut("$desktop\Bark.lnk")
$lnk.TargetPath = $target
$lnk.WorkingDirectory = $barkDir
$lnk.IconLocation = "$icon,0"
$lnk.Description = "Bark - Voice Dictation"
$lnk.Save()
Write-Host "Desktop shortcut: $desktop\Bark.lnk"

# Start Menu shortcut
$startMenu = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs"
$lnk2 = $ws.CreateShortcut("$startMenu\Bark.lnk")
$lnk2.TargetPath = $target
$lnk2.WorkingDirectory = $barkDir
$lnk2.IconLocation = "$icon,0"
$lnk2.Description = "Bark - Voice Dictation"
$lnk2.Save()
Write-Host "Start Menu shortcut: $startMenu\Bark.lnk"

Write-Host "`nDone - Bark should now appear in Start Menu search and on your Desktop."
