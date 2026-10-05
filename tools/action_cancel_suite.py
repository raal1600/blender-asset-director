"""Isolated installed-runtime Action cancellation through real Chrome and Blender."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from create_workbench_studio import create

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blender', required=True)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--native-fixture')
    parser.add_argument('--node', default='node')
    parser.add_argument('--chrome')
    parser.add_argument('--playwright-module', help='Existing absolute Playwright Node index.mjs; otherwise use the Python package driver')
    args = parser.parse_args()
    output = Path(args.evidence).resolve(); output.mkdir(parents=True, exist_ok=False)
    report = {'status':'FAIL', 'scope':'GENERATED_INSTALLED_ACTION_CANCELLATION',
              'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'worktree_dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT)),
              'native_desktop':'NOT_TESTED', 'codex':'NOT_INVOKED'}
    try:
        if args.playwright_module:
            module = Path(args.playwright_module); assert module.is_absolute() and module.is_file()
        else:
            import playwright
            module = Path(playwright.__file__).parent/'driver/package/index.mjs'
        native = Path(args.native_fixture).resolve() if args.native_fixture else output/'native'
        if not args.native_fixture:
            with (output/'native.log').open('wb') as log:
                subprocess.run([args.blender,'--background','--factory-startup','--disable-autoexec','--threads','2',
                                '--python-exit-code','11','--python',str(ROOT/'tools/motion_stitch_fixture.py'),'--',str(native)],
                               cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=300,check=True)
        studio = output/'Studio'
        # The installer requires an existing executable for this unused field.
        # Python is an explicit sentinel; no Codex/model operation is tested.
        create(str(studio),args.blender,sys.executable,sys.executable,source_commit=report['commit'])
        with (output/'browser.log').open('wb') as log:
            subprocess.run([args.node,str(ROOT/'tools/action_cancel_browser_check.mjs'),str(output/'browser'),
                            str(native),sys.executable,args.blender,str(module),args.chrome or '',str(studio)],
                           cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=600,check=True)
        result=json.loads((output/'browser/RESULTS.json').read_text(encoding='utf-8'))
        assert result['status']=='PASS'
        report.update(status='PASS',checks=result['checks'],cases=result['cases'],video='browser/'+result['video'])
    except BaseException as error:
        report['error']=str(error)
        raise
    finally:
        (output/'RESULTS.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({key:report[key] for key in ['status','scope','commit']}))


if __name__ == '__main__':
    main()
