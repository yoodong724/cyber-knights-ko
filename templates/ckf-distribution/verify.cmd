@echo off
setlocal DisableDelayedExpansion
set "CKF_PACKAGE=%~dp0"
powershell.exe -NoLogo -NoProfile -Command "try { Add-Type -Path (Join-Path $env:CKF_PACKAGE 'Patch.cs') -ReferencedAssemblies System.dll,System.Core.dll,System.Web.Extensions.dll; exit [CkfPatch]::Run($env:CKF_PACKAGE,'verify',$true) } catch { Write-Host $_; exit 1 }"
set "CKF_RESULT=%ERRORLEVEL%"
if not "%CKF_NONINTERACTIVE%"=="1" pause
exit /b %CKF_RESULT%
