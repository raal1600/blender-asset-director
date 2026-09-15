"""Apply reviewed consolidation edits to the exact merged historical sources.

Temporary assembly input. Removed from the resulting source tree. No tests,
credentials, assets, settings, branches or main are modified by this script.
"""
from pathlib import Path


def replace(path, old, new):
    p = Path(path)
    data = p.read_text()
    if data.count(old) != 1:
        raise RuntimeError('Unexpected source for exact replacement: ' + path)
    p.write_text(data.replace(old, new))


def section(path, start, end, content):
    p = Path(path)
    data = p.read_text()
    a = data.index(start)
    b = data.index(end, a)
    p.write_text(data[:a] + content + data[b:])


replace('src/asset_director/transfer_blender.py',
    "    ops.assign(obj, action, asset.metadata.get('slot'))",
    "    from .action_identity import imported_slot\n    slot_id = imported_slot(obj, action, asset.metadata.get('slot'), asset.metadata['source_object'])\n    ops.assign(obj, action, slot_id)")
replace('src/asset_director/transfer_blender.py',
    "    alignment_precision = precision(o['target_meters_per_unit'], max(target.matrix_world.to_scale()))\n",
    "    alignment_precision = precision(o['target_meters_per_unit'], max(target.matrix_world.to_scale()))\n" + '''    # Identical observed references need zero deformation, not float32 round trips.
    same_reference = (sr['fingerprint'] == tr['fingerprint']
        and all(s == t for s,t in pairs.items()) and abs(yaw) < 1e-8
        and max(abs(source.matrix_world[r][c]-target.matrix_world[r][c])
                for r in range(3) for c in range(3)) < 1e-8)
    if same_reference:
        alignment={n:flat(Matrix.Identity(4)) for n in pairs.values()}
        alignment_evidence=[{'role':role,'source':s_roles[role],'target':t_roles[role],
            'swing_degrees':0.0,'source_basis':'matching observed reference fingerprint and world linear transform',
            'target_basis':'unchanged target rest; exact identity basis'} for role in common]
''')
replace('src/asset_director/transfer_blender.py', '        if b.name in role_for:', '        if b.name in role_for and not same_reference:')
replace('src/asset_director/transfer_blender.py',
    "        'alignment_method':'minimal anatomical swing; nearest target-rest twist; host must review terminal axes',",
    "        'alignment_method':('exact identity for identical observed references' if same_reference else\n            'minimal anatomical swing; nearest target-rest twist; host must review terminal axes'),")
replace('src/asset_director/worker.py',
    '''                reviewed_roles = verify_execution(lib, source, target, matches[0], options.get("slot"), options)
                data = ops.retarget(source, target, matches[0], options.get("slot"), options, backend.verify(lib), job["id"], reviewed_roles=reviewed_roles)''',
    '''                from asset_director.action_identity import imported_slot
                slot_id = imported_slot(source, matches[0], options.get("slot"), options.get("source_object"))
                reviewed_roles = verify_execution(lib, source, target, matches[0], slot_id, options)
                data = ops.retarget(source, target, matches[0], slot_id, options, backend.verify(lib), job["id"], reviewed_roles=reviewed_roles)''')

for path in ('.github/workflows/ci.yml', '.github/workflows/source-package.yml'):
    replace(path, "branches: [main, 'fix/**', 'feature/**']", "branches: [main, 'fix/**', 'feature/**', 'chore/**', 'docs/**']")
