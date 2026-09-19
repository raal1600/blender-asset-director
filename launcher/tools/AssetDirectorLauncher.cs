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
using System.Management;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;
[assembly: AssemblyTitle("Asset Director")]
[assembly: AssemblyVersion("0.2.0.0")]
internal static class Launcher {
    [DllImport("user32.dll")] static extern bool AllowSetForegroundWindow(int processId);
    [STAThread] static int Main(string[] args) {
        if(args.Length>0&&args[0]=="--task-process")return TaskProcess.Run(args);
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
// No script-policy changes and no process-name termination. The authenticated
// server supplies a project-owned task manifest, not arbitrary user arguments.
internal static class TaskProcess {
    [DllImport("shell32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr CommandLineToArgvW(string line,out int count);
    [DllImport("kernel32.dll")] static extern IntPtr LocalFree(IntPtr value);
    [DllImport("user32.dll")] static extern bool ShowWindowAsync(IntPtr window,int command);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr window);
    static Dictionary<string,object> State(string state){return new Dictionary<string,object>{{"state",state}};}
    static string[] Split(string line) {
        int count;IntPtr p=CommandLineToArgvW(line,out count);if(p==IntPtr.Zero)throw new InvalidOperationException();
        try{var a=new string[count];for(int i=0;i<count;i++)a[i]=Marshal.PtrToStringUni(Marshal.ReadIntPtr(p,i*IntPtr.Size));return a;}finally{LocalFree(p);}
    }
    static bool SamePath(string a,string b){return String.Equals(Path.GetFullPath(a),Path.GetFullPath(b),StringComparison.OrdinalIgnoreCase);}
    static Dictionary<string,object> Inspect(string[] args) {
        int pid;
        if(args.Length!=6||!Int32.TryParse(args[1],out pid)||pid<=0||!(args[4]=="inspect"||args[4]=="close"))return State("unknown");
        var task=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(File.ReadAllText(args[3]));
        string id=Convert.ToString(task["id"]),project=Convert.ToString(task["projectDirectory"]);
        if(!Regex.IsMatch(id,@"^task_[a-f0-9-]{36}$")||Convert.ToInt32(task["processId"])!=pid||
           Convert.ToString(task["action"])!="workbench-edit"||!SamePath(args[3],Path.Combine(project,"Runs/"+id+".json")))return State("unknown");
        Process process;
        try{process=Process.GetProcessById(pid);}catch(ArgumentException){return State("stopped");}
        using(process) {
            // Keep the process handle open through the close request. PID reuse
            // cannot substitute a different instance between inspection and action.
            IntPtr held=process.Handle;if(process.HasExited)return State("stopped");
            string identity=process.StartTime.ToUniversalTime().Ticks.ToString();
            if(!SamePath(process.MainModule.FileName,args[2]))return State("unknown");
            string line=null;
            using(var query=new ManagementObjectSearcher("SELECT CommandLine FROM Win32_Process WHERE ProcessId="+pid))
            using(var found=query.Get())foreach(ManagementObject item in found){using(item){line=Convert.ToString(item["CommandLine"]);}}
            if(String.IsNullOrEmpty(line))return State("unknown");
            var words=Split(line);int separator=Array.IndexOf(words,"--");
            if(separator<0||words.Length!=separator+2||!SamePath(words[separator+1],args[3]))return State("unknown");
            if(process.HasExited)return State("stopped");
            process.Refresh();bool window=process.MainWindowHandle!=IntPtr.Zero;
            var result=State("verified");result["identity"]=identity;result["hasWindow"]=window;
            if(args[4]=="close") {
                if(args[5]!=identity||!window)return State("unknown");
                ShowWindowAsync(process.MainWindowHandle,9);SetForegroundWindow(process.MainWindowHandle);
                result["requested"]=process.CloseMainWindow();
            }
            return result;
        }
    }
    public static int Run(string[] args) {
        Dictionary<string,object> result;
        try{result=Inspect(args);}catch{result=State("unknown");}
        using(var stream=new StreamWriter(Console.OpenStandardOutput())){stream.Write(new JavaScriptSerializer().Serialize(result));}
        return 0;
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
        FormClosing+=async(s,e)=>{if(allowClose)return;e.Cancel=true;if(starting){
            if(MessageBox.Show(this,"Director is still starting. Exit its window and leave the local backend running? No Blender or Codex process will be stopped.","Exit Director only",MessageBoxButtons.YesNo,MessageBoxIcon.Question,MessageBoxDefaultButton.Button2)==DialogResult.Yes){allowClose=true;Close();}
            return;}await TryExit(true);};
        FormClosed+=(s,e)=>{timer.Stop();tray.Dispose();view.Dispose();};
    }
    void RestoreWindow(){Show();WindowState=FormWindowState.Normal;Activate();BringToFront();tray.Visible=false;}
    async Task<Dictionary<string,object>> Request(string endpoint,bool post=false,object body=null) {
        var request=(HttpWebRequest)WebRequest.Create(origin+endpoint);request.Proxy=null;request.Timeout=15000;request.ReadWriteTimeout=15000;request.KeepAlive=false;
        request.Headers["Authorization"]="Bearer "+token;
        if(post){byte[] bytes=Encoding.UTF8.GetBytes(body==null?"{}":json.Serialize(body));request.Method="POST";request.ContentType="application/json";request.ContentLength=bytes.Length;using(var stream=await request.GetRequestStreamAsync()){await stream.WriteAsync(bytes,0,bytes.Length);}}
        using(var timeout=new System.Threading.Timer(s=>request.Abort(),null,15000,System.Threading.Timeout.Infinite)) using(var response=await request.GetResponseAsync())using(var reader=new StreamReader(response.GetResponseStream()))return json.Deserialize<Dictionary<string,object>>(await reader.ReadToEndAsync());
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
                var start=new ProcessStartInfo("node.exe","\""+Path.Combine(launcherRoot,"server.mjs")+"\" \""+studioRoot+"\" --desktop-logs");
                start.WorkingDirectory=launcherRoot;start.UseShellExecute=false;start.CreateNoWindow=true;
                ownedServer=new Process();ownedServer.StartInfo=start;
                ownedServer.Start();
                bool connected=false;for(int i=0;i<120;i++){if(await LoadSession()){connected=true;break;}if(ownedServer.HasExited)break;await Task.Delay(500);}
                if(!connected)throw new Exception("The local server could not start. See SystemRuntime/UserData/Launcher/server-error.log.");
            }
            if(allowClose)return;
            var environment=await CoreWebView2Environment.CreateAsync(null,Path.Combine(settings,"WebView2"));
            await view.EnsureCoreWebView2Async(environment);
            if(allowClose)return;
            view.CoreWebView2.Settings.AreDevToolsEnabled=false;view.CoreWebView2.Settings.AreDefaultContextMenusEnabled=false;
            view.CoreWebView2.WebResourceResponseReceived+=(s,e)=>{
                if(e.Request.Uri==origin+"/api/stop"&&e.Request.Method=="POST"&&e.Response.StatusCode==200){allowClose=true;Close();}
            };
            view.CoreWebView2.PermissionRequested+=(s,e)=>e.State=CoreWebView2PermissionState.Deny;
            view.CoreWebView2.NewWindowRequested+=(s,e)=>{e.Handled=true;OpenExternal(e.Uri);};
            view.CoreWebView2.NavigationStarting+=(s,e)=>{if(!e.Uri.StartsWith(origin+"/",StringComparison.Ordinal)){e.Cancel=true;OpenExternal(e.Uri);}};
            view.CoreWebView2.NavigationCompleted+=(s,e)=>{if(e.IsSuccess){status.Visible=false;Log("desktop.log","Desktop interface loaded successfully.");}else{status.Text="Unable to display Asset Director. Close the window and reopen it.";}};
            view.Source=new Uri(origin+"/workbench#"+token);
        } catch(Exception e) {if(!allowClose){status.Text="Asset Director could not open.\n\n"+e.Message;MessageBox.Show(this,status.Text,"Asset Director",MessageBoxButtons.OK,MessageBoxIcon.Error);}}
        finally {starting=false;}
    }
    readonly object logLock=new object();
    void Log(string name,string line){if(line==null)return;try{lock(logLock)File.AppendAllText(Path.Combine(settings,name),line+Environment.NewLine);}catch{}}
    void OpenExternal(string url){Uri parsed;if(Uri.TryCreate(url,UriKind.Absolute,out parsed)&&(parsed.Scheme=="https"||parsed.Scheme=="http")&&!parsed.IsLoopback)Process.Start(new ProcessStartInfo(url){UseShellExecute=true});}
    async Task ManageTask(Dictionary<string,object> selected) {
        var state=await Request("/api/lifecycle/task?projectId="+Uri.EscapeDataString(Convert.ToString(selected["projectId"]))+"&runId="+Uri.EscapeDataString(Convert.ToString(selected["runId"])));
        using(var choices=new TaskExitChoices(state)) {
            choices.ShowDialog(this);if(choices.Choice==0)return;
            var body=new Dictionary<string,object>{{"projectId",state["projectId"]},{"runId",state["runId"]},{"revision",state["revision"]},{"confirmed",true}};
            Dictionary<string,object> result;
            if(choices.Choice==3) {
                body["sceneId"]=state["sceneId"];await Request("/api/workbench/task-collect",true,body);
                MessageBox.Show(this,"Checkpoint collected for review. It has not been approved.","Checkpoint retained",MessageBoxButtons.OK,MessageBoxIcon.Information);return;
            }
            if(choices.Choice==1)body["processIdentity"]=((Dictionary<string,object>)state["process"])["identity"];
            result=await Request(choices.Choice==1?"/api/lifecycle/task-close":"/api/lifecycle/task-recover",true,body);
            MessageBox.Show(this,Convert.ToString(result["message"]),"Task status",MessageBoxButtons.OK,MessageBoxIcon.Information);
        }
    }
    async Task TryExit(bool prompt) {
        if(checking)return;checking=true;bool retryExit=false;
        try {
            if(origin==null){allowClose=true;Close();return;}
            while(true) {
            Dictionary<string,object> state;
            try {state=await Request("/api/lifecycle");}
            catch(WebException e) {
                if(e.Status==WebExceptionStatus.ConnectFailure){allowClose=true;Close();return;}
                throw new Exception("Cannot verify backend status. You can exit only Director without stopping any work. "+e.Message);
            }
            if(Convert.ToBoolean(state["busy"])) {
                if(prompt||Convert.ToBoolean(state["needsAttention"])) {
                    waiting=false;
                    using(var choices=new CloseChoices(state)) {
                        choices.ShowDialog(this);
                        if(choices.Choice==1){waiting=false;tray.Visible=true;Hide();}
                        if(choices.Choice==2){waiting=true;Text="Asset Director — waiting for work to finish";}
                        if(choices.Choice==3&&choices.Selected!=null){await ManageTask(choices.Selected);prompt=true;continue;}
                        if(choices.Choice==4){prompt=true;continue;}
                        if(choices.Choice==5){Log("desktop.log","Desktop exited; local backend and tasks retained.");allowClose=true;Close();}
                    }
                }
                return;
            }
            try {await Request("/api/stop",true);}
            catch(WebException e){if(e.Response!=null&&((HttpWebResponse)e.Response).StatusCode==HttpStatusCode.Conflict){waiting=true;Text="Asset Director — waiting for work to finish";return;}throw;}
            // Allow the idle server to release its socket. A transient disconnect
            // after an accepted stop must not trap the desktop in a warning loop.
            for(int i=0;i<50;i++) {
                await Task.Delay(100);
                try {await Request("/api/session");}
                catch(WebException e){if(e.Status==WebExceptionStatus.ConnectFailure){allowClose=true;Close();return;}}
            }
            Log("desktop.log","Backend accepted idle shutdown; desktop closed while it finishes.");allowClose=true;Close();return;
            }
        } catch(Exception e){
            waiting=false;Text="Asset Director";RestoreWindow();
            var unavailable=new Dictionary<string,object>{{"reasons",new object[]{e.Message}},{"tasks",new object[0]},{"needsAttention",true}};
            using(var choices=new CloseChoices(unavailable)){choices.ShowDialog(this);if(choices.Choice==5){allowClose=true;Close();}else if(choices.Choice==1){tray.Visible=true;Hide();}else if(choices.Choice==4)retryExit=true;}
        }
        finally{checking=false;if(retryExit&&!allowClose)BeginInvoke(new Action(async()=>await TryExit(true)));}
    }
}
internal sealed class CloseChoices : Form {
    public int Choice;
    readonly ListBox tasks=new ListBox();
    readonly List<Dictionary<string,object>> records=new List<Dictionary<string,object>>();
    public Dictionary<string,object> Selected {get{return tasks.SelectedIndex>=0?records[tasks.SelectedIndex]:null;}}
    public CloseChoices(Dictionary<string,object> state){
        Text="Before you exit";Width=780;Height=570;MinimumSize=new Size(780,570);StartPosition=FormStartPosition.CenterParent;ShowInTaskbar=false;Font=new Font("Segoe UI",10);MinimizeBox=false;MaximizeBox=false;Padding=new Padding(12);
        var text=new TextBox{Multiline=true,ReadOnly=true,ScrollBars=ScrollBars.Vertical,Dock=DockStyle.Fill,BorderStyle=BorderStyle.None,BackColor=SystemColors.Control};
        var reasons=(System.Collections.IEnumerable)state["reasons"];var lines=new List<string>();foreach(var reason in reasons)lines.Add("• "+Convert.ToString(reason));text.Text=String.Join("\r\n\r\n",lines);Controls.Add(text);
        var header=new Label{Text="Before you exit\nReview unfinished work, or exit only Director and leave the backend running. Blender and Codex are never force-terminated.",Dock=DockStyle.Top,Height=95,Padding=new Padding(14)};Controls.Add(header);
        tasks.Dock=DockStyle.Bottom;tasks.Height=100;tasks.IntegralHeight=false;
        object values;if(state.TryGetValue("tasks",out values))foreach(var item in (System.Collections.IEnumerable)values){var record=item as Dictionary<string,object>;if(record!=null){records.Add(record);tasks.Items.Add(Convert.ToString(record["label"]));}}
        if(tasks.Items.Count>0)tasks.SelectedIndex=0;Controls.Add(tasks);
        var buttons=new FlowLayoutPanel{Dock=DockStyle.Bottom,Height=112,Padding=new Padding(10),WrapContents=true};Controls.Add(buttons);
        Add(buttons,"Inspect selected task",3,190).Enabled=records.Count>0;
        Add(buttons,"Refresh status",4,135);
        Add(buttons,"Exit Director only",5,170);
        Add(buttons,"Keep running in tray",1,190);
        Add(buttons,"Exit when finished",2,170).Enabled=!Convert.ToBoolean(state["needsAttention"]);
        CancelButton=Add(buttons,"Cancel",0,100);
    }
    Button Add(Control parent,string text,int choice,int width){var button=new Button{Text=text,Width=width,Height=36};button.Click+=(s,e)=>{Choice=choice;Close();};parent.Controls.Add(button);return button;}
}
internal sealed class TaskExitChoices : Form {
    public int Choice;
    public TaskExitChoices(Dictionary<string,object> state) {
        Text="Task needs attention";Width=750;Height=460;MinimumSize=new Size(750,460);StartPosition=FormStartPosition.CenterParent;ShowInTaskbar=false;Font=new Font("Segoe UI",10);MinimizeBox=false;MaximizeBox=false;Padding=new Padding(12);
        var text=new TextBox{Text=Convert.ToString(state["detail"]).Replace("\n","\r\n"),Multiline=true,ReadOnly=true,ScrollBars=ScrollBars.Vertical,Dock=DockStyle.Fill,BorderStyle=BorderStyle.None,BackColor=SystemColors.Control};Controls.Add(text);
        var buttons=new FlowLayoutPanel{Dock=DockStyle.Bottom,Height=106,Padding=new Padding(12),WrapContents=true};Controls.Add(buttons);
        Add(buttons,"Close Blender task",1,185).Enabled=Convert.ToBoolean(state["canClose"]);
        Add(buttons,"Recover stopped task",2,195).Enabled=Convert.ToBoolean(state["canRecover"]);
        Add(buttons,"Collect checkpoint",3,185).Enabled=Convert.ToBoolean(state["canCollect"]);
        CancelButton=Add(buttons,"Back",0,100);
    }
    Button Add(Control parent,string text,int choice,int width){var b=new Button{Text=text,Width=width,Height=36};b.Click+=(s,e)=>{Choice=choice;Close();};parent.Controls.Add(b);return b;}
}
