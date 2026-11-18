"""Prepare a scoped host-model batch and validate decisions against local evidence."""
import argparse
import json
import os
from kb import ROLES, SECRET, allowed, digest, events, ingest, open_db, pretty, read

VERSION = "host-v1"

def pending(db,policy,source):
    if not allowed(policy,source,"model"):
        raise ValueError("model processing not granted for this source")
    db.execute("CREATE TABLE IF NOT EXISTS analyses (id TEXT, version TEXT, PRIMARY KEY (id,version))")
    done = {r[0] for r in db.execute("SELECT id FROM analyses WHERE version=?",(VERSION,))}
    return [r for r in events(db,policy) if r["source"]==source and r["local_only"] and r["id"] not in done]

def prepare(db,policy,source):
    grant=policy["sources"][source]
    rows=pending(db,policy,source)
    limit=min(int(grant.get("model_batch_limit",0)),32)
    if limit<1:
        raise ValueError("configure an approved batch size")
    return {"version":VERSION,"source":source,"records":[{k:r[k] for k in ("id","topic","role","statement","level")}
                                                           for r in rows[:limit]]}

def apply(db,policy,source,response):
    # Verify against the source and its current grant again even if it was revoked during inference.
    eligible={r["id"]:r for r in pending(db,policy,source)}
    if response["version"]!=VERSION or response["source"]!=source:
        raise ValueError("stale protocol or source")
    decisions=response["decisions"]
    if not isinstance(decisions,list) or len(decisions)>min(int(policy["sources"][source].get("model_batch_limit",0)),32):
        raise ValueError("batch limit exceeded")
    seen=set()
    rows=[]
    for decision in decisions:
        eid=decision["id"]
        if eid not in eligible or eid in seen:
            raise ValueError("unknown, stale or duplicate source")
        seen.add(eid)
        row=eligible[eid]
        if decision["kind"]=="skip":
            continue
        quote=decision["evidence"]
        if not isinstance(quote,str) or not quote.strip() or quote not in row["statement"]:
            raise ValueError("evidence span not found in selected source")
        if decision["kind"] not in ROLES[row["role"]] or any(SECRET.search(str(v)) for v in decision.values()):
            raise ValueError("invalid attribution or restricted output")
        if not isinstance(decision["statement"],str) or not decision["statement"].strip():
            raise ValueError("missing derived statement")
        # A model cannot certify semantics. Model proposals remain explicitly marked as inferences.
        rows.append(dict(item="D-"+digest([eid,VERSION])[:24],role=row["role"],topic=row["topic"],
                         title=decision["title"],statement=decision["statement"],locator=row["locator"],
                         occurred_at=row["occurred_at"],kind=decision["kind"],level="summary",
                         conditions=decision.get("conditions"),sensitivity="ordinary",
                         derived_from=eid,span_digest=digest(quote)))
    result=ingest(db,policy,{"source":source,"items":rows})
    if result["filtered"]:
        raise ValueError("some candidates filtered; review this batch")
    with db:
        db.executemany("INSERT OR IGNORE INTO analyses VALUES(?,?)",[(eid,VERSION) for eid in seen])
    return result

def main():
    os.umask(0o077)
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ("db","policy","source"):
        ap.add_argument("--"+key,required=True)
    cmd=ap.add_subparsers(dest="cmd",required=True)
    cmd.add_parser("prepare")
    cmd.add_parser("apply").add_argument("result")
    a=ap.parse_args()
    policy=read(a.policy)
    with open_db(a.db) as db:
        out=prepare(db,policy,a.source) if a.cmd=="prepare" else apply(db,policy,a.source,read(a.result))
        print(pretty(out),end="")
if __name__=="__main__":
    main()
