@echo off
cd /d "%~dp0"
REM Mata servidores viejos en nuestro puerto (evita servir codigo antiguo)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8765.*LISTENING"') do taskkill /PID %%a /F >nul 2>&1
start "MF Glyph Mapper web" /min python web\server.py --port 8765
timeout /t 2 >nul
start http://127.0.0.1:8765/
echo Servidor en http://127.0.0.1:8765/ (cierra la ventana minimizada para detenerlo)
