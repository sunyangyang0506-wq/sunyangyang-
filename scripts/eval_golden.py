#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"evals"/"golden-cases.json"
ALLOWED={"contains_all","contains_any","not_contains"}

def load_cases():
    return json.loads(DATA.read_text(encoding="utf-8"))

def validate_dataset():
    errors=[]
    data=load_cases()
    registry=json.loads((ROOT/"skill-registry.json").read_text(encoding="utf-8"))
    active={x["name"] for x in registry["skills"] if x["status"]=="active"}
    ids=set(); counts={name:0 for name in active}
    for case in data.get("cases",[]):
        for key in ("id","skill","mode","input","expected","assertions"):
            if key not in case: errors.append(f"{case.get('id','?')}: missing {key}")
        cid=case.get("id")
        if cid in ids: errors.append(f"duplicate case id: {cid}")
        ids.add(cid)
        skill=case.get("skill")
        if skill not in active: errors.append(f"{cid}: inactive/unknown skill {skill}")
        else: counts[skill]+=1
        if not case.get("expected"): errors.append(f"{cid}: expected empty")
        if not case.get("assertions"): errors.append(f"{cid}: assertions empty")
        for a in case.get("assertions",[]):
            if a.get("type") not in ALLOWED: errors.append(f"{cid}: unsupported assertion")
            if not a.get("values"): errors.append(f"{cid}: assertion values empty")
    for name,count in counts.items():
        if count<2: errors.append(f"{name}: requires >=2 golden cases")
    return errors

def check(text,a):
    vals=a["values"]; kind=a["type"]
    if kind=="contains_all": return all(v in text for v in vals)
    if kind=="contains_any": return any(v in text for v in vals)
    if kind=="not_contains": return all(v not in text for v in vals)
    return False

def evaluate(directory):
    passed=total=0; failures=[]
    for case in load_cases()["cases"]:
        path=directory/f"{case['id']}.txt"
        if not path.exists():
            failures.append(f"missing candidate: {path.name}"); continue
        text=path.read_text(encoding="utf-8")
        for idx,a in enumerate(case["assertions"],1):
            total+=1
            if check(text,a): passed+=1
            else: failures.append(f"{case['id']} assertion #{idx} failed")
    return passed,total,failures

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--validate-only",action="store_true")
    p.add_argument("--candidates",type=Path)
    args=p.parse_args()
    errors=validate_dataset()
    if errors:
        for e in errors: print("ERROR:",e,file=sys.stderr)
        return 1
    count=len(load_cases()["cases"])
    print(f"Golden dataset valid: {count} cases.")
    if args.candidates:
        passed,total,failures=evaluate(args.candidates)
        rate=passed/total if total else 0
        print(f"Candidate assertions: {passed}/{total} ({rate:.1%})")
        for f in failures: print("FAIL:",f,file=sys.stderr)
        if failures or rate<0.90: return 1
    return 0

if __name__=="__main__":
    raise SystemExit(main())
