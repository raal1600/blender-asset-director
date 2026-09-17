param([switch]$RestoreDependencies)
$ErrorActionPreference = 'Stop'
$launcherRoot = Split-Path -Parent $PSScriptRoot
if ($RestoreDependencies) {
    $dependencyRoot = Join-Path $launcherRoot '.deps'
    New-Item -ItemType Directory -Path $dependencyRoot -Force | Out-Null
    $archive = Join-Path $dependencyRoot 'webview2-1.0.3800.47.zip'
    Invoke-WebRequest -Uri 'https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/1.0.3800.47/microsoft.web.webview2.1.0.3800.47.nupkg' -OutFile $archive
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne '56C9F26BDD07916A2D1949FB58A5C7E434DFA1173577DCA879206050C4E718DB') { throw 'WebView2 package checksum mismatch' }
    $sdk = Join-Path $dependencyRoot 'webview2-1.0.3800.47'
    Expand-Archive -LiteralPath $archive -DestinationPath $sdk -Force
    foreach ($dll in @('Microsoft.Web.WebView2.Core.dll','Microsoft.Web.WebView2.WinForms.dll')) {
        Copy-Item -LiteralPath (Join-Path $sdk ('lib\net462\'+$dll)) -Destination (Join-Path $launcherRoot $dll) -Force
    }
    Copy-Item -LiteralPath (Join-Path $sdk 'runtimes\win-x64\native\WebView2Loader.dll') -Destination $launcherRoot -Force
}
foreach ($dll in @('Microsoft.Web.WebView2.Core.dll','Microsoft.Web.WebView2.WinForms.dll','WebView2Loader.dll')) {
    if (-not (Test-Path -LiteralPath (Join-Path $launcherRoot $dll))) { throw 'WebView2 dependencies missing. Run this build with -RestoreDependencies.' }
}
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
& $compiler /nologo /target:winexe /platform:x64 /optimize+ /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll ('/reference:'+(Join-Path $launcherRoot 'Microsoft.Web.WebView2.Core.dll')) ('/reference:'+(Join-Path $launcherRoot 'Microsoft.Web.WebView2.WinForms.dll')) ('/out:' + (Join-Path $launcherRoot 'Asset Director.exe')) (Join-Path $PSScriptRoot 'AssetDirectorLauncher.cs')
if ($LASTEXITCODE -ne 0) { throw 'Desktop launcher compilation failed' }
