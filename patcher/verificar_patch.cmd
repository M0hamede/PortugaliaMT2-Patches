@echo off
setlocal

set "GIT_PAGER=cat"

rem Localizar o Git incluido no GitHub Desktop
for /d %%D in ("%LOCALAPPDATA%\GitHubDesktop\app-*") do (
    if exist "%%~fD\resources\app\git\cmd\git.exe" (
        set "PATH=%%~fD\resources\app\git\cmd;%PATH%"
    )
)

rem Criar pasta de logs
if not exist "%LOCALAPPDATA%\PortugaliaMT2Patcher" (
    mkdir "%LOCALAPPDATA%\PortugaliaMT2Patcher"
)

rem Executar o publicador automatico
python "%~dp0auto_patcher.py" run >> "%LOCALAPPDATA%\PortugaliaMT2Patcher\auto.log" 2>&1

exit /b %ERRORLEVEL%