#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def addtree(zf,root,prefix):
    base=ROOT/prefix
    if not base.exists(): return
    for p in base.rglob("*"):
        if p.is_file(): zf.write(p,str(p.relative_to(ROOT)))

def main():
    p=argparse.ArgumentParser(); p.add_argument("--output",type=Path,default=ROOT/"dist")
    a=p.parse_args(); out=a.output
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True)
    reg=json.loads((ROOT/"skill-registry.json").read_text(encoding="utf-8"))
    artifacts=[]
    for e in reg["skills"]:
        if e["status"]!="active": continue
        z=out/f"{e['name']}-{e['version']}.zip"
        with zipfile.ZipFile(z,"w",zipfile.ZIP_DEFLATED) as f:
            addtree(f,ROOT,"skills/"+e["name"])
            f.write(ROOT/e["contract"],e["contract"])
            for rel in e.get("shared_dependencies",[]): f.write(ROOT/rel,rel)
        artifacts.append(z)
    bundle=out/f"skills-bundle-{reg['repository_version']}.zip"
    with zipfile.ZipFile(bundle,"w",zipfile.ZIP_DEFLATED) as f:
        for prefix in ("skills","contracts","shared","examples","schemas","scripts","bin","evals","docs"):
            addtree(f,ROOT,prefix)
        for rel in ("README.md","VERSIONING.md","CHANGELOG.md","skill-registry.json"):
            f.write(ROOT/rel,rel)
    artifacts.append(bundle)
    sums=out/"SHA256SUMS.txt"
    sums.write_text("".join(f"{digest(x)}  {x.name}\n" for x in artifacts),encoding="utf-8")
    for x in artifacts+[sums]: print(x)
    return 0
if __name__=="__main__": raise SystemExit(main())
