@echo off
REM Simple wrapper to run the Python installer inside the current environment
REM Usage: open the venv's prompt (e.g., envjarvis\Scripts\activate) then run this .bat

python -u "%~dp0install_voice_deps.py"
if %ERRORLEVEL% NEQ 0 (
    echo Installer failed. See output above for details.
    pause
) else (
    echo Installer completed successfully.
)
