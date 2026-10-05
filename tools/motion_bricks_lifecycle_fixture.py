"""Real abrupt-parent-death regression for the isolated native provider."""
from pathlib import Path
import argparse
import ctypes
import os
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from asset_director.core import atomic_json, load_json, require
from asset_director.motion_bricks_provider import execute, _memory_mib


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config",type=Path,required=True);p.add_argument("--request",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True);p.add_argument("--child",action="store_true")
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);marker=a.output/"native-worker.json"
    if a.child:
        def progress(event):
            if event["stage"]=="running":atomic_json(marker,event)
        execute(load_json(a.config),load_json(a.request),progress=progress)
        atomic_json(a.output/"unexpected-completion.json",{"completed":True});return
    require(not marker.exists(),"FIXTURE_OUTPUT_EXISTS","Use a fresh lifecycle evidence directory")
    command=[sys.executable,str(Path(__file__).resolve()),"--config",str(a.config),"--request",str(a.request),
             "--output",str(a.output),"--child"]
    with (a.output/"owner.log").open("wb") as log:
        owner=subprocess.Popen(command,stdout=log,stderr=log,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        native_handle=None
        try:
            deadline=time.monotonic()+30
            while not marker.is_file() and owner.poll() is None and time.monotonic()<deadline:time.sleep(.01)
            require(marker.is_file(),"FIXTURE_WORKER_START","Native worker did not start")
            pid=load_json(marker)["worker_pid"]
            if os.name=="nt":
                from ctypes import wintypes as w
                kernel=ctypes.WinDLL("kernel32",use_last_error=True)
                kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
                kernel.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];kernel.WaitForSingleObject.restype=w.DWORD
                kernel.CloseHandle.argtypes=[w.HANDLE];kernel.TerminateProcess.argtypes=[w.HANDLE,w.UINT]
                native_handle=kernel.OpenProcess(0x100000|0x1,False,pid)
                require(bool(native_handle),"FIXTURE_WORKER_START","Native worker already exited")
                def alive():return kernel.WaitForSingleObject(native_handle,0)==258
            else:
                def alive():
                    try:os.kill(pid,0);return True
                    except ProcessLookupError:return False
            # Ensure the real helper is alive and loading, not merely queued.
            deadline=time.monotonic()+5
            while alive() and (_memory_mib(pid) or 0)<100 and time.monotonic()<deadline:time.sleep(.005)
            require(alive(),"FIXTURE_WORKER_TIMING","Native work finished before parent-death exercise")
            started=time.monotonic();owner.kill();owner.wait(timeout=10)
            while alive() and time.monotonic()-started<3:time.sleep(.01)
            exited=not alive()
            if not exited and native_handle:kernel.TerminateProcess(native_handle,126)
            require(exited,"FIXTURE_ORPHAN","Native child survived owner termination")
            result={"status":"PASS","owner_pid":owner.pid,"native_pid":pid,
                    "native_exit_after_owner_seconds":time.monotonic()-started,
                    "partial_result_accepted":False,"method":"real parent process terminated during native worker model load"}
            atomic_json(a.output/"summary.json",result);print(result)
        finally:
            if owner.poll() is None:owner.kill();owner.wait(timeout=10)
            if native_handle:kernel.CloseHandle(native_handle)


if __name__=="__main__":main()
