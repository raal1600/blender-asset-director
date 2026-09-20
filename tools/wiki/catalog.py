"""Read the real portable command and evidence definitions without running jobs."""
import argparse
import json
from pathlib import Path
import socket
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tools/ci'))


def refuse_network(*args, **kwargs):
    raise RuntimeError('Wiki catalog generation must not access the network')


socket.socket.connect = refuse_network
socket.create_connection = refuse_network
from asset_director import __version__, jobs
from asset_director.cli import parser
from contracts import partitions

commands = {}
for action in parser()._actions:
    if isinstance(action, argparse._SubParsersAction):
        commands.update((name, sub.format_help()) for name, sub in sorted(action.choices.items()))
if not commands or not jobs.OPS or not partitions():
    raise RuntimeError('Empty runtime or evidence inventory')
print(json.dumps({'version': __version__, 'commands': commands,
                  'operations': {key: sorted(value) for key, value in sorted(jobs.OPS.items())},
                  'partitions': [(list(key), list(value)) for key, value in sorted(partitions().items())]}, sort_keys=True))
