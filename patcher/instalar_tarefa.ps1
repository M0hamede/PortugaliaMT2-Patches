# Executar depois de fazer Commit + Push dos ficheiros de patcher/.
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
& python (Join-Path $here 'auto_patcher.py') baseline
if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel criar baseline. Faz primeiro Commit + Push de patcher/.' }
$name = 'PortugaliaMT2-PublicadorPatches'
$launcher = Join-Path $here 'verificar_patch.cmd'
$action = New-ScheduledTaskAction -Execute $env:ComSpec -Argument ('/d /c "{0}"' -f $launcher) -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Days 3650)
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 4) -StartWhenAvailable -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Write-Host 'Tarefa instalada:' $name
Write-Host 'Executa a cada minuto enquanto estares com sessao iniciada no Windows.'
Write-Host 'Log:' (Join-Path $env:LOCALAPPDATA 'PortugaliaMT2Patcher\auto.log')
