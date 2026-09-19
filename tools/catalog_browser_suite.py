"""Run the large-library browser check in a new disposable fixture only."""
import argparse
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',required=True);parser.add_argument('--chrome');args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='synthetic-catalog-browser-') as temporary:
        root=Path(temporary)/'studio';session_file=root/'browser-session.json'
        # This exact child only serves generated metadata. It refuses native jobs.
        process=subprocess.Popen(['node',str(ROOT/'tools/catalog_browser_fixture.mjs'),str(root),'10000'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        session=None
        try:
            deadline=time.monotonic()+30
            while not session_file.exists():
                if process.poll() is not None:raise RuntimeError('Synthetic browser fixture exited during setup')
                if time.monotonic()>deadline:raise TimeoutError('Synthetic browser fixture did not start')
                time.sleep(.1)
            session=json.loads(session_file.read_text())
            assert session['fixture']=='synthetic-catalog-browser'
            command=[sys.executable,'-B',str(ROOT/'tools/catalog_browser_check.py'),'--fixture',str(root),'--evidence',str(Path(args.evidence).resolve())]
            if args.chrome:command+=['--chrome',args.chrome]
            return subprocess.run(command,timeout=180).returncode
        finally:
            if session and process.poll() is None:
                request=urllib.request.Request(session['origin']+'/api/stop',data=b'{}',headers={'Authorization':'Bearer '+session['token'],'Content-Type':'application/json'})
                try:
                    with urllib.request.urlopen(request,timeout=5) as response:assert response.status==200
                except Exception:pass
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate();process.wait(timeout=10)
if __name__=='__main__':raise SystemExit(main())
