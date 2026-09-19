# New-only candidate setup. No downloads, provider changes, or production replacement.
param([string]$StudioPath='', [string]$FromStudio='', [string]$PythonPath='',
      [string]$BlenderPath='', [string]$CodexPath='', [string]$FFmpegPath='', [string]$FFprobePath='')
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
Write-Host 'Asset Director - isolated candidate setup'
Write-Host 'Your existing studio and assets will not be changed or copied.'
if(-not $FromStudio -and -not $PythonPath){$FromStudio=Read-Host 'Existing studio folder to read executable paths (or Enter to choose tools)'}
$config=@{}
if($FromStudio){
 $file=Join-Path $FromStudio 'SystemRuntime\UserData\Launcher\config.json'
 if(-not (Test-Path -LiteralPath $file -PathType Leaf)){throw 'Existing studio config was not found. Nothing was changed.'}
 $settings=Get-Content -LiteralPath $file -Raw | ConvertFrom-Json
 foreach($key in @('python','blender','codex','ffmpeg','ffprobe')){
  if($settings.PSObject.Properties.Name -contains $key){$config[$key]=[string]$settings.$key}
 }
}
foreach($entry in @(@('python',$PythonPath),@('blender',$BlenderPath),@('codex',$CodexPath),@('ffmpeg',$FFmpegPath),@('ffprobe',$FFprobePath))){
 if($entry[1]){$config[$entry[0]]=$entry[1]}
}
foreach($key in @('python','blender','codex','ffmpeg','ffprobe')){
 if(-not $config[$key]){
  $config[$key]=Read-Host "Absolute path to existing $key executable (no software will be downloaded)"
 }
 if(-not [IO.Path]::IsPathRooted($config[$key]) -or -not (Test-Path -LiteralPath $config[$key] -PathType Leaf)){throw "Invalid $key executable path"}
}
if(-not (Get-Command node.exe -ErrorAction SilentlyContinue)){throw 'Node.js is required on PATH. This setup does not install it.'}
if(-not $StudioPath){$StudioPath=Read-Host 'New studio folder (must not already exist)'}
if(-not [IO.Path]::IsPathRooted($StudioPath) -or (Test-Path -LiteralPath $StudioPath)){throw 'Choose a new absolute directory. Existing studios are never overwritten.'}
$arguments=@((Join-Path $root 'tools\install_workbench_candidate.py'),'--root',$StudioPath)
foreach($key in @('python','blender','codex','ffmpeg','ffprobe')){$arguments+=@('--'+$key,$config[$key])}
& $config.python @arguments
if($LASTEXITCODE -ne 0){throw 'Candidate setup failed. Preserve its diagnostic directory; the previous studio was not changed.'}
Write-Host "Created candidate. Open: $StudioPath\Open Workbench.cmd"
Write-Host 'No app was launched. Validate the new studio before using it for important work.'
