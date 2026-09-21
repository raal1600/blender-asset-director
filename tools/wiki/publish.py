"""Fast-forward-only wiki sync with managed-file conflict checks and read-back."""
from __future__ import annotations
import argparse
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from build import ROOT, SCHEMA, MANIFEST, PAGE, SHA, digest, text


def git(path, *args, env=None, check=True):
    # Wiki hashes bind exact UTF-8/LF bytes on Windows as well as POSIX.
    result = subprocess.run(['git', '-c', 'core.autocrlf=false', '-C', str(path), *args], env=env, capture_output=True,
                            text=True, encoding='utf-8', timeout=120)
    if check and result.returncode:
        # Credentials are never placed in command arguments or persisted in Git config.
        raise RuntimeError('Git '+args[0]+' failed; check repository availability, authentication or concurrent writes')
    return result


def load_manifest(directory, repository):
    path = Path(directory)/MANIFEST
    if path.is_symlink():
        raise ValueError('Symlink manifest refused')
    data = json.loads(text(path))
    if data.get('schema') != SCHEMA or data.get('repository') != repository or not SHA.fullmatch(data.get('source_commit', '')):
        raise ValueError('Invalid wiki manifest identity')
    pages = data.get('pages')
    if not isinstance(pages, dict) or not pages or 'Home.md' not in pages:
        raise ValueError('Missing managed pages')
    if len({name.casefold() for name in pages}) != len(pages):
        raise ValueError('Case-insensitive managed page collision')
    for name, checksum in pages.items():
        if not name.endswith('.md') or not PAGE.fullmatch(name[:-3]) or not re.fullmatch(r'[a-f0-9]{64}', checksum):
            raise ValueError('Unsafe managed page or hash')
    return data


def verify(directory, manifest):
    for name, checksum in manifest['pages'].items():
        path = Path(directory)/name
        if path.is_symlink() or not path.is_file() or digest(path.read_bytes()) != checksum:
            raise ValueError('Missing, edited or unsafe managed page: '+name)


def sync(source, destination, repository):
    source, destination = Path(source), Path(destination)
    if source.is_symlink() or destination.is_symlink():
        raise ValueError('Symlink directory refused')
    incoming = load_manifest(source, repository)
    verify(source, incoming)
    expected_files = set(incoming['pages']) | {MANIFEST}
    if {p.name for p in source.iterdir()} != expected_files:
        raise ValueError('Unexpected files in generated wiki')
    if (destination/MANIFEST).is_symlink():
        raise ValueError('Symlink destination manifest refused')
    old = load_manifest(destination, repository) if (destination/MANIFEST).exists() else None
    if old:
        verify(destination, old)  # Check everything before changing any file.
    previous = old['pages'] if old else {}
    seed = {'<!-- live-wiki-bootstrap -->', 'Welcome to the '+repository.split('/')[1]+' wiki!'}
    for name in incoming['pages']:
        path = destination/name
        if path.is_symlink():
            raise ValueError('Symlink target refused: '+name)
        if (path.exists() or path.is_symlink()) and name not in previous:
            if name != 'Home.md' or not path.is_file() or text(path).strip() not in seed:
                raise ValueError('Unowned wiki page would be overwritten: '+name)
    for name in previous.keys() - incoming['pages'].keys():
        (destination/name).unlink()
    for name in incoming['pages']:
        (destination/name).write_bytes((source/name).read_bytes())
    (destination/MANIFEST).write_bytes((source/MANIFEST).read_bytes())
    verify(destination, incoming)
    return incoming, sorted(set(previous) | set(incoming['pages']) | {MANIFEST})


def select_source(checkout, default_branch, bootstrap_branch, env=None):
    for branch in (default_branch, bootstrap_branch):
        git(checkout, 'check-ref-format', '--branch', branch)
    git(checkout, 'fetch', '--no-tags', '--depth=1', 'origin',
        '+refs/heads/'+default_branch+':refs/remotes/wiki/default', env=env)
    present = git(checkout, 'cat-file', '-e', 'refs/remotes/wiki/default:wiki/config.json', check=False)
    return default_branch if present.returncode == 0 else bootstrap_branch


