param([Parameter(Mandatory=$true)][int]$ProcessIdentifier,[Parameter(Mandatory=$true)][string]$Executable)
$ErrorActionPreference='Stop'
$process=Get-Process -Id $ProcessIdentifier -ErrorAction Stop
if ([IO.Path]::GetFullPath($process.Path) -ne [IO.Path]::GetFullPath($Executable)) {throw 'Process executable does not match the configured Blender.'}
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
using System.Collections.Generic;
public static class LauncherWindow {
 public delegate bool Callback(IntPtr h, IntPtr p);
 [DllImport("user32.dll")] public static extern bool EnumWindows(Callback cb, IntPtr p);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint id);
 [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr h, int n);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr h,StringBuilder s,int n);
 public static IntPtr Find(int pid) {
   IntPtr result=IntPtr.Zero;
   EnumWindows((h,p)=>{uint id;GetWindowThreadProcessId(h,out id);if(id==(uint)pid){var c=new StringBuilder(256);GetClassName(h,c,256);if(c.ToString().Contains("GHOST")){result=h;return false;}}return true;},IntPtr.Zero);
   return result;
 }
}
"@
$handle=[LauncherWindow]::Find($ProcessIdentifier)
if ($handle -eq [IntPtr]::Zero) { @{visible=$false;focused=$false;processId=$ProcessIdentifier;reason='No Blender editor window found.'} | ConvertTo-Json -Compress; exit 0 }
[LauncherWindow]::ShowWindowAsync($handle,9) | Out-Null
Start-Sleep -Milliseconds 150
[LauncherWindow]::SetForegroundWindow($handle) | Out-Null
@{visible=[LauncherWindow]::IsWindowVisible($handle);focused=([LauncherWindow]::GetForegroundWindow() -eq $handle);processId=$ProcessIdentifier} | ConvertTo-Json -Compress
