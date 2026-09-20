param([Parameter(Mandatory=$true)][string]$ProjectId,[Parameter(Mandatory=$true)][string]$SessionId,[switch]$InteractionTest)
$ErrorActionPreference='Stop'
if($ProjectId -notmatch '^prj_[a-f0-9-]{36}$'){throw 'Invalid project ID'}
if($SessionId -notmatch '^[a-f0-9-]{36}$'){throw 'Invalid session ID'}
$script=Join-Path $PSScriptRoot 'project-session.ps1'
$terminalArgs=@('-NoProfile','-NoExit','-ExecutionPolicy','Bypass','-File',('"'+$script+'"'),'-ProjectId',$ProjectId,'-SessionId',$SessionId)
if($InteractionTest){$terminalArgs+='-InteractionTest'}
$child=Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -ArgumentList $terminalArgs -WindowStyle Normal -PassThru
@{processId=$child.Id} | ConvertTo-Json -Compress
