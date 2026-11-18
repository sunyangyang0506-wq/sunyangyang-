"""Publish immutable, derived snapshots to one explicitly pinned private GitHub repository."""
import base64
import hashlib
import json
import os
import re
import subprocess
import time

def github(method, endpoint, data=None):
    command = ["gh","api","--hostname","github.com","--method",method,endpoint]
    if data is not None:
        command.extend(["--input","-"])
    try:
        result = subprocess.run(command,input=json.dumps(data) if data is not None else None,
                                text=True,capture_output=True,timeout=60,
                                env=dict(os.environ,GH_PROMPT_DISABLED="1"))
    except subprocess.TimeoutExpired as exc:
        raise OSError("GitHub request timed out; retry the same batch") from exc
    if result.returncode:
        match = re.search(r"HTTP (\d{3})",result.stderr)
        raise OSError("GitHub " + (match[1] if match else "request failed"))
    return json.loads(result.stdout)

def blob_id(body):
    raw = body.encode()
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def publish(db,policy,files,dry_run=False,api=github):
    from kb import digest
    repo = policy.get("repository","")
    if not re.fullmatch(r"[\w.-]+/[\w.-]+",repo) or not str(policy.get("repository_id","")).isdigit():
        raise ValueError("configure the dedicated repository and its numeric ID")
    batch = digest(files)
    if dry_run:
        return {"batch":batch,"files":sorted(files),"status":"preview"}
    endpoint = "repos/"+repo
    def check():
        meta = api("GET",endpoint)
        if (meta.get("private") is not True or meta.get("id") != int(policy["repository_id"])
                or meta.get("full_name","").casefold()!=repo.casefold() or not meta.get("permissions",{}).get("push")):
            raise ValueError("target identity, privacy or write permission mismatch")
        return meta["default_branch"]
    # Use immutable per-batch paths so multiple collectors cannot overwrite one another.
    # Initialize a new repository with a README before first use.
    branch = check()
    from urllib.parse import quote
    ref = "git/ref/heads/"+quote(branch,safe="")
    prefix = "batches/"+batch+"/"
    expected = {prefix+k:blob_id(v) for k,v in files.items()}
    def head():
        return api("GET",endpoint+"/"+ref)["object"]["sha"]
    def paths(sha):
        commit = api("GET",endpoint+"/git/commits/"+sha)
        tree = commit["tree"]["sha"]
        index = api("GET",endpoint+"/git/trees/"+tree+"?recursive=1")
        if index.get("truncated"):
            raise ValueError("remote tree too large for verified recursive read")
        return tree,{r["path"]:r["sha"] for r in index["tree"] if r["type"]=="blob" and r["path"].startswith(prefix)}
    for attempt in range(3):
        sha = head()
        base, existing = paths(sha)
        if existing == expected:
            # Check one snapshot root plus every file's Git blob ID in the remotely read tree.
            check()
            with db:
                db.execute("INSERT OR REPLACE INTO sync_log VALUES(?,?,?)",(repo,batch,sha))
            return {"status":"verified","batch":batch,"commit":sha,"files":len(existing)}
        if existing:
            raise ValueError("immutable remote batch is incomplete or differs")
        check()
        entries = [{"path":prefix+k,"mode":"100644","type":"blob","content":v} for k,v in files.items()]
        tree = api("POST",endpoint+"/git/trees",{"base_tree":base,"tree":entries})["sha"]
        commit = api("POST",endpoint+"/git/commits",{"message":"Archive knowledge batch "+batch[:12],
                                                    "tree":tree,"parents":[sha]})["sha"]
        check()
        try:
            api("PATCH",endpoint+"/git/refs/heads/"+quote(branch,safe=""),{"sha":commit,"force":False})
        except OSError:
            if attempt==2 and paths(head())[1]!=expected:
                raise
            time.sleep(0.1*(attempt+1))
        observed = head()
        if paths(observed)[1] == expected:
            check()
            with db:
                db.execute("INSERT OR REPLACE INTO sync_log VALUES(?,?,?)",(repo,batch,observed))
            return {"status":"verified","batch":batch,"commit":observed,"files":len(expected)}
    raise OSError("remote not verified; retry from the local ledger")