def assert_current(checkout, manifest, default_branch, bootstrap_branch, env=None):
    selected = select_source(checkout, default_branch, bootstrap_branch, env)
    if selected != manifest['source_branch']:
        raise ValueError('Publishing branch changed; rebuild from '+selected)
    remote = git(checkout, 'ls-remote', '--heads', 'origin', 'refs/heads/'+selected, env=env).stdout.split()
    if not remote or remote[0] != manifest['source_commit']:
        raise ValueError('Source branch moved; only its latest commit may publish')
    if git(checkout, 'rev-parse', 'HEAD').stdout.strip() != manifest['source_commit']:
        raise ValueError('Build does not match the publisher checkout')


def publish(source, remote, repository, env=None, before_push=None):
    with tempfile.TemporaryDirectory(prefix='live-wiki-publish-') as tmp:
        root = Path(tmp)
        wiki = root/'wiki'
        clone = git(root, 'clone', '--depth=1', remote, str(wiki), env=env, check=False)
        if clone.returncode:
            raise RuntimeError('WIKI_UNAVAILABLE: wiki clone failed. Check network and contents: write; '
                               'for a new wiki, save Home with <!-- live-wiki-bootstrap --> in the Wiki tab, then rerun this job.')
        manifest, names = sync(source, wiki, repository)
        git(wiki, 'add', '--all', '--', *names)
        change = git(wiki, 'diff', '--cached', '--quiet', check=False)
        if change.returncode not in (0, 1):
            raise RuntimeError('Cannot compare wiki changes')
        if before_push:
            before_push()
        if change.returncode:
            git(wiki, '-c', 'user.name=github-actions[bot]', '-c',
                'user.email=41898282+github-actions[bot]@users.noreply.github.com',
                '-c', 'commit.gpgsign=false', 'commit', '-m', 'docs: sync '+manifest['source_commit'])
            branch = git(wiki, 'symbolic-ref', '--short', 'HEAD').stdout.strip()
            git(wiki, 'push', 'origin', 'HEAD:refs/heads/'+branch, env=env)
        fresh = root/'readback'
        git(root, 'clone', '--depth=1', remote, str(fresh), env=env)
        if load_manifest(fresh, repository) != manifest:
            raise ValueError('Read-back manifest differs from generated source')
        verify(fresh, manifest)
        return {'status': 'PUBLISHED' if change.returncode else 'UNCHANGED',
                'source_commit': manifest['source_commit'], 'source_branch': manifest['source_branch'],
                'wiki_commit': git(fresh, 'rev-parse', 'HEAD').stdout.strip(),
                'pages_verified': len(manifest['pages']), 'readback_verified': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--default-branch', required=True)
    parser.add_argument('--bootstrap-branch', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    report = {'status': 'FAIL'}
    try:
        if not re.fullmatch(r'[\w.-]+/[\w.-]+', args.repository):
            raise ValueError('Invalid repository')
        token = os.environ.get('GH_TOKEN')
        if not token:
            raise ValueError('Automatic workflow token is missing')
        env = dict(os.environ)
        authorization = base64.b64encode(('x-access-token:'+token).encode()).decode()
        env.update(GIT_TERMINAL_PROMPT='0', GIT_CONFIG_COUNT='1',
                   GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',
                   GIT_CONFIG_VALUE_0='AUTHORIZATION: basic '+authorization)
        manifest = load_manifest(args.source, args.repository)
        current = lambda: assert_current(ROOT, manifest, args.default_branch, args.bootstrap_branch, env)
        current()
        report = publish(args.source, 'https://github.com/'+args.repository+'.wiki.git',
                         args.repository, env, before_push=current)
        print(json.dumps(report))
    except Exception as error:
        report['error'] = str(error)
        raise SystemExit(str(error))
    finally:
        target = Path(args.report)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
