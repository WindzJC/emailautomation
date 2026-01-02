@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "SCRIPT=%SCRIPT_DIR%check_pending.py"
if not exist "%SCRIPT%" (
  echo check_pending.py not found in %SCRIPT_DIR%
  exit /b 1
)
py -3 "%SCRIPT%" %*
if errorlevel 1 (
  python "%SCRIPT%" %*
)
EOF

cat <<'EOF' > 'email automation/run_check_pending.ps1'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script = Join-Path $ScriptDir "check_pending.py"
if (-not (Test-Path $Script)) {
  Write-Error "check_pending.py not found in $ScriptDir"
  exit 1
}

py -3 $Script @args
if ($LASTEXITCODE -ne 0) {
  python $Script @args
}
