param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("switch-to-mac", "switch-to-windows", "switch-to-cloud", "status", "verify", "activate", "rollback")]
    [string]$Command,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

$WslRepo = if ($env:HANDOFF_WINDOWS_REPO) { $env:HANDOFF_WINDOWS_REPO } else { "/home/jc/email-automation" }
$QuotedArgs = (@($Command) + $RemainingArgs) | ForEach-Object {
    "'" + ($_ -replace "'", "'\''") + "'"
}
$BashCommand = "cd '$WslRepo' && ./handoff " + ($QuotedArgs -join " ")

& wsl.exe bash -lc $BashCommand
exit $LASTEXITCODE