replace('.github/workflows/ci.yml', 'permissions:\n  contents: read\n', 'permissions:\n  contents: read\n  actions: read\n  pull-requests: read\n')
replace('.github/workflows/ci.yml',
    '      - name: Skill installation round trip\n        run: python tools/install_skill.py --self-test\n',
    '''      - name: Current documentation and unit gate summary
        if: always()
        shell: bash
        run: |
          echo '## Portable tests and contributor documentation' >> "$GITHUB_STEP_SUMMARY"
          echo 'Commit: `${{ github.sha }}` · OS: `${{ matrix.os }}` · Python: `${{ matrix.python }}`' >> "$GITHUB_STEP_SUMMARY"
          echo 'Result so far: **${{ job.status }}**. Exact totals and skips are in the unit-test log.' >> "$GITHUB_STEP_SUMMARY"
      - name: Skill installation round trip
        run: python tools/install_skill.py --self-test
      - name: Dry-run manifest-bound branch cleanup
        if: matrix.os == 'ubuntu-latest' && matrix.python == '3.11' && github.repository == 'raal1600/blender-asset-director'
        env:
          GH_TOKEN: ${{ github.token }}
        run: python tools/cleanup_merged_branches.py --target-sha "${{ github.sha }}" --dry-run
      - uses: actions/upload-artifact@v4
        if: always() && matrix.os == 'ubuntu-latest' && matrix.python == '3.11'
        with:
          name: branch-cleanup-dry-run
          path: cleanup-evidence/
          retention-days: 30
          if-no-files-found: warn
''')
replace('.github/workflows/ci.yml',
    '      - name: Full long-take sequence, root alignment, bridge and reviewed-role QA\n',
    '''      - name: Imported action labels, owned slots and identical reference preservation
        run: |
          "$BLENDER" --background --factory-startup --disable-autoexec --threads 2 --python-exit-code 11 --python tools/action_collision_fixture.py -- "$RUNNER_TEMP/collision"
          cp "$RUNNER_TEMP/collision/action_collision_report.json" evidence/
          "$BLENDER" --background --factory-startup --disable-autoexec --threads 2 --python-exit-code 11 --python tools/reference_identity_fixture.py -- "$RUNNER_TEMP/reference" "$RUNNER_TEMP/bad-library"
          cp "$RUNNER_TEMP/reference/reference_identity_report.json" evidence/
      - name: Full long-take sequence, root alignment, bridge and reviewed-role QA
''')
for path in ('.github/workflows/consolidation-audit.yml', '.github/workflows/sequence-diagnostic.yml'):
    section(path, 'on:\n', 'permissions:', 'on:\n  workflow_dispatch:\n')
section('.github/workflows/transition-lab-pages.yml', 'on:\n', 'permissions:',
    "on:\n  push:\n    branches: [main, 'chore/consolidate-main-20260915']\n  pull_request:\n  workflow_dispatch:\n")
replace('.github/workflows/transition-lab-pages.yml', '  group: transition-lab-pages\n', '  group: transition-lab-pages-${{ github.ref }}\n')
replace('.github/workflows/transition-lab-pages.yml', '  deploy:\n', "  deploy:\n    if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'\n")

replace('tools/reference_identity_fixture.py', 'Run factory background Blender -- OUTPUT_DIRECTORY.', 'Run factory background Blender -- OUTPUT_DIRECTORY VERIFIED_BACKEND_LIBRARY.')
replace('tools/reference_identity_fixture.py', 'def main(directory):', 'def main(directory, backend_library):')
replace('tools/reference_identity_fixture.py', "    with Library(out/'library') as lib:\n", '''    with Library(out/'library') as lib:
        # Reuse the independently checksum-verified backend from this CI job.
        from asset_director import backend, transfer_review
        with Library(backend_library) as source_library:
            verified = backend.verify(source_library)
            shutil.copytree(verified, backend.location(lib), dirs_exist_ok=True)
        backend.verify(lib)
''')
replace('tools/reference_identity_fixture.py', "        _,proposal,_=run('transfer-plan'", "        planned,proposal,_=run('transfer-plan'")
replace('tools/reference_identity_fixture.py', "        report={'status':'PASS'", '''        approved=transfer_review.prepare(lib,dict(plan_job_id=planned['id'],
            plan_id=proposal['id'],reviewer='synthetic-fixture',
            reviewed_at='2026-09-15T00:00:00Z',approved=True))
        done=jobs.run(lib,approved['id'],bpy.app.binary_path,180)
        result_dir=lib.root/'jobs'/approved['id']
        data=load_json(result_dir/'result.json')['data']
        assert done['state']=='SUCCEEDED' and data['qa_roles']==proposal['target_roles']
        assert (result_dir/'result.blend').is_file()
        assert file_hash(target_file)==untouched and file_hash(fbx)==original
        assert approved['specification']['options']['slot']==lib.get(cid).metadata['slot']
        report={'reviewed_execution':'PASS','status':'PASS' ''')
