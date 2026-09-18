# Open the real workbench using the existing authenticated loopback launcher.
# Starting a browser is not verification of native Blender or Codex readiness.
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'Start Launcher.ps1') -NoBrowser
$studioRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$sessionFile = Join-Path $studioRoot 'SystemRuntime\UserData\Launcher\session.json'
$session = Get-Content -LiteralPath $sessionFile -Raw | ConvertFrom-Json
if ($session.origin -notmatch '^http://127\.0\.0\.1:\d+$' -or $session.token -notmatch '^[a-f0-9]{64}$' -or $session.root -ne $studioRoot) {
    throw 'Invalid launcher session. Reopen the Start shortcut.'
}
$verified = Invoke-RestMethod -Uri ($session.origin + '/api/session') -Headers @{Authorization=('Bearer '+$session.token)} -TimeoutSec 5
if ($verified.app -ne 'asset-director-launcher' -or $verified.root -ne $studioRoot) {
    throw 'Launcher session belongs to another studio.'
}
Start-Process ($session.origin + '/workbench#' + $session.token)
