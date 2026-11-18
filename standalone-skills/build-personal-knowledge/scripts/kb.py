"""Local knowledge ledger. Python 3.10+. All material must pass a source policy."""
import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from render_knowledge import render

ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")
SECRET = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY|(?:gh[pousr]_|github_pat_|sk-)[\w-]{12,}|Bearer\s+\S{8,}|(?:api[_-]?key|password|token|口令|密码)\s*[:=]\s*\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", re.I)
ROLES = {"user": {"idea", "decision", "revision", "question"}, "assistant": {"proposal", "method"},
         "tool": {"execution", "verification", "failure"}, "document": {"method", "artifact"}}
FIELDS = ("topic", "title", "statement", "conditions", "locator", "kind", "role", "level", "occurred_at", "parent", "relation", "derived_from", "span_digest")
RELATIONS = {"deepens", "branches_from", "supersedes", "contradicts", "tests", "reuses", "supports"}

def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

def digest(value):
    return hashlib.sha256(dump(value).encode()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def clock(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("a timezone is required")
    return dt.astimezone(timezone.utc)

def check_id(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError("invalid identifier")
    return value

def open_db(path):
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version not in (0, 1):
        raise ValueError("unsupported database version")
    db.executescript("""
      CREATE TABLE IF NOT EXISTS events(
        seq INTEGER PRIMARY KEY, id TEXT NOT NULL UNIQUE, source TEXT NOT NULL,
        item TEXT NOT NULL, data TEXT NOT NULL, signature TEXT NOT NULL,
        UNIQUE(source,item,signature));
      CREATE TABLE IF NOT EXISTS review_log(
        source TEXT NOT NULL, fingerprint TEXT NOT NULL, PRIMARY KEY(source,fingerprint));
      CREATE TABLE IF NOT EXISTS sync_log(
        repo TEXT NOT NULL, batch TEXT NOT NULL, sha TEXT NOT NULL, PRIMARY KEY(repo,batch));
      PRAGMA user_version=1;
    """)
    return db

def allowed(policy, source, action):
    grant = policy.get("sources", {}).get(source, {})
    return grant.get("read") is True and grant.get("store") is True and grant.get(action) is True

def classify(role, text):
    if role == "assistant":
        return "proposal"
    if role == "tool":
        return "execution"
    if role == "document":
        return "artifact"
    if re.search(r"改为|调整为|改成|之前.+现在|不再", text):
        return "revision"
    if re.search(r"决定|确定采用|选定", text):
        return "decision"
    if text.endswith(("?", "？")):
        return "question"
    return "idea"

def ingest(db, policy, batch):
    source = check_id(batch["source"])
    if not allowed(policy, source, "store"):
        raise ValueError("source not authorized")
    grant = policy["sources"][source]
    rows = batch["items"]
    if not isinstance(rows, list):
        raise ValueError("items must be a list")
    added = ignored = 0
    with db:
        db.execute("BEGIN IMMEDIATE")
        for raw in rows:
            item = check_id(raw["item"])
            topic = check_id(raw["topic"])
            if topic not in grant.get("topics", []):
                raise ValueError("topic outside grant")
            if raw.get("sensitivity") != "ordinary" or raw.get("role") not in ROLES:
                ignored += 1
                continue
            # Never retain raw tool streams, credentials, other JSON fields or the message body.
            plain = raw.get("statement", "").strip()
            if not plain or plain.lower().strip("。.!！ ") in {"嗯", "嗯嗯", "继续", "好的", "ok", "什么进展"}:
                ignored += 1
                continue
            role, level = raw["role"], raw["level"]
            if level not in {"original", "summary", "receipt"}:
                raise ValueError("invalid evidence level")
            kind = raw.get("kind") or classify(role, plain)
            if kind not in ROLES[role]:
                raise ValueError("incompatible attribution")
            if kind == "verification" and (role, level) != ("tool", "receipt"):
                raise ValueError("verification requires a tool receipt")
            for key in ("title", "locator"):
                if not isinstance(raw.get(key), str) or not raw[key].strip():
                    raise ValueError("title and evidence locator required")
            data = {key: raw.get(key) for key in FIELDS}
            data.update(kind=kind, statement=plain, local_only=raw.get("local_only") is True)
            if data["occurred_at"]:
                data["occurred_at"] = clock(data["occurred_at"]).isoformat()
            if any(not isinstance(v, (str, type(None))) for k,v in data.items() if k != "local_only"):
                raise ValueError("unexpected structured field")
            if len(plain) > 1000 or any(len(v) > 1000 for v in data.values() if isinstance(v,str)):
                raise ValueError("use a short derived record")
            if SECRET.search(dump(data)):
                ignored += 1
                continue
            if bool(data["parent"]) != bool(data["relation"]) or (data["relation"] and data["relation"] not in RELATIONS):
                raise ValueError("invalid relation")
            if data["parent"]:
                parent = db.execute("SELECT source,data FROM events WHERE id=?", (data["parent"],)).fetchone()
                if not parent or not allowed(policy, parent["source"], "store") or json.loads(parent["data"])["topic"] != topic:
                    raise ValueError("inaccessible parent or different topic")
            data["state"] = ("candidate" if level == "summary" or "kind" not in raw
                             else {"assistant":"suggested","user":"expressed","document":"documented","tool":"observed"}[role])
            sig = digest(data)
            eid = "E-" + digest([source, item, sig])[:28]
            count = db.execute("INSERT OR IGNORE INTO events(id,source,item,data,signature) VALUES(?,?,?,?,?)",
                               (eid,source,item,dump(data),sig)).rowcount
            added += count
    return {"inserted":added, "filtered":ignored, "duplicate":len(rows)-added-ignored}

def events(db, policy, action="store", topic=None, as_of=None):
    result = []
    for row in db.execute("SELECT * FROM events ORDER BY seq"):
        if not allowed(policy, row["source"], action):
            continue
        data = json.loads(row["data"])
        if action=="sync" and data.get("local_only"):
            continue
        if data["topic"] not in policy["sources"][row["source"]].get("topics", []):
            continue
        if topic and data["topic"] != topic or as_of is not None and row["seq"] > as_of:
            continue
        result.append(dict(data, id=row["id"], revision=row["seq"], source=row["source"], item=row["item"]))
    # A record derived from a removed or non-exportable parent cannot escape by itself.
    visible = set()
    valid = []
    for row in result:
        if not row["parent"] or row["parent"] in visible:
            visible.add(row["id"])
            valid.append(row)
    return valid

def build_files(rows):
    thoughts, cards, edges, files, by_topic = [], [], [], {}, {}
    for row in rows:
        by_topic.setdefault(row["topic"], []).append(row)
        node = dict(id=row["id"],title=row["title"],statement=row["statement"],
                    conditions=row["conditions"] or "待补充",
                    source=f'{row["state"]} · {row["role"]} · {row["level"]} · {row["locator"]}',
                    role=row["role"],kind=row["kind"],state=row["state"],level=row["level"])
        thoughts.append(node)
        if row["relation"]:
            edges.append({"from":row["parent"],"to":row["id"],"type":row["relation"],"evidence":row["locator"]})
        if row["kind"] == "method":
            card = dict(node, id="K-"+row["id"][2:],thought_ids=[row["id"]],epistemic_status=row["state"])
            cards.append(card)
            files["knowledge/"+card["id"]+".json"] = pretty(card)
    for topic, history in by_topic.items():
        files["evolution/"+topic+".jsonl"] = "".join(dump(row)+"\n" for row in history)
        files["ideas/"+topic+".json"] = pretty({"id":topic,"events":[r["id"] for r in history]})
    snapshot = {"title":"个人知识库","thoughts":thoughts,"knowledge":cards,"relations":edges,
                "status":{"来源范围":"已授权的可见材料","事件数":len(rows),"方法卡":len(cards)}}
    files["indexes/topics.json"] = pretty({k:len(v) for k,v in by_topic.items()})
    files["indexes/snapshot.json"] = pretty(snapshot)
    files["views/index.html"] = render(snapshot)
    files["README.md"] = "# 个人知识库\n\n[主题索引](indexes/topics.json) · [思路与知识](indexes/snapshot.json) · [离线视图](views/index.html)\n\n" + "".join(
        "- ["+topic+"](evolution/"+topic+".jsonl) · "+str(len(history))+" 条记录\n" for topic,history in by_topic.items())
    return files

def pretty(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+"\n"

def export_snapshot(db, policy, dest):
    files = build_files(events(db, policy, "sync"))
    batch = digest(files)
    dest.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = dest/batch
    if not target.is_dir():
        with tempfile.TemporaryDirectory(dir=dest) as temp:
            stage = Path(temp)/"batch"
            stage.mkdir()
            for name, body in files.items():
                path = stage/name
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(body,encoding="utf-8")
            try:
                stage.rename(target)
            except OSError:
                if not target.is_dir():
                    raise
    actual = {p.relative_to(target).as_posix():p.read_text() for p in target.rglob("*") if p.is_file()}
    if actual != files:
        raise ValueError("snapshot differs from ledger")
    return {"batch":batch,"directory":str(target),"files":len(files)}

def review(db, policy, meta, now, hours):
    if hours < 1:
        raise ValueError("idle hours must be positive")
    source = check_id(meta["source"])
    if not allowed(policy,source,"store"):
        raise ValueError("source not authorized")
    if meta.get("coverage") != "complete" or not meta.get("last_activity") or not meta.get("checked_through"):
        return {"review":"coverage_unknown"}
    last = clock(meta["last_activity"])
    if clock(meta["checked_through"]) < now or last > now:
        return {"review":"coverage_unknown"}
    if now-last < timedelta(hours=hours):
        return {"review":"active"}
    rows = [r for r in events(db,policy) if r["source"]==source]
    key = digest([last.isoformat(),rows])
    with db:
        inserted = db.execute("INSERT OR IGNORE INTO review_log VALUES(?,?)",(source,key)).rowcount
    return {"review":"ready" if inserted else "unchanged","fingerprint":key,"events":[r["id"] for r in rows]}

def main():
    os.umask(0o077)
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--policy", required=True)
    cmd = ap.add_subparsers(dest="cmd", required=True)
    for name in ("ingest","extract","review"):
        sub = cmd.add_parser(name)
        sub.add_argument("input")
        if name=="review":
            sub.add_argument("--at")
            sub.add_argument("--idle-hours",type=int,default=48)
    cmd.add_parser("verify")
    show = cmd.add_parser("show")
    show.add_argument("topic",nargs="?")
    show.add_argument("--as-of",type=int)
    exp = cmd.add_parser("export")
    exp.add_argument("directory",type=Path)
    sync = cmd.add_parser("sync")
    sync.add_argument("--dry-run",action="store_true")
    args = ap.parse_args()
    policy = read(args.policy)
    db = open_db(args.db)
    try:
        if args.cmd in {"extract","ingest"}:
            output = ingest(db,policy,read(args.input))
        elif args.cmd=="show":
            output = events(db,policy,topic=args.topic,as_of=args.as_of)
        elif args.cmd=="export":
            output = export_snapshot(db,policy,args.directory)
        elif args.cmd=="verify":
            rows = events(db,policy)
            build_files(rows)
            if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise ValueError("database integrity failure")
            output = {"integrity":"ok","events":len(rows),"sources":sorted({r["source"] for r in rows})}
        elif args.cmd=="review":
            now = clock(args.at) if args.at else datetime.now(timezone.utc)
            output = review(db,policy,read(args.input),now,args.idle_hours)
        else:
            from kb_sync import publish
            output = publish(db,policy,build_files(events(db,policy,"sync")),args.dry_run)
        print(pretty(output),end="")
    finally:
        db.close()

if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, sqlite3.Error) as exc:
        sys.exit("kb: "+str(exc))
