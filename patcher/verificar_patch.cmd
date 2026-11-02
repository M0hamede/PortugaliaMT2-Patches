@echo off
setlocal

rem Git do GitHub Desktop
set "GIT_PAGER=cat"

for /d %%D in ("%LOCALAPPDATA%\GitHubDesktop\app-*") do (
    if exist "%%~fD\resources\app\git\cmd\git.exe" (
        set "PATH=%%~fD\resources\app\git\cmd;%PATH%"
    )
)

rem Pasta de logs
if not exist "%LOCALAPPDATA%\PortugaliaMT2Patcher" (
    mkdir "%LOCALAPPDATA%\PortugaliaMT2Patcher"
)

rem Executar publicador
python "D:\Games\DEV\Metin2FullClient\patcher\auto_patcher.py" run >> "%LOCALAPPDATA%\PortugaliaMT2Patcher\auto.log" 2>&1

exit /b %ERRORLEVEL%