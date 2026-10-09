@echo off
setlocal
cd /d "%~dp0"

rem Use a locally installed Python. No Conda installation is required.
if defined PYTHON (
    "%PYTHON%" "%~dp0prepare_build_env.py" %*
    goto :result
)

rem Windows Python Launcher, if available.
py -3 -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if not errorlevel 1 (
    py -3 "%~dp0prepare_build_env.py" %*
    goto :result
)

rem Standard Python installation / PATH.
python -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if not errorlevel 1 (
    python "%~dp0prepare_build_env.py" %*
    goto :result
)

echo [ERROR] Python 3.10+ could not be found.
echo Install Python from https://www.python.org/downloads/
echo On Windows, select "Add Python to PATH" during installation.
echo Then reopen this script.
set "BUILD_EXIT=1"
goto :finish

:result
set "BUILD_EXIT=%ERRORLEVEL%"

:finish
if not "%BUILD_EXIT%"=="0" (
    echo.
    echo Build failed. See the error above.
    if not defined CI pause
)
exit /b %BUILD_EXIT%
