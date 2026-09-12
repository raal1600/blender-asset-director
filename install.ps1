#requires -Version 5.1
<#
Install a pinned Blender Asset Director release for local Codex.
No Git, administrator, provider key, or global execution-policy change is required.
Requires Python 3.11+. Existing Codex/MCP/Blender settings are never rewritten.
#>
[CmdletBinding()]
param(
    [ValidatePattern('^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?$')][string]$Version = '0.2.2',
    [string]$PythonPath,
    [string]$BlenderPath,
    [string]$LibraryPath,
    [string]$SkillPath,
    [switch]$Update,
    [string]$Archive,
    [string]$Sha256
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$tempDir = $null
try {
    if ([bool]$Archive -ne [bool]$Sha256) { throw '-Archive and -Sha256 must be supplied together.' }
    $candidates = @()
    if ($PythonPath) {
        if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) { throw '-PythonPath does not exist.' }
        $candidates += @{ Exe = $PythonPath; Prefix = @() }
    } else {
        foreach ($name in @('py', 'python', 'python3')) {
            $cmd = Get-Command $name -ErrorAction SilentlyContinue
            if ($null -ne $cmd -and $cmd.Source -and $cmd.Source -notlike '*\WindowsApps\*') {
                $prefix = @(); if ($name -eq 'py') { $prefix = @('-3') }
                $candidates += @{ Exe = $cmd.Source; Prefix = $prefix }
            }
        }
    }
    $chosen = $null
    foreach ($candidate in $candidates) {
        $exe = $candidate.Exe; $prefix = $candidate.Prefix
        & $exe @prefix -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) { $chosen = $candidate; break }
    }
    if ($null -eq $chosen) {
        throw 'Python 3.11+ was not found. Install it from https://www.python.org/downloads/, reopen PowerShell, and retry; or use -PythonPath with your interpreter. Nothing was installed.'
    }
    $tempDir = Join-Path ([IO.Path]::GetTempPath()) ('bad-bootstrap-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tempDir | Out-Null
    $bootstrap = Join-Path $tempDir 'install.py'
    if ($Archive) {
        $localBootstrap = Join-Path $PSScriptRoot 'install.py'
        if (-not (Test-Path -LiteralPath $localBootstrap -PathType Leaf)) { throw 'Offline installation needs install.py beside install.ps1.' }
        Copy-Item -LiteralPath $localBootstrap -Destination $bootstrap
    } else {
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        $url = "https://raw.githubusercontent.com/raal1600/blender-asset-director/v$Version/install.py"
        Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $bootstrap -TimeoutSec 60
    }
    $argsList = @($bootstrap, '--version', $Version)
    if ($Update) { $argsList += '--update' }
    foreach ($pair in @(@('--dest', $SkillPath), @('--library', $LibraryPath), @('--blender', $BlenderPath), @('--archive', $Archive), @('--sha256', $Sha256))) {
        if ($pair[1]) { $argsList += $pair }
    }
    $exe = $chosen.Exe; $prefix = $chosen.Prefix
    & $exe @prefix @argsList
    if ($LASTEXITCODE -ne 0) { throw "Installer returned exit code $LASTEXITCODE. See the error above." }
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
} finally {
    if ($tempDir -and (Test-Path -LiteralPath $tempDir)) { Remove-Item -LiteralPath $tempDir -Recurse -Force }
}
