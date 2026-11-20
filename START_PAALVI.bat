@echo off
REM Double-click to run the whole Paalvi app on this computer: website, Designer (admin) and Studio.
REM Needs Python 3.12+ and Node.js 20+ installed. The first run sets everything up (a few minutes).
cd /d "%~dp0"
set PY=backend\.venv\Scripts\python.exe

if not exist "%PY%" (
  echo First-time setup: installing the app...
  python -m venv backend\.venv || goto :fail
  "%PY%" -m pip install -q -r backend\requirements.txt || goto :fail
  if not exist backend\.env echo DJANGO_DEBUG=true> backend\.env
  "%PY%" backend\manage.py migrate --noinput || goto :fail
  "%PY%" backend\manage.py seed_themes
  echo.
  echo Create the owner login for the Designer and Studio:
  "%PY%" backend\manage.py createsuperuser
)

if not exist frontend\dist\index.html (
  echo Building the website...
  pushd frontend
  call npm install || goto :fail
  call npm run build || goto :fail
  popd
)

set SITE_URL=http://127.0.0.1:8000
set STAFF_URL=http://127.0.0.1:8000
"%PY%" backend\manage.py migrate --noinput >nul
REM Cached pages may hold photo links from another address; start fresh.
"%PY%" backend\manage.py shell -c "from django.core.cache import cache; cache.clear()" >nul
echo.
echo Paalvi is running. Keep this window open; close it to stop.
echo   Website:  http://127.0.0.1:8000/
echo   Designer: http://127.0.0.1:8000/admin/
echo   Studio:   http://127.0.0.1:8000/studio
start "" http://127.0.0.1:8000/
"%PY%" backend\manage.py runserver 8000
exit /b 0

:fail
echo.
echo Setup failed - see the messages above. Is Python 3.12+ and Node.js 20+ installed?
pause
exit /b 1
