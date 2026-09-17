param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$launcherRoot = $PSScriptRoot
$studioRoot = [IO.Path]::GetFullPath((Join-Path $launcherRoot '..\..'))
$sessionPath = Join-Path $studioRoot 'SystemRuntime\UserData\Launcher\session.json'
$settingsRoot = Split-Path -Parent $sessionPath
function Get-LauncherSession {
    if (-not (Test-Path -LiteralPath $sessionPath)) { return $null }
    try {
        $candidate = Get-Content -LiteralPath $sessionPath -Raw | ConvertFrom-Json
        if ($candidate.origin -notmatch '^http://127\.0\.0\.1:\d+$' -or $candidate.token -notmatch '^[a-f0-9]{64}$' -or $candidate.root -ne $studioRoot) { return $null }
        $response = Invoke-RestMethod -Uri ($candidate.origin + '/api/session') -Headers @{Authorization=('Bearer '+$candidate.token)} -TimeoutSec 2
        if ($response.app -eq 'asset-director-launcher' -and $response.root -eq $studioRoot) { return $candidate }
    } catch { return $null }
    return $null
}
$session = Get-LauncherSession
if (-not $session) {
    $nodeExecutable = (Get-Command node.exe -ErrorAction Stop).Source
    $serverFile = Join-Path $launcherRoot 'server.mjs'
    Start-Process -FilePath $nodeExecutable -ArgumentList @(('"'+$serverFile+'"'),('"'+$studioRoot+'"')) -WorkingDirectory $launcherRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $settingsRoot 'server.log') -RedirectStandardError (Join-Path $settingsRoot 'server-error.log') | Out-Null
    for ($attempt=0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 500
        $session = Get-LauncherSession
        if ($session) { break }
    }
}
if (-not $session) { throw "The launcher did not start. Check $settingsRoot\server-error.log" }
if (-not $NoBrowser) { Start-Process ($session.origin + '/#' + $session.token) }
Write-Output ('Asset Director Launcher is running at ' + $session.origin)
