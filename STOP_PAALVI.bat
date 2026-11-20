@echo off
REM Double-click to stop Paalvi: the app from START_PAALVI.bat (port 8000) and any local test servers (ports 5173, 5000).
powershell -NoProfile -Command "$found = $false; foreach ($port in 8000, 5173, 5000) { foreach ($c in Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { $p = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue; if ($p -and $p.ProcessName -in 'python', 'node') { taskkill /PID $p.Id /T /F | Out-Null; Write-Host ('Stopped Paalvi on port ' + $port); $found = $true } } }; if (-not $found) { Write-Host 'Paalvi is not running.' }"
timeout /t 4 >nul
