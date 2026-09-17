using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;
[assembly: AssemblyTitle("Asset Director")]
[assembly: AssemblyVersion("0.2.0.0")]
internal static class Launcher {
    [DllImport("user32.dll")] static extern bool AllowSetForegroundWindow(int processId);
    [STAThread] static int Main(string[] args) {
        Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
        string root=AppDomain.CurrentDomain.BaseDirectory;
        string key; using(var hash=SHA256.Create()) key=BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(root.ToLowerInvariant()))).Replace("-", "");
        bool first;
        using(var mutex=new Mutex(true,"Local\\AssetDirector-"+key,out first))
        using(var activate=new EventWaitHandle(false,EventResetMode.AutoReset,"Local\\AssetDirectorActivate-"+key)) {
            if(!first) {
                foreach(var process in Process.GetProcessesByName("Asset Director")) {
                    try {if(String.Equals(process.MainModule.FileName,Path.Combine(root,"Asset Director.exe"),StringComparison.OrdinalIgnoreCase))AllowSetForegroundWindow(process.Id);}catch{}
                    process.Dispose();
                }
                activate.Set();return 0;
            }
            try { Application.Run(new Desktop(root,activate)); return 0; }
            catch(Exception e) {MessageBox.Show(e.Message,"Asset Director",MessageBoxButtons.OK,MessageBoxIcon.Error);return 1;}
        }
    }
}
internal sealed class Desktop : Form {
    readonly string launcherRoot,studioRoot,settings;
    readonly EventWaitHandle activate;
    readonly WebView2 view=new WebView2();
    readonly Label status=new Label();
    readonly NotifyIcon tray=new NotifyIcon();
    readonly System.Windows.Forms.Timer timer=new System.Windows.Forms.Timer();
    readonly JavaScriptSerializer json=new JavaScriptSerializer();
    string origin,token;
    bool allowClose,checking,waiting,starting=true;
    Process ownedServer;
    public Desktop(string root,EventWaitHandle signal) {
        launcherRoot=root;studioRoot=Path.GetFullPath(Path.Combine(root,"../.."));settings=Path.Combine(studioRoot,"SystemRuntime/UserData/Launcher");activate=signal;
        Text="Asset Director";Width=1280;Height=850;MinimumSize=new Size(860,600);StartPosition=FormStartPosition.CenterScreen;Icon=SystemIcons.Application;
        status.Dock=DockStyle.Fill;status.Text="Starting Asset Director...";status.TextAlign=ContentAlignment.MiddleCenter;status.Font=new Font("Segoe UI",12);
        view.Dock=DockStyle.Fill;Controls.Add(view);Controls.Add(status);
        tray.Icon=Icon;tray.Text="Asset Director";tray.DoubleClick+=(s,e)=>RestoreWindow();
        var menu=new ContextMenuStrip();menu.Items.Add("Open Asset Director",null,(s,e)=>RestoreWindow());menu.Items.Add("Exit",null,(s,e)=>{RestoreWindow();Close();});tray.ContextMenuStrip=menu;
        timer.Interval=1000;timer.Tick+=async(s,e)=>{if(activate.WaitOne(0))RestoreWindow();if(waiting&&!checking)await TryExit(false);};timer.Start();
        Shown+=async(s,e)=>await Start();
        FormClosing+=async(s,e)=>{if(allowClose)return;e.Cancel=true;if(starting)return;await TryExit(true);};
        FormClosed+=(s,e)=>{timer.Stop();tray.Dispose();view.Dispose();};
    }
    void RestoreWindow(){Show();WindowState=FormWindowState.Normal;Activate();BringToFront();tray.Visible=false;}
    async Task<Dictionary<string,object>> Request(string endpoint,bool post=false) {
        var request=(HttpWebRequest)WebRequest.Create(origin+endpoint);request.Proxy=null;request.Timeout=5000;request.ReadWriteTimeout=5000;
        request.Headers["Authorization"]="Bearer "+token;
        if(post){request.Method="POST";request.ContentType="application/json";request.ContentLength=2;using(var stream=await request.GetRequestStreamAsync()){byte[] bytes=Encoding.UTF8.GetBytes("{}");await stream.WriteAsync(bytes,0,bytes.Length);}}
        using(var timeout=new System.Threading.Timer(s=>request.Abort(),null,5000,System.Threading.Timeout.Infinite)) using(var response=await request.GetResponseAsync())using(var reader=new StreamReader(response.GetResponseStream()))return json.Deserialize<Dictionary<string,object>>(await reader.ReadToEndAsync());
    }
    async Task<bool> LoadSession() {
        try {
            var data=json.Deserialize<Dictionary<string,object>>(File.ReadAllText(Path.Combine(settings,"session.json")));
            string candidate=Convert.ToString(data["origin"]),secret=Convert.ToString(data["token"]);
            if(!Regex.IsMatch(candidate,@"^http://127\.0\.0\.1:\d+$")||!Regex.IsMatch(secret,"^[a-f0-9]{64}$")||!String.Equals(Convert.ToString(data["root"]),studioRoot,StringComparison.OrdinalIgnoreCase))return false;
            origin=candidate;token=secret;var result=await Request("/api/session");return Convert.ToString(result["app"])=="asset-director-launcher"&&String.Equals(Convert.ToString(result["root"]),studioRoot,StringComparison.OrdinalIgnoreCase);
        }catch{return false;}
    }
    async Task Start() {
        try {
            Directory.CreateDirectory(settings);
            if(!await LoadSession()) {
                var start=new ProcessStartInfo("node.exe","\""+Path.Combine(launcherRoot,"server.mjs")+"\" \""+studioRoot+"\"");
                start.WorkingDirectory=launcherRoot;start.UseShellExecute=false;start.CreateNoWindow=true;start.RedirectStandardOutput=true;start.RedirectStandardError=true;
                ownedServer=new Process();ownedServer.StartInfo=start;
                ownedServer.OutputDataReceived+=(s,e)=>Log("server.log",e.Data);ownedServer.ErrorDataReceived+=(s,e)=>Log("server-error.log",e.Data);
                ownedServer.Start();ownedServer.BeginOutputReadLine();ownedServer.BeginErrorReadLine();
                bool connected=false;for(int i=0;i<120;i++){if(await LoadSession()){connected=true;break;}if(ownedServer.HasExited)break;await Task.Delay(500);}
                if(!connected)throw new Exception("The local server could not start. See SystemRuntime/UserData/Launcher/server-error.log.");
            }
            await Request("/api/lifecycle");
            var environment=await CoreWebView2Environment.CreateAsync(null,Path.Combine(settings,"WebView2"));
            await view.EnsureCoreWebView2Async(environment);
            view.CoreWebView2.Settings.AreDevToolsEnabled=false;view.CoreWebView2.Settings.AreDefaultContextMenusEnabled=false;
            view.CoreWebView2.WebResourceResponseReceived+=async(s,e)=>{
                if(e.Request.Uri==origin+"/api/stop"&&e.Request.Method=="POST"&&e.Response.StatusCode==200){await Task.Delay(400);Close();}
            };
            view.CoreWebView2.PermissionRequested+=(s,e)=>e.State=CoreWebView2PermissionState.Deny;
            view.CoreWebView2.NewWindowRequested+=(s,e)=>{e.Handled=true;OpenExternal(e.Uri);};
            view.CoreWebView2.NavigationStarting+=(s,e)=>{if(!e.Uri.StartsWith(origin+"/",StringComparison.Ordinal)){e.Cancel=true;OpenExternal(e.Uri);}};
            view.CoreWebView2.NavigationCompleted+=(s,e)=>{if(e.IsSuccess){status.Visible=false;Log("desktop.log","Desktop interface loaded successfully.");}else{status.Text="Unable to display Asset Director. Close the window and reopen it.";}};
            view.Source=new Uri(origin+"/#"+token);
        } catch(Exception e) {status.Text="Asset Director could not open.\n\n"+e.Message;MessageBox.Show(this,status.Text,"Asset Director",MessageBoxButtons.OK,MessageBoxIcon.Error);}
        finally {starting=false;}
    }
    readonly object logLock=new object();
    void Log(string name,string line){if(line==null)return;try{lock(logLock)File.AppendAllText(Path.Combine(settings,name),line+Environment.NewLine);}catch{}}
    void OpenExternal(string url){Uri parsed;if(Uri.TryCreate(url,UriKind.Absolute,out parsed)&&(parsed.Scheme=="https"||parsed.Scheme=="http")&&!parsed.IsLoopback)Process.Start(new ProcessStartInfo(url){UseShellExecute=true});}
    async Task TryExit(bool prompt) {
        if(checking)return;checking=true;
        try {
            if(origin==null){allowClose=true;Close();return;}
            Dictionary<string,object> state;
            try {state=await Request("/api/lifecycle");}
            catch(WebException e) {
                if(e.Status==WebExceptionStatus.ConnectFailure){allowClose=true;Close();return;}
                throw new Exception("Cannot verify server status. The window will stay open. "+e.Message);
            }
            if(Convert.ToBoolean(state["busy"])) {
                if(prompt) {
                    using(var choices=new CloseChoices()) {
                        choices.ShowDialog(this);
                        if(choices.Choice==1){waiting=false;tray.Visible=true;Hide();}
                        if(choices.Choice==2){waiting=true;Text="Asset Director — waiting for work to finish";}
                    }
                }
                return;
            }
            try {await Request("/api/stop",true);}
            catch(WebException e){if(e.Response!=null&&((HttpWebResponse)e.Response).StatusCode==HttpStatusCode.Conflict){waiting=true;Text="Asset Director — waiting for work to finish";return;}throw;}
            // Wait for the listening socket to close before releasing the single-instance lock.
            for(int i=0;i<50;i++) {
                await Task.Delay(100);
                try {await Request("/api/session");}
                catch(WebException e){if(e.Status==WebExceptionStatus.ConnectFailure){allowClose=true;Close();return;}throw;}
            }
            throw new Exception("The server is still shutting down. Try closing again shortly.");
        } catch(Exception e){waiting=false;Text="Asset Director";if(prompt)MessageBox.Show(this,e.Message,"Cannot close Asset Director",MessageBoxButtons.OK,MessageBoxIcon.Warning);else{RestoreWindow();MessageBox.Show(this,e.Message,"Shutdown paused",MessageBoxButtons.OK,MessageBoxIcon.Warning);}}
        finally{checking=false;}
    }
}
internal sealed class CloseChoices : Form {
    public int Choice;
    public CloseChoices(){
        Text="Work is still running";Width=560;Height=205;FormBorderStyle=FormBorderStyle.FixedDialog;MaximizeBox=false;MinimizeBox=false;StartPosition=FormStartPosition.CenterParent;
        var label=new Label{Text="Asset Director has active or unfinished work.\nChoose what happens when you close the window.",Dock=DockStyle.Top,Height=85,Padding=new Padding(18),AutoSize=false};Controls.Add(label);
        var buttons=new FlowLayoutPanel{Dock=DockStyle.Bottom,Height=65,Padding=new Padding(12)};Controls.Add(buttons);
        Add(buttons,"Keep running in tray",1,180);Add(buttons,"Exit when finished",2,150);Add(buttons,"Cancel",0,90);
    }
    void Add(Control parent,string text,int choice,int width){var button=new Button{Text=text,Width=width,Height=32};button.Click+=(s,e)=>{Choice=choice;Close();};parent.Controls.Add(button);}
}
