"""Deliver a validated English image post and video reply to one bound X account."""
import argparse
import base64
import contextlib
import fcntl
import html
import json
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from edition import require, sha, today, validate

SLOTS = {"root": "card.png", "video": "explainer.mp4"}

class X:
    def __init__(self, token):
        self.token = token

    def api(self, method, path, data=None, mime="application/json"):
        if data is not None and not isinstance(data, bytes):
            data = json.dumps(data).encode()
        request = Request("https://api.x.com/2/" + path, data=data, method=method,
                          headers={"Authorization": "Bearer " + self.token, "Content-Type": mime})
        with urlopen(request, timeout=40) as result:
            payload = result.read()
        return json.loads(payload) if payload else {}

    def image(self, path, alt):
        require(path.stat().st_size <= 5_000_000, "Image exceeds upload limit")
        media = base64.b64encode(path.read_bytes()).decode("ascii")
        result = self.api("POST", "media/upload", {"media": media, "media_category": "tweet_image"})
        media_id = str(result["data"]["id"])
        self.api("POST", "media/metadata", {"id": media_id, "metadata": {"alt_text": {"text": alt}}})
        return media_id

    def video(self, path):
        spec = {"media_type": "video/mp4", "media_category": "tweet_video", "total_bytes": path.stat().st_size}
        media_id = str(self.api("POST", "media/upload/initialize", spec)["data"]["id"])
        upload = f"media/upload/{media_id}/"
        with path.open("rb") as stream:
            for index, chunk in enumerate(iter(lambda: stream.read(4 * 1024 * 1024), b"")):
                boundary = uuid.uuid4().hex
                prefix = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"segment_index\""
                          f"\r\n\r\n{index}\r\n--{boundary}\r\nContent-Disposition: form-data; "
                          'name="media"; filename="segment.mp4"\r\nContent-Type: video/mp4\r\n\r\n')
                body = prefix.encode() + chunk + f"\r\n--{boundary}--\r\n".encode()
                self.api("POST", upload + "append", body, "multipart/form-data; boundary=" + boundary)
        result = self.api("POST", upload + "finalize", {})
        info = result["data"].get("processing_info")
        deadline = time.monotonic() + 240
        while info and info.get("state") != "succeeded":
            require(info.get("state") in {"pending", "in_progress"}, "Video processing failed")
            require(time.monotonic() < deadline, "Video processing timeout; no post created")
            time.sleep(max(1, min(30, int(info.get("check_after_secs", 2)))))
            info = self.api("GET", "media/upload?" + urlencode(
                {"command": "STATUS", "media_id": media_id}))["data"]["processing_info"]
        return media_id

    def verify(self, post_id, user, text, media_id, parent=None):
        require(str(post_id).isdigit(), "Invalid X status ID")
        fields = urlencode({"tweet.fields":"author_id,attachments,entities,referenced_tweets"})
        data = self.api("GET", f"tweets/{post_id}?{fields}")["data"]
        require(str(data["author_id"]) == user and str(data["id"]) == str(post_id), "Unexpected receipt identity")
        keys = data.get("attachments", {}).get("media_keys", [])
        require(len(keys) == 1 and keys[0].split("_")[-1] == str(media_id), "Wrong media on X receipt")
        actual = html.unescape(data["text"])
        for entity in data.get("entities", {}).get("urls", []):
            if entity["expanded_url"] in text:
                actual = actual.replace(entity["url"], entity["expanded_url"])
        # X may append a separate t.co media permalink; the attachment ID above must also match.
        if actual != text:
            actual = re.sub(r"\s+https://t\.co/[a-zA-Z0-9]+$", "", actual)
        require(actual.strip() == text.strip(), "Receipt text mismatch")
        parents = [str(t["id"]) for t in data.get("referenced_tweets", []) if t["type"] == "replied_to"]
        require(parents == ([str(parent)] if parent else []), "Wrong thread on X receipt")

def preflight(packet, folder):
    d = json.loads(packet.read_text())
    validate(d)
    manifest = json.loads((folder/"manifest.json").read_text())
    require(manifest["edition_sha256"] == sha(packet), "Edition changed; render again")
    for name in (*SLOTS.values(), "captions.srt"):
        require(sha(folder/name) == manifest["media_sha256"][name], "Asset changed: " + name)
    return d

