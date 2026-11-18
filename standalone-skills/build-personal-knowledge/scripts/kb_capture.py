"""Read one selected ChatGPT export branch or one known Codex JSONL run, locally."""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from kb import SECRET, allowed, check_id, ingest, open_db, pretty, read

def short_id(*parts):
    return hashlib.sha256(json.dumps(parts,sort_keys=True).encode()).hexdigest()[:28]

def capture_chat(doc, conversation_id, topic):
    sessions = doc if isinstance(doc,list) else [doc]
    matches = [s for s in sessions if (s.get("conversation_id") or s.get("id"))==conversation_id]
    if len(matches)!=1:
        raise ValueError("expected exactly one selected conversation")
    session = matches[0]
    nodes = session["mapping"]
    current = session["current_node"]
    records, seen = [], set()
    while current:
        if current in seen or current not in nodes:
            raise ValueError("broken branch in export")
        seen.add(current)
        node = nodes[current]
        msg = node.get("message") or {}
        role = msg.get("author",{}).get("role")
        content = msg.get("content",{})
        if (role in {"user","assistant"} and content.get("content_type")=="text"
                and not msg.get("metadata",{}).get("is_visually_hidden_from_conversation")
                and msg.get("channel") not in {"analysis","commentary"} and msg.get("recipient","all") in {None,"all"}):
            text = " ".join(p for p in content.get("parts",[]) if isinstance(p,str)).strip()
            if SECRET.search(text):
                current = node.get("parent")
                continue
            timestamp = msg.get("create_time")
            records.append({"item":short_id(conversation_id,current),"topic":topic,"role":role,
                            "level":"original","sensitivity":"ordinary","local_only":True,
                            "title":"对话候选","locator":"export/"+conversation_id+"/"+current,
                            "occurred_at":datetime.fromtimestamp(timestamp,timezone.utc).isoformat() if timestamp else None,
                            "statement":text[:220]})
        current = node.get("parent")
    return list(reversed(records))

def capture_codex(lines, thread_id, topic):
    current = None
    result = []
    turn = 0
    for index,line in enumerate(lines,1):
        obj = json.loads(line)
        kind = obj.get("type")
        if kind=="thread.started":
            current = obj["thread_id"]
            if current!=thread_id:
                raise ValueError("unexpected thread in stream")
        elif current!=thread_id:
            raise ValueError("missing or incorrect thread header")
        elif kind=="turn.started":
            turn += 1
        elif kind in {"turn.completed","turn.failed"}:
            result.append({"item":short_id(current,turn,kind),"topic":topic,"role":"tool",
                           "level":"receipt","kind":"execution" if kind=="turn.completed" else "failure",
                           "sensitivity":"ordinary","title":"Codex 调用终态","locator":f"codex/{current}/line/{index}",
                           "statement":"本次运行结束。" if kind=="turn.completed" else "本次运行失败。"})
        elif kind=="item.completed" and obj.get("item",{}).get("type")=="command_execution":
            item = obj["item"]
            if isinstance(item.get("exit_code"),int):
                result.append({"item":short_id(current,turn,item["id"]),"topic":topic,"role":"tool",
                               "level":"receipt","kind":"execution","sensitivity":"ordinary","title":"命令结束",
                               "locator":f"codex/{current}/line/{index}","statement":f"命令已返回，退出码 {item['exit_code']}。"})
    if current!=thread_id:
        raise ValueError("no matching run")
    return result

def main():
    os.umask(0o077)
    ap = argparse.ArgumentParser(description=__doc__)
    for field in ("db","policy","source","topic","scope"):
        ap.add_argument("--"+field,required=True)
    ap.add_argument("format",choices=("chatgpt","codex"))
    ap.add_argument("input",type=Path)
    a=ap.parse_args()
    policy=read(a.policy)
    if not allowed(policy,a.source,"store"):
        raise SystemExit("source not authorized")
    grant=policy["sources"][a.source]
    if [a.format,a.scope,a.topic] not in grant.get("inputs",[]):
        raise SystemExit("input scope not granted")
    check_id(a.scope)
    if a.format=="chatgpt":
        rows=capture_chat(read(a.input),a.scope,a.topic)
    else:
        with a.input.open() as stream:
            rows=capture_codex((line for line in stream if line.strip()),a.scope,a.topic)
    with open_db(a.db) as db:
        print(pretty(ingest(db,policy,{"source":a.source,"items":rows})),end="")
if __name__=="__main__":
    main()
