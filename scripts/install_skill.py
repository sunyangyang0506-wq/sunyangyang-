#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load_registry():
    return json.loads((ROOT/"skill-registry.json").read_text(encoding="utf-8"))

def active_entries():
    return [x for x in load_registry()["skills"] if x["status"]=="active"]

def active_skills():
    return [x["name"] for x in active_entries()]

def by_name():
    return {x["name"]:x for x in active_entries()}

def parse_version(path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("version:"):
            return line.split(":",1)[1].strip().strip("'\"")
    raise ValueError(f"version not found in {path}")

def vt(v):
    return tuple(int(x) for x in v.split("-",1)[0].split("+",1)[0].split("."))

def install_entry(entry,target,force=False,upgrade=False):
    name=entry["name"]; dest=target/"skills"/name
    if dest.exists():
        current=parse_version(dest/"SKILL.md")
        if upgrade and vt(entry["version"])<=vt(current):
            return dest,"up-to-date"
        if not force and not upgrade:
            raise FileExistsError(f"{dest} already exists; use --force or --upgrade")
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copytree(ROOT/"skills"/name,dest)
    csrc=ROOT/entry["contract"]; cdst=target/entry["contract"]
    cdst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(csrc,cdst)
    for rel in entry.get("shared_dependencies",[]):
        src=ROOT/rel; dst=target/rel
        dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
    (dest/".skill-install.json").write_text(json.dumps({
        "name":name,"version":entry["version"],
        "repository_version":load_registry()["repository_version"]
    },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return dest,"installed"

def install(name,target,force=False,upgrade=False):
    entry=by_name().get(name)
    if not entry: raise ValueError(f"Unknown/inactive skill: {name}")
    return install_entry(entry,target,force,upgrade)[0]

def check_updates(target):
    out=[]
    for e in active_entries():
        path=target/"skills"/e["name"]/"SKILL.md"
        if not path.exists(): out.append((e["name"],"not-installed",e["version"])); continue
        current=parse_version(path)
        state="update-available" if vt(e["version"])>vt(current) else "current"
        out.append((e["name"],state,f"{current} -> {e['version']}"))
    return out

def main():
    p=argparse.ArgumentParser(description="Install/upgrade Skills")
    p.add_argument("skill",nargs="?"); p.add_argument("--target",type=Path)
    p.add_argument("--force",action="store_true"); p.add_argument("--upgrade",action="store_true")
    p.add_argument("--all",action="store_true"); p.add_argument("--list",action="store_true")
    p.add_argument("--check-updates",action="store_true")
    a=p.parse_args()
    if a.list:
        for e in active_entries(): print(f"{e['name']}\t{e['version']}")
        return 0
    if not a.target: p.error("--target is required")
    target=a.target.expanduser().resolve()
    if a.check_updates:
        for row in check_updates(target): print("\t".join(row))
        return 0
    names=list(by_name()) if a.all else [a.skill] if a.skill else []
    if not names: p.error("provide a skill or --all")
    try:
        for name in names:
            e=by_name().get(name)
            if not e: raise ValueError(f"Unknown/inactive skill: {name}")
            dest,state=install_entry(e,target,a.force,a.upgrade)
            print(f"{name}\t{state}\t{dest}")
        return 0
    except (ValueError,FileExistsError) as exc:
        print("ERROR:",exc,file=sys.stderr); return 1

if __name__=="__main__":
    raise SystemExit(main())
