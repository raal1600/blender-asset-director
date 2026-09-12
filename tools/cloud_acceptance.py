"""Independent live-provider gates; failures stay visible without hiding other results."""
from pathlib import Path
import json
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from asset_director.core import Library, DirectorError, atomic_json, load_json
from asset_director.providers import Providers
from asset_director import backend, jobs


def main(blender, library, out):
    output = Path(out).resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = {'status': 'RUNNING', 'checks': {}, 'blender': blender}

    def check(name, fn):
        try:
            value = fn()
            results['checks'][name] = {'status': 'PASS', 'evidence': value}
        except DirectorError as exc:
            results['checks'][name] = {'status': 'FAIL', 'code': exc.code, 'message': exc.message}
        except (AssertionError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
            # Provider exceptions may contain URLs or response data; store only type.
            results['checks'][name] = {'status': 'FAIL', 'code': type(exc).__name__, 'message': 'See the bounded stage/worker log; no raw exception data is persisted'}
        atomic_json(output / 'live_acceptance.json', results)
        print(json.dumps({'check': name, **results['checks'][name]}), flush=True)
        return results['checks'][name]['status'] == 'PASS'

    with Library(library) as lib:
        providers = Providers(lib)

        def pack_test():
            pack = providers.search('quaternius', 'animation')['results'][0]['asset']['id']
            acquired = providers.acquire(pack)
            j = jobs.prepare(lib, 'index', asset_id=pack, options={'max_clips': 256})
            jobs.run(lib, j['id'], blender, 900)
            indexed = jobs.index_result(lib, pack, j['id'])
            clips = [a for a in lib.all() if a.kind == 'animation']
            assert clips and any('walk' in a.title.lower() for a in clips), 'No actual walk clip was indexed'
            return {'asset_id': pack, 'acquisition': acquired['status'], 'index': indexed, 'actual_clip_names': [a.title for a in clips]}

        pack_ok = check('quaternius_acquire_and_index', pack_test)

        def environment_test(provider, query, kind):
            r = providers.search(provider, query, kind, 3, refresh=True)
            assert r['results'], 'No live candidates'
            aid = r['results'][0]['asset']['id']
            acquired = providers.acquire(aid)
            imp = jobs.prepare(lib, 'import', asset_id=aid)
            imported = jobs.run(lib, imp['id'], blender, 240)
            return {'asset_id': aid, 'acquisition': acquired['status'], 'import': imported['summary']}

        check('polyhaven_acquire_and_import', lambda: environment_test('polyhaven', 'desert', 'hdri'))
        check('ambientcg_acquire_and_import', lambda: environment_test('ambientcg', 'sand', 'material'))

        def motion_test():
            backend.install(lib)
            walks = [a for a in lib.all() if a.kind == 'animation' and 'walk' in a.title.lower()
                     and a.metadata.get('qa', {}).get('limb_relative_motion_height_ratio', 0) > .005]
            assert walks, 'No usable walking motion was measured'
            walk = sorted(walks, key=lambda a: (a.metadata['duration_seconds'], a.id))[0]
            selection = output / 'selected_clip.json'
            atomic_json(selection, {'library': str(lib.root), 'asset_id': walk.id})
            subprocess.run([blender, '--background', '--factory-startup', '--disable-autoexec', '--threads', '2',
                            '--python-exit-code', '11', '--python', str(ROOT / 'tools' / 'real_motion_test.py'),
                            '--', str(selection), str(output)], check=True, timeout=600)
            return load_json(output / 'real_motion_report.json')

        if pack_ok:
            check('real_motion', motion_test)
        else:
            results['checks']['real_motion'] = {'status': 'BLOCKED', 'reason': 'Actual animation acquisition/index did not pass'}
        lib.export_report()
    results['status'] = 'PASS' if all(c['status'] == 'PASS' for c in results['checks'].values()) else 'FAIL'
    atomic_json(output / 'live_acceptance.json', results)
    print(json.dumps(results), flush=True)
    return 0 if results['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main(*sys.argv[1:]))
