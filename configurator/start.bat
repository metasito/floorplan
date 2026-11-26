@echo off
rem Double-click to open the Unit 13 configurator. Close this window to stop the server.
rem First run sets up .venv with the Python packages (needs Python: install from python.org).
cd /d "%~dp0.."
set URL=http://localhost:8013
rem Already running (double-clicked twice)? Just open the browser.
curl -s -o nul %URL%/api/jobs && (start "" %URL% & exit /b)
if not exist .venv\Scripts\python.exe (
  echo First run: setting up Python packages, this takes a minute or two...
  python -m venv .venv || goto fail
  .venv\Scripts\python -m pip install -q -r requirements.txt || goto fail
)
rem Open the browser two seconds from now, once the server is up.
start "" /b cmd /c "ping -n 3 127.0.0.1 >nul & start "" %URL%"
echo Configurator running at %URL%. Keep this window open while you work and render.
.venv\Scripts\python configurator\server.py
pause
exit /b
:fail
echo Setup failed. Is Python installed from python.org, with "Add python.exe to PATH" ticked?
pause
