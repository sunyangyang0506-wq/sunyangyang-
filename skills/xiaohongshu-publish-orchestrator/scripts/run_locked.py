#!/usr/bin/env python3
"""Serialize one local publisher's entire foreground workflow; never schedules it."""
import argparse
import fcntl
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lock', required=True, type=Path)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('Provide a foreground executor command after --')
    args.lock.parent.mkdir(parents=True, exist_ok=True)
    with args.lock.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({'action': 'SKIP_OCCUPIED'}))
            return 0
        # Inherit lock in the child too, so a wrapper crash cannot release a running executor.
        return subprocess.call(command, pass_fds=(lock.fileno(),))


if __name__ == '__main__':
    raise SystemExit(main())
