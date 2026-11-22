"""Summarize consent-based, pseudonymous inquiry events from an authorized private inbox export."""
import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

STATES = ("received", "qualified", "handed_off", "confirmed", "closed")
FIELDS = {"inquiry_key", "post_id", "category", "stage", "at", "opted_in", "specific_need"}
CATEGORIES = {"navigation", "partnership", "medical_question", "other"}

def summarize(events):
    cases = defaultdict(list)
    for event in events:
        if set(event) != FIELDS:
            raise ValueError("Use the minimal event schema. Do not include names, messages or contact details.")
        key = event["inquiry_key"]
        if not re.fullmatch(r"[a-f0-9]{32}", key):
            raise ValueError("Use a stable, locally assigned random inquiry key")
        if event["category"] not in CATEGORIES or event["stage"] not in STATES:
            raise ValueError("Invalid category or stage")
        post = event["post_id"]
        if post is not None and not re.fullmatch(r"[0-9]{1,24}", str(post)):
            raise ValueError("Use the source X post ID or null")
        at = datetime.fromisoformat(event["at"].replace("Z","+00:00"))
        if at.utcoffset() is None:
            raise ValueError("Use a timezone-aware event time")
        if any(type(event[k]) is not bool for k in ("opted_in","specific_need")):
            raise ValueError("Consent and need must be booleans")
        if event["stage"] in {"qualified","handed_off","confirmed"} and not (
                event["opted_in"] and event["specific_need"] and event["category"] in {"navigation","partnership"}):
            raise ValueError("Need explicit opt-in and a concrete nonclinical request for this stage")
        cases[key].append((at, event))

    counts = defaultdict(Counter)
    for history in cases.values():
        history.sort(key=lambda pair: pair[0])
        first = history[0][1]
        group = (str(first["post_id"] or "unattributed"), first["category"])
        stages = []
        seen = set()
        for stamp, event in history:
            identity = (stamp,tuple(sorted(event.items())))
            if identity in seen:
                continue
            seen.add(identity)
            if event["post_id"] != first["post_id"] or event["category"] != first["category"]:
                raise ValueError("Conflicting attribution/category within one inquiry")
            stage = event["stage"]
            if stage in stages and stage != stages[-1]:
                raise ValueError("Stage regression")
            if not stages or stage != stages[-1]:
                previous = stages[-1] if stages else None
                allowed = {None:{"received"}, "received":{"qualified","closed"},
                           "qualified":{"handed_off","closed"}, "handed_off":{"confirmed","closed"},
                           "confirmed":{"closed"}, "closed":set()}
                if stage not in allowed[previous]:
                    raise ValueError("Incomplete or conflicting stage history")
                stages.append(stage)
        counts[group].update(stages)
    return [{"post_id":post,"category":category,**{s:c[s] for s in STATES},
             "qualification_rate":round(c["qualified"]/c["received"],4) if c["received"] else None,
             "confirmed_per_qualified":round(c["confirmed"]/c["qualified"],4) if c["qualified"] else None}
            for (post,category),c in sorted(counts.items())]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("events",type=Path)
    args = parser.parse_args()
    with args.events.open() as f:
        data = summarize(json.loads(row) for row in f if row.strip())
    print(json.dumps(data,indent=2))
