param([Parameter(Mandatory=$true)][string]$ProjectId,[Parameter(Mandatory=$true)][string]$SessionId,[switch]$InteractionTest)
$ErrorActionPreference='Stop'
$studioRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$config=Get-Content -Encoding UTF8 -LiteralPath (Join-Path $studioRoot 'SystemRuntime\UserData\Launcher\config.json') -Raw | ConvertFrom-Json
if($ProjectId -notmatch '^prj_[a-f0-9-]{36}$'){throw 'Invalid project ID'}
$projectMatches=@(Get-ChildItem -LiteralPath (Join-Path $studioRoot 'Workspace\Projects') -Directory | Where-Object {Test-Path -LiteralPath (Join-Path $_.FullName 'project.json')} | Where-Object {(Get-Content -Encoding UTF8 -LiteralPath (Join-Path $_.FullName 'project.json') -Raw | ConvertFrom-Json).id -eq $ProjectId})
if($projectMatches.Count -ne 1){throw 'Project missing or ambiguous'}
$projectDirectory=$projectMatches[0].FullName
if($SessionId -notmatch '^[a-f0-9-]{36}$'){throw 'Invalid session ID'}
$sessionFile=Join-Path $projectDirectory ('Docs\Codex\'+$SessionId+'.json')
$sessionData=Get-Content -Encoding UTF8 -LiteralPath $sessionFile -Raw | ConvertFrom-Json
if($sessionData.projectId -ne $ProjectId -or $sessionData.directory -ne $projectDirectory){throw 'Session project mismatch'}

Set-Location -LiteralPath $projectDirectory
$Host.UI.RawUI.WindowTitle='Asset Director - '+$projectMatches[0].Name
$nodeExecutable=(Get-Command node.exe -ErrorAction Stop).Source
if($InteractionTest){ & $nodeExecutable (Join-Path $PSScriptRoot 'codex-session.mjs') $ProjectId $SessionId 'interaction-test' } else { & $nodeExecutable (Join-Path $PSScriptRoot 'codex-session.mjs') $ProjectId $SessionId }
