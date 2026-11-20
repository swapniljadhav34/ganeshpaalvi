@echo off
REM Double-click to build the static website (no prices) for Hostinger shared hosting or any web host.
REM Result: static_site\ folder and static_site.zip — upload the contents to public_html.
cd /d "%~dp0"

set PY=backend\.venv\Scripts\python.exe
if not exist "%PY%" set PY=python

set /p SITEURL=Website address (e.g. https://paalvi.in, or press Enter to skip):

echo.
echo Building the static website...
"%PY%" backend\manage.py export_static_site --site-url "%SITEURL%"
if errorlevel 1 (
  echo.
  echo Build failed - see the messages above.
  pause
  exit /b 1
)

echo.
echo Ready! Upload everything inside the "static_site" folder to public_html
echo (or upload static_site.zip in Hostinger File Manager and Extract it there).
explorer static_site
pause
