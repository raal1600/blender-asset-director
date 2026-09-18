# Only for disposable acceptance desktops. Never run over a user's working session.
param([Parameter(Mandatory=$true)][int]$ProcessIdentifier,
 [Parameter(Mandatory=$true)][ValidateSet('observe','close','button','move','checkpoint','capture')][string]$Action,
 [string]$Text='', [string]$OutputPath='', [int]$X=0, [int]$Y=0)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class NativeWindow {
 public delegate bool Callback(IntPtr h,IntPtr p);
 [StructLayout(LayoutKind.Sequential)] public struct Point {public int x,y;}
 [StructLayout(LayoutKind.Sequential)] public struct Rect {public int left,top,right,bottom;}
 [DllImport("user32.dll")] public static extern bool EnumWindows(Callback c,IntPtr p);
 [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr h,Callback c,IntPtr p);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h,out uint p);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr h,int n);
 [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h,uint m,IntPtr w,IntPtr l);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h,out Rect r);
 [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h,out Rect r);
 [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h,ref Point p);
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h,StringBuilder s,int n);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr h,StringBuilder s,int n);
 public static string Title(IntPtr h){var s=new StringBuilder(512);GetWindowText(h,s,512);return s.ToString();}
 public static string Class(IntPtr h){var s=new StringBuilder(256);GetClassName(h,s,256);return s.ToString();}
 public static IntPtr[] Find(int pid){var r=new List<IntPtr>();EnumWindows((h,p)=>{uint id;GetWindowThreadProcessId(h,out id);if(id==pid&&Title(h).Length>0)r.Add(h);return true;},IntPtr.Zero);return r.ToArray();}
 public static IntPtr Button(IntPtr parent,string text){IntPtr r=IntPtr.Zero;EnumChildWindows(parent,(h,p)=>{if(Title(h)==text){r=h;return false;}return true;},IntPtr.Zero);return r;}
}
'@
$handles=@([NativeWindow]::Find($ProcessIdentifier))
if($Action -eq 'observe') {
 $records=@($handles | ForEach-Object { @{title=[NativeWindow]::Title($_);class=[NativeWindow]::Class($_);visible=[NativeWindow]::IsWindowVisible($_)} })
 @{windows=$records} | ConvertTo-Json -Depth 5 -Compress; exit 0
}
$handle=$handles | Where-Object { [NativeWindow]::IsWindowVisible($_) -and ($Text -eq '' -or [NativeWindow]::Title($_) -eq $Text -or $Action -eq 'button') } | Select-Object -First 1
if(-not $handle){throw 'Expected visible fixture process window is missing.'}
if($Action -eq 'close'){[NativeWindow]::PostMessage($handle,0x0010,[IntPtr]::Zero,[IntPtr]::Zero)|Out-Null;exit 0}
if($Action -eq 'button') {
 $button=[IntPtr]::Zero
 foreach($h in $handles){$button=[NativeWindow]::Button($h,$Text);if($button -ne [IntPtr]::Zero){break}}
 if($button -eq [IntPtr]::Zero){throw "Native button missing: $Text"}
 [NativeWindow]::PostMessage($button,0x00F5,[IntPtr]::Zero,[IntPtr]::Zero)|Out-Null;exit 0
}
[NativeWindow]::ShowWindowAsync($handle,9)|Out-Null
[NativeWindow]::SetForegroundWindow($handle)|Out-Null
Start-Sleep -Milliseconds 400
if([NativeWindow]::GetForegroundWindow() -ne $handle){throw 'Foreground denied; refusing input to an unverified window.'}
if($Action -eq 'capture') {
 $r=New-Object NativeWindow+Rect;[NativeWindow]::GetWindowRect($handle,[ref]$r)|Out-Null
 $bitmap=New-Object Drawing.Bitmap ($r.right-$r.left),($r.bottom-$r.top);$g=[Drawing.Graphics]::FromImage($bitmap)
 try{$g.CopyFromScreen($r.left,$r.top,0,0,$bitmap.Size);$bitmap.Save($OutputPath,[Drawing.Imaging.ImageFormat]::Png)}finally{$g.Dispose();$bitmap.Dispose()};exit 0
}
if(-not [NativeWindow]::Class($handle).Contains('GHOST')){throw 'Input target is not the fixture Blender editor.'}
$r=New-Object NativeWindow+Rect;[NativeWindow]::GetClientRect($handle,[ref]$r)|Out-Null
if($X -le 0 -or $Y -le 0 -or $X -ge $r.right -or $Y -ge $r.bottom){throw 'Requested editor point is outside the client area.'}
$p=New-Object NativeWindow+Point;$p.x=$X;$p.y=$r.bottom-$Y
[NativeWindow]::ClientToScreen($handle,[ref]$p)|Out-Null;[NativeWindow]::SetCursorPos($p.x,$p.y)|Out-Null
Start-Sleep -Milliseconds 200
if($Action -eq 'move') {
 [Windows.Forms.SendKeys]::SendWait('g');Start-Sleep -Milliseconds 150
 [Windows.Forms.SendKeys]::SendWait('x');[Windows.Forms.SendKeys]::SendWait('1');[Windows.Forms.SendKeys]::SendWait('{ENTER}')
}else{
 [Windows.Forms.SendKeys]::SendWait('{F3}');Start-Sleep -Milliseconds 400
 [Windows.Forms.SendKeys]::SendWait('Save checkpoint and return to launcher');Start-Sleep -Milliseconds 400
 [Windows.Forms.SendKeys]::SendWait('{ENTER}')
}
