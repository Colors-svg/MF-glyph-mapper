@echo off
REM MF Glyph Mapper — app de escritorio (servidor local + ventana propia).
setlocal
cd /d %~dp0
set PORT=8765
set URL=http://127.0.0.1:%PORT%/
echo [MF] Deteniendo servidor anterior (si lo hay)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | Where-Object { $_.CommandLine -match 'web[\\/]server\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo [MF] Iniciando servidor en %URL% ...
start "MF Glyph Mapper (servidor)" /min python -u web\server.py --port %PORT%
echo [MF] Esperando al servidor...
for /l %%i in (1,1,30) do (
  powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing %URL% -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
  if not errorlevel 1 goto listo
  timeout /t 2 /nobreak >nul
)
echo [MF] El servidor no respondio; revisa la ventana "MF Glyph Mapper (servidor)".
pause
exit /b 1
:listo
echo [MF] Abriendo ventana de la app...
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
  start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" --app=%URL% --user-data-dir="%LOCALAPPDATA%\MF-Glyph-Mapper-App" --class=MF-Glyph-Mapper
  exit /b 0
)
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
  start "" "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" --app=%URL% --user-data-dir="%LOCALAPPDATA%\MF-Glyph-Mapper-App" --class=MF-Glyph-Mapper
  exit /b 0
)
if exist "%ProgramW6432%\Microsoft\Edge\Application\msedge.exe" (
  start "" "%ProgramW6432%\Microsoft\Edge\Application\msedge.exe" --app=%URL% --user-data-dir="%LOCALAPPDATA%\MF-Glyph-Mapper-App"
  exit /b 0
)
start "" %URL%
