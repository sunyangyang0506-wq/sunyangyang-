#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def registry():
    return json.loads((ROOT / "skill-registry.json").read_text(encoding="utf-8"))

def active_skills():
    return [
        item["name"]
        for item in registry().get("skills", [])
        if item.get("status") == "active"
    ]

def install(name: str, target: Path, force: bool = False):
    if name not in active_skills():
        raise ValueError(f"Unknown/inactive skill: {name}")
    source = ROOT / "skills" / name
    destination = target / name
    target.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if not force:
            raise FileExistsError(f"{destination} already exists")
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    return destination

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("skill", nargs="?")
    parser.add_argument("--target", type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        print("\n".join(sorted(active_skills())))
        return 0
    if not args.skill or not args.target:
        parser.error("skill and --target are required unless --list is used")
    try:
        print(install(args.skill, args.target.expanduser().resolve(), args.force))
        return 0
    except (ValueError, FileExistsError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