@contextlib.contextmanager
def ledger(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with Path(str(path) + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with contextlib.closing(sqlite3.connect(path, isolation_level=None)) as db:
            db.row_factory = sqlite3.Row
            db.execute("""CREATE TABLE IF NOT EXISTS issues (
                account TEXT, day TEXT, story TEXT, revision INTEGER, digest TEXT,
                PRIMARY KEY (account, day), UNIQUE (account, story, revision))""")
            db.execute("""CREATE TABLE IF NOT EXISTS deliveries (
                account TEXT, day TEXT, slot TEXT, media_id TEXT, post_id TEXT, state TEXT,
                PRIMARY KEY (account, day, slot))""")
            yield db

def deliver(api, db, d, digest, folder, account, recover):
    live_user = api.api("GET", "users/me")["data"]
    require(str(live_user["id"]) == account, "Bound X account mismatch")
    key = (account, d["day"])
    current_day = d["day"] == today().isoformat()
    existing = db.execute("SELECT * FROM issues WHERE account=? AND day=?", key).fetchone()
    if existing:
        require(existing["digest"] == digest, "A different packet is reserved for this account/day")
    else:
        require(current_day and not recover, "New live edition must be checked today")
        db.execute("INSERT INTO issues VALUES (?,?,?,?,?)", (*key, d["story_key"], d["revision"], digest))
    rows = {r["slot"]:r for r in db.execute("SELECT * FROM deliveries WHERE account=? AND day=?", key)}
    require(set(recover) <= set(rows), "Recovery requires an existing uncertain attempt")
    results, uploads = {}, {}
    for slot, row in rows.items():
        if row["state"] == "pending":
            require(slot in recover or row["post_id"], "Uncertain " + slot + " write; reconcile on X before retry")
        if slot in recover:
            require(row["state"] == "pending" and (not row["post_id"] or row["post_id"] == recover[slot]),
                    "Recovery conflicts with saved receipt")
    # Prepare both assets before the first post. Re-upload only missing, unattempted slots.
    if current_day:
        for slot, filename in SLOTS.items():
            if slot not in rows:
                path = folder / filename
                uploads[slot] = (api.image(path,d["public_copy"]["alt"]) if slot == "root" else api.video(path))
    for slot in SLOTS:
        text = d["public_copy"][slot]
        parent = results.get("root") if slot == "video" else None
        row = rows.get(slot)
        if row:
            media_id = row["media_id"]
            post_id = row["post_id"] or recover.get(slot)
        else:
            require(current_day, "Old edition reconciled only; missing slot needs a fresh editorial decision")
            media_id = uploads[slot]
            payload = {"text":text, "media":{"media_ids":[media_id]}}
            if parent:
                payload["reply"] = {"in_reply_to_tweet_id":parent}
            db.execute("INSERT INTO deliveries VALUES (?,?,?,?,?,?)", (*key,slot,media_id,None,"pending"))
            try:
                post_id = str(api.api("POST", "tweets", payload)["data"]["id"])
            except HTTPError as e:
                # These definite refusals create no post. An ambiguous timeout or 5xx keeps the reservation.
                if e.code in {400,401,402,403,404,413,422,429}:
                    db.execute("DELETE FROM deliveries WHERE account=? AND day=? AND slot=?", (*key,slot))
                raise
            require(post_id.isdigit(), "Missing X status identifier")
            db.execute("UPDATE deliveries SET post_id=? WHERE account=? AND day=? AND slot=?", (post_id,*key,slot))
        api.verify(post_id,account,text,media_id,parent)
        db.execute("UPDATE deliveries SET post_id=?,state='verified' WHERE account=? AND day=? AND slot=?",
                   (post_id,*key,slot))
        results[slot] = post_id
    return {s:f"https://x.com/{live_user['username']}/status/{p}" for s,p in results.items()}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("folder", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--send", action="store_true")
    parser.add_argument("--state", type=Path)
    parser.add_argument("--recover", action="append", default=[], metavar="SLOT=STATUS_ID")
    a = parser.parse_args()
    d = preflight(a.packet, a.folder)
    if a.check:
        print("Checked packet, media and captions. No network calls or account writes.")
        return
    require(a.state and os.environ.get("X_USER_ACCESS_TOKEN") and os.environ.get("X_EXPECTED_USER_ID"),
            "Configure the private persistent ledger and X user authorization")
    recover = dict(item.split("=",1) for item in a.recover)
    require(all(k in SLOTS and v.isdigit() for k,v in recover.items()), "Invalid recovery argument")
    os.umask(0o077)
    with ledger(a.state) as db:
        print(json.dumps(deliver(X(os.environ["X_USER_ACCESS_TOKEN"]), db, d, sha(a.packet), a.folder,
                                 os.environ["X_EXPECTED_USER_ID"], recover), indent=2))

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, sqlite3.Error) as error:
        raise SystemExit(str(error)) from None
