# (Re)crea el acceso directo del escritorio: iniciar.vbs + icono propio.
$ws = New-Object -ComObject WScript.Shell
$desk = [Environment]::GetFolderPath("Desktop")
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$lnk = $ws.CreateShortcut("$desk\MF Glyph Mapper.lnk")
$lnk.TargetPath = Join-Path $root "iniciar.vbs"
$lnk.WorkingDirectory = $root
$lnk.Description = "MF Glyph Mapper - indices reales, Manim"
$lnk.IconLocation = (Join-Path $root "assets\icon.ico") + ",0"
$lnk.Save()
Write-Output "OK"