replace('tools/reference_identity_fixture.py', "if __name__=='__main__':main(sys.argv[sys.argv.index('--')+1])", "if __name__=='__main__':main(*sys.argv[sys.argv.index('--')+1:])")

replace('AGENTS.md',
    'Direct main updates are authorized for initial development of this repository. Never force-push or overwrite unrelated future changes. Preserve the existing repository license.',
    'Use tested pull requests for development. Read CONTRIBUTING.md and docs/CONSOLIDATION.md before resuming; dated handoffs are historical. Merge only a validated, unchanged head. Never rewrite main or overwrite unrelated future changes. Delete only merged, unchanged branches after successful main gates. Preserve the existing repository license.')
section('README.md', '> **Development branch:', '**Give Codex', '''**Development source: `main` · runtime `0.6.0-dev.4`.** The published installer
still installs **v0.5.0**; merging source does not publish a release or update an
installed skill. Identify development builds by their full Git commit SHA.

[Contributor quick start](CONTRIBUTING.md) · [Current handoff and test gates](docs/CONSOLIDATION.md) ·
[Documentation index](docs/README.md) · [Synthetic Transition Lab](https://raal1600.github.io/blender-asset-director/)

Main brings together local animation intake, canonical motion and clay proxies,
reviewed transfer planning, custom semantic roles, bone-display controls,
subframe grounding, full-clip sequencing, physical-unit precision and imported
action identity fixes. The sequence bridge adds an explicitly reviewed interval;
it does not silently shorten either source clip. Technical tests and human
performance review remain separate.

''')
replace('README.md', 'This branch provides `transfer-plan`', 'Main provides `transfer-plan`')
replace('README.md', 'release or merge automatically.', 'release; merge only after the documented test gates.')
section('README.md', '## Tests, maintenance and removal', 'From the installed runtime', '''## Tests, maintenance and removal

Every pull request runs portable tests and installation checks, the real Blender
matrix (4.5.3, 5.0.0 and 5.2.1), and four bootstrap configurations. The normal
matrix now includes imported-action collisions and reviewed identity-reference
execution, rather than leaving these in an easy-to-miss branch-only workflow.
The Transition Lab separately tests rendering, encoding and desktop/mobile video
playback. Results and diagnostic artifacts are attached to each Actions run.

Read [current gates and consolidation evidence](docs/CONSOLIDATION.md) for the
exact acceptance process. Older acceptance documents describe their named
commits; their test counts are not claims about the latest main revision.
Private licensed-input validation is separate and never uploads source assets to
this public repository. CI cannot certify a user's live GUI or artistic result.

''')
p=Path('docs/LOCAL_MOTION_SESSION_HANDOFF.md')
p.write_text('> **Historical session record.** For the current branch, contributor workflow and\n> acceptance gates, read [the current handoff](CONSOLIDATION.md). The dated\n> instructions below are preserved as evidence, not current merge restrictions.\n\n'+p.read_text())
section('docs/TRANSITION_LAB.md', 'This website visualizes', '## What is shown', '''This website visualizes generated source motions through the current reviewed
runtime on `main`. It publishes only synthetic, allowlisted demo media. This is
not a harness release or publication of private source assets.

''')
section('docs/TRANSITION_LAB.md', '`.github/workflows/transition-lab-pages.yml` runs', 'The build runs', '''`.github/workflows/transition-lab-pages.yml` validates pull requests, main and the
one-time consolidation branch. Only the main push/manual path can deploy; PR
builds cannot publish. Each build creates its own media from the same source SHA,
rather than relying on an expiring artifact from a different revision.

''')
for path in ('.github/workflows/action-collision.yml', '.github/workflows/transition-lab-deploy.yml'):
    Path(path).unlink()
